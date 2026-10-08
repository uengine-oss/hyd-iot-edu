"""B4 (DECISIONS 110 ④) 선례 고정 — 교육용: 선례 몫은 미리 넣은 예시(시드 DecisionCase, seeded=true)만 센다.

같은 경보를 반복 판단해 승인할 때마다 DecisionCase가 하나씩 투영돼도(procsvc/case_projection.py) 선례 조회
(it/neo4j/templates/t3_precedents.cypher — agent의 mcp_kg와 dmn-mcp `precedents` 도구가 같은 파일을 쓴다)의 결과와
카드 순위·선례 몫은 바뀌지 않아야 한다. 단위 시험에는 Neo4j가 없으므로, 실제 템플릿 파일을 읽어 그 MATCH 모양과 WHERE 조건을
작은 메모리 그래프에 그대로 적용한다 — WHERE 줄을 지우면(학습 켜기) 아래 '일부러 깨뜨리기' 시험이 차이를 잡는다.
"""
import re
from pathlib import Path

import pytest

from agentsvc.tools import mcp_kg
from procsvc import case_projection
from test_cards import run

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'it' / 'neo4j' / 'templates' / 't3_precedents.cypher'
SEED = (ROOT / 'it' / 'neo4j' / 'v2' / 'instances.cypher').read_text(encoding='utf-8')


def _template_text() -> str:
    """What mcp_kg.KnowledgeGraph.template() runs: the file without its // comment lines."""
    kg = mcp_kg.KnowledgeGraph.__new__(mcp_kg.KnowledgeGraph)
    kg._cache = {}
    old = mcp_kg.TEMPLATES
    try:
        mcp_kg.TEMPLATES = TEMPLATE.parent
        return kg.template('t3_precedents')
    finally:
        mcp_kg.TEMPLATES = old


def _where(text: str) -> list[tuple[str, object]]:
    """WHERE dc.<prop> = <true|false|'str'> [AND …] — anything else is refused so a template change must update this test."""
    preds = []
    for line in text.splitlines():
        line = line.strip()
        if not line.upper().startswith('WHERE'):
            continue
        for term in re.split(r'\s+AND\s+', line[5:].strip(), flags=re.I):
            m = re.fullmatch(r"dc\.(\w+)\s*=\s*(true|false|'[^']*')", term.strip())
            if not m:
                raise AssertionError(f'시험이 모르는 선례 조건입니다: {term!r} — test_precedent_fixed를 함께 고치세요')
            value = {'true': True, 'false': False}.get(m.group(2), m.group(2).strip("'"))
            preds.append((m.group(1), value))
    return preds


def precedents(graph: dict, failure_mode: str, text: str | None = None) -> list[dict]:
    """t3_precedents over a memory graph: DecisionCase -FOR_INCIDENT-> Incident -DIAGNOSED_AS-> Cause -CAUSES-> FailureMode,
    the template's WHERE on dc, then group by the chosen skill (count, first five reasons)."""
    text = _template_text() if text is None else text
    assert 'FOR_INCIDENT' in text and 'DIAGNOSED_AS' in text and 'CAUSES' in text and 'CHOSE' in text
    preds = _where(text)
    out: dict[str, dict] = {}
    for case in graph['cases']:
        if graph['cause_fm'].get(graph['incident_cause'].get(case['incident'])) != failure_mode:
            continue
        if not all(case['props'].get(k) == v for k, v in preds):
            continue
        row = out.setdefault(case['skill'], {'skill': case['skill'], 'n': 0, 'reasons': []})
        row['n'] += 1
        row['reasons'] = (row['reasons'] + [case['props'].get('reason')])[:5]
    return sorted(out.values(), key=lambda r: r['skill'])


def _seed_graph() -> dict:
    """The seeded precedents exactly as it/neo4j/v2/instances.cypher writes them (§7 운영 기록)."""
    incidents = re.findall(r"\['(inc:demo-\d)','[^']+',datetime\('[^']+'\),'[^']+','([^']+)'\]", SEED)
    cases = re.findall(r"\['(case:demo-\d)','(inc:demo-\d)','([^']+)','[^']+',(true|false),'([^']*)'", SEED)
    assert len(incidents) == 3 and len(cases) == 3
    assert re.search(r"MERGE \(c:DecisionCase \{id: r\[0\]\}\) SET [^\n]*c\.seeded = true", SEED), '시드 DecisionCase에 seeded = true가 없습니다'
    return {'incident_cause': dict(incidents), 'cause_fm': {'cause:cooler-fin-fouling': 'fm:cooler', 'cause:pump-seal-wear': 'fm:pump'},
            'cases': [{'id': cid, 'incident': inc, 'skill': sk, 'props': {'seeded': True, 'reason': reason}}
                      for cid, inc, sk, _followed, reason in cases]}


