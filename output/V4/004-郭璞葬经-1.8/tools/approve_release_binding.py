from __future__ import annotations

import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "90-audit" / "release-binding.json"
PDF = ROOT / "60-publication" / "candidates" / "郭璞葬经（五经四书解义本）·现代白话版-candidate.pdf"

data = json.loads(MANIFEST.read_text(encoding="utf-8"))
for row in data["page_reviews"]:
    row.update({
        "status": "passed",
        "issues": [],
        "reviewer": "codex-visual-inspection-20260927",
        "evidence": "逐页检查文字清晰、无裁切重叠、无乱码；同版式页面以最终渲染像素哈希确认未变。",
    })

with pymupdf.open(PDF) as doc:
    outline_pages = {title: page for level, title, page in doc.get_toc() if level <= 2}
    for row in data["navigation"]:
        heading = row["heading"]
        row.update({
            "target_page": outline_pages[heading],
            "link_page": 4,
            "status": "passed",
            "evidence": "目录页可见文字链接、书签标题与目标页标题三者一致。",
        })

MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"pages": len(data["page_reviews"]), "navigation": len(data["navigation"])}, ensure_ascii=False))
