"""Typeset the accepted modern-language manuscript."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, CondPageBreak, Image, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
import reportlab.lib.textsplit as textsplit
import reportlab.platypus.paragraph as paragraph_module

CANNOT_START = '，。；：？！、）》】」』”’％,.;:!?)]'
CANNOT_END = '（《【「『“‘('

def chinese_split(word, widths, max_widths):
    """Backtrack a glyph at prohibited breaks instead of stranding punctuation."""
    if not isinstance(max_widths, (tuple, list)):
        max_widths = [max_widths]
    result, start = [], 0
    while start < len(word):
        limit = max_widths[min(len(result), len(max_widths)-1)]
        end, used = start, 0
        while end < len(word) and used + widths[end] <= limit + 0.001:
            used += widths[end]
            end += 1
        end = max(start+1, end)
        if end < len(word):
            while end > start+1 and (word[end] in CANNOT_START or word[end-1] in CANNOT_END):
                end -= 1
        result.append([limit-sum(widths[start:end]), word[start:end]])
        start = end
    return result

textsplit.dumbSplit = chinese_split
textsplit.ALL_CANNOT_START += CANNOT_START
paragraph_module.ALL_CANNOT_START += CANNOT_START

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '60-publication/modern-reading.md'
OUTPUT = ROOT / '60-publication/candidates/平砂玉尺经·现代白话版-candidate.pdf'
WIDTH, HEIGHT = 595.28, 841.89
MARGIN = 54
pdfmetrics.registerFont(TTFont('Reader', 'C:/Windows/Fonts/Deng.ttf'))
pdfmetrics.registerFont(TTFont('ReaderBold', 'C:/Windows/Fonts/Dengb.ttf'))
pdfmetrics.registerFontFamily('Reader', normal='Reader', bold='ReaderBold', italic='Reader', boldItalic='ReaderBold')

BASE = dict(fontName='Reader', fontSize=11.5, leading=19.5, wordWrap='CJK', textColor=HexColor('#242424'))
STYLES = {
    'body': ParagraphStyle('body', **BASE, spaceAfter=9, firstLineIndent=23, allowWidows=0, allowOrphans=0),
    'note': ParagraphStyle('note', fontName='Reader', fontSize=9.5, leading=15.5, wordWrap='CJK', textColor=HexColor('#565656'), spaceAfter=11),
    'warning': ParagraphStyle('warning', fontName='Reader', fontSize=9.5, leading=15.5, wordWrap='CJK', textColor=HexColor('#565656'), spaceAfter=11, keepWithNext=True),
    'h1': ParagraphStyle('chapter', fontName='ReaderBold', fontSize=21, leading=31, wordWrap='CJK', spaceAfter=22, keepWithNext=True),
    'h2': ParagraphStyle('subsection', fontName='ReaderBold', fontSize=14, leading=23, spaceBefore=14, spaceAfter=9, keepWithNext=True, wordWrap='CJK'),
    'caption': ParagraphStyle('caption', fontName='ReaderBold', fontSize=11, leading=18, spaceAfter=9, keepWithNext=True, wordWrap='CJK'),
    'cover': ParagraphStyle('cover', fontName='ReaderBold', fontSize=36, leading=54, alignment=1, textColor=HexColor('#203B32')),
    'credit': ParagraphStyle('credit', fontName='Reader', fontSize=11, leading=22, alignment=1, spaceAfter=5, wordWrap='CJK'),
}

def html(text):
    text = escape(text)
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

class Book(SimpleDocTemplate):
    def beforeDocument(self):
        self.chapter = ''
    def afterFlowable(self, flow):
        if isinstance(flow, Paragraph) and hasattr(flow, 'anchor'):
            self.canv.bookmarkPage(flow.anchor)
            level = getattr(flow, 'anchor_level', 0)
            title = getattr(flow, 'anchor_title', flow.getPlainText())
            self.canv.addOutlineEntry(title, flow.anchor, level)
            self.notify('TOCEntry', (level, title, self.page, flow.anchor))
            self.chapter = title

def furniture(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFillColor(HexColor('#777777'))
    canvas.setFont('Reader', 8)
    canvas.drawString(MARGIN, HEIGHT-30, '平砂玉尺经')
    canvas.setStrokeColor(HexColor('#DDDDDD'))
    canvas.line(MARGIN, HEIGHT-38, WIDTH-MARGIN, HEIGHT-38)
    canvas.drawCentredString(WIDTH/2, 26, str(doc.page))
    canvas.restoreState()

def main():
    text = SOURCE.read_text(encoding='utf-8')
    cover_title = Paragraph('平砂玉尺经', STYLES['cover'])
    cover_title.anchor = 'book-title'
    cover_title.anchor_level = 0
    cover_title.anchor_title = '平砂玉尺经'
    story = [Spacer(1, 135), cover_title, Spacer(1, 12),
             Paragraph('白话文版', STYLES['credit']), Spacer(1, 70)]
    front, body = text.split('## 出版说明', 1)
    for line in front.splitlines():
        if line.startswith(('传本题署', '现代编校', '制作')):
            story.append(Paragraph(html(line), STYLES['credit']))
    story.append(PageBreak())
    story.append(Paragraph('目录', STYLES['h1']))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle('toc', fontName='Reader', fontSize=12, leading=28, wordWrap='CJK', rightIndent=20),
        ParagraphStyle('toc-sub', fontName='Reader', fontSize=10.5, leading=22, wordWrap='CJK', leftIndent=24, rightIndent=20),
    ]
    toc.dotsMinLevel = 0
    story.append(toc)
    # Publication note shares the first prose page with the original preface;
    # it does not consume a nearly empty standalone page.
    story.append(PageBreak())
    publication_note = Paragraph('出版说明', STYLES['h2'])
    publication_note.anchor = 'publication-note'
    publication_note.anchor_level = 1
    publication_note.anchor_title = '出版说明'
    story.append(publication_note)
    lines = body.splitlines()
    heading_count = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith('<!--'):
            continue
        heading = re.match(r'^(#{1,3}) (.+)', line)
        if heading:
            level, name = len(heading[1]), heading[2]
            if level == 1:
                if name != '卷首':
                    story.append(CondPageBreak(520))
                para = Paragraph(html(name), STYLES['h1'])
                para.anchor = f'chapter-{heading_count}'
                para.anchor_level = 0
                para.anchor_title = name
                heading_count += 1
                story.append(para)
            elif level == 2:
                para = Paragraph(html(name), STYLES['h2'])
                para.anchor = f'section-{heading_count}'
                para.anchor_level = 1
                para.anchor_title = name
                heading_count += 1
                story.append(para)
            else:
                # Keep each figure title, image and associated caption together.
                group = [Paragraph(html(name), STYLES['caption'])]
                while i < len(lines) and (not lines[i].strip() or lines[i].startswith('<!--')):
                    i += 1
                match = re.match(r'!\[.*?\]\((.*?)\)', lines[i].strip()) if i < len(lines) else None
                if match:
                    image_path = (SOURCE.parent / match[1]).resolve()
                    img = Image(str(image_path))
                    scale = min((WIDTH-2*MARGIN-24)/img.imageWidth, 270/img.imageHeight)
                    img.drawWidth = img.imageWidth * scale
                    img.drawHeight = img.imageHeight * scale
                    img.hAlign = 'CENTER'
                    group.extend([img, Spacer(1, 9)])
                    i += 1
                    while i < len(lines) and (not lines[i].strip() or lines[i].startswith('<!--')):
                        i += 1
                    if i < len(lines) and lines[i].startswith('>'):
                        group.append(Paragraph(html(lines[i].lstrip('> ').removeprefix('图注：')), STYLES['note']))
                        i += 1
                story.append(KeepTogether(group))
            continue
        if line.startswith('!['):
            raise ValueError('Figure missing heading: ' + line)
        note = line.startswith('>')
        value = line.lstrip('> ') if note else line
        style = STYLES['note'] if note or heading_count == 0 else STYLES['body']
        if note and value.startswith(('以下', '此段')):
            style = STYLES['warning']
        # Split only at complete sentence boundaries; no words or punctuation
        # are removed. This prevents multi-page solid walls of text.
        chunks, current = [], ''
        for sentence in re.findall(r'.+?(?:[。！？](?:[”’」』])?|$)', value):
            current += sentence
            if len(current) >= 230:
                chunks.append(current)
                current = ''
        if current:
            chunks.append(current)
        for chunk in chunks:
            story.append(Paragraph(html(chunk), style))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Book(str(OUTPUT), pagesize=(WIDTH, HEIGHT), rightMargin=MARGIN, leftMargin=MARGIN,
               topMargin=57, bottomMargin=48, title='平砂玉尺经·白话文版', author='葛超云',
               pageCompression=1)
    doc.multiBuild(story, onFirstPage=furniture, onLaterPages=furniture)
    print(OUTPUT)

if __name__ == '__main__':
    main()
