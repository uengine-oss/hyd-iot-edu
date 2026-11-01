"""데이터 연결(common/hydcommon/fabric.py) — 업무 DB(ent)와 시계열 DB(세 표)를 전용 읽기 계정으로만 읽어 한 질문에 묶는다.

판정:
- guard_for: 원천마다 같은 읽기 SELECT 계약(업무 DB 는 ent 표만, 시계열은 tag_1s · feat_1s · tag_1m 과 time_bucket 만).
- env_connectors: 연결 주소는 ENTERPRISE_READ_DSN · TSDB_READ_DSN 하나씩(G3b-26 — 옛 TSDB_DSN 은 받지 않는다), 전용 계정 확인을 거친다.
- failure_reason: 실제 연결 · 조회 실패를 사람이 읽는 한국어 문장으로(원문은 detail). 실패는 실제로 일으켜 본다.
- Fabric: 한 원천만 실패하면 부분 답(partial), 다 실패하면 FabricUnavailable(빈 성공 없음), 직접 쓴 SQL 은 연결 전에 가드,
  교차 조회의 기준값은 지식 그래프에서 읽는다(코드 상수 아님).
실제 테스트 업무 DB(pg_dsn), 이 테스트 자리의 시계열 컨테이너(timescale), 시드 그래프(seeded_graph)에 붙는다.
"""
import re
import socket
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest

from hydcommon import fabric
from hydcommon.enterprise import reader_connection
from hydcommon.fabric import ENT, TS, Fabric, FabricUnavailable, SourceUnavailable, SqlRejected
from conftest import as_user, ent_reader, ts_reader


def _dead_dsn():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    return f'postgresql://u:p@127.0.0.1:{port}/x'


@pytest.fixture
def readers(pg_dsn, timescale):
    return {'ENTERPRISE_READ_DSN': ent_reader(pg_dsn), 'TSDB_READ_DSN': ts_reader(timescale)}


@pytest.fixture
def fab(readers, seeded_graph):
    return Fabric(fabric.env_connectors(readers), seeded_graph.query)


@pytest.fixture
def tags(timescale):
    """시계열을 비우고 HYD-01 의 지금 값 몇 개를 넣는다(connect-sink 가 막 적재한 것처럼)."""
    timescale.clear()
    timescale.write('HYD-01', {'TS1': 51.25, 'LoadSP': 90, 'VS1': 0.61, 'NOT_IN_GRAPH': 1})
    yield
    timescale.clear()


# ---------------------------------------------------------------- 가드 · 설정 (DB 없이)
@pytest.mark.parametrize('source, sql, ok', [
    (ENT, 'select part_no from parts', True),
    (ENT, 'select * from public.users', False),
    (ENT, 'select * from tag_1s', True),                    # 업무 DB 가드는 ent 안의 이름으로 본다(없으면 DB 가 거절)
    (TS, "select time_bucket('1 minute', time), avg(value) from tag_1s group by 1", True),
    (TS, 'select * from alerts', False),
    (TS, 'select * from sink_offsets', False),
    (TS, 'delete from tag_1s', False),
], ids=['업무 표', '업무 DB 다른 스키마', '업무 DB 모르는 표 이름', '시계열 time_bucket', '시계열 경보 표', '시계열 오프셋 표', '시계열 쓰기'])
def test_원천마다_읽기_SELECT_계약으로_가드한다(source, sql, ok):
    if ok:
        assert fabric.guard_for(source, sql, 10).endswith('LIMIT 10')
    else:
        with pytest.raises(SqlRejected):
            fabric.guard_for(source, sql, 10)


def test_등록되지_않은_원천은_가드에서_거절한다():
    with pytest.raises(ValueError, match='등록되지 않은 원천'):
        fabric.guard_for('hyd-other', 'select 1', 10)


