import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"D:\壮五福\风水项目\chaoyun-ancient-book-renovator\skills\chaoyun-ancient-book-renovator\scripts")
import text_hygiene as th

V4 = Path(r"D:\壮五福\风水项目\output\V4")
out = open(Path(__file__).with_name("hygiene-probe.txt"), "w", encoding="utf-8")

root = V4 / "001-青囊海角经"
src = {r["block_id"]: r["source_text"] for r in th.read_jsonl(root / "20-source/blocks.jsonl")}
for r in th.read_jsonl(root / "50-edited/blocks.jsonl"):
    if r["block_id"] in ("P000006-B001", "P000007-B001"):
        print("SRC", src[r["block_id"]][:300], file=out)
        print("EDT", r["modern_text"][:300], file=out)
        for m in th.DIRECTIONAL_GAN.finditer(r["modern_text"]):
            print("M", m.start(), repr(r["modern_text"][max(0, m.start() - 10):m.end() + 10]), file=out)
lines = (root / "60-publication/modern-reading.md").read_text(encoding="utf-8").splitlines()
for n in (121, 131, 849, 1545):
    print("L", n, repr(lines[n - 3][:60]), "|", repr(lines[n - 1][:120]), file=out)

for ws in ("002-入地眼全书", "003-平砂玉尺经-1.7"):
    r = V4 / ws
    t = (r / "60-publication/modern-reading.md").read_text(encoding="utf-8")
    for i in th.reader_text_issues(t, json.loads((r / "book.json").read_text(encoding="utf-8"))):
        print(ws[:3], i, file=out)
    for m in re.finditer(r".{20}(?:OCR|识别错误|识别有误|乱码|释读存疑|无法释读|核义模型|自动修复|保守记录|硬校验).{20}", t):
        print(ws[:3], "ctx", m.group(0), file=out)
out.close()
