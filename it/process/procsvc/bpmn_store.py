"""B3: 가져온 흐름의 저장 — 매핑 초안 · 학생 판본(그림 원본 포함) · 기준으로 되돌리기.

  초안   public.proc_bpmn_draft(tenant_id, proc_def_id, bpmn, file_name, mapping)  — 다시 가져오면 같은 id 의 매핑을 유지하는 원천
  판본   public.proc_def_version(..., snapshot = .bpmn 원본, origin = 'user', version_tag = 'hyd-immutable')
         public.proc_def(id, bpmn = 마지막으로 등록한 .bpmn 원본, origin = 'user')
         등록은 **운영 판본 포인터(proc_def.prod_version · definition)를 움직이지 않는다** — 배포는 B4.
  되돌리기  origin='user' 인 정의 · 판본 · 초안만 지운다. 기준 정의(origin 없음)는 그대로. 진행 중 처리 건이 학생 판본을 쓰면 거절.

제품 대조: process-gpt-vue3 ProcessGPTBackend.ts:573-685 putRawDefinition 은 proc_def.bpmn 과 proc_def_version.snapshot 에 XML 을
저장한다(같은 칸). 판본 번호는 HYD 규칙(학생 흐름마다 1, 2, 3 …, 같은 번호는 바꿀 수 없음).
"""
from __future__ import annotations

import re

ORIGIN = "user"


class FlowBusy(ValueError):
    """되돌리기를 막는 진행 중 처리 건."""
    def __init__(self, running: list[dict]):
        self.running = running
        names = ", ".join(f"「{r.get('proc_inst_name') or r['proc_def_id']}」(판본 {r['proc_def_version']}"
                          f"{', ' + str(r['start_date'])[:16].replace('T', ' ') + ' 시작' if r.get('start_date') else ''})" for r in running[:5])
        super().__init__(f"진행 중인 처리 건 {len(running)}건이 내가 가져온 흐름을 씁니다: {names} — [처리 건]에서 끝내거나 닫은 뒤 되돌리세요")


def next_version(existing: list[str]) -> str:
    nums = [int(v) for v in existing if re.fullmatch(r"\d+", str(v or ""))]
    return str(max(nums) + 1) if nums else "1"


#: 그 흐름 id 에 한 번이라도 쓰인 판본 번호 — 지금 판본 · 판본으로 연 처리 건(되돌리기가 숨긴 것 포함) · 배포 기록(되돌리기가 지우지 않는다).
#: 되돌리기 뒤 같은 번호를 다른 원문에 다시 쓰지 않는다(P5-24 — 숨긴 처리 건 · 받아 둔 그림 파일이 같은 번호의 다른 흐름을 가리키게 된다).
USED_VERSIONS_SQL = """select version from proc_def_version where tenant_id=%(t)s and proc_def_id=%(d)s
                       union select proc_def_version from bpm_proc_inst where tenant_id=%(t)s and proc_def_id=%(d)s
                       union select version from proc_def_deployment where tenant_id=%(t)s and proc_def_id=%(d)s and version is not null"""


