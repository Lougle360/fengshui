from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(r"D:\壮五福\风水项目")
WORKSPACE = ROOT / "output" / "V4" / "001-青囊海角经"
SOURCE_PDF = Path(r"D:\ocr_work\v4-book001-99b2edc1\source.pdf")
MIDDLE_JSON = Path(
    r"C:\Users\QIQI\.codex\visualizations\2026\09\18\01a0b255-9285-73d3-b98d-0ebe46512e50"
    r"\ocr_batch\full-output\doc001\doc001\ocr\doc001_middle.json"
)
PROOF_JSONL = ROOT / "Md" / "V2" / "_reports" / "proof" / "doc001.proof.jsonl"
AUDIT_JSON = ROOT / "Md" / "V2" / "_reports" / "documents" / "doc001.audit.json"
V2_MD = ROOT / "Md" / "V2" / "001 青囊海角经（郭璞著·郑同校·2017）.md"
MASTER_LEDGER = ROOT / "output" / "V4" / "V4交付总账.json"
PDFTOPPM = Path(
    r"D:\CDriveMigration\QIQI-cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)

# The prior page-proof run accidentally carried the continuation from physical
# page 28 into the last text block on page 27. The exact page break below was
# independently verified against both retained page images on 2026-09-26.
VISUAL_PAGE_OVERRIDES = {
    (26, 3): (
        "元女以坤元天书取其三吉，不用五凶山水也。以九曜之权衡，取阴阳之得配，贪巨廉武，"
        "洛书取其阴也。抽中爻为体，则知上下阴阳得配以定吉龙也。破禄文辅，洛书弃其阳也。"
        "抽中爻而知上下，孤阴寡阳而失配，"
    )
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def block_text(block: dict) -> str:
    parts: list[str] = []
    for line in block.get("lines", []):
        text = "".join(
            str(span.get("content", ""))
            for span in line.get("spans", [])
            if span.get("type") == "text"
        ).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def block_score(block: dict) -> float:
    scores = [
        float(span.get("score"))
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span.get("type") == "text" and isinstance(span.get("score"), (int, float))
    ]
    if scores:
        return round(sum(scores) / len(scores), 4)
    if isinstance(block.get("score"), (int, float)):
        return round(float(block["score"]), 4)
    return 0.5


def normalize_block_type(value: str) -> str:
    mapping = {
        "text": "body",
        "title": "title",
        "index": "toc",
        "image": "figure",
        "image_body": "figure",
        "image_caption": "image_caption",
        "table": "table",
        "equation": "formula",
    }
    return mapping.get(value or "", value or "unknown")


def scale_bbox(bbox, source_size: tuple[int, int], output_size: tuple[int, int]):
    if not bbox or len(bbox) != 4:
        return None
    sx = output_size[0] / source_size[0]
    sy = output_size[1] / source_size[1]
    return [round(bbox[0] * sx), round(bbox[1] * sy), round(bbox[2] * sx), round(bbox[3] * sy)]


def render_pages(page_count: int) -> dict[int, tuple[int, int]]:
    pages_dir = WORKSPACE / "20-source" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    final_paths = [pages_dir / f"P{i:06d}.jpg" for i in range(1, page_count + 1)]
    if not all(path.exists() and path.stat().st_size > 0 for path in final_paths):
        temp_dir = pages_dir / "_render"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        prefix = temp_dir / "page"
        cmd = [
            str(PDFTOPPM),
            "-jpeg",
            "-jpegopt",
            "quality=90,progressive=y,optimize=y",
            "-scale-to-x",
            "912",
            "-scale-to-y",
            "-1",
            str(SOURCE_PDF),
            str(prefix),
        ]
        subprocess.run(cmd, check=True)
        rendered = sorted(temp_dir.glob("page-*.jpg"))
        if len(rendered) != page_count:
            raise RuntimeError(f"rendered {len(rendered)} pages, expected {page_count}")
        for index, source in enumerate(rendered, 1):
            source.replace(pages_dir / f"P{index:06d}.jpg")
        temp_dir.rmdir()

    dimensions: dict[int, tuple[int, int]] = {}
    for index, path in enumerate(final_paths, 1):
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            dimensions[index] = image.size
    return dimensions


def latest_successful_proof() -> dict[int, dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for line in PROOF_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            grouped[int(row["page"])].append(row)
    result: dict[int, dict] = {}
    for page_zero, rows in grouped.items():
        successes = [row for row in rows if row.get("status") == "success"]
        if not successes:
            raise RuntimeError(f"no successful proof record for page index {page_zero}")
        result[page_zero] = successes[-1]
    return result


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"^>\s*来源：.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", "", text)


def shingle_coverage(reference: str, candidate: str, width: int = 12) -> float:
    reference = clean_markdown(reference)
    candidate = clean_markdown(candidate)
    if len(reference) < width:
        return 1.0 if reference in candidate else 0.0
    shingles = [reference[i : i + width] for i in range(0, len(reference) - width + 1, width)]
    return round(sum(shingle in candidate for shingle in shingles) / len(shingles), 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()

    now = utc_now()
    book = read_json(WORKSPACE / "book.json")
    middle = read_json(MIDDLE_JSON)["pdf_info"]
    proofs = latest_successful_proof()
    audit = read_json(AUDIT_JSON)
    page_count = len(middle)
    if page_count != 216 or len(proofs) != page_count:
        raise RuntimeError(f"page mismatch: middle={page_count}, proofs={len(proofs)}")
    if sha256(SOURCE_PDF).lower() != book["source_pdf_sha256"].lower():
        raise RuntimeError("source PDF hash mismatch")

    if args.skip_render:
        dimensions = {}
        for page in range(1, page_count + 1):
            path = WORKSPACE / "20-source" / "pages" / f"P{page:06d}.jpg"
            with Image.open(path) as image:
                dimensions[page] = image.size
    else:
        dimensions = render_pages(page_count)

    applied_by_page_block: dict[tuple[int, int], list[dict]] = defaultdict(list)
    unresolved_entries: list[dict] = []
    for entry in audit["entries"]:
        key = (int(entry["page_zero_based"]), int(entry["block_index"]))
        if entry.get("status") in {"applied", "already_applied"} and entry.get("old") != entry.get("new"):
            applied_by_page_block[key].append(entry)
        elif entry.get("status") == "recorded_not_applied" and entry.get("old") != entry.get("new"):
            unresolved_entries.append(entry)

    records: list[dict] = []
    markdown: list[str] = ["# 青囊海角经：可追溯原文层", ""]
    correction_events: list[dict] = []
    failed_corrections: list[dict] = []
    fallback_pages: list[int] = []
    figure_blocks = 0
    blank_or_visual_pages: list[int] = []

    for page_zero in range(page_count):
        physical_page = page_zero + 1
        page_id = f"P{physical_page:06d}"
        page_meta = middle[page_zero]
        source_size = tuple(page_meta["page_size"])
        output_size = dimensions[physical_page]
        proof_blocks = proofs[page_zero].get("blocks") or []
        working: list[dict] = []

        if proof_blocks:
            for block_index, raw in enumerate(proof_blocks):
                text = str(raw.get("text", "")).strip()
                original = text
                for correction in applied_by_page_block.get((page_zero, block_index), []):
                    old = str(correction.get("old", ""))
                    new = str(correction.get("new", ""))
                    if old and text.count(old) == 1:
                        text = text.replace(old, new, 1)
                        correction_events.append(
                            {
                                "source_page": physical_page,
                                "block_index": block_index,
                                "candidate_id": correction.get("candidate_id"),
                                "before": old,
                                "after": new,
                                "reason": correction.get("judge_reason"),
                            }
                        )
                    else:
                        failed_corrections.append(correction)
                override = VISUAL_PAGE_OVERRIDES.get((page_zero, block_index))
                if override is not None and text != override:
                    correction_events.append(
                        {
                            "source_page": physical_page,
                            "block_index": block_index,
                            "candidate_id": -1,
                            "before": text,
                            "after": override,
                            "reason": "Physical pages 27 and 28 were visually compared; page 27 ends at ‘孤阴寡阳而失配，’ and page 28 begins ‘以舍凶龙也。’.",
                        }
                    )
                    text = override
                working.append(
                    {
                        "type": normalize_block_type(str(raw.get("type", "text"))),
                        "bbox": raw.get("bbox"),
                        "text": text,
                        "confidence": 0.97 if text == original else 0.99,
                        "evidence": ["qwen3-vl-page-proof", "two-pass-v2-audit"],
                        "notes": [],
                    }
                )
        else:
            fallback_pages.append(physical_page)
            for raw in page_meta.get("preproc_blocks", []):
                text = block_text(raw)
                block_type = normalize_block_type(str(raw.get("type", "unknown")))
                working.append(
                    {
                        "type": block_type,
                        "bbox": raw.get("bbox_fs") or raw.get("bbox"),
                        "text": text,
                        "confidence": block_score(raw),
                        "evidence": ["mineru-preproc-fallback", "page-image-retained"],
                        "notes": ["视觉校对记录无文本块，使用 MinerU 预处理层并保留整页图像。"],
                    }
                )

        # MinerU image/table regions remain first-class evidence even when the proof pass returned text.
        occupied_figures = {
            tuple(item.get("bbox") or [])
            for item in working
            if item.get("type") in {"figure", "table"}
        }
        for raw in page_meta.get("para_blocks", []):
            raw_type = normalize_block_type(str(raw.get("type", "unknown")))
            if raw_type not in {"figure", "table"}:
                continue
            bbox = raw.get("bbox")
            if tuple(bbox or []) in occupied_figures:
                continue
            working.append(
                {
                    "type": raw_type,
                    "bbox": bbox,
                    "text": "",
                    "confidence": block_score(raw),
                    "evidence": ["mineru-layout", "page-image-retained"],
                    "notes": ["图像内容以整页证据图保留，文字解释在相邻图题或正文块中。"],
                }
            )

        if not working or not any(item.get("text") or item.get("type") in {"figure", "table"} for item in working):
            blank_or_visual_pages.append(physical_page)
            working = [
                {
                    "type": "noncontent",
                    "bbox": [0, 0, source_size[0], source_size[1]],
                    "text": "",
                    "confidence": 1.0,
                    "evidence": ["page-image-retained", "full-corpus-contact-sheet-review"],
                    "notes": ["本页为留白或无正文版面；整页图像已保留，未静默丢页。"],
                }
            ]

        markdown.extend([f"## 物理页 {physical_page} {{#{page_id}}}", ""])
        for sequence, item in enumerate(working, 1):
            block_id = f"{page_id}-B{sequence:03d}"
            text = item["text"]
            block_type = item["type"]
            if block_type in {"figure", "table"}:
                figure_blocks += 1
            disposition = "retained" if text or block_type in {"figure", "table", "noncontent"} else "unreadable"
            record = {
                "schema_version": "1.0",
                "book_id": book["book_id"],
                "page_id": page_id,
                "block_id": block_id,
                "source_page": physical_page,
                "block_type": block_type,
                "bbox": scale_bbox(item.get("bbox"), source_size, output_size),
                "source_image": f"20-source/pages/{page_id}.jpg",
                "source_text": text,
                "normalized_text": None,
                "modern_text": None,
                "language": "mixed" if physical_page <= 15 else "lzh",
                "operation": "source",
                "disposition": disposition,
                "confidence": item["confidence"],
                "evidence": item["evidence"],
                "notes": item["notes"],
            }
            records.append(record)
            if block_type == "title" and text:
                markdown.extend([f"### {text}", ""])
            elif block_type in {"figure", "table"}:
                markdown.extend([f"![{block_type} {block_id}](pages/{page_id}.jpg)", ""])
            elif text:
                markdown.extend([text, ""])
            else:
                markdown.extend([f"> [{block_type}：见 {page_id} 页图像证据]", ""])

    source_dir = WORKSPACE / "20-source"
    blocks_path = source_dir / "blocks.jsonl"
    blocks_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    source_md_path = source_dir / "source.md"
    source_md_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    unresolved_path = WORKSPACE / "90-audit" / "uncertain-items.jsonl"
    unresolved_path.write_text("", encoding="utf-8")
    for entry in unresolved_entries:
        page = int(entry["source_page"])
        append_jsonl(
            unresolved_path,
            {
                "schema_version": "1.0",
                "book_id": book["book_id"],
                "item_id": f"V2-AUDIT-P{page:06d}-C{int(entry['candidate_id']):03d}",
                "source_page": page,
                "page_id": f"P{page:06d}",
                "source_image": f"20-source/pages/P{page:06d}.jpg",
                "stage": "source_reconstruction",
                "status": "recorded_not_applied",
                "old": entry.get("old"),
                "proposed": entry.get("new"),
                "judge_decision": entry.get("judge_decision"),
                "judge_confidence": entry.get("judge_confidence"),
                "rationale": entry.get("judge_reason"),
                "reasons": entry.get("reasons", []),
                "source_audit": "Md/V2/_reports/documents/doc001.audit.json",
            },
        )

    events_path = WORKSPACE / "90-audit" / "events.jsonl"
    prior_correction_keys: set[tuple[int, int, int]] = set()
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            prior = json.loads(line)
            if prior.get("event") == "source_correction_reapplied":
                prior_correction_keys.add(
                    (
                        int(prior.get("source_page", -1)),
                        int(prior.get("block_index", -1)),
                        int(prior.get("candidate_id", -1)),
                    )
                )
    for event in correction_events:
        key = (int(event["source_page"]), int(event["block_index"]), int(event["candidate_id"]))
        if key in prior_correction_keys:
            continue
        append_jsonl(
            events_path,
            {
                "schema_version": "1.0",
                "event": "source_correction_reapplied",
                "time": now,
                "actor": "build_source_layer.py",
                **event,
            },
        )

    source_text = "\n".join(str(record["source_text"]) for record in records if record["source_text"])
    v2_text = V2_MD.read_text(encoding="utf-8")
    coverage = shingle_coverage(v2_text, source_text)
    report = {
        "schema_version": "1.0",
        "book_id": book["book_id"],
        "generated_at": now,
        "status": "passed_with_ledger" if not failed_corrections else "failed",
        "physical_pages": page_count,
        "page_images": len(dimensions),
        "source_blocks": len(records),
        "text_blocks": sum(bool(record["source_text"]) for record in records),
        "figure_or_table_blocks": figure_blocks,
        "proof_primary_pages": page_count - len(fallback_pages),
        "mineru_fallback_pages": fallback_pages,
        "blank_or_visual_only_pages": blank_or_visual_pages,
        "accepted_corrections_reapplied": sum(event["candidate_id"] >= 0 for event in correction_events),
        "manual_visual_page_boundary_corrections": sum(event["candidate_id"] < 0 for event in correction_events),
        "accepted_corrections_failed": len(failed_corrections),
        "unresolved_text_change_candidates": len(unresolved_entries),
        "v2_markdown_12char_shingle_coverage": coverage,
        "source_pdf_sha256": sha256(SOURCE_PDF),
        "blocks_sha256": sha256(blocks_path),
        "source_md_sha256": sha256(source_md_path),
        "evidence": {
            "proof": str(PROOF_JSONL),
            "two_pass_audit": str(AUDIT_JSON),
            "mineru_middle": str(MIDDLE_JSON),
            "v2_markdown": str(V2_MD),
        },
    }
    write_json(source_dir / "source-reconstruction-report.json", report)
    if failed_corrections:
        write_json(source_dir / "failed-corrections.json", failed_corrections)
        raise RuntimeError(f"{len(failed_corrections)} accepted corrections could not be reapplied")
    if coverage < 0.75:
        raise RuntimeError(f"V2 markdown coverage too low: {coverage:.2%}")

    state_path = WORKSPACE / "run-state.json"
    state = read_json(state_path)
    state.setdefault("stages", {})["source_reconstruction"] = {
        "status": "passed_with_ledger",
        "updated_at": now,
        "physical_pages": page_count,
        "page_images": page_count,
        "blocks": len(records),
        "accepted_corrections_reapplied": sum(event["candidate_id"] >= 0 for event in correction_events),
        "manual_visual_page_boundary_corrections": sum(event["candidate_id"] < 0 for event in correction_events),
        "unresolved_candidates": len(unresolved_entries),
        "v2_markdown_12char_shingle_coverage": coverage,
        "tool": "build_source_layer.py + existing Qwen3-VL two-pass audit + MinerU",
        "cost": 0,
        "evidence": "20-source/source-reconstruction-report.json",
    }
    state["current_stage"] = "normalization"
    state["updated_at"] = now
    write_json(state_path, state)

    append_jsonl(
        WORKSPACE / "90-audit" / "events.jsonl",
        {
            "schema_version": "1.0",
            "event": "stage_gate",
            "stage": "source_reconstruction",
            "status": "passed_with_ledger",
            "time": now,
            "actor": "build_source_layer.py",
            "counts": {
                "pages": page_count,
                "blocks": len(records),
                "corrections_reapplied": sum(event["candidate_id"] >= 0 for event in correction_events),
                "manual_visual_corrections": sum(event["candidate_id"] < 0 for event in correction_events),
                "uncertain_items": len(unresolved_entries),
            },
            "rationale": "216页均有整页图像；视觉校对文本为主，MinerU预处理层补齐目录和特殊版面；既有两轮审校结论完整继承。",
        },
    )

    ledger = read_json(MASTER_LEDGER)
    for item in ledger["books"]:
        if int(item["book_no"]) == 1:
            item.update(
                {
                    "status": "source_reconstructed",
                    "current_stage": "normalization",
                    "source_pages": page_count,
                    "source_blocks": len(records),
                    "source_gate": "passed_with_ledger",
                    "updated_at": now,
                }
            )
            break
    ledger["updated_at"] = now
    write_json(MASTER_LEDGER, ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
