"""2회차 실습3·4 강사 참조 검증. 학생/AI 수행 증거와 구별한다.

1) 독립 대조: 생성기의 정답 구조(data_session2.TRUTH, CSV를 다시 읽지 않음)에서 질문별 기대 답을 계산하고,
   원자료 CSV를 해석해 만든 참조 그래프(build_labs.reference_model)의 답과 비교한다.
   실전반은 공급 조건마다 값의 출처(견적 줄 · 승인 등록 줄 · 기준일 — 실습3 9단계)도 대조하고, 실습4 입력 모델의 출처 줄을
   실습4 폴더 `입력/자료/`의 실제 CSV 줄에서 다시 읽어 값이 같은지 본다.
   실전반 실습4 조회 갈래 ㄱ · ㄴ은 실습4 입력 모델(갈래 ㄴ)에서 같은 답이 나오는지 함께 대조한다.
2) Neo4j 실행(--offline이 없을 때): 이 스크립트가 만든 별도 교육용 컨테이너에 참조 그래프를 적재 → 질의 → 같은 적재 재실행
   를 실습3 갈래마다, 실전반은 실습4 입력 모델(ㄴ) 위에서 조회 갈래마다 실제로 하고 개수·답·출처를 확인한다. 끝나면 그 컨테이너와 이름 없는 볼륨만 지운다.
   통합반 실습4(적재 · 조회 · 수정본 갈래 남김 · 삭제)의 실제 DB 실행은 학생 폴더로 도는 reference/session2_graph_trials.py 한 곳이 한다.
과정마다 그 과정의 규모로 돈다(통합반 = 실습 랩 규모, 실전반 = 공장 규모 — data_session2.for_course).
갈래: 실습3 통합반 A · B · C · E, 실전반 A · B · ㄴ · ㄷ · ㄹ · ㅁ(build_labs.REFERENCE_BRANCHES, ㄹ · ㅁ은 ㄴ에 견적 갈래만 다름 — 대응은 reference/실전반/README.md).
      실습4 실전반 조회 갈래 ㄱ · ㄴ(build_labs.LAB4_QUERY_BRANCHES — PR-07 7.4 정보를 빼고 · 함께 돌려줌).
사용: python verify_reference.py [--offline]
"""
from pathlib import Path
from collections import defaultdict
import csv
import json
import re
import subprocess
import sys
import time
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data_session2 as D          # noqa: E402
import build_labs as B             # noqa: E402

REPORT = HERE/'reference/session2_검증.json'
EXPECT = {'통합반': HERE/'reference/통합반/기대답.json', '실전반': HERE/'reference/실전반/기대답.json'}
# 통합반(실습 랩 규모): 사내 품번 · 예전 품번 · 줄여 쓴 표기 · 제조사 품번 · 원자료에 없는 품번.
PROBES = {'통합반': ['P-PMP-SEAL', 'P-PMP-SEAL-HT', 'P-PMP-SEAL-22', 'P-FAN-BRG', 'P-CLR-CORE', 'P-CLR-PLT', 'P-RTN-FLT', 'P-SUC-STR', 'P-CPL-ELM', 'P-VLV-COIL', 'P-HYD-OIL',
                   'PS-4510', 'PMP-SEAL', 'P_PMP_SEAL', 'FB-6205', 'RF-10', 'HI-RF-10', 'HI-SK-45A', 'HI-GS-22', 'P-PMP-SEAL-X'],
          '실전반': ['P-PMP-SEAL', 'P-PMP-SEAL-HT', 'P-CLR-CORE', 'P-CLR-PLT', 'P-ACC-BLD', 'P-RTN-FLT', 'P-FAN-BRG', 'PS-4510', 'PMP-SEAL', 'P-PMP-SEAL-X']}


# ───────────── 기대 답(생성 정답 구조에서) ─────────────
def supply_row(branch, supplier, approved, price, defect, lead, extra, pending):
    """공급 조건 한 줄. 갈래 ㄴ은 PR-07 7.4 비교 가산 비용, ㄷ은 미결(확인 요청) 표시를 덧붙인다(ㄹ · ㅁ은 승인 판단이 ㄴ)."""
    branch = B.supply_branch(branch)[0]
    row = [supplier, approved, price, defect, lead]
    if branch == 'ㄴ':
        row.append(extra)
    if branch == 'ㄷ':
        row.append(bool(pending))
    return row


