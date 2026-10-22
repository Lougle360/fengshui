"""Print a compact map of source uncertainty candidates and recorded corrections."""
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent


def main() -> None:
    candidates = [
        json.loads(line)
        for line in (ROOT / "90-audit/uncertainty-candidates.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    corrected: set[str] = set()
    for path in (ROOT / "90-audit/source-reading").glob("corrections-*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for change in payload.get("changes", []):
            corrected.add(change.get("candidate_id") or change.get("issue_id"))
        for change in payload.get("text_changes", []):
            corrected.add(change[-1])
        for key in ("structure_issues", "structural_issues"):
            values = payload.get(key, [])
            corrected.update(values if isinstance(values, list) else [values])
        if payload.get("structural_issue"):
            corrected.add(payload["structural_issue"])
    for row in candidates:
        fields = (
            row["candidate_id"],
            row["page_id"],
            row["kind"],
            row["severity"],
            "CORR" if row["candidate_id"] in corrected else "-",
            row["excerpt"],
            row["reason"],
        )
        print("\t".join(fields))


if __name__ == "__main__":
    main()
