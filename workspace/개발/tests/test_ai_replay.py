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
from student_words import WORKER_TALK
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


def test_녹화와_수량만_다른_지금_계산은_멈추지_않고_어느_값이_준비_당시_값인지_처리_과정에_말한다(world):
    """전수검사 04-D3: 재고 보충 녹화는 정기 정비를 먼저 승인한 뒤(예약 3 · 필요 7개 · 총비용 420)에 떠졌다. 시작 상태(예약 2 · 필요 6개)에서
    재생하면 AI 설명은 7개 · 420만 원, 승인 카드는 6개 · 360만 원인데 아무 말이 없었다. 권장 조치는 같으므로 멈추지 않고 그 차이를 말한다."""
    pid, did = _scenario('C')(world)
    card = next(o for o in world.main.book[did]['options'] if o['id'] == world.main.book[did]['recommended'])
    now = card['economicComparison']
    assert (now['quantity'], now['total_cost']) == (6, 360)                                 # 이 PC의 지금 계산(시작 상태)
    notices = [e['data'] for e in world.events(pid) if (e.get('data') or {}).get('type') == 'notice']
    said = [d['content'] for d in notices]
    found = next((d for d in notices if '준비 당시 값' in d['content']), None)
    line = found and found['content']
    assert line and line.startswith(ai_replay.REPLAY) and '수량 7 → 6개' in line and '비교 총비용 420 → 360만 원' in line, said
    assert '「순정(OEM) 공급사 표준 발주」' in line and not FORBIDDEN.search(line) and '강사' not in line and '녹화' not in line
    # 화면이 문장을 읽어 가르지 않게 종류를 싣는다: 묶음 종류와 문장마다의 종류, 문장을 이으면 content 다. 기본 제공 구성 그대로인 실행이라 스킬 안내는 없다
    kinds = [part['kind'] for part in found['parts']]
    assert found['kind'] == 'replay' and kinds[:2] == ['prepared', 'values_differ'] and set(kinds) <= set(ai_replay.NOTICE_KINDS) - {'skills'}, found
    assert ' '.join(part['text'] for part in found['parts']) == line
    assert '수량 7 → 6개' in next(part['text'] for part in found['parts'] if part['kind'] == 'values_differ')


@pytest.mark.parametrize('slot, start', [
    ('c3_cooling/T_agent', lambda world: world.start_cooling()[1:]),
    ('c3_pm/T_agent', _scenario('B')),
], ids=['냉각 경보', '정기 점검'])
def test_지금_계산이_녹화와_같은_판단이면_재생_안내를_남기지_않는다(world, slot, start):
    """평소 실행의 화면은 실제 AI 실행과 같다(CLAUDE.md 5절) — 점수 · 예측처럼 측정값을 따라 조금씩 달라지는 값으로는 안내하지 않는다."""
    pid, _ = start(world)
    assert [e['data']['content'] for e in world.events(pid) if (e.get('data') or {}).get('type') == 'notice' and '재생 모드' in e['data']['content']] == []


