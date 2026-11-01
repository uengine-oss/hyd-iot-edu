"""AI 응답 저장 · 다시 쓰기(worker/ai_replay.py) — 저장소 녹화 6개를 실제 재생기로 이 처리 건의 값에 맞춰 낸다. 도구 서버는 이 PC 의 실제 서버(tool_servers).

열쇠는 서버가 준 수업 AI 자리(course_policy) · 처리 건 종류 · 실행 차례다. 녹화 밖 행동은 학생이 알아듣는 말로 멈춘다.
"""
import gzip
import json
import re
import uuid
from pathlib import Path

import pytest
from cliagents import ExecEvent, ExecEventKind, ExecRequest

from conftest import rejected_first_replay, REPLAY_DIR
from procsvc import course_policy
from worker import ai_replay
from worker.ai_replay import COURSE, REUSE, Library, NotRecorded, Responses

COURSE_LIB = Library(REPLAY_DIR, COURSE)
FORBIDDEN = re.compile(r'API 키|COOLER_DEGRADATION|PM_DUE|SPARE_BELOW_MIN|시스템 오류|Error|Exception|AI_MODE|녹화를 다시 저장')


def docs():
    return {doc['slot'] + '|' + doc['case']: doc for _, doc in COURSE_LIB.docs()}


def workdir_for(tmp_path, run, servers, *, inputs=None):
    """이 PC의 새 처리 건: 녹화 때와 다른 작업 · 처리 건 · 점유 id, 입력은 녹화와 같거나(inputs 없음) 바꾼 것."""
    ctx = run['context']
    wd = tmp_path / uuid.uuid4().hex
    (wd / 'context').mkdir(parents=True)
    todo, inst = str(uuid.uuid4()), ctx['proc_inst_id'].split('.')[0] + '.' + str(uuid.uuid4())
    scope = dict(ctx['process_scope'], instance=inst, workitem=todo, consumer='agent-worker:test:' + uuid.uuid4().hex)
    task = {'id': todo, 'proc_inst_id': inst, 'process_scope': scope,
            'query': '지시\n[InputData] ' + json.dumps(ctx['inputs'] if inputs is None else inputs, ensure_ascii=False)}
    (wd / 'context' / 'task.json').write_text(json.dumps(task, ensure_ascii=False), encoding='utf8')
    (wd / '.mcp.json').write_text(json.dumps({'mcpServers': {n: {'type': 'http', 'url': u} for n, u in servers.items()}}), encoding='utf8')
    return wd, task


def claim(mode='replay', *, slot, case='', attempt=(0, 0), cache=None, accepted=lambda source: True, step='단계', cli=None, course=COURSE_LIB):
    return Responses(mode, course=course, cache=cache).claim(cli=cli, slot=slot, case=case, attempt=attempt, request_key='k' * 32,
                                                                 step=step, provider='claude-code', source={'todo_id': 't', 'generation': 0},
                                                                 accepted=accepted)


def play(c, wd, resume=None):
    return list(c(None, ExecRequest(prompt='', workdir=str(wd), resume_session=resume, extra_args=[]), {}))


def created_ids(run):
    """녹화 때 쓰기 도구(판단 · 발주 등록)가 만든 문서 id."""
    out = []
    for e in run['events']:
        if e['kind'] == 'tool_end' and (e.get('tool') or '').endswith(('submit_decision', 'submit_purchase')):
            body = ai_replay._as_json((run.get('tool_outputs_full') or {}).get(e.get('tool_use_id')) or e.get('tool_output'))
            out.append((ai_replay._created(body) or {}).get('id'))
    return [i for i in out if i]


