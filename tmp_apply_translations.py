import csv
import re
from pathlib import Path

TRANS = {
    "0191": {
        0: "@{CTRL_0000}{CTRL_0200}{CTRL_0002}{CTRL_4000}{CTRL_8100}u他们连第三面镜子也拿到了吗」",
        1: "A{CTRL_0000}{CTRL_0200}{CTRL_0002}{CTRL_4100}{CTRL_8100}u非常抱歉{CTRL_0001}我们稍微有些玩过头了」",
        2: "@{CTRL_0000}{CTRL_0200}{CTRL_0002}{CTRL_4000}{CTRL_8100}u也好　只要他们替我们去找镜子{CTRL_0001}我们也能省些工夫」{CTRL_0001}「对了　灵兽的状态如何？」",
        3: "A{CTRL_0000}{CTRL_0200}{CTRL_0002}{CTRL_4100}{CTRL_8100}u已经越来越接近完全体了」",
        4: "B{CTRL_0200}{CTRL_0200}{CTRL_0002}{CTRL_4200}{CTRL_8100}u邪气也扩散得相当厉害　各地都{CTRL_0001}开始爆发动乱了」",
        5: "A{CTRL_0200}{CTRL_0200}{CTRL_0002}{CTRL_4100}{CTRL_8100}u等灵兽变成完全体的时候{CTRL_0001}木叶也应该会被邪气笼罩」",
        6: "@{CTRL_0200}{CTRL_0200}{CTRL_0002}{CTRL_4000}{CTRL_8100}u是吗　真叫人期待　呵呵」",
    },
    "0192": {
        0: "「纲手婆婆！找到镜子了{CTRL_0001}说到做到！」",
        1: "「你们来得正好」",
        2: "呃？",
        3: "「现在　{CTRL_0103}{CTRL_0002}砂隐村{CTRL_0103}{CTRL_0000}那边{CTRL_0001}有使者来报」",
        4: "「啊　手鞠！」",
        5: "「出什么事了？」",
        6: "「灵兽的邪气{CTRL_0001}正在逼近砂隐」",
        7: "「到砂隐了吗！？」",
        8: "「邪气造成的灾害{CTRL_0001}已经在各地扩散」",
        9: "「这样下去　砂隐也撑不了多久」",
        10: "「这么说来　木叶也会变得不妙啊」",
        11: "「得赶紧去找剩下的镜子！」",
        12: "「你们接下来要立刻前往{CTRL_0103}{CTRL_0002}砂隐村{CTRL_0001}{CTRL_0103}{CTRL_0000}」",
        13: "砂隐？",
        14: "「是去砂隐支援吗？」",
        15: "「就凭你们几个　不来帮忙{CTRL_0001}砂隐靠我们自己也没问题」",
        16: "「那为什么？」",
        17: "「我们收到情报　砂隐村里某处有镜子{CTRL_0001}」",
        18: "「哦…真的吗！？ 」",
        19: "「嗯　据说村里有个{CTRL_0001}知道镜子下落的老人」",
        20: "「我已经先派了{CTRL_0103}{CTRL_0002}日向宁次　{CTRL_0101}{CTRL_0014}小李{CTRL_0101}{CTRL_0014}{CTRL_0001}天天{CTRL_0103}{CTRL_0000}三人过去」",
        21: "「你们也立刻追上去{CTRL_0001}和他们会合」",
        22: "「明白了！」",
        23: "「鹿丸！　马上出发！」",
        24: "「拿你没辙」",
        25: "「木叶和砂隐是同盟国！{CTRL_0001}出了事当然要帮忙」",
        26: "「而且我们还欠砂隐人情」",
        27: "「你这家伙　还挺讲义气啊」",
        28: "「才不是呢！」",
        29: "「鸣人　快走吧」",
        30: "6{CTRL_0000}{CTRL_0200}{CTRL_0002}{CTRL_3600}{CTRL_8100}u请稍等一下」",
        31: "「噗！{CTRL_0301}{CTRL_0082}{CTRL_0000}{CTRL_0000}噗！」",
        32: "「{CTRL_0103}{CTRL_0002}豚豚{CTRL_0103}{CTRL_0000}…？」",
        33: "「鸣人！　你之前不是{CTRL_0001}说被岩石挡住走不过去吗」",
        34: "「你不是说路过不去{CTRL_0001}吗？」",
        35: "「我是说过！」",
        36: "「那种时候就把{CTRL_0103}{CTRL_0002}这家伙叫出来{CTRL_0001}在岩石前按一下A键试试！{CTRL_0103}{CTRL_0000}」",
        37: "「这家伙可以把{CTRL_0103}{CTRL_0002}岩石敲碎{CTRL_0001}这样你就能继续前进了{CTRL_0103}{CTRL_0000}」",
        38: "「太厉害了！豚豚！！」",
        39: "「噗！！」",
        40: "「和蛞蝓一样　它也应该能在很多地方{CTRL_0001}帮上忙」",
        41: "「・・・那我就确实{CTRL_0001}把它交给你了！！」",
        42: "学会了口寄宠物“豚豚”！",
        43: "豚豚成为同伴了！{CTRL_0001}以后可以带着豚豚一起行动了！",
        44: "6{CTRL_0000}{CTRL_0200}{CTRL_0002}{CTRL_3600}{CTRL_8100}u纲手！」",
        45: "「啊…差点忘了」",
        46: "「我正想着把这家伙借给你呢」",
        47: "「谢谢你！　纲手婆婆！！」",
    },
}

CTRL_RE = re.compile(r"\{CTRL_[0-9A-Fa-f]{4}\}")


def serialized_len(text: str) -> int:
    total = 0
    pos = 0
    for m in CTRL_RE.finditer(text):
        total += len(text[pos:m.start()].encode("utf-8"))
        total += 2
        pos = m.end()
    total += len(text[pos:].encode("utf-8"))
    return total


def run() -> None:
    for chunk in ("0191", "0192"):
        src = Path(f"text/translation/chunks/source/chunk_{chunk}.tsv")
        dst = Path(f"text/translation/chunks/translated/chunk_{chunk}.tsv")
        with src.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            fields = reader.fieldnames
            rows = []
            for row in reader:
                idx = int(row["chunk_row_index"])
                text = TRANS[chunk][idx]
                expected = int(row["source_byte_len"])
                current = serialized_len(text)
                if current > expected:
                    raise ValueError(f"chunk {chunk} row {idx}: {current}>{expected}")
                text += " " * (expected - current)
                row["zh_text"] = text
                row["status"] = "translated_aligned"
                row["length_risk"] = "ok"
                row["translator_note"] = ""
                row["qa_note"] = ""
                rows.append(row)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
    print("ok")


if __name__ == "__main__":
    run()
