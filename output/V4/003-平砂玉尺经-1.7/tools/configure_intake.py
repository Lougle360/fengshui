#!/usr/bin/env python3
"""Record Book 003 metadata and verified omnibus-scan provenance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT.parent
SLICE_MANIFEST = Path(r"D:\ocr_work\v4-book003-ingest\slice-manifest.json")


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    slice_info = read(SLICE_MANIFEST)
    staged = ROOT / "00-intake" / "source.pdf"
    pages = len(PdfReader(str(staged)).pages)
    if pages != 86:
        raise RuntimeError(f"Book-specific source must contain 86 pages, got {pages}")
    staged_hash = sha256(staged)
    if staged_hash != slice_info["extracted_sha256"]:
        raise RuntimeError("Workspace source hash differs from verified extracted slice")

    book = read(ROOT / "book.json")
    book.update({
        "title": "平砂玉尺经",
        "subtitle": "刘文成公汇解·新刻石函本",
        "edition_label": "现代白话版",
        "target_reader": "现代普通读者",
        "author": "元·刘秉忠述；明·刘基解；赖从谦发挥",
        "editor": "葛超云",
        "producer": "壮五福国学院",
        "release_filename": "60-publication/平砂玉尺经·现代白话版.pdf",
        "source_pdf_pages": 86,
        "corpus_book_no": 3,
        "edition_scope": "ordinary_reader_modern_edition",
        "modernization_depth": "完整现代阅读重构",
        "source_parent_pdf_pages": 346,
        "source_parent_page_range": [167, 252],
        "page_accounting": {
            "physical_pages": 86,
            "included_pending_classification": 86,
            "excluded": 0,
            "blank_or_noncontent_pending_diagnosis": 0,
            "unreadable_pending_diagnosis": 0,
        },
    })
    write(ROOT / "book.json", book)

    manifest = read(ROOT / "00-intake" / "source-manifest.json")
    manifest.update({
        "source_path": str(staged),
        "source_name": staged.name,
        "source_bytes": staged.stat().st_size,
        "source_sha256": staged_hash,
        "source_copied": True,
        "staged_source": str(staged),
        "source_pdf_pages": 86,
        "source_encrypted": False,
        "source_opened_successfully": True,
        "parent_source_path": slice_info["parent_source"],
        "parent_source_sha256": slice_info["parent_sha256"],
        "parent_source_bytes": slice_info["parent_bytes"],
        "parent_source_pages": slice_info["parent_pages"],
        "parent_page_range_inclusive": [167, 252],
        "parent_boundary_evidence": "output/V4/_boundary-audit-book003",
        "slice_manifest": str(SLICE_MANIFEST),
        "slice_sha256_verified": True,
        "page_accounting": book["page_accounting"],
        "verified_at": now,
    })
    write(ROOT / "00-intake" / "source-manifest.json", manifest)

    state = read(ROOT / "run-state.json")
    state["updated_at"] = now
    state["current_stage"] = "diagnosis"
    state["stages"]["intake"] = {
        "status": "passed",
        "physical_pages": 86,
        "parent_page_range": [167, 252],
        "source_sha256": staged_hash,
        "parent_source_sha256": slice_info["parent_sha256"],
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
        "source_pages": 86,
        "parent_page_range": [167, 252],
        "rationale": "V2 declaration and direct visual checks prove page 167 begins 平砂玉尺经 and page 253 begins the next book, 葬经.",
    }
    with (ROOT / "90-audit" / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    ledger_path = V4 / "V4交付总账.json"
    ledger = read(ledger_path)
    item = next(row for row in ledger["books"] if row["book_no"] == 3)
    item.update({
        "status": "diagnosis",
        "current_stage": "diagnosis",
        "workspace": ROOT.name,
        "source_pages": 86,
        "source_gate": "pending",
        "updated_at": now,
    })
    ledger["next_book_no"] = 3
    ledger["updated_at"] = now
    write(ledger_path, ledger)
    print(json.dumps({
        "book": "平砂玉尺经",
        "book_id": book["book_id"],
        "pages": pages,
        "parent_range": [167, 252],
        "intake": "passed",
        "next_stage": "diagnosis",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
