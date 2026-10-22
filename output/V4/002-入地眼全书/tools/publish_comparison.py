#!/usr/bin/env python3
"""Publish a page-image/source/modern-text comparison edition."""

from __future__ import annotations

import json
from collections import defaultdict
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


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "60-publication" / "入地眼全书·原文对照版.pdf"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ComparisonDoc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and hasattr(flowable, "_bookmark"):
            self.canv.bookmarkPage(flowable._bookmark)
            self.canv.addOutlineEntry(
                flowable.getPlainText(), flowable._bookmark, level=0, closed=True
            )


def main() -> int:
    grouped = defaultdict(list)
    for row in read_jsonl(ROOT / "50-edited" / "blocks.jsonl"):
        grouped[int(row["source_page"])].append(row)
    audit = defaultdict(list)
    for row in read_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl"):
        audit[int(row["source_page"])].append(row)
    if sorted(grouped) != list(range(1, 163)):
        raise RuntimeError("Comparison edition does not cover source pages 1-162")

    md = [
        "# 入地眼全书",
        "",
        "## 原文对照版",
        "",
        "> 按原书 162 个物理页的顺序提供源图、校勘原文和现代释读。",
        "",
    ]
    for page in range(1, 163):
        source = "\n\n".join(
            (row.get("source_text") or "").strip()
            for row in grouped[page]
            if (row.get("source_text") or "").strip()
        )
        modern = "\n\n".join(
            (row.get("modern_text") or "").strip()
            for row in grouped[page]
            if (row.get("modern_text") or "").strip()
        )
        md.extend(
            [
                f"## 原书第 {page} 页",
                "",
                f"![原书第 {page} 页](../20-source/pages/P{page:06d}.jpg)",
                "",
                "### 校勘原文",
                "",
                source or "〔本页无可恢复文字〕",
                "",
                "### 现代释读",
                "",
                modern or "〔本页无须释读或内容不可恢复〕",
                "",
            ]
        )
        if audit[page]:
            md.extend(
                [
                    "### 校勘记录",
                    "",
                    f"- 本页有 {len(audit[page])} 条可追溯校勘或释读记录，详见随书审校账本。",
                    "",
                ]
            )
    (ROOT / "60-publication" / "source-comparison.md").write_text(
        "\n".join(md).rstrip() + "\n", encoding="utf-8"
    )

    pdfmetrics.registerFont(TTFont("YaHei", str(FONT), subfontIndex=0))
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "title", parent=base["Title"], fontName="YaHei", fontSize=25,
        leading=35, alignment=TA_CENTER, textColor=colors.HexColor("#183f36"),
    )
    h1 = ParagraphStyle(
        "h1", parent=base["Heading1"], fontName="YaHei", fontSize=15,
        leading=22, textColor=colors.HexColor("#183f36"), keepWithNext=True,
    )
    h2 = ParagraphStyle(
        "h2", parent=base["Heading2"], fontName="YaHei", fontSize=11,
        leading=17, textColor=colors.HexColor("#315d52"), keepWithNext=True,
    )
    body = ParagraphStyle(
        "body", parent=base["BodyText"], fontName="YaHei", fontSize=9.1,
        leading=15, firstLineIndent=18, alignment=TA_JUSTIFY,
        spaceAfter=3 * mm, allowWidows=0, allowOrphans=0,
    )
    note = ParagraphStyle(
        "note", parent=body, firstLineIndent=0, leftIndent=5 * mm,
        rightIndent=5 * mm, backColor=colors.HexColor("#f2f7f5"),
        borderPadding=5, keepWithNext=True,
    )
    caption = ParagraphStyle(
        "caption", parent=body, fontSize=8, leading=12,
        firstLineIndent=0, alignment=TA_CENTER,
        textColor=colors.HexColor("#66716e"),
    )

    def decorate(canvas, document):
        canvas.saveState()
        if document.page > 1:
            canvas.setFont("YaHei", 8)
            canvas.setFillColor(colors.HexColor("#6a7471"))
            canvas.drawString(19 * mm, 9 * mm, "入地眼全书·原文对照版")
            canvas.drawRightString(A4[0] - 19 * mm, 9 * mm, str(document.page))
        canvas.restoreState()

    doc = ComparisonDoc(
        str(OUT), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=17 * mm, bottomMargin=16 * mm,
        title="入地眼全书·原文对照版",
        author="宋·托长老；葛超云整理",
    )
    story = [
        Spacer(1, 42 * mm),
        Paragraph("入地眼全书", title),
        Spacer(1, 5 * mm),
        Paragraph("原文对照版", title),
        Spacer(1, 45 * mm),
        Paragraph("宋·托长老 原著", caption),
        Paragraph("葛超云 整理", caption),
        Spacer(1, 20 * mm),
        Paragraph("壮五福国学院 出品", caption),
    ]
    for page in range(1, 163):
        story.append(PageBreak())
        head = Paragraph(f"原书第 {page} 页", h1)
        head._bookmark = f"source-page-{page:03d}"
        story.append(head)
        image = Image(str(ROOT / "20-source" / "pages" / f"P{page:06d}.jpg"))
        scale = min((120 * mm) / image.imageWidth, (100 * mm) / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        story.extend(
            [image, Paragraph(f"原书第 {page} 页图像", caption), Paragraph("校勘原文", h2)]
        )
        source = "\n\n".join(
            (row.get("source_text") or "").strip()
            for row in grouped[page]
            if (row.get("source_text") or "").strip()
        ) or "〔本页无可恢复文字〕"
        modern = "\n\n".join(
            (row.get("modern_text") or "").strip()
            for row in grouped[page]
            if (row.get("modern_text") or "").strip()
        ) or "〔本页无须释读或内容不可恢复〕"
        story.extend(
            [
                Paragraph(escape(source).replace("\n", "<br/>"), body),
                Paragraph("现代释读", h2),
            ]
        )
        if audit[page]:
            story.append(
                Paragraph(
                    f"本页有 {len(audit[page])} 条可追溯校勘或释读记录，详见随书审校账本。",
                    note,
                )
            )
        # Put the audit notice before the modern text.  Combined with
        # keepWithNext this prevents a notice from becoming an otherwise
        # empty trailing page when a long modern paragraph splits.
        story.append(Paragraph(escape(modern).replace("\n", "<br/>"), body))
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    result = {
        "pdf": str(OUT),
        "pages": len(PdfReader(str(OUT)).pages),
        "bytes": OUT.stat().st_size,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
