"""2회차 실습3·4 강사 참조 검증. 학생/AI 수행 증거와 구별한다.

1) 독립 대조: 생성기의 정답 구조(data_session2.TRUTH, CSV를 다시 읽지 않음)에서 질문별 기대 답을 계산하고,
   원자료 CSV를 해석해 만든 참조 그래프(build_labs.reference_model)의 답과 비교한다.
2) Neo4j 실행(--offline이 없을 때): 이 스크립트가 만든 별도 교육용 컨테이너에 참조 그래프를 적재 → 질의 → 같은 적재 재실행
   → 수정본 반영 → 수정본 재반영을 실제로 하고 개수·답을 확인한다. 끝나면 그 컨테이너와 이름 없는 볼륨만 지운다.
사용: python verify_reference.py [--offline]
"""
from pathlib import Path
from collections import defaultdict
import csv
import datetime as dt
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
PROBES = {'통합반': ['P-PMP-SEAL', 'P-FAN-BRG', 'P-BRG-6205', 'P-PMP-SEAL-HT', 'P-RTN-FLT', 'P-HYD-OIL', 'PMP-SEAL', 'RF-10', 'P-PMP-SEAL-X'],
          '실전반': ['P-PMP-SEAL', 'P-PMP-SEAL-HT', 'P-CLR-CORE', 'P-CLR-PLT', 'P-ACC-BLD', 'P-RTN-FLT', 'PS-4510', 'PMP-SEAL', 'P-PMP-SEAL-X']}


# ───────────── 기대 답(생성 정답 구조에서) ─────────────
def code_to_part(code):
    if code in D.TRUTH['parts']:
        return code
    hits = {c[0] for c in D.CROSS if c[1] == code}
    return hits.pop() if len(hits) == 1 else None


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
            if part:
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
        pid = code_to_part(code)
        if pid is None:
            probes[code] = None
            continue
        group = same.get(pid, {pid})
        assets = sorted(set().union(*(usage[p]['assets'] for p in group)))
        comps = sorted(set().union(*(usage[p]['components'] for p in group)))
        entry = {'part': pid, 'assets': assets, 'components': comps}
        if course == '실전반':
            key = 'approved_A' if branch == 'A' else 'approved_B'
            entry['supply'] = sorted([[s, v[key], v['price_manwon'], v['defect_rate'], v['lead_days']] for (s, p), v in t['supply'].items() if p == pid])
        probes[code] = entry
    out = {'sensors_by_asset': sensors_by_asset, 'quantity_members': {k: sorted(v) for k, v in sorted(quantity_members.items())},
           'sensor_props': dict(sorted(sensor_props.items())), 'probes': probes}
    if course == '실전반':
        out['lead_times'] = lead_times_truth()
    return out


def lead_times_truth():
    """입고 실측 납기(일). 갈래 first=분할 입고의 첫 입고, complete=발주 수량을 다 받은 날. 미입고 발주는 뺀다."""
    old = {c[1]: c[0] for c in D.CROSS if c[2] == '구 사내 품번'}
    pos = defaultdict(list)
    for r in D.receipts():
        part = old.get(r[1], r[1])
        if part != 'P-PMP-SEAL' or not r[5]:
            continue
        pos[(r[2], r[0], r[3], r[6])].append((r[5], r[7]))
    res = {}
    for mode in ['first', 'complete']:
        per = defaultdict(list)
        for (sup, po, ordered, qty), arrivals in pos.items():
            arrivals.sort()
            if mode == 'first':
                day = arrivals[0][0]
            else:
                got = 0; day = None
                for d, q in arrivals:
                    got += q
                    if got >= qty:
                        day = d; break
                if day is None:
                    continue
            per[sup].append((dt.date.fromisoformat(day) - dt.date.fromisoformat(ordered)).days)
        res[mode] = {s: {'orders': len(v), 'mean': round(sum(v)/len(v), 2), 'max': max(v), 'days': sorted(v)} for s, v in sorted(per.items())}
    res['quoted'] = {s: v['lead_days'] for (s, p), v in D.TRUTH['supply'].items() if p == 'P-PMP-SEAL'}
    return res


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
        hits = [i for i, p in props.items() if labels[i] == 'Part' and (i == code or code in p.get('other_codes', []))]
        if len(hits) != 1:
            probes[code] = None
            continue
        pid = hits[0]; group = same.get(pid) or {pid}
        entry = {'part': pid, 'assets': sorted(set().union(*(usage[p]['assets'] for p in group))),
                 'components': sorted(set().union(*(usage[p]['components'] for p in group)))}
        if course == '실전반':
            entry['supply'] = sorted([[r['a'].split(':', 1)[1], r['props']['approved'], r['props']['price_manwon'], r['props']['defect_rate'], r['props']['lead_days']]
                                      for r in by_type['SUPPLIES'] if r['b'] == pid])
        probes[code] = entry
    out = {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors_by_asset.items())},
           'quantity_members': {k: sorted(v) for k, v in sorted(quantity_members.items())}, 'sensor_props': dict(sorted(sensor_props.items())), 'probes': probes}
    if course == '실전반':
        out['lead_times'] = lead_times_from_csv()
    return out


