# Reconstruction policy

## Block types

Use `title`, `heading`, `body`, `quotation`, `commentary`, `marginalia`, `caption`, `table`, `figure`, `seal`, `page_number`, `header_footer`, `noncontent`, or `unknown`.

Block-print 版心 text (book title, 卷 number, section label, folio number, carver name such as 李桂林刻) and library stamps (such as 雪濤圖書館) are `header_footer` or `seal`, never `body`. When OCR has fused 版心 text into a body line (入地眼全書卷五砂法六壬砂疊登…), split it into its own block. Record book-specific forms in `book.json` `running_header_patterns` so the publication gate can catch any that slip through.

## Evidence hierarchy

1. Visible page image and coordinates.
2. Reliable embedded glyphs aligned to the image.
3. Agreement between independent OCR/layout passes.
4. Lexical or semantic plausibility, which may raise a review candidate but cannot establish transcription by itself.

## Cross-page joins

Join only when punctuation, syntax, indentation, block type, and page layout jointly support continuation. Preserve contributing block IDs and page IDs. Never join across a heading, caption, table, or note boundary merely because a sentence seems incomplete.

## Uncertainty

Keep the visible candidate text, confidence, alternatives, crop reference, and reason. Use a replacement marker only when no defensible character candidate exists.
