from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\壮五福\风水项目")
WORKSPACE = ROOT / "output" / "V4" / "001-青囊海角经"
MODERN = WORKSPACE / "40-modernized"
MASTER_LEDGER = ROOT / "output" / "V4" / "V4交付总账.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_event(value: dict) -> None:
    path = WORKSPACE / "90-audit" / "events.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, ensure_ascii=False) + "\n")


def main() -> None:
    now = utc_now()
    repairs = read_jsonl(MODERN / "manual-repairs.jsonl")
    repair_by_id = {row["v3_segment_id"]: row for row in repairs}
    if len(repair_by_id) != len(repairs):
        raise RuntimeError("duplicate v3_segment_id in manual repairs")

    blocks_path = MODERN / "blocks.jsonl"
    blocks = read_jsonl(blocks_path)
    applied_segments: set[str] = set()
    applied_blocks = 0
    for block in blocks:
        segment_ids = block.get("v3_segment_ids") or []
        matched = [segment_id for segment_id in segment_ids if segment_id in repair_by_id]
        if not matched:
            continue
        if len(matched) != 1:
            raise RuntimeError(f"ambiguous repair mapping for {block['block_id']}: {matched}")
        repair = repair_by_id[matched[0]]
        block["modern_text"] = repair["modern_text"]
        block["review_status"] = repair["review_status"]
        block["confidence"] = 0.92 if repair["review_status"] == "accepted_after_issue_directed_repair" else 0.82
        block["manual_repair"] = {
            "v3_segment_id": matched[0],
            "applied_at": now,
            "method": "issue_directed_local_repair",
            "rationale": repair["rationale"],
            "uncertainty": repair.get("uncertainty") or [],
            "paid_api_cost_rmb": 0,
        }
        applied_segments.add(matched[0])
        applied_blocks += 1

    missing = sorted(set(repair_by_id) - applied_segments)
    if missing:
        raise RuntimeError(f"manual repairs have no mapped V4 block: {missing}")
    write_jsonl(blocks_path, blocks)

    initial_queue_path = MODERN / "repair-queue.jsonl"
    initial_queue = read_jsonl(initial_queue_path)
    remaining = [row for row in initial_queue if row["v3_segment_id"] not in repair_by_id]
    remaining_path = MODERN / "repair-queue.remaining.jsonl"
    write_jsonl(remaining_path, remaining)

    # Rebuild the draft so the local review state is immediately visible.
    markdown = [
        "# 青囊海角经：V4 现代化草稿",
        "",
        f"> 已完成 {len(applied_segments)} 个问题段的本地修复；仍有 {len(remaining)} 段待修复。所有修复均未调用付费 API。",
        "",
    ]
    previous_page = None
    for block in blocks:
        if previous_page != block["page_id"]:
            markdown.extend([f"## 物理页 {block['source_page']} {{#{block['page_id']}}}", ""])
            previous_page = block["page_id"]
        modern_text = block.get("modern_text") or ""
        if block["block_type"] == "title" and modern_text:
            markdown.extend([f"### {modern_text}", ""])
        elif block["block_type"] in {"figure", "table"}:
            markdown.extend([f"![{block['block_type']} {block['block_id']}](../20-source/pages/{block['page_id']}.jpg)", ""])
        elif modern_text:
            if block.get("review_status") == "pending_repair":
                markdown.extend([f"> **待修复：** `{block['block_id']}`", ""])
            elif block.get("review_status") == "accepted_with_source_damage_ledger":
                markdown.extend([f"> **原件损伤说明：** `{block['block_id']}` 已保留原图与存疑记录。", ""])
            markdown.extend([modern_text, ""])
        else:
            markdown.extend([f"> [{block['block_type']}：沿用 {block['page_id']} 图像证据]", ""])
    modern_md_path = MODERN / "modernized.md"
    modern_md_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    report_path = MODERN / "modernization-report.json"
    report = read_json(report_path)
    report.update(
        {
            "updated_at": now,
            "manual_repairs_applied": len(applied_segments),
            "manual_repaired_blocks": applied_blocks,
            "repair_queue_segments_remaining": len(remaining),
            "paid_calls_made": 0,
            "paid_api_cost_rmb": 0,
            "blocks_sha256": sha256(blocks_path),
            "draft_markdown_sha256": sha256(modern_md_path),
            "remaining_queue_sha256": sha256(remaining_path),
        }
    )
    write_json(report_path, report)

    state_path = WORKSPACE / "run-state.json"
    state = read_json(state_path)
    stage = state.setdefault("stages", {}).setdefault("modernization", {})
    stage.update(
        {
            "status": "running",
            "updated_at": now,
            "manual_repairs_applied": len(applied_segments),
            "repair_queue_segments_remaining": len(remaining),
            "paid_calls_made": 0,
            "cost": 0,
        }
    )
    state["updated_at"] = now
    write_json(state_path, state)

    ledger = read_json(MASTER_LEDGER)
    for item in ledger["books"]:
        if int(item["book_no"]) == 1:
            item.update(
                {
                    "status": "modernization_in_progress",
                    "current_stage": "modernization_manual_repair",
                    "manual_repairs_applied": len(applied_segments),
                    "repair_queue_segments": len(remaining),
                    "paid_api_cost_rmb": 0,
                    "updated_at": now,
                }
            )
            break
    ledger["updated_at"] = now
    write_json(MASTER_LEDGER, ledger)

    append_event(
        {
            "schema_version": "1.0",
            "event": "modernization_manual_repair_batch",
            "time": now,
            "actor": "Codex local issue-directed review",
            "segments_repaired": len(applied_segments),
            "blocks_updated": applied_blocks,
            "remaining_segments": len(remaining),
            "paid_api_cost_rmb": 0,
            "repair_ids": sorted(applied_segments),
        }
    )
    print(
        json.dumps(
            {
                "manual_repairs": len(applied_segments),
                "updated_blocks": applied_blocks,
                "remaining": len(remaining),
                "paid_api_cost_rmb": 0,
                "blocks_sha256": sha256(blocks_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
