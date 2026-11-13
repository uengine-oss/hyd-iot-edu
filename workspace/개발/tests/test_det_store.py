"""감지기 상태 파일(it/detector/det/store.py) — 체크포인트 · 오프셋(+ 가장 새 기록 시각) · 경보 outbox(G3b-12 · 13)."""
import json
import sqlite3

from det.store import Store


def test_체크포인트_오프셋_경보를_한_번에_적고_읽는다(tmp_path):
    store = Store(tmp_path / 'd.sqlite3')
    store.save({'runtime': None}, {('plant.tag', 0): (41, 9000)}, [{'alertId': 'A1'}])
    assert store.load() == {'runtime': None} and store.position('plant.tag', 0) == (42, 9000)
    assert [e for _, e in store.pending()] == [{'alertId': 'A1'}]
    store.delivered(store.pending()[0][0])
    assert store.pending() == [] and store.position('plant.status', 0) == (None, None)


def test_가장_새_기록_시각은_줄지_않고_잊으면_처음부터다(tmp_path):
    store = Store(tmp_path / 'd.sqlite3')
    store.save({}, {('plant.tag', 0): (10, 9000)})
    store.save({}, {('plant.tag', 0): (11, 8000)})
    assert store.position('plant.tag', 0) == (12, 9000)
    store.forget('plant.tag', 0)
    assert store.position('plant.tag', 0) == (None, None)


def test_옛_파일은_시각_칸을_얻고_올린_때의_시각으로_채운다(tmp_path):
    path = tmp_path / 'old.sqlite3'
    db = sqlite3.connect(path)
    db.executescript('CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);'
                     'CREATE TABLE offsets(topic TEXT, partition INTEGER, position INTEGER NOT NULL, PRIMARY KEY(topic,partition));'
                     'CREATE TABLE outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL);'
                     "INSERT INTO offsets VALUES('plant.tag',0,500); INSERT INTO checkpoint VALUES(1, '{\"scope\": \"production\"}');")
    db.commit()
    db.close()
    store = Store(path)
    position, max_ts = store.position('plant.tag', 0)
    assert position == 501 and max_ts > 1_700_000_000_000 and store.load() == {'scope': 'production'}


def test_NaN은_저장하지_않는다(tmp_path):
    store = Store(tmp_path / 'd.sqlite3')
    try:
        store.save({'x': float('nan')})
        raise AssertionError('NaN 이 저장됐다')
    except ValueError:
        pass
    assert store.load() is None and json.dumps({}) == '{}'
