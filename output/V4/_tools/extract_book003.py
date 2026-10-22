#!/usr/bin/env python3
"""Extract and hash the verified Book 003 page range from the omnibus scan."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader, PdfWriter


PARENT = Path(
    r"D:\壮五福\风水项目\Docs\地学-经典\410.入地眼全书+玉尺经+葬经+鲁班经+选择纪全+秘诀仙机.pdf"
)
OUT_DIR = Path(r"D:\ocr_work\v4-book003-ingest")
OUT = OUT_DIR / "source.pdf"
MANIFEST = OUT_DIR / "slice-manifest.json"
FIRST_PAGE = 167
LAST_PAGE = 252


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    reader = PdfReader(str(PARENT))
    if len(reader.pages) != 346:
        raise RuntimeError(f"Expected 346 parent pages, got {len(reader.pages)}")
    writer = PdfWriter()
    for index in range(FIRST_PAGE - 1, LAST_PAGE):
        writer.add_page(reader.pages[index])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT.open("wb") as handle:
        writer.write(handle)
    extracted_pages = len(PdfReader(str(OUT)).pages)
    if extracted_pages != 86:
        raise RuntimeError(f"Expected 86 extracted pages, got {extracted_pages}")
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "book_no": 3,
        "title": "平砂玉尺经",
        "parent_source": str(PARENT),
        "parent_pages": len(reader.pages),
        "parent_bytes": PARENT.stat().st_size,
        "parent_sha256": sha256(PARENT),
        "parent_page_range_inclusive": [FIRST_PAGE, LAST_PAGE],
        "extracted_source": str(OUT),
        "extracted_pages": extracted_pages,
        "extracted_bytes": OUT.stat().st_size,
        "extracted_sha256": sha256(OUT),
        "range_evidence": "Md/V2/003 平砂玉尺经.md declares PDF pages 167-252; adjacent boundary pages require visual confirmation",
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
