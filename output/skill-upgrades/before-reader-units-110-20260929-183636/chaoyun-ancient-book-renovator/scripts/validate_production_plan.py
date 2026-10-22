"""Read-only workflow 1.8 dependency checks, not semantic certification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_BINDINGS = {
    '20-source/blocks.jsonl', '30-normalized/blocks.jsonl',
    '40-modernized/book-understanding.md', '50-edited/editorial-plan.md',
    '50-edited/sample/reader-sample.md',
}
FIGURE_TYPES = {'figure', 'table', 'diagram', 'map', 'image', 'chart', 'figure/table'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('evidence path must be workspace-relative')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'missing, empty or escaping evidence: {relative}')
    return path


def obj(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'expected object: {path.name}')
    return value


def validate_session(root, session, require_figures=False, expected_manuscript=None):
    """Return errors and task IDs; existence/text matching cannot prove independence."""
    errors, ids = [], set()
    try:
        if not isinstance(session, dict):
            raise ValueError('actual reading session is required')
        if session.get('status') != 'passed':
            errors.append('reading session is not accepted')
        producer, reviewer = session.get('producer_execution_id'), session.get('reviewer_execution_id')
        if not isinstance(producer, str) or not producer.strip() or not isinstance(reviewer, str) or not reviewer.strip() or producer == reviewer:
            errors.append('reading session requires distinct actual execution references')
        if session.get('reviewer_kind') not in {'model', 'human'}:
            errors.append('reading session must disclose model or human reviewer')
        manuscript = local(root, session.get('manuscript_file'))
        if sha(manuscript) != session.get('manuscript_sha256'):
            errors.append('reading session manuscript is stale')
        if expected_manuscript is not None and manuscript.read_bytes() != expected_manuscript.read_bytes():
            errors.append('reading session does not describe the accepted manuscript')
        manuscript_lines = len(manuscript.read_text(encoding='utf-8').splitlines())
        data, paths = {}, []
        for name in ('tasks', 'responses', 'assessments', 'provenance'):
            path = local(root, session.get(name + '_file'))
            paths.append(path)
            if sha(path) != session.get(name + '_sha256'):
                errors.append(f'reading {name} evidence is stale')
            data[name] = path.read_text(encoding='utf-8')
        if len(set(paths)) != 4:
            errors.append('reading tasks, responses, assessments and provenance require distinct files')
        tasks, responses, assessments = [json.loads(data[k]) for k in ('tasks', 'responses', 'assessments')]
        for rows in (tasks, responses, assessments):
            if not isinstance(rows, list) or not rows or any(not isinstance(x, dict) for x in rows):
                raise ValueError('reading records must be nonempty arrays of objects')
        task_ids = [x.get('id') for x in tasks]
        if any(not isinstance(x, str) or not x.strip() for x in task_ids) or len(set(task_ids)) != len(task_ids):
            raise ValueError('reading task IDs must be nonempty and unique')
        ids = set(task_ids)
        for name, rows in (('responses', responses), ('assessments', assessments)):
            keys = [x.get('task_id') for x in rows]
            if any(not isinstance(x, str) for x in keys) or len(keys) != len(ids) or set(keys) != ids:
                errors.append(f'reading {name} must cover each task exactly once')
        kinds = set()
        for task in tasks:
            if 'start_line' in task or 'end_line' in task:
                start, end = task.get('start_line'), task.get('end_line')
                if type(start) is not int or type(end) is not int or not 1 <= start <= end <= manuscript_lines:
                    errors.append('reading task has invalid manuscript scope')
            if 'terms' in task and (not isinstance(task['terms'], list) or any(not isinstance(t, str) or not t.strip() for t in task['terms'])):
                errors.append('reading task terms must be a list of concept names')
            kind = task.get('kind')
            if kind not in {'main_point', 'application', 'distinction', 'figure', 'other'}:
                errors.append('invalid reading task kind')
            else:
                kinds.add(kind)
            question = task.get('question')
            if not isinstance(question, str) or not question.strip() or question not in data['provenance']:
                errors.append('reading question missing from actual provenance')
            if any(key in task for key in ('answer', 'expected_answer', 'answer_key')):
                errors.append('reading task exposes an answer key')
        required = {'main_point', 'application', 'distinction'} | ({'figure'} if require_figures else set())
        exemptions = session.get('task_exemptions') or {}
        if not isinstance(exemptions, dict):
            raise ValueError('task_exemptions must be an object')
        for kind in required - kinds:
            if not isinstance(exemptions.get(kind), str) or not exemptions[kind].strip():
                errors.append(f'reading task missing {kind}; source-grounded exemption required')
        answers = []
        for response in responses:
            answer = response.get('answer')
            if not isinstance(answer, str) or not answer.strip() or answer not in data['provenance']:
                errors.append('actual reader answer missing from provenance')
            else:
                answers.append(answer.strip())
        if len(answers) > 1 and len(set(answers)) == 1:
            errors.append('identical answers across reading tasks cannot evidence comprehension')
        for assessment in assessments:
            if assessment.get('status') != 'passed' or not isinstance(assessment.get('evidence'), str) or not assessment['evidence'].strip():
                errors.append('reading task lacks a passing source-based assessment')
        if any(not isinstance(ref, str) or ref not in data['provenance'] for ref in (producer, reviewer)):
            errors.append('execution references absent from reading provenance')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f'invalid reading session: {exc}')
    return errors, ids


def validate(root):
    errors = []
    try:
        book = obj(root / 'book.json')
        if book.get('delivery_mode') in {'source_comparison', 'evidence_archive'}:
            return []
        if book.get('delivery_mode') != 'ordinary_reader':
            return ['production requires explicit delivery_mode']
        if book.get('workflow_schema_version') not in {'1.7', '1.8', '1.9'}:
            errors.append('ordinary-reader production requires workflow 1.7, 1.8 or 1.9; preserve legacy evidence and perform fresh design/sample review')
        plan = obj(local(root, '50-edited/production-plan.json'))
        if plan.get('schema_version') != '1.0':
            errors.append('production-plan schema must be 1.0')
        bindings = plan.get('bindings')
        if not isinstance(bindings, dict) or not REQUIRED_BINDINGS.issubset(bindings):
            raise ValueError('production-plan is missing required source/design/sample bindings')
        for name, digest in bindings.items():
            if sha(local(root, name)) != digest:
                errors.append(f'production dependency changed: {name}; review impacted work, do not refresh hashes alone')
        source = [json.loads(line) for line in (root / '20-source/blocks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        if not source or any(not isinstance(x, dict) for x in source):
            raise ValueError('source records must be nonempty objects')
        source_ids = {x['block_id'] for x in source}
        selection = plan.get('sample_selection')
        if not isinstance(selection, dict):
            raise ValueError('sample_selection required')
        ids = selection.get('block_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids) or not set(ids).issubset(source_ids):
            errors.append('sample selection requires actual source block IDs')
        for field in ('reason', 'figure_reason'):
            if not isinstance(selection.get(field), str) or not selection[field].strip():
                errors.append(f'sample selection requires {field}')
        if not isinstance(selection.get('covered_difficulties'), list) or not selection['covered_difficulties'] or any(not isinstance(x, str) or not x.strip() for x in selection['covered_difficulties']):
            errors.append('sample selection requires actual covered difficulties')
        if not isinstance(selection.get('deferred_difficulties'), list):
            errors.append('sample selection requires deferred_difficulties list')
        has_figures = any(x.get('block_type') in FIGURE_TYPES and x.get('disposition') not in {'noncontent', 'excluded_with_reason'} for x in source)
        if type(selection.get('figures_applicable')) is not bool or selection['figures_applicable'] != has_figures:
            errors.append('sample figure applicability differs from source inventory')
        if has_figures:
            sample = (root / '50-edited/sample/reader-sample.md').read_text(encoding='utf-8')
            import re
            images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', sample)
            if not images:
                errors.append('figure-bearing book requires an actual figure in the reader sample')
            for target in images:
                target = target.strip().strip('<>')
                path = (root / '50-edited/sample' / target).resolve()
                if not path.is_relative_to(root.resolve()):
                    errors.append('sample image escapes workspace')
                elif path.relative_to(root.resolve()).as_posix() not in bindings:
                    errors.append('sample image must be included in dependency bindings')
        if plan.get('blocking_questions') != []:
            errors.append('production has unresolved central questions or missing question inventory')
        session_errors, _ = validate_session(root, plan.get('sample_review'), has_figures,
                                            root / '50-edited/sample/reader-sample.md')
        errors.extend(session_errors)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f'invalid production prerequisites: {exc}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    errors = validate(args.workspace.resolve())
    print(json.dumps({'valid': not errors, 'scope': 'record integrity, not semantic quality', 'errors': errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
