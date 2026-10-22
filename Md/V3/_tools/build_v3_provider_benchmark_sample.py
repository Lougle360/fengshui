#!/usr/bin/env python3
"""Build a deterministic, non-paid V3 sample for cross-provider comparison."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
V3 = ROOT / "Md" / "V3"
SEGMENTS = V3 / "_work" / "segments"
REPORTS = V3 / "_reports"
SAMPLE_PATH = REPORTS / "V3多供应商基准样本.jsonl"
SUMMARY_PATH = REPORTS / "V3多供应商基准样本摘要.json"
TARGET = 36


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def length_bucket(length: int) -> str:
    if length < 40:
        return "short_lt40"
    if length < 120:
        return "medium_40_119"
    if length < 300:
        return "long_120_299"
    return "very_long_ge300"


def stable_rank(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"v3-provider-benchmark-2026-09-23|{row['id']}".encode("utf-8")
    ).hexdigest()


def select_sample(rows: list[dict[str, Any]], target: int = TARGET) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("language_hint") or "unknown"),
            str(row.get("kind") or "unknown"),
            length_bucket(len(str(row.get("source") or ""))),
        )
        buckets[key].append(row)
    for values in buckets.values():
        values.sort(key=stable_rank)

    selected: list[dict[str, Any]] = []
    # First cover every available shape once. Rare Japanese/mixed/html/heading
    # cases therefore cannot disappear behind the dominant prose corpus.
    for key in sorted(buckets, key=lambda item: (len(buckets[item]), item)):
        if len(selected) >= target:
            break
        selected.append(buckets[key].pop(0))

    # Fill the remainder round-robin, favoring buckets that still contain data.
    while len(selected) < target:
        progressed = False
        for key in sorted(buckets, key=lambda item: (-len(buckets[item]), item)):
            if buckets[key]:
                selected.append(buckets[key].pop(0))
                progressed = True
                if len(selected) >= target:
                    break
        if not progressed:
            break
    return sorted(selected, key=lambda row: (int(row["book_no"]), row["id"]))


def main() -> None:
    rows = [
        row
        for path in sorted(SEGMENTS.glob("book*.jsonl"))
        for row in read_jsonl(path)
        if row.get("translatable")
    ]
    selected = select_sample(rows)
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sample_lines = []
    for row in selected:
        record = {
            "id": row["id"],
            "book_no": row["book_no"],
            "kind": row["kind"],
            "language_hint": row["language_hint"],
            "source_length": len(row["source"]),
            "length_bucket": length_bucket(len(row["source"])),
            "source_sha256": row["source_sha256"],
            "locked_terms": row.get("locked_terms") or [],
            "opaque_terms": row.get("opaque_terms") or [],
            "source": row["source"],
        }
        sample_lines.append(json.dumps(record, ensure_ascii=False))
    temp = SAMPLE_PATH.with_suffix(SAMPLE_PATH.suffix + ".tmp")
    temp.write_text("\n".join(sample_lines) + "\n", encoding="utf-8", newline="\n")
    temp.replace(SAMPLE_PATH)

    summary = {
        "generated_at": now_iso(),
        "status": "passed" if len(selected) == TARGET else "incomplete",
        "target": TARGET,
        "selected": len(selected),
        "books_covered": len({row["book_no"] for row in selected}),
        "language_counts": dict(Counter(row["language_hint"] for row in selected)),
        "kind_counts": dict(Counter(row["kind"] for row in selected)),
        "length_bucket_counts": dict(
            Counter(length_bucket(len(row["source"])) for row in selected)
        ),
        "sample_path": str(SAMPLE_PATH),
        "selection": "deterministic_sha256_stratified",
        "paid_api_calls": 0,
    }
    temp_summary = SUMMARY_PATH.with_suffix(SUMMARY_PATH.suffix + ".tmp")
    temp_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp_summary.replace(SUMMARY_PATH)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
