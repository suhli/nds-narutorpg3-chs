from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import extract_translation_charset as charset_tools  # noqa: E402


DEFAULT_EXCLUDED_SOURCE_FILES = "msg/wifi/friend_msg.msg,msg/wifi/kinshi_msg.msg"


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def unique_output_path(path: Path, tag: str) -> Path:
    if not path.exists():
        return path
    candidate = path.with_name(f"{path.stem}_{tag}{path.suffix}")
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        indexed = path.with_name(f"{path.stem}_{tag}_{index}{path.suffix}")
        if not indexed.exists():
            return indexed
    raise FileExistsError(f"could not find an unused output path near {path}")


def python_exe() -> Path:
    local = REPO / ".venv" / "Scripts" / "python.exe"
    return local if local.is_file() else Path(sys.executable)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_cmd(args: Iterable[str | Path], *, log_path: Path) -> subprocess.CompletedProcess[str]:
    cmd = [str(arg) for arg in args]
    result = subprocess.run(
        cmd,
        cwd=REPO,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        if result.stdout:
            handle.write(result.stdout)
            if not result.stdout.endswith("\n"):
                handle.write("\n")
        if result.stderr:
            handle.write("[stderr]\n")
            handle.write(result.stderr)
            if not result.stderr.endswith("\n"):
                handle.write("\n")
        handle.write(f"[exit] {result.returncode}\n\n")
    if result.returncode:
        raise RuntimeError(f"command failed with exit={result.returncode}: {' '.join(cmd)}")
    return result


def required_unpack_files(work: Path) -> list[Path]:
    return [
        work / "arm9.bin",
        work / "arm7.bin",
        work / "y9.bin",
        work / "y7.bin",
        work / "banner.bin",
        work / "header.bin",
        work / "data",
        work / "overlay",
    ]


def ensure_origin_unpacked(args: argparse.Namespace, run_dir: Path, log_path: Path) -> Path:
    origin_rom = repo_path(args.origin_rom)
    if origin_rom.resolve() == (REPO / "rom" / "origin.nds").resolve() and not origin_rom.is_file():
        raise FileNotFoundError(origin_rom)
    if not origin_rom.is_file():
        raise FileNotFoundError(origin_rom)

    target = repo_path(args.origin_work)
    complete = all(path.exists() for path in required_unpack_files(target))
    if complete and not args.force_unpack:
        return target

    if target.exists() and not complete:
        target = run_dir / "origin_unpacked"

    target.mkdir(parents=True, exist_ok=True)
    (target / "data").mkdir(parents=True, exist_ok=True)
    (target / "overlay").mkdir(parents=True, exist_ok=True)

    run_cmd(
        [
            TOOLS / "ndstool.exe",
            "-x",
            origin_rom,
            "-9",
            target / "arm9.bin",
            "-7",
            target / "arm7.bin",
            "-y9",
            target / "y9.bin",
            "-y7",
            target / "y7.bin",
            "-d",
            target / "data",
            "-y",
            target / "overlay",
            "-t",
            target / "banner.bin",
            "-h",
            target / "header.bin",
        ],
        log_path=log_path,
    )
    return target


def copy_file(src: Path, dst: Path) -> Path:
    if not src.is_file():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def build_code_assets_from_frozen(
    *,
    frozen_translation: Path,
    out_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Path]:
    frozen_copy = copy_file(frozen_translation, out_dir / "frozen_translation.tsv")
    rows = charset_tools.read_tsv(frozen_copy)
    chars, ascii_counter, char_totals, control_values, raw_word_values = charset_tools.build_charset(rows)
    modes = charset_tools.parse_modes(args.modes)
    existing_scans = [repo_path(path) for path in args.existing_font_scan]
    existing_font_codes = charset_tools.discover_existing_font_codes(existing_scans)
    code_rows, allocation_summary = charset_tools.allocate_codes(
        chars,
        start_code=int(args.start_code, 0),
        code_shape=args.code_shape,
        modes=modes,
        reserved_values=control_values,
        existing_font_codes=existing_font_codes,
        raw_word_values=raw_word_values,
    )

    charset_tools.write_charset(out_dir / "zh_charset.txt", chars)
    charset_tools.write_ignored_ascii(out_dir / "ignored_ascii.txt", ascii_counter)
    charset_tools.write_code_table(out_dir / "zh_code_table.tsv", code_rows)
    charset_tools.write_manifest(out_dir / "font_manifest.json", out_dir / "font_manifest.txt", code_rows)

    summary = {
        "inputs": {
            "frozen_translation": display_path(frozen_translation),
            "existing_font_scan": [display_path(path) for path in existing_scans],
        },
        "outputs": {
            "out_dir": display_path(out_dir),
            "code_table": "zh_code_table.tsv",
            "font_manifest": "font_manifest.json",
        },
        "char_totals": char_totals,
        "allocation": allocation_summary,
        "frozen_sha1": charset_tools.sha1_file(frozen_copy),
    }
    write_text(out_dir / "code-table-summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    if allocation_summary.get("collision_count"):
        raise ValueError(f"code allocation collision_count={allocation_summary['collision_count']}")

    return {
        "frozen_translation": frozen_copy,
        "code_table": out_dir / "zh_code_table.tsv",
        "font_manifest": out_dir / "font_manifest.json",
        "font_manifest_txt": out_dir / "font_manifest.txt",
        "charset": out_dir / "zh_charset.txt",
        "summary": out_dir / "code-table-summary.json",
    }


def validate_menu_report(report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    status_counts = report.get("status_counts", {})
    blocked = {
        status: count
        for status, count in status_counts.items()
        if status != "ready" and count
    }
    if blocked:
        raise ValueError(f"menu translation report has blocked statuses: {blocked}")
    missing = report.get("missing_font_chars", "")
    if missing:
        raise ValueError(f"menu translation report has missing font chars: {missing}")


def prepare_text_assets(args: argparse.Namespace, run_dir: Path, resources: Path, log_path: Path) -> dict[str, Path]:
    text_resources = resources / "text"
    menu_resources = resources / "menu"
    generated = run_dir / "text_assets"
    manual_overrides = repo_path(args.manual_overrides) if args.manual_overrides else text_resources / "translation-struct-manual-overrides.tsv"

    if args.translation_preview:
        code_table = repo_path(args.code_table) if args.code_table else text_resources / "zh_code_table.tsv"
        font_manifest = repo_path(args.font_manifest) if args.font_manifest else text_resources / "font_manifest.json"
        preview = repo_path(args.translation_preview)
        adjusted_preview = generated / "encoded-preview-struct-adjusted.tsv"
        run_cmd(
            [
                python_exe(),
                TOOLS / "audit_structsafe_translations.py",
                "--preview",
                preview,
                "--code-table",
                code_table,
                "--candidate-code-endian",
                args.candidate_code_endian,
                "--manual-overrides",
                manual_overrides,
                "--report-json",
                generated / "translation-struct-audit-report.json",
                "--issues-tsv",
                generated / "translation-struct-mismatches.tsv",
                "--adjusted-preview",
                adjusted_preview,
            ],
            log_path=log_path,
        )
        return {
            "code_table": code_table,
            "font_manifest": font_manifest,
            "frozen_translation": text_resources / "frozen_translation.tsv",
            "preview": adjusted_preview,
            "menu_translations": repo_path(args.menu_translations) if args.menu_translations else menu_resources / "overlay_menu_translations.tsv",
        }

    if args.translation_table or args.rebuild_text_assets:
        frozen = repo_path(args.translation_table) if args.translation_table else text_resources / "frozen_translation.tsv"
        assets = build_code_assets_from_frozen(frozen_translation=frozen, out_dir=generated, args=args)
        encoded_preview = generated / "encoded_preview.tsv"
        run_cmd(
            [
                python_exe(),
                TOOLS / "encode_translation_text.py",
                "--translation",
                assets["frozen_translation"],
                "--code-table",
                assets["code_table"],
                "--preview-out",
                encoded_preview,
                "--report-out",
                generated / "writeback-capacity-report.json",
                "--candidate-code-endian",
                args.candidate_code_endian,
            ],
            log_path=log_path,
        )
        adjusted_preview = generated / "encoded-preview-struct-adjusted.tsv"
        run_cmd(
            [
                python_exe(),
                TOOLS / "audit_structsafe_translations.py",
                "--preview",
                encoded_preview,
                "--code-table",
                assets["code_table"],
                "--candidate-code-endian",
                args.candidate_code_endian,
                "--manual-overrides",
                manual_overrides,
                "--report-json",
                generated / "translation-struct-audit-report.json",
                "--issues-tsv",
                generated / "translation-struct-mismatches.tsv",
                "--adjusted-preview",
                adjusted_preview,
            ],
            log_path=log_path,
        )
        menu_translations = generated / "overlay_menu_translations.tsv"
        menu_report = generated / "overlay_menu_translation_report.json"
        run_cmd(
            [
                python_exe(),
                TOOLS / "prepare_overlay_menu_translations.py",
                "--candidates",
                repo_path(args.menu_candidates) if args.menu_candidates else menu_resources / "overlay_menu_candidates.tsv",
                "--reuse",
                assets["frozen_translation"],
                "--code-table",
                assets["code_table"],
                "--out",
                menu_translations,
                "--report-out",
                menu_report,
            ],
            log_path=log_path,
        )
        validate_menu_report(menu_report)
        return {
            "code_table": assets["code_table"],
            "font_manifest": assets["font_manifest"],
            "frozen_translation": assets["frozen_translation"],
            "preview": adjusted_preview,
            "menu_translations": menu_translations,
        }

    return {
        "code_table": repo_path(args.code_table) if args.code_table else text_resources / "zh_code_table.tsv",
        "font_manifest": repo_path(args.font_manifest) if args.font_manifest else text_resources / "font_manifest.json",
        "frozen_translation": text_resources / "frozen_translation.tsv",
        "preview": text_resources / "encoded-preview-struct-adjusted.tsv",
        "menu_translations": repo_path(args.menu_translations) if args.menu_translations else menu_resources / "overlay_menu_translations.tsv",
    }


def build_font_assets(args: argparse.Namespace, run_dir: Path, resources: Path, text_assets: dict[str, Path], log_path: Path) -> Path:
    if args.font_dir:
        return repo_path(args.font_dir)

    font_1x1 = repo_path(args.font_1x1) if args.font_1x1 else resources / "fonts" / "fusion-pixel-8px-monospaced-zh_hans.ttf"
    font_1x2 = repo_path(args.font_1x2) if args.font_1x2 else resources / "fonts" / "FashionBitmap16_0.092.ttf"
    if args.font:
        font_1x1 = repo_path(args.font)
        font_1x2 = repo_path(args.font)

    font_dir = run_dir / "font_build"
    run_cmd(
        [
            python_exe(),
            TOOLS / "build_vram_font_files.py",
            "--manifest",
            text_assets["font_manifest"],
            "--output-dir",
            font_dir,
            "--font-1x1",
            font_1x1,
            "--font-1x2",
            font_1x2,
        ],
        log_path=log_path,
    )
    return font_dir


def build_rom(args: argparse.Namespace, run_dir: Path, origin_work: Path, text_assets: dict[str, Path], font_dir: Path, log_path: Path) -> Path:
    requested_output = repo_path(args.output)
    if requested_output.resolve() == (REPO / "rom" / "origin.nds").resolve():
        raise ValueError("refusing to overwrite rom/origin.nds")
    output = unique_output_path(requested_output, run_dir.name)

    records_out = repo_path(args.records_out) if args.records_out else run_dir / "build-records.json"
    cmd: list[str | Path] = [
        python_exe(),
        TOOLS / "build_full_writeback_menu_overlay_rom.py",
        "--origin-work",
        origin_work,
        "--preview",
        text_assets["preview"],
        "--menu-translations",
        text_assets["menu_translations"],
        "--font-dir",
        font_dir,
        "--code-table",
        text_assets["code_table"],
        "--candidate-code-endian",
        args.candidate_code_endian,
        "--work",
        run_dir / "rom_work",
        "--output",
        output,
        "--records-out",
        records_out,
        "--exclude-source-files",
        args.exclude_source_files,
    ]
    if not args.keep_record_details:
        cmd.append("--compact-records")
    run_cmd(cmd, log_path=log_path)

    run_cmd([TOOLS / "ndstool.exe", "-i", output], log_path=log_path)
    return output


def write_build_summary(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    origin_work: Path,
    text_assets: dict[str, Path],
    font_dir: Path,
    output: Path,
    log_path: Path,
) -> Path:
    summary = {
        "run_dir": display_path(run_dir),
        "origin_rom": display_path(repo_path(args.origin_rom)),
        "origin_work": display_path(origin_work),
        "output_rom": display_path(output),
        "text_assets": {key: display_path(value) for key, value in text_assets.items()},
        "font_dir": display_path(font_dir),
        "log": display_path(log_path),
        "options": {
            "translation_table": args.translation_table,
            "translation_preview": args.translation_preview,
            "rebuild_text_assets": args.rebuild_text_assets,
            "font": args.font,
            "font_1x1": args.font_1x1,
            "font_1x2": args.font_1x2,
            "font_dir": args.font_dir,
            "candidate_code_endian": args.candidate_code_endian,
            "exclude_source_files": args.exclude_source_files,
        },
    }
    summary_path = run_dir / "patcher-build-summary.json"
    write_text(summary_path, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Naruto RPG3 Chinese patched ROM.")
    parser.add_argument("--origin-rom", default="rom/origin.nds")
    parser.add_argument("--origin-work", default="patcher/work/origin_unpacked")
    parser.add_argument("--resources", default="patcher/resources")
    parser.add_argument("--work-root", default="patcher/work")
    parser.add_argument("--output", default="rom/narutorpg3_chs_patcher.nds")
    parser.add_argument("--records-out", default="")
    parser.add_argument("--force-unpack", action="store_true")

    parser.add_argument("--font", default="", help="Use one TTF for both 1x1 and 1x2 generated font assets.")
    parser.add_argument("--font-1x1", default="")
    parser.add_argument("--font-1x2", default="")
    parser.add_argument("--font-dir", default="", help="Use an existing chs_*.map/chunk directory instead of generating from TTF.")

    parser.add_argument("--translation-table", default="", help="Frozen translation TSV to encode and audit before repacking.")
    parser.add_argument("--translation-preview", default="", help="Encoded preview TSV to audit and repack directly.")
    parser.add_argument("--rebuild-text-assets", action="store_true", help="Rebuild code table, manifest, preview, and menu table from bundled frozen_translation.tsv.")
    parser.add_argument("--code-table", default="")
    parser.add_argument("--font-manifest", default="")
    parser.add_argument("--manual-overrides", default="")
    parser.add_argument("--menu-candidates", default="")
    parser.add_argument("--menu-translations", default="")

    parser.add_argument("--candidate-code-endian", choices=("big", "little"), default="big")
    parser.add_argument("--start-code", default="0xF040")
    parser.add_argument("--code-shape", choices=("contiguous", "sjis"), default="sjis")
    parser.add_argument("--modes", default="1x1,1x2")
    parser.add_argument("--existing-font-scan", action="append", default=[])
    parser.add_argument("--exclude-source-files", default=DEFAULT_EXCLUDED_SOURCE_FILES)
    parser.add_argument("--keep-record-details", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resources = repo_path(args.resources)
    if not resources.is_dir():
        raise FileNotFoundError(resources)

    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = repo_path(args.work_root) / f"build_{run_tag}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "patcher.log"

    origin_work = ensure_origin_unpacked(args, run_dir, log_path)
    text_assets = prepare_text_assets(args, run_dir, resources, log_path)
    font_dir = build_font_assets(args, run_dir, resources, text_assets, log_path)
    output = build_rom(args, run_dir, origin_work, text_assets, font_dir, log_path)
    summary = write_build_summary(
        args=args,
        run_dir=run_dir,
        origin_work=origin_work,
        text_assets=text_assets,
        font_dir=font_dir,
        output=output,
        log_path=log_path,
    )

    print(f"output_rom={output}")
    print(f"run_dir={run_dir}")
    print(f"summary={summary}")
    print(f"log={log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
