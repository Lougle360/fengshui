"""Preserve a candidate book slice and render boundary evidence; no acceptance claims."""
import hashlib
import json
from pathlib import Path
import fitz

PROJECT = Path(__file__).resolve().parents[3]
SOURCE = PROJECT / 'Docs/地学-经典/413.地理正宗臆解+黑囊经+青囊心印+地学.pdf'
TARGET = PROJECT / 'tmp/pdfs/qingnang-xinyin-110'
TARGET.mkdir(parents=True, exist_ok=True)
doc = fitz.open(SOURCE)
pdf = TARGET / 'source.pdf'
if not pdf.exists():
    sliced = fitz.open()
    sliced.insert_pdf(doc, from_page=284, to_page=305)
    sliced.save(pdf)
for page in [284, 285, 286, 287, 288, 294, 305, 306, 307]:
    doc[page-1].get_pixmap(matrix=fitz.Matrix(2, 2)).save(TARGET / f'collection-{page:03}.png')
print(json.dumps({'collection_pages': len(doc), 'slice_pages': 22, 'source_slice': str(pdf),
                  'slice_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(), 'render_root': str(TARGET)}, ensure_ascii=False))
