#!/usr/bin/env python3
"""Bind the independently reviewed v1.9 sample and advance the workflow gate."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def main() -> int:
    bindings = {
        path: sha(path)
        for path in (
            "20-source/blocks.jsonl",
            "30-normalized/blocks.jsonl",
            "40-modernized/book-understanding.md",
            "50-edited/editorial-plan.md",
            "50-edited/sample/reader-sample.md",
        )
    }
    sample_ids = []
    for page, limits in ((4, (1, 11)), (5, (1, 9)), (6, (5, 12))):
        sample_ids.extend(f"P{page:06d}-B{number:03d}" for number in range(limits[0], limits[1] + 1))
    plan = {
        "schema_version": "1.0",
        "workflow_schema_version": "1.9",
        "status": "sample_accepted",
        "bindings": bindings,
        "sample_selection": {
            "reason": "内篇二至内篇三连续呈现气随地势行止、风水、支垄、深浅、势形和定穴顺序，是全书概念依赖最密且最易被普通读者误读的段落。",
            "block_ids": sample_ids,
            "covered_difficulties": [
                "势、止、形、穴的先后关系",
                "支与垄的特征并非机械二分",
                "得水与藏风的不同作用和优先关系",
                "深浅是相对判断而非固定尺寸",
                "可观察地形与传统气论的边界",
                "经文与本版旧注的声音区分",
            ],
            "deferred_difficulties": [
                "亲子感应和鬼福论证在全书审读时单独检查",
                "土色长注、四势正反例及卷末三吉六凶在全书审读时检查",
                "第28页真实缺字在卷尾翻译和最终排版时检查",
            ],
            "figures_applicable": False,
            "figure_reason": "正式原文307块均为经文、旧注、篇题或版心文字，29页没有承担内容教学的图、表、地图或示意图。",
        },
        "blocking_questions": [],
        "sample_review": {
            "status": "passed",
            "producer_execution_id": "root-book004-v19-sample-20260929",
            "reviewer_execution_id": "sample-reader-v19-20260929",
            "reviewer_kind": "model",
            "manuscript_file": "50-edited/sample/reader-sample.md",
            "manuscript_sha256": sha("50-edited/sample/reader-sample.md"),
            "tasks_file": "50-edited/sample/tasks.json",
            "tasks_sha256": sha("50-edited/sample/tasks.json"),
            "responses_file": "50-edited/sample/responses-v19.json",
            "responses_sha256": sha("50-edited/sample/responses-v19.json"),
            "assessments_file": "50-edited/sample/assessments-v19.json",
            "assessments_sha256": sha("50-edited/sample/assessments-v19.json"),
            "provenance_file": "50-edited/sample/provenance-v19.md",
            "provenance_sha256": sha("50-edited/sample/provenance-v19.md"),
            "task_exemptions": {},
            "nonblocking_reader_limits": [
                "原书没有给出止处、有效横水和护卫的现代量化指标",
                "原书没有给出深浅的通用数值；白话版不得替它编造操作标准",
                "后续全文需持续区分气势、外气、内气、阴阳之气和生气的上下文用法",
            ],
        },
        "process_edition": "50-edited/process-edition/modern-reading.md",
        "final_reader_cut": "50-edited/modern-reading.md",
    }
    (ROOT / "50-edited/production-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    now = datetime.now(timezone.utc).isoformat()
    state_path = ROOT / "run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["updated_at"] = now
    state["current_stage"] = "modernization"
    state["stages"]["book_understood"] = {"status": "passed", "evidence": "40-modernized/book-understanding.md"}
    state["stages"]["reader_designed"] = {"status": "passed", "evidence": "50-edited/editorial-plan.md"}
    state["stages"]["sample_accepted"] = {"status": "passed", "evidence": "50-edited/production-plan.json"}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "sample_accepted", "sample_blocks": len(sample_ids), "bindings": bindings}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
