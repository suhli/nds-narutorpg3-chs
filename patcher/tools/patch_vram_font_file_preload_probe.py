from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
from pathlib import Path


OVERLAY0_BASE = 0x0207E320
ARM9_BASE = 0x02000000

SAVE_CHAR_PATCH_ADDR = 0x0208914C
COPY_PATCH_ADDR = 0x02089190
LOAD_PATCH_ADDR = 0x020869E0
ORIGINAL_SAVE_CHAR_WORD = 0xE1A06001
ORIGINAL_COPY_WORD = 0xEBFDFD89
ORIGINAL_LOAD_WORD = 0xE28DD020  # add sp, sp, #0x20
ORIGINAL_COPY_ADDR = 0x020087BC
FILE_LOAD_ADDR = 0x0207F80C

SAVE_CHAR_HOOK_ADDR = 0x0207411C
COPY_HOOK_ADDR = 0x02074140
LOAD_HOOK_ADDR = 0x020741A0
PATH_STRING_ADDR = 0x02074240
CHS_DATA_PTR_ADDR = 0x02074280
CHS_DATA_SIZE_ADDR = 0x02074284
CURRENT_CHAR_ADDR = 0x02074288
PATCH_SIZE = 0x180

DEFAULT_CHAR_A = 0x82CD
DEFAULT_CHAR_B = 0x82DF
CHS_NITROFS_PATH = "font/chs_probe.bin"
CHS_UNPACKED_PATH = Path("data/font/chs_probe.bin")


def arm_branch(src: int, dst: int, *, link: bool) -> int:
    offset = (dst - (src + 8)) >> 2
    if offset < -0x800000 or offset > 0x7FFFFF:
        raise ValueError(f"branch out of range: {src:08X} -> {dst:08X}")
    return (0xEB000000 if link else 0xEA000000) | (offset & 0xFFFFFF)


def arm_cond_branch(src: int, dst: int, cond_opcode: int) -> int:
    offset = (dst - (src + 8)) >> 2
    if offset < -0x800000 or offset > 0x7FFFFF:
        raise ValueError(f"branch out of range: {src:08X} -> {dst:08X}")
    return cond_opcode | (offset & 0xFFFFFF)


def ldr_literal(rd: int, instr_addr: int, literal_addr: int) -> int:
    offset = literal_addr - (instr_addr + 8)
    if offset < 0 or offset > 0xFFF:
        raise ValueError(f"literal out of range: {instr_addr:08X} -> {literal_addr:08X}")
    return 0xE59F0000 | (rd << 12) | offset


def word(value: int) -> bytes:
    return struct.pack("<I", value)


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
    hook_addr = COPY_HOOK_ADDR
    current_lit = COPY_HOOK_ADDR + 0x54
    data_ptr_lit = COPY_HOOK_ADDR + 0x58
    done_addr = COPY_HOOK_ADDR + 0x4C
    loop_addr = COPY_HOOK_ADDR + 0x2C

    hook = bytearray()
    hook += word(0xE92D501C)  # push {r2, r3, r4, r12, lr}
    hook += word(ldr_literal(3, hook_addr + len(hook), current_lit))
    hook += word(0xE5933000)  # ldr r3, [r3]
    hook += word(ldr_literal(14, hook_addr + len(hook), data_ptr_lit))
    hook += word(0xE59EE000)  # ldr lr, [lr]
    hook += word(0xE35E0000)  # cmp lr, #0
    hook += word(arm_cond_branch(hook_addr + len(hook), done_addr, 0x0A000000))
    hook += word(0xE59E2000)  # ldr r2, [lr]
    hook += word(0xE28E4004)  # add r4, lr, #4
    hook += word(0xE3520000)  # cmp r2, #0
    hook += word(arm_cond_branch(hook_addr + len(hook), done_addr, 0x0A000000))
    if hook_addr + len(hook) != loop_addr:
        raise AssertionError("copy hook loop address drifted")
    hook += word(0xE494C004)  # ldr r12, [r4], #4
    hook += word(0xE153000C)  # cmp r3, r12
    hook += word(0x05940000)  # ldreq r0, [r4]
    hook += word(0x0080000E)  # addeq r0, r0, lr
    hook += word(arm_cond_branch(hook_addr + len(hook), done_addr, 0x0A000000))
    hook += word(0xE2844004)  # add r4, r4, #4
    hook += word(0xE2522001)  # subs r2, r2, #1
    hook += word(arm_cond_branch(hook_addr + len(hook), loop_addr, 0x1A000000))
    if hook_addr + len(hook) != done_addr:
        raise AssertionError("copy hook done address drifted")
    hook += word(0xE8BD501C)  # pop {r2, r3, r4, r12, lr}
    hook += word(arm_branch(hook_addr + len(hook), ORIGINAL_COPY_ADDR, link=False))
    if hook_addr + len(hook) != current_lit:
        raise AssertionError("copy hook literal address drifted")
    hook += word(CURRENT_CHAR_ADDR)
    hook += word(CHS_DATA_PTR_ADDR)
    return bytes(hook)


