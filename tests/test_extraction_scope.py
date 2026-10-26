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
    assert extraction.VERSION == '2.15'
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
    proposal = {k: v for k, v in manual_review.proposal(source).items() if k in extraction.PROPOSAL_KEYS}   # AI 출력 꼴(맨 위 칸)
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


def test_instruction_2_7_pins_numbers_penalty_measure_and_document_defined_failure_modes():
    """2026-10-25 수업 한 바퀴: 같은 HM-8 세 번 추출 — 두 번은 weight · penalizes 형식 거부로 교정 2회(11분 넘김), 한 번은 고장 유형 · 원인 0개,
    팬 절차는 「catalog에 없음」으로 고장 유형 연결을 비웠다. 지시가 그 넷을 막는가."""
    text = extraction.INSTRUCTION
    assert '"weight":1.0' in text and '"prior":0.6' in text and '"weight":0.0~1.0' not in text   # 범위 예시를 베껴 문자열을 쓰게 하지 않는다
    assert "penalizes에 ontology_catalog의 지표(msr:…) 하나를 반드시" in text
    assert "빈 목록으로 두지 마세요" in text and "ontology_catalog에 아직 없어도 됩니다" in text
    assert "REMEDIED_BY · addresses=[그 원인]" in text


def test_instruction_2_8_asks_one_candidate_rule_per_cause():
    """2026-10-25 수업 한 바퀴 재실행: 같은 HM-8 세 번 중 한 번이 즉시 완화 후보 규칙만 만들고 원인별 근본 조치(핀 세척 · 환기 · 팬 점검)의
    후보 규칙(in:cause == 원인)을 빠뜨렸다 — 원인이 판정돼도 근본 조치 카드가 나오지 않는다."""
    text = extraction.INSTRUCTION
    assert '"input":"in:cause","operator":"==","value":"cause:…"' in text
    assert "그 원인마다" in text and "빠뜨리지 마세요" in text


def test_instruction_2_8_asks_purchase_comparison_and_maintenance_policies():
    """2026-10-25 수업 한 바퀴: 지시에 두 정책이 없어 4회차에 다시 적재한 PR-07 · PM-02 제안이 정책 없이 C · B 판단을 막았다."""
    text = extraction.INSTRUCTION
    assert '"purchase_comparison_policy":{"version":1,"loss_per_failure"' in text and '"inspection_threshold":불량률 비율(10 %면 0.1)' in text
    assert '"maintenance_policy":{"version":1,"scope":"single' in text and '"model_anchor":ANCHOR' in text and '"packages":[' in text


def test_instruction_2_9_links_a_procedure_the_handed_over_inspection_hands_on():
    """2026-10-25 final4: 같은 HM-8 세 번 중 한 번이 HM-8.1 점검이 '벗어나면 교체한다'로 넘기는 벨트 교체(SOP-FAN-12)의 link 를 비웠다."""
    text = extraction.INSTRUCTION
    assert "넘겨받은 점검 절차가 다시 다른 절차로 넘기면" in text and "그 절차도 같은 고장 유형 · REMEDIED_BY · addresses=[그 원인]" in text


def test_instruction_2_10_maps_unit_numbers_to_catalog_asset_codes():
    """2026-10-26: PM-02 추출 정책의 model_assets 가 매번 빠졌다 — 원문 '1~3호기'를 옮길 설비 목록이 카탈로그에 없었다."""
    from procsvc import manual_knowledge
    assert "ontology_catalog.assets code" in extraction.INSTRUCTION and '1~3호기 → "HYD-01","HYD-02","HYD-03"' in extraction.INSTRUCTION
    assert "MATCH (n:Asset)" in manual_knowledge.CATALOG_Q["assets"] and "n.code AS code" in manual_knowledge.CATALOG_Q["assets"]


def test_instruction_2_11_keeps_handed_on_procedures_out_of_candidate_outputs():
    """2026-10-26 final5: HM-8 세 번 중 한 번이 점검이 넘기는 벨트 교체(SOP-FAN-12)를 팬 구동 불량 후보 규칙에도 넣었다(검토본은 점검만)."""
    assert "원인 후보 규칙의 outputs 에 넣지 마세요 — 후보는 원문이 그 원인에서 바로 쓰라고 한 절차(점검)만" in extraction.INSTRUCTION


def test_instruction_2_12_unnumbered_criteria_sections_are_not_sops():
    """2026-10-26 final6: HM-8 세 번 중 한 번이 판정 기준만 적은 HM-8.6(회복 판정)을 SOP 로 뽑았다(검토본은 절 · 규칙만)."""
    text = extraction.INSTRUCTION
    assert "번호 없는 절은 실행 행위" in text and "판정 · 합격 기준만 정한 절" in text and "SOP로 만들지 말고" in text
