"""Payload contracts (v3 section 7.3) and validation helpers."""
import hashlib
import hmac
import json
import os
from typing import Any

# A148 (remaining-sweep 69): the approval ledger. Kafka and MQTT carry no authentication, so before this a client that could
# write to `action.cmd` had a command executed by the PLC (`.evidence/a148/69/`: forged FAN_SET passed all five checks and
# ACKed DONE). Now process records every approval on the audit topic (`CMD_APPROVAL_LEDGER_EVENT`, actor "process") with the
# command's fingerprint, and cmd-gateway forwards a command only when that record exists for its cmdId and the fingerprint
# recomputed from the command matches. The fingerprint is an HMAC with a key only process and cmd-gateway hold
# (`CMD_FINGERPRINT_KEY`, compose default below — set a private value in `.env` for anything beyond the classroom).
CMD_APPROVAL_LEDGER_EVENT = "CMD_APPROVAL_RECORDED"
CMD_FINGERPRINT_KEY_ENV = "CMD_FINGERPRINT_KEY"
CMD_FINGERPRINT_DEFAULT_KEY = "hyd-cmd-approval-local"
_FINGERPRINT_FIELDS = ("cmdId", "asset", "incident", "actions", "approvedBy", "expiresAt", "approvalId")


def cmd_fingerprint(cmd: dict, key: str | None = None) -> str:
    """HMAC-SHA256 over the command's approved fields (canonical JSON). Any change to the actions, asset, expiry, approver
    or approval id gives a different value, so the gateway can tell a forwarded command from the one process approved."""
    k = key if key is not None else os.getenv(CMD_FINGERPRINT_KEY_ENV, CMD_FINGERPRINT_DEFAULT_KEY)
    canonical = json.dumps({f: cmd.get(f) for f in _FINGERPRINT_FIELDS}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(k.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def approval_ledger_record(cmd: dict, key: str | None = None) -> dict:
    """The audit `detail` process writes before publishing the command (what cmd-gateway keeps as its ledger)."""
    return {"cmdId": cmd["cmdId"], "approvalId": cmd["approvalId"], "approvedBy": cmd.get("approvedBy"),
            "expiresAt": cmd.get("expiresAt"), "fingerprint": cmd_fingerprint(cmd, key)}

# Ontology v2 atomic commands (Action.code) the PLC supports: fan / load setpoints, interlock reset, standby pump
# selection (actr:pump-selector) and a planned stop. PRESSURE_SET exists in the ontology only as the forbidden old
# procedure (rule:no-pressure-raise), this PLC has no pressure setpoint, so the gateway rejects it (WHITELIST).
# FAN_BOOST / REDUCE_LOAD are the v1 names, kept for old cards.
ACTION_WHITELIST = {"FAN_SET", "LOAD_SET", "RESET", "PUMP_SELECT", "STOP", "FAN_BOOST", "REDUCE_LOAD"}
# action code -> (PLC resource, parameter key in action.cmd)
ACTION_TO_WRITES = {
    "FAN_SET": ("FanSpeedSP", "fan_pct"),
    "LOAD_SET": ("LoadSP", "load_pct"),
    "RESET": ("Reset", None),
    "PUMP_SELECT": ("PumpSelect", "pump"),
    "STOP": ("Stop", None),
    "FAN_BOOST": ("FanSpeedSP", "fan_pct"),
    "REDUCE_LOAD": ("LoadSP", "load_pct"),
}
PUMP_CODES = {"A": 0, "B": 1}      # PumpSelect write value (the ontology Action value is the pump letter)
MODES = ("LOCAL", "REMOTE_MANUAL", "REMOTE_AUTO")

_REQUIRED_CMD_FIELDS = ("cmdId", "asset", "incident", "source", "actions", "approvedBy", "expiresAt")


def validate_action_cmd(d: Any) -> list[str]:
    """Return a list of problems; empty list means the action.cmd message is well formed."""
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["payload is not an object"]
    for f in _REQUIRED_CMD_FIELDS:
        if f not in d:
            errs.append(f"missing field: {f}")
    if "actions" in d:
        if not isinstance(d["actions"], list) or not d["actions"]:
            errs.append("actions must be a non-empty list")
        else:
            for i, a in enumerate(d["actions"]):
                if not isinstance(a, dict) or "code" not in a:
                    errs.append(f"actions[{i}] missing code")
    if d.get("source") not in (None, "HITL"):
        errs.append("source must be HITL")
    return errs


def actions_to_writes(actions: list[dict]) -> list[dict]:
    """[{code:FAN_BOOST, fan_pct:100}] -> [{res:FanSpeedSP, v:100}] (v3 7.3 cmd/auto form)."""
    writes = []
    for a in actions:
        res, key = ACTION_TO_WRITES[a["code"]]
        v = 1 if key is None else a[key]
        if key == "pump":
            v = PUMP_CODES[str(v).upper()] if str(v).upper() in PUMP_CODES else v
        writes.append({"res": res, "v": v})
    return writes
