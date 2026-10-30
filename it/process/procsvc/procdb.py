"""Persistence of definitions, instances, work items and events in the ProcessGPT-shaped tables (Supabase/Postgres).

PgRepo — psycopg 3 against the Supabase Postgres (it/supabase/migrations/20261003000001_process_engine.sql). 학생 PC 의 구성은
이것 하나다(메모리 저장소 판은 2026-10-30 지움 — 원천 접수 · 임대 · 투영 대기열이 모두 PostgreSQL 행이라 실행 서비스에서 쓸 수 없었다).

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

import os
import socket
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Protocol
from .approval_store import PgApprovals
from .rework_store import PgReworks
from .effect_store import PgEffects
from .projection_repo import PgProjection
from .agents_store import PgAgents          # U2: tenant skills · agent ↔ skill (read side)
from .agent_authoring import PgAuthoring    # B1: 에이전트 · 스킬 · 배정 쓰기 + 되돌리기
from .effect_parts import TOOLS as C2_SERVICE_TOOLS

#: process 가 다시 돌려 보는 서비스 줄(멱등 처리기만): 사건 경로 · CMMS 작업지시 + C2 승인 뒤 실행 부품(기다리는 부품은 끝날 때까지 여기서 다시 본다)
SERVICE_QUEUE_TOOLS = ('incident:command', 'incident:reobserve', 'enterprise:WO_CREATE', *C2_SERVICE_TOOLS)

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
# P9 (audit2 2026-10-23, 사용자 결정): 수업 흐름 표시. 수업 흐름 설치(course_bootstrap — 시작.bat)가 배포할 때(class_flow=True) 운영 포인터 머리
# proc_def.owner 에 이 값을 남긴다 — 지금 배포의 주인이 '수업'이라는 뜻이다. 다른 배포 · 되돌리기 · 내리기는 owner 를 비운다(마지막 배포 행위가 정한다).
# 포털의 [기준 흐름으로 되돌리기]는 이 표시가 있는 흐름을 남긴다. 흐름 id 접두어(c3_*)로 짐작하지 않는다. proc_def_deployment 는 action 에
# 검사 제약이 있고 칸이 고정이라(마이그레이션 000044) 지금 표 구조 그대로 쓰는 머리의 owner 칸(000001, 이 서비스가 쓰지 않던 칸)에 둔다.
CLASS_OWNER = "class"
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
    def record_deployment(self, def_id: str, version: str, tenant_id: str, *, action: str, actor: str, reason: str,
                          class_flow: bool = False) -> dict: ...
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
    def find_active_coalesced_instance(self, tenant_id: str, def_id: str, key: str) -> dict | None: ...
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
    def waiting_services(self, tenant_id: str, now: datetime, after_id: str | None = None, limit: int = 100) -> list[dict]: ...
    def find_event_instance(self, tenant_id: str, def_id: str, event_id: str) -> dict | None: ...
    def insert_instance(self, inst: dict) -> None: ...
    def update_instance(self, inst: dict) -> None: ...
    def get_instance(self, proc_inst_id: str) -> dict | None: ...
    def list_instances(self, status: str | None = None, limit: int = 100, tenant_id: str | None = None, incident_id: str | None = None,
                       asset: str | None = None) -> list[dict]: ...
    def list_source_runs(self, tenant_id, def_id, event_prefix, limit=51, offset=0) -> list[dict]: ...
    def hide_instances(self, tenant_id, def_id, ids) -> int: ...   # B5: finished instances of one definition → is_deleted (rows kept)
    # work items
    def insert_workitems(self, items: list[dict]) -> None: ...
    def update_workitem(self, item: dict) -> None: ...
    def get_workitem(self, wid: str) -> dict | None: ...
    # newest=True: 자를 때 최신 start_date 쪽을 남긴다(돌려주는 순서는 그대로 오래된 것부터). 기본은 전처럼 오래된 것부터 자른다
    def list_workitems(self, proc_inst_id: str | None = None, status: str | None = None, user_id: str | None = None,
                       agent_orch: str | None = None, limit: int = 200, tenant_id: str | None = None, newest: bool = False) -> list[dict]: ...
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
    def record_service_progress(self, tenant_id: str, proc_inst_id: str, todo_id: str, consumer: str, events: list[dict]) -> None: ...
    def find_task_event(self, todo_id: str, job_id: str, event_type: str) -> dict | None: ...
    # A161-G4: `before` = an event id (keyset cursor): the newest `limit` rows strictly older than that event, oldest first.
    # A cursor that is not an event of the same filter raises LookupError — an empty page would read as "no older rows"
    def list_events(self, proc_inst_id: str | None = None, todo_id: str | None = None, limit: int = 500, before: str | None = None) -> list[dict]: ...
    def list_events_since(self, since: str | None = None, limit: int = 300) -> list[dict]: ...   # A091 live stream cursor
    # A161-G2: full tool results too large for an events row (migration 20261009000048), one row per (case, content sha256)
    def store_event_payload(self, payload: dict) -> None: ...
    def get_event_payload(self, payload_id: str) -> dict | None: ...
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
                """select * from bpm_proc_inst where tenant_id=%s and proc_def_id=%s
                and (start_event_id=%s or exists (select 1 from jsonb_array_elements(variables_data) v
                    where v->>'key'='_runtime_coalescing' and (v->'value'->'events') ? %s))""",
                (tenant_id, def_id, event_id, event_id)).fetchone())

    def find_active_coalesced_instance(self, tenant_id: str, def_id: str, key: str) -> dict | None:
        with self._conn() as connection:
            return self._row(connection.execute('''select * from bpm_proc_inst
                where tenant_id=%s and proc_def_id=%s and status='RUNNING' and not is_deleted
                and variables_data @> %s''', (tenant_id,def_id,self._Jsonb([
                    {'key':'_runtime_coalescing','value':{'key':key}}]))).fetchone())

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

    def waiting_services(self, tenant_id: str, now: datetime, after_id: str | None = None, limit: int = 100) -> list[dict]:
        """process 가 이미 집었던(consumer 있음) 시스템 단계 중 다시 볼 차례인 행: 마감(due_date)이 없거나 지난 행만(B-2 — 기다리는 행을
        2초마다 다시 집어 담당 표식을 새로 쓰면 그래프 반영 대기열이 쌓였다). 마감 = ACK 마감 · 재관측 창 · 대기 부품의 끝 시각."""
        with self._conn() as c:
            return [self._row(w) for w in c.execute("""select w.* from todolist w join bpm_proc_inst i using(proc_inst_id)
                where w.tenant_id=%s and i.tenant_id=%s and i.status='RUNNING' and not i.is_deleted
                and w.status='SUBMITTED' and w.agent_orch='hyd-process' and w.consumer is not null
                and coalesce(w.output,'{}'::jsonb)='{}'::jsonb
                and w.tool = any(%s) and (w.due_date is null or w.due_date<=%s)
                and (%s::uuid is null or w.id>%s::uuid) order by w.id limit %s""",
                (tenant_id,tenant_id,list(SERVICE_QUEUE_TOOLS),now,after_id,after_id,limit)).fetchall()]

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

    def record_deployment(self, def_id: str, version: str, tenant_id: str, *, action: str, actor: str, reason: str,
                          class_flow: bool = False) -> dict:
        with self._conn() as c, c.transaction():
            head = c.execute("select prod_version from proc_def where id=%s and tenant_id=%s and isdeleted=false for update",
                             (def_id, tenant_id)).fetchone()
            known = c.execute("""select 1 from proc_def_version where tenant_id=%s and proc_def_id=%s and version=%s
                                 and version_tag='hyd-immutable'""", (tenant_id, def_id, version)).fetchone()
            if head is None or known is None:
                raise LookupError(f'등록되지 않은 정의 판본입니다: {def_id}@{version}')
            c.execute("update proc_def set prod_version=%s, owner=%s, updated_at=now() where id=%s and tenant_id=%s and isdeleted=false",
                      (version, CLASS_OWNER if class_flow else None, def_id, tenant_id))
            row = c.execute("""insert into proc_def_deployment (tenant_id, proc_def_id, version, previous_version, action, actor, reason)
                               values (%s,%s,%s,%s,%s,%s,%s) returning *""",
                            (tenant_id, def_id, version, head['prod_version'], action, actor, reason)).fetchone()
            return dict(self._row(row), class_flow=bool(class_flow))

    def list_deployments(self, def_id: str, tenant_id: str = "hyd", limit: int = 50) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("""select * from proc_def_deployment where tenant_id=%s and proc_def_id=%s
                order by created_at desc, id desc limit %s""", (tenant_id, def_id, limit)).fetchall()]

    def deployed_heads(self, tenant_id: str = "hyd") -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("""select d.id, d.prod_version, x.created_at as deployed_at, x.action as last_action,
                    x.actor as deployed_by, coalesce(d.owner = %s, false) as class_flow
                from proc_def d left join lateral (select created_at, action, actor from proc_def_deployment y
                    where y.tenant_id=d.tenant_id and y.proc_def_id=d.id order by y.created_at desc, y.id desc limit 1) x on true
                where d.tenant_id=%s and not d.isdeleted and d.prod_version is not null
                order by x.created_at desc nulls last, d.id desc""", (CLASS_OWNER, tenant_id)).fetchall()]

    def clear_deployment(self, def_id: str, tenant_id: str, *, actor: str, reason: str) -> dict:
        with self._conn() as c, c.transaction():
            head = c.execute("select prod_version from proc_def where id=%s and tenant_id=%s and isdeleted=false for update",
                             (def_id, tenant_id)).fetchone()
            if head is None or not head['prod_version']:
                raise LookupError(f'배포된 판본이 없는 정의입니다: {def_id}')
            c.execute("update proc_def set prod_version=null, owner=null, updated_at=now() where id=%s and tenant_id=%s and isdeleted=false",
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

    def list_instances(self, status: str | None = None, limit: int = 100, tenant_id: str | None = None, incident_id: str | None = None,
                       asset: str | None = None) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("""select * from bpm_proc_inst where is_deleted=false
                    and (%s::text is null or status::text=%s) and (%s::text is null or tenant_id=%s)
                    and (%s::text is null or variables_data @> %s::jsonb)
                    and (%s::text is null or variables_data @> %s::jsonb)
                    order by start_date desc limit %s""", (status,status,tenant_id,tenant_id,incident_id,
                        self._Jsonb([{'key':'incident','value':incident_id}]),asset,self._Jsonb([{'key':'asset','value':asset}]),limit)).fetchall()
            return [self._row(r) for r in rows]

    def list_source_runs(self, tenant_id, def_id, event_prefix, limit=51, offset=0, cache_prefix=None):
        with self._conn() as c:
            return [self._row(r) for r in c.execute('''select proc_inst_id,status,start_date,end_date from bpm_proc_inst
                where tenant_id=%s and proc_def_id=%s and is_deleted=false and
                (left(start_event_id,%s)=%s or (%s <> '' and left(start_event_id,%s)=%s))
                order by start_date desc,proc_inst_id desc limit %s offset %s''',
                (tenant_id,def_id,len(event_prefix),event_prefix,cache_prefix or '',len(cache_prefix or ''),
                 cache_prefix or '',limit,offset)).fetchall()]

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

    def list_workitems(self, proc_inst_id=None, status=None, user_id=None, agent_orch=None, limit=200, tenant_id=None, newest=False) -> list[dict]:
        where, args = [], []
        for col, v in (("proc_inst_id", proc_inst_id), ("status", status), ("user_id", user_id), ("agent_orch", agent_orch), ("tenant_id", tenant_id)):
            if v is not None:
                where.append(f"{col} = %s")
                args.append(v)
        sql = "select * from todolist" + (" where " + " and ".join(where) if where else "")
        sql = (f"select * from ({sql} order by start_date desc limit %s) newest order by start_date" if newest
               else sql + " order by start_date limit %s")
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
    def record_service_progress(self, tenant_id, proc_inst_id, todo_id, consumer, events):
        """Only the observation journal uses its own transaction; no business flush."""
        from . import service_progress as progress
        progress.validate_rows(events, proc_inst_id, todo_id)
        # Deliberately bypass _conn(): it reuses the locked business connection.
        with self._psycopg.connect(self.dsn, connect_timeout=5, row_factory=self._dict_row) as c:
            c.execute("set local statement_timeout='5000ms'")
            inst = c.execute('select proc_inst_id,tenant_id,status,is_deleted from bpm_proc_inst where proc_inst_id=%s', (proc_inst_id,)).fetchone()
            wi = c.execute('select id,proc_inst_id,tenant_id,status,agent_orch,user_id,consumer from todolist where id=%s', (todo_id,)).fetchone()
            for row in events:
                if row['job_id'] in ('SYSTEM_ATTEMPT_COMMITTED', 'SYSTEM_ATTEMPT_ROLLED_BACK'):
                    start = c.execute("select data from events where proc_inst_id=%s and todo_id=%s and event_type='tool_usage_started' and data->>'attempt_id'=%s order by timestamp limit 1", (proc_inst_id, todo_id, row['data']['attempt_id'])).fetchone()
                    progress.require_closure(inst, wi, start, tenant_id, proc_inst_id, todo_id, consumer, row)
                else:
                    progress.require_owner(inst, wi, tenant_id, proc_inst_id, todo_id, consumer)
            c.execute('select record_events_bulk(%s)', (self._Jsonb(events),))

    def record_events(self, events: list[dict]) -> None:
        if not events:
            return
        with self._conn() as c:
            c.execute("select record_events_bulk(%s)", (self._Jsonb([dict(e, id=e.get("id") or str(uuid.uuid4())) for e in events]),))

    def insert_event(self, evt: dict) -> None:
        self.record_events([evt])

    def list_events(self, proc_inst_id=None, todo_id=None, limit=500, before=None) -> list[dict]:
        where, args = [], []
        if proc_inst_id is not None:
            where.append("proc_inst_id = %s"); args.append(proc_inst_id)
        if todo_id is not None:
            where.append("todo_id = %s"); args.append(todo_id)
        if before is not None:
            # A161-G4: keyset cursor on (timestamp, id) — the same order the page is read in, so no row is skipped or repeated
            # when rows arrive between two page reads (offset paging would shift). The cursor must be an event of this filter.
            with self._conn() as c:
                cursor = c.execute("select timestamp, id from events where id = %s" + "".join(" and " + w for w in where),
                                   [before] + args).fetchone()
            if cursor is None:
                raise LookupError(f"events cursor '{before}' is not an event of this case")
            where.append("(timestamp, id) < (%s, %s)"); args += [cursor["timestamp"], cursor["id"]]
        # A161-U1: the newest `limit` rows, oldest first (newest page, oldest first). It returned the OLDEST rows, so a long
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

    def store_event_payload(self, payload: dict) -> None:
        with self._conn() as c:
            c.execute("""insert into event_payloads (id, content, chars, content_type, source, tool, tool_use_id, job_id, todo_id, proc_inst_id, meta)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (id) do nothing""",
                      (payload["id"], payload["content"], payload.get("chars"), payload.get("content_type"), payload.get("source"),
                       payload.get("tool"), payload.get("tool_use_id"), payload.get("job_id"), payload.get("todo_id"),
                       payload.get("proc_inst_id"), self._Jsonb(payload.get("meta") or {})))

    def list_stream_events(self, since=None, limit=300):
        # Separate short publication transaction: no uncommitted source event can
        # acquire a cursor. Serialize publishers so positions also commit in order.
        with self._psycopg.connect(self.dsn, row_factory=self._dict_row, connect_timeout=5) as c:
            c.execute("select pg_advisory_xact_lock(hashtextextended('hyd:event-stream-publication',0))")
            c.execute('''insert into event_stream_positions(event_id)
                select e.id from events e where not exists
                (select 1 from event_stream_positions s where s.event_id=e.id)
                order by e.timestamp,e.id on conflict (event_id) do nothing''')
            base = "select e.*, 's:' || lpad(s.position::text,20,'0') as stream_cursor from event_stream_positions s join events e on e.id=s.event_id"
            if since is None:
                rows = c.execute('select * from (' + base + ' order by s.position desc limit %s) q order by stream_cursor', (limit,)).fetchall()
            elif str(since).startswith('s:'):
                rows = c.execute(base + ' where s.position >= %s order by s.position limit %s', (int(since[2:]), limit)).fetchall()
            else:  # Existing browsers can reconnect once with their old timestamp.
                rows = c.execute(base + ' where e.timestamp >= %s::timestamptz order by s.position limit %s', (since, limit)).fetchall()
            return [self._row(r) for r in rows]

    def get_event_payload(self, payload_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("select * from event_payloads where id = %s", (payload_id,)).fetchone()
            return self._row(row) if row else None

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

