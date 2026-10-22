"""Render contact sheets for locating passages in the public-domain Shanghai scan."""
from pathlib import Path
import pymupdf
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parent
pdf=root/'90-audit/external-evidence/Shanghai-地理青囊經解-青囊心印續編.pdf'
out=root/'90-audit/external-evidence/index'
out.mkdir(parents=True,exist_ok=True)
doc=pymupdf.open(pdf)
thumbs=[]
for i,page in enumerate(doc):
    pix=page.get_pixmap(matrix=pymupdf.Matrix(0.22,0.22),colorspace=pymupdf.csGRAY,alpha=False)
    im=Image.frombytes('L',(pix.width,pix.height),pix.samples).convert('RGB')
    thumbs.append((i+1,im))
for start in range(0,len(thumbs),20):
    batch=thumbs[start:start+20]
    cellw,cellh=220,190
    sheet=Image.new('RGB',(cellw*5,cellh*4),'white')
    draw=ImageDraw.Draw(sheet)
    for pos,(number,im) in enumerate(batch):
        im.thumbnail((cellw-10,cellh-24))
        x=(pos%5)*cellw+(cellw-im.width)//2
        y=(pos//5)*cellh+20
        sheet.paste(im,(x,y))
        draw.text(((pos%5)*cellw+5,(pos//5)*cellh+3),f'PDF {number}',fill='black')
    sheet.save(out/f'pages-{batch[0][0]:03}-{batch[-1][0]:03}.png')
print({'pages':len(doc),'sheets':len(list(out.glob('*.png')))})
