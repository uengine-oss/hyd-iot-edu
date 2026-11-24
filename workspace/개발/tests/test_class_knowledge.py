"""시작 7단계 수업 지식(scripts/class_knowledge.py) — 정본은 강사 서명 묶음 하나: 시작은 그 검토본(절 · 절차 · 지식 · 검토한 연결)을
그대로 넣고, 4회차에 같은 문서를 제공 문서 캐시(AI 0)로 다시 넣어 제안 그대로 검토 완료하면 같은 지식이다. 옛 시작 사본이 넣은 판은 다음 시작 때
묶음 판으로 바꿔 넣고, 학생이 다시 넣은 판은 건드리지 않는다.
실제 process(world — 시작이 끝난 학생 PC: kg-seed + 이 스크립트의 적재)와 실제 그래프로 판정한다."""
import base64
import json
import re
import shutil
import uuid
from copy import deepcopy
from pathlib import Path

import pytest

import class_knowledge as ck

RULE = 'rule:cooler-forecast-temperature-warning'


# ---------------------------------------------------------------- 묶음에서 읽기
def test_묶음에서_세_문서를_적재_순서대로_읽고_담당자_칸에는_사람_이름이_아니라_기본_제공이라고_적는다():
    """문서 등록 이력의 담당자 칸에 「강사 검토본(2026-10-27-reviewed-1)」이 보였다(화면에 「강사」가 없어야 한다). 어느 판인지는 담당자 글이
    아니라 판 표시(provided_revision)가 싣는다."""
    from student_words import WORKER_TALK
    items = ck.reviewed()
    assert [i['doc'] for i in items] == ['HM-8', 'PM-02', 'PR-07']
    revision = json.loads(ck.BUNDLE.read_text(encoding='utf8'))['payload']['revision']
    assert {(i['by'], i['revision']) for i in items} == {(ck.PROVIDED_BY, revision)} and not WORKER_TALK.search(ck.PROVIDED_BY)


def test_원문이_묶음의_판과_다르면_넣지_않고_멈춘다(tmp_path):
    shutil.copytree(ck.ORIGINALS, tmp_path / 'samples')
    hm8 = tmp_path / 'samples' / 'HM-8_cooler-fan-manual.md'
    hm8.write_bytes(hm8.read_bytes() + b'\n')
    with pytest.raises(ck.Stop, match='HM-8.*다릅니다'):
        ck.reviewed(originals=tmp_path / 'samples')


def test_적재_요청은_묶음_제안과_검토한_연결을_이_PC의_원문_판본으로_가리킨다():
    item = ck.reviewed()[0]
    body = ck.commit_body(item, {'source_id': 'manual:d:' + item['sha256'], 'document_id': 'd', 'filename': item['filename'],
                                 'batch': str(uuid.uuid4()), 'previous_batch': None})
    assert 'provided-source' not in json.dumps(body) and body['reviewed'] is True
    assert body['links'] == {p['id']: ck.rebased(p['link'], body['source_id']) for p in item['proposal']['procedures'] if p.get('link')}
    assert all('link' not in p for p in body['procedures'])
    assert RULE in {r['id'] for r in body['knowledge']['rules']}


@pytest.mark.parametrize('current, what', [
    (None, 'load'), ({'by': ck.OLD_SEED_BY}, 'revise'),
    ({'by': '강사 검토본(2026-10-27-reviewed-1)', 'review_method': 'user-delegated-ai-review'}, 'revise'),
    ({'by': ck.PROVIDED_BY, 'review_method': 'user-delegated-ai-review', 'provided_revision': '옛 판'}, 'revise'),
    ({'by': '지식 관리자'}, 'student'),
    ({'by': '강사 검토본(2026-10-27-reviewed-1)'}, 'student'), ({'by': ck.PROVIDED_BY}, 'student'),
], ids=['처음', '지운 시작 사본이 넣은 판', '판 표시가 없던 앞 판의 기본 제공 판', '옛 묶음 판', '학생이 다시 넣은 판',
        '학생이 담당자 칸에 옛 기본 제공 글을 적은 판', '학생이 담당자 칸에 기본 제공이라고 적은 판'])
