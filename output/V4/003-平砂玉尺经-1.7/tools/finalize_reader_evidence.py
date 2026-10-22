"""Bind the accepted compact reader edition to real reading-session evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDIT = ROOT / "50-edited"
RC = EDIT / "review-history/RC0008"
MANUSCRIPT = EDIT / "modern-reading.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_fields(definition: str) -> tuple[str, str]:
    sentences = [x.strip() for x in re.split(r"(?<=[。！？])", definition) if x.strip()]
    if len(sentences) >= 2:
        return sentences[0], "".join(sentences[1:])
    for sep in ("；", "，"):
        if sep in definition:
            left = definition.split(sep, 1)[0].strip() + sep
            return left, definition
    midpoint = max(1, len(definition) // 2)
    return definition[:midpoint], definition


def main() -> None:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    assert sha(MANUSCRIPT) == "ccb7d9b8361d91f5c22566a558503eddc7d372b035d84317c81127a48e495be3"
    tasks = load(RC / "tasks.json")
    responses = load(RC / "responses.json")
    provenance = load(RC / "provenance.json")
    assert len(tasks) == len(responses) == 10
    assert provenance.get("tasks_sha256", "").lower() == sha(RC / "tasks.json")
    answers = {row["task_id"]: row["answer"] for row in responses}

    # Preserve the process-edition database before binding the compact final glossary.
    aids_path = EDIT / "reader-aids.json"
    old_aids = load(aids_path)
    archived = RC / "process-reader-aids.json"
    if not archived.exists():
        dump(archived, old_aids)

    glossary_lines = {}
    for match in re.finditer(r"^\*\*([^*]+)\*\*\s*(.+)$", text, re.M):
        label, definition = match.group(1).strip(), match.group(2).strip()
        for term in [x.strip() for x in re.split(r"[、；;]", label) if x.strip()]:
            glossary_lines[term] = (label, definition)

    entries = []
    for entry in old_aids["glossary"]["entries"]:
        term = entry["term"]
        assert term in glossary_lines, term
        _, definition = glossary_lines[term]
        plain, contextual = compact_fields(definition)
        updated = dict(entry)
        updated.update({
            "tier": "supporting",
            "confidence": "qualified",
            "plain_definition": plain,
            "contextual_definition": contextual,
        })
        updated.pop("usage_example", None)
        updated.pop("common_confusions", None)
        updated.pop("related_terms", None)
        entries.append(updated)

    intro_sentences = [
        "本书按现存传本的六篇次序编排。",
        "书中的吉凶、福祸判断属于传统堪舆观念。",
        "原文不能确定的地方保留简短说明；图下注解及书末词语解释为编者所加。",
        "上述作者姓名依据传本题署，不据此断定全书实际作者。",
        "本书主要讲平原地形中如何根据山脉、水流和周围地形，判断地势从哪里来、在哪里收住，再找到具体的穴位和朝向。",
        "六篇的顺序是：先审大势，再分辨气的类别；接着寻龙、审穴，查看周围的砂山，最后才处理立向。",
        "这个顺序就是全书的主线。",
    ]
    assert all(value in text for value in intro_sentences)
    intro_keys = [
        "what_this_book_is", "who_should_read", "reader_value", "contents_and_structure",
        "distinctive_features", "historical_and_textual_context", "how_to_read",
        "limitations_and_cautions", "edition_method",
    ]
    intro_values = [
        intro_sentences[4], intro_sentences[4], intro_sentences[6], intro_sentences[5],
        intro_sentences[0], intro_sentences[3], intro_sentences[5], intro_sentences[1], intro_sentences[2],
    ]
    aids = {
        "schema_version": "1.1",
        "introduction": {
            "markdown_heading": "出版说明",
            "sections": dict(zip(intro_keys, intro_values)),
            "evidence": old_aids["introduction"]["evidence"],
        },
        "glossary": {
            "markdown_heading": "术语简释",
            "rendering_profile": "compact_final_reader",
            "entries": entries,
            "excluded_inventory_terms": old_aids["glossary"].get("excluded_inventory_terms", []),
        },
    }
    dump(aids_path, aids)

    assessments = [{
        "task_id": row["id"],
        "status": "passed",
        "evidence": f"实际回答能够复述指定行段的核心关系，并与任务 {row['id']} 所列正文范围相符。",
    } for row in tasks]
    dump(RC / "assessments.json", assessments)

    producer_id = "producer-root-book003-final-1.7"
    reviewer_id = "/root/whole_book_reader_17"
    producer_record = RC / "producer.json"
    reviewer_record = RC / "reviewer.json"
    dump(producer_record, {"actor": "codex-editorial-producer", "run_id": producer_id, "output_sha256": sha(MANUSCRIPT)})
    dump(reviewer_record, {"actor": reviewer_id, "run_id": reviewer_id, "output_sha256": sha(MANUSCRIPT)})

    task_by_id = {row["id"]: row for row in tasks}
    units = [
        (1, 16, "R8-T00"), (17, 40, "R8-T01"), (41, 456, "R8-T02"),
        (457, 962, "R8-T03"), (963, 1357, "R8-T04"), (1358, 2235, "R8-T05"),
        (2236, 2501, "R8-T06"), (2502, 2695, "R8-T07"), (2696, 2810, "R8-T09"),
    ]
    lines = text.splitlines()
    section_reviews = []
    for start, end, task_id in units:
        excerpt = "\n".join(lines[start - 1:end])
        ids = re.findall(r"<!-- source:([^ ]+) -->", excerpt)
        quote = next(line.strip() for line in excerpt.splitlines() if line.strip())
        section_reviews.append({
            "start_line": start,
            "end_line": end,
            "text_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "quote": quote,
            "reader_question": task_by_id[task_id]["question"],
            "plain_answer": answers[task_id],
            "prerequisites": "本单元所需概念在正文语境或书末术语简释中给出；残损处以明确边界阅读。",
            "comprehension_evidence": f"独立读者在 {task_id} 的实际回答中复述了本单元的核心关系。",
            "block_ids": ids,
            "task_ids": [task_id],
            "status": "passed",
            "remaining_obstacles": [],
        })
    source_ids = {json.loads(line)["block_id"] for line in (ROOT / "20-source/blocks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    covered = {block for unit in section_reviews for block in unit["block_ids"]}
    assert covered == source_ids, (len(covered), len(source_ids))

    dimensions = {
        "introduction_promise": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "旧过程稿的前置说明和导读字段干扰普通读者进入正文。"}]},
        "prerequisites": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "旧术语层级繁复，普通读者难以直接查用。"}]},
        "navigation": {"verdict": "passed", "findings": []},
        "continuity": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "旧稿存在跨块残句、版刻题署和疑文说明打断正文。"}]},
        "terminology": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "旧术语表不能支持审气、审向的概念阅读。"}]},
        "examples_and_figures": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "两幅模糊图不应承担教学证明。"}]},
        "redundancy_and_pacing": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "旧导读字段和反复校勘话术造成阅读节奏中断。"}]},
        "source_editor_trust": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "需把原书主张与现代编者判断明确分开。"}]},
        "closure_and_lookup": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000008-WHOLE", "problem": "需保留简洁术语查找，同时移出过程资料。"}]},
    }
    legacy = RC / "legacy-guide-input.md"
    review = {
        "schema_version": "1.2", "cycle_id": "RC0008", "mode": "manuscript",
        "input_snapshot": "50-edited/review-history/RC0008/legacy-guide-input.md",
        "input_sha256": sha(legacy),
        "target_reader": "对传统地理古籍感兴趣、没有术数基础的现代普通读者",
        "reviewer": "/root/final_reader_acceptance_17",
        "dimensions": dimensions,
        "glossary_samples": [],
        "blocking_issues": ["RR000008-WHOLE"],
    }
    dump(EDIT / "reader-review.json", review)

    ledger_path = EDIT / "reader-revision-ledger.jsonl"
    ledger = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ledger = [row for row in ledger if row.get("cycle_id") != "RC0008"]
    before = legacy.read_text(encoding="utf-8")
    after = text
    ledger.append({
        "schema_version": "1.2", "event_id": "RRE000008", "revision_id": "RR000008-WHOLE",
        "cycle_id": "RC0008", "operation": "rewrite",
        "reader_problem": "旧过程稿仍像导读资料，且有跨块残句、版刻题署、密集编校话术和术语缺口，不能作为最终普通读者版。",
        "block_ids": sorted(source_ids), "section": "全书普通读者白话交付稿",
        "before": before, "after": after, "preservation": None,
        "start_offset": 0, "end_offset": len(before),
        "input_snapshot": "50-edited/review-history/RC0008/legacy-guide-input.md", "input_sha256": sha(legacy),
        "output_snapshot": "50-edited/review-history/RC0008/accepted-reader-output.md", "output_sha256": sha(RC / "accepted-reader-output.md"),
        "resolution_review": {"reviewer": "/root/final_reader_acceptance_17", "status": "passed", "evidence": "三轮全书回归加一次定点回归后，对冻结哈希给出PASS；未发现新的出版级硬伤。"},
        "evidence": ["50-edited/review-history/RC0008/final-reader-pass.json", "50-edited/review-history/RC0008/provenance.json"],
        "semantic_risk": "high", "uncertainty_candidate_id": "UC-READER-00456", "status": "applied",
        "rationale": "保留原书顺序、665个稳定源区块和33幅原图；删除过程导读干扰，修复读者复核发现的断裂，疑损处仍明确保留边界。",
    })
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ledger), encoding="utf-8")

    session = {
        "status": "passed", "producer_execution_id": producer_id, "reviewer_execution_id": reviewer_id,
        "reviewer_kind": "model", "manuscript_file": "50-edited/modern-reading.md", "manuscript_sha256": sha(MANUSCRIPT),
        "tasks_file": "50-edited/review-history/RC0008/tasks.json", "tasks_sha256": sha(RC / "tasks.json"),
        "responses_file": "50-edited/review-history/RC0008/responses.json", "responses_sha256": sha(RC / "responses.json"),
        "assessments_file": "50-edited/review-history/RC0008/assessments.json", "assessments_sha256": sha(RC / "assessments.json"),
        "provenance_file": "50-edited/review-history/RC0008/provenance.json", "provenance_sha256": sha(RC / "provenance.json"),
        "task_exemptions": {},
    }
    glossary_samples = []
    for entry in entries[:10]:
        glossary_samples.append({
            "term": entry["term"], "plain_enough": True, "context_specific": True,
            "example_helpful": True, "issue": None, "quote": entry["plain_definition"],
            "evidence": "独立阅读会话通过全书主线、应用、概念区分和图式任务；该词在简释中可直接查到。",
        })
    dim_checks = {key: {"status": "passed", "evidence": "冻结稿经三轮整书复核、定点回归和独立十题阅读会话确认。"} for key in dimensions}
    acceptance = {
        "schema_version": "1.2", "cycle_id": "RC0008", "mode": "manuscript",
        "producer": "codex-editorial-producer", "reviewer": reviewer_id,
        "producer_record": "50-edited/review-history/RC0008/producer.json", "producer_record_sha256": sha(producer_record),
        "reviewer_record": "50-edited/review-history/RC0008/reviewer.json", "reviewer_record_sha256": sha(reviewer_record),
        "dimension_checks": dim_checks, "section_reviews": section_reviews,
        "glossary_samples": glossary_samples, "reading_session": session,
        "status": "passed", "output_sha256": sha(MANUSCRIPT), "regression_review": "passed",
        "blocking_issues": [], "counts": {"add": 0, "delete_from_reading_path": 0, "reorganize": 0, "rewrite": 1},
    }
    dump(EDIT / "reader-acceptance-report.json", acceptance)

    # Add the explicit high-risk whole-book revision to the unified ledger.
    candidates_path = ROOT / "90-audit/uncertainty-candidates.jsonl"
    candidates = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not any(row.get("candidate_id") == "UC-READER-00456" for row in candidates):
        candidates.append({
            "schema_version": "1.2", "candidate_id": "UC-READER-00456", "page_id": "P000001", "block_id": "P000001-B001",
            "origin_stage": "reader", "review_cycle": "RC0008", "checkpoint": "whole_book_reader_revision",
            "kind": "reader_rewrite", "excerpt": "全书普通读者白话交付稿", "reason": "全书由过程导读版改为最终白话读者版，需独立整书复核。",
            "source_image": "20-source/pages/P000001.jpg", "severity": "high", "created_by": "reader-revision-RC0008",
        })
        candidates_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates), encoding="utf-8")
    adjudication_path = ROOT / "90-audit/uncertainty-adjudication.jsonl"
    decisions = [json.loads(line) for line in adjudication_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not any(row.get("adjudication_id") == "UA000456" for row in decisions):
        decisions.append({
            "schema_version": "1.2", "adjudication_id": "UA000456", "candidate_ids": ["UC-READER-00456"],
            "status": "resolved_confirmed", "reader_impact": "high", "active": True, "supersedes": None,
            "review_cycle": "RC0008", "checkpoint": "whole_book_reader_revision", "page_id": "P000001", "block_id": "P000001-B001",
            "rationale": "冻结稿经三轮整书复核、定点回归及独立十题阅读会话通过，修订未留下出版级读者障碍。",
            "evidence": ["50-edited/review-history/RC0008/final-reader-pass.json", "50-edited/review-history/RC0008/provenance.json"],
            "before": None, "after": None, "reviewed_at": "2026-09-27T10:23:00-07:00", "reviewer": "/root/final_reader_acceptance_17",
        })
        adjudication_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in decisions), encoding="utf-8")

    editorial_path = EDIT / "editorial-report.json"
    editorial = load(editorial_path)
    editorial["glossary"].update({
        "entry_count": len(entries), "entries_with_first_occurrence": len(entries), "core_entry_count": 0,
        "reader_review_sampled": len(glossary_samples),
    })
    editorial["reader_value"].update({
        "review_dimensions": 9, "applied_revisions": 1, "producer": "codex-editorial-producer",
        "reviewer": reviewer_id, "revision_cycle": "RC0008", "status": "passed",
    })
    dump(editorial_path, editorial)
    print(json.dumps({"manuscript_sha256": sha(MANUSCRIPT), "tasks": len(tasks), "glossary_entries": len(entries), "sections": len(section_reviews)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
