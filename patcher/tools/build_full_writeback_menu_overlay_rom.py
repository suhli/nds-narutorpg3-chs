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


OVERLAY_0002_TEMPLATE_RANGE = (0x12C80, 0x12DB0)

OVERLAY_0002_VISIBLE_TEXT_PATCHES = (
    (
        "item_get_haitteita_suffix",
        "\u306f\u3044\u3063\u3066\u3044\u305f\uff01",
        "\u83b7\u5f97\u4e86\uff01",
    ),
    (
        "item_get_tenireta_suffix",
        "\u3066\u306b\u3044\u308c\u305f\uff01",
        "\u83b7\u5f97\u4e86\uff01",
    ),
    (
        "item_full_warning",
        "\u3082\u3061\u3082\u306e\u304c\u3000\u3044\u3063\u3071\u3044\u3067\u3059\uff01",
        "\u9053\u5177\u5df2\u6ee1\uff01",
    ),
)

OVERLAY_0002_RAW_PATCHES = (
    (
        "item_get_particle_ga_after_percent_s",
        bytes.fromhex("25 73 82 AA"),
        bytes.fromhex("25 73 81 40"),
    ),
    (
        "item_get_particle_wo_after_percent_s",
        bytes.fromhex("25 73 82 F0"),
        bytes.fromhex("25 73 81 40"),
    ),
)


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


def replace_all_in_range(data: bytearray, start: int, end: int, source: bytes, replacement: bytes) -> int:
    if len(source) != len(replacement):
        raise ValueError("overlay template patch must preserve byte length")
    count = 0
    pos = start
    while True:
        index = data.find(source, pos, end)
        if index < 0:
            return count
        data[index : index + len(source)] = replacement
        count += 1
        pos = index + len(replacement)


def fixed_visible_overlay_text(
    text: str,
    width: int,
    code_table: dict[str, int],
    *,
    candidate_code_endian: str,
) -> bytes:
    encoded = text_rom.encode_text(text, code_table, candidate_code_endian=candidate_code_endian)
    if len(encoded) > width:
        raise ValueError(f"overlay template text {text!r} exceeds width {width}")
    return encoded + text_rom.message_padding(width - len(encoded))


