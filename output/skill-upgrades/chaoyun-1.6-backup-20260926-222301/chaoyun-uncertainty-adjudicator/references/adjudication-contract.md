# Uncertainty adjudication contract

## Candidate record

```json
{
  "schema_version": "1.2",
  "candidate_id": "UC000123",
  "page_id": "P000017",
  "block_id": "P000017-B001",
  "origin_stage": "source",
  "review_cycle": "RC0001",
  "checkpoint": "source_reconstruction",
  "kind": "glyph",
  "excerpt": "〔疑〕",
  "reason": "stamp overlaps caption",
  "source_image": "20-source/pages/P000017.jpg",
  "severity": "medium",
  "created_by": "vision-pass-2"
}
```

`kind` may be `glyph`, `missing`, `reading_order`, `layout`, `language`, `translation`, `terminology`, `structure`, or `noncontent_candidate`. Candidate records are raw evidence and are never deleted after adjudication.

## Adjudication record

```json
{
  "schema_version": "1.2",
  "adjudication_id": "UA000087",
  "candidate_ids": ["UC000123", "UC000124"],
  "status": "resolved_noncontent",
  "reader_impact": "none",
  "active": true,
  "supersedes": null,
  "review_cycle": "RC0001",
  "checkpoint": "source_reconstruction",
  "page_id": "P000017",
  "block_id": "P000017-B001",
  "rationale": "The overlap is a library stamp outside the caption.",
  "evidence": ["20-source/pages/P000017.jpg"],
  "before": null,
  "after": null,
  "reviewed_at": "2026-01-01T00:00:00Z",
  "reviewer": "chaoyun-uncertainty-adjudicator"
}
```

Every candidate belongs to exactly one active adjudication. One adjudication may group repeated candidates. A review-discovered issue that had no prior candidate must first receive a new candidate record.

A later review appends a new decision with `supersedes` pointing to the previous decision and changes the previous record to `active: false`. Historical decisions stay in the file. An active `open_material` decision also requires a stable `issue_id`, preferably derived from the canonical candidate ID rather than its row number.

There is no fixed number of review cycles. `review_cycle` identifies a stable pass such as `RC0001`; `checkpoint` describes why it ran. Candidates and decisions from source, normalization, modernization, whole-book reader revision, proof review, and final audit remain in the same ledgers. Schema 1.1 legacy records may omit these fields; every schema 1.2+ record requires them.

## Open-item projection

```json
{
  "schema_version": "1.0",
  "issue_id": "UI-UC000123",
  "adjudication_id": "UA000099",
  "status": "open",
  "reader_impact": "medium",
  "page_id": "P000080",
  "block_id": "P000080-B001",
  "note": "The surviving scan ends mid-sentence; the edition stops rather than inventing a continuation.",
  "source_image": "20-source/pages/P000080.jpg"
}
```

The open projection contains no resolved record. Its set of `adjudication_id` values must equal the set of `open_material` adjudications.
