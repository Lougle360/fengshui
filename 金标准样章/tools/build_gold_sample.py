"""Build the gold-sample comparison drafts from selection.json and copy their page images.

Reads output/ and 缺陷库/ only; everything is written under 金标准样章/.
usage: python build_gold_sample.py
"""
import json
import re
import shutil
from functools import lru_cache

from common import BOOK_NAMES, CURRENT_VERSIONS, GAP_RE, GOLD, OUTPUT, WORKSPACES, blocks, defects, shingles

SELECTION = json.loads((GOLD / "tools" / "selection.json").read_text(encoding="utf-8"))
IMG_DIR = GOLD / "原页图"
SOURCE_COMMENT = re.compile(r"<!--\s*source:([^>]*?)\s*-->")
PAGE_HEADING = re.compile(r"^#+\s*原书第")
TYPE_NAMES = {"body": "正文", "title": "标题", "heading": "标题", "commentary": "注文",
              "commentary_unaligned": "注文（续）", "figure": "图", "图解": "图解", "text": "正文",
              "image_footnote": "图注", "running_header": "版心"}
BLANK = "> （待填）"


def clean_paragraph(p):
    lines = []
    for ln in p.splitlines():
        ln = SOURCE_COMMENT.sub("", ln).strip()
        ln = re.sub(r"^>\s?", "", ln)
        if ln:
            lines.append(ln)
    return "\n".join(lines)


@lru_cache(None)
def reader_index(book):
    """Cleaned reader paragraphs, their first line numbers, and block_id -> paragraph index from source comments."""
    text = (OUTPUT / WORKSPACES[book] / "60-publication" / "modern-reading.md").read_text(encoding="utf-8")
    cleaned, line_nos, by_id = [], [], {}
    for m in re.finditer(r"\S(?:.|\n(?!\s*\n))*", text):
        p = m.group(0).strip()
        for c in SOURCE_COMMENT.finditer(p):
            for bid in c.group(1).split(","):
                by_id.setdefault(bid.strip(), len(cleaned))
        cleaned.append(clean_paragraph(p))
        line_nos.append(text.count("\n", 0, m.start()) + 1)
    return cleaned, line_nos, by_id


