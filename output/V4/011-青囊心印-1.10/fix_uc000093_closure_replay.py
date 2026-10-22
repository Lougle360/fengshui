"""Bind UA000002 to the complete, real before/after snapshot delta."""
from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "90-audit/uncertainty-adjudication.jsonl"
BEFORE = ROOT / "90-audit/source-reading/snapshots/uc000093-collation/pages-019-020.before.json"
AFTER = ROOT / "90-audit/source-reading/snapshots/uc000093-collation/pages-019-020.after.json"
CURRENT = ROOT / "20-source/transcription-inputs/pages-019-020.json"
REVIEW = ROOT / "90-audit/source-reading/uc000093-closure-independent.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    before = BEFORE.read_text(encoding="utf-8")
    after = AFTER.read_text(encoding="utf-8")
    if CURRENT.read_bytes() != AFTER.read_bytes():
        raise SystemExit("current transcription no longer matches the accepted after snapshot")

    start = 0
    limit = min(len(before), len(after))
    while start < limit and before[start] == after[start]:
        start += 1
    suffix = 0
    while (
        suffix < len(before) - start
        and suffix < len(after) - start
        and before[len(before) - 1 - suffix] == after[len(after) - 1 - suffix]
    ):
        suffix += 1
    before_end = len(before) - suffix
    after_end = len(after) - suffix

    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    previous = next(row for row in rows if row.get("adjudication_id") == "UA000001")
    previous["active"] = False
    decision = next(row for row in rows if row.get("adjudication_id") == "UA000002")
    change = decision["closure"]["change"]
    change.update(
        start_offset=start,
        end_offset=before_end,
        before=before[start:before_end],
        after=after[start:after_end],
    )
    change["input"]["sha256"] = digest(BEFORE)
    change["output"]["sha256"] = digest(AFTER)
    change["current"]["sha256"] = digest(CURRENT)
    decision["closure"]["review_record"] = {
        "path": "90-audit/source-reading/uc000093-closure-independent.json",
        "sha256": digest(REVIEW),
    }

    LEDGER.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "start_offset": start,
                "end_offset": before_end,
                "before_chars": before_end - start,
                "after_chars": after_end - start,
                "replay_ok": before[:start] + change["after"] + before[before_end:] == after,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
