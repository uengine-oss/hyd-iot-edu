"""확정 TODO C1: 문서 한 편에서 고장 지식 · 판단 규칙 · 원자 조치까지 — 추출 제안 → 사람 검토 → 적재.

문서(매뉴얼 · 지침 · 구매 기준)는 지금까지 절 · SOP · 단계만 만들었다. 이 모듈은 같은 문서에서 아래를 더 꺼내게 한다.
  - 고장 유형(FailureMode) — 일어나는 구성 요소(OCCURS_IN), 그 고장을 나타내는 기존 증상(Symptom -INDICATES->), 이어지는 고장(LEADS_TO)
  - 원인(Cause) — 사전 확률 prior, 원인이 일으키는 고장(CAUSES), 관련 부품(INVOLVES_PART), 흔드는 상태 변수(DISTURBS {sign})
  - 증거(Evidence) — 태그 · 집계 · 구간 · 비교 · 임계값. 시계열 SQL은 서버가 정해진 틀로 만든다(문서 · 에이전트가 SQL을 쓰지 않음)
  - 규칙(Rule) — 기존 결정표(진단 · 후보 · 규정)의 새 행. 기존 판단 입력을 TESTS, 출력 · 적용 대상, 감점 지표, 근거 절(DERIVED_FROM)
  - 원자 조치 값 — SOP가 쓰는 기존 Action과 값(CONSISTS_OF {value, seq}): 설비 명령 값 · 발주 공급사 · 작업지시 SOP. ADDRESSES(원인)
  - 새 항목 제안(NEW_KINDS) — 지금 지식에 없는 그 문서 설비의 구성 요소(Component) · 증상(Symptom -OBSERVED_BY-> Sensor) · 센서
    (Sensor — 그 설비 시스템이 쓰는 태그, Component -MONITORED_BY->). 고장 유형 · 원인처럼 원문 인용이 있고, 사람이 검토 화면에서 항목마다
    넣기를 골라야(approved) 적재된다 — 추출 제안은 승인하지 못하고, 자동 검증만 거친 적재(한 번에 적재)는 새 항목을 싣지 못한다(uEngine Ontology
    Studio 의 틀 바꾸기 제안 tbox_proposals 와 같은 자리: 틀에 없는 개념은 데이터가 아니라 사람이 승인할 제안이다).
스키마 v2의 기존 클래스 · 관계만 쓴다. 새 Action · 입력 · 결정표 · 경보 패턴 · 부품 · 공급사 · 상태 변수 · 성과 지표 · 설비(Asset)는 만들지 않는다
(시드 구조에 있는 것만 가리킨다 — 설비 한 대와 그 운영 데이터는 그 현장의 시스템이 도구 서버로 준다). 가상 설비(설비 Asset 에 딸린 구성 요소)의 구조는
넓히지 않는다: 새 증상 · 새 센서 · 수집하지 않는 값을 읽는 증거는 설비에 딸린 구성 요소의 고장 유형에 잇지 않고, 그 설비의 수집 태그(hydcommon.daq_contract)는
설비에 딸리지 않은 구성 요소의 증거로 쓰지 않는다(new_item_issues).
사람이 검토 화면에서 확인 · 수정한 것만 적재된다(manual_review.validate → manual_graph.commit).
"""
from __future__ import annotations

from hydcommon.words import particle
import re
from copy import deepcopy

from hydcommon.daq_contract import TAGS as TAG_NAMES
from hydcommon.maintenance_policy import PM_PATTERN
from hydcommon.skill_scope import purchase_rule_problem

from . import kgadmin

KINDS = ('failure_modes', 'causes', 'evidence', 'rules')
NEW_KINDS = ('components', 'symptoms', 'sensors')          # 새 항목 제안 — 사람이 항목마다 넣기를 골라야 적재된다(머리말)
ALL_KINDS = KINDS + NEW_KINDS
LIMITS = {'failure_modes': 50, 'causes': 100, 'evidence': 200, 'rules': 200, 'components': 50, 'symptoms': 100, 'sensors': 100}
ID_RE = {'failure_modes': re.compile(r'^fm:[a-z0-9]+(?:-[a-z0-9]+)*$'), 'causes': re.compile(r'^cause:[a-z0-9]+(?:-[a-z0-9]+)*$'),
         'evidence': re.compile(r'^evd:[a-z0-9]+(?:-[a-z0-9]+)*$'), 'rules': re.compile(r'^rule:[a-z0-9]+(?:-[a-z0-9]+)*$'),
         'components': re.compile(r'^comp:[a-z0-9]+(?:-[a-z0-9]+)*$'), 'symptoms': re.compile(r'^sym:[a-z0-9]+(?:-[a-z0-9]+)*$'),
         'sensors': re.compile(r'^sen:[a-z0-9]+(?:-[a-z0-9]+)*$')}
LABEL = {'failure_modes': 'FailureMode', 'causes': 'Cause', 'evidence': 'Evidence', 'rules': 'Rule',
         'components': 'Component', 'symptoms': 'Symptom', 'sensors': 'Sensor'}
