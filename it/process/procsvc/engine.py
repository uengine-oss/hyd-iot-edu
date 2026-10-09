"""Process-instance engine (pure logic) — the ProcessGPT completion semantics on a definition JSON.

Shapes and rules follow the product so the lecture can end with "this is what ProcessGPT productises"
(docs/handoff/REPO_GAP.md §1, sources: process-gpt-completion/polling_service/{process_definition,workitem_processor,database}.py):

  definition   it/process/definitions/*.json — activities[id,name,type,role,agent,agentMode,orchestration,tool,instruction,
               inputData,outputData,checkpoints,attachedEvents,duration], events, gateways, sequences[source,target,condition,
               properties{default,priority}], roles[name,endpoint,resolutionRule], data[name,type,description]
  instance     bpm_proc_inst row — status RUNNING from creation, role_bindings from the roles, variables_data as the product's
               list [{key, name, value}], current_activity_ids, participants
  work item    todolist row — one per activity, created TODO for every reachable activity when the instance starts
               (예정 업무, upsert_todo_workitems), flipped to IN_PROGRESS when the flow reaches it (upsert_next_workitems),
               SUBMITTED when a person / the agent worker / a service turns it in, DONE when the engine has created the
               next work items (upsert_completed_workitem), CANCELLED for the branch not taken, PENDING when the
               outgoing conditions are not met (run_completed_determination). Boundary timers are work items too
               (inject_boundary_events_as_next) with a due_date the housekeeping loop fires.

Gateway conditions are small boolean expressions over the instance variables, evaluated by a whitelisted AST walker
(the product's conditionFunction eval with restricted builtins; natural-language conditions judged by an LLM are
deliberately not supported here — decisions stay deterministic, DECISIONS.md 3 · 12).
"""
from __future__ import annotations

import ast
import json
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER_TYPES = {"userTask", "manualTask"}
AUTO_TYPES = {"businessRuleTask", "serviceTask", "scriptTask", "sendTask", "receiveTask"}
SERVICE_TYPES = {"serviceTask", "scriptTask", "sendTask"}
# A116 (r14 B5, ProcessGPT shape): an agent activity is a userTask carrying agentMode DRAFT|COMPLETE (+ orchestration), the
# way the product's designer (GPTUserTaskPanel) and polling service (database.determine_agent_mode) read it. Registered
# definitions are stored in that shape; versions stored before A116 still carry businessRuleTask and keep running.
AGENT_MODES = ("DRAFT", "COMPLETE")
AGENT_ORCH = "cliagents"              # the only agent orchestration HYD executes (the product defaults to crewai-deep-research)
NO_MODE = (None, "", "none", "None", "null")


def agent_mode_of(activity: dict) -> str | None:
    mode = str(activity.get("agentMode") or "").upper()
    return mode if mode in AGENT_MODES else None


def is_agent(activity: dict) -> bool:
    return activity.get("type") in USER_TYPES | {"businessRuleTask"} and agent_mode_of(activity) is not None


def is_human(activity: dict) -> bool:
    return activity.get("type") in USER_TYPES and agent_mode_of(activity) is None
TERMINAL_STATUSES = {"DONE", "CANCELLED"}
LIVE_STATUSES = {"IN_PROGRESS", "SUBMITTED", "PENDING"}
PROCESS_ORCH = "hyd-process"          # service tasks the process service executes itself
SYSTEM_USER = "sys:process"           # performer of event work items (the product writes nextUserEmail="system")
# C2 (확정 TODO C, 결정 4): 기다리는 부품(시간 대기 · 입고 확인)은 업무 시간(예정된 정비 시간까지 몇 시간, 납기 며칠)을 기다린다. 배속(TIME_SCALE)만으로는
# 20배속에서도 납기 5일이 6시간이라 수업에서 볼 수 없으므로, 그 부품과 그 부품에 붙은 경계 타이머에만 수업용 압축 배율을 한 번 더 곱한다.
# 설비 물리 · 감지기 · 재관측 · 사람 응답 타이머(TIME_SCALE 규칙)는 그대로다. 값은 instance_mode.build 가 PROCESS_WAIT_COMPRESSION 으로 정한다.
WAIT_TOOLS = ("process:wait", "enterprise:GR_CONFIRM", "plant:restore")   # 정비 수행은 예정된 정비 시간까지 기다릴 수 있다(until)
_WAIT_COMPRESSION = [1.0]


def configure_wait_compression(factor: float) -> float:
    """수업용 대기 압축 배율(1 이상)을 정한다. 돌려준 값이 이후 기다리는 부품 · 그 경계 타이머에 쓰인다."""
    value = float(factor)
    if not value >= 1.0 or value != value or value == float("inf"):
        raise ValueError("대기 압축 배율은 1 이상의 유한한 수여야 합니다")
    _WAIT_COMPRESSION[0] = value
    return value


def wait_compression() -> float:
    return _WAIT_COMPRESSION[0]


