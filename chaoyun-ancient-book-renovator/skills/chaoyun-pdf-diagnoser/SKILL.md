---
name: chaoyun-pdf-diagnoser
description: Diagnose book-like PDFs before conversion, classify page-level text, scan, layout, language, damage, and complexity, then produce a route map and risk report. Use when a conversion must choose reliable OCR, layout, language, and modernization paths; do not use to claim conversion quality from metadata alone.
---

# 超云文档慧检

Inspect before converting. Produce evidence for route selection, not a generic PDF summary.

## Required work

1. Record source hash, byte size, page count, encryption/corruption state, page dimensions, embedded-text coverage, image resolution, and duplicate or missing-page evidence.
   On Windows, stage non-ASCII source paths to an ASCII-only working path and verify the copied hash before invoking native PDF/OCR tools.
2. Classify every page as `digital`, `scan`, `mixed`, `image_only`, `damaged`, or `unsupported`.
3. Detect layout families: horizontal/vertical, single/multi-column, main text, double-line notes, marginalia, tables, figures, seals, formulas, handwriting, and unusual reading order.
4. Detect language/script at block or region level: `zh-Hans`, `zh-Hant`, `lzh`, `ja`, `ja-bungo`, `kanbun`, `mixed`, or `und`.
5. Build a representative verification set covering every layout/language family plus the worst pages. Test proposed routes on that set.
6. Write `10-diagnosis/profile.json` and `10-diagnosis/page-map.jsonl` using [references/diagnosis-contract.md](references/diagnosis-contract.md).

## Decisions

- Prefer a reliable embedded text layer only after checking glyph correctness and reading order against page images.
- Use layout-aware OCR for scans; use page-level hybrid routing for mixed PDFs.
- Route Japanese, kanbun, handwriting, tables, and dense annotations explicitly. Do not treat CJK character overlap as language proof.
- Preserve primarily visual pages as images when Markdown cannot faithfully represent them.
- If source information is physically absent or unreadable, classify the limitation; do not predict the lost content.

## Gate

Pass diagnosis only when every page has a route, every distinct page family has a tested sample, exclusions are counted, and risks are explicit. A successful sample validates routing only, not the entire book.