#: 새 항목 한 건을 학생 화면에서 부르는 이름(검토 화면 · 지식 지도와 같은 이름 — it/portal/www/enterprise.js LABEL_KO)
NEW_KIND_KO = {'components': '구성 요소', 'symptoms': '증상', 'sensors': '센서'}
REF_RE = {p: re.compile(rf'^{p}:[a-z0-9]+(?:-[a-z0-9.]+)*$') for p in ('comp', 'sym', 'sen', 'part', 'sv', 'msr', 'in', 'action', 'role', 'skill', 'fm', 'cause')}
#: 그 설비 시스템이 쓰는 센서 태그의 꼴(문서가 새 센서로 제안하는 태그 — 수집 계약의 태그는 TAGS)
SENSOR_TAG_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,63}$')
SOP_RE = kgadmin.SOP_ID_RE
TABLES = {'dt:diagnose-cause': ('SELECT',), 'dt:action-candidates': ('SELECT',), 'dt:compliance': ('EXCLUDE', 'WARN', 'PENALTY')}
OPERATORS = ('<', '<=', '>', '>=', '==', '!=')
AGGREGATES = ('avg', 'max', 'min', 'range')
EXPECTS = {'lt': '<', 'gt': '>', 'gte': '>='}
TAGS = frozenset(TAG_NAMES)          # 증거가 읽을 수 있는 태그(설비 계약 hydcommon.daq_contract 한 곳)
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
    """A rule/WO value pointing at a skill: an SOP id of this document, or an existing skill id from the catalog.
    sops=None: one segment of a long document is being checked (I3, 2026-10-23 검수) — the SOP may be extracted by another
    segment, so its existence is checked on the merged whole-document proposal (manual_segments.merge · validate_proposal)."""
    if isinstance(value, str) and SOP_RE.fullmatch(value):
        if sops is not None and value not in sops:
            # 추출 제안(AI)에도 검토본(사람)에도 같은 문장이다 — 검토에서 그 절차를 뺐거나 번호를 바꿨으면 이 규칙도 함께 빼거나 고쳐야 한다
            raise ValueError(f'{name}: 절차 {value}{particle(value, "이")} 이 문서의 절차 목록에 없습니다 — 그 절차를 남기거나 이 규칙을 함께 빼세요'
                             '(다른 문서의 조치 방법은 skill:… id로 가리킵니다)')
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
    affects is validated by kgadmin.validate_affects (one rule for the admin skill edit and the review)."""
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
            raise ValueError(f'{sop}: 구매 총비용 비교 정책은 실행하는 구매 절차(scope=purchase · executable=true)에만 붙입니다')
        from hydcommon.purchase_comparison import policy
        out['purchase_comparison_policy']=policy(link['purchase_comparison_policy'])
    if link.get('maintenance_policy') is not None:
        if link.get('scope') == 'purchase' or link.get('kind') == 'reference':
            raise ValueError(f'{sop}: 정기 정비 시행 정책은 구매 절차 · 비실행 참고 절차에 붙이지 않습니다')
        from hydcommon.maintenance_policy import policy
        out['maintenance_policy']=policy(link['maintenance_policy'])
    if link.get('scope') not in (None, 'fault', 'purchase'):
        raise ValueError(f'{sop}: 조치 방법의 업무 범위는 고장 조치 또는 구매(purchase)입니다')
    if link.get('scope') != 'purchase' and (link.get('executable') is not None or link.get('parts') is not None or link.get('supplier_policy') is not None):
        raise ValueError(f'{sop}: 실행 여부 · 구매 부품 · 공급사 정책은 구매(purchase) 절차에서만 씁니다')
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
            raise ValueError(f'{sop}: 조치 방법 종류는 설비 명령(control) 또는 정비 요청(work_order)입니다')
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


def validate(knowledge, *, sections, sops, anchor, reviewed=False):
    """Shape · enum · range · internal reference checks of the knowledge part of a proposal or a reviewed body.
    `anchor(value)` validates (and may complete) one citation. Graph existence is checked at commit (check_graph).
    reviewed=False: an extraction proposal (or its preview) — a new item (NEW_KINDS) carries no approval. reviewed=True: the body a
    person reviewed — every new item in it must carry approved=true (the reviewer chose 「넣기」). The result always has the four
    knowledge kinds and a new kind only when it has items (a document with no new items keeps the plan shape it always had)."""
    if knowledge is None:
        return None
    if not isinstance(knowledge, dict) or set(knowledge) - set(ALL_KINDS):
        raise ValueError(f'knowledge는 {list(ALL_KINDS)} 목록을 가진 객체입니다')
    out, seen, errors = {}, set(), []
    for kind in ALL_KINDS:
        items = knowledge.get(kind) or []
        if not isinstance(items, list) or len(items) > LIMITS[kind]:
            errors.append(f'knowledge.{kind}: 최대 {LIMITS[kind]}개의 목록이어야 합니다')
            items = []
        if kind in NEW_KINDS and not items:
            continue
        out[kind] = []
        for item in items:
            try:
                if not isinstance(item, dict):
                    raise ValueError(f'knowledge.{kind}: 항목은 객체여야 합니다')
                nid = item.get('id')
                if not isinstance(nid, str) or not ID_RE[kind].fullmatch(nid) or nid in seen:
                    raise ValueError(f'knowledge.{kind}: id 형식 또는 중복을 확인하세요 ({nid!r}, 예: {ID_RE[kind].pattern})')
                seen.add(nid)
                if kind in NEW_KINDS:
                    _approval(kind, nid, item, reviewed)
                section = item.get('section')
                if section not in sections:
                    raise ValueError(f'{nid}: section {section!r}이 sections의 ref에 없습니다')
                base = dict(id=nid, section=section, anchor=anchor(item.get('anchor')))
                out[kind].append(_ITEM[kind](item, base, sops))
            except ValueError as exc:
                errors.append(str(exc))
    tags = [s['tag'] for s in out.get('sensors') or []]
    for tag in sorted({t for t in tags if tags.count(t) > 1}):
        errors.append(f"knowledge.sensors: 태그 {tag}{particle(tag, '을')} 쓰는 새 센서가 둘 이상입니다 — 센서 하나가 태그 하나입니다")
    # 원인의 고장 유형 · 증거의 원인이 실제로 있는지는 꼴(_ref)이 아니라 그래프가 본다 — 적재 전 검사(REFERENCE_NOT_FOUND)와 적재(manual_graph._validate_targets).
    # 증거 · 센서 · 새 증상이 지금 지식의 설비 구조와 맞는지도 그래프가 본다(new_item_issues)
    if errors:
        raise ValueError(' / '.join(dict.fromkeys(errors)))
    return out


def _approval(kind, nid, item, reviewed):
    """새 항목의 넣기 표시(approved). 추출 제안(AI)은 승인하지 못하고, 사람이 검토한 본문은 넣기를 고른 항목만 담는다."""
    approved = item.get('approved')
    what = f"새 {NEW_KIND_KO[kind]} 「{item.get('name') or nid}」"
    if reviewed and approved is not True:
        raise ValueError(f"{nid}: {what}{particle(what, '은')} 사람이 검토 화면에서 「넣기」를 골라야 적재됩니다 — 넣지 않으려면 「제외」를 고르세요")
    if not reviewed and approved is not None:
        raise ValueError(f"{nid}: 추출 제안은 {what}{particle(what, '을')} 승인하지 않습니다(approved 칸을 쓰지 마세요) — 넣을지는 사람이 검토 화면에서 고릅니다")


def source_value_warnings(proposal):
    """Literal numeric discrepancies need review; units/derived values cannot be proven by substring matching."""
    from decimal import Decimal
    warnings = []
    def check(owner, field, value, quotes):
        if type(value) not in (int, float):
            return
        found = {Decimal(n.replace(',', '')) for n in re.findall(r'(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?![\d.])', '\n'.join(quotes))}
        if Decimal(str(value)) not in found:
            warnings.append(f'{owner} · {field}={value}: 해당 인용에서 같은 수치를 찾지 못했습니다. 원문의 값·단위 환산·계산 근거를 확인하세요')
    def quote(anchor):
        return (anchor or {}).get('quote') or ''
    overrides = proposal.get('links') or {}
    for p in proposal.get('procedures') or []:
        link = overrides.get(p['id'], p.get('link', p)) or {}
        quotes = [quote(p.get('anchor')), *[quote(s.get('anchor')) for s in p.get('steps') or []]]
        for a in link.get('actions') or []:
            check(p['id'], a.get('action', 'action') + '.value', a.get('value'), quotes)
        policy = link.get('maintenance_policy') or {}
        for key in ('interval_h', 'tolerance_pct'):
            check(p['id'], 'maintenance_policy.' + key, policy.get(key), [quote(policy.get('anchor'))])
    knowledge = proposal.get('knowledge') or {}
    for evidence in knowledge.get('evidence') or []:
        check(evidence['id'], 'threshold', evidence.get('threshold'), [quote(evidence.get('anchor'))])
    for rule in knowledge.get('rules') or []:
        for test in rule.get('tests') or []:
            check(rule['id'], (test.get('input') or test.get('variable') or 'test') + '.value', test.get('value'), [quote(rule.get('anchor'))])
    return list(dict.fromkeys(warnings))


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
    """tag 가 수집 계약의 태그면 판단 엔진이 평가할 시계열 SQL 을 서버가 만든다. 그 밖의 태그는 센서(이 문서의 새 센서나 지금 지식의 센서)의 태그여야
    하고(new_item_issues 가 그래프로 본다) SQL 이 없다 — 이 시스템이 수집하지 않는 값이라 평가하지 않는다는 문장(unevaluated_note)이 그 자리에 선다."""
    nid = base['id']
    tag, agg, expect = item.get('tag'), item.get('aggregate'), item.get('expect')
    if tag not in TAGS and not (isinstance(tag, str) and SENSOR_TAG_RE.fullmatch(tag)):
        raise ValueError(f'{nid}: tag는 수집 계약의 태그 {sorted(TAGS)} 또는 센서의 태그(이 문서가 새로 제안하는 센서 · 지금 지식의 센서)여야 합니다 ({tag!r})')
    if agg not in AGGREGATES:
        raise ValueError(f'{nid}: aggregate는 {AGGREGATES} 중 하나')
    if expect not in EXPECTS:
        raise ValueError(f'{nid}: expect는 {tuple(EXPECTS)} 중 하나')
    window = item.get('window_seconds')
    if type(window) is not int or not 1 <= window <= 3600:
        raise ValueError(f'{nid}: window_seconds는 1~3600 정수')
    threshold = _number(item.get('threshold'), f'{nid} 임계치')
    out = dict(base, cause=_ref(item.get('cause'), 'cause', f'{nid} 원인'), name=_text(item.get('name'), f'{nid} 이름', 120),
               tag=tag, aggregate=agg, window_seconds=window, expect=expect, threshold=threshold,
               weight=_number(item.get('weight'), f'{nid} 가중치 weight', 0.0, 1.0), rule=evidence_rule(tag, agg, window, expect, threshold))
    if tag in TAGS:
        out['sql'] = evidence_sql(tag, agg, window)
    return out


def unevaluated_note(tag, sensor_name=None):
    """수집하지 않는 값을 읽는 증거의 한 문장 — 지식(Evidence.note)과 적재 전 검사의 참고(notices)가 이 한 곳의 글을 쓴다."""
    what = f"「{sensor_name}」(태그 {tag})" if sensor_name else f"태그 {tag}"
    return (f"이 증거가 읽는 {what}{particle(what, '은')} 이 시스템이 수집하는 설비 값이 아니어서 판단 엔진이 이 증거를 평가하지 않습니다 — "
            "이 설비를 맡은 에이전트가 그 설비 시스템을 연결한 도구 서버로 값을 읽어 확인합니다")


def _aliases(item, nid):
    aliases = item.get('aliases') or []
    if not isinstance(aliases, list) or len(aliases) > 10:
        raise ValueError(f'{nid}: aliases는 최대 10개의 문자열 목록입니다')
    return [_text(a, f'{nid} 별칭', 60) for a in aliases]


def _component(item, base, sops):
    nid = base['id']
    return dict(base, name=_text(item.get('name'), f'{nid} 이름', 120), aliases=_aliases(item, nid))


def _symptom(item, base, sops):
    nid = base['id']
    return dict(base, name=_text(item.get('name'), f'{nid} 이름', 120), aliases=_aliases(item, nid),
                sensors=_refs(item.get('sensors'), 'sen', f'{nid} 관측 센서', limit=10))


def _sensor(item, base, sops):
    nid, tag = base['id'], item.get('tag')
    if not isinstance(tag, str) or not SENSOR_TAG_RE.fullmatch(tag):
        raise ValueError(f'{nid}: tag는 그 설비 시스템이 쓰는 센서 태그입니다(영문자로 시작하는 영문자 · 숫자 · _ . - 64자 이내 — {tag!r})')
    if tag in TAGS:
        raise ValueError(f"{nid}: 태그 {tag}{particle(tag, '은')} 이 시스템이 수집하는 유압 설비 값의 이름이라 새 센서의 태그로 쓸 수 없습니다 — "
                         "이 문서 설비의 값이면 그 설비 시스템에서 이 이름과 겹치지 않는 태그를 적으세요")
    return dict(base, name=_text(item.get('name'), f'{nid} 이름', 120), tag=tag,
                unit=_text(item.get('unit'), f'{nid} 단위', 20, required=False) or None,
                component=_ref(item.get('component'), 'comp', f'{nid} 구성 요소'))


def _rule(item, base, sops):
    nid = base['id']
    table, effect = item.get('table'), item.get('effect')
    if table not in TABLES:
        raise ValueError(f'{nid}: table은 {list(TABLES)} 중 하나 (순위 정책 dt:rank-actions는 회사 규정이라 문서가 바꾸지 않습니다)')
    if effect not in TABLES[table]:
        raise ValueError(f'{nid}: {table}의 effect는 {TABLES[table]} 중 하나')
    tests = item.get('tests')
    if not isinstance(tests, list) or not 1 <= len(tests) <= 8:
        raise ValueError(f'{nid}: TESTS(임계치 검사)가 1~8개 필요합니다')
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
            outputs = [_skill_ref(o, sops, f'규칙 {nid}의 결과') for o in outputs]
    else:
        if outputs:
            raise ValueError(f'{nid}: {effect} 규칙은 applies_to(대상 SOP, 비우면 모든 후보)를 씁니다')
        applies = [_skill_ref(o, sops, f'규칙 {nid}의 적용 대상') for o in applies]
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


_ITEM = {'failure_modes': _fm, 'causes': _cause, 'evidence': _evidence, 'rules': _rule,
         'components': _component, 'symptoms': _symptom, 'sensors': _sensor}


def anchors(knowledge):
    for kind in ALL_KINDS:
        for item in (knowledge or {}).get(kind) or []:
            if isinstance(item, dict) and isinstance(item.get('anchor'), dict):
                yield item['anchor']


def skill_of(ref, skill_id):
    return skill_id(ref) if SOP_RE.fullmatch(ref) else ref


# ------------------------------------------------------------------ graph side (read-only; commit-time checks)

CATALOG_Q = {
    # assets: 그 구성 요소가 딸린 설비(Asset -HAS_COMPONENT->)의 코드 — 문서는 그 관계를 만들지 않으므로 빈 목록이면 문서가 넣은 구성 요소다(new_item_issues)
    # (목록은 정렬해 읽는다 — 카탈로그는 제공 문서 추출의 캐시 열쇠에 들어가 같은 지식이면 같은 글이어야 한다)
    'components': 'MATCH (n:Component) RETURN n.id AS id, n.name AS name, n.aliases AS aliases, '
                  'COLLECT { MATCH (a:Asset)-[:HAS_COMPONENT]->(n) RETURN a.code ORDER BY a.code } AS assets ORDER BY id',
    'sensors': 'MATCH (n:Sensor) RETURN n.id AS id, n.name AS name, n.tag AS tag, n.unit AS unit, '
               'COLLECT { MATCH (c:Component)-[:MONITORED_BY]->(n) RETURN c.id ORDER BY c.id } AS components ORDER BY id',
    # 2026-10-25 final4: 정기 정비 정책의 model_assets(원문 '1~3호기')를 옮길 설비 목록이 없어 PM-02 추출의 정책이 모두 빠졌다
    'assets': 'MATCH (n:Asset) RETURN n.id AS id, n.code AS code, n.name AS name ORDER BY id',
    'symptoms': 'MATCH (n:Symptom) OPTIONAL MATCH (p:AnomalyPattern)-[:DETECTS]->(n) '
                'RETURN n.id AS id, n.name AS name, n.aliases AS aliases, [c IN collect(DISTINCT p.code) WHERE c IS NOT NULL] AS patterns ORDER BY id',
    'patterns': 'MATCH (n:AnomalyPattern) RETURN n.id AS id, n.code AS code, n.name AS name ORDER BY id',
    'parts': 'MATCH (n:Part) OPTIONAL MATCH (n)-[x:SUPPLIED_BY]->(s:Supplier) OPTIONAL MATCH (c:Component)-[:USES_PART]->(n) '
             'RETURN n.id AS id, n.name AS name, n.partNo AS partNo, collect(DISTINCT c.id) AS usedIn, '
             '[r IN collect(DISTINCT {supplier:s.id, name:s.name, avl:s.avl, oem:s.oem, price:x.price, failRate:x.failRate, leadDays:x.leadDays}) '
             'WHERE r.supplier IS NOT NULL] AS suppliers ORDER BY id',
    'suppliers': 'MATCH (n:Supplier) RETURN n.id AS id, n.name AS name, n.avl AS avl, n.oem AS oem ORDER BY id',
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
    the commit-time ownership check stays the hard rule. A reviewer drops such an item and refers to the existing id.
    owner_name = 그 항목을 가진 문서의 지금 판을 적재한 파일 이름(검사 문장이 문서를 그 이름으로 부른다 — 문서의 그래프 열쇠는 학생이 읽을 이름이 아니다)."""
    import json
    ids = [(LABEL[k], i['id']) for k in ALL_KINDS for i in (knowledge or {}).get(k) or [] if isinstance(i, dict) and i.get('id')]
    if not ids:
        return []
    def read(tx):
        out = []
        for label, nid in ids:
            row = tx.run(f'MATCH (n:{label} {{id:$id}}) RETURN n.id AS id', id=nid).single()
            if not row:
                continue
            doc = tx.run('MATCH (d:ManualIngestionDocument) WHERE d.snapshot CONTAINS $needle '
                         'OPTIONAL MATCH (b:ManualIngestionBatch {id:d.head}) RETURN d.id AS id, b.receipt AS receipt LIMIT 1',
                         needle='"id":"' + nid + '"').single()
            if doc and doc['id'] == document:
                continue                      # the same document's earlier batch — a re-ingest replaces it
            try:
                name = json.loads(doc['receipt']).get('filename') if doc and doc['receipt'] else None
            except (TypeError, ValueError):
                name = None
            out.append(dict(id=nid, label=label, owner=doc['id'] if doc else 'seed', kind='other_document' if doc else 'seed_or_admin',
                            **({'owner_name': name} if name else {})))
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
                    elif p['supplier_policy'] == 'oem' and not any(s.get('oem') is True for s in available):
                        # 순정 여부는 공급사 노드의 oem 속성 하나로 본다(표시 이름 글자가 아니다 — 이름을 바꿔도 판정이 같다)
                        issue('PURCHASE_OEM_SOURCE_MISSING', p['id'], 'link.supplier_policy',
                              f"{p['id']}: {part}{particle(part, '을')} 공급하는 순정(제조사) 공급사가 지식에 없습니다(공급사의 순정 표시 oem)")
                elif p.get('executable') and not p.get('supplier_policy'):
                    supplier = (p.get('actions') or [{}])[0].get('value')
                    if not any(s.get('supplier') == supplier for s in parts[part].get('suppliers') or []):
                        issue('PURCHASE_SUPPLIER_PART_MISMATCH', p['id'], 'link.actions', f"{p['id']}: {supplier} 공급사와 {part}의 실제 SUPPLIED_BY 관계가 없습니다")
            if p.get('executable') and not any(r['id'] == p.get('approver') for r in catalog['roles']):
                issue('PURCHASE_ROLE_NOT_FOUND', p['id'], 'link.approver', f"{p['id']}: 명시한 구매 승인 역할이 역할 목록에 없습니다 — 있는 역할을 고르거나 "
                                                                        "「AI 에이전트」 화면의 담당 배정에서 [역할 만들기]로 먼저 만드세요")
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
                issue('SOP_NOT_FOUND', p['id'], 'link.actions', f"{where}: 정비 요청 값은 SOP 번호여야 합니다({v!r})")
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
                      f"{r['id']}: 규칙이 견주는 입력 {t['input']}은 판단 「{table.get('name') or table['decision']}」이 읽는 입력이 아니라서 "
                      "이 규칙을 적재할 수 없습니다. 판단이 읽는 입력은 기본 제공 지식이 정해 둔 것뿐입니다 — 「지식 › 문서 등록 › 업무 DB 표 정의」로 만든 "
                      "입력은 판단 규칙에 쓸 수 없습니다. 이 판단이 읽는 입력 가운데 하나로 바꾸세요: "
                      + ', '.join(f"{i}({inputs[i].get('name') or inputs[i].get('variable')})" for i in sorted(inputs)))
            else:
                t['variable'] = inputs[t['input']]['variable']
        if r.get('effect') == 'SELECT' and r.get('table') == 'dt:action-candidates':
            own = {ref: p for p in plan['procedures'] for ref in (p['id'], kgadmin.skill_id(p['id']))}
            stored = {row['id']: row for row in catalog['skills'] if row.get('id')}
            outputs = [own.get(ref) or stored.get(ref) for ref in r.get('outputs') or []]
            for output in outputs:
                if output and (output.get('kind') == 'reference' or output.get('executable') is False):
                    what = f"「{output.get('name')}」({output.get('sopId') or output.get('id')})" if output.get('name') else str(output.get('sopId') or output.get('id'))
                    issue('RULE_OUTPUT_NOT_EXECUTABLE', r['id'], 'knowledge.rules.outputs',
                          f"{r['id']}: 이 규칙이 조치 후보로 내는 절차 {what}{particle(what, '은')} 원문만 보관하는 참고 절차라 후보가 될 수 없습니다 — "
                          "이 규칙을 함께 빼거나 그 절차의 종류를 되돌리세요")
                if output and output.get('id') in own and any(t.get('variable') == 'pattern' and t.get('value') == PM_PATTERN for t in r['tests']):
                    effect_codes = [actions.get(a['action'],{}).get('code') for a in output.get('actions') or []]
                    if sum(code in ('WO_CREATE','WO_RESCHEDULE') for code in effect_codes) != 1:
                        issue('PM_ORDER_EFFECT_REQUIRED',output['id'],'link.actions',f"{output['id']}: PM 실행 후보에는 원문 기반 오더 발행 또는 기존 오더 일정 변경 Action 하나가 필요합니다")
            purchase = [p for p in outputs if p and p.get('scope') == 'purchase']
            if purchase:
                if any(p.get('executable') is not True for p in purchase):
                    issue('RULE_OUTPUT_NOT_EXECUTABLE', r['id'], 'knowledge.rules.outputs', f"{r['id']}: 참고 보관 구매 절차는 실행 후보 Rule의 출력이 될 수 없습니다")
                if any(p and p.get('scope') != 'purchase' for p in outputs):
                    issue('RULE_OUTPUT_SCOPE_MIXED', r['id'], 'knowledge.rules.outputs', f"{r['id']}: 구매 후보와 고장 조치 후보를 같은 Rule에 섞지 않습니다")
                problem = purchase_rule_problem(r['tests'])       # 구매 판단이 도는 경보 조건 — 그래프 검사기와 같은 한 벌(hydcommon.skill_scope)
                if problem:
                    issue('PURCHASE_RULE_PATTERN_REQUIRED', r['id'], 'knowledge.rules.tests', f"{r['id']}: {problem}")
    return plan, issues


