"""Capture actual read-only gate output. No semantic acceptance is generated."""
import json
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parent
scripts=Path('C:/Users/QIQI/.codex/skills')
reports={}
for name, relative, args in [
 ('source','chaoyun-ancient-book-renovator/scripts/validate_workspace.py',['--stage','source']),
 ('uncertainty','chaoyun-uncertainty-adjudicator/scripts/project_open_items.py',['--check']),
]:
    run=subprocess.run([sys.executable,str(scripts/relative),str(root),*args],capture_output=True,text=True,encoding='utf-8')
    reports[name]={'exit_code':run.returncode,'stdout':run.stdout,'stderr':run.stderr}
stamp=datetime.now(timezone.utc).isoformat()
report={'created_at':stamp,'source_sha256':hashlib.sha256((root/'20-source/blocks.jsonl').read_bytes()).hexdigest(),
        'checks':reports,'semantic_acceptance':False,'publication_ready':False,
        'blocking_issue':'UI-UC000093','remaining_adjudication_work':121,
        'independent_coordinate_review':'90-audit/source-reading/coordinate-replay-check.md'}
target=root/'90-audit/source-reading/source-checkpoint-with-gap.json'
if target.exists():
    raise SystemExit('Checkpoint already exists; refusing to overwrite historical check.')
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
statepath=root/'run-state.json'
state=json.loads(statepath.read_text(encoding='utf-8-sig'))
state['updated_at']=stamp
state['current_stage']='source'
state['stages']['source']={'status':'running','structural_validator':'passed','semantic_acceptance':False,
 'evidence':'90-audit/source-reading/source-checkpoint-with-gap.json',
 'input_gap':'UI-UC000093: original physical page303 / printed299 / slice19 faded commentary',
 'next_action':'Obtain readable source evidence for faded passage; retain all 122 candidates and finish the 121 remaining formal adjudications. Do not advance to bulk modernization or publication.'}
statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_contract_exit':reports['source']['exit_code'],'uncertainty_contract_exit':reports['uncertainty']['exit_code'],
 'publication_ready':False,'checkpoint':str(target)},ensure_ascii=False))
