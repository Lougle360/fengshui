#!/usr/bin/env python3
"""Fair, budgeted benchmark for configured V3 writer routes.

Without --confirm-paid-benchmark this command is strictly offline and only
prints the planned calls. API keys remain in process environment variables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PIPELINE = Path(__file__).with_name("v3_pipeline.py")
m = runpy.run_path(str(PIPELINE), run_name="v3_provider_benchmark")
V3: Path = m["V3"]
REPORTS: Path = m["REPORTS"]
SAMPLE_PATH = REPORTS / "V3多供应商基准样本.jsonl"
EXTERNAL_LEDGER = REPORTS / "V3外部API费用台账.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def external_cost_total() -> float:
    if not EXTERNAL_LEDGER.exists():
        return 0.0
    return round(
        sum(float(row.get("estimated_cost_rmb") or 0.0) for row in read_jsonl(EXTERNAL_LEDGER)),
        6,
    )


def append_ledger(row: dict[str, Any]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    with EXTERNAL_LEDGER.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def atomic_json(path: Path, data: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp.replace(path)


def writer_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    glossary = m["load_glossary"]()
    return {
        "book_no": "provider_benchmark",
        "items": [
            {
                "id": row["id"],
                "language_hint": row["language_hint"],
                "kind": row["kind"],
                "locked_terms": row.get("locked_terms") or [],
                "opaque_terms": row.get("opaque_terms") or [],
                "allowed_glossary": m["allowed_glossary_for"](
                    row.get("locked_terms") or [], glossary
                ),
                "source": row["source"],
            }
            for row in rows
        ],
    }


def sample_batches(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return list(
        m["batches"](
            rows,
            min(int(m["MAX_BATCH_CHARS"]), 1800),
            min(int(m["MAX_BATCH_ITEMS"]), 12),
        )
    )


def safe_route(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": route["provider"],
        "api_url": route["api_url"],
        "api_key_env": route["api_key_env"],
        "remote_model": route["remote_model"],
        "max_concurrent_requests": route["max_concurrent_requests"],
        "max_concurrent_model_requests": route["max_concurrent_model_requests"],
        "stream": route["stream"],
        "prices": route.get("prices") or m["PRICE"].get(m["WRITER_MODEL"], {}),
    }


def conservative_call_reserve(
    route: dict[str, Any], payload: dict[str, Any], max_tokens: int
) -> float:
    prompt = m["WRITER_SYSTEM"] + json.dumps(payload, ensure_ascii=False)
    usage = {
        # UTF-8 bytes deliberately overestimate tokens for budget safety.
        "prompt_tokens": len(prompt.encode("utf-8")),
        "completion_tokens": max_tokens,
        "cached_prompt_tokens": 0,
    }
    return m["estimate_cost"](
        m["WRITER_MODEL"], usage, route=route
    )


def evaluate_items(
    source_rows: list[dict[str, Any]], response: Any
) -> tuple[list[dict[str, Any]], int]:
    glossary = m["load_glossary"]()
    returned = {
        item.get("id"): item
        for item in m["normalize_items"](response)
        if isinstance(item, dict) and item.get("id")
    }
    details: list[dict[str, Any]] = []
    hard_failures = 0
    for source in source_rows:
        candidate = returned.get(source["id"])
        if not candidate:
            hard_failures += 1
            details.append({"id": source["id"], "missing": True, "issues": ["模型漏回结果"]})
            continue
        issues = m["local_quality_issues"](
            source["source"],
            str(candidate.get("modern_text") or ""),
            candidate.get("language"),
            source.get("locked_terms") or [],
            m["allowed_glossary_for"](source.get("locked_terms") or [], glossary),
            source.get("opaque_terms") or [],
        )
        messages = m["hard_issue_messages"](issues)
        if messages:
            hard_failures += 1
        details.append(
            {
                "id": source["id"],
                "language": candidate.get("language"),
                "confidence": candidate.get("confidence"),
                "modern_text": candidate.get("modern_text"),
                "uncertainty": candidate.get("uncertainty") or [],
                "hard_issues": messages,
            }
        )
    return details, hard_failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-count", type=int, default=12)
    parser.add_argument("--max-cost-rmb", type=float, default=3.0)
    parser.add_argument("--confirm-paid-benchmark", action="store_true")
    args = parser.parse_args()

    if not SAMPLE_PATH.exists():
        raise RuntimeError("缺少固定基准样本；请先运行 build_v3_provider_benchmark_sample.py")
    samples = read_jsonl(SAMPLE_PATH)[: max(1, min(args.sample_count, 36))]
    batches = sample_batches(samples)
    routes = m["MODEL_ROUTES"].get(m["WRITER_MODEL"]) or [
        m["normalize_model_route"](m["WRITER_MODEL"], {})
    ]
    plan = {
        "generated_at": now_iso(),
        "mode": "paid" if args.confirm_paid_benchmark else "offline_plan",
        "logical_model": m["WRITER_MODEL"],
        "sample_count": len(samples),
        "batch_count_per_route": len(batches),
        "routes": [safe_route(route) for route in routes],
        "max_cost_rmb": args.max_cost_rmb,
        "production_cost_before_rmb": float(
            m["load_state"]()["usage"].get("estimated_cost_rmb") or 0.0
        ),
        "external_cost_before_rmb": external_cost_total(),
    }
    if not args.confirm_paid_benchmark:
        plan["status"] = "ready_requires_explicit_paid_confirmation"
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    m["ensure_api_keys"](False)
    if plan["production_cost_before_rmb"] + plan["external_cost_before_rmb"] + args.max_cost_rmb > float(m["MAX_BUDGET_RMB"]):
        raise RuntimeError("基准预算会侵占人民币 150 元总上限，已拒绝启动")

    benchmark_cost = 0.0
    route_results: list[dict[str, Any]] = []
    max_tokens = 6000
    for route in routes:
        started = time.perf_counter()
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "cached_prompt_tokens": 0}
        all_details: list[dict[str, Any]] = []
        route_hard_failures = 0
        route_error: str | None = None
        completed_items = 0
        try:
            for batch in batches:
                payload = writer_payload(batch)
                reserve = conservative_call_reserve(route, payload, max_tokens)
                if benchmark_cost + reserve > args.max_cost_rmb:
                    raise RuntimeError("基准测试费用安全预估将超过本次上限")
                response, usage = m["request_json"](
                    m["WRITER_MODEL"],
                    m["WRITER_SYSTEM"],
                    payload,
                    max_tokens=max_tokens,
                    route=route,
                )
                actual_cost = m["estimate_cost"](
                    m["WRITER_MODEL"], usage, route=route
                )
                benchmark_cost = round(benchmark_cost + actual_cost, 6)
                append_ledger(
                    {
                        "recorded_at": now_iso(),
                        "purpose": "v3_provider_benchmark",
                        "provider": route["provider"],
                        "logical_model": m["WRITER_MODEL"],
                        "remote_model": route["remote_model"],
                        "request_sha256": hashlib.sha256(
                            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                        ).hexdigest(),
                        "usage": usage,
                        "estimated_cost_rmb": round(actual_cost, 6),
                    }
                )
                for key in usage_total:
                    usage_total[key] += int(usage.get(key) or 0)
                details, hard_failures = evaluate_items(batch, response)
                all_details.extend(details)
                route_hard_failures += hard_failures
                completed_items += len(batch)
        except Exception as exc:
            route_error = str(exc)
        elapsed = max(time.perf_counter() - started, 0.000001)
        route_results.append(
            {
                "route": safe_route(route),
                "status": "passed_technical_gate" if not route_error and route_hard_failures == 0 else "needs_review",
                "elapsed_seconds": round(elapsed, 3),
                "completed_items": completed_items,
                "items_per_minute": round(completed_items / elapsed * 60, 3),
                "source_characters_per_second": round(
                    sum(len(row["source"]) for row in samples[:completed_items]) / elapsed, 3
                ),
                "hard_failure_count": route_hard_failures,
                "hard_failure_rate": round(route_hard_failures / max(completed_items, 1), 4),
                "usage": usage_total,
                "error": route_error,
                "items": all_details,
            }
        )

    report = {
        **plan,
        "status": "completed",
        "completed_at": now_iso(),
        "benchmark_cost_rmb": benchmark_cost,
        "routes_tested": len(route_results),
        "results": route_results,
        "note": "本地硬门只验证结构与确定性错误；正式接入仍需独立语义裁判。",
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS / f"V3多供应商基准结果-{stamp}.json"
    atomic_json(report_path, report)
    print(json.dumps({**report, "results": [{k: v for k, v in row.items() if k != "items"} for row in route_results], "report_path": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
