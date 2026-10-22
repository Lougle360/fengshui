from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load_pipeline():
    spec = importlib.util.spec_from_file_location("v3_pipeline", HERE / "v3_pipeline.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 v3_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_issue(message: str) -> str:
    return message.split("：", 1)[0].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True, help="ISO 8601 起始时间")
    parser.add_argument(
        "--sample-details",
        action="store_true",
        help="输出每类样本的原文、初稿和最终文本，便于离线定位规则问题",
    )
    args = parser.parse_args()
    since = parse_time(args.since)
    pipeline = load_pipeline()
    glossary = pipeline.load_glossary()

    segments: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "_work" / "segments").glob("book*.jsonl")):
        for row in read_jsonl(path):
            segments[row["id"]] = row
    for path in sorted((ROOT / "_work" / "results").glob("book*.jsonl")):
        for row in read_jsonl(path):
            segment = segments.get(row.get("id"))
            if (
                row.get("status") == "judged"
                and segment
                and row.get("source_sha256") == segment.get("source_sha256")
            ):
                results[row["id"]] = row

    cache_by_hash: dict[str, tuple[int, dict[str, Any]]] = {}
    for path in (ROOT / "_work" / "api_cache").glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if parse_time(row["created_at"]) < since:
                continue
        except (KeyError, ValueError, json.JSONDecodeError):
            continue
        key = row.get("request_sha256") or path.stem.removesuffix(".partial")
        rank = 1 if path.name.endswith(".partial.json") else 2
        if key not in cache_by_hash or rank > cache_by_hash[key][0]:
            cache_by_hash[key] = (rank, row)

    writer_items: dict[str, dict[str, Any]] = {}
    for _, cache in cache_by_hash.values():
        if cache.get("model") != pipeline.WRITER_MODEL:
            continue
        for item in (cache.get("response") or {}).get("items") or []:
            if item.get("id") in segments:
                writer_items[item["id"]] = item

    counts = Counter()
    issue_counts = Counter()
    hard_by_kind = Counter()
    hard_by_length = Counter()
    copy_shape = Counter()
    local_hard_chars = 0
    semantic_only_chars = 0
    clean_chars = 0
    sample_ids: dict[str, list[str]] = {
        "local_hard": [],
        "semantic_only": [],
        "clean": [],
    }

    for sid, writer in writer_items.items():
        source = segments[sid]
        final = results.get(sid)
        counts["writer_items"] += 1
        source_chars = len(source.get("source") or "")
        allowed = pipeline.allowed_glossary_for(source.get("locked_terms") or [], glossary)
        check = pipeline.local_quality_issues(
            source.get("source") or "",
            writer.get("modern_text") or "",
            writer.get("language"),
            source.get("locked_terms") or [],
            allowed,
            source.get("opaque_terms") or [],
        )
        hard = pipeline.hard_issue_messages(check)
        if hard:
            counts["initial_local_hard"] += 1
            local_hard_chars += source_chars
            hard_by_kind[source.get("kind") or "unknown"] += 1
            if source_chars < 40:
                hard_by_length["lt_40"] += 1
            elif source_chars < 120:
                hard_by_length["40_119"] += 1
            elif source_chars < 300:
                hard_by_length["120_299"] += 1
            else:
                hard_by_length["gte_300"] += 1
            compact_source = pipeline.compact_text(source.get("source") or "")
            compact_initial = pipeline.compact_text(writer.get("modern_text") or "")
            if compact_initial == compact_source:
                copy_shape["exact_after_compaction"] += 1
            elif compact_source and compact_source in compact_initial:
                copy_shape["source_plus_other_text"] += 1
            elif check.get("insufficient_modernization"):
                copy_shape["near_copy"] += 1
            else:
                copy_shape["other_hard_issue"] += 1
            for message in hard:
                issue_counts[normalize_issue(message)] += 1
            if len(sample_ids["local_hard"]) < 10:
                sample_ids["local_hard"].append(sid)
        else:
            counts["initial_local_clean"] += 1

        if final:
            counts["has_final_result"] += 1
            repaired = int(final.get("repair_rounds") or 0) > 0
            if repaired:
                counts["final_repaired"] += 1
                if hard:
                    counts["repair_with_initial_local_hard"] += 1
                else:
                    counts["semantic_only_repair"] += 1
                    semantic_only_chars += source_chars
                    if len(sample_ids["semantic_only"]) < 10:
                        sample_ids["semantic_only"].append(sid)
            else:
                counts["final_not_repaired"] += 1
                clean_chars += source_chars
                if len(sample_ids["clean"]) < 10:
                    sample_ids["clean"].append(sid)
            counts[f"initial_judge_{final.get('initial_judge_verdict') or 'none'}"] += 1

    writer_total = counts["writer_items"] or 1
    final_total = counts["has_final_result"] or 1
    report = {
        "since": since.isoformat(),
        "writer_model": pipeline.WRITER_MODEL,
        "writer_items": counts["writer_items"],
        "writer_items_with_final_result": counts["has_final_result"],
        "initial_local_hard": counts["initial_local_hard"],
        "initial_local_hard_rate": round(counts["initial_local_hard"] / writer_total, 4),
        "final_repaired": counts["final_repaired"],
        "final_repair_rate": round(counts["final_repaired"] / final_total, 4),
        "repair_with_initial_local_hard": counts["repair_with_initial_local_hard"],
        "semantic_only_repair": counts["semantic_only_repair"],
        "semantic_only_repair_rate": round(counts["semantic_only_repair"] / final_total, 4),
        "initial_judge_verdicts": {
            "accept": counts["initial_judge_accept"],
            "revise": counts["initial_judge_revise"],
            "uncertain": counts["initial_judge_uncertain"],
        },
        "source_chars_by_path": {
            "local_hard": local_hard_chars,
            "semantic_only_repair": semantic_only_chars,
            "no_repair": clean_chars,
        },
        "top_initial_local_hard_issues": issue_counts.most_common(20),
        "initial_hard_by_kind": dict(hard_by_kind),
        "initial_hard_by_source_length": dict(hard_by_length),
        "copy_shape": dict(copy_shape),
        "sample_ids": sample_ids,
    }
    if args.sample_details:
        report["sample_details"] = {
            category: [
                {
                    "id": sid,
                    "kind": segments[sid].get("kind"),
                    "language_hint": segments[sid].get("language_hint"),
                    "writer_language": writer_items[sid].get("language"),
                    "source": segments[sid].get("source"),
                    "initial": writer_items[sid].get("modern_text"),
                    "final": (results.get(sid) or {}).get("final_text"),
                }
                for sid in ids
            ]
            for category, ids in sample_ids.items()
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
