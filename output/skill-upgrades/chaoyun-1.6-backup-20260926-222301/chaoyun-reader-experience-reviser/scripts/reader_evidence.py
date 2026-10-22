"""Content-bound evidence checks shared by reader and publication gates.

These checks verify artifacts and coverage, not the truth of a reviewer's judgment.
"""
import hashlib
import re
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("evidence path must be workspace-relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing or escaping evidence path: {relative}")
    return path


def snapshot(root, record, prefix):
    path = local_file(root, record.get(prefix + "_snapshot"))
    if sha256(path) != record.get(prefix + "_sha256"):
        raise ValueError(f"{prefix} snapshot hash mismatch")
    return path.read_text(encoding="utf-8")


def sections(text):
    """Partition every line, including pre-heading material; ignore fenced headings."""
    lines = text.splitlines()
    starts = [1] if lines else []
    fence = None
    for number, line in enumerate(lines, 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
            continue
        if fence is None and re.match(r"^#{1,6}\s+\S", line) and number not in starts:
            starts.append(number)
    return [(start, end - 1) for start, end in zip(starts, starts[1:] + [len(lines) + 1])]


def check_chapters(text, records, source_ids):
    errors = []
    if not isinstance(records, list) or not records:
        return ["section-level reader evidence is required"]
    actual = [(row.get("start_line"), row.get("end_line")) for row in records if isinstance(row, dict)]
    if actual != sections(text):
        errors.append("section review does not cover every manuscript section in order")
    lines = text.splitlines()
    covered = set()
    for row in records:
        if not isinstance(row, dict):
            errors.append("section review must be an object")
            continue
        start, end = row.get("start_line"), row.get("end_line")
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            errors.append("invalid section review range")
            continue
        excerpt = "\n".join(lines[start - 1:end])
        if row.get("text_sha256") != hashlib.sha256(excerpt.encode("utf-8")).hexdigest():
            errors.append("section review text hash mismatch")
        if not row.get("quote") or row["quote"] not in excerpt:
            errors.append("section review quote is absent from the section")
        for key in ("reader_question", "plain_answer", "prerequisites", "comprehension_evidence"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                errors.append(f"section review requires {key}")
        if row.get("status") != "passed" or row.get("remaining_obstacles") != []:
            errors.append("section review has unresolved reading obstacles")
        ids = row.get("block_ids")
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            errors.append("section review requires block_ids list")
        else:
            covered.update(ids)
    if covered != source_ids:
        errors.append("section review source coverage differs from source block inventory")
    return errors