def test_이미_적재된_문서를_어떻게_할지는_담당자_글이_아니라_적재_기록의_판_표시로_정한다(current, what):
    """장부 11-#15: 시작 판과 학생이 다시 넣은 판을 담당자 칸의 자유 글로 갈라, 학생이 그 글을 적으면 기본 제공 판으로 읽혔다."""
    assert ck.decide(ck.reviewed()[0], current, loaded_before=current is not None) == what


def test_지금_묶음_판이_적재돼_있으면_그대로_둔다():
    item = ck.reviewed()[0]
    assert ck.decide(item, {'by': '아무 글', 'review_method': item['review_method'], 'provided_revision': item['revision']},
                     loaded_before=True) == 'keep'


def test_적재_기록은_있는데_지금_판이_없는_문서는_학생이_비운_것이라_넣지_않는다():
    """시작이 다시 채우면 학생이 비운 뒤 포털에서 다시 넣는 길이 가려지고, PBL에서 수업 문서를 뺀 그래프를 쓸 수 없다."""
    assert ck.decide(ck.reviewed()[0], None, loaded_before=True) == 'emptied'


def test_기본_제공_문서의_적재_기록은_파일_이름이_아니라_그_문서로_찾는다():
    """전수검사 03-25: 시작이 지금 판을 파일 이름으로 찾아, 학생이 같은 이름으로 올린 다른 문서를 이 문서의 「학생이 다시 넣은 판」으로 읽었다 —
    기본 제공 판이 그대로 있는데도, 묶음 판이 바뀌어도 그 문서를 개정하지 않는다. ensure 가 실제로 무엇을 하는지(올리기 · 적재 요청)로 판정한다."""
    item = ck.reviewed()[0]
    provided = {'batch': 'b-provided', 'document_id': 'doc-provided', 'source_id': 'manual:doc-provided:' + item['sha256'],
                'filename': item['filename'], 'by': ck.PROVIDED_BY, 'review_method': item['review_method'],
                'provided_revision': '옛 묶음 판', 'current': True, 'status': 'ACTIVE'}
    # 학생이 같은 파일 이름으로 올린 다른 문서(다른 원문 · 판 표시 없음) — 등록 이력에서 더 최신이라 앞에 온다
    other = {'batch': 'b-other', 'document_id': 'doc-other', 'source_id': 'manual:doc-other:' + 'f' * 64,
             'filename': item['filename'], 'by': 'user:me', 'current': True, 'status': 'ACTIVE'}
    assert ck.lineage([other, provided], item) == [provided]
    # 학생이 기본 제공 문서를 개정한 판(같은 문서 · 다른 원문)은 그 문서의 판이다 — 그 판이 지금 판이면 시작이 건드리지 않는다
    revised = dict(other, batch='b-revised', document_id='doc-provided', source_id='manual:doc-provided:' + 'e' * 64)
    superseded = dict(provided, current=False)
    assert ck.lineage([other, revised, superseded], item) == [revised, superseded]
    # 같은 원문을 다른 이름으로 올려 적재한 문서도 이 문서의 지식을 담는다(원문 sha256)
    renamed = dict(other, batch='b-renamed', document_id='doc-renamed', filename='내가 바꾼 이름.md',
                   source_id='manual:doc-renamed:' + item['sha256'])
    assert ck.lineage([renamed, other], item) == [renamed]

    def run(history):
        calls = []

        def call(method, path, body=None):
            calls.append((method, path, body))
            if path == '/api/kg/scm-sync':
                return {}
            if path == '/api/kg/manuals':
                return history
            if path == '/api/kg/manuals/preview':
                assert body['filename'] == item['filename'], '이 시험의 등록 이력으로는 첫 문서만 다시 넣는다'
                return {'source_id': 'manual:' + (body.get('document_id') or 'doc-new') + ':' + item['sha256'],
                        'document_id': body.get('document_id') or 'doc-new', 'filename': item['filename'], 'batch': 'b-new',
                        'previous_batch': 'b-provided' if body.get('document_id') else None}
            if path == '/api/kg/manuals/commit':
                return {'procedures': 7, 'steps': 25, 'batch': 'b-new'}
            raise AssertionError(path)
        lines = ck.ensure(call)
        return lines[0], [c for c in calls if c[1] == '/api/kg/manuals/preview' and c[2]['filename'] == item['filename']]

    rest = [dict(provided, batch='b-' + r['doc'], document_id='doc-' + r['doc'], filename=r['filename'],
                 source_id='manual:doc-' + r['doc'] + ':' + r['sha256'], provided_revision=r['revision']) for r in ck.reviewed()[1:]]
    line, uploads = run([other, provided, *rest])
    assert '앞 판의 기본 제공 판을 지금 판으로 바꿈' in line, line
    assert [u[2].get('document_id') for u in uploads] == ['doc-provided'], '같은 이름의 학생 문서가 아니라 기본 제공 판을 담은 문서를 개정한다'
    line, uploads = run([other, revised, superseded, *rest])
    assert '이 PC에서 다시 적재한 판' in line and 'b-revised' in line and not uploads


