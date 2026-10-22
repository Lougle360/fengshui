#!/usr/bin/env python3
"""Checkpoint-safe V3 second-pass candidate generation.

The first pass remains immutable. Approved changes are written to a separate
candidate ledger and require a later hard-verified apply step. Paid execution
is refused while the first-pass background PID is alive.
"""

from __future__ import annotations

import argparse
import json
import os
import runpy
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PIPELINE = Path(__file__).with_name("v3_pipeline.py")
m = runpy.run_path(str(PIPELINE), run_name="v3_second_pass_runner")
V3: Path = m["V3"]
WORK: Path = m["WORK"]
REPORTS: Path = m["REPORTS"]
SEGMENTS: Path = m["SEGMENTS"]
RESULTS: Path = m["RESULTS"]
SECOND_PASS = WORK / "second_pass"
QUEUE_PATH = Path(os.getenv("V3_SECOND_PASS_QUEUE_PATH", str(SECOND_PASS / "V3二次自动裁决队列.jsonl")))
CANDIDATES = Path(os.getenv("V3_SECOND_PASS_CANDIDATES_DIR", str(SECOND_PASS / "candidates")))
DECISIONS_PATH = Path(os.getenv("V3_SECOND_PASS_DECISIONS_PATH", str(SECOND_PASS / "V3二次自动裁决决策.jsonl")))
STATE_PATH = Path(os.getenv("V3_SECOND_PASS_STATE_PATH", str(REPORTS / "V3二次自动裁决运行状态.json")))
MANUAL_REPAIRS_PATH = (
    V3.parent.parent
    / "output"
    / "V4"
    / "001-青囊海角经"
    / "40-modernized"
    / "manual-repairs.jsonl"
)

SECOND_PASS_REPAIR_MODEL = os.getenv(
    "V3_SECOND_PASS_REPAIR_MODEL", m["ESCALATION_MODEL"]
)
SECOND_PASS_JUDGE_MODEL = os.getenv(
    "V3_SECOND_PASS_JUDGE_MODEL", m["JUDGE_MODEL"]
)

PAIRWISE_JUDGE_SYSTEM = """你是独立的古籍与风水术数终审裁判。输入含 source、current 和 candidate。逐句核对原文，比较两版谁更准确、完整、通俗、保守。专业术语、数字、干支、卦象、方位、书名和口诀不得擅改；不得接受无原文依据的解释；原文损坏时允许明确保留存疑。你绝不能改稿，只能裁决。只有 candidate 明确优于 current，且 candidate 本身可以直接出版时，winner 才能为 candidate。两版各有得失或证据不足时必须选 uncertain；current 更稳妥时选 current。只输出 JSON 对象：{"items":[{"id":"...","winner":"current|candidate|uncertain","candidate_verdict":"accept|revise|uncertain","confidence":"high|medium|low","issues":["..."],"uncertainty":["..."]}]}。"""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def latest_by_id(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in read_jsonl(path):
            if row.get("id"):
                latest[row["id"]] = row
    return latest


def queue_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("id") or ""), str(row.get("source_sha256") or "")


def first_pass_alive() -> tuple[bool, int]:
    path = REPORTS / "V3后台进程.json"
    if not path.exists():
        return False, 0
    record = json.loads(path.read_text(encoding="utf-8"))
    pid = int(record.get("pid") or 0)
    return bool(m["pid_is_alive"](pid)), pid


def candidate_is_approvable(
    decision: dict[str, Any], local_issues: list[str]
) -> bool:
    return bool(
        decision.get("winner") == "candidate"
        and decision.get("candidate_verdict") == "accept"
        and decision.get("confidence") in {"high", "medium"}
        and not local_issues
    )


def queue_batches(
    rows: list[dict[str, Any]], max_chars: int = 1800, max_items: int = 10
) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    size = 0
    for row in rows:
        row_size = len(str(row.get("source") or ""))
        if batch and (size + row_size > max_chars or len(batch) >= max_items):
            yield batch
            batch = []
            size = 0
        batch.append(row)
        size += row_size
    if batch:
        yield batch


