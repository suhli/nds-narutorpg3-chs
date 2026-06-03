from __future__ import annotations

import argparse
import struct
from pathlib import Path

from patch_vram_font_split_map_probe import (
    ARM9_BASE,
    CHS_1X1_CHUNK_PTR_ADDR,
    CHS_1X1_MAP_PTR_ADDR,
    CHS_1X2_CHUNK_PTR_ADDR,
    CHS_1X2_MAP_PTR_ADDR,
    COPY_HOOK_ADDR,
    CURRENT_CHAR_ADDR,
    DEFAULT_1X1_EXTRA_CHAR,
    DEFAULT_1X2_EXTRA_CHAR_A,
    DEFAULT_1X2_EXTRA_CHAR_B,
    DEFAULT_SHARED_CHAR,
    LOAD_HOOK_ADDR,
    NITROFS_FILES,
    ORIGINAL_COPY_ADDR,
    PATCH_SIZE,
    SAVE_CHAR_HOOK_ADDR,
    ArmBuilder,
    build_load_hook,
    build_save_char_hook,
    copy_unpacked,
    patch_overlay,
    repeated_glyph,
    repack,
    word,
)


MAP_MAGIC = b"CHMP"
CHUNK_MAGIC = b"CHCK"
VERSION = 1
HEADER_SIZE = 0x20
ENTRY_SIZE = 0x10
COMPRESSION_NONE = 0


def build_copy_hook() -> bytes:
    b = ArmBuilder(COPY_HOOK_ADDR)
    b.emit(0xE92D507C)  # push {r2, r3, r4, r5, r6, r12, lr}
    b.ldr_label(3, "current_char_lit")
    b.emit(0xE5933000)  # ldr r3, [r3]
    b.emit(0xE3520020)  # cmp r2, #0x20
    b.b("use_1x1", 0x0A000000)
    b.emit(0xE3520040)  # cmp r2, #0x40
    b.b("use_1x2", 0x0A000000)
    b.b("done")

    b.label("use_1x1")
    b.ldr_label(4, "map_1x1_ptr_lit")
    b.emit(0xE5944000)  # ldr r4, [r4]
    b.ldr_label(5, "chunk_1x1_ptr_lit")
    b.emit(0xE5955000)  # ldr r5, [r5]
    b.b("lookup")

    b.label("use_1x2")
    b.ldr_label(4, "map_1x2_ptr_lit")
    b.emit(0xE5944000)  # ldr r4, [r4]
    b.ldr_label(5, "chunk_1x2_ptr_lit")
    b.emit(0xE5955000)  # ldr r5, [r5]
    b.b("lookup")

    b.label("lookup")
    b.emit(0xE3540000)  # cmp r4, #0
    b.b("done", 0x0A000000)
    b.emit(0xE3550000)  # cmp r5, #0
    b.b("done", 0x0A000000)
    b.emit(0xE594600C)  # ldr r6, [r4, #0x0C] ; entry_count
    b.emit(0xE2844020)  # add r4, r4, #0x20 ; entries begin after header
    b.emit(0xE3560000)  # cmp r6, #0
    b.b("done", 0x0A000000)

    b.label("loop")
    b.emit(0xE594C000)  # ldr r12, [r4] ; char_code
    b.emit(0xE153000C)  # cmp r3, r12
    b.emit(0x05940004)  # ldreq r0, [r4, #4] ; glyph_offset from chunk file start
    b.emit(0x00800005)  # addeq r0, r0, r5
    b.b("done", 0x0A000000)
    b.emit(0xE2844010)  # add r4, r4, #0x10
    b.emit(0xE2566001)  # subs r6, r6, #1
    b.b("loop", 0x1A000000)

    b.label("done")
    b.emit(0xE8BD507C)  # pop {r2, r3, r4, r5, r6, r12, lr}
    b.b_abs(ORIGINAL_COPY_ADDR)

    b.literal("current_char_lit", CURRENT_CHAR_ADDR)
    b.literal("map_1x1_ptr_lit", CHS_1X1_MAP_PTR_ADDR)
    b.literal("chunk_1x1_ptr_lit", CHS_1X1_CHUNK_PTR_ADDR)
    b.literal("map_1x2_ptr_lit", CHS_1X2_MAP_PTR_ADDR)
    b.literal("chunk_1x2_ptr_lit", CHS_1X2_CHUNK_PTR_ADDR)
    return b.finalize()


def build_payload() -> bytes:
    payload = bytearray(PATCH_SIZE)
    save = build_save_char_hook()
    copy = build_copy_hook()
    load = build_load_hook()
    copy_off = COPY_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR
    load_off = LOAD_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR

    payload[: len(save)] = save
    payload[copy_off : copy_off + len(copy)] = copy
    payload[load_off : load_off + len(load)] = load

    from patch_vram_font_split_map_probe import PATH_1X1_CHUNK_ADDR, PATH_1X1_MAP_ADDR, PATH_1X2_CHUNK_ADDR, PATH_1X2_MAP_ADDR

    strings = [
        (PATH_1X1_MAP_ADDR, NITROFS_FILES["1x1_map"][0]),
        (PATH_1X1_CHUNK_ADDR, NITROFS_FILES["1x1_chunk"][0]),
        (PATH_1X2_MAP_ADDR, NITROFS_FILES["1x2_map"][0]),
        (PATH_1X2_CHUNK_ADDR, NITROFS_FILES["1x2_chunk"][0]),
    ]
    for addr, text in strings:
        encoded = text.encode("ascii") + b"\x00"
        off = addr - SAVE_CHAR_HOOK_ADDR
        payload[off : off + len(encoded)] = encoded

    from patch_vram_font_split_map_probe import CHS_1X1_MAP_PTR_ADDR as VARS_START

    vars_off = VARS_START - SAVE_CHAR_HOOK_ADDR
    payload[vars_off : CURRENT_CHAR_ADDR - SAVE_CHAR_HOOK_ADDR + 4] = bytes(
        CURRENT_CHAR_ADDR - VARS_START + 4
    )
    return bytes(payload)


