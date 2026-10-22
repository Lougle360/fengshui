"""Synthetic contract fixtures only; never use these as real reader evidence."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from validate_production_plan import REQUIRED_BINDINGS, sha, validate, validate_session

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / 'chaoyun-reader-experience-reviser/scripts'))
from reader_evidence import check_chapters, sections


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def fixture_session(root, manuscript, folder='50-edited/synthetic-session'):
    """Build an explicitly synthetic record for tests, not a real model call."""
    target = root / folder
    target.mkdir(parents=True, exist_ok=True)
    tasks = [{'id': 'T1', 'question': 'What is the fixture about?', 'kind': 'main_point'},
             {'id': 'T2', 'question': 'How is the paired word used?', 'kind': 'application'},
             {'id': 'T3', 'question': 'How do the two referents differ?', 'kind': 'distinction'}]
    answers = [{'task_id': 'T1', 'answer': 'A synthetic explanation of a classical pair.'},
               {'task_id': 'T2', 'answer': 'The pair opens a sentence about the world.'},
               {'task_id': 'T3', 'answer': 'One denotes sky, the other earth.'}]
    tasks[1]['terms'] = ['天地']
    for start, end in sections((root / manuscript).read_text(encoding='utf-8')):
        tasks.append({'id': f'U{start}', 'question': f'What does unit {start}-{end} state?',
                      'kind': 'other', 'start_line': start, 'end_line': end})
        answers.append({'task_id': f'U{start}', 'answer': f'Synthetic fixture section at line {start}.'})
    assessments = [{'task_id': row['id'], 'status': 'passed', 'evidence': 'Synthetic integrity fixture, not semantic acceptance.'} for row in tasks]
    for name, value in [('tasks', tasks), ('responses', answers), ('assessments', assessments)]:
        write(target / (name + '.json'), value)
    (target / 'provenance.txt').write_text('SYNTHETIC TEST ONLY\nproducer-fixture-run\nreviewer-fixture-run\n' +
        '\n'.join(x['question'] for x in tasks) + '\n' + '\n'.join(x['answer'] for x in answers), encoding='utf-8')
    session = {'status': 'passed', 'producer_execution_id': 'producer-fixture-run',
               'reviewer_execution_id': 'reviewer-fixture-run', 'reviewer_kind': 'model',
               'manuscript_file': manuscript, 'manuscript_sha256': sha(root / manuscript)}
    for name in ('tasks', 'responses', 'assessments', 'provenance'):
        path = target / (name + ('.txt' if name == 'provenance' else '.json'))
        session[name + '_file'] = path.relative_to(root).as_posix()
        session[name + '_sha256'] = sha(path)
    return session


def fixture_plan(root):
    """Caller supplies source/normalized records. No real book should call this."""
    for name, value in {
        '40-modernized/book-understanding.md': 'Synthetic understanding fixture: paired sky and earth.',
        '50-edited/editorial-plan.md': 'Synthetic plan: orient, explain a pair, then read the passage.',
        '50-edited/sample/reader-sample.md': 'Synthetic sample: sky and earth are distinct referents.',
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')
    plan = {'schema_version': '1.0', 'bindings': {name: sha(root / name) for name in REQUIRED_BINDINGS},
            'sample_selection': {'reason': 'Synthetic paired-word test.', 'block_ids': ['P000001-B001'],
                                 'covered_difficulties': ['paired meaning'], 'deferred_difficulties': [],
                                 'figures_applicable': False, 'figure_reason': 'Text-only synthetic fixture.'},
            'blocking_questions': [], 'sample_review': fixture_session(root, '50-edited/sample/reader-sample.md', '50-edited/sample/synthetic-session')}
    write(root / '50-edited/production-plan.json', plan)
    return plan


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chaoyun-production-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write(self.root / 'book.json', {'delivery_mode': 'ordinary_reader', 'workflow_schema_version': '1.8'})
        row = {'block_id': 'P000001-B001', 'block_type': 'body', 'source_text': '天地玄黄'}
        for relative in ('20-source/blocks.jsonl', '30-normalized/blocks.jsonl'):
            write(self.root / relative, row)
            # One JSONL line rather than pretty-printed object.
            (self.root / relative).write_text(json.dumps(row), encoding='utf-8')
        self.plan = fixture_plan(self.root)

    def save(self):
        write(self.root / '50-edited/production-plan.json', self.plan)

    def test_valid_integrity_fixture(self):
        self.assertEqual(validate(self.root), [])

    def test_legacy_requires_migration(self):
        write(self.root / 'book.json', {'delivery_mode': 'ordinary_reader', 'workflow_schema_version': '1.6'})
        self.assertTrue(any('1.7, 1.8 or 1.9' in e for e in validate(self.root)))

    def test_archive_exempt(self):
        write(self.root / 'book.json', {'delivery_mode': 'evidence_archive'})
        (self.root / '50-edited/production-plan.json').unlink()
        self.assertEqual(validate(self.root), [])

    def test_dependency_changes_invalidate(self):
        (self.root / '40-modernized/book-understanding.md').write_text('changed', encoding='utf-8')
        self.assertTrue(any('dependency changed' in e for e in validate(self.root)))

    def test_unknown_block(self):
        self.plan['sample_selection']['block_ids'] = ['missing']
        self.save()
        self.assertTrue(any('source block' in e for e in validate(self.root)))

    def test_blocking_question(self):
        self.plan['blocking_questions'] = ['meaning unsettled']
        self.save()
        self.assertTrue(any('unresolved central' in e for e in validate(self.root)))

    def test_paths_cannot_escape(self):
        self.plan['sample_review']['responses_file'] = '../outside.json'
        self.save()
        self.assertTrue(any('escaping evidence' in e for e in validate(self.root)))

    def test_same_execution_rejected(self):
        self.plan['sample_review']['reviewer_execution_id'] = 'producer-fixture-run'
        self.save()
        self.assertTrue(any('distinct actual' in e for e in validate(self.root)))

    def test_session_manuscript_binding(self):
        path = self.root / '50-edited/sample/reader-sample.md'
        path.write_text('different manuscript', encoding='utf-8')
        self.plan['bindings']['50-edited/sample/reader-sample.md'] = sha(path)
        self.save()
        self.assertTrue(any('manuscript is stale' in e for e in validate(self.root)))

    def test_sample_cannot_certify_other_manuscript(self):
        path = self.root / 'other.md'
        path.write_text('a different final edition', encoding='utf-8')
        errors, _ = validate_session(self.root, self.plan['sample_review'], expected_manuscript=path)
        self.assertTrue(any('accepted manuscript' in e for e in errors))

    def test_pending_assessment(self):
        session = self.plan['sample_review']
        path = self.root / session['assessments_file']
        rows = json.loads(path.read_text())
        rows[0]['status'] = 'needs_revision'
        write(path, rows)
        session['assessments_sha256'] = sha(path)
        self.save()
        self.assertTrue(any('passing source-based' in e for e in validate(self.root)))

    def test_missing_actual_answer(self):
        session = self.plan['sample_review']
        path = self.root / session['provenance_file']
        path.write_text('producer-fixture-run reviewer-fixture-run', encoding='utf-8')
        session['provenance_sha256'] = sha(path)
        self.save()
        self.assertTrue(any('answer missing' in e for e in validate(self.root)))

    def test_figure_inventory_not_self_report(self):
        path = self.root / '20-source/blocks.jsonl'
        row = json.loads(path.read_text())
        row['block_type'] = 'figure'
        path.write_text(json.dumps(row), encoding='utf-8')
        self.plan['bindings']['20-source/blocks.jsonl'] = sha(path)
        self.save()
        errors = validate(self.root)
        self.assertTrue(any('applicability differs' in e for e in errors))
        self.assertTrue(any('actual figure' in e for e in errors))

    def test_grouped_units_and_missing_lines(self):
        text = '# One\nFirst.\n## Two\nSecond.'
        row = {'start_line': 1, 'end_line': 4, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'quote': 'First.', 'reader_question': 'How do these parts connect?', 'plain_answer': 'First then second.',
               'prerequisites': 'None.', 'comprehension_evidence': 'Synthetic only.', 'block_ids': ['B1'],
               'status': 'passed', 'remaining_obstacles': []}
        self.assertEqual(check_chapters(text, [row], {'B1'}, grouped=True), [])
        row['end_line'] = 3
        self.assertTrue(any('complete manuscript' in e for e in check_chapters(text, [row], {'B1'}, grouped=True)))

    def test_batch_review_rejected(self):
        text = '# One\nFirst.\n# Two\nSecond.'
        rows = []
        for start, end, bid in [(1, 2, 'B1'), (3, 4, 'B2')]:
            excerpt = '\n'.join(text.splitlines()[start-1:end])
            rows.append({'start_line': start, 'end_line': end, 'text_sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                         'quote': excerpt, 'reader_question': 'What does this say?', 'plain_answer': 'A readable section.',
                         'prerequisites': 'None.', 'comprehension_evidence': 'It is clear.', 'block_ids': [bid],
                         'status': 'passed', 'remaining_obstacles': []})
        self.assertTrue(any('repeated plain_answer' in e for e in check_chapters(text, rows, {'B1', 'B2'}, grouped=True)))


if __name__ == '__main__':
    unittest.main()
