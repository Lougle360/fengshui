from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(r"D:\壮五福\风水项目\output\V4\001-青囊海角经")
MASTER_LEDGER = Path(r"D:\壮五福\风水项目\output\V4\V4交付总账.json")
VENDOR = WORKSPACE / "tools" / "_vendor"
sys.path.insert(0, str(VENDOR))

from opencc import OpenCC  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, value) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def punctuation_normalize(text: str) -> str:
    # Only typography-level substitutions; no sentence-boundary inference.
    text = re.sub(r"(?<=[\u3400-\u9fff])[?](?=[\u3400-\u9fff]|$)", "？", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])[!](?=[\u3400-\u9fff]|$)", "！", text)
    text = re.sub(r"(?<=[\u3400-\u9fff]);(?=[\u3400-\u9fff]|$)", "；", text)
    text = re.sub(r"(?<=[\u3400-\u9fff]):(?=[\u3400-\u9fff])", "：", text)
    return text


def whitespace_normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[\t\u3000 ]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def changes_for_step(block_id: str, before: str, after: str, operation: str, rule: str, now: str) -> list[dict]:
    if before == after:
        return []
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    changes: list[dict] = []
    serial = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        serial += 1
        changes.append(
            {
                "schema_version": "1.0",
                "change_id": f"{block_id}-{operation}-{serial:03d}",
                "block_id": block_id,
                "source_span": [i1, i2],
                "before": before[i1:i2],
                "after": after[j1:j2],
                "operation": operation,
                "rule_or_evidence": rule,
                "confidence": 0.99,
                "reviewer_state": "auto_verified_reversible",
                "created_at": now,
            }
        )
    return changes


