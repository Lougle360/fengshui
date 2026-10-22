# Normalization policy

Classify each operation as `script_conversion`, `variant_mapping`, `punctuation`, `segmentation`, `whitespace`, `terminology`, or `editorial_exception`.

Each change record contains `block_id`, source span, before, after, operation, rule or evidence, confidence, and reviewer state.

## Safe defaults

- Convert common traditional characters only when the target word and domain meaning are unambiguous.
- Keep rare names, place names, book titles, calendrical terms, technical glyphs, and variant forms until a terminology decision exists.
- Add punctuation conservatively. When punctuation materially changes parsing, keep alternatives in the ledger.
- Japanese old/new character conversion occurs only inside text already classified as Japanese and follows a Japanese route.
- Preserve original quotations in the source layer even when the reading edition uses normalized typography.
