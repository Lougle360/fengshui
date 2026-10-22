"""Collect defect-bearing records from every book workspace into one raw file.

Read-only with respect to book workspaces. Output: 缺陷库/work/raw.jsonl
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\壮五福\风水项目")
OUTPUT = ROOT / "output"
LIB = ROOT / "缺陷库"
WORK = LIB / "work"

# workspace dir -> (book group, label). Book 003 1.5 is superseded by the 1.7 workspace,
# which keeps the 1.5 review history; its ledgers are read only for de-duplication.
WORKSPACES = {
    "V4/001-青囊海角经": ("001", "青囊海角经"),
    "V4/002-入地眼全书": ("002", "入地眼全书"),
    "V4/003-平砂玉尺经": ("003", "平砂玉尺经·1.5"),
    "V4/003-平砂玉尺经-1.7": ("003", "平砂玉尺经·1.7"),
    "V4/004-郭璞葬经-1.8": ("004", "郭璞葬经"),
    "V4/011-青囊心印-1.10": ("011", "青囊心印"),
    "V4/036-增释地理琢玉斧峦头歌括": ("036", "琢玉斧·V4"),
    "chaoyun-pilot-zengshi-dili-zhuoyufu": ("036", "琢玉斧·试跑"),
    "chaoyun-full-zengshi-dili-zhuoyufu": ("036", "琢玉斧·整本初版"),
    "chaoyun-remake-zengshi-dili-zhuoyufu": ("036", "琢玉斧·重制"),
    "chaoyun-remake-zengshi-dili-zhuoyufu-v2": ("036", "琢玉斧·重制v2"),
}
SKIP_PARTS = {"snapshots", "archive", "_vendor"}


def rel(p):
    return str(p.relative_to(OUTPUT)).replace("\\", "/")


def read_jsonl(p):
    rows = []
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append((i, json.loads(line)))
        except json.JSONDecodeError:
            pass
    return rows


def text_of(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return "；".join(text_of(x) for x in v.values() if x)
    if isinstance(v, list):
        return "；".join(text_of(x) for x in v if x)
    return str(v)


def page_of(page_id):
    m = re.search(r"P0*(\d+)", page_id or "")
    return int(m.group(1)) if m else None


records = []


def add(ws, **kw):
    group, label = WORKSPACES[ws]
    base = {
        "book": group,
        "version": label,
        "workspace": ws,
        "record_kind": None,
        "raw_kind": None,
        "page": None,
        "block_id": None,
        "text": "",
        "reason": "",
        "before": None,
        "after": None,
        "outcome": None,
        "reader_impact": None,
        "found_at": None,
        "evidence": None,
        "ref_id": None,
    }
    base.update(kw)
    base["text"] = text_of(base["text"])[:600]
    base["reason"] = text_of(base["reason"])[:600]
    records.append(base)


# ---------------------------------------------------------------- doubts
def adjudication_outcome(adj):
    if adj is None:
        return "unadjudicated"
    status = adj.get("status", "")
    closure = adj.get("closure") or {}
    action = closure.get("action", "")
    changed = (adj.get("before") not in (None, adj.get("after"))) or (
        adj.get("modern_text_before") and adj.get("modern_text_before") != adj.get("modern_text_after")
    )
    if status == "resolved_duplicate":
        return "duplicate"
    if status in ("resolved_structural", "resolved_noncontent"):
        return "not_defect"
    if status == "open_material":
        return "unresolved"
    if status == "resolved_confirmed":
        if changed or action in ("corrected", "corrected_and_verified", "text_corrected", "replaced"):
            return "fixed"
        if action == "confirmed_unchanged" or re.search(r"保留原字|不构成|非缺|误报|无需修改|原文如此", text_of(adj.get("rationale"))):
            return "not_defect"
        return "fixed"
    return status or "unknown"


def collect_doubts(ws, d):
    audit = d / "90-audit"
    cand_path = audit / "uncertainty-candidates.jsonl"
    adj_path = audit / "uncertainty-adjudication.jsonl"
    adjs = read_jsonl(adj_path) if adj_path.exists() else []
    by_cand = defaultdict(list)
    for line, a in adjs:
        for cid in a.get("candidate_ids") or []:
            by_cand[cid].append((line, a))

    def pick(cid):
        lst = by_cand.get(cid) or []
        active = [x for x in lst if x[1].get("active") is True]
        return (active or lst or [(None, None)])[-1]

    if cand_path.exists():
        for line, c in read_jsonl(cand_path):
            cid = c.get("candidate_id")
            aline, adj = pick(cid)
            ev = f"{rel(cand_path)}:{line}"
            if aline:
                ev += f" ; {rel(adj_path)}:{aline}"
            add(
                ws,
                record_kind="doubt",
                raw_kind=c.get("kind") or c.get("stage"),
                page=page_of(c.get("page_id")),
                block_id=c.get("block_id"),
                text=c.get("excerpt") or c.get("candidate_text"),
                reason=[c.get("reason"), (adj or {}).get("rationale"), (adj or {}).get("decision")],
                before=(adj or {}).get("before") or (adj or {}).get("modern_text_before"),
                after=(adj or {}).get("after") or (adj or {}).get("modern_text_after"),
                outcome=adjudication_outcome(adj),
                reader_impact=(adj or {}).get("reader_impact") or c.get("severity"),
                found_at=c.get("checkpoint") or c.get("origin_stage") or c.get("stage"),
                evidence=ev,
                ref_id=cid,
            )
        # adjudications not tied to any candidate (e.g. reader-level issues)
        cand_ids = {c.get("candidate_id") for _, c in read_jsonl(cand_path)}
        for line, a in adjs:
            if not set(a.get("candidate_ids") or []) & cand_ids:
                add(
                    ws,
                    record_kind="doubt",
                    raw_kind="adjudication_only",
                    page=page_of(a.get("page_id")),
                    block_id=a.get("block_id"),
                    text=a.get("decision") or a.get("rationale"),
                    reason=a.get("rationale"),
                    before=a.get("before") or a.get("modern_text_before"),
                    after=a.get("after") or a.get("modern_text_after"),
                    outcome=adjudication_outcome(a),
                    reader_impact=a.get("reader_impact"),
                    found_at=a.get("checkpoint"),
                    evidence=f"{rel(adj_path)}:{line}",
                    ref_id=a.get("adjudication_id"),
                )
        return

    # workspaces without candidate ledgers
    if adjs:  # remake-v2: adjudication wraps the original item
        for line, a in adjs:
            orig = a.get("original") or {}
            note = orig.get("note")
            add(
                ws,
                record_kind="doubt",
                raw_kind="ledger_item",
                page=page_of(orig.get("page_id")),
                block_id=orig.get("block_id"),
                text=note.get("excerpt") if isinstance(note, dict) else note,
                reason=[note.get("reason") if isinstance(note, dict) else None, a.get("rationale")],
                outcome=adjudication_outcome(a),
                reader_impact=orig.get("severity"),
                found_at="ledger",
                evidence=f"{rel(adj_path)}:{line}",
                ref_id=a.get("adjudication_id"),
            )
        return

    items = audit / "uncertain-items.jsonl"
    if not items.exists():
        return
    for line, it in read_jsonl(items):
        note = it.get("note")
        status = it.get("status")
        if "judge_verdict" in it and "modern_text" in it:  # chaoyun-full model-judge records
            verdict = it.get("model_judge_verdict") or it.get("judge_verdict")
            issues = (it.get("judge_issues") or []) + (it.get("local_issues") or []) + (it.get("issues") or [])
            add(
                ws,
                record_kind="doubt",
                raw_kind=f"judge_{verdict}",
                block_id=it.get("id"),
                text=it.get("uncertainty") or it.get("source"),
                reason=issues or it.get("uncertainty"),
                after=it.get("modern_text"),
                outcome="unresolved" if verdict != "accept" or it.get("uncertainty") else "not_defect",
                reader_impact="high" if verdict == "uncertain" else "medium",
                found_at="model_judge",
                evidence=f"{rel(items)}:{line}",
                ref_id=it.get("id"),
            )
            continue
        if "uncertainty" in it:  # 002
            add(
                ws,
                record_kind="doubt",
                raw_kind=f"{it.get('stage')}_{it.get('judge_verdict')}",
                page=it.get("source_page") or page_of(it.get("page_id")),
                block_id=it.get("block_id"),
                text=it.get("uncertainty"),
                reason=it.get("issues"),
                before=it.get("source"),
                after=it.get("edited_candidate") or it.get("candidate"),
                outcome="unresolved",
                reader_impact=it.get("judge_confidence"),
                found_at=it.get("stage"),
                evidence=f"{rel(items)}:{line}",
                ref_id=it.get("item_id"),
            )
            continue
        add(
            ws,
            record_kind="doubt",
            raw_kind="ledger_item",
            page=page_of(it.get("page_id")) or (it.get("page_ids") or [None])[0] and page_of(it["page_ids"][0]),
            block_id=it.get("block_id"),
            text=note.get("excerpt") if isinstance(note, dict) else (note or it.get("issue")),
            reason=note.get("reason") if isinstance(note, dict) else None,
            outcome="not_defect" if status and status.startswith("resolved_non") else "unresolved",
            reader_impact=it.get("severity") or it.get("reader_impact"),
            found_at="ledger",
            evidence=f"{rel(items)}:{line}",
            ref_id=it.get("issue_id") or it.get("block_id"),
        )


# ---------------------------------------------------------------- corrections
def collect_events(ws, d):
    p = d / "90-audit" / "events.jsonl"
    if not p.exists():
        return
    for line, e in read_jsonl(p):
        ev = e.get("event")
        if ev == "source_correction_reapplied":
            add(
                ws,
                record_kind="correction",
                raw_kind="source_correction",
                page=e.get("source_page"),
                block_id=f"page{e.get('source_page')}-idx{e.get('block_index')}",
                text=e.get("reason"),
                reason=e.get("reason"),
                before=e.get("before"),
                after=e.get("after"),
                outcome="fixed",
                found_at="source",
                evidence=f"{rel(p)}:{line}",
                ref_id=f"{e.get('source_page')}-{e.get('block_index')}-{e.get('candidate_id')}",
            )
        elif ev == "cross_page_carryover_removed":
            add(
                ws,
                record_kind="correction",
                raw_kind="cross_page_duplicate",
                page=e.get("source_page"),
                block_id=e.get("block_id"),
                text=f"跨页重复：上一页尾部与下一页开头重复 {e.get('removed_characters')} 字，已删除重复部分",
                reason=e.get("rationale"),
                before=(e.get("matched_prefix") or "")[:120],
                outcome="fixed",
                found_at="source",
                evidence=f"{rel(p)}:{line}",
                ref_id=e.get("block_id"),
            )


def collect_011_source_reading(ws, d):
    sr = d / "90-audit" / "source-reading"
    if not sr.exists():
        return
    for p in sorted(sr.glob("corrections-*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for i, row in enumerate(data.get("text_changes") or []):
            page, block_no, before, after, issue = (list(row) + [None] * 5)[:5]
            add(
                ws,
                record_kind="correction",
                raw_kind="source_correction",
                page=page,
                block_id=f"P{page:06d}-B{block_no:03d}" if isinstance(page, int) and isinstance(block_no, int) else None,
                text=f"{before} → {after}",
                before=before,
                after=after,
                outcome="fixed",
                found_at="independent_source_review",
                evidence=f"{rel(p)}#text_changes[{i}]",
                ref_id=issue,
            )
        for i, ch in enumerate(data.get("changes") or []):
            if ch.get("text_unchanged"):
                add(
                    ws,
                    record_kind="correction",
                    raw_kind="coordinate_repair",
                    page=page_of(ch.get("block_id")),
                    block_id=ch.get("block_id"),
                    text="版面坐标截短或错位，文字未变，修正坐标",
                    before=json.dumps(ch.get("before"), ensure_ascii=False),
                    after=json.dumps(ch.get("after"), ensure_ascii=False),
                    outcome="fixed",
                    found_at="correction_replay",
                    evidence=f"{rel(p)}#changes[{i}]",
                    ref_id=ch.get("candidate_id"),
                )
                continue
            add(
                ws,
                record_kind="correction",
                raw_kind="source_correction",
                page=page_of(ch.get("block_id")),
                block_id=ch.get("block_id"),
                text=ch.get("reason") or f"{ch.get('before')} → {ch.get('after')}",
                reason=ch.get("reason"),
                before=ch.get("before"),
                after=ch.get("after"),
                outcome="fixed",
                found_at="independent_source_review",
                evidence=f"{rel(p)}#changes[{i}]",
                ref_id=ch.get("issue_id"),
            )


def collect_004_page_reviews(ws, d):
    folder = d / "90-audit" / "source-page-reviews-v19b"
    if not folder.exists():
        return
    for p in sorted(folder.glob("P*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for i, b in enumerate(data.get("blocks") or []):
            if str(b.get("promotion_status", "")).startswith("rejected"):
                add(
                    ws,
                    record_kind="correction",
                    raw_kind="ocr_pseudo_block",
                    page=page_of(data.get("page_id")),
                    block_id=b.get("candidate_id"),
                    text=b.get("evidence") or "OCR 伪块被拒绝",
                    reason=b.get("rejection_reason") or b.get("evidence"),
                    outcome="fixed",
                    found_at="source_page_review",
                    evidence=f"{rel(p)}#blocks[{i}]",
                    ref_id=b.get("candidate_id"),
                )


PROGRESS_DEFECT = re.compile(r"纠正|纠正|误|错|漏|伪块|重复|废止|撤销|截短|错位|拼接|退回|混入|缺陷")


def collect_progress_log(ws, d):
    p = d / "90-audit" / "当前工作进度.md"
    if not p.exists():
        return
    for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("- 2026-") and PROGRESS_DEFECT.search(line):
            add(
                ws,
                record_kind="progress_log",
                raw_kind="progress_entry",
                page=None,
                text=line[2:],
                reason=line[2:],
                outcome="fixed",
                found_at="source_page_review",
                evidence=f"{rel(p)}:{line_no}",
                ref_id=f"log-{line_no}",
            )


# ---------------------------------------------------------------- reader reviews
def collect_reader_reviews(ws, d):
    edited = d / "50-edited"
    if not edited.exists():
        return
    files = [edited / "reader-review.json"] + sorted((edited / "review-history").glob("*/reader-review.json"))
    for p in files:
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for dim, v in (data.get("dimensions") or {}).items():
            if v.get("verdict") == "passed":
                continue
            for j, f in enumerate(v.get("findings") or []):
                add(
                    ws,
                    record_kind="review_finding",
                    raw_kind=f"reader_{dim}",
                    text=f.get("problem"),
                    reason=f.get("problem"),
                    outcome="fixed_or_superseded",
                    reader_impact="medium",
                    found_at=f"reader_review:{data.get('cycle_id')}",
                    evidence=f"{rel(p)}#dimensions.{dim}.findings[{j}]",
                    ref_id=f.get("revision_id"),
                )
    for p in [edited / "reader-revision-ledger.jsonl"] + sorted((edited / "review-history").glob("*/reader-revision-ledger.jsonl")):
        if not p.exists():
            continue
        for line, r in read_jsonl(p):
            add(
                ws,
                record_kind="review_finding",
                raw_kind=f"revision_{r.get('operation')}",
                block_id=",".join(r.get("block_ids") or []) or None,
                text=r.get("reader_problem"),
                reason=r.get("rationale"),
                before=(r.get("before") or "")[:300],
                after=(r.get("after") or "")[:300],
                outcome="fixed" if r.get("status") == "applied" else r.get("status"),
                reader_impact=r.get("semantic_risk"),
                found_at=f"reader_review:{r.get('cycle_id')}",
                evidence=f"{rel(p)}:{line}",
                ref_id=r.get("revision_id"),
            )


# ---------------------------------------------------------------- reader text scan
SCAN_PATTERNS = {
    "释读缺口": re.compile(r"具体所指不详|所指不详|语义不明|意思不明|无法确定其含义|无法释读|含义不详"),
    "流程用语混入": re.compile(r"台账|裁决|门禁|硬校验|区块|\bblock\b|UC0\d|UA0\d|P0000\d|疑点编号|过程稿|核义模型|自动修复|候选转录|candidate|OCR|识别误差"),
    "AI腔套话": re.compile(r"值得注意的是|需要指出的是|总的来说|综上所述|不难看出|换句话说|简而言之|简单来说|由此可见"),
    "版心混入": re.compile(r"[^#\s].{8,}(經|经)(\s*[上下]\s*卷之?|\s+卷之?)\s*[一二三四五六七八九十廿]+"),
}


def final_reader_md(d):
    for cand in ("60-publication/modern-reading.md", "50-edited/modern-reading.md"):
        p = d / cand
        if p.exists():
            return p
    hits = sorted(d.glob("60-publication/*.md"))
    return hits[0] if hits else None


def collect_text_scan(ws, d):
    p = final_reader_md(d)
    if not p:
        return
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("<!--") or s.startswith("!["):
            continue
        for name, pat in SCAN_PATTERNS.items():
            m = pat.search(s)
            if m:
                add(
                    ws,
                    record_kind="text_scan",
                    raw_kind=name,
                    text=s[:300],
                    reason=f"命中：{m.group(0)}",
                    outcome="in_final_text",
                    found_at="defect_library_scan",
                    evidence=f"{rel(p)}:{no}",
                    ref_id=f"scan-{no}-{name}",
                )


# ---------------------------------------------------------------- process-quality metrics
def collect_template_metrics(ws, d, metrics):
    p = d / "90-audit" / "fidelity-review.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        blocks = data.get("blocks") or []
        checks = [json.dumps(b.get("checks"), ensure_ascii=False, sort_keys=True) for b in blocks]
        evid = [b.get("evidence") for b in blocks]
        metrics.setdefault(ws, {})["fidelity_review"] = {
            "blocks": len(blocks),
            "passed": sum(1 for b in blocks if b.get("status") == "passed"),
            "distinct_checks_text": len(set(checks)),
            "distinct_evidence_text": len(set(evid)),
            "file": rel(p),
        }
    p = d / "90-audit" / "pdf-reader-review.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        pages = data.get("pages") or []
        norm = [re.sub(r"\d+", "N", json.dumps(x, ensure_ascii=False, sort_keys=True)) for x in pages]
        metrics.setdefault(ws, {})["pdf_reader_review"] = {
            "pages": len(pages),
            "distinct_after_removing_page_numbers": len(set(norm)),
            "status": data.get("status"),
            "file": rel(p),
        }
    for name in ("uncertainty-adjudication.jsonl",):
        p = d / "90-audit" / name
        if p.exists():
            rows = [r for _, r in read_jsonl(p)]
            rats = [text_of(r.get("rationale")) for r in rows]
            from collections import Counter

            top = Counter(rats).most_common(3)
            metrics.setdefault(ws, {})["adjudication_rationale"] = {
                "rows": len(rows),
                "distinct_rationale": len(set(rats)),
                "top": [{"text": t[:80], "count": c} for t, c in top],
                "file": rel(p),
            }
    p = d / "90-audit" / "uncertainty-candidates.jsonl"
    if p.exists():
        from collections import Counter

        reasons = Counter(text_of(r.get("reason")) for _, r in read_jsonl(p))
        metrics.setdefault(ws, {})["candidate_reason"] = {
            "rows": sum(reasons.values()),
            "distinct_reason": len(reasons),
            "top": [{"text": t[:80], "count": c} for t, c in reasons.most_common(3)],
        }


# ---------------------------------------------------------------- manual rework records
def collect_manual():
    p = LIB / "tools" / "rework_manual.json"
    for i, r in enumerate(json.loads(p.read_text(encoding="utf-8"))):
        ws = r["workspace"]
        add(
            ws,
            record_kind="rework",
            raw_kind=r.get("raw_kind", "rework"),
            page=r.get("page"),
            text=r["description"],
            reason=r.get("reason", ""),
            outcome=r.get("outcome", "fixed"),
            reader_impact=r.get("reader_impact", "high"),
            found_at=r.get("found_at"),
            evidence=r["evidence"],
            ref_id=f"RW{i + 1:03d}",
            manual=r,
        )


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    metrics = {}
    for ws in WORKSPACES:
        d = OUTPUT / ws
        if not d.exists():
            print("missing", ws)
            continue
        collect_doubts(ws, d)
        collect_events(ws, d)
        collect_011_source_reading(ws, d)
        collect_004_page_reviews(ws, d)
        collect_progress_log(ws, d)
        collect_reader_reviews(ws, d)
        collect_text_scan(ws, d)
        collect_template_metrics(ws, d, metrics)
    collect_manual()
    with (WORK / "raw.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (WORK / "process-metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter

    c = Counter((r["version"], r["record_kind"]) for r in records)
    for k, v in sorted(c.items()):
        print(k, v)
    print("total", len(records))


if __name__ == "__main__":
    main()
