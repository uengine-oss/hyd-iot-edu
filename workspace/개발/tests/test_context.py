"""점유한 작업 행이 싣지 않는 것을 읽는 곳(worker/context.py) — 폼(결과 계약) · 사람과 에이전트 · 테넌트 도구 서버(+ 비밀 값) · 피드백.
실제 업무 DB(마이그레이션 + seed.sql), 고정 판 정의는 실제 process(world)가 등록한 것. 작업 행 자체는 입력이다(표의 경계 · 실패 칸).
"""
import json
import uuid
from datetime import datetime, timezone

import pytest

from conftest import DEFINITIONS, OPERATOR, TENANT, start_handover
from procsvc import mcp_secrets, procdb
from worker import bridge, context
from worker.context import FREEFORM_FIELDS

SEED_FORM = 'diagnose'          # seed.sql 의 옛 폼 표(form_def) 한 줄


def handover_file():
    return json.loads((DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8'))


def seed_form_fields(dsn, form_id):
    import psycopg
    with psycopg.connect(dsn) as db:
        (fields,) = db.execute('SELECT fields_json FROM form_def WHERE id=%s AND tenant_id=%s', (form_id, TENANT)).fetchone()
    return fields


def tenant_mcp(dsn):
    import psycopg
    with psycopg.connect(dsn) as db:
        (mcp,) = db.execute('SELECT mcp FROM tenants WHERE id=%s', (TENANT,)).fetchone()
    return mcp


@pytest.fixture
def repo(pg_dsn):
    return procdb.PgRepo(pg_dsn)


@pytest.fixture
def secret(repo):
    """비밀 값 표에 값 둘(이 테스트가 넣고 끝나면 지운다) — 하나는 서버가 쓰고 하나는 쓰지 않는다."""
    values = {'FGB_TOKEN': 'fgb-token-' + uuid.uuid4().hex, 'FGB_UNUSED': 'fgb-unused-' + uuid.uuid4().hex}
    now = datetime.now(timezone.utc).isoformat()
    for key, value in values.items():
        mcp_secrets.put(repo, TENANT, key, value, 'test:fgb', now)
    yield values
    for key in values:
        mcp_secrets.remove(repo, TENANT, key)


# ---------------------------------------------------------------- 작업 행의 계약(정의 판 · 테넌트)
@pytest.mark.parametrize('row, error, text', [
    ({'id': 'w1', 'tenant_id': 'other', 'tool': ''}, ValueError, '다른 테넌트의 작업입니다'),
    ({'id': 'w1', 'tenant_id': TENANT, 'proc_def_id': 'shift_handover', 'version': None}, LookupError, '고정 정의 버전이 없습니다'),
    ({'id': 'w1', 'tenant_id': TENANT, 'proc_def_id': 'fgb_no_such_flow', 'version': '1'}, LookupError, '고정 정의를 찾을 수 없습니다'),
], ids=['다른 테넌트', '판본 없음', '등록되지 않은 판본'])
def test_작업_행이_다른_테넌트이거나_고정_판_정의를_가리키지_못하면_까닭과_함께_멈춘다(repo, row, error, text):
    with pytest.raises(error) as e:
        context.prepare(repo, row, TENANT)
    assert text in str(e.value)


# ---------------------------------------------------------------- 정의 없는 작업(옛 폼 표 · 자유형식)
@pytest.mark.parametrize('tool, form_id, from_table', [
    (f'formHandler:{SEED_FORM}', SEED_FORM, True),
    (SEED_FORM, SEED_FORM, True),
    ('', 'freeform', False),
], ids=['폼 도구', '폼 이름만', '도구 없음'])
def test_정의_없는_작업은_옛_폼_표의_폼을_쓰고_없으면_자유형식_한_칸이다(repo, pg_dsn, tool, form_id, from_table):
    ctx = context.prepare(repo, {'id': 'w1', 'tenant_id': TENANT, 'tool': tool}, TENANT)
    assert ctx.form_id == form_id and ctx.definition is None
    assert ctx.form_fields == (seed_form_fields(pg_dsn, SEED_FORM) if from_table else FREEFORM_FIELDS)


def test_없는_폼을_가리키는_작업은_자유형식으로_돌지_않고_폼_이름과_함께_멈춘다(repo):
    """결과 계약이 없는 채로 AI 가 아무 글이나 내고 성공하던 조용한 폴백(2026-11-14 전수 검사)."""
    with pytest.raises(LookupError) as e:
        context.prepare(repo, {'id': 'w1', 'tenant_id': TENANT, 'tool': 'formHandler:fgb_no_such_form'}, TENANT)
    assert 'fgb_no_such_form' in str(e.value)


@pytest.mark.parametrize('user_id, agents, users, profile', [
    ('agent:cooling, role:operator ,sys:scada', ['agent:cooling', 'sys:scada'], ['role:operator'], 'agent:cooling'),
    ('sys:scada,agent:pm-plan', ['agent:pm-plan', 'sys:scada'], [], 'agent:pm-plan'),
    ('sys:scada', ['sys:scada'], [], None),
    (OPERATOR['by'], [], [OPERATOR['by']], None),
    ('', [], [], None),
    ('fgb:nobody', [], [], None),
], ids=['에이전트 · 사람 · 시스템', '시스템이 앞에 적힘', '시스템만', '사람만', '배정 없음', '없는 id'])
def test_배정된_id_는_에이전트와_사람으로_나뉘고_프로필은_시스템이_아닌_첫_에이전트다(repo, user_id, agents, users, profile):
    ctx = context.prepare(repo, {'id': 'w1', 'tenant_id': TENANT, 'tool': '', 'user_id': user_id}, TENANT)
    assert [a['id'] for a in ctx.agents] == agents and [u['id'] for u in ctx.users] == users
    assert (ctx.profile or {}).get('id') == profile


@pytest.mark.parametrize('feedback, text, answer', [
    (None, '', ''),
    ('다시 확인하세요', '다시 확인하세요', ''),
    ({'text': '근거를 보태세요', 'human_answer': '오늘은 정지 불가'}, '근거를 보태세요', '오늘은 정지 불가'),
    ({'human_answer': '예'}, '', '예'),
    ({}, '', ''),
], ids=['없음', '글', '글과 사람 답', '사람 답만', '빈 객체'])
def test_피드백은_글_또는_글과_사람_답으로_읽는다(repo, feedback, text, answer):
    ctx = context.prepare(repo, {'id': 'w1', 'tenant_id': TENANT, 'tool': '', 'feedback': feedback}, TENANT)
    assert (ctx.feedback, ctx.human_answer) == (text, answer)


def test_테넌트_도구_서버_설정은_업무_DB_의_tenants_mcp_다(repo, pg_dsn):
    ctx = context.prepare(repo, {'id': 'w1', 'tenant_id': TENANT, 'tool': ''}, TENANT)
    assert ctx.tenant_mcp == tenant_mcp(pg_dsn)


# ---------------------------------------------------------------- 비밀 값(${SECRET:KEY})
def test_서버가_쓰는_비밀_값만_설정에_실리고_프롬프트_재료에는_실리지_않는다(repo, secret):
    config = {'mcpServers': {'mine': {'type': 'url', 'url': 'http://127.0.0.1:9/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:FGB_TOKEN}'}},
                             'neo4j': {'type': 'url', 'url': 'http://127.0.0.1:9/neo4j/mcp'}}}
    held = context.with_secrets(repo, TENANT, config)
    assert held[bridge.SECRETS_KEY] == {'FGB_TOKEN': secret['FGB_TOKEN']}                  # 쓰지 않는 FGB_UNUSED 는 싣지 않는다
    assert bridge.SECRETS_ERROR_KEY not in held
    extras = context.Context(row={'id': 'w1'}, form_id='freeform', form_fields=FREEFORM_FIELDS, tenant_mcp=held).extras
    assert secret['FGB_TOKEN'] not in json.dumps(extras, ensure_ascii=False)
    assert extras['tenant_mcp'] == config


def test_비밀_자리표시자가_없는_설정은_비밀_값_표를_읽지_않고_그대로다(scratch_db):
    config = {'mcpServers': {'neo4j': {'type': 'url', 'url': 'http://127.0.0.1:9/neo4j/mcp'}}}
    assert context.with_secrets(procdb.PgRepo(scratch_db), TENANT, config) is config         # 표가 없는 DB 라도 읽지 않으니 실패하지 않는다


def test_비밀_값_표를_읽지_못하면_점유는_이어가고_그_서버를_뺀_까닭에_표_문제가_실린다(scratch_db):
    """표가 없는 DB(마이그레이션 전) — 다른 서버는 그대로 돌고, 비밀이 필요한 서버는 「표를 읽지 못함」 까닭으로 빠진다."""
    config = {'mcpServers': {'mine': {'type': 'url', 'url': 'http://127.0.0.1:9/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:FGB_TOKEN}'}}}}
    held = context.with_secrets(procdb.PgRepo(scratch_db), TENANT, config)
    assert held[bridge.SECRETS_KEY] == {} and held[bridge.SECRETS_ERROR_KEY] == mcp_secrets.PgSecretStore.MISSING
    gate = bridge.gate_servers(held, trusted={'mine'})
    assert 'mine' not in gate.config['mcpServers'] and mcp_secrets.PgSecretStore.MISSING in gate.dropped['mine']


