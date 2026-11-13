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
    def make(ai_mode):
        (tmp_path / '.env').write_text(f'LLM_API_KEY=\nAI_MODE={ai_mode}\n', encoding='utf-8')
        return tmp_path
    return make


def never_relay(call):
    raise AssertionError('키 없는 PC에서 강의 중계를 불렀다')


# 워커 /health 의 실제 모양(it/agent-worker/worker/main.py): replay_recordings = 켜질 때 실제로 읽은 녹화 수(재생이 아니면 null).
# 저장소 폴더의 파일 수가 아니라 워커가 읽은 수를 본다 — 빈 · 깨진 녹화 파일을 「있음」으로 세지 않는다(깨졌으면 워커가 켜지지 않는다)
@pytest.mark.parametrize('ai_mode, health, relay_out, outcome', [
    ('replay', {'ai_mode': 'replay', 'replay_recordings': 6}, None, NA),            # 키 없음 + 녹화 있음 = 해당 없음(통과로 꾸미지 않음)
    ('replay', {'ai_mode': 'replay', 'replay_recordings': 0}, None, FAIL),          # 녹화가 없는 판
    ('replay', {'ai_mode': 'replay'}, None, FAIL),                                  # 녹화 수를 알리지 않는 옛 워커
    ('replay', {'ai_mode': 'live', 'replay_recordings': None}, None, FAIL),         # 워커가 다른 방식으로 켜짐
    ('live', {'ai_mode': 'live', 'replay_recordings': None}, {'ok': True, 'message': '강의 중계 연결됨'}, PASS),
    ('live', {'ai_mode': 'live', 'replay_recordings': None}, {'ok': False, 'message': '강의 중계가 이 키를 받지 않습니다'}, FAIL),
], ids=['replay_saved', 'replay_empty', 'replay_old_worker', 'mode_mismatch', 'live_ok', 'live_refused'])
def test_AI_단계는_방식에_따라_통과_해당없음_실패로_가른다(checkout, ai_mode, health, relay_out, outcome):
    root = checkout(ai_mode)
    relay = (lambda call: relay_out) if relay_out else never_relay
    got, note = cs.check_ai(root, relay_fn=relay, health_fn=lambda: health)
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
    ([('T_wo_only', 'DONE'), ('T_fix', 'DONE'), ('T_reobs_wo', 'DONE'), ('R_wo_only', 'DONE')], True, '정비 수행 → 재관측(정상)'),
    ([('T_wo_only', 'DONE'), ('R_wo_only', 'DONE')], False, '닿지 않았습니다'),          # 정비 · 재관측 없이 정상 보고 — 회복 확인 없는 종결은 통과가 아니다
    ([('T_wo_only', 'DONE'), ('T_fix', 'DONE'), ('T_reobs_wo', 'DONE'), ('R_fail', 'DONE')], False, '정비 뒤'),
    ([('R_kind', 'DONE')], False, '실행하지 않았습니다'),
    ([('T_approve', 'IN_PROGRESS')], False, '닿지 않았습니다'),
], ids=['명령 → 재관측 → 작업지시', '미달', '작업지시만 → 정비 → 재관측', '작업지시만 재관측 없음', '작업지시만 미달', '조치 종류 밖', '멈춤'])
def test_승인_뒤_명령_재관측_작업지시가_정상_보고까지_가야_통과다(rows, ok, words):
    got, detail = cs.flow_result(view(*[(a, s, {}) for a, s in rows], status='COMPLETED'))
    assert got is ok and words in detail


def test_쿨러_경보는_감지기의_패턴별_칸에서_읽는다():
    """설비 하나에 패턴이 여럿이다 — 펌프 · 팬 패턴이 RAISED 여도 쿨러 판정은 쿨러 패턴 칸만 본다(감지기 API 실제 모양)."""
    state = {'patterns': {'COOLER_DEGRADATION': {'phase': 'RAISED', 'alert_id': 'a1'}, 'PUMP_LEAKAGE': {'phase': 'IDLE'},
                          'FAN_VIBRATION': {'phase': 'IDLE'}}, 'ts1': 61.2, 'ce': 40.0}
    assert cs.cooler_phase(state) == 'RAISED'
    assert cs.cooler_phase({**state, 'patterns': {**state['patterns'], 'COOLER_DEGRADATION': {'phase': 'IDLE'}, 'PUMP_LEAKAGE': {'phase': 'RAISED'}}}) == 'IDLE'


