# Reader value contract

Use this contract for an ordinary-reader edition. Its purpose is not to prove that front matter exists, but to prove that a non-specialist can understand why the book matters and continue reading without being abandoned at specialist vocabulary.

## Editorial stance: 增、删、改、整

- **增**：add only the context, definitions, examples, transitions, reading routes, and cautions that remove a real reader obstacle. Label editor-created material and attach evidence.
- **删**：remove repetition, pipeline language, and reader-hostile clutter from the continuous reading path. Never erase source content; move retained catalogues or technical material to a labeled reference section with provenance.
- **改**：rewrite archaic syntax, vague references, overlong sentences, and unexplained jumps into natural modern Chinese without increasing certainty or changing the accepted meaning.
- **整**：organize chapters, concepts, figures, cross-references, and terminology around the reader's questions while preserving a separately recoverable source order.

Every operation answers a documented reader problem. Cosmetic rewriting alone is not a reader-value pass.

## Required structured file

Create `50-edited/reader-aids.json`. The summary counts in `editorial-report.json` are derived from this file, never typed independently.

```json
{
  "schema_version": "1.0",
  "target_reader": "Interested non-specialist",
  "introduction": {
    "markdown_heading": "本书介绍",
    "sections": {
      "what_this_book_is": "Plain description of the surviving work.",
      "who_should_read": "Named reader groups and prerequisites.",
      "reader_value": "What the reader will understand after reading.",
      "contents_and_structure": "Major parts and how they relate.",
      "distinctive_features": "What is distinctive in this book, not generic praise.",
      "historical_and_textual_context": "Attribution, compilation, edition, and limits of available evidence.",
      "how_to_read": "Routes for different reader goals.",
      "limitations_and_cautions": "Difficulties, unresolved evidence, and status of traditional claims.",
      "edition_method": "What this modern edition changed, retained, or moved."
    },
    "evidence": [
      {"claim": "A source-derived claim", "block_ids": ["P000001-B001"], "source_pages": [1], "editorial_sources": []}
    ]
  },
  "glossary": {
    "markdown_heading": "本书术语表",
    "entries": [
      {
        "term": "示例术语",
        "tier": "core",
        "aliases": [],
        "plain_definition": "A first explanation using no unexplained specialist term.",
        "contextual_definition": "How the present book uses the term.",
        "first_occurrence": {"page_id": "P000001", "block_id": "P000001-B001", "source_page": 1, "quote": "原文片段"},
        "usage_example": "A source-grounded or clearly labeled editorial example.",
        "related_terms": ["相关词"],
        "common_confusions": "What a beginner is likely to misunderstand.",
        "confidence": "confirmed"
      }
    ],
    "excluded_inventory_terms": [
      {"term": "非正文标记", "reason": "Stamp or pipeline label, not a reader term."}
    ]
  }
}
```

## Introduction acceptance

Write the introduction as coherent prose from whole-book understanding and the editorial plan before populating the nine coverage keys. All keys point to actual final passages within the introduction; a passage may answer several questions. They do not prescribe nine paragraphs or nine sentences. Render the referenced prose verbatim and update JSON/manuscript together. The validator checks placement, not understanding. Generic praise, headings repeated as a list, or a production disclaimer do not explain a book.

Source-derived claims use block or physical-page evidence. External historical background, when included, names its editorial source. When evidence is unavailable, say so in `limitations_and_cautions`; do not fill the gap with a confident generalization.

The introduction must let the target reader answer: What is this book? What does it contain? How are its parts related? Why might I read it? What background do I need? Where should I start? What should I not treat as established modern fact? What did this edition change?

## Glossary acceptance

- Build an inventory from the actual book. Every term in `40-modernized/terminology.json` is either an entry or an explicitly excluded item with a reason.
- The inventory file is mandatory. Core/supporting classification and exclusions need semantic review; never demote a core concept to avoid explaining it.
- Render each term under its own unique subheading within the glossary. Render the exact plain/contextual definitions and, for core terms, example, confusion guidance and related concepts in that entry. A mention elsewhere in the book cannot satisfy this check.
- Every entry has an exact source occurrence linked to an existing block. A summary count is not evidence.
- `plain_definition` explains the term without merely repeating it or replacing it with another unexplained specialist term.
- `contextual_definition` explains how this book uses the term; a generic dictionary definition is insufficient.
- An example walks through a real source passage or explicitly labeled editorial illustration and explains what the concept does there. A quotation plus “按本书语境理解” is not an example. Confusion guidance identifies a particular misunderstanding and resolves it. Related terms require an actual conceptual relationship; never mass-fill the same list.
- Start from concept dependencies in the understanding brief and actual reader obstacles. Explain prerequisites before using them in definitions. Do not demote essential concepts to supporting terms to avoid explaining them. Retain raw source wording in evidence; reader examples need comprehensible explanations rather than unexamined OCR fragments.
- Core terms additionally require a usage example, related terms, and a likely confusion. Supporting terms may omit these only when the plain and contextual definitions are independently sufficient. Opaque terms use `tier: opaque`, state the uncertainty, and must not receive an invented definition.
- A single-character match, contents-page mention, or substring collision is not automatically the first substantive occurrence. Verify it against the linked block.
- In the rendered book, explain a term at first reader-facing use as well as in the end glossary.

After this file validates, `$chaoyun-reader-experience-reviser` performs the independent whole-book reading pass, glossary sampling, revision loop, and final reader acceptance. Production evidence and acceptance evidence remain separate.

Passing these mechanical checks proves text placement and source references, not clarity or accuracy. In the final reader pass, ask a reader to explain each core concept in their own words and distinguish it from a neighboring concept. Record the answer and the remaining misunderstanding, not just a boolean. Do not invent a source example where only an explicitly labeled editorial illustration is available.
