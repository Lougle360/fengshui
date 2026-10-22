"""Content-bound uncertainty closure checks. Evidence presence is not semantic truth."""
import hashlib
import json
from pathlib import Path

SCOPES = {'source', 'translation', 'terminology', 'reader_text', 'figures', 'publication'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closure_digest(row):
    payload = {key: row.get(key) for key in ['adjudication_id', 'candidate_ids', 'status', 'reader_impact', 'page_id', 'block_id', 'rationale', 'supersedes', 'duplicate_of', 'before', 'after', 'review_cycle', 'checkpoint']}
    payload['closure'] = {key: value for key, value in row.get('closure', {}).items() if key != 'review_record'}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def artifact(root, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str) or not ref['path'] or Path(ref['path']).is_absolute():
        raise ValueError('evidence requires a workspace-relative path and hash')
    path = (root / ref['path']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
        raise ValueError('missing, empty or escaping evidence file')
    if ref.get('sha256') != sha(path):
        raise ValueError('stale evidence hash')
    return path


def located(root, ref):
    path = artifact(root, ref)
    if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp'}:
        import pymupdf
        box = ref.get('region')
        image = pymupdf.Pixmap(str(path))
        if not isinstance(box, list) or len(box) != 4 or any(type(n) not in {int, float} for n in box) or not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height):
            raise ValueError('image evidence needs a valid pixel region')
    else:
        quote = ref.get('quote')
        if not isinstance(quote, str) or not quote.strip() or quote not in path.read_text(encoding='utf-8'):
            raise ValueError('evidence quote is missing from its file')
    return path


def validate_closure(root, row):
    errors = []
    label = row.get('adjudication_id')
    closure = row.get('closure')
    if not isinstance(closure, dict):
        return [f'{label} resolved decision requires closure evidence; legacy success is not grandfathered']
    try:
        evidence = closure.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError('closure requires nonempty located evidence')
        for ref in evidence:
            located(root, ref)
        action = closure.get('action')
        if action not in {'corrected', 'confirmed_unchanged', 'noncontent', 'structural', 'duplicate'}:
            raise ValueError('invalid closure action')
        permitted = {'resolved_confirmed': {'corrected', 'confirmed_unchanged'}, 'resolved_noncontent': {'noncontent'},
                     'resolved_structural': {'structural', 'corrected'}, 'resolved_duplicate': {'duplicate'}}
        if action not in permitted.get(row.get('status'), set()):
            raise ValueError('closure action disagrees with decision status')
        if (row.get('before') is not None or row.get('after') is not None) and action != 'corrected':
            raise ValueError('a recorded correction must use replayable corrected closure')
        if action == 'corrected':
            change = closure.get('change') or {}
            before_path = artifact(root, change.get('input'))
            output_path = artifact(root, change.get('output'))
            before_text = before_path.read_text(encoding='utf-8')
            after_text = output_path.read_text(encoding='utf-8')
            start, end = change.get('start_offset'), change.get('end_offset')
            before, after = change.get('before'), change.get('after')
            if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(before_text):
                raise ValueError('correction needs valid exact offsets')
            if not isinstance(before, str) or not isinstance(after, str) or before == after or before_text[start:end] != before or before_text[:start] + after + before_text[end:] != after_text:
                raise ValueError('correction does not replay between snapshots')
            current = artifact(root, change.get('current'))
            if current.read_bytes() != output_path.read_bytes():
                raise ValueError('correction was not applied to its current artifact')
        impacts = closure.get('impact_review') or {}
        if set(impacts) != SCOPES:
            raise ValueError('closure requires all six impact scopes')
        for scope, review in impacts.items():
            if not isinstance(review, dict) or not review.get('reason') or review.get('status') not in {'checked', 'not_applicable'}:
                raise ValueError(f'invalid impact review: {scope}')
            if review['status'] == 'checked':
                if not review.get('artifacts'):
                    raise ValueError(f'checked impact has no artifacts: {scope}')
                for ref in review['artifacts']:
                    located(root, ref)
        record_path = artifact(root, closure.get('review_record'))
        record = json.loads(record_path.read_text(encoding='utf-8'))
        if not closure.get('producer') or not closure.get('producer_run_id') or not record.get('reviewer') or record['reviewer'] == closure['producer']:
            raise ValueError('closure requires a distinct producer and reviewer')
        if not record.get('run_id') or record['run_id'] == closure['producer_run_id'] or record.get('adjudication_id') != label:
            raise ValueError('closure review must be a separate run bound to this decision')
        binding = closure_digest(row)
        if record.get('closure_sha256') != binding or record.get('status') != 'passed' or not record.get('fidelity_evidence') or not record.get('reader_evidence'):
            raise ValueError('closure review is stale or lacks fidelity/reader acceptance')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError) as exc:
        errors.append(f'{label}: {exc}')
    return errors


