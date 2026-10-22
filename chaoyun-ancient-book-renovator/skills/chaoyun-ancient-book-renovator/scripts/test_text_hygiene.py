#!/usr/bin/env python3
"""Regression tests for text_hygiene.py, built from defects found in delivered books."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from text_hygiene import qian_as_gan, reader_text_issues, validate


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class QianAsGan(unittest.TestCase):
    def test_trigram_simplified_to_gan_is_caught(self):
        # 入地眼全书 P000011-B002
        self.assertTrue(qian_as_gan("若乾龍起祖由坤入午正出面結穴者", "如果干龙起祖，由坤入午正出面结穴"))
        # 入地眼全书 P000083-B004
        self.assertTrue(qian_as_gan("坎峯沛天秀入雲乾峯獨步黃金門", "坎峰沛天秀入云，干峰独步黄金门"))
        self.assertTrue(qian_as_gan("乾坤艮巽", "干、坤、艮、巽"))

    def test_kept_qian_passes(self):
        self.assertFalse(qian_as_gan("乾坤艮巽切莫逢", "乾坤艮巽切莫逢"))
        self.assertFalse(qian_as_gan("若乾龍起祖", "如果乾龙起祖"))

    def test_legitimate_gan_passes(self):
        self.assertFalse(qian_as_gan("十干行龍主不祥", "十干行龙主不祥"))
        self.assertFalse(qian_as_gan("大幹龍脉多近江河", "大干龙脉多靠近江河"))
        self.assertFalse(qian_as_gan("乾燥之地宜淺", "干燥的地方宜浅"))
        self.assertFalse(qian_as_gan("乾卦納甲，干支相配", "乾卦纳甲，干支相配"))


class ReaderText(unittest.TestCase):
    book = {"title": "入地眼全书", "running_header_patterns": ["李桂林"]}

    def test_running_header_in_body_is_caught(self):
        issues = reader_text_issues("入地眼全书卷五砂法八李辰砂法\n\n正文。\n", self.book)
        self.assertTrue(any("running header" in i for i in issues))
        issues = reader_text_issues("艮方阜立，贵入峰。入地眼全书卷五砂。\n", self.book)
        self.assertTrue(any("running header" in i for i in issues))
        issues = reader_text_issues("文中提到‘七李桂林郁’。\n", self.book)
        self.assertTrue(any("running header" in i for i in issues))

    def test_heading_and_plain_title_pass(self):
        self.assertEqual(reader_text_issues("## 入地眼全书卷五 砂法\n\n《入地眼全书》是清代风水书。\n", self.book), [])

    def test_pipeline_language_is_caught(self):
        text = "原文存在严重乱码或OCR识别错误，无法进行有效释读。\n"
        issues = reader_text_issues(text, self.book)
        self.assertEqual(len([i for i in issues if "pipeline" in i]), 4)


class StageGate(unittest.TestCase):
    def test_validate_reports_each_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(root / "20-source/blocks.jsonl", [{"block_id": "P000001-B001", "source_text": "乾龍起祖"}])
            write_jsonl(root / "30-normalized/blocks.jsonl", [{"block_id": "P000001-B001", "normalized_text": "干龙起祖"}])
            write_jsonl(root / "50-edited/blocks.jsonl", [{"block_id": "P000001-B001", "modern_text": "乾龙起祖。"}])
            issues = validate(root)
            self.assertEqual(len(issues), 1)
            self.assertIn("30-normalized", issues[0])


if __name__ == "__main__":
    unittest.main()