# ---------------------------------------------------------------- 기다리기: 「아직 아님」과 「실패」를 가른다
def test_기다리는_동안_서버_오류가_이어지면_시간이_다_됐을_때_그_오류를_까닭에_붙인다():
    clock = Clock()
    def probe():
        raise cs.ApiError(500, 'relation ent.work_orders does not exist')
    with pytest.raises(cs.Timeout) as caught:
        cs.wait_for(60, probe, '처리 건이 열리지 않았습니다', sleep=clock.sleep, clock=clock)
    assert '처리 건이 열리지 않았습니다' in str(caught.value) and 'ent.work_orders' in str(caught.value) and clock.now >= 60


def test_잠깐_답하지_않던_서비스가_답하면_그_값을_낸다():
    clock, answers = Clock(), [cs.ApiError(503, '켜지는 중'), None, {'phase': 'RAISED'}]
    def probe():
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
    assert cs.wait_for(60, probe, '경보', sleep=clock.sleep, clock=clock) == {'phase': 'RAISED'}


def test_응답_모양이_다르면_기다리지_않고_바로_드러난다():
    clock = Clock()
    with pytest.raises(KeyError):
        cs.wait_for(420, lambda: {}['patterns'], '경보', sleep=clock.sleep, clock=clock)
    assert clock.now == 0


# ---------------------------------------------------------------- 포털: 화면과 같은 출처 길(/svc/…)
@pytest.fixture
def portal(tmp_path):
    """포털 대역(바깥 — nginx 자리): 경로마다 정한 상태 코드로 답하는 실제 HTTP 서버. 시작이 남긴 포트 표가 그 포트를 가리킨다."""
    import http.server
    import json as _json
    import threading
    answers = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            code = answers.get(self.path, 404)
            self.send_response(code); self.end_headers(); self.wfile.write(b'{}')

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (tmp_path / '.hyd-runtime').mkdir()
    (tmp_path / '.hyd-runtime' / 'ports.json').write_text(_json.dumps({'8088': server.server_address[1]}), encoding='utf-8')
    yield tmp_path, answers
    server.shutdown()


@pytest.fixture
def process_api():
    """process 대역(바깥): 승인 고르기 · 미리 보기 요청을 받아 정한 답을 내고, 받은 몸을 남기는 실제 HTTP 서버."""
    import http.server
    import json as _json
    import threading
    plan, seen = {'select': []}, []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = _json.loads(self.rfile.read(int(self.headers['Content-Length'])) or b'{}')
            seen.append((self.path, body))
            code, answer = plan['select'].pop(0) if self.path.endswith('/select') else (200, {'id': 'review-1'})
            data = _json.dumps(answer, ensure_ascii=False).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}', plan, seen
    server.shutdown()


APPROVAL = {'decision': 'd1', 'option': 'fan-up', 'by': 'user:kim-op', 'role': 'role:operator', 'reason': '점검'}


def test_예측이_낡았다는_거절_코드면_미리_보기로_다시_검토해_그_검토로_승인한다(process_api):
    url, plan, seen = process_api
    plan['select'] = [(409, {'detail': {'code': 'review_required', 'reason': '현재 조건에서 승인을 보류합니다: 검토한 카드가 12분 전 예측입니다'}}),
                      (200, {'approval_status': 'APPROVED'})]
    cs.approve(url, 't1', APPROVAL)
    assert [p for p, _ in seen] == ['/api/todolist/t1/select', '/api/todolist/t1/decision-preview', '/api/todolist/t1/select']
    assert seen[-1][1] == dict(APPROVAL, review_id='review-1')


def test_다른_까닭의_승인_거절은_그_문장으로_멈추고_다시_고르지_않는다(process_api):
    url, plan, seen = process_api
    plan['select'] = [(403, {'detail': '이 카드의 승인 역할(role:prod-mgr)이 아닙니다'})]
    with pytest.raises(cs.CheckError, match='승인 역할'):
        cs.approve(url, 't1', APPROVAL)
    assert len(seen) == 1


@pytest.mark.parametrize('screen, process, problem', [
    (200, 200, None),
    (200, 502, '/svc/process/healthz'),                 # 화면은 뜨는데 포털을 거쳐 process 에 닿는 길이 끊김
    (500, 200, '/ '),
], ids=['둘_다_됨', '같은_출처_길_끊김', '화면_오류'])
def test_포털은_화면과_포털을_거쳐_process에_닿는_길을_둘_다_본다(portal, screen, process, problem):
    root, answers = portal
    answers.update({'/': screen, '/svc/process/healthz': process})
    found = cs.portal_problems(root)
    assert (found == []) if problem is None else (len(found) == 1 and problem.strip() in found[0])
