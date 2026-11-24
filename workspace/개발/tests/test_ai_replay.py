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
from worker import ai_replay, result_check
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
        status, out = world.api('POST', f'/api/scenario/{key}/start', {'by': 'user:me', 'role': 'role:operator'}, source_loop=True)
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


def test_녹화와_수량만_다른_지금_계산은_멈추지_않고_어느_값이_판단_때_값이고_지금_값은_무엇인지_처리_과정에_말한다(world):
    """전수검사 04-D3: 재고 보충 녹화는 정기 정비를 먼저 승인한 뒤(예약 3 · 필요 7개 · 총비용 420)에 떠졌다. 시작 상태(예약 2 · 필요 6개)에서
    재생하면 AI 설명은 7개 · 420만 원, 승인 카드는 6개 · 360만 원인데 아무 말이 없었다. 권장 조치는 같으므로 멈추지 않고 그 차이를 말한다.
    2026-11-20: 그 알림이 「AI 키가 없을 때 쓰는 재생 모드에서는 … 준비된 것을 그대로 보입니다 … 준비 당시 값」으로 재생 사정을 밝혔다 — 막힌 행동을
    한 것이 아니므로 재생 모드 · 준비된 글이라는 말 없이 사실만 말한다(글 속 값은 판단 때 값이고 지금 값은 무엇인가)."""
    pid, did = _scenario('C')(world)
    card = next(o for o in world.main.book[did]['options'] if o['id'] == world.main.book[did]['recommended'])
    now = card['economicComparison']
    assert (now['quantity'], now['total_cost']) == (6, 360)                                 # 이 PC의 지금 계산(시작 상태)
    notices = [e['data'] for e in world.events(pid) if (e.get('data') or {}).get('type') == 'notice']
    said = [d['content'] for d in notices]
    found = next((d for d in notices if '판단 때 값' in d['content']), None)
    line = found and found['content']
    assert line and line.startswith('AI 설명 속 값 일부는 판단 때 값입니다 — 판단 때 → 지금 값: ') and '수량 7 → 6개' in line and '비교 총비용 420 → 360만 원' in line, said
    assert '재생' not in line and '준비' not in line, line
    assert '「순정(OEM) 공급사 표준 발주」' in line and not FORBIDDEN.search(line) and '강사' not in line and '녹화' not in line
    # 화면이 문장을 읽어 가르지 않게 종류를 싣는다: 묶음 종류와 문장마다의 종류, 문장을 이으면 content 다. 기본 제공 구성 그대로인 실행이라 스킬 안내는 없다
    kinds = [part['kind'] for part in found['parts']]
    assert found['kind'] == 'replay' and kinds[0] == 'values_differ' and set(kinds) <= set(ai_replay.NOTICE_KINDS) - {'skills'}, found
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
    결과는 그 파일의 지금 본문으로 보인다. 작업 폴더에 없는 스킬(학생이 뗀 스킬)이나 일부만 읽은 호출은 저장된 결과 그대로다.
    2026-11-23 저장분은 그 스킬을 Read 가 아니라 Skill 도구(`hyd-course-skills:cooling-emergency-response`)로 연다 — 본문이 결과로 나오지 않는
    호출이다. 그래서 Read 로 옛 본문을 읽은 실행은 저장분의 그 호출을 옛 본문을 읽은 Read 로 바꾼 녹화 묶음으로 세운다."""
    old_body = '0\t---\n1\tname: cooling-emergency-response\n2\tdescription: 쿨러 과열 경보 — 원인 진단 · 냉각 조치 카드 (시나리오 A)\n3\t---\n4\t\n5\t# 옛 제목'

    def read_instead_of_skill_tool(run):
        ids = set()
        for e in run['events']:
            if e['kind'] == 'tool_start' and e.get('tool') == 'Skill' and 'cooling-emergency-response' in json.dumps(e.get('tool_input')):
                ids.add(e['tool_use_id'])
                e.update(tool='Read', tool_input={'file_path': '/workspace/hyd/rec/.claude/skills/cooling-emergency-response/SKILL.md',
                                                  'offset': 0, 'limit': 2000})
            elif e['kind'] == 'tool_end' and e.get('tool_use_id') in ids:
                e.update(tool='Read', text=old_body, tool_output=old_body)
                (run.get('tool_outputs_full') or {}).pop(e['tool_use_id'], None)
        assert ids, '냉각 저장분에 그 스킬을 여는 호출이 없다'
    made = _replay_recorded_edited(tmp_path, 'c3_cooling/T_agent', read_instead_of_skill_tool)
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    tags = world.plant.tags('HYD-01')
    _, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01', ts1=tags['TS1'], ce=tags['CE'])
    world.report()
    with world.reporting('HYD-01'):
        assert world.runner('replay', replay_dir=made).poll_once() == 1
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


def _replay_recorded_edited(tmp_path, slot, edit):
    """시험이 만든 녹화 묶음: 저장소 녹화를 복사하되 그 자리 녹화의 첫 실행을 edit(run)으로 고친다."""
    import shutil
    out = tmp_path / 'replay-edited'
    shutil.copytree(REPLAY_DIR, out)
    doc = next(d for key, d in docs().items() if key.startswith(slot + '|'))
    edit(doc['runs'][0])
    Library(out, COURSE).file_of(ai_replay.course_key(doc['slot'], doc['case'])).write_bytes(gzip.compress(json.dumps(doc, ensure_ascii=False).encode('utf8')))
    return out


def _replay_recorded_under_another_state(tmp_path, slot, change):
    """시험이 만든 녹화 묶음: 그 자리의 녹화가 등록했던 판단 문서만 바꾼다(change) — 다른 설비 · 업무 상태에서 뜬 녹화의 대역."""
    def edit(run):
        for e in run['events']:
            if e['kind'] == 'tool_end' and (e.get('tool') or '').endswith(('submit_decision', 'submit_purchase')) and not e.get('is_error'):
                full = run.setdefault('tool_outputs_full', {})
                body = ai_replay._as_json(full.get(e['tool_use_id']) or e.get('tool_output'))
                if ai_replay._failed(body):
                    continue
                change(body['document'])
                full[e['tool_use_id']] = json.dumps(body, ensure_ascii=False)
    return _replay_recorded_edited(tmp_path, slot, edit)


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
    with world.reporting('HYD-01'):             # 설비는 1초마다 보고한다 — 판단 등록이 그 자리에서 다시 하는 원인 진단의 관측 구간이 비지 않게
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
    # 조회 말(읽기 조회 견주기)은 이 PC의 지식 · 업무 상태에 따라 붙는다 — 지식 지도 조회도 견준다(아래 시험). 여기서는 스킬 말만 본다


def test_질문_답이_읽은_지식_지도를_이_PC에서_다시_조회해_같으면_말이_없고_비우면_무엇이_다른지_말한다(world, course_graph, tool_servers):
    """질문하기의 준비된 답은 그 답을 만들 때 읽은 지식 지도 조회 결과를 사실로 적는다. 전에는 표 꼴 조회만 견주어, 이 PC에서 HM-8을 비운
    뒤 물어도 이 PC에 없는 절차 번호를 인용한 답이 아무 말 없이 나갔다(2026-11-22 조사). 시작이 끝난 PC(세 문서 적재)에서는 같은 조회가
    같으므로 말이 없고(PC마다 다른 문서 판본 id · 테넌트 해시는 견주지 않는다), HM-8을 비우면 어느 조회가 지금 몇 건인지 말한다."""
    import class_knowledge as ck
    doc = next(d for key, d in docs().items() if key.startswith('question|') and 'HM-8' in d['case'])

    def asked():
        wd, _ = workdir_for(world.tmp / ('q-' + uuid.uuid4().hex[:6]), doc['runs'][0], tool_servers)
        c = Responses('replay', course=COURSE_LIB).claim(cli=None, slot='question', case=doc['case'], attempt=(0, 0), request_key=None,
                                                        step=doc['step'], provider='claude-code', source={}, accepted=lambda s: True, skills=[],
                                                        skills_changed=False)
        play(c, wd)
        return c.notice() or ''

    said = asked()
    assert '조회 결과' not in said, said
    hm8 = next(i for i in ck.reviewed() if i['doc'] == 'HM-8')
    status, rows = world.api('GET', '/api/kg/manuals')
    current = next(r for r in rows if r.get('current') and r['filename'] == hm8['filename'])
    status, out = world.api('POST', f"/api/kg/manuals/batches/{current['batch']}/rollback", {'by': 'user:me'})
    assert status == 200, out
    said = asked()
    assert said.startswith('결과 글 안의 조회 결과는 판단 때 값입니다') and '지식 지도 조회(KnowledgeSource · ManualSection' in said, said
    assert '지금 0건' in said and 'neo4j' not in said and 'MATCH' not in said and not FORBIDDEN.search(said), said


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
        assert '재생' not in text and '준비' not in text, text          # 막힌 행동이 아니다 — 재생 사정을 말하지 않고 사실만(2026-11-20)
        assert f'AI 설명은 지금 넣은 입력과 다른 입력을 두고 쓴 글입니다: 글이 쓰인 때 「{recorded}」 · 지금 「{MEMO}」.' in text, text
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
    assert said and said.startswith('결과 글 안의 조회 결과는 판단 때 값입니다') and '재생' not in said and '준비' not in said, said
    assert '같은 조회 2개를 이 PC에서 다시 해 보니 2개가 지금 값과 다릅니다' in said, said
    # 조회를 가리키는 말: 데이터 원천의 이름(정본 hydcommon.data_sources.SOURCES — 데이터 원천 화면의 이름)이 앞, 표 이름은 괄호
    assert f'업무 DB 조회(ent.work_orders) — 판단 때 {n}건 · 지금 {n + 1}건' in said, said
    assert f"업무 DB 조회(ent.spare_stock) — {len(stock['rows'])}건으로 같고 값이 다름" in said and 'updated_at 조회' not in said, said
    assert '견주지 못했습니다' not in said
    assert not FORBIDDEN.search(said) and not WORKER_TALK.search(said) and 'mcp__' not in said and '{' not in said and 'query' not in said, said


def test_전문_검색의_관련도_점수만_다른_조회는_같다고_보고_찾은_항목이_다르면_다르다고_본다(seeded_graph):
    """질문하기의 AI는 이름 전문 검색(db.index.fulltext.queryNodes — 결과에 관련도 score)을 자주 쓴다. 점수는 찾은 항목이 같아도 그 그래프에 든 것
    전체를 따라 달라져, 학생 PC마다 「값이 다름」 알림이 늘 붙었다(2026-11-23 실측: 질문 「고객센터 전화번호」의 검색 두 개 — 같은 28건 · 같은 이름,
    점수만 다름). 실제 그래프의 같은 검색을 두 상태로: 검색어와 상관없는 지식 노드가 늘면 점수만 바뀌고(같다고 봄), 찾은 항목의 이름이 바뀌면 다르다."""
    import time
    query = "CALL db.index.fulltext.queryNodes('ont_names', '쿨러 팬 모터') YIELD node, score RETURN labels(node) AS labels, node.id AS id, node.name AS name, score"
    args = {'query': query}
    table = lambda: ai_replay._table(json.dumps({'result': json.dumps(seeded_graph.query(query), ensure_ascii=False)}, ensure_ascii=False))
    before = table()
    assert before and 'score' in before[0] and len(before[1]) >= 3, before
    seeded_graph.query("UNWIND range(1, 40) AS i CREATE (:Role {id: 'role:zz-score-' + i, name: '야간 근무 기록 담당 ' + i})")
    deadline, after = time.monotonic() + 60, before
    while time.monotonic() < deadline and ai_replay.read_gap(before, after) is None:      # 전문 색인은 쓰기 뒤 잠시 뒤에 바뀐다
        time.sleep(1)
        after = table()
    ranked = ai_replay.ranked_columns(args)
    assert ranked == {'score'}
    assert ai_replay.read_gap(before, after) == (len(before[1]), len(before[1])), '검색어와 상관없는 노드가 늘어도 점수가 바뀌지 않았다 — 이 시험의 전제가 틀렸다'
    assert ai_replay.read_gap(before, after, ranked) is None                                       # 같은 항목 · 같은 이름 — 알림 없음
    name = next(r for r in seeded_graph.query(query) if r['name'])
    seeded_graph.query('MATCH (n {id: $id}) SET n.name = n.name + " (바뀜)"', id=name['id'])
    deadline, renamed = time.monotonic() + 60, after
    while time.monotonic() < deadline and ai_replay.read_gap(after, renamed, ranked) is None:
        time.sleep(1)
        renamed = table()
    assert ai_replay.read_gap(after, renamed, ranked) == (len(after[1]), len(renamed[1]))          # 찾은 항목의 이름이 바뀜 — 알림
    # 점수를 다른 이름으로 바꿔 부른 검색도 그 이름의 칸을 뺀다 — 검색이 아닌 조회의 score 칸은 그대로 견준다
    assert ai_replay.ranked_columns({'query': "CALL db.index.fulltext.queryNodes('ont_names', $q) YIELD node, score RETURN node.id AS id, score AS relevance"}) == {'score', 'relevance'}
    assert ai_replay.ranked_columns({'query': 'MATCH (n:Measure) RETURN n.id AS id, n.score AS score'}) == set()


def test_이_PC에서_다시_조회하지_못한_조회는_다르다고_지어내지_않고_견주지_못했다고_말한다(tmp_path, tool_servers):
    """다시 부른 조회가 지금은 오류로 답하면(뜬 PC에는 있던 자료가 이 PC에 없음) 견줄 지금 값이 없다 — 「다르다」도 「같다」도 아니다."""
    stock = _asked(tool_servers['enterprise'], STOCK_SQL)
    gone = 'SELECT part_no, on_hand FROM ent.spare_stock_of_another_pc'
    library, run = _recording_of_reads(tmp_path, [(STOCK_SQL, stock), (gone, {'columns': ['part_no', 'on_hand'], 'rows': [['P-X', 1]]})])
    said, _ = _said_after_replay(tmp_path, tool_servers, library, run)
    assert said and said.startswith('결과 글 안의 조회 결과는 판단 때 값입니다') and '조회 1개는 이 PC에서 다시 조회하지 못해 지금 값과 견주지 못했습니다' in said, said
    assert '다릅니다' not in said and '지금 0건' not in said, said
    assert not FORBIDDEN.search(said) and not WORKER_TALK.search(said), said


def test_교대_인계안의_조회가_이_PC의_지금과_다르면_멈추지_않고_처리_과정에_알린다(course, worker):
    """끝까지: 키 없는 PC의 교대 인수인계. 저장된 인계안은 정비 요청 두 건을 적는다. 이 PC의 정비 요청 수가 그와 달라도 인계안 작성은 제출까지 가고,
    처리 과정에 조회 결과가 판단 때 값이라는 것과 지금 이 PC와 다른 조회가 남는다(재생 모드 · 준비된 글이라는 말 없이 — 2026-11-20)."""
    import psycopg
    from conftest import events_of, start_handover, task_of
    inst = start_handover(course.rt)
    assert worker('replay').poll_once() == 1
    task = task_of(course.rt, inst['proc_inst_id'], 'task:draft')
    assert task['status'] == 'SUBMITTED', events_of(course.rt, task['id'], 'error')
    with psycopg.connect(course.dsn) as db:
        now = db.execute("SELECT count(*) FROM ent.work_orders WHERE asset = 'HYD-01'").fetchone()[0]
    said = [e['data']['content'] for e in events_of(course.rt, task['id']) if (e.get('data') or {}).get('type') == 'notice']
    line = next((text for text in said if '조회 결과는 판단 때 값' in text), None)
    assert line and '재생' not in line and '준비' not in line, said
    assert ('업무 DB 조회(ent.work_orders) — ' + (f'판단 때 2건 · 지금 {now}건' if now != 2 else '2건으로 같고 값이 다름')) in line, line
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
LIVE_SESSION = 'live-session-now'


def _live_run(tools=()):
    """키 있는 PC 의 실제 CLI 한 번 — tools: 그 실행이 부른 MCP 도구 이름(mcp__<서버>__<도구>)."""
    def cli(provider, request, env, check_stop=None):
        for n, tool in enumerate(tools):
            yield ExecEvent(kind=ExecEventKind.TOOL_START, tool=tool, tool_use_id=f'u{n}', tool_input={}, session_id='s1')
            yield ExecEvent(kind=ExecEventKind.TOOL_END, tool=tool, tool_use_id=f'u{n}', tool_output='{"result":"ok","document":{}}', session_id='s1')
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text='문서의 절차를 정리했습니다.', session_id='s1')
        yield ExecEvent(kind=ExecEventKind.RESULT, text='{"ok": true}', session_id='s1')
    return cli


def _task_folder(path):
    """Runner 가 실행 전에 쓰는 작업 기록(workspace.provision 의 context/task.json)이 있는 작업 폴더 — claim() 의 작업(todo_id 't')이다.
    저장기 · 재생기는 그 기록으로 처리 건의 값을 받아 두고 견준다(_task_context — 기록이 없으면 실패한다)."""
    (path / 'context').mkdir(parents=True, exist_ok=True)
    task = {'id': 't', 'proc_inst_id': 'shift_handover.t', 'process_scope': {'tenant': 'hyd', 'instance': 'shift_handover.t', 'workitem': 't'},
            'query': '지시'}
    (path / 'context' / 'task.json').write_text(json.dumps(task, ensure_ascii=False), encoding='utf8')
    return path


def _cached(tmp_path, tools=(), slot='handover/draft-1'):
    """실제 저장 길(실제 CLI 실행 → 제출로 끝난 점유 → keep)로 만든 같은 요청 저장."""
    cache = Library(tmp_path / 'cache', REUSE)
    c = claim('live', slot=slot, cache=cache, cli=_live_run(tools))
    play(c, _task_folder(tmp_path))
    c.keep('submitted', [])
    return cache


def test_같은_설정_같은_입력이면_앞선_실행을_다시_쓰고_실제_CLI_를_부르지_않는다(tmp_path):
    """키 있는 PC: 같은 설정 · 같은 입력이면 앞선 실행을 다시 쓴다(새로 추론하지 않음) — 결과가 설정 · 입력만으로 정해지는 실행(도구 서버를 부르지
    않은 실행)이다. 화면에 남는 한 줄은 저장 사정(「다시 썼습니다 · 새로 추론하지 않음 · 언제 실행」)이 아니라 사실과 할 일이다(2026-11-20)."""
    cache = _cached(tmp_path)
    assert cache.file_of('k' * 32).exists()
    c = claim('live', slot='handover/draft-1', cache=cache, cli=lambda *a, **k: pytest.fail('실제 CLI 를 불렀다'))
    events = play(c, tmp_path)
    assert events[0].session_id.startswith(REUSE) and [e.text for e in events if e.kind == ExecEventKind.RESULT] == ['{"ok": true}']
    said = c.notice()
    assert said == '같은 설정 · 같은 입력이라 앞선 실행 결과와 같습니다. 새로 추론하게 하려면 입력이나 에이전트 설정을 바꿔 실행하세요.', said


@pytest.mark.parametrize('slot, tools, kept', [
    ('c3_cooling/T_agent', ['mcp__hyd-dmn__diagnose', 'mcp__hyd-dmn__submit_decision'], True),
    ('handover/draft-1', ['mcp__enterprise__query'], True),
    ('question', ['mcp__hyd-question__kg_query'], False),
    (None, ['mcp__enterprise__query'], False),
    (None, [f'mcp__{result_check.SERVER}__{result_check.TOOL}'], False),
    (None, [], False),
], ids=['수업 판단 자리', '수업 인계안 자리', '질문 자리', '학생 흐름 · PBL 의 조회', '학생 흐름 · PBL 의 문법 검사만', '학생 흐름 · PBL 의 도구 없음'])
def test_같은_요청_저장은_수업_녹화와_같은_수업_AI_자리에서만_남고_그_밖은_늘_실제_AI다(tmp_path, slot, tools, kept):
    """사용자 2026-11-22 「재생모드는 수업한정인거고, 캐시랑 재생모드랑 … 뿌리는 같다」 · 탐사 N2: 같은 요청 저장의 열쇠는 설정 · 입력뿐이고 도구가 읽는
    지식 · 업무 · 설비 상태는 열쇠에 없다. 수업 녹화와 같은 장치라 같은 곳(서버가 준 수업 AI 자리 — PBL 단계에서는 자리가 없다)에서만 쓰고, 다시 쓸 때도
    수업 녹화와 같은 가드(쓰기 도구를 이 PC에서 다시 불러 판단을 견줌)를 지난다. 학생 흐름 · PBL 단계의 AI 단계는 결과가 같은 입력만으로 정해져도
    남기지 않는다 — 실제 AI 로 돈다. 질문 자리는 G1-09 그대로."""
    cache = _cached(tmp_path, tools, slot=slot)
    assert cache.file_of('k' * 32).exists() is kept
    if not kept:
        out = play(claim('live', slot=slot, cache=cache, cli=_real_cli()), tmp_path)
        assert [e.session_id for e in out if e.kind == ExecEventKind.RESULT] == [LIVE_SESSION]      # 같은 요청도 실제 AI 가 새로 답한다


def test_다시_쓰던_같은_요청_저장의_판단이_지금_계산과_다르면_그_저장을_버리고_다음_실행이_실제_AI라고_말한다(tmp_path):
    """탐사 N2: 키 있는 PC에서 지식을 고친 뒤 [다시 수행]하면 같은 요청 저장이 맞아 앞선 판단 설명이 그대로 나왔고, 다시 부른 판단 등록이 다른 조치를
    권해도 멈추지 않았다(수업 녹화에서만 멈췄다). 같은 규칙으로 멈추되, 키 있는 PC의 할 일은 다음 실행이 실제 AI 로 새로 판단하는 것이다."""
    cache = _cached(tmp_path, [], slot='c3_cooling/T_agent')
    gap = {'changed': ['권장 조치가 준비된 판단은 「팬 최대 운전」인데 지금 계산은 「쿨러 핀 세척」입니다'], 'numbers': [], 'rules': [],
           'gone': ['조치 후보 「팬 최대 운전」'], 'judged': True, 'same_knowledge': False}   # decision_gap 의 꼴
    with pytest.raises(ai_replay.ReuseDropped) as e:
        ai_replay.decision_changed(cache, 'k' * 32, '원인 진단 · 냉각 조치 제안', gap, 'DEC-1')
    said = str(e.value)
    assert not cache.file_of('k' * 32).exists()                      # 다음 [다시 수행]은 저장이 없어 실제 AI
    assert '앞서 실행한 판단이 지금과 맞지 않습니다' in said and '「쿨러 핀 세척」' in said and '지금 지식에 없습니다' in said and '실제 AI로 새로 판단' in said, said
    assert '판단 DEC-1은 승인 단계로 넘어가지 않습니다' in said and '앞선 판단 때와 다릅니다' not in said, said      # 없어진 지식을 말하면 지문 말은 겹쳐 쓰지 않는다
    assert ai_replay.REPLAY not in said and not FORBIDDEN.search(said) and '녹화' not in said
    with pytest.raises(NotRecorded) as course:                       # 수업 녹화(키 없는 PC)는 재생 모드의 할 일로 멈추고 녹화는 지우지 않는다
        ai_replay.decision_changed(COURSE_LIB, ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION'), '원인 진단 · 냉각 조치 제안', gap, None)
    assert str(course.value).startswith(ai_replay.REPLAY) and COURSE_LIB.file_of(ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION')).exists()


def test_같은_요청_저장은_규정_판정이나_지식이_달라진_판단을_다시_쓰지_않고_버리며_수치만_다르면_그_사실을_말한다(tmp_path):
    """2026-11-24 검토 가-3: 키 있는 PC에서 규칙을 뺀 문서를 다시 적재하고 [다시 수행]하면, 권장안이 같아 같은 요청 저장이 다시 쓰였다 — 승인 카드에는
    그 규칙이 없는데 AI 설명은 그 규칙을 말했고, 화면은 「같은 설정 · 같은 입력이라 앞선 실행 결과와 같습니다」라고만 했다(지식은 요청 열쇠에 없다).
    실제 저장분의 판단 기록으로: 규정 판정만 달라진 지금 계산 → 저장을 버리고 다음 실행이 실제 AI 라고 말한다. 같은 판단 → 그대로 쓴다.
    수업 녹화(키 없는 PC)는 새로 판단할 길이 없어 같은 차이를 알리며 쓴다. 다시 쓸 때 수치만 다르면 그 사실을 숨기지 않는다."""
    import copy
    old, seen = _recorded('c3_cooling/T_agent', 'submit_decision'), _recorded('c3_cooling/T_agent', 'evaluate_cards')
    same = _now_view(seen, keep=[o['id'] for o in ai_replay._created(seen)['options']])
    warned = copy.deepcopy(same)
    card = next(o for o in warned['document']['options'] if o['id'] == warned['document']['recommended'])
    card['warnings'] = [*(card.get('warnings') or []), {'rule': 'rule:test-warning', 'annotation': '시험 경고 — 지금 지식에만 있는 규칙'}]
    # 지금 지식의 규칙 목록 = 지금 계산에 걸린 규칙(그 밖의 차이 없이). 지금 판단 서비스는 지식 지문도 싣는다(dmn-mcp agent_view) — 같은 지식이면
    # 저장분과 같은 지문, 규칙이 하나 더 있는 지식이면 다른 지문
    digest = ai_replay._created(old)['knowledge']['digest']
    for doc, mark in ((same, digest), (warned, digest[::-1])):
        doc['document']['knowledge']['rules'] = sorted({r['rule'] for o in doc['document']['options'] for k in ai_replay.RULE_KINDS for r in o.get(k) or []})
        doc['document']['knowledge']['digest'] = mark
    gap_same, gap_rules = ai_replay.decision_gap(old, same, seen), ai_replay.decision_gap(old, warned, seen)
    assert not gap_same['changed'] and not gap_same['rules'] and not gap_rules['changed'] and gap_rules['rules'], (gap_same, gap_rules)
    step = '원인 진단 · 냉각 조치 제안'
    cache = _cached(tmp_path, [], slot='c3_cooling/T_agent')
    ai_replay.check_decision(cache, 'k' * 32, step, gap_same, None)                     # 같은 판단 — 다시 쓴다
    assert cache.file_of('k' * 32).exists()
    with pytest.raises(ai_replay.ReuseDropped) as e:
        ai_replay.check_decision(cache, 'k' * 32, step, gap_rules, 'DEC-1')
    said = str(e.value)
    assert not cache.file_of('k' * 32).exists() and '시험 경고' in said and '실제 AI로 새로 판단' in said, said
    key = ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION')
    ai_replay.check_decision(COURSE_LIB, key, step, gap_rules, None)                    # 수업 녹화는 멈추지 않고(새로 판단할 길이 없다) 알린다
    shown = ai_replay.notice({'library': COURSE, 'rules': gap_rules['rules'], 'differs': [], 'gone': [], 'reads': [], 'typed': []})
    assert '시험 경고' in shown and '승인 카드의 규정 판정이 지금 계산' in shown, shown
    reused = ai_replay.notice({'library': REUSE, 'differs': ['「팬 최대 운전」 비교 총비용 30 → 45만 원'], 'rules': [], 'gone': [], 'reads': []})
    assert reused.startswith('같은 설정 · 같은 입력이라 앞선 실행 결과와 같습니다.') and '앞선 실행 때 값입니다 — 그때 → 지금 값: 「팬 최대 운전」 비교 총비용 30 → 45만 원' in reused, reused


def test_같은_요청_저장은_판단을_계산한_지식이_바뀌면_권장과_규정_판정이_같아도_버리고_수업_녹화는_그대로_쓴다(tmp_path, course_graph):
    """감독관 재검토(2026-11-24): 같은 요청 저장은 권장 · 규정 판정이 달라질 때만 버려, 학생이 문서 규칙의 기준값만 바꿔(70 → 65 ℃) 다시 적재하고 그
    규칙의 판정이 그대로면 저장이 다시 쓰였다 — 옛 기준값을 말하는 AI 설명이 「같은 설정 · 같은 입력이라 앞선 실행 결과와 같습니다」로 나갔다. 판단
    기록은 그 판단을 계산한 지식의 지문을 싣는다(agentsvc.decide.knowledge_of). 시작이 끝난 이 PC 의 그래프로 냉각 판단(저장분의 판단 인자)의 지문을 실제로
    계산하고, 인터록 규칙(rule:ts1-hard — 예측 유온 65 ℃ 이상이면 제외)의 기준값만 64 ℃ 로 바꾼 그래프로 다시 계산한다 — 규칙 · 후보 목록은 같고 지문만
    다르다. 실제 저장분의 냉각 판단 기록에 그 지문을 실어(같은 PC 가 저장하고 등록한 판단) 견준다: 같은 지문 → 다시 쓴다, 다른 지문 → 버리고 다음 실행이
    실제 AI 라고 말한다, 앞선 판단에 지문이 없음(옛 판의 저장분) → 견줄 수 없어 버린다. 수업 녹화(키 없는 PC)는 새로 판단할 길이 없어 판단이 같으면 쓴다."""
    import copy
    from agentsvc import decide
    from agentsvc.tools import mcp_kg
    known = {'pattern': 'COOLER_DEGRADATION', 'cause': 'cause:cooler-fin-fouling', 'failure_mode': 'fm:cooler-cooling-loss'}   # 저장분이 판단 도구에 준 인자

    def knowledge():
        ctx = decide.judgment_context(mcp_kg.KnowledgeGraph(), known)
        return decide.knowledge_of(ctx['dmn'], ctx['skills'], ctx['candidate_ids'], ctx['tradeoffs'])
    here = knowledge()
    moved = course_graph.query("MATCH (:Rule {id: 'rule:ts1-hard'})-[x:TESTS]->(:InputData {id: 'in:forecast-ts1'}) SET x.value = 64 RETURN x.value AS value")
    assert moved == [{'value': 64}], moved
    after = knowledge()
    assert (after['rules'], after['candidates']) == (here['rules'], here['candidates']) and after['digest'] != here['digest'], (here, after)

    old, seen = _recorded('c3_cooling/T_agent', 'submit_decision'), _recorded('c3_cooling/T_agent', 'evaluate_cards')

    def registered(digest, made):
        """저장분과 같은 판단(권장 · 카드 · 규정 판정 · 지식 목록 그대로)을 이 PC가 등록한 것 — 그 판단을 계산한 지식의 지문만 digest(None 이면 싣지 않은 옛 판)."""
        doc = copy.deepcopy(old)
        doc['document']['id'] = made
        doc['document']['knowledge'].pop('digest')
        if digest is not None:
            doc['document']['knowledge']['digest'] = digest
        return doc
    saved = registered(here['digest'], ai_replay._created(old)['id'])
    gap_same = ai_replay.decision_gap(saved, registered(here['digest'], 'DEC-now'), seen)
    gap_moved = ai_replay.decision_gap(saved, registered(after['digest'], 'DEC-now'), seen)
    gap_unknown = ai_replay.decision_gap(registered(None, ai_replay._created(old)['id']), registered(here['digest'], 'DEC-now'), seen)
    for gap in (gap_same, gap_moved, gap_unknown):        # 권장 · 실행할 수 있는 후보 · 수치 · 규정 판정 · 지식 목록은 모두 같다
        assert gap['judged'] and not (gap['changed'] or gap['numbers'] or gap['rules'] or gap['gone']), gap
    assert (gap_same['same_knowledge'], gap_moved['same_knowledge'], gap_unknown['same_knowledge']) == (True, False, None)

    step = '원인 진단 · 냉각 조치 제안'
    cache = _cached(tmp_path, [], slot='c3_cooling/T_agent')
    ai_replay.check_decision(cache, 'k' * 32, step, gap_same, 'DEC-now')              # 같은 지식 — 다시 쓴다
    assert cache.file_of('k' * 32).exists()
    for gap, why in ((gap_moved, '판단에 쓰는 지식(규칙 · 조치 방법 · 성과 지표 경로)이 앞선 판단 때와 다릅니다'),
                     (gap_unknown, '앞선 판단에는 그 판단을 계산한 지식의 기록이 없어 지금 지식과 같은지 견줄 수 없습니다')):
        cache = _cached(tmp_path, [], slot='c3_cooling/T_agent')
        with pytest.raises(ai_replay.ReuseDropped) as e:
            ai_replay.check_decision(cache, 'k' * 32, step, gap, 'DEC-now')
        said = str(e.value)
        assert not cache.file_of('k' * 32).exists(), said                            # 다음 [다시 수행]은 저장이 없어 실제 AI
        assert said.startswith(f'「{step}」의 같은 설정 · 같은 입력으로 앞서 실행한 판단이 지금과 맞지 않습니다 — {why}. 앞선 실행 결과는 버렸습니다'), said
        assert '실제 AI로 새로 판단합니다(지금 계산으로 등록된 판단 DEC-now은 승인 단계로 넘어가지 않습니다).' in said, said
        assert ai_replay.REPLAY not in said and not FORBIDDEN.search(said) and not WORKER_TALK.search(said), said
    key = ai_replay.course_key('c3_cooling/T_agent', 'COOLER_DEGRADATION')
    for gap in (gap_moved, gap_unknown):
        ai_replay.check_decision(COURSE_LIB, key, step, gap, None)                    # 수업 녹화는 멈추지 않고 녹화도 지우지 않는다
    assert COURSE_LIB.file_of(key).exists()


KG_SLOT = 'handover/draft-2'      # 저장분이 지식 지도 조회(매뉴얼 절에서 설비 이력 번호 hi-01 찾기 — 그때 0건)를 한 교대 인계안


@pytest.mark.parametrize('change', ['같은 지식', '바뀐 지식', '다시 조회하지 못함'])
def test_같은_요청_저장은_그_실행이_읽은_지식_지도가_지금과_다르거나_견주지_못하면_버리고_수업_녹화는_알리며_쓴다(tmp_path, tool_servers, course_graph, change):
    """감독관 재검토(2026-11-24): 판단 도구를 부르지 않는 교대 인계안은 조회 결과가 곧 근거인데, 같은 요청 저장은 그 실행이 읽은 지식 지도가 지금과 달라도
    「같은 설정 · 같은 입력이라 앞선 실행 결과와 같습니다」로 다시 쓰였다. 판단의 지식 지문과 같은 원칙으로, 지식 지도 조회가 지금과 다르거나 다시
    조회하지 못해 견주지 못했으면 버리고 다음 실행이 실제 AI 라고 말한다. 업무 · 설비 상태 조회(정비 요청 · 재고 · 설비 측정값 — 측정값은 다시 부르면
    늘 다르다)의 차이는 버리지 않고 알린다. 실제 저장분을 이 PC 의 실제 도구 서버와 시작이 끝난 그래프로: 같은 지식 → 다시 쓴다, 그 번호가 든 매뉴얼
    절이 생긴 지식 → 버린다, 그 조회가 이 PC 에서 오류(없는 함수)라 견주지 못함 → 버린다. 수업 녹화(키 없는 PC)는 같은 상황에서 멈추지 않고 알린다."""
    import copy
    doc = copy.deepcopy(COURSE_LIB.load(ai_replay.course_key(KG_SLOT, '')))
    run = doc['runs'][0]
    read = next(e for e in run['events'] if e['kind'] == 'tool_start' and e.get('tool') == 'mcp__neo4j__read_neo4j_cypher')
    if change == '바뀐 지식':
        course_graph.query("CREATE (:ManualSection {id: 'ms:test-hi-01', ref: 'HI-01.1', title: '설비 이력 HI-01', excerpt: '시험으로 넣은 절'})")
    elif change == '다시 조회하지 못함':            # 뜬 PC 에서는 된 조회가 이 PC 에서는 오류 — 저장된 결과(0건)는 그대로
        read['tool_input'] = {'query': 'MATCH (n:ManualSection) RETURN hyd.noSuchFunction(n.id) AS id'}
    course = Library(tmp_path / 'course', COURSE)
    course.root.mkdir()
    course.file_of(ai_replay.course_key(KG_SLOT, '')).write_bytes(gzip.compress(json.dumps(doc, ensure_ascii=False).encode('utf8')))
    cache = Library(tmp_path / 'cache', REUSE)       # 키 있는 PC 가 같은 단계를 실제 AI 로 실행해 제출한 저장(Claim.keep 이 남기는 꼴)
    cache.write('k' * 32, {'request': 'k' * 32, 'step': doc['step'], 'case': '', 'provider': doc['provider'],
                           'source': {'todo_id': 't', 'generation': 0}, 'runs': doc['runs']}, [])
    wd, _ = workdir_for(tmp_path, run, tool_servers)
    c = claim('live', slot=KG_SLOT, cache=cache, step=doc['step'], cli=lambda *a, **k: pytest.fail('실제 CLI 를 불렀다'))
    if change == '같은 지식':
        assert play(c, wd) and (wd / 'output' / 'result.json').is_file() and cache.file_of('k' * 32).exists()
        said = c.notice()
        assert said.startswith('같은 설정 · 같은 입력이라 앞선 실행 결과와 같습니다.') and '지식 지도 조회' not in said, said
        assert '결과 글 안의 조회 결과는 앞선 실행 때 값입니다' in said and '시계열 DB 조회(public.tag_1s) — ' in said, said   # 설비 측정값은 달라도 버리지 않고 알린다
        return
    with pytest.raises(ai_replay.ReuseDropped) as e:
        play(c, wd)
    said = str(e.value)
    assert not cache.file_of('k' * 32).exists() and not (wd / 'output' / 'result.json').exists(), said
    why = ('읽은 지식이 지금과 다릅니다: 지식 지도 조회(ManualSection) — 앞선 실행 때 0건 · 지금 1건.' if change == '바뀐 지식' else
           '읽은 지식을 이 PC에서 다시 조회하지 못해 지금 지식과 같은지 견주지 못했습니다: 지식 지도 조회(ManualSection).')
    assert said.startswith(f'「{doc["step"]}」을 같은 설정 · 같은 입력으로 앞서 실행할 때 {why} 앞선 실행 결과는 버렸습니다'), said
    assert said.endswith('「다시 수행」으로 다시 실행하면 실제 AI로 새로 실행합니다.'), said
    assert ai_replay.REPLAY not in said and not FORBIDDEN.search(said) and not WORKER_TALK.search(said) and 'neo4j' not in said and 'MATCH' not in said, said
    wd, _ = workdir_for(tmp_path, run, tool_servers)                            # 키 없는 PC 의 같은 처리 건
    c = claim('replay', slot=KG_SLOT, step=doc['step'], course=course)
    assert play(c, wd) and (wd / 'output' / 'result.json').is_file()
    told = c.notice() or ''
    assert (('지식 지도 조회(ManualSection) — 판단 때 0건 · 지금 1건' in told) if change == '바뀐 지식' else ('다시 조회하지 못해 지금 값과 견주지 못했습니다' in told)), told


@pytest.mark.parametrize('broken', ['작업 기록 없음', '지시 꼴이 깨짐'])
def test_작업_기록을_읽지_못하면_입력_대조를_건너뛰지_않고_그_자리를_대며_실패한다(tmp_path, tool_servers, broken):
    """감독관 재검토(2026-11-24): 작업 기록(context/task.json)의 지시를 처리 엔진의 꼴로 읽지 못하면 ValueError 를 삼키고 입력 대조를 건너뛰었다 —
    기록이 없을 때도 빈 값으로 넘어가, 저장된 실행의 처리 건 id · 입력을 이 처리 건의 값과 견주지도 바꿔 끼우지도 않은 채 결과를 냈다. Runner 는 실행 전에
    늘 그 기록을 쓰므로(workspace.provision) 닿지 않는 길이지만, 그 자리(파일 · 작업 · 칸)를 대며 실패한다. 도구 서버는 이 PC의 실제 서버다 — 고치기
    전 동작이 도구 서버가 없다는 딴 까닭으로 멈추지 않고 저장된 결과까지 내는 길을 이 시험이 잡는다."""
    doc = COURSE_LIB.load(ai_replay.course_key('handover/draft-1', ''))
    run = doc['runs'][0]
    wd, task = workdir_for(tmp_path, run, tool_servers)
    path = wd / 'context' / 'task.json'
    if broken == '작업 기록 없음':
        path.unlink()
    else:                                                   # [InputData] 값 뒤에 처리 엔진이 붙이지 않는 글
        path.write_text(json.dumps(dict(task, query=task['query'] + '\n덧붙은 글'), ensure_ascii=False), encoding='utf8')
    with pytest.raises(RuntimeError) as e:
        play(claim(slot='handover/draft-1', step=doc['step']), wd)
    said = str(e.value)
    assert str(path) in said, said
    if broken == '지시 꼴이 깨짐':
        assert f"작업 {task['id']} 의 지시" in said and 'query 칸' in said and '[InputData] 값 뒤에 모르는 글' in said, said
    assert not (wd / 'output' / 'result.json').exists()


def test_PBL_단계의_AI_단계는_키_없는_PC에서_재생하지_않고_실제_AI로_하라고_말한다(tmp_path):
    """서버는 PBL 단계의 AI 단계에 자리를 주지 않는다(course_policy.ai_slot). 키 없는 PC가 수업 때의 응답을 내지 않고 그 까닭을 말한다."""
    c = Responses('replay', course=COURSE_LIB).claim(cli=None, slot=None, case='', attempt=(0, 0), request_key=None, step='원인 진단 · 냉각 조치 제안',
                                                     provider='claude-code', source={}, accepted=lambda s: True, phase='pbl')
    with pytest.raises(NotRecorded) as e:
        play(c, tmp_path)
    said = str(e.value)
    assert said.startswith(ai_replay.REPLAY) and 'PBL 기간' in said and 'AI 키' in said and '기본 제공 흐름' not in said, said


def _real_cli():
    """키 있는 PC 의 CLI 자리 — 지금 실행의 세션 id 로 결과 하나."""
    def cli(provider, request, env, check_stop=None):
        yield ExecEvent(kind=ExecEventKind.RESULT, text='{}', session_id=LIVE_SESSION)
    return cli


def test_저장한_실행이_처리_흐름에서_받아들여지지_않았으면_버리고_실제_AI로_실행한다(tmp_path):
    cache = _cached(tmp_path)
    out = play(claim('live', slot='handover/draft-1', cache=cache, accepted=lambda source: False, cli=_real_cli()), tmp_path)
    assert [e.session_id for e in out if e.kind == ExecEventKind.RESULT] == [LIVE_SESSION]     # 결과는 실제 AI 의 것(저장 실행의 세션 아님)
    assert not cache.file_of('k' * 32).exists()


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
    play(c, _task_folder(tmp_path))
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
    cache = _cached(tmp_path)
    now = time.time()
    os.utime(cache.file_of('k' * 32), (now - age_h * 3600, now - age_h * 3600))
    removed = ai_replay.sweep_cache(cache, lambda todo: todo_exists and todo == 't', 72 * 3600, now=now)
    assert cache.file_of('k' * 32).exists() is kept and removed == ([] if kept else ['k' * 32])


def test_다시_쓴_같은_요청_저장은_보존_기간을_그때부터_다시_센다(tmp_path):
    import os
    import time
    cache = _cached(tmp_path)
    old = time.time() - 73 * 3600
    os.utime(cache.file_of('k' * 32), (old, old))
    out = play(claim('live', slot='handover/draft-1', cache=cache, cli=_real_cli()), tmp_path)   # 끝난 작업의 같은 요청 → 저장을 다시 낸다
    assert LIVE_SESSION not in [e.session_id for e in out if e.kind == ExecEventKind.RESULT]     # 실제 AI 가 아니라 저장을 냈다
    assert ai_replay.sweep_cache(cache, lambda todo: True, 72 * 3600) == [] and cache.file_of('k' * 32).exists()


# ---------------------------------------------------------------- 다시 등록한 판단과 준비된 판단의 차이(decision_gap) — 까닭이 지식인지 설비 · 업무 상태인지
def _recorded(slot, tool):
    """저장소 녹화의 그 자리 첫 실행에서 판단 도구 결과 하나(마지막 것)."""
    run = next(d for _, d in COURSE_LIB.docs() if d['slot'] == slot)['runs'][0]
    ends = [e for e in run['events'] if e['kind'] == 'tool_end' and (e.get('tool') or '').endswith(tool)]
    return ai_replay._as_json((run.get('tool_outputs_full') or {}).get(ends[-1].get('tool_use_id')) or ends[-1].get('tool_output'))


def _now_view(seen, *, keep, knowledge=True, drop_rules=()):
    """이 PC가 지금 계산한 판단(dmn-mcp agent_view 꼴): 준비된 평가에서 keep 카드만 남기고 첫째를 권장, drop_rules 규칙 판정은 뺀다.
    knowledge=False 는 지금 지식 목록을 싣지 않는 옛 판 판단 서비스다 — 저장된 평가가 지식(knowledge)을 실었어도 뺀다(2026-11-23 저장분은 싣는다)."""
    doc = dict(ai_replay._created(seen))
    doc['options'] = [dict(o, **{k: [r for r in o.get(k) or [] if r['rule'] not in drop_rules] for k in ai_replay.RULE_KINDS})
                      for o in doc['options'] if o['id'] in keep]
    doc['recommended'] = doc['options'][0]['id']
    doc.pop('knowledge', None)
    if knowledge:
        doc['knowledge'] = {'candidates': list(keep), 'rules': sorted({r['rule'] for o in ai_replay._created(seen)['options'] for k in ai_replay.RULE_KINDS
                                                                       for r in o.get(k) or [] if r['rule'] not in drop_rules})}
    return {'result': 'ok', 'document': doc}


def test_후보_규칙을_뺀_지식으로_다시_계산한_판단은_지식이_바뀐_까닭과_할_일로_멈춘다():
    """메인 실측 2026-11-22: HM-8 의 냉각 조치 후보 규칙을 빼고 다시 적재하자 지금 계산이 「쿨러 핀 세척」 하나가 됐고 재생이 멈췄는데, 문장이
    「설비 · 업무 상태를 시작 상태로 되돌리라」고 했다 — 학생이 바꾼 것은 지식이다. 지금 계산이 준비된 판단의 조치 후보가 지금 지식에 없다고
    말하면 지식 때문이고, 그 근거가 없으면(옛 판 판단 서비스) 둘 다 말한다."""
    old, seen = _recorded('c3_cooling/T_agent', 'submit_decision'), _recorded('c3_cooling/T_agent', 'evaluate_cards')
    gap = ai_replay.decision_gap(old, _now_view(seen, keep=['skill:sop-cool-14']), seen)
    assert gap['changed'] and set(gap['gone']) == {'조치 후보 「팬 최대 운전」', '조치 후보 「부하 70 %와 야간 핀 세척」', '조치 후보 「팬 최대 운전과 부하 80 %」'}, gap
    said = ai_replay.changed_because(gap['gone'])
    assert '지금 지식에 없습니다' in said and '제안 그대로 다시 적재' in said and '시작 상태로 되돌린' not in said, said
    unknown = ai_replay.decision_gap(old, _now_view(seen, keep=['skill:sop-cool-14'], knowledge=False), seen)
    assert unknown['changed'] and unknown['gone'] is None
    both = ai_replay.changed_because(unknown['gone'])
    assert '지금 지식' in both and '설비 · 업무 상태' in both and '제안 그대로 다시 적재' in both and '시작 상태로 되돌린' in both, both
    for text in (said, both):
        assert not FORBIDDEN.search(text) and '강사' not in text and '녹화' not in text


def test_두_판단의_지식_지문이_같으면_달라진_까닭을_설비_업무_상태_한쪽으로_말한다():
    """탐사 N7 의 남은 것: 준비된 판단과 지금 계산이 다를 때 지식이 같아도 「지식이나 설비 · 업무 상태」 둘 다를 말했다 — 학생이 무엇을 되돌릴지 고르지
    못한다. 판단 기록은 그 판단을 계산한 지식의 내용 지문을 싣고(agentsvc.decide.knowledge_of), 준비된 판단의 지문과 지금 계산의 지문이 같으면 설비 ·
    업무 상태만 말한다. 지문이 다르거나 준비된 판단에 지문이 없으면(옛 판의 저장분) 한쪽으로 단정하지 않고 전처럼 둘 다 말한다."""
    old, seen = _recorded('c3_cooling/T_agent', 'submit_decision'), _recorded('c3_cooling/T_agent', 'evaluate_cards')
    keep = [o['id'] for o in ai_replay._created(seen)['options']]

    def judged(doc, digest):
        out = {'result': 'ok', 'document': dict(ai_replay._created(doc))}
        out['document']['knowledge'] = dict(out['document'].get('knowledge') or {'candidates': keep, 'rules': []}, digest=digest)
        return out
    now = _now_view(seen, keep=keep)                                       # 같은 지식(후보 모두)인데 권장이 다르다 = 설비 · 업무 상태가 다르다
    now['document']['recommended'] = next(i for i in keep if i != ai_replay._created(old)['recommended'])
    same = ai_replay.decision_gap(judged(old, 'a' * 64), judged(now, 'a' * 64), seen)
    assert same['changed'] and same['gone'] == [] and same['same_knowledge'] is True, same
    said = ai_replay.changed_because(same['gone'], same['same_knowledge'])
    assert '준비된 판단 때와 같고' in said and '설비 · 업무 상태를 시작 상태로 되돌린' in said and '다시 적재' not in said, said
    assert not FORBIDDEN.search(said) and '강사' not in said and '녹화' not in said
    # 둘 다 지문을 실었는데 다름 → False, 한쪽이라도 싣지 않음(옛 판의 저장분) → None(견줄 수 없음). 수업 녹화는 둘 다 한쪽으로 단정하지 않는다
    without_knowledge = {'result': 'ok', 'document': {k: v for k, v in ai_replay._created(old).items() if k != 'knowledge'}}
    for before, after, expected in ((judged(old, 'a' * 64), judged(now, 'b' * 64), False), (old, judged(now, 'a' * 64), False),
                                    (judged(old, ''), judged(now, ''), None), (without_knowledge, judged(now, 'a' * 64), None)):
        gap = ai_replay.decision_gap(before, after, seen)
        assert gap['changed'] and gap['judged'] is True and gap['same_knowledge'] is expected, gap
        both = ai_replay.changed_because(gap['gone'], gap['same_knowledge'])
        assert '다시 적재' in both and '시작 상태로 되돌린' in both, both
    gone = ai_replay.decision_gap(judged(old, 'a' * 64), judged(_now_view(seen, keep=keep[-1:]), 'a' * 64), seen)      # 사라진 지식이 있으면 지식이 먼저다
    assert gone['gone'] and '지금 지식에 없습니다' in ai_replay.changed_because(gone['gone'], gone['same_knowledge'])


def test_권장이_같아도_AI_설명이_든_규정_판정이_지금_계산에_없으면_처리_과정에_그_차이를_말한다():
    """탐사 N7: 권장 조치 · 실행할 수 있는 후보가 같으면 재생은 멈추지 않는데, 학생이 감점 · 경고 규칙을 뺀 뒤에도 AI 설명은 그 규칙 때문에 이 안이
    졌다고 말했다(승인 카드에는 그 규칙이 없다). 녹화의 정기 정비 평가가 든 경고 규칙 하나를 뺀 지금 계산으로 본다."""
    old, seen = _recorded('c3_pm/T_agent', 'submit_decision'), _recorded('c3_pm/T_agent', 'evaluate_cards')
    keep = [o['id'] for o in ai_replay._created(seen)['options']]
    now = _now_view(seen, keep=keep, drop_rules=('rule:pm-seal-kit-reorder-warning',))
    now['document']['recommended'] = ai_replay._created(old)['recommended']
    gap = ai_replay.decision_gap(old, now, seen)
    assert gap['changed'] == [] and gap['rules'] and gap['gone'] and gap['gone'][0].startswith('규칙 「'), gap
    parts = ai_replay.notice_parts({'library': COURSE, 'rules': gap['rules'], 'gone': gap['gone']})
    (kind, text), = parts
    assert kind == 'values_differ' and '판단 때 걸린' in text and '지금 계산에는 없음' in text and '지금 지식에 없습니다' in text, text
    assert 'rule:' not in text and not FORBIDDEN.search(text), text


def test_앞_조회가_돌려준_PC마다_다른_식별자를_조건에_적은_뒤_조회는_이_PC의_식별자로_다시_부른다():
    """2026-11-23: 다시 받은 질문 답(HM-8)은 첫 조회가 돌려준 문서 판본 id 를 다음 조회의 조건에 적었다. 그 조회문을 글자 그대로 다시 부르면 다른 PC 에는 그
    id 가 없어 0건이 되고, 지식이 같은데도 「판단 때 8건 · 지금 0건」 알림이 붙는다. 같다고 본 조회 결과에서 식별자를 짝지어 뒤 조회의 입력을 이 PC 의
    것으로 바꾼다. 식별자를 빼면 같은 행이 둘이면 짝짓지 않고, 모르는 식별자는 그대로 둔다."""
    saved_id = 'ks:manual:' + 'a' * 64 + ':11111111-1111-4111-8111-111111111111:' + 'c' * 64
    here_id = 'ks:manual:' + 'a' * 64 + ':22222222-2222-4222-8222-222222222222:' + 'c' * 64
    twin_a, twin_b = '33333333-3333-4333-8333-333333333333', '44444444-4444-4444-8444-444444444444'
    old = (['id', 'name'], [[saved_id, 'HM-8 유압 설비 고장 매뉴얼'], [twin_a, '같은 이름'], [twin_b, '같은 이름']])
    new = (['id', 'name'], [['55555555-5555-4555-8555-555555555555', '같은 이름'], [here_id, 'HM-8 유압 설비 고장 매뉴얼'],
                            ['66666666-6666-4666-8666-666666666666', '같은 이름']])
    assert ai_replay.read_gap(old, new) is None
    known = {}
    ai_replay.pair_generated(old, new, known)
    assert known == {'11111111-1111-4111-8111-111111111111': '22222222-2222-4222-8222-222222222222'}, known
    query = {'query': "MATCH (k:KnowledgeSource {id: '%s'})<-[:PART_OF]-(m) WHERE m.note <> '%s' RETURN m.ref AS ref" % (saved_id, twin_a), 'limit': 50}
    again = ai_replay.with_generated(query, known)
    assert again == {'query': "MATCH (k:KnowledgeSource {id: '%s'})<-[:PART_OF]-(m) WHERE m.note <> '%s' RETURN m.ref AS ref" % (here_id, twin_a), 'limit': 50}
    assert ai_replay.with_generated(query, {}) is query


def test_칸_안에_모은_묶음은_안쪽의_PC마다_다른_식별자와_모은_차례를_빼고_견준다():
    """2026-11-23: 다시 받은 질문 답의 조회는 절마다 단계를 collect 로 모아 한 칸에 담는다. 그 칸 안의 인용에는 문서 판본 id 가 있고 모은 차례는 조회마다
    다를 수 있다 — 맨 바깥 글만 식별자를 가리던 때는 지식이 같아도 「8건으로 같고 값이 다름」이었다. 안쪽 글이 다르면 여전히 다르다."""
    def step(doc, n, text):
        return {'step_id': f'skill:sop-cool-13:{n}', 'order': n, 'text': text,
                'citation': json.dumps({'source_id': f'manual:{doc}:' + 'c' * 64, 'start': 100 * n}, ensure_ascii=False)}
    a, b = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'
    old = (['ref', 'steps'], [['HM-8.5', [step(a, 2, '부하를 70 %로 낮춘다'), step(a, 4, '세척 작업지시를 건다')]]])
    same = (['ref', 'steps'], [['HM-8.5', [step(b, 4, '세척 작업지시를 건다'), step(b, 2, '부하를 70 %로 낮춘다')]]])
    other = (['ref', 'steps'], [['HM-8.5', [step(b, 4, '세척 작업지시를 건다'), step(b, 2, '부하를 80 %로 낮춘다')]]])
    assert ai_replay.read_gap(old, same) is None
    assert ai_replay.read_gap(old, other) == (1, 1)