def code_to_parts(code):
    """조회 표기 → 사내 품번 후보(정렬). 없으면 빈 목록, 같은 표기를 가진 품번이 여럿이면 여럿."""
    if code in D.TRUTH['parts']:
        return [code]
    return sorted({c[0] for c in D.CROSS if c[1] == code})


def expected(course, branch):
    t = D.TRUTH
    pol = B.policy(branch, course == '실전반')
    sensors_by_asset = {}
    quantity_members = defaultdict(set)
    sensor_props = {}
    usage = defaultdict(lambda: {'assets': set(), 'components': set()})
    kinds = any(s['kind'] != 'measured' for a in t['assets'].values() for s in a['sensors'].values())   # 실측뿐인 자료(실습 랩 규모)의 모델은 kind를 두지 않는다
    for aid, a in t['assets'].items():
        per = defaultdict(list)
        for tag, s in a['sensors'].items():
            per[s['component'] or '(설비 전체)'].append(tag)
            q = 'quantity:TS3' if (pol[3] == '자리' and s['quantity'] == 'quantity:TS1' and s['component'] == 'tank') else s['quantity']   # 붙은 자리까지: 탱크의 유온계는 탱크 유온
            q = D.QUANTITY_KINDS[q][0] if pol[3] == '종류' else q   # 재는 값의 종류
            quantity_members[q].add(f'{aid}:{tag}')
            sensor_props[f'{aid}:{tag}'] = [q, s['unit'], s['normal'], s['limit'], s['direction'], s['kind'] if kinds else None]
        sensors_by_asset[aid] = {k: sorted(v) for k, v in sorted(per.items())}
        for key, part in a['components'].items():
            if part:
                usage[part]['assets'].add(aid)
                usage[part]['components'].add(f'{aid}:{key}')
    probes = {}
    for code in PROBES[course]:
        found = []
        for pid in code_to_parts(code):
            entry = {'part': pid, 'assets': sorted(usage[pid]['assets']), 'components': sorted(usage[pid]['components'])}
            if course == '실전반':
                entry['supply'] = sorted(supply_row(branch, s, v['approved_B' if branch == 'B' else 'approved_A'], v['price_manwon'], v['defect_rate'], v['lead_days'],
                                                    float(D.PR74_EXTRA_MANWON) if v['pr74'] else None, v['pr74'] and not v['condition'])
                                         for (s, p), v in t['supply_modes'][B.supply_branch(branch)[1]].items() if p == pid)
            found.append(entry)
        probes[code] = None if not found else (found[0] if len(found) == 1 else {'candidates': found})
    out = {'sensors_by_asset': sensors_by_asset, 'quantity_members': {k: sorted(v) for k, v in sorted(quantity_members.items())},
           'sensor_props': dict(sorted(sensor_props.items())), 'probes': probes}
    if course == '통합반':   # 자리마다 실물(지금 · 지난) — 자리와 실물을 나눈 갈래만 실물을 따로 둔다
        units = {f'{aid}:{key}': [[s, True]] for (aid, key), s in sorted(D.SERIALS.items())}
        units[f'{D.REMOVED_PUMP[0]}:{D.REMOVED_PUMP[1]}'].append([D.REMOVED_PUMP[2], False])
        out['units'] = {k: sorted(v) for k, v in units.items()} if pol[2] == '나눔' else {}
    if course == '통합반':   # 실습4 「설비별 교체 부품 조회」: 설비 → 구성 요소 → 교체 부품(없으면 None)
        out['parts_by_asset'] = {aid: dict(sorted(a['components'].items())) for aid, a in sorted(t['assets'].items())}
    else:                    # 실습3 「값마다 출처 남기기」: 생성 순서에서 센 줄(CSV를 다시 읽지 않음)
        out['supply_sources'] = {f'{s}→{p}': [D.line_ref(D.QUOTE_FILE, v['quote_line']), D.line_ref(D.AVL_FILE, v['avl_line']) if 'avl_line' in v else None, D.REF_DATE]
                                 for (s, p), v in sorted(t['supply_modes'][B.supply_branch(branch)[1]].items())}
    return out


