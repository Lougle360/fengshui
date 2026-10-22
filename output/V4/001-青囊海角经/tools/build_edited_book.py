from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "60-publication" / "assets" / "figures"


TEXT_REPAIRS = {
    "華龄出版社": "华龄出版社",
    "青囊海角經": "青囊海角经",
    "青囊匯刊": "青囊汇刊",
    "堪與珠玑": "堪舆珠玑",
    "堪輿珠璣": "堪舆珠玑",
    "挥塵": "挥尘",
    "720×10201/16": "720×1020毫米，1/16开",
}


SECTIONS = {
    15: (
        "# 第一编　气数、卦象与图式",
        "**编者导读：**这一编从阴阳、五行、六气与卦象入手，并配有大量图式。阅读时先辨认图中层次、方位和相互关系，再读图说；不要把单一数字或方位直接理解成现实吉凶。",
    ),
    67: (
        "# 第二编　九星与寻龙",
        "**编者导读：**本编以贪狼、巨门、武曲等九星名称归纳山形，并讨论寻龙的基本思路。九星首先是传统形态分类，歌诀中的富贵吉凶属于古人的解释体系。",
    ),
    93: (
        "# 第三编　权衡、钳口与行水",
        "**编者导读：**本编把穴形、水路和局势放在一起衡量。建议先看山势在哪里停聚，再看水怎样来去，最后理解钳口与上、中、下局的传统分法。",
    ),
    104: (
        "# 第四编　龙、穴、砂、水与葬法",
        "**编者导读：**这一编集中讨论寻龙、点穴、观砂、察水和葬法。阅读顺序应是先看整体来龙和堂局，再看局部穴位，不宜脱离现场只背口诀。",
    ),
    138: (
        "# 第五编　《道法双谈》摘句",
        "**编者导读：**本编多用短句讨论学步、认星、神气、结穴和品级。短句高度压缩，遇到意义不确定的术语，本版保留并给出审校提示，不强行补成确定答案。",
    ),
    150: (
        "# 第六编　堪舆人物与传承资料",
        "**编者导读：**本编汇集历代相关人物的小传与传说，兼具资料性和传统谱系建构色彩。阅读时应区分可核验的生平记载与术家传说。",
    ),
    175: (
        "# 第七编　堪舆纪事与艺文",
        "**编者导读：**本编保存地方纪事、书目和艺文资料，适合作为查考部分。第一次通读可先把握每篇在讨论什么，不必记忆全部人名和书名。",
    ),
    185: (
        "# 第八编　风水论辨与葬书问答",
        "**编者导读：**这一编既有支持风水的论述，也有质疑和反驳。阅读重点是看作者如何举例、如何论证，以及不同立场的分歧，而不是把任何一方直接当作现代科学结论。",
    ),
    206: (
        "# 第九编　王充《论衡》相关选录",
        "**编者导读：**末编保存王充等人对择日、宅术、五音和吉凶观念的辨析，具有思想史意义。它与前文并非完全同一立场，正可帮助读者比较古代内部的争论。",
    ),
}


