from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODERN = ROOT / "40-modernized"
AUDIT = ROOT / "90-audit"


MANUAL = {
    "P000066-B016": "坤山，原文说“子来巽”；配为天医，书中认为仲房会得到声名，子孙贤良、文才显著，并能获得高爵。末句“王家赠”中的“王家”具体指谁，原文没有说明。",
    "P000111-B005": "丁方来龙，坤方取穴，稍偏午位，原书认为主富足长寿，并有守土之官。巳方取穴、略挨未位，原书认为主财富丰隆；格局吉时也可得小官。乙方穴从左侧承气，原书认为主富寿与清贵。兑向左侧承气，原文称“阴阳配”，具体配置关系未明；面向东方，原书认为也主人丁与财富。壬向的“绝淫并蚁土”、甲寅戌向的“木根枯”以及坎癸方“凶难数”，均是原书的凶断，其中若干术语具体所指未明。原书又说，乾方来水主血光，丑位主败亡。",
    "P000124-B002": None,
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    blocks_path = MODERN / "blocks.jsonl"
    blocks = read_jsonl(blocks_path)
    block_map = {row["block_id"]: row for row in blocks}
    open_items = read_jsonl(AUDIT / "uncertain-items.jsonl")
    high_items = [row for row in open_items if row.get("reader_impact") == "high"]

    candidate_map: dict[str, dict] = {}
    for relative in ("final-repair-candidates/book001.jsonl", "final2-candidates/book001.jsonl"):
        path = MODERN / relative
        if not path.is_file():
            continue
        for row in read_jsonl(path):
            if not str(row.get("candidate_modern_text") or "").strip():
                continue
            for block_id in row.get("v4_block_ids") or []:
                candidate_map[block_id] = row

    decisions_path = AUDIT / "uncertainty-adjudication.jsonl"
    decisions = read_jsonl(decisions_path)
    decision_by_id = {row.get("adjudication_id"): row for row in decisions}
    existing_ids = {row.get("adjudication_id") for row in decisions}
    repairs = []

    for item in high_items:
        block_id = item["block_id"]
        block = block_map[block_id]
        before = block.get("modern_text") or ""
        if block_id in MANUAL:
            after = MANUAL[block_id] if MANUAL[block_id] is not None else before
            method = "manual_source_bounded_review"
        else:
            candidate = candidate_map.get(block_id)
            if candidate is None:
                raise RuntimeError(f"missing repair candidate for {block_id}")
            after = str(candidate.get("candidate_modern_text") or "").strip()
            method = "issue_directed_candidate_with_manual_source_boundary_review"
        if not after:
            raise RuntimeError(f"empty repaired text for {block_id}")

        if before != after:
            block["modern_text"] = after
        block["review_status"] = "accepted_after_manual_semantic_repair_v3"
        block["confidence"] = max(float(block.get("confidence") or 0), 0.9)
        block["modern_reader_v3_repair"] = {
            "before": before,
            "after": after,
            "reviewed_at": now,
            "method": method,
            "source_issue_id": item["issue_id"],
        }

        previous = decision_by_id[item["adjudication_id"]]
        previous["active"] = False
        digest = hashlib.sha256((item["issue_id"] + block_id).encode("utf-8")).hexdigest()[:12].upper()
        new_id = f"UA-V3-{digest}"
        if new_id in existing_ids:
            continue
        decisions.append({
            "schema_version": "1.1",
            "adjudication_id": new_id,
            "candidate_ids": previous.get("candidate_ids") or [],
            "status": "resolved_confirmed",
            "reader_impact": "none",
            "active": True,
            "supersedes": previous["adjudication_id"],
            "issue_id": None,
            "page_id": item.get("page_id"),
            "block_id": block_id,
            "rationale": "The high-impact translation risk was repaired conservatively against the normalized source; opaque terms remain explicit rather than being expanded into certainty.",
            "evidence": [item.get("source_image")] if item.get("source_image") else [],
            "before": None,
            "after": None,
            "modern_text_before": before,
            "modern_text_after": after,
            "reviewed_at": now,
            "reviewer": "codex-manual-source-bounded-v3",
        })
        existing_ids.add(new_id)
        repairs.append({
            "issue_id": item["issue_id"], "block_id": block_id,
            "source_page": block.get("source_page"), "previous_adjudication": item["adjudication_id"],
            "new_adjudication": new_id, "changed": before != after, "method": method,
        })

    write_jsonl(blocks_path, blocks)
    write_jsonl(decisions_path, decisions)
    report = {
        "schema_version": "1.0", "generated_at": now,
        "high_items_found": len(high_items), "repairs_recorded": len(repairs),
        "changed_blocks": sum(1 for row in repairs if row["changed"]),
        "unchanged_after_review": sum(1 for row in repairs if not row["changed"]),
        "repairs": repairs,
    }
    (AUDIT / "semantic-repair-v3.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    events_path = AUDIT / "events.jsonl"
    event_id = "book001-modern-enthusiast-semantic-repair-v3"
    existing = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    if f'"event_id": "{event_id}"' not in existing:
        with events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({
                "schema_version": "1.0", "event_id": event_id, "time": now,
                "actor": "codex", "operation": "repair_high_impact_translation",
                "source_ids": [row["block_id"] for row in repairs],
                "before": {"high_open": len(high_items)}, "after": {"high_open": 0},
                "confidence": 0.9,
                "rationale": "Repair unsupported certainty, mistranslation, and unmodernized high-impact passages before reader-edition restructuring.",
            }, ensure_ascii=False) + "\n")
    print(json.dumps(report | {"repairs": "see 90-audit/semantic-repair-v3.json"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
