"""Create a cached, source-bound final-reader rewrite of every book block."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "40-modernized/blocks.jsonl"
OUTDIR = ROOT / "40-modernized/final-reader-pages"
OUTFILE = ROOT / "40-modernized/final-reader-blocks.jsonl"
REPORT = ROOT / "40-modernized/final-reader-report.json"
URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
WRITER = "doubao-seed-2-0-pro-260215"
JUDGE = "doubao-seed-2-0-pro-260215"
FALLBACK = "Qwen/Qwen3.5-122B-A10B"

WRITER_SYSTEM = """你是《平砂玉尺经》的古文今译编辑。你收到同一物理页的逐块原文、已有译文及相邻上下文。请逐块写成现代普通读者能够连续阅读的自然简体白话文。

硬规则：
1. 忠实保留人名、地名、方位、干支、数量、条件、否定、因果和术语；不得凭常识补原文没有的事实。
2. 原文有缺损、讹字或词义不明时，只翻译能够确定的部分，并在句内用“原文此处有缺损，具体含义不详”等自然短语说明；不得猜补。
3. 传统吉凶、福祸、人物品性等判断，用“书中认为”“按书中的说法”等措辞明确归属于原书，但同一连续段落不要机械重复。
4. 必须使用简体中文。不要保留整段文言，不要写导读、讲解步骤、编辑过程、页码、卷页标、OCR、模型或审核信息。正文块末尾夹入的“玉尺经/尺经+卷次+数字”等版刻书眉、卷次、页码一律静默删除，不得写“已保留相关信息”之类说明；只有本身就是书名或篇名的独立短标题块才保留。
5. 标题、短题署和无法展开的短标签可以简洁保留；正文必须是完整、顺畅、说人话的白话文。
6. 不合并、不拆分、不遗漏 block_id。只输出 JSON 对象，不输出 Markdown。
7. 如果整句损坏到无法翻译，不要把乱码原句抄给读者，改写为“此处原文残缺，只能辨认出与……有关，无法确译”；能够确定多少就只写多少。

输出格式：{"blocks":[{"block_id":"...","text":"...","uncertain":false,"note":""}]}。"""

JUDGE_SYSTEM = """你是独立的古文今译终审。逐块比较规范化原文和候选白话文。检查遗漏、擅加、条件或否定颠倒、数字与专名错误、把疑文写确定、整段文言或繁体残留，以及不自然的AI腔。

你必须直接给出可用终稿：候选合格则原样返回；不合格则在不增加原意的前提下修正。传统吉凶预测需归属于原书，疑损必须保留边界。不得加入审核说明、导读、卷页标、页码，也不得把正文块末尾的“玉尺经/尺经+卷次+数字”等版刻杂项解释给读者。整句已坏时用自然的残缺说明，不照抄乱码。

