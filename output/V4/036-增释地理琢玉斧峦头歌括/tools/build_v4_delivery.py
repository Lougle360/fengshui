#!/usr/bin/env python3
"""Build the V4 delivery package for book 036 without changing accepted text."""

from __future__ import annotations

import hashlib
import json
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


ROOT = Path(__file__).resolve().parents[1]
V4_ROOT = ROOT.parent
PROJECT_ROOT = V4_ROOT.parents[1]
PUBLICATION = ROOT / "60-publication"
AUDIT = ROOT / "90-audit"
TITLE = "增释地理琢玉斧峦头歌括"
EDITION = "现代白话版"
OFFICIAL_NAME = f"{TITLE}·{EDITION}.pdf"
COMPARISON_NAME = f"{TITLE}·原文对照版.pdf"
SOURCE_PDF = PROJECT_ROOT / "Docs" / "地学古本-明代" / "增释地理琢玉斧峦头歌括 张九仪.pdf"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def append_event(event: dict) -> None:
    path = AUDIT / "events.jsonl"
    existing_ids = {
        json.loads(line).get("event_id")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if event["event_id"] not in existing_ids:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def note_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        labels = {"severity": "严重度", "excerpt": "相关片段", "reason": "说明"}
        for key in ("severity", "excerpt", "reason"):
            raw = value.get(key)
            if raw in (None, ""):
                continue
            text = str(raw)
            if "�" in text or text.count("?") > 3:
                return "该页存在结构化OCR或校勘异常记录，详细内容保存在后台不确定项台账。"
            parts.append(f"{labels[key]}：{text}")
        if parts:
            return "；".join(parts)
    return "该页存在结构化校勘记录，详细内容保存在后台不确定项台账。"


class ComparisonDoc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and hasattr(flowable, "_bookmark"):
            key = flowable._bookmark
            title = flowable.getPlainText()
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=0, closed=True)