def _plain(text):
    return re.sub(r'\s+', '', str(text or '')).lower()


def component_assets(knowledge, catalog):
    """구성 요소 id → 그것이 딸린 설비(Asset -HAS_COMPONENT->)의 코드 목록. 이 문서의 새 구성 요소와 문서가 넣은 구성 요소는 [](문서는 그 관계를 만들지
    않는다). 카탈로그의 구성 요소에 설비 목록(assets)이 있어야 한다 — 없는 옛 카탈로그는 부르는 쪽(new_item_issues)이 먼저 가린다."""
    out = {c['id']: list(c['assets'] or []) for c in catalog['components']}
    out.update({c['id']: [] for c in (knowledge or {}).get('components') or []})
    return out


def _failure_mode_plants(knowledge, catalog):
    """고장 유형 id → 그 고장이 생기는 구성 요소가 딸린 설비 코드 목록([] = 설비에 딸리지 않은 구성 요소, None = 구성 요소를 모름)."""
    assets = component_assets(knowledge, catalog)
    rows = {r['id']: r for r in catalog['failure_modes']}
    rows.update({r['id']: r for r in (knowledge or {}).get('failure_modes') or []})      # 이 문서의 판이 지금 지식의 같은 id 를 대신한다(개정)
    return {fm: assets.get(r.get('component')) for fm, r in rows.items()}


