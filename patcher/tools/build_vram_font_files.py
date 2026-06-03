from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import freetype

from patch_vram_font_formal_format_probe import build_map
from patch_vram_font_chunk_table_dual_mode_1x1_copy_probe import (
    PAGE_1X1_SIZE,
    PACK_1X1_HEADER_SIZE,
)
from patch_vram_font_chunk_table_resident_copy_probe import PAGE_1X2_SIZE


MAP_HEADER_SIZE = 0x20
PACK_HEADER_SIZE = 0x20
INK = 3
BG = 0x11


@dataclass(frozen=True)
class FontEntry:
    code: int
    char: str
    modes: frozenset[str]


def decode_code(value: str | int) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text, 0)


def decode_char(value: str) -> str:
    text = value.strip()
    if text.startswith("\\u") and len(text) == 6:
        return chr(int(text[2:], 16))
    if text.startswith("U+") and len(text) >= 6:
        return chr(int(text[2:], 16))
    if not text:
        raise ValueError("empty character")
    return text[0]


def parse_modes(value: str | list[str] | None) -> frozenset[str]:
    if value is None:
        return frozenset({"1x1", "1x2"})
    if isinstance(value, str):
        parts = re.split(r"[,+\s]+", value.strip())
    else:
        parts = [str(item) for item in value]
    modes = {part for part in parts if part}
    invalid = modes - {"1x1", "1x2"}
    if invalid:
        raise ValueError(f"invalid modes: {sorted(invalid)}")
    if not modes:
        raise ValueError("entry must include at least one mode")
    return frozenset(modes)


def parse_manifest(path: Path) -> list[FontEntry]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_entries = payload["entries"] if isinstance(payload, dict) else payload
        entries = [
            FontEntry(
                code=decode_code(item["code"]),
                char=decode_char(item["char"]),
                modes=parse_modes(item.get("modes")),
            )
            for item in raw_entries
        ]
    else:
        entries = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            line = line.replace("=", " ").replace(",", " ")
            parts = line.split()
            if len(parts) < 2:
                raise ValueError(f"{path}:{line_no}: expected '<code> <char> [modes]'")
            modes = parse_modes(parts[2] if len(parts) > 2 else None)
            entries.append(FontEntry(decode_code(parts[0]), decode_char(parts[1]), modes))
    seen: set[tuple[int, str]] = set()
    for entry in entries:
        for mode in entry.modes:
            key = (entry.code, mode)
            if key in seen:
                raise ValueError(f"duplicate code 0x{entry.code:04X} for mode {mode}")
            seen.add(key)
    return entries


def entries_from_chars(chars: str, start_code: int) -> list[FontEntry]:
    return [
        FontEntry(code=start_code + index, char=char, modes=frozenset({"1x1", "1x2"}))
        for index, char in enumerate(chars)
    ]


