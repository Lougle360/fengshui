#!/usr/bin/env python3
"""Validate versioned uncertainty adjudication and atomically project open items."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closure_evidence import validate_closure, validate_release_review, validate_pilot, located


STATUSES = {"resolved_confirmed", "resolved_noncontent", "resolved_structural", "resolved_duplicate", "open_material"}
IMPACTS = {"none", "low", "medium", "high"}
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")


def schema_12_or_later(value: object) -> bool:
    try:
        major, minor, *_ = (int(part) for part in str(value).split("."))
        return (major, minor) >= (1, 2)
    except (TypeError, ValueError):
        return False


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"missing {path}")
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected object at {path}:{number}")
        rows.append(value)
    return rows


def atomic_write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    temporary = Path(handle.name)
    try:
        with handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        read_jsonl(temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def active_decisions(decisions: list[dict]) -> list[dict]:
    return [row for row in decisions if row.get("active", True) is True]


def validate(root: Path, candidates: list[dict], decisions: list[dict], require_release: bool = False) -> list[str]:
    errors: list[str] = []
    candidate_ids = [row.get("candidate_id") for row in candidates]
    if any(not value for value in candidate_ids):
        errors.append("every candidate requires candidate_id")
    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("duplicate candidate_id")
    candidate_set = set(candidate_ids)
    source_blocks: dict[str, dict] = {}
    source_path = root / "20-source" / "blocks.jsonl"
    if source_path.is_file():
        source_blocks = {row.get("block_id"): row for row in read_jsonl(source_path) if row.get("block_id")}
    for row in candidates:
        if row.get('schema_version') == '1.3':
            for field in ('page_id', 'block_id', 'kind', 'excerpt', 'reason', 'owner_stage', 'created_at'):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    errors.append(f"{row.get('candidate_id')} discovery requires {field}")
            if row.get('owner_stage') not in {'source', 'normalized', 'modernized', 'edited', 'reader_revised', 'publication'}:
                errors.append('discovery requires a responsible pipeline stage')
            try:
                located(root, row.get('input_ref'))
            except (OSError, ValueError, TypeError, ImportError) as exc:
                errors.append(f"{row.get('candidate_id')} discovery input is not bound: {exc}")
        if schema_12_or_later(row.get("schema_version")):
            for field in ("origin_stage", "review_cycle", "checkpoint", "created_by"):
                if not str(row.get(field) or "").strip():
                    errors.append(f"{row.get('candidate_id')} schema 1.2+ requires {field}")
        source_image = row.get("source_image")
        if source_image:
            image_path = (root / str(source_image)).resolve()
            try:
                image_path.relative_to(root)
            except ValueError:
                errors.append(f"{row.get('candidate_id')} source_image escapes workspace")
            else:
                if not image_path.is_file():
                    errors.append(f"{row.get('candidate_id')} missing source_image {source_image}")
        block_id = row.get("block_id")
        if block_id and source_blocks and block_id not in source_blocks:
            errors.append(f"{row.get('candidate_id')} unknown block_id {block_id}")

    decision_ids = [row.get("adjudication_id") for row in decisions]
    if any(not value for value in decision_ids):
        errors.append("every adjudication requires adjudication_id")
    if len(set(decision_ids)) != len(decision_ids):
        errors.append("duplicate adjudication_id")
    decision_map = {row.get("adjudication_id"): row for row in decisions if row.get("adjudication_id")}
    for row in decisions:
        decision_id = row.get("adjudication_id")
        if schema_12_or_later(row.get("schema_version")):
            for field in ("review_cycle", "checkpoint"):
                if not str(row.get(field) or "").strip():
                    errors.append(f"{decision_id} schema 1.2+ requires {field}")
        if row.get("status") not in STATUSES:
            errors.append(f"{decision_id} invalid status")
        if row.get("reader_impact") not in IMPACTS:
            errors.append(f"{decision_id} invalid reader_impact")
        ids = row.get("candidate_ids")
        if not isinstance(ids, list) or not ids:
            errors.append(f"{decision_id} requires candidate_ids")
        else:
            unknown = sorted(set(ids) - candidate_set)
            if unknown:
                errors.append(f"{decision_id} unknown candidates {unknown}")
        if not row.get("rationale"):
            errors.append(f"{decision_id} missing rationale")
        supersedes = row.get("supersedes")
        if supersedes:
            previous = decision_map.get(supersedes)
            if previous is None:
                errors.append(f"{decision_id} supersedes unknown adjudication {supersedes}")
            else:
                if previous.get("active", True) is not False:
                    errors.append(f"{decision_id} supersedes an adjudication that is still active")
                if not set(row.get("candidate_ids") or []) & set(previous.get("candidate_ids") or []):
                    errors.append(f"{decision_id} supersedes an unrelated adjudication")
        before, after = row.get("before"), row.get("after")
        if row.get("status") == "resolved_confirmed" and (before is None) != (after is None):
            errors.append(f"{decision_id} correction requires both before and after")
        if before is not None and after is not None:
            if before == after:
                errors.append(f"{decision_id} correction before and after are identical")
            block_id = row.get("block_id")
            current = source_blocks.get(block_id, {}).get("source_text") if block_id else None
            if row.get('active', True) is True and current is not None and str(after) not in str(current):
                errors.append(f"{decision_id} corrected text is not present in current source block")
        for evidence in row.get("evidence") or []:
            value = str(evidence)
            if value.lower().endswith(IMAGE_SUFFIXES):
                evidence_path = (root / value).resolve()
                try:
                    evidence_path.relative_to(root)
                except ValueError:
                    errors.append(f"{decision_id} evidence escapes workspace")
                else:
                    if not evidence_path.is_file():
                        errors.append(f"{decision_id} missing evidence {value}")

    active = active_decisions(decisions)
    referenced = [candidate_id for row in active for candidate_id in row.get("candidate_ids") or []]
    missing = sorted(candidate_set - set(referenced))
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in referenced:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    if missing:
        errors.append(f"unadjudicated candidates {missing}")
    if repeated:
        errors.append(f"candidates have more than one active adjudication {sorted(repeated)}")
    for row in active:
        if row.get("status") == "open_material" and not row.get("issue_id"):
            errors.append(f"{row.get('adjudication_id')} open_material requires stable issue_id")
        if row.get('status', '').startswith('resolved_'):
            if row.get('block_id') not in source_blocks:
                errors.append(f"{row.get('adjudication_id')} closure requires an existing source block")
            errors.extend(validate_closure(root, row))
    by_candidate = {candidate: row for row in active for candidate in row.get('candidate_ids') or []}
    for row in active:
        if row.get('status') != 'resolved_duplicate':
            continue
        seen = set()
        current = row
        while current.get('status') == 'resolved_duplicate':
            identifier = current.get('adjudication_id')
            if identifier in seen:
                errors.append('duplicate resolution cycle detected')
                break
            seen.add(identifier)
            current = by_candidate.get(current.get('duplicate_of'))
            if current is None:
                errors.append(f"{row.get('adjudication_id')} duplicate requires an active canonical candidate")
                break
        else:
            if current.get('status') == 'open_material':
                errors.append(f"{row.get('adjudication_id')} duplicate cannot close while its canonical issue is open")
    # Supersession is chronological, acyclic, and preserves an existing open issue identity.
    positions = {row.get('adjudication_id'): index for index, row in enumerate(decisions)}
    for index, row in enumerate(decisions):
        previous_id = row.get('supersedes')
        if previous_id and positions.get(previous_id, index) >= index:
            errors.append(f"{row.get('adjudication_id')} supersedes must reference an earlier decision")
        ancestor = decision_map.get(previous_id)
        visited = set()
        while ancestor and ancestor.get('adjudication_id') not in visited:
            visited.add(ancestor.get('adjudication_id'))
            if row.get('status') == 'open_material' and ancestor.get('issue_id') and row.get('issue_id') != ancestor['issue_id']:
                errors.append('reopened uncertainty must retain the original issue_id')
                break
            ancestor = decision_map.get(ancestor.get('supersedes'))
    if require_release:
        errors.extend(validate_release_review(root, decisions))
        errors.extend(validate_pilot(root, candidates))
    return errors


def projection(decisions: list[dict]) -> list[dict]:
    rows = []
    open_rows = [item for item in active_decisions(decisions) if item.get("status") == "open_material"]
    for row in sorted(open_rows, key=lambda item: str(item.get("issue_id"))):
        rows.append({
            "schema_version": "1.1",
            "issue_id": row["issue_id"],
            "adjudication_id": row["adjudication_id"],
            "status": "open",
            "reader_impact": row["reader_impact"],
            "page_id": row.get("page_id"),
            "block_id": row.get("block_id"),
            "note": row["rationale"],
            "source_image": next((value for value in row.get("evidence", []) if str(value).lower().endswith(IMAGE_SUFFIXES)), None),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--publication", action="store_true", help="Require final-manuscript recheck of all adjudications")
    parser.add_argument("--pilot", action="store_true", help="Read-only chapter-trial gate before scaling work")
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    audit = root / "90-audit"
    if args.pilot:
        try:
            errors = validate_pilot(root, read_jsonl(audit / 'uncertainty-candidates.jsonl'))
        except (OSError, ValueError) as exc:
            errors = [str(exc)]
        print(json.dumps({'valid': not errors, 'gate': 'chapter_trial', 'errors': errors}, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    try:
        candidates = read_jsonl(audit / "uncertainty-candidates.jsonl")
        decisions = read_jsonl(audit / "uncertainty-adjudication.jsonl")
        errors = validate(root, candidates, decisions, require_release=args.publication)
        expected = projection(decisions)
        target = audit / "uncertain-items.jsonl"
        if args.check:
            actual = read_jsonl(target)
            if actual != expected:
                errors.append("uncertain-items.jsonl is not the current open-material projection")
        elif not errors:
            atomic_write_jsonl(target, expected)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
        candidates = []
        decisions = []
        expected = []
    cycles = sorted({str(row.get("review_cycle")) for row in [*candidates, *decisions] if row.get("review_cycle")})
    result = {"valid": not errors, "review_cycles": len(cycles), "candidates": len(candidates), "adjudications": len(decisions), "active_adjudications": len(active_decisions(decisions)), "open_material": len(expected), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