def outside_plant(knowledge, catalog):
    """설비에 딸리지 않은 구성 요소에서 생기는 고장 유형 id(이 문서의 것 · 지금 지식의 것) — 판단 엔진(경보 → 증상 → 고장 유형)이 닿지 않는 곳이다."""
    return {fm for fm, codes in _failure_mode_plants(knowledge, catalog).items() if codes == []}


def performers(plan, catalog):
    """절차마다 그 절차를 수행하는 이 시스템의 업무 시스템 {절차 번호: System id 또는 None} — 적재(manual_graph.desired)가 이 한 판정으로 System -HAS_SKILL-> Skill 을
    긋는다. 구매 절차는 ERP(이 시스템 업무 데이터의 부품 · 공급사를 산다), 이 시스템이 운영하는 설비(설비에 딸린 구성 요소)의 고장 조치는 설비 명령이면 SCADA ·
    정비 요청이면 CMMS. 그 밖의 설비(문서가 새 항목으로 넣은 다른 설비 — 학생 설비)의 절차는 None 이다: 그 실행은 그 설비 시스템을 도구 서버로 연결한 흐름의
    「승인 뒤 MCP 호출」이 하므로, 이 시스템의 CMMS · SCADA 가 수행한다고 지식 지도에 적지 않는다. 참고 절차는 수행하지 않아 싣지 않는다."""
    plant = {fm for fm, codes in _failure_mode_plants(plan.get('knowledge'), catalog).items() if codes}
    out = {}
    for p in plan['procedures']:
        if p.get('kind') == 'reference':
            continue
        if p.get('scope') == 'purchase':
            out[p['id']] = 'sys:erp'
        elif p.get('failureMode') in plant:
            out[p['id']] = 'sys:scada' if p['kind'] == 'control' else 'sys:cmms'
        else:
            out[p['id']] = None
    return out