def _approve_repeatedly(graph: dict, n: int, skill: str, incident='inc:live', cause='cause:cooler-fin-fouling') -> dict:
    """What approving the same alert n times leaves in the graph: case_projection.DECISION_CASE_Q nodes (no seeded)."""
    graph = {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in graph.items()}
    graph['incident_cause'][incident] = cause
    for i in range(n):
        graph['cases'].append({'id': f'case:live-{i}', 'incident': incident, 'skill': skill,
                               'props': {'reason': f'승인 {i}', 'source_incident_id': incident, 'status': 'EXECUTED'}})
    return graph


def test_projection_never_marks_a_case_as_seeded():
    assert 'seeded' not in case_projection.DECISION_CASE_Q


def test_the_template_counts_seeded_cases_only_with_the_education_comment():
    raw = TEMPLATE.read_text(encoding='utf-8')
    lines = raw.splitlines()
    where = next(i for i, l in enumerate(lines) if l.strip().upper().startswith('WHERE'))
    assert lines[where].strip() == 'WHERE dc.seeded = true'
    assert '교육용 고정: 시드 선례만 센다' in lines[where - 1] and 'DECISIONS 110 ④' in lines[where - 1]
    assert _where(_template_text()) == [('seeded', True)]


def test_seeded_precedents_are_counted():
    g = _seed_graph()
    assert precedents(g, 'fm:cooler') == [{'skill': 'skill:derate-night-clean', 'n': 1, 'reasons': ['팬 100 % 운전이 이번 주 이미 30시간 — 팬 수명 보호']},
                                          {'skill': 'skill:fan-max-derate', 'n': 1, 'reasons': ['OEM 납기 우선, 야간 세척 예정']}]
    assert precedents(g, 'fm:pump') == [{'skill': 'skill:switch-standby-pump', 'n': 1, 'reasons': ['예비 펌프 정비 완료 상태 확인']}]


def test_repeated_judgments_of_the_same_alert_do_not_change_precedents():
    g = _seed_graph()
    before = precedents(g, 'fm:cooler')
    after = precedents(_approve_repeatedly(g, 25, 'skill:fan-max-derate'), 'fm:cooler')
    assert after == before


def test_deliberately_removing_the_condition_turns_learning_on_and_is_caught():
    """일부러 깨뜨리기: WHERE 줄을 뺀 템플릿(제품 동작 = 승인할 때마다 선례가 쌓임)이면 결과가 달라진다."""
    g = _approve_repeatedly(_seed_graph(), 25, 'skill:fan-max-derate')
    learning = '\n'.join(l for l in _template_text().splitlines() if not l.strip().upper().startswith('WHERE'))
    fixed, grown = precedents(g, 'fm:cooler'), precedents(g, 'fm:cooler', text=learning)
    assert fixed != grown and next(r for r in grown if r['skill'] == 'skill:fan-max-derate')['n'] == 26
    with pytest.raises(AssertionError, match='시험이 모르는'):
        _where('WHERE dc.decidedAt < datetime()')


def _ranking(precedent_rows):
    r = run(precedents=precedent_rows)
    return [(o['id'], o['rank'], o['scoreParts']['precedent'], (o['precedent'] or {}).get('share')) for o in r['options']], r['recommended']


def test_card_ranking_and_precedent_share_stay_put_when_cases_pile_up():
    """test_cards 조치 카드(skill:fan · skill:mix)에 같은 경보를 20번 반복 승인한 사례가 쌓여도 순위·선례 몫 불변; 학습을 켜면 선례 몫이 달라진다."""
    g = {'incident_cause': {'inc:demo-a': 'cause:fouling', 'inc:demo-b': 'cause:fouling'}, 'cause_fm': {'cause:fouling': 'fm:cool'},
         'cases': [{'id': 'case:demo-a', 'incident': 'inc:demo-a', 'skill': 'skill:fan', 'props': {'seeded': True, 'reason': '예시 1'}},
                   {'id': 'case:demo-b', 'incident': 'inc:demo-b', 'skill': 'skill:mix', 'props': {'seeded': True, 'reason': '예시 2'}}]}
    before = _ranking(precedents(g, 'fm:cool'))
    piled = _approve_repeatedly(g, 20, 'skill:fan', cause='cause:fouling')
    assert _ranking(precedents(piled, 'fm:cool')) == before
    assert before[1] == 'skill:mix' and dict((o[0], o[2]) for o in before[0]) == {'skill:mix': 0.75, 'skill:fan': 0.75}
    learning = '\n'.join(l for l in _template_text().splitlines() if not l.strip().upper().startswith('WHERE'))
    grown = _ranking(precedents(piled, 'fm:cool', text=learning))
    assert grown != before      # 학습이 켜지면 반복 승인한 카드의 선례 몫이 커진다(0.75 → 1.42)
    assert dict((o[0], o[2]) for o in grown[0])['skill:fan'] > 0.75
