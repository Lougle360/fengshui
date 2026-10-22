"""Check actual incremental source projections, not full-book acceptance."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run([sys.executable,'-X','utf8',str(root/'build_source.py')],check=True)
targets=[root/'20-source/blocks.jsonl',root/'20-source/source.md']
before=[sha(p) for p in targets]
subprocess.run([sys.executable,'-X','utf8',str(root/'build_source.py')],check=True)
assert before==[sha(p) for p in targets], 'not idempotent'
rows=[json.loads(s) for s in targets[0].read_text(encoding='utf-8').splitlines()]
by_id={r['block_id']:r for r in rows}
assert len(rows)==len(by_id)
assert len({(r['source_page'],r['reading_order']) for r in rows})==len(rows), 'duplicate reading order'
for r in rows:
    assert r['source_text'].strip()
    if 'commentary_target' in r:
        assert r['commentary_target'] in by_id, ('missing commentary target',r['block_id'])
    for target in r.get('commentary_targets',[]):
        assert target in by_id, ('missing multiple commentary target',r['block_id'])
    if 'continues_to_block' in r:
        other=by_id[r['continues_to_block']]
        assert other['continues_from_block']==r['block_id']
    if 'continues_from_block' in r:
        other=by_id[r['continues_from_block']]
        assert other['continues_to_block']==r['block_id']
assert '亦旣孜孜矻矻' in by_id['P000001-B003']['source_text']
ledger=root/'90-audit/uncertainty-candidates.jsonl'
count=len(ledger.read_text(encoding='utf-8').splitlines())
subprocess.run([sys.executable,'-X','utf8',str(root/'register_source_findings.py')],check=True)
assert len(ledger.read_text(encoding='utf-8').splitlines())==count
report={
    'checked_at':datetime.now(timezone.utc).isoformat(),
    'scope':'incremental_source_only',
    'checks':{'deterministic_rebuild':True,'unique_block_ids':True,'unique_page_reading_order':True,'commentary_targets_exist':True,'nonempty_text':True,
       'symmetric_continuation_links':True,'UC000004_applied':True,'no_duplicate_candidate_registration':True},
    'pages_transcribed':sorted({r['source_page'] for r in rows}),
    'block_count':len(rows),'candidate_count':count,
    'full_source_gate':'not_passed_unresolved_source_review' if len({r['source_page'] for r in rows})==22 else 'not_passed_incomplete_book',
    'source_sha256':sha(targets[0]),
}
(root/'90-audit/source-reading/incremental-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=json.loads((root/'run-state.json').read_text(encoding='utf-8-sig'))
state['updated_at']=report['checked_at']
state['stages']['diagnosis']['source_transcription_pages']=len(report['pages_transcribed'])
state['stages']['diagnosis']['source_transcription_blocks']=len(rows)
state['stages']['diagnosis']['source_pages_word_accepted']=0
state['stages']['diagnosis']['next_action']='Complete independent correction replay, source uncertainty adjudication and source gate; full page transcription is not accepted source.'
(root/'run-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
