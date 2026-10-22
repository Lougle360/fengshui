"""Render the matched collation spread and its left-page text area at high resolution."""
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parent
PDF = ROOT / "90-audit/external-evidence/Shanghai-地理青囊經解-青囊心印續編.pdf"
OUT = ROOT / "90-audit/external-evidence/p38-collation"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(PDF) as document:
        page = document[37]
        matrix = pymupdf.Matrix(3.0, 3.0)
        page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False).save(
            OUT / "pdf-038-full-3x.png"
        )
        rect = page.rect
        left_text = pymupdf.Rect(rect.x0, rect.y0 + rect.height * 0.12, rect.x0 + rect.width * 0.51, rect.y1)
        page.get_pixmap(
            matrix=matrix,
            clip=left_text,
            colorspace=pymupdf.csGRAY,
            alpha=False,
        ).save(OUT / "pdf-038-left-text-3x.png")
    print({"page": 38, "output": str(OUT)})


if __name__ == "__main__":
    main()
