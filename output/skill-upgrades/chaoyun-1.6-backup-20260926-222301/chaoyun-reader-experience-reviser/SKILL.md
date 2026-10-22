---
name: chaoyun-reader-experience-reviser
description: Read a complete modernized book as an ordinary reader, diagnose whole-book comprehension failures, and apply traceable additions, removals from the reading path, rewrites, and reorganizations. Use after the first reading edition and again when a publication candidate needs reader-experience proofing; do not repair OCR or silently change source meaning.
---

# 超云全书读者审编

Read the book from cover to glossary as the declared reader, not as the pipeline that produced it. Separate the first audit pass from the revision pass so that editing does not hide the original reader problem.

## Modes

- **Manuscript mode:** required after `$chaoyun-reading-editor`. Review `50-edited/modern-reading.md`, apply accepted changes, and produce the reader-accepted manuscript before final uncertainty adjudication.
- **Proof mode:** run on the publication candidate when pagination, figure placement, navigation, or rendered context may change the reading experience. Return content defects to manuscript mode and visual defects to `$chaoyun-quality-publisher`.

## Workflow

1. Save an immutable input manuscript snapshot and its hash, then complete an uninterrupted reader pass before editing. Review introduction promises, prerequisites, navigation, continuity, terminology burden, examples, figures, repetition, source/editor distinction, and closure.
2. Record every obstacle in `50-edited/reader-review.json`. A statement such as “reads well” is not evidence; identify where the reader stops, guesses, backtracks, or loses the argument.
3. Create append-only `50-edited/reader-revision-ledger.jsonl` records using exactly one operation:
   - `add`: supply evidence-based context, explanation, example, transition, route, or caution.
   - `delete_from_reading_path`: remove repetition or pipeline clutter from continuous reading while preserving source material and a destination or provenance reference.
   - `rewrite`: clarify archaic syntax, vague reference, overloaded sentences, or terminology without changing accepted meaning.
   - `reorganize`: improve sequence, hierarchy, cross-reference, or figure placement while retaining a recoverable source order.
4. Route OCR, missing-source, translation, attribution, or meaning uncertainty back to the responsible Skill and create an uncertainty candidate. Do not solve an evidence problem through fluent editing.
5. Apply accepted revisions to the reading layer, update `reader-aids.json` when the introduction or glossary changes, and preserve contributing `block_id` values.
6. Perform a fresh regression read of the revised full manuscript. Cover every section, preserve execution records separately from production, recheck every core term, and close issues across all cycles. Write `50-edited/reader-acceptance-report.json` only from the actual review and revision ledger. Naming two reviewers is not evidence of independent execution.
7. Run `scripts/validate_reader_revision.py <workspace>`. Publication remains blocked until it passes.

Read [references/reader-revision-contract.md](references/reader-revision-contract.md) before creating review or revision records.

Do not mechanically add a preface, summary or example to every section. First establish the actual reader obstacle. A section may need no edit; a zero-edit cycle may pass with full evidenced review. Stop repeating cycles when the same blockers survive two consecutive cycles with no new evidence: preserve the draft, report the unresolved reason, and request only the missing evidence or decision. Budget exhaustion also stops work; a stop is not acceptance.

## Boundaries

- Do not edit `20-source`, repair unreadable glyphs, or turn an uncertain translation into a confident sentence.
- Do not delete source-bearing material merely because it is difficult. Move it to a labeled reference path when continuous reading benefits, and keep provenance.
- Do not add generic background, decorative examples, or praise that answers no reader problem.
- Do not let the same pass both create and certify its own revision. The final regression reviewer differs from the revision producer.

## Gate

Pass when all required reading dimensions have evidence-based regression verdicts, every applied change replays exactly between frozen snapshots, no unresolved reader issue remains from any cycle, the acceptance hash and section evidence match the final manuscript, and medium/high semantic-risk changes have active evidence-backed confirmation in the unified uncertainty lifecycle. Deterministic validation cannot certify that a reader truly understands; report that limit and retain the actual comprehension review.
