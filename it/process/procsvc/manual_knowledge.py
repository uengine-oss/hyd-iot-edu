"""확정 TODO C1: 문서 한 편에서 고장 지식 · 판단 규칙 · 원자 조치까지 — 추출 제안 → 사람 검토 → 적재.

문서(매뉴얼 · 지침 · 구매 기준)는 지금까지 절 · SOP · 단계만 만들었다. 이 모듈은 같은 문서에서 아래를 더 꺼내게 한다.
  - 고장 유형(FailureMode) — 일어나는 구성 요소(OCCURS_IN), 그 고장을 나타내는 기존 증상(Symptom -INDICATES->), 이어지는 고장(LEADS_TO)
  - 원인(Cause) — 사전 확률 prior, 원인이 일으키는 고장(CAUSES), 관련 부품(INVOLVES_PART), 흔드는 상태 변수(DISTURBS {sign})
  - 증거(Evidence) — 태그 · 집계 · 구간 · 비교 · 임계값. 시계열 SQL은 서버가 정해진 틀로 만든다(문서 · 에이전트가 SQL을 쓰지 않음)
  - 규칙(Rule) — 기존 결정표(진단 · 후보 · 규정)의 새 행. 기존 판단 입력을 TESTS, 출력 · 적용 대상, 감점 지표, 근거 절(DERIVED_FROM)
  - 원자 조치 값 — SOP가 쓰는 기존 Action과 값(CONSISTS_OF {value, seq}): 설비 명령 값 · 발주 공급사 · 작업지시 SOP. ADDRESSES(원인)
스키마 v2의 기존 클래스 · 관계만 쓴다. 새 Action · 입력 · 결정표 · 증상은 만들지 않는다(시드 구조에 있는 것만 가리킨다).
사람이 검토 화면에서 확인 · 수정한 것만 적재된다(manual_review.validate → manual_graph.commit).
"""
from __future__ import annotations

import re
from copy import deepcopy

from hydcommon.daq_contract import ALWAYS, AUX, DEADBAND

from . import kgadmin

KINDS = ('failure_modes', 'causes', 'evidence', 'rules')
LIMITS = {'failure_modes': 50, 'causes': 100, 'evidence': 200, 'rules': 200}
ID_RE = {'failure_modes': re.compile(r'^fm:[a-z0-9]+(?:-[a-z0-9]+)*$'), 'causes': re.compile(r'^cause:[a-z0-9]+(?:-[a-z0-9]+)*$'),
         'evidence': re.compile(r'^evd:[a-z0-9]+(?:-[a-z0-9]+)*$'), 'rules': re.compile(r'^rule:[a-z0-9]+(?:-[a-z0-9]+)*$')}
LABEL = {'failure_modes': 'FailureMode', 'causes': 'Cause', 'evidence': 'Evidence', 'rules': 'Rule'}
REF_RE = {p: re.compile(rf'^{p}:[a-z0-9]+(?:-[a-z0-9.]+)*$') for p in ('comp', 'sym', 'part', 'sv', 'msr', 'in', 'action', 'role', 'skill', 'fm', 'cause')}
SOP_RE = re.compile(r'^SOP-[A-Z0-9]+(?:-[A-Z0-9]+)*$')
TABLES = {'dt:diagnose-cause': ('SELECT',), 'dt:action-candidates': ('SELECT',), 'dt:compliance': ('EXCLUDE', 'WARN', 'PENALTY')}
OPERATORS = ('<', '<=', '>', '>=', '==', '!=')
AGGREGATES = ('avg', 'max', 'min', 'range')
EXPECTS = {'lt': '<', 'gt': '>', 'gte': '>='}
TAGS = frozenset(ALWAYS | AUX | set(DEADBAND))
RELATIONS = kgadmin.FAILURE_RELATIONS      # 즉시 완화 · 근본 조치 · 예방 조치(정기 정비)
SKILL_KINDS = ('control', 'work_order')
ACTIONS_MAX = 10


def _text(value, name, limit=300, required=True):
    if value is None and not required:
        return ''
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f'{name}: 비어 있지 않은 문자열이 필요합니다')
    return value.strip()[:limit]


def _ref(value, prefix, name):
    if not isinstance(value, str) or not REF_RE[prefix].fullmatch(value):
        raise ValueError(f'{name}: {prefix}:… 형식의 온톨로지 id가 필요합니다 ({value!r})')
    return value


def _refs(value, prefix, name, limit=20):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f'{name}: 최대 {limit}개의 id 목록이어야 합니다')
    out = []
    for v in value:
        v = _ref(v, prefix, name)
        if v not in out:
            out.append(v)
    return out


def _number(value, name, low=None, high=None):
    if type(value) not in (int, float) or value != value or value in (float('inf'), float('-inf')):
        raise ValueError(f'{name}: 유한한 숫자가 필요합니다')
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f'{name}: {low}~{high} 범위여야 합니다')
    return value


