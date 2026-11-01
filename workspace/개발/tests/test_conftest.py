"""테스트 공통 준비(conftest.py) — 테스트 자리마다 다시 쓰는 컨테이너는 다음 묶음이 시작할 때 앞 묶음의 것이 하나도 남지 않는다.

컨테이너는 테스트 DB 이름마다 하나(`hyd-test-<서비스>-<DB 이름>`)를 묶음이 바뀌어도 다시 쓴다. 다음 묶음의 시작 = 같은 이름으로 서버 준비를
다시 만드는 것(GraphServer() · TimescaleServer())이고, 그때 그래프(데이터 · 제약 · 색인)와 시계열 표(1분 집계 포함)가 비어 있어야 한다.
"""
import subprocess
import sys
import threading

import psycopg

from conftest import ROOT, ComposeContainer, GraphServer, TimescaleServer, container_name, take_slot, until


def test_다음_묶음은_앞_묶음이_그래프에_남긴_노드와_제약_없이_시작한다(graph_server):
    graph_server._run("CREATE (:LeftOver {id: 'from-earlier-run'})")
    graph_server._run('CREATE CONSTRAINT leftover_id IF NOT EXISTS FOR (n:LeftOver) REQUIRE n.id IS UNIQUE')
    again = GraphServer()
    try:
        assert again.box.reused and again.box.name == container_name('neo4j') == graph_server.box.name
        assert again._run('MATCH (n) RETURN count(n) AS n') == [{'n': 0}]
        assert again._schema() == []
    finally:
        again.close()


def test_다음_묶음은_앞_묶음이_시계열에_남긴_값과_1분_집계_없이_시작한다(timescale):
    # 같은 실행의 앞 테스트도 이 시계열에 값을 넣는다 — 「앞 묶음」은 여기서 새로 시작한 묶음으로 만든다(2026-11-01 전체 실행 5: 앞 테스트의
    # 1분 집계 58줄이 남아 있어 「1줄이 생겼다」 준비 단언이 깨졌다 — 정리 판정이 아니라 시험 준비가 앞 테스트에 기댔다)
    first = TimescaleServer()
    with psycopg.connect(first.dsn, autocommit=True) as db:
        db.execute("INSERT INTO tag_1s(time, asset, name, value) VALUES (now() - interval '5 minutes', 'HYD-01', 'TS1', 61.0)")
        db.execute("INSERT INTO alerts(alert_id, asset, pattern, state) VALUES ('ALT-left-over', 'HYD-01', 'COOLER_DEGRADATION', 'RAISE')")
        db.execute("CALL refresh_continuous_aggregate('tag_1m', NULL, NULL)")
        assert db.execute('SELECT count(*) FROM tag_1m').fetchone()[0] == 1          # 앞 묶음의 1분 집계가 실제로 생겼다
    again = TimescaleServer()
    assert again.box.reused and again.box.name == container_name('timescaledb')
    with psycopg.connect(again.dsn) as db:
        left = {t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('tag_1s', 'feat_1s', 'tag_1m', 'alerts', 'actions', 'audit')}
    assert left == dict.fromkeys(left, 0)


def test_띄우는_내용이_바뀐_컨테이너는_다시_쓰지_않고_새로_띄운다(timescale):
    """이 묶음의 컨테이너를 건드리지 않게 따로 이름 붙인 컨테이너로 잰다(끝나면 지운다)."""
    import subprocess
    name = container_name('timescaledb') + '-probe'
    try:
        first = ComposeContainer('timescaledb', 5432, name=name)
        assert ComposeContainer('timescaledb', 5432, name=name).reused, '같은 내용이면 다시 쓴다'
        changed = ComposeContainer('timescaledb', 5432, name=name, env={'HYD_TEST_PROBE': 'changed'})
        assert not changed.reused and changed.port == first.port
    finally:
        subprocess.run(['docker', 'rm', '-f', '-v', name], capture_output=True)


HOLDER = """import sys, time
sys.path.insert(0, sys.argv[2])
from conftest import take_slot
held = take_slot(sys.argv[1], slots=3)              # 잡은 파일을 쥐고 있는 동안 칸이 잠긴다
print('held', flush=True)
sys.stdin.read()
"""