# ---------------------------------------------------------------- 실제 학생 PC
def manuals(world):
    status, rows = world.api('GET', '/api/kg/manuals')
    assert status == 200, rows
    return {r['filename']: r for r in rows if r.get('current')}


def rules_of(world, filename):
    status, rows = world.api('GET', '/api/kg/manuals')
    current = next(r for r in rows if r.get('current') and r['filename'] == filename)
    return set(current['knowledge']['rules'])


def test_시작이_끝난_PC에는_세_문서가_기본_제공_판으로_있고_냉각_경고_규칙도_있다(world):
    """G3a-1 · P2-02: 지운 시작 사본으로 시작한 PC에는 예측 유온 55 ℃ 경고 규칙이 없었다. 화면의 문서 등록 이력이 읽는 실제 응답의 담당자 칸에
    작업자끼리 쓰는 말이 없다."""
    from student_words import WORKER_TALK
    current = manuals(world)
    items = {i['filename']: i for i in ck.reviewed()}
    assert set(items) <= set(current) and all(current[f]['by'] == items[f]['by'] for f in items)
    assert all(current[f]['provided_revision'] == items[f]['revision'] and not WORKER_TALK.search(current[f]['by']) for f in items)
    assert RULE in rules_of(world, items['HM-8_cooler-fan-manual.md']['filename'])


def test_다시_시작해도_적재된_검토본은_그대로_두고_새_배치를_만들지_않는다(world):
    before = {f: r['batch'] for f, r in manuals(world).items()}
    lines = ck.ensure(ck.http_call(world.url))
    assert all('그대로 둠' in line for line in lines)
    assert {f: r['batch'] for f, r in manuals(world).items()} == before


def test_업무_DB_견적이_그래프에_없는_부품을_가리키면_적재_전에_그_좌표로_멈춘다(world):
    """G3a-25: 구매 기준(PR-07)의 의미 검사가 그래프의 공급 관계를 읽으므로 시작은 먼저 업무 DB → 그래프 동기화를 부른다."""
    import psycopg
    before = {f: r['batch'] for f, r in manuals(world).items()}
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("INSERT INTO ent.parts(part_no, name, std_price) VALUES ('P-TEST-NOGRAPH', '그래프에 없는 시험 부품', 1)")
        db.execute("INSERT INTO ent.part_quotes(part_no, supplier_id, price, fail_rate, lead_d) VALUES ('P-TEST-NOGRAPH', 'sup:a', 1, 0.1, 1)")
    try:
        with pytest.raises(ck.Stop, match='P-TEST-NOGRAPH/sup:a'):
            ck.ensure(ck.http_call(world.url))
    finally:
        with psycopg.connect(world.dsn, autocommit=True) as db:
            db.execute("DELETE FROM ent.part_quotes WHERE part_no='P-TEST-NOGRAPH'")
            db.execute("DELETE FROM ent.parts WHERE part_no='P-TEST-NOGRAPH'")
    assert {f: r['batch'] for f, r in manuals(world).items()} == before       # 아무 문서도 적재하지 않았다


