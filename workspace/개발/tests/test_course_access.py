"""AI 워커가 process 와 말하는 곳(worker/course_access.py) — 수업 판정 · 실행 토큰 · 실행 닫기. 실제 process(world) · 실제 수업 판정 ·
실제 관문 장부 · 실제 DB. 바깥(강의 중계)만 대체(FakeRelay), 실행 시간이 흐른 것은 장부 행의 기한(시계)으로 만든다.

403 의 본문이 「[HYD:<code>] 문장」이면 관문 장부 거절(LedgerDenied — 머리말은 코드로), 문장만이면 수업 경계 거절(CourseDenied)이다.
"""
import json
import socket
import time
import urllib.request
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from conftest import DEFINITIONS, RELAY_KEY, TENANT, WORKER_KEY, ask_question, start_handover
from procsvc import course_policy
from procsvc.course_ledger import POLICY, REASONS, coded
from worker import course_access
from worker.course_access import CourseAccess, CourseDenied, LedgerDenied, RuntimeConnectionError, Stop

MODEL_NAMES = ('ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL',
               'ANTHROPIC_DEFAULT_HAIKU_MODEL')
#: 장부 거절 코드 → 학생이 보는 처리 기록 머리말(FB → FG 넘김 2번의 요구 그대로)
TITLES = {'run_limit': 'AI 사용 한도', 'task_limit': 'AI 사용 한도', 'pc_limit': 'AI 사용 한도', 'concurrent': '다른 AI 단계 실행 중',
          'run_time': 'AI 실행 다시 필요', 'claim_ended': 'AI 실행 다시 필요', 'token': 'AI 실행 다시 필요'}


def claimed(course, **start):
    """교대 인수인계 처리 건 하나를 시작하고 그 AI 단계를 워커처럼 점유한다(점유마다 새 consumer). 돌려줌 = 점유한 작업 행."""
    start_handover(course.rt, **start)
    [row] = course.rt.repo.fetch_pending_task('cliagents', f'fgb-worker:{uuid.uuid4().hex}', tenant_id=TENANT)
    return row


def access(course, key_file=None):
    return CourseAccess(course.url, str(key_file or course.world.stack.worker_key))


def runs(dsn, todo_id):
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        return db.execute('SELECT state, consumer FROM hyd_course_runs WHERE todo_id=%s ORDER BY created_at', (str(todo_id),)).fetchall()


def closed_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def sql(dsn, statement, *args):
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute(statement, args)


