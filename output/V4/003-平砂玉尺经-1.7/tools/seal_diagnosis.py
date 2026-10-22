#!/usr/bin/env python3
"""Seal G1 after all three Book 003 contact sheets have been reviewed."""

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
    page_map_path = ROOT / "10-diagnosis" / "page-map.jsonl"
    page_map = [json.loads(line) for line in page_map_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sheets = sorted((ROOT / "10-diagnosis" / "all-page-visual-audit").glob("sheet-*.jpg"))
    if len(page_map) != 86 or len(sheets) != 3 or profile["all_page_visual_audit"]["automatic_blank_like_pages"]:
        raise RuntimeError("Diagnosis evidence is incomplete or contradicts the all-page review")

    # Human review overrides the simple luma heuristic for the noisy final page.
    final_page = next(row for row in page_map if row["source_page"] == 86)
    final_page["scan_quality"] = "poor"
    final_page["risk_flags"] = list(dict.fromkeys(
        final_page.get("risk_flags", [])
        + ["bleed_through", "heavy_scan_noise", "low_contrast", "conservative_transcription_required"]
    ))
    final_page["notes"] = ["Human visual review: recoverable text remains, but noise and bleed-through are severe."]
    page_map_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in page_map), encoding="utf-8"
    )

    profile["status"] = "passed_with_ledger"
    profile["low_quality_pages"] = sorted(set(profile.get("low_quality_pages", []) + [86]))
    quality = profile.get("scan_quality_counts", {})
    previous = quality.get("fair", 0)
    if previous > 0:
        quality["fair"] = previous - 1
    quality["poor"] = quality.get("poor", 0) + 1
    profile["all_page_visual_audit"].update({
        "status": "passed",
        "confirmed_at": now,
        "reviewed_pages": 86,
        "blank_or_noncontent_pages": [],
        "unreadable_pages": [],
        "findings": [
            "All 86 pages belong to 平砂玉尺经 and contain included title, front matter, text, or figures.",
            "Pages 50-67 contain figure-heavy layouts requiring image preservation and independent visual checks.",
            "Page 86 is noisy and affected by bleed-through but retains recoverable text; it requires conservative, ledger-backed reconstruction.",
        ],
    })
    write(profile_path, profile)

    accounting = {
        "physical_pages": 86,
        "included_content": 86,
        "blank_or_noncontent": 0,
        "excluded": 0,
        "unreadable": 0,
    }
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
        "pages_routed": 86,
        "all_pages_visually_reviewed": 86,
        "representative_pages_verified": 15,
        "embedded_text_pages": 0,
        "poor_pages": [86],
        "paid_cost_rmb": 0,
    }
    state["stages"]["source"] = {"status": "running"}
    write(ROOT / "run-state.json", state)

    with (ROOT / "90-audit" / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "schema_version": "1.0",
            "event_id": "v4-book003-diagnosis-sealed",
            "time": now,
            "actor": "all-page visual review + seal_diagnosis.py",
            "operation": "diagnosis_gate",
            "source_ids": [book["book_id"]],
            "before": "diagnosis_running",
            "after": "passed_with_ledger",
            "confidence": 1.0,
            "rationale": "All three contact sheets covering 86/86 pages were visually reviewed; no blank, missing, rotated, or cross-book pages were found. Page 86 is retained with a low-quality warning.",
        }, ensure_ascii=False) + "\n")

    ledger_path = V4 / "V4交付总账.json"
    ledger = read(ledger_path)
    ledger["updated_at"] = now
    ledger["next_book_no"] = 3
    item = next(row for row in ledger["books"] if row["book_no"] == 3)
    item.update({
        "status": "diagnosis_passed",
        "workspace": ROOT.name,
        "current_stage": "source_reconstruction",
        "source_pages": 86,
        "source_gate": "pending",
        "updated_at": now,
    })
    write(ledger_path, ledger)
    print(json.dumps({
        "status": "passed_with_ledger",
        "pages": 86,
        "poor_pages": [86],
        "next_stage": "source_reconstruction",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
