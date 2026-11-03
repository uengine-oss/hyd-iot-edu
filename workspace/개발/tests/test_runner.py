"""AI 워커 한 점유(worker/runner.py) — 실제 처리 흐름 · 실제 DB · 실제 수업 판정 · 실제 관문 장부. 바깥(Claude Code · 강의 중계 · 업무 도구 서버)만 대체물.

키 있는 PC(live): CLI 자리는 저장소 녹화 실행을 내며 녹화의 모델 호출 수만큼 관문을 실제로 부른다(RecordedCli). 키 없는 PC(replay): 녹화 재생.
"""
import json

import psycopg
import pytest
from psycopg.rows import dict_row

from conftest import rejected_first_replay, RELAY_KEY, SERVER_SECRET, RecordedCli, ask_question, events_of, model_turns, recording, start_handover, task_of


def ledger_runs(dsn, todo_id=None):
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        sql = 'SELECT * FROM hyd_course_runs' + (' WHERE todo_id=%s' if todo_id else '') + ' ORDER BY created_at'
        return db.execute(sql, (todo_id,) if todo_id else ()).fetchall()


def friendly(rt, todo_id):
    errors = events_of(rt, todo_id, 'error')
    return errors[-1]['data'] if errors else None


DRAFT = 'task:draft'


# ---------------------------------------------------------------- 키 있는 PC(실제 AI 자리 = 녹화 대체물)
def test_키_있는_PC의_교대_초안은_관문_토큰으로_모델을_부르고_결과를_제출한다(course, worker, relay):
    run = recording('handover/draft-1')['runs'][0]
    cli = RecordedCli(run)
    inst = start_handover(course.rt)
    assert worker('live', cli).poll_once() == 1
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['status'] == 'SUBMITTED', friendly(course.rt, task['id'])
    # 중계는 녹화의 모델 호출 수만큼 불렸고, 받은 키는 process 의 중계 키(CLI 가 쥔 실행 토큰이 아니다)
    assert len(relay.requests) == model_turns(run)
    assert {r['headers'].get('x-api-key') for r in relay.requests} == {RELAY_KEY}
    assert cli.requests[0].env['ANTHROPIC_API_KEY'].startswith('HydModel ')
    [ledger] = ledger_runs(course.dsn, str(task['id']))
    assert (ledger['state'], ledger['calls']) == ('ENDED', model_turns(run))


def test_업무_규칙은_CLI_시스템_프롬프트로_간다(course, worker):
    """CLI 가 받은 규칙 = 포털 에이전트 화면이 그 단계의 에이전트(agent:handover, 업무 규칙 칸은 seed 의 users.work_rules)에 보이는 글."""
    cli = RecordedCli(recording('handover/draft-1')['runs'][0])
    start_handover(course.rt)
    worker('live', cli).poll_once()
    args = cli.requests[0].request.extra_args
    # 설정 출처를 끈 CLI(--setting-sources '')는 작업 폴더의 규칙 파일을 읽지 않는다 — 규칙은 인자로 간다
    assert args[args.index('--setting-sources') + 1] == ''
    status, shown = course.world.api('GET', '/api/agents/agent:handover')
    assert status == 200 and shown['work_rules'] == 'hyd-handover', shown
    assert args[args.index('--append-system-prompt') + 1] == shown['work_rules_detail']['content']
    assert not (__import__('pathlib').Path(cli.requests[0].request.workdir) / 'CLAUDE.md').exists()


@pytest.mark.parametrize('status, body, code', [
    (401, {'error': {'message': 'Authentication Error, Invalid proxy server token passed'}}, 'relay_auth'),
    (400, {'error': {'message': 'Budget has been exceeded! Current cost: 5.1, Max budget: 5.0', 'type': 'budget_exceeded'}}, 'relay_budget'),
    (403, {'error': {'message': 'key not allowed to access model. This key can only access models=[coding]'}}, 'relay_model'),
    (429, {'error': {'message': 'Rate limit reached'}}, 'relay_busy'),
])
def test_강의_중계가_거절하면_학생이_할_일을_종류별_문장으로_남긴다(course, worker, relay, status, body, code):
    from procsvc.course_ledger import REASONS
    relay.answer(status, body)
    inst = start_handover(course.rt)
    worker('live', RecordedCli(recording('handover/draft-1')['runs'][0])).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    error = friendly(course.rt, task['id'])
    assert task['draft_status'] == 'FAILED'
    assert (error['name'], error['friendly']) == ('AI 중계 멈춤', REASONS[code].text)
    assert body['error']['message'] not in json.dumps(error, ensure_ascii=False)       # 중계 원문은 학생 칸에도 원문 칸에도 없다