def _scalar(value, name):
    if isinstance(value, bool) or type(value) is str and value.strip() and len(value) <= 120:
        return value
    return _number(value, name)


def _sign(value, name):
    sign = {'+': 1, '-': -1, 1: 1, -1: -1, '1': 1, '-1': -1}.get(value) if not isinstance(value, bool) else None
    if sign is None:
        raise ValueError(f'{name}: sign은 +/- 또는 1/-1 이어야 합니다')
    return sign


def _skill_ref(value, sops, name):
    """A rule/WO value pointing at a skill: an SOP id of this document, or an existing skill id from the catalog."""
    if isinstance(value, str) and SOP_RE.fullmatch(value):
        if value not in sops:
            raise ValueError(f'{name}: {value}는 이 문서의 SOP가 아닙니다. 다른 문서의 스킬은 skill:… id로 가리키세요')
        return value
    return _ref(value, 'skill', name)


def evidence_sql(tag, aggregate, window):
    value = 'max(value) - min(value)' if aggregate == 'range' else f'{aggregate}(value)'
    return (f"SELECT {value} AS value FROM tag_1s WHERE asset = %(asset)s AND name = '{tag}' "
            f"AND time > now() - interval '{window} seconds'")


def evidence_rule(tag, aggregate, window, expect, threshold):
    agg = f'max({tag}) - min({tag})' if aggregate == 'range' else f'{aggregate}({tag})'
    return f'{agg} over {window}s {EXPECTS[expect]} {threshold:g}'


def when_text(tests):
    """The readable rule condition, written from the TESTS so the two never disagree (ontology_v2 integrity checks it)."""
    def fmt(v):
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, str):
            return f"'{v}'"
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    return ' and '.join(f"{t['variable']} {t['operator']} {fmt(t['value'])}" for t in tests)


def blanks_as_absent(link):
    """추출 지시는 확인할 수 없는 link 값을 「비워 두라」고 한다. 빈 글('')로 비운 칸은 값 없음(null)과 같다 — 2026-10-23 리허설에서
    중계 모델이 고장 유형 · 승인 역할을 ''로 비워 PM-02 · PR-07 추출이 세 번 다 「fm:… 형식의 id가 필요합니다 ('')」로 거부됐다.
    원자 조치의 빈 값도 같다. 값이 꼭 필요한 곳(적재의 고장 유형 등)은 여전히 「필요합니다」로 거부된다."""
    out = {k: (None if isinstance(v, str) and not v.strip() else v) for k, v in link.items()}
    if isinstance(out.get('actions'), list):
        out['actions'] = [dict(a, value=None) if isinstance(a, dict) and isinstance(a.get('value'), str) and not a['value'].strip() else a
                          for a in out['actions']]
    return out


def validate_link(sop, link, *, sops, require_failure_mode):
    """One SOP's reviewed (or suggested) connection: failure mode · relation · kind · approver · atomic actions · addressed causes.
    affects is validated by manual_review.validate_affects (kept there for the A079 shape)."""
    if link is None:
        link = {}
    if not isinstance(link, dict):
        raise ValueError(f'{sop}: 연결은 객체여야 합니다')
    link = blanks_as_absent(link)
    if link.get('kind') == 'reference':
        from .manual_references import reference_shape
        return reference_shape(sop, link)
    out = {}
    if link.get('purchase_comparison_policy') is not None:
        if link.get('scope') != 'purchase' or link.get('executable') is not True:
            raise ValueError('구매 비용 정책은 명시 실행 구매 SOP에만 연결합니다')
        from hydcommon.purchase_comparison import policy
        out['purchase_comparison_policy']=policy(link['purchase_comparison_policy'])
    if link.get('maintenance_policy') is not None:
        if link.get('scope') == 'purchase' or link.get('kind') == 'reference':
            raise ValueError('PM 실행 정책은 구매·비실행 참고 절차에 붙이지 않습니다')
        from hydcommon.maintenance_policy import policy
        out['maintenance_policy']=policy(link['maintenance_policy'])
    if link.get('scope') not in (None, 'fault', 'purchase'):
        raise ValueError(f'{sop}: 스킬 영역은 기존 고장 조치 또는 purchase입니다')
    if link.get('scope') != 'purchase' and (link.get('executable') is not None or link.get('parts') is not None or link.get('supplier_policy') is not None):
        raise ValueError(f'{sop}: executable·Part 업무 범위는 명시 purchase SOP에만 둡니다')
    if link.get('scope') == 'purchase':
        from hydcommon.skill_scope import purchase_shape
        out.update(purchase_shape(link, source_backed=True))
    fm = link.get('failureMode')
    if fm is not None or require_failure_mode and link.get('scope') != 'purchase':
        out['failureMode'] = _ref(fm, 'fm', f'{sop} 고장 유형')
    if link.get('relation') is not None:
        if link['relation'] not in RELATIONS:
            raise ValueError(f'{sop}: ' + kgadmin.FAILURE_RELATION_HELP)
        out['relation'] = link['relation']
    if link.get('kind') is not None:
        if link['kind'] not in SKILL_KINDS:
            raise ValueError(f'{sop}: 스킬 종류는 control 또는 work_order')
        out['kind'] = link['kind']
    if link.get('approver') is not None:
        out['approver'] = _ref(link['approver'], 'role', f'{sop} 승인 역할')
    actions = link.get('actions')
    if actions is not None:
        if not isinstance(actions, list) or len(actions) > ACTIONS_MAX:
            raise ValueError(f'{sop}: 원자 조치는 최대 {ACTIONS_MAX}개의 {{action, value}} 목록입니다')
        out['actions'] = []
        for a in actions:
            if not isinstance(a, dict):
                raise ValueError(f'{sop}: 원자 조치는 객체여야 합니다')
            value = a.get('value')
            if value is not None:
                value = _scalar(value, f'{sop} 원자 조치 값')
            out['actions'].append(dict(action=_ref(a.get('action'), 'action', f'{sop} 원자 조치'), value=value))
    if link.get('addresses') is not None:
        out['addresses'] = _refs(link['addresses'], 'cause', f'{sop} 대상 원인')
    if link.get('affects') is not None:
        out['affects'] = link['affects']
    return out


