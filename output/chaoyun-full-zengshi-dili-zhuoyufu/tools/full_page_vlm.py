#!/usr/bin/env python3
"""Resume-safe full-page visual transcription and modern Chinese rendering."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import requests


API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "Qwen/Qwen3-VL-32B-Instruct"
PROMPT = """你是古籍整理专家。请只根据当前这一页扫描图工作，不要根据常识补字。

任务分成互相独立的证据层和阅读层：
1. source_text：按竖排古籍真实阅读顺序，忠实抄录本页能够辨认的繁体原文。保留原字、异体字和原有标题；看不清处写〔缺字〕，禁止猜字。印章、馆藏编号、页码若明显不属正文，不混入正文。
2. normalized_text：在不改变含义的前提下，转为简体、补现代标点并合理分段。无法确认的字仍保留〔缺字〕。
3. modern_text：面向现代普通读者翻译为清楚的现代白话文。风水术语可保留，并在首次出现时用很短的括注解释。不得添加原文没有的事实、结论或科学有效性判断。
4. uncertainty：逐项列出所有看不清、断句歧义、图中文字或不能可靠翻译之处。不要为了流畅隐藏问题。
5. 图版页优先说明 page_type=image 或 mixed；能辨认的图题、图签写入 source_text，图形含义只做保守说明。

只输出一个完整 JSON 对象，字段必须齐全：
{"page_type":"text|image|mixed|blank","title":"本页标题或空字符串","source_text":"繁体忠实转录或空字符串","normalized_text":"简体标点版或空字符串","modern_text":"现代白话或空字符串","uncertainty":[{"excerpt":"疑难片段","reason":"直接原因"}],"confidence":"high|medium|low"}

不要输出 Markdown 围栏、解释、前后缀。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_object(content: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.S)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError("response has no complete JSON object")
        raw = match.group(0)
    return json.loads(raw, strict=False)


