#!/usr/bin/env python3
"""Regression tests for workflow 1.9 integrity gates."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from validate_integrity import validate, validate_source


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root: Path) -> None:
    write_json(root / "book.json", {"workflow_schema_version": "1.9", "delivery_mode": "ordinary_reader"})
    write_jsonl(root / "20-source/blocks.jsonl", [{
        "block_id": "P000001-B001", "source_page": 1, "text": "葬经",
        "component_id": "C-MAIN", "structural_role": "heading", "bbox": [10, 5, 90, 9],
        "reading_order": 1, "disposition": "included",
    }, {
        "block_id": "P000001-B002", "source_page": 1, "text": "葬者，藏也。",
        "component_id": "C-MAIN", "structural_role": "body", "bbox": [10, 10, 90, 40],
        "reading_order": 2, "disposition": "included",
    }])
    manuscript = root / "50-edited/modern-reading.md"
    manuscript.parent.mkdir(parents=True, exist_ok=True)
    manuscript.write_text("# 正文\n\n<!-- source:P000001-B001 -->\n《葬经》\n\n<!-- source:P000001-B002 -->\n古人所说的葬，就是妥善收藏。\n", encoding="utf-8")
    write_json(root / "10-diagnosis/edition-scope.json", {
        "status": "locked", "locked_at": "2026-09-27T00:00:00-07:00",
        "delivery_mode": "ordinary_reader", "completeness_claim": "full_source_content",
        "user_requirement": "交付忠于原著的完整白话文版。",
        "source_components": [{"component_id": "C-MAIN", "kind": "main_text",
                               "required_in_release": True, "planned_destination": "final_reader"}],
    })
    write_jsonl(root / "50-edited/source-reader-map.jsonl", [{
        "block_id": "P000001-B001", "component_id": "C-MAIN", "reader_heading": "正文",
        "reader_quote": "《葬经》", "status": "reviewed", "review_evidence": "书名已保留。",
    }, {
        "block_id": "P000001-B002", "component_id": "C-MAIN", "reader_heading": "正文",
        "reader_quote": "古人所说的葬，就是妥善收藏。", "status": "reviewed",
        "review_evidence": "逐句核对原文和白话句，含义相符。",
    }])
    write_json(root / "50-edited/review-policy.json", {"minimum_full_passes": 3, "required_stable_passes": 2})
    pass_dir = root / "50-edited/review-history/full-passes"
    for number in range(1, 4):
        transcript = pass_dir / f"pass-{number}.md"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(f"第 {number} 次逐章通读记录：正文含义清楚，未发现阻断问题。\n", encoding="utf-8")
        write_json(pass_dir / f"pass-{number}.json", {
            "manuscript_sha256": digest(manuscript), "reviewer_run_id": f"real-run-{number}",
            "status": "passed", "findings": [], "sections_covered": ["正文"],
            "new_blocking_issues": [], "open_blocking_issues": [],
            "transcript": transcript.relative_to(root).as_posix(), "transcript_sha256": digest(transcript),
        })


def assert_rejects(root: Path, fragment: str) -> None:
    errors = validate(root)
    if not any(fragment in error for error in errors):
        raise AssertionError(f"expected rejection containing {fragment!r}; got {errors!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chaoyun-integrity-v19-") as directory:
        root = Path(directory)
        fixture(root)
        baseline = validate(root)
        if baseline != ["workflow 1.9 requires a frozen acceptance-policy-lock.json"]:
            raise AssertionError(f"unexpected baseline failures: {baseline!r}")
        if validate_source(root):
            raise AssertionError(f"valid structured source fixture failed source gate: {validate_source(root)!r}")

        scope = root / "10-diagnosis/edition-scope.json"
        saved_scope = scope.read_bytes()
        scope.unlink()
        assert_rejects(root, "requires a frozen 10-diagnosis/edition-scope.json")
        scope.write_bytes(saved_scope)

        source_path = root / "20-source/blocks.jsonl"
        source = json.loads(source_path.read_text(encoding="utf-8").splitlines()[0])
        source.pop("component_id")
        source.pop("bbox")
        other = json.loads(source_path.read_text(encoding="utf-8").splitlines()[1])
        write_jsonl(source_path, [source, other])
        assert_rejects(root, "lacks structural fields")
        if not any("lacks structural fields" in error for error in validate_source(root)):
            raise AssertionError("source-stage gate did not reject missing structural fields")
        fixture(root)

        manuscript = root / "50-edited/modern-reading.md"
        manuscript.write_text("# 正文\n\n<!-- source:A --><!-- source:B --> 合并映射。\n", encoding="utf-8")
        assert_rejects(root, "aggregated source anchors")
        fixture(root)

        pass_file = root / "50-edited/review-history/full-passes/pass-3.json"
        record = json.loads(pass_file.read_text(encoding="utf-8"))
        record["reviewer_run_id"] = "real-run-2"
        write_json(pass_file, record)
        assert_rejects(root, "distinct real reviewer_run_id")

    print("workflow 1.9 integrity regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
