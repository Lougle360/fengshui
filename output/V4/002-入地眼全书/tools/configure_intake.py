#!/usr/bin/env python3
"""Record Book 002 metadata and parent-scan provenance after workspace init."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SLICE_MANIFEST = Path(r"D:\ocr_work\v4-book002-ingest\slice-manifest.json")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    slice_info = read(SLICE_MANIFEST)
    staged = ROOT / "00-intake" / "source.pdf"
    pages = len(PdfReader(str(staged)).pages)
    if pages != 162:
        raise RuntimeError(f"Book-specific source must contain 162 pages, got {pages}")

    book = read(ROOT / "book.json")
    book.update({
        "title": "入地眼全书",
        "subtitle": "道光丙戌新镌·文星堂藏板",
        "edition_label": "现代白话版",
        "target_reader": "现代普通读者",
        "author": "宋·托长老",
        "original_compiler": "万树华",
        "editor": "葛超云",
        "producer": "壮五福国学院",
        "release_filename": "60-publication/入地眼全书·现代白话版.pdf",
        "source_pdf_pages": 162,
        "corpus_book_no": 2,
        "edition_scope": "ordinary_reader_modern_edition",
        "modernization_depth": "完整现代阅读重构",
        "source_parent_pdf_pages": 346,
        "source_parent_page_range": [5, 166],
        "page_accounting": {
            "physical_pages": 162,
            "included_pending_classification": 162,
            "excluded": 0,
            "blank_or_noncontent_pending_diagnosis": 0,
            "unreadable_pending_diagnosis": 0,
        },
    })
    write(ROOT / "book.json", book)

    manifest = read(ROOT / "00-intake" / "source-manifest.json")
    manifest.update({
        "source_pdf_pages": 162,
        "source_encrypted": False,
        "source_opened_successfully": True,
        "parent_source_path": slice_info["parent_source"],
        "parent_source_sha256": slice_info["parent_sha256"],
        "parent_source_bytes": slice_info["parent_bytes"],
        "parent_source_pages": slice_info["parent_pages"],
        "parent_page_range_inclusive": [5, 166],
        "parent_boundary_evidence": "output/V4/_boundary-audit-book002",
        "slice_manifest": str(SLICE_MANIFEST),
        "slice_sha256_verified": manifest["source_sha256"] == slice_info["extracted_sha256"],
        "page_accounting": book["page_accounting"],
    })
    if not manifest["slice_sha256_verified"]:
        raise RuntimeError("Workspace source hash differs from verified extracted slice")
    write(ROOT / "00-intake" / "source-manifest.json", manifest)

    state = read(ROOT / "run-state.json")
    state["updated_at"] = now
    state["current_stage"] = "diagnosis"
    state["stages"]["intake"] = {
        "status": "passed",
        "physical_pages": 162,
        "parent_page_range": [5, 166],
        "source_sha256": manifest["source_sha256"],
        "parent_source_sha256": manifest["parent_source_sha256"],
        "paid_cost_rmb": 0,
    }
    state["stages"]["diagnosis"] = {"status": "running"}
    write(ROOT / "run-state.json", state)

    event = {
        "schema_version": "1.0",
        "generated_at": now,
        "stage": "intake",
        "actor": "configure_intake.py",
        "action": "verified_parent_range_and_initialized_book_source",
        "status": "passed",
        "source_pages": 162,
        "parent_page_range": [5, 166],
        "rationale": "V2/V3 declaration and visual checks prove page 5 begins 入地眼全书 and page 167 begins 平砂玉尺经.",
    }
    with (ROOT / "90-audit" / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps({"book": "入地眼全书", "book_id": book["book_id"], "pages": pages, "intake": "passed"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
