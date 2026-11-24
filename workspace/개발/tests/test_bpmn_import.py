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


@pytest.mark.parametrize('agent, says', [
    (None, '맡길 에이전트를 고르세요 — 비어 있습니다'), ('', '맡길 에이전트를 고르세요 — 비어 있습니다'),
    ('agent:no-such', '이 PC에 없는 에이전트입니다'), ('agent:handover', None),
], ids=['칸 없음', '빈 칸', '없는 에이전트', '고른 에이전트'])
def test_에이전트를_비운_단계는_첫_에이전트로_채우지_않고_비었다고_말한다(world, agent, says):
    """전수 대조(2026-11-14): 에이전트 칸을 비운 「에이전트 task」를 서버가 목록의 첫 에이전트로 채워 「검사 통과」가 됐다 — 사람이 고르지 않은
    수행자가 정의에 들어갔다(설정 불러오기 · API 길에서는 아무 말 없이). 비었으면 검사가 그 단계를 짚어 말한다."""
    mapping = copy.deepcopy(HANDOVER['mapping'])
    task = {'part': 'agent', 'instruction': '교대 인계안을 쓴다', 'outputs': [{'key': 'note', 'text': '인계안'}]}
    if agent is not None:
        task['agent'] = agent
    mapping['tasks']['task_draft'] = task
    result = _check(world, HANDOVER['xml'], mapping)
    found = [p for p in result['problems'] if p['field'] == 'agent' and p['where']['id'] == 'task_draft']
    if says is None:
        assert found == [], found
    else:
        assert not result['ok'] and len(found) == 1 and says in found[0]['reason'], result['problems']


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
    ('x' * (TEXT_MAX + 1), f'{TEXT_MAX:,}자 이하'),                                    # 수업 경계 정본의 한도 하나(가져오기 · 내 구성 파일 · 수업 판정)
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
    기준 흐름의 고정된 보고 넷(거절 · 발주만 등록 · 조치 종류 확인 필요 · 정비 뒤 미달)이 학생의 부품 목록에 끼지 않는다. 같은 부품을 두 갈래에
    둔 단계(설비 명령 뒤와 정비 요청만의 정비 요청 등록 · 효과 확인 — 2.8)도 부품 하나로 실린다."""
    from procsvc import effect_parts
    base = _base()
    reports = [a['id'] for a in base['activities'] if a.get('tool') == effect_parts.REPORT_TOOL]
    assert len(reports) == 4
    cat = bpmn_import.catalog(base, [])
    assert not set(reports) & {p['key'] for p in cat['parts']}
    assert [p['key'] for p in cat['parts'] if p.get('tool') == effect_parts.REPORT_TOOL] == ['svc:report']
    twice = {t for t in ('enterprise:WO_CREATE', 'incident:reobserve') if sum(a.get('tool') == t for a in base['activities']) == 2}
    assert twice == {'enterprise:WO_CREATE', 'incident:reobserve'}
    assert {t: [p['key'] for p in cat['parts'] if p.get('tool') == t] for t in twice} == \
           {'enterprise:WO_CREATE': ['task:work-order'], 'incident:reobserve': ['task:reobserve']}


def test_기준_흐름의_승인_단계가_거절_값을_내지_않으면_거절_값을_지어_붙이지_않고_까닭을_말한다():
    """옛 기준 흐름(2.3 — 낸 그대로의 원문)을 부품 원천으로 주면: 거절 칸을 붙여 부품을 만들어 내지 않는다."""
    import json
    from pathlib import Path
    old = json.loads((Path(__file__).resolve().parent / 'data' / 'definitions' / 'anomaly_response_2.3.json').read_text(encoding='utf8'))
    with pytest.raises(ValueError, match='거절 값\\(approval, approval_reason\\)을 내지 않습니다'):
        bpmn_import.catalog(old, [])


def test_고르는_목록에_없는_경보는_조용히_받지_않고_고를_수_있는_경보와_내_경보_종류로_적는_길을_말한다(world):
    """전수검사 10-G9: 「경보 정책에 없습니다」 한마디뿐이었다. S-A: 모르는 코드를 조용히 새 경보로 받으면 오타가 아무 경보도 받지 않는 흐름이
    되므로 고르는 목록은 아는 경보만이고, 내 시스템이 보내는 새 경보 종류는 「내 경보 종류」로 따로 적는다."""
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['start'] = {'kind': 'alert', 'patterns': ['PRESSURE_DROP']}
    said = next(p['reason'] for p in _check(world, HANDOVER['xml'], mapping)['problems'] if p.get('field') == 'start.patterns')
    assert '이 포털이 아는 경보가 아닙니다: PRESSURE_DROP' in said and '「내 경보 종류」에 코드와 이름을 적으세요' in said, said
    for offered in ('COOLER_DEGRADATION', 'PUMP_LEAKAGE', 'FAN_VIBRATION', 'OIL_ANALYSIS', 'SPARE_BELOW_MIN', 'PM_DUE'):
        assert offered in said, (offered, said)
    mapping['start'] = {'kind': 'alert', 'patterns': ['PUMP_LEAKAGE']}
    assert not [p for p in _check(world, HANDOVER['xml'], mapping)['problems'] if p.get('field') == 'start.patterns']


@pytest.mark.parametrize('declared, words', [
    ([{'pattern': 'APU_AIR_LEAK', 'name': '공기 누설 의심'}], None),
    ([{'pattern': 'apu-air-leak', 'name': '공기 누설 의심'}], "코드 'apu-air-leak'는 쓸 수 없습니다"),
    ([{'pattern': 'COOLER_DEGRADATION', 'name': '냉각'}], '이 포털이 이미 아는 경보입니다'),
    ([{'pattern': 'APU_AIR_LEAK', 'name': ''}], '이름을 적으세요'),
    ([{'pattern': 'APU_AIR_LEAK', 'name': '가'}, {'pattern': 'APU_AIR_LEAK', 'name': '나'}], '두 번 적혔습니다'),
], ids=['내 경보', '코드 꼴', '아는 경보', '이름 없음', '두 번'])
def test_내_시스템이_보내는_경보_종류를_흐름이_선언하고_회복은_원천의_해제다(world, declared, words):
    """S-A: 흐름 가져오기는 기준 흐름 · 사람 입력 · 업무 경보(모두 유압 실습장)만 고르게 해, 학생 시스템이 보내는 경보는 현장 검토로만 갔다.
    흐름이 받는 경보 종류를 스스로 선언하고, 그 경보의 회복 계약은 원천의 해제(시계열 기준 없음)다."""
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['start'] = {'kind': 'alert', 'patterns': [], 'declared': declared}
    result = _check(world, HANDOVER['xml'], mapping)
    said = [p['reason'] for p in result['problems'] if p.get('field') == 'start.declared']
    if words is None:
        assert not said and not [p for p in result['problems'] if p.get('field', '').startswith('start')], result['problems']
        assert result['definition']['alertPolicy']['patterns'] == {'APU_AIR_LEAK': {'requireClear': True, 'name': '공기 누설 의심'}}
        from procsvc import alert_policy
        policy = alert_policy.for_definition(dict(result['definition'], version='1'), 'APU_AIR_LEAK')
        assert (policy['route'], policy['criterion']) == ('response', None), policy
    else:
        assert said and words in said[0], said


def _course(did):
    from procsvc.course_policy import COURSE_FLOWS
    _, xml, mapping = COURSE_FLOWS[did]
    return xml, copy.deepcopy(mapping)


def _catalog(world):
    return bpmn_import.catalog(flows_api.default_base_loader(world.rt), world.rt.repo.list_users(None, 'hyd'))


@pytest.mark.parametrize('patterns, blocked', [
    (['OIL_ANALYSIS'], True),            # 사람 입력 경보 — 해제를 내는 원천이 없다
    (['SPARE_BELOW_MIN'], True),         # 업무 경보 — 이탈 표시는 시계열에 없고 해제도 없다
    (['COOLER_DEGRADATION'], False),     # 센서 경보 — 시계열 회복 기준(유온)이 있다
], ids=['사람 입력', '업무 경보', '센서 경보'])
def test_시계열_회복_기준이_없는_경보로_여는_흐름에는_효과_확인을_두지_못한다(world, patterns, blocked):
    """새5: 오일 분석 입력(사람 입력) · 업무 경보로 연 흐름에 효과 확인을 두면, 맞는 조치를 골라도 해제가 오지 않아 창을 세 번 늘린 뒤 늘 「미달」로
    끝났다(업무 경보는 값조차 없어 바로 미달). 가져오기 사전 검사가 그 칸에서 까닭과 함께 막는다."""
    xml, mapping = _course('c3_cooling')
    mapping['start'] = {'kind': 'alert', 'patterns': patterns}
    said = [p['reason'] for p in _check(world, xml, mapping)['problems'] if '효과 확인은 가상 설비 시계열의' in p['reason']]
    assert bool(said) is blocked, said
    if blocked:
        assert len(said) == 2 and all('그 기준이 없어(회복은 원천이 보내는 해제뿐) 효과 확인이 늘 미달로 끝납니다' in r and '「승인 뒤 MCP 호출」' in r
                                      for r in said), said     # 흐름 A 의 효과 확인 둘


def test_메시지로_시작하는_그림의_시작_경보는_미리_채우지_않고_사람이_고르게_둔다(world):
    """01 #8: 가져오기 API 의 기본값이 감지기 경보 전부라, 고르지 않은 흐름을 배포하면 모든 센서 경보의 경로를 가져갔다(포털만 빈 목록을 보냈다)."""
    xml, _ = _course('c3_cooling')
    mapping, _ = bpmn_import.merge_mapping(bpmn_import.parse_bpmn(xml), None, _catalog(world))
    assert mapping['start'] == {'kind': 'alert', 'patterns': []}
    said = [p['reason'] for p in _check(world, xml, mapping)['problems'] if p.get('field') == 'start.patterns']
    assert said == ['이 흐름을 시작할 경보를 하나 이상 고르거나 내 경보 종류를 적으세요'], said


