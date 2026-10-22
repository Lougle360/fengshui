# Routing difficult PDFs

Diagnose at page level rather than assuming one route for the whole file.

| Condition | Primary route | Required check |
|---|---|---|
| Reliable embedded text | text extraction plus layout recovery | compare sampled glyphs and reading order against page images |
| Clear scan | layout-aware OCR | sample vertical text, small notes, tables, and page edges |
| Mixed digital and scan | per-page hybrid | detect blank/garbled embedded-text pages |
| Vertical classical Chinese | vertical-layout OCR plus `lzh` modernization | column order and annotation ownership |
| Japanese or kanbun | Japanese-capable OCR plus language segmentation | distinguish Japanese grammar from classical Chinese |
| Dense notes or double-line annotations | region/column reconstruction | parent note anchors and reading order |
| Tables, diagrams, seals, formulas | preserve as image plus structured representation where reliable | no invented cells or labels |
| Blur, bleed-through, damage | image enhancement variants plus visual comparison | unresolved glyph ledger, never semantic guessing |
| Handwriting or cursive | specialist recognition or assisted transcription | default grade C unless independently verified |

Use a representative set containing the beginning, middle, end, densest page, image-heavy page, smallest annotations, worst scan, and every distinct language/layout family. The sample determines routing only; it does not prove full-book quality.

Markdown is unsuitable as the sole representation for maps, music, engineering drawings, or primarily visual comics. Preserve those pages as images and state the semantic limitations.
