"""흐름 그림 가져오기(procsvc/bpmn_import.py) — 학생이 bpmn.io 로 그린 그림을 매핑 · 사전 검사 · 등록 검사까지.

제공 교대 그림 · 매핑(it/process/definitions/shift_handover.bpmn · .mapping.json — course_policy.HANDOVER)을 원본으로 쓴다.
카탈로그(부품 · 역할 · 에이전트)는 실제 DB(시드 테넌트 hyd)에서 읽는다.
"""
import copy
import re
import time

import pytest

from procsvc import bpmn_import, flows_api
from procsvc.course_policy import HANDOVER, TEXT_MAX

NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def _check(world, xml, mapping=None):
    parsed = bpmn_import.parse_bpmn(xml)
    catalog = bpmn_import.catalog(flows_api.default_base_loader(world.rt), world.rt.repo.list_users(None, 'hyd'))
    ctx = {'catalog': catalog, 'definition_id': 'ShiftHandover', 'version': '1', 'file_name': 'shift-handover.bpmn',
           'xml_sha256': bpmn_import.xml_sha256(xml), 'name': None}
    return bpmn_import.check(parsed, HANDOVER['mapping'] if mapping is None else mapping, ctx)


def _reasons(result):
    return ' '.join(p['reason'] for p in result['problems'])


def test_제공_그림_그대로는_검사를_통과하고_정의가_된다(world):
    result = _check(world, HANDOVER['xml'])
    assert result['ok'], result['problems']
    assert {a['id'] for a in result['definition']['activities']} >= {'task_draft', 'task_sender', 'task_receiver'}


def _renamed(xml):
    return xml.replace('name="인계자 검토"', 'name="보내는 사람 검토"').replace('name="인수자 확인"', 'name="받는 사람 확인"')


def _moved(xml):
    return re.sub(r'<dc:Bounds x="(\d+)" y="(\d+)"', lambda m: f'<dc:Bounds x="{int(m[1]) + 37}" y="{int(m[2]) + 11}"', xml)


@pytest.mark.parametrize('change, names', [
    (_renamed, {'task_sender': '보내는 사람 검토', 'task_receiver': '받는 사람 확인'}),          # 이름만(G5b-14)
    (_moved, {'task_sender': '인계자 검토', 'task_receiver': '인수자 확인'}),                    # 배치만
    (lambda x: _moved(_renamed(x)), {'task_sender': '보내는 사람 검토', 'task_receiver': '받는 사람 확인'}),
])
def test_이름이나_배치만_바꾼_그림도_같은_흐름으로_통과하고_바꾼_이름이_단계_이름이_된다(world, change, names):
    xml = change(HANDOVER['xml'])
    assert xml != HANDOVER['xml']
    result = _check(world, xml)
    assert result['ok'], result['problems']
    got = {a['id']: a['name'] for a in result['definition']['activities']}
    assert {k: got[k] for k in names} == names


def _chained_gateway(xml):
    """인계자 승인 뒤에 분기를 하나 더 — 조건 선만 있고 「그 밖의 경우」가 없다(#16)."""
    xml = xml.replace('<bpmn:exclusiveGateway id="gw_sender" name="인계자 결정" />',
                      '<bpmn:exclusiveGateway id="gw_sender" name="인계자 결정" /><bpmn:exclusiveGateway id="gw_extra" name="긴급 분기" />')
    xml = xml.replace('<bpmn:sequenceFlow id="seq_3" name="전달" sourceRef="gw_sender" targetRef="task_receiver" />',
                      '<bpmn:sequenceFlow id="seq_3" name="전달" sourceRef="gw_sender" targetRef="gw_extra" />'
                      "<bpmn:sequenceFlow id=\"seq_extra\" sourceRef=\"gw_extra\" targetRef=\"task_receiver\" name=\"sender_notes == '긴급'\" />"
                      "<bpmn:sequenceFlow id=\"seq_extra2\" sourceRef=\"gw_extra\" targetRef=\"ev_followup\" name=\"sender_notes == '보통'\" />")
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['flows']['seq_extra'] = {'var': 'sender_notes', 'op': '==', 'value': '긴급'}
    mapping['flows']['seq_extra2'] = {'var': 'sender_notes', 'op': '==', 'value': '보통'}
    return xml, mapping


