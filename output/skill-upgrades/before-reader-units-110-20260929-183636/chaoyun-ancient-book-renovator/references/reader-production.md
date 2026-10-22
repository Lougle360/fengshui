# Reader production — workflow 1.8

Workflow 1.9 retains this sequence and adds a locked edition-scope contract, `source-reader-map.jsonl`, a frozen acceptance-policy hash, at least three complete reader passes, two stable final passes, and a sequential final-PDF reading record. These are evidence requirements, not a claim that a fixed number of passes proves quality.

Applies to `ordinary_reader` work. Archive/comparison editions retain their routes. This extends, and does not replace, 1.6 uncertainty closure and chapter-trial requirements. Use the same representative chapter for both trials; share actual snapshots and provenance, retaining each trial's distinct questions and conclusions.

## Ownership and sequence

1. **classical-modernizer / understanding**, after normalization: read the whole reliable source. Write `40-modernized/book-understanding.md`: central questions, claims and supporting block IDs, chapter relationships, concept dependencies, useful actual examples/figures and unsettled meanings. Explain in ordinary language. A contents list is insufficient; do not force a single argument onto a miscellany. Central meaning gaps block bulk work; lesser doubts remain in the existing ledger.
2. **reading-editor / design**: consume that brief and write `50-edited/editorial-plan.md`: reader/goal, introduction narrative, chapter connections, prerequisite and first-use explanation order, actual examples, figure routes and reference material. Draft pending `delivery-contract.json` outcomes. Do not write nine isolated sentences to fill nine introduction fields.
3. **modernizer + editor / sample**: translate and edit a representative difficult passage into `50-edited/sample/reader-sample.md`. Include introduction prose, connected body prose and representative concepts; include a content figure when applicable. Keep source IDs and neighboring context. Sample translation is allowed before full modernization.
4. **reader-experience-reviser / sample**: give a fresh reviewer the sample and tasks without production conclusions or answer keys. Preserve actual answers before comparing them to source. Test main point, application, concept distinction and figure reading where applicable. Revise the method before expanding a failed sample to the book.
5. **modernizer + editor / full process edition**: complete translation and editing using settled context and sample quality. The translator owns meaning; the editor owns explanations and reading order. Update dependencies when meanings change. This information-rich manuscript may contain labeled guide material needed for audit and editorial reasoning. Preserve it as an immutable process edition before reader finalization.
6. **reader-experience-reviser / manuscript**: review the complete book in meaningful reading units; preserve answers, identify obstacles, correct locally when appropriate and regression-read changed content in whole-book context. Systematic failure returns to understanding/design.
7. **reader-experience-reviser / final-reader cut**: derive the delivery manuscript from the preserved process edition. Keep all source-bearing content, but remove or move internal metadata, field dumps, repetitive guide prose, generic AI commentary and explanations that solve no observed reader problem. Review every AI-authored section for reader need, plain language, source basis and reading burden. Preserve exact before/after evidence in the revision chain.
8. **reader-experience-reviser / final regression**: read the exact final manuscript in meaningful contiguous units covering every chapter and all front/back matter. The final acceptance records the preserved process snapshot and six evidenced finalization checks. **quality-publisher** uses existing fidelity/rendering gates only after this acceptance.

New ordinary-reader stages between `normalized` and full `modernized`: `book_understood`, `reader_designed`, `sample_accepted`. Run-state is a summary, never its own evidence. No fixed word counts, concept quotas or compulsory revision counts.

## Minimal dependency index

Maintain `50-edited/production-plan.json`, schema `1.0`. New book/run metadata uses workflow `1.8`; the 1.7 production prerequisites remain valid and are extended by final-reader evidence.

## Final-reader cut evidence

The accepted reader cycle includes `final_reader_cut` in `50-edited/reader-acceptance-report.json`:

- `status: passed` and `rendering_profile: compact_final_reader`;
- `process_snapshot` and `process_sha256`, pointing to an immutable non-release manuscript under `50-edited/review-history/<cycle_id>/`;
- `output_sha256`, matching `50-edited/modern-reading.md`;
- six checks—`ai_authored_material`, `guide_material_removed`, `chapter_completeness`, `terminology_plainness`, `figure_truthfulness`, and `pipeline_language_absent`—each with `status: passed` and substantive evidence.

