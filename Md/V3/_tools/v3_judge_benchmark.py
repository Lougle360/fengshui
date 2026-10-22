#!/usr/bin/env python3
"""Compare a lower-cost independent judge with cached DeepSeek decisions.

This tool never changes translation result files. It rebuilds the exact initial
judge payloads from cached writer responses, calls the candidate judge, and
records false-accept/false-reject differences for a cost and quality decision.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
from pathlib import Path

import v3_pipeline as p


def cache_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(p.API_CACHE.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        row["_path"] = str(path)
        rows.append(row)
    return rows


def item_ids(response: object) -> set[str]:
    try:
        return {str(item["id"]) for item in p.normalize_items(response)}
    except Exception:
        return set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="stepfun-ai/Step-3.5-Flash")
    parser.add_argument("--input-price", type=float, default=0.7)
    parser.add_argument("--output-price", type=float, default=2.1)
    parser.add_argument("--batches", type=int, default=2)
    parser.add_argument("--prompt-key", action="store_true")
    args = parser.parse_args()

    if args.prompt_key:
        os.environ["SILICONFLOW_API_KEY"] = getpass.getpass(
            "SILICONFLOW_API_KEY（隐藏输入，不写入文件）："
        ).strip()
    if not os.getenv("SILICONFLOW_API_KEY"):
        raise RuntimeError("缺少 SILICONFLOW_API_KEY")

    p.PRICE[args.model] = {"input": args.input_price, "output": args.output_price}
    state = p.load_state()
    glossary = p.load_glossary()
    segments = {
        row["id"]: row
        for path in sorted(p.SEGMENTS.glob("book*.jsonl"))
        for row in p.read_jsonl(path)
    }
    caches = cache_rows()
    writer_rows = [row for row in caches if row.get("model") == p.WRITER_MODEL]
    reference_rows = [row for row in caches if row.get("model") == p.JUDGE_MODEL]

    selected: list[tuple[dict, dict]] = []
    for writer in writer_rows:
        ids = item_ids(writer.get("response"))
        if not ids:
            continue
        reference = next(
            (row for row in reference_rows if item_ids(row.get("response")) == ids),
            None,
        )
        if reference is not None:
            selected.append((writer, reference))
        if len(selected) >= args.batches:
            break
    if not selected:
        raise RuntimeError("没有找到可复现的写作/DeepSeek 初审缓存对")

    report_batches: list[dict] = []
    total_reference_nonaccept: set[str] = set()
    total_candidate_nonaccept: set[str] = set()
    total_missed: set[str] = set()
    total_extra: set[str] = set()
    candidate_cost = 0.0

    for writer_cache, reference_cache in selected:
        writer_items = {
            item["id"]: item for item in p.normalize_items(writer_cache["response"])
        }
        ids = list(writer_items)
        source_rows = [segments[sid] for sid in ids]
        book_numbers = {int(row["book_no"]) for row in source_rows}
        if len(book_numbers) != 1:
            raise RuntimeError("缓存批次跨书，无法构建核义请求")
        payload = {
            "book_no": next(iter(book_numbers)),
            "items": [
                {
                    "id": row["id"],
                    "source": row["source"],
                    "kind": row.get("kind"),
                    "candidate": writer_items[row["id"]].get("modern_text", ""),
                    "locked_terms": row.get("locked_terms") or [],
                    "opaque_terms": row.get("opaque_terms") or [],
                    "allowed_glossary": p.allowed_glossary_for(
                        row.get("locked_terms") or [], glossary
                    ),
                    "writer_confidence": writer_items[row["id"]].get("confidence"),
                    "writer_uncertainty": writer_items[row["id"]].get("uncertainty", []),
                }
                for row in source_rows
            ],
        }

        before = float(state["usage"]["estimated_cost_rmb"])
        candidate = p.request_json_cached(
            state, args.model, p.JUDGE_SYSTEM, payload, max_tokens=10000
        )
        after = float(state["usage"]["estimated_cost_rmb"])
        candidate_cost += after - before

        reference_items = {
            item["id"]: item
            for item in p.normalize_items(reference_cache["response"])
        }
        candidate_items = {
            item["id"]: item for item in p.normalize_items(candidate)
        }
        reference_nonaccept = {
            sid
            for sid in ids
            if reference_items[sid].get("verdict", "uncertain") != "accept"
        }
        candidate_nonaccept = {
            sid
            for sid in ids
            if candidate_items[sid].get("verdict", "uncertain") != "accept"
        }
        missed = reference_nonaccept - candidate_nonaccept
        extra = candidate_nonaccept - reference_nonaccept
        total_reference_nonaccept.update(reference_nonaccept)
        total_candidate_nonaccept.update(candidate_nonaccept)
        total_missed.update(missed)
        total_extra.update(extra)
        report_batches.append(
            {
                "items": len(ids),
                "source_characters": sum(len(segments[sid]["source"]) for sid in ids),
                "reference_nonaccept": sorted(reference_nonaccept),
                "candidate_nonaccept": sorted(candidate_nonaccept),
                "missed_reference_nonaccept": sorted(missed),
                "extra_candidate_nonaccept": sorted(extra),
            }
        )

    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.model)
    report = {
        "generated_at": p.now_iso(),
        "candidate_model": args.model,
        "reference_model": p.JUDGE_MODEL,
        "batches": report_batches,
        "summary": {
            "batches": len(report_batches),
            "items": sum(row["items"] for row in report_batches),
            "source_characters": sum(
                row["source_characters"] for row in report_batches
            ),
            "reference_nonaccept": len(total_reference_nonaccept),
            "candidate_nonaccept": len(total_candidate_nonaccept),
            "missed_reference_nonaccept": len(total_missed),
            "extra_candidate_nonaccept": len(total_extra),
            "candidate_estimated_cost_rmb": round(candidate_cost, 6),
        },
        "decision_rule": (
            "候选裁判不得漏放 DeepSeek 已判非接受项；若有漏放，不得直接替换主裁判。"
        ),
    }
    p.atomic_json(p.REPORTS / f"V3裁判模型基准-{safe_model}.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
