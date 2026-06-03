from __future__ import annotations

import argparse
import struct
from pathlib import Path

from patch_vram_font_file_preload_probe import (
    ARM9_BASE,
    COPY_PATCH_ADDR,
    FILE_LOAD_ADDR,
    LOAD_PATCH_ADDR,
    ORIGINAL_COPY_ADDR,
    ORIGINAL_COPY_WORD,
    ORIGINAL_LOAD_WORD,
    ORIGINAL_SAVE_CHAR_WORD,
    OVERLAY0_BASE,
    SAVE_CHAR_PATCH_ADDR,
    arm_branch,
    arm_cond_branch,
    copy_unpacked,
    ldr_literal,
    repack,
    word,
)


SAVE_CHAR_HOOK_ADDR = 0x0207411C
COPY_HOOK_ADDR = 0x02074140
LOAD_HOOK_ADDR = 0x02074200

PATH_1X1_MAP_ADDR = 0x02074340
PATH_1X1_CHUNK_ADDR = 0x02074354
PATH_1X2_MAP_ADDR = 0x02074368
PATH_1X2_CHUNK_ADDR = 0x0207437C

CHS_1X1_MAP_PTR_ADDR = 0x020743A0
CHS_1X1_MAP_SIZE_ADDR = 0x020743A4
CHS_1X1_CHUNK_PTR_ADDR = 0x020743A8
CHS_1X1_CHUNK_SIZE_ADDR = 0x020743AC
CHS_1X2_MAP_PTR_ADDR = 0x020743B0
CHS_1X2_MAP_SIZE_ADDR = 0x020743B4
CHS_1X2_CHUNK_PTR_ADDR = 0x020743B8
CHS_1X2_CHUNK_SIZE_ADDR = 0x020743BC
CURRENT_CHAR_ADDR = 0x020743C0

PATCH_SIZE = 0x2C0
MAX_LOAD_SIZE = 0x7FFFFFFF

NITROFS_FILES = {
    "1x1_map": ("font/chs_1x1.map", Path("data/font/chs_1x1.map")),
    "1x1_chunk": ("font/chs_1x1.chunk", Path("data/font/chs_1x1.chunk")),
    "1x2_map": ("font/chs_1x2.map", Path("data/font/chs_1x2.map")),
    "1x2_chunk": ("font/chs_1x2.chunk", Path("data/font/chs_1x2.chunk")),
}

DEFAULT_SHARED_CHAR = 0x82A2
DEFAULT_1X1_EXTRA_CHAR = 0x82BD
DEFAULT_1X2_EXTRA_CHAR_A = 0x82CD
DEFAULT_1X2_EXTRA_CHAR_B = 0x82DF


class ArmBuilder:
    def __init__(self, base_addr: int) -> None:
        self.base_addr = base_addr
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.branch_patches: list[tuple[int, str, int]] = []
        self.ldr_patches: list[tuple[int, int, str]] = []

    @property
    def pc(self) -> int:
        return self.base_addr + len(self.data)

    def emit(self, value: int) -> None:
        self.data += word(value)

    def label(self, name: str) -> None:
        self.labels[name] = self.pc

    def b(self, label: str, cond_opcode: int = 0xEA000000) -> None:
        self.branch_patches.append((len(self.data), label, cond_opcode))
        self.emit(0)

    def ldr_label(self, rd: int, label: str) -> None:
        self.ldr_patches.append((len(self.data), rd, label))
        self.emit(0)

    def bl_abs(self, dst: int) -> None:
        self.emit(arm_branch(self.pc, dst, link=True))

    def b_abs(self, dst: int) -> None:
        self.emit(arm_branch(self.pc, dst, link=False))

    def literal(self, name: str, value: int) -> None:
        self.label(name)
        self.emit(value)

    def finalize(self) -> bytes:
        for off, label, cond_opcode in self.branch_patches:
            src = self.base_addr + off
            dst = self.labels[label]
            struct.pack_into("<I", self.data, off, arm_cond_branch(src, dst, cond_opcode))
        for off, rd, label in self.ldr_patches:
            src = self.base_addr + off
            dst = self.labels[label]
            struct.pack_into("<I", self.data, off, ldr_literal(rd, src, dst))
        return bytes(self.data)


def build_save_char_hook() -> bytes:
    hook = bytearray()
    hook += word(0xE92D4008)  # push {r3, lr}
    hook += word(0xE1A06001)  # mov r6, r1
    hook += word(0xE59F3004)  # ldr r3, [pc, #4]
    hook += word(0xE5831000)  # str r1, [r3]
    hook += word(0xE8BD8008)  # pop {r3, pc}
    hook += word(CURRENT_CHAR_ADDR)
    return bytes(hook)


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
    b.emit(0xE5946000)  # ldr r6, [r4]
    b.emit(0xE2844004)  # add r4, r4, #4
    b.emit(0xE3560000)  # cmp r6, #0
    b.b("done", 0x0A000000)

    b.label("loop")
    b.emit(0xE494C004)  # ldr r12, [r4], #4
    b.emit(0xE153000C)  # cmp r3, r12
    b.emit(0x05940000)  # ldreq r0, [r4]
    b.emit(0x00800005)  # addeq r0, r0, r5
    b.b("done", 0x0A000000)
    b.emit(0xE2844004)  # add r4, r4, #4
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


