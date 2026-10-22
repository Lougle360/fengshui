#!/usr/bin/env python3
"""Create Book 003's reversible simplified-Chinese normalization layer."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
MASTER_LEDGER = ROOT.parent / "V4交付总账.json"
sys.path.insert(0, str(PROJECT / "output" / "V4" / "001-青囊海角经" / "tools" / "_vendor"))

from opencc import OpenCC  # noqa: E402


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def punctuation_normalize(text: str) -> str:
    # Typography only. Sentence boundaries remain evidence-neutral.
    text = re.sub(r"(?<=[\u3400-\u9fff])[?](?=[\u3400-\u9fff]|$)", "？", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])[!](?=[\u3400-\u9fff]|$)", "！", text)
    text = re.sub(r"(?<=[\u3400-\u9fff]);(?=[\u3400-\u9fff]|$)", "；", text)
    text = re.sub(r"(?<=[\u3400-\u9fff]):(?=[\u3400-\u9fff])", "：", text)
    return text


def whitespace_normalize(text: str) -> str:
    lines = [re.sub(r"[\t\u3000 ]+", " ", line).strip() for line in text.replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def changes_for(block_id: str, before: str, after: str, operation: str, rule: str, timestamp: str) -> list[dict]:
    if before == after:
        return []
    changes = []
    serial = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        serial += 1
        changes.append({
            "schema_version": "1.0", "change_id": f"{block_id}-{operation}-{serial:03d}",
            "block_id": block_id, "source_span": [i1, i2], "before": before[i1:i2], "after": after[j1:j2],
            "operation": operation, "rule_or_evidence": rule, "confidence": 0.99,
            "reviewer_state": "auto_verified_reversible", "created_at": timestamp,
        })
    return changes


def main() -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    source_path = ROOT / "20-source" / "blocks.jsonl"
    source = read_jsonl(source_path)
    if not source:
        raise RuntimeError("Source layer is empty")
    converter = OpenCC("t2s")
    output, changes = [], []
    counts: Counter[str] = Counter()
    markdown = ["# 平砂玉尺经：规范化原文", ""]
    previous_page = None

    for record in source:
        block_id = record["block_id"]
        source_text = record.get("source_text") or ""
        simplified = converter.convert(source_text)
        step = changes_for(block_id, source_text, simplified, "script_conversion", "OpenCC t2s; source remains in same record", timestamp)
        changes.extend(step); counts["script_conversion"] += len(step)
        punctuated = punctuation_normalize(simplified)
        step = changes_for(block_id, simplified, punctuated, "punctuation", "Full-width punctuation only; no inferred sentence split", timestamp)
        changes.extend(step); counts["punctuation"] += len(step)
        normalized = whitespace_normalize(punctuated)
        step = changes_for(block_id, punctuated, normalized, "whitespace", "Trim/collapse layout whitespace without changing word order", timestamp)
        changes.extend(step); counts["whitespace"] += len(step)

        item = dict(record)
        item.update({
            "normalized_text": normalized, "modern_text": None, "operation": "normalized",
            "language": "zh-Hans" if normalized else record.get("language", "und"),
            "normalization_operations": [name for name, changed in (
                ("script_conversion", source_text != simplified), ("punctuation", simplified != punctuated),
                ("whitespace", punctuated != normalized),
            ) if changed],
        })
        output.append(item)
        if previous_page != record["page_id"]:
            markdown.extend([f"## 原书第 {record['source_page']} 页 {{{record['page_id']}}}", ""])
            previous_page = record["page_id"]
        if record["block_type"] == "title" and normalized:
            markdown.extend([f"### {normalized}", ""])
        elif record["block_type"] in {"figure", "table"}:
            markdown.extend([f"![{record['block_type']} {block_id}](../20-source/pages/{record['page_id']}.jpg)", ""])
        elif normalized:
            markdown.extend([normalized, ""])
        else:
            markdown.extend([f"> [{record['block_type']}：沿用 {record['page_id']} 图像证据]", ""])

    source_ids, output_ids = [row["block_id"] for row in source], [row["block_id"] for row in output]
    if source_ids != output_ids or len(set(output_ids)) != len(output_ids):
        raise RuntimeError("Block identity or ordering changed")
    lost = [dst["block_id"] for src, dst in zip(source, output) if (src.get("source_text") or "").strip() and not (dst.get("normalized_text") or "").strip()]
    if lost:
        raise RuntimeError(f"Normalization lost text in {len(lost)} blocks")

    out_dir = ROOT / "30-normalized"
    blocks_path, changes_path, md_path = out_dir / "blocks.jsonl", out_dir / "changes.jsonl", out_dir / "normalized.md"
    blocks_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8")
    changes_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in changes), encoding="utf-8")
    md_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")
    write_json(out_dir / "terminology-decisions.json", {
        "schema_version": "1.0", "target_script": "zh-Hans", "converter": "opencc-python-reimplemented / t2s",
        "protected_domain_terms": ["龙", "穴", "砂", "水", "向", "峦头", "理气", "挨星", "纳甲", "乾", "坤", "坎", "离", "震", "巽", "艮", "兑", "河图", "洛书", "九星"],
        "policy": "Only orthography, typography punctuation, and whitespace are normalized; names and uncertain glyphs remain traceable to source_text.",
    })
    report = {
        "schema_version": "1.0", "generated_at": timestamp, "status": "passed",
        "source_blocks": len(source), "normalized_blocks": len(output), "identity_match": source_ids == output_ids,
        "lost_text_blocks": lost, "change_records": len(changes), "operation_counts": dict(counts),
        "source_sha256": sha256(source_path), "normalized_blocks_sha256": sha256(blocks_path),
        "normalized_md_sha256": sha256(md_path), "changes_sha256": sha256(changes_path),
        "semantic_paraphrase_operations": 0, "tool_cost_rmb": 0,
    }
    write_json(out_dir / "normalization-report.json", report)

    state = read_json(ROOT / "run-state.json")
    state["updated_at"] = timestamp; state["current_stage"] = "modernized"
    state["stages"]["normalized"] = {
        "status": "passed", "blocks": len(output), "change_records": len(changes),
        "operation_counts": dict(counts), "tool": "OpenCC t2s + conservative typography", "paid_cost_rmb": 0,
        "evidence": "30-normalized/normalization-report.json",
    }
    state["stages"]["modernized"] = {"status": "running"}
    write_json(ROOT / "run-state.json", state)
    append_jsonl(ROOT / "90-audit" / "events.jsonl", {
        "schema_version": "1.0", "event": "stage_gate", "stage": "normalized", "status": "passed",
        "time": timestamp, "actor": "build_normalized_layer.py", "counts": {"blocks": len(output), "changes": len(changes)},
        "rationale": "All source block identities were preserved and every orthographic/typographic change is reversible; no paraphrase operation was used.",
    })
    ledger = read_json(MASTER_LEDGER)
    item = next(row for row in ledger["books"] if int(row["book_no"]) == 3)
    item.update({"status": "normalized", "current_stage": "modernization", "normalized_blocks": len(output), "normalization_gate": "passed", "updated_at": timestamp})
    ledger["updated_at"] = timestamp
    write_json(MASTER_LEDGER, ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
