from __future__ import annotations

import argparse
from pathlib import Path

from patch_vram_font_formal_format_probe import build_chunk, build_map
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
)


RESIDENT_1X1_CHUNK_ID = 0
RESIDENT_1X2_CHUNK_ID = 1
FALLBACK_OFFSET = 0x20


def write_chunk_table_files(
    work: Path,
    *,
    shared_char: int,
    char_1x1_extra: int,
    char_1x2_a: int,
    char_1x2_b: int,
    shared_1x1_chunk_id: int,
    char_1x1_extra_chunk_id: int,
    shared_1x2_chunk_id: int,
    char_1x2_a_chunk_id: int,
    char_1x2_b_chunk_id: int,
) -> dict[str, Path]:
    paths = {name: work / rel for name, (_, rel) in NITROFS_FILES.items()}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    paths["1x1_map"].write_bytes(
        build_map(
            0x20,
            [
                (shared_char, 0x40, 0, 0, shared_1x1_chunk_id),
                (char_1x1_extra, 0x60, 0, 0, char_1x1_extra_chunk_id),
            ],
        )
    )
    paths["1x1_chunk"].write_bytes(
        build_chunk(
            0x20,
            [
                repeated_glyph(0x20, 0x6A, 0xA6),  # fallback
                repeated_glyph(0x20, 0x15, 0x51),  # resident 0x82A2
                repeated_glyph(0x20, 0x26, 0x62),  # resident/fallback target
            ],
        )
    )
    paths["1x2_map"].write_bytes(
        build_map(
            0x40,
            [
                (shared_char, 0x60, 0, 0, shared_1x2_chunk_id),
                (char_1x2_a, 0xA0, 0, 0, char_1x2_a_chunk_id),
                (char_1x2_b, 0xA0, 0, 0, char_1x2_b_chunk_id),
            ],
        )
    )
    paths["1x2_chunk"].write_bytes(
        build_chunk(
            0x40,
            [
                repeated_glyph(0x40, 0x6B, 0xB6),  # fallback
                repeated_glyph(0x40, 0x37, 0x73),  # resident 0x82A2
                repeated_glyph(0x40, 0x59, 0x95),  # resident 0x82DF/0x82CD
            ],
        )
    )
    return paths


def build_copy_hook() -> bytes:
    b = ArmBuilder(COPY_HOOK_ADDR)
    b.emit(0xE92D50FC)  # push {r2, r3, r4, r5, r6, r7, r12, lr}
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
    b.emit(0xE3A07000)  # mov r7, #0 ; resident chunk id for 1x1
    b.b("lookup")

    b.label("use_1x2")
    b.ldr_label(4, "map_1x2_ptr_lit")
    b.emit(0xE5944000)  # ldr r4, [r4]
    b.ldr_label(5, "chunk_1x2_ptr_lit")
    b.emit(0xE5955000)  # ldr r5, [r5]
    b.emit(0xE3A07001)  # mov r7, #1 ; resident chunk id for 1x2
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
    b.emit(0x05940004)  # ldreq r0, [r4, #4] ; resident glyph offset
    b.emit(0x00800005)  # addeq r0, r0, r5
    b.emit(0x13A00020)  # movne r0, #0x20 ; fallback glyph offset
    b.emit(0x10800005)  # addne r0, r0, r5
    b.b("done")

    b.label("next")
    b.emit(0xE2844010)  # add r4, r4, #0x10
    b.emit(0xE2566001)  # subs r6, r6, #1
    b.b("loop", 0x1A000000)

    b.label("done")
    b.emit(0xE8BD50FC)  # pop {r2, r3, r4, r5, r6, r7, r12, lr}
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

    from patch_vram_font_split_map_probe import (
        CHS_1X1_MAP_PTR_ADDR as VARS_START,
        PATH_1X1_CHUNK_ADDR,
        PATH_1X1_MAP_ADDR,
        PATH_1X2_CHUNK_ADDR,
        PATH_1X2_MAP_ADDR,
    )

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a resident chunk-table decision probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_chunk_table_probe_v2")
    parser.add_argument("--output", default="rom/test_vram_font_chunk_table_probe.nds")
    parser.add_argument("--shared-char", default=hex(DEFAULT_SHARED_CHAR))
    parser.add_argument("--char-1x1-extra", default=hex(DEFAULT_1X1_EXTRA_CHAR))
    parser.add_argument("--char-1x2-a", default=hex(DEFAULT_1X2_EXTRA_CHAR_A))
    parser.add_argument("--char-1x2-b", default=hex(DEFAULT_1X2_EXTRA_CHAR_B))
    parser.add_argument("--shared-1x1-chunk-id", type=int, default=0)
    parser.add_argument("--char-1x1-extra-chunk-id", type=int, default=1)
    parser.add_argument("--shared-1x2-chunk-id", type=int, default=0)
    parser.add_argument("--char-1x2-a-chunk-id", type=int, default=1)
    parser.add_argument("--char-1x2-b-chunk-id", type=int, default=0)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    work = repo / args.work
    output_rom = repo / args.output
    shared_char = int(args.shared_char, 0)
    char_1x1_extra = int(args.char_1x1_extra, 0)
    char_1x2_a = int(args.char_1x2_a, 0)
    char_1x2_b = int(args.char_1x2_b, 0)

    copy_unpacked(repo / "rom" / "unpacked" / "origin", work)
    files = write_chunk_table_files(
        work,
        shared_char=shared_char,
        char_1x1_extra=char_1x1_extra,
        char_1x2_a=char_1x2_a,
        char_1x2_b=char_1x2_b,
        shared_1x1_chunk_id=args.shared_1x1_chunk_id,
        char_1x1_extra_chunk_id=args.char_1x1_extra_chunk_id,
        shared_1x2_chunk_id=args.shared_1x2_chunk_id,
        char_1x2_a_chunk_id=args.char_1x2_a_chunk_id,
        char_1x2_b_chunk_id=args.char_1x2_b_chunk_id,
    )
    patch_arm9(work / "arm9.bin")
    patch_overlay(work / "overlay" / "overlay_0000.bin")
    repack(repo, work, output_rom)

    print(f"output={output_rom}")
    print(f"resident_1x1_chunk_id={RESIDENT_1X1_CHUNK_ID}")
    print(f"resident_1x2_chunk_id={RESIDENT_1X2_CHUNK_ID}")
    print(f"fallback_offset=0x{FALLBACK_OFFSET:X}")
    print(f"shared_1x1_chunk_id={args.shared_1x1_chunk_id}")
    print(f"char_1x1_extra_chunk_id={args.char_1x1_extra_chunk_id}")
    print(f"shared_1x2_chunk_id={args.shared_1x2_chunk_id}")
    print(f"char_1x2_a_chunk_id={args.char_1x2_a_chunk_id}")
    print(f"char_1x2_b_chunk_id={args.char_1x2_b_chunk_id}")
    for name, path in files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")


if __name__ == "__main__":
    main()
