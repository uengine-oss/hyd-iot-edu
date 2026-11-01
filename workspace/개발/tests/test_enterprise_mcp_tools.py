"""업무 MCP 도구 본체(it/enterprise-mcp/enterprise_mcp/tools.py) — 실제 업무 DB(묶음 DB)에 실제 읽기 전용 계정(hyd_enterprise_reader)으로 붙는다."""

import pytest

from enterprise_mcp.tools import EnterpriseTools, guarded
from conftest import ent_reader
from hydcommon.enterprise import reader_connection


@pytest.fixture
def tools(pg_dsn):
    dsn = ent_reader(pg_dsn)
    return EnterpriseTools(lambda: reader_connection(dsn))


@pytest.mark.parametrize('name, params, records', [
    ('mes_orders', {'asset': 'HYD-01'}, 1),
    ('pm_status', {'asset': None}, 3),            # 도구 설명대로 비우면 세 대(G2-04: 옛 판은 「등록되지 않은 설비」)
    ('pm_status', {'asset': 'HYD-02'}, 1),
    ('spare_stock', {'part': None}, 4),
    ('part_quotes', {'part': 'P-PMP-SEAL'}, 3),
    ('ems_demand', {}, 1),
], ids=['생산오더', '정기정비_전체', '정기정비_한_대', '예비품_전체', '견적', '전력'])
def test_고정_읽기는_업무_DB_함수의_사실을_봉투에_담아_돌려준다(tools, name, params, records):
    out = guarded(tools.read)(name, **params)
    assert out['result'] == 'ok' and out['document']['facts'] is not None and len(out['document']['records']) == records


@pytest.mark.parametrize('name, params', [
    ('mes_orders', {'asset': 'HYD-09'}), ('scm_suppliers', {'part': 'NOPE'}), ('part_quotes', {'part': 'NOPE'}),
    ('maintenance_windows', {'asset': None}),
], ids=['없는_설비', '없는_부품_공급사', '없는_부품_견적', '설비가_꼭_필요한_조회'])
def test_업무_DB에_대상이_없으면_0건_성공이_아니라_INVALID다(tools, name, params):
    """G2-04: 없는 부품의 견적이 「0건 성공」으로 와 에이전트가 견적이 없다고 결론을 냈다."""
    out = guarded(tools.read)(name, **params)
    assert out['result'] == 'error' and out['error_kind'] == 'INVALID' and '자료가 없습니다' in out['message']


@pytest.mark.parametrize('sql, kind', [
    ("select part_no, on_hand from spare_stock where part_no = 'P-PMP-SEAL'", 'ok'),
    ("delete from spare_stock", 'INVALID'),
    ("select ent.exec_skill('{}'::jsonb)", 'INVALID'),
    ("select no_such_column from spare_stock", 'UNKNOWN'),
], ids=['읽기', '쓰기', '쓰기_함수', '없는_열'])
def test_에이전트_SQL은_가드와_읽기_전용_연결을_지나고_결과는_봉투다(tools, sql, kind):
    out = guarded(tools.query)(sql=sql)
    if kind == 'ok':
        assert out['result'] == 'ok' and out['document']['rows'] == [['P-PMP-SEAL', 3]]
    else:
        assert out['result'] == 'error' and out['error_kind'] == kind and out['statement'] == sql


def test_표_목록은_읽기_계정이_볼_수_있는_업무_표만이다(tools):
    names = {r['name'] for r in tools.describe_catalog()['document']['relations']}
    assert {'spare_stock', 'work_orders', 'skill_contracts'} <= names and 'mcp_secrets' not in names
