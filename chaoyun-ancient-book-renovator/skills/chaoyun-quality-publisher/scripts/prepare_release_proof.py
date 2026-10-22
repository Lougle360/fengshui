"""Render proof images and a PENDING manifest; never manufacture visual approval."""
import argparse
import json
from pathlib import Path

from validate_release_binding import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--candidate-pdf", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    destination = root / "90-audit/release-binding.json"
    if destination.exists():
        parser.error("release-binding.json already exists; preserve it in review history before preparing new proof")
    try:
        import re
        import pymupdf
        book = json.loads((root / "book.json").read_text(encoding="utf-8"))
        relative = book.get("release_filename")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError("book.json requires a relative release_filename")
        pdf = args.candidate_pdf.resolve()
        if pdf == (root / relative).resolve():
            raise ValueError("proof preparation requires a separate candidate, not the official release")
        if not pdf.is_relative_to(root) or not pdf.is_file():
            raise ValueError("candidate PDF is missing or escapes workspace")
        edited = root / "50-edited/modern-reading.md"
        markdown = root / "60-publication/modern-reading.md"
        if edited.read_bytes() != markdown.read_bytes():
            raise ValueError("publication Markdown must equal the accepted manuscript")
        assets = {}
        for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")):
            clean = target.strip()
            clean = clean[1:-1] if clean.startswith('<') and clean.endswith('>') else clean.split()[0]
            path = (markdown.parent / clean).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("missing or escaping publication asset")
            assets[clean] = sha(path)
        pdf_hash = sha(pdf)
        directory = root / "90-audit/proofs" / pdf_hash
        directory.mkdir(parents=True, exist_ok=True)
        reviews = []
        with pymupdf.open(pdf) as document:
            for number, page in enumerate(document, 1):
                path = directory / f"page-{number:04d}.png"
                page.get_pixmap(matrix=pymupdf.Matrix(1, 1), colorspace=pymupdf.csRGB, alpha=False).save(path)
                reviews.append({"page": number, "image": path.relative_to(root).as_posix(),
                                "role": None, "status": "pending", "issues": [],
                                "checks": {key: None for key in ("legibility", "density", "whitespace", "hierarchy", "continuity")},
                                "density_exception": None, "furniture": [],
                                "reviewer": None, "evidence": None})
        manifest = {"schema_version": "1.1", "renderer": "PyMuPDF " + pymupdf.VersionBind,
                    "manuscript_sha256": sha(edited), "markdown_sha256": sha(markdown),
                    "pdf_sha256": pdf_hash, "assets": assets, "page_reviews": reviews}
        manifest['navigation'] = [{"heading": heading, "target_page": None, "link_page": None,
                                   "visible_page_label": None,
                                   "status": "pending", "evidence": None}
                                  for heading in re.findall(r'^#{1,2}\s+(.+?)\s*$', markdown.read_text(encoding='utf-8'), re.M)]
        with destination.open('x', encoding='utf-8') as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        print(json.dumps({"status": "pending_visual_review", "pages": len(reviews), "manifest": str(destination)}))
    except (OSError, ValueError, ImportError, KeyError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
