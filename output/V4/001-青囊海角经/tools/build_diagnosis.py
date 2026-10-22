#!/usr/bin/env python3
"""Create the page-level V4 diagnosis for book 001."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
V4_ROOT = ROOT.parent
PROJECT_ROOT = V4_ROOT.parents[1]
SOURCE = PROJECT_ROOT / "Docs" / "地学-经典" / "《青囊海角经》四库存目 青囊汇刊2 (晋)郭璞著 郑同校2017.pdf"
STAGED = Path(r"D:\ocr_work\v4-book001-99b2edc1\source.pdf")
SAMPLE_SOURCE = PROJECT_ROOT / "tmp" / "pdfs" / "v4-book001-diagnosis"
SAMPLE_OUTPUT = ROOT / "10-diagnosis" / "samples"
EXPECTED_SHA = "99B2EDC10753C8C5E32F7DBBA6D88B9E6FC9CEA0FA1EEA16012E841C9B5E22B9"
SAMPLE_PAGES = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 40, 80, 120, 160, 200, 216}
KNOWN_COMPLEX_PAGES = {5, 6, 7, 8, 9, 11, 12, 13, 14, 16, 40, 54, 56, 58, 60, 61}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_event(event: dict) -> None:
    path = ROOT / "90-audit" / "events.jsonl"
    existing = {
        json.loads(line).get("event_id")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if event["event_id"] not in existing:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def page_family(page: int) -> tuple[str, list[str], list[str], str, list[str], list[str]]:
    if page == 1:
        return "cover", ["full_page_art", "vertical_title"], ["zh-Hant", "lzh"], "good", ["color_background"], ["preserve_full_page", "visual_transcription"]
    if page == 2:
        return "title_page", ["vertical_title", "illustration"], ["zh-Hant", "lzh"], "good", [], ["layout_ocr", "preserve_figures"]
    if page == 3:
        return "copyright", ["horizontal", "single_column", "bibliographic"], ["zh-Hans"], "good", [], ["layout_ocr_horizontal"]
    if page == 4:
        return "preface", ["horizontal", "single_column"], ["zh-Hans"], "good", [], ["layout_ocr_horizontal"]
    if 5 <= page <= 10:
        return "table_of_contents", ["horizontal", "dense_toc", "page_numbers"], ["zh-Hans", "zh-Hant", "lzh"], "good", ["dense_small_text"], ["layout_ocr_toc", "visual_verify_reading_order"]
    if page == 216:
        return "back_cover", ["full_page_art", "bibliographic"], ["zh-Hans", "zh-Hant"], "good", ["color_background"], ["preserve_full_page", "visual_transcription"]
    if page in KNOWN_COMPLEX_PAGES:
        return "content", ["horizontal", "diagram_or_table", "single_column"], ["lzh", "zh-Hant", "zh-Hans"], "fair", ["diagram_text", "complex_reading_order"], ["layout_ocr_with_figure_preservation", "independent_visual_check"]
    return "content", ["horizontal", "single_column"], ["lzh", "zh-Hant", "zh-Hans"], "good", [], ["layout_ocr_horizontal", "page_image_verification"]


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    for path in (SOURCE, STAGED):
        if not path.is_file() or sha256(path) != EXPECTED_SHA:
            raise RuntimeError(f"Source identity check failed: {path}")
    reader = PdfReader(str(STAGED))
    if len(reader.pages) != 216 or reader.is_encrypted:
        raise RuntimeError("Expected an unencrypted 216-page source PDF")
    text_counts = [len((page.extract_text() or "").strip()) for page in reader.pages]
    if any(text_counts):
        raise RuntimeError("Diagnosis assumption changed: source now has extractable text")

    SAMPLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    sample_files = [
        path
        for path in sorted(SAMPLE_SOURCE.glob("front-*.png")) + sorted(SAMPLE_SOURCE.glob("sample-*.png"))
        if "contact" not in path.name
    ]
    if len(sample_files) != len(SAMPLE_PAGES):
        raise RuntimeError(f"Expected {len(SAMPLE_PAGES)} rendered verification pages, found {len(sample_files)}")
    for source in sample_files:
        shutil.copy2(source, SAMPLE_OUTPUT / source.name)

    profile = {
        "schema_version": "1.0",
        "book_id": "99b2edc10753c8c5",
        "diagnosed_at": now,
        "source": {
            "path": str(SOURCE),
            "staged_ascii_path": str(STAGED),
            "sha256": EXPECTED_SHA,
            "bytes": SOURCE.stat().st_size,
            "physical_pages": 216,
            "encrypted": False,
            "corrupt": False,
            "page_size_points": [456.945, 675.84],
            "embedded_text_pages": 0,
            "embedded_text_characters": 0,
        },
        "page_accounting": {"included": 216, "excluded": 0, "blank_or_noncontent_pending_source_stage": 0, "unreadable": 0},
        "page_kind_counts": {"scan": 216},
        "layout_families": [
            "color_cover", "vertical_title", "copyright_bibliography", "dense_table_of_contents",
            "horizontal_single_column_prose", "diagram_and_caption", "verse_or_list", "back_cover",
        ],
        "language_families": ["zh-Hans", "zh-Hant", "lzh", "mixed"],
        "representative_verified_pages": sorted(SAMPLE_PAGES),
        "known_complex_pages": sorted(KNOWN_COMPLEX_PAGES),
        "proposed_routes": [
            "layout_ocr_horizontal", "layout_ocr_toc", "layout_ocr_with_figure_preservation",
            "independent_visual_check", "preserve_full_page",
        ],
        "known_limits": [
            "The PDF has no extractable text layer; every included page requires image-grounded reconstruction.",
            "Dense diagrams and small labels require figure preservation and independent visual verification.",
            "V2 contains 816 conservative non-applied OCR candidates that must not be silently resolved from context.",
        ],
        "reuse_inventory": {
            "v2_markdown": "Md/V2/001 青囊海角经（郭璞著·郑同校·2017）.md",
            "v2_visual_audit": "Md/V2/_reports/documents/doc001.audit.json",
            "v3_segments": "Md/V3/_work/segments/book001.jsonl",
            "v3_results": "Md/V3/_work/results/book001.jsonl",
            "v3_traceable_coverage": "1375/1375 in the latest existing traceability audit",
            "policy": "reuse only after source hash and page/block evidence match the V4 reconstruction",
        },
        "cost_estimate": {
            "status": "pending_source_reconstruction_and_v3_reuse_audit",
            "paid_calls_used_for_diagnosis": 0,
        },
        "recommended_grade_ceiling_at_diagnosis": "B",
        "grade_ceiling_reason": "The source is recoverable and visually clear, but diagram labels and unresolved OCR candidates require ledger-backed review.",
        "status": "passed_with_ledger",
    }
    write_json(ROOT / "10-diagnosis" / "profile.json", profile)

    records = []
    for page in range(1, 217):
        family, layout, languages, quality, risks, routes = page_family(page)
        records.append(
            {
                "schema_version": "1.0",
                "book_id": "99b2edc10753c8c5",
                "page_id": f"P{page:06d}",
                "source_page": page,
                "page_kind": "scan",
                "content_family": family,
                "layout": layout,
                "languages": languages,
                "text_layer_quality": "none",
                "scan_quality": quality,
                "route": routes,
                "risk_flags": risks,
                "sample_verified": page in SAMPLE_PAGES,
                "notes": [],
            }
        )
    (ROOT / "10-diagnosis" / "page-map.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8"
    )

    book = read_json(ROOT / "book.json")
    book.update(
        {
            "corpus_book_no": 1,
            "title": "青囊海角经",
            "subtitle": "四库存目·青囊汇刊②",
            "author": "郭璞",
            "editor": "葛超云",
            "producer": "壮五福国学院",
            "source_pdf_pages": 216,
            "source_pdf_sha256": EXPECTED_SHA.lower(),
            "edition_scope": "ordinary_reader_modern_edition",
            "modernization_depth": "完整现代阅读重构",
            "release_filename": "60-publication/青囊海角经·现代白话版.pdf",
            "page_accounting": profile["page_accounting"],
        }
    )
    write_json(ROOT / "book.json", book)

    manifest = read_json(ROOT / "00-intake" / "source-manifest.json")
    manifest.update(
        {
            "source_path": str(SOURCE),
            "source_name": SOURCE.name,
            "source_bytes": SOURCE.stat().st_size,
            "source_sha256": EXPECTED_SHA.lower(),
            "source_pdf_pages": 216,
            "staged_source": str(STAGED),
            "staged_source_sha256": EXPECTED_SHA.lower(),
            "source_copied": True,
            "page_accounting": profile["page_accounting"],
            "verified_at": now,
        }
    )
    write_json(ROOT / "00-intake" / "source-manifest.json", manifest)

    state = read_json(ROOT / "run-state.json")
    state["updated_at"] = now
    state["stages"]["intake"] = {
        "status": "passed", "physical_pages": 216, "source_sha256": EXPECTED_SHA.lower(), "paid_cost_rmb": 0,
    }
    state["stages"]["diagnosis"] = {
        "status": "passed_with_ledger", "pages_routed": 216, "representative_pages_verified": len(SAMPLE_PAGES),
        "embedded_text_pages": 0, "paid_cost_rmb": 0,
    }
    state["tools"] = ["Poppler pdftoppm", "pypdf", "chaoyun-pdf-diagnoser"]
    write_json(ROOT / "run-state.json", state)

    append_event(
        {
            "schema_version": "1.0",
            "event_id": "v4-book001-intake-diagnosis",
            "time": now,
            "actor": "build_diagnosis.py",
            "operation": "intake_and_page_route_diagnosis",
            "source_ids": ["99b2edc10753c8c5"],
            "before": "pending",
            "after": "diagnosis_passed_with_ledger",
            "confidence": 1.0,
            "rationale": "All 216 pages received image-grounded routes; 17 representative pages cover all observed layout families.",
        }
    )

    report = ROOT / "10-diagnosis" / "diagnosis-report.md"
    report.write_text(
        "# 《青囊海角经》V4诊断报告\n\n"
        "- 原始PDF：216页，未加密，哈希校验通过。\n"
        "- 文字层：0/216页，必须以页面图像为证据重建。\n"
        "- 逐页路由：216/216。\n"
        "- 已视觉核验代表页：17页，覆盖封面、版权、目录、图式、正文、条目和封底。\n"
        "- 已知高风险：密集目录、图式内小字、复杂阅读顺序及V2保守未采用候选。\n"
        "- 当前质量上限：B；完成原文重建和高风险独立核验后重新评级。\n"
        "- 诊断阶段新增模型费用：0元。\n"
        "- 下一阶段：建立216页证据图和稳定block_id，审计V2/V3可复用内容。\n",
        encoding="utf-8",
    )

    ledger_path = V4_ROOT / "V4交付总账.json"
    ledger = read_json(ledger_path)
    ledger["updated_at"] = now
    ledger["next_book_no"] = 1
    for item in ledger["books"]:
        if item["book_no"] == 1:
            item.update(
                {
                    "status": "diagnosis_passed",
                    "workspace": "001-青囊海角经",
                    "current_stage": "source_reconstruction",
                    "source_pages": 216,
                }
            )
    write_json(ledger_path, ledger)

    print(
        json.dumps(
            {
                "status": "passed_with_ledger",
                "physical_pages": 216,
                "pages_routed": len(records),
                "representative_pages_verified": len(SAMPLE_PAGES),
                "next_stage": "source_reconstruction",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
