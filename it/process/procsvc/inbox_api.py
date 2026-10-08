"""U5 HTTP routes: 나(사람 사용자) · 내 작업함 · 알림 · 업무분장(읽기). 로직은 inbox.py, 저장은 procdb.

    GET  /api/inbox/users                         사람 사용자(포털의 "나" 선택지)와 각자의 역할
    GET  /api/inbox?user_id=                      내 작업함: tasks(me | role) · asked(에이전트 질문) · unassigned_roles · unread
    GET  /api/inbox/assignments                   업무분장(역할 → 사람, 읽기 전용 — 바꾸는 곳은 seed/랩업)
    GET  /api/todolist/{wid}/assignments          담당자 해석 이력(업무분장으로 사람에게 바로 배정된 것)
    GET  /api/inbox/notifications?user_id=&unread=1&limit=   알림 목록(나 + 내 역할 앞으로 온 것, 각 행에 포털 link)
    GET  /api/inbox/notifications/unread-count?user_id=
    POST /api/inbox/notifications/read            {user_id, ids?}  읽음 처리(ids 없으면 모두)
    GET  /api/inbox/notifications/stream?user_id= 새 알림 실시간(SSE, /api/events/stream 과 같은 생성기)

권한: HYD 포털에는 로그인이 없어 user_id 를 호출자가 준다(기존 by·role 과 같은 수준). 승인 권한(역할 403)은 /select 가 그대로 검사하고,
"나"(user:*)로 승인하면 그 사람이 내세운 역할의 구성원인지도 본다(inbox.check_actor). 수동 재배정·위임·외부 알림은 범위 밖(TODO A3).
409 unless PROCESS_MODE=instance (instance_mode._rt)."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import inbox, instance_mode
from .instance_mode import _in_executor, _rt


class ReadReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    ids: list[str] | None = None


def _person(rt, user_id: str) -> dict:
    user = next((u for u in rt.repo.list_users([user_id], rt.tenant_id)), None)
    if user is None or not user_id.startswith(inbox.PERSON) or user.get("is_agent"):
        raise HTTPException(404, f"없는 사람 사용자입니다: {user_id}")
    return user


def mount(app: FastAPI) -> None:
    @app.get("/api/inbox/users")
    async def inbox_users():
        rt = _rt()
        return await _in_executor(lambda: inbox.assignment_board(rt.repo, rt.tenant_id)["people"])

    @app.get("/api/inbox")
    async def my_inbox(user_id: str):
        rt = _rt()
        try:
            return await _in_executor(inbox.inbox_view, rt, user_id)
        except LookupError as e:
            raise HTTPException(404, str(e))

    @app.get("/api/inbox/assignments")
    async def assignments():
        rt = _rt()
        return await _in_executor(inbox.assignment_board, rt.repo, rt.tenant_id)

    @app.get("/api/todolist/{wid}/assignments")
    async def task_assignments(wid: str):
        rt = _rt()
        wi = await _in_executor(rt.repo.get_workitem, wid)
        if not wi or wi.get("tenant_id") != rt.tenant_id:
            raise HTTPException(404, "no such work item")
        return await _in_executor(rt.repo.list_assignments, wid, rt.tenant_id)

    @app.get("/api/inbox/notifications")
    async def notifications(user_id: str, unread: bool = False, limit: int = 100):
        rt = _rt()
        await _in_executor(_person, rt, user_id)
        ids = await _in_executor(inbox.user_ids_for, rt.repo, rt.tenant_id, user_id)
        rows = await _in_executor(rt.repo.list_notifications, rt.tenant_id, ids, unread, min(max(limit, 1), 500))
        return await _in_executor(inbox.with_links, rt.repo, rows)

    @app.get("/api/inbox/notifications/unread-count")
    async def unread_count(user_id: str):
        rt = _rt()
        await _in_executor(_person, rt, user_id)
        ids = await _in_executor(inbox.user_ids_for, rt.repo, rt.tenant_id, user_id)
        return {"user_id": user_id, "unread": await _in_executor(rt.repo.count_unread_notifications, rt.tenant_id, ids)}

    @app.post("/api/inbox/notifications/read")
    async def mark_read(req: ReadReq):
        rt = _rt()
        await _in_executor(_person, rt, req.user_id)
        for nid in req.ids or []:
            try:
                uuid.UUID(nid)
            except ValueError:
                raise HTTPException(400, f"알림 id 형식이 아닙니다: {nid[:60]}")
        ids = await _in_executor(inbox.user_ids_for, rt.repo, rt.tenant_id, req.user_id)
        n = await _in_executor(rt.repo.mark_notifications_read, rt.tenant_id, ids, req.ids)
        return {"user_id": req.user_id, "marked": n, "unread": await _in_executor(rt.repo.count_unread_notifications, rt.tenant_id, ids)}

    @app.get("/api/inbox/notifications/stream")
    async def notifications_stream(request: Request, user_id: str, since: str | None = None):
        """새 알림을 생기는 즉시 보낸다(나 + 내 역할 앞으로 온 것만) — /api/events/stream 과 같은 생성기, 커서는 created_at."""
        rt = _rt()
        await _in_executor(_person, rt, user_id)
        mine = set(await _in_executor(inbox.user_ids_for, rt.repo, rt.tenant_id, user_id))

        def fetch(since_, limit):                                     # 내 것만 DB 에서 고른다(남의 알림은 보내지 않는다)
            return inbox.with_links(rt.repo, rt.repo.list_notifications_since(since_, limit, rt.tenant_id, sorted(mine)))
        return StreamingResponse(instance_mode.event_stream(rt.repo, since, request.is_disconnected, fetch=fetch, ts_key="created_at", history=20),
                                 media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
