"""시작 5 · 8단계와 점검(scripts/check_stack.py)의 판정 — 무엇을 「떴다 · 통과 · 해당 없음 · 실패」로 보는가.

규칙(정답의 출처):
  · 서비스 목록은 손으로 적지 않고 compose 가 아는 서비스 전부다(옛 시작 · 점검은 effects-mcp 8197 등을 빠뜨렸다 — 견적 #20, E6).
    계속 도는 서비스 = running + healthy(건강 확인 없는 선택 도구는 running), 한 번 도는 준비 작업(재시작 정책 no) = 종료 코드 0.
    다 뜬 것처럼 보여도 확인하는 동안 다시 시작한 서비스가 있으면 「재시작 반복」으로 실패(옛 시작은 찍기만 하고 「완료」).
  · AI 단계: 워커가 .env 의 AI_MODE 로 켜져야 한다. 키 없음(replay)은 저장된 응답이 있으면 「해당 없음」(강의 중계를 부르지 않는다 —
    옛 점검은 「건너뜀」을 「통과」로 표시), 없으면 실패. 키 있음은 process 안의 중계 확인 결과 그대로.
  · 쿨러 한 바퀴의 승인은 추천 카드의 승인 역할을 가진 사람으로 한다(포털에서 「나」를 그 사람으로 고르고 [승인]).
Docker · 처리 엔진 응답은 바깥이라, docker compose ps 와 process API 의 실제 모양(이 PC 스택에서 읽음)으로 만든 값을 넣는다. 시계 · 잠은 주입.
"""
import pytest

import check_stack as cs

PASS, FAIL, NA = cs.PASS, cs.FAIL, cs.NA


def row(service, state='running', health='healthy', exit_code=0, one_shot=False, restarts=0):
    return {'service': service, 'state': state, 'health': health, 'exit_code': exit_code, 'one_shot': one_shot, 'restarts': restarts}


# ---------------------------------------------------------------- 서비스
@pytest.mark.parametrize('rows, failed, waiting', [
    ([row('process')], [], []),
    ([row('redpanda-console', health='')], [], []),                                   # 건강 확인 없는 선택 도구
    ([row('kg-seed', 'exited', '', 0, one_shot=True)], [], []),                       # 준비 작업은 0 으로 끝나면 된다
    ([row('kg-seed', 'exited', '', 1, one_shot=True)], ['kg-seed'], []),              # 준비 작업 실패 — 바로 실패
    ([row('topic-init', 'running', '', one_shot=True)], [], ['topic-init']),          # 준비 작업 중
    ([row('process', health='starting')], [], ['process']),
    ([row('process', health='unhealthy')], [], ['process']),
    ([row('process', 'restarting', '')], [], ['process']),
    ([row('effects-mcp', 'exited', '', 1)], ['effects-mcp'], []),                     # 계속 돌아야 할 서비스가 멈춤
    ([row('effects-mcp', 'exited', '', 0)], ['effects-mcp'], []),                     # 0 으로 끝나도 멈춘 것
    ([], [], ['process']),                                                            # 아직 만들어지지 않음
], ids=['healthy', 'no_healthcheck', 'oneshot_ok', 'oneshot_fail', 'oneshot_running', 'starting', 'unhealthy',
        'restarting', 'stopped_nonzero', 'stopped_zero', 'missing'])
def test_서비스마다_떴는지_기다릴지_실패인지_가른다(rows, failed, waiting):
    expected = {r['service'] for r in rows} or {'process'}
    got_failed, got_waiting = cs.classify(expected, rows)
    assert [x.split(':')[0] for x in got_failed] == failed and [x.split(':')[0] for x in got_waiting] == waiting


def test_compose가_아는_서비스는_모두_판정한다():
    """effects-mcp 처럼 옛 포트 목록에 없던 서비스도 빠지지 않는다."""
    expected = {'process', 'effects-mcp', 'fuxa', 'grafana', 'fuxa-init'}
    rows = [row('process'), row('fuxa'), row('grafana'), row('fuxa-init', 'exited', '', 0, one_shot=True)]
    failed, waiting = cs.classify(expected, rows)
    assert failed == [] and [w.split(':')[0] for w in waiting] == ['effects-mcp']


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run_wait(samples, wait=60):
    """samples: 차례로 낼 (expected, rows). 마지막 것은 계속 낸다."""
    clock, queue = Clock(), list(samples)
    def rows_fn():
        return queue.pop(0) if len(queue) > 1 else queue[0]
    return cs.wait_services(wait, rows_fn=rows_fn, sleep=clock.sleep, clock=clock), clock.now


def test_켜지는_중이던_서비스가_건강해지면_끝난다():
    expected = {'process'}
    problems, _ = run_wait([(expected, [row('process', health='starting')]), (expected, [row('process')])])
    assert problems == []


def test_다_뜬_뒤_확인하는_동안_다시_시작하면_재시작_반복으로_실패한다():
    expected = {'grafana'}
    looping = [(expected, [row('grafana', restarts=n)]) for n in range(1, 40)]   # 볼 때마다 재시작 수가 는다
    problems, _ = run_wait(looping)
    assert problems and '재시작 반복' in problems[0]


def test_준비_작업이_실패하면_기한까지_기다리지_않고_멈춘다():
    expected = {'kg-seed'}
    problems, waited = run_wait([(expected, [row('kg-seed', 'exited', '', 1, one_shot=True)])], wait=180)
    assert problems and waited < 180


def test_기한이_지나도_뜨지_않은_서비스를_까닭과_함께_낸다():
    expected = {'process'}
    problems, waited = run_wait([(expected, [row('process', health='starting')])], wait=30)
    assert problems == ['process: 켜지는 중'] and waited >= 30


