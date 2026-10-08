"""B3: 가져온 흐름의 저장 — 매핑 초안 · 학생 판본(그림 원본 포함) · 기준으로 되돌리기.

  초안   public.proc_bpmn_draft(tenant_id, proc_def_id, bpmn, file_name, mapping)  — 다시 가져오면 같은 id 의 매핑을 유지하는 원천
  판본   public.proc_def_version(..., snapshot = .bpmn 원본, origin = 'user', version_tag = 'hyd-immutable')
         public.proc_def(id, bpmn = 마지막으로 등록한 .bpmn 원본, origin = 'user')
         등록은 **운영 판본 포인터(proc_def.prod_version · definition)를 움직이지 않는다** — 배포는 B4.
  되돌리기  origin='user' 인 정의 · 판본 · 초안만 지운다. 기준 정의(origin 없음)는 그대로. 진행 중 처리 건이 학생 판본을 쓰면 거절.

제품 대조: process-gpt-vue3 ProcessGPTBackend.ts:573-685 putRawDefinition 은 proc_def.bpmn 과 proc_def_version.snapshot 에 XML 을
저장한다(같은 칸). 판본 번호는 HYD 규칙(학생 흐름마다 1, 2, 3 …, 같은 번호는 바꿀 수 없음).
MemoryRepo(단위 시험) 는 repo.def_versions 에 판본을 넣고, 머리(proc_def)와 초안은 이 객체가 들고 있다.
"""
from __future__ import annotations

import re
import threading
from copy import deepcopy
from datetime import datetime, timezone

from . import procdb

ORIGIN = "user"
_MEM_LOCK = threading.RLock()


class FlowBusy(ValueError):
    """되돌리기를 막는 진행 중 처리 건."""
    def __init__(self, running: list[dict]):
        self.running = running
        names = ", ".join(f"{r['proc_inst_id']}({r['proc_def_id']} 판본 {r['proc_def_version']})" for r in running[:5])
        super().__init__(f"진행 중인 처리 건 {len(running)}건이 내가 가져온 흐름을 씁니다: {names} — 끝내거나 닫은 뒤 되돌리세요")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def next_version(existing: list[str]) -> str:
    nums = [int(v) for v in existing if re.fullmatch(r"\d+", str(v or ""))]
    return str(max(nums) + 1) if nums else "1"


