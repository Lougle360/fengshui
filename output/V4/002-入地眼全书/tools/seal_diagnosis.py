#!/usr/bin/env python3
"""Seal G1 after the five all-page contact sheets have been reviewed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT.parent


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    profile_path = ROOT / "10-diagnosis" / "profile.json"
    profile = read(profile_path)
    page_map = [json.loads(line) for line in (ROOT / "10-diagnosis" / "page-map.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    sheets = sorted((ROOT / "10-diagnosis" / "all-page-visual-audit").glob("sheet-*.jpg"))
    if len(page_map) != 162 or len(sheets) != 5 or profile["all_page_visual_audit"]["automatic_blank_like_pages"]:
        raise RuntimeError("Diagnosis evidence is incomplete or contradicts the all-page review")
    profile["status"] = "passed_with_ledger"
    profile["all_page_visual_audit"].update(
        {
            "status": "passed",
            "confirmed_at": now,
            "reviewed_pages": 162,
            "blank_or_noncontent_pages": [],
            "unreadable_pages": [],
            "findings": [
                "All 162 pages belong to 入地眼全书 and contain included title, front matter, text, or figures.",
                "Pages 151-153 and 162 contain low-contrast, bleed-through, or damaged scan evidence and require ledger-backed reconstruction.",
            ],
        }
    )
    write(profile_path, profile)

    accounting = {"physical_pages": 162, "included_content": 162, "blank_or_noncontent": 0, "excluded": 0, "unreadable": 0}
    book = read(ROOT / "book.json")
    book["page_accounting"] = accounting
    write(ROOT / "book.json", book)
    manifest = read(ROOT / "00-intake" / "source-manifest.json")
    manifest["page_accounting"] = accounting
    manifest["verified_at"] = now
    write(ROOT / "00-intake" / "source-manifest.json", manifest)

    state = read(ROOT / "run-state.json")
    state["updated_at"] = now
    state["current_stage"] = "source"
    state["stages"]["diagnosis"] = {
        "status": "passed_with_ledger",
        "pages_routed": 162,
        "all_pages_visually_reviewed": 162,
        "representative_pages_verified": 17,
        "embedded_text_pages": 0,
        "paid_cost_rmb": 0,
    }
    state["stages"]["source"] = {"status": "running"}
    write(ROOT / "run-state.json", state)

    with (ROOT / "90-audit" / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "schema_version": "1.0", "event_id": "v4-book002-diagnosis-sealed", "time": now,
            "actor": "all-page visual review + seal_diagnosis.py", "operation": "diagnosis_gate",
            "source_ids": [book["book_id"]], "before": "diagnosis_running", "after": "passed_with_ledger",
            "confidence": 1.0,
            "rationale": "All five contact sheets covering 162/162 pages were visually reviewed; no blank, missing, or cross-book pages were found.",
        }, ensure_ascii=False) + "\n")

    ledger_path = V4 / "V4交付总账.json"
    ledger = read(ledger_path)
    ledger["updated_at"] = now
    ledger["next_book_no"] = 2
    item = next(row for row in ledger["books"] if row["book_no"] == 2)
    item.update({"status": "diagnosis_passed", "workspace": ROOT.name, "current_stage": "source_reconstruction", "source_pages": 162})
    write(ledger_path, ledger)
    print(json.dumps({"status": "passed_with_ledger", "pages": 162, "next_stage": "source_reconstruction"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
