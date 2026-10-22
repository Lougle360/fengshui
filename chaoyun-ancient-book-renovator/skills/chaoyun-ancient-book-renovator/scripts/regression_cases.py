"""Adversarial fixtures: contract tests, never a semantic quality score."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_regressions(root):
    skills = Path(__file__).resolve().parents[2]
    value = load("reader_value_regression", skills / "chaoyun-reading-editor/scripts/validate_reader_value.py")
    revision = load("reader_revision_regression", skills / "chaoyun-reader-experience-reviser/scripts/validate_reader_revision.py")
    release = load("release_regression", skills / "chaoyun-quality-publisher/scripts/validate_release_binding.py")
    official = root / "60-publication/source·现代白话版.pdf"
    initial = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
    passed = []

    def read(relative):
        return json.loads((root / relative).read_text(encoding="utf-8"))

    def write(relative, obj):
        (root / relative).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def change(relative, mutate):
        data = read(relative)
        mutate(data)
        write(relative, data)

    def ledger(mutate):
        relative = "50-edited/reader-revision-ledger.jsonl"
        rows = [json.loads(line) for line in (root / relative).read_text(encoding="utf-8").splitlines()]
        mutate(rows)
        (root / relative).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding="utf-8")

    def case(name, mutate, check, expected):
        try:
            mutate()
            errors = check()
            if not any(expected in error for error in errors):
                raise AssertionError(f"{name}: expected {expected!r}, got {errors}")
            passed.append(name)
        finally:
            for path, content in initial.items():
                path.write_bytes(content)

    check_value = lambda: value.validate(root)[0]
    check_revision = lambda: revision.validate(root)[0]
    check_release = lambda: release.validate(root, official)
    def check_stage(stage):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(skills / 'chaoyun-ancient-book-renovator/scripts/validate_workspace.py'), str(root), '--stage', stage], capture_output=True, text=True, encoding='utf-8')
        return json.loads(result.stdout)['errors']
    delivery = load('delivery_regression', skills / 'chaoyun-ancient-book-renovator/scripts/validate_delivery.py')
    for check in (check_value, check_revision, check_release):
        if check():
            raise AssertionError(f"positive baseline failed: {check()}")

    case("skeletal-introduction", lambda: (root / '50-edited/modern-reading.md').write_text('# 本书介绍\n仅一句话。\n# 本书术语表\n天地：天空与大地。', encoding='utf-8'), check_value, "is not rendered")
    case("missing-term-explanation", lambda: change('50-edited/reader-aids.json', lambda d: d['glossary']['entries'][0].update(contextual_definition='An explanation absent from the book.')), check_value, "not rendered in its entry")
    case("missing-term-inventory", lambda: (root / '40-modernized/terminology.json').unlink(), check_value, "inventory is missing")
    case("unmapped-blocked-finding", lambda: change('50-edited/reader-review.json', lambda d: d['dimensions']['continuity'].update(verdict='blocked', findings=[{'revision_id':'RR_MISSING','problem':'The body is absent.'}])), check_revision, "no revision event")
    case("missing-dimension-regression", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['dimension_checks'].pop('continuity')), check_revision, "every reader dimension")

    def old_pending(rows):
        old = copy.deepcopy(rows[0])
        old.update(event_id='RRE_OLD', revision_id='RR_OLD', cycle_id='RC0000', status='proposed')
        rows.insert(0, old)
    case("old-cycle-pending", lambda: ledger(old_pending), check_revision, "unresolved revisions")
    case("claimed-but-unapplied-edit", lambda: ledger(lambda rows: rows[0].update(after='A paragraph that was never applied.')), check_revision, "differs from snapshot")
    case("tampered-input-snapshot", lambda: (root / '50-edited/review-history/RC0001/input.md').write_text('changed', encoding='utf-8'), check_revision, "snapshot hash mismatch")
    case("unreviewed-section", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['section_reviews'].pop()), check_revision, "complete manuscript")
    case("stale-section-evidence", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['section_reviews'][0].update(text_sha256='0'*64)), check_revision, "section review text hash")
    case("rejection-without-evidence", lambda: ledger(lambda rows: rows[0].update(status='rejected', rationale='', resolution_review={})), check_revision, "evidenced resolution")
    case("same-production-review-run", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d.update(reviewer_record=d['producer_record'], reviewer_record_sha256=d['producer_record_sha256'])), check_revision, "separate execution")
    case("invented-unit-answer", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['section_reviews'][0].update(plain_answer='An answer the reader never gave.')), check_revision, "actual response")
    case("unrelated-unit-task", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['section_reviews'][0].update(task_ids=['T1'])), check_revision, "scoped to this unit")
    case("invented-glossary-answer", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['glossary_samples'][0].update(answer_quote='An invented concept explanation.')), check_revision, "actual answer_quote")
    case("unrelated-glossary-task", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['glossary_samples'][0].update(task_ids=['T1'])), check_revision, "naming this term")
    case("spliced-execution-record", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['reading_session'].update(reviewer_execution_id='unrelated-run')), check_revision, "execution differs")
    case("missing-final-reader-cut", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d.pop('final_reader_cut')), check_revision, "requires final_reader_cut")
    case("stale-process-edition-binding", lambda: change('50-edited/reader-acceptance-report.json', lambda d: d['final_reader_cut'].update(process_sha256='0'*64)), check_revision, "process snapshot hash mismatch")
    case("template-term-example", lambda: change('50-edited/reader-aids.json', lambda d: d['glossary']['entries'][0].update(usage_example='阅读“天地玄黄”时，应把“天地”按本书语境理解。')), check_value, "instead of an explained example")

    def many_core():
        aids = read('50-edited/reader-aids.json')
        original = aids['glossary']['entries'][0]
        aids['glossary']['entries'] += [dict(original, term=f'核心词{i}') for i in range(10)]
        write('50-edited/reader-aids.json', aids)
    case("eleven-core-terms", many_core, check_revision, "every core term")

    def unconfirmed():
        ledger(lambda rows: rows[0].update(semantic_risk='high', uncertainty_candidate_id='UC000001'))
        (root / '90-audit/uncertainty-adjudication.jsonl').write_text('', encoding='utf-8')
    case("candidate-without-confirmation", unconfirmed, check_revision, "active evidence-backed confirmation")
    case("publication-md-drift", lambda: (root / '60-publication/modern-reading.md').write_text('Changed publication', encoding='utf-8'), check_release, "differs from the reader-accepted")
    case("missing-proof-pages", lambda: change('90-audit/release-binding.json', lambda d: d.update(page_reviews=[])), check_release, "every PDF page")
    case("missing-proof-image", lambda: change('90-audit/release-binding.json', lambda d: d['page_reviews'][0].update(image='90-audit/no-such-image.png')), check_release, "missing or escaping")
    case("stale-pdf-hash", lambda: change('90-audit/release-binding.json', lambda d: d.update(pdf_sha256='0'*64)), check_release, "pdf_sha256 is stale")

    def blank_pdf():
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=1100, height=2000)
        writer.write(str(official))
        change('90-audit/release-binding.json', lambda d: d.update(pdf_sha256=hashlib.sha256(official.read_bytes()).hexdigest()))
    case("blank-pdf-with-updated-hash", blank_pdf, check_release, "PDF text does not cover")

    def pending_proof():
        (root / '90-audit/release-binding.json').unlink()
        command = [sys.executable, '-X', 'utf8', str(skills / 'chaoyun-quality-publisher/scripts/prepare_release_proof.py'), str(root), '--candidate-pdf', str(root / '60-publication/candidates/candidate.pdf')]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise AssertionError(result.stderr)
        frozen = (root / '90-audit/release-binding.json').read_bytes()
        retry = subprocess.run(command, capture_output=True)
        if retry.returncode == 0 or frozen != (root / '90-audit/release-binding.json').read_bytes():
            raise AssertionError('proof retry overwrote an existing manifest')
    case("proof-preparation-does-not-approve", pending_proof, check_release, "lacks passing visual review")

    case('empty-source', lambda: (root / '20-source/blocks.jsonl').write_text('', encoding='utf-8'), lambda: check_stage('source'), 'records must not be empty')
    case('null-modern-text', lambda: change('40-modernized/blocks.jsonl', lambda d: d.update(modern_text=None)), lambda: check_stage('modernized'), 'requires nonempty modern_text')
    case('missing-delivery-mode', lambda: change('book.json', lambda d: d.pop('delivery_mode')), lambda: check_stage('source'), 'explicit delivery_mode')
    case('wrong-physical-page-count', lambda: change('book.json', lambda d: d.update(source_pdf_pages=80)), lambda: check_stage('source'), 'physical PDF page count')
    case('unknown-disposition', lambda: change('20-source/blocks.jsonl', lambda d: d.update(disposition='done')), lambda: check_stage('source'), 'invalid disposition')
    case('stale-fidelity-after-source-edit', lambda: change('20-source/blocks.jsonl', lambda d: d.update(source_text='天地方圆')), lambda: delivery.validate(root), 'stale or missing binding')
    case('missing-source-reader-mapping', lambda: change('90-audit/fidelity-review.json', lambda d: d.update(blocks=[])), lambda: delivery.validate(root), 'every source block')
    case('unreviewed-negation', lambda: change('90-audit/fidelity-review.json', lambda d: d['blocks'][0]['checks'].update(negation='')), lambda: delivery.validate(root), 'negation review')
    case('unfulfilled-reader-outcome', lambda: change('50-edited/delivery-contract.json', lambda d: d['outcomes'][0].update(status='pending')), lambda: delivery.validate(root), 'manuscript evidence and acceptance')

    def keyword_independence():
        change('book.json', lambda d: d.update(target_reader='风水爱好者', edition_label='今读版'))
        (root / '50-edited/editorial-report.json').unlink()
    case('reader-gate-independent-of-title', keyword_independence, lambda: check_stage('publication'), 'requires 50-edited/editorial-report.json')

    def injected_pdf():
        import pymupdf, re
        text = (root / '60-publication/modern-reading.md').read_text(encoding='utf-8')
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.M).replace('这是一个单页测试读本。', '这是一个单页测试读本。但绝对不要使用。')
        with pymupdf.open() as doc:
            page = doc.new_page(width=1100, height=2000)
            page.insert_text((30, 30), text, fontname='china-s', fontsize=10)
            replacement = root / '60-publication/candidates/injected.pdf'
            doc.save(replacement)
        official.write_bytes(replacement.read_bytes())
        change('90-audit/release-binding.json', lambda d: d.update(pdf_sha256=hashlib.sha256(official.read_bytes()).hexdigest()))
    case('extra-negation-in-PDF', injected_pdf, check_release, 'PDF text does not cover')
    if release.prose('-1') == release.prose('1') or release.prose('可以使用。') == release.compact('可以，但绝对不要使用。'):
        raise AssertionError('PDF comparator erased a sign or accepted contradictory added text')

    def try_bad_install():
        original = official.read_bytes()
        candidate = root / '60-publication/candidates/candidate.pdf'
        from pypdf import PdfWriter
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.write(str(candidate))
        installer = skills / 'chaoyun-quality-publisher/scripts/install_official_pdf.py'
        result = subprocess.run([sys.executable, '-X', 'utf8', str(installer), str(root), str(candidate)], capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0 or original != official.read_bytes():
            raise AssertionError('rejected candidate changed the official release')
        return [result.stdout + result.stderr]
    case('failed-candidate-preserves-release', lambda: None, try_bad_install, 'candidate gate failed')

    installer = skills / 'chaoyun-quality-publisher/scripts/install_official_pdf.py'
    result = subprocess.run([sys.executable, '-X', 'utf8', str(installer), str(root), str(root / '60-publication/candidates/candidate.pdf')], capture_output=True, text=True, encoding='utf-8')
    backup = root / '90-audit/release-history' / hashlib.sha256(official.read_bytes()).hexdigest() / official.name
    if result.returncode or not backup.is_file() or backup.read_bytes() != official.read_bytes():
        raise AssertionError(f'accepted install/backup failed: {result.stdout} {result.stderr}')

    # A legitimate zero-edit cycle must remain possible: evidence, not forced rewriting.
    try:
        change('50-edited/reader-review.json', lambda d: d.update(
            input_snapshot='50-edited/review-history/RC0001/output.md',
            input_sha256=hashlib.sha256((root / '50-edited/modern-reading.md').read_bytes()).hexdigest(),
            dimensions={key: {'verdict': 'passed', 'findings': []} for key in d['dimensions']}, blocking_issues=[]))
        (root / '50-edited/reader-revision-ledger.jsonl').write_text('', encoding='utf-8')
        change('50-edited/reader-acceptance-report.json', lambda d: d.update(counts={key: 0 for key in d['counts']}))
        if check_revision():
            raise AssertionError(f'zero-edit acceptance failed: {check_revision()}')
    finally:
        for path, content in initial.items():
            path.write_bytes(content)
    print(f"Adversarial contract cases passed: {len(passed)}")
    print('Positive zero-edit acceptance passed')
    navigation_tests(release)


def navigation_tests(release):
    import pymupdf
    with tempfile.TemporaryDirectory(prefix='chaoyun-navigation-') as folder:
        root = Path(folder)
        for relative in ['50-edited', '60-publication', '90-audit']:
            (root / relative).mkdir()
        text = '\n\n'.join(f'# Chapter {number}\n\nText {number}.' for number in range(1, 7))
        for relative in ['50-edited/modern-reading.md', '60-publication/modern-reading.md']:
            (root / relative).write_text(text, encoding='utf-8')
        pdf = root / '60-publication/book.pdf'
        with pymupdf.open() as doc:
            toc_page = doc.new_page()
            for number in range(1, 7):
                page = doc.new_page()
                page.insert_text((30, 40), f'Chapter {number}\n\nText {number}.', fontsize=12)
            toc_page = doc[0]
            for number in range(1, 7):
                y = 40 + (number - 1) * 22
                toc_page.insert_text((30, y), f'Chapter {number}', fontsize=12)
                toc_page.insert_link({'kind': pymupdf.LINK_GOTO, 'from': pymupdf.Rect(25, y - 14, 150, y + 4),
                                      'page': number, 'to': pymupdf.Point(0, 0)})
            for number, page in enumerate(doc, 1):
                page.insert_text((30, page.rect.height - 20), str(number), fontsize=12)
            doc.set_toc([[1, f'Chapter {number}', number + 1] for number in range(1, 7)])
            doc.save(pdf)
        reviews = []
        with pymupdf.open(pdf) as doc:
            for number, page in enumerate(doc, 1):
                image = root / f'90-audit/{number}.png'
                page.get_pixmap().save(image)
                reviews.append({'page': number, 'image': image.relative_to(root).as_posix(), 'status': 'passed', 'issues': [], 'reviewer': 'fixture', 'evidence': 'Synthetic navigation test.',
                                'furniture': [{'kind': 'page_number', 'text': str(number), 'bbox': [20, page.rect.height - 40, 70, page.rect.height - 5]}]})
        binding = {'manuscript_sha256': release.sha(root / '50-edited/modern-reading.md'),
                   'markdown_sha256': release.sha(root / '60-publication/modern-reading.md'), 'pdf_sha256': release.sha(pdf), 'assets': {},
                   'page_reviews': reviews,
                   'navigation': [{'heading': f'Chapter {n}', 'target_page': n + 1, 'link_page': 1, 'status': 'passed', 'evidence': 'Synthetic link test.'} for n in range(1, 7)]}
        path = root / '90-audit/release-binding.json'
        path.write_text(json.dumps(binding), encoding='utf-8')
        errors = release.validate(root, pdf)
        if errors:
            raise AssertionError(f'positive navigation failed: {errors}')
        binding['navigation'][0]['target_page'] = 3
        path.write_text(json.dumps(binding), encoding='utf-8')
        if not any('navigation target' in error for error in release.validate(root, pdf)):
            raise AssertionError('wrong navigation target accepted')
        binding['navigation'] = []
        path.write_text(json.dumps(binding), encoding='utf-8')
        if not any('navigation evidence' in error for error in release.validate(root, pdf)):
            raise AssertionError('missing navigation inventory accepted')
        binding['page_reviews'][0]['furniture'][0]['bbox'] = [0, 0, 400, 600]
        path.write_text(json.dumps(binding), encoding='utf-8')
        if not any('invalid page furniture' in error for error in release.validate(root, pdf)):
            raise AssertionError('body-region furniture exclusion accepted')
    print('Navigation/page-number tests passed: 1 positive and 3 negative')