def segment_context_maps() -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, str]]
]:
    segment_map: dict[str, dict[str, Any]] = {}
    context_map: dict[str, dict[str, str]] = {}
    for path in sorted(SEGMENTS.glob("book*.jsonl")):
        rows = read_jsonl(path)
        segment_map.update({row["id"]: row for row in rows})
        context_map.update(m["build_short_segment_contexts"](rows))
    return segment_map, context_map


def atomic_state(data: dict[str, Any]) -> None:
    m["atomic_json"](STATE_PATH, data)


def append_decision(row: dict[str, Any]) -> None:
    m["append_jsonl"](DECISIONS_PATH, row)
    book_no = int(row["book_no"])
    m["append_jsonl"](CANDIDATES / f"book{book_no:03d}.jsonl", row)


def technical_check(
    source: dict[str, Any], current: dict[str, Any], modern_text: str
) -> tuple[dict[str, Any], list[str]]:
    glossary = m["load_glossary"]()
    check = m["local_quality_issues"](
        source["source"],
        modern_text,
        current.get("language"),
        source.get("locked_terms") or [],
        m["allowed_glossary_for"](source.get("locked_terms") or [], glossary),
        source.get("opaque_terms") or [],
    )
    return check, m["hard_issue_messages"](check)


def repair_payload(
    batch: list[dict[str, Any]],
    segment_map: dict[str, dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
    context_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    glossary = m["load_glossary"]()
    return {
        "book_no": "second_pass",
        "repair_phase": "independent_second_pass",
        "items": [
            {
                "id": row["id"],
                "kind": segment_map[row["id"]].get("kind"),
                "source": segment_map[row["id"]]["source"],
                "candidate": current_map[row["id"]]["modern_text"],
                "issues": row.get("issues") or current_map[row["id"]].get("issues") or [],
                "locked_terms": segment_map[row["id"]].get("locked_terms") or [],
                "opaque_terms": segment_map[row["id"]].get("opaque_terms") or [],
                "allowed_glossary": m["allowed_glossary_for"](
                    segment_map[row["id"]].get("locked_terms") or [], glossary
                ),
                **context_map.get(row["id"], {}),
            }
            for row in batch
        ],
    }


def pairwise_payload(
    batch: list[dict[str, Any]],
    segment_map: dict[str, dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
    repaired_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    glossary = m["load_glossary"]()
    return {
        "book_no": "second_pass_pairwise",
        "items": [
            {
                "id": row["id"],
                "source": segment_map[row["id"]]["source"],
                "kind": segment_map[row["id"]].get("kind"),
                "current": current_map[row["id"]]["modern_text"],
                "candidate": repaired_map[row["id"]].get("modern_text") or "",
                "locked_terms": segment_map[row["id"]].get("locked_terms") or [],
                "opaque_terms": segment_map[row["id"]].get("opaque_terms") or [],
                "allowed_glossary": m["allowed_glossary_for"](
                    segment_map[row["id"]].get("locked_terms") or [], glossary
                ),
            }
            for row in batch
        ],
    }


def current_judge_payload(
    batch: list[dict[str, Any]],
    segment_map: dict[str, dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    glossary = m["load_glossary"]()
    return {
        "book_no": "second_pass_rejudge",
        "items": [
            {
                "id": row["id"],
                "source": segment_map[row["id"]]["source"],
                "kind": segment_map[row["id"]].get("kind"),
                "candidate": current_map[row["id"]]["modern_text"],
                "locked_terms": segment_map[row["id"]].get("locked_terms") or [],
                "opaque_terms": segment_map[row["id"]].get("opaque_terms") or [],
                "allowed_glossary": m["allowed_glossary_for"](
                    segment_map[row["id"]].get("locked_terms") or [], glossary
                ),
                "writer_confidence": current_map[row["id"]].get("writer_confidence"),
                "writer_uncertainty": current_map[row["id"]].get("uncertainty") or [],
            }
            for row in batch
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--prompt-key", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if not QUEUE_PATH.exists():
        raise RuntimeError("缺少二次自动裁决队列")
    queue = read_jsonl(QUEUE_PATH)
    if args.limit is not None:
        queue = queue[: max(0, args.limit)]
    decisions_by_id = latest_by_id([DECISIONS_PATH])
    decided_keys = {
        queue_key(row)
        for row in read_jsonl(DECISIONS_PATH)
        if row.get("status") in {
            "second_pass_preserved",
            "second_pass_judged",
            "second_pass_rejudged",
        }
    }
    pending = [row for row in queue if queue_key(row) not in decided_keys]
    counts = Counter(row["priority"] for row in pending)
    plan = {
        "generated_at": m["now_iso"](),
        "status": "ready" if not args.execute else "starting",
        "queue_snapshot": len(queue),
        "already_decided": len(decided_keys),
        "decision_ids_latest": len(decisions_by_id),
        "pending": len(pending),
        "pending_by_priority": dict(counts),
        "repair_model": SECOND_PASS_REPAIR_MODEL,
        "judge_model": SECOND_PASS_JUDGE_MODEL,
        "first_pass_immutable": True,
        "candidate_output": str(CANDIDATES),
    }
    if not args.execute:
        atomic_state(plan)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    alive, pid = first_pass_alive()
    if alive:
        raise RuntimeError(
            f"首轮后台进程 PID={pid} 仍在运行；为避免费用状态和结果文件竞争，拒绝并发执行二次裁决。"
        )
    m["ensure_api_keys"](args.prompt_key)
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    segment_map, context_map = segment_context_maps()
    current_map = latest_by_id(sorted(RESULTS.glob("book*.jsonl")))
    valid_pending = [
        row for row in pending
        if row["id"] in segment_map
        and row["id"] in current_map
        and segment_map[row["id"]].get("source_sha256") == row.get("source_sha256")
        and current_map[row["id"]].get("source_sha256") == row.get("source_sha256")
    ]
    valid_keys = {queue_key(row) for row in valid_pending}
    stale_queue_items = [
        {
            "id": row.get("id"),
            "source_sha256": row.get("source_sha256"),
            "segment_present": row.get("id") in segment_map,
            "result_present": row.get("id") in current_map,
            "segment_hash_matches": (
                row.get("id") in segment_map
                and segment_map[row["id"]].get("source_sha256") == row.get("source_sha256")
            ),
            "result_hash_matches": (
                row.get("id") in current_map
                and current_map[row["id"]].get("source_sha256") == row.get("source_sha256")
            ),
        }
        for row in pending
        if queue_key(row) not in valid_keys
    ]
    state = m["load_state"]()
    processed = 0
    approved = 0
    decisions = Counter()

    # Reuse issue-directed human repairs that were already accepted in the V4
    # workspace. This avoids repeatedly charging for the same reviewed segment
    # while keeping the decision in the same immutable second-pass ledger.
    manual_repairs = {
        row["v3_segment_id"]: row
        for row in read_jsonl(MANUAL_REPAIRS_PATH)
        if row.get("v3_segment_id")
        and row.get("review_status") == "accepted_after_issue_directed_repair"
    }
    for row in [r for r in valid_pending if r["id"] in manual_repairs]:
        manual = manual_repairs[row["id"]]
        decision = {
            **row,
            "status": "second_pass_judged",
            "decision": "approve_manual_candidate",
            "approved_for_apply": True,
            "candidate_modern_text": manual["modern_text"],
            "candidate_confidence": "medium",
            "candidate_uncertainty": manual.get("uncertainty") or [],
            "manual_review_status": manual["review_status"],
            "manual_review_rationale": manual.get("rationale") or "",
            "decided_at": m["now_iso"](),
        }
        append_decision(decision)
        processed += 1
        approved += 1
        decisions[decision["decision"]] += 1

    # Low-risk transparent uncertainties are intentionally preserved without a
    # paid rewrite. They remain visible in the final uncertainty ledger.
    for row in [r for r in valid_pending if r["priority"] == "low"]:
        decision = {
            **row,
            "status": "second_pass_preserved",
            "decision": "keep_current_transparent_uncertainty",
            "approved_for_apply": False,
            "decided_at": m["now_iso"](),
        }
        append_decision(decision)
        processed += 1
        decisions[decision["decision"]] += 1

    high_rows = [
        r
        for r in valid_pending
        if r["priority"] == "high" and r["id"] not in manual_repairs
    ]
    for batch in queue_batches(high_rows):
        repair = m["request_json_cached"](
            state,
            SECOND_PASS_REPAIR_MODEL,
            m["REPAIR_SYSTEM"],
            repair_payload(batch, segment_map, current_map, context_map),
        )
        repaired_map = {item["id"]: item for item in m["normalize_items"](repair)}
        missing = [row["id"] for row in batch if row["id"] not in repaired_map]
        if missing:
            raise RuntimeError("二次修复模型漏回：" + "、".join(missing))
        judged = m["request_json_cached"](
            state,
            SECOND_PASS_JUDGE_MODEL,
            PAIRWISE_JUDGE_SYSTEM,
            pairwise_payload(batch, segment_map, current_map, repaired_map),
        )
        judge_map = {item["id"]: item for item in m["normalize_items"](judged)}
        missing = [row["id"] for row in batch if row["id"] not in judge_map]
        if missing:
            raise RuntimeError("二次终审模型漏回：" + "、".join(missing))
        for row in batch:
            sid = row["id"]
            source = segment_map[sid]
            current = current_map[sid]
            repaired = repaired_map[sid]
            final_text = str(repaired.get("modern_text") or "")
            check, local_issues = technical_check(source, current, final_text)
            judge = judge_map[sid]
            approvable = candidate_is_approvable(judge, local_issues)
            decision_name = "approve_candidate" if approvable else "keep_current"
            decision = {
                **row,
                "status": "second_pass_judged",
                "decision": decision_name,
                "approved_for_apply": approvable,
                "candidate_modern_text": final_text,
                "candidate_confidence": repaired.get("confidence"),
                "candidate_uncertainty": repaired.get("uncertainty") or [],
                "pairwise_judge": judge,
                "candidate_local_issues": local_issues,
                "candidate_quality_check": check,
                "current_result_generated_at": current.get("generated_at"),
                "repair_model": SECOND_PASS_REPAIR_MODEL,
                "judge_model": SECOND_PASS_JUDGE_MODEL,
                "decided_at": m["now_iso"](),
            }
            append_decision(decision)
            processed += 1
            approved += int(approvable)
            decisions[decision_name] += 1
        atomic_state({**plan, "status": "running", "processed": processed, "approved": approved, "decisions": dict(decisions), "updated_at": m["now_iso"]()})

    medium_rows = [r for r in valid_pending if r["priority"] == "medium"]
    for batch in queue_batches(medium_rows):
        judged = m["request_json_cached"](
            state,
            SECOND_PASS_JUDGE_MODEL,
            m["JUDGE_SYSTEM"],
            current_judge_payload(batch, segment_map, current_map),
        )
        judge_map = {item["id"]: item for item in m["normalize_items"](judged)}
        for row in batch:
            sid = row["id"]
            judge = judge_map.get(sid) or {
                "verdict": "uncertain",
                "confidence": "low",
                "issues": ["复核模型漏回结果"],
                "uncertainty": [],
            }
            decision_name = (
                "reconfirmed_current"
                if judge.get("verdict") == "accept"
                else "keep_current_source_uncertain"
            )
            decision = {
                **row,
                "status": "second_pass_rejudged",
                "decision": decision_name,
                "approved_for_apply": False,
                "independent_rejudge": judge,
                "judge_model": SECOND_PASS_JUDGE_MODEL,
                "decided_at": m["now_iso"](),
            }
            append_decision(decision)
            processed += 1
            decisions[decision_name] += 1

    final = {
        **plan,
        "status": "completed" if not stale_queue_items else "needs_source_reconciliation",
        "valid_pending": len(valid_pending),
        "stale_queue_items": stale_queue_items,
        "processed": processed,
        "approved_candidates": approved,
        "decisions": dict(decisions),
        "completed_at": m["now_iso"](),
    }
    atomic_state(final)
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
