"""Shared read-only loaders for the gold-sample tools."""
import json
import re
from functools import lru_cache
from pathlib import Path

PROJECT = Path(r"D:\壮五福\风水项目")
OUTPUT = PROJECT / "output"
GOLD = PROJECT / "金标准样章"
DEFECTS = PROJECT / "缺陷库" / "defects.jsonl"

# current version of each book that has a reader text
WORKSPACES = {
    "001": "V4/001-青囊海角经",
    "002": "V4/002-入地眼全书",
    "003": "V4/003-平砂玉尺经-1.7",
    "004": "V4/004-郭璞葬经-1.8",
    "036": "V4/036-增释地理琢玉斧峦头歌括",
}
BOOK_NAMES = {"001": "青囊海角经", "002": "入地眼全书", "003": "平砂玉尺经", "004": "郭璞葬经", "036": "琢玉斧"}
CURRENT_VERSIONS = {"青囊海角经", "入地眼全书", "平砂玉尺经·1.7", "郭璞葬经", "琢玉斧·V4"}

GAP_RE = re.compile(r"具体所指不详|所指不详|含义不详|语义不明|意思不明|无法确定其含义|无法释读|语意不明|具体含义不详")


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


@lru_cache(None)
def defects():
    return read_jsonl(DEFECTS)


@lru_cache(None)
def blocks(book, layer="50-edited"):
    p = OUTPUT / WORKSPACES[book] / layer / "blocks.jsonl"
    return read_jsonl(p) if p.exists() else []


@lru_cache(None)
def source_blocks(book):
    return {b["block_id"]: b for b in blocks(book, "20-source")}


@lru_cache(None)
def reader_paragraphs(book):
    p = OUTPUT / WORKSPACES[book] / "60-publication" / "modern-reading.md"
    text = p.read_text(encoding="utf-8")
    paras = [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]
    return paras


def shingles(s, n=12):
    s = re.sub(r"[\s\W_]", "", s or "")
    return {s[i:i + n] for i in range(0, max(len(s) - n + 1, 0), 3)}


def locate_in_reader(book, modern_text):
    """Return (paragraph, index) of the published paragraph sharing most 12-char shingles with modern_text."""
    target = shingles(modern_text)
    if not target:
        return None, None
    best, best_i, best_n = None, None, 0
    for i, p in enumerate(reader_paragraphs(book)):
        if p.startswith(">") or p.startswith("#"):
            continue
        n = len(target & shingles(p))
        if n > best_n:
            best, best_i, best_n = p, i, n
    if best_n < max(2, len(target) // 5):
        return None, None
    return best, best_i
