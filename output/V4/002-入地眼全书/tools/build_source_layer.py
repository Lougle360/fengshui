#!/usr/bin/env python3
"""Build Book 002's traceable source layer from page proof and layout evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
SOURCE_PDF = ROOT / "00-intake" / "source.pdf"
MIDDLE_JSON = Path(
    r"C:\Users\QIQI\.codex\visualizations\2026\09\18\01a0b255-9285-73d3-b98d-0ebe46512e50"
    r"\ocr_batch\full-output\doc002\doc002\ocr\doc002_middle.json"
)
PROOF_JSONL = PROJECT / "Md" / "V2" / "_reports" / "proof" / "doc002.proof.jsonl"
AUDIT_JSON = PROJECT / "Md" / "V2" / "_reports" / "documents" / "doc002.audit.json"
V2_MD = PROJECT / "Md" / "V2" / "002 入地眼全书.md"
MASTER_LEDGER = ROOT.parent / "V4交付总账.json"
PAGE_COUNT = 162
PARENT_ZERO_OFFSET = 4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def block_text(block: dict) -> str:
    parts = []
    for line in block.get("lines", []):
        text = "".join(
            str(span.get("content", ""))
            for span in line.get("spans", [])
            if span.get("type") == "text"
        ).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def block_score(block: dict) -> float:
    scores = [
        float(span["score"])
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span.get("type") == "text" and isinstance(span.get("score"), (int, float))
    ]
    if scores:
        return round(sum(scores) / len(scores), 4)
    return round(float(block.get("score", 0.5)), 4) if isinstance(block.get("score"), (int, float)) else 0.5


def normalize_type(value: str) -> str:
    return {
        "text": "body", "title": "title", "index": "table", "image": "figure",
        "image_body": "figure", "image_caption": "caption", "table": "table",
        "equation": "figure", "page_number": "page_number", "header": "header_footer",
        "footer": "header_footer",
    }.get(value or "", value or "unknown")


def scale_bbox(bbox, source_size: tuple[int, int], output_size: tuple[int, int]):
    if not bbox or len(bbox) != 4:
        return None
    sx, sy = output_size[0] / source_size[0], output_size[1] / source_size[1]
    return [round(bbox[0] * sx), round(bbox[1] * sy), round(bbox[2] * sx), round(bbox[3] * sy)]


def latest_successful_proofs() -> dict[int, dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for line in PROOF_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            grouped[int(row["page"])].append(row)
    result = {}
    for parent_zero in range(PARENT_ZERO_OFFSET, PARENT_ZERO_OFFSET + PAGE_COUNT):
        successes = [row for row in grouped.get(parent_zero, []) if row.get("status") == "success"]
        if not successes:
            raise RuntimeError(f"Missing successful proof evidence for parent page {parent_zero + 1}")
        result[parent_zero] = successes[-1]
    return result


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"^>\s*来源：.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", "", text)


def shingle_coverage(reference: str, candidate: str, width: int = 12) -> float:
    reference, candidate = clean_markdown(reference), clean_markdown(candidate)
    if len(reference) < width:
        return 1.0 if reference in candidate else 0.0
    shingles = [reference[index : index + width] for index in range(0, len(reference) - width + 1, width)]
    return round(sum(shingle in candidate for shingle in shingles) / len(shingles), 4)


def evidence_canonical_with_map(text: str) -> tuple[str, list[int]]:
    """Return punctuation-free source glyphs and their raw string offsets."""
    chars, offsets = [], []
    for index, char in enumerate(text or ""):
        if re.match(r"[0-9A-Za-z\u3400-\u9fff]", char):
            chars.append(char)
            offsets.append(index)
    return "".join(chars), offsets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-render", action="store_true", help="Require and reuse diagnosis-rendered page images")
    args = parser.parse_args()
    timestamp = now()
    book = read_json(ROOT / "book.json")
    manifest = read_json(ROOT / "00-intake" / "source-manifest.json")
    if sha256(SOURCE_PDF) != manifest["source_sha256"]:
        raise RuntimeError("Book-specific source hash mismatch")

    pages_dir = ROOT / "20-source" / "pages"
    page_paths = [pages_dir / f"P{page:06d}.jpg" for page in range(1, PAGE_COUNT + 1)]
    if not args.skip_render:
        raise RuntimeError("Book 002 page evidence is created by diagnosis; rerun with --skip-render")
    if not all(path.exists() and path.stat().st_size > 0 for path in page_paths):
        raise RuntimeError("The 162 diagnosis-rendered source page images are incomplete")
    dimensions = {}
    for page, path in enumerate(page_paths, 1):
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            dimensions[page] = image.size

    middle = read_json(MIDDLE_JSON)["pdf_info"]
    if len(middle) != 346:
        raise RuntimeError("Parent MinerU evidence must contain 346 pages")
    proofs = latest_successful_proofs()
    audit = read_json(AUDIT_JSON)

    accepted_by_block: dict[tuple[int, int], list[dict]] = defaultdict(list)
    unresolved = []
    for entry in audit.get("entries", []):
        if int(entry.get("book_number", -1)) != 2:
            continue
        parent_zero = int(entry["page_zero_based"])
        if not (PARENT_ZERO_OFFSET <= parent_zero < PARENT_ZERO_OFFSET + PAGE_COUNT):
            raise RuntimeError(f"Book 002 audit entry lies outside the verified page range: {parent_zero + 1}")
        if entry.get("status") in {"applied", "already_applied"} and entry.get("old") != entry.get("new"):
            accepted_by_block[(parent_zero, int(entry["block_index"]))].append(entry)
        elif entry.get("status") == "recorded_not_applied" and entry.get("old") != entry.get("new"):
            unresolved.append(entry)

    records = []
    markdown = ["# 入地眼全书：可追溯原文层", ""]
    correction_events = []
    failed_corrections = []
    fallback_pages = []
    visual_only_pages = []
    figure_blocks = 0

    for book_zero in range(PAGE_COUNT):
        book_page = book_zero + 1
        parent_zero = PARENT_ZERO_OFFSET + book_zero
        parent_page = parent_zero + 1
        page_id = f"P{book_page:06d}"
        page_meta = middle[parent_zero]
        source_size = tuple(page_meta["page_size"])
        output_size = dimensions[book_page]
        proof_blocks = proofs[parent_zero].get("blocks") or []
        working = []

        if proof_blocks:
            for block_index, raw in enumerate(proof_blocks):
                text = str(raw.get("text", "")).strip()
                original = text
                evidence = ["qwen3-vl-page-proof", "two-pass-v2-audit", f"parent-pdf-page-{parent_page}"]
                for correction in accepted_by_block.get((parent_zero, block_index), []):
                    old, new = str(correction.get("old", "")), str(correction.get("new", ""))
                    if old and text.count(old) == 1:
                        text = text.replace(old, new, 1)
                        outcome = "reapplied"
                    elif new and new in text:
                        outcome = "already_present_in_proof"
                    else:
                        failed_corrections.append(correction)
                        continue
                    correction_events.append({
                        "source_page": book_page, "parent_source_page": parent_page,
                        "block_index": block_index, "candidate_id": correction.get("candidate_id"),
                        "before": old, "after": new, "outcome": outcome,
                        "reason": correction.get("judge_reason"),
                    })
                working.append({
                    "type": normalize_type(str(raw.get("type", "text"))),
                    "bbox": raw.get("bbox"), "text": text,
                    "confidence": 0.97 if text == original else 0.99,
                    "evidence": evidence, "notes": [],
                })
        else:
            fallback_pages.append(book_page)
            for raw in page_meta.get("preproc_blocks", []):
                working.append({
                    "type": normalize_type(str(raw.get("type", "unknown"))),
                    "bbox": raw.get("bbox_fs") or raw.get("bbox"), "text": block_text(raw),
                    "confidence": block_score(raw),
                    "evidence": ["mineru-preproc-fallback", "page-image-retained", f"parent-pdf-page-{parent_page}"],
                    "notes": ["视觉校对记录无文本块，使用 MinerU 预处理层并保留整页图像。"],
                })

        occupied = {tuple(item.get("bbox") or []) for item in working if item["type"] in {"figure", "table"}}
        for raw in page_meta.get("para_blocks", []):
            raw_type = normalize_type(str(raw.get("type", "unknown")))
            if raw_type not in {"figure", "table"} or tuple(raw.get("bbox") or []) in occupied:
                continue
            working.append({
                "type": raw_type, "bbox": raw.get("bbox"), "text": "", "confidence": block_score(raw),
                "evidence": ["mineru-layout", "page-image-retained", f"parent-pdf-page-{parent_page}"],
                "notes": ["图式以整页证据图保留；不依据模糊线条虚构标签或单元格。"],
            })

        if not working or not any(item.get("text") or item["type"] in {"figure", "table"} for item in working):
            visual_only_pages.append(book_page)
            working = [{
                "type": "figure", "bbox": [0, 0, source_size[0], source_size[1]], "text": "", "confidence": 1.0,
                "evidence": ["page-image-retained", "full-corpus-contact-sheet-review"],
                "notes": ["本页以图像或严重透印内容为主；整页证据保留，不推测缺损文字。"],
            }]

        markdown.extend([f"## 原书第 {book_page} 页 {{#{page_id}}}", ""])
        for sequence, item in enumerate(working, 1):
            block_id = f"{page_id}-B{sequence:03d}"
            text, block_type = item["text"], item["type"]
            if block_type in {"figure", "table"}:
                figure_blocks += 1
            disposition = "retained" if text or block_type in {"figure", "table", "noncontent"} else "unreadable"
            record = {
                "schema_version": "1.0", "book_id": book["book_id"], "page_id": page_id,
                "block_id": block_id, "source_page": book_page, "parent_source_page": parent_page,
                "block_type": block_type, "bbox": scale_bbox(item.get("bbox"), source_size, output_size),
                "source_image": f"20-source/pages/{page_id}.jpg", "source_text": text,
                "normalized_text": None, "modern_text": None,
                "language": "lzh" if book_page > 1 else "zh-Hant",
                "operation": "source", "disposition": disposition, "confidence": item["confidence"],
                "evidence": item["evidence"], "notes": item["notes"],
            }
            records.append(record)
            if block_type == "title" and text:
                markdown.extend([f"### {text}", ""])
            elif block_type in {"figure", "table"}:
                markdown.extend([f"![{block_type} {block_id}](pages/{page_id}.jpg)", ""])
            elif text:
                markdown.extend([text, ""])
            else:
                markdown.extend([f"> [{block_type}：见 {page_id} 页图像证据]", ""])

    # Remove page-proof carryover only when the next physical page supplies an
    # exact, long, source-visible prefix.  This repairs duplicated continuations
    # without guessing a semantic boundary.
    by_page: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        by_page[int(record["source_page"])].append(record)
    cross_page_carryover_events = []
    for page in range(1, PAGE_COUNT):
        right_candidates = [row for row in by_page[page + 1] if len(evidence_canonical_with_map(row.get("source_text") or "")[0]) >= 40]
        if not right_candidates:
            continue
        for left in by_page[page]:
            left_text = left.get("source_text") or ""
            left_value, left_offsets = evidence_canonical_with_map(left_text)
            if len(left_value) < 80:
                continue
            matches = []
            for right in right_candidates:
                right_value, _ = evidence_canonical_with_map(right.get("source_text") or "")
                probe = right_value[: min(80, len(right_value))]
                position = left_value.find(probe)
                if position >= 30:
                    matches.append((position, right["block_id"], probe))
            if not matches:
                continue
            position, right_id, probe = min(matches, key=lambda row: row[0])
            raw_cut = left_offsets[position]
            before = left_text
            after = before[:raw_cut].rstrip()
            if not after:
                continue
            left["source_text"] = after
            left["notes"].append(f"移除由下一物理页 {page + 1} 视觉校勘块重复携入的尾文；续接至 {right_id}。")
            left["evidence"].append("adjacent-page-exact-prefix-deduplication")
            cross_page_carryover_events.append({
                "source_page": page, "block_id": left["block_id"], "continuation_block_id": right_id,
                "removed_characters": len(before) - len(after), "matched_prefix": probe,
                "before_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
                "after_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
            })

    # Rebuild source Markdown after evidence-based carryover removal.
    markdown = ["# 入地眼全书：可追溯原文层", ""]
    previous_page = None
    for record in records:
        if previous_page != record["source_page"]:
            markdown.extend([f"## 原书第 {record['source_page']} 页 {{#{record['page_id']}}}", ""])
            previous_page = record["source_page"]
        text, block_type = record.get("source_text") or "", record["block_type"]
        if block_type == "title" and text:
            markdown.extend([f"### {text}", ""])
        elif block_type in {"figure", "table"}:
            markdown.extend([f"![{block_type} {record['block_id']}](pages/{record['page_id']}.jpg)", ""])
        elif text:
            markdown.extend([text, ""])
        else:
            markdown.extend([f"> [{block_type}：见 {record['page_id']} 页图像证据]", ""])

    # Preserve explicit page-sequence links. Classical pages often continue
    # without modern punctuation, so downstream stages must not treat page
    # boundaries as semantic sentence boundaries.
    for page in range(1, PAGE_COUNT):
        left = next((row for row in reversed(by_page[page]) if row["source_text"]), None)
        right = next((row for row in by_page[page + 1] if row["source_text"]), None)
        if left and right:
            left["continuation_to"] = right["block_id"]
            right["continuation_from"] = left["block_id"]

    source_dir = ROOT / "20-source"
    blocks_path = source_dir / "blocks.jsonl"
    blocks_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    source_md_path = source_dir / "source.md"
    source_md_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    uncertainty_path = ROOT / "90-audit" / "uncertain-items.jsonl"
    uncertainty_path.write_text("", encoding="utf-8")
    for entry in unresolved:
        parent_page = int(entry["source_page"])
        book_page = parent_page - PARENT_ZERO_OFFSET
        append_jsonl(uncertainty_path, {
            "schema_version": "1.0", "book_id": book["book_id"],
            "item_id": f"V2-AUDIT-P{book_page:06d}-C{int(entry['candidate_id']):03d}",
            "source_page": book_page, "parent_source_page": parent_page, "page_id": f"P{book_page:06d}",
            "source_image": f"20-source/pages/P{book_page:06d}.jpg", "stage": "source_reconstruction",
            "status": "recorded_not_applied", "old": entry.get("old"), "proposed": entry.get("new"),
            "judge_decision": entry.get("judge_decision"), "judge_confidence": entry.get("judge_confidence"),
            "rationale": entry.get("judge_reason"), "reasons": entry.get("reasons", []),
            "source_audit": "Md/V2/_reports/documents/doc002.audit.json",
        })

    events_path = ROOT / "90-audit" / "events.jsonl"
    existing_events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    prior_corrections = {
        (int(row.get("source_page", -1)), int(row.get("block_index", -1)), int(row.get("candidate_id", -1)))
        for row in existing_events if row.get("event") == "source_correction_reapplied"
    }
    prior_carryovers = {
        (int(row.get("source_page", -1)), str(row.get("block_id", "")), str(row.get("continuation_block_id", "")))
        for row in existing_events if row.get("event") == "cross_page_carryover_removed"
    }
    for event in correction_events:
        key = (int(event["source_page"]), int(event["block_index"]), int(event.get("candidate_id", -1)))
        if key in prior_corrections:
            continue
        append_jsonl(events_path, {
            "schema_version": "1.0", "event": "source_correction_reapplied", "time": timestamp,
            "actor": "build_source_layer.py", **event,
        })
    for event in cross_page_carryover_events:
        key = (int(event["source_page"]), str(event["block_id"]), str(event["continuation_block_id"]))
        if key in prior_carryovers:
            continue
        append_jsonl(events_path, {
            "schema_version": "1.0", "event": "cross_page_carryover_removed", "time": timestamp,
            "actor": "build_source_layer.py", **event,
            "rationale": "The following physical page contains the same long visible prefix; duplicate tail removed from the prior page without semantic inference.",
        })

    coverage = shingle_coverage(V2_MD.read_text(encoding="utf-8"), "\n".join(row["source_text"] for row in records if row["source_text"]))
    report = {
        "schema_version": "1.0", "book_id": book["book_id"], "generated_at": timestamp,
        "status": "passed_with_ledger" if not failed_corrections and coverage >= 0.75 else "failed",
        "physical_pages": PAGE_COUNT, "page_images": len(dimensions), "source_blocks": len(records),
        "text_blocks": sum(bool(row["source_text"]) for row in records),
        "figure_or_table_blocks": figure_blocks, "proof_primary_pages": PAGE_COUNT - len(fallback_pages),
        "mineru_fallback_pages": fallback_pages, "visual_only_pages": visual_only_pages,
        "accepted_corrections_reapplied_or_confirmed": len(correction_events),
        "cross_page_carryover_corrections": len(cross_page_carryover_events),
        "accepted_corrections_failed": len(failed_corrections),
        "unresolved_text_change_candidates": len(unresolved),
        "v2_markdown_12char_shingle_coverage": coverage,
        "source_pdf_sha256": sha256(SOURCE_PDF), "blocks_sha256": sha256(blocks_path),
        "source_md_sha256": sha256(source_md_path),
        "evidence": {"proof": str(PROOF_JSONL), "two_pass_audit": str(AUDIT_JSON), "mineru_middle": str(MIDDLE_JSON), "v2_markdown": str(V2_MD)},
    }
    write_json(source_dir / "source-reconstruction-report.json", report)
    if failed_corrections:
        write_json(source_dir / "failed-corrections.json", failed_corrections)
        raise RuntimeError(f"{len(failed_corrections)} accepted source corrections could not be reconciled")
    if coverage < 0.75:
        raise RuntimeError(f"V2 markdown coverage is too low: {coverage:.2%}")

    state = read_json(ROOT / "run-state.json")
    state["updated_at"] = timestamp
    state["current_stage"] = "normalized"
    state["stages"]["source"] = {
        "status": "passed_with_ledger", "physical_pages": PAGE_COUNT, "page_images": PAGE_COUNT,
        "blocks": len(records), "accepted_corrections": len(correction_events),
        "unresolved_candidates": len(unresolved), "v2_markdown_12char_shingle_coverage": coverage,
        "tool": "Qwen3-VL page proof + V2 two-pass audit + MinerU layout + full-page images", "paid_cost_rmb": 0,
        "evidence": "20-source/source-reconstruction-report.json",
    }
    state["stages"]["normalized"] = {"status": "running"}
    write_json(ROOT / "run-state.json", state)
    append_jsonl(events_path, {
        "schema_version": "1.0", "event": "stage_gate", "stage": "source", "status": "passed_with_ledger",
        "time": timestamp, "actor": "build_source_layer.py",
        "counts": {"pages": PAGE_COUNT, "blocks": len(records), "corrections": len(correction_events), "cross_page_carryover_corrections": len(cross_page_carryover_events), "uncertain_items": len(unresolved)},
        "rationale": "All 162 pages have retained page images and stable block identities; visual-proof text is primary and complex figures remain linked to page evidence.",
    })

    ledger = read_json(MASTER_LEDGER)
    item = next(row for row in ledger["books"] if int(row["book_no"]) == 2)
    item.update({
        "status": "source_reconstructed", "current_stage": "normalization", "source_pages": PAGE_COUNT,
        "source_blocks": len(records), "source_gate": "passed_with_ledger", "updated_at": timestamp,
    })
    ledger["updated_at"] = timestamp
    write_json(MASTER_LEDGER, ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
