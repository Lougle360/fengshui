#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/'40-modernized/blocks.v19-in-progress.jsonl'
FORMAL=ROOT/'40-modernized/blocks.jsonl'
EDIT=ROOT/'50-edited'

def rows(path): return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
def dump(path,obj): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def dump_lines(path,data): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data),encoding='utf-8')

DISPLAY_OVERRIDES={
    'P000008-B011':'这里引用经文，是为了说明支龙怎样运行。平坦之地会微微露出土脊：圆的像浮沤、星点或珠子，方的像箱子或印章，长的像玉尺或芦鞭，曲的像几案或衣带；大小方圆不等的，又像龟、鱼、蛙、蛤。古注认为，这些都是地中吉气上涌，使泥土随之凸起的形态。到了停止处，则像鸡窝或旋螺。形态停止、脉络穷尽，又有一线水流横过。地面高一寸也可以称山，低一寸也可以称水；这说明支气停止时，水与它贴近，彼此配合发挥作用。《天宝经》说，判断平洋地的高低与收放，要看水怎样会合，分金也在这里；说的正是“水随而比”。来势要顺伏而不反逆，形态要活动而不僵硬，砂与水交勾夹护，回环往复，首尾没有缺蔽，从头到尾都要有情。依法选择穴位，才能使亡者安宁、后人得福，长久吉利而没有凶患。以上说的是支脉，以下转入高垄。',
    'P000020-B016':'“派”是水流分开，“朝”是水流汇合，也就是江汉百川归向共同源头的意思。水开始流动时，刚分出细小水流，只是一线之微，这就是水势尚未盛大时的分流。',
    'P000021-B004':None,
    'P000023-B001':'这里说的弯曲、迟缓、倾斜，并不是灵活蜿蜒，而是横向乱窜、笔直伸展，运行的节奏不协调；山势畏缩、不舒展，僵硬而不蜿蜒，所以旧说葬在这里会家亡国灭。',
    'P000026-B001':None,
    'P000026-B011':'活人的福力浅薄，却想谋取王侯之地，就是不衡量自己的力量和德行。',
    'P000027-B001':'依仗现有福分、仗恃当前权势，是第四凶。',
    'P000028-B001':None,
}

def clean_display(block_id,text):
    display=' '.join(text.split()).replace('旧注','古注')
    if block_id=='P000021-B004':
        return display.removesuffix('——杂篇一。')
    if block_id=='P000009-B006':
        return display.replace('已经看不清……','已经看不清；')
    if block_id=='P000013-B024':
        return display.replace('廊庑围护着……','廊庑围护正堂、侧厅辅助主堂一样。')
    if block_id=='P000014-B001':
        return display.removeprefix('……侧厅辅助正堂一样。')
    if block_id=='P000021-B002':
        return display.replace('繁多名目装饰手段……’','繁多名目装饰手段。’')
    if block_id=='P000021-B003':
        return display.replace('……又把其他术数','他们又把其他术数')
    if block_id=='P000024-B024':
        return display.replace('顺就吉……','顺就吉；')
    if block_id=='P000025-B001':
        return display.removeprefix('……')
    if block_id=='P000026-B001':
        return display.removeprefix('……').replace('；然而最终……','。')
    if block_id=='P000027-B008':
        return display.replace('何况将来……','何况后世')
    if block_id=='P000028-B001':
        return ('的人大多把虚假当真实，把附会当可信。世上流传说《葬经》原有二十篇，只存八篇，又把这些杂篇增补进去。观察文字意义，多有不通顺。它先谈“地有四势”，属于世俗选择生旺、辨别衰墓的说法；又列震、离、坎、兑、乾、坤、艮、巽和葬乾、葬坤等内容，属于世俗选择吉龙、讨论分金；再谈方位，属于世俗格量土地、测山涉水；又谈合朔、神迎鬼避、阴阳差错、岁时不合，属于世俗选择年月。古注认为，下篇比上篇尤其荒谬，全都不像郭氏文字，而是后人模仿创作，不值得深究。《锦囊》全书大体以生气为主，以太极为本体；其次分出支脉、垄脉，作为阴阳的作用；再其次讲风水、止聚、形势、骨脉；再其次验证纹理的秀异，说明具体处置是否合宜。学习者应当熟读全书，反复体会。')
    if block_id=='P000028-B002':
        return display.replace('反复体会，就能','这样才能')
    if block_id=='P000028-B003':
        return display.replace('；或舍弃自家吉地而……','；或舍弃自家吉地，')
    if block_id=='P000029-B002':
        return display.removeprefix('……').replace('反而另找','转而另找',1)
    override=DISPLAY_OVERRIDES.get(block_id)
    return override if override else display

