from __future__ import annotations

import argparse
from datetime import datetime
import os
import stat
import shutil
from pathlib import Path

import patch_vram_font_chunk_table_dual_mode_1x1_copy_probe as cache
import patch_vram_font_split_map_probe as split


FONT_FILES = {
    "chs_1x1.map": "1x1_map",
    "chs_1x1.chunk": "1x1_chunk",
    "chs_1x2.map": "1x2_map",
    "chs_1x2.chunk": "1x2_chunk",
}

MAP_HEADER_SIZE = 0x20
MAP_ENTRY_SIZE = 0x10
MAP_VERSION = 1
PACK_HEADER_SIZE = 0x20
FONT_SPECS = {
    "1x1": {
        "map_key": "1x1_map",
        "chunk_key": "1x1_chunk",
        "pack_magic": b"CHP1",
        "glyph_size": 0x20,
        "page_size": cache.PAGE_1X1_SIZE,
        "resident_slots": 1,
        "min_source_pages": 1,
    },
    "1x2": {
        "map_key": "1x2_map",
        "chunk_key": "1x2_chunk",
        "pack_magic": b"CHP2",
        "glyph_size": 0x40,
        "page_size": cache.SOURCE_PAGE1_OFFSET - cache.SOURCE_PAGE0_OFFSET,
        "resident_slots": 2,
        "min_source_pages": 2,
    },
}


class FontFormatError(ValueError):
    pass


def require_under(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"{resolved} is outside {root_resolved}")


def remove_existing(path: Path, *, allowed_root: Path) -> None:
    if not path.exists():
        return
    require_under(path, allowed_root)
    if path.is_dir():
        def make_writable_and_retry(func, failing_path, _exc_info):
            os.chmod(failing_path, stat.S_IWRITE)
            func(failing_path)

        shutil.rmtree(path, onexc=make_writable_and_retry)
    else:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()


def unique_build_path(path: Path, run_tag: str) -> Path:
    candidate = path.with_name(f"{path.stem}_build_{run_tag}{path.suffix}")
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        indexed = path.with_name(f"{path.stem}_build_{run_tag}_{index}{path.suffix}")
        if not indexed.exists():
            return indexed
    raise FileExistsError(f"could not find an unused build path near {path}")


def remove_or_fallback(path: Path, *, allowed_root: Path, run_tag: str) -> Path:
    if not path.exists():
        return path
    try:
        remove_existing(path, allowed_root=allowed_root)
        return path
    except OSError as exc:
        fallback = unique_build_path(path, run_tag)
        print(f"warning: could not remove {path}: {exc}; using {fallback}")
        return fallback


def copy_font_files(font_dir: Path, work: Path) -> dict[str, Path]:
    data_font = work / "data" / "font"
    data_font.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for filename, key in FONT_FILES.items():
        src = font_dir / filename
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = data_font / filename
        shutil.copy2(src, dst)
        copied[key] = dst
    return copied


def read_u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def read_u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def validate_map(path: Path, *, glyph_size: int, page_size: int, source_page_count: int) -> None:
    data = path.read_bytes()
    if len(data) < MAP_HEADER_SIZE:
        raise FontFormatError(f"{path} is too small for a CHMP header")
    if data[:4] != b"CHMP":
        raise FontFormatError(f"{path} has invalid magic {data[:4]!r}, expected CHMP")
    version = read_u16(data, 4)
    header_size = read_u16(data, 6)
    actual_glyph_size = read_u16(data, 8)
    entry_size = read_u16(data, 10)
    entry_count = read_u32(data, 12)
    if version != MAP_VERSION:
        raise FontFormatError(f"{path} version={version}, expected {MAP_VERSION}")
    if header_size != MAP_HEADER_SIZE:
        raise FontFormatError(f"{path} header_size=0x{header_size:X}, expected 0x{MAP_HEADER_SIZE:X}")
    if actual_glyph_size != glyph_size:
        raise FontFormatError(f"{path} glyph_size=0x{actual_glyph_size:X}, expected 0x{glyph_size:X}")
    if entry_size != MAP_ENTRY_SIZE:
        raise FontFormatError(f"{path} entry_size=0x{entry_size:X}, expected 0x{MAP_ENTRY_SIZE:X}")
    expected_size = header_size + entry_count * entry_size
    if len(data) < expected_size:
        raise FontFormatError(f"{path} is truncated: size=0x{len(data):X}, expected at least 0x{expected_size:X}")

    seen_chars: set[int] = set()
    for index in range(entry_count):
        offset = header_size + index * entry_size
        char_code = read_u32(data, offset)
        glyph_offset = read_u32(data, offset + 4)
        chunk_id = read_u16(data, offset + 12)
        if char_code in seen_chars:
            raise FontFormatError(f"{path} has duplicate char_code=0x{char_code:04X}")
        seen_chars.add(char_code)
        if chunk_id >= source_page_count:
            raise FontFormatError(
                f"{path} entry {index} char=0x{char_code:04X} chunk_id={chunk_id}, source_page_count={source_page_count}"
            )
        if glyph_offset < MAP_HEADER_SIZE or glyph_offset + glyph_size > page_size:
            raise FontFormatError(
                f"{path} entry {index} char=0x{char_code:04X} glyph_offset=0x{glyph_offset:X} outside page_size=0x{page_size:X}"
            )


