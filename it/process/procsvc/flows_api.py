"""B3: bpmn.io 그림 가져오기 API — 매핑 · 사전 검사 · 판본 등록 · 그림 다시 받기 · 기준으로 되돌리기.

  GET  /api/flows/catalog                        부품(기준 정의에서 읽은 시나리오 부품 + 일반 부품) · 역할 · 에이전트 · 경보 패턴
  POST /api/flows/import {xml, file_name, definition_id?, start_patterns?}
                                                 .bpmn 읽기 → 같은 흐름 id 의 앞선 매핑 유지 → 초안 저장 → 사전 검사 결과
  GET  /api/flows                                내가 가져온 흐름(초안) · 등록한 판본 — 강사가 설치한 수업 흐름은 class_flow 표시
  GET  /api/flows/{id}                           초안 하나(읽은 그림 · 매핑 · 사전 검사 · 판본 · 등록할 수 있는가)
  PUT  /api/flows/{id}/mapping {mapping}         매핑 저장 + 사전 검사(수업 흐름 · 기준 흐름의 매핑은 저장하지 않는다)
  POST /api/flows/{id}/check {mapping?}          사전 검사만(저장 없음)
  POST /api/flows/{id}/register {mapping?, by}   검사 통과 시 새 판본 등록(정의 JSON + .bpmn 원본). 운영 판본 포인터는 그대로(배포는 B4)
  GET  /api/flows/{id}/versions/{v}/bpmn         그 판본의 그림(.bpmn) 내려받기
  POST /api/flows/reset {by}                     기준으로 되돌리기: 내가 가져온 정의 · 판본 · 초안만 지움
  DELETE /api/flows/{id}?by=                     학생 흐름 하나 지우기

거절은 사람이 읽을 사유(와 칸 위치): {reason, problems?:[{where:{kind, kind_label, id, name}, field, reason}]} — 모든 거절이 같은 모양이다.
누른 사람(by)은 등록 · 되돌리기 · 지우기의 감사 기록에 남는다(P5-18).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import bpmn_import, course_policy, mcp_dependencies
from .bpmn_store import FlowBusy, FlowStore

#: 수업 흐름 설치(course_bootstrap — 시작 스크립트의 서버 안 호출, 수업 흐름 표시는 그 길만 보낼 수 있다)의 등록 행위자
BOOTSTRAP_ACTOR = "시작 스크립트(수업 흐름 설치)"


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
    by: str | None = Field(default=None, max_length=200)     # 등록한 사람(등록에서만 — 수업 흐름 설치는 BOOTSTRAP_ACTOR)


class ResetReq(BaseModel):
    by: str = Field(default="", max_length=200)          # 빈 값 · 본문 없음은 _who 가 학생이 알아듣는 문장으로 거절(422 꼴이 아니라)


def default_base_loader(rt) -> dict:
    """부품의 원천 = 기준 정의 파일(it/process/definitions/<PROCESS_DEFINITION_FILE>). 학생 판본이 배포돼도 부품은 기준에서 읽는다.
    파일이 없으면 다른 정의로 대신하지 않고 그 자리와 함께 실패한다(P5-15)."""
    from . import instance_mode
    path = Path(instance_mode.DEFINITIONS_DIR) / instance_mode.DEFINITION_FILE
    if not path.is_file():
        raise RuntimeError(f"기준 정의 파일 {path} 이(가) 없어 흐름 부품 목록을 만들 수 없습니다 — 이미지의 정의 폴더를 확인하세요")
    return json.loads(path.read_text(encoding="utf-8"))


def _who(rt, by) -> str:
    """누른 사람 = 포털의 「나」(사용자 표의 사람 user:*). 빈 값은 400, 이름만 적은 자유 입력 · 없는 사람은 403 — 이력에 지어낸 이름이 남지 않게
    (사람 확인은 inbox.require_person 한 곳)."""
    who = by.strip() if isinstance(by, str) else ""
    if not who:
        raise HTTPException(400, {"reason": "누가 했는지 모릅니다 — 포털 위쪽에서 '나'(사람 사용자)를 고른 뒤 다시 누르세요"})
    from .inbox import require_person
    try:
        require_person(rt.repo, rt.tenant_id, who)
    except PermissionError as e:
        raise HTTPException(403, {"reason": str(e)}) from None
    return who


def register(app, *, runtime_factory, audit=lambda *a, **k: None, base_loader=default_base_loader):
    def runtime():
        rt = runtime_factory()
        if rt is None:
            from .instances import NOT_READY      # 런타임 모듈 — 이 모듈이 먼저 읽혀도 순환 import 가 되지 않게 여기서
            raise HTTPException(503, NOT_READY)            # 「켜지는 중」은 다른 경로와 같은 모양(detail = 글)
        return rt

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except KeyError as exc:
            raise HTTPException(404, {"reason": str(exc.args[0]) if exc.args else "찾을 수 없습니다"}) from exc

    def catalog_of(rt) -> dict:
        return bpmn_import.catalog(base_loader(rt), rt.repo.list_users(None, rt.tenant_id))

    def class_flows(rt) -> dict[str, str]:
        """강사가 설치한 수업 흐름(배포의 주인이 수업) id → 이름. 학생은 읽기만 한다(매핑 열기) — 지우기 · 매핑 저장 · 등록은 하지 않는다."""
        out = {}
        for h in rt.repo.deployed_heads(rt.tenant_id):
            if h.get('class_flow'):
                out[h['id']] = rt.definition_for({'proc_def_id': h['id'], 'tenant_id': rt.tenant_id, 'proc_def_version': h['prod_version']}).name
        return out

    def ctx_for(rt, store, cat, def_id, draft) -> dict:
        return {"catalog": cat, "definition_id": def_id, "version": store.next_version(def_id), "file_name": draft.get("file_name"),
                "xml_sha256": bpmn_import.xml_sha256(draft["bpmn"]), "name": None}

    def registration(rt, store, def_id, draft, mapping, class_flow_ids, bootstrap=False) -> dict:
        """이 초안을 지금 판본으로 등록할 수 있는가(W3-08 — 「검사 통과」 뒤 등록에서야 거절되지 않게 사전 검사와 같은 화면에서 미리 알린다).
        구조 검사(check.ok)와 따로다: 거절 = 기준 흐름 id · 강사 수업 흐름 · 수업 경계(course_policy.register_flow).
        bootstrap = 수업 흐름 설치(course_bootstrap — 서버 안 호출만 class_flow 표시를 보낼 수 있다)의 요청: 그 설치가 등록하므로 판정하지 않는다."""
        if bootstrap:
            return {"allowed": True, "reason": None}
        if store.is_protected(def_id):
            return {"allowed": False, "reason": f"'{def_id}'은(는) 기준 흐름 id 입니다 — 기준은 바꾸지 않습니다"}
        if def_id in class_flow_ids:
            return {"allowed": False, "reason": f"「{class_flow_ids[def_id]}」은(는) 수업 흐름이라 읽기만 할 수 있습니다 — 내 판본은 "
                                                "[흐름 가져오기]에서 다른 흐름 id(예: my_cooling)로 가져와 등록하세요"}
        try:
            app.state.course.register_flow(def_id, draft['bpmn'], mapping)
        except course_policy.AccessDenied as exc:
            return {"allowed": False, "reason": str(exc), "course": True}
        return {"allowed": True, "reason": None}

    def view(rt, store, cat, def_id, draft, mapping, report=None, *, bootstrap=False) -> dict:
        parsed = bpmn_import.parse_bpmn(draft["bpmn"])
        result = bpmn_import.check(parsed, mapping, ctx_for(rt, store, cat, def_id, draft))
        from .instance_mode import EFFECT_MCP_SERVERS
        result['dependencies'] = mcp_dependencies.for_repo(rt.repo, rt.tenant_id, parsed, mapping, tuple(EFFECT_MCP_SERVERS))
        classes = class_flows(rt)
        verdict = registration(rt, store, def_id, draft, mapping, classes, bootstrap)
        if verdict.get("course"):
            result["problems"].append(bpmn_import.problem({"kind": "process", "id": parsed["process"]["id"], "name": parsed["process"]["name"]},
                                                          "course", verdict["reason"]))
            result["ok"] = False
        return {"definition_id": def_id, "file_name": draft.get("file_name"), "parsed": parsed, "mapping": mapping,
                "reimport": report, "check": result, "next_version": result["definition"]["version"],
                "versions": store.versions(def_id), "base": cat["base"], "class_flow": def_id in classes,
                "register": {k: verdict[k] for k in ("allowed", "reason")}}

    def course(check):
        """수업 경계(course_policy) 판정 — 거절은 학생이 읽을 까닭과 403."""
        try:
            check(app.state.course)
        except course_policy.AccessDenied as exc:
            raise HTTPException(403, {"reason": str(exc)}) from None

    def draft_of(store, def_id) -> dict:
        draft = store.get_draft(def_id)
        if draft is None:
            raise KeyError(f"가져온 그림이 없습니다: {def_id} — 먼저 .bpmn 파일을 가져오세요")
        return draft

    def editable(rt, store, def_id) -> None:
        """매핑을 고칠 수 있는 흐름인가 — 기준 흐름 · 강사 수업 흐름은 읽기만(그 초안을 바꾸면 강사 흐름의 다음 설치가 학생 매핑을 이어받는다)."""
        if store.is_protected(def_id):
            raise HTTPException(409, {"reason": f"'{def_id}'은(는) 기준 흐름 id 입니다 — 기준은 바꾸지 않습니다"})
        classes = class_flows(rt)
        if def_id in classes:
            raise HTTPException(409, {"reason": f"「{classes[def_id]}」은(는) 수업 흐름이라 읽기만 할 수 있습니다 — 매핑을 고쳐 보려면 "
                                                "[흐름 가져오기]에서 같은 그림을 다른 흐름 id(예: my_cooling)로 가져오세요"})

    def mapping_of(req: MappingReq, draft) -> dict:
        mapping = req.mapping if isinstance(req.mapping, dict) else (draft.get("mapping") or {})
        try:                                   # 두 단계 공통 대용량 한도(P5-21) — 등록뿐 아니라 저장 · 검사에서도, 수업 경계 정본의 함수 하나
            course_policy.within_text_max(mapping, '흐름 연결(매핑)')
        except course_policy.AccessDenied as e:
            raise HTTPException(400, {"reason": str(e)}) from None
        return mapping

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
                raise HTTPException(400, {"reason": str(e), "problems": e.problems}) from None
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
            if not req.class_flow and def_id in class_flows(rt):
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 수업 흐름 id 입니다 — 내 흐름 id 를 따로 쓰세요(예: my_{def_id.split('_')[-1]})"})
            cat = catalog_of(rt)
            old = store.get_draft(def_id)
            mapping, report = bpmn_import.merge_mapping(parsed, (old or {}).get("mapping"), cat)
            if not req.class_flow:
                mapping = app.state.course.imported_mapping(mapping, (old or {}).get("mapping"))
            if old is None and req.start_patterns is not None and mapping["start"].get("kind") == "alert":
                mapping["start"]["patterns"] = list(req.start_patterns)
            report["previous"] = old is not None
            draft = {"bpmn": req.xml, "file_name": req.file_name}
            store.save_draft(def_id, req.xml, req.file_name, mapping)
            return view(rt, store, cat, def_id, draft, mapping, report, bootstrap=req.class_flow)
        return await run(work)

    @app.get("/api/flows")
    async def flows_list():
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            classes = class_flows(rt)
            return {"drafts": [dict(d, class_flow=d["proc_def_id"] in classes) for d in store.drafts()],
                    "versions": [dict(v, class_flow=v["id"] in classes) for v in store.versions()]}
        return await run(work)

    def removed(rt, out: dict) -> None:
        """지운 학생 판본으로 끝난 처리 건 · 판본 노드를 그래프에서도 정리한다(그 자리에서 한 번, 남으면 반영 주기가 다시)."""
        for pid in out.get("projection_instances", []):
            rt._project({"proc_inst_id": pid})
        rt.cleanup_removed_definitions()

    @app.post("/api/flows/reset")
    async def flows_reset(req: ResetReq | None = None):
        rt = runtime()
        by = _who(rt, req.by if req else None)
        def work():
            from .flow_deploy import routes
            deployed = {f["definition"]: f["name"] for f in routes(rt)["flows"]}   # 경보 경로에 배포된 흐름(수업 흐름 포함)은 남긴다
            try:
                out = FlowStore(rt.repo, rt.tenant_id).reset(keep=set(deployed))
            except FlowBusy as e:
                raise HTTPException(409, {"reason": str(e), "running": e.running}) from None
            removed(rt, out)
            out["kept"] = [deployed[d] for d in out["kept"]]        # 학생이 읽을 흐름 이름(W3-17 — 정의 id 목록이 아니라)
            audit("-", by, "FLOWS_RESET", {k: v for k, v in out.items() if k != "projection_instances"})
            return {k: v for k, v in out.items() if k != "projection_instances"}
        return await run(work)

    @app.delete("/api/flows/{def_id}")
    async def flows_delete(def_id: str, by: str = ""):
        rt = runtime()
        who = _who(rt, by)
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            if store.is_protected(def_id):
                raise HTTPException(403, {"reason": "수업 기준 흐름은 삭제할 수 없습니다"})
            classes = class_flows(rt)
            if def_id in classes:
                raise HTTPException(409, {"reason": f"「{classes[def_id]}」은(는) 수업 흐름이라 지울 수 없습니다(수업 버튼 · 경보가 이 흐름을 씁니다)"})
            if not store.get_draft(def_id) and not store.versions(def_id):
                raise HTTPException(404, {"reason": "삭제할 학생 흐름이 없습니다"})
            # [기준으로 되돌리기](flows_reset)의 keep 과 같은 기준: 경보 경로에 배포된 흐름은 지우지 않는다.
            # 지우면 경보가 조용히 기준 흐름으로 돌아가고 그 흐름의 시나리오 버튼이 '배포되어 있지 않습니다'로 멈춘다.
            from .flow_deploy import routes
            deployed = next((f for f in routes(rt)["flows"] if f["definition"] == def_id), None)
            if deployed is not None:
                patterns = ", ".join(deployed.get("patterns") or []) or "경보 패턴 없음"
                raise HTTPException(409, {"reason": f"「{deployed.get('name') or def_id}」은(는) 지금 경보 경로에 배포된 흐름입니다(판본 {deployed.get('version')}, "
                                                    f"경보 {patterns}) — 지우지 않았습니다. 먼저 [관리] 탭 「흐름 판본 배포 · 비교 · 되돌리기」의 "
                                                    "[기준 흐름으로 되돌리기]로 배포를 내린 뒤 지우세요",
                                          "deployed": deployed})
            try:
                out = store.reset(def_id)
            except FlowBusy as e:
                raise HTTPException(409, {"reason": str(e), "running": e.running}) from None
            removed(rt, out)
            out["projection_pending"] = sum(bool(rt.repo.projection_status(rt.tenant_id, pid)["pending"]) for pid in out.get("projection_instances", []))
            out.pop("projection_instances", None)
            out.pop("kept", None)
            audit("-", who, "FLOW_DELETED", {"definition_id": def_id, **out})
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
            editable(rt, store, def_id)
            if not isinstance(req.mapping, dict):
                raise HTTPException(400, {"reason": "저장할 연결(매핑)이 객체로 없습니다"})
            mapping = mapping_of(req, draft)
            store.save_mapping(def_id, mapping)
            return view(rt, store, catalog_of(rt), def_id, draft, mapping)
        return await run(work)

    @app.post("/api/flows/{def_id}/check")
    async def flows_check(def_id: str, req: MappingReq):
        rt = runtime()
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            draft = draft_of(store, def_id)
            return view(rt, store, catalog_of(rt), def_id, draft, mapping_of(req, draft), bootstrap=req.class_flow)
        return await run(work)

    @app.post("/api/flows/{def_id}/register", status_code=201)
    async def flows_register(def_id: str, req: MappingReq):
        rt = runtime()
        who = BOOTSTRAP_ACTOR if req.class_flow else _who(rt, req.by)
        def work():
            store = FlowStore(rt.repo, rt.tenant_id)
            draft = draft_of(store, def_id)
            mapping = mapping_of(req, draft)
            if store.is_protected(def_id):
                raise HTTPException(409, {"reason": f"'{def_id}'은(는) 기준 흐름 id 입니다 — 기준은 바꾸지 않습니다"})
            # 2026-10-25 수업 한 바퀴: 수업 흐름(강사 배포)의 [매핑 열기] → [판본 등록]이 통과해 강사 흐름에 학생 판본이 쌓였다(배포만 막혔다)
            classes = class_flows(rt)
            if not req.class_flow and def_id in classes:
                raise HTTPException(409, {"reason": f"「{classes[def_id]}」은(는) 수업 흐름입니다 — 내 판본은 [흐름 가져오기]에서 "
                                                    "다른 흐름 id(예: my_cooling)로 가져와 등록하세요"})
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
                raise HTTPException(409, {"reason": str(e)}) from None
            audit("-", who, "FLOW_REGISTERED", {"definition": def_id, "version": raw["version"], "file": draft.get("file_name"),
                                                "origin": "user", "class_flow": bool(req.class_flow)})
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