# ───────────── 참조 그래프에서 같은 답(메모리 순회) ─────────────
def answers_from_graph(course, branch, graph):
    labels = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    by_type = defaultdict(list)
    for r in graph['rels']:
        by_type[r['type']].append(r)
    owner = {r['b']: r['a'] for r in by_type['HAS_COMPONENT']}
    sensors_by_asset = defaultdict(lambda: defaultdict(list))
    for r in by_type['MONITORED_BY']:
        src = r['a']
        if labels[src] == 'Asset':
            sensors_by_asset[src]['(설비 전체)'].append(props[r['b']]['tag'])
        else:
            sensors_by_asset[owner[src]][src.split(':', 1)[1]].append(props[r['b']]['tag'])
    quantity_members = defaultdict(set); sensor_props = {}
    for r in by_type['OBSERVES']:
        quantity_members[r['b']].add(r['a'])
        s = props[r['a']]
        sensor_props[r['a']] = [r['b'], s['unit'], s.get('normal'), s.get('limit'), s.get('limit_direction'), s.get('kind')]   # kind가 없는 모델은 None — 기대 답(expected)도 실측뿐인 자료에서 None
    usage = defaultdict(lambda: {'assets': set(), 'components': set()})
    for r in by_type['USES_PART']:
        usage[r['b']]['assets'].add(owner[r['a']]); usage[r['b']]['components'].add(r['a'])
    probes = {}
    for code in PROBES[course]:
        hits = [i for i, p in props.items() if labels[i] == 'Part' and i == code] or \
               sorted(i for i, p in props.items() if labels[i] == 'Part' and code in p.get('other_codes', []))
        found = []
        for pid in hits:
            entry = {'part': pid, 'assets': sorted(usage[pid]['assets']), 'components': sorted(usage[pid]['components'])}
            if course == '실전반':
                entry['supply'] = sorted(supply_row(branch, r['a'].split(':', 1)[1], r['props']['approved'], r['props']['price_manwon'], r['props']['defect_rate'], r['props']['lead_days'],
                                                    r['props'].get('compare_extra_manwon'), 'pending_check' in r['props'])
                                         for r in by_type['SUPPLIES'] if r['b'] == pid)
            found.append(entry)
        probes[code] = None if not found else (found[0] if len(found) == 1 else {'candidates': found})
    out = {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors_by_asset.items())},
           'quantity_members': {k: sorted(v) for k, v in sorted(quantity_members.items())}, 'sensor_props': dict(sorted(sensor_props.items())), 'probes': probes}
    if course == '통합반':
        parts = defaultdict(dict)
        for r in by_type['HAS_COMPONENT']:
            parts[r['a']][r['b'].split(':', 1)[1]] = next((u['b'] for u in by_type['USES_PART'] if u['a'] == r['b']), None)
        out['parts_by_asset'] = {a: dict(sorted(d.items())) for a, d in sorted(parts.items())}
        units = defaultdict(list)
        for r in by_type['INSTALLED_UNIT']:
            units[r['a']].append([props[r['b']]['serial'], r['props']['current']])
        out['units'] = {k: sorted(v) for k, v in sorted(units.items())}
    else:
        out['supply_sources'] = {f'{r["a"].split(":", 1)[1]}→{r["b"]}': [r['props'].get('quote_source'), r['props'].get('approval_source'), r['props'].get('as_of')]
                                 for r in sorted(by_type['SUPPLIES'], key=lambda r: (r['a'], r['b']))}
    return out