def test_재생이_보이는_스킬_파일_읽기_결과는_이_실행의_작업_폴더에_있는_지금_본문이다(world, tmp_path):
    """한 바퀴 실측(2026-11-14): 냉각 판단의 처리 과정에서 「읽은 스킬 파일」을 펼치면 녹화 당시의 옛 본문(「… 카드 (시나리오 A)」)이 보였다 —
    스킬의 이름 · 설명은 그 뒤 고쳤다(마이그레이션 078). 워커는 실행 전에 에이전트의 스킬을 작업 폴더에 쓰므로, 그 파일을 통째로 읽은 호출의
    결과는 그 파일의 지금 본문으로 보인다. 작업 폴더에 없는 스킬(학생이 뗀 스킬)이나 일부만 읽은 호출은 저장된 결과 그대로다."""
    pid, _ = world.start_cooling()[1:]
    skill = world.rt.repo.get_skill(world.rt.tenant_id, 'cooling-emergency-response')
    shown = json.dumps([e['data'] for e in world.events(pid)], ensure_ascii=False)
    assert 'cooling-emergency-response/SKILL.md' in shown                       # 그 스킬 파일을 읽는 호출이 처리 과정에 있다
    assert f"description: {skill['description']}" in shown and '시나리오 A' not in shown
    # 같은 호출을 손으로: 파일이 있으면 지금 본문(녹화와 같은 줄 번호 꼴), 없거나 일부만 읽었으면 None(저장된 결과 그대로)
    recorded = '0\t---\n1\tname: x\n2\tdescription: 옛 설명\n3\t---\n4\t\n5\t# 옛 제목'
    read = {'file_path': '/workspace/hyd/abc/.claude/skills/my-skill/SKILL.md', 'offset': 0, 'limit': 2000}
    assert ai_replay.skill_file_now(tmp_path, 'Read', read, recorded) is None
    (tmp_path / '.claude/skills/my-skill').mkdir(parents=True)
    (tmp_path / '.claude/skills/my-skill/SKILL.md').write_text('---\nname: x\ndescription: 지금 설명\n---\n\n# 지금 제목\n', encoding='utf8')
    assert ai_replay.skill_file_now(tmp_path, 'Read', read, recorded) == '0\t---\n1\tname: x\n2\tdescription: 지금 설명\n3\t---\n4\t\n5\t# 지금 제목'
    assert ai_replay.skill_file_now(tmp_path, 'Read', read, '     1\t---\n     2\tname: x\n     3\t옛').startswith('     1\t---\n     2\tname: x\n     3\tdescription: 지금 설명')
    assert ai_replay.skill_file_now(tmp_path, 'Read', read, '2\tdescription: 옛 설명') is None
    assert ai_replay.skill_file_now(tmp_path, 'Bash', read, recorded) is None


def _replay_recorded_under_another_state(tmp_path, slot, change):
    """시험이 만든 녹화 묶음: 저장소 녹화를 복사하되 그 자리의 녹화가 등록했던 판단 문서만 바꾼다(change) — 다른 설비 · 업무 상태에서 뜬 녹화의 대역."""
    import shutil
    out = tmp_path / 'replay-other-state'
    shutil.copytree(REPLAY_DIR, out)
    doc = next(d for key, d in docs().items() if key.startswith(slot + '|'))
    run = doc['runs'][0]
    for e in run['events']:
        if e['kind'] == 'tool_end' and (e.get('tool') or '').endswith(('submit_decision', 'submit_purchase')) and not e.get('is_error'):
            full = run.setdefault('tool_outputs_full', {})
            body = ai_replay._as_json(full.get(e['tool_use_id']) or e.get('tool_output'))
            if ai_replay._failed(body):
                continue
            change(body['document'])
            full[e['tool_use_id']] = json.dumps(body, ensure_ascii=False)
    Library(out, COURSE).file_of(ai_replay.course_key(doc['slot'], doc['case'])).write_bytes(gzip.compress(json.dumps(doc, ensure_ascii=False).encode('utf8')))
    return out


def test_지금_계산의_권장_조치가_녹화와_다르면_그_설명을_이_처리_건에_쓰지_않고_까닭을_말하며_멈춘다(world, tmp_path):
    """전수검사 02-1: 재생은 녹화의 AI 설명 · 결과 글을 그대로 내고 승인 카드만 지금 계산이라, 둘이 다른 조치를 권해도 대조하지 않았다."""
    def other_card_recommended(document):
        document['recommended'] = 'skill:sop-cool-13'
    made = _replay_recorded_under_another_state(tmp_path, 'c3_cooling/T_agent', other_card_recommended)
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    tags = world.plant.tags('HYD-01')
    _, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01', ts1=tags['TS1'], ce=tags['CE'])
    world.report()
    assert world.runner('replay', replay_dir=made).poll_once() == 1
    row = world.row(pid, 'T_agent')
    text = json.dumps(world._failure(row), ensure_ascii=False)
    assert row['status'] not in ('SUBMITTED', 'DONE'), row['status']
    assert ai_replay.REPLAY in text and '권장 조치가 준비된 판단은 「부하 70 %와 야간 핀 세척」인데 지금 계산은 「팬 최대 운전」입니다' in text, text
    assert not FORBIDDEN.search(text) and '강사' not in text and '녹화' not in text


@pytest.mark.parametrize('slot, skills, changed, said', [
    ('question', ['cooler-check'], True, True), ('question', [], True, False),
    ('handover/draft-1', ['my-shift-handover-review'], True, False), ('handover/draft-1', [], True, True),
    ('question', ['cooler-check'], False, False), ('handover/draft-1', [], False, False),
], ids=['스킬 붙임', '스킬 없음 그대로', '저장된 실행과 같은 스킬', '저장된 실행의 스킬을 뗌',
        '기본 제공 구성 — 저장된 실행이 열지 않은 스킬이 붙어 있어도 말하지 않음', '기본 제공 구성 — 스킬 없는 단계'])