def locate(book, block, hint):
    """Index of the reader paragraph carrying this block, preferring paragraphs near hint."""
    cleaned, _, by_id = reader_index(book)
    if block["block_id"] in by_id:
        return by_id[block["block_id"]]
    text = (block.get("modern_text") or "").strip()
    if not text:
        return None
    target = shingles(text)
    if len(target) < 2:
        target = set()
    best, best_key = None, None
    for i, p in enumerate(cleaned):
        if not p or PAGE_HEADING.match(p):
            continue
        if target:
            score = len(target & shingles(p))
            if score < max(2, len(target) // 5):
                continue
        else:
            if text not in p:
                continue
            score = 1 if p.strip("#* ") == text else 0.5
        key = (score, -abs(i - hint) if hint is not None else 0)
        if best_key is None or key > best_key:
            best, best_key = i, key
    return best


@lru_cache(None)
def defect_map():
    """block_id -> current-version defects that point at a handful of blocks (not whole-book findings)."""
    m = {}
    for d in defects():
        if not (d.get("version") in CURRENT_VERSIONS or any(v in CURRENT_VERSIONS for v in d.get("versions") or [])):
            continue
        ids = [x.strip() for x in str(d["location"].get("block") or "").split(",") if x.strip()]
        if not ids or len(ids) > 3:
            continue
        for bid in ids:
            m.setdefault((d["book"][:3], bid), []).append(d)
    return m


def defect_label(d):
    label = f"{d['defect_id']}（{d['category']}/{d.get('subcategory') or '—'}"
    if d.get("outcome") == "not_defect":
        label += "，缺陷库判为非缺陷"
    return label + "）"


def qian_as_gan(src, pub):
    if "乾" not in src:
        return False
    stripped = re.sub(r"[天主大树若相]干|干支", "", pub)
    return "干" in stripped


def extra_issue_labels(block, pub, extra):
    labels = []
    for issue in extra:
        if issue["kind"] == "乾误作干":
            hit = qian_as_gan(block.get("source_text") or "", pub)
        else:
            hit = issue["match"] in pub
        if hit and issue["note"] not in labels:
            labels.append(issue["note"])
    return labels


def image_name(book, block):
    return f"{book}-P{int(block['source_page']):06d}.jpg"


def copy_image(book, block, copied):
    name = image_name(book, block)
    if name not in copied:
        src = OUTPUT / WORKSPACES[book] / block["source_image"]
        shutil.copy2(src, IMG_DIR / name)
        copied.add(name)
    return name


def quote(text):
    return "\n".join("> " + ln if ln.strip() else ">" for ln in (text or "").strip().splitlines()) or ">"


class Renderer:
    def __init__(self, book):
        self.book = book
        self.index = {b["block_id"]: b for b in blocks(book)}
        self.hint = None
        self.last_idx = None

    def current_text(self, block):
        idx = locate(self.book, block, self.hint)
        if idx is None:
            return None, (block.get("modern_text") or "").strip(), "读者稿中未找到此段，以下取自编辑层"
        self.hint = idx
        cleaned, line_nos, _ = reader_index(self.book)
        return idx, cleaned[idx], f"读者稿 modern-reading.md 第 {line_nos[idx]} 行"

    def block_section(self, block, copied, extra=(), with_blanks=True, heading_level="###"):
        book = self.book
        img = copy_image(book, block, copied)
        idx, pub, where = self.current_text(block)
        same_as_last = idx is not None and idx == self.last_idx
        self.last_idx = idx
        kind = TYPE_NAMES.get(block.get("block_type"), block.get("block_type") or "")
        links = []
        if block.get("continuation_from") or block.get("continues_from_previous_page"):
            links.append(f"接上页 {block.get('continuation_from') or ''}".strip())
        if block.get("continuation_to") or block.get("continues_to_next_page"):
            links.append(f"转下页 {block.get('continuation_to') or ''}".strip())
        out = [f"{heading_level} {block['block_id']} · {kind}", ""]
        out.append(f"原页图：`原页图/{img}`（原书第 {block['source_page']} 页）" + (f"；{'，'.join(links)}" if links else ""))
        out += ["", "**原文**", "", quote(block.get("source_text")), ""]
        if same_as_last:
            out += [f"**AI 现稿**（{where}）：与上一块同属读者稿一段，见上。", ""]
        else:
            out += [f"**AI 现稿**（{where}）", "", quote(pub), ""]
        issues = [defect_label(d) for d in defect_map().get((book, block["block_id"]), [])]
        issues += extra_issue_labels(block, pub, extra)
        gaps = len(GAP_RE.findall(pub)) if not same_as_last else 0
        if gaps:
            issues.append(f"现稿含“不详/不明”类说法 {gaps} 处")
        if with_blanks:
            out += ["**已知问题**：" + ("；".join(issues) if issues else "缺陷库无记录"), ""]
            out += ["**老师定稿**", "", BLANK, "", "**改动理由**", "", BLANK, ""]
        record = {"block_id": block["block_id"], "page": block["source_page"], "image": img,
                  "source_text": block.get("source_text"), "current_text": None if same_as_last else pub,
                  "current_from": where, "issues": issues, "gap_phrases": gaps}
        return out, record


def page_blocks(book, pages):
    return [b for b in blocks(book) if b.get("source_page") in pages]


def build_passage(copied):
    p = SELECTION["passage"]["default"]
    book = p["book"]
    r = Renderer(book)
    body = page_blocks(book, set(p["pages"]))
    records, lines = [], []
    src_chars = sum(len(re.sub(r"\s", "", b.get("source_text") or "")) for b in body)

    ctx_lines = []
    for bid in p.get("context_before", []):
        sec, _ = r.block_section(r.index[bid], copied, with_blanks=False, heading_level="####")
        ctx_lines += sec
    for b in body:
        sec, rec = r.block_section(b, copied, p.get("extra_issues", []))
        lines += sec + ["---", ""]
        records.append(rec)
    tail_lines = []
    for bid in p.get("context_after", []):
        sec, _ = r.block_section(r.index[bid], copied, with_blanks=False, heading_level="####")
        tail_lines += sec

    gaps = sum(x["gap_phrases"] for x in records)
    defect_ids = sorted({i.split("（")[0] for x in records for i in x["issues"] if i.startswith("D")})
    pages = "、".join(str(x) for x in p["pages"])
    head = [
        f"# 金标准样章 · 连续正文：{p['title']}",
        "",
        f"- 书：{BOOK_NAMES[book]}（当前版本 `{WORKSPACES[book]}`）",
        f"- 原书页：第 {pages} 页，原页图见 `原页图/` 目录",
        f"- 篇幅：原文 {src_chars} 字，{len(records)} 个段块",
        f"- 现稿中“不详/不明”类说法共 {gaps} 处；缺陷库记录 {len(defect_ids)} 条",
        "- 目标读者：普通读者",
        "",
        "填写方法：每个段块下面有“老师定稿”和“改动理由”两栏。定稿栏写您认为普通读者该读到的白话；"
        "不需要改的写“同现稿”；理由栏写一句话即可。“已知问题”只是提示，不代表一定要改，也可能有遗漏。",
        "",
        "## 上文衔接（只供参考，不必填写）",
        "",
    ]
    doc = head + ctx_lines + ["## 正文", ""] + lines + ["## 下文衔接（只供参考，不必填写）", ""] + tail_lines
    (GOLD / "样章-连续正文.md").write_text("\n".join(doc).rstrip() + "\n", encoding="utf-8")
    return {"book": book, "pages": p["pages"], "title": p["title"], "source_chars": src_chars,
            "gap_phrases": gaps, "blocks": records}


def build_fragments(copied):
    lines = [
        "# 金标准样章 · 专项片段",
        "",
        "每个片段针对一类反复出现的问题。请在“老师定稿”栏写出普通读者该读到的白话，"
        "在“改动理由”栏写一句话说明为什么这样改（或为什么不改）。“已知问题”是 AI 工作记录里的描述，只作提示。",
        "",
        "| 编号 | 类别 | 书 · 页 |",
        "|---|---|---|",
    ]
    body, records = [], []
    for f in SELECTION["fragments"]:
        book = f["book"]
        r = Renderer(book)
        bls = [r.index[bid] for bid in f["blocks"]]
        pages = "～".join(sorted({str(b["source_page"]) for b in bls}, key=int))
        lines.append(f"| {f['id']} | {f['slot']} | {BOOK_NAMES[book]} · 第 {pages} 页 |")
        body += [f"## {f['id']} · {f['slot']} · {BOOK_NAMES[book]} 第 {pages} 页", ""]
        body += [f"**为什么选这一段**：{f['why']}", ""]
        ids = "、".join(f["defect_ids"]) if f["defect_ids"] else "缺陷库未收录"
        body += [f"**已知问题**（{ids}）：{f['problem']}", ""]
        recs = []
        for b in bls:
            sec, rec = r.block_section(b, copied, with_blanks=False)
            body += sec
            recs.append(rec)
        body += ["**老师定稿**", "", BLANK, "", "**改动理由**", "", BLANK, "", "---", ""]
        records.append({**f, "blocks": recs})
    doc = lines + [""] + body
    (GOLD / "样章-专项片段.md").write_text("\n".join(doc).rstrip() + "\n", encoding="utf-8")
    return records


def main():
    IMG_DIR.mkdir(exist_ok=True)
    copied = set()
    passage = build_passage(copied)
    fragments = build_fragments(copied)
    data = {"reader": "普通读者", "passage": passage, "fragments": fragments, "images": sorted(copied)}
    (GOLD / "tools" / "gold_items.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"passage blocks={len(passage['blocks'])} gaps={passage['gap_phrases']} "
          f"fragments={len(fragments)} images={len(copied)}")


if __name__ == "__main__":
    main()