def new_item_issues(knowledge, catalog, procedures):
    """새 항목(구성 요소 · 증상 · 센서)과 그것을 쓰는 증거 · 고장 유형 · 원인 · 절차가 지금 지식의 설비 구조와 맞는가 → (issues, notices).
    적재 전 검사(manual_preflight.validate)와 적재(check_graph)가 같은 판정을 쓴다. 가상 설비의 구조는 넓히지 않는다(머리말) — 설비에 딸린
    구성 요소(카탈로그 components 의 assets 가 있는 것)와 수집 태그(TAGS)의 센서가 그 설비의 구조다. procedures = 연결을 풀어 둔 절차 목록(검토 계획의 꼴).
      ① 새 센서의 태그는 다른 센서가 쓰지 않는다. 새 센서는 설비에 딸린 구성 요소에 붙지 않는다
      ② 새 증상은 설비에 딸린 구성 요소의 고장 유형을 가리키지 않고, 그 관측 센서는 수집 태그의 센서가 아니다. 설비에 딸리지 않은 구성 요소의
         고장 유형은 경보 패턴이 감지하는 증상을 쓰지 않는다(쓰면 그 설비의 경보가 이 고장 유형까지 닿는다)
      ③ 수집하지 않는 태그를 읽는 증거는 이 문서의 새 센서나 지금 지식의 센서를 가리키고, 그 원인의 고장 유형은 설비에 딸리지 않은 구성 요소에서
         생긴다. 수집 태그를 읽는 증거의 고장 유형은 설비에 딸린 구성 요소에서 생긴다(다른 설비의 증거가 이 시스템의 수집 값을 읽지 않게)
      ④ 설비에 딸리지 않은 구성 요소의 고장(다른 설비)의 원인 · 고장 조치는 이 시스템 설비의 부품 · 상태 변수(INVOLVES_PART · DISTURBS · AFFECTS sv:)와
         이 시스템의 원자 조치(CONSISTS_OF — 카탈로그의 원자 조치는 모두 이 시스템의 구동기 · 업무 시스템을 TARGETS 로 가리킨다)를 가리키지 않는다. 성과
         지표(msr:)는 회사의 지표라 가리킬 수 있다. 구매 절차는 고장 유형이 없어 해당하지 않는다(이 시스템 업무 데이터의 부품을 산다)
    notices(고칠 곳이 아니라 알고 넘어갈 것): 판단 엔진이 평가하지 않는 증거(unevaluated_note), 지금 지식의 같은 종류 항목과 이름이 같은 새 항목.
    구성 요소의 설비 · 센서 목록이 없는 카탈로그(그 칸이 생기기 전에 추출 작업에 고정한 것)로는 판정하지 않고 CATALOG_OUTDATED 한 건으로 말한다."""
    k = knowledge or {}
    issues, notices = [], []

    def issue(code, owner, field, message):
        issues.append(dict(code=code, sop=owner, field=field, message=message))
    if 'sensors' not in catalog or any('assets' not in c for c in catalog['components']):
        issue('CATALOG_OUTDATED', None, 'catalog', '이 검사에 쓴 지금 지식 목록이 구성 요소의 설비 · 센서를 싣지 않은 옛 목록이라 새 항목과 증거의 설비 구조를 '
              '판정하지 않았습니다 — 지금 지식으로 다시 검사하세요(AI 추출 결과를 다시 열면 다시 검사합니다)')
        return issues, notices
    own = {kind: {i['id']: i for i in k.get(kind) or []} for kind in ('components', 'symptoms', 'sensors', 'failure_modes', 'causes')}
    components = {c['id']: c for c in catalog['components']}
    sensors = {s['id']: s for s in catalog['sensors']}
    fms = {r['id']: r for r in catalog['failure_modes']}
    causes = {r['id']: r for r in catalog['causes']}
    plant = component_assets(k, catalog).get       # 구성 요소 → 그것이 딸린 설비 코드(문서가 넣은 것은 [], 모르는 것은 None — 그 참조는 적재 전 검사가 짚는다)

    def named(row, nid):
        return f"「{(row or {}).get('name') or nid}」"
    comp_name = lambda cid: named(own['components'].get(cid) or components.get(cid), cid)            # noqa: E731
    fm_name = lambda fm: named(own['failure_modes'].get(fm) or fms.get(fm), fm)                    # noqa: E731
    fm_component = lambda fm: (own['failure_modes'].get(fm) or fms.get(fm) or {}).get('component')     # noqa: E731
    cause_fms = lambda c: [own['causes'][c]['failure_mode']] if c in own['causes'] else list((causes.get(c) or {}).get('failureModes') or [])   # noqa: E731
    for sid, s in own['sensors'].items():
        taken = next((r for r in sensors.values() if r.get('tag') == s['tag'] and r['id'] != sid), None)
        if taken:
            there = named(taken, taken['id'])
            issue('SENSOR_TAG_TAKEN', sid, 'tag', f"{sid}: 새 센서 「{s['name']}」의 태그 {s['tag']}{particle(s['tag'], '은')} 지금 지식의 센서 {there}{particle(there, '이')} "
                  "이미 씁니다 — 같은 값이면 새 센서를 제외하고 그 센서를 쓰게 AI 추출을 다시 하세요")
        codes = plant(s['component'])
        if codes:
            issue('NEW_ITEM_ON_PLANT', sid, 'component', f"{sid}: 새 센서 「{s['name']}」{particle(s['name'], '은')} 설비 {' · '.join(codes)}의 구성 요소 {comp_name(s['component'])}에 "
                  "붙어 있습니다 — 그 설비의 센서는 지금 지식에 있는 것만 씁니다. 다른 설비의 센서면 그 설비의 구성 요소에 붙이세요")
    for sym, s in own['symptoms'].items():
        for sen in s['sensors']:
            row = own['sensors'].get(sen) or sensors.get(sen)
            if row and row.get('tag') in TAGS:
                there = named(row, sen)
                issue('NEW_ITEM_ON_PLANT', sym, 'sensors', f"{sym}: 새 증상 「{s['name']}」의 관측 센서 {there}{particle(there, '은')} 이 시스템이 수집하는 설비 값의 "
                      "센서입니다 — 그 설비의 증상은 지금 지식에 있는 것만 씁니다")
    patterned = {r['id']: r for r in catalog['symptoms'] if r.get('patterns')}
    for f in own['failure_modes'].values():
        codes = plant(f['component'])
        for sym in f['symptoms'] if codes is not None else ():
            if codes and sym in own['symptoms']:
                new = own['symptoms'][sym]['name']
                issue('NEW_ITEM_ON_PLANT', f['id'], 'symptoms', f"{f['id']}: 고장 유형 「{f['name']}」{particle(f['name'], '은')} 설비 {' · '.join(codes)}의 구성 요소 "
                      f"{comp_name(f['component'])}에서 생기는데 새 증상 「{new}」{particle(new, '을')} 가리킵니다 — 그 설비의 증상은 지금 지식에 있는 것만 씁니다")
            if not codes and sym in patterned:
                name = named(patterned[sym], sym)
                issue('PLANT_SYMPTOM_ON_OTHER', f['id'], 'symptoms', f"{f['id']}: 고장 유형 「{f['name']}」{particle(f['name'], '은')} 설비에 딸리지 않은 구성 요소 "
                      f"{comp_name(f['component'])}에서 생기는데, 증상 {name}{particle(name, '은')} 이 시스템의 경보가 감지하는 설비 증상이라 그 경보가 이 고장 유형까지 "
                      "닿습니다 — 이 문서 설비의 증상을 새 항목으로 쓰세요")
    known_tags = {r['tag'] for r in sensors.values() if r.get('tag')} | {s['tag'] for s in own['sensors'].values()}
    own_names = {s['tag']: s['name'] for s in own['sensors'].values()}       # 그래프의 증거 문장(desired)과 같은 이름 — 이 문서의 새 센서만
    for e in k.get('evidence') or []:
        collected = e['tag'] in TAGS
        if not collected and e['tag'] not in known_tags:
            issue('REFERENCE_NOT_FOUND', e['id'], 'tag', f"{e['id']}: 증거 「{e['name']}」{particle(e['name'], '이')} 읽는 태그 {e['tag']}{particle(e['tag'], '은')} 이 시스템의 "
                  "수집 값도, 이 문서의 새 센서도, 지금 지식의 센서도 아닙니다 — 그 값을 재는 센서를 새 항목으로 넣거나 이 증거를 적재에서 제외하세요")
            continue
        for fm in cause_fms(e['cause']):
            cid = fm_component(fm)
            codes = plant(cid) if cid else None
            if codes is None:
                continue
            if not collected and codes:
                issue('NEW_ITEM_ON_PLANT', e['id'], 'tag', f"{e['id']}: 증거 「{e['name']}」{particle(e['name'], '은')} 이 시스템이 수집하지 않는 값({e['tag']})을 읽는데, "
                      f"그 원인의 고장 유형 {fm_name(fm)}{particle(fm_name(fm), '은')} 설비 {' · '.join(codes)}의 구성 요소 {comp_name(cid)}에서 생깁니다 — "
                      "그 설비의 증거는 이 시스템의 수집 값을 읽습니다")
            if collected and not codes:
                issue('PLANT_TAG_ON_OTHER', e['id'], 'tag', f"{e['id']}: 증거 「{e['name']}」{particle(e['name'], '은')} 이 시스템이 수집하는 유압 설비 값 "
                      f"{e['tag']}{particle(e['tag'], '을')} 읽는데, 그 원인의 고장 유형 {fm_name(fm)}{particle(fm_name(fm), '은')} 설비에 딸리지 않은 구성 요소 "
                      f"{comp_name(cid)}에서 생깁니다 — 이 문서 설비의 값이면 그 값을 재는 센서를 새 항목으로 넣고 그 태그를 쓰세요")
        if not collected:
            notices.append(dict(code='EVIDENCE_NOT_EVALUATED', sop=e['id'], field='tag',
                                message=f"증거 「{e['name']}」: " + unevaluated_note(e['tag'], own_names.get(e['tag']))))
    outside = outside_plant(k, catalog)
    lookup = {key: {r['id']: r for r in catalog.get(key) or []} for key in ('parts', 'state_variables', 'actions')}

    def plant_link(owner, field, who, fm, what, key, nid, fix):
        target = f"{what} {named(lookup[key].get(nid), nid)}"
        issue('PLANT_LINK_ON_OTHER', owner, field, f"{owner}: {who}{particle(who, '은')} 설비에 딸리지 않은 구성 요소 {comp_name(fm_component(fm))}에서 생기는 "
              f"고장 {fm_name(fm)}{particle(fm_name(fm), '을')} 다루는데, 이 시스템이 운영하는 설비의 {target}{particle(target, '을')} 가리킵니다 — 다른 설비의 "
              f"지식은 이 시스템 설비의 부품 · 상태 변수 · 원자 조치에 잇지 않습니다(그 설비의 실행은 그 설비 시스템을 도구 서버로 연결한 흐름이 합니다). {fix}")
    for c in own['causes'].values():
        if c['failure_mode'] in outside:
            who, fix = f"원인 「{c['name']}」", '이 원인을 적재에서 제외하거나 AI 추출을 다시 하세요'
            for part in c['parts']:
                plant_link(c['id'], 'parts', who, c['failure_mode'], '부품', 'parts', part, fix)
            for d in c['disturbs']:
                plant_link(c['id'], 'disturbs', who, c['failure_mode'], '상태 변수', 'state_variables', d['target'], fix)
    for p in procedures:
        if p.get('kind') == 'reference' or p.get('scope') == 'purchase' or p.get('failureMode') not in outside:
            continue
        who = f"절차 「{p.get('name') or p['id']}」"
        for a in p.get('actions') or []:
            plant_link(p['id'], 'link.actions', who, p['failureMode'], '원자 조치', 'actions', a['action'], 'AI 추출을 다시 하세요')
        for a in p.get('affects') or []:
            if str(a.get('target')).startswith('sv:'):
                plant_link(p['id'], 'link.affects', who, p['failureMode'], '상태 변수', 'state_variables', a['target'], '이 절차의 영향 칸에서 그 상태 변수를 지우세요')
    existing = {'components': catalog['components'], 'symptoms': catalog['symptoms'], 'sensors': catalog['sensors']}
    for kind in NEW_KINDS:
        for nid, item in own[kind].items():
            words = {_plain(w) for w in [item['name'], *(item.get('aliases') or [])]} - {''}
            same = next((r for r in existing[kind] if r['id'] != nid
                         and words & ({_plain(w) for w in [r.get('name'), *(r.get('aliases') or [])]} - {''})), None)
            if same:
                what, there = NEW_KIND_KO[kind], named(same, same['id'])
                notices.append(dict(code='NEW_ITEM_SAME_NAME', sop=nid, field=kind, message=(
                    f"새 {what} 「{item['name']}」{particle(item['name'], '과')} 이름이 같은 {what} {there}{particle(there, '이')} 지금 지식에 있습니다 — "
                    "같은 것이면 이 새 항목을 제외하고 AI 추출을 다시 해 있는 항목을 가리키게 하세요. 다른 설비의 것이면 그대로 넣어도 됩니다")))
    return issues, notices


