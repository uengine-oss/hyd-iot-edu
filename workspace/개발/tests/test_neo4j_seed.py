"""지식 그래프 시드(it/neo4j — seed.sh · v2/*.cypher · v2/seed_checks.cypher)를 실제 Neo4j(compose neo4j 이미지의 버릴 컨테이너)에 적재해 판정한다.

시드는 kg-seed 와 같은 명령(seed.sh)을 그 컨테이너 안에서 돌린다(conftest graph_server). 그래프 비교는 노드 id 기준이다(elementId 는 적재마다 다르다).
"""
import importlib.util
import io
import json
import shutil
import subprocess
import tarfile
import uuid

import pytest
from conftest import ROOT

NEO4J = ROOT / 'it' / 'neo4j'
CHECKS = NEO4J / 'v2' / 'seed_checks.cypher'
# 손으로 쓴 흐름 사본 · 두 판(구조판 · 전체판)이 있던 마지막 시드(main). 이 판으로 적재된 학생 PC 그래프가 새 시드로 옮겨 가는지 잰다.
PRE_CHANGE = 'ca3d9dd6'


def dump(g):
    """그래프 전부(노드 · 관계와 속성, 제약 · 색인)를 id 기준의 정렬된 목록으로."""
    def rows(cypher):
        return sorted(json.dumps(r, sort_keys=True, ensure_ascii=False, default=str) for r in g.query(cypher))
    return {'nodes': rows('MATCH (n) RETURN labels(n) AS labels, properties(n) AS props'),
            'rels': rows('MATCH (a)-[x]->(b) RETURN a.id AS a, type(x) AS type, b.id AS b, properties(x) AS props'),
            'schema': rows('SHOW CONSTRAINTS YIELD createStatement RETURN createStatement AS s')
            + rows("SHOW INDEXES YIELD type, owningConstraint, createStatement WHERE owningConstraint IS NULL AND type <> 'LOOKUP' "
                   "RETURN createStatement AS s")}


def differences(want, got):
    return {k: {'시드에만': sorted(set(want[k]) - set(got[k]))[:8], '비교 쪽에만': sorted(set(got[k]) - set(want[k]))[:8]}
            for k in want if want[k] != got[k]}


def check_queries():
    """seed.sh 가 실행하는 그대로: 빈 줄과 // 로 시작하는 줄을 뺀 줄 하나가 질의 하나."""
    return [line for line in CHECKS.read_text(encoding='utf-8').splitlines() if line and not line.startswith('//')]


def problems(g):
    return [row['problem'] for q in check_queries() for row in g.query(q)]


def run_seed(graph_server, seed_dir=None, **env):
    """kg-seed 명령(seed.sh)을 시험 그래프 컨테이너 안에서 돌린다. seed_dir 을 주면 그 폴더를 컨테이너에 복사해 SEED_DIR 로 쓴다."""
    env = {**graph_server.seed_env, 'NEO4J_URI': 'bolt://localhost:7687', **env}
    command = list(graph_server.seed_command)
    if seed_dir is not None:
        target = f'/tmp/seed-{uuid.uuid4().hex[:8]}'
        subprocess.run(['docker', 'cp', str(seed_dir), f'{graph_server.box.name}:{target}'], check=True, capture_output=True, timeout=120)
        env['SEED_DIR'] = target
        command = ['/bin/bash', f'{target}/seed.sh']
    args = ['docker', 'exec'] + [a for k, v in env.items() for a in ('-e', f'{k}={v}')] + [graph_server.box.name, *command]
    done = subprocess.run(args, capture_output=True, timeout=900)
    return done.returncode, (done.stdout + done.stderr).decode('utf-8', 'replace')


def test_시드를_적재한_그래프는_되읽기_검사를_모두_통과한다(seeded_graph):
    assert problems(seeded_graph) == []


def test_시드를_다시_적재해도_그래프가_같다(seeded_graph, graph_server):
    before = dump(seeded_graph)
    code, out = run_seed(graph_server)
    assert code == 0, out[-3000:]
    assert differences(before, dump(seeded_graph)) == {}