GLOSSARY = """# 附录　核心术语表

## 阴阳与五行

- **阴阳**：古人用来说明事物相反相成、消长转化的一组范畴。
- **五行**：木、火、土、金、水五类关系系统，并非五种简单物质。
- **河洛**：河图、洛书及其衍生的数理象征体系。
- **八卦**：乾、坤、震、巽、坎、离、艮、兑八种基本卦象。
- **纳甲**：把天干地支等系统配入卦象的传统方法。

## 龙穴砂水

- **龙**：堪舆语境中连续行进的山势或地脉。
- **寻龙**：追踪山势的来路、起伏、转折和停聚。
- **穴**：传统上认为山水关系集中、适宜取用的核心位置。
- **点穴**：在整体地局中判断具体穴位。
- **砂**：穴场周围起护卫、呼应、关拦作用的山丘或高地。
- **水**：河流、溪涧、湖塘等水体，也包括其来去、聚散和流速。
- **明堂**：穴前相对开阔、容纳水势和视线的空间。
- **水口**：水流进入或离开地局时形成收束的位置。
- **来龙**：向穴场延伸而来的主山势。
- **结穴**：传统上所说龙脉停聚并形成穴场。

## 星体与方法

- **九星**：贪狼、巨门、禄存、文曲、廉贞、武曲、破军、左辅、右弼等传统分类名称。
- **生气**：古代堪舆对有利地气或生发状态的概括。
- **形气**：可观察的形势与传统所说气脉之间的关系。
- **理气**：借方位、卦象、干支等系统推演地局的方法。
- **峦头**：以山形、水势和空间结构为主要观察对象的方法。
- **钳口**：穴场前后或左右形成夹持、收束的形态。
- **行水**：观察或安排水流来去的传统方法。
- **藏风聚气**：传统上形容空间有遮护、山水能收聚的状态。

## 阅读提示

书中的富贵、贫贱、寿夭、官职和灾福判断属于传统文献的历史表达，不构成现代科学、工程、医疗、法律或投资结论。
"""


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def clean_text(value: str) -> str:
    text = value
    for before, after in TEXT_REPAIRS.items():
        text = text.replace(before, after)
    text = re.sub(r"四库存目青囊汇刊[\[【（(]?[二2][\]】）)]?", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def reader_safe_reason(value: str) -> str:
    forbidden = (
        "本地硬校验", "自动修复", "核义模型", "后续自动处理", "candidate", "current",
        "locked_terms", "allowed_glossary", "模型", "pipeline", "V4", "可直接出版",
    )
    pieces = re.split(r"[；。]\s*", clean_text(value))
    kept = [piece.strip() for piece in pieces if piece.strip() and not any(word in piece for word in forbidden)]
    return "；".join(kept[:3])


def crop_figure(row: dict) -> str | None:
    bbox = row.get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    source = ROOT / str(row["source_image"])
    if not source.exists():
        return None
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURE_DIR / f"{row['block_id']}.jpg"
    with Image.open(source) as image:
        width, height = image.size
        x0, y0, x1, y1 = [int(v) for v in bbox]
        pad = 14
        box = (max(0, x0 - pad), max(0, y0 - pad), min(width, x1 + pad), min(height, y1 + pad))
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        image.crop(box).convert("RGB").save(out, quality=92, optimize=True)
    return f"assets/figures/{out.name}"


def note_summary(notes: list[dict]) -> str:
    details = []
    for note in notes:
        reason = reader_safe_reason(str(note.get("reason") or ""))
        if reason and reason not in details:
            details.append(reason)
        if len(details) == 2:
            break
    if not details:
        return "本页含已登记的校勘或释读不确定项，可在原文对照版中核查。"
    compact = "；".join(details)
    return f"本页有 {len(notes)} 条校勘记录，主要涉及：{compact[:220]}。详见原文对照版。"


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    modern = read_jsonl(ROOT / "40-modernized" / "blocks.jsonl")
    uncertainties = read_jsonl(ROOT / "40-modernized" / "uncertainties.jsonl")
    by_page = defaultdict(list)
    notes_by_block = defaultdict(list)
    for row in modern:
        by_page[int(row["source_page"])].append(row)
    for item in uncertainties:
        if item.get("block_id"):
            notes_by_block[item["block_id"]].append(item)

    edited = []
    edited_blocks = []
    audit_rows = []
    for page in range(1, 217):
        rows = sorted(by_page[page], key=lambda row: row["block_id"])
        source_parts = [str(row.get("source_text") or "").strip() for row in rows]
        normalized_parts = [str(row.get("normalized_text") or "").strip() for row in rows]
        modern_parts = [clean_text(str(row.get("modern_text") or "")) for row in rows]
        page_notes = []
        for row in rows:
            for note in notes_by_block.get(row["block_id"], []):
                page_notes.append(
                    {
                        "severity": "medium" if note.get("status") == "accepted_with_ledger" else "low",
                        "excerpt": (note.get("source") or "")[:160],
                        "reason": reader_safe_reason("；".join((note.get("issues") or []) + (note.get("uncertainty") or [])))[:800],
                        "source_block_id": row["block_id"],
                    }
                )
                audit_rows.append(
                    {
                        "schema_version": "1.0",
                        "item_id": note.get("item_id") or f"V4-EDIT-{row['block_id']}",
                        "page_id": row["page_id"],
                        "source_page": page,
                        "block_id": row["block_id"],
                        "severity": page_notes[-1]["severity"],
                        "status": "accepted_with_ledger",
                        "source_image": f"20-source/pages/{row['page_id']}.jpg",
                        "source": note.get("source") or row.get("normalized_text") or "",
                        "candidate": note.get("candidate") or row.get("modern_text") or "",
                        "issues": note.get("issues") or [],
                        "uncertainty": note.get("uncertainty") or [],
                    }
                )
        for row in rows:
            item = dict(row)
            item["modern_text"] = clean_text(str(item.get("modern_text") or ""))
            item.update(
                {
                    "operation": "edit",
                    "notes": [
                        {
                            "severity": "medium" if note.get("status") == "accepted_with_ledger" else "low",
                            "excerpt": (note.get("source") or "")[:160],
                            "reason": reader_safe_reason("；".join((note.get("issues") or []) + (note.get("uncertainty") or [])))[:800],
                        }
                        for note in notes_by_block.get(row["block_id"], [])
                    ],
                }
            )
            edited_blocks.append(item)
        first = rows[0]
        edited.append(
            {
                "schema_version": "1.0",
                "book_id": first["book_id"],
                "page_id": first["page_id"],
                "block_id": f"{first['page_id']}-B001",
                "source_page": page,
                "block_type": "page",
                "bbox": None,
                "source_image": f"20-source/pages/{first['page_id']}.jpg",
                "source_text": "\n\n".join(part for part in source_parts if part),
                "normalized_text": "\n\n".join(part for part in normalized_parts if part),
                "modern_text": "\n\n".join(part for part in modern_parts if part),
                "language": "lzh",
                "disposition": "retained" if not any(modern_parts) else "translated",
                "confidence": min(float(row.get("confidence") or 0.5) for row in rows),
                "evidence": ["source_reconstruction", "v3_multi_pass_review", "v4_page_edit"],
                "notes": page_notes,
                "operation": "edit",
            }
        )

    write_jsonl(ROOT / "50-edited" / "blocks.jsonl", edited_blocks)
    write_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl", audit_rows)
    book = read_json(ROOT / "book.json")
    book["page_accounting"] = {
        "physical_pages": 216,
        "included_content": 215,
        "blank_or_noncontent": 1,
        "excluded": 0,
        "unreadable": 0,
    }
    write_json(ROOT / "book.json", book)

    md = [
        "# 青囊海角经",
        "",
        "## 现代白话版",
        "",
        "郭璞原著",
        "",
        "葛超云 整理",
        "",
        "本书是一部汇集传统堪舆图式、歌诀、人物资料和论辨文章的文献整理本，供希望系统了解古代风水知识结构的普通读者阅读。",
        "",
        "# 本书介绍",
        "",
        "《青囊海角经》现行本内容复杂，既有阴阳、五行、卦象与山水图式，也有寻龙点穴歌诀、历代人物资料和对风水术的支持或质疑。它并不是一条从头到尾只讲操作方法的单线教材，因此本版重新建立九编阅读路线。",
        "",
        "**阅读提示：**先用前四编认识传统概念和龙穴砂水，再读人物、纪事与论辨部分。书中关于富贵、寿夭、官职和灾福的判断属于传统文献表达，不应当作现代科学因果结论。",
        "",
        "# 阅读地图",
        "",
        "1. 第一编先读图式，建立阴阳、五行、卦象与方位的基本词汇。",
        "2. 第二至第四编进入九星、寻龙、点穴、观砂和察水。",
        "3. 第五编是高度压缩的口诀，需要结合审校提示慢读。",
        "4. 第六、七编属于人物、书目和纪事资料，可按需查阅。",
        "5. 第八、九编保存古人内部的争论，既有申辩，也有批评。",
        "",
        "**版本说明：**原书第1至14页为封面、出版信息、序和目录。连续阅读版保留序言，将现代出版社信息和原目录移入原文对照版，以免与本版版权页及新目录混淆。全部216页仍保留页面证据，其中第152页为空白或非内容页。",
        "",
        "# 原序",
        "",
    ]
    page_rows = {int(row["source_page"]): row for row in edited}
    figure_rows = defaultdict(list)
    for row in edited_blocks:
        if row.get("block_type") == "figure" and int(row["source_page"]) >= 15:
            figure_rows[int(row["source_page"])].append(row)

    preface = page_rows[4]["modern_text"].strip()
    if preface:
        md.extend([preface, ""])

    for page in range(15, 217):
        if page in SECTIONS:
            title, guide = SECTIONS[page]
            md.extend([title, "", guide, ""])
        row = page_rows[page]
        text = row["modern_text"].strip()
        if not text:
            text = ""
        md.extend([f"**原书页码：{page}**", ""])
        if text:
            md.extend([text, ""])
        for index, figure in enumerate(figure_rows.get(page, []), 1):
            asset = crop_figure(figure)
            if asset:
                md.extend([
                    f"![原书第{page}页图示{index}]({asset})",
                    "",
                    f"**读图提示：**这是原书第 {page} 页的图示。先看主体轮廓和方向，再结合本页文字判断各部分关系；原图未能可靠辨认的字不作补写。",
                    "",
                ])
        if row["notes"]:
            md.extend([f"> 审校提示：{note_summary(row['notes'])}", ""])
    md.extend([GLOSSARY.strip(), ""])
    markdown = "\n".join(md).rstrip() + "\n"
    (ROOT / "50-edited" / "modern-reading.md").write_text(markdown, encoding="utf-8")
    (ROOT / "60-publication" / "modern-reading.md").write_text(markdown, encoding="utf-8")

    state = read_json(ROOT / "run-state.json")
    state.setdefault("stages", {})["editing"] = {
        "status": "completed",
        "updated_at": now,
        "blocks": len(edited_blocks),
        "pages": len(edited),
        "uncertainty_records": len(audit_rows),
        "evidence": "50-edited/blocks.jsonl",
    }
    state["current_stage"] = "publication"
    state["updated_at"] = now
    write_json(ROOT / "run-state.json", state)
    print(json.dumps({"edited_blocks": len(edited_blocks), "edited_pages": len(edited), "uncertainty_records": len(audit_rows), "reader_chars": len(markdown)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