def portal_commit(world, item, *, by, drop_rule=None):
    """포털 지식 관리와 같은 길: 제공 문서 고르기(같은 이름으로 적재된 문서가 있으면 그 문서의 개정, 없으면 새 문서 — 화면 hitl.js 의 제공 문서 줄과
    같다) → 제공 문서 캐시 추출(AI 0) → 결과 → 제안 그대로 검토 완료(drop_rule: 사람이 검토에서 뺀 규칙) → 적재."""
    current = manuals(world).get(item['filename'])
    upload = {'filename': item['filename'], 'data': base64.b64encode(item['raw']).decode(), **({'document_id': current['document_id']} if current else {})}
    status, preview = world.api('POST', '/api/kg/manuals/preview', upload)
    assert status == 200, preview
    sid = preview['source_id']
    status, started = world.api('POST', f'/api/kg/manuals/sources/{sid}/extractions', {'request_id': str(uuid.uuid4())})
    assert status == 200, started
    assert world.poll() == []                     # 서명 제안은 제출된 결과로 들어간다 — 엔진 폴링 한 바퀴가 결과 검사 · 완료를 한다(실행 서비스의 2초 폴링)
    status, result = world.api('GET', f"/api/kg/manuals/sources/{sid}/extractions/{started['instance']}")
    assert status == 200 and result['preview'], result
    reviewed = deepcopy(result['preview'])
    if drop_rule:                                       # 검토 화면의 [적재에서 제외] — 규칙 id 하나 또는 여럿
        gone = {drop_rule} if isinstance(drop_rule, str) else set(drop_rule)
        reviewed['knowledge']['rules'] = [r for r in reviewed['knowledge']['rules'] if r['id'] not in gone]
    request = dict(reviewed, links={p['id']: p['link'] for p in reviewed['procedures'] if p.get('link')}, by=by, reviewed=True)
    status, changes = world.api('POST', '/api/kg/manuals/changes', request)
    assert status == 200, changes
    status, out = world.api('POST', '/api/kg/manuals/commit', request)
    assert status == 200, out
    return changes, out


#: 문서 번호(uuid) — 참고 절차 단계 id 처럼 문서에서 나온 id 에 들어간다. 같은 원문을 다시 올리면 보관소의 어느 문서가 그 원문을 다시 쓰는지에 따라
#: 달라진다(시험 묶음은 원문 보관소를 함께 쓴다 — 앞 시험 파일이 같은 제공 문서를 새 문서로 올려 두면 그 문서가 다시 쓰인다). 지식 내용이 아니다.
DOCUMENT_NO = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def owned(graph):
    """적재된 문서들이 가진 지식 그래프(노드 id · 종류 · 실행에 쓰이는 속성) — 판본 · 배치 · 인용 위치 · 문서 번호처럼 적재마다 달라지는 칸은 뺀다."""
    rows = graph.query(
        'MATCH (d:ManualIngestionDocument) WHERE d.head IS NOT NULL WITH d MATCH (n) WHERE n._manual_document = d.id '
        'AND (n:Skill OR n:FailureMode OR n:Cause OR n:Evidence OR n:Rule OR n:Step) '
        'RETURN labels(n)[0] AS label, n.id AS id, properties(n) AS props')
    keep = lambda props: {k: v for k, v in props.items() if k not in ('source_id', 'citation', '_manual_document', 'id') and not k.startswith('_')}
    # 정비 기준 같은 속성 안의 원문 인용(anchor.source_id = manual:<문서 번호>:<원본 sha256>)도 문서 번호만 다르다 — 인용 칸(citation)을 빼는 것과 같은 까닭
    return {(r['label'], DOCUMENT_NO.sub('(문서)', r['id']), DOCUMENT_NO.sub('(문서)', json.dumps(keep(r['props']), sort_keys=True, ensure_ascii=False)))
            for r in rows}


