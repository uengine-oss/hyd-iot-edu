"""승인 뒤 실행 부품 처리기(procsvc/service_parts.py) — 입고의 시간 근거, 결과 보고의 측정값 · 알림, 승인 없는 실행 거절(실제 엔진 · 업무 DB)."""
import json

import psycopg
import pytest

from conftest import OPERATOR
from hydcommon import topics
from procsvc import effect_parts, scenario_buttons as sb, service_parts

BUYER = dict(by=OPERATOR['by'], role='role:purchasing')    # 사람은 담당자 한 명 — 구매 담당 역할로 승인한다
PO = {'ref': 'PR-1', 'after': {'lead_d': 5, 'expected_at': '2026-11-04T06:09:57+00:00'}}


@pytest.mark.parametrize('plan, text', [
    ({'real_s': 60.0, 'time_scale': 20.0, 'compression': 360.0, 'lead_d': 5, 'delay_d': 0.0},
     '업무 시간 리드타임 5일을 실제 60초로 줄여 기다린 뒤 입고했습니다(배속 20 × 대기 압축 360)'),
    ({'real_s': 120.0, 'time_scale': 20.0, 'compression': 360.0, 'lead_d': 5, 'delay_d': 5.0},
     '업무 시간 리드타임 5일 + 공급사 지연 5일을 실제 120초로 줄여 기다린 뒤 입고했습니다(배속 20 × 대기 압축 360)'),
], ids=['배속 × 압축', '공급사 지연 포함'])
def test_입고_거래는_업무_시각의_입고_예정과_실제_입고의_차이를_글로_싣는다(plan, text):
    """H-11: ERP 발주 행의 입고 예정은 업무 시각(발주 + 리드타임 5일)이라, 줄여 기다린 입고가 「예정보다 일찍 입고」로 읽혔다. 이 글은 업무 DB
    입고 기록과 결과 보고에 그대로 나가므로 작업자끼리 쓰는 말(「수업 즉시 입고」)을 담지 않는다."""
    assert service_parts.receipt_basis(PO, plan) == text


def _press_c(world):
    world.main._entsim_post(*sb.SCENARIOS['C']['reset'])
    prep = sb.prepare('C', world.instance_mode.enterprise_read, world.rt, world.main._scenario_route,
                      sb.who({'by': '담당자', 'user_id': OPERATOR['by'], 'roles': ['role:purchasing']}))
    receipt = world.receive(topics.K_ALERTS, prep['alert'])
    assert receipt['status'] == 'HANDLED', receipt
    return receipt['result']['instance']


def test_흐름_C의_입고는_리드타임을_줄여_기다린_근거를_업무_DB_입고_기록에_남긴다(world):
    """전에는 흐름 C 가 리드타임을 건너뛰고(흐름 설정 immediate) 입고 기록에 「수업 즉시 입고 — …」를 남겼다. 그 지름길을 지웠다 — 승인 직후에는
    입고 기록이 없고, 입고 예정(리드타임을 배속 × 대기 압축으로 줄인 시각) 뒤에 입고하며 그 근거를 기록에 남긴다."""
    pid = _press_c(world)
    decision = world.agent(pid, 'T_agent')
    world.approve(pid, decision, world.main.book[decision]['recommended'], BUYER)
    world.poll(2)
    assert world.values(pid).get('goods_receipt') is None, '승인 직후에 입고됐다'
    wait = next(e['data']['plan'] for e in world.events(todo=world.row(pid, 'T_gr')['id']) if e['job_id'] == 'RECEIPT_WAIT')
    world.clock.advance(wait['real_s'] + 1)
    world.poll(3)
    values = world.values(pid)
    po, gr = values['purchase_order']['ref'], values['goods_receipt']['ref']
    with psycopg.connect(world.dsn) as db:
        detail = db.execute('SELECT detail FROM ent.transactions WHERE ref = %s', (gr,)).fetchone()[0]
    assert service_parts.receipt_basis(values['purchase_order'], wait) in detail and po in detail and '수업' not in detail, detail
    assert values['result_report']['notification_count'] >= 1


def test_결과_보고는_회복_기준_측정값을_싣고_못_읽은_까닭이_없으면_빈칸을_두지_않는다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    world.ack('HYD-01', cmd['cmdId'])
    world.tag('HYD-01', 'TS1', 50.0)
    world.clear_alert(alert)
    world.clock.advance(15 * 60 / 20 + 1)
    world.poll()
    report = world.values(pid)['result_report']
    ts1 = next(r for r in report['values'] if r['name'] == '유온 (TS1)')
    assert (ts1['value'], ts1['unit'], ts1['limit'], ts1['ok']) == (50.0, ' ℃', '< 55 ℃', True), ts1
    assert 'values_error' not in report


