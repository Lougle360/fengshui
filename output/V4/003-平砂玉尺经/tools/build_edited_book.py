#!/usr/bin/env python3
"""Build the ordinary-reader V4 edition for Book 002.

The edited layer keeps every modernized block in source order, converts the
display text to Simplified Chinese, and adds visibly labelled reader aids.
No source-derived block is deleted or silently rewritten.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
sys.path.insert(
    0,
    str(PROJECT / "output" / "V4" / "001-青囊海角经" / "tools" / "_vendor"),
)

from opencc import OpenCC  # noqa: E402


SECTIONS = [
    (1, 7, "卷前材料：牌记、序跋、例言与目录", "先了解版本来历、编次说明和全书结构，再进入术法正文。"),
    (8, 27, "卷一·天星", "以二十四山、八卦与星宿为框架，依次说明各宫天星及相关龙法。"),
    (28, 51, "卷二·龙法", "回答如何寻龙、辨帐、辨峡，以及如何识别九星行龙与平洋龙。"),
    (52, 72, "卷三·穴法", "说明点穴的基本观察顺序，并讨论四势、怪穴、阴阳、明堂、葬法与土色。"),
    (73, 79, "卷四·砂说与看砂法", "先辨砂的形体、方位和情势，再进入拨砂、吊冲等判断方法。"),
    (80, 92, "卷五·砂法", "展开分金消砂、二十四山砂法，并分论印砂、青龙白虎、乐山与星体砂。"),
    (93, 110, "卷六·水法基础", "从水势与五种水局起步，进入河图洛书、纳甲、干支与各类水法关系。"),
    (111, 123, "卷七·水法判局", "讨论水的来去、聚散、水口与明堂，并以合局、破局条目记录传统判断。"),
    (124, 135, "卷八·向法与分房", "说明立向、翻卦、洛书紫白与分房方法，并保留原书对罗经用法的辨论。"),
    (136, 154, "卷九·合局与破局图说", "将河图、洛书和方位组合落到具体坐向，并列举黄泉、八煞等传统忌例。"),
    (155, 162, "卷十·阳宅", "从东西四宅、游星与竹节贯井法，讲到门、主、灶及宅元生克的传统说法。"),
]


EDITORIAL_TERMS = {
    "龙": "指山脉或地势连续起伏的走向，不是神话生物。",
    "峦头": "以地形、山水外观与空间关系为主的观察方法。",
    "理气": "以卦、干支、五行、方位和时序关系进行推演的方法。",
    "龙脉": "风水文献中对山脉及其走势的称呼。",
    "结穴": "传统上认为山水形势在某处收束、聚集并形成穴场。",
    "过峡": "龙脉行度中相对收窄、连接前后山体的地段。",
    "入首": "龙脉进入结穴区域前的关键一段。",
    "砂": "穴场周围起护卫、朝应作用的山丘或地形。",
    "穴": "风水中认为地势收束、气脉聚结的位置。",
    "明堂": "穴前相对开阔、有收聚关系的空间。",
    "案山": "穴前较近、形如案几的山体。",
    "朝山": "穴前较远、与穴场形成朝拱关系的山体。",
    "青龙": "穴场左侧形势的传统称呼。",
    "白虎": "穴场右侧形势的传统称呼。",
    "朱雀": "穴场前方形势的传统称呼。",
    "玄武": "穴场后方形势的传统称呼。",
    "水口": "水流进出一地或局势收束的位置。",
    "坐山": "建筑或穴位背靠的方位。",
    "向": "建筑或穴位所朝的方位。",
    "立向": "依特定规则确定坐与向的操作。",
    "二十四山": "将周天分为二十四个方位的系统。",
    "分金": "罗盘中进一步细分坐向度数的方法。",
    "纳甲": "将八卦与天干、地支等相配的术数方法。",
    "翻卦": "按特定次序变换卦爻，以排定星曜或方位吉凶的方法。",
    "游星": "八宅等体系中依门宅方位排布的星名序列。",
    "河图": "术数传统中的数理图式，本书用于解释生成关系。",
    "洛书": "术数传统中的九宫数理图式。",
    "合局": "按本书规则，来水、去水、坐向等相互配合的情形。",
    "破局": "按本书规则，水、向或方位关系不合的情形。",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_display(text: str, converter: OpenCC) -> str:
    text = converter.convert(text or "")
    text = text.replace("\r", "\n")
    text = re.sub(r"[\t\u3000 ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def section_for(page: int):
    for section in SECTIONS:
        if section[0] <= page <= section[1]:
            return section
    raise RuntimeError(f"No editorial section for page {page}")


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    converter = OpenCC("t2s")
    modern_path = ROOT / "40-modernized" / "blocks.jsonl"
    modern = read_jsonl(modern_path)
    uncertainties = read_jsonl(ROOT / "40-modernized" / "uncertainties.jsonl")
    terminology = read_json(ROOT / "40-modernized" / "terminology.json")
    if len(modern) != 903:
        raise RuntimeError(f"Expected 903 modernized blocks, got {len(modern)}")

    notes_by_block = defaultdict(list)
    for note in uncertainties:
        if note.get("block_id"):
            notes_by_block[note["block_id"]].append(note)

    edited_blocks = []
    audit_rows = []
    by_page = defaultdict(list)
    for row in modern:
        item = dict(row)
        item["modern_text"] = clean_display(str(row.get("modern_text") or ""), converter)
        item["operation"] = "edit"
        item["edition_language"] = "zh-Hans"
        item["editorial_section"] = section_for(int(row["source_page"]))[2]
        item["editorial_notes"] = [
            {
                "label": "阅读提示",
                "severity": "medium",
                "reason": "；".join(
                    list(note.get("issues") or []) + list(note.get("uncertainty") or [])
                )[:1200],
            }
            for note in notes_by_block.get(row["block_id"], [])
        ]
        edited_blocks.append(item)
        by_page[int(row["source_page"])].append(item)

        for index, note in enumerate(notes_by_block.get(row["block_id"], []), 1):
            audit_rows.append(
                {
                    **note,
                    "schema_version": "1.0",
                    "item_id": f"V4-EDIT-{row['block_id']}-{index:03d}",
                    "stage": "editing",
                    "status": "accepted_with_ledger",
                    "source_image": f"20-source/pages/{row['page_id']}.jpg",
                    "edited_candidate": item["modern_text"],
                }
            )

    source_ids = [row["block_id"] for row in modern]
    edited_ids = [row["block_id"] for row in edited_blocks]
    if source_ids != edited_ids or len(set(edited_ids)) != len(edited_ids):
        raise RuntimeError("Edited block identity/order no longer matches modernization")

    merged_terms = {
        row["term"]: (row.get("notes") or [""])[0]
        for row in terminology.get("terms", [])
        if row.get("term")
    }
    merged_terms.update(EDITORIAL_TERMS)
    merged_terms = {converter.convert(k): converter.convert(v) for k, v in merged_terms.items()}

    md = [
        "# 入地眼全书",
        "",
        "## 现代白话版",
        "",
        "> 本版面向对传统风水文献感兴趣的普通读者。书中的吉凶、福祸、子嗣、疾病及官禄判断均属传统观念，不代表现代科学或医学结论。",
        "",
        "## 编者导读：这本书在讲什么",
        "",
        "《入地眼全书》把传统地理知识组织为“龙、穴、砂、水、向”五条线索，又用八卦、天星、河图洛书和纳甲等系统解释方位关系。阅读时可先辨认书中所说的可观察形势，再理解古人如何以术数规则赋予吉凶意义。",
        "",
        "## 编者导读：阅读路线",
        "",
    ]
    for _, _, title, intro in SECTIONS:
        md.append(f"- **{title}**：{intro}")
    md.extend(
        [
            "",
            "## 阅读提示：怎样区分原书与编者内容",
            "",
            "正文是对原书的现代白话转述。所有“编者导读”“术语说明”“阅读提示”和“图版说明”均为后加内容，不属于原作者。对原页残损、OCR 难识或多义之处，本版不猜补，用“具体所指不详”等语句显式保留。",
            "",
        ]
    )

    seen_terms = set()
    started_sections = set()
    figure_no = 0
    for page in range(1, 163):
        section = section_for(page)
        if section[2] not in started_sections:
            started_sections.add(section[2])
            md.extend(
                [
                    f"## {section[2]}",
                    "",
                    f"> **编者导读**：{section[3]}",
                    "",
                ]
            )
        md.extend([f"### 原书第 {page} 页", ""])
        page_rows = by_page[page]
        page_has_uncertainty = False
        page_image_added = False
        for row in page_rows:
            text = row["modern_text"]
            if row.get("editorial_notes"):
                page_has_uncertainty = True
            if row.get("block_type") == "figure":
                figure_no += 1
                if not page_image_added:
                    md.extend(
                        [
                            f"![图 {figure_no}：原书第 {page} 页图版](../20-source/pages/{row['page_id']}.jpg)",
                            "",
                            f"> **图版说明**：本页含图式或表格。请先核对方位标签，再按附近正文的顺序阅读；模糊或缺失标签不作推定。",
                            "",
                        ]
                    )
                    page_image_added = True
                continue
            if not text:
                continue
            if row.get("block_type") == "title" and len(text) <= 40:
                md.extend([f"#### {text}", ""])
            else:
                md.extend([text, ""])
            new_terms = []
            for term in sorted(merged_terms, key=len, reverse=True):
                if term not in seen_terms and term in text:
                    seen_terms.add(term)
                    new_terms.append(f"**{term}**：{merged_terms[term]}")
            if new_terms:
                md.extend(["> **术语说明**：" + "；".join(new_terms), ""])
        if page_has_uncertainty:
            md.extend(
                [
                    "> **阅读提示**：本页含已登记的残损、校勘或释读不确定项，可在原文对照版与审校账本中逐项核查。",
                    "",
                ]
            )

    md.extend(
        [
            "## 编者附录：实地观察顺序",
            "",
            "> **阅读提示**：以下只是帮助理解原书的观察顺序，不是对吉凶预测的认证。",
            "",
            "1. 先看大地形势和山脉走向，区分可观察的地形与书中的象征解释。",
            "2. 再看候选穴场前后左右的高低、开合和遮护关系。",
            "3. 记录水流的来向、去向、曲直、聚散和水口位置。",
            "4. 最后再对照本书的方位、卦例和星名规则，不要把规则名称误当成直接可观察的事实。",
            "",
            "## 术语表",
            "",
            "> **编者说明**：以下定义用于帮助阅读本书，不扩展为原书未说明的新理论。",
            "",
        ]
    )
    for term in sorted(merged_terms):
        md.append(f"- **{term}**：{merged_terms[term]}")
    md.append("")

    markdown = "\n".join(md).rstrip() + "\n"
    edited_dir = ROOT / "50-edited"
    publication_dir = ROOT / "60-publication"
    write_jsonl(edited_dir / "blocks.jsonl", edited_blocks)
    write_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl", audit_rows)
    (edited_dir / "modern-reading.md").write_text(markdown, encoding="utf-8")
    (publication_dir / "modern-reading.md").write_text(markdown, encoding="utf-8")
    write_json(
        edited_dir / "editorial-report.json",
        {
            "schema_version": "1.0",
            "generated_at": now,
            "status": "completed",
            "target_reader": "对传统风水文献感兴趣的普通读者",
            "reading_level": "无需预先掌握术数专业知识",
            "modernization_depth": "完整现代阅读重构",
            "annotation_density": "首次术语解释+逐页不确定性提示",
            "edition_type": "ordinary-reader plus source-comparison",
            "source_blocks": len(modern),
            "edited_blocks": len(edited_blocks),
            "identity_match": source_ids == edited_ids,
            "sections": len(SECTIONS),
            "pages": len(by_page),
            "figure_blocks": sum(1 for row in modern if row.get("block_type") == "figure"),
            "audit_records": len(audit_rows),
            "glossary_terms": len(merged_terms),
            "display_script": "zh-Hans",
            "source_blocks_sha256": sha256(modern_path),
        },
    )

    state = read_json(ROOT / "run-state.json")
    state.setdefault("stages", {})["editing"] = {
        "status": "completed",
        "updated_at": now,
        "blocks": len(edited_blocks),
        "pages": len(by_page),
        "sections": len(SECTIONS),
        "uncertainty_records": len(audit_rows),
        "evidence": "50-edited/editorial-report.json",
    }
    state["current_stage"] = "publication"
    state["updated_at"] = now
    write_json(ROOT / "run-state.json", state)
    print(
        json.dumps(
            {
                "edited_blocks": len(edited_blocks),
                "edited_pages": len(by_page),
                "sections": len(SECTIONS),
                "uncertainty_records": len(audit_rows),
                "glossary_terms": len(merged_terms),
                "reader_chars": len(markdown),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
