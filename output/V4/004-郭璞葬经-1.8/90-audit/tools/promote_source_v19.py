#!/usr/bin/env python3
"""Promote the fully reviewed v1.9 candidates into the official source layer."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "20-source/blocks.v19-candidates.jsonl"
AUDIT = ROOT / "90-audit/source-candidate-review.json"
BLOCKS = ROOT / "20-source/blocks.jsonl"
SOURCE_MD = ROOT / "20-source/source.md"
REPORT = ROOT / "20-source/source-reconstruction-report.json"
STATE = ROOT / "run-state.json"
EVENTS = ROOT / "90-audit/events.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    book = read_json(ROOT / "book.json")
    audit = read_json(AUDIT)
    candidates = read_jsonl(CANDIDATES)
    allowed = {"accepted", "rejected_duplicate"}
    failures = []
    for row in candidates:
        if row.get("promotion_status") not in allowed:
            failures.append(f"{row.get('block_id')}: unresolved promotion status")
        bbox = row.get("bbox")
        if row.get("bbox_status") != "visually_measured" or not isinstance(bbox, list) or len(bbox) != 4:
            failures.append(f"{row.get('block_id')}: missing measured bbox")
        if not str(row.get("visual_structure_evidence") or "").strip():
            failures.append(f"{row.get('block_id')}: missing page-specific visual evidence")
        if row.get("promotion_status") == "accepted" and not str(row.get("source_text") or "").strip():
            failures.append(f"{row.get('block_id')}: accepted block has no source text")
    pages = sorted({int(row["source_page"]) for row in candidates})
    if pages != list(range(1, int(book["source_pdf_pages"]) + 1)):
        failures.append(f"physical page coverage mismatch: {pages}")
    if audit.get("status") != "accepted_with_rejected_duplicates" or audit.get("pending_visual_review") != 0:
        failures.append("candidate audit has not reached a closed accepted state")
    if failures:
        raise RuntimeError("source promotion blocked:\n- " + "\n- ".join(failures))

    accepted = [row for row in candidates if row["promotion_status"] == "accepted"]
    rejected = [row for row in candidates if row["promotion_status"] == "rejected_duplicate"]
    page_orders: Counter[int] = Counter()
    id_map: dict[str, str] = {}
    records = []
    for row in accepted:
        page = int(row["source_page"])
        page_orders[page] += 1
        block_id = f"P{page:06d}-B{page_orders[page]:03d}"
        id_map[row["block_id"]] = block_id
        record = {
            "schema_version": "1.0",
            "book_id": book["book_id"],
            "page_id": row["page_id"],
            "block_id": block_id,
            "source_candidate_id": row["block_id"],
            "source_page": page,
            "block_type": row["structural_role"],
            "component_id": row["component_id"],
            "structural_role": row["structural_role"],
            "reading_order": page_orders[page],
            "bbox": row["bbox"],
            "source_image": row["primary_evidence"],
            "source_text": row["source_text"],
            "normalized_text": None,
            "modern_text": None,
            "language": "lzh",
            "operation": "source",
            "disposition": "retained",
            "confidence": 1.0,
            "evidence": [
                "page-specific-visual-transcription",
                row["primary_evidence"],
                "90-audit/source-page-reviews-v19b",
            ],
            "notes": [row["visual_structure_evidence"]],
            "continues_from_previous_page": bool(row.get("continues_from_previous_page")),
            "continues_to_next_page": bool(row.get("continues_to_next_page")),
        }
        if row.get("regions"):
            record["regions"] = row["regions"]
        records.append(record)

    by_page: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        by_page[int(record["source_page"])].append(record)
    for page in range(1, int(book["source_pdf_pages"])):
        left = next((row for row in reversed(by_page[page]) if row.get("source_text")), None)
        right = next((row for row in by_page[page + 1] if row.get("source_text")), None)
        if left and right and (left["continues_to_next_page"] or right["continues_from_previous_page"]):
            left["continuation_to"] = right["block_id"]
            right["continuation_from"] = left["block_id"]

    BLOCKS.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    markdown = [f"# {book['title']}：可追溯原文层", ""]
    for page in range(1, int(book["source_pdf_pages"]) + 1):
        markdown.extend([f"## 原书第 {page} 页 {{#P{page:06d}}}", ""])
        for row in by_page[page]:
            if row["structural_role"] == "heading":
                markdown.extend([f"### {row['source_text']}", ""])
            elif row["structural_role"] == "running_header":
                markdown.extend([f"> 页内版心：{row['source_text']}", ""])
            else:
                markdown.extend([row["source_text"], ""])
    SOURCE_MD.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "1.9",
        "book_id": book["book_id"],
        "generated_at": now,
        "status": "passed_with_ledger",
        "physical_pages": int(book["source_pdf_pages"]),
        "page_images": int(book["source_pdf_pages"]),
        "candidate_blocks": len(candidates),
        "source_blocks": len(records),
        "accepted_source_blocks": len(records),
        "rejected_duplicate_blocks": len(rejected),
        "pending_visual_review": 0,
        "stale_page_review_bindings": audit.get("stale_page_review_bindings", []),
        "reference_only_omissions": audit.get("reference_only_omissions", []),
        "source_only_residual_rows": audit.get("source_only_residual_rows", []),
        "multi_region_blocks": sum(bool(row.get("regions")) for row in records),
        "blocks_sha256": sha256(BLOCKS),
        "source_md_sha256": sha256(SOURCE_MD),
        "candidate_audit_sha256": sha256(AUDIT),
        "rejected_candidates": [
            {"candidate_id": row["block_id"], "source_page": row["source_page"], "reason": row["visual_structure_evidence"]}
            for row in rejected
        ],
    }
    write_json(REPORT, report)

    state = read_json(STATE)
    state["updated_at"] = now
    state["current_stage"] = "normalization"
    state["stages"]["source"] = {
        "status": "passed_with_ledger",
        "pages": int(book["source_pdf_pages"]),
        "blocks": len(records),
        "rejected_duplicate_blocks": len(rejected),
        "pending_visual_review": 0,
        "evidence": "20-source/source-reconstruction-report.json",
        "paid_cost_rmb": 0,
    }
    for stage in ("source_adjudicated", "normalized", "book_understood", "reader_designed", "sample_accepted", "modernized", "edited", "reader_revised", "final_adjudicated"):
        state["stages"][stage] = {
            "status": "pending_rebuild",
            "reason": "Official source layer was replaced by the 307-block visually verified workflow-1.9 reconstruction.",
        }
    # Publication stays explicitly revoked until the entire downstream workflow is rebuilt and revalidated.
    write_json(STATE, state)
    with EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "schema_version": "1.0",
            "event": "stage_gate",
            "stage": "source",
            "status": "passed_with_ledger",
            "time": now,
            "actor": "promote_source_v19.py",
            "counts": {"pages": int(book["source_pdf_pages"]), "blocks": len(records), "rejected_duplicates": len(rejected)},
            "rationale": "All 309 candidates have measured page coordinates and page-specific evidence; 307 were promoted and two duplicate OCR pseudo-blocks were excluded with explicit evidence.",
        }, ensure_ascii=False) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
