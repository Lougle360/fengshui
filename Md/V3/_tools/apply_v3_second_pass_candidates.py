#!/usr/bin/env python3
"""Conservatively append only fully approved second-pass candidates.

This never rewrites a source file or overwrites an existing result line. It is
designed to run after first pass and the second-pass queue have both completed.
"""

from __future__ import annotations

import argparse
import json
import os
import runpy
from collections import Counter
from pathlib import Path
from typing import Any


PIPELINE = Path(__file__).with_name("v3_pipeline.py")
m = runpy.run_path(str(PIPELINE), run_name="v3_second_pass_apply")
V3: Path = m["V3"]
WORK: Path = m["WORK"]
REPORTS: Path = m["REPORTS"]
RESULTS: Path = m["RESULTS"]
SECOND_PASS = WORK / "second_pass"
CANDIDATES = Path(os.getenv("V3_SECOND_PASS_CANDIDATES_DIR", str(SECOND_PASS / "candidates")))
DECISIONS_PATH = Path(os.getenv("V3_SECOND_PASS_DECISIONS_PATH", str(SECOND_PASS / "V3二次自动裁决决策.jsonl")))
RUN_STATE_PATH = Path(os.getenv("V3_SECOND_PASS_STATE_PATH", str(REPORTS / "V3二次自动裁决运行状态.json")))
APPLY_REPORT_PATH = Path(os.getenv("V3_SECOND_PASS_APPLY_REPORT_PATH", str(REPORTS / "V3二次自动裁决回写报告.json")))
MANUAL_REPAIRS_PATH = V3.parent.parent / "output" / "V4" / "001-青囊海角经" / "40-modernized" / "manual-repairs.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def latest_by_id(paths: list[Path]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in read_jsonl(path):
            if row.get("id"):
                latest[row["id"]] = row
    return latest


def write_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp.replace(path)


