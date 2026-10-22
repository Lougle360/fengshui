from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(r"D:\壮五福\风水项目")
WORKSPACE = ROOT / "output" / "V4" / "001-青囊海角经"
CACHE = ROOT / "Md" / "V3" / "_work" / "api_cache"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    queue = read_jsonl(WORKSPACE / "40-modernized" / "repair-queue.jsonl")
    repair_ids = {row["v3_segment_id"] for row in queue}
    hits: dict[str, list[dict]] = defaultdict(list)
    parsed_files = 0
    parse_errors = 0
    for path in CACHE.glob("*.json"):
        raw = path.read_text(encoding="utf-8", errors="replace")
        if "book001-" not in raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        parsed_files += 1
        response = payload.get("response") or {}
        items = response.get("items") if isinstance(response, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("id") not in repair_ids:
                continue
            hits[item["id"]].append(
                {
                    "cache_file": path.name,
                    "created_at": payload.get("created_at"),
                    "model": payload.get("model"),
                    "fields": sorted(item),
                    "modern_text": item.get("modern_text"),
                    "candidate": item.get("candidate"),
                    "verdict": item.get("verdict") or item.get("judge_verdict"),
                    "confidence": item.get("confidence"),
                    "issues": item.get("issues") or item.get("judge_issues") or [],
                    "uncertainty": item.get("uncertainty") or [],
                }
            )

    with_candidates = {
        segment_id: rows
        for segment_id, rows in hits.items()
        if any(row.get("modern_text") or row.get("candidate") for row in rows)
    }
    with_accept_verdict = {
        segment_id: rows
        for segment_id, rows in hits.items()
        if any(str(row.get("verdict", "")).lower() == "accept" for row in rows)
    }
    candidate_versions = Counter(
        sum(bool(row.get("modern_text") or row.get("candidate")) for row in rows)
        for rows in hits.values()
    )
    report = {
        "repair_ids": len(repair_ids),
        "cache_files_with_book001": parsed_files,
        "parse_errors": parse_errors,
        "ids_with_any_cache_hit": len(hits),
        "ids_with_candidate_versions": len(with_candidates),
        "ids_with_accept_verdict_somewhere": len(with_accept_verdict),
        "candidate_version_count_distribution": dict(sorted(candidate_versions.items())),
        "sample": {segment_id: rows for segment_id, rows in list(hits.items())[:8]},
    }
    (WORKSPACE / "40-modernized" / "cached-v3-candidate-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "sample"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
