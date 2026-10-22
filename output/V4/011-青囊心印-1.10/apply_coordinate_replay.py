"""Apply two independently observed coordinate repairs; never accept source."""
import json
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent
snapshot = root / '90-audit/source-reading/snapshots/before-coordinate-replay'
if snapshot.exists():
    raise SystemExit('Already applied or interrupted: inspect preserved snapshots; refusing overwrite.')
snapshot.mkdir(parents=True)
changes = []
for filename, page, index, box, candidate in [
    ('pages-013-014.json', 13, 9, [699,795,914,1341], 'UC000121'),
    ('pages-019-020.json', 19, 17, [610,787,652,1230], 'UC000122'),
]:
    path = root / '20-source/transcription-inputs' / filename
    before = path.read_bytes()
    (snapshot / filename).write_bytes(before)
    payload = json.loads(before)
    block = next(p for p in payload['pages'] if p['page']==page)['blocks'][index]
    old = {'bbox':block['bbox'], 'regions':block.get('regions')}
    block['bbox'] = box
    if page==19:
        block['regions'] = [box]
    block.setdefault('notes', []).append(candidate + '：根据correction-replay-independent.md并再次查看native原图，仅修正图证范围。')
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    changes.append({'candidate_id':candidate,'block_id':f'P{page:06}-B{index+1:03}',
                    'before':old,'after':{'bbox':box,'regions':block.get('regions')},
                    'text_unchanged':True,'input_sha256':hashlib.sha256(before).hexdigest(),
                    'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(root/'90-audit/source-reading/corrections-coordinate-replay.json').write_text(
    json.dumps({'status':'corrected_not_closed','changes':changes},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
