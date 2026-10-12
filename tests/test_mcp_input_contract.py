"""Advertised MCP input contracts fail before tools/call, including effects.

The session fixture is a protocol test double, never Google completion evidence.
"""
import copy

import pytest

from procsvc import mcp_check


@pytest.fixture
def session(monkeypatch):
    class Session:
        schema = {"type": "object", "properties": {"count": {"type": "integer", "minimum": 1},
                  "mode": {"enum": ["accepted", "declined"]},
                  "participants": {"type": "array", "minItems": 1,
                                   "items": {"type": "string"}}},
                  "required": ["count", "mode", "participants"], "additionalProperties": False}
        annotations = {"readOnlyHint": True}
        calls = []

        def request(self, method, params):
            if method == "tools/list":
                return {"tools": [{"name": "lookup", "inputSchema": copy.deepcopy(self.schema),
                                   "annotations": self.annotations}]}
            assert method == "tools/call"
            self.calls.append(params)
            return {"content": [{"type": "text", "text": "ok"}]}

    s = Session()
    s.calls = []
    monkeypatch.setattr(mcp_check, "_with_session", lambda spec, timeout, work: work(s))
    return s


VALID = {"count": 2, "mode": "accepted", "participants": ["example participant"]}


@pytest.mark.parametrize("effect", [False, True])
@pytest.mark.parametrize("change", [
    {"count": None}, {"count": True}, {"count": "2"}, {"count": 0},
    {"mode": "tentative"}, {"participants": []}, {"participants": [False]}, {"extra": 1},
])
def test_invalid_advertised_input_never_reaches_call(session, effect, change):
    args = dict(VALID, **change)
    out = (mcp_check.call_effect if effect else mcp_check.call)({}, "lookup", args)
    assert out["status"] == "refused" and out["error_kind"] == "input"
    assert session.calls == []


@pytest.mark.parametrize("effect", [False, True])
def test_required_and_fresh_contract_checked_every_call(session, effect):
    call = mcp_check.call_effect if effect else mcp_check.call
    assert call({}, "lookup", VALID)["status"] == "ok"
    session.schema["required"].append("calendar_id")
    assert call({}, "lookup", VALID)["error_kind"] == "input"
    assert len(session.calls) == 1


def test_effect_validates_after_idempotency_injection(session):
    session.schema = {"type": "object", "properties": {"idempotency_key": {"type": "string"}},
                      "required": ["idempotency_key"], "additionalProperties": False}
    out = mcp_check.call_effect({}, "lookup", {}, idempotency_key="instance:task")
    assert out["status"] == "ok" and out["idempotent"] is True
    assert session.calls[0]["arguments"] == {"idempotency_key": "instance:task"}


def test_local_ref_and_composition_are_validated(session):
    session.schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
                      "$defs": {"positive": {"type": "integer", "minimum": 1}},
                      "properties": {"count": {"$ref": "#/$defs/positive"}},
                      "allOf": [{"required": ["count"]}]}
    assert mcp_check.call({}, "lookup", {"count": 3})["status"] == "ok"
    assert mcp_check.call({}, "lookup", {"count": -1})["error_kind"] == "input"
    assert len(session.calls) == 1


@pytest.mark.parametrize("schema", [None, {"type": "unknown"},
    {"$schema": "https://example.invalid/unsupported-dialect"},
    {"$ref": "https://example.invalid/remote-schema"}, {"$ref": "file:///private-schema.json"},
    {"$ref": "#/missing"}])
def test_invalid_or_unavailable_schema_refuses_without_external_retrieval(session, schema):
    session.schema = schema
    out = mcp_check.call_effect({}, "lookup", {})
    assert out["status"] == "refused" and out["error_kind"] == "input_schema"
    assert session.calls == []
    assert "private-schema" not in out["error"] and "example.invalid" not in out["error"]


def test_rejected_credential_value_is_not_in_error(session):
    session.schema = {"type": "object", "properties": {"token": {"enum": ["expected"]}}, "required": ["token"]}
    out = mcp_check.call_effect({}, "lookup", {"token": "must-not-be-printed"})
    assert out["error_kind"] == "input" and "must-not-be-printed" not in str(out)
    assert session.calls == []


def test_input_validation_does_not_override_read_only_gate(session):
    session.annotations = {"readOnlyHint": False}
    out = mcp_check.call({}, "lookup", VALID)
    assert out["error_kind"] == "not_read_only" and session.calls == []
    assert mcp_check.call_effect({}, "lookup", VALID)["status"] == "ok"
