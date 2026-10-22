#!/usr/bin/env python3
"""Rank source candidates for manual scan review; never auto-accept text."""

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "20-source/blocks.v19-candidates.jsonl"
ALIGNMENT = ROOT / "40-modernized/reference-alignment.jsonl"
OCR_DIR = ROOT / "90-audit/ocr-v19b"
OUTPUT = ROOT / "90-audit/ocr-consensus-review.json"
PANELS = ("top-right", "top-left", "bottom-right", "bottom-left")


def compact(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fff]", text or ""))


def coverage(expected: str, observed: str) -> float:
    expected = compact(expected)
    observed = compact(observed)
    if not expected or not observed:
        return 0.0
    matcher = SequenceMatcher(None, expected, observed, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return round(min(1.0, matched / len(expected)), 4)


def main() -> int:
    candidates = [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines() if line]
    alignments = {
        row["candidate_id"]: row
        for row in (json.loads(line) for line in ALIGNMENT.read_text(encoding="utf-8").splitlines() if line)
    }
    page_ocr: dict[int, str] = {}
    for page in range(1, 30):
        chunks = []
        for panel in PANELS:
            path = OCR_DIR / f"P{page:06d}-{panel}.txt"
            if path.is_file():
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        page_ocr[page] = "\n".join(chunks)

    findings = []
    priorities = Counter()
    for row in candidates:
        expected = row.get("source_text") or row.get("collated_text") or ""
        old_support = "".join(
            alignments.get(support_id, {}).get("old_source", "")
            for support_id in row.get("page_ocr_support", [])
        )
        old_coverage = coverage(expected, old_support)
        vertical_coverage = coverage(expected, page_ocr.get(int(row["source_page"]), ""))
        if row.get("promotion_status") == "accepted":
            priority = "accepted_visual"
        elif min(old_coverage, vertical_coverage) >= 0.75:
            priority = "review_after_conflicts"
        elif max(old_coverage, vertical_coverage) < 0.45:
            priority = "highest_manual_priority"
        else:
            priority = "manual_priority"
        priorities[priority] += 1
        findings.append({
            "block_id": row["block_id"],
            "page_id": row["page_id"],
            "structural_role": row["structural_role"],
            "old_ocr_coverage": old_coverage,
            "vertical_ocr_coverage": vertical_coverage,
            "priority": priority,
            "automatic_acceptance": False,
        })

    payload = {
        "schema_version": "1.0",
        "status": "triage_only",
        "method": "candidate text compared with inherited OCR and new local traditional-vertical Tesseract OCR",
        "automatic_acceptance": False,
        "candidate_count": len(candidates),
        "page_ocr_files": sum(1 for _ in OCR_DIR.glob("P*.txt")),
        "priority_counts": dict(priorities),
        "findings": findings,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("candidate_count", "page_ocr_files", "priority_counts")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
