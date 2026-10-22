#!/usr/bin/env python3
"""V3 AI 白话释读流水线。

密钥只从进程环境变量或隐藏输入读取；路由配置不得包含密钥值。

Commands:
  prepare  建立隔离基线、复制图片、切分 Markdown 并生成清单
  run      调用写作模型和独立核义模型，断点续跑
  render   将已完成结果渲染为一书一 MD（全部块完成才进入 V3 根目录）
  verify   执行结构、覆盖率、原文追溯和图片硬校验
  status   输出当前进度
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests


ROOT = Path(__file__).resolve().parents[3]
V2 = ROOT / "Md" / "V2"
V3 = ROOT / "Md" / "V3"
WORK = V3 / "_work"
SEGMENTS = WORK / "segments"
RESULTS = WORK / "results"
API_CACHE = WORK / "api_cache"
DRAFTS = V3 / "_drafts"
REPORTS = V3 / "_reports"
ASSETS = V3 / "assets"
GLOSSARY_PATH = V3 / "V3风水专业术语表.md"
EXTERNAL_API_COST_LEDGER = REPORTS / "V3外部API费用台账.jsonl"

API_URL = "https://api.siliconflow.cn/v1/chat/completions"
WRITER_MODEL = os.getenv("V3_WRITER_MODEL", "Qwen/Qwen3.5-35B-A3B")
REPAIR_MODEL = os.getenv("V3_REPAIR_MODEL", "Qwen/Qwen3.5-122B-A10B")
ESCALATION_MODEL = os.getenv("V3_ESCALATION_MODEL", "Qwen/Qwen3.5-122B-A10B")
JUDGE_MODEL = os.getenv("V3_JUDGE_MODEL", "deepseek-ai/DeepSeek-V3.2")
MAX_BATCH_CHARS = int(os.getenv("V3_MAX_BATCH_CHARS", "2200"))
MAX_BATCH_ITEMS = int(os.getenv("V3_MAX_BATCH_ITEMS", "10"))
MAX_REPAIR_ROUNDS = int(os.getenv("V3_MAX_REPAIR_ROUNDS", "1"))
MAX_API_ATTEMPTS = int(os.getenv("V3_MAX_API_ATTEMPTS", "1"))
API_CONNECT_TIMEOUT_SECONDS = int(os.getenv("V3_API_CONNECT_TIMEOUT_SECONDS", "15"))
API_READ_TIMEOUT_SECONDS = int(os.getenv("V3_API_READ_TIMEOUT_SECONDS", "90"))
API_STREAM_MAX_SECONDS = int(os.getenv("V3_API_STREAM_MAX_SECONDS", "600"))
MAX_BUDGET_RMB = float(os.getenv("V3_MAX_BUDGET_RMB", "150"))
MAX_BOOK_TRANSIENT_RESTARTS = int(
    os.getenv("V3_MAX_BOOK_TRANSIENT_RESTARTS", "5")
)
DEFAULT_PARALLEL_WORKERS = int(os.getenv("V3_PARALLEL_WORKERS", "3"))
MAX_CONCURRENT_API_REQUESTS = max(
    1, int(os.getenv("V3_MAX_CONCURRENT_API_REQUESTS", "2"))
)
# Parallel requests can finish after another worker reaches the cap.  Stop
# starting paid cache misses before the last half yuan so the aggregate remains
# strictly below the user-authorized ceiling even with three in-flight calls.
BUDGET_PARALLEL_HEADROOM_RMB = float(
    os.getenv("V3_BUDGET_PARALLEL_HEADROOM_RMB", "0.5")
)
STATE_LOCK = threading.RLock()
FILE_IO_LOCK = threading.RLock()
MODEL_REQUEST_SEMAPHORES: dict[str, threading.Semaphore] = {}
MODEL_REQUEST_SEMAPHORES_LOCK = threading.Lock()


def normalize_string_list(value: Any) -> list[str]:
    """Flatten and deduplicate model-provided list fields safely.

    Models occasionally return nested arrays or objects in ``issues`` and
    ``uncertainty``.  Those values must never be used as dictionary keys (or
    crash the long-running worker); retain them as readable JSON/text entries.
    """
    flattened: list[str] = []

    def visit(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                visit(child)
            return
        if isinstance(item, dict):
            text = json.dumps(item, ensure_ascii=False, sort_keys=True)
        else:
            text = str(item)
        text = text.strip()
        if text:
            flattened.append(text)

    visit(value)
    return list(dict.fromkeys(flattened))


VALID_JUDGE_VERDICTS = frozenset({"accept", "revise", "uncertain"})


def normalize_judge_verdict(value: Any) -> str:
    """Fail closed when a model or legacy cache contains a malformed verdict."""
    verdict = str(value or "").strip().lower()
    return verdict if verdict in VALID_JUDGE_VERDICTS else "uncertain"


GLOBAL_REQUEST_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_API_REQUESTS)
PROVIDER_REQUEST_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}
PROVIDER_REQUEST_SEMAPHORES_LOCK = threading.Lock()
NO_JSON_MODE_MODELS = {
    name.strip()
    for name in os.getenv(
        "V3_NO_JSON_MODE_MODELS", "stepfun-ai/Step-3.5-Flash"
    ).split(",")
    if name.strip()
}

# 2026-09 官方公开价格（元 / 百万 token）；可由环境变量覆盖。
PRICE = {
    WRITER_MODEL: {
        "input": float(os.getenv("V3_WRITER_INPUT_PRICE", "0.4")),
        "output": float(os.getenv("V3_WRITER_OUTPUT_PRICE", "3.2")),
    },
    REPAIR_MODEL: {
        "input": float(os.getenv("V3_REPAIR_INPUT_PRICE", "0.8")),
        "output": float(os.getenv("V3_REPAIR_OUTPUT_PRICE", "6.4")),
    },
    ESCALATION_MODEL: {
        "input": float(os.getenv("V3_ESCALATION_INPUT_PRICE", "0.8")),
        "output": float(os.getenv("V3_ESCALATION_OUTPUT_PRICE", "6.4")),
    },
    JUDGE_MODEL: {
        "input": float(os.getenv("V3_JUDGE_INPUT_PRICE", "4.0")),
        "output": float(os.getenv("V3_JUDGE_OUTPUT_PRICE", "6.0")),
        "cached_input": float(os.getenv("V3_JUDGE_CACHED_INPUT_PRICE", "0.4")),
    },
}


DEFAULT_MODEL_ROUTE = {
    "provider": "siliconflow",
    "api_url": API_URL,
    "api_key_env": "SILICONFLOW_API_KEY",
    "max_concurrent_requests": MAX_CONCURRENT_API_REQUESTS,
    "models_url": "https://api.siliconflow.cn/v1/models",
    "stream": True,
}


def normalize_model_route(model: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate one non-secret OpenAI-compatible route."""
    forbidden = {"api_key", "key", "token", "secret", "authorization"}
    if any(str(name).lower() in forbidden for name in raw):
        raise ValueError("V3_MODEL_ROUTES_JSON 只能写密钥环境变量名，禁止写密钥值")
    route = dict(DEFAULT_MODEL_ROUTE)
    route.update(raw)
    route["remote_model"] = str(route.get("remote_model") or model)
    route["provider"] = str(route.get("provider") or "custom").strip()
    route["api_url"] = str(route.get("api_url") or "").strip()
    route["api_key_env"] = str(route.get("api_key_env") or "").strip()
    if not re.match(r"^https?://", route["api_url"], re.I):
        raise ValueError(f"模型 {model} 的 api_url 必须是 http(s) URL")
    is_default_endpoint = route["api_url"] == API_URL
    if raw and not is_default_endpoint and "api_key_env" not in raw:
        raise ValueError(f"模型 {model} 的自定义路由必须显式提供 api_key_env")
    if raw and not is_default_endpoint and "models_url" not in raw:
        route["models_url"] = None
    if not re.match(r"^[A-Z_][A-Z0-9_]*$", route["api_key_env"]):
        raise ValueError(f"模型 {model} 的 api_key_env 不是安全的环境变量名")
    route["max_concurrent_requests"] = max(
        1, int(route.get("max_concurrent_requests") or 1)
    )
    route["max_concurrent_model_requests"] = max(
        1, int(route.get("max_concurrent_model_requests") or 1)
    )
    route["stream"] = bool(route.get("stream", True))
    omit = route.get("omit_body_fields") or []
    if not isinstance(omit, list) or not all(isinstance(name, str) for name in omit):
        raise ValueError(f"模型 {model} 的 omit_body_fields 必须是字符串数组")
    overrides = route.get("body_overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError(f"模型 {model} 的 body_overrides 必须是对象")
    route["omit_body_fields"] = omit
    route["body_overrides"] = overrides
    prices = route.get("prices") or {}
    if not isinstance(prices, dict):
        raise ValueError(f"模型 {model} 的 prices 必须是对象")
    route["prices"] = {
        name: float(value)
        for name, value in prices.items()
        if name in {"input", "output", "cached_input"}
    }
    if raw and not is_default_endpoint and not {
        "input", "output"
    }.issubset(route["prices"]):
        raise ValueError(
            f"模型 {model} 的自定义路由必须提供 prices.input 和 prices.output，"
            "以保证人民币 150 元总预算准确"
        )
    return route


def parse_model_routes(raw: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Parse logical-model routes; a list enables stable provider sharding."""
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("V3_MODEL_ROUTES_JSON 顶层必须是对象")
    result: dict[str, list[dict[str, Any]]] = {}
    for model, value in parsed.items():
        candidates = value if isinstance(value, list) else [value]
        if not candidates or not all(isinstance(item, dict) for item in candidates):
            raise ValueError(f"模型 {model} 的路由必须是对象或非空对象数组")
        result[str(model)] = [normalize_model_route(str(model), item) for item in candidates]
    return result


MODEL_ROUTES = parse_model_routes(os.getenv("V3_MODEL_ROUTES_JSON"))


def route_identity(route: dict[str, Any]) -> str:
    return "|".join(
        (
            str(route["provider"]),
            str(route["api_url"]),
            str(route["api_key_env"]),
            str(route["remote_model"]),
        )
    )


def route_cache_identity(route: dict[str, Any]) -> str:
    """Non-secret response-affecting identity used only for cache isolation."""
    return json.dumps(
        {
            "provider": route["provider"],
            "api_url": route["api_url"],
            "api_key_env": route["api_key_env"],
            "remote_model": route["remote_model"],
            "stream": route["stream"],
            "omit_body_fields": route.get("omit_body_fields") or [],
            "body_overrides": route.get("body_overrides") or {},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def route_for_model(model: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    candidates = MODEL_ROUTES.get(model)
    if not candidates:
        return normalize_model_route(model, {})
    if len(candidates) == 1:
        return candidates[0]
    stable_material = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    index = int(hashlib.sha256(stable_material.encode("utf-8")).hexdigest(), 16) % len(candidates)
    return candidates[index]


def public_model_route_summary() -> dict[str, list[dict[str, Any]]]:
    summary: dict[str, list[dict[str, Any]]] = {}
    for model in (WRITER_MODEL, REPAIR_MODEL, ESCALATION_MODEL, JUDGE_MODEL):
        routes = MODEL_ROUTES.get(model) or [normalize_model_route(model, {})]
        summary[model] = [
            {
                "provider": route["provider"],
                "api_url": route["api_url"],
                "api_key_env": route["api_key_env"],
                "remote_model": route["remote_model"],
                "max_concurrent_requests": route["max_concurrent_requests"],
                "max_concurrent_model_requests": route[
                    "max_concurrent_model_requests"
                ],
            }
            for route in routes
        ]
    return summary

IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
COMMENT_LINE_RE = re.compile(r"^\s*<!--[\s\S]*?-->\s*$")
BOOK_FILE_RE = re.compile(r"^\d{3}\s+.+\.md$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
EMPTY_HEADING_RE = re.compile(r"^#{2,6}\s*$")
SOURCE_RE = re.compile(r"^>\s*来源：")
HTML_ONLY_RE = re.compile(r"^\s*</?(?:table|tr|td|th|tbody|thead|img|div|details|summary)\b", re.I)
JAPANESE_RE = re.compile(r"[\u3040-\u30ff]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
PROTECTED_RE = re.compile(
    r"(?:[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])|"
    r"(?:\d+(?:\.\d+)?(?:°|度|年|月|日|时|頁|页|卷|章|節|节)?)|"
    r"(?:[一二三四五六七八九十百千万]+(?:度|年|月|日|時|时|頁|页|卷|章|節|节))"
)

# 这些古籍专名/凝固短语在目前证据下不宜逐字猜释：白话中必须原样引用。
OPAQUE_TERMS = [
    "浮黎", "鳌极", "鳌布", "始青", "赤明", "云篆", "元女", "元钧",
    "庚甲", "德刑", "神化", "幽明", "虎贲",
]

# 这些词允许在白话文中增加经过术语表批准的解释，但禁止被另造普通词替代。
LOCKED_TERMS = [
    "阴阳", "五行", "河图", "洛书", "八卦", "先天", "后天", "天干", "地支",
    "干支", "生克", "制化", "纳甲", "分金", "二十四山", "七十二龙", "三元",
    "三合", "玄空", "挨星", "峦头", "理气", "龙", "穴", "砂", "水", "向",
    "来龙", "入首", "过峡", "结穴", "明堂", "水口", "案山", "朝山", "青龙",
    "白虎", "朱雀", "玄武", "生气", "旺气", "煞气", "罗盘", "坐山", "朝向",
    "乾", "坤", "震", "巽", "坎", "离", "艮", "兑",
] + OPAQUE_TERMS

# 已在小样中发现的典型“看似专业、实为无原文依据”的扩写。它们既用于
# 本地硬拦截，也作为后续回归样例；命中后必须退回修复，不能靠模型自评放行。
UNSUPPORTED_EXPANSION_RULES = [
    ("九天元女", lambda source: "九天元女" not in source),
    ("九天玄女", lambda source: "九天玄女" not in source),
    ("浮黎一脉", lambda source: "浮黎一脉" not in source),
    ("浮黎派", lambda source: "浮黎派" not in source),
    ("八个关键方位", lambda source: "八个关键方位" not in source),
    ("六个甲子", lambda source: "六个甲子" not in source),
    ("天地运行的根本度量", lambda source: "天地运行的根本度量" not in source),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, data: Any) -> None:
    with FILE_IO_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Multiple resumable V3 workers can legitimately write distinct books
        # while sharing the global status report.  A fixed ``.tmp`` name lets
        # one process replace another process' temporary file on Windows.
        # Keep the temporary file process-local, then atomically publish it.
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with FILE_IO_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with FILE_IO_LOCK:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows


def split_long_text(text: str, limit: int = 2600) -> list[str]:
    if len(text) <= limit:
        return [text]
    pieces = re.split(r"(?<=[。！？；.!?;])", text)
    out: list[str] = []
    current = ""
    for piece in pieces:
        if not piece:
            continue
        if current and len(current) + len(piece) > limit:
            out.append(current)
            current = ""
        while len(piece) > limit:
            room = limit - len(current)
            if room > 0:
                current += piece[:room]
                piece = piece[room:]
                out.append(current)
                current = ""
            else:
                out.append(piece[:limit])
                piece = piece[limit:]
        current += piece
    if current:
        out.append(current)
    return out


def split_html_block(text: str, limit: int = 6500) -> list[str]:
    """在 </tr> 边界切大型 HTML 表格，避免破坏行和单元格。"""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    match = re.search(r"(?is)(.*?)(<table\b[^>]*>)(.*?)(</table>)(.*)", text)
    if not match:
        return [text]
    prefix, open_tag, body, close_tag, suffix = match.groups()
    rows = re.findall(r"(?is)<tr\b[^>]*>.*?</tr>", body)
    if not rows:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    size = len(open_tag) + len(close_tag)
    for row in rows:
        if current and size + len(row) > limit:
            parts.append(open_tag + "".join(current) + close_tag)
            current = []
            size = len(open_tag) + len(close_tag)
        current.append(row)
        size += len(row)
    if current:
        parts.append(open_tag + "".join(current) + close_tag)
    if prefix.strip():
        parts[0] = prefix.strip() + "\n" + parts[0]
    if suffix.strip():
        parts[-1] = parts[-1] + "\n" + suffix.strip()
    return parts


def semantic_visible_text(text: Any) -> str:
    """Remove markup-only material before semantic and protected-value checks.

    Cached model rows can contain a malformed list/dict in ``modern_text``.
    Coerce that value before regex processing so one legacy response cannot
    terminate the long-running worker.
    """
    if isinstance(text, (list, tuple, set, dict)):
        text = "\n".join(normalize_string_list(text))
    elif text is None:
        text = ""
    elif not isinstance(text, str):
        text = str(text)
    visible_text = re.sub(r"<!--[\s\S]*?-->", "", text or "")
    visible_text = IMAGE_RE.sub("", visible_text)
    visible_text = re.sub(r"<[^>]+>", "", visible_text)
    return visible_text


def protected_tokens(text: str) -> list[str]:
    # HTML attributes, page-image comments and hashed image filenames are
    # layout metadata, not values that a white-language rendering must repeat.
    visible_text = semantic_visible_text(text)
    return list(dict.fromkeys(PROTECTED_RE.findall(visible_text)))


def protected_token_present(candidate: str, token: str) -> bool:
    if token in candidate:
        return True
    # 二十四山等列举中，OCR 常把相邻山名连写为“丙午”“壬子”；白话加
    # 顿号只是恢复列举结构，不应误判为干支丢失。真实甲子年等仍需原样。
    if re.fullmatch(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]", token):
        return bool(re.search(rf"{token[0]}[、，,·/\s及与和]*{token[1]}", candidate))
    return False


def looks_like_toc(text: str) -> bool:
    """识别扫描书目录：多行标题 + 页码/点线，不把目录改写成连续正文。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 8:
        return False
    leader_lines = sum(1 for line in lines if re.search(r"[…\.·]{3,}", line))
    page_lines = sum(
        1 for line in lines
        if re.search(r"(?:[…\.·\s]|^)(?:\d{1,4}|[一二三四五六七八九十百]+)\s*$", line)
    )
    return leader_lines >= 4 or page_lines >= max(6, len(lines) // 3)


def load_glossary() -> dict[str, str]:
    """读取人工批准的术语解释；模型不得自行扩充这份白名单。"""
    glossary: dict[str, str] = {}
    if not GLOSSARY_PATH.exists():
        return glossary
    for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"术语", "---"} or set(cells[0]) == {"-"}:
            continue
        glossary[cells[0]] = cells[1]
    return glossary


def allowed_glossary_for(locked_terms: list[str], glossary: dict[str, str]) -> dict[str, str]:
    return {term: glossary[term] for term in locked_terms if term in glossary}


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def split_markdown_media_block(block: str) -> list[tuple[str, str]]:
    """Split image/comment lines from adjacent prose while preserving order.

    V2 intentionally keeps page images beside OCR/search notes and captions.
    Treating the whole block as prose sends image hashes and page metadata to
    the language model, creates false protected-number failures, and hides the
    image inside the source-details fold.  Returning separate media/text chunks
    keeps each image visible in the main reading flow and only translates text.
    """
    stripped = block.strip()
    lines = stripped.splitlines()
    if not any(IMAGE_LINE_RE.fullmatch(line.strip()) for line in lines):
        return [("text", stripped)]

    chunks: list[tuple[str, str]] = []
    current_role: str | None = None
    current_lines: list[str] = []
    for line in lines:
        clean = line.strip()
        role = "media" if (
            IMAGE_LINE_RE.fullmatch(clean) or COMMENT_LINE_RE.fullmatch(clean)
        ) else "text"
        if current_lines and role != current_role:
            chunks.append((current_role or "text", "\n".join(current_lines).strip()))
            current_lines = []
        current_role = role
        current_lines.append(line)
    if current_lines:
        chunks.append((current_role or "text", "\n".join(current_lines).strip()))
    return [(role, text) for role, text in chunks if text]


def locked_term_requires_exact_preservation(source: str, term: str) -> bool:
    """Disambiguate common one-character words from technical trigram terms."""
    if term == "离":
        compact = compact_text(source)
        if re.search(r"(?:八卦|八宫|卦体|卦象|卦位)", compact):
            return True
        if re.search(
            r"(?:离(?:山|宮|宫|卦|位|方|龍|龙|水|向)|"
            r"(?:來|来|至|坐|朝|向|配|歸|归|屬|属|入)离|"
            r"[乾坤震巽坎艮兑]离|离[乾坤震巽坎艮兑])",
            compact,
        ):
            return True
        heading = HEADING_RE.match(source.strip())
        return bool(heading and heading.group(2).strip() == "离")
    if term == "向":
        compact = compact_text(source)
        if re.search(
            r"(?:立向|定向|坐向|朝向|向(?:法|首|水|山|方|位|线|線)|"
            r"(?:分金|二十四山).{0,12}向)",
            compact,
        ):
            return True
        heading = HEADING_RE.match(source.strip())
        return bool(heading and heading.group(2).strip() == "向")
    return True


def normalize_rendered_heading(source: str, candidate: str) -> str:
    """Deterministically preserve Markdown hierarchy and the exact source heading.

    Models sometimes turn a heading into explanatory prose even when prompted
    not to.  Rendering is the final structural boundary, so restore the source
    level and title without another paid model call, then append genuinely new
    explanatory prose when present.
    """
    source_match = HEADING_RE.match(source.strip())
    if not source_match:
        return candidate.strip()
    marks, source_title = source_match.groups()
    # The only document-level H1 is the book title (kind=title).  Some OCR
    # baselines accidentally label chapter headings with a single '#'; keep
    # their wording but render them as H2 so the generated book has one H1.
    if marks == "#":
        marks = "##"
    candidate_text = candidate.strip()
    candidate_match = HEADING_RE.match(candidate_text)
    if candidate_match:
        candidate_text = candidate_match.group(2).strip()
    if not candidate_text:
        return f"{marks} {source_title}"
    if compact_text(source_title) in compact_text(candidate_text):
        return f"{marks} {candidate_text}"
    return f"{marks} {source_title} — {candidate_text}"


def normalize_rendered_body_headings(text: str) -> str:
    """Keep generated in-body headings below the book's single H1 title."""
    return re.sub(r"(?m)^#(?=\s)", "##", text)


def local_quality_issues(
    source: str,
    candidate: str,
    language: str | None,
    locked_terms: list[str],
    allowed_glossary: dict[str, str],
    opaque_terms: list[str] | None = None,
) -> dict[str, Any]:
    """不依赖模型自评的保守硬检查。"""
    candidate = semantic_visible_text(candidate)
    semantic_source = semantic_visible_text(source)
    semantic_candidate = semantic_visible_text(candidate)
    compact_source = compact_text(semantic_source)
    compact_candidate = compact_text(semantic_candidate)
    missing_terms = [
        term for term in locked_terms
        if locked_term_requires_exact_preservation(source, term)
        and term not in candidate
    ]
    missing_values = [
        token for token in protected_tokens(source)
        if not protected_token_present(candidate, token)
    ]
    similarity = (
        difflib.SequenceMatcher(None, compact_source, compact_candidate).ratio()
        if compact_source else 0.0
    )
    source_duplicated = (
        language in {"classical_chinese", "japanese"}
        and len(compact_source) >= 20
        and compact_source in compact_candidate
    )
    insufficient_modernization = (
        language in {"classical_chinese", "japanese"}
        and len(compact_source) >= 12
        and similarity >= 0.92
    )

    unsupported: list[str] = []
    for phrase, applies in UNSUPPORTED_EXPANSION_RULES:
        if phrase in semantic_candidate and applies(semantic_source):
            unsupported.append(phrase)

    # 新增括号解释只允许逐字采用术语表中的批准解释。普通白话改写无需括号。
    approved_notes = set(allowed_glossary.values())
    inserted_parentheticals: list[str] = []
    for match in re.finditer(r"（([^（）]{2,120})）|\(([^()]{2,120})\)", semantic_candidate):
        note = (match.group(1) or match.group(2) or "").strip()
        conservative_note = bool(re.search(r"不详|不明|原文|疑|可能|错乱|缺字|无法|OCR", note, re.I))
        pagination_note = bool(re.fullmatch(r"(?:第)?\d{1,4}\s*页", note))
        if (
            note not in semantic_source
            and note not in approved_notes
            and not conservative_note
            and not pagination_note
        ):
            inserted_parentheticals.append(note)

    quoted_spans = [
        match.group(1) or match.group(2) or match.group(3) or ""
        for match in re.finditer(r"“([^”]+)”|‘([^’]+)’|\"([^\"]+)\"", semantic_candidate)
    ]
    unquoted_opaque_terms = [] if language == "modern_chinese" else [
        term for term in (opaque_terms or [])
        if term in semantic_source and not any(term in span for span in quoted_spans)
    ]
    unsupported_opaque_definitions = [] if language == "modern_chinese" else [
        term for term in (opaque_terms or [])
        if re.search(
            rf"[‘“\"]{re.escape(term)}[’”\"]\s*(?:一词)?\s*(?:指|是|即|意为|指代|表示|属于)",
            semantic_candidate,
        )
    ]

    return {
        "missing_locked_terms": missing_terms,
        "missing_protected_tokens": missing_values,
        "source_candidate_similarity": round(similarity, 6),
        "source_duplicated": source_duplicated,
        "insufficient_modernization": insufficient_modernization,
        "unsupported_expansions": list(dict.fromkeys(unsupported)),
        "unapproved_parenthetical_notes": list(dict.fromkeys(inserted_parentheticals)),
        "unquoted_opaque_terms": unquoted_opaque_terms,
        "unsupported_opaque_definitions": unsupported_opaque_definitions,
    }


def hard_issue_messages(check: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if check["missing_locked_terms"]:
        issues.append("专业术语未保留：" + "、".join(check["missing_locked_terms"]))
    if check["missing_protected_tokens"]:
        issues.append("数字或干支等保护项未保留：" + "、".join(check["missing_protected_tokens"]))
    if check["source_duplicated"]:
        issues.append("候选文本重复收录了完整原文；原文应只出现在系统折叠区。")
    if check["insufficient_modernization"]:
        issues.append("古文或日文与候选文本高度相同，没有完成可验证的白话化或中译。")
    if check["unsupported_expansions"]:
        issues.append("出现无原文依据的具体化解释：" + "、".join(check["unsupported_expansions"]))
    if check["unapproved_parenthetical_notes"]:
        issues.append("出现术语表未批准的括号解释：" + "；".join(check["unapproved_parenthetical_notes"]))
    if check["unquoted_opaque_terms"]:
        issues.append("含义未定专名未作为原词引用：" + "、".join(check["unquoted_opaque_terms"]))
    if check["unsupported_opaque_definitions"]:
        issues.append(
            "含义未定专名被擅自下定义：" + "、".join(check["unsupported_opaque_definitions"])
        )
    return issues


LOCAL_ISSUE_PREFIXES = (
    "专业术语未保留：",
    "数字或干支等保护项未保留：",
    "候选文本重复收录了完整原文",
    "古文或日文与候选文本高度相同",
    "出现无原文依据的具体化解释：",
    "出现术语表未批准的括号解释：",
    "含义未定专名未作为原词引用：",
    "含义未定专名被擅自下定义：",
)


def classify_block(block: str, index: int) -> tuple[str, bool, str]:
    stripped = block.strip()
    if index == 0 and stripped.startswith("# "):
        return "title", False, "mixed"
    if EMPTY_HEADING_RE.match(stripped):
        return "empty_heading", False, "none"
    if HEADING_RE.match(stripped):
        language = "japanese" if JAPANESE_RE.search(stripped) else "classical_or_modern_chinese"
        return "heading", True, language
    if SOURCE_RE.match(stripped):
        return "source_note", False, "mixed"
    if IMAGE_RE.fullmatch(stripped):
        return "image", False, "none"
    if stripped.startswith("<!--") and stripped.endswith("-->"):
        return "comment", False, "none"
    if stripped.startswith("```"):
        return "code", False, "mixed"
    if looks_like_toc(stripped):
        if JAPANESE_RE.search(stripped):
            return "toc", True, "japanese"
        return "toc", False, "mixed"
    if "<table" in stripped.lower() or HTML_ONLY_RE.match(stripped):
        return "html", True, "mixed"
    if JAPANESE_RE.search(stripped):
        return "prose", True, "japanese"
    han = len(HAN_RE.findall(stripped))
    if han < 2:
        return "other", False, "mixed"
    return "prose", True, "classical_or_modern_chinese"


def merge_japanese_fragments(blocks: list[str]) -> list[tuple[int, str]]:
    """合并由扫描版换行造成的短日文句片，避免逐行翻译成碎片。"""
    merged: list[tuple[int, str]] = []
    index = 0
    while index < len(blocks):
        block = blocks[index].strip()
        if not block:
            index += 1
            continue
        kind, translatable, language = classify_block(block, index)
        if (
            kind == "prose"
            and translatable
            and language == "japanese"
            and len(block) <= 120
            and not re.search(r"[。！？!?]\s*$", block)
        ):
            parts = [block]
            next_index = index + 1
            total = len(block)
            while next_index < len(blocks) and total < 800:
                following = blocks[next_index].strip()
                next_kind, next_translatable, next_language = classify_block(following, next_index)
                if not (
                    next_kind == "prose"
                    and next_translatable
                    and next_language == "japanese"
                    and len(following) <= 180
                ):
                    break
                parts.append(following)
                total += len(following)
                next_index += 1
                if re.search(r"[。！？!?]\s*$", following):
                    break
            if len(parts) > 1:
                merged.append((index, "\n".join(parts)))
                index = next_index
                continue
        merged.append((index, block))
        index += 1
    return merged


@dataclass
class Segment:
    id: str
    book_no: int
    book_file: str
    block_index: int
    part_index: int
    kind: str
    translatable: bool
    language_hint: str
    source: str
    source_sha256: str
    locked_terms: list[str]
    opaque_terms: list[str]


def segment_book(path: Path, book_no: int) -> list[Segment]:
    raw = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", raw)
    segments: list[Segment] = []
    for block_index, block in merge_japanese_fragments(blocks):
        part_index = 0
        for role, subblock in split_markdown_media_block(block):
            if role == "media":
                classified_parts = [("image", False, "none", subblock)]
            else:
                kind, translatable, language_hint = classify_block(subblock, block_index)
                # Bare labels add no reader value when sent through a paid
                # model; preserve them beside their image exactly as printed.
                if compact_text(subblock) in {"图", "圖", "图说", "圖說", "插图", "插圖", "附图", "附圖"}:
                    kind, translatable, language_hint = "image_caption", False, "mixed"
                if kind == "html":
                    raw_parts = split_html_block(subblock)
                else:
                    raw_parts = split_long_text(subblock) if translatable else [subblock]
                classified_parts = [
                    (kind, translatable, language_hint, part) for part in raw_parts
                ]

            for kind, translatable, language_hint, part in classified_parts:
                part = part.strip()
                source_sha256 = hashlib.sha256(part.encode("utf-8")).hexdigest()
                sid = (
                    f"book{book_no:03d}-b{block_index:06d}"
                    f"-p{part_index:03d}-{source_sha256[:10]}"
                )
                terms = [t for t in LOCKED_TERMS if t in part]
                opaque_terms = [t for t in OPAQUE_TERMS if t in part]
                segments.append(
                    Segment(
                        id=sid,
                        book_no=book_no,
                        book_file=path.name,
                        block_index=block_index,
                        part_index=part_index,
                        kind=kind,
                        translatable=translatable,
                        language_hint=language_hint,
                        source=part,
                        source_sha256=source_sha256,
                        locked_terms=terms,
                        opaque_terms=opaque_terms,
                    )
                )
                part_index += 1
    return segments


def copy_assets() -> None:
    source = V2 / "assets"
    if not source.exists():
        raise FileNotFoundError(source)
    if ASSETS.exists():
        source_files = sorted(p.relative_to(source) for p in source.rglob("*") if p.is_file())
        target_files = sorted(p.relative_to(ASSETS) for p in ASSETS.rglob("*") if p.is_file())
        if source_files == target_files and all(
            (source / rel).stat().st_size == (ASSETS / rel).stat().st_size
            for rel in source_files
        ):
            return
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, ASSETS, dirs_exist_ok=True, copy_function=shutil.copy2)


def prepare() -> None:
    if not V2.exists():
        raise FileNotFoundError(V2)
    for p in (SEGMENTS, RESULTS, DRAFTS, REPORTS):
        p.mkdir(parents=True, exist_ok=True)
    copy_assets()

    books = sorted(V2.glob("*.md"))
    manifest_books: list[dict[str, Any]] = []
    total_segments = 0
    total_translatable = 0
    total_chars = 0
    for book_no, path in enumerate(books, start=1):
        segments = segment_book(path, book_no)
        seg_path = SEGMENTS / f"book{book_no:03d}.jsonl"
        seg_path.write_text(
            "".join(json.dumps(asdict(s), ensure_ascii=False) + "\n" for s in segments),
            encoding="utf-8",
            newline="\n",
        )
        translatable = [s for s in segments if s.translatable]
        row = {
            "book_no": book_no,
            "file": path.name,
            "source_sha256": sha256_file(path),
            "source_bytes": path.stat().st_size,
            "segments": len(segments),
            "translatable_segments": len(translatable),
            "translatable_characters": sum(len(s.source) for s in translatable),
            "languages": sorted({s.language_hint for s in translatable}),
        }
        manifest_books.append(row)
        total_segments += row["segments"]
        total_translatable += row["translatable_segments"]
        total_chars += row["translatable_characters"]

    assets = [p for p in ASSETS.rglob("*") if p.is_file()]
    manifest = {
        "version": "V3",
        "generated_at": now_iso(),
        "source": str(V2),
        "output": str(V3),
        "books": manifest_books,
        "totals": {
            "books": len(books),
            "segments": total_segments,
            "translatable_segments": total_translatable,
            "translatable_characters": total_chars,
            "asset_files": len(assets),
            "asset_bytes": sum(p.stat().st_size for p in assets),
        },
        "source_v2_report": str(V2 / "_reports" / "V2总体验收报告.json"),
        "known_source_damaged_pages": 6,
    }
    atomic_json(REPORTS / "V3基线清单.json", manifest)
    old_state_path = REPORTS / "V3运行状态.json"
    old_state = json.loads(old_state_path.read_text(encoding="utf-8")) if old_state_path.exists() else {}
    state = {
        "state": "prepared",
        "updated_at": now_iso(),
        "writer_model": WRITER_MODEL,
        "repair_model": REPAIR_MODEL,
        "escalation_model": ESCALATION_MODEL,
        "judge_model": JUDGE_MODEL,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
        "max_concurrent_api_requests": MAX_CONCURRENT_API_REQUESTS,
        "model_routes": public_model_route_summary(),
        "max_budget_rmb": MAX_BUDGET_RMB,
        "books_total": len(books),
        "books_rendered": 0,
        "segments_total": total_translatable,
        "segments_writer_completed": 0,
        "segments_judged": 0,
        "segments_uncertain": 0,
        "usage": old_state.get("usage") or {"prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_rmb": 0.0},
    }
    atomic_json(REPORTS / "V3运行状态.json", state)
    print(json.dumps(manifest["totals"], ensure_ascii=False, indent=2))


def batches(
    rows: Iterable[dict[str, Any]],
    max_chars: int,
    max_items: int = MAX_BATCH_ITEMS,
) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    size = 0
    for row in rows:
        row_size = len(row["source"])
        if batch and (size + row_size > max_chars or len(batch) >= max_items):
            yield batch
            batch = []
            size = 0
        batch.append(row)
        size += row_size
    if batch:
        yield batch


def parse_json_content(content: str) -> Any:
    """Parse JSON directly or extract a complete JSON value from model framing."""
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text).strip()
        decoder = json.JSONDecoder()
        # raw_decode tolerates harmless prose before/after a complete value;
        # downstream stable-ID and per-item schema checks remain authoritative.
        # Scan both object and array starts to handle gateways/models that wrap
        # otherwise valid JSON in explanatory framing or code-fence remnants.
        for start, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text, start)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, (dict, list)):
                return parsed
        raise


