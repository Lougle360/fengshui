"""Count 乾 (trigram / direction) rendered as 干 in current reader texts."""
import re
import sys

from common import OUTPUT, WORKSPACES

sys.stdout.reconfigure(encoding="utf-8")
AFTER = set("峰峯龙山方位宫卦坤艮巽亥甲壬水砂向穴")
BEFORE_OK = set("天主大树若相")
for book, ws in WORKSPACES.items():
    t = (OUTPUT / ws / "60-publication" / "modern-reading.md").read_text(encoding="utf-8")
    hits = []
    for m in re.finditer("干", t):
        i = m.start()
        prev, nxt = t[i - 1:i], t[i + 1:i + 2]
        if prev in BEFORE_OK or nxt == "支":
            continue
        if nxt in AFTER or prev in "坤艮巽亥甲壬、":
            hits.append(t[max(0, i - 6):i + 7].replace("\n", " "))
    print(book, "干(疑为乾)", len(hits), "| 乾", t.count("乾"), hits[:5])
