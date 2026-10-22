#!/usr/bin/env python3
"""Validate a candidate PDF and atomically install it at book.json.release_filename."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_pdf(path: Path, expected_pages: int | None) -> int:
    if not path.is_file() or path.stat().st_size == 0 or path.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"candidate is not a nonempty PDF: {path}")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to install the official PDF") from exc
    pages = len(PdfReader(str(path)).pages)
    if expected_pages is not None and pages != expected_pages:
        raise ValueError(f"candidate page count differs from expected: {pages}/{expected_pages}")
    return pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("candidate_pdf", type=Path)
    parser.add_argument("--expected-pages", type=int)
    args = parser.parse_args()
    root = args.workspace.expanduser().resolve()
    candidate = args.candidate_pdf.expanduser().resolve()
    book = json.loads((root / "book.json").read_text(encoding="utf-8"))
    release = book.get("release_filename")
    if not release:
        raise SystemExit("book.json.release_filename is required")
    target = (root / str(release)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SystemExit("release_filename escapes workspace") from exc
    pages = inspect_pdf(candidate, args.expected_pages)
    if not candidate.is_relative_to(root) or candidate == target:
        raise SystemExit("candidate must be a separate file inside the workspace")
    candidate_hash = sha256(candidate)
    report = json.loads((root / '90-audit/quality-report.json').read_text(encoding='utf-8'))
    if report.get('grade') not in {'A', 'B'}:
        raise SystemExit('only an accepted A/B edition may replace the official release')
    scripts = Path(__file__).resolve().parent
    workspace_gate = scripts.parents[1] / "chaoyun-ancient-book-renovator/scripts/validate_workspace.py"
    for script in (workspace_gate, scripts / "audit_publication.py"):
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), str(root), "--candidate-pdf", str(candidate)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise SystemExit(f"candidate gate failed; official release unchanged:\n{result.stdout}\n{result.stderr}")
    if sha256(candidate) != candidate_hash:
        raise SystemExit("candidate changed during audit; official release unchanged")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            with target.open("r+b"):
                pass
        except PermissionError as exc:
            raise SystemExit(f"official PDF is locked or not writable: {target}") from exc
        backup = root / "90-audit/release-history" / sha256(target) / target.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(target, backup)
        if sha256(backup) != sha256(target):
            raise SystemExit("previous release backup failed; official release unchanged")
    handle = tempfile.NamedTemporaryFile("wb", delete=False, dir=target.parent, prefix=target.name + ".", suffix=".tmp.pdf")
    temporary = Path(handle.name)
    try:
        with handle, candidate.open("rb") as source:
            shutil.copyfileobj(source, handle)
            handle.flush()
            os.fsync(handle.fileno())
        inspect_pdf(temporary, pages)
        if sha256(temporary) != candidate_hash:
            raise SystemExit("candidate changed while copying; official release unchanged")
        try:
            os.replace(temporary, target)
        except PermissionError as exc:
            raise SystemExit(f"could not atomically replace locked official PDF: {target}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    print(json.dumps({"official_pdf": str(target), "pages": pages, "bytes": target.stat().st_size, "sha256": sha256(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
