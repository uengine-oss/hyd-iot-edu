"""AI 응답 저장 · 다시 쓰기(worker/ai_replay.py) — 저장소 녹화 6개를 실제 재생기로 이 처리 건의 값에 맞춰 낸다. 업무 도구 서버만 대체(mcp_servers).

열쇠는 서버가 준 수업 AI 자리(course_policy) · 처리 건 종류 · 실행 차례다. 녹화 밖 행동은 학생이 알아듣는 말로 멈춘다.
"""
import gzip
import json
import re
import uuid
from pathlib import Path

import pytest
from cliagents import ExecEvent, ExecEventKind, ExecRequest

from conftest import REPLAY_DIR
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


def claim(mode='replay', *, slot, case='', attempt=(0, 0), cache=None, accepted=lambda source: True, step='단계', cli=None):
    return Responses(mode, course=COURSE_LIB, cache=cache).claim(cli=cli, slot=slot, case=case, attempt=attempt, request_key='k' * 32,
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
@pytest.mark.parametrize('slot', ['c3_cooling/T_agent', 'c3_pm/T_agent', 'c3_spare/T_agent', 'handover/draft-1', 'handover/draft-2', 'question'])
def test_수업_자리마다_녹화를_이_처리_건의_값으로_다시_낸다(tmp_path, mcp_servers, slot):
    doc = next(d for key, d in docs().items() if key.startswith(slot + '|'))
    run = doc['runs'][0]
    wd, task = workdir_for(tmp_path, run, mcp_servers['urls'])
    events = play(claim(slot=slot, case=doc['case'], step=doc['step']), wd)
    shown = json.dumps([ev.text for ev in events] + [ev.tool_output for ev in events] + [ev.tool_input for ev in events], ensure_ascii=False, default=str)
    result = (wd / 'output' / 'result.json').read_text(encoding='utf8') if run.get('result_file') else ''
    assert len(events) == len(run['events']) + 1
    assert events[0].session_id == f'{COURSE}{ai_replay.course_key(slot, doc["case"])}:0'
    old = run['context']
    assert old['proc_inst_id'] not in shown + result and old['id'] not in shown + result      # 녹화 때 처리 건 · 작업 id 는 지금 값으로
    for made in created_ids(run):                                                           # 쓰기 도구는 이 PC 서버로 다시 불러 새 id
        assert made not in shown + result
    if created_ids(run):
        server_calls = mcp_servers['calls']['hyd-dmn']
        assert server_calls and server_calls[-1][1]['process_scope']['workitem'] == task['id']


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


def test_녹화와_다른_설비의_처리_건은_바꿔_끼우지_않고_멈춘다(tmp_path, mcp_servers):
    """B-04: 녹화의 HYD-01 실측을 HYD-02 의 사실처럼 보이지 않는다."""
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    inputs = dict(doc['runs'][0]['context']['inputs'], asset='HYD-02')
    wd, _ = workdir_for(tmp_path, doc['runs'][0], mcp_servers['urls'], inputs=inputs)
    with pytest.raises(NotRecorded) as caught:
        play(claim(slot='handover/draft-1', step=doc['step']), wd)
    assert '설비 HYD-01' in str(caught.value) and 'HYD-02' in str(caught.value)


def test_처리_건마다_새로_생기는_입력_값은_지금_값으로_바꿔_낸다(tmp_path, mcp_servers):
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    run = doc['runs'][0]
    inputs = dict(run['context']['inputs'], as_of='2026-11-02T09:00:00+00:00', work_notes='다른 메모')
    wd, _ = workdir_for(tmp_path, run, mcp_servers['urls'], inputs=inputs)
    events = play(claim(slot='handover/draft-1', step=doc['step']), wd)
    shown = json.dumps([ev.tool_input for ev in events] + [ev.text for ev in events], ensure_ascii=False, default=str)
    assert run['context']['inputs']['as_of'] not in shown + (wd / 'output' / 'result.json').read_text(encoding='utf8')


def test_녹화가_쓴_도구_서버가_지금_단계에_없으면_녹화_결과를_그대로_내지_않고_멈춘다(tmp_path, mcp_servers):
    """W-01: 쓰기 도구 서버(hyd-dmn)를 에이전트에서 빼면 옛 판단 id 가 든 녹화 결과가 그대로 나갔다."""
    doc = COURSE_LIB.load(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'))
    servers = {k: v for k, v in mcp_servers['urls'].items() if k != 'hyd-dmn'}
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


def test_처리_흐름이_돌려보낸_교대_초안은_녹화의_다음_실행으로_이어_낸다(tmp_path, mcp_servers):
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    wd, _ = workdir_for(tmp_path, doc['runs'][1], mcp_servers['urls'])
    key = ai_replay.course_key('handover/draft-1', '')
    events = play(claim(slot='handover/draft-1', step=doc['step']), wd, resume=f'{COURSE}{key}:0')
    assert events[0].session_id == f'{COURSE}{key}:1'


@pytest.mark.parametrize('mode, session, expected', [
    ('replay', 'replay:k:0', 'replay:k:0'), ('replay', 'reuse:k:0', None), ('replay', 'a-real-cli-session', None),
    ('live', 'replay:k:0', None), ('live', 'a-real-cli-session', 'a-real-cli-session'),
])
def test_모드에서_이어_받을_수_없는_세션이면_이어_하기_없이_새로_시작한다(mode, session, expected):
    """키 없는 PC는 실제 CLI 세션을 이어 받을 수 없고(모델을 부르지 않는다), 키 있는 PC는 녹화 세션을 이어 받을 수 없다."""
    assert claim(mode, slot='question').resumable(session) == expected


# ---------------------------------------------------------------- 같은 요청 저장(키 있는 PC)
def test_쓰기_단계의_같은_요청도_다시_쓰되_쓰기_도구는_이_PC에서_다시_불러_새_id를_쓴다(tmp_path, mcp_servers):
    cooling = COURSE_LIB.load(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'))
    cache = Library(tmp_path / 'cache', REUSE)
    cache.write('k' * 32, {'request': 'k' * 32, 'step': cooling['step'], 'case': '', 'provider': 'claude-code',
                           'source': {'todo_id': 't', 'generation': 0}, 'runs': cooling['runs']}, [])
    wd, task = workdir_for(tmp_path, cooling['runs'][0], mcp_servers['urls'])
    c = claim('live', slot='c3_cooling/T_agent', cache=cache, cli=lambda *a, **k: pytest.fail('실제 CLI 를 불렀다'))
    events = play(c, wd)
    result = (wd / 'output' / 'result.json').read_text(encoding='utf8')
    assert events[0].session_id.startswith(REUSE)
    assert c.notice().startswith('같은 설정 · 같은 입력의 앞선 실행 결과를 다시 썼습니다(새로 추론하지 않음')
    assert created_ids(cooling['runs'][0])[0] not in result
    assert mcp_servers['calls']['hyd-dmn'][-1][1]['process_scope']['workitem'] == task['id']


def test_저장한_실행이_처리_흐름에서_받아들여지지_않았으면_버리고_실제_AI로_실행한다(tmp_path):
    cache = Library(tmp_path / 'cache', REUSE)
    question = COURSE_LIB.load(next(k for k, d in COURSE_LIB.docs() if d['slot'] == 'question'))
    cache.write('k' * 32, dict(question, request='k' * 32, source={'todo_id': 't', 'generation': 0}), [])
    ran = []

    def cli(provider, request, env, check_stop=None):
        ran.append(request)
        yield ExecEvent(kind=ExecEventKind.RESULT, text='{}', session_id='s1')
    c = claim('live', slot='question', cache=cache, accepted=lambda source: False, cli=cli)
    play(c, tmp_path)
    assert ran and not cache.file_of('k' * 32).exists()


def test_실패로_끝난_점유는_아무것도_남기지_않는다(tmp_path):
    """#11: 녹화 · 같은 요청 저장은 점유가 저장된 결과로 끝났을 때만 쓴다."""
    for mode in ('record', 'live'):
        cache, course_dir = Library(tmp_path / f'cache-{mode}', REUSE), Library(tmp_path / f'course-{mode}', COURSE)
        c = Responses(mode, course=course_dir, cache=cache).claim(
            cli=lambda *a, **k: iter([ExecEvent(kind=ExecEventKind.RESULT, text='{}', session_id='s1')]), slot='handover/draft-1', case='',
            attempt=(0, 0), request_key='k' * 32, step='인계안 작성', provider='claude-code', source={}, accepted=lambda s: True)
        play(c, tmp_path)
        c.keep('failed', [])
        assert course_dir.docs() == [] and cache.docs() == []
        c.keep('submitted', [])
        assert len((course_dir if mode == 'record' else cache).docs()) == 1


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


def test_녹화_목록은_수업_AI_자리마다_있는지_대조하고_빠진_자리가_있으면_실패로_끝난다(capsys):
    rows, missing = ai_replay.listing(COURSE_LIB)
    assert missing == sorted(set(course_policy.AI_SLOTS.values()) - {r['slot'] for r in rows}) == ['handover/draft-3']
    assert all(r['course'] for r in rows)
    assert ai_replay.main([str(REPLAY_DIR)]) == 1
    assert '[녹화 없음] handover/draft-3' in capsys.readouterr().out


def test_저장소_녹화는_모두_지금_형식과_열쇠_규칙의_파일_이름이다():
    for path in sorted(Path(REPLAY_DIR).glob('*.json.gz')):
        doc = json.loads(gzip.decompress(path.read_bytes()))
        assert doc['format'] == ai_replay.FORMAT
        assert path.name == ai_replay.course_key(doc['slot'], doc['case']) + '.json.gz'
