#!/usr/bin/env python3
"""Validate workflow 1.9 scope, traceability, review stability and policy freeze."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path


REQUIRED_SOURCE_FIELDS = {"component_id", "structural_role", "bbox", "reading_order"}
ALLOWED_COMPONENT_KINDS = {"main_text", "commentary", "preface", "figure", "table", "paratext"}
ALLOWED_DESTINATIONS = {"final_reader", "supplement", "evidence_only"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict]:
    values = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected object at {path}:{number}")
        value["_line"] = number
        values.append(value)
    return values


def section(text: str, heading: str) -> str:
    matches = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", text, re.M))
    for index, match in enumerate(matches):
        if match.group(2) != heading:
            continue
        end = next(
            (later.start() for later in matches[index + 1 :] if len(later.group(1)) <= len(match.group(1))),
            len(text),
        )
        return text[match.end() : end]
    return ""


def validate_scope(root: Path, source: list[dict], manuscript: str, errors: list[str]) -> None:
    path = root / "10-diagnosis/edition-scope.json"
    if not path.is_file():
        errors.append("workflow 1.9 requires a frozen 10-diagnosis/edition-scope.json")
        return
    try:
        scope = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid edition-scope.json: {exc}")
        return

    if scope.get("status") != "locked" or not str(scope.get("locked_at") or "").strip():
        errors.append("edition scope must be locked before production")
    if scope.get("delivery_mode") != "ordinary_reader" or scope.get("completeness_claim") != "full_source_content":
        errors.append("ordinary-reader white-language delivery requires full_source_content scope")
    if not str(scope.get("user_requirement") or "").strip():
        errors.append("edition scope must preserve the user's actual delivery requirement")

    components = scope.get("source_components")
    if not isinstance(components, list) or not components:
        errors.append("edition scope requires a nonempty source_components inventory")
        return
    component_by_id: dict[str, dict] = {}
    for item in components:
        if not isinstance(item, dict) or not str(item.get("component_id") or "").strip():
            errors.append("edition scope contains a component without component_id")
            continue
        component_id = item["component_id"]
        if component_id in component_by_id:
            errors.append(f"duplicate edition component: {component_id}")
        component_by_id[component_id] = item
        if item.get("kind") not in ALLOWED_COMPONENT_KINDS:
            errors.append(f"edition component {component_id} has invalid kind")
        if item.get("planned_destination") not in ALLOWED_DESTINATIONS:
            errors.append(f"edition component {component_id} has invalid planned_destination")
        if item.get("kind") in {"main_text", "commentary", "preface"} and item.get("required_in_release") is not True:
            authorization = item.get("exclusion_authorization")
            if not isinstance(authorization, dict) or not authorization.get("user_quote") or not authorization.get("recorded_at"):
                errors.append(f"source-bearing component {component_id} may not be excluded without explicit user authorization")

    source_component_ids = {row.get("component_id") for row in source if row.get("component_id")}
    unknown = source_component_ids - set(component_by_id)
    if unknown:
        errors.append(f"source blocks reference unknown edition components: {sorted(unknown)[:10]}")
    unused = set(component_by_id) - source_component_ids
    if unused:
        errors.append(f"edition components have no source blocks: {sorted(unused)[:10]}")

    map_path = root / "50-edited/source-reader-map.jsonl"
    if not map_path.is_file():
        errors.append("workflow 1.9 requires 50-edited/source-reader-map.jsonl")
        return
    try:
        mappings = read_jsonl(map_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid source-reader-map.jsonl: {exc}")
        return
    by_block = Counter(row.get("block_id") for row in mappings)
    duplicates = sorted(key for key, count in by_block.items() if key and count != 1)
    if duplicates:
        errors.append(f"source-reader map must contain each block exactly once: {duplicates[:10]}")

    source_by_id = {row.get("block_id"): row for row in source}
    for block_id, block in source_by_id.items():
        component = component_by_id.get(block.get("component_id"), {})
        source_bearing = block.get("disposition") not in {"noncontent", "unreadable", "excluded_with_reason"}
        required = component.get("required_in_release") is True and component.get("planned_destination") == "final_reader"
        rows = [row for row in mappings if row.get("block_id") == block_id]
        if source_bearing and required and len(rows) != 1:
            errors.append(f"source block {block_id} lacks exactly one reader mapping")
            continue
        if not rows:
            continue
        row = rows[0]
        if row.get("component_id") != block.get("component_id"):
            errors.append(f"source-reader map component mismatch for {block_id}")
        if required:
            heading = row.get("reader_heading")
            quote = row.get("reader_quote")
            if not isinstance(heading, str) or not isinstance(quote, str) or not quote.strip():
                errors.append(f"reader mapping for {block_id} requires heading and exact quote")
            elif quote not in section(manuscript, heading):
                errors.append(f"reader mapping for {block_id} is not located in its declared section")
            if row.get("status") != "reviewed" or not str(row.get("review_evidence") or "").strip():
                errors.append(f"reader mapping for {block_id} lacks reviewed evidence")
        else:
            if row.get("destination") not in {"supplement", "evidence_only", "noncontent", "unreadable"}:
                errors.append(f"non-reading block {block_id} lacks a valid preserved destination")

    for number, line in enumerate(manuscript.splitlines(), 1):
        if line.count("<!-- source:") > 1:
            errors.append(f"aggregated source anchors are not valid mapping evidence: line {number}")


def validate_source_structure(source: list[dict], errors: list[str]) -> None:
    roles = Counter()
    pages = Counter()
    for row in source:
        missing = REQUIRED_SOURCE_FIELDS - row.keys()
        if missing:
            errors.append(f"source block {row.get('block_id')} lacks structural fields: {sorted(missing)}")
            continue
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(value, (int, float)) for value in bbox):
            errors.append(f"source block {row.get('block_id')} has invalid bbox")
        if not isinstance(row.get("reading_order"), int) or row["reading_order"] < 1:
            errors.append(f"source block {row.get('block_id')} has invalid reading_order")
        roles[str(row.get("structural_role"))] += 1
        pages[row.get("source_page")] += 1
    if source and set(roles) == {"body"} and all(count == 1 for count in pages.values()):
        errors.append("source reconstruction collapsed every page into one body block; printed structure was not reconstructed")


def validate_review_stability(root: Path, manuscript_path: Path, errors: list[str]) -> None:
    policy_path = root / "50-edited/review-policy.json"
    if not policy_path.is_file():
        errors.append("workflow 1.9 requires 50-edited/review-policy.json")
        return
    try:
        policy = read_json(policy_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid review-policy.json: {exc}")
        return
    minimum = policy.get("minimum_full_passes")
    stable = policy.get("required_stable_passes")
    if not isinstance(minimum, int) or minimum < 3:
        errors.append("ordinary-reader review policy requires at least three complete passes")
        return
    if not isinstance(stable, int) or stable < 2 or stable > minimum:
        errors.append("review policy requires at least two stable final passes")
        return

    pass_dir = root / "50-edited/review-history/full-passes"
    paths = sorted(pass_dir.glob("*.json")) if pass_dir.is_dir() else []
    if len(paths) < minimum:
        errors.append(f"complete reader passes are insufficient: {len(paths)}/{minimum}")
        return
    expected_hash = sha256(manuscript_path)
    records = []
    run_ids = set()
    for path in paths:
        try:
            record = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid complete reader pass {path.name}: {exc}")
            continue
        records.append(record)
        if record.get("manuscript_sha256") != expected_hash:
            errors.append(f"complete reader pass {path.name} is stale")
        run_id = record.get("reviewer_run_id")
        if not isinstance(run_id, str) or not run_id.strip() or run_id in run_ids:
            errors.append(f"complete reader pass {path.name} requires a distinct real reviewer_run_id")
        run_ids.add(run_id)
        if record.get("status") not in {"passed", "failed"}:
            errors.append(f"complete reader pass {path.name} has invalid status")
        findings = record.get("findings")
        if not isinstance(findings, list):
            errors.append(f"complete reader pass {path.name} requires findings list")
        if not isinstance(record.get("sections_covered"), list) or not record.get("sections_covered"):
            errors.append(f"complete reader pass {path.name} lacks section coverage")
        transcript = record.get("transcript")
        if not isinstance(transcript, str):
            errors.append(f"complete reader pass {path.name} requires transcript path")
        else:
            transcript_path = (root / transcript).resolve()
            if not transcript_path.is_relative_to(root) or not transcript_path.is_file() or record.get("transcript_sha256") != sha256(transcript_path):
                errors.append(f"complete reader pass {path.name} transcript binding is invalid")
    if len(records) >= stable:
        for record in records[-stable:]:
            if record.get("status") != "passed" or record.get("new_blocking_issues") != [] or record.get("open_blocking_issues") != []:
                errors.append("the final stable reader passes must have no new or open blocking issues")

    acceptance_path = root / "50-edited/reader-acceptance-report.json"
    if acceptance_path.is_file():
        try:
            acceptance = read_json(acceptance_path)
            evidence = [
                str(item.get("evidence") or "").strip()
                for item in (acceptance.get("dimension_checks") or {}).values()
                if isinstance(item, dict)
            ]
            if evidence:
                repeated = Counter(evidence).most_common(1)[0][1]
                if repeated > max(2, math.ceil(len(evidence) / 3)):
                    errors.append("reader acceptance reuses generic evidence across too many dimensions")
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    process = root / "50-edited/review-history/RC0001/process-edition.md"
    ledger = root / "50-edited/reader-revision-ledger.jsonl"
    if process.is_file() and ledger.is_file():
        try:
            before = len(re.sub(r"\s+", "", process.read_text(encoding="utf-8")))
            after = len(re.sub(r"\s+", "", manuscript_path.read_text(encoding="utf-8")))
            changes = read_jsonl(ledger)
            if before and abs(after - before) / before > 0.15 and len(changes) < 3:
                errors.append("a large final-reader cut cannot be represented by one catch-all revision record")
        except (OSError, ValueError, json.JSONDecodeError):
            pass


def validator_paths() -> dict[str, Path]:
    controller = Path(__file__).resolve().parent
    skills = controller.parents[1]
    return {
        "controller/validate_workspace.py": controller / "validate_workspace.py",
        "controller/validate_integrity.py": controller / "validate_integrity.py",
        "controller/validate_delivery.py": controller / "validate_delivery.py",
        "reading-editor/validate_reader_value.py": skills / "chaoyun-reading-editor/scripts/validate_reader_value.py",
        "reader-reviser/validate_reader_revision.py": skills / "chaoyun-reader-experience-reviser/scripts/validate_reader_revision.py",
        "publisher/audit_publication.py": skills / "chaoyun-quality-publisher/scripts/audit_publication.py",
        "publisher/validate_release_binding.py": skills / "chaoyun-quality-publisher/scripts/validate_release_binding.py",
        "publisher/validate_pdf_readability.py": skills / "chaoyun-quality-publisher/scripts/validate_pdf_readability.py",
    }


def validate_policy_lock(root: Path, errors: list[str]) -> None:
    path = root / "90-audit/acceptance-policy-lock.json"
    if not path.is_file():
        errors.append("workflow 1.9 requires a frozen acceptance-policy-lock.json")
        return
    try:
        lock = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid acceptance-policy-lock.json: {exc}")
        return
    if lock.get("policy_version") != "1.9":
        errors.append("acceptance policy lock must use version 1.9")
    contract = root / "10-diagnosis/edition-scope.json"
    if not contract.is_file() or lock.get("edition_scope_sha256") != sha256(contract):
        errors.append("acceptance policy lock does not match the frozen edition scope")
    locked = lock.get("validators") if isinstance(lock.get("validators"), dict) else {}
    for name, path_value in validator_paths().items():
        if not path_value.is_file() or locked.get(name) != sha256(path_value):
            errors.append(f"acceptance policy changed after review began: {name}")


def validate_source(root: Path) -> list[str]:
    """Run the workflow-1.9 structure/scope gate as soon as source reconstruction ends."""
    errors: list[str] = []
    try:
        book = read_json(root / "book.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot validate workflow 1.9 source integrity: {exc}"]
    if book.get("delivery_mode") != "ordinary_reader" or str(book.get("workflow_schema_version") or "") != "1.9":
        return errors
    try:
        source = read_jsonl(root / "20-source/blocks.jsonl")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot validate workflow 1.9 source blocks: {exc}"]
    validate_source_structure(source, errors)
    scope_path = root / "10-diagnosis/edition-scope.json"
    if not scope_path.is_file():
        errors.append("workflow 1.9 source gate requires a frozen 10-diagnosis/edition-scope.json")
        return errors
    try:
        scope = read_json(scope_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid edition-scope.json: {exc}")
        return errors
    if scope.get("status") != "locked":
        errors.append("edition scope must be locked before source reconstruction can pass")
    components = scope.get("source_components") if isinstance(scope.get("source_components"), list) else []
    component_ids = {item.get("component_id") for item in components if isinstance(item, dict)}
    invalid_components = [row.get("block_id") for row in source if row.get("component_id") not in component_ids]
    if invalid_components:
        errors.append(
            "source blocks lack a component declared by edition scope: "
            f"count={len(invalid_components)}, examples={invalid_components[:10]}"
        )
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        book = read_json(root / "book.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot validate workflow 1.9 integrity: {exc}"]
    if book.get("delivery_mode") != "ordinary_reader" or str(book.get("workflow_schema_version") or "") != "1.9":
        return errors
    try:
        source = read_jsonl(root / "20-source/blocks.jsonl")
        manuscript_path = root / "50-edited/modern-reading.md"
        manuscript = manuscript_path.read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot validate workflow 1.9 artifacts: {exc}"]
    validate_source_structure(source, errors)
    validate_scope(root, source, manuscript, errors)
    validate_review_stability(root, manuscript_path, errors)
    validate_policy_lock(root, errors)
    return errors
