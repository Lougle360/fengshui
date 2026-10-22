"""Exact registered corrections; retain stable IDs through role splits."""
import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
docs={}
for name in ['pages-015.json','pages-016.json']:
 path=root/'20-source/transcription-inputs'/name
 snap=root/'90-audit/source-reading'/name.replace('.json','-before-review-015-016.json')
 assert not snap.exists()
 shutil.copy2(path,snap)
 docs[name]=json.loads(path.read_text(encoding='utf-8'))
def b(page,n):return docs[f'pages-{page:03d}.json']['pages'][0]['blocks'][n-1]
edits=[
 (15,2,'山向此神者有四山','山向比和者有四山','UC000015A'),
 (15,2,'小元有訣云','小元空有訣云','UC000077'),
 (15,3,'若還退時家不要','若還退時家不興','UC000067'),
 (15,8,'且又申得亥卯未','且又再得亥卯未','UC000069'),
 (15,8,'一訣千金大神精義','一訣千金入神精義','UC000069'),
 (16,4,'皆是朝折得向所宜','皆是謂折得向所宜','UC000071'),
 (16,5,'乾坤艮巽長男與','乾坤艮巽長男興','UC000072'),
 (16,9,'雷公眥位','雷公師位','UC000074'),
 (16,10,'酉名帥位','酉名師位','UC000074'),
 (16,12,'淫亂紋戮','淫亂絞戮','UC000073'),
 (16,13,'惟有富申巳亥','惟有寅申巳亥','UC000078'),
 (16,15,'吉者乙丙丁三奇也','奇者乙丙丁三奇也','UC000079'),
 (16,15,'官父貢人','官及貢人','UC000079')]
for pg,n,old,new,issue in edits:
 x=b(pg,n); assert old in x['text'],(pg,n,old)
 x['text']=x['text'].replace(old,new,1)
 x.setdefault('notes',[]).append(f'{issue}：依pages-015-016-independent.md图证改{old}为{new}；未闭合。')
prefix='過堂出要係本龍鄉皆是謂折得向所宜也可有科名冠世'
assert b(16,4)['text'].startswith(prefix)
b(16,4)['text']=b(16,4)['text'][len(prefix):]
b(16,4)['bbox']=[617,160,658,390]
b(16,4).pop('regions',None)
b(16,5).update(type='quotation',role='main_text',component='C-MAIN-UPPER',bbox=[520,174,658,711],regions=[[618,392,658,711],[568,174,617,711],[520,174,568,374]])
b(16,5).pop('commentary_target',None)
for n in range(4,16): b(16,n)['reading_order']=n+1
docs['pages-016.json']['pages'][0]['blocks'].append(dict(type='commentary',role='commentary',component='C-NOTES-UPPER',bbox=[656,169,704,711],text=prefix,reading_order=4,commentary_target='P000015-B010',notes=['UC000071：从B004分出放水例末注，不删文。']))
docs['pages-016.json']['content_chains'] += [['P000016-B003','P000016-B016'],['P000016-B004','P000016-B005']]
t=b(16,12)
t['bbox']=[336,785,477,1249]
t['table_cells']=[
 dict(label='子水',bbox=[414,785,477,1024],entries=[dict(kind='吉',text='吉主偏軍賊之財',bbox=[445,843,477,1019]),dict(kind='凶',text='凶主軍賊且淫亂',bbox=[414,845,445,1024])]),
 dict(label='卯水',bbox=[338,785,414,1013],entries=[dict(kind='吉',text='吉主橫財驟富',bbox=[375,843,414,1009]),dict(kind='凶',text='凶主雷擊淫亂',bbox=[338,846,376,1013])]),
 dict(label='午水',bbox=[414,1011,477,1233],entries=[dict(kind='吉',text='吉主出武職',bbox=[445,1082,477,1210]),dict(kind='凶',text='凶主火盜軍兵',bbox=[414,1082,445,1233])]),
 dict(label='酉水',bbox=[336,1011,414,1249],entries=[dict(kind='吉',text='吉主商飾女色',bbox=[375,1082,414,1238]),dict(kind='凶',text='凶主淫亂絞戮',bbox=[336,1082,377,1249])])]
t['notes'].append('UC000073：修正表整体及四组框，分开八个吉凶列，保留表内未核字候选。')
for name,doc in docs.items():
 (root/'20-source/transcription-inputs'/name).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'90-audit/source-reading/corrections-015-016.json').write_text(json.dumps({'status':'corrected_not_closed','text_changes':edits,'structure_issues':['UC000071','UC000072','UC000073']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'text_changes':len(edits),'closure_count':0}))
