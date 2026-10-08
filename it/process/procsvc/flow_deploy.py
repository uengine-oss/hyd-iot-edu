"""B4 (확정 TODO B4, DECISIONS 110 ②) — 흐름 판본 배포: 경보 패턴 → 지금 배포된 흐름, 기준 흐름으로 되돌리기, 기준과 비교.

경보 하나가 어느 흐름으로 열리는가 (기존 alert_policy 계약 그대로 — `alert_policy.for_definition(raw, pattern)`):
  1. 배포 API로 배포된(마지막 배포 기록이 deploy/rollback) 학생 흐름 중, 메시지 시작 + `alertPolicy.patterns`에 그 패턴이 있는
     흐름 — 여러 개면 가장 최근에 배포한 것.
  2. 없으면 기준 흐름(경보 진입 정의 `anomaly_response`)의 운영 판본(`proc_def.prod_version`). 지원하지 않는 패턴은 그 정의의
     `alertPolicy.unsupported`(사람 검토 alert_triage)로 간다 — 지금까지와 같다.
이미 열린 처리 건은 자기 판본(`bpm_proc_inst.proc_def_version`)으로 끝까지 간다(판본은 열 때 고정).

기준 보호: 기준 흐름 id(`rt.reference_ids` — 기준 파일 `anomaly_response`와 `alert_triage`)의 판본 원문은 불변 등록이라 바뀌지 않고,
"기준 흐름으로 되돌리기"(`POST /api/flows/deploy-reset`)는 운영 포인터만 기준으로 돌린다: 학생 흐름은 경보 경로에서 내리고(withdraw,
등록한 판본은 남음 — 지우는 것은 B3 `POST /api/flows/reset`), 기준 흐름의 운영 판본은 기준 판본(기동 파일 판본)으로(reset).
마지막 배포 기록이 seed(기동·마이그레이션 백필)인 흐름은 경보 경로를 가져가지 않는다 — 사람이 배포한 적 없는 옛 등록본이
조용히 경보를 가로채지 않게.

제품 근거: process-gpt-vue3 `ProcessDefinitionVersionManager.vue`(반영 버전 = prod_version), `utils/bpmnDiff.ts`(바뀐 요소 목록).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import engine

ROUTING_ACTIONS = ('deploy', 'rollback')   # 사람이 배포 API로 올린 흐름만 경보 패턴을 가져간다


def alert_patterns(raw: dict) -> list[str]:
    """Patterns a definition opens on an alert: a message start event plus the patterns named in its alertPolicy."""
    starts = [e for e in raw.get('events') or [] if isinstance(e, dict) and e.get('type') == 'startEvent']
    if not any(e.get('eventDefinition') == 'message' for e in starts):
        return []
    policy = raw.get('alertPolicy')
    patterns = policy.get('patterns') if isinstance(policy, dict) else None
    return sorted(p for p in (patterns or {}) if isinstance(p, str))


def _reference_ids(rt) -> set[str]:
    return set(getattr(rt, 'reference_ids', None) or {rt.defn.id})


def _base_version(rt) -> str:
    return getattr(rt, 'base_version', None) or rt.defn.raw['version']


def _candidates(rt) -> list[tuple[dict, engine.Definition]]:
    """Student flows on the alert path, newest deployment first."""
    refs, out = _reference_ids(rt), []
    for head in rt.repo.deployed_heads(rt.tenant_id):
        if head['id'] in refs or head.get('last_action') not in ROUTING_ACTIONS:
            continue
        defn = rt.definition_for({'proc_def_id': head['id'], 'tenant_id': rt.tenant_id, 'proc_def_version': head['prod_version']})
        out.append((head, defn))
    return out


def route_definition(rt, pattern) -> engine.Definition:
    """The deployed definition an alert of `pattern` opens (see the module docstring)."""
    if isinstance(pattern, str):
        for _head, defn in _candidates(rt):
            if pattern in alert_patterns(defn.raw):
                return defn
    return rt.deployed_definition(rt.defn.id)


def routes(rt) -> dict:
    """경보 패턴 → 지금 그 패턴을 여는 흐름·판본 표, 배포된 학생 흐름 목록(가린 패턴 포함)."""
    base = rt.deployed_definition(rt.defn.id)
    base_version = _base_version(rt)
    candidates = _candidates(rt)
    owner: dict[str, tuple[dict, engine.Definition]] = {}
    flows = []
    for head, defn in candidates:
        mine = alert_patterns(defn.raw)
        taken = [p for p in mine if p not in owner]
        for p in taken:
            owner[p] = (head, defn)
        flows.append({'definition': defn.id, 'name': defn.name, 'version': defn.raw.get('version'), 'deployed_at': head.get('deployed_at'),
                      'patterns': mine, 'opens': taken, 'shadowed': [p for p in mine if p not in taken]})
    rows = []
    for p in sorted(set(alert_patterns(base.raw)) | set(owner)):
        head, defn = owner.get(p, (None, base))
        rows.append({'pattern': p, 'definition': defn.id, 'name': defn.name, 'version': defn.raw.get('version'),
                     'reference': head is None and defn.raw.get('version') == base_version,
                     'source': '내가 배포한 흐름' if head else ('기준 흐름' if defn.raw.get('version') == base_version else '기준 흐름의 다른 판본')})
    return {'reference': {'definition': rt.defn.id, 'version': base_version, 'deployed_version': base.raw.get('version'),
                          'name': base.name, 'changed': base.raw.get('version') != base_version},
            'routes': rows, 'flows': flows,
            'unsupported': (base.raw.get('alertPolicy') or {}).get('unsupported'),
            'at_reference': not flows and base.raw.get('version') == base_version}


def deploy_reset(rt, by: str, reason: str | None = None) -> dict:
    """운영 포인터를 기준으로: 학생 흐름은 경보 경로에서 내리고, 기준 흐름의 운영 판본은 기준 판본으로. 등록한 판본·열린 처리 건은 그대로."""
    if not isinstance(by, str) or not by.strip():
        raise ValueError('되돌린 사람을 적으세요')
    by, reason = by.strip(), (reason or '').strip() or '기준 흐름으로 되돌리기'
    refs, changes = _reference_ids(rt), []
    for head in rt.repo.deployed_heads(rt.tenant_id):
        if head['id'] in refs:
            continue
        row = rt.repo.clear_deployment(head['id'], rt.tenant_id, actor=by, reason=reason)
        rt.hooks.audit('-', by, 'DEFINITION_WITHDRAWN', {'definition': head['id'], 'previous_version': head['prod_version'], 'reason': reason})
        changes.append({'definition': head['id'], 'action': 'withdraw', 'from': head['prod_version'], 'to': None,
                        'text': f'{head["id"]}@{head["prod_version"]} 경보 경로에서 내림', 'deployment': row})
    base_id, base_version = rt.defn.id, _base_version(rt)
    current = rt.repo.deployed_version(base_id, rt.tenant_id)
    if current != base_version:
        out = rt.deploy_definition(base_id, base_version, by, reason, action='reset')
        changes.append({'definition': base_id, 'action': 'reset', 'from': current, 'to': base_version,
                        'text': f'{base_id} 운영 판본 {current} → 기준 판본 {base_version}', 'deployment': out['deployment']})
    return {'changes': changes, 'already_reference': not changes,
            'message': '이미 기준 흐름입니다' if not changes else f'기준 흐름으로 되돌림 — {len(changes)}건, 다음 경보부터 적용(열린 처리 건은 자기 판본으로 끝남)',
            'routes': routes(rt)}


def compare_with_reference(rt, def_id: str, version: str | None = None) -> dict:
    """학생 판본(없으면 그 정의의 운영 판본) vs 기준 판본: 바뀐 단계·연결·조건을 사람이 읽는 목록으로 (definition_diff.compare)."""
    from .definition_diff import compare
    base_version = _base_version(rt)
    base = rt.repo.get_proc_def(rt.defn.id, rt.tenant_id, version=base_version)
    if not base or not base.get('definition'):
        raise LookupError(f'기준 판본 원문이 없습니다: {rt.defn.id}@{base_version}')
    version = version or rt.repo.deployed_version(def_id, rt.tenant_id)
    if not version:
        raise LookupError(f'비교할 판본을 지정하세요(배포된 판본이 없는 정의): {def_id}')
    row = rt.repo.get_proc_def(def_id, rt.tenant_id, version=version)
    if not row or not row.get('definition'):
        raise LookupError(f'등록되지 않은 정의 판본입니다: {def_id}@{version}')
    diff = compare(base['definition'], row['definition'])
    steps = [c['text'] for c in diff['changes'] if c['kind'] in ('단계', '연결', '분기점', '이벤트')]
    return dict(diff, reference={'definition': rt.defn.id, 'version': base_version}, target={'definition': def_id, 'version': version},
                steps=steps, summary=('기준 흐름과 같습니다' if diff['same'] else
                                      f"기준 대비 추가 {diff['counts']['추가']} · 삭제 {diff['counts']['삭제']} · 변경 {diff['counts']['변경']}"))


class ResetReq(BaseModel):
    by: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


def mount(app: FastAPI, runtime_factory) -> None:
    def _rt():
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(409, 'instance 모드가 아닙니다 (PROCESS_MODE=instance)')
        return rt

    @app.get('/api/flows/deployments')
    def flow_deployments():
        """경보 패턴 → 지금 여는 흐름·판본, 배포된 학생 흐름, 기준 판본."""
        try:
            return routes(_rt())
        except LookupError as e:
            raise HTTPException(409, str(e))

    @app.post('/api/flows/deploy-reset')
    def flow_deploy_reset(req: ResetReq):
        """기준 흐름으로 되돌리기 — 운영 포인터만(학생 흐름 정의를 지우는 것은 B3 /api/flows/reset)."""
        try:
            return deploy_reset(_rt(), req.by, req.reason)
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.get('/api/flows/deploy-compare')
    def flow_deploy_compare(definition: str, version: str | None = None):
        """학생 판본 vs 기준 판본의 바뀐 단계."""
        try:
            return compare_with_reference(_rt(), definition, version)
        except LookupError as e:
            raise HTTPException(404, str(e))