def test_스킬_구성이_저장된_실행과_다를_때만_같은_답이라고_말한다(tmp_path, tool_servers, slot, skills, changed, said):
    """실라버스 포털 실습 3번(스킬을 붙이고 같은 질문 → 떼고 같은 질문): 재생은 같은 답을 내므로 「스킬이 아무 일도 안 한다」로 배우지
    않게, 스킬 구성이 저장된 실행(그 실행이 연 스킬)과 다를 때만 처리 과정 한 줄로 말한다. 수업 기본 구성 그대로인 평소 실행에는
    재생 안내를 남기지 않는다(화면은 실제 AI 실행과 같다, CLAUDE.md 5절). 교대 초안은 조회 결과가 이 PC와 달라 다른 안내(읽기 조회 견주기)가
    붙을 수 있다 — 여기서는 스킬 말만 본다. changed: 학생이 스킬 구성을 바꿀 수 있었던 실행인가(포털에서 만든 에이전트 · 스킬 —
    runner._skills_changed). 기본 제공 구성의 실행은 붙은 스킬이 저장된 실행이 연 스킬과 달라도 말하지 않는다 — 한 바퀴 실측(2026-11-14)에서
    AI 단계마다 같은 스킬 안내가 붙었다."""
    doc = next(d for key, d in docs().items() if key.startswith(slot + '|'))
    wd, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers)
    c = Responses('replay', course=COURSE_LIB).claim(cli=None, slot=slot, case=doc['case'], attempt=(0, 0), request_key=None,
                                                    step=doc['step'], provider='claude-code', source={}, accepted=lambda s: True, skills=skills,
                                                    skills_changed=changed)
    play(c, wd)
    text = c.notice()
    if said:
        assert '같은 답을 냅니다' in text and (', '.join(skills) or '없음') in text and '강사' not in text
        assert ('skills', next(t for k, t in c.notices()[1] if k == 'skills')) in c.notices()[1] and c.notices()[0] == 'replay'
    else:
        assert '같은 답을 냅니다' not in (text or '')
    if slot == 'question':                      # 표를 돌려준 조회가 없는 저장분 — 견줄 것이 없어 조회 말이 없다
        assert '조회 결과' not in (text or '')


# ---------------------------------------------------------------- 사람이 넣은 글 견주기
MEMO = '쿨러 핀 세척 뒤 유온 51 ℃ 안정. 팬 소음은 확인 안 됨.'


@pytest.mark.parametrize('change, said', [
    ({'work_notes': MEMO}, True),
    ({'as_of': '2026-11-02T09:00:00+00:00'}, False),
    ({'work_notes': None}, False),
], ids=['다른 메모', '시각만 다름', '띄어쓰기 · 끝 마침표만 다름'])
def test_지금_넣은_글이_저장된_실행의_입력과_다르면_멈추지_않고_그_글을_두고_쓴_답이_아니라고_말한다(tmp_path, tool_servers, change, said):
    """한 바퀴 실측(2026-11-14): 학생이 넣은 메모는 「쿨러 핀 세척 뒤 유온 51 ℃ 안정 …」인데 재생한 인계안은 「정비 완료 메모와 달리 …」
    「부품 도착 예정은 …」처럼 준비 당시의 메모를 두고 말했고 아무 알림이 없었다. 데이터를 고르는 입력과 달리 멈추지는 않는다(키 없는
    PC에서 이 단계를 해 볼 길이 없어진다) — 결과는 그대로 내고, 무엇을 두고 쓴 글인지를 처리 과정에 말한다. 같은 글이면 말이 없다."""
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    run = doc['runs'][0]
    recorded = run['context']['inputs']['work_notes']
    if change.get('work_notes', '') is None:
        change = {'work_notes': '  ' + recorded.replace(' ', '  ').rstrip('.') + ' '}
    wd, _ = workdir_for(tmp_path, run, tool_servers, inputs=dict(run['context']['inputs'], **change))
    c = Responses('replay', course=COURSE_LIB).claim(cli=None, slot='handover/draft-1', case='', attempt=(0, 0), request_key=None,
                                                    step=doc['step'], provider='claude-code', source={}, accepted=lambda s: True,
                                                    skills=['my-shift-handover-review'])
    assert play(c, wd) and (wd / 'output' / 'result.json').is_file()           # 멈추지 않는다
    text = c.notice() or ''
    if said:
        assert text.startswith(ai_replay.REPLAY), text
        assert f'결과 글은 준비 당시의 입력을 두고 쓴 것이고, 지금 넣은 입력과 다릅니다: 준비 당시 「{recorded}」 · 지금 「{MEMO}」.' in text, text
        assert not FORBIDDEN.search(text) and not WORKER_TALK.search(text) and 'work_notes' not in text, text
    else:
        assert '지금 넣은 입력' not in text, text