def validate(knowledge, *, sections, sops, anchor):
    """Shape · enum · range · internal reference checks of the knowledge part of a proposal or a reviewed body.
    `anchor(value)` validates (and may complete) one citation. Graph existence is checked at commit (check_graph)."""
    if knowledge is None:
        return None
    if not isinstance(knowledge, dict) or set(knowledge) - set(KINDS):
        raise ValueError(f'knowledge는 {list(KINDS)} 목록을 가진 객체입니다')
    out, seen = {}, set()
    for kind in KINDS:
        items = knowledge.get(kind) or []
        if not isinstance(items, list) or len(items) > LIMITS[kind]:
            raise ValueError(f'knowledge.{kind}: 최대 {LIMITS[kind]}개의 목록이어야 합니다')
        out[kind] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f'knowledge.{kind}: 항목은 객체여야 합니다')
            nid = item.get('id')
            if not isinstance(nid, str) or not ID_RE[kind].fullmatch(nid) or nid in seen:
                raise ValueError(f'knowledge.{kind}: id 형식 또는 중복을 확인하세요 ({nid!r}, 예: {ID_RE[kind].pattern})')
            seen.add(nid)
            section = item.get('section')
            if section not in sections:
                raise ValueError(f'{nid}: section {section!r}이 sections의 ref에 없습니다')
            base = dict(id=nid, section=section, anchor=anchor(item.get('anchor')))
            out[kind].append(_ITEM[kind](item, base, sops))
    own = {k: {i['id'] for i in out[k]} for k in KINDS}
    for c in out['causes']:
        if c['failure_mode'] not in own['failure_modes'] and not c['failure_mode'].startswith('fm:'):
            raise ValueError(f"{c['id']}: 고장 유형이 필요합니다")
    for e in out['evidence']:
        if e['cause'] not in own['causes'] and not REF_RE['cause'].fullmatch(e['cause']):
            raise ValueError(f"{e['id']}: 원인 id가 필요합니다")
    return out


def _fm(item, base, sops):
    return dict(base, name=_text(item.get('name'), f"{base['id']} 이름", 120),
                component=_ref(item.get('component'), 'comp', f"{base['id']} 구성 요소"),
                symptoms=_refs(item.get('symptoms'), 'sym', f"{base['id']} 증상"),
                leads_to=_refs(item.get('leads_to'), 'fm', f"{base['id']} 이어지는 고장"))


def _cause(item, base, sops):
    nid = base['id']
    aliases = item.get('aliases') or []
    if not isinstance(aliases, list) or len(aliases) > 10:
        raise ValueError(f'{nid}: aliases는 최대 10개의 문자열 목록입니다')
    disturbs = []
    for d in item.get('disturbs') or []:
        if not isinstance(d, dict):
            raise ValueError(f'{nid}: disturbs 항목은 {{target, sign}} 객체입니다')
        disturbs.append(dict(target=_ref(d.get('target'), 'sv', f'{nid} 외란 변수'), sign=_sign(d.get('sign', 1), f'{nid} 외란')))
    return dict(base, name=_text(item.get('name'), f'{nid} 이름', 120), aliases=[_text(a, f'{nid} 별칭', 60) for a in aliases],
                prior=_number(item.get('prior'), f'{nid} 사전 확률 prior', 0.0, 1.0),
                failure_mode=_ref(item.get('failure_mode'), 'fm', f'{nid} 고장 유형'),
                parts=_refs(item.get('parts'), 'part', f'{nid} 부품'), disturbs=disturbs)


