from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import struct
import sys
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PATCHER_DIR = Path(__file__).resolve().parent
REPO = PATCHER_DIR.parent
DEFAULT_DATA = PATCHER_DIR / "narutorpg3_chs_v36.json"
DEFAULT_CODE_TABLE = PATCHER_DIR / "resources" / "text" / "zh_code_table.tsv"
MAP_HEADER_SIZE = 0x20
MAP_ENTRY_SIZE = 0x10
PACK_HEADER_SIZE = 0x20
GLYPH_INK = 3
GLYPH_BG = 1

FONT_FILES = {
    "1x1": {
        "map": "font/chs_1x1.map",
        "chunk": "font/chs_1x1.chunk",
        "map_magic": b"CHMP",
        "chunk_magic": b"CHP1",
        "page_magic": b"CHG1",
        "page_size": 0x80,
        "glyph_size": 0x20,
        "canvas": (8, 8),
        "font_size": 8,
        "target": (8, 8),
        "target_y": 0,
        "resident_source_pages": (0,),
    },
    "1x2": {
        "map": "font/chs_1x2.map",
        "chunk": "font/chs_1x2.chunk",
        "map_magic": b"CHMP",
        "chunk_magic": b"CHP2",
        "page_magic": b"CHPG",
        "page_size": 0xE0,
        "glyph_size": 0x40,
        "canvas": (8, 16),
        "font_size": 12,
        "target": (8, 12),
        "target_y": 2,
        "resident_source_pages": (1, None),
    },
}


@dataclass(frozen=True)
class FontEntry:
    code: int
    char: str
    modes: frozenset[str]


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


def parse_font_modes(value: str) -> frozenset[str]:
    modes = {part.strip() for part in value.split(",") if part.strip()}
    invalid = modes - {"1x1", "1x2"}
    if invalid:
        raise ValueError(f"invalid font modes: {sorted(invalid)}")
    if not modes:
        raise ValueError("font code table entry must include at least one mode")
    return frozenset(modes)