def _holder(directory):
    proc = subprocess.Popen([sys.executable, '-c', HOLDER, str(directory), str(ROOT / 'workspace' / '개발' / 'tests')],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == 'held'
    return proc


def test_칸이_다_찬_넷째_묶음은_기다리고_칸을_잡은_묶음이_죽으면_그_칸을_받는다(tmp_path):
    holders = [_holder(tmp_path) for _ in range(3)]
    got, said = {}, []
    try:
        waiter = threading.Thread(target=lambda: got.update(handle=take_slot(tmp_path, slots=3, say=said.append)), daemon=True)
        waiter.start()
        until(lambda: said, '넷째 묶음이 기다린다고 알리지 않았다', 30)
        assert 'handle' not in got and '칸 3개' in said[0]
        holders[1].kill()                                  # 칸을 잡은 묶음이 죽는다(창 닫기 · 강제 종료)
        holders[1].wait(10)
        waiter.join(60)
        assert 'handle' in got, '죽은 묶음의 칸이 풀리지 않았다'
        got['handle'].close()
    finally:
        for proc in holders:
            proc.kill()
            proc.wait(10)


def test_멈춘_서비스는_그동안_답하지_않고_풀면_다시_답한다(stack):
    """paused() 는 런처와 그 자식(실제 서버)을 함께 멈춘다 — 런처만 멈추면 서버가 계속 답한다(Windows venv)."""
    import urllib.request
    agent = stack.services['agent']
    with agent.paused():
        try:
            urllib.request.urlopen(agent.health, timeout=3)
            answered = True
        except OSError:
            answered = False
    assert not answered, '멈춘 동안 서비스가 답했다'
    assert urllib.request.urlopen(agent.health, timeout=30).status == 200


def test_칸_여럿을_바라는_묶음은_한_칸을_쥔_묶음이_끝나면_칸을_모두_잡는다(tmp_path):
    """서비스 스택 묶음(브로커까지 2.52 GB)은 칸 전부를 잡는다 — 다른 묶음이 한 칸이라도 쥐고 있으면 기다린다."""
    holder = _holder_slots(tmp_path, 2)
    got, said = {}, []
    try:
        waiter = threading.Thread(target=lambda: got.update(held=take_slot(tmp_path, slots=2, say=said.append, count=2)), daemon=True)
        waiter.start()
        until(lambda: said, '칸 둘을 바라는 묶음이 기다린다고 알리지 않았다', 30)
        assert 'held' not in got
        holder.kill()
        holder.wait(10)
        waiter.join(60)
        assert 'held' in got and len(got['held'].handles) == 2, '한 칸을 쥔 묶음이 끝났는데 칸 둘을 잡지 못했다'
        assert all(not take_slot_free(tmp_path, i) for i in range(2)), '잡았다는 칸이 실제로 잠겨 있지 않다'
        got['held'].close()
        assert all(take_slot_free(tmp_path, i) for i in range(2))
    finally:
        holder.kill()
        holder.wait(10)


def _holder_slots(directory, slots):
    proc = subprocess.Popen([sys.executable, '-c', HOLDER.replace('slots=3', f'slots={slots}'), str(directory),
                             str(ROOT / 'workspace' / '개발' / 'tests')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == 'held'
    return proc


def take_slot_free(directory, i):
    """칸 i 가 지금 비었나(잠가 보고 바로 푼다)."""
    from conftest import _try_lock
    with open(directory / f'slot-{i}.lock', 'a+b') as handle:
        return _try_lock(handle, block=False)


def _labeled_container(site):
    """테스트 자리 꼬리표만 단 멈춘 컨테이너 하나(만들기만 — 띄우지 않는다) → 이름."""
    from conftest import CONTAINER_LABEL, CONTAINER_SITE, _compose_service
    name = f'hyd-test-probe-{site}'
    subprocess.run(['docker', 'create', '--name', name, '--label', f'{CONTAINER_LABEL}=probe', '--label', f'{CONTAINER_SITE}={site}',
                    _compose_service('timescaledb')['image']], check=True, capture_output=True)
    return name


def _exists(name):
    return subprocess.run(['docker', 'ps', '-aq', '--filter', f'name=^{name}$'], capture_output=True, text=True, check=True).stdout.strip() != ''


def test_칸을_잡으면_도는_묶음이_없는_자리의_남은_컨테이너는_지우고_도는_자리의_것은_둔다(timescale):
    """끊긴 묶음(자리 잠금을 아무도 쥐지 않음)의 컨테이너는 칸 셈 밖에서 메모리를 쓴다 — 다음 묶음이 칸을 잡을 때 지운다."""
    from conftest import _site_lock_path, _test_site, _try_lock, sweep_dead_sites
    mine = _test_site()
    dead, alive = _labeled_container(mine + '_deadprobe'), _labeled_container(mine + '_liveprobe')
    lock = open(_site_lock_path(mine + '_liveprobe'), 'a+b')
    try:
        assert _try_lock(lock, block=False)                       # 도는 묶음 하나가 그 자리를 쥐고 있다
        swept = sweep_dead_sites(mine, say=lambda line: None)
        assert mine + '_deadprobe' in swept and not _exists(dead), '도는 묶음이 없는 자리의 컨테이너가 남았다'
        assert mine + '_liveprobe' not in swept and _exists(alive), '도는 묶음의 컨테이너를 지웠다'
        assert mine not in swept and _exists(container_name('timescaledb')), '자기 자리의 컨테이너를 지웠다'
    finally:
        lock.close()
        subprocess.run(['docker', 'rm', '-f', dead, alive], capture_output=True)


def test_엔진_시계가_앞선_뒤_명령_응답이_와도_그_뒤_설비_보고가_최신_상태가_된다(world):
    """설비의 명령 응답과 상태 보고는 같은 설비 시계다 — 응답 시각이 엔진 시계를 따라 앞서 가면 그 뒤 보고가 최신 상태를 못 고친다."""
    from hydcommon import topics
    world.clock.advance(10 * 60)
    world.ack('HYD-01', 'FUXA-probe-1')
    status = world.plant.status('HYD-01')
    world.receive(topics.K_STATUS, status)
    latest = world.main.source_inbox.latest_states()['HYD-01']
    assert latest.get('cmdId') != 'FUXA-probe-1' and latest['t'] == status['t'], latest


def test_설비_데이터_수집기는_실제_MQTT_Kafka_브로커에_붙어_정상으로_답한다(stack):
    """학생 PC 처럼 connect-ingest 가 떠 있다(agent · dmn-mcp 의 데이터 신뢰 확인 mcp_prom.freshness 가 읽는 자리 — 판정은 test_trial)."""
    import json
    import urllib.request
    with urllib.request.urlopen(stack.services['connect-ingest'].health, timeout=10) as r:
        body = json.loads(r.read())
    assert r.status == 200 and body['ok'] and body['mqtt'] and body['kafka'], body


def test_칸_여럿을_기다리는_묶음_뒤에_온_한_칸_묶음은_빈_칸이_있어도_차례를_기다린다(tmp_path):
    """문(gate) 차례: 칸 둘을 바라는 묶음이 먼저 기다리면, 뒤에 온 한 칸 묶음이 빈 칸을 가로채 그 묶음을 끝없이 밀어내지 않는다."""
    holder = _holder_slots(tmp_path, 2)                     # 한 칸을 쥔 묶음(0번 칸)
    big, small, said_big, said_small = {}, {}, [], []
    try:
        threading.Thread(target=lambda: big.update(held=take_slot(tmp_path, slots=2, say=said_big.append, count=2)), daemon=True).start()
        until(lambda: said_big, '칸 둘을 바라는 묶음이 기다린다고 알리지 않았다', 30)
        assert take_slot_free(tmp_path, 1)                  # 1번 칸은 비어 있다
        threading.Thread(target=lambda: small.update(held=take_slot(tmp_path, slots=2, say=said_small.append)), daemon=True).start()
        until(lambda: said_small, '뒤에 온 한 칸 묶음이 기다린다고 알리지 않았다', 30)
        assert 'held' not in small, '뒤에 온 한 칸 묶음이 차례를 건너뛰어 빈 칸을 잡았다'
        holder.kill()
        holder.wait(10)
        until(lambda: 'held' in big, '한 칸을 쥔 묶음이 끝났는데 칸 둘을 바라는 묶음이 이어 가지 못했다', 60)
        assert 'held' not in small
        big['held'].close()
        until(lambda: 'held' in small, '칸이 비었는데 기다리던 한 칸 묶음이 이어 가지 못했다', 60)
        small['held'].close()
    finally:
        holder.kill()
        holder.wait(10)


def test_world_를_닫으면_기동이_바꾼_대기_압축이_기동_전_값으로_돌아온다(stack, course_graph, tmp_path):
    """process 기동(instance_mode.build)이 프로세스 전역 대기 압축을 compose 값(60)으로 정한다 — 닫은 뒤에도 남으면 그 뒤 순수 함수
    테스트(test_effect_parts 등)가 앞 world 의 압축을 물려받아 순서에 따라 결과가 달랐다."""
    from conftest import EngineWorld
    from procsvc import engine
    engine.configure_wait_compression(1.0)
    w = EngineWorld(stack, tmp_path)
    try:
        assert engine.wait_compression() == float(__import__('os').environ['PROCESS_WAIT_COMPRESSION'])   # 기동 중에는 compose 값
    finally:
        w.close()
    assert engine.wait_compression() == 1.0
