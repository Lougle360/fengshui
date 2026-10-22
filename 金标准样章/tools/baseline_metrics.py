"""Baseline metrics of the current AI draft on the gold passage (input: gold_items.json)."""
import json
import re
import sys

from common import GAP_RE, GOLD

sys.stdout.reconfigure(encoding="utf-8")
PROCESS_RE = re.compile(r"OCR|识别错误|释读|模型|乱码|校验|原文中|原文存在")
META_RE = re.compile(r"文中提到|文中还提到|原文提到|这一短语")
HEADER_RE = re.compile(r"入地眼全书卷|李桂林")

data = json.loads((GOLD / "tools" / "gold_items.json").read_text(encoding="utf-8"))
texts = [b["current_text"] for b in data["passage"]["blocks"] if b["current_text"]]
joined = "\n".join(texts)
chars = len(re.sub(r"\s", "", joined))
gaps = len(GAP_RE.findall(joined))
qian = sum(1 for b in data["passage"]["blocks"] for i in b["issues"] if i.startswith("原文“乾”"))
print(f"现稿字数 {chars}")
print(f"不详类 {gaps}  每万字 {gaps / chars * 10000:.0f}")
print(f"流程用语 {len(PROCESS_RE.findall(joined))}")
print(f"元叙述(文中提到等) {len(META_RE.findall(joined))}")
print(f"版心残留 {len(HEADER_RE.findall(joined))}")
print(f"乾误作干段块 {qian}")
