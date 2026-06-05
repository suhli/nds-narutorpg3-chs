from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

import build_text_writeback_smoke_rom as text_rom
import build_vram_font_dynamic_cache_rom as font_rom
import patch_vram_font_chunk_table_dual_immediate_cache_probe as cache
import patch_vram_font_split_map_probe as split


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_hex_bytes(value: str) -> bytes:
    value = (value or "").strip()
    if not value:
        return b""
    return bytes(int(part, 16) for part in value.split())


def should_space_pad_visible_overlay_span(row: dict[str, str]) -> bool:
    notes = row.get("notes", "")
    if "manual_0100_delimited" in notes:
        return True
    if row.get("source_file") != "overlay/overlay_0002.bin":
        return False
    offset = int(row["offset"], 0)
    return 0x12C0C <= offset <= 0x12C80


def overlay_replacement(row: dict[str, str], encoded: bytes, slot_len: int) -> tuple[bytes, dict[str, Any]]:
    raw_len = int(row.get("raw_len") or len(parse_hex_bytes(row.get("raw_hex", ""))))
    if should_space_pad_visible_overlay_span(row) and len(encoded) <= raw_len <= slot_len:
        visible_padding = text_rom.message_padding(raw_len - len(encoded))
        zero_padding = bytes(slot_len - raw_len)
        return encoded + visible_padding + zero_padding, {
            "overlay_padding_strategy": "fullwidth_to_original_visible_len_then_zero",
            "visible_padding_count": len(visible_padding),
            "fill_zero_count": len(zero_padding),
        }
    return encoded + bytes(slot_len - len(encoded)), {
        "overlay_padding_strategy": "zero_fill_after_encoded",
        "visible_padding_count": 0,
        "fill_zero_count": slot_len - len(encoded),
    }


def patch_menu_rows(work: Path, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "ready":
            continue
        rel_path = Path(row["source_file"])
        target = work / rel_path
        if not target.is_file():
            raise FileNotFoundError(target)
        offset = int(row["offset"], 0)
        slot_len = int(row["slot_len"])
        encoded = parse_hex_bytes(row["encoded_hex"])
        if len(encoded) > slot_len:
            raise ValueError(f"{row['id']} encoded length exceeds slot")

        data = bytearray(target.read_bytes())
        original = bytes(data[offset : offset + slot_len])
        expected_prefix = parse_hex_bytes(row["raw_hex"])
        if not original.startswith(expected_prefix):
            raise ValueError(f"{row['id']} original bytes mismatch at {target}:{row['offset']}")
        replacement, padding_info = overlay_replacement(row, encoded, slot_len)
        data[offset : offset + slot_len] = replacement
        target.write_bytes(data)
        records.append(
            {
                "id": row["id"],
                "source_file": row["source_file"],
                "work_file": target.as_posix(),
                "offset": row["offset"],
                "slot_len": slot_len,
                "jp_text": row["jp_text"],
                "zh_text": row["zh_text"],
                "encoded_len": len(encoded),
                **padding_info,
                "original_hex": original.hex(" ").upper(),
                "replacement_hex": replacement.hex(" ").upper(),
            }
        )
    return records


def build(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    repo = Path(__file__).resolve().parents[1]
    origin_work = (repo / args.origin_work).resolve()
    if not origin_work.is_dir():
        raise FileNotFoundError(origin_work)
    requested_work = (repo / args.work).resolve()
    requested_output = (repo / args.output).resolve()
    if requested_output.name.lower() == "origin.nds":
        raise ValueError("refusing to overwrite rom/origin.nds")

    work = text_rom.unique_path(requested_work)
    output_rom = text_rom.unique_path(requested_output)
    shutil.copytree(origin_work, work)

    font_files = font_rom.copy_font_files((repo / args.font_dir).resolve(), work)
    font_rom.validate_font_files(font_files)

    excluded_source_files = text_rom.parse_source_file_set(args.exclude_source_files)
    text_rows, excluded_text_counts = text_rom.load_all_rows(repo / args.preview, excluded_source_files)
    text_validation = text_rom.validate_no_overlaps(work, text_rows)
    code_table = text_rom.load_code_table(repo / args.code_table)
    text_records = text_rom.patch_samples(
        work,
        text_rows,
        keep_sample_text=False,
        code_table=code_table,
        candidate_code_endian=args.candidate_code_endian,
    )

    cache.patch_arm9(work / "arm9.bin")
    cache.patch_overlay(work / "overlay" / "overlay_0000.bin")

    menu_rows = read_rows(repo / args.menu_translations)
    menu_records = patch_menu_rows(work, menu_rows)
    split.repack(repo, work, output_rom)

    metadata = {
        "work": work.as_posix(),
        "output_rom": output_rom.as_posix(),
        "origin_work": origin_work.as_posix(),
        "font_dir": (repo / args.font_dir).resolve().as_posix(),
        "font_cache_strategy": {
            "name": "dual_immediate_1x1_1x2_page_cache",
            "copy_hook": f"0x{cache.EXT_COPY_HOOK_ADDR:08X}",
            "copy_hook_size": len(cache.build_copy_hook()),
            "copy_dispatch": f"0x{split.COPY_HOOK_ADDR:08X}",
            "copy_dispatch_size": len(cache.build_copy_dispatch()),
            "sync_1x1_body": f"0x{cache.SYNC_1X1_BODY_ADDR:08X}",
            "sync_1x1_body_size": len(cache.build_sync_1x1_body()),
            "note": "Synchronous 1x1 page cache plus runtime-validated synchronous 1x2 dual-slot cache.",
        },
        "text_writeback": {
            "preview": args.preview,
            "row_count": len(text_records),
            "excluded_source_files": excluded_text_counts,
            "code_table": args.code_table,
            "validation": text_validation,
        },
        "menu_writeback": {
            "translations": args.menu_translations,
            "row_count": len(menu_records),
        },
        "records": {
            "text_samples": text_records if not args.compact_records else [],
            "menu_samples": menu_records if not args.compact_records else [],
        },
    }
    return work, output_rom, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full text writeback ROM with overlay menu translations.")
    parser.add_argument("--origin-work", default="rom/unpacked/origin")
    parser.add_argument("--preview", default="text/writeback/encoded_preview.tsv")
    parser.add_argument("--menu-translations", default="text/menu/overlay_menu_translations.tsv")
    parser.add_argument("--font-dir", default="plan/cache/text-writeback-smoke/font-build-smoke-sjis-code-table")
    parser.add_argument("--code-table", default="text/code_table/zh_code_table.tsv")
    parser.add_argument("--candidate-code-endian", choices=("big", "little"), default="big")
    parser.add_argument("--work", default="rom/unpacked/narutorpg3_chs_full_writeback_menu_v1")
    parser.add_argument("--output", default="rom/narutorpg3_chs_full_writeback_menu_v1.nds")
    parser.add_argument("--records-out", default="plan/cache/text-writeback-smoke/full-writeback-menu-v1-records.json")
    parser.add_argument(
        "--exclude-source-files",
        default=",".join(sorted(text_rom.DEFAULT_EXCLUDED_SOURCE_FILES)),
        help="Comma-separated text source_file values to leave unmodified.",
    )
    parser.add_argument("--compact-records", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work, output_rom, metadata = build(args)
    records_path = Path(args.records_out)
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"work={work}")
    print(f"output_rom={output_rom}")
    print(f"records={records_path}")
    print(f"text_rows={metadata['text_writeback']['row_count']}")
    print(f"menu_rows={metadata['menu_writeback']['row_count']}")
    print(f"copy_hook_size=0x{metadata['font_cache_strategy']['copy_hook_size']:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
