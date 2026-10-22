---
name: chaoyun-classical-modernizer
description: Convert normalized classical Chinese, traditional prose, modern Japanese, classical Japanese, or kanbun into traceable modern Chinese while preserving meaning and uncertainty. Use when historical text needs translation or explanation for contemporary readers; do not perform OCR, source reconstruction, or unmarked creative rewriting.
---

# 超云古文今译

Produce accurate modern Chinese at block level, with the source and normalization layers intact.

## Route before translating

Classify each block or segment as `zh-Hans`, `zh-Hant`, `lzh`, `ja`, `ja-bungo`, `kanbun`, `mixed`, or `und`. Split mixed blocks only where the boundary is evidenced. Read [references/language-routes.md](references/language-routes.md) for route-specific rules.

## Workflow

1. Read normalized and source records together. Preserve `block_id`, quotations, names, dates, quantities, and technical terms.
2. Create a faithful modern rendering before any reader-friendly edit. Resolve ellipsis only when the referent is supported by nearby source context.
3. Record `operation`, language route, confidence, terminology decisions, and unresolved alternatives in `40-modernized/blocks.jsonl`.
4. Maintain `40-modernized/terminology.json` for stable names and domain terms.
5. Independently compare high-risk blocks: divination formulas, prescriptions, legal/religious claims, measurements, chronology, damaged text, and low-confidence language detection.
6. Generate `40-modernized/modernized.md` only from accepted records.

## Boundaries

- Do not add background facts, explanations, or conclusions inside the translation. Those belong to labeled editor notes.
- Do not turn ambiguity into certainty. Preserve or explain alternatives.
- Do not interpret Japanese solely from shared Chinese characters.
- Do not modernize a source block whose transcription is materially unresolved; carry it forward as uncertain.

## Gate

Every source content block must be translated, retained, marked noncontent, or excluded with a reason. No silent omission is allowed. High-risk translations must have evidence of an independent comparison or appear in the uncertainty ledger.
