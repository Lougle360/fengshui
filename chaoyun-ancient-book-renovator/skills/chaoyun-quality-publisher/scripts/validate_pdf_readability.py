#!/usr/bin/env python3
"""Reject mechanically intact PDFs that still fail ordinary-reader layout."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path


PAGE_ROLES = {"cover", "credits", "frontmatter", "toc", "body", "glossary", "backmatter"}
PAGE_CHECKS = {"legibility", "density", "whitespace", "hierarchy", "continuity"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def validate(root: Path, pdf: Path) -> list[str]:
    errors: list[str] = []
    try:
        import pymupdf

        binding = json.loads((root / "90-audit/release-binding.json").read_text(encoding="utf-8"))
        markdown = (root / "60-publication/modern-reading.md").read_text(encoding="utf-8")
        document = pymupdf.open(pdf)
    except (OSError, ValueError, json.JSONDecodeError, ImportError) as exc:
        return [f"cannot validate PDF reader quality: {exc}"]

    if binding.get("schema_version") != "1.1":
        errors.append("workflow 1.9 PDF proof requires release-binding schema 1.1")
    page_reviews = binding.get("page_reviews") if isinstance(binding.get("page_reviews"), list) else []
    if len(page_reviews) != len(document):
        errors.append("PDF reader proof must describe every physical page")
        return errors

    evidence = []
    body_counts: list[tuple[int, int, dict]] = []
    for review in page_reviews:
        page_number = review.get("page")
        if not isinstance(page_number, int) or not 1 <= page_number <= len(document):
            continue
        role = review.get("role")
        if role not in PAGE_ROLES:
            errors.append(f"proof page {page_number} requires a valid reader-facing role")
        checks = review.get("checks") if isinstance(review.get("checks"), dict) else {}
        missing = PAGE_CHECKS - checks.keys()
        if missing:
            errors.append(f"proof page {page_number} lacks reader checks: {sorted(missing)}")
        for key in PAGE_CHECKS & checks.keys():
            if not isinstance(checks[key], str) or len(compact(checks[key])) < 8:
                errors.append(f"proof page {page_number} has non-substantive {key} evidence")
        value = str(review.get("evidence") or "").strip()
        if value:
            evidence.append(value)
        page = document[page_number - 1]
        count = len(compact(page.get_text()))
        if role in {"body", "glossary"}:
            body_counts.append((page_number, count, review))
        if role in {"body", "glossary", "backmatter"}:
            furniture = review.get("furniture") if isinstance(review.get("furniture"), list) else []
            if not any(item.get("kind") == "page_number" for item in furniture if isinstance(item, dict)):
                errors.append(f"reader page {page_number} has no reviewed visible page number")

    if evidence:
        repeated = Counter(evidence).most_common(1)[0][1]
        if repeated > max(2, len(page_reviews) // 3):
            errors.append("page review repeats generic evidence across too many pages")

    counts = [count for _, count, _ in body_counts if count]
    if counts:
        median = statistics.median(counts)
        for page_number, count, review in body_counts:
            outlier = count < median * 0.45 or count > median * 1.8
            if outlier and len(compact(str(review.get("density_exception") or ""))) < 10:
                errors.append(f"reader page {page_number} has extreme text density without a reviewed reason")

    toc_reviews = [row for row in page_reviews if row.get("role") == "toc"]
    if len(document) > 5 and len(toc_reviews) != 1:
        errors.append("reader PDF requires exactly one declared TOC page")
    navigation = binding.get("navigation") if isinstance(binding.get("navigation"), list) else []
    for row in navigation:
        if not str(row.get("visible_page_label") or "").strip():
            errors.append(f"TOC entry lacks a visible page label: {row.get('heading')}")

    unordered_items = [
        re.sub(r"^\s*[-*+]\s+", "", line).strip()
        for line in markdown.splitlines()
        if re.match(r"^\s*[-*+]\s+\S", line)
    ]
    if unordered_items:
        pdf_text = "\n".join(page.get_text(sort=True) for page in document)
        visible_bullets = sum(1 for line in pdf_text.splitlines() if re.match(r"\s*[•·▪◦\-–]\s*\S", line))
        if visible_bullets < len(unordered_items):
            errors.append("unordered-list hierarchy was lost during PDF rendering")

    aids_path = root / "50-edited/reader-aids.json"
    if aids_path.is_file():
        try:
            aids = json.loads(aids_path.read_text(encoding="utf-8"))
            entries = ((aids.get("glossary") or {}).get("entries") or [])
            core_terms = [row.get("term") for row in entries if row.get("tier") == "core" and row.get("term")]
            bold_terms = set()
            for page in document:
                for block in page.get_text("dict", sort=True).get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if "bold" in str(span.get("font") or "").lower():
                                bold_terms.add(str(span.get("text") or "").strip("：: "))
            missing = [term for term in core_terms if term not in bold_terms]
            if missing:
                errors.append(f"core glossary terms lost visual emphasis: {missing[:10]}")
        except (OSError, ValueError, json.JSONDecodeError):
            errors.append("cannot validate glossary typography")

    session_path = root / "90-audit/pdf-reader-review.json"
    if not session_path.is_file():
        errors.append("workflow 1.9 requires a sequential 90-audit/pdf-reader-review.json")
    else:
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
            if session.get("pdf_sha256") != sha256(pdf):
                errors.append("PDF reader review is stale")
            if session.get("status") != "passed" or session.get("blocking_issues") != []:
                errors.append("PDF reader review has not passed")
            pages = session.get("pages") if isinstance(session.get("pages"), list) else []
            if [row.get("page") for row in pages] != list(range(1, len(document) + 1)):
                errors.append("PDF reader review does not cover every page in order")
            for row in pages:
                if any(len(compact(str(row.get(key) or ""))) < 6 for key in ("readability", "continuity", "reader_action")):
                    errors.append(f"PDF reader review page {row.get('page')} lacks substantive sequential evidence")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid PDF reader review: {exc}")
    return errors