def source_rows(graph, folder):
    """출처 줄을 실제 파일에서 다시 읽는다: 견적 줄의 공급사 · 품번 · 단가 · 불량률 · 납기 · 견적일, 승인 등록 줄의 공급사 · 품번이 그 관계와 같은지.
    단위를 바꾼 불량률 · 납기(숫자만이 아닌 칸)는 원래 표기가 *_original에 그대로 있는지, 바꾸지 않은 칸에는 *_original이 없는지도 본다(실습3 8단계)."""
    def numbered(name):
        with (folder/name).open(encoding='utf-8-sig', newline='') as f:
            return {D.line_ref(name, i): r for i, r in enumerate(csv.DictReader(f), 2)}
    quotes, avl = numbered(D.QUOTE_FILE), numbered(D.AVL_FILE)
    names = {n['props']['id']: n['props'].get('name') for n in graph['nodes']}
    bad = []
    for r in graph['rels']:
        if r['type'] != 'SUPPLIES':
            continue
        sup, part, p = r['a'].split(':', 1)[1], r['b'], r['props']
        q = quotes.get(p.get('quote_source'))
        fail, lead = (q or {}).get('불량률', ''), (q or {}).get('납기(일)', '')
        if (q is None or not q['공급사'].startswith(sup) or q['견적일'] != p['quote_date'] or float(q['단가(만원)']) != p['price_manwon']
                or (float(fail.rstrip('%')) / (100 if fail.endswith('%') else 1)) != p['defect_rate']
                or (int(lead[:-1]) * 7 if lead.endswith('주') else int(lead)) != p['lead_days']
                or (q['품번'] != part and q['품번'] not in {x[1] for x in D.PARTS if x[0] == part})):
            bad.append(f'{sup}→{part}: 견적 출처 {p.get("quote_source")}')
        for col, key in [('불량률', 'defect_rate_original'), ('납기(일)', 'lead_days_original')]:
            raw = (q or {}).get(col, '')
            if p.get(key) != (None if re.fullmatch(r'\d+(\.\d+)?', raw) else raw):
                bad.append(f'{sup}→{part}: {col} 원래 표기 {raw!r} ≠ {key} {p.get(key)!r}')
        a = avl.get(p.get('approval_source'))
        if a is None or a['공급사'] != sup or a['품번'] != part:
            bad.append(f'{sup}→{part}: 승인 출처 {p.get("approval_source")}')
        if p.get('as_of') != D.REF_DATE:
            bad.append(f'{sup}→{part}: 기준일 {p.get("as_of")}')
        if names.get(r['a']) != sup:
            bad.append(f'{sup}: 공급사 이름 {names.get(r["a"])} ≠ 승인 목록의 이름')
    return bad


def diff(a, b, path=''):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f'{path}/{k}: 한쪽에만 있음')
            else:
                out += diff(a[k], b[k], f'{path}/{k}')
    elif a != b:
        out.append(f'{path}: 기대 {a!r} ≠ 참조 {b!r}')
    return out