@pytest.mark.parametrize('definition_id, name, refused', [
    ('my_cooling', None, True),                    # 제공 그림 그대로 — 그림의 프로세스 이름 「냉각 긴급 대응」
    ('my_cooling', '내 냉각 긴급 대응', False),
    ('c3_cooling', None, False),                   # 그 이름의 주인(수업 흐름 설치)
], ids=['같은 이름', '다른 이름', '이름의 주인'])
def test_기본_제공_흐름과_같은_이름의_흐름은_등록하지_못한다(world, definition_id, name, refused):
    """새6: 제공 냉각 그림을 고쳐 my_cooling 으로 가져오면 흐름 이름이 그림의 프로세스 이름 「냉각 긴급 대응」이 되어, 배포가 빠져 기본 제공 흐름이
    열려도 처리 건 화면(머리 = 흐름 이름)만으로는 내 흐름이 돈 줄 알았다."""
    xml, mapping = _course('c3_cooling')
    if name:
        mapping['name'] = name
    ctx = {'catalog': _catalog(world), 'definition_id': definition_id, 'version': '1', 'file_name': 'cooling-emergency.bpmn',
           'xml_sha256': bpmn_import.xml_sha256(xml), 'name': None, 'taken_names': {'냉각 긴급 대응': 'c3_cooling', '설비 이상 조치': 'anomaly_response'}}
    said = [p['reason'] for p in bpmn_import.check(bpmn_import.parse_bpmn(xml), mapping, ctx)['problems'] if p.get('field') == 'name']
    assert bool(said) is refused, said
    if refused:
        assert said == ['흐름 이름 「냉각 긴급 대응」은 기본 제공 흐름의 이름입니다 — 처리 건 화면에서 어느 흐름이 돌았는지 가를 수 있게 다른 이름을 적으세요(예: 「내 냉각 긴급 대응」)']


