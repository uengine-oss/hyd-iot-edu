"""실전반 2회차 그래프 랩(공장 규모 + 구매팀 응용)의 강사 참조 시험 — 실제 별도 랩 DB에서 넣기 · 묻기 · 수정본 갈래 · 구매팀 응용을 판정한다. AI 호출과 촬영을 하지 않는다.

통합반 시험(reference/session2_graph_trials.py)의 도구(랩 DB 띄우고 지우기 · 화면 블록 읽기 · 유일 제약 걸음)를 그대로 쓰고, 기대 값은 제공 코드를 거치지 않고
자료 생성기의 정의에서 바로 센다(session2_factory_answers.literal · usage, session2_factory_graph.live_quotes).
판정:
- 제공 모델 = 설계 랩 강사 참조(E · 받은 날마다 견적을 따로)의 출력. 구매팀 질문 단계 앞에서는 공급사 · 견적을 잇는 관계 둘을 뺀 모델과 넣은 그래프가 같고, 그 단계 뒤에는 모델 전체와 같다.
- 수정본 갈래 남김 · 삭제마다 세 질문의 답이 독립 기대 값과 같고, 두 갈래의 답이 실제로 다르다. 구매팀 질문(질문 4)의 답이 독립 기대 값과 같다.
- 그럴듯하지만 틀린 선택마다 결과가 따라 바뀐다(공장 규모 자료의 사실과 구매팀 응용 — 자료는 바꾸지 않는다). 내 모델(견적을 하나만 담은 설계)로 돌리면 구매팀 질문의 답이 달라진다.
- 모델을 망가뜨리면(ID 중복 · 끝점 없음 · 관계 방향) 구조 검사가 잡고, 학생 ZIP과 완성본 ZIP을 새 폴더에 풀어 명령이 돈다.
이 시험이 만든 랩 DB 컨테이너는 라벨을 다시 확인한 뒤 익명 볼륨째 지운다.
사용: python reference/practical2_graph_trials.py <graph-lab 폴더> [--out <결과 json>]
"""
from pathlib import Path
import argparse
import copy
import json
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_labs as B
import data_session2 as D
import session2_answers as A
import session2_factory_answers as FA
import session2_factory_graph as XG
from lab_package import ROOT
from reference import session2_graph_trials as T
from reference.session2_graph_trials import instance, result, equal_answers, normalized, http, cards_of, command, put      # instance는 완성본 생성(build_session2_projects.completed)도 쓴다

BRANCH = B.GRAPH_LAB_INPUT['통합반']      # 제공 모델의 설비 쪽 갈래(실물을 나눔 · 붙은 자리까지 물리량) — 통합반 그래프 랩과 같다
ASK = B.GRAPH_ASK


def queries(folder, status=False, purchase=None):
    schema = T.schema_in_use(folder)
    return A.query_text([*[A.query_integrated(schema, status=status)[n] for n in (1, 2, 3)], purchase or XG.purchase_query(schema)])


def fill(folder, change='남김', later=True):
    """강사 참조 답을 빈 틀에 넣는다 — 쿼리는 지금 쓰는 모델의 스키마에서 이름 · 식별자 틀을 읽어 만든다. later=False = 구매팀 질문 단계 앞(공급사 · 견적을 잇는 관계 쿼리와 질문 4가 아직 없다)."""
    schema = T.schema_in_use(folder)
    load = A.load_student_answer(schema) + ('\n' + XG.load_later_answer(schema) if later else '')
    query = queries(folder) if later else A.query_text([A.query_integrated(schema)[n] for n in (1, 2, 3)])
    put(folder, {A.CONSTRAINT_FILE: A.constraint_answer(schema), '결과/load.cypher': load, '결과/update.cypher': A.update_integrated(change, schema, '실전반'),
                 '결과/query.cypher': query, '결과/스키마_추가.csv': A.addition_answer(change), '결과/정한_것.csv': B.chosen_text(XG.chosen(change))}, True)
    expectation(folder, purchase=later)


def finish(folder, change, purchase=True):
    """수정본을 반영한 뒤의 참조 답 — 기대 답을 반영 뒤의 답으로, 센서를 상태로 남기는 갈래는 질문 1이 센서의 상태도 돌려주게."""
    expectation(folder, after=change, purchase=purchase)
    schema = T.schema_in_use(folder)
    base = [A.query_integrated(schema, status=change == '남김')[n] for n in (1, 2, 3)]
    put(folder, {'결과/query.cypher': A.query_text(base + ([XG.purchase_query(schema)] if purchase else []))}, True)


