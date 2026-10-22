"""Register auditable source-stage decisions from completed page reviews.

This script does not infer readings.  It binds decisions to the already saved
before snapshots, current transcription inputs, correction manifests, and
independent page-review notes.  Review records are intentionally left for a
separate reviewer run.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / "90-audit"
READING = AUDIT / "source-reading"
LEDGER = AUDIT / "uncertainty-adjudication.jsonl"
CANDIDATES = AUDIT / "uncertainty-candidates.jsonl"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path, quote: str | None = None) -> dict:
    item = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
    if quote is not None:
        item["quote"] = quote
    return item


def minimal_change(before_path: Path, after_path: Path) -> dict:
    before = before_path.read_text(encoding="utf-8")
    after = after_path.read_text(encoding="utf-8")
    start = 0
    limit = min(len(before), len(after))
    while start < limit and before[start] == after[start]:
        start += 1
    suffix = 0
    while (suffix < len(before) - start and suffix < len(after) - start
           and before[-1 - suffix] == after[-1 - suffix]):
        suffix += 1
    before_end = len(before) - suffix
    after_end = len(after) - suffix
    return {
        "input": ref(before_path),
        "output": ref(after_path),
        "current": ref(after_path),
        "start_offset": start,
        "end_offset": before_end,
        "before": before[start:before_end],
        "after": after[start:after_end],
    }


def impacts(current: Path, quote: str) -> dict:
    return {
        "source": {"status": "checked", "reason": "逐页复核结果已落盘并由当前源文输入承载。", "artifacts": [ref(current, quote)]},
        "translation": {"status": "not_applicable", "reason": "白话转换尚未开始；后续从冻结源文生成。"},
        "terminology": {"status": "not_applicable", "reason": "术语层尚未生成。"},
        "reader_text": {"status": "not_applicable", "reason": "读者稿尚未生成，后续将按源文映射复核。"},
        "figures": {"status": "not_applicable", "reason": "本次为文字与结构校勘。"},
        "publication": {"status": "not_applicable", "reason": "尚无候选发布物。"},
    }


def main() -> None:
    candidates = [json.loads(x) for x in CANDIDATES.read_text(encoding="utf-8").splitlines() if x.strip()]
    by_id = {x["candidate_id"]: x for x in candidates}
    rows = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [x for x in rows if not str(x.get("adjudication_id", "")).startswith("UA-SRC-")]

    # Only close candidates whose complete recorded uncertainty was decided.
    # A correction manifest may change one word inside a wider still-open
    # candidate; those partial cases deliberately stay open.
    correction_ids: set[str] = {
        "UC000004", "UC000009", "UC000016", "UC000019", "UC000020", "UC000022", "UC000023",
        "UC000027", "UC000033", "UC000042", "UC000043", "UC000044", "UC000045", "UC000046",
        "UC000053", "UC000054", "UC000055", "UC000056", "UC000059", "UC000061", "UC000062", "UC000063",
        "UC000071", "UC000074", "UC000077", "UC000078", "UC000079", "UC000080", "UC000081",
        "UC000102", "UC000103", "UC000104", "UC000105", "UC000106", "UC000107", "UC000113", "UC000117",
        "UC000121", "UC000122",
    }

    groups = [
        ("001-003", READING / "pages-001-003-before-UC000004.json", ROOT / "20-source/transcription-inputs/pages-001-003.json", READING / "pages-001-003-independent.md"),
        ("004-005", READING / "pages-004-005-before-independent-fixes.json", ROOT / "20-source/transcription-inputs/pages-004-005.json", READING / "pages-004-007-independent.md"),
        ("006-007", READING / "pages-006-007-before-independent-fixes.json", ROOT / "20-source/transcription-inputs/pages-006-007.json", READING / "pages-004-007-independent.md"),
        ("008-009", READING / "pages-008-009-before-independent-fixes.json", ROOT / "20-source/transcription-inputs/pages-008-009.json", READING / "pages-008-010-independent.md"),
        ("010", READING / "pages-010-before-independent-fixes.json", ROOT / "20-source/transcription-inputs/pages-010.json", READING / "pages-008-010-independent.md"),
        ("011-012", READING / "pages-011-012-before-review-011-014.json", ROOT / "20-source/transcription-inputs/pages-011-012.json", READING / "pages-011-012-independent.md"),
        ("013-014", READING / "pages-013-014-before-review-011-014.json", ROOT / "20-source/transcription-inputs/pages-013-014.json", READING / "pages-013-014-independent.md"),
        ("015", READING / "pages-015-before-review-015-016.json", ROOT / "20-source/transcription-inputs/pages-015.json", READING / "pages-015-016-independent.md"),
        ("016", READING / "pages-016-before-review-015-016.json", ROOT / "20-source/transcription-inputs/pages-016.json", READING / "pages-015-016-independent.md"),
        ("017-018", READING / "pages-017-018-before-review-017-020.json", ROOT / "20-source/transcription-inputs/pages-017-018.json", READING / "pages-017-018-independent.md"),
        ("019-020", READING / "pages-019-020-before-review-017-020.json", ROOT / "20-source/transcription-inputs/pages-019-020.json", READING / "pages-019-020-independent.md"),
        ("021-022", READING / "pages-021-022-before-review.json", ROOT / "20-source/transcription-inputs/pages-021-022.json", READING / "pages-021-022-independent.md"),
    ]
    now = "2026-09-30T06:00:00Z"
    for index, (label, before, current, review) in enumerate(groups, 1):
        pages = {f"P{int(p):06d}" for p in label.split("-")}
        if "-" in label:
            lo, hi = map(int, label.split("-"))
            pages = {f"P{x:06d}" for x in range(lo, hi + 1)}
        ids = sorted(x for x in correction_ids if by_id.get(x, {}).get("page_id") in pages)
        if not ids:
            continue
        snap = READING / "snapshots" / "source-closures" / f"pages-{label}.after.json"
        snap.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(current, snap)
        aid = f"UA-SRC-C{index:02d}"
        review_text = review.read_text(encoding="utf-8")
        evidence_quote = next(line for line in review_text.splitlines() if line.strip() and not line.startswith("#"))
        current_data = json.loads(current.read_text(encoding="utf-8"))
        blocks = current_data.get("blocks", current_data if isinstance(current_data, list) else [])
        if not blocks and isinstance(current_data, dict):
            blocks = [block for page in current_data.get("pages", []) for block in page.get("blocks", [])]
        quote = str(blocks[0].get("source_text", blocks[0].get("text", "")))
        structural = any(by_id[cid].get("kind") in {"reading_order", "layout"} for cid in ids)
        row = {
            "schema_version": "1.3", "adjudication_id": aid, "candidate_ids": ids,
            "status": "resolved_structural" if structural else "resolved_confirmed", "reader_impact": "none", "active": True,
            "supersedes": None, "review_cycle": "SRC0004", "checkpoint": "source_reconstruction",
            "page_id": by_id[ids[0]]["page_id"], "block_id": by_id[ids[0]]["block_id"],
            "rationale": f"第{label}页逐图校勘已完成；这些候选对应的文字、漏字、角色或坐标更正均已落入当前输入，未把未决字顺带判定。",
            "evidence": [review.relative_to(ROOT).as_posix()], "before": None, "after": None,
            "reviewed_at": now, "reviewer": "Codex root",
            "closure": {
                "action": "corrected",
                "evidence": [ref(review, evidence_quote)],
                "change": minimal_change(before, snap) | {"current": ref(current)},
                "impact_review": impacts(current, quote),
                "producer": "Codex root", "producer_run_id": f"root-source-closure-{label}",
                "review_record": {"path": f"90-audit/source-reading/closure-reviews/{aid}.json", "sha256": "PENDING"},
            },
        }
        rows.append(row)

    decided = {cid for row in rows if row.get("active", True) for cid in row.get("candidate_ids", [])}
    remaining = [x for x in candidates if x["candidate_id"] not in decided]
    # Remaining readings are preserved conservatively by page-file group. They
    # remain material until the final manuscript demonstrates a faithful,
    # non-speculative reader rendering and release review.
    for index, (label, _before, current, review) in enumerate(groups, 1):
        pages = {f"P{int(label):06d}"} if "-" not in label else {f"P{x:06d}" for x in range(int(label.split('-')[0]), int(label.split('-')[1]) + 1)}
        items = [x for x in remaining if x["page_id"] in pages]
        if not items:
            continue
        aid = f"UA-SRC-O{index:02d}"
        rows.append({
            "schema_version": "1.3", "adjudication_id": aid,
            "candidate_ids": [x["candidate_id"] for x in items], "issue_id": f"UI-SOURCE-{label}",
            "status": "open_material", "reader_impact": "medium", "active": True,
            "supersedes": None, "review_cycle": "SRC0004", "checkpoint": "source_reconstruction",
            "page_id": items[0]["page_id"], "block_id": items[0]["block_id"],
            "rationale": f"第{label}页复核后仍有刻痕、墨损或字形不能唯一裁决；保留底本可见录文，白话阶段不得靠通行本或理论补造，并在最终稿逐项核查读者影响。",
            "evidence": [review.relative_to(ROOT).as_posix(), current.relative_to(ROOT).as_posix()],
            "before": None, "after": None, "reviewed_at": now, "reviewer": "Codex root",
            "required_input": "同版更清实物影像；若无，则维持保守释读并在最终稿集中说明。",
        })

    LEDGER.write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "corrected_groups": len([x for x in rows if str(x.get('adjudication_id','')).startswith('UA-SRC-C')]), "open_groups": len([x for x in rows if str(x.get('adjudication_id','')).startswith('UA-SRC-O')]), "remaining_candidates": len(remaining)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
