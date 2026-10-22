---
name: chaoyun-text-normalizer
description: Normalize faithful historical text for modern reading through script conversion, variant-character handling, punctuation, segmentation, and terminology consistency with a complete change ledger. Use after source reconstruction; do not translate classical Chinese or Japanese, paraphrase meaning, or overwrite the faithful source layer.
---

# 超云古字通

Make the source legible at the character and sentence-boundary level while keeping meaning unchanged.

## Workflow

1. Read `20-source/blocks.jsonl`; preserve every `block_id` and `source_text`.
2. Select a declared target script, normally simplified Chinese for the modern reading edition. Preserve proper names and technical forms according to a project terminology file.
3. Apply script conversion, verified variant mapping, punctuation, whitespace normalization, and conservative segmentation as distinct operations.
4. Write `30-normalized/blocks.jsonl`, `30-normalized/normalized.md`, and one `30-normalized/changes.jsonl` record per material change.
5. Review names, dates, quantities, citations, formulas, titles, and rare domain terms more strictly than ordinary prose.

Read [references/normalization-policy.md](references/normalization-policy.md) before handling variants, Japanese forms, or uncertain punctuation.

## Boundaries

- Traditional-to-simplified conversion is orthographic normalization, not translation.
- Classical Chinese-to-modern Chinese belongs to `$chaoyun-classical-modernizer`.
- Japanese kanji must not be converted through a Chinese dictionary before language routing.
- Do not silently replace a source error with the expected phrase. Record an editorial note or uncertainty instead.
- Preserve an unambiguous link from normalized text to the exact source string and operation list.

## Gate

Pass only when block identity and coverage match the source stage, every material change is logged, and no semantic paraphrase has entered normalized text.
