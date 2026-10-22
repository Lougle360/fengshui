#!/usr/bin/env python3
"""Edit page-level translations into fluent chapter-continuous reader prose."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "50-edited" / "blocks.jsonl"
OUTPUT = ROOT / "90-audit" / "reader-chapter-edits-122b.jsonl"
MODEL = "Qwen/Qwen3.5-122B-A10B"
GROUPS = [(3, 10), (11, 17), (18, 22), (23, 42), (43, 50), (51, 58), (59, 65), (66, 72), (73, 80)]


def call_model(key: str, prompt: str) -> dict:
    error = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                "https://api.siliconflow.cn/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.15, "max_tokens": 8000, "response_format": {"type": "json_object"}},
                timeout=300,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end < start:
                raise RuntimeError("response has no JSON object")
            return json.loads(text[start:end + 1])
        except Exception as exc:
            error = exc
            if attempt < 3:
                time.sleep(attempt * 3)
    raise RuntimeError(f"model failed after retries: {error}")


def main() -> int:
    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise SystemExit("SILICONFLOW_API_KEY is unavailable")
    rows = [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_page = {int(row["source_page"]): row for row in rows}
    saved = {}
    if OUTPUT.exists():
        for line in OUTPUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                saved[int(row["source_page"])] = row

    def edit(group: tuple[int, int]) -> list[dict]:
        start, end = group
        material = []
        for page in range(start, end + 1):
            row = by_page[page]
            material.append({"page": page, "source": row.get("normalized_text", ""),
                             "draft": row.get("modern_text", ""), "block_type": row.get("block_type", "body")})
        prompt = """你是面向普通读者的古籍现代白话编辑。请把以下连续页面编辑成自然、准确、可直接阅读的现代简体中文。

规则：
1. 严格输出 JSON：{\"pages\":[{\"page\":3,\"modern_text\":\"...\"}]}，页码和输入完全一致，不增不减。
2. 只输出现代白话，不输出原文、校勘说明、OCR、置信度、页码说明或制作过程。
3. 全部使用简体中文和现代标点；消除生硬直译、繁体残留、断句错误和重复。
4. 相邻页的半句话要结合上下文接顺。可以在相邻页面之间重新分配语句，但每页 modern_text 必须非空。
5. 保留原意、专名、数字和术语；术语首次出现时用短括号解释。不能凭常识增加原文没有的事实。
6. 图解页用一至三句解释图的用途和主要标签，不臆测吉凶结论。
7. 对残损且不能可靠理解的局部，省略残字并保留可确定的主旨；不要显示缺字符号。
8. 目录、题名和参与校订人名单压缩成简洁出版说明，不要把人名堆成正文。

连续页面材料：
""" + json.dumps(material, ensure_ascii=False)
        result = call_model(key, prompt)
        edited = result.get("pages") or []
        expected = list(range(start, end + 1))
        actual = [int(x.get("page", -1)) for x in edited]
        if actual != expected or any(not str(x.get("modern_text", "")).strip() for x in edited):
            raise RuntimeError(f"invalid page coverage for {start}-{end}: {actual}")
        return [{"schema_version": "1.0", "status": "success", "group": [start, end],
                 "source_page": int(x["page"]), "page_id": f"P{int(x['page']):06d}",
                 "model": MODEL, "modern_text": str(x["modern_text"]).strip()} for x in edited]

    pending_groups = [group for group in GROUPS if not all(page in saved for page in range(group[0], group[1] + 1))]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(edit, group): group for group in pending_groups}
        for future in as_completed(futures):
            group = futures[future]
            result = future.result()
            for row in result:
                saved[int(row["source_page"])] = row
            OUTPUT.write_text("".join(json.dumps(saved[p], ensure_ascii=False) + "\n" for p in sorted(saved)), encoding="utf-8")
            print(f"group {group[0]}-{group[1]}: {len(result)} pages", flush=True)
    print(json.dumps({"pages": len(saved), "groups": len(GROUPS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