def render_mono(face: freetype.Face, char: str, *, px_size: int) -> list[list[int]]:
    face.set_pixel_sizes(0, px_size)
    face.load_char(char, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bmp = face.glyph.bitmap
    pixels = [[0] * bmp.width for _ in range(bmp.rows)]
    for y in range(bmp.rows):
        row = bmp.buffer[y * bmp.pitch : (y + 1) * bmp.pitch]
        for x in range(bmp.width):
            byte = row[x >> 3]
            pixels[y][x] = (byte >> (7 - (x & 7))) & 1
    return pixels


def blit_center(src: list[list[int]], *, width: int, height: int) -> list[list[int]]:
    src_h = len(src)
    src_w = len(src[0]) if src_h else 0
    dst = [[0] * width for _ in range(height)]
    ox = (width - src_w) // 2
    oy = (height - src_h) // 2
    for y, row in enumerate(src):
        ty = oy + y
        if not 0 <= ty < height:
            continue
        for x, value in enumerate(row):
            tx = ox + x
            if 0 <= tx < width:
                dst[ty][tx] = value
    return dst


def compress_16w_to_8w(src: list[list[int]]) -> list[list[int]]:
    dst = [[0] * 8 for _ in range(16)]
    for y in range(16):
        for x in range(8):
            dst[y][x] = 1 if (src[y][x * 2] or src[y][x * 2 + 1]) else 0
    return dst


def tile8_to_4bpp(tile: list[list[int]], *, ink: int, bg: int) -> bytes:
    out = bytearray()
    ink &= 0xF
    bg &= 0xF
    for y in range(8):
        for x in range(0, 8, 2):
            p0 = ink if tile[y][x] else bg
            p1 = ink if tile[y][x + 1] else bg
            out.append((p1 << 4) | p0)
    return bytes(out)


def render_1x1(face: freetype.Face, char: str, *, ink: int, bg: int) -> bytes:
    canvas = blit_center(render_mono(face, char, px_size=8), width=8, height=8)
    return tile8_to_4bpp(canvas, ink=ink, bg=bg)


def render_1x2(face: freetype.Face, char: str, *, ink: int, bg: int) -> bytes:
    canvas16 = blit_center(render_mono(face, char, px_size=16), width=16, height=16)
    glyph = compress_16w_to_8w(canvas16)
    return tile8_to_4bpp(glyph[:8], ink=ink, bg=bg) + tile8_to_4bpp(glyph[8:], ink=ink, bg=bg)


def build_page(
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


def pack_mode(
    entries: list[FontEntry],
    *,
    mode: str,
    face: freetype.Face,
    fallback_char: str,
    ink: int,
    bg: int,
) -> tuple[bytes, bytes, int]:
    if mode == "1x1":
        glyph_size = 0x20
        page_size = PAGE_1X1_SIZE
        page_magic = b"CHG1"
        pack_magic = b"CHP1"
        resident_slots = 1
        render = render_1x1
    else:
        glyph_size = 0x40
        page_size = PAGE_1X2_SIZE
        page_magic = b"CHPG"
        pack_magic = b"CHP2"
        resident_slots = 2
        render = render_1x2

    mode_entries = [entry for entry in entries if mode in entry.modes]
    slots_per_page = (page_size - (MAP_HEADER_SIZE + glyph_size)) // glyph_size
    if slots_per_page <= 0:
        raise ValueError(f"{mode} page has no room for custom glyphs")

    source_page_count = max(2, math.ceil(len(mode_entries) / slots_per_page))
    fallback = render(face, fallback_char, ink=ink, bg=bg)
    pages: list[bytes] = []
    map_entries: list[tuple[int, int, int, int, int]] = []

    for page_index in range(source_page_count):
        start = page_index * slots_per_page
        page_entries = mode_entries[start : start + slots_per_page]
        glyphs = [render(face, entry.char, ink=ink, bg=bg) for entry in page_entries]
        pages.append(
            build_page(
                magic=page_magic,
                page_size=page_size,
                glyph_size=glyph_size,
                fallback=fallback,
                glyphs=glyphs,
            )
        )
        for slot_index, entry in enumerate(page_entries):
            glyph_offset = MAP_HEADER_SIZE + glyph_size + slot_index * glyph_size
            map_entries.append((entry.code, glyph_offset, 0, 0, page_index))

    header = bytearray(PACK_HEADER_SIZE)
    header[:4] = pack_magic
    header[4:8] = PACK_HEADER_SIZE.to_bytes(4, "little")
    header[8:12] = page_size.to_bytes(4, "little")
    header[12:16] = source_page_count.to_bytes(4, "little")
    header[16:20] = resident_slots.to_bytes(4, "little")

    if mode == "1x1":
        resident_pages = [pages[0]]
    else:
        resident_pages = [pages[1], bytes(page_size)]

    return build_map(glyph_size, map_entries), bytes(header) + b"".join(resident_pages) + b"".join(pages), source_page_count


def write_font_dir(args: argparse.Namespace) -> Path:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.manifest:
        entries = parse_manifest(Path(args.manifest))
    else:
        entries = entries_from_chars(args.chars, int(args.start_code, 0))
    if not entries:
        raise ValueError("no font entries")

    face_1x1 = freetype.Face(str(Path(args.font_1x1)))
    face_1x2 = freetype.Face(str(Path(args.font_1x2)))

    map_1x1, chunk_1x1, pages_1x1 = pack_mode(
        entries,
        mode="1x1",
        face=face_1x1,
        fallback_char=args.fallback_char,
        ink=int(args.ink, 0),
        bg=int(args.bg, 0),
    )
    map_1x2, chunk_1x2, pages_1x2 = pack_mode(
        entries,
        mode="1x2",
        face=face_1x2,
        fallback_char=args.fallback_char,
        ink=int(args.ink, 0),
        bg=int(args.bg, 0),
    )

    files = {
        "chs_1x1.map": map_1x1,
        "chs_1x1.chunk": chunk_1x1,
        "chs_1x2.map": map_1x2,
        "chs_1x2.chunk": chunk_1x2,
    }
    for name, data in files.items():
        (out_dir / name).write_bytes(data)

    summary = {
        "entry_count": len(entries),
        "entries": [
            {"code": f"0x{entry.code:04X}", "char": entry.char, "modes": sorted(entry.modes)}
            for entry in entries
        ],
        "1x1_source_pages": pages_1x1,
        "1x2_source_pages": pages_1x2,
        "files": {name: len(data) for name, data in files.items()},
    }
    (out_dir / "manifest.resolved.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"output_dir={out_dir}")
    print(f"entries={len(entries)}")
    print(f"1x1_source_pages={pages_1x1}")
    print(f"1x2_source_pages={pages_1x2}")
    for name, data in files.items():
        print(f"{name} size=0x{len(data):X}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v0 dynamic-font chs_1x1/chs_1x2 map and chunk files.")
    parser.add_argument("--manifest", default="", help="JSON or text mapping file: code char [modes]")
    parser.add_argument("--chars", default="", help="Characters to assign sequentially when --manifest is not used")
    parser.add_argument("--start-code", default="0xE000")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--font-1x1", default="assets/fusion-pixel-8px-monospaced-zh_hans.ttf")
    parser.add_argument("--font-1x2", default="assets/FashionBitmap16_0.092.ttf")
    parser.add_argument("--fallback-char", default="□")
    parser.add_argument("--ink", default=hex(INK))
    parser.add_argument("--bg", default=hex(BG))
    args = parser.parse_args()
    write_font_dir(args)


if __name__ == "__main__":
    main()
