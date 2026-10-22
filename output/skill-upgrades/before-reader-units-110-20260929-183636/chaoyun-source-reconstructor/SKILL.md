---
name: chaoyun-source-reconstructor
description: Reconstruct faithful, traceable source Markdown and page/block data from complex book PDFs while preserving layout evidence, images, notes, and uncertainty. Use after PDF diagnosis when OCR or layout recovery is needed; do not translate, simplify, paraphrase, or silently repair unreadable source text.
---

# 超云原貌重建

Create the evidentiary source edition that all later stages depend on.

## Workflow

1. Read the diagnosis profile and honor its page-level routes. If none exists, diagnose first.
2. Render or preserve page images at sufficient resolution for later verification. Keep source page numbering separate from logical numbering.
3. Extract or OCR regions with coordinates, block type, language hint, and reading-order index. Use multiple passes only where diagnosis shows a concrete benefit.
4. Reconstruct headings, body, notes, captions, tables, figures, and cross-page paragraphs according to visible evidence.
5. Assign stable `page_id` and `block_id` values. Every block records `component_id`, `structural_role`, `bbox`, and page-local `reading_order`. Write `20-source/blocks.jsonl` before producing `20-source/source.md`.
6. Compare representative and high-risk pages against source images. Put uncertain glyphs, reading order, and damaged regions into the audit ledger.

Follow [references/reconstruction-policy.md](references/reconstruction-policy.md).

## Hard boundaries

- Preserve original characters, wording, claims, mistakes, and historical forms at this stage.
- Do not use semantic plausibility as proof of an unreadable glyph.
- Do not collapse marginalia or commentary into the main text without explicit structural evidence.
- Do not represent an annotated or multi-register page as one catch-all `body` block. Separate visible main text, commentary, headings, running matter and other regions before modernization.
- Preserve figures and complex tables as images when a structured transcription cannot be verified.
- Remove repeated headers or page numbers only after demonstrating the repetition pattern.

## Gate

Pass only when all included pages and blocks are accounted for, reading order is supported, assets resolve, and uncertain material is linked to page evidence. Every included physical page must use its real non-sentinel page ID; repeated placeholders such as `p000` are a hard failure. Join cross-page sentences before modernization or preserve an explicit continuation link; do not translate isolated line fragments as complete prose. Structural validity alone is not OCR accuracy.
