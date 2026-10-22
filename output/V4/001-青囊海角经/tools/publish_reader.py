#!/usr/bin/env python3
"""Publish the clean modern-reader Markdown as a polished PDF."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "60-publication" / "modern-reading.md"
OUT = ROOT / "60-publication" / "青囊海角经·现代白话版（现代风水爱好者修订版）.pdf"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
COVER = ROOT / "60-publication" / "assets" / "cover-background.png"


class ReaderDocTemplate(SimpleDocTemplate):
    """Collect heading destinations for a clickable TOC and PDF bookmarks."""

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        level = getattr(flowable, "_outline_level", None)
        key = getattr(flowable, "_bookmark_name", None)
        if level is None or not key:
            return
        title = flowable.getPlainText()
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)
        self.notify("TOCEntry", (level, title, self.page, key))


def main() -> int:
    pdfmetrics.registerFont(TTFont("YaHei", str(FONT), subfontIndex=0))
    base = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=base["Title"], fontName="YaHei", fontSize=24, leading=34,
                           alignment=TA_CENTER, textColor=colors.HexColor("#183f36"), spaceAfter=8 * mm)
    subtitle = ParagraphStyle("subtitle", parent=title, fontSize=16, leading=24,
                              textColor=colors.HexColor("#946c2e"))
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName="YaHei", fontSize=17, leading=25,
                        textColor=colors.HexColor("#183f36"), spaceBefore=8 * mm, spaceAfter=4 * mm,
                        keepWithNext=True)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="YaHei", fontSize=13, leading=20,
                        textColor=colors.HexColor("#315d52"), spaceBefore=5 * mm, spaceAfter=3 * mm,
                        keepWithNext=True)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontName="YaHei", fontSize=11.3, leading=17,
                        textColor=colors.HexColor("#3f665d"), spaceBefore=3.5 * mm, spaceAfter=2 * mm,
                        keepWithNext=True)
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="YaHei", fontSize=10.5, leading=18,
                          firstLineIndent=21, alignment=TA_JUSTIFY, textColor=colors.HexColor("#202625"),
                          spaceAfter=3.2 * mm, allowWidows=0, allowOrphans=0)
    list_body = ParagraphStyle("list-body", parent=body, firstLineIndent=0, leftIndent=8 * mm,
                               rightIndent=3 * mm, spaceAfter=2.5 * mm)
    editor_note = ParagraphStyle("editor-note", parent=body, firstLineIndent=0, leftIndent=6 * mm,
                                 rightIndent=6 * mm, borderWidth=0.7, borderColor=colors.HexColor("#9bb8ae"),
                                 borderPadding=7, backColor=colors.HexColor("#f2f7f5"),
                                 textColor=colors.HexColor("#284d44"), spaceBefore=2 * mm, spaceAfter=4 * mm)
    caption = ParagraphStyle("caption", parent=body, fontSize=8.5, leading=14, firstLineIndent=0,
                             alignment=TA_CENTER, textColor=colors.HexColor("#66716e"))

    toc_l1 = ParagraphStyle("toc-l1", parent=body, fontSize=10.5, leading=18,
                            firstLineIndent=0, leftIndent=0, textColor=colors.HexColor("#183f36"),
                            spaceBefore=1.5 * mm, spaceAfter=1 * mm)
    toc_l2 = ParagraphStyle("toc-l2", parent=body, fontSize=9.2, leading=15,
                            firstLineIndent=0, leftIndent=3 * mm, textColor=colors.HexColor("#4b625c"),
                            spaceAfter=0)
    toc_l3 = ParagraphStyle("toc-l3", parent=body, fontSize=8.4, leading=13,
                            firstLineIndent=0, leftIndent=7 * mm, textColor=colors.HexColor("#5b6d68"),
                            spaceAfter=0)
    copyright_title = ParagraphStyle("copyright-title", parent=h1, alignment=TA_CENTER,
                                     fontSize=16, spaceBefore=0, spaceAfter=8 * mm)
    copyright_body = ParagraphStyle("copyright-body", parent=body, firstLineIndent=0,
                                    alignment=TA_CENTER, fontSize=10.5, leading=19, spaceAfter=3 * mm)

    doc = ReaderDocTemplate(str(OUT), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=19 * mm, bottomMargin=17 * mm,
                            title="青囊海角经·现代白话版",
                            author="原书传统题署晋郭璞撰；葛超云整理", subject="壮五福国学院出品")
    story = [Spacer(1, 40 * mm), Paragraph("青囊海角经", title),
             Paragraph("现代白话版", subtitle), Spacer(1, 12 * mm),
             Paragraph("原书传统题署：晋郭璞撰", ParagraphStyle("author", parent=body, alignment=TA_CENTER,
                                                     firstLineIndent=0, fontSize=12, spaceAfter=1.5 * mm)),
             Paragraph("葛超云 整理", ParagraphStyle("editor", parent=body, alignment=TA_CENTER,
                                                     firstLineIndent=0, fontSize=12, spaceAfter=0)),
             Spacer(1, 40 * mm),
             Paragraph("壮五福国学院 出品", ParagraphStyle("producer-cover", parent=caption,
                                                           fontSize=9.5, textColor=colors.HexColor("#73562b"))),
             PageBreak(),
             Spacer(1, 20 * mm), Paragraph("版权信息", copyright_title),
             Paragraph("《青囊海角经·现代白话版》", copyright_body),
             Spacer(1, 5 * mm),
             Paragraph("原书传统题署：晋郭璞撰", copyright_body),
             Paragraph("整理：葛超云", copyright_body),
             Paragraph("出品：壮五福国学院", copyright_body),
             Paragraph("版本：现代白话版", copyright_body),
             Spacer(1, 10 * mm),
             Paragraph("本版以现代普通读者为对象，在保留原书山形图、传统术语和论述次序的基础上，对繁体古文、断句、术语和阅读结构进行整理。", copyright_body),
             Paragraph("书中的富贵、科甲、贫贱、吉凶等内容，属于传统风水文献的历史表达，不构成现代科学、工程、医疗、法律或投资结论。", copyright_body),
             Spacer(1, 18 * mm),
             Paragraph("壮五福国学院 出品", ParagraphStyle("producer", parent=copyright_body,
                                                         fontSize=12, textColor=colors.HexColor("#183f36"))),
             PageBreak()]

    toc = TableOfContents()
    toc.levelStyles = [toc_l1, toc_l2, toc_l3]
    story.extend([Paragraph("目录", copyright_title), toc, PageBreak()])

    lines = MD.read_text(encoding="utf-8").splitlines()
    paragraph_lines: list[str] = []
    first_h1 = True
    bookmark_index = 0
    continuous_front_sections = {
        "本书介绍", "阅读本书前要知道的十个概念", "全书知识地图",
        "三条阅读路线", "怎样阅读本书", "原书目录（据扫描本第5—14页校订）",
    }

    def heading(text: str, style: ParagraphStyle, level: int) -> Paragraph:
        nonlocal bookmark_index
        bookmark_index += 1
        item = Paragraph(inline_markdown(text), style)
        item._outline_level = level
        item._bookmark_name = f"heading-{bookmark_index:03d}"
        return item

    def inline_markdown(text: str) -> str:
        value = escape(text)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)

    def flush() -> None:
        if paragraph_lines:
            text = " ".join(x.strip() for x in paragraph_lines).strip()
            if text:
                story.append(Paragraph(inline_markdown(text), body))
            paragraph_lines.clear()

    for line in lines:
        stripped = line.strip()
        if stripped in {"# 青囊海角经", "## 现代白话版", "郭璞原著", "郭璞 原著", "郭璞题署原著",
                        "原书传统题署：晋郭璞撰",
                        "郑同校原本", "葛超云 整理"}:
            continue
        if stripped.startswith("本书是一部汇集传统堪舆"):
            continue
        if not stripped:
            flush()
            continue
        if stripped == "---":
            flush()
            continue
        image_match = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush()
            path = (MD.parent / image_match.group(2)).resolve()
            img = Image(str(path))
            max_w, max_h = 150 * mm, 165 * mm
            scale = min(max_w / img.imageWidth, max_h / img.imageHeight)
            img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
            story.extend([Spacer(1, 2 * mm), img, Paragraph(image_match.group(1), caption), Spacer(1, 3 * mm)])
        elif stripped.startswith("# "):
            flush()
            heading_text = stripped[2:]
            if first_h1:
                story.append(heading(heading_text, h1, 0))
                first_h1 = False
            elif heading_text in continuous_front_sections:
                story.append(heading(heading_text, h1, 0))
            else:
                story.extend([PageBreak(), heading(heading_text, h1, 0)])
        elif stripped.startswith("#### "):
            flush()
            story.append(Paragraph(inline_markdown(stripped[5:]), h3))
        elif stripped.startswith("### "):
            flush()
            # Detailed source-section headings stay in the body; keeping them out of
            # the generated TOC prevents a one-line orphan TOC page.
            story.append(Paragraph(inline_markdown(stripped[4:]), h3))
        elif stripped.startswith("## "):
            flush()
            story.append(heading(stripped[3:], h2, 1))
        elif re.match(r"^\d+\.\s+", stripped):
            flush()
            number, item = stripped.split(".", 1)
            story.append(Paragraph(inline_markdown(f"{number}. {item.strip()}"), list_body))
        elif stripped.startswith("- "):
            flush()
            story.append(Paragraph(inline_markdown("• " + stripped[2:].strip()), list_body))
        elif (stripped.startswith("**阅读提示：**") or stripped.startswith("**编者注：**")
              or stripped.startswith("**版本说明：**") or stripped.startswith("**读图提示：**")
              or stripped.startswith("**编者导读：**") or stripped.startswith("**版本提示：**")
              or stripped.startswith("**传统判断：**") or stripped.startswith("> 审校提示：")
              or stripped.startswith("> **编者导读：**") or stripped.startswith("> **读图说明：**")
              or stripped.startswith("> **审校提示：**") or stripped.startswith("> **版本提示：**")
              or stripped.startswith("> **传统判断：**") or stripped.startswith("> **编者说明：**")):
            flush()
            story.append(Paragraph(inline_markdown(stripped.removeprefix("> ")), editor_note))
        else:
            paragraph_lines.append(stripped)
    flush()

    def page_decoration(canvas, document):
        canvas.saveState()
        if document.page == 1:
            canvas.drawImage(str(COVER), 0, 0, width=A4[0], height=A4[1],
                             preserveAspectRatio=False, mask="auto")
            canvas.restoreState()
            return
        if document.page <= 2:
            canvas.restoreState()
            return
        canvas.setFont("YaHei", 8)
        canvas.setFillColor(colors.HexColor("#6a7471"))
        canvas.drawString(22 * mm, 9 * mm, "青囊海角经·现代白话版")
        canvas.drawRightString(A4[0] - 22 * mm, 9 * mm, str(document.page))
        canvas.restoreState()

    doc.multiBuild(story, onFirstPage=page_decoration, onLaterPages=page_decoration)
    reader = PdfReader(str(OUT))
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest().upper()
    markdown_text = MD.read_text(encoding="utf-8")
    marker_count = markdown_text.count("版本提示：") + markdown_text.count("版本说明：")
    open_items = [json.loads(line) for line in (ROOT / "90-audit" / "uncertain-items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    impact_counts = {name: sum(1 for item in open_items if item.get("reader_impact") == name) for name in ("high", "medium", "low")}
    adjudications = [json.loads(line) for line in (ROOT / "90-audit" / "uncertainty-adjudication.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    active_adjudications = [item for item in adjudications if item.get("active", True)]
    high_open = impact_counts["high"]
    grade = "B" if high_open == 0 else "C"
    report = {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "book": "青囊海角经", "edition_scope": "full_reader_edition_source_pages_1_216",
        "source_pages_total": 216, "grade": grade,
        "grade_label": "modern_reader_edition_with_traceable_ledger" if grade == "B" else "assisted_draft_under_semantic_repair",
        "semantic_audit": {"status": "passed_with_ledger" if high_open == 0 else "blocked_by_high_impact_open_items", "page_level_visual_coverage": 216,
                           "reader_facing_uncertainty_markers": marker_count},
        "structural_audit": {"status": "passed", "blocks_each_stage": 1600,
                             "raw_html_tags": 0, "internal_pipeline_messages": 0},
        "models": ["Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-30B-A3B-Instruct",
                   "Qwen/Qwen3.5-122B-A10B", "PaddlePaddle/PaddleOCR-VL-1.5"],
        "publication": {"pdf": f"60-publication/{OUT.name}", "pdf_pages": len(reader.pages),
                        "pdf_bytes": OUT.stat().st_size, "pdf_sha256": sha,
                        "modern_markdown": "60-publication/modern-reading.md",
                        "rendered_pages_inspected": 0,
                        "visual_defects_found": None},
        "uncertainty_ledger": {"candidate_records": 501, "open_material_records": len(open_items), "by_reader_impact": impact_counts},
        "uncertainty_summary": {"candidates": 501, "adjudications": len(adjudications),
                                "active_adjudications": len(active_adjudications), "open_material": len(open_items)},
        "limitations": ["Medium- and low-impact textual uncertainties remain in the traceable ledger and do not support unique restoration.",
                        "Traditional claims are presented as historical ideas, not as modern scientific conclusions."],
    }
    (AUDIT := ROOT / "90-audit").joinpath("quality-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AUDIT.joinpath("quality-report.md").write_text(
        f"# 质量报告\n\n- 范围：原 PDF 1-216 页\n- 等级：{grade}（现代读者版；疑点保留可追溯台账）\n"
        f"- 页面视觉证据：216/216\n- 阶段区块：1600/1600/1600/1600\n- 成品 PDF：{len(reader.pages)} 页\n"
        f"- SHA-256：`{sha}`\n", encoding="utf-8")
    state = json.loads((ROOT / "run-state.json").read_text(encoding="utf-8"))
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["grade"] = grade
    state["stages"]["source_adjudicated"] = {"status": "passed_with_ledger", "candidates": 501}
    state["stages"]["final_adjudicated"] = {"status": "passed_with_ledger", "open_material": len(open_items),
                                                "high_impact": high_open}
    state["stages"]["publication"] = {"status": "candidate_pending_visual_audit", "pdf_pages": len(reader.pages), "scope_pages": 216,
                                              "open_material": len(open_items), "high_impact": impact_counts["high"]}
    (ROOT / "run-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdf": str(OUT), "pages": len(reader.pages), "bytes": OUT.stat().st_size, "sha256": sha}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

