#!/usr/bin/env python3
"""Render every release PDF page and build full-corpus contact sheets."""

from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageStat


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "90-audit" / "rendered-pdf-audit"
AUDIT.mkdir(parents=True, exist_ok=True)
PDFS = [
    ROOT / "60-publication" / "入地眼全书·现代白话版.pdf",
    ROOT / "60-publication" / "入地眼全书·原文对照版.pdf",
]


def main() -> int:
    for old in AUDIT.glob("*-sheet-*.jpg"):
        old.unlink()
    (AUDIT / "all-pages-overview.jpg").unlink(missing_ok=True)
    report = {
        "schema_version": "1.0",
        "pdfs": [],
        "total_pages_rendered": 0,
        "render_failures": [],
        "blank_like_pages": [],
    }
    overview_tiles = []
    for pdf_path in PDFS:
        pdf = pdfium.PdfDocument(str(pdf_path))
        thumbs, sizes = [], []
        for index in range(len(pdf)):
            try:
                image = pdf[index].render(scale=0.32).to_pil().convert("RGB")
                sizes.append(image.size)
                stat = ImageStat.Stat(image.convert("L"))
                if stat.mean[0] > 252.5 and stat.var[0] < 8:
                    report["blank_like_pages"].append(
                        {"pdf": pdf_path.name, "page": index + 1}
                    )
                thumb = image.copy()
                thumb.thumbnail((180, 250))
                tile = Image.new("RGB", (190, 275), "white")
                tile.paste(thumb, ((190 - thumb.width) // 2, 18))
                ImageDraw.Draw(tile).text((5, 3), f"{index + 1}", fill="black")
                thumbs.append(tile)
            except Exception as exc:
                report["render_failures"].append(
                    {"pdf": pdf_path.name, "page": index + 1, "error": str(exc)}
                )
        sheet_paths = []
        for start in range(0, len(thumbs), 40):
            batch = thumbs[start : start + 40]
            sheet = Image.new("RGB", (190 * 5, 275 * 8), "#d9dedc")
            for offset, tile in enumerate(batch):
                sheet.paste(tile, ((offset % 5) * 190, (offset // 5) * 275))
            path = AUDIT / f"{pdf_path.stem}-sheet-{start // 40 + 1:02d}.jpg"
            sheet.save(path, quality=84)
            sheet_paths.append(path)
            mini = sheet.copy()
            mini.thumbnail((240, 560))
            overview_tiles.append((pdf_path.stem, start // 40 + 1, mini))
        report["pdfs"].append(
            {
                "name": pdf_path.name,
                "pages": len(pdf),
                "rendered": len(thumbs),
                "page_sizes": sorted({str(size) for size in sizes}),
                "contact_sheets": [str(path.relative_to(ROOT)) for path in sheet_paths],
            }
        )
        report["total_pages_rendered"] += len(thumbs)

    width = 240 * 5
    height = 590 * ((len(overview_tiles) + 4) // 5)
    overview = Image.new("RGB", (width, height), "#eef1f0")
    draw = ImageDraw.Draw(overview)
    for index, (name, number, mini) in enumerate(overview_tiles):
        x, y = (index % 5) * 240, (index // 5) * 590
        draw.text((x + 5, y + 3), f"{name[-6:]} {number}", fill="black")
        overview.paste(mini, (x, y + 25))
    overview_path = AUDIT / "all-pages-overview.jpg"
    overview.save(overview_path, quality=90)
    report["overview"] = str(overview_path.relative_to(ROOT))
    report["expected_pages"] = sum(item["pages"] for item in report["pdfs"])
    report["valid"] = (
        not report["render_failures"]
        and report["total_pages_rendered"] == report["expected_pages"]
        and all(item["rendered"] == item["pages"] for item in report["pdfs"])
    )
    (AUDIT / "render-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