def owned_gap(before: set, after: set) -> list[str]:
    """두 owned() 의 차이를 노드마다 「종류 id: 칸 — 앞 값 → 뒤 값」으로(없어진 노드 · 생긴 노드 포함). 같으면 빈 목록."""
    a = {(l, i): json.loads(p) for l, i, p in before}
    b = {(l, i): json.loads(p) for l, i, p in after}
    out = [f'{l} {i}: 없어짐' for l, i in sorted(set(a) - set(b))] + [f'{l} {i}: 새로 생김' for l, i in sorted(set(b) - set(a))]
    for key in sorted(set(a) & set(b)):
        for field in sorted(set(a[key]) | set(b[key])):
            if a[key].get(field) != b[key].get(field):
                out.append(f'{key[0]} {key[1]}: {field} — {str(a[key].get(field))[:300]} → {str(b[key].get(field))[:300]}')
    return out


def test_4회차에_같은_문서를_제안_그대로_다시_넣으면_시작_지식과_같은_지식이다(world, course_graph):
    """시작이 넣은 지식 = 4회차 재적재(서명 묶음 · AI 0) 결과. 빠지는 노드가 없고 남는 노드 · 실행 속성이 같다."""
    item = next(i for i in ck.reviewed() if i['doc'] == 'HM-8')
    before = owned(course_graph)
    performed = lambda: {(r['sop'], tuple(r['by'])) for r in course_graph.query(
        'MATCH (d:ManualIngestionDocument) WHERE d.head IS NOT NULL MATCH (k:Skill {_manual_document: d.id}) WHERE k.kind <> "reference" '
        'RETURN k.sopId AS sop, COLLECT { MATCH (s:System)-[:HAS_SKILL]->(k) RETURN s.id } AS by')}
    first = performed()
    # 세 문서의 실행 절차는 모두 이 시스템의 업무 시스템 하나가 수행한다(설비 명령 SCADA · 정비 요청 CMMS · 구매 ERP) — 수행 시스템을 판정으로 정한 뒤에도 그대로다
    links = [(p['id'], p.get('link') or {}) for i in ck.reviewed() for p in i['proposal']['procedures']]
    expect = {(sop, ('sys:erp',) if link.get('scope') == 'purchase' else ('sys:scada',) if link.get('kind') == 'control' else ('sys:cmms',))
              for sop, link in links if link.get('kind') != 'reference'}
    assert first == expect, first ^ expect
    changes, out = portal_commit(world, item, by='지식 관리자')
    assert changes['removed'] == [] and out['procedures'] == len(item['proposal']['procedures'])
    gap = owned_gap(before, owned(course_graph))
    assert gap == [], chr(10).join(gap)
    assert performed() == first


def test_옛_시작_판이_있는_PC는_다음_시작_때_강사_검토본으로_바꿔_넣는다(world):
    """지운 시작 사본(2026-10-25 판)이 넣은 판 = 경고 규칙이 없고 담당이 옛 글인 판. 다음 시작이 그것을 묶음 판으로 바꾼다."""
    item = next(i for i in ck.reviewed() if i['doc'] == 'HM-8')
    portal_commit(world, item, by=ck.OLD_SEED_BY, drop_rule=RULE)
    assert RULE not in rules_of(world, item['filename'])
    lines = ck.ensure(ck.http_call(world.url))
    assert any(line.startswith('HM-8: 앞 판의 기본 제공 판을 지금 판으로 바꿈') for line in lines)
    assert RULE in rules_of(world, item['filename']) and manuals(world)[item['filename']]['by'] == item['by']


def test_학생이_다시_넣은_판은_시작이_건드리지_않는다(world):
    item = next(i for i in ck.reviewed() if i['doc'] == 'PR-07')
    _, out = portal_commit(world, item, by='지식 관리자')
    lines = ck.ensure(ck.http_call(world.url))
    assert any(line.startswith('PR-07: 이 PC에서 다시 적재한 판') for line in lines)
    assert manuals(world)[item['filename']]['batch'] == out['batch']


def test_4회차에_다시_넣은_판을_되돌리면_시작_판이_다시_지금_판이_된다(world):
    item = next(i for i in ck.reviewed() if i['doc'] == 'HM-8')
    before = manuals(world)[item['filename']]
    _, out = portal_commit(world, item, by='지식 관리자')
    status, rolled = world.api('POST', f"/api/kg/manuals/batches/{out['batch']}/rollback", {'by': 'user:me'})
    assert status == 200 and rolled['restored_batch'] == before['batch']
    assert manuals(world)[item['filename']]['batch'] == before['batch']


