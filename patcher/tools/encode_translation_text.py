from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


CTRL_RE = re.compile(r"\{CTRL_([0-9A-Fa-f]{4})\}")
HEX_BYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}$")


PREVIEW_FIELDS = [
    "id",
    "jp_id_ref",
    "category",
    "source_file",
    "offset",
    "record_index",
    "chunk_id",
    "source_byte_len",
    "payload_capacity",
    "raw_payload_len",
    "raw_terminator_hex",
    "jp_text",
    "zh_text_raw",
    "zh_text_candidate_payload",
    "padding_spaces",
    "encoded_hex_candidate",
    "encoded_len_candidate",
    "capacity_delta",
    "encoded_complete",
    "candidate_code_endian",
    "code_endian_evidence",
    "control_tokens_expected",
    "control_tokens_in_zh",
    "control_raw_verdict",
    "control_raw_evidence",
    "visible_ascii_chars",
    "missing_chars",
    "risk_flags",
    "fixed_slot_status",
    "stage2_eligible",
    "pre_endian_candidate",
    "raw_hex",
]


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


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_raw_hex(raw_hex: str) -> bytes:
    parts = [part for part in (raw_hex or "").split() if HEX_BYTE_RE.fullmatch(part)]
    return bytes(int(part, 16) for part in parts)


