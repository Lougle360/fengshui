"""Print schema summaries of defect-bearing records in every book workspace (read-only)."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT = Path(r"D:\壮五福\风水项目\output")
PATTERNS = [
    "uncertainty-candidates.jsonl",
    "uncertainty-adjudication.jsonl",
    "uncertain-items.jsonl",
    "events.jsonl",
    "reader-revision-ledger.jsonl",
    "reader-chapter-edits*.jsonl",
    "reader-refinements.jsonl",
    "semantic-repair*.json",
    "fidelity-review.json",
    "reader-review.json",
    "pdf-reader-review.json",
    "quality-report.json",
    "render-audit.json",
]
SKIP = ("snapshots", "_vendor", "review-history")


def workspaces():
    for d in sorted(OUTPUT.iterdir()):
        if d.name == "V4":
            yield from (x for x in sorted(d.iterdir()) if x.is_dir())
        elif d.is_dir() and d.name != "skill-upgrades":
            yield d


def load(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".jsonl":
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def short(v, n=220):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + "…"


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for ws in workspaces():
        if only and only not in ws.name:
            continue
        print(f"\n######## {ws.relative_to(OUTPUT)}")
        for pat in PATTERNS:
            for f in sorted(ws.rglob(pat)):
                if any(s in f.parts for s in SKIP):
                    continue
                data = load(f)
                rel = f.relative_to(ws)
                if isinstance(data, list):
                    keys = Counter(k for r in data if isinstance(r, dict) for k in r)
                    print(f"-- {rel}  rows={len(data)}")
                    print("   keys:", dict(keys.most_common(25)))
                    for field in ("status", "kind", "category", "issue_type", "event", "operation", "reader_impact", "type"):
                        vals = Counter(str(r.get(field)) for r in data if isinstance(r, dict) and field in r)
                        if vals:
                            print(f"   {field}:", dict(vals.most_common(15)))
                    if data:
                        print("   sample:", short(data[len(data) // 2]))
                elif isinstance(data, dict):
                    print(f"-- {rel}  dict keys={list(data)[:25]}")
                    print("   sample:", short(data, 400))


if __name__ == "__main__":
    main()
