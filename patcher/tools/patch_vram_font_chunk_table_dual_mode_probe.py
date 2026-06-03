from __future__ import annotations

import argparse
from pathlib import Path

from patch_vram_font_chunk_table_dual_slot_probe import (
    DUAL_CONSUME_HOOK_ADDR,
    EXT_COPY_HOOK_ADDR,
    EXT_PATCH_SIZE,
    INVALID_CHUNK_ID,
    RESIDENT_1X2_NEXT_SLOT_ADDR,
    RESIDENT_1X2_SLOT0_ID_ADDR,
    RESIDENT_1X2_SLOT1_ID_ADDR,
    SLOT0_OFFSET,
    SLOT1_OFFSET,
    SOURCE_PAGE0_OFFSET,
    SOURCE_PAGE1_OFFSET,
    build_1x2_dual_pack,
    build_consume_hook,
    build_copy_trampoline,
)
from patch_vram_font_chunk_table_resident_copy_probe import build_1x2_page, glyph
from patch_vram_font_formal_format_probe import build_chunk, build_map
import patch_vram_font_chunk_table_miss_consumer_probe as consumer
import patch_vram_font_chunk_table_slim_moved_probe as slim
import patch_vram_font_split_map_probe as split


DUAL_MODE_VARS_END_ADDR = RESIDENT_1X2_NEXT_SLOT_ADDR + 0x04


