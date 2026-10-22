---
name: chaoyun-reading-editor
description: Edit an accepted modern Chinese rendering into a coherent contemporary reading edition with clear hierarchy, notes, terminology, figures, and reader aids. Use after faithful modernization; do not change source meaning, hide uncertainty, or mix newly authored explanations into translated source text.
---

# 超云今读编辑

Transform an accurate modern rendering into a book that contemporary readers can follow.

The reader, not the pipeline, is the organizing point of view. Every editorial action follows `增、删、改、整`: add what removes a real comprehension barrier, remove reader-hostile clutter from the continuous path without erasing source evidence, rewrite for natural modern understanding without changing meaning, and reorganize navigation while preserving recoverable source order.

## Establish the edition

For ordinary-reader work, use [design/sample/full-edition modes](../chaoyun-ancient-book-renovator/references/reader-production.md). Consume whole-book understanding before writing `50-edited/editorial-plan.md`: introduction narrative, chapter connections, prerequisites, first explanations, actual examples, figures and lookup material. Draft pending reader outcomes. Design precedes full translation; consult the translator on meaning.

Make a real sample with introduction, connected prose, representative terms and a figure where applicable. Hand it to reader-experience-reviser sample mode before scaling. Use its accepted quality and explanation methods, not repeated sentence templates. Full-edition mode uses accepted translations and this plan.

Scripts may render authored prose, preserve source mapping and derive counts; they must not generate comprehension answers, reviewer identities or semantic success. Write a coherent introduction first, then index its coverage. Nine dimensions do not require nine short paragraphs. Glossary examples must actually explain a source passage or a labeled editorial illustration; a quote plus “understand in context” is unfinished work.

Assume AI-authored prose is the likeliest source of reader hostility. For every introduction, transition, glossary explanation, example, caption and reading instruction, identify the exact obstacle it solves and its source basis. If it only announces structure, praises the book, repeats nearby prose, exposes a data field, or replaces one unexplained term with another, rewrite it or leave it out. Preserve a richer guide/process edition when useful, but do not force that material into the final reader path.

Record target reader, reading goal, reading level, modernization depth, annotation density, and whether the output is reading-only or source-comparison. If the user asks for ordinary people to read directly, optimize for interested non-specialists: retain necessary domain terminology, explain it on first occurrence, and do not assume prior training.

## Editing work

1. Preserve every source `block_id` in `50-edited/blocks.jsonl` while allowing display-level paragraph grouping with contributing IDs. Maintain `50-edited/source-reader-map.jsonl`: exactly one row per source block, with its component, destination, reader heading and an exact reader quote or an explicit preserved non-reading destination. Hidden comments and aggregated anchors are not mapping evidence.
2. Build coherent book, volume, chapter, section, note, figure, and table hierarchy.
3. Improve sentence length, transitions, and paragraphing only within the accepted meaning.
4. Add a front-of-book reading map when the original structure is unfamiliar, and give each major chapter a concise introduction stating its question, key concepts, and reading route.
5. Create reader aids—first-use term notes, historical context, cross-references, examples, and practical observation checklists where appropriate—as explicitly labeled editorial content.
6. Keep figures and captions near the relevant passage. Maintain stable numbering and alt text, and explain what to inspect and in what order when the image is necessary to understand the text.
7. Attribute traditional causal, predictive, medical, or fortune claims as source/traditional views. Separate them from observable descriptions without deleting or endorsing them.
8. Move repetitive catalogues or case lists to clearly named reference sections only when this improves continuous reading; preserve source order and provenance.
9. Treat the book introduction as a substantive reader deliverable. Explain the surviving work, intended reader, reader value, contents and relationships, distinctive features, textual context, reading routes, limitations, and what this edition changed. A production note or generic praise is not an introduction.
10. Build a term inventory from this book, then write tiered glossary entries. Core terms require a plain definition, contextual definition, exact first source occurrence, usage example, related concepts, and common-confusion guidance. Do not publish one-line labels that send the reader back to the unexplained text.
11. Generate `50-edited/reader-aids.json`, then render `50-edited/modern-reading.md`. Derive `editorial-report.json` counts from the structured reader aids; never type success counts independently.
12. Assemble final cover/credits wording and all reader-facing sections before full-reader review. Maintain the book-specific `50-edited/delivery-contract.json` outcomes using the controller's `references/delivery-and-rework.md`. Preserve this complete information-rich draft as the process edition, then hand it to `$chaoyun-reader-experience-reviser` for the final-reader cut and full regression; do not certify it from the same production pass. A large cut requires issue-level revision rows with before/after evidence; one catch-all `rewrite` record cannot account for a book-scale deletion.

Use [references/editorial-policy.md](references/editorial-policy.md) for boundaries and labeling.
For ordinary-reader work, read and enforce [references/reader-value-contract.md](references/reader-value-contract.md), then run:

```shell
python scripts/validate_reader_value.py book-workspace
```

## Gate

Pass this production stage when the introduction and glossary have verifiable book-specific evidence, hierarchy and references are coherent, all content IDs are accounted for, and editorial additions are visibly distinct from translated source content. Whole-book reader acceptance belongs to `$chaoyun-reader-experience-reviser`; OCR corruption or missing evidence returns to reconstruction. Fluency never overrides semantic fidelity.
