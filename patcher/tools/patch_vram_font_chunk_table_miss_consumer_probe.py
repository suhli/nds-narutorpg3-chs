from __future__ import annotations

import argparse
from pathlib import Path

import patch_vram_font_chunk_table_miss_flag_probe as miss
import patch_vram_font_chunk_table_slim_moved_probe as slim
import patch_vram_font_split_map_probe as split


DRAW_ENTRY_PATCH_ADDR = 0x0208913C
ORIGINAL_DRAW_ENTRY_WORD = 0xE92D40F0  # push {r4, r5, r6, r7, lr}
CONSUME_HOOK_ADDR = 0x02073D64

RESIDENT_1X1_ID_ADDR = miss.MISS_MODE_ADDR + 0x04
RESIDENT_1X2_ID_ADDR = miss.MISS_MODE_ADDR + 0x08
VARS_END_ADDR = RESIDENT_1X2_ID_ADDR + 0x04


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
    b.emit(0xE5945018)  # ldr r5, [r4, #0x18] ; 1x2 chunk ptr
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
    b = split.ArmBuilder(CONSUME_HOOK_ADDR)
    b.emit(ORIGINAL_DRAW_ENTRY_WORD)
    b.ldr_label(2, "vars_base_lit")
    b.emit(0xE5923024)  # ldr r3, [r2, #0x24] ; miss_flag
    b.emit(0xE3530000)  # cmp r3, #0
    b.b("done", 0x0A000000)
    b.emit(0xE5923030)  # ldr r3, [r2, #0x30] ; miss_mode
    b.emit(0xE3530020)  # cmp r3, #0x20
    b.b("set_1x1", 0x0A000000)
    b.emit(0xE3530040)  # cmp r3, #0x40
    b.b("set_1x2", 0x0A000000)
    b.b("clear")

    b.label("set_1x1")
    b.emit(0xE592302C)  # ldr r3, [r2, #0x2C] ; miss_chunk_id
    b.emit(0xE5823034)  # str r3, [r2, #0x34] ; resident_1x1_chunk_id
    b.b("clear")

    b.label("set_1x2")
    b.emit(0xE592302C)  # ldr r3, [r2, #0x2C] ; miss_chunk_id
    b.emit(0xE5823038)  # str r3, [r2, #0x38] ; resident_1x2_chunk_id

    b.label("clear")
    b.emit(0xE3A03000)  # mov r3, #0
    b.emit(0xE5823024)  # str r3, [r2, #0x24] ; clear miss_flag

    b.label("done")
    b.b_abs(DRAW_ENTRY_PATCH_ADDR + 4)
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
    if VARS_END_ADDR > split.SAVE_CHAR_HOOK_ADDR + split.PATCH_SIZE:
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

    payload[vars_off : VARS_END_ADDR - split.SAVE_CHAR_HOOK_ADDR] = bytes(
        VARS_END_ADDR - split.CHS_1X1_MAP_PTR_ADDR
    )
    payload[RESIDENT_1X1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : RESIDENT_1X1_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4] = split.word(0)
    payload[RESIDENT_1X2_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR : RESIDENT_1X2_ID_ADDR - split.SAVE_CHAR_HOOK_ADDR + 4] = split.word(1)
    return bytes(payload)


def patch_arm9(arm9_path: Path) -> None:
    data = bytearray(arm9_path.read_bytes())

    payload_off = split.SAVE_CHAR_HOOK_ADDR - split.ARM9_BASE
    old_payload = data[payload_off : payload_off + split.PATCH_SIZE]
    if len(old_payload) != split.PATCH_SIZE or any(old_payload):
        raise ValueError(f"ARM9 hook cave is not empty at 0x{split.SAVE_CHAR_HOOK_ADDR:08X}")
    data[payload_off : payload_off + split.PATCH_SIZE] = build_payload()

    consume = build_consume_hook()
    consume_off = CONSUME_HOOK_ADDR - split.ARM9_BASE
    old_consume = data[consume_off : consume_off + len(consume)]
    if len(old_consume) != len(consume) or any(old_consume):
        raise ValueError(f"ARM9 consume hook cave is not empty at 0x{CONSUME_HOOK_ADDR:08X}")
    data[consume_off : consume_off + len(consume)] = consume

    arm9_path.write_bytes(data)


