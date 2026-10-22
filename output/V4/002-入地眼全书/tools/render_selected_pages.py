#!/usr/bin/env python3
"""Render representative release pages at high resolution for inspection."""

from pathlib import Path

import pypdfium2 as pdfium


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "90-audit" / "rendered-pdf-audit" / "highres"
OUT.mkdir(parents=True, exist_ok=True)
SELECTIONS = {
    "reader": (
        ROOT / "60-publication" / "入地眼全书·现代白话版.pdf",
        [1, 2, 3, 4, 9, 31, 90, 91, 169, 170],
    ),
    "comparison": (
        ROOT / "60-publication" / "入地眼全书·原文对照版.pdf",
        [1, 2, 3, 120, 241, 306, 350, 351],
    ),
}


def main() -> None:
    for old in OUT.glob("*.png"):
        old.unlink()
    for label, (path, pages) in SELECTIONS.items():
        pdf = pdfium.PdfDocument(str(path))
        for number in pages:
            image = pdf[number - 1].render(scale=1.5).to_pil().convert("RGB")
            image.save(OUT / f"{label}-{number:03d}.png")
    print(f"rendered={sum(len(item[1]) for item in SELECTIONS.values())}")


if __name__ == "__main__":
    main()
