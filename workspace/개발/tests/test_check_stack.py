"""시작 5 · 8단계와 점검(scripts/check_stack.py)의 판정 — 무엇을 「떴다 · 통과 · 해당 없음 · 실패」로 보는가.

규칙(정답의 출처):
  · 서비스 목록은 손으로 적지 않고 compose 가 아는 서비스 전부다(옛 시작 · 점검은 effects-mcp 8197 등을 빠뜨렸다 — 견적 #20, E6).
    계속 도는 서비스 = running + healthy(건강 확인 없는 선택 도구는 running), 한 번 도는 준비 작업(재시작 정책 no) = 종료 코드 0.
    다 뜬 것처럼 보여도 확인하는 동안 다시 시작한 서비스가 있으면 「재시작 반복」으로 실패(옛 시작은 찍기만 하고 「완료」).
  · AI 단계: 워커가 .env 의 AI_MODE 로 켜져야 한다. 키 없음(replay)은 저장된 응답이 있으면 「해당 없음」(강의 중계를 부르지 않는다 —
    옛 점검은 「건너뜀」을 「통과」로 표시), 없으면 실패. 키 있음은 process 안의 중계 확인 결과 그대로.
  · 쿨러 한 바퀴의 승인은 추천 카드의 승인 역할을 가진 사람으로 한다(포털에서 「나」를 그 사람으로 고르고 [승인]).
  · 쿨러 한 바퀴는 쿨러 경보를 기본 제공 흐름이 맡을 때만 돈다(경보 경로표). 학생이 배포한 자기 흐름이 맡으면 그 흐름의 승인을 점검이 대신하지
    않아 「해당 없음」, 기본 제공 흐름이 배포되지 않았으면 실패와 시작 안내.
  · AI 판단 단계가 멈추면(보류 · 실패) 서버가 판정한 멈춤(처리 건 보기의 attention — 포털 「사람 조치 필요」 알림과 같은 것)과 그 까닭을
    그대로 말한다. 점검이 까닭을 짐작하지 않는다(옛 점검: 보류면 늘 「기본 지식이 없는 것 같다」 — 실제 AI 는 시작 직후 「관측 공백」으로
    보류했다. 실패는 서버에 없는 상태 값을 보아 7분 뒤 「닿지 않았다」).
  · 키 있는 PC 는 결함을 넣기 전에 AI가 판단에 쓰는 기간만큼 설비 기록이 쌓이기를 기다린다 — 판단 실험(에이전트 서비스)의 관측 범위로
    재고, 그 기간 + 여유가 지나도 비면 기록이 끊기는 것이라 실패, 잴 수 없으면 까닭을 알리고 기다리지 않는다.
Docker · 처리 엔진 · 에이전트 서비스 응답은 바깥이라, docker compose ps 와 각 API 의 실제 모양(이 PC 스택에서 읽음)으로 만든 값을 넣는다.
처리 건 보기의 멈춤 판정(attention)은 서버 함수 그대로 계산한다. 시계 · 잠은 주입.
"""
import pytest

import check_stack as cs
from procsvc.instances import attention

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
    ([('서비스', PASS, ''), ('강의 중계', NA, 'AI 키 없음')], 0),
    ([('서비스', PASS, ''), ('승인 뒤 실행', FAIL, '미달')], 1),
])
def test_해당_없음은_실패로_세지_않고_실패가_있으면_1로_끝난다(capsys, results, code):
    assert cs.show(results) == code
    out = capsys.readouterr().out
    assert ('실패 1건' in out) is bool(code)


# ---------------------------------------------------------------- 쿨러 사건 한 바퀴(처리 엔진 응답의 실제 모양으로)
def view(*rows, status='RUNNING', events=(), variables=None, **instance):
    """GET /api/instances/{id} 의 모양 — attention 은 서버(procsvc.instances.attention)가 계산하는 그대로. instance: 처리 건 칸(end_label 등)."""
    inst = {'status': status, 'variables_data': [{'key': k, 'value': v} for k, v in (variables or {}).items()], **instance}
    items = [{'activity_id': a, 'status': s, 'id': f'w-{a}', 'tool': f'tool:{a}', **extra} for a, s, extra in rows]
    return {'instance': inst, 'workitems': items, 'events': list(events), 'attention': attention(inst, items, [], list(events))}


