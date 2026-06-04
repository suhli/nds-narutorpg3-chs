from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROCESS_BLOCKS = {
    "overlay_0000": 0x2F6AC,
    "overlay_0001": 0x1EC60,
    "overlay_0002": 0x128B8,
    "overlay_0003": 0x42A60,
    "overlay_0004": 0x5270,
}

FIELDS = [
    "id",
    "component",
    "source_file",
    "offset",
    "raw_len",
    "slot_len",
    "raw_hex",
    "jp_text",
    "jp_key",
    "zh_text",
    "translation_source",
    "encoded_hex",
    "encoded_len",
    "capacity_delta",
    "missing_chars",
    "status",
    "notes",
]

LOCAL_TRANSLATIONS = {
    "エラーコード": "错误代码",
    "たいせんネーム": "对战名称",
    "あんぶ": "暗部",
    "ネジ": "宁次",
    "キバ": "牙",
    "猿魔": "猿魔",
    "守鶴": "守鹤",
    "ガイ": "阿凯",
    "リー": "小李",
    "ハク": "白",
    "シノ": "志乃",
    "いの": "井野",
    "ガアラ": "我爱罗",
    "ザブザ": "再不斩",
    "たかい": "高",
    "イルカ": "伊鲁卡",
    "サクラ": "小樱",
    "ふつう": "普通",
    "ガマ忠": "蛤蟆忠",
    "ガマ竜": "蛤蟆龙",
    "三代目": "三代目",
    "テマリ": "手鞠",
    "ナルト": "鸣人",
    "ガマ吉": "蛤蟆吉",
    "ヒナタ": "雏田",
    "カツユ": "蛞蝓",
    "八忍犬": "八忍犬",
    "ひくい": "低",
    "イタチ": "鼬",
    "マンダ": "万蛇",
    "サスケ": "佐助",
    "カカシ": "卡卡西",
    "キサメ": "鬼鲛",
    "ツナデ": "纲手",
    "パックン": "帕克",
    "さいてい": "最低",
    "シカマル": "鹿丸",
    "チョウジ": "丁次",
    "テンテン": "天天",
    "じらいや": "自来也",
    "カマタリ": "镰多利",
    "さいこう！": "最高！",
    "カンクロウ": "勘九郎",
    "ガイの忍亀": "凯的忍龟",
    "ガマブン太": "蛤蟆文太",
    "ミニカツユ": "小蛞蝓",
    "オロチまる": "大蛇丸",
    "たいちょう": "队长",
    "そうびちゅう": "装备中",
    "あがる　　　おなじ　　　　　　　　さがる　　　そうびちゅう": "提升　　　相同　　　　　　　　下降　　　装备中",
    "セットできるキャラクター": "可装备角色",
    "そうびじょうたい": "装备状态",
    "たいちょうこうか": "队长效果",
    "やるき": "干劲",
    "げんざいのけいけんち": "当前经验值",
    "つぎのレベルまで　あと": "距下一级还差",
    "%s／%s": "%s／%s",
    "%s／%s　%s／%s": "%s／%s　%s／%s",
    "はい": "是",
    "いいえ": "否",
    "つうしんエラーが　はっせいしました": "发生通信错误",
    "つうしんエラーが　はっせいしました！": "发生通信错误！",
    "チャクラがたりない！": "查克拉不足！",
    "術がふうじられている！": "术被封印！",
    "にげられなかった・・・": "没能逃走…",
    "にげられない！": "无法逃走！",
    "は　おちこんでいる・・・": "正在沮丧…",
    "は　鼻血をふいた！！": "流鼻血了！！",
    "しゅっけつたりょうで　動けない・・・": "出血过多，无法动弹…",
    "は　こっそりみている": "正在偷偷看",
    "は　鼻の下がのびている": "正在偷看",
    "いどう": "移动",
    "こうたい": "替换",
    "もどる": "返回",
    "ぼうぎょ": "防御",
    "にげる": "逃跑",
    "ぜんたい": "全体",
    "チャクラ": "查克拉",
    "こすう": "数量",
    "術が　ふうじられています！": "术已被封印！",
    "チャクラが　たりません！": "查克拉不足！",
    "そうびで　術が　ふうじられています！": "装备使术被封印！",
    "たいせんでは　つかえません": "对战中不能使用",
    "きんじゅつは　つかえません": "禁术不能使用",
    "いまは　つかえません": "现在不能使用",
    "かげ分身": "影分身",
    "しゃりんがん": "写轮眼",
    "びゃくがん": "白眼",
    "八門とんこう": "八门遁甲",
    "うちなるサクラ": "内在小樱",
    "じょうたいで　つかえます": "该状态下可用",
    "チャクラねり　なし": "无查克拉凝聚",
    "チャクラねり　あり": "有查克拉凝聚",
    "こうげき": "攻击",
    "じゅつ": "忍术",
    "どうぐ": "道具",
    "ぼうぐ": "防具",
    "もどす": "放回",
    "うる": "出售",
    "を　てにいれた！": "获得了！",
    "ガマちゃんをすべてあつめました！！": "蛤蟆全收集！！",
    "やめる": "退出",
    "０１２３４５６７８９？ー": "０１２３４５６７８９？ー",
    "みる": "查看",
    "つかう": "使用",
    "だいじなもの": "重要物",
    "%sの": "%s的",
    "全体の": "全体的",
    "%sスタミナと　チャクラが　かいふくした！": "%s体力和查克拉恢复了！",
    "%sスタミナが　かいふくした！": "%s体力恢复了！",
    "%sチャクラが　かいふくした！": "%s查克拉恢复了！",
    "%sさいだいスタミナが　%sふえた！": "%s最大体力增加%s！",
    "%sさいだいチャクラが　%sふえた！": "%s最大查克拉增加%s！",
    "%sこうげき力が　%sふえた！": "%s攻击力增加%s！",
    "%sぼうぎょ力が　%sふえた！": "%s防御力增加%s！",
    "%sすばやさが　%sふえた！": "%s速度增加%s！",
    "%sにんりょくが　%sふえた！": "%s忍力增加%s！",
    "%sやるきが　あがった！": "%s干劲提升！",
    "%sやるきが　さがった！": "%s干劲下降！",
    "%sを": "%s",
    "トントン": "豚豚",
    "%s口よせした！": "%s通灵了！",
    "しょうひ": "消耗",
    "にんりょく：": "忍力：",
    "前：": "前：",
    "中：": "中：",
    "後：": "后：",
    "すばやさ%s": "速度%s",
    "術をみる": "查看术",
    "しのび札をみる": "查看忍识卡",
    "こうげき　ぼうぎょ　すばやさ": "攻击　防御　速度",
    "モンスター": "怪物",
    "そうびなし": "无装备",
    "ぶき": "武器",
    "ぶき　　　　　　　　　　　　　　　　　　　ぼうぐ　　　　　　　　　　　　　　　　　　きゃはん": "武器　　　　　　　　　　　　　　　　　　　防具　　　　　　　　　　　　　　　　　　护腿",
    "そうび": "装备",
    "メンバー": "成员",
    "じんけい": "阵型",
    "ユーザー": "用户",
    "しのび札": "忍识卡",
    "ステータス": "状态",
    "？？？？？？？？？？？？？": "？？？？？？？？？？？？？",
    "はずす": "卸下",
    "たいせいけいしのび札": "体术系忍识卡",
    "とくしゅけいしのび札": "特殊系忍识卡",
    "ステータスけいしのび札": "状态系忍识卡",
    "にんじゅつけいしのび札": "忍术系忍识卡",
    "／%s": "／%s",
    "スタミナ　チャクラ　　　　　　こうげき　ぼうぎょ　すばやさ　　　　　　にんりょく": "体力　查克拉　　　　　　攻击　防御　速度　　　　　　忍力",
    "スタミナ　　チャクラ　　　　　　　　こうげき　　ぼうぎょ　　すばやさ　　　　　　　　にんりょく": "体力　　查克拉　　　　　　　　攻击　　防御　　速度　　　　　　　　忍力",
    "　　　　　　　　　　　　スタミナ　　チャクラ　　　　　　　　こうげき　　ぼうぎょ　　すばやさ　　　　　　　　にんりょく": "　　　　　　　　　　　　体力　　查克拉　　　　　　　　攻击　　防御　　速度　　　　　　　　忍力",
    "レベル　　　　スタミナ　　　チャクラ　　　こうげき　　　ぼうぎょ　　　すばやさ　　　にんりょく　　　　　　　　　おぼえたじゅつ": "等级　　　　体力　　　查克拉　　　攻击　　　防御　　　速度　　　忍力　　　　　　　　　习得忍术",
    "たいちょうせってい": "队长设置",
    "さと": "村子",
    "なまえ": "名字",
    "ひとこと": "一句话",
    "里のせってい": "村子设置",
    "リストをみる": "查看列表",
    "ともだちリスト": "好友列表",
    "なまえのせってい": "名字设置",
    "たいせんせいせき": "对战成绩",
    "なまえのへんこう": "更改名字",
    "リストからはずす": "从列表移除",
    "たいせんせってい": "对战设置",
    "せいせきかくにん": "确认成绩",
    "ひとことのせってい": "一句话设置",
    "ＷｉーＦｉポイント": "Wi-Fi点数",
    "あなたのともだちコード": "你的好友代码",
    "ともだちコードとうろく": "登记好友代码",
    "ともだちコードかくにん": "确认好友代码",
    "ねだん": "价格",
    "ごうけい": "合计",
    "ざんきん": "余额",
    "こうにゅうするかず": "购买数量",
    "てにいれた": "获得了",
    "ふたりめ": "第二人",
    "よにんめ": "第四人",
    "ひとりめ": "第一人",
    "さんにんめ": "第三人",
    "もっているかず": "持有数量",
    "うるかず": "出售数量",
    "ＬＶアップまで": "距LV提升",
    "それぞれ%s": "各自%s",
    "%sは%s": "%s是%s",
    "は　レベルがあがった！": "升级了！",
    "の　やるきが": "的干劲",
    "くちよせシートを　おいて　　　　　　あんごうを　にゅうりょくせよ！": "放置通灵纸，输入暗号！",
    "しょう": "奖",
    "ポイント": "点数",
    "セーブファイル・臨": "存档文件・临",
    "セーブファイル・兵": "存档文件・兵",
    "%s　%s：%s：%s": "%s　%s：%s：%s",
    "データが　ありません": "没有数据",
    "データが　こわれています": "数据损坏",
    "%s　００：００：００": "%s　００：００：００",
    "データなし": "无数据",
    "はそんデータファイル": "损坏的存档",
    "ーー": "－－",
    "中忍": "中忍",
    "下忍": "下忍",
    "上忍": "上忍",
    "ーーーー": "－－－－",
    "はじめから": "开始",
    "ＷｉーＦｉせってい": "通信设置",
    "ともだちにくばる": "分发好友",
    "つづきから": "继续",
    "ファイルさくじょ": "删除存档",
    "サウンドテスト": "声音测试",
    "ＢＧＭ": "ＢＧＭ",
    "キャラクター": "角色",
    "ボイス": "语音",
    "ていし": "停止",
    "さいせい": "播放",
}