def test_결과_파일에_실린_비밀값은_저장_전에_가려진다(course, worker):
    """#18: 에이전트가 작업 폴더의 .mcp.json 에서 읽은 비밀(도구 서버 인증 머리글)을 결과 파일에 적어도 DB · 처리 기록 · 결과 사본에 남지 않는다."""
    from procsvc.mcp_secrets import REDACTED
    run = recording('handover/draft-1')['runs'][0]

    def leaking(request):
        servers = json.loads((__import__('pathlib').Path(request.workdir) / '.mcp.json').read_text(encoding='utf8'))['mcpServers']
        secret = servers['enterprise']['headers']['Authorization']
        result = json.loads(run['result_file'])
        result['handover_summary'] = result['handover_summary'] + f' (연결 머리글 {secret})'
        return json.dumps(result, ensure_ascii=False)
    cli = RecordedCli(run, result_file=leaking)
    inst = start_handover(course.rt)
    worker('live', cli).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    workdir = __import__('pathlib').Path(cli.requests[0].request.workdir)
    stored = json.dumps([task['output'], [e['data'] for e in events_of(course.rt, task['id'])]], ensure_ascii=False) \
        + (workdir / 'outputs' / 'result.json').read_text(encoding='utf8')
    assert task['status'] == 'SUBMITTED'
    assert REDACTED in task['output']['handover_summary']
    assert SERVER_SECRET not in stored and SERVER_SECRET.split()[1] not in stored


# ---------------------------------------------------------------- 관문 장부: 같은 작업 이어 하기 · 동시 한도 · 늦은 결과
def test_같은_작업을_실패_뒤_다시_실행하면_10분이_지나도_새_실행으로_열린다(course, worker, relay):
    """B-01: 옛 장부는 작업 행 하나 = 실행 하나라 첫 실행 기한(10분) 뒤 같은 작업은 영구 거절이었다."""
    run = recording('handover/draft-1')['runs'][0]
    relay.answer(503, {'error': {'message': 'overloaded'}})
    inst = start_handover(course.rt)
    worker('live', RecordedCli(run)).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['draft_status'] == 'FAILED'
    with psycopg.connect(course.dsn) as db:      # 첫 실행이 열린 지 11분 지난 것으로
        db.execute("UPDATE hyd_course_runs SET created_at=now()-interval '11 minutes', deadline=now()-interval '1 minute'")
        db.execute("UPDATE todolist SET draft_status='FB_REQUESTED', consumer=NULL WHERE id=%s", (task['id'],))   # 사람이 다시 실행
    relay.reset()
    worker('live', RecordedCli(run)).poll_once()
    assert task_of(course.rt, inst['proc_inst_id'], DRAFT)['status'] == 'SUBMITTED'
    runs = ledger_runs(course.dsn, str(task['id']))
    assert [r['state'] for r in runs] == ['ENDED', 'ENDED'] and runs[1]['calls'] == model_turns(run) and runs[0]['consumer'] != runs[1]['consumer']


