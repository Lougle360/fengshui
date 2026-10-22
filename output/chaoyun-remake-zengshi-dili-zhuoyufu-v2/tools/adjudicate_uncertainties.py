#!/usr/bin/env python3
"""Preserve and adjudicate the original 99-item uncertainty ledger."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "90-audit" / "uncertain-items.jsonl"
OUTPUT = ROOT / "90-audit" / "uncertainty-adjudication.jsonl"

# One representative remains open when the old ledger repeated the same doubt.
OPEN_MATERIAL = {4, 18, 23, 34, 36, 39, 47, 77, 80, 84, 85, 86, 96, 97}
STRUCTURAL = {5, 6, 7, 8, 9, 11, 12, 22, 24, 26, 27, 30, 33, 37, 45, 50, 68, 79, 81, 89, 91, 92, 93}
NONCONTENT = {1, 28, 29, 35, 38, 46, 48, 49, 58, 66, 74, 75, 78, 90, 94, 95, 98, 99}
DUPLICATES = {19, 20, 21, 25, 31, 32, 87, 88}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    if OUTPUT.exists():
        rows = load_jsonl(OUTPUT)
        original = [row for row in rows if row.get("origin") == "original_99"]
        if len(original) == 99:
            print(json.dumps({"preserved": 99, "status_counts": Counter(row["status"] for row in rows)}, ensure_ascii=False, default=dict))
            return 0
    source = load_jsonl(LEDGER)
    if len(source) != 99:
        raise SystemExit(f"expected the original 99-item ledger, found {len(source)}")
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for index, item in enumerate(source, 1):
        if index in OPEN_MATERIAL:
            status = "open_material"
            rationale = "原图或旧刻仍不足以支持唯一读法；保留一个面向读者的实质疑点。"
        elif index in NONCONTENT:
            status = "resolved_noncontent"
            rationale = "复核确认属于馆藏章、页边墨迹或非正文标记，不应计作正文缺失。"
        elif index in STRUCTURAL:
            status = "resolved_structural"
            rationale = "复核确认属于跨页续文、版面关系、编者说明或完整性提示，不是未识读正文。"
        elif index in DUPLICATES:
            status = "resolved_duplicate"
            rationale = "与同页已保留疑点重复或为同一模型判断的拆分记录，合并处理。"
        else:
            status = "resolved_confirmed"
            rationale = "依据原页字形、成组对举、上下文或异体字规则复核后，可作确定处理。"
        rows.append({
            "schema_version": "1.0",
            "adjudication_id": f"U{index:03d}",
            "origin": "original_99",
            "original": item,
            "status": status,
            "rationale": rationale,
            "reviewed_at": now,
            "reviewer": "chaoyun-source-reconstructor",
        })
    rows.append({
        "schema_version": "1.0",
        "adjudication_id": "NEW-001",
        "origin": "review_discovery",
        "original": {"page_id": "P000080", "source_image": "20-source/pages/P000080.jpg"},
        "status": "open_material",
        "rationale": "复核时发现现存扫描最后一页在‘掌衡曰……’处戛然而止；这是原99项未正确记录的真实卷末残缺。",
        "reviewed_at": now,
        "reviewer": "chaoyun-source-reconstructor",
    })
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    counts = Counter(row["status"] for row in rows)
    print(json.dumps({"preserved": 99, "new_findings": 1, "status_counts": dict(counts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
