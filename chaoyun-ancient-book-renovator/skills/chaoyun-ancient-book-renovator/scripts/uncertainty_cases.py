"""Adversarial closure tests. All evidence is synthetic and lives in a temporary workspace."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


def run(root):
    from closure_evidence import closure_digest
    path = Path(__file__).resolve().parents[2] / 'chaoyun-uncertainty-adjudicator/scripts/project_open_items.py'
    spec = importlib.util.spec_from_file_location('uncertainty_contract_tests', path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    original_candidates = gate.read_jsonl(root / '90-audit/uncertainty-candidates.jsonl')
    original_decisions = gate.read_jsonl(root / '90-audit/uncertainty-adjudication.jsonl')
    original_files = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    passed = []

    def check(name, mutate, expected=None, publication=False):
        candidates, decisions = copy.deepcopy(original_candidates), copy.deepcopy(original_decisions)
        try:
            mutate(candidates, decisions)
            errors = gate.validate(root, candidates, decisions, require_release=publication)
            if expected is None and errors:
                raise AssertionError(f'{name}: {errors}')
            if expected and not any(expected in error for error in errors):
                raise AssertionError(f'{name}: expected {expected}, got {errors}')
            passed.append(name)
        finally:
            for p, data in original_files.items():
                p.write_bytes(data)

    def sign(row):
        closure = row['closure']
        payload = {k: v for k, v in closure.items() if k != 'review_record'}
        record = {'reviewer': 'synthetic-independent-reviewer', 'run_id': 'synthetic-review',
                  'adjudication_id': row['adjudication_id'], 'status': 'passed',
                  'fidelity_evidence': 'Synthetic test.', 'reader_evidence': 'Synthetic test.',
                  'closure_sha256': closure_digest(row)}
        relative = '90-audit/test-review-' + row['adjudication_id'] + '.json'
        file = root / relative
        file.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        closure['review_record'] = {'path': relative, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}

    check('positive-closure', lambda c, d: None)
    check('positive-final-recheck-and-pilot', lambda c, d: None, publication=True)
    def discovery(c, d):
        c[0].update(schema_version='1.3', owner_stage='source', created_at='2026-01-01T00:00:00Z',
                    input_ref=copy.deepcopy(d[0]['closure']['evidence'][0]))
    check('located-discovery', discovery)
    def unlocated(c, d):
        discovery(c, d); c[0].pop('input_ref')
    check('unlocated-discovery', unlocated, 'discovery input is not bound')
    def no_owner(c, d):
        discovery(c, d); c[0]['owner_stage'] = 'polish_anything'
    check('missing-responsible-stage', no_owner, 'responsible pipeline stage')
    for status in ['resolved_confirmed', 'resolved_noncontent', 'resolved_structural', 'resolved_duplicate']:
        def bare(c, d, status=status):
            d[0].pop('closure'); d[0]['status'] = status
        check('bare-' + status, bare, 'requires closure evidence')
    check('empty-evidence', lambda c, d: d[0]['closure'].update(evidence=[]), 'nonempty located evidence')
    check('fake-file', lambda c, d: d[0]['closure']['evidence'][0].update(path='90-audit/absent.png'), 'missing, empty or escaping')
    check('stale-evidence', lambda c, d: d[0]['closure']['evidence'][0].update(sha256='0'*64), 'stale evidence hash')
    check('unsupported-quote', lambda c, d: d[0]['closure']['evidence'][0].update(quote='不存在的证据片段'), 'quote is missing')
    check('missing-impact-scope', lambda c, d: d[0]['closure']['impact_review'].pop('terminology'), 'all six impact scopes')
    check('impact-without-files', lambda c, d: d[0]['closure']['impact_review']['source'].update(artifacts=[]), 'checked impact has no artifacts')
    check('stale-review-binding', lambda c, d: d[0]['closure']['impact_review']['source'].update(reason='A different conclusion'), 'review is stale')
    check('changed-decision-with-old-review', lambda c, d: d[0].update(rationale='A different decision rationale'), 'review is stale')
    check('missing-review-record', lambda c, d: d[0]['closure'].pop('review_record'), 'workspace-relative path and hash')

    def self_review(c, d):
        d[0]['closure']['producer'] = 'synthetic-independent-reviewer'; sign(d[0])
    check('same-producer-and-reviewer', self_review, 'distinct producer and reviewer')

    def duplicate(c, d):
        c.append(dict(c[0], candidate_id='UC_DUP'))
        row = copy.deepcopy(d[0]); row.update(adjudication_id='UA_DUP', candidate_ids=['UC_DUP'], status='resolved_duplicate', duplicate_of=c[0]['candidate_id'])
        row['closure']['action'] = 'duplicate'; sign(row); d.append(row)
    check('valid-duplicate-of-closed-main', duplicate)

    def duplicate_open(c, d):
        duplicate(c, d); d[0].update(status='open_material', issue_id='UI-MAIN')
    check('duplicate-of-open-main', duplicate_open, 'canonical issue is open')

    def duplicate_cycle(c, d):
        duplicate(c, d); d[0].update(status='resolved_duplicate', duplicate_of='UC_DUP')
        d[0]['closure']['action'] = 'duplicate'; sign(d[0])
    check('duplicate-cycle', duplicate_cycle, 'duplicate resolution cycle')
    check('unknown-duplicate-main', lambda c, d: d[0].update(status='resolved_duplicate', duplicate_of='NO_SUCH_CANDIDATE'), 'active canonical candidate')

    def historical(c, d):
        old = copy.deepcopy(d[0]); old.update(adjudication_id='UA_OLD', active=False, before='old', after='historical-value-not-current', issue_id='UI-STABLE')
        d[0]['supersedes'] = 'UA_OLD'; d.insert(0, old)
        sign(d[-1])
    check('historical-correction-preserved', historical)
    def reopened(c, d):
        historical(c, d); d[-1].update(status='open_material', issue_id='UI-STABLE')
    check('reopened-original-identity', reopened)
    def changed_identity(c, d):
        reopened(c, d); d[-1]['issue_id'] = 'UI-NEW'
    check('reopened-identity-drift', changed_identity, 'retain the original issue_id')

    def corrected(c, d):
        before, after = '天地玄黄', '天地元黄'
        refs = {}
        for key, text in [('input', before), ('output', after), ('current', after)]:
            relative = f'90-audit/test-change-{key}.txt'; p = root / relative
            p.write_text(text, encoding='utf-8')
            refs[key] = {'path': relative, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        d[0]['closure'].update(action='corrected', change={**refs, 'start_offset': 2, 'end_offset': 3, 'before': '玄', 'after': '元'})
        sign(d[0])
    check('exact-correction-applied', corrected)
    def unapplied(c, d):
        corrected(c, d); p = root / d[0]['closure']['change']['current']['path']; p.write_text('尚未修改', encoding='utf-8')
        d[0]['closure']['change']['current']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest(); sign(d[0])
    check('correction-not-applied', unapplied, 'not applied to its current artifact')
    def false_change(c, d):
        corrected(c, d); d[0]['closure']['change']['after'] = '错'; sign(d[0])
    check('fabricated-edit', false_change, 'does not replay')
    check('missing-final-recheck', lambda c, d: (root / '90-audit/uncertainty-release-review.json').unlink(), 'invalid final uncertainty review', publication=True)
    check('missing-real-chapter-trial', lambda c, d: (root / '90-audit/pilot-review.json').unlink(), 'invalid chapter trial', publication=True)
    def trial_changed(c, d):
        p = root / '90-audit/pilot-review.json'; data = json.loads(p.read_text(encoding='utf-8')); data['cases'][0]['evidence'] = 'New conclusion without review'
        p.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    check('stale-blind-trial-review', trial_changed, 'content-bound record', publication=True)
    def trial_errors(c, d):
        p = root / '90-audit/pilot-review.json'; data = json.loads(p.read_text(encoding='utf-8')); data['new_errors'] = ['new mistranslation']
        p.write_text(json.dumps(data), encoding='utf-8')
    check('trial-introduced-errors', trial_errors, 'unaddressed introduced errors', publication=True)
    def final_quote(c, d):
        p = root / '90-audit/uncertainty-release-review.json'; data = json.loads(p.read_text(encoding='utf-8'))
        data['items'][0]['quote'] = 'Unapplied final correction'
        record_path = root / data['review_record']['path']; record = json.loads(record_path.read_text(encoding='utf-8'))
        payload = {k: v for k, v in data.items() if k != 'review_record'}
        record['final_review_sha256'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        record_path.write_text(json.dumps(record), encoding='utf-8')
        data['review_record']['sha256'] = hashlib.sha256(record_path.read_bytes()).hexdigest()
        p.write_text(json.dumps(data), encoding='utf-8')
    check('final-correction-not-in-book', final_quote, 'absent from manuscript', publication=True)
    print(f'Uncertainty lifecycle tests passed: {len(passed)} (including positive and negative cases)')