# ---------------------------------------------------------------- 비운 뒤 다시 채우기 — 미리 채운 시작 상태가 가리던 길(2026-11-22)
def empty_all(world, by='user:me'):
    """학생이 「지식 › 문서 등록」의 등록 이력에서 적재한 문서를 모두 되돌려 비운다(화면의 [되돌리기] — 최신 판부터, 문서 순서는 이력의 차례)."""
    while heads := [r for r in world.api('GET', '/api/kg/manuals')[1] if r.get('current') and r.get('status') == 'ACTIVE']:
        for r in heads:
            status, out = world.api('POST', f"/api/kg/manuals/batches/{r['batch']}/rollback", {'by': by})
            assert status == 200, (r['filename'], out)


def cooling_case(world):
    """HYD-01 쿨러 오염 → 냉각 성능 저하 경보 → 처리 건 c3_cooling(흐름 A) → 키 없는 PC의 AI 단계 한 번. 돌려줌 = (처리 건, AI 단계 행)."""
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.report('HYD-01')                      # 설비는 감지기가 경보를 내기 전에도 1초마다 보고한다 — 사건은 그 최신 상태 뒤에 열린다
    tags = world.plant.tags('HYD-01')
    _, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01', ts1=tags['TS1'], ce=tags['CE'])
    world.report()
    with world.reporting('HYD-01'):             # AI 단계가 도는 동안에도 설비는 1초마다 보고한다 — 원인 진단의 관측 구간이 비면 판단이 「근거 조회 불완전」으로 멈춰 이 시험이 재려는 까닭을 가린다
        assert world.runner('replay').poll_once() == 1
    return pid, world.row(pid, 'T_agent')


def test_학생이_비운_문서는_시작이_다시_채우지_않고_쿨러_판단은_원인_지식이_없다는_까닭으로_멈춘다(world, course_graph):
    """시작이 비운 문서를 다시 채우면 학생이 비운 뒤 포털로 다시 넣는 길이 가려진다. 빈 지식의 판단은 「진단 지식(T1)에 없는 원인 … diagnose 결과의
    원인 id를 쓰세요」라는 도구 거절 문장으로 멈췄다 — 고칠 것은 인자가 아니라 지식이다."""
    empty_all(world)
    assert manuals(world) == {}
    assert not course_graph.query('MATCH (n) WHERE n:FailureMode OR n:Cause OR n:Skill RETURN n.id AS id')   # 문서에서 온 지식이 0
    lines = ck.ensure(ck.http_call(world.url))
    assert len(lines) == 3 and all('이 PC에서 비운 문서라 그대로 둠' in line for line in lines), lines
    assert manuals(world) == {}
    pid, row = cooling_case(world)
    said = json.dumps(world._failure(row), ensure_ascii=False)
    assert row['status'] not in ('SUBMITTED', 'DONE') and '원인 지식이 아직 없습니다' in said and '지식 › 문서 등록' in said, said
    assert 'T1' not in said and 'diagnose' not in said, said


SOURCE_ID = re.compile(r'manual:[0-9a-f-]{36}:([0-9a-f]{64})')


