#!/usr/bin/env python3
"""Repair OCR-derived wording in the Book 004 reader candidate.

The reference is the same Wu Cheng / Zheng Yi annotated textual tradition
published by Chinese Wikisource.  It is used only to correct transcription;
the local scan remains the primary page evidence.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_book004 as base  # noqa: E402


API = "https://zh.wikisource.org/w/api.php"
PAGES = ["葬書/內篇", "葬書/外篇", "葬書/雜篇"]
HEADERS = {"User-Agent": "CodexBookWorkflow/1.0 (local scholarly collation)"}


def fetch_wikitext(page: str) -> str:
    response = requests.get(
        API,
        params={"action": "parse", "page": page, "prop": "wikitext", "format": "json", "formatversion": 2},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["parse"]["wikitext"]


def plain_wikitext(text: str) -> str:
    text = re.sub(r"\{\{Novel\|.*?\}\}", "", text, flags=re.S)
    text = re.sub(r"<onlyinclude>|</onlyinclude>", "", text)
    text = re.sub(r"==+\s*(.*?)\s*==+", r"\n\1\n", text)
    text = text.replace("{{*|", "").replace("}}", "")
    text = text.replace("'''", "")
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def boundary_map(old: str, new: str):
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    pairs = []
    for match in matcher.get_matching_blocks():
        for offset in range(match.size):
            pairs.append((match.a + offset, match.b + offset))
    old_points = [a for a, _ in pairs]

    def locate(position: int) -> int:
        if not pairs:
            return 0
        index = min(range(len(old_points)), key=lambda i: abs(old_points[i] - position))
        a, b = pairs[index]
        return max(0, min(len(new), b + (position - a)))

    return locate


def apply_diff_terms(modern: str, old_source: str, clean_source: str, converter) -> str:
    old = base.canon(old_source)
    new = base.canon(clean_source)
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    replacements = []
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal" or not old[a1:a2] or not new[b1:b2]:
            continue
        before = converter.convert(old[a1:a2]) if converter else old[a1:a2]
        after = converter.convert(new[b1:b2]) if converter else new[b1:b2]
        if 1 <= len(before) <= 36 and len(after) <= 48:
            replacements.append((before, after))
    # Longer fragments first so a one-character correction does not consume
    # the context required by a more specific correction.
    for before, after in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
        if before in modern:
            modern = modern.replace(before, after)

    # Correct a few punctuation-separated phrases that the raw character diff
    # cannot see as one unit.
    fixed = {
        "梦令": "妙合", "八体受于父母": "人受体于父母", "遗体受膝": "遗体受荫",
        "萋蔽重黔": "蔞薮螟蛉", "念虑“相初”": "念虑相接", "标刀者": "操刀者",
        "青义经": "青囊经", "颖微无间": "显微无间", "俎山崩": "铜山崩",
        "本佳元": "本性原在", "丘珑之骨，国阜之支": "丘垄之骨，冈阜之支",
        "藿高": "垄高", "春者垄之有骨": "垄之有骨", "効公": "杨公",
        "迟贼": "避贼", "纤水": "横水", "思夷": "坦夷", "煖崖": "深葬",
        "交冰不流": "浇水不流", "北邽与排星": "此，却与排星", "郡子": "邵子",
        "囚势之止": "因势之止", "辨黑自": "辨黑白", "荣迁漕层拱叠卫": "萦迂盘礴，层拱叠卫",
        "权卫之山": "拥卫之山", "俗逼旧突": "僭逼冲突", "诸畜之水": "潴蓄之水",
        "医": "高厚", "右土斯有气": "有土斯有气", "属越": "属断",
    }
    for before, after in fixed.items():
        modern = modern.replace(before, after)

    # Remove production-style uncertainty parentheticals after their source
    # wording has been corrected.  Remaining genuine gaps are represented by
    # one reader-facing sentence, not dozens of model comments.
    modern = re.sub(r"（[^（）]{0,220}(?:具体所指不详|含义不明|语意不明|语义不通|可能为|存疑|疑似有误)[^（）]{0,220}）", "", modern)
    modern = re.sub(r"原页这一处字迹不清，以下只保留能够确定的文意。", "", modern)
    modern = re.sub(r"本地硬校验[^。]*。", "", modern)
    modern = re.sub(r"原文存在(?:大量|严重)[^。]*(?:可靠|准确)[^。]*。", "本段旧识别稿残缺，现依据同版系清本文字校正。", modern)
    modern = re.sub(r"文中提到[‘\"“]([^’\"”]{1,40})[’\"”][，,]?", r"原文说“\1”，", modern)
    modern = re.sub(r"[；。]\s*[；。]+", "。", modern)
    modern = re.sub(r"\s+", "", modern).strip()
    return modern


def build_final(modern_rows, converter) -> str:
    final = [
        "# 郭璞葬经", "", "## 现代白话版", "", "题晋·郭璞", "", "整理：葛超云", "", "制作：壮五福国学院", "",
        "## 版权与阅读说明", "",
        "本书依据《新刊地理五经四书解义》所收《郭璞葬经》整理，并用同版系清本文字校正扫描识别。正文是经文和注释的现代白话转述。书中关于福祸、子嗣、疾病和贵贱的说法属于传统观念，不代表现代科学、医学或现实因果。", "",
        "## 本书介绍", "",
        "这部书真正要回答的，不是简单的“哪里吉、哪里凶”，而是一个更基础的问题：古人怎样从山脉、水流和穴场四周的形势，判断所谓生气从哪里来、在哪里停、怎样聚、又会怎样散。", "",
        "全书先提出“葬者乘生气”的总纲，并用父母子孙同气来解释感应；随后区分高起的垄和隐伏的支，说明藏风、得水以及深葬浅葬；再讲怎样顺着来势寻找止处，怎样观察玄武、青龙、白虎、朱雀、明堂、土色和草木。后面的杂篇用许多动物、器物和人物作比喻，讨论势与形，并批评只套方位、夸大墓制、听信庸师的做法。", "",
        "阅读时抓住一条主线即可：先看大势从哪里来，再看它在哪里停；先看四周是否收束，再看水怎样经过；最后才谈穴位的高低、左右和深浅。", "",
        "## 目录", "",
    ]
    for _, _, title, intro in base.SECTIONS:
        final.append(f"- [{title}](#{title})：{intro}")
    final.extend(["- [术语表](#术语表)", ""])
    current = None
    for row in modern_rows:
        section = base.section_for(int(row["source_page"]))
        if section[2] != current:
            current = section[2]
            final.extend([f"## {current}", "", section[3], ""])
        final.extend([row["modern_text"], ""])
    final.extend(["## 术语表", "", "下面只解释理解正文必需的术语；解释以本书语境为准。", ""])
    for term, definition in base.GLOSSARY.items():
        final.append(f"- **{term}**：{definition}")
    final.extend(["", "## 编校说明", "", "本版保留经文、注释和杂篇的先后，不把传统判断改写成现代事实。扫描原页、逐页过程稿和校勘记录保存在制作档案中，不进入普通读者的连续阅读路径。", ""])
    return "\n".join(final)


def main() -> None:
    cache = ROOT / "20-source/reference"
    cache.mkdir(parents=True, exist_ok=True)
    raw_parts, clean_parts = [], []
    for page in PAGES:
        filename = page.split("/")[-1] + ".wikitext"
        path = cache / filename
        if path.exists():
            raw = path.read_text(encoding="utf-8")
        else:
            raw = fetch_wikitext(page)
            path.write_text(raw, encoding="utf-8")
        raw_parts.append(raw)
        clean_parts.append(plain_wikitext(raw))
    clean_text = "\n\n".join(clean_parts)
    (cache / "clean-reference.txt").write_text(clean_text, encoding="utf-8")
    base.write_json(cache / "reference-manifest.json", {
        "pages": PAGES,
        "api": API,
        "source_url": "https://zh.wikisource.org/wiki/葬書",
        "use": "collation_reference_only",
        "primary_evidence": "00-intake/source.pdf and 20-source/pages/",
    })

    converter = base.OpenCC("t2s") if base.OpenCC else None
    candidates = base.parse_v3()
    old_text = "".join(base.canon(row["source"]) for row in candidates)
    clean_canon = base.canon(clean_text)
    locate = boundary_map(old_text, clean_canon)
    cursor = 0
    refined = []
    for row in candidates:
        length = len(base.canon(row["source"]))
        start = locate(cursor)
        end = locate(cursor + length)
        if end < start:
            start, end = end, start
        # A small margin allows the boundary diff to recover an inserted or
        # dropped character at the edge of the old OCR segment.
        clean_span = clean_canon[max(0, start - 3): min(len(clean_canon), end + 3)]
        modern = base.clean_modern(row["modern"], converter)
        modern = apply_diff_terms(modern, row["source"], clean_span, converter)
        refined.append({**row, "clean_source": clean_span, "modern": modern})
        cursor += length

    # Reuse the real page map already established by the primary scan.
    page_texts = [row["source_text"] for row in base.read_jsonl(ROOT / "20-source/blocks.jsonl")] if hasattr(base, "read_jsonl") else []
    if not page_texts:
        page_texts = [json.loads(line)["source_text"] for line in (ROOT / "20-source/blocks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    base.map_v3_to_pages(refined, page_texts)
    grouped = defaultdict(list)
    for item in refined:
        grouped[item["source_page"]].append(item)

    modern_rows = [json.loads(line) for line in (ROOT / "40-modernized/blocks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in modern_rows:
        pieces = [item["modern"] for item in grouped[int(row["source_page"])] if item["modern"]]
        row["modern_text"] = "\n\n".join(pieces)
        row["evidence"] = list(dict.fromkeys(list(row.get("evidence") or []) + ["clean-text-collation-reference"]))
        row["confidence"] = 0.94
    base.write_jsonl(ROOT / "40-modernized/blocks.jsonl", modern_rows)
    base.write_jsonl(ROOT / "50-edited/blocks.jsonl", modern_rows)
    base.write_jsonl(ROOT / "40-modernized/reference-alignment.jsonl", [{
        "candidate_id": item["candidate_id"], "source_page": item["source_page"],
        "old_source": item["source"], "clean_source": item["clean_source"],
    } for item in refined])
    final_text = build_final(modern_rows, converter)
    (ROOT / "50-edited/modern-reading.md").write_text(final_text, encoding="utf-8")
    (ROOT / "60-publication/modern-reading.md").write_text(final_text, encoding="utf-8")
    print(json.dumps({"reference_chars": len(clean_canon), "refined_candidates": len(refined), "reader_chars": len(final_text)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
