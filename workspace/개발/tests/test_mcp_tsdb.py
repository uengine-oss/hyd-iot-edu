"""시계열 읽기(agentsvc.tools.mcp_tsdb) — agent 가 근거(Evidence) 판정 · 최신 값 · 팬 연속 운전 시간 · 학생 질의를 시계열 DB 에서 읽는 길.

시계열은 실제 timescaledb(픽스처 timescale — compose 이미지 · init.sql · reader.sql 그대로), 읽기는 agent 가 compose 에서 받는 값 그대로
(TSDB_READ_DSN = 읽기 전용 계정 hyd_timeseries_reader · DAQ_PROFILE). 설비 값은 테스트마다 다른 설비 이름으로 넣어 서로 섞이지 않는다.
근거 SQL 은 수업 문서 적재가 만드는 것(procsvc.manual_knowledge.evidence_sql)을 그대로 쓴다.
"""
import importlib
import json
import math
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from conftest import HOST_ENV, ROOT, _compose_default, _compose_service, here
from hydcommon.sql_read import SqlRejected
from procsvc.manual_knowledge import evidence_sql

AGENT_ENV = ('TSDB_READ_DSN', 'DAQ_PROFILE')
SIGNED = ROOT / 'it' / 'process' / 'procsvc' / 'course_extractions.json'


def agent_env():
    """compose agent environment 중 시계열 읽기가 가져올 때 읽는 값(주소만 이 PC)."""
    return {k: here(_compose_default(v)) for k, v in _compose_service('agent')['environment'].items() if k in AGENT_ENV}


@pytest.fixture(scope='module')
def tsdb_module(timescale):
    with pytest.MonkeyPatch.context() as mp:
        for k, v in agent_env().items():
            mp.setenv(k, v)
        return importlib.import_module('agentsvc.tools.mcp_tsdb')


@pytest.fixture
def tsdb(tsdb_module):
    return tsdb_module.TimeSeriesDB()


@pytest.fixture
def asset():
    return f'T-{uuid.uuid4().hex[:8]}'


def put(timescale, asset, rows, table='tag_1s'):
    """설비 값 줄 (태그, 값, 지금부터 몇 초 전 — 음수는 미래) 을 시계열 DB 의 한 시각(now()) 기준으로 한 문장에 넣는다."""
    if not rows:
        return
    names, values, ago = (list(c) for c in zip(*rows))
    with psycopg.connect(timescale.dsn, autocommit=True) as db:
        db.execute(f'INSERT INTO {table}(time, asset, name, value) SELECT now() - make_interval(secs => s), %s, n, v '
                   'FROM unnest(%s::text[], %s::float8[], %s::float8[]) AS u(n, v, s)', (asset, names, values, ago))


def series(tag, value, start, end=0, step=1):
    """tag 를 start 초 전부터 end 초 전까지 step 초마다 같은 값으로."""
    return [(tag, value, s) for s in range(start, end - 1, -step)]


# ---------------------------------------------------------------- 만들기
@pytest.mark.parametrize('dsn', [None, ''], ids=['주소 없음', '빈 주소'])
def test_시계열_읽기_주소가_없으면_agent_가_켜질_때_까닭과_함께_실패한다(dsn):
    env = {k: v for k, v in HOST_ENV.items() if k != 'TSDB_READ_DSN'}
    env.update(PYTHONUTF8='1', DAQ_PROFILE='lite', PYTHONPATH=os.pathsep.join([str(ROOT / 'common'), str(ROOT / 'it' / 'agent')]))
    if dsn is not None:
        env['TSDB_READ_DSN'] = dsn
    done = subprocess.run([sys.executable, '-c', 'from agentsvc.tools import mcp_tsdb; mcp_tsdb.TimeSeriesDB()'], env=env,
                          capture_output=True, timeout=120)
    assert done.returncode != 0
    assert 'RuntimeError: 시계열 DB 읽기 주소(TSDB_READ_DSN)가 없습니다 — compose.yaml 의 이 서비스 environment 를 확인하세요' in done.stderr.decode('utf8')


def test_시계열_읽기는_compose_가_준_읽기_전용_계정으로_붙는다(tsdb):
    with tsdb._conn() as conn:
        assert conn.execute('SELECT current_user, current_setting(%s)', ('default_transaction_read_only',)).fetchone() == (
            'hyd_timeseries_reader', 'on')


