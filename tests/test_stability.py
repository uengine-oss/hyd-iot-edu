import asyncio
import copy
import io
import json
import urllib.request

import pytest
from fastapi import HTTPException

from agentsvc import llm
from procsvc import main, machine, decisions
from procsvc.store import Store
from test_machine import CARD, new_incident, approve, FX
from test_decisions_process import dec
from entsim.state import EnterpriseState
from agentsvc.tools import mcp_prom


def test_enterprise_retry_after_restart_does_not_duplicate_work_order(tmp_path):
    path = tmp_path / "enterprise.sqlite3"
    req = {"decision": "D-1", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "params": {}}
    first = EnterpriseState(path)
    tx = first.execute(req)
    first._db.close()
    second = EnterpriseState(path)
    assert second.execute(req) == tx
    assert len(second.snapshot()["cmms"]["work_orders"]) == 1
    with pytest.raises(ValueError, match="idempotency conflict"):
        second.execute(dict(req, params={"window": "different"}))
    second._db.close()


def test_restart_keeps_pending_and_terminal_but_escalates_inflight(tmp_path):
    path = tmp_path / "state.sqlite3"
    pending = new_incident()
    inflight = copy.deepcopy(pending)
    inflight.id = "inflight"
    approve(inflight, FX())
    terminal = copy.deepcopy(pending)
    terminal.id, terminal.state = "closed", "REJECTED_BY_OPERATOR"
    decision = decisions.new(dec())
    decisions.approve(decision, "skill:derate-night-clean", "reviewer", "role:prod-mgr")
    store = Store(path)
    store.save({i.id: i for i in (pending, inflight, terminal)}, {"d": decision}, [{"event": "TEST"}])
    store.db.close()
    restored = Store(path)
    incidents, book, audit = restored.restore()
    assert incidents[pending.id].state == "AWAITING_APPROVAL"
    assert incidents["closed"].state == "REJECTED_BY_OPERATOR"
    assert incidents["inflight"].state == "ESCALATED"
    assert incidents["inflight"].cmd_id == inflight.cmd_id
    assert book["d"]["state"] == "PARTIAL"
    assert audit == [{"event": "TEST"}]
    restored.db.close()


@pytest.fixture
def hitl(monkeypatch):
    inc = new_incident()
    inc.card = dict(inc.card, recommended=[      # ontology v2 guide card: atomic commands of the failure mode's SOP skills
        {"code": "FAN_SET", "actionId": "action:set-fan", "name": "팬 속도 설정", "kind": "command", "param": "fan_pct", "value": 100, "paramRange": [0, 100]},
        {"code": "LOAD_SET", "actionId": "action:set-load", "name": "펌프 부하 설정", "kind": "command", "param": "load_pct", "value": 80, "paramRange": [60, 100]}])
    d = decisions.new(dec())
    d.update(id="D-test", asset=inc.asset, origin={"incident": inc.id})
    monkeypatch.setattr(main, "incidents", {inc.id: inc})
    monkeypatch.setattr(main, "book", {d["id"]: d})
    monkeypatch.setattr(main, "audit_log", [])
    return inc, d


def test_invalid_hitl_input_does_not_consume_approval(hitl):
    inc, d = hitl
    before = copy.deepcopy(d)
    req = main.HitlDecideReq(decision=d["id"], option="skill:fan-max-derate", role="role:prod-mgr", fan_pct=999)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.hitl_decide(inc.id, req))
    assert exc.value.status_code == 400 and "fan_pct=999" in str(exc.value.detail)
    assert d == before
    assert inc.state == "AWAITING_APPROVAL" and inc.cmd_id is None


def test_hitl_rejects_unrelated_decision(hitl):
    inc, d = hitl
    d["origin"]["incident"] = "another"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.hitl_decide(inc.id, main.HitlDecideReq(decision=d["id"], option="skill:fan-max-derate", role="role:prod-mgr")))
    assert exc.value.status_code == 400
    assert d["state"] == "PENDING_APPROVAL"


def test_duplicate_decision_submission_cannot_reset_approval(hitl):
    inc, d = hitl
    d["state"] = "EXECUTED"
    result = asyncio.run(main.create_decision(copy.deepcopy(d)))
    assert result["duplicate"] and main.book[d["id"]]["state"] == "EXECUTED"


@pytest.mark.parametrize("response", [
    {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
    {"choices": [{"finish_reason": "length", "message": {"content": "cut off"}}]},
    {"choices": []},
])
def test_llm_invalid_response_uses_template(monkeypatch, response):
    monkeypatch.setattr(llm, "PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-secret")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(json.dumps(response).encode()))
    assert llm.summarize(CARD, "fallback") == ("fallback", "template")


def test_llm_timeout_is_bounded_and_falls_back(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-secret")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "8")
    def fail(req, timeout):
        assert timeout == 8
        raise TimeoutError("secret must not be logged")
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert llm.summarize(CARD, "fallback") == ("fallback", "template")


def test_llm_valid_response_reports_model(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-secret")
    response = {"choices": [{"finish_reason": "stop", "message": {"content": "grounded summary"}}]}
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(json.dumps(response).encode()))
    assert llm.summarize(CARD, "fallback") == ("grounded summary", llm.MODEL)


def test_data_trust_fails_closed_when_ingest_is_unreachable(monkeypatch):
    class DB:
        def latest(self, *args):
            return 48.0, 1.0
    def unavailable(*args, **kwargs):
        raise TimeoutError("offline")
    monkeypatch.setattr(urllib.request, "urlopen", unavailable)
    result = mcp_prom.freshness(DB(), "HYD-01")
    assert result["ok"] is False and result["reason"] == "ingest unavailable"


def test_store_save_from_another_thread(tmp_path):
    """Instance-runtime hooks persist from executor threads; the shared SQLite connection must accept that."""
    import threading
    store = Store(str(tmp_path / "p.sqlite3"))
    errors = []

    def save():
        try:
            store.save({}, {"d1": {"state": "DONE", "history": []}}, ["from-thread"])
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    th = threading.Thread(target=save)
    th.start(); th.join()
    assert errors == []
    _, book, audit = store.restore()
    assert book["d1"]["state"] == "DONE" and audit == ["from-thread"]


def test_llm_extra_body_and_dedicated_key_reach_the_request(monkeypatch):
    """A073: the internal LLM endpoint may be a GPU SGLang/LiteLLM relay — LLM_API_KEY (not the real OpenAI key) signs the
    request and LLM_EXTRA_BODY vendor fields are merged (Qwen thinking off, otherwise reasoning eats max_completion_tokens)."""
    monkeypatch.setattr(llm, "PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "real-openai-key-not-used")
    monkeypatch.setenv("LLM_API_KEY", "gpu-key")
    monkeypatch.setenv("LLM_EXTRA_BODY", '{"chat_template_kwargs": {"enable_thinking": false}}')
    seen = {}
    def fake(req, timeout):
        seen["auth"] = req.get_header("Authorization"); seen["body"] = json.loads(req.data)
        return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert llm.summarize(CARD, "fallback") == ("ok", llm.MODEL)
    assert seen["auth"] == "Bearer gpu-key" and seen["body"]["chat_template_kwargs"] == {"enable_thinking": False} and seen["body"]["max_completion_tokens"] == 600
    monkeypatch.setenv("LLM_EXTRA_BODY", "not json")
    assert llm.extra_body() == {}