def offline():
    report = {}
    for course in ['통합반', '실전반']:
        report[course] = {}
        answers = {}
        with D.for_course(course):
            for branch in B.REFERENCE_BRANCHES[course]:
                graph = B.reference_model(course == '실전반', branch)[1]
                exp = expected(course, branch); got = answers_from_graph(course, branch, graph)
                d = diff(exp, got)
                report[course][branch] = {'nodes': len(graph['nodes']), 'rels': len(graph['rels']), 'mismatch': d}
                answers[branch] = exp
        EXPECT[course].write_text(json.dumps(answers, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    # 실전반 실습4 조회 갈래: 실습4 입력 모델(갈래 ㄴ) 하나에서 갈래마다 돌려줄 열만 달리해 같은 기대 답이 나오는지(ㄱ = 기대 답 A의 공급 조건 열, ㄴ = 기대 답 ㄴ)
    graph = B.reference_model(True, B.GRAPH_LAB_INPUT['실전반'])[1]
    report['실전반']['실습4'] = {g: {'input_branch': B.GRAPH_LAB_INPUT['실전반'], 'expected_key': key,
                                   'mismatch': diff(expected('실전반', key)['probes'], answers_from_graph('실전반', key, graph)['probes'])}
                               for g, key in B.LAB4_QUERY_BRANCHES.items()}
    lab4_sources = B.OUT/'실전반/실습/02회차/랩'/B.LAB4/'입력/자료'
    report['실전반']['실습4']['출처 줄'] = {'folder': lab4_sources.relative_to(B.ROOT).as_posix(),
                                        'mismatch': source_rows(json.loads((lab4_sources.parent/'graph.json').read_text(encoding='utf-8')), lab4_sources) if lab4_sources.is_dir() else [],
                                        'note': '' if lab4_sources.is_dir() else '실전반 실습4 옛 구조 입력 폴더가 없습니다(새 구조 graph-lab으로 바뀜) — 새 구조의 출처 줄 대조는 reference/practical2_project_trials.py가 한다'}
    return report


# ───────────── Neo4j 실제 실행 ─────────────
def docker(*args):
    r = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        raise RuntimeError(f'docker {args[0]} 실패: {r.stderr.strip()}')
    return r.stdout.strip()


class Lab:
    def __init__(self):
        self.name = 'hyd-s2ref-' + uuid.uuid4().hex[:8]
        docker('run', '-d', '--name', self.name, '--label', 'hyd.owner=session2-reference', '-p', '127.0.0.1::7474',
               '-e', 'NEO4J_AUTH=none', '-e', 'NEO4J_server_memory_heap_max__size=512m', 'neo4j:5.26-community')
        port = json.loads(docker('inspect', self.name))[0]['NetworkSettings']['Ports']['7474/tcp'][0]['HostPort']
        self.url = f'http://127.0.0.1:{port}/db/neo4j/tx/commit'
        deadline = time.monotonic() + 120
        while True:
            try:
                self.run('RETURN 1'); break
            except Exception:
                if time.monotonic() > deadline:
                    self.close()   # 뜨지 않은 컨테이너도 익명 볼륨째 지운다 — 부른 쪽은 Lab을 받지 못해 지울 수 없다
                    raise RuntimeError('Neo4j 시작 대기 시간 초과')
                time.sleep(2)

    def run(self, statement, **params):
        body = json.dumps({'statements': [{'statement': statement, 'parameters': params}]}).encode()
        req = urllib.request.Request(self.url, body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        if data['errors']:
            raise RuntimeError(data['errors'])
        return [x['row'] for x in data['results'][0]['data']]

    def close(self):
        docker('rm', '-f', '-v', self.name)


def ident(v):
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', v):
        raise ValueError(v)
    return v


def load(lab, graph):
    for label in sorted({x for n in graph['nodes'] for x in n['labels']}):
        lab.run(f'CREATE CONSTRAINT ref_{ident(label)} IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE')
    by = defaultdict(list)
    for n in graph['nodes']:
        by[n['labels'][0]].append(n['props'])
    for label, items in by.items():
        lab.run(f'UNWIND $items AS p MERGE (n:{ident(label)} {{id:p.id}}) SET n += p', items=items)
    rb = defaultdict(list)
    for r in graph['rels']:
        rb[r['type']].append({'a': r['a'], 'b': r['b'], 'props': r['props']})
    for t, items in rb.items():
        lab.run(f'UNWIND $items AS r MATCH (a {{id:r.a}}),(b {{id:r.b}}) MERGE (a)-[x:{ident(t)}]->(b) SET x += r.props', items=items)


def counts(lab):
    return [lab.run('MATCH (n) RETURN count(n)')[0][0], lab.run('MATCH ()-[r]->() RETURN count(r)')[0][0]]


def neo4j_run(report):
    lab = Lab()
    try:
        for course in ['통합반', '실전반']:
            out = report.setdefault('neo4j', {}).setdefault(course, {'실습3': {}, '실습4': {}})
            with D.for_course(course):
                for branch in B.REFERENCE_BRANCHES[course]:
                    lab.run('MATCH (n) DETACH DELETE n')     # 강사 전용 컨테이너를 비우고 갈래마다 다시 시작(학생 랩 DB 아님)
                    graph = B.reference_model(course == '실전반', branch)[1]
                    load(lab, graph); first = counts(lab); load(lab, graph); second = counts(lab)
                    assert first == second == [len(graph['nodes']), len(graph['rels'])], (course, branch, first, second)
                    exp = expected(course, branch)
                    db_probes = {}
                    for code in PROBES[course]:
                        rows = lab.run('OPTIONAL MATCH (exact:Part {id:$c}) WITH exact '
                                       'MATCH (p:Part) WHERE (exact IS NOT NULL AND p = exact) OR (exact IS NULL AND $c IN coalesce(p.other_codes,[])) '
                                       'OPTIONAL MATCH (p)-[:SAME_ITEM_AS*0..1]-(x:Part) WITH p, collect(DISTINCT x)+[p] AS grp UNWIND grp AS g '
                                       'OPTIONAL MATCH (g)<-[:USES_PART]-(c:Component)<-[:HAS_COMPONENT]-(a:Asset) '
                                       'RETURN p.id, collect(DISTINCT a.id), collect(DISTINCT c.id) ORDER BY p.id', c=code)
                        found = []
                        for pid, assets, comps in rows:
                            e = {'part': pid, 'assets': sorted(assets), 'components': sorted(comps)}
                            unsure = lab.run('MATCH (p:Part {id:$p}) OPTIONAL MATCH (p)-[:SAME_ITEM_AS*0..1]-(x:Part) WITH p, collect(DISTINCT x)+[p] AS grp UNWIND grp AS g '
                                             'MATCH (g)<-[:CANDIDATE_PART]-(c:Component)<-[:HAS_COMPONENT]-(a:Asset) RETURN collect(DISTINCT a.id), collect(DISTINCT c.id)', p=pid)
                            if unsure and unsure[0][0]:
                                e['to_check'] = {'assets': sorted(unsure[0][0]), 'components': sorted(unsure[0][1])}
                            if course == '실전반':
                                e['supply'] = sorted(supply_row(branch, *row) for row in lab.run(
                                    'MATCH (s:Supplier)-[r:SUPPLIES]->(:Part {id:$p}) RETURN substring(s.id,9), r.approved, r.price_manwon, r.defect_rate, r.lead_days, '
                                    'r.compare_extra_manwon, r.pending_check IS NOT NULL', p=pid))
                            found.append(e)
                        db_probes[code] = None if not found else (found[0] if len(found) == 1 else {'candidates': found})
                    sensors = lab.run('MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor) RETURN a.id, count(s) ORDER BY a.id')
                    asset_level = lab.run('MATCH (a:Asset)-[:MONITORED_BY]->(s:Sensor) RETURN a.id, collect(s.tag) ORDER BY a.id')
                    qid = exp['sensor_props']['HYD-01:TS1'][0]      # HYD-01 쿨러 쪽 유온을 담은 물리량(갈래의 「같은 물리량의 범위」에 따라 다름)
                    same_qty = lab.run('MATCH (s:Sensor)-[:OBSERVES]->(q:Quantity {id:$q}) RETURN collect(s.id)', q=qid)[0][0]
                    entry = {'first': first, 'second': second, 'probe_mismatch': diff(exp['probes'], db_probes),
                             'sensors_per_asset_via_component': sensors, 'asset_level_sensors': asset_level,
                             'quantity_of_HYD-01_TS1': qid, 'quantity_members_match': sorted(same_qty) == exp['quantity_members'][qid]}
                    assert entry['quantity_members_match'], (course, branch, qid)
                    if course == '실전반':
                        entry['P-PMP-SEAL'] = db_probes['P-PMP-SEAL']
                        entry['source_mismatch'] = diff(exp['supply_sources'], {f'{s}→{p}': [q, a, d] for s, p, q, a, d in lab.run(
                            'MATCH (s:Supplier)-[r:SUPPLIES]->(p:Part) RETURN substring(s.id,9), p.id, r.quote_source, r.approval_source, r.as_of')})
                    out['실습3'][branch] = entry
                if course == '실전반':   # 실습4는 실습4 입력/ 모델(앞 단계 완성) 위에서 돈다. 통합반 실습4는 reference/session2_graph_trials.py가 한다.
                    input_branch = B.GRAPH_LAB_INPUT[course]
                    graph = B.reference_model(True, input_branch)[1]
                    # 조회 갈래 ㄱ · ㄴ: 같은 적재 위에서 돌려줄 열만 다르다(ㄴ은 PR-07 7.4 비교 가산 비용을 함께).
                    lab.run('MATCH (n) DETACH DELETE n')
                    load(lab, graph); first = counts(lab); load(lab, graph); second = counts(lab)
                    assert first == second == [len(graph['nodes']), len(graph['rels'])], (course, 'lab4', first, second)
                    columns = {'ㄱ': '', 'ㄴ': ', r.compare_extra_manwon'}
                    for g, key in B.LAB4_QUERY_BRANCHES.items():
                        exp = expected(course, key)
                        db_probes = {}
                        for code in PROBES[course]:
                            found = []
                            for pid, assets, comps in lab.run('MATCH (p:Part) WHERE p.id = $c OR $c IN coalesce(p.other_codes,[]) '
                                                              'OPTIONAL MATCH (p)<-[:USES_PART]-(c:Component)<-[:HAS_COMPONENT]-(a:Asset) '
                                                              'RETURN p.id, collect(DISTINCT a.id), collect(DISTINCT c.id) ORDER BY p.id', c=code):
                                rows = lab.run('MATCH (s:Supplier)-[r:SUPPLIES]->(:Part {id:$p}) RETURN substring(s.id,9), r.approved, r.price_manwon, r.defect_rate, r.lead_days'
                                               + columns[g], p=pid)
                                found.append({'part': pid, 'assets': sorted(assets), 'components': sorted(comps),
                                              'supply': sorted(supply_row(key, *row, False) if key == 'ㄴ' else supply_row(key, *row, None, False) for row in rows)})
                            db_probes[code] = None if not found else (found[0] if len(found) == 1 else {'candidates': found})
                        out['실습4'][g] = {'input_branch': input_branch, 'expected_key': key, 'first': first, 'second': second,
                                          'probe_mismatch': diff(exp['probes'], db_probes), 'P-PMP-SEAL': db_probes['P-PMP-SEAL']}
                    # 질문 1 「각 값은 어느 파일 · 어느 줄에서 왔는가」 — 조회만으로(원자료를 다시 읽지 않고) 출처 줄과 기준일이 나오는지
                    sources = lab.run('MATCH (s:Supplier)-[r:SUPPLIES]->(p:Part {id:"P-PMP-SEAL"}) '
                                      'RETURN substring(s.id,9) AS sup, s.name, r.quote_source, r.quote_date, r.approval_source, r.as_of ORDER BY sup')
                    exp_sources = expected(course, B.GRAPH_LAB_INPUT[course])['supply_sources']
                    out['실습4']['출처 조회'] = {'P-PMP-SEAL': sources,
                                             'mismatch': diff({k: v for k, v in exp_sources.items() if k.endswith('→P-PMP-SEAL')},
                                                              {f'{s}→P-PMP-SEAL': [q, a, d] for s, _, q, _, a, d in sources})
                                                         + [f'{s}: 이름 {n}' for s, n, *_ in sources if s != n]}
    finally:
        lab.close()
        report['neo4j_container_removed'] = lab.name not in docker('ps', '-a', '--format', '{{.Names}}').split()


if __name__ == '__main__':
    report = {'kind': '강사 참조 검증 — 학생 AI 수행/촬영 아님', 'ref_date': D.REF_DATE, 'offline': offline()}
    bad = {f'{c}/{b}': v['mismatch'] for c, x in report['offline'].items() for b, v in x.items() if b != '실습4' and v['mismatch']}
    bad |= {f'실전반/실습4/{g}': v['mismatch'] for g, v in report['offline']['실전반']['실습4'].items() if v['mismatch']}
    if bad:
        print(json.dumps(bad, ensure_ascii=False, indent=1)); sys.exit('독립 대조 불일치')
    if '--offline' not in sys.argv:
        neo4j_run(report)
        bad = {f'{c}/{b}': v['probe_mismatch'] + v.get('source_mismatch', []) for c, x in report['neo4j'].items() for b, v in x['실습3'].items()
               if v['probe_mismatch'] or v.get('source_mismatch')}
        bad |= {f'{c}/실습4/{g}': v.get('probe_mismatch') or v.get('mismatch') for c, x in report['neo4j'].items() for g, v in x['실습4'].items() if v.get('probe_mismatch') or v.get('mismatch')}
        if bad:
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
            print(json.dumps(bad, ensure_ascii=False, indent=1)); sys.exit('Neo4j 조회 불일치')
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    brief = {c: {'실습3': {b: {k: e[k] for k in ['first', 'second', 'probe_mismatch']} for b, e in x['실습3'].items()},
                 '실습4': {g: {k: e[k] for k in ['input_branch', 'first', 'second', 'after_changes', 'after_changes_again', 'probe_mismatch', 'mismatch'] if k in e} for g, e in x['실습4'].items()}}
             for c, x in report.get('neo4j', {}).items()}
    print(json.dumps({k: v for k, v in report.items() if k != 'neo4j'} | ({'neo4j': brief} if brief else {}), ensure_ascii=False, indent=1))