# ---------------------------------------------------------------- 최신 값
@pytest.mark.parametrize('rows, name, value, age', [
    ([], 'TS1', None, None),
    ([('TS1', 40.0, 30), ('TS1', 45.5, 2), ('TS2', 99.0, 0)], 'TS1', 45.5, 2),
    ([('TS1', 40.0, 30), ('TS2', 99.0, 0)], 'TS2', 99.0, 0),
    ([('TS2', 99.0, 0)], 'TS1', None, None),
], ids=['값 없음', '그 태그의 가장 새 값', '다른 태그', '다른 태그만 있음'])
def test_최신_값은_그_설비_그_태그의_가장_새_값과_그_나이다(tsdb, timescale, asset, rows, name, value, age):
    put(timescale, asset, rows)
    put(timescale, f'{asset}-other', [(name, 77.0, 0)])               # 다른 설비의 더 새 값은 섞이지 않는다
    got = tsdb.latest(asset, name)
    assert got[0] == value
    assert got[1] is None if age is None else age <= got[1] < age + 1.0


# ---------------------------------------------------------------- 스키마 설명
def test_스키마_설명은_세_표의_실제_칸과_최근_5분에_관측된_계열만_낸다(tsdb, timescale, asset):
    put(timescale, asset, [('TS1', 40.0, 10), ('CE', 70.0, 400)])
    out = tsdb.describe_schema()
    assert sorted(out['tables']) == ['feat_1s', 'tag_1m', 'tag_1s']
    assert [(c['name'], c['type']) for c in out['tables']['tag_1s']] == [
        ('time', 'timestamp with time zone'), ('asset', 'text'), ('name', 'text'), ('value', 'double precision')]
    mine = [(s['asset'], s['name']) for s in out['recent_series'] if s['asset'] == asset]
    assert mine == [(asset, 'TS1')]                                   # 6분 넘은 CE 는 「최근 계열」이 아니다
    assert (out['series_window_seconds'], out['query_tool']) == (300, 'timeseries_query')


def test_최근_계열이_200개를_넘으면_200개만_내고_잘렸다고_밝힌다(tsdb, timescale, asset):
    put(timescale, asset, [(f'X{i:03d}', 1.0, 0) for i in range(201)])
    out = tsdb.describe_schema()
    assert (len(out['recent_series']), out['series_truncated']) == (200, True)


# ---------------------------------------------------------------- 학생 · 에이전트 질의
def test_질의는_행_한도를_붙여_읽고_칸_이름과_행을_낸다(tsdb, timescale, asset):
    put(timescale, asset, [('TS1', 40.0 + i, 300 - i) for i in range(250)])
    out = tsdb.query(f"SELECT value FROM tag_1s WHERE asset = '{asset}' ORDER BY time")
    assert out['statement'].endswith('LIMIT 200')
    assert (out['columns'], out['row_count'], out['at_row_limit']) == (['value'], 200, True)
    assert out['rows'][:2] == [[40.0], [41.0]]


def test_질의는_시계열_묶음_함수_time_bucket_을_쓸_수_있다(tsdb, timescale, asset):
    put(timescale, asset, [('TS1', 10.0, 25), ('TS1', 20.0, 24), ('TS1', 30.0, 5)])
    out = tsdb.query(f"SELECT time_bucket('1 hour', time) AS hour, avg(value) AS v FROM tag_1s WHERE asset = '{asset}' GROUP BY hour")
    assert sum(r[1] for r in out['rows']) / len(out['rows']) > 0 and out['at_row_limit'] is False
    assert sorted(r[1] for r in out['rows']) in ([20.0], [15.0, 30.0], [10.0, 25.0])   # 한 시간 칸 하나, 또는 정시를 걸친 두 칸


@pytest.mark.parametrize('sql, phrase', [
    ('DELETE FROM tag_1s', 'SELECT 조회 하나'),
    ('SELECT * FROM alerts', 'public 스키마의 허용된 표만'),
    ('SELECT rolname FROM pg_catalog.pg_roles', 'public 스키마의 허용된 표만'),
    ('SELECT pg_sleep(10)', '허용되지 않은 함수입니다'),
    ('SELECT 1; SELECT 2', 'SELECT 조회 하나'),
    ('', '조회문(SQL) 한 개가 필요합니다'),
], ids=['쓰기', '감사 · 경보 표', '시스템 표', '허용 밖 함수', '두 문장', '빈 문장'])
def test_질의는_세_표_밖_쓰기_허용_밖_함수를_실행_전에_거절한다(tsdb, sql, phrase):
    with pytest.raises(SqlRejected, match=phrase.replace('(', r'\(').replace(')', r'\)')):
        tsdb.query(sql)