@pytest.mark.parametrize('env, source, word', [
    ({}, ENT, 'ENTERPRISE_READ_DSN'),
    ({}, TS, 'TSDB_READ_DSN'),
    ({'TSDB_DSN': 'postgresql://hyd_timeseries_reader:x@127.0.0.1:1/hyd'}, TS, 'TSDB_READ_DSN'),   # G3b-26: 옛 이름은 읽지 않는다
    ({'TSDB_READ_DSN': ''}, TS, 'TSDB_READ_DSN'),
], ids=['업무 주소 없음', '시계열 주소 없음', '옛 시계열 이름만', '빈 주소'])
def test_연결_주소가_없으면_그_환경_변수_이름을_말한다(env, source, word):
    with pytest.raises(SourceUnavailable) as caught:
        fabric.env_connectors(env)[source]()
    assert word in caught.value.reason and caught.value.reason.startswith('연결 설정이 없습니다')


@pytest.mark.parametrize('value, expected', [
    (Decimal('12'), 12), (Decimal('12.50'), 12.5), (datetime(2026, 10, 30, 5, tzinfo=timezone.utc), '2026-10-30T05:00:00+00:00'),
    (UUID(int=1), '00000000-0000-0000-0000-000000000001'), ({'a': [Decimal('1'), None]}, {'a': [1, None]}), (b'x', "b'x'"),
], ids=['정수 십진', '소수 십진', '시각', 'UUID', '안쪽 값', '그 밖'])
def test_DB_값은_JSON_값으로_바꾼다(value, expected):
    assert fabric.jsonable(value) == expected


@pytest.mark.parametrize('name, quoted', [('tag_1s', '"tag_1s"'), ('a"b', '"a""b"')], ids=['보통', '따옴표'])
def test_식별자는_따옴표로_감싼다(name, quoted):
    assert fabric.ident(name) == quoted


@pytest.mark.parametrize('name', ['', 'a\x00b', None], ids=['빈 이름', 'NUL', '없음'])
def test_잘못된_식별자는_거절한다(name):
    with pytest.raises(ValueError):
        fabric.ident(name)