def readable_chunks(text,limit=360):
    sentences=[x for x in re.split(r'(?<=[。！？])',text) if x]
    chunks=[]; current=''
    for sentence in sentences:
        if current and len(current)+len(sentence)>limit:
            chunks.append(current); current=sentence
        else:
            current+=sentence
    if current: chunks.append(current)
    return chunks

def main():
    data=rows(MOD)
    if len(data)!=307 or any(not str(x.get('modern_text') or '').strip() for x in data): raise RuntimeError('modernized layer incomplete')
    source=rows(ROOT/'20-source/blocks.jsonl')
    if [x['block_id'] for x in data] != [x['block_id'] for x in source]: raise RuntimeError('source/modernized identity mismatch')
    shutil.copyfile(MOD,FORMAL)
    chapter='正文'
    intro_lines=['这是《葬经》原经与“五经四书解义本”古注的完整白话文。','全书讨论古人怎样从山脉、水流和穴场四周形势判断所谓生气的来、止、聚、散。','正文依原书内篇、外篇、杂篇顺序展开。版式上，较醒目的段落是原经白话；紧随其后的缩进段落，是原书古注的白话解释。古注即使在扫描本中跨页，也仍归在它所解释的原经之后。','书中的福祸、疾病、子嗣和贵贱判断属于传统观念；文字以扫描底本为准，参考文本只作辅助。','个别字形仍有疑义时，本版保留底本文字，不以参考文本强行替换。']
    final=['# 郭璞葬经（五经四书解义本）','', '## 现代白话版','',*intro_lines,'', '## 目录','', '- [内篇一](#内篇一)', '- [内篇二](#内篇二)', '- [内篇三](#内篇三)', '- [内篇四](#内篇四)', '- [外篇一](#外篇一)', '- [杂篇一](#杂篇一)', '- [术语表](#术语表)','']
    process=['# 郭璞葬经（五经四书解义本）过程对照版','']
    mapping=[]; edited=[]; body=[]; pending_main=[]; pending_notes=[]
    def flush_main():
        if not pending_main:
            return
        body.extend(f'<!-- source:{row["block_id"]} -->' for row,_ in pending_main)
        body.extend(['**' + ''.join(display for _,display in pending_main) + '**',''])
        pending_main.clear()
    def flush_notes():
        if not pending_notes:
            return
        body.extend(f'<!-- source:{row["block_id"]} -->' for row,_ in pending_notes)
        joined=''.join(display for _,display in pending_notes).replace('……','').replace('  ',' ').strip()
        for chunk in readable_chunks(joined):
            body.extend(['> '+chunk,''])
        pending_notes.clear()
    for row in data:
        text=row['modern_text'].strip(); display=clean_display(row['block_id'],text); typ=row['block_type']; comp=row['component_id']
        if typ=='heading':
            flush_main()
            flush_notes()
            chapter=text
            body += [f'<!-- source:{row["block_id"]} -->',f'## {chapter}','']
            process += [f'## {row["block_id"]}｜第{row["source_page"]}页｜篇题','',f'原文：{row["source_text"]}','',f'白话：{text}','']
            mapping.append({'schema_version':'1.0','block_id':row['block_id'],'component_id':comp,'destination':'final_reader','reader_heading':'目录','reader_quote':text,'status':'reviewed','review_evidence':'90-audit/modernization-v19/'+row['page_id']+'.json'})
        elif comp in {'C-MAIN','C-COMMENTARY'}:
            label='原经' if comp=='C-MAIN' else '古注'
            if comp=='C-MAIN':
                flush_notes()
                pending_main.append((row,display))
            else:
                flush_main()
                pending_notes.append((row,display))
            process += [f'## {row["block_id"]}｜第{row["source_page"]}页｜{label}','',f'原文：{row["source_text"]}','',f'白话：{text}','']
            mapping.append({'schema_version':'1.0','block_id':row['block_id'],'component_id':comp,'destination':'final_reader','reader_heading':chapter,'reader_quote':display.replace('……','')[:120],'status':'reviewed','review_evidence':'90-audit/modernization-v19/'+row['page_id']+'.json'})
        else:
            flush_main()
            flush_notes()
            body += [f'<!-- source:{row["block_id"]} -->']
            process += [f'## {row["block_id"]}｜证据层','',f'原文：{row["source_text"]}','',f'白话：{text}','']
            mapping.append({'schema_version':'1.0','block_id':row['block_id'],'component_id':comp,'destination':'evidence_only','status':'reviewed','review_evidence':'90-audit/modernization-v19/'+row['page_id']+'.json'})
        out=dict(row); out['edit_status']='reader_copy_reviewed'; edited.append(out)
    flush_main(); flush_notes()
    final += body
    glossary={
      '生气':('地中能使万物发生的气。','本书把它作为山川融结、安葬取用的总纲。'),'乘气':('让葬处承接生气。','既包括寻找气的停聚处，也包括穴位深浅左右的配合。'),
      '龙':('连续起伏的山脉走势。','它是山势脉络的比喻，不是神话动物。'),'支':('平缓隐伏的地势支脉。','本书常把它与高起明显的垄相对。'),'垄':('高起明显的山脊走势。','本书常把它与平缓隐伏的支相对。'),
      '穴':('传统上认为气聚的安葬点。','它必须结合来势、停处、四周护卫和深浅共同判断。'),'止':('山势由行进转为停聚。','书中认为气随势止，穴随形结。'),'风水':('藏风与得水的合称。','本书先讲水怎样界止生气，再讲四周形势怎样减少风散。'),
      '明堂':('穴前较开阔的空间。','它与前方水势、朝应和视野是否舒展有关。'),'玄武':('穴后的来山或屏障。','理想形态是逐渐低垂、能够承托穴场。'),'青龙':('穴场左侧护卫形势。','书中要求它蜿蜒、柔顺而有环抱之情。'),
      '白虎':('穴场右侧护卫形势。','书中要求它驯顺俯伏，并反对把蹲踞当成吉形。'),'朱雀':('穴场前方水势或朝应。','既可指前山，也可指位于明堂前方的水。'),'砂':('穴场周围的小山或地形。','它们承担护卫、朝应、界穴等作用。'),
      '得水':('水在适当位置环抱停聚。','本书把界止来气、曲折有情的水势列为重要条件。'),'藏风':('四周形势挡住直吹之风。','目的是避免书中所谓生气被风吹散。'),'入首':('龙脉进入穴场前的关键一段。','观察它可以判断来脉真假、厚薄和落穴方式。'),
      '势':('远处看见的整体来势。','它关注山脉绵延、起伏和行进方向。'),'形':('近处已经收束的具体地貌。','它关注穴场周围可见的局部形状。'),'裁剪':('调整穴位的具体做法。','包括高低、左右、深浅、吞吐和顺逆等选择。'),
      '五土四备':('五种土色取其四种。','古注排除黑色，并偏重红、黄、白等明润土色。'),'童山':('草木不生的秃山。','本书特指土脉枯槁者，也承认温润石山可能例外。'),'断山':('被凿断的山。','本书区分人为截断与天然开断。'),
      '石山':('融结处全是顽石的山。','古注并不排斥一切有石之山，而排斥焦硬枯燥的石质。'),'过山':('只经过而没有停聚的山。','与横龙滴落、正龙腰落等可结穴情形不同。'),'独山':('孤立而无护卫的山。','若远处有水和砂会合，古注也允许例外。'),
      '四势':('穴场前后左右四方形势。','通常指后玄武、左青龙、右白虎、前朱雀。'),'三吉六凶':('三种有利条件与六种失误。','杂篇借此讨论时日、能力、礼制和安葬方法。'),
      '土圭、玉尺':('测方向与远近的器具。','本书古注把它们进一步解释为内心判断和目力尺度。'),'宗庙卦':('方位配长生八卦的后世术法。','本书古注多次批评它拘泥方位并有伪托嫌疑。')}
    aliases={'生气':['生氣'],'乘气':['乘生氣'],'龙':['龍'],'垄':['壠'],'穴':['穴'],'止':['止'],'风水':['風水'],'明堂':['明堂'],'玄武':['玄武'],'青龙':['青龍'],'白虎':['白虎'],'朱雀':['朱雀'],'砂':['砂'],'得水':['得水'],'藏风':['藏風'],'入首':['入首'],'势':['勢'],'形':['形'],'裁剪':['裁剪'],'五土四备':['五土四備'],'童山':['童山'],'断山':['斷山'],'石山':['石山'],'过山':['過山'],'独山':['獨山'],'四势':['四勢'],'三吉六凶':['三吉','六凶'],'土圭、玉尺':['土圭','玉尺'],'宗庙卦':['宗廟卦'],'支':['支']}
    core={'生气','龙','支','垄','穴'}; entries=[]
    for term,(plain,context) in glossary.items():
      forms=[term,*aliases.get(term,[])]; found=next((x for x in source if x['block_type'] not in {'title','heading','toc','running_header'} and any(f in x['source_text'] for f in forms)),None)
      if not found: raise RuntimeError('no substantive source occurrence for '+term)
      form=next(f for f in forms if f in found['source_text']); pos=found['source_text'].index(form); quote=found['source_text'][max(0,pos-6):min(len(found['source_text']),pos+len(form)+12)]
      entry={'term':term,'plain_definition':plain,'contextual_definition':context,'tier':'core' if term in core else 'supporting','confidence':'qualified','aliases':aliases.get(term,[]),'first_occurrence':{'block_id':found['block_id'],'page_id':found['page_id'],'source_page':found['source_page'],'quote':quote}}
      if term in core:
        examples={'生气':'例：“气乘风则散，界水则止”说的是生气会被风吹散，又会被水势截住。','龙':'例：“龙贵阴”中的龙，是连绵而来的山脉走势。','支':'例：“支葬其巅”说平缓支脉的穴位应取其微微隆起处。','垄':'例：“垄葬其麓”说高起山脊的穴位应取其落势会合处。','穴':'例：“势来形止，是谓全气”说明穴是来势停聚、形局收束的位置。'}
        confusions={'生气':'易混：这里的“气”是本书解释山川与安葬的传统概念，不是现代科学中的气体或能量。','龙':'易混：这里不是神话动物，而是山脉的连续走势。','支':'易混：支脉较平缓隐伏，不等于任意一块平地。','垄':'易混：垄指高起明显的山脊，不是田垄。','穴':'易混：穴是整套山水形势收束出的安葬位置，不是单指挖出的坑。'}
        entry.update({'usage_example':examples[term],'related_terms':['生气','穴'] if term not in {'生气','穴'} else ['龙','势'],'common_confusions':confusions[term]})
      entries.append(entry)
    final += ['## 术语表','']
    for e in entries:
      extra=''
      if e['tier']=='core': extra=f' {e["usage_example"]} {e["common_confusions"]} 相关：'+'、'.join(e['related_terms'])+'。'
      final.append(f'**{e["term"]}**：{e["plain_definition"]} {e["contextual_definition"]}{extra}')
    final.append('')
    manuscript='\n'.join(final)
    (EDIT/'modern-reading.md').write_text(manuscript,encoding='utf-8')
    (EDIT/'final-reader-core.md').write_text(manuscript,encoding='utf-8')
    (ROOT/'60-publication').mkdir(parents=True,exist_ok=True)
    (ROOT/'60-publication/modern-reading.md').write_text(manuscript,encoding='utf-8')
    (EDIT/'process-edition').mkdir(parents=True,exist_ok=True)
    (EDIT/'process-edition/modern-reading.md').write_text('\n'.join(process),encoding='utf-8')
    dump_lines(EDIT/'blocks.jsonl',edited); dump_lines(EDIT/'source-reader-map.jsonl',mapping)
    dump(EDIT/'reader-aids.json',{'schema_version':'1.2','glossary':{'markdown_heading':'术语表','rendering_profile':'compact_final_reader','entries':entries,'excluded_inventory_terms':[]},'introduction':{'markdown_heading':'现代白话版','sections':{'what_this_book_is':intro_lines[0],'who_should_read':intro_lines[0],'reader_value':intro_lines[1],'contents_and_structure':intro_lines[2],'distinctive_features':intro_lines[2],'historical_and_textual_context':intro_lines[3],'how_to_read':intro_lines[2],'limitations_and_cautions':intro_lines[3],'edition_method':intro_lines[3]},'evidence':[{'claim':'原经与古注完整进入读者版','block_ids':[x['block_id'] for x in source if x['component_id'] in {'C-MAIN','C-COMMENTARY'}],'source_pages':list(range(1,30)),'editorial_sources':['10-diagnosis/edition-scope.json']}]}})
    digest=hashlib.sha256((EDIT/'modern-reading.md').read_bytes()).hexdigest()
    print(json.dumps({'blocks':len(data),'mappings':len(mapping),'sha256':digest},ensure_ascii=False))
if __name__=='__main__': main()
