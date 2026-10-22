#!/usr/bin/env python3
"""不联网、不写生产结果的 V3 流水线回归测试。"""

from __future__ import annotations

import hashlib
import json
import re
import runpy
import tempfile
from pathlib import Path


PIPELINE = Path(__file__).with_name("v3_pipeline.py")
m = runpy.run_path(str(PIPELINE), run_name="v3_pipeline_test")
SECOND_PASS = Path(__file__).with_name("build_v3_second_pass_queue.py")
q = runpy.run_path(str(SECOND_PASS), run_name="v3_second_pass_test")


def test_split_and_hash() -> None:
    text = "甲" * 2700 + "。" + "乙" * 2700
    pieces = m["split_long_text"](text, 2600)
    assert "".join(pieces) == text
    assert all(0 < len(piece) <= 2600 for piece in pieces)
    assert hashlib.sha256("".join(pieces).encode("utf-8")).hexdigest() == hashlib.sha256(text.encode("utf-8")).hexdigest()
    many_short_rows = [{"source": "短句"} for _ in range(95)]
    grouped = list(m["batches"](many_short_rows, 2200, 40))
    assert [len(batch) for batch in grouped] == [40, 40, 15]
    default_grouped = list(m["batches"](many_short_rows, 2200))
    assert max(map(len, default_grouped)) == 10
    assert sum(map(len, default_grouped)) == len(many_short_rows)


def test_protected_values() -> None:
    source = "甲子年立乾山巽向，二十四山分金为120度，共三卷。"
    tokens = m["protected_tokens"](source)
    assert "甲子" in tokens
    assert "120度" in tokens
    assert "三卷" in tokens
    assert m["protected_token_present"]("列为丙、午、丁三山", "丙午")
    assert not m["protected_token_present"]("甲年", "甲子")
    html_tokens = m["protected_tokens"]('<table><tr><td rowspan="1">甲子年120度</td></tr></table>')
    assert "1" not in html_tokens
    assert "甲子" in html_tokens and "120度" in html_tokens
    media_tokens = m["protected_tokens"](
        '<!-- doc001 PDF 第 54 页 -->\n'
        '![](assets/book001/doc001/7160f54996f344a670f3fbd5a5ca9514508918102.jpg)\n'
        '乾山120度'
    )
    assert media_tokens == ["120度"]


