# Ordinary-reader modern edition

This edition is a newly edited reading experience grounded in the source, not a raw transcript with simplified characters.

It is also not the production dossier. Preserve the guide/process manuscript separately, but do not expose audit fields, model reasoning, validator language, repetitive teaching scaffolds, or other material that makes the reader serve the pipeline. The official release is the compact final-reader manuscript accepted under workflow 1.8.

## Required reader experience

Before full production, follow [reader-production.md](reader-production.md): whole-book understanding, unified editorial design and an actual representative sample trial. Introduction, glossary and figure explanations share the same concept dependencies. The sample establishes explanation methods; final whole-book review verifies their application. Do not interpret the requirements below as a prose template or fixed paragraph count.

- State in one plain sentence what the book is, who it is for, and how it should be used. The longer introduction must distinguish title attribution, demonstrated authorship, later compilation, and surviving-edition scope whenever they differ.
- Place a reading map or “how to read this book” section before the main text when the original structure is difficult for modern readers.
- Reconstruct an “original-book contents” view from printed contents pages and verified physical-page evidence. Keep it distinct from a reader-oriented route or editor-created regrouping.
- Give each major chapter a short introduction that explains its question, key terms, and reading route.
- Explain specialist terms at first occurrence and maintain a complete glossary at the end. Each glossary entry records its first source occurrence and contextual meaning; unresolved names or opaque terms stay explicitly unresolved.
- Apply `增、删、改、整` from the reader's point of view. Add context that removes a barrier, remove clutter from the main path without erasing source evidence, rewrite for clear modern comprehension, and organize the book around reader questions while preserving source order separately.
- Make the introduction answer what the book is, who should read it, what value it offers, what its parts contain and how they relate, what is distinctive, where to begin, what remains limited or uncertain, and what the modern edition changed.
- For core terms, add a plain definition, contextual definition, exact source occurrence, usage example, related terms, and likely confusion. Validate these fields from `reader-aids.json`; do not infer completion from a summary count.
- After the first complete reader draft, run `$chaoyun-reader-experience-reviser` from cover through glossary. Record and apply traceable additions, removals from the continuous reading path, rewrites, and reorganizations; then require a different regression reviewer before publication.
- After preserving the guide/process edition, perform the final-reader cut. Reassess every AI-authored introduction, transition, glossary explanation, example and figure note for a concrete reader need; remove, rewrite or move anything that is generic, circular, promotional, field-shaped or more burdensome than the source passage it explains.
- For content-bearing diagrams, plates, maps, tables, or formula-like passages, explain what the reader should look at and in what order. Do not reuse one generic note as if it were figure-specific guidance.
- Add practical checklists, observation guides, or examples only when they are supported by the source or clearly labeled as editorial aids.
- Render classical Chinese, traditional Chinese, and Japanese into natural modern Chinese without adding unsupported facts or certainty.

## Traditional claims and present-day framing

Preserve traditional claims as part of the book. Attribute them with wording such as `书中认为`, `传统上认为`, or `古人以为` when a modern reader might mistake them for verified contemporary fact. Separate directly observable descriptions from traditional causal, predictive, medical, or fortune claims. Do not silently delete, endorse, or sensationalize them.

## Completeness

- Lock the source PDF physical page count at intake.
- Give every source page one explicit disposition.
- Keep front matter, illustrations, captions, marginal notes, appendices, and colophons unless excluded with a recorded reason.
- A sample, excerpt, or representative chapter must be labeled as such and stored outside the official release path.

## Release acceptance

The official reader release contains a designed cover, formal copyright/credits page, producer credit when supplied, clickable table of contents, PDF bookmarks, readable body, glossary, and any declared appendices. Its filename follows `<原书名>·<版本名>.pdf`, for example `<原书名>·现代白话版.pdf`. Deliver one unambiguous official PDF; archive or clearly label superseded drafts.

For this ordinary-reader mode, inspect every rendered page regardless of book length. Preserve specific findings and proof images; a total count is not review evidence.

Before publication, complete `50-edited/editorial-report.json`. A polished cover, clickable contents, and valid PDF structure cannot compensate for a missing evidence-based introduction, reconstructed source hierarchy, contextual glossary, or semantic review.