class FlowStore:
    def __init__(self, repo, tenant_id: str):
        self.repo, self.tenant_id = repo, tenant_id
        self.memory = isinstance(repo, procdb.MemoryRepo)
        if self.memory:
            with _MEM_LOCK:
                if not hasattr(repo, "_b3_flows"):
                    repo._b3_flows = {"drafts": {}, "heads": {}, "versions": {}}   # versions: (def, tenant, version) → {snapshot, at, file}
            self.mem = repo._b3_flows

    # ------------------------------------------------------------ 보호
    def is_protected(self, def_id: str) -> bool:
        """기준(학생이 만든 것이 아닌) 정의 id 인가 — 그 id 로는 가져오지 않는다."""
        if self.memory:
            mine = {k for k, v in self.mem["heads"].items() if k[1] == self.tenant_id}
            return any(k[0] == def_id and k[1] == self.tenant_id for k in self.repo.def_versions) and (def_id, self.tenant_id) not in mine
        with self.repo._conn() as c:
            row = c.execute("""select exists(select 1 from proc_def_version where tenant_id=%s and proc_def_id=%s
                                   and coalesce(origin,'')<>'user')
                               or exists(select 1 from proc_def where tenant_id=%s and id=%s and coalesce(origin,'')<>'user') as p""",
                            (self.tenant_id, def_id, self.tenant_id, def_id)).fetchone()
            return bool(row["p"])

    # ------------------------------------------------------------ 초안(매핑)
    def get_draft(self, def_id: str) -> dict | None:
        if self.memory:
            return deepcopy(self.mem["drafts"].get((def_id, self.tenant_id)))
        with self.repo._conn() as c:
            return self.repo._row(c.execute("select proc_def_id, bpmn, file_name, mapping, updated_at from proc_bpmn_draft "
                                            "where tenant_id=%s and proc_def_id=%s", (self.tenant_id, def_id)).fetchone())

    def save_draft(self, def_id: str, bpmn: str, file_name: str | None, mapping: dict) -> None:
        if self.memory:
            with _MEM_LOCK:
                self.mem["drafts"][(def_id, self.tenant_id)] = {"proc_def_id": def_id, "bpmn": bpmn, "file_name": file_name,
                                                               "mapping": deepcopy(mapping), "updated_at": _now()}
            return
        with self.repo._conn() as c:
            c.execute("""insert into proc_bpmn_draft (tenant_id, proc_def_id, bpmn, file_name, mapping, updated_at)
                         values (%s,%s,%s,%s,%s,now())
                         on conflict (tenant_id, proc_def_id) do update set bpmn=excluded.bpmn, file_name=excluded.file_name,
                             mapping=excluded.mapping, updated_at=now()""",
                      (self.tenant_id, def_id, bpmn, file_name, self.repo._Jsonb(mapping)))

    def save_mapping(self, def_id: str, mapping: dict) -> None:
        if self.memory:
            with _MEM_LOCK:
                d = self.mem["drafts"].get((def_id, self.tenant_id))
                if d is None:
                    raise KeyError(f"가져온 그림이 없습니다: {def_id}")
                d.update(mapping=deepcopy(mapping), updated_at=_now())
            return
        with self.repo._conn() as c:
            n = c.execute("update proc_bpmn_draft set mapping=%s, updated_at=now() where tenant_id=%s and proc_def_id=%s",
                          (self.repo._Jsonb(mapping), self.tenant_id, def_id)).rowcount
            if not n:
                raise KeyError(f"가져온 그림이 없습니다: {def_id}")

    # ------------------------------------------------------------ 판본
    def versions(self, def_id: str | None = None) -> list[dict]:
        """학생 판본 목록 [{id, version, name, registered_at, file_name}] (오래된 것 먼저)."""
        if self.memory:
            rows = []
            for (did, tenant, version), meta in self.mem["versions"].items():
                if tenant != self.tenant_id or (def_id and did != def_id):
                    continue
                d = self.repo.def_versions.get((did, tenant, version)) or {}
                rows.append({"id": did, "version": version, "name": d.get("name"), "registered_at": meta["at"], "file_name": meta.get("file")})
            return sorted(rows, key=lambda r: (r["id"], int(r["version"]) if r["version"].isdigit() else 0))
        with self.repo._conn() as c:
            rows = c.execute("""select proc_def_id as id, version, definition->>'processDefinitionName' as name,
                                       "timeStamp" as registered_at, message as file_name
                                from proc_def_version where tenant_id=%s and origin='user' and (%s::text is null or proc_def_id=%s)
                                order by proc_def_id, "timeStamp", version""", (self.tenant_id, def_id, def_id)).fetchall()
            return [self.repo._row(r) for r in rows]

    def drafts(self) -> list[dict]:
        if self.memory:
            return [{k: v for k, v in d.items() if k != "bpmn"} for (did, tenant), d in sorted(self.mem["drafts"].items()) if tenant == self.tenant_id]
        with self.repo._conn() as c:
            return [self.repo._row(r) for r in c.execute("select proc_def_id, file_name, mapping, updated_at from proc_bpmn_draft "
                                                         "where tenant_id=%s order by proc_def_id", (self.tenant_id,)).fetchall()]

    def register(self, raw: dict, bpmn: str, file_name: str | None) -> dict:
        """새 판본 번호를 정해 정의 + .bpmn 원본을 함께 넣는다. 운영 판본 포인터는 건드리지 않는다. 돌려줌: 넣은 정의(판본 포함)."""
        def_id = raw["processDefinitionId"]
        message = f"bpmn.io 가져오기: {file_name or '그림'}"
        if self.memory:
            with _MEM_LOCK:
                mine = [v for (d, t, v) in self.repo.def_versions if d == def_id and t == self.tenant_id]
                raw = dict(raw, version=next_version(mine))
                key = (def_id, self.tenant_id, raw["version"])
                if key in self.repo.def_versions:
                    raise ValueError("이미 등록한 판본은 바꿀 수 없습니다")
                self.repo.def_versions[key] = {"id": def_id, "tenant_id": self.tenant_id, "name": raw.get("processDefinitionName"),
                                               "definition": deepcopy(raw), "prod_version": raw["version"], "type": "bpmn",
                                               "ontology_ref": raw.get("ontologyRef"), "message": message}
                self.mem["versions"][key] = {"snapshot": bpmn, "at": _now(), "file": file_name}
                head = self.mem["heads"].setdefault((def_id, self.tenant_id), {"prod_version": None})
                head.update(bpmn=bpmn, name=raw.get("processDefinitionName"))
            return raw
        with self.repo._conn() as c, c.transaction():
            c.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"b3-flow:{self.tenant_id}:{def_id}",))
            existing = [r["version"] for r in c.execute("select version from proc_def_version where tenant_id=%s and proc_def_id=%s",
                                                       (self.tenant_id, def_id)).fetchall()]
            raw = dict(raw, version=next_version(existing))
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
        if self.memory:
            if version is None:
                return (self.mem["heads"].get((def_id, self.tenant_id)) or {}).get("bpmn")
            return (self.mem["versions"].get((def_id, self.tenant_id, version)) or {}).get("snapshot")
        with self.repo._conn() as c:
            if version is None:
                row = c.execute("select bpmn from proc_def where tenant_id=%s and id=%s and isdeleted=false", (self.tenant_id, def_id)).fetchone()
                return row["bpmn"] if row else None
            row = c.execute("""select snapshot from proc_def_version where tenant_id=%s and proc_def_id=%s and version=%s
                               and version_tag='hyd-immutable'""", (self.tenant_id, def_id, version)).fetchone()
            return row["snapshot"] if row else None

    # ------------------------------------------------------------ 기준으로 되돌리기
    def reset(self) -> dict:
        """학생이 가져온 정의 · 판본 · 초안만 지운다. 그 판본으로 끝난 처리 건은 목록에서 숨긴다(is_deleted — 정의가 없어지므로).
        진행 중(NEW · RUNNING) 처리 건이 있으면 아무것도 지우지 않고 FlowBusy."""
        if self.memory:
            with _MEM_LOCK:
                keys = [k for k in self.mem["versions"] if k[1] == self.tenant_id]
                pinned = {(d, v) for d, t, v in keys}
                insts = [i for i in self.repo.instances.values() if i.get("tenant_id") == self.tenant_id and not i.get("is_deleted")
                         and (i.get("proc_def_id"), i.get("proc_def_version")) in pinned]
                running = [i for i in insts if i.get("status") in ("NEW", "RUNNING")]
                if running:
                    raise FlowBusy([{k: i.get(k) for k in ("proc_inst_id", "proc_def_id", "proc_def_version")} for i in running])
                for i in insts:
                    i["is_deleted"] = True
                for k in keys:
                    self.repo.def_versions.pop(k, None)
                    self.mem["versions"].pop(k, None)
                heads = [k for k in self.mem["heads"] if k[1] == self.tenant_id]
                for k in heads:
                    self.mem["heads"].pop(k, None)
                    self.repo.defs.pop(k, None)
                drafts = [k for k in self.mem["drafts"] if k[1] == self.tenant_id]
                for k in drafts:
                    self.mem["drafts"].pop(k, None)
            return {"versions": len(keys), "definitions": len(heads), "drafts": len(drafts), "hidden_instances": len(insts)}
        with self.repo._conn() as c, c.transaction():
            c.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"b3-flow-reset:{self.tenant_id}",))
            pinned = """exists (select 1 from proc_def_version v where v.tenant_id=i.tenant_id and v.proc_def_id=i.proc_def_id
                        and v.version=i.proc_def_version and v.origin='user')"""
            running = c.execute(f"""select proc_inst_id, proc_def_id, proc_def_version from bpm_proc_inst i
                                    where tenant_id=%s and not is_deleted and status in ('NEW','RUNNING') and {pinned}
                                    order by start_date""", (self.tenant_id,)).fetchall()
            if running:
                raise FlowBusy([dict(r) for r in running])
            hidden = c.execute(f"update bpm_proc_inst i set is_deleted=true where tenant_id=%s and not is_deleted and {pinned}",
                               (self.tenant_id,)).rowcount
            versions = c.execute("delete from proc_def_version where tenant_id=%s and origin='user'", (self.tenant_id,)).rowcount
            definitions = c.execute("delete from proc_def where tenant_id=%s and origin='user'", (self.tenant_id,)).rowcount
            drafts = c.execute("delete from proc_bpmn_draft where tenant_id=%s", (self.tenant_id,)).rowcount
        return {"versions": versions, "definitions": definitions, "drafts": drafts, "hidden_instances": hidden}
