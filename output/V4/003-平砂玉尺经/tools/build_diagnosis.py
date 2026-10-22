#!/usr/bin/env python3
"""Build page-level diagnosis and all-page visual evidence for Book 003."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "00-intake" / "source.pdf"
MIDDLE = Path(
    r"C:\Users\QIQI\.codex\visualizations\2026\09\18\01a0b255-9285-73d3-b98d-0ebe46512e50"
    r"\ocr_batch\full-output\doc002\doc002\ocr\doc002_middle.json"
)
PARENT_OFFSET = 166
PAGE_COUNT = 86
SAMPLE_PAGES = {1, 2, 3, 4, 10, 20, 30, 40, 50, 60, 70, 80, 84, 85, 86}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_pages() -> list[Path]:
    pages_dir = ROOT / "20-source" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    targets = [pages_dir / f"P{page:06d}.jpg" for page in range(1, PAGE_COUNT + 1)]
    if not all(path.exists() and path.stat().st_size > 0 for path in targets):
        render_dir = pages_dir / "_render"
        if render_dir.exists():
            shutil.rmtree(render_dir)
        render_dir.mkdir()
        executable = shutil.which("pdftoppm")
        if not executable:
            raise RuntimeError("pdftoppm is unavailable")
        subprocess.run(
            [
                executable, "-jpeg", "-jpegopt", "quality=90,progressive=y,optimize=y",
                "-scale-to-x", "912", "-scale-to-y", "-1", str(SOURCE), str(render_dir / "page"),
            ],
            check=True,
        )
        rendered = sorted(render_dir.glob("page-*.jpg"))
        if len(rendered) != PAGE_COUNT:
            raise RuntimeError(f"Rendered {len(rendered)} pages; expected {PAGE_COUNT}")
        for page, path in enumerate(rendered, 1):
            path.replace(pages_dir / f"P{page:06d}.jpg")
        render_dir.rmdir()
    return targets


def build_contact_sheets(page_paths: list[Path]) -> tuple[list[str], list[int], dict[int, dict]]:
    output = ROOT / "10-diagnosis" / "all-page-visual-audit"
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("sheet-*.jpg"):
        old.unlink()
    tiles: list[Image.Image] = []
    blank_like: list[int] = []
    image_stats: dict[int, dict] = {}
    for page, path in enumerate(page_paths, 1):
        with Image.open(path) as raw:
            image = raw.convert("RGB")
        stat = ImageStat.Stat(image.convert("L"))
        mean = round(stat.mean[0], 2)
        variance = round(stat.var[0], 2)
        image_stats[page] = {"mean_luma": mean, "variance": variance, "bytes": path.stat().st_size}
        if mean > 252.5 and variance < 8:
            blank_like.append(page)
        image.thumbnail((180, 245))
        tile = Image.new("RGB", (190, 270), "white")
        tile.paste(image, ((190 - image.width) // 2, 20))
        ImageDraw.Draw(tile).text((6, 4), f"{page:03d}", fill="black")
        tiles.append(tile)
    sheet_paths: list[str] = []
    for start in range(0, len(tiles), 40):
        sheet = Image.new("RGB", (190 * 5, 270 * 8), "#d9dedc")
        for offset, tile in enumerate(tiles[start : start + 40]):
            sheet.paste(tile, ((offset % 5) * 190, (offset // 5) * 270))
        path = output / f"sheet-{start // 40 + 1:02d}.jpg"
        sheet.save(path, quality=86)
        sheet_paths.append(str(path.relative_to(ROOT)))
    return sheet_paths, blank_like, image_stats


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    manifest = read_json(ROOT / "00-intake" / "source-manifest.json")
    if sha256(SOURCE) != manifest["source_sha256"]:
        raise RuntimeError("Staged source hash mismatch")
    reader = PdfReader(str(SOURCE))
    if reader.is_encrypted or len(reader.pages) != PAGE_COUNT:
        raise RuntimeError("Expected an unencrypted 86-page book-specific source")
    text_counts = [len((page.extract_text() or "").strip()) for page in reader.pages]
    if any(text_counts):
        raise RuntimeError("Source unexpectedly contains an extractable text layer")

    page_paths = render_pages()
    sheet_paths, blank_like, image_stats = build_contact_sheets(page_paths)
    middle = read_json(MIDDLE)["pdf_info"]
    if len(middle) != 346:
        raise RuntimeError("MinerU parent-page evidence no longer matches the 346-page source")

    page_records = []
    complex_pages: list[int] = []
    poor_pages: list[int] = []
    scan_quality_counts: Counter[str] = Counter()
    for book_page in range(1, PAGE_COUNT + 1):
        parent_zero = PARENT_OFFSET + book_page - 1
        parent_page = parent_zero + 1
        page = middle[parent_zero]
        types = Counter(block.get("type", "unknown") for block in page.get("para_blocks", []))
        has_visual = any(types.get(kind, 0) for kind in ("image", "table", "equation", "image_body"))
        stats = image_stats[book_page]
        low_quality = stats["mean_luma"] < 170 or stats["variance"] < 450
        if book_page == 1:
            family = "title_page"
            layout = ["vertical", "large_title", "multi_column"]
            route = ["preserve_full_page", "layout_ocr_vertical_zh"]
            risks = []
        elif book_page <= 4:
            family = "front_matter"
            layout = ["vertical", "multi_column", "classical_prose"]
            route = ["layout_ocr_vertical_zh", "visual_verify_column_order"]
            risks = ["vertical_column_order"]
        else:
            family = "content"
            layout = ["vertical", "multi_column", "classical_prose"]
            route = ["layout_ocr_vertical_zh", "page_image_verification"]
            risks = ["vertical_column_order"]
        if has_visual:
            layout.append("diagram_or_table")
            route.extend(["preserve_figures", "independent_visual_check"])
            risks.extend(["diagram_text", "complex_reading_order"])
            complex_pages.append(book_page)
        if low_quality:
            quality = "poor"
            risks.extend(["low_contrast_or_noise", "conservative_transcription_required"])
            poor_pages.append(book_page)
        else:
            quality = "fair" if book_page != 1 else "good"
        scan_quality_counts[quality] += 1
        page_records.append({
            "schema_version": "1.0",
            "book_id": manifest["book_id"],
            "page_id": f"P{book_page:06d}",
            "source_page": book_page,
            "parent_source_page": parent_page,
            "page_kind": "scan",
            "content_family": family,
            "layout": layout,
            "languages": ["lzh", "zh-Hant"],
            "text_layer_quality": "none",
            "scan_quality": quality,
            "route": list(dict.fromkeys(route)),
            "risk_flags": list(dict.fromkeys(risks)),
            "sample_verified": book_page in SAMPLE_PAGES,
            "mineru_block_types": dict(types),
            "image_stats": stats,
            "disposition": "included_content",
            "notes": [],
        })
    (ROOT / "10-diagnosis" / "page-map.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in page_records), encoding="utf-8"
    )

    segments_path = ROOT.parents[2] / "Md" / "V3" / "_work" / "segments" / "book003.jsonl"
    results_path = ROOT.parents[2] / "Md" / "V3" / "_work" / "results" / "book003.jsonl"
    segments = [json.loads(line) for line in segments_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    translatable = sum(bool(row.get("translatable")) for row in segments)
    profile = {
        "schema_version": "1.0",
        "book_id": manifest["book_id"],
        "diagnosed_at": now,
        "status": "pending_all_page_visual_confirmation",
        "source": {
            "path": str(SOURCE),
            "sha256": manifest["source_sha256"],
            "bytes": SOURCE.stat().st_size,
            "physical_pages": PAGE_COUNT,
            "parent_page_range": [167, 252],
            "encrypted": False,
            "corrupt": False,
            "embedded_text_pages": 0,
            "embedded_text_characters": 0,
        },
        "page_accounting": {
            "included_content": PAGE_COUNT,
            "blank_or_noncontent": 0,
            "excluded": 0,
            "unreadable": 0,
        },
        "page_kind_counts": {"scan": PAGE_COUNT},
        "scan_quality_counts": dict(scan_quality_counts),
        "layout_families": [
            "vertical_large_title", "vertical_multi_column_classical_prose",
            "diagrams_and_formula_like_tables", "noisy_or_low_contrast_scan",
        ],
        "language_families": ["lzh", "zh-Hant"],
        "representative_verified_pages": sorted(SAMPLE_PAGES),
        "complex_pages": complex_pages,
        "low_quality_pages": poor_pages,
        "proposed_routes": [
            "layout_ocr_vertical_zh", "visual_verify_column_order", "preserve_figures",
            "independent_visual_check", "page_image_verification",
        ],
        "known_limits": [
            "The source has no text layer; all 86 pages require image-grounded reconstruction.",
            "The parent scan contains noise, bleed-through, and diagram-heavy pages requiring conservative transcription.",
            "V2 recorded 550 non-applied candidates for this book; unresolved items remain ledger entries unless independently verified.",
        ],
        "reuse_inventory": {
            "v2_markdown": "Md/V2/003 平砂玉尺经.md",
            "v2_book_report": "Md/V2/_reports/books/003.json",
            "v3_segments": "Md/V3/_work/segments/book003.jsonl",
            "v3_results": "Md/V3/_work/results/book003.jsonl",
            "v3_declared_segments": len(segments),
            "v3_declared_translatable_segments": translatable,
            "v3_result_records": len(results),
            "policy": "Reuse only after source-text evidence and stable block mapping match the V4 reconstruction.",
        },
        "all_page_visual_audit": {
            "rendered_pages": PAGE_COUNT,
            "contact_sheets": sheet_paths,
            "automatic_blank_like_pages": blank_like,
            "status": "awaiting_human_visual_confirmation",
        },
        "cost_estimate": {
            "paid_calls_used_for_diagnosis": 0,
            "paid_repair_budget_pending_source_and_v3_reuse_audit": True,
        },
        "recommended_grade_ceiling_at_diagnosis": "B",
        "grade_ceiling_reason": "Recoverable complete scan with bounded OCR and diagram uncertainty requiring a ledger.",
    }
    write_json(ROOT / "10-diagnosis" / "profile.json", profile)
    (ROOT / "10-diagnosis" / "diagnosis-report.md").write_text(
        "# 《平砂玉尺经》V4诊断报告（待视觉确认）\n\n"
        "- 独立书源：合订本原 PDF 第167–252页，共86页。\n"
        "- 文字层：0/86页；必须以页面图像为证据重建。\n"
        "- 逐页路由：86/86。\n"
        f"- 图式或复杂版面页：{len(complex_pages)}页。\n"
        f"- 自动疑似空白页：{len(blank_like)}页。\n"
        f"- 自动标记低质页：{len(poor_pages)}页。\n"
        "- 当前状态：等待全部接触表视觉确认，确认后方可通过G1。\n",
        encoding="utf-8",
    )
    state = read_json(ROOT / "run-state.json")
    state["updated_at"] = now
    state["stages"]["diagnosis"] = {
        "status": "running",
        "pages_routed": PAGE_COUNT,
        "rendered_pages": PAGE_COUNT,
        "visual_confirmation": "pending",
        "paid_cost_rmb": 0,
    }
    state["tools"] = ["Poppler pdftoppm", "pypdf", "MinerU evidence reuse", "chaoyun-pdf-diagnoser"]
    write_json(ROOT / "run-state.json", state)
    print(json.dumps({
        "pages_routed": PAGE_COUNT,
        "complex_pages": len(complex_pages),
        "poor_pages": poor_pages,
        "blank_like": blank_like,
        "contact_sheets": sheet_paths,
        "v3_segments": len(segments),
        "v3_translatable": translatable,
        "v3_results": len(results),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
