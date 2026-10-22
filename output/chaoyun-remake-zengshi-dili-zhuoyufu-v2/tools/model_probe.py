#!/usr/bin/env python3
"""Probe one vision model on one rendered page without modifying stage records."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("model")
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise SystemExit("SILICONFLOW_API_KEY is unavailable")
    encoded = base64.b64encode(args.image.read_bytes()).decode("ascii")
    prompt = (
        "这是一页中文古籍竖排扫描图。请从最右列到最左列、每列从上到下，逐字忠实转录全部正文。"
        "不要翻译，不要释义，不要补字，不要把模糊字按上下文猜成通顺句。"
        "请先输出逐列转录，再输出按阅读顺序合并的全文；无法辨认写〔缺〕，不确定写〔疑:候选〕。"
    )
    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": args.model,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}},
                {"type": "text", "text": prompt},
            ]}],
            "temperature": 0,
            "max_tokens": 2200,
        },
        timeout=args.timeout,
    )
    response.raise_for_status()
    body = response.json()
    result = {
        "model": args.model,
        "image": str(args.image),
        "content": body["choices"][0]["message"]["content"],
        "usage": body.get("usage", {}),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
