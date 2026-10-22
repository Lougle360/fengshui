"""Render selected boundary/title pages from the Shanghai public-domain scan."""
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parent
PDF = ROOT / "90-audit/external-evidence/Shanghai-地理青囊經解-青囊心印續編.pdf"
OUT = ROOT / "90-audit/external-evidence/selected-pages"
PAGES = (*range(1, 93),)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(PDF) as document:
        for physical_page in PAGES:
            page = document[physical_page - 1]
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.4, 1.4),
                colorspace=pymupdf.csGRAY,
                alpha=False,
            )
            pixmap.save(OUT / f"pdf-{physical_page:03}.png")
    print({"rendered": len(PAGES), "output": str(OUT)})


if __name__ == "__main__":
    main()
