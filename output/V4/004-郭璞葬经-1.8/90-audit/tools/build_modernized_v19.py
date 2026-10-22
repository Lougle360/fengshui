#!/usr/bin/env python3
"""Assemble reviewed page translations; keep incomplete work visibly incomplete."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = ROOT / "30-normalized/blocks.jsonl"
REVIEW_DIR = ROOT / "90-audit/modernization-v19"
OUTPUT = ROOT / "40-modernized/blocks.v19-in-progress.jsonl"
REPORT = ROOT / "40-modernized/modernization-v19-progress.json"


def main() -> int:
    normalized = [json.loads(line) for line in NORMALIZED.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {row["block_id"]: row for row in normalized}
    translations = {}
    page_status = {}
    duplicates = []
    for path in sorted(REVIEW_DIR.glob("P*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        page_status[payload["page_id"]] = payload["status"]
        for item in payload.get("blocks", []):
            block_id = item["block_id"]
            if block_id in translations:
                duplicates.append(block_id)
            translations[block_id] = item
    unknown = sorted(set(translations) - set(by_id))
    if duplicates or unknown:
        raise RuntimeError(f"invalid translations: duplicates={duplicates}, unknown={unknown}")
    rows = []
    for block_id, item in translations.items():
        base = dict(by_id[block_id])
        if not str(item.get("modern_text") or "").strip():
            raise RuntimeError(f"empty modern text: {block_id}")
        base.update({
            "modern_text": item["modern_text"],
            "operation": "modernize",
            "language": "zh-Hans",
            "disposition": "translated",
            "confidence": item["confidence"],
            "translation_status": "self_checked",
            "review_notes": item.get("review_notes", []),
        })
        rows.append(base)
    rows.sort(key=lambda row: (row["source_page"], row["reading_order"]))
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    completed_pages = sorted({int(row["source_page"]) for row in rows})
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress" if len(rows) < len(normalized) else "ready_for_independent_comparison",
        "source_blocks": len(normalized),
        "translated_blocks": len(rows),
        "remaining_blocks": len(normalized) - len(rows),
        "completed_pages": completed_pages,
        "page_status": page_status,
        "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
