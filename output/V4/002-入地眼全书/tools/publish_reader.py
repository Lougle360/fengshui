#!/usr/bin/env python3
"""Render Book 002's ordinary-reader Markdown as the official PDF."""

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
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "60-publication" / "modern-reading.md"
OUT = ROOT / "60-publication" / "入地眼全书·现代白话版.pdf"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


class ReaderDoc(SimpleDocTemplate):
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
    cover_title = ParagraphStyle(
        "cover-title", parent=base["Title"], fontName="YaHei", fontSize=34,
        leading=48, alignment=TA_CENTER, textColor=colors.HexColor("#f4dfaa"),
        spaceAfter=10 * mm,
    )
    cover_subtitle = ParagraphStyle(
        "cover-subtitle", parent=cover_title, fontSize=18, leading=28,
        textColor=colors.HexColor("#f4ead0"),
    )
    cover_line = ParagraphStyle(
        "cover-line", parent=cover_title, fontSize=12, leading=20,
        textColor=colors.HexColor("#efe6cf"), spaceAfter=2 * mm,
    )
    h1 = ParagraphStyle(
        "h1", parent=base["Heading1"], fontName="YaHei", fontSize=17,
        leading=25, textColor=colors.HexColor("#183f36"), spaceBefore=8 * mm,
        spaceAfter=4 * mm, keepWithNext=True,
    )
    h2 = ParagraphStyle(
        "h2", parent=base["Heading2"], fontName="YaHei", fontSize=14,
        leading=21, textColor=colors.HexColor("#315d52"), spaceBefore=6 * mm,
        spaceAfter=3 * mm, keepWithNext=True,
    )
    h3 = ParagraphStyle(
        "h3", parent=base["Heading3"], fontName="YaHei", fontSize=11.4,
        leading=18, textColor=colors.HexColor("#486a62"), spaceBefore=4 * mm,
        spaceAfter=2 * mm, keepWithNext=True,
    )
    h4 = ParagraphStyle(
        "h4", parent=h3, fontSize=10.6, leading=17,
        textColor=colors.HexColor("#6e542d"), spaceBefore=3 * mm,
    )
    body = ParagraphStyle(
        "body", parent=base["BodyText"], fontName="YaHei", fontSize=10.2,
        leading=18, firstLineIndent=20.4, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#202625"), spaceAfter=3.2 * mm,
        allowWidows=0, allowOrphans=0,
    )
    list_body = ParagraphStyle(
        "list-body", parent=body, firstLineIndent=0, leftIndent=7 * mm,
        rightIndent=3 * mm, spaceAfter=2.3 * mm,
    )
    note = ParagraphStyle(
        "note", parent=body, firstLineIndent=0, leftIndent=5 * mm,
        rightIndent=5 * mm, borderWidth=0.7,
        borderColor=colors.HexColor("#9bb8ae"), borderPadding=7,
        backColor=colors.HexColor("#f2f7f5"),
        textColor=colors.HexColor("#284d44"), spaceBefore=2 * mm,
        spaceAfter=4 * mm,
    )
    caption = ParagraphStyle(
        "caption", parent=body, fontSize=8.3, leading=13,
        firstLineIndent=0, alignment=TA_CENTER,
        textColor=colors.HexColor("#66716e"),
    )
    toc_l1 = ParagraphStyle(
        "toc-l1", parent=body, fontSize=10, leading=16,
        firstLineIndent=0, leftIndent=0,
        textColor=colors.HexColor("#183f36"), spaceAfter=1 * mm,
    )
    copyright_title = ParagraphStyle(
        "copyright-title", parent=h1, alignment=TA_CENTER,
        fontSize=16, spaceBefore=0, spaceAfter=8 * mm,
    )
    copyright_body = ParagraphStyle(
        "copyright-body", parent=body, firstLineIndent=0,
        alignment=TA_CENTER, fontSize=10.2, leading=19,
        spaceAfter=3 * mm,
    )

    doc = ReaderDoc(
        str(OUT), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=19 * mm, bottomMargin=17 * mm,
        title="入地眼全书·现代白话版",
        author="宋·托长老；葛超云整理",
        subject="壮五福国学院出品",
    )
    story = [
        Spacer(1, 38 * mm),
        Paragraph("入地眼全书", cover_title),
        Paragraph("现代白话版", cover_subtitle),
        Spacer(1, 12 * mm),
        Paragraph("宋·托长老 原著", cover_line),
        Paragraph("葛超云 整理", cover_line),
        Spacer(1, 42 * mm),
        Paragraph("壮五福国学院 出品", cover_line),
        PageBreak(),
        Spacer(1, 18 * mm),
        Paragraph("版权与版本信息", copyright_title),
        Paragraph("《入地眼全书·现代白话版》", copyright_body),
        Spacer(1, 5 * mm),
        Paragraph("原著：宋·托长老", copyright_body),
        Paragraph("原编：万树华", copyright_body),
        Paragraph("整理：葛超云", copyright_body),
        Paragraph("出品：壮五福国学院", copyright_body),
        Paragraph("版本：现代白话版", copyright_body),
        Spacer(1, 9 * mm),
        Paragraph(
            "本版以道光丙戌新镌、文星堂藏板本为来源，按原书 162 个物理页建立页级图像证据与块级追溯链。",
            copyright_body,
        ),
        Paragraph(
            "书中的吉凶、福祸、子嗣、疾病及官禄判断属传统文献表述，不构成现代科学、医学、工程、法律或投资建议。",
            copyright_body,
        ),
        Spacer(1, 15 * mm),
        Paragraph(
            "壮五福国学院 出品",
            ParagraphStyle(
                "producer", parent=copyright_body, fontSize=12,
                textColor=colors.HexColor("#183f36"),
            ),
        ),
        PageBreak(),
    ]
    toc = TableOfContents()
    toc.levelStyles = [toc_l1]
    story.extend([Paragraph("目录", copyright_title), toc, PageBreak()])

    def inline(text: str) -> str:
        value = escape(text)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)

    bookmark_index = 0

    def bookmarked(text: str, style: ParagraphStyle) -> Paragraph:
        nonlocal bookmark_index
        bookmark_index += 1
        para = Paragraph(inline(text), style)
        para._outline_level = 0
        para._bookmark_name = f"section-{bookmark_index:03d}"
        return para

    paragraph_lines: list[str] = []

    def flush() -> None:
        if paragraph_lines:
            value = " ".join(x.strip() for x in paragraph_lines).strip()
            if value:
                story.append(Paragraph(inline(value), body))
            paragraph_lines.clear()

    for line in MD.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped in {"# 入地眼全书", "## 现代白话版"}:
            continue
        if not stripped or stripped == "---":
            flush()
            continue
        image_match = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush()
            path = (MD.parent / image_match.group(2)).resolve()
            image = Image(str(path))
            scale = min((145 * mm) / image.imageWidth, (170 * mm) / image.imageHeight)
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            story.extend(
                [Spacer(1, 2 * mm), image, Paragraph(inline(image_match.group(1)), caption), Spacer(1, 3 * mm)]
            )
        elif stripped.startswith("#### "):
            flush(); story.append(Paragraph(inline(stripped[5:]), h4))
        elif stripped.startswith("### "):
            flush(); story.append(Paragraph(inline(stripped[4:]), h3))
        elif stripped.startswith("## "):
            flush(); story.append(bookmarked(stripped[3:], h2))
        elif stripped.startswith("# "):
            flush(); story.append(bookmarked(stripped[2:], h1))
        elif stripped.startswith("> "):
            flush(); story.append(KeepTogether([Paragraph(inline(stripped[2:]), note)]))
        elif re.match(r"^\d+\.\s+", stripped):
            flush(); story.append(Paragraph(inline(stripped), list_body))
        elif stripped.startswith("- "):
            flush(); story.append(Paragraph(inline("• " + stripped[2:]), list_body))
        else:
            paragraph_lines.append(stripped)
    flush()

    def decorate(canvas, document):
        canvas.saveState()
        if document.page == 1:
            canvas.setFillColor(colors.HexColor("#173b35"))
            canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            canvas.setStrokeColor(colors.HexColor("#b8924f"))
            canvas.setLineWidth(1.2)
            canvas.rect(13 * mm, 13 * mm, A4[0] - 26 * mm, A4[1] - 26 * mm, fill=0, stroke=1)
            canvas.setLineWidth(0.4)
            canvas.rect(16 * mm, 16 * mm, A4[0] - 32 * mm, A4[1] - 32 * mm, fill=0, stroke=1)
            canvas.restoreState()
            return
        if document.page > 2:
            canvas.setFont("YaHei", 8)
            canvas.setFillColor(colors.HexColor("#6a7471"))
            canvas.drawString(22 * mm, 9 * mm, "入地眼全书·现代白话版")
            canvas.drawRightString(A4[0] - 22 * mm, 9 * mm, str(document.page))
        canvas.restoreState()

    doc.multiBuild(story, onFirstPage=decorate, onLaterPages=decorate)
    reader = PdfReader(str(OUT))
    result = {
        "pdf": str(OUT),
        "pages": len(reader.pages),
        "bytes": OUT.stat().st_size,
        "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest().upper(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
