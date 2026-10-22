# Publication package

## Required files

- `modern-reading.md`
- one official `<book-title>·<edition-label>.pdf` declared by `book.json.release_filename` or `quality-report.json.publication.pdf`
- `quality-report.json`
- `quality-report.md`
- all referenced local assets

Create `source-comparison.md` and `source-comparison.pdf` when source text is sufficiently recovered. Do not create an empty comparison edition merely to satisfy a template.

`modern-reading.pdf` may be retained as an internal canonical alias, but the package must identify exactly one reader-facing release PDF. Superseded drafts belong in an archive or carry an unmistakable draft label.

## PDF requirements

- Embedded CJK fonts cover simplified/traditional Chinese, Japanese, punctuation, and rare glyphs used by the book.
- Searchable/selectable text is preferred; page images remain available for evidence.
- TOC targets, bookmarks, headings, page numbers, running headers, figures, tables, notes, and links render correctly.
- The cover, copyright/credits page, author/editor/producer credits, and edition label agree with `book.json`.
- Chinese cover typography is checked character by character. A hybrid cover may use generated art with programmatically typeset title/credits when this gives more reliable text.
- Avoid widows/orphans, clipped glyphs, stretched images, missing characters, and blank overflow pages.
- Inspect rendered pages from each layout family, not only the first page.

## Quality report

Record source identity, tools/models and versions, physical source-page accounting, reader-PDF page count, page/block coverage, sampling method, TOC link and bookmark results, rendered-page inspection count, error findings, uncertainty counts by severity, cost, grade, limitations, and the exact official output path. Structural audit and semantic audit must be reported separately.

## Content-bound publication proof (workflow 1.5)

For ordinary-reader editions, require `90-audit/release-binding.json`. Run `scripts/prepare_release_proof.py <workspace> --candidate-pdf <workspace>/60-publication/candidates/candidate.pdf` BEFORE installation. Existing manifests are never silently overwritten: preserve them with their review history before generating new proof. This helper renders pages and creates **pending** records. It does not read the book, approve page appearance, or certify the release. The installer runs workspace and publication gates against the separate candidate before replacing the official file, and preserves the previous PDF under `90-audit/release-history/<hash>/`.

The manifest has `manuscript_sha256`, `markdown_sha256`, `pdf_sha256`, `assets` (Markdown image target to SHA-256), and ordered `page_reviews` for physical PDF pages 1 through N. The accepted and publication Markdown must be byte-identical. Stage-relative copies of assets must have identical hashes; use shared workspace assets or copy them without changing Markdown. All final cover/credit/intro text is frozen before manuscript acceptance.

Each page review contains `page`, workspace-relative `image`, `status`, `issues`, `reviewer`, and specific `evidence`. The helper saves RGB, no-alpha, 72-dpi PNGs. Inspect these at minimum, using higher-resolution supplementary images when glyphs or diagrams need it. Only after genuine visual review and correction set `status: passed`, `issues: []`, and identify the reviewer and observed evidence. The audit rerenders every page and compares proof-image pixels to the current PDF. Changing the PDF invalidates old hashes and proof images. Preserve the PyMuPDF version for reproducibility.

Set `quality-report.json.publication.rendered_pages_inspected` to the actual inspected count; it must equal the PDF page count. No missing-field or large-book exemption applies to an ordinary-reader release.

The audit compares rendered Markdown text with extracted PDF text in reading order for exact equality after layout whitespace removal and Unicode NFC normalization. Punctuation, negative signs, quantities and extra text are preserved: a subsequence match is not acceptance. The supported projection removes ATX heading markers, bullet markers, bold/code delimiters, link destinations, image markup and comments. Unsupported Markdown constructs, image-only cover words, renderer-generated text not in the manuscript, tables and complex extraction order may require a compatible searchable rendering route. The check fails closed; it does not provide an automatic override or certify every PDF format. Never remove source punctuation or body text to satisfy it. Actual semantic and visual review remain separate requirements.

For PDFs longer than five pages, the manifest also has ordered `navigation` entries for every level 1/2 Markdown heading: `heading`, one-based `target_page`, one-based `link_page`, `status: passed`, and `evidence`. The audit checks the target page title, matching bookmark, and an actual internal link to that page. The reviewer must inspect the clickable label and exact destination; a link count alone is not sufficient. Short test fixtures do not establish real-book navigation quality.

An optional `modern-reading.pdf` alias must be byte-identical to the official file. Production records, page reviews and hashes are auditable local evidence, not cryptographically authenticated proof of independent human review.

### Page numbers and running headers

Optional `page_reviews[].furniture` may describe exact excluded layout text as `{kind, text, bbox}`. `bbox` is `[x0,y0,x1,y1]` in PDF points and must lie entirely in the top/bottom 12% of the page. `page_number` text must equal the one-based physical page number; `running_header` text must equal an actual manuscript heading. Each declaration must match exactly one extracted line in that rectangle. Arbitrary body text, disclaimers, negative signs and unmatched rectangles cannot be excluded. Keep these declarations under visual review; they are not semantic overrides. Other page-label conventions currently fail closed until an explicit, tested mapping is implemented.
