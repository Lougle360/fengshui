"""Check book-specific outcomes and content-bound fidelity evidence, not semantic truth."""
import hashlib
import json
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(text, heading):
    matches = list(re.finditer(r'^(#{1,6})\s+(.+?)\s*$', text, re.M))
    selected = [i for i, match in enumerate(matches) if match[2] == heading]
    if len(selected) != 1:
        return ''
    index = selected[0]
    first = matches[index]
    end = next((match.start() for match in matches[index + 1:] if len(match[1]) <= len(first[1])), len(text))
    return text[first.end():end]


def validate(root):
    errors = []
    try:
        contract = json.loads((root / '50-edited/delivery-contract.json').read_text(encoding='utf-8'))
        book = json.loads((root / 'book.json').read_text(encoding='utf-8'))
        audit = json.loads((root / '90-audit/fidelity-review.json').read_text(encoding='utf-8'))
        manuscript = root / '50-edited/modern-reading.md'
        text = manuscript.read_text(encoding='utf-8')
        compact_final = contract.get('rendering_profile') == 'compact_final_reader'
        if str(book.get('workflow_schema_version') or '') in {'1.8', '1.9', '1.10'} and not compact_final:
            errors.append('workflow 1.8+ ordinary-reader delivery requires compact_final_reader rendering_profile')
        paths = ['20-source/blocks.jsonl', '30-normalized/blocks.jsonl', '40-modernized/blocks.jsonl',
                 '50-edited/blocks.jsonl', '50-edited/modern-reading.md', '50-edited/delivery-contract.json']
        for relative in paths:
            if audit.get('input_hashes', {}).get(relative) != digest(root / relative):
                errors.append(f'fidelity review stale or missing binding: {relative}')
        source = {row['block_id']: row for row in (json.loads(line) for line in (root / paths[0]).read_text(encoding='utf-8').splitlines() if line.strip())}
        modern = {row['block_id']: row for row in (json.loads(line) for line in (root / paths[2]).read_text(encoding='utf-8').splitlines() if line.strip())}
        for field in ['target_reader', 'reading_goal', 'scope', 'limitations']:
            if not isinstance(contract.get(field), str) or not contract[field].strip():
                errors.append(f'delivery contract requires {field}')
        headings = set(re.findall(r'^#{1,6}\s+(.+?)\s*$', text, re.M))
        outcomes = contract.get('outcomes') or []
        if not outcomes:
            errors.append('delivery contract requires book-specific reader outcomes')
        ids = []
        for item in outcomes:
            ids.append(item.get('id'))
            if not item.get('question') or not item.get('answer') or item.get('section_heading') not in headings:
                errors.append('reader outcome lacks question/answer or a real section')
            if not item.get('quote') or item['quote'] not in section(text, item.get('section_heading')) or not item.get('review_evidence') or item.get('status') != 'passed':
                errors.append('reader outcome lacks manuscript evidence and acceptance')
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            errors.append('reader outcomes require unique IDs')
        if not audit.get('reviewer') or audit.get('reviewer') == audit.get('producer') or not audit.get('producer'):
            errors.append('fidelity review requires separate producer and reviewer')
        rows = audit.get('blocks') or []
        if len(rows) != len(source) or {row.get('block_id') for row in rows} != set(source):
            errors.append('fidelity review must account for every source block exactly once')
        for row in rows:
            block = source.get(row.get('block_id'), {})
            if row.get('status') != 'passed' or not row.get('evidence'):
                errors.append('source block lacks passing fidelity evidence')
            if block.get('disposition') in {'noncontent', 'excluded_with_reason', 'unreadable'}:
                if not row.get('disposition_reason'):
                    errors.append('non-reading block requires a reviewed disposition reason')
                continue
            quote_checks = [('source_quote', block.get('source_text') or ''),
                            ('modern_quote', modern.get(row.get('block_id'), {}).get('modern_text') or '')]
            if not compact_final:
                quote_checks.append(('reader_quote', text))
            for key, content in quote_checks:
                if not isinstance(row.get(key), str) or not row[key].strip() or row[key] not in content:
                    errors.append(f'fidelity {row.get("block_id")} missing real {key}')
            if compact_final:
                expected_anchor = f'<!-- source:{row.get("block_id")} -->'
                if row.get('reader_anchor') != expected_anchor or expected_anchor not in text:
                    errors.append(f'fidelity {row.get("block_id")} missing final-reader source anchor')
            checks = row.get('checks') or {}
            for dimension in ['omissions', 'additions', 'negation', 'conditions', 'quantities', 'terms']:
                if not isinstance(checks.get(dimension), str) or not checks[dimension].strip():
                    errors.append(f'fidelity {row.get("block_id")} lacks {dimension} review')
        figures = {key for key, row in source.items() if row.get('block_type') in {'figure', 'table', 'diagram', 'map'} and row.get('disposition') not in {'noncontent', 'excluded_with_reason'}}
        figure_rows = audit.get('figures') or []
        if len(figure_rows) != len(figures) or {row.get('block_id') for row in figure_rows} != figures:
            errors.append('figure evidence must match source figure inventory')
        for row in figure_rows:
            if compact_final:
                expected_anchor = f'<!-- source:{row.get("block_id")} -->'
                if row.get('figure_anchor') != expected_anchor or expected_anchor not in text or not row.get('evidence') or row.get('status') != 'passed':
                    errors.append('final-reader figure requires a rendered source anchor and review')
                if row.get('mode') not in {'guided', 'reference_only'}:
                    errors.append('final-reader figure requires guided or reference_only mode')
                if row.get('mode') == 'reference_only' and row.get('notice') != '原图模糊，仅保留原图，不承担教学证明。':
                    errors.append('reference-only figure requires the exact reader notice')
            else:
                if not row.get('guidance_quote') or row['guidance_quote'] not in section(text, row.get('section_heading')) or not row.get('evidence') or row.get('status') != 'passed':
                    errors.append('figure requires rendered specific guidance and review')
                if row.get('section_heading') not in headings:
                    errors.append('figure references unknown reader section')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(f'invalid delivery evidence: {exc}')
    return errors