def collect_streamed_chat(
    lines: Iterable[bytes | str], max_seconds: int | float | None = None
) -> tuple[str, dict[str, Any]]:
    """Collect OpenAI-compatible SSE content and the final usage object."""
    content_parts: list[str] = []
    final_usage: dict[str, Any] = {}
    started_at = time.monotonic()
    for raw in lines:
        if max_seconds is not None and time.monotonic() - started_at > max_seconds:
            raise TimeoutError(f"SSE 流式响应超过总时长上限 {max_seconds}s")
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        if not line.startswith("data:"):
            continue
        event_text = line[5:].strip()
        if not event_text or event_text == "[DONE]":
            continue
        event = json.loads(event_text)
        if event.get("code") and not event.get("choices"):
            raise RuntimeError(
                f"流式 API 错误 {event.get('code')}: {event.get('message') or event.get('data')}"
            )
        if isinstance(event.get("usage"), dict) and event["usage"]:
            final_usage = event["usage"]
        choices = event.get("choices") or []
        if choices:
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                content_parts.append(piece)
    return "".join(content_parts), final_usage


def model_request_semaphore(
    model: str, capacity: int = 1
) -> threading.Semaphore:
    """Serialize calls per remote model route while allowing providers in parallel."""
    with MODEL_REQUEST_SEMAPHORES_LOCK:
        if model not in MODEL_REQUEST_SEMAPHORES:
            MODEL_REQUEST_SEMAPHORES[model] = threading.BoundedSemaphore(
                max(1, int(capacity))
            )
        return MODEL_REQUEST_SEMAPHORES[model]


