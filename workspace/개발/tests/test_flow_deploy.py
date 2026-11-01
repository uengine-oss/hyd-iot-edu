"""흐름 배포 표 · 기준 흐름으로 되돌리기 · 기준과 비교(procsvc/flow_deploy.py) — 수업 흐름은 시작이 설치하고, 화면 · API 의 되돌리기는 남긴다.
「기준과 비교」의 기준은 흐름마다 다르다(학생 경보 흐름 = 그 경보를 원래 여는 흐름)."""
import copy
import uuid

import pytest

from procsvc import flow_deploy

CLASS_FLOWS = {'c3_cooling', 'c3_pm', 'c3_spare'}


def _class_heads(world):
    return {h['id'] for h in world.rt.repo.deployed_heads(world.rt.tenant_id) if h.get('class_flow')}


def test_시작이_설치한_수업_흐름은_수업_표시와_함께_경보를_연다(world):
    status, out = world.api('GET', '/api/flows/deployments')
    assert status == 200 and _class_heads(world) >= CLASS_FLOWS
    assert {f['definition'] for f in out['flows'] if f['class_flow']} >= CLASS_FLOWS


@pytest.mark.parametrize('body', [
    {'by': 'user:kim-op'},
    {'by': 'user:kim-op', 'include_class': True},     # 예전 강사 명령의 표시 — 지금은 보내는 쪽이 없고, 학생이 보내도 수업 흐름을 내리지 않는다
])
def test_API_로_기준_흐름으로_되돌려도_수업_흐름은_남는다(world, body):
    status, out = world.api('POST', '/api/flows/deploy-reset', body)
    assert status == 200, out
    assert {k['definition'] for k in out['kept']} >= CLASS_FLOWS and out['include_class'] is False
    assert _class_heads(world) >= CLASS_FLOWS


def test_출발본_불러오기의_되돌리기만_수업_흐름까지_내린다(world):
    out = flow_deploy.deploy_reset(world.rt, 'user:kim-op', '출발본 불러오기', include_class=True)
    try:
        assert out['kept'] == [] and not (_class_heads(world) & CLASS_FLOWS)
    finally:
        world.install_course_flows()    # 시작.bat 을 다시 실행한 것과 같은 길로 다시 설치


@pytest.fixture
def student_deployed(world):
    """학생이 배포한 흐름 하나(되돌리기가 내릴 것) — 거절된 되돌리기가 정말 아무것도 내리지 않았는지 보려고."""
    head = next(h for h in world.rt.repo.deployed_heads('hyd') if h['id'] == 'c3_cooling')
    raw = copy.deepcopy(world.rt.repo.get_proc_def('c3_cooling', 'hyd', version=head['prod_version'])['definition'])
    def_id = 'my_reset_' + uuid.uuid4().hex[:8]
    raw.update(processDefinitionId=def_id, version='1')
    world.rt.register_definition(raw)
    world.rt.deploy_definition(def_id, '1', 'user:kim-op', '되돌리기 거절 확인')
    yield def_id
    if def_id in {h['id'] for h in world.rt.repo.deployed_heads('hyd')}:
        world.rt.repo.clear_deployment(def_id, 'hyd', actor='user:kim-op', reason='테스트 끝')


def _heads(world):
    return {h['id'] for h in world.rt.repo.deployed_heads('hyd')}


@pytest.mark.parametrize('body, status, words', [
    ({'by': ' '}, 400, '누가 되돌렸는지 모릅니다'),                    # 사람 칸은 있으나 비었다
    ({}, 400, '누가 되돌렸는지 모릅니다'),                             # 사람 칸이 없다
    ({'by': '수강생 김'}, 403, "'나'(사람 사용자)를 고른 뒤"),         # 이름만 적은 자유 입력 — 배포 이력에 지어낸 이름이 남던 것(FW2)
    ({'by': 'user:nobody'}, 403, '없는 사람 사용자입니다: user:nobody'),
], ids=['빈 칸', '칸 없음', '자유 입력', '없는 사람'])
def test_되돌린_사람이_등록된_사람이_아니면_되돌리지_않는다(world, student_deployed, body, status, words):
    got, out = world.api('POST', '/api/flows/deploy-reset', body)
    assert got == status and words in out['detail'], out
    assert student_deployed in _heads(world) and _class_heads(world) >= CLASS_FLOWS


def test_고른_사람이면_되돌리고_학생_흐름을_내린다(world, student_deployed):
    status, out = world.api('POST', '/api/flows/deploy-reset', {'by': 'user:kim-op', 'reason': '수업 끝'})
    assert status == 200, out
    assert student_deployed not in _heads(world) and _class_heads(world) >= CLASS_FLOWS


@pytest.fixture
def student_cooling(world):
    """학생이 냉각 경보로 시작하게 만든 흐름 하나(수업 흐름 c3_cooling 의 정의를 다른 id 로) — 등록 · 배포, 끝나면 배포를 내린다."""
    head = next(h for h in world.rt.repo.deployed_heads('hyd') if h['id'] == 'c3_cooling')
    raw = copy.deepcopy(world.rt.repo.get_proc_def('c3_cooling', 'hyd', version=head['prod_version'])['definition'])
    def_id = 'my_cooling_' + uuid.uuid4().hex[:8]
    raw.update(processDefinitionId=def_id, version='1')             # 내용은 수업 흐름 그대로 — 비교하면 같아야 한다
    world.rt.register_definition(raw)
    world.rt.deploy_definition(def_id, '1', 'user:kim-op', '비교 기준 확인')
    yield def_id
    world.rt.repo.clear_deployment(def_id, 'hyd', actor='user:kim-op', reason='테스트 끝')


def test_기준과_비교의_기준은_흐름마다_그_경보를_원래_여는_흐름이다(world, student_cooling):
    rt = world.rt
    base = flow_deploy.compare_base(rt, student_cooling)
    assert base['definition'] == 'c3_cooling' and base['pattern'] == 'COOLER_DEGRADATION'   # 이 흐름이 없을 때 냉각 경보를 여는 흐름
    assert base['why'] == '이 흐름이 없을 때 같은 경보를 여는 흐름'                        # 까닭 문장에 경보 코드가 없다 — 이름표는 화면이 pattern 으로(FW2)
    assert flow_deploy.compare_base(rt, rt.defn.id) == {'definition': rt.defn.id, 'version': rt.base_version, 'name': rt.defn.name,
                                                        'pattern': None, 'why': '기준 흐름의 기준 판본'}
    assert flow_deploy.compare_base(rt, 'c3_cooling') is None                                # 강사가 설치한 수업 흐름 — 그 자체가 기준
    assert flow_deploy.compare_base(rt, 'shift_handover') is None                            # 경보로 시작하지 않는 흐름


def test_기준과_비교는_같은_흐름이면_같다고_하고_기준이_없으면_까닭과_함께_거절한다(world, student_cooling):
    status, same = world.api('GET', f'/api/flows/deploy-compare?definition={student_cooling}&version=1')
    assert status == 200 and same['reference']['definition'] == 'c3_cooling' and same['same'] is True, same
    assert same['summary'] == f"「{same['reference']['name']}」와 같습니다"
    status, out = world.api('GET', '/api/flows/deploy-compare?definition=c3_cooling')
    assert status == 409 and '견줄 기준 흐름이 없습니다' in out['detail'], out