# ---------------------------------------------------------------- 처리 범위 · 프롬프트 재료 · 프로필
@pytest.mark.parametrize('row, scope', [
    ({'tenant_id': 'hyd', 'proc_inst_id': 'p1', 'id': 'w1', 'generation': 2, 'version': '1.1', 'consumer': 'c1'},
     {'tenant': 'hyd', 'instance': 'p1', 'workitem': 'w1', 'generation': 2, 'version': '1.1', 'consumer': 'c1'}),
    ({'tenant_id': 'hyd', 'proc_inst_id': 'p1', 'id': 'w1', 'generation': None},
     {'tenant': 'hyd', 'instance': 'p1', 'workitem': 'w1', 'generation': 0, 'version': None, 'consumer': None}),
    ({'id': 'w1', 'generation': '3'}, {'tenant': None, 'instance': None, 'workitem': 'w1', 'generation': 3, 'version': None, 'consumer': None}),
], ids=['전부 있음', '세대 없음 = 0', '세대 글자'])
def test_처리_범위는_테넌트_처리_건_작업_세대_판본_점유이다(row, scope):
    assert context.process_scope(row) == scope


def test_프롬프트_재료의_처리_건은_하위_처리_건이면_뿌리_처리_건이다():
    row = {'id': 'w1', 'proc_inst_id': 'child', 'root_proc_inst_id': 'root', 'activity_name': '인계안 작성'}
    extras = context.Context(row=row, form_id='freeform', form_fields=FREEFORM_FIELDS).extras
    assert (extras['proc_inst_id'], extras['activity_name'], extras['process_scope']['instance']) == ('root', '인계안 작성', 'child')
    assert context.Context(row=dict(row, root_proc_inst_id=None), form_id='f', form_fields=[]).extras['proc_inst_id'] == 'child'


