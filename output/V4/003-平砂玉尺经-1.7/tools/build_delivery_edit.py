"""Book-specific, reversible editing of AI additions; no source prose rewriting."""
from pathlib import Path
import re
import json
import hashlib
import difflib

ROOT = Path(__file__).resolve().parents[1]
EDIT = ROOT / '50-edited/delivery-edit'
SOURCE = ROOT / '50-edited/modern-reading.md'
FINAL_BLOCKS = ROOT / '40-modernized/final-reader-clean-blocks.jsonl'

FRONT = '''# 平砂玉尺经

白话文版

传本题署：刘秉忠述、刘基解、赖从谦发挥

现代编校：葛超云

制作：壮五福国学院

## 出版说明

本书按现存传本的六篇次序编排。书中的吉凶、福祸判断属于传统堪舆观念。原文不能确定的地方保留简短说明；图下注解及书末词语解释为编者所加。上述作者姓名依据传本题署，不据此断定全书实际作者。

本书主要讲平原地形中如何根据山脉、水流和周围地形，判断地势从哪里来、在哪里收住，再找到具体的穴位和朝向。六篇的顺序是：先审大势，再分辨气的类别；接着寻龙、审穴，查看周围的砂山，最后才处理立向。这个顺序就是全书的主线。

'''
CHAPTERS = {
    '卷首：先辨认这部传本': '卷首',
    '第一章：审势——从水看地势的来路': '第一篇　审势',
    '第二章：审气——给观察结果加上分类': '第二篇　审气',
    '第三章：寻龙——判断仍在走还是已经停': '第三篇　寻龙',
    '第四章：审穴——从来路找到具体落点': '第四篇　审穴',
    '第五章：审砂——用周围形态复核': '第五篇　审砂',
    '第六章：审向——最后才处理方向': '第六篇　审向',
}

# Exact, inspected editorial insertions inside existing translated paragraphs.
# Original paragraphs remain in the immutable working snapshot and diff.
PROSE_EDITS = {
    '原文结尾有数字“7”，可能是页码或标记，具体所指不详。': '',
    '原文中夹有“上人經下 卷之一 王大經下 卷之 二”的文字，属于排版错乱的卷次标注。': '',
    '原文末尾有“主尺經下 卷之”的内容，为书名加卷次的标识，“主”字保留原文原样。': '',
    '此处出现“中王尺 卷之四 十”的文字，疑似书名或卷次标识，具体所指不详。': '',
    '文末標註了“玉尺經 卷之四 十四”，這具體所指不详。': '',
    '文末標註了“王尺經 卷之四 十五”，這具體所指不详。': '',
    '文末標註了“五尺經下 卷之四 十八”，這具體所指不详。': '',
    '此段出自《玉尺經》下卷，原文標記為“卷之國 十九”，其中“國”字疑為“四”或“五”之誤，具體分卷及頁碼不详。': '',
    '第57页整页组合图': '组合图',
    '第59页整页图式': '回龙与截气诸图',
    '> 编者核查：原句把‘笔直逼仄’与‘平坦开阔’都判作阴，内部相互冲突，可能有讹脱；在未取得更可靠底本前，不据此建立阴阳对照规则。': '> 注：原文将“笔直逼仄”与“平坦开阔”均写作阴，疑有讹误。',
    '“少经方”“衰弱方”“长生方”为风水术语，原文未做解释，含义依风水常识确定；': '“少经方”所指不明；',
    "文中提到'1亥龍起酈'，其中数字'1'必须保留。接着描述": "原文开头‘1亥龍起酈’有疑字。下文说，",
    '本段出自《人经》下卷之二，页码为19。': '',
    '内容属于《天经下》卷之二，页码为十十十。': '',
    '此处提及《玉尺经》卷三上。': '',
    '此处穿插有《尺經》卷之四的章节标识。': '',
    '此处穿插有卷之四十的标识。': '',
    '本段出自《玉尺释》下卷之四，页码为二十四。': '',
    '本段出自卷之四，页码114。': '',
    '此段出自《玉尺经》卷六。': '',
    '疑似OCR识别错误或原文残缺': '字句有误或残缺',
    '可能是OCR识别误差': '可能是文字讹误',
    '此段出自《尺经》卷六十五，原文末尾文意未完，可能存在脱文或错乱。': '（原文至此未完，后文有缺损。）',
}

# Inspected standalone running titles, duplicated volume credits and page
# numerals. Keep their source markers and original text in the working archive.
PRINT_FURNITURE = {
    'P000013-B001', 'P000014-B004', 'P000017-B007', 'P000024-B004',
    'P000030-B014', 'P000030-B015', 'P000032-B005', 'P000033-B004',
    'P000034-B002', 'P000039-B009', 'P000040-B008', 'P000040-B009',
    'P000041-B002', 'P000046-B007', 'P000049-B001', 'P000052-B002',
    'P000052-B004', 'P000061-B005', 'P000061-B006', 'P000064-B002',
    'P000066-B004', 'P000067-B007', 'P000071-B003', 'P000075-B006',
    'P000084-B003', 'P000084-B004', 'P000085-B002',
}

