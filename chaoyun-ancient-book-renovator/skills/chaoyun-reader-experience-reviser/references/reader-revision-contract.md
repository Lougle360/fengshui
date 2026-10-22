# Whole-book reader revision contract

Workflow 1.9 uses reader review/acceptance schema **1.2** and adds auditable repeated full-manuscript passes without changing the schema number. Preserve legacy reports and perform fresh review; do not manufacture historical snapshots or execution records. The examples below describe the base fields; actual reading-session and finalization fields are also required as specified in [reader-production](../../chaoyun-ancient-book-renovator/references/reader-production.md). Revision-event schema remains 1.1 for append-only compatibility.

Before review, create `50-edited/review-policy.json` with `minimum_full_passes >= 3` and `required_stable_passes >= 2`. Three is a floor, not an automatic finish line. Each real pass writes one JSON record plus its retained transcript under `50-edited/review-history/full-passes/`. The record binds `manuscript_sha256`, a distinct `reviewer_run_id`, `status`, `findings`, `sections_covered`, `new_blocking_issues`, `open_blocking_issues`, `transcript`, and `transcript_sha256`. Every chapter and front/back-matter unit is actually read in every pass. The final required stable passes must both have no new or open blocking issue. Any edit after a pass invalidates its manuscript hash and restarts the stability count.

## Reader review

Create `50-edited/reader-review.json` before editing:

```json
{
  "schema_version": "1.2",
  "cycle_id": "RC0003",
  "mode": "manuscript",
  "input_sha256": "...",
  "target_reader": "现代普通读者",
  "reviewer": "reader-audit-model-or-person",
  "dimensions": {
    "introduction_promise": {"verdict": "needs_revision", "findings": [{"revision_id": "RR000001", "problem": "The introduction promises a method not explained later."}]},
    "prerequisites": {"verdict": "passed", "findings": []},
    "navigation": {"verdict": "passed", "findings": []},
    "continuity": {"verdict": "passed", "findings": []},
    "terminology": {"verdict": "passed", "findings": []},
    "examples_and_figures": {"verdict": "passed", "findings": []},
    "redundancy_and_pacing": {"verdict": "passed", "findings": []},
    "source_editor_trust": {"verdict": "passed", "findings": []},
    "closure_and_lookup": {"verdict": "passed", "findings": []}
  },
  "glossary_samples": [
    {"term": "示例术语", "plain_enough": true, "context_specific": true, "example_helpful": true, "issue": null}
  ],
  "blocking_issues": ["RR000001"]
}
```

Every dimension is reviewed even when no defect is found. Findings use `revision_id` and `problem` to identify an obstacle and its location; every ID resolves to a revision event. Review every core glossary term, plus enough other terms to reach at least the lesser of ten or all entries. Final glossary results belong in the acceptance report, bound to the final manuscript, not just the initial review. Each sample retains the three booleans shown above, plus an exact final-manuscript `quote` and substantive `evidence` explaining the comprehension result.

## Revision ledger

`50-edited/reader-revision-ledger.jsonl` is append-only across unlimited cycles:

```json
{
  "schema_version": "1.1",
  "event_id": "RRE000002",
  "revision_id": "RR000001",
  "cycle_id": "RC0003",
  "operation": "add",
  "reader_problem": "The core term is used before the reader can understand it.",
  "block_ids": ["P000080-B003"],
  "section": "卷三·点穴歌",
  "before": "...",
  "after": "...",
  "preservation": null,
  "evidence": ["P000080-B003"],
  "semantic_risk": "low",
  "uncertainty_candidate_id": null,
  "status": "applied",
  "rationale": "Adds a first-use explanation without changing the translated claim."
}
```

Rules:

- `event_id` is unique. The same `revision_id` may appear in later appended events as its status moves from proposed to applied, rejected, or returned.
- `operation` is `add`, `delete_from_reading_path`, `rewrite`, or `reorganize`.
- `status` is `proposed`, `applied`, `rejected`, or `returned_to_responsible_stage`.
- Applied `add`, `rewrite`, and `reorganize` records contain distinct before/after state. Applied deletion records name where the source material remains available in `preservation`.
- Every record names the reader problem, evidence, and affected blocks or section.
- A medium/high semantic-risk change has an `uncertainty_candidate_id` and is adjudicated before publication.

## Acceptance report

After a fresh regression read, create `50-edited/reader-acceptance-report.json`:

```json
{
  "schema_version": "1.2",
  "cycle_id": "RC0003",
  "mode": "manuscript",
  "producer": "revision-producer",
  "reviewer": "different-regression-reviewer",
  "status": "passed",
  "output_sha256": "...",
  "regression_review": "passed",
  "blocking_issues": [],
  "counts": {"add": 1, "delete_from_reading_path": 0, "rewrite": 0, "reorganize": 0}
}
```

The output hash matches `50-edited/modern-reading.md`. Counts are derived from the latest event for each revision in the accepted cycle. Unresolved status is computed from the latest event for each revision across **all cycles**. The producer and regression reviewer differ. A new later cycle supersedes acceptance; publication uses the latest cycle represented in the ledger and acceptance report.