def test_conservative_quality_gate() -> None:
    glossary = m["load_glossary"]()
    assert "八卦" in glossary
    source = "浮黎正统，八卦八门，六甲天书。八方云篆，元女降质。"
    bad = "这是浮黎一脉的正统传承，讲八卦与八门（风水方位中的八个关键方位），九天元女降临。"
    check = m["local_quality_issues"](
        source,
        bad,
        "classical_chinese",
        ["八卦"],
        m["allowed_glossary_for"](["八卦"], glossary),
    )
    assert "浮黎一脉" in check["unsupported_expansions"]
    assert "九天元女" in check["unsupported_expansions"]
    assert "风水方位中的八个关键方位" in check["unapproved_parenthetical_notes"]
    assert m["hard_issue_messages"](check)

    opaque_check = m["local_quality_issues"](
        "镇世鳌极，四极鳌布，首司庚甲。",
        "镇守世间如巨鳌般的根基，并在四方铺展，掌管庚与甲。",
        "classical_chinese",
        ["鳌极", "鳌布", "庚甲"],
        {},
        ["鳌极", "鳌布", "庚甲"],
    )
    assert opaque_check["missing_locked_terms"] == ["鳌极", "鳌布", "庚甲"]
    assert opaque_check["unquoted_opaque_terms"] == ["鳌极", "鳌布", "庚甲"]

    quoted_check = m["local_quality_issues"](
        "镇世鳌极，四极鳌布，首司庚甲。",
        "文中说它能‘镇世鳌极’，又提到‘四极鳌布’和‘首司庚甲’；这些短语具体所指不详。",
        "classical_chinese",
        ["鳌极", "鳌布", "庚甲"],
        {},
        ["鳌极", "鳌布", "庚甲"],
    )
    assert not quoted_check["missing_locked_terms"]
    assert not quoted_check["unquoted_opaque_terms"]

    ordinary_li = m["local_quality_issues"](
        "震山子来巽，绝体残疾当。小房不离床。",
        "震山来巽时，小房人常卧病在床。",
        "classical_chinese",
        ["离"],
        {},
    )
    assert ordinary_li["missing_locked_terms"] == []
    technical_li = m["local_quality_issues"](
        "震山子来离，生气五子奇。",
        "震山有水来，但方位文字遗漏。",
        "classical_chinese",
        ["离"],
        {},
    )
    assert technical_li["missing_locked_terms"] == ["离"]
    ordinary_xiang = m["local_quality_issues"](
        "向之窃窃然疑者，至是不觉涣然。",
        "过去暗自怀疑的人，到此豁然明白。",
        "classical_chinese",
        ["向"],
        {},
    )
    assert ordinary_xiang["missing_locked_terms"] == []
    technical_xiang = m["local_quality_issues"](
        "至于立向一法，更未有详言。",
        "这一方法从未详细说明。",
        "classical_chinese",
        ["向"],
        {},
    )
    assert technical_xiang["missing_locked_terms"] == ["向"]

    definition_check = m["local_quality_issues"](
        "御虎贲之强兵。",
        "它能抵御‘虎贲’之强兵；‘虎贲’指古代军队。",
        "classical_chinese",
        ["虎贲"],
        {},
        ["虎贲"],
    )
    assert definition_check["unsupported_opaque_definitions"] == ["虎贲"]

    modern_preserve_check = m["local_quality_issues"](
        "九天元女青囊海角经序",
        "九天元女青囊海角经序",
        "modern_chinese",
        ["元女"],
        {},
        ["元女"],
    )
    assert not modern_preserve_check["unquoted_opaque_terms"]
    assert not modern_preserve_check["unsupported_opaque_definitions"]

    safe = "这段文字称其为浮黎正统，并提到八卦、八门和六甲天书；元女降质一句的具体所指不详。"
    safe_check = m["local_quality_issues"](
        source,
        safe,
        "classical_chinese",
        ["八卦"],
        m["allowed_glossary_for"](["八卦"], glossary),
    )
    assert not safe_check["unsupported_expansions"]
    assert not safe_check["unapproved_parenthetical_notes"]
    assert not safe_check["source_duplicated"]

    uncertain_note_check = m["local_quality_issues"](
        "未山有圆石土卯黄土。",
        "未山有圆石、‘土卯’（具体所指不详）及黄土。",
        "classical_chinese",
        [],
        {},
    )
    assert not uncertain_note_check["unapproved_parenthetical_notes"]

    page_note_check = m["local_quality_issues"](
        "图说1",
        "图说（第1页）",
        "classical_chinese",
        [],
        {},
    )
    assert not page_note_check["unapproved_parenthetical_notes"]


def test_classification() -> None:
    kind, translatable, language = m["classify_block"]("本書は術数学をテーマとする。", 3)
    assert (kind, translatable, language) == ("prose", True, "japanese")
    kind, translatable, _ = m["classify_block"]("![](assets/book001/a.jpg)", 3)
    assert kind == "image" and not translatable
    kind, translatable, _ = m["classify_block"]("## 卷之一", 3)
    assert kind == "heading" and translatable
    kind, translatable, _ = m["classify_block"]("##", 3)
    assert kind == "empty_heading" and not translatable
    toc = "\n".join(f"章节{i}……………………{i}" for i in range(1, 10))
    kind, translatable, language = m["classify_block"](toc, 5)
    assert (kind, translatable, language) == ("toc", False, "mixed")
    japanese_toc = "\n".join(f"第{i}章の内容……………………{i}" for i in range(1, 10))
    kind, translatable, language = m["classify_block"](japanese_toc, 5)
    assert (kind, translatable, language) == ("toc", True, "japanese")


def test_split_markdown_media_block() -> None:
    page_image = (
        "<!-- doc001 PDF 第 54 页：高风险/复杂版面 OCR 供检索；内容与排版以原页图为准。 -->\n"
        "![](assets/book001/doc001/source-page-0054.jpg)"
    )
    assert m["split_markdown_media_block"](page_image) == [("media", page_image)]

    mixed = (
        "![](assets/book001/doc001/abc123.jpg)  \n"
        "图说  \n"
        "乾山立向一百二十度，取其来龙。"
    )
    chunks = m["split_markdown_media_block"](mixed)
    assert chunks[0] == ("media", "![](assets/book001/doc001/abc123.jpg)")
    assert chunks[1][0] == "text"
    assert "乾山立向一百二十度" in chunks[1][1]
    assert "abc123" not in m["semantic_visible_text"](mixed)