def build_load_hook() -> bytes:
    hook_addr = LOAD_HOOK_ADDR
    literals_addr = LOAD_HOOK_ADDR + 0x44
    data_lit = literals_addr
    path_lit = literals_addr + 4
    data_lit_again = literals_addr + 8
    max_lit = literals_addr + 12
    size_lit = literals_addr + 16

    hook = bytearray()
    hook += word(0xE92D401F)  # push {r0, r1, r2, r3, r4, lr}
    hook += word(0xE24DD008)  # sub sp, sp, #8
    hook += word(ldr_literal(0, hook_addr + len(hook), data_lit))
    hook += word(0xE3A01000)  # mov r1, #0
    hook += word(0xE5801000)  # str r1, [r0]
    hook += word(ldr_literal(0, hook_addr + len(hook), path_lit))
    hook += word(ldr_literal(1, hook_addr + len(hook), data_lit_again))
    hook += word(ldr_literal(2, hook_addr + len(hook), max_lit))
    hook += word(0xE3A03000)  # mov r3, #0
    hook += word(0xE58D3000)  # str r3, [sp]
    hook += word(ldr_literal(4, hook_addr + len(hook), size_lit))
    hook += word(0xE58D4004)  # str r4, [sp, #4]
    hook += word(arm_branch(hook_addr + len(hook), FILE_LOAD_ADDR, link=True))
    hook += word(0xE28DD008)  # add sp, sp, #8
    hook += word(0xE8BD401F)  # pop {r0, r1, r2, r3, r4, lr}
    hook += word(0xE28DD020)  # add sp, sp, #0x20
    hook += word(0xE8BD8010)  # pop {r4, pc}
    if hook_addr + len(hook) != literals_addr:
        raise AssertionError("load hook literal address drifted")
    hook += word(CHS_DATA_PTR_ADDR)
    hook += word(PATH_STRING_ADDR)
    hook += word(CHS_DATA_PTR_ADDR)
    hook += word(0x7FFFFFFF)
    hook += word(CHS_DATA_SIZE_ADDR)
    return bytes(hook)


def glyph_a() -> bytes:
    return bytes(
        [
            0x33, 0x33, 0x33, 0x33, 0x11, 0x11, 0x11, 0x11,
            0x33, 0x33, 0x33, 0x33, 0x11, 0x11, 0x11, 0x11,
            0x11, 0x11, 0x33, 0x33, 0x33, 0x33, 0x11, 0x11,
            0x11, 0x11, 0x33, 0x33, 0x33, 0x33, 0x11, 0x11,
            0x11, 0x11, 0x33, 0x33, 0x33, 0x33, 0x11, 0x11,
            0x11, 0x11, 0x33, 0x33, 0x33, 0x33, 0x11, 0x11,
            0x33, 0x33, 0x33, 0x33, 0x11, 0x11, 0x11, 0x11,
            0x33, 0x33, 0x33, 0x33, 0x11, 0x11, 0x11, 0x11,
        ]
    )


def glyph_b() -> bytes:
    return bytes(
        [
            0x22, 0x22, 0x44, 0x44, 0x44, 0x44, 0x22, 0x22,
            0x22, 0x22, 0x44, 0x44, 0x44, 0x44, 0x22, 0x22,
            0x44, 0x44, 0x22, 0x22, 0x22, 0x22, 0x44, 0x44,
            0x44, 0x44, 0x22, 0x22, 0x22, 0x22, 0x44, 0x44,
            0x44, 0x44, 0x22, 0x22, 0x22, 0x22, 0x44, 0x44,
            0x44, 0x44, 0x22, 0x22, 0x22, 0x22, 0x44, 0x44,
            0x22, 0x22, 0x44, 0x44, 0x44, 0x44, 0x22, 0x22,
            0x22, 0x22, 0x44, 0x44, 0x44, 0x44, 0x22, 0x22,
        ]
    )


