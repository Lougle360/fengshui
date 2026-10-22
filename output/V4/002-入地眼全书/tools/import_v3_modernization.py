#!/usr/bin/env python3
"""Import V3 segment translations into Book 002's stable V4 block graph."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
V3 = PROJECT / "Md" / "V3"
LEDGER = ROOT.parent / "V4交付总账.json"
sys.path.insert(0, str(PROJECT / "output" / "V4" / "001-青囊海角经" / "tools" / "_vendor"))
from opencc import OpenCC  # noqa: E402

CC = OpenCC("t2s")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", CC.convert(text or ""))


def clean_modern(text: str) -> str:
    value = re.sub(r"^#{1,6}\s*", "", (text or "").strip())
    return value.strip()


def result_confidence(result: dict | None, mapping: str) -> float:
    if result is None:
        return 0.9 if mapping in {"short_source_label_retained", "nontext"} else 0.65
    base = {"accept": 0.96, "revise": 0.70, "uncertain": 0.58}.get(result.get("judge_verdict"), 0.60)
    if result.get("judge_confidence") == "medium":
        base -= 0.05
    elif result.get("judge_confidence") == "low":
        base -= 0.12
    return round(max(0.0, base), 2)


def main() -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    normalized_path = ROOT / "30-normalized" / "blocks.jsonl"
    normalized = read_jsonl(normalized_path)
    segments = read_jsonl(V3 / "_work" / "segments" / "book002.jsonl")
    results = read_jsonl(V3 / "_work" / "results" / "book002.jsonl")
    segment_by_id = {row["id"]: row for row in segments}
    current_ids = set(segment_by_id)
    result_by_id = {row["id"]: row for row in results if row.get("id") in current_ids}

    alignment = read_json(ROOT / "40-modernized" / "segment-alignment-analysis.json")
    alignment_by_id = {row["id"]: row for row in alignment["alignments"]}
    bounded_decisions = read_jsonl(ROOT / "40-modernized" / "final-decisions.jsonl")
    bounded_ids = {
        row["id"] for row in bounded_decisions
        if row.get("status") in {"second_pass_judged", "second_pass_rejudged"}
        and row.get("decision") in {"keep_current", "keep_current_transparent_uncertainty"}
        and row.get("approved_for_apply") is False
    }

    anchor_payloads: dict[str, list[dict]] = defaultdict(list)
    segment_anchor: dict[str, str] = {}
    block_segments: dict[str, set[str]] = defaultdict(set)
    terminology: dict[str, set[str]] = defaultdict(set)
    mapped_segment_ids = set()
    verdict_counts: Counter[str] = Counter()

    for segment in segments:
        row = alignment_by_id.get(segment["id"], {})
        block_ids = row.get("block_ids") or []
        if row.get("status") != "anchored" or not block_ids:
            continue
        mapped_segment_ids.add(segment["id"])
        anchor = block_ids[0]
        segment_anchor[segment["id"]] = anchor
        for block_id in block_ids:
            block_segments[block_id].add(segment["id"])
        result = result_by_id.get(segment["id"])
        if result is not None:
            modern = clean_modern(result.get("modern_text") or "")
            verdict = result.get("judge_verdict") or "unknown"
            verdict_counts[verdict] += 1
            for note in result.get("term_notes") or []:
                term, explanation = str(note.get("term", "")).strip(), str(note.get("note", "")).strip()
                if term and explanation:
                    terminology[term].add(explanation)
        else:
            modern = clean_modern(CC.convert(segment.get("source") or ""))
            verdict = "nontranslatable"
        anchor_payloads[anchor].append({
            "segment_id": segment["id"], "modern_text": modern, "result": result,
            "verdict": verdict, "all_block_ids": block_ids,
        })

    output, mapping_rows, uncertainties = [], [], []
    mapping_counts: Counter[str] = Counter()
    for record in normalized:
        block_id = record["block_id"]
        normalized_text = record.get("normalized_text") or ""
        payloads = anchor_payloads.get(block_id, [])
        related_ids = sorted(block_segments.get(block_id, set()))
        review_status = "accepted"
        if payloads:
            modern_text = "\n\n".join(payload["modern_text"] for payload in payloads if payload["modern_text"])
            mapping_mode = "v3_segment_anchor"
            disposition = "translated"
            linked_results = [payload["result"] for payload in payloads if payload["result"]]
            pending = [payload for payload in payloads if payload["result"] and payload["verdict"] != "accept" and payload["segment_id"] not in bounded_ids]
            bounded = [payload for payload in payloads if payload["segment_id"] in bounded_ids]
            has_uncertainty = any((payload["result"] or {}).get("uncertainty") for payload in payloads)
            if pending:
                review_status = "pending_repair"
            elif bounded or has_uncertainty:
                review_status = "accepted_with_ledger"
            confidence = min((result_confidence(payload["result"], mapping_mode) for payload in payloads), default=0.9)
        elif related_ids:
            modern_text = ""
            mapping_mode = "v3_segment_continuation"
            disposition = "translated"
            linked_results = [result_by_id[segment_id] for segment_id in related_ids if segment_id in result_by_id]
            pending = [segment_id for segment_id in related_ids if segment_id in result_by_id and result_by_id[segment_id].get("judge_verdict") != "accept" and segment_id not in bounded_ids]
            review_status = "pending_repair" if pending else ("accepted_with_ledger" if any(segment_id in bounded_ids for segment_id in related_ids) else "accepted")
            confidence = min((result_confidence(result, mapping_mode) for result in linked_results), default=0.85)
        elif not canonical(normalized_text):
            modern_text = ""
            mapping_mode = "nontext"
            disposition = record.get("disposition", "retained")
            linked_results = []
            confidence = 0.95
        else:
            # The alignment audit proves all uncovered blocks are short titles,
            # contributor lines, or damaged labels (max 23 canonical chars).
            # Retain them rather than forcing an unrelated V3 segment.
            modern_text = normalized_text
            mapping_mode = "short_source_label_retained"
            disposition = "retained"
            linked_results = []
            confidence = 0.82 if len(canonical(normalized_text)) <= 23 else 0.65
            review_status = "accepted_with_ledger"
            uncertainties.append({
                "schema_version": "1.0", "item_id": f"V4-MOD-{block_id}", "book_id": record["book_id"],
                "block_id": block_id, "page_id": record["page_id"], "source_page": record["source_page"],
                "stage": "modernization", "status": review_status,
                "issues": ["Short heading/contributor label did not receive a unique V3 segment anchor; normalized source wording is retained."],
                "uncertainty": [], "source": normalized_text, "candidate": modern_text,
            })

        for payload in payloads:
            result = payload["result"]
            if result and (result.get("issues") or result.get("uncertainty") or result.get("judge_verdict") != "accept"):
                uncertainties.append({
                    "schema_version": "1.0", "item_id": f"V4-MOD-{block_id}-{payload['segment_id']}",
                    "book_id": record["book_id"], "block_id": block_id, "page_id": record["page_id"],
                    "source_page": record["source_page"], "stage": "modernization", "status": review_status,
                    "v3_segment_id": payload["segment_id"], "judge_verdict": result.get("judge_verdict"),
                    "judge_confidence": result.get("judge_confidence"), "issues": result.get("issues") or [],
                    "uncertainty": result.get("uncertainty") or [], "source": segment_by_id[payload["segment_id"]].get("source"),
                    "candidate": payload["modern_text"],
                })

        item = dict(record)
        item.update({
            "modern_text": modern_text, "operation": "modernized", "disposition": disposition,
            "language_route": "lzh_to_zh-Hans" if disposition == "translated" else "zh-Hans_retain",
            "modernization_mapping": mapping_mode, "v3_segment_ids": related_ids,
            "segment_anchor_ids": {segment_id: segment_anchor.get(segment_id) for segment_id in related_ids},
            "confidence": confidence, "review_status": review_status,
            "review_evidence": [{
                "segment_id": result.get("id"), "writer_model": result.get("writer_model"),
                "repair_model": result.get("repair_model"), "judge_model": result.get("judge_model"),
                "judge_verdict": result.get("judge_verdict"), "judge_confidence": result.get("judge_confidence"),
            } for result in linked_results],
        })
        output.append(item)
        mapping_counts[mapping_mode] += 1
        mapping_rows.append({"block_id": block_id, "mapping_mode": mapping_mode, "v3_segment_ids": related_ids, "review_status": review_status})

    normalized_ids, output_ids = [row["block_id"] for row in normalized], [row["block_id"] for row in output]
    if normalized_ids != output_ids:
        raise RuntimeError("Modernization changed block identity/order")
    uncovered = [row for row in output if row["modernization_mapping"] == "short_source_label_retained"]
    if any(len(canonical(row.get("normalized_text") or "")) > 23 for row in uncovered):
        raise RuntimeError("A substantive unmatched block exceeds the bounded short-label policy")

    out_dir = ROOT / "40-modernized"
    blocks_path = out_dir / "blocks.jsonl"
    blocks_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8")
    (out_dir / "mapping.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in mapping_rows), encoding="utf-8")
    (out_dir / "uncertainties.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in uncertainties), encoding="utf-8")

    current_translatable = {row["id"] for row in segments if row.get("translatable")}
    mapped_translatable = current_translatable & mapped_segment_ids
    repair_ids = sorted(
        segment_id for segment_id in mapped_translatable
        if segment_id in result_by_id and result_by_id[segment_id].get("judge_verdict") != "accept" and segment_id not in bounded_ids
    )
    repair_queue = []
    for segment_id in repair_ids:
        segment, result = segment_by_id[segment_id], result_by_id[segment_id]
        repair_queue.append({
            "schema_version": "1.0", "id": segment_id, "book_no": 2,
            "source_sha256": segment["source_sha256"], "category": "v4_final_repair", "priority": "high",
            "repair_id": f"V4-REPAIR-{segment_id}",
            "v4_block_ids": alignment_by_id[segment_id].get("block_ids") or [],
            "source": segment["source"], "locked_terms": segment.get("locked_terms") or [],
            "opaque_terms": segment.get("opaque_terms") or [], "draft_modern_text": result.get("modern_text") or "",
            "current_modern_text": result.get("modern_text") or "", "judge_verdict": result.get("judge_verdict"),
            "judge_confidence": result.get("judge_confidence"), "issues": result.get("issues") or [],
            "uncertainty": result.get("uncertainty") or [], "required_action": "repair_and_independent_rejudge",
        })
    repair_path = out_dir / "repair-queue.jsonl"
    repair_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in repair_queue), encoding="utf-8")

    markdown = ["# 入地眼全书：V4 现代化草稿", "", "> 待修复标记清零前，本文件不得进入出版稿。", ""]
    previous_page = None
    for row in output:
        if previous_page != row["page_id"]:
            markdown.extend([f"## 原书第 {row['source_page']} 页 {{{row['page_id']}}}", ""])
            previous_page = row["page_id"]
        if row["block_type"] in {"figure", "table"}:
            markdown.extend([f"![{row['block_type']} {row['block_id']}](../20-source/pages/{row['page_id']}.jpg)", ""])
        elif row.get("modern_text"):
            if row["review_status"] == "pending_repair":
                markdown.extend([f"> **待修复：** `{row['block_id']}`", ""])
            markdown.extend([row["modern_text"], ""])
    modern_md = out_dir / "modernized.md"
    modern_md.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")
    write_json(out_dir / "terminology.json", {
        "schema_version": "1.0", "source": "V3 term notes aggregated without new definitions",
        "terms": [{"term": term, "notes": sorted(notes), "status": "source-attested"} for term, notes in sorted(terminology.items())],
    })

    total_chars = sum(len(canonical(row.get("normalized_text") or "")) for row in output)
    mapped_chars = sum(len(canonical(row.get("normalized_text") or "")) for row in output if row["modernization_mapping"] != "short_source_label_retained")
    report = {
        "schema_version": "1.0", "generated_at": timestamp,
        "status": "completed" if not repair_queue else "running",
        "normalized_blocks": len(normalized), "modernized_blocks": len(output), "identity_match": normalized_ids == output_ids,
        "mapping_counts": dict(mapping_counts), "mapped_canonical_character_percent": round(100 * mapped_chars / total_chars, 3),
        "v3_current_translatable_segments": len(current_translatable), "v3_traceable_results": sum(segment_id in result_by_id for segment_id in current_translatable),
        "v3_traceability_percent": round(100 * sum(segment_id in result_by_id for segment_id in current_translatable) / len(current_translatable), 3),
        "mapped_v3_segments": len(mapped_segment_ids), "mapped_translatable_segments": len(mapped_translatable),
        "mapped_verdict_counts": dict(verdict_counts), "repair_queue_segments": len(repair_queue),
        "bounded_uncertainty_segments": len(bounded_ids & mapped_translatable), "unresolved_block_records": len(uncertainties),
        "short_label_blocks_retained": len(uncovered), "short_label_characters_retained": sum(len(canonical(row.get("normalized_text") or "")) for row in uncovered),
        "paid_calls_made_by_v4_import": 0,
        "repair_preflight": {
            "provider": "volcengine-ark", "credential_scope": "Windows user environment; secret not written to artifacts",
            "paid_calls_authorized": True, "shared_project_hard_cap_rmb": 150.0,
        },
        "normalized_sha256": sha256(normalized_path), "blocks_sha256": sha256(blocks_path),
        "draft_markdown_sha256": sha256(modern_md), "repair_queue_sha256": sha256(repair_path),
    }
    write_json(out_dir / "modernization-report.json", report)

    state = read_json(ROOT / "run-state.json")
    state["updated_at"] = timestamp; state["current_stage"] = "modernized" if repair_queue else "edited"
    state["stages"]["modernized"] = {
        "status": "running" if repair_queue else "passed_with_ledger", "blocks": len(output),
        "repair_queue_segments": len(repair_queue), "mapping_counts": dict(mapping_counts),
        "paid_calls_made_by_import": 0, "evidence": "40-modernized/modernization-report.json",
    }
    write_json(ROOT / "run-state.json", state)
    ledger = read_json(LEDGER)
    item = next(row for row in ledger["books"] if int(row["book_no"]) == 2)
    item.update({
        "status": "modernization_in_progress" if repair_queue else "editing_ready",
        "current_stage": "modernization_repair" if repair_queue else "editing", "modernized_blocks": len(output),
        "repair_queue_segments": len(repair_queue), "modernization_gate": "running" if repair_queue else "passed_with_ledger", "updated_at": timestamp,
    })
    ledger["updated_at"] = timestamp
    write_json(LEDGER, ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