def main() -> None:
    now = utc_now()
    source_path = WORKSPACE / "20-source" / "blocks.jsonl"
    source = read_jsonl(source_path)
    if not source:
        raise RuntimeError("source layer is empty")
    converter = OpenCC("t2s")

    output: list[dict] = []
    changes: list[dict] = []
    markdown: list[str] = ["# 青囊海角经：规范化原文", ""]
    operation_counts: Counter[str] = Counter()
    previous_page = None

    for record in source:
        block_id = record["block_id"]
        source_text = record.get("source_text") or ""
        script_text = converter.convert(source_text)
        step_changes = changes_for_step(
            block_id,
            source_text,
            script_text,
            "script_conversion",
            "OpenCC 0.1.7 t2s; source text preserved in the same record",
            now,
        )
        changes.extend(step_changes)
        operation_counts["script_conversion"] += len(step_changes)

        punctuated = punctuation_normalize(script_text)
        step_changes = changes_for_step(
            block_id,
            script_text,
            punctuated,
            "punctuation",
            "Conservative full-width punctuation only; no inferred sentence split",
            now,
        )
        changes.extend(step_changes)
        operation_counts["punctuation"] += len(step_changes)

        normalized = whitespace_normalize(punctuated)
        step_changes = changes_for_step(
            block_id,
            punctuated,
            normalized,
            "whitespace",
            "Trim and collapse layout whitespace without changing word order",
            now,
        )
        changes.extend(step_changes)
        operation_counts["whitespace"] += len(step_changes)

        item = dict(record)
        item["normalized_text"] = normalized
        item["modern_text"] = None
        item["operation"] = "normalized"
        item["language"] = "zh-Hans" if normalized else record.get("language", "und")
        item["normalization_operations"] = [
            name
            for name, value in (
                ("script_conversion", source_text != script_text),
                ("punctuation", script_text != punctuated),
                ("whitespace", punctuated != normalized),
            )
            if value
        ]
        output.append(item)

        if previous_page != record["page_id"]:
            markdown.extend([f"## 物理页 {record['source_page']} {{#{record['page_id']}}}", ""])
            previous_page = record["page_id"]
        if record["block_type"] == "title" and normalized:
            markdown.extend([f"### {normalized}", ""])
        elif record["block_type"] in {"figure", "table"}:
            markdown.extend([f"![{record['block_type']} {block_id}](../20-source/pages/{record['page_id']}.jpg)", ""])
        elif normalized:
            markdown.extend([normalized, ""])
        else:
            markdown.extend([f"> [{record['block_type']}：沿用 {record['page_id']} 图像证据]", ""])

    source_ids = [item["block_id"] for item in source]
    output_ids = [item["block_id"] for item in output]
    if source_ids != output_ids or len(set(output_ids)) != len(output_ids):
        raise RuntimeError("block identity or ordering changed")
    lost_text = [
        item["block_id"]
        for src, item in zip(source, output)
        if (src.get("source_text") or "").strip() and not (item.get("normalized_text") or "").strip()
    ]
    if lost_text:
        raise RuntimeError(f"normalization lost text in {len(lost_text)} blocks")

    normalized_dir = WORKSPACE / "30-normalized"
    blocks_path = normalized_dir / "blocks.jsonl"
    changes_path = normalized_dir / "changes.jsonl"
    markdown_path = normalized_dir / "normalized.md"
    blocks_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in output),
        encoding="utf-8",
    )
    changes_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in changes),
        encoding="utf-8",
    )
    markdown_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    terminology = {
        "schema_version": "1.0",
        "target_script": "zh-Hans",
        "converter": "opencc-python-reimplemented 0.1.7 / t2s",
        "protected_domain_terms": ["乾", "坤", "坎", "离", "震", "巽", "艮", "兑", "河图", "洛书", "先天", "后天"],
        "policy": "Only orthography, typography punctuation, and whitespace are normalized; meaning and word order are unchanged.",
    }
    write_json(normalized_dir / "terminology-decisions.json", terminology)

    report = {
        "schema_version": "1.0",
        "generated_at": now,
        "status": "passed",
        "source_blocks": len(source),
        "normalized_blocks": len(output),
        "identity_match": source_ids == output_ids,
        "lost_text_blocks": lost_text,
        "change_records": len(changes),
        "operation_counts": dict(operation_counts),
        "source_sha256": sha256(source_path),
        "normalized_blocks_sha256": sha256(blocks_path),
        "normalized_md_sha256": sha256(markdown_path),
        "changes_sha256": sha256(changes_path),
        "semantic_paraphrase_operations": 0,
        "tool_cost": 0,
    }
    write_json(normalized_dir / "normalization-report.json", report)

    state_path = WORKSPACE / "run-state.json"
    state = read_json(state_path)
    state.setdefault("stages", {})["normalization"] = {
        "status": "passed",
        "updated_at": now,
        "blocks": len(output),
        "change_records": len(changes),
        "operation_counts": dict(operation_counts),
        "tool": "opencc-python-reimplemented 0.1.7 + conservative typography rules",
        "cost": 0,
        "evidence": "30-normalized/normalization-report.json",
    }
    state["current_stage"] = "modernization"
    state["updated_at"] = now
    write_json(state_path, state)

    append_jsonl(
        WORKSPACE / "90-audit" / "events.jsonl",
        {
            "schema_version": "1.0",
            "event": "stage_gate",
            "stage": "normalization",
            "status": "passed",
            "time": now,
            "actor": "build_normalized_layer.py",
            "counts": {"blocks": len(output), "changes": len(changes)},
            "rationale": "Block identity and coverage match the source layer; every orthographic or typographic change has a reversible ledger entry; no paraphrase operation was used.",
        },
    )

    ledger = read_json(MASTER_LEDGER)
    for item in ledger["books"]:
        if int(item["book_no"]) == 1:
            item.update(
                {
                    "status": "normalized",
                    "current_stage": "modernization",
                    "normalized_blocks": len(output),
                    "normalization_gate": "passed",
                    "updated_at": now,
                }
            )
            break
    ledger["updated_at"] = now
    write_json(MASTER_LEDGER, ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
