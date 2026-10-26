"""Internal, claim-bound OAuth credentials; never mounted on a portal route."""
import hmac
import hashlib
import base64
import json
import os
import time
import math
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from . import mcp_registry, mcp_secrets, mcp_check


def _key() -> str:
    key_file = Path(os.getenv("HYD_WORKER_RUNTIME_KEY_FILE", "/data/mcp/worker-runtime.key"))
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except OSError:
        raise HTTPException(503, "실행 연결 인증 파일이 준비되지 않았습니다") from None
    if len(key) < 32:
        raise HTTPException(503, "실행 연결 인증 파일이 올바르지 않습니다")
    return key


def _claim(runtime, body):
    tenant = body.get("tenant_id")
    if tenant != runtime.tenant_id:
        raise HTTPException(403, "실행 연결의 교육 공간이 일치하지 않습니다")
    row = runtime.repo.get_workitem(str(body.get("todo_id") or ""))
    consumer = body.get("consumer")
    if not row or row.get("tenant_id") != tenant or not consumer or row.get("consumer") != consumer or \
            row.get("status") != "IN_PROGRESS" or row.get("draft_status") != "STARTED":
        raise HTTPException(409, "현재 담당 실행기가 시작한 단계에서만 연결할 수 있습니다")
    lease = row.get("lease_until")
    try:
        if isinstance(lease,str) and ('T' in lease or 'Z' in lease):
            lease=datetime.fromisoformat(lease.replace('Z','+00:00'))
        if isinstance(lease,datetime) and lease.tzinfo is None:
            raise ValueError('lease timezone missing')
        until = lease.timestamp() if isinstance(lease, datetime) else float(lease)
        if not math.isfinite(until):raise ValueError('invalid lease')
    except (TypeError, ValueError):
        raise HTTPException(409, "현재 실행 단계의 유효한 임대 시간이 없습니다") from None
    if until <= time.time():
        raise HTTPException(409, "현재 실행 단계의 임대 시간이 만료되었습니다")
    return row


def _entry(runtime, name, fingerprint):
    entry = mcp_registry.store_for(runtime.repo).servers(runtime.tenant_id).get(name)
    if not entry or mcp_registry.fingerprint(entry) != fingerprint:
        raise HTTPException(409, "실행 연결 설정이 바뀌었습니다. 다시 연결을 확인하세요")
    if not (entry.get("hyd") or {}).get("oauth_connection"):
        raise HTTPException(422, "로그인 연결 서버만 실행 자격증명을 요청할 수 있습니다")
    if mcp_check.normalize(entry)["transport"] != "streamable_http":
        raise HTTPException(422, "로그인 실행 연결은 Streamable HTTP만 지원합니다. 기존 SSE 연결은 지원하지 않습니다")
    gate = (entry.get("hyd") or {}).get("gate") or {}
    if gate.get("fingerprint") != fingerprint or not gate.get("read_tools"):
        raise HTTPException(409, "읽기 도구 연결 검사를 다시 확인하세요")
    return entry


def resolve(runtime, body: dict, authorization: str | None) -> dict:
    key = _key()
    supplied = (authorization or "").removeprefix("Bearer ")
    if not hmac.compare_digest(supplied.encode(), key.encode()):
        raise HTTPException(403, "실행 연결 인증을 확인할 수 없습니다")
    row = _claim(runtime, body)
    tenant, consumer = runtime.tenant_id, body["consumer"]
    requested = body.get("servers")
    if not isinstance(requested, dict) or not requested or len(requested) > 100:
        raise HTTPException(422, "실행 연결 서버 목록이 올바르지 않습니다")
    headers = {}
    for name, fingerprint in requested.items():
        entry = _entry(runtime, name, fingerprint)
        try:
            mcp_secrets.runtime_spec(runtime.repo, tenant, name, entry)
        except mcp_secrets.SecretError as exc:
            raise HTTPException(exc.status, exc.reason) from None
        capability = dict(tenant_id=tenant, todo_id=row["id"], consumer=consumer, name=name,
                          fingerprint=fingerprint, expires=time.time() + 1800, nonce=secrets.token_hex(16))
        encoded = base64.urlsafe_b64encode(json.dumps(capability, separators=(",", ":")).encode()).decode()
        signature = hmac.new(key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        headers[name] = {"fingerprint": fingerprint, "path": "/internal/worker/mcp/" + name,
                        "headers": {"Authorization": "HydRuntime " + encoded + "." + signature}}
    return {"tenant_id": tenant, "todo_id": row["id"], "consumer": consumer, "servers": headers}


def authorize_relay(runtime, name, authorization):
    try:
        if not authorization or not authorization.startswith("HydRuntime ") or len(authorization) > 4096:
            raise ValueError()
        encoded, signature = authorization.removeprefix("HydRuntime ").split(".")
        expected = hmac.new(_key().encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        binding = json.loads(base64.urlsafe_b64decode(encoded))
        if binding["name"] != name or not time.time() < binding["expires"] <= time.time() + 1801:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(403, "실행 연결 권한이 만료되었거나 일치하지 않습니다") from None
    _claim(runtime, binding)
    entry = _entry(runtime, name, binding["fingerprint"])
    return binding, entry