# ---------------------------------------------------------------- 읽기 조회 견주기
# 조회문 안의 EXTRACT(… FROM 칸)은 자료를 읽는 FROM 이 아니다 — 알림이 칸 이름을 자료 이름으로 말하면 안 된다
STOCK_SQL = 'SELECT part_no, on_hand, reserved, on_order, updated_at, extract(year FROM updated_at) AS y FROM ent.spare_stock ORDER BY part_no'
ORDERS_SQL = "SELECT id, asset, status, created_at FROM ent.work_orders WHERE asset = 'HYD-03' ORDER BY created_at DESC"
SLOT = 'handover/draft-1'


def _asked(url, sql):
    """이 PC의 업무 자료 조회 도구를 실제로 불러 받은 표(document)."""
    from procsvc import mcp_check
    out = mcp_check.call(mcp_check.normalize({'url': url}), 'query', {'sql': sql}, max_chars=1_000_000)
    assert out['status'] == 'ok' and not out['result']['is_error'], out
    return json.loads(out['result']['text'])['document']


def _recording_of_reads(tmp_path, reads):
    """시험이 만든 저장분: 업무 자료 조회(reads = [(조회문, 그때 받은 표)])만 한 실행 하나 — 다른 때 · 다른 PC에서 뜬 저장분의 대역.
    이벤트의 꼴은 저장소 저장분의 조회 한 쌍을 본뜬다."""
    real = next(d for key, d in docs().items() if key.startswith(SLOT + '|'))['runs'][0]
    start = next(e for e in real['events'] if e['kind'] == 'tool_start' and e['tool'] == 'mcp__enterprise__query')
    end = next(e for e in real['events'] if e['kind'] == 'tool_end' and e['tool_use_id'] == start['tool_use_id'])
    events = []
    for n, (sql, document) in enumerate(reads):
        text = json.dumps({'result': 'ok', 'document': document}, ensure_ascii=False)
        events += [dict(start, tool_input={'sql': sql}, tool_use_id=f'call_{n}'), dict(end, text=text, tool_output=text, tool_use_id=f'call_{n}')]
    run = {'session_id': start['session_id'], 'events': events, 'result_file': '{"note": "조회만 한 실행"}', 'context': real['context'],
           'tool_outputs_full': {}}
    doc = {'format': ai_replay.FORMAT, 'slot': SLOT, 'case': '', 'step': '인계안 작성', 'provider': 'claude-code',
           'recorded_at': '2026-11-01 05:35 UTC', 'runs': [run]}
    library = Library(tmp_path / ('reads-' + uuid.uuid4().hex), COURSE)
    library.root.mkdir(parents=True)
    library.file_of(ai_replay.course_key(SLOT, '')).write_bytes(gzip.compress(json.dumps(doc, ensure_ascii=False).encode('utf8')))
    return library, run


def _said_after_replay(tmp_path, tool_servers, library, run):
    wd, _ = workdir_for(tmp_path, run, tool_servers)
    c = Responses('replay', course=library).claim(cli=None, slot=SLOT, case='', attempt=(0, 0), request_key=None, step='인계안 작성',
                                                  provider='claude-code', source={}, accepted=lambda s: True, skills=[])
    events = play(c, wd)
    return c.notice(), events


