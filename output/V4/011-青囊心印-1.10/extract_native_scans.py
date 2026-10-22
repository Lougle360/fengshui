"""Preserve original JPEG streams, without upsampling or acceptance claims."""
from pathlib import Path
import pymupdf

root = Path(__file__).resolve().parent
with pymupdf.open(root / '00-intake/source.pdf') as doc:
    for i, page in enumerate(doc, 1):
        images = page.get_images()
        if len(images) != 1:
            raise RuntimeError(f'Page {i}: expected exactly one original image')
        data = doc.extract_image(images[0][0])
        target = root / f'20-source/pages/P{i:06}.native.{data["ext"]}'
        if target.exists() and target.read_bytes() != data['image']:
            raise RuntimeError(f'Refusing to overwrite changed image: {target}')
        target.write_bytes(data['image'])
        print(f'{i}: {data["width"]}x{data["height"]} {target.name}')