def timer_scale(activity: dict | None, time_scale: float) -> float:
    """경계 타이머의 배율: 기다리는 부품에 붙은 타이머는 배속 × 수업 압축, 그 밖은 배속 그대로."""
    if activity and activity.get("tool") in WAIT_TOOLS:
        return max(1.0, time_scale) * wait_compression()
    return time_scale


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------- definition
@dataclass
class Definition:
    raw: dict
    id: str
    name: str
    activities: dict[str, dict] = field(default_factory=dict)
    events: dict[str, dict] = field(default_factory=dict)
    gateways: dict[str, dict] = field(default_factory=dict)
    roles: dict[str, dict] = field(default_factory=dict)
    data: dict[str, dict] = field(default_factory=dict)
    sequences: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Definition":
        defn = cls(raw=d, id=d["processDefinitionId"], name=d.get("processDefinitionName", d["processDefinitionId"]))
        defn.activities = {a["id"]: a for a in d.get("activities", [])}
        defn.events = {e["id"]: e for e in d.get("events", [])}
        defn.gateways = {g["id"]: g for g in d.get("gateways", [])}
        defn.roles = {r["name"]: r for r in d.get("roles", [])}
        defn.data = {v["name"]: v for v in d.get("data", [])}
        defn.sequences = list(d.get("sequences", []))
        defn.validate()
        return defn

    @classmethod
    def load(cls, path: str | Path) -> "Definition":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---- structure
    def validate(self) -> None:
        nodes = set(self.activities) | set(self.events) | set(self.gateways)
        for s in self.sequences:
            for end in ("source", "target"):
                if s[end] not in nodes:
                    raise ValueError(f"sequence {s.get('id')} references unknown node {s[end]}")
        if len(self.start_events()) != 1:
            raise ValueError(f"definition needs exactly one startEvent, found {len(self.start_events())}")
        for a in self.activities.values():
            if a.get("role") and a["role"] not in self.roles:
                raise ValueError(f"activity {a['id']} uses undefined role {a['role']!r}")
            # A143 (remaining-sweep 17, R13 C03): subProcess/callActivity have no execution branch anywhere in this engine, so
            # a file loaded directly (Definition.load) is refused the same way the registration path refuses it.
            if a.get("type") not in USER_TYPES | AUTO_TYPES:
                raise ValueError(f"activity {a['id']} has unsupported type {a.get('type')!r}")
            for ev_id in a.get("attachedEvents") or []:
                if ev_id not in self.events:
                    raise ValueError(f"activity {a['id']} attaches unknown event {ev_id}")
        for s in self.sequences:
            if s.get("condition"):
                compile_condition(s["condition"])           # fail at load time, not at runtime

    def start_events(self) -> list[dict]:
        return [e for e in self.events.values() if e.get("type") == "startEvent"]

    def node_kind(self, node_id: str) -> str:
        if node_id in self.activities:
            return "activity"
        if node_id in self.gateways:
            return "gateway"
        if node_id in self.events:
            return "event"
        raise KeyError(node_id)

    def outgoing(self, node_id: str) -> list[dict]:
        return [s for s in self.sequences if s["source"] == node_id]

    def incoming(self, node_id: str) -> list[dict]:
        return [s for s in self.sequences if s["target"] == node_id]

    def attached_events(self, activity_id: str) -> list[dict]:
        """Boundary events of an activity — the product keeps the list on the activity (attachedEvents); the event's
        own attachedTo is accepted too so either spelling works."""
        ids = list(self.activities.get(activity_id, {}).get("attachedEvents") or [])
        ids += [e["id"] for e in self.events.values() if e.get("type") == "boundaryEvent" and e.get("attachedTo") == activity_id and e["id"] not in ids]
        return [self.events[i] for i in ids]

    def attached_activity(self, event_id: str) -> dict | None:
        for a in self.activities.values():
            if event_id in (a.get("attachedEvents") or []):
                return a
        ev = self.events.get(event_id) or {}
        return self.activities.get(ev.get("attachedTo") or "")

    def role_binding(self, role_name: str | None) -> dict | None:
        r = self.roles.get(role_name or "")
        return {"name": r["name"], "endpoint": r.get("endpoint"), "resolutionRule": r.get("resolutionRule")} if r else None

    def role_endpoint(self, role_name: str | None) -> str | None:
        r = self.roles.get(role_name or "")
        return r.get("endpoint") if r else None

    def initial_activities(self) -> list[str]:
        """Activities the start event leads to (through gateways), in flow order."""
        return [n for n in _targets_through_gateways(self, self.start_events()[0]["id"]) if n in self.activities]

    def downstream_activities(self, from_node: str) -> list[str]:
        """Every activity reachable from a node following all branches (the product's find_all_downstream_activities)."""
        out, seen, queue = [], set(), [s["target"] for s in self.outgoing(from_node)]
        while queue:
            n = queue.pop(0)
            if n in seen:
                continue
            seen.add(n)
            if n in self.activities and n not in out:
                out.append(n)
            if n in self.events and self.events[n].get("type") == "endEvent":
                continue
            queue += [s["target"] for s in self.outgoing(n)]
        return out


def _targets_through_gateways(defn: Definition, node_id: str) -> list[str]:
    out, queue, seen = [], [s["target"] for s in defn.outgoing(node_id)], set()
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        if n in defn.gateways:
            queue += [s["target"] for s in defn.outgoing(n)]
        else:
            out.append(n)
    return out