For workflow 1.8, acceptance also contains `final_reader_cut` as defined by the controller's `references/reader-production.md`. Its immutable process snapshot preserves the richer guide/process manuscript; its output hash binds the compact final manuscript. Every required check has a substantive evidence sentence. The validator confirms paths, hashes and recorded judgments, but cannot decide that prose is genuinely useful.

## Content-bound evidence fields (retained and extended in 1.2)

All paths below are workspace-relative, resolve inside the workspace, and point to real files. Preserve snapshots and archived review/acceptance files under `50-edited/review-history/<cycle_id>/`; never overwrite old cycle evidence. Hashes are SHA-256 of file bytes. The validator uses UTF-8 text with universal newline decoding for edit offsets.

### Exact edit chain

- Initial review: `input_snapshot`, `input_sha256` point to the actual pre-edit Markdown.
- Each applied event: `input_snapshot`, `input_sha256`, `output_snapshot`, `output_sha256`, integer `start_offset`, `end_offset`, and literal-string `before` / `after`.
- An edit must equal `input[:start_offset] + after + input[end_offset:]`, and `input[start_offset:end_offset] == before`. Use empty string, not null, for an insertion/deletion side. A reorganization can replace a larger contiguous passage or use several ordered events.
- Applied events in the accepted cycle form one continuous chain from the review input to the current manuscript. Unrecorded changes fail; a zero-edit cycle requires identical input and output.
- A deletion also has a `preservation` path containing the removed literal text; a path-shaped string is insufficient.
- Every terminal issue (`applied` or `rejected`) has `resolution_review: {reviewer, status: "passed", evidence}`. Rejection also requires a substantive `rationale`. Do not use rejection to hide an unresolved reader obstacle.
- Medium/high semantic-risk applied revisions require exactly one active `resolved_confirmed` adjudication with nonempty evidence for their candidate. If a meaning change cannot be confirmed, revert it or return it to the responsible stage; do not publish the speculative edit.

### Full-manuscript regression

The acceptance adds `dimension_checks`, with exactly the same nine dimension keys; each value is `{status: "passed", evidence: "specific regression observation"}`. It also adds `glossary_samples` as described above and `section_reviews`.

Partition the final Markdown into meaningful contiguous reading units, including front/back matter. Units must cover all lines in order without gaps or overlaps. Adjacent ATX sections may be grouped into one argument or chapter; `reader_evidence.sections(text)` is an optional inventory helper, not the required reading-unit boundary. Each unit keeps its full text hash. Do not group the whole book merely to avoid chapter-specific reasoning. Each section review contains:

```json
{
  "start_line": 1,
  "end_line": 12,
  "text_sha256": "sha256 of the section lines joined with LF, without trailing LF",
  "quote": "an exact passage in this section",
  "reader_question": "What does the reader need to understand here?",
  "plain_answer": "A plain-language answer actually supported by this section.",
  "prerequisites": "Necessary knowledge and where it is explained, or why none is needed.",
  "comprehension_evidence": "What was understandable, tested by restatement, distinction or figure explanation.",
  "task_ids": ["actual-reading-task-id"],
  "block_ids": [],
  "status": "passed",
  "remaining_obstacles": []
}
```

All source block IDs must be accounted for across these reviews. A source block moved to a reference section is reviewed there; noncontent/excluded blocks are accounted for in the relevant editorial-method section, with their disposition explained in evidence. This inventory correspondence does not itself prove fidelity: compare source text and reader prose separately.

Keep introduction promises tied to actual chapters; test first-use explanations and distinctions between similar terms; explain each content figure's reading sequence. Resolve or record obstacles before marking a section passed. Do not infer comprehension from length, vocabulary count or a model's numeric score.

### Separate execution records

Acceptance also requires `reading_session` from the shared reader-production contract, bound to the reviewed manuscript, actual tasks, answers, assessments and retained provenance. Every reading unit and core glossary sample links its `task_ids`. Tasks name inclusive `start_line/end_line`; unit `plain_answer` is the actual response to a linked task covering that unit. Concept tasks name `terms`; core glossary samples preserve `answer_quote` from the actual response. Questions for every core term must elicit meaning/application or distinction; copying the glossary sentence is insufficient. A task can connect neighboring units when their relationship is the question, but a generic task cannot support every chapter. Preserve incorrect responses; re-test revised material and retain earlier sessions. The separate reviewer may be a model; disclose that fact. A script may derive inventory/hashes but must never author answers or verdicts.

Acceptance includes `producer_record`, `producer_record_sha256`, `reviewer_record`, `reviewer_record_sha256`. Each file is a JSON object with `actor`, a distinct `run_id`, and the accepted `output_sha256`. Preserve real review transcripts/notes or model-call references alongside these records. Distinct strings/hashes prove artifact separation, not human independence: do not fabricate identities, runs or trial readers.

## Upgrade and stopping rules

Keep legacy ledgers unchanged in an archive and re-audit current pending work. Record migration decisions and stable issue IDs; unresolved issues cannot disappear. Old acceptance and downstream PDF proof are invalid for changed content. Never upgrade by changing only `schema_version`.

After two consecutive no-progress cycles on the same blockers, report the missing evidence or unresolved decision and stop without declaring success. Respect the authorized cost budget. Use a real representative chapter before a paid full-book re-run. A synthetic self-test verifies contracts only; full-book reader quality needs actual whole-book review and, where available, target-reader feedback.