# ---------------------------------------------------------------- 수업 자리별 재생
@pytest.mark.parametrize('slot', ['handover/draft-1', 'handover/draft-2', 'question'])
def test_읽기_자리는_녹화를_이_처리_건의_값으로_다시_낸다(tmp_path, tool_servers, slot):
    doc = next(d for key, d in docs().items() if key.startswith(slot + '|'))
    run = doc['runs'][0]
    wd, task = workdir_for(tmp_path, run, tool_servers)
    events = play(claim(slot=slot, case=doc['case'], step=doc['step']), wd)
    shown = json.dumps([ev.text for ev in events] + [ev.tool_output for ev in events] + [ev.tool_input for ev in events], ensure_ascii=False, default=str)
    result = (wd / 'output' / 'result.json').read_text(encoding='utf8') if run.get('result_file') else ''
    kept = [e for e in run['events'] if not ai_replay.partial_chunk(e)]
    assert len(events) == len(kept) + (0 if any(e['kind'] == 'run_start' for e in kept) else 1)
    assert events[0].session_id == f'{COURSE}{ai_replay.course_key(slot, doc["case"])}:0'
    old = run['context']
    assert old['proc_inst_id'] not in shown + result and old['id'] not in shown + result      # 녹화 때 처리 건 · 작업 id 는 지금 값으로


def _scenario(key):
    def start(world):
        status, out = world.api('POST', f'/api/scenario/{key}/start', {'by': 'user:kim-op', 'role': 'role:operator'}, source_loop=True)
        assert status == 200, out
        return out['instance'], world.agent(out['instance'], 'T_agent')
    return start


@pytest.mark.parametrize('slot, start', [
    ('c3_cooling/T_agent', lambda world: world.start_cooling()[1:]),
    ('c3_pm/T_agent', _scenario('B')),
    ('c3_spare/T_agent', _scenario('C')),
], ids=['냉각 경보', '정기 점검', '재고 보충'])
def test_쓰기_자리는_녹화의_쓰기_도구를_이_PC_서버로_다시_불러_이_처리_건에_새_판단을_등록한다(world, slot, start):
    """G5b(FX): 쓰기 도구 서버를 가짜 기록기로 보던 확인을 실제 처리 건 · 실제 dmn-mcp · 처리 엔진 판단 장부로."""
    pid, did = start(world)                                                                  # 키 없는 PC: 강사 녹화 재생
    doc = next(d for key, d in docs().items() if key.startswith(slot + '|'))
    assert did and did not in created_ids(doc['runs'][0])                                  # 녹화 때의 id 가 아니라 새로 등록한 판단
    scope = world.main.book[did]['origin']['process_scope']
    assert scope['instance'] == pid and scope['workitem'] == world.row(pid, 'T_agent')['id']


@pytest.mark.parametrize('skills, said', [(['cooler-check'], True), ([], False)], ids=['스킬 붙임', '스킬 없음'])
def test_스킬을_붙여도_재생한_답에는_반영되지_않았다고_말한다(tmp_path, tool_servers, skills, said):
    """실라버스 포털 실습 3번(스킬을 붙이고 같은 질문 → 떼고 같은 질문): 키 없는 PC 에서는 같은 녹화가 나와 「스킬이 아무 일도 안 한다」로
    배우지 않게, 처리 과정 한 줄에 붙인 스킬이 이 답에 반영되지 않았음을 적는다."""
    doc = next(d for key, d in docs().items() if key.startswith('question|'))
    wd, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers)
    c = Responses('replay', course=COURSE_LIB).claim(cli=None, slot='question', case=doc['case'], attempt=(0, 0), request_key=None,
                                                    step=doc['step'], provider='claude-code', source={}, accepted=lambda s: True, skills=skills)
    play(c, wd)
    text = c.notice()
    assert text.startswith('AI 응답 재생 — 강사가 미리 실행해 둔 응답이며')
    assert ('cooler-check' in text and '반영되지 않았습니다' in text) is said
    # 한바퀴 무키 최종: 재생한 교대 인계안의 작업지시 번호가 녹화 때 것이라 이 PC 의 열린 작업지시와 달랐다 — 학생이 제 PC 것으로 읽지 않게 말한다
    assert '강사 PC에서 저장할 때의 것' in text and '이 PC의 업무 데이터와 다를 수 있습니다' in text


def test_녹화_열쇠는_흐름_id_와_작업_이름이_아니라_수업_자리다():
    """B-02: 학생이 가져온 교대 흐름(ShiftHandover)과 제공 흐름(shift_handover)의 첫 초안 자리는 같은 녹화를 쓴다."""
    slots = {course_policy.AI_SLOTS[(d, a)] for d, a in (('ShiftHandover', 'task_draft'), ('shift_handover', 'task:draft'))}
    assert slots == {'handover/draft-1'}
    assert COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))['step'] == '인계안 작성'