# ---------------------------------------------------------------- 실패 문장(실제 실패를 일으켜)
def _raised(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — 실제로 난 예외를 그대로 판정에 쓴다
        return exc
    raise AssertionError('실패가 나지 않았다')


def _run_as(dsn, *statements):
    def go():
        with psycopg.connect(dsn, connect_timeout=5) as c:
            for s in statements:
                c.execute(s)
    return go


@pytest.mark.parametrize('make, sentence', [
    (lambda pg, ts: (lambda: reader_connection(as_user(pg, 'postgres', 'postgres'))), '전용 읽기 계정이 아닌 계정으로 연결돼 거부했습니다'),
    (lambda pg, ts: _run_as(as_user(pg, 'hyd_enterprise_reader', 'wrong')), '읽기 전용 계정 인증에 실패했습니다'),
    (lambda pg, ts: _run_as(pg.rsplit('/', 1)[0] + '/hyd_test_fo2_none'), '데이터베이스 이름이 없습니다'),
    (lambda pg, ts: _run_as('postgresql://u:p@no-such-host.invalid:5432/x'), 'DB 주소(호스트 이름)를 찾을 수 없습니다'),
    (lambda pg, ts: _run_as(ent_reader(pg), 'set role fo2_nobody'), '읽기 전용 계정이 DB에 없습니다'),
    (lambda pg, ts: _run_as(ent_reader(pg), "set statement_timeout = '50ms'", 'select pg_sleep(1)'), '시간이 초과됐습니다'),
    (lambda pg, ts: _run_as(ts_reader(ts), 'select * from alerts'), '읽기 권한이 없는 표입니다'),
    (lambda pg, ts: _run_as(ent_reader(pg), "insert into ent.parts (part_no, name, std_price) values ('P-FO2', 'x', 1)"),
     '읽기 전용 연결이라 쓰기를 거부했습니다'),
    (lambda pg, ts: _run_as(ent_reader(pg), 'select no_such_column from ent.parts'), 'DB 오류: column "no_such_column" does not exist'),
], ids=['관리자 계정', '비밀번호 틀림', '없는 DB', '없는 호스트', '없는 역할', '조회 시간 초과', '권한 없는 표', '읽기 전용에 쓰기', '그 밖의 오류'])
def test_실제_연결_조회_실패를_사람이_읽는_문장으로_바꾼다(pg_dsn, timescale, make, sentence):
    exc = _raised(make(pg_dsn, timescale))
    assert sentence in fabric.failure_reason(exc), (type(exc).__name__, str(exc))


def test_원천_사유가_있는_실패는_그_사유_그대로다():
    assert fabric.failure_reason(SourceUnavailable('지식 그래프 연결이 설정되지 않았습니다', 'x')) == '지식 그래프 연결이 설정되지 않았습니다'


# ---------------------------------------------------------------- 원천 · 표 · 샘플
def test_세_원천을_전용_읽기_계정과_읽기_전용_트랜잭션으로_연다(fab):
    rows = {r['id']: r for r in fab.sources()}
    assert {s: (r['ok'], r['user'], r['read_only']) for s, r in rows.items()} == {
        ENT: (True, 'hyd_enterprise_reader', True), fabric.LEGACY: (True, 'hyd_enterprise_reader', True),
        TS: (True, 'hyd_timeseries_reader', True)}
    assert {t['name'] for t in rows[TS]['tables']} == set(fabric.TS_TABLES)
    assert 'work_orders' in {t['name'] for t in rows[ENT]['tables']}


def test_한_원천이_꺼져_있어도_다른_원천은_읽고_꺼진_쪽은_사유를_단다(readers, seeded_graph):
    fab = Fabric(fabric.env_connectors(dict(readers, ENTERPRISE_READ_DSN=_dead_dsn())), seeded_graph.query)
    rows = {r['id']: r for r in fab.sources()}
    assert rows[TS]['ok'] is True and rows[ENT]['ok'] is False and rows[ENT]['reason'] and rows[ENT]['detail']


def test_샘플은_읽기_계정이_보는_표만_최신_순으로_한도까지(fab, tags):
    out = fab.sample(TS, 'tag_1s', 2)
    assert out['row_count'] == 2 and out['statement'] == ('select * from "public"."tag_1s" where "time" > now() - interval \'1 day\' '
                                                          'order by "time" desc limit 2')
    assert fab.sample(ENT, 'parts', 1)['row_count'] == 1
    with pytest.raises(ValueError, match='읽을 수 있는 표가 아닙니다'):
        fab.sample(TS, 'alerts')
    with pytest.raises(ValueError, match='읽을 수 있는 표가 아닙니다'):
        fab.sample(ENT, 'users; drop table parts')


@pytest.mark.parametrize('limit', [0, 21, True, '5'], ids=['0', '21', '참거짓', '글'])
def test_샘플_행_한도는_1부터_20(fab, limit):
    with pytest.raises(ValueError, match='1~20'):
        fab.sample(ENT, 'parts', limit)


# ---------------------------------------------------------------- 묶어 보기
def test_설비_하나를_두_원천에서_묶어_보면_값마다_클래스와_출처가_붙는다(fab, tags):
    out = fab.query('HYD-01')
    assert out['partial'] is False and out['sources'] == {ENT: {'ok': True}, TS: {'ok': True}} and out['graph'] == {'ok': True}
    ts = {v['field']: v for v in out['answer'] if v['source'] == TS}
    assert (ts['TS1']['klass'], ts['TS1']['value'], ts['TS1']['from']) == ('Sensor', 51.25, 'public.tag_1s.value')
    assert ts['LoadSP']['klass'] == 'Actuator'
    assert ts['NOT_IN_GRAPH']['klass'] is None and ts['NOT_IN_GRAPH']['label'] == '온톨로지에 연결된 클래스 없음'   # 버리지 않는다
    ent = {v['field']: v for v in out['answer'] if v['source'] == ENT and v['klass'] == 'Asset'}
    assert ent['code']['value'] == 'HYD-01'


def test_어느_원천에도_없는_설비는_빈_답이_아니라_까닭으로_실패한다(fab, tags):
    with pytest.raises(ValueError, match='HYD-99는 업무 DB'):
        fab.query('HYD-99')


@pytest.mark.parametrize('asset', ['', '   ', 'H' * 41, None], ids=['빈', '공백', '41자', '없음'])
def test_설비_코드가_없거나_길면_입력_오류다(fab, asset):
    with pytest.raises(ValueError, match='설비 코드가 필요합니다'):
        fab.query(asset)


def test_한_원천이_꺼지면_부분_답이고_둘_다_꺼지면_답이_없다(readers, seeded_graph, tags):
    half = Fabric(fabric.env_connectors(dict(readers, ENTERPRISE_READ_DSN=_dead_dsn())), seeded_graph.query).query('HYD-01')
    assert half['partial'] is True and half['sources'][ENT]['ok'] is False and any(v['source'] == TS for v in half['answer'])
    down = Fabric(fabric.env_connectors({'ENTERPRISE_READ_DSN': _dead_dsn(), 'TSDB_READ_DSN': _dead_dsn()}), seeded_graph.query)
    with pytest.raises(FabricUnavailable) as caught:
        down.query('HYD-01')
    assert '업무 DB:' in str(caught.value) and '시계열 DB:' in str(caught.value)


def test_직접_쓴_SQL_은_원천마다_가드하고_읽는다(fab, tags):
    out = fab.query('HYD-01', 'sql', 5, {ENT: "select part_no from ent.parts where part_no = 'P-PMP-SEAL'",
                                         TS: "select name, value from tag_1s where name = 'TS1'"})
    rows = {p['id']: p['rows'] for p in out['parts']}
    assert rows == {ENT: [['P-PMP-SEAL']], TS: [['TS1', 51.25]]} and all(p['statement'].endswith('LIMIT 5') for p in out['parts'])


def test_쓰기_SQL_은_연결을_열기_전에_거절한다(seeded_graph):
    """원천이 모두 꺼져 있어도 SqlRejected 다 — 연결을 먼저 열었다면 FabricUnavailable 이 났다."""
    down = Fabric(fabric.env_connectors({'ENTERPRISE_READ_DSN': _dead_dsn(), 'TSDB_READ_DSN': _dead_dsn()}), seeded_graph.query)
    with pytest.raises(SqlRejected):
        down.query('HYD-01', 'sql', 5, {ENT: 'delete from ent.parts'})


@pytest.mark.parametrize('sql', [None, {}, {'hyd-other': 'select 1'}, 'select 1'], ids=['없음', '빈 사전', '모르는 원천', '글'])
def test_직접_쓴_SQL_은_원천별_사전이어야_한다(fab, sql):
    with pytest.raises(ValueError, match='원천별 SELECT'):
        fab.query('HYD-01', 'sql', 5, sql)


def test_교차_조회의_기준값은_지식_그래프의_이상_패턴_임계값이다(fab, seeded_graph, tags):
    (limit,) = seeded_graph.query(fabric.LIMIT_Q, variable='ts1')
    out = fab.query('HYD-01', 'hot-lots-vs-ts1')
    ts1 = next(p for p in out['parts'] if p['id'] == 'ts1')
    assert ts1['params'] == {'asset': 'HYD-01', 'ts1_limit': limit['value']} and limit['pattern'] in out['notes'][0]
    assert ts1['rows'][0][1] == 51.25                                    # 최근 60분 최고 유온 = 넣은 값
    assert [a['label'] for a in out['answer']][:2] == ['QMS 기록 고온 시간', '출하 대기 로트']


def test_지식_그래프에_임계값이_없으면_교차_조회를_하지_않는다(readers, neo4j_graph):
    with pytest.raises(SourceUnavailable, match='ts1 임계값이 없습니다'):
        Fabric(fabric.env_connectors(readers), neo4j_graph.query).query('HYD-01', 'hot-lots-vs-ts1')


def test_정의되지_않은_교차_조회는_가능한_목록과_함께_거절한다(fab):
    with pytest.raises(ValueError) as caught:
        fab.query('HYD-01', 'no-such-query')
    assert all(q in str(caught.value) for q in fabric.CROSS_QUERIES)


# ---------------------------------------------------------------- 클래스 ↔ 표 · 열
def test_온톨로지_클래스의_식별_키를_살아_있는_원천에_대어_본다(fab, tags):
    out = fab.links()
    rows = {(c['klass'], c['source'], c['table']): c for c in out['classes']}
    asset = rows[('Asset', ENT, 'assets')]
    assert asset['state'] == 'OK' and {m['key'] for m in asset['matched']} == {'HYD-01', 'HYD-02', 'HYD-03'}
    sensor = rows[('Sensor', TS, 'tag_1s')]
    assert sensor['state'] == 'OK' and {m['key'] for m in sensor['matched']} == {'TS1', 'VS1'}       # 최근 10분에 들어온 태그만
    assert {'PS1', 'FS1', 'CE'} <= {m['key'] for m in sensor['unmatched']}


def test_그래프가_없으면_연결_판정은_그래프_사유를_달고_원천은_그대로_본다(readers):
    out = Fabric(fabric.env_connectors(readers), None).links()
    assert out['graph']['ok'] is False and out['graph']['reason'] == '지식 그래프 연결이 설정되지 않았습니다'
    assert out['sources'] == {ENT: {'ok': True}, fabric.LEGACY: {'ok': True}, TS: {'ok': True}} and all(c['instances'] == 0 for c in out['classes'])


def test_판단_입력_질의는_템플릿_한_곳을_읽어_템플릿의_열을_그대로_싣는다(seeded_graph):
    """G2-18: 사본 INPUTS_Q 가 템플릿(catalog · sourceLiveType · REPRESENTS 열)과 이미 어긋났다 — 이제 템플릿 파일이 정본이다."""
    rows = seeded_graph.query(fabric.inputs_query())
    assert rows and {'catalog', 'sourceLiveType', 'represents', 'representsName', 'source'} <= set(rows[0])


def test_판단_입력_템플릿이_없으면_그_자리를_말하며_실패한다(fab, tmp_path, monkeypatch):
    monkeypatch.setenv('KG_TEMPLATES', str(tmp_path))
    with pytest.raises(RuntimeError, match='t3_inputs.cypher'):
        fab.links()


# ---------------------------------------------------------------- 옛 설비 DB(실라버스 통합 40행 — 제공 legacy-plant-db.sql)
from pathlib import Path

from procsvc import legacy_meaning
from procsvc.ingest import parse_ddl

_ROOT = Path(__file__).resolve().parents[3]
LEGACY_SQL = (_ROOT / 'it' / 'portal' / 'www' / 'samples' / 'legacy-plant-db.sql').read_text(encoding='utf-8')
LEGACY_MIGRATION = _ROOT / 'it' / 'supabase' / 'migrations' / '20261031000071_legacy_plant_db.sql'


def _file_rows():
    """제공 파일의 INSERT 행 수 {표: 행 수} — 파일을 읽는 실제 해석기(legacy_meaning.sample_rows)로."""
    tables = parse_ddl(LEGACY_SQL, 'legacy')
    return {n: v['total'] for (_, n), v in legacy_meaning.sample_rows(LEGACY_SQL, tables)['tables'].items()}


def test_옛_설비_DB_마이그레이션은_제공_파일_본문을_그대로_담는다():
    """정본은 제공 파일 — 마이그레이션은 DB 컨테이너가 저장소 파일을 못 읽어 본문을 담는다. 둘이 갈라지면 여기서 멈춘다."""
    body = LEGACY_SQL[LEGACY_SQL.index('CREATE TABLE'):]
    assert body in LEGACY_MIGRATION.read_text(encoding='utf-8')


def test_옛_설비_DB는_등록_원천이고_샘플_행은_제공_파일의_행_그대로다(fab):
    rows = {s['id']: s for s in fab.sources()}
    legacy = rows[fabric.LEGACY]
    assert legacy['ok'] and legacy['read_only'] and legacy['user'] == 'hyd_enterprise_reader' and legacy['schema'] == 'legacy', legacy
    want = _file_rows()
    assert {t['name'] for t in legacy['tables']} == set(want) == {'T_EQP00', 'T_EQP01', 'T_MNT10'}
    parsed = legacy_meaning.sample_rows(LEGACY_SQL, parse_ddl(LEGACY_SQL, 'legacy'))['tables']
    for table, n in want.items():
        sample = fab.sample(fabric.LEGACY, table, fabric.SAMPLE_MAX)
        assert sample['row_count'] == n and '"legacy"' in sample['statement'], (table, sample)
        # 행 수만이 아니라 값까지 — 마이그레이션이 파일 본문 뒤에서 값을 바꿔도(UPDATE · ALTER) 잡는다(마지막고침 검증 H11)
        file_part = parsed[('legacy', table)]
        assert _row_set(sample['columns'], sample['rows']) == _row_set(file_part['columns'], file_part['rows']), table


def _row_set(columns, rows):
    """열 이름 순서와 값 꼴(문자 · 수 · 날짜)에 기대지 않고 견줄 수 있는 행 모음 — 수로 읽히는 값은 수로, 나머지는 글자로."""
    def norm(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            text = None if v is None else str(v)   # 날짜 시각: DB 는 「…T…」, 파일은 「… …」 — 날짜 뒤 T 하나만 띄어쓰기로
            return text if text is None or not re.match(r'\d{4}-\d\d-\d\dT', text) else text.replace('T', ' ', 1)
    return sorted((tuple(sorted((c, norm(v)) for c, v in zip(columns, r))) for r in rows), key=repr)   # 빈 값(None)과 글자가 섞여도 줄 세울 수 있게


@pytest.mark.parametrize('link, state', [
    (dict(datasource=ENT, schema='ent', table='assets', column='code'), 'OK'),
    (dict(datasource=fabric.LEGACY, schema='legacy', table='T_EQP01', column='C_TMP_O'), 'OK'),
    (dict(datasource=fabric.LEGACY, schema='legacy', table='T_EQP01', column='NO_SUCH'), 'MISSING'),
    (dict(datasource=fabric.LEGACY, schema='public', table='T_EQP01', column='C_TMP_O'), 'UNREGISTERED'),
    (dict(datasource='hyd-other', schema='legacy', table='T_EQP01', column='C_TMP_O'), 'UNREGISTERED'),
    (dict(datasource=TS, schema='public', table='tag_1s', column='value'), 'UNREGISTERED'),
], ids=['업무 DB 열', '옛 설비 DB 열', '옛 설비 DB 에 없는 열', '옛 원천 다른 스키마', '등록 안 된 원천', '시계열은 DDL 원천 아님'])
def test_DDL로_이은_판단_입력은_등록_원천의_살아_있는_열일_때만_OK(fab, link, state):
    live = {}
    for sid in (ENT, fabric.LEGACY):
        with fab._session(sid) as cur:
            live[sid] = {'ok': True, 'tables': {t['name']: {c['name']: c for c in t['columns']} for t in fab._tables(cur, sid)}}
    live[TS] = {'ok': True, 'tables': {}}
    row = Fabric._input_link(dict(link, id='in:x', name='x'), live)
    assert row['state'] == state, row
    if state == 'UNREGISTERED':
        assert '옛 설비 DB legacy' in row['reason'], row['reason']


def test_옛_설비_DB_가드는_legacy_표만_읽는다():
    assert fabric.guard_for(fabric.LEGACY, 'select * from "T_EQP01"', 5).endswith('LIMIT 5')
    for sql in ('select * from ent.assets', 'delete from "T_EQP01"'):
        with pytest.raises(SqlRejected):
            fabric.guard_for(fabric.LEGACY, sql, 5)
