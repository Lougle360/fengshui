#!/usr/bin/env python3
"""Freeze workflow 1.9 acceptance code and edition scope before semantic review."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_integrity import sha256, validator_paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    target = root / "90-audit/acceptance-policy-lock.json"
    if target.exists():
        parser.error("preserve or explicitly archive the existing policy lock before creating another")
    scope = root / "10-diagnosis/edition-scope.json"
    if not scope.is_file():
        parser.error("lock 10-diagnosis/edition-scope.json first")
    data = {
        "schema_version": "1.0",
        "policy_version": json.loads((root / "book.json").read_text(encoding="utf-8"))["workflow_schema_version"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "edition_scope_sha256": sha256(scope),
        "validators": {name: sha256(path) for name, path in validator_paths().items()},
    }
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"policy_lock": str(target), "validators": len(data["validators"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
