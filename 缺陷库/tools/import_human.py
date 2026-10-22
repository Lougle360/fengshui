"""Convert the filled table in 人工意见录入表.md into human-defects.jsonl (same fields as defects.jsonl)."""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
LIB = Path(r"D:\壮五福\风水项目\缺陷库")
SRC = LIB / "人工意见录入表.md"
OUT = LIB / "human-defects.jsonl"

COLUMNS = ["编号", "书", "版本", "位置", "问题描述", "原文", "现在的写法", "应该怎么改", "类别", "严重程度", "您的判断", "截图"]
OUTCOME = {"必须改": "must_fix", "最好改": "should_fix", "可以接受": "acceptable", "退回": "rejected_by_user"}


def entry_rows(md):
    lines = md.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| 编号 | 书 |"))
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(COLUMNS):
            print("skip malformed row:", line)
            continue
        yield dict(zip(COLUMNS, cells))


def main():
    out = []
    for row in entry_rows(SRC.read_text(encoding="utf-8")):
        if not row["问题描述"] or row["问题描述"].startswith("（示例）"):
            continue
        m = re.match(r"(\d{3})", row["书"])
        out.append({
            "defect_id": row["编号"],
            "book": m.group(1) if m else row["书"],
            "version": row["版本"] or "当前版",
            "versions": [row["版本"] or "当前版"],
            "location": {"text": row["位置"]},
            "category": row["类别"] or None,
            "subcategory": None,
            "caused_at": None,
            "found_at": "人工审读",
            "severity": row["严重程度"] or None,
            "outcome": OUTCOME.get(row["您的判断"], row["您的判断"] or None),
            "is_false_alarm": row["您的判断"] == "可以接受",
            "rework_cost": None,
            "before": row["原文"] or None,
            "after": row["现在的写法"] or None,
            "suggested": row["应该怎么改"] or None,
            "description": row["问题描述"],
            "reason": None,
            "record_kind": "human_review",
            "source_type": "human",
            "closure_template": False,
            "occurrences": 1,
            "evidence": f"人工意见录入表.md#{row['编号']}" + (f" ; 人工截图/{row['截图']}" if row["截图"] else ""),
            "ref_id": row["编号"],
        })
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print("wrote", OUT, len(out), "records")


if __name__ == "__main__":
    main()
