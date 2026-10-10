"""Agent settings and skills — the read side shared by the process service (portal API) and the agent worker (U2 · A2).

One source each, read on every run (nothing is copied or cached):
  * agent profile — public.users where is_agent (role · goal · persona · model · tools csv), as the product keeps it
    (process-gpt-vue3 ProcessGPTBackend.ts:4250-4287 putAgent writes the same columns);
  * skill — public.tenant_skills (tenant_id, skill_name, description, content = the SKILL.md text), migration 20261008000026;
  * agent ↔ skill — public.agent_skills (user_id, tenant_id, skill_name), the product's table (ProcessGPTBackend.ts:4389-4407);
  * step ↔ skill/tools — the definition activity's `skills` / `tools` (read by the worker since A095, skills used since U2).
HYD difference: the product keeps SKILL.md files in a skills store (deepagents core/skills/tools.py:702-716 registers only the
name in tenant_skills); HYD keeps the text in tenant_skills.content so the portal and the worker read the same row.
The portal only reads. A student adds an agent or a skill in the wrap-up (Claude Code → SQL), see
docs/handoff/verification/2026-10-08/u2-agents-skills.md.

`agent_settings()` is the one function that answers "what will this agent run with" — the worker calls it for every run and
a trial run (A10) can call it with any agent id to get the same model · MCP servers · skills · instructions.
This module is copied into the worker image (it/agent-worker/Dockerfile): stdlib + hydcommon only.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field

from hydcommon.timeutil import now_iso

SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
#: where each CLI discovers a skill (cliagents layouts: claude_code.py skill_path · codex.py _SKILL_PATH)
SKILL_ROOTS = {"claude-code": ".claude/skills", "codex": ".agents/skills"}
MODEL_KEYS = ("agent_model", "agentModel", "model")
#: users.role holds a category code in the HYD seed, not a sentence; say it in words where it is shown or prompted
ROLE_WORDS = {"agent": "AI 에이전트", "system": "시스템 수행자", "operator": "운전원", "manager": "관리자"}


def csv_list(value) -> list[str]:
    """users.tools is comma-separated in the product; lists are accepted too."""
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def role_text(role) -> str:
    role = str(role or "").strip()
    return ROLE_WORDS.get(role, role)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """`---\\nname: x\\ndescription: y\\n---\\nbody` → ({name, description}, body). Text without frontmatter → ({}, text)."""
    text = str(text or "")
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:]).lstrip("\n")
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return {}, text          # unterminated: not frontmatter


def skill_markdown(skill: dict) -> str:
    """The SKILL.md the worker writes. Stored text that already has frontmatter is written as is (the wrap-up stores the
    file a student wrote); a bare body gets name · description from the row so the CLI can list it."""
    content = str(skill.get("content") or "")
    meta, _ = split_frontmatter(content)
    if meta.get("name"):
        return content if content.endswith("\n") else content + "\n"
    description = str(skill.get("description") or "").replace("\n", " ").strip()
    return f"---\nname: {skill['skill_name']}\ndescription: {description}\n---\n\n{content.strip()}\n"


def skill_title(skill: dict) -> str:
    """First markdown heading of the body, else the description — what a person reads instead of the folder name."""
    _, body = split_frontmatter(skill.get("content") or "")
    for line in body.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return str(skill.get("description") or "").strip() or skill.get("skill_name") or ""


def activity_capabilities(definition: dict | None, activity_id: str) -> dict:
    """The designer's choices for this activity (the product's core/activity.py): agentConfig{cli, model, permission}, skills, tools."""
    if not isinstance(definition, dict):
        return {}
    for a in definition.get("activities") or []:
        if isinstance(a, dict) and a.get("id") == activity_id:
            config = a.get("agentConfig") or a.get("agent_config") or {}
            return {"agent_config": config if isinstance(config, dict) else {}, "skills": list(a.get("skills") or []),
                    "tools": list(a.get("tools") or a.get("mcpServers") or [])}
    return {}


def _first(config: dict, keys) -> str | None:
    for k in keys:
        v = config.get(k)
        if v not in (None, ""):
            return str(v)
    return None


@dataclass
class AgentSettings:
    """What one run of `agent` on one activity uses. tools None = no declaration anywhere (every tenant server, as before
    U2); [] = the agent's servers and the activity's declaration do not overlap (no MCP server — said out loud by the worker)."""
    agent_id: str | None
    profile: dict | None
    model: str | None = None                 # None = the worker's default model
    model_source: str | None = None          # "activity" | "agent"
    tools: list[str] | None = None
    tools_source: str | None = None          # "agent+activity" | "agent" | "activity"
    skills: list[dict] = field(default_factory=list)          # tenant_skills rows, in assignment order
    missing_skills: list[str] = field(default_factory=list)   # assigned names without a tenant_skills row
    work_rules: str | None = None            # G9: users.work_rules — the business part of the run's constitution (work_rules.py); None = common only

    @property
    def skill_names(self) -> list[str]:
        return [s["skill_name"] for s in self.skills]

    def instructions(self, skill_root: str = SKILL_ROOTS["claude-code"]) -> str:
        """The section the worker adds to the run's prompt (process-gpt-cli-agent core/subagents.py:36-46 joins
        role · goal · persona the same way). Empty for a work item without an agent profile."""
        p = self.profile or {}
        lines = []
        for label, value in (("이름", p.get("username") or p.get("name")), ("역할", role_text(p.get("role"))),
                             ("목표", p.get("goal")), ("성격·말투", p.get("persona"))):
            value = str(value or "").strip()
            if value:
                lines.append(f"- {label}: {value}")
        text = ""
        if lines:
            text = ("## 에이전트 프로필\n당신은 아래 프로필의 에이전트로서 이 업무를 맡습니다. 역할과 목표에 맞게 판단하고, "
                    "성격·말투를 결과 문장에 반영하세요.\n" + "\n".join(lines))
        if self.skills:
            listed = "\n".join(f"- `{s['skill_name']}`" + (f": {s['description']}" if s.get("description") else "")
                               + f" — `{skill_root}/{s['skill_name']}/SKILL.md`" for s in self.skills)
            text += (("\n\n" if text else "") + "## 배정된 스킬\n"
                     f"작업 디렉터리의 `{skill_root}/<이름>/SKILL.md` 에 이 에이전트의 스킬이 있습니다. 업무에 해당하는 스킬을 먼저 읽고 "
                     "그 절차를 따르세요. 스킬은 결과 제출 형식을 바꾸지 않습니다.\n" + listed)
        return text

    def summary(self) -> dict:
        """JSON shape for task.json and the portal: names only, no skill bodies."""
        p = self.profile or {}
        return {"id": self.agent_id, "name": p.get("username") or self.agent_id, "model": self.model, "model_source": self.model_source,
                "tools": self.tools, "tools_source": self.tools_source, "skills": self.skill_names, "missing_skills": list(self.missing_skills),
                "work_rules": self.work_rules}


def agent_settings(repo, tenant_id: str, agent, *, activity: dict | None = None) -> AgentSettings:
    """Read an agent's run settings from the one source (users · agent_skills · tenant_skills) and the activity's declaration.

    agent: a users.id, a users row, or None (a work item without an agent profile — only the activity's declaration counts).
    activity: activity_capabilities(definition, activity_id) of the step it runs, or None (e.g. a trial run outside a step).
    Model: the activity's agentConfig model (the designer's explicit choice) > the agent's model > None (worker default).
    Tools: agent servers ∩ activity servers when both are named, else whichever is named, else None (every tenant server).
    Skills: activity skills ∪ the agent's agent_skills rows; names without a stored body go to missing_skills.
    Raises LookupError for an id that is not an agent of this tenant."""
    caps = activity or {}
    if isinstance(agent, str):
        rows = [u for u in repo.list_users([agent], tenant_id) if u.get("is_agent")]
        if not rows:
            raise LookupError(f"그런 에이전트가 없습니다: {agent}")
        profile = rows[0]
    else:
        profile = agent or None
    agent_id = profile.get("id") if profile else None

    model, model_source = _first(caps.get("agent_config") or {}, MODEL_KEYS), "activity"
    if not model and profile and str(profile.get("model") or "").strip():
        model, model_source = str(profile["model"]).strip(), "agent"
    if not model:
        model_source = None

    agent_tools = csv_list(profile.get("tools")) if profile else []
    act_tools = [str(t) for t in caps.get("tools") or []]
    if agent_tools and act_tools:
        tools, tools_source = [t for t in act_tools if t in agent_tools], "agent+activity"
    elif agent_tools:
        tools, tools_source = agent_tools, "agent"
    elif act_tools:
        tools, tools_source = act_tools, "activity"
    else:
        tools, tools_source = None, None

    names = [str(n) for n in caps.get("skills") or []]
    if agent_id:
        names += [r["skill_name"] for r in repo.list_agent_skills(tenant_id, agent_id)]
    names = list(dict.fromkeys(names))
    rows = {r["skill_name"]: r for r in repo.list_skills(tenant_id, names)} if names else {}
    return AgentSettings(agent_id=agent_id, profile=profile, model=model, model_source=model_source, tools=tools, tools_source=tools_source,
                         skills=[rows[n] for n in names if n in rows], missing_skills=[n for n in names if n not in rows],
                         work_rules=(str(profile.get("work_rules") or "").strip() or None) if profile else None)


# ---------------------------------------------------------------- repositories (read only; MemoryRepo also seeds for tests)
class MemoryAgents:
    def _skill_rows(self) -> dict:
        if not hasattr(self, "_skills"):
            self._skills = {}
        return self._skills

    def _agent_skill_rows(self) -> list:
        if not hasattr(self, "_agent_skills"):
            self._agent_skills = []
        return self._agent_skills

    def list_skills(self, tenant_id: str = "hyd", names: list[str] | None = None) -> list[dict]:
        return [deepcopy(s) for (t, n), s in sorted(self._skill_rows().items()) if t == tenant_id and (names is None or n in names)]

    def get_skill(self, tenant_id: str, name: str) -> dict | None:
        row = self._skill_rows().get((tenant_id, name))
        return deepcopy(row) if row else None

    def list_agent_skills(self, tenant_id: str = "hyd", user_id: str | None = None) -> list[dict]:
        return [deepcopy(r) for r in self._agent_skill_rows() if r["tenant_id"] == tenant_id and (user_id is None or r["user_id"] == user_id)]

    # what the wrap-up's SQL does against Supabase — the in-memory repo needs it to stand in (tests, PROCESS_REPO=memory)
    def put_skill(self, skill: dict) -> None:
        if not SKILL_NAME_RE.match(skill["skill_name"]):
            raise ValueError(f"스킬 이름은 소문자·숫자·하이픈만 씁니다: {skill['skill_name']}")
        key = (skill.get("tenant_id") or "hyd", skill["skill_name"])
        self._skill_rows()[key] = {"description": "", "content": "", **skill, "tenant_id": key[0], "updated_at": now_iso()}

    def attach_skill(self, user_id: str, skill_name: str, tenant_id: str = "hyd") -> None:
        if (tenant_id, skill_name) not in self._skill_rows():          # the FK of agent_skills → tenant_skills
            raise ValueError(f"없는 스킬입니다: {skill_name}")
        if not any(r["user_id"] == user_id and r["tenant_id"] == tenant_id and r["skill_name"] == skill_name for r in self._agent_skill_rows()):
            self._agent_skill_rows().append({"user_id": user_id, "tenant_id": tenant_id, "skill_name": skill_name, "created_at": now_iso()})


class PgAgents:
    def list_skills(self, tenant_id: str = "hyd", names: list[str] | None = None) -> list[dict]:
        with self._conn() as c:
            if names is None:
                rows = c.execute("select * from tenant_skills where tenant_id = %s order by skill_name", (tenant_id,)).fetchall()
            else:
                rows = c.execute("select * from tenant_skills where tenant_id = %s and skill_name = any(%s) order by skill_name",
                                 (tenant_id, list(names))).fetchall()
            return [self._row(r) for r in rows]

    def get_skill(self, tenant_id: str, name: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("select * from tenant_skills where tenant_id = %s and skill_name = %s", (tenant_id, name)).fetchone())

    def list_agent_skills(self, tenant_id: str = "hyd", user_id: str | None = None) -> list[dict]:
        with self._conn() as c:
            if user_id is None:
                rows = c.execute("select * from agent_skills where tenant_id = %s order by user_id, created_at, skill_name", (tenant_id,)).fetchall()
            else:
                rows = c.execute("select * from agent_skills where tenant_id = %s and user_id = %s order by created_at, skill_name",
                                 (tenant_id, user_id)).fetchall()
            return [self._row(r) for r in rows]
