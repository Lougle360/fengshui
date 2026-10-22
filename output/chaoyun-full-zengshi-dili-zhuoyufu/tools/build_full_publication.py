#!/usr/bin/env python3
"""Build the complete Chaoyun reading package from audited V2/V3 records."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PROJECT = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = PROJECT / "Md/V3/_work/segments/book036.jsonl"
RESULTS = PROJECT / "Md/V3/_work/results/book036.jsonl"
ASSET_ROOT = PROJECT / "Md/V3"
PUBLICATION = ROOT / "60-publication"
AUDIT = ROOT / "90-audit"
PDF = PUBLICATION / "modern-reading.pdf"
SOURCE_PDF_SHA256 = "a8905dff46683b57b0bf695c8263c0a098b4ef0106e571564f6a1c898b970a06"
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def esc(text: str) -> str:
    return html.escape(text).replace("\n", "<br/>")


def strip_heading(text: str) -> str:
    return re.sub(r"^#{1,6}\s*", "", text.strip()).strip()


def scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    image = Image(str(path))
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight, 1.0)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    return image


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    PUBLICATION.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    segments = load_jsonl(SEGMENTS)
    results = {row["id"]: row for row in load_jsonl(RESULTS) if row.get("status") == "judged"}
    required = [row for row in segments if row.get("translatable")]
    missing = [row["id"] for row in required if row["id"] not in results]
    if missing:
        raise RuntimeError(f"missing {len(missing)} modernized segments")

    output_assets = PUBLICATION / "assets"
    image_refs: list[str] = []
    for segment in segments:
        for ref in IMAGE_RE.findall(segment.get("source", "")):
            ref = ref.replace("\\", "/")
            source = ASSET_ROOT / ref
            if not source.exists():
                raise FileNotFoundError(source)
            target_ref = ref.removeprefix("assets/")
            target = output_assets / target_ref
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.stat().st_size != source.stat().st_size:
                shutil.copy2(source, target)
            image_refs.append(target_ref)

    verdicts = Counter(row.get("judge_verdict", "missing") for row in results.values())
    uncertain_rows = [
        row for row in results.values()
        if row.get("judge_verdict") != "accept" or row.get("uncertainty")
    ]

    reading: list[str] = [
        "# 增释地理琢玉斧峦头歌括",
        "",
        "> **超云古籍今读 - 整本辅助读本（C级）**",
        ">",
        "> 本版覆盖原 PDF 全部 80 页。正文由付费模型完成白话释读与独立核义；原始扫描图完整保留。由于底层 OCR 仍有较多古字和断句风险，本版适合辅助阅读，不作为无校勘责任的权威点校本。",
        "",
        "> **阅读说明：** 文中风水判断属于古籍原有观点，不代表现代科学结论。遇到存疑处请展开对应原文并核对附近原页图。",
        "",
    ]
    comparison: list[str] = list(reading)

    for segment in segments:
        source = segment.get("source", "").strip()
        kind = segment.get("kind")
        sid = segment["id"]
        if kind == "title":
            continue
        refs = IMAGE_RE.findall(source)
        if refs:
            for ref in refs:
                target_ref = ref.replace("\\", "/").removeprefix("assets/")
                line = f"![](assets/{target_ref})"
                reading.extend([line, ""])
                comparison.extend([line, ""])
            continue
        if segment.get("translatable"):
            result = results[sid]
            modern = result.get("modern_text", "").strip()
            if not modern:
                modern = "〔本段未能可靠释读，请参看原文。〕"
            reading.extend([f"<!-- CHAoyun_SOURCE_ID:{sid} -->", modern, ""])
            if result.get("uncertainty") or result.get("judge_verdict") == "uncertain":
                notes = result.get("uncertainty") or result.get("issues") or ["本段释读存疑"]
                reading.extend(["> **释读存疑：** " + "；".join(str(x) for x in notes), ""])
            comparison.extend([
                f"<!-- CHAoyun_SOURCE_ID:{sid} -->",
                modern,
                "",
                "<details>",
                "<summary>查看对应原文</summary>",
                "",
                source,
                "",
                "</details>",
                "",
            ])
            continue
        if kind in {"source_note", "image_caption"} and source:
            reading.extend([source, ""])
            comparison.extend([source, ""])
        elif kind == "other" and source:
            comparison.extend([
                f"<!-- OCR_RESIDUAL:{sid} -->",
                "<details>",
                "<summary>OCR 残片（仅供证据核对）</summary>",
                "",
                source,
                "",
                "</details>",
                "",
            ])

    modern_md = PUBLICATION / "modern-reading.md"
    comparison_md = PUBLICATION / "source-comparison.md"
    modern_md.write_text("\n".join(reading).rstrip() + "\n", encoding="utf-8")
    comparison_md.write_text("\n".join(comparison).rstrip() + "\n", encoding="utf-8")

    with (AUDIT / "uncertain-items.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in sorted(uncertain_rows, key=lambda item: item["id"]):
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    pdfmetrics.registerFont(TTFont("YaHei", r"C:\Windows\Fonts\msyh.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("YaHeiBold", r"C:\Windows\Fonts\msyhbd.ttc", subfontIndex=0))
    base = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCN", parent=base["Title"], fontName="YaHeiBold", fontSize=23, leading=33, textColor=colors.HexColor("#243B32"), alignment=TA_CENTER, spaceAfter=14)
    subtitle = ParagraphStyle("SubtitleCN", parent=base["Normal"], fontName="YaHei", fontSize=11, leading=19, textColor=colors.HexColor("#66756E"), alignment=TA_CENTER)
    h1 = ParagraphStyle("H1CN", parent=base["Heading1"], fontName="YaHeiBold", fontSize=16, leading=24, textColor=colors.HexColor("#264E3B"), spaceBefore=11, spaceAfter=8)
    body = ParagraphStyle("BodyCN", parent=base["BodyText"], fontName="YaHei", fontSize=10, leading=18, textColor=colors.HexColor("#202824"), alignment=TA_LEFT, firstLineIndent=20, spaceAfter=7, allowWidows=0, allowOrphans=0)
    note = ParagraphStyle("NoteCN", parent=body, fontSize=8.5, leading=15, textColor=colors.HexColor("#6A5940"), firstLineIndent=0)
    label = ParagraphStyle("LabelCN", parent=body, fontSize=7.5, leading=12, textColor=colors.HexColor("#7A827E"), firstLineIndent=0)

    def note_box(text: str) -> Table:
        table = Table([[Paragraph(esc(text), note)]], colWidths=[158 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F1E5")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9B989")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    story = [
        Spacer(1, 22 * mm),
        Paragraph("超云古籍今读", title_style),
        Paragraph("《增释地理琢玉斧峦头歌括》", title_style),
        Paragraph("整本现代白话辅助读本", subtitle),
        Spacer(1, 15 * mm),
        note_box("覆盖原 PDF 80 页；373 个正文区块经付费模型释读与独立核义。质量等级 C：可用于辅助阅读，疑难古字与残缺句仍须回看原页。"),
        Spacer(1, 12 * mm),
        Paragraph("古籍中的风水判断属于历史文本观点，不代表现代科学结论。", subtitle),
        PageBreak(),
        Paragraph("阅读说明", h1),
        Paragraph("本书将现代白话与原始扫描图编排在同一份 PDF 中。文字段落以现代阅读为主；扫描图是最终证据。遇到“释读存疑”提示，请以原页图为准。", body),
        Paragraph(f"模型裁决：直接通过 {verdicts.get('accept', 0)} 段，专业修订 {verdicts.get('revise', 0)} 段，明确未决 {verdicts.get('uncertain', 0)} 段。另有 {len(uncertain_rows)} 段带不确定性或非直接通过记录。", body),
        PageBreak(),
    ]

    page_number = 0
    for segment in segments:
        kind = segment.get("kind")
        source = segment.get("source", "").strip()
        sid = segment["id"]
        refs = IMAGE_RE.findall(source)
        if refs:
            for ref in refs:
                target_ref = ref.replace("\\", "/").removeprefix("assets/")
                image_path = output_assets / target_ref
                story.append(PageBreak())
                story.append(Paragraph("原页或图版", h1))
                story.append(scaled_image(image_path, 158 * mm, 220 * mm))
                story.append(Spacer(1, 3 * mm))
                story.append(Paragraph(esc(target_ref), label))
            continue
        if not segment.get("translatable"):
            continue
        row = results[sid]
        text = row.get("modern_text", "").strip() or "〔本段未能可靠释读，请参看原页。〕"
        uncertainty = row.get("uncertainty") or (
            row.get("issues") if row.get("judge_verdict") == "uncertain" else []
        )
        if kind == "heading":
            story.append(Paragraph(esc(strip_heading(text)), h1))
        elif uncertainty:
            notes = uncertainty or ["本段释读存疑"]
            story.append(KeepTogether([
                Paragraph(esc(text), body),
                note_box("释读存疑：" + "；".join(str(x) for x in notes)),
                Spacer(1, 2 * mm),
            ]))
        else:
            story.append(Paragraph(esc(text), body))
        if kind == "heading" and uncertainty:
            notes = row.get("uncertainty") or row.get("issues") or ["本段释读存疑"]
            story.append(note_box("释读存疑：" + "；".join(str(x) for x in notes)))
            story.append(Spacer(1, 2 * mm))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("YaHei", 8)
        canvas.setFillColor(colors.HexColor("#758078"))
        canvas.drawString(22 * mm, 13 * mm, "超云古籍今读 · 整本辅助读本")
        canvas.drawRightString(188 * mm, 13 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(PDF),
        pagesize=A4,
        rightMargin=21 * mm,
        leftMargin=21 * mm,
        topMargin=18 * mm,
        bottomMargin=21 * mm,
        title="超云古籍今读 - 增释地理琢玉斧峦头歌括",
        author="超云古籍今读",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    vision_path = ROOT / "40-modernized/pages-evidence.jsonl"
    vision_rows = load_jsonl(vision_path) if vision_path.exists() else []
    vision_latest = {int(row["source_page"]): row for row in vision_rows}
    vision_success = [row for row in vision_latest.values() if row.get("status") == "success"]
    report = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "book": "增释地理琢玉斧峦头歌括（张九仪）",
        "source_pdf_sha256": SOURCE_PDF_SHA256,
        "grade": "C",
        "grade_label": "assisted_draft",
        "pages": 80,
        "segments_total": len(segments),
        "segments_translatable": len(required),
        "segments_judged": len(results),
        "verdicts": dict(verdicts),
        "uncertain_or_nonaccept_records": len(uncertain_rows),
        "ocr_residual_segments_preserved_in_comparison": sum(1 for s in segments if s.get("kind") == "other"),
        "source_images_packaged": len(set(image_refs)),
        "paid_api_used": True,
        "models": [
            "doubao-seed-2-0-mini-260428",
            "doubao-seed-2-0-pro-260215",
            "Qwen/Qwen3-VL-32B-Instruct",
        ],
        "vision_reconstruction": {
            "successful_pages": len(vision_success),
            "scope": sorted(row["source_page"] for row in vision_success),
            "status": "partial_due_to_provider_timeouts",
        },
        "publication": {
            "modern_markdown": str(modern_md.relative_to(ROOT)).replace("\\", "/"),
            "source_comparison_markdown": str(comparison_md.relative_to(ROOT)).replace("\\", "/"),
            "pdf": str(PDF.relative_to(ROOT)).replace("\\", "/"),
            "pdf_bytes": PDF.stat().st_size,
            "pdf_sha256": sha256_file(PDF),
        },
        "limitations": [
            "The full book is readable but the source OCR still contains material errors and fragmented lines.",
            "The direct full-page visual reconstruction completed only ten pages before repeated provider timeouts.",
            "This edition is an assisted reading draft, not an authoritative critical edition.",
        ],
    }
    (AUDIT / "quality-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md = [
        "# 超云古籍今读 - 整本质量报告",
        "",
        "- 等级：C（辅助读本）",
        f"- 原书页数：{report['pages']}",
        f"- 可释读区块：{report['segments_translatable']}，已完成：{report['segments_judged']}",
        f"- 裁决：通过 {verdicts.get('accept', 0)}，修订 {verdicts.get('revise', 0)}，未决 {verdicts.get('uncertain', 0)}",
        f"- 视觉重建成功页：{len(vision_success)}/80",
        f"- PDF：{report['publication']['pdf_bytes']} bytes",
        f"- PDF SHA-256：`{report['publication']['pdf_sha256']}`",
        "",
        "本版已完整覆盖 80 页并保留原页图，但底层 OCR 风险尚未全部消除，因此不能评为出版级。",
    ]
    (AUDIT / "quality-report.md").write_text("\n".join(report_md) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
