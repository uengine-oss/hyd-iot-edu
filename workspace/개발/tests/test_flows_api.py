"""흐름 가져오기 API(procsvc/flows_api.py) — 학생이 포털에서 누르는 길 그대로(가져오기 · 검사 · 매핑 저장 · 등록 · 지우기 · 되돌리기), 수업 단계.

거절은 모두 같은 모양 {reason, problems?}이고, 누른 사람(by)이 감사 기록에 남는다. 강사가 설치한 수업 흐름은 읽기만 한다.
"""
import copy
import json

import pytest

from procsvc.course_policy import HANDOVER, TEXT_MAX

FLOW = 'ShiftHandover'
ME = 'user:me'                     # 이 PC의 담당자(시드 사용자 표의 사람 한 명) — 누른 사람 칸은 이 user id 만 받는다


@pytest.fixture
def handover(world):
    """제공 교대 그림을 가져온 상태 — 실습 순서 그대로. 수업 단계의 가져오기는 제공 연결(매핑)을 채워 돌려준다(화면은 흐름 이름 · 초안
    에이전트만 연다). 앞 테스트가 등록한 ShiftHandover 판본 · 초안은 먼저 지운다."""
    status, out = world.api('DELETE', f'/api/flows/{FLOW}?by={ME}')
    assert status in (200, 404), out                 # 앞 테스트가 남긴 것이 있으면 지움 · 없으면 404(지울 것 없음)
    status, view = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200, view
    assert view['class_flow'] is False
    return view


def test_수업_단계에서_제공_교대_그림을_가져오면_잠긴_칸까지_제공_연결로_채워_바로_등록할_수_있다(world, handover):
    """한바퀴3 고침: 화면이 흐름 이름 · 초안 에이전트 말고는 잠그는데(flows.js W3-08) 가져오기는 자동 연결(빈 실행 기능 칸)을 돌려줘, 학생은
    잠긴 칸을 채울 길이 없어 등록할 수 없었다. 시험은 매핑을 API 로 직접 넣어(학생에게 없는 길) 이 틈을 못 봤다."""
    assert handover['mapping'] == HANDOVER['mapping']
    assert handover['register'] == {'allowed': True, 'reason': None}


def test_다시_가져오면_앞_초안의_흐름_이름과_고른_에이전트를_잇는다(world, handover):
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['name'] = '우리 반 교대 인계'
    mapping['tasks']['task_draft']['agent'] = 'agent:my-handover'
    status, view = world.api('PUT', f'/api/flows/{FLOW}/mapping', {'mapping': mapping})
    assert status == 200, view
    status, view = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200 and view['mapping'] == mapping, view.get('mapping')


def _audit(world, event):
    return [e for e in world.main.audit_log if e['event'] == event]


@pytest.mark.parametrize('xml, words', [
    (HANDOVER['xml'][:5000], '행'),
    ('<definitions/>', 'BPMN 2.0 흐름 그림 파일이 아닙니다'),
    ('', '빈 파일입니다'),
], ids=['잘린 파일', 'BPMN 아님', '빈 파일'])
def test_깨진_그림을_가져오면_400_과_학생이_읽을_사유_칸_위치가_온다(world, xml, words):
    """G5b-14: 깨진 그림은 함수가 아니라 학생이 누르는 API 로도 확인한다(실습 09 확인 도구가 읽는 모양)."""
    status, out = world.api('POST', '/api/flows/import', {'xml': xml, 'file_name': 'broken.bpmn'})
    assert status == 400
    assert words in out['detail']['reason'] and out['detail']['problems'][0]['reason'] == out['detail']['reason']


def test_제공_교대_그림과_매핑을_넣으면_내_흐름이고_지금_등록할_수_있다고_미리_알린다(world, handover):
    assert handover['definition_id'] == FLOW and handover['check']['ok'] is True
    assert handover['class_flow'] is False and handover['register'] == {'allowed': True, 'reason': None}


def test_수업에서_바꿀_수_없는_칸을_바꾸면_검사에서_등록_불가와_까닭을_먼저_보인다(world, handover):
    """W3-08: 「검사 통과」를 보인 뒤 등록에서야 403 이 나던 것 — 같은 화면에서 등록 판정을 미리 싣는다."""
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['timers'] = {'b_extra': 'PT1M'}
    status, view = world.api('POST', f'/api/flows/{FLOW}/check', {'mapping': mapping})
    assert status == 200 and view['register']['allowed'] is False
    assert '바뀐 곳' in view['register']['reason'] and '시한' in view['register']['reason'], view['register']
    assert view['check']['ok'] is False                                           # 사전 검사도 같은 까닭 한 줄로 멈춘다
    assert [p['reason'] for p in view['check']['problems'] if p['field'] == 'course'] == [view['register']['reason']]
    status, out = world.api('POST', f'/api/flows/{FLOW}/register', {'mapping': mapping, 'by': ME})
    assert status == 403 and out['detail']['reason'] == view['register']['reason']


@pytest.mark.parametrize('body, status, words', [
    ({'mapping': HANDOVER['mapping']}, 400, '담당자 정보 없이 온 요청'),            # 누른 사람이 없다
    ({'mapping': HANDOVER['mapping'], 'by': '  '}, 400, '담당자 정보 없이 온 요청'),
    ({'mapping': HANDOVER['mapping'], 'by': '수강생 김'}, 403, '담당자 정보 없이 온 요청'),   # 이름만 적은 자유 입력
    ({'mapping': HANDOVER['mapping'], 'by': 'user:nobody'}, 403, '없는 사람 사용자입니다: user:nobody'),
], ids=['없음', '빈 칸', '자유 입력', '없는 사람'])
def test_판본_등록은_누른_사람이_없으면_등록하지_않는다(world, handover, body, status, words):
    got, out = world.api('POST', f'/api/flows/{FLOW}/register', body)
    assert got == status and words in out['detail']['reason']
    assert world.api('GET', f'/api/flows/{FLOW}')[1]['versions'] == []


