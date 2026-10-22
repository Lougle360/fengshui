"""Append hand-authored discoveries with real image hashes; never close issues."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parent
ledger=root/'90-audit/uncertainty-candidates.jsonl'
prior=[json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
ids={x['candidate_id'] for x in prior}
blocks={r['block_id']:r for r in map(json.loads,(root/'20-source/blocks.jsonl').read_text(encoding='utf-8').splitlines())}
new=[]
items=[]
for file in sorted((root/'90-audit/source-reading').glob('findings-*.json')):
    items.extend(json.loads(file.read_text(encoding='utf-8')))
assert len({item['id'] for item in items})==len(items), 'duplicate discovery IDs in authored input'
for item in items:
    if item['id'] in ids: continue
    block=blocks[item['block']]
    image=block['source_image']
    new.append({'schema_version':'1.3','candidate_id':item['id'],
       'page_id':block['page_id'],'block_id':item['block'],'origin_stage':'source',
       'owner_stage':'source','review_cycle':'SRC0001','checkpoint':'source_reconstruction',
       'kind':item.get('kind','glyph'),'excerpt':item['excerpt'],'reason':item['reason'],
       'severity':item['severity'],'source_image':image,'created_by':'Codex',
       'created_at':datetime.now(timezone.utc).isoformat(),
       'input_ref':{'path':image,'sha256':hashlib.sha256((root/image).read_bytes()).hexdigest(),'region':item['region']}})
with ledger.open('a',encoding='utf-8') as stream:
    for row in new: stream.write(json.dumps(row,ensure_ascii=False)+'\n')
print(json.dumps({'new_candidates':len(new),'total_candidates':len(ids)+len(new),'closures_generated':0}))
