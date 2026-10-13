"""Business SOP prompt delivery and review contract; CLI output is a test double.

The actual Sol extraction is measured separately by the live PR-07 probe. These
tests check what the model receives, historical scope removal, and preservation
of source-authored numbered steps through the ordinary worker/review lifecycle.
"""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from procsvc import manual_extraction as extraction, manual_review
from procsvc.manual_sources import ManualSources
from test_manual_extraction import _delivered_prompt, rt
from test_worker import _fake_exec, _settings
from worker.runner import Runner


def test_scope_includes_source_business_procedures_and_keeps_installation_boundary():
    instruction = extraction.definition()['activities'][0]['instruction']
    assert extraction.VERSION == '2.4'
    assert '번호가 없는 일반 문장에서도 명시된 업무 실행 절차' in instruction
    assert '구매·발주·입고·재고 관리의 실행 절차도 SOP(procedures)로' in instruction
    assert '문서 제목이나 장 이름이 정비가 아니라는 이유로' in instruction
    assert 'ERP 발주서 작성·공급사 통지·입고 검사·ERP 입고 처리' in instruction
    assert '설치·배선·시운전·반입/양중 장의 독립 설치 절차' in instruction
    assert '정비·업무 절차 안의 시운전 확인·회복 판정·입고 확인 단계는 삭제하지' in instruction
    assert '원문만으로 절차의 업무 성격을 판정할 수 없는 경우에만' in instruction
    assert '고장 유형·원자 조치·공급사 등의 연결을 아직 제안할 수 없어도' in instruction
    assert '조건·금지·역할·순서·수치·승인을 원문 그대로 보존' in instruction
    assert '번호 목록 밖의 승인·선행 조건 문장은 새 단계로 끼워 넣지' in instruction
    assert '근거 없는 조치나 새 단계를 추가하지' in instruction
    assert '운전·점검·정비·고장 조치(트러블슈팅) 장의 절차만' not in instruction
    assert '명시된 정비 절차를 찾되' not in instruction


def test_pr07_business_source_reaches_worker_and_requires_human_review(rt, tmp_path):
    runtime, _ = rt
    path = Path(__file__).resolve().parents[1] / '문서/시스템/참조/수업_문서_원문/PR-07_spare-parts-standard.md'
    archive = ManualSources(tmp_path / 'manual.sqlite3')
    source = archive.save('hyd', path.name, path.read_bytes())
    # Explicit test double, not an LLM result or production extraction fallback.
    proposal = manual_review.proposal(source)
    proposal['page_reviews'] = [dict(page=p['page'], note='구매/재고 업무 절차 검토') for p in source['pages']]
    expected = {'SOP-PUR-11', 'SOP-PUR-12', 'SOP-PUR-13'}
    assert {p['id'] for p in proposal['procedures']} == expected
    original_steps = {p['id']: [s['text'] for s in p['steps']] for p in proposal['procedures']}
    assert all(len(steps) == 5 for steps in original_steps.values())
    assert '300만 원' in original_steps['SOP-PUR-11'][2]
    assert '승인 공급사가 아니면 이 절차를 쓰지 않는다.' in original_steps['SOP-PUR-13'][1]
    requests = []
    inst = extraction.start(runtime, source, str(uuid4()))
    runner = Runner(_settings(tmp_path / 'worker', cli_agent='codex'), runtime.repo,
                    exec_fn=_fake_exec(json.dumps({'proposal': proposal}), requests=requests),
                    schema_prompt='ManualSection Skill Step', resolve_provider=lambda _: object())
    assert runner.poll_once() == 1
    workitem = runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    delivered = _delivered_prompt(requests[0][0], tmp_path / 'worker' / 'hyd' / workitem['id'])
    assert extraction.INSTRUCTION in delivered
    inputs = json.loads(delivered.split('[InputData]\n')[1].split('\n\n##')[0])
    assert inputs['manual_source'] == source
    assert '승인: 구매 담당.' in inputs['manual_source']['pages'][0]['text']
    assert runtime.poll_once() == 1
    preview = extraction.result(runtime, source, inst['proc_inst_id'], None)['preview']
    assert {p['id']: [s['text'] for s in p['steps']] for p in preview['procedures']} == original_steps
    assert all([s['order'] for s in p['steps']] == [1, 2, 3, 4, 5] for p in preview['procedures'])
    assert 'reviewed' not in preview and 'by' not in preview
    with pytest.raises(ValueError, match='검토'):
        manual_review.validate(archive, 'hyd', preview)
