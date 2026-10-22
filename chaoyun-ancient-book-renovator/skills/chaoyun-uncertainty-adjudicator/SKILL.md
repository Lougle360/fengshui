---
name: chaoyun-uncertainty-adjudicator
description: Adjudicate OCR, layout, glyph, translation, reader-edit, proof, and collation uncertainties through unlimited review cycles in a Chaoyun ancient-book workspace. Use at any evidence or reader checkpoint to separate true reader-impacting defects from stamps, cross-page continuations, duplicates, confirmed variants, and editorial notes.
---

# 超云古书疑点裁决

Turn raw model doubts into a traceable, reader-safe uncertainty ledger. Do not treat every model warning as missing source text.

This is one lifecycle with unlimited checkpoints, not separate first, second, or final doubt lists. Each new pass uses a stable `review_cycle` and `checkpoint`; all cycles append to the same candidate and adjudication history.

## Required separation

Workflow 1.7 reader production shares the 1.6 chapter trial sample and retained evidence. Meaning uncertainty belongs here; a vague introduction or an unhelpful definition with settled meaning belongs to reading-editor. Do not relabel failed explanation as a tolerable source doubt. Retain existing candidate/closure obligations when a registered issue moves to editorial ownership.

Keep three append-only or reproducible views:

- `uncertainty-candidates.jsonl`: every raw candidate raised by OCR, vision, translation, rules, or review.
- `uncertainty-adjudication.jsonl`: the decision history, evidence, grouping, and any confirmed correction.
- `uncertain-items.jsonl`: only the current unresolved material items that a reader or later reviewer must know.

For an older workspace, run `python scripts/migrate_legacy_ledger.py <workspace>`. It creates a timestamped backup before writing stable candidate IDs. Legacy closure claims reopen as `open_material` for evidence-based review; migration never creates successful closure evidence. Candidates without decisions remain unadjudicated and publication stays blocked.

## Adjudication workflow

1. Group candidates that point to the same page region or phrase. Preserve every `candidate_id` in the grouped decision.
2. Register the doubt before editing. New candidate schema 1.3 records `origin_stage`, `review_cycle`, `checkpoint`, `created_by`, `created_at`, precise location/excerpt/reason, severity, a frozen located `input_ref`, and `owner_stage`. Route glyph/order issues to source reconstruction; script/punctuation to normalization; meaning to modernization; explanation to reading edit/revision; rendering to publication. Do not solve an evidence gap through fluent rewriting.
3. Inspect the source image, page layout, adjacent pages, other recognition passes, and established variant-character or terminology evidence. A fluent sentence is not transcription evidence.
4. Assign exactly one status:
   - `resolved_confirmed`: the reading is supported by visible or documentary evidence.
   - `resolved_noncontent`: stamp, page header, folio mark, bleed-through, border, or other nonbody material.
   - `resolved_structural`: cross-page continuation, reading-order relation, caption association, or editorial explanation rather than an unread glyph.
   - `resolved_duplicate`: explicitly points via `duplicate_of` to a canonical candidate whose active decision is closed. Keep repeated findings linked to the main open decision until that decision actually closes; duplicate chains cannot hide an open issue.
   - `open_material`: the source still does not support a unique reading or the missing passage is real.
5. Record `reader_impact` as `none`, `low`, `medium`, or `high`. A doubt about an unused colophon name is not equivalent to a missing doctrinal sentence.
6. Apply a source correction only for `resolved_confirmed`, recording exact before/after text and evidence. Check all six impact scopes: source, translation, terminology, reader text, figures, publication. A corrected closure must replay exactly between immutable snapshots and match the actual current artifact. False positives, noncontent and structural conclusions also require located evidence; none can close by status alone.
7. Project only `open_material` decisions into `uncertain-items.jsonl`. Merge repeated reports into one intelligible note and state whether ordinary reading is affected.
8. When revising a decision in any later cycle, append a new active adjudication with `supersedes` and mark the previous record `active: false`. Never rewrite the old rationale. Every active `open_material` decision keeps a stable `issue_id` across revisions.
9. Use a separate review execution to examine fidelity and reader effect before closure. Retain a content-bound review record; another actor name alone is insufficient. Reopen the original issue when evidence contradicts it or dependencies change, preserving its `issue_id` and prior rationale. Run `scripts/project_open_items.py <workspace> --check` after each checkpoint; never delete history to clear the count.
10. Before scaling to the full book, freeze a representative chapter, exercise the full doubt-handling loop, and conduct a separate review without giving the expected answers. Run `scripts/project_open_items.py <workspace> --pilot`. Report actual verified cases, residual cases, introduced errors, time and cost; do not count a simulation as a real chapter trial.
11. Before publication, independently recheck every active adjudication against the final manuscript in `uncertainty-release-review.json`. Explicitly disclose unresolved material issues. Regenerate the open projection, then run `scripts/project_open_items.py <workspace> --check --publication`. This requires the real chapter-trial report as well as the final recheck.

Read [references/adjudication-contract.md](references/adjudication-contract.md) when creating or validating records.
Read [references/closure-and-trial.md](references/closure-and-trial.md) for workflow 1.6 closure, reopening, dependent-file review, pilot and final-manuscript fields. These requirements apply to every active closed decision, including legacy records. Do not fabricate evidence or review runs to satisfy the contract.

## Gates

- Grade A requires no material unresolved decision.
- Grade B may retain bounded `low` or `medium` open items that do not undermine ordinary reading.
- A `high` open item that affects a central argument, diagram, formula, name attribution, or chapter continuity blocks Grade A and normally makes the affected section a draft until explicitly bounded.
- Library stamps, traditional-versus-simplified notes, semantics-only commentary, and already-confirmed glyphs must not inflate the reader-facing count.
- The final report states both numbers: original candidates adjudicated and material items still open.
- A failed evidence check blocks projection/publication; it never deletes the candidate or overwrites the current projection with an empty one. Report inability to verify rather than promising zero doubts. These checks establish evidence integrity and recorded review, not that a model or human judgment is necessarily correct.