LOCAL_TRANSLATIONS["\u305d\u3046\u3073\u3092\u307f\u308b"] = "\u67e5\u770b\u88c5\u5907"

MANUAL_CANDIDATES = (
    {
        "id": "menu_overlay_0003_0441F0",
        "component": "overlay_0003",
        "source_file": "overlay/overlay_0003.bin",
        "offset": "0x441F0",
        "raw_len": "12",
        "slot_len": "16",
        "raw_hex": "82 BB 82 A4 82 D1 82 F0 82 DD 82 E9",
        "jp_text": "\u305d\u3046\u3073\u3092\u307f\u308b",
        "jp_text_stripped": "\u305d\u3046\u3073\u3092\u307f\u308b",
        "zh_text": "",
        "status": "candidate",
        "notes": "manual fixed-slot entry omitted by scanner",
    },
)

ROW_TRANSLATION_OVERRIDES = {
    "menu_overlay_0002_0128B8": "　　　　　　　　　　　获得了！",
}

FIXED_WIDTH_ROW_REPLACEMENTS = {
    "menu_overlay_0000_030270": (
        ("スタミナ", "体力　　"),
        ("チャクラ", "查克拉　"),
        ("こうげき", "攻击　　"),
        ("ぼうぎょ", "防御　　"),
        ("すばやさ", "速度　　"),
        ("にんりょく", "忍力　　　"),
    ),
    "menu_overlay_0003_0450A0": (
        ("レベル", "等级　"),
        ("スタミナ", "体力　　"),
        ("チャクラ", "查克拉　"),
        ("こうげき", "攻击　　"),
        ("ぼうぎょ", "防御　　"),
        ("すばやさ", "速度　　"),
        ("にんりょく", "忍力　　　"),
        ("おぼえたじゅつ", "习得忍术　　　"),
    ),
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def normalize(text: str) -> str:
    return (text or "").strip(" \u3000")


def fixed_width_row_translation(row: dict[str, str]) -> str | None:
    replacements = FIXED_WIDTH_ROW_REPLACEMENTS.get(row.get("id", ""))
    if not replacements:
        return None

    text = bytes.fromhex(row["raw_hex"]).decode("cp932")
    for source, target in replacements:
        if len(source) != len(target):
            raise ValueError(f"fixed-width replacement length mismatch: {source!r} -> {target!r}")
        if source not in text:
            raise ValueError(f"fixed-width source label not found in {row['id']}: {source!r}")
        text = text.replace(source, target, 1)
    return text


def selected_candidate(row: dict[str, str]) -> bool:
    component = row.get("component", "")
    if component not in PROCESS_BLOCKS:
        return False
    return int(row.get("offset", "0"), 0) >= PROCESS_BLOCKS[component]


def load_reuse_translations(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for row in read_rows(path):
        jp = normalize(row.get("jp_text", ""))
        zh = normalize((row.get("zh_text", "") or "").rstrip(" "))
        if jp and zh:
            out.setdefault(jp, zh)
    return out


def load_code_table(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in read_rows(path):
        char = row.get("char", "")
        code = row.get("code_hex", "")
        if char and code:
            out[char] = int(code, 16)
    return out


def encode_text(text: str, code_table: dict[str, int]) -> tuple[bytes, list[str]]:
    out = bytearray()
    missing: list[str] = []
    for char in text:
        if char in code_table:
            out.extend(code_table[char].to_bytes(2, "big"))
            continue
        try:
            encoded = char.encode("cp932")
        except UnicodeEncodeError:
            if char not in missing:
                missing.append(char)
            continue
        out.extend(encoded)
    return bytes(out), missing


def choose_translation(key: str, reuse: dict[str, str]) -> tuple[str, str]:
    if key in LOCAL_TRANSLATIONS:
        return LOCAL_TRANSLATIONS[key], "local_menu_dictionary"
    if key in reuse:
        return reuse[key], "reused_frozen_translation"
    return "", "pending_translation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare fixed-slot overlay menu translations.")
    parser.add_argument("--candidates", default="text/menu/overlay_menu_candidates.tsv")
    parser.add_argument("--reuse", default="text/code_table/frozen_translation.tsv")
    parser.add_argument("--code-table", default="text/code_table/zh_code_table.tsv")
    parser.add_argument("--out", default="text/menu/overlay_menu_translations.tsv")
    parser.add_argument("--report-out", default="text/menu/overlay_menu_translation_report.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = [row for row in read_rows(Path(args.candidates)) if selected_candidate(row)]
    candidate_ids = {row["id"] for row in candidates}
    candidates.extend(row.copy() for row in MANUAL_CANDIDATES if row["id"] not in candidate_ids)
    reuse = load_reuse_translations(Path(args.reuse))
    code_table = load_code_table(Path(args.code_table))
    rows: list[dict[str, Any]] = []
    missing_keys: list[str] = []
    missing_chars: set[str] = set()
    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for row in candidates:
        key = normalize(row["jp_text"])
        fixed_width_override = fixed_width_row_translation(row)
        row_override = ROW_TRANSLATION_OVERRIDES.get(row.get("id", ""))
        if fixed_width_override is not None:
            zh_text, source = fixed_width_override, "row_fixed_width_override"
        elif row_override:
            zh_text, source = row_override, "row_menu_override"
        else:
            zh_text, source = choose_translation(key, reuse)
        encoded, missing = encode_text(zh_text, code_table) if zh_text else (b"", [])
        slot_len = int(row["slot_len"])
        capacity_delta = slot_len - len(encoded)
        if not zh_text:
            status = "pending_translation"
            missing_keys.append(key)
        elif missing:
            status = "pending_font_chars"
            missing_chars.update(missing)
        elif capacity_delta < 0:
            status = "blocked_overflow"
        else:
            status = "ready"
        status_counts[status] += 1
        source_counts[source] += 1
        rows.append(
            {
                **row,
                "jp_key": key,
                "zh_text": zh_text,
                "translation_source": source,
                "encoded_hex": " ".join(f"{byte:02X}" for byte in encoded),
                "encoded_len": len(encoded) if zh_text else "",
                "capacity_delta": capacity_delta if zh_text else "",
                "missing_chars": "".join(missing),
                "status": status,
                "notes": row.get("notes", ""),
            }
        )

    write_rows(Path(args.out), rows, FIELDS)
    report = {
        "inputs": {
            "candidates": args.candidates,
            "reuse": args.reuse,
            "code_table": args.code_table,
        },
        "outputs": {"translations": args.out, "report": args.report_out},
        "selected_rows": len(rows),
        "unique_keys": len({row["jp_key"] for row in rows}),
        "status_counts": dict(sorted(status_counts.items())),
        "translation_source_counts": dict(sorted(source_counts.items())),
        "pending_keys": sorted(set(missing_keys)),
        "missing_font_chars": "".join(sorted(missing_chars)),
    }
    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    blocked_statuses = ("pending_translation", "blocked_overflow")
    return 1 if any(status_counts.get(status) for status in blocked_statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