def patch_arm9(arm9_path: Path) -> None:
    data = bytearray(arm9_path.read_bytes())
    off = SAVE_CHAR_HOOK_ADDR - ARM9_BASE
    old = data[off : off + PATCH_SIZE]
    if len(old) != PATCH_SIZE or any(old):
        raise ValueError(f"ARM9 hook cave is not empty at 0x{SAVE_CHAR_HOOK_ADDR:08X}")
    data[off : off + PATCH_SIZE] = build_payload()
    arm9_path.write_bytes(data)


def pack_u16(value: int) -> bytes:
    return struct.pack("<H", value)


def build_map(glyph_size: int, entries: list[tuple[int, int, int, int, int]]) -> bytes:
    data = bytearray()
    data += MAP_MAGIC
    data += pack_u16(VERSION)
    data += pack_u16(HEADER_SIZE)
    data += pack_u16(glyph_size)
    data += pack_u16(ENTRY_SIZE)
    data += word(len(entries))
    data += word(0)  # flags
    data += word(0)  # default chunk id
    data += word(0)
    data += word(0)
    for char_code, glyph_offset, advance, flags, chunk_id in entries:
        data += word(char_code)
        data += word(glyph_offset)
        data += pack_u16(advance)
        data += pack_u16(flags)
        data += pack_u16(chunk_id)
        data += pack_u16(0)
    return bytes(data)


def build_chunk(glyph_size: int, glyphs: list[bytes]) -> bytes:
    body = b"".join(glyphs)
    data = bytearray()
    data += CHUNK_MAGIC
    data += pack_u16(VERSION)
    data += pack_u16(HEADER_SIZE)
    data += pack_u16(glyph_size)
    data += pack_u16(COMPRESSION_NONE)
    data += word(len(glyphs))
    data += word(len(body))
    data += word(0)  # flags
    data += word(0)
    data += word(0)
    data += body
    return bytes(data)


def write_formal_files(
    work: Path,
    *,
    shared_char: int,
    char_1x1_extra: int,
    char_1x2_a: int,
    char_1x2_b: int,
) -> dict[str, Path]:
    paths = {name: work / rel for name, (_, rel) in NITROFS_FILES.items()}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    paths["1x1_map"].write_bytes(
        build_map(
            0x20,
            [
                (shared_char, 0x20, 0, 0, 0),
                (char_1x1_extra, 0x40, 0, 0, 0),
            ],
        )
    )
    paths["1x1_chunk"].write_bytes(
        build_chunk(
            0x20,
            [
                repeated_glyph(0x20, 0x15, 0x51),
                repeated_glyph(0x20, 0x26, 0x62),
            ],
        )
    )
    paths["1x2_map"].write_bytes(
        build_map(
            0x40,
            [
                (shared_char, 0x20, 0, 0, 0),
                (char_1x2_a, 0x60, 0, 0, 0),
                (char_1x2_b, 0xA0, 0, 0, 0),
            ],
        )
    )
    paths["1x2_chunk"].write_bytes(
        build_chunk(
            0x40,
            [
                repeated_glyph(0x40, 0x37, 0x73),
                repeated_glyph(0x40, 0x48, 0x84),
                repeated_glyph(0x40, 0x59, 0x95),
            ],
        )
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a formal v0 split-map font hook probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_formal_format_probe")
    parser.add_argument("--output", default="rom/test_vram_font_formal_format_probe.nds")
    parser.add_argument("--shared-char", default=hex(DEFAULT_SHARED_CHAR))
    parser.add_argument("--char-1x1-extra", default=hex(DEFAULT_1X1_EXTRA_CHAR))
    parser.add_argument("--char-1x2-a", default=hex(DEFAULT_1X2_EXTRA_CHAR_A))
    parser.add_argument("--char-1x2-b", default=hex(DEFAULT_1X2_EXTRA_CHAR_B))
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    work = repo / args.work
    output_rom = repo / args.output
    shared_char = int(args.shared_char, 0)
    char_1x1_extra = int(args.char_1x1_extra, 0)
    char_1x2_a = int(args.char_1x2_a, 0)
    char_1x2_b = int(args.char_1x2_b, 0)

    copy_unpacked(repo / "rom" / "unpacked" / "origin", work)
    formal_files = write_formal_files(
        work,
        shared_char=shared_char,
        char_1x1_extra=char_1x1_extra,
        char_1x2_a=char_1x2_a,
        char_1x2_b=char_1x2_b,
    )
    patch_overlay(work / "overlay" / "overlay_0000.bin")
    patch_arm9(work / "arm9.bin")
    repack(repo, work, output_rom)

    print(f"work={work}")
    print(f"output={output_rom}")
    for name, path in formal_files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")
    print(f"map_magic={MAP_MAGIC.decode('ascii')} chunk_magic={CHUNK_MAGIC.decode('ascii')}")
    print(f"header_size=0x{HEADER_SIZE:X} entry_size=0x{ENTRY_SIZE:X}")
    print(f"current_char=0x{CURRENT_CHAR_ADDR:08X}")
    print(f"shared_char=0x{shared_char:04X} offset=0x20 in both chunks")
    print(f"char_1x1_extra=0x{char_1x1_extra:04X} offset=0x40")
    print(f"char_1x2_a=0x{char_1x2_a:04X} offset=0x60")
    print(f"char_1x2_b=0x{char_1x2_b:04X} offset=0xA0")


if __name__ == "__main__":
    main()
