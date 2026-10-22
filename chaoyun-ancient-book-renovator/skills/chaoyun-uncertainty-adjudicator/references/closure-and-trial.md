# Closure and real-book trial — workflow 1.6

## Complete lifecycle

Discover → register before editing → assign a responsible stage and impact → inspect source/context/independent evidence → decide error, false alarm, duplicate or unresolved → apply the supported correction → review dependent content → independent fidelity and reader review → close or retain → final manuscript and PDF gate.

The complete candidate ledger and decision history are permanent. Only the regenerated current-open view loses a closed item. Never repair missing source by plausible invention or change status to meet a zero-count target.

## Registration

Use candidate schema `1.3` for new findings. Preserve existing ID, origin and history for repeated findings. Required fields include existing page/block IDs, `kind`, `excerpt`, `reason`, `severity`, `origin_stage`, `review_cycle`, `checkpoint`, `created_by`, `created_at`, `owner_stage` and `input_ref`. Owners are `source`, `normalized`, `modernized`, `edited`, `reader_revised`, or `publication`.

`input_ref` is a located reference to the actual frozen material reviewed. Text: `{path, sha256, quote}`. Image: `{path, sha256, region: [x0,y0,x1,y1]}` with pixel coordinates inside the image. Paths are relative to the workspace and must resolve to nonempty files inside it. Save external evidence as attributed local material; do not substitute an unexamined URL for evidence. Schema 1.2 discovery metadata remains readable, but all active closure claims still require the new closure contract.

## Evidence required for every closure

Each active `resolved_*` decision adds `closure`:

```json
{
  "action": "confirmed_unchanged",
  "producer": "actual-processing-actor",
  "producer_run_id": "actual-production-execution",
  "evidence": [{"path": "evidence/page-note.md", "sha256": "actual file digest", "quote": "actual inspected passage"}],
  "impact_review": {
    "source": {"status": "checked", "reason": "Specific source conclusion", "artifacts": []},
    "translation": {"status": "not_applicable", "reason": "Specific explanation"},
    "terminology": {"status": "not_applicable", "reason": "Specific explanation"},
    "reader_text": {"status": "not_applicable", "reason": "Specific explanation"},
    "figures": {"status": "not_applicable", "reason": "Specific explanation"},
    "publication": {"status": "not_applicable", "reason": "Specific explanation"}
  },
  "review_record": {"path": "90-audit/reviews/actual-review.json", "sha256": "actual file digest"}
}
```

This is a field guide, not a passing fixture: replace each explanation and hash with actual evidence; every `checked` scope requires one or more located `artifacts`. Use `not_applicable` only for a defensible absence of impact, never to avoid checking terminology uses or downstream prose. If a later stage does not exist yet, state that limitation and perform its mandatory final-stage recheck later.

Actions are `corrected`, `confirmed_unchanged`, `noncontent`, `structural`, `duplicate`. They must agree with the adjudication status. Evidence files are mandatory for false alarms and nonbody material too. The validator verifies file identity and quoted passage/region, not the interpretation of that evidence.

### Actual correction

For `corrected`, `closure.change` contains `input`, `output`, `current` file references `{path, sha256}`, plus `start_offset`, `end_offset`, `before`, `after`. Input and output are retained snapshots; current is the actual stage file. UTF-8 text is decoded with universal newlines, offsets count characters. The required equality is:

`input[:start_offset] + after + input[end_offset:] == output`, with `input[start_offset:end_offset] == before`.

The current file must be byte-identical to the corrected output at acceptance. Group dependent edits into a traceable contiguous replacement or preserve separate decisions/events. After later changes, preserve the previous record and re-review the affected closure; do not silently refresh old hashes. Source corrections also retain the existing decision-level before/after fields. Translation/editorial corrections use `closure.change` without pretending to alter original source text.

### Separate closure review

The JSON `review_record` contains `reviewer`, a different `run_id` from `producer_run_id`, `adjudication_id`, `status: passed`, `fidelity_evidence`, `reader_evidence`, and `closure_sha256`. Compute the latter using `closure_evidence.closure_digest(decision)` after the actual review; it binds decision identity, candidate IDs, status, impact, location, rationale, supersession, duplicate target, correction and closure inputs. The review record's own digest then becomes `closure.review_record.sha256`. This two-step binding avoids a circular hash.