def _evidence(item, base, sops):
    nid = base['id']
    tag, agg, expect = item.get('tag'), item.get('aggregate'), item.get('expect')
    if tag not in TAGS:
        raise ValueError(f'{nid}: tag는 수집 계약의 태그여야 합니다 {sorted(TAGS)}')
    if agg not in AGGREGATES:
        raise ValueError(f'{nid}: aggregate는 {AGGREGATES} 중 하나')
    if expect not in EXPECTS:
        raise ValueError(f'{nid}: expect는 {tuple(EXPECTS)} 중 하나')
    window = item.get('window_seconds')
    if type(window) is not int or not 1 <= window <= 3600:
        raise ValueError(f'{nid}: window_seconds는 1~3600 정수')
    threshold = _number(item.get('threshold'), f'{nid} 임계값')
    return dict(base, cause=_ref(item.get('cause'), 'cause', f'{nid} 원인'), name=_text(item.get('name'), f'{nid} 이름', 120),
                tag=tag, aggregate=agg, window_seconds=window, expect=expect, threshold=threshold,
                weight=_number(item.get('weight'), f'{nid} 가중치 weight', 0.0, 1.0),
                rule=evidence_rule(tag, agg, window, expect, threshold), sql=evidence_sql(tag, agg, window))


def _rule(item, base, sops):
    nid = base['id']
    table, effect = item.get('table'), item.get('effect')
    if table not in TABLES:
        raise ValueError(f'{nid}: table은 {list(TABLES)} 중 하나 (순위 정책 dt:rank-actions는 회사 규정이라 문서가 바꾸지 않습니다)')
    if effect not in TABLES[table]:
        raise ValueError(f'{nid}: {table}의 effect는 {TABLES[table]} 중 하나')
    tests = item.get('tests')
    if not isinstance(tests, list) or not 1 <= len(tests) <= 8:
        raise ValueError(f'{nid}: TESTS(임계값 검사)가 1~8개 필요합니다')
    checked = []
    for t in tests:
        if not isinstance(t, dict) or t.get('operator') not in OPERATORS:
            raise ValueError(f'{nid}: 검사는 {{input, operator, value, unit}}이고 operator는 {OPERATORS} 중 하나')
        if t.get('value') is None:
            raise ValueError(f'{nid}: 검사 값(value)이 필요합니다')
        checked.append(dict(input=_ref(t.get('input'), 'in', f'{nid} 입력'), operator=t['operator'],
                            value=_scalar(t['value'], f'{nid} 검사 값'), unit=_text(t.get('unit'), f'{nid} 단위', 20, required=False) or None))
    outputs, applies = item.get('outputs') or [], item.get('applies_to') or []
    if not isinstance(outputs, list) or not isinstance(applies, list) or len(outputs) > 30 or len(applies) > 30:
        raise ValueError(f'{nid}: outputs · applies_to는 최대 30개의 목록입니다')
    if effect == 'SELECT':
        if applies or not outputs:
            raise ValueError(f'{nid}: SELECT 규칙은 outputs(원인 또는 SOP)가 필요하고 applies_to는 쓰지 않습니다')
        if table == 'dt:diagnose-cause':
            outputs = [_ref(o, 'cause', f'{nid} 출력 원인') for o in outputs]
        else:
            outputs = [_skill_ref(o, sops, f'{nid} 출력 SOP') for o in outputs]
    else:
        if outputs:
            raise ValueError(f'{nid}: {effect} 규칙은 applies_to(대상 SOP, 비우면 모든 후보)를 씁니다')
        applies = [_skill_ref(o, sops, f'{nid} 적용 SOP') for o in applies]
    outputs, applies = list(dict.fromkeys(outputs)), list(dict.fromkeys(applies))
    penalty = item.get('penalty')
    penalizes = item.get('penalizes')
    if effect == 'PENALTY':
        penalty = _number(penalty, f'{nid} 감점액(만원)', 0, 100000)
        penalizes = _ref(penalizes, 'msr', f'{nid} 감점 지표')
    elif penalty is not None or penalizes is not None:
        raise ValueError(f'{nid}: penalty · penalizes는 PENALTY 규칙에만 씁니다')
    order = item.get('order')
    if order is not None and (type(order) is not int or not 1 <= order <= 9999):
        raise ValueError(f'{nid}: order는 1~9999 정수')
    return dict(base, table=table, effect=effect, tests=checked, outputs=outputs, applies_to=applies, penalty=penalty,
                penalizes=penalizes, order=order, annotation=_text(item.get('annotation'), f'{nid} 설명', 500, required=False))


_ITEM = {'failure_modes': _fm, 'causes': _cause, 'evidence': _evidence, 'rules': _rule}


def anchors(knowledge):
    for kind in KINDS:
        for item in (knowledge or {}).get(kind) or []:
            if isinstance(item, dict) and isinstance(item.get('anchor'), dict):
                yield item['anchor']


def skill_of(ref, skill_id):
    return skill_id(ref) if SOP_RE.fullmatch(ref) else ref


