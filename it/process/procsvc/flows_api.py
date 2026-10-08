"""B3: bpmn.io 그림 가져오기 API — 매핑 · 사전 검사 · 판본 등록 · 그림 다시 받기 · 기준으로 되돌리기.

  GET  /api/flows/catalog                        부품(기준 정의에서 읽은 시나리오 부품 + 일반 부품) · 역할 · 에이전트 · 경보 패턴
  POST /api/flows/import {xml, file_name, definition_id?}
                                                 .bpmn 읽기 → 같은 흐름 id 의 앞선 매핑 유지 → 초안 저장 → 사전 검사 결과
  GET  /api/flows                                내가 가져온 흐름(초안) · 등록한 판본
  GET  /api/flows/{id}                           초안 하나(읽은 그림 · 매핑 · 사전 검사 · 판본)
  PUT  /api/flows/{id}/mapping {mapping}         매핑 저장 + 사전 검사
  POST /api/flows/{id}/check {mapping?}          사전 검사만(저장 없음)
  POST /api/flows/{id}/register {mapping?}       검사 통과 시 새 판본 등록(정의 JSON + .bpmn 원본). 운영 판본 포인터는 그대로(배포는 B4)
  GET  /api/flows/{id}/versions/{v}/bpmn         그 판본의 그림(.bpmn) 내려받기
  POST /api/flows/reset                          기준으로 되돌리기: 내가 가져온 정의 · 판본 · 초안만 지움

거절은 사람이 읽을 사유와 칸 위치: 400 {reason, problems:[{where:{kind, kind_label, id, name}, field, reason}]}.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from . import bpmn_import
from .bpmn_store import FlowBusy, FlowStore, next_version


class ImportReq(BaseModel):
    xml: str
    file_name: str | None = None
    definition_id: str | None = None


class MappingReq(BaseModel):
    mapping: dict | None = None


def default_base_loader(rt) -> dict:
    """부품의 원천 = 기준 정의 파일(it/process/definitions/<PROCESS_DEFINITION_FILE>). 학생 판본이 배포돼도 부품은 기준에서 읽는다."""
    from . import instance_mode
    path = Path(instance_mode.DEFINITIONS_DIR) / instance_mode.DEFINITION_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return rt.defn.raw


def register(app, *, runtime_factory, audit=lambda *a, **k: None, base_loader=default_base_loader):
    def runtime():
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(503, "흐름 가져오기에는 instance 실행 서비스가 필요합니다 (PROCESS_MODE=instance)")
        return rt

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except KeyError as exc:
            raise HTTPException(404, str(exc.args[0]) if exc.args else "찾을 수 없습니다") from exc

    def catalog_of(rt) -> dict:
        return bpmn_import.catalog(base_loader(rt), rt.repo.list_users(None, rt.tenant_id))

    def ctx_for(rt, store, cat, def_id, draft) -> dict:
        existing = [v["version"] for v in store.versions(def_id)]
        return {"catalog": cat, "definition_id": def_id, "version": next_version(existing), "file_name": draft.get("file_name"),
                "xml_sha256": bpmn_import.xml_sha256(draft["bpmn"]), "name": None}

    def view(rt, store, cat, def_id, draft, mapping, report=None) -> dict:
        parsed = bpmn_import.parse_bpmn(draft["bpmn"])
        result = bpmn_import.check(parsed, mapping, ctx_for(rt, store, cat, def_id, draft))
        return {"definition_id": def_id, "file_name": draft.get("file_name"), "parsed": parsed, "mapping": mapping,
                "reimport": report, "check": result, "next_version": result["definition"]["version"],
                "versions": store.versions(def_id), "base": cat["base"]}

    def draft_of(store, def_id) -> dict:
        draft = store.get_draft(def_id)
        if draft is None:
            raise KeyError(f"가져온 그림이 없습니다: {def_id} — 먼저 .bpmn 파일을 가져오세요")
        return draft

    @app.get("/api/flows/catalog")
    async def flows_catalog():
        rt = runtime()
        return await run(lambda: catalog_of(rt))

    @app.post("/api/flows/import")
    async def flows_import(req: ImportReq):
        rt = runtime()
        def work():
            try:
                parsed = bpmn_import.parse_bpmn(req.xml)
            except bpmn_import.BpmnError as e:
                raise HTTPException(400, {"reason": str(e), "problems": e.problems})
            def_id = (req.definition_id or "").strip() or bpmn_import.suggest_definition_id(parsed)
            if not bpmn_import.valid_definition_id(def_id):
                raise HTTPException(400, {"reason": f"흐름 id '{def_id}'은(는) 쓸 수 없습니다 — 영문자로 시작하고 영문 · 숫자 · _ . - 만 (64자까지)"})
            store = FlowStore(rt.repo, rt.tenant_id)
            if store.is_protected(def_id):
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 기준 흐름 id 입니다 — 기준은 바꾸지 않습니다. 다른 흐름 id 를 쓰세요"})
            cat = catalog_of(rt)
            old = store.get_draft(def_id)
            mapping, report = bpmn_import.merge_mapping(parsed, (old or {}).get("mapping"), cat)
            report["previous"] = old is not None
            draft = {"bpmn": req.xml, "file_name": req.file_name}
            store.save_draft(def_id, req.xml, req.file_name, mapping)
            return view(rt, store, cat, def_id, draft, mapping, report)
        return await run(work)

    @app.get("/api/flows")
    async def flows_list():
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            return {"drafts": store.drafts(), "versions": store.versions()}
        return await run(work)

    @app.post("/api/flows/reset")
    async def flows_reset():
        rt = runtime()
        def work():
            try:
                out = FlowStore(rt.repo, rt.tenant_id).reset()
            except FlowBusy as e:
                raise HTTPException(409, {"reason": str(e), "running": e.running})
            audit("-", "portal", "FLOWS_RESET", out)
            return out
        return await run(work)

    @app.get("/api/flows/{def_id}")
    async def flows_get(def_id: str):
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            draft = draft_of(store, def_id)
            return view(rt, store, catalog_of(rt), def_id, draft, draft.get("mapping") or {})
        return await run(work)

    @app.put("/api/flows/{def_id}/mapping")
    async def flows_mapping(def_id: str, req: MappingReq):
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            draft = draft_of(store, def_id)
            mapping = req.mapping if isinstance(req.mapping, dict) else {}
            store.save_mapping(def_id, mapping)
            return view(rt, store, catalog_of(rt), def_id, draft, mapping)
        return await run(work)

    @app.post("/api/flows/{def_id}/check")
    async def flows_check(def_id: str, req: MappingReq):
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            draft = draft_of(store, def_id)
            mapping = req.mapping if isinstance(req.mapping, dict) else (draft.get("mapping") or {})
            return view(rt, store, catalog_of(rt), def_id, draft, mapping)
        return await run(work)

    @app.post("/api/flows/{def_id}/register", status_code=201)
    async def flows_register(def_id: str, req: MappingReq):
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            draft = draft_of(store, def_id)
            if store.is_protected(def_id):
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 기준 흐름 id 입니다 — 기준은 바꾸지 않습니다"})
            mapping = req.mapping if isinstance(req.mapping, dict) else (draft.get("mapping") or {})
            if isinstance(req.mapping, dict):
                store.save_mapping(def_id, mapping)
            cat = catalog_of(rt)
            parsed = bpmn_import.parse_bpmn(draft["bpmn"])
            result = bpmn_import.check(parsed, mapping, ctx_for(rt, store, cat, def_id, draft))
            if not result["ok"]:
                first = result["problems"][0]
                where = first.get("where") or {}
                at = f"{where.get('kind_label', '')} {where.get('name') or where.get('id') or ''}".strip()
                raise HTTPException(400, {"reason": f"사전 검사를 통과하지 못해 등록하지 않았습니다 ({len(result['problems'])}건) — "
                                                    f"{at + ': ' if at else ''}{first['reason']}", "problems": result["problems"]})
            try:
                raw = store.register(result["definition"], draft["bpmn"], draft.get("file_name"))
            except ValueError as e:
                raise HTTPException(409, {"reason": str(e)})
            audit("-", "portal", "FLOW_REGISTERED", {"definition": def_id, "version": raw["version"], "file": draft.get("file_name"),
                                                     "origin": "user"})
            return {"definition_id": def_id, "version": raw["version"], "name": raw.get("processDefinitionName"), "origin": "user",
                    "deployed": False, "start": (mapping.get("start") or {}).get("kind"), "definition": raw}
        return await run(work)

    @app.get("/api/flows/{def_id}/versions/{version}/bpmn")
    async def flows_bpmn(def_id: str, version: str):
        rt = runtime()
        def work():
            xml = FlowStore(rt.repo, rt.tenant_id).bpmn_of(def_id, version)
            if not xml:
                raise HTTPException(404, {"reason": f"{def_id} 판본 {version} 의 그림 원본이 없습니다 (포털로 가져와 등록한 판본만 그림이 있습니다)"})
            return xml
        xml = await run(work)
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in f"{def_id}-v{version}")
        return Response(content=xml, media_type="application/xml",
                        headers={"Content-Disposition": f'attachment; filename="{safe}.bpmn"'})
