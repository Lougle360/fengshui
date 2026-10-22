"""Synthetic behavioral regressions; these are not actual manuscript acceptance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from validate_reader_units import digest, validate


class ReaderUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write('book.json', {'delivery_mode': 'ordinary_reader', 'workflow_schema_version': '1.10'})
        self.write('90-audit/structure-review.json', {'synthetic': True})
        self.ev = {'file': '90-audit/structure-review.json', 'sha256': digest(self.root / '90-audit/structure-review.json'), 'reason': 'Synthetic test evidence, not real approval'}
        self.source = [
            {'block_id': 'h', 'source_page': 1, 'reading_order': 1, 'structural_role': 'heading'},
            {'block_id': 'a', 'source_page': 1, 'reading_order': 2, 'structural_role': 'body', 'continues_to_next_page': True},
            {'block_id': 'b', 'source_page': 2, 'reading_order': 1, 'structural_role': 'body', 'continues_from_previous_page': True},
            {'block_id': 'c', 'source_page': 2, 'reading_order': 2, 'structural_role': 'commentary'},
            {'block_id': 'd', 'source_page': 2, 'reading_order': 3, 'structural_role': 'body'},
        ]
        for block in self.source:
            block['component_id'] = 'C'
        self.write('10-diagnosis/edition-scope.json', {'status': 'locked', 'source_components': [
            {'component_id': 'C', 'kind': 'main_text', 'planned_destination': 'final_reader', 'required_in_release': True}]})
        p = self.root / '20-source/blocks.jsonl'
        p.parent.mkdir(parents=True)
        p.write_text('\n'.join(json.dumps(x) for x in self.source), encoding='utf-8')
        def unit(uid, kind, ids, pages, **extra):
            return dict(unit_id=uid, kind=kind, source_blocks=ids, source_pages=pages,
                        destination='final_reader', decision_evidence=self.ev, **extra)
        self.data = {'schema_version': '1.0', 'status': 'reviewed', 'source_sha256': digest(p), 'review_evidence': self.ev,
                     'units': [unit('H', 'heading', ['h'], [1]), unit('A', 'main_text', ['a', 'b'], [1, 2]),
                               unit('C', 'commentary', ['c'], [2], commentary_scope='passage', target_units=['A']),
                               unit('D', 'main_text', ['d'], [2])],
                     'continuations': [{'from_block': 'a', 'to_block': 'b', 'evidence': self.ev}]}
        self.save()
        self.write('50-edited/modern-reading.md', '# Chapter\nA complete passage\nAn explanation\nA passage without commentary\n')
        self.render = {'units_sha256': digest(self.root / '50-edited/reader-units.json'),
                       'manuscript_sha256': digest(self.root / '50-edited/modern-reading.md'),
                       'units': [dict(unit_id=uid, start_line=i, end_line=i, quote=quote) for i, (uid, quote) in enumerate([
                           ('H', '# Chapter'), ('A', 'A complete passage'), ('C', 'An explanation'), ('D', 'A passage without commentary')], 1)]}
        self.write('50-edited/reader-unit-rendering.json', self.render)

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')

    def save(self):
        self.write('50-edited/reader-units.json', self.data)

    def test_valid_cross_page_and_unannotated_passage(self):
        self.assertEqual(validate(self.root, True), [])

    def test_chapter_note(self):
        self.data['units'][2].update(commentary_scope='chapter', target_units=['H'])
        self.save()
        self.assertEqual(validate(self.root), [])

    def test_orphan_unknown_and_wrong_role(self):
        for targets in ([], ['unknown'], ['H']):
            self.data['units'][2]['target_units'] = targets
            self.save()
            self.assertTrue(validate(self.root))

    def test_disguised_commentary(self):
        self.data['units'][2].update(kind='main_text', target_units=[])
        self.save()
        self.assertTrue(validate(self.root))

    def test_note_cycle(self):
        self.data['units'][2].update(commentary_scope='note', target_units=['C'])
        self.save()
        self.assertTrue(validate(self.root))

    def test_missing_and_duplicate_source(self):
        initial = copy.deepcopy(self.data)
        self.data['units'].pop()
        self.save()
        self.assertTrue(validate(self.root))
        self.data = initial
        self.data['units'][-1]['source_blocks'].append('c')
        self.save()
        self.assertTrue(validate(self.root))

    def test_missing_reversed_duplicate_continuation(self):
        original = copy.deepcopy(self.data['continuations'])
        for links in ([], [{'from_block': 'b', 'to_block': 'a', 'evidence': self.ev}], original + original):
            self.data['continuations'] = links
            self.save()
            self.assertTrue(validate(self.root))

    def test_stale_source_or_evidence(self):
        self.data['source_sha256'] = 'stale'
        self.save()
        self.assertTrue(validate(self.root))
        self.data['source_sha256'] = digest(self.root / '20-source/blocks.jsonl')
        self.write('90-audit/structure-review.json', {'changed': True})
        self.save()
        self.assertTrue(validate(self.root))

    def test_escaping_evidence(self):
        self.data['review_evidence'] = dict(self.ev, file='../outside.json')
        self.save()
        self.assertTrue(validate(self.root))

    def test_lacuna_requires_real_ledger_and_notice(self):
        self.data['units'][2].update(commentary_scope='missing_source', target_units=[], uncertainty_id='U1', reader_notice='The source passage is missing.')
        self.save()
        self.assertTrue(validate(self.root))
        self.write('90-audit/uncertain-items.jsonl', json.dumps({'issue_id': 'U1'}) + '\n')
        self.assertEqual(validate(self.root), [])
        self.render['units_sha256'] = digest(self.root / '50-edited/reader-units.json')
        self.write('50-edited/reader-unit-rendering.json', self.render)
        self.assertTrue(validate(self.root, True))

    def test_rendering_stale_overlap_omission(self):
        for change in ('stale', 'overlap', 'omission'):
            r = copy.deepcopy(self.render)
            if change == 'stale':
                r['units_sha256'] = 'stale'
            elif change == 'overlap':
                r['units'][2]['start_line'] = 2
            else:
                r['units'].pop()
            self.write('50-edited/reader-unit-rendering.json', r)
            self.assertTrue(validate(self.root, True))

    def test_legacy_is_not_silently_migrated(self):
        self.write('book.json', {'delivery_mode': 'ordinary_reader', 'workflow_schema_version': '1.9'})
        self.assertEqual(validate(self.root), [])

    def test_110_keeps_old_integrity_gates(self):
        from validate_integrity import validate as integrity, validate_source
        self.assertTrue(validate_source(self.root))
        errors = integrity(self.root)
        self.assertTrue(any('edition scope' in e for e in errors))
        self.assertTrue(any('acceptance-policy-lock' in e for e in errors))

    def test_cannot_hide_all_units_from_publication(self):
        for unit in self.data['units']:
            unit['destination'] = 'evidence_only'
        self.save()
        self.render['units_sha256'] = digest(self.root / '50-edited/reader-units.json')
        self.render['units'] = []
        self.write('50-edited/reader-unit-rendering.json', self.render)
        self.assertTrue(any('locked edition scope' in e for e in validate(self.root, True)))

    def test_invalid_json_shapes_return_failure(self):
        self.write('50-edited/reader-units.json', [])
        self.assertTrue(validate(self.root))
        self.save()
        self.write('50-edited/reader-unit-rendering.json', [])
        self.assertTrue(validate(self.root, True))

    def test_complete_110_integrity_and_policy_binding(self):
        from test_integrity_v19 import fixture
        from validate_integrity import validate as integrity, validator_paths
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            def write(name, value):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(json.dumps(value), encoding='utf-8')
            write('book.json', {'workflow_schema_version': '1.10', 'delivery_mode': 'ordinary_reader'})
            write('run-state.json', {'stages': {'reader_units_built': {'status': 'passed'}}})
            transcript = '50-edited/review-history/full-passes/pass-1.md'
            ev = {'file': transcript, 'sha256': digest(root / transcript), 'reason': 'Synthetic structure test'}
            units = {'schema_version': '1.0', 'status': 'reviewed', 'source_sha256': digest(root / '20-source/blocks.jsonl'),
                     'review_evidence': ev, 'continuations': [], 'units': [
                         dict(unit_id='H', kind='heading', source_blocks=['P000001-B001'], source_pages=[1], destination='final_reader', decision_evidence=ev),
                         dict(unit_id='M', kind='main_text', source_blocks=['P000001-B002'], source_pages=[1], destination='final_reader', decision_evidence=ev)]}
            write('50-edited/reader-units.json', units)
            write('50-edited/reader-unit-rendering.json', {'units_sha256': digest(root / '50-edited/reader-units.json'),
                'manuscript_sha256': digest(root / '50-edited/modern-reading.md'), 'units': [
                    dict(unit_id='H', start_line=1, end_line=4, quote='《葬经》'),
                    dict(unit_id='M', start_line=5, end_line=7, quote='古人所说的葬，就是妥善收藏。')]})
            lock = {'policy_version': '1.10', 'edition_scope_sha256': digest(root / '10-diagnosis/edition-scope.json'),
                    'validators': {name: digest(path) for name, path in validator_paths().items()}}
            write('90-audit/acceptance-policy-lock.json', lock)
            self.assertEqual(integrity(root), [])
            lock['validators']['controller/validate_reader_units.py'] = 'changed'
            write('90-audit/acceptance-policy-lock.json', lock)
            self.assertTrue(any('acceptance policy changed' in e for e in integrity(root)))


if __name__ == '__main__':
    unittest.main()
