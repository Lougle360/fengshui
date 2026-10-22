"""Shared statistics for the defect report (imported by build_report.py, runnable for a quick dump)."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

LIB = Path(r"D:\壮五福\风水项目\缺陷库")
BOOK_NAMES = {
    "001": "青囊海角经", "002": "入地眼全书", "003": "平砂玉尺经",
    "004": "郭璞葬经", "011": "青囊心印", "036": "琢玉斧",
}
CATEGORY_ORDER = ["识别", "结构", "归属", "范围", "忠实性", "释读缺口", "术语", "读者层",
                  "出版", "质量门失效", "工具缺陷", "流程噪音"]
KIND_NAMES = {
    "doubt": "疑点账本", "correction": "更正记录", "progress_log": "进度日志",
    "review_finding": "读者审编意见", "text_scan": "终稿扫描", "rework": "返工记录",
}


def load():
    rows = [json.loads(x) for x in (LIB / "defects.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    metrics = json.loads((LIB / "work" / "process-metrics.json").read_text(encoding="utf-8"))
    raw_n = sum(1 for x in (LIB / "work" / "raw.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())
    return rows, metrics, raw_n


def real(rows):
    """Records that describe an actual defect (not noise, not a confirmed false alarm)."""
    return [r for r in rows if r["category"] != "流程噪音" and r["outcome"] != "not_defect"]


def crosstab(rows, a, b):
    t = defaultdict(Counter)
    for r in rows:
        t[a(r)][b(r)] += 1
    return t


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rows, metrics, raw_n = load()
    print("raw", raw_n, "merged", len(rows))
    print("kind", Counter(r["record_kind"] for r in rows))
    print("outcome", Counter(r["outcome"] for r in rows))
    ct = crosstab(rows, lambda r: r["category"], lambda r: r["record_kind"])
    for c in CATEGORY_ORDER:
        print(c, dict(ct[c]))
    print("\nsubcategory (real, non-scan)")
    for (c, s), n in Counter((r["category"], r["subcategory"]) for r in real(rows) if r["record_kind"] != "text_scan").most_common(40):
        print(n, c, s)
    print("\nscan subcategory by book")
    print(crosstab([r for r in rows if r["record_kind"] == "text_scan"], lambda r: r["book"], lambda r: r["subcategory"]))
    print("\nbook x category (real, non-scan)")
    bt = crosstab([r for r in real(rows) if r["record_kind"] != "text_scan"], lambda r: r["book"], lambda r: r["category"])
    for b in sorted(bt):
        print(b, dict(bt[b]))
    print("\ncaused x found (real)")
    cf = crosstab(real(rows), lambda r: r["caused_at"], lambda r: r["found_at"])
    for k in cf:
        print(k, dict(cf[k]))
    print("\nseverity (real)", Counter(r["severity"] for r in real(rows)))
    print("\nbook outcome")
    bo = crosstab([r for r in rows if r["record_kind"] == "doubt"], lambda r: r["book"], lambda r: r["outcome"])
    for b in sorted(bo):
        print(b, dict(bo[b]), "noise", sum(1 for r in rows if r["book"] == b and r["record_kind"] == "doubt" and r["category"] == "流程噪音"))
    print("closure_template", Counter(r["book"] for r in rows if r["closure_template"]))
    print("元女", sum(1 for r in rows if "元女" in (r["description"] or "") + (r["reason"] or "")))
