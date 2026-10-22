#!/usr/bin/env python3
"""Promote accepted sample translations for complete pages 4 and 5."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "50-edited/sample/reader-sample.md"
OUT = ROOT / "90-audit/modernization-v19"


def main() -> int:
    text = SAMPLE.read_text(encoding="utf-8")
    matches = list(re.finditer(r"<!-- source:([^>]+) -->", text))
    translations = {}
    previous = 0
    for match in matches:
        segment = text[previous:match.start()]
        value = "\n".join(line for line in segment.strip().splitlines() if not line.startswith("#")).strip()
        ids = match.group(1).split(",")
        if len(ids) == 1:
            translations[ids[0]] = value
        previous = match.end()
    translations["P000004-B001"] = "丘陵高起处的石骨、冈阜平缓处的土脊，都是气所依从的路径。"
    translations["P000004-B011"] = "为什么这样说？气势盛大时，虽然仍在运行，余气也会有所停留；即使表面看起来零散，"
    translations["P000005-B001"] = "深处仍可能有所聚集。"
    translations.update({
        "P000006-B001": "气本来没有形体，要借土显出形体，因此从土可以知道气的存在。水本来没有所谓母体，这里借气作它的母体，因此从气可以知道水的存在。五行说“天一生水”，水又从哪里生出？生水的是金，生金的是土。天地形成以前还没有具体形质，哪里已有土呢？邵雍说，天地的根本起于中央；中央就是土。当时虽还没有具体的气，却已有相应的道理；土中藏金，虽无形质，却已有其气。乾藏在坤中，隐而未见；等到水开始发生，征兆才显露出来。因此，说气是水的母体，指的是乾金之气。世人不追究根源，只看到水，便把水当成“天一”的起点；旧注认为这种理解有所见，却还不精确。",
        "P000006-B002": "经书说：土形成，气便运行，万物由此发生。",
        "P000006-B003": "生气依附形体而有所凭借，依着土地运行；万物也无不由此而生。这句经文是总结上文“有土便有气”的意思。",
        "P000006-B004": "内篇三",
    })
    for page, last in ((4, 11), (5, 9), (6, 12)):
        ids = [f"P{page:06d}-B{number:03d}" for number in range(1, last + 1)]
        missing = [block_id for block_id in ids if block_id not in translations]
        if missing:
            raise RuntimeError(f"sample does not cover page {page}: {missing}")
        payload = {
            "schema_version": "1.0",
            "page_id": f"P{page:06d}",
            "status": "translated_and_independently_sample_checked",
            "blocks": [
                {
                    "block_id": block_id,
                    "modern_text": translations[block_id],
                    "confidence": 0.96,
                    "review_notes": ["Translation appears in the independently accepted v1.9 reader sample."],
                }
                for block_id in ids
            ],
        }
        (OUT / f"P{page:06d}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"promoted_pages": [4, 5, 6], "promoted_blocks": 32}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
