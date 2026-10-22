"""Print source and current reader text for given pages (exploration aid).

usage: python peek_pages.py <out.txt> <book> <page> [<page> ...]
"""
import sys

from common import blocks, locate_in_reader

sys.stdout = open(sys.argv[1], "w", encoding="utf-8")
book, pages = sys.argv[2], {int(x) for x in sys.argv[3:]}
for b in blocks(book):
    if b["source_page"] not in pages:
        continue
    print(f"--- {b['block_id']} [{b['block_type']}] from={b.get('continuation_from')} to={b.get('continuation_to')}")
    print("SRC:", (b.get("source_text") or "")[:400])
    print("EDT:", (b.get("modern_text") or "")[:400])
    para, idx = locate_in_reader(book, b.get("modern_text") or "")
    print("PUB:", f"#{idx}", (para or "（未在读者稿中定位到）")[:400])
