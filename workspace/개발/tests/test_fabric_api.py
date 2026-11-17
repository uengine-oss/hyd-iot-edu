"""데이터 연결 API(procsvc/fabric_api.py) — 업무 DB · 시계열 DB 를 전용 읽기 계정으로만 읽고, 입력 오류 400 · 원천 실패 503 을 가른다.

실제 process 앱의 라우트(world.api)와 실제 업무 DB · 시계열 컨테이너 · 그래프로 부른다.
"""
import pytest


def test_세_원천의_연결_상태와_표_목록은_읽기_전용_계정으로_읽는다(world):
    status, body = world.api('GET', '/api/fabric/sources')
    assert status == 200, body
    sources = {s['id']: s for s in body}
    assert set(sources) == {'hyd-enterprise', 'hyd-legacy', 'hyd-timeseries'} and all(s['ok'] and s['read_only'] for s in sources.values()), body


def test_표의_열과_최신_샘플을_읽는다(world):
    status, tables = world.api('GET', '/api/fabric/sources/hyd-enterprise/tables')
    assert status == 200 and any(t['name'] == 'work_orders' for t in tables['tables']), tables
    status, sample = world.api('GET', '/api/fabric/sources/hyd-enterprise/tables/work_orders/sample?limit=2')
    assert status == 200 and sample['row_count'] <= 2 and sample['statement'].lower().startswith('select'), sample


@pytest.mark.parametrize('path, code', [
    ('/api/fabric/sources/no-such-source/tables', 404),
    ('/api/fabric/sources/hyd-enterprise/tables/no_such_table/sample', 400),
], ids=['등록 안 된 원천', '없는 표'])
def test_모르는_원천과_표는_까닭과_함께_거절한다(world, path, code):
    """원천 이름은 등록된 둘, 표 이름은 읽기 계정이 보는 목록에 있는 것만 SQL 에 닿는다."""
    status, body = world.api('GET', path)
    assert status == code and body['detail'], body


@pytest.mark.parametrize('sql', ['delete from ent.work_orders', 'select 1; select 2'], ids=['쓰기', '두 문장'])
def test_직접_실행하는_질의는_읽기_전용_SELECT_한_문장만_받는다(world, sql):
    status, body = world.api('POST', '/api/fabric/query', {'asset': 'HYD-01', 'query': 'sql', 'sql': {'hyd-enterprise': sql}})
    assert status == 400 and '읽기 전용 SELECT만 실행합니다' in body['detail'], body


def test_정의된_교차_조회_목록과_클래스_연결을_읽는다(world):
    status, queries = world.api('GET', '/api/fabric/queries')
    assert status == 200 and queries, queries
    status, links = world.api('GET', '/api/fabric/links')
    assert status == 200 and links['classes'] and links['graph']['ok'], links.get('graph')


def test_설비_코드_없이_묶어_보기를_부르면_입력_오류다(world):
    status, body = world.api('POST', '/api/fabric/query', {'asset': ' ', 'query': 'asset'})
    assert status == 400 and '설비 코드가 필요합니다' in body['detail'], body


def test_제공_옛_설비_DB_파일을_잇고_되돌리면_원래_상태다(world):
    """실라버스 통합 40행: 제공 파일 미리보기(원천을 고르지 않음) → 적재 → 「판단 입력의 원천」이 옛 설비 DB 의 살아 있는 열(OK) ·
    그 표의 샘플 행 = 파일 행 → 배치 되돌리기 → 입력 수 · 배치 목록이 처음과 같다."""
    from pathlib import Path
    text = (Path(__file__).resolve().parents[3] / 'it' / 'portal' / 'www' / 'samples' / 'legacy-plant-db.sql').read_text(encoding='utf-8')

    def state():
        status, rows = world.api('GET', '/api/kg/ingests')
        assert status == 200, rows
        status, links = world.api('GET', '/api/fabric/links')
        assert status == 200, links
        return {r['batch'] for r in rows}, links['inputs']
    batches0, inputs0 = state()
    status, plan = world.api('POST', '/api/kg/ddl/preview', {'filename': 'legacy-plant-db.sql', 'text': text,
                                                             'systems': {'T_EQP00': 'sys:cmms', 'T_EQP01': 'sys:cmms', 'T_MNT10': 'sys:cmms'}})
    assert status == 200 and plan['datasource'] == 'hyd-legacy' and plan['inputs'], plan
    assert {i['schema'] for i in plan['inputs']} == {'legacy'} and {o['id'] for o in plan['sourceOptions']} == {'hyd-enterprise', 'hyd-legacy'}
    status, out = world.api('POST', '/api/kg/ddl/commit', dict(plan, by='시험'))
    assert status == 200, out
    _, inputs = state()
    legacy = [i for i in inputs if i.get('datasource') == 'hyd-legacy']
    assert len(legacy) == len(plan['inputs']) and all(i['state'] == 'OK' and i['source_label'] == '옛 설비 DB' for i in legacy), \
        [(i['table'], i['column'], i['state'], i.get('reason')) for i in legacy]
    status, sample = world.api('GET', '/api/fabric/sources/hyd-legacy/tables/T_EQP00/sample?limit=20')
    assert status == 200 and sample['row_count'] == 4, sample                                  # 파일의 T_EQP00 INSERT 4행
    status, refused = world.api('DELETE', f"/api/kg/ingests/{out['batch']}")              # 「누가」 없이 온 되돌리기는 지우지 않는다
    assert status == 400 and '담당자 정보 없이 온 요청' in refused['detail'] and out['batch'] in state()[0], refused
    status, cleared = world.api('DELETE', f"/api/kg/ingests/{out['batch']}?by=user:me")    # 화면이 보내는 꼴(hitl.js — 이 PC의 담당자 id)
    assert status == 200, cleared
    batches, inputs = state()
    assert batches == batches0 and sorted(i['id'] for i in inputs) == sorted(i['id'] for i in inputs0)
