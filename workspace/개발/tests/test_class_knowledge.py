"""시작 7단계 수업 지식(scripts/class_knowledge.py) — 정본은 강사 서명 묶음 하나(결정 5): 시작은 그 검토본(절 · 절차 · 지식 · 검토한 연결)을
그대로 넣고, 4회차에 같은 문서를 제공 문서 캐시(AI 0)로 다시 넣어 제안 그대로 검토 완료하면 같은 지식이다. 옛 시작 사본이 넣은 판은 다음 시작 때
묶음 판으로 바꿔 넣고, 학생이 다시 넣은 판은 건드리지 않는다.
실제 process(world — 시작이 끝난 학생 PC: kg-seed + 이 스크립트의 적재)와 실제 그래프로 판정한다."""
import base64
import json
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
    assert ck.decide(ck.reviewed()[0], current) == what


def test_지금_묶음_판이_적재돼_있으면_그대로_둔다():
    item = ck.reviewed()[0]
    assert ck.decide(item, {'by': '아무 글', 'review_method': item['review_method'], 'provided_revision': item['revision']}) == 'keep'


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
    """포털 지식 관리와 같은 길: 같은 문서로 다시 올리기(문서 개정) → 제공 문서 캐시 추출(AI 0) → 결과 → 제안 그대로 검토 완료 → 적재."""
    current = manuals(world)[item['filename']]
    status, preview = world.api('POST', '/api/kg/manuals/preview', {'filename': item['filename'], 'document_id': current['document_id'],
                                                                     'data': base64.b64encode(item['raw']).decode()})
    assert status == 200, preview
    sid = preview['source_id']
    status, started = world.api('POST', f'/api/kg/manuals/sources/{sid}/extractions', {'request_id': str(uuid.uuid4())})
    assert status == 200, started
    assert world.poll() == []                     # 서명 제안은 제출된 결과로 들어간다 — 엔진 폴링 한 바퀴가 결과 검사 · 완료를 한다(실행 서비스의 2초 폴링)
    status, result = world.api('GET', f"/api/kg/manuals/sources/{sid}/extractions/{started['instance']}")
    assert status == 200 and result['preview'], result
    reviewed = deepcopy(result['preview'])
    if drop_rule:
        reviewed['knowledge']['rules'] = [r for r in reviewed['knowledge']['rules'] if r['id'] != drop_rule]
    request = dict(reviewed, links={p['id']: p['link'] for p in reviewed['procedures'] if p.get('link')}, by=by, reviewed=True)
    status, changes = world.api('POST', '/api/kg/manuals/changes', request)
    assert status == 200, changes
    status, out = world.api('POST', '/api/kg/manuals/commit', request)
    assert status == 200, out
    return changes, out


def owned(graph):
    """적재된 문서들이 가진 지식 그래프(노드 id · 종류 · 실행에 쓰이는 속성) — 판본 · 배치 · 인용 위치처럼 적재마다 달라지는 칸은 뺀다."""
    rows = graph.query(
        'MATCH (d:ManualIngestionDocument) WHERE d.head IS NOT NULL WITH d MATCH (n) WHERE n._manual_document = d.id '
        'AND (n:Skill OR n:FailureMode OR n:Cause OR n:Evidence OR n:Rule OR n:Step) '
        'RETURN labels(n)[0] AS label, n.id AS id, properties(n) AS props')
    keep = lambda props: {k: v for k, v in props.items() if k not in ('source_id', 'citation', '_manual_document') and not k.startswith('_')}
    return {(r['label'], r['id'], json.dumps(keep(r['props']), sort_keys=True, ensure_ascii=False)) for r in rows}


def test_4회차에_같은_문서를_제안_그대로_다시_넣으면_시작_지식과_같은_지식이다(world, course_graph):
    """결정 5: 시작이 넣은 지식 = 4회차 재적재(서명 묶음 · AI 0) 결과. 빠지는 노드가 없고 남는 노드 · 실행 속성이 같다."""
    item = next(i for i in ck.reviewed() if i['doc'] == 'HM-8')
    before = owned(course_graph)
    changes, out = portal_commit(world, item, by='지식 관리자')
    assert changes['removed'] == [] and out['procedures'] == len(item['proposal']['procedures'])
    assert owned(course_graph) == before


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
    status, rolled = world.api('POST', f"/api/kg/manuals/batches/{out['batch']}/rollback", {'by': '수강생'})
    assert status == 200 and rolled['restored_batch'] == before['batch']
    assert manuals(world)[item['filename']]['batch'] == before['batch']