def emit_load_file(
    b: ArmBuilder,
    *,
    name: str,
    path_addr: int,
    ptr_addr: int,
    size_addr: int,
) -> None:
    b.ldr_label(0, f"{name}_ptr_lit")
    b.emit(0xE3A01000)  # mov r1, #0
    b.emit(0xE5801000)  # str r1, [r0]
    b.ldr_label(0, f"{name}_size_lit")
    b.emit(0xE5801000)  # str r1, [r0]
    b.ldr_label(0, f"{name}_path_lit")
    b.ldr_label(1, f"{name}_ptr_lit")
    b.ldr_label(2, "max_load_lit")
    b.emit(0xE3A03000)  # mov r3, #0
    b.emit(0xE58D3000)  # str r3, [sp]
    b.ldr_label(4, f"{name}_size_lit")
    b.emit(0xE58D4004)  # str r4, [sp, #4]
    b.bl_abs(FILE_LOAD_ADDR)


def build_load_hook() -> bytes:
    b = ArmBuilder(LOAD_HOOK_ADDR)
    b.emit(0xE92D401F)  # push {r0, r1, r2, r3, r4, lr}
    b.emit(0xE24DD008)  # sub sp, sp, #8

    emit_load_file(
        b,
        name="map_1x1",
        path_addr=PATH_1X1_MAP_ADDR,
        ptr_addr=CHS_1X1_MAP_PTR_ADDR,
        size_addr=CHS_1X1_MAP_SIZE_ADDR,
    )
    emit_load_file(
        b,
        name="chunk_1x1",
        path_addr=PATH_1X1_CHUNK_ADDR,
        ptr_addr=CHS_1X1_CHUNK_PTR_ADDR,
        size_addr=CHS_1X1_CHUNK_SIZE_ADDR,
    )
    emit_load_file(
        b,
        name="map_1x2",
        path_addr=PATH_1X2_MAP_ADDR,
        ptr_addr=CHS_1X2_MAP_PTR_ADDR,
        size_addr=CHS_1X2_MAP_SIZE_ADDR,
    )
    emit_load_file(
        b,
        name="chunk_1x2",
        path_addr=PATH_1X2_CHUNK_ADDR,
        ptr_addr=CHS_1X2_CHUNK_PTR_ADDR,
        size_addr=CHS_1X2_CHUNK_SIZE_ADDR,
    )

    b.emit(0xE28DD008)  # add sp, sp, #8
    b.emit(0xE8BD401F)  # pop {r0, r1, r2, r3, r4, lr}
    b.emit(0xE28DD020)  # add sp, sp, #0x20
    b.emit(0xE8BD8010)  # pop {r4, pc}
    b.literal("max_load_lit", MAX_LOAD_SIZE)
    b.literal("map_1x1_path_lit", PATH_1X1_MAP_ADDR)
    b.literal("map_1x1_ptr_lit", CHS_1X1_MAP_PTR_ADDR)
    b.literal("map_1x1_size_lit", CHS_1X1_MAP_SIZE_ADDR)
    b.literal("chunk_1x1_path_lit", PATH_1X1_CHUNK_ADDR)
    b.literal("chunk_1x1_ptr_lit", CHS_1X1_CHUNK_PTR_ADDR)
    b.literal("chunk_1x1_size_lit", CHS_1X1_CHUNK_SIZE_ADDR)
    b.literal("map_1x2_path_lit", PATH_1X2_MAP_ADDR)
    b.literal("map_1x2_ptr_lit", CHS_1X2_MAP_PTR_ADDR)
    b.literal("map_1x2_size_lit", CHS_1X2_MAP_SIZE_ADDR)
    b.literal("chunk_1x2_path_lit", PATH_1X2_CHUNK_ADDR)
    b.literal("chunk_1x2_ptr_lit", CHS_1X2_CHUNK_PTR_ADDR)
    b.literal("chunk_1x2_size_lit", CHS_1X2_CHUNK_SIZE_ADDR)
    return b.finalize()


def build_map(entries: list[tuple[int, int]]) -> bytes:
    data = bytearray()
    data += word(len(entries))
    for char_code, offset in entries:
        data += word(char_code)
        data += word(offset)
    return bytes(data)


