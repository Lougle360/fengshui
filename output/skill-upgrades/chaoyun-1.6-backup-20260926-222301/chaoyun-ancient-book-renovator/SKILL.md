---
name: chaoyun-ancient-book-renovator
description: Renovate book-like PDFs into traceable modern Chinese Markdown and polished reader-facing PDFs. Use for complex scanned books, classical Chinese, traditional Chinese, Japanese, vertical text, annotations, or mixed layouts that require diagnosis, faithful reconstruction, modernization, editing, and quality gates; do not use for a simple one-off text extraction.
---

# 超云古书翻新skill

Turn a recoverable book PDF into a modern reading edition without losing the evidentiary link to the source.

## Non-negotiable model

Maintain two separate layers:

- **Evidence layer:** page images, layout coordinates, faithful source text, uncertainty, and provenance.
- **Reading layer:** normalized text, modern Chinese, editorial additions, Markdown, and PDF.

Never replace the evidence layer with a translation or fluent rewrite. Every modernized content block must resolve to a stable source `block_id`. Do not invent missing text from context. Mark unrecoverable content explicitly.

## Editorial truth before packaging

For an ordinary-reader edition, introduction, table of contents, glossary, and figure guidance are semantic deliverables, not decorative front/back matter. Build them only after source reconstruction and modernization are stable.

Organize the reading layer from the reader's point of view using `增、删、改、整`: add only what resolves a comprehension barrier, remove clutter from the continuous path without deleting source evidence, rewrite into natural modern Chinese without changing accepted meaning, and reorganize navigation while preserving source order separately.

- The introduction must state what kind of surviving book this is, distinguish title attribution from demonstrated authorship, and disclose compilation or layering when the evidence shows it.
- Reconstruct the source hierarchy from printed contents pages, running titles,卷次,篇名, and physical-page evidence. Never infer printed page numbers from PDF offsets without a verified mapping.
- Preserve a source-faithful contents view separately from editor-created reading guidance. Label every editor-created introduction or regrouping.
- Build the glossary from terms actually used in this book. Record the first source occurrence and give the contextual meaning; mark opaque terms instead of filling them with generic domain definitions.
- Do not accept a one-line label as a sufficient explanation of a core term. Require plain meaning, book-specific use, an exact source occurrence, an example, related concepts, and likely beginner confusion.
- Give each content-bearing figure a specific reading route. A repeated generic caption is not figure guidance.
- Do not allow model verdicts, repair queues, candidate text, pipeline states, or internal validation language into the reader layer.

For ordinary-reader work, write `50-edited/editorial-report.json` using [references/editorial-evidence-contract.md](references/editorial-evidence-contract.md). The report is auditable evidence for these decisions; it does not replace human semantic review.

## Define the edition before processing

Choose and record one primary delivery mode before bulk work begins:

- **Evidence archive:** optimized for faithful recovery, provenance, and later research.
- **Source-comparison edition:** source text and modern text remain visibly paired.
- **Ordinary-reader modern edition:** a complete contemporary book that a non-specialist can read directly.

When the user asks for “普通人可以直接阅读” or equivalent, use the ordinary-reader modern edition. Do not substitute OCR text, a source comparison, or a lightly punctuated transcript for that deliverable. Read [references/modern-reading-edition.md](references/modern-reading-edition.md) and [references/delivery-and-rework.md](references/delivery-and-rework.md). Record explicit `delivery_mode`, `target_reader`, `edition_label`, and `release_filename` in `book.json`; display wording never selects a gate.

## Run the suite

1. Establish the input PDF, output root, delivery mode, intended reader, modernization depth, and whether paid model calls are authorized. Preserve the source PDF. Record the physical PDF page count and classify every page as included content, front/back matter, blank/noncontent, excluded with reason, or unreadable.
2. Initialize a new isolated workspace:

   ```shell
   python scripts/init_workspace.py input.pdf output-directory --edition-label 现代白话版 --target-reader 现代普通读者
   ```