def validate(value: dict) -> dict:
    required = {
        "page_type",
        "title",
        "source_text",
        "normalized_text",
        "modern_text",
        "uncertainty",
        "confidence",
    }
    missing = required - set(value)
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if value["page_type"] not in {"text", "image", "mixed", "blank"}:
        raise ValueError("invalid page_type")
    if value["confidence"] not in {"high", "medium", "low"}:
        raise ValueError("invalid confidence")
    for key in ("title", "source_text", "normalized_text", "modern_text"):
        if not isinstance(value[key], str):
            raise ValueError(f"{key} is not a string")
        value[key] = value[key].strip()
    if not isinstance(value["uncertainty"], list):
        raise ValueError("uncertainty is not a list")
    cleaned: list[dict[str, str]] = []
    for item in value["uncertainty"]:
        if isinstance(item, dict):
            excerpt = str(item.get("excerpt", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if excerpt or reason:
                cleaned.append({"excerpt": excerpt, "reason": reason})
    value["uncertainty"] = cleaned
    if value["page_type"] in {"text", "mixed"} and not value["source_text"]:
        raise ValueError("text page omitted source_text")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("pages_dir", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--proof-jsonl", type=Path)
    parser.add_argument("--judge-jsonl", type=Path)
    args = parser.parse_args()

    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise SystemExit("SILICONFLOW_API_KEY is unavailable")

    trusted_by_page: dict[int, list[str]] = {}
    if args.proof_jsonl and args.judge_jsonl:
        proof_by_page: dict[int, dict] = {}
        for line in args.proof_jsonl.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("status") == "success":
                proof_by_page[int(row["source_page"])] = row
        for line in args.judge_jsonl.read_text(encoding="utf-8").splitlines():
            judged = json.loads(line)
            if judged.get("status") != "success":
                continue
            source_page = int(judged["source_page"])
            proof = proof_by_page.get(source_page, {})
            corrections = proof.get("corrections") or []
            accepted: list[str] = []
            for decision in judged.get("decisions") or []:
                index = int(decision.get("id", -1))
                if not 0 <= index < len(corrections):
                    continue
                correction = corrections[index]
                if (
                    decision.get("decision") == "accept"
                    and decision.get("confidence") == "high"
                    and correction.get("confidence") == "high"
                    and str(correction.get("fix", "")).strip()
                ):
                    accepted.append(str(correction["fix"]).strip())
            if accepted:
                trusted_by_page[source_page] = accepted

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.pages_dir.mkdir(parents=True, exist_ok=True)
    completed: dict[int, dict] = {}
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("status") == "success":
                    completed[int(row["source_page"])] = row
            except Exception:
                continue

    document = pymupdf.open(args.pdf)
    page_count = document.page_count
    pending = [page for page in range(1, page_count + 1) if page not in completed]
    doc_lock = threading.Lock()
    write_lock = threading.Lock()
    out = args.output.open("a", encoding="utf-8", newline="\n")

    def process(source_page: int) -> dict:
        started = time.time()
        with doc_lock:
            pix = document[source_page - 1].get_pixmap(dpi=args.dpi, colorspace=pymupdf.csRGB)
            image = pix.tobytes("jpg", jpg_quality=90)
        image_path = args.pages_dir / f"P{source_page:06d}.jpg"
        if not image_path.exists():
            image_path.write_bytes(image)
        encoded = base64.b64encode(image).decode("ascii")
        trusted = trusted_by_page.get(source_page, [])
        evidence_note = ""
        if trusted:
            evidence_note = (
                "\n\n以下片段来自此前两轮独立看图复核，均被判定为 high-confidence accept。"
                "它们只是局部字词证据，仍须与本页图像核对，不得据此补出图中不存在的内容：\n"
                + "\n".join(f"- {item}" for item in trusted)[:2400]
            )
        page_prompt = PROMPT + f"\n\n当前为原 PDF 第 {source_page} 页。" + evidence_note
        base_content = [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}},
            {"type": "text", "text": page_prompt},
        ]
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": base_content}],
            "temperature": 0,
            "max_tokens": args.max_tokens,
        }
        last_error = "unknown"
        for attempt in range(1, 6):
            try:
                request_payload = payload
                if attempt > 1:
                    repair = (
                        page_prompt
                        + "\n\n上一轮没有返回合格 JSON。"
                        + "本轮必须返回字段齐全、使用英文双引号并完整闭合的单个 JSON 对象。"
                    )
                    request_payload = {
                        **payload,
                        "messages": [{
                            "role": "user",
                            "content": [base_content[0], {"type": "text", "text": repair}],
                        }],
                    }
                response = requests.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    json=request_payload,
                    timeout=120,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(f"HTTP {response.status_code}")
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                data = validate(parse_object(content))
                return {
                    "schema_version": "1.0",
                    "source_page": source_page,
                    "page_id": f"P{source_page:06d}",
                    "source_image": f"20-source/pages/P{source_page:06d}.jpg",
                    "status": "success",
                    "model": MODEL,
                    **data,
                    "usage": body.get("usage", {}),
                    "attempts": attempt,
                    "elapsed_seconds": round(time.time() - started, 3),
                    "generated_at": utc_now(),
                }
            except Exception as exc:
                last_error = repr(exc)[:600]
                time.sleep(min(30, 4 * attempt))
        return {
            "schema_version": "1.0",
            "source_page": source_page,
            "page_id": f"P{source_page:06d}",
            "source_image": f"20-source/pages/P{source_page:06d}.jpg",
            "status": "failed",
            "model": MODEL,
            "error": last_error,
            "elapsed_seconds": round(time.time() - started, 3),
            "generated_at": utc_now(),
        }

    counts: Counter[str] = Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(process, page): page for page in pending}
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            row = future.result()
            counts[row["status"]] += 1
            with write_lock:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
            if done % 5 == 0 or row["status"] == "failed":
                print(
                    f"pages {done}/{len(pending)} source={row['source_page']} "
                    f"status={row['status']} elapsed={time.time()-started:.0f}s",
                    flush=True,
                )
    out.close()
    document.close()

    latest: dict[int, dict] = {}
    for line in args.output.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        latest[int(row["source_page"])] = row
    usage: Counter[str] = Counter()
    for row in latest.values():
        for name, value in (row.get("usage") or {}).items():
            if isinstance(value, int):
                usage[name] += value
    status = {
        "generated_at": utc_now(),
        "model": MODEL,
        "pages_total": page_count,
        "pages_recorded": len(latest),
        "status_counts": dict(Counter(row.get("status") for row in latest.values())),
        "usage": dict(usage),
        "complete": len(latest) == page_count and all(row.get("status") == "success" for row in latest.values()),
    }
    status_path = args.output.with_suffix(".status.json")
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2), flush=True)
    return 0 if status["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
