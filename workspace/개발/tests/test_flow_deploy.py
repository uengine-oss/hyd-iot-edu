"""흐름 배포 표 · 기준 흐름으로 되돌리기(procsvc/flow_deploy.py) — 수업 흐름은 시작이 설치하고, 화면 · API 의 되돌리기는 남긴다."""
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
        world._course_flows()           # 시작.bat 을 다시 실행한 것과 같은 길로 다시 설치


@pytest.mark.parametrize('body, words', [({'by': ' '}, '되돌린 사람'), ({}, None)])
def test_되돌린_사람이_없으면_되돌리지_않는다(world, body, words):
    status, out = world.api('POST', '/api/flows/deploy-reset', body)
    assert status in (409, 422) and _class_heads(world) >= CLASS_FLOWS
    if words:
        assert words in out['detail']
