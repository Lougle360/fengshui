"""Print detailed samples of nested defect records (read-only)."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).with_name("probe_detail.txt")
V4 = Path(r"D:\壮五福\风水项目\output\V4")
OLD = Path(r"D:\壮五福\风水项目\output")


def dump(v, n=1500):
    s = json.dumps(v, ensure_ascii=False, indent=1)
    return s if len(s) <= n else s[:n] + "\n…"


def jl(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


lines = []
w = lines.append

for p in sorted(V4.glob("*/50-edited/reader-review.json")) + sorted(V4.glob("*/50-edited/review-history/*/reader-review.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    w(f"\n== {p.relative_to(V4)}")
    w("blocking: " + dump(d.get("blocking_issues"), 800))
    for k, v in (d.get("dimensions") or {}).items():
        if v.get("findings"):
            w(f"  dim {k} {v.get('verdict')}: " + dump(v["findings"][:2], 700))

for p in sorted(V4.glob("*/90-audit/fidelity-review.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    blocks = d.get("blocks") or []
    w(f"\n== {p.relative_to(V4)} blocks={len(blocks)}")
    bad = [b for b in blocks if isinstance(b, dict) and str(b.get("verdict", b.get("status"))) not in ("passed", "accept", "faithful")]
    w(f"  non-pass={len(bad)} keys={list(blocks[0]) if blocks else None}")
    w(dump(bad[:2] or blocks[:1], 900))

p = V4 / "001-青囊海角经/90-audit/semantic-repair-v3.json"
d = json.loads(p.read_text(encoding="utf-8"))
w(f"\n== {p.relative_to(V4)}")
w(dump(d["repairs"][:2], 1500))

for p in sorted((V4 / "011-青囊心印-1.10/90-audit/source-reading").glob("corrections-*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    w(f"\n== {p.relative_to(V4)} type={type(d).__name__}")
    w(dump(d if isinstance(d, dict) else d[:2], 1200))
    break

rev = sorted((V4 / "004-郭璞葬经-1.8/90-audit/source-page-reviews-v19b").glob("*"))
w(f"\n== 004 source-page-reviews-v19b files={len(rev)} {[x.name for x in rev[:5]]}")
for x in rev:
    if x.suffix == ".json":
        w(dump(json.loads(x.read_text(encoding="utf-8")), 1500))
        break

for rel in ["002-入地眼全书/90-audit/uncertain-items.jsonl"]:
    rows = jl(V4 / rel)
    w(f"\n== {rel}")
    w(dump(rows[5], 1500))

rows = jl(OLD / "chaoyun-full-zengshi-dili-zhuoyufu/90-audit/uncertain-items.jsonl")
w("\n== chaoyun-full uncertain-items")
w(dump({k: rows[3][k] for k in ("source", "modern_text", "judge_verdict", "judge_issues", "local_issues", "issues", "uncertainty")}, 1500))

for rel in ["001-青囊海角经/90-audit/uncertainty-candidates.jsonl", "003-平砂玉尺经-1.7/90-audit/uncertainty-candidates.jsonl",
            "004-郭璞葬经-1.8/90-audit/uncertainty-candidates.jsonl", "011-青囊心印-1.10/90-audit/uncertainty-candidates.jsonl"]:
    rows = jl(V4 / rel)
    w(f"\n== {rel}")
    w(dump(rows[len(rows) // 3], 900))

for rel in ["001-青囊海角经/90-audit/uncertainty-adjudication.jsonl", "003-平砂玉尺经-1.7/90-audit/uncertainty-adjudication.jsonl",
            "004-郭璞葬经-1.8/90-audit/uncertainty-adjudication.jsonl"]:
    rows = jl(V4 / rel)
    w(f"\n== {rel}")
    conf = [r for r in rows if r.get("status") == "resolved_confirmed"]
    w(dump(conf[:1] or rows[:1], 1200))

for rel in ["002-入地眼全书/90-audit/events.jsonl"]:
    rows = jl(V4 / rel)
    w(f"\n== {rel}")
    w(dump([r for r in rows if r.get("event") == "cross_page_carryover_removed"][:1], 900))
    w(dump([r for r in rows if r.get("event") == "source_correction_reapplied"][:1], 900))

for p in sorted(V4.glob("*/50-edited/editorial-report.json")):
    w(f"\n== {p.relative_to(V4)}")
    w(dump(json.loads(p.read_text(encoding="utf-8")), 900))

OUT.write_text("\n".join(lines), encoding="utf-8")
print("ok", len(lines))