def test_merge_japanese_fragments() -> None:
    blocks = [
        "## 前言",
        "天文学や数学などの",
        "数理科学的分野を対象とする暦算、",
        "そして占術からなる。",
        "![](assets/book015/a.jpg)",
    ]
    merged = m["merge_japanese_fragments"](blocks)
    assert merged[0] == (0, "## 前言")
    assert merged[1][0] == 1
    assert merged[1][1] == "天文学や数学などの\n数理科学的分野を対象とする暦算、\nそして占術からなる。"
    assert merged[2] == (4, "![](assets/book015/a.jpg)")


def test_html_split() -> None:
    rows = [f"<tr><td>{i}</td><td>来龙与分金</td></tr>" for i in range(200)]
    source = "表题\n<table>" + "".join(rows) + "</table>\n表后说明"
    pieces = m["split_html_block"](source, 1000)
    assert len(pieces) > 1
    assert all("<table>" in p and "</table>" in p for p in pieces)
    assert sum(p.count("<tr>") for p in pieces) == 200
    assert pieces[0].startswith("表题")
    assert pieces[-1].endswith("表后说明")


def test_saved_segments() -> None:
    manifest = m["json"].loads((m["REPORTS"] / "V3基线清单.json").read_text(encoding="utf-8"))
    assert len(manifest["books"]) == 36
    seen: set[str] = set()
    segment_count = 0
    translatable_count = 0
    for path in sorted(m["SEGMENTS"].glob("book*.jsonl")):
        for row in m["read_jsonl"](path):
            assert row["id"] not in seen
            seen.add(row["id"])
            assert row["source"].strip()
            assert hashlib.sha256(row["source"].encode("utf-8")).hexdigest() == row["source_sha256"]
            assert re.fullmatch(r"book\d{3}-b\d{6}-p\d{3}-[0-9a-f]{10}", row["id"])
            assert row["id"].endswith(row["source_sha256"][:10])
            segment_count += 1
            translatable_count += int(row["translatable"])
    assert segment_count == manifest["totals"]["segments"]
    assert translatable_count == manifest["totals"]["translatable_segments"]
    assert segment_count > 41000
    assert translatable_count > 34000


def test_parse_json_content() -> None:
    expected = {"items": [{"id": "x", "verdict": "accept"}]}
    raw = m["json"].dumps(expected, ensure_ascii=False)
    assert m["parse_json_content"](raw) == expected
    assert m["parse_json_content"](f"```json\n{raw}\n```") == expected
    assert m["parse_json_content"](f"结果如下：\n{raw}") == expected
    assert m["parse_json_content"](f"结果：[{m['json'].dumps(expected['items'][0])}]\n结束 {{未闭合") == expected["items"]
    assert m["parse_json_content"](f"前言 {raw} 后记 {{其他内容}}") == expected


