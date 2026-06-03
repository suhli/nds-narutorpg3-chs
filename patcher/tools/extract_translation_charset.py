from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Iterable


CTRL_RE = re.compile(r"\{CTRL_([0-9A-Fa-f]{4})\}")
DEFAULT_MODES = ("1x1", "1x2")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_modes(value: str) -> list[str]:
    modes = [part.strip() for part in re.split(r"[,+\s]+", value) if part.strip()]
    if not modes:
        return list(DEFAULT_MODES)
    invalid = set(modes) - set(DEFAULT_MODES)
    if invalid:
        raise ValueError(f"invalid modes: {sorted(invalid)}")
    return modes


def tokens_from_text(text: str) -> list[int]:
    return [int(match.group(1), 16) for match in CTRL_RE.finditer(text or "")]


def parse_raw_words_big_endian(raw_hex: str) -> set[int]:
    parts = [part for part in (raw_hex or "").split() if re.fullmatch(r"[0-9A-Fa-f]{2}", part)]
    out: set[int] = set()
    for index in range(0, len(parts) - 1, 2):
        out.add((int(parts[index], 16) << 8) | int(parts[index + 1], 16))
    return out


def parse_chmp_codes(path: Path) -> set[int]:
    data = path.read_bytes()
    if len(data) < 0x20 or data[:4] != b"CHMP":
        return set()
    header_size = int.from_bytes(data[6:8], "little")
    entry_size = int.from_bytes(data[10:12], "little")
    entry_count = int.from_bytes(data[12:16], "little")
    codes: set[int] = set()
    for index in range(entry_count):
        offset = header_size + index * entry_size
        if offset + 4 > len(data):
            break
        codes.add(int.from_bytes(data[offset : offset + 4], "little"))
    return codes


def is_sjis_lead(byte: int) -> bool:
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC


def is_sjis_trail(byte: int) -> bool:
    return (0x40 <= byte <= 0x7E) or (0x80 <= byte <= 0xFC)


def is_sjis_shaped_code(code: int) -> bool:
    return is_sjis_lead((code >> 8) & 0xFF) and is_sjis_trail(code & 0xFF)


def iter_candidate_codes(start_code: int, code_shape: str) -> Iterable[int]:
    code = start_code
    while code <= 0xFFFF:
        if code_shape == "sjis" and not is_sjis_shaped_code(code):
            code += 1
            continue
        yield code
        code += 1


def parse_manifest_codes(path: Path) -> set[int]:
    if not path.exists():
        return set()
    if path.suffix.lower() == ".json":
        payload = read_json(path)
        if isinstance(payload, dict):
            raw_entries = payload.get("entries", [])
        else:
            raw_entries = payload
        codes = set()
        for item in raw_entries:
            if isinstance(item, dict) and "code" in item:
                codes.add(int(str(item["code"]), 0))
        return codes

    codes = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.replace("=", " ").replace(",", " ").split()
        if parts:
            codes.add(int(parts[0], 0))
    return codes


def discover_existing_font_codes(paths: Iterable[Path]) -> set[int]:
    codes: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix.lower() == ".map":
                codes.update(parse_chmp_codes(path))
            elif path.suffix.lower() in {".json", ".txt"}:
                codes.update(parse_manifest_codes(path))
            continue
        for child in path.rglob("*"):
            if child.suffix.lower() == ".map":
                codes.update(parse_chmp_codes(child))
            elif child.name in {"manifest.resolved.json", "font_manifest.json", "font_manifest.txt"}:
                codes.update(parse_manifest_codes(child))
    return codes


def is_ascii_visible(char: str) -> bool:
    code = ord(char)
    return 0x20 <= code <= 0x7E


def text_manifest_char(char: str) -> str:
    if char.isspace() or char == "#" or char == "\\":
        return f"\\u{ord(char):04X}"
    return char


def iter_visible_chars(text: str) -> tuple[list[str], Counter[str], int, int]:
    stripped = (text or "").rstrip(" ")
    padding_spaces = len(text or "") - len(stripped)
    chars: list[str] = []
    ascii_counter: Counter[str] = Counter()
    ctrl_count = 0
    position = 0
    for match in CTRL_RE.finditer(stripped):
        for char in stripped[position : match.start()]:
            if is_ascii_visible(char):
                ascii_counter[char] += 1
            elif char:
                chars.append(char)
        ctrl_count += 1
        position = match.end()
    for char in stripped[position:]:
        if is_ascii_visible(char):
            ascii_counter[char] += 1
        elif char:
            chars.append(char)
    return chars, ascii_counter, ctrl_count, padding_spaces


