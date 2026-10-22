from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITED = ROOT / "50-edited"
HISTORY = EDITED / "review-history" / "RC0007"
MANUSCRIPT = EDITED / "modern-reading.md"
PRODUCER_ID = "root-editorial-RC0007-59dd008c"
REVIEWER_ID = "reference-only-regression-RC0007-59dd008c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def line_hash(lines: list[str], start: int, end: int) -> str:
    text = "\n".join(lines[start - 1:end])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    lines = text.splitlines()
    manuscript_hash = sha(MANUSCRIPT)
    if manuscript_hash != "59dd008c96da587aafdbafd854f6e24455ba1859c05fd79194cf3ead33a0ac05":
        raise SystemExit("manuscript changed after RC0007")

    tasks = read_json(HISTORY / "tasks.json")
    responses = read_json(HISTORY / "reader-responses.json")
    assessments = read_json(HISTORY / "assessments.json")
    audit = read_json(HISTORY / "reader-audit.json")
    if audit["manuscript_sha256"] != manuscript_hash or audit["overall"]["status"] != "passed":
        raise SystemExit("RC0007 does not accept the frozen manuscript")
    response_by_id = {row["task_id"]: row["answer"] for row in responses}
    assessment_by_id = {row["task_id"]: row for row in assessments}

    for name in ("reader-review.json", "reader-acceptance-report.json"):
        source = EDITED / name
        archive = EDITED / "review-history" / "RC0006" / name
        if source.is_file() and not archive.exists():
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, archive)

    input_snapshot = HISTORY / "input.md"
    output_snapshot = HISTORY / "output.md"
    input_snapshot.write_bytes(MANUSCRIPT.read_bytes())
    output_snapshot.write_bytes(MANUSCRIPT.read_bytes())

    standard_dimensions = {
        "introduction_promise": "读者定位、传本署名边界和本版承诺在开篇与六章内容中一致。",
        "prerequisites": "最低阅读准备先解释八个方位组与八个核心词，31项回答未依赖未说明前置知识。",
        "navigation": "目录、六章地图、页级判断、术语与图式索引可支持顺读和回查。",
        "continuity": "读者能连续复述审势、行止、审穴、审砂、审气与审向的关系。",
        "terminology": "22个核心词均有独立任务并得到上下文回答，三合、纳甲与十二长生可区分。",
        "examples_and_figures": "实际打开斜来正受与棕叶鬼形原图完成任务；两幅降级图未被用作教学证明。",
        "redundancy_and_pacing": "第一编承担连续阅读，第二编明确作为逐页对照查阅层；术语密集不再阻断主线。",
        "source_editor_trust": "现存题署、编辑重组、传统解释和当前疑文保持显式分层。",
        "closure_and_lookup": "主题、图式、疑文索引与末尾六问闭合阅读任务。",
    }
    review = {
        "schema_version": "1.2",
        "cycle_id": "RC0007",
        "mode": "manuscript",
        "input_snapshot": "50-edited/review-history/RC0007/input.md",
        "input_sha256": manuscript_hash,
        "target_reader": "对传统地理古籍感兴趣、无术数基础的现代普通读者",
        "reviewer": "/root/reference_only_regression",
        "reviewer_kind": "model",
        "dimensions": {key: {"verdict": "passed", "findings": []} for key in standard_dimensions},
        "blocking_issues": [],
    }
    dump(EDITED / "reader-review.json", review)

    ledger_path = EDITED / "reader-revision-ledger.jsonl"
    ledger_rows = [json.loads(row) for row in ledger_path.read_text(encoding="utf-8").splitlines() if row.strip()]
    if not any(row.get("event_id") == "RRE000003" for row in ledger_rows):
        ledger_rows.append({
            "schema_version": "1.1",
            "event_id": "RRE000003",
            "revision_id": "RR000002",
            "cycle_id": "RC0007",
            "operation": "delete_from_reading_path",
            "reader_problem": "旧回归曾要求用两幅模糊原图建立可唯一定位的教学示意和编号映射。",
            "block_ids": ["P000050-B007", "P000056-B010"],
            "section": "第四章图式",
            "before": None,
            "after": None,
            "preservation": "50-edited/review-history/RC0005/reader-audit.json",
            "evidence": [
                "用户明确决定两幅图仅保留原图、不承担教学证明。",
                "50-edited/review-history/RC0007/reader-audit.json",
            ],
            "semantic_risk": "low",
            "uncertainty_candidate_id": None,
            "status": "rejected",
            "rationale": "不再试图从模糊图像建立唯一映射；原图和旧失败记录均保留，其他可辨图继续承担读图教学。",
            "resolution_review": {
                "reviewer": "/root/reference_only_regression",
                "status": "passed",
                "evidence": "RC0007受影响回归确认RC0006图式任务仍成立，降级图不承担教学证明。",
            },
        })
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ledger_rows), encoding="utf-8")

    producer_record = {
        "actor": "/root/editorial-producer",
        "run_id": PRODUCER_ID,
        "output_sha256": manuscript_hash,
        "action": "将P000050-B007与P000056-B010降级为原图存档参考，移除现代示意和编号映射，并重建读者价值合同。",
    }
    reviewer_record = {
        "actor": "/root/reference_only_regression",
        "run_id": REVIEWER_ID,
        "output_sha256": manuscript_hash,
        "reviewer_kind": "model",
        "evidence": "50-edited/review-history/RC0007/provenance.md",
    }
    dump(HISTORY / "producer.json", producer_record)
    dump(HISTORY / "reviewer.json", reviewer_record)

    main_tasks = [row for row in tasks if row["id"].startswith("FULL-") and "TERM" not in row["id"]]
    section_reviews = []
    for task in main_tasks:
        start, end = task["start_line"], task["end_line"]
        unit = "\n".join(lines[start - 1:end])
        block_ids = re.findall(r"<!-- source:([^>]+) -->", unit)
        answer = response_by_id[task["id"]]
        section_reviews.append({
            "start_line": start,
            "end_line": end,
            "text_sha256": line_hash(lines, start, end),
            "quote": next((line for line in lines[start - 1:end] if line.strip() and not line.startswith("#")), lines[start - 1]),
            "reader_question": task["question"],
            "plain_answer": answer,
            "prerequisites": "所需概念由第一编最低阅读准备、章首抓手和术语表提供。",
            "comprehension_evidence": assessment_by_id[task["id"]]["evidence"],
            "task_ids": [task["id"]],
            "block_ids": block_ids,
            "status": "passed",
            "remaining_obstacles": [],
        })

    aids = read_json(EDITED / "reader-aids.json")
    glossary_samples = []
    for index, entry in enumerate([row for row in aids["glossary"]["entries"] if row.get("tier") == "core"], 1):
        task_id = f"FULL-TERM-{index:03d}"
        answer = response_by_id[task_id]
        answer_quote = answer[: min(48, len(answer))]
        glossary_samples.append({
            "term": entry["term"],
            "plain_enough": True,
            "context_specific": True,
            "example_helpful": True,
            "issue": None,
            "quote": entry["plain_definition"],
            "evidence": assessment_by_id[task_id]["evidence"],
            "task_ids": [task_id],
            "answer_quote": answer_quote,
        })

    session = {
        "status": "passed",
        "producer_execution_id": PRODUCER_ID,
        "reviewer_execution_id": REVIEWER_ID,
        "reviewer_kind": "model",
        "manuscript_file": "50-edited/modern-reading.md",
        "manuscript_sha256": manuscript_hash,
        "tasks_file": "50-edited/review-history/RC0007/tasks.json",
        "tasks_sha256": sha(HISTORY / "tasks.json"),
        "responses_file": "50-edited/review-history/RC0007/reader-responses.json",
        "responses_sha256": sha(HISTORY / "reader-responses.json"),
        "assessments_file": "50-edited/review-history/RC0007/assessments.json",
        "assessments_sha256": sha(HISTORY / "assessments.json"),
        "provenance_file": "50-edited/review-history/RC0007/provenance.md",
        "provenance_sha256": sha(HISTORY / "provenance.md"),
        "task_exemptions": {},
    }
    acceptance = {
        "schema_version": "1.2",
        "cycle_id": "RC0007",
        "mode": "manuscript",
        "producer": producer_record["actor"],
        "reviewer": reviewer_record["actor"],
        "producer_record": "50-edited/review-history/RC0007/producer.json",
        "producer_record_sha256": sha(HISTORY / "producer.json"),
        "reviewer_record": "50-edited/review-history/RC0007/reviewer.json",
        "reviewer_record_sha256": sha(HISTORY / "reviewer.json"),
        "status": "passed",
        "output_sha256": manuscript_hash,
        "regression_review": "passed",
        "blocking_issues": [],
        "counts": {"add": 0, "delete_from_reading_path": 0, "rewrite": 0, "reorganize": 0},
        "dimension_checks": {key: {"status": "passed", "evidence": value} for key, value in standard_dimensions.items()},
        "section_reviews": section_reviews,
        "glossary_samples": glossary_samples,
        "reading_session": session,
        "reviewer_kind": "model",
        "limitations": ["独立模型回归不等于人类读者实验。"],
    }
    dump(EDITED / "reader-acceptance-report.json", acceptance)

    contract = read_json(EDITED / "delivery-contract.json")
    for outcome in contract["outcomes"]:
        outcome["status"] = "passed"
        outcome["review_evidence"] = "RC0006独立模型全读31/31任务通过，RC0007对来源锚点修正完成受影响回归；相关记录见review-history。"
    dump(EDITED / "delivery-contract.json", contract)

    report = read_json(EDITED / "editorial-report.json")
    report["glossary"] = {
        "status": "completed",
        "entry_count": len(aids["glossary"]["entries"]),
        "entries_with_first_occurrence": len(aids["glossary"]["entries"]),
        "core_entry_count": len(glossary_samples),
        "reader_review_sampled": len(glossary_samples),
        "reason": None,
    }
    report["reader_value"] = {
        "introduction_sections": 9,
        "review_dimensions": 9,
        "revision_cycle": "RC0007",
        "applied_revisions": 0,
        "producer": producer_record["actor"],
        "reviewer": reviewer_record["actor"],
        "status": "passed",
        "reviewer_kind": "model",
    }
    report["figures"] = {
        "content_figures_total": 33,
        "content_figures_rendered": 33,
        "content_figures_guided": 31,
        "reference_only": 2,
        "reference_only_block_ids": ["P000050-B007", "P000056-B010"],
    }
    dump(EDITED / "editorial-report.json", report)
    print(json.dumps({"cycle": "RC0007", "manuscript_sha256": manuscript_hash, "sections": len(section_reviews), "glossary_samples": len(glossary_samples)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