def _cut_receiver(xml):
    return xml.replace('<bpmn:sequenceFlow id="seq_3" name="전달" sourceRef="gw_sender" targetRef="task_receiver" />', ''), None


def _parallel_sender(xml):
    """P5-11: 인계자 검토 뒤 배타 분기를 병렬 분기로 — 매핑의 세 선 조건(승인 · 보완 · 거절)이 그대로 남아 있다."""
    return xml.replace('<bpmn:exclusiveGateway id="gw_sender" name="인계자 결정" />', '<bpmn:parallelGateway id="gw_sender" name="인계자 결정" />'), None


def _broken_condition(xml):
    """P5-19: 그림의 조건식이 틀렸고 매핑에는 그 선의 조건이 없다."""
    xml = xml.replace('<bpmn:sequenceFlow id="seq_5" name="반려" sourceRef="gw_sender" targetRef="ev_rejected" />',
                      '<bpmn:sequenceFlow id="seq_5" name="반려" sourceRef="gw_sender" targetRef="ev_rejected">'
                      "<bpmn:conditionExpression>sender_decision ==== 'reject'</bpmn:conditionExpression></bpmn:sequenceFlow>")
    mapping = copy.deepcopy(HANDOVER['mapping'])
    del mapping['flows']['seq_5']
    return xml, mapping


@pytest.mark.parametrize('change, words', [
    (_cut_receiver, '시작에서 닿지 않습니다'),             # 인수자 확인으로 가는 선을 끊음
    (_chained_gateway, '그 밖의 경우'),                    # #16: 분기 뒤 분기에 기본 선 없음
    (_parallel_sender, '병렬 분기'),                        # P5-11: 병렬 분기에 조건 — 조건이 조용히 버려지지 않는다
    (_broken_condition, "조건식 'sender_decision ==== 'reject''를 읽을 수 없습니다"),   # P5-19: 「조건이 없습니다」가 아니라
])
def test_구조를_바꾼_그림은_학생이_읽을_사유와_함께_검사에서_멈춘다(world, change, words):
    xml, mapping = change(HANDOVER['xml'])
    assert xml != HANDOVER['xml']
    result = _check(world, xml, mapping)
    assert not result['ok']
    reasons = _reasons(result)
    assert words in reasons and re.search('[가-힣]', reasons), reasons


def test_병렬_분기로_바꾼_그림은_조건이_있던_선마다_사유가_나온다(world):
    xml, _ = _parallel_sender(HANDOVER['xml'])
    result = _check(world, xml)
    parallel = [p['where']['id'] for p in result['problems'] if '병렬 분기' in p['reason']]
    assert sorted(parallel) == ['seq_3', 'seq_4', 'seq_5'], result['problems']


def _chain(n, *, loop=False):
    """시작 → 사람 task n개 사슬 → 끝(loop 면 마지막 task 에서 첫 task 로 되돌아가는 선)."""
    tasks = ''.join(f'<bpmn:userTask id="t{i}" name="단계 {i}" />' for i in range(n))
    flows = ['<bpmn:sequenceFlow id="f_s" sourceRef="s" targetRef="t0" />']
    flows += [f'<bpmn:sequenceFlow id="f{i}" sourceRef="t{i}" targetRef="t{i + 1}" />' for i in range(n - 1)]
    flows.append(f'<bpmn:sequenceFlow id="f_back" sourceRef="t{n - 1}" targetRef="t0" />' if loop else
                 f'<bpmn:sequenceFlow id="f_e" sourceRef="t{n - 1}" targetRef="e" />')
    return (f'<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions {NS} id="d"><bpmn:process id="long" isExecutable="true">'
            f'<bpmn:startEvent id="s" />{tasks}<bpmn:endEvent id="e" />{"".join(flows)}</bpmn:process></bpmn:definitions>')