AI = {'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE'}
GAP = '팬 진동과 캐비닛 온도 기록에 관측 공백이 있어 원인을 확정하고 냉각 조치를 비교할 근거가 부족합니다. 센서 기록의 연속성을 확인한 뒤 다시 평가해 주세요.'


def deferred(reason, *, event=True):
    """AI 가 판단을 보류한 처리 건(procsvc/task_deferral.defer 가 남기는 모양): 단계는 PENDING + draft._deferral, 기록에 [DEFERRED] 까닭,
    사건 task_deferred 의 message = 까닭(2026-11-17 실제 AI 점검의 업무 DB 에서 읽은 까닭)."""
    row = ('T_agent', 'PENDING', dict(AI, draft={'_deferral': {'id': 'run-1', 'reason': reason}}, log=f'[DEFERRED] {reason}; ' if reason else ''))
    events = [{'todo_id': 'w-T_agent', 'event_type': 'task_deferred', 'data': {'message': reason, 'receipt': {'reason': reason}}}] if event else []
    return view(row, events=events)


def failed(friendly):
    """AI 실행이 실패한 처리 건(procdb: 단계는 IN_PROGRESS + draft_status FAILED, 사건 error 의 friendly = 학생 문장)."""
    return view(('T_agent', 'IN_PROGRESS', dict(AI, draft_status='FAILED', log='run failed; ')),
                events=[{'todo_id': 'w-T_agent', 'event_type': 'error', 'data': {'friendly': friendly}}])


@pytest.mark.parametrize('v, expected', [
    (view(('T_agent', 'DONE', dict(AI)), ('T_approve', 'IN_PROGRESS', {})), 'approval'),
    (view(('T_agent', 'IN_PROGRESS', dict(AI, draft_status='STARTED'))), None),
], ids=['approval', 'thinking'])
def test_AI_판단_단계가_승인에_닿았는지_아직인지_가른다(v, expected):
    out = cs.agent_outcome(v, 'replay')
    assert (out[0] if out else None) == expected


@pytest.mark.parametrize('v, ai_mode, said, not_said', [
    (deferred(GAP), 'live', GAP, '기본 지식'),                                          # 보류 — AI 가 남긴 까닭 그대로
    (deferred('', event=False), 'live', '까닭을 남기지 않았습니다', '기본 지식'),            # 까닭이 없으면 없다고
    (failed('이 AI 단계는 수업에서 허용한 흐름이 아니라 실행하지 않았습니다'), 'live', '수업에서 허용한 흐름이 아니라', 'README'),
    (view(('T_agent', 'IN_PROGRESS', dict(AI, draft_status='FAILED'))), 'replay', '새 판 받기', 'LLM_API_KEY'),      # 까닭이 기록되지 않은 실패
    (failed("「원인 진단 · 냉각 조치 제안」의 결과를 이 PC에 등록하지 못했습니다 — '쿨러 성능 저하'의 원인 지식이 아직 없습니다 — 지식 › 문서 등록에서 …"),
     'replay', '까닭에 적힌 대로 고친 뒤', '새 판 받기'),
    (failed('AI 키가 없을 때 쓰는 재생 모드에서는 「원인 진단 · 냉각 조치 제안」의 준비된 AI 판단을 이 처리 건에 쓸 수 없습니다. 권장 조치가 …'),
     'replay', '준비된 AI 판단을 이 처리 건에 쓸 수 없습니다', '새 판 받기'),
], ids=['보류_까닭', '보류_까닭없음', '실패_키', '실패_재생_까닭없음', '실패_지식없음_재생', '실패_판단다름_재생'])
def test_AI_판단_단계가_멈추면_서버가_판정한_멈춤의_까닭을_그대로_말한다(v, ai_mode, said, not_said):
    with pytest.raises(cs.CheckError) as caught:
        cs.agent_outcome(v, ai_mode)
    assert said in str(caught.value) and not_said not in str(caught.value)


