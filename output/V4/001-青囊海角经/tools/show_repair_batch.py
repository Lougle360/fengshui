from __future__ import annotations

import argparse
import json
from pathlib import Path


MODERN = Path(r"D:\壮五福\风水项目\output\V4\001-青囊海角经\40-modernized")
QUEUE = MODERN / "repair-queue.remaining.jsonl"
if not QUEUE.exists():
    QUEUE = MODERN / "repair-queue.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=16)
    args = parser.parse_args()
    rows = [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = rows[args.offset : args.offset + args.count]
    chunks = []
    for index, row in enumerate(selected, args.offset + 1):
        chunks.append(
            "\n".join(
                [
                    f"### {index} {row['v3_segment_id']}",
                    f"SOURCE: {row['source']}",
                    f"DRAFT: {row['draft_modern_text']}",
                    "ISSUES: " + " | ".join(row.get("issues") or []),
                    "UNCERTAINTY: " + " | ".join(row.get("uncertainty") or []),
                ]
            )
        )
    print("\n\n".join(chunks))


if __name__ == "__main__":
    main()
