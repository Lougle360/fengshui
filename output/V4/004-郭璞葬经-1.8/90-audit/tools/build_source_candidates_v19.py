#!/usr/bin/env python3
"""Build role-correct provisional blocks; visual review is still mandatory."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "20-source/reference"
ALIGNMENT = ROOT / "40-modernized/reference-alignment.jsonl"
OUTPUT = ROOT / "20-source/blocks.v19-candidates.jsonl"
AUDIT = ROOT / "90-audit/source-candidate-review.json"
WORKSHEET = ROOT / "90-audit/source-candidate-review.md"
PAGE_REVIEWS = ROOT / "90-audit/source-page-reviews-v19b"
PAGE_BOUNDARIES = ROOT / "90-audit/source-page-boundaries.json"
RESIDUAL_DECISIONS = ROOT / "90-audit/source-residual-decisions.json"
REFERENCE_OMISSIONS = ROOT / "90-audit/source-reference-omissions.json"
STRUCTURAL_OVERRIDES = ROOT / "90-audit/source-structural-overrides.json"
PUNCTUATION = set("，。；：！？、,.!?;:'\"『』“”‘’《》（）()[]{}〈〉【】·—… \t\r\n")


def clean_wiki(text: str) -> str:
    text = re.sub(r"\[\[(?:[^]|]+\|)?([^]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("{{*|", "")
    text = re.sub(r"\{\{(?:Novel|footer|传统汉字化)[^}]*\}\}", "", text, flags=re.I)
    text = text.replace("}}", "")
    return re.sub(r"\s+", " ", text).strip()


def normalized_with_map(text: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    positions: list[int] = []
    for index, character in enumerate(text):
        if character in PUNCTUATION or character.isspace():
            continue
        characters.append(character)
        positions.append(index)
    return "".join(characters), positions


def compact(text: str) -> str:
    return normalized_with_map(clean_wiki(text))[0]


def reference_segments() -> tuple[list[dict], str]:
    segments: list[dict] = []
    token = re.compile(r"==\s*([^=]+?)\s*==|'''(.*?)'''", re.S)
    cursor = 0

    def append_segment(role: str, component: str, value: str) -> None:
        nonlocal cursor
        value = clean_wiki(value)
        normalized, text_positions = normalized_with_map(value)
        if not normalized:
            return
        segments.append({
            "segment_index": len(segments) + 1,
            "structural_role": role,
            "component_id": component,
            "reference_text": value,
            "normalized": normalized,
            "text_positions": text_positions,
            "canonical_start": cursor,
            "canonical_end": cursor + len(normalized),
        })
        cursor += len(normalized)

    for name in ("內篇.wikitext", "外篇.wikitext", "雜篇.wikitext"):
        text = (REFERENCE / name).read_text(encoding="utf-8")
        matches = list(token.finditer(text))
        if not any(match.group(1) for match in matches):
            append_segment("heading", "C-MAIN", Path(name).stem)
        previous_end = 0
        for match in matches:
            append_segment("commentary", "C-COMMENTARY", text[previous_end:match.start()])
            if match.group(1):
                append_segment("heading", "C-MAIN", match.group(1))
            else:
                append_segment("body", "C-MAIN", match.group(2))
            previous_end = match.end()
        append_segment("commentary", "C-COMMENTARY", text[previous_end:])
    return segments, "".join(segment["normalized"] for segment in segments)


def locate_alignment_rows(rows: list[dict], canonical: str) -> list[dict]:
    located: list[dict] = []
    cursor = 0
    for row in rows:
        query = compact(row["clean_source"])
        window_start = max(0, cursor - 600)
        window_end = min(len(canonical), cursor + max(3500, len(query) * 4))
        window = canonical[window_start:window_end]
        match = SequenceMatcher(None, query, window, autojunk=False).find_longest_match()
        canonical_match_start = window_start + match.b
        if match.size < 6:
            match = SequenceMatcher(None, query, canonical, autojunk=False).find_longest_match()
            canonical_match_start = match.b
        estimated_start = max(0, canonical_match_start - match.a)
        estimated_end = min(len(canonical), estimated_start + len(query))
        source_query = compact(row.get("old_source", ""))
        source_window_start = max(0, estimated_start - 800)
        source_window_end = min(len(canonical), estimated_end + max(800, len(source_query) * 3))
        source_matcher = SequenceMatcher(
            None,
            source_query,
            canonical[source_window_start:source_window_end],
            autojunk=False,
        )
        matched_source_characters = sum(
            block.size for block in source_matcher.get_matching_blocks() if block.size >= 2
        )
        cursor = max(cursor, canonical_match_start + match.size)
        located.append({
            **row,
            "canonical_start": estimated_start,
            "canonical_end": estimated_end,
            "longest_match": match.size,
            "match_coverage": round(match.size / max(1, len(query)), 4),
            "source_reference_length_ratio": round(len(compact(row["old_source"])) / max(1, len(query)), 4),
            "source_canonical_coverage": round(matched_source_characters / max(1, len(source_query)), 4),
        })
    return located


def load_page_boundary_overrides(canonical: str) -> tuple[dict[int, int], dict[int, dict]]:
    if not PAGE_BOUNDARIES.is_file():
        return {}, {}
    payload = json.loads(PAGE_BOUNDARIES.read_text(encoding="utf-8"))
    offsets: dict[int, int] = {}
    records: dict[int, dict] = {}
    for record in payload.get("boundaries", []):
        page = int(record["page"])
        anchor = compact(record["starts_with"])
        occurrences = [match.start() for match in re.finditer(re.escape(anchor), canonical)]
        occurrence = int(record.get("occurrence", 1))
        if occurrence < 1 or occurrence > len(occurrences):
            raise ValueError(f"page {page} boundary anchor is not uniquely resolvable: {record['starts_with']}")
        offsets[page] = occurrences[occurrence - 1]
        records[page] = record
    return offsets, records


def page_intervals(located: list[dict], canonical: str) -> tuple[dict[int, tuple[int, int]], dict[int, dict]]:
    by_page: dict[int, list[dict]] = defaultdict(list)
    for row in located:
        by_page[int(row["source_page"])].append(row)
    pages = sorted(by_page)
    boundaries = [0]
    for left, right in zip(pages, pages[1:]):
        left_end = max(row["canonical_end"] for row in by_page[left])
        right_start = min(row["canonical_start"] for row in by_page[right])
        boundary = (left_end + right_start) // 2
        boundary = max(boundaries[-1] + 1, min(boundary, len(canonical) - 1))
        boundaries.append(boundary)
    boundaries.append(len(canonical))
    overrides, override_records = load_page_boundary_overrides(canonical)
    for index, page in enumerate(pages):
        if page in overrides:
            boundaries[index] = overrides[page]
    if boundaries != sorted(boundaries) or len(set(boundaries)) != len(boundaries):
        raise ValueError("page-boundary overrides are not strictly increasing")
    return (
        {page: (boundaries[index], boundaries[index + 1]) for index, page in enumerate(pages)},
        override_records,
    )


def page_slices(page: int, page_start: int, page_end: int, located: list[dict]) -> list[tuple[int, int, list[str]]]:
    rows = sorted((row for row in located if int(row["source_page"]) == page), key=lambda row: row["canonical_start"])
    if not rows:
        return [(page_start, page_end, [])]
    boundaries = [page_start]
    for left, right in zip(rows, rows[1:]):
        boundary = (left["canonical_end"] + right["canonical_start"]) // 2
        boundary = max(boundaries[-1] + 1, min(boundary, page_end - 1))
        boundaries.append(boundary)
    boundaries.append(page_end)
    return [
        (boundaries[index], boundaries[index + 1], [rows[index]["candidate_id"]])
        for index in range(len(rows))
        if boundaries[index] < boundaries[index + 1]
    ]


def reference_slice(segment: dict, start: int, end: int) -> str:
    relative_start = max(0, start - segment["canonical_start"])
    relative_end = min(len(segment["normalized"]), end - segment["canonical_start"])
    positions = segment["text_positions"]
    if relative_start >= relative_end or not positions:
        return ""
    text_start = positions[relative_start]
    text_end = positions[relative_end - 1] + 1
    return segment["reference_text"][text_start:text_end].strip()


def main() -> int:
    segments, canonical = reference_segments()
    omission_payload = (
        json.loads(REFERENCE_OMISSIONS.read_text(encoding="utf-8"))
        if REFERENCE_OMISSIONS.is_file()
        else {"omissions": []}
    )
    omission_ranges = []
    for omission in omission_payload.get("omissions", []):
        left_anchor = compact(omission["after_scan_text"])
        right_anchor = compact(omission["resumes_with"])
        left = canonical.find(left_anchor)
        right = canonical.find(right_anchor, left + len(left_anchor))
        if left < 0 or right < 0 or right <= left:
            raise ValueError(f"reference omission is not resolvable: {omission['id']}")
        omission_ranges.append((left + len(left_anchor), right, omission))
    rows = [json.loads(line) for line in ALIGNMENT.read_text(encoding="utf-8").splitlines() if line.strip()]
    located = locate_alignment_rows(rows, canonical)
    intervals, boundary_records = page_intervals(located, canonical)
    support_by_page: dict[int, list[str]] = defaultdict(list)
    for row in located:
        support_by_page[int(row["source_page"])].append(row["candidate_id"])

    candidates: list[dict] = []
    page_orders: Counter[int] = Counter()
    for page, (page_start, page_end) in intervals.items():
        for segment in segments:
            overlap_start = max(page_start, segment["canonical_start"])
            overlap_end = min(page_end, segment["canonical_end"])
            if overlap_start >= overlap_end:
                continue
            pieces = [(overlap_start, overlap_end)]
            for omit_start, omit_end, _ in omission_ranges:
                next_pieces = []
                for piece_start, piece_end in pieces:
                    if omit_end <= piece_start or omit_start >= piece_end:
                        next_pieces.append((piece_start, piece_end))
                        continue
                    if piece_start < omit_start:
                        next_pieces.append((piece_start, omit_start))
                    if omit_end < piece_end:
                        next_pieces.append((omit_end, piece_end))
                pieces = next_pieces
            for piece_start, piece_end in pieces:
                text = reference_slice(segment, piece_start, piece_end)
                if not compact(text):
                    continue
                page_orders[page] += 1
                candidates.append({
                "schema_version": "1.9-candidate",
                "block_id": f"P{page:06d}-C{page_orders[page]:03d}",
                "page_id": f"P{page:06d}",
                "source_page": page,
                "component_id": segment["component_id"],
                "structural_role": segment["structural_role"],
                "reading_order": page_orders[page],
                "bbox": None,
                "bbox_status": "pending_visual_measurement",
                "source_text": None,
                "collated_text": text,
                "reference_segment_index": segment["segment_index"],
                "continues_from_previous_page": piece_start > segment["canonical_start"],
                "continues_to_next_page": piece_end < segment["canonical_end"],
                "page_ocr_support": support_by_page[page],
                "primary_evidence": f"20-source/pages/P{page:06d}.jpg",
                "collation_reference_only": True,
                "scan_transcription_status": "pending_visual_confirmation",
                    "promotion_status": "pending_visual_review",
                })

    merged_candidates: list[dict] = []
    for candidate in candidates:
        previous = merged_candidates[-1] if merged_candidates else None
        mergeable_main_split = (
            previous
            and candidate["source_page"] == previous["source_page"]
            and candidate["reference_segment_index"] == previous["reference_segment_index"]
            and candidate["structural_role"] in {"body", "heading"}
            and candidate["structural_role"] == previous["structural_role"]
        )
        if mergeable_main_split:
            previous["collated_text"] += candidate["collated_text"]
            previous["continues_to_next_page"] = candidate["continues_to_next_page"]
            previous["page_ocr_support"] = list(dict.fromkeys(previous["page_ocr_support"] + candidate["page_ocr_support"]))
        else:
            merged_candidates.append(candidate)
    candidates = merged_candidates
    structural_payload = (
        json.loads(STRUCTURAL_OVERRIDES.read_text(encoding="utf-8"))
        if STRUCTURAL_OVERRIDES.is_file()
        else {"merge_reference_segments": []}
    )
    applied_structural_overrides = []
    for override in structural_payload.get("merge_reference_segments", []):
        segment_index = int(override["reference_segment_index"])
        target_page = int(override["target_page"])
        source_pages = {int(page) for page in override.get("source_pages", [])}
        pieces = [
            row for row in candidates
            if row.get("reference_segment_index") == segment_index
            and (not source_pages or int(row["source_page"]) in source_pages)
        ]
        if not pieces:
            raise ValueError(f"structural override has no candidates: segment {segment_index}")
        pieces.sort(key=lambda row: (row["source_page"], row["reading_order"]))
        base = pieces[0]
        base["collated_text"] = "".join(row.get("collated_text") or "" for row in pieces)
        base["source_page"] = target_page
        base["page_id"] = f"P{target_page:06d}"
        base["primary_evidence"] = override["evidence_image"]
        base["bbox"] = override.get("evidence_region")
        base["bbox_status"] = "visually_measured" if override.get("evidence_region") else "pending_visual_measurement"
        base["continues_from_previous_page"] = False
        base["continues_to_next_page"] = False
        base["structural_override_status"] = override["status"]
        candidates = [row for row in candidates if row not in pieces]
        candidates.append(base)
        applied_structural_overrides.append({
            "reference_segment_index": segment_index,
            "source_pages": sorted(source_pages),
            "target_page": target_page,
            "status": override["status"],
        })
    page_orders = Counter()
    for candidate in candidates:
        page = candidate["source_page"]
        page_orders[page] += 1
        candidate["reading_order"] = page_orders[page]
        candidate["block_id"] = f"P{page:06d}-C{page_orders[page]:03d}"

    residual_payload = (
        json.loads(RESIDUAL_DECISIONS.read_text(encoding="utf-8"))
        if RESIDUAL_DECISIONS.is_file()
        else {"decisions": []}
    )
    residual_decisions = {row["candidate_id"]: row for row in residual_payload.get("decisions", [])}
    residual_rows = []
    possible_unaligned_rows = []
    for row in located:
        clean_hint = str(row["clean_source"])
        source = str(row["old_source"]).strip()
        source_length = len(compact(source))
        reference_artifact = bool(re.search(r"footer|previous|上一卷|vious", clean_hint, re.I))
        source_only_suspect = (
            row["source_reference_length_ratio"] > 3 and source_length > 80
            or row["source_canonical_coverage"] < 0.4 and source_length > 40
        )
        if source_only_suspect or reference_artifact:
            possible_unaligned_rows.append(row["candidate_id"])
        decision = residual_decisions.get(row["candidate_id"], {})
        if not source or decision.get("decision") not in {
            "retain_for_manual_transcription",
            "retain_as_structured_transcription",
        }:
            continue
        page = int(row["source_page"])
        if decision.get("decision") == "retain_as_structured_transcription":
            page = int(decision.get("evidence_page", page))
            for fragment in decision.get("fragments", []):
                page_orders[page] += 1
                evidence_region = fragment.get("evidence_region") or decision.get("evidence_region")
                candidates.append({
                    "schema_version": "1.9-candidate",
                    "block_id": f"P{page:06d}-C{page_orders[page]:03d}",
                    "page_id": f"P{page:06d}",
                    "source_page": page,
                    "component_id": fragment["component_id"],
                    "structural_role": fragment["structural_role"],
                    "reading_order": page_orders[page],
                    "bbox": evidence_region,
                    "bbox_status": "visually_measured" if evidence_region else "pending_visual_measurement",
                    "source_text": fragment["source_text"],
                    "collated_text": None,
                    "reference_segment_index": None,
                    "continues_from_previous_page": bool(fragment.get("continues_from_previous_page", False)),
                    "continues_to_next_page": bool(fragment.get("continues_to_next_page", False)),
                    "page_ocr_support": [row["candidate_id"]],
                    "primary_evidence": decision.get("evidence_image", f"20-source/pages/P{page:06d}.jpg"),
                    "collation_reference_only": False,
                    "scan_transcription_status": fragment.get("scan_transcription_status", "ocr_requires_manual_transcription"),
                    "promotion_status": fragment.get("promotion_status", "pending_visual_review"),
                    "source_text_basis": "page_specific_visual_transcription",
                    "_insert_before_reference_segment_index": fragment.get("insert_before_reference_segment_index"),
                    "_insert_after_reference_segment_index": fragment.get("insert_after_reference_segment_index"),
                })
            residual_rows.append(row["candidate_id"])
            continue
        page_orders[page] += 1
        running_matter = reference_artifact and source_length < 30
        candidates.append({
            "schema_version": "1.9-candidate",
            "block_id": f"P{page:06d}-C{page_orders[page]:03d}",
            "page_id": f"P{page:06d}",
            "source_page": page,
            "component_id": "C-FURNITURE" if running_matter else "C-COMMENTARY",
            "structural_role": "running_header" if running_matter else "commentary_unaligned",
            "reading_order": page_orders[page],
            "bbox": None,
            "bbox_status": "pending_visual_measurement",
            "source_text": source,
            "collated_text": None,
            "reference_segment_index": None,
            "continues_from_previous_page": False,
            "continues_to_next_page": False,
            "page_ocr_support": [row["candidate_id"]],
            "primary_evidence": f"20-source/pages/P{page:06d}.jpg",
            "collation_reference_only": False,
            "scan_transcription_status": "ocr_requires_manual_transcription",
            "promotion_status": "pending_visual_review",
        })
        residual_rows.append(row["candidate_id"])

    def structural_sort_key(candidate: dict) -> tuple[int, float, int]:
        before = candidate.get("_insert_before_reference_segment_index")
        after = candidate.get("_insert_after_reference_segment_index")
        segment = candidate.get("reference_segment_index")
        if before is not None:
            structural_position = float(before) - 0.5
        elif after is not None:
            structural_position = float(after) + 0.5
        elif segment is not None:
            structural_position = float(segment)
        else:
            structural_position = 1_000_000.0
        return int(candidate["source_page"]), structural_position, int(candidate["reading_order"])

    candidates.sort(key=structural_sort_key)
    page_orders = Counter()
    for candidate in candidates:
        page = int(candidate["source_page"])
        page_orders[page] += 1
        candidate["reading_order"] = page_orders[page]
        candidate["block_id"] = f"P{page:06d}-C{page_orders[page]:03d}"
        candidate.pop("_insert_before_reference_segment_index", None)
        candidate.pop("_insert_after_reference_segment_index", None)
    review_files = sorted(PAGE_REVIEWS.glob("P*.json")) if PAGE_REVIEWS.is_dir() else []
    candidate_by_id = {row["block_id"]: row for row in candidates}
    reviewed_regions = 0
    stale_review_bindings: list[str] = []
    for review_file in review_files:
        review = json.loads(review_file.read_text(encoding="utf-8"))
        for finding in review.get("blocks", []):
            candidate = candidate_by_id.get(finding.get("candidate_id"))
            if not candidate:
                stale_review_bindings.append(str(finding.get("candidate_id")))
                continue
            candidate_text = candidate.get("collated_text") or candidate.get("source_text") or ""
            expected_hash = hashlib.sha256(candidate_text.encode("utf-8")).hexdigest()
            if finding.get("candidate_text_sha256") != expected_hash:
                stale_review_bindings.append(str(finding.get("candidate_id")))
                continue
            candidate["bbox"] = finding.get("bbox")
            if finding.get("regions"):
                candidate["regions"] = finding["regions"]
            candidate["bbox_status"] = finding.get("bbox_status")
            candidate["visual_structure_evidence"] = finding.get("evidence")
            candidate["scan_transcription_status"] = finding.get("text_status")
            candidate["promotion_status"] = finding.get("promotion_status")
            if finding.get("verified_source_text") is not None:
                candidate["source_text"] = finding["verified_source_text"]
                candidate["source_text_basis"] = "page_specific_visual_transcription"
            if "continues_from_previous_page" in finding:
                candidate["continues_from_previous_page"] = bool(finding["continues_from_previous_page"])
            if "continues_to_next_page" in finding:
                candidate["continues_to_next_page"] = bool(finding["continues_to_next_page"])
            if candidate["bbox_status"] == "visually_measured":
                reviewed_regions += 1

    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates), encoding="utf-8")
    role_counts = Counter(row["structural_role"] for row in candidates)
    weak_rows = [row["candidate_id"] for row in located if row["match_coverage"] < 0.08]
    accepted_blocks = sum(row["promotion_status"] == "accepted" for row in candidates)
    rejected_duplicates = sum(row["promotion_status"] == "rejected_duplicate" for row in candidates)
    pending_blocks = sum(
        row.get("promotion_status") not in {"accepted", "rejected_duplicate"}
        for row in candidates
    )
    candidate_review_complete = (
        reviewed_regions == len(candidates)
        and not stale_review_bindings
        and pending_blocks == 0
        and accepted_blocks + rejected_duplicates == len(candidates)
    )
    audit = {
        "schema_version": "1.1",
        "status": "accepted_with_rejected_duplicates" if candidate_review_complete else "not_accepted",
        "method": "monotonic alignment of page OCR to structurally marked collation reference",
        "candidate_blocks": len(candidates),
        "pages": len(intervals),
        "visually_measured_blocks": reviewed_regions,
        "visually_accepted_blocks": accepted_blocks,
        "rejected_duplicate_blocks": rejected_duplicates,
        "pending_visual_review": pending_blocks,
        "role_counts": dict(role_counts),
        "weak_alignment_rows": weak_rows,
        "source_only_residual_rows": residual_rows,
        "possible_unaligned_rows": possible_unaligned_rows,
        "residual_decision_file": str(RESIDUAL_DECISIONS.relative_to(ROOT)).replace("\\", "/"),
        "stale_page_review_bindings": stale_review_bindings,
        "visually_locked_page_boundaries": sorted(boundary_records),
        "boundary_leading_source_only_fragments": [
            {
                "page": page,
                "text": record["leading_source_only_text"],
                "status": record.get("leading_source_only_status", "pending"),
            }
            for page, record in sorted(boundary_records.items())
            if record.get("leading_source_only_text")
        ],
        "boundary_source_specific_readings": [
            {
                "page": page,
                "visible_scan_text": record.get("visible_scan_text"),
                "scan_variant_for_anchor": record.get("scan_variant_for_anchor"),
                "following_source_only_text": record.get("following_source_only_text"),
                "status": record.get("source_specific_status", "recorded"),
            }
            for page, record in sorted(boundary_records.items())
            if record.get("scan_variant_for_anchor") or record.get("following_source_only_text")
        ],
        "reference_only_omissions": [
            {
                "id": omission["id"],
                "canonical_character_count": omit_end - omit_start,
                "canonical_sha256": hashlib.sha256(canonical[omit_start:omit_end].encode("utf-8")).hexdigest(),
                "status": omission["status"],
                "scan_page_before": omission["scan_page_before"],
                "scan_page_after": omission["scan_page_after"],
            }
            for omit_start, omit_end, omission in omission_ranges
        ],
        "structural_overrides_applied": applied_structural_overrides,
        "multi_region_blocks": sum(bool(row.get("regions")) for row in candidates),
        "prohibition": "Candidate blocks may not replace 20-source/blocks.jsonl until every block has a measured bbox and page-specific visual evidence.",
        "page_counts": {str(page): page_orders[page] for page in sorted(page_orders)},
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    worksheet = [
        "# 《郭璞葬经》逐页源块核验表",
        "",
        "> 本表是候选核验工具，不是通过记录。只有补齐真实 bbox、逐块核对原图并把状态改为 accepted，才可提升为正式源块。",
        "",
    ]
    for page in sorted(intervals):
        worksheet.extend([f"## 原书扫描第 {page} 页", "", f"![P{page:06d}](../20-source/pages/P{page:06d}.jpg)", ""])
        for row in (item for item in candidates if item["source_page"] == page):
            evidence = row.get("collated_text") or row.get("source_text") or ""
            worksheet.extend([
                f"- [ ] `{row['block_id']}` · `{row['component_id']}` · `{row['structural_role']}`",
                f"  - 候选文字：{evidence}",
                f"  - 原图区域：{row.get('bbox') if row.get('bbox') else '待测量'}",
                f"  - 核验结论：{row.get('promotion_status')}",
                "",
            ])
    WORKSHEET.write_text("\n".join(worksheet), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