@pytest.fixture
def my_flow(course):
    """학생이 따로 등록한 흐름(수업 AI 자리가 아닌 정의) — 수업 단계에서는 그 AI 단계가 수업 밖이다. 끝나면 지운다."""
    did = 'fgb_my_flow_' + uuid.uuid4().hex[:8]
    raw = json.loads((DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8'))
    raw.update(processDefinitionId=did, processDefinitionName='내가 만든 인계', version='1')
    course.rt.register_definition(raw)
    yield did
    with psycopg.connect(course.dsn, autocommit=True) as db:
        db.execute('DELETE FROM bpm_proc_inst WHERE proc_def_id=%s', (did,))
        db.execute('DELETE FROM proc_def_version WHERE proc_def_id=%s', (did,))
        db.execute('DELETE FROM proc_def WHERE id=%s', (did,))


# ---------------------------------------------------------------- 주소 · 인증 파일(요청 전에 판정)
@pytest.mark.parametrize('url, ok', [
    ('http://process:8080', True),
    ('http://127.0.0.1:18080/', True),
    ('http://localhost:8080', True),
    ('https://process.example.org', True),
    ('http://process.example.org:8080', False),
    ('http://user:pw@process:8080', False),
    ('http://process:8080/api', False),
    ('http://process:8080?x=1', False),
    ('http://process:8080#a', False),
    ('ftp://process:8080', False),
    ('', False),
], ids=['서비스 이름', '이 PC 끝 빗금', 'localhost', '바깥 HTTPS', '바깥 HTTP', '사용자 정보', '경로', '질의', '조각', '다른 방식', '빈 주소'])
def test_process_주소는_이_PC_안의_HTTP_나_HTTPS_만_받고_사용자_정보_경로가_붙으면_거절한다(url, ok):
    if ok:
        assert course_access.process_base(url) == url.rstrip('/')
    else:
        with pytest.raises(RuntimeConnectionError) as e:
            course_access.process_base(url)
        assert '시작.bat' in str(e.value) and e.value.title == '연결 확인 필요'


@pytest.mark.parametrize('content', [None, '', 'k' * 31, '   ' + 'k' * 20 + '   '], ids=['파일 없음', '빈 파일', '31자', '공백 빼면 20자'])
def test_실행기_인증_파일이_없거나_32자보다_짧으면_연결_확인_필요로_멈춘다(tmp_path, content):
    path = tmp_path / 'runtime.key'
    if content is not None:
        path.write_text(content, encoding='utf8')
    with pytest.raises(RuntimeConnectionError) as e:
        course_access.read_key(path)
    assert '실행기 인증 파일' in str(e.value) and '시작.bat' in str(e.value)


def test_실행기_인증_파일은_앞뒤_공백을_뗀_값을_쓴다(tmp_path):
    path = tmp_path / 'runtime.key'
    path.write_text('\n' + WORKER_KEY + '  \n', encoding='utf8')
    assert course_access.read_key(path) == WORKER_KEY


# ---------------------------------------------------------------- 장부 거절 코드 → 머리말(문장은 사유 표의 것, 코드 글자 없이)
@pytest.mark.parametrize('code', sorted(TITLES))
def test_코드가_실린_403_본문은_그_코드의_머리말과_사유_표_문장의_장부_거절이다(code):
    denial = course_access.ledger_denial(coded(code))
    assert isinstance(denial, LedgerDenied) and isinstance(denial, Stop)
    assert (denial.code, denial.title, str(denial)) == (code, TITLES[code], REASONS[code].text)
    assert '[HYD:' not in str(denial)


@pytest.mark.parametrize('detail', [course_policy.Policy.REASONS['ai_slot'], '질문은 1~2000자로 적습니다.', ''],
                         ids=['수업 밖 AI 단계', '질문 길이', '빈 본문'])
def test_코드가_없는_403_본문은_장부_거절이_아니다(detail):
    assert course_access.ledger_denial(detail) is None


# ---------------------------------------------------------------- 실제 process: 수업 판정
def test_점유한_교대_초안의_수업_판정은_서버가_정한_수업_AI_자리와_단계다(course):
    row = claimed(course)
    assert access(course).decide(row, TENANT) == {'slot': 'handover/draft-1', 'phase': 'course'}


def test_질문_단계의_수업_판정은_질문_자리다(course):
    ask_question(course.rt, 'HYD-01 유온이 왜 올라가나요?')
    [row] = course.rt.repo.fetch_pending_task('cliagents', f'fgb-worker:{uuid.uuid4().hex}', tenant_id=TENANT)
    assert access(course).decide(row, TENANT)['slot'] == 'question'


def test_수업_밖_흐름의_AI_단계는_process_가_쓴_학생_문장_그대로_수업_권한_확인_필요로_멈춘다(course, my_flow):
    row = claimed(course, definition=my_flow, version='1')
    for call in (access(course).decide, access(course).permit):
        with pytest.raises(CourseDenied) as e:
            call(row, TENANT)
        assert (str(e.value), e.value.title) == (course_policy.Policy.REASONS['ai_slot'], 'AI 실행 범위 확인 필요')
        assert not isinstance(e.value, LedgerDenied)
    assert runs(course.dsn, row['id']) == []                  # 거절된 실행은 장부에 열리지 않았다


def test_지금_점유가_아닌_작업의_판정은_상태_코드와_process_까닭을_실은_연결_확인_필요다(course):
    row = claimed(course)
    stale = dict(row, consumer=row['consumer'] + ':old')
    with pytest.raises(RuntimeConnectionError) as e:
        access(course).decide(stale, TENANT)
    assert '(409) — ' in str(e.value) and not isinstance(e.value, CourseDenied)


def test_process_에_닿지_않으면_연결_확인_필요로_멈추고_시작_bat_을_안내한다(course, tmp_path):
    row = claimed(course)
    down = CourseAccess(f'http://127.0.0.1:{closed_port()}', str(course.world.stack.worker_key))
    with pytest.raises(RuntimeConnectionError) as e:
        down.decide(row, TENANT)
    assert '닿지 않습니다' in str(e.value) and '시작.bat' in str(e.value)


def test_인증_파일이_process_의_것과_다르면_수업_권한이_아니라_연결_확인_필요로_멈춘다(course, tmp_path):
    """실행기 인증 거절(process 401 — course_policy.require_worker)은 수업 경계 판정(403)이 아니다 — 인증 파일 문제는 read_key 처럼
    「연결 확인 필요」(시작.bat 다시 실행)로 보여야 학생이 할 일을 안다."""
    other = tmp_path / 'other.key'
    other.write_text('z' * 48, encoding='utf8')
    row = claimed(course)
    with pytest.raises(Stop) as e:
        access(course, other).decide(row, TENANT)
    assert isinstance(e.value, RuntimeConnectionError), (type(e.value).__name__, e.value.title, str(e.value))
    assert '실행기 인증' in str(e.value) and '시작.bat을 다시 실행하세요' in str(e.value) and '(401)' not in str(e.value), str(e.value)


# ---------------------------------------------------------------- 실제 process: 실행 토큰 · 닫기
def test_실행_권한은_관문_주소와_그_점유의_토큰만_CLI_환경에_주고_그_환경으로_부른_모델은_중계에_닿는다(course, relay):
    row = claimed(course)
    grant = access(course).permit(row, TENANT)
    env, token = grant['env'], grant['env']['ANTHROPIC_API_KEY']
    assert grant['model'] == POLICY['model'] and all(env[name] == POLICY['model'] for name in MODEL_NAMES)
    assert env['ANTHROPIC_BASE_URL'] == course.url + '/internal/model'
    assert token.startswith('HydModel ') and grant['secrets'] == [token]
    assert (env['ANTHROPIC_AUTH_TOKEN'], env['OPENAI_API_KEY'], env['LLM_API_KEY']) == ('', '', '')    # 원본 키 자리는 비운다
    assert time.time() < grant['deadline'] <= time.time() + POLICY['run']['seconds'] + 1
    assert [r['state'] for r in runs(course.dsn, row['id'])] == ['OPEN']
    body = json.dumps({'model': grant['model'], 'max_tokens': 16, 'messages': [{'role': 'user', 'content': '다음 단계'}]}).encode()
    call = urllib.request.Request(env['ANTHROPIC_BASE_URL'] + '/v1/messages', data=body, method='POST',
                                  headers={'x-api-key': token, 'content-type': 'application/json'})
    with urllib.request.urlopen(call, timeout=15) as response:
        assert response.status == 200
    assert relay.requests[-1]['headers']['x-api-key'] == RELAY_KEY      # 중계에는 process 의 키가 간다(CLI 토큰이 아님)


def test_실행을_닫으면_그_점유의_장부_실행이_끝나고_같은_점유로는_다시_열리지_않는다(course):
    row = claimed(course)
    grant = access(course)
    grant.permit(row, TENANT)
    assert grant.end(row, TENANT) is None
    assert [r['state'] for r in runs(course.dsn, row['id'])] == ['ENDED']
    with pytest.raises(LedgerDenied) as e:
        grant.permit(row, TENANT)
    assert (e.value.code, e.value.title, str(e.value)) == ('claim_ended', TITLES['claim_ended'], REASONS['claim_ended'].text)


def _another_claim_running(course, row):
    access(course).permit(claimed(course), TENANT)


def _run_time_passed(course, row):
    access(course).permit(row, TENANT)
    sql(course.dsn, "UPDATE hyd_course_runs SET deadline = now() - interval '1 second' WHERE todo_id=%s", str(row['id']))


def _task_used_up(course, row):
    sql(course.dsn, 'INSERT INTO hyd_course_grants(account, policy) VALUES (%s, %s) ON CONFLICT (account) DO NOTHING', TENANT, Jsonb(POLICY))
    sql(course.dsn, "INSERT INTO hyd_course_runs(id, account, todo_id, generation, consumer, state, deadline, calls) "
        "VALUES (%s, %s, %s, 0, %s, 'ENDED', now(), %s)", uuid.uuid4(), TENANT, str(row['id']), 'fgb-earlier', POLICY['task']['calls'])


def _pc_used_up(course, row):
    sql(course.dsn, 'INSERT INTO hyd_course_grants(account, policy, calls) VALUES (%s, %s, %s) '
        'ON CONFLICT (account) DO UPDATE SET calls = excluded.calls', TENANT, Jsonb(POLICY), POLICY['pc']['calls'])


@pytest.mark.parametrize('arrange, code', [
    (_another_claim_running, 'concurrent'),
    (_run_time_passed, 'run_time'),
    (_task_used_up, 'task_limit'),
    (_pc_used_up, 'pc_limit'),
], ids=['다른 점유 실행 중', '한 번 실행 시간 지남', '작업 한도 소진', 'PC 한도 소진'])
def test_관문_장부가_열지_않은_실행은_코드로_고른_머리말과_사유_문장으로_멈춘다(course, arrange, code):
    """P2-13: 장부 거절은 권한 문제가 아니다 — 옛 워커는 모두 「수업 권한 확인 필요 · [HYD:…] …」로 보였다."""
    row = claimed(course)
    arrange(course, row)
    with pytest.raises(LedgerDenied) as e:
        access(course).permit(row, TENANT)
    assert (e.value.code, e.value.title, str(e.value)) == (code, TITLES[code], REASONS[code].text)
    assert not isinstance(e.value, CourseDenied) and isinstance(e.value, Stop)