@pytest.mark.parametrize('v, said', [
    (view(('T_agent', 'DONE', dict(AI, activity_name='AI 판단 · 제안', end_date='2026-11-17T05:00:00+00:00')),
          ('T_decide', 'DONE', dict(activity_name='조치 필요 확인', end_date='2026-11-17T05:00:04+00:00')),
          status='COMPLETED', end_event='incident-ended-before-action', end_label='조치 전 해소'), ('조치 전 해소', '조치 필요 확인')),
    (view(('T_agent', 'CANCELLED', dict(AI, activity_name='AI 판단 · 제안', end_date='2026-11-17T05:00:00+00:00')), status='CANCELLED',
          end_label='취소'), ('취소', 'AI 판단 · 제안')),
    (view(('T_agent', 'DONE', dict(AI, activity_name='AI 판단 · 제안', end_date='2026-11-17T05:00:00+00:00')), status='COMPLETED'), ('끝남',)),
], ids=['조치_전_해소', '취소', '끝_이름_없음'])
def test_처리_건이_승인에_닿기_전에_끝나면_기다리지_않고_어디서_끝났는지_말한다(v, said):
    """옛 점검은 끝난 처리 건을 「아직」으로 보아 AI 판단 한도 7분을 다 기다린 뒤 「닿지 않았다」고만 했다."""
    with pytest.raises(cs.CheckError) as caught:
        cs.agent_outcome(v, 'live')
    assert '승인 단계에 닿기 전에 끝났습니다' in str(caught.value) and all(w in str(caught.value) for w in said)


def test_추천_카드는_그_승인_역할을_가진_사람으로_승인한다():
    decision = {'recommended': 'fan-up', 'options': [{'id': 'derate', 'approver': {'id': 'role:prod-mgr'}},
                                                     {'id': 'fan-up', 'approver': {'id': 'role:operator'}}]}
    people = [{'id': 'sys:process', 'roles': []}, {'id': 'user:me', 'roles': ['role:prod-mgr', 'role:operator']}]     # 사람은 이 PC의 담당자 한 명(모든 역할)
    assert cs.pick_approval(decision, people) == ('fan-up', 'role:operator', 'user:me')


@pytest.mark.parametrize('decision, people', [
    ({'recommended': None, 'options': []}, []),
    ({'recommended': 'fan-up', 'options': [{'id': 'fan-up', 'approver': {'id': 'role:operator'}}]}, [{'id': 'u', 'roles': ['role:x']}]),
])
def test_추천_카드나_승인할_사람이_없으면_까닭을_보이고_멈춘다(decision, people):
    with pytest.raises(cs.CheckError):
        cs.pick_approval(decision, people)


@pytest.mark.parametrize('rows, ok, words', [
    ([('T_cmd', 'DONE'), ('T_reobs', 'DONE'), ('T_wo', 'DONE'), ('R_ok', 'DONE')], True, '정비 요청'),
    ([('T_cmd', 'DONE'), ('T_reobs', 'DONE'), ('R_fail', 'DONE')], False, '미달'),
    ([('T_wo_only', 'DONE'), ('T_fix', 'DONE'), ('T_reobs_wo', 'DONE'), ('R_wo_only', 'DONE')], True, '정비 수행 → 효과 확인(정상)'),
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


# ---------------------------------------------------------------- 점검 정리: 서버가 멈췄다고 판정한 단계를 닫는다
@pytest.fixture
def services():
    """process · 설비 대역(바깥): POST 는 200 {} 로 받고 남기며, GET /api/inbox/users 는 업무 DB 의 사람 목록 모양으로 답하는 실제 HTTP 서버."""
    import http.server
    import json as _json
    import threading
    posts = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, answer):
            data = _json.dumps(answer, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)

        def do_GET(self):
            self._send([{'id': 'user:me', 'roles': ['role:operator']}] if self.path == '/api/inbox/users' else {})

        def do_POST(self):
            posts.append((self.path, _json.loads(self.rfile.read(int(self.headers['Content-Length'])) or b'{}')))
            self._send({})

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}', posts
    server.shutdown()


