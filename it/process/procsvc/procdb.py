"""Persistence of definitions, instances, work items and events in the ProcessGPT-shaped tables (Supabase/Postgres).

Two implementations behind one small interface:
  PgRepo      — psycopg 3 against the Supabase Postgres (it/supabase/migrations/20261003000001_process_engine.sql)
  MemoryRepo  — dict-based, for unit tests and for PROCESS_MODE=legacy without a database. PROCESS_MODE=instance needs
                PgRepo: source receipts, leases and the projection outbox are PostgreSQL rows (source_inbox.PgSourceInbox
                refuses a MemoryRepo at startup with a clear message, A143).

The repo is deliberately thin: SQL only, no business rules. Which work items exist and what state they are in is the
engine's decision (engine.py); here they are written down. The product's RPC names are kept so the lecture can point at
them, but what runs is HYD's own lock-ordered SQL (migration 000004, DECISIONS 31): the worker claim is
claim_process_workitems(…,'worker') with tenant/instance filters (fetch_pending_task is a thin wrapper of it), the
engine claim claim_process_workitems(…,'engine') (claim_submitted_workitems wrapper), results are saved by a conditional
UPDATE on the expected consumer (save_task_result RPC only when no expected_consumer is given), leases by
renew_task_lease / clear_task_lease, sweeps by expire_worker_leases / cleanup_stale_consumers. Every work-item write
locks the parent instance first (_workitem_connection), including lease renew/clear (A143).
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Protocol
from .approval_store import MemoryApprovals, PgApprovals
from .rework_store import MemoryReworks, PgReworks
from .effect_store import MemoryEffects, PgEffects
from .projection_repo import MemoryProjection, PgProjection
from .agents_store import MemoryAgents, PgAgents          # U2: tenant skills · agent ↔ skill (read side)
from .agent_authoring import MemoryAuthoring, PgAuthoring  # B1: 에이전트 · 스킬 · 배정 쓰기 + 되돌리기

SUPABASE_DSN = os.getenv("SUPABASE_DSN", "postgresql://postgres:postgres@host.docker.internal:54322/postgres")

WORKITEM_COLS = ("id", "user_id", "username", "proc_inst_id", "root_proc_inst_id", "execution_scope", "proc_def_id", "version_tag", "version",
                 "activity_id", "activity_name", "start_date", "end_date", "status", "description", "tool", "due_date", "tenant_id",
                 "reference_ids", "adhoc", "assignees", "duration", "output", "retry", "consumer", "log", "project_id", "draft", "agent_mode",
                 "agent_orch", "feedback", "draft_status", "temp_feedback", "output_url", "rework_count", "query", "feedback_status",
                 "gateway_decisions", "generation", "rework_request_id", "supersedes_id")
INSTANCE_COLS = ("proc_def_id", "proc_inst_id", "proc_inst_name", "root_proc_inst_id", "parent_proc_inst_id", "execution_scope",
                 "current_activity_ids", "participants", "role_bindings", "variables_data", "status", "tenant_id", "proc_def_version",
                 "version_tag", "version", "project_id", "start_date", "end_date", "due_date", "end_event", "start_event_id",
                 "initial_variables", "variable_sources", "rework_generation", "rework_request_id", "flow_state")
JSON_COLS = {"assignees", "output", "draft", "feedback", "role_bindings", "variables_data", "gateway_decisions", "definition", "mcp",
             "fields_json", "data", "initial_variables", "variable_sources", "flow_state"}
STALE_MINUTES = 30
LEASE_SECONDS = 120      # A097: a worker claim lives this long unless renewed (agent-sdk lease.py: 120 s, renew every 30 s)
MAX_CLAIMS = 3           # A097: after the third expired lease the row is FAILED for a person to close (agent-sdk max_claims)


class Repo(Protocol):
    def enqueue_knowledge_projections(self, tenant: str) -> None: ...
    def pending_projections(self, tenant: str, limit: int = 20) -> list[str]: ...
    def projection_snapshot(self, tenant: str, pid: str): ...
    def finish_projection(self, snapshot: dict, error: str | None = None) -> None: ...
    def projection_status(self, tenant: str, pid: str) -> dict: ...
    # definitions · forms · users · tenants
    def upsert_proc_def(self, definition: dict, tenant_id: str = "hyd") -> None: ...
    def get_proc_def(self, def_id: str, tenant_id: str = "hyd", *, version: str | None = None) -> dict | None: ...
    def list_definitions(self, tenant_id: str = "hyd") -> list[dict]: ...
    # U4: the deployed ("운영") version of a definition — what an alert RAISE opens. proc_def.prod_version + proc_def_deployment history.
    def deployed_version(self, def_id: str, tenant_id: str = "hyd") -> str | None: ...
    def record_deployment(self, def_id: str, version: str, tenant_id: str, *, action: str, actor: str, reason: str) -> dict: ...
    def list_deployments(self, def_id: str, tenant_id: str = "hyd", limit: int = 50) -> list[dict]: ...
    # B4: every definition id that has a deployed version, with the time of its newest deployment record (alert routing by
    # pattern — the newest deployed flow whose alertPolicy names the pattern opens it), and taking a flow off the alert path.
    def deployed_heads(self, tenant_id: str = "hyd") -> list[dict]: ...
    def clear_deployment(self, def_id: str, tenant_id: str, *, actor: str, reason: str) -> dict: ...
    def get_form(self, form_id: str, tenant_id: str = "hyd") -> dict | None: ...
    def get_tenant(self, tenant_id: str = "hyd") -> dict | None: ...
    def list_users(self, ids: list[str] | None = None, tenant_id: str = "hyd") -> list[dict]: ...
    # U2 (agents_store.py, read only): list_skills · get_skill · list_agent_skills
    # instances
    def event_transaction(self, key: str): ...
    def instance_transaction(self, tenant_id: str, proc_inst_id: str): ...
    def insert_approval(self, row: dict) -> None: ...
    def get_approval(self, todo_id: str, tenant_id: str) -> dict | None: ...
    def update_approval(self, row: dict) -> None: ...
    def get_rework(self, tenant_id: str, proc_inst_id: str, request_id: str) -> dict | None: ...
    def list_reworks(self, tenant_id: str, proc_inst_id: str) -> list[dict]: ...
    def insert_rework(self, row: dict) -> None: ...
    def list_approvals(self, proc_inst_id: str, tenant_id: str) -> list[dict]: ...
    # effect receipts (A072): compensation deliveries and human acknowledgements, replayed by request id
    def insert_effect_receipt(self, row: dict) -> None: ...
    def update_effect_receipt(self, row: dict) -> None: ...
    def get_effect_receipt(self, tenant_id: str, proc_inst_id: str, request_id: str) -> dict | None: ...
    def list_effect_receipts(self, tenant_id: str, proc_inst_id: str) -> list[dict]: ...
    def pending_approvals(self, tenant_id: str, after_id: str | None = None, limit: int = 100) -> list[dict]: ...
    def incident_is_process_owned(self, incident_id: str) -> bool: ...
    def due_timers(self, tenant_id: str, now: datetime, limit: int = 100) -> list[dict]: ...
    def waiting_services(self, tenant_id: str, after_id: str | None = None, limit: int = 100) -> list[dict]: ...
    def find_event_instance(self, tenant_id: str, def_id: str, event_id: str) -> dict | None: ...
    def insert_instance(self, inst: dict) -> None: ...
    def update_instance(self, inst: dict) -> None: ...
    def get_instance(self, proc_inst_id: str) -> dict | None: ...
    def list_instances(self, status: str | None = None, limit: int = 100, tenant_id: str | None = None, incident_id: str | None = None) -> list[dict]: ...
    def list_source_runs(self, tenant_id, def_id, event_prefix, limit=51, offset=0) -> list[dict]: ...
    def hide_instances(self, tenant_id, def_id, ids) -> int: ...   # B5: finished instances of one definition → is_deleted (rows kept)
    # work items
    def insert_workitems(self, items: list[dict]) -> None: ...
    def update_workitem(self, item: dict) -> None: ...
    def get_workitem(self, wid: str) -> dict | None: ...
    def list_workitems(self, proc_inst_id: str | None = None, status: str | None = None, user_id: str | None = None,
                       agent_orch: str | None = None, limit: int = 200, tenant_id: str | None = None) -> list[dict]: ...
    # the worker's RPCs (agent-sdk function.sql)
    def fetch_pending_task(self, agent_orch: str | None, consumer: str, limit: int = 1, tenant_id: str | None = None, proc_inst_id: str | None = None) -> list[dict]: ...
    def save_task_result(self, todo_id: str, payload: dict, final: bool, expected_consumer: str | None = None) -> bool: ...
    def update_task_error(self, todo_id: str, expected_consumer: str | None = None) -> bool: ...
    def set_draft_status(self, todo_id: str, draft_status: str | None, consumer: str | None = None, expected_consumer: str | None = None) -> bool: ...
    def release_worker_claim(self,todo_id: str,consumer: str) -> bool: ...
    # A097 (agent-sdk lease_until/claim_count/max_claims): a worker claim is a lease the runner renews; an expired lease
    # is reclaimable by another worker (fetch_pending_task) and, past MAX_CLAIMS, marked FAILED by the engine's sweep
    def renew_task_lease(self, todo_id: str, consumer: str, seconds: int = LEASE_SECONDS) -> bool: ...
    # A115 (infra-docker init.sql:2559-2564): a claim path that does not renew the worker lease clears it, so no worker
    # reclaims a row whose owner keeps its own expiry (legacy assessment)
    def clear_task_lease(self, todo_id: str, consumer: str) -> bool: ...
    def expire_worker_leases(self, max_claims: int = MAX_CLAIMS) -> int: ...
    # the engine's claim (completion polling)
    def claim_submitted(self, consumer: str, limit: int = 10, tenant_id: str | None = None) -> list[dict]: ...
    def cleanup_stale_consumers(self, minutes: int = STALE_MINUTES) -> int: ...
    # events · notifications
    def record_events(self, events: list[dict]) -> None: ...
    def find_task_event(self, todo_id: str, job_id: str, event_type: str) -> dict | None: ...
    def list_events(self, proc_inst_id: str | None = None, todo_id: str | None = None, limit: int = 500) -> list[dict]: ...
    def list_events_since(self, since: str | None = None, limit: int = 300) -> list[dict]: ...   # A091 live stream cursor
    def agent_task_origins(self, proc_inst_id: str, tenant_id: str) -> list[str]: ...
    def insert_notification(self, note: dict) -> dict: ...
    # U5 (inbox): 역할 → 사람 업무분장 · 담당자 변경 이력 · 사용자별 알림 조회 (migration 000029)
    def list_role_members(self, tenant_id: str, role_id: str | None = None) -> list[dict]: ...
    def set_role_member(self, tenant_id: str, role_id: str, user_id: str, member: bool) -> None: ...
    def insert_assignment(self, row: dict) -> dict: ...
    def list_assignments(self, todo_id: str, tenant_id: str) -> list[dict]: ...
    def list_notifications(self, tenant_id: str, user_ids: list[str], unread_only: bool = False, limit: int = 100) -> list[dict]: ...
    def count_unread_notifications(self, tenant_id: str, user_ids: list[str]) -> int: ...
    def mark_notifications_read(self, tenant_id: str, user_ids: list[str], ids: list[str] | None = None) -> int: ...
    def list_notifications_since(self, since: str | None = None, limit: int = 300, tenant_id: str | None = None,
                                 user_ids: list[str] | None = None) -> list[dict]: ...
    def ping(self) -> bool: ...


def consumer_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _copy(v):
    return json.loads(json.dumps(v)) if v is not None else None


def _owns_claim(row,consumer):
    return row.get('consumer')==consumer and row.get('status')=='IN_PROGRESS' and row.get('draft_status')=='STARTED'


# ---------------------------------------------------------------- in-memory
class MemoryRepo(MemoryApprovals, MemoryReworks, MemoryEffects, MemoryProjection, MemoryAgents, MemoryAuthoring):
    def __init__(self):
        self._lock = threading.RLock()
        self.defs: dict[tuple[str, str], dict] = {}
        self.def_versions: dict[tuple[str, str, str], dict] = {}
        self.deployments: list[dict] = []
        self.forms: dict[tuple[str, str], dict] = {}
        self.tenants: dict[str, dict] = {"hyd": {"id": "hyd", "name": "hyd", "mcp": None}}
        self.users: dict[str, dict] = {}
        self.instances: dict[str, dict] = {}
        self.workitems: dict[str, dict] = {}
        self.events: list[dict] = []
        self.notifications: list[dict] = []
        self.role_members: list[dict] = []
        self.assignments: list[dict] = []
        self.approvals: dict[str, dict] = {}
        self.reworks: dict[tuple, dict] = {}
        self.effect_receipts: dict[tuple, dict] = {}
        self.projection_jobs = {}
        self._projection_sequence = 0

    @contextmanager
    def event_transaction(self, key: str):
        with self._lock:
            before = (_copy(self.instances), _copy(self.workitems), deepcopy(self.projection_jobs))
            try:
                yield
            except Exception:
                self.instances, self.workitems, self.projection_jobs = before
                raise

    def find_event_instance(self, tenant_id: str, def_id: str, event_id: str) -> dict | None:
        return next((_copy(i) for i in self.instances.values()
                     if i.get("tenant_id") == tenant_id and i.get("proc_def_id") == def_id
                     and i.get("start_event_id") == event_id), None)

    @contextmanager
    def instance_transaction(self, tenant_id: str, proc_inst_id: str):
        with self._lock:
            inst=self.instances.get(proc_inst_id)
            if not inst or inst.get('tenant_id')!=tenant_id:raise KeyError('no such instance')
            before=deepcopy((self.instances,self.workitems,self.events,self.notifications,self.approvals,self.reworks,self.projection_jobs,self.assignments))
            try:yield
            except Exception:
                self.instances,self.workitems,self.events,self.notifications,self.approvals,self.reworks,self.projection_jobs,self.assignments=before
                raise

    def due_timers(self, tenant_id: str, now: datetime, limit: int = 100) -> list[dict]:
        with self._lock:
            rows=[w for w in self.workitems.values() if w.get('tenant_id')==tenant_id
                  and w['status']=='IN_PROGRESS' and w.get('agent_orch')=='hyd-process'
                  and w.get('user_id')=='sys:process' and w.get('due_date')
                  and datetime.fromisoformat(w['due_date'].replace('Z','+00:00'))<=now
                  and self.instances.get(w['proc_inst_id'],{}).get('status')=='RUNNING'
                  and self.instances[w['proc_inst_id']].get('tenant_id')==tenant_id
                  and not self.instances[w['proc_inst_id']].get('is_deleted')]
            return [_copy(w) for w in sorted(rows,key=lambda w:(w['due_date'],w['id']))[:limit]]

    def waiting_services(self, tenant_id: str, after_id: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            rows=[w for w in self.workitems.values() if w.get('tenant_id')==tenant_id and w['status']=='SUBMITTED'
                  and w.get('agent_orch')=='hyd-process' and w.get('consumer') and not w.get('output')
                  and w.get('tool') in ('incident:command','incident:reobserve','enterprise:WO_CREATE')
                  and self.instances.get(w['proc_inst_id'],{}).get('status')=='RUNNING'
                  and self.instances[w['proc_inst_id']].get('tenant_id')==tenant_id
                  and not self.instances[w['proc_inst_id']].get('is_deleted')
                  and (after_id is None or w['id']>after_id)]
            return [_copy(w) for w in sorted(rows,key=lambda w:w['id'])[:limit]]

    # ---- definitions · forms · users · tenants
    def upsert_proc_def(self, definition: dict, tenant_id: str = "hyd") -> None:
        version = definition.get('version')
        if not isinstance(version, str) or not version.strip():
            raise ValueError('정의 버전(version)은 비어 있지 않은 문자열이어야 합니다')
        with self._lock:
            key = (definition['processDefinitionId'], tenant_id, version)
            old = self.def_versions.get(key)
            if old and json.dumps(old['definition'], sort_keys=True) != json.dumps(definition, sort_keys=True):
                raise ValueError('이미 등록한 정의 버전은 변경할 수 없습니다. 새 버전을 사용하세요')
            # U4: registering never moves the deployed pointer (prod_version); only record_deployment does.
            head = self.defs.get(key[:2]) or {}
            row = {'id': definition['processDefinitionId'], 'tenant_id': tenant_id,
                   'name': definition.get('processDefinitionName'), 'definition': _copy(definition),
                   'prod_version': head.get('prod_version'), 'type': 'bpmn', 'ontology_ref': definition.get('ontologyRef')}
            if old is None:
                self.def_versions[key] = dict(_copy(row), prod_version=version, message='HYD immutable registration',
                                              registered_at=datetime.now(timezone.utc).isoformat())
            self.defs[key[:2]] = row

    def get_proc_def(self, def_id: str, tenant_id: str = "hyd", *, version: str | None = None) -> dict | None:
        if version is not None:
            return _copy(self.def_versions.get((def_id, tenant_id, version)))
        return _copy(self.defs.get((def_id, tenant_id)))

    def list_definitions(self, tenant_id: str = "hyd") -> list[dict]:
        return [_copy(v) for (did,tenant,version),v in sorted(self.def_versions.items()) if tenant == tenant_id]

    def deployed_version(self, def_id: str, tenant_id: str = "hyd") -> str | None:
        head = self.defs.get((def_id, tenant_id))
        return head.get('prod_version') if head else None

    def record_deployment(self, def_id: str, version: str, tenant_id: str, *, action: str, actor: str, reason: str) -> dict:
        with self._lock:
            head = self.defs.get((def_id, tenant_id))
            if (def_id, tenant_id, version) not in self.def_versions:
                raise LookupError(f'등록되지 않은 정의 판본입니다: {def_id}@{version}')
            if head is None:   # B3 가져온 흐름: PG 는 등록 때 proc_def 머리(prod_version NULL)를 넣는다 — 메모리는 첫 배포 때 같은 머리를 만든다
                v = self.def_versions[(def_id, tenant_id, version)]
                head = self.defs[(def_id, tenant_id)] = {'id': def_id, 'tenant_id': tenant_id, 'name': v.get('name'), 'definition': _copy(v.get('definition')),
                                                         'prod_version': None, 'type': 'bpmn', 'ontology_ref': v.get('ontology_ref')}
            row = {'id': str(uuid.uuid4()), 'tenant_id': tenant_id, 'proc_def_id': def_id, 'version': version,
                   'previous_version': head.get('prod_version'), 'action': action, 'actor': actor, 'reason': reason,
                   'created_at': datetime.now(timezone.utc).isoformat()}
            head['prod_version'] = version
            self.deployments.append(row)
            return _copy(row)

    def list_deployments(self, def_id: str, tenant_id: str = "hyd", limit: int = 50) -> list[dict]:
        rows = [d for d in self.deployments if d['tenant_id'] == tenant_id and d['proc_def_id'] == def_id]
        return [_copy(d) for d in list(reversed(rows))[:limit]]

    def deployed_heads(self, tenant_id: str = "hyd") -> list[dict]:
        out = []
        for (def_id, tenant), head in self.defs.items():
            if tenant != tenant_id or not head.get('prod_version'):
                continue
            seq = max((n for n, d in enumerate(self.deployments) if d['tenant_id'] == tenant_id and d['proc_def_id'] == def_id), default=-1)
            last = self.deployments[seq] if seq >= 0 else {}
            out.append({'id': def_id, 'prod_version': head['prod_version'], 'deployed_seq': seq,
                        'deployed_at': last.get('created_at'), 'last_action': last.get('action')})
        return sorted(out, key=lambda r: (r['deployed_seq'], r['id']), reverse=True)

    def clear_deployment(self, def_id: str, tenant_id: str, *, actor: str, reason: str) -> dict:
        with self._lock:
            head = self.defs.get((def_id, tenant_id))
            if head is None or not head.get('prod_version'):
                raise LookupError(f'배포된 판본이 없는 정의입니다: {def_id}')
            row = {'id': str(uuid.uuid4()), 'tenant_id': tenant_id, 'proc_def_id': def_id, 'version': None,
                   'previous_version': head['prod_version'], 'action': 'withdraw', 'actor': actor, 'reason': reason,
                   'created_at': datetime.now(timezone.utc).isoformat()}
            head['prod_version'] = None
            self.deployments.append(row)
            return _copy(row)

    def upsert_form(self, form: dict, tenant_id: str = "hyd") -> None:
        self.forms[(form["id"], tenant_id)] = dict(form, tenant_id=tenant_id)

    def get_form(self, form_id: str, tenant_id: str = "hyd") -> dict | None:
        return _copy(self.forms.get((form_id, tenant_id)))

    def upsert_tenant(self, tenant: dict) -> None:
        self.tenants[tenant["id"]] = dict(tenant)

    def get_tenant(self, tenant_id: str = "hyd") -> dict | None:
        return _copy(self.tenants.get(tenant_id))

    def upsert_user(self, user: dict) -> None:
        self.users[user["id"]] = dict(user)

    def list_users(self, ids: list[str] | None = None, tenant_id: str = "hyd") -> list[dict]:
        return [_copy(u) for u in self.users.values() if (ids is None or u["id"] in ids) and u.get("tenant_id", "hyd") == tenant_id]

    # ---- instances
    def insert_instance(self, inst: dict) -> None:
        with self._lock:
            self.instances.setdefault(inst["proc_inst_id"], _copy(inst))
            self._enqueue_projection(inst)

    def update_instance(self, inst: dict) -> None:
        with self._lock:
            prior = self.instances.get(inst['proc_inst_id'])
            if prior is not None and prior.get('initial_variables') != inst.get('initial_variables'):
                raise ValueError('저장된 시작 입력은 변경할 수 없습니다')
            self.instances[inst['proc_inst_id']] = _copy(inst)
            self._enqueue_projection(inst)

    def get_instance(self, proc_inst_id: str) -> dict | None:
        return _copy(self.instances.get(proc_inst_id))

    def incident_is_process_owned(self, incident_id: str) -> bool:
        return any(any(v.get('key')=='incident' and v.get('value')==incident_id
                       for v in i.get('variables_data') or []) for i in self.instances.values())

    def list_instances(self, status: str | None = None, limit: int = 100, tenant_id: str | None = None, incident_id: str | None = None) -> list[dict]:
        rows = [i for i in self.instances.values() if not i.get("is_deleted",False)
                and (status is None or i["status"] == status) and (tenant_id is None or i.get("tenant_id") == tenant_id)
                and (incident_id is None or any(v.get('key')=='incident' and v.get('value')==incident_id
                    for v in i.get('variables_data') or []))]
        return [_copy(i) for i in sorted(rows, key=lambda i: i["start_date"], reverse=True)[:limit]]

    # ---- work items
    def list_source_runs(self, tenant_id, def_id, event_prefix, limit=51, offset=0):
        rows=[i for i in self.instances.values() if i.get('tenant_id')==tenant_id and i.get('proc_def_id')==def_id
              and not i.get('is_deleted',False) and str(i.get('start_event_id') or '').startswith(event_prefix)]
        rows.sort(key=lambda i:(i['start_date'],i['proc_inst_id']),reverse=True)
        return [{k:_copy(i.get(k)) for k in ('proc_inst_id','status','start_date','end_date')} for i in rows[offset:offset+limit]]

    def hide_instances(self, tenant_id, def_id, ids):
        n=0
        with self._lock:
            for pid in ids:
                i=self.instances.get(pid)
                if i and i.get('tenant_id')==tenant_id and i.get('proc_def_id')==def_id and i.get('status')!='RUNNING' and not i.get('is_deleted'):
                    i['is_deleted']=True;n+=1
        return n

    def insert_workitems(self, items: list[dict]) -> None:
        with self._lock:
            for w in items:
                self.workitems[w["id"]] = _copy(w)
                self._enqueue_projection(w)

    def update_workitem(self, item: dict) -> None:
        prior = self.workitems.get(item['id'])
        if prior and any(prior.get(k) != item.get(k) for k in ('generation', 'rework_request_id', 'supersedes_id')):
            raise ValueError('stored workitem generation identity is immutable')
        self.insert_workitems([item])

    def get_workitem(self, wid: str) -> dict | None:
        return _copy(self.workitems.get(wid))

    def list_workitems(self, proc_inst_id=None, status=None, user_id=None, agent_orch=None, limit=200, tenant_id=None) -> list[dict]:
        rows = [w for w in self.workitems.values()
                if (proc_inst_id is None or w["proc_inst_id"] == proc_inst_id) and (status is None or w["status"] == status)
                and (user_id is None or w.get("user_id") == user_id) and (agent_orch is None or w.get("agent_orch") == agent_orch) and (tenant_id is None or w.get("tenant_id") == tenant_id)]
        return [_copy(w) for w in sorted(rows, key=lambda w: w["start_date"])[:limit]]

    # ---- worker RPCs
    def fetch_pending_task(self, agent_orch: str | None, consumer: str, limit: int = 1, tenant_id: str | None = None, proc_inst_id: str | None = None) -> list[dict]:
        with self._lock:
            out = []
            for w in sorted(self.workitems.values(), key=lambda w: w["start_date"]):
                if w["status"] != "IN_PROGRESS" or (agent_orch and w.get("agent_orch") != agent_orch) or (tenant_id is not None and w.get("tenant_id") != tenant_id) or (proc_inst_id is not None and w.get("proc_inst_id") != proc_inst_id):
                    continue
                expired = w.get("draft_status") == "STARTED" and w.get("lease_until") is not None \
                    and w["lease_until"] < time.time() and int(w.get("claim_count") or 0) < MAX_CLAIMS
                ready = (w.get("agent_mode") in ("DRAFT", "COMPLETE") and w.get("draft") is None and w.get("draft_status") is None) \
                    or w.get("draft_status") == "FB_REQUESTED" or expired
                if not ready:
                    continue
                if expired:
                    w["log"] = (w.get("log") or "") + f"[Lease expired: reclaimed by {consumer} (claim {int(w.get('claim_count') or 0) + 1})] "
                w["draft_status"], w["consumer"] = "STARTED", consumer
                # A114 (agent-sdk function.sql:102-105): only a reclaim of an expired lease accumulates; a fresh claim or a
                # re-claim after a person's answer (FB_REQUESTED) starts at 1, so feedback rounds do not use up the cap.
                w["lease_until"] = time.time() + LEASE_SECONDS
                w["claim_count"] = int(w.get("claim_count") or 0) + 1 if expired else 1
                self._enqueue_projection(w)
                out.append(_copy(w))
                if len(out) >= limit:
                    break
            return out

    def save_task_result(self, todo_id: str, payload: dict, final: bool, expected_consumer: str | None = None) -> bool:
        with self._lock:
            w = self.workitems.get(todo_id)
            if not w or (expected_consumer is not None and not _owns_claim(w,expected_consumer)):
                return False
            if not final:
                w["draft"] = _copy(payload)
            elif w.get("agent_mode") == "COMPLETE":
                w.update(output=_copy(payload), status="SUBMITTED", draft_status="COMPLETED", consumer=None)
            else:
                w.update(draft=_copy(payload), draft_status="COMPLETED", consumer=None)
            self._enqueue_projection(w)
            return True

    def update_task_error(self, todo_id: str, expected_consumer: str | None = None) -> bool:
        return self.set_draft_status(todo_id,"FAILED",expected_consumer=expected_consumer)

    def set_draft_status(self, todo_id: str, draft_status: str | None, consumer: str | None = None, expected_consumer: str | None = None) -> bool:
        with self._lock:
            w=self.workitems.get(todo_id)
            if not w or (expected_consumer is not None and not _owns_claim(w,expected_consumer)):
                return False
            w.update(draft_status=draft_status,consumer=consumer)
            self._enqueue_projection(w)
            return True

    def release_worker_claim(self,todo_id: str,consumer: str) -> bool:
        with self._lock:
            w=self.workitems.get(todo_id)
            if not w or w.get('consumer')!=consumer:return False
            w['consumer']=None
            self._enqueue_projection(w)
            return True

    def renew_task_lease(self, todo_id: str, consumer: str, seconds: int = LEASE_SECONDS) -> bool:
        with self._lock:
            w = self.workitems.get(todo_id)
            if not w or w.get("consumer") != consumer or w.get("status") != "IN_PROGRESS" or w.get("draft_status") != "STARTED":
                return False
            w["lease_until"] = time.time() + seconds
            return True

    def clear_task_lease(self, todo_id: str, consumer: str) -> bool:
        with self._lock:
            w = self.workitems.get(todo_id)
            if not w or w.get("consumer") != consumer:
                return False
            w["lease_until"] = None
            return True

    def expire_worker_leases(self, max_claims: int = MAX_CLAIMS) -> int:
        with self._lock:
            n = 0
            for w in self.workitems.values():
                if w.get("status") == "IN_PROGRESS" and w.get("draft_status") == "STARTED" and w.get("lease_until") is not None \
                        and w["lease_until"] < time.time() and int(w.get("claim_count") or 0) >= max_claims:
                    w.update(draft_status="FAILED", consumer=None, log=(w.get("log") or "") + f"[Lease expired after {w.get('claim_count')} claims: run marked FAILED] ")
                    self._enqueue_projection(w); n += 1
            return n

    # ---- engine claim
    def claim_submitted(self, consumer: str, limit: int = 10, tenant_id: str | None = None) -> list[dict]:
        with self._lock:
            out = []
            for w in sorted(self.workitems.values(), key=lambda w: w["start_date"]):
                if w["status"] == "SUBMITTED" and w.get("consumer") is None and (tenant_id is None or w.get("tenant_id") == tenant_id):
                    w["consumer"] = consumer
                    self._enqueue_projection(w)
                    out.append(_copy(w))
                    if len(out) >= limit:
                        break
            return out

    def cleanup_stale_consumers(self, minutes: int = STALE_MINUTES) -> int:
        return 0

    # ---- events · notifications
    def record_events(self, events: list[dict]) -> None:
        with self._lock:
            for evt in events:
                e = dict(evt)
                e.setdefault("id", str(uuid.uuid4()))
                e.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                e.setdefault("data", {})
                self.events.append(e)

    def insert_event(self, evt: dict) -> None:
        self.record_events([evt])

    def list_events(self, proc_inst_id=None, todo_id=None, limit=500) -> list[dict]:
        rows = [e for e in self.events if (proc_inst_id is None or e.get("proc_inst_id") == proc_inst_id) and (todo_id is None or e.get("todo_id") == todo_id)]
        return [_copy(e) for e in rows[-limit:]]

    def list_events_since(self, since=None, limit=300) -> list[dict]:
        """Events at or after `since` (ISO), oldest first; the caller drops ids it has seen (A091 SSE cursor)."""
        rows = [e for e in self.events if since is None or str(e.get("timestamp") or "") >= since]
        return [_copy(e) for e in sorted(rows, key=lambda e: (str(e.get("timestamp") or ""), e["id"]))[:limit]]

    def find_task_event(self, todo_id, job_id, event_type):
        return next((_copy(e) for e in reversed(self.events) if e.get('todo_id')==todo_id
                     and e.get('job_id')==job_id and e.get('event_type')==event_type),None)

    def insert_notification(self, note: dict) -> dict:
        with self._lock:
            row = dict(note, id=note.get("id") or str(uuid.uuid4()), tenant_id=note.get("tenant_id", "hyd"), is_read=False,
                       created_at=datetime.now(timezone.utc).isoformat())
            self.notifications.append(row)
            return _copy(row)

    def agent_task_origins(self, proc_inst_id: str, tenant_id: str) -> list[str]:
        inst = self.instances.get(proc_inst_id)
        if not inst or inst.get('tenant_id') != tenant_id:
            return []
        return sorted({e.get('job_id') or '' for e in self.events
                       if e.get('proc_inst_id') == proc_inst_id and e.get('event_type') == 'task_started'})

    # ---- U5 inbox: 업무분장 · 담당자 이력 · 사용자별 알림
    def list_role_members(self, tenant_id: str, role_id: str | None = None) -> list[dict]:
        return [_copy(m) for m in self.role_members if m["tenant_id"] == tenant_id and (role_id is None or m["role_id"] == role_id)]

    def set_role_member(self, tenant_id: str, role_id: str, user_id: str, member: bool) -> None:
        with self._lock:
            self.role_members = [m for m in self.role_members if not (m["tenant_id"] == tenant_id and m["role_id"] == role_id and m["user_id"] == user_id)]
            if member:
                self.role_members.append({"tenant_id": tenant_id, "role_id": role_id, "user_id": user_id,
                                          "created_at": datetime.now(timezone.utc).isoformat()})

    def insert_assignment(self, row: dict) -> dict:
        with self._lock:
            saved = dict(row, id=row.get("id") or str(uuid.uuid4()), created_at=row.get("created_at") or datetime.now(timezone.utc).isoformat())
            self.assignments.append(saved)
            return _copy(saved)

    def list_assignments(self, todo_id: str, tenant_id: str) -> list[dict]:
        return [_copy(a) for a in self.assignments if a["todo_id"] == todo_id and a.get("tenant_id", "hyd") == tenant_id]

    def _notes_for(self, tenant_id, user_ids):
        return [n for n in self.notifications if n.get("tenant_id", "hyd") == tenant_id and n.get("user_id") in set(user_ids)]

    def list_notifications(self, tenant_id, user_ids, unread_only=False, limit=100) -> list[dict]:
        rows = [n for n in self._notes_for(tenant_id, user_ids) if not unread_only or not n.get("is_read")]
        return [_copy(n) for n in sorted(rows, key=lambda n: (n["created_at"], n["id"]), reverse=True)[:limit]]

    def count_unread_notifications(self, tenant_id, user_ids) -> int:
        return sum(1 for n in self._notes_for(tenant_id, user_ids) if not n.get("is_read"))

    def mark_notifications_read(self, tenant_id, user_ids, ids=None) -> int:
        with self._lock:
            n = 0
            for note in self._notes_for(tenant_id, user_ids):
                if not note.get("is_read") and (ids is None or note["id"] in set(ids)):
                    note["is_read"] = True; n += 1
            return n

    def list_notifications_since(self, since=None, limit=300, tenant_id=None, user_ids=None) -> list[dict]:
        rows = [n for n in self.notifications if (since is None or str(n.get("created_at") or "") >= since)
                and (tenant_id is None or n.get("tenant_id", "hyd") == tenant_id) and (user_ids is None or n.get("user_id") in set(user_ids))]
        return [_copy(n) for n in sorted(rows, key=lambda n: (str(n.get("created_at") or ""), n["id"]))[:limit]]

    def ping(self) -> bool:
        return True


# ---------------------------------------------------------------- postgres (Supabase)
class PgRepo(PgApprovals, PgReworks, PgEffects, PgProjection, PgAgents, PgAuthoring):
    def __init__(self, dsn: str | None = None):
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
        self._psycopg, self._dict_row, self._Jsonb = psycopg, dict_row, Jsonb
        self.dsn = dsn or SUPABASE_DSN
        self._local = threading.local()

    @contextmanager
    def _conn(self):
        active = getattr(self._local, "connection", None)
        if active is not None:
            yield active
        else:
            with self._psycopg.connect(self.dsn, autocommit=True, connect_timeout=5, row_factory=self._dict_row) as connection:
                yield connection

    @contextmanager
    def event_transaction(self, key: str):
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("nested event transaction")
        with self._psycopg.connect(self.dsn, connect_timeout=5, row_factory=self._dict_row) as connection:
            self._local.connection = connection
            try:
                connection.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))
                yield
            finally:
                del self._local.connection

    def find_event_instance(self, tenant_id: str, def_id: str, event_id: str) -> dict | None:
        with self._conn() as connection:
            return self._row(connection.execute(
                "select * from bpm_proc_inst where tenant_id=%s and proc_def_id=%s and start_event_id=%s",
                (tenant_id, def_id, event_id)).fetchone())

    @contextmanager
    def instance_transaction(self, tenant_id: str, proc_inst_id: str):
        if getattr(self._local,'connection',None) is not None:
            raise RuntimeError('nested storage transaction; runtime must reuse its transition')
        with self._psycopg.connect(self.dsn,connect_timeout=5,row_factory=self._dict_row) as c:
            self._local.connection=c
            try:
                row=c.execute('select proc_inst_id from bpm_proc_inst where tenant_id=%s and proc_inst_id=%s for update',
                              (tenant_id,proc_inst_id)).fetchone()
                if not row:raise KeyError('no such instance')
                # Claims/results update child rows independently. Lock these too,
                # then load the current state before calculating the transition.
                c.execute('select id from todolist where proc_inst_id=%s order by id for update',(proc_inst_id,)).fetchall()
                yield
            finally:
                del self._local.connection

    def due_timers(self, tenant_id: str, now: datetime, limit: int = 100) -> list[dict]:
        with self._conn() as c:
            return [self._row(w) for w in c.execute("""select w.* from todolist w join bpm_proc_inst i using(proc_inst_id)
                where w.tenant_id=%s and i.tenant_id=%s and i.status='RUNNING' and not i.is_deleted
                and w.status='IN_PROGRESS' and w.agent_orch='hyd-process' and w.user_id='sys:process'
                and w.due_date<=%s order by w.due_date,w.id limit %s""",(tenant_id,tenant_id,now,limit)).fetchall()]

    def waiting_services(self, tenant_id: str, after_id: str | None = None, limit: int = 100) -> list[dict]:
        with self._conn() as c:
            return [self._row(w) for w in c.execute("""select w.* from todolist w join bpm_proc_inst i using(proc_inst_id)
                where w.tenant_id=%s and i.tenant_id=%s and i.status='RUNNING' and not i.is_deleted
                and w.status='SUBMITTED' and w.agent_orch='hyd-process' and w.consumer is not null
                and coalesce(w.output,'{}'::jsonb)='{}'::jsonb
                and w.tool in ('incident:command','incident:reobserve','enterprise:WO_CREATE')
                and (%s::uuid is null or w.id>%s::uuid) order by w.id limit %s""",
                (tenant_id,tenant_id,after_id,after_id,limit)).fetchall()]

    def _val(self, col: str, v):
        if col in JSON_COLS and v is not None:
            return self._Jsonb(v)
        return v

    @contextmanager
    def _workitem_connection(self, wid):
        """Match engine lock order, including the child UPDATE parent trigger."""
        with self._conn() as c:
            with c.transaction():
                c.execute('''select i.proc_inst_id from bpm_proc_inst i
                    join todolist w using(proc_inst_id) where w.id=%s for update of i''',(wid,)).fetchone()
                yield c

    @staticmethod
    def _row(r: dict | None) -> dict | None:
        if r is None:
            return None
        out = {}
        for k, v in r.items():
            if isinstance(v, datetime):
                v = (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            elif isinstance(v, uuid.UUID):
                v = str(v)
            out[k] = v
        return out

    # ---- definitions · forms · users · tenants
    def upsert_proc_def(self, definition: dict, tenant_id: str = "hyd") -> None:
        version = definition.get('version')
        if not isinstance(version, str) or not version.strip():
            raise ValueError('정의 버전(version)은 비어 있지 않은 문자열이어야 합니다')
        with self._conn() as c, c.transaction():
            c.execute('''insert into proc_def_version
                         (arcv_id, proc_def_id, version, version_tag, tenant_id, definition, message)
                         values (%s,%s,%s,'hyd-immutable',%s,%s,'HYD immutable registration')
                         on conflict (tenant_id,proc_def_id,version) where version_tag='hyd-immutable' do nothing''',
                      (definition['processDefinitionId']+'_'+version, definition['processDefinitionId'], version,
                       tenant_id, self._Jsonb(definition)))
            row = c.execute('''select definition = %s as same from proc_def_version
                               where tenant_id=%s and proc_def_id=%s and version=%s and version_tag='hyd-immutable' ''',
                            (self._Jsonb(definition), tenant_id, definition['processDefinitionId'], version)).fetchone()
            if not row or not row['same']:
                raise ValueError('이미 등록한 정의 버전은 변경할 수 없습니다. 새 버전을 사용하세요')
            # U4: proc_def.definition is the latest registered text; prod_version (the deployed pointer) is left as it is —
            # a new row starts with no deployed version, record_deployment() sets it.
            c.execute("""insert into proc_def (id, tenant_id, name, definition, prod_version, type, ontology_ref, updated_at)
                         values (%s, %s, %s, %s, null, 'bpmn', %s, now())
                         on conflict (id, tenant_id) where isdeleted = false do update set name = excluded.name, definition = excluded.definition,
                             ontology_ref = excluded.ontology_ref, updated_at = now()""",
                      (definition["processDefinitionId"], tenant_id, definition.get("processDefinitionName"), self._Jsonb(definition),
                       definition.get("ontologyRef")))

    def get_proc_def(self, def_id: str, tenant_id: str = "hyd", *, version: str | None = None) -> dict | None:
        with self._conn() as c:
            if version is not None:
                return self._row(c.execute('''select proc_def_id as id, tenant_id, definition, version as prod_version,
                        definition->>'processDefinitionName' as name, definition->>'ontologyRef' as ontology_ref, message,
                        "timeStamp" as registered_at
                        from proc_def_version where proc_def_id=%s and tenant_id=%s and version=%s and version_tag='hyd-immutable' ''',
                        (def_id, tenant_id, version)).fetchone())
            return self._row(c.execute("select * from proc_def where id = %s and tenant_id = %s and isdeleted = false", (def_id, tenant_id)).fetchone())

    def list_definitions(self, tenant_id: str = "hyd") -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("""select proc_def_id as id,tenant_id,version as prod_version,
                definition->>'processDefinitionName' as name,definition,message,"timeStamp" as registered_at from proc_def_version
                where tenant_id=%s and version_tag='hyd-immutable' order by proc_def_id,version""", (tenant_id,)).fetchall()]

    def deployed_version(self, def_id: str, tenant_id: str = "hyd") -> str | None:
        with self._conn() as c:
            row = c.execute("select prod_version from proc_def where id=%s and tenant_id=%s and isdeleted=false", (def_id, tenant_id)).fetchone()
            return row['prod_version'] if row else None

    def record_deployment(self, def_id: str, version: str, tenant_id: str, *, action: str, actor: str, reason: str) -> dict:
        with self._conn() as c, c.transaction():
            head = c.execute("select prod_version from proc_def where id=%s and tenant_id=%s and isdeleted=false for update",
                             (def_id, tenant_id)).fetchone()
            known = c.execute("""select 1 from proc_def_version where tenant_id=%s and proc_def_id=%s and version=%s
                                 and version_tag='hyd-immutable'""", (tenant_id, def_id, version)).fetchone()
            if head is None or known is None:
                raise LookupError(f'등록되지 않은 정의 판본입니다: {def_id}@{version}')
            c.execute("update proc_def set prod_version=%s, updated_at=now() where id=%s and tenant_id=%s and isdeleted=false",
                      (version, def_id, tenant_id))
            row = c.execute("""insert into proc_def_deployment (tenant_id, proc_def_id, version, previous_version, action, actor, reason)
                               values (%s,%s,%s,%s,%s,%s,%s) returning *""",
                            (tenant_id, def_id, version, head['prod_version'], action, actor, reason)).fetchone()
            return self._row(row)

    def list_deployments(self, def_id: str, tenant_id: str = "hyd", limit: int = 50) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("""select * from proc_def_deployment where tenant_id=%s and proc_def_id=%s
                order by created_at desc, id desc limit %s""", (tenant_id, def_id, limit)).fetchall()]

    def deployed_heads(self, tenant_id: str = "hyd") -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("""select d.id, d.prod_version, x.created_at as deployed_at, x.action as last_action
                from proc_def d left join lateral (select created_at, action from proc_def_deployment y
                    where y.tenant_id=d.tenant_id and y.proc_def_id=d.id order by y.created_at desc, y.id desc limit 1) x on true
                where d.tenant_id=%s and not d.isdeleted and d.prod_version is not null
                order by x.created_at desc nulls last, d.id desc""", (tenant_id,)).fetchall()]

    def clear_deployment(self, def_id: str, tenant_id: str, *, actor: str, reason: str) -> dict:
        with self._conn() as c, c.transaction():
            head = c.execute("select prod_version from proc_def where id=%s and tenant_id=%s and isdeleted=false for update",
                             (def_id, tenant_id)).fetchone()
            if head is None or not head['prod_version']:
                raise LookupError(f'배포된 판본이 없는 정의입니다: {def_id}')
            c.execute("update proc_def set prod_version=null, updated_at=now() where id=%s and tenant_id=%s and isdeleted=false",
                      (def_id, tenant_id))
            row = c.execute("""insert into proc_def_deployment (tenant_id, proc_def_id, version, previous_version, action, actor, reason)
                               values (%s,%s,null,%s,'withdraw',%s,%s) returning *""",
                            (tenant_id, def_id, head['prod_version'], actor, reason)).fetchone()
            return self._row(row)

    def get_form(self, form_id: str, tenant_id: str = "hyd") -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("select * from form_def where id = %s and tenant_id = %s", (form_id, tenant_id)).fetchone())

    def get_tenant(self, tenant_id: str = "hyd") -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("select * from tenants where id = %s", (tenant_id,)).fetchone())

    def list_users(self, ids: list[str] | None = None, tenant_id: str = "hyd") -> list[dict]:
        with self._conn() as c:
            if ids is None:
                rows = c.execute("select * from users where tenant_id = %s order by id", (tenant_id,)).fetchall()
            else:
                rows = c.execute("select * from users where tenant_id = %s and id = any(%s) order by id", (tenant_id, list(ids))).fetchall()
            return [self._row(r) for r in rows]

    # ---- instances
    def insert_instance(self, inst: dict) -> None:
        cols = [k for k in INSTANCE_COLS if k in inst]
        with self._conn() as c:
            c.execute(f"insert into bpm_proc_inst ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) on conflict (proc_inst_id) do nothing",
                      [self._val(k, inst[k]) for k in cols])

    def update_instance(self, inst: dict) -> None:
        cols = [k for k in INSTANCE_COLS if k in inst and k != "proc_inst_id"]
        with self._conn() as c:
            c.execute(f"update bpm_proc_inst set {', '.join(f'{k} = %s' for k in cols)} where proc_inst_id = %s",
                      [self._val(k, inst[k]) for k in cols] + [inst["proc_inst_id"]])

    def get_instance(self, proc_inst_id: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("select * from bpm_proc_inst where proc_inst_id = %s", (proc_inst_id,)).fetchone())

    def incident_is_process_owned(self, incident_id: str) -> bool:
        # Deleted/completed instances still own their Incident; legacy APIs must not reopen them.
        with self._conn() as c:
            return c.execute('select exists(select 1 from bpm_proc_inst where variables_data @> %s::jsonb) as owned',
                             (self._Jsonb([{'key':'incident','value':incident_id}]),)).fetchone()['owned']

    def list_instances(self, status: str | None = None, limit: int = 100, tenant_id: str | None = None, incident_id: str | None = None) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("""select * from bpm_proc_inst where is_deleted=false
                    and (%s::text is null or status::text=%s) and (%s::text is null or tenant_id=%s)
                    and (%s::text is null or variables_data @> %s::jsonb)
                    order by start_date desc limit %s""", (status,status,tenant_id,tenant_id,incident_id,
                        self._Jsonb([{'key':'incident','value':incident_id}]),limit)).fetchall()
            return [self._row(r) for r in rows]

    def list_source_runs(self, tenant_id, def_id, event_prefix, limit=51, offset=0):
        with self._conn() as c:
            return [self._row(r) for r in c.execute('''select proc_inst_id,status,start_date,end_date from bpm_proc_inst
                where tenant_id=%s and proc_def_id=%s and is_deleted=false and left(start_event_id,%s)=%s
                order by start_date desc,proc_inst_id desc limit %s offset %s''',
                (tenant_id,def_id,len(event_prefix),event_prefix,limit,offset)).fetchall()]

    def hide_instances(self, tenant_id, def_id, ids):
        if not ids:return 0
        with self._conn() as c:
            return c.execute('''update bpm_proc_inst set is_deleted=true where tenant_id=%s and proc_def_id=%s
                and proc_inst_id=any(%s) and status<>'RUNNING' and not is_deleted''',(tenant_id,def_id,list(ids))).rowcount

    # ---- work items
    def insert_workitems(self, items: list[dict]) -> None:
        if not items:
            return
        with self._conn() as c:
            for w in items:
                cols = [k for k in WORKITEM_COLS if k in w]
                c.execute(f"insert into todolist ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) on conflict (id) do nothing",
                          [self._val(k, w[k]) for k in cols])

    def update_workitem(self, item: dict) -> None:
        cols = [k for k in WORKITEM_COLS if k in item and k != "id"]
        with self._workitem_connection(item['id']) as c:
            c.execute(f"update todolist set {', '.join(f'{k} = %s' for k in cols)} where id = %s", [self._val(k, item[k]) for k in cols] + [item["id"]])

    def get_workitem(self, wid: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("select * from todolist where id = %s", (wid,)).fetchone())

    def list_workitems(self, proc_inst_id=None, status=None, user_id=None, agent_orch=None, limit=200, tenant_id=None) -> list[dict]:
        where, args = [], []
        for col, v in (("proc_inst_id", proc_inst_id), ("status", status), ("user_id", user_id), ("agent_orch", agent_orch), ("tenant_id", tenant_id)):
            if v is not None:
                where.append(f"{col} = %s")
                args.append(v)
        sql = "select * from todolist" + (" where " + " and ".join(where) if where else "") + " order by start_date limit %s"
        with self._conn() as c:
            return [self._row(r) for r in c.execute(sql, args + [limit]).fetchall()]

    # ---- worker RPCs (names and arguments of the product's function.sql)
    def fetch_pending_task(self, agent_orch: str | None, consumer: str, limit: int = 1, tenant_id: str | None = None, proc_inst_id: str | None = None) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute(
                "select * from claim_process_workitems(%s,%s,%s,%s,%s,'worker')",
                (consumer,limit,tenant_id,proc_inst_id,agent_orch)).fetchall()]

    def save_task_result(self, todo_id: str, payload: dict, final: bool, expected_consumer: str | None = None) -> bool:
        with self._workitem_connection(todo_id) as c:
            if expected_consumer is None:
                c.execute("select save_task_result(%s, %s, %s)", (todo_id,self._Jsonb(payload),final))
                return True
            return c.execute("""update todolist set
                output=case when %s and agent_mode='COMPLETE' then %s else output end,
                draft=case when not %s or agent_mode is distinct from 'COMPLETE' then %s else draft end,
                status=case when %s and agent_mode='COMPLETE' then 'SUBMITTED'::todo_status else status end,
                draft_status=case when %s then 'COMPLETED'::draft_status else draft_status end,
                consumer=case when %s then null else consumer end
                where id=%s and consumer=%s and status='IN_PROGRESS' and draft_status='STARTED'
                returning id""",(final,self._Jsonb(payload),final,self._Jsonb(payload),final,final,final,todo_id,expected_consumer)).fetchone() is not None

    def update_task_error(self, todo_id: str, expected_consumer: str | None = None) -> bool:
        return self.set_draft_status(todo_id,"FAILED",expected_consumer=expected_consumer)

    def set_draft_status(self, todo_id: str, draft_status: str | None, consumer: str | None = None, expected_consumer: str | None = None) -> bool:
        with self._workitem_connection(todo_id) as c:
            return c.execute("""update todolist set draft_status=%s,consumer=%s where id=%s
                and (%s::text is null or (consumer=%s and status='IN_PROGRESS' and draft_status='STARTED'))
                returning id""",(draft_status,consumer,todo_id,expected_consumer,expected_consumer)).fetchone() is not None

    def release_worker_claim(self,todo_id: str,consumer: str) -> bool:
        with self._workitem_connection(todo_id) as c:
            return c.execute('update todolist set consumer=null where id=%s and consumer=%s returning id',
                             (todo_id,consumer)).fetchone() is not None

    def renew_task_lease(self, todo_id: str, consumer: str, seconds: int = LEASE_SECONDS) -> bool:
        with self._conn() as c:
            return bool(c.execute("select renew_task_lease(%s,%s,%s)", (todo_id, consumer, seconds)).fetchone()["renew_task_lease"])

    def clear_task_lease(self, todo_id: str, consumer: str) -> bool:
        # A143: parent first like every other todolist write (the child UPDATE trigger writes the parent; a direct UPDATE
        # deadlocked against an engine transition holding the instance — .evidence/a143/lease_lock_order.json)
        with self._workitem_connection(todo_id) as c:
            return c.execute("update todolist set lease_until = null where id = %s and consumer = %s", (todo_id, consumer)).rowcount == 1

    def expire_worker_leases(self, max_claims: int = MAX_CLAIMS) -> int:
        with self._conn() as c:
            return int(c.execute("select expire_worker_leases(%s)", (max_claims,)).fetchone()["expire_worker_leases"])

    # ---- engine claim
    def claim_submitted(self, consumer: str, limit: int = 10, tenant_id: str | None = None) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute(
                "select * from claim_process_workitems(%s,%s,%s,null,null,'engine')",
                (consumer,limit,tenant_id)).fetchall()]

    def cleanup_stale_consumers(self, minutes: int = STALE_MINUTES) -> int:
        with self._conn() as c:
            return int(c.execute("select cleanup_stale_consumers(%s)", (minutes,)).fetchone()["cleanup_stale_consumers"])

    # ---- events · notifications
    def record_events(self, events: list[dict]) -> None:
        if not events:
            return
        with self._conn() as c:
            c.execute("select record_events_bulk(%s)", (self._Jsonb([dict(e, id=e.get("id") or str(uuid.uuid4())) for e in events]),))

    def insert_event(self, evt: dict) -> None:
        self.record_events([evt])

    def list_events(self, proc_inst_id=None, todo_id=None, limit=500) -> list[dict]:
        where, args = [], []
        if proc_inst_id is not None:
            where.append("proc_inst_id = %s"); args.append(proc_inst_id)
        if todo_id is not None:
            where.append("todo_id = %s"); args.append(todo_id)
        # A161-U1: the newest `limit` rows, oldest first (MemoryRepo's rows[-limit:]). It returned the OLDEST rows, so a long
        # agent run (hundreds of usage rows) cut the newest tool calls out of the instance view and the screen stopped moving.
        sql = ("select * from (select * from events" + (" where " + " and ".join(where) if where else "")
               + " order by timestamp desc, id desc limit %s) x order by timestamp, id")
        with self._conn() as c:
            return [self._row(r) for r in c.execute(sql, args + [limit]).fetchall()]

    def list_events_since(self, since=None, limit=300) -> list[dict]:
        with self._conn() as c:
            if since is None:
                rows = c.execute("select * from (select * from events order by timestamp desc, id desc limit %s) x order by timestamp, id", (limit,)).fetchall()
            else:
                rows = c.execute("select * from events where timestamp >= %s::timestamptz order by timestamp, id limit %s", (since, limit)).fetchall()
            return [self._row(r) for r in rows]

    def find_task_event(self, todo_id, job_id, event_type):
        with self._conn() as c:
            row=c.execute('''select * from events where todo_id=%s and job_id=%s and event_type=%s
                order by timestamp desc limit 1''',(todo_id,job_id,event_type)).fetchone()
            return self._row(row) if row else None

    def insert_notification(self, note: dict) -> dict:
        with self._conn() as c:
            return self._row(c.execute("insert into notifications (title, type, description, user_id, tenant_id, url, from_user_id) "
                                       "values (%s, %s, %s, %s, %s, %s, %s) returning *",
                      (note.get("title"), note.get("type"), note.get("description"), note.get("user_id"), note.get("tenant_id", "hyd"),
                       note.get("url"), note.get("from_user_id"))).fetchone())

    # ---- U5 inbox: 업무분장 · 담당자 이력 · 사용자별 알림 (migration 000029)
    def list_role_members(self, tenant_id: str, role_id: str | None = None) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("select * from role_members where tenant_id=%s and (%s::text is null or role_id=%s) order by role_id, user_id",
                                                    (tenant_id, role_id, role_id)).fetchall()]

    def set_role_member(self, tenant_id: str, role_id: str, user_id: str, member: bool) -> None:
        with self._conn() as c:
            if member:
                c.execute("insert into role_members (tenant_id, role_id, user_id) values (%s,%s,%s) on conflict do nothing", (tenant_id, role_id, user_id))
            else:
                c.execute("delete from role_members where tenant_id=%s and role_id=%s and user_id=%s", (tenant_id, role_id, user_id))

    def insert_assignment(self, row: dict) -> dict:
        with self._conn() as c:
            return self._row(c.execute("insert into task_assignments (tenant_id, proc_inst_id, todo_id, from_user_id, to_user_id, kind, by_user, reason) "
                                       "values (%s,%s,%s,%s,%s,%s,%s,%s) returning *",
                                       (row.get("tenant_id", "hyd"), row["proc_inst_id"], row["todo_id"], row.get("from_user_id"), row["to_user_id"], row["kind"],
                                        row.get("by_user"), row.get("reason"))).fetchone())

    def list_assignments(self, todo_id: str, tenant_id: str) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("select * from task_assignments where todo_id=%s and tenant_id=%s order by created_at, id",
                                                    (todo_id, tenant_id)).fetchall()]

    def list_notifications(self, tenant_id, user_ids, unread_only=False, limit=100) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("select * from notifications where tenant_id=%s and user_id = any(%s) and (not %s or not is_read) "
                                                    "order by created_at desc, id desc limit %s", (tenant_id, list(user_ids), unread_only, limit)).fetchall()]

    def count_unread_notifications(self, tenant_id, user_ids) -> int:
        with self._conn() as c:
            return int(c.execute("select count(*) as n from notifications where tenant_id=%s and user_id = any(%s) and not is_read",
                                 (tenant_id, list(user_ids))).fetchone()["n"])

    def mark_notifications_read(self, tenant_id, user_ids, ids=None) -> int:
        with self._conn() as c:
            return c.execute("update notifications set is_read=true where tenant_id=%s and user_id = any(%s) and not is_read "
                             "and (%s::uuid[] is null or id = any(%s::uuid[]))", (tenant_id, list(user_ids), ids, ids)).rowcount

    def list_notifications_since(self, since=None, limit=300, tenant_id=None, user_ids=None) -> list[dict]:
        scope = "(%s::text is null or tenant_id=%s) and (%s::text[] is null or user_id = any(%s::text[]))"
        args = (tenant_id, tenant_id, user_ids, user_ids)
        with self._conn() as c:
            if since is None:
                rows = c.execute(f"select * from (select * from notifications where {scope} order by created_at desc, id desc limit %s) x "
                                 "order by created_at, id", (*args, limit)).fetchall()
            else:
                rows = c.execute(f"select * from notifications where {scope} and created_at >= %s::timestamptz order by created_at, id limit %s",
                                 (*args, since, limit)).fetchall()
            return [self._row(r) for r in rows]

    def agent_task_origins(self, proc_inst_id: str, tenant_id: str) -> list[str]:
        with self._conn() as c:
            return [r['job_id'] or '' for r in c.execute(
                "select distinct e.job_id from events e join bpm_proc_inst p on p.proc_inst_id=e.proc_inst_id "
                "where p.proc_inst_id=%s and p.tenant_id=%s and e.event_type='task_started'",
                (proc_inst_id, tenant_id)).fetchall()]

    def ping(self) -> bool:
        try:
            with self._conn() as c:
                c.execute("select 1")
            return True
        except Exception:  # noqa: BLE001
            return False


def make_repo() -> Repo:
    """PROCESS_REPO=memory (tests, no DB) | pg (default — Supabase)."""
    return MemoryRepo() if os.getenv("PROCESS_REPO", "pg") == "memory" else PgRepo()