def test_저장된_조회가_이_PC의_지금_값과_같으면_말이_없고_다르면_무엇이_다른지_말한다(tmp_path, tool_servers, pg_dsn):
    """교대 인계안의 저장된 응답은 뜬 PC의 조회 결과(「작업지시 두 건 배정됨」 · 재고 수치)를 그대로 적는데, 읽기 조회는 다시 부르지 않아 이 PC에
    없는 것을 사실로 적어도 아무 말이 없었다. 같은 조회를 이 PC의 실제 업무 DB에 다시 해 견준다. 행의 순서와 시각만 다른 것은 같은 것이다."""
    import psycopg
    stock, orders = _asked(tool_servers['enterprise'], STOCK_SQL), _asked(tool_servers['enterprise'], ORDERS_SQL)
    assert len(stock['rows']) >= 2
    at = stock['columns'].index('updated_at')
    # 뜬 PC가 지금 이 PC와 같은 상태였던 저장분: 값은 같고 행의 순서와 고친 시각만 다르다
    moved = [row[:at] + ['2026-11-01T05:02:42.691270Z'] + row[at + 1:] for row in reversed(stock['rows'])]
    library, run = _recording_of_reads(tmp_path, [(STOCK_SQL, dict(stock, rows=moved)), (ORDERS_SQL, orders)])
    said, events = _said_after_replay(tmp_path, tool_servers, library, run)
    assert said is None, said
    shown = [json.loads(ev.tool_output)['document']['rows'] for ev in events if ev.kind is ExecEventKind.TOOL_END]
    assert shown == [moved, orders['rows']]                    # 처리 과정에는 저장된 조회 결과 그대로(AI 글이 그 결과로 쓰였다)

    part, order = stock['rows'][0][0], 'WO-TEST-' + uuid.uuid4().hex[:8].upper()
    with psycopg.connect(pg_dsn, autocommit=True) as db:        # 이 PC의 업무 상태가 달라졌다: 정비 요청 한 건이 생기고 재고 한 줄이 바뀜
        db.execute("INSERT INTO ent.work_orders (id, asset, task, window_label) VALUES (%s, 'HYD-03', '시험 정비', '즉시')", (order,))
        db.execute('UPDATE ent.spare_stock SET on_hand = on_hand + 1 WHERE part_no = %s', (part,))
    try:
        said, _ = _said_after_replay(tmp_path, tool_servers, library, run)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as db:
            db.execute('DELETE FROM ent.work_orders WHERE id = %s', (order,))
            db.execute('UPDATE ent.spare_stock SET on_hand = on_hand - 1 WHERE part_no = %s', (part,))
    n = len(orders['rows'])
    assert said and said.startswith(ai_replay.REPLAY) and '결과 글 안의 조회 결과는 준비 당시 값입니다' in said, said
    assert '같은 조회 2개를 이 PC에서 다시 해 보니 2개가 지금 값과 다릅니다' in said, said
    # 조회를 가리키는 말: 데이터 원천의 이름(정본 hydcommon.data_sources.SOURCES — 데이터 원천 화면의 이름)이 앞, 표 이름은 괄호
    assert f'업무 DB 조회(ent.work_orders) — 준비 당시 {n}건 · 지금 {n + 1}건' in said, said
    assert f"업무 DB 조회(ent.spare_stock) — {len(stock['rows'])}건으로 같고 값이 다름" in said and 'updated_at 조회' not in said, said
    assert '견주지 못했습니다' not in said
    assert not FORBIDDEN.search(said) and not WORKER_TALK.search(said) and 'mcp__' not in said and '{' not in said and 'query' not in said, said


def test_이_PC에서_다시_조회하지_못한_조회는_다르다고_지어내지_않고_견주지_못했다고_말한다(tmp_path, tool_servers):
    """다시 부른 조회가 지금은 오류로 답하면(뜬 PC에는 있던 자료가 이 PC에 없음) 견줄 지금 값이 없다 — 「다르다」도 「같다」도 아니다."""
    stock = _asked(tool_servers['enterprise'], STOCK_SQL)
    gone = 'SELECT part_no, on_hand FROM ent.spare_stock_of_another_pc'
    library, run = _recording_of_reads(tmp_path, [(STOCK_SQL, stock), (gone, {'columns': ['part_no', 'on_hand'], 'rows': [['P-X', 1]]})])
    said, _ = _said_after_replay(tmp_path, tool_servers, library, run)
    assert said and said.startswith(ai_replay.REPLAY) and '조회 1개는 이 PC에서 다시 조회하지 못해 지금 값과 견주지 못했습니다' in said, said
    assert '다릅니다' not in said and '지금 0건' not in said, said
    assert not FORBIDDEN.search(said) and not WORKER_TALK.search(said), said