def provider_request_semaphore(route: dict[str, Any]) -> threading.BoundedSemaphore:
    identity = route_identity(route)
    default_identity = route_identity(normalize_model_route(route["remote_model"], {}))
    if identity == default_identity:
        return GLOBAL_REQUEST_SEMAPHORE
    with PROVIDER_REQUEST_SEMAPHORES_LOCK:
        if identity not in PROVIDER_REQUEST_SEMAPHORES:
            PROVIDER_REQUEST_SEMAPHORES[identity] = threading.BoundedSemaphore(
                int(route["max_concurrent_requests"])
            )
        return PROVIDER_REQUEST_SEMAPHORES[identity]


def request_json(
    model: str,
    system: str,
    payload: dict[str, Any],
    max_tokens: int = 10000,
    route: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, int]]:
    return request_json_unlocked(
        model, system, payload, max_tokens, route=route
    )


def normalize_usage(
    usage: Any,
    system: str,
    payload: dict[str, Any],
    content: str,
) -> dict[str, int | bool]:
    """Use conservative UTF-8 byte estimates when a gateway reports zero usage."""
    raw_usage = usage if isinstance(usage, dict) else {}
    prompt_tokens = int(raw_usage.get("prompt_tokens") or 0)
    completion_tokens = int(raw_usage.get("completion_tokens") or 0)
    estimated = bool(raw_usage.get("usage_estimated"))
    if prompt_tokens <= 0:
        prompt_material = system + json.dumps(payload, ensure_ascii=False)
        prompt_tokens = len(prompt_material.encode("utf-8"))
        estimated = True
    if completion_tokens <= 0:
        completion_tokens = len(content.encode("utf-8"))
        estimated = True
    prompt_details = raw_usage.get("prompt_tokens_details") or {}
    cached_prompt_tokens = int(
        raw_usage.get("prompt_cache_hit_tokens")
        or prompt_details.get("cached_tokens")
        or 0
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_prompt_tokens": min(cached_prompt_tokens, prompt_tokens),
        "usage_estimated": estimated,
    }