def test_사람에게_묻고_멈춘_작업은_PC의_다른_AI_단계를_막지_않는다(course, worker):
    """B-01 ②: 사람 대기 · 실패 · 보류로 끝난 점유의 실행은 동시 한도에 세지 않는다."""
    asked = dict(recording('handover/draft-1')['runs'][0])
    question = json.dumps({'__human_input__': {'question': '작업 메모의 정비 완료는 누가 확인했나요?', 'options': []}}, ensure_ascii=False)
    asked = dict(asked, events=[e for e in asked['events'] if e['kind'] != 'result'] + [{'kind': 'result', 'text': question}])
    first = start_handover(course.rt)
    worker('live', RecordedCli(asked, result_file=None, calls=2)).poll_once()
    asked_task = task_of(course.rt, first['proc_inst_id'], DRAFT)
    assert asked_task['draft_status'] == 'HUMAN_ASKED'
    with psycopg.connect(course.dsn) as db:      # G1-21: 질문 알림은 이 단계 뒤 첫 사람 단계(인계자)에게 — 늘 운전원이 아니라
        told = [r[0] for r in db.execute('SELECT user_id FROM notifications WHERE url=%s', (f"/todolist/{asked_task['id']}",))]
    assert told == ['user:kim-op']
    second = start_handover(course.rt)
    worker('live', RecordedCli(recording('handover/draft-1')['runs'][0])).poll_once()
    assert task_of(course.rt, second['proc_inst_id'], DRAFT)['status'] == 'SUBMITTED'


def test_살아_있는_다른_점유가_있으면_동시_한도로_학생_문장과_함께_멈춘다(course, worker):
    from procsvc.course_ledger import REASONS
    run = recording('handover/draft-1')['runs'][0]
    second = {}

    def other_claim(n, cli):
        if n == 1:          # 첫 작업이 실행 중일 때 두 번째 워커가 다른 작업을 잡는다
            second['inst'] = start_handover(course.rt)
            worker('live', RecordedCli(run), consumer='second-worker').poll_once()
    first = start_handover(course.rt)
    worker('live', RecordedCli(run, after=other_claim)).poll_once()
    assert task_of(course.rt, first['proc_inst_id'], DRAFT)['status'] == 'SUBMITTED'
    task = task_of(course.rt, second['inst']['proc_inst_id'], DRAFT)
    assert (task['draft_status'], friendly(course.rt, task['id'])['friendly']) == ('FAILED', REASONS['concurrent'].text)


def test_임대가_끊긴_사이_다른_워커가_잡으면_늦은_결과는_버리고_그_작업_폴더도_건드리지_않는다(course, worker, tmp_path):
    """워커 재시작 중 AI 단계: 임대 만료 뒤 재점유 → 앞 워커의 결과는 저장되지 않고(실행 중단), 이어받은 워커의 도구 설정(.mcp.json 비밀)은 남는다(하-02)."""
    run = recording('handover/draft-1')['runs'][0]
    taken = {}

    def reclaimed(n, cli):
        if n == 3:
            with psycopg.connect(course.dsn) as db:
                db.execute("UPDATE todolist SET lease_until=now()-interval '1 second' WHERE agent_orch='cliagents' AND draft_status='STARTED'")
            taken['rows'] = course.rt.repo.fetch_pending_task('cliagents', 'second-worker:x', tenant_id='hyd')
            mcp = __import__('pathlib').Path(cli.requests[0].request.workdir) / '.mcp.json'
            taken['mcp'] = mcp
            taken['before'] = mcp.read_text(encoding='utf8')
    inst = start_handover(course.rt)
    worker('live', RecordedCli(run, after=reclaimed)).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert (task['status'], task['draft_status'], task['consumer']) == ('IN_PROGRESS', 'STARTED', 'second-worker:x')
    assert [e['data']['name'] for e in events_of(course.rt, task['id'], 'task_cancelled')] == ['실행 중단']
    assert taken['mcp'].read_text(encoding='utf8') == taken['before']


