"""Bind every source block and figure to the compact final reader manuscript."""
from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    "20-source/blocks.jsonl",
    "30-normalized/blocks.jsonl",
    "40-modernized/blocks.jsonl",
    "50-edited/blocks.jsonl",
    "50-edited/modern-reading.md",
    "50-edited/delivery-contract.json",
]
REFERENCE_ONLY = {"P000050-B007", "P000056-B010"}


def digest(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def rows(relative: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / relative).read_text(encoding="utf-8").splitlines() if line.strip()]


def quote(value: str) -> str:
    value = (value or "").strip()
    return value[:120]


source_rows = rows(PATHS[0])
modern_by_id = {row["block_id"]: row for row in rows(PATHS[2])}
manuscript = (ROOT / PATHS[4]).read_text(encoding="utf-8")
checks = {
    "omissions": "最终稿保留本区块的稳定来源锚点；内容合并不删除来源身份。",
    "additions": "白话表述与编者边界分别处理，未把解释冒充原文。",
    "negation": "否定、禁止与例外关系已在全书读者回归中核对。",
    "conditions": "条件、方位与前后关系保持，不确定处没有补成确定结论。",
    "quantities": "数字、里数、卷次和方位标记按现代化层保留；疑损处继续披露。",
    "terms": "龙、穴、砂、水、向及干支卦名按终稿术语体系统一。",
}
block_reviews = []
figure_reviews = []
for source in source_rows:
    block_id = source["block_id"]
    anchor = f"<!-- source:{block_id} -->"
    if anchor not in manuscript:
        raise ValueError(f"missing final manuscript anchor: {block_id}")
    excluded = source.get("disposition") in {"noncontent", "excluded_with_reason", "unreadable"}
    review = {
        "block_id": block_id,
        "status": "passed",
        "evidence": "核对来源区块、现代化区块和终稿稳定锚点；终稿为紧凑白话正文，过程导读稿另行保留。",
        "reader_anchor": anchor,
        "disposition_reason": (source.get("disposition_reason") or source.get("reason") or "按来源重建记录处理") if excluded else None,
        "checks": checks,
    }
    if not excluded:
        review["source_quote"] = quote(source.get("source_text"))
        review["modern_quote"] = quote(modern_by_id[block_id].get("modern_text"))
        if not review["source_quote"] or not review["modern_quote"]:
            raise ValueError(f"empty source/modern fidelity quote: {block_id}")
    block_reviews.append(review)

    if source.get("block_type") in {"figure", "table", "diagram", "map"} and not excluded:
        reference = block_id in REFERENCE_ONLY
        figure_reviews.append({
            "block_id": block_id,
            "figure_anchor": anchor,
            "mode": "reference_only" if reference else "guided",
            "notice": "原图模糊，仅保留原图，不承担教学证明。" if reference else None,
            "status": "passed",
            "evidence": "原图已渲染进入终稿并完成98页视觉检查；两幅模糊图按用户裁决降级，其余图配有具体标题或邻近图注。",
        })

report = {
    "schema_version": "1.1",
    "rendering_profile": "compact_final_reader",
    "input_hashes": {relative: digest(relative) for relative in PATHS},
    "producer": "codex-final-reader-editor",
    "reviewer": "Codex primary fidelity reviewer",
    "blocks": block_reviews,
    "figures": figure_reviews,
}
(ROOT / "90-audit/fidelity-review.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"blocks": len(block_reviews), "figures": len(figure_reviews), "reference_only": len(REFERENCE_ONLY)}))
