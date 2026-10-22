#!/usr/bin/env python3
"""Build a deterministic queue for V3's later fully automatic second pass."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
V3 = HERE.parent
SEGMENTS = V3 / "_work" / "segments"
RESULTS = V3 / "_work" / "results"
QUEUE_DIR = V3 / "_work" / "second_pass"
QUEUE_PATH = QUEUE_DIR / "V3二次自动裁决队列.jsonl"
SUMMARY_PATH = V3 / "_reports" / "V3二次自动裁决队列摘要.json"
VALID_JUDGE_VERDICTS = frozenset({"accept", "revise", "uncertain"})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def normalized_issue(message: str) -> str:
    text = message.strip()
    return text.split("：", 1)[0] if "：" in text else text[:80]


def queue_category(row: dict[str, Any]) -> tuple[str | None, str | None]:
    local_issues = list(row.get("local_issues") or [])
    verdict = row.get("judge_verdict")
    if local_issues:
        return "auto_repair_local_hard", "high"
    if verdict == "revise":
        return "auto_repair_semantic", "high"
    if verdict == "uncertain":
        return "independent_rejudge_source_uncertain", "medium"
    if verdict == "accept" and row.get("uncertainty"):
        return "transparent_uncertainty_no_rewrite", "low"
    if verdict not in VALID_JUDGE_VERDICTS:
        return "independent_rejudge_source_uncertain", "medium"
    return None, None


def build_queue() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    segments = {
        row["id"]: row
        for path in sorted(SEGMENTS.glob("book*.jsonl"))
        for row in read_jsonl(path)
        if row.get("translatable")
    }
    latest: dict[str, dict[str, Any]] = {}
    for path in sorted(RESULTS.glob("book*.jsonl")):
        for row in read_jsonl(path):
            if row.get("id"):
                latest[row["id"]] = row

    queue: list[dict[str, Any]] = []
    categories: Counter[str] = Counter()
    issue_types: Counter[str] = Counter()
    books: Counter[int] = Counter()
    for sid, row in latest.items():
        segment = segments.get(sid)
        if not segment or row.get("source_sha256") != segment.get("source_sha256"):
            continue
        category, priority = queue_category(row)
        if category is None:
            continue
        issues = list(dict.fromkeys(list(row.get("issues") or []) + list(row.get("local_issues") or [])))
        for issue in issues:
            issue_types[normalized_issue(str(issue))] += 1
        categories[category] += 1
        books[int(segment.get("book_no") or 0)] += 1
        queue.append(
            {
                "id": sid,
                "book_no": segment.get("book_no"),
                "source_sha256": segment.get("source_sha256"),
                "category": category,
                "priority": priority,
                "source": segment.get("source"),
                "current_modern_text": row.get("modern_text"),
                "judge_verdict": row.get("judge_verdict"),
                "model_judge_verdict": row.get("model_judge_verdict"),
                "issues": issues,
                "uncertainty": row.get("uncertainty") or [],
                "repair_rounds": row.get("repair_rounds") or 0,
                "repair_models_used": row.get("repair_models_used") or [],
                "writer_model": row.get("writer_model"),
                "judge_model": row.get("judge_model"),
                "queued_at": datetime.now(timezone.utc).astimezone().isoformat(),
            }
        )

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    queue.sort(key=lambda row: (priority_rank[row["priority"]], int(row["book_no"] or 0), row["id"]))
    summary = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "current_traceable_results": sum(
            1
            for sid, row in latest.items()
            if sid in segments and row.get("source_sha256") == segments[sid].get("source_sha256")
        ),
        "queue_items": len(queue),
        "categories": dict(categories),
        "high_priority_machine_repair": categories["auto_repair_local_hard"] + categories["auto_repair_semantic"],
        "medium_priority_independent_rejudge": categories["independent_rejudge_source_uncertain"],
        "low_priority_transparent_only": categories["transparent_uncertainty_no_rewrite"],
        "top_issue_types": issue_types.most_common(30),
        "books_with_queue_items": dict(sorted(books.items())),
        "queue_path": str(QUEUE_PATH),
        "policy": {
            "high": "由另一修复模型重写，再由独立裁判复核；不得覆盖原结果，先生成候选版本。",
            "medium": "由不同模型独立裁决原文是否足以释读；原文损坏则保留透明存疑，不强行改写。",
            "low": "裁判已接受，仅保留透明疑点；默认不再次付费改写。",
        },
    }
    return queue, summary


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8", newline="\n")
    temp.replace(path)


def main() -> None:
    queue, summary = build_queue()
    atomic_write(QUEUE_PATH, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in queue))
    atomic_write(SUMMARY_PATH, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
