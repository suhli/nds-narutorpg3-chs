from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import build_full_writeback_menu_overlay_rom as menu_rom
import build_text_writeback_smoke_rom as text_rom


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "risk_type",
        "severity",
        "id",
        "source_file",
        "offset",
        "source_kind",
        "strategy",
        "encoded_len",
        "raw_len",
        "slot_len",
        "padding_len",
        "details",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def add_risk(
    risks: list[dict[str, Any]],
    *,
    risk_type: str,
    severity: str,
    row: dict[str, str],
    source_kind: str,
    strategy: str = "",
    encoded_len: int = 0,
    raw_len: int = 0,
    slot_len: int = 0,
    padding_len: int = 0,
    details: str = "",
) -> None:
    risks.append(
        {
            "risk_type": risk_type,
            "severity": severity,
            "id": row.get("id", ""),
            "source_file": row.get("source_file", ""),
            "offset": row.get("offset", ""),
            "source_kind": source_kind,
            "strategy": strategy,
            "encoded_len": encoded_len,
            "raw_len": raw_len,
            "slot_len": slot_len,
            "padding_len": padding_len,
            "details": details,
        }
    )


def visible_ascii_outside_controls(row: dict[str, str], text: str) -> str:
    suffix = text_rom.ASCII_PRESERVE_SUFFIXES.get(row.get("id", ""))
    if suffix and text.endswith(suffix):
        text = text[: -len(suffix)]

    chars: list[str] = []
    pos = 0
    for match in text_rom.CTRL_RE.finditer(text or ""):
        chars.extend(char for char in text[pos : match.start()] if 0x20 <= ord(char) <= 0x7E)
        pos = match.end()
    chars.extend(char for char in (text or "")[pos:] if 0x20 <= ord(char) <= 0x7E)
    return "".join(chars)


