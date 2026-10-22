# Normalization policy

Classify each operation as `script_conversion`, `variant_mapping`, `punctuation`, `segmentation`, `whitespace`, `terminology`, or `editorial_exception`.

Each change record contains `block_id`, source span, before, after, operation, rule or evidence, confidence, and reviewer state.

## Safe defaults

- Convert common traditional characters only when the target word and domain meaning are unambiguous.
- Keep rare names, place names, book titles, calendrical terms, technical glyphs, and variant forms until a terminology decision exists.
- Add punctuation conservatively. When punctuation materially changes parsing, keep alternatives in the ledger.
- Japanese old/new character conversion occurs only inside text already classified as Japanese and follows a Japanese route.
- Preserve original quotations in the source layer even when the reading edition uses normalized typography.

## 乾 is not 干

Generic traditional-to-simplified converters map 乾 to 干. In feng-shui, Yijing and calendrical texts 乾 is almost always the trigram or the northwest direction (乾龍, 乾宮, 乾山巽向, 乾亥, 乾坤艮巽) and must stay 乾. Convert to 干 only when it means dry (乾燥, 乾枯, 乾涸). 幹 (trunk, as in 大幹龍) correctly becomes 干. After conversion, run `text_hygiene.py <workspace>`; any 乾 simplified to 干 blocks G3.
