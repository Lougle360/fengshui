"""Apply only individually evidenced replacements; never mark review passed."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
changes = {
 'pages-008-009.json': {
  (8,7): [('青囊序心印卷之一','青囊心印卷之一','UC000027')],
  (8,9): [('繡湖李讓言','繡湖季讓言','UC000042')],
  (9,9): [('玉尺合璧旨云','玉尺合秘旨云','UC000033')],
  (9,14): [('引隱洛得配以證之也','引營洛得配以論之也','UC000036'),('察澗水在西瀍水在西','察澗水在東瀍水在西','UC000036'),('其金曰我乃卜','其金言曰我乃卜','UC000043')],
 },
 'pages-010.json': {
  (10,2): [('幸有逼其微者','幸有通其微者','UC000037')],
  (10,3): [('此是陰陽元妙','此是陰陽元妙印','UC000044')],
  (10,13): [('陰陽福與宗','陰陽祖與宗','UC000040'),('有人得其中意','有人會得其中意','UC000045')],
  (10,14): [('中二句分最明','中二句分疏最明','UC000046')],
 }
}
report=[]
for name, mapping in changes.items():
 path=root/'20-source/transcription-inputs'/name
 data=json.loads(path.read_text(encoding='utf-8'))
 for (page,index), edits in mapping.items():
  block=next(p for p in data['pages'] if p['page']==page)['blocks'][index-1]
  for before,after,issue in edits:
   # Each invocation is one-shot; replay against immutable snapshots separately.
   assert before in block['text'], (name,page,index,before)
   block['text']=block['text'].replace(before,after,1)
   block.setdefault('notes',[]).append(f'{issue}：据pages-008-010-independent.md原图复核更正{before}为{after}，正式闭合待审。')
   report.append(dict(issue_id=issue,block_id=f'P{page:06d}-B{index:03d}',before=before,after=after))
  if (page,index)==(10,3):
   block['regions'][1]=[519,157,559,257]
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'90-audit/source-reading/corrections-008-010.json').write_text(json.dumps({'status':'corrected_not_closed','review':'90-audit/source-reading/pages-008-010-independent.md','changes':report},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'applied':len(report),'closed':0}))
