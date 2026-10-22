"""Generate mechanical evidence fields and pending review rows; never approve meaning."""
import argparse
import json
from pathlib import Path
from validate_delivery import digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    root = parser.parse_args().workspace.resolve()
    target = root / '90-audit/fidelity-review.json'
    if target.exists():
        parser.error('preserve the existing fidelity review in history before preparing a new one')
    paths = ['20-source/blocks.jsonl', '30-normalized/blocks.jsonl', '40-modernized/blocks.jsonl',
             '50-edited/blocks.jsonl', '50-edited/modern-reading.md', '50-edited/delivery-contract.json']
    hashes = {relative: digest(root / relative) for relative in paths}
    rows = [json.loads(line) for line in (root / paths[0]).read_text(encoding='utf-8').splitlines() if line.strip()]
    data = {'schema_version': '1.0', 'input_hashes': hashes, 'producer': None, 'reviewer': None,
            'blocks': [{'block_id': row['block_id'], 'status': 'pending', 'evidence': None,
                        'source_quote': None, 'modern_quote': None, 'reader_quote': None,
                        'disposition_reason': None,
                        'checks': {key: None for key in ['omissions', 'additions', 'negation', 'conditions', 'quantities', 'terms']}} for row in rows],
            'figures': [{'block_id': row['block_id'], 'section_heading': None, 'guidance_quote': None,
                         'status': 'pending', 'evidence': None} for row in rows
                        if row.get('block_type') in {'figure', 'table', 'diagram', 'map'} and row.get('disposition') not in {'noncontent', 'excluded_with_reason'}]}
    with target.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'status': 'pending_fidelity_review', 'blocks': len(rows)}))


if __name__ == '__main__':
    main()
