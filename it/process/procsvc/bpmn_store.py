"""B3: 가져온 흐름의 저장 — 매핑 초안 · 학생 판본(그림 원본 포함) · 기준으로 되돌리기.

  초안   public.proc_bpmn_draft(tenant_id, proc_def_id, bpmn, file_name, mapping)  — 다시 가져오면 같은 id 의 매핑을 유지하는 원천
  판본   public.proc_def_version(..., snapshot = .bpmn 원본, origin = 'user', version_tag = 'hyd-immutable')
         public.proc_def(id, bpmn = 마지막으로 등록한 .bpmn 원본, origin = 'user')
         등록은 **운영 판본 포인터(proc_def.prod_version · definition)를 움직이지 않는다** — 배포는 B4.
  되돌리기  origin='user' 인 정의 · 판본 · 초안만 지운다. 기준 정의(origin 없음)는 그대로. 진행 중 처리 건이 학생 판본을 쓰면 거절.

제품 대조: process-gpt-vue3 ProcessGPTBackend.ts:573-685 putRawDefinition 은 proc_def.bpmn 과 proc_def_version.snapshot 에 XML 을
저장한다(같은 칸). 판본 번호는 HYD 규칙(학생 흐름마다 1, 2, 3 …, 같은 번호는 바꿀 수 없음).

기본 제공 흐름(정의 JSON 으로 등록하는 기준 흐름 · 교대 인수인계)의 그림도 같은 칸(proc_def_version.snapshot)에 둔다 — 화면은 가져온 흐름과
같은 길(GET /api/flows/{id}/versions/{v}/bpmn)로 읽는다. 그림의 원문은 정의 파일 옆의 `<정의 id>.bpmn`(bpmn.io 에서 배치한 파일)이고,
기동(instance_mode.build)이 provided_diagram 으로 정의와 대조한 뒤 그 판본에 붙인다(attach_diagram). 정의와 어긋난 그림은 붙이지 않는다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

ORIGIN = "user"

# ---------------------------------------------------------------- 기본 제공 흐름의 그림(정의 옆 .bpmn → 그 판본의 그림)
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_NAMESPACES = {"bpmn": BPMN_NS, "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
               "dc": "http://www.omg.org/spec/DD/20100524/DC", "di": "http://www.omg.org/spec/DD/20100524/DI"}
_ID_ATTRS = ("id", "bpmnElement", "sourceRef", "targetRef", "attachedToRef", "default")
_ID_TEXTS = ("flowNodeRef", "incoming", "outgoing")


class DiagramMismatch(ValueError):
    """그림 파일이 정의와 어긋남 — problems 는 사람이 읽을 사유 목록."""
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(" / ".join(problems[:6]) + (f" 외 {len(problems) - 6}건" if len(problems) > 6 else ""))


def xid(def_id) -> str:
    """정의의 id(task:draft · seq:0)를 그림(XML)의 id 로 — 화면(it/portal/www/flow.js 의 xid)과 같은 규칙이다. 화면은 처리 건의 상태(끝남 ·
    지금 · 남음)를 정의의 id 로 받아 이 규칙으로 그림의 요소를 찾는다. XML id 로 쓸 수 있는 id 는 그대로, 아닌 글자는 _x<코드>_ 로 바꾼다."""
    s = str(def_id if def_id is not None else "")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", s):
        return s
    return ("" if re.match(r"[A-Za-z_]", s) else "_") + re.sub(r"[^A-Za-z0-9_.-]", lambda m: f"_x{ord(m.group()):x}_", s)


def _file_key(some_id: str) -> str:
    """그림 파일의 id 와 정의의 id 를 맞대는 열쇠 — 글자 · 숫자가 아닌 것은 모두 밑줄(task:draft-r2 ↔ task_draft_r2)."""
    return re.sub(r"[^A-Za-z0-9]", "_", some_id)


def _kind(tag: str) -> str:
    return ("task" if tag.endswith("ask") else "gateway" if tag.endswith("Gateway") else "boundary" if tag == "boundaryEvent"
            else "start" if tag == "startEvent" else "end" if tag == "endEvent" else "event" if tag.endswith("Event") else "")


def provided_diagram(definition: dict, xml: str) -> str:
    """정의 옆의 그림 파일(bpmn.io 에서 배치한 .bpmn)을 그 정의 판본의 그림으로 만든다: 요소 · 선 · 이름이 정의와 같은지 대조하고(어긋나면
    DiagramMismatch), 그림의 id 를 화면이 찾는 id(xid(정의 id))로 바꿔 돌려준다. 그림에만 있는 것은 차선과 좌표뿐이어야 한다."""
    try:
        root = ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError as e:
        raise DiagramMismatch([f"그림 파일을 읽을 수 없습니다({e})"]) from None
    process = root.find(f"{{{BPMN_NS}}}process")
    if process is None or root.find(f".//{{{_NAMESPACES['bpmndi']}}}BPMNDiagram") is None:
        raise DiagramMismatch(["그림 파일에 흐름(process)이나 배치 정보(BPMNDiagram)가 없습니다"])
    drawn = {}        # 그림의 id → (종류, 이름, 선의 양 끝 또는 붙은 단계)
    for el in process:
        tag = el.tag.split("}")[-1]
        if tag == "sequenceFlow":
            drawn[el.get("id")] = ("flow", el.get("name") or "", (el.get("sourceRef"), el.get("targetRef")))
        elif _kind(tag):
            drawn[el.get("id")] = (_kind(tag), el.get("name") or "", el.get("attachedToRef"))
    wanted = {}       # 정의의 id → 같은 꼴
    for x in definition.get("events") or []:
        kind = "boundary" if x.get("type") == "boundaryEvent" or x.get("attachedTo") else "start" if x.get("type") == "startEvent" \
            else "end" if x.get("type") == "endEvent" else "event"
        wanted[x["id"]] = (kind, x.get("name") or "", x.get("attachedTo"))
    for x in definition.get("activities") or []:
        wanted[x["id"]] = ("task", x.get("name") or "", None)
    for x in definition.get("gateways") or []:
        wanted[x["id"]] = ("gateway", x.get("name") or "", None)
    for x in definition.get("sequences") or []:
        wanted[x["id"]] = ("flow", x.get("name") or "", (x.get("source"), x.get("target")))
    by_key, problems = {}, []
    for file_id in drawn:
        if by_key.setdefault(_file_key(file_id), file_id) != file_id:
            problems.append(f"그림의 id {file_id} · {by_key[_file_key(file_id)]} 가 구별되지 않습니다")
    to_def = {}       # 그림의 id → 정의의 id
    for def_id, (kind, name, link) in wanted.items():
        file_id = by_key.get(_file_key(def_id))
        if file_id is None or file_id in to_def:
            problems.append(f"정의의 {def_id}(「{name}」)이(가) 그림에 없습니다")
            continue
        to_def[file_id] = def_id
    for file_id in drawn:
        if file_id not in to_def:
            problems.append(f"그림의 {file_id}(「{drawn[file_id][1]}」)이(가) 정의에 없습니다")
    def as_file(def_id):
        return by_key.get(_file_key(def_id)) if def_id else None
    for file_id, def_id in to_def.items():
        (kind, name, link), (d_kind, d_name, d_link) = wanted[def_id], drawn[file_id]
        if kind != d_kind:
            problems.append(f"{def_id}: 정의는 {kind} 인데 그림은 {d_kind} 입니다")
        if name != d_name:
            problems.append(f"{def_id}: 이름이 다릅니다(정의 「{name}」 · 그림 「{d_name}」)")
        want_link = tuple(as_file(v) for v in link) if isinstance(link, tuple) else as_file(link)
        if want_link != d_link:
            problems.append(f"{def_id}: 이어진 곳이 다릅니다(정의 {link} · 그림 {d_link})")
    if problems:
        raise DiagramMismatch(problems)
    rename = {file_id: xid(def_id) for file_id, def_id in to_def.items()}
    for el in root.iter():
        for attr in _ID_ATTRS:
            if el.get(attr) in rename:
                el.set(attr, rename[el.get(attr)])
        if el.tag.split("}")[-1] in _ID_TEXTS and (el.text or "").strip() in rename:
            el.text = rename[el.text.strip()]
    for prefix, uri in _NAMESPACES.items():
        ET.register_namespace(prefix, uri)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


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

    def attach_diagram(self, def_id: str, version: str, bpmn: str) -> bool:
        """기본 제공 흐름(학생이 가져온 것이 아닌 판본)의 그림을 그 판본에 붙인다 — 정의 원문 · 운영 판본 포인터는 건드리지 않는다. 그림은 보이는 꼴일 뿐이라
        같은 판본의 그림은 저장소의 파일이 바뀌면 새 그림으로 바뀐다(정의와 어긋나지 않는지는 provided_diagram 이 본다). 돌려줌: 바뀌었는가."""
        with self.repo._conn() as c:
            return bool(c.execute("""update proc_def_version set snapshot=%s where tenant_id=%s and proc_def_id=%s and version=%s
                                     and version_tag='hyd-immutable' and coalesce(origin,'')<>'user' and snapshot is distinct from %s""",
                                  (bpmn, self.tenant_id, def_id, version, bpmn)).rowcount)

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