def request_json_unlocked(
    model: str,
    system: str,
    payload: dict[str, Any],
    max_tokens: int = 10000,
    route: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, int]]:
    route = route or route_for_model(model, payload)
    api_key = os.getenv(str(route["api_key_env"]))
    if not api_key:
        raise RuntimeError(
            f"进程环境缺少 {route['api_key_env']}；密钥不会从文件或命令参数读取。"
        )
    body = {
        "model": route["remote_model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.15,
        "max_tokens": max_tokens,
        "enable_thinking": False,
        "stream": bool(route["stream"]),
    }
    if route["stream"]:
        body["stream_options"] = {"include_usage": True}
    if model not in NO_JSON_MODE_MODELS:
        body["response_format"] = {"type": "json_object"}
    body.update(route.get("body_overrides") or {})
    for field in route.get("omit_body_fields") or []:
        body.pop(field, None)
    last_error: Exception | None = None
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            # Hold the per-model slot for one network attempt only. If an
            # attempt times out, release the slot before backoff so another
            # book can make progress instead of waiting through all retries.
            remote_slot = route_identity(route)
            with model_request_semaphore(
                remote_slot, int(route["max_concurrent_model_requests"])
            ):
                # Each provider has its own capacity. Stable payload sharding
                # lets independent gateways make progress without cache drift.
                with provider_request_semaphore(route):
                    with requests.post(
                        route["api_url"],
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=body,
                        timeout=(API_CONNECT_TIMEOUT_SECONDS, API_READ_TIMEOUT_SECONDS),
                        stream=bool(route["stream"]),
                    ) as resp:
                        if resp.status_code >= 400:
                            excerpt = resp.text[:500].replace(api_key, "[REDACTED]")
                            raise RuntimeError(f"HTTP {resp.status_code}: {excerpt}")
                        if route["stream"]:
                            content, usage = collect_streamed_chat(
                                resp.iter_lines(chunk_size=1),
                                max_seconds=API_STREAM_MAX_SECONDS,
                            )
                        else:
                            response_json = resp.json()
                            choices = response_json.get("choices") or []
                            content = (
                                ((choices[0].get("message") or {}).get("content") or "")
                                if choices else ""
                            )
                            usage = response_json.get("usage") or {}
            if not content:
                raise RuntimeError("流式响应没有返回正文内容")
            normalized_usage = normalize_usage(usage, system, payload, content)
            try:
                parsed = parse_json_content(content)
            except json.JSONDecodeError as exc:
                # A syntactically invalid but otherwise successful response is
                # still billable. Return a nonconforming marker so the caller
                # records usage before its schema retry; never log raw content.
                parsed = {
                    "_invalid_json": True,
                    "parse_error": str(exc),
                    "content_sha256": hashlib.sha256(
                        content.encode("utf-8", errors="replace")
                    ).hexdigest(),
                }
            return parsed, normalized_usage
        except (requests.RequestException, TimeoutError, KeyError, RuntimeError) as exc:
            last_error = exc
            if attempt == MAX_API_ATTEMPTS:
                break
            time.sleep(min(2**attempt, 20))
    append_jsonl(
        REPORTS / "V3 API失败台账.jsonl",
        {
            "failed_at": now_iso(),
            "provider": route["provider"],
            "model": model,
            "remote_model": route["remote_model"],
            "payload_sha256": hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "attempts": MAX_API_ATTEMPTS,
            "error": str(last_error),
        },
    )
    raise RuntimeError(f"API 请求连续失败（{route['provider']}）：{last_error}")


def normalize_response_envelope(
    response: Any,
    expected_ids: list[str] | None = None,
) -> tuple[Any, bool, str | None]:
    """Normalize common list/single-item wrappers without weakening ID checks."""
    if isinstance(response, list):
        return {"items": response}, True, "top_level_array_wrapped_as_items"
    if isinstance(response, dict):
        for key in ("results", "translations", "records", "data"):
            if isinstance(response.get(key), list):
                return {"items": response[key]}, True, f"{key}_array_wrapped_as_items"
    expected = set(expected_ids or [])
    if (
        isinstance(response, dict)
        and not isinstance(response.get("items"), list)
        and response.get("id") in expected
    ):
        return {"items": [response]}, True, "top_level_item_wrapped_as_items"
    return response, False, None


def response_shape_summary(response: Any) -> str:
    """Describe schema shape without logging model text or source content."""
    if not isinstance(response, dict):
        return f"type={type(response).__name__}"
    keys = sorted(str(key)[:48] for key in response.keys())[:20]
    list_fields = sorted(
        str(key)[:48] for key, value in response.items() if isinstance(value, list)
    )[:20]
    return f"type=dict,keys={keys},list_fields={list_fields}"


def sanitize_response_items(
    response: Any,
    payload: dict[str, Any],
    model: str,
    request_sha256: str,
) -> Any:
    """只保留预期 ID；多余无 ID 项记账但不让有效结果整批报废。"""
    expected = [item.get("id") for item in payload.get("items", []) if item.get("id")]
    if not expected:
        return response
    if not isinstance(response, dict) or not isinstance(response.get("items"), list):
        raise ValueError(
            "模型返回缺少 items 数组（" + response_shape_summary(response) + "）"
        )
    by_id: dict[str, dict[str, Any]] = {}
    extras = 0
    for item in response["items"]:
        if not isinstance(item, dict) or item.get("id") not in expected:
            extras += 1
            continue
        sid = item["id"]
        if sid in by_id:
            raise ValueError(f"模型重复返回 ID：{sid}")
        by_id[sid] = item
    missing = [sid for sid in expected if sid not in by_id]
    if missing:
        raise ValueError("模型漏回结果：" + "、".join(missing))
    if extras:
        append_jsonl(
            REPORTS / "V3 API异常台账.jsonl",
            {
                "observed_at": now_iso(),
                "model": model,
                "request_sha256": request_sha256,
                "type": "extra_or_missing_id_items_ignored",
                "count": extras,
            },
        )
    sanitized = dict(response)
    sanitized["items"] = [by_id[sid] for sid in expected]
    return sanitized


def merge_partial_response_items(
    response: Any,
    expected_ids: list[str],
    collected: dict[str, dict[str, Any]],
) -> tuple[list[str], int, int]:
    """Keep valid partial items and return missing IDs, extras and new count."""
    if not isinstance(response, dict) or not isinstance(response.get("items"), list):
        raise ValueError(
            "模型返回缺少 items 数组（" + response_shape_summary(response) + "）"
        )
    expected = set(expected_ids)
    extras = 0
    added = 0
    seen_in_response: set[str] = set()
    for item in response["items"]:
        if not isinstance(item, dict):
            extras += 1
            continue
        sid = item.get("id")
        if sid not in expected or sid in seen_in_response:
            extras += 1
            continue
        seen_in_response.add(sid)
        if sid not in collected:
            added += 1
        collected[sid] = item
    missing = [sid for sid in expected_ids if sid not in collected]
    return missing, extras, added


def request_cache_material_record(
    model: str,
    system: str,
    payload: dict[str, Any],
    max_tokens: int,
    route: dict[str, Any],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "model": model,
        "system": system,
        "payload": payload,
        "max_tokens": max_tokens,
    }
    default_route = normalize_model_route(model, {})
    if route_cache_identity(route) != route_cache_identity(default_route):
        record["route"] = route_cache_identity(route)
    return record


def external_api_cost_total() -> float:
    """Count paid sidecar benchmarks in the same RMB 150 global ceiling."""
    if not EXTERNAL_API_COST_LEDGER.exists():
        return 0.0
    total = 0.0
    for row in read_jsonl(EXTERNAL_API_COST_LEDGER):
        total += float(row.get("estimated_cost_rmb") or 0.0)
    return round(total, 6)


def request_json_cached(
    state: dict[str, Any],
    model: str,
    system: str,
    payload: dict[str, Any],
    max_tokens: int = 10000,
) -> Any:
    """校验后缓存成功响应；相同请求重跑时不重复调用、不重复计费。"""
    route = route_for_model(model, payload)
    material_record = request_cache_material_record(
        model, system, payload, max_tokens, route
    )
    # Preserve every existing SiliconFlow cache key. Non-default providers
    # include only non-secret route identity so cross-provider responses cannot
    # collide.
    material = json.dumps(
        material_record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    cache_key = hashlib.sha256(material.encode("utf-8")).hexdigest()
    cache_path = API_CACHE / f"{cache_key}.json"
    partial_path = API_CACHE / f"{cache_key}.partial.json"
    with FILE_IO_LOCK:
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return sanitize_response_items(cached["response"], payload, model, cache_key)

    expected_items = [item for item in payload.get("items", []) if item.get("id")]
    expected_ids = [item["id"] for item in expected_items]
    collected: dict[str, dict[str, Any]] = {}
    usage_calls: list[dict[str, int]] = []
    if expected_ids:
        with FILE_IO_LOCK:
            if partial_path.exists():
                partial = json.loads(partial_path.read_text(encoding="utf-8"))
                for item in partial.get("items", []):
                    if isinstance(item, dict) and item.get("id") in expected_ids:
                        collected[item["id"]] = item

    last_error: Exception | None = None
    split_invalid_writer_batch = False
    split_writer_remainder = False
    for schema_attempt in range(1, 4):
        missing_ids = [sid for sid in expected_ids if sid not in collected]
        if expected_ids and not missing_ids:
            break

        # In parallel mode multiple requests may already be in flight when one
        # of them updates the total. Reserve conservative headroom before every
        # paid cache miss, including a partial-response completion request.
        with STATE_LOCK:
            spent = float(ensure_usage_state(state).get("estimated_cost_rmb") or 0.0)
            external_spent = external_api_cost_total()
            combined_spent = spent + external_spent
            if combined_spent >= MAX_BUDGET_RMB - BUDGET_PARALLEL_HEADROOM_RMB:
                state["state"] = "budget_blocked"
                state["external_api_cost_rmb"] = external_spent
                state["combined_estimated_cost_rmb"] = round(combined_spent, 6)
                state["updated_at"] = now_iso()
                atomic_json(REPORTS / "V3运行状态.json", state)
                raise RuntimeError(
                    f"预算保护触发：并行安全余量后可用预算不足，正式任务 ¥{spent:.2f}，"
                    f"外部测试 ¥{external_spent:.2f}，"
                    f"上限 ¥{MAX_BUDGET_RMB:.2f}"
                )

        if expected_ids:
            missing_set = set(missing_ids)
            active_payload = dict(payload)
            active_payload["items"] = [
                item for item in expected_items if item["id"] in missing_set
            ]
        else:
            active_payload = payload
        response, usage = request_json(
            model,
            system,
            active_payload,
            max_tokens=max_tokens,
            route=route,
        )
        # 成功返回即已发生费用，先记账，再做结构校验。
        update_usage(state, model, usage, route=route)
        usage_calls.append(usage)
        # A billable response with syntactically invalid JSON cannot become a
        # candidate. Retrying the identical large writer batch repeats the
        # same risk and may consume the output-token cap. Split only this
        # no-usable-content case; child calls receive distinct cache keys and
        # still pass the unchanged strict ID/schema validation below.
        if (
            model == WRITER_MODEL
            and isinstance(response, dict)
            and response.get("_invalid_json")
        ):
            append_jsonl(
                REPORTS / "V3 API异常台账.jsonl",
                {
                    "observed_at": now_iso(),
                    "model": model,
                    "request_sha256": cache_key,
                    "type": "writer_invalid_json_batch_split",
                    "item_count": len(expected_ids),
                    "schema_attempt": schema_attempt,
                    "usage": usage,
                },
            )
            if len(expected_ids) > 1:
                last_error = ValueError("写作模型返回无法解析的 JSON；拆分批次后重试")
                split_invalid_writer_batch = True
                break
            raise RuntimeError("写作模型对单个片段仍返回无法解析的 JSON")
        # Some compatible chat models return a top-level array or a singleton
        # item object instead of wrapping records in {"items": [...]}. Wrap
        # only these shapes; downstream ID and item-schema validation remains
        # strict, so malformed/unknown records cannot be silently accepted.
        response, was_wrapped, wrapper_type = normalize_response_envelope(
            response, expected_ids
        )
        if was_wrapped:
            append_jsonl(
                REPORTS / "V3 API异常台账.jsonl",
                {
                    "observed_at": now_iso(),
                    "model": model,
                    "request_sha256": cache_key,
                    "type": wrapper_type,
                    "count": len(response["items"]),
                },
            )
        try:
            if not expected_ids:
                sanitized = sanitize_response_items(response, payload, model, cache_key)
            else:
                missing, extras, added = merge_partial_response_items(
                    response, expected_ids, collected
                )
                if extras:
                    append_jsonl(
                        REPORTS / "V3 API异常台账.jsonl",
                        {
                            "observed_at": now_iso(),
                            "model": model,
                            "request_sha256": cache_key,
                            "type": "extra_or_duplicate_items_ignored",
                            "count": extras,
                        },
                    )
                if missing:
                    last_error = ValueError("模型漏回结果：" + "、".join(missing))
                    atomic_json(
                        partial_path,
                        {
                            "updated_at": now_iso(),
                            "provider": route["provider"],
                            "model": model,
                            "remote_model": route["remote_model"],
                            "request_sha256": cache_key,
                            "items": [collected[sid] for sid in expected_ids if sid in collected],
                            "missing_ids": missing,
                        },
                    )
                    append_jsonl(
                        REPORTS / "V3 API异常台账.jsonl",
                        {
                            "observed_at": now_iso(),
                            "model": model,
                            "request_sha256": cache_key,
                            "type": "partial_response_saved",
                            "schema_attempt": schema_attempt,
                            "new_items": added,
                            "saved_items": len(collected),
                            "missing_count": len(missing),
                            "usage": usage,
                        },
                    )
                    if model == WRITER_MODEL:
                        split_writer_remainder = True
                        break
                    continue
                sanitized = dict(response)
                sanitized["items"] = [collected[sid] for sid in expected_ids]
        except Exception as exc:
            last_error = exc
            append_jsonl(
                REPORTS / "V3 API异常台账.jsonl",
                {
                    "observed_at": now_iso(),
                    "model": model,
                    "request_sha256": cache_key,
                    "type": "invalid_response_schema",
                    "schema_attempt": schema_attempt,
                    "error": str(exc),
                    "usage": usage,
                },
            )
            continue
        atomic_json(
            cache_path,
            {
                "created_at": now_iso(),
                "provider": route["provider"],
                "model": model,
                "remote_model": route["remote_model"],
                "request_sha256": cache_key,
                "response": sanitized,
                "usage": usage,
                "usage_calls": usage_calls,
            },
        )
        with FILE_IO_LOCK:
            if partial_path.exists():
                partial_path.unlink()
        return sanitized
    if split_invalid_writer_batch or split_writer_remainder:
        missing_ids = [sid for sid in expected_ids if sid not in collected]
        if missing_ids:
            missing_set = set(missing_ids)
            missing_items = [item for item in expected_items if item["id"] in missing_set]
            # Always make recursive progress: an all-invalid response can have
            # no collected IDs, in which case retrying the complete remainder
            # would recreate the exact same cache key indefinitely.
            if len(missing_items) > 1:
                midpoint = len(missing_items) // 2
                child_groups = (missing_items[:midpoint], missing_items[midpoint:])
            else:
                child_groups = (missing_items,)
            for child_items in child_groups:
                child_payload = dict(payload)
                child_payload["items"] = child_items
                child = request_json_cached(state, model, system, child_payload, max_tokens)
                for item in child.get("items") or []:
                    if item.get("id") in missing_set:
                        collected[item["id"]] = item
        # Child calls have enforced exact expected IDs and item schemas. Keep
        # source order and apply strict parent-ID validation once more.
        sanitized = sanitize_response_items(
            {"items": [collected[sid] for sid in expected_ids if sid in collected]},
            payload,
            model,
            cache_key,
        )
        atomic_json(
            cache_path,
            {
                "created_at": now_iso(),
                "provider": route["provider"],
                "model": model,
                "remote_model": route["remote_model"],
                "request_sha256": cache_key,
                "response": sanitized,
                "usage": usage_calls[-1] if usage_calls else {},
                "usage_calls": usage_calls,
                "composed_from_subbatches": True,
            },
        )
        with FILE_IO_LOCK:
            if partial_path.exists():
                partial_path.unlink()
        return sanitized
    if expected_ids and collected:
        missing_ids = [sid for sid in expected_ids if sid not in collected]
        raise RuntimeError("模型部分响应待补全：" + "、".join(missing_ids))
    # Conservative fail-safe for non-writer stages: if a judge or repair
    # endpoint repeatedly returns a billable but unusable JSON shape, do not
    # keep paying identical retries or silently invent meaning.  Preserve the
    # existing candidate for repair, and mark judge results as uncertain so the
    # item remains visible in the review ledger. Writer failures still fail
    # closed because there is no trustworthy candidate to preserve.
    if expected_ids and model in {JUDGE_MODEL, REPAIR_MODEL, ESCALATION_MODEL}:
        fallback_items: list[dict[str, Any]] = []
        for item in expected_items:
            sid = item["id"]
            if model == JUDGE_MODEL:
                fallback_items.append(
                    {
                        "id": sid,
                        "verdict": "uncertain",
                        "confidence": "low",
                        "issues": ["裁判模型未返回可验证的 items 结构"],
                        "uncertainty": ["未完成独立核义，保留候选并进入复核台账"],
                    }
                )
            else:
                fallback_items.append(
                    {
                        "id": sid,
                        "modern_text": item.get("candidate", ""),
                        "confidence": "low",
                        "uncertainty": ["修复模型未返回可验证的 items 结构，保留原候选"],
                    }
                )
        fallback = {"items": fallback_items}
        append_jsonl(
            REPORTS / "V3 API异常台账.jsonl",
            {
                "observed_at": now_iso(),
                "model": model,
                "request_sha256": cache_key,
                "type": "schema_fallback_transparent_uncertainty",
                "count": len(fallback_items),
            },
        )
        atomic_json(
            cache_path,
            {
                "created_at": now_iso(),
                "provider": route["provider"],
                "model": model,
                "remote_model": route["remote_model"],
                "request_sha256": cache_key,
                "response": fallback,
                "usage": usage_calls[-1] if usage_calls else {},
                "usage_calls": usage_calls,
                "transparent_fallback": True,
            },
        )
        return fallback
    raise RuntimeError(f"模型连续返回不合格 JSON 结构：{last_error}")


def configured_model_routes() -> list[tuple[str, dict[str, Any]]]:
    pairs: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for model in (WRITER_MODEL, REPAIR_MODEL, ESCALATION_MODEL, JUDGE_MODEL):
        for route in MODEL_ROUTES.get(model) or [normalize_model_route(model, {})]:
            key = (model, route_identity(route))
            if key not in seen:
                seen.add(key)
                pairs.append((model, route))
    return pairs


def api_check() -> None:
    results: list[dict[str, Any]] = []
    model_lists: dict[tuple[str, str], set[str]] = {}
    for logical_model, route in configured_model_routes():
        api_key = os.getenv(route["api_key_env"])
        if not api_key:
            raise RuntimeError(f"缺少 {route['api_key_env']}")
        models_url = str(route.get("models_url") or "").strip()
        list_key = (models_url, route["api_key_env"])
        if models_url and list_key not in model_lists:
            resp = requests.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=(15, 30),
            )
            if resp.status_code >= 400:
                excerpt = resp.text[:300].replace(api_key, "[REDACTED]")
                raise RuntimeError(
                    f"{route['provider']} 模型列表请求失败 HTTP {resp.status_code}: {excerpt}"
                )
            model_lists[list_key] = {
                row.get("id") for row in (resp.json().get("data") or [])
            }
        if models_url and route["remote_model"] not in model_lists[list_key]:
            raise RuntimeError(
                f"{route['provider']} 模型列表缺少：{route['remote_model']}"
            )
        parsed, usage = request_json(
            logical_model,
            '只输出 JSON 对象 {"ok":true}。',
            {"ping": "V3 多供应商 API 连通性测试"},
            max_tokens=32,
            route=route,
        )
        if not isinstance(parsed, dict) or parsed.get("ok") is not True:
            raise RuntimeError(
                f"{route['provider']} 短文本测试返回异常：{parsed}"
            )
        results.append(
            {
                "provider": route["provider"],
                "logical_model": logical_model,
                "remote_model": route["remote_model"],
                "usage": usage,
            }
        )
    print(json.dumps({"status": "passed", "routes": results}, ensure_ascii=False))


WRITER_SYSTEM = """你是严谨的中国古籍与风水术数白话释读编辑。请将输入块逐句改写成普通中文读者能顺畅理解的现代汉语；日文块翻译成中文。硬规则：
1. 不摘要、不删减、不增加原文没有的结论；保持作者立场。
2. locked_terms 中的专业术语必须原样保留。只有 allowed_glossary 提供的解释才可原样写在术语后的括号中；不得自创释义。未列入 allowed_glossary 的专名或术语只保留原词，不解释其身份、门派、神名、象征或现代对应物。
2a. opaque_terms 是当前证据不足以确定含义的原词。它们必须原样放在中文引号中引用，不得充当已经理解的普通词来造句，也不得拆字猜释；可在句外说明“具体所指不详”。
3. 干支、卦名、爻位、数字、度数、方位、人名、地名、书名、引文、口诀和公式不得擅改。
4. 口诀、赋、经文必须给出逐句白话解释，不能只复制原句。原文会由系统另行附在折叠区，所以 modern_text 只能放白话释读，不得先抄原文再加“现代文解释”。符咒、真言只说明用途和可确认含义，不猜译。
4a. 把繁体改成简体、补标点、调整断句或替换少数字词，都不算白话释读。classical_chinese、japanese 或 mixed 的 modern_text 必须形成现代说明性句子：补出原文明示但省略的主语、谓语和连接关系，使普通读者不看原文也能读懂。
4b. 输出前在内部逐项复核 source 与 modern_text；若古文或日文仍有大段连续照抄，必须先重新改写再输出。不要在 JSON 中写出复核过程。
4c. 对书名页、署名、卷末题记等元数据，可写成“此处题记为……”“本卷署名为……”等现代说明句，并保留原有专名。OCR 残缺时，不得原样粘贴冒充译文；应只说明能够确认的信息，并在 uncertainty 标出缺字或错乱。
4d. items 按原书顺序排列。遇到孤立短句、跨页残句或卷末题记，应参考同一批次相邻 item 判断承接关系，但每个 modern_text 只能改写自己的 source，不得把相邻 item 翻译、合并或重复进去。
5. OCR 可疑或原义不确定时，不得脑补；在 uncertainty 中指出，并在 modern_text 中使用保守表达。
6. 不得把原文中的专名擅自认定为某流派、人物、神名、数理含义或现代概念。例如原文只写“浮黎”“元女”“庚甲”“元钧”，就只保留这些词；除非原文明示，不得扩写为“浮黎一脉”“九天元女”“六个甲子”“根本度量”等。必要时可在句外用“此处具体所指不详”作保守说明。
7. kind=heading 时，modern_text 必须保留原来的 Markdown 标题级别（# 数量相同），标题术语原样保留，必要时在破折号后增加白话说明。
8. kind=html 时，modern_text 应把表内文字改成易懂中文并完整保留关键数据；可输出 Markdown 表格或分项列表，不得只写摘要。
9. kind=toc 时，只翻译日文目录标题；必须保持一项一行、原顺序、层级、点线和所有页码，不得改写成摘要或连续段落。
10. 不要返回 term_notes；术语注释由系统依据 approved glossary 确定性生成，重复输出会被丢弃。
11. 正例：source=“見地可以知人，而察來驗于巳往”时，可写“观察地势能够推知人的情况；要判断将来的变化，也可以用已经发生的事情来验证。”反例“见地可以知人，而察来验于已往”只是转成简体并加标点，必须重写。
12. 只输出 JSON 对象：{"items":[{"id":"...","language":"classical_chinese|modern_chinese|japanese|mixed","content_type":"...","action":"rewrite|translate|preserve|uncertain","modern_text":"...","confidence":"high|medium|low","uncertainty":["..."]}]}。不得输出 Markdown 代码围栏。"""

JUDGE_SYSTEM = """你是独立的古籍与风水术数白话核义审校员，只负责判错，绝对不能改稿。V3 的目标是“普通读者能读懂的白话释读”，不是逐字直译，也不要求保留古文的简洁风格。逐项比较 source 和 candidate，检查漏译、反义、专业术语误换、数字/干支/卦象/方位变化、日文误译、把推测写成事实，以及古文/日文没有真正转换成现代中文。

判定边界：
1. 为形成现代汉语句子而补出主语、谓语、连接词，以及不改变含义的浅显释义，不算增译。例如“焕乎五行”释为“使五行焕发光彩”可以接受。
2. 对含混短语，candidate 可以保留原短语并明确说“具体所指不详”“原文未明”；这种风险标注不是增译，也不应要求删除。若 candidate 把不确定解释写成确定事实，才是问题。
3. 允许引用必要的短语来说明歧义，但不得重复整段原文。原文会由系统另附在折叠区。
4. 只有 allowed_glossary 中的术语定义可以作为确定解释加入；其他含混专名不得认定为某流派、人物、神名、数理含义或现代概念。locked_terms 必须保留；opaque_terms 必须原样处在引号引用范围内，不能被候选句赋予确定含义。
5. verdict=accept 表示释读准确、完整、通俗且无无依据扩写；即使原文存在已明确标注的歧义，也可以 accept 并在 uncertainty 中列出。可修复的语义风险用 revise；OCR 或原文损坏导致连保守释读都无法成立时才用 uncertain。
6. kind=toc 时逐行核对标题、原顺序、层级、点线和页码；不得接受摘要化、合并行或页码遗漏。
只输出 JSON 对象：{"items":[{"id":"...","verdict":"accept|revise|uncertain","confidence":"high|medium|low","issues":["..."],"uncertainty":["..."]}]}。不得包含 final_text，不得输出 Markdown 代码围栏。"""

REPAIR_SYSTEM = """你是古籍白话释读修复编辑。输入包含 source、上一版 candidate、审核 issues、locked_terms、opaque_terms 和 allowed_glossary。只修复已指出的问题，同时逐句覆盖原意。硬规则：
1. modern_text 只能是白话释读，不得复制整段原文，也不得写“原文如下”“现代文解释”。
2. 不得加入 source 没有的门派、人物身份、神名、象征、数理含义、因果或现代概念。
3. 未列入 allowed_glossary 的专名和术语只保留原词，不加括号定义；如果一个短语整体含义不稳，就用引号保留完整短语，并在现代说明句中写“具体所指不详”。不要拆开这个短语再逐字猜释。保留不确定短语不等于保留整段古文。
3a. opaque_terms 中每个词必须逐字保留在中文引号引用范围内；不得写成“浮黎一脉”、不得把“鳌极”解释成巨鳌的根基、不得把“鳌布”当作执行动作的对象，也不得写“‘虎贲’指古代军队”这类未经批准的定义。可以引用包含该词的较完整原短语，然后说明具体所指不详。
4. locked_terms、数字、干支、卦名、爻位、度数、方位、人名、地名、书名、口诀和公式不得遗漏或擅改。
5. 日文必须译成中文；古文必须改成现代说明性散文，增加必要的主语、谓语、连接词和判断词，不得继续模仿四字韵文，也不得摘要。
6. 处理示例：
   - source=“八卦八门，六甲天书” → “这部书所讲的内容涉及八卦、八门和六甲天书。”
   - source=“元女降质” → “文中又提到‘元女降质’，但这一短语的具体所指不详。”
   - source=“御虎贲之强兵” → “它还能用于‘御虎贲之强兵’；这里的‘御’究竟指抵御还是统御，原文未明。”
   - source=“四极鳌布”且无法可靠解释 → “文中还说‘四极鳌布’，具体含义不详。”
   反例：“八卦八门，六甲天书。在始青之下，包罗万象。”仍是古文句法，不能采用。
7. kind=toc 时只修复日文标题翻译；一项一行、原顺序、点线和所有页码必须原样保留，不得摘要。
8. context_before/context_after 只用于理解 source；修复结果只能覆盖 source，不得把上下文拼入 modern_text。
9. 只输出 JSON 对象：{"items":[{"id":"...","modern_text":"...","confidence":"high|medium|low","uncertainty":["..."]}]}。不得输出 Markdown 代码围栏。"""


def estimate_cost(
    model: str,
    usage: dict[str, int],
    route: dict[str, Any] | None = None,
) -> float:
    route_prices = (route or {}).get("prices") or {}
    prices = route_prices or PRICE.get(model, {"input": 0.0, "output": 0.0})
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    cached_tokens = min(
        int(usage.get("cached_prompt_tokens") or 0), prompt_tokens
    )
    uncached_tokens = prompt_tokens - cached_tokens
    cached_price = prices.get("cached_input", prices.get("input", 0.0))
    return (
        uncached_tokens / 1_000_000 * prices.get("input", 0.0)
        + cached_tokens / 1_000_000 * cached_price
        + int(usage.get("completion_tokens") or 0)
        / 1_000_000
        * prices.get("output", 0.0)
    )


def load_state() -> dict[str, Any]:
    path = REPORTS / "V3运行状态.json"
    if not path.exists():
        raise RuntimeError("请先运行 prepare。")
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_usage_state(state: dict[str, Any]) -> dict[str, Any]:
    """Keep checkpoint recovery safe even if an older worker wrote sparse state."""
    usage = state.setdefault("usage", {})
    usage.setdefault("prompt_tokens", 0)
    usage.setdefault("completion_tokens", 0)
    usage.setdefault("cached_prompt_tokens", 0)
    usage.setdefault("estimated_cost_rmb", 0.0)
    usage.setdefault("by_provider", {})
    return usage


def is_transient_api_failure(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "connectionreseterror",
        "connection aborted",
        "max retries exceeded",
        "read timed out",
        "connect timeout",
        "temporarily unavailable",
        "service overloaded",
        "rate limit",
        "http 429",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "sse 流式响应超过总时长上限",
        "模型部分响应待补全",
        # A syntactically invalid singleton writer response has no usable
        # candidate to cache, but it is still an API formatting failure rather
        # than a content-level hard error. Let the bounded book restart policy
        # retry it from the stable-ID checkpoint instead of abandoning the
        # remainder of the book.
        "写作模型对单个片段仍返回无法解析的 json",
    )
    return any(marker in text for marker in markers)


def update_usage(
    state: dict[str, Any],
    model: str,
    usage: dict[str, int],
    route: dict[str, Any] | None = None,
) -> None:
    route = route or route_for_model(model)
    call_cost = estimate_cost(model, usage, route=route)
    with STATE_LOCK:
        ensure_usage_state(state)
        state["usage"]["prompt_tokens"] += usage["prompt_tokens"]
        state["usage"]["completion_tokens"] += usage["completion_tokens"]
        state["usage"]["cached_prompt_tokens"] = int(
            state["usage"].get("cached_prompt_tokens") or 0
        ) + int(usage.get("cached_prompt_tokens") or 0)
        state["usage"]["estimated_cost_rmb"] = round(
            state["usage"]["estimated_cost_rmb"] + call_cost, 6
        )
        external_spent = external_api_cost_total()
        state["external_api_cost_rmb"] = external_spent
        state["combined_estimated_cost_rmb"] = round(
            float(state["usage"]["estimated_cost_rmb"]) + external_spent, 6
        )
        provider_usage = state["usage"].setdefault("by_provider", {})
        provider_row = provider_usage.setdefault(
            route["provider"],
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_prompt_tokens": 0,
                "estimated_cost_rmb": 0.0,
            },
        )
        provider_row["prompt_tokens"] += usage["prompt_tokens"]
        provider_row["completion_tokens"] += usage["completion_tokens"]
        provider_row["cached_prompt_tokens"] += int(
            usage.get("cached_prompt_tokens") or 0
        )
        provider_row["estimated_cost_rmb"] = round(
            float(provider_row["estimated_cost_rmb"]) + call_cost, 6
        )
        # A paid response proves the current API path is healthy. Do not let a
        # failure message inherited from an earlier process survive indefinitely.
        state.pop("last_error", None)
        state["updated_at"] = now_iso()
        if state["combined_estimated_cost_rmb"] > MAX_BUDGET_RMB:
            state["state"] = "budget_blocked"
            atomic_json(REPORTS / "V3运行状态.json", state)
            raise RuntimeError(f"预算保护触发：估算费用超过 ¥{MAX_BUDGET_RMB:.2f}")
        # 每次付费调用后立即落盘，异常退出也不会丢失费用统计。
        atomic_json(REPORTS / "V3运行状态.json", state)


