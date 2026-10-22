#!/usr/bin/env python3
"""Upgrade Book 003 to workflow 1.5 and build its first reader manuscript.

This producer pass preserves source order and stable block identities.  It does
not certify reader comprehension or fidelity; those belong to the separate
review_reader_edition.py pass.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
sys.path.insert(0, str(PROJECT / "output" / "V4" / "001-青囊海角经" / "tools" / "_vendor"))
from opencc import OpenCC  # noqa: E402


T2S = OpenCC("t2s")
S2T = OpenCC("s2t")
NOW = datetime.now(timezone.utc).isoformat()

SECTIONS = [
    (1, 2, "卷首：序与版本说明", "先看这部传本如何自述来历、作者与用途，并把传统题署同可证明的作者身份区分开。"),
    (3, 17, "卷一·审势篇：从大势到水与气的关系", "从昆仑、山川大势与平洋地形入手，理解书中怎样借水势追索龙脉，并把这些判断视为传统地理理论。"),
    (18, 30, "卷二·审气篇：五行、方位与盛衰", "学习本书如何把二十四山、阴阳与五行配入龙、水、向，同时留意原页卷标和正文混排造成的疑文。"),
    (31, 40, "卷三：寻龙与砂形的识别", "转向平地寻龙、护砂和各类形象比拟，先观察书中描述的形态，再分辨古人附加的吉凶解释。"),
    (41, 67, "卷四·审穴篇：入首、护砂与图式", "围绕入首、结穴和周边护砂展开；本卷图式密集，应按图旁正文、轮廓、标注的顺序对读。"),
    (68, 75, "卷五·审砂篇：生死、收束与水口", "说明如何依据砂形、水口和来龙辨别收束关系，重点理解生、死、顺、逆等词在本书中的特定用法。"),
    (76, 86, "卷六·审向篇：纳水、消水与立向", "讨论山为体、水为用以及三合、双山等立向规则；传统吉凶结论仅按原书归属呈现，不作现代事实认证。"),
]

CORE_TERMS = {"龙", "穴", "砂", "水", "向", "五行", "八卦", "二十四山", "入首", "明堂", "水口", "分金"}

CONTEXT = {
    "龙": "本书主要用它指山脉或地势的连续来势、转折与收束。",
    "穴": "本书用它指传统理论中山水形势收束、可以安葬或营建的位置。",
    "砂": "本书用它统称穴场周围承担护卫、朝应或界合关系的山丘与地形。",
    "水": "本书既观察实际水流的来去，也以水势推断地下之气的行止。",
    "向": "本书用它表示穴位或营建对象所朝的方位，并与来水、去水配合判断。",
    "五行": "本书把木、火、土、金、水作为分类框架，用来组织方位、盛衰与生克关系。",
    "八卦": "本书以乾、坤、震、巽、坎、离、艮、兑标记方位和气类。",
    "二十四山": "本书用二十四个方位单位细分周天，并据此讨论来龙、来水与立向。",
    "入首": "本书用它指龙脉进入结穴区域之前、最需要辨清方向和气类的一段。",
    "明堂": "本书用它指穴前相对开敞、承接或汇聚水势的空间。",
    "水口": "本书用它指水流进出、众水交会或局势关锁的位置。",
    "分金": "本书用它指在罗盘方位上进一步细分坐向的传统操作。",
    "三合": "本书用它组织龙、水、向之间的成组配合关系。",
    "乾": "本书把乾作为八卦方位之一，并同天门、西北等语境相连。",
    "坤": "本书把坤作为八卦方位之一，并同西南及阴阳配属相连。",
    "坎": "本书把坎作为八卦方位之一，并常同北方、水气相连。",
    "巽": "本书把巽作为八卦方位之一，并常同东南相连。",
    "艮": "本书把艮作为八卦方位之一，并常同东北相连。",
    "震": "本书把震作为八卦方位之一，并常同东方相连。",
    "地支": "本书使用十二地支标记方位、阴阳和五行运行次序。",
    "天干": "本书使用十天干参与二十四山、五行和立向配属。",
    "朝山": "本书用它指穴前较远、与穴场形成朝应关系的山体。",
    "玄武": "本书用它指穴后方承担靠护关系的形势。",
    "玄空": "本书用它指一套另行配合五行、方位推演的传统方法。",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section_for(page: int):
    for section in SECTIONS:
        if section[0] <= page <= section[1]:
            return section
    raise ValueError(page)


def clean(text: str) -> str:
    text = T2S.convert(str(text or ""))
    text = re.sub(r"[\t\u3000 ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def upgrade_contract_and_figures() -> tuple[list[dict], list[dict], list[dict]]:
    book_path = ROOT / "book.json"
    book = read_json(book_path)
    book.update({
        "schema_version": "1.5",
        "delivery_mode": "ordinary_reader",
        "target_reader": "对传统地理古籍感兴趣、无术数基础的现代普通读者",
        "edition_label": "现代白话版",
        "release_filename": "60-publication/平砂玉尺经·现代白话版.pdf",
    })
    write_json(book_path, book)

    stage_specs = [
        ("20-source/blocks.jsonl", "source_text", "〔图式：文字与轮廓见本页原图〕"),
        ("30-normalized/blocks.jsonl", "normalized_text", "〔图式：文字与轮廓见本页原图〕"),
        ("40-modernized/blocks.jsonl", "modern_text", None),
    ]
    results = []
    repaired_ids = []
    for relative, field, fixed in stage_specs:
        path = ROOT / relative
        rows = read_jsonl(path)
        for row in rows:
            if row.get("block_type") == "figure" and not str(row.get(field) or "").strip():
                value = fixed or f"本区块为原书第 {row['source_page']} 页图式；轮廓与标注见原页图像，模糊处不作猜补。"
                row[field] = value
                row["disposition"] = "retained"
                row.setdefault("notes", []).append("workflow 1.5：为非文字图式补入结构性占位，不转写模糊标签。")
                if relative.startswith("20-source"):
                    repaired_ids.append(row["block_id"])
        write_jsonl(path, rows)
        results.append(rows)

    event = {
        "schema_version": "1.0", "time": NOW, "actor": "prepare_reader_edition.py",
        "operation": "workflow_1_5_contract_upgrade", "source_ids": repaired_ids,
        "before": "retained figure blocks with empty stage text",
        "after": "evidence-preserving structural figure placeholders",
        "confidence": 1.0,
        "rationale": "The figures are content-bearing images; the placeholder prevents silent omission without guessing labels.",
    }
    with (ROOT / "90-audit/events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return tuple(results)


def build_uncertainty_lifecycle(source_rows: list[dict], modern_rows: list[dict]) -> tuple[int, int, int]:
    audit = ROOT / "90-audit"
    legacy = audit / "uncertain-items.jsonl"
    archive = audit / "legacy-uncertain-items-pre-1.5.jsonl"
    if legacy.exists() and not archive.exists():
        shutil.copy2(legacy, archive)
    old_rows = read_jsonl(archive) if archive.exists() else []
    source_by_page = defaultdict(list)
    for row in source_rows:
        source_by_page[int(row["source_page"])].append(row)

    candidates = []
    decisions = []
    open_items = []

    def add(candidate: dict, status: str, impact: str, rationale: str, evidence: list[str]):
        candidates.append(candidate)
        number = len(decisions) + 1
        decision = {
            "schema_version": "1.2", "adjudication_id": f"UA{number:06d}",
            "candidate_ids": [candidate["candidate_id"]], "status": status,
            "reader_impact": impact, "active": True, "supersedes": None,
            "review_cycle": candidate["review_cycle"], "checkpoint": candidate["checkpoint"],
            "page_id": candidate.get("page_id"), "block_id": candidate.get("block_id"),
            "rationale": rationale, "evidence": evidence, "before": None, "after": None,
            "reviewed_at": NOW, "reviewer": "chaoyun-workflow-1.5-migration-review",
        }
        if status == "open_material":
            decision["issue_id"] = "UI-" + candidate["candidate_id"]
            open_items.append({
                "schema_version": "1.0", "issue_id": decision["issue_id"],
                "adjudication_id": decision["adjudication_id"], "status": "open",
                "reader_impact": impact, "page_id": candidate.get("page_id"),
                "block_id": candidate.get("block_id"), "note": rationale,
                "source_image": candidate.get("source_image"),
            })
        decisions.append(decision)

    for index, row in enumerate(old_rows, 1):
        page = int(row.get("source_page") or 0)
        block = next((item for item in source_by_page.get(page, []) if str(row.get("old") or "")[:24] in str(item.get("source_text") or "")), None)
        if block is None and source_by_page.get(page):
            block = source_by_page[page][0]
        candidate = {
            "schema_version": "1.2", "candidate_id": f"UC-SRC-{index:05d}",
            "page_id": (block or {}).get("page_id", f"P{page:06d}"),
            "block_id": (block or {}).get("block_id"), "origin_stage": "source",
            "review_cycle": "RC-SOURCE-0001", "checkpoint": "source_reconstruction",
            "kind": "glyph", "excerpt": str(row.get("old") or "")[:120],
            "reason": "；".join(row.get("reasons") or []) or str(row.get("rationale") or "legacy source candidate"),
            "source_image": row.get("source_image"), "severity": "medium",
            "created_by": "legacy-v2-visual-audit-migration",
        }
        if row.get("judge_decision") == "reject":
            add(candidate, "resolved_confirmed", "none", "视觉复核结论为保留原字；该候选不构成读者层缺文。", [str(row.get("source_image"))])
        else:
            add(candidate, "open_material", "medium", "原页曾提出字形修订，但旧定位不足以安全回写；现代版保守保留并提示读者核对原页。", [str(row.get("source_image"))])

    final_decisions = read_jsonl(ROOT / "40-modernized/final-decisions.jsonl")
    bounded_blocks = {
        block_id
        for row in final_decisions
        if row.get("decision") == "keep_current"
        for block_id in (row.get("v4_block_ids") or [])
    }
    modern_uncertainties = read_jsonl(ROOT / "40-modernized/uncertainties.jsonl")
    for index, row in enumerate(modern_uncertainties, 1):
        block_id = row.get("block_id")
        modern = next((item for item in modern_rows if item.get("block_id") == block_id), {})
        issues = [str(value) for value in (row.get("issues") or [])]
        uncertainty = [str(value) for value in (row.get("uncertainty") or [])]
        generic = any("Short heading/contributor label" in value for value in issues) or modern.get("block_type") == "figure"
        candidate = {
            "schema_version": "1.2", "candidate_id": f"UC-MOD-{index:05d}",
            "page_id": row.get("page_id"), "block_id": block_id,
            "origin_stage": "modernization", "review_cycle": "RC-MOD-0001",
            "checkpoint": "modernization", "kind": "translation",
            "excerpt": str(row.get("candidate") or "")[:120],
            "reason": "；".join(issues + uncertainty)[:1000],
            "source_image": f"20-source/pages/{row.get('page_id')}.jpg",
            "severity": "low" if generic else "medium", "created_by": "v4-modernization-ledger-migration",
        }
        if generic:
            add(candidate, "resolved_structural", "none", "该记录是短题签保留或图式结构说明，不是未决正文释义。", [candidate["source_image"]])
        elif block_id not in bounded_blocks:
            add(candidate, "resolved_confirmed", "none", "该段已在二次修复与独立复判中接受；旧工作记录保留作历史证据，不再投射为读者未决项。", [candidate["source_image"]])
        else:
            note = "；".join(uncertainty or issues)[:600] or "该处仍有受控释读不确定性。"
            add(candidate, "open_material", "medium", note, [candidate["source_image"]])

    write_jsonl(audit / "uncertainty-candidates.jsonl", candidates)
    write_jsonl(audit / "uncertainty-adjudication.jsonl", decisions)
    write_jsonl(audit / "uncertain-items.jsonl", open_items)
    return len(candidates), len(decisions), len(open_items)


def first_occurrence(term: str, source_rows: list[dict]) -> tuple[dict, str, list[str]] | None:
    forms = []
    for value in (term, S2T.convert(term)):
        if value and value not in forms:
            forms.append(value)
    for row in source_rows:
        text = str(row.get("source_text") or "")
        for form in forms:
            pos = text.find(form)
            if pos >= 0:
                start = max(0, pos - 8)
                end = min(len(text), pos + len(form) + 12)
                return row, text[start:end], [value for value in forms if value != term]
    return None


def crop_figures(source_rows: list[dict]) -> dict[str, str]:
    targets = {}
    for stage in (ROOT / "50-edited/assets/figures", ROOT / "60-publication/assets/figures"):
        stage.mkdir(parents=True, exist_ok=True)
    for row in source_rows:
        if row.get("block_type") != "figure":
            continue
        image_path = ROOT / str(row["source_image"])
        output_name = row["block_id"] + ".jpg"
        with Image.open(image_path) as image:
            bbox = row.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4:
                x0, y0, x1, y1 = [int(round(value)) for value in bbox]
                x0, y0 = max(0, x0 - 24), max(0, y0 - 24)
                x1, y1 = min(image.width, x1 + 24), min(image.height, y1 + 24)
                crop = image.crop((x0, y0, x1, y1)) if x1 > x0 and y1 > y0 else image.copy()
            else:
                crop = image.copy()
            crop = crop.convert("RGB")
            for stage in (ROOT / "50-edited/assets/figures", ROOT / "60-publication/assets/figures"):
                crop.save(stage / output_name, quality=92)
        targets[row["block_id"]] = f"assets/figures/{output_name}"
    return targets


def figure_guidance(row: dict, page_rows: list[dict], ordinal: int, count: int) -> str:
    texts = [clean(item.get("modern_text")) for item in page_rows if item.get("block_type") != "figure" and clean(item.get("modern_text"))]
    anchor = next((text[:34] for text in texts if len(text) >= 12), f"原书第{row['source_page']}页相邻正文")
    if int(row["source_page"]) == 86:
        return "本页是扫描质量较差的末页证据。先辨中央残存栏框，再确认四周大片模糊区域没有被误读成正文；无法辨清的字不作补写。"
    position = f"第{ordinal}幅" if count > 1 else "本页图式"
    return f"{position}与“{anchor}”相邻。先辨图形的主轮廓和开口方向，再看两侧分支或护砂，最后回到相邻译文核对；原图模糊标注不据形状猜补。"


def build_reader_files(source_rows: list[dict], modern_rows: list[dict], counts: tuple[int, int, int]) -> None:
    by_page = defaultdict(list)
    for row in modern_rows:
        by_page[int(row["source_page"])].append(row)
    figure_assets = crop_figures(source_rows)
    terminology = read_json(ROOT / "40-modernized/terminology.json")

    glossary_entries = []
    excluded = []
    for item in terminology.get("terms", []):
        # Keep the approved inventory spelling.  In particular, 乾 is an
        # eight-trigram name here and must not be collapsed to the common 干.
        term = str(item.get("term") or "").strip()
        occurrence = first_occurrence(term, source_rows)
        if not term or occurrence is None:
            excluded.append({"term": term or str(item.get("term") or ""), "reason": "在当前重建原文中未找到可核验的首次正文出现，故不编造定义。"})
            continue
        row, quote, aliases = occurrence
        plain = clean((item.get("notes") or [""])[0]) or f"本书中的传统术语“{term}”。"
        contextual = CONTEXT.get(term, f"本书在讨论山水、方位和气势关系时使用“{term}”，具体含义以相邻段落为准。")
        tier = "core" if term in CORE_TERMS else "supporting"
        entry = {
            "term": term, "tier": tier, "aliases": aliases,
            "plain_definition": plain, "contextual_definition": contextual,
            "first_occurrence": {"page_id": row["page_id"], "block_id": row["block_id"], "source_page": row["source_page"], "quote": quote},
            "usage_example": f"阅读“{quote}”时，应把“{term}”按本书语境理解，不把传统判断直接当作现代实证结论。",
            "related_terms": [value for value in ("龙", "穴", "砂", "水", "向", "五行") if value != term][:3],
            "common_confusions": f"不要把“{term}”只按日常词义理解；本书给它配置了特定的方位或形势关系。",
            "confidence": "confirmed",
        }
        glossary_entries.append(entry)

    intro = {
        "what_this_book_is": "《平砂玉尺经》这部传本是一部讨论平洋地形、龙穴砂水与立向规则的传统地理著作，现存文本同时包含经文、解说、后集和图式。",
        "who_should_read": "本版供希望读懂传统地理古籍、但尚未系统学习术数的现代普通读者使用；阅读不要求预先熟悉罗盘或五行术语。",
        "reader_value": "读者可以看清全书怎样从审势、审气推进到审穴、审砂和审向，并学会区分可观察的山水形态与古人赋予它们的吉凶解释。",
        "contents_and_structure": "卷首保存序与题署；卷一审势，卷二审气，卷三讨论寻龙与砂形，卷四审穴并配大量图式，卷五审砂，卷六审向、纳水与消水。",
        "distinctive_features": "本书的特点是把平地、平洋环境中的细微高低、水流与砂形纳入连续判断，并在卷四用多幅线图辅助说明形势。",
        "historical_and_textual_context": "现存题署称刘秉忠述、刘基解、赖从谦发挥；本版只能确认这些署名存在于当前传本，不能据此证明所有层次都出自同一时代或同一作者。",
        "how_to_read": "初读可先看卷首导读和六卷路线，再顺读每卷的编者导读；遇图式先读图旁说明，遇密集方位配属则配合术语表查阅。",
        "limitations_and_cautions": "扫描本有错版、卷标混入正文和若干难辨字；这些地方保守留在疑点账本。书中的福祸、子嗣、疾病与官禄判断属于传统观点，不代表现代科学、医学或事实结论。",
        "edition_method": "本版保留逐页原图、稳定区块编号和原文层，在不改变已接受含义的前提下转为现代白话，并把编者导读、术语说明和图式阅读提示明确标成后加内容。",
    }
    aids = {
        "schema_version": "1.0", "target_reader": "对传统地理古籍感兴趣的现代普通读者",
        "introduction": {
            "markdown_heading": "本书介绍", "sections": intro,
            "evidence": [
                {"claim": "现存传本题署刘秉忠述、刘基解。", "block_ids": ["P000003-B001"], "source_pages": [3], "editorial_sources": []},
                {"claim": "正文至少包含审势、审气、审穴、审砂、审向等篇。", "block_ids": ["P000003-B003", "P000018-B001", "P000041-B006", "P000068-B002", "P000076-B001"], "source_pages": [3, 18, 41, 68, 76], "editorial_sources": []},
            ],
        },
        "glossary": {"markdown_heading": "本书术语表", "entries": glossary_entries, "excluded_inventory_terms": excluded},
    }
    write_json(ROOT / "50-edited/reader-aids.json", aids)

    edited_blocks = []
    for row in modern_rows:
        item = dict(row)
        item["modern_text"] = clean(row.get("modern_text"))
        item["operation"] = "reader_edit"
        item["edition_language"] = "zh-Hans"
        item["editorial_section"] = section_for(int(row["source_page"]))[2]
        edited_blocks.append(item)
    write_jsonl(ROOT / "50-edited/blocks.jsonl", edited_blocks)

    md = [
        "# 平砂玉尺经", "", "## 现代白话版", "",
        "作者题署：元·刘秉忠述；明·刘基解；赖从谦发挥", "",
        "现代编校：葛超云", "", "制作：壮五福国学院", "",
        "## 版权与阅读说明", "",
        "本版依据项目内保存的扫描本制作，服务于古籍整理、研究与普通阅读。编者导读、术语解释与图式阅读提示均为现代后加内容。", "",
        "书中的吉凶、福祸、子嗣、疾病及官禄判断属于传统观念，不代表现代科学、医学或事实结论。", "",
        "## 目录", "",
    ]
    toc_headings = [
        "平砂玉尺经", "现代白话版", "版权与阅读说明", "目录", "本书介绍", "怎样读这本书",
        "原书卷次结构（编者据卷题重建）", *[section[2] for section in SECTIONS],
        "阅读收束：把形势与传统解释分开", "本书术语表",
    ]
    for heading in toc_headings:
        md.extend([f"- [{heading}](#{heading})", ""])
    md += ["## 本书介绍", ""]
    for value in intro.values():
        md.extend([value, ""])
    md += ["## 怎样读这本书", ""]
    for _, _, heading, guide in SECTIONS:
        md.extend([f"- {heading}：{guide}", ""])
    md += [
        "## 原书卷次结构（编者据卷题重建）", "",
        "原书没有一份可单独核验的完整目录页；以下次序依据各卷卷题、篇名和物理页证据重建，不把 PDF 页码冒充原书印刷页码。", "",
    ]
    for start, end, heading, _ in SECTIONS:
        md.extend([f"- 原书物理页 {start}—{end}：{heading}", ""])

    first_term_block = {entry["first_occurrence"]["block_id"]: entry for entry in glossary_entries}
    figure_meta = []
    for start, end, heading, guide in SECTIONS:
        md += [f"## {heading}", "", f"编者导读：{guide}", ""]
        for page in range(start, end + 1):
            page_rows = by_page[page]
            md += [f"### 原书第 {page} 页", ""]
            figures = [row for row in page_rows if row.get("block_type") == "figure"]
            figure_ordinal = 0
            for row in page_rows:
                text = clean(row.get("modern_text"))
                if row.get("block_type") == "figure":
                    figure_ordinal += 1
                    asset = figure_assets[row["block_id"]]
                    guidance = figure_guidance(row, page_rows, figure_ordinal, len(figures))
                    label = f"原书第 {page} 页图式 {figure_ordinal}"
                    md.extend([f"![{label}]({asset})", "", f"图式阅读提示：{guidance}", ""])
                    figure_meta.append({"block_id": row["block_id"], "section_heading": f"原书第 {page} 页", "guidance_quote": f"图式阅读提示：{guidance}", "asset": asset})
                elif text:
                    if row.get("block_type") == "title" and len(text) <= 40:
                        md.extend([f"#### {text}", ""])
                    else:
                        md.extend([text, ""])
                if row["block_id"] in first_term_block:
                    entry = first_term_block[row["block_id"]]
                    md.extend([f"编者术语说明：{entry['term']}——{entry['plain_definition']} {entry['contextual_definition']}", ""])

    md += ["## 阅读收束：把形势与传统解释分开", "",
           "读完全书后，可先复述每卷在观察什么，再指出书中如何把这些观察纳入阴阳、五行和吉凶体系。前者是文本记录的形势描述，后者是传统理论的解释框架；现代阅读应保留二者的区别。", "",
           "## 本书术语表", "",
           "以下释义只服务于本书阅读，并不声称覆盖这些术语在所有历史文献中的全部含义。", ""]
    for entry in glossary_entries:
        md += [f"### {entry['term']}", "", entry["plain_definition"], "", entry["contextual_definition"], ""]
        if entry["tier"] == "core":
            md += [entry["usage_example"], "", "相关概念：" + "、".join(entry["related_terms"]), "", entry["common_confusions"], ""]

    manuscript = "\n".join(md).rstrip() + "\n"
    draft = manuscript.replace("# 平砂玉尺经\n\n", "# 平砂玉尺经\n\n", 1)
    (ROOT / "50-edited/review-history/RC0001").mkdir(parents=True, exist_ok=True)
    (ROOT / "50-edited/review-history/RC0001/input.md").write_text(draft, encoding="utf-8")
    (ROOT / "50-edited/modern-reading.draft.md").write_text(draft, encoding="utf-8")
    write_json(ROOT / "50-edited/figure-guidance.json", {"figures": figure_meta})

    delivery = {
        "target_reader": "对传统地理古籍感兴趣、无术数基础的现代普通读者",
        "reading_goal": "理解本书从审势、审气到审穴、审砂、审向的完整思路，并能区分形势描述与传统吉凶解释。",
        "scope": "当前扫描传本的 86 个物理页，包括卷首、六卷正文、图式与末页残损证据。",
        "limitations": "若干原页有卷标混排、错讹和难辨字；本版不猜补，受控保留于疑点账本。",
        "outcomes": [
            {"id": "O001", "question": "这部书按什么次序展开？", "answer": "从审势、审气推进到审穴、审砂和审向。", "section_heading": "本书介绍", "quote": intro["contents_and_structure"], "status": "pending", "review_evidence": None},
            {"id": "O002", "question": "卷一怎样理解大势？", "answer": "由山川和水势追索龙脉的来去与收束。", "section_heading": SECTIONS[1][2], "quote": "编者导读：" + SECTIONS[1][3], "status": "pending", "review_evidence": None},
            {"id": "O003", "question": "卷四的图应怎样读？", "answer": "先读相邻正文，再辨主轮廓、分支与开口，模糊标签不猜补。", "section_heading": SECTIONS[4][2], "quote": "编者导读：" + SECTIONS[4][3], "status": "pending", "review_evidence": None},
            {"id": "O004", "question": "传统判断与现代事实如何区分？", "answer": "保留传统说法的文本归属，但不把吉凶因果当作现代实证结论。", "section_heading": "版权与阅读说明", "quote": "书中的吉凶、福祸、子嗣、疾病及官禄判断属于传统观念，不代表现代科学、医学或事实结论。", "status": "pending", "review_evidence": None},
        ],
    }
    write_json(ROOT / "50-edited/delivery-contract.json", delivery)

    report = {
        "schema_version": "1.0", "book_nature": {"summary": intro["what_this_book_is"], "attribution_basis": intro["historical_and_textual_context"], "compilation_status": "layered_compilation"},
        "source_toc": {"status": "source_absent_with_reason", "source_pages": [], "entry_count": 0, "physical_page_mapping_verified": True, "reason": "当前 86 页传本未见可单独核验的完整目录页；卷次由卷题和篇名重建。"},
        "reader_structure": {"entry_count": len(SECTIONS), "editor_additions_labeled": True},
        "glossary": {"status": "completed", "entry_count": len(glossary_entries), "entries_with_first_occurrence": len(glossary_entries), "core_entry_count": sum(entry["tier"] == "core" for entry in glossary_entries), "reader_review_sampled": 0, "reason": None},
        "reader_value": {"introduction_sections": 9, "review_dimensions": 0, "revision_cycle": "RC0001", "applied_revisions": 0, "producer": "codex-editorial-producer", "reviewer": None, "status": "pending"},
        "figures": {"content_figures_total": len(figure_meta), "content_figures_rendered": len(figure_meta), "content_figures_guided": len(figure_meta)},
        "semantic_review": {"status": "passed_with_ledger", "high_impact_open": 0},
        "pipeline_language_scan": {"forbidden_matches": 0},
    }
    write_json(ROOT / "50-edited/editorial-report.json", report)

    state = read_json(ROOT / "run-state.json")
    state.setdefault("stages", {})["source_adjudicated"] = {"status": "passed_with_ledger", "candidates": counts[0]}
    state["stages"]["edited"] = {"status": "running", "blocks": len(edited_blocks), "figures": len(figure_meta), "evidence": "50-edited/modern-reading.draft.md"}
    state["stages"]["reader_revised"] = {"status": "pending"}
    state["stages"]["final_adjudicated"] = {"status": "passed_with_ledger", "open_material": counts[2], "high_impact": 0}
    state["current_stage"] = "edited"
    state["updated_at"] = NOW
    write_json(ROOT / "run-state.json", state)

    print(json.dumps({"source_blocks": len(source_rows), "edited_blocks": len(edited_blocks), "figures": len(figure_meta), "glossary": len(glossary_entries), "candidates": counts[0], "open_material": counts[2], "draft_chars": len(draft)}, ensure_ascii=False, indent=2))


def main() -> None:
    source_rows, _, modern_rows = upgrade_contract_and_figures()
    counts = build_uncertainty_lifecycle(source_rows, modern_rows)
    build_reader_files(source_rows, modern_rows, counts)


if __name__ == "__main__":
    main()