def lead_times_from_csv():
    """학생과 같은 길: 입고_이력.csv + 품번_교차표.csv를 읽어 계산(강사 참조 구현)."""
    old = {r['다른표기']: r['사내품번'] for r in B.rows('품번_교차표.csv') if r['표기종류'] == '구 사내 품번'}
    pos = defaultdict(list)
    for r in B.rows('입고_이력.csv'):
        if old.get(r['품번'], r['품번']) != 'P-PMP-SEAL' or not r['입고일']:
            continue
        pos[(r['공급사'], r['발주번호'], r['발주일'], int(r['발주수량']))].append((r['입고일'], int(r['입고수량'])))
    res = {}
    for mode in ['first', 'complete']:
        per = defaultdict(list)
        for (sup, po, ordered, qty), arr in pos.items():
            arr.sort(); day = None
            if mode == 'first':
                day = arr[0][0]
            else:
                got = 0
                for d, q in arr:
                    got += q
                    if got >= qty:
                        day = d; break
            if day:
                per[sup].append((dt.date.fromisoformat(day) - dt.date.fromisoformat(ordered)).days)
        res[mode] = {s: {'orders': len(v), 'mean': round(sum(v)/len(v), 2), 'max': max(v), 'days': sorted(v)} for s, v in sorted(per.items())}
    g = B.reference_model(True)[1]
    res['quoted'] = {r['a'].split(':', 1)[1]: r['props']['lead_days'] for r in g['rels'] if r['type'] == 'SUPPLIES' and r['b'] == 'P-PMP-SEAL'}
    return res


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
        for branch in ['A', 'B']:
            graph = B.reference_model(course == '실전반', branch)[1]
            exp = expected(course, branch); got = answers_from_graph(course, branch, graph)
            d = diff(exp, got)
            report[course][branch] = {'nodes': len(graph['nodes']), 'rels': len(graph['rels']), 'mismatch': d}
            if branch == 'A':
                EXPECT[course].write_text(json.dumps({'A': exp, 'B': expected(course, 'B')}, ensure_ascii=False, indent=1), encoding='utf-8')
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
    path = folder/name
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def apply_changes(lab, course, branch):
    """강사 참조의 수정본 반영: 필요한 대상만 SET/MERGE. 갈래 B는 불용 설비를 전용 하위 대상과 함께 지운다."""
    done = []
    for r in change_rows(course, '설비_대장_변경.csv'):
        if branch == 'B' and r['상태'].startswith('불용'):
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
    for r in change_rows(course, '공급_조건_변경.csv'):
        sup = next(k for k in D.SUPPLIERS if r['공급사'].startswith(k))
        lab.run('MATCH (:Supplier {id:$s})-[x:SUPPLIES]->(:Part {id:$p}) WHERE x.quote_date < $d SET x.price_manwon=$price, x.quote_date=$d, x.valid_until=$u',
                s='supplier:'+sup, p=r['품번'], d=r['견적일'], u=r['유효기한'], price=float(r['단가(만원)']))
        done.append(f'{sup}→{r["품번"]} 새 견적')
    for r in change_rows(course, '승인공급사_변경.csv'):
        lab.run('MATCH (:Supplier {id:$s})-[x:SUPPLIES]->(:Part {id:$p}) SET x.approved=true, x.approval_status=$st', s='supplier:'+r['공급사'], p=r['품번'], st=r['승인상태'])
        done.append(f'{r["공급사"]}→{r["품번"]} 재승인')
    return done


