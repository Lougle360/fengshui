#!/usr/bin/env python3
"""Render the verified Chaoyun pilot as a polished modern-reading PDF."""

from __future__ import annotations

import html
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "60-publication/modern-reading.pdf"


def esc(text: str) -> str:
    return html.escape(text).replace("\n", "<br/>")


def scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    image = Image(str(path))
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    return image


def main() -> int:
    pdfmetrics.registerFont(TTFont("YaHei", r"C:\Windows\Fonts\msyh.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("YaHeiBold", r"C:\Windows\Fonts\msyhbd.ttc", subfontIndex=0))
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleCN", parent=styles["Title"], fontName="YaHeiBold", fontSize=24, leading=34, textColor=colors.HexColor("#243B32"), alignment=TA_CENTER, spaceAfter=14)
    subtitle = ParagraphStyle("SubtitleCN", parent=styles["Normal"], fontName="YaHei", fontSize=12, leading=20, textColor=colors.HexColor("#66756E"), alignment=TA_CENTER)
    h1 = ParagraphStyle("H1CN", parent=styles["Heading1"], fontName="YaHeiBold", fontSize=18, leading=26, textColor=colors.HexColor("#264E3B"), spaceBefore=10, spaceAfter=10)
    h2 = ParagraphStyle("H2CN", parent=styles["Heading2"], fontName="YaHeiBold", fontSize=13, leading=20, textColor=colors.HexColor("#815B2A"), spaceBefore=8, spaceAfter=6)
    body = ParagraphStyle("BodyCN", parent=styles["BodyText"], fontName="YaHei", fontSize=10.5, leading=19, textColor=colors.HexColor("#202824"), alignment=TA_LEFT, firstLineIndent=21, spaceAfter=7)
    note = ParagraphStyle("NoteCN", parent=body, fontSize=9, leading=16, textColor=colors.HexColor("#53645C"), firstLineIndent=0)
    original = ParagraphStyle("OriginalCN", parent=body, fontSize=9.5, leading=18, textColor=colors.HexColor("#38443E"), firstLineIndent=0)

    modern = {
        row["block_id"]: row
        for row in (json.loads(line) for line in (ROOT / "40-modernized/blocks.jsonl").read_text(encoding="utf-8").splitlines() if line)
    }

    def original_box(text: str) -> Table:
        table = Table([[Paragraph(esc(text), original)]], colWidths=[156 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F0E7")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8B991")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    story = [Spacer(1, 22 * mm), Paragraph("超云古籍今读", title), Paragraph("《增释地理琢玉斧峦头歌括》现代阅读试跑样章", subtitle), Spacer(1, 18 * mm)]
    story.append(scaled_image(ROOT / "20-source/pages/P000040.png", 105 * mm, 105 * mm))
    story.extend([Spacer(1, 12 * mm), Paragraph("试跑范围：原 PDF 第 38—45 页", subtitle), Paragraph("纯扫描 · 竖排繁体 · 文言文 · 图文混排 · 无外部付费 API", subtitle), PageBreak()])

    story.extend([Paragraph("一、天罡形法（三例）", h1), scaled_image(ROOT / "20-source/pages/P000039.png", 118 * mm, 150 * mm), Spacer(1, 5 * mm), Paragraph("规范原文", h2), original_box(modern["P000039-B001"]["normalized_text"]), Spacer(1, 5 * mm), Paragraph("现代白话", h2), Paragraph(esc(modern["P000039-B001"]["modern_text"]), body), PageBreak()])

    story.extend([Paragraph("原书图版", h1), scaled_image(ROOT / "20-source/pages/P000040.png", 145 * mm, 190 * mm), Spacer(1, 5 * mm), Paragraph("编者注：图中文字存在识别风险，本次试跑完整保留原图，不强行补写。", note), PageBreak()])

    story.extend([Paragraph("二、为什么“砂”很重要", h1), Paragraph("第一段规范原文", h2), original_box(modern["P000044-B002"]["normalized_text"]), Spacer(1, 4 * mm), Paragraph("第一段现代白话", h2), Paragraph(esc(modern["P000044-B002"]["modern_text"]), body), Spacer(1, 6 * mm), Paragraph("第二段规范原文", h2), original_box(modern["P000045-B001"]["normalized_text"]), Spacer(1, 4 * mm), Paragraph("第二段现代白话", h2), Paragraph(esc(modern["P000045-B001"]["modern_text"]), body), PageBreak()])

    story.extend([Paragraph("原页对照", h1), Paragraph("原 PDF 第 44 页", h2), scaled_image(ROOT / "20-source/pages/P000044.png", 120 * mm, 160 * mm), PageBreak(), Paragraph("原 PDF 第 45 页", h2), scaled_image(ROOT / "20-source/pages/P000045.png", 120 * mm, 175 * mm), PageBreak()])

    story.extend([Paragraph("阅读提示与质量边界", h1), Paragraph("“龙”指山脉走势或地势脉络；“穴”指风水理论中选择安葬或营建的位置；“砂”指围绕龙、穴、水口的山体与地形。本文是在忠实转述古籍观点，不代表对相关理论作科学有效性判断。", body), Paragraph("本样章只覆盖原 PDF 第 38—45 页。原页含馆藏印章、低清晰度字形和图版文字；白话文只采用能够回查原页的文字块。高风险拟读与未识别区域已写入审计台账。全书尚未转换，也未评级。", body)])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("YaHei", 8)
        canvas.setFillColor(colors.HexColor("#758078"))
        canvas.drawString(24 * mm, 14 * mm, "超云古籍今读 · 可追溯试跑样章")
        canvas.drawRightString(186 * mm, 14 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=22 * mm, leftMargin=22 * mm, topMargin=20 * mm, bottomMargin=22 * mm, title="超云古籍今读试跑样章", author="超云古籍今读")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
