"""Registered final-page corrections; keep all old IDs."""
import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
p=root/'20-source/transcription-inputs/pages-021-022.json'
s=root/'90-audit/source-reading/pages-021-022-before-review.json'
assert not s.exists()
shutil.copy2(p,s)
d=json.loads(p.read_text(encoding='utf-8'))
def pg(n):return next(x for x in d['pages'] if x['page']==n)
def b(n,i):return pg(n)['blocks'][i-1]
edits=[(22,6,'龍歇脈寒','龍敗脈寒','UC000117'),(22,8,'龍歇脈寒','龍敗脈寒','UC000118'),(22,10,'砂如圓淨發孝忠貞','砂如圓淨證孝忠貞','UC000119')]
for n,i,old,new,issue in edits:
 x=b(n,i);assert old in x['text'];x['text']=x['text'].replace(old,new,1)
 x.setdefault('notes',[]).append(f'{issue}：据pages-021-022-independent.md独立图证校改{old}为{new}，未闭合。')
q='向放水生旺有吉休囚否'
text=b(21,13)['text'];left,rest=text.split(q,1)
b(21,13)['text']=left;b(21,13)['bbox']=[698,813,831,1342]
pg(21)['blocks'].append(dict(type='quotation',role='main_text',component='C-MAIN-LOWER',bbox=[653,805,698,1030],text=q,reading_order=14,notes=['UC000113：独立经句从B013分出，旧ID保持不变。']))
pg(21)['blocks'].append(dict(type='commentary',role='commentary',component='C-NOTES-LOWER',bbox=[566,810,653,1342],regions=[[610,812,653,1342],[566,810,610,905]],text=rest,reading_order=15,commentary_target='P000021-B018',notes=['UC000113：此释文归新B018；言之矣在左邻短列，明确分区。']))
for i in range(14,18):b(21,i)['reading_order']=i+2
b(21,14)['bbox']=[525,797,566,1035]
b(22,9)['bbox']=[610,802,698,1341]
b(22,9)['regions']=[[650,802,698,1341],[610,802,650,910]]
b(22,10)['bbox']=[512,815,650,1340]
b(22,10)['regions']=[[610,913,650,1340],[512,815,610,1340]]
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'90-audit/source-reading/corrections-021-022.json').write_text(json.dumps({'status':'corrected_not_closed','text_changes':edits,'structural_issue':'UC000113','coordinate_repair':'P000022-B009/B010 short-tail separation'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'text_changes':3,'closure_count':0}))