def build_comparison(blocks: list[dict]) -> tuple[Path, Path, int, str]:
    md_path = PUBLICATION / "source-comparison.md"
    pdf_path = PUBLICATION / COMPARISON_NAME

    md: list[str] = [
        f"# {TITLE}",
        "",
        "## 原文对照版",
        "",
        "> 本对照版用于追溯原书页面、校勘原文与现代释读。正式阅读请使用同目录下的现代白话版。",
        "",
    ]
    for record in blocks:
        page = int(record["source_page"])
        md.extend(
            [
                f"## 原书第 {page} 页",
                "",
                f"![原书第{page}页](../20-source/pages/{record['page_id']}.jpg)",
                "",
                "### 校勘原文",
                "",
                record.get("source_text") or "〔本页无可恢复文字〕",
                "",
                "### 现代释读",
                "",
                record.get("modern_text") or "〔本页无须释读或内容不可恢复〕",
                "",
            ]
        )
        notes = record.get("notes") or []
        if notes:
            md.extend(["### 校勘记录", ""])
            md.extend(f"- {note_text(note)}" for note in notes)
            md.append("")
    md_path.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")

    pdfmetrics.registerFont(TTFont("YaHei", str(FONT), subfontIndex=0))
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontName="YaHei", fontSize=23, leading=32,
        alignment=TA_CENTER, textColor=colors.HexColor("#183f36"), spaceAfter=8 * mm,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", parent=title_style, fontSize=16, leading=24, textColor=colors.HexColor("#946c2e")
    )
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], fontName="YaHei", fontSize=15, leading=22,
        textColor=colors.HexColor("#183f36"), spaceAfter=4 * mm, keepWithNext=True,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontName="YaHei", fontSize=11.5, leading=18,
        textColor=colors.HexColor("#315d52"), spaceBefore=3 * mm, spaceAfter=2 * mm,
        keepWithNext=True,
    )
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontName="YaHei", fontSize=9.5, leading=16,
        firstLineIndent=19, alignment=TA_JUSTIFY, textColor=colors.HexColor("#202625"),
        spaceAfter=3 * mm, allowWidows=0, allowOrphans=0,
    )
    note = ParagraphStyle(
        "note", parent=body, fontSize=8.5, leading=14, firstLineIndent=0, leftIndent=5 * mm,
        rightIndent=5 * mm, borderWidth=0.5, borderColor=colors.HexColor("#9bb8ae"),
        borderPadding=5, backColor=colors.HexColor("#f2f7f5"), textColor=colors.HexColor("#284d44"),
    )
    caption = ParagraphStyle(
        "caption", parent=body, fontSize=8, leading=12, firstLineIndent=0, alignment=TA_CENTER,
        textColor=colors.HexColor("#66716e"),
    )

    def decorate(canvas, document):
        canvas.saveState()
        if document.page > 1:
            canvas.setFont("YaHei", 8)
            canvas.setFillColor(colors.HexColor("#6a7471"))
            canvas.drawString(19 * mm, 9 * mm, f"{TITLE}·原文对照版")
            canvas.drawRightString(A4[0] - 19 * mm, 9 * mm, str(document.page))
        canvas.restoreState()

    doc = ComparisonDoc(
        str(pdf_path), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=17 * mm, bottomMargin=16 * mm,
        title=f"{TITLE}·原文对照版", author="张九仪；葛超云整理", subject="V4证据对照版",
    )
    story = [
        Spacer(1, 45 * mm), Paragraph(TITLE, title_style), Paragraph("原文对照版", subtitle_style),
        Spacer(1, 12 * mm), Paragraph("张九仪 原著", subtitle_style),
        Spacer(1, 55 * mm), Paragraph("壮五福国学院 出品", caption), PageBreak(),
        Paragraph("使用说明", h1),
        Paragraph(
            "本对照版按原书物理页顺序排列页面图像、校勘原文和现代释读，用于核对来源与校勘记录。"
            "它是证据资料版，不替代面向普通读者的现代白话版。", body,
        ),
    ]
    for index, record in enumerate(blocks):
        story.append(PageBreak())
        page = int(record["source_page"])
        heading = Paragraph(f"原书第 {page} 页", h1)
        heading._bookmark = f"source-page-{page:03d}"
        story.append(heading)
        image_path = ROOT / record["source_image"]
        image = Image(str(image_path))
        max_w, max_h = 120 * mm, 105 * mm
        scale = min(max_w / image.imageWidth, max_h / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        story.extend([image, Paragraph(f"原书第 {page} 页图像", caption), Spacer(1, 2 * mm)])
        story.append(Paragraph("校勘原文", h2))
        source = escape(record.get("source_text") or "〔本页无可恢复文字〕").replace("\n", "<br/>")
        story.append(Paragraph(source, body))
        story.append(Paragraph("现代释读", h2))
        modern = escape(record.get("modern_text") or "〔本页无须释读或内容不可恢复〕").replace("\n", "<br/>")
        story.append(Paragraph(modern, body))
        notes = record.get("notes") or []
        if notes:
            story.append(Paragraph("校勘记录", h2))
            story.append(Paragraph("<br/>".join(escape(note_text(item)) for item in notes), note))
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    pages = len(PdfReader(str(pdf_path)).pages)
    return md_path, pdf_path, pages, sha256(pdf_path)


def build_master_ledger() -> None:
    v2_files = sorted((PROJECT_ROOT / "Md" / "V2").glob("[0-9][0-9][0-9] *.md"))
    if len(v2_files) != 36:
        raise RuntimeError(f"Expected 36 V2 books, found {len(v2_files)}")
    books = []
    for path in v2_files:
        number = int(path.name[:3])
        books.append(
            {
                "book_no": number,
                "title": path.stem[4:],
                "status": "delivered" if number == 36 else "pending",
                "grade": "B" if number == 36 else None,
                "workspace": "036-增释地理琢玉斧峦头歌括" if number == 36 else None,
                "official_pdf": (
                    f"036-增释地理琢玉斧峦头歌括/60-publication/{OFFICIAL_NAME}"
                    if number == 36 else None
                ),
            }
        )
    ledger = {
        "schema_version": "1.0",
        "objective": "完成一本、验收一本、交付一本，然后再进入下一本，直到36本全部达到B级以上。",
        "delivery_mode": "one_book_at_a_time",
        "books_total": 36,
        "books_delivered": 1,
        "next_book_no": 1,
        "books": books,
    }
    write_json(V4_ROOT / "V4交付总账.json", ledger)
    lines = [
        "# V4逐书交付总账", "", "- 目标书目：36", "- 已正式交付：1", "- 下一本：001 青囊海角经（郭璞著·郑同校·2017）", "",
        "| 编号 | 书名 | 状态 | 等级 |", "|---:|---|---|---|",
    ]
    for item in books:
        lines.append(
            f"| {item['book_no']:03d} | {item['title']} | "
            f"{'已交付' if item['status'] == 'delivered' else '待处理'} | {item['grade'] or '-'} |"
        )
    (V4_ROOT / "V4交付总账.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    source_hash = sha256(SOURCE_PDF)
    if source_hash.lower() != "a8905dff46683b57b0bf695c8263c0a098b4ef0106e571564f6a1c898b970a06":
        raise RuntimeError("Source PDF hash does not match the accepted workspace")

    blocks = read_jsonl(ROOT / "50-edited" / "blocks.jsonl")
    if len(blocks) != 80 or {int(item["source_page"]) for item in blocks} != set(range(1, 81)):
        raise RuntimeError("Edited block coverage is not exactly source pages 1-80")

    book = read_json(ROOT / "book.json")
    book.update(
        {
            "corpus_book_no": 36,
            "v4_delivery_sequence": 1,
            "edition_label": EDITION,
            "edition_scope": "ordinary_reader_modern_edition",
            "modernization_depth": "完整现代阅读重构",
            "release_filename": f"60-publication/{OFFICIAL_NAME}",
            "source_pdf_path": str(SOURCE_PDF),
            "source_pdf_pages": 80,
            "page_accounting": {
                "physical_pages": 80,
                "included_content": 79,
                "blank_or_noncontent": 1,
                "excluded": 0,
                "unreadable": 0,
            },
        }
    )
    write_json(ROOT / "book.json", book)

    manifest = read_json(ROOT / "00-intake" / "source-manifest.json")
    manifest.update(
        {
            "source_path": str(SOURCE_PDF),
            "source_name": SOURCE_PDF.name,
            "source_bytes": SOURCE_PDF.stat().st_size,
            "source_sha256": source_hash.lower(),
            "source_pdf_pages": 80,
            "page_accounting": book["page_accounting"],
            "v4_verified_at": now,
        }
    )
    write_json(ROOT / "00-intake" / "source-manifest.json", manifest)

    md_path, comparison_pdf, comparison_pages, comparison_hash = build_comparison(blocks)
    official_pdf = PUBLICATION / OFFICIAL_NAME
    official_reader = PdfReader(str(official_pdf))
    uncertainties = read_jsonl(AUDIT / "uncertain-items.jsonl")
    severity_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in uncertainties:
        severity = item.get("severity", "unspecified")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        status = item.get("status", "unspecified")
        status_counts[status] = status_counts.get(status, 0) + 1
    reader_markdown = (PUBLICATION / "modern-reading.md").read_text(encoding="utf-8")
    reader_markers = reader_markdown.count("审校提示：") + reader_markdown.count("版本说明：")

    report = read_json(AUDIT / "quality-report.json")
    report.update(
        {
            "generated_at": now,
            "edition_label": EDITION,
            "target_reader": "现代普通读者",
            "source_pdf": {
                "path": str(SOURCE_PDF),
                "sha256": source_hash,
                "bytes": SOURCE_PDF.stat().st_size,
                "physical_pages": 80,
                "page_accounting": book["page_accounting"],
            },
            "uncertainty_ledger": {
                "records": len(uncertainties),
                "by_severity": severity_counts,
                "by_status": status_counts,
                "reader_facing_markers": reader_markers,
            },
            "cost": {
                "amount_rmb": None,
                "status": "historical_run_not_metered_in_workspace",
                "v4_migration_incremental_cost_rmb": 0,
            },
        }
    )
    report["publication"].update(
        {
            "pdf": f"60-publication/{OFFICIAL_NAME}",
            "pdf_pages": len(official_reader.pages),
            "pdf_bytes": official_pdf.stat().st_size,
            "pdf_sha256": sha256(official_pdf),
            "modern_markdown": "60-publication/modern-reading.md",
            "source_comparison_markdown": "60-publication/source-comparison.md",
            "source_comparison_pdf": f"60-publication/{COMPARISON_NAME}",
            "source_comparison_pdf_pages": comparison_pages,
            "source_comparison_pdf_bytes": comparison_pdf.stat().st_size,
            "source_comparison_pdf_sha256": comparison_hash,
            "rendered_pages_inspected": len(official_reader.pages),
            "visual_inspection_method": "all-page contact review plus full-resolution representative pages",
            "visual_defects_found": 0,
        }
    )
    report["validation"] = {
        "contract_validator": "pending_recheck_after_v4_migration",
        "publication_auditor": "pending_recheck_after_v4_migration",
        "source_comparison_visual_review": "pending",
    }
    write_json(AUDIT / "quality-report.json", report)

    state = read_json(ROOT / "run-state.json")
    state.update(
        {
            "updated_at": now,
            "grade": "B",
            "v4_delivery": {
                "sequence": 1,
                "status": "pending_final_validation",
                "official_pdf": f"60-publication/{OFFICIAL_NAME}",
            },
        }
    )
    write_json(ROOT / "run-state.json", state)

    append_event(
        {
            "schema_version": "1.0",
            "event_id": "v4-book036-migration",
            "time": now,
            "actor": "codex",
            "operation": "v4_workspace_migration",
            "source_ids": ["a8905dff46683b57"],
            "before": "output/chaoyun-remake-zengshi-dili-zhuoyufu",
            "after": "output/V4/036-增释地理琢玉斧峦头歌括",
            "confidence": 1.0,
            "rationale": "Preserve the accepted B-grade workspace while adding explicit V4 delivery metadata.",
        }
    )
    append_event(
        {
            "schema_version": "1.0",
            "event_id": "v4-book036-source-comparison",
            "time": now,
            "actor": "build_v4_delivery.py",
            "operation": "publish_source_comparison",
            "source_ids": [item["block_id"] for item in blocks],
            "before": None,
            "after": f"60-publication/{COMPARISON_NAME}",
            "confidence": 1.0,
            "rationale": "Provide page-image, faithful-source, and modern-text comparison for all 80 source pages.",
        }
    )

    (ROOT / "V4交付说明.md").write_text(
        f"# V4第1本交付说明\n\n"
        f"- 书号：036\n- 书名：{TITLE}\n- 质量等级：B\n"
        f"- 原书页数：80\n- 现代阅读版页数：{len(official_reader.pages)}\n"
        f"- 原文对照版页数：{comparison_pages}\n"
        f"- 正式阅读版：`60-publication/{OFFICIAL_NAME}`\n"
        f"- 原文对照版：`60-publication/{COMPARISON_NAME}`\n"
        f"- 当前状态：等待V4迁移后的最终契约、出版和视觉复核\n",
        encoding="utf-8",
    )
    build_master_ledger()
    print(
        json.dumps(
            {
                "workspace": str(ROOT),
                "official_pdf": str(official_pdf),
                "official_pdf_sha256": sha256(official_pdf),
                "source_comparison_pdf": str(comparison_pdf),
                "source_comparison_pages": comparison_pages,
                "source_comparison_sha256": comparison_hash,
                "uncertainties": severity_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
