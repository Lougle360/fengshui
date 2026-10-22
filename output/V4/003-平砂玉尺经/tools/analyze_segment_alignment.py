#!/usr/bin/env python3
"""Analyze monotonic shingle anchors between V3 segments and V4 source blocks."""

from __future__ import annotations

import bisect
import json
import re
import statistics
import sys
from collections import Counter
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


def unique_anchors(source: str, corpus: str, width: int) -> list[tuple[int, int]]:
    anchors = []
    step = max(1, width // 2)
    for offset in range(0, max(1, len(source) - width + 1), step):
        shingle = source[offset : offset + width]
        if len(shingle) < width:
            continue
        first = corpus.find(shingle)
        if first >= 0 and corpus.find(shingle, first + 1) < 0:
            anchors.append((offset, first))
    return anchors


def main() -> int:
    blocks = [row for row in rows(ROOT / "30-normalized" / "blocks.jsonl") if canonical(row.get("normalized_text", ""))]
    segments = rows(PROJECT / "Md" / "V3" / "_work" / "segments" / "book003.jsonl")
    block_starts, block_ranges, corpus_parts = [], [], []
    cursor = 0
    for block in blocks:
        value = canonical(block["normalized_text"])
        block_starts.append(cursor)
        block_ranges.append((cursor, cursor + len(value), block["block_id"], block["source_page"]))
        corpus_parts.append(value)
        cursor += len(value)
    corpus = "".join(corpus_parts)
    alignments = []
    unmapped = []
    mapped_blocks = set()
    for segment in segments:
        source = canonical(segment.get("source", ""))
        if not source:
            alignments.append({"id": segment["id"], "status": "nontext", "block_ids": []})
            continue
        anchors = unique_anchors(source, corpus, 12)
        width = 12
        if not anchors:
            anchors = unique_anchors(source, corpus, 8)
            width = 8
        if anchors:
            monotonic_chain = []
            last_b = -1
            for spos, bpos in sorted(anchors):
                if bpos > last_b:
                    monotonic_chain.append((spos, bpos))
                    last_b = bpos
            filtered = monotonic_chain
            first_s, first_b = filtered[0]
            last_s, last_b = filtered[-1]
            start = max(0, first_b - first_s)
            end = min(len(corpus), last_b + (len(source) - last_s))
            overlaps = [item for item in block_ranges if item[0] < end and item[1] > start]
            plausible_span = end > start and end - start <= max(len(source) * 2, len(source) + 500)
            if overlaps and plausible_span:
                block_ids = [item[2] for item in overlaps]
                mapped_blocks.update(block_ids)
                alignments.append({
                    "id": segment["id"], "status": "anchored", "anchor_width": width,
                    "unique_anchors": len(anchors), "consistent_anchors": len(filtered),
                    "estimated_start": start, "estimated_end": end, "block_ids": block_ids,
                    "source_pages": sorted({item[3] for item in overlaps}),
                })
                continue
        unmapped.append({"id": segment["id"], "source": segment.get("source"), "length": len(source), "translatable": segment.get("translatable"), "kind": segment.get("kind")})
        alignments.append({"id": segment["id"], "status": "unmapped", "block_ids": []})

    uncovered_blocks = [
        {"block_id": block["block_id"], "source_page": block["source_page"], "block_type": block["block_type"], "length": len(canonical(block["normalized_text"])), "text": block["normalized_text"][:300]}
        for block in blocks if block["block_id"] not in mapped_blocks
    ]
    payload = {
        "schema_version": "1.0", "v4_canonical_characters": len(corpus), "v4_text_blocks": len(blocks),
        "v3_segments": len(segments), "alignment_status_counts": dict(Counter(row["status"] for row in alignments)),
        "mapped_v4_blocks": len(mapped_blocks), "uncovered_v4_blocks": len(uncovered_blocks),
        "uncovered_v4_characters": sum(row["length"] for row in uncovered_blocks),
        "alignments": alignments, "unmapped_segments": unmapped, "uncovered_blocks": uncovered_blocks,
    }
    path = ROOT / "40-modernized" / "segment-alignment-analysis.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key not in {"alignments", "unmapped_segments", "uncovered_blocks"}}, ensure_ascii=False, indent=2))
    print(json.dumps({"unmapped_segments": unmapped[:30], "uncovered_blocks": uncovered_blocks[:30]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