@pytest.mark.parametrize('stopped', [
    ('T_agent', 'IN_PROGRESS', dict(AI, draft_status='FAILED')),          # AI 실행 실패
    ('T_agent', 'IN_PROGRESS', dict(AI, draft_status='CANCELLED')),       # 실행 취소
    ('T_agent', 'PENDING', dict(AI, draft={'_deferral': {'id': 'run-1', 'reason': GAP}})),            # 보류
], ids=['실행_실패', '실행_취소', '보류'])
def test_점검_정리는_서버가_멈췄다고_판정한_AI_단계를_닫고_처리_건이_끝나면_통과다(services, monkeypatch, stopped):
    url, posts = services
    clock, results = Clock(), []
    monkeypatch.setattr(cs, 'wait_for', __import__('functools').partial(cs.wait_for, sleep=clock.sleep, clock=clock))
    closed = lambda: any(path == '/api/todolist/w-T_agent/close' for path, _ in posts)
    current = lambda pid: view(stopped, status='COMPLETED' if closed() else 'RUNNING')       # 닫으면 처리 건이 「사람이 닫음」으로 끝난다
    cs.cleanup(url, url, 'c3_cooling.x', None, current, lambda *row: results.append(row))
    assert ('/api/todolist/w-T_agent/close', {'by': 'user:me', 'reason': '시스템 점검이 연 처리 건 정리'}) in posts
    assert results == [('점검 정리', PASS, '쿨러 · 설비를 되돌리고 점검이 연 처리 건을 닫았습니다')]


