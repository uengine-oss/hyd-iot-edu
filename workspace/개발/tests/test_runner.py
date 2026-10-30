"""AI 워커 한 점유(worker/runner.py) — 실제 처리 흐름 · 실제 DB · 실제 수업 판정 · 실제 관문 장부. 바깥(Claude Code · 강의 중계 · 업무 도구 서버)만 대체물.

키 있는 PC(live): CLI 자리는 저장소 녹화 실행을 내며 녹화의 모델 호출 수만큼 관문을 실제로 부른다(RecordedCli). 키 없는 PC(replay): 녹화 재생.
"""
import json

import psycopg
import pytest
from psycopg.rows import dict_row

from conftest import RELAY_KEY, SERVER_SECRET, RecordedCli, ask_question, events_of, model_turns, recording, start_handover, task_of


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
    from procsvc import work_rules
    cli = RecordedCli(recording('handover/draft-1')['runs'][0])
    start_handover(course.rt)
    worker('live', cli).poll_once()
    args = cli.requests[0].request.extra_args
    # 설정 출처를 끈 CLI(--setting-sources '')는 작업 폴더의 규칙 파일을 읽지 않는다 — 규칙은 인자로 간다
    assert args[args.index('--setting-sources') + 1] == ''
    assert args[args.index('--append-system-prompt') + 1] == work_rules.constitution(work_rules.rules_for('hyd-handover'))
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
    assert task_of(course.rt, first['proc_inst_id'], DRAFT)['draft_status'] == 'HUMAN_ASKED'
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


# ---------------------------------------------------------------- 키 없는 PC(재생)
def test_키_없는_PC의_교대_초안은_녹화를_재생해_제출하고_재생임을_알린다(course, worker, relay):
    inst = start_handover(course.rt)
    worker('replay').poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['status'] == 'SUBMITTED', friendly(course.rt, task['id'])
    notes = [e['data'].get('content') for e in events_of(course.rt, task['id'], 'task_working')]
    assert any(str(n).startswith('AI 응답 재생') for n in notes)
    assert relay.requests == [] and ledger_runs(course.dsn) == []        # 재생은 관문 · 중계를 부르지 않는다


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
    assert error['name'] == 'AI 응답 재생 범위 밖'
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
        assert '강의에서 다룬 질문' in after['message'] and 'RuntimeError' not in after['message']


def test_워커가_다시_켜지면_끊긴_재생_실행을_처음부터_다시_낸다(course, worker):
    """#10: 재생 중 워커가 죽으면(임대 만료 뒤 재점유) 다음 녹화 실행으로 넘어가지 않고 같은 실행을 다시 낸다."""
    inst = start_handover(course.rt)
    first = worker('replay')
    real = first.responses.claim

    def crashing(**kw):
        claim = real(**kw)
        inner = claim.__call__

        def died(provider, request, env, *, check_stop=None):
            gen = inner(provider, request, env, check_stop=check_stop)
            yield next(gen)                                  # 세션 id(replay:<열쇠>:0)가 작업에 저장된 뒤
            raise SystemExit('워커 프로세스가 죽었다')
        claim.__class__ = type('Dying', (type(claim),), {'__call__': lambda self, *a, **k: died(*a, **k)})
        return claim
    first.responses.claim = crashing
    with pytest.raises(SystemExit):
        first.poll_once()
    with psycopg.connect(course.dsn) as db:
        db.execute("UPDATE todolist SET lease_until=now()-interval '1 second' WHERE draft_status='STARTED'")
    worker('replay', consumer='restarted-worker').poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['status'] == 'SUBMITTED', friendly(course.rt, task['id'])
    assert task['output']['cliagents_session_id'].endswith(':0')


# ---------------------------------------------------------------- 강사 녹화(record): 성공 확정 뒤에만 남긴다
def test_녹화_모드에서_실패한_실행은_좋은_녹화를_덮지_않는다(course, worker, tmp_path, relay):
    """#11: 녹화는 점유가 저장된 결과로 끝난 뒤에만 쓴다."""
    import shutil
    replay_dir = tmp_path / 'replay'
    shutil.copytree(__import__('conftest').REPLAY_DIR, replay_dir)
    from worker import ai_replay
    key = ai_replay.course_key('handover/draft-1', '')
    before = (replay_dir / f'{key}.json.gz').read_bytes()
    relay.answer(503, {'error': {'message': 'overloaded'}})
    start_handover(course.rt)
    worker('record', RecordedCli(recording('handover/draft-1')['runs'][0]), replay_dir=replay_dir).poll_once()
    assert (replay_dir / f'{key}.json.gz').read_bytes() == before
    relay.reset()
    start_handover(course.rt)
    worker('record', RecordedCli(recording('handover/draft-1')['runs'][0]), replay_dir=replay_dir).poll_once()
    after = ai_replay.Library(replay_dir).load(key)
    assert after['slot'] == 'handover/draft-1' and len(after['runs']) == 1 and after['recorded_at'] != recording('handover/draft-1')['recorded_at']


# ---------------------------------------------------------------- 키 있는 PC의 같은 요청 저장
def recorded_question():
    from worker import ai_replay
    doc = next(d for _, d in ai_replay.Library(__import__('conftest').REPLAY_DIR).docs() if d.get('slot') == 'question')
    return doc, doc['case'][len(ai_replay.QUESTION_PREFIX):]


def test_같은_설정_같은_입력의_질문은_앞선_결과를_다시_쓰고_모델을_부르지_않는다(course, worker, relay):
    from procsvc import ask
    doc, question = recorded_question()
    first = ask_question(course.rt, question)
    w = worker('live', RecordedCli(doc['runs'][0]))
    w.poll_once()
    _complete(course.rt, first['id'])
    calls = len(relay.requests)
    second = ask_question(course.rt, question + ' ')
    worker('live', RecordedCli(doc['runs'][0])).poll_once()
    task = task_of(course.rt, second['id'])
    notes = [str(e['data'].get('content')) for e in events_of(course.rt, task['id'], 'task_working')]
    assert len(relay.requests) == calls                              # AI 호출 0
    assert any(n.startswith('같은 설정 · 같은 입력의 앞선 실행 결과를 다시 썼습니다(새로 추론하지 않음') for n in notes)
    assert ask.view(course.rt, second['id'])['state'] in ('submitted', 'done')


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
    monkeypatch.setattr(course.ledger, 'policy', dict(course.ledger.policy, run=dict(course.ledger.policy['run'], seconds=1)))
    inst = start_handover(course.rt)
    worker('live', RecordedCli(recording('handover/draft-1')['runs'][0], calls=0)).poll_once()
    task = task_of(course.rt, inst['proc_inst_id'], DRAFT)
    assert task['draft_status'] == 'FAILED'
    assert friendly(course.rt, task['id'])['friendly'].startswith('AI 단계가 한 번 실행 시간(1초)을 넘어 멈췄습니다')
