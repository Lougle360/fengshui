#!/usr/bin/env python3
"""Dual-pass, resume-safe visual reconstruction for a bounded sample."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import requests


API_URL = "https://api.siliconflow.cn/v1/chat/completions"
TRANSCRIBER = "Qwen/Qwen3-VL-32B-Instruct"
JUDGE = "Qwen/Qwen3-VL-30B-A3B-Instruct"

TRANSCRIBE_PROMPT = """你是古籍影像转录员。只根据当前扫描页工作，禁止凭上下文补字。

页面为中文古籍竖排版，通常从右列向左列阅读，每列从上到下。请逐列检查。
1. 忠实转录所有可辨正文、题名、署名和图中文字，保留繁体与异体字。
2. 不确定但有候选字时写〔疑:字〕；完全不可辨写〔缺〕。不得把猜测写成确定文字。
3. 印章、馆藏号、手写页码与正文分开记录。
4. 跨页未完句只转录本页内容，不擅自补全。

只输出 JSON：
{"page_type":"text|image|mixed|blank","title":"","columns":[{"order":1,"text":""}],"source_text":"按阅读顺序合并的原文","nonbody_marks":[""],"uncertain_glyphs":[{"excerpt":"","reason":""}],"confidence":"high|medium|low"}
"""

JUDGE_PROMPT = """你是独立古籍校勘与今译审校员。请重新查看扫描图，不得默认候选转录正确。

任务：
1. 逐列核对候选转录；修正看图能够确认的错字。不能确认就保留〔疑:字〕或〔缺〕。
2. 给出 faithful_source_text：仍保持繁体原貌，不增补图中没有的文字。
3. 给出 normalized_text：只转简体、加标点、合理分段，不翻译、不改变意义。
4. 给出 modern_text：面向普通现代读者忠实翻译。跨页残句要与候选中提供的相邻页上下文衔接；证据不足时明确说“本页句子未完”，不要编造完整句。
5. 人名、书名、年代、数字、术语从严。不得把‘可能’写成事实，不得添加未经原文支持的历史年份换算。
6. 若候选与图像明显不符，verdict=revise；若本页无法可靠转录，verdict=unreadable。

只输出 JSON：
{"verdict":"accept|revise|unreadable","page_type":"text|image|mixed|blank","title":"","faithful_source_text":"","normalized_text":"","modern_text":"","uncertainties":[{"excerpt":"","reason":"","severity":"low|medium|high"}],"confidence":"high|medium|low","review_notes":[""]}
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("response has no JSON object")
        raw = match.group(0)
    value = json.loads(raw, strict=False)
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def data_url(image: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")


def call_model(key: str, model: str, image: bytes, prompt: str, max_tokens: int, timeout: int) -> tuple[dict, dict]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url(image)}},
            {"type": "text", "text": prompt},
        ]}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    error = None
    for attempt in range(1, 4):
        started = time.time()
        try:
            response = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return parse_json(content), {
                "model": model,
                "attempt": attempt,
                "elapsed_seconds": round(time.time() - started, 3),
                "usage": body.get("usage", {}),
            }
        except Exception as exc:
            error = exc
            if attempt < 3:
                time.sleep(3 * attempt)
    raise RuntimeError(f"{model} failed after retries: {error}")


def load_completed(path: Path) -> dict[int, dict]:
    completed: dict[int, dict] = {}
    if not path.is_file():
        return completed
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status") == "success":
            completed[int(row["source_page"])] = row
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=10)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--audit-suffix", default="")
    args = parser.parse_args()

    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise SystemExit("SILICONFLOW_API_KEY is unavailable")

    pages_dir = args.workspace / "20-source" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = args.workspace / "90-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.audit_suffix}" if args.audit_suffix else ""
    pass1_path = audit_dir / f"vision-pass1{suffix}.jsonl"
    pass2_path = audit_dir / f"vision-pass2{suffix}.jsonl"
    pass1_done = load_completed(pass1_path)
    pass2_done = load_completed(pass2_path)

    doc = pymupdf.open(args.pdf)
    if args.start < 1 or args.end > doc.page_count or args.start > args.end:
        raise SystemExit("invalid page range")

    with pass1_path.open("a", encoding="utf-8", newline="\n") as pass1_out, pass2_path.open("a", encoding="utf-8", newline="\n") as pass2_out:
        for source_page in range(args.start, args.end + 1):
            pix = doc[source_page - 1].get_pixmap(dpi=args.dpi, colorspace=pymupdf.csRGB)
            image = pix.tobytes("jpg", jpg_quality=94)
            image_path = pages_dir / f"P{source_page:06d}.jpg"
            if not image_path.exists():
                image_path.write_bytes(image)

            first = pass1_done.get(source_page)
            if first is None:
                result, meta = call_model(
                    key, TRANSCRIBER, image,
                    TRANSCRIBE_PROMPT + f"\n当前是原 PDF 第 {source_page} 页。",
                    3600, args.timeout,
                )
                first = {"schema_version": "1.0", "status": "success", "source_page": source_page,
                         "page_id": f"P{source_page:06d}", "source_image": f"20-source/pages/P{source_page:06d}.jpg",
                         "result": result, "request": meta, "generated_at": now()}
                pass1_out.write(json.dumps(first, ensure_ascii=False) + "\n")
                pass1_out.flush()

            if source_page in pass2_done:
                print(f"page {source_page}: already judged", flush=True)
                continue
            candidate = first["result"]
            prev_text = pass2_done.get(source_page - 1, {}).get("result", {}).get("faithful_source_text", "")
            prompt = (
                JUDGE_PROMPT
                + f"\n当前是原 PDF 第 {source_page} 页。"
                + "\n候选转录如下，仅供核对，不是事实：\n"
                + json.dumps(candidate, ensure_ascii=False)
            )
            if prev_text:
                prompt += "\n上一页经复核的末文如下，仅用于判断跨页续接，不得补入本页：\n" + prev_text[-300:]
            result, meta = call_model(key, JUDGE, image, prompt, 4200, args.timeout)
            second = {"schema_version": "1.0", "status": "success", "source_page": source_page,
                      "page_id": f"P{source_page:06d}", "source_image": f"20-source/pages/P{source_page:06d}.jpg",
                      "candidate_model": TRANSCRIBER, "result": result, "request": meta, "generated_at": now()}
            pass2_out.write(json.dumps(second, ensure_ascii=False) + "\n")
            pass2_out.flush()
            pass2_done[source_page] = second
            print(f"page {source_page}: {result.get('verdict')} {result.get('confidence')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
