"""B1 HTTP routes: 에이전트 · 스킬 만들기 · 고치기 · 지우기 · 붙이기, 단계 → 에이전트 · 역할 → 사람 배정, 되돌리기. 로직은 agent_authoring.py.

    GET    /api/agent-authoring/options                  폼 선택지: 등록된 도구 서버(tenants.mcp, 검사 상태가 있으면 함께) · 스킬 · 모델 예시
    POST   /api/agents                                   새 에이전트 {name, role, goal, persona, model, tools[], skills[]} → origin=user
    PUT    /api/agents/{id}                              고치기(내가 만든 것만 — 기본은 403 + 사유)
    DELETE /api/agents/{id}                              지우기(내가 만든 것만; 실행 중이면 409, 열린 단계는 기본 담당으로 되돌림)
    POST   /api/agents/{id}/clone                        복제해서 고치기 {name?} — 기본 에이전트도 됨(사본은 origin=user)
    POST   /api/agents/{id}/skills                       {skill_name} 붙이기  ·  DELETE /api/agents/{id}/skills/{name} 떼기
    POST   /api/skills                                   새 스킬 {skill_name, description, content(SKILL.md)} — 빈 본문 · 이름 중복은 거절
    PUT    /api/skills/{name} · DELETE /api/skills/{name}  내가 만든 스킬만
    GET    /api/agent-assignments                        단계 → 담당 에이전트(기본 · 배정) 표
    PUT    /api/agent-assignments                        {definition_id, activity_id, agent_id}
    DELETE /api/agent-assignments/{definition_id}/{activity_id}   배정 지우기 → 다음에 열리는 단계부터 기본 담당
    POST   /api/role-members                             {role_id, user_id} 역할에 사람 넣기 · DELETE /api/role-members?role_id=&user_id= (넣은 것만)
    POST   /api/agents/reset                             기준으로 되돌리기: 내가 만든 에이전트 · 스킬 · 배정 · 업무분장만 지움

거절은 모두 사람이 읽을 사유(detail)와 함께: 403 기본 보호 · 404 없음 · 409 중복/실행 중 · 422 입력. 409 unless PROCESS_MODE=instance.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import agent_authoring as A
from .instance_mode import _in_executor, _rt


class AgentReq(BaseModel):
    name: str = ""
    role: str = ""
    goal: str = ""
    persona: str = ""
    model: str = ""
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    by: str | None = None


class CloneReq(BaseModel):
    name: str = ""
    by: str | None = None


class SkillReq(BaseModel):
    skill_name: str = ""
    description: str = ""
    content: str = ""
    by: str | None = None


class AttachReq(BaseModel):
    skill_name: str = Field(min_length=1, max_length=64)


class MapReq(BaseModel):
    definition_id: str = Field(min_length=1, max_length=200)
    activity_id: str = Field(min_length=1, max_length=200)
    agent_id: str = Field(min_length=1, max_length=200)
    by: str | None = None


class MemberReq(BaseModel):
    role_id: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)


class ResetReq(BaseModel):
    by: str | None = None


async def _call(fn, *args, **kwargs):
    try:
        return await _in_executor(lambda: fn(*args, **kwargs))
    except A.AuthoringError as e:
        raise HTTPException(e.status, e.message)


def mount(app: FastAPI) -> None:
    @app.get("/api/agent-authoring/options")
    async def options():
        rt = _rt()

        def work():
            agents = [u for u in rt.repo.list_users(None, rt.tenant_id) if u.get("is_agent")]
            models = sorted({str(u.get("model")).strip() for u in agents if str(u.get("model") or "").strip()})
            return {"servers": A.server_options(rt.repo, rt.tenant_id),
                    "skills": [{"skill_name": s["skill_name"], "description": s.get("description") or "", "origin": A.origin_of(s)}
                               for s in rt.repo.list_skills(rt.tenant_id)],
                    "models": models}
        return await _in_executor(work)

    @app.post("/api/agents/reset")
    async def reset(req: ResetReq | None = None):
        rt = _rt()
        return await _call(A.reset, rt, by=(req.by if req else None))

    @app.post("/api/agents", status_code=201)
    async def create_agent(req: AgentReq):
        rt = _rt()
        return await _call(A.create_agent, rt.repo, rt.tenant_id, req.model_dump(), by=req.by)

    @app.put("/api/agents/{agent_id}")
    async def update_agent(agent_id: str, req: AgentReq):
        rt = _rt()
        return await _call(A.update_agent, rt.repo, rt.tenant_id, agent_id, req.model_dump(), by=req.by)

    @app.delete("/api/agents/{agent_id}")
    async def delete_agent(agent_id: str, by: str | None = None):
        rt = _rt()
        return await _call(A.delete_agent, rt, agent_id, by=by)

    @app.post("/api/agents/{agent_id}/clone", status_code=201)
    async def clone_agent(agent_id: str, req: CloneReq | None = None):
        rt = _rt()
        body = req.model_dump() if req else {}
        return await _call(A.clone_agent, rt.repo, rt.tenant_id, agent_id, body, by=body.get("by"))

    @app.post("/api/agents/{agent_id}/skills")
    async def attach_skill(agent_id: str, req: AttachReq):
        rt = _rt()
        return await _call(A.attach_skill, rt.repo, rt.tenant_id, agent_id, req.skill_name)

    @app.delete("/api/agents/{agent_id}/skills/{skill_name}")
    async def detach_skill(agent_id: str, skill_name: str):
        rt = _rt()
        return await _call(A.detach_skill, rt.repo, rt.tenant_id, agent_id, skill_name)

    @app.post("/api/skills", status_code=201)
    async def create_skill(req: SkillReq):
        rt = _rt()
        return await _call(A.create_skill, rt.repo, rt.tenant_id, req.model_dump(), by=req.by)

    @app.put("/api/skills/{name}")
    async def update_skill(name: str, req: SkillReq):
        rt = _rt()
        return await _call(A.update_skill, rt.repo, rt.tenant_id, name, req.model_dump(), by=req.by)

    @app.delete("/api/skills/{name}")
    async def delete_skill(name: str):
        rt = _rt()
        return await _call(A.delete_skill, rt.repo, rt.tenant_id, name)

    @app.get("/api/agent-assignments")
    async def assignments():
        rt = _rt()
        return await _call(A.assignment_board, rt)

    @app.put("/api/agent-assignments")
    async def set_assignment(req: MapReq):
        rt = _rt()
        return await _call(A.set_assignment, rt, req.definition_id, req.activity_id, req.agent_id, by=req.by)

    @app.delete("/api/agent-assignments/{definition_id}/{activity_id}")
    async def clear_assignment(definition_id: str, activity_id: str):
        rt = _rt()
        return await _call(A.clear_assignment, rt, definition_id, activity_id)

    @app.post("/api/role-members", status_code=201)
    async def add_member(req: MemberReq):
        rt = _rt()
        return await _call(A.add_member, rt.repo, rt.tenant_id, req.role_id, req.user_id)

    @app.delete("/api/role-members")
    async def remove_member(role_id: str, user_id: str):
        rt = _rt()
        return await _call(A.remove_member, rt.repo, rt.tenant_id, role_id, user_id)

