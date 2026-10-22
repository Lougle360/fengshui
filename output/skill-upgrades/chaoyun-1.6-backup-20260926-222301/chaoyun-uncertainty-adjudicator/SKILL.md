---
name: chaoyun-uncertainty-adjudicator
description: Adjudicate OCR, layout, glyph, translation, reader-edit, proof, and collation uncertainties through unlimited review cycles in a Chaoyun ancient-book workspace. Use at any evidence or reader checkpoint to separate true reader-impacting defects from stamps, cross-page continuations, duplicates, confirmed variants, and editorial notes.
---

# 超云古书疑点裁决

Turn raw model doubts into a traceable, reader-safe uncertainty ledger. Do not treat every model warning as missing source text.

This is one lifecycle with unlimited checkpoints, not separate first, second, or final doubt lists. Each new pass uses a stable `review_cycle` and `checkpoint`; all cycles append to the same candidate and adjudication history.

## Required separation

Keep three append-only or reproducible views:

- `uncertainty-candidates.jsonl`: every raw candidate raised by OCR, vision, translation, rules, or review.
- `uncertainty-adjudication.jsonl`: the decision history, evidence, grouping, and any confirmed correction.
- `uncertain-items.jsonl`: only the current unresolved material items that a reader or later reviewer must know.

For an older workspace, run `python scripts/migrate_legacy_ledger.py <workspace>`. It creates a timestamped backup before writing stable candidate IDs. If the old ledger has no decisions, the migrated candidates deliberately remain unadjudicated and publication stays blocked.

## Adjudication workflow

1. Group candidates that point to the same page region or phrase. Preserve every `candidate_id` in the grouped decision.
2. Record `origin_stage`, `review_cycle`, `checkpoint`, and `introduced_by` for every new-schema candidate. Examples of checkpoints include source reconstruction, normalization, modernization, whole-book reader revision, proof review, and prepublication audit.
3. Inspect the source image, page layout, adjacent pages, other recognition passes, and established variant-character or terminology evidence. A fluent sentence is not transcription evidence.
4. Assign exactly one status:
   - `resolved_confirmed`: the reading is supported by visible or documentary evidence.
   - `resolved_noncontent`: stamp, page header, folio mark, bleed-through, border, or other nonbody material.
   - `resolved_structural`: cross-page continuation, reading-order relation, caption association, or editorial explanation rather than an unread glyph.
   - `resolved_duplicate`: merged into another decision; retain the linked candidate IDs.
   - `open_material`: the source still does not support a unique reading or the missing passage is real.
5. Record `reader_impact` as `none`, `low`, `medium`, or `high`. A doubt about an unused colophon name is not equivalent to a missing doctrinal sentence.
6. Apply a source correction only for `resolved_confirmed`, recording exact before/after text and evidence. Do not repair source text from meaning alone.
7. Project only `open_material` decisions into `uncertain-items.jsonl`. Merge repeated reports into one intelligible note and state whether ordinary reading is affected.
8. When revising a decision in any later cycle, append a new active adjudication with `supersedes` and mark the previous record `active: false`. Never rewrite the old rationale. Every active `open_material` decision keeps a stable `issue_id` across revisions.
9. Run `scripts/project_open_items.py <workspace> --check` after every checkpoint. Before publication, run it without `--check` once to regenerate the open-item projection atomically, then check again.

Read [references/adjudication-contract.md](references/adjudication-contract.md) when creating or validating records.

## Gates

- Grade A requires no material unresolved decision.
- Grade B may retain bounded `low` or `medium` open items that do not undermine ordinary reading.
- A `high` open item that affects a central argument, diagram, formula, name attribution, or chapter continuity blocks Grade A and normally makes the affected section a draft until explicitly bounded.
- Library stamps, traditional-versus-simplified notes, semantics-only commentary, and already-confirmed glyphs must not inflate the reader-facing count.
- The final report states both numbers: original candidates adjudicated and material items still open.