def test_글자_한도_안의_가장_긴_사슬도_재귀_한도_없이_빨리_검사한다(world):
    """P5-02: task 1,500개 사슬에서 RecursionError(500) · 900개에서 1초 넘게 걸렸다(노드마다 조상을 다시 훑음)."""
    n = 1
    while len(_chain(n * 2)) <= TEXT_MAX:
        n *= 2
    while len(_chain(n + 100)) <= TEXT_MAX:
        n += 100
    xml = _chain(n)
    assert n >= 1500 and len(xml) <= TEXT_MAX
    started = time.monotonic()
    result = _check(world, xml, {'start': {'kind': 'human', 'fields': []}, 'tasks': {}})
    took = time.monotonic() - started
    assert sum(1 for p in result['problems'] if p['field'] == 'part') == n      # 끝까지 훑었다: task 마다 「부품을 고르세요」
    assert took < 10, took


def test_긴_되돌림_고리도_빠져나갈_분기가_없다는_사유_하나로_찾는다(world):
    result = _check(world, _chain(1200, loop=True), {'start': {'kind': 'human', 'fields': []}, 'tasks': {}})
    loops = [p for p in result['problems'] if p['field'] == 'loop']
    assert result['loops'] and len(result['loops'][0]) == 1200
    assert [p['reason'] for p in loops] == ['되돌아가는 선에서 빠져나갈 배타 분기가 없습니다 (끝나지 않는 반복)']


@pytest.mark.parametrize('xml, pattern', [
    (HANDOVER['xml'][:5000], r'XML 을 읽을 수 없습니다 \(\d+행 \d+열\)'),          # 잘린 파일 — 위치(행 · 열)를 말한다
    (f'<bpmn:definitions {NS}><bpmn:process id="p">', r'XML 을 읽을 수 없습니다 \(\d+행 \d+열\)'),
    ('', '빈 파일입니다'),
    ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>', 'DOCTYPE · ENTITY'),
    (f'<?xml version="1.0"?><!--{"주석" * 2600}--><!DOCTYPE x SYSTEM "http://127.0.0.1:9/x.dtd"><bpmn:definitions {NS}/>',
     'DOCTYPE · ENTITY'),                                                              # P5-15: 앞 4,096자 뒤의 DOCTYPE 도
    ('<definitions/>', r'BPMN 2\.0 흐름 그림 파일이 아닙니다 — bpmn\.io 에서'),
    ('x' * (TEXT_MAX + 1), f'{TEXT_MAX:,}자 이하'),                                    # 수업 경계 정본의 한도 하나(가져오기 · 출발본 · 수업 판정)
], ids=['잘린 파일', '닫히지 않은 태그', '빈 파일', 'DOCTYPE', '긴 주석 뒤 DOCTYPE', 'BPMN 아님', '글자 한도 넘음'])
def test_깨진_XML은_위치와_할_일을_말하고_파서_영문을_보이지_않는다(xml, pattern):
    with pytest.raises(bpmn_import.BpmnError) as caught:
        bpmn_import.parse_bpmn(xml)
    message = str(caught.value)
    assert re.search(pattern, message), message
    assert not re.search(r'unclosed|not well-formed|syntax error|bpmn:definitions', message)


def test_글자_한도와_같은_길이의_그림은_한도_때문에_거절되지_않는다():
    head = f'<bpmn:definitions {NS}><bpmn:process id="p"><bpmn:startEvent id="s" /><bpmn:endEvent id="e" />'
    tail = '<bpmn:sequenceFlow id="f" sourceRef="s" targetRef="e" /></bpmn:process></bpmn:definitions>'
    xml = head + '<!--' + 'x' * (TEXT_MAX - len(head) - len(tail) - 7) + '-->' + tail
    assert len(xml) == TEXT_MAX
    assert bpmn_import.parse_bpmn(xml)['process']['id'] == 'p'


# ---------------------------------------------------------------- 부품 목록: 기준 흐름의 승인 단계 · 승인 뒤 실행 부품
def _base(name='anomaly_response_v22.json'):
    import json
    from conftest import DEFINITIONS
    return json.loads((DEFINITIONS / name).read_text(encoding='utf8'))