def test_다시_적재해도_학생이_만든_노드에_선을_긋지_않고_그_노드_때문에_멈추지도_않는다(seeded_graph, graph_server):
    """학생 이름 공간 노드(업무 스키마 실습)는 목표 · 대상 설비 · 예측 모델이 없어도 kg-seed 를 멈추지 않는다(학생 스키마 검사는 따로 한다)."""
    seeded_graph.query("CREATE (:Process {id:'s01:proc', ns:'s01', name:'학생 프로세스'}), (:Asset {id:'s01:asset', ns:'s01', code:'S01-1', name:'학생 설비'}), "
                       "(:AnomalyPattern {id:'s01:pattern', ns:'s01', code:'S01_ALARM', name:'학생 경보', rule:'x > 1'}), "
                       "(:Component {id:'s01:comp', ns:'s01', name:'학생 부품'})")
    code, out = run_seed(graph_server)
    assert code == 0, out[-3000:]
    crossing = seeded_graph.query("MATCH (a)-[r]-(b) WHERE a.ns = 's01' AND b.ns IS NULL RETURN a.id AS student, type(r) AS type, b.id AS seed")
    assert crossing == []


def test_옛_판으로_적재된_그래프에_새_시드를_적재하면_처음부터_새로_적재한_그래프와_같다(seeded_graph, graph_server, tmp_path):
    fresh = dump(seeded_graph)
    archive = subprocess.run(['git', '-C', str(ROOT), 'archive', PRE_CHANGE, 'it/neo4j'], check=True, capture_output=True).stdout
    tarfile.open(fileobj=io.BytesIO(archive)).extractall(tmp_path, filter='data')
    graph_server.reset()
    code, out = run_seed(graph_server, tmp_path / 'it' / 'neo4j')
    assert code == 0, '옛 판 시드가 들어가지 않았다: ' + out[-3000:]
    assert seeded_graph.query("MATCH (n:FlowNode {id:'task:compliance'}) RETURN count(n) AS n") == [{'n': 1}]   # 옛 판의 흐름 사본이 있는 그래프에서 출발
    code, out = run_seed(graph_server)
    assert code == 0, out[-3000:]
    # 공급사 · 견적은 시드 것이 아니다(업무 DB 정본 → scm_sync 동기화가 맞춘다) — 옛 판이 넣은 것은 동기화 몫이라 비교에서 뺀다
    seeded_graph.query('MATCH (s:Supplier) DETACH DELETE s')
    assert differences(fresh, dump(seeded_graph)) == {}


# 저장소 값과 달라진 시드 값(옛 판이 처음 적재 때 고정한 값 · 손 편집): [바꾸는 질의, 매개변수]. 시드 값을 바꾸는 편집 기능은 시스템에 없다.
DRIFT = [
    ("MATCH (p:AnomalyPattern {code:'COOLER_DEGRADATION'}) SET p.clearRule = 'TS1 < 50', p.clearHoldSeconds = 30, p.severity = 'LOW'", {}),
    ("MATCH (:AnomalyPattern {code:'FAN_VIBRATION'})-[t:TESTS]->(:InputData {id:'in:vs1'}) SET t.value = 1.5", {}),
    ("MATCH (p:AnomalyPattern {code:'PUMP_LEAKAGE'}), (i:InputData {id:'in:ce'}) MERGE (p)-[:TESTS {operator:'<', value:50}]->(i)", {}),
    ("MATCH (r:Rule {id:'rule:rank-value'}) SET r.rankingPolicy = $policy", {'policy': '{"version":1}'}),
    ("MATCH (m:Measure {id:'msr:op-profit'}) SET m.formula = 'msr:revenue - kpi:cost'", {}),
    ("MATCH (s:System {id:'sys:cep'}) SET s.name = 'CEP 탐지기 (Flink 대체)'", {}),
]


@pytest.mark.parametrize('drift, params', DRIFT, ids=['쿨러 해제 기준', '팬 경보 임계값', '펌프에 없는 검사', '순위 정책', '성과 지표 식', '시스템 이름'])
def test_저장소_값과_달라진_시드_값은_다음_적재에서_저장소_값으로_돌아간다(seeded_graph, graph_server, drift, params):
    fresh = dump(seeded_graph)
    seeded_graph.query(drift, **params)
    assert dump(seeded_graph) != fresh
    code, out = run_seed(graph_server)
    assert code == 0, out[-3000:]
    assert differences(fresh, dump(seeded_graph)) == {}


