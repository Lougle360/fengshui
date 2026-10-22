"""Build source projections from hand-authored page records, never from OCR prose.

Deterministic and idempotent. Does not accept text or advance workflow gates.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
BOOK = json.loads((ROOT/'book.json').read_text(encoding='utf-8-sig'))
rows, covered, chains = [], set(), []
for path in sorted((ROOT/'20-source/transcription-inputs').glob('pages-*.json')):
    payload=json.loads(path.read_text(encoding='utf-8'))
    evidence=payload['review_evidence']
    assert (ROOT/evidence).is_file()
    chains.append(payload.get('content_chain',[]))
    chains.extend(payload.get('content_chains',[]))
    for page in payload['pages']:
        number=page['page']
        assert number not in covered, f'duplicate page {number}'
        covered.add(number)
        image=f'20-source/pages/P{number:06}.native.jpeg'
        with Image.open(ROOT/image) as scan:
            width,height=scan.size
        for order,raw in enumerate(page['blocks'],1):
            for box in raw.get('regions',[raw['bbox']]):
                x0,y0,x1,y1=box
                assert 0<=x0<x1<=width and 0<=y0<y1<=height, (number,order,box)
            row={
                'schema_version':'1.0','book_id':BOOK['book_id'],
                'page_id':f'P{number:06}','block_id':f'P{number:06}-B{order:03}',
                'source_page':number,'collection_source_page':number+284,
                'block_type':raw['type'],'structural_role':raw['role'],
                'component_id':raw['component'],'reading_order':raw.get('reading_order',order),
                'bbox':raw['bbox'],'source_image':image,'source_text':raw['text'],
                'normalized_text':None,'modern_text':None,
                'language':'lzh','operation':'source',
                'disposition':'noncontent' if raw['component']=='C-FURNITURE' else 'retained',
                'confidence':None,'review_status':payload['status'],
                'evidence':[evidence], 'notes':raw.get('notes',[]),
            }
            for key in ['regions','uncertain_regions','table_cells','continues_from_previous_page','continues_to_next_page','commentary_target','commentary_targets']:
                if key in raw: row[key]=raw[key]
            if raw['component']=='C-FURNITURE':
                row['notes']=list(row['notes'])+[
                    f"非内容判定：原图第{number}页区域{raw['bbox']}为页眉或版心的书名、丛刊名及页叶码（{raw['text']}）；无正文或释文。保留源图与转录，不进入连续白话正文。对图记录：{evidence}。"
                ]
            rows.append(row)
rows.sort(key=lambda r:(r['source_page'],r['reading_order']))
by_id={r['block_id']:r for r in rows}
assert len(by_id)==len(rows)
for chain in chains:
    assert all(x in by_id for x in chain)
    for left,right in zip(chain,chain[1:]):
        by_id[left]['continues_to_block']=right
        by_id[right]['continues_from_block']=left
data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
(ROOT/'20-source/blocks.jsonl').write_text(data,encoding='utf-8')
all_pages=len(covered)==BOOK['source_pdf_pages']
md=['# 青囊心印：源文重建（待验收）' if all_pages else '# 青囊心印：源文重建（未完）','',
    '> 全页已初次转录，疑字与结构仍在核准中；源文门禁未通过。' if all_pages else '> 仅投影已经逐图转录的页；未覆盖的页不是空白，也不是获准删去。疑字以台账为准，源文门禁未通过。','']
for r in rows:
    md += [f'## {r["block_id"]} · {r["structural_role"]}',r['source_text'],'']
(ROOT/'20-source/source.md').write_text('\n'.join(md),encoding='utf-8')
print(json.dumps({'covered_pages':sorted(covered),'total_source_pages':BOOK['source_pdf_pages'],
  'blocks':len(rows),'source_sha256':hashlib.sha256((ROOT/'20-source/blocks.jsonl').read_bytes()).hexdigest(),
  'acceptance':'not_claimed'},ensure_ascii=False))