def test_질의_결과가_응답_한도를_넘으면_일부를_전체처럼_내지_않고_좁히라고_한다(tsdb, timescale, asset):
    put(timescale, asset, [('N' * 150 + f'{i:03d}', 1.0, 0) for i in range(200)])
    with pytest.raises(ValueError, match='응답 한도 20000자를 넘었습니다'):
        tsdb.query(f"SELECT name FROM tag_1s WHERE asset = '{asset}'")


# ---------------------------------------------------------------- 근거 판정
def evidence(tag='CE', aggregate='avg', window=30, expect='lt', threshold=70, **over):
    """t1_causes 가 내는 근거 한 줄의 꼴(SQL 은 수업 문서 적재의 생성기 그대로)."""
    return dict(dict(id='evd:test', name='시험 근거', weight=1.0, expect=expect, threshold=threshold, sql=evidence_sql(tag, aggregate, window),
                     tag=tag, windowSeconds=window), **over)


@pytest.mark.parametrize('rows, given, status, value, passed', [
    (series('CE', 60.0, 34), evidence(), 'PASS', 60.0, True),
    (series('CE', 80.0, 34), evidence(), 'FAIL', 80.0, False),
    (series('CE', 69.996, 34), evidence(), 'PASS', 69.996, True),
    (series('CE', 70.0, 34), evidence(), 'FAIL', 70.0, False),
    (series('CE', 70.0, 34), evidence(expect='lte'), 'PASS', 70.0, True),
    (series('CE', 0.5, 34), evidence(expect='gte', threshold=0.5), 'PASS', 0.5, True),
    (series('TS3', 50.0, 40, step=10), evidence(tag='TS3', expect='gt', threshold=45), 'PASS', 50.0, True),
    (series('TS3', 50.0, 41, step=11), evidence(tag='TS3', expect='gt', threshold=45), 'PASS', 50.0, True),
    (series('CE', 60.0, 34), evidence() | {'tag': None, 'windowSeconds': None}, 'PASS', 60.0, True),
], ids=['낮음 → 통과', '높음 → 불통과', '임계 바로 아래는 반올림하지 않는다', '같으면 lt 는 불통과', '같으면 lte 는 통과', 'gte',
        '데드밴드 태그는 하트비트(10초) 안의 침묵을 관측으로 친다', '하트비트 + 여유 2초 안의 11초 간격도 관측', '창 선언이 없는 근거는 값으로만'])
def test_근거는_관측된_창의_값을_임계와_비교해_통과_불통과를_낸다(tsdb, timescale, asset, rows, given, status, value, passed):
    put(timescale, asset, rows)
    got = tsdb.evaluate([given], asset)['evd:test']
    assert (got['status'], got['passed'], got.get('reason')) == (status, passed, None) and got['value'] == pytest.approx(value, abs=1e-9)
    if given['tag'] is None:
        assert got['coverage'] is None
    else:
        assert got['coverage']['covered'] is True and got['coverage']['window_s'] == float(given['windowSeconds'])


@pytest.mark.parametrize('rows, given, reason, value', [
    ([], evidence(), 'NO_DATA', None),
    (series('CE', 60.0, 34, 20), evidence(), 'OBSERVATION_GAP', 60.0),
    (series('TS3', 50.0, 39, step=13), evidence(tag='TS3', expect='gt', threshold=45), 'OBSERVATION_GAP', 50.0),
    ([('CE', 60.0, 400)], evidence(), 'NO_DATA', None),
], ids=['값 없음', '창의 끝 20초가 비었다', '데드밴드 태그도 하트비트 + 여유를 넘는 13초 간격은 공백', '창 밖의 오래된 값만'])
def test_관측되지_않은_창은_거짓이_아니라_판정하지_않음이다(tsdb, timescale, asset, rows, given, reason, value):
    put(timescale, asset, rows)
    got = tsdb.evaluate([given], asset)['evd:test']
    assert (got['status'], got['passed'], got['reason'], got['value']) == ('UNKNOWN', None, reason, value)
    if reason == 'OBSERVATION_GAP':
        assert got['coverage']['covered'] is False and got['coverage']['max_gap_s'] > got['coverage']['limit_s']