# 시드가 어긋난 그래프: [어긋나게 만드는 질의, 되읽기 검사가 내야 하는 문제 문장의 앞부분]
BROKEN = [
    ("MATCH (:AnomalyPattern {id:'pattern:cooler-degradation'})-[t:TESTS]->(:InputData {id:'in:ce'}) DELETE t",
     'pattern rule does not state exactly its TESTS pattern:cooler-degradation'),
    ("MATCH (p:AnomalyPattern {code:'COOLER_DEGRADATION'}) REMOVE p.detectionMode", 'course equipment pattern COOLER_DEGRADATION is missing or not held'),
    ("MATCH (p:AnomalyPattern {code:'LOW_PRESSURE_TRIP'}) DETACH DELETE p", 'course equipment pattern LOW_PRESSURE_TRIP is missing or not plc-trip'),
    ("MATCH (p:AnomalyPattern {code:'FAN_VIBRATION'}) REMOVE p.clearRule", 'held pattern without full detector contract pattern:fan-vibration'),
    ("MATCH (p:AnomalyPattern {code:'OVERHEAT_TRIP'})-[d:DETECTS]->() DELETE d", 'equipment pattern without symptom pattern:overheat-trip'),
    ("MATCH (r:Rule {id:'rule:ts1-hard'}) SET r.when = 'forecast_ts1 >= 60'", 'rule when does not state exactly its TESTS rule:ts1-hard'),
    ("MATCH (t:DecisionTable {id:'dt:compliance'}), (i:InputData {id:'in:oil-analysis'}) "
     "CREATE (t)-[:HAS_RULE]->(r:Rule {id:'rule:test-undeclared', order:99, effect:'WARN', when:'oil_analysis_out_of_spec == true'})"
     "-[:TESTS {operator:'==', value:true}]->(i)", 'rule rule:test-undeclared tests in:oil-analysis that dec:compliance does not require'),
    ("MATCH (t:DecisionTable {id:'dt:rank-actions'}) CREATE (t)-[:HAS_RULE]->(:Rule {id:'rule:test-rank-2', order:2, effect:'RANK', when:'true', rankingPolicy:'{}'})",
     'rank-actions table must hold exactly one ranking policy, has 2'),
    ("MATCH (:Measure {id:'msr:precedent'})-[i:INFLUENCES]->() DELETE i", 'leading measure reaches no lagging measure msr:precedent'),
    ("MATCH (:Process {id:'proc:alert-triage'})-[a:ACTS_ON]->() DELETE a", 'process without objective/asset proc:alert-triage'),
    ("CREATE (:FlowNode:Task {id:'task:hand-written', name:'손으로 쓴 흐름 노드', taskType:'user'})", 'flow node outside a deployed process version task:hand-written'),
    ("MATCH (s:Symptom) DETACH DELETE s", 'empty label Symptom'),
    ("MATCH (:AnomalyPattern {code:'PUMP_LEAKAGE'})-[d:DERIVED_FROM]->() DELETE d", 'pattern without source pattern:pump-leakage'),
]


@pytest.mark.parametrize('breaking, problem', BROKEN, ids=[p.split(' ')[0] + ':' + p.split(' ')[-1] for _, p in BROKEN])
def test_되읽기_검사는_시드가_어긋난_자리를_집어_낸다(seeded_graph, breaking, problem):
    seeded_graph.query(breaking)
    found = problems(seeded_graph)
    assert any(p.startswith(problem) for p in found), found


@pytest.mark.parametrize('lines, code, message', [
    (['MATCH (n:NoSuchLabel) RETURN n.id AS problem'], 0, 'read-back: 1 checks, 0 failed'),
    (["RETURN '일부러 낸 문제' AS problem"], 1, 'CHECK FAILED'),
    (['MATCH (n RETURN n'], 1, 'CHECK ERROR'),
    (['// 질의 없이 주석만'], 1, '되읽기 검사 파일에 질의가 없다'),
], ids=['문제 없음', '문제 행', '질의 오류', '질의 없음'])
def test_되읽기_질의가_실패하거나_문제_행을_내면_kg_seed가_실패한다(neo4j_graph, graph_server, tmp_path, lines, code, message):
    seed_dir = tmp_path / 'neo4j'
    (seed_dir / 'v2').mkdir(parents=True)
    shutil.copy(NEO4J / 'seed.sh', seed_dir / 'seed.sh')
    (seed_dir / 'v2' / 'constraints.cypher').write_text('RETURN 1;\n', encoding='utf-8', newline='\n')
    for name in ('instances.cypher', 'scenario_structure.cypher', 'pm_capabilities.cypher'):
        (seed_dir / 'v2' / name).write_text('RETURN 1;\n', encoding='utf-8', newline='\n')
    (seed_dir / 'v2' / 'seed_checks.cypher').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    got, out = run_seed(graph_server, seed_dir)
    assert (got, message in out) == (code, True), out[-3000:]


