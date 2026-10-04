"""One claimed work item from start to stored result (process-gpt-cli-agent/executor.py, synchronous).

    fetch_pending_task ─▶ context (form · users · tenant MCP) ─▶ workspace per run ─▶ .mcp.json bridge ─▶ prompt
      ─▶ coding agent headless (cliagents stream_exec) ─▶ UI events + events rows ─▶ outcome against the form contract
      ─▶ save_task_result(final=True)  (the row becomes SUBMITTED; the engine takes it from there)

Less is observable with a CLI than with an in-process graph, so more has to be said out loud: a run that could not use its
tools pauses as a human question, a run that produced prose where the form wanted fields fails instead of storing a shrug,
a cancelled run says it was cancelled.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict
from typing import Callable, Iterable

from cliagents import ExecEvent, ExecEventKind, ExecRequest, Permission, Surface, registry, stream_exec
from procsvc import task_deferral

from . import bridge, context, hitl, outcome, prompt, workspace
from . import events as ui_events
from .settings import Settings
from .process_control import controlled_stream

log = logging.getLogger("worker.runner")
ExecFn = Callable[[object, ExecRequest, dict | None], Iterable[ExecEvent]]
_PERMISSION_BY_NAME = {p.value: p for p in Permission}


class RunFailed(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


class Runner:
    def __init__(self, s: Settings, repo, exec_fn: ExecFn | None = None, schema_prompt: str | None = None, resolve_provider=None):
        self.s, self.repo = s, repo
        self.exec_fn = exec_fn or _exec_stream
        self.schema_prompt = schema_prompt if schema_prompt is not None else _read(s.schema_prompt_path)
        self.resolve_provider = resolve_provider or _resolve_provider
        self.in_flight = 0

    # ---- polling
    def poll_once(self) -> int:
        claim_owner=f"{self.s.consumer}:{uuid.uuid4().hex}"
        rows = self.repo.fetch_pending_task(self.s.agent_orch, claim_owner, limit=1, tenant_id=self.s.tenant_id)
        for row in rows:
            self.handle(row)
        return len(rows)

    def handle(self, row: dict) -> None:
        job_id = f"run-{row['id'][:8]}-{uuid.uuid4().hex}"
        self.in_flight += 1
        try:
            ctx = context.prepare(self.repo, row, self.s.tenant_id)
            self.run(row, ctx, job_id)
        except Cancelled:
            self.repo.release_worker_claim(row['id'],row['consumer'])
            log.info("%s %s cancelled by a person", row.get("proc_inst_id"), row.get("activity_id"))
            self._event(row, job_id, "task_cancelled", {"name": "작업 취소", "goal": "담당자가 실행을 취소했습니다."}, crew_type="agent")
        except Exception as e:  # noqa: BLE001 — every failure path ends in a DB state, never a lost claim
            self._fail(row, job_id, e)
        finally:
            self.in_flight -= 1

    # ---- one run
    def run(self, row: dict, ctx: context.Context, job_id: str) -> None:
        caps = context.activity_capabilities(ctx.definition, row.get("activity_id") or "")
        config = caps.get("agent_config") or {}
        provider_id = str(config.get("cli") or config.get("agent") or self.s.cli_agent)
        model = config.get("model") or self.s.model
        permission = _PERMISSION_BY_NAME.get(str(config.get("permission") or ""), self.s.default_permission)
        provider = self.resolve_provider(provider_id)
        ws = workspace.for_run(self.s.workspace_root, row["id"], tenant_id=self.s.tenant_id)
        workspace.provision(ws, agent_id=provider_id, schema_prompt=self.schema_prompt,
                            task={"id": row["id"], "proc_inst_id": row.get("proc_inst_id"), "activity_id": row.get("activity_id"),
                                  "activity_name": row.get("activity_name"), "form_id": ctx.form_id, "form_fields": ctx.form_fields,
                                  "process_scope": context.process_scope(row), "query": row.get("query"),
                                  "draft": row.get("draft"), "output": row.get("output")})
        bridged = bridge.install(ws.path, ctx.tenant_mcp, provider_id=provider_id, isolate_config_dir=self.s.isolate_config_dir,
                                 host_rewrite=bridge.parse_host_rewrite(self.s.mcp_host_rewrite))
        if ctx.human_answer:
            plan = hitl.durable_resume(row) or hitl.plan_resume(ws.path, workspace_exists=ws.exists)
            text = prompt.resume_prompt(ctx.human_answer, previous_summary=str(row.get("draft") or "")[:2000], restarted=plan.restarted)
            resume_session = plan.session_id or None
            if plan.restarted:
                text = prompt.build(row, ctx.extras, workdir=str(ws.path)) + "\n\n" + text
                self._event(row, job_id, "task_working", {"type": "notice", "content": f"이전 실행을 이어갈 수 없어 새로 시작합니다. ({plan.reason})"}, crew_type="agent")
        else:
            text = prompt.build(row, ctx.extras, workdir=str(ws.path))
            resume_session = _session_of(row)
        extra_args = list(bridged.extra_args)
        if provider_id == "codex":
            # This is a business task, not a developer resuming the parent repo.
            # Codex skips inherited AGENTS files; supply only this run's contract.
            text = workspace.CONSTITUTION + "\n\n## Ontology schema\n" + self.schema_prompt + "\n\n" + text
            extra_args += ["-c", "model_reasoning_effort=" + json.dumps(config.get("reasoning_effort") or self.s.reasoning_effort)]
        if provider_id == "claude-code" and self.s.allowed_tools:
            extra_args += ["--allowedTools", ",".join(self.s.allowed_tools)]
        request = ExecRequest(prompt=text, workdir=str(ws.path), model=model, permission=permission, resume_session=resume_session, extra_args=extra_args)
        crew = f"{self.s.agent_orch}:{provider_id}"
        self._event(row, job_id, "task_started", ui_events.task_started(row, getattr(provider, "display_name", provider_id)), crew_type="result")
        final_text, session_id, paused = self._stream(row, job_id, provider, request, bridged.env or None, crew,
                                                       trace_path=ws.path / f"{job_id}.events.jsonl")
        assessment = task_deferral.control(final_text)
        if assessment is not None:
            task_deferral.defer(self.repo,self.s.tenant_id,row['id'],expected_consumer=row['consumer'],
                                request_id=job_id,assessment=assessment,session_id=session_id or None)
            hitl.clear(ws.path)
            return
        question = hitl.business_question(final_text)
        if question is not None:
            self._pause(row, ws, provider_id, session_id or "", question['question'], job_id,
                        options=question['options'])
            return
        if paused is not None and not final_text:
            self._pause(row, ws, provider_id, session_id or "", paused, job_id)
            return
        if paused is not None:
            self._event(row, job_id, "task_working", {"type": "notice", "content": f"실행 중 허용되지 않은 동작이 있었습니다(결과는 그대로 저장합니다): {paused}"}, crew_type="agent")
        result = outcome.interpret(final_text, ctx.form_fields, versioned='forms' in (ctx.definition or {}))
        if not result.contract_met:
            raise RunFailed(f"결과가 요구된 출력 형식과 맞지 않습니다: {result.mismatch_reason}\n\n에이전트 응답:\n{result.raw_text[:1000]}")
        payload = dict(result.payload)
        if session_id:
            payload["cliagents_session_id"] = session_id          # the next task of the instance, or a human's answer, resumes it
        if not self.repo.save_task_result(row["id"], payload, final=True,expected_consumer=row['consumer']):
            raise Cancelled()
        self._event(row, job_id, "task_completed", {"output_keys": sorted(result.outputs), "text": result.raw_text[:2000], "session_id": session_id}, crew_type="result")
        hitl.clear(ws.path)
        (ws.path / "outputs").mkdir(exist_ok=True)
        (ws.path / "outputs" / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("%s %s submitted (%s)", row.get("proc_inst_id"), row.get("activity_id"), ", ".join(sorted(result.outputs)) or "text")

    def _stream(self, row: dict, job_id: str, provider, request: ExecRequest, env: dict | None, crew: str, trace_path=None) -> tuple[str, str | None, str | None]:
        """Forward progress to the events table; stop when a person cancels. Returns (final text, session, pause reason)."""
        final_text, session_id, pause_reason, streamed, pending_rows = "", None, None, [], []
        last_check, deadline = time.monotonic(), time.monotonic() + self.s.run_timeout_s
        def check_stop():
            nonlocal last_check
            if time.monotonic()-last_check >= self.s.cancel_check_every_s:
                last_check=time.monotonic()
                if self._cancelled(row):raise Cancelled()
            if time.monotonic()>deadline:
                raise RunFailed(f"실행 제한 시간을 초과했습니다({self.s.run_timeout_s:g}s). 지금까지의 산출물은 보존됩니다.")
        gen = (_exec_stream(provider,request,env,check_stop=check_stop) if self.exec_fn is _exec_stream
               else self.exec_fn(provider,request,env))
        trace = trace_path.open("a", encoding="utf-8") if trace_path else None
        try:
            for ev in gen:
                if trace:
                    trace.write(json.dumps(asdict(ev), ensure_ascii=False, default=str) + "\n")
                    trace.flush()
                if ev.session_id:
                    session_id = ev.session_id
                if ev.kind is ExecEventKind.RESULT:
                    if ev.is_error:
                        raise RunFailed(ev.text or "agent reported failure")
                    final_text = ev.text or final_text
                elif ev.kind is ExecEventKind.ASSISTANT_TEXT:
                    streamed.append(ev.text)
                elif ev.kind is ExecEventKind.PERMISSION_REQUEST:
                    pause_reason = pause_reason or (ev.text or "권한이 필요합니다")      # first refusal wins
                elif ev.kind is ExecEventKind.ERROR and not final_text:
                    raise RunFailed(ev.text or "agent error")
                for ui in ui_events.translate(ev):
                    r = ui_events.row_of(ui, job_id=job_id, todo_id=row["id"], proc_inst_id=row.get("proc_inst_id"), crew_type=crew)
                    if r:
                        pending_rows.append(r)
                if pending_rows:
                    self.repo.record_events(pending_rows)
                    pending_rows = []
                check_stop()
        finally:
            if trace:
                trace.close()
            if hasattr(gen, "close"):
                gen.close()                                   # the library's teardown reaps the child process
            if pending_rows:
                self.repo.record_events(pending_rows)
        if self._cancelled(row):raise Cancelled()
        return (final_text or "".join(streamed)).strip(), session_id, pause_reason

    def _cancelled(self, row: dict) -> bool:
        fresh = self.repo.get_workitem(row["id"]) or {}
        return (not fresh or fresh.get('status') != 'IN_PROGRESS'
                or str(fresh.get("draft_status") or "").upper() == "CANCELLED"
                or fresh.get('consumer') != row.get('consumer'))

    # ---- outcomes
    def _pause(self, row: dict, ws: workspace.Workspace, agent_id: str, session_id: str, question: str, job_id: str,
               options: list[str] | None = None) -> None:
        """Stop and wait for a person, without calling it done or failed (draft_status HUMAN_ASKED + human_asked event)."""
        ask_job = f"human_asked_{row['id'][:8]}_{uuid.uuid4().hex}"
        request = hitl.PendingRequest(run_id=row["id"], agent_id=agent_id, session_id=session_id, question=question, job_id=ask_job,
                                      fingerprint=hitl.fingerprint(agent_id, question))
        with self.repo.instance_transaction(self.s.tenant_id, row['proc_inst_id']):
            if not self.repo.set_draft_status(row['id'],'HUMAN_ASKED',expected_consumer=row['consumer']):
                raise Cancelled()
            fresh = self.repo.get_workitem(row['id'])
            fresh['draft'] = {'cliagents_session_id': session_id, '_human_request': request.as_dict()}
            self.repo.update_workitem(fresh)
            self.repo.record_events([{"job_id": ask_job, "todo_id": row["id"], "proc_inst_id": row.get("proc_inst_id"), "crew_type": "agent",
                                      "event_type": "human_asked", "status": "ASKED",
                                      "data": {"role": "user", "text": question, "type": "confirm", "options": options or [],
                                               "signature": request.fingerprint, "agent": agent_id, "session_id": session_id}}])
            self.repo.insert_notification({"title": question[:200], "type": "workitem_bpm", "description": agent_id, "user_id": _asker_of(row),
                                           "tenant_id": self.s.tenant_id, "url": f"/todolist/{row['id']}", "from_user_id": agent_id})
        try:
            hitl.remember(ws.path, request)
        except OSError:
            log.exception('pending file cache failed; question/session already persisted in DB')
        log.info("%s %s paused for a person: %s", row.get("proc_inst_id"), row.get("activity_id"), question[:80])

    def _fail(self, row: dict, job_id: str, err: Exception) -> None:
        if not self.repo.update_task_error(row['id'],expected_consumer=row['consumer']):
            self.repo.release_worker_claim(row['id'],row['consumer'])
            self._event(row,job_id,'task_cancelled',{'name':'실행 결과 폐기','goal':'작업 취소 또는 점유 변경 후 도착한 오류'},crew_type='agent')
            return
        msg = f"{type(err).__name__}: {str(err)[:600]}"
        log.warning("%s %s failed: %s", row.get("proc_inst_id"), row.get("activity_id"), msg)
        self.repo.record_events([{"job_id": "TASK_ERROR", "todo_id": row["id"], "proc_inst_id": row.get("proc_inst_id"), "crew_type": "agent",
                                  "event_type": "error", "data": {"name": "시스템 오류 알림", "goal": "오류 원인과 대처 안내를 전달합니다.",
                                                                 "friendly": "에이전트 실행이 실패했습니다. 담당자가 확인한 뒤 다시 보낼 수 있습니다.", "raw_error": msg}}])

    def _event(self, row: dict, job_id: str, event_type: str, data: dict, *, crew_type: str) -> None:
        self.repo.record_events([{"job_id": job_id, "todo_id": row["id"], "proc_inst_id": row.get("proc_inst_id"), "crew_type": crew_type,
                                  "event_type": event_type, "data": data}])


def _session_of(row: dict) -> str | None:
    """The CLI session this conversation is already using (stored in the previous output/draft as cliagents_session_id)."""
    for key in ("draft", "output"):
        value = row.get(key)
        if isinstance(value, str) and value.strip().startswith("{"):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = None
        if isinstance(value, dict) and isinstance(value.get("cliagents_session_id"), str) and value["cliagents_session_id"].strip():
            return value["cliagents_session_id"].strip()
    return None


def _exec_stream(provider, request, env, *, check_stop=None):
    # Pinned cliagents records process exit/stderr only in its thread-local
    # result slot; stream_exec itself emits a blank success on startup failure.
    # The controlled adapter reads it after exhaustion in its own pump thread.
    yield from controlled_stream(stream_exec,provider,request,env,check_stop or (lambda:None),RunFailed)


def _asker_of(row: dict) -> str:
    """Who gets the notification for an agent's question: the people of the instance roles, operator first."""
    return "role:operator"


def _resolve_provider(provider_id: str):
    """One place to swap the provider registry (tests pass a fake). cliagents resolves the CLI (shutil.which) but keeps the bare
    name in argv; on Windows CreateProcess does not search PATHEXT, so `claude` (the npm shim claude.cmd) raises WinError 2
    (live check 2026-10-04). Hand the provider its full path."""
    if provider_id == "codex":
        from .codex_provider import WorkerCodexProvider
        provider = WorkerCodexProvider()
    else:
        provider = registry.resolve(provider_id, surface=Surface.EXEC)
    try:
        provider.executable = provider.resolve_executable()
    except Exception:  # noqa: BLE001 — not installed: exec_argv raises the library's own AgentNotInstalledError later
        pass
    return provider


def _read(path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "(schema_prompt.md 를 찾지 못했다 — Neo4j MCP get_neo4j_schema 로 스키마를 직접 확인하라)"
