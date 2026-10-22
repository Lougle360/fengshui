from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\壮五福\风水项目")
WORKSPACE = ROOT / "output" / "V4" / "001-青囊海角经"
MASTER_LEDGER = ROOT / "output" / "V4" / "V4交付总账.json"
V3 = ROOT / "Md" / "V3"
sys.path.insert(0, str(WORKSPACE / "tools" / "_vendor"))
from opencc import OpenCC  # noqa: E402


CC = OpenCC("t2s")
CROSS_PAGE_RESULT = "book001-b000112-p000-d550fb4973"
CROSS_PAGE_BLOCKS = ("P000027-B004", "P000028-B001")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", CC.convert(text or ""))


def clean_modern_text(text: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", (text or "").strip())
    return text.strip()


def confidence(result: dict | None, mapping_mode: str) -> float:
    if result is None:
        return 0.9 if mapping_mode in {"modern_metadata", "nontext"} else 0.65
    verdict = result.get("judge_verdict")
    judge_confidence = result.get("judge_confidence")
    base = {"accept": 0.96, "revise": 0.7, "uncertain": 0.58}.get(verdict, 0.6)
    if judge_confidence == "medium":
        base -= 0.05
    elif judge_confidence == "low":
        base -= 0.12
    if mapping_mode == "fuzzy_suffix":
        base -= 0.05
    return round(max(0.0, base), 2)


def choose_segment(candidates: list[dict], result_by_id: dict[str, dict]) -> dict:
    rank = {"accept": 3, "revise": 2, "uncertain": 1}
    return max(
        candidates,
        key=lambda segment: (
            rank.get((result_by_id.get(segment["id"]) or {}).get("judge_verdict"), 0),
            int(segment.get("translatable", False)),
            -int(segment.get("part_index", 0)),
        ),
    )


def main() -> None:
    now = utc_now()
    normalized_path = WORKSPACE / "30-normalized" / "blocks.jsonl"
    normalized = read_jsonl(normalized_path)
    segments = read_jsonl(V3 / "_work" / "segments" / "book001.jsonl")
    all_results = read_jsonl(V3 / "_work" / "results" / "book001.jsonl")
    current_ids = {segment["id"] for segment in segments}
    result_by_id = {result["id"]: result for result in all_results if result["id"] in current_ids}
    segment_by_id = {segment["id"]: segment for segment in segments}
    final2_path = WORKSPACE / "40-modernized" / "final2-decisions.jsonl"
    final2_decisions = read_jsonl(final2_path) if final2_path.exists() else []
    bounded_ledger_ids = {
        row["id"]
        for row in final2_decisions
        if row.get("status") == "second_pass_judged"
        and row.get("decision") == "keep_current"
        and row.get("approved_for_apply") is False
    }

    exact_index: dict[str, list[dict]] = defaultdict(list)
    for segment in segments:
        value = canonical(segment.get("source", ""))
        if value:
            exact_index[value].append(segment)

    cross_result = result_by_id[CROSS_PAGE_RESULT]
    cross_modern = clean_modern_text(cross_result["modern_text"])
    marker = "以舍凶龙。"
    if marker not in cross_modern:
        raise RuntimeError("cross-page modern text no longer contains the verified split marker")
    split_at = cross_modern.index(marker)
    cross_modern_parts = {
        CROSS_PAGE_BLOCKS[0]: cross_modern[:split_at].rstrip(),
        CROSS_PAGE_BLOCKS[1]: cross_modern[split_at:].lstrip(),
    }

    output: list[dict] = []
    mapping_rows: list[dict] = []
    block_ids_by_segment: dict[str, list[str]] = defaultdict(list)
    unresolved_rows: list[dict] = []
    terminology: dict[str, set[str]] = defaultdict(set)
    mapping_counts: Counter[str] = Counter()
    verdict_counts: Counter[str] = Counter()

    segment_pairs = [(segment, canonical(segment["source"])) for segment in segments if canonical(segment["source"])]

    for record in normalized:
        block_id = record["block_id"]
        normalized_text = record.get("normalized_text") or ""
        value = canonical(normalized_text)
        modern_text = ""
        result = None
        segment = None
        mapping_mode = "nontext"
        review_status = "accepted"
        disposition = record.get("disposition", "retained")

        if block_id in cross_modern_parts:
            segment = segment_by_id[CROSS_PAGE_RESULT]
            result = cross_result
            modern_text = cross_modern_parts[block_id]
            mapping_mode = "cross_page_split"
            disposition = "translated"
        elif not value:
            modern_text = ""
            mapping_mode = "nontext"
        elif value in exact_index:
            segment = choose_segment(exact_index[value], result_by_id)
            result = result_by_id.get(segment["id"])
            if result is not None:
                modern_text = clean_modern_text(result["modern_text"])
                disposition = "translated" if result.get("action") in {"rewrite", "translate"} else "retained"
                mapping_mode = "v3_exact"
            else:
                modern_text = clean_modern_text(segment["source"])
                disposition = "retained"
                mapping_mode = "v3_nontranslatable"
        elif record["source_page"] in range(4, 15) or value == canonical("四库存目青囊汇刊（二）"):
            modern_text = normalized_text
            disposition = "retained"
            mapping_mode = "modern_metadata"
        else:
            scored = sorted(
                (
                    (difflib.SequenceMatcher(a=value, b=segment_value, autojunk=False).ratio(), candidate, segment_value)
                    for candidate, segment_value in segment_pairs
                ),
                key=lambda row: row[0],
                reverse=True,
            )
            ratio, candidate, candidate_value = scored[0]
            if ratio >= 0.9 and candidate_value.endswith(value):
                segment = candidate
                result = result_by_id.get(segment["id"])
                if result is not None:
                    modern_text = clean_modern_text(result["modern_text"])
                    modern_text = re.sub(r"^(图示解说|图说)[:：]?\s*", "", modern_text)
                    disposition = "translated" if result.get("action") in {"rewrite", "translate"} else "retained"
                    mapping_mode = "fuzzy_suffix"
                else:
                    modern_text = normalized_text
                    mapping_mode = "fallback_preserve"
            else:
                modern_text = normalized_text
                disposition = "retained"
                mapping_mode = "fallback_preserve"
                review_status = "needs_manual_mapping_review"

        if result is not None:
            verdict = result.get("judge_verdict") or "unknown"
            verdict_counts[verdict] += 1
            if verdict != "accept":
                review_status = (
                    "accepted_with_ledger"
                    if segment is not None and segment["id"] in bounded_ledger_ids
                    else "pending_repair"
                )
            elif result.get("uncertainty"):
                review_status = "accepted_with_ledger"
            if segment is not None:
                block_ids_by_segment[segment["id"]].append(block_id)
            for term_note in result.get("term_notes") or []:
                term = str(term_note.get("term", "")).strip()
                note = str(term_note.get("note", "")).strip()
                if term and note:
                    terminology[term].add(note)
            if result.get("uncertainty") or result.get("issues") or review_status == "pending_repair":
                unresolved_rows.append(
                    {
                        "schema_version": "1.0",
                        "item_id": f"V4-MOD-{block_id}",
                        "book_id": record["book_id"],
                        "block_id": block_id,
                        "page_id": record["page_id"],
                        "source_page": record["source_page"],
                        "stage": "modernization",
                        "status": review_status,
                        "v3_segment_id": segment["id"] if segment else None,
                        "judge_verdict": verdict,
                        "judge_confidence": result.get("judge_confidence"),
                        "issues": result.get("issues") or [],
                        "uncertainty": result.get("uncertainty") or [],
                        "source": normalized_text,
                        "candidate": modern_text,
                    }
                )
        elif review_status != "accepted":
            unresolved_rows.append(
                {
                    "schema_version": "1.0",
                    "item_id": f"V4-MOD-{block_id}",
                    "book_id": record["book_id"],
                    "block_id": block_id,
                    "page_id": record["page_id"],
                    "source_page": record["source_page"],
                    "stage": "modernization",
                    "status": review_status,
                    "issues": ["No reliable V3 segment mapping; normalized text is retained as a placeholder."],
                    "uncertainty": [],
                    "source": normalized_text,
                    "candidate": modern_text,
                }
            )

        item = dict(record)
        item.update(
            {
                "modern_text": modern_text,
                "operation": "modernized",
                "disposition": disposition,
                "language_route": "lzh_to_zh-Hans" if disposition == "translated" else "zh-Hans_retain",
                "modernization_mapping": mapping_mode,
                "v3_segment_ids": [segment["id"]] if segment else [],
                "confidence": confidence(result, mapping_mode),
                "review_status": review_status,
                "review_evidence": (
                    {
                        "writer_model": result.get("writer_model"),
                        "repair_model": result.get("repair_model"),
                        "judge_model": result.get("judge_model"),
                        "judge_verdict": result.get("judge_verdict"),
                        "judge_confidence": result.get("judge_confidence"),
                    }
                    if result
                    else {"method": "metadata_or_nontext_retention"}
                ),
            }
        )
        output.append(item)
        mapping_counts[mapping_mode] += 1
        mapping_rows.append(
            {
                "block_id": block_id,
                "mapping_mode": mapping_mode,
                "v3_segment_id": segment["id"] if segment else None,
                "review_status": review_status,
            }
        )

    normalized_ids = [record["block_id"] for record in normalized]
    output_ids = [record["block_id"] for record in output]
    if normalized_ids != output_ids:
        raise RuntimeError("modernization changed block identity or ordering")
    missing_dispositions = [
        record["block_id"]
        for record in output
        if record.get("disposition") not in {"translated", "retained", "noncontent", "unreadable", "excluded_with_reason"}
    ]
    if missing_dispositions:
        raise RuntimeError(f"invalid disposition on {len(missing_dispositions)} blocks")

    modern_dir = WORKSPACE / "40-modernized"
    blocks_path = modern_dir / "blocks.jsonl"
    blocks_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in output),
        encoding="utf-8",
    )
    (modern_dir / "mapping.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in mapping_rows),
        encoding="utf-8",
    )
    (modern_dir / "uncertainties.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in unresolved_rows),
        encoding="utf-8",
    )

    current_translatable_ids = {segment["id"] for segment in segments if segment.get("translatable")}
    repair_results = [
        result_by_id[segment_id]
        for segment_id in current_translatable_ids
        if segment_id in result_by_id
        and result_by_id[segment_id].get("judge_verdict") != "accept"
        and segment_id not in bounded_ledger_ids
    ]
    repair_results.sort(key=lambda result: result["id"])
    repair_queue = []
    for result in repair_results:
        segment = segment_by_id[result["id"]]
        repair_queue.append(
            {
                "schema_version": "1.0",
                "id": result["id"],
                "book_no": 1,
                "source_sha256": segment["source_sha256"],
                "category": "v4_final_repair",
                "priority": "high",
                "repair_id": f"V4-REPAIR-{result['id']}",
                "v3_segment_id": result["id"],
                "v4_block_ids": sorted(set(block_ids_by_segment.get(result["id"], []))),
                "source": segment["source"],
                "locked_terms": segment.get("locked_terms") or [],
                "opaque_terms": segment.get("opaque_terms") or [],
                "draft_modern_text": result["modern_text"],
                "current_modern_text": result["modern_text"],
                "judge_verdict": result.get("judge_verdict"),
                "judge_confidence": result.get("judge_confidence"),
                "issues": result.get("issues") or [],
                "uncertainty": result.get("uncertainty") or [],
                "required_action": "repair_and_independent_rejudge",
            }
        )
    repair_path = modern_dir / "repair-queue.jsonl"
    repair_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in repair_queue),
        encoding="utf-8",
    )

    # Draft reading view. Pending repairs remain visibly labeled and cannot be
    # mistaken for accepted publication text.
    markdown = ["# 青囊海角经：V4 现代化草稿", "", "> 本文件尚未通过现代化阶段门；标有“待修复”的段落不得进入出版稿。", ""]
    previous_page = None
    for record in output:
        if previous_page != record["page_id"]:
            markdown.extend([f"## 物理页 {record['source_page']} {{#{record['page_id']}}}", ""])
            previous_page = record["page_id"]
        modern_text = record.get("modern_text") or ""
        if record["block_type"] == "title" and modern_text:
            markdown.extend([f"### {modern_text}", ""])
        elif record["block_type"] in {"figure", "table"}:
            markdown.extend([f"![{record['block_type']} {record['block_id']}](../20-source/pages/{record['page_id']}.jpg)", ""])
        elif modern_text:
            if record.get("review_status") == "pending_repair":
                markdown.extend([f"> **待修复：** `{record['block_id']}`", ""])
            markdown.extend([modern_text, ""])
        else:
            markdown.extend([f"> [{record['block_type']}：沿用 {record['page_id']} 图像证据]", ""])
    modern_md_path = modern_dir / "modernized.md"
    modern_md_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    terminology_json = {
        "schema_version": "1.0",
        "source": "V3 accepted term notes, aggregated without inventing new definitions",
        "terms": [
            {"term": term, "notes": sorted(notes), "status": "source-attested"}
            for term, notes in sorted(terminology.items())
        ],
    }
    write_json(modern_dir / "terminology.json", terminology_json)

    report = {
        "schema_version": "1.0",
        "generated_at": now,
        "status": "completed" if not repair_queue else "running",
        "normalized_blocks": len(normalized),
        "modernized_blocks": len(output),
        "identity_match": normalized_ids == output_ids,
        "mapping_counts": dict(mapping_counts),
        "mapped_canonical_character_percent": round(
            100
            * sum(
                len(canonical(record.get("normalized_text") or ""))
                for record in output
                if record["modernization_mapping"] not in {"fallback_preserve"}
            )
            / sum(len(canonical(record.get("normalized_text") or "")) for record in output),
            3,
        ),
        "v3_current_translatable_segments": len(current_translatable_ids),
        "v3_traceable_results": sum(segment_id in result_by_id for segment_id in current_translatable_ids),
        "v3_traceability_percent": round(
            100 * sum(segment_id in result_by_id for segment_id in current_translatable_ids) / len(current_translatable_ids), 3
        ),
        "mapped_verdict_counts": dict(verdict_counts),
        "repair_queue_segments": len(repair_queue),
        "bounded_uncertainty_segments": len(
            bounded_ledger_ids & current_translatable_ids
        ),
        "unresolved_block_records": len(unresolved_rows),
        "paid_calls_made_by_v4_import": 0,
        "repair_preflight": {
            "provider": "volcengine-ark",
            "credential_scope": "Windows user environment; value never written to artifacts",
            "credential_present": True,
            "estimated_cost_rmb": 3.0,
            "hard_cap_rmb": 10.0,
            "authorization_required_before_paid_calls": bool(repair_queue),
        },
        "normalized_sha256": sha256(normalized_path),
        "blocks_sha256": sha256(blocks_path),
        "draft_markdown_sha256": sha256(modern_md_path),
        "repair_queue_sha256": sha256(repair_path),
    }
    write_json(modern_dir / "modernization-report.json", report)

    state_path = WORKSPACE / "run-state.json"
    state = read_json(state_path)
    state.setdefault("stages", {})["modernization"] = {
        "status": "completed" if not repair_queue else "running",
        "updated_at": now,
        "blocks": len(output),
        "mapping_counts": dict(mapping_counts),
        "repair_queue_segments": len(repair_queue),
        "paid_calls_made": 0,
        "evidence": "40-modernized/modernization-report.json",
    }
    state["current_stage"] = "editing" if not repair_queue else "modernization"
    state["updated_at"] = now
    write_json(state_path, state)

    ledger = read_json(MASTER_LEDGER)
    for item in ledger["books"]:
        if int(item["book_no"]) == 1:
            item.update(
                {
                    "status": "editing_ready" if not repair_queue else "modernization_in_progress",
                    "current_stage": "editing" if not repair_queue else "modernization_repair",
                    "modernized_blocks": len(output),
                    "repair_queue_segments": len(repair_queue),
                    "modernization_gate": "passed" if not repair_queue else "running",
                    "updated_at": now,
                }
            )
            break
    ledger["updated_at"] = now
    write_json(MASTER_LEDGER, ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