@pytest.mark.parametrize('given, kind', [
    (evidence(sql=None), 'INVALID'),
    (evidence(expect='ne'), 'INVALID'),
    (evidence(threshold='abc'), 'INVALID'),
    (evidence(threshold=True), 'INVALID'),
    (evidence(threshold=float('inf')), 'INVALID'),
    (evidence(sql='SELECT value FROM tag_1s WHERE asset = %(asset)s'), 'INVALID'),
    (evidence(sql='SELECT 1 AS a, 2 AS b'), 'INVALID'),
    (evidence(sql="SELECT 'abc' AS value"), 'INVALID'),
    (evidence(sql='SELECT true AS value'), 'INVALID'),
    (evidence(sql='SELECT count(*) AS value FROM alerts'), 'INVALID'),
    (evidence(sql='SELECT avg(nope) AS value FROM tag_1s WHERE asset = %(asset)s'), 'INVALID'),
    (evidence(windowSeconds=None), 'INVALID'),
    (evidence(windowSeconds=0), 'INVALID'),
    (evidence(windowSeconds=True), 'INVALID'),
    (evidence() | {'tag': 'XYZ'}, 'INVALID'),
    (evidence(sql='SELECT 1 / 0 AS value'), 'UNKNOWN'),
], ids=['SQL 없음', '모르는 비교', '임계가 수가 아님', '임계가 참거짓', '임계 무한', '여러 행', '여러 칸', '글자 값', '참거짓 값', '허용 밖 표',
        '없는 칸', '태그만 있고 창 없음', '창 0초', '창이 참거짓', '수집 계약에 없는 태그', '실행 중 자료 오류(0으로 나눔)'])
def test_근거_정의나_SQL_이_틀리면_판정하지_않고_오류의_종류를_가른다(tsdb, timescale, asset, given, kind):
    put(timescale, asset, series('CE', 60.0, 34))
    got = tsdb.evaluate([given], asset)['evd:test']
    assert (got['status'], got['passed'], got['reason'], got['error_kind']) == ('UNKNOWN', None, 'QUERY_ERROR', kind)
    assert got['error']


def test_틀린_근거_하나가_같은_묶음의_다른_근거_판정을_막지_않는다(tsdb, timescale, asset):
    put(timescale, asset, series('CE', 60.0, 34))
    out = tsdb.evaluate([evidence(id='evd:bad', sql='SELECT avg(nope) AS value FROM tag_1s'), evidence(id='evd:good')], asset)
    assert (out['evd:bad']['reason'], out['evd:good']['status']) == ('QUERY_ERROR', 'PASS')


def test_같은_id_의_근거는_처음_것만_판정한다(tsdb, timescale, asset):
    put(timescale, asset, series('CE', 60.0, 34))
    out = tsdb.evaluate([evidence(), evidence(sql='SELECT 1 / 0 AS value')], asset)
    assert list(out) == ['evd:test'] and out['evd:test']['status'] == 'PASS'


def test_근거는_그_설비의_값만_본다(tsdb, timescale, asset):
    put(timescale, asset, series('CE', 60.0, 34))
    put(timescale, f'{asset}-other', series('CE', 99.0, 34))
    assert tsdb.evaluate([evidence()], asset)['evd:test']['value'] == 60.0


def _signed_evidence():
    payload = json.loads(SIGNED.read_text(encoding='utf8'))['payload']
    return [e for doc in payload['documents'].values() for e in ((doc.get('proposal') or {}).get('knowledge') or {}).get('evidence') or []]


@pytest.mark.parametrize('side', ['아래', '위'])
def test_서명된_수업_지식의_근거_규칙은_시계열_판독기가_모두_판정한다(tsdb, timescale, side):
    """강사가 서명한 수업 문서 추출(course_extractions.json)의 근거 규칙 전부를, 적재가 만드는 SQL 그대로 판정한다 — 창 전체가 관측된 일정한
    값이면 판정 불가(UNKNOWN)가 하나도 없고, 통과 여부는 그 규칙의 비교 방향대로다."""
    rules = _signed_evidence()
    assert len(rules) >= 6                                             # 쿨러 4 · 정기 정비 2
    for e in rules:
        asset, t = f'T-{uuid.uuid4().hex[:8]}', float(e['threshold'])
        value = t * (0.5 if side == '아래' else 1.5)
        put(timescale, asset, series(e['tag'], value, e['window_seconds'] + 4))
        given = dict(id=e['id'], name=e['name'], weight=e['weight'], expect=e['expect'], threshold=e['threshold'],
                     sql=evidence_sql(e['tag'], e['aggregate'], e['window_seconds']), tag=e['tag'], windowSeconds=e['window_seconds'])
        got = tsdb.evaluate([given], asset)[e['id']]
        observed = 0.0 if e['aggregate'] == 'range' else value
        holds = {'lt': observed < t, 'lte': observed <= t, 'gt': observed > t, 'gte': observed >= t, 'eq': observed == t}[e['expect']]
        assert (e['id'], got['status'], got['coverage']['covered']) == (e['id'], 'PASS' if holds else 'FAIL', True)