3. Use `$chaoyun-pdf-diagnoser` to create the book profile and page-level route map. Read [references/routing.md](references/routing.md) when layouts or languages are mixed.
4. Use `$chaoyun-source-reconstructor` to create the faithful source Markdown and page/block records. Do not proceed if source coverage or reading order fails its gate.
5. Run `$chaoyun-uncertainty-adjudicator` at the source-reconstruction checkpoint. It is one unified lifecycle, not a fixed “first” or “second” list: every later stage may open another review cycle while preserving stable candidate and issue identities.
6. Use `$chaoyun-text-normalizer` for script conversion, variant-character policy, punctuation, and segmentation. This stage must not paraphrase.
7. Use `$chaoyun-classical-modernizer` for classical Chinese-to-modern Chinese and Japanese-to-modern Chinese. Route mixed-language blocks separately.
8. Use `$chaoyun-reading-editor` to assemble the complete declared reader edition, including final cover/credits wording, introduction, original preface, body, reader guidance, glossary and appendices. Draft book-specific reader outcomes and keep editorial additions labeled.
9. Use `$chaoyun-reader-experience-reviser` to read the complete manuscript as the target reader, record obstacles before editing, apply traceable `增、删、改、整`, and run a separate regression review. Repeat this reader-revision cycle until its gate passes.
10. Run `$chaoyun-uncertainty-adjudicator` at every checkpoint that generated new OCR, translation, terminology, structural, reader-edit, or proof concerns. There is no maximum number of cycles. The reader-facing ledger contains only current `open_material` decisions with reader impact and evidence.
11. Freeze the complete accepted manuscript and complete the independent source-to-reader fidelity review. Use `$chaoyun-quality-publisher` to render a separate candidate, inspect every ordinary-reader PDF page and navigation target, and run both candidate gates. Only the guarded installer may then back up and atomically replace the official PDF. Do not add new prose after acceptance without returning it for review.
12. Run the deterministic contract validator:

   ```shell
   python scripts/validate_workspace.py output-directory --stage publication
   ```

13. Report the achieved grade, source-page accounting, reader-facing PDF page count, uncertainty cycles, raw candidate count, adjudicated count, material unresolved count, reader revision count, and the single official release path. Never call a run complete merely because files exist.

For scan-heavy books, do not publish a full-book reading edition until every included source page has page-level visual evidence or an explicit `unreadable` / `noncontent` disposition. Text-only judging against inherited OCR is not an independent semantic check. The contract validator and publication auditor must both exit successfully; a hand-written `passed_with_ledger` state cannot override either failure.

## State and stopping rules

Workflow schema 1.5 adds explicit delivery modes, nonempty stage content, actual source-page verification, book-specific outcomes, fidelity bindings and gated candidate promotion. Read the delivery/rework, reader-revision and publication contracts when upgrading a legacy workspace. Preserve old acceptance as history and perform a fresh review; do not turn a legacy pass into a new pass by editing version numbers. Mechanical validation proves artifact consistency and coverage, not comprehension or semantic accuracy.

- Stages are `intake`, `diagnosis`, `source`, `source_adjudicated`, `normalized`, `modernized`, `edited`, `reader_revised`, `final_adjudicated`, and `publication`.
- A later stage may start only after the preceding gate is `passed` or explicitly `passed_with_ledger`.
- Use append-only audit records and preserve stage outputs; do not rewrite earlier evidence in place.
- Support resume from the last completed stage. A retry must not duplicate accepted records.
- Migration and rebuild scripts must be idempotent. Read from an immutable source ledger, never from the projection they overwrite. Before accepting a migration, run it twice or verify that the second run refuses safely and leaves hashes/counts unchanged.
- Before a paid full-book run, estimate pages/cost and obtain authorization. A representative sample is not authorization for the full corpus.
- Keep samples and full-book artifacts in visibly different paths and filenames. A sample may validate routing and quality, but it is never proof that the complete book was converted. Never label a partial, C-grade, or validation-failing artifact as `完整版`, `final`, or publication-ready.
- Keep uncertainty candidates, adjudications, and reader-facing open items distinct. A resolved stamp, variant character, cross-page continuation, semantic comment, or duplicate must remain traceable in history but must not inflate the published uncertainty count.
- Stop on corrupt/encrypted input, missing pages, materially ambiguous reading order, systematic language misclassification, or budget exhaustion. Record the exact blocker.
- Stop a revision loop after two consecutive cycles on the same blockers with no new evidence or meaningful progress. Report the missing input and preserve the draft, rather than consuming unlimited budget or calling the loop successful.

## Completion grades

- **A — publication-ready:** all gates pass, all content blocks are accounted for, and no active material uncertainty remains.
- **B — readable with ledger:** the edition is usable, with bounded uncertainties fully listed and linked to source evidence, and no active high-impact item.
- **C — assisted draft:** substantial uncertainties or layout/translation risks remain; do not present as publication-ready.
- **D — unrecoverable:** source evidence is insufficient for a responsible conversion.

Use [references/data-contract.md](references/data-contract.md) for files and record fields. Use [references/quality-gates.md](references/quality-gates.md) before advancing a stage or declaring completion.