#: 가상 설비 전용 단계를 막는 문장의 머리(engine.plant_only_words) — 단계 이름마다
PLANT_ONLY = {'정비 수행': '정비 수행은 가상 설비의 결함 상태를 되돌리는 단계라 가상 설비(HYD-01 · HYD-02 · HYD-03)의 처리 건에서만 합니다',
              '시운전 확인': '시운전 확인은 가상 설비 시계열의 태그 값을 읽어 판정하는 단계라 가상 설비(HYD-01 · HYD-02 · HYD-03)의 처리 건에서만 합니다',
              '효과 확인': '효과 확인은 가상 설비 시계열의 회복 기준 값으로 회복을 재는 단계라 가상 설비(HYD-01 · HYD-02 · HYD-03)의 처리 건에서만 합니다'}


def _plant_only(problems):
    """가상 설비 전용 단계로 막힌 칸 {단계 이름: [칸 id …]} — 문장 머리로 가른다(그 밖의 문제는 세지 않는다)."""
    out = {}
    for p in problems:
        for name, head in PLANT_ONLY.items():
            if p['reason'].startswith(head):
                out.setdefault(name, []).append(p['where']['id'])
    return {name: sorted(ids) for name, ids in out.items()}


@pytest.mark.parametrize('start, test_run, expected', [
    ({'kind': 'alert', 'patterns': [], 'declared': [{'pattern': 'APU_AIR_LEAK', 'name': '공기 누설 의심'}]}, True,
     {'효과 확인': ['T_reobs', 'T_reobs_wo'], '시운전 확인': ['T_fix']}),
    ({'kind': 'alert', 'patterns': [], 'declared': [{'pattern': 'APU_AIR_LEAK', 'name': '공기 누설 의심'}]}, False,
     {'효과 확인': ['T_reobs', 'T_reobs_wo'], '정비 수행': ['T_fix']}),
    ({'kind': 'alert', 'patterns': ['COOLER_DEGRADATION']}, True, {}),
    ({'kind': 'alert', 'patterns': ['COOLER_DEGRADATION']}, False, {}),
    ({'kind': 'alert', 'patterns': ['PM_DUE']}, True, {}),         # 업무 경보 — 설비는 가상 설비라 시운전은 둘 수 있다(효과 확인은 기준이 없어 못 둔다)
], ids=['내 경보 · 시운전', '내 경보 · 정비 수행', '센서 경보 · 시운전', '센서 경보 · 정비 수행', '업무 경보 · 시운전'])
def test_내_시스템_경보로_여는_흐름에는_가상_설비_전용_단계를_두지_못한다(world, start, test_run, expected):
    """S-A · 검토 가-2: 학생 설비는 가상 설비에 없다 — 그런 경보의 흐름에 효과 확인 · 시운전을 두면 늘 「값 없음 → 미달」이고, 정비 수행을 두면
    설비 시뮬레이터가 그 설비를 몰라 「시작.bat 으로 시스템을 다시 켠 뒤」라는 엉뚱한 까닭으로 실패했다(전에는 정비 수행은 막지 않았다). 가져오기가
    세 단계 모두 그 칸에서 막고, 내 시스템을 부르는 「승인 뒤 MCP 호출」로 그리라고 말한다. 가상 설비 경보의 흐름은 그대로 통과한다."""
    xml, mapping = _course('c3_cooling')
    mapping['start'] = start
    if test_run:
        mapping['tasks']['T_fix'] = {'part': 'svc:test-run', 'config': {'criteria': {'TS1': ['<', 55]}}}
    problems = _check(world, xml, mapping)['problems']
    assert _plant_only(problems) == expected, problems
    said = [p['reason'] for p in problems if p['where']['id'] == 'T_fix' and p['reason'].startswith(tuple(PLANT_ONLY.values()))]
    if said:
        assert '이 흐름을 여는 경보 공기 누설 의심은 가상 설비 밖(내 시스템)의 경보라 그 설비가 가상 설비에 없습니다' in said[0] \
            and '「승인 뒤 MCP 호출」' in said[0], said


