"""Derive scan inventory and resumable state; no semantic pass generation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

manifest = json.loads((ROOT/'00-intake/source-manifest.json').read_text(encoding='utf-8-sig'))
source = ROOT/'00-intake/source.pdf'
assert digest(source) == manifest['source_sha256']
groups = {
    1: '张哲序起', 2: '张哲序续', 3: '张哲序终',
    4: '小引起', 5: '小引终；另一序起', 6: '张德炳序终；例言起',
    7: '例言终；王宗臣自述', 8: '青囊经序；卷上起',
    18: '卷上终；青囊奥语心印卷下起', 22: '卷下终',
}
rows=[]
with pymupdf.open(source) as doc:
    assert len(doc)==22
    for number,page in enumerate(doc,1):
        img=ROOT/f'20-source/pages/P{number:06}.native.jpeg'
        assert img.is_file() and img.stat().st_size>0
        assert not page.get_text().strip()
        assert len(page.get_images())==1
        risks=['vertical_reading_order','running_matter','damaged_glyphs']
        if number in range(8,23): risks += ['commentary_ownership']
        if number in [8,9]: risks += ['cross_page_commentary']
        if number==16: risks += ['inline_table_not_in_figure_catalogue']
        rows.append({
            'schema_version':'1.0','book_id':manifest['book_id'],
            'page_id':f'P{number:06}','source_page':number,
            'collection_source_page':number+284,'page_kind':'scan',
            'accounting':'included_content','layout':['vertical','two_half_leaves'],
            'languages':['lzh'],'text_layer_quality':'none','scan_quality':'fair',
            'route':'native_image_visual_reconstruction',
            'risk_flags':risks,'sample_verified':False,
            'layout_inspected':True,'word_level_review':'pending',
            'source_image':img.relative_to(ROOT).as_posix(),'image_sha256':digest(img),
            'notes':[groups.get(number,'卷上正文与注释' if number<18 else '卷下正文与注释')]
        })
(ROOT/'10-diagnosis/page-map.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
now=datetime.now(timezone.utc).isoformat()
state=json.loads((ROOT/'run-state.json').read_text(encoding='utf-8-sig'))
state['updated_at']=now
state['current_stage']='diagnosis'
state['stages']['intake']={'status':'passed','evidence':'source-manifest.json hash matches preserved 22-page PDF; 22 original JPEG streams extracted','verified_at':now}
state['stages']['diagnosis']={'status':'running','layout_pages_inspected':22,'source_pages_word_accepted':0,'evidence':'10-diagnosis/inspection-notes.md','trial':'10-diagnosis/trial/','limitation':'opening trial does not replace complete chapter trial, full source coverage, or formal sample acceptance'}
write_json(ROOT/'run-state.json',state)
event={'time':now,'actor':'Codex','tool':'record_diagnosis.py','operation':'record_scan_inventory','source_ids':[r['page_id'] for r in rows],'before':None,'after':{'included_pages':22,'native_images':22,'word_level_accepted':0},'confidence':1.0,'rationale':'Mechanical count/hash verification, layout findings retained separately; no semantic stage promoted.'}
with (ROOT/'90-audit/events.jsonl').open('a',encoding='utf-8') as handle:
    handle.write(json.dumps(event,ensure_ascii=False)+'\n')
print(json.dumps({'source_hash_verified':True,'page_count':22,'native_images':22,'current_stage':'diagnosis','publication':'pending'},ensure_ascii=False))