def audit_text_rows(
    preview_path: Path,
    code_table_path: Path,
    excluded_source_files: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows, excluded_counts = text_rom.load_all_rows(preview_path, excluded_source_files)
    code_table = text_rom.load_code_table(code_table_path)
    risks: list[dict[str, Any]] = []
    strategy_counts: Counter[str] = Counter()
    source_strategy_counts: dict[str, Counter[str]] = defaultdict(Counter)
    fixed_subslot_rows: list[dict[str, Any]] = []
    early_03_rows: list[dict[str, Any]] = []
    early_nul4_rows: list[dict[str, Any]] = []
    fullwidth_message_padding_rows = 0
    preserved_ascii_suffix_rows = 0

    for row in rows:
        source_file = text_rom.normalize_source_file(row.get("source_file", ""))
        raw = text_rom.parse_hex_bytes(row.get("raw_hex", ""))
        raw_terminator = text_rom.parse_hex_bytes(row.get("raw_terminator_hex", ""))
        try:
            encoded, terminator, replacement, extra = text_rom.make_replacement(
                row,
                code_table=code_table,
                candidate_code_endian=row.get("candidate_code_endian") or "big",
            )
        except Exception as exc:  # pragma: no cover - report-only path
            add_risk(
                risks,
                risk_type="text_replacement_exception",
                severity="error",
                row=row,
                source_kind="text",
                details=str(exc),
            )
            continue

        normalized_text = text_rom.normalized_message_text(row)
        visible_ascii = visible_ascii_outside_controls(row, normalized_text)
        if visible_ascii:
            add_risk(
                risks,
                risk_type="text_visible_ascii_after_normalization",
                severity="high",
                row=row,
                source_kind="text",
                strategy="normalized_message_text",
                encoded_len=len(encoded),
                raw_len=len(raw),
                padding_len=max(0, len(replacement) - len(encoded) - len(terminator)),
                details=f"visible ASCII outside controls: {visible_ascii}",
            )
        suffix = text_rom.ASCII_PRESERVE_SUFFIXES.get(row.get("id", ""))
        if suffix and normalized_text.endswith(suffix):
            preserved_ascii_suffix_rows += 1

        strategy = (
            extra.get("fixed_slot_strategy")
            or extra.get("message_stream_strategy")
            or extra.get("padding_strategy")
            or "default"
        )
        padding_strategy = (
            extra.get("message_padding_strategy")
            or extra.get("padding_strategy")
            or extra.get("fixed_subslot_padding_strategy")
            or ""
        )
        strategy_counts[str(strategy)] += 1
        source_strategy_counts[source_file][str(strategy)] += 1

        padding_len = max(0, len(replacement) - len(encoded) - len(terminator))
        if padding_strategy == "fullwidth_space_fill_before_original_terminator":
            fullwidth_message_padding_rows += 1

        if extra.get("fixed_slot_strategy") == "preserve_ctrl_0000_subslot_offsets":
            fixed_subslot_rows.append(
                {
                    "id": row["id"],
                    "source_file": row["source_file"],
                    "offset": row["offset"],
                    "subslot_count": len(extra.get("fixed_subslots", [])),
                    "padding_len": sum(slot.get("padding_len", 0) for slot in extra.get("fixed_subslots", [])),
                }
            )

        if extra.get("message_padding_strategy") == "early_03_zero_fill_after_terminator":
            early_03_rows.append({"id": row["id"], "source_file": row["source_file"], "offset": row["offset"]})

        if extra.get("padding_strategy") == "early_nul4_zero_fill":
            early_nul4_rows.append({"id": row["id"], "source_file": row["source_file"], "offset": row["offset"]})

        if (
            row.get("category") == "message"
            and "{CTRL_0000}" in row.get("jp_text", "")
            and (source_file.startswith("msg/menu/") or source_file.startswith("msg/wifi/"))
            and source_file not in text_rom.FIXED_SUBSLOT_SOURCE_FILES
        ):
            add_risk(
                risks,
                risk_type="ui_ctrl0000_not_fixed_subslot",
                severity="high",
                row=row,
                source_kind="text",
                strategy=str(strategy),
                encoded_len=len(encoded),
                raw_len=len(raw),
                padding_len=padding_len,
                details="UI or Wi-Fi message contains CTRL_0000 but is not in FIXED_SUBSLOT_SOURCE_FILES",
            )

        if (
            row.get("category") == "message"
            and raw_terminator == b"\x03\x00"
            and (source_file.startswith("msg/menu/") or source_file.startswith("msg/wifi/"))
            and extra.get("fixed_slot_strategy") != "preserve_ctrl_0000_subslot_offsets"
            and not text_rom.should_end_message_after_text(row, b"\x03\x00")
            and padding_len > 0
        ):
            add_risk(
                risks,
                risk_type="ui_03_not_early_terminated",
                severity="medium",
                row=row,
                source_kind="text",
                strategy=str(strategy),
                encoded_len=len(encoded),
                raw_len=len(raw),
                padding_len=padding_len,
                details="UI or Wi-Fi message keeps fullwidth padding before original 03 00 terminator",
            )

        if (
            row.get("category") == "message"
            and raw.endswith(text_rom.NUL4_TERMINATOR)
            and (source_file.startswith("msg/menu/") or source_file.startswith("msg/wifi/"))
            and source_file not in text_rom.EARLY_NUL4_TERMINATOR_SOURCE_FILES
            and extra.get("padding_strategy") == "fullwidth_space_before_original_nul4_terminator"
        ):
            add_risk(
                risks,
                risk_type="ui_nul4_fullwidth_padding_preserved",
                severity="medium",
                row=row,
                source_kind="text",
                strategy=str(strategy),
                encoded_len=len(encoded),
                raw_len=len(raw),
                padding_len=padding_len,
                details="UI or Wi-Fi NUL4 row still preserves fullwidth padding before original terminator",
            )

    return (
        {
            "selected_rows": len(rows),
            "excluded_source_file_counts": dict(excluded_counts),
            "strategy_counts": dict(strategy_counts),
            "source_strategy_counts": {key: dict(value) for key, value in sorted(source_strategy_counts.items())},
            "fixed_subslot_row_count": len(fixed_subslot_rows),
            "fixed_subslot_rows_by_source": dict(Counter(row["source_file"] for row in fixed_subslot_rows)),
            "early_03_row_count": len(early_03_rows),
            "early_03_rows_by_source": dict(Counter(row["source_file"] for row in early_03_rows)),
            "early_nul4_row_count": len(early_nul4_rows),
            "early_nul4_rows_by_source": dict(Counter(row["source_file"] for row in early_nul4_rows)),
            "fullwidth_message_padding_row_count": fullwidth_message_padding_rows,
            "preserved_ascii_suffix_row_count": preserved_ascii_suffix_rows,
        },
        risks,
    )


def audit_menu_rows(menu_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [row for row in read_tsv(menu_path) if row.get("status") == "ready"]
    risks: list[dict[str, Any]] = []
    strategy_counts: Counter[str] = Counter()
    source_strategy_counts: dict[str, Counter[str]] = defaultdict(Counter)
    fixed_width_rows = 0
    visible_span_rows = 0

    for row in rows:
        raw = menu_rom.parse_hex_bytes(row.get("raw_hex", ""))
        encoded = menu_rom.parse_hex_bytes(row.get("encoded_hex", ""))
        raw_len = int(row.get("raw_len") or len(raw))
        slot_len = int(row.get("slot_len") or raw_len)
        covered_visible_span = menu_rom.should_space_pad_visible_overlay_span(row)
        translation_source = row.get("translation_source", "")
        notes = row.get("notes", "")
        if covered_visible_span:
            strategy = "fullwidth_to_original_visible_len_then_zero"
            visible_span_rows += 1
        elif translation_source == "row_fixed_width_override":
            strategy = "row_fixed_width_override"
            fixed_width_rows += 1
        else:
            strategy = "zero_fill_after_encoded"
        strategy_counts[strategy] += 1
        source_strategy_counts[row.get("source_file", "")][strategy] += 1

        if len(encoded) >= raw_len:
            continue

        raw_has_control_separator = (b"\x00\x00" in raw) or (b"\x01\x00" in raw)
        raw_space_count = raw.count(b"\x81\x40")

        if (
            raw_has_control_separator
            and not covered_visible_span
            and translation_source != "row_fixed_width_override"
            and "manual_null_delimited" not in notes
        ):
            add_risk(
                risks,
                risk_type="overlay_control_delimited_zero_fill_candidate",
                severity="high",
                row=row,
                source_kind="overlay",
                strategy=strategy,
                encoded_len=len(encoded),
                raw_len=raw_len,
                slot_len=slot_len,
                padding_len=slot_len - len(encoded),
                details="overlay row contains 00/01 separators and would zero-fill immediately after encoded text",
            )
        elif (
            raw_space_count >= 3
            and raw_len >= 24
            and translation_source != "row_fixed_width_override"
            and not covered_visible_span
        ):
            add_risk(
                risks,
                risk_type="overlay_fixed_width_spacing_candidate",
                severity="medium",
                row=row,
                source_kind="overlay",
                strategy=strategy,
                encoded_len=len(encoded),
                raw_len=raw_len,
                slot_len=slot_len,
                padding_len=slot_len - len(encoded),
                details=f"overlay row has {raw_space_count} fullwidth spaces and may encode a fixed layout",
            )

    return (
        {
            "ready_rows": len(rows),
            "strategy_counts": dict(strategy_counts),
            "source_strategy_counts": {key: dict(value) for key, value in sorted(source_strategy_counts.items())},
            "visible_span_padding_rows": visible_span_rows,
            "fixed_width_override_rows": fixed_width_rows,
        },
        risks,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit structural risk patterns covered by the v24 writeback rules.")
    parser.add_argument("--preview", default="patcher/resources/text/encoded-preview-struct-adjusted.tsv")
    parser.add_argument("--code-table", default="patcher/resources/text/zh_code_table.tsv")
    parser.add_argument("--menu", default="patcher/resources/menu/overlay_menu_translations.tsv")
    parser.add_argument("--exclude-source-files", default="msg/wifi/kinshi_msg.msg")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--tsv-out", required=True)
    args = parser.parse_args()

    text_summary, text_risks = audit_text_rows(
        Path(args.preview),
        Path(args.code_table),
        text_rom.parse_source_file_set(args.exclude_source_files),
    )
    menu_summary, menu_risks = audit_menu_rows(Path(args.menu))
    risks = text_risks + menu_risks
    risk_counts = Counter(row["risk_type"] for row in risks)
    severity_counts = Counter(row["severity"] for row in risks)

    summary = {
        "text": text_summary,
        "menu": menu_summary,
        "risk_counts": dict(risk_counts),
        "severity_counts": dict(severity_counts),
        "risk_rows": len(risks),
    }
    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_tsv(Path(args.tsv_out), risks)
    print(
        json.dumps(
            {
                "risk_rows": len(risks),
                "risk_counts": dict(risk_counts),
                "severity_counts": dict(severity_counts),
                "json_out": args.json_out,
                "tsv_out": args.tsv_out,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
