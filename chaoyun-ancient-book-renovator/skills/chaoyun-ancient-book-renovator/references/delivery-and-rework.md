# Delivery and rework contract — workflow 1.6

## Define a book, not a collection of artifacts

Workflow 1.8 ordinary-reader production follows [reader-production.md](reader-production.md) before full translation/editing and requires a final-reader cut after the information-rich process edition. Preserve all workflow 1.6 uncertainty closure, chapter-trial and final recheck requirements. One representative sample can support both reader-method and uncertainty trials, with separate evidence for their distinct decisions. Plan pending outcomes during design; do not retroactively manufacture a sample after whole-book acceptance.

Set `book.json.delivery_mode` explicitly to `ordinary_reader`, `source_comparison`, or `evidence_archive`. Display titles, edition labels and reader names never select or disable gates. Missing mode is an error, not an exemption. Review legacy projects before assigning a mode.

An ordinary-reader edition has three independent acceptance gates:

1. **Integrity:** actual source PDF identity/page count, complete page/block accounting, meaningful stage text, complete figures and references, consistent final files.
2. **Fidelity:** no unsupported additions, missing conditions/negations, changed quantities, term drift or disguised uncertainty. Audit the source, accepted translation and final reading passage together.
3. **Reader comprehension:** a target reader can state the chapter's point, distinguish important concepts, follow diagrams, and find promised answers without internal production reports.

None of these gates compensates for another. A polished PDF does not prove fidelity; zero registered doubts does not prove correctness. Synthetic contract tests are not evidence of real-reader comprehension.

## Book-specific reader outcomes

Draft `50-edited/delivery-contract.json` before reader editing, refine it against the reconstructed source, and freeze its accepted form before publication:

```json
{
  "target_reader": "Interested beginner in the actual subject of this book",
  "reading_goal": "The central understanding this edition offers",
  "scope": "What this surviving edition actually covers",
  "limitations": "What cannot be recovered or should not be promised",
  "outcomes": [
    {
      "id": "O001",
      "question": "A substantive question a reader brings to this book",
      "answer": "A plain answer grounded in the book, not promotional copy",
      "section_heading": "An exact unique heading in the final manuscript",
      "quote": "An exact passage within that section supporting this answer",
      "status": "pending",
      "review_evidence": null
    }
  ]
}
```

Use as many outcomes as the work needs, not a fixed quota. Check introduction promises against these outcomes and the final chapters. Only a real comprehension review may set `status: passed` and record substantive evidence. Do not increase book length by adding generic background, repetitive summaries or decorative examples.

## Fidelity evidence and source-to-reader mapping

After freezing the full manuscript, run `python scripts/prepare_delivery_review.py <workspace>`. It writes `90-audit/fidelity-review.json` with current file hashes and **pending** block/figure records, never success. Preserve older reports in review history before regenerating.

Every source block appears once. For content, record exact `source_quote`, `modern_quote`, `reader_quote`, `status`, `evidence`, and explanatory `checks` for `omissions`, `additions`, `negation`, `conditions`, `quantities`, `terms`. Read the entire affected passage, not just the chosen quote. Explain non-applicable checks rather than writing an empty field. Noncontent, excluded and unreadable blocks require `disposition_reason`; uncertainty remains in the unified ledger and reader-facing disclosure where needed.

Workflow 1.9 also requires `50-edited/source-reader-map.jsonl`. Each source block has exactly one mapping row. A source-bearing row names its source component, exact final heading and exact final-reader quote; the quote must occur inside that declared section. A displaced row names its preserved supplement or evidence destination. HTML comments, IDs collected at the end of the manuscript, and generic first-character quotes do not establish semantic mapping.

Content figures/tables/maps/diagrams additionally have `block_id`, `section_heading`, `guidance_quote`, `status`, `evidence`. Compare the actual original image, final figure, labels and explanation; counts alone are insufficient. Source figure block types must be correctly classified. The script verifies inventory/locations; it cannot judge figure meaning.

The audit retains distinct `producer` and `reviewer` identities and binds source, normalized, modernized, edited records, manuscript and delivery contract with `input_hashes`. Any change to those inputs invalidates this acceptance. Never merely refresh hashes: conduct the affected review and preserve the superseded report.

## Freeze, render, review, publish

Assemble **all textual content**—cover/credits wording, introduction, original preface, body, reader notes, glossary and appendices—before full-reader acceptance. Freeze approved text before rendering. Cover artwork may be designed separately but its words and attribution must agree with the accepted manuscript.

For ordinary-reader delivery, preserve the reviewed information-rich manuscript in `50-edited/review-history/<cycle_id>/` before removing process/guide material from the release path. The final cut may delete only from the reading path: source-bearing text remains in the final manuscript, while displaced editorial material remains recoverable in the process snapshot or another named preservation artifact. The final cut invalidates earlier reader acceptance until the exact compact manuscript receives complete section review, reading-session evidence and the six finalization checks defined in [reader-production.md](reader-production.md).

Keep the candidate PDF under `60-publication/candidates/`. Prepare page proofs and run both gates against that candidate. Only the guarded installer may replace the official PDF after all gates pass. It backs up any previous official PDF by hash and uses atomic replacement. Do not give a candidate the official path just to enable its audit. Use an isolated edition workspace for a rebuild so that the previous delivered PDF/Markdown/assets package remains intact.

## Rework impact

| Change | Required return and recheck |
|---|---|
| Source glyph, reading order, missing content | Source reconstruction and adjudication; affected normalization/translation; connected terms, figures and chapters; new fidelity, reader and PDF acceptance |
| Translation or core-term meaning | Modernization/adjudication; all uses of the term and connected claims; affected chapter comprehension; new whole-book regression and publication proof |
| Introduction, explanations, regrouping | Reader editing; outcome promises and source/editor boundary; new fidelity and reader acceptance |
| Only typography/pagination | Keep unchanged content review; regenerate PDF binding, full-page proof and navigation mapping |
| Source file, manuscript, asset or contract changed after approval | Treat dependent evidence as stale; preserve history and review the impacted scope before release |

The complete final manuscript still gets a regression read; do not imply unchanged sections were retranslated. Hash mismatch is a deterministic stop, not a semantic diagnosis. `run-state.json: passed` alone cannot override it.

## Real-book acceptance benchmark

Before claiming production readiness, run a real, rights-permitted chapter containing the work's actual difficult features, followed by a whole-book review. Preserve the source images, accepted meanings, reader obstacles, before/after passages and final rendered proof. Cover negation/conditions, similar terms, annotation order, diagrams and cross-chapter continuity where present. If external readers participate, record actual feedback without inventing respondents. Fix systematic errors and expand inspection before a paid full-book run.

No real-book benchmark is automatically passed by installing this workflow. Workflow 1.6 requires `90-audit/pilot-review.json` and the uncertainty Skill's `--pilot` gate before scale-up; publication checks it again. Follow that Skill's `references/closure-and-trial.md` for exact fields and independent-review evidence. Report separately: contract tests, actual trial, source-fidelity review, reader review, and publication proof.