def test_교대_인계안의_조회가_이_PC의_지금과_다르면_멈추지_않고_처리_과정에_알린다(course, worker):
    """끝까지: 키 없는 PC의 교대 인수인계. 저장된 인계안은 정비 요청 두 건을 적는다. 이 PC의 정비 요청 수가 그와 달라도 인계안 작성은 제출까지 가고,
    처리 과정에 조회 결과가 준비 당시 값이라는 것과 지금 이 PC와 다른 조회가 남는다."""
    import psycopg
    from conftest import events_of, start_handover, task_of
    inst = start_handover(course.rt)
    assert worker('replay').poll_once() == 1
    task = task_of(course.rt, inst['proc_inst_id'], 'task:draft')
    assert task['status'] == 'SUBMITTED', events_of(course.rt, task['id'], 'error')
    with psycopg.connect(course.dsn) as db:
        now = db.execute("SELECT count(*) FROM ent.work_orders WHERE asset = 'HYD-01'").fetchone()[0]
    said = [e['data']['content'] for e in events_of(course.rt, task['id']) if (e.get('data') or {}).get('type') == 'notice']
    line = next((text for text in said if '조회 결과는 준비 당시 값' in text), None)
    assert line and line.startswith(ai_replay.REPLAY), said
    assert ('업무 DB 조회(ent.work_orders) — ' + (f'준비 당시 2건 · 지금 {now}건' if now != 2 else '2건으로 같고 값이 다름')) in line, line
    assert '시계열 DB 조회(public.tag_1s) — ' in line, line
    assert not FORBIDDEN.search(line) and not WORKER_TALK.search(line) and 'mcp__' not in line and '{' not in line, line


def test_녹화_열쇠는_흐름_id_와_작업_이름이_아니라_수업_자리다():
    """B-02: 학생이 가져온 교대 흐름(ShiftHandover)과 제공 흐름(shift_handover)의 첫 초안 자리는 같은 녹화를 쓴다."""
    slots = {course_policy.AI_SLOTS[(d, a)] for d, a in (('ShiftHandover', 'task_draft'), ('shift_handover', 'task:draft'))}
    assert slots == {'handover/draft-1'}
    assert COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))['step'] == '인계안 작성'


# ---------------------------------------------------------------- 녹화 밖 행동 = 쉬운 말 실패
@pytest.mark.parametrize('slot, case, attempt, has', [
    ('handover/draft-3', '', (0, 0), '보완 요청은 1번까지'),
    ('c3_cooling/T_agent', 'COOLER_DEGRADATION', (0, 1), '다시 평가'),
    ('c3_cooling/T_agent', 'COOLER_DEGRADATION', (1, 1), '다시 평가'),
    ('c3_cooling/T_agent', 'PUMP_LEAK', (0, 0), '이 경보로 시작한 처리 건'),
    (None, '', (0, 0), '재생 모드에서 진행되는 AI 단계'),
    ('question', ai_replay.question_case('다른 질문'), (0, 0), '준비된 질문에만'),
], ids=['교대 보완 2', '보류 뒤 재평가', '다시 수행 뒤의 재평가', '저장된 응답이 없는 경보 종류', '저장된 응답이 없는 단계', '준비되지 않은 질문'])
def test_녹화에_없는_행동은_무엇이_없고_무엇을_하면_되는지_말하고_멈춘다(tmp_path, slot, case, attempt, has):
    """#9 · #23: 「API 키를 넣으면」(키 없는 학생이 할 수 없는 안내) · 경보 코드 · 「시스템 오류」 없이. 작업자끼리 쓰는 말(강사 · 녹화 · 수업 ·
    실습 — student_words.WORKER_TALK)도 없이: 무엇이 안 되고 무엇이 되는지를 대상으로 말한다."""
    with pytest.raises(NotRecorded) as caught:
        play(claim(slot=slot, case=case, attempt=attempt, step='인계안 작성 · 보완 2'), tmp_path)
    said = str(caught.value)
    assert has in said and said.startswith(ai_replay.REPLAY), said
    assert not FORBIDDEN.search(said) and not WORKER_TALK.search(said), said


