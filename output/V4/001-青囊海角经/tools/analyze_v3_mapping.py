from __future__ import annotations

import json
import difflib
import re
import sys
from collections import defaultdict
from pathlib import Path


WORKSPACE = Path(r"D:\壮五福\风水项目\output\V4\001-青囊海角经")
sys.path.insert(0, str(WORKSPACE / "tools" / "_vendor"))
from opencc import OpenCC  # noqa: E402

V3 = Path(r"D:\壮五福\风水项目\Md\V3")
CC = OpenCC("t2s")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", CC.convert(text or ""))


def main() -> None:
    normalized = read_jsonl(WORKSPACE / "30-normalized" / "blocks.jsonl")
    segments = read_jsonl(V3 / "_work" / "segments" / "book001.jsonl")
    index: dict[str, list[dict]] = defaultdict(list)
    for segment in segments:
        value = canonical(segment["source"])
        if value:
            index[value].append(segment)
    text_blocks = [block for block in normalized if canonical(block.get("normalized_text", ""))]
    exact = [block for block in text_blocks if canonical(block["normalized_text"]) in index]
    unique = [block for block in exact if len(index[canonical(block["normalized_text"])]) == 1]
    duplicate = [block for block in exact if len(index[canonical(block["normalized_text"])]) > 1]
    unmatched = [block for block in text_blocks if canonical(block["normalized_text"]) not in index]
    segment_pairs = [(segment, canonical(segment["source"])) for segment in segments if canonical(segment["source"])]
    unmatched_best = []
    for block in unmatched:
        value = canonical(block["normalized_text"])
        scored = sorted(
            (
                (difflib.SequenceMatcher(a=value, b=segment_value, autojunk=False).ratio(), segment)
                for segment, segment_value in segment_pairs
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )[:3]
        unmatched_best.append(
            {
                "block_id": block["block_id"],
                "text": value[:160],
                "best": [
                    {"ratio": round(ratio, 4), "id": segment["id"], "source": canonical(segment["source"])[:160]}
                    for ratio, segment in scored
                ],
            }
        )
    result = {
        "v4_text_blocks": len(text_blocks),
        "exact": len(exact),
        "unique": len(unique),
        "duplicate": len(duplicate),
        "unmatched": len(unmatched),
        "canonical_characters": sum(len(canonical(block["normalized_text"])) for block in text_blocks),
        "exact_characters": sum(len(canonical(block["normalized_text"])) for block in exact),
        "unmatched_examples": unmatched_best,
    }
    result["exact_character_percent"] = round(100 * result["exact_characters"] / result["canonical_characters"], 3)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
