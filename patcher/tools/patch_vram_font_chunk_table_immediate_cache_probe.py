from __future__ import annotations

from pathlib import Path

from patch_vram_font_chunk_table_dual_mode_1x1_copy_probe import (
    CONSUME_BODY_ADDR,
    CONSUME_BODY_BUDGET,
    DUAL_CONSUME_HOOK_ADDR,
    EXT_COPY_HOOK_ADDR,
    EXT_PATCH_SIZE,
    build_consume_body,
    build_consume_trampoline,
)
from patch_vram_font_chunk_table_dual_slot_probe import (
    INVALID_CHUNK_ID,
    RESIDENT_1X2_NEXT_SLOT_ADDR,
    RESIDENT_1X2_SLOT0_ID_ADDR,
    RESIDENT_1X2_SLOT1_ID_ADDR,
)
import patch_vram_font_chunk_table_miss_consumer_probe as consumer
import patch_vram_font_chunk_table_slim_moved_probe as slim
import patch_vram_font_split_map_probe as split


def build_copy_hook() -> bytes:
    b = split.ArmBuilder(EXT_COPY_HOOK_ADDR)
    b.emit(0xE92D51FE)  # push {r1, r2, r3, r4, r5, r6, r7, r8, r12, lr}
    b.ldr_label(6, "vars_base_lit")
    b.emit(0xE5963020)  # ldr r3, [r6, #0x20] ; current_char
    b.emit(0xE3A0C000)  # mov r12, #0
    b.emit(0xE586C024)  # str r12, [r6, #0x24] ; clear miss_flag
    b.emit(0xE3520040)  # cmp r2, #0x40
    b.b("done", 0x1A000000)
    b.emit(0xE5967038)  # ldr r7, [r6, #0x38] ; 1x2 slot0 chunk id
    b.emit(0xE596103C)  # ldr r1, [r6, #0x3C] ; 1x2 slot1 chunk id
    b.emit(0xE5965018)  # ldr r5, [r6, #0x18] ; 1x2 chunk pack ptr
    b.emit(0xE3550000)  # cmp r5, #0
    b.b("done", 0x0A000000)
    b.emit(0xE2855020)  # add r5, r5, #0x20 ; slot0 resident page
    b.emit(0xE5964010)  # ldr r4, [r6, #0x10] ; 1x2 map ptr

    b.label("lookup")
    b.emit(0xE3540000)  # cmp r4, #0
    b.b("done", 0x0A000000)
    b.emit(0xE594800C)  # ldr r8, [r4, #0x0C] ; entry_count
    b.emit(0xE2844020)  # add r4, r4, #0x20 ; entries begin after header

    b.label("loop")
    b.emit(0xE594C000)  # ldr r12, [r4] ; char_code
    b.emit(0xE153000C)  # cmp r3, r12
    b.b("next", 0x1A000000)
    b.emit(0xE594C00C)  # ldr r12, [r4, #0x0C] ; chunk_id
    b.emit(0xE15C0007)  # cmp r12, r7
    b.b("hit_slot0", 0x0A000000)
    b.emit(0xE15C0001)  # cmp r12, r1
    b.b("hit_slot1", 0x0A000000)
    b.emit(0xE1A0800C)  # mov r8, r12 ; missing chunk id
    b.b("miss_1x2")

    b.label("hit_slot0")
    b.emit(0xE5940004)  # ldr r0, [r4, #4] ; resident glyph offset
    b.emit(0xE0800005)  # add r0, r0, r5
    b.b("done")

    b.label("hit_slot1")
    b.emit(0xE5940004)  # ldr r0, [r4, #4] ; resident glyph offset
    b.emit(0xE0800005)  # add r0, r0, r5
    b.emit(0xE28000E0)  # add r0, r0, #0xE0 ; 1x2 slot1 page
    b.b("done")

    b.label("miss_1x2")
    b.emit(0xE596C040)  # ldr r12, [r6, #0x40] ; next slot
    b.emit(0xE35C0000)  # cmp r12, #0
    b.b("use_slot0", 0x0A000000)

    b.label("use_slot1")
    b.emit(0xE28570E0)  # add r7, r5, #0xE0 ; slot1 destination
    b.emit(0xE3A0C000)  # mov r12, #0
    b.emit(0xE586C040)  # str r12, [r6, #0x40] ; next slot = 0
    b.emit(0xE586803C)  # str r8, [r6, #0x3C] ; slot1 chunk id
    b.b("copy_1x2_page")

    b.label("use_slot0")
    b.emit(0xE1A07005)  # mov r7, r5 ; slot0 destination
    b.emit(0xE3A0C001)  # mov r12, #1
    b.emit(0xE586C040)  # str r12, [r6, #0x40] ; next slot = 1
    b.emit(0xE5868038)  # str r8, [r6, #0x38] ; slot0 chunk id

    b.label("copy_1x2_page")
    b.emit(0xE1A01007)  # mov r1, r7 ; destination
    b.emit(0xE28510E0)  # add r1, r5, #0xE0
    b.emit(0xE28110E0)  # add r1, r1, #0xE0 ; source page 0
    b.emit(0xE0683188)  # rsb r3, r8, r8, lsl #3 ; chunk_id * 7
    b.emit(0xE0811283)  # add r1, r1, r3, lsl #5 ; source by chunk_id * 0xE0
    b.emit(0xE1A00007)  # mov r0, r7 ; destination
    b.emit(0xE3A030E0)  # mov r3, #0xE0
    b.label("copy_1x2_loop")
    b.emit(0xE491C004)  # ldr r12, [r1], #4
    b.emit(0xE480C004)  # str r12, [r0], #4
    b.emit(0xE2533004)  # subs r3, r3, #4
    b.b("copy_1x2_loop", 0x1A000000)
    b.emit(0xE5940004)  # ldr r0, [r4, #4]
    b.emit(0xE0800007)  # add r0, r0, r7
    b.b("done")

    b.label("next")
    b.emit(0xE2844010)  # add r4, r4, #0x10
    b.emit(0xE2588001)  # subs r8, r8, #1
    b.b("loop", 0x1A000000)

    b.label("done")
    b.emit(0xE8BD51FE)  # pop {r1, r2, r3, r4, r5, r6, r7, r8, r12, lr}
    b.b_abs(split.ORIGINAL_COPY_ADDR)

    b.literal("vars_base_lit", split.CHS_1X1_MAP_PTR_ADDR)
    return b.finalize()