def write_dual_mode_files(
    work: Path,
    *,
    shared_char: int,
    char_1x1_extra: int,
    char_1x2_a: int,
    char_1x2_b: int,
    char_1x2_repeat: int,
    space_char: int,
) -> dict[str, Path]:
    paths = {name: work / rel for name, (_, rel) in split.NITROFS_FILES.items()}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    paths["1x1_map"].write_bytes(
        build_map(
            0x20,
            [
                (space_char, 0x40, 0, 0, 0),
                (char_1x1_extra, 0x60, 0, 0, 0),
                (shared_char, 0x80, 0, 0, 0),
            ],
        )
    )
    paths["1x1_chunk"].write_bytes(
        build_chunk(
            0x20,
            [
                glyph(0x20, 0x6A, 0xA6),  # fallback
                glyph(0x20, 0x14, 0x41),  # 1x1 space
                glyph(0x20, 0x26, 0x62),  # 1x1 extra
                glyph(0x20, 0x15, 0x51),  # 1x1 shared char
            ],
        )
    )
    paths["1x2_map"].write_bytes(
        build_map(
            0x40,
            [
                (space_char, 0x60, 0, 0, 1),
                (shared_char, 0x60, 0, 0, 0),
                (char_1x2_a, 0xA0, 0, 0, 1),
                (char_1x2_b, 0xA0, 0, 0, 0),
                (char_1x2_repeat, 0xA0, 0, 0, 1),
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
        shared=glyph(0x40, 0x48, 0x84),
        extra=glyph(0x40, 0x59, 0x95),
    )
    paths["1x2_chunk"].write_bytes(build_1x2_dual_pack(page0, page1))
    return paths


def build_copy_hook() -> bytes:
    b = split.ArmBuilder(EXT_COPY_HOOK_ADDR)
    b.emit(0xE92D50FE)  # push {r1, r2, r3, r4, r5, r6, r7, r12, lr}
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
    b.emit(0xE5947034)  # ldr r7, [r4, #0x34] ; 1x1 resident chunk id
    b.emit(0xE5945008)  # ldr r5, [r4, #8] ; 1x1 chunk ptr
    b.emit(0xE3E01000)  # mvn r1, #0 ; no second slot for 1x1
    b.emit(0xE5944000)  # ldr r4, [r4] ; 1x1 map ptr
    b.b("lookup")

    b.label("use_1x2")
    b.emit(0xE5947038)  # ldr r7, [r4, #0x38] ; 1x2 slot0 chunk id
    b.emit(0xE594103C)  # ldr r1, [r4, #0x3C] ; 1x2 slot1 chunk id
    b.emit(0xE5945018)  # ldr r5, [r4, #0x18] ; 1x2 chunk pack ptr
    b.emit(0xE2855020)  # add r5, r5, #0x20 ; slot0 resident page
    b.emit(0xE5944010)  # ldr r4, [r4, #0x10] ; 1x2 map ptr

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
    b.emit(0xE594C00C)  # ldr r12, [r4, #0x0C] ; chunk_id
    b.emit(0xE15C0007)  # cmp r12, r7
    b.b("hit_slot0", 0x0A000000)
    b.emit(0xE15C0001)  # cmp r12, r1
    b.b("hit_slot1", 0x0A000000)
    b.ldr_label(6, "vars_base_lit")
    b.emit(0xE3A00020)  # mov r0, #0x20 ; fallback from slot0 page/chunk
    b.emit(0xE0800005)  # add r0, r0, r5
    b.emit(0xE586C02C)  # str r12, [r6, #0x2C] ; miss_chunk_id
    b.emit(0xE5863028)  # str r3, [r6, #0x28] ; miss_char
    b.emit(0xE5862030)  # str r2, [r6, #0x30] ; miss_mode
    b.emit(0xE3A0C001)  # mov r12, #1
    b.emit(0xE586C024)  # str r12, [r6, #0x24] ; miss_flag
    b.b("done")

    b.label("hit_slot0")
    b.emit(0xE5940004)  # ldr r0, [r4, #4] ; resident glyph offset
    b.emit(0xE0800005)  # add r0, r0, r5
    b.b("done")

    b.label("hit_slot1")
    b.emit(0xE5940004)  # ldr r0, [r4, #4] ; resident glyph offset
    b.emit(0xE0800005)  # add r0, r0, r5
    b.emit(0xE28000E0)  # add r0, r0, #0xE0 ; 1x2 slot1 page
    b.b("done")

    b.label("next")
    b.emit(0xE2844010)  # add r4, r4, #0x10
    b.emit(0xE2566001)  # subs r6, r6, #1
    b.b("loop", 0x1A000000)

    b.label("done")
    b.emit(0xE8BD50FE)  # pop {r1, r2, r3, r4, r5, r6, r7, r12, lr}
    b.b_abs(split.ORIGINAL_COPY_ADDR)

    b.literal("vars_base_lit", split.CHS_1X1_MAP_PTR_ADDR)
    return b.finalize()


def build_payload() -> bytes:
    payload = bytearray(EXT_PATCH_SIZE)
    save = split.build_save_char_hook()
    trampoline = build_copy_trampoline()
    load = slim.build_load_hook()
    consume = build_consume_hook()

    copy_off = split.COPY_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    load_off = slim.MOVED_LOAD_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    path_off = split.PATH_1X1_MAP_ADDR - split.SAVE_CHAR_HOOK_ADDR
    vars_off = split.CHS_1X1_MAP_PTR_ADDR - split.SAVE_CHAR_HOOK_ADDR
    consume_off = DUAL_CONSUME_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR

    if copy_off < len(save):
        raise ValueError("copy trampoline overlaps save hook")
    if copy_off + len(trampoline) > load_off:
        raise ValueError("copy trampoline overlaps moved load hook")
    if load_off + len(load) > path_off:
        raise ValueError("moved load hook overlaps path strings")
    if DUAL_MODE_VARS_END_ADDR > DUAL_CONSUME_HOOK_ADDR:
        raise ValueError("dual-mode vars overlap consume hook")
    if consume_off + len(consume) > EXT_PATCH_SIZE:
        raise ValueError("consume hook exceeds extended payload")

    payload[: len(save)] = save
    payload[copy_off : copy_off + len(trampoline)] = trampoline
    payload[load_off : load_off + len(load)] = load
    payload[consume_off : consume_off + len(consume)] = consume

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

    payload[vars_off : DUAL_MODE_VARS_END_ADDR - split.SAVE_CHAR_HOOK_ADDR] = bytes(
        DUAL_MODE_VARS_END_ADDR - split.CHS_1X1_MAP_PTR_ADDR
    )
    payload[
        consumer.RESIDENT_1X1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : consumer.RESIDENT_1X1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4
    ] = split.word(0)
    payload[
        RESIDENT_1X2_SLOT0_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : RESIDENT_1X2_SLOT0_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4
    ] = split.word(1)
    payload[
        RESIDENT_1X2_SLOT1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : RESIDENT_1X2_SLOT1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4
    ] = split.word(INVALID_CHUNK_ID)
    payload[
        RESIDENT_1X2_NEXT_SLOT_ADDR - split.SAVE_CHAR_HOOK_ADDR : RESIDENT_1X2_NEXT_SLOT_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4
    ] = split.word(1)
    return bytes(payload)


def patch_arm9(arm9_path: Path) -> None:
    data = bytearray(arm9_path.read_bytes())

    payload_off = split.SAVE_CHAR_HOOK_ADDR - split.ARM9_BASE
    old_payload = data[payload_off : payload_off + EXT_PATCH_SIZE]
    if len(old_payload) != EXT_PATCH_SIZE or any(old_payload):
        raise ValueError(f"ARM9 extended hook cave is not empty at 0x{split.SAVE_CHAR_HOOK_ADDR:08X}")
    data[payload_off : payload_off + EXT_PATCH_SIZE] = build_payload()

    copy = build_copy_hook()
    copy_off = EXT_COPY_HOOK_ADDR - split.ARM9_BASE
    old_copy = data[copy_off : copy_off + len(copy)]
    if len(old_copy) != len(copy) or any(old_copy):
        raise ValueError(f"ARM9 copy hook cave is not empty at 0x{EXT_COPY_HOOK_ADDR:08X}")
    data[copy_off : copy_off + len(copy)] = copy
    arm9_path.write_bytes(data)


def patch_overlay(overlay_path: Path) -> None:
    slim.patch_overlay(overlay_path)
    data = bytearray(overlay_path.read_bytes())
    off = consumer.DRAW_ENTRY_PATCH_ADDR - split.OVERLAY0_BASE
    current = int.from_bytes(data[off : off + 4], "little")
    if current != consumer.ORIGINAL_DRAW_ENTRY_WORD:
        raise ValueError(f"unexpected word at 0x{consumer.DRAW_ENTRY_PATCH_ADDR:08X}: 0x{current:08X}")
    data[off : off + 4] = split.word(
        split.arm_branch(consumer.DRAW_ENTRY_PATCH_ADDR, DUAL_CONSUME_HOOK_ADDR, link=False)
    )
    overlay_path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dual-mode resident chunk-table probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_chunk_table_dual_mode_probe")
    parser.add_argument("--output", default="rom/test_vram_font_chunk_table_dual_mode_probe.nds")
    parser.add_argument("--shared-char", default=hex(split.DEFAULT_SHARED_CHAR))
    parser.add_argument("--char-1x1-extra", default=hex(split.DEFAULT_1X1_EXTRA_CHAR))
    parser.add_argument("--char-1x2-a", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_A))
    parser.add_argument("--char-1x2-b", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_B))
    parser.add_argument("--char-1x2-repeat", default="0x82C6")
    parser.add_argument("--space-char", default="0x8140")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    work = repo / args.work
    output_rom = repo / args.output

    split.copy_unpacked(repo / "rom" / "unpacked" / "origin", work)
    files = write_dual_mode_files(
        work,
        shared_char=int(args.shared_char, 0),
        char_1x1_extra=int(args.char_1x1_extra, 0),
        char_1x2_a=int(args.char_1x2_a, 0),
        char_1x2_b=int(args.char_1x2_b, 0),
        char_1x2_repeat=int(args.char_1x2_repeat, 0),
        space_char=int(args.space_char, 0),
    )
    patch_arm9(work / "arm9.bin")
    patch_overlay(work / "overlay" / "overlay_0000.bin")
    split.repack(repo, work, output_rom)

    print(f"output={output_rom}")
    print(f"copy_trampoline=0x{split.COPY_HOOK_ADDR:08X} size=0x{len(build_copy_trampoline()):X}")
    print(f"copy_hook=0x{EXT_COPY_HOOK_ADDR:08X} size=0x{len(build_copy_hook()):X}")
    print(f"consume_hook=0x{DUAL_CONSUME_HOOK_ADDR:08X} size=0x{len(build_consume_hook()):X}")
    print(f"extended_payload=0x{split.SAVE_CHAR_HOOK_ADDR:08X} size=0x{EXT_PATCH_SIZE:X}")
    print(f"1x2_slot0_offset=0x{SLOT0_OFFSET:X}")
    print(f"1x2_slot1_offset=0x{SLOT1_OFFSET:X}")
    print(f"source_1x2_page0_offset=0x{SOURCE_PAGE0_OFFSET:X}")
    print(f"source_1x2_page1_offset=0x{SOURCE_PAGE1_OFFSET:X}")
    print(f"resident_1x1_id=0x{consumer.RESIDENT_1X1_ID_ADDR:08X}")
    print(f"resident_1x2_slot0_id=0x{RESIDENT_1X2_SLOT0_ID_ADDR:08X}")
    print(f"resident_1x2_slot1_id=0x{RESIDENT_1X2_SLOT1_ID_ADDR:08X}")
    print(f"resident_1x2_next_slot=0x{RESIDENT_1X2_NEXT_SLOT_ADDR:08X}")
    for name, path in files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")


if __name__ == "__main__":
    main()
