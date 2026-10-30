"""사건 · 판단의 그래프 반영 대기열(procsvc/case_projection_store.py) — 그래프가 받은 행은 남지 않고, 실패한 행만 남아 다시 보내지는가."""
import sqlite3

import pytest

from procsvc import machine
from procsvc.store import Store


def _incident(note):
    inc = machine.Incident.from_card('INC-test', {'alert': {'alertId': 'ALT-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'},
                                                  'recommended': []})
    inc.history.append({'note': note})
    return {'INC-test': inc}


def rows(store):
    return store.db.execute('select attempts, last_error, processed_at from case_projection_outbox').fetchall()


@pytest.mark.parametrize('error, left', [
    (None, []),                                                   # 그래프가 받음 — 행이 남지 않는다
    ('ServiceUnavailable: neo4j down', [(1, 'ServiceUnavailable: neo4j down', None)]),   # 못 받음 — 남아 다시 보낸다
])
def test_그래프가_받은_행은_지우고_받지_못한_행은_까닭과_함께_남긴다(tmp_path, error, left):
    store = Store(str(tmp_path / 'process.sqlite3'))
    store.save(_incident('opened'), {}, [])
    [job] = store.case_projection_batch()
    store.finish_case_projection(job, error)
    assert rows(store) == left
    assert store.case_projection_status()['pending'] == len(left)


def test_받은_행을_지운_뒤에도_다음_판번호는_앞_판번호보다_크다(tmp_path):
    store = Store(str(tmp_path / 'process.sqlite3'))
    store.save(_incident('opened'), {}, [])
    [first] = store.case_projection_batch()
    store.finish_case_projection(first)
    store.save(_incident('approved'), {}, [])
    [second] = store.case_projection_batch()
    assert second['revision'] > first['revision']


def test_옛_판이_남긴_처리한_행은_다시_켤_때_지우고_처리_전_행은_남긴다(tmp_path):
    path = tmp_path / 'process.sqlite3'
    Store(str(path))
    old = sqlite3.connect(path)                                     # 옛 판이 남긴 모습: 처리 표시만 한 행 + 아직 처리 전인 행
    old.executemany('insert into case_projection_outbox(kind, source_id, body, created_at, processed_at) values (?, ?, ?, ?, ?)',
                    [('Incident', 'INC-old', '{}', 1.0, 2.0), ('Incident', 'INC-new', '{}', 3.0, None)])
    old.commit()
    old.close()
    store = Store(str(path))
    assert store.db.execute('select source_id from case_projection_outbox').fetchall() == [('INC-new',)]