Preserve real review notes/transcripts or tool-call references. Separate names/run IDs and matching hashes are provenance checks, not proof that an independent person participated. Never generate fictional actors or successful review evidence.

### Duplicates and reopening

Prefer grouping repeated candidate IDs in one active adjudication. A separate `resolved_duplicate` requires `duplicate_of` naming an existing canonical **candidate ID**, and its own evidence-based explanation. Its canonical chain must terminate at an active closed decision. Unknown targets, self/circular links, and links to an open main issue fail validation. If the main issue reopens, update/group the dependent duplicate decisions before publication.

New decisions append with `supersedes` pointing to an earlier decision; the old record becomes inactive but retains rationale/evidence. A reopened issue reuses the original `issue_id`. Changed evidence/dependent files invalidate active closure checks. Historical corrections are not incorrectly required to match today's text; current decisions must be current.

## Real chapter trial before scaling

Choose an actual rights-permitted chapter spanning relevant difficult features, freeze its original reader draft, then run the full uncertainty process. Give the fresh reviewer raw evidence and the revised text but withhold the expected resolutions. Record actual results, residual doubts, newly introduced errors, time and cost. Fix introduced errors and high-risk residuals before declaring a successful trial. Do not invent trial doubts when none exist; record an empty candidate list with a substantive passage review.

Save `90-audit/pilot-review.json` with:

- `kind: chapter_trial`, `workflow_version: "1.6"`, `source_pdf_sha256` matching intake.
- `selection_reason`, `risk_coverage`, `limitations`, nonempty `sample_block_ids` existing in source records.
- Located `before` and `after` snapshot references, `candidate_ids` belonging to the selected sample.
- `cases`: one `{candidate_id, result: verified | residual, evidence}` per selected candidate. These are trial outcomes, not a deletion list.
- `status: passed`, `new_errors: []` only after actual repair/recheck; measured `elapsed_seconds`, `cost`, and `cost_unit`.
- `producer`, `producer_run_id`, and `review_record: {path, sha256}`.

The separate execution JSON contains `reviewer`, distinct `run_id`, `expected_answers_withheld: true`, substantive `findings`, and `pilot_sha256`: SHA-256 of `json.dumps(report_without_review_record, ensure_ascii=False, sort_keys=True).encode('utf-8')`. Retain the genuine review input/output alongside it. Run `project_open_items.py <workspace> --pilot` before scaling; this is read-only. Full publication requires this trial evidence again. Changing the workflow or source requires a new trial; passing a trial does not accept the rest of the book.

## Final-book recheck

Save `90-audit/uncertainty-release-review.json` after manuscript freeze. `input_hashes` binds `90-audit/uncertainty-candidates.jsonl`, `90-audit/uncertainty-adjudication.jsonl`, and `50-edited/modern-reading.md`.

`items` covers every active adjudication exactly once. Each contains `adjudication_id`, `evidence`, `reader_affected` and `result`. Closed decisions use `verified`; open decisions use `disclosed_unresolved` and an exact final-manuscript `quote` disclosing the uncertainty. Reader-affecting closed decisions also require a final-manuscript quote. Unaffected false alarms/noncontent may use `reader_affected: false` plus `no_reader_change_reason` rather than polluting the book with internal audit chatter.

Include `producer`, `producer_run_id`, `reviewer` and a `{path, sha256}` review record. That separate JSON contains matching `reviewer`, a distinct `run_id`, `status: passed`, and `final_review_sha256` computed over the report without `review_record` using the same sorted-JSON encoding as the pilot. Updating the ledger or manuscript invalidates this final check. Final PDF fidelity/proof gates then verify the publication artifact.

Run projection generation and then `project_open_items.py <workspace> --check --publication`. Grade A requires no active material uncertainties. Grade B retains bounded low/medium issues honestly disclosed; any high-impact open issue blocks A/B. Evidence failure blocks publication even if the raw open count is zero.

## Migration and claims

Never delete complete ledgers or fabricate old snapshots. Legacy migration retains a backup, reopens old closure claims for fresh review, and reports them as needing review. Existing books are not re-adjudicated by upgrading the Skill.

Synthetic tests demonstrate that invalid states are rejected; they do not constitute a successful real-book trial, prove translation accuracy, or guarantee that all potential doubts have been discovered. Keep those claims separate in delivery reports.