def validate_pack(path: Path, *, magic: bytes, glyph_size: int, page_size: int, resident_slots: int) -> int:
    data = path.read_bytes()
    if len(data) < PACK_HEADER_SIZE:
        raise FontFormatError(f"{path} is too small for a pack header")
    if data[:4] != magic:
        raise FontFormatError(f"{path} has invalid magic {data[:4]!r}, expected {magic.decode('ascii')}")
    header_size = read_u32(data, 4)
    actual_page_size = read_u32(data, 8)
    source_page_count = read_u32(data, 12)
    actual_resident_slots = read_u32(data, 16)
    if header_size != PACK_HEADER_SIZE:
        raise FontFormatError(f"{path} header_size=0x{header_size:X}, expected 0x{PACK_HEADER_SIZE:X}")
    if actual_page_size != page_size:
        raise FontFormatError(f"{path} page_size=0x{actual_page_size:X}, expected 0x{page_size:X}")
    if actual_resident_slots != resident_slots:
        raise FontFormatError(f"{path} resident_slots={actual_resident_slots}, expected {resident_slots}")
    if source_page_count == 0:
        raise FontFormatError(f"{path} source_page_count must be non-zero")
    expected_size = header_size + (resident_slots + source_page_count) * page_size
    if len(data) < expected_size:
        raise FontFormatError(f"{path} is truncated: size=0x{len(data):X}, expected at least 0x{expected_size:X}")
    if MAP_HEADER_SIZE + glyph_size > page_size:
        raise FontFormatError(f"{path} page_size=0x{page_size:X} cannot hold fallback glyph size 0x{glyph_size:X}")
    return source_page_count


def validate_font_files(files: dict[str, Path]) -> None:
    for name, spec in FONT_SPECS.items():
        source_page_count = validate_pack(
            files[spec["chunk_key"]],
            magic=spec["pack_magic"],
            glyph_size=spec["glyph_size"],
            page_size=spec["page_size"],
            resident_slots=spec["resident_slots"],
        )
        if source_page_count < spec["min_source_pages"]:
            raise FontFormatError(
                f"{files[spec['chunk_key']]} source_page_count={source_page_count}, "
                f"expected at least {spec['min_source_pages']}"
            )
        validate_map(
            files[spec["map_key"]],
            glyph_size=spec["glyph_size"],
            page_size=spec["page_size"],
            source_page_count=source_page_count,
        )
        print(f"{name}_font_format=ok source_pages={source_page_count}")


def build(args: argparse.Namespace) -> Path:
    repo = Path(__file__).resolve().parents[1]
    work = (repo / args.work).resolve()
    output_rom = (repo / args.output).resolve()
    origin_work = repo / "rom" / "unpacked" / "origin"

    if not origin_work.is_dir():
        raise FileNotFoundError(f"missing unpacked origin: {origin_work}")
    if output_rom.name == "origin.nds":
        raise ValueError("refusing to overwrite rom/origin.nds")

    if args.force:
        run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        work = remove_or_fallback(work, allowed_root=repo / "rom" / "unpacked", run_tag=run_tag)
        output_rom = remove_or_fallback(output_rom, allowed_root=repo / "rom", run_tag=run_tag)

    split.copy_unpacked(origin_work, work)
    if args.font_dir:
        files = copy_font_files(Path(args.font_dir), work)
    else:
        files = cache.write_probe_files(
            work,
            shared_char=int(args.shared_char, 0),
            char_1x1_extra=int(args.char_1x1_extra, 0),
            char_1x2_a=int(args.char_1x2_a, 0),
            char_1x2_b=int(args.char_1x2_b, 0),
            char_1x2_repeat=int(args.char_1x2_repeat, 0),
            space_char=int(args.space_char, 0),
        )
    validate_font_files(files)

    cache.patch_arm9(work / "arm9.bin")
    cache.patch_overlay(work / "overlay" / "overlay_0000.bin")
    split.repack(repo, work, output_rom)

    print(f"output={output_rom}")
    print(f"work={work}")
    print(f"copy_hook=0x{cache.EXT_COPY_HOOK_ADDR:08X} size=0x{len(cache.build_copy_hook()):X}")
    print(f"consume_trampoline=0x{cache.DUAL_CONSUME_HOOK_ADDR:08X} size=0x{len(cache.build_consume_trampoline()):X}")
    print(f"consume_body=0x{cache.CONSUME_BODY_ADDR:08X} size=0x{len(cache.build_consume_body()):X}")
    for name, path in files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")
    return output_rom


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the integrated dynamic font cache ROM.")
    parser.add_argument("--work", default="rom/unpacked/narutorpg3_chs_dynamic_font_v0")
    parser.add_argument("--output", default="rom/narutorpg3_chs_dynamic_font_v0.nds")
    parser.add_argument("--font-dir", default="", help="Directory containing chs_1x1.map/chunk and chs_1x2.map/chunk")
    parser.add_argument("--force", action="store_true", help="Replace the selected work directory and output ROM")
    parser.add_argument("--shared-char", default=hex(split.DEFAULT_SHARED_CHAR))
    parser.add_argument("--char-1x1-extra", default=hex(split.DEFAULT_1X1_EXTRA_CHAR))
    parser.add_argument("--char-1x2-a", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_A))
    parser.add_argument("--char-1x2-b", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_B))
    parser.add_argument("--char-1x2-repeat", default="0x82C6")
    parser.add_argument("--space-char", default="0x8140")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