def provenance_gaps(world, graph) -> list[str]:
    """지식 그래프의 모든 원문 인용(인용 칸 citation · 정비 기준 같은 속성 안의 anchor.source_id — 값에 든 원문 판본 id 전부)이 지금 적재된 문서의
    원문을 가리키는가: 그 판본이 지금 적재된 어느 문서의 지금 판 원문이고(되돌려 지운 문서 · 앞 판이 아님), 문서가 가진 노드면 그 문서 자신의 원문이며,
    보관소에 그 원문이 있고 그 바이트의 sha256 이 판본 id 의 것과 같다. 학생이 화면에서 출처를 누르면 이 원문이 열린다 — 엉뚱한 문서 · 없는 원문이면 가짜다."""
    import hashlib
    heads = {r['doc']: json.loads(r['receipt'])['source_id'] for r in graph.query(
        'MATCH (d:ManualIngestionDocument) WHERE d.head IS NOT NULL MATCH (b:ManualIngestionBatch {id: d.head}) RETURN d.id AS doc, b.receipt AS receipt')}
    live, gaps, checked = set(heads.values()), [], {}
    from procsvc import manual_graph
    # 문서가 넣는 지식 노드만(manual_graph.LABELS — 학생이 지식 지도 · 검토 화면에서 출처를 보는 것). 적재 기록(ManualIngestionBatch · Document)은 되돌리기 ·
    # 감사를 위해 옛 판의 원문 id 를 그대로 갖는 것이 맞다 — 출처로 보이는 지식이 아니다
    rows = graph.query('MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) AND any(k IN keys(n) WHERE n[k] IS :: STRING AND n[k] CONTAINS "manual:") '
                       'RETURN labels(n)[0] AS label, n.id AS id, n._manual_document AS owner, properties(n) AS props', labels=list(manual_graph.LABELS))
    for r in rows:
        text = json.dumps({k: v for k, v in r['props'].items() if k != 'id' and not k.startswith('_')}, ensure_ascii=False)
        for m in SOURCE_ID.finditer(text):
            sid, where = m.group(0), f"{r['label']} {r['id']}"
            if sid not in live:
                gaps.append(f'{where}: 인용한 원문 {sid}이 지금 적재된 어느 문서의 지금 판 원문도 아닙니다')
            elif r['owner'] and heads.get(r['owner']) != sid:
                gaps.append(f"{where}: 그 문서의 지금 판 원문 {heads.get(r['owner'])}이 아니라 {sid}을 인용합니다")
            if sid not in checked:
                # 학생이 출처를 누르면 여는 바로 그 경로(hitl.js originalUrl). 제공 문서는 UTF-8 글(.md)이라 받은 글을 다시 UTF-8 로 바꾸면 원본 바이트다
                status, original = world.api('GET', f'/api/kg/manuals/sources/{sid}/original')
                checked[sid] = status == 200 and isinstance(original, str) and hashlib.sha256(original.encode('utf-8')).hexdigest() == m.group(1)
            if not checked[sid]:
                gaps.append(f'{where}: 인용한 원문 {sid}이 보관소에 없거나 바이트가 판본 id 의 sha256 과 다릅니다')
    return sorted(set(gaps))


def test_비운_뒤_포털의_제공_문서로_다시_채우면_시작할_때와_같은_지식이고_쿨러_판단이_다시_된다(world, course_graph):
    before = owned(course_graph)
    old_sources = {r['source_id'] for r in manuals(world).values()}
    assert provenance_gaps(world, course_graph) == []
    empty_all(world)
    for item in ck.reviewed():                         # 화면의 제공 문서 줄을 하나씩: 적재된 같은 이름 문서가 없으니 새 문서로 올린다(보관소의 되돌린 같은 원문은 서버가 그 문서로 다시 쓴다)
        portal_commit(world, item, by='user:me')
    gap = owned_gap(before, owned(course_graph))       # 문서에서 온 지식(조치 방법 · 고장 유형 · 원인 · 근거 · 규칙 · 단계)과 실행 속성이 같다
    assert gap == [], chr(10).join(gap)
    # 같은 지식이어도 출처는 지금 적재된 문서의 원문이어야 한다(되돌려 지운 문서 · 보관소에 없는 원문을 가리키면 학생이 누른 출처가 엉뚱하다)
    assert provenance_gaps(world, course_graph) == [], provenance_gaps(world, course_graph)
    assert all(r['by'] == 'user:me' for r in manuals(world).values())
    # 같은 이름 · 같은 바이트로 다시 올린 문서는 되돌린 그 문서를 다시 쓴다(manual_api 올리기 — 보관소에 같은 원문이 쌓이지 않음) → 원문 id 도 처음과 같다
    assert {r['source_id'] for r in manuals(world).values()} == old_sources
    # 판정이 잡는지: 인용 하나를 지금 적재되지 않았고 보관소에도 없는 원문(다른 문서 id · 다른 바이트)으로 바꾸면 그 노드를 짚는다
    import hashlib
    stale = f'manual:{uuid.uuid4()}:{hashlib.sha256(b"not-a-loaded-original").hexdigest()}'
    [step] = course_graph.query('MATCH (s:Step) WHERE s.citation CONTAINS "manual:" RETURN s.id AS id, s.citation AS citation LIMIT 1')
    course_graph.query('MATCH (s:Step {id:$id}) SET s.citation = $bad', id=step['id'], bad=SOURCE_ID.sub(stale, step['citation']))
    caught = provenance_gaps(world, course_graph)
    assert any(step['id'] in g and stale in g for g in caught), caught
    course_graph.query('MATCH (s:Step {id:$id}) SET s.citation = $good', id=step['id'], good=step['citation'])
    assert provenance_gaps(world, course_graph) == []
    pid, row = cooling_case(world)
    assert row['status'] in ('SUBMITTED', 'DONE'), world._failure(row)