def test_neo4j에_닿지_못하면_kg_seed가_주소와_기다린_시간을_내고_멈춘다(graph_server):
    code, out = run_seed(graph_server, NEO4J_URI='bolt://localhost:1', SEED_WAIT_TRIES='2')
    assert code == 1
    assert 'kg-seed FAILED: Neo4j(bolt://localhost:1)에 6초 동안 닿지 못했다' in out, out[-2000:]


def _ontology_v2():
    spec = importlib.util.spec_from_file_location('ontology_v2', ROOT / 'workspace' / '개발' / 'scripts' / 'ontology_v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_적재한_시드는_스키마를_지킨다(seeded_graph):
    tool = _ontology_v2()
    with seeded_graph.driver.session() as s:
        nodes, rels = tool.read_rows(s)
    assert tool.validate(nodes, rels, tool.load_schema()) == []


def test_감지기는_시드의_감지_패턴_셋을_그대로_실행_정의로_읽는다(seeded_graph):
    from det.pattern_source import read_patterns
    from det.patterns import compile_catalog
    rows, names = read_patterns(seeded_graph.driver)
    catalog = compile_catalog(rows, profile='lite', time_scale=20)
    assert sorted(catalog) == ['COOLER_DEGRADATION', 'FAN_VIBRATION', 'PUMP_LEAKAGE']
    assert {names[c] for c in ('OVERHEAT_TRIP', 'LOW_PRESSURE_TRIP', 'HIGH_VIBRATION_TRIP')} == {'과열 인터록 트립', '저압 인터록 트립', '고진동 인터록 트립'}
    assert {code: p.summary for code, p in catalog.items()} == {r['code']: r['rule'] for r in rows}


def test_감지_기준이_수업_문서_절을_출처로_대면_그_절에_그_기준이_있고_문서에_있는_기준은_회사_설정이라고_하지_않는다(seeded_graph):
    """FK 검증: 패턴 출처가 모두 「감시 임계값 회사 설정값 (수업 문서에 없음)」이었는데 쿨러 값은 HM-8.3, 펌프 165 bar · 8.0 l/min 은 PM-2.10,
    재고 경보는 PR-7.2 에 있다(it/portal/www/samples). 출처가 절 번호(ref)면 그 절 본문에 출처 이름이 든 값(또는 패턴 코드)이 있어야 한다."""
    import re
    samples = ROOT / 'it' / 'portal' / 'www' / 'samples'
    rows = seeded_graph.query("MATCH (p:AnomalyPattern)-[:DERIVED_FROM]->(k:KnowledgeSource) WHERE p.ns IS NULL AND k.ref =~ '[A-Z]+-[0-9]+[.][0-9]+' "
                              "RETURN p.code AS code, k.ref AS ref, k.name AS name")

    def section(name, ref):
        # 출처 이름은 문서 번호와 절 이름을 「<문서 번호> 「<절 번호> <절 이름>」」 꼴로 적는다(it/neo4j/v2/instances.cypher — 전에는 「수업 문서 <번호>」)
        (doc,) = samples.glob(re.search(r'([A-Z]+-\d+) 「' + re.escape(ref) + ' ', name).group(1) + '_*.md')
        text = doc.read_text(encoding='utf-8')
        start = text.index(f'## {ref} ')
        end = text.find('\n## ', start + 1)
        return text[start:end if end > 0 else None]
    for r in rows:
        body = section(r['name'], r['ref'])
        values = re.findall(r'(\d+(?:\.\d+)?) ?(℃|%|bar|l/min|mm/s)', r['name'])
        assert (values and all(f'{v} {u}' in body or f'{v}{u}' in body for v, u in values)) or r['code'] in body, r
    assert {r['code'] for r in rows} >= {'COOLER_DEGRADATION', 'OVERHEAT_TRIP', 'PUMP_LEAKAGE', 'FAN_VIBRATION', 'SPARE_BELOW_MIN'}, rows