def test_부품_목록의_가상_설비_전용_부품은_설명_첫머리에서_가상_설비의_처리_건에서만_한다고_말한다(world):
    """검토 가-2 · 의심: 흐름 가져오기 부품 목록(catalog)의 정비 수행 · 시운전 확인 설명은 가상 설비 전용이라는 말이 없었다 — 학생이 내 설비
    흐름에 그려 놓고서야 검사에서 알았다. 설명은 가져오기 검사 · 실행의 거절과 같은 문장(engine.plant_only_words)으로 시작하고, 내 설비에서 같은
    일을 하는 길(「승인 뒤 MCP 호출」)을 말한다."""
    from procsvc import engine
    parts = {p['tool']: p for p in _catalog(world)['parts'] if p.get('group') == 'general' and p.get('tool') in engine.PLANT_ONLY_TOOLS}
    assert sorted(parts) == ['plant:restore', 'plant:test-run'], sorted(parts)
    for tool, part in parts.items():
        assert part['help'].startswith(f'{engine.plant_only_words(tool)} — {engine.PLANT_ONLY_INSTEAD}. '), part['help']


MAINTAIN = f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions {NS} id="D_MT"><bpmn:process id="Process_MT" name="정비 요청">
  <bpmn:startEvent id="Start" name="정비 요청 접수"/>
  <bpmn:userTask id="T_ok" name="운전원 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_fix" name="정비"/>
  <bpmn:serviceTask id="T_run" name="시운전"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:endEvent id="E_no" name="반려"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_ok"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_ok" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_fix"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="E_no"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_fix" targetRef="T_run"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_run" targetRef="E_end"/>