def check_graph(session, plan, skill_id):
    """Commit rechecks the live catalog before writes and keeps its legacy plan contract."""
    def read(tx):
        out = dict(actions=tx.run(CATALOG_Q['actions']).data(),
                    suppliers=tx.run('MATCH (s:Supplier) RETURN s.id AS id').data(),
                    skills=tx.run(CATALOG_Q['skills']).data(),
                    decision_tables=tx.run(CATALOG_Q['decision_tables']).data())
        if any(p.get('scope') == 'purchase' for p in plan['procedures']):
            out.update({key: tx.run(CATALOG_Q[key]).data() for key in ('systems', 'roles')})
        # 새 항목 · 증거 · 다른 설비의 원인 · 절차와 설비 구조의 판정(new_item_issues), 절차의 수행 시스템(performers)이 읽는 것 — 적재 전 검사와 같은 판정을 지금 그래프로 다시 한다
        out.update({key: tx.run(CATALOG_Q[key]).data() for key in ('components', 'sensors', 'symptoms', 'failure_modes', 'causes', 'parts', 'state_variables')})
        return out
    current = session.execute_read(read)
    checked, issues = graph_semantics(plan, current)
    issues += new_item_issues(plan.get('knowledge'), current, plan['procedures'])[0]
    if issues:
        raise ValueError(' / '.join(i['message'] for i in issues))
    if 'knowledge' in checked:
        plan['knowledge'] = checked['knowledge']
    plan['performers'] = performers(plan, current)       # 적재(manual_graph.desired)가 긋는 System -HAS_SKILL-> Skill — 지금 그래프의 설비 구조로 정한다
    from . import manual_references
    references = session.execute_read(lambda tx: manual_references.check_plan(tx, plan))
    if references:
        plan['references'] = references
    return plan