class FlowStore:
    def __init__(self, repo, tenant_id: str):
        self.repo, self.tenant_id = repo, tenant_id

    # ------------------------------------------------------------ 보호
    def is_protected(self, def_id: str) -> bool:
        """기준(학생이 만든 것이 아닌) 정의 id 인가 — 그 id 로는 가져오지 않는다."""
        with self.repo._conn() as c:
            row = c.execute("""select exists(select 1 from proc_def_version where tenant_id=%s and proc_def_id=%s
                                   and coalesce(origin,'')<>'user')
                               or exists(select 1 from proc_def where tenant_id=%s and id=%s and coalesce(origin,'')<>'user') as p""",
                            (self.tenant_id, def_id, self.tenant_id, def_id)).fetchone()
            return bool(row["p"])

    # ------------------------------------------------------------ 초안(매핑)
    def get_draft(self, def_id: str) -> dict | None:
        with self.repo._conn() as c:
            return self.repo._row(c.execute("select proc_def_id, bpmn, file_name, mapping, updated_at from proc_bpmn_draft "
                                            "where tenant_id=%s and proc_def_id=%s", (self.tenant_id, def_id)).fetchone())

    def save_draft(self, def_id: str, bpmn: str, file_name: str | None, mapping: dict) -> None:
        with self.repo._conn() as c:
            c.execute("""insert into proc_bpmn_draft (tenant_id, proc_def_id, bpmn, file_name, mapping, updated_at)
                         values (%s,%s,%s,%s,%s,now())
                         on conflict (tenant_id, proc_def_id) do update set bpmn=excluded.bpmn, file_name=excluded.file_name,
                             mapping=excluded.mapping, updated_at=now()""",
                      (self.tenant_id, def_id, bpmn, file_name, self.repo._Jsonb(mapping)))

    def save_mapping(self, def_id: str, mapping: dict) -> None:
        with self.repo._conn() as c:
            n = c.execute("update proc_bpmn_draft set mapping=%s, updated_at=now() where tenant_id=%s and proc_def_id=%s",
                          (self.repo._Jsonb(mapping), self.tenant_id, def_id)).rowcount
            if not n:
                raise KeyError(f"가져온 그림이 없습니다: {def_id}")

    # ------------------------------------------------------------ 판본
    def versions(self, def_id: str | None = None) -> list[dict]:
        """학생 판본 목록 [{id, version, name, registered_at, file_name}] (오래된 것 먼저)."""
        with self.repo._conn() as c:
            rows = c.execute("""select proc_def_id as id, version, definition->>'processDefinitionName' as name,
                                       "timeStamp" as registered_at, message as file_name
                                from proc_def_version where tenant_id=%s and origin='user' and (%s::text is null or proc_def_id=%s)
                                order by proc_def_id, "timeStamp", version""", (self.tenant_id, def_id, def_id)).fetchall()
            return [self.repo._row(r) for r in rows]

    def next_version(self, def_id: str) -> str:
        """다음에 등록할 판본 번호(미리 보기) — 등록(register)이 자문 잠금 안에서 같은 규칙으로 다시 정한다."""
        with self.repo._conn() as c:
            return next_version([r["version"] for r in c.execute(USED_VERSIONS_SQL, {"t": self.tenant_id, "d": def_id}).fetchall()])

    def drafts(self) -> list[dict]:
        with self.repo._conn() as c:
            return [self.repo._row(r) for r in c.execute("select proc_def_id, file_name, mapping, updated_at from proc_bpmn_draft "
                                                         "where tenant_id=%s order by proc_def_id", (self.tenant_id,)).fetchall()]

    def register(self, raw: dict, bpmn: str, file_name: str | None) -> dict:
        """새 판본 번호를 정해 정의 + .bpmn 원본을 함께 넣는다. 운영 판본 포인터는 건드리지 않는다. 돌려줌: 넣은 정의(판본 포함)."""
        def_id = raw["processDefinitionId"]
        message = f"bpmn.io 가져오기: {file_name or '그림'}"
        with self.repo._conn() as c, c.transaction():
            c.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"b3-flow:{self.tenant_id}:{def_id}",))
            used = [r["version"] for r in c.execute(USED_VERSIONS_SQL, {"t": self.tenant_id, "d": def_id}).fetchall()]
            raw = dict(raw, version=next_version(used))
            inserted = c.execute("""insert into proc_def_version
                    (arcv_id, proc_def_id, version, version_tag, tenant_id, definition, snapshot, message, origin)
                    values (%s,%s,%s,'hyd-immutable',%s,%s,%s,%s,'user')
                    on conflict (tenant_id,proc_def_id,version) where version_tag='hyd-immutable' do nothing""",
                    (f"{def_id}_{raw['version']}", def_id, raw["version"], self.tenant_id, self.repo._Jsonb(raw), bpmn, message)).rowcount
            if not inserted:
                raise ValueError("이미 등록한 판본은 바꿀 수 없습니다")
            c.execute("""insert into proc_def (id, tenant_id, name, bpmn, type, origin, updated_at)
                         values (%s,%s,%s,%s,'bpmn','user',now())
                         on conflict (id, tenant_id) where isdeleted = false do update set bpmn=excluded.bpmn, name=excluded.name,
                             updated_at=now() where proc_def.origin='user'""",
                      (def_id, self.tenant_id, raw.get("processDefinitionName"), bpmn))
        return raw

    def bpmn_of(self, def_id: str, version: str | None = None) -> str | None:
        """판본의 그림 원본(.bpmn). version 이 없으면 proc_def.bpmn(마지막으로 등록한 그림)."""
        with self.repo._conn() as c:
            if version is None:
                row = c.execute("select bpmn from proc_def where tenant_id=%s and id=%s and isdeleted=false", (self.tenant_id, def_id)).fetchone()
                return row["bpmn"] if row else None
            row = c.execute("""select snapshot from proc_def_version where tenant_id=%s and proc_def_id=%s and version=%s
                               and version_tag='hyd-immutable'""", (self.tenant_id, def_id, version)).fetchone()
            return row["snapshot"] if row else None

    # ------------------------------------------------------------ 기준으로 되돌리기
    @staticmethod
    def _blocking_row(r) -> dict:
        """거절 응답(409 본문 blocking — HTTPException 은 표준 JSON 으로 쓴다)에 싣는 진행 중 처리 건 한 줄 — 시작 시각은 ISO 문자열.
        running() 과 reset() 의 FlowBusy 가 같은 줄을 쓴다(_running)."""
        return dict(r, start_date=r["start_date"].isoformat() if r["start_date"] else None)

    #: 처리 건(i)이 「되돌리기가 지울 학생 판본」을 쓰는가 — 매개변수 (def_id, def_id, keep). running() 과 reset() 이 이 조각 하나를 쓴다:
    #: 되돌리기 전 확인이 남길 흐름(keep — 수업 흐름)을 빼지 않고 세면, 실제 되돌리기는 건드리지 않는 처리 건을 까닭으로 거절한다.
    PINNED = """exists (select 1 from proc_def_version v where v.tenant_id=i.tenant_id and v.proc_def_id=i.proc_def_id
                and v.version=i.proc_def_version and v.origin='user' and (%s::text is null or v.proc_def_id=%s)
                and not (v.proc_def_id = any(%s::text[])))"""

    def _running(self, c, def_id: str | None, keep: list[str]) -> list[dict]:
        return [self._blocking_row(r) for r in c.execute(f"""select proc_inst_id, proc_inst_name, proc_def_id, proc_def_version, start_date
                from bpm_proc_inst i where tenant_id=%s and not is_deleted and status in ('NEW','RUNNING') and {self.PINNED}
                order by start_date""", (self.tenant_id, def_id, def_id, keep)).fetchall()]

    def running(self, def_id: str | None = None, keep: frozenset | set = frozenset()) -> list[dict]:
        """B6: 되돌리기 전 확인 — reset(def_id, keep) 이 지울 학생 판본을 쓰는 진행 중(NEW · RUNNING) 처리 건. 아무것도 바꾸지 않는다.
        reset 과 같은 def_id · keep 을 넘겨야 같은 답이다(keep = 남길 흐름 — 관리 탭 되돌리기는 수업 흐름)."""
        with self.repo._conn() as c:
            return self._running(c, def_id, sorted(set(keep)))

    def reset(self, def_id: str | None = None, keep: frozenset | set = frozenset()) -> dict:
        """학생이 가져온 정의 · 판본 · 초안만 지운다. 그 판본으로 끝난 처리 건은 목록에서 숨긴다(is_deleted — 정의가 없어지므로).
        진행 중(NEW · RUNNING) 처리 건이 있으면 아무것도 지우지 않고 FlowBusy.
        keep: 지우지 않을 정의 id — 경보 경로에 배포된 흐름(2026-10-23 점검: 수업 흐름 c3_* 도 origin=user 라, 학생이 [기준으로 되돌리기]를
        누르면 강사가 배포한 수업 흐름까지 지워져 [정기 점검] · [재고 보충]이 「배포되어 있지 않습니다」로 멈췄다)."""
        keep = sorted(set(keep))
        with self.repo._conn() as c, c.transaction():
            c.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"b3-flow-reset:{self.tenant_id}",))
            running = self._running(c, def_id, keep)
            if running:
                raise FlowBusy(running)
            hidden = c.execute(f"update bpm_proc_inst i set is_deleted=true where tenant_id=%s and not is_deleted and {self.PINNED} returning proc_inst_id",
                               (self.tenant_id, def_id, def_id, keep)).fetchall()
            versions = c.execute("delete from proc_def_version where tenant_id=%s and origin='user' and (%s::text is null or proc_def_id=%s) and not (proc_def_id = any(%s::text[]))", (self.tenant_id, def_id, def_id, keep)).rowcount
            definitions = c.execute("delete from proc_def where tenant_id=%s and origin='user' and (%s::text is null or id=%s) and not (id = any(%s::text[]))", (self.tenant_id, def_id, def_id, keep)).rowcount
            drafts = c.execute("delete from proc_bpmn_draft where tenant_id=%s and (%s::text is null or proc_def_id=%s) and not (proc_def_id = any(%s::text[]))", (self.tenant_id, def_id, def_id, keep)).rowcount
            c.execute("delete from hyd_student_case_tags where tenant_id=%s and kind='flows' and (%s::text is null or asset_id=%s) and not (asset_id = any(%s::text[]))", (self.tenant_id, def_id, def_id, keep))
        return {"versions": versions, "definitions": definitions, "drafts": drafts, "hidden_instances": len(hidden), "kept": keep,
                "projection_instances": [i["proc_inst_id"] for i in hidden]}
