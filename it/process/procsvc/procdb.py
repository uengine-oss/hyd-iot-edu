"""Persistence of definitions, instances, work items and events in the ProcessGPT-shaped tables (Supabase/Postgres).

PgRepo — psycopg 3 against the Supabase Postgres (it/supabase/migrations/20261003000001_process_engine.sql). 학생 PC 의 구성은
이것 하나다(메모리 저장소 판은 2026-10-30 지움 — 원천 접수 · 임대 · 투영 대기열이 모두 PostgreSQL 행이라 실행 서비스에서 쓸 수 없었다).

The repo is deliberately thin: SQL only, no business rules. Which work items exist and what state they are in is the
engine's decision (engine.py); here they are written down. The product's RPC names are kept so the lecture can point at
them, but what runs is HYD's own lock-ordered SQL (migration 000004): the worker claim is
claim_process_workitems(…,'worker') with tenant/instance filters (fetch_pending_task is a thin wrapper of it), the
engine claim claim_process_workitems(…,'engine') (claim_submitted_workitems wrapper), results are saved by a conditional
UPDATE on the expected consumer, leases by renew_task_lease / clear_task_lease, the worker sweep by expire_worker_leases.
엔진이 집은 행은 엔진이 바퀴마다 놓는다(release_engine_claims). Every work-item write locks the parent instance first
(_workitem_connection), including lease renew/clear (A143).
"""
from __future__ import annotations