# ---------------------------------------------------------------- 녹화 밖 행동 = 쉬운 말 실패
@pytest.mark.parametrize('slot, case, attempt, has', [
    ('handover/draft-3', '', (0, 0), '보완 요청 1번까지'),
    ('c3_cooling/T_agent', 'COOLER_DEGRADATION', (1, 0), '재작업'),
    ('c3_cooling/T_agent', 'COOLER_DEGRADATION', (0, 1), '다시 평가'),
    ('c3_cooling/T_agent', 'PUMP_LEAK', (0, 0), '이 종류의 처리 건'),
    (None, '', (0, 0), '수업 AI 단계가 아니라'),
    ('question', ai_replay.question_case('다른 질문'), (0, 0), '강의에서 다룬 질문에만'),
], ids=['교대 보완 2', '재작업 세대 1', '보류 뒤 재평가', '녹화 없는 경보 종류', 'PBL 단계의 수업 밖 단계', '다루지 않은 질문'])
def test_녹화에_없는_행동은_무엇이_없고_무엇을_하면_되는지_말하고_멈춘다(tmp_path, slot, case, attempt, has):
    """#9 · #23: 「API 키를 넣으면」(키 없는 학생이 할 수 없는 안내) · 경보 코드 · 「시스템 오류」 없이."""
    with pytest.raises(NotRecorded) as caught:
        play(claim(slot=slot, case=case, attempt=attempt, step='인계안 작성 · 보완 2'), tmp_path)
    assert has in str(caught.value)
    assert not FORBIDDEN.search(str(caught.value))


def test_녹화와_다른_설비의_처리_건은_바꿔_끼우지_않고_멈춘다(tmp_path, tool_servers):
    """B-04: 녹화의 HYD-01 실측을 HYD-02 의 사실처럼 보이지 않는다."""
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    inputs = dict(doc['runs'][0]['context']['inputs'], asset='HYD-02')
    wd, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers, inputs=inputs)
    with pytest.raises(NotRecorded) as caught:
        play(claim(slot='handover/draft-1', step=doc['step']), wd)
    assert '설비 HYD-01' in str(caught.value) and 'HYD-02' in str(caught.value)


@pytest.mark.parametrize('change', [
    {'as_of': '2026-11-02T09:00:00+00:00', 'work_notes': '다른 메모'},
    {'work_notes': '재확인'},
    {'shift_label': 'B조'},
], ids=['시각 · 메모', '공백 없는 짧은 글', '교대 이름'])
def test_처리_건마다_새로_생기는_입력_값은_지금_값으로_바꿔_낸다(tmp_path, tool_servers, change):
    """G1-03: 공백 없는 짧은 값(보완 요청 「재확인」 · 누른 사람)을 「데이터를 고르는 값」으로 보아 멈췄다 — 고르는 값은 FIELD_NAMES 한 곳뿐."""
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    run = doc['runs'][0]
    inputs = dict(run['context']['inputs'], **change)
    wd, _ = workdir_for(tmp_path, run, tool_servers, inputs=inputs)
    events = play(claim(slot='handover/draft-1', step=doc['step']), wd)
    shown = json.dumps([ev.tool_input for ev in events] + [ev.text for ev in events], ensure_ascii=False, default=str)
    result = (wd / 'output' / 'result.json').read_text(encoding='utf8')
    assert events and result
    if 'as_of' in change:
        assert run['context']['inputs']['as_of'] not in shown + result