def desired(plan, node, edge, sections, skill_id):
    """Graph additions of the knowledge part (manual_graph.desired calls this with its node/edge builders)."""
    k = plan.get('knowledge') or {}
    fms, causes = {}, {}
    named = lambda item: dict(name=item['name'], **({'aliases': item['aliases']} if item.get('aliases') else {}))     # noqa: E731
    for c in k.get('components') or []:              # 새 항목(사람이 넣기를 고른 것) — 고장 유형 · 원인과 같이 이 문서가 가진다
        node('Component', c['id'], **named(c))
    sensor_names = {}
    for s in k.get('sensors') or []:
        sensor_names[s['tag']] = s['name']
        n = node('Sensor', s['id'], tag=s['tag'], **named(s), **({'unit': s['unit']} if s.get('unit') else {}))
        edge(('Component', s['component']), 'MONITORED_BY', n)
    for s in k.get('symptoms') or []:
        n = node('Symptom', s['id'], **named(s))
        for sensor in s['sensors']:
            edge(n, 'OBSERVED_BY', ('Sensor', sensor))
    for f in k.get('failure_modes') or []:
        fms[f['id']] = node('FailureMode', f['id'], name=f['name'])
    for c in k.get('causes') or []:
        props = dict(name=c['name'], prior=c['prior'])
        if c['aliases']:
            props['aliases'] = c['aliases']
        causes[c['id']] = node('Cause', c['id'], **props)
    for e in k.get('evidence') or []:
        # 수집 태그는 판단 엔진이 평가하는 시계열 SQL 을, 그 밖의 센서 태그는 평가하지 않는다는 문장을 갖는다(unevaluated_note — 지식을 읽는 에이전트도 본다).
        # 지금 지식의 센서 이름은 적재 기록에 넣지 않는다(바뀌면 이 문서 그래프가 일지와 달라진다) — 이 문서의 새 센서만 이름으로 부른다
        judged = dict(sql=e['sql']) if 'sql' in e else dict(note=unevaluated_note(e['tag'], sensor_names.get(e['tag'])))
        n = node('Evidence', e['id'], name=e['name'], rule=e['rule'], **judged, expect=e['expect'], threshold=e['threshold'],
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