def normalize_items(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict) and isinstance(response.get("items"), list):
        return response["items"]
    if isinstance(response, list):
        return response
    raise ValueError("模型返回缺少 items 数组")


def needs_semantic_judge(writer_item: dict[str, Any]) -> bool:
    """Modern Chinese is copied verbatim, so judging a discarded rewrite is wasteful."""
    return writer_item.get("language") != "modern_chinese"


def build_short_segment_contexts(
    rows: list[dict[str, Any]],
    short_limit: int = 40,
    context_limit: int = 100,
) -> dict[str, dict[str, str]]:
    """Attach nearby source only to help interpret isolated short/OCR fragments.

    Context never changes the stable segment ID and is never rendered as the
    segment's answer.  Use the closest visible block in each direction; this is
    enough to reconnect many cross-page fragments without multiplying tokens.
    """
    contexts: dict[str, dict[str, str]] = {}

    def nearest(index: int, step: int) -> str:
        cursor = index + step
        while 0 <= cursor < len(rows):
            neighbor = rows[cursor]
            visible = semantic_visible_text(str(neighbor.get("source") or "")).strip()
            if visible and neighbor.get("kind") not in {"image", "image_caption"}:
                return visible[-context_limit:] if step < 0 else visible[:context_limit]
            cursor += step
        return ""

    for index, row in enumerate(rows):
        source = semantic_visible_text(str(row.get("source") or "")).strip()
        if not row.get("translatable") or len(source) >= short_limit:
            continue
        context: dict[str, str] = {}
        before = nearest(index, -1)
        after = nearest(index, 1)
        if before:
            context["context_before"] = before
        if after:
            context["context_after"] = after
        if context:
            contexts[row["id"]] = context
    return contexts


def latest_result_records() -> dict[str, dict[str, Any]]:
    """按 JSONL 顺序取每个片段的最后一条记录，支持失败后安全重跑。"""
    latest: dict[str, dict[str, Any]] = {}
    for path in sorted(RESULTS.glob("book*.jsonl")):
        for row in read_jsonl(path):
            if row.get("id"):
                latest[row["id"]] = row
    return latest


