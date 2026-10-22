"""Probe: 004 unaligned commentary, 002 running-header leaks, 002 乾→干 sample blocks. usage: probe_misc.py <out.txt>"""
import sys

from common import blocks, defects, locate_in_reader

out = open(sys.argv[1], "w", encoding="utf-8")


def show(book, b):
    para, idx = locate_in_reader(book, b.get("modern_text") or "")
    print(f"--- {book} {b['block_id']} p{b.get('source_page')} [{b.get('block_type')}] role={b.get('structural_role')}", file=out)
    print("SRC:", b.get("source_text"), file=out)
    print("EDT:", b.get("modern_text"), file=out)
    print("PUB:", "None" if para is None else f"#{idx} {para[:300]}", file=out)


print("##### 004 commentary_unaligned", file=out)
bl4 = blocks("004")
for i, b in enumerate(bl4):
    if b.get("block_type") == "commentary_unaligned":
        if i:
            show("004", bl4[i - 1])
        show("004", b)
print("##### 002 running headers in reader", file=out)
for b in blocks("002"):
    mt = b.get("modern_text") or ""
    if "入地眼全书卷" in mt and b.get("source_page") in (40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82):
        show("002", b)
print("##### 002 乾 rendered 干", file=out)
n = 0
for b in blocks("002"):
    src, mt = b.get("source_text") or "", b.get("modern_text") or ""
    if "乾龍" in src and "干龙" in mt and len(src) < 160:
        show("002", b)
        n += 1
        if n >= 4:
            break
print("##### defects on 002 header pages", file=out)
for d in defects():
    if d["book"].startswith("002") and d["location"].get("page") in (43, 44, 68, 69, 81, 82) and d["category"] in ("结构", "流程噪音"):
        print(d["defect_id"], d["location"], d["category"], d.get("subcategory"), (d.get("description") or "")[:60], file=out)
out.close()
