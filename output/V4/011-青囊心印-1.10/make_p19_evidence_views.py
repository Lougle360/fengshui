"""Create reversible diagnostic views of P19 faded ink; never changes source evidence."""
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import hashlib, json

root=Path(__file__).resolve().parent
source=root/'20-source/pages/P000019.native.jpeg'
out=root/'90-audit/source-reading/p19-evidence-views'
out.mkdir(parents=True,exist_ok=True)
img=Image.open(source).convert('L')
# Include context around the registered faded region so vertical columns remain attributable.
crop_box=(590,760,810,1240)
crop=img.crop(crop_box)
views={
 '00-gray-4x.png': crop.resize((880,1920),Image.Resampling.LANCZOS),
 '01-autocontrast-4x.png': ImageOps.autocontrast(crop,cutoff=(0.5,0.5)).resize((880,1920),Image.Resampling.LANCZOS),
 '02-contrast-3x-sharp.png': ImageEnhance.Contrast(crop).enhance(3.0).filter(ImageFilter.UnsharpMask(2,180,2)).resize((880,1920),Image.Resampling.NEAREST),
 '03-equalize-4x.png': ImageOps.equalize(crop).resize((880,1920),Image.Resampling.NEAREST),
}
for threshold in (150,170,190,210,225):
    views[f'10-threshold-{threshold}.png']=crop.point(lambda p,t=threshold: 255 if p>t else 0).resize((880,1920),Image.Resampling.NEAREST)
records=[]
for name,view in views.items():
    path=out/name
    view.save(path)
    records.append({'path':str(path.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'derivative_only':True,'source_crop':list(crop_box)})
# Column strips are rotated only for legibility. Coordinates stay in the original image.
for idx,box in enumerate(((730,760,785,1230),(680,760,735,1230),(635,760,685,1230),(590,760,640,1230)),1):
    strip=ImageOps.autocontrast(img.crop(box),cutoff=(0.5,0.5)).resize(((box[2]-box[0])*8,(box[3]-box[1])*8),Image.Resampling.LANCZOS)
    strip=strip.rotate(90,expand=True)
    name=f'20-column-{idx}-rotated.png'
    path=out/name
    strip.save(path)
    records.append({'path':str(path.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'derivative_only':True,'source_crop':list(box),'rotation_degrees':90})
# Tight page-column segments avoid screen downscaling and make residual strokes inspectable.
for cidx,(x0,x1) in enumerate(((740,784),(696,740),(652,696)),1):
    for sidx,(y0,y1) in enumerate(((790,990),(970,1170),(1150,1343)),1):
        box=(x0,y0,x1,y1)
        seg=ImageOps.autocontrast(img.crop(box),cutoff=(0.2,0.2)).resize(((x1-x0)*10,(y1-y0)*10),Image.Resampling.LANCZOS)
        name=f'30-col-{cidx}-seg-{sidx}.png'
        path=out/name
        seg.save(path)
        records.append({'path':str(path.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'derivative_only':True,'source_crop':list(box)})
(out/'manifest.json').write_text(json.dumps({'source':str(source.relative_to(root)).replace('\\','/'),
 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'views':records,
 'warning':'Pixel transforms are diagnostic views, not independent evidence and cannot recreate absent strokes.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'views':len(records),'directory':str(out),'source_unchanged':True},ensure_ascii=False))