@pytest.mark.parametrize('agents, profile', [
    ([{'id': 'sys:scada', 'agent_type': 'system'}, {'id': 'agent:a', 'agent_type': 'agent'}, {'id': 'agent:b', 'agent_type': 'agent'}], 'agent:a'),
    ([{'id': 'agent:x', 'agent_type': None}], 'agent:x'),
    ([{'id': 'sys:process', 'agent_type': 'system'}], None),
    ([], None),
], ids=['시스템 건너 첫 에이전트', '종류 없음 = 에이전트', '시스템만', '없음'])
def test_프로필은_시스템_수행자가_아닌_첫_에이전트다(agents, profile):
    assert (context.agent_profile(agents) or {}).get('id') == profile


# ---------------------------------------------------------------- 실제 process 가 등록한 고정 판 정의
def test_교대_초안_작업은_등록된_그_판_정의의_폼과_결과_계약을_쓴다(course):
    """폼은 그 판 정의 안의 것(정의 파일 원문) — 옛 폼 표가 아니다. 배정 에이전트는 인계안 에이전트."""
    inst = start_handover(course.rt)
    [row] = course.rt.repo.fetch_pending_task('cliagents', f'fgb-worker:{uuid.uuid4().hex}', tenant_id=TENANT)
    assert row['proc_inst_id'] == inst['proc_inst_id']
    shipped = handover_file()
    activity = next(a for a in shipped['activities'] if a['id'] == row['activity_id'])
    form_id = activity['tool'].split(':', 1)[1]
    ctx = context.prepare(course.rt.repo, row, TENANT)
    assert ctx.definition['version'] == shipped['version'] == row['version']
    assert (ctx.form_id, ctx.form_fields, ctx.form_contract) == (form_id, shipped['forms'][form_id]['fields_json'],
                                                                   shipped['forms'][form_id]['contract'])
    endpoint = next(r['endpoint'] for r in shipped['roles'] if r['name'] == activity['role'])
    assert [a['id'] for a in ctx.agents] == [endpoint] and ctx.profile['id'] == endpoint
    assert context.activity_capabilities(ctx.definition, row['activity_id'])['contract'] == shipped['forms'][form_id]['contract']


def test_등록된_정의에_없는_단계를_가리키는_작업은_멈춘다(course):
    start_handover(course.rt)
    [row] = course.rt.repo.fetch_pending_task('cliagents', f'fgb-worker:{uuid.uuid4().hex}', tenant_id=TENANT)
    with pytest.raises(ValueError) as e:
        context.prepare(course.rt.repo, dict(row, activity_id='task:fgb-none'), TENANT)
    assert '정의에 없는 작업입니다' in str(e.value)