# ---------------------------------------------------------------- 팬 연속 운전 시간
@pytest.mark.parametrize('scale', [0, -1, float('nan'), float('inf'), True, '20', None],
                         ids=['0', '음수', 'NaN', '무한', '참거짓', '글자', '없음'])
def test_팬_운전_시간의_배속이_양의_유한한_수가_아니면_까닭과_함께_실패한다(tsdb, asset, scale):
    with pytest.raises(ValueError, match='팬 연속 운전 시간을 설비 시간으로 바꿀 배율이 올바르지 않습니다'):
        tsdb.fan100_hours(asset, time_scale=scale)


H = 3600


@pytest.mark.parametrize('rows, scale, hours', [
    ([], 20, None),
    ([(100.0, 49 * H)], 20, None),
    ([(100.0, 600), (50.0, 0)], 20, 0.0),
    ([(100.0, H), (100.0, H // 2), (100.0, 0)], 20, 20.0),
    ([(100.0, H), (100.0, 0)], 20.0, 20.0),
    ([(99.0, H), (99.0, 0)], 1, 1.0),
    ([(100.0, H), (98.9, H // 2), (100.0, H // 4), (100.0, 0)], 1, 0.25),
    ([(100.0, 49 * H), (100.0, H), (100.0, 0)], 1, 1.0),
    ([(100.0, 0)], 20, 0.0),
], ids=['값 없음은 0시간이 아니라 모름', '48시간보다 오래된 값만', '지금 99 % 아래', '끊김 없는 실제 1시간 = 배속 20 에서 설비 20시간',
        '배속은 소수여도 된다', '99 % 는 운전으로 센다', '98.9 % 는 끊김 — 그 뒤부터 센다', '48시간 창 밖의 시작은 세지 않는다', '막 99 % 에 닿은 한 줄'])
def test_팬_연속_운전_시간은_마지막_끊김_뒤부터_지금까지의_설비_시간이다(tsdb, timescale, asset, rows, scale, hours):
    put(timescale, asset, [('FanSpeedSP', v, ago) for v, ago in rows])
    assert tsdb.fan100_hours(asset, time_scale=scale) == hours


# ---------------------------------------------------------------- 관측 덮음(순수 함수)
T0 = datetime(2026, 10, 30, tzinfo=timezone.utc)


def at(*seconds):
    return [T0 + timedelta(seconds=s) for s in seconds]


@pytest.mark.parametrize('times, now_s, limit, covered, samples, max_gap', [
    (at(0, *range(1, 31)), 30, 3, True, 30, 1.0),
    (at(0, *range(1, 11), *range(15, 31)), 30, 3, False, 26, 5.0),
    (at(0, *range(1, 11), *range(14, 31)), 30, 4, True, 27, 4.0),
    (at(-1), 10, 12, True, 0, 11.0),
    (at(-1), 30, 12, False, 0, 31.0),
    ([], 30, 60, False, 0, 30.0),
    (at(0, *range(1, 31), 31, 40), 30, 3, True, 30, 1.0),
], ids=['매초 표본', '가운데 5초 공백은 한도 3초 밖', '공백이 한도와 같으면 관측', '창 앞 표본 하나 · 하트비트 안', '창 앞 표본 하나 · 하트비트 밖',
        '표본 없음은 한도가 커도 관측 아님', '지금 뒤의 표본은 세지 않는다'])
def test_창의_모든_순간이_어느_표본의_한도_안에_있어야_관측된_창이다(times, now_s, limit, covered, samples, max_gap):
    out = observation_coverage(times, T0, T0 + timedelta(seconds=now_s), limit)
    assert (out['covered'], out['samples'], out['max_gap_s'], out['limit_s']) == (covered, samples, max_gap, limit)


def observation_coverage(*args):
    from agentsvc.tools.mcp_tsdb import observation_coverage as fn
    return fn(*args)
