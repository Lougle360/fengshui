#!/usr/bin/env python3
"""Import a MinerU API result into the Chaoyun source-stage contract."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from statistics import mean


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def span_text(block: dict) -> tuple[str, list[float]]:
    lines: list[str] = []
    scores: list[float] = []
    for line in block.get("lines", []):
        parts: list[str] = []
        for span in line.get("spans", []):
            content = span.get("content")
            if isinstance(content, str) and content:
                parts.append(content)
            score = span.get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))
        if parts:
            lines.append("".join(parts))
    return "\n".join(lines), scores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--result-name", default=None)
    parser.add_argument("--start-source-page", type=int, required=True)
    parser.add_argument("--language", default="lzh")
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    book = json.loads((workspace / "book.json").read_text(encoding="utf-8"))
    payload = json.loads(args.result_json.expanduser().resolve().read_text(encoding="utf-8"))
    results = payload.get("results")
    if not isinstance(results, dict) or not results:
        parser.error("result_json has no MinerU results")
    name = args.result_name or next(iter(results))
    if name not in results:
        parser.error(f"result not found: {name}")
    result = results[name]
    middle = json.loads(result["middle_json"])
    pages = middle.get("pdf_info")
    if not isinstance(pages, list) or not pages:
        parser.error("middle_json has no pdf_info pages")

    source_dir = workspace / "20-source"
    images_dir = source_dir / "images"
    pages_dir = source_dir / "pages"
    images_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "mineru.md").write_text(result.get("md_content", ""), encoding="utf-8")
    write_json(source_dir / "mineru-middle.json", middle)

    for filename, data_url in result.get("images", {}).items():
        if not isinstance(data_url, str) or "," not in data_url:
            continue
        header, encoded = data_url.split(",", 1)
        if not header.startswith("data:image/"):
            continue
        (images_dir / Path(filename).name).write_bytes(base64.b64decode(encoded))

    records: list[dict] = []
    markdown: list[str] = [f"# {book.get('title', name)} — 忠实原文样章", ""]
    for page_offset, page in enumerate(pages):
        source_page = args.start_source_page + page_offset
        page_id = f"P{source_page:06d}"
        page_image = f"20-source/pages/{page_id}.png"
        markdown.extend([f"## 原 PDF 第 {source_page} 页", "", f"![原页](pages/{page_id}.png)", ""])
        page_blocks = page.get("para_blocks", [])
        if not page_blocks:
            page_blocks = [{"type": "unknown", "bbox": None, "lines": [], "score": 0.0}]
        for block_index, block in enumerate(page_blocks, 1):
            text, scores = span_text(block)
            block_type = block.get("type", "unknown")
            confidence = mean(scores) if scores else float(block.get("score") or 0.0)
            disposition = "retained" if text or block_type in {"image", "table", "figure"} else "unreadable"
            block_id = f"{page_id}-B{block_index:03d}"
            notes = []
            if block.get("lines_deleted"):
                notes.append("MinerU detected a region but deleted its OCR lines")
            record = {
                "schema_version": "1.0",
                "book_id": book["book_id"],
                "page_id": page_id,
                "block_id": block_id,
                "source_page": source_page,
                "block_type": block_type,
                "bbox": block.get("bbox"),
                "source_image": page_image,
                "source_text": text,
                "normalized_text": None,
                "modern_text": None,
                "language": args.language,
                "operation": "source",
                "disposition": disposition,
                "confidence": round(confidence, 4),
                "evidence": ["20-source/mineru-middle.json", page_image],
                "notes": notes,
            }
            records.append(record)
            if text:
                markdown.extend([f"<!-- {block_id} -->", text, ""])
            elif block_type in {"image", "table", "figure"}:
                markdown.extend([f"<!-- {block_id}: visual block retained in original page image -->", ""])
            else:
                markdown.extend([f"<!-- {block_id}: unreadable OCR region; see original page -->", ""])

    with (source_dir / "blocks.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (source_dir / "source.md").write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps({"pages": len(pages), "blocks": len(records), "workspace": str(workspace)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
