from __future__ import annotations

import argparse
from pathlib import Path

from patch_vram_font_formal_format_probe import build_chunk, build_map
import patch_vram_font_chunk_table_miss_consumer_probe as consumer
import patch_vram_font_chunk_table_slim_moved_probe as slim
import patch_vram_font_split_map_probe as split


PAGE_1X2_SIZE = 0xE0
PACK_HEADER_SIZE = 0x20
RESIDENT_PAGE_OFFSET = PACK_HEADER_SIZE
SOURCE_PAGE0_OFFSET = RESIDENT_PAGE_OFFSET + PAGE_1X2_SIZE


def glyph(size: int, a: int, b: int) -> bytes:
    return bytes([a, b]) * (size // 2)


def build_1x2_page(*, fallback: bytes, shared: bytes | None = None, extra: bytes | None = None) -> bytes:
    page = bytearray(PAGE_1X2_SIZE)
    page[:4] = b"CHPG"
    page[4:8] = PAGE_1X2_SIZE.to_bytes(4, "little")
    page[8:12] = (0x40).to_bytes(4, "little")
    page[0x20 : 0x20 + 0x40] = fallback
    if shared is not None:
        page[0x60 : 0x60 + 0x40] = shared
    if extra is not None:
        page[0xA0 : 0xA0 + 0x40] = extra
    return bytes(page)


def build_1x2_pack(page0: bytes, page1: bytes) -> bytes:
    header = bytearray(PACK_HEADER_SIZE)
    header[:4] = b"CHPK"
    header[4:8] = PACK_HEADER_SIZE.to_bytes(4, "little")
    header[8:12] = PAGE_1X2_SIZE.to_bytes(4, "little")
    header[12:16] = (2).to_bytes(4, "little")
    return bytes(header) + page1 + page0 + page1


def write_resident_copy_files(
    work: Path,
    *,
    shared_char: int,
    char_1x1_extra: int,
    char_1x2_a: int,
    char_1x2_b: int,
) -> dict[str, Path]:
    paths = {name: work / rel for name, (_, rel) in split.NITROFS_FILES.items()}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    paths["1x1_map"].write_bytes(
        build_map(
            0x20,
            [
                (shared_char, 0x40, 0, 0, 0),
                (char_1x1_extra, 0x60, 0, 0, 0),
            ],
        )
    )
    paths["1x1_chunk"].write_bytes(
        build_chunk(
            0x20,
            [
                glyph(0x20, 0x6A, 0xA6),
                glyph(0x20, 0x15, 0x51),
                glyph(0x20, 0x26, 0x62),
            ],
        )
    )
    paths["1x2_map"].write_bytes(
        build_map(
            0x40,
            [
                (shared_char, 0x60, 0, 0, 0),
                (char_1x2_a, 0xA0, 0, 0, 1),
                (char_1x2_b, 0xA0, 0, 0, 0),
            ],
        )
    )

    page0 = build_1x2_page(
        fallback=glyph(0x40, 0x6B, 0xB6),
        shared=glyph(0x40, 0x37, 0x73),
        extra=glyph(0x40, 0x5A, 0xA5),
    )
    page1 = build_1x2_page(
        fallback=glyph(0x40, 0x7C, 0xC7),
        extra=glyph(0x40, 0x59, 0x95),
    )
    paths["1x2_chunk"].write_bytes(build_1x2_pack(page0, page1))
    return paths


def build_copy_hook() -> bytes:
    b = split.ArmBuilder(split.COPY_HOOK_ADDR)
    b.emit(0xE92D50FC)  # push {r2, r3, r4, r5, r6, r7, r12, lr}
    b.ldr_label(4, "vars_base_lit")
    b.emit(0xE5943020)  # ldr r3, [r4, #0x20] ; current_char
    b.emit(0xE3A0C000)  # mov r12, #0
    b.emit(0xE584C024)  # str r12, [r4, #0x24] ; clear miss_flag
    b.emit(0xE3520020)  # cmp r2, #0x20
    b.b("use_1x1", 0x0A000000)
    b.emit(0xE3520040)  # cmp r2, #0x40
    b.b("use_1x2", 0x0A000000)
    b.b("done")

    b.label("use_1x1")
    b.emit(0xE5947034)  # ldr r7, [r4, #0x34] ; resident 1x1 chunk id
    b.emit(0xE5945008)  # ldr r5, [r4, #8] ; 1x1 chunk ptr
    b.emit(0xE5944000)  # ldr r4, [r4] ; 1x1 map ptr
    b.b("lookup")

    b.label("use_1x2")
    b.emit(0xE5947038)  # ldr r7, [r4, #0x38] ; resident 1x2 chunk id
    b.emit(0xE5945018)  # ldr r5, [r4, #0x18] ; 1x2 chunk pack ptr
    b.emit(0xE3550000)  # cmp r5, #0
    b.b("done", 0x0A000000)
    b.emit(0xE2855020)  # add r5, r5, #0x20 ; resident page
    b.emit(0xE5944010)  # ldr r4, [r4, #0x10] ; 1x2 map ptr
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
    b.b("next", 0x1A000000)
    b.emit(0xE594C00C)  # ldr r12, [r4, #0x0C] ; chunk_id/reserved
    b.emit(0xE15C0007)  # cmp r12, r7
    b.ldr_label(6, "vars_base_lit")
    b.emit(0x05940004)  # ldreq r0, [r4, #4] ; resident glyph offset
    b.emit(0x00800005)  # addeq r0, r0, r5
    b.emit(0x13A00020)  # movne r0, #0x20 ; fallback glyph offset
    b.emit(0x10800005)  # addne r0, r0, r5
    b.emit(0x1586C02C)  # strne r12, [r6, #0x2C] ; miss_chunk_id
    b.emit(0x15863028)  # strne r3, [r6, #0x28] ; miss_char
    b.emit(0x15862030)  # strne r2, [r6, #0x30] ; miss_mode
    b.emit(0x13A0C001)  # movne r12, #1
    b.emit(0x1586C024)  # strne r12, [r6, #0x24] ; miss_flag
    b.b("done")

    b.label("next")
    b.emit(0xE2844010)  # add r4, r4, #0x10
    b.emit(0xE2566001)  # subs r6, r6, #1
    b.b("loop", 0x1A000000)

    b.label("done")
    b.emit(0xE8BD50FC)  # pop {r2, r3, r4, r5, r6, r7, r12, lr}
    b.b_abs(split.ORIGINAL_COPY_ADDR)

    b.literal("vars_base_lit", split.CHS_1X1_MAP_PTR_ADDR)
    return b.finalize()


def build_consume_hook() -> bytes:
    b = split.ArmBuilder(consumer.CONSUME_HOOK_ADDR)
    b.emit(consumer.ORIGINAL_DRAW_ENTRY_WORD)
    b.emit(0xE92D100F)  # push {r0, r1, r2, r3, r12}
    b.ldr_label(2, "vars_base_lit")
    b.emit(0xE5923024)  # ldr r3, [r2, #0x24] ; miss_flag
    b.emit(0xE3530000)  # cmp r3, #0
    b.b("restore", 0x0A000000)
    b.emit(0xE5923030)  # ldr r3, [r2, #0x30] ; miss_mode
    b.emit(0xE3530020)  # cmp r3, #0x20
    b.b("set_1x1", 0x0A000000)
    b.emit(0xE3530040)  # cmp r3, #0x40
    b.b("load_1x2", 0x0A000000)
    b.b("clear")

    b.label("set_1x1")
    b.emit(0xE592302C)  # ldr r3, [r2, #0x2C] ; miss_chunk_id
    b.emit(0xE5823034)  # str r3, [r2, #0x34] ; resident_1x1_chunk_id
    b.b("clear")

    b.label("load_1x2")
    b.emit(0xE5920018)  # ldr r0, [r2, #0x18] ; 1x2 chunk pack ptr
    b.emit(0xE3500000)  # cmp r0, #0
    b.b("clear", 0x0A000000)
    b.emit(0xE2800020)  # add r0, r0, #0x20 ; resident page destination
    b.emit(0xE1A01000)  # mov r1, r0
    b.emit(0xE28110E0)  # add r1, r1, #0xE0 ; source page 0
    b.emit(0xE592302C)  # ldr r3, [r2, #0x2C] ; miss_chunk_id
    b.emit(0xE3530000)  # cmp r3, #0
    b.emit(0x128110E0)  # addne r1, r1, #0xE0 ; source page 1
    b.emit(0xE3A030E0)  # mov r3, #0xE0

    b.label("copy_loop")
    b.emit(0xE491C004)  # ldr r12, [r1], #4
    b.emit(0xE480C004)  # str r12, [r0], #4
    b.emit(0xE2533004)  # subs r3, r3, #4
    b.b("copy_loop", 0x1A000000)
    b.emit(0xE592302C)  # ldr r3, [r2, #0x2C] ; miss_chunk_id
    b.emit(0xE5823038)  # str r3, [r2, #0x38] ; resident_1x2_chunk_id

    b.label("clear")
    b.emit(0xE3A03000)  # mov r3, #0
    b.emit(0xE5823024)  # str r3, [r2, #0x24] ; clear miss_flag

    b.label("restore")
    b.emit(0xE8BD100F)  # pop {r0, r1, r2, r3, r12}
    b.b_abs(consumer.DRAW_ENTRY_PATCH_ADDR + 4)
    b.literal("vars_base_lit", split.CHS_1X1_MAP_PTR_ADDR)
    return b.finalize()


def build_payload() -> bytes:
    payload = bytearray(split.PATCH_SIZE)
    save = split.build_save_char_hook()
    copy = build_copy_hook()
    load = slim.build_load_hook()

    copy_off = split.COPY_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    load_off = slim.MOVED_LOAD_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    path_off = split.PATH_1X1_MAP_ADDR - split.SAVE_CHAR_HOOK_ADDR
    vars_off = split.CHS_1X1_MAP_PTR_ADDR - split.SAVE_CHAR_HOOK_ADDR

    if copy_off < len(save):
        raise ValueError("copy hook overlaps save hook")
    if copy_off + len(copy) > load_off:
        raise ValueError("copy hook overlaps moved load hook")
    if load_off + len(load) > path_off:
        raise ValueError("moved load hook overlaps path strings")
    if consumer.VARS_END_ADDR > split.SAVE_CHAR_HOOK_ADDR + split.PATCH_SIZE:
        raise ValueError("resident vars exceed payload")

    payload[: len(save)] = save
    payload[copy_off : copy_off + len(copy)] = copy
    payload[load_off : load_off + len(load)] = load

    strings = [
        (split.PATH_1X1_MAP_ADDR, split.NITROFS_FILES["1x1_map"][0]),
        (split.PATH_1X1_CHUNK_ADDR, split.NITROFS_FILES["1x1_chunk"][0]),
        (split.PATH_1X2_MAP_ADDR, split.NITROFS_FILES["1x2_map"][0]),
        (split.PATH_1X2_CHUNK_ADDR, split.NITROFS_FILES["1x2_chunk"][0]),
    ]
    for addr, text in strings:
        encoded = text.encode("ascii") + b"\x00"
        off = addr - split.SAVE_CHAR_HOOK_ADDR
        payload[off : off + len(encoded)] = encoded

    payload[vars_off : consumer.VARS_END_ADDR - split.SAVE_CHAR_HOOK_ADDR] = bytes(
        consumer.VARS_END_ADDR - split.CHS_1X1_MAP_PTR_ADDR
    )
    payload[
        consumer.RESIDENT_1X1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : consumer.RESIDENT_1X1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4
    ] = split.word(0)
    payload[
        consumer.RESIDENT_1X2_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : consumer.RESIDENT_1X2_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4
    ] = split.word(1)
    return bytes(payload)


def patch_arm9(arm9_path: Path) -> None:
    data = bytearray(arm9_path.read_bytes())

    payload_off = split.SAVE_CHAR_HOOK_ADDR - split.ARM9_BASE
    old_payload = data[payload_off : payload_off + split.PATCH_SIZE]
    if len(old_payload) != split.PATCH_SIZE or any(old_payload):
        raise ValueError(f"ARM9 hook cave is not empty at 0x{split.SAVE_CHAR_HOOK_ADDR:08X}")
    data[payload_off : payload_off + split.PATCH_SIZE] = build_payload()

    consume = build_consume_hook()
    consume_off = consumer.CONSUME_HOOK_ADDR - split.ARM9_BASE
    old_consume = data[consume_off : consume_off + len(consume)]
    if len(old_consume) != len(consume) or any(old_consume):
        raise ValueError(f"ARM9 consume hook cave is not empty at 0x{consumer.CONSUME_HOOK_ADDR:08X}")
    data[consume_off : consume_off + len(consume)] = consume

    arm9_path.write_bytes(data)


def patch_overlay(overlay_path: Path) -> None:
    slim.patch_overlay(overlay_path)
    data = bytearray(overlay_path.read_bytes())
    off = consumer.DRAW_ENTRY_PATCH_ADDR - split.OVERLAY0_BASE
    current = int.from_bytes(data[off : off + 4], "little")
    if current != consumer.ORIGINAL_DRAW_ENTRY_WORD:
        raise ValueError(f"unexpected word at 0x{consumer.DRAW_ENTRY_PATCH_ADDR:08X}: 0x{current:08X}")
    data[off : off + 4] = split.word(
        split.arm_branch(consumer.DRAW_ENTRY_PATCH_ADDR, consumer.CONSUME_HOOK_ADDR, link=False)
    )
    overlay_path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a resident-buffer copy probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_chunk_table_resident_copy_probe")
    parser.add_argument("--output", default="rom/test_vram_font_chunk_table_resident_copy_probe.nds")
    parser.add_argument("--shared-char", default=hex(split.DEFAULT_SHARED_CHAR))
    parser.add_argument("--char-1x1-extra", default=hex(split.DEFAULT_1X1_EXTRA_CHAR))
    parser.add_argument("--char-1x2-a", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_A))
    parser.add_argument("--char-1x2-b", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_B))
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    work = repo / args.work
    output_rom = repo / args.output

    split.copy_unpacked(repo / "rom" / "unpacked" / "origin", work)
    files = write_resident_copy_files(
        work,
        shared_char=int(args.shared_char, 0),
        char_1x1_extra=int(args.char_1x1_extra, 0),
        char_1x2_a=int(args.char_1x2_a, 0),
        char_1x2_b=int(args.char_1x2_b, 0),
    )
    patch_arm9(work / "arm9.bin")
    patch_overlay(work / "overlay" / "overlay_0000.bin")
    split.repack(repo, work, output_rom)

    print(f"output={output_rom}")
    print(f"copy_hook=0x{split.COPY_HOOK_ADDR:08X} size=0x{len(build_copy_hook()):X}")
    print(f"copy_budget=0x{slim.MOVED_LOAD_HOOK_ADDR - split.COPY_HOOK_ADDR:X}")
    print(f"consume_hook=0x{consumer.CONSUME_HOOK_ADDR:08X} size=0x{len(build_consume_hook()):X}")
    print(f"resident_1x2_page_offset=0x{RESIDENT_PAGE_OFFSET:X} size=0x{PAGE_1X2_SIZE:X}")
    print(f"source_1x2_page0_offset=0x{SOURCE_PAGE0_OFFSET:X}")
    print(f"load_hook=0x{slim.MOVED_LOAD_HOOK_ADDR:08X} size=0x{len(slim.build_load_hook()):X}")
    print(f"miss_flag=0x{consumer.miss.MISS_FLAG_ADDR:08X}")
    print(f"resident_1x1_chunk_id=0x{consumer.RESIDENT_1X1_ID_ADDR:08X}")
    print(f"resident_1x2_chunk_id=0x{consumer.RESIDENT_1X2_ID_ADDR:08X}")
    for name, path in files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")


if __name__ == "__main__":
    main()