def is_complete_result(row: dict[str, Any], expected_sha256: str | None = None) -> bool:
    """只有已核义、原文哈希匹配且实际含有释读文本的记录才算完成。

    历史网关偶尔会返回结构完整但 modern_text 为空的记录；若只看
    status=judged，断点恢复会永久跳过这些硬错误。
    """
    if row.get("status") != "judged":
        return False
    if expected_sha256 is not None and row.get("source_sha256") != expected_sha256:
        return False
    modern_text = row.get("modern_text")
    return isinstance(modern_text, str) and bool(modern_text.strip())


def is_expected_complete_result(
    row: dict[str, Any], expected_hashes: dict[str, str]
) -> bool:
    """只接受仍属于现行分段基线、且哈希完整匹配的完成记录。"""
    segment_id = row.get("id")
    return (
        isinstance(segment_id, str)
        and segment_id in expected_hashes
        and is_complete_result(row, expected_hashes[segment_id])
    )


def completed_result_count_for_book(book_no: int) -> int:
    """Count current-baseline results for one book using stable ID + full hash.

    The per-book transient retry budget is intended to stop a request that is
    making no headway.  A long book can nevertheless complete many valid
    batches between intermittent gateway failures.  Counting only current
    stable IDs and matching source hashes lets the retry wrapper distinguish
    real progress from repeated failures without trusting the aggregate state
    file (which is shared by multiple book workers).
    """
    segments = read_jsonl(SEGMENTS / f"book{book_no:03d}.jsonl")
    expected_hashes = {
        row["id"]: row["source_sha256"]
        for row in segments
        if row.get("translatable")
    }
    latest: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(RESULTS / f"book{book_no:03d}.jsonl"):
        segment_id = row.get("id")
        if isinstance(segment_id, str):
            latest[segment_id] = row
    return sum(
        1
        for row in latest.values()
        if is_expected_complete_result(row, expected_hashes)
    )


def expected_translatable_ids() -> set[str]:
    return {
        row["id"]
        for path in SEGMENTS.glob("book*.jsonl")
        for row in read_jsonl(path)
        if row.get("translatable")
    }


def expected_translatable_hashes() -> dict[str, str]:
    return {
        row["id"]: row["source_sha256"]
        for path in SEGMENTS.glob("book*.jsonl")
        for row in read_jsonl(path)
        if row.get("translatable")
    }


def run_book(
    book_no: int,
    limit_batches: int | None = None,
    only_ids: set[str] | None = None,
    shared_state: dict[str, Any] | None = None,
) -> None:
    state = shared_state if shared_state is not None else load_state()
    with STATE_LOCK:
        state["state"] = "running"
        state.pop("last_transient_error", None)
        state.pop("transient_retry_attempt", None)
        active = set(state.get("current_books") or [])
        active.add(book_no)
        state["current_books"] = sorted(active)
        state["current_book"] = min(active)
        state["updated_at"] = now_iso()
        atomic_json(REPORTS / "V3运行状态.json", state)
    glossary = load_glossary()
    seg_path = SEGMENTS / f"book{book_no:03d}.jsonl"
    all_rows = read_jsonl(seg_path)
    context_by_id = build_short_segment_contexts(all_rows)
    rows = [
        r for r in all_rows
        if r["translatable"] and (only_ids is None or r["id"] in only_ids)
    ]
    if only_ids is not None:
        found = {r["id"] for r in rows}
        missing = sorted(only_ids - found)
        if missing:
            raise RuntimeError("指定片段不存在或不可翻译：" + "、".join(missing))
    out_path = RESULTS / f"book{book_no:03d}.jsonl"
    source_hashes = {r["id"]: r["source_sha256"] for r in rows}
    completed = {
        r["id"] for r in read_jsonl(out_path)
        if is_expected_complete_result(r, source_hashes)
    }
    pending = [r for r in rows if r["id"] not in completed]
    batch_count = 0
    for batch in batches(pending, MAX_BATCH_CHARS):
        if limit_batches is not None and batch_count >= limit_batches:
            break
        batch_count += 1
        writer_payload = {
            "book_no": book_no,
            "items": [
                {
                    "id": r["id"],
                    "language_hint": r["language_hint"],
                    "kind": r["kind"],
                    "locked_terms": r["locked_terms"],
                    "opaque_terms": r.get("opaque_terms") or [],
                    "allowed_glossary": allowed_glossary_for(r["locked_terms"], glossary),
                    "source": r["source"],
                }
                for r in batch
            ],
        }
        written = request_json_cached(state, WRITER_MODEL, WRITER_SYSTEM, writer_payload)
        written_items = {r["id"]: r for r in normalize_items(written)}
        missing_writer_ids = [r["id"] for r in batch if r["id"] not in written_items]
        if missing_writer_ids:
            raise RuntimeError("写作模型漏回结果：" + "、".join(missing_writer_ids))

        repair_rounds = {r["id"]: 0 for r in batch}
        repair_models_used: dict[str, list[str]] = {r["id"]: [] for r in batch}

        # Deterministic violations are cheaper and safer to catch before the
        # independent semantic judge. Repair them first so DeepSeek does not
        # spend a full review on a candidate that is already known to fail.
        for local_round in range(1, MAX_REPAIR_ROUNDS + 1):
            local_targets: list[dict[str, Any]] = []
            local_issue_map: dict[str, list[str]] = {}
            for source in batch:
                sid = source["id"]
                writer = written_items[sid]
                if writer.get("language") == "modern_chinese":
                    continue
                check = local_quality_issues(
                    source["source"],
                    writer.get("modern_text", ""),
                    writer.get("language"),
                    source["locked_terms"],
                    allowed_glossary_for(source["locked_terms"], glossary),
                    source.get("opaque_terms") or [],
                )
                hard_messages = hard_issue_messages(check)
                if hard_messages and repair_rounds[sid] < MAX_REPAIR_ROUNDS:
                    local_targets.append(source)
                    local_issue_map[sid] = hard_messages
            if not local_targets:
                break
            local_payload = {
                "book_no": book_no,
                "repair_phase": "pre_judge_local",
                "repair_round": local_round,
                "items": [
                    {
                        "id": source["id"],
                        "kind": source.get("kind"),
                        "source": source["source"],
                        "candidate": written_items[source["id"]].get("modern_text", ""),
                        "issues": local_issue_map[source["id"]],
                        "locked_terms": source["locked_terms"],
                        "opaque_terms": source.get("opaque_terms") or [],
                        "allowed_glossary": allowed_glossary_for(source["locked_terms"], glossary),
                        **context_by_id.get(source["id"], {}),
                    }
                    for source in local_targets
                ],
            }
            local_model = REPAIR_MODEL if local_round == 1 else ESCALATION_MODEL
            repaired = request_json_cached(
                state, local_model, REPAIR_SYSTEM, local_payload
            )
            repaired_items = {r["id"]: r for r in normalize_items(repaired)}
            missing_repair_ids = [
                r["id"] for r in local_targets if r["id"] not in repaired_items
            ]
            if missing_repair_ids:
                raise RuntimeError("本地硬错误修复模型漏回结果：" + "、".join(missing_repair_ids))
            for source in local_targets:
                sid = source["id"]
                repaired_item = repaired_items[sid]
                written_items[sid]["modern_text"] = repaired_item.get("modern_text", "")
                written_items[sid]["confidence"] = repaired_item.get("confidence")
                written_items[sid]["uncertainty"] = repaired_item.get("uncertainty") or []
                repair_rounds[sid] += 1
                repair_models_used[sid].append(local_model)

        def build_judge_payload(targets: list[dict[str, Any]]) -> dict[str, Any]:
            return {
                "book_no": book_no,
                "items": [
                    {
                        "id": r["id"],
                        "source": r["source"],
                        "kind": r.get("kind"),
                        "candidate": written_items[r["id"]].get("modern_text", ""),
                        "locked_terms": r["locked_terms"],
                        "opaque_terms": r.get("opaque_terms") or [],
                        "allowed_glossary": allowed_glossary_for(r["locked_terms"], glossary),
                        "writer_confidence": written_items[r["id"]].get("confidence"),
                        "writer_uncertainty": written_items[r["id"]].get("uncertainty", []),
                    }
                    for r in targets
                ],
            }

        judge_targets = [
            r for r in batch if needs_semantic_judge(written_items[r["id"]])
        ]
        judged_items = {
            r["id"]: {
                "id": r["id"],
                "verdict": "accept",
                "confidence": "high",
                "issues": [],
                "uncertainty": [],
            }
            for r in batch
            if not needs_semantic_judge(written_items[r["id"]])
        }
        if judge_targets:
            judge_payload = build_judge_payload(judge_targets)
            judged = request_json_cached(state, JUDGE_MODEL, JUDGE_SYSTEM, judge_payload)
            judged_items.update({r["id"]: r for r in normalize_items(judged)})
        missing_judge_ids = [
            r["id"] for r in judge_targets if r["id"] not in judged_items
        ]
        if missing_judge_ids:
            raise RuntimeError("核义模型漏回结果：" + "、".join(missing_judge_ids))

        initial_verdicts = {
            sid: normalize_judge_verdict(judged_items[sid].get("verdict"))
            for sid in judged_items
        }
        semantic_repairs = {r["id"]: 0 for r in batch}

        # The semantic judge never supplies final prose. Give each semantic
        # objection one automatic rewrite attempt. Later rounds are reserved
        # for deterministic hard errors; unresolved meaning stays visible in
        # the review ledger instead of being repeatedly rewritten into drift.
        for semantic_round in range(1, MAX_REPAIR_ROUNDS + 1):
            repair_targets: list[dict[str, Any]] = []
            repair_issue_map: dict[str, list[str]] = {}
            semantic_target_ids: set[str] = set()
            for source in batch:
                sid = source["id"]
                writer = written_items[sid]
                if writer.get("language") == "modern_chinese":
                    continue
                check = local_quality_issues(
                    source["source"],
                    writer.get("modern_text", ""),
                    writer.get("language"),
                    source["locked_terms"],
                    allowed_glossary_for(source["locked_terms"], glossary),
                    source.get("opaque_terms") or [],
                )
                hard_messages = hard_issue_messages(check)
                semantic_needed = (
                    judged_items[sid].get("verdict", "uncertain") != "accept"
                    and semantic_repairs[sid] < 1
                )
                if (
                    repair_rounds[sid] < MAX_REPAIR_ROUNDS
                    and (semantic_needed or hard_messages)
                ):
                    repair_targets.append(source)
                    repair_issue_map[sid] = normalize_string_list(
                        [judged_items[sid].get("issues") or [], hard_messages]
                    )
                    if semantic_needed:
                        semantic_target_ids.add(sid)
            if not repair_targets:
                break

            repair_payload = {
                "book_no": book_no,
                "repair_phase": "post_judge",
                "repair_round": semantic_round,
                "items": [
                    {
                        "id": source["id"],
                        "kind": source.get("kind"),
                        "source": source["source"],
                        "candidate": written_items[source["id"]].get("modern_text", ""),
                        "issues": repair_issue_map[source["id"]],
                        "locked_terms": source["locked_terms"],
                        "opaque_terms": source.get("opaque_terms") or [],
                        "allowed_glossary": allowed_glossary_for(source["locked_terms"], glossary),
                        **context_by_id.get(source["id"], {}),
                    }
                    for source in repair_targets
                ],
            }
            active_repair_model = (
                REPAIR_MODEL
                if all(repair_rounds[source["id"]] == 0 for source in repair_targets)
                else ESCALATION_MODEL
            )
            repaired = request_json_cached(
                state, active_repair_model, REPAIR_SYSTEM, repair_payload
            )
            repaired_items = {r["id"]: r for r in normalize_items(repaired)}
            missing_repair_ids = [r["id"] for r in repair_targets if r["id"] not in repaired_items]
            if missing_repair_ids:
                raise RuntimeError("修复模型漏回结果：" + "、".join(missing_repair_ids))
            for source in repair_targets:
                sid = source["id"]
                repaired_item = repaired_items[sid]
                written_items[sid]["modern_text"] = repaired_item.get("modern_text", "")
                written_items[sid]["confidence"] = repaired_item.get("confidence")
                written_items[sid]["uncertainty"] = repaired_item.get("uncertainty") or []
                repair_rounds[sid] += 1
                if sid in semantic_target_ids:
                    semantic_repairs[sid] += 1
                repair_models_used[sid].append(active_repair_model)

            rejudged = request_json_cached(
                state,
                JUDGE_MODEL,
                JUDGE_SYSTEM,
                build_judge_payload(repair_targets),
            )
            rejudged_items = {r["id"]: r for r in normalize_items(rejudged)}
            missing_rejudge_ids = [r["id"] for r in repair_targets if r["id"] not in rejudged_items]
            if missing_rejudge_ids:
                raise RuntimeError("复审核义模型漏回结果：" + "、".join(missing_rejudge_ids))
            judged_items.update(rejudged_items)

        for source in batch:
            sid = source["id"]
            writer = written_items[sid]
            judge = judged_items[sid]
            # 裁判永不改稿；最终正文只能来自写作/修复模型。
            final_text = writer.get("modern_text") or ""
            preserved_modern_source = writer.get("language") == "modern_chinese"
            if preserved_modern_source:
                final_text = source["source"]
            check = local_quality_issues(
                source["source"],
                final_text,
                writer.get("language"),
                source["locked_terms"],
                allowed_glossary_for(source["locked_terms"], glossary),
                source.get("opaque_terms") or [],
            )
            uncertainty = normalize_string_list(
                [writer.get("uncertainty") or [], judge.get("uncertainty") or []]
            )
            local_issues = hard_issue_messages(check)
            issues = normalize_string_list([judge.get("issues") or [], local_issues])
            verdict = normalize_judge_verdict(judge.get("verdict"))
            if preserved_modern_source:
                verdict = "accept"
                issues = []
                uncertainty = []
            elif local_issues:
                verdict = "uncertain"
                uncertainty.append("本地硬校验仍未通过，已记录供后续自动处理或人工核对。")
            elif verdict == "revise":
                uncertainty.append(
                    f"{repair_rounds[sid]}轮自动修复后核义模型仍建议修订，已保守记录。"
                )
            # Model responses can still contain nested arrays after the
            # earlier normalization (for example when a cached legacy row is
            # merged).  Normalize again instead of using the raw values as
            # dictionary keys; this keeps one malformed item from terminating
            # the long-running book worker.
            uncertainty = normalize_string_list(uncertainty)
            approved_term_notes = [
                {"term": term, "note": glossary[term]}
                for term in source["locked_terms"]
                if term in glossary and term in final_text
            ]
            record = {
                "id": sid,
                "status": "judged",
                "book_no": book_no,
                "source_sha256": source["source_sha256"],
                "source": source["source"],
                "language": writer.get("language"),
                "content_type": writer.get("content_type"),
                "action": writer.get("action"),
                "modern_text": final_text,
                "term_notes": approved_term_notes,
                "writer_confidence": writer.get("confidence"),
                "initial_judge_verdict": initial_verdicts.get(sid),
                "repair_rounds": repair_rounds[sid],
                "repair_models_used": repair_models_used[sid],
                "model_judge_verdict": judge.get("verdict", "uncertain"),
                "judge_verdict": verdict,
                "judge_confidence": judge.get("confidence"),
                "judge_issues": judge.get("issues") or [],
                "local_issues": local_issues,
                "issues": issues,
                "uncertainty": uncertainty,
                **check,
                "preserved_modern_source": preserved_modern_source,
                "writer_model": WRITER_MODEL,
                "repair_model": REPAIR_MODEL,
                "escalation_model": ESCALATION_MODEL,
                "judge_model": JUDGE_MODEL,
                "generated_at": now_iso(),
            }
            append_jsonl(out_path, record)
            if verdict != "accept" or uncertainty:
                append_jsonl(REPORTS / "V3待人工复核台账.jsonl", record)
        latest_records = latest_result_records()
        expected_hashes = expected_translatable_hashes()
        all_completed = sum(
            1 for sid, r in latest_records.items()
            if is_expected_complete_result(r, expected_hashes)
        )
        all_uncertain = sum(
            1 for sid, r in latest_records.items()
            if is_expected_complete_result(r, expected_hashes)
            and (r.get("judge_verdict") != "accept" or r.get("uncertainty"))
        )
        with STATE_LOCK:
            retries = dict(state.get("transient_retries") or {})
            retries.pop(str(book_no), None)
            state["transient_retries"] = retries
            state.update(
                {
                    "state": "running",
                    "updated_at": now_iso(),
                    "segments_writer_completed": all_completed,
                    "segments_judged": all_completed,
                    "segments_uncertain": all_uncertain,
                }
            )
            atomic_json(REPORTS / "V3运行状态.json", state)
        print(f"book{book_no:03d}: +{len(batch)}，累计 {all_completed}/{state['segments_total']}")
    with STATE_LOCK:
        active = set(state.get("current_books") or [])
        active.discard(book_no)
        state["current_books"] = sorted(active)
        if active:
            state["current_book"] = min(active)
        state["updated_at"] = now_iso()
        atomic_json(REPORTS / "V3运行状态.json", state)
    if limit_batches is not None or only_ids is not None:
        state = load_state()
        state["state"] = "pilot_complete"
        state["updated_at"] = now_iso()
        atomic_json(REPORTS / "V3运行状态.json", state)


