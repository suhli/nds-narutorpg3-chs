from __future__ import annotations

import argparse
import io
import struct
import sys
import zlib
from array import array
from pathlib import Path


PATCHER_DIR = Path(__file__).resolve().parent
REPO = PATCHER_DIR.parent

DEFAULT_SOURCE = REPO / "rom" / "origin.nds"
DEFAULT_TARGET = REPO / "rom" / "narutorpg3_chs_patcher_v36_no_pre03_spaces.nds"
DEFAULT_OUTPUT = REPO / "dist" / "narutorpg3_chs_v36.bps"

BPS_MAGIC = b"BPS1"
SOURCE_READ = 0
TARGET_READ = 1
SOURCE_COPY = 2
TARGET_COPY = 3


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def crc32(data: bytes | bytearray) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def encode_number(value: int) -> bytes:
    if value < 0:
        raise ValueError(f"BPS number must be non-negative: {value}")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(0x80 | byte)
            return bytes(out)
        out.append(byte)
        value -= 1


def decode_number(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        if offset >= len(data):
            raise ValueError("unexpected end of BPS variable-length integer")
        byte = data[offset]
        offset += 1
        value += (byte & 0x7F) * shift
        if byte & 0x80:
            return value, offset
        shift <<= 7
        value += shift


def encode_signed_offset(value: int) -> bytes:
    encoded = (abs(value) << 1) | (1 if value < 0 else 0)
    return encode_number(encoded)


def decode_signed_offset(data: bytes, offset: int) -> tuple[int, int]:
    encoded, offset = decode_number(data, offset)
    value = encoded >> 1
    if encoded & 1:
        value = -value
    return value, offset


def encode_action(action: int, length: int) -> bytes:
    if length <= 0:
        raise ValueError(f"BPS action length must be positive: {length}")
    return encode_number(((length - 1) << 2) | action)


def token_hash(buffer: bytes, offset: int, hash_bits: int) -> int:
    value = struct.unpack_from("<Q", buffer, offset)[0]
    value = (value * 0x9E3779B185EBCA87) & 0xFFFFFFFFFFFFFFFF
    return value >> (64 - hash_bits)


def common_prefix(a: bytes, a_offset: int, b: bytes, b_offset: int, limit: int) -> int:
    matched = 0
    chunk = 4096
    while matched + chunk <= limit:
        a_slice = a[a_offset + matched : a_offset + matched + chunk]
        b_slice = b[b_offset + matched : b_offset + matched + chunk]
        if a_slice != b_slice:
            break
        matched += chunk
    while matched < limit and a[a_offset + matched] == b[b_offset + matched]:
        matched += 1
    return matched


class SourceIndex:
    def __init__(self, source: bytes, *, min_match: int, index_step: int, hash_bits: int) -> None:
        if min_match < 8:
            raise ValueError("min_match must be at least 8")
        if index_step < 1:
            raise ValueError("index_step must be positive")
        if not (12 <= hash_bits <= 26):
            raise ValueError("hash_bits must be between 12 and 26")

        self.source = source
        self.min_match = min_match
        self.index_step = index_step
        self.hash_bits = hash_bits
        self.bucket_count = 1 << hash_bits

        if len(source) < min_match:
            self.entry_count = 0
            self.heads = array("i", [-1]) * self.bucket_count
            self.next = array("i")
            return

        self.entry_count = ((len(source) - min_match) // index_step) + 1
        self.heads = array("i", [-1]) * self.bucket_count
        self.next = array("i", [-1]) * self.entry_count

        for entry in range(self.entry_count - 1, -1, -1):
            source_offset = entry * index_step
            bucket = token_hash(source, source_offset, hash_bits)
            self.next[entry] = self.heads[bucket]
            self.heads[bucket] = entry

    def find_best(
        self,
        target: bytes,
        target_offset: int,
        *,
        max_candidates: int,
    ) -> tuple[int, int]:
        if self.entry_count == 0 or target_offset + self.min_match > len(target):
            return -1, 0

        bucket = token_hash(target, target_offset, self.hash_bits)
        entry = self.heads[bucket]
        checked = 0
        best_offset = -1
        best_length = 0
        token = target[target_offset : target_offset + self.min_match]

        while entry != -1 and checked < max_candidates:
            source_offset = entry * self.index_step
            if self.source[source_offset : source_offset + self.min_match] == token:
                limit = min(len(self.source) - source_offset, len(target) - target_offset)
                length = common_prefix(self.source, source_offset, target, target_offset, limit)
                if length > best_length:
                    best_offset = source_offset
                    best_length = length
            entry = self.next[entry]
            checked += 1

        if best_length < self.min_match:
            return -1, 0
        return best_offset, best_length


class BpsWriter:
    def __init__(self) -> None:
        self.patch = io.BytesIO()
        self.source_relative_offset = 0

    def write_header(self, source_size: int, target_size: int, metadata: bytes) -> None:
        self.patch.write(BPS_MAGIC)
        self.patch.write(encode_number(source_size))
        self.patch.write(encode_number(target_size))
        self.patch.write(encode_number(len(metadata)))
        self.patch.write(metadata)

    def source_read(self, length: int) -> None:
        self.patch.write(encode_action(SOURCE_READ, length))

    def target_read(self, data: bytes | bytearray) -> None:
        if not data:
            return
        self.patch.write(encode_action(TARGET_READ, len(data)))
        self.patch.write(data)

    def source_copy(self, source_offset: int, length: int) -> None:
        relative = source_offset - self.source_relative_offset
        self.patch.write(encode_action(SOURCE_COPY, length))
        self.patch.write(encode_signed_offset(relative))
        self.source_relative_offset = source_offset + length

    def finish(self, source: bytes, target: bytes) -> bytes:
        self.patch.write(struct.pack("<I", crc32(source)))
        self.patch.write(struct.pack("<I", crc32(target)))
        patch_without_crc = self.patch.getvalue()
        self.patch.write(struct.pack("<I", crc32(patch_without_crc)))
        return self.patch.getvalue()


def make_bps(
    source: bytes,
    target: bytes,
    *,
    metadata: bytes,
    min_match: int,
    index_step: int,
    hash_bits: int,
    max_candidates: int,
    target_read_flush: int,
    quiet: bool,
) -> bytes:
    if not quiet:
        print(
            f"building source index: source={len(source)} bytes, step={index_step}, "
            f"min_match={min_match}, hash_bits={hash_bits}",
            file=sys.stderr,
        )
    index = SourceIndex(source, min_match=min_match, index_step=index_step, hash_bits=hash_bits)

    writer = BpsWriter()
    writer.write_header(len(source), len(target), metadata)
    target_buffer = bytearray()
    target_offset = 0
    next_progress = 0
    progress_step = 4 * 1024 * 1024

    def flush_target() -> None:
        nonlocal target_buffer
        if target_buffer:
            writer.target_read(target_buffer)
            target_buffer = bytearray()

    while target_offset < len(target):
        if not quiet and target_offset >= next_progress:
            percent = (target_offset * 100.0) / max(1, len(target))
            print(f"diff progress: {target_offset}/{len(target)} ({percent:.1f}%)", file=sys.stderr)
            next_progress = target_offset + progress_step

        same_offset_length = 0
        if target_offset < len(source):
            same_limit = min(len(source) - target_offset, len(target) - target_offset)
            same_offset_length = common_prefix(source, target_offset, target, target_offset, same_limit)

        source_copy_offset, source_copy_length = index.find_best(
            target, target_offset, max_candidates=max_candidates
        )

        if same_offset_length >= min_match and same_offset_length >= source_copy_length:
            flush_target()
            writer.source_read(same_offset_length)
            target_offset += same_offset_length
            continue

        if source_copy_length >= min_match:
            flush_target()
            writer.source_copy(source_copy_offset, source_copy_length)
            target_offset += source_copy_length
            continue

        target_buffer.append(target[target_offset])
        target_offset += 1
        if len(target_buffer) >= target_read_flush:
            flush_target()

    flush_target()
    return writer.finish(source, target)


def apply_bps(source: bytes, patch: bytes) -> bytes:
    if not patch.startswith(BPS_MAGIC):
        raise ValueError("not a BPS1 patch")
    if len(patch) < 16:
        raise ValueError("patch is too small")

    expected_patch_crc = struct.unpack_from("<I", patch, len(patch) - 4)[0]
    actual_patch_crc = crc32(patch[:-4])
    if actual_patch_crc != expected_patch_crc:
        raise ValueError(f"patch CRC mismatch: got {actual_patch_crc:08X}, expected {expected_patch_crc:08X}")

    expected_source_crc = struct.unpack_from("<I", patch, len(patch) - 12)[0]
    actual_source_crc = crc32(source)
    if actual_source_crc != expected_source_crc:
        raise ValueError(f"source CRC mismatch: got {actual_source_crc:08X}, expected {expected_source_crc:08X}")

    offset = len(BPS_MAGIC)
    source_size, offset = decode_number(patch, offset)
    target_size, offset = decode_number(patch, offset)
    metadata_size, offset = decode_number(patch, offset)
    offset += metadata_size

    if source_size != len(source):
        raise ValueError(f"source size mismatch: got {len(source)}, expected {source_size}")
    if offset > len(patch) - 12:
        raise ValueError("metadata extends past command stream")

    target = bytearray()
    source_relative_offset = 0
    target_relative_offset = 0
    command_end = len(patch) - 12

    while offset < command_end:
        encoded, offset = decode_number(patch, offset)
        action = encoded & 3
        length = (encoded >> 2) + 1
        output_offset = len(target)

        if action == SOURCE_READ:
            end = output_offset + length
            if end > len(source):
                raise ValueError("SourceRead extends past source")
            target.extend(source[output_offset:end])
        elif action == TARGET_READ:
            end = offset + length
            if end > command_end:
                raise ValueError("TargetRead extends past command stream")
            target.extend(patch[offset:end])
            offset = end
        elif action == SOURCE_COPY:
            relative, offset = decode_signed_offset(patch, offset)
            source_relative_offset += relative
            end = source_relative_offset + length
            if source_relative_offset < 0 or end > len(source):
                raise ValueError("SourceCopy extends past source")
            target.extend(source[source_relative_offset:end])
            source_relative_offset = end
        elif action == TARGET_COPY:
            relative, offset = decode_signed_offset(patch, offset)
            target_relative_offset += relative
            if target_relative_offset < 0:
                raise ValueError("TargetCopy starts before target")
            for _ in range(length):
                if target_relative_offset >= len(target):
                    raise ValueError("TargetCopy reads past generated target")
                target.append(target[target_relative_offset])
                target_relative_offset += 1
        else:
            raise AssertionError(action)

        if len(target) > target_size:
            raise ValueError("generated target exceeds declared size")

    if len(target) != target_size:
        raise ValueError(f"target size mismatch: got {len(target)}, expected {target_size}")

    expected_target_crc = struct.unpack_from("<I", patch, len(patch) - 8)[0]
    actual_target_crc = crc32(target)
    if actual_target_crc != expected_target_crc:
        raise ValueError(f"target CRC mismatch: got {actual_target_crc:08X}, expected {expected_target_crc:08X}")
    return bytes(target)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a BPS patch from origin.nds to the verified Chinese ROM.")
    parser.add_argument("--source", default=DEFAULT_SOURCE.as_posix(), help="Original ROM path.")
    parser.add_argument("--target", default=DEFAULT_TARGET.as_posix(), help="Patched ROM path.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix(), help="Output .bps path.")
    parser.add_argument("--metadata", default="Naruto RPG3 CHS v36 no-pre03-spaces\n")
    parser.add_argument("--min-match", type=int, default=8)
    parser.add_argument("--index-step", type=int, default=4)
    parser.add_argument("--hash-bits", type=int, default=22)
    parser.add_argument("--max-candidates", type=int, default=64)
    parser.add_argument("--target-read-flush", type=int, default=1024 * 1024)
    parser.add_argument("--no-verify", action="store_true", help="Skip applying the patch back in memory.")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)

    source_path = repo_path(args.source)
    target_path = repo_path(args.target)
    output_path = repo_path(args.output)

    source = source_path.read_bytes()
    target = target_path.read_bytes()
    metadata = args.metadata.encode("utf-8")

    patch = make_bps(
        source,
        target,
        metadata=metadata,
        min_match=args.min_match,
        index_step=args.index_step,
        hash_bits=args.hash_bits,
        max_candidates=args.max_candidates,
        target_read_flush=args.target_read_flush,
        quiet=args.quiet,
    )

    if not args.no_verify:
        rebuilt = apply_bps(source, patch)
        if rebuilt != target:
            raise ValueError("internal BPS verification failed: rebuilt ROM differs from target")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(patch)

    print(f"source={display_path(source_path)}")
    print(f"target={display_path(target_path)}")
    print(f"output={display_path(output_path)}")
    print(f"source_size={len(source)}")
    print(f"target_size={len(target)}")
    print(f"patch_size={len(patch)}")
    print(f"source_crc32={crc32(source):08X}")
    print(f"target_crc32={crc32(target):08X}")
    print(f"patch_crc32={crc32(patch[:-4]):08X}")
    print(f"verified={'no' if args.no_verify else 'yes'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
