"""Draw a reproducible random sample from a jsonl file for manual reading.

usage: python sample_records.py <in.jsonl> <out.txt> <per_group> [group_field]
"""
import json
import random
import sys
from collections import defaultdict

src, dst, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
field = sys.argv[4] if len(sys.argv) > 4 else "version"
rows = [json.loads(x) for x in open(src, encoding="utf-8") if x.strip()]
groups = defaultdict(list)
for r in rows:
    groups[r.get(field)].append(r)
rng = random.Random(int(sys.argv[5]) if len(sys.argv) > 5 else 20260930)
out = []
for g in sorted(groups, key=str):
    pick = rng.sample(groups[g], min(n, len(groups[g])))
    out.append(f"\n######## {g}  (total {len(groups[g])}, sampled {len(pick)})")
    for r in pick:
        keys = ["defect_id", "record_kind", "raw_kind", "category", "subcategory", "outcome", "reader_impact", "found_at"]
        head = " | ".join(f"{k}={r.get(k)}" for k in keys if r.get(k) is not None)
        out.append(f"- {head}")
        out.append(f"    text: {str(r.get('text') or r.get('description'))[:160]}")
        if r.get("reason") and r.get("reason") != r.get("text"):
            out.append(f"    reason: {str(r.get('reason'))[:200]}")
        if r.get("before") or r.get("after"):
            out.append(f"    before: {str(r.get('before'))[:90]}  ||  after: {str(r.get('after'))[:90]}")
open(dst, "w", encoding="utf-8").write("\n".join(out))
print("wrote", dst)
