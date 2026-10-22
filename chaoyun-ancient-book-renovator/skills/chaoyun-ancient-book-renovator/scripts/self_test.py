#!/usr/bin/env python3
"""Exercise Chaoyun initialization, adjudication, grading, migration, and publication gates."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import re
from pathlib import Path

from pypdf import PdfWriter
import pymupdf


HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
PUBLISH_AUDIT = SKILLS / "chaoyun-quality-publisher" / "scripts" / "audit_publication.py"
INSTALL_PDF = SKILLS / "chaoyun-quality-publisher" / "scripts" / "install_official_pdf.py"
PROJECT_OPEN = SKILLS / "chaoyun-uncertainty-adjudicator" / "scripts" / "project_open_items.py"
MIGRATE = SKILLS / "chaoyun-uncertainty-adjudicator" / "scripts" / "migrate_legacy_ledger.py"
sys.path.insert(0, str(SKILLS / "chaoyun-reader-experience-reviser" / "scripts"))
from reader_evidence import sections
sys.path.insert(0, str(SKILLS / 'chaoyun-uncertainty-adjudicator/scripts'))
from closure_evidence import SCOPES, sha, closure_digest


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", *args], text=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != expect:
        raise AssertionError(f"expected {expect}, got {result.returncode}: {result.stdout}\n{result.stderr}")
    return result


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def fixture_closure(workspace: Path, decision: dict) -> None:
    """Synthetic evidence to test structure; this is not a real adjudication."""
    reference = {'path': '20-source/blocks.jsonl', 'sha256': sha(workspace / '20-source/blocks.jsonl'), 'quote': '天地玄黄'}
    closure = {'action': 'confirmed_unchanged', 'producer': 'fixture-producer', 'producer_run_id': 'fixture-production',
               'evidence': [reference], 'impact_review': {scope: {'status': 'not_applicable', 'reason': 'Synthetic source-stage fixture; publication is independently rechecked.'} for scope in SCOPES}}
    closure['impact_review']['source'] = {'status': 'checked', 'reason': 'Synthetic source fixture.', 'artifacts': [reference]}
    decision['closure'] = closure
    record = {'reviewer': 'fixture-reviewer', 'run_id': 'fixture-review-' + decision['adjudication_id'],
              'adjudication_id': decision['adjudication_id'], 'status': 'passed',
              'fidelity_evidence': 'Synthetic test only.', 'reader_evidence': 'Synthetic test only.',
              'closure_sha256': closure_digest(decision)}
    relative = '90-audit/closure-' + decision['adjudication_id'] + '.json'
    write_json(workspace / relative, record)
    closure['review_record'] = {'path': relative, 'sha256': sha(workspace / relative)}
    decision['closure'] = closure


def fixture_final_uncertainty(workspace: Path, decisions: list[dict]) -> None:
    report = {
        'producer': 'fixture-producer', 'producer_run_id': 'fixture-production', 'reviewer': 'fixture-reviewer',
        'input_hashes': {path: sha(workspace / path) for path in ['90-audit/uncertainty-candidates.jsonl', '90-audit/uncertainty-adjudication.jsonl', '50-edited/modern-reading.md']},
        'items': [{'adjudication_id': row['adjudication_id'], 'result': 'disclosed_unresolved' if row['status'] == 'open_material' else 'verified',
                   'reader_affected': True, 'quote': '天地玄黄', 'evidence': 'Synthetic final-manuscript check.'}
                  for row in decisions if row.get('active', True)]}
    path = workspace / '90-audit/final-uncertainty-execution.json'
    write_json(path, {'reviewer': 'fixture-reviewer', 'run_id': 'fixture-final-review', 'status': 'passed',
                     'final_review_sha256': hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()})
    report['review_record'] = {'path': path.relative_to(workspace).as_posix(), 'sha256': sha(path)}
    write_json(workspace / '90-audit/uncertainty-release-review.json', report)


def fixture_pilot(workspace: Path):
    report = {'kind': 'chapter_trial', 'workflow_version': '1.6',
              'source_pdf_sha256': json.loads((workspace / '00-intake/source-manifest.json').read_text(encoding='utf-8'))['source_sha256'],
              'producer': 'fixture-producer', 'producer_run_id': 'fixture-production',
              'selection_reason': 'Synthetic single-block fixture.', 'risk_coverage': ['glyph'],
              'limitations': 'Synthetic test data; NOT a completed real-book benchmark.',
              'before': {'path': '50-edited/review-history/RC0001/input.md', 'sha256': sha(workspace / '50-edited/review-history/RC0001/input.md'), 'quote': '天地玄黄'},
              'after': {'path': '50-edited/review-history/RC0001/output.md', 'sha256': sha(workspace / '50-edited/review-history/RC0001/output.md'), 'quote': '天地玄黄'},
              'sample_block_ids': ['P000001-B001'], 'candidate_ids': ['UC000001'],
              'cases': [{'candidate_id': 'UC000001', 'result': 'verified', 'evidence': 'Synthetic fixture only.'}],
              'new_errors': [], 'status': 'passed', 'elapsed_seconds': 0, 'cost': 0, 'cost_unit': 'synthetic-test'}
    record = {'reviewer': 'fixture-blind-reviewer', 'run_id': 'fixture-blind-run', 'expected_answers_withheld': True,
              'findings': 'Synthetic test record, not actual reader feedback.',
              'pilot_sha256': hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()}
    path = workspace / '90-audit/pilot-execution.json'
    write_json(path, record)
    report['review_record'] = {'path': '90-audit/pilot-execution.json', 'sha256': sha(path)}
    write_json(workspace / '90-audit/pilot-review.json', report)


def make_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as handle:
        writer.write(handle)


def set_accepted_stages(workspace: Path) -> None:
    state_path = workspace / "run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for stage in ("intake", "diagnosis", "source", "source_adjudicated", "normalized", "book_understood", "reader_designed", "sample_accepted", "modernized", "edited", "reader_revised", "final_adjudicated"):
        state["stages"][stage]["status"] = "passed"
    write_json(state_path, state)


def quality_report(workspace: Path, grade: str, counts: dict[str, int]) -> None:
    write_json(
        workspace / "90-audit/quality-report.json",
        {
            "grade": grade,
            "source_pages": 1,
            "semantic_audit": {"passed": True, "page_level_visual_coverage": 1},
            "structural_audit": {"passed": True},
            "uncertainty_summary": counts,
            "publication": {"pdf": "60-publication/source·现代白话版.pdf", "pdf_pages": 1, "rendered_pages_inspected": 1},
        },
    )


def editorial_report(workspace: Path, high_open: int = 0) -> None:
    write_json(
        workspace / "50-edited/editorial-report.json",
        {
            "schema_version": "1.0",
            "book_nature": {
                "summary": "A compact classical fixture used to test a modern reading edition.",
                "attribution_basis": "The fixture makes no authorship claim beyond its recorded source.",
                "compilation_status": "single_work",
            },
            "source_toc": {
                "status": "source_absent_with_reason", "source_pages": [], "entry_count": 0,
                "physical_page_mapping_verified": True,
                "reason": "The one-page fixture has no printed contents.",
            },
            "reader_structure": {"entry_count": 1, "editor_additions_labeled": True},
            "glossary": {
                "status": "completed", "entry_count": 1,
                "entries_with_first_occurrence": 1, "reason": None,
                "core_entry_count": 1, "reader_review_sampled": 1,
            },
            "reader_value": {
                "introduction_sections": 9, "review_dimensions": 9,
                "revision_cycle": "RC0001", "applied_revisions": 1,
                "producer": "fixture-reviser", "reviewer": "fixture-regression-reviewer",
                "status": "passed",
            },
            "figures": {
                "content_figures_total": 0, "content_figures_rendered": 0,
                "content_figures_guided": 0,
            },
            "semantic_review": {
                "status": "blocked_by_high_impact_open_items" if high_open else "passed",
                "high_impact_open": high_open,
            },
            "pipeline_language_scan": {"forbidden_matches": 0},
        },
    )


def reader_aids(workspace: Path) -> None:
    sections = {
        "what_this_book_is": "A one-page classical fixture.",
        "who_should_read": "Readers testing an ordinary-reader edition.",
        "reader_value": "It demonstrates traceable explanation.",
        "contents_and_structure": "One source block followed by its explanation.",
        "distinctive_features": "A deliberately compact evidence fixture.",
        "historical_and_textual_context": "No authorship claim is made beyond the recorded source.",
        "how_to_read": "Read the source concept, then its modern explanation.",
        "limitations_and_cautions": "It is a test fixture, not a historical edition.",
        "edition_method": "The source is retained and a labeled modern explanation is added.",
    }
    write_json(
        workspace / "50-edited/reader-aids.json",
        {
            "schema_version": "1.0", "target_reader": "modern ordinary reader",
            "introduction": {
                "markdown_heading": "本书介绍", "sections": sections,
                "evidence": [{"claim": "The fixture contains one classical block.",
                              "block_ids": ["P000001-B001"], "source_pages": [1], "editorial_sources": []}],
            },
            "glossary": {
                "markdown_heading": "本书术语表",
                "entries": [{
                    "term": "天地", "tier": "core", "aliases": [],
                    "plain_definition": "The sky and the earth considered together.",
                    "contextual_definition": "This fixture uses the pair to open its account of the world.",
                    "first_occurrence": {"page_id": "P000001", "block_id": "P000001-B001",
                                         "source_page": 1, "quote": "天地玄黄"},
                    "usage_example": "Read 天地 as the paired frame of the sentence.",
                    "related_terms": ["玄黄"], "common_confusions": "It is a pair, not one place name.",
                    "confidence": "confirmed",
                }],
                "excluded_inventory_terms": [],
            },
        },
    )


def reader_revision(workspace: Path) -> None:
    from test_reader_production import fixture_plan, fixture_session
    fixture_plan(workspace)
    reading_session = fixture_session(workspace, '50-edited/modern-reading.md')
    dimensions = {
        name: {"verdict": "passed", "findings": []}
        for name in (
            "introduction_promise", "prerequisites", "navigation", "continuity", "terminology",
            "examples_and_figures", "redundancy_and_pacing", "source_editor_trust", "closure_and_lookup",
        )
    }
    dimensions["introduction_promise"] = {
        "verdict": "needs_revision", "findings": [{"revision_id": "RR000001", "problem": "The draft lacked a plain opening sentence."}],
    }
    markdown = workspace / "50-edited/modern-reading.md"
    output = markdown.read_text(encoding="utf-8")
    added = "这是一个单页测试读本。\n\n"
    original = output.replace(added, "", 1)
    frozen = workspace / "50-edited/review-history/RC0001"
    frozen.mkdir(parents=True, exist_ok=True)
    (frozen / "input.md").write_text(original, encoding="utf-8")
    (frozen / "output.md").write_text(output, encoding="utf-8")
    input_hash = hashlib.sha256((frozen / "input.md").read_bytes()).hexdigest()
    output_hash = hashlib.sha256(markdown.read_bytes()).hexdigest()
    execution = {}
    for role, actor in (("producer", "fixture-reviser"), ("reviewer", "fixture-regression-reviewer")):
        path = frozen / (role + ".json")
        write_json(path, {"actor": actor, "run_id": role + "-fixture-run", "output_sha256": output_hash})
        execution[role + "_record"] = path.relative_to(workspace).as_posix()
        execution[role + "_record_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(
        workspace / "50-edited/reader-review.json",
        {
            "schema_version": "1.2", "cycle_id": "RC0001", "mode": "manuscript",
            "input_snapshot": "50-edited/review-history/RC0001/input.md",
            "input_sha256": input_hash,
            "target_reader": "modern ordinary reader", "reviewer": "fixture-reader-auditor",
            "dimensions": dimensions,
            "glossary_samples": [{"term": "天地", "plain_enough": True, "context_specific": True,
                                  "example_helpful": True, "issue": None}],
            "blocking_issues": ["RR000001"],
        },
    )
    write_jsonl(workspace / "50-edited/reader-revision-ledger.jsonl", [{
        "schema_version": "1.0", "event_id": "RRE000001", "revision_id": "RR000001",
        "cycle_id": "RC0001", "operation": "add",
        "reader_problem": "The draft lacked a plain opening sentence.",
        "block_ids": ["P000001-B001"], "section": "本书介绍", "before": "",
        "after": added, "preservation": None,
        "start_offset": len("# 本书介绍\n\n"), "end_offset": len("# 本书介绍\n\n"),
        "input_snapshot": "50-edited/review-history/RC0001/input.md", "input_sha256": input_hash,
        "output_snapshot": "50-edited/review-history/RC0001/output.md", "output_sha256": output_hash,
        "resolution_review": {"reviewer": "fixture-regression-reviewer", "status": "passed", "evidence": "The opening sentence states the fixture's scope."},
        "evidence": ["P000001-B001"], "semantic_risk": "low",
        "uncertainty_candidate_id": None, "status": "applied",
        "rationale": "Adds a plain reader orientation without changing the source claim.",
    }])
    write_json(
        workspace / "50-edited/reader-acceptance-report.json",
        {
            "schema_version": "1.2", "cycle_id": "RC0001", "mode": "manuscript",
            "reading_session": reading_session,
            **execution,
            "dimension_checks": {name: {"status": "passed", "evidence": "Fixture check only; not a real reader judgment."} for name in dimensions},
            "section_reviews": [{
                "start_line": start, "end_line": end,
                "text_sha256": hashlib.sha256("\n".join(output.splitlines()[start-1:end]).encode("utf-8")).hexdigest(),
                "quote": output.splitlines()[start-1], "reader_question": "What does this fixture section show?",
                "plain_answer": f"Synthetic fixture section at line {start}.", "prerequisites": "No specialist knowledge is assumed in this fixture.",
                "comprehension_evidence": f"Synthetic fixture only, unit {start}-{end}; not semantic acceptance.",
                "task_ids": [f"U{start}"],
                "block_ids": ["P000001-B001"], "status": "passed", "remaining_obstacles": [],
            } for start, end in sections(output)],
            "glossary_samples": [{"term": "天地", "plain_enough": True, "context_specific": True,
                                  "example_helpful": True, "issue": None, "quote": "天空与大地", "evidence": "Fixture glossary explanation is present.", "task_ids": ["T2", "T3"], "answer_quote": "The pair opens a sentence about the world."}],
            "producer": "fixture-reviser", "reviewer": "fixture-regression-reviewer", "status": "passed",
            "output_sha256": hashlib.sha256(markdown.read_bytes()).hexdigest(),
            "final_reader_cut": {
                "status": "passed", "rendering_profile": "compact_final_reader",
                "process_snapshot": "50-edited/review-history/RC0001/input.md",
                "process_sha256": input_hash, "output_sha256": output_hash,
                "checks": {name: {"status": "passed", "evidence": "Synthetic contract fixture only."} for name in (
                    "ai_authored_material", "guide_material_removed", "chapter_completeness",
                    "terminology_plainness", "figure_truthfulness", "pipeline_language_absent",
                )},
            },
            "regression_review": "passed", "blocking_issues": [],
            "counts": {"add": 1, "delete_from_reading_path": 0, "reorganize": 0, "rewrite": 0},
        },
    )


def rendered_reader(workspace: Path) -> str:
    aids = json.loads((workspace / "50-edited/reader-aids.json").read_text(encoding="utf-8"))
    parts = ["# 本书介绍", "这是一个单页测试读本。", *aids["introduction"]["sections"].values(), "# 正文", "<!-- source:P000001-B001 -->", "天地玄黄。天是玄色的，地是黄色的。", "# 本书术语表"]
    for entry in aids["glossary"]["entries"]:
        parts += ["## " + entry["term"], "天空与大地。", entry["plain_definition"], entry["contextual_definition"], entry["usage_example"], entry["common_confusions"], "、".join(entry["related_terms"])]
    return "\n\n".join(parts) + "\n"


def release_fixture(workspace: Path, pdf: Path) -> None:
    """Real rendering for mechanical tests, explicitly not a reader-quality benchmark."""
    text = (workspace / "60-publication/modern-reading.md").read_text(encoding="utf-8")
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    with pymupdf.open() as doc:
        page = doc.new_page(width=1100, height=2000)
        page.insert_text((30, 30), re.sub(r'^#{1,6}\s+', '', text, flags=re.M), fontname="china-s", fontsize=10)
        doc.save(pdf)
        proof = workspace / "90-audit/fixture-page.png"
        page.get_pixmap(matrix=pymupdf.Matrix(1, 1), colorspace=pymupdf.csRGB, alpha=False).save(proof)
    write_json(workspace / "90-audit/release-binding.json", {
        "manuscript_sha256": hashlib.sha256((workspace / "50-edited/modern-reading.md").read_bytes()).hexdigest(),
        "markdown_sha256": hashlib.sha256((workspace / "60-publication/modern-reading.md").read_bytes()).hexdigest(),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "assets": {},
        "page_reviews": [{"page": 1, "image": "90-audit/fixture-page.png", "status": "passed", "issues": [],
                          "reviewer": "fixture-proof-reviewer", "evidence": "Synthetic rendering fixture, not human proof approval."}],
    })


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chaoyun-skill-test-") as temporary:
        temp = Path(temporary)
        source = temp / "source.pdf"
        make_pdf(source)
        workspace = temp / "workspace"
        run(str(HERE / "init_workspace.py"), str(source), str(workspace), "--copy-source",
            "--edition-label", "现代白话版", "--target-reader", "现代普通读者")
        if (workspace / "00-intake/source.pdf").read_bytes() != source.read_bytes():
            raise AssertionError("staged source differs from the original")
        set_accepted_stages(workspace)

        book_path = workspace / "book.json"
        book = json.loads(book_path.read_text(encoding="utf-8"))
        # The long-standing suite remains a workflow-1.8 compatibility test.
        # Workflow 1.9 integrity gates have their own adversarial regression test.
        book["workflow_schema_version"] = "1.8"
        book["source_pages"] = 1
        book["source_pdf_pages"] = 1
        write_json(book_path, book)
        book_id = book["book_id"]
        record = {
            "schema_version": "1.0", "book_id": book_id, "page_id": "P000001", "block_id": "P000001-B001",
            "source_page": 1, "block_type": "body", "bbox": [0, 0, 100, 100], "source_image": None,
            "source_text": "天地玄黄", "normalized_text": "天地玄黄", "modern_text": "天是玄色的，地是黄色的。",
            "language": "lzh", "operation": "translate", "disposition": "translated", "confidence": 0.98,
            "evidence": [], "notes": [],
        }
        for relative in ("20-source/blocks.jsonl", "30-normalized/blocks.jsonl", "40-modernized/blocks.jsonl", "50-edited/blocks.jsonl"):
            write_jsonl(workspace / relative, [record])
        write_json(workspace / "40-modernized/terminology.json", {"terms": [{"term": "天地"}]})

        candidates = [{
            "schema_version": "1.2", "candidate_id": "UC000001", "page_id": "P000001",
            "block_id": "P000001-B001", "origin_stage": "source", "kind": "glyph", "excerpt": "玄",
            "reason": "fixture", "source_image": None, "severity": "low",
            "review_cycle": "RC0001", "checkpoint": "source_reconstruction", "created_by": "self-test",
        }]
        decisions = [{
            "schema_version": "1.2", "adjudication_id": "UA000001", "candidate_ids": ["UC000001"],
            "status": "resolved_confirmed", "reader_impact": "none", "active": True, "supersedes": None,
            "review_cycle": "RC0001", "checkpoint": "source_reconstruction",
            "issue_id": None, "page_id": "P000001", "block_id": "P000001-B001",
            "rationale": "The fixture glyph is explicit.", "evidence": [], "before": None, "after": None,
            "reviewed_at": "2026-01-01T00:00:00Z", "reviewer": "self-test",
        }]
        candidate_path = workspace / "90-audit/uncertainty-candidates.jsonl"
        decision_path = workspace / "90-audit/uncertainty-adjudication.jsonl"
        fixture_closure(workspace, decisions[0])
        write_jsonl(candidate_path, candidates)
        write_jsonl(decision_path, decisions)
        run(str(PROJECT_OPEN), str(workspace))
        run(str(PROJECT_OPEN), str(workspace), "--check")

        publication = workspace / "60-publication"
        reader_aids(workspace)
        reader_markdown = rendered_reader(workspace)
        (workspace / "50-edited/modern-reading.md").write_text(reader_markdown, encoding="utf-8")
        (publication / "modern-reading.md").write_text(reader_markdown, encoding="utf-8")
        (workspace / '60-publication/candidates').mkdir()
        candidate_pdf = workspace / "60-publication/candidates/candidate.pdf"
        release_fixture(workspace, candidate_pdf)
        (workspace / "90-audit/quality-report.md").write_text("# Quality report\n", encoding="utf-8")
        counts = {"review_cycles": 1, "candidates": 1, "adjudications": 1, "active_adjudications": 1, "open_material": 0}
        quality_report(workspace, "A", counts)
        reader_aids(workspace)
        reader_revision(workspace)
        editorial_report(workspace)
        fixture_final_uncertainty(workspace, decisions)
        fixture_pilot(workspace)
        write_json(workspace / '50-edited/delivery-contract.json', {
            'schema_version': '1.1', 'rendering_profile': 'compact_final_reader',
            'target_reader': 'Test reader', 'reading_goal': 'Understand the fixture', 'scope': 'One test block',
            'limitations': 'Synthetic test, not a real edition',
            'outcomes': [{'id': 'O1', 'question': 'What does this passage say?', 'answer': 'It names heaven and earth.',
                          'section_heading': '正文', 'quote': '天地玄黄', 'status': 'passed', 'review_evidence': 'Synthetic fixture.'}]})
        run(str(HERE / 'prepare_delivery_review.py'), str(workspace))
        fidelity_path = workspace / '90-audit/fidelity-review.json'
        fidelity = json.loads(fidelity_path.read_text(encoding='utf-8'))
        fidelity.update(producer='fixture-translator', reviewer='fixture-fidelity-reviewer')
        fidelity['blocks'][0].update(status='passed', evidence='Synthetic fixture only.', source_quote='天地玄黄',
                                    modern_quote='天是玄色的，地是黄色的。', reader_anchor='<!-- source:P000001-B001 -->',
                                    checks={key: 'Synthetic fixture, no claim of real semantic review.' for key in fidelity['blocks'][0]['checks']})
        write_json(fidelity_path, fidelity)
        run(str(INSTALL_PDF), str(workspace), str(candidate_pdf), "--expected-pages", "1")
        run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication")
        run(str(PUBLISH_AUDIT), str(workspace))

        from regression_cases import run_regressions
        run_regressions(workspace)
        from uncertainty_cases import run as run_uncertainty_cases
        run_uncertainty_cases(workspace)

        # An ordinary-reader release cannot pass with packaging alone.
        (workspace / "50-edited/editorial-report.json").unlink()
        missing_editorial = run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication", expect=1)
        if "requires 50-edited/editorial-report.json" not in missing_editorial.stdout:
            raise AssertionError("workspace validator did not require editorial evidence")
        missing_editorial_audit = run(str(PUBLISH_AUDIT), str(workspace), expect=1)
        if "requires 50-edited/editorial-report.json" not in missing_editorial_audit.stdout:
            raise AssertionError("publication audit did not require editorial evidence")
        editorial_report(workspace)

        acceptance_path = workspace / "50-edited/reader-acceptance-report.json"
        acceptance_path.unlink()
        missing_reader_acceptance = run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication", expect=1)
        if "reader-acceptance-report.json" not in missing_reader_acceptance.stdout:
            raise AssertionError("workspace validator did not require whole-book reader acceptance")
        reader_revision(workspace)

        # Reader value must be proved item by item, not by self-reported totals.
        aids_path = workspace / "50-edited/reader-aids.json"
        aids = json.loads(aids_path.read_text(encoding="utf-8"))
        aids["glossary"]["entries"][0]["usage_example"] = ""
        write_json(aids_path, aids)
        weak_reader_value = run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication", expect=1)
        if "requires a usage example" not in weak_reader_value.stdout:
            raise AssertionError("workspace validator accepted a shallow core glossary entry")
        reader_aids(workspace)

        # A high-impact open item must make Grade B fail in both gates.
        candidates.append({
            "schema_version": "1.2", "candidate_id": "UC000002", "page_id": "P000001",
            "block_id": "P000001-B001", "origin_stage": "reader_revised", "kind": "missing", "excerpt": "黄",
            "reason": "high-risk fixture", "source_image": None, "severity": "high",
            "review_cycle": "RC0002", "checkpoint": "whole_book_reader_revision", "created_by": "self-test",
        })
        decisions.append({
            "schema_version": "1.2", "adjudication_id": "UA000002", "candidate_ids": ["UC000002"],
            "status": "open_material", "reader_impact": "high", "active": True, "supersedes": None,
            "review_cycle": "RC0002", "checkpoint": "whole_book_reader_revision",
            "issue_id": "UI-UC000002", "page_id": "P000001", "block_id": "P000001-B001",
            "rationale": "A central glyph remains unreadable.", "evidence": [], "before": None, "after": None,
            "reviewed_at": "2026-01-01T00:00:01Z", "reviewer": "self-test",
        })
        write_jsonl(candidate_path, candidates)
        write_jsonl(decision_path, decisions)
        run(str(PROJECT_OPEN), str(workspace))
        quality_report(workspace, "B", {"review_cycles": 2, "candidates": 2, "adjudications": 2, "active_adjudications": 2, "open_material": 1})
        editorial_report(workspace, high_open=1)
        grade_failure = run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication", expect=1)
        if "grade B cannot contain high-impact" not in grade_failure.stdout:
            raise AssertionError("workspace validator did not enforce Grade B uncertainty risk")
        audit_failure = run(str(PUBLISH_AUDIT), str(workspace), expect=1)
        if "grade B cannot contain high-impact" not in audit_failure.stdout:
            raise AssertionError("publication audit did not enforce Grade B uncertainty risk")

        # A later decision supersedes rather than overwrites the first decision.
        decisions[-1]["active"] = False
        decisions.append({
            "schema_version": "1.2", "adjudication_id": "UA000003", "candidate_ids": ["UC000002"],
            "status": "resolved_confirmed", "reader_impact": "none", "active": True, "supersedes": "UA000002",
            "review_cycle": "RC0003", "checkpoint": "prepublication_recheck",
            "issue_id": None, "page_id": "P000001", "block_id": "P000001-B001",
            "rationale": "Independent evidence confirms the glyph.", "evidence": [], "before": None, "after": None,
            "reviewed_at": "2026-01-01T00:00:02Z", "reviewer": "self-test",
        })
        fixture_closure(workspace, decisions[-1])
        write_jsonl(decision_path, decisions)
        fixture_final_uncertainty(workspace, decisions)
        run(str(PROJECT_OPEN), str(workspace))
        quality_report(workspace, "A", {"review_cycles": 3, "candidates": 2, "adjudications": 3, "active_adjudications": 2, "open_material": 0})
        editorial_report(workspace)
        run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication")
        run(str(PUBLISH_AUDIT), str(workspace))

        # Projection drift and cross-stage block drift must still fail.
        write_jsonl(workspace / "90-audit/uncertain-items.jsonl", [{
            "schema_version": "1.1", "issue_id": "UI-BAD", "adjudication_id": "UA-BAD",
            "status": "open", "reader_impact": "high", "note": "invalid fixture",
        }])
        mismatch = run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "publication", expect=1)
        if "not the current open-material projection" not in mismatch.stdout:
            raise AssertionError("validator did not reject an inconsistent open-item projection")
        run(str(PROJECT_OPEN), str(workspace))
        bad = dict(record)
        bad["block_id"] = "P000001-B999"
        write_jsonl(workspace / "30-normalized/blocks.jsonl", [bad])
        failed = run(str(HERE / "validate_workspace.py"), str(workspace), "--stage", "normalized", expect=1)
        if "block identity mismatch" not in failed.stdout:
            raise AssertionError("validator did not report the expected identity mismatch")

        # A legacy ledger is backed up and migrated to stable candidate IDs.
        legacy = temp / "legacy-workspace"
        run(str(HERE / "init_workspace.py"), str(source), str(legacy), "--edition-label", "现代白话版")
        legacy_item = {
            "schema_version": "1.0", "page_id": "P000001", "block_id": "P000001-B001",
            "severity": "medium", "status": "open", "note": "legacy fixture", "source_image": None,
        }
        write_jsonl(legacy / "90-audit/uncertain-items.jsonl", [legacy_item])
        write_jsonl(legacy / "90-audit/uncertainty-adjudication.jsonl", [{
            "schema_version": "1.0", "adjudication_id": "U001", "origin": "original_99",
            "original": legacy_item, "status": "open_material", "rationale": "Still materially uncertain.",
            "reviewed_at": "2026-01-01T00:00:00Z", "reviewer": "legacy-review",
        }])
        migration = run(str(MIGRATE), str(legacy))
        migrated = json.loads(migration.stdout)
        if migrated["candidates"] != 1 or migrated["adjudications"] != 1 or migrated["needs_review"] != 0:
            raise AssertionError("legacy migration did not preserve the adjudicated candidate")
        run(str(PROJECT_OPEN), str(legacy))
        run(str(PROJECT_OPEN), str(legacy), "--check")
        before_retry = {
            path.name: path.read_bytes()
            for path in (
                legacy / "90-audit/uncertainty-candidates.jsonl",
                legacy / "90-audit/uncertainty-adjudication.jsonl",
            )
        }
        run(str(MIGRATE), str(legacy), expect=1)
        after_retry = {
            path.name: path.read_bytes()
            for path in (
                legacy / "90-audit/uncertainty-candidates.jsonl",
                legacy / "90-audit/uncertainty-adjudication.jsonl",
            )
        }
        if before_retry != after_retry:
            raise AssertionError("a refused migration retry changed accepted ledgers")
        if not any((legacy / "90-audit/legacy-uncertainty-migration").iterdir()):
            raise AssertionError("legacy migration did not create a backup")

    print("Chaoyun skill self-test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
