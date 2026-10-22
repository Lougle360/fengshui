#!/usr/bin/env python3
"""Audit the growing V3 result set without requiring full-corpus completion."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
V3 = HERE.parent
SEGMENTS = V3 / "_work" / "segments"
RESULTS = V3 / "_work" / "results"
REPORT = V3 / "_reports" / "V3增量可追溯性审计.json"


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"file": path.name, "line": line_no, "error": str(exc)})
                continue
            if isinstance(value, dict):
                rows.append(value)
            else:
                errors.append({"file": path.name, "line": line_no, "error": "row_not_object"})
    return rows, errors


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def audit() -> dict[str, Any]:
    segment_by_id: dict[str, dict[str, Any]] = {}
    expected_by_book: Counter[int] = Counter()
    parse_errors: list[dict[str, Any]] = []
    for path in sorted(SEGMENTS.glob("book*.jsonl")):
        rows, errors = read_jsonl(path)
        parse_errors.extend(errors)
        for row in rows:
            if not row.get("translatable"):
                continue
            sid = str(row.get("id") or "")
            if sid:
                segment_by_id[sid] = row
                expected_by_book[int(row.get("book_no") or 0)] += 1

    latest: dict[str, dict[str, Any]] = {}
    history_count: Counter[str] = Counter()
    result_file_by_id: dict[str, str] = {}
    for path in sorted(RESULTS.glob("book*.jsonl")):
        rows, errors = read_jsonl(path)
        parse_errors.extend(errors)
        for row in rows:
            sid = str(row.get("id") or "")
            if not sid:
                continue
            history_count[sid] += 1
            latest[sid] = row
            result_file_by_id[sid] = path.name

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    valid_by_book: Counter[int] = Counter()
    verdict_counts: Counter[str] = Counter()
    uncertain = 0
    accepted_with_uncertainty = 0
    unresolved_local = 0

    for sid, row in latest.items():
        segment = segment_by_id.get(sid)
        if segment is None:
            warnings.append({"id": sid, "type": "orphaned_historical_result", "file": result_file_by_id[sid]})
            continue
        source = str(segment.get("source") or "")
        expected_hash = str(segment.get("source_sha256") or sha256_text(source))
        if row.get("status") != "judged":
            failures.append({"id": sid, "type": "status_not_judged", "value": row.get("status")})
            continue
        if row.get("source_sha256") != expected_hash:
            failures.append({"id": sid, "type": "source_hash_mismatch"})
            continue
        if str(row.get("source") or "") != source:
            failures.append({"id": sid, "type": "source_text_mismatch"})
            continue
        if not str(row.get("modern_text") or "").strip():
            failures.append({"id": sid, "type": "empty_modern_text"})
            continue
        missing_evidence = [field for field in ("writer_model", "judge_model", "judge_verdict", "generated_at") if not row.get(field)]
        if missing_evidence:
            failures.append({"id": sid, "type": "missing_evidence_fields", "fields": missing_evidence})
            continue
        valid_by_book[int(segment.get("book_no") or 0)] += 1
        verdict = str(row.get("judge_verdict") or "missing")
        verdict_counts[verdict] += 1
        if row.get("judge_verdict") != "accept" or row.get("uncertainty"):
            uncertain += 1
        if verdict == "accept" and row.get("uncertainty"):
            accepted_with_uncertainty += 1
        if row.get("local_issues"):
            unresolved_local += 1
        if history_count[sid] > 1:
            warnings.append({"id": sid, "type": "multiple_history_records", "count": history_count[sid]})

    expected_total = len(segment_by_id)
    valid_total = sum(valid_by_book.values())
    books = []
    for book_no in sorted(expected_by_book):
        expected = expected_by_book[book_no]
        valid = valid_by_book[book_no]
        books.append({"book_no": book_no, "expected": expected, "traceable_results": valid, "coverage_percent": round(valid * 100 / expected, 3) if expected else 100.0})

    status = "failed" if parse_errors or failures else ("complete_passed" if valid_total == expected_total else "partial_passed")
    return {
        "status": status,
        "audited_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "expected_translatable_segments": expected_total,
        "latest_result_records": len(latest),
        "traceable_results": valid_total,
        "coverage_percent": round(valid_total * 100 / expected_total, 3) if expected_total else 100.0,
        "missing_result_count": expected_total - len(set(segment_by_id) & set(latest)),
        "uncertain_or_nonaccept_count": uncertain,
        "judge_verdict_counts": dict(verdict_counts),
        "accepted_with_transparent_uncertainty_count": accepted_with_uncertainty,
        "unresolved_local_issue_count": unresolved_local,
        "historical_revision_ids": sum(1 for count in history_count.values() if count > 1),
        "parse_errors": parse_errors,
        "integrity_failures": failures,
        "warnings": warnings[:100],
        "warnings_truncated": max(0, len(warnings) - 100),
        "books": books,
    }


def main() -> None:
    report = audit()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(REPORT)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