def append_result(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def validate_candidate(
    decision: dict[str, Any],
    source: dict[str, Any],
    current: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if decision.get("status") != "second_pass_judged":
        return {}, ["decision_not_second_pass_judged"]
    decision_kind = decision.get("decision")
    if decision_kind not in {"approve_candidate", "approve_manual_candidate"} or decision.get("approved_for_apply") is not True:
        return {}, ["candidate_not_explicitly_approved"]
    if decision.get("source_sha256") != source.get("source_sha256"):
        return {}, ["decision_source_sha256_mismatch"]
    if current.get("source_sha256") != source.get("source_sha256"):
        return {}, ["current_result_source_sha256_mismatch"]
    if current.get("status") != "judged":
        return {}, ["current_result_not_judged"]
    if decision_kind == "approve_manual_candidate":
        if decision.get("manual_review_status") != "accepted_after_issue_directed_repair":
            return {}, ["manual_review_gate_failed"]
    else:
        if decision.get("current_result_generated_at") != current.get("generated_at"):
            return {}, ["current_result_changed_after_pairwise_review"]
        judge = decision.get("pairwise_judge") or {}
        if not (
            judge.get("winner") == "candidate"
            and judge.get("candidate_verdict") == "accept"
            and judge.get("confidence") in {"high", "medium"}
        ):
            return {}, ["pairwise_judge_gate_failed"]
    final_text = str(decision.get("candidate_modern_text") or "").strip()
    if not final_text:
        return {}, ["empty_candidate"]
    source_for_validation = dict(source)
    source_for_validation["language_hint"] = current.get("language") or source.get("language_hint")
    checker = runpy.run_path(str(PIPELINE), run_name="v3_second_pass_check")
    glossary = checker["load_glossary"]()
    quality = checker["local_quality_issues"](
        source.get("source") or "",
        final_text,
        current.get("language"),
        source.get("locked_terms") or [],
        checker["allowed_glossary_for"](source.get("locked_terms") or [], glossary),
        source.get("opaque_terms") or [],
    )
    hard_issues = checker["hard_issue_messages"](quality)
    if hard_issues:
        return {"quality": quality}, ["local_hard_gate_failed", *hard_issues]
    return {"quality": quality, "modern_text": final_text}, []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    process_path = REPORTS / "V3后台进程.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    pid = int(process.get("pid") or 0)
    if m["pid_is_alive"](pid):
        raise RuntimeError(f"首轮后台 PID={pid} 仍存活，拒绝回写")
    if not RUN_STATE_PATH.exists():
        raise RuntimeError("缺少二次裁决状态，不能回写")
    second_state = json.loads(RUN_STATE_PATH.read_text(encoding="utf-8"))
    if second_state.get("status") != "completed":
        raise RuntimeError("二次裁决尚未完整结束")
    if not DECISIONS_PATH.exists():
        raise RuntimeError("缺少二次裁决决策台账")

    decision_map = latest_by_id([DECISIONS_PATH])
    manual_repairs = {
        row["v3_segment_id"]: row
        for row in read_jsonl(MANUAL_REPAIRS_PATH)
        if row.get("v3_segment_id")
        and row.get("review_status") == "accepted_after_issue_directed_repair"
    }
    source_map: dict[str, dict[str, Any]] = {}
    for path in sorted((WORK / "segments").glob("book*.jsonl")):
        source_map.update({row["id"]: row for row in read_jsonl(path)})
    current_map = latest_by_id(sorted(RESULTS.glob("book*.jsonl")))
    report = {
        "generated_at": m["now_iso"](),
        "status": "dry_run" if not args.apply else "applying",
        "first_pass_pid": pid,
        "second_pass_status": second_state.get("status"),
        "approved_candidates": sum(
            1 for row in decision_map.values() if row.get("approved_for_apply") is True
        ),
        "appended": 0,
        "skipped_or_rejected": 0,
        "rejection_reasons": {},
        "preserves_existing_rows": True,
    }
    reason_counts: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    for sid, decision in decision_map.items():
        if decision.get("approved_for_apply") is not True:
            continue
        if decision.get("decision") == "approve_manual_candidate" and sid in manual_repairs:
            manual = manual_repairs[sid]
            decision = dict(decision)
            decision["candidate_modern_text"] = manual["modern_text"]
            decision["candidate_uncertainty"] = manual.get("uncertainty") or []
        source = source_map.get(sid)
        current = current_map.get(sid)
        if source is None or current is None:
            reasons = ["missing_current_source_or_result"]
            quality_and_errors: dict[str, Any] = {}
        else:
            quality_and_errors, reasons = validate_candidate(decision, source, current)
        if reasons:
            report["skipped_or_rejected"] += 1
            reason_counts.update(reasons)
            continue
        assert source is not None and current is not None
        new_row = dict(current)
        new_row.update(
            {
                "modern_text": quality_and_errors["modern_text"],
                "judge_verdict": "accept",
                "model_judge_verdict": "accept",
                "judge_confidence": (decision.get("pairwise_judge") or {}).get("confidence"),
                "judge_issues": [],
                "local_issues": [],
                "issues": [],
                "uncertainty": list(
                    dict.fromkeys(
                        (current.get("uncertainty") or [])
                        + (decision.get("candidate_uncertainty") or [])
                        + ((decision.get("pairwise_judge") or {}).get("uncertainty") or [])
                    )
                ),
                **quality_and_errors["quality"],
                "second_pass_applied": True,
                "second_pass_candidate_path": str(CANDIDATES / f"book{int(current['book_no']):03d}.jsonl"),
                "second_pass_judge_model": (decision.get("pairwise_judge") or {}).get("model")
                or decision.get("judge_model"),
                "second_pass_previous_result_generated_at": current.get("generated_at"),
                "generated_at": m["now_iso"](),
            }
        )
        output_rows.append(new_row)

    report["rejection_reasons"] = dict(reason_counts)
    if not args.apply:
        report["eligible_to_append"] = len(output_rows)
        write_json(APPLY_REPORT_PATH, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    for row in output_rows:
        result_path = RESULTS / f"book{int(row['book_no']):03d}.jsonl"
        append_result(result_path, row)
        report["appended"] += 1
    report["status"] = "completed" if not reason_counts else "completed_with_rejections"
    report["completed_at"] = m["now_iso"]()
    write_json(APPLY_REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