def repeated_glyph(size: int, first: int, second: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        data += bytes([first]) * 4
        data += bytes([second]) * 4
    return bytes(data[:size])


def build_payload() -> bytes:
    payload = bytearray(PATCH_SIZE)
    save = build_save_char_hook()
    copy = build_copy_hook()
    load = build_load_hook()
    copy_off = COPY_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR
    load_off = LOAD_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR
    path_off = PATH_1X1_MAP_ADDR - SAVE_CHAR_HOOK_ADDR

    if copy_off < len(save):
        raise AssertionError("save hook overlaps copy hook")
    if copy_off + len(copy) > load_off:
        raise AssertionError("copy hook overlaps load hook")
    if load_off + len(load) > path_off:
        raise AssertionError("load hook overlaps path strings")

    payload[: len(save)] = save
    payload[copy_off : copy_off + len(copy)] = copy
    payload[load_off : load_off + len(load)] = load

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

    vars_off = CHS_1X1_MAP_PTR_ADDR - SAVE_CHAR_HOOK_ADDR
    payload[vars_off : CURRENT_CHAR_ADDR - SAVE_CHAR_HOOK_ADDR + 4] = bytes(
        CURRENT_CHAR_ADDR - CHS_1X1_MAP_PTR_ADDR + 4
    )
    return bytes(payload)


def patch_overlay(overlay_path: Path) -> None:
    data = bytearray(overlay_path.read_bytes())
    checks = [
        (SAVE_CHAR_PATCH_ADDR, ORIGINAL_SAVE_CHAR_WORD, arm_branch(SAVE_CHAR_PATCH_ADDR, SAVE_CHAR_HOOK_ADDR, link=True)),
        (COPY_PATCH_ADDR, ORIGINAL_COPY_WORD, arm_branch(COPY_PATCH_ADDR, COPY_HOOK_ADDR, link=True)),
        (LOAD_PATCH_ADDR, ORIGINAL_LOAD_WORD, arm_branch(LOAD_PATCH_ADDR, LOAD_HOOK_ADDR, link=False)),
    ]
    for addr, expected, replacement in checks:
        off = addr - OVERLAY0_BASE
        actual = struct.unpack_from("<I", data, off)[0]
        if actual != expected:
            raise ValueError(f"unexpected word at 0x{addr:08X}: got {actual:08X}, expected {expected:08X}")
        struct.pack_into("<I", data, off, replacement)
    overlay_path.write_bytes(data)


def patch_arm9(arm9_path: Path) -> None:
    data = bytearray(arm9_path.read_bytes())
    off = SAVE_CHAR_HOOK_ADDR - ARM9_BASE
    old = data[off : off + PATCH_SIZE]
    if len(old) != PATCH_SIZE or any(old):
        raise ValueError(f"ARM9 hook cave is not empty at 0x{SAVE_CHAR_HOOK_ADDR:08X}")
    data[off : off + PATCH_SIZE] = build_payload()
    arm9_path.write_bytes(data)


def write_split_files(
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

    paths["1x1_map"].write_bytes(build_map([(shared_char, 0x00), (char_1x1_extra, 0x20)]))
    paths["1x1_chunk"].write_bytes(
        repeated_glyph(0x20, 0x15, 0x51)
        + repeated_glyph(0x20, 0x26, 0x62)
    )
    paths["1x2_map"].write_bytes(
        build_map([(shared_char, 0x00), (char_1x2_a, 0x40), (char_1x2_b, 0x80)])
    )
    paths["1x2_chunk"].write_bytes(
        repeated_glyph(0x40, 0x37, 0x73)
        + repeated_glyph(0x40, 0x48, 0x84)
        + repeated_glyph(0x40, 0x59, 0x95)
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a split 1x1/1x2 map and chunk font hook probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_split_map_probe")
    parser.add_argument("--output", default="rom/test_vram_font_split_map_probe.nds")
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
    split_files = write_split_files(
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
    for name, path in split_files.items():
        print(f"{name}={path} size=0x{path.stat().st_size:X}")
    print(f"load_hook=0x{LOAD_HOOK_ADDR:08X}")
    print(f"copy_hook=0x{COPY_HOOK_ADDR:08X}")
    print(f"current_char=0x{CURRENT_CHAR_ADDR:08X}")
    print(f"1x1_map_ptr=0x{CHS_1X1_MAP_PTR_ADDR:08X}")
    print(f"1x1_chunk_ptr=0x{CHS_1X1_CHUNK_PTR_ADDR:08X}")
    print(f"1x2_map_ptr=0x{CHS_1X2_MAP_PTR_ADDR:08X}")
    print(f"1x2_chunk_ptr=0x{CHS_1X2_CHUNK_PTR_ADDR:08X}")
    print(f"shared_char=0x{shared_char:04X} 1x1_offset=0x00 1x2_offset=0x00")
    print(f"char_1x1_extra=0x{char_1x1_extra:04X} 1x1_offset=0x20")
    print(f"char_1x2_a=0x{char_1x2_a:04X} 1x2_offset=0x40")
    print(f"char_1x2_b=0x{char_1x2_b:04X} 1x2_offset=0x80")


if __name__ == "__main__":
    main()
