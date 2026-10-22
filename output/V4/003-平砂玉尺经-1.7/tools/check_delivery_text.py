"""Read-only text-presence check, not a semantic acceptance test."""
from pathlib import Path
import re
import hashlib
import json
import fitz

root = Path(__file__).resolve().parents[1]
work = (root / '50-edited/modern-reading.md').read_text(encoding='utf-8')
draft = (root / '60-publication/modern-reading.md').read_text(encoding='utf-8')
glossary = draft.split('# 术语简释', 1)[1]
pdf = fitz.open(root / '60-publication/candidates/平砂玉尺经·现代白话版-candidate.pdf')
def norm(s):
    return re.sub(r'\s+', '', s)
visible = norm(''.join(p.get_text(clip=fitz.Rect(0, 45, p.rect.width, p.rect.height-40)) for p in pdf))
missing = []
for line in draft.splitlines():
    line = line.strip()
    if not line or line.startswith(('<!--', '![')) or line == '## 出版说明':
        continue
    line = re.sub(r'^#{1,3}\s+', '', line).lstrip('> ').removeprefix('图注：').replace('**', '')
    # Running page furniture can interrupt a paragraph across pages.
    for sentence in re.split(r'[。！？]', line):
        sentence = norm(sentence)
        if sentence and sentence not in visible:
            missing.append(sentence)
terms = re.findall(r'^\*\*(.+?)\*\*', glossary, re.M)
ids = lambda s: re.findall(r'P\d{6}-B\d{3}', '\n'.join(x for x in s.splitlines() if x.startswith('<!--')))
print(json.dumps({'original_sha256': hashlib.sha256((root/'50-edited/modern-reading.md').read_bytes()).hexdigest(), 'ids_same_order': ids(work)==ids(draft), 'source_id_count': len(ids(draft)), 'term_count': len(terms), 'missing_terms': [t for t in terms if t not in glossary], 'sentences_not_contiguous_in_pdf': missing}, ensure_ascii=False, indent=2))