# ---------------------------------------------------------------- conditions
_ALLOWED = (ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Constant, ast.Load,
            ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
            ast.List, ast.Tuple)


def compile_condition(expr: str) -> ast.Expression:
    """Parse a sequence condition and refuse anything but comparisons of variables and literals."""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"condition {expr!r}: {type(node).__name__} is not allowed")
    return tree


def eval_condition(expr: str, variables: dict) -> bool:
    tree = compile_condition(expr)

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return variables.get(n.id)
        if isinstance(n, (ast.List, ast.Tuple)):
            return [ev(x) for x in n.elts]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return not ev(n.operand)
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, comp in zip(n.ops, n.comparators):
                right = ev(comp)
                ok = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
                      ast.Lt: lambda a, b: a is not None and b is not None and a < b,
                      ast.LtE: lambda a, b: a is not None and b is not None and a <= b,
                      ast.Gt: lambda a, b: a is not None and b is not None and a > b,
                      ast.GtE: lambda a, b: a is not None and b is not None and a >= b,
                      ast.In: lambda a, b: b is not None and a in b, ast.NotIn: lambda a, b: b is None or a not in b,
                      ast.Is: lambda a, b: a is b, ast.IsNot: lambda a, b: a is not b}[type(op)](left, right)
                if not ok:
                    return False
                left = right
            return True
        raise ValueError(f"unsupported node {type(n).__name__}")
    return bool(ev(tree))