def test_다시_수행한_단계는_저장된_첫_실행을_이_처리_건의_값으로_다시_낸다(tmp_path, tool_servers):
    """재생 모드의 [다시 수행]은 「재작업으로 다시 하는 것을 지원하지 않습니다 … 새 처리 건으로」로 멈췄다 — AI 단계가 한 번 실패한 학생은
    그 건을 다시 해 볼 길이 없었다. 다시 수행은 같은 단계를 같은 입력으로 새로 하는 것이라(새 작업 행 — 사유는 AI 입력이 아니다) 첫 실행의
    저장된 응답이 그 답이다. 차례가 저장돼 있으면(재작업 세대를 따로 뜬 녹화) 그 실행이 앞선다."""
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    wd, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers)
    first = play(claim(slot='handover/draft-1', step=doc['step']), wd)
    wd2, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers)
    again = play(claim(slot='handover/draft-1', attempt=(2, 0), step=doc['step']), wd2)
    assert [(e.kind, e.tool) for e in again] == [(e.kind, e.tool) for e in first] and (wd2 / 'output' / 'result.json').exists()
    own = dict(doc, runs=[doc['runs'][0], dict(doc['runs'][0], attempt={'generation': 2, 'reassessment': 0}, result_file='{"draft": "둘째 차수의 저장된 응답"}')])
    lib = Library(tmp_path / 'with-rework-run', COURSE)
    lib.root.mkdir()
    lib.file_of(ai_replay.course_key('handover/draft-1', '')).write_bytes(gzip.compress(json.dumps(own, ensure_ascii=False).encode('utf8')))
    wd3, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers)
    play(claim(slot='handover/draft-1', attempt=(2, 0), step=doc['step'], course=lib), wd3)
    assert '둘째 차수의 저장된 응답' in (wd3 / 'output' / 'result.json').read_text(encoding='utf8')


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
    assert 'hyd-dmn' in str(caught.value) and not WORKER_TALK.search(str(caught.value)), str(caught.value)
    assert not (wd / 'output' / 'result.json').exists()