@pytest.mark.parametrize('stop, name, said', [
    ('person', '작업 취소', '담당자가 실행을 취소했습니다.'),
    ('flow', '실행 멈춤', '처리 흐름이 이 단계를 닫아 실행을 멈췄습니다 — 까닭은 이 처리 건의 처리 기록에 있습니다.'),
], ids=['사람이 취소 요청', '처리 흐름이 닫음'])
def test_실행_도중_멈추면_누가_왜_멈췄는지를_작업_행대로_적는다(course, worker, stop, name, said):
    """재시작 확인(2026-11-01): 경보가 승인 전에 풀려 처리 흐름이 AI 단계를 닫았는데 「담당자가 실행을 취소했습니다」로 남았다 — 사람이 한 것처럼 읽혔다."""
    run = recording('handover/draft-1')['runs'][0]

    def stopped(n, cli):
        if n == 3:
            w = task_of(course.rt, inst['proc_inst_id'], DRAFT)
            if stop == 'person':
                course.rt.cancel_agent_task(w['id'], 'user:kim-op', '다시 하겠습니다')
            else:                    # 처리 흐름이 진행 중인 단계를 닫는 실제 함수(engine.abort_to — 열린 행을 모두 까닭과 함께 끝낸다)
                from datetime import datetime, timezone
                from procsvc import engine
                rt = course.rt
                live = rt.repo.get_instance(inst['proc_inst_id'])
                rows = rt.repo.list_workitems(inst['proc_inst_id'], None, None, None, None, rt.tenant_id)
                adv = engine.abort_to(rt.definition_for(live), live, rows, 'task:sender', 'cancelled outside', datetime.now(timezone.utc))
                for row in adv.updated:
                    rt.repo.update_workitem(row)
                rt.repo.insert_workitems(adv.created)
                rt.repo.update_instance(live)
    inst = start_handover(course.rt)
    worker('live', RecordedCli(run, after=stopped)).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    said_all = [(e['data']['name'], e['data']['goal']) for e in events_of(course.rt, task['id'], 'task_cancelled')]
    assert said_all[-1] == (name, said), said_all                       # 사람 취소는 process 의 「실행 취소 요청」 뒤에 워커 문장이 온다
    assert stop == 'person' or all('담당자' not in goal and 'cancelled' not in goal for _, goal in said_all), said_all   # 내부 글을 옮기지 않는다


# ---------------------------------------------------------------- 키 없는 PC(재생)
def test_키_없는_PC의_교대_초안은_녹화를_재생해_제출하고_스킬_구성이_다를_때만_재생을_알린다(course, worker, relay):
    """재생 화면은 실제 AI 실행과 같다 — 처리 과정의 재생 안내는 재생이 지원하지 않는 행동에서만(CLAUDE.md 5절). 여기서는 기본 교대
    에이전트의 스킬(shift-handover-review)이 저장된 실행이 연 스킬(my-shift-handover-review)과 달라 그 한 줄만 남는다."""
    inst = start_handover(course.rt)
    worker('replay').poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['status'] == 'SUBMITTED', friendly(course.rt, task['id'])
    notes = [str(e['data'].get('content')) for e in events_of(course.rt, task['id'], 'task_working')]
    said = [n for n in notes if '재생' in n or '강사' in n]
    assert len(said) == 1 and '같은 답을 냅니다' in said[0] and 'shift-handover-review' in said[0] and '강사' not in said[0], said
    assert relay.requests == [] and ledger_runs(course.dsn) == []        # 재생은 관문 · 중계를 부르지 않는다


def test_키_없는_PC의_교대_초안은_검사에_거절된_첫_답_뒤_녹화된_고친_답으로_이어_간다(course, worker, tmp_path):
    """FX 넘김(교대 재생 거절): 강사 녹화 첫 실행의 근거 번호 하나가 범위 밖(13개 중 13번)이라 process 검사가 「거절 1/3」으로 돌려보낸다.
    녹화에는 그 거절을 받고 AI 가 고친 둘째 실행이 함께 있다 — 워커가 다시 잡으면 그 실행으로 이어 가 검사를 통과한다(멈추지 않는다)."""
    replay = rejected_first_replay(tmp_path)                    # 거절될 첫 실행 → 고친 둘째 실행(시험이 만든 녹화)
    inst = start_handover(course.rt)
    worker('replay', replay_dir=replay).poll_once()
    course.rt.poll_once()
    first = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert (first['status'], first['draft_status']) == ('IN_PROGRESS', 'FB_REQUESTED') and '[Rejected 1/3]' in (first['log'] or '')
    worker('replay', replay_dir=replay).poll_once()
    course.rt.poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['status'] == 'DONE', (task['status'], task['log'])
    assert task['output']['cliagents_session_id'].endswith(':1')


