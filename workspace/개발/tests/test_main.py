"""process HTTP(procsvc/main.py) — 학생 PC 의 단 하나의 구성만 남았다(옛 처리 엔진 · 메모리판 경로 없음)."""
import pytest


@pytest.mark.parametrize('method, path', [
    ('POST', '/api/incidents'),                                 # 옛 자동 파이프라인의 가이드 카드 진입
    ('POST', '/api/incidents/INC-x/approve'), ('POST', '/api/incidents/INC-x/reject'),
    ('POST', '/api/incidents/INC-x/decide'), ('POST', '/api/incidents/INC-x/decision-preview'),
    ('POST', '/api/incidents/INC-x/work-order-retry'),
    ('POST', '/api/decisions/D-x/approve'), ('POST', '/api/decisions/D-x/reject'),
])
def test_처리_건_밖의_옛_승인_경로는_없다(world, method, path):
    status, _ = world.api(method, path, {})
    assert status in (404, 405)


def test_사건_판단_조회와_경보_정책은_처리_엔진으로_답한다(world):
    alert, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01')
    status, incidents = world.api('GET', '/api/incidents')
    assert status == 200 and any(i['id'] == world.values(pid)['incident'] for i in incidents)
    status, policy = world.api('GET', '/api/alerts/policy?pattern=COOLER_DEGRADATION')
    assert status == 200 and policy['target']['definition'] == 'c3_cooling'


@pytest.mark.parametrize('body', [{'filename': 'schema.sql'}, {'filename': 'schema.sql', 'text': '   '},
                                  {'filename': 'schema.sql', 'data': 'Q1JFQVRFIFRBQkxFIHQoYSBpbnQpOw=='}])
def test_DDL_미리보기는_글이_비면_쉬운_말로_거절한다(world, body):
    """예전 base64(data) 갈래는 읽는 함수가 없어 부르면 내부 오류(이름 없음)가 학생 화면에 나왔다."""
    status, out = world.api('POST', '/api/kg/ddl/preview', body)
    assert status == 400 and 'CREATE TABLE' in out['detail'] and 'not defined' not in out['detail']