# ---------------------------------------------------------------- 쿨러 한 바퀴의 앞: 쿨러 경보의 원인 지식이 있는가
@pytest.mark.parametrize('patterns, outcome, said', [
    ([{'code': 'COOLER_DEGRADATION', 'judgeable': True, 'reason': None}], None, None),
    ([{'code': 'COOLER_DEGRADATION', 'judgeable': False, 'reason': "'쿨러 성능 저하'의 원인 지식이 아직 없습니다 — 지식 › 문서 등록에서 …"}],
     NA, "한 바퀴를 돌리지 않았습니다 — '쿨러 성능 저하'의 원인 지식이 아직 없습니다"),
    ([{'code': 'PM_DUE', 'judgeable': False}], FAIL, '지식 지도에 이상 패턴 COOLER_DEGRADATION이 없습니다'),
], ids=['원인 지식 있음 — 돌린다', '학생이 쿨러 문서를 비움 — 해당 없음과 서버의 까닭', '바탕 지식의 패턴 없음 — 실패'])
def test_쿨러_원인_지식이_없으면_결함을_넣지_않고_서버가_말한_까닭으로_한_바퀴를_돌리지_않는다(patterns, outcome, said):
    """비운 지식에서 점검이 결함을 넣고 처리 건을 연 뒤 AI 단계에서 멈추며 「준비된 AI 응답이 든 새 판을 받았는지」라는 엉뚱한 까닭을 붙였다."""
    import http.server
    import json as _json
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            data = _json.dumps(patterns if self.path == '/api/ontology/patterns' else {}, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        got = cs.cooler_knowledge(f'http://127.0.0.1:{server.server_address[1]}')
    finally:
        server.shutdown()
    assert (got is None) if outcome is None else (got[0] == outcome and said in got[1]), got


def _route(pattern, definition, name, source, class_flow):
    """경보 경로표 한 줄(procsvc.flow_deploy.routes 의 routes[] 모양)."""
    return {'pattern': pattern, 'definition': definition, 'name': name, 'version': '1', 'reference': False, 'class_flow': class_flow, 'source': source}


@pytest.mark.parametrize('rows, outcome, said, not_said', [
    ([_route('COOLER_DEGRADATION', 'c3_cooling', '냉각 긴급 대응', '기본 제공 흐름', True)], None, None, None),
    ([_route('COOLER_DEGRADATION', 'my_cooling', '우리 공장 냉각 대응', '내가 배포한 흐름', False)],
     NA, '쿨러 경보를 여는 흐름이 지금 내가 배포한 흐름 「우리 공장 냉각 대응」입니다', '시작 파일'),
    ([_route('COOLER_DEGRADATION', 'anomaly_response', '이상 대응', '기준 흐름', False)],
     FAIL, '시작 파일을 다시 실행하면 기본 제공 흐름을 배포합니다', '내가 배포한'),
    ([_route('PUMP_LEAKAGE', 'anomaly_response', '이상 대응', '기준 흐름', False)], FAIL, '여는 흐름이 없습니다', None),
], ids=['기본 제공 흐름 — 돌린다', '학생이 배포한 자기 냉각 흐름 — 해당 없음', '기본 제공 흐름이 배포되지 않음 — 실패와 시작 안내', '경로표에 쿨러 경보 없음'])
def test_쿨러_경보를_학생이_배포한_자기_흐름이_맡으면_결함을_넣지_않고_해당_없음이다(rows, outcome, said, not_said):
    """PBL 에서 학생이 자기 냉각 흐름을 배포하면 쿨러 경보는 가장 최근 배포가 맡는다. 전에는 점검이 결함을 넣고 처리 건을 연 뒤 「수업 흐름이
    아님 — 시작 파일을 다시 실행하면 수업 흐름을 배포합니다」로 실패했다(시작은 같은 내용의 기본 제공 흐름을 다시 배포하지 않아 계속 실패)."""
    import http.server
    import json as _json
    import threading
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            data = _json.dumps({'routes': rows, 'flows': []} if self.path == '/api/flows/deployments' else {}, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        got = cs.cooler_route(f'http://127.0.0.1:{server.server_address[1]}')
    finally:
        server.shutdown()
    assert seen == ['/api/flows/deployments']
    if outcome is None:
        assert got is None
    else:
        assert got[0] == outcome and said in got[1] and (not_said is None or not_said not in got[1]), got


@pytest.mark.parametrize('patterns, rows, asked, said', [
    ([{'code': 'COOLER_DEGRADATION', 'judgeable': True, 'reason': None}],
     [_route('COOLER_DEGRADATION', 'my_cooling', '우리 공장 냉각 대응', '내가 배포한 흐름', False)],
     ['/svc/agent/api/ontology/patterns', '/svc/process/api/flows/deployments'], '쿨러 경보를 여는 흐름이 지금 내가 배포한 흐름 「우리 공장 냉각 대응」입니다'),
    ([{'code': 'COOLER_DEGRADATION', 'judgeable': False, 'reason': "'쿨러 성능 저하'의 원인 지식이 아직 없습니다 — 지식 › 문서 등록에서 …"}],
     [_route('COOLER_DEGRADATION', 'c3_cooling', '냉각 긴급 대응', '기본 제공 흐름', True)],
     ['/svc/agent/api/ontology/patterns'], "'쿨러 성능 저하'의 원인 지식이 아직 없습니다"),
], ids=['경로표가 학생 흐름', '원인 지식이 없음'])
def test_점검_한_바퀴는_경로표나_원인_지식이_막으면_설비와_처리_건을_건드리지_않는다(tmp_path, patterns, rows, asked, said):
    """막히면 설비 초기화 · 결함 주입 · 정리를 하나도 하지 않고 그 한 줄만 남긴다(학생 처리 건 · 설비를 바꾸지 않는다). 처리 엔진 · 에이전트 ·
    설비 · 감지기는 바깥이라 그 API 의 실제 모양으로 답하는 실제 HTTP 서버 하나가 포털 자리에서 맡고(점검은 서비스를 포털의 같은 출처 길
    /svc/<서비스>/ 로 부른다 — 서비스 포트는 PC 에 열지 않는다), 받은 요청을 모두 남긴다. 그 서버의 포트를 이 PC 의 포트 표(.hyd-runtime/ports.json
    의 포털 8088 자리)와 AI 모드(.env)에 적은 저장소 자리에서 점검이 그대로 돈다."""
    import http.server
    import json as _json
    import threading
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def _answer(self):
            seen.append((self.command, self.path))
            data = {'/svc/agent/api/ontology/patterns': patterns, '/svc/process/api/flows/deployments': {'routes': rows, 'flows': []}}.get(self.path, {})
            body = _json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)
        do_GET = do_POST = _answer

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    (tmp_path / '.hyd-runtime').mkdir()
    (tmp_path / '.hyd-runtime' / 'ports.json').write_text(_json.dumps({'8088': port}), encoding='utf-8')
    (tmp_path / '.env').write_text('AI_MODE=replay\n', encoding='utf-8')
    results = []
    try:
        cs.cooler_round(tmp_path, lambda *row: results.append(row))
    finally:
        server.shutdown()
    assert seen == [('GET', path) for path in asked], seen
    assert len(results) == 1 and results[0][:2] == ('쿨러 사건', NA) and results[0][2].startswith('한 바퀴를 돌리지 않았습니다 — ') and said in results[0][2], results


# ---------------------------------------------------------------- 키 있는 PC: 결함 전에 AI가 판단에 쓰는 설비 기록이 쌓이기를 기다린다
@pytest.fixture
def agent_api():
    """에이전트 서비스 대역(바깥): POST /api/agent/decide 에 정한 답을 차례로 내는(마지막 것은 계속) 실제 HTTP 서버. 받은 몸을 남긴다."""
    import http.server
    import json as _json
    import threading
    plan, seen = [], []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, _json.loads(self.rfile.read(int(self.headers['Content-Length'])) or b'{}')))
            code, answer = plan.pop(0) if len(plan) > 1 else plan[0]
            data = _json.dumps(answer, ensure_ascii=False).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}', plan, seen
    server.shutdown()