def freeze_chunks(
    *,
    index_path: Path,
    translated_dir: Path,
    reports_dir: Path,
) -> tuple[list[dict[str, str]], list[str], list[dict[str, object]], list[dict[str, object]]]:
    index = read_json(index_path)
    entries = index.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError(f"{index_path} has no entries list")

    frozen_rows: list[dict[str, str]] = []
    chunk_summaries: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    fieldnames: list[str] | None = None

    for entry in entries:
        chunk_id = str(entry["chunk_id"])
        expected_rows = int(entry["rows"])
        translated_path = translated_dir / f"{chunk_id}.tsv"
        report_path = reports_dir / f"{chunk_id}-control-code-check.json"

        if not translated_path.exists():
            issues.append({"chunk_id": chunk_id, "reason": "missing_translated_chunk", "path": str(translated_path)})
            continue

        rows = read_tsv(translated_path)
        if fieldnames is None:
            fieldnames = list(rows[0].keys()) if rows else []
            if "chunk_id" not in fieldnames:
                fieldnames.append("chunk_id")
        if len(rows) != expected_rows:
            issues.append(
                {
                    "chunk_id": chunk_id,
                    "reason": "row_count_mismatch",
                    "expected": expected_rows,
                    "actual": len(rows),
                }
            )

        translated_rows = sum(1 for row in rows if row.get("zh_text", "").strip())
        aligned_rows = sum(1 for row in rows if row.get("status") == "translated_aligned")
        if translated_rows != len(rows):
            issues.append(
                {
                    "chunk_id": chunk_id,
                    "reason": "empty_translation_rows",
                    "expected_non_empty": len(rows),
                    "actual_non_empty": translated_rows,
                }
            )
        if aligned_rows != len(rows):
            issues.append(
                {
                    "chunk_id": chunk_id,
                    "reason": "not_all_rows_aligned",
                    "expected_aligned": len(rows),
                    "actual_aligned": aligned_rows,
                }
            )

        report_issue_count = None
        if report_path.exists():
            report = read_json(report_path)
            report_issue_count = int(report.get("issue_count", 0))
            if report_issue_count:
                issues.append(
                    {
                        "chunk_id": chunk_id,
                        "reason": "validation_report_has_issues",
                        "issue_count": report_issue_count,
                    }
                )
        else:
            issues.append({"chunk_id": chunk_id, "reason": "missing_validation_report", "path": str(report_path)})

        for row in rows:
            row = dict(row)
            row["chunk_id"] = chunk_id
            frozen_rows.append(row)

        chunk_summaries.append(
            {
                "chunk_id": chunk_id,
                "path": translated_path.as_posix(),
                "sha1": sha1_file(translated_path),
                "rows": len(rows),
                "translated_rows": translated_rows,
                "aligned_rows": aligned_rows,
                "report_path": report_path.as_posix() if report_path.exists() else "",
                "report_issue_count": report_issue_count,
            }
        )

    if fieldnames is None:
        fieldnames = ["chunk_id"]
    return frozen_rows, fieldnames, chunk_summaries, issues


def build_charset(rows: list[dict[str, str]]) -> tuple[OrderedDict[str, dict[str, object]], Counter[str], dict[str, int], set[int], set[int]]:
    chars: OrderedDict[str, dict[str, object]] = OrderedDict()
    ascii_counter: Counter[str] = Counter()
    totals = {
        "visible_non_ascii_chars": 0,
        "unique_non_ascii_chars": 0,
        "ignored_ascii_chars": 0,
        "control_tokens": 0,
        "ignored_padding_spaces": 0,
    }
    control_values: set[int] = set()
    raw_word_values: set[int] = set()

    for row_index, row in enumerate(rows):
        chunk_id = row.get("chunk_id", "")
        chunk_row = row.get("chunk_row_index", str(row_index))
        text = row.get("zh_text", "")
        visible_chars, row_ascii, ctrl_count, padding_spaces = iter_visible_chars(text)
        ascii_counter.update(row_ascii)
        totals["ignored_ascii_chars"] += sum(row_ascii.values())
        totals["control_tokens"] += ctrl_count
        totals["ignored_padding_spaces"] += padding_spaces
        control_values.update(tokens_from_text(text))
        control_values.update(tokens_from_text(row.get("jp_text", "")))
        raw_word_values.update(parse_raw_words_big_endian(row.get("raw_hex", "")))

        seen_in_row: set[str] = set()
        for char in visible_chars:
            totals["visible_non_ascii_chars"] += 1
            if char not in chars:
                chars[char] = {
                    "frequency": 0,
                    "first_seen_chunk": chunk_id,
                    "first_seen_row": chunk_row,
                    "source_count": 0,
                }
            chars[char]["frequency"] = int(chars[char]["frequency"]) + 1
            if char not in seen_in_row:
                chars[char]["source_count"] = int(chars[char]["source_count"]) + 1
                seen_in_row.add(char)

    totals["unique_non_ascii_chars"] = len(chars)
    return chars, ascii_counter, totals, control_values, raw_word_values


