#!/usr/bin/env python3
"""Refine non-high-confidence pages into reader-facing modern Chinese."""

from __future__ import annotations

import importlib.util
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "90-audit"
PAGES = ROOT / "20-source" / "pages"
OUT = AUDIT / "reader-refinements.jsonl"
MODEL = "Qwen/Qwen3-VL-32B-Instruct"


def load_driver():
    path = Path(__file__).with_name("dual_vision_sample.py")
    spec = importlib.util.spec_from_file_location("dual_vision_sample", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_pages() -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for path in AUDIT.glob("vision-pass2*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[int(row["source_page"])] = row
    return rows


def main() -> int:
    key = os.getenv("SILICONFLOW_API_KEY")
    if not key:
        raise SystemExit("SILICONFLOW_API_KEY is unavailable")
    driver = load_driver()
    rows = load_pages()
    targets = [p for p, row in sorted(rows.items())
               if row["result"].get("verdict") != "accept" or row["result"].get("confidence") != "high"]
    done = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("status") == "success":
                    done[int(row["source_page"])] = row

    def refine(page: int) -> dict:
        current = rows[page]["result"]
        prev = rows.get(page - 1, {}).get("result", {}).get("modern_text", "")
        nxt = rows.get(page + 1, {}).get("result", {}).get("modern_text", "")
        prompt = f"""你是古籍现代白话版的资深编辑。请直接观察本页扫描图，并参考候选转录，生成普通读者可直接阅读的简体中文。

要求：
1. 输出严格 JSON 对象，不要代码围栏：{{"modern_text":"...","page_role":"正文|标题|图解|非正文","confidence":"high|medium|low","editor_note":"..."}}。
2. 正文要译成自然、完整的现代白话，不保留生硬古文句式。
3. 如果本页主要是山形示意图，不要编造理论；用一两句话说明图中列出的格局名称和本图用途。
4. 删除藏书章、馆藏编号、OCR说明和模型说明。
5. 无法确认的字不要猜；若不影响主旨，省略该残字。若影响主旨，在 editor_note 中说明，modern_text 仍保持可读。
6. 不要出现“本页句子未完”“候选”“置信度”“OCR”等制作措辞。

原页：{page}
候选忠实转录：{current.get('faithful_source_text','')}
候选白话：{current.get('modern_text','')}
上一页白话末段：{prev[-500:]}
下一页白话首段：{nxt[:500]}
"""
        image = (PAGES / f"P{page:06d}.jpg").read_bytes()
        result, meta = driver.call_model(key, MODEL, image, prompt, 2600, 240)
        return {"schema_version": "1.0", "status": "success", "source_page": page,
                "page_id": f"P{page:06d}", "model": MODEL, "result": result, "request": meta}

    pending = [p for p in targets if p not in done]
    new_rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(refine, p): p for p in pending}
        for future in as_completed(futures):
            page = futures[future]
            row = future.result()
            new_rows.append(row)
            print(f"page {page}: {row['result'].get('confidence')}", flush=True)
    merged = [done[p] for p in sorted(done)] + new_rows
    merged = {int(row["source_page"]): row for row in merged}
    OUT.write_text("".join(json.dumps(merged[p], ensure_ascii=False) + "\n" for p in sorted(merged)), encoding="utf-8")
    print(json.dumps({"targets": targets, "completed": len(merged)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
