#!/usr/bin/env python3
"""Initialize an isolated, traceable Chaoyun book workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


STAGES = [
    "intake",
    "diagnosis",
    "source",
    "source_adjudicated",
    "normalized",
    "book_understood",
    "reader_designed",
    "sample_accepted",
    "modernized",
    "edited",
    "reader_revised",
    "final_adjudicated",
    "publication",
]
DIRECTORIES = [
    "00-intake",
    "10-diagnosis",
    "20-source/pages",
    "30-normalized",
    "40-modernized",
    "50-edited",
    "60-publication",
    "90-audit",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_pdf", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--edition-label", help="Reader-facing edition label, for example 现代白话版")
    parser.add_argument("--target-reader", help="Declared reader, for example 现代普通读者")
    parser.add_argument("--author")
    parser.add_argument("--editor")
    parser.add_argument("--producer")
    parser.add_argument("--delivery-mode", choices=["ordinary_reader", "source_comparison", "evidence_archive"], default="ordinary_reader")
    parser.add_argument(
        "--copy-source",
        action="store_true",
        help="Copy the source to 00-intake/source.pdf for ASCII-safe native processing.",
    )
    args = parser.parse_args()

    source = args.source_pdf.expanduser().resolve()
    output = args.output_directory.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        parser.error(f"source_pdf is not a PDF file: {source}")
    if output.exists() and any(output.iterdir()):
        parser.error(f"output_directory must be new or empty: {output}")

    output.mkdir(parents=True, exist_ok=True)
    for relative in DIRECTORIES:
        (output / relative).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    digest = sha256(source)
    book_id = digest[:16]
    staged_source = None
    if args.copy_source:
        staged_source = output / "00-intake/source.pdf"
        shutil.copy2(source, staged_source)
        if sha256(staged_source) != digest:
            raise RuntimeError("staged source hash does not match the original")
    manifest = {
        "schema_version": "1.0",
        "book_id": book_id,
        "source_path": str(source),
        "source_name": source.name,
        "source_bytes": source.stat().st_size,
        "source_sha256": digest,
        "source_copied": bool(staged_source),
        "staged_source": str(staged_source) if staged_source else None,
        "created_at": now,
    }
    release_filename = f"{source.stem}·{args.edition_label}.pdf" if args.edition_label else None
    write_json(
        output / "book.json",
        {
            "schema_version": "1.0",
            "workflow_schema_version": "1.9",
            "delivery_mode": args.delivery_mode,
            "book_id": book_id,
            "title": source.stem,
            "edition_label": args.edition_label,
            "target_reader": args.target_reader,
            "author": args.author,
            "editor": args.editor,
            "producer": args.producer,
            "release_filename": f"60-publication/{release_filename}" if release_filename else None,
            "source_pdf_pages": None,
        },
    )
    write_json(output / "00-intake/source-manifest.json", manifest)
    write_json(
        output / "run-state.json",
        {
            "schema_version": "1.0",
            "workflow_schema_version": "1.9",
            "book_id": book_id,
            "updated_at": now,
            "stages": {stage: {"status": "pending"} for stage in STAGES
                       if args.delivery_mode == "ordinary_reader" or stage not in {"book_understood", "reader_designed", "sample_accepted"}},
            "current_stage": "intake",
        },
    )
    if args.delivery_mode == "ordinary_reader":
        write_json(
            output / "50-edited/review-policy.json",
            {
                "schema_version": "1.0",
                "minimum_full_passes": 3,
                "required_stable_passes": 2,
                "required_methods": ["manuscript_reader", "source_fidelity", "final_pdf_reader"],
                "rule": "Continue until all blocking issues close and the final two complete passes find no new blockers.",
            },
        )
    (output / "90-audit/events.jsonl").touch()
    (output / "90-audit/uncertainty-candidates.jsonl").touch()
    (output / "90-audit/uncertainty-adjudication.jsonl").touch()
    (output / "90-audit/uncertain-items.jsonl").touch()
    print(
        json.dumps(
            {"workspace": str(output), "book_id": book_id, "staged_source": str(staged_source) if staged_source else None},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
