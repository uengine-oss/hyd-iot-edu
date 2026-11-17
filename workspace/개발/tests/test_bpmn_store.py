"""가져온 흐름의 저장(procsvc/bpmn_store.py) — 초안 · 학생 판본(불변) · 기준으로 되돌리기. 실제 업무 DB(시드 테넌트 hyd).

판본 번호는 그 흐름 id 에 한 번이라도 쓰인 번호 다음이다 — 되돌리기 뒤에도 같은 번호를 다른 원문에 다시 쓰지 않는다(P5-24).
"""
import json
import uuid

import pytest

from procsvc.bpmn_store import FlowBusy, FlowStore, next_version
from procsvc.course_policy import HANDOVER

FLOW = 'ShiftHandover'


@pytest.mark.parametrize('used, want', [
    ([], '1'),
    (['1'], '2'),
    (['1', '2', '9', '10'], '11'),           # 글자 순(「9」 > 「10」)이 아니라 숫자 순
    (['1', 'draft', None, '2.2'], '2'),       # 숫자가 아닌 판본(기준 정의의 2.2 등)은 학생 번호가 아니다
])
def test_다음_판본_번호는_쓰인_숫자_판본의_가장_큰_것_다음이다(used, want):
    assert next_version(used) == want


@pytest.fixture
def store(world):
    status, out = world.api('DELETE', f'/api/flows/{FLOW}?by=user:me')
    assert status in (200, 404), out
    return FlowStore(world.rt.repo, world.rt.tenant_id)


def _register(world):
    status, out = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200, out
    status, out = world.api('POST', f'/api/flows/{FLOW}/register', {'mapping': HANDOVER['mapping'], 'by': 'user:me'})
    assert status == 201, out
    return out['version']


def test_등록할_때마다_새_판본이고_앞_판본은_그대로_남는다(world, store):
    first = _register(world)
    second = _register(world)
    assert int(second) == int(first) + 1
    assert [v['version'] for v in store.versions(FLOW)][-2:] == [first, second]
    assert store.bpmn_of(FLOW, first) == HANDOVER['xml'] and store.next_version(FLOW) == str(int(second) + 1)


def test_배포했다가_내리고_지운_흐름을_다시_등록해도_옛_번호를_다시_쓰지_않는다(world, store):
    old = _register(world)
    world.rt.deploy_definition(FLOW, old, 'user:me', '번호 확인')
    world.rt.repo.clear_deployment(FLOW, 'hyd', actor='user:me', reason='번호 확인')
    out = store.reset(FLOW)
    assert out['versions'] >= 1 and store.versions(FLOW) == []
    again = _register(world)
    assert int(again) > int(old), (old, again)            # 배포 기록이 그 번호를 가리킨다 — 다른 원문에 같은 번호를 주지 않는다


def test_되돌리기는_진행_중인_처리_건이_있으면_아무것도_지우지_않고_흐름_이름으로_알린다(world, store):
    version = _register(world)
    inst = world.rt.start_definition(FLOW, version, 'store-test:' + uuid.uuid4().hex,
                                     values={'asset': 'HYD-01', 'shift_label': '다음 교대', 'as_of': world.now_iso(),
                                             'work_notes': '작업 메모'})
    with pytest.raises(FlowBusy) as caught:
        store.reset(FLOW)
    message = str(caught.value)
    assert '진행 중인 처리 건 1건' in message and f'(판본 {version}' in message
    assert inst['proc_inst_id'] not in message                                    # 내부 처리 건 id 가 아니라 이름 · 판본 · 시작 시각
    assert [v['version'] for v in store.versions(FLOW)] == [version]
    assert caught.value.running[0]['proc_inst_id'] == inst['proc_inst_id']        # 화면이 그 처리 건으로 갈 수 있게 목록에는 id
    json.loads(json.dumps(caught.value.running))                                  # 그 목록이 409 본문에 그대로 실린다(datetime 이면 500)
    assert isinstance(caught.value.running[0]['start_date'], str)


def test_기준_정의_id는_보호되고_학생_흐름_id는_아니다(world, store):
    assert store.is_protected(world.rt.defn.id) is True
    assert store.is_protected('shift_handover') is True
    _register(world)
    assert store.is_protected(FLOW) is False


def test_되돌리기는_남길_흐름을_지우지_않고_돌려준다(world, store):
    _register(world)
    keep = {FLOW} | {h['id'] for h in world.rt.repo.deployed_heads('hyd')}      # 배포된 수업 흐름도 남긴다(다른 테스트가 쓴다)
    out = store.reset(keep=keep)
    assert out['kept'] == sorted(keep) and [v['version'] for v in store.versions(FLOW)]
    assert store.get_draft(FLOW) is not None
