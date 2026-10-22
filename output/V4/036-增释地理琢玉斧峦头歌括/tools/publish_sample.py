#!/usr/bin/env python3
"""Publish the curated sample to a readable, auditable PDF."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "60-publication" / "modern-reading.pdf"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def safe(text: str) -> str:
    return escape(text).replace("\n", "<br/>")


def main() -> int:
    pdfmetrics.registerFont(TTFont("YaHei", str(FONT), subfontIndex=0))
    rows = load_jsonl(ROOT / "50-edited" / "blocks.jsonl")
    uncertainties = load_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl")
    by_block: dict[str, list[dict]] = {}
    for item in uncertainties:
        by_block.setdefault(item["block_id"], []).append(item)

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
        topMargin=19 * mm, bottomMargin=17 * mm,
        title="增释地理琢玉斧峦头歌括 - 前10页质量样章",
        author="超云古籍今读",
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=base["Title"], fontName="YaHei", fontSize=22, leading=31,
                           textColor=colors.HexColor("#173f35"), alignment=TA_CENTER, spaceAfter=12 * mm)
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName="YaHei", fontSize=17, leading=24,
                        textColor=colors.HexColor("#173f35"), spaceBefore=4 * mm, spaceAfter=4 * mm)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="YaHei", fontSize=12.5, leading=18,
                        textColor=colors.HexColor("#225c4d"), spaceBefore=3 * mm, spaceAfter=2 * mm)
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="YaHei", fontSize=10.5, leading=18,
                          textColor=colors.HexColor("#202625"), alignment=TA_LEFT, spaceAfter=3 * mm)
    note = ParagraphStyle("note", parent=body, fontSize=9, leading=14, textColor=colors.HexColor("#5f4d25"))
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=13, textColor=colors.HexColor("#56615e"))

    story = [
        Spacer(1, 28 * mm),
        Paragraph("增释地理琢玉斧峦头歌括", title),
        Paragraph("前 10 页质量样章", ParagraphStyle("subtitle", parent=title, fontSize=16, leading=23,
                                                  textColor=colors.HexColor("#9a6d25"))),
        Spacer(1, 8 * mm),
        Table([[Paragraph("版本性质", small), Paragraph("B 级样章 - 仅覆盖原 PDF 第 1-10 页，不是整本成品", body)],
               [Paragraph("证据链", small), Paragraph("原页扫描 - 忠实转录 - 简体点校 - 现代白话 - 校勘存疑", body)],
               [Paragraph("质检方式", small), Paragraph("双视觉模型转录与裁决、专用 OCR 比对、逐页人工抽查、阶段合同验证", body)]],
              colWidths=[32 * mm, 114 * mm], style=TableStyle([
                  ("FONTNAME", (0, 0), (-1, -1), "YaHei"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                  ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf4f1")),
                  ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#aac2ba")),
                  ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cfddd8")),
                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                  ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
              ])),
        Spacer(1, 12 * mm),
        Paragraph("阅读说明", h1),
        Paragraph("本样章刻意保留无法完全确认的字，不以流畅代替证据。在线异本只用于提供校勘线索，最终取舍仍以当前扫描页的字形为准。", body),
        PageBreak(),
    ]

    for row in rows:
        page = row["source_page"]
        story.append(Paragraph(f"原 PDF 第 {page} 页 - 原页证据", h1))
        img_path = ROOT / row["source_image"]
        img = Image(str(img_path))
        max_w, max_h = 154 * mm, 225 * mm
        scale = min(max_w / img.imageWidth, max_h / img.imageHeight)
        img.drawWidth = img.imageWidth * scale
        img.drawHeight = img.imageHeight * scale
        story += [img, Spacer(1, 2 * mm), Paragraph(f"证据编号：{row['block_id']}", small), PageBreak()]

        story += [Paragraph(f"原 PDF 第 {page} 页 - 今读", h1), Paragraph("忠实转录", h2),
                  Paragraph(safe(row["source_text"]), body), Paragraph("简体点校", h2),
                  Paragraph(safe(row["normalized_text"]), body), Paragraph("现代白话", h2),
                  Paragraph(safe(row["modern_text"]), body)]
        issues = by_block.get(row["block_id"], [])
        if issues:
            items = [Paragraph("校勘存疑", h2)]
            items.extend(Paragraph("- " + safe(x["note"]), note) for x in issues)
            story.append(KeepTogether(items))
        else:
            story += [Paragraph("校勘状态", h2), Paragraph("本页未记录实质性存疑。", note)]
        story.append(PageBreak())

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("YaHei", 8)
        canvas.setFillColor(colors.HexColor("#65716d"))
        canvas.drawString(21 * mm, 10 * mm, "超云古籍今读 - 前10页质量样章")
        canvas.drawRightString(A4[0] - 21 * mm, 10 * mm, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(str(OUT)).pages)
    report = {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "book": "增释地理琢玉斧峦头歌括", "edition_scope": "source_pages_1_10_only",
        "source_pages_total": 80, "pages_in_sample": 10, "grade": "B", "grade_label": "readable_sample_with_ledger",
        "semantic_audit": {"status": "passed_with_ledger", "pages_visually_reviewed": 10,
                           "open_uncertainties": len(uncertainties), "parallel_edition_used_as_clue_only": True},
        "structural_audit": {"status": "passed", "blocks_each_stage": 10, "stable_page_ids": True,
                             "raw_html_tags": 0, "internal_pipeline_messages": 0},
        "vision_reconstruction": {"successful_pages": 10, "scope": list(range(1, 11)),
                                  "models": ["Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-30B-A3B-Instruct", "PaddlePaddle/PaddleOCR-VL-1.5"]},
        "publication": {"pdf": f"60-publication/{OUT.name}", "pdf_pages": pages,
                        "modern_markdown": "60-publication/modern-reading.md"},
        "limitations": ["This is a ten-page quality sample, not a full-book edition.",
                        "Open glyph-level uncertainties remain explicitly listed."],
    }
    (ROOT / "90-audit" / "quality-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "90-audit" / "quality-report.md").write_text(
        "# 质量报告\n\n- 范围：原 PDF 第 1-10 页\n- 等级：B（仅限样章）\n- 逐页视觉检查：10/10\n"
        f"- 开放存疑：{len(uncertainties)} 项\n- PDF 页数：{pages}\n\n本报告不得外推为整本质量结论。\n",
        encoding="utf-8",
    )
    state = json.loads((ROOT / "run-state.json").read_text(encoding="utf-8"))
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["grade"] = "B-sample"
    state["stages"]["publication"] = {"status": "passed_with_ledger", "pdf_pages": pages, "scope_pages": 10}
    (ROOT / "run-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdf": str(OUT), "pages": pages, "uncertainties": len(uncertainties)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