CAPTIONS = [
    '从上方的长砂看到中部穴位，再比较两侧回抱与右侧向外斜出的支砂。',
    '看腰肋分出的支砂：是回抱堂局，还是向外伸展。',
    '沿长直的来脉，先看中途的枝水和转折，再看末端两侧的水是否回抱。',
    '来脉虽然斜入，穴前的水和两侧护砂仍可能使它收正。来路与取穴方向要分别看。',
    '看两旁枝水如何把来脉约束在中央。',
    '中央地面较平，没有明显凹窝或突起；取点要结合两侧水流的位置。',
    '居中的大砂与周围小砂，形似群雁相随。要看各处是否朝向堂局。',
    '看支水、支砂在何处倒插、穿破主体。',
    '这一页包含多幅小图，需分别看各图的来脉和收束处。',
    '砂体两端尖，像船或梭子；注意侧面的枝水是否回钩入腹。',
    '沿砂体看水流切入、回钩的位置。原书据此讨论从侧面取穴。',
    '与前图比较，注意钩形水流位于哪一侧。图中文字模糊，不能据此确定方位。',
    '先看来脉是否回转，再看水流是否随之回转。原书认为，只有砂回而水不回，还不能算真回龙。',
    '这一页应分成几个局部看；画在一起的线条，不一定表示地形相连。',
    '从上方山体看到平坡，再找两侧弯出的月角、细小水迹和前方界限。',
    '先找来龙和堂前水流，再分清水从哪里来、往哪里去。',
    '这一幅补充前图的水口位置。图中文字残缺，不能据此补出完整水法。',
    '比较靠近穴前的水与外围水路，看它们的流向是否相同。',
    '这是前图的局部，需要结合前图阅读。',
    '沿水线看各股水在何处会合、又从哪里分流。',
    '本图对应的文字残缺较多，具体方位不能确定。',
    '原书在来脉末端余势过长时主张退后取穴。看图中末端与取点的位置关系。',
    '外观上显眼的来路未必通向真穴，还要结合左右护砂和前方朝应判断。',
    '地面宽平时，注意细小的高低痕迹、左右两翼和前方朝应。',
    '结合前图，比较中央和边角分别受到哪些地形朝应。',
    '来脉细节不清时，原书借前方朝山和左右护砂辅助寻找穴位。',
    '图中画出周围峰峦的位置与高低。原书据此所作的官禄判断属于传统说法。',
    '与前图合看四周峰峦的朝向，不能只凭一座山峰判断。',
    '地形宽平混杂时，先追来脉，再看左右护砂与前方朝应是否指向同一处。',
    '结合前图看各处朝应。图中小字有未能辨清之处。',
    '卷末图文残损，保留原图。',
]

# Verified sentence continuations split only by a source page/block boundary.
# Both source comments stay in place and in order after the visible paragraphs
# are joined.
MERGE_PAIRS = [
    ('P000004-B004', 'P000004-B005'),
    ('P000004-B006', 'P000005-B001'),
    ('P000021-B004', 'P000021-B005'),
    ('P000021-B006', 'P000021-B007'),
    ('P000034-B008', 'P000034-B009'),
    ('P000044-B005', 'P000044-B006'),
    ('P000061-B001', 'P000061-B002'),
    ('P000069-B007', 'P000069-B008'),
    ('P000074-B014', 'P000075-B001'),
    ('P000078-B004', 'P000078-B005'),
    ('P000082-B001', 'P000082-B002'),
]

def paragraphize(text, target=430, threshold=620):
    """Split only long reader paragraphs at existing sentence boundaries."""
    if len(text) <= threshold:
        return text
    pieces = re.findall(r'.*?(?:[。！？](?:[”’』）])?|；)|.+$', text)
    paragraphs, current = [], ''
    for piece in pieces:
        if current and len(current) + len(piece) > target:
            paragraphs.append(current)
            current = piece
        else:
            current += piece
    if current:
        paragraphs.append(current)
    return '\n\n'.join(paragraphs)