# ------------------------------------------------------------------ graph side (read-only; commit-time checks)

CATALOG_Q = {
    'components': 'MATCH (n:Component) RETURN n.id AS id, n.name AS name ORDER BY id',
    'symptoms': 'MATCH (n:Symptom) OPTIONAL MATCH (p:AnomalyPattern)-[:DETECTS]->(n) '
                'RETURN n.id AS id, n.name AS name, [c IN collect(DISTINCT p.code) WHERE c IS NOT NULL] AS patterns ORDER BY id',
    'patterns': 'MATCH (n:AnomalyPattern) RETURN n.id AS id, n.code AS code, n.name AS name ORDER BY id',
    'parts': 'MATCH (n:Part) OPTIONAL MATCH (n)-[x:SUPPLIED_BY]->(s:Supplier) OPTIONAL MATCH (c:Component)-[:USES_PART]->(n) '
             'RETURN n.id AS id, n.name AS name, n.partNo AS partNo, collect(DISTINCT c.id) AS usedIn, '
             '[r IN collect(DISTINCT {supplier:s.id, name:s.name, avl:s.avl, price:x.price, failRate:x.failRate, leadDays:x.leadDays}) '
             'WHERE r.supplier IS NOT NULL] AS suppliers ORDER BY id',
    'suppliers': 'MATCH (n:Supplier) RETURN n.id AS id, n.name AS name, n.avl AS avl ORDER BY id',
    'state_variables': 'MATCH (n:StateVariable) RETURN n.id AS id, n.name AS name, n.unit AS unit, n.kind AS kind ORDER BY id',
    'measures': 'MATCH (n:Measure) RETURN n.id AS id, n.name AS name, n.unit AS unit ORDER BY id',
    'actions': 'MATCH (n:Action) OPTIONAL MATCH (n)-[:TARGETS]->(t) RETURN n.id AS id, n.name AS name, n.code AS code, '
               'n.kind AS kind, n.param AS param, n.min AS min, n.max AS max, t.id AS target ORDER BY id',
    'roles': 'MATCH (n:Role) RETURN n.id AS id, n.name AS name, n.level AS level ORDER BY id',
    'systems': 'MATCH (n:System) RETURN n.id AS id, n.name AS name ORDER BY id',
    'decision_tables': 'MATCH (d:Decision)-[:IMPLEMENTED_BY]->(t:DecisionTable) OPTIONAL MATCH (d)-[:REQUIRES_INPUT]->(i:InputData) '
                       'RETURN t.id AS id, t.name AS name, d.id AS decision, '
                       'collect({id:i.id, variable:i.variable, typeRef:i.typeRef, name:i.name}) AS inputs ORDER BY id',
    'failure_modes': 'MATCH (n:FailureMode) OPTIONAL MATCH (n)-[:OCCURS_IN]->(c:Component) RETURN n.id AS id, n.name AS name, c.id AS component ORDER BY id',
    'causes': 'MATCH (n:Cause) OPTIONAL MATCH (n)-[:CAUSES]->(f:FailureMode) RETURN n.id AS id, n.name AS name, collect(f.id) AS failureModes ORDER BY id',
    'skills': 'MATCH (n:Skill) RETURN n.id AS id, n.sopId AS sopId, n.name AS name, n.kind AS kind, '
              'n.scope AS scope, n.executable AS executable, n.supplier_policy AS supplier_policy ORDER BY id',
    # 고장 유형만으로 고르는 조치 후보 규칙이 있는 고장 유형: 고장 조치(MITIGATED_BY · REMEDIED_BY) SOP는 적재 때 이 규칙에 자동으로
    # 합류한다(skill_graph.CANDIDATE_RULES_Q 와 같은 조건). 예방 정비 · 구매 SOP는 합류하지 않는다 — 문서가 후보 규칙을 진술해야 한다.
    'candidate_failure_modes': "MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]->(r:Rule)-[t:TESTS]->(i:InputData) "
                               "WITH r, collect({input:i.id, operator:t.operator, value:t.value}) AS tests "
                               "WHERE size(tests)=1 AND tests[0].input='in:failure-mode' AND tests[0].operator='==' "
                               "RETURN DISTINCT tests[0].value AS id ORDER BY id",
}


def catalog(session):
    """What a document may point at: the ontology's existing ids (structure seed + earlier documents). The extraction agent gets
    this pinned as input (it cannot invent Action codes, inputs or symptoms), and the review screen uses it for its pickers."""
    def read(tx):
        out = {k: tx.run(q).data() for k, q in CATALOG_Q.items()}
        for t in out['decision_tables']:
            t['inputs'] = [i for i in t['inputs'] if i.get('id')]
        from . import manual_references
        pinned = manual_references.contracts(tx, [s['id'] for s in out['skills']])
        for skill in out['skills']:
            if skill['id'] in pinned:
                skill['reference_contract'] = {k: v for k, v in pinned[skill['id']].items() if k != 'contract'}
        out['evidence_tags'] = sorted(TAGS)
        out['rule_tables'] = {k: list(v) for k, v in TABLES.items()}
        return out
    return session.execute_read(read)


