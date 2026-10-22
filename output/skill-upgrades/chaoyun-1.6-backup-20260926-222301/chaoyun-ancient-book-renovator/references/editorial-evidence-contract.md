# Editorial evidence contract

Use this contract for an ordinary-reader modern edition. It prevents a polished package from being mistaken for a semantically edited book.

## Required file

Create `50-edited/reader-aids.json` under the `$chaoyun-reading-editor` reader-value contract. Then derive `50-edited/editorial-report.json` from that item-level file after reading edit and refresh it after the final uncertainty adjudication. The report is a summary, not a place to assert unverified success totals.

```json
{
  "schema_version": "1.0",
  "book_nature": {
    "summary": "What kind of surviving book this is.",
    "attribution_basis": "Evidence for title attribution versus demonstrated authorship.",
    "compilation_status": "single_work | layered_compilation | uncertain"
  },
  "source_toc": {
    "status": "reconstructed | source_absent_with_reason",
    "source_pages": [5, 6],
    "entry_count": 24,
    "physical_page_mapping_verified": true,
    "reason": null
  },
  "reader_structure": {
    "entry_count": 30,
    "editor_additions_labeled": true
  },
  "glossary": {
    "status": "completed | not_applicable_with_reason",
    "entry_count": 60,
    "entries_with_first_occurrence": 60,
    "core_entry_count": 20,
    "reader_review_sampled": 10,
    "reason": null
  },
  "reader_value": {
    "introduction_sections": 9,
    "review_dimensions": 9,
    "revision_cycle": "RC0003",
    "applied_revisions": 12,
    "producer": "editor-or-model-id",
    "reviewer": "different-reviewer-id",
    "status": "passed"
  },
  "figures": {
    "content_figures_total": 40,
    "content_figures_rendered": 40,
    "content_figures_guided": 40
  },
  "semantic_review": {
    "status": "passed | passed_with_ledger | blocked_by_high_impact_open_items",
    "high_impact_open": 0
  },
  "pipeline_language_scan": {
    "forbidden_matches": 0
  }
}
```

## Evidence rules

- `book_nature.summary` describes the surviving edition, not the reputation of the title in general.
- `attribution_basis` explicitly separates a title-page or traditional attribution from authorship established by the available evidence.
- `source_toc.source_pages` uses physical source-PDF pages. A printed-to-physical mapping must be checked against page images; an assumed constant offset is not evidence.
- If the source has no usable contents, use `source_absent_with_reason` and state the reason. Do not manufacture an original table of contents.
- A completed glossary is book-specific. Every entry has a first source occurrence in `reader-aids.json`, linked to an existing source block and exact quote. Generic domain definitions alone do not satisfy this contract.
- Introduction and glossary counts are computed from `reader-aids.json` and must match it. A producer-written count cannot prove coverage.
- The introduction covers all nine reader-value sections. `$chaoyun-reader-experience-reviser` reviews all nine whole-book dimensions and its acceptance hash matches the final manuscript.
- The revision producer and regression reviewer identities differ. A whole-book review with blocking issues, unresolved proposed changes, missing revision evidence, or insufficient glossary sampling blocks publication.
- `content_figures_guided` counts figure-specific reading guidance, not repeated boilerplate. Decorative images are excluded from all three content-figure counts.
- `semantic_review.high_impact_open` equals the current active adjudication ledger. Any value above zero requires Grade C or lower.
- `pipeline_language_scan.forbidden_matches` covers reader-visible model verdicts, candidate fields, repair queues, internal state names, and validation messages. It must be zero.

The report makes editorial decisions inspectable. It must not be fabricated from target numbers or used as a substitute for checking the source and reader edition.

Workflow 1.5 additionally requires the book-specific outcomes and source-to-reader fidelity evidence in [delivery-and-rework.md](delivery-and-rework.md). The figure counts above are summaries only; actual figure-block inventory, rendered guidance and reviewed locations must also match. A first-occurrence quote, field count or block ID is not proof of accurate meaning.
