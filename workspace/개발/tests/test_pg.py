"""PostgreSQL 연결을 맺는 한 곳(common/hydcommon/pg.py connect) — 서버가 받지 않은 연결(틀린 암호 · 없는 DB)은 다시 맺지 않고 참 까닭을 말하고,
닿지 않는 연결은 전과 같이 다시 맺어 본 뒤 「지금 연결되지 않습니다」로 실패하며, 답하지 않는 서버에서도 연결 예산(CONNECT_BUDGET_S) 안에 그친다.
서버는 이 PC 의 실제 업무 DB(HYD_TEST_DSN 의 서버)와, 받기만 하고 답하지 않는 실제 TCP 자리다. 잠깐 끊긴 뒤 다시 맺어지는 길(처음 몇 번 끊는 선)은
test_main 의 업무 DB 선(_DbLine — 2번 끊김 → 200 · 계속 끊김 → 503) 시험이 잰다. 연결을 맺은 뒤의 문장 오류는 다시 하지 않는다 — 다시 맺기는
pg.connect 안의 psycopg.connect 한 줄만 감싼다(그 밖은 그대로 올라간다)."""
import logging
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from conftest import DSN_ENV
from hydcommon import pg


def server(**change):
    """HYD_TEST_DSN 의 서버에 계정 · 암호 · DB 만 바꾼 주소."""
    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        pytest.fail(f'{DSN_ENV}가 없어 실제 업무 DB 서버로 연결 거절을 재지 못했다 — 로컬 Supabase 가 켜진 PC 에서 주고 다시 돌린다', pytrace=False)
    parts = urlsplit(dsn)
    user, password = change.get('user', parts.username), change.get('password', parts.password)
    return urlunsplit(parts._replace(netloc=f'{user}:{password}@{parts.hostname}:{parts.port}', path='/' + change.get('db', 'postgres')))


def retries(caplog):
    return [r for r in caplog.records if r.name == 'hyd.pg' and 'retrying' in r.getMessage()]


@pytest.mark.parametrize('change, reason', [
    ({'password': 'not-the-password'}, '계정 또는 암호가 맞지 않습니다'),
    ({'user': 'no_such_role_' + uuid.uuid4().hex[:6], 'password': 'x'}, '계정 또는 암호가 맞지 않습니다'),   # 없는 계정 — 서버가 암호 틀림으로 숨긴다
    ({'db': 'no_such_db_' + uuid.uuid4().hex[:6]}, '연결하려는 데이터베이스가 없습니다'),
], ids=['틀린_암호', '없는_계정', '없는_DB'])
def test_서버가_받지_않은_연결은_다시_맺지_않고_참_까닭을_말한다(caplog, change, reason):
    """전에는 틀린 암호 · 없는 DB 도 2.5초 동안 네 번 다시 맺은 뒤 「지금 연결되지 않습니다. 잠시 뒤 다시 해 보세요」만 보였다."""
    caplog.set_level(logging.WARNING, logger='hyd.pg')
    with pytest.raises(pg.DbRefused) as caught:
        pg.connect(server(**change), name='업무 DB')
    assert retries(caplog) == []
    detail = caught.value.detail
    assert detail == pg.refused_text('업무 DB', reason) and '잠시 뒤' not in detail and '다시 해도 같습니다' in detail
    assert isinstance(caught.value, pg.DbUnreachable)          # 503 으로 답하는 자리(answer_unreachable)가 그대로 받는다
    assert 'FATAL' in str(caught.value.__cause__)              # 까닭의 원문은 서버의 답


def test_닿지_않는_연결은_전과_같이_다시_맺어_본_뒤_지금_연결되지_않는다고_실패한다(caplog):
    """망 안의 이름(db.supabase.internal)은 이 PC 에서 풀리지 않는다 — 서버의 답이 없는 실패는 거절로 보지 않는다."""
    caplog.set_level(logging.WARNING, logger='hyd.pg')
    with pytest.raises(pg.DbUnreachable) as caught:
        pg.connect('postgresql://postgres:postgres@db.supabase.internal:5432/postgres', name='업무 DB')
    assert type(caught.value) is pg.DbUnreachable and caught.value.detail == pg.unreachable_text('업무 DB')
    assert len(retries(caplog)) == len(pg.CONNECT_PAUSES_S)


def test_서버가_받지_않은_연결을_만난_요청은_503과_참_까닭으로_답한다():
    """포털 · 에이전트가 받는 답(answer_unreachable) — 학생은 「잠시 뒤 다시」가 아니라 무엇이 틀렸는지를 읽는다."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    pg.answer_unreachable(app)

    @app.get('/read')
    def read():
        with pg.connect(server(password='not-the-password'), name='시계열 DB'):
            return {}
    answer = TestClient(app).get('/read')
    assert answer.status_code == 503 and answer.json() == {'detail': pg.refused_text('시계열 DB', '계정 또는 암호가 맞지 않습니다')}


def test_받기만_하고_답하지_않는_서버에는_연결_예산_안에_그치고_포털의_읽기_제한_8초를_넘기지_않는다():
    """연결 한 번의 기다림은 CONNECT_TIMEOUT_S(3초), 다시 맺기를 다 합쳐 CONNECT_BUDGET_S(7초) — 포털 화면의 읽기 제한 8초 안에 「지금 연결되지
    않습니다」로 답해야 화면이 그 문장을 보인다. 실제 TCP 자리가 연결을 받기만 하고 서버 인사를 보내지 않는다(망 너머 DB 가 멈춘 꼴)."""
    import socket
    import threading
    import time
    held, server = [], socket.create_server(('127.0.0.1', 0))
    server.settimeout(0.2)
    port, stop = server.getsockname()[1], threading.Event()

    def accept():
        while not stop.is_set():
            try:
                held.append(server.accept()[0])
            except OSError:
                continue
    threading.Thread(target=accept, daemon=True).start()
    started = time.monotonic()
    try:
        with pytest.raises(pg.DbUnreachable) as caught:
            pg.connect(f'postgresql://postgres:postgres@127.0.0.1:{port}/postgres', name='업무 DB')
        took = time.monotonic() - started
    finally:
        stop.set()
        for sock in held + [server]:
            sock.close()
    assert type(caught.value) is pg.DbUnreachable and caught.value.detail == pg.unreachable_text('업무 DB')
    assert len(held) >= 2, f'다시 맺지 않았다(받은 연결 {len(held)})'
    assert took < 8, f'{took:.1f} 초 — 포털의 읽기 제한(8초)을 넘겼다'
