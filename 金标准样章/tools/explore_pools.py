"""Print continuous-passage page scores and fragment candidate pools (exploration aid)."""
import re
import sys
from collections import Counter, defaultdict

from common import CURRENT_VERSIONS, GAP_RE, blocks, defects

sys.stdout.reconfigure(encoding="utf-8")
out = open(sys.argv[1], "w", encoding="utf-8") if len(sys.argv) > 1 else sys.stdout


def p(*a):
    print(*a, file=out)


# ---------------------------------------------------------------- page scoring
D = defects()
typo_by_page = Counter()
known_by_page = Counter()
for d in D:
    pg = (d.get("location") or {}).get("page")
    if not pg or d["version"] not in CURRENT_VERSIONS:
        continue
    if d["subcategory"] in ("错字未校正直接进入译文",) or d["category"] == "识别":
        typo_by_page[(d["book"], pg)] += 1
    if d["category"] not in ("流程噪音",) and d["outcome"] != "not_defect":
        known_by_page[(d["book"], pg)] += 1

for book in ("002", "001"):
    pages = defaultdict(list)
    for b in blocks(book):
        pages[b["source_page"]].append(b)
    feats = {}
    for pg, bl in pages.items():
        body = [b for b in bl if b["block_type"] == "body" and (b.get("modern_text") or "")]
        modern = "".join(b.get("modern_text") or "" for b in bl)
        src = "".join(b.get("source_text") or "" for b in bl)
        f = {
            "gap": len(GAP_RE.findall(modern)),
            "typo": typo_by_page[(book, pg)],
            "cross": sum(1 for b in bl if b.get("continuation_from") or b.get("continuation_to")),
            "figure": sum(1 for b in bl if b["block_type"] == "figure"),
            "title": sum(1 for b in bl if b["block_type"] == "title"),
            "verse": int(bool(re.search(r"[，。].{5,7}[，。].{5,7}[，。]", modern) and re.search(r"(.{7}，.{7}。){2}", modern))),
            "terms": len(re.findall(r"八卦|纳甲|天星|九星|贪狼|巨门|禄存|文曲|廉贞|武曲|破军|左辅|右弼|三合|长生|墓库|干支|河图|洛书|龙|砂|穴|水口|明堂", modern)) > 3,
            "src_chars": len(src),
            "body": len(body),
        }
        feats[pg] = f
    p(f"\n===== {book} pages={len(feats)}")
    wins = []
    for start in sorted(feats):
        for n in (2, 3):
            pgs = [start + i for i in range(n) if start + i in feats]
            if len(pgs) < n:
                continue
            chars = sum(feats[x]["src_chars"] for x in pgs)
            if chars > 2600 or chars < 700:
                continue
            types = sum(1 for k in ("gap", "typo", "cross", "figure", "title", "verse", "terms") if any(feats[x][k] for x in pgs))
            gaps = sum(feats[x]["gap"] for x in pgs)
            typos = sum(feats[x]["typo"] for x in pgs)
            wins.append((types, gaps + typos, -chars, pgs))
    for w in sorted(wins, reverse=True)[:12]:
        types, gt, nchars, pgs = w
        p(f"  pages {pgs} types={types} gap+typo={gt} chars={-nchars}", {x: {k: v for k, v in feats[x].items() if v} for x in pgs})

# ---------------------------------------------------------------- fragment pools
SLOTS = {
    "错字进译文": lambda d: d["subcategory"] == "错字未校正直接进入译文",
    "元女": lambda d: "元女" in (d["description"] or ""),
    "八宅": lambda d: re.search(r"绝命|天医|五鬼|游魂|延年", d["description"] or "") and d["category"] in ("术语", "释读缺口"),
    "版心": lambda d: d["subcategory"] in ("版心页眉混入正文", "版心页眉被当作正文释读"),
    "跨页残句": lambda d: d["subcategory"] in ("残句或切断", "跨页切分", "跨页接续"),
    "经注": lambda d: d["category"] == "归属",
    "忠实性": lambda d: d["subcategory"] in ("误译", "增译或无依据扩写", "漏译", "不确定写成确定"),
    "流程用语": lambda d: d["subcategory"] in ("流程用语混入正文",),
    "真残损": lambda d: d["subcategory"] in ("漫漶不可辨",),
}
for name, pred in SLOTS.items():
    pool = [d for d in D if pred(d) and d["version"] in CURRENT_VERSIONS]
    p(f"\n===== slot {name}: {len(pool)} current  by book {Counter(d['book'] for d in pool)}")
    for d in pool[:40]:
        loc = d.get("location") or {}
        p(f"  {d['defect_id']} {d['book']} {d['version']} p{loc.get('page')} {loc.get('block')} [{d['record_kind']}/{d['subcategory']}/{d['outcome']}] {re.sub(chr(10), ' ', (d['description'] or ''))[:110]} || {re.sub(chr(10), ' ', d.get('reason') or '')[:80]}")