def test_작업_이름을_바꾼_교대_흐름도_같은_녹화를_재생한다(course, worker):
    """B-02: 녹화 열쇠는 서버가 준 수업 AI 자리다 — 실라버스대로 bpmn.io 에서 작업 이름을 고쳐도 재생된다."""
    raw = json.loads((__import__('conftest').DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8'))
    raw['version'] = '9.1'
    for a in raw['activities']:
        if a['id'] == DRAFT:
            a['name'] = '우리 반 인계 초안 쓰기'
    course.rt.register_definition(raw)
    inst = start_handover(course.rt, version='9.1')
    worker('replay').poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert (task['activity_name'], task['status']) == ('우리 반 인계 초안 쓰기', 'SUBMITTED')


def test_녹화와_다른_설비로_시작한_교대는_바꿔_끼우지_않고_쉬운_말로_멈춘다(course, worker):
    """B-04: 녹화는 HYD-01 의 실측이다 — HYD-02 로 바꿔 끼워 그 설비의 사실처럼 보이지 않는다."""
    inst = start_handover(course.rt, asset='HYD-02')
    worker('replay').poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    error = friendly(course.rt, task['id'])
    assert task['draft_status'] == 'FAILED' and task.get('output') is None
    assert error['name'] == '재생 모드에서 지원하지 않는 AI 단계'
    assert 'HYD-01' in error['friendly'] and 'HYD-02' in error['friendly']


@pytest.mark.parametrize('question, answered', [
    ('HM-8 매뉴얼에서 쿨러 냉각 성능 상실의 즉시 완화 조치 절차 번호를 모두 알려 주고, 각 절차의 승인 역할도 알려 줘', True),
    ('HM-8 매뉴얼에서  쿨러 냉각 성능 상실의 즉시 완화 조치 절차 번호를 모두 알려 주고, 각 절차의 승인 역할도 알려 줘?', True),
    ('펌프 누설 절차를 알려 줘', False),
])
def test_키_없는_PC의_질문은_강의에서_다룬_질문에만_답한다(course, worker, question, answered):
    from procsvc import ask
    view = ask_question(course.rt, question)
    worker('replay').poll_once()
    after = ask.view(course.rt, view['id'])
    if answered:
        assert after['state'] in ('submitted', 'done'), after['message']
    else:
        assert after['state'] == 'failed'
        assert '수업에서 다룬 질문' in after['message'] and 'RuntimeError' not in after['message']


def test_워커가_다시_켜지면_끊긴_재생_실행을_처음부터_다시_낸다(course, worker):
    """#10 · G5b-07: 재생 중 워커가 죽으면(임대 만료 뒤 재점유) 다음 녹화 실행으로 넘어가지 않고 같은 실행을 다시 낸다.
    준비는 죽은 워커가 DB 에 남기는 그대로 — 실제 점유(fetch_pending_task) 한 번, 저장된 세션 replay:<열쇠>:0, 지난 임대."""
    from psycopg.types.json import Jsonb
    from worker import ai_replay
    inst = start_handover(course.rt)
    w = worker('replay', consumer='restarted-worker')
    (dead,) = course.rt.repo.fetch_pending_task(w.s.agent_orch, 'dead-worker:1', limit=1, tenant_id=w.s.tenant_id)
    session = f"{ai_replay.COURSE}{ai_replay.course_key('handover/draft-1', '')}:0"
    with psycopg.connect(course.dsn) as db:
        db.execute("UPDATE todolist SET draft=%s, lease_until=now()-interval '1 second' WHERE id=%s",
                   (Jsonb({'cliagents_session_id': session}), dead['id']))
    w.poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['status'] == 'SUBMITTED', friendly(course.rt, task['id'])
    assert task['output']['cliagents_session_id'] == session


# ---------------------------------------------------------------- 강사 녹화(record): 성공 확정 뒤에만 남긴다
def _replay_copy(tmp_path):
    import shutil
    from worker import ai_replay
    replay_dir = tmp_path / 'replay'
    shutil.copytree(__import__('conftest').REPLAY_DIR, replay_dir)
    return replay_dir, ai_replay.course_key('handover/draft-1', '')


def test_녹화_모드에서_실패한_실행은_좋은_녹화를_덮지_않는다(course, worker, tmp_path, relay):
    """#11: 녹화는 점유가 저장된 결과로 끝난 뒤에만 쓴다."""
    replay_dir, key = _replay_copy(tmp_path)
    before = (replay_dir / f'{key}.json.gz').read_bytes()
    relay.answer(503, {'error': {'message': 'overloaded'}})
    start_handover(course.rt)
    worker('record', RecordedCli(recording('handover/draft-1')['runs'][0]), replay_dir=replay_dir).poll_once()
    assert (replay_dir / f'{key}.json.gz').read_bytes() == before


def test_녹화_모드에서_제출된_실행은_그_자리의_녹화를_새로_쓴다(course, worker, tmp_path):
    from worker import ai_replay
    replay_dir, key = _replay_copy(tmp_path)
    start_handover(course.rt)
    worker('record', RecordedCli(recording('handover/draft-1')['runs'][0]), replay_dir=replay_dir).poll_once()
    after = ai_replay.Library(replay_dir).load(key)
    assert after['slot'] == 'handover/draft-1' and len(after['runs']) == 1 and after['recorded_at'] != recording('handover/draft-1')['recorded_at']


# ---------------------------------------------------------------- 키 있는 PC의 같은 요청 저장
def recorded_question():
    from worker import ai_replay
    doc = next(d for _, d in ai_replay.Library(__import__('conftest').REPLAY_DIR).docs() if d.get('slot') == 'question')
    return doc, doc['case'][len(ai_replay.QUESTION_PREFIX):]


def test_같은_질문을_다시_해도_앞선_답을_다시_쓰지_않고_지금_상태로_새로_답한다(course, worker, relay):
    """G1-09: 질문의 같은 요청 저장 열쇠에 지식 적재 · 업무 값이 없어 같은 질문에 옛 답을 냈다 — 질문은 저장하지 않는다(사용자 결정 기록).
    비용은 관문 장부(호출 상한)가 막는다."""
    from procsvc import ask
    doc, question = recorded_question()
    first = ask_question(course.rt, question)
    worker('live', RecordedCli(doc['runs'][0])).poll_once()
    _complete(course.rt, first['id'])
    calls = len(relay.requests)
    second = ask_question(course.rt, question + ' ')
    worker('live', RecordedCli(doc['runs'][0])).poll_once()
    assert len(relay.requests) == calls + model_turns(doc['runs'][0])        # 실제 AI 를 다시 불렀다
    assert ask.view(course.rt, second['id'])['state'] in ('submitted', 'done')


@pytest.mark.parametrize('agent', ['agent:pm-plan', 'agent:spare-buy'])
def test_정기_정비_구매_에이전트에게_물어도_질문용_읽기_서버로_답한다(course, worker, agent):
    """G1-02: 질문 창구가 허용 서버 사본(neo4j · enterprise · hyd-dmn)을 들고 목록 밖 서버(enterprise-maint 등)를 오류로 처리해,
    두 에이전트에게 물으면 키 있는 PC 에서 늘 「연결 확인 필요」로 끝났다. 이제 질문용 읽기 목록(QUESTION_READS) 한 곳의 서버만 붙인다."""
    from hydcommon.handover_tools import QUESTION_READS
    from procsvc import ask
    doc, question = recorded_question()
    view = ask.start(course.rt, question, agent, '수강생', definitions_dir=__import__('conftest').DEFINITIONS,
                     worker_probe=lambda: {'reachable': True})
    cli = RecordedCli(doc['runs'][0])
    worker('live', cli).poll_once()
    after = ask.view(course.rt, view['id'])
    assert after['state'] in ('submitted', 'done'), after['message']
    attached = json.loads((__import__('pathlib').Path(cli.requests[0].request.workdir) / '.mcp.json').read_text(encoding='utf8'))['mcpServers']
    assert attached and set(attached) <= set(QUESTION_READS)


def _complete(rt, proc_inst_id):
    """처리 흐름이 결과를 받아들인다(제출 → 끝남)."""
    rt.poll_once()
    task = task_of(rt, proc_inst_id)
    assert task['status'] == 'DONE', task['status']


@pytest.mark.parametrize('change', ['다른 질문', '에이전트 설정'])
def test_입력이나_설정이_하나라도_다르면_앞선_결과를_쓰지_않고_새로_실행한다(course, worker, relay, change):
    doc, question = recorded_question()
    first = ask_question(course.rt, question)
    worker('live', RecordedCli(doc['runs'][0])).poll_once()
    _complete(course.rt, first['id'])
    relay.reset()
    if change == '에이전트 설정':
        with psycopg.connect(course.dsn) as db:
            db.execute("UPDATE users SET goal = coalesce(goal,'') || ' 답은 두 문장으로.' WHERE id='sys:agent'")
    try:
        ask_question(course.rt, question if change != '다른 질문' else question + ' 그리고 담당 부서도')
        worker('live', RecordedCli(doc['runs'][0])).poll_once()
    finally:
        if change == '에이전트 설정':
            with psycopg.connect(course.dsn) as db:
                db.execute("UPDATE users SET goal = replace(goal, ' 답은 두 문장으로.', '') WHERE id='sys:agent'")
    assert len(relay.requests) == model_turns(doc['runs'][0])        # 실제 AI 를 다시 불렀다


def test_앞선_실행이_실패였으면_남긴_것이_없어_다시_실행하면_실제_AI를_부른다(course, worker, relay, tmp_path):
    import uuid
    from procsvc import ask
    doc, question = recorded_question()
    relay.answer(503, {'error': {'message': 'overloaded'}})
    first = ask_question(course.rt, question)
    w = worker('live', RecordedCli(doc['runs'][0]))
    w.poll_once()
    assert ask.view(course.rt, first['id'])['state'] == 'failed'
    assert not list(w.s.ai_cache_dir.glob('*.json.gz'))              # 실패한 실행은 같은 요청 저장에 남지 않는다
    relay.reset()
    ask.retry(course.rt, first['id'], str(uuid.uuid4()), '수강생', '중계가 다시 열려 재개합니다')
    worker('live', RecordedCli(doc['runs'][0])).poll_once()
    assert len(relay.requests) == model_turns(doc['runs'][0])
    assert ask.view(course.rt, first['id'])['state'] in ('submitted', 'done')


def test_사람이_답한_뒤_작업_폴더가_정리돼_없으면_그_까닭을_말하고_새로_시작한다(course, worker):
    """하-03: 폴더를 먼저 만들고 나서 있었는지 물어 「작업 공간이 정리되어…」가 나올 수 없었다(늘 「세션 정보를 찾을 수 없어」)."""
    inst = start_handover(course.rt)
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    with psycopg.connect(course.dsn) as db:      # 사람이 답했다(질문 기록은 남지 않은 옛 행 — 이어 갈 세션은 작업 폴더에서만 찾는다)
        db.execute('''UPDATE todolist SET draft_status='FB_REQUESTED', consumer=NULL, draft='{}'::jsonb,
                      feedback='{"human_answer": "정비 완료는 박정비가 확인했습니다", "job_id": "ask-1"}'::jsonb WHERE id=%s''', (task['id'],))
    worker('replay').poll_once()
    notes = [str(e['data'].get('content')) for e in events_of(course.rt, task['id'], 'task_working')]
    assert any('이전 작업 공간이 정리되어 이어갈 수 없습니다' in n for n in notes)


def test_관문이_정한_한_번_실행_기한을_넘으면_그_실제_기한으로_말하고_멈춘다(course, worker, monkeypatch):
    """B-01: 관문 기한(10분)으로 끊기는데 문구는 워커 자체 기한 「(1800s)」였다. 여기서는 관문 정책을 1초로 줄여 확인한다."""
    import time
    from conftest import until
    from procsvc import course_ledger
    monkeypatch.setitem(course_ledger.POLICY['run'], 'seconds', 1)        # 관문 정책(설정 값) — 끝나면 되돌린다
    inst = start_handover(course.rt)

    def past_deadline(n, cli):       # G5b-12: 「1초가 지났겠지」가 아니라 관문이 정한 기한(DB)을 이 PC 시계가 넘을 때까지
        if n == 1:
            deadline = ledger_runs(course.dsn)[-1]['deadline']
            until(lambda: time.time() > deadline.timestamp(), '관문 실행 기한이 지남', timeout=30)
    worker('live', RecordedCli(recording('handover/draft-1')['runs'][0], calls=0, after=past_deadline)).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['draft_status'] == 'FAILED'
    assert friendly(course.rt, task['id'])['friendly'].startswith('AI 단계가 한 번 실행 시간(1초)을 넘어 멈췄습니다')
