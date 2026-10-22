"""Read-only 1.10 reading-unit contract; validates evidence, not interpretation."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'expected JSON object: {path.name}')
    return value


def evidence(root, item):
    if not isinstance(item, dict) or not isinstance(item.get('file'), str):
        raise ValueError('missing evidence file/hash')
    path = (root / item['file']).resolve()
    if Path(item['file']).is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError('missing or escaping evidence file')
    if item.get('sha256') != digest(path):
        raise ValueError('stale evidence hash')
    if not str(item.get('reason', '')).strip():
        raise ValueError('missing evidence reason')


def validate(root, publication=False):
    root = Path(root).resolve()
    errors = []
    try:
        book = load(root / 'book.json')
        if book.get('delivery_mode') != 'ordinary_reader' or book.get('workflow_schema_version') != '1.10':
            return errors
        source_path = root / '20-source/blocks.jsonl'
        source = [json.loads(x) for x in source_path.read_text(encoding='utf-8').splitlines() if x.strip()]
        by_id = {x['block_id']: x for x in source}
        if len(by_id) != len(source):
            raise ValueError('duplicate source block IDs')
        scope = load(root / '10-diagnosis/edition-scope.json')
        components = {c['component_id']: c for c in scope['source_components']}
        if scope.get('status') != 'locked':
            errors.append('edition scope must be locked before reader units')
        path = root / '50-edited/reader-units.json'
        data = load(path)
        if data.get('schema_version') != '1.0' or data.get('status') != 'reviewed':
            errors.append('reader units require schema 1.0 and actual reviewed status')
        if data.get('source_sha256') != digest(source_path):
            errors.append('reader units source binding is stale')
        evidence(root, data.get('review_evidence'))
        units = data['units']
        if not isinstance(units, list) or not units or any(not isinstance(u, dict) for u in units):
            raise ValueError('reader units must be nonempty objects')
        index = {u['unit_id']: u for u in units}
        if len(index) != len(units) or any(not isinstance(k, str) or not k.strip() for k in index):
            raise ValueError('duplicate or empty unit IDs')
        owned, owner = Counter(), {}
        for u in units:
            uid = u['unit_id']
            ids = u.get('source_blocks')
            if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
                raise ValueError(f'{uid}: source_blocks must be nonempty IDs')
            owned.update(ids)
            owner.update({bid: uid for bid in ids})
            if not set(ids).issubset(by_id):
                raise ValueError(f'{uid}: unknown source block')
            if u.get('kind') not in {'main_text', 'commentary', 'heading', 'preface', 'figure', 'table', 'paratext', 'noncontent'}:
                errors.append(f'{uid}: invalid kind')
            if u.get('source_pages') != sorted({by_id[b]['source_page'] for b in ids}):
                errors.append(f'{uid}: source page inventory differs')
            if u.get('destination') not in {'final_reader', 'supplement', 'evidence_only'}:
                errors.append(f'{uid}: invalid destination')
            for bid in ids:
                block = by_id[bid]
                component = components.get(block.get('component_id'))
                if not component:
                    errors.append(f'{uid}: source component is absent from edition scope')
                elif block.get('disposition') not in {'noncontent', 'unreadable', 'excluded_with_reason'} and u.get('destination') != component.get('planned_destination'):
                    errors.append(f'{uid}: destination contradicts locked edition scope')
            if any(by_id[b].get('structural_role') == 'commentary' or by_id[b].get('block_type') == 'commentary' for b in ids) and u.get('kind') != 'commentary':
                errors.append(f'{uid}: commentary cannot be disguised as another kind')
            evidence(root, u.get('decision_evidence'))
            targets = u.get('target_units', [])
            if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
                raise ValueError(f'{uid}: invalid target_units')
            if u.get('kind') == 'commentary':
                scope = u.get('commentary_scope')
                allowed = {'passage': {'main_text'}, 'chapter': {'heading'}, 'book': {'heading'}, 'note': {'commentary'}}
                if scope in allowed:
                    if not targets or len(targets) != len(set(targets)) or any(t not in index or index[t].get('kind') not in allowed[scope] for t in targets):
                        errors.append(f'{uid}: commentary has no valid target for its scope')
                elif scope == 'missing_source':
                    # An actual source lacuna is retained, never filled from another edition.
                    if targets or not u.get('uncertainty_id') or not u.get('reader_notice'):
                        errors.append(f'{uid}: source lacuna needs an uncertainty ID and reader notice, without invented target')
                    ledger = root / '90-audit/uncertain-items.jsonl'
                    entries = [json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
                    if not any(u.get('uncertainty_id') in {r.get('issue_id'), r.get('candidate_id'), r.get('id')} for r in entries):
                        errors.append(f'{uid}: missing-source uncertainty is not in the active reader ledger')
                else:
                    errors.append(f'{uid}: unresolved commentary scope')
            elif targets:
                errors.append(f'{uid}: only commentary may declare targets')
        if set(owned) != set(by_id) or any(n != 1 for n in owned.values()):
            errors.append('every source block must belong to exactly one reader unit')
        # Cycles can arise in notes explaining other notes.
        def visit(uid, chain):
            if uid in chain:
                raise ValueError('cyclic commentary ownership')
            for target in index[uid].get('target_units', []):
                if target in index:
                    visit(target, chain | {uid})
        for uid in index:
            visit(uid, set())
        joins = data.get('continuations')
        if not isinstance(joins, list):
            raise ValueError('continuations inventory is required, even when empty')
        pairs = set()
        for link in joins:
            a, b = link['from_block'], link['to_block']
            if a not in by_id or b not in by_id or a == b or (a, b) in pairs:
                raise ValueError('invalid or duplicate continuation')
            pairs.add((a, b))
            if (by_id[a]['source_page'], by_id[a]['reading_order']) >= (by_id[b]['source_page'], by_id[b]['reading_order']):
                errors.append('continuation reverses source order')
            if owner.get(a) != owner.get(b):
                errors.append('continued text must be understood in the same reader unit')
            evidence(root, link.get('evidence'))
        for bid, row in by_id.items():
            if row.get('continues_to_next_page') and not any(a == bid for a, b in pairs):
                errors.append(f'{bid}: missing outgoing continuation')
            if row.get('continues_from_previous_page') and not any(b == bid for a, b in pairs):
                errors.append(f'{bid}: missing incoming continuation')
        if publication:
            rendered = load(root / '50-edited/reader-unit-rendering.json')
            md = root / '50-edited/modern-reading.md'
            if rendered.get('units_sha256') != digest(path) or rendered.get('manuscript_sha256') != digest(md):
                errors.append('reader-unit rendering binding is stale')
            lines = md.read_text(encoding='utf-8').splitlines()
            locations = rendered['units']
            if not isinstance(locations, list) or any(not isinstance(x, dict) for x in locations):
                raise ValueError('rendering units must be objects in an array')
            required = {u['unit_id'] for u in units if u['destination'] == 'final_reader'}
            if Counter(x['unit_id'] for x in locations) != Counter({k: 1 for k in required}):
                errors.append('rendering must locate every released unit exactly once')
            previous_end = 0
            seen = set()
            for loc in locations:
                uid = loc['unit_id']
                u = index[uid]
                start, end = loc['start_line'], loc['end_line']
                if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines) or start <= previous_end:
                    raise ValueError('invalid, overlapping or unordered reader unit range')
                previous_end = end
                excerpt = '\n'.join(lines[start-1:end])
                if not loc.get('quote') or loc['quote'] not in excerpt:
                    errors.append(f'{uid}: reader quote absent from bound range')
                if u.get('commentary_scope') == 'missing_source' and u['reader_notice'] not in excerpt:
                    errors.append(f'{uid}: source lacuna notice absent from reader text')
                for target in u.get('target_units', []):
                    if target not in seen:
                        errors.append(f'{uid}: commentary precedes or lacks its displayed target')
                seen.add(uid)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        errors.append(f'invalid reader-unit contract: {exc}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--publication', action='store_true')
    args = parser.parse_args()
    errors = validate(args.workspace, args.publication)
    print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
