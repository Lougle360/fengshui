#!/usr/bin/env python3
"""Render the accepted Book 003 manuscript as a searchable candidate PDF."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / "60-publication"
MARKDOWN = PUBLISH / "modern-reading.md"
CANDIDATE = PUBLISH / "candidates" / "平砂玉尺经·现代白话版-candidate.pdf"
REGULAR = Path(r"C:\Windows\Fonts\Deng.ttf")
BOLD = Path(r"C:\Windows\Fonts\Dengb.ttf")
PAGE_W, PAGE_H = 595.0, 842.0
LEFT, RIGHT, TOP, BOTTOM = 56.0, 52.0, 52.0, 54.0
BODY_W = PAGE_W - LEFT - RIGHT


def projected_line(line: str) -> str:
    if re.match(r"^!\[[^\]]*\]\([^)]+\)\s*$", line):
        return ""
    line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
    line = re.sub(r"^\s*[-*+]\s+", "", line)
    line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    line = re.sub(r"`([^`]+)`", r"\1", line)
    return line


def wrap(text: str, font: pymupdf.Font, size: float, width: float) -> list[str]:
    if not text:
        return []
    result, current = [], ""
    for char in text:
        trial = current + char
        if current and font.text_length(trial, fontsize=size) > width:
            result.append(current)
            current = char
        else:
            current = trial
    if current:
        result.append(current)
    return result


class Renderer:
    def __init__(self):
        self.doc = pymupdf.open()
        self.regular = pymupdf.Font(fontfile=str(REGULAR))
        self.bold = pymupdf.Font(fontfile=str(BOLD))
        self.page = None
        self.y = TOP
        self.page_no = -1
        self.heading_targets: dict[str, tuple[int, pymupdf.Point]] = {}
        self.toc_links: list[tuple[int, pymupdf.Rect, str]] = []
        self.toc_entries: list[tuple[int, str, int]] = []
        self.in_toc = False
        self.first_page = True
        self.new_page(cover=True)

    def new_page(self, cover: bool = False):
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.page_no += 1
        self.y = 92.0 if cover else TOP
        if cover:
            self.page.draw_rect(self.page.rect, color=(0.08, 0.18, 0.15), fill=(0.08, 0.18, 0.15), overlay=False)
            self.page.draw_rect(pymupdf.Rect(24, 24, PAGE_W - 24, PAGE_H - 24), color=(0.75, 0.62, 0.32), width=1.2)
        else:
            self.page.draw_rect(self.page.rect, color=(0.96, 0.94, 0.88), fill=(0.96, 0.94, 0.88), overlay=False)

    def ensure(self, height: float):
        if self.y + height > PAGE_H - BOTTOM:
            self.new_page()

    def draw_text(self, text: str, size: float, leading: float, bold: bool = False, color=(0.12, 0.12, 0.10), indent: float = 0, toc_target: str | None = None):
        font = self.bold if bold else self.regular
        available = BODY_W - indent
        lines = wrap(text, font, size, available)
        if not lines:
            self.y += leading * 0.45
            return None
        first_rect = None
        for value in lines:
            self.ensure(leading)
            origin = pymupdf.Point(LEFT + indent, self.y + size)
            self.page.insert_text(origin, value, fontname="DengBold" if bold else "Deng", fontfile=str(BOLD if bold else REGULAR), fontsize=size, color=color)
            width = font.text_length(value, fontsize=size)
            rect = pymupdf.Rect(origin.x, self.y, min(origin.x + width + 2, PAGE_W - RIGHT), self.y + leading)
            if first_rect is None:
                first_rect = rect
            if toc_target is not None:
                self.toc_links.append((self.page_no, rect, toc_target))
            self.y += leading
        self.y += leading * 0.25
        return first_rect

    def draw_image(self, relative: str):
        path = (PUBLISH / relative).resolve()
        pix = pymupdf.Pixmap(str(path))
        ratio = pix.height / max(pix.width, 1)
        width = min(BODY_W, 360.0)
        height = min(width * ratio, 330.0)
        width = min(width, height / ratio if ratio else width)
        self.ensure(height + 18)
        x0 = LEFT + (BODY_W - width) / 2
        rect = pymupdf.Rect(x0, self.y, x0 + width, self.y + height)
        self.page.insert_image(rect, filename=str(path), keep_proportion=True)
        self.page.draw_rect(rect, color=(0.55, 0.48, 0.35), width=0.5)
        self.y += height + 14

    def heading(self, level: int, heading: str):
        if level == 1:
            size, leading, color = 34.0, 48.0, (0.95, 0.88, 0.63)
        elif level == 2:
            if heading != "现代白话版":
                self.new_page()
            size, leading, color = 21.0, 31.0, (0.18, 0.28, 0.20)
            if self.page_no == 0:
                color = (0.92, 0.84, 0.58)
        elif level == 3:
            self.ensure(45)
            size, leading, color = 15.0, 23.0, (0.28, 0.38, 0.27)
        else:
            self.ensure(38)
            size, leading, color = 12.5, 20.0, (0.32, 0.35, 0.28)
        point = pymupdf.Point(LEFT, self.y)
        # Markdown can repeat a title later at a lower heading level.  Anchor
        # TOC links to the first occurrence, which is also the outline target.
        self.heading_targets.setdefault(heading, (self.page_no, point))
        self.toc_entries.append((level, heading, self.page_no + 1))
        self.draw_text(heading, size, leading, bold=True, color=color)
        self.in_toc = heading == "目录"

    def render(self, markdown: str):
        for raw in markdown.splitlines():
            image = re.match(r"^!\[[^\]]*\]\(([^)]+)\)\s*$", raw)
            if image:
                self.draw_image(image.group(1).strip())
                continue
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw)
            if heading:
                self.heading(len(heading.group(1)), heading.group(2))
                continue
            value = projected_line(raw)
            if not value:
                self.y += 5.0
                continue
            is_toc_link = self.in_toc and bool(re.match(r"^\s*[-*+]\s+\[", raw))
            target = value if is_toc_link else None
            cover = self.page_no == 0
            self.draw_text(value, 10.4 if not cover else 11.5, 17.2 if not cover else 20.0, color=(0.88, 0.88, 0.78) if cover else (0.12, 0.12, 0.10), indent=8 if raw.startswith("-") else 0, toc_target=target)

        outline = []
        for level, heading, page in self.toc_entries:
            if level <= 3:
                outline.append([level, heading, page])
        self.doc.set_toc(outline)
        for page_no, rect, target in self.toc_links:
            if target not in self.heading_targets:
                raise RuntimeError(f"TOC target missing: {target}")
            target_page, point = self.heading_targets[target]
            self.doc[page_no].insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": target_page, "to": point})

        CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
        self.doc.subset_fonts()
        self.doc.save(CANDIDATE, garbage=4, deflate=True)


def main() -> None:
    text = MARKDOWN.read_text(encoding="utf-8")
    renderer = Renderer()
    renderer.render(text)
    with pymupdf.open(CANDIDATE) as document:
        result = {"candidate": str(CANDIDATE), "pages": len(document), "bookmarks": len(document.get_toc()), "links": sum(len(page.get_links()) for page in document)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
