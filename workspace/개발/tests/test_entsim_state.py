"""업무 거래 이름 표와 /api/state 모양(it/enterprise-sim/entsim/state.py)."""
import psycopg
import pytest

from entsim.state import SKILL_NAMES, snapshot_view


def test_이름_표의_거래는_업무_DB_계약의_거래와_같다(pg_dsn):
    """이름 표(포털 이름 사전의 재료)와 업무 DB 가 받는 거래(ent.skill_contracts)가 갈라지면 화면에 원문 id 가 보이거나 지운 거래 이름이 남는다."""
    with psycopg.connect(pg_dsn) as db:
        skills = {s for (s,) in db.execute('SELECT skill FROM ent.skill_contracts').fetchall()}
    assert set(SKILL_NAMES) == skills and all(SKILL_NAMES.values())


@pytest.mark.parametrize('table, row, alias, original', [
    ('work_orders', {'id': 'WO-1', 'window_label': '야간'}, 'window', 'window_label'),
    ('purchase_requests', {'id': 'PR-1', 'supplier_name': 'B-OEM (순정)'}, 'supplierName', 'supplier_name'),
], ids=['작업지시_창', '발주_공급사'])
def test_상태_모양은_업무_DB_칸을_포털이_읽는_이름으로도_싣는다(table, row, alias, original):
    systems = {'work_orders': 'cmms', 'purchase_requests': 'erp'}
    out = snapshot_view([], {table: [row]})
    got = out[systems[table]][table][0]
    assert got[alias] == got[original] == row[original]


def test_상태_모양은_행이_없는_표도_빈_목록으로_싣는다():
    out = snapshot_view([{'order_id': 'MO-1'}], {})
    assert out['mes'] == {'orders': [{'order_id': 'MO-1'}]}
    assert out == {'mes': {'orders': [{'order_id': 'MO-1'}]}, 'cmms': {'work_orders': []}, 'erp': {'purchase_requests': [], 'goods_receipts': []}}