class _Forward:
    """닫혀 있던 주소에 뒤늦게 뜨는 서버의 대역: 받은 연결을 실제 도구 서버로 그대로 넘긴다(TCP)."""
    def __init__(self, port, target):
        import socket
        import socketserver
        import threading
        from urllib.parse import urlsplit
        to = urlsplit(target)

        class Pipe(socketserver.BaseRequestHandler):
            def handle(self):
                with socket.create_connection((to.hostname, to.port)) as far:
                    def pump(src, dst):
                        try:
                            while data := src.recv(65536):
                                dst.sendall(data)
                        except OSError:
                            pass
                        finally:
                            try:
                                dst.shutdown(socket.SHUT_WR)
                            except OSError:
                                pass
                    back = threading.Thread(target=pump, args=(far, self.request), daemon=True)
                    back.start()
                    pump(self.request, far)
                    back.join(5)

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.server = socketserver.ThreadingTCPServer(('127.0.0.1', port), Pipe)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _closed_port():
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def test_쓰기_도구_서버가_잠깐_닿지_않다가_뜨면_같은_실행_안에서_다시_연결해_진행한다(tmp_path, tool_servers, monkeypatch):
    """잠깐의 연결 실패 한 번이 그 단계의 실패로 굳었다(재생 모드는 다시 수행도 막혀 있었다). 요청이 서버에 가지 않은 것이 분명한 연결
    실패(연결 거부)는 정해진 간격으로 다시 본다 — 그 사이 서버가 뜬다."""
    from urllib.parse import urlsplit
    real = tool_servers['hyd-dmn']
    port = _closed_port()
    doc = COURSE_LIB.load(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'))
    wd, _ = workdir_for(tmp_path, doc['runs'][0], dict(tool_servers, **{'hyd-dmn': f'http://127.0.0.1:{port}{urlsplit(real).path}'}))
    up = []
    monkeypatch.setattr(ai_replay, '_wait', lambda seconds, check_stop: up or up.append(_Forward(port, real)))
    try:
        tools = ai_replay._Tools(wd, doc['step'])
        assert tools.writes('hyd-dmn', 'submit_decision') is True and tools.writes('hyd-dmn', 'diagnose') is False
    finally:
        for server in up:
            server.close()
    assert up, '첫 연결이 실패하지 않았다 — 이 시험이 보려는 길이 아니다'


def test_쓰기_도구_서버에_끝내_닿지_못하면_그_까닭으로_멈추고_학생_문장에_내부_이름을_싣지_않는다(tmp_path, tool_servers, monkeypatch):
    doc = COURSE_LIB.load(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'))
    wd, _ = workdir_for(tmp_path, doc['runs'][0], dict(tool_servers, **{'hyd-dmn': f'http://127.0.0.1:{_closed_port()}/mcp'}))
    monkeypatch.setattr(ai_replay, 'WRITE_RETRY_WAITS_S', (0.05, 0.05))
    with pytest.raises(ai_replay.WriteFailed) as caught:
        play(claim(slot='c3_cooling/T_agent', case='COOLER_DEGRADATION', step=doc['step']), wd)
    said, raw = str(caught.value), caught.value.raw
    assert '닿지 못해' in said and '다시 수행' in said and doc['step'] in said, said
    assert 'hyd-dmn' not in said and '{' not in said and not WORKER_TALK.search(said) and not FORBIDDEN.search(said), said
    assert 'hyd-dmn' in raw, raw
    assert not (wd / 'output' / 'result.json').exists()


def test_다시_시도할_오류가_아닌_거절은_기다리지_않고_바로_그_까닭으로_멈춘다(world, tmp_path, tool_servers, monkeypatch):
    """이 PC 처리 엔진에 없는 처리 건의 판단 등록은 거절된다(처리 범위가 다름) — 다시 불러도 같은 답이라 기다리지 않는다. 학생 문장에는 도구의
    내부 이름 · 응답 원문(JSON)이 없고 원문 칸에 남는다.
    판단 서비스가 판단을 끝까지 계산해 처리 엔진의 거절까지 가도록 시작 상태를 이 시험이 만든다(world: 수업 지식이 든 그래프 · 켜진 처리 엔진,
    쿨러가 오염돼 값을 보고하는 HYD-01). 전에는 앞 시험이 남긴 상태에 기댔다 — 혼자 돌리면 그래프에 수업 지식이 없어 「진단 지식에 없는 원인」
    으로, 묶음에서는 설비 값이 끊겨 「값을 아직 받지 못함」(다시 시도하는 것이 맞는 오류)으로 끝나 이 시험이 보려는 거절이 아니었다."""
    doc = COURSE_LIB.load(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'))
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.reported_for('HYD-01')
    wd, _ = workdir_for(tmp_path, doc['runs'][0], tool_servers)

    def no_wait(seconds, check_stop):
        raise AssertionError('다시 시도할 오류가 아닌데 기다렸다')
    monkeypatch.setattr(ai_replay, '_wait', no_wait)
    with world.reporting('HYD-01'), pytest.raises(ai_replay.WriteFailed) as caught:
        play(claim(slot='c3_cooling/T_agent', case='COOLER_DEGRADATION', step=doc['step']), wd)
    said, raw = str(caught.value), caught.value.raw
    assert '등록하지 못했습니다' in said and doc['step'] in said, said
    assert all(word not in said for word in ('hyd-dmn', 'submit_decision', 'error_kind', '{', '"result"')), said
    assert not WORKER_TALK.search(said) and not FORBIDDEN.search(said), said
    assert 'hyd-dmn/submit_decision' in raw and 'error_kind' in raw, raw


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


def test_저장소_녹화에_나오는_사람은_이_시스템의_담당자뿐이다():
    """재생은 녹화의 도구 결과 · 입력을 화면에 그대로 낸다. 지금은 없는 직원(사람 고르기를 없애기 전의 여섯)이 남아 있으면 키 없는 PC 의
    처리 기록에 없는 사람이 「요청자」로 보인다(전수검사 12 — 네 자리). 시작 버튼이 넣는 이름 · id(requested_by · requested_user)도 같다."""
    from conftest import OPERATOR
    for path in sorted(Path(REPLAY_DIR).glob('*.json.gz')):
        text = gzip.decompress(path.read_bytes()).decode('utf8')
        assert set(re.findall(r'user:[a-z][a-z0-9-]*', text)) <= {OPERATOR['by']}, path.name
        for run in json.loads(text)['runs']:
            evidence = ((run['context'].get('inputs') or {}).get('alert') or {}).get('evidence') or {}
            if 'requested_by' in evidence:
                assert (evidence['requested_by'], evidence['requested_user']) == ('담당자', OPERATOR['by']), path.name
                assert re.findall(r'requested_by\\*": \\*"([^"\\]+)', text) and set(re.findall(r'requested_by\\*": \\*"([^"\\]+)', text)) == {'담당자'}, path.name


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
