# Workspace and data contract

## Directory layout

```text
book-workspace/
|-- book.json
|-- run-state.json
|-- 00-intake/
|   `-- source-manifest.json
|-- 10-diagnosis/
|   |-- profile.json
|   `-- page-map.jsonl
|-- 20-source/
|   |-- source.md
|   |-- blocks.jsonl
|   `-- pages/
|-- 30-normalized/
|   |-- normalized.md
|   |-- blocks.jsonl
|   `-- changes.jsonl
|-- 40-modernized/
|   |-- modernized.md
|   |-- blocks.jsonl
|   `-- terminology.json
|-- 50-edited/
|   |-- modern-reading.md
|   |-- blocks.jsonl
|   |-- reader-aids.json
|   |-- reader-review.json
|   |-- reader-revision-ledger.jsonl
|   |-- reader-acceptance-report.json
|   |-- review-history/ (immutable cycle snapshots and execution records)
|   `-- editorial-report.json
|-- 60-publication/
|   |-- modern-reading.md
|   |-- <book-title>·<edition-label>.pdf
|   |-- modern-reading.pdf (optional internal alias)
|   `-- supplements/
|       |-- source-comparison.md
|       `-- source-comparison.pdf
`-- 90-audit/
    |-- events.jsonl
    |-- uncertainty-candidates.jsonl
    |-- uncertainty-adjudication.jsonl
    |-- uncertain-items.jsonl
    |-- release-binding.json (final file hashes and per-page visual review)
    `-- quality-report.json
```

Files appear only when their stage runs. Do not create fake empty outputs to satisfy the layout.

New workspaces declare workflow schema 1.5 and explicit `delivery_mode`. Reader review and acceptance use schema 1.1; their exact edit, section coverage and execution-record fields are maintained in the reader-experience-reviser contract. Ordinary-reader editions additionally require `50-edited/delivery-contract.json` and `90-audit/fidelity-review.json` under [delivery-and-rework.md](delivery-and-rework.md). Existing books need fresh review, not automatic successful migration. Preserve old records and all unresolved issue identities.

For an ordinary-reader edition, `50-edited/reader-aids.json`, the three whole-book reader-review artifacts, and `50-edited/editorial-report.json` are required before publication. The reader-aids file and revision ledger are item-level evidence sources; the editorial report is a derived summary and may not self-certify counts. Its schema and evidence rules are defined in [editorial-evidence-contract.md](editorial-evidence-contract.md). Supplemental PDFs stay below `60-publication/supplements/`; the publication root contains only the single declared official reader PDF and an optional exact internal alias.

## Edition and release metadata

`book.json` records `title`, `edition_label`, `target_reader`, `author`, `editor`, `producer`, `release_filename`, `source_pdf_pages`, and the included/excluded page accounting when known. The official reader PDF uses `release_filename`; `modern-reading.pdf` may exist only as a stable internal alias and must not create ambiguity about which file is the release artifact.

## Stable identity

- `book_id` is fixed at intake.
- `page_id` uses `P` plus a zero-padded logical page number, such as `P000123`.
- `block_id` uses the page ID and source reading-order index, such as `P000123-B007`.
- Later stages preserve every source `block_id`; they may mark it `noncontent`, `unreadable`, `retained`, `translated`, or `excluded_with_reason`, but may not silently drop it.
- A split translation uses `segment_id` beneath the same `block_id`. A merge lists every contributing `block_id`.

## Block record

Each JSONL record contains these shared fields:

```json
{
  "schema_version": "1.0",
  "book_id": "sha256-prefix",
  "page_id": "P000123",
  "block_id": "P000123-B007",
  "source_page": 128,
  "block_type": "body",
  "bbox": [120, 340, 980, 620],
  "source_image": "20-source/pages/P000123.jpg",
  "source_text": "...",
  "normalized_text": null,
  "modern_text": null,
  "language": "lzh",
  "operation": "source",
  "disposition": "retained",
  "confidence": 0.97,
  "evidence": [],
  "notes": []
}
```

Required values may be `null` before their stage, never fabricated. `bbox` is in source-page pixel coordinates and may be `null` only when the input has no reliable layout coordinates.

## Language codes

- `zh-Hans`: modern simplified Chinese
- `zh-Hant`: modern traditional Chinese
- `lzh`: classical/literary Chinese
- `ja`: modern Japanese
- `ja-bungo`: classical Japanese
- `kanbun`: Japanese kanbun or kundoku-related text
- `mixed`: block needs finer segmentation
- `und`: genuinely undetermined

## Run state

`run-state.json` records each stage as `pending`, `running`, `passed`, `passed_with_ledger`, `blocked`, or `failed`, plus timestamps, counts, model/tool identity, cost, and a short evidence summary. Never change a failed or blocked stage to passed without a new audit event explaining the resolution.

## Audit rules

`90-audit/events.jsonl` is append-only. Every automatic correction, translation acceptance, exclusion, manual override, and gate result records actor/tool, time, source IDs, before/after values, confidence, and rationale. Secrets and full API credentials must never appear in any artifact.

Uncertainty has three distinct views. `uncertainty-candidates.jsonl` preserves raw model and reviewer candidates. `uncertainty-adjudication.jsonl` groups them and records one of `resolved_confirmed`, `resolved_noncontent`, `resolved_structural`, `resolved_duplicate`, or `open_material`, plus reader impact and evidence. All stages use the same ledgers through unlimited `review_cycle` and `checkpoint` values; do not create separate first-, second-, or final-doubt files. Revisions append a new decision using `supersedes`; only one active decision may cover each candidate. `uncertain-items.jsonl` is an atomically generated projection containing only active `open_material` decisions with stable issue IDs. Read the `$chaoyun-uncertainty-adjudicator` contract before creating these records.