def expect_rows(after=None, purchase=True, wide=False):
    """기대 답 줄 — 원자료에 적힌 그대로 센 독립 기대 값에서. after = 수정본을 반영한 갈래. wide = 질문 1에 「설비 전체」 센서까지 넣은 기대 답(틀린 선택 시험)."""
    exp = FA.literal(BRANCH)
    names = B.quantities_of(B.POLICY[BRANCH])
    status = {a[0]: a[8] for a in D.ASSETS}
    retired, retired_status = D.LAB_RETIRED
    code, tag, _ = D.LAB_SENSOR_REMOVED
    asked = ASK['sensors']
    seats = {k: v for k, v in exp['sensors_by_asset'][asked].items() if wide or k != '(설비 전체)'}
    gone = lambda t: after == '삭제' and (code, tag) == (asked, t)
    pairs = sorted((('설비 전체' if k == '(설비 전체)' else B.CANON_NAME[k]), t) for k, tags in seats.items() for t in tags if not gone(t))
    tags = sorted(t for _, t in pairs)
    props = exp['sensor_props']
    where = '입력/자료/센서_목록.csv'
    rows = [['1', asked, 'component+tag', ' · '.join(f'{c}={t}' for c, t in pairs), where + ' 붙은곳 · 태그 칸'],
            ['1', asked, 'tag+quantity', ' · '.join(f'{t}={names[props[f"{asked}:{t}"][0]][0]}' for t in tags), where + ' 태그 · 재는것 칸'],
            ['1', asked, 'tag+limit', ' · '.join(f'{t}=' + ('없음' if props[f'{asked}:{t}'][3] is None else '%g' % props[f'{asked}:{t}'][3]) for t in tags), where + ' 태그 · 한계 칸']]
    if after == '남김':
        rows.append(['1', asked, 'tag+status', ' · '.join(f'{t}={A.SENSOR_KEPT if (code, tag) == (asked, t) else "없음"}' for t in tags), f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/센서_변경.csv:3'])
    a = ASK['parts']
    parts = exp['parts_by_asset'][a]
    rows.append(['2', a, 'part', ' · '.join(sorted(p for p in parts.values() if p) + ['없음'] * sum(1 for p in parts.values() if not p)), '입력/자료/구성요소_목록.csv 교체부품 칸 · 입력/자료/품번_교차표.csv'])
    alive = lambda users: [u for u in users if not (after == '삭제' and u == retired)]
    state = lambda u: retired_status if (after and u == retired) else status[u]
    shared = alive(FA.usage(B.GRAPH_SHARED_PART))
    rows.append(['3', B.GRAPH_SHARED_PART, 'status', ' · '.join(state(u) for u in shared), '입력/자료/구성요소_목록.csv 교체부품 칸 · 입력/자료/설비_대장.csv 상태 칸' + (' · ' + B.retired_change_line() if after else '')])
    for alias in ASK['aliases']:
        (inner,) = sorted({c[0] for c in D.CROSS if c[1] == alias})
        rows.append(['3', alias, 'asset', ' · '.join(alive(FA.usage(inner))) or '없음', '입력/자료/품번_교차표.csv · 입력/자료/구성요소_목록.csv 교체부품 칸'])
    rows.append(['3', ASK['missing'], 'note', '원자료에 없는 품번', '입력/자료/예비품_목록.csv · 입력/자료/품번_교차표.csv에 없음'])
    if after:
        part, alias = D.LAB_ALIAS_ADDED[:2]
        rows.append(['3', alias, 'asset', ' · '.join(alive(FA.usage(part))), f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/품번_교차표_변경.csv:2 · 입력/자료/구성요소_목록.csv 교체부품 칸'])
    return rows + (XG.purchase_expect_rows() if purchase else [])


def expectation(folder, after=None, purchase=True, wide=False):
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(A.GRAPH_EXPECT_COLUMNS)
    for r in expect_rows(after, purchase, wide):
        w.writerow(r)
    head = (folder / 'app/features/expected.csv').read_text(encoding='utf-8').split('\n', 1)[0]      # 칸 뜻 머리는 받은 빈 틀의 줄 그대로
    (folder / 'app/features/expected.csv').write_text(head + '\n' + T.P.convert(buf.getvalue()), encoding='utf-8', newline='\n')


def off_rows(blocks):
    return [r for b in blocks if b['kind'] == 'compare' for r in b['rows'] if r['state'] != '같음']


def notes(blocks):
    return ' / '.join(str(b.get('text', '')) for b in blocks if b['kind'] == 'note')


def exported(folder):
    result(folder, 'export')
    return json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))


def copy_of(starter, work, name):
    folder = work / name / starter.name
    shutil.copytree(starter, folder, ignore=shutil.ignore_patterns('__pycache__', 'output', '.lab_connection.json'))
    return folder


def staged(graph, names):
    return dict(graph, rels=[r for r in graph['rels'] if r['type'] not in names])


def purchase_wrong(folder, schema):
    """구매팀 질문의 틀린 쿼리 — 자료는 그대로다. 걸리는 것은 랩 DB의 실제 답뿐이다."""
    out = []
    right = (folder / 'app/features/query.cypher').read_bytes()
    try:
        for name, kw, check in (
                ('기준일로 거르지 않은 쿼리', dict(as_of=False), lambda off: len(off) == 1 and XG.PURCHASE_ASK['alias'] in off[0]['key']),
                ('사내 품번으로만 찾는 쿼리', dict(aliases=False), lambda off: len(off) == 1 and XG.PURCHASE_ASK['alias'] in off[0]['key'])):
            put(folder, {'결과/query.cypher': queries(folder, purchase=XG.purchase_query(schema, **kw))}, True)
            off = off_rows(result(folder, 'purchase'))
            assert check(off), (name, off)
            out.append({'wrong': name, 'result': f'질문 4 대조 {len(XG.purchase_expect_rows())}줄 가운데 {len(off)}줄이 같음이 아님 — ' + ' / '.join(f'{r["key"]}: 기대 「{r["cells"][0][0]}」 · 실제 「{r["cells"][0][1]}」' for r in off)})
        head, body = XG.purchase_query(schema)
        offers = schema['links']['공급사-견적']
        turned = body.replace(f'-[:{offers}]->', f'<-[:{offers}]-')
        assert turned != body
        put(folder, {'결과/query.cypher': queries(folder, purchase=(head, turned))}, True)
        off = off_rows(result(folder, 'purchase'))
        assert len(off) == 3 and not any(XG.PURCHASE_ASK['missing'] in r['key'] for r in off), off
        out.append({'wrong': '공급사와 견적을 잇는 관계의 화살표를 거꾸로 적은 쿼리', 'result': f'공급사를 묻는 {len(off)}줄이 모두 같음이 아님 — 실제 「{off[0]["cells"][0][1]}」(없는 품번 줄만 같음)'})
        as_text = body.replace("date('", "('")      # 유효기한은 랩 DB에 날짜로 들어 있다 — 기준일을 글자로 적어 견주면 오류 없이 모든 견적이 빠진다
        assert as_text != body
        put(folder, {'결과/query.cypher': queries(folder, purchase=(head, as_text))}, True)
        shown = result(folder, 'purchase')
        off = off_rows(shown)
        assert len(off) == 3 and not any(XG.PURCHASE_ASK['missing'] in r['key'] for r in off), off
        texted = T.cards_of(shown, '날짜 속성을 글자와 견준 조건')      # 까닭을 화면이 말한다(받기 시험 가13) — 날짜로 견준 참조 쿼리에는 이 카드가 없다
        assert [c['title'] for c in texted] == [f"valid_until ↔ '{D.REF_DATE}'"], texted
        put(folder, {'결과/query.cypher': queries(folder, purchase=(head, body))}, True)
        assert not T.cards_of(result(folder, 'purchase'), '날짜 속성을 글자와 견준 조건')
        put(folder, {'결과/query.cypher': queries(folder, purchase=(head, as_text))}, True)
        assert T.http(folder, "MATCH (q:Quote) WHERE NOT q.valid_until IS :: DATE OR NOT q.quote_date IS :: DATE RETURN count(q)")[0][0] == 0
        out.append({'wrong': '기준일을 날짜가 아니라 글자로 적어 견준 쿼리', 'result': f'공급사를 묻는 {len(off)}줄이 모두 같음이 아님 — 실제 「{off[0]["cells"][0][1]}」(랩 DB의 유효기한은 날짜), 화면이 「날짜 속성을 글자와 견준 조건 — {texted[0]["title"]}」을 짚음'})
    finally:
        (folder / 'app/features/query.cypher').write_bytes(right)
    return out


def supply_wrong(folder, schema, graph, later):
    """구매팀 질문 단계의 넣기에서 틀린 선택 — 관계 하나만 씀 · 양 끝의 레이블을 바꿔 적음 · MERGE 대신 CREATE."""
    out = []
    load = folder / 'app/features/load.cypher'
    base = A.load_student_answer(schema)
    two = XG.load_later_answer(schema)
    offers, quotes = (schema['links'][x] for x in XG.LATER)
    blank = command(folder, 'run.py', 'supply', '--no-open')
    assert f'넣을 것: {offers}' in blank and '아직 없습니다' in blank, blank[-300:]
    asked = command(folder, 'run.py', 'purchase', '--no-open')
    assert '질문 4' in asked and '아직 없습니다' in asked, asked[-300:]
    result(folder, 'export')
    checked = command(folder, 'run.py', 'check', '--no-open', ok=False)
    assert '적어도 하나' in checked and offers in checked, checked[-500:]
    out.append({'wrong': '공급사 · 견적을 잇는 관계를 넣지 않고 저장 · 검사', 'result': '구조 검사 실패 — ' + next(x.strip() for x in checked.splitlines() if '적어도 하나' in x)[:140]})
    only = '\n'.join(two.split('\n\n')[1:])
    assert f'넣을 것: {quotes}' in only and offers not in only
    load.write_text(T.P.convert(base + '\n' + only), encoding='utf-8', newline='\n')
    one = command(folder, 'run.py', 'supply', '--no-open')
    assert f'넣을 것: {offers}' in one and '아직 없습니다' in one, one[-300:]
    waiting = notes(result(folder, 'status'))
    assert offers in waiting and quotes not in waiting.split('(')[1].split(')')[0], waiting
    out.append({'wrong': '관계 둘 가운데 견적과 부품을 잇는 것만 씀', 'result': f'넣기 화면이 「// 넣을 것: {offers}」 쿼리가 아직 없다고 말하고, 개수 화면은 {offers}만 아직 넣지 않은 관계로 알림'})
    back = two.replace(f'MERGE (a)-[r:{quotes}]->(b)', f'MERGE (b)-[r:{quotes}]->(a)')      # 견적과 부품을 잇는 관계만 화살표를 거꾸로 — 개수는 모델과 같다
    assert back != two
    load.write_text(T.P.convert(base + '\n' + back), encoding='utf-8', newline='\n')
    blocks = result(folder, 'supply')
    turned_cards = cards_of(blocks, '모델 파일과 다르게 이어진 관계')
    m = sum(1 for r in graph['rels'] if r['type'] == quotes)
    assert http(folder, f'MATCH ()-[r:{quotes}]->() RETURN count(r)')[0][0] == m
    assert blocks[0]['state'] == 'bad' and '다르게 이어진 관계' in blocks[0]['text'] and '이어졌습니다' not in blocks[0]['text'], blocks[0]
    assert [c['title'] for c in turned_cards] == [quotes] and f'거꾸로 {m}개' in json.dumps(turned_cards, ensure_ascii=False), turned_cards
    back = result(folder, 'reset')      # 그 쿼리 그대로 되돌리면 거꾸로 그대로 다시 들어간다 — 되돌리기 화면이 「모델 파일대로 돌아왔습니다」라고 하지 않는다(받기 시험 v63 나4)
    assert back[0]['state'] == 'bad' and '다르게 이어진 관계' in back[0]['text'] and '돌아왔습니다' not in json.dumps(back[0], ensure_ascii=False), back[0]
    assert [c['title'] for c in cards_of(back, '모델 파일과 다르게 이어진 관계')] == [quotes], back
    out.append({'wrong': '견적과 부품을 잇는 관계의 화살표를 거꾸로 넣음', 'result': f'개수는 모델과 같지만({quotes} {m}개) 넣기 화면이 「{blocks[0]["text"]}」로 끝남 — 거꾸로 {m}개. 그 쿼리 그대로 되돌리면 되돌리기 화면도 「{back[0]["text"]}」'})
    http(folder, f'MATCH ()-[r:{quotes}|{offers}]->() DELETE r')      # 다음 경우를 위해 이번에 넣은 관계를 비운다
    spec = schema['relations'][offers]
    turned = two.replace(f"(a:{spec['from']} {{id: row.a}}), (b:{spec['to']} {{id: row.b}}) MERGE (a)-[r:{offers}]", f"(a:{spec['to']} {{id: row.a}}), (b:{spec['from']} {{id: row.b}}) MERGE (a)-[r:{offers}]")
    assert turned != two
    load.write_text(T.P.convert(base + '\n' + turned), encoding='utf-8', newline='\n')
    blocks = result(folder, 'supply')
    short = cards_of(blocks, '모델보다 적게 들어간 관계')
    n = sum(1 for r in graph['rels'] if r['type'] == offers)
    assert blocks[0]['state'] == 'bad' and [c['badge'] for c in short] == [f'모델 {n}개 → 랩 DB 0개'], (blocks[0], short)
    out.append({'wrong': '공급사와 견적을 잇는 관계의 양 끝 레이블을 서로 바꿔 적음', 'result': f'오류 없이 끝나고 「모델보다 적게 들어간 관계」 {offers} 모델 {n}개 → 랩 DB 0개'})
    created = two.replace('MERGE (a)-[r:', 'CREATE (a)-[r:')
    assert created.count('CREATE (a)-[r:') == 2
    load.write_text(T.P.convert(base + '\n' + created), encoding='utf-8', newline='\n')
    blocks = result(folder, 'supply')
    assert blocks[0]['state'] == 'bad' and ('늘었습니다' in blocks[0]['text'] or '다른 관계' in blocks[0]['text']), blocks[0]
    twice = http(folder, f'MATCH ()-[r:{offers}]->() RETURN count(r)')[0][0]
    assert twice == 2 * n, (twice, n)
    out.append({'wrong': '관계를 MERGE 대신 CREATE로 넣음', 'result': f'넣기 화면이 실패로 끝남 — 「{blocks[0]["text"]}」, 랩 DB의 {offers} {twice}개(모델 {n}개)'})
    load.write_text(T.P.convert(base + '\n' + two), encoding='utf-8', newline='\n')
    return out


def trials(starter, work):
    import build_session2_projects as S
    records, usage, sensors = T.student_condition_selftest(starter, work, 'sources'), {}, {}
    (renamed, new_name), (retired, status) = D.LAB_RENAMED, D.LAB_RETIRED
    provided = json.loads((starter / 'data/model/graph.json').read_text(encoding='utf-8'))
    schema = json.loads((starter / 'data/model/schema.json').read_text(encoding='utf-8'))
    made_schema, made = (json.loads(T.P.convert(json.dumps(x, ensure_ascii=False))) for x in S.design_model(BRANCH, course='실전반', supply=FA.PROVIDED_SUPPLY))      # 설계 랩이 output/에 쓰는 글(이 폴더의 파일 이름)
    assert normalized(provided) == normalized(made) and schema == made_schema, '제공 모델이 설계 랩 강사 참조의 출력과 다름'
    sources = sorted({v.rsplit(':', 1)[0] for n in provided['nodes'] for k, v in n['props'].items() if k.endswith('_source')})      # 모델 파일의 출처 줄은 이 폴더에 실제로 있는 파일을 가리킨다
    assert sources and all((starter / s).is_file() for s in sources), ('모델 파일의 출처가 이 폴더에 없는 파일 이름', sources)
    count = lambda g, label: sum(1 for n in g['nodes'] if n['labels'] == [label])
    assert (count(provided, 'Asset'), count(provided, 'Supplier'), count(provided, 'Quote')) == (len(D.ASSETS), len(D.SUPPLIERS), len(D.QUOTES)), '설비 · 공급사 · 견적 수가 자료의 정의와 다름'
    later = [schema['links'][x] for x in XG.LATER]
    records.append({'provided_model': 'design-lab reference ' + BRANCH + ' · ' + FA.PROVIDED_SUPPLY, 'nodes': len(provided['nodes']), 'rels': len(provided['rels']),
                    'rels_before_purchase_step': len(staged(provided, later)['rels'])})
    legacy = FA.facts()['legacy']
    for change in ('남김', '삭제'):
        folder = copy_of(starter, work, change)
        command(folder, 'run.py', '--no-open')
        assert '실행할 쿼리가 없습니다' in command(folder, 'run.py', 'load', '--no-open', ok=False)
        fill(folder, change, later=False)
        with instance(folder) as state:
            records += T.constraint_trials(folder, provided) if change == '남김' else T.legacy_db_trials(folder, provided)
            loaded = result(folder, 'load')
            said = notes(loaded)
            assert loaded[0]['state'] == 'ok' and all(x in said for x in later) and all(f'data/equipment.csv:{i}' in said for i in legacy), (loaded[0], said)
            initial = exported(folder)
            assert normalized(initial) == normalized(staged(provided, later)), '구매팀 질문 단계 앞: 넣은 그래프가 그 관계 둘을 뺀 모델과 다름'
            assert result(folder, 'repeat')[0]['state'] == 'ok'
            equal_answers(result(folder, 'sensors'))
            equal_answers(result(folder, 'parts'))
            before = equal_answers(result(folder, 'usage'))
            if change == '남김':
                records.append({'factory_fact': '옛 코드 설비 줄', 'result': f'설비 표 {len(B.numbered("설비_대장.csv"))}줄 가운데 모델이 담은 {count(provided, "Asset")}줄만 내 설비 쿼리로 넘어가고, 넣기 화면이 넘기지 않은 줄(data/equipment.csv:{legacy[0]})을 알림'})
                expectation(folder, purchase=False, wide=True)      # 틀린 선택: 질문 1의 기대 답에 「설비 전체」 센서까지 넣음(질문은 구성 요소마다 붙은 센서를 묻는다)
                off = off_rows(result(folder, 'sensors'))
                assert len(off) == 3 and all(r['key'].startswith(ASK['sensors']) for r in off), off
                records.append({'wrong': '질문 1의 기대 답에 붙은곳이 「설비 전체」인 센서까지 넣음', 'result': f'질문 1 대조 3줄이 모두 다름 — 쿼리는 설비 → 구성 요소 → 센서 길만 따라가 그 센서를 돌려주지 않는다(기대 「…{off[0]["cells"][0][0][-28:]}」)'})
                expectation(folder, purchase=False)
                records += supply_wrong(folder, T.schema_in_use(folder), provided, later)
                back = result(folder, 'reset')      # CREATE로 겹쳐 넣은 관계를 비우고 참조 쿼리로 다시 넣는다
                assert back[0]['state'] == 'ok' and '모델 파일대로 돌아왔습니다' in back[0]['detail'], back[0]
            # 수정본 반영
            decisions = folder / 'app/features/decisions.csv'
            filled = decisions.read_bytes()
            point = B.GRAPH_POINTS['통합반'][0 if change == '남김' else 1]
            lines = filled.decode('utf-8').rstrip('\n').split('\n')
            at = next(k for k, x in enumerate(lines) if x.startswith(point + ','))
            decisions.write_text('\n'.join(lines[:at] + [point + ',,,'] + lines[at + 1:]) + '\n', encoding='utf-8', newline='\n')
            out = command(folder, 'run.py', 'update', '--no-open', ok=False)
            assert 'decisions.csv:' in out and point in out, out[-500:]
            decisions.write_bytes(filled)
            records.append({'empty_decision': 'update', 'stopped_on': point})
            update = result(folder, 'update')
            assert update[0]['kind'] == 'verdict' and update[0]['state'] == 'ok', update[0]
            shown = {c['title']: c['badge'] for c in cards_of(update, '바뀐 노드')}
            five = [D.LAB_RENAMED[0], D.LAB_RETIRED[0], ':'.join(D.LAB_SENSOR_LIMIT[:2]), ':'.join(D.LAB_SENSOR_REMOVED[:2]), D.LAB_ALIAS_ADDED[0]]
            assert all(x in shown for x in five) and (sorted(shown) == sorted(five) if change == '남김' else shown[retired] == shown[five[3]] == '사라짐'), shown
            after = json.loads((folder / 'output/after_update.json').read_text(encoding='utf-8'))
            props = {n['props']['id']: n['props'] for n in after['nodes']}
            (lc, lt, limit, _), (part, alias, *_) = D.LAB_SENSOR_LIMIT, D.LAB_ALIAS_ADDED
            assert props[renamed]['name'] == new_name and props[f'{lc}:{lt}']['limit'] == float(limit) and props[part]['other_codes'].count(alias) == 1
            assert (props[retired]['status'] == status and props[five[3]]['status'] == A.SENSOR_KEPT) if change == '남김' else (retired not in props and five[3] not in props)
            assert count(after, 'Part') == count(provided, 'Part') and count(after, 'Quote') == count(provided, 'Quote')      # 공용 대상과 공급 쪽은 어느 갈래에서도 남는다
            finish(folder, change, purchase=False)
            usage[change], sensors[change] = equal_answers(result(folder, 'usage')), equal_answers(result(folder, 'sensors'))
            assert usage[change] != before, (change, '수정본을 반영해도 사용 설비 조회의 답이 그대로')
            # 구매팀 질문 단계
            if change == '삭제':      # 관계를 넣기 전에 묻는 쿼리부터 쓰면: 공급사가 이어져 있지 않아 답이 없다
                finish(folder, change)
                asked = command(folder, 'run.py', 'purchase', '--no-open')
                off = off_rows(json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks'])
                assert len(off) == 3, (off, asked[-300:])
                records.append({'wrong': '공급사 · 견적을 잇는 관계를 넣기 전에 질문 4를 물음', 'result': f'공급사를 묻는 3줄이 같음이 아님 — 실제 「{off[0]["cells"][0][1]}」'})
            put(folder, {'결과/load.cypher': A.load_student_answer(T.schema_in_use(folder)) + '\n' + XG.load_later_answer(T.schema_in_use(folder))}, True)
            nodes_before = http(folder, 'MATCH (n) RETURN count(n)')[0][0]
            supplied = result(folder, 'supply')
            assert supplied[0]['state'] == 'ok' and any(b['kind'] == 'graph' for b in supplied), supplied[0]
            assert http(folder, 'MATCH (n) RETURN count(n)')[0][0] == nodes_before, '구매팀 관계 넣기가 노드를 바꿈(수정본으로 지운 것이 되살아남)'
            now = exported(folder)
            assert sorted(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in now['rels'] if r['type'] in later) == sorted(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in provided['rels'] if r['type'] in later)
            finish(folder, change)
            answers = equal_answers(result(folder, 'purchase'))
            shown = result(folder, 'purchase')
            assert any(b['kind'] == 'graph' and b['title'].startswith('쿼리가 따라간 길') for b in shown) and sum(1 for b in shown if b['kind'] == 'table' and b['title'].startswith('같은 값')) == 3, [b.get('title') for b in shown]
            if change == '남김':
                records += purchase_wrong(folder, T.schema_in_use(folder))
                assert result(folder, 'repeat')[0]['state'] == 'ok'      # 모델을 한 번 더 넣어도(공급 관계까지) 그대로
            records.append({'change': change, 'nodes_after_update': len(after['nodes']), 'final_nodes': len(now['nodes']), 'final_rels': len(now['rels']), 'usage_before': before, 'usage_after': usage[change],
                            'sensors_after': sensors[change], 'purchase': answers})
            result(folder, 'export')
            result(folder, 'check')
            if change == '남김':
                saved = (folder / 'output/graph.json').read_bytes()
                for broken in ('duplicate-id', 'missing-endpoint', 'reverse-direction'):
                    damaged = copy.deepcopy(now)
                    if broken == 'duplicate-id':
                        damaged['nodes'].append(copy.deepcopy(damaged['nodes'][0]))
                    elif broken == 'missing-endpoint':
                        damaged['rels'][0]['b'] = 'not-in-graph'
                    else:
                        damaged['rels'][0]['a'], damaged['rels'][0]['b'] = damaged['rels'][0]['b'], damaged['rels'][0]['a']
                    (folder / 'output/graph.json').write_text(json.dumps(damaged), encoding='utf-8')
                    assert '구조 확인 필요' in command(folder, 'run.py', 'check', '--no-open', ok=False)
                    records.append({'broken': broken, 'rejected': True})
                (folder / 'output/graph.json').write_bytes(saved)
        print(change + ' 실행·정리 통과', flush=True)
    assert usage['남김'] != usage['삭제'] and sensors['남김'] != sensors['삭제'], '수정본의 두 갈래가 같은 답을 냄'
    records.append({'decision': '목록에서 빠진 센서', 'changed_answers': {k: [sensors['남김'].get(k), sensors['삭제'].get(k)] for k in sensors['남김'] if sensors['남김'][k] != sensors['삭제'].get(k)}})
    records.append({'decision': '불용 결정 설비', 'changed_answers': {k: [usage['남김'].get(k), usage['삭제'].get(k)] for k in usage['남김'] if usage['남김'][k] != usage['삭제'].get(k)}})
    records += my_model(starter, work, answers)
    print('내 모델 실행·정리 통과', flush=True)
    return records


def my_model(starter, work, provided_answers):
    """설계 실습에서 견적을 하나만 담기로 한 내 모델(셋째 결정의 다른 갈래)로 같은 랩을 돈다 — 넣은 그래프가 내 모델과 같고, 구매팀 질문의 답이 제공 모델과 달라진다."""
    import build_session2_projects as S
    folder = copy_of(starter, work, '내모델')
    other = next(x for x in FA.SUPPLY_BRANCHES if x != FA.PROVIDED_SUPPLY)
    schema, graph = S.design_model(BRANCH, course='실전반', supply=other)
    mine = folder / 'app/features/model'
    mine.mkdir(parents=True)
    for name, value in (('schema.json', schema), ('graph.json', graph)):
        (mine / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    with instance(folder):
        fill(folder, '남김')
        result(folder, 'constraints')
        assert result(folder, 'load')[0]['state'] == 'ok'
        assert normalized(exported(folder)) == normalized(graph)
        assert result(folder, 'supply')[0]['state'] == 'ok'
        for a in ('sensors', 'parts', 'usage'):
            equal_answers(result(folder, a))
        off = off_rows(result(folder, 'purchase'))
        assert off and all(XG.PURCHASE_ASK['part'] in r['key'] for r in off), off
    return [{'my_model': f'design-lab output with the third decision 「{other}」', 'loaded_equals_my_model': True, 'nodes': len(graph['nodes']), 'rels': len(graph['rels']),
             'purchase_rows_changed': {r['key']: [r['cells'][0][0], r['cells'][0][1]] for r in off}}]


def packages(starter, work):
    records = []
    target = work / 'new-zip'
    with zipfile.ZipFile(starter.with_suffix('.zip')) as z:
        z.extractall(target)
    command(target / 'graph-lab', 'run.py', '--no-open')
    records.append({'package': 'new-zip', 'actions': ['sources']})
    done = next((p for p in (starter.parent / 'graph-lab-completed.zip', starter.parent.parent / '완성본/graph-lab-completed.zip') if p.is_file()), None)
    if done is None:
        raise FileNotFoundError('완성본 ZIP(graph-lab-completed.zip)을 찾지 못했습니다 — --completed로 함께 만듭니다.')
    target = work / 'completed-zip'
    with zipfile.ZipFile(done) as z:
        z.extractall(target)
    folder = target / 'graph-lab'
    actions = ['constraints', 'load', 'update', 'supply', 'sensors', 'parts', 'usage', 'purchase', 'export', 'check']
    with instance(folder):
        same = 0
        for action in actions:
            blocks = result(folder, action)
            if action in ('sensors', 'parts', 'usage', 'purchase'):
                same += len(equal_answers(blocks))
    records.append({'package': 'completed-zip', 'actions': ['db', *actions], 'answers_same_rows': same})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / '작업/검사/session2-projects/practical-graph-results.json')
    args = parser.parse_args()
    base = ROOT / '작업/검사/session2-projects'
    base.mkdir(parents=True, exist_ok=True)
    D.require('실전반')
    with tempfile.TemporaryDirectory(prefix='practical-graph-trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base.resolve()) and work != base.resolve()
        starter = args.folder.resolve()
        records = trials(starter, work) + packages(starter, work)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({'kind': '실제 별도 DB·강사 참조; 학생 AI 또는 GUI 시험 아님', 'records': records, 'created_containers_removed': True}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 검증 통과 — {args.out}')


if __name__ == '__main__':
    main()
