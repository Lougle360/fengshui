"""Registered, exact source corrections and structural repair. No acceptance."""
import json, shutil
from pathlib import Path
root=Path(__file__).resolve().parent
names=['pages-011-012.json','pages-013-014.json','pages-015.json']
docs={}
for name in names:
 p=root/'20-source/transcription-inputs'/name
 snap=root/'90-audit/source-reading'/name.replace('.json','-before-review-011-014.json')
 assert not snap.exists(), 'one-shot correction already applied'
 shutil.copy2(p,snap)
 docs[name]=json.loads(p.read_text(encoding='utf-8'))
def block(page,idx):
 return next(p for d in docs.values() for p in d['pages'] if p['page']==page)['blocks'][idx-1]
changes=[
 (12,10,'雖終不敢','然終不敢','UC000051'),(12,10,'二李子舉','二季子舉','UC000051'),
 (13,8,'支庫大小','文庫大小','UC000056'),(13,9,'而五方收入囗','而去方收入口','UC000057'),
 (13,10,'正尺云','玉尺云','UC000058'),(13,10,'一例似箭射相連孤殘','一泓似箭射相連孤寒','UC000058'),
 (13,10,'恐人工實從於長生','蓋人丁實係於長生','UC000058'),(13,10,'射破祿神生方則破傷生氣','射破龍神生方則輕傷生氣','UC000058'),
 (13,10,'財祿必敗故官旺','財祿必敗於官旺','UC000058'),(13,10,'且敗成貿之子','且敗成財之子','UC000058'),
 (13,11,'如下文勿云','如下文所云','UC000053'),(13,12,'名為進進退水宜流','名為進退水宜流','UC000059'),
 (13,14,'上文言局中財水及流','上文言局中凶水反逆','UC000060'),
 (14,5,'如朱未之忠烈公','如宋末文忠烈公','UC000061'),(14,5,'公欲葬公公不見','公欲封公公不見','UC000061'),(14,5,'死絕衰方水去','死絕墓方水去','UC000061'),
 (14,6,'倒左出是破煞倒沖','倒左出辰是破煞倒沖','UC000062'),(14,6,'西金同木廿八水四火四土','四金四木并八水四火四土','UC000063'),
 (14,9,'甲癸亥良是木神','甲癸亥艮是木神','UC000064'),(14,9,'戌未壬庚土為真','戌未丑庚土為真','UC000064'),
 (14,9,'申衰壬方是水神','申與壬方是水神','UC000064'),(14,9,'大考言陰陽','大者言陰陽','UC000064'),
 (14,9,'出煞之祕機朝魯意旨之神術','出煞之元機朝貧暮富之神術','UC000064'),(14,9,'裏交再提撥','裏矣再提撥','UC000064'),(14,9,'共有十二山此十山','共有十山此十山','UC000064')]
for page,idx,old,new,issue in changes:
 b=block(page,idx)
 assert old in b['text'], (page,idx,old)
 b['text']=b['text'].replace(old,new,1)
 b.setdefault('notes',[]).append(f'{issue}：独立对图更正{old}为{new}；其他疑处仍未闭合。')
block(13,7)['bbox']=[396,166,477,700]
b=block(13,11)
b.update(type='commentary',role='commentary',component='C-NOTES-UPPER',bbox=[614,790,701,1341],regions=[[655,790,701,1341],[614,796,654,912]],commentary_target='P000013-B008')
b['notes'].append('UC000053：据实际字号和列界改作承转按语，不因墨重认作经句。')
quote='進退得位出公卿發登巨富旺人丁旺方帶殺來不宜庫中帶殺去亦非'
b=block(13,14)
assert b['text'].endswith(quote)
b['text']=b['text'][:-len(quote)]
b['bbox']=[173,795,476,1342]
b['notes'].append('UC000054：末大字经句已另列稳定新块P000013-B015，非删文。')
page13=next(p for p in docs['pages-013-014.json']['pages'] if p['page']==13)
page13['blocks'].append(dict(type='quotation',role='main_text',component='C-MAIN-UPPER',bbox=[80,794,173,1342],regions=[[124,794,173,1342],[80,794,123,1016]],text=quote,notes=['UC000054：从B014分出；發登字候选仍待核。']))
d=docs['pages-013-014.json']
chain=next(c for c in d['content_chains'] if c[0]=='P000013-B014')
chain.remove('P000013-B014')
d['content_chains'].append(['P000013-B010','P000013-B011'])
for page in (14,15):
 for p in [p for doc in docs.values() for p in doc['pages'] if p['page']==page]:
  for b in p['blocks']:
   if b.get('commentary_target')=='P000013-B012':
    b['commentary_target']='P000013-B015'
    b.setdefault('notes',[]).append('UC000054：本注/引文解进退得位，改归P000013-B015。')
block(14,2).pop('continues_from_previous_page',None)
for name,data in docs.items():
 (root/'20-source/transcription-inputs'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'90-audit/source-reading/corrections-011-014.json').write_text(json.dumps({'status':'corrected_not_closed','text_changes':changes,'structure_issues':['UC000053','UC000054','UC000055'],'independent_reviews':['pages-011-012-independent.md','pages-013-014-independent.md']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'text_changes':len(changes),'structural_issues_repaired':3,'closures':0}))
