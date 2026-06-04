from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import re
import shutil
from pathlib import Path
from typing import Any

import build_vram_font_dynamic_cache_rom as font_rom


DEFAULT_SAMPLE_IDS = [
    "zh_txt_869691fa_0000AE_0003",
    "zh_txt_876c4bf1_003C60_0367",
]

DEFAULT_EXCLUDED_SOURCE_FILES = {
    "msg/wifi/friend_msg.msg",
    "msg/wifi/kinshi_msg.msg",
}

DEFAULT_INCLUDED_ROW_IDS_WHEN_SOURCE_EXCLUDED = {
    "zh_txt_64f689a6_0006A2_0015",
    "zh_txt_64f689a6_0006F6_0016",
}

DEFAULT_EXCLUDED_ROW_IDS = {
    "zh_txt_a346a806_0031E1_0180",
    "zh_txt_579f0fbf_0029AD_0181",
    "zh_txt_c741b6bc_003795_0263",
}

SPACE_PADDED_FIXED_SLOT_SOURCE_FILES = {
    "msg/equip_msg.msg",
    "msg/item_msg.msg",
    "msg/jyutu_msg.msg",
    "msg/menu/item_menu_msg.msg",
    "msg/skill_msg.msg",
    "msg/taityou_kouka.msg",
}

FIXED_SUBSLOT_SOURCE_FILES = {
    "msg/jyutu_msg.msg",
    "msg/menu/status_menu_msg.msg",
    "msg/menu/top_menu_msg.msg",
}

LOCAL_FIXED_TEXT_SPAN_REPLACEMENTS = {
    "zh_txt_2191d3e9_00005A_0002": (
        (0, "\u3053\u3046\u304b", "\u6548\u679c"),
    ),
}

TRANSLATABLE_MESSAGE_PREFIX_ROW_IDS = {
    "zh_txt_08033e0a_0005CC_0016",
    "zh_txt_4dc3cb5a_000126_0004",
    "zh_txt_fd9564ad_00049C_0014",
    "zh_txt_6fae3ea4_00015E_0005",
    "zh_txt_df1b8d0f_000110_0003",
    "zh_txt_f3b3bfac_0006E8_0027",
}

CTRL_RE = re.compile(r"\{CTRL_([0-9A-Fa-f]{4})\}")
LEADING_CTRL_RUN_RE = re.compile(r"^((?:\{CTRL_[0-9A-Fa-f]{4}\})+)(.*)$", re.S)
OPEN_QUOTES = ("\u300c", "\u300e", "\u201c", '"')
LEADING_STRUCTURE_EXEMPT_CHARS = "{\u300c\u300e\u201c\""
YES_BYTES = b"\x82\xCD\x82\xA2"
NO_BYTES = b"\x82\xA2\x82\xA2\x82\xA6"
YES_NO_OPTION_PREFIX = YES_BYTES + b"\x01\x00" + NO_BYTES
SCENE_TAIL_CTRL = "{CTRL_0101}"
SCENE_TAIL_WITH_BREAK_CTRL = "{CTRL_0001}{CTRL_0101}"
GENERIC_ITEM_GET_JP_PREFIX = "\u3092{CTRL_0001}\u3066\u306b"
GENERIC_ITEM_GET_TEXT = "{CTRL_0001}\u83b7\u5f97\u4e86\uff01"
MESSAGE_TEXT_OVERRIDES = {
    "zh_txt_ea2a6c3d_00019E_0004": "\u300c\u563b\u563b\u563b\u2026\u2026\u6211\u4e0d\u4f1a\u8ba9\u4f60\u4eec{CTRL_0001}\u518d\u5f80\u524d\u8d70\u4e86\u300d",
    "zh_txt_36cf8fef_000316_0010": "\u8bf7\u5173\u95ed\u7535\u6e90{CTRL_0001}\u91cd\u65b0\u63d2\u5165\u8bb0\u5fc6\u5361",
    "zh_txt_805b124c_0002CE_0004": "\u627e\u5230\u5bf9\u6218\u5bf9\u624b\u4e86\uff01{CTRL_0000}\u65e0\u6cd5\u5f00\u59cb\u5bf9\u6218{CTRL_0001}\u8bf7\u91cd\u65b0\u5c1d\u8bd5{CTRL_0000}\u901a\u4fe1\u5bf9\u6218\u51c6\u5907\u4e2d\u2026\u2026{CTRL_0000}\u51c6\u5907\u5b8c\u6bd5\uff01{CTRL_0000}{CTRL_0103}{CTRL_0002}Wi-Fi\u8fde\u63a5{CTRL_0103}{CTRL_0000}\u65ad\u5f00\u5e76\u7ed3\u675fWi-Fi\u901a\u4fe1\u5417\uff1f{CTRL_0000}{CTRL_0103}{CTRL_0002}Wi-Fi\u8fde\u63a5{CTRL_0103}{CTRL_0000}\u6b63\u5728\u65ad\u5f00{CTRL_0001}\u2026\u2026{CTRL_0000}{CTRL_0103}{CTRL_0002}Wi-Fi\u8fde\u63a5{CTRL_0103}{CTRL_0000}{CTRL_0001}\u5df2\u65ad\u5f00",
    "zh_txt_28e72e7e_0004A2_0008": "\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002{CTRL_0000}\u7531\u4e8e\u901a\u4fe1\u9519\u8bef\uff0c\u5df2\u4ece{CTRL_0103}{CTRL_0002}Wi-Fi\u8fde\u63a5{CTRL_0103}{CTRL_0000}{CTRL_0001}\u65ad\u5f00\u3002{CTRL_0000}\u5bf9\u65b9\u6ca1\u6709\u54cd\u5e94\u3002{CTRL_0001}\u5bf9\u65b9\u53ef\u80fd\u5c1a\u672a\u8fde\u63a5\u5230{CTRL_0103}{CTRL_0002}Wi-Fi\u8fde\u63a5{CTRL_0103}{CTRL_0000}{CTRL_0001}\u3002",
}