GR_ONLY = '''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_GR"><bpmn:process id="Process_GR" name="입고만">
  <bpmn:startEvent id="Start" name="입고 확인 요청"/>
  <bpmn:userTask id="T_ok" name="구매 담당 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_gr" name="입고 · 재고 반영"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:endEvent id="E_no" name="반려"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_ok"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_ok" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_gr"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="E_no"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_gr" targetRef="E_end"/>
</bpmn:process></bpmn:definitions>'''


def test_리드타임을_어디서도_못_얻은_입고는_0일로_바로_입고하지_않고_그_까닭으로_멈춘다(world):
    """FD 검증 ②: 발주 영수증에도 구매 · 재고 관리에도 리드타임이 없으면 0일(바로 입고) · 「리드타임 None일」 출처를 지어냈다.
    입고 단계 하나짜리 흐름으로 리드타임 없는 발주를 시작한다. 수업 단계는
    교대 인수인계 외의 흐름 가져오기를 막으므로(course_policy — PBL 에서 열림), 가져오기와 같은 변환(bpmn_import.parse_bpmn → check,
    기준 정의 부품 목록 flows_api.default_base_loader)으로 정의를 만들어 엔진에 등록한다(HTTP 수업 문지기만 지나지 않음)."""
    import uuid
    from procsvc import bpmn_import, flows_api
    mapping = {'name': '입고만', 'start': {'kind': 'human', 'fields': [{'key': 'purchase_order', 'text': '발주 영수증', 'type': 'object'},
                                                                     {'key': 'proposal', 'text': '입고할 안', 'type': 'object'}]},
               'tasks': {'T_ok': {'part': 'human:approve', 'role': '구매 담당', 'config': {'options': 'proposal.options'}},   # 효과 앞 사람 승인(등록 검사)
                         'T_gr': {'part': 'svc:goods-receipt', 'config': {}}},
               'flows': {'F_yes': {'var': 'approval', 'op': '==', 'value': '승인'}, 'F_no': {'default': True}}, 'lanes': {}, 'timers': {}}
    did = 'gr_only_' + uuid.uuid4().hex[:8]
    cat = bpmn_import.catalog(flows_api.default_base_loader(world.rt), world.rt.repo.list_users(None, world.rt.tenant_id))
    checked = bpmn_import.check(bpmn_import.parse_bpmn(GR_ONLY), mapping, {'catalog': cat, 'definition_id': did, 'version': '1',
                                'file_name': 'gr-only.bpmn', 'xml_sha256': bpmn_import.xml_sha256(GR_ONLY), 'name': None})
    assert checked['ok'], checked['problems']
    world.rt.register_definition(checked['definition'])
    version = checked['definition']['version']
    ref = 'PR-NOLEAD-' + uuid.uuid4().hex[:8].upper()                     # 리드타임이 비어 있는 발주(옛 구매요청 꼴) — ERP 조회도 리드타임을 주지 못한다
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("INSERT INTO ent.purchase_requests (id, part, supplier, supplier_name, asset, requested_by) "
                   "VALUES (%s, '펌프 축 씰 키트', 'sup:b', 'B-OEM', 'HYD-01', 'test')", (ref,))
    pid = world.rt.start_definition(did, version, 'gr:' + uuid.uuid4().hex,
                                    values={'purchase_order': {'ref': ref, 'after': {}}, 'proposal': {'options': [{'slot': 'A', 'reason': '입고 확인'}]}})['proc_inst_id']
    world.poll()
    from procsvc import approval_part
    world.rt.approve(world.row(pid, 'T_ok', 'IN_PROGRESS')['id'], approval_part.APPROVE, 'A', **BUYER)
    world.poll(3)
    row = world.row(pid, 'T_gr')
    errors = [e['data'] for e in world.events(pid) if e['event_type'] == 'error']
    text = json.dumps(errors, ensure_ascii=False) + (row.get('log') or '')
    assert row['status'] != 'DONE' and world.values(pid).get('goods_receipt') is None, (row['status'], world.values(pid).get('goods_receipt'))
    assert f'발주 {ref} 의 공급사 리드타임' in text and '입고 예정 시각을 정할 수 없습니다' in text, text
