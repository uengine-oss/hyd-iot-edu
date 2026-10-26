"""Source-based scope regression; no LLM calls or extraction consistency claims."""
from copy import deepcopy
from pathlib import Path

import pytest

from procsvc import manual_extraction as extraction
from procsvc.manual_sources import ManualSources
from test_instances import rt
from uuid import uuid4


def proposal_for(tmp_path, text, title, steps):
    source = ManualSources(tmp_path / 'source.sqlite3').save('hyd', 'renamed.md', text.encode())
    def anchor(quote):
        return dict(source_id=source['source_id'], page=1, quote=quote)
    proposal = dict(source_id=source['source_id'],
                    sections=[dict(ref='section-x', title='다른 제목', excerpt=text, anchor=anchor(title))],
                    procedures=[dict(id='SOP-UNRELATED-99', name='다른 이름', section='section-x',
                                     anchor=anchor(title), steps=[dict(order=i, text=s, manual='section-x', anchor=anchor(s))
                                                                 for i, s in enumerate(steps, 1)])],
                    page_reviews=[dict(page=1, note='원문 대조')], warnings=[])
    return source, extraction.validate_proposal(source, proposal)


@pytest.mark.parametrize('segment', [False, True])
def test_hm8_actual_recovery_section_rejected_even_with_renamed_sop(tmp_path, segment):
    text = (Path(__file__).parents[1] / 'it/portal/www/samples/HM-8_cooler-fan-manual.md').read_text(encoding='utf8')
    source, proposal = proposal_for(tmp_path, text, '## HM-8.6 회복 판정',
                                    ['회복하지 않으면 결과 보고에 미달로 적는다.'])
    original = deepcopy(proposal)
    issues = extraction.content_issues(proposal, source, None, segment=segment)
    assert any('독립 실행 근거' in issue and 'sections.excerpt' in issue for issue in issues)
    assert proposal == original  # Never silently delete the evidence/procedure.


@pytest.mark.parametrize('title,body', [
    ('## Q-3 합격 기준', '압력이 기준 이상이면 합격이다. 미달이면 결과에 기록한다.'),
    ('## Z-2 Recovery criteria', 'The action passes if temperature is below 50 C. Otherwise it fails.'),
])
def test_criteria_check_is_not_a_document_id_or_sop_count_answer_key(tmp_path, title, body):
    source, proposal = proposal_for(tmp_path, title+'\n'+body, title, [body])
    with pytest.raises(ValueError, match='독립 실행 근거'):
        extraction.check_criteria_procedures(proposal, source)


@pytest.mark.parametrize('title,steps', [
    ('## 합격 기준 확인 절차', ['압력을 측정한다.', '기준 이상이면 합격으로 기록한다.']),
    ('## 회복 판정과 통보', ['미달이면 담당자에게 통보한다.']),
    ('## 정비 작업', ['밸브를 연다.', '회복하지 않으면 결과 보고에 미달로 적는다.']),
    ('## 보고 절차', ['담당자에게 결과를 보고한다.']),
    ('## 회복 판정', ['밸브를 연다.', '정상 압력이면 성공이다.']),
    ('## 회복 판정', ['미달이면 밸브를 연다.']),
])
def test_real_actions_and_embedded_criteria_remain(tmp_path, title, steps):
    source, proposal = proposal_for(tmp_path, title+'\n'+'\n'.join(steps), title, steps)
    extraction.check_criteria_procedures(proposal, source)
    assert [s['text'] for s in proposal['procedures'][0]['steps']] == steps


def test_prompt_resolves_reporting_conflict():
    assert '독립 업무 여부를 먼저 판단' in extraction.INSTRUCTION
    assert '판정 결과를 보고에 적는 문장은 독립 SOP의 근거가 아닙니다' in extraction.INSTRUCTION
    assert '기존 SOP 안의 확인·판정·기록 단계는 그대로' in extraction.INSTRUCTION


def test_new_scope_contract_does_not_rewrite_old_running_version(tmp_path, monkeypatch):
    title, body = '## 회복 판정', '미달이면 결과 보고에 미달로 적는다.'
    source, proposal = proposal_for(tmp_path, title+'\n'+body, title, [body])
    monkeypatch.setattr(extraction.engine, 'variables', lambda inst: {'manual_source': source})
    form = {'contract': extraction.CONTRACT}
    extraction.validate_result(form, {'proc_def_version': '2.12'}, {'proposal': proposal})
    with pytest.raises(ValueError, match='독립 실행 근거'):
        extraction.validate_result(form, {'proc_def_version': '2.13'}, {'proposal': proposal})


def test_misclassification_returns_to_correction_then_preserves_review_evidence(rt, tmp_path):
    runtime, _ = rt
    title = '## 회복 판정'
    body = '기준 미달이면 결과 보고에 미달로 적는다.'
    source, proposal = proposal_for(tmp_path, title+'\n'+body, title, [body])
    inst = extraction.start(runtime, source, str(uuid4()))
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    runtime.repo.save_task_result(wi['id'], {'proposal': proposal}, final=True)
    runtime.poll_once()
    row = runtime.repo.get_workitem(wi['id'])
    assert row['draft_status'] == 'FB_REQUESTED' and row['output'] is None
    assert '독립 실행 근거' in row['feedback']['text']
    assert extraction.result(runtime, source, inst['proc_inst_id'], None)['preview'] is None
    proposal['procedures'] = []
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    runtime.repo.save_task_result(wi['id'], {'proposal': proposal}, final=True)
    runtime.poll_once()
    preview = extraction.result(runtime, source, inst['proc_inst_id'], None)['preview']
    assert body in preview['sections'][0]['excerpt']
    assert preview['procedures'] == [] and 'reviewed' not in preview
