---
name: chaoyun-quality-publisher
description: Independently audit a traceable modern reading edition and publish validated Markdown and PDF packages with source comparison, embedded fonts, resolved assets, and a quality report. Use after editing or when an existing book workspace needs final acceptance; do not certify content from file existence or structural checks alone.
---

# 超云品质出版

Treat audit and rendering as separate gates. A beautiful PDF is not evidence of accurate transcription or translation.

## Audit

1. Verify source hash, page coverage, block identity across stages, dispositions, asset references, and uncertainty-ledger coverage.
2. Compare high-risk and statistically distributed samples against source page images and accepted translations. Expand review when systematic errors appear.
3. Check names, dates, quantities, terminology, quotations, captions, tables, and Japanese/classical-language routes.
4. Confirm editor-created content is labeled and does not masquerade as source text.
5. For ordinary-reader editions, validate item-level `50-edited/reader-aids.json` against source blocks and the final publication Markdown; require `$chaoyun-reader-experience-reviser` acceptance and its revision ledger; then audit the derived `50-edited/editorial-report.json`: book nature and attribution, introduction coverage, whole-book reader review, contextual glossary coverage, figure-specific guidance, pipeline-language scan, and high-impact uncertainty count. Never accept self-reported counts in place of entries and evidence.
6. Assign grade A–D with explicit evidence and limitations.

Hard publication failures include unresolved literal HTML/XML tags in rendered text, internal pipeline messages presented to readers, OCR garbage treated as prose, repeated sentinel page IDs, broken page-to-block links, low-confidence fragments accepted as high-confidence without image evidence, or incomplete page-level visual coverage claimed as a full scan conversion. Stop and return the edition to the responsible stage instead of decorating these defects with an uncertainty box.

Use [references/publication-package.md](references/publication-package.md) for output and visual requirements.

## Publish

- Produce `60-publication/modern-reading.md` and one official reader PDF named from `book.json.release_filename`, normally `<原书名>·<版本名>.pdf`. A `modern-reading.pdf` internal alias is optional and must not be presented as a second final edition.
- Produce source-comparison Markdown/PDF under `60-publication/supplements/` when evidence supports it; do not place a second final-looking PDF beside the official reader PDF.
- Use relative asset paths in Markdown and embed suitable CJK fonts in PDF.
- Include a formal cover, copyright/credits page, supplied author/editor/producer lines, and appropriate reader-use notes. For generated covers, intentionally choose either a full-image cover with verified Chinese typography or an image background with programmatically typeset text; inspect every cover character.
- Verify clickable TOC targets, PDF bookmarks, heading levels, page breaks, figures, captions, tables, footnotes, links, selectable text, and rendered pages.
- For ordinary-reader editions, inspect every rendered page regardless of book length. Other declared modes may use full anomaly inspection and documented stratified sampling. Blank overflow pages, raw markup, orphan fragments, unexplained crops, and pages with extreme whitespace are defects, not stylistic choices.
- Keep exactly one unambiguous official release artifact in the publication root. Archive or clearly label superseded drafts. If a file lock forces a versioned working filename, restore the declared official name before delivery.
- Treat `book.json.release_filename` as canonical. `quality-report.json` must name the same file; a versioned fallback cannot pass the publication audit as the official release.
- Render under `60-publication/candidates/`, not the official path. Prepare and review candidate proofs, then install with `python scripts/install_official_pdf.py <workspace> <candidate.pdf> --expected-pages N`. The installer runs both gates against the candidate, requires grade A/B, backs up the previous official file, checks locks and uses atomic replacement. Failure leaves the previous release unchanged.
- Write `90-audit/quality-report.json` and a human-readable quality report.
- Before installation, prepare content-bound proof with `python scripts/prepare_release_proof.py <workspace> --candidate-pdf <candidate.pdf>`. This writes pending page reviews, never approvals. Inspect the actual pages, record findings and resolutions, then run `audit_publication.py <workspace> --candidate-pdf <candidate.pdf>` and the workspace validator with the same option. Never install an unaudited PDF to enable its proof review.
- Keep publication Markdown byte-identical to the accepted complete manuscript, including final front matter. Freeze credits, cover text and reader-facing additions before acceptance. Asset references must resolve to identical content from both stages. If publication changes prose, return it to reader review instead of refreshing hashes to bypass it.

Run the deterministic package audit:

```shell
python scripts/audit_publication.py book-workspace
```

## Gate

Do not report completion until required outputs are nonempty, the package audit passes against the declared official PDF, semantic gates are evidenced, source-page accounting reconciles, and unresolved items fit the declared grade. Report the single official release file and remaining limitations.
