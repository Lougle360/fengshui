"""Bind reader acceptance to the actual Markdown, assets, PDF and rendered proofs."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prose(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*图注：", "", text, flags=re.M)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return compact(text)


def compact(text):
    # Preserve punctuation, signs and digits. Only layout whitespace is ignorable.
    return "".join(c for c in unicodedata.normalize("NFC", text) if not c.isspace())


def without_generated_navigation_sections(text, navigation, navigation_pages):
    """Remove manuscript sections whose rendered pages are generated navigation."""
    headings = [
        str(row.get("heading"))
        for row in navigation
        if row.get("target_page") in navigation_pages and row.get("heading")
    ]
    for heading in headings:
        pattern = rf"^#{{1,6}}\s+{re.escape(heading)}\s*$.*?(?=^#{{1,6}}\s+|\Z)"
        text = re.sub(pattern, "", text, flags=re.M | re.S)
    return text


def page_text(page, review, headings, errors):
    """Exclude only exact declared running headers/page numbers in page-edge strips."""
    import pymupdf
    furniture = review.get('furniture') or []
    if not furniture:
        return page.get_text(sort=True)
    allowed = []
    for item in furniture:
        try:
            rectangle = pymupdf.Rect(item['bbox'])
            value = str(item['text'])
            valid_text = ((item.get('kind') == 'page_number' and value == str(page.number + 1)) or
                          (item.get('kind') == 'running_header' and value in headings))
            edge = rectangle.y1 <= page.rect.height * .12 or rectangle.y0 >= page.rect.height * .88
            if not valid_text or not edge or rectangle.is_empty or not page.rect.contains(rectangle):
                raise ValueError('not permitted edge furniture')
            allowed.append([rectangle, compact(value), 0])
        except (ValueError, KeyError, TypeError):
            errors.append('invalid page furniture declaration')
    lines = []
    for block in page.get_text('dict', sort=True)['blocks']:
        for line in block.get('lines', []):
            text = ''.join(span.get('text', '') for span in line['spans'])
            matches = [item for item in allowed if item[0].contains(pymupdf.Rect(line['bbox'])) and item[1] == compact(text)]
            if len(matches) == 1:
                matches[0][2] += 1
            else:
                lines.append(text)
    if any(item[2] != 1 for item in allowed):
        errors.append('page furniture must match exactly one real edge line')
    return '\n'.join(lines)


def validate(root, pdf):
    errors = []
    try:
        import pymupdf
        manifest = json.loads((root / "90-audit/release-binding.json").read_text(encoding="utf-8"))
        edited = root / "50-edited/modern-reading.md"
        published = root / "60-publication/modern-reading.md"
        if edited.read_bytes() != published.read_bytes():
            errors.append("publication Markdown differs from the reader-accepted manuscript")
        for field, path in (("manuscript_sha256", edited), ("markdown_sha256", published), ("pdf_sha256", pdf)):
            if manifest.get(field) != sha(path):
                errors.append(f"release binding {field} is stale")
        text = published.read_text(encoding="utf-8")
        assets = manifest.get("assets")
        if not isinstance(assets, dict):
            raise ValueError("release binding requires assets hash map")
        actual_assets = {}
        for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
            clean = target.strip()
            clean = clean[1:-1] if clean.startswith('<') and clean.endswith('>') else clean.split()[0]
            path = (published.parent / clean).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError("missing or escaping publication asset")
            actual_assets[clean] = sha(path)
            edited_asset = (edited.parent / clean).resolve()
            if not edited_asset.is_relative_to(root.resolve()) or not edited_asset.is_file() or sha(edited_asset) != sha(path):
                errors.append(f"reader and publication assets differ: {clean}")
        if assets != actual_assets:
            errors.append("release asset inventory/hash mismatch")
        with pymupdf.open(pdf) as document:
            # A conservative mechanical check, not semantic equivalence or typography review.
            pages = manifest.get("page_reviews") or []
            by_page = {row.get('page'): row for row in pages}
            headings = set(re.findall(r'^#{1,6}\s+(.+?)\s*$', text, re.M))
            # Navigation pages contain a generated table of contents that is
            # validated below, link by link, and is not manuscript prose.
            # Including it here duplicates headings and makes the prose check
            # contradict the navigation gate.
            navigation_pages = {
                row.get('link_page') for row in (manifest.get('navigation') or [])
                if type(row.get('link_page')) is int
            }
            extracted = compact("\n".join(
                page_text(page, by_page.get(page.number + 1, {}), headings, errors)
                for page in document
                if page.number + 1 not in navigation_pages
            ))
            expected_text = without_generated_navigation_sections(
                text, manifest.get('navigation') or [], navigation_pages
            )
            expected = prose(expected_text)
            if not expected or expected != extracted:
                errors.append("PDF text does not cover the accepted Markdown in reading order")
            navigation = manifest.get('navigation') or []
            if len(document) > 5:
                headings = re.findall(r'^#{1,2}\s+(.+?)\s*$', text, re.M)
                if [row.get('heading') for row in navigation] != headings:
                    errors.append('navigation evidence must cover every level 1/2 heading in order')
                outlines = document.get_toc()
                for row in navigation:
                    page = row.get('target_page')
                    link_page = row.get('link_page')
                    heading = row.get('heading')
                    if type(page) is not int or not 1 <= page <= len(document) or type(link_page) is not int or not 1 <= link_page <= len(document):
                        errors.append('invalid navigation page mapping')
                        continue
                    if compact(heading) not in compact(document[page - 1].get_text()) or not any(item[1] == heading and item[2] == page for item in outlines):
                        errors.append('navigation target title/bookmark mismatch')
                    links = document[link_page - 1].get_links()
                    if not any(link.get('page') == page - 1 and compact(heading) in compact(document[link_page - 1].get_text(clip=link['from'])) for link in links):
                        errors.append('navigation has no matching internal link target')
                    if row.get('status') != 'passed' or not row.get('evidence'):
                        errors.append('navigation mapping lacks review evidence')
            if [row.get("page") for row in pages] != list(range(1, len(document) + 1)):
                errors.append("release requires ordered proof evidence for every PDF page")
            for row in pages:
                number = row.get("page")
                if type(number) is not int or not 1 <= number <= len(document):
                    errors.append("invalid proof page number")
                    continue
                if row.get("status") != "passed" or row.get("issues") != [] or not row.get("evidence") or not row.get("reviewer"):
                    errors.append(f"proof page {number} lacks passing visual review")
                relative = row.get("image")
                if not isinstance(relative, str) or Path(relative).is_absolute():
                    raise ValueError("proof image must be workspace-relative")
                path = (root / relative).resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    raise ValueError("missing or escaping proof image")
                rendered = document[number - 1].get_pixmap(matrix=pymupdf.Matrix(1, 1), colorspace=pymupdf.csRGB, alpha=False)
                saved = pymupdf.Pixmap(str(path))
                if (saved.width, saved.height, saved.n, saved.samples) != (rendered.width, rendered.height, rendered.n, rendered.samples):
                    errors.append(f"proof page {number} image does not match current PDF render")
    except (OSError, ValueError, TypeError, KeyError, ImportError, AttributeError) as exc:
        errors.append(f"invalid release binding: {exc}")
    return errors
