from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import fitz
import numpy as np


ROOT = Path(r"D:\壮五福\风水项目\output\chaoyun-remake-zengshi-dili-zhuoyufu")
PDF = ROOT / "60-publication" / "增释地理琢玉斧峦头歌括·现代白话版.pdf"
MD = ROOT / "60-publication" / "modern-reading.md"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "").replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')


source = load_jsonl(ROOT / "20-source" / "blocks.jsonl")
normalized = load_jsonl(ROOT / "30-normalized" / "blocks.jsonl")
modern = load_jsonl(ROOT / "40-modernized" / "blocks.jsonl")
edited = load_jsonl(ROOT / "50-edited" / "blocks.jsonl")
md_text = MD.read_text(encoding="utf-8")
md_compact = compact(md_text)

record_rows = []
for s, n, m, e in zip(source, normalized, modern, edited):
    sl = len(compact(s.get("source_text", "")))
    ml = len(compact(m.get("modern_text", "")))
    record_rows.append(
        {
            "page": s["source_page"],
            "source_chars": sl,
            "modern_chars": ml,
            "ratio": round(ml / sl, 2) if sl else None,
            "normalized_unchanged": compact(s.get("source_text", "")) == compact(n.get("normalized_text", "")),
            "modern_equals_edited": m.get("modern_text") == e.get("modern_text"),
            "summary_voice": bool(re.match(r"^(本页|本图|这一页)", m.get("modern_text", ""))),
            "present_in_md": compact(m.get("modern_text", "")) in md_compact,
        }
    )

doc = fitz.open(PDF)
pdf_rows = []
leading_punctuation = []
for index, page in enumerate(doc, 1):
    text = page.get_text("text")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if re.match(r"^[，。；：！？、）》】〕,.;:!?]", line):
            leading_punctuation.append({"page": index, "line": line[:30]})
    pix = page.get_pixmap(matrix=fitz.Matrix(0.8, 0.8), colorspace=fitz.csGRAY, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    ink = arr < 242
    ink_fraction = float(ink.mean())
    ys, xs = np.where(ink)
    if len(xs):
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        content_bottom = bbox[3] / pix.height
        content_top = bbox[1] / pix.height
    else:
        bbox = None
        content_bottom = 0.0
        content_top = 1.0
    pdf_rows.append(
        {
            "page": index,
            "text_chars": len(compact(text)),
            "ink_fraction": round(ink_fraction, 4),
            "content_top": round(content_top, 3),
            "content_bottom": round(content_bottom, 3),
            "bbox": bbox,
        }
    )

uncertainties = load_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl")
uncertainty_pages = Counter(row.get("page_id") for row in uncertainties)
report = json.loads((ROOT / "90-audit" / "quality-report.json").read_text(encoding="utf-8"))
publication_pdfs = sorted(p.name for p in (ROOT / "60-publication").glob("*.pdf"))

result = {
    "records": {
        "count": len(record_rows),
        "low_ratio_under_0_5": [r for r in record_rows if r["ratio"] is not None and r["ratio"] < 0.5],
        "high_ratio_over_2": [r for r in record_rows if r["ratio"] is not None and r["ratio"] > 2],
        "normalized_unchanged_pages": [r["page"] for r in record_rows if r["normalized_unchanged"]],
        "modern_equals_edited_count": sum(r["modern_equals_edited"] for r in record_rows),
        "summary_voice_pages": [r["page"] for r in record_rows if r["summary_voice"]],
        "not_present_verbatim_in_md": [r["page"] for r in record_rows if not r["present_in_md"]],
    },
    "pdf": {
        "pages": len(doc),
        "sparse_pages_under_120_chars": [r for r in pdf_rows if r["page"] > 4 and r["text_chars"] < 120],
        "top_heavy_pages": [r for r in pdf_rows if r["page"] > 4 and r["content_bottom"] < 0.55],
        "leading_punctuation": leading_punctuation,
    },
    "audit": {
        "open_uncertainties": len(uncertainties),
        "pages_with_uncertainties": len(uncertainty_pages),
        "max_uncertainties": uncertainty_pages.most_common(10),
        "events_log_bytes": (ROOT / "90-audit" / "events.jsonl").stat().st_size,
        "reported_visual_defects": report.get("publication", {}).get("visual_defects_found"),
        "publication_root_pdfs": publication_pdfs,
    },
}

print(json.dumps(result, ensure_ascii=False, indent=2))