def write_charset(path: Path, chars: OrderedDict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(chars.keys()) + "\n", encoding="utf-8")


def write_ignored_ascii(path: Path, ascii_counter: Counter[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["char\tunicode_hex\tcount\tdisplay\n"]
    for char, count in sorted(ascii_counter.items(), key=lambda item: (ord(item[0]), item[0])):
        display = "SPACE" if char == " " else char
        lines.append(f"{char}\tU+{ord(char):04X}\t{count}\t{display}\n")
    path.write_text("".join(lines), encoding="utf-8")


def allocate_codes(
    chars: OrderedDict[str, dict[str, object]],
    *,
    start_code: int,
    code_shape: str,
    modes: list[str],
    reserved_values: set[int],
    existing_font_codes: set[int],
    raw_word_values: set[int],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    rows: list[dict[str, str]] = []
    collisions: list[dict[str, object]] = []
    skipped_codes: list[dict[str, object]] = []
    assigned_codes: set[int] = set()
    mode_text = ",".join(modes)
    candidates = iter_candidate_codes(start_code, code_shape)

    for char, meta in chars.items():
        while True:
            try:
                code = next(candidates)
            except StopIteration as exc:
                raise ValueError(f"not enough assignable codes for {len(chars)} chars from 0x{start_code:04X}") from exc
            reasons = []
            if code in reserved_values:
                reasons.append("reserved_or_control")
            if code in existing_font_codes:
                reasons.append("existing_font_code")
            if code in raw_word_values:
                reasons.append("raw_text_word")
            if code in assigned_codes:
                reasons.append("duplicate_assignment")
            if reasons:
                skipped_codes.append({"code_hex": f"0x{code:04X}", "reasons": reasons})
                continue
            break
        assigned_codes.add(code)
        rows.append(
            {
                "char": char,
                "unicode_hex": f"U+{ord(char):04X}",
                "code_hex": f"0x{code:04X}",
                "modes": mode_text,
                "frequency": str(meta["frequency"]),
                "first_seen_chunk": str(meta["first_seen_chunk"]),
                "first_seen_row": str(meta["first_seen_row"]),
                "source_count": str(meta["source_count"]),
                "notes": "provisional",
            }
        )

    shape_issues = [
        {"char": row["char"], "code_hex": row["code_hex"], "reason": "not_sjis_shaped"}
        for row in rows
        if code_shape == "sjis" and not is_sjis_shaped_code(int(row["code_hex"], 16))
    ]
    collisions.extend(shape_issues)
    assigned_values = [int(row["code_hex"], 16) for row in rows]
    end_code = max(assigned_values) if assigned_values else start_code
    summary = {
        "start_code": f"0x{start_code:04X}",
        "end_code": f"0x{end_code:04X}",
        "code_shape": code_shape,
        "entry_count": len(chars),
        "collision_count": len(collisions),
        "collisions": collisions,
        "skipped_code_count": len(skipped_codes),
        "skipped_code_examples": skipped_codes[:50],
    }
    return rows, summary


def write_manifest(json_path: Path, txt_path: Path, code_rows: list[dict[str, str]]) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    txt_lines: list[str] = []
    for row in code_rows:
        modes = parse_modes(row["modes"])
        manifest_char = text_manifest_char(row["char"])
        entries.append({"code": row["code_hex"], "char": manifest_char, "modes": modes})
        txt_lines.append(f"{row['code_hex']} {manifest_char} {','.join(modes)}\n")
    json_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    txt_path.write_text("".join(txt_lines), encoding="utf-8")


def write_code_table(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "char",
        "unicode_hex",
        "code_hex",
        "modes",
        "frequency",
        "first_seen_chunk",
        "first_seen_row",
        "source_count",
        "notes",
    ]
    write_tsv(path, rows, fields)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze translated chunks and extract the Chinese code table inputs.")
    parser.add_argument("--index", default="text/translation/chunks/index.json")
    parser.add_argument("--translated-dir", default="text/translation/chunks/translated")
    parser.add_argument("--reports-dir", default="text/translation/chunks/reports")
    parser.add_argument("--out-dir", default="text/code_table")
    parser.add_argument("--summary", default="text/reports/code-table-summary.json")
    parser.add_argument("--start-code", default="0xF040")
    parser.add_argument(
        "--code-shape",
        choices=("contiguous", "sjis"),
        default="sjis",
        help="Code allocation shape. 'sjis' keeps lead/trail bytes in Shift-JIS-like ranges.",
    )
    parser.add_argument("--modes", default="1x1,1x2")
    parser.add_argument(
        "--existing-font-scan",
        action="append",
        default=["plan/cache/vram-font-bypass/generated-font-smoke"],
        help="Existing font dir, map, or manifest to scan for code collisions. Can be repeated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    summary_path = Path(args.summary)
    modes = parse_modes(args.modes)
    start_code = int(str(args.start_code), 0)

    frozen_rows, frozen_fields, chunks, freeze_issues = freeze_chunks(
        index_path=Path(args.index),
        translated_dir=Path(args.translated_dir),
        reports_dir=Path(args.reports_dir),
    )
    frozen_path = out_dir / "frozen_translation.tsv"
    write_tsv(frozen_path, frozen_rows, frozen_fields)

    chars, ascii_counter, char_totals, control_values, raw_word_values = build_charset(frozen_rows)
    charset_path = out_dir / "zh_charset.txt"
    ignored_ascii_path = out_dir / "ignored_ascii.txt"
    write_charset(charset_path, chars)
    write_ignored_ascii(ignored_ascii_path, ascii_counter)

    reserved_values = set(control_values) | {0x0000, 0x0001, 0x0002, 0x0003, 0x0103}
    existing_font_codes = discover_existing_font_codes(Path(path) for path in args.existing_font_scan)
    code_rows, allocation = allocate_codes(
        chars,
        start_code=start_code,
        code_shape=args.code_shape,
        modes=modes,
        reserved_values=reserved_values,
        existing_font_codes=existing_font_codes,
        raw_word_values=raw_word_values,
    )
    code_table_path = out_dir / "zh_code_table.tsv"
    write_code_table(code_table_path, code_rows)

    manifest_json_path = out_dir / "font_manifest.json"
    manifest_txt_path = out_dir / "font_manifest.txt"
    write_manifest(manifest_json_path, manifest_txt_path, code_rows)

    index_payload = read_json(Path(args.index))
    summary = {
        "inputs": {
            "index": Path(args.index).as_posix(),
            "translated_dir": Path(args.translated_dir).as_posix(),
            "reports_dir": Path(args.reports_dir).as_posix(),
            "index_chunks": index_payload.get("chunks", 0),
            "index_rows": index_payload.get("rows", 0),
        },
        "outputs": {
            "frozen_translation": frozen_path.as_posix(),
            "zh_charset": charset_path.as_posix(),
            "zh_code_table": code_table_path.as_posix(),
            "font_manifest_json": manifest_json_path.as_posix(),
            "font_manifest_txt": manifest_txt_path.as_posix(),
            "ignored_ascii": ignored_ascii_path.as_posix(),
        },
        "freeze": {
            "chunks": len(chunks),
            "rows": len(frozen_rows),
            "issue_count": len(freeze_issues),
            "issues": freeze_issues,
            "chunks_detail": chunks,
        },
        "charset": char_totals,
        "ascii": {
            "unique_ignored_ascii_chars": len(ascii_counter),
            "ignored_ascii_counts": dict(sorted(ascii_counter.items(), key=lambda item: (ord(item[0]), item[0]))),
        },
        "conflict_scan": {
            "reserved_or_control_values_count": len(reserved_values),
            "raw_text_word_values_count": len(raw_word_values),
            "existing_font_codes_count": len(existing_font_codes),
            "existing_font_scan_paths": [str(path) for path in args.existing_font_scan],
        },
        "allocation": allocation,
        "manifest": {
            "entry_count": len(code_rows),
            "modes": modes,
            "format": {"json": {"entries": [{"code": "0xE000", "char": "字", "modes": ["1x1", "1x2"]}]}, "text": "<code> <char> [modes]"},
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"chunks={len(chunks)} rows={len(frozen_rows)} freeze_issues={len(freeze_issues)}")
    print(f"charset={len(chars)} ignored_ascii={sum(ascii_counter.values())}")
    print(f"start_code=0x{start_code:04X} code_shape={args.code_shape} collisions={allocation['collision_count']}")
    print(f"summary={summary_path}")
    return 1 if freeze_issues or allocation["collision_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