def build_payload() -> bytes:
    payload = bytearray(EXT_PATCH_SIZE)
    save = split.build_save_char_hook()
    trampoline = split.word(split.arm_branch(split.COPY_HOOK_ADDR, EXT_COPY_HOOK_ADDR, link=False))
    load = slim.build_load_hook()
    consume_trampoline = build_consume_trampoline()

    copy_off = split.COPY_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    load_off = slim.MOVED_LOAD_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    path_off = split.PATH_1X1_MAP_ADDR - split.SAVE_CHAR_HOOK_ADDR
    vars_off = split.CHS_1X1_MAP_PTR_ADDR - split.SAVE_CHAR_HOOK_ADDR
    consume_off = DUAL_CONSUME_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR

    payload[: len(save)] = save
    payload[copy_off : copy_off + len(trampoline)] = trampoline
    payload[load_off : load_off + len(load)] = load
    payload[consume_off : consume_off + len(consume_trampoline)] = consume_trampoline

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

    vars_end = RESIDENT_1X2_NEXT_SLOT_ADDR + 0x04
    payload[vars_off : vars_end - split.SAVE_CHAR_HOOK_ADDR] = bytes(vars_end - split.CHS_1X1_MAP_PTR_ADDR)
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

    consume = build_consume_body()
    if len(consume) > CONSUME_BODY_BUDGET:
        raise ValueError(f"consume body too large: 0x{len(consume):X} > 0x{CONSUME_BODY_BUDGET:X}")
    consume_off = CONSUME_BODY_ADDR - split.ARM9_BASE
    old_consume = data[consume_off : consume_off + len(consume)]
    if len(old_consume) != len(consume) or any(old_consume):
        raise ValueError(f"ARM9 consume body cave is not empty at 0x{CONSUME_BODY_ADDR:08X}")
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
        split.arm_branch(consumer.DRAW_ENTRY_PATCH_ADDR, DUAL_CONSUME_HOOK_ADDR, link=False)
    )
    overlay_path.write_bytes(data)
