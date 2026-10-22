# Diagnosis contract

`profile.json` contains book-level facts, counts, layout/language families, proposed engines, representative pages, known limits, cost estimate, and recommended completion grade ceiling.

Each `page-map.jsonl` record contains:

```json
{
  "schema_version": "1.0",
  "book_id": "...",
  "page_id": "P000123",
  "source_page": 128,
  "page_kind": "scan",
  "layout": ["vertical", "double_line_notes"],
  "languages": ["lzh"],
  "text_layer_quality": "none",
  "scan_quality": "fair",
  "route": "layout_ocr_vertical_zh",
  "risk_flags": ["bleed_through"],
  "sample_verified": true,
  "notes": []
}
```

Allowed route names are descriptive identifiers, not commitments to one vendor. Record the actual tool and version in the run state when execution begins.
