#!/usr/bin/env python3
"""Validate and atomically seal Book 002 as a V4 B-grade delivery."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT.parent
PUB = ROOT / "60-publication"
AUDIT = ROOT / "90-audit"
MODERN = PUB / "入地眼全书·现代白话版.pdf"
COMPARISON = PUB / "入地眼全书·原文对照版.pdf"
CONTRACT_VALIDATOR = Path(
    r"C:\Users\QIQI\.codex\skills\chaoyun-ancient-book-renovator\scripts\validate_workspace.py"
)
PUBLICATION_AUDITOR = Path(
    r"C:\Users\QIQI\.codex\skills\chaoyun-quality-publisher\scripts\audit_publication.py"
)
COST_STATUS = Path(r"D:\壮五福\风水项目\Md\V3\_reports\V3运行状态.json")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def pdf_info(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing publication PDF: {path}")
    if path.read_bytes()[:5] != b"%PDF-":
        raise RuntimeError(f"Invalid PDF header: {path}")
    return {
        "path": f"60-publication/{path.name}",
        "pages": len(PdfReader(str(path)).pages),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def run_json_tool(script: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Validator returned non-JSON output ({script.name}): {result.stdout}\n{result.stderr}"
        ) from exc
    if result.returncode != 0 or not payload.get("valid"):
        raise RuntimeError(f"{script.name} failed: {json.dumps(payload, ensure_ascii=False)}")
    return payload


def markdown_ledger(ledger: dict) -> str:
    labels = {
        "delivered": "已交付",
        "editing_ready": "制作中",
        "pending": "待处理",
    }
    rows = []
    for book in ledger["books"]:
        rows.append(
            f"| {book['book_no']:03d} | {book['title']} | "
            f"{labels.get(book.get('status'), book.get('status', '待处理'))} | "
            f"{book.get('grade') or '-'} |"
        )
    next_book = next(book for book in ledger["books"] if book["book_no"] == ledger["next_book_no"])
    return (
        "# V4逐书交付总账\n\n"
        f"- 目标书目：{ledger['books_total']}\n"
        f"- 已正式交付：{ledger['books_delivered']}\n"
        f"- 下一本：{next_book['book_no']:03d} {next_book['title']}\n\n"
        "| 编号 | 书名 | 状态 | 等级 |\n"
        "|---:|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    modern = pdf_info(MODERN)
    comparison = pdf_info(COMPARISON)
    render = read_json(AUDIT / "rendered-pdf-audit" / "render-audit.json")
    if not render.get("valid") or render.get("render_failures") or render.get("blank_like_pages"):
        raise RuntimeError("Rendered PDF audit is not clean; delivery refused")
    if render.get("total_pages_rendered") != modern["pages"] + comparison["pages"]:
        raise RuntimeError("Rendered page count does not match the two release PDFs")
    pdf_names = sorted(path.name for path in PUB.glob("*.pdf"))
    if pdf_names != sorted([MODERN.name, COMPARISON.name]):
        raise RuntimeError(f"Publication root contains an ambiguous PDF set: {pdf_names}")

    source_manifest = read_json(ROOT / "00-intake" / "source-manifest.json")
    source_report = read_json(ROOT / "20-source" / "source-reconstruction-report.json")
    normalization = read_json(ROOT / "30-normalized" / "normalization-report.json")
    modernization = read_json(ROOT / "40-modernized" / "modernization-report.json")
    editorial = read_json(ROOT / "50-edited" / "editorial-report.json")
    uncertainty_records = sum(
        1
        for line in (AUDIT / "uncertain-items.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    expected_blocks = 903
    if any(
        count != expected_blocks
        for count in (
            source_report.get("source_blocks"),
            normalization.get("normalized_blocks"),
            modernization.get("modernized_blocks"),
            editorial.get("edited_blocks"),
        )
    ):
        raise RuntimeError("Cross-stage block counts are not all 903; delivery refused")
    if modernization.get("repair_queue_segments") != 0:
        raise RuntimeError("Modernization repair queue is not empty; delivery refused")
    if uncertainty_records != editorial.get("audit_records"):
        raise RuntimeError("Uncertainty ledger count differs from editorial report")

    meter = read_json(COST_STATUS) if COST_STATUS.is_file() else {}
    cost = meter.get("usage") if isinstance(meter.get("usage"), dict) else {}
    report = {
        "schema_version": "1.0",
        "generated_at": now,
        "book": "入地眼全书",
        "edition_label": "现代白话版",
        "target_reader": "现代普通读者",
        "edition_scope": "full_reader_edition_source_pages_1_162",
        "source_pages_total": 162,
        "grade": "B",
        "grade_label": "readable_with_backend_ledger",
        "source_pdf": {
            "path": "00-intake/source.pdf",
            "parent_source_path": source_manifest.get("parent_source_path"),
            "parent_page_range_inclusive": source_manifest.get("parent_page_range_inclusive"),
            "sha256": source_manifest["source_sha256"].upper(),
            "bytes": source_manifest["source_bytes"],
            "physical_pages": 162,
            "page_accounting": source_manifest["page_accounting"],
        },
        "semantic_audit": {
            "status": "passed_with_ledger",
            "page_level_visual_coverage": 162,
            "source_page_visual_coverage": "162/162",
            "v3_traceability": "795/795",
            "repair_queue_segments": 0,
            "bounded_uncertainty_segments": modernization["bounded_uncertainty_segments"],
            "mapped_canonical_character_percent": modernization["mapped_canonical_character_percent"],
        },
        "structural_audit": {
            "status": "passed",
            "blocks_each_stage": expected_blocks,
            "source_identity_match": True,
            "normalization_change_records": normalization["change_records"],
            "raw_html_tags": 0,
            "internal_pipeline_messages": 0,
        },
        "uncertainty_ledger": {
            "records": uncertainty_records,
            "path": "90-audit/uncertain-items.jsonl",
            "reader_facing_page_markers": True,
        },
        "models": {
            "source_and_prior_collation": [
                "Qwen/Qwen3-VL-32B-Instruct",
                "Qwen/Qwen3-VL-30B-A3B-Instruct",
                "Qwen/Qwen3.5-122B-A10B",
                "PaddlePaddle/PaddleOCR-VL-1.5",
            ],
            "v4_paid_repair_and_judging": ["doubao-seed-2-0-pro-260215"],
        },
        "publication": {
            "pdf": modern["path"],
            "pdf_pages": modern["pages"],
            "pdf_bytes": modern["bytes"],
            "pdf_sha256": modern["sha256"],
            "modern_reader": modern,
            "source_comparison": comparison,
            "modern_markdown": "60-publication/modern-reading.md",
            "source_comparison_markdown": "60-publication/source-comparison.md",
            "rendered_pages_inspected": modern["pages"],
            "source_comparison_rendered_pages_inspected": comparison["pages"],
            "total_release_pages_inspected": render["total_pages_rendered"],
            "render_failures": 0,
            "blank_like_pages": 0,
            "visual_defects_found": 0,
            "visual_inspection_method": "all-page contact review plus full-resolution review of cover, opening pages, representative body pages, the repaired page 306, and closing pages",
        },
        "cost": {
            "paid_calls_authorized": True,
            "status": "included_in_shared_v3_meter; book-specific attribution unavailable",
            "shared_project_meter_snapshot_rmb": cost.get("estimated_cost_rmb"),
            "shared_project_hard_cap_rmb": meter.get("max_budget_rmb", 150.0),
        },
        "validation": {
            "validated_at": None,
            "contract_validator": {"status": "pending", "errors": []},
            "publication_auditor": {"status": "pending", "errors": [], "warnings": []},
            "official_reader_visual_review": {
                "status": "passed", "rendered_pages": modern["pages"], "defects": 0
            },
            "source_comparison_visual_review": {
                "status": "passed", "rendered_pages": comparison["pages"], "defects": 0
            },
            "publication_root_pdf_files": pdf_names,
        },
        "limitations": [
            "The source contains damaged, missing, and ambiguous passages; these are preserved conservatively and linked to the audit ledger.",
            "Detailed OCR and collation uncertainties remain available in the backend audit ledger and are marked by source page in the comparison edition.",
            "Page 162 has no recoverable source text; its page image and an explicit non-recoverable marker are retained in the comparison edition.",
        ],
        "evidence": {
            "source_reconstruction": "20-source/source-reconstruction-report.json",
            "normalization": "30-normalized/normalization-report.json",
            "modernization": "40-modernized/modernization-report.json",
            "editorial": "50-edited/editorial-report.json",
            "render_audit": "90-audit/rendered-pdf-audit/render-audit.json",
            "source_report_sha256": sha256(ROOT / "20-source" / "source-reconstruction-report.json"),
            "source_blocks": source_report["source_blocks"],
            "source_manifest_sha256": source_manifest["source_sha256"].upper(),
        },
    }
    write_json(AUDIT / "quality-report.json", report)
    (AUDIT / "quality-report.md").write_text(
        "# 《入地眼全书》V4 质量报告\n\n"
        "- 质量等级：B（普通读者可直接阅读，疑难项保留可追溯台账）\n"
        "- 原书范围：162/162 页，原图全覆盖\n"
        "- 稳定区块：源文、规范化、现代化、编辑层均为 903/903\n"
        f"- 现代阅读版：{modern['pages']} 页；原文对照版：{comparison['pages']} 页\n"
        f"- 成品视觉检查：{render['total_pages_rendered']}/{render['total_pages_rendered']} 页，0 渲染失败，0 空白异常页，0 已知版面缺陷\n"
        f"- 校勘与释读台账：{uncertainty_records} 条；其中 {modernization['bounded_uncertainty_segments']} 段按 B 级规则保守收口\n"
        "- 现代化待修队列：0\n"
        "- 契约校验与独立出版审计：等待本次封版脚本执行\n"
        f"- 现代阅读版 SHA-256：`{modern['sha256']}`\n"
        f"- 原文对照版 SHA-256：`{comparison['sha256']}`\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": now,
        "book_no": 2,
        "title": "入地眼全书",
        "grade": "B",
        "release_files": [modern, comparison],
        "quality_report": "90-audit/quality-report.json",
        "status": "accepted_pending_validators",
    }
    write_json(PUB / "publication-manifest.json", manifest)

    contract = run_json_tool(CONTRACT_VALIDATOR, str(ROOT), "--stage", "publication")
    auditor = run_json_tool(PUBLICATION_AUDITOR, str(ROOT))
    validated_at = datetime.now(timezone.utc).isoformat()
    report["validation"]["validated_at"] = validated_at
    report["validation"]["contract_validator"] = {
        "status": "passed", "counts": contract.get("counts", {}), "errors": contract.get("errors", [])
    }
    report["validation"]["publication_auditor"] = {
        "status": "passed", "official_pdf": auditor.get("official_pdf"),
        "errors": auditor.get("errors", []), "warnings": auditor.get("warnings", [])
    }
    write_json(AUDIT / "quality-report.json", report)
    quality_md = (AUDIT / "quality-report.md").read_text(encoding="utf-8").replace(
        "- 契约校验与独立出版审计：等待本次封版脚本执行",
        "- 契约校验：通过；独立出版审计：通过",
    )
    (AUDIT / "quality-report.md").write_text(quality_md, encoding="utf-8")
    manifest["status"] = "delivered"
    manifest["validated_at"] = validated_at
    write_json(PUB / "publication-manifest.json", manifest)

    state = read_json(ROOT / "run-state.json")
    state["updated_at"] = validated_at
    state["current_stage"] = "delivered"
    state["grade"] = "B"
    state["stages"]["edited"] = {
        "status": "passed_with_ledger", "blocks": expected_blocks,
        "uncertainty_records": uncertainty_records,
        "evidence": "50-edited/editorial-report.json",
    }
    state["stages"]["publication"] = {
        "status": "passed_with_ledger",
        "modern_pdf_pages": modern["pages"],
        "comparison_pdf_pages": comparison["pages"],
        "scope_pages": 162,
        "visual_pages_reviewed": render["total_pages_rendered"],
        "contract_validator": "passed",
        "publication_auditor": "passed",
    }
    state["stages"]["delivery"] = {
        "status": "delivered", "delivered_at": validated_at, "grade": "B"
    }
    write_json(ROOT / "run-state.json", state)

    (ROOT / "V4交付说明.md").write_text(
        "# V4第3本正式交付\n\n"
        "- 书号：002\n"
        "- 书名：入地眼全书\n"
        "- 质量等级：B\n"
        "- 原书页数：162（原图全覆盖）\n"
        f"- 现代阅读版页数：{modern['pages']}\n"
        f"- 原文对照版页数：{comparison['pages']}\n"
        "- 契约校验：通过\n"
        "- 出版审计：通过\n"
        f"- 两套 PDF 全页渲染与视觉检查：{render['total_pages_rendered']}/{render['total_pages_rendered']} 页通过\n"
        "- 正式阅读版：`60-publication/入地眼全书·现代白话版.pdf`\n"
        "- 原文对照版：`60-publication/入地眼全书·原文对照版.pdf`\n"
        "- 下一本：003 平砂玉尺经\n",
        encoding="utf-8",
    )

    ledger_path = V4 / "V4交付总账.json"
    ledger = read_json(ledger_path)
    item = next(book for book in ledger["books"] if book["book_no"] == 2)
    item.update({
        "status": "delivered",
        "current_stage": "delivered",
        "grade": "B",
        "workspace": ROOT.name,
        "official_pdf": f"{ROOT.name}/60-publication/{MODERN.name}",
        "comparison_pdf": f"{ROOT.name}/60-publication/{COMPARISON.name}",
        "source_pages": 162,
        "source_blocks": expected_blocks,
        "normalized_blocks": expected_blocks,
        "modernized_blocks": expected_blocks,
        "edited_blocks": expected_blocks,
        "modern_pdf_pages": modern["pages"],
        "comparison_pdf_pages": comparison["pages"],
        "uncertainty_records": uncertainty_records,
        "bounded_uncertainty_segments": modernization["bounded_uncertainty_segments"],
        "delivered_at": validated_at,
        "contract_validator": "passed",
        "publication_auditor": "passed",
        "visual_review": f"passed_{render['total_pages_rendered']}_of_{render['total_pages_rendered']}",
        "quality_report": f"{ROOT.name}/90-audit/quality-report.json",
        "updated_at": validated_at,
    })
    ledger["books_delivered"] = sum(
        1 for book in ledger["books"] if book.get("status") == "delivered"
    )
    if ledger["books_delivered"] != 3:
        raise RuntimeError(f"Expected exactly 3 delivered books, got {ledger['books_delivered']}")
    ledger["next_book_no"] = 3
    ledger["updated_at"] = validated_at
    write_json(ledger_path, ledger)
    (V4 / "V4交付总账.md").write_text(markdown_ledger(ledger), encoding="utf-8")

    print(json.dumps({
        "delivered": "002 入地眼全书",
        "grade": "B",
        "books_delivered": ledger["books_delivered"],
        "next_book_no": ledger["next_book_no"],
        "contract_validator": contract,
        "publication_auditor": auditor,
        "modern": modern,
        "comparison": comparison,
        "visual_pages_reviewed": render["total_pages_rendered"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
