from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import struct
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any


PATCHER_DIR = Path(__file__).resolve().parent
REPO = PATCHER_DIR.parent
DEFAULT_DATA = PATCHER_DIR / "narutorpg3_chs_v36.json"
CTRL_TOKEN_RE = re.compile(r"\{CTRL_[0-9A-Fa-f]{4}\}")

FONT_FILES = {
    "1x1": {
        "map": "font/chs_1x1.map",
        "chunk": "font/chs_1x1.chunk",
        "map_magic": b"CHMP",
        "chunk_magic": b"CHP1",
        "glyph_size": 0x20,
        "canvas": (8, 8),
        "font_size": 8,
        "target": (8, 8),
        "target_y": 0,
    },
    "1x2": {
        "map": "font/chs_1x2.map",
        "chunk": "font/chs_1x2.chunk",
        "map_magic": b"CHMP",
        "chunk_magic": b"CHP2",
        "glyph_size": 0x40,
        "canvas": (8, 16),
        "font_size": 12,
        "target": (8, 12),
        "target_y": 2,
    },
}


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def load_project(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "narutorpg3-chs-final-project-v1":
        raise ValueError(f"unsupported project data schema: {data.get('schema')!r}")
    return data


def decode_rom_image(data: dict[str, Any]) -> bytes:
    rom_image = data["rom_image"]
    if rom_image.get("encoding") != "base64" or rom_image.get("compression") != "zlib":
        raise ValueError("unsupported ROM image encoding")
    compressed = base64.b64decode(rom_image["data"])
    expected_compressed_size = int(rom_image["compressed_size"])
    if len(compressed) != expected_compressed_size:
        raise ValueError(
            f"compressed ROM size mismatch: got {len(compressed)}, expected {expected_compressed_size}"
        )
    rom = zlib.decompress(compressed)
    expected_size = int(rom_image["uncompressed_size"])
    if len(rom) != expected_size:
        raise ValueError(f"ROM size mismatch: got {len(rom)}, expected {expected_size}")
    expected_sha = str(rom_image["sha256"]).upper()
    actual_sha = sha256_bytes(rom)
    if actual_sha != expected_sha:
        raise ValueError(f"ROM SHA256 mismatch: got {actual_sha}, expected {expected_sha}")
    return rom


def parse_nitrofs_files(rom: bytes) -> dict[str, tuple[int, int]]:
    fnt_offset = struct.unpack_from("<I", rom, 0x40)[0]
    fnt_size = struct.unpack_from("<I", rom, 0x44)[0]
    fat_offset = struct.unpack_from("<I", rom, 0x48)[0]
    fat_size = struct.unpack_from("<I", rom, 0x4C)[0]
    if not fnt_offset or not fnt_size or not fat_offset or not fat_size:
        raise ValueError("ROM does not contain a valid NitroFS FNT/FAT")
    if fnt_offset + fnt_size > len(rom) or fat_offset + fat_size > len(rom):
        raise ValueError("NitroFS FNT/FAT points outside the ROM")

    files: dict[str, tuple[int, int]] = {}
    seen_dirs: set[int] = set()

    def dir_entry(dir_id: int) -> tuple[int, int, int]:
        index = dir_id - 0xF000
        offset = fnt_offset + index * 8
        if offset < fnt_offset or offset + 8 > fnt_offset + fnt_size:
            raise ValueError(f"directory id out of FNT range: 0x{dir_id:04X}")
        return struct.unpack_from("<IHH", rom, offset)

    def walk(dir_id: int, prefix: str) -> None:
        if dir_id in seen_dirs:
            raise ValueError(f"NitroFS directory cycle at 0x{dir_id:04X}")
        seen_dirs.add(dir_id)

        subtable_offset, first_file_id, _parent = dir_entry(dir_id)
        cursor = fnt_offset + subtable_offset
        file_id = first_file_id
        while True:
            if cursor >= fnt_offset + fnt_size:
                raise ValueError(f"NitroFS directory 0x{dir_id:04X} is not terminated")
            marker = rom[cursor]
            cursor += 1
            if marker == 0:
                break
            is_dir = bool(marker & 0x80)
            name_len = marker & 0x7F
            name = rom[cursor : cursor + name_len].decode("ascii")
            cursor += name_len
            if is_dir:
                child_dir_id = struct.unpack_from("<H", rom, cursor)[0]
                cursor += 2
                walk(child_dir_id, f"{prefix}{name}/")
            else:
                fat_entry = fat_offset + file_id * 8
                if fat_entry + 8 > fat_offset + fat_size:
                    raise ValueError(f"NitroFS file id out of FAT range: {file_id}")
                start, end = struct.unpack_from("<II", rom, fat_entry)
                if start > end or end > len(rom):
                    raise ValueError(f"NitroFS file points outside ROM: {prefix}{name}")
                files[f"{prefix}{name}"] = (start, end)
                file_id += 1

    walk(0xF000, "")
    return files


def parse_font_map(data: bytes, *, expected_glyph_size: int) -> list[tuple[int, int, int]]:
    if len(data) < 0x20 or data[:4] != b"CHMP":
        raise ValueError("font map is not a CHMP file")
    version, header_size, glyph_size, entry_size = struct.unpack_from("<HHHH", data, 0x04)
    entry_count = struct.unpack_from("<I", data, 0x0C)[0]
    if version != 1 or header_size != 0x20 or entry_size != 0x10:
        raise ValueError(
            f"unsupported CHMP header: version={version}, header=0x{header_size:X}, entry=0x{entry_size:X}"
        )
    if glyph_size != expected_glyph_size:
        raise ValueError(f"font map glyph size mismatch: got 0x{glyph_size:X}, expected 0x{expected_glyph_size:X}")
    expected_size = header_size + entry_count * entry_size
    if expected_size != len(data):
        raise ValueError(f"font map size mismatch: got {len(data)}, expected {expected_size}")

    entries: list[tuple[int, int, int]] = []
    seen_codes: set[int] = set()
    for index in range(entry_count):
        offset = header_size + index * entry_size
        char_code, glyph_offset, _flags, chunk_id = struct.unpack_from("<IIII", data, offset)
        if char_code in seen_codes:
            raise ValueError(f"duplicate font char code: 0x{char_code:04X}")
        seen_codes.add(char_code)
        entries.append((char_code, glyph_offset, chunk_id))
    return entries


def parse_chunk_header(data: bytes, *, expected_magic: bytes) -> tuple[int, int, int, int]:
    if len(data) < 0x20 or data[:4] != expected_magic:
        raise ValueError(f"font chunk is not a {expected_magic.decode('ascii')} file")
    header_size, page_size, source_pages, resident_slots = struct.unpack_from("<IIII", data, 0x04)
    if header_size != 0x20:
        raise ValueError(f"unsupported chunk header size: 0x{header_size:X}")
    expected_size = header_size + (source_pages + resident_slots) * page_size
    if expected_size != len(data):
        raise ValueError(f"chunk size mismatch: got {len(data)}, expected {expected_size}")
    return header_size, page_size, source_pages, resident_slots


def iter_visible_chars(text: str) -> list[str]:
    chars: list[str] = []
    cursor = 0
    while cursor < len(text):
        match = CTRL_TOKEN_RE.match(text, cursor)
        if match:
            cursor = match.end()
            continue
        char = text[cursor]
        # The final code table intentionally excludes single-byte ASCII because
        # those bytes can be control parameters in the game's text stream.
        if not (0x20 <= ord(char) <= 0x7E):
            chars.append(char)
        cursor += 1
    return chars


def build_code_to_char(data: dict[str, Any], map_entries: list[tuple[int, int, int]]) -> dict[int, str]:
    chars: dict[str, None] = {}
    for row in data["translations"]["text_rows"]:
        for char in iter_visible_chars(row.get("zh_text", "")):
            chars.setdefault(char, None)

    char_list = list(chars)
    if len(char_list) != len(map_entries):
        raise ValueError(
            f"reconstructed charset count mismatch: got {len(char_list)}, map has {len(map_entries)} entries"
        )
    return {entry[0]: char for entry, char in zip(map_entries, char_list)}


def render_font_glyphs(
    font_path: Path,
    chars: dict[int, str],
    *,
    canvas: tuple[int, int],
    font_size: int,
    target: tuple[int, int],
    target_y: int,
) -> dict[int, bytes]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("font replacement requires Pillow in the active Python environment") from exc

    if not font_path.is_file():
        raise FileNotFoundError(font_path)

    font = ImageFont.truetype(str(font_path), font_size)
    output: dict[int, bytes] = {}
    canvas_width, canvas_height = canvas
    target_width, target_height = target

    for code, char in chars.items():
        image = Image.new("L", canvas, 0)
        draw = ImageDraw.Draw(image)
        bbox = draw.textbbox((0, 0), char, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (target_width - text_width) // 2 - bbox[0]
        y = target_y + (target_height - text_height) // 2 - bbox[1]
        draw.text((x, y), char, fill=255, font=font)
        output[code] = pack_4bpp_glyph(image, canvas_width, canvas_height)
    return output


def pack_4bpp_glyph(image: Any, width: int, height: int) -> bytes:
    if width != 8 or height not in {8, 16}:
        raise ValueError(f"unsupported glyph canvas: {width}x{height}")
    packed = bytearray()
    for tile_y in range(0, height, 8):
        for y in range(8):
            for x in range(0, width, 2):
                left = 3 if image.getpixel((x, tile_y + y)) >= 128 else 1
                right = 3 if image.getpixel((x + 1, tile_y + y)) >= 128 else 1
                packed.append(left | (right << 4))
    return bytes(packed)


def patch_font_chunk(
    chunk_data: bytes,
    map_entries: list[tuple[int, int, int]],
    glyphs: dict[int, bytes],
    *,
    expected_magic: bytes,
    glyph_size: int,
) -> bytes:
    header_size, page_size, source_pages, resident_slots = parse_chunk_header(
        chunk_data, expected_magic=expected_magic
    )
    patched = bytearray(chunk_data)
    for char_code, glyph_offset, chunk_id in map_entries:
        glyph = glyphs[char_code]
        if len(glyph) != glyph_size:
            raise ValueError(f"rendered glyph size mismatch for 0x{char_code:04X}")
        if chunk_id >= source_pages:
            raise ValueError(f"font map chunk id out of range for 0x{char_code:04X}: {chunk_id}")
        if glyph_offset < header_size or glyph_offset + glyph_size > page_size:
            raise ValueError(f"font map glyph offset out of page for 0x{char_code:04X}: 0x{glyph_offset:X}")
        offset = header_size + chunk_id * page_size + glyph_offset
        patched[offset : offset + glyph_size] = glyph
    resident_start = header_size + source_pages * page_size
    for slot in range(resident_slots):
        source_page = min(slot, source_pages - 1)
        source_offset = header_size + source_page * page_size
        target_offset = resident_start + slot * page_size
        patched[target_offset : target_offset + page_size] = patched[source_offset : source_offset + page_size]
    return bytes(patched)


def apply_font_replacements(
    rom: bytes,
    data: dict[str, Any],
    *,
    font_1x1: Path | None,
    font_1x2: Path | None,
) -> tuple[bytes, list[str]]:
    if not font_1x1 and not font_1x2:
        return rom, []

    files = parse_nitrofs_files(rom)
    patched = bytearray(rom)
    changes: list[str] = []
    reference_entries: list[tuple[int, int, int]] | None = None
    reference_code_to_char: dict[int, str] | None = None

    for mode, font_path in (("1x1", font_1x1), ("1x2", font_1x2)):
        if font_path is None:
            continue
        spec = FONT_FILES[mode]
        map_path = str(spec["map"])
        chunk_path = str(spec["chunk"])
        if map_path not in files or chunk_path not in files:
            raise FileNotFoundError(f"required NitroFS font files are missing: {map_path}, {chunk_path}")

        map_start, map_end = files[map_path]
        chunk_start, chunk_end = files[chunk_path]
        map_data = rom[map_start:map_end]
        chunk_data = rom[chunk_start:chunk_end]
        map_entries = parse_font_map(map_data, expected_glyph_size=int(spec["glyph_size"]))
        if reference_entries is None:
            reference_entries = map_entries
            reference_code_to_char = build_code_to_char(data, map_entries)
        elif [entry[0] for entry in map_entries] != [entry[0] for entry in reference_entries]:
            raise ValueError("1x1 and 1x2 font maps use different char code order")

        assert reference_code_to_char is not None
        glyphs = render_font_glyphs(
            font_path,
            reference_code_to_char,
            canvas=spec["canvas"],  # type: ignore[arg-type]
            font_size=int(spec["font_size"]),
            target=spec["target"],  # type: ignore[arg-type]
            target_y=int(spec["target_y"]),
        )
        new_chunk = patch_font_chunk(
            chunk_data,
            map_entries,
            glyphs,
            expected_magic=spec["chunk_magic"],  # type: ignore[arg-type]
            glyph_size=int(spec["glyph_size"]),
        )
        if len(new_chunk) != len(chunk_data):
            raise ValueError(f"font replacement changed {chunk_path} size")
        patched[chunk_start:chunk_end] = new_chunk
        changes.append(f"{mode}={display_path(font_path)} -> {chunk_path}")

    return bytes(patched), changes


def unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}_{tag}{path.suffix}")
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        indexed = path.with_name(f"{path.stem}_{tag}_{index}{path.suffix}")
        if not indexed.exists():
            return indexed
    raise FileExistsError(f"could not find an unused output path near {path}")


def write_rom(path: Path, data: bytes, *, force: bool) -> Path:
    output = path if force else unique_output_path(path)
    if output.resolve() == (REPO / "rom" / "origin.nds").resolve():
        raise ValueError("refusing to overwrite rom/origin.nds")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def command_info(args: argparse.Namespace) -> int:
    data = load_project(repo_path(args.data))
    source = data["source_rom"]
    output = data["output_rom"]
    translations = data["translations"]
    writeback = data["writeback"]
    term = writeback.get("terminator_padding_audit", {})
    print(f"version={data['version']}")
    print(f"status={data.get('status', '')}")
    print(f"source_sha256={source['sha256']}")
    print(f"output_sha256={output['sha256']}")
    print(f"text_rows={translations['text_row_count']}")
    print(f"menu_rows={translations['menu_row_count']}")
    print(f"manual_overrides={translations['manual_override_row_count']}")
    print(f"structural_risk_rows={writeback.get('structural_audit', {}).get('risk_rows')}")
    print(f"pre_0300_fullwidth_padding_rows={term.get('fullwidth_padding_before_final_0300_rows')}")
    print(f"post_0300_zero_then_later_0300_rows={term.get('terminator_then_zero_then_later_0300_rows')}")
    print(f"post_0300_fullwidth_then_later_0300_rows={term.get('terminator_then_fullwidth_then_later_0300_rows')}")
    return 0


def command_verify_data(args: argparse.Namespace) -> int:
    data_path = repo_path(args.data)
    data = load_project(data_path)
    rom = decode_rom_image(data)
    print(f"data={display_path(data_path)}")
    print(f"embedded_rom_size={len(rom)}")
    print(f"embedded_rom_sha256={sha256_bytes(rom)}")
    return 0


def command_build(args: argparse.Namespace) -> int:
    data_path = repo_path(args.data)
    origin_path = repo_path(args.origin_rom)
    output_path = repo_path(args.output)
    data = load_project(data_path)

    if not origin_path.is_file():
        raise FileNotFoundError(origin_path)
    expected_origin_sha = str(data["source_rom"]["sha256"]).upper()
    actual_origin_sha = sha256_file(origin_path)
    if actual_origin_sha != expected_origin_sha:
        raise ValueError(f"origin ROM SHA256 mismatch: got {actual_origin_sha}, expected {expected_origin_sha}")

    rom = decode_rom_image(data)
    font_1x1 = repo_path(args.font_1x1 or args.font) if (args.font_1x1 or args.font) else None
    font_1x2 = repo_path(args.font_1x2 or args.font) if (args.font_1x2 or args.font) else None
    rom, font_changes = apply_font_replacements(rom, data, font_1x1=font_1x1, font_1x2=font_1x2)
    output = write_rom(output_path, rom, force=args.force)
    print(f"data={display_path(data_path)}")
    print(f"origin={display_path(origin_path)}")
    for change in font_changes:
        print(f"font_replaced={change}")
    print(f"output_rom={display_path(output)}")
    print(f"output_sha256={sha256_bytes(rom)}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the verified Naruto RPG3 Chinese ROM from one consolidated project data file."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Validate origin.nds and write the final patched ROM.")
    build.add_argument("--data", default=DEFAULT_DATA.as_posix())
    build.add_argument("--origin-rom", default="rom/origin.nds")
    build.add_argument("--output", default="rom/narutorpg3_chs.nds")
    build.add_argument("--font", help="Use one TTF/TTC/OTF font for both 8x8 and 8x16 Chinese glyphs.")
    build.add_argument(
        "--font-1x1",
        "--font-8x8",
        dest="font_1x1",
        help="Use this font for the 8x8 / 1x1 Chinese glyph chunk.",
    )
    build.add_argument(
        "--font-1x2",
        "--font-8x16",
        dest="font_1x2",
        help="Use this font for the 8x16 / 1x2 Chinese glyph chunk.",
    )
    build.add_argument("--force", action="store_true", help="Overwrite the output path if it already exists.")
    build.set_defaults(func=command_build)

    info = subparsers.add_parser("info", help="Print project summary from the consolidated data file.")
    info.add_argument("--data", default=DEFAULT_DATA.as_posix())
    info.set_defaults(func=command_info)

    verify = subparsers.add_parser("verify-data", help="Decode and hash-check the embedded final ROM image.")
    verify.add_argument("--data", default=DEFAULT_DATA.as_posix())
    verify.set_defaults(func=command_verify_data)
    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    commands = {"build", "info", "verify-data", "-h", "--help"}
    if not argv or argv[0] not in commands:
        return ["build", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(normalize_argv(list(sys.argv[1:] if argv is None else argv)))
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
