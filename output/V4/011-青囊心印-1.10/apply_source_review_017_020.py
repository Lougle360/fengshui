"""Apply registered image-supported corrections. No semantic acceptance."""
import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
docs={}
for name in ['pages-017-018.json','pages-019-020.json']:
 p=root/'20-source/transcription-inputs'/name
 s=root/'90-audit/source-reading'/name.replace('.json','-before-review-017-020.json')
 assert not s.exists()
 shutil.copy2(p,s); docs[name]=json.loads(p.read_text(encoding='utf-8'))
def page(n):return next(p for d in docs.values() for p in d['pages'] if p['page']==n)
def b(p,n):return page(p)['blocks'][n-1]
edits=[
 (17,13,'得四失六難為全矣也','得四失六難為全美也','UC000102'),
 (18,2,'楊公特其發暢吾世地學之宗也','楊公得其發暢萬世地學之宗也','UC000086'),
 (18,7,'□語錯抑季先□先生同鑒定','繡湖季讓言九宜先生同鑒定','UC000088'),
 (18,9,'俱從穴干位上起長生','俱從天干位上起長生','UC000089'),
 (18,9,'用挨羅盤凡佈九星','用挨星盤凡佈九星','UC000089'),
 (18,11,'地卦水神第在此例','地卦水神者不在此例','UC000104'),
 (18,11,'得生旺交歸墓','得生旺互交歸墓','UC000105'),
 (18,11,'得生旺五交入墓','得生旺互交入墓','UC000090'),
 (19,2,'得生旺五支歸庫','得生旺互交歸庫','UC000091'),
 (19,2,'得生旺五交入墓','得生旺互交入墓','UC000091'),
 (19,2,'陽水神從巽神起長生','陽水神從零神起長生','UC000091'),
 (20,11,'第八裁庇曲流神認去來','第八裁屈曲流神認去來','UC000096'),
 (20,23,'庇曲流神','屈曲流神','UC000101')]
for pg,n,old,new,issue in edits:
 x=b(pg,n); assert old in x['text'],(pg,n,old)
 x['text']=x['text'].replace(old,new,1)
 x.setdefault('notes',[]).append(f'{issue}：据独立图审更正{old}为{new}，正式闭合待审。')
for n in [4,8]:
 b(17,n).update(role='main_text',component='C-MAIN-UPPER')
 b(17,n).pop('commentary_target',None)
assert b(17,10)['text'].endswith('明')
b(17,10)['text']=b(17,10)['text'][:-1]
b(17,12)['text']='明'+b(17,12)['text']
b(17,12)['bbox']=[432,791,476,976]
b(17,13)['bbox']=[130,797,474,1341]
b(17,13)['regions'][0]=[432,979,474,1341]
b(18,7).update(type='body',role='authorship',component='C-PREFACES',bbox=[775,793,830,1023])
b(18,7)['notes'].append('署名让言、九宜并排，按两人保留；下方黑墨非署名字，不混入正文。')
tail='元空只在五行中知此理不必尋納甲'
assert b(19,11)['text'].endswith(tail)
b(19,11)['text']=b(19,11)['text'][:-len(tail)]
b(19,11)['bbox']=[650,799,784,1343]
b(19,11)['notes'].append('UC000106：末独立经句从本注分出至P000019-B018；褪印未决仍保留。')
for n in range(12,18):b(19,n)['reading_order']=n+1
page(19)['blocks'].append(dict(type='quotation',role='main_text',component='C-MAIN-LOWER',bbox=[610,787,698,1230],regions=[[610,787,652,1230],[650,984,698,1169]],reading_order=12,text='明'+tail,notes=['UC000106：独立经句分出并据图补明；淡印穿插处边界保留待最终坐标复核。']))
for n in [12,14]:b(19,n)['commentary_target']='P000019-B018'
b(20,24)['commentary_targets']=['P000020-B012','P000020-B013']
b(20,24)['notes'].append('UC000107：明确九、十共释；单目标字段只为兼容，不代表排除第十。')
for name,doc in docs.items():
 (root/'20-source/transcription-inputs'/name).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'90-audit/source-reading/corrections-017-020.json').write_text(json.dumps({'status':'corrected_not_closed','text_changes':edits,'structural_issues':['UC000080','UC000081','UC000103','UC000106','UC000107']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'text_changes':len(edits),'closures':0}))