</bpmn:process></bpmn:definitions>'''


def maintain_mapping(asset_field):
    """사람이 시작할 때 설비와 정비 안을 적는 흐름: 운전원 승인 → 정비 수행 → 시운전 확인. asset_field = 시작 칸 asset(없으면 None)."""
    fields = ([asset_field] if asset_field else []) + [{'key': 'proposal', 'text': '정비 안', 'type': 'object'}]
    return {'name': '정비 요청', 'start': {'kind': 'human', 'fields': fields}, 'lanes': {}, 'timers': {},
            'tasks': {'T_ok': {'part': 'human:approve', 'role': '운전원', 'config': {'options': 'proposal.options'}},
                      'T_fix': {'part': 'svc:maintenance', 'config': {}},
                      'T_run': {'part': 'svc:test-run', 'config': {'criteria': {'TS1': ['<', 55]}, 'settle': 'PT1M'}}},
            'flows': {'F_yes': {'var': 'approval', 'op': '==', 'value': '승인'}, 'F_no': {'default': True}}}


@pytest.mark.parametrize('asset_field, blocked', [
    ({'key': 'asset', 'text': '설비', 'type': 'select', 'items': ['HYD-01', 'HYD-02', 'HYD-03']}, False),
    ({'key': 'asset', 'text': '설비', 'type': 'select', 'items': ['HYD-02']}, False),
    ({'key': 'asset', 'text': '설비', 'type': 'text'}, True),
    ({'key': 'asset', 'text': '설비', 'type': 'select', 'items': ['HYD-01', 'APU-01']}, True),
    (None, True),
], ids=['가상 설비 셋에서 고름', '가상 설비 하나', '글로 적음', '내 설비도 고를 수 있음', '설비 칸 없음'])
def test_사람_입력으로_시작하는_흐름의_가상_설비_전용_단계는_시작_칸이_가상_설비를_고를_때만_둔다(world, asset_field, blocked):
    """검토 가-2: 사람 입력으로 시작하는 흐름은 경보 정책이 없어 전에는 효과 확인 · 시운전 · 정비 수행을 모두 그대로 통과시켰다 — 시작할 때 내 설비
    (APU-01)를 적으면 정비 수행은 설비 시뮬레이터가 모르는 설비로 엉뚱한 까닭에 실패하고, 시운전은 값 없음을 미달로 판정했다. 설비는 시작할 때 사람이
    적으므로, 시작 칸 asset 이 가상 설비 셋 안에서 고르는 칸일 때만 가상 설비 전용 단계를 둔다."""
    problems = _check(world, MAINTAIN, maintain_mapping(asset_field))['problems']
    assert _plant_only(problems) == ({'정비 수행': ['T_fix'], '시운전 확인': ['T_run']} if blocked else {}), problems
    if blocked:
        said = next(p['reason'] for p in problems if p['where']['id'] == 'T_fix' and p['reason'].startswith(PLANT_ONLY['정비 수행']))
        assert '시작 칸 asset 을 HYD-01 · HYD-02 · HYD-03 중에서 고르는 칸(select)으로 두세요' in said and '「승인 뒤 MCP 호출」' in said, said
    else:
        assert not [p for p in problems if p['where']['id'] in ('T_fix', 'T_run')], problems


@pytest.mark.parametrize('patterns, blocked', [(['PM_DUE'], True), (['PM_DUE', 'COOLER_DEGRADATION'], False), (['COOLER_DEGRADATION'], False)],
                         ids=['정기 정비 도래만', '정기 정비와 센서 경보', '센서 경보만'])
def test_정기_정비_도래_경보만_받는_흐름에는_정비_수행을_두지_못한다(world, patterns, blocked):
    """새3: 정기 정비 카드의 정비 요청은 늘 정비 범위의 부품을 예약한 요청이고, 업무 시스템은 그 요청의 완료를 받지 않는다(예약 부품 출고가 없다 — 현장 쪽
    한계). 그리면 승인 · 정비 요청 등록 뒤에야 정비 수행이 실패했다. 가져오기가 그 칸에서 까닭과 함께 막는다. 다른 경보도 받는 흐름은 막지 않는다
    (그 경보의 정비 요청은 완료된다 — 정기 정비 카드가 그 단계에 오면 업무 시스템이 같은 까닭으로 거절한다)."""
    xml, mapping = _course('c3_cooling')
    mapping['start'] = {'kind': 'alert', 'patterns': patterns}
    said = [p for p in _check(world, xml, mapping)['problems'] if '정비 수행은 승인 뒤 늘 실패합니다' in p['reason']]
    assert bool(said) is blocked, said
    if blocked:
        assert [p['where']['id'] for p in said] == ['T_fix'] and '예약한 부품을 출고하는 처리가 없습니다' in said[0]['reason']             and '정비 요청 등록과 결과 보고까지 그리세요' in said[0]['reason'], said


def test_사람_승인과_설비_명령_사이에_다른_실행_단계를_두면_그_칸에서_막는다(world):
    """설비 명령이 든 안을 승인한 사건은 그 명령이 나갈 때까지 승인 대기다 — 그 사이 경보가 풀리면 설비에 명령을 내지 않고 「조치 전 해소」로 닫는다.
    승인과 설비 명령 사이에 정비 요청 같은 다른 실행 단계가 돌면, 그 효과가 나간 뒤의 해제가 「조치 전」으로 적혔다. 제공 그림(설비 명령 → 효과 확인 →
    정비 요청)은 그대로 통과하고, 두 단계의 차례를 바꾼 흐름(정비 요청 → 효과 확인 → 설비 명령)은 앞선 단계에서 막는다."""
    for did in ('c3_cooling', 'c3_pm', 'c3_spare'):
        xml, mapping = _course(did)
        assert not [p for p in _check(world, xml, mapping)['problems'] if '사람 승인과 설비 명령 사이에서 실행됩니다' in p['reason']], did
    xml, mapping = _course('c3_cooling')
    mapping['tasks']['T_cmd'], mapping['tasks']['T_wo'] = mapping['tasks']['T_wo'], mapping['tasks']['T_cmd']
    said = [p for p in _check(world, xml, mapping)['problems'] if '사람 승인과 설비 명령 사이에서 실행됩니다' in p['reason']]
    assert [p['where']['id'] for p in said] == ['T_cmd'], said
    assert said[0]['reason'].startswith('정비 요청 부품이 사람 승인과 설비 명령 사이에서 실행됩니다') and '「조치 전 해소」로 끝납니다' in said[0]['reason']         and '설비 명령 부품을 사람 승인 바로 뒤에 두고 이 단계는 그 뒤로 옮기세요' in said[0]['reason'], said

