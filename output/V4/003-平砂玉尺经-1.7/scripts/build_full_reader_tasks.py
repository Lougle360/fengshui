from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "50-edited" / "modern-reading.md"
OUT = ROOT / "50-edited" / "full-reader-tasks.json"


UNITS = [
    ("FULL-FRONT-001", "main_point", 1, 79, "读完第一编后，请用自己的话讲清全书要解决的核心问题、六步判断链，以及本版为什么要分观察层、传统解释层和疑文层。"),
    ("FULL-PREFACE-001", "distinction", 80, 127, "卷首怎样处理刘秉忠、刘基、赖从谦的题署？请说明‘传本这样署名’与‘实际作者已经得到证明’的区别。"),
    ("FULL-CH1-001", "application", 128, 589, "第一章从昆仑大势转到平原微地形时，真正留给后文的可操作方法是什么？请用一个陌生平地场景说明。"),
    ("FULL-CH2-001", "distinction", 590, 1143, "第二章同时出现二十四山、三合、纳甲和十二长生。请分别说明它们大致在做什么，并指出为什么不能把它们当成同一张表。"),
    ("FULL-CH3-001", "application", 1144, 1583, "第三章怎样区分地势仍在延伸和已经停住？请列出至少两项‘尚行’证据和两项‘住结’证据。"),
    ("FULL-CH4-001", "figure", 1584, 2625, "第四章图式很多。请任选两幅不同问题的图，分别写出应按什么顺序看、图解决什么判断、哪些内容不能从模糊图字中猜补。"),
    ("FULL-CH5-001", "distinction", 2626, 2929, "第五章为什么说砂是相对关系而不只是形状名称？请用护送、朝应、关锁或分泄中的至少两种关系解释。"),
    ("FULL-CH6-001", "main_point", 2930, 3169, "第六章为什么把立向放在最后？请写出立向前需要的输入，并说明面对残缺公式时本版采取什么边界。"),
    ("FULL-CLOSE-001", "other", 3170, 3482, "查阅术语表和末尾六问后，请指出哪三个词最能帮助你复述全书主线，哪一组词仍最容易混淆，并说明原因。"),
]


TERM_QUESTIONS = {
    "砂": "为什么说‘砂’在本书里是关系词而不是沙粒或孤立山丘？请给出一种护持关系和一种外泄关系。",
    "龙": "请解释‘龙’在本书中的操作含义，并说明它与神话动物、现代地质构造有何区别。",
    "气": "本书的‘气’怎样通过水和土形被作者解释？为什么不能把它当作现代可直接测量的物理量？",
    "水": "请区分‘水’作为可观察对象与作为气的证据这两层含义，并说明‘见水’为什么不等于‘见穴’。",
    "水神": "‘水神’在本文中指什么？遇到这个词时应先还原成哪些具体可观察关系？",
    "穴": "‘穴’是判断链的哪一种结果？哪些证据不足以单独把一处平地判为穴？",
    "行龙": "请解释‘行龙’与‘住结’的相反关系，并写出一种表示仍在行走的形态。",
    "入首": "‘入首’位于整条来脉的哪一段？为什么入首清楚与否会影响具体取点？",
    "住结": "本书用哪些相互印证的关系判断住结？只看地面平整为什么不够？",
    "合襟": "‘合襟’提供什么证据？请构造一个有合襟但仍不能直接定穴的反例。",
    "界水": "‘界水’和一般经过的水有什么不同？它可能对土脉起哪三种位置作用？",
    "明堂": "‘明堂’在本书中是什么空间？来水、去水与它有什么关系？",
    "水口": "‘水口’为什么必须在整局中判断？它在审向之前提供什么信息？",
    "来水": "‘来水’以什么为参照？为什么不能简单把它等同于地图上游？",
    "去水": "‘去水’怎样帮助判断外泄和水口？它与来水的参照点是否相同？",
    "护砂": "什么样的相对方向使一处砂成为护砂？为什么离穴很近仍可能不是护砂？",
    "劫砂": "劫砂与护砂的核心差别是什么？为什么头面端正仍可能被劫砂破坏整体关系？",
    "鬼砂": "先用可观察语言描述鬼砂，再说明‘鬼’这个评价标签属于哪一层。",
    "朝应": "当中心脉络不清时，朝应如何帮助反推穴位？它为什么不是固定山名？",
    "朝山": "朝山与近前护砂的距离和作用有何不同？书中为何用朝山校验混杂地形？",
    "玄武": "‘玄武’在本书里标示什么位置关系？为什么不能按神兽实体理解？",
    "向": "请说明‘向’为什么是综合来龙、水口和砂水后的输出，而不是任意起点。",
}


def main() -> None:
    lines = MANUSCRIPT.read_text(encoding="utf-8").splitlines()
    heading = {line: i for i, line in enumerate(lines, 1) if line.startswith("#")}
    ranges = {
        "FULL-FRONT-001": (1, heading["# 第二编：原书逐页现代释文（对照查阅编）"] - 1),
        "FULL-PREFACE-001": (heading["# 第二编：原书逐页现代释文（对照查阅编）"], heading["## 第一章：审势——从水看地势的来路"] - 1),
        "FULL-CH1-001": (heading["## 第一章：审势——从水看地势的来路"], heading["## 第二章：审气——给观察结果加上分类"] - 1),
        "FULL-CH2-001": (heading["## 第二章：审气——给观察结果加上分类"], heading["## 第三章：寻龙——判断仍在走还是已经停"] - 1),
        "FULL-CH3-001": (heading["## 第三章：寻龙——判断仍在走还是已经停"], heading["## 第四章：审穴——从来路找到具体落点"] - 1),
        "FULL-CH4-001": (heading["## 第四章：审穴——从来路找到具体落点"], heading["## 第五章：审砂——用周围形态复核"] - 1),
        "FULL-CH5-001": (heading["## 第五章：审砂——用周围形态复核"], heading["## 第六章：审向——最后才处理方向"] - 1),
        "FULL-CH6-001": (heading["## 第六章：审向——最后才处理方向"], heading["# 附录一：本书术语表"] - 1),
        "FULL-CLOSE-001": (heading["# 附录一：本书术语表"], len(lines)),
    }
    tasks = []
    for tid, kind, start, end, question in UNITS:
        start, end = ranges[tid]
        tasks.append({"id": tid, "kind": kind, "start_line": start, "end_line": end, "question": question})
    aids = json.loads((ROOT / "50-edited" / "reader-aids.json").read_text(encoding="utf-8"))
    by_term = {e["term"]: e for e in aids["glossary"]["entries"]}
    for idx, term in enumerate(TERM_QUESTIONS, 1):
        entry = by_term[term]
        start = next(i for i, line in enumerate(lines, 1) if line == f"## {term}")
        next_heading = next((i for i in range(start + 1, len(lines) + 1) if lines[i - 1].startswith("## ") or lines[i - 1].startswith("# ")), len(lines) + 1)
        tasks.append({
            "id": f"FULL-TERM-{idx:03d}",
            "kind": "distinction" if term in {"水", "行龙", "合襟", "劫砂", "鬼砂", "向"} else "application",
            "start_line": start,
            "end_line": next_heading - 1,
            "terms": [term],
            "question": TERM_QUESTIONS[term],
        })
    OUT.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tasks": len(tasks), "lines": len(lines), "path": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
