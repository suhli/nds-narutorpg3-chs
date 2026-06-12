from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any


PATCHER_DIR = Path(__file__).resolve().parent
REPO = PATCHER_DIR.parent
DEFAULT_DATA = PATCHER_DIR / "narutorpg3_chs_v36.json"


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def load_project(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "narutorpg3-chs-final-project-v1":
        raise ValueError(f"unsupported project data schema: {data.get('schema')!r}")
    return data


def decode_rom_image(data: dict[str, Any]) -> bytes:
    rom_image = data["rom_image"]
    if rom_image.get("encoding") != "base64" or rom_image.get("compression") != "zlib":
        raise ValueError("unsupported ROM image encoding")
    compressed = base64.b64decode(rom_image["data"])
    expected_compressed_size = int(rom_image["compressed_size"])
    if len(compressed) != expected_compressed_size:
        raise ValueError(
            f"compressed ROM size mismatch: got {len(compressed)}, expected {expected_compressed_size}"
        )
    rom = zlib.decompress(compressed)
    expected_size = int(rom_image["uncompressed_size"])
    if len(rom) != expected_size:
        raise ValueError(f"ROM size mismatch: got {len(rom)}, expected {expected_size}")
    expected_sha = str(rom_image["sha256"]).upper()
    actual_sha = sha256_bytes(rom)
    if actual_sha != expected_sha:
        raise ValueError(f"ROM SHA256 mismatch: got {actual_sha}, expected {expected_sha}")
    return rom


def unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}_{tag}{path.suffix}")
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        indexed = path.with_name(f"{path.stem}_{tag}_{index}{path.suffix}")
        if not indexed.exists():
            return indexed
    raise FileExistsError(f"could not find an unused output path near {path}")


def write_rom(path: Path, data: bytes, *, force: bool) -> Path:
    output = path if force else unique_output_path(path)
    if output.resolve() == (REPO / "rom" / "origin.nds").resolve():
        raise ValueError("refusing to overwrite rom/origin.nds")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def command_info(args: argparse.Namespace) -> int:
    data = load_project(repo_path(args.data))
    source = data["source_rom"]
    output = data["output_rom"]
    translations = data["translations"]
    writeback = data["writeback"]
    term = writeback.get("terminator_padding_audit", {})
    print(f"version={data['version']}")
    print(f"status={data.get('status', '')}")
    print(f"source_sha256={source['sha256']}")
    print(f"output_sha256={output['sha256']}")
    print(f"text_rows={translations['text_row_count']}")
    print(f"menu_rows={translations['menu_row_count']}")
    print(f"manual_overrides={translations['manual_override_row_count']}")
    print(f"structural_risk_rows={writeback.get('structural_audit', {}).get('risk_rows')}")
    print(f"pre_0300_fullwidth_padding_rows={term.get('fullwidth_padding_before_final_0300_rows')}")
    print(f"post_0300_zero_then_later_0300_rows={term.get('terminator_then_zero_then_later_0300_rows')}")
    print(f"post_0300_fullwidth_then_later_0300_rows={term.get('terminator_then_fullwidth_then_later_0300_rows')}")
    return 0


def command_verify_data(args: argparse.Namespace) -> int:
    data_path = repo_path(args.data)
    data = load_project(data_path)
    rom = decode_rom_image(data)
    print(f"data={display_path(data_path)}")
    print(f"embedded_rom_size={len(rom)}")
    print(f"embedded_rom_sha256={sha256_bytes(rom)}")
    return 0


def command_build(args: argparse.Namespace) -> int:
    data_path = repo_path(args.data)
    origin_path = repo_path(args.origin_rom)
    output_path = repo_path(args.output)
    data = load_project(data_path)

    if not origin_path.is_file():
        raise FileNotFoundError(origin_path)
    expected_origin_sha = str(data["source_rom"]["sha256"]).upper()
    actual_origin_sha = sha256_file(origin_path)
    if actual_origin_sha != expected_origin_sha:
        raise ValueError(f"origin ROM SHA256 mismatch: got {actual_origin_sha}, expected {expected_origin_sha}")

    rom = decode_rom_image(data)
    output = write_rom(output_path, rom, force=args.force)
    print(f"data={display_path(data_path)}")
    print(f"origin={display_path(origin_path)}")
    print(f"output_rom={display_path(output)}")
    print(f"output_sha256={sha256_bytes(rom)}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the verified Naruto RPG3 Chinese ROM from one consolidated project data file."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Validate origin.nds and write the final patched ROM.")
    build.add_argument("--data", default=DEFAULT_DATA.as_posix())
    build.add_argument("--origin-rom", default="rom/origin.nds")
    build.add_argument("--output", default="rom/narutorpg3_chs.nds")
    build.add_argument("--force", action="store_true", help="Overwrite the output path if it already exists.")
    build.set_defaults(func=command_build)

    info = subparsers.add_parser("info", help="Print project summary from the consolidated data file.")
    info.add_argument("--data", default=DEFAULT_DATA.as_posix())
    info.set_defaults(func=command_info)

    verify = subparsers.add_parser("verify-data", help="Decode and hash-check the embedded final ROM image.")
    verify.add_argument("--data", default=DEFAULT_DATA.as_posix())
    verify.set_defaults(func=command_verify_data)
    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    commands = {"build", "info", "verify-data", "-h", "--help"}
    if not argv or argv[0] not in commands:
        return ["build", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(normalize_argv(list(sys.argv[1:] if argv is None else argv)))
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