The process snapshot and final manuscript use different paths. They may have identical bytes only when the review genuinely finds no reader-hostile material; never manufacture a change to satisfy the contract. Section reviews and reading tasks still cover the final manuscript itself. This record proves binding and recorded execution, not that the prose is semantically good.

- `bindings`: SHA-256 map containing `20-source/blocks.jsonl`, `30-normalized/blocks.jsonl`, `40-modernized/book-understanding.md`, `50-edited/editorial-plan.md`, `50-edited/sample/reader-sample.md`, plus sample image paths when used.
- `sample_selection`: `{reason, block_ids, covered_difficulties, deferred_difficulties, figures_applicable, figure_reason}`. Lists reflect actual source difficulties, not quotas. IDs exist in source. Describe handling of unrepresented risks. Figure applicability follows the book; do not declare false to skip testing.
- `blocking_questions`: central unresolved questions with source references; empty before bulk production. Preserve minor uncertainties in the unified ledger.
- `sample_review`: the reading-session object below, with `status: passed` only after actual assessment.

Use `python scripts/validate_production_plan.py WORKSPACE` before bulk production and publication. It verifies records, source IDs, dependency hashes and task coverage, not comprehension. No script exit code grants semantic acceptance.

## Actual reading sessions

The session object contains `status`, `producer_execution_id`, `reviewer_execution_id`, `reviewer_kind` (`model` or `human`), `manuscript_file/manuscript_sha256` identifying the actual sample/final manuscript reviewed, and four file/hash pairs: `tasks_file/tasks_sha256`, `responses_file/responses_sha256`, `assessments_file/assessments_sha256`, `provenance_file/provenance_sha256`. Final session execution IDs must match the producer/reviewer record run IDs. A different or changed manuscript invalidates the session.

Retain three UTF-8 JSON arrays:

- Tasks: `{id, question, kind}`. Kinds are `main_point`, `application`, `distinction`, `figure`, `other`. Main point, application and distinction are required, plus figure if applicable. Set tasks before reading; exclude expected answers. A required kind can be omitted only with a source-grounded reason in session `task_exemptions: {kind: reason}`. Do not invent a concept contrast absent from the book.
- Responses: `{task_id, answer}`. Retain actual answers including mistakes. Never rewrite a response into the desired result.
- Assessments: `{task_id, status, evidence}` with `passed`, `needs_revision` or `blocked`, comparing the answer to specific source/final prose. A failed answer needs revised material and a new retained reading session; keep the failed session.
- Provenance: local transcript/export or contemporaneous notes containing actual question/answer text and actual execution references. Different generated UUIDs/roles or duplicate summaries are not independent execution. The validator can verify contents and binding, not who truly performed a review. The controller must inspect provenance and disclose model/human review type.

Use a separate model invocation/subagent for sample and full reading when available; this contract explicitly authorizes this scoped delegation. Do not provide expected conclusions. If independent execution is unavailable, disclose it and withhold independent-reader acceptance. Human participation is optional and never fabricated. Routine sample acceptance does not require user approval.

Final reader acceptance schema `1.2` adds `reading_session` with this shape. Each meaningful section review and core glossary sample names `task_ids`. Full-manuscript tasks specify inclusive `start_line/end_line` and, for concept tasks, `terms`. A unit's `plain_answer` is an actual verbatim response to a linked task covering that unit. A core glossary sample includes `answer_quote` actually present in the linked response to a task naming that term. Do not reuse a generic whole-book task to stand for chapter understanding; connecting adjacent units is legitimate only when that relationship is tested. Answers must explain the content, not repeat headings or generic claims. Layout-only units can state their actual navigation function; coverage remains complete.

## Upgrade and honest claims

Preserve existing books/PDFs/reviews/issue identities. Do not alter installed releases during a Skill update. Resuming ordinary-reader production requires fresh understanding/design and actual sample evidence; version edits cannot upgrade an old pass. Legacy publication lacking these prerequisites is blocked with a migration explanation, not automatically repaired or deleted.

Use failed template introductions, circular glossary entries and batch-generated review records as negative cases. Also evaluate fresh source material not used to design the rules. Distinguish synthetic contract tests, actual sample results and whole-book readability. Preserve valid unchanged technical evidence; avoid repeated full checks without changed inputs. Two no-progress cycles on a central blocker return to its responsible stage; never call budget exhaustion acceptance.