def neo4j_run(report):
    lab = Lab()
    try:
        for course in ['통합반', '실전반']:
            for branch in ['A', 'B']:
                lab.run('MATCH (n) DETACH DELETE n')     # 강사 전용 컨테이너를 비우고 갈래마다 다시 시작(학생 랩 DB 아님)
                graph = B.reference_model(course == '실전반', branch)[1]
                load(lab, graph); first = counts(lab); load(lab, graph); second = counts(lab)
                assert first == second == [len(graph['nodes']), len(graph['rels'])], (course, branch, first, second)
                exp = expected(course, branch)
                db_probes = {}
                for code in PROBES[course]:
                    rows = lab.run('MATCH (p:Part) WHERE p.id=$c OR $c IN coalesce(p.other_codes,[]) '
                                   'OPTIONAL MATCH (p)-[:SAME_ITEM_AS*0..1]-(x:Part) WITH p, collect(DISTINCT x)+[p] AS grp UNWIND grp AS g '
                                   'OPTIONAL MATCH (g)<-[:USES_PART]-(c:Component)<-[:HAS_COMPONENT]-(a:Asset) '
                                   'RETURN p.id, collect(DISTINCT a.id), collect(DISTINCT c.id)', c=code)
                    if not rows:
                        db_probes[code] = None; continue
                    pid, assets, comps = rows[0]
                    e = {'part': pid, 'assets': sorted(assets), 'components': sorted(comps)}
                    if course == '실전반':
                        e['supply'] = sorted(lab.run('MATCH (s:Supplier)-[r:SUPPLIES]->(:Part {id:$p}) RETURN substring(s.id,9), r.approved, r.price_manwon, r.defect_rate, r.lead_days', p=pid))
                    db_probes[code] = e
                sensors = lab.run('MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor) RETURN a.id, count(s) ORDER BY a.id')
                asset_level = lab.run('MATCH (a:Asset)-[:MONITORED_BY]->(s:Sensor) RETURN a.id, collect(s.tag) ORDER BY a.id')
                same_qty = lab.run('MATCH (s:Sensor)-[:OBSERVES]->(q:Quantity {id:"quantity:TS1"}) RETURN collect(s.id)')[0][0]
                entry = {'first': first, 'second': second, 'probe_mismatch': diff(exp['probes'], db_probes),
                         'sensors_per_asset_via_component': sensors, 'asset_level_sensors': asset_level,
                         'quantity_TS1_members_match': sorted(same_qty) == exp['quantity_members']['quantity:TS1']}
                if course == '실전반':
                    entry['P-PMP-SEAL'] = db_probes['P-PMP-SEAL']
                done = apply_changes(lab, course, branch); after = counts(lab)
                apply_changes(lab, course, branch); after2 = counts(lab)
                checks = {'HYD-02 name': lab.run('MATCH (a:Asset {id:"HYD-02"}) RETURN a.name')[0][0],
                          'HYD-07': lab.run('MATCH (a:Asset {id:"HYD-07"}) RETURN a.status'),
                          'HYD-06:I_MOTOR normal': lab.run('MATCH (s:Sensor {id:"HYD-06:I_MOTOR"}) RETURN s.normal')[0][0]}
                if course == '실전반':
                    checks['A정밀→P-FAN-BRG'] = lab.run('MATCH (:Supplier {id:"supplier:A정밀"})-[r:SUPPLIES]->(:Part {id:"P-FAN-BRG"}) RETURN r.price_manwon, r.quote_date')[0]
                    checks['A정밀→P-ACC-BLD approved'] = lab.run('MATCH (:Supplier {id:"supplier:A정밀"})-[r:SUPPLIES]->(:Part {id:"P-ACC-BLD"}) RETURN r.approved')[0][0]
                expect_after = [first[0], first[1]] if branch == 'A' else [first[0] - 8, first[1] - 13]
                assert after == after2 == expect_after, (course, branch, after, after2, expect_after)
                assert checks['HYD-02 name'] == 'HYD-02 2라인 2호 파워팩' and checks['HYD-06:I_MOTOR normal'] == 18.5
                assert (checks['HYD-07'] == [['불용(매각 예정)']]) if branch == 'A' else checks['HYD-07'] == []
                if course == '실전반':
                    assert checks['A정밀→P-FAN-BRG'] == [19.0, '2026-10-18'] and checks['A정밀→P-ACC-BLD approved'] is True
                entry.update(changes_applied=done, after_changes=after, after_changes_again=after2, change_checks=checks)
                report.setdefault('neo4j', {}).setdefault(course, {})[branch] = entry
    finally:
        lab.close()
        report['neo4j_container_removed'] = lab.name not in docker('ps', '-a', '--format', '{{.Names}}').split()


if __name__ == '__main__':
    report = {'kind': '강사 참조 검증 — 학생 AI 수행/촬영 아님', 'ref_date': D.REF_DATE, 'offline': offline()}
    bad = {f'{c}/{b}': v['mismatch'] for c, x in report['offline'].items() for b, v in x.items() if v['mismatch']}
    if bad:
        print(json.dumps(bad, ensure_ascii=False, indent=1)); sys.exit('독립 대조 불일치')
    if '--offline' not in sys.argv:
        neo4j_run(report)
        bad = {f'{c}/{b}': v['probe_mismatch'] for c, x in report['neo4j'].items() for b, v in x.items() if v['probe_mismatch']}
        if bad:
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
            print(json.dumps(bad, ensure_ascii=False, indent=1)); sys.exit('Neo4j 조회 불일치')
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'neo4j'} | ({'neo4j': {c: {b: {k: e[k] for k in ['first', 'second', 'after_changes', 'after_changes_again', 'probe_mismatch']} for b, e in x.items()} for c, x in report['neo4j'].items()}} if 'neo4j' in report else {}), ensure_ascii=False, indent=1))
