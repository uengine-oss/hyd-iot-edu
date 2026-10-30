"""B3: bpmn.io 그림 가져오기 API — 매핑 · 사전 검사 · 판본 등록 · 그림 다시 받기 · 기준으로 되돌리기.

  GET  /api/flows/catalog                        부품(기준 정의에서 읽은 시나리오 부품 + 일반 부품) · 역할 · 에이전트 · 경보 패턴
  POST /api/flows/import {xml, file_name, definition_id?, start_patterns?}
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

from . import bpmn_import, mcp_dependencies
from .bpmn_store import FlowBusy, FlowStore, next_version


class ImportReq(BaseModel):
    xml: str
    file_name: str | None = None
    definition_id: str | None = None
    # 새 경보 초안에만 적용. None은 기존 센서 기본값, []는 명시적으로 미선택.
    start_patterns: list[str] | None = None
    # 수업 흐름 설치(course_bootstrap — 시작.bat, 프로세스 안 호출)만 true — 지금 수업 흐름으로 배포된 흐름 id 를 다시 가져온다.
    class_flow: bool = False


class MappingReq(BaseModel):
    mapping: dict | None = None
    class_flow: bool = False          # 수업 흐름의 판본 등록은 수업 흐름 설치(course_bootstrap)만 이 표시를 보낸다 — 밖에서 보내면 course_policy 가 거절한다


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
            from .instances import NOT_READY      # 런타임 모듈 — 이 모듈이 먼저 읽혀도 순환 import 가 되지 않게 여기서
            raise HTTPException(503, NOT_READY)
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
        from .instance_mode import EFFECT_MCP_SERVERS
        result['dependencies'] = mcp_dependencies.for_repo(rt.repo, rt.tenant_id, parsed, mapping, tuple(EFFECT_MCP_SERVERS))
        return {"definition_id": def_id, "file_name": draft.get("file_name"), "parsed": parsed, "mapping": mapping,
                "reimport": report, "check": result, "next_version": result["definition"]["version"],
                "versions": store.versions(def_id), "base": cat["base"]}

    def course(check):
        """수업 경계(course_policy) 판정 — 거절은 학생이 읽을 까닭과 403."""
        from .course_policy import AccessDenied
        try:
            check(app.state.course)
        except AccessDenied as exc:
            raise HTTPException(403, str(exc)) from None

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
            if not req.class_flow:
                course(lambda policy: policy.import_flow(req.xml, def_id))
            store = FlowStore(rt.repo, rt.tenant_id)
            if store.is_protected(def_id):
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 기준 흐름 id 입니다 — 기준은 바꾸지 않습니다. 다른 흐름 id 를 쓰세요"})
            # 2026-10-25 학생 행위 점검: 수업 흐름 id 로 가져오면 강사 초안을 덮고, 등록 · 배포하면 수업 흐름 표시가 없는 판본이
            # 경보를 가져가 [기준 흐름으로 되돌리기]가 그 흐름을 내렸다(B · C 버튼 멈춤). 판정은 지금 배포의 수업 흐름 표시로 한다.
            if not req.class_flow and any(h['id'] == def_id and h.get('class_flow') for h in rt.repo.deployed_heads(rt.tenant_id)):
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 강사가 배포한 수업 흐름 id 입니다 — 내 흐름 id 를 따로 쓰세요(예: my_{def_id.split('_')[-1]})"})
            cat = catalog_of(rt)
            old = store.get_draft(def_id)
            mapping, report = bpmn_import.merge_mapping(parsed, (old or {}).get("mapping"), cat)
            if old is None and req.start_patterns is not None and mapping["start"].get("kind") == "alert":
                mapping["start"]["patterns"] = list(req.start_patterns)
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
            from .flow_deploy import routes
            deployed = {f["definition"] for f in routes(rt)["flows"]}     # 경보 경로에 배포된 흐름(수업 흐름 포함)은 남긴다
            try:
                out = FlowStore(rt.repo, rt.tenant_id).reset(keep=deployed)
            except FlowBusy as e:
                raise HTTPException(409, {"reason": str(e), "running": e.running})
            for pid in out.pop("projection_instances", []):
                rt._project({"proc_inst_id": pid})
            rt.cleanup_removed_definitions()
            audit("-", "portal", "FLOWS_RESET", out)
            return out
        return await run(work)

    @app.delete("/api/flows/{def_id}")
    async def flows_delete(def_id: str, by: str = "portal"):
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            if store.is_protected(def_id):
                raise HTTPException(403, {"reason": "수업 기준 흐름은 삭제할 수 없습니다"})
            if not store.get_draft(def_id) and not store.versions(def_id):
                raise HTTPException(404, {"reason": "삭제할 학생 흐름이 없습니다"})
            # [기준으로 되돌리기](flows_reset)의 keep 과 같은 기준: 경보 경로에 배포된 흐름(수업 흐름 포함)은 지우지 않는다.
            # 지우면 경보가 조용히 기준 흐름으로 돌아가고 그 흐름의 시나리오 버튼이 '배포되어 있지 않습니다'로 멈춘다.
            from .flow_deploy import routes
            deployed = next((f for f in routes(rt)["flows"] if f["definition"] == def_id), None)
            if deployed is not None:
                patterns = ", ".join(deployed.get("patterns") or []) or "경보 패턴 없음"
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 지금 경보 경로에 배포된 흐름입니다(판본 {deployed.get('version')}, "
                                                    f"경보 {patterns}) — 지우지 않았습니다. 먼저 배포를 내리세요"
                                                    "(흐름 배포 화면의 [기준 흐름으로 되돌리기]) 뒤에 지우세요",
                                          "deployed": deployed})
            try:
                out = store.reset(def_id)
            except FlowBusy as e:
                raise HTTPException(409, {"reason": str(e), "running": e.running})
            for pid in out.get("projection_instances", []):
                rt._project({"proc_inst_id": pid})
            rt.cleanup_removed_definitions()
            out["projection_pending"] = sum(bool(rt.repo.projection_status(rt.tenant_id, pid)["pending"]) for pid in out.get("projection_instances", []))
            audit("-", by, "FLOW_DELETED", {"definition_id": def_id, **out})
            return {"definition_id": def_id, **out}
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
            # 2026-10-25 수업 한 바퀴: 수업 흐름(강사 배포)의 [매핑 열기] → [판본 등록]이 통과해 강사 흐름에 학생 판본이 쌓였다(배포만 막혔다)
            if not req.class_flow and any(h['id'] == def_id and h.get('class_flow') for h in rt.repo.deployed_heads(rt.tenant_id)):
                raise HTTPException(409, {"reason": f"'{draft.get('name') or def_id}'은(는) 강사가 배포한 수업 흐름입니다 — 내 판본은 [흐름 가져오기]에서 "
                                                    "다른 흐름 id(예: my_cooling)로 가져와 등록하세요"})
            mapping = req.mapping if isinstance(req.mapping, dict) else (draft.get("mapping") or {})
            if not req.class_flow:
                course(lambda policy: policy.register_flow(def_id, draft['bpmn'], mapping))
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
