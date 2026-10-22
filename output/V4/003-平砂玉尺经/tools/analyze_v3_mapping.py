#!/usr/bin/env python3
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[2]
sys.path.insert(0, str(PROJECT / "output" / "V4" / "001-青囊海角经" / "tools" / "_vendor"))
from opencc import OpenCC  # noqa: E402

CC = OpenCC("t2s")


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", CC.convert(text or ""))


def main() -> int:
    normalized = rows(ROOT / "30-normalized" / "blocks.jsonl")
    segments = rows(PROJECT / "Md" / "V3" / "_work" / "segments" / "book003.jsonl")
    index = defaultdict(list)
    for segment in segments:
        value = canonical(segment.get("source", ""))
        if value:
            index[value].append(segment)
    text_blocks = [block for block in normalized if canonical(block.get("normalized_text", ""))]
    joined_v4 = "".join(canonical(block["normalized_text"]) for block in text_blocks)
    global_exact_segments = [segment for segment in segments if canonical(segment.get("source", "")) and canonical(segment["source"]) in joined_v4]
    exact = [block for block in text_blocks if canonical(block["normalized_text"]) in index]
    unmatched = [block for block in text_blocks if canonical(block["normalized_text"]) not in index]
    pairs = [(segment, canonical(segment["source"])) for segment in segments if canonical(segment.get("source", ""))]
    examples = []
    for block in unmatched:
        value = canonical(block["normalized_text"])
        best = sorted(((difflib.SequenceMatcher(a=value, b=source, autojunk=False).ratio(), segment, source) for segment, source in pairs), reverse=True, key=lambda row: row[0])[:3]
        examples.append({
            "block_id": block["block_id"], "page": block["source_page"], "text": value[:160],
            "best": [{"ratio": round(ratio, 4), "id": segment["id"], "source": source[:160]} for ratio, segment, source in best],
        })
    payload = {
        "v4_text_blocks": len(text_blocks), "exact": len(exact), "unmatched": len(unmatched),
        "canonical_characters": sum(len(canonical(block["normalized_text"])) for block in text_blocks),
        "exact_characters": sum(len(canonical(block["normalized_text"])) for block in exact),
        "exact_character_percent": round(100 * sum(len(canonical(block["normalized_text"])) for block in exact) / sum(len(canonical(block["normalized_text"])) for block in text_blocks), 3),
        "global_exact_segments": len(global_exact_segments),
        "global_exact_segment_characters": sum(len(canonical(segment["source"])) for segment in global_exact_segments),
        "unmatched_examples": examples,
    }
    (ROOT / "40-modernized" / "v3-mapping-analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "unmatched_examples"}, ensure_ascii=False, indent=2))
    print(json.dumps(examples[:25], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