def patch_overlay(overlay_path: Path) -> None:
    slim.patch_overlay(overlay_path)
    data = bytearray(overlay_path.read_bytes())
    off = DRAW_ENTRY_PATCH_ADDR - split.OVERLAY0_BASE
    current = int.from_bytes(data[off : off + 4], "little")
    if current != ORIGINAL_DRAW_ENTRY_WORD:
        raise ValueError(f"unexpected word at 0x{DRAW_ENTRY_PATCH_ADDR:08X}: 0x{current:08X}")
    data[off : off + 4] = split.word(split.arm_branch(DRAW_ENTRY_PATCH_ADDR, CONSUME_HOOK_ADDR, link=False))
    overlay_path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a miss-consumer chunk-table probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_chunk_table_miss_consumer_probe")
    parser.add_argument("--output", default="rom/test_vram_font_chunk_table_miss_consumer_probe.nds")
    parser.add_argument("--shared-char", default=hex(split.DEFAULT_SHARED_CHAR))
    parser.add_argument("--char-1x1-extra", default=hex(split.DEFAULT_1X1_EXTRA_CHAR))
    parser.add_argument("--char-1x2-a", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_A))
    parser.add_argument("--char-1x2-b", default=hex(split.DEFAULT_1X2_EXTRA_CHAR_B))
    parser.add_argument("--shared-1x1-chunk-id", type=int, default=0)
    parser.add_argument("--char-1x1-extra-chunk-id", type=int, default=0)
    parser.add_argument("--shared-1x2-chunk-id", type=int, default=0)
    parser.add_argument("--char-1x2-a-chunk-id", type=int, default=1)
    parser.add_argument("--char-1x2-b-chunk-id", type=int, default=0)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    work = repo / args.work
    output_rom = repo / args.output

    split.copy_unpacked(repo / "rom" / "unpacked" / "origin", work)
    files = slim.write_chunk_table_files(
        work,
        shared_char=int(args.shared_char, 0),
        char_1x1_extra=int(args.char_1x1_extra, 0),
        char_1x2_a=int(args.char_1x2_a, 0),
        char_1x2_b=int(args.char_1x2_b, 0),
        shared_1x1_chunk_id=args.shared_1x1_chunk_id,
        char_1x1_extra_chunk_id=args.char_1x1_extra_chunk_id,
        shared_1x2_chunk_id=args.shared_1x2_chunk_id,
        char_1x2_a_chunk_id=args.char_1x2_a_chunk_id,
        char_1x2_b_chunk_id=args.char_1x2_b_chunk_id,
    )
    patch_arm9(work / "arm9.bin")
    patch_overlay(work / "overlay" / "overlay_0000.bin")
    split.repack(repo, work, output_rom)

    copy_size = len(build_copy_hook())
    consume_size = len(build_consume_hook())
    load_size = len(slim.build_load_hook())
    print(f"output={output_rom}")
    print(f"copy_hook=0x{split.COPY_HOOK_ADDR:08X} size=0x{copy_size:X}")
    print(f"copy_budget=0x{slim.MOVED_LOAD_HOOK_ADDR - split.COPY_HOOK_ADDR:X}")
    print(f"consume_hook=0x{CONSUME_HOOK_ADDR:08X} size=0x{consume_size:X}")
    print(f"load_hook=0x{slim.MOVED_LOAD_HOOK_ADDR:08X} size=0x{load_size:X}")
    print(f"miss_flag=0x{miss.MISS_FLAG_ADDR:08X}")
    print(f"miss_char=0x{miss.MISS_CHAR_ADDR:08X}")
    print(f"miss_chunk_id=0x{miss.MISS_CHUNK_ID_ADDR:08X}")
    print(f"miss_mode=0x{miss.MISS_MODE_ADDR:08X}")
    print(f"resident_1x1_chunk_id=0x{RESIDENT_1X1_ID_ADDR:08X}")
    print(f"resident_1x2_chunk_id=0x{RESIDENT_1X2_ID_ADDR:08X}")
    for name, path in files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")


if __name__ == "__main__":
    main()