def test_녹화가_쓴_도구_서버가_지금_단계에_없으면_녹화_결과를_그대로_내지_않고_멈춘다(tmp_path, tool_servers):
    """W-01: 쓰기 도구 서버(hyd-dmn)를 에이전트에서 빼면 옛 판단 id 가 든 녹화 결과가 그대로 나갔다."""
    doc = COURSE_LIB.load(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'))
    servers = {k: v for k, v in tool_servers.items() if k != 'hyd-dmn'}
    wd, _ = workdir_for(tmp_path, doc['runs'][0], servers)
    with pytest.raises(NotRecorded) as caught:
        play(claim(slot='c3_cooling/T_agent', case='COOLER_DEGRADATION', step=doc['step']), wd)
    assert 'hyd-dmn' in str(caught.value)
    assert not (wd / 'output' / 'result.json').exists()


# ---------------------------------------------------------------- 이어 하기 · 재시작
@pytest.mark.parametrize('session, reclaimed, expected', [
    ('replay:abc:0', True, None), ('replay:abc:1', True, 'replay:abc:0'), ('reuse:abc:2', True, 'reuse:abc:1'),
    ('replay:abc:0', False, 'replay:abc:0'), ('7d773cd2-2d2d-4d80-8de1-b7e4b106a368', True, '7d773cd2-2d2d-4d80-8de1-b7e4b106a368'),
    (None, True, None),
], ids=['재생 첫 실행 중 재시작', '재생 이어 하기 중 재시작', '다시 쓰기 중 재시작', '정상 이어 하기', '실제 CLI 세션', '세션 없음'])
def test_워커가_다시_켜져_재점유하면_끊긴_재생_실행을_처음부터_다시_낸다(session, reclaimed, expected):
    """#10: 다시 잡은 점유는 앞 실행이 끝나지 않았다 — 녹화의 다음 실행으로 넘어가지 않는다."""
    assert ai_replay.resume_after(session, reclaimed=reclaimed) == expected


def test_처리_흐름이_돌려보낸_교대_초안은_녹화의_다음_실행으로_이어_낸다(tmp_path, tool_servers):
    lib = Library(rejected_first_replay(tmp_path), COURSE)        # 거절될 첫 실행 → 고친 둘째 실행(시험이 만든 녹화 — conftest)
    doc = lib.load(ai_replay.course_key('handover/draft-1', ''))
    wd, _ = workdir_for(tmp_path, doc['runs'][1], tool_servers)
    key = ai_replay.course_key('handover/draft-1', '')
    events = play(claim(slot='handover/draft-1', step=doc['step'], course=lib), wd, resume=f'{COURSE}{key}:0')
    assert events[0].session_id == f'{COURSE}{key}:1'


@pytest.mark.parametrize('event, chunk', [
    ({'kind': 'unknown', 'raw': {'type': 'stream_event', 'event': {'type': 'content_block_delta'}}}, True),
    ({'kind': 'unknown', 'raw': {'type': 'stream_event', 'event': {'type': 'message_start'}}}, False),
    ({'kind': 'unknown', 'raw': {'type': 'system'}}, False),
    ({'kind': 'tool_end', 'raw': {'type': 'stream_event', 'event': {'type': 'content_block_delta'}}}, False),
], ids=['부분 응답 조각', '모델 호출 경계', '다른 모르는 이벤트', '완성된 이벤트'])
def test_녹화_추적에서_빼는_것은_부분_응답_조각뿐이다(event, chunk):
    """G1-08: 녹화 · 실행 추적의 95 %가 화면 어디에도 쓰이지 않는 토큰 조각이었다. 모델 호출 경계는 남긴다(호출 수를 센다)."""
    assert ai_replay.partial_chunk(event) is chunk


def test_재점유한_재생은_끊기기_전에_부른_쓰기_도구를_다시_부르지_않고_그때_결과를_쓴다(tmp_path, tool_servers):
    """G1-11: 처음부터 다시 낸 재생이 판단 등록을 또 불러 process 가 409(한 작업 · 세대에 판단 하나)로 거절해 단계가 실패했다.
    여기의 처리 건은 이 PC 처리 엔진에 없어 다시 부르면 거절된다 — 이어 받은 결과를 쓰면 끝까지 낸다."""
    key = ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION')
    doc = COURSE_LIB.load(key)
    run = doc['runs'][0]
    wd, _ = workdir_for(tmp_path, run, tool_servers)
    write = next(e for e in run['events'] if e['kind'] == 'tool_start' and (e.get('tool') or '').endswith('submit_decision'))
    recorded = (run.get('tool_outputs_full') or {}).get(write['tool_use_id']) or next(
        e['tool_output'] for e in run['events'] if e['kind'] == 'tool_end' and e.get('tool_use_id') == write['tool_use_id'])
    text = recorded if isinstance(recorded, str) else json.dumps(recorded, ensure_ascii=False)
    (wd / ai_replay.SWAPS_FILE).write_text(json.dumps({'exact': {}, 'results': {write['tool_use_id']: text}}, ensure_ascii=False), encoding='utf8')
    request = ExecRequest(prompt='', workdir=str(wd), resume_session=None, extra_args=[])
    events = list(ai_replay.play(COURSE_LIB, key, doc, 0, request, None, {}, reclaimed=True))
    assert events and (wd / 'output' / 'result.json').exists()


@pytest.mark.parametrize('mode, session, expected', [
    ('replay', 'replay:k:0', 'replay:k:0'), ('replay', 'reuse:k:0', None), ('replay', 'a-real-cli-session', None),
    ('live', 'replay:k:0', None), ('live', 'a-real-cli-session', 'a-real-cli-session'),
])
def test_모드에서_이어_받을_수_없는_세션이면_이어_하기_없이_새로_시작한다(mode, session, expected):
    """키 없는 PC는 실제 CLI 세션을 이어 받을 수 없고(모델을 부르지 않는다), 키 있는 PC는 녹화 세션을 이어 받을 수 없다."""
    assert claim(mode, slot='question').resumable(session) == expected


# ---------------------------------------------------------------- 같은 요청 저장(키 있는 PC)
def test_같은_설정_같은_입력이면_앞선_실행을_다시_쓰고_실제_CLI_를_부르지_않는다(tmp_path, tool_servers):
    """키 있는 PC: 같은 설정 · 같은 입력이면 앞선 실행을 다시 쓴다(새로 추론하지 않음). 읽기 자리로 — 쓰기 도구의 실제 재등록은 위 처리 건 시험이 본다."""
    draft = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    cache = Library(tmp_path / 'cache', REUSE)
    cache.write('k' * 32, {'request': 'k' * 32, 'step': draft['step'], 'case': '', 'provider': 'claude-code',
                           'source': {'todo_id': 't', 'generation': 0}, 'runs': draft['runs']}, [])
    wd, _ = workdir_for(tmp_path, draft['runs'][0], tool_servers)
    c = claim('live', slot='handover/draft-1', cache=cache, cli=lambda *a, **k: pytest.fail('실제 CLI 를 불렀다'))
    events = play(c, wd)
    assert events[0].session_id.startswith(REUSE)
    assert c.notice().startswith('같은 설정 · 같은 입력의 앞선 실행 결과를 다시 썼습니다(새로 추론하지 않음')


def _cached(tmp_path, slot):
    cache = Library(tmp_path / 'cache', REUSE)
    doc = COURSE_LIB.load(next(k for k, d in COURSE_LIB.docs() if d['slot'] == slot))
    cache.write('k' * 32, dict(doc, request='k' * 32, source={'todo_id': 't', 'generation': 0}), [])
    return cache


LIVE_SESSION = 'live-session-now'


def _real_cli():
    """키 있는 PC 의 CLI 자리 — 지금 실행의 세션 id 로 결과 하나."""
    def cli(provider, request, env, check_stop=None):
        yield ExecEvent(kind=ExecEventKind.RESULT, text='{}', session_id=LIVE_SESSION)
    return cli


def test_저장한_실행이_처리_흐름에서_받아들여지지_않았으면_버리고_실제_AI로_실행한다(tmp_path):
    cache = _cached(tmp_path, 'handover/draft-1')
    out = play(claim('live', slot='handover/draft-1', cache=cache, accepted=lambda source: False, cli=_real_cli()), tmp_path)
    assert [e.session_id for e in out if e.kind == ExecEventKind.RESULT] == [LIVE_SESSION]     # 결과는 실제 AI 의 것(저장 실행의 세션 아님)
    assert not cache.file_of('k' * 32).exists()


def test_질문은_같은_요청_저장을_읽지도_쓰지도_않고_지금_상태로_답한다(tmp_path):
    """G1-09: 세계 상태(지식 적재 · 업무 값)가 열쇠에 없어 같은 질문에 옛 답을 냈다 — 질문 자리는 저장 대상이 아니다."""
    cache = _cached(tmp_path, 'question')
    c = claim('live', slot='question', cache=cache, cli=_real_cli())
    out = play(c, tmp_path)
    c.keep('submitted', [])
    assert [e.session_id for e in out if e.kind == ExecEventKind.RESULT] == [LIVE_SESSION]      # 저장 답이 아니라 지금 실행의 답
    assert cache.file_of('k' * 32).exists() and len(cache.docs()) == 1


@pytest.mark.parametrize('mode, outcome, kept', [
    ('record', 'submitted', True), ('record', 'asked', True), ('record', 'deferred', False), ('record', 'failed', False),
    ('live', 'submitted', True), ('live', 'asked', False), ('live', 'deferred', False), ('live', 'failed', False),
], ids=['녹화 · 제출', '녹화 · 사람 질문', '녹화 · 보류', '녹화 · 실패', '저장 · 제출', '저장 · 사람 질문', '저장 · 보류', '저장 · 실패'])
def test_녹화와_같은_요청_저장은_정한_끝으로_끝난_점유만_남긴다(tmp_path, mode, outcome, kept):
    """#11 · G1-22: 보류로 끝난 실행도 수업 녹화를 덮었다. 녹화 = 제출 · 사람 질문(그 뒤 이어지는 실행과 한 녹화), 같은 요청 저장 = 제출만."""
    cache, course_dir = Library(tmp_path / 'cache', REUSE), Library(tmp_path / 'course', COURSE)
    c = Responses(mode, course=course_dir, cache=cache).claim(
        cli=lambda *a, **k: iter([ExecEvent(kind=ExecEventKind.RESULT, text='{}', session_id='s1')]), slot='handover/draft-1', case='',
        attempt=(0, 0), request_key='k' * 32, step='인계안 작성', provider='claude-code', source={}, accepted=lambda s: True)
    play(c, tmp_path)
    c.keep(outcome, [])
    assert len((course_dir if mode == 'record' else cache).docs()) == (1 if kept else 0)
    assert (cache if mode == 'record' else course_dir).docs() == []


def test_저장할_때_이번_실행의_비밀값을_가린다(tmp_path):
    """#18: 저장 직전 가림 한 곳(diagnostics.hide) — 값 그대로 · JSON 안의 꼴 · 「Bearer <토큰>」의 토큰 조각."""
    from procsvc.mcp_secrets import REDACTED
    secret = 'Bearer abc"def\\ghi-0123456789'
    library = Library(tmp_path, COURSE)
    library.write('x', {'slot': 'question', 'case': '', 'step': '', 'runs': [{'events': [{'text': f'토큰 {secret}'},
                    {'text': json.dumps({'h': secret})}, {'text': 'abc"def\\ghi-0123456789'}]}]}, [secret])
    raw = gzip.decompress(library.file_of('x').read_bytes()).decode('utf8')
    assert 'ghi-0123456789' not in raw and raw.count(REDACTED) == 3


# ---------------------------------------------------------------- 모드 · 목록
@pytest.mark.parametrize('mode', ['auto', 'LIVE', ''])
def test_세_모드_밖의_AI_모드로는_켜지지_않는다(mode):
    """B-06: 키 · 로그인을 추측하던 자동 모드는 수업 구성에서 쓰지 않아 지웠다 — 모드는 live · record · replay 셋이고 그 밖은 켜지지 않는다."""
    with pytest.raises(ValueError):
        Responses(mode, course=COURSE_LIB)


SLOTS = [{'slot': s, 'recorded': s not in course_policy.UNRECORDED_SLOTS} for s in sorted(set(course_policy.AI_SLOTS.values()))]


@pytest.mark.parametrize('slots, missing, unrecorded', [
    (SLOTS, [], ['handover/draft-3']),
    (SLOTS + [{'slot': 'c3_new/T_agent', 'recorded': True}], ['c3_new/T_agent'], ['handover/draft-3']),
    ([x for x in SLOTS if x['slot'] != 'question'], [], ['handover/draft-3']),
], ids=['지금 수업', '녹화할 자리 하나 빠짐', '수업 자리가 아닌 녹화'])
def test_녹화_목록은_녹화할_자리와_녹화하지_않기로_한_자리를_가른다(slots, missing, unrecorded):
    """G5b-09 · P2-04: 교대 보완 2(녹화 없이 멈추기로 정한 자리)를 「녹화 없음」 실패로 세어 목록 도구가 늘 1로 끝났다."""
    rows, got_missing, got_unrecorded = ai_replay.listing(COURSE_LIB, slots)
    assert (got_missing, got_unrecorded) == (missing, unrecorded)
    assert {r['slot'] for r in rows if not r['course']} == {x['slot'] for x in SLOTS} - {x['slot'] for x in slots}


def test_목록_도구는_수업_자리를_process_에서_읽고_저장소_녹화로_빠진_자리가_없다(world):
    """P2-04: 워커 이미지에는 정의 폴더가 없어 규칙 모듈을 가져오던 목록 도구가 죽었다 — 자리는 process 의 GET /api/course-access 가 준다."""
    slots = ai_replay.course_slots(world.url)
    assert {x['slot'] for x in slots} == set(course_policy.AI_SLOTS.values())
    rows, missing, unrecorded = ai_replay.listing(COURSE_LIB, slots)
    assert missing == [] and unrecorded == sorted(course_policy.UNRECORDED_SLOTS) and all(r['course'] for r in rows)


def test_수업_자리를_읽지_못하면_목록_도구는_어디를_못_읽었는지_말하고_실패한다():
    with pytest.raises(RuntimeError) as e:
        ai_replay.course_slots('http://127.0.0.1:9')
    assert '수업 AI 자리를 process(' in str(e.value) and '스택이 켜져 있는지' in str(e.value)


def test_저장소_녹화는_모두_지금_형식과_열쇠_규칙의_파일_이름이다():
    for path in sorted(Path(REPLAY_DIR).glob('*.json.gz')):
        doc = json.loads(gzip.decompress(path.read_bytes()))
        assert doc['format'] == ai_replay.FORMAT
        assert path.name == ai_replay.course_key(doc['slot'], doc['case']) + '.json.gz'


@pytest.mark.parametrize('todo_exists, age_h, kept', [
    (True, 1, True),            # 작업이 있고 최근에 쓰임
    (False, 1, False),          # 작업 행이 없어짐(처리 건 지움 · 초기화)
    (True, 73, False),          # 작업은 남았지만 보존 기간(72 h) 동안 다시 쓰이지 않음 — 같은 요청이 오지 않는 c3 처리 건
    (True, 71, True),           # 보존 기간 안
], ids=['최근 · 작업 있음', '작업 없음', '보존 기간 넘음', '보존 기간 안'])
def test_같은_요청_저장은_작업이_없어지거나_보존_기간_동안_쓰이지_않으면_정리가_지운다(tmp_path, todo_exists, age_h, kept):
    """G1-09: 작업 행이 지워질 때만 지워 끝난 처리 건의 저장이 끝없이 쌓였다."""
    import os
    import time
    cache = _cached(tmp_path, 'handover/draft-1')
    now = time.time()
    os.utime(cache.file_of('k' * 32), (now - age_h * 3600, now - age_h * 3600))
    removed = ai_replay.sweep_cache(cache, lambda todo: todo_exists and todo == 't', 72 * 3600, now=now)
    assert cache.file_of('k' * 32).exists() is kept and removed == ([] if kept else ['k' * 32])


def test_다시_쓴_같은_요청_저장은_보존_기간을_그때부터_다시_센다(tmp_path, tool_servers):
    import os
    import time
    cache = _cached(tmp_path, 'handover/draft-1')
    old = time.time() - 73 * 3600
    os.utime(cache.file_of('k' * 32), (old, old))
    wd, _ = workdir_for(tmp_path, cache.load('k' * 32)['runs'][0], tool_servers)
    out = play(claim('live', slot='handover/draft-1', cache=cache, cli=_real_cli()), wd)         # 끝난 작업의 같은 요청 → 저장을 다시 낸다
    assert LIVE_SESSION not in [e.session_id for e in out if e.kind == ExecEventKind.RESULT]     # 실제 AI 가 아니라 저장을 냈다
    assert ai_replay.sweep_cache(cache, lambda todo: True, 72 * 3600) == [] and cache.file_of('k' * 32).exists()