import os
import socket
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
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
# P9 (audit2 2026-10-23, 사용자 결정): 수업 흐름 표시. 수업 흐름 설치(course_bootstrap — 시작.bat)가 배포할 때(class_flow=True) 운영 포인터 머리
# proc_def.owner 에 이 값을 남긴다 — 지금 배포의 주인이 '수업'이라는 뜻이다. 다른 배포 · 되돌리기 · 내리기는 owner 를 비운다(마지막 배포 행위가 정한다).
# 포털의 [기준 흐름으로 되돌리기]는 이 표시가 있는 흐름을 남긴다. 흐름 id 접두어(c3_*)로 짐작하지 않는다. proc_def_deployment 는 action 에
# 검사 제약이 있고 칸이 고정이라(마이그레이션 000044) 지금 표 구조 그대로 쓰는 머리의 owner 칸(000001, 이 서비스가 쓰지 않던 칸)에 둔다.
CLASS_OWNER = "class"
LEASE_SECONDS = 120      # A097: a worker claim lives this long unless renewed (agent-sdk lease.py: 120 s, renew every 30 s)
MAX_CLAIMS = 3           # A097: after the third expired lease the row is FAILED for a person to close (agent-sdk max_claims)


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

    def add_coalesced_event(self, proc_inst_id: str, key: str, event_id: str, limit: int = 100) -> dict | None:
        """같은 질문 다시 보내기(P1-02): 진행 중 처리 건의 행을 잠그고 다시 읽어 `_runtime_coalescing.events` 에 요청 id 하나만 더한다 —
        variables_data 한 칸만 쓴다(다른 칸은 그대로). 그 사이 처리 건이 끝났으면 None(호출자가 새 처리 건을 연다). 한도를 넘으면 ValueError."""
        with self._conn() as c:
            row = c.execute("select * from bpm_proc_inst where proc_inst_id=%s for update", (proc_inst_id,)).fetchone()
            if not row or row['status'] != 'RUNNING' or row['is_deleted']:
                return None
            variables = row['variables_data'] or []
            binding = next((v['value'] for v in variables if isinstance(v, dict) and v.get('key') == '_runtime_coalescing'), None)
            if not isinstance(binding, dict) or binding.get('key') != key:
                return None
            if len(binding.get('events') or []) >= limit:
                raise ValueError(f'같은 질문을 {limit}번 넘게 다시 보냈습니다 — 앞 질문의 답을 기다리거나 새 질문으로 보내세요')
            binding['events'] = list(binding.get('events') or []) + [event_id]
            c.execute("update bpm_proc_inst set variables_data=%s where proc_inst_id=%s", (self._Jsonb(variables), proc_inst_id))
            return self._row(dict(row, variables_data=variables))

    @contextmanager
    def read_snapshot(self):
        """한 시점의 읽기 전용 스냅숏(REPEATABLE READ READ ONLY) — 그 안의 읽기가 모두 같은 시점을 본다. 잠금은 잡지 않는다(P1-04: 미리보기가
        바깥 응답을 기다리는 동안 같은 처리 건의 쓰기를 막지 않게). 안에서 쓰면 DB 가 거절한다."""
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("nested storage transaction; a snapshot opens its own")
        with self._psycopg.connect(self.dsn, connect_timeout=5, row_factory=self._dict_row) as c:
            c.execute("set transaction isolation level repeatable read read only")
            self._local.connection = c
            try:
                yield
            finally:
                del self._local.connection

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
        """정의마다 판본을 오래된 판본부터(version_key — 숫자는 수로, P3-13: 글자 순이면 '10' 이 '9' 보다 앞이라 10판부터 9판을 최신으로 봤다).
        정의마다 마지막 행이 그 정의의 최신 판본이다."""
        with self._conn() as c:
            rows = [self._row(r) for r in c.execute("""select proc_def_id as id,tenant_id,version as prod_version,
                definition->>'processDefinitionName' as name,definition,message,"timeStamp" as registered_at from proc_def_version
                where tenant_id=%s and version_tag='hyd-immutable'""", (tenant_id,)).fetchall()]
        return sorted(rows, key=lambda r: (r['id'], version_key(r['prod_version'])))

    def registered_versions(self, tenant_id: str = "hyd") -> list[tuple[str, str]]:
        """등록된 (정의 id, 판본) — 원문 없이(지운 흐름 정리가 그래프와 대조한다)."""
        with self._conn() as c:
            return [(r['proc_def_id'], r['version']) for r in c.execute(
                "select proc_def_id, version from proc_def_version where tenant_id=%s and version_tag='hyd-immutable'", (tenant_id,)).fetchall()]

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
                raise LookupError(f'판본 {version}이(가) 등록돼 있지 않습니다(흐름 id {def_id} — 배포하는 사이에 지워졌을 수 있습니다)')
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
        # 지워졌거나 끝난 처리 건도 그 사건의 주인이다 — 처리 건 밖에서 그 사건에 새 판단을 붙이지 않는다(main._create_decision).
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

    def list_source_runs(self, tenant_id, def_id, event_prefix, limit=51, offset=0, cache_prefix=None, status=None, exclude_def=None):
        """시작 요청 id(start_event_id)의 앞부분으로 고른 처리 건(최신부터, 변수 없이 요약 칸만). def_id=None 이면 모든 정의,
        status 를 주면 그 상태만, exclude_def 를 주면 그 정의는 빼고(시나리오 버튼 상태가 「이 버튼 경보로 연 처리 건」을 처리 건 전부를
        변수째 읽지 않고 고른다 — P4-05)."""
        with self._conn() as c:
            return [self._row(r) for r in c.execute('''select proc_inst_id,proc_def_id,status,start_date,end_date,end_event
                from bpm_proc_inst
                where tenant_id=%s and (%s::text is null or proc_def_id=%s) and (%s::text is null or proc_def_id<>%s)
                and is_deleted=false and (%s::text is null or status::text=%s) and
                (left(start_event_id,%s)=%s or (%s <> '' and left(start_event_id,%s)=%s))
                order by start_date desc,proc_inst_id desc limit %s offset %s''',
                (tenant_id,def_id,def_id,exclude_def,exclude_def,status,status,len(event_prefix),event_prefix,cache_prefix or '',
                 len(cache_prefix or ''),cache_prefix or '',limit,offset)).fetchall()]

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

    def stuck_workitems(self, tenant_id: str, proc_inst_ids: list[str]) -> list[dict]:
        """처리 건들의 멈춘 단계 후보(PENDING, 또는 진행 중인데 실행이 실패 · 취소됨) — 처리 건 목록이 한 질의로 읽는다."""
        if not proc_inst_ids:
            return []
        with self._conn() as c:
            return [self._row(r) for r in c.execute("""select id, proc_inst_id, activity_id, activity_name, status, draft_status, draft, tool,
                agent_orch from todolist where tenant_id=%s and proc_inst_id = any(%s)
                and (status='PENDING' or (status='IN_PROGRESS' and draft_status in ('FAILED','CANCELLED')))
                order by start_date""", (tenant_id, list(proc_inst_ids))).fetchall()]

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

    def save_task_result(self, todo_id: str, payload: dict, final: bool, expected_consumer: str) -> bool:
        """워커 결과 저장 — 그 행을 집은 워커(expected_consumer)만 쓸 수 있다(다른 워커 · 늦은 실행의 결과는 False)."""
        if not expected_consumer:
            raise ValueError('워커 결과는 그 작업을 집은 워커 이름(expected_consumer)과 함께 저장합니다')
        with self._workitem_connection(todo_id) as c:
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
        # deadlocked against an engine transition holding the instance — A143 — git 4947e366 의 교착 재현)
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

    def release_engine_claims(self, consumer: str, tenant_id: str) -> int:
        """이 엔진(consumer)이 집어 둔 채 남은 제출 행을 놓는다 — 엔진은 하나이고 집은 행을 같은 폴링 바퀴 안에서 처리하므로, 바퀴 처음에 이
        이름으로 남은 행은 지난 바퀴 · 지난 기동이 처리 도중 끊긴 것이다(P1-05). 시스템 단계의 실행 표식(…:service:…)과 승인 전달 대기
        (approval:waiting)는 각자의 정리(waiting_services · reconcile_approvals)가 다루므로 건드리지 않는다. 돌려줌 = 놓은 행 수."""
        with self._conn() as c:
            parents = [r['proc_inst_id'] for r in c.execute(
                """select distinct proc_inst_id from todolist where tenant_id=%s and status='SUBMITTED' and consumer=%s""",
                (tenant_id, consumer)).fetchall()]
        released = 0
        for pid in parents:                    # 부모 먼저 잠그는 순서(_workitem_connection 과 같다) — 처리 건마다 짧은 트랜잭션
            with self._conn() as c, c.transaction():
                c.execute('select 1 from bpm_proc_inst where proc_inst_id=%s for update', (pid,)).fetchone()
                released += c.execute("""update todolist set consumer=null where proc_inst_id=%s and status='SUBMITTED' and consumer=%s""",
                                      (pid, consumer)).rowcount
        return released

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

    def store_event_payload(self, payload: dict) -> None:
        with self._conn() as c:
            c.execute("""insert into event_payloads (id, content, chars, content_type, source, tool, tool_use_id, job_id, todo_id, proc_inst_id, meta)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (id) do nothing""",
                      (payload["id"], payload["content"], payload.get("chars"), payload.get("content_type"), payload.get("source"),
                       payload.get("tool"), payload.get("tool_use_id"), payload.get("job_id"), payload.get("todo_id"),
                       payload.get("proc_inst_id"), self._Jsonb(payload.get("meta") or {})))

    def list_stream_events(self, since=None, limit=300):
        """처리 기록 흐름(SSE)의 한 쪽. 위치는 커밋된 기록에만 따로 짧은 트랜잭션에서 매긴다(`publish_event_positions` — 마이그레이션 069 §11,
        자체 권고 잠금으로 매기는 쪽을 줄 세워 위치가 커밋 순서대로) — 늦게 커밋된 기록이 앞선 위치 뒤에 숨지 않는다.
        since: None(마지막 limit 건) 또는 앞서 받은 stream_cursor(`s:` + 위치 20자리, 그 위치부터 포함)."""
        if since is not None and not str(since).startswith('s:'):
            raise ValueError(f'처리 기록 흐름의 이어 받기 위치 {since!r}를 알 수 없습니다(s:로 시작하는 stream_cursor만 받습니다)')
        with self._psycopg.connect(self.dsn, row_factory=self._dict_row, connect_timeout=5) as c:
            c.execute('select public.publish_event_positions()')
            c.commit()
            base = "select e.*, 's:' || lpad(e.stream_position::text,20,'0') as stream_cursor from events e where e.stream_position is not null"
            if since is None:
                rows = c.execute('select * from (' + base + ' order by e.stream_position desc limit %s) q order by stream_cursor', (limit,)).fetchall()
            else:
                rows = c.execute(base + ' and e.stream_position >= %s order by e.stream_position limit %s', (int(since[2:]), limit)).fetchall()
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

    def insert_assignment(self, row: dict) -> dict:
        with self._conn() as c:
            return self._row(c.execute("insert into task_assignments (tenant_id, proc_inst_id, todo_id, from_user_id, to_user_id, kind, by_user, reason) "
                                       "values (%s,%s,%s,%s,%s,%s,%s,%s) returning *",
                                       (row.get("tenant_id", "hyd"), row["proc_inst_id"], row["todo_id"], row.get("from_user_id"), row["to_user_id"], row["kind"],
                                        row.get("by_user"), row.get("reason"))).fetchone())

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

    def ping(self) -> bool:
        try:
            with self._conn() as c:
                c.execute("select 1")
            return True
        except Exception:  # noqa: BLE001
            return False


def version_key(version: str) -> tuple:
    """판본 문자열의 순서 키: 점으로 나눈 조각마다 숫자는 수로, 글은 글로('2.10' > '2.9', '10' > '9'). 판본 순서는 이 함수 하나가 정한다."""
    return tuple((0, int(part), '') if part.isdigit() else (1, 0, part) for part in str(version).split('.'))