def test_invalid_json_writer_batch_is_split_without_repeating_parent() -> None:
    pipeline_globals = m["request_json_cached"].__globals__
    original_cache = pipeline_globals["API_CACHE"]
    original_reports = pipeline_globals["REPORTS"]
    original_request = pipeline_globals["request_json"]
    calls: list[int] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline_globals["API_CACHE"] = root / "cache"
            pipeline_globals["REPORTS"] = root / "reports"

            def fake_request(model, system, payload, max_tokens=10000, route=None):
                count = len(payload.get("items") or [])
                calls.append(count)
                usage = {
                    "prompt_tokens": 20,
                    "completion_tokens": 2,
                    "cached_prompt_tokens": 0,
                    "usage_estimated": False,
                }
                if count > 1:
                    return {"_invalid_json": True, "content_sha256": "test"}, usage
                return {"items": [{"id": payload["items"][0]["id"]}]}, usage

            pipeline_globals["request_json"] = fake_request
            ids = ["book001-test-a", "book001-test-b", "book001-test-c"]
            payload = {"items": [{"id": sid, "source": sid} for sid in ids]}
            state = {
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cached_prompt_tokens": 0,
                    "estimated_cost_rmb": 0.0,
                    "by_provider": {},
                }
            }
            result = m["request_json_cached"](
                state, m["WRITER_MODEL"], "system", payload, max_tokens=100
            )
            assert [item["id"] for item in result["items"]] == ids
            assert calls == [3, 1, 2, 1, 1]
            events = [
                json.loads(line)
                for line in (pipeline_globals["REPORTS"] / "V3 API异常台账.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            assert sum(event["type"] == "writer_invalid_json_batch_split" for event in events) == 2
    finally:
        pipeline_globals["API_CACHE"] = original_cache
        pipeline_globals["REPORTS"] = original_reports
        pipeline_globals["request_json"] = original_request


def test_partial_writer_batch_requests_only_missing_ids() -> None:
    pipeline_globals = m["request_json_cached"].__globals__
    original_cache = pipeline_globals["API_CACHE"]
    original_reports = pipeline_globals["REPORTS"]
    original_request = pipeline_globals["request_json"]
    calls: list[list[str]] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline_globals["API_CACHE"] = root / "cache"
            pipeline_globals["REPORTS"] = root / "reports"

            def fake_request(model, system, payload, max_tokens=10000, route=None):
                ids = [item["id"] for item in payload.get("items") or []]
                calls.append(ids)
                usage = {
                    "prompt_tokens": 20,
                    "completion_tokens": 2,
                    "cached_prompt_tokens": 0,
                    "usage_estimated": False,
                }
                returned = ids[:1] if len(ids) == 3 else ids
                return {"items": [{"id": sid} for sid in returned]}, usage

            pipeline_globals["request_json"] = fake_request
            ids = ["book001-partial-a", "book001-partial-b", "book001-partial-c"]
            payload = {"items": [{"id": sid, "source": sid} for sid in ids]}
            state = {
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cached_prompt_tokens": 0,
                    "estimated_cost_rmb": 0.0,
                    "by_provider": {},
                }
            }
            result = m["request_json_cached"](
                state, m["WRITER_MODEL"], "system", payload, max_tokens=100
            )
            assert [item["id"] for item in result["items"]] == ids
            assert calls == [ids, [ids[1]], [ids[2]]]
            parent_key = hashlib.sha256(
                json.dumps(
                    m["request_cache_material_record"](
                        m["WRITER_MODEL"],
                        "system",
                        payload,
                        100,
                        m["route_for_model"](m["WRITER_MODEL"], payload),
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            parent_cache = json.loads(
                (pipeline_globals["API_CACHE"] / f"{parent_key}.json").read_text(encoding="utf-8")
            )
            assert parent_cache["composed_from_subbatches"] is True
    finally:
        pipeline_globals["API_CACHE"] = original_cache
        pipeline_globals["REPORTS"] = original_reports
        pipeline_globals["request_json"] = original_request


def test_collect_streamed_chat() -> None:
    lines = [
        b'data: {"choices":[{"delta":{"content":"{\\"ok\\":"}}]}',
        b'data: {"choices":[{"delta":{"content":"true}"}}]}',
        b'data: {"choices":[],"usage":{"prompt_tokens":40,"completion_tokens":5,"prompt_cache_hit_tokens":0}}',
        b'data: [DONE]',
    ]
    content, usage = m["collect_streamed_chat"](lines)
    assert content == '{"ok":true}'
    assert usage["prompt_tokens"] == 40
    assert usage["completion_tokens"] == 5


def test_collect_streamed_chat_has_total_duration_guard() -> None:
    original_monotonic = m["time"].monotonic
    ticks = iter([0.0, 1.0, 3.1])
    m["time"].monotonic = lambda: next(ticks)
    try:
        try:
            m["collect_streamed_chat"](
                [
                    b'data: {"choices":[{"delta":{"content":"a"}}]}',
                    b'data: {"choices":[{"delta":{"content":"b"}}]}',
                ],
                max_seconds=2,
            )
        except TimeoutError as exc:
            assert "SSE" in str(exc)
        else:
            raise AssertionError("expected SSE total duration timeout")
    finally:
        m["time"].monotonic = original_monotonic


def test_cached_input_cost() -> None:
    model = m["JUDGE_MODEL"]
    price = m["PRICE"][model]
    usage = {
        "prompt_tokens": 1000,
        "cached_prompt_tokens": 500,
        "completion_tokens": 100,
    }
    expected = (
        500 / 1_000_000 * price["input"]
        + 500 / 1_000_000 * price["cached_input"]
        + 100 / 1_000_000 * price["output"]
    )
    assert abs(m["estimate_cost"](model, usage) - expected) < 1e-12


def test_usage_zero_fields_use_conservative_byte_estimates() -> None:
    system = "白话释读"
    payload = {"items": [{"id": "a", "source": "乾山"}]}
    content = '{"items":[]}'
    estimated = m["normalize_usage"](
        {"prompt_tokens": 0, "completion_tokens": 0}, system, payload, content
    )
    assert estimated["prompt_tokens"] == len(
        (system + json.dumps(payload, ensure_ascii=False)).encode("utf-8")
    )
    assert estimated["completion_tokens"] == len(content.encode("utf-8"))
    assert estimated["usage_estimated"] is True

    partial = m["normalize_usage"](
        {
            "prompt_tokens": 12,
            "completion_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 20},
        },
        system,
        payload,
        content,
    )
    assert partial["prompt_tokens"] == 12
    assert partial["completion_tokens"] == len(content.encode("utf-8"))
    assert partial["cached_prompt_tokens"] == 12
    assert partial["usage_estimated"] is True


def test_transient_api_failure_classifier() -> None:
    assert m["is_transient_api_failure"](
        RuntimeError("ConnectionResetError(10054): connection aborted")
    )
    assert m["is_transient_api_failure"](RuntimeError("HTTP 503: overloaded"))
    assert m["is_transient_api_failure"](
        RuntimeError("模型部分响应待补全：book001-example")
    )
    assert m["is_transient_api_failure"](
        TimeoutError("SSE 流式响应超过总时长上限 600s")
    )
    assert m["is_transient_api_failure"](
        RuntimeError("写作模型对单个片段仍返回无法解析的 JSON")
    )
    assert not m["is_transient_api_failure"](
        RuntimeError("模型连续返回不合格 JSON 结构")
    )


def test_rendered_heading_normalization() -> None:
    source = "## 南昌萬樹華編　宋託長老入地眼全書　文星堂藏板"
    prose = "这是《入地眼全书》的文星堂藏板版本标题。"
    normalized = m["normalize_rendered_heading"](source, prose)
    assert normalized.startswith("## ")
    assert "南昌萬樹華編" in normalized
    assert prose in normalized
    already_heading = m["normalize_rendered_heading"](source, "## 南昌萬樹華編白话说明")
    assert already_heading.startswith("## ")
    assert not already_heading.startswith("### ")
    assert m["normalize_rendered_heading"]("普通正文", "白话正文") == "白话正文"
    assert m["normalize_rendered_heading"]("# 第一章", "# 第一章") == "## 第一章"
    assert m["normalize_rendered_body_headings"]("# 正文小标题\n## 章节\n# 另一段") == (
        "## 正文小标题\n## 章节\n## 另一段"
    )


def _check_render_preserves_exact_foldback_source(tmp_path: Path) -> None:
    globals_ = m["render_book"].__globals__
    original_paths = {key: globals_[key] for key in ("SEGMENTS", "RESULTS", "DRAFTS", "V3")}
    segments_dir = tmp_path / "segments"
    results_dir = tmp_path / "results"
    drafts_dir = tmp_path / "drafts"
    v3_dir = tmp_path / "v3"
    for directory in (segments_dir, results_dir, drafts_dir, v3_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source = "  # 第一章  \n"
    segment_id = "book001-b000001-p000-test"
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    segments = [
        {
            "id": "book001-title",
            "source_sha256": hashlib.sha256("# 测试书".encode("utf-8")).hexdigest(),
            "kind": "title",
            "translatable": False,
            "source": "# 测试书",
            "book_file": "001 测试书.md",
        },
        {
            "id": segment_id,
            "source_sha256": source_hash,
            "kind": "heading",
            "translatable": True,
            "source": source,
            "book_file": "001 测试书.md",
        },
    ]
    result = {
        "id": segment_id,
        "status": "judged",
        "source_sha256": source_hash,
        "modern_text": "# 第一章",
        "judge_verdict": "accept",
        "uncertainty": [14, "原文疑有脱字"],
    }
    (segments_dir / "book001.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in segments) + "\n",
        encoding="utf-8",
    )
    (results_dir / "book001.jsonl").write_text(
        json.dumps(result, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    globals_.update(
        SEGMENTS=segments_dir,
        RESULTS=results_dir,
        DRAFTS=drafts_dir,
        V3=v3_dir,
    )
    try:
        assert m["render_book"](1)
        rendered = (v3_dir / "001 测试书.md").read_text(encoding="utf-8")
        assert sum(line.startswith("# ") for line in rendered.splitlines()) == 1
        assert "## 第一章" in rendered
        assert "> **释读存疑：** 14；原文疑有脱字" in rendered
        folded_source = m["extract_foldback_source"](rendered, segment_id)
        assert folded_source == source
        assert hashlib.sha256(folded_source.encode("utf-8")).hexdigest() == source_hash
    finally:
        globals_.update(original_paths)


def test_render_preserves_exact_foldback_source() -> None:
    with tempfile.TemporaryDirectory(prefix="v3-render-test-") as temp_dir:
        _check_render_preserves_exact_foldback_source(Path(temp_dir))


def test_partial_response_merge() -> None:
    expected = ["a", "b", "c"]
    collected = {}
    missing, extras, added = m["merge_partial_response_items"](
        {"items": [{"id": "a", "value": 1}, {"id": "outside"}]},
        expected,
        collected,
    )
    assert missing == ["b", "c"]
    assert extras == 1 and added == 1
    assert list(collected) == ["a"]
    missing, extras, added = m["merge_partial_response_items"](
        {"items": [{"id": "b", "value": 2}, {"id": "c", "value": 3}]},
        expected,
        collected,
    )
    assert missing == []
    assert extras == 0 and added == 2
    assert [collected[sid]["value"] for sid in expected] == [1, 2, 3]


def test_top_level_array_response_envelope() -> None:
    rows = [{"id": "a", "modern_text": "白话释读"}]
    wrapped, changed, reason = m["normalize_response_envelope"](rows, ["a"])
    assert changed is True and reason == "top_level_array_wrapped_as_items"
    assert wrapped == {"items": rows}
    untouched, changed, reason = m["normalize_response_envelope"]({"items": rows}, ["a"])
    assert changed is False and reason is None
    assert untouched == {"items": rows}
    single, changed, reason = m["normalize_response_envelope"](rows[0], ["a"])
    assert changed is True and reason == "top_level_item_wrapped_as_items"
    assert single == {"items": rows}
    unknown, changed, reason = m["normalize_response_envelope"](
        {"id": "outside", "modern_text": "不应接纳"}, ["a"]
    )
    assert changed is False and reason is None
    assert unknown["id"] == "outside"
    aliased, changed, reason = m["normalize_response_envelope"](
        {"results": rows, "diagnostic": "secret content is not logged"}, ["a"]
    )
    assert changed is True and reason == "results_array_wrapped_as_items"
    assert aliased == {"items": rows}
    shape = m["response_shape_summary"](
        {"result": "private source text", "rows": [1], "metadata": {}}
    )
    assert "private source text" not in shape
    assert "rows" in shape and "list_fields" in shape


def test_model_request_semaphore_scope() -> None:
    writer_a = m["model_request_semaphore"]("writer-test")
    writer_b = m["model_request_semaphore"]("writer-test")
    judge = m["model_request_semaphore"]("judge-test")
    assert writer_a is writer_b
    assert writer_a is not judge


def test_global_request_semaphore_cap() -> None:
    semaphore = m["GLOBAL_REQUEST_SEMAPHORE"]
    assert m["MAX_CONCURRENT_API_REQUESTS"] == 2
    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    assert not semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()


def test_default_route_preserves_cache_identity() -> None:
    payload = {"items": [{"id": "seg-1", "source": "古文"}]}
    route = m["normalize_model_route"]("model-a", {})
    record = m["request_cache_material_record"](
        "model-a", "system", payload, 100, route
    )
    assert record == {
        "model": "model-a",
        "system": "system",
        "payload": payload,
        "max_tokens": 100,
    }


def test_multi_provider_stable_sharding() -> None:
    logical_model = "logical-model-test"
    routes = m["parse_model_routes"](
        json.dumps(
            {
                logical_model: [
                    {
                        "provider": "provider-a",
                        "api_url": "https://a.example/v1/chat/completions",
                        "api_key_env": "PROVIDER_A_API_KEY",
                        "remote_model": "remote-a",
                        "max_concurrent_requests": 3,
                        "max_concurrent_model_requests": 2,
                        "prices": {"input": 1, "output": 2},
                    },
                    {
                        "provider": "provider-b",
                        "api_url": "https://b.example/v1/chat/completions",
                        "api_key_env": "PROVIDER_B_API_KEY",
                        "remote_model": "remote-b",
                        "stream": False,
                        "prices": {"input": 1.5, "output": 2.5},
                    },
                ]
            }
        )
    )[logical_model]
    previous = m["MODEL_ROUTES"].get(logical_model)
    m["MODEL_ROUTES"][logical_model] = routes
    try:
        payload = {"items": [{"id": "fixed-id", "source": "甲"}]}
        first = m["route_for_model"](logical_model, payload)
        second = m["route_for_model"](logical_model, payload)
        assert m["route_identity"](first) == m["route_identity"](second)
        providers = {
            m["route_for_model"](
                logical_model,
                {"items": [{"id": f"seg-{index}", "source": "甲"}]},
            )["provider"]
            for index in range(30)
        }
        assert providers == {"provider-a", "provider-b"}
        custom_record = m["request_cache_material_record"](
            logical_model, "system", payload, 100, first
        )
        assert "route" in custom_record
    finally:
        if previous is None:
            m["MODEL_ROUTES"].pop(logical_model, None)
        else:
            m["MODEL_ROUTES"][logical_model] = previous


def test_provider_independent_semaphore_cap() -> None:
    route = m["normalize_model_route"](
        "remote-cap-test",
        {
            "provider": "provider-cap-test",
            "api_url": "https://cap.example/v1/chat/completions",
            "api_key_env": "CAP_TEST_API_KEY",
            "max_concurrent_requests": 2,
            "prices": {"input": 1, "output": 1},
        },
    )
    semaphore = m["provider_request_semaphore"](route)
    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    assert not semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()


def test_route_config_rejects_embedded_secret() -> None:
    try:
        m["parse_model_routes"](
            json.dumps(
                {
                    "model": {
                        "provider": "bad",
                        "api_url": "https://bad.example/v1/chat/completions",
                        "api_key": "must-not-be-here",
                        "api_key_env": "BAD_API_KEY",
                        "prices": {"input": 1, "output": 1},
                    }
                }
            )
        )
    except ValueError as exc:
        assert "禁止写密钥值" in str(exc)
    else:
        raise AssertionError("embedded secret route should be rejected")


def test_semantic_judge_routing() -> None:
    assert not m["needs_semantic_judge"]({"language": "modern_chinese"})
    assert m["needs_semantic_judge"]({"language": "classical_chinese"})
    assert m["needs_semantic_judge"]({"language": "japanese"})
    assert m["needs_semantic_judge"]({})


def test_writer_does_not_repeat_term_notes() -> None:
    assert '"term_notes":' not in m["WRITER_SYSTEM"]
    assert "不要返回 term_notes" in m["WRITER_SYSTEM"]


def test_writer_requires_real_modernization() -> None:
    prompt = m["WRITER_SYSTEM"]
    assert "繁体改成简体、补标点" in prompt
    assert "必须先重新改写再输出" in prompt
    assert "OCR 残缺时，不得原样粘贴冒充译文" in prompt


def test_short_segment_contexts() -> None:
    rows = [
        {"id": "a", "source": "前一段讲龙脉来势与束气。", "kind": "prose", "translatable": True},
        {"id": "img", "source": "![图](assets/a.jpg)", "kind": "image", "translatable": False},
        {"id": "b", "source": "察來驗于巳往", "kind": "prose", "translatable": True},
        {"id": "c", "source": "后一段继续说明如何根据祖基龙砂推断。", "kind": "prose", "translatable": True},
        {"id": "d", "source": "长" * 100, "kind": "prose", "translatable": True},
    ]
    contexts = m["build_short_segment_contexts"](rows)
    assert contexts["b"]["context_before"] == "前一段讲龙脉来势与束气。"
    assert contexts["b"]["context_after"] == "后一段继续说明如何根据祖基龙砂推断。"
    assert "d" not in contexts
    assert "items 按原书顺序排列" in m["WRITER_SYSTEM"]
    assert "不得把相邻 item 翻译、合并或重复" in m["WRITER_SYSTEM"]


def test_second_pass_queue_policy() -> None:
    assert q["queue_category"]({"local_issues": ["漏术语"], "judge_verdict": "accept"}) == (
        "auto_repair_local_hard",
        "high",
    )
    assert q["queue_category"]({"local_issues": [], "judge_verdict": "revise"}) == (
        "auto_repair_semantic",
        "high",
    )
    assert q["queue_category"]({"local_issues": [], "judge_verdict": "uncertain"}) == (
        "independent_rejudge_source_uncertain",
        "medium",
    )
    assert q["queue_category"](
        {"local_issues": [], "judge_verdict": "accept", "uncertainty": ["OCR 缺字"]}
    ) == ("transparent_uncertainty_no_rewrite", "low")
    assert q["queue_category"]({"local_issues": [], "judge_verdict": "accept", "uncertainty": []}) == (
        None,
        None,
    )


def test_empty_modern_text_is_not_complete() -> None:
    sha = "a" * 64
    assert m["is_complete_result"](
        {"status": "judged", "source_sha256": sha, "modern_text": "已完成释读"}, sha
    )
    assert not m["is_complete_result"](
        {"status": "judged", "source_sha256": sha, "modern_text": ""}, sha
    )
    assert not m["is_complete_result"](
        {"status": "judged", "source_sha256": sha, "modern_text": "   "}, sha
    )
    assert not m["is_complete_result"](
        {"status": "judged", "source_sha256": "b" * 64, "modern_text": "释读"}, sha
    )


def test_orphaned_historical_result_is_not_expected_complete() -> None:
    current_sha = "a" * 64
    expected_hashes = {"current-segment": current_sha}
    current = {
        "id": "current-segment",
        "status": "judged",
        "source_sha256": current_sha,
        "modern_text": "已完成释读",
    }
    orphan = {
        "id": "historical-orphan",
        "status": "judged",
        "source_sha256": "b" * 64,
        "modern_text": "旧分段历史结果",
    }
    assert m["is_expected_complete_result"](current, expected_hashes)
    assert not m["is_expected_complete_result"](orphan, expected_hashes)


def test_malformed_judge_verdict_fails_closed() -> None:
    malformed = "accept','confidence':'high','issues':[]"
    assert m["normalize_judge_verdict"]("accept") == "accept"
    assert m["normalize_judge_verdict"](malformed) == "uncertain"
    assert q["queue_category"]({"judge_verdict": malformed}) == (
        "independent_rejudge_source_uncertain",
        "medium",
    )


def test_transient_retry_budget_resets_after_checkpoint_progress() -> None:
    runtime = m["run_book_with_retries"].__globals__
    originals = {
        "run_book": runtime["run_book"],
        "completed_result_count_for_book": runtime[
            "completed_result_count_for_book"
        ],
        "atomic_json": runtime["atomic_json"],
        "sleep": runtime["time"].sleep,
    }
    completed = 0
    calls = 0

    def fake_count(_book_no: int) -> int:
        return completed

    def fake_run_book(*_args, **_kwargs) -> None:
        nonlocal completed, calls
        calls += 1
        if calls <= m["MAX_BOOK_TRANSIENT_RESTARTS"] + 1:
            completed += 1
            raise RuntimeError("API 请求连续失败（siliconflow）：read timed out")

    try:
        runtime["run_book"] = fake_run_book
        runtime["completed_result_count_for_book"] = fake_count
        runtime["atomic_json"] = lambda *_args, **_kwargs: None
        runtime["time"].sleep = lambda _seconds: None
        state = {"current_books": [28], "transient_retries": {}}
        assert m["run_book_with_retries"](28, None, state) == 28
        assert calls == m["MAX_BOOK_TRANSIENT_RESTARTS"] + 2
    finally:
        runtime["run_book"] = originals["run_book"]
        runtime["completed_result_count_for_book"] = originals[
            "completed_result_count_for_book"
        ]
        runtime["atomic_json"] = originals["atomic_json"]
        runtime["time"].sleep = originals["sleep"]


def test_secret_absent_from_v3_files() -> None:
    key_pattern = re.compile(r"sk-[A-Za-z0-9]{20,}")
    for path in m["V3"].rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not key_pattern.search(text), f"potential API key found in {path}"


def main() -> None:
    tests = [
        test_split_and_hash,
        test_protected_values,
        test_conservative_quality_gate,
        test_classification,
        test_split_markdown_media_block,
        test_merge_japanese_fragments,
        test_html_split,
        test_saved_segments,
        test_parse_json_content,
        test_invalid_json_writer_batch_is_split_without_repeating_parent,
        test_partial_writer_batch_requests_only_missing_ids,
        test_collect_streamed_chat,
        test_collect_streamed_chat_has_total_duration_guard,
        test_cached_input_cost,
        test_usage_zero_fields_use_conservative_byte_estimates,
        test_transient_api_failure_classifier,
        test_rendered_heading_normalization,
        test_render_preserves_exact_foldback_source,
        test_partial_response_merge,
        test_top_level_array_response_envelope,
        test_model_request_semaphore_scope,
        test_global_request_semaphore_cap,
        test_default_route_preserves_cache_identity,
        test_multi_provider_stable_sharding,
        test_provider_independent_semaphore_cap,
        test_route_config_rejects_embedded_secret,
        test_semantic_judge_routing,
        test_writer_does_not_repeat_term_notes,
        test_writer_requires_real_modernization,
        test_short_segment_contexts,
        test_second_pass_queue_policy,
        test_empty_modern_text_is_not_complete,
        test_orphaned_historical_result_is_not_expected_complete,
        test_malformed_judge_verdict_fails_closed,
        test_transient_retry_budget_resets_after_checkpoint_progress,
        test_secret_absent_from_v3_files,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS total={len(tests)}")


if __name__ == "__main__":
    main()
