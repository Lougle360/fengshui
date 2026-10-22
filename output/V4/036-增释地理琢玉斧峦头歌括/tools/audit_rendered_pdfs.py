from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageStat


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "90-audit" / "rendered-pdf-audit"
AUDIT.mkdir(parents=True, exist_ok=True)
PDFS = [
    ROOT / "60-publication" / "增释地理琢玉斧峦头歌括·现代白话版.pdf",
    ROOT / "60-publication" / "增释地理琢玉斧峦头歌括·原文对照版.pdf",
]


def main() -> None:
    for old in AUDIT.glob("*.jpg"):
        old.unlink()
    report = {"schema_version": "1.0", "pdfs": [], "total_pages_rendered": 0,
              "render_failures": [], "blank_like_pages": []}
    for pdf_path in PDFS:
        pdf = pdfium.PdfDocument(str(pdf_path))
        tiles = []
        for index in range(len(pdf)):
            try:
                image = pdf[index].render(scale=0.32).to_pil().convert("RGB")
                stat = ImageStat.Stat(image.convert("L"))
                if stat.mean[0] > 252.5 and stat.var[0] < 8:
                    report["blank_like_pages"].append({"pdf": pdf_path.name, "page": index + 1})
                image.thumbnail((180, 250))
                tile = Image.new("RGB", (190, 275), "white")
                tile.paste(image, ((190 - image.width) // 2, 18))
                ImageDraw.Draw(tile).text((5, 3), str(index + 1), fill="black")
                tiles.append(tile)
            except Exception as exc:
                report["render_failures"].append({"pdf": pdf_path.name, "page": index + 1, "error": str(exc)})
        sheets = []
        for start in range(0, len(tiles), 40):
            sheet = Image.new("RGB", (950, 2200), "#d9dedc")
            for offset, tile in enumerate(tiles[start:start + 40]):
                sheet.paste(tile, ((offset % 5) * 190, (offset // 5) * 275))
            path = AUDIT / f"{pdf_path.stem}-sheet-{start // 40 + 1:02d}.jpg"
            sheet.save(path, quality=84)
            sheets.append(str(path.relative_to(ROOT)))
        report["pdfs"].append({"name": pdf_path.name, "pages": len(pdf),
                               "rendered": len(tiles), "contact_sheets": sheets})
        report["total_pages_rendered"] += len(tiles)
    expected = sum(item["pages"] for item in report["pdfs"])
    report["expected_pages"] = expected
    report["valid"] = not report["render_failures"] and report["total_pages_rendered"] == expected
    (AUDIT / "render-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
