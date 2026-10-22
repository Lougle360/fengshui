from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageStat


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "90-audit" / "rendered-pdf-audit"
AUDIT.mkdir(parents=True, exist_ok=True)
PDFS = [
    ROOT / "60-publication" / "青囊海角经·现代白话版（现代风水爱好者修订版）.pdf",
    ROOT / "60-publication" / "supplements" / "青囊海角经·原文对照版.pdf",
]


def main():
    for old_sheet in AUDIT.glob("*-sheet-*.jpg"):
        old_sheet.unlink()
    (AUDIT / "all-pages-overview.jpg").unlink(missing_ok=True)
    report = {"schema_version": "1.1", "pdfs": [], "total_pages_rendered": 0,
              "render_failures": [], "blank_like_pages": [], "sparse_pages": []}
    overview_tiles = []
    for pdf_path in PDFS:
        pdf = pdfium.PdfDocument(str(pdf_path))
        thumbs = []
        sizes = []
        for index in range(len(pdf)):
            try:
                image = pdf[index].render(scale=0.32).to_pil().convert("RGB")
                sizes.append(image.size)
                stat = ImageStat.Stat(image.convert("L"))
                if stat.mean[0] > 252.5 and stat.var[0] < 8:
                    report["blank_like_pages"].append({"pdf": pdf_path.name, "page": index + 1})
                gray = image.convert("L")
                ink_pixels = sum(1 for pixel in gray.getdata() if pixel < 235)
                ink_ratio = ink_pixels / (gray.width * gray.height)
                if index + 1 > 2 and ink_ratio < 0.012:
                    report["sparse_pages"].append({"pdf": pdf_path.name, "page": index + 1,
                                                   "ink_ratio": round(ink_ratio, 5)})
                thumb = image.copy(); thumb.thumbnail((180, 250))
                tile = Image.new("RGB", (190, 275), "white")
                tile.paste(thumb, ((190-thumb.width)//2, 18))
                ImageDraw.Draw(tile).text((5, 3), f"{index+1}", fill="black")
                thumbs.append(tile)
            except Exception as exc:
                report["render_failures"].append({"pdf": pdf_path.name, "page": index + 1, "error": str(exc)})
        sheet_paths = []
        for start in range(0, len(thumbs), 40):
            batch = thumbs[start:start+40]
            sheet = Image.new("RGB", (190*5, 275*8), "#d9dedc")
            for offset, tile in enumerate(batch):
                sheet.paste(tile, ((offset % 5)*190, (offset // 5)*275))
            path = AUDIT / f"{pdf_path.stem}-sheet-{start//40+1:02d}.jpg"
            sheet.save(path, quality=82)
            sheet_paths.append(path)
            mini = sheet.copy(); mini.thumbnail((240, 560)); overview_tiles.append((pdf_path.stem, start//40+1, mini))
        report["pdfs"].append({"name": pdf_path.name, "pages": len(pdf), "rendered": len(thumbs), "page_sizes": sorted({str(size) for size in sizes}), "contact_sheets": [str(p.relative_to(ROOT)) for p in sheet_paths]})
        report["total_pages_rendered"] += len(thumbs)

    width = 240*5; height = 590*((len(overview_tiles)+4)//5)
    overview = Image.new("RGB", (width, height), "#eef1f0")
    draw = ImageDraw.Draw(overview)
    for i, (name, number, mini) in enumerate(overview_tiles):
        x=(i%5)*240; y=(i//5)*590
        draw.text((x+5,y+3), f"{name[-6:]} {number}", fill="black")
        overview.paste(mini,(x,y+25))
    overview_path = AUDIT / "all-pages-overview.jpg"; overview.save(overview_path, quality=88)
    report["overview"] = str(overview_path.relative_to(ROOT))
    expected_pages = sum(item["pages"] for item in report["pdfs"])
    report["expected_pages"] = expected_pages
    report["valid"] = (
        not report["render_failures"]
        and report["total_pages_rendered"] == expected_pages
        and all(item["rendered"] == item["pages"] for item in report["pdfs"])
    )
    report["requires_visual_review"] = bool(report["blank_like_pages"] or report["sparse_pages"])
    (AUDIT / "render-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    quality_path = ROOT / "90-audit" / "quality-report.json"
    if quality_path.exists() and report["pdfs"]:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        modern_name = report["pdfs"][0]["name"]
        modern_sparse = [item for item in report["sparse_pages"] if item["pdf"] == modern_name]
        modern_blank = [item for item in report["blank_like_pages"] if item["pdf"] == modern_name]
        publication = quality.setdefault("publication", {})
        publication["rendered_pages_inspected"] = report["pdfs"][0]["rendered"]
        publication["visual_defects_found"] = len(modern_sparse) + len(modern_blank)
        publication["visual_audit"] = "passed" if not modern_sparse and not modern_blank else "needs_review"
        quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
