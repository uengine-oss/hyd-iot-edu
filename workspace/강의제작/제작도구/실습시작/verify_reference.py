"""2회차 실습3·4 강사 참조 검증. 학생/AI 수행 증거와 구별한다.

1) 독립 대조: 생성기의 정답 구조(data_session2.TRUTH, CSV를 다시 읽지 않음)에서 질문별 기대 답을 계산하고,
   원자료 CSV를 해석해 만든 참조 그래프(build_labs.reference_model)의 답과 비교한다.
   실전반은 공급 조건마다 값의 출처(견적 줄 · 승인 등록 줄 · 기준일 — 실습3 9단계)도 대조하고, 실습4 입력 모델의 출처 줄을
   실습4 폴더 `입력/자료/`의 실제 CSV 줄에서 다시 읽어 값이 같은지 본다.
   실전반 실습4 조회 갈래 ㄱ · ㄴ은 실습4 입력 모델(갈래 ㄴ)에서 같은 답이 나오는지 함께 대조한다.
2) Neo4j 실행(--offline이 없을 때): 이 스크립트가 만든 별도 교육용 컨테이너에 참조 그래프를 적재 → 질의 → 같은 적재 재실행
   를 실습3 갈래마다, 실습4 입력 모델(통합 A · 실전 ㄴ) 위에서 통합반은 설비별 교체 부품 조회와 수정본 반영 → 재반영을 수정본 갈래마다,
   실전반은 조회 갈래마다 실제로 하고 개수·답·출처를 확인한다. 통합반은 수정본 전에도 부품의 사용 설비를 설비 상태와 함께 조회한다
   (10단계 「지금 가동하는 설비」). 끝나면 그 컨테이너와 이름 없는 볼륨만 지운다.
갈래: 실습3 통합반 A · B · C, 실전반 A · B · ㄴ · ㄷ(build_labs.REFERENCE_BRANCHES, 대응은 reference/실전반/README.md).
      실습4 통합반 수정본 갈래 남김 · 삭제(build_labs.LAB4_CHANGE_BRANCHES — 불용 설비를 상태로 남김 · 전용 하위 대상과 함께 지움),
      실전반 조회 갈래 ㄱ · ㄴ(build_labs.LAB4_QUERY_BRANCHES — PR-07 7.4 정보를 빼고 · 함께 돌려줌).
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
# 6205-2RS: 두 사내 품번(P-FAN-BRG·P-BRG-6205)이 같은 제조사 품번을 가진다 → 후보 둘. 갈래 A는 후보마다 따로, 갈래 B는 같은 물품 묶음으로 답한다.
PROBES = {'통합반': ['P-PMP-SEAL', 'P-FAN-BRG', 'P-BRG-6205', 'P-PMP-SEAL-HT', 'P-RTN-FLT', 'P-HYD-OIL', 'PMP-SEAL', 'RF-10', 'P-PMP-SEAL-X', '6205-2RS'],
          '실전반': ['P-PMP-SEAL', 'P-PMP-SEAL-HT', 'P-CLR-CORE', 'P-CLR-PLT', 'P-ACC-BLD', 'P-RTN-FLT', 'PS-4510', 'PMP-SEAL', 'P-PMP-SEAL-X']}


# ───────────── 기대 답(생성 정답 구조에서) ─────────────
def supply_row(branch, supplier, approved, price, defect, lead, extra, pending):
    """공급 조건 한 줄. 갈래 ㄴ은 PR-07 7.4 비교 가산 비용, ㄷ은 미결(확인 요청) 표시를 덧붙인다."""
    row = [supplier, approved, price, defect, lead]
    if branch == 'ㄴ':
        row.append(extra)
    if branch == 'ㄷ':
        row.append(bool(pending))
    return row


def written_code(aid, key):
    """그 구성 요소의 교체부품 칸(생성 정답 D.PART_TEXT)이 품번을 말하는가 — 괄호 속 품번 · 사내 품번 · 교차표에 하나로 적힌 표기.
    통합반 갈래 C(빈 칸 · 품명만 적힌 칸은 잇지 않음)의 기대 답에 쓴다. 교체로 다시 적은 HYD-02 주 펌프 줄은 사내 품번(P-PMP-SEAL)이다."""
    if (aid, key) == D.REMOVED_PUMP[:2]:
        return True
    text = D.PART_TEXT[aid].get(key, '')
    if re.search(r'\((P-[A-Z0-9-]+)\)', text) or text in D.TRUTH['parts']:
        return True
    return len({c[0] for c in D.CROSS if c[1] == text}) == 1


def code_to_parts(code):
    """조회 표기 → 사내 품번 후보(정렬). 없으면 빈 목록, 같은 표기를 가진 품번이 여럿이면 여럿."""
    if code in D.TRUTH['parts']:
        return [code]
    return sorted({c[0] for c in D.CROSS if c[1] == code})


def expected(course, branch):
    t = D.TRUTH
    sensors_by_asset = {}
    quantity_members = defaultdict(set)
    sensor_props = {}
    usage = defaultdict(lambda: {'assets': set(), 'components': set()})
    for aid, a in t['assets'].items():
        per = defaultdict(list)
        for tag, s in a['sensors'].items():
            per[s['component'] or '(설비 전체)'].append(tag)
            quantity_members[s['quantity']].add(f'{aid}:{tag}')
            sensor_props[f'{aid}:{tag}'] = [s['quantity'], s['unit'], s['normal'], s['limit'], s['direction'], s['kind']]
        sensors_by_asset[aid] = {k: sorted(v) for k, v in sorted(per.items())}
        for key, part in a['components'].items():
            if part and not (course == '통합반' and branch == 'C' and not written_code(aid, key)):
                usage[part]['assets'].add(aid)
                usage[part]['components'].add(f'{aid}:{key}')
    same = {}
    if course == '통합반' and branch == 'B':
        by = defaultdict(set)
        for pid, other, kind, *_ in D.CROSS:
            if kind == '제조사 품번':
                by[other].add(pid)
        for ids in by.values():
            for p in ids:
                same.setdefault(p, set()).update(ids)
    probes = {}
    for code in PROBES[course]:
        found = []
        for pid in code_to_parts(code):
            group = same.get(pid, {pid})
            assets = sorted(set().union(*(usage[p]['assets'] for p in group)))
            comps = sorted(set().union(*(usage[p]['components'] for p in group)))
            entry = {'part': pid, 'assets': assets, 'components': comps}
            if course == '실전반':
                entry['supply'] = sorted(supply_row(branch, s, v['approved_B' if branch == 'B' else 'approved_A'], v['price_manwon'], v['defect_rate'], v['lead_days'],
                                                    float(D.PR74_EXTRA_MANWON) if v['pr74'] else None, v['pr74'] and not v['condition'])
                                         for (s, p), v in t['supply'].items() if p == pid)
            found.append(entry)
        probes[code] = None if not found else (found[0] if len(found) == 1 else {'candidates': found})
    out = {'sensors_by_asset': sensors_by_asset, 'quantity_members': {k: sorted(v) for k, v in sorted(quantity_members.items())},
           'sensor_props': dict(sorted(sensor_props.items())), 'probes': probes}
    if course == '통합반':   # 실습4 「설비별 교체 부품 조회」: 설비 → 구성 요소 → 교체 부품(없으면 None)
        out['parts_by_asset'] = {aid: {k: (v if not (branch == 'C' and not written_code(aid, k)) else None) for k, v in sorted(a['components'].items())}
                                 for aid, a in sorted(t['assets'].items())}
    else:                    # 실습3 「값마다 출처 남기기」: 생성 순서에서 센 줄(CSV를 다시 읽지 않음)
        out['supply_sources'] = {f'{s}→{p}': [D.line_ref(D.QUOTE_FILE, v['quote_line']), D.line_ref(D.AVL_FILE, v['avl_line']) if 'avl_line' in v else None, D.REF_DATE]
                                 for (s, p), v in sorted(t['supply'].items())}
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
        sensor_props[r['a']] = [r['b'], s['unit'], s.get('normal'), s.get('limit'), s.get('limit_direction'), s['kind']]
    usage = defaultdict(lambda: {'assets': set(), 'components': set()})
    for r in by_type['USES_PART']:
        usage[r['b']]['assets'].add(owner[r['a']]); usage[r['b']]['components'].add(r['a'])
    same = defaultdict(set)
    for r in by_type['SAME_ITEM_AS']:
        same[r['a']].update({r['a'], r['b']}); same[r['b']].update({r['a'], r['b']})
    probes = {}
    for code in PROBES[course]:
        hits = [i for i, p in props.items() if labels[i] == 'Part' and i == code] or \
               sorted(i for i, p in props.items() if labels[i] == 'Part' and code in p.get('other_codes', []))
        found = []
        for pid in hits:
            group = same.get(pid) or {pid}
            entry = {'part': pid, 'assets': sorted(set().union(*(usage[p]['assets'] for p in group))),
                     'components': sorted(set().union(*(usage[p]['components'] for p in group)))}
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
        for branch in B.REFERENCE_BRANCHES[course]:
            graph = B.reference_model(course == '실전반', branch)[1]
            exp = expected(course, branch); got = answers_from_graph(course, branch, graph)
            d = diff(exp, got)
            report[course][branch] = {'nodes': len(graph['nodes']), 'rels': len(graph['rels']), 'mismatch': d}
            answers[branch] = exp
        EXPECT[course].write_text(json.dumps(answers, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    # 실전반 실습4 조회 갈래: 실습4 입력 모델(갈래 ㄴ) 하나에서 갈래마다 돌려줄 열만 달리해 같은 기대 답이 나오는지(ㄱ = 기대 답 A의 공급 조건 열, ㄴ = 기대 답 ㄴ)
    graph = B.reference_model(True, B.LAB4_INPUT_BRANCH['실전반'])[1]
    report['실전반']['실습4'] = {g: {'input_branch': B.LAB4_INPUT_BRANCH['실전반'], 'expected_key': key,
                                   'mismatch': diff(expected('실전반', key)['probes'], answers_from_graph('실전반', key, graph)['probes'])}
                               for g, key in B.LAB4_QUERY_BRANCHES.items()}
    lab4_sources = B.OUT/'실전반/실습/02회차/랩'/B.LAB4/'입력/자료'
    report['실전반']['실습4']['출처 줄'] = {'folder': lab4_sources.relative_to(B.ROOT).as_posix(),
                                        'mismatch': source_rows(json.loads((lab4_sources.parent/'graph.json').read_text(encoding='utf-8')), lab4_sources)
                                        if lab4_sources.is_dir() else ['실전반 실습4 옛 구조 입력 폴더가 없습니다(새 구조 graph-lab으로 바뀜) — 새 구조의 출처 줄 대조는 reference/practical2_project_trials.py가 한다']}
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


def change_rows(course, name):
    folder = B.OUT/course/'실습/02회차/랩'/B.LAB4/'입력/자료_변경분'/f'{D.CHANGE_DATE}_수정본'
    if course == '통합반':
        from session2_project import NAMES
        folder = B.OUT/course/'실습/02회차/랩/graph-lab/data/changes'/D.CHANGE_DATE
        name = NAMES[name]
    path = folder/name
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def apply_changes(lab, course, change):
    """강사 참조의 수정본 반영(통합반 실습4 입력 모델 위): 필요한 대상만 SET/MERGE. 수정본 갈래 「삭제」는 불용 설비를 전용 하위 대상과 함께 지우고, 「남김」은 상태로 남긴다."""
    done = []
    for r in change_rows(course, '설비_대장_변경.csv'):
        if change == '삭제' and r['상태'].startswith('불용'):
            lab.run('MATCH (a:Asset {id:$id}) OPTIONAL MATCH (a)-[:HAS_COMPONENT]->(c) OPTIONAL MATCH (c)-[:MONITORED_BY]->(s) OPTIONAL MATCH (a)-[:MONITORED_BY]->(s2) '
                    'WITH a, collect(DISTINCT c)+collect(DISTINCT s)+collect(DISTINCT s2) AS sub FOREACH (x IN sub | DETACH DELETE x) DETACH DELETE a', id=r['설비코드'])
            done.append(f'{r["설비코드"]} 하위 대상과 삭제')
            continue
        lab.run('MATCH (a:Asset {id:$id}) SET a.name=$name, a.status=$status', id=r['설비코드'], name=r['설비명'], status=r['상태'])
        done.append(f'{r["설비코드"]} 이름·상태 수정')
    for r in change_rows(course, '구성요소_변경.csv'):
        cid = r['설비코드'] + ':' + B.comp_key(r['구성요소'], {k for k, *_ in D.MODEL_COMPONENTS[D.model_of(r['설비코드'])]})
        lab.run('MATCH (c:Component {id:$c}),(p:Part {id:$p}) MERGE (c)-[u:USES_PART]->(p) SET u.source_text=$t', c=cid, p=r['교체부품'], t=r['교체부품'])
        done.append(f'{cid} 교체부품 확인')
    for r in change_rows(course, '센서_변경.csv'):
        sid = r['설비코드'] + ':' + r['태그']
        if r['변경'] == '삭제':
            done.append(f'{sid} 중복 행 삭제(같은 센서의 다른 행이 남아 대상 유지)')
            continue
        unit, factor = B.UNIT.get(r['단위'], (r['단위'], 1))
        lab.run('MATCH (s:Sensor {id:$id}) SET s.unit=$unit, s.normal=$normal', id=sid, unit=unit, normal=round(float(r['정상값']) * factor, 6))
        done.append(f'{sid} 값 보완')
    return done


def neo4j_run(report):
    lab = Lab()
    try:
        for course in ['통합반', '실전반']:
            out = report.setdefault('neo4j', {}).setdefault(course, {'실습3': {}, '실습4': {}})
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
                        if course == '실전반':
                            e['supply'] = sorted(supply_row(branch, *row) for row in lab.run(
                                'MATCH (s:Supplier)-[r:SUPPLIES]->(:Part {id:$p}) RETURN substring(s.id,9), r.approved, r.price_manwon, r.defect_rate, r.lead_days, '
                                'r.compare_extra_manwon, r.pending_check IS NOT NULL', p=pid))
                        found.append(e)
                    db_probes[code] = None if not found else (found[0] if len(found) == 1 else {'candidates': found})
                sensors = lab.run('MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor) RETURN a.id, count(s) ORDER BY a.id')
                asset_level = lab.run('MATCH (a:Asset)-[:MONITORED_BY]->(s:Sensor) RETURN a.id, collect(s.tag) ORDER BY a.id')
                same_qty = lab.run('MATCH (s:Sensor)-[:OBSERVES]->(q:Quantity {id:"quantity:TS1"}) RETURN collect(s.id)')[0][0]
                entry = {'first': first, 'second': second, 'probe_mismatch': diff(exp['probes'], db_probes),
                         'sensors_per_asset_via_component': sensors, 'asset_level_sensors': asset_level,
                         'quantity_TS1_members_match': sorted(same_qty) == exp['quantity_members']['quantity:TS1']}
                if course == '실전반':
                    entry['P-PMP-SEAL'] = db_probes['P-PMP-SEAL']
                    entry['source_mismatch'] = diff(exp['supply_sources'], {f'{s}→{p}': [q, a, d] for s, p, q, a, d in lab.run(
                        'MATCH (s:Supplier)-[r:SUPPLIES]->(p:Part) RETURN substring(s.id,9), p.id, r.quote_source, r.approval_source, r.as_of')})
                out['실습3'][branch] = entry
            # 실습4는 실습4 입력/ 모델(앞 단계 완성) 위에서 돈다.
            input_branch = B.LAB4_INPUT_BRANCH[course]
            graph = B.reference_model(course == '실전반', input_branch)[1]
            if course == '실전반':
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
                exp_sources = expected(course, B.LAB4_INPUT_BRANCH[course])['supply_sources']
                out['실습4']['출처 조회'] = {'P-PMP-SEAL': sources,
                                         'mismatch': diff({k: v for k, v in exp_sources.items() if k.endswith('→P-PMP-SEAL')},
                                                          {f'{s}→P-PMP-SEAL': [q, a, d] for s, _, q, _, a, d in sources})
                                                     + [f'{s}: 이름 {n}' for s, n, *_ in sources if s != n]}
                continue
            # 통합반: 설비별 교체 부품 조회, 그다음 수정본 갈래 남김 · 삭제를 각각 새로 적재해 돌린다.
            hyd07 = D.TRUTH['assets']['HYD-07']
            gone_nodes = 1 + len(hyd07['components']) + len(hyd07['sensors'])
            gone_rels = len(hyd07['components']) + sum(1 for p in hyd07['components'].values() if p) + 2 * len(hyd07['sensors'])
            lab.run('MATCH (n) DETACH DELETE n')
            load(lab, graph)
            parts = defaultdict(dict)
            for aid, cid, pid in lab.run('MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component) OPTIONAL MATCH (c)-[:USES_PART]->(p:Part) RETURN a.id, c.id, p.id ORDER BY a.id, c.id'):
                parts[aid][cid.split(':', 1)[1]] = pid
            out['실습4']['설비별 교체 부품'] = {'input_branch': input_branch,
                                         'mismatch': diff(expected(course, input_branch)['parts_by_asset'], {a: dict(sorted(d.items())) for a, d in sorted(parts.items())}),
                                         'HYD-01': dict(sorted(parts['HYD-01'].items()))}
            # 10단계 「부품의 사용 설비」 — 수정본 전: 설비 대장의 상태(가동 · 예비)가 그래프에 있어 「정한 것」대로 빼거나 함께 보일 수 있다
            with_status = lab.run('MATCH (:Part {id:"P-RTN-FLT"})<-[:USES_PART]-(:Component)<-[:HAS_COMPONENT]-(a:Asset) RETURN DISTINCT a.id, a.status ORDER BY a.id')
            running = [r[0] for r in lab.run('MATCH (:Part {id:"P-RTN-FLT"})<-[:USES_PART]-(:Component)<-[:HAS_COMPONENT]-(a:Asset) '
                                             'WHERE a.status = "가동" RETURN DISTINCT a.id ORDER BY a.id')]
            assert ['HYD-07', '예비(보관)'] in with_status and running == ['HYD-01', 'HYD-02', 'HYD-03', 'HYD-04'], (with_status, running)
            out['실습4']['부품의 사용 설비(상태) 수정본 전'] = {'P-RTN-FLT 사용 설비(상태)': with_status, 'P-RTN-FLT 지금 가동 설비': running}
            for change in B.LAB4_CHANGE_BRANCHES:
                lab.run('MATCH (n) DETACH DELETE n')
                load(lab, graph); first = counts(lab)
                done = apply_changes(lab, course, change); after = counts(lab)
                apply_changes(lab, course, change); after2 = counts(lab)
                checks = {'HYD-02 name': lab.run('MATCH (a:Asset {id:"HYD-02"}) RETURN a.name')[0][0],
                          'HYD-07': lab.run('MATCH (a:Asset {id:"HYD-07"}) RETURN a.status'),
                          'HYD-01:TS1 남음': lab.run('MATCH (:Asset {id:"HYD-01"})-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor {id:"HYD-01:TS1"}) RETURN count(s)')[0][0],
                          'HYD-06:I_MOTOR normal': lab.run('MATCH (s:Sensor {id:"HYD-06:I_MOTOR"}) RETURN s.normal')[0][0],
                          # 2-4 질문의 업무 맥락(지금 가동하는 설비의 예비품). 남김은 불용 설비를 상태로 구별, 삭제는 지운다.
                          'P-RTN-FLT 사용 설비(상태)': lab.run('MATCH (:Part {id:"P-RTN-FLT"})<-[:USES_PART]-(:Component)<-[:HAS_COMPONENT]-(a:Asset) RETURN DISTINCT a.id, a.status ORDER BY a.id'),
                          'P-RTN-FLT 지금 가동 설비': [r[0] for r in lab.run('MATCH (:Part {id:"P-RTN-FLT"})<-[:USES_PART]-(:Component)<-[:HAS_COMPONENT]-(a:Asset) '
                                                                            'WHERE NOT coalesce(a.status,"") STARTS WITH "불용" RETURN DISTINCT a.id ORDER BY a.id')]}
                expect_after = first if change == '남김' else [first[0] - gone_nodes, first[1] - gone_rels]
                assert first == [len(graph['nodes']), len(graph['rels'])], (course, change, first)
                assert after == after2 == expect_after, (course, change, after, after2, expect_after)
                assert checks['HYD-02 name'] == 'HYD-02 2라인 2호 파워팩' and checks['HYD-06:I_MOTOR normal'] == 18.5 and checks['HYD-01:TS1 남음'] == 1
                assert (checks['HYD-07'] == [['불용(매각 예정)']]) if change == '남김' else checks['HYD-07'] == []
                assert checks['P-RTN-FLT 지금 가동 설비'] == ['HYD-01', 'HYD-02', 'HYD-03', 'HYD-04'], checks['P-RTN-FLT 지금 가동 설비']
                assert ['HYD-07', '불용(매각 예정)'] in checks['P-RTN-FLT 사용 설비(상태)'] if change == '남김' else all(r[0] != 'HYD-07' for r in checks['P-RTN-FLT 사용 설비(상태)'])
                out['실습4'][change] = {'input_branch': input_branch, 'first': first, 'changes_applied': done, 'after_changes': after,
                                       'after_changes_again': after2, 'change_checks': checks}
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
