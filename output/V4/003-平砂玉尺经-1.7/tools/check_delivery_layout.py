"""Render every candidate page and report geometry; never assign acceptance."""
from pathlib import Path
import hashlib
import json
import re
import pymupdf
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / '60-publication/candidates/平砂玉尺经·现代白话版-candidate.pdf'
OUT = ROOT / 'tmp/delivery-proof'
OUT.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(PDF)
pages, bounds, links, sparse = [], [], [], []
for page in doc:
    number = page.number + 1
    image = OUT / f'page-{number:03}.png'
    page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(image)
    pages.append(image)
    for b in page.get_text('blocks'):
        if not page.rect.contains(pymupdf.Rect(b[:4])):
            bounds.append({'page': number, 'bbox': b[:4]})
    for link in page.get_links():
        if link['kind'] == pymupdf.LINK_GOTO:
            links.append({'from': number, 'target': link['page']+1})
    chars = len(page.get_text().strip())
    if chars < 150 and not page.get_images() and number > 2:
        sparse.append({'page': number, 'characters': chars})
for offset in range(0, len(pages), 4):
    sheet = Image.new('RGB', (1560, 2260), '#d0d0d0')
    draw = ImageDraw.Draw(sheet)
    for k, path in enumerate(pages[offset:offset+4]):
        im = Image.open(path).convert('RGB')
        im.thumbnail((760, 1080))
        x, y = (k % 2)*780 + 10, (k//2)*1130 + 32
        sheet.paste(im, (x, y))
        draw.text((x, y-20), f'PDF {offset+k+1}', fill='black')
    sheet.save(OUT / f'sheet-{offset//4+1:02}.jpg', quality=90)
text = '\n'.join(p.get_text() for p in doc)
leaks = {s: len(re.findall(s, text)) for s in ['P[0-9]{6}-B[0-9]{3}', '本页新增判断', '阅读抓手', '读图顺序与本图边界', '必须保留', '按本书的判断链', '<!--']}
report = {'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(), 'pages': len(doc),
          'figures': sum(len(p.get_images()) for p in doc), 'navigation': links,
          'bookmarks': doc.get_toc(), 'out_of_bounds': bounds, 'sparse_pages': sparse,
          'known_production_phrases': leaks, 'visual_status': 'pending_manual_review',
          'line_start_punctuation': [{'page': p.number+1, 'text': line[:50]} for p in doc for line in p.get_text().splitlines() if re.match(r'^[，。；：？！、）》】」』”’％,.;:!?]', line.strip()) and not line.strip().startswith('.')],
          'semantic_status': 'not_certified_by_this_script'}
(OUT / 'layout-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