def revalidate_results() -> None:
    """仅重算本地硬规则；不调用模型、不改写正文、不增加费用。"""
    glossary = load_glossary()
    segment_map = {
        row["id"]: row
        for path in sorted(SEGMENTS.glob("book*.jsonl"))
        for row in read_jsonl(path)
    }
    changed = 0
    for path in sorted(RESULTS.glob("book*.jsonl")):
        rows = read_jsonl(path)
        updated_rows: list[dict[str, Any]] = []
        for row in rows:
            source = segment_map.get(row.get("id"))
            if not source or row.get("status") != "judged":
                updated_rows.append(row)
                continue
            check = local_quality_issues(
                source["source"],
                row.get("modern_text", ""),
                row.get("language"),
                source.get("locked_terms") or [],
                allowed_glossary_for(source.get("locked_terms") or [], glossary),
                source.get("opaque_terms") or [],
            )
            local_issues = hard_issue_messages(check)
            judge_issues = row.get("judge_issues")
            if judge_issues is None:
                judge_issues = [
                    issue for issue in (row.get("issues") or [])
                    if not issue.startswith(LOCAL_ISSUE_PREFIXES)
                ]
            uncertainty = [
                note for note in (row.get("uncertainty") or [])
                if note != "本地硬校验仍未通过，已记录供后续自动处理或人工核对。"
            ]
            model_verdict = row.get("model_judge_verdict") or row.get("judge_verdict")
            verdict = normalize_judge_verdict(model_verdict)
            if row.get("preserved_modern_source"):
                verdict = "accept"
                local_issues = []
            elif local_issues:
                verdict = "uncertain"
                uncertainty.append("本地硬校验仍未通过，已记录供后续自动处理或人工核对。")
            row.update(check)
            row["judge_issues"] = judge_issues
            row["local_issues"] = local_issues
            row["issues"] = normalize_string_list([judge_issues, local_issues])
            row["uncertainty"] = normalize_string_list(uncertainty)
            row["judge_verdict"] = verdict
            row["revalidated_at"] = now_iso()
            updated_rows.append(row)
            changed += 1
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in updated_rows),
            encoding="utf-8",
            newline="\n",
        )
        tmp.replace(path)

    latest = latest_result_records()
    expected_ids = expected_translatable_ids()
    state = load_state()
    state["segments_writer_completed"] = sum(
        1 for sid, row in latest.items()
        if sid in expected_ids and is_complete_result(row)
    )
    state["segments_judged"] = state["segments_writer_completed"]
    state["segments_uncertain"] = sum(
        1 for sid, row in latest.items()
        if sid in expected_ids
        and is_complete_result(row)
        and (row.get("judge_verdict") != "accept" or row.get("uncertainty"))
    )
    state["updated_at"] = now_iso()
    atomic_json(REPORTS / "V3运行状态.json", state)
    print(f"离线重校验完成：{changed} 条；API 调用 0；新增费用 ¥0")


def migrate_archived_results(source_dir: Path) -> dict[str, Any]:
    """按原文哈希迁移旧 ID 结果；只接受唯一匹配且本地硬校验为零的记录。"""
    source_dir = source_dir.resolve()
    v3_root = V3.resolve()
    if not str(source_dir).lower().startswith(str(v3_root).lower()):
        raise RuntimeError("迁移源必须位于 V3 目录内")
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)

    glossary = load_glossary()
    candidates: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for path in sorted(SEGMENTS.glob("book*.jsonl")):
        for segment in read_jsonl(path):
            if not segment.get("translatable"):
                continue
            key = (int(segment["book_no"]), segment["source_sha256"])
            candidates.setdefault(key, []).append(segment)

    migrated_by_book: dict[int, dict[str, dict[str, Any]]] = {}
    stats = {
        "source_dir": str(source_dir),
        "examined": 0,
        "migrated": 0,
        "skipped_nonjudged": 0,
        "skipped_no_match": 0,
        "skipped_ambiguous": 0,
        "skipped_source_mismatch": 0,
        "skipped_hard_error": 0,
    }
    for path in sorted(source_dir.glob("book*.jsonl")):
        for row in read_jsonl(path):
            stats["examined"] += 1
            if row.get("status") != "judged":
                stats["skipped_nonjudged"] += 1
                continue
            key = (int(row.get("book_no") or 0), row.get("source_sha256") or "")
            matches = candidates.get(key, [])
            if not matches:
                stats["skipped_no_match"] += 1
                continue
            exact = [segment for segment in matches if segment["source"] == row.get("source")]
            if len(exact) != 1:
                stats["skipped_ambiguous"] += 1
                continue
            segment = exact[0]
            if hashlib.sha256(row["source"].encode("utf-8")).hexdigest() != segment["source_sha256"]:
                stats["skipped_source_mismatch"] += 1
                continue
            check = local_quality_issues(
                segment["source"],
                row.get("modern_text", ""),
                row.get("language"),
                segment.get("locked_terms") or [],
                allowed_glossary_for(segment.get("locked_terms") or [], glossary),
                segment.get("opaque_terms") or [],
            )
            local_issues = hard_issue_messages(check)
            if local_issues:
                stats["skipped_hard_error"] += 1
                continue
            migrated = dict(row)
            migrated["migrated_from_id"] = row["id"]
            migrated["id"] = segment["id"]
            migrated["source_sha256"] = segment["source_sha256"]
            migrated["model_judge_verdict"] = (
                row.get("model_judge_verdict") or row.get("judge_verdict", "uncertain")
            )
            migrated["judge_verdict"] = migrated["model_judge_verdict"]
            migrated.update(check)
            migrated["local_issues"] = []
            migrated["issues"] = normalize_string_list(
                migrated.get("judge_issues") or row.get("issues") or []
            )
            migrated["uncertainty"] = [
                note for note in (row.get("uncertainty") or [])
                if note != "本地硬校验仍未通过，已记录供后续自动处理或人工核对。"
            ]
            migrated["migrated_at"] = now_iso()
            migrated_by_book.setdefault(segment["book_no"], {})[segment["id"]] = migrated
            stats["migrated"] += 1

    for book_no, migrated_rows in migrated_by_book.items():
        out_path = RESULTS / f"book{book_no:03d}.jsonl"
        existing = {row["id"]: row for row in read_jsonl(out_path)}
        existing.update(migrated_rows)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in existing.values()),
            encoding="utf-8",
            newline="\n",
        )
        for row in migrated_rows.values():
            if row.get("judge_verdict") != "accept" or row.get("uncertainty"):
                append_jsonl(REPORTS / "V3待人工复核台账.jsonl", row)

    stats["generated_at"] = now_iso()
    atomic_json(REPORTS / "V3稳定ID结果迁移报告.json", stats)
    revalidate_results()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return stats


def required_api_key_env_names() -> list[str]:
    return sorted(
        {route["api_key_env"] for _, route in configured_model_routes()}
    )


def ensure_api_keys(prompt_key: bool) -> None:
    missing = [name for name in required_api_key_env_names() if not os.getenv(name)]
    if not missing:
        return
    if not prompt_key:
        raise RuntimeError(
            "进程环境缺少 " + "、".join(missing) + "；可使用 --prompt-key 从隐藏输入读取。"
        )
    for name in missing:
        value = getpass.getpass(f"{name}（隐藏输入，不写入文件）：").strip()
        if not value:
            raise RuntimeError(f"未输入 {name}")
        os.environ[name] = value


# Backward-compatible helper name for local scripts that imported it.
ensure_api_key = ensure_api_keys


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                handle, ctypes.byref(exit_code)
            ):
                return False
            return exit_code.value == still_active
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_background(start_book: int = 1, workers: int = DEFAULT_PARALLEL_WORKERS) -> None:
    """以继承的临时密钥环境启动长期任务；命令行和文件均不含密钥。"""
    process_path = REPORTS / "V3后台进程.json"
    if process_path.exists():
        previous = json.loads(process_path.read_text(encoding="utf-8"))
        previous_pid = int(previous.get("pid") or 0)
        if pid_is_alive(previous_pid):
            raise RuntimeError(f"V3 后台进程仍在运行，PID={previous_pid}")

    stdout_path = REPORTS / "V3后台运行.log"
    stderr_path = REPORTS / "V3后台错误.log"
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-u",
        str(Path(__file__).resolve()),
        "run-all",
        "--start-book",
        str(start_book),
        "--workers",
        str(workers),
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x00000008 | 0x00000200 | 0x08000000
    with stdout_path.open("ab") as stdout_file, stderr_path.open("ab") as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=creationflags,
            close_fds=True,
        )
    process_record = {
        "started_at": now_iso(),
        "pid": process.pid,
        "alive_at_start": pid_is_alive(process.pid),
        "start_book": start_book,
        "workers": workers,
        "max_concurrent_api_requests": MAX_CONCURRENT_API_REQUESTS,
        "model_routes": public_model_route_summary(),
        "script": str(Path(__file__).resolve()),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "secret_storage": "process_environment_only",
    }
    atomic_json(process_path, process_record)
    state = load_state()
    state["state"] = "background_starting"
    state["background_pid"] = process.pid
    state["updated_at"] = now_iso()
    atomic_json(REPORTS / "V3运行状态.json", state)
    print(json.dumps(process_record, ensure_ascii=False, indent=2))


def run_book_with_retries(
    book_no: int,
    limit_batches_per_book: int | None,
    state: dict[str, Any],
) -> int:
    """Run one book with checkpoint-safe transient retries."""
    transient_attempt = 0
    try:
        while True:
            completed_before = completed_result_count_for_book(book_no)
            try:
                run_book(
                    book_no,
                    limit_batches_per_book,
                    shared_state=state,
                )
                with STATE_LOCK:
                    retries = dict(state.get("transient_retries") or {})
                    retries.pop(str(book_no), None)
                    state["transient_retries"] = retries
                return book_no
            except Exception as exc:
                completed_after = completed_result_count_for_book(book_no)
                if completed_after > completed_before:
                    # Successful checkpointed batches mean this is a fresh
                    # intermittent failure, not a fifth consecutive failure.
                    transient_attempt = 0
                if (
                    not is_transient_api_failure(exc)
                    or transient_attempt >= MAX_BOOK_TRANSIENT_RESTARTS
                ):
                    raise
                transient_attempt += 1
                delay = min(30 * (2 ** (transient_attempt - 1)), 300)
                with STATE_LOCK:
                    retries = dict(state.get("transient_retries") or {})
                    retries[str(book_no)] = {
                        "attempt": transient_attempt,
                        "last_error": str(exc),
                        "next_retry_delay_seconds": delay,
                        "updated_at": now_iso(),
                    }
                    state["transient_retries"] = retries
                    state["state"] = "running"
                    state["updated_at"] = now_iso()
                    atomic_json(REPORTS / "V3运行状态.json", state)
                print(
                    f"book{book_no:03d}: 瞬时 API 故障，{delay}s 后从缓存断点重试 "
                    f"({transient_attempt}/{MAX_BOOK_TRANSIENT_RESTARTS})",
                    flush=True,
                )
                time.sleep(delay)
    finally:
        with STATE_LOCK:
            active = set(state.get("current_books") or [])
            active.discard(book_no)
            state["current_books"] = sorted(active)
            if active:
                state["current_book"] = min(active)
            state["updated_at"] = now_iso()
            atomic_json(REPORTS / "V3运行状态.json", state)