def conflicts(session, knowledge, document=None):
    """Before commit (review aid): which proposed knowledge ids already exist in the graph and who holds them. Read-only;
    the commit-time ownership check stays the hard rule. A reviewer drops such an item and refers to the existing id."""
    ids = [(LABEL[k], i['id']) for k in KINDS for i in (knowledge or {}).get(k) or [] if isinstance(i, dict) and i.get('id')]
    if not ids:
        return []
    def read(tx):
        out = []
        for label, nid in ids:
            row = tx.run(f'MATCH (n:{label} {{id:$id}}) RETURN n.id AS id', id=nid).single()
            if not row:
                continue
            doc = tx.run('MATCH (d:ManualIngestionDocument) WHERE d.snapshot CONTAINS $needle RETURN d.id AS id LIMIT 1',
                         needle='"id":"' + nid + '"').single()
            if doc and doc['id'] == document:
                continue                      # the same document's earlier batch — a re-ingest replaces it
            out.append(dict(id=nid, label=label, owner=doc['id'] if doc else 'seed', kind='other_document' if doc else 'seed_or_admin'))
        return out
    return session.execute_read(read)


def graph_semantics(plan, catalog):
    """Pure Action/Rule checks shared by preview and commit. Never changes the proposal.

    Returns a copy with resolved rule variables and structured issues. The
    catalog is supplied by the caller; an unavailable catalog is not an empty one.
    """
    plan = deepcopy(plan)
    knowledge = plan.get('knowledge') or {}
    issues = []
    own_sops = {p['id'] for p in plan['procedures']}
    actions = {r['id']: r for r in catalog['actions']}
    suppliers = {r['id'] for r in catalog['suppliers']}
    sops = {r.get('sopId', r.get('sop')) for r in catalog['skills']}
    tables = {r['id']: r for r in catalog['decision_tables']}

    def issue(code, owner, field, message):
        issues.append(dict(code=code, sop=owner, field=field, message=message))
    for p in plan['procedures']:
        if p.get('kind') == 'reference':
            from .manual_references import reference_shape
            try:
                reference_shape(p['id'], p)
            except ValueError as exc:
                issue('REFERENCE_CONTRACT_INVALID', p['id'], 'link', str(exc))
            continue
        if p.get('scope') == 'purchase':
            from hydcommon.skill_scope import purchase_shape
            try:
                purchase_shape(p, source_backed=True)
            except ValueError as exc:
                issue('PURCHASE_CONTRACT_INVALID', p['id'], 'link', f"{p['id']}: {exc}")
            parts = {r['id']: r for r in catalog['parts']}
            purchase_action = actions.get('action:purchase-request')
            if p.get('executable') and (not purchase_action or purchase_action.get('code') != 'PR_CREATE' or purchase_action.get('kind') != 'transaction'):
                issue('PURCHASE_ACTION_CONTRACT_INVALID', p['id'], 'link.actions', f"{p['id']}: 구매요청 Action의 실제 계약이 PR_CREATE transaction이 아닙니다")
            if not any(r['id'] == 'sys:erp' for r in catalog['systems']):
                issue('PURCHASE_SYSTEM_NOT_FOUND', p['id'], 'link.scope', f"{p['id']}: 구매 실행 시스템 sys:erp가 현재 지식에 없습니다")
            for part in p.get('parts') or []:
                if part not in parts:
                    issue('PURCHASE_PART_NOT_FOUND', p['id'], 'link.parts', f"{p['id']}: 구매 범위 부품 {part}가 없습니다")
                elif p.get('executable') and p.get('supplier_policy'):
                    available = parts[part].get('suppliers') or []
                    if not available:
                        issue('PURCHASE_SUPPLIER_PART_MISMATCH', p['id'], 'link.parts', f"{p['id']}: {part}의 실제 공급 관계가 없습니다")
                    elif p['supplier_policy'] == 'oem' and not any(s.get('name') == 'B-OEM (순정)' for s in available):
                        issue('PURCHASE_OEM_SOURCE_MISSING', p['id'], 'link.supplier_policy', f"{p['id']}: {part}의 정본 순정 공급사 라벨 B-OEM (순정)이 없습니다")
                elif p.get('executable') and not p.get('supplier_policy'):
                    supplier = (p.get('actions') or [{}])[0].get('value')
                    if not any(s.get('supplier') == supplier for s in parts[part].get('suppliers') or []):
                        issue('PURCHASE_SUPPLIER_PART_MISMATCH', p['id'], 'link.actions', f"{p['id']}: {supplier} 공급사와 {part}의 실제 SUPPLIED_BY 관계가 없습니다")
            if p.get('executable') and not any(r['id'] == p.get('approver') for r in catalog['roles']):
                issue('PURCHASE_ROLE_NOT_FOUND', p['id'], 'link.approver', f"{p['id']}: 명시한 구매 승인 역할이 없습니다")
        for seq, a in enumerate(p.get('actions') or [], 1):
            act = actions.get(a['action'])
            where = f"{p['id']} 원자 조치 {seq}"
            if not act:
                issue('ACTION_NOT_FOUND', p['id'], 'link.actions', f"{where}: Action {a['action']}이 온톨로지에 없습니다(문서는 새 원자 조치를 만들지 않습니다)")
                continue
            v = a['value']
            if act['kind'] == 'command':
                if act['min'] is not None or act['max'] is not None:
                    if type(v) not in (int, float) or isinstance(v, bool) or \
                            (act['min'] is not None and v < act['min']) or (act['max'] is not None and v > act['max']):
                        issue('ACTION_VALUE_RANGE', p['id'], 'link.actions', f"{where}: {act['code']} 값 {v!r}은 {act['min']}~{act['max']} 범위여야 합니다")
            elif act['code'] == 'PR_CREATE' and v not in suppliers and not (p.get('scope') == 'purchase' and p.get('supplier_policy') and v is None):
                issue('SUPPLIER_NOT_FOUND', p['id'], 'link.actions', f"{where}: 구매요청 값은 공급사 id여야 합니다({v!r})")
            elif act['code'] in ('WO_CREATE','WO_RESCHEDULE') and v not in own_sops and v not in sops:
                issue('SOP_NOT_FOUND', p['id'], 'link.actions', f"{where}: 작업지시 값은 SOP 번호여야 합니다({v!r})")
            if act['kind'] == 'command' and p['kind'] != 'control':
                issue('COMMAND_IN_WORK_ORDER', p['id'], 'link.actions', f"{where}: 설비 명령({act['code']})은 control 스킬에만 둡니다")
    for r in knowledge.get('rules') or []:
        table = tables.get(r['table'])
        if not table:
            issue('DECISION_TABLE_NOT_FOUND', r['id'], 'knowledge.rules.table', f"{r['id']}: 결정표 {r['table']}이 없습니다")
            continue
        inputs = {i['id']: i for i in table['inputs']}
        for t in r['tests']:
            if t['input'] not in inputs:
                issue('RULE_INPUT_NOT_DECLARED', r['id'], 'knowledge.rules.tests',
                      f"{r['id']}: {table['decision']}이 입력 {t['input']}을 선언하지 않았습니다(REQUIRES_INPUT). 선언된 입력: {sorted(inputs)}")
            else:
                t['variable'] = inputs[t['input']]['variable']
        if r.get('effect') == 'SELECT' and r.get('table') == 'dt:action-candidates':
            own = {ref: p for p in plan['procedures'] for ref in (p['id'], kgadmin.skill_id(p['id']))}
            stored = {row['id']: row for row in catalog['skills'] if row.get('id')}
            outputs = [own.get(ref) or stored.get(ref) for ref in r.get('outputs') or []]
            for output in outputs:
                if output and (output.get('kind') == 'reference' or output.get('executable') is False):
                    issue('RULE_OUTPUT_NOT_EXECUTABLE', r['id'], 'knowledge.rules.outputs', f"{r['id']}: 참고 절차는 실행 후보 Rule 출력이 될 수 없습니다")
                if output and output.get('id') in own and any(t.get('variable') == 'pattern' and t.get('value') == 'PM_DUE' for t in r['tests']):
                    effect_codes = [actions.get(a['action'],{}).get('code') for a in output.get('actions') or []]
                    if sum(code in ('WO_CREATE','WO_RESCHEDULE') for code in effect_codes) != 1:
                        issue('PM_ORDER_EFFECT_REQUIRED',output['id'],'link.actions',f"{output['id']}: PM 실행 후보에는 원문 기반 오더 발행 또는 기존 오더 일정 변경 Action 하나가 필요합니다")
            purchase = [p for p in outputs if p and p.get('scope') == 'purchase']
            if purchase:
                if any(p.get('executable') is not True for p in purchase):
                    issue('RULE_OUTPUT_NOT_EXECUTABLE', r['id'], 'knowledge.rules.outputs', f"{r['id']}: 참고 보관 구매 절차는 실행 후보 Rule의 출력이 될 수 없습니다")
                if any(p and p.get('scope') != 'purchase' for p in outputs):
                    issue('RULE_OUTPUT_SCOPE_MIXED', r['id'], 'knowledge.rules.outputs', f"{r['id']}: 구매 후보와 고장 조치 후보를 같은 Rule에 섞지 않습니다")
                if not any(t.get('variable') == 'pattern' and t.get('operator') == '==' and t.get('value') == 'SPARE_BELOW_MIN' for t in r['tests']):
                    issue('PURCHASE_RULE_PATTERN_REQUIRED', r['id'], 'knowledge.rules.tests', f"{r['id']}: 구매 후보 Rule은 pattern == SPARE_BELOW_MIN을 명시해야 합니다")
    return plan, issues