def evidence(tag, window, max_gap, limit):
    """판단 실험 응답의 근거 한 줄(agentsvc card.rank_causes 가 mcp_tsdb.evaluate 결과를 옮긴 모양 — 2026-11-17 이 스택에서 읽음)."""
    covered = max_gap <= limit
    return {'id': f'evd:{tag.lower()}-{window}', 'name': f'최근 {window}초 {tag}', 'tag': tag, 'passed': True if covered else None,
            'status': 'PASS' if covered else 'UNKNOWN', **({} if covered else {'reason': 'OBSERVATION_GAP'}),
            'coverage': {'samples': 96, 'max_gap_s': max_gap, 'limit_s': limit, 'covered': covered, 'tag': tag, 'window_s': float(window)}}


def withheld(*rows):        # 근거가 덜 모여 판단 보류 — 409 detail 에 근거 목록
    return 409, {'detail': {'reason': '근거 조회가 불완전하여 원인 순위와 조치를 보류합니다.', 'causes': [{'id': 'cause:cooler-fin-fouling', 'evidence': list(rows)}]}}


def judged(*rows):          # 근거가 다 모여 판단함 — 200 본문에 근거 목록
    return 200, {'status': 'EVALUATED', 'causes': [{'id': 'cause:cooler-fin-fouling', 'evidence': list(rows)}]}


START_GAP = evidence('VS1', 120, 24.55, 3.0), evidence('CE', 30, 1.0, 3.0)            # 시작 직후: 창 앞부분 24초가 기록 전
FILLED = evidence('VS1', 120, 1.0, 3.0), evidence('CE', 30, 1.0, 3.0)


def test_시작_직후면_AI가_판단에_쓰는_기간만큼_기록이_쌓일_때까지_기다리고_결함을_넣는다(agent_api):
    url, plan, seen = agent_api
    plan[:] = [withheld(*START_GAP), withheld(*START_GAP), judged(*FILLED)]
    clock, said = Clock(), []
    cs.wait_for_record(url, say=said.append, sleep=clock.sleep, clock=clock)
    assert [p for p, _ in seen] == ['/api/agent/decide'] * 3 and seen[0][1] == {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}
    assert clock.now == 10 and len(said) == 1 and '최근 120초' in said[0] and f'최대 {120 + cs.RECORD_SPARE}초' in said[0]


def test_그_기간과_여유가_지나도_비면_기록이_끊기는_것이라_실패하고_빈_곳을_말한다(agent_api):
    url, plan, _ = agent_api
    plan[:] = [withheld(*START_GAP)]
    clock = Clock()
    with pytest.raises(cs.CheckError) as caught:
        cs.wait_for_record(url, say=lambda s: None, sleep=clock.sleep, clock=clock)
    assert clock.now >= 120 + cs.RECORD_SPARE
    assert 'VS1' in str(caught.value) and '24.55초 동안 값 없음' in str(caught.value) and 'CE' not in str(caught.value)