只输出 JSON：{"blocks":[{"block_id":"...","text":"...","verdict":"passed|corrected","issues":[]}]}。ID必须与输入完全相同、顺序完全相同。"""

def read_rows():
    return [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines() if line.strip()]

def request(model: str, system: str, payload: dict, max_tokens: int = 8000):
    key = os.getenv("ARK_API_KEY")
    if not key:
        raise RuntimeError("进程环境缺少 ARK_API_KEY")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        "temperature": 0.05,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    error = None
    for attempt in range(3):
        try:
            response = requests.post(URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=(30, 240))
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300].replace(key, '[REDACTED]')}")
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content), data.get("usage") or {}
        except (requests.RequestException, RuntimeError, KeyError, json.JSONDecodeError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(str(error))

def request_fallback(system: str, payload: dict, max_tokens: int = 7000):
    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise RuntimeError("进程环境缺少 SILICONFLOW_API_KEY")
    body = {"model": FALLBACK, "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], "temperature": 0.05, "max_tokens": max_tokens, "response_format": {"type": "json_object"}}
    response = requests.post("https://api.siliconflow.cn/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=(30, 300))
    if response.status_code >= 400:
        raise RuntimeError(f"fallback HTTP {response.status_code}: {response.text[:300].replace(key, '[REDACTED]')}")
    data = response.json(); content = data["choices"][0]["message"]["content"]
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("fallback response has no JSON object")
    return json.loads(content[start:end+1]), data.get("usage") or {}

def validate(result, expected, text_key="text"):
    blocks = result.get("blocks") or []
    ids = [str(item.get("block_id", "")) for item in blocks]
    if ids != expected:
        raise ValueError(f"返回ID不匹配: expected={expected}, actual={ids}")
    if any(not str(item.get(text_key, "")).strip() for item in blocks):
        raise ValueError("返回正文为空")
    return blocks

def chunk_rows(rows, max_items=6, max_chars=3000):
    chunks, current, chars = [], [], 0
    for row in rows:
        size = len(row.get("normalized_text", "")) + len(row.get("modern_text", ""))
        if current and (len(current) >= max_items or chars + size > max_chars):
            chunks.append(current); current, chars = [], 0
        current.append(row); chars += size
    if current:
        chunks.append(current)
    return chunks

def process_chunk(job):
    page, chunk_index, chunk, previous_context, next_context, chunk_cache = job
    chunk_ids = [r["block_id"] for r in chunk]
    chunk_payload = {
        "page": page, "chunk": chunk_index,
        "previous_context": previous_context,
        "blocks": [{"block_id": r["block_id"], "normalized_source": r.get("normalized_text", ""), "existing_rendering": r.get("modern_text", ""), "source_confidence": r.get("confidence")} for r in chunk],
        "next_context": next_context,
    }
    chunk_hash = hashlib.sha256((WRITER_SYSTEM + JUDGE_SYSTEM + json.dumps(chunk_payload, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    if chunk_cache.exists():
        saved = json.loads(chunk_cache.read_text(encoding="utf-8"))
        if saved.get("prompt_sha256") == chunk_hash:
            return page, chunk_index, "cached"
    def run_part(part, label):
        ids = [r["block_id"] for r in part]
        part_payload = dict(chunk_payload)
        part_payload["chunk"] = label
        part_payload["blocks"] = [{"block_id": r["block_id"], "normalized_source": r.get("normalized_text", ""), "existing_rendering": r.get("modern_text", ""), "source_confidence": r.get("confidence")} for r in part]
        try:
            written, usage = request(WRITER, WRITER_SYSTEM, part_payload, 7000)
            writer_blocks = validate(written, ids)
            judge_payload = {"page": page, "chunk": label, "blocks": [{"block_id": r["block_id"], "normalized_source": r.get("normalized_text", ""), "candidate": w["text"]} for r, w in zip(part, writer_blocks)]}
            judged, judge_usage = request(JUDGE, JUDGE_SYSTEM, judge_payload, 7000)
            return validate(judged, ids), [usage], [judge_usage]
        except (ValueError, RuntimeError):
            if len(part) == 1:
                written, usage = request_fallback(WRITER_SYSTEM, part_payload)
                writer_blocks = validate(written, ids)
                judge_payload = {"page": page, "chunk": label, "blocks": [{"block_id": part[0]["block_id"], "normalized_source": part[0].get("normalized_text", ""), "candidate": writer_blocks[0]["text"]}]}
                judged, judge_usage = request_fallback(JUDGE_SYSTEM, judge_payload)
                return validate(judged, ids), [usage], [judge_usage]
            mid = len(part) // 2
            left, lw, lj = run_part(part[:mid], str(label) + "a")
            right, rw, rj = run_part(part[mid:], str(label) + "b")
            return left + right, lw + rw, lj + rj
    final_blocks, writer_usage, judge_usage = run_part(chunk, chunk_index)
    chunk_cache.write_text(json.dumps({"page": page, "chunk": chunk_index, "prompt_sha256": chunk_hash, "blocks": final_blocks, "usage": {"writer": writer_usage, "judge": judge_usage}}, ensure_ascii=False, indent=2), encoding="utf-8")
    return page, chunk_index, f"{len(final_blocks)} blocks"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", help="例如 3-6 或 3,5,8")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    rows = read_rows()
    by_page = defaultdict(list)
    for row in rows:
        by_page[int(row["source_page"])].append(row)
    selected = set(by_page)
    if args.pages:
        selected = set()
        for part in args.pages.split(','):
            if '-' in part:
                lo, hi = map(int, part.split('-', 1)); selected.update(range(lo, hi + 1))
            else:
                selected.add(int(part))
    elif not args.all:
        raise SystemExit("请使用 --pages 或 --all")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    jobs, page_meta = [], {}
    for page in sorted(selected):
        page_rows = by_page[page]
        translatable = [r for r in page_rows if r["block_type"] != "figure"]
        expected = [r["block_id"] for r in translatable]
        previous_context = "".join(r.get("modern_text", "") for r in by_page.get(page-1, [])[-2:])[-600:]
        next_context = "".join(r.get("modern_text", "") for r in by_page.get(page+1, [])[:2])[:600]
        chunks = chunk_rows(translatable)
        page_meta[page] = (expected, len(chunks))
        for chunk_index, chunk in enumerate(chunks, 1):
            jobs.append((page, chunk_index, chunk, previous_context, next_context, OUTDIR / f"page-{page:03d}-chunk-{chunk_index:02d}.json"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(process_chunk, job) for job in jobs]
        for future in as_completed(futures):
            page, chunk, status = future.result()
            print(f"page {page} chunk {chunk}: {status}", flush=True)
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for page, (expected, chunk_count) in page_meta.items():
        final_blocks, page_usage = [], {"writer": [], "judge": []}
        prompt_hashes = []
        for chunk_index in range(1, chunk_count + 1):
            saved = json.loads((OUTDIR / f"page-{page:03d}-chunk-{chunk_index:02d}.json").read_text(encoding="utf-8"))
            prompt_hashes.append(saved["prompt_sha256"]); final_blocks.extend(saved["blocks"])
            for role in ("writer", "judge"):
                uses = saved["usage"][role]
                if isinstance(uses, dict): uses = [uses]
                page_usage[role].extend(uses)
                for u in uses:
                    for key in usage_total:
                        usage_total[key] += int(u.get(key, 0) or 0)
        if [b["block_id"] for b in final_blocks] != expected:
            raise ValueError(f"page {page} 汇总ID不匹配")
        prompt_hash = hashlib.sha256("".join(prompt_hashes).encode()).hexdigest()
        (OUTDIR / f"page-{page:03d}.json").write_text(json.dumps({"page": page, "prompt_sha256": prompt_hash, "writer_model": WRITER, "judge_model": JUDGE, "blocks": final_blocks, "usage": page_usage}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"page {page}: assembled {len(final_blocks)} blocks", flush=True)
    completed = {}
    for cache in sorted(OUTDIR.glob("page-*.json")):
        saved = json.loads(cache.read_text(encoding="utf-8"))
        for block in saved["blocks"]:
            completed[block["block_id"]] = block
    output_rows = []
    for row in rows:
        copy = dict(row)
        if row["block_type"] != "figure" and row["block_id"] in completed:
            block = completed[row["block_id"]]
            copy["final_reader_text"] = block["text"]
            copy["final_reader_verdict"] = block.get("verdict", "passed")
            copy["final_reader_issues"] = block.get("issues", [])
        elif row["block_type"] == "figure":
            copy["final_reader_text"] = ""
            copy["final_reader_verdict"] = "nontext_figure"
            copy["final_reader_issues"] = []
        output_rows.append(copy)
    OUTFILE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in output_rows), encoding="utf-8")
    coverage = sum(1 for r in output_rows if r["block_type"] == "figure" or r.get("final_reader_text"))
    REPORT.write_text(json.dumps({"schema_version": "1.0", "status": "completed" if coverage == len(rows) else "partial", "source_blocks": len(rows), "accounted_blocks": coverage, "pages_cached": len(list(OUTDIR.glob('page-*.json'))), "writer_model": WRITER, "judge_model": JUDGE, "usage_this_run": usage_total, "source_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(), "output_sha256": hashlib.sha256(OUTFILE.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
