#!/usr/bin/env python3
"""Rule checks for defects that no reader edition may contain.

Three checks, shared by the stage gate (validate_workspace.py) and the publication audit:

- 乾 (the trigram / direction, qián) must not be simplified to 干.
- Running headers (book title + 卷 number, carver names, library stamps) must not enter reader text.
- Internal pipeline language (OCR, 识别错误, 释读, model / repair status) must not enter reader text.

usage: python text_hygiene.py <book-workspace>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 乾 read as gān (dry) legitimately simplifies to 干.
QIAN_DRY = re.compile(r"乾(?=[燥枯涸旱淨净脆])")
# 干 used as a trigram or direction: next to compass / trigram / stem characters or feng-shui nouns.
DIRECTIONAL_GAN = re.compile(
    r"(?<![天主树枝躯骨若相])干(?![支燥涸枯旱净脆])"
    r"(?=[卦宫龙山峰方位向穴水砂坤艮巽坎离震兑亥甲壬子癸戌、])"
    r"|(?<=[坤艮巽坎离震兑亥甲壬戌])、?干(?![支燥涸枯旱净脆])"
)

PIPELINE_LANGUAGE = (
    "OCR",
    "识别错误",
    "识别有误",
    "乱码",
    "无法进行有效释读",
    "释读存疑",
    "核义模型",
    "自动修复",
    "保守记录",
    "硬校验",
    "已记录供后续",
)

STAGE_TEXT_FIELDS = {
    "30-normalized/blocks.jsonl": "normalized_text",
    "40-modernized/blocks.jsonl": "modern_text",
    "50-edited/blocks.jsonl": "modern_text",
}


def qian_kept(source_text: str) -> int:
    return source_text.count("乾") - len(QIAN_DRY.findall(source_text))


def qian_as_gan(source_text: str, target_text: str) -> list[str]:
    """Contexts where a 乾 of the source appears as 干 in the target."""
    expected = qian_kept(source_text or "")
    target = target_text or ""
    if expected <= 0 or target.count("乾") >= expected:
        return []
    return [target[max(0, m.start() - 4):m.end() + 4] for m in DIRECTIONAL_GAN.finditer(target)]


def running_header_patterns(book: dict) -> list[re.Pattern]:
    patterns = []
    title = str(book.get("title") or "").strip()
    if title:
        patterns.append(re.compile(re.escape(title) + r"\s*卷\s*[一二三四五六七八九十〇百]+"))
    for extra in book.get("running_header_patterns") or []:
        patterns.append(re.compile(str(extra)))
    return patterns


def reader_text_issues(text: str, book: dict) -> list[str]:
    """Pipeline language anywhere, running headers outside heading lines."""
    issues = []
    for term in PIPELINE_LANGUAGE:
        count = text.count(term)
        if count:
            issues.append(f"internal pipeline language in reader text: {term!r} ({count})")
    headers = running_header_patterns(book)
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        for pattern in headers:
            match = pattern.search(stripped)
            if match:
                issues.append(f"running header leaked into reader text at line {number}: {match.group(0)!r}")
                break
    return issues


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stage_qian_issues(root: Path, stage_file: str) -> list[str]:
    """乾→干 per block of one stage, compared with 20-source."""
    path = root / stage_file
    source_path = root / "20-source/blocks.jsonl"
    if not path.is_file() or not source_path.is_file():
        return []
    sources = {row.get("block_id"): row.get("source_text") or "" for row in read_jsonl(source_path)}
    field = STAGE_TEXT_FIELDS[stage_file]
    issues = []
    for row in read_jsonl(path):
        hits = qian_as_gan(sources.get(row.get("block_id"), ""), row.get(field) or "")
        if hits:
            issues.append(f"{stage_file} {row.get('block_id')}: 乾 simplified to 干: {', '.join(hits[:3])}")
    return issues


def validate(root: Path, stages: tuple[str, ...] = tuple(STAGE_TEXT_FIELDS), reader: bool = True) -> list[str]:
    root = Path(root)
    issues = []
    for stage_file in stages:
        issues.extend(stage_qian_issues(root, stage_file))
    reader_md = root / "60-publication/modern-reading.md"
    if reader and reader_md.is_file():
        book_path = root / "book.json"
        book = json.loads(book_path.read_text(encoding="utf-8")) if book_path.is_file() else {}
        issues.extend(reader_text_issues(reader_md.read_text(encoding="utf-8"), book))
    return issues


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    issues = validate(Path(sys.argv[1]))
    print(json.dumps({"valid": not issues, "issue_count": len(issues), "issues": issues},
                     ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