def parse_capacity(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def format_hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def load_code_table(path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for row in read_tsv(path):
        char = row.get("char", "")
        code_hex = row.get("code_hex", "")
        if not char or not code_hex:
            continue
        mapping[char] = int(code_hex, 16)
    return mapping


def is_sjis_lead(byte: int) -> bool:
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC


def is_sjis_trail(byte: int) -> bool:
    return (0x40 <= byte <= 0x7E) or (0x80 <= byte <= 0xFC)


def summarize_code_byte_shape(code_table: dict[str, int], candidate_code_endian: str) -> dict[str, Any]:
    invalid: list[dict[str, Any]] = []
    zero_byte: list[dict[str, str]] = []
    values = list(code_table.values())
    for char, code in code_table.items():
        raw = code.to_bytes(2, candidate_code_endian)
        if 0 in raw:
            zero_byte.append({"char": char, "code_hex": f"0x{code:04X}", "bytes": format_hex(raw)})
        if not (is_sjis_lead(raw[0]) and is_sjis_trail(raw[1])):
            invalid.append({"char": char, "code_hex": f"0x{code:04X}", "bytes": format_hex(raw)})
    return {
        "entry_count": len(code_table),
        "range": [] if not values else [f"0x{min(values):04X}", f"0x{max(values):04X}"],
        "candidate_code_endian": candidate_code_endian,
        "sjis_shape_invalid_count": len(invalid),
        "zero_byte_count": len(zero_byte),
        "first_invalid": invalid[:20],
        "first_zero_byte": zero_byte[:20],
        "verdict": "sjis_shape_ok" if not invalid and not zero_byte else "unsafe_for_unpatched_sjis_like_parser",
    }


def tokens_from_text(text: str) -> list[str]:
    return [f"CTRL_{int(match.group(1), 16):04X}" for match in CTRL_RE.finditer(text or "")]


def tokens_from_field(text: str) -> list[str]:
    out: list[str] = []
    for token in (text or "").split():
        token = token.strip().upper()
        if not token:
            continue
        if token.startswith("{") and token.endswith("}"):
            token = token[1:-1]
        if token.startswith("CTRL_"):
            out.append(f"CTRL_{int(token[5:], 16):04X}")
    return out


def count_nonoverlapping(data: bytes, needle: bytes) -> int:
    if not needle:
        return 0
    count = 0
    pos = 0
    while True:
        found = data.find(needle, pos)
        if found < 0:
            return count
        count += 1
        pos = found + len(needle)


def verify_control_tokens(raw: bytes, expected_tokens: list[str]) -> tuple[str, str]:
    if not expected_tokens:
        return "not_applicable", ""

    counts = Counter(expected_tokens)
    evidence_parts: list[str] = []
    little_supported = True
    for token, expected_count in sorted(counts.items()):
        value = int(token[5:], 16)
        little = value.to_bytes(2, "little")
        big = value.to_bytes(2, "big")
        little_count = count_nonoverlapping(raw, little)
        big_count = count_nonoverlapping(raw, big)
        if little_count < expected_count:
            little_supported = False
        evidence_parts.append(
            f"{token}:expected={expected_count},le={format_hex(little)}x{little_count},be={format_hex(big)}x{big_count}"
        )

    if little_supported:
        return "candidate_little_endian_raw_hex_supported", "; ".join(evidence_parts)
    return "candidate_little_endian_unverified", "; ".join(evidence_parts)


def visible_ascii_chars(text_without_tokens: str) -> list[str]:
    chars: list[str] = []
    for char in text_without_tokens:
        code = ord(char)
        if 0x20 <= code <= 0x7E:
            chars.append(char)
    return chars


def uniq_join(chars: list[str]) -> str:
    seen: dict[str, None] = {}
    for char in chars:
        seen.setdefault(char, None)
    return "".join(seen.keys())


def encode_payload(
    text: str,
    code_table: dict[str, int],
    candidate_code_endian: str,
) -> tuple[bytes, bool, list[str], list[str]]:
    encoded = bytearray()
    missing: list[str] = []
    ascii_seen: list[str] = []
    complete = True
    pos = 0

    for match in CTRL_RE.finditer(text):
        segment = text[pos : match.start()]
        seg_bytes, seg_complete, seg_missing, seg_ascii = encode_visible_segment(
            segment, code_table, candidate_code_endian
        )
        encoded.extend(seg_bytes)
        complete = complete and seg_complete
        missing.extend(seg_missing)
        ascii_seen.extend(seg_ascii)

        value = int(match.group(1), 16)
        encoded.extend(value.to_bytes(2, "little"))
        pos = match.end()

    tail = text[pos:]
    seg_bytes, seg_complete, seg_missing, seg_ascii = encode_visible_segment(
        tail, code_table, candidate_code_endian
    )
    encoded.extend(seg_bytes)
    complete = complete and seg_complete
    missing.extend(seg_missing)
    ascii_seen.extend(seg_ascii)
    return bytes(encoded), complete, missing, ascii_seen


def encode_visible_segment(
    segment: str,
    code_table: dict[str, int],
    candidate_code_endian: str,
) -> tuple[bytes, bool, list[str], list[str]]:
    encoded = bytearray()
    missing: list[str] = []
    ascii_seen: list[str] = []
    complete = True

    for char in segment:
        codepoint = ord(char)
        if char in code_table:
            encoded.extend(code_table[char].to_bytes(2, candidate_code_endian))
        elif 0x20 <= codepoint <= 0x7E:
            encoded.append(codepoint)
            ascii_seen.append(char)
        else:
            complete = False
            missing.append(char)

    return bytes(encoded), complete, missing, ascii_seen


def payload_without_padding(text: str) -> tuple[str, int]:
    stripped = text.rstrip(" ")
    return stripped, len(text) - len(stripped)


def raw_lengths(raw: bytes, source_len: int | None) -> tuple[int, str, int]:
    if source_len is not None and len(raw) >= source_len + 2 and raw[source_len : source_len + 2] == b"\x03\x00":
        return source_len, "03 00", 2
    if raw.endswith(b"\x03\x00"):
        return len(raw) - 2, "03 00", 2
    return len(raw), "", 0


def status_for_row(risks: list[str]) -> tuple[str, bool, bool]:
    risk_set = set(risks)
    if not risk_set:
        return "ok_fixed_slot", True, True
    if risk_set == {"endian_unverified"}:
        return "candidate_fixed_slot_pending_endian", False, True
    if "overflow" in risk_set:
        return "blocked_overflow", False, False
    if "missing_code_table" in risk_set:
        return "blocked_missing_code_table", False, False
    if "control_decode_unverified" in risk_set or "control_token_mismatch" in risk_set:
        return "blocked_control_verification", False, False
    if "needs_ascii_policy" in risk_set:
        return "blocked_ascii_policy", False, False
    if "padding_ambiguous" in risk_set:
        return "blocked_padding_policy", False, False
    if "missing_capacity" in risk_set:
        return "blocked_missing_capacity", False, False
    return "blocked_policy_or_validation", False, False


def analyze_rows(
    rows: list[dict[str, str]],
    code_table: dict[str, int],
    candidate_code_endian: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    preview_rows: list[dict[str, Any]] = []
    risk_counts: Counter[str] = Counter()
    fixed_status_counts: Counter[str] = Counter()
    control_verdict_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    overflow_examples: list[dict[str, Any]] = []
    ascii_examples: list[dict[str, Any]] = []
    padding_examples: list[dict[str, Any]] = []
    missing_examples: list[dict[str, Any]] = []
    control_examples: list[dict[str, Any]] = []
    pre_endian_candidates: list[dict[str, Any]] = []

    encoded_complete_count = 0
    capacity_known_count = 0
    overflow_count = 0

    for row in rows:
        raw = parse_raw_hex(row.get("raw_hex", ""))
        source_len = parse_capacity(row.get("source_byte_len", ""))
        raw_payload_len, raw_terminator_hex, terminator_len = raw_lengths(raw, source_len)
        payload_capacity = raw_payload_len if raw_terminator_hex else source_len
        zh_raw = row.get("zh_text", "")
        zh_payload, padding_spaces = payload_without_padding(zh_raw)
        expected_tokens = tokens_from_field(row.get("control_tokens", "")) or tokens_from_text(
            row.get("jp_text", "")
        )
        actual_tokens = tokens_from_text(zh_payload)
        control_verdict, control_evidence = verify_control_tokens(raw, expected_tokens)
        encoded, complete, missing_chars, ascii_seen = encode_payload(
            zh_payload, code_table, candidate_code_endian
        )

        risks: list[str] = []
        if payload_capacity is None:
            risks.append("missing_capacity")
        else:
            capacity_known_count += 1
            if len(encoded) > payload_capacity:
                risks.append("overflow")
                overflow_count += 1
        if actual_tokens != expected_tokens:
            risks.append("control_token_mismatch")
        if expected_tokens and control_verdict != "candidate_little_endian_raw_hex_supported":
            risks.append("control_decode_unverified")
        if ascii_seen:
            risks.append("needs_ascii_policy")
        if missing_chars:
            risks.append("missing_code_table")
        if padding_spaces:
            risks.append("padding_ambiguous")
        if any(char in code_table for char in strip_control_tokens(zh_payload)):
            risks.append("endian_unverified")

        deduped_risks = list(dict.fromkeys(risks))
        for risk in deduped_risks:
            risk_counts[risk] += 1

        status, stage2_eligible, pre_endian_candidate = status_for_row(deduped_risks)
        fixed_status_counts[status] += 1
        control_verdict_counts[control_verdict] += 1
        category_counts[row.get("category", "") or "unknown"] += 1
        if complete:
            encoded_complete_count += 1

        capacity_delta = "" if payload_capacity is None else payload_capacity - len(encoded)
        preview = {
            "id": row.get("id", ""),
            "jp_id_ref": row.get("jp_id_ref", ""),
            "category": row.get("category", ""),
            "source_file": row.get("source_file", ""),
            "offset": row.get("offset", ""),
            "record_index": row.get("record_index", ""),
            "chunk_id": row.get("chunk_id", ""),
            "source_byte_len": "" if source_len is None else source_len,
            "payload_capacity": "" if payload_capacity is None else payload_capacity,
            "raw_payload_len": raw_payload_len,
            "raw_terminator_hex": raw_terminator_hex,
            "jp_text": row.get("jp_text", ""),
            "zh_text_raw": zh_raw,
            "zh_text_candidate_payload": zh_payload,
            "padding_spaces": padding_spaces,
            "encoded_hex_candidate": format_hex(encoded),
            "encoded_len_candidate": len(encoded),
            "capacity_delta": capacity_delta,
            "encoded_complete": bool_text(complete),
            "candidate_code_endian": candidate_code_endian,
            "code_endian_evidence": "cp932_source_bytes_are_file_order_big_endian; new_code_table_runtime_endian_unverified",
            "control_tokens_expected": " ".join(expected_tokens),
            "control_tokens_in_zh": " ".join(actual_tokens),
            "control_raw_verdict": control_verdict,
            "control_raw_evidence": control_evidence,
            "visible_ascii_chars": uniq_join(ascii_seen),
            "missing_chars": uniq_join(missing_chars),
            "risk_flags": " ".join(deduped_risks),
            "fixed_slot_status": status,
            "stage2_eligible": bool_text(stage2_eligible),
            "pre_endian_candidate": bool_text(pre_endian_candidate),
            "raw_hex": row.get("raw_hex", ""),
        }
        preview_rows.append(preview)

        example = {
            "id": preview["id"],
            "source_file": preview["source_file"],
            "offset": preview["offset"],
            "encoded_len_candidate": preview["encoded_len_candidate"],
            "source_byte_len": preview["source_byte_len"],
            "payload_capacity": preview["payload_capacity"],
            "capacity_delta": preview["capacity_delta"],
            "risk_flags": preview["risk_flags"],
        }
        if "overflow" in deduped_risks and len(overflow_examples) < 20:
            overflow_examples.append(example)
        if "needs_ascii_policy" in deduped_risks and len(ascii_examples) < 20:
            ascii_examples.append({**example, "visible_ascii_chars": preview["visible_ascii_chars"]})
        if "padding_ambiguous" in deduped_risks and len(padding_examples) < 20:
            padding_examples.append({**example, "padding_spaces": padding_spaces})
        if "missing_code_table" in deduped_risks and len(missing_examples) < 20:
            missing_examples.append({**example, "missing_chars": preview["missing_chars"]})
        if (
            "control_decode_unverified" in deduped_risks
            or "control_token_mismatch" in deduped_risks
        ) and len(control_examples) < 20:
            control_examples.append(
                {
                    **example,
                    "control_tokens_expected": preview["control_tokens_expected"],
                    "control_tokens_in_zh": preview["control_tokens_in_zh"],
                    "control_raw_verdict": control_verdict,
                }
            )
        if pre_endian_candidate and len(pre_endian_candidates) < 30:
            pre_endian_candidates.append(example)

    report = {
        "row_count": len(rows),
        "encoded_complete_count": encoded_complete_count,
        "capacity_known_count": capacity_known_count,
        "overflow_count": overflow_count,
        "stage2_eligible_count": sum(1 for row in preview_rows if row["stage2_eligible"] == "yes"),
        "pre_endian_candidate_count": sum(
            1 for row in preview_rows if row["pre_endian_candidate"] == "yes"
        ),
        "risk_counts": dict(sorted(risk_counts.items())),
        "fixed_slot_status_counts": dict(sorted(fixed_status_counts.items())),
        "control_raw_verdict_counts": dict(sorted(control_verdict_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "examples": {
            "pre_endian_candidates": pre_endian_candidates,
            "overflow": overflow_examples,
            "needs_ascii_policy": ascii_examples,
            "padding_ambiguous": padding_examples,
            "missing_code_table": missing_examples,
            "control_decode_or_token_issues": control_examples,
        },
    }
    return preview_rows, report


def strip_control_tokens(text: str) -> str:
    return CTRL_RE.sub("", text or "")


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build candidate encoded text preview and fixed-slot capacity risk report."
    )
    parser.add_argument("--translation", default="text/code_table/frozen_translation.tsv")
    parser.add_argument("--code-table", default="text/code_table/zh_code_table.tsv")
    parser.add_argument("--preview-out", default="text/writeback/encoded_preview.tsv")
    parser.add_argument("--report-out", default="text/reports/writeback-capacity-report.json")
    parser.add_argument(
        "--candidate-code-endian",
        choices=("big", "little"),
        default="big",
        help="Candidate byte order for new 0xF000-range text codes. This remains unverified.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    translation_path = Path(args.translation)
    code_table_path = Path(args.code_table)
    preview_path = Path(args.preview_out)
    report_path = Path(args.report_out)

    rows = read_tsv(translation_path)
    code_table = load_code_table(code_table_path)
    preview_rows, analysis = analyze_rows(rows, code_table, args.candidate_code_endian)
    code_byte_shape = summarize_code_byte_shape(code_table, args.candidate_code_endian)

    write_tsv(preview_path, preview_rows, PREVIEW_FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "inputs": {
            "translation": translation_path.as_posix(),
            "translation_sha1": sha1_file(translation_path),
            "code_table": code_table_path.as_posix(),
            "code_table_sha1": sha1_file(code_table_path),
        },
        "outputs": {
            "preview": preview_path.as_posix(),
            "report": report_path.as_posix(),
        },
        "candidate_code_endian": args.candidate_code_endian,
        "code_endian_verdict": "unverified_candidate",
        "code_endian_evidence": [
            "Original CP932 two-byte visible characters are stored in file byte order.",
            "New Chinese code-table runtime consumption has not yet been verified.",
            "Rows with mapped Chinese/fullwidth chars keep endian_unverified and are not Stage 2 eligible.",
        ],
        "code_byte_shape": code_byte_shape,
        "control_decode_verdict": "candidate_little_endian_checked_by_raw_hex_occurrence",
        "code_table_entries": len(code_table),
        **analysis,
        "next_actions": [
            "Verify new-code byte order before selecting Stage 2 samples.",
            "Decide ordinary ASCII handling before rows with needs_ascii_policy can be written.",
            "Decide padding handling before rows with padding_ambiguous can be written.",
            "Use only rows with stage2_eligible=yes after all hard gates are satisfied.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("row_count", "risk_counts", "fixed_slot_status_counts")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
