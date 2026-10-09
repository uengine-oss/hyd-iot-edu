"""What the work item row does not carry: the form (output contract), the people and agents, the tenant's MCP servers.

The product's ProcessGPTRequestContext.prepare_context (processgpt_agent_sdk/processgpt_agent_framework.py) gathers the
same bundle: form_def by the row's tool, users split into agents/users, tenants.mcp, notify emails, sources, feedback.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any
from hydcommon.process_contracts import pinned_form
from procsvc import mcp_secrets
from procsvc.agents_store import activity_capabilities as _activity_capabilities

from . import bridge, env_guard

log = logging.getLogger("worker.context")

FREEFORM_FIELDS = [{"key": "freeform", "type": "textarea", "text": "자유형식 입력"}]


@dataclass
class Context:
    row: dict
    form_id: str
    form_fields: list[dict]
    form_html: str | None = None
    agents: list[dict] = field(default_factory=list)
    users: list[dict] = field(default_factory=list)
    tenant_mcp: dict | None = None
    notify_user_emails: str = ""
    feedback: str = ""                 # the product summarises long feedback with an LLM; here the text is passed as is
    human_answer: str = ""             # a person's answer to the agent's question (HITL resume)
    sources: list[dict] = field(default_factory=list)
    definition: dict | None = None     # proc_def.definition — the designer's agentConfig/skills per activity live here
    profile: dict | None = None        # U2: the agent this item is assigned to (users row) — its settings: agents_store.agent_settings

    @property
    def extras(self) -> dict[str, Any]:
        return {"id": self.row.get("id"), "proc_inst_id": self.row.get("root_proc_inst_id") or self.row.get("proc_inst_id"),
                "activity_name": self.row.get("activity_name"), "agents": self.agents, "users": self.users, "tenant_mcp": bridge.without_secrets(self.tenant_mcp),
                "form_fields": self.form_fields, "form_html": self.form_html, "form_id": self.form_id,
                "notify_user_emails": self.notify_user_emails, "summarized_feedback": self.feedback, "sources": self.sources,
                "process_scope": process_scope(self.row)}


def process_scope(row):
    return {'tenant': row.get('tenant_id'), 'instance': row.get('proc_inst_id'), 'workitem': row.get('id'),
            'generation': int(row.get('generation') or 0), 'version': row.get('version'), 'consumer': row.get('consumer')}


def prepare(repo, row: dict, tenant_id: str) -> Context:
    """Read the bundle for one claimed row. Version-owned forms are authoritative; pre-contract definitions use the legacy form table."""
    if row.get('tenant_id',tenant_id) != tenant_id:
        raise ValueError('다른 테넌트의 작업입니다')
    definition = None
    form = None
    tool = row.get('tool') or ''
    if row.get('proc_def_id'):
        if not row.get('version'):
            raise LookupError('작업의 고정 정의 버전이 없습니다')
        definition = (repo.get_proc_def(row['proc_def_id'],tenant_id,version=row['version']) or {}).get('definition')
        if not definition:
            raise LookupError('작업의 고정 정의를 찾을 수 없습니다')
        activity = next((a for a in definition.get('activities',[]) if a['id']==row['activity_id']),None)
        if activity is None:
            raise ValueError('정의에 없는 작업입니다')
        tool = activity.get('tool') or tool
        form = pinned_form(definition,tool)
    form_id = tool.split(':',1)[1] if tool.startswith('formHandler:') else tool
    if form is None and form_id:
        form = repo.get_form(form_id,tenant_id)
    fields = (form or {}).get('fields_json')
    if fields is None:
        fields = FREEFORM_FIELDS
    user_ids = [u.strip() for u in (row.get("user_id") or "").split(",") if u.strip()]
    people = repo.list_users(user_ids, tenant_id) if user_ids else []
    agents = [u for u in people if u.get("is_agent")]
    users = [u for u in people if not u.get("is_agent")]
    tenant = repo.get_tenant(tenant_id) or {}
    tenant_mcp = with_secrets(repo, tenant_id, tenant.get("mcp"))
    feedback = row.get("feedback") or {}
    if isinstance(feedback, str):
        feedback = {"text": feedback}
    return Context(row=row, form_id=form_id or "freeform", form_fields=fields, form_html=(form or {}).get("html"), agents=agents, users=users,
                   tenant_mcp=tenant_mcp, notify_user_emails=",".join(u.get("email") for u in users if u.get("email")),
                   feedback=str(feedback.get("text") or "") if feedback else "", human_answer=str(feedback.get("human_answer") or "") if feedback else "",
                   sources=[], definition=definition, profile=agent_profile(agents))


def with_secrets(repo, tenant_id: str, tenant_mcp: dict | None) -> dict | None:
    """G2: the values of the `${SECRET:KEY}` placeholders the tenant's servers name (mcp_secrets table, then HYD_SECRET_* the
    worker held back from its environment — env_guard). Only bridge.install reads them; a lookup failure leaves them out, and the
    gate then names the missing secret instead of starting the server with an empty token."""
    if not isinstance(tenant_mcp, dict) or not any(mcp_secrets.references(s) for s in (tenant_mcp.get("mcpServers") or {}).values()
                                                   if isinstance(tenant_mcp.get("mcpServers"), dict)):
        return tenant_mcp
    try:
        values = mcp_secrets.load(repo, tenant_id, environ={**os.environ, **env_guard.held_secrets()})
    except Exception as e:  # noqa: BLE001 — a missing table or a DB hiccup must not fail the claim
        log.warning("MCP secret lookup failed: %s", e)
        values = mcp_secrets.env_values({**os.environ, **env_guard.held_secrets()})
    return bridge.attach_secrets(tenant_mcp, values)


def agent_profile(agents: list[dict]) -> dict | None:
    """The agent this work item is assigned to (row.user_id → users). A system performer (SCADA · process · CMMS) is not a
    profile; among several, the first real agent wins (the product's root agent is agents[0] as well)."""
    for a in agents:
        if (a.get("agent_type") or "agent") == "agent":
            return a
    return None


def activity_capabilities(definition: dict | None, activity_id: str) -> dict:
    """The designer's choices for this activity: agentConfig{cli, model, permission}, skills, tools (shared with the
    process service — procsvc/agents_store.py; the runner looks it up here so a test can replace it)."""
    return _activity_capabilities(definition, activity_id)