def load_code_table(path: Path) -> list[FontEntry]:
    if not path.is_file():
        raise FileNotFoundError(path)
    entries: list[FontEntry] = []
    seen: set[tuple[int, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"char", "code_hex", "modes"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"font code table must contain columns: {sorted(required)}")
        for line_no, row in enumerate(reader, 2):
            char = row["char"]
            if not char:
                raise ValueError(f"{display_path(path)}:{line_no}: empty char")
            code = int(row["code_hex"], 0)
            modes = parse_font_modes(row["modes"])
            for mode in modes:
                key = (code, mode)
                if key in seen:
                    raise ValueError(f"{display_path(path)}:{line_no}: duplicate code 0x{code:04X} for {mode}")
                seen.add(key)
            entries.append(FontEntry(code=code, char=char[0], modes=modes))
    if not entries:
        raise ValueError(f"font code table is empty: {display_path(path)}")
    return entries


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


def build_font_map(glyph_size: int, entries: list[tuple[int, int, int]]) -> bytes:
    data = bytearray()
    data += b"CHMP"
    data += struct.pack("<HHHH", 1, MAP_HEADER_SIZE, glyph_size, MAP_ENTRY_SIZE)
    data += struct.pack("<I", len(entries))
    data += struct.pack("<IIII", 0, 0, 0, 0)
    for char_code, glyph_offset, chunk_id in entries:
        data += struct.pack("<IIHHHH", char_code, glyph_offset, 0, 0, chunk_id, 0)
    return bytes(data)


def build_font_page(
    *,
    magic: bytes,
    page_size: int,
    glyph_size: int,
    fallback: bytes,
    glyphs: list[bytes],
) -> bytes:
    page = bytearray(page_size)
    page[:4] = magic
    page[4:8] = page_size.to_bytes(4, "little")
    page[8:12] = glyph_size.to_bytes(4, "little")
    page[MAP_HEADER_SIZE : MAP_HEADER_SIZE + glyph_size] = fallback
    offset = MAP_HEADER_SIZE + glyph_size
    for glyph in glyphs:
        page[offset : offset + glyph_size] = glyph
        offset += glyph_size
    return bytes(page)


def build_font_pack(
    entries: list[FontEntry],
    glyphs: dict[int, bytes],
    fallback: bytes,
    *,
    mode: str,
    spec: dict[str, Any],
) -> tuple[bytes, bytes, int]:
    glyph_size = int(spec["glyph_size"])
    page_size = int(spec["page_size"])
    resident_sources = tuple(spec["resident_source_pages"])
    mode_entries = [entry for entry in entries if mode in entry.modes]
    slots_per_page = (page_size - (MAP_HEADER_SIZE + glyph_size)) // glyph_size
    if slots_per_page <= 0:
        raise ValueError(f"{mode} font page has no room for custom glyphs")

    source_page_count = max(2, math.ceil(len(mode_entries) / slots_per_page))
    pages: list[bytes] = []
    map_entries: list[tuple[int, int, int]] = []

    for page_index in range(source_page_count):
        start = page_index * slots_per_page
        page_entries = mode_entries[start : start + slots_per_page]
        page_glyphs = [glyphs[entry.code] for entry in page_entries]
        pages.append(
            build_font_page(
                magic=spec["page_magic"],
                page_size=page_size,
                glyph_size=glyph_size,
                fallback=fallback,
                glyphs=page_glyphs,
            )
        )
        for slot_index, entry in enumerate(page_entries):
            glyph_offset = MAP_HEADER_SIZE + glyph_size + slot_index * glyph_size
            map_entries.append((entry.code, glyph_offset, page_index))

    header = bytearray(PACK_HEADER_SIZE)
    header[:4] = spec["chunk_magic"]
    header[4:8] = PACK_HEADER_SIZE.to_bytes(4, "little")
    header[8:12] = page_size.to_bytes(4, "little")
    header[12:16] = source_page_count.to_bytes(4, "little")
    header[16:20] = len(resident_sources).to_bytes(4, "little")

    resident_pages: list[bytes] = []
    for source_page in resident_sources:
        if source_page is None:
            resident_pages.append(bytes(page_size))
        else:
            resident_pages.append(pages[int(source_page)])
    return build_font_map(glyph_size, map_entries), bytes(header) + b"".join(resident_pages) + b"".join(pages), source_page_count


def render_mono_pixels(face: Any, char: str, *, px_size: int, cell_size: tuple[int, int] | None) -> list[list[int]]:
    if cell_size is None:
        face.set_pixel_sizes(0, px_size)
    else:
        face.set_pixel_sizes(cell_size[0], cell_size[1])
    import freetype

    face.load_char(char, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bitmap = face.glyph.bitmap
    width = bitmap.width
    height = bitmap.rows
    pitch = bitmap.pitch
    stride = abs(pitch)
    buffer = bytes(bitmap.buffer)
    pixels = [[0] * width for _ in range(height)]
    for y in range(height):
        row_start = y * pitch if pitch >= 0 else (height - 1 - y) * stride
        row = buffer[row_start : row_start + stride]
        for x in range(width):
            pixels[y][x] = (row[x >> 3] >> (7 - (x & 7))) & 1
    return pixels


def blit_center_pixels(src: list[list[int]], *, width: int, height: int, xoff: int = 0, yoff: int = 0) -> list[list[int]]:
    src_h = len(src)
    src_w = len(src[0]) if src_h else 0
    dst = [[0] * width for _ in range(height)]
    ox = (width - src_w) // 2 + xoff
    oy = (height - src_h) // 2 + yoff
    for y, row in enumerate(src):
        ty = oy + y
        if not 0 <= ty < height:
            continue
        for x, value in enumerate(row):
            tx = ox + x
            if 0 <= tx < width:
                dst[ty][tx] = value
    return dst


def pack_4bpp_pixels(pixels: list[list[int]], *, width: int, height: int) -> bytes:
    if width != 8 or height not in {8, 16}:
        raise ValueError(f"unsupported glyph canvas: {width}x{height}")
    if len(pixels) != height or any(len(row) != width for row in pixels):
        raise ValueError(f"glyph pixel grid does not match canvas: {width}x{height}")
    packed = bytearray()
    for tile_y in range(0, height, 8):
        for y in range(8):
            for x in range(0, width, 2):
                left = GLYPH_INK if pixels[tile_y + y][x] else GLYPH_BG
                right = GLYPH_INK if pixels[tile_y + y][x + 1] else GLYPH_BG
                packed.append(left | (right << 4))
    return bytes(packed)


def render_font_glyphs(
    font_path: Path,
    chars: dict[int, str],
    *,
    canvas: tuple[int, int],
    font_size: int,
    target: tuple[int, int],
    target_y: int,
) -> tuple[dict[int, bytes], bytes]:
    try:
        import freetype
    except ImportError as exc:
        raise RuntimeError("font replacement requires freetype-py in the active Python environment") from exc

    if not font_path.is_file():
        raise FileNotFoundError(font_path)

    face = freetype.Face(str(font_path))
    canvas_width, canvas_height = canvas
    target_width, target_height = target
    if target_y < 0 or target_y + target_height > canvas_height:
        raise ValueError(f"target area {target_width}x{target_height}+{target_y} exceeds canvas {canvas_width}x{canvas_height}")

    def render_char(char: str) -> bytes:
        cell_size = target if target != canvas else None
        glyph_pixels = render_mono_pixels(face, char, px_size=font_size, cell_size=cell_size)
        if target == canvas:
            canvas_pixels = blit_center_pixels(glyph_pixels, width=canvas_width, height=canvas_height)
        else:
            target_pixels = blit_center_pixels(glyph_pixels, width=target_width, height=target_height)
            canvas_pixels = [[0] * canvas_width for _ in range(canvas_height)]
            for y, row in enumerate(target_pixels):
                canvas_pixels[target_y + y][:target_width] = row
        return pack_4bpp_pixels(canvas_pixels, width=canvas_width, height=canvas_height)

    output = {code: render_char(char) for code, char in chars.items()}
    return output, render_char("□")


def apply_font_replacements(
    rom: bytes,
    *,
    font_1x1: Path | None,
    font_1x2: Path | None,
    code_table: Path,
) -> tuple[bytes, list[str]]:
    if not font_1x1 and not font_1x2:
        return rom, []

    files = parse_nitrofs_files(rom)
    code_entries = load_code_table(code_table)
    patched = bytearray(rom)
    changes: list[str] = []

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
        mode_entries = [entry for entry in code_entries if mode in entry.modes]
        table_codes = [entry.code for entry in mode_entries]
        map_codes = [entry[0] for entry in map_entries]
        if table_codes != map_codes:
            mismatch_at = next(
                (index for index, (left, right) in enumerate(zip(table_codes, map_codes)) if left != right),
                min(len(table_codes), len(map_codes)),
            )
            table_code = table_codes[mismatch_at] if mismatch_at < len(table_codes) else None
            map_code = map_codes[mismatch_at] if mismatch_at < len(map_codes) else None
            raise ValueError(
                f"{mode} code table does not match embedded font map at index {mismatch_at}: "
                f"table={table_code!r}, map={map_code!r}"
            )

        code_to_char = {entry.code: entry.char for entry in mode_entries}
        glyphs, fallback = render_font_glyphs(
            font_path,
            code_to_char,
            canvas=spec["canvas"],  # type: ignore[arg-type]
            font_size=int(spec["font_size"]),
            target=spec["target"],  # type: ignore[arg-type]
            target_y=int(spec["target_y"]),
        )
        new_map, new_chunk, source_pages = build_font_pack(
            mode_entries,
            glyphs,
            fallback,
            mode=mode,
            spec=spec,
        )
        if new_map != map_data:
            raise ValueError(f"regenerated {map_path} does not match embedded ROM map")
        parse_chunk_header(new_chunk, expected_magic=spec["chunk_magic"])  # type: ignore[arg-type]
        if len(new_map) != len(map_data):
            raise ValueError(f"font replacement changed {map_path} size")
        if len(new_chunk) != len(chunk_data):
            raise ValueError(f"font replacement changed {chunk_path} size")
        patched[map_start:map_end] = new_map
        patched[chunk_start:chunk_end] = new_chunk
        changes.append(f"{mode}={display_path(font_path)} -> {map_path},{chunk_path} source_pages={source_pages}")

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
    rom, font_changes = apply_font_replacements(
        rom,
        font_1x1=font_1x1,
        font_1x2=font_1x2,
        code_table=repo_path(args.code_table),
    )
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
    build.add_argument(
        "--code-table",
        default=DEFAULT_CODE_TABLE.as_posix(),
        help="Fixed Chinese char-code table used when rebuilding custom font map/chunk files.",
    )
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
