#!/usr/bin/env python3
"""Extract the verified Book 002 range from its six-book parent scan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter


PROJECT = Path(r"D:\壮五福\风水项目")
PARENT = PROJECT / "Docs" / "地学-经典" / "410.入地眼全书+玉尺经+葬经+鲁班经+选择纪全+秘诀仙机.pdf"
OUT_DIR = Path(r"D:\ocr_work\v4-book002-ingest")
OUT = OUT_DIR / "source.pdf"
MANIFEST = OUT_DIR / "slice-manifest.json"
FIRST_PAGE = 5
LAST_PAGE = 166


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    reader = PdfReader(str(PARENT))
    if reader.is_encrypted or len(reader.pages) != 346:
        raise RuntimeError("Parent PDF integrity does not match the verified intake facts")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for page_index in range(FIRST_PAGE - 1, LAST_PAGE):
        writer.add_page(reader.pages[page_index])
    with OUT.open("wb") as handle:
        writer.write(handle)
    extracted = PdfReader(str(OUT))
    if len(extracted.pages) != 162:
        raise RuntimeError(f"Expected 162 pages, got {len(extracted.pages)}")
    payload = {
        "schema_version": "1.0",
        "book_no": 2,
        "title": "入地眼全书",
        "parent_source": str(PARENT),
        "parent_sha256": sha256(PARENT),
        "parent_bytes": PARENT.stat().st_size,
        "parent_pages": len(reader.pages),
        "range_first_page": FIRST_PAGE,
        "range_last_page": LAST_PAGE,
        "range_pages": len(extracted.pages),
        "range_basis": "V2/V3 source declaration plus visual boundary verification of parent pages 4-6 and 165-168",
        "extracted_source": str(OUT),
        "extracted_sha256": sha256(OUT),
        "extracted_bytes": OUT.stat().st_size,
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