@pytest.mark.parametrize('answer, said', [
    (judged(*FILLED), None),                                                            # 이미 다 쌓였다(오래 켜 둔 PC)
    ((404, {'detail': "'쿨러 성능 저하'의 원인 지식이 아직 없습니다 — 지식 › 문서 등록에서 매뉴얼을 적재한 뒤 다시 실행하세요"}), '원인 지식이 아직 없습니다'),
], ids=['이미_쌓임', '잴_수_없음'])
def test_기록이_이미_있거나_잴_수_없으면_기다리지_않는다(agent_api, answer, said):
    url, plan, seen = agent_api
    plan[:] = [answer]
    clock, lines = Clock(), []
    cs.wait_for_record(url, say=lines.append, sleep=clock.sleep, clock=clock)
    assert clock.now == 0 and len(seen) == 1
    assert (lines == []) if said is None else (len(lines) == 1 and said in lines[0])


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


APPROVAL = {'decision': 'd1', 'option': 'fan-up', 'by': 'user:me', 'role': 'role:operator', 'reason': '점검'}


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
    found = cs.portal_problems(root, 0, inside=lambda: pytest.fail('응답은 왔다 — 컨테이너 안을 두드릴 까닭이 없다'))
    assert (found == []) if problem is None else (len(found) == 1 and problem.strip() in found[0])


def test_막_다시_만든_포털이_잠깐_답하지_않다가_답하면_통과다(portal):
    root, answers = portal
    answers.update({'/': 502, '/svc/process/healthz': 502})
    waited = []
    def sleep(seconds):                                  # 두드리는 사이 포털이 뜬다
        waited.append(seconds)
        answers.update({'/': 200, '/svc/process/healthz': 200})
    assert cs.portal_problems(root, 30, sleep=sleep) == [] and waited == [3]


@pytest.fixture
def cut_port(tmp_path):
    """연결을 받자마자 끊는 실제 포트 — 2026-11-25 학생 PC 의 5/8단계 꼴(컨테이너는 모두 정상인데 PC 쪽 포털 주소가 「Remote end closed connection
    without response」). 시작이 남긴 포트 표가 그 포트를 가리킨다."""
    import json as _json
    import socket
    import threading
    server = socket.socket()
    server.bind(('127.0.0.1', 0)); server.listen()
    stop = threading.Event()
    def serve():
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                continue
            conn.close()
    threading.Thread(target=serve, daemon=True).start()
    (tmp_path / '.hyd-runtime').mkdir()
    (tmp_path / '.hyd-runtime' / 'ports.json').write_text(_json.dumps({'8088': server.getsockname()[1]}), encoding='utf-8')
    yield tmp_path, server.getsockname()[1]
    stop.set(); server.close()


@pytest.mark.parametrize('inside, others, said, not_said', [
    (True, [], ['포트 {port}번으로 들어가는 연결만 끊깁니다', 'Docker Desktop 을 다시 켠 뒤'], ['logs portal']),
    (True, ['someapp.exe(PID 42)'], ['다른 프로그램이 듣고 있습니다: someapp.exe(PID 42)'], ['Docker Desktop 을 다시 켠 뒤']),
    (False, [], ['컨테이너 안에서도 답하지 않습니다', 'docker compose logs portal'], ['Docker Desktop']),
], ids=['안은_됨_PC쪽만_끊김', '그_포트를_다른_프로그램이_들음', '안에서도_안_됨'])
def test_PC에서_포털_연결이_끊기면_컨테이너_안을_두드려_어디_탓인지_가르고_할_일을_말한다(cut_port, inside, others, said, not_said):
    root, port_no = cut_port
    found = cs.portal_problems(root, 0, inside=lambda: inside, listeners=lambda p: others if p == port_no else pytest.fail(p))
    assert len(found) == 3 and all('응답하지 않음' in f for f in found[:2]), found
    assert all(w.format(port=port_no) in found[2] for w in said) and not any(w in found[2] for w in not_said), found[2]