def test_판본_등록은_누른_사람을_감사_기록에_남긴다(world, handover):
    before = len(_audit(world, 'FLOW_REGISTERED'))
    status, out = world.api('POST', f'/api/flows/{FLOW}/register', {'mapping': HANDOVER['mapping'], 'by': ME})
    assert status == 201, out
    entries = _audit(world, 'FLOW_REGISTERED')
    assert len(entries) == before + 1 and entries[0]['actor'] == ME and entries[0]['detail']['version'] == out['version']


def test_흐름_목록은_강사가_설치한_수업_흐름을_따로_표시한다(world, handover):
    status, out = world.api('GET', '/api/flows')
    assert status == 200
    marks = {d['proc_def_id']: d['class_flow'] for d in out['drafts']}
    assert marks[FLOW] is False and {k for k, v in marks.items() if v} >= {'c3_cooling', 'c3_pm', 'c3_spare'}


def test_수업_흐름은_지우지_않고_까닭을_말한다(world):
    status, out = world.api('DELETE', f'/api/flows/c3_cooling?by={ME}')
    assert status == 409 and '기본 제공 흐름이라 지울 수 없습니다' in out['detail']['reason']
    assert 'c3_cooling' in {h['id'] for h in world.rt.repo.deployed_heads('hyd')}


@pytest.mark.parametrize('path, code, words', [
    (f'/api/flows/{FLOW}', 400, '담당자 정보 없이 온 요청'), (f'/api/flows/{FLOW}?by=', 400, '담당자 정보 없이 온 요청'),
    (f'/api/flows/{FLOW}?by=%20', 400, '담당자 정보 없이 온 요청'), (f'/api/flows/{FLOW}?by=user:nobody', 403, '없는 사람 사용자입니다'),
], ids=['없음', '빈 칸', '공백', '없는 사람'])
def test_흐름_지우기는_등록된_사람이_아니면_지우지_않는다(world, handover, path, code, words):
    status, out = world.api('DELETE', path)
    assert status == code and words in out['detail']['reason']
    assert world.api('GET', f'/api/flows/{FLOW}')[0] == 200


def test_매핑이_글자_한도를_넘으면_저장하지_않는다(world, handover):
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['name'] = '가' * (TEXT_MAX + 1)
    status, out = world.api('PUT', f'/api/flows/{FLOW}/mapping', {'mapping': mapping})
    assert status == 400 and f'{TEXT_MAX:,}자 이하' in out['detail']['reason']
    assert world.api('GET', f'/api/flows/{FLOW}')[1]['mapping']['name'] == HANDOVER['mapping']['name']


def test_매핑이_한도와_같은_길이면_저장한다(world, handover):
    mapping = copy.deepcopy(HANDOVER['mapping'])
    mapping['name'] = ''
    pad = TEXT_MAX - len(json.dumps(mapping, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    mapping['name'] = '가' * pad
    status, view = world.api('PUT', f'/api/flows/{FLOW}/mapping', {'mapping': mapping})
    assert status == 200 and len(view['mapping']['name']) == pad


@pytest.mark.parametrize('body, code, words', [
    (None, 400, '담당자 정보 없이 온 요청'), ({}, 400, '담당자 정보 없이 온 요청'), ({'by': ''}, 400, '담당자 정보 없이 온 요청'),
    ({'by': '수강생 김'}, 403, '담당자 정보 없이 온 요청'), ({'by': 'user:nobody'}, 403, '없는 사람 사용자입니다'),
], ids=['본문 없음', '칸 없음', '빈 칸', '자유 입력', '없는 사람'])
def test_기준으로_되돌리기는_등록된_사람이_아니면_아무것도_지우지_않는다(world, handover, body, code, words):
    status, out = world.api('POST', '/api/flows/reset', body)
    assert status == code and words in out['detail']['reason'], out
    assert world.api('GET', f'/api/flows/{FLOW}')[0] == 200


def test_기준으로_되돌리기는_내_흐름만_지우고_남긴_흐름을_이름으로_알린다(world, handover):
    status, routes = world.api('GET', '/api/flows/deployments')
    deployed = {f['definition']: f['name'] for f in routes['flows']}
    status, out = world.api('POST', '/api/flows/reset', {'by': ME})
    assert status == 200, out
    assert sorted(out['kept']) == sorted(deployed.values())                      # W3-17: id 가 아니라 흐름 이름
    assert out['drafts'] >= 1 and world.api('GET', f'/api/flows/{FLOW}')[0] == 404
    assert _audit(world, 'FLOWS_RESET')[0]['actor'] == ME
    assert set(deployed) <= {h['id'] for h in world.rt.repo.deployed_heads('hyd')}


def test_부품_목록은_결과_보고의_결과_고르기를_서버_목록_하나로_준다(world):
    """화면(flows.js)은 결과 고르기를 이 목록에서 그린다 — 사본이던 화면 목록이 서버에 새 결과(정비 요청 등록 · 실행하지 않음)가 생기자 어긋났다."""
    from procsvc import effect_parts
    status, cat = world.api('GET', '/api/flows/catalog')
    assert status == 200 and cat['report_outcomes'] == list(effect_parts.REPORT_OUTCOMES)
    assert {'정비 요청 등록', '실행하지 않음'} <= set(cat['report_outcomes'])
