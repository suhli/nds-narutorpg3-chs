from __future__ import annotations

from pathlib import Path

import patch_vram_font_chunk_table_immediate_cache_probe as immediate
import patch_vram_font_chunk_table_miss_consumer_probe as consumer
import patch_vram_font_chunk_table_slim_moved_probe as slim
import patch_vram_font_split_map_probe as split


EXT_COPY_HOOK_ADDR = immediate.EXT_COPY_HOOK_ADDR
EXT_PATCH_SIZE = immediate.EXT_PATCH_SIZE
SYNC_1X1_BODY_ADDR = immediate.CONSUME_BODY_ADDR
SYNC_1X1_BODY_BUDGET = immediate.CONSUME_BODY_BUDGET


def build_copy_dispatch() -> bytes:
    b = split.ArmBuilder(split.COPY_HOOK_ADDR)
    b.emit(0xE3520020)  # cmp r2, #0x20
    b.emit(split.arm_cond_branch(b.pc, SYNC_1X1_BODY_ADDR, 0x0A000000))
    b.b_abs(EXT_COPY_HOOK_ADDR)
    return b.finalize()


def build_copy_hook() -> bytes:
    # Preserve the already runtime-validated synchronous 1x2 implementation.
    return immediate.build_copy_hook()


def build_sync_1x1_body() -> bytes:
    b = split.ArmBuilder(SYNC_1X1_BODY_ADDR)
    b.emit(0xE92D51FE)  # push {r1, r2, r3, r4, r5, r6, r7, r8, r12, lr}
    b.ldr_label(6, "vars_base_lit")
    b.emit(0xE5963020)  # ldr r3, [r6, #0x20] ; current_char
    b.emit(0xE5967034)  # ldr r7, [r6, #0x34] ; resident 1x1 chunk id
    b.emit(0xE5965008)  # ldr r5, [r6, #8] ; 1x1 chunk pack ptr
    b.emit(0xE3550000)  # cmp r5, #0
    b.b("done", 0x0A000000)
    b.emit(0xE2855020)  # add r5, r5, #0x20 ; resident 1x1 page
    b.emit(0xE5964000)  # ldr r4, [r6] ; 1x1 map ptr
    b.emit(0xE3540000)  # cmp r4, #0
    b.b("done", 0x0A000000)
    b.emit(0xE594800C)  # ldr r8, [r4, #0x0C] ; entry_count
    b.emit(0xE2844020)  # add r4, r4, #0x20 ; entries begin after header
    b.emit(0xE3580000)  # cmp r8, #0
    b.b("done", 0x0A000000)

    b.label("lookup")
    b.emit(0xE594C000)  # ldr r12, [r4] ; char_code
    b.emit(0xE153000C)  # cmp r3, r12
    b.b("next", 0x1A000000)
    b.emit(0xE594C00C)  # ldr r12, [r4, #0x0C] ; chunk_id
    b.emit(0xE15C0007)  # cmp r12, r7
    b.b("hit", 0x0A000000)

    b.emit(0xE1A0700C)  # mov r7, r12 ; missing chunk id
    b.emit(0xE2851080)  # add r1, r5, #0x80 ; source page 0
    b.emit(0xE0811387)  # add r1, r1, r7, lsl #7 ; source page by chunk id
    b.emit(0xE1A00005)  # mov r0, r5 ; resident page destination
    b.emit(0xE3A02080)  # mov r2, #0x80

    b.label("copy_page")
    b.emit(0xE491C004)  # ldr r12, [r1], #4
    b.emit(0xE480C004)  # str r12, [r0], #4
    b.emit(0xE2522004)  # subs r2, r2, #4
    b.b("copy_page", 0x1A000000)
    b.emit(0xE5867034)  # str r7, [r6, #0x34] ; resident 1x1 chunk id

    b.label("hit")
    b.emit(0xE5940004)  # ldr r0, [r4, #4] ; resident glyph offset
    b.emit(0xE0800005)  # add r0, r0, r5
    b.b("done")

    b.label("next")
    b.emit(0xE2844010)  # add r4, r4, #0x10
    b.emit(0xE2588001)  # subs r8, r8, #1
    b.b("lookup", 0x1A000000)

    b.label("done")
    b.emit(0xE8BD51FE)  # pop {r1, r2, r3, r4, r5, r6, r7, r8, r12, lr}
    b.b_abs(split.ORIGINAL_COPY_ADDR)
    b.literal("vars_base_lit", split.CHS_1X1_MAP_PTR_ADDR)
    return b.finalize()


def build_payload() -> bytes:
    payload = bytearray(immediate.build_payload())
    dispatch = build_copy_dispatch()
    dispatch_off = split.COPY_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR
    if dispatch_off + len(dispatch) > slim.MOVED_LOAD_HOOK_ADDR - split.SAVE_CHAR_HOOK_ADDR:
        raise ValueError("copy dispatch overlaps moved load hook")
    payload[dispatch_off : dispatch_off + len(dispatch)] = dispatch
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

    sync_1x1 = build_sync_1x1_body()
    if len(sync_1x1) > SYNC_1X1_BODY_BUDGET:
        raise ValueError(f"sync 1x1 body too large: 0x{len(sync_1x1):X} > 0x{SYNC_1X1_BODY_BUDGET:X}")
    sync_1x1_off = SYNC_1X1_BODY_ADDR - split.ARM9_BASE
    old_sync_1x1 = data[sync_1x1_off : sync_1x1_off + len(sync_1x1)]
    if len(old_sync_1x1) != len(sync_1x1) or any(old_sync_1x1):
        raise ValueError(f"ARM9 sync 1x1 cave is not empty at 0x{SYNC_1X1_BODY_ADDR:08X}")
    data[sync_1x1_off : sync_1x1_off + len(sync_1x1)] = sync_1x1

    arm9_path.write_bytes(data)


def patch_overlay(overlay_path: Path) -> None:
    # Do not patch the draw entry: both 1x1 and 1x2 misses are resolved synchronously.
    slim.patch_overlay(overlay_path)

