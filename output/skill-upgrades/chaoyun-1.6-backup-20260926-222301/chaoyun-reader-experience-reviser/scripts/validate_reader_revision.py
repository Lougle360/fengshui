#!/usr/bin/env python3
"""Validate whole-book reader review, revision ledger, and acceptance evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reader_evidence import snapshot, local_file, check_chapters


DIMENSIONS = {
    "introduction_promise", "prerequisites", "navigation", "continuity", "terminology",
    "examples_and_figures", "redundancy_and_pacing", "source_editor_trust", "closure_and_lookup",
}
OPERATIONS = {"add", "delete_from_reading_path", "rewrite", "reorganize"}
STATUSES = {"proposed", "applied", "rejected", "returned_to_responsible_stage"}
RISKS = {"low", "medium", "high"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"missing {path}")
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected object at {path}:{number}")
        rows.append(value)
    return rows


def validate(root: Path) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    edited = root / "50-edited"
    try:
        review = read_json(edited / "reader-review.json")
        acceptance = read_json(edited / "reader-acceptance-report.json")
        reader_aids = read_json(edited / "reader-aids.json")
        ledger = read_jsonl(edited / "reader-revision-ledger.jsonl")
        source = {row.get("block_id") for row in read_jsonl(root / "20-source/blocks.jsonl") if row.get("block_id")}
        uncertainty_candidates = {
            row.get("candidate_id") for row in read_jsonl(root / "90-audit/uncertainty-candidates.jsonl")
            if row.get("candidate_id")
        }
        output_hash = digest(edited / "modern-reading.md")
        output_text = (edited / "modern-reading.md").read_text(encoding="utf-8")
        input_text = snapshot(root, review, "input")
        decisions = read_jsonl(root / "90-audit/uncertainty-adjudication.jsonl")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid reader-revision evidence: {exc}"], {}

    cycle_id = str(acceptance.get("cycle_id") or "").strip()
    if not cycle_id or review.get("cycle_id") != cycle_id:
        errors.append("reader review and acceptance require the same nonempty cycle_id")
    if review.get("mode") != "manuscript" or acceptance.get("mode") != "manuscript":
        errors.append("publication requires an accepted manuscript-mode reader cycle")
    if not re.fullmatch(r"[0-9a-f]{64}", str(review.get("input_sha256") or "")):
        errors.append("reader review requires the frozen input SHA-256")
    if review.get("schema_version") != "1.1" or acceptance.get("schema_version") != "1.1":
        errors.append("reader evidence requires schema 1.1; legacy acceptance must be re-reviewed")
    dimensions = review.get("dimensions") if isinstance(review.get("dimensions"), dict) else {}
    if set(dimensions) != DIMENSIONS:
        errors.append(f"reader review dimensions mismatch: missing={sorted(DIMENSIONS - set(dimensions))}, extra={sorted(set(dimensions) - DIMENSIONS)}")
    for name, result in dimensions.items():
        if not isinstance(result, dict) or result.get("verdict") not in {"passed", "needs_revision", "blocked"}:
            errors.append(f"reader review dimension {name} has invalid verdict")
        if not isinstance(result, dict) or not isinstance(result.get("findings"), list):
            errors.append(f"reader review dimension {name} requires findings list")
        elif result.get("verdict") in {"needs_revision", "blocked"} and not result.get("findings"):
            errors.append(f"reader review dimension {name} requires findings for its verdict")
    final_dimensions = acceptance.get("dimension_checks") or {}
    if set(final_dimensions) != DIMENSIONS:
        errors.append("acceptance requires regression evidence for every reader dimension")
    for name, result in final_dimensions.items():
        if not isinstance(result, dict) or result.get("status") != "passed" or not str(result.get("evidence") or "").strip():
            errors.append(f"reader dimension {name} lacks a passing evidenced regression")
    errors.extend(check_chapters(output_text, acceptance.get("section_reviews"), source))

    glossary = reader_aids.get("glossary") if isinstance(reader_aids.get("glossary"), dict) else {}
    entries = glossary.get("entries") if isinstance(glossary.get("entries"), list) else []
    terms = {str(row.get("term")) for row in entries if isinstance(row, dict) and row.get("term")}
    core_terms = {str(row.get("term")) for row in entries if isinstance(row, dict) and row.get("term") and row.get("tier") == "core"}
    samples = acceptance.get("glossary_samples") if isinstance(acceptance.get("glossary_samples"), list) else []
    sampled = {
        str(item.get("term")) for item in samples
        if isinstance(item, dict) and item.get("term")
        and item.get("plain_enough") is True and item.get("context_specific") is True
        and item.get("example_helpful") is True and not str(item.get("issue") or "").strip()
        and str(item.get("evidence") or "").strip()
        and item.get("quote") and item["quote"] in output_text
    }
    required_sample = min(10, len(terms))
    if len(sampled & terms) < required_sample:
        errors.append(f"whole-book reader review sampled too few glossary terms: {len(sampled & terms)}/{required_sample}")
    if not core_terms.issubset(sampled):
        errors.append("whole-book reader review must sample every core term")

    event_ids = [row.get("event_id") for row in ledger]
    revision_ids = [row.get("revision_id") for row in ledger]
    if any(not value for value in event_ids) or len(event_ids) != len(set(event_ids)):
        errors.append("reader revision ledger requires unique event_id values")
    if any(not value for value in revision_ids):
        errors.append("every reader revision event requires revision_id")
    current_events = [row for row in ledger if row.get("cycle_id") == cycle_id]
    current_latest: dict[str, dict] = {}
    all_latest: dict[str, dict] = {}
    for row in ledger:
        if row.get("revision_id"):
            all_latest[str(row["revision_id"])] = row
    for row in current_events:
        if row.get("revision_id"):
            current_latest[str(row["revision_id"])] = row
    if ledger and ledger[-1].get("cycle_id") != cycle_id:
        errors.append("reader acceptance does not represent the latest revision cycle")
    blocking_review = set(str(value) for value in review.get("blocking_issues") or [])
    unknown_blocking = sorted(blocking_review - set(str(value) for value in revision_ids if value))
    if unknown_blocking:
        errors.append(f"reader review references unknown revision issues {unknown_blocking}")
    for name, result in dimensions.items():
        for finding in result.get("findings", []) if isinstance(result, dict) else []:
            if not isinstance(finding, dict) or not finding.get("revision_id") or not finding.get("problem"):
                errors.append(f"{name} findings require revision_id and problem")
            elif finding["revision_id"] not in all_latest:
                errors.append(f"{name} finding has no revision event")
    for issue, row in all_latest.items():
        if row.get("status") in {"applied", "rejected"}:
            resolution = row.get("resolution_review") or {}
            if resolution.get("status") != "passed" or not resolution.get("evidence") or not resolution.get("reviewer"):
                errors.append(f"{issue} requires evidenced resolution review")
            if resolution.get("reviewer") == acceptance.get("producer"):
                errors.append(f"{issue} resolution reviewer cannot be the producer")
            if row.get("status") == "rejected" and not row.get("rationale"):
                errors.append(f"{issue} rejection requires rationale")
    replay = input_text
    for row in ledger:
        revision_id = row.get("revision_id")
        if row.get("operation") not in OPERATIONS:
            errors.append(f"{revision_id} has invalid reader revision operation")
        if row.get("status") not in STATUSES:
            errors.append(f"{revision_id} has invalid reader revision status")
        if row.get("semantic_risk") not in RISKS:
            errors.append(f"{revision_id} has invalid semantic_risk")
        if not str(row.get("reader_problem") or "").strip() or not row.get("evidence"):
            errors.append(f"{revision_id} requires reader_problem and evidence")
        block_ids = row.get("block_ids") or []
        if not block_ids and not str(row.get("section") or "").strip():
            errors.append(f"{revision_id} requires affected blocks or section")
        unknown = sorted(set(block_ids) - source)
        if unknown:
            errors.append(f"{revision_id} references unknown blocks {unknown}")
        if row.get("status") == "applied":
            operation = row.get("operation")
            before, after = row.get("before"), row.get("after")
            if operation in {"add", "rewrite", "reorganize"} and (after is None or before == after):
                errors.append(f"{revision_id} applied {operation} requires distinct before/after state")
            if operation == "delete_from_reading_path" and not str(row.get("preservation") or "").strip():
                errors.append(f"{revision_id} deletion requires preservation destination or provenance")
            try:
                before_text = snapshot(root, row, "input")
                after_text = snapshot(root, row, "output")
                start, end = row.get("start_offset"), row.get("end_offset")
                if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(before_text):
                    raise ValueError("invalid exact edit offsets")
                if not isinstance(before, str) or not isinstance(after, str):
                    raise ValueError("before and after must be literal strings")
                if before_text[start:end] != before or before_text[:start] + after + before_text[end:] != after_text:
                    raise ValueError("claimed edit differs from snapshot change")
                if operation == "add" and (start != end or before != "" or not after):
                    raise ValueError("add must insert nonempty text")
                if operation == "delete_from_reading_path":
                    if not before or after:
                        raise ValueError("deletion must remove nonempty text")
                    retained = local_file(root, row.get("preservation")).read_text(encoding="utf-8")
                    if before not in retained:
                        raise ValueError("deleted material is absent from preservation file")
                if row.get("cycle_id") == cycle_id:
                    if before_text != replay:
                        raise ValueError("revision snapshots do not form a continuous edit chain")
                    replay = after_text
            except (OSError, ValueError) as exc:
                errors.append(f"{revision_id}: {exc}")
            if row.get("semantic_risk") in {"medium", "high"} and not row.get("uncertainty_candidate_id"):
                errors.append(f"{revision_id} medium/high semantic risk requires uncertainty_candidate_id")
            elif row.get("semantic_risk") in {"medium", "high"} and row.get("uncertainty_candidate_id") not in uncertainty_candidates:
                errors.append(f"{revision_id} references unknown uncertainty_candidate_id")
    if replay != output_text:
        errors.append("accepted manuscript differs from replayed revision output")
    for row in all_latest.values():
        if row.get("status") == "applied" and row.get("semantic_risk") in {"medium", "high"}:
            active = [item for item in decisions if item.get("active") is True and row.get("uncertainty_candidate_id") in (item.get("candidate_ids") or [])]
            if len(active) != 1 or active[0].get("status") != "resolved_confirmed" or not active[0].get("evidence"):
                errors.append(f"{row.get('revision_id')} semantic revision lacks active evidence-backed confirmation")

    producer = str(acceptance.get("producer") or "").strip()
    reviewer = str(acceptance.get("reviewer") or "").strip()
    if not producer or not reviewer or producer == reviewer:
        errors.append("reader acceptance requires distinct producer and regression reviewer")
    execution_ids = []
    for role in ("producer", "reviewer"):
        try:
            path = local_file(root, acceptance.get(role + "_record"))
            if digest(path) != acceptance.get(role + "_record_sha256"):
                errors.append(f"{role} execution record hash mismatch")
            record = read_json(path)
            execution_ids.append(record.get("run_id"))
            if record.get("actor") != acceptance.get(role) or record.get("output_sha256") != output_hash or not record.get("run_id"):
                errors.append(f"{role} execution record is not bound to this actor and manuscript")
        except (OSError, ValueError) as exc:
            errors.append(f"{role} execution record: {exc}")
    if acceptance.get("producer_record") == acceptance.get("reviewer_record"):
        errors.append("producer and reviewer require separate execution records")
    if len(execution_ids) == 2 and execution_ids[0] == execution_ids[1]:
        errors.append("producer and reviewer must use separate review runs")
    if acceptance.get("status") != "passed" or acceptance.get("regression_review") != "passed":
        errors.append("reader acceptance and regression review must pass")
    if acceptance.get("blocking_issues"):
        errors.append("reader acceptance contains blocking issues")
    if acceptance.get("output_sha256") != output_hash:
        errors.append("reader acceptance hash does not match 50-edited/modern-reading.md")

    expected_counts = {operation: 0 for operation in sorted(OPERATIONS)}
    for row in current_latest.values():
        if row.get("status") == "applied" and row.get("operation") in expected_counts:
            expected_counts[row["operation"]] += 1
    if acceptance.get("counts") != expected_counts:
        errors.append("reader acceptance counts do not match applied revisions in the accepted cycle")
    unresolved = [row.get("revision_id") for row in all_latest.values() if row.get("status") in {"proposed", "returned_to_responsible_stage"}]
    if unresolved:
        errors.append(f"accepted reader cycle still has unresolved revisions {unresolved}")

    counts = {
        "cycles": len({value for value in [cycle_id, *[row.get("cycle_id") for row in ledger]] if value}),
        "current_revisions": len(current_latest),
        "applied_revisions": sum(expected_counts.values()),
        "glossary_sampled": len(sampled & terms),
        "review_dimensions": len(set(dimensions) & DIMENSIONS),
    }
    return errors, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    errors, counts = validate(args.workspace.expanduser().resolve())
    print(json.dumps({"valid": not errors, "counts": counts, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
