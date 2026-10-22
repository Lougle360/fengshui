#!/usr/bin/env python3
"""Safely migrate a legacy uncertainty ledger into candidate/adjudication files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def stable_id(prefix: str, value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12].upper()


def impact(severity: object) -> str:
    return str(severity) if severity in {"low", "medium", "high"} else "medium"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    audit = root / "90-audit"
    legacy_open = audit / "uncertain-items.jsonl"
    candidate_path = audit / "uncertainty-candidates.jsonl"
    decision_path = audit / "uncertainty-adjudication.jsonl"
    existing_candidates = read_jsonl(candidate_path)
    if existing_candidates:
        raise SystemExit("candidate ledger is not empty; refusing to overwrite an already migrated workspace")
    legacy_items = read_jsonl(legacy_open)
    old_decisions = read_jsonl(decision_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = audit / "legacy-uncertainty-migration" / stamp
    backup.mkdir(parents=True, exist_ok=False)
    for path in (legacy_open, candidate_path, decision_path):
        if path.exists():
            shutil.copy2(path, backup / path.name)

    candidates: list[dict] = []
    candidate_by_original: dict[str, str] = {}
    for item in legacy_items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in candidate_by_original:
            continue
        candidate_id = stable_id("UC", item)
        candidate_by_original[key] = candidate_id
        candidates.append({
            "schema_version": "1.2", "candidate_id": candidate_id,
            "page_id": item.get("page_id"), "block_id": item.get("block_id"),
            "origin_stage": "legacy", "kind": "glyph", "excerpt": item.get("excerpt"),
            "reason": item.get("note") or item.get("reason") or "legacy uncertainty",
            "source_image": item.get("source_image"), "severity": item.get("severity", "medium"),
            "review_cycle": "RC-LEGACY-0001", "checkpoint": "legacy_migration",
            "created_by": "legacy-migration",
        })

    decisions: list[dict] = []
    if old_decisions and all(isinstance(row.get("original"), dict) for row in old_decisions):
        for row in old_decisions:
            original = row["original"]
            key = json.dumps(original, ensure_ascii=False, sort_keys=True)
            candidate_id = candidate_by_original.get(key)
            if not candidate_id:
                candidate_id = stable_id("UC", original)
                candidate_by_original[key] = candidate_id
                candidates.append({
                    "schema_version": "1.2", "candidate_id": candidate_id,
                    "page_id": original.get("page_id"), "block_id": original.get("block_id"),
                    "origin_stage": "review_discovery", "kind": "missing",
                    "excerpt": None, "reason": row.get("rationale") or "review-discovered issue",
                    "source_image": original.get("source_image"), "severity": "medium",
                    "review_cycle": "RC-LEGACY-0001", "checkpoint": "legacy_migration",
                    "created_by": "legacy-migration",
                })
            # Archive preserves the old claim. Migration must never manufacture evidence for it.
            old_status = row.get("status")
            status = 'open_material'
            decision_id = stable_id("UA", {"legacy_id": row.get("adjudication_id"), "candidate_id": candidate_id, "row": row})
            decisions.append({
                "schema_version": "1.2", "adjudication_id": decision_id,
                "candidate_ids": [candidate_id], "status": status,
                "reader_impact": impact(original.get("severity")) if status == "open_material" else "none",
                "issue_id": "UI-" + candidate_id if status == "open_material" else None,
                "page_id": original.get("page_id"), "block_id": original.get("block_id"),
                "rationale": (row.get("rationale") or "Migrated legacy adjudication.") + (" Legacy closure requires fresh evidence and review." if old_status != 'open_material' else ''),
                "legacy_status": old_status,
                "evidence": [original["source_image"]] if original.get("source_image") else [],
                "before": None, "after": None, "active": True, "supersedes": None,
                "review_cycle": "RC-LEGACY-0001", "checkpoint": "legacy_migration",
                "reviewed_at": row.get("reviewed_at") or datetime.now(timezone.utc).isoformat(),
                "reviewer": row.get("reviewer") or "legacy-migration",
            })

    write_jsonl(candidate_path, candidates)
    write_jsonl(decision_path, decisions)
    legacy_open.write_text("", encoding="utf-8")
    result = {"backup": str(backup), "candidates": len(candidates), "adjudications": len(decisions), "needs_review": len(candidates) - len(decisions) + sum(row.get('legacy_status') != 'open_material' for row in decisions)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
