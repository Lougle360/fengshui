import json
from pathlib import Path
import pymupdf as fitz

ROOT = Path(__file__).resolve().parent
doc = fitz.open(ROOT / '00-intake/source.pdf')
rows = []
for i, page in enumerate(doc):
    image = ROOT / f'20-source/pages/P{i+1:06}.png'
    page.get_pixmap(matrix=fitz.Matrix(3, 3)).save(image)
    rows.append({'page': i+1, 'collection_page': i+285, 'width_pt': page.rect.width,
                 'height_pt': page.rect.height, 'text_chars': len(page.get_text()), 'images': len(page.get_images())})
print(json.dumps(rows, ensure_ascii=False))