def rebuild_source_body(body, final_rows):
    """Rebuild every source interval instead of guessing marker offsets."""
    global_caption_index = 0
    rebuilt = []
    cursor = 0
    markers = list(re.finditer(r'<!-- source:(.*?) -->', body))
    assert [m.group(1) for m in markers] == [r['block_id'] for r in final_rows]

    for marker, record in zip(markers, final_rows):
        segment = body[cursor:marker.start()]
        cursor = marker.end()
        structural = []
        for raw_line in segment.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('## ') and line[3:] in CHAPTERS:
                structural.append('# ' + CHAPTERS[line[3:]])
            elif re.match(r'^### 原书物理页 ', line):
                continue
            elif line.startswith('#### 图式：'):
                structural.append('### ' + line.removeprefix('#### 图式：').replace('（原图存档参考）', '（原图）'))
            elif record['reader_disposition'] == 'nontext_figure' and line.startswith('!['):
                structural.append(line.replace('（原图存档参考）', '（原图）'))
            elif record['reader_disposition'] == 'nontext_figure' and line.startswith('**读图顺序与本图边界：** '):
                structural.append('> 图注：' + CAPTIONS[global_caption_index])
                global_caption_index += 1
            elif record['reader_disposition'] == 'nontext_figure' and line.startswith('**使用边界：'):
                structural.append('> 原图模糊，仅保留原图，不承担教学证明。')
            elif line.startswith('# '):
                structural.append(line)

        if record['reader_disposition'] == 'reader_text':
            structural.append(paragraphize(record['final_reader_text_clean']))
        cleaned = '\n\n'.join(structural).strip()
        if cleaned:
            rebuilt.append(cleaned)
        rebuilt.append(f"<!-- source:{record['block_id']} -->")

    assert global_caption_index == len(CAPTIONS), global_caption_index
    tail = body[cursor:].strip()
    if tail:
        # Body tails must contain no unaccounted prose after the final marker.
        assert not re.search(r'\S', tail), tail[:200]
    result = '\n\n'.join(rebuilt)

    for left_id, right_id in MERGE_PAIRS:
        left_raw = next(r['final_reader_text_clean'] for r in final_rows if r['block_id'] == left_id)
        right_raw = next(r['final_reader_text_clean'] for r in final_rows if r['block_id'] == right_id)
        left = paragraphize(left_raw)
        right = paragraphize(right_raw)
        old_pair = (
            f'{left}\n\n<!-- source:{left_id} -->\n\n'
            f'{right}\n\n<!-- source:{right_id} -->'
        )
        new_pair = (
            f'{paragraphize(left_raw + right_raw)}\n\n<!-- source:{left_id} -->\n'
            f'<!-- source:{right_id} -->'
        )
        assert old_pair in result, (left_id, right_id)
        result = result.replace(old_pair, new_pair, 1)
    return result

def main():
    original = SOURCE.read_text(encoding='utf-8')
    final_rows = [json.loads(line) for line in FINAL_BLOCKS.read_text(encoding='utf-8').splitlines() if line.strip()]
    final_map = {row['block_id']: row for row in final_rows}
    EDIT.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    snapshot = EDIT / f'working-input-{sha[:12]}.md'
    if not snapshot.exists():
        snapshot.write_bytes(SOURCE.read_bytes())
    body = original[original.index('## 卷首：'):original.index('# 附录一：')]
    body = rebuild_source_body(body, final_rows)
    changes = [{'method': 'source_interval_rebuild', 'blocks': len(final_rows)}]
    # Prove that changes outside explicitly identified editorial lines did not
    # alter the existing source-bearing prose or remove figure references.
    assert re.findall(r'<!-- source:(.*?) -->', original) == re.findall(r'<!-- source:(.*?) -->', body)
    assert re.findall(r'!\[[^\]]*\]\(([^)]+)\)', original) == re.findall(r'!\[[^\]]*\]\(([^)]+)\)', body)
    glossary = (EDIT / '术语简释.md').read_text(encoding='utf-8')
    result = FRONT + body + '\n\n' + glossary
    result = result.replace('](assets/', '](../assets/')
    output = EDIT / '白话交付稿.md'
    if output.exists():
        previous = output.read_bytes()
        history = EDIT / ('previous-' + hashlib.sha256(previous).hexdigest()[:12] + '.md')
        if not history.exists():
            history.write_bytes(previous)
    output.write_text(result, encoding='utf-8')
    (EDIT / '修改记录.json').write_text(json.dumps({
        'input': str(snapshot), 'input_sha256': sha,
        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'scope': 'AI framing and layout preparation; existing source-bearing prose retained',
        'status': 'pending_independent_review',
        'source_ids_retained': len(re.findall(r'<!-- source:', body)),
        'figures_retained': len(re.findall(r'!\[', body)),
        'line_edits': changes,
        'front_matter': 'replace process introduction with brief publication note',
        'back_matter': 'replace template glossary and production indexes with compact authored terms',
        'publication_status': 'not_formally_accepted; prior acceptance does not transfer',
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    (EDIT / '修改对照.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), result.splitlines(True), fromfile='工作版', tofile='白话交付稿')), encoding='utf-8')
    print(output)

if __name__ == '__main__':
    main()