def is_sjis_lead(byte: int) -> bool:
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC


def is_sjis_trail(byte: int) -> bool:
    return (0x40 <= byte <= 0x7E) or (0x80 <= byte <= 0xFC)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def normalize_source_file(value: str) -> str:
    return value.replace("\\", "/").lower()


def parse_source_file_set(value: str) -> set[str]:
    return {normalize_source_file(part.strip()) for part in value.split(",") if part.strip()}


def filter_excluded_source_files(
    rows: list[dict[str, str]],
    excluded_source_files: set[str],
    included_row_ids: set[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not excluded_source_files:
        return rows, {}
    included_row_ids = included_row_ids or set()
    selected: list[dict[str, str]] = []
    excluded: dict[str, int] = {}
    for row in rows:
        source_file = normalize_source_file(row.get("source_file", ""))
        if source_file in excluded_source_files and row.get("id", "") not in included_row_ids:
            excluded[source_file] = excluded.get(source_file, 0) + 1
            continue
        selected.append(row)
    return selected, excluded


def parse_hex_bytes(value: str) -> bytes:
    value = (value or "").strip()
    if not value:
        return b""
    return bytes(int(part, 16) for part in value.split())


def load_code_table(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in read_tsv(path):
        char = row.get("char", "")
        code_hex = row.get("code_hex", "")
        if char and code_hex:
            out[char] = int(code_hex, 16)
    return out


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}_build_{stamp}{path.suffix}")
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        indexed = path.with_name(f"{path.stem}_build_{stamp}_{index}{path.suffix}")
        if not indexed.exists():
            return indexed
    raise FileExistsError(f"could not find unused path near {path}")


def load_samples(preview_path: Path, sample_ids: list[str]) -> list[dict[str, str]]:
    rows = read_tsv(preview_path)
    by_id = {row["id"]: row for row in rows}
    missing = [sample_id for sample_id in sample_ids if sample_id not in by_id]
    if missing:
        raise KeyError(f"missing sample ids in preview: {missing}")
    samples = [by_id[sample_id] for sample_id in sample_ids]
    for row in samples:
        risks = set((row.get("risk_flags") or "").split())
        allowed = {"endian_unverified"}
        if risks - allowed:
            raise ValueError(f"{row['id']} is not a low-risk sample: {sorted(risks)}")
        if row.get("pre_endian_candidate") != "yes":
            raise ValueError(f"{row['id']} is not marked pre_endian_candidate=yes")
    return samples


def load_all_rows(preview_path: Path, excluded_source_files: set[str] | None = None) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows = read_tsv(preview_path)
    selected: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for row in rows:
        if row.get("id", "") in DEFAULT_EXCLUDED_ROW_IDS:
            continue
        if row.get("encoded_complete") != "yes":
            blocked.append(row)
            continue
        if not row.get("encoded_hex_candidate", "").strip():
            blocked.append(row)
            continue
        capacity_delta = row.get("capacity_delta", "").strip()
        if capacity_delta and int(capacity_delta) < 0:
            blocked.append(row)
            continue
        selected.append(row)
    if blocked:
        raise ValueError(f"{len(blocked)} rows cannot be written by fixed-slot full-writeback mode")
    return filter_excluded_source_files(
        selected,
        excluded_source_files or set(),
        DEFAULT_INCLUDED_ROW_IDS_WHEN_SOURCE_EXCLUDED,
    )


def encode_text(text: str, code_table: dict[str, int], *, candidate_code_endian: str) -> bytes:
    encoded = bytearray()
    pos = 0
    for match in CTRL_RE.finditer(text):
        encoded.extend(encode_plain_text(text[pos : match.start()], code_table, candidate_code_endian=candidate_code_endian))
        encoded.extend(int(match.group(1), 16).to_bytes(2, "little"))
        pos = match.end()
    encoded.extend(encode_plain_text(text[pos:], code_table, candidate_code_endian=candidate_code_endian))
    return bytes(encoded)


def encode_plain_text(text: str, code_table: dict[str, int], *, candidate_code_endian: str) -> bytes:
    encoded = bytearray()
    for char in text:
        if char in code_table:
            encoded.extend(code_table[char].to_bytes(2, candidate_code_endian))
            continue
        if 0x20 <= ord(char) <= 0x7E:
            encoded.append(ord(char))
            continue
        try:
            encoded.extend(char.encode("cp932"))
        except UnicodeEncodeError as exc:
            raise ValueError(f"missing code table entry for {char!r}") from exc
    return bytes(encoded)


def split_text_controls(text: str) -> tuple[list[str], list[int]]:
    segments: list[str] = []
    controls: list[int] = []
    pos = 0
    for match in CTRL_RE.finditer(text or ""):
        segments.append(text[pos : match.start()])
        controls.append(int(match.group(1), 16))
        pos = match.end()
    segments.append((text or "")[pos:])
    return segments, controls


def join_text_controls(segments: list[str], controls: list[int]) -> str:
    if len(segments) != len(controls) + 1:
        raise ValueError("text control segments do not match control count")
    out = [segments[0]]
    for control, segment in zip(controls, segments[1:]):
        out.append(f"{{CTRL_{control:04X}}}")
        out.append(segment)
    return "".join(out)


def split_raw_controls(raw: bytes) -> tuple[list[bytes], list[int]]:
    segments: list[bytes] = []
    controls: list[int] = []
    start = 0
    index = 0
    while index < len(raw):
        byte = raw[index]
        if byte < 0x20:
            if index + 1 >= len(raw):
                raise ValueError("truncated raw control word")
            segments.append(raw[start:index])
            controls.append(int.from_bytes(raw[index : index + 2], "little"))
            index += 2
            start = index
            continue
        if is_sjis_lead(byte) and index + 1 < len(raw) and is_sjis_trail(raw[index + 1]):
            index += 2
            continue
        index += 1
    segments.append(raw[start:])
    return segments, controls


def split_raw_ctrl_0000_subslots(raw: bytes) -> tuple[list[bytes], list[bytes], list[int]]:
    slots: list[bytes] = []
    separators: list[bytes] = []
    separator_offsets: list[int] = []
    start = 0
    index = 0
    while index < len(raw):
        byte = raw[index]
        if byte < 0x20:
            if index + 1 >= len(raw):
                raise ValueError("truncated raw control word")
            value = int.from_bytes(raw[index : index + 2], "little")
            if value == 0:
                slots.append(raw[start:index])
                separators.append(raw[index : index + 2])
                separator_offsets.append(index)
                index += 2
                start = index
                continue
            index += 2
            continue
        if is_sjis_lead(byte) and index + 1 < len(raw) and is_sjis_trail(raw[index + 1]):
            index += 2
            continue
        index += 1
    slots.append(raw[start:])
    return slots, separators, separator_offsets


def strip_leading_structure_text(text: str) -> str:
    out = (text or "").strip()
    changed = True
    while changed:
        changed = False
        match = LEADING_CTRL_RUN_RE.match(out)
        if match:
            out = match.group(2)
            changed = True
        while out and ord(out[0]) < 0x80 and out[0] not in LEADING_STRUCTURE_EXEMPT_CHARS:
            out = out[1:]
            changed = True
    return out


def text_from_first_open_quote(text: str) -> str:
    clean = strip_leading_structure_text(text)
    quote_positions = [clean.find(quote) for quote in OPEN_QUOTES if clean.find(quote) >= 0]
    if quote_positions:
        return clean[min(quote_positions) :]
    return clean


def text_after_translated_yes_no_prefix(text: str) -> str:
    clean = strip_leading_structure_text(text)
    if len(clean) >= 2 and clean[0] in OPEN_QUOTES and clean[1] == "\u662f":
        clean = clean[1:]
    option_text = "\u662f{CTRL_0001}\u5426"
    if clean.startswith(option_text):
        clean = clean[len(option_text) :]
        control_prefix = "{CTRL_0006}{CTRL_0000}"
        if clean.startswith(control_prefix):
            clean = clean[len(control_prefix) :]
        clean = clean.lstrip()
    return text_from_first_open_quote(clean)


def text_override_for_row(row: dict[str, str]) -> str | None:
    row_id = row.get("id", "")
    if row_id in MESSAGE_TEXT_OVERRIDES:
        return MESSAGE_TEXT_OVERRIDES[row_id]
    jp_text = row.get("jp_text", "")
    if jp_text.startswith(GENERIC_ITEM_GET_JP_PREFIX):
        return GENERIC_ITEM_GET_TEXT
    return None


def normalized_message_text(row: dict[str, str]) -> str:
    override = text_override_for_row(row)
    if override is not None:
        return override
    text = row.get("zh_text_candidate_payload", "")
    return text


def translate_fixed_message_prefix(
    row: dict[str, str],
    prefix: bytes,
    code_table: dict[str, int],
    *,
    candidate_code_endian: str,
) -> tuple[bytes, str, dict[str, Any]]:
    raw_segments, raw_controls = split_raw_controls(prefix)
    if not raw_controls or raw_segments[-1]:
        raise ValueError(f"{row['id']} fixed message prefix is not control-terminated")

    translated = normalized_message_text(row).strip()
    if translated.startswith(OPEN_QUOTES):
        translated = translated[1:]
    translated_segments, translated_controls = split_text_controls(translated)
    control_count = len(raw_controls)
    if translated_controls[:control_count] != raw_controls:
        raise ValueError(f"{row['id']} translated message prefix controls do not match original prefix")

    prefix_segments = translated_segments[:control_count] + [""]
    replacement = bytearray()
    translated_lengths: list[int] = []
    for index, (raw_segment, translated_segment) in enumerate(zip(raw_segments, prefix_segments)):
        encoded = encode_text(
            translated_segment,
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        if len(encoded) > len(raw_segment):
            raise ValueError(f"{row['id']} translated message prefix segment {index} exceeds original width")
        replacement.extend(encoded)
        replacement.extend(message_padding(len(raw_segment) - len(encoded)))
        translated_lengths.append(len(encoded))
        if index < control_count:
            replacement.extend(raw_controls[index].to_bytes(2, "little"))

    body = join_text_controls(translated_segments[control_count:], translated_controls[control_count:]).lstrip()
    if body and not body.startswith(OPEN_QUOTES):
        body = OPEN_QUOTES[0] + body
    return bytes(replacement), body, {
        "message_prefix_segment_count": len(prefix_segments) - 1,
        "message_prefix_translated_lengths": translated_lengths[:-1],
        "message_prefix_controls_preserved": [f"0x{value:04X}" for value in raw_controls],
    }


def make_local_fixed_text_span_replacement(
    row: dict[str, str],
    *,
    raw: bytes,
    terminator: bytes,
    code_table: dict[str, int],
    candidate_code_endian: str,
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    replacements = LOCAL_FIXED_TEXT_SPAN_REPLACEMENTS[row["id"]]
    replacement = bytearray(raw)
    encoded_parts: list[bytes] = []
    spans: list[dict[str, Any]] = []
    for offset, source_text, translated_text in replacements:
        source = source_text.encode("cp932")
        original = raw[offset : offset + len(source)]
        if original != source:
            raise ValueError(f"{row['id']} local fixed text span source mismatch at 0x{offset:X}")
        encoded = encode_text(
            translated_text,
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        if len(encoded) > len(source):
            raise ValueError(f"{row['id']} local fixed text span exceeds original width")
        replacement[offset : offset + len(source)] = encoded + message_padding(len(source) - len(encoded))
        encoded_parts.append(encoded)
        spans.append(
            {
                "offset": offset,
                "source_len": len(source),
                "translated_len": len(encoded),
            }
        )
    return b"".join(encoded_parts), terminator, bytes(replacement), {
        "fixed_slot_strategy": "local_text_span_preserve_binary",
        "local_text_spans": spans,
    }


def make_fixed_subslot_replacement(
    row: dict[str, str],
    *,
    raw: bytes,
    terminator: bytes,
    code_table: dict[str, int],
    candidate_code_endian: str,
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    jp_slots = row.get("jp_text", "").split("{CTRL_0000}")
    translated_slots = normalized_message_text(row).split("{CTRL_0000}")
    if len(jp_slots) != len(translated_slots):
        raise ValueError(f"{row['id']} translated fixed subslot count does not match original text")

    payload = raw[: -len(terminator)] if terminator else raw
    raw_slots, separators, separator_offsets = split_raw_ctrl_0000_subslots(payload)
    if len(raw_slots) < len(translated_slots):
        raise ValueError(f"{row['id']} raw fixed subslot count is smaller than translated slot count")

    replacement = bytearray(raw)
    encoded_parts: list[bytes] = []
    slot_records: list[dict[str, Any]] = []
    for index, translated_slot in enumerate(translated_slots):
        _, jp_controls = split_text_controls(jp_slots[index])
        _, translated_controls = split_text_controls(translated_slot)
        if jp_controls != translated_controls:
            raise ValueError(f"{row['id']} translated fixed subslot {index} controls do not match original")
        encoded = encode_text(
            translated_slot,
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        raw_slot = raw_slots[index]
        if len(encoded) > len(raw_slot):
            raise ValueError(f"{row['id']} translated fixed subslot {index} exceeds original width")
        slot_start = 0 if index == 0 else separator_offsets[index - 1] + len(separators[index - 1])
        slot_end = slot_start + len(raw_slot)
        replacement[slot_start:slot_end] = encoded + message_padding(len(raw_slot) - len(encoded))
        encoded_parts.append(encoded)
        slot_records.append(
            {
                "index": index,
                "offset": slot_start,
                "source_len": len(raw_slot),
                "translated_len": len(encoded),
                "control_count": len(translated_controls),
            }
        )

    if len(replacement) != len(raw):
        raise ValueError(f"{row['id']} fixed subslot replacement length mismatch")
    for offset, separator in zip(separator_offsets, separators):
        if replacement[offset : offset + len(separator)] != separator:
            raise ValueError(f"{row['id']} fixed subslot separator moved at 0x{offset:X}")
    if terminator and not replacement.endswith(terminator):
        raise ValueError(f"{row['id']} fixed subslot terminator moved")
    encoded_joined = b"\x00\x00".join(encoded_parts)
    return encoded_joined, terminator, bytes(replacement), {
        "fixed_slot_strategy": "preserve_ctrl_0000_subslot_offsets",
        "fixed_subslots": slot_records,
        "ctrl_0000_separator_offsets": separator_offsets,
        "preserved_trailing_subslot_count": len(raw_slots) - len(translated_slots),
    }


def encode_padded_label(
    text: str,
    width: int,
    code_table: dict[str, int],
    *,
    candidate_code_endian: str,
) -> bytes:
    encoded = encode_text(text, code_table, candidate_code_endian=candidate_code_endian)
    if len(encoded) > width:
        raise ValueError(f"option label {text!r} exceeds original width {width}")
    return encoded + message_padding(width - len(encoded))


def translate_yes_no_option_prefix(
    raw: bytes,
    code_table: dict[str, int],
    *,
    candidate_code_endian: str,
) -> bytes:
    if not raw.startswith(YES_NO_OPTION_PREFIX):
        return raw
    translated = bytearray(raw)
    translated[0 : len(YES_BYTES)] = encode_padded_label(
        "\u662f",
        len(YES_BYTES),
        code_table,
        candidate_code_endian=candidate_code_endian,
    )
    no_start = len(YES_BYTES) + 2
    translated[no_start : no_start + len(NO_BYTES)] = encode_padded_label(
        "\u5426",
        len(NO_BYTES),
        code_table,
        candidate_code_endian=candidate_code_endian,
    )
    return bytes(translated)


def message_stream_prefix_and_text(row: dict[str, str], raw: bytes) -> tuple[bytes, str, str]:
    zh_text = normalized_message_text(row)
    jp_text = row.get("jp_text", "")
    terminator = b"\x03\x00" if raw.endswith(b"\x03\x00") else b""
    payload = raw[: -len(terminator)] if terminator else raw
    quote_pos = payload.find(b"\x81\x75")
    if quote_pos > 0 and not jp_text.startswith(OPEN_QUOTES[0]):
        clean = strip_leading_structure_text(zh_text)
        if not clean.startswith(OPEN_QUOTES):
            clean = OPEN_QUOTES[0] + clean
        return raw[:quote_pos], clean, "preserve_prefix_before_open_quote"
    if raw.startswith(b"\x81\x75"):
        clean = strip_leading_structure_text(zh_text)
        if jp_text.startswith(OPEN_QUOTES[0]) and not clean.startswith(OPEN_QUOTES):
            clean = OPEN_QUOTES[0] + clean
        return b"", clean, "open_quote_text"
    if (
        len(payload) >= 4
        and payload[1] == 0
        and is_sjis_lead(payload[2])
        and is_sjis_trail(payload[3])
    ):
        return payload[:2], zh_text, "preserve_prefix_before_sjis_text"
    return b"", zh_text, "plain_message_text"


def message_scene_tail(raw: bytes) -> bytes:
    if len(raw) < 3 or raw[-3:-1] != b"\x01\x01":
        return b""
    if not 0x20 <= raw[-1] <= 0x7E:
        return b""
    if len(raw) >= 5 and raw[-5:-3] == b"\x01\x00":
        return raw[-5:]
    return raw[-3:]


def text_without_scene_tail(text: str, scene_tail: bytes) -> str:
    marker = SCENE_TAIL_WITH_BREAK_CTRL if scene_tail.startswith(b"\x01\x00") else SCENE_TAIL_CTRL
    marker_pos = text.rfind(marker)
    if marker_pos < 0 and marker != SCENE_TAIL_CTRL:
        marker_pos = text.rfind(SCENE_TAIL_CTRL)
    if marker_pos < 0:
        return text
    return text[:marker_pos].rstrip()


def message_padding(length: int) -> bytes:
    if length < 0:
        raise ValueError("negative message padding")
    return b"\x81\x40" * (length // 2) + (b"\x20" if length % 2 else b"")


def message_control_padding(length: int) -> bytes:
    if length < 0:
        raise ValueError("negative message control padding")
    return message_padding(length)


def fixed_slot_padding(row: dict[str, str], length: int) -> tuple[bytes, str]:
    if length < 0:
        raise ValueError("negative fixed slot padding")
    source_file = normalize_source_file(row.get("source_file", ""))
    if source_file in SPACE_PADDED_FIXED_SLOT_SOURCE_FILES:
        return message_padding(length), "fullwidth_space_fixed_slot"
    return bytes(length), "zero_fixed_slot"


def make_message_stream_replacement(
    row: dict[str, str],
    *,
    raw: bytes,
    source_len: int,
    terminator: bytes,
    code_table: dict[str, int],
    candidate_code_endian: str,
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    prefix, text, strategy = message_stream_prefix_and_text(row, raw)
    is_scene_tail = terminator != b"\x03\x00"
    if is_scene_tail:
        text = text_without_scene_tail(text, terminator)
        strategy += "_preserve_scene_tail"
    prefix_extra: dict[str, Any] = {}
    if row.get("id", "") in TRANSLATABLE_MESSAGE_PREFIX_ROW_IDS:
        prefix, text, prefix_extra = translate_fixed_message_prefix(
            row,
            prefix,
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        strategy = "translate_fixed_prefix_before_open_quote"
    if prefix.startswith(YES_NO_OPTION_PREFIX):
        prefix = translate_yes_no_option_prefix(
            prefix,
            code_table,
            candidate_code_endian=candidate_code_endian,
        )
        text = text_after_translated_yes_no_prefix(row.get("zh_text_candidate_payload", ""))
        strategy = "preserve_translated_yes_no_option_prefix_before_open_quote"
    encoded = encode_text(text, code_table, candidate_code_endian=candidate_code_endian)
    payload_capacity = source_len - len(prefix) - len(terminator)
    if payload_capacity < 0:
        raise ValueError(f"{row['id']} message prefix exceeds source length")
    if len(encoded) > payload_capacity:
        raise ValueError(f"{row['id']} encoded message length exceeds payload capacity")
    replacement = prefix + encoded + message_control_padding(payload_capacity - len(encoded)) + terminator
    if len(replacement) != source_len:
        raise ValueError(f"{row['id']} message replacement length mismatch")
    return encoded, terminator, replacement, {
        "message_stream_strategy": strategy,
        "message_prefix_len": len(prefix),
        "message_terminator_position": "preserved_original_end",
        "message_terminator_kind": "scene_tail" if is_scene_tail else "03_00",
        "message_padding_len": payload_capacity - len(encoded),
        "message_padding_strategy": "fullwidth_space_fill_before_original_terminator",
        **prefix_extra,
    }


def make_replacement(
    row: dict[str, str],
    *,
    code_table: dict[str, int] | None = None,
    candidate_code_endian: str = "big",
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    raw = parse_hex_bytes(row.get("raw_hex", ""))
    encoded = parse_hex_bytes(row.get("encoded_hex_candidate", ""))
    terminator = parse_hex_bytes(row.get("raw_terminator_hex", ""))
    source_len = int(row["source_byte_len"])
    payload_capacity = int(row["payload_capacity"])
    extra: dict[str, Any] = {}
    text_override = text_override_for_row(row)
    if text_override is not None and code_table is not None:
        encoded = encode_text(text_override, code_table, candidate_code_endian=candidate_code_endian)
        extra["text_override"] = "yes"
    if row.get("id", "") in LOCAL_FIXED_TEXT_SPAN_REPLACEMENTS and code_table is not None:
        return make_local_fixed_text_span_replacement(
            row,
            raw=raw,
            terminator=terminator,
            code_table=code_table,
            candidate_code_endian=candidate_code_endian,
        )
    if (
        row.get("category") == "message"
        and normalize_source_file(row.get("source_file", "")) in FIXED_SUBSLOT_SOURCE_FILES
        and "{CTRL_0000}" in row.get("jp_text", "")
        and code_table is not None
    ):
        return make_fixed_subslot_replacement(
            row,
            raw=raw,
            terminator=terminator,
            code_table=code_table,
            candidate_code_endian=candidate_code_endian,
        )
    if row.get("category") == "message" and raw.startswith(YES_NO_OPTION_PREFIX) and code_table is not None:
        quote_pos = raw.find(b"\x81\x75")
        if quote_pos < 0:
            replacement = translate_yes_no_option_prefix(
                raw,
                code_table,
                candidate_code_endian=candidate_code_endian,
            )
            return b"", terminator, replacement, {
                "message_stream_strategy": "preserve_binary_tail_translate_yes_no_options",
                "message_padding_len": 0,
                "message_padding_strategy": "preserve_original_tail",
            }
    if (
        row.get("category") == "message"
        and code_table is not None
        and (terminator == b"\x03\x00" or message_scene_tail(raw))
    ):
        message_terminator = terminator or message_scene_tail(raw)
        return make_message_stream_replacement(
            row,
            raw=raw,
            source_len=source_len,
            terminator=message_terminator,
            code_table=code_table,
            candidate_code_endian=candidate_code_endian,
        )
    if len(encoded) > payload_capacity:
        raise ValueError(f"{row['id']} encoded length exceeds payload capacity")

    if terminator:
        used_len = len(encoded) + len(terminator)
        if used_len > source_len:
            raise ValueError(f"{row['id']} replacement exceeds original record length")
        replacement = encoded + terminator + bytes(source_len - used_len)
        extra["padding_strategy"] = "zero_after_terminator"
    else:
        if len(encoded) > source_len:
            raise ValueError(f"{row['id']} replacement exceeds fixed field length")
        padding, strategy = fixed_slot_padding(row, source_len - len(encoded))
        replacement = encoded + padding
        extra["padding_strategy"] = strategy
    return encoded, terminator, replacement, extra


def target_for_row(work: Path, row: dict[str, str]) -> Path:
    rel = Path(*Path(row["source_file"]).parts)
    target = work / "data" / rel
    if not target.is_file():
        target = work / "data" / "text" / rel
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def validate_no_overlaps(work: Path, samples: list[dict[str, str]]) -> dict[str, Any]:
    by_file: dict[Path, list[tuple[int, int, str]]] = {}
    for row in samples:
        target = target_for_row(work, row)
        offset = int(row["offset"], 0)
        source_len = int(row["source_byte_len"])
        by_file.setdefault(target, []).append((offset, offset + source_len, row["id"]))

    overlaps: list[dict[str, Any]] = []
    for target, ranges in by_file.items():
        ranges.sort()
        previous: tuple[int, int, str] | None = None
        for current in ranges:
            if previous and current[0] < previous[1]:
                overlaps.append(
                    {
                        "file": target.as_posix(),
                        "previous_id": previous[2],
                        "previous_range": [previous[0], previous[1]],
                        "current_id": current[2],
                        "current_range": [current[0], current[1]],
                    }
                )
            previous = current
    if overlaps:
        raise ValueError(f"full writeback ranges overlap: {overlaps[:20]}")
    return {
        "file_count": len(by_file),
        "row_count": len(samples),
    }


def patch_samples(
    work: Path,
    samples: list[dict[str, str]],
    *,
    keep_sample_text: bool,
    code_table: dict[str, int] | None = None,
    candidate_code_endian: str = "big",
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in samples:
        target = target_for_row(work, row)
        offset = int(row["offset"], 0)
        source_len = int(row["source_byte_len"])
        encoded, terminator, replacement, extra = make_replacement(
            row,
            code_table=code_table,
            candidate_code_endian=candidate_code_endian,
        )

        data = bytearray(target.read_bytes())
        original = bytes(data[offset : offset + source_len])
        if len(original) != source_len:
            raise ValueError(f"{row['id']} original slice is truncated")
        data[offset : offset + source_len] = replacement
        target.write_bytes(data)

        record: dict[str, Any] = {
            "id": row["id"],
            "source_file": row["source_file"],
            "work_file": target.as_posix(),
            "offset": row["offset"],
            "source_byte_len": source_len,
            "payload_capacity": int(row["payload_capacity"]),
            "encoded_len_candidate": len(encoded),
            "terminator_hex": terminator.hex(" ").upper(),
            "fill_zero_count": len(replacement) - len(encoded) - len(terminator),
            "risk_flags": row.get("risk_flags", ""),
            **extra,
        }
        if keep_sample_text:
            record.update(
                {
                    "jp_text": row.get("jp_text", ""),
                    "zh_text": row.get("zh_text_candidate_payload", ""),
                    "encoded_hex_candidate": row.get("encoded_hex_candidate", ""),
                    "original_hex": original.hex(" ").upper(),
                    "replacement_hex": replacement.hex(" ").upper(),
                }
            )
        records.append(record)
    return records


def build(args: argparse.Namespace) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    repo = Path(__file__).resolve().parents[1]
    origin_work = repo / "rom" / "unpacked" / "origin"
    if not origin_work.is_dir():
        raise FileNotFoundError(f"missing unpacked origin: {origin_work}")

    requested_work = (repo / args.work).resolve()
    requested_output = (repo / args.output).resolve()
    if requested_output.name.lower() == "origin.nds":
        raise ValueError("refusing to overwrite rom/origin.nds")
    work = unique_path(requested_work)
    output_rom = unique_path(requested_output)

    shutil.copytree(origin_work, work)
    files = font_rom.copy_font_files((repo / args.font_dir).resolve(), work)
    font_rom.validate_font_files(files)

    if args.all:
        excluded_source_files = parse_source_file_set(args.exclude_source_files)
        samples, excluded_counts = load_all_rows(repo / args.preview, excluded_source_files)
        mode = "all_fixed_slot"
    else:
        sample_ids = [part.strip() for part in args.sample_ids.split(",") if part.strip()]
        samples = load_samples(repo / args.preview, sample_ids)
        excluded_counts = {}
        mode = "sample"
    validation = validate_no_overlaps(work, samples)
    code_table = load_code_table(repo / args.code_table)
    records = patch_samples(
        work,
        samples,
        keep_sample_text=not args.compact_records,
        code_table=code_table,
        candidate_code_endian=args.candidate_code_endian,
    )

    font_rom.cache.patch_arm9(work / "arm9.bin")
    font_rom.cache.patch_overlay(work / "overlay" / "overlay_0000.bin")
    font_rom.split.repack(repo, work, output_rom)
    metadata = {
        "mode": mode,
        "validation": validation,
        "writeback_policy": {
            "chinese_code_endian": "big_candidate",
            "ascii": "single_byte_candidate",
            "trailing_padding": "strip_and_zero_fill",
            "terminator": "preserve_raw_terminator_when_present",
            "message_stream": "preserve_prefix_and_original_terminator_or_scene_tail_with_fullwidth_space_fill",
            "fixed_slot_without_terminator": "space_pad_known_ui_text_tables_else_zero_fill",
            "rom_origin": "read_only_not_modified",
            "excluded_source_files": excluded_counts,
            "included_row_ids_when_source_excluded": sorted(DEFAULT_INCLUDED_ROW_IDS_WHEN_SOURCE_EXCLUDED),
        },
    }
    return work, output_rom, records, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a small text writeback smoke ROM.")
    parser.add_argument("--preview", default="text/writeback/encoded_preview.tsv")
    parser.add_argument("--font-dir", default="plan/cache/text-writeback-smoke/font-build-smoke-sjis-code-table")
    parser.add_argument("--work", default="rom/unpacked/text_writeback_smoke")
    parser.add_argument("--output", default="rom/text_writeback_smoke.nds")
    parser.add_argument("--sample-ids", default=",".join(DEFAULT_SAMPLE_IDS))
    parser.add_argument("--records-out", default="plan/cache/text-writeback-smoke/sample-writeback-records.json")
    parser.add_argument("--all", action="store_true", help="Write every fixed-slot encoded preview row.")
    parser.add_argument("--code-table", default="text/code_table/zh_code_table.tsv")
    parser.add_argument("--candidate-code-endian", choices=("big", "little"), default="big")
    parser.add_argument(
        "--exclude-source-files",
        default=",".join(sorted(DEFAULT_EXCLUDED_SOURCE_FILES)),
        help="Comma-separated source_file values to leave unmodified in full writeback mode.",
    )
    parser.add_argument("--compact-records", action="store_true", help="Keep per-row records compact for full writeback.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work, output_rom, records, metadata = build(args)
    records_path = Path(args.records_out)
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text(
        json.dumps(
            {
                "work": work.as_posix(),
                "output_rom": output_rom.as_posix(),
                **metadata,
                "sample_count": len(records),
                "samples": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"work={work}")
    print(f"output={output_rom}")
    print(f"records={records_path}")
    print(f"samples={len(records)}")
    print(f"mode={metadata['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