def recorded_recommendation(slot='c3_cooling/T_agent', case='COOLER_DEGRADATION'):
    """키 없는 PC가 재생하는 준비된 판단의 권장 조치(저장된 판단 등록 결과의 recommended) — 학생이 검토에서 뺄 절차를 고르는 데 쓴다."""
    from conftest import REPLAY_DIR
    from worker import ai_replay
    doc = ai_replay.Library(REPLAY_DIR, ai_replay.COURSE).load(ai_replay.course_key(slot, case))
    for run in doc['runs']:
        for e in run['events']:
            if e['kind'] == 'tool_end' and (e.get('tool') or '').endswith('submit_decision') and not e.get('is_error'):
                body = ai_replay._as_json((run.get('tool_outputs_full') or {}).get(e['tool_use_id']) or e.get('tool_output'))
                if not ai_replay._failed(body):
                    return body['document']['recommended']
    raise AssertionError('준비된 판단에 등록 결과가 없다')


def test_다시_채울_때_검토에서_뺀_후보_규칙은_쿨러_판단을_바꾼다(world, course_graph):
    """해피패스 판정: 학생이 검토에서 다른 선택을 하면 결과가 달라져야 한다. 준비된 판단이 권하는 절차를 후보로 내는 규칙을 검토 화면의
    [적재에서 제외]로 빼고 HM-8을 다시 채우면, 이 PC에서 다시 등록한 판단의 후보에 그 절차가 없다 — 그래서 키 없는 PC의 재생은 준비된 설명을
    이 처리 건에 쓰지 않고 그 까닭으로 멈춘다(재생모드.md 3절 5번). 2026-11-22 실측: 권장이 「팬 최대 운전」에서 「쿨러 핀 세척」으로 바뀜."""
    skill = recorded_recommendation()
    [sop] = [r['sop'] for r in course_graph.query('MATCH (k:Skill {id:$id}) RETURN k.sopId AS sop', id=skill)]
    hm8 = next(i for i in ck.reviewed() if i['doc'] == 'HM-8')
    choosing = [r['id'] for r in hm8['proposal']['knowledge']['rules'] if r.get('table') == 'dt:action-candidates' and sop in (r.get('outputs') or [])]
    assert choosing, f'{sop}를 후보로 내는 규칙이 검토본에 없다'
    status, out = world.api('POST', f"/api/kg/manuals/batches/{manuals(world)[hm8['filename']]['batch']}/rollback", {'by': 'user:me'})
    assert status == 200, out
    portal_commit(world, hm8, by='user:me', drop_rule=choosing)
    pid, row = cooling_case(world)
    said = json.dumps(world._failure(row), ensure_ascii=False)
    assert row['status'] not in ('SUBMITTED', 'DONE') and '지금 계산은' in said, said
    made = [d for d in world.main.book.values() if ((d.get('origin') or {}).get('process_scope') or {}).get('instance') == pid]
    assert made and all(skill not in {o['id'] for o in d['options']} for d in made), [[o['id'] for o in d['options']] for d in made]