def validate_pilot(root, candidates):
    """Validate a book-specific trial record. This does not execute or invent a real trial."""
    try:
        report = json.loads((root / '90-audit/pilot-review.json').read_text(encoding='utf-8'))
        intake = json.loads((root / '00-intake/source-manifest.json').read_text(encoding='utf-8'))
        if report.get('source_pdf_sha256') != intake.get('source_sha256') or report.get('kind') != 'chapter_trial':
            raise ValueError('pilot must be a chapter trial bound to this source PDF')
        if report.get('workflow_version') != '1.6':
            raise ValueError('pilot has not validated the current uncertainty workflow')
        for field in ('selection_reason', 'risk_coverage', 'limitations'):
            if not report.get(field):
                raise ValueError(f'pilot requires {field}')
        for field in ('before', 'after'):
            located(root, report.get(field))
        selected = report.get('candidate_ids')
        by_id = {row['candidate_id']: row for row in candidates}
        if not isinstance(selected, list) or len(selected) != len(set(selected)) or not set(selected).issubset(by_id):
            raise ValueError('pilot requires unique existing candidate IDs')
        blocks = {json.loads(line)['block_id'] for line in (root / '20-source/blocks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()}
        sample = report.get('sample_block_ids')
        if not isinstance(sample, list) or not sample or not set(sample).issubset(blocks):
            raise ValueError('pilot requires existing sample block IDs')
        if any(by_id[identifier].get('block_id') not in sample for identifier in selected):
            raise ValueError('pilot candidates must belong to the selected sample')
        cases = report.get('cases') or []
        if len(cases) != len(selected) or {row.get('candidate_id') for row in cases} != set(selected):
            raise ValueError('pilot cases must cover every selected candidate')
        for case in cases:
            if case.get('result') not in {'verified', 'residual'} or not case.get('evidence'):
                raise ValueError('pilot case requires supported verified/residual result')
            if case.get('result') == 'residual' and by_id[case['candidate_id']].get('severity') == 'high':
                raise ValueError('pilot cannot pass a residual high-risk issue')
        if report.get('status') != 'passed' or report.get('new_errors') != []:
            raise ValueError('pilot must have no unaddressed introduced errors')
        for field in ('elapsed_seconds', 'cost'):
            if type(report.get(field)) not in {int, float} or report[field] < 0:
                raise ValueError(f'pilot requires measured nonnegative {field}')
        if not report.get('cost_unit'):
            raise ValueError('pilot cost needs a unit')
        record_path = artifact(root, report.get('review_record'))
        record = json.loads(record_path.read_text(encoding='utf-8'))
        expected = {key: value for key, value in report.items() if key != 'review_record'}
        binding = hashlib.sha256(json.dumps(expected, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        if record.get('pilot_sha256') != binding or not report.get('producer') or not report.get('producer_run_id') or not record.get('reviewer') or record['reviewer'] == report['producer']:
            raise ValueError('pilot needs a separately reviewed, content-bound record')
        if not record.get('run_id') or record['run_id'] == report['producer_run_id'] or record.get('expected_answers_withheld') is not True or not record.get('findings'):
            raise ValueError('pilot lacks independent blind-review evidence')
        return []
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError) as exc:
        return [f'invalid chapter trial: {exc}']


def validate_release_review(root, decisions):
    """A final-manuscript recheck is separate from early source-stage closure."""
    if not decisions:
        return []
    try:
        report = json.loads((root / '90-audit/uncertainty-release-review.json').read_text(encoding='utf-8'))
        for relative in ['90-audit/uncertainty-candidates.jsonl', '90-audit/uncertainty-adjudication.jsonl', '50-edited/modern-reading.md']:
            if report.get('input_hashes', {}).get(relative) != sha(root / relative):
                raise ValueError('final uncertainty review is stale')
        if not report.get('producer') or not report.get('reviewer') or report['producer'] == report['reviewer']:
            raise ValueError('final uncertainty review needs separate producer/reviewer')
        record = json.loads(artifact(root, report.get('review_record')).read_text(encoding='utf-8'))
        payload = {key: value for key, value in report.items() if key != 'review_record'}
        binding = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        if record.get('final_review_sha256') != binding or record.get('reviewer') != report['reviewer'] or not report.get('producer_run_id') or not record.get('run_id') or record['run_id'] == report['producer_run_id'] or record.get('status') != 'passed':
            raise ValueError('final uncertainty review needs a separate content-bound execution record')
        active = {row['adjudication_id']: row for row in decisions if row.get('active', True) is True}
        items = report.get('items') or []
        if len(items) != len(active) or {item.get('adjudication_id') for item in items} != set(active):
            raise ValueError('final review must cover every active adjudication exactly once')
        manuscript = (root / '50-edited/modern-reading.md').read_text(encoding='utf-8')
        for item in items:
            decision = active[item['adjudication_id']]
            expected = 'disclosed_unresolved' if decision['status'] == 'open_material' else 'verified'
            if item.get('result') != expected or not item.get('evidence'):
                raise ValueError('final uncertainty item lacks a valid disposition')
            if decision['status'] == 'open_material' or item.get('reader_affected') is True:
                if not item.get('quote') or item['quote'] not in manuscript:
                    raise ValueError('final reader correction/disclosure is absent from manuscript')
            elif item.get('reader_affected') is not False or not item.get('no_reader_change_reason'):
                raise ValueError('unaffected closure needs explicit no-reader-change reason')
        return []
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return [f'invalid final uncertainty review: {exc}']