_ISO_DURATION = re.compile(r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$")


def iso_duration_seconds(text: str) -> float:
    m = _ISO_DURATION.match(text or "")
    if not m:
        raise ValueError(f"unsupported ISO-8601 duration {text!r}")
    g = {k: int(v or 0) for k, v in m.groupdict().items()}
    return g["d"] * 86400 + g["h"] * 3600 + g["m"] * 60 + g["s"]


def _properties(seq: dict) -> dict:
    p = seq.get("properties")
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except json.JSONDecodeError:
            p = {}
    return p if isinstance(p, dict) else {}


# ---------------------------------------------------------------- variables (product shape: list of {key, name, value})
def variables(inst: dict) -> dict:
    return {v["key"]: v.get("value") for v in (inst.get("variables_data") or []) if isinstance(v, dict) and "key" in v}


def set_variables(defn: Definition, inst: dict, values: dict, *, source: dict | None = None) -> None:
    """Merge values into variables_data by key (the product's _update_process_variables)."""
    rows = inst.setdefault("variables_data", [])
    for key, value in values.items():
        inst.setdefault('variable_sources', {})[key] = deepcopy(source or {'kind': 'runtime'})
        name = (defn.data.get(key) or {}).get("description") or key
        for row in rows:
            if row.get("key") == key:
                row["value"], row["name"] = value, row.get("name") or name
                break
        else:
            rows.append({"key": key, "name": name, "value": value})


# ---------------------------------------------------------------- instances and work items
def new_instance_id(def_id: str) -> str:
    return f"{def_id}.{uuid.uuid4()}"


def new_instance(defn: Definition, values: dict, name: str | None = None, now: datetime | None = None,
                 tenant_id: str = "hyd", root: str | None = None) -> dict:
    """bpm_proc_inst row. RUNNING from creation (the product's _create_or_get_process_instance)."""
    iid = new_instance_id(defn.id)
    inst = {"proc_inst_id": iid, "proc_def_id": defn.id, "proc_inst_name": name or f"{defn.name} {values.get('asset', '')}".strip(),
            "status": "RUNNING", "variables_data": [], "current_activity_ids": [], "participants": [],
            "role_bindings": [b for b in (defn.role_binding(r) for r in defn.roles) if b],
            "root_proc_inst_id": root or iid, "parent_proc_inst_id": None, "execution_scope": None, "tenant_id": tenant_id,
            "proc_def_version": defn.raw.get("version"), "version": defn.raw.get("version"), "version_tag": None,
            "start_date": now_iso(now), "end_date": None, "due_date": None, "end_event": None,
            "initial_variables": deepcopy(values), "variable_sources": {}, "rework_generation": 0,
            "flow_state": {"end_arrivals": []}}
    set_variables(defn, inst, deepcopy(values), source={'kind': 'input'})
    return inst


def instance_binding(defn: Definition, inst: dict | None, role_name: str | None) -> dict | None:
    """B5: the instance's role binding wins over the definition's default (ProcessGPT keeps role_bindings per instance).
    new_instance copies the definition's bindings, so this is the definition's binding unless the start chose another
    performer for a role (start_definition(role_endpoints=…), e.g. the agent a person picked to answer a question)."""
    for b in (inst or {}).get("role_bindings") or []:
        if isinstance(b, dict) and b.get("name") == role_name and b.get("endpoint"):
            return {"name": b["name"], "endpoint": b["endpoint"], "resolutionRule": b.get("resolutionRule")}
    return defn.role_binding(role_name)


def _query_text(activity: dict) -> str:
    """The product's query column: [Description] + [Instruction] (the agent's brief); [InputData] is appended when reached."""
    parts = []
    if activity.get("description"):
        parts.append(f"[Description]\n{activity['description']}\n")
    if activity.get("instruction"):
        parts.append(f"[Instruction]\n{activity['instruction']}\n")
    return "\n".join(parts)


def new_workitem(defn: Definition, inst: dict, activity: dict, now: datetime | None = None, status: str = "TODO") -> dict:
    """todolist row for one activity, TODO (예정 업무) unless told otherwise. agent_mode: COMPLETE/DRAFT for agents, NULL for people."""
    is_user = is_human(activity)
    binding = instance_binding(defn, inst, activity.get("role"))
    agent_mode = agent_mode_of(activity)
    orch = activity.get("orchestration")
    if orch in NO_MODE:
        orch = None if is_user else (AGENT_ORCH if agent_mode else (PROCESS_ORCH if activity.get("type") in SERVICE_TYPES else None))
    tool = activity.get("tool") or ("formHandler:defaultForm" if "task" in str(activity.get("type", "")).lower() else None)
    return {"id": str(uuid.uuid4()), "proc_inst_id": inst["proc_inst_id"], "root_proc_inst_id": inst.get("root_proc_inst_id"),
            "proc_def_id": defn.id, "activity_id": activity["id"], "activity_name": activity.get("name"),
            "status": status, "user_id": binding.get("endpoint") if binding else None, "username": activity.get("role"),
            "assignees": [binding] if binding else [], "tool": tool, "description": activity.get("description") or activity.get("instruction"),
            "query": _query_text(activity), "agent_mode": agent_mode, "agent_orch": orch,
            "duration": activity.get("duration"), "output": None, "draft": None, "draft_status": None, "log": None, "retry": 0,
            "consumer": None, "reference_ids": [], "gateway_decisions": None, "tenant_id": inst.get("tenant_id", "hyd"),
            "version": defn.raw.get("version"), "start_date": now_iso(now), "end_date": None, "due_date": None, "execution_scope": None,
            "generation": inst.get('rework_generation', 0), "rework_count": 0,
            "rework_request_id": inst.get('rework_request_id')}


def new_event_workitem(defn: Definition, inst: dict, event: dict, now: datetime | None = None, time_scale: float = 1.0) -> dict:
    """A boundary/intermediate event as a work item (the product injects attached events into nextActivities, user 'system').
    A timer event carries its due_date; the housekeeping loop fires it."""
    due = None
    if event.get("eventDefinition") == "timer" and event.get("timer"):
        secs = iso_duration_seconds(event["timer"]) / max(1.0, time_scale)
        due = now_iso((now or datetime.now(timezone.utc)) + timedelta(seconds=secs))
    return {"id": str(uuid.uuid4()), "proc_inst_id": inst["proc_inst_id"], "root_proc_inst_id": inst.get("root_proc_inst_id"),
            "proc_def_id": defn.id, "activity_id": event["id"], "activity_name": event.get("name"), "status": "IN_PROGRESS",
            "user_id": SYSTEM_USER, "username": "system", "assignees": [], "tool": None, "description": event.get("description"),
            "query": None, "agent_mode": None, "agent_orch": PROCESS_ORCH, "duration": None, "output": None, "draft": None,
            "draft_status": None, "log": None, "retry": 0, "consumer": None, "reference_ids": [], "gateway_decisions": None,
            "tenant_id": inst.get("tenant_id", "hyd"), "version": defn.raw.get("version"), "start_date": now_iso(now), "end_date": None,
            "due_date": due, "execution_scope": None, "generation": inst.get('rework_generation', 0),
            "rework_request_id": inst.get('rework_request_id')}


@dataclass
class Advance:
    """What one engine step did: rows to insert, rows to update, and the instance's new state."""
    created: list[dict] = field(default_factory=list)       # new rows (event work items)
    updated: list[dict] = field(default_factory=list)       # existing rows whose status changed (TODO→IN_PROGRESS, CANCELLED, DONE …)
    reached: list[dict] = field(default_factory=list)       # the rows the flow arrived at (subset of created+updated)
    ended: str | None = None                                 # end event id if the instance finished
    visited: list[str] = field(default_factory=list)        # gateways/events passed, for the log
    pending: bool = False                                    # the completed item could not proceed (conditions not met)
    waiting_joins: list[str] = field(default_factory=list)  # A100: parallel joins this path arrived at that still wait for other paths


def workitem_order(row: dict) -> tuple:
    return (int(row.get('generation') or 0), row.get('start_date') or '')


def _by_activity(workitems: list[dict]) -> dict[str, dict]:
    """Latest row per activity id (a re-run activity has several rows)."""
    out: dict[str, dict] = {}
    for w in sorted(workitems, key=workitem_order):
        out[w["activity_id"]] = w
    return out


def start(defn: Definition, inst: dict, now: datetime | None = None, time_scale: float = 1.0) -> Advance:
    """Open the instance: every reachable activity becomes a TODO row (예정 업무), then the flow reaches the first ones."""
    adv = Advance()
    start_ev = defn.start_events()[0]
    adv.visited.append(start_ev["id"])
    rows = [new_workitem(defn, inst, defn.activities[aid], now) for aid in defn.downstream_activities(start_ev["id"])]
    adv.created.extend(rows)
    from . import input_bindings
    input_bindings.install(defn, inst, rows, rows)
    _advance(defn, inst, start_ev["id"], rows, adv, now, time_scale)
    return adv


def reach(defn: Definition, inst: dict, row: dict, workitems: list[dict], now: datetime | None = None,
          time_scale: float = 1.0) -> list[dict]:
    """The flow arrived at an activity: TODO → IN_PROGRESS (service tasks go straight to SUBMITTED for the engine to run),
    the performer is bound, [InputData] is appended to the query, attached boundary events become live event rows.
    Returns the new event rows."""
    activity = defn.activities[row["activity_id"]]
    row["status"] = "SUBMITTED" if activity.get("type") in SERVICE_TYPES else "IN_PROGRESS"
    row["start_date"] = now_iso(now)
    inst.setdefault('flow_state',{}).setdefault('activity_arrivals',{})[row['id']] = {
        'activity':row['activity_id'],'generation':int(row.get('generation') or 0),'at':now_iso(now)}
    binding = instance_binding(defn, inst, activity.get("role"))
    if binding and not row.get("user_id"):
        row["user_id"], row["assignees"] = binding.get("endpoint"), [binding]
    inputs = {k: v for k, v in variables(inst).items() if k in (activity.get("inputData") or [])}
    from . import input_bindings
    inputs = input_bindings.snapshot(defn, inst, row, workitems, inputs)
    base = (row.get("query") or _query_text(activity)).split("[InputData]")[0].split('[ConditionData]')[0].rstrip()
    row["query"] = f"{base}\n\n[InputData]\n{json.dumps(inputs, ensure_ascii=False)}" if inputs else base
    prev = [w["id"] for w in _by_activity(workitems).values() if w["activity_id"] in _immediate_prev(defn, activity["id"]) and w["status"] == "DONE"]
    row["reference_ids"] = prev
    from . import dependency_schedule
    dependency_schedule.opened(inst, row)
    condition_names=(dependency_schedule.entry(inst,row) or {}).get('condition_names',[])
    if condition_names:
        condition_data={key:variables(inst)[key] for key in condition_names if key in variables(inst)}
        row['query']+='\n\n[ConditionData]\n'+json.dumps(condition_data,ensure_ascii=False)
        inst['flow_state'].setdefault('condition_snapshots',{})[row['id']]={
            'inputs':deepcopy(condition_data),
            'sources':{key:deepcopy((inst.get('variable_sources') or {}).get(key)) for key in condition_data}}
    if row.get("user_id") and row["user_id"] not in inst.setdefault("participants", []):
        inst["participants"].append(row["user_id"])
    events = [new_event_workitem(defn, inst, ev, now, timer_scale(activity, time_scale)) for ev in defn.attached_events(activity["id"])]
    for event in events:
        prior = _by_activity(workitems).get(event['activity_id'])
        if prior and event['generation'] > int(prior.get('generation') or 0):
            event['supersedes_id'] = prior['id']
    return events


def _immediate_prev(defn: Definition, activity_id: str) -> set[str]:
    out, queue, seen = set(), [s["source"] for s in defn.sequences if s["target"] == activity_id], set()
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        if n in defn.activities:
            out.add(n)
        elif n in defn.gateways:
            queue += [s["source"] for s in defn.sequences if s["target"] == n]
    return out


def submit(defn: Definition, inst: dict, workitem: dict, output: dict | None, now: datetime | None = None) -> dict:
    """A work item is turned in (person's form, agent's save_task_result, service result): output stored, status SUBMITTED.
    Only the activity's declared outputData keys are accepted — the engine refuses outputs the definition did not name."""
    if workitem["status"] in TERMINAL_STATUSES:
        raise ValueError(f"work item {workitem['id']} is already {workitem['status']}")
    if workitem['status'] == 'TODO':
        raise ValueError(f"work item {workitem['id']} is not reached")
    if workitem["proc_inst_id"] != inst["proc_inst_id"]:
        raise ValueError("work item does not belong to this instance")
    activity = defn.activities.get(workitem["activity_id"])
    output = dict(output or {})
    if activity is not None:
        declared = set(activity.get("outputData") or [])
        unknown = set(output) - declared
        if unknown and declared:
            raise ValueError(f"{activity['id']} may only output {sorted(declared)}, got {sorted(unknown)}")
    workitem.update(status="SUBMITTED", output=output, consumer=None)
    return workitem


def process_submitted(defn: Definition, inst: dict, workitem: dict, workitems: list[dict], now: datetime | None = None,
                      time_scale: float = 1.0) -> Advance:
    """The engine's turn (the product's handle_workitem): merge the output into the variables, judge the outgoing
    conditions (gateway_decisions), mark DONE or PENDING, cancel the alternatives, reach the next activities."""
    if workitem["status"] != "SUBMITTED":
        raise ValueError(f"work item {workitem['id']} is {workitem['status']}, not SUBMITTED")
    if workitem["proc_inst_id"] != inst["proc_inst_id"]:
        raise ValueError("work item does not belong to this instance")
    adv = Advance()
    node_id = workitem["activity_id"]
    activity = defn.activities.get(node_id)
    output = workitem.get("output") or {}
    if activity is not None:
        declared = activity.get("outputData") or []
        set_variables(defn, inst, {k: v for k, v in output.items() if k in declared} if declared else {},
                      source={'kind': 'workitem', 'id': workitem['id'], 'activity': node_id, 'version': workitem.get('version')})
    from . import dependency_schedule
    missing=dependency_schedule.completion_missing(defn,inst,workitem,workitems)
    if missing:
        decisions,ok,reasons={},False,[{'type':'CONDITION_INPUT_UNAVAILABLE','reason':', '.join(missing)}]
    else:
        decisions, ok, reasons = _judge(defn, node_id, variables(inst))
    if decisions:
        workitem["gateway_decisions"] = decisions
    if not ok:
        workitem["status"] = "PENDING"
        workitem["log"] = (workitem.get("log") or "") + " ".join(f"[{r['type']}] {r['reason']};" for r in reasons) + " "
        adv.updated.append(workitem)
        adv.pending = True
        return adv
    workitem.update(status="DONE", end_date=now_iso(now), consumer=None)
    adv.updated.append(workitem)
    if workitem.get("user_id") and workitem["user_id"] not in inst.setdefault("participants", []):
        inst["participants"].append(workitem["user_id"])
    inst["current_activity_ids"] = [a for a in inst.get("current_activity_ids") or [] if a != node_id]
    # the alternatives die with the winner: an activity's attached events, or an event's attached activity.
    # C2: a non-interrupting boundary timer (BPMN cancelActivity="false", e.g. 승인 지연 알림) leaves its activity running —
    # its path is a second token; the activity's own completion later retires the (already fired) timer row.
    alternatives = [] if non_interrupting(defn, node_id) else _alternatives(defn, node_id)
    for other in alternatives:
        row = _by_activity(workitems).get(other)
        if row and row["status"] not in TERMINAL_STATUSES:
            row.update(status="CANCELLED", end_date=now_iso(now), log=(row.get("log") or "") + f"cancelled: {node_id} completed first; ")
            adv.updated.append(row)
            inst['current_activity_ids'] = [a for a in inst.get('current_activity_ids') or [] if a != other]
    _advance(defn, inst, node_id, workitems, adv, now, time_scale)
    return adv


def non_interrupting(defn: Definition, node_id: str) -> bool:
    ev = defn.events.get(node_id) or {}
    return ev.get("type") == "boundaryEvent" and ev.get("cancelActivity") is False


def _alternatives(defn: Definition, node_id: str) -> list[str]:
    if node_id in defn.activities:
        return [e["id"] for e in defn.attached_events(node_id)]
    attached = defn.attached_activity(node_id)
    if attached is None:
        return []
    return [attached["id"]] + [e["id"] for e in defn.attached_events(attached["id"]) if e["id"] != node_id]


def _advance(defn: Definition, inst: dict, node_id: str, workitems: list[dict], adv: Advance, now, time_scale: float) -> None:
    """Follow the flow from a finished node to the next activities / end events (resolve_next_activity_payloads + execute_next_activity)."""
    from . import dependency_schedule
    rows = _by_activity(workitems)
    for target in _next_nodes(defn, node_id, variables(inst), adv, workitems):
        if target in defn.activities:
            row = rows.get(target)
            if row is None or row["status"] in TERMINAL_STATUSES:
                row = new_workitem(defn, inst, defn.activities[target], now)       # re-entry (loop) → a fresh row
                adv.created.append(row)
                rows[target] = row
                from . import input_bindings
                input_bindings.install(defn, inst, list(rows.values()), [row])
            elif row["status"] != "TODO":
                continue                                                           # already live
            else:
                adv.updated.append(row)
            scheduled = dependency_schedule.entry(inst, row)
            if scheduled is not None:
                scheduled['flow_arrived'] = True
                scheduled['arrival_source'] = node_id
            if not dependency_schedule.ready(inst, row, list(rows.values())):
                continue
            events = reach(defn, inst, row, list(rows.values()), now, time_scale)
            adv.created.extend(events)
            adv.reached += [row] + events
            if target not in inst.setdefault("current_activity_ids", []):
                inst["current_activity_ids"].append(target)
        else:
            ev = defn.events[target]
            adv.visited.append(target)
            if ev.get("type") == "endEvent":
                # An ordinary end consumes this path, not other admitted work.
                # Persist the arrival in the same transaction as task completion
                # so a new runtime can close only after the remaining paths finish.
                arrivals = inst.setdefault('flow_state', {}).setdefault('end_arrivals', [])
                source = rows.get(node_id)
                arrival = {'event': target, 'source': node_id,
                           'workitem': source['id'] if source else None,
                           'generation': int((source or inst).get('generation', inst.get('rework_generation')) or 0)}
                if arrival not in arrivals:
                    arrivals.append(arrival)
            else:
                row = new_event_workitem(defn, inst, ev, now, time_scale)
                adv.created.append(row)
                adv.reached.append(row)
    # A producer on a different control path can release already-admitted work.
    # This mutation and the producer's DONE/output commit in one transaction.
    for row in list(rows.values()):
        if (row['status'] != 'TODO' or dependency_schedule.entry(inst, row) is None
                or not dependency_schedule.ready(inst, row, list(rows.values()))):
            continue
        events = reach(defn, inst, row, list(rows.values()), now, time_scale)
        if row not in adv.updated and row not in adv.created:
            adv.updated.append(row)
        adv.created.extend(events)
        adv.reached += [row] + events
        if row['activity_id'] not in inst.setdefault('current_activity_ids', []):
            inst['current_activity_ids'].append(row['activity_id'])
    arrivals = (inst.get('flow_state') or {}).get('end_arrivals', [])
    live = any(row['status'] in {'IN_PROGRESS', 'SUBMITTED', 'PENDING'}
               for row in list(rows.values()) + adv.created)
    if arrivals and not live and not dependency_schedule.waiting(inst, list(rows.values())):
        adv.ended = arrivals[-1]['event']
        inst.update(status="COMPLETED", end_event=adv.ended, end_date=now_iso(now), current_activity_ids=[])
        for row in rows.values():
            if row["status"] == "TODO" or (row["status"] == "IN_PROGRESS" and row["activity_id"] in defn.events):
                row.update(status="CANCELLED", end_date=now_iso(now), log=(row.get("log") or "") + f"cancelled: instance ended ({adv.ended}); ")
                if row not in adv.updated and row not in adv.created:
                    adv.updated.append(row)


def _join_ready(defn: Definition, gateway_id: str, workitems: list[dict]) -> bool:
    """A100 (process-gpt-completion check_task_status: a parallel join waits for every incoming path). The join is ready
    when the latest row of every incoming source is finished — an activity DONE, a boundary/timer event fired. Readiness
    is computed from the rows, never stored, so a reworked branch (new generation) must finish again before the join
    fires again while the other branch's DONE row still counts."""
    rows = _by_activity(workitems)
    for seq in defn.sequences:
        if seq["target"] != gateway_id:
            continue
        src = seq["source"]
        row = rows.get(src)
        if src in defn.activities:
            if not row or row["status"] != "DONE":
                return False
        elif src in defn.events:
            if not row or row["status"] not in ("SUBMITTED", "DONE"):
                return False
        else:                                                   # a gateway feeding a join is refused at registration
            return False
    return True


def is_parallel_join(defn: Definition, gateway_id: str) -> bool:
    return defn.gateways.get(gateway_id, {}).get("type") == "parallelGateway" and len(defn.incoming(gateway_id)) > 1


def _next_nodes(defn: Definition, node_id: str, values: dict, adv: Advance, workitems: list[dict] | None = None) -> list[str]:
    """Targets after a node, expanding gateways with the product's rules: XOR takes exactly one (true → priority → default),
    inclusive takes every allowed branch, parallel takes all. A parallel join (≥2 incoming) is expanded only when every
    incoming path has finished (`_join_ready`); otherwise this path stops here and the last arriving path fires it."""
    out: list[str] = []
    queue = [node_id]
    seen: set[str] = set()
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        if cur in defn.gateways and cur != node_id:
            if is_parallel_join(defn, cur) and not _join_ready(defn, cur, workitems or []):
                adv.waiting_joins.append(cur)
                continue
            adv.visited.append(cur)
        for tgt in _allowed_targets(defn, cur, values):
            if tgt in defn.gateways:
                queue.append(tgt)
            elif tgt not in out:
                out.append(tgt)
    return out


def _allowed_targets(defn: Definition, source: str, values: dict) -> list[str]:
    outs = defn.outgoing(source)
    if source not in defn.gateways:
        return [s["target"] for s in outs if _state(s, values) is not False]
    gtype = defn.gateways[source].get("type", "exclusiveGateway")
    if gtype == "exclusiveGateway":
        # BPMN default flow: an outgoing sequence without a condition (or marked properties.default) is taken only when
        # no conditioned sequence is true. Several true → lowest priority number, then id (the product's tie-break).
        conditioned = [s for s in outs if s.get("condition") and not _properties(s).get("default")]
        true_seqs = [s for s in conditioned if _state(s, values) is True]
        default = next((s for s in outs if _properties(s).get("default") is True), None) or next((s for s in outs if not s.get("condition")), None)
        if len(true_seqs) == 1:
            chosen = true_seqs
        elif true_seqs:
            chosen = [sorted(true_seqs, key=lambda s: (int(_properties(s).get("priority") or 0), s.get("id") or ""))[0]]
        else:
            chosen = [default] if default else []
        return [s["target"] for s in chosen]
    return [s["target"] for s in outs if _state(s, values) is not False]


def _state(seq: dict, values: dict) -> bool | None:
    """True/False for a conditioned sequence, True when it has no condition (the product treats "empty as true")."""
    cond = seq.get("condition")
    if not cond:
        return True
    return eval_condition(cond, values)


def _judge(defn: Definition, node_id: str, values: dict) -> tuple[dict, bool, list[dict]]:
    """run_completed_determination: can the flow leave this node? Returns (gateway_decisions, ok, cannotProceedErrors)."""
    decisions: dict = {}
    outs = defn.outgoing(node_id)
    if not outs:
        return decisions, True, []
    ok = False
    for s in outs:
        tgt = s["target"]
        if _state(s, values) is False:
            continue
        if tgt not in defn.gateways:
            ok = True
            continue
        gw_type = defn.gateways[tgt].get("type", "exclusiveGateway")
        states = {}
        decisions.setdefault(tgt, {"selected": [], "sequences": {}})
        for gs in defn.outgoing(tgt):
            is_default = _properties(gs).get("default") is True or not gs.get("condition")
            if is_default:
                decisions[tgt]["default"] = gs["id"]              # a default flow is not judged (the product records conditionEval only)
                continue
            st = _state(gs, values)
            states[gs["id"]] = st
            decisions[tgt]["sequences"][gs["id"]] = {"target": gs["target"], "condition": gs.get("condition") or gs.get("name"), "eval": bool(st)}
            if st:
                decisions[tgt]["selected"].append(gs["id"])
        has_default = "default" in decisions[tgt]
        if gw_type == "parallelGateway":
            gw_ok = all(states.values()) if states else True
        else:
            gw_ok = any(states.values()) or has_default
        ok = ok or gw_ok
    reasons = [] if ok else [{"type": "PROCEED_CONDITION_NOT_MET", "reason": "시퀀스/게이트웨이 조건 불만족"}]
    return decisions, ok, reasons


def fire_event(defn: Definition, inst: dict, event_row: dict, workitems: list[dict], now: datetime | None = None,
               time_scale: float = 1.0) -> Advance:
    """A live event work item fired (timer due): it completes, its attached activity is cancelled, its flow is followed."""
    if event_row["activity_id"] not in defn.events:
        raise ValueError(f"{event_row['activity_id']} is not an event")
    if event_row["status"] in TERMINAL_STATUSES:
        raise ValueError(f"event {event_row['id']} is already {event_row['status']}")
    event_row.update(status="SUBMITTED", output={}, log=(event_row.get("log") or "") + f"fired at {now_iso(now)}; ")
    return process_submitted(defn, inst, event_row, workitems, now, time_scale)



def abort_to(defn: Definition, inst: dict, workitems: list[dict], target_activity_id: str, reason: str,
             now: datetime | None = None, time_scale: float = 1.0) -> Advance:
    """The case ended outside the flow (A074: the Incident reached a terminal state before any action was issued — alert
    cleared, operator rejected, escalated). Every open work item is cancelled with the reason and the flow jumps to the
    named human activity so a person records the outcome and the instance ends through the definition's own end event.
    Nothing is invented: no output is written for the cancelled work, agent claims are released by the CANCELLED status."""
    if target_activity_id not in defn.activities:
        raise ValueError(f"{target_activity_id} is not an activity")
    adv = Advance()
    # the engine pre-creates a TODO row per activity: the target's own waiting row is reached, never cancelled and re-created
    waiting = [w for w in workitems if w["activity_id"] == target_activity_id and w["status"] == "TODO"]
    target = max(waiting, key=workitem_order) if waiting else None
    for row in workitems:
        if row["status"] in TERMINAL_STATUSES or row is target:
            continue
        row.update(status="CANCELLED", end_date=now_iso(now), consumer=None, log=(row.get("log") or "") + f"cancelled: {reason}; ")
        adv.updated.append(row)
    if target is None:
        target = new_workitem(defn, inst, defn.activities[target_activity_id], now)
        adv.created.append(target)
    else:
        adv.updated.append(target)
    target["log"] = (target.get("log") or "") + f"reached by abort: {reason}; "
    events = reach(defn, inst, target, workitems, now, time_scale)
    adv.created += events
    adv.reached = [target]
    inst["current_activity_ids"] = [target_activity_id]
    return adv


# ---------------------------------------------------------------- views for the portal / tests
def timeline(defn: Definition, inst: dict, workitems: list[dict]) -> list[dict]:
    """Every activity of the definition with its latest work item state, in flow order (the portal derives the richer
    step view client-side with the product's instanceSteps.js)."""
    by_act: dict[str, list[dict]] = {}
    for w in workitems:
        by_act.setdefault(w["activity_id"], []).append(w)
    out = []
    for aid in _topological(defn):
        a = defn.activities[aid]
        items = sorted(by_act.get(aid, []), key=workitem_order)
        last = items[-1] if items else None
        out.append({"activity_id": aid, "name": a.get("name"), "type": a.get("type"), "role": a.get("role"),
                    "performer": defn.role_endpoint(a.get("role")), "orchestration": a.get("orchestration"),
                    "status": (last or {}).get("status") or "", "workitem": (last or {}).get("id"),
                    "start": (last or {}).get("start_date"), "end": (last or {}).get("end_date"), "runs": len(items),
                    "generation": (last or {}).get('generation', 0)})
    return out


def _topological(defn: Definition) -> list[str]:
    """Activities in flow order (Kahn): a node is listed only after every node that can reach it, ties in sequence order.
    A boundary event sits after the activity it is attached to. Nodes on a cycle fall back to definition order."""
    edges = [(s["source"], s["target"]) for s in defn.sequences]
    edges += [(a["id"], e["id"]) for a in defn.activities.values() for e in defn.attached_events(a["id"])]
    nodes = list(defn.events) + list(defn.gateways) + list(defn.activities)
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for a, b in edges:
        succ[a].append(b)
        indeg[b] += 1
    ready = [n for n in nodes if indeg[n] == 0]
    order: list[str] = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for nxt in succ[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    order += [n for n in nodes if n not in order]
    return [n for n in order if n in defn.activities]
