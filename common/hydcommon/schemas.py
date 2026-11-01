"""Payload contracts (v3 section 7.3) and their checks — one place for every service that reads or writes them.

Commands: the approval ledger (A148). Kafka carries no authentication, so process records every approval on the audit topic
(`CMD_APPROVAL_LEDGER_EVENT`, actor "process") with the command's fingerprint, and cmd-gateway forwards a command only when
that record exists for its cmdId and the fingerprint recomputed from the command matches. The fingerprint is an HMAC with a
key only process and cmd-gateway hold (`CMD_FINGERPRINT_KEY`; the start script writes one per PC into `.env`, compose
requires it). There is no default key: a service started without it stops with the variable's name.

Plant records: the edge publishes measurements, waveforms and PLC status on MQTT; connect-ingest copies them to Kafka and
the detector · connect-sink consume them. Kafka is reachable from the host (19092), so each consumer checks a record with
the same function the ingest used (tag_record · wave_record · status_record · alert_record · feat_record · audit_record) —
one malformed record is rejected with its reason (RecordError) instead of stopping a consumer.
"""
import hashlib
import hmac
import json
import math
import os
from datetime import datetime
from typing import Any

from .daq_contract import TAGS
from .topics import ASSETS

CMD_APPROVAL_LEDGER_EVENT = "CMD_APPROVAL_RECORDED"
CMD_FINGERPRINT_KEY_ENV = "CMD_FINGERPRINT_KEY"
_FINGERPRINT_FIELDS = ("cmdId", "asset", "incident", "actions", "approvedBy", "expiresAt", "approvalId")


def fingerprint_key(env=None) -> str:
    key = (os.environ if env is None else env).get(CMD_FINGERPRINT_KEY_ENV)
    if not key:
        raise ValueError(f"{CMD_FINGERPRINT_KEY_ENV} is not set — the start script writes it into .env and compose passes it "
                         "to process and cmd-gateway")
    return key


