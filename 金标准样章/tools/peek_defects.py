"""Show source / edited / published text for given defect ids. usage: peek_defects.py <out.txt> <id> ..."""
import sys

from common import blocks, defects, locate_in_reader

out = open(sys.argv[1], "w", encoding="utf-8")
index = {d["defect_id"]: d for d in defects()}
for did in sys.argv[2:]:
    d = index[did]
    book = d["book"][:3]
    loc = d["location"]
    print(f"=== {did} {d['book']} v={d.get('version')} {loc} {d['category']}/{d.get('subcategory')} "
          f"{d.get('source_type')} sev={d.get('severity')} outcome={d.get('outcome')}", file=out)
    print("DESC:", (d.get("description") or "")[:300], file=out)
    print("BEFORE:", (d.get("before") or "")[:200], file=out)
    print("AFTER:", (d.get("after") or "")[:200], file=out)
    try:
        bl = blocks(book)
    except FileNotFoundError:
        print("  (no blocks)", file=out)
        continue
    hit = [b for b in bl if b["block_id"] == loc.get("block")]
    if not hit and loc.get("page") is not None:
        hit = [b for b in bl if b.get("source_page") == loc["page"]]
    for b in hit[:12]:
        pub = locate_in_reader(book, b.get("modern_text") or "")
        pub = None if pub[0] is None else pub
        print(f"--- {b['block_id']} [{b.get('block_type')}] from={b.get('continuation_from')} to={b.get('continuation_to')}", file=out)
        print("SRC:", b.get("source_text"), file=out)
        print("EDT:", b.get("modern_text"), file=out)
        print("PUB:", "None" if pub is None else f"#{pub[1]} {pub[0][:400]}", file=out)
out.close()
