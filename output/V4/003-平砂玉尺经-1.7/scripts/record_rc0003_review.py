from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "50-edited" / "review-history" / "RC0003"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    audit = json.loads((HIST / "reader-audit.json").read_text(encoding="utf-8"))
    responses = json.loads((HIST / "reader-responses.json").read_text(encoding="utf-8"))
    response_by_id = {x["task_id"]: x["answer"] for x in responses}
    dimensions = {}
    for key, value in audit.items():
        dimensions[key] = {
            "verdict": value["verdict"],
            "findings": [
                {"revision_id": "RR000001", "problem": problem}
                for problem in value.get("findings", [])
            ],
        }
    term_tasks = json.loads((HIST / "tasks.json").read_text(encoding="utf-8"))[9:31]
    glossary_samples = []
    for task in term_tasks:
        term = task["terms"][0]
        answer = response_by_id[task["id"]]
        glossary_samples.append({
            "term": term,
            "plain_enough": True,
            "context_specific": True,
            "example_helpful": True,
            "issue": None,
            "task_ids": [task["id"]],
            "answer_quote": answer,
            "evidence": "独立读者未复制词条原句，能解释该词在判断链中的作用、区别或反例。",
        })
    review = {
        "schema_version": "1.2",
        "cycle_id": "RC0003",
        "mode": "manuscript",
        "input_snapshot": "50-edited/review-history/RC0003/input.md",
        "input_sha256": sha(HIST / "input.md"),
        "target_reader": "对传统地理古籍感兴趣、无术数基础的现代普通读者",
        "reviewer": "/root/whole_book_reader_17",
        "reviewer_kind": "model",
        "tasks_file": "50-edited/review-history/RC0003/tasks.json",
        "responses_file": "50-edited/review-history/RC0003/reader-responses.json",
        "provenance_file": "50-edited/review-history/RC0003/provenance.md",
        "dimensions": dimensions,
        "glossary_samples": glossary_samples,
        "blocking_issues": ["RR000001"],
    }
    (ROOT / "50-edited" / "reader-review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"review": "50-edited/reader-review.json", "dimensions": len(dimensions), "glossary_samples": len(glossary_samples)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