def cmd_fingerprint(cmd: dict, key: str | None = None) -> str:
    """HMAC-SHA256 over the command's approved fields (canonical JSON). Any change to the actions, asset, expiry, approver
    or approval id gives a different value, so the gateway can tell a forwarded command from the one process approved."""
    k = key if key is not None else fingerprint_key()
    canonical = json.dumps({f: cmd.get(f) for f in _FINGERPRINT_FIELDS}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(k.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def approval_ledger_record(cmd: dict, key: str | None = None) -> dict:
    """The audit `detail` process writes before publishing the command (what cmd-gateway keeps as its ledger)."""
    return {"cmdId": cmd["cmdId"], "approvalId": cmd["approvalId"], "approvedBy": cmd.get("approvedBy"),
            "expiresAt": cmd.get("expiresAt"), "fingerprint": cmd_fingerprint(cmd, key)}


# Ontology v2 atomic commands (Action.code) the PLC supports: fan / load setpoints, interlock reset, standby pump
# selection (actr:pump-selector) and a planned stop. PRESSURE_SET exists in the ontology only as the forbidden old
# procedure (rule:no-pressure-raise), this PLC has no pressure setpoint, so the gateway rejects it (WHITELIST).
# action code -> (PLC resource, parameter key in action.cmd or None)
ACTION_TO_WRITES = {
    "FAN_SET": ("FanSpeedSP", "fan_pct"),
    "LOAD_SET": ("LoadSP", "load_pct"),
    "RESET": ("Reset", None),
    "PUMP_SELECT": ("PumpSelect", "pump"),
    "STOP": ("Stop", None),
}
ACTION_WHITELIST = frozenset(ACTION_TO_WRITES)
PUMP_CODES = {"A": 0, "B": 1}      # PumpSelect write value (the ontology Action value is the pump letter)
MODES = ("LOCAL", "REMOTE_MANUAL", "REMOTE_AUTO")
PLC_STATES = ("RUN", "STOP", "TRIP")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ALERT_STATES = ("RAISE", "CLEAR")

_REQUIRED_CMD_FIELDS = ("cmdId", "asset", "incident", "source", "actions", "approvedBy", "expiresAt")


def _parameter_problem(i: int, action: dict) -> str | None:
    _, key = ACTION_TO_WRITES[action["code"]]
    if key is None:
        return None
    if key not in action:
        return f"actions[{i}] {action['code']} needs parameter {key}"
    value = action[key]
    if key == "pump":
        return None if value in PUMP_CODES else f"actions[{i}] pump must be one of {sorted(PUMP_CODES)}"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return f"actions[{i}] {key} must be a finite number"
    return None


def validate_action_cmd(d: Any) -> list[str]:
    """Return a list of problems; empty list means the action.cmd message is well formed — every action is a known code
    with its parameter present and of the right type, so actions_to_writes cannot fail on it (the PLC still checks ranges)."""
    if not isinstance(d, dict):
        return ["payload is not an object"]
    errs = [f"missing field: {f}" for f in _REQUIRED_CMD_FIELDS if f not in d]
    if "cmdId" in d and (not isinstance(d["cmdId"], str) or not d["cmdId"].strip()):
        errs.append("cmdId must be non-empty text")
    if "asset" in d and d["asset"] not in ASSETS:
        errs.append(f"asset must be one of {list(ASSETS)}")
    if "expiresAt" in d and not isinstance(d["expiresAt"], str):
        errs.append("expiresAt must be ISO time text")
    if "actions" in d:
        if not isinstance(d["actions"], list) or not d["actions"]:
            errs.append("actions must be a non-empty list")
        else:
            for i, a in enumerate(d["actions"]):
                if not isinstance(a, dict) or "code" not in a:
                    errs.append(f"actions[{i}] missing code")
                elif a["code"] in ACTION_TO_WRITES:
                    problem = _parameter_problem(i, a)
                    if problem:
                        errs.append(problem)
    if d.get("source") not in (None, "HITL"):
        errs.append("source must be HITL")
    return errs


def actions_to_writes(actions: list[dict]) -> list[dict]:
    """[{code:FAN_SET, fan_pct:100}] -> [{res:FanSpeedSP, v:100}] (v3 7.3 cmd/auto form). Input checked by validate_action_cmd."""
    writes = []
    for a in actions:
        res, key = ACTION_TO_WRITES[a["code"]]
        v = 1 if key is None else a[key]
        writes.append({"res": res, "v": PUMP_CODES[v] if key == "pump" else v})
    return writes


# ---------------------------------------------------------------- plant records (MQTT payload -> Kafka record)
class RecordError(ValueError):
    """One record does not match its contract; the message names the field."""


def _time(body: dict, field: str) -> str:
    value = body.get(field)
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        except ValueError:
            stamp = None
        if stamp is not None and stamp.tzinfo is not None:
            return value
    raise RecordError(f"{field} must be ISO time text with a time zone")


def _number(value, field: str, allow_none: bool = False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RecordError(f"{field} must be a finite number")
    return float(value)


def _object(body) -> dict:
    if not isinstance(body, dict) or "_raw" in body:
        raise RecordError("payload is not a JSON object")
    return body


def _asset(asset) -> str:
    if asset not in ASSETS:
        raise RecordError(f"asset must be one of {list(ASSETS)}")
    return asset


def tag_record(asset: str, name: str, body: Any) -> dict:
    """plant/{a}/tag/{name} payload {"t","v","q"} -> plant.tag record {"asset","name","t","v","q"}."""
    body = _object(body)
    if name not in TAGS:
        raise RecordError(f"tag {name!r} is not a DAQ tag")
    q = body.get("q", "good")
    if not isinstance(q, str) or not 0 < len(q) <= 32:
        raise RecordError("q must be quality text")
    return {"asset": _asset(asset), "name": name, "t": _time(body, "t"), "v": _number(body.get("v"), "v"), "q": q}


def wave_record(asset: str, sensor: str, body: Any) -> dict:
    """plant/{a}/wave/{sensor} payload {"t0","hz","v":[...]} -> plant.wave record."""
    body = _object(body)
    if sensor not in TAGS:
        raise RecordError(f"sensor {sensor!r} is not a DAQ tag")
    hz = body.get("hz")
    if isinstance(hz, bool) or not isinstance(hz, int) or not 1 <= hz <= 1000:
        raise RecordError("hz must be an integer 1..1000")
    v = body.get("v")
    if not isinstance(v, list) or not 1 <= len(v) <= hz:
        raise RecordError("v must be a list of 1..hz samples")
    return {"asset": _asset(asset), "sensor": sensor, "t0": _time(body, "t0"), "hz": hz,
            "v": [_number(x, f"v[{i}]") for i, x in enumerate(v)]}


def status_record(asset: str, body: Any) -> dict:
    """plant/{a}/status payload -> plant.status record. The asset is the topic's: a payload naming another asset is refused
    (one unit's status must never be filed under another)."""
    body = _object(body)
    if body.get("asset", asset) != asset:
        raise RecordError(f"payload asset {body.get('asset')!r} differs from the topic's {asset}")
    if body.get("mode") not in MODES:
        raise RecordError(f"mode must be one of {list(MODES)}")
    if body.get("state") not in PLC_STATES:
        raise RecordError(f"state must be one of {list(PLC_STATES)}")
    if body.get("trip") is not None and not isinstance(body["trip"], str):
        raise RecordError("trip must be text or null")
    for field in ("cmdId", "result", "reason", "source"):
        if body.get(field) is not None and not isinstance(body[field], str):
            raise RecordError(f"{field} must be text or null")
    _time(body, "t")
    return {**body, "asset": _asset(asset)}


def alert_record(body: Any) -> dict:
    """alerts topic record (detector RAISE / CLEAR)."""
    body = _object(body)
    _asset(body.get("asset"))
    if not isinstance(body.get("alertId"), str) or not body["alertId"]:
        raise RecordError("alertId must be non-empty text")
    if not isinstance(body.get("pattern"), str) or not body["pattern"]:
        raise RecordError("pattern must be non-empty text")
    if body.get("name") is not None and (not isinstance(body["name"], str) or not body["name"]):
        raise RecordError("name must be the pattern's display name or null")
    if body.get("state") not in ALERT_STATES:
        raise RecordError(f"state must be one of {list(ALERT_STATES)}")
    if body.get("severity") not in SEVERITIES:
        raise RecordError(f"severity must be one of {list(SEVERITIES)}")
    if not isinstance(body.get("evidence", {}), dict):
        raise RecordError("evidence must be an object")
    _time(body, "t")
    return body


def feat_record(body: Any) -> dict:
    """feat.1s record (detector features): asset · sensor · t and four numbers that may be null."""
    body = _object(body)
    _asset(body.get("asset"))
    if body.get("sensor") not in TAGS:
        raise RecordError("sensor must be a DAQ tag")
    _time(body, "t")
    return {**body, **{k: _number(body.get(k), k, allow_none=True) for k in ("mean", "rms", "slope", "score")}}


def audit_record(body: Any) -> dict:
    """audit topic record: t · actor · event (text) and an object detail."""
    body = _object(body)
    for field in ("actor", "event"):
        if not isinstance(body.get(field), str) or not body[field]:
            raise RecordError(f"{field} must be non-empty text")
    if body.get("incident") is not None and not isinstance(body["incident"], str):
        raise RecordError("incident must be text or null")
    if not isinstance(body.get("detail", {}), dict):
        raise RecordError("detail must be an object")
    _time(body, "t")
    return body