def run_all(
    start_book: int = 1,
    limit_batches_per_book: int | None = None,
    workers: int = DEFAULT_PARALLEL_WORKERS,
) -> None:
    state = load_state()
    workers = max(1, min(int(workers), 6, 37 - start_book))
    with STATE_LOCK:
        ensure_usage_state(state)
        state["state"] = "running"
        state["writer_model"] = WRITER_MODEL
        state["repair_model"] = REPAIR_MODEL
        state["escalation_model"] = ESCALATION_MODEL
        state["judge_model"] = JUDGE_MODEL
        state["max_repair_rounds"] = MAX_REPAIR_ROUNDS
        state["max_concurrent_api_requests"] = MAX_CONCURRENT_API_REQUESTS
        state["model_routes"] = public_model_route_summary()
        state["parallel_workers"] = workers
        state["current_books"] = []
        state["transient_retries"] = {}
        # A recovered run must not keep an obsolete failure banner after it has
        # successfully resumed from the existing cache/checkpoint.
        state.pop("last_error", None)
        state["updated_at"] = now_iso()
        atomic_json(REPORTS / "V3运行状态.json", state)
    try:
        book_numbers = iter(range(start_book, 37))
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="v3-book",
        ) as executor:
            futures: dict[concurrent.futures.Future[int], int] = {}
            for _ in range(workers):
                try:
                    book_no = next(book_numbers)
                except StopIteration:
                    break
                future = executor.submit(
                    run_book_with_retries,
                    book_no,
                    limit_batches_per_book,
                    state,
                )
                futures[future] = book_no

            while futures:
                done, _ = concurrent.futures.wait(
                    futures,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                for future in done:
                    completed_book = future.result()
                    futures.pop(future)
                    if limit_batches_per_book is None:
                        render_book(completed_book)
                    try:
                        next_book = next(book_numbers)
                    except StopIteration:
                        continue
                    next_future = executor.submit(
                        run_book_with_retries,
                        next_book,
                        limit_batches_per_book,
                        state,
                    )
                    futures[next_future] = next_book
        render_all()
        report = verify()
        with STATE_LOCK:
            state["state"] = "complete" if report["status"] == "passed" else "validation_failed"
            state.pop("last_error", None)
            state["updated_at"] = now_iso()
            atomic_json(REPORTS / "V3运行状态.json", state)
    except Exception as exc:
        with STATE_LOCK:
            if state.get("state") != "budget_blocked":
                state["state"] = "error"
            state["last_error"] = str(exc)
            state["updated_at"] = now_iso()
            atomic_json(REPORTS / "V3运行状态.json", state)
        raise


def render_book(book_no: int) -> bool:
    segments = read_jsonl(SEGMENTS / f"book{book_no:03d}.jsonl")
    result_rows = read_jsonl(RESULTS / f"book{book_no:03d}.jsonl")
    segment_hashes = {s["id"]: s["source_sha256"] for s in segments}
    results = {
        r["id"]: r for r in result_rows
        if is_expected_complete_result(r, segment_hashes)
    }
    required = [s for s in segments if s["translatable"]]
    complete = all(s["id"] in results for s in required)
    out_lines: list[str] = []
    title_added = False
    for segment in segments:
        source_exact = segment["source"]
        source = source_exact.strip()
        if segment["kind"] == "title":
            out_lines.append(source)
            out_lines.append("> V3 AI 全自动白话释读版。专业术语保留，释读内容可展开核对原文。")
            title_added = True
            continue
        if segment["kind"] == "empty_heading":
            continue
        if not segment["translatable"]:
            out_lines.append(source)
            continue
        result = results.get(segment["id"])
        if not result:
            out_lines.append(f"<!-- V3_PENDING:{segment['id']} -->")
            out_lines.append(source)
            continue
        out_lines.append(f"<!-- V3_SOURCE_ID:{segment['id']} -->")
        modern_text = result["modern_text"].strip()
        if segment["kind"] == "heading":
            modern_text = normalize_rendered_heading(source, modern_text)
        modern_text = normalize_rendered_body_headings(modern_text)
        out_lines.append(modern_text)
        if result.get("uncertainty") or result.get("judge_verdict") == "uncertain":
            raw_notes = result.get("uncertainty") or result.get("issues") or ["本段释读存在不确定性"]
            note = "；".join(str(item) for item in raw_notes)
            out_lines.append(f"> **释读存疑：** {note}")
        out_lines.append("<details>")
        out_lines.append("<summary>查看对应原文</summary>")
        # The source hash is computed over the exact source bytes, so retain
        # surrounding whitespace in the collapsible evidence block.  Unique
        # sentinels make extraction unambiguous even when the source itself
        # begins or ends with whitespace/newlines.
        out_lines.append(f"<!-- V3_FOLDBACK_BEGIN:{segment['id']} -->")
        out_lines.append(source_exact)
        out_lines.append(f"<!-- V3_FOLDBACK_END:{segment['id']} -->")
        out_lines.append("</details>")
    if not title_added:
        raise RuntimeError(f"book{book_no:03d} 缺少 H1")
    text = "\n\n".join(out_lines).rstrip() + "\n"
    book_file = segments[0]["book_file"]
    draft = DRAFTS / book_file
    draft.write_text(text, encoding="utf-8", newline="\n")
    if complete:
        (V3 / book_file).write_text(text, encoding="utf-8", newline="\n")
    return complete


def extract_foldback_source(text: str, segment_id: str) -> str:
    """Extract the exact source text between the per-segment sentinels."""
    begin = f"<!-- V3_FOLDBACK_BEGIN:{segment_id} -->"
    end = f"<!-- V3_FOLDBACK_END:{segment_id} -->"
    begin_at = text.index(begin) + len(begin)
    end_at = text.index(end, begin_at)
    source = text[begin_at:end_at]
    if source.startswith("\n\n"):
        source = source[2:]
    if source.endswith("\n\n"):
        source = source[:-2]
    return source


def render_all() -> None:
    manifest = json.loads((REPORTS / "V3基线清单.json").read_text(encoding="utf-8"))
    completed = 0
    for book in manifest["books"]:
        completed += int(render_book(book["book_no"]))
    state = load_state()
    state["books_rendered"] = completed
    state["updated_at"] = now_iso()
    atomic_json(REPORTS / "V3运行状态.json", state)
    print(f"完整成书：{completed}/{len(manifest['books'])}；未完成稿位于 {DRAFTS}")


def verify() -> dict[str, Any]:
    manifest = json.loads((REPORTS / "V3基线清单.json").read_text(encoding="utf-8"))
    source_books = manifest["books"]
    final_books = sorted(p for p in V3.glob("*.md") if p.is_file() and BOOK_FILE_RE.match(p.name))
    expected_ids = expected_translatable_ids()
    latest_records = latest_result_records()
    judged_records = {
        sid: row for sid, row in latest_records.items()
        if sid in expected_ids and is_complete_result(row)
    }
    result_ids = set(judged_records)
    uncertain = sum(
        1 for row in judged_records.values()
        if row.get("judge_verdict") != "accept" or row.get("uncertainty")
    )
    missing_images: list[dict[str, str]] = []
    absolute_images: list[dict[str, str]] = []
    h1_errors: list[str] = []
    trace_errors: list[str] = []
    source_hash_errors: list[str] = []
    image_refs = 0
    for path in final_books:
        text = path.read_text(encoding="utf-8")
        if len(re.findall(r"(?m)^#\s+\S", text)) != 1:
            h1_errors.append(path.name)
        ids = re.findall(r"<!-- V3_SOURCE_ID:([^ ]+) -->", text)
        details = text.count("<summary>查看对应原文</summary>")
        if len(ids) != details:
            trace_errors.append(path.name)
        result_map = {
            r["id"]: r for r in read_jsonl(RESULTS / f"book{int(path.name[:3]):03d}.jsonl")
            if r.get("status") == "judged"
        }
        for sid in ids:
            record = result_map.get(sid)
            if not record:
                source_hash_errors.append(f"{path.name}:{sid}:missing-result")
                continue
            marker = f"<!-- V3_SOURCE_ID:{sid} -->"
            start = text.find(marker)
            summary = text.find("<summary>查看对应原文</summary>", start)
            end = text.find("</details>", summary)
            foldback_begin = text.find(f"<!-- V3_FOLDBACK_BEGIN:{sid} -->", summary)
            foldback_end = text.find(f"<!-- V3_FOLDBACK_END:{sid} -->", foldback_begin)
            if (
                start < 0
                or summary < 0
                or end < 0
                or foldback_begin < 0
                or foldback_end < 0
                or foldback_end > end
            ):
                source_hash_errors.append(f"{path.name}:{sid}:missing-details")
                continue
            original = extract_foldback_source(text, sid)
            if hashlib.sha256(original.encode("utf-8")).hexdigest() != record["source_sha256"]:
                source_hash_errors.append(f"{path.name}:{sid}:hash-mismatch")
        for ref in IMAGE_RE.findall(text):
            image_refs += 1
            ref_clean = ref.split("#", 1)[0].split("?", 1)[0]
            if re.match(r"^[A-Za-z]:[\\/]", ref_clean) or ref_clean.startswith("/"):
                absolute_images.append({"file": path.name, "ref": ref})
            elif not (V3 / ref_clean).exists():
                missing_images.append({"file": path.name, "ref": ref})
    report = {
        "generated_at": now_iso(),
        "status": "passed" if (
            len(source_books) == 36
            and len(final_books) == 36
            and not (expected_ids - result_ids)
            and not missing_images
            and not absolute_images
            and not h1_errors
            and not trace_errors
            and not source_hash_errors
            and not any(
                r.get("missing_locked_terms")
                or r.get("missing_protected_tokens")
                or r.get("insufficient_modernization")
                or r.get("source_duplicated")
                or r.get("unsupported_expansions")
                or r.get("unapproved_parenthetical_notes")
                or r.get("unquoted_opaque_terms")
                or r.get("unsupported_opaque_definitions")
                for r in judged_records.values()
            )
            and image_refs == manifest["totals"]["asset_files"]
        ) else "incomplete",
        "books_expected": len(source_books),
        "books_final": len(final_books),
        "segments_expected": len(expected_ids),
        "segments_judged": len(result_ids & expected_ids),
        "segments_missing": len(expected_ids - result_ids),
        "segments_uncertain_recorded": uncertain,
        "image_references": image_refs,
        "image_files_expected": manifest["totals"]["asset_files"],
        "missing_images": missing_images,
        "absolute_images": absolute_images,
        "h1_errors": h1_errors,
        "trace_errors": trace_errors,
        "source_hash_errors": source_hash_errors,
        "protected_value_errors": sum(
            1 for r in judged_records.values()
            if r.get("missing_locked_terms") or r.get("missing_protected_tokens")
        ),
        "insufficient_modernization_errors": sum(
            1 for r in judged_records.values() if r.get("insufficient_modernization")
        ),
        "source_duplication_errors": sum(1 for r in judged_records.values() if r.get("source_duplicated")),
        "unsupported_expansion_errors": sum(
            1 for r in judged_records.values() if r.get("unsupported_expansions")
        ),
        "unapproved_parenthetical_errors": sum(
            1 for r in judged_records.values() if r.get("unapproved_parenthetical_notes")
        ),
        "unquoted_opaque_term_errors": sum(
            1 for r in judged_records.values() if r.get("unquoted_opaque_terms")
        ),
        "unsupported_opaque_definition_errors": sum(
            1 for r in judged_records.values() if r.get("unsupported_opaque_definitions")
        ),
        "known_source_damaged_pages": 6,
    }
    atomic_json(REPORTS / "V3硬校验.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def status() -> None:
    state = load_state()
    manifest = json.loads((REPORTS / "V3基线清单.json").read_text(encoding="utf-8"))
    expected_ids = expected_translatable_ids()
    completed = sum(
        1 for sid, r in latest_result_records().items()
        if sid in expected_ids and is_complete_result(r)
    )
    total = manifest["totals"]["translatable_segments"]
    state["segments_judged"] = completed
    state["progress_percent"] = round(completed / total * 100, 4) if total else 100.0
    state["final_markdown_files"] = len(
        [p for p in V3.glob("*.md") if p.is_file() and BOOK_FILE_RE.match(p.name)]
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


def tree_digest(root: Path) -> tuple[int, int, str]:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    h = hashlib.sha256()
    total = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        digest = sha256_file(path)
        size = path.stat().st_size
        total += size
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return len(files), total, h.hexdigest()


def preflight() -> dict[str, Any]:
    manifest = json.loads((REPORTS / "V3基线清单.json").read_text(encoding="utf-8"))
    source_hash_errors = []
    for book in manifest["books"]:
        source = V2 / book["file"]
        if not source.exists() or sha256_file(source) != book["source_sha256"]:
            source_hash_errors.append(book["file"])
    ids: set[str] = set()
    duplicate_ids: list[str] = []
    empty_translatable: list[str] = []
    for path in sorted(SEGMENTS.glob("book*.jsonl")):
        for row in read_jsonl(path):
            if row["id"] in ids:
                duplicate_ids.append(row["id"])
            ids.add(row["id"])
            if row["translatable"] and not row["source"].strip():
                empty_translatable.append(row["id"])
            if hashlib.sha256(row["source"].encode("utf-8")).hexdigest() != row["source_sha256"]:
                source_hash_errors.append(row["id"])
    v2_count, v2_bytes, v2_digest = tree_digest(V2 / "assets")
    v3_count, v3_bytes, v3_digest = tree_digest(ASSETS)
    report = {
        "generated_at": now_iso(),
        "status": "passed" if (
            len(manifest["books"]) == 36
            and not source_hash_errors
            and not duplicate_ids
            and not empty_translatable
            and v2_count == v3_count == 8777
            and v2_bytes == v3_bytes
            and v2_digest == v3_digest
        ) else "failed",
        "books": len(manifest["books"]),
        "segments": len(ids),
        "source_hash_errors": source_hash_errors,
        "duplicate_segment_ids": duplicate_ids,
        "empty_translatable_segments": empty_translatable,
        "v2_assets": {"files": v2_count, "bytes": v2_bytes, "tree_sha256": v2_digest},
        "v3_assets": {"files": v3_count, "bytes": v3_bytes, "tree_sha256": v3_digest},
    }
    atomic_json(REPORTS / "V3基线独立校验.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    run_p = sub.add_parser("run")
    run_p.add_argument("--book", type=int, required=True)
    run_p.add_argument("--limit-batches", type=int)
    run_p.add_argument("--ids", help="仅处理逗号分隔的片段 ID，用于质量小样")
    run_p.add_argument("--prompt-key", action="store_true")
    all_p = sub.add_parser("run-all")
    all_p.add_argument("--start-book", type=int, default=1)
    all_p.add_argument("--limit-batches-per-book", type=int)
    all_p.add_argument("--workers", type=int, default=DEFAULT_PARALLEL_WORKERS)
    all_p.add_argument("--prompt-key", action="store_true")
    background_p = sub.add_parser("start-background")
    background_p.add_argument("--start-book", type=int, default=1)
    background_p.add_argument("--workers", type=int, default=DEFAULT_PARALLEL_WORKERS)
    background_p.add_argument("--prompt-key", action="store_true")
    sub.add_parser("render")
    sub.add_parser("verify")
    sub.add_parser("revalidate")
    migrate_p = sub.add_parser("migrate-archived-results")
    migrate_p.add_argument("--source", required=True)
    sub.add_parser("status")
    sub.add_parser("preflight")
    check_p = sub.add_parser("api-check")
    check_p.add_argument("--prompt-key", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "run":
        ensure_api_keys(args.prompt_key)
        only_ids = {sid.strip() for sid in args.ids.split(",") if sid.strip()} if args.ids else None
        run_book(args.book, args.limit_batches, only_ids)
    elif args.command == "run-all":
        ensure_api_keys(args.prompt_key)
        run_all(args.start_book, args.limit_batches_per_book, args.workers)
    elif args.command == "start-background":
        ensure_api_keys(args.prompt_key)
        start_background(args.start_book, args.workers)
    elif args.command == "render":
        render_all()
    elif args.command == "verify":
        verify()
    elif args.command == "revalidate":
        revalidate_results()
    elif args.command == "migrate-archived-results":
        migrate_archived_results(Path(args.source))
    elif args.command == "status":
        status()
    elif args.command == "preflight":
        preflight()
    elif args.command == "api-check":
        ensure_api_keys(args.prompt_key)
        api_check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
