"""List current-version defects on given pages. usage: list_page_defects.py <out.txt> <book>:<page>,<page> ..."""
import sys

from common import CURRENT_VERSIONS, defects


def is_current(d):
    return d.get("version") in CURRENT_VERSIONS or any(v in CURRENT_VERSIONS for v in d.get("versions") or [])


out = open(sys.argv[1], "w", encoding="utf-8")
want = {}
for arg in sys.argv[2:]:
    book, pages = arg.split(":")
    want[book] = {int(p) for p in pages.split(",")}
for d in defects():
    book = d["book"][:3]
    page = d["location"].get("page")
    if book in want and page in want[book] and is_current(d):
        desc = (d.get("description") or "").replace("\n", " ")[:80]
        print(d["defect_id"], book, page, d["location"].get("block"), d["category"], d.get("subcategory"),
              d.get("source_type"), desc, file=out)
out.close()