def patch_overlay_message_templates(
    work: Path,
    code_table: dict[str, int],
    *,
    candidate_code_endian: str,
) -> list[dict[str, Any]]:
    target = work / "overlay" / "overlay_0002.bin"
    if not target.is_file():
        raise FileNotFoundError(target)
    data = bytearray(target.read_bytes())
    start, end = OVERLAY_0002_TEMPLATE_RANGE
    records: list[dict[str, Any]] = []

    for patch_id, source, replacement in OVERLAY_0002_RAW_PATCHES:
        count = replace_all_in_range(data, start, end, source, replacement)
        records.append(
            {
                "id": patch_id,
                "source_file": "overlay/overlay_0002.bin",
                "range": [f"0x{start:X}", f"0x{end:X}"],
                "replacement_count": count,
                "strategy": "fixed_binary_template_raw_replace",
                "source_hex": source.hex(" ").upper(),
                "replacement_hex": replacement.hex(" ").upper(),
            }
        )

    for patch_id, source_text, zh_text in OVERLAY_0002_VISIBLE_TEXT_PATCHES:
        source = source_text.encode("cp932")
        replacement = fixed_visible_overlay_text(
            zh_text,
            len(source),
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        count = replace_all_in_range(data, start, end, source, replacement)
        records.append(
            {
                "id": patch_id,
                "source_file": "overlay/overlay_0002.bin",
                "range": [f"0x{start:X}", f"0x{end:X}"],
                "jp_text": source_text,
                "zh_text": zh_text,
                "replacement_count": count,
                "strategy": "fixed_binary_template_visible_text_replace",
                "source_hex": source.hex(" ").upper(),
                "replacement_hex": replacement.hex(" ").upper(),
            }
        )

    if sum(record["replacement_count"] for record in records) == 0:
        raise ValueError("overlay_0002 item-get template patch did not match any bytes")
    target.write_bytes(data)
    return records


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
        compact_message_terminators=args.compact_message_terminators,
        early_message_terminator_fullwidth_fill=args.early_message_terminator_fullwidth_fill,
        early_message_terminator_zero_fill=args.early_message_terminator_zero_fill,
        event_script_early_message_terminator_fullwidth_fill=args.event_script_early_message_terminator_fullwidth_fill,
        control_slot_final_message_terminator_fullwidth_fill=args.control_slot_final_message_terminator_fullwidth_fill,
    )

    cache.patch_arm9(work / "arm9.bin")
    cache.patch_overlay(work / "overlay" / "overlay_0000.bin")

    menu_rows = read_rows(repo / args.menu_translations)
    menu_records = patch_menu_rows(work, menu_rows)
    overlay_template_records = patch_overlay_message_templates(
        work,
        code_table,
        candidate_code_endian=args.candidate_code_endian,
    )
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
            "compact_message_terminators": args.compact_message_terminators,
            "early_message_terminator_fullwidth_fill": args.early_message_terminator_fullwidth_fill,
            "early_message_terminator_zero_fill": args.early_message_terminator_zero_fill,
            "event_script_early_message_terminator_fullwidth_fill": args.event_script_early_message_terminator_fullwidth_fill,
            "control_slot_final_message_terminator_fullwidth_fill": args.control_slot_final_message_terminator_fullwidth_fill,
            "compacted_row_count": sum(1 for record in text_records if record.get("message_compacted_removed_len", 0) > 0),
            "compacted_removed_bytes": sum(record.get("message_compacted_removed_len", 0) for record in text_records),
            "early_03_fullwidth_fill_row_count": sum(
                1
                for record in text_records
                if record.get("message_padding_strategy") == "early_03_fullwidth_fill_after_terminator"
            ),
            "early_03_fullwidth_fill_bytes": sum(
                record.get("message_post_terminator_padding_len", 0)
                for record in text_records
                if record.get("message_padding_strategy") == "early_03_fullwidth_fill_after_terminator"
            ),
            "early_03_zero_fill_row_count": sum(
                1
                for record in text_records
                if record.get("message_padding_strategy") == "early_03_zero_fill_after_terminator"
            ),
            "early_03_zero_fill_bytes": sum(
                record.get("message_post_terminator_padding_len", 0)
                for record in text_records
                if record.get("message_padding_strategy") == "early_03_zero_fill_after_terminator"
            ),
            "event_script_early_03_fullwidth_fill_row_count": sum(
                1
                for record in text_records
                if record.get("message_padding_strategy") == "event_script_early_03_fullwidth_fill_after_terminator"
            ),
            "event_script_early_03_fullwidth_fill_bytes": sum(
                record.get("message_post_terminator_padding_len", 0)
                for record in text_records
                if record.get("message_padding_strategy") == "event_script_early_03_fullwidth_fill_after_terminator"
            ),
            "event_script_fixed_control_final_03_fullwidth_fill_row_count": sum(
                1
                for record in text_records
                if record.get("message_padding_strategy")
                == "event_script_fixed_control_final_03_fullwidth_fill_after_terminator"
            ),
            "event_script_fixed_control_final_03_fullwidth_fill_bytes": sum(
                record.get("message_post_terminator_padding_len", 0)
                for record in text_records
                if record.get("message_padding_strategy")
                == "event_script_fixed_control_final_03_fullwidth_fill_after_terminator"
            ),
            "fixed_control_final_03_fullwidth_fill_row_count": sum(
                1
                for record in text_records
                if record.get("message_padding_strategy") == "fixed_control_final_03_fullwidth_fill_after_terminator"
            ),
            "fixed_control_final_03_fullwidth_fill_bytes": sum(
                record.get("message_post_terminator_padding_len", 0)
                for record in text_records
                if record.get("message_padding_strategy") == "fixed_control_final_03_fullwidth_fill_after_terminator"
            ),
            "fixed_subslot_final_03_fullwidth_fill_row_count": sum(
                1
                for record in text_records
                if record.get("message_padding_strategy") == "fixed_subslot_final_03_fullwidth_fill_after_terminator"
            ),
            "fixed_subslot_final_03_fullwidth_fill_bytes": sum(
                record.get("message_post_terminator_padding_len", 0)
                for record in text_records
                if record.get("message_padding_strategy") == "fixed_subslot_final_03_fullwidth_fill_after_terminator"
            ),
        },
        "menu_writeback": {
            "translations": args.menu_translations,
            "row_count": len(menu_records),
        },
        "overlay_template_writeback": {
            "row_count": len(overlay_template_records),
            "replacement_count": sum(record["replacement_count"] for record in overlay_template_records),
        },
        "records": {
            "text_samples": text_records if not args.compact_records else [],
            "menu_samples": menu_records if not args.compact_records else [],
            "overlay_template_samples": overlay_template_records if not args.compact_records else [],
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
    parser.add_argument(
        "--compact-message-terminators",
        action="store_true",
        help="Compact ordinary 03 00 message streams by deleting padding before the terminator.",
    )
    parser.add_argument(
        "--early-message-terminator-fullwidth-fill",
        action="store_true",
        help="Move ordinary 03 00 message terminators after text and fill the original slot with fullwidth spaces.",
    )
    parser.add_argument(
        "--early-message-terminator-zero-fill",
        action="store_true",
        help="Move ordinary 03 00 message terminators after text and fill the original slot with 00 bytes.",
    )
    parser.add_argument(
        "--event-script-early-message-terminator-fullwidth-fill",
        action="store_true",
        help="Move event-script 03 00 message terminators after text and keep fixed length with fullwidth-space tail padding.",
    )
    parser.add_argument(
        "--control-slot-final-message-terminator-fullwidth-fill",
        action="store_true",
        help="Move final 03 00 terminators after final fixed control/subslot text and keep fixed length with fullwidth-space tail padding.",
    )
    args = parser.parse_args()
    message_terminator_modes = [
        args.compact_message_terminators,
        args.early_message_terminator_fullwidth_fill,
        args.early_message_terminator_zero_fill,
    ]
    if sum(1 for enabled in message_terminator_modes if enabled) > 1:
        parser.error("message terminator rewrite modes are mutually exclusive")
    return args


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
