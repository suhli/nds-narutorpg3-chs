from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


CTRL_RE = re.compile(r"\{CTRL_([0-9A-Fa-f]{4})\}")
LEADING_CTRL_RUN_RE = re.compile(r"^((?:\{CTRL_[0-9A-Fa-f]{4}\})+)(.*)$", re.S)
OPEN_QUOTES = ("\u300c", "\u300e", "\u201c", '"')

SOURCE_TEXT_OVERRIDES = {
    "zh_txt_6b929156_0006CE_0023": "\u300c\u304a\u307e\u3048\u3089\u306b\u306f\u3000\u304b\u3093\u3051\u3044\u3000\u306a\u3044\u3000\u3053\u3068\u3060\uff01{CTRL_0001}{CTRL_0101}{CTRL_0050}\u3072\u3063\u3053\u3093\u3067\u308d\uff01\u300d",
}
DEFAULT_EXCLUDED_SOURCE_FILES = {
    "msg/wifi/friend_msg.msg",
    "msg/wifi/kinshi_msg.msg",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def parse_hex_bytes(value: str) -> bytes:
    value = (value or "").strip()
    if not value:
        return b""
    return bytes(int(part, 16) for part in value.split())


def format_hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def normalize_source_file(value: str) -> str:
    return value.replace("\\", "/").lower()


def parse_source_file_set(value: str) -> set[str]:
    return {normalize_source_file(part.strip()) for part in value.split(",") if part.strip()}


def is_sjis_lead(byte: int) -> bool:
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC


def is_sjis_trail(byte: int) -> bool:
    return (0x40 <= byte <= 0x7E) or (0x80 <= byte <= 0xFC)


def decode_payload(data: bytes) -> str:
    out: list[str] = []
    index = 0
    while index < len(data):
        byte = data[index]
        if byte < 0x20:
            if index + 1 < len(data):
                value = byte | (data[index + 1] << 8)
                out.append(f"{{CTRL_{value:04X}}}")
                index += 2
            else:
                out.append(f"{{CTRL_{byte:02X}}}")
                index += 1
            continue
        if is_sjis_lead(byte) and index + 1 < len(data) and is_sjis_trail(data[index + 1]):
            out.append(data[index : index + 2].decode("cp932", errors="replace"))
            index += 2
            continue
        out.append(bytes([byte]).decode("cp932", errors="replace"))
        index += 1
    return "".join(out)


def trim_terminator(raw: bytes, terminator: bytes) -> bytes:
    if terminator and raw.endswith(terminator):
        return raw[: -len(terminator)]
    return raw


def adjusted_source(row: dict[str, str]) -> dict[str, Any]:
    raw = parse_hex_bytes(row.get("raw_hex", ""))
    terminator = parse_hex_bytes(row.get("raw_terminator_hex", ""))
    payload = trim_terminator(raw, terminator)
    prefix = b""
    strategy = "plain_payload"
    adjusted_jp_text = row.get("jp_text", "")
    quote_pos = payload.find(b"\x81\x75")
    if (
        row.get("category") == "message"
        and terminator == b"\x03\x00"
        and quote_pos > 0
    ):
        prefix = payload[:quote_pos]
        payload = payload[quote_pos:]
        strategy = "strip_prefix_before_open_quote"
        adjusted_jp_text = strip_leading_structure_text(adjusted_jp_text)
        if adjusted_jp_text and not adjusted_jp_text.startswith(OPEN_QUOTES):
            adjusted_jp_text = "\u300c" + adjusted_jp_text
        exact_jp_text = decode_payload(payload)
        translated_text = strip_leading_structure_text(
            row.get("zh_text_candidate_payload", "") or row.get("zh_text_raw", "")
        )
        if exact_jp_text.startswith("\u300c") and translated_text and not translated_text.startswith(OPEN_QUOTES):
            translated_text = "\u300c" + translated_text
        if tokens_from_text(translated_text) == tokens_from_text(exact_jp_text):
            adjusted_jp_text = exact_jp_text
            strategy = "strip_prefix_before_open_quote_exact_body_controls"
    elif (
        row.get("category") == "message"
        and terminator == b"\x03\x00"
        and len(payload) >= 4
        and payload[1] == 0
        and is_sjis_lead(payload[2])
        and is_sjis_trail(payload[3])
    ):
        prefix = payload[:2]
        payload = payload[2:]
        strategy = "strip_prefix_before_sjis_text"
        adjusted_jp_text = decode_payload(payload)
    return {
        "strategy": strategy,
        "prefix": prefix,
        "prefix_len": len(prefix),
        "prefix_text": decode_payload(prefix),
        "adjusted_payload": payload,
        "adjusted_jp_text": adjusted_jp_text,
        "terminator": terminator,
        "source_len": int(row.get("source_byte_len") or len(raw)),
    }


def tokens_from_text(text: str) -> list[str]:
    return [f"CTRL_{int(match.group(1), 16):04X}" for match in CTRL_RE.finditer(text or "")]


def strip_leading_structure_text(text: str) -> str:
    out = (text or "").strip()
    changed = True
    while changed:
        changed = False
        match = LEADING_CTRL_RUN_RE.match(out)
        if match:
            out = match.group(2)
            changed = True
        while out and ord(out[0]) < 0x80 and out[0] not in "{\u300c\u300e\u201c\"":
            out = out[1:]
            changed = True
    return out


def adjusted_translation(row: dict[str, str], source_info: dict[str, Any]) -> tuple[str, list[str]]:
    before = row.get("zh_text_candidate_payload", "") or row.get("zh_text_raw", "")
    after = before
    changes: list[str] = []
    if source_info["strategy"].startswith("strip_prefix_before_open_quote"):
        stripped = strip_leading_structure_text(after)
        if stripped != after:
            after = stripped
            changes.append("strip_leading_structure_residue")
    source_text = source_info["adjusted_jp_text"]
    if source_text.startswith("\u300c") and after and not after.startswith(OPEN_QUOTES):
        after = "\u300c" + after
        changes.append("add_open_quote")
    return after, changes


def remove_extra_control_tokens(text: str, expected_tokens: list[str]) -> tuple[str, list[str]]:
    matches = list(CTRL_RE.finditer(text or ""))
    actual = [f"CTRL_{int(match.group(1), 16):04X}" for match in matches]
    if not matches or actual == expected_tokens:
        return text, []

    keep_indexes: list[int] = []
    search_from = 0
    for expected in expected_tokens:
        found = -1
        for index in range(search_from, len(actual)):
            if actual[index] == expected:
                found = index
                break
        if found < 0:
            return text, []
        keep_indexes.append(found)
        search_from = found + 1

    keep = set(keep_indexes)
    remove_ranges = [
        (matches[index].start(), matches[index].end())
        for index in range(len(matches))
        if index not in keep
    ]
    if not remove_ranges:
        return text, []

    out_parts: list[str] = []
    pos = 0
    for start, end in remove_ranges:
        out_parts.append(text[pos:start])
        pos = end
    out_parts.append(text[pos:])
    return "".join(out_parts), [f"remove_extra_control_tokens:{len(remove_ranges)}"]


def load_code_table(path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for row in read_tsv(path):
        char = row.get("char", "")
        code_hex = row.get("code_hex", "")
        if char and code_hex:
            mapping[char] = int(code_hex, 16)
    return mapping


def load_manual_overrides(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    overrides: dict[str, str] = {}
    for row in read_tsv(path):
        row_id = row.get("id", "").strip()
        zh_text = row.get("zh_text", "")
        if row_id:
            overrides[row_id] = zh_text
    return overrides


def encode_text(text: str, code_table: dict[str, int], *, candidate_code_endian: str) -> tuple[bytes, list[str]]:
    encoded = bytearray()
    missing: list[str] = []
    pos = 0
    for match in CTRL_RE.finditer(text or ""):
        seg_bytes, seg_missing = encode_plain_text(
            text[pos : match.start()],
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        encoded.extend(seg_bytes)
        missing.extend(seg_missing)
        encoded.extend(int(match.group(1), 16).to_bytes(2, "little"))
        pos = match.end()
    seg_bytes, seg_missing = encode_plain_text(
        (text or "")[pos:],
        code_table,
        candidate_code_endian=candidate_code_endian,
    )
    encoded.extend(seg_bytes)
    missing.extend(seg_missing)
    return bytes(encoded), missing


def encode_plain_text(text: str, code_table: dict[str, int], *, candidate_code_endian: str) -> tuple[bytes, list[str]]:
    encoded = bytearray()
    missing: list[str] = []
    for char in text:
        if char in code_table:
            encoded.extend(code_table[char].to_bytes(2, candidate_code_endian))
            continue
        if 0x20 <= ord(char) <= 0x7E:
            encoded.append(ord(char))
            continue
        try:
            encoded.extend(char.encode("cp932"))
        except UnicodeEncodeError:
            missing.append(char)
    return bytes(encoded), missing


def capacity_for_row(row: dict[str, str], source_info: dict[str, Any]) -> int:
    source_len = source_info["source_len"]
    terminator_len = len(source_info["terminator"])
    prefix_len = int(source_info["prefix_len"])
    if terminator_len:
        return source_len - prefix_len - terminator_len
    return source_len - prefix_len


def audit_rows(
    rows: list[dict[str, str]],
    *,
    code_table: dict[str, int],
    candidate_code_endian: str,
    excluded_source_files: set[str],
    manual_overrides: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    issue_rows: list[dict[str, Any]] = []
    adjusted_rows: list[dict[str, str]] = []
    counters: Counter[str] = Counter()
    issue_counters: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()

    for row in rows:
        row = dict(row)
        source_file = normalize_source_file(row.get("source_file", ""))
        if source_file in excluded_source_files:
            excluded_counts[source_file] += 1
            adjusted_rows.append(row)
            counters["excluded"] += 1
            continue

        counters["checked"] += 1
        source_info = adjusted_source(row)
        source_override = SOURCE_TEXT_OVERRIDES.get(row.get("id", ""))
        if source_override:
            source_info = {**source_info, "adjusted_jp_text": source_override}
        expected_tokens = tokens_from_text(source_info["adjusted_jp_text"])
        before_text = row.get("zh_text_candidate_payload", "") or row.get("zh_text_raw", "")
        override_text = manual_overrides.get(row.get("id", ""))
        if override_text is not None:
            before_text = override_text
        before_tokens = tokens_from_text(before_text)
        after_text, changes = adjusted_translation(row, source_info)
        if override_text is not None:
            after_text = override_text
            changes.append("manual_override")
        control_fixed_text, control_changes = remove_extra_control_tokens(after_text, expected_tokens)
        if control_changes:
            after_text = control_fixed_text
            changes.extend(control_changes)
        after_tokens = tokens_from_text(after_text)
        encoded, missing = encode_text(after_text, code_table, candidate_code_endian=candidate_code_endian)
        capacity = capacity_for_row(row, source_info)

        issues: list[str] = []
        if source_info["prefix_len"]:
            counters["structure_prefix_rows"] += 1
            if changes:
                issues.append("auto_adjusted_structure_residue")
        if control_changes:
            issues.append("auto_adjusted_extra_control_tokens")
        if before_tokens != expected_tokens:
            issues.append("control_tokens_before_mismatch")
        if after_tokens != expected_tokens:
            issues.append("control_tokens_after_mismatch")
        if missing:
            issues.append("missing_code_table_or_cp932_chars")
        if len(encoded) > capacity:
            issues.append("encoded_overflow_after_adjust")
        if source_info["adjusted_jp_text"].startswith("\u300c") and after_text and not after_text.startswith(OPEN_QUOTES):
            issues.append("opening_quote_missing_after_adjust")

        if changes:
            counters["auto_adjusted_rows"] += 1
        if override_text is not None:
            counters["manual_override_rows"] += 1
        if before_tokens != expected_tokens:
            counters["before_control_mismatch_rows"] += 1
        if after_tokens != expected_tokens:
            counters["after_control_mismatch_rows"] += 1
        if missing:
            counters["missing_char_rows"] += 1
        if len(encoded) > capacity:
            counters["overflow_rows"] += 1

        for issue in issues:
            issue_counters[issue] += 1

        row["zh_text_candidate_payload"] = after_text
        row["zh_text_raw"] = after_text
        row["encoded_hex_candidate"] = format_hex(encoded)
        row["encoded_len_candidate"] = str(len(encoded))
        row["payload_capacity"] = str(capacity)
        row["capacity_delta"] = str(capacity - len(encoded))
        row["encoded_complete"] = "no" if missing or len(encoded) > capacity else "yes"
        row["control_tokens_expected"] = " ".join(expected_tokens)
        row["control_tokens_in_zh"] = " ".join(after_tokens)
        adjusted_rows.append(row)

        if issues:
            issue_rows.append(
                {
                    "id": row.get("id", ""),
                    "jp_id_ref": row.get("jp_id_ref", ""),
                    "category": row.get("category", ""),
                    "source_file": row.get("source_file", ""),
                    "offset": row.get("offset", ""),
                    "record_index": row.get("record_index", ""),
                    "chunk_id": row.get("chunk_id", ""),
                    "issues": " ".join(issues),
                    "auto_changes": " ".join(changes),
                    "strategy": source_info["strategy"],
                    "prefix_len": source_info["prefix_len"],
                    "prefix_hex": format_hex(source_info["prefix"]),
                    "prefix_text": source_info["prefix_text"],
                    "expected_tokens": " ".join(expected_tokens),
                    "tokens_before": " ".join(before_tokens),
                    "tokens_after": " ".join(after_tokens),
                    "encoded_len_after": len(encoded),
                    "payload_capacity_after": capacity,
                    "capacity_delta_after": capacity - len(encoded),
                    "missing_chars": "".join(dict.fromkeys(missing)),
                    "adjusted_jp_text": source_info["adjusted_jp_text"],
                    "zh_text_before": before_text,
                    "zh_text_after": after_text,
                }
            )

    report = {
        "input_rows": len(rows),
        "checked_rows": counters["checked"],
        "excluded_counts": dict(excluded_counts),
        "issue_rows": len(issue_rows),
        "auto_adjusted_rows": counters["auto_adjusted_rows"],
        "structure_prefix_rows": counters["structure_prefix_rows"],
        "before_control_mismatch_rows": counters["before_control_mismatch_rows"],
        "after_control_mismatch_rows": counters["after_control_mismatch_rows"],
        "missing_char_rows": counters["missing_char_rows"],
        "overflow_rows": counters["overflow_rows"],
        "manual_override_rows": counters["manual_override_rows"],
        "issue_counts": dict(issue_counters),
    }
    return issue_rows, adjusted_rows, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit struct-safe translation/control-token alignment.")
    parser.add_argument("--preview", default="text/writeback/encoded_preview.tsv")
    parser.add_argument("--code-table", default="text/code_table/zh_code_table.tsv")
    parser.add_argument("--candidate-code-endian", choices=("big", "little"), default="big")
    parser.add_argument(
        "--exclude-source-files",
        default=",".join(sorted(DEFAULT_EXCLUDED_SOURCE_FILES)),
        help="Comma-separated source_file values skipped by the current full writeback build.",
    )
    parser.add_argument("--report-json", default="plan/cache/text-writeback-smoke/translation-struct-audit-report.json")
    parser.add_argument("--issues-tsv", default="plan/cache/text-writeback-smoke/translation-struct-mismatches.tsv")
    parser.add_argument("--adjusted-preview", default="plan/cache/text-writeback-smoke/encoded-preview-struct-adjusted.tsv")
    parser.add_argument("--manual-overrides", default="plan/cache/text-writeback-smoke/translation-struct-manual-overrides.tsv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preview_path = Path(args.preview)
    rows = read_tsv(preview_path)
    code_table = load_code_table(Path(args.code_table))
    issue_rows, adjusted_rows, report = audit_rows(
        rows,
        code_table=code_table,
        candidate_code_endian=args.candidate_code_endian,
        excluded_source_files=parse_source_file_set(args.exclude_source_files),
        manual_overrides=load_manual_overrides(Path(args.manual_overrides)),
    )

    issues_path = Path(args.issues_tsv)
    issue_fields = [
        "id",
        "jp_id_ref",
        "category",
        "source_file",
        "offset",
        "record_index",
        "chunk_id",
        "issues",
        "auto_changes",
        "strategy",
        "prefix_len",
        "prefix_hex",
        "prefix_text",
        "expected_tokens",
        "tokens_before",
        "tokens_after",
        "encoded_len_after",
        "payload_capacity_after",
        "capacity_delta_after",
        "missing_chars",
        "adjusted_jp_text",
        "zh_text_before",
        "zh_text_after",
    ]
    write_tsv(issues_path, issue_rows, issue_fields)

    adjusted_path = Path(args.adjusted_preview)
    fieldnames = list(rows[0].keys()) if rows else []
    write_tsv(adjusted_path, adjusted_rows, fieldnames)

    report_path = Path(args.report_json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report.update(
        {
            "preview": args.preview,
            "code_table": args.code_table,
            "candidate_code_endian": args.candidate_code_endian,
            "issues_tsv": args.issues_tsv,
            "adjusted_preview": args.adjusted_preview,
            "manual_overrides": args.manual_overrides,
        }
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"checked={report['checked_rows']} excluded={sum(report['excluded_counts'].values())}")
    print(f"issue_rows={report['issue_rows']} auto_adjusted={report['auto_adjusted_rows']}")
    print(f"after_control_mismatch={report['after_control_mismatch_rows']} overflow={report['overflow_rows']} missing={report['missing_char_rows']}")
    print(f"issues={issues_path}")
    print(f"adjusted_preview={adjusted_path}")
    print(f"report={report_path}")
    return 1 if report["after_control_mismatch_rows"] or report["overflow_rows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
