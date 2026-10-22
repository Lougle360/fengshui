#!/usr/bin/env python3
"""Validate reader-facing introduction and glossary evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


INTRO_KEYS = {
    "what_this_book_is", "who_should_read", "reader_value", "contents_and_structure",
    "distinctive_features", "historical_and_textual_context", "how_to_read",
    "limitations_and_cautions", "edition_method",
}
TIERS = {"core", "supporting", "opaque"}
CONFIDENCE = {"confirmed", "qualified", "unresolved"}


def section_text(markdown: str, heading: str) -> str:
    """Return one exact heading's section; duplicate headings are ambiguous."""
    matches = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown, re.M))
    targets = [i for i, match in enumerate(matches) if match[2] == heading]
    if len(targets) != 1:
        return ""
    index = targets[0]
    start = matches[index]
    end = next((m.start() for m in matches[index + 1:] if len(m[1]) <= len(start[1])), len(markdown))
    return markdown[start.end():end]


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(root: Path, markdown_relative: str = "50-edited/modern-reading.md") -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    aids_path = root / "50-edited/reader-aids.json"
    markdown_path = root / markdown_relative
    if not aids_path.is_file():
        return ["ordinary-reader edition requires 50-edited/reader-aids.json"], {}
    try:
        aids = load_json(aids_path)
        source_rows = load_jsonl(root / "20-source/blocks.jsonl")
        markdown = markdown_path.read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid reader-value evidence: {exc}"], {}

    source = {row.get("block_id"): row for row in source_rows if row.get("block_id")}
    intro = aids.get("introduction") if isinstance(aids.get("introduction"), dict) else {}
    sections = intro.get("sections") if isinstance(intro.get("sections"), dict) else {}
    for key in sorted(INTRO_KEYS):
        if not str(sections.get(key) or "").strip():
            errors.append(f"reader introduction missing substantive section {key}")
    intro_heading = str(intro.get("markdown_heading") or "").strip()
    introduction_text = section_text(markdown, intro_heading)
    if not intro_heading or not introduction_text:
        errors.append(f"reader introduction heading is not present in {markdown_relative}")
    for key, value in sections.items():
        if not isinstance(value, str) or not value.strip() or value.strip() not in introduction_text:
            errors.append(f"introduction section {key} is not rendered in the introduction")
    evidence = intro.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("reader introduction requires claim-level evidence")
    else:
        for index, item in enumerate(evidence, 1):
            if not isinstance(item, dict) or not str(item.get("claim") or "").strip():
                errors.append(f"introduction evidence {index} requires a claim")
                continue
            block_ids = item.get("block_ids") or []
            pages = item.get("source_pages") or []
            editorial_sources = item.get("editorial_sources") or []
            if not block_ids and not pages and not editorial_sources:
                errors.append(f"introduction evidence {index} has no source reference")
            unknown = sorted(set(block_ids) - set(source))
            if unknown:
                errors.append(f"introduction evidence {index} references unknown blocks {unknown}")
            if any(page not in {row.get('source_page') for row in source_rows} for page in pages):
                errors.append(f"introduction evidence {index} references unknown source pages")

    glossary = aids.get("glossary") if isinstance(aids.get("glossary"), dict) else {}
    compact_final = glossary.get("rendering_profile") == "compact_final_reader"
    entries = glossary.get("entries") if isinstance(glossary.get("entries"), list) else []
    if not entries:
        errors.append("reader glossary requires structured entries")
    glossary_heading = str(glossary.get("markdown_heading") or "").strip()
    glossary_text = section_text(markdown, glossary_heading)
    if not glossary_heading or not glossary_text:
        errors.append(f"reader glossary heading is not present in {markdown_relative}")
    terms: set[str] = set()
    core_terms: set[str] = set()
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            errors.append(f"glossary entry {index} must be an object")
            continue
        term = str(entry.get("term") or "").strip()
        if not term or term in terms:
            errors.append(f"glossary entry {index} has missing or duplicate term {term!r}")
            continue
        terms.add(term)
        tier = entry.get("tier")
        if tier not in TIERS:
            errors.append(f"glossary term {term} has invalid tier")
        if tier == "core":
            core_terms.add(term)
        if entry.get("confidence") not in CONFIDENCE:
            errors.append(f"glossary term {term} has invalid confidence")
        plain = str(entry.get("plain_definition") or "").strip()
        contextual = str(entry.get("contextual_definition") or "").strip()
        if not plain or not contextual or plain == contextual:
            errors.append(f"glossary term {term} requires distinct plain and contextual definitions")
        occurrence = entry.get("first_occurrence") if isinstance(entry.get("first_occurrence"), dict) else {}
        block_id = occurrence.get("block_id")
        row = source.get(block_id)
        if row is None:
            errors.append(f"glossary term {term} references unknown first-occurrence block")
        else:
            if occurrence.get("page_id") != row.get("page_id") or occurrence.get("source_page") != row.get("source_page"):
                errors.append(f"glossary term {term} first-occurrence location disagrees with source block")
            quote = str(occurrence.get("quote") or "").strip()
            source_text = str(row.get("source_text") or "")
            if not quote or quote not in source_text:
                errors.append(f"glossary term {term} first-occurrence quote is not in source block")
            forms = [term, *[str(value) for value in entry.get("aliases") or []]]
            if not any(form and form in quote for form in forms):
                errors.append(f"glossary term {term} or an alias is absent from its occurrence quote")
        if tier == "core":
            if not str(entry.get("usage_example") or "").strip():
                errors.append(f"core glossary term {term} requires a usage example")
            example = str(entry.get('usage_example') or '').strip()
            confusion = str(entry.get('common_confusions') or '').strip()
            if '按本书语境理解' in example and example.startswith('阅读'):
                errors.append(f"core glossary term {term} uses a context reminder instead of an explained example")
            if '只按日常词义理解' in confusion and '特定的方位或形势关系' in confusion:
                errors.append(f"core glossary term {term} uses generic confusion guidance")
            if not entry.get("related_terms"):
                errors.append(f"core glossary term {term} requires related terms")
            if not str(entry.get("common_confusions") or "").strip():
                errors.append(f"core glossary term {term} requires common-confusion guidance")
        # The process/guide edition may use one heading per term.  The final-reader
        # profile intentionally renders a compact bold-label glossary so internal
        # database fields do not swamp the reading edition.
        if compact_final:
            entry_text = ""
            for match in re.finditer(r"^\*\*([^*]+)\*\*\s*(.+)$", glossary_text, re.M):
                labels = [value.strip() for value in re.split(r"[、；;]", match.group(1)) if value.strip()]
                candidate = match.group(0)
                if (term in labels or term == match.group(1).strip()) and plain in candidate and contextual in candidate:
                    entry_text = candidate
                    break
        else:
            entry_text = section_text(glossary_text, term)
        fields = ["plain_definition", "contextual_definition"]
        if tier == "core":
            fields += ["usage_example", "common_confusions"]
        for field in fields:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip() or value.strip() not in entry_text:
                errors.append(f"glossary term {term} field {field} is not rendered in its entry")
        if tier == "core" and any(str(related) not in entry_text for related in entry.get("related_terms") or []):
            errors.append(f"glossary term {term} related terms are not rendered")
        if term not in glossary_text:
            errors.append(f"glossary term {term} is absent from {markdown_relative}")

    inventory_path = root / "40-modernized/terminology.json"
    # A title/contents match is not a substantive term occurrence. This check
    # catches explicit heading records; the reviewer must still judge prose uses.
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        occurrence = entry.get('first_occurrence') or {}
        row = source.get(occurrence.get('block_id'), {}) if isinstance(occurrence, dict) else {}
        if row.get('block_type') in {'title', 'heading', 'toc', 'running_header'}:
            errors.append(f"glossary term {entry.get('term')} needs a substantive occurrence, not a heading/title")
    inventory_terms: set[str] = set()
    if not inventory_path.is_file():
        errors.append("required terminology inventory is missing")
    if inventory_path.is_file():
        try:
            inventory = load_json(inventory_path)
            inventory_terms = {
                str(row.get("term")) for row in inventory.get("terms", [])
                if isinstance(row, dict) and row.get("term")
            }
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid terminology inventory: {exc}")
    excluded_rows = glossary.get("excluded_inventory_terms") or []
    excluded = {
        str(row.get("term")) for row in excluded_rows
        if isinstance(row, dict) and row.get("term") and str(row.get("reason") or "").strip()
    }
    missing_inventory = sorted(inventory_terms - terms - excluded)
    if missing_inventory:
        errors.append(f"terminology inventory is not fully adjudicated for readers: {missing_inventory}")

    counts = {
        "introduction_sections": len([key for key in INTRO_KEYS if str(sections.get(key) or "").strip()]),
        "glossary_entries": len(terms),
        "glossary_core": len(core_terms),
        "glossary_with_first_occurrence": sum(1 for entry in entries if isinstance(entry, dict) and isinstance(entry.get("first_occurrence"), dict) and entry["first_occurrence"].get("block_id") in source),
    }
    return errors, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    errors, counts = validate(root)
    print(json.dumps({"valid": not errors, "counts": counts, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