def test_조치_카드_승인_거절_부품은_기준_흐름의_승인_단계_계약_그대로다():
    """기준 흐름 2.4 부터 승인 단계가 거절 값을 낸다 — 부품 목록이 거절 칸을 한 번 더 붙이면(2.3 까지의 방식) 폼에 같은 칸이 둘이 된다."""
    from procsvc import approval_part
    base = _base()
    parts = {p['key']: p for p in bpmn_import.catalog(base, [])['parts']}
    select = next(a for a in base['activities'] if a['id'] == 'task:select')
    part = parts[bpmn_import.REJECTABLE_SELECT_PART]
    assert part['outputs'] == select['outputData'] == ['chosen_skill', 'chosen_skill_kind', *approval_part.OUTPUTS]
    assert part['form'] == base['forms']['select_card'] and [f['key'] for f in part['form']['fields_json']] == part['outputs']
    assert part['contract']['outputData'] == part['outputs'] and part['contract']['instruction'] == select['instruction']
    assert parts[bpmn_import.SELECT_PART]['outputs'] == part['outputs'], '거절 값 없는 조치 카드 승인 부품은 더는 없다'


def test_기준_흐름이_쓰는_결과_보고는_설정을_고르는_일반_부품_하나로만_실린다():
    """기준 흐름의 단계는 모두 「시나리오 부품」으로 실리는데, 결과 보고(승인 뒤 실행 부품)는 결과 · 글을 고르는 일반 부품이 따로 있다 —
    기준 흐름의 고정된 보고 셋(거절 · 발주만 등록 · 조치 종류 확인 필요)이 학생의 부품 목록에 끼지 않는다."""
    from procsvc import effect_parts
    base = _base()
    reports = [a['id'] for a in base['activities'] if a.get('tool') == effect_parts.REPORT_TOOL]
    assert len(reports) == 3
    cat = bpmn_import.catalog(base, [])
    assert not set(reports) & {p['key'] for p in cat['parts']}
    assert [p['key'] for p in cat['parts'] if p.get('tool') == effect_parts.REPORT_TOOL] == ['svc:report']


def test_기준_흐름의_승인_단계가_거절_값을_내지_않으면_거절_값을_지어_붙이지_않고_까닭을_말한다():
    """옛 기준 흐름(2.3 — 낸 그대로의 원문)을 부품 원천으로 주면: 거절 칸을 붙여 부품을 만들어 내지 않는다."""
    import json
    from pathlib import Path
    old = json.loads((Path(__file__).resolve().parent / 'data' / 'definitions' / 'anomaly_response_2.3.json').read_text(encoding='utf8'))
    with pytest.raises(ValueError, match='거절 값\\(approval, approval_reason\\)을 내지 않습니다'):
        bpmn_import.catalog(old, [])


def test_회복_기준이_없는_경보_패턴으로_시작하려_하면_까닭과_고를_수_있는_경보와_그_경보가_가는_곳을_말한다(world):
    """전수검사 10-G9: 지식 지도에 새로 그린 경보 패턴(회복 기준 없음)을 흐름의 시작으로 고르면 「경보 정책에 없습니다」 한마디뿐이었다 — 무엇이
    정책이고 무엇을 고를 수 있는지, 그 경보가 감지되면 어떻게 되는지 알 수 없었다."""
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['start'] = {'kind': 'alert', 'patterns': ['PRESSURE_DROP']}
    said = next(p['reason'] for p in _check(world, HANDOVER['xml'], mapping)['problems'] if p.get('field') == 'start.patterns')
    assert '경보 패턴 PRESSURE_DROP로는 이 흐름을 시작할 수 없습니다' in said and '회복 기준' in said
    for offered in ('COOLER_DEGRADATION', 'PUMP_LEAKAGE', 'FAN_VIBRATION', 'OIL_ANALYSIS', 'SPARE_BELOW_MIN', 'PM_DUE'):
        assert offered in said, (offered, said)
    assert '「미지원 경보 → 현장 검토」' in said and '경보 정책에 없습니다' not in said
    mapping['start'] = {'kind': 'alert', 'patterns': ['PUMP_LEAKAGE']}
    assert not [p for p in _check(world, HANDOVER['xml'], mapping)['problems'] if p.get('field') == 'start.patterns']
