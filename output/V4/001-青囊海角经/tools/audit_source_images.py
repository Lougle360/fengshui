from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat


WORKSPACE = Path(r"D:\壮五福\风水项目\output\V4\001-青囊海角经")
PAGES = WORKSPACE / "20-source" / "pages"
OUT = WORKSPACE / "90-audit" / "source-contact-sheets"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page_paths = sorted(PAGES.glob("P*.jpg"))
    if len(page_paths) != 216:
        raise RuntimeError(f"expected 216 page images, found {len(page_paths)}")

    font = ImageFont.load_default()
    metrics: list[dict] = []
    thumbs: list[tuple[str, Image.Image]] = []
    for path in page_paths:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            gray = rgb.convert("L")
            stat = ImageStat.Stat(gray)
            extrema = gray.getextrema()
            metrics.append(
                {
                    "page_id": path.stem,
                    "width": rgb.width,
                    "height": rgb.height,
                    "mean_luma": round(stat.mean[0], 2),
                    "stddev_luma": round(stat.stddev[0], 2),
                    "min_luma": extrema[0],
                    "max_luma": extrema[1],
                    "bytes": path.stat().st_size,
                }
            )
            thumb = rgb.copy()
            thumb.thumbnail((190, 285))
            thumbs.append((path.stem, thumb))

    per_sheet = 18
    cols = 6
    rows = 3
    cell_w = 210
    cell_h = 320
    sheets: list[str] = []
    for sheet_no in range(math.ceil(len(thumbs) / per_sheet)):
        batch = thumbs[sheet_no * per_sheet : (sheet_no + 1) * per_sheet]
        canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, (label, thumb) in enumerate(batch):
            row, col = divmod(slot, cols)
            x = col * cell_w + (cell_w - thumb.width) // 2
            y = row * cell_h + 22
            canvas.paste(thumb, (x, y))
            draw.text((col * cell_w + 8, row * cell_h + 4), label, fill="black", font=font)
        out_path = OUT / f"sheet-{sheet_no + 1:02d}.jpg"
        canvas.save(out_path, quality=90, optimize=True)
        sheets.append(str(out_path.relative_to(WORKSPACE)).replace("\\", "/"))

    suspicious = [
        item
        for item in metrics
        if item["bytes"] < 10_000
        or item["stddev_luma"] < 4
        or item["mean_luma"] < 80
        or item["mean_luma"] > 254.5
    ]
    report = {
        "schema_version": "1.0",
        "status": "passed" if not suspicious else "needs_visual_review",
        "page_images": len(metrics),
        "contact_sheets": sheets,
        "automated_suspicious_pages": suspicious,
        "metrics": metrics,
    }
    (WORKSPACE / "90-audit" / "source-image-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: report[key] for key in report if key != "metrics"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