def check_graph(session, plan, skill_id):
    """Commit rechecks the live catalog before writes and keeps its legacy plan contract."""
    def read(tx):
        out = dict(actions=tx.run(CATALOG_Q['actions']).data(),
                    suppliers=tx.run('MATCH (s:Supplier) RETURN s.id AS id').data(),
                    skills=tx.run(CATALOG_Q['skills']).data(),
                    decision_tables=tx.run(CATALOG_Q['decision_tables']).data())
        if any(p.get('scope') == 'purchase' for p in plan['procedures']):
            out.update({key: tx.run(CATALOG_Q[key]).data() for key in ('parts', 'systems', 'roles')})
        return out
    checked, issues = graph_semantics(plan, session.execute_read(read))
    if issues:
        raise ValueError(' / '.join(i['message'] for i in issues))
    if 'knowledge' in checked:
        plan['knowledge'] = checked['knowledge']
    from . import manual_references
    references = session.execute_read(lambda tx: manual_references.check_plan(tx, plan))
    if references:
        plan['references'] = references
    return plan


def desired(plan, node, edge, sections, skill_id):
    """Graph additions of the knowledge part (manual_graph.desired calls this with its node/edge builders)."""
    k = plan.get('knowledge') or {}
    fms, causes = {}, {}
    for f in k.get('failure_modes') or []:
        fms[f['id']] = node('FailureMode', f['id'], name=f['name'])
    for c in k.get('causes') or []:
        props = dict(name=c['name'], prior=c['prior'])
        if c['aliases']:
            props['aliases'] = c['aliases']
        causes[c['id']] = node('Cause', c['id'], **props)
    for e in k.get('evidence') or []:
        n = node('Evidence', e['id'], name=e['name'], rule=e['rule'], sql=e['sql'], expect=e['expect'], threshold=e['threshold'],
                 weight=e['weight'], tag=e['tag'], windowSeconds=e['window_seconds'])
        edge(causes.get(e['cause'], ('Cause', e['cause'])), 'EVIDENCED_BY', n)
    for f in k.get('failure_modes') or []:
        edge(fms[f['id']], 'OCCURS_IN', ('Component', f['component']))
        for s in f['symptoms']:
            edge(('Symptom', s), 'INDICATES', fms[f['id']])
        for nxt in f['leads_to']:
            edge(fms[f['id']], 'LEADS_TO', fms.get(nxt, ('FailureMode', nxt)))
    for c in k.get('causes') or []:
        edge(causes[c['id']], 'CAUSES', fms.get(c['failure_mode'], ('FailureMode', c['failure_mode'])))
        for part in c['parts']:
            edge(causes[c['id']], 'INVOLVES_PART', ('Part', part))
        for d in c['disturbs']:
            edge(causes[c['id']], 'DISTURBS', ('StateVariable', d['target']), sign=d['sign'])
    for i, r in enumerate(k.get('rules') or [], 1):
        if any('variable' not in t for t in r['tests']):
            raise ValueError(f"{r['id']}: 검사 입력의 변수 이름이 확인되지 않았습니다(check_graph를 먼저 거쳐야 합니다)")
        props = dict(order=r['order'] or 100 + i, when=when_text(r['tests']), effect=r['effect'])
        if r['annotation']:
            props['annotation'] = r['annotation']
        if r['penalty'] is not None:
            props['penalty'] = r['penalty']
        n = node('Rule', r['id'], **props)
        edge(('DecisionTable', r['table']), 'HAS_RULE', n)
        for t in r['tests']:
            tp = dict(operator=t['operator'], value=t['value'])
            if t['unit']:
                tp['unit'] = t['unit']
            edge(n, 'TESTS', ('InputData', t['input']), **tp)
        for o in r['outputs']:
            edge(n, 'OUTPUTS', causes.get(o, ('Cause', o)) if o.startswith('cause:') else ('Skill', skill_of(o, skill_id)), tagged=False)
        for a in r['applies_to']:
            edge(n, 'APPLIES_TO', ('Skill', skill_of(a, skill_id)))
        if r['penalizes']:
            edge(n, 'PENALIZES', ('Measure', r['penalizes']))
        edge(n, 'DERIVED_FROM', sections[r['section']])
    return fms, causes


def own_candidate_outputs(plan, skill_id):
    """Skills this document's own candidate rules already output, and the document's own rule ids. The A075 automatic
    candidate-rule joining skips both: a document that states its candidate rule is not widened into other rules."""
    rules = (plan.get('knowledge') or {}).get('rules') or []
    skills = {skill_of(o, skill_id) for r in rules if r['table'] == 'dt:action-candidates' for o in r['outputs']}
    return skills, {r['id'] for r in rules}
