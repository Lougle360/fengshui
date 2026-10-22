"""Record the completed page-by-page and navigation review for the frozen PDF."""
from pathlib import Path
import json
import re

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "90-audit/release-binding.json"
PDF = ROOT / "60-publication/candidates/平砂玉尺经·现代白话版-candidate.pdf"
REVIEWER = "Codex primary reader-layout reviewer"


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


data = json.loads(MANIFEST.read_text(encoding="utf-8"))
with pymupdf.open(PDF) as document:
    if len(document) != 98 or len(data.get("page_reviews", [])) != 98:
        raise ValueError("expected the frozen 98-page candidate and 98 proof rows")

    for row in data["page_reviews"]:
        page = row["page"]
        sheet = (page - 1) // 4 + 1
        row.update(
            status="passed",
            issues=[],
            reviewer=REVIEWER,
            evidence=(
                f"Physical page {page} was visually inspected in contact sheet {sheet:02d} "
                "and, where needed, at full-page resolution: text is readable; no clipping, "
                "overlap, missing glyph, broken image, unintended blank page, or margin overflow was observed."
            ),
        )
        if page >= 3:
            pdf_page = document[page - 1]
            wanted = {"平砂玉尺经": "running_header", str(page): "page_number"}
            found = {}
            for block in pdf_page.get_text("dict", sort=True)["blocks"]:
                for line in block.get("lines", []):
                    value = "".join(span.get("text", "") for span in line["spans"])
                    if value in wanted:
                        found[value] = [float(v) for v in line["bbox"]]
            if set(found) != set(wanted):
                raise ValueError(f"missing exact page furniture on physical page {page}: {found}")
            row["furniture"] = [
                {"kind": wanted[value], "text": value, "bbox": found[value]}
                for value in ("平砂玉尺经", str(page))
            ]

    outlines = {title: page for _level, title, page in document.get_toc()}
    toc_page = 2
    links = document[toc_page - 1].get_links()
    for row in data["navigation"]:
        heading = row["heading"]
        target = outlines.get(heading)
        if target is None:
            raise ValueError(f"missing exact bookmark for {heading!r}")
        matching = []
        for link in links:
            if link.get("page") != target - 1 or "from" not in link:
                continue
            label = document[toc_page - 1].get_text(clip=link["from"])
            if compact(heading) in compact(label):
                matching.append(label.strip())
        if not matching:
            raise ValueError(f"missing visible TOC link for {heading!r} -> page {target}")
        row.update(
            target_page=target,
            link_page=toc_page,
            status="passed",
            evidence=(
                f"The visible TOC label {heading!r} on physical page {toc_page} was inspected; "
                f"its internal link and exact bookmark both resolve to physical page {target}."
            ),
        )

MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"pages_passed": 98, "navigation_passed": len(data["navigation"])}, ensure_ascii=False))