# ---------------------------------------------------------------- AI 단계
@pytest.fixture
def checkout(tmp_path):
    def make(ai_mode, saved=0):
        (tmp_path / '.env').write_text(f'LLM_API_KEY=\nAI_MODE={ai_mode}\n', encoding='utf-8')
        replay = tmp_path / 'it' / 'agent-worker' / 'replay'
        replay.mkdir(parents=True, exist_ok=True)
        for n in range(saved):
            (replay / f'{n:016x}.json.gz').write_bytes(b'')
        return tmp_path
    return make


def never_relay(call):
    raise AssertionError('키 없는 PC에서 강의 중계를 불렀다')


@pytest.mark.parametrize('ai_mode, worker, saved, relay_out, outcome', [
    ('replay', 'replay', 6, None, NA),                     # 키 없음 + 저장 응답 있음 = 해당 없음(통과로 꾸미지 않음)
    ('replay', 'replay', 0, None, FAIL),                   # 저장 응답이 없는 판
    ('replay', 'live', 6, None, FAIL),                     # 워커가 다른 방식으로 켜짐
    ('live', 'live', 0, {'ok': True, 'message': '강의 중계 연결됨'}, PASS),
    ('live', 'live', 0, {'ok': False, 'message': '강의 중계가 이 키를 받지 않습니다'}, FAIL),
], ids=['replay_saved', 'replay_empty', 'mode_mismatch', 'live_ok', 'live_refused'])
def test_AI_단계는_방식에_따라_통과_해당없음_실패로_가른다(checkout, ai_mode, worker, saved, relay_out, outcome):
    root = checkout(ai_mode, saved)
    relay = (lambda call: relay_out) if relay_out else never_relay
    got, note = cs.check_ai(root, relay_fn=relay, health_fn=lambda: {'ai_mode': worker})
    assert got == outcome and note


def test_process_안에서_중계_확인을_돌리지_못하면_실패로_까닭을_보인다(checkout):
    def broken(call):
        raise cs.CheckError('process 안에서 강의 중계 확인을 돌리지 못했습니다: no container')
    got, note = cs.check_ai(checkout('live'), relay_fn=broken, health_fn=lambda: {'ai_mode': 'live'})
    assert got == FAIL and 'process' in note


@pytest.mark.parametrize('results, code', [
    ([('서비스', PASS, ''), ('강의 중계', NA, '키 없는 수업')], 0),
    ([('서비스', PASS, ''), ('승인 뒤 실행', FAIL, '미달')], 1),
])
def test_해당_없음은_실패로_세지_않고_실패가_있으면_1로_끝난다(capsys, results, code):
    assert cs.show(results) == code
    out = capsys.readouterr().out
    assert ('실패 1건' in out) is bool(code)


# ---------------------------------------------------------------- 쿨러 사건 한 바퀴(처리 엔진 응답의 실제 모양으로)
def view(*rows, status='RUNNING', events=(), variables=None):
    return {'instance': {'status': status, 'variables_data': [{'key': k, 'value': v} for k, v in (variables or {}).items()]},
            'workitems': [dict(activity_id=a, status=s, id=f'w-{a}', **extra) for a, s, extra in rows], 'events': list(events)}


@pytest.mark.parametrize('v, expected', [
    (view(('T_agent', 'DONE', {}), ('T_approve', 'IN_PROGRESS', {})), 'approval'),
    (view(('T_agent', 'IN_PROGRESS', {})), None),
    (view(('T_agent', 'PENDING', {}), events=[{'event_type': 'task_deferred'}]), cs.CheckError),
    (view(('T_agent', 'FAILED', {'log': '수업 권한 확인 필요'})), cs.CheckError),
], ids=['approval', 'thinking', 'deferred', 'failed'])
def test_AI_판단_단계가_어디까지_왔는지_가른다(v, expected):
    if expected is cs.CheckError:
        with pytest.raises(cs.CheckError):
            cs.agent_outcome(v, 'replay')
    else:
        out = cs.agent_outcome(v, 'replay')
        assert (out[0] if out else None) == expected


def test_추천_카드는_그_승인_역할을_가진_사람으로_승인한다():
    decision = {'recommended': 'fan-up', 'options': [{'id': 'derate', 'approver': {'id': 'role:prod-mgr'}},
                                                     {'id': 'fan-up', 'approver': {'id': 'role:operator'}}]}
    people = [{'id': 'user:lee-prod', 'roles': ['role:prod-mgr']}, {'id': 'user:kim-op', 'roles': ['role:operator']}]
    assert cs.pick_approval(decision, people) == ('fan-up', 'role:operator', 'user:kim-op')


@pytest.mark.parametrize('decision, people', [
    ({'recommended': None, 'options': []}, []),
    ({'recommended': 'fan-up', 'options': [{'id': 'fan-up', 'approver': {'id': 'role:operator'}}]}, [{'id': 'u', 'roles': ['role:x']}]),
])
def test_추천_카드나_승인할_사람이_없으면_까닭을_보이고_멈춘다(decision, people):
    with pytest.raises(cs.CheckError):
        cs.pick_approval(decision, people)


@pytest.mark.parametrize('rows, ok, words', [
    ([('T_cmd', 'DONE'), ('T_reobs', 'DONE'), ('T_wo', 'DONE'), ('R_ok', 'DONE')], True, '작업지시'),
    ([('T_cmd', 'DONE'), ('T_reobs', 'DONE'), ('R_fail', 'DONE')], False, '미달'),
    ([('T_approve', 'IN_PROGRESS')], False, '닿지 않았습니다'),
])
def test_승인_뒤_명령_재관측_작업지시가_정상_보고까지_가야_통과다(rows, ok, words):
    got, detail = cs.flow_result(view(*[(a, s, {}) for a, s in rows], status='COMPLETED'))
    assert got is ok and words in detail
