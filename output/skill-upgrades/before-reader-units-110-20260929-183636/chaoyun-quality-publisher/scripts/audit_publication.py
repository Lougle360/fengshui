#!/usr/bin/env python3
"""Audit a declared reader-facing publication and its local Markdown assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_release_binding import validate as validate_release_binding
from validate_pdf_readability import validate as validate_pdf_readability

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'chaoyun-ancient-book-renovator' / 'scripts'))
from validate_production_plan import validate as validate_production_plan
from validate_integrity import validate as validate_integrity


IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
RAW_MARKUP = re.compile(r"</?(?:table|tbody|thead|tr|td|th)(?:\s[^>]*)?>", re.I)
INTERNAL_MESSAGES = (
    "本地硬校验仍未通过",
    "自动修复后核义模型仍建议修订",
    "已记录供后续自动处理",
    "judge_verdict",
    "candidate_modern_text",
    "repair_queue",
    "locked_terms",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--candidate-pdf", type=Path)
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    report = root / "90-audit/quality-report.json"
    report_data: dict = {}
    if report.is_file():
        try:
            report_data = json.loads(report.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid quality-report.json: {exc}")

    book_file = root / "book.json"
    book_data: dict = {}
    if book_file.is_file():
        try:
            book_data = json.loads(book_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid book.json: {exc}")

    target_reader = str(book_data.get("target_reader") or "")
    edition_label = str(book_data.get("edition_label") or "")
    ordinary_reader = book_data.get("delivery_mode") not in {"source_comparison", "evidence_archive"}
    if book_data.get("delivery_mode") not in {"ordinary_reader", "source_comparison", "evidence_archive"}:
        errors.append("book.json requires explicit delivery_mode")
    editorial_path = root / "50-edited/editorial-report.json"
    editorial_data: dict = {}
    acceptance_data: dict = {}
    reader_counts: dict[str, int] = {}
    revision_counts: dict[str, int] = {}
    if ordinary_reader:
        errors.extend(validate_production_plan(root))
        uncertainty_gate = Path(__file__).resolve().parents[2] / 'chaoyun-uncertainty-adjudicator/scripts/project_open_items.py'
        checked = subprocess.run([sys.executable, '-X', 'utf8', str(uncertainty_gate), str(root), '--check', '--publication'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if checked.returncode:
            errors.append('uncertainty publication gate failed: ' + checked.stdout + checked.stderr)
        if not editorial_path.is_file():
            errors.append("ordinary-reader edition requires 50-edited/editorial-report.json")
        else:
            try:
                editorial_data = json.loads(editorial_path.read_text(encoding="utf-8"))
                if not isinstance(editorial_data, dict):
                    errors.append("editorial-report.json must contain an object")
                    editorial_data = {}
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"invalid editorial-report.json: {exc}")
        reader_validator = Path(__file__).resolve().parents[2] / "chaoyun-reading-editor" / "scripts" / "validate_reader_value.py"
        if not reader_validator.is_file():
            errors.append("missing chaoyun-reading-editor reader-value validator")
        else:
            spec = importlib.util.spec_from_file_location("chaoyun_reader_value_audit", reader_validator)
            if spec is None or spec.loader is None:
                errors.append("could not load reader-value validator")
            else:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                reader_errors, reader_counts = module.validate(root, "60-publication/modern-reading.md")
                errors.extend(reader_errors)
        revision_validator = Path(__file__).resolve().parents[2] / "chaoyun-reader-experience-reviser" / "scripts" / "validate_reader_revision.py"
        if not revision_validator.is_file():
            errors.append("missing chaoyun-reader-experience-reviser validator")
        else:
            revision_spec = importlib.util.spec_from_file_location("chaoyun_reader_revision_audit", revision_validator)
            if revision_spec is None or revision_spec.loader is None:
                errors.append("could not load reader-revision validator")
            else:
                revision_module = importlib.util.module_from_spec(revision_spec)
                revision_spec.loader.exec_module(revision_module)
                revision_errors, revision_counts = revision_module.validate(root)
                errors.extend(revision_errors)
        acceptance_path = root / "50-edited/reader-acceptance-report.json"
        if acceptance_path.is_file():
            try:
                acceptance_data = json.loads(acceptance_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"invalid reader-acceptance-report.json: {exc}")

    publication = report_data.get("publication")
    publication = publication if isinstance(publication, dict) else {}
    book_declared_pdf = book_data.get("release_filename")
    report_declared_pdf = publication.get("pdf")
    if book_declared_pdf and report_declared_pdf and str(book_declared_pdf).replace("\\", "/") != str(report_declared_pdf).replace("\\", "/"):
        errors.append(
            "quality report PDF differs from book.json.release_filename; "
            f"got {report_declared_pdf!r}/{book_declared_pdf!r}"
        )
    declared_pdf = book_declared_pdf or report_declared_pdf
    if declared_pdf:
        pdf = (root / str(declared_pdf)).resolve()
    else:
        pdf = (root / "60-publication/modern-reading.pdf").resolve()
        warnings.append("official PDF is not declared; using 60-publication/modern-reading.pdf")
    try:
        pdf.relative_to(root)
    except ValueError:
        errors.append(f"declared official PDF escapes workspace: {declared_pdf!r}")
        pdf = root / "60-publication/modern-reading.pdf"
    if args.candidate_pdf:
        pdf = args.candidate_pdf.resolve()
        if not pdf.is_relative_to(root):
            errors.append("candidate PDF escapes workspace")

    required = [
        root / "60-publication/modern-reading.md",
        pdf,
        report,
        root / "90-audit/quality-report.md",
    ]
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty: {path.relative_to(root)}")

    markdown = required[0]
    if markdown.is_file():
        text = markdown.read_text(encoding="utf-8")
        raw_tags = RAW_MARKUP.findall(text)
        if raw_tags:
            errors.append(f"literal table markup remains in modern-reading.md: {len(raw_tags)} tags")
        for message in INTERNAL_MESSAGES:
            count = text.count(message)
            if count:
                errors.append(f"internal pipeline message leaked into reader text: {message!r} ({count})")
        for target in IMAGE.findall(text):
            raw = target.strip()
            clean = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw.split(maxsplit=1)[0]
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", clean):
                errors.append(f"remote image reference: {clean}")
                continue
            candidate = (markdown.parent / clean).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(f"image escapes workspace: {clean}")
                continue
            if not candidate.is_file():
                errors.append(f"missing image: {clean}")

    if pdf.is_file() and not pdf.read_bytes()[:5] == b"%PDF-":
        errors.append(f"official PDF does not have a PDF header: {pdf.relative_to(root)}")
    if ordinary_reader:
        errors.extend(validate_integrity(root))
        errors.extend(validate_release_binding(root, pdf))
        if str(book_data.get("workflow_schema_version") or "") == "1.9" and pdf.is_file():
            errors.extend(validate_pdf_readability(root, pdf))
        alias = root / "60-publication/modern-reading.pdf"
        if not args.candidate_pdf and alias.is_file() and pdf.is_file() and alias.read_bytes() != pdf.read_bytes():
            errors.append("internal PDF alias differs from the official release")

    allowed_pdfs = {pdf.resolve(), (root / str(declared_pdf or '60-publication/modern-reading.pdf')).resolve(), (root / "60-publication/modern-reading.pdf").resolve(),
                    (root / "60-publication/source-comparison.pdf").resolve()}
    extra_pdfs = [path for path in (root / "60-publication").glob("*.pdf") if path.resolve() not in allowed_pdfs]
    if extra_pdfs:
        errors.append("ambiguous extra PDFs in publication root: " + ", ".join(path.name for path in extra_pdfs))

    data = report_data
    if report.is_file() and data:
        if data.get("grade") not in {"A", "B", "C", "D"}:
            errors.append("quality-report.json requires grade A, B, C, or D")
        if "semantic_audit" not in data or "structural_audit" not in data:
            errors.append("quality-report.json requires semantic_audit and structural_audit")
        for key in ("semantic_audit", "structural_audit"):
            audit = data.get(key)
            if audit is not None and not isinstance(audit, dict):
                errors.append(f"quality-report.json {key} must be an object")
            if data.get("grade") in {"A", "B"} and (not isinstance(audit, dict) or audit.get("passed") is not True):
                errors.append(f"grade A/B requires a passing {key}")

        source_pages = data.get("source_pages_total") or data.get("source_pages") or data.get("pages")
        semantic = data.get("semantic_audit")
        vision = data.get("vision_reconstruction")
        successful = semantic.get("page_level_visual_coverage") if isinstance(semantic, dict) else None
        if successful is None and isinstance(vision, dict):
            successful = vision.get("successful_pages")
        if data.get("grade") in {"A", "B"} and isinstance(source_pages, int):
            if successful != source_pages:
                errors.append(
                    "grade A/B scan publication requires complete page-level visual coverage; "
                    f"got {successful!r}/{source_pages}"
                )

        book_source_pages = book_data.get("source_pdf_pages")
        if isinstance(book_source_pages, int) and isinstance(source_pages, int):
            if book_source_pages != source_pages:
                errors.append(
                    "source-page accounting differs between book.json and quality report; "
                    f"got {book_source_pages}/{source_pages}"
                )

        uncertainty_summary = data.get("uncertainty_summary")
        if not isinstance(uncertainty_summary, dict):
            errors.append("quality-report.json requires uncertainty_summary")
        open_ledger = root / "90-audit/uncertain-items.jsonl"
        if not open_ledger.is_file():
            errors.append("missing 90-audit/uncertain-items.jsonl")
            open_items = []
        else:
            try:
                open_items = [json.loads(line) for line in open_ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"invalid uncertain-items.jsonl: {exc}")
                open_items = []
        if isinstance(uncertainty_summary, dict) and uncertainty_summary.get("open_material") != len(open_items):
            errors.append("quality-report uncertainty_summary.open_material mismatch")
        high_open = sum(1 for row in open_items if row.get("reader_impact") == "high")
        if ordinary_reader and editorial_data:
            glossary_report = editorial_data.get("glossary")
            glossary_report = glossary_report if isinstance(glossary_report, dict) else {}
            for report_key, count_key in (
                ("entry_count", "glossary_entries"),
                ("entries_with_first_occurrence", "glossary_with_first_occurrence"),
                ("core_entry_count", "glossary_core"),
            ):
                if glossary_report.get(report_key) != reader_counts.get(count_key):
                    errors.append(f"editorial-report glossary.{report_key} does not match reader-aids.json")
            if glossary_report.get("reader_review_sampled") != revision_counts.get("glossary_sampled"):
                errors.append("editorial-report glossary.reader_review_sampled does not match whole-book reader review")
            reader_value = editorial_data.get("reader_value")
            reader_value = reader_value if isinstance(reader_value, dict) else {}
            for key, expected in {
                "introduction_sections": reader_counts.get("introduction_sections"),
                "review_dimensions": revision_counts.get("review_dimensions"),
                "revision_cycle": acceptance_data.get("cycle_id"),
                "applied_revisions": revision_counts.get("applied_revisions"),
                "producer": acceptance_data.get("producer"),
                "reviewer": acceptance_data.get("reviewer"),
                "status": acceptance_data.get("status"),
            }.items():
                if reader_value.get(key) != expected:
                    errors.append(f"editorial-report reader_value.{key} does not match reader acceptance")
            semantic_review = editorial_data.get("semantic_review")
            semantic_review = semantic_review if isinstance(semantic_review, dict) else {}
            if semantic_review.get("high_impact_open") != high_open:
                errors.append("editorial-report semantic_review.high_impact_open mismatch")
            pipeline_scan = editorial_data.get("pipeline_language_scan")
            pipeline_scan = pipeline_scan if isinstance(pipeline_scan, dict) else {}
            if pipeline_scan.get("forbidden_matches") != 0:
                errors.append("editorial-report reader layer contains internal pipeline language")
        if data.get("grade") == "A" and open_items:
            errors.append("grade A cannot contain open_material uncertainty")
        if data.get("grade") == "B" and high_open:
            errors.append("grade B cannot contain high-impact open_material uncertainty")

    if pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf))
            actual_pages = len(reader.pages)
            reported_pages = publication.get("pdf_pages")
            if isinstance(reported_pages, int) and reported_pages != actual_pages:
                errors.append(f"official PDF page count differs from report: {actual_pages}/{reported_pages}")

            inspected = publication.get("rendered_pages_inspected")
            if ordinary_reader and inspected != actual_pages:
                errors.append(
                    "short/medium book requires full rendered-page inspection; "
                    f"got {inspected}/{actual_pages}"
                )

            internal_links = 0
            for page in reader.pages:
                annotations = page.get("/Annots") or []
                for annotation_ref in annotations:
                    annotation = annotation_ref.get_object()
                    if annotation.get("/Subtype") != "/Link":
                        continue
                    if annotation.get("/Dest") is not None:
                        internal_links += 1
                        continue
                    action = annotation.get("/A")
                    if action and action.get("/S") == "/GoTo":
                        internal_links += 1

            try:
                outline = reader.outline
                outline_items = len(outline) if isinstance(outline, list) else int(bool(outline))
            except Exception:
                outline_items = 0

            if actual_pages > 5 and internal_links == 0:
                errors.append("official PDF has no internal clickable TOC links")
            if actual_pages > 5 and outline_items == 0:
                errors.append("official PDF has no bookmarks/outlines")
        except ImportError:
            warnings.append("pypdf unavailable; PDF page, link, and bookmark checks skipped")
        except Exception as exc:
            errors.append(f"could not inspect official PDF structure: {exc}")

    result = {
        "valid": not errors,
        "official_pdf": str(pdf.relative_to(root)) if pdf.is_relative_to(root) else str(pdf),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