def build_chs_file(char_a: int, char_b: int) -> bytes:
    data = bytearray()
    data += word(2)
    data += word(char_a)
    data += word(0x20)
    data += word(char_b)
    data += word(0x60)
    data += bytes(0x20 - len(data))
    data += glyph_a()
    data += glyph_b()
    return bytes(data)


def build_payload() -> bytes:
    payload = bytearray(PATCH_SIZE)
    save = build_save_char_hook()
    copy = build_copy_hook()
    load = build_load_hook()
    payload[: len(save)] = save
    payload[COPY_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR : COPY_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR + len(copy)] = copy
    payload[LOAD_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR : LOAD_HOOK_ADDR - SAVE_CHAR_HOOK_ADDR + len(load)] = load
    path = CHS_NITROFS_PATH.encode("ascii") + b"\x00"
    payload[PATH_STRING_ADDR - SAVE_CHAR_HOOK_ADDR : PATH_STRING_ADDR - SAVE_CHAR_HOOK_ADDR + len(path)] = path
    payload[CHS_DATA_PTR_ADDR - SAVE_CHAR_HOOK_ADDR : CHS_DATA_PTR_ADDR - SAVE_CHAR_HOOK_ADDR + 12] = bytes(12)
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


def copy_unpacked(src: Path, dst: Path) -> None:
    if dst.exists():
        raise FileExistsError(dst)
    shutil.copytree(src, dst)


def repack(repo: Path, work: Path, output_rom: Path) -> None:
    if output_rom.exists():
        raise FileExistsError(output_rom)
    cmd = [
        str(repo / "tools" / "ndstool.exe"),
        "-c",
        str(output_rom),
        "-9",
        str(work / "arm9.bin"),
        "-7",
        str(work / "arm7.bin"),
        "-y9",
        str(work / "y9.bin"),
        "-y7",
        str(work / "y7.bin"),
        "-d",
        str(work / "data"),
        "-y",
        str(work / "overlay"),
        "-t",
        str(work / "banner.bin"),
        "-h",
        str(work / "header.bin"),
    ]
    subprocess.run(cmd, cwd=repo, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a file-preloaded VRAM font hook probe ROM.")
    parser.add_argument("--work", default="rom/unpacked/vram_font_file_preload_probe_v2")
    parser.add_argument("--output", default="rom/test_vram_font_file_preload_probe.nds")
    parser.add_argument("--char-a", default=hex(DEFAULT_CHAR_A), help="First character code mapped to glyph A")
    parser.add_argument("--char-b", default=hex(DEFAULT_CHAR_B), help="Second character code mapped to glyph B")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    work = repo / args.work
    output_rom = repo / args.output
    char_a = int(args.char_a, 0)
    char_b = int(args.char_b, 0)

    copy_unpacked(repo / "rom" / "unpacked" / "origin", work)
    chs_path = work / CHS_UNPACKED_PATH
    chs_path.write_bytes(build_chs_file(char_a, char_b))
    patch_overlay(work / "overlay" / "overlay_0000.bin")
    patch_arm9(work / "arm9.bin")
    repack(repo, work, output_rom)

    print(f"work={work}")
    print(f"output={output_rom}")
    print(f"nitrofs_path={CHS_NITROFS_PATH}")
    print(f"chs_file={chs_path}")
    print(f"load_hook=0x{LOAD_HOOK_ADDR:08X}")
    print(f"copy_hook=0x{COPY_HOOK_ADDR:08X}")
    print(f"current_char=0x{CURRENT_CHAR_ADDR:08X}")
    print(f"data_ptr=0x{CHS_DATA_PTR_ADDR:08X}")
    print(f"data_size=0x{CHS_DATA_SIZE_ADDR:08X}")
    print(f"char_a=0x{char_a:04X} glyph_offset=0x20")
    print(f"char_b=0x{char_b:04X} glyph_offset=0x60")


if __name__ == "__main__":
    main()
