"""G2 (전체 과정 랩업, docs/handoff/verification/2026-10-09/capstone-lab.md 5.2) — MCP 서버 설정의 비밀 자리표시자 `${SECRET:KEY}`.

구글처럼 토큰이 필요한 서버를 학생 · 강사가 등록할 때, 설정(tenants.mcp)에는 토큰 대신 자리표시자만 둔다:

  "my-drive": {"type": "url", "url": "https://…/mcp", "headers": {"Authorization": "Bearer ${SECRET:GOOGLE_TOKEN}"}}

값은 별도 칸(public.mcp_secrets, migration 20261009000050)에 두고, 실행 직전에만 채운다 — 연결 검사(mcp_registry.run_check),
도구 지도 써 보기(mcp_api.spec_of), 승인 뒤 시스템 task(instance_mode.mcp_call), 워커가 에이전트용 .mcp.json 을 쓸 때(bridge.install).
값은 어떤 API 응답에도 실리지 않는다(GET 은 이름 · 고친 시각 · 쓰는 서버만). 토큰을 갈아 끼워도 설정 해시(fingerprint)는 그대로라
연결 검사 도장이 유지된다 — 해시는 자리표시자가 든 설정으로 계산한다.

참고(같은 모양): ProcessGPT mcp-hub `services/mcp-hub/src/mcp_hub/catalog.py` 115~137행 resolve_template(헤더의 ${SECRET:X} 를
입력받은 env 로 치환), `gallery/servers.json` 108행("Authorization": "Bearer ${SECRET:GITHUB_TOKEN}"), `conformance.py` 57~63행
(하드코딩된 시크릿 경고). 다른 점: mcp-hub 는 설치 때 한 번 채워 연결정보에 저장하지만, 여기서는 설정에 자리표시자를 남기고
실행 때마다 채운다 — "비밀은 설정 · 화면에 남지 않는다"(설계 G2 ①).

자리표시자는 headers 와 env 값에서만 읽는다(mcp-hub 도 headers · env). url · args 안의 자리표시자는 채우지 않고 사유와 함께 거절한다 —
워커가 실행 뒤 작업 폴더에서 지우는 칸이 env · headers 뿐이라서다(bridge.cleanup).

값 찾는 순서: 비밀 값 표(포털에서 넣음) → 환경 변수 HYD_SECRET_<KEY>(강사가 워커 · process 환경에 직접 둘 때).
OAuth 동의 · 갱신은 하지 않는다(구글 인증은 사용자가 맡는다) — 토큰이 만료되면 401 사유와 함께 연결 검사가 실패한다.
"""
from __future__ import annotations

import os
import re
from copy import deepcopy

PLACEHOLDER_RE = re.compile(r"\$\{SECRET:([^}]*)\}")
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
ENV_PREFIX = "HYD_SECRET_"
FIELDS = ("headers", "env")                      # 자리표시자를 채우는 칸
MAX_VALUE = 8000
#: 값 전체가 자리표시자(+ 인증 방식 낱말)이면 화면에 그대로 보여도 된다 — 비밀이 아니라 비밀의 이름이다
_SCHEMES = ("", "bearer", "basic", "token")


class SecretError(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def valid_key(key: str) -> bool:
    return bool(KEY_RE.match(str(key or "")))


def is_reference_only(value) -> bool:
    """'${SECRET:X}' · 'Bearer ${SECRET:X}' 처럼 비밀 값이 아니라 비밀 이름만 든 값인가(가리지 않아도 되는가)."""
    if not isinstance(value, str) or "${SECRET:" not in value:
        return False
    rest = PLACEHOLDER_RE.sub("", value).strip().lower()
    return rest in _SCHEMES


def references(entry) -> list[str]:
    """설정 한 칸이 쓰는 비밀 이름(중복 없이, 나온 순서). headers · env 값만 본다."""
    out: list[str] = []
    if not isinstance(entry, dict):
        return out
    for field in FIELDS:
        values = entry.get(field)
        if not isinstance(values, dict):
            continue
        for v in values.values():
            for key in PLACEHOLDER_RE.findall(v if isinstance(v, str) else ""):
                if key not in out:
                    out.append(key)
    return out


def misplaced(entry) -> list[str]:
    """headers · env 밖(url · args · command)의 자리표시자, 이름 규칙에 맞지 않는 자리표시자 — 등록 때 사유로 거절한다."""
    out: list[str] = []
    if not isinstance(entry, dict):
        return out
    for field in ("url", "command"):
        if isinstance(entry.get(field), str) and "${SECRET:" in entry[field]:
            out.append(f"{field}: 비밀 자리표시자는 headers · env 값에만 쓸 수 있습니다")
    if any(isinstance(a, str) and "${SECRET:" in a for a in entry.get("args") or []):
        out.append("args: 비밀 자리표시자는 headers · env 값에만 쓸 수 있습니다 — 서버가 환경 변수로 받게 하세요")
    for key in references(entry):
        if not valid_key(key):
            out.append(f"${{SECRET:{key}}}: 비밀 이름은 대문자 · 숫자 · 밑줄(_) 64자 이내, 첫 글자는 대문자여야 합니다 (예: GOOGLE_TOKEN)")
    return out


def literal_secrets(entry) -> list[str]:
    """비밀처럼 보이는 이름(Authorization · *TOKEN · *KEY …)에 자리표시자가 아닌 값을 그대로 넣은 칸 — 등록 응답의 경고
    (mcp-hub conformance.py 57~63행 'secrets' 검사와 같은 뜻: 하드코딩 대신 ${SECRET:KEY} 를 쓰라)."""
    from .mcp_check import is_secret_key
    out = []
    for field in FIELDS:
        values = entry.get(field) if isinstance(entry, dict) else None
        if not isinstance(values, dict):
            continue
        for k, v in values.items():
            if is_secret_key(k) and isinstance(v, str) and v.strip() and "${SECRET:" not in v:
                out.append(f"{field}.{k}")
    return out


def env_values(environ=None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    return {k[len(ENV_PREFIX):]: v for k, v in env.items() if k.startswith(ENV_PREFIX) and valid_key(k[len(ENV_PREFIX):]) and v != ""}


def resolve(entry: dict, values: dict[str, str] | None) -> tuple[dict, list[str]]:
    """자리표시자를 채운 사본과 값이 없는 비밀 이름 목록. 값이 하나라도 없으면 그 칸은 그대로 둔다(호출하는 쪽이 사유로 멈춘다)."""
    out = deepcopy(entry) if isinstance(entry, dict) else entry
    missing: list[str] = []
    if not isinstance(out, dict):
        return out, missing
    values = values or {}
    for field in FIELDS:
        block = out.get(field)
        if not isinstance(block, dict):
            continue
        for k, v in list(block.items()):
            if not isinstance(v, str) or "${SECRET:" not in v:
                continue

            def fill(m):
                key = m.group(1)
                if key in values and values[key] not in (None, ""):
                    return str(values[key])
                if key not in missing:
                    missing.append(key)
                return m.group(0)
            block[k] = PLACEHOLDER_RE.sub(fill, v)
    return out, missing


def missing_reason(name: str | None, missing: list[str]) -> str:
    keys = " · ".join(missing)
    who = f"MCP 서버 '{name}' 에 필요한" if name else "이 서버에 필요한"
    return (f"{who} 비밀 값 {keys} 이(가) 없습니다 — 포털 MCP 화면의 '비밀 값'에 넣거나 "
            f"환경 변수 {ENV_PREFIX}<이름> 으로 두세요")


# ---------------------------------------------------------------- 저장소 (public.mcp_secrets)
class MemorySecretStore:
    def __init__(self, repo):
        self.repo = repo
        if not hasattr(repo, "_mcp_secrets"):
            repo._mcp_secrets = {}
        self.rows = repo._mcp_secrets

    def values(self, tenant_id) -> dict[str, str]:
        return {k: r["value"] for (t, k), r in self.rows.items() if t == tenant_id}

    def keys(self, tenant_id) -> list[dict]:
        return [{"key": k, "updated_at": r.get("updated_at"), "updated_by": r.get("updated_by")}
                for (t, k), r in sorted(self.rows.items()) if t == tenant_id]

    def put(self, tenant_id, key, value, by, now) -> None:
        self.rows[(tenant_id, key)] = {"value": value, "updated_by": by, "updated_at": now}

    def delete(self, tenant_id, key) -> bool:
        return self.rows.pop((tenant_id, key), None) is not None

    def delete_all(self, tenant_id) -> int:
        keys = [k for k in self.rows if k[0] == tenant_id]
        for k in keys:
            del self.rows[k]
        return len(keys)


class PgSecretStore:
    """public.mcp_secrets (migration 20261009000050). 표가 없으면 모든 동작이 503 사유로 멈춘다 — 표가 없는 것을
    '값이 없음'(빈 dict · 0건)으로 보이면 강사는 값을 넣으라는 엉뚱한 안내만 받는다."""
    MISSING = "비밀 값 표(public.mcp_secrets)가 없습니다 — it/supabase/migrations/20261009000050_mcp_secrets.sql 을 적용하세요"

    def __init__(self, repo):
        self.repo = repo

    def _require(self, c) -> None:
        if not c.execute("select to_regclass('public.mcp_secrets') is not null as ok").fetchone()["ok"]:
            raise SecretError(503, self.MISSING)

    def values(self, tenant_id) -> dict[str, str]:
        with self.repo._conn() as c:
            self._require(c)
            return {r["key"]: r["value"] for r in c.execute("select key, value from mcp_secrets where tenant_id = %s", (tenant_id,)).fetchall()}

    def keys(self, tenant_id) -> list[dict]:
        with self.repo._conn() as c:
            self._require(c)
            rows = c.execute("select key, updated_at, updated_by from mcp_secrets where tenant_id = %s order by key", (tenant_id,)).fetchall()
        return [{"key": r["key"], "updated_at": r["updated_at"].isoformat() if hasattr(r["updated_at"], "isoformat") else r["updated_at"],
                 "updated_by": r["updated_by"]} for r in rows]

    def put(self, tenant_id, key, value, by, now) -> None:
        with self.repo._conn() as c:
            self._require(c)
            c.execute("insert into mcp_secrets (tenant_id, key, value, updated_by, updated_at) values (%s, %s, %s, %s, now()) "
                      "on conflict (tenant_id, key) do update set value = excluded.value, updated_by = excluded.updated_by, updated_at = now()",
                      (tenant_id, key, value, by))

    def delete(self, tenant_id, key) -> bool:
        with self.repo._conn() as c:
            self._require(c)
            return c.execute("delete from mcp_secrets where tenant_id = %s and key = %s", (tenant_id, key)).rowcount == 1

    def delete_all(self, tenant_id) -> int:
        with self.repo._conn() as c:
            self._require(c)
            return c.execute("delete from mcp_secrets where tenant_id = %s", (tenant_id,)).rowcount or 0


def store_for(repo):
    if hasattr(repo, "dsn") and hasattr(repo, "_conn"):
        return PgSecretStore(repo)
    return MemorySecretStore(repo)


def load(repo, tenant_id: str, environ=None) -> dict[str, str]:
    """실행 직전에 채울 값: 환경 변수 HYD_SECRET_* 위에 비밀 값 표를 덮는다(표가 이긴다). 표가 없으면 환경 변수만."""
    values = env_values(environ)
    if repo is not None:
        values.update(store_for(repo).values(tenant_id))
    return values


def runtime_spec(repo, tenant_id: str, name: str, entry: dict, environ=None) -> tuple[dict, list[str]]:
    """실행 직전 설정: (자리표시자를 채운 사본, 채운 비밀 값들 — 결과 · 오류를 redact 할 때 쓴다).
    값이 없으면 SecretError(422, 사유) — 빈 토큰으로 부르지 않는다. 자리표시자가 없으면 표를 읽지 않는다."""
    keys = references(entry)
    if not keys:
        return entry, []
    values = load(repo, tenant_id, environ)
    resolved, missing = resolve(entry, values)
    if missing:
        raise SecretError(422, missing_reason(name, missing))
    return resolved, [values[k] for k in keys]


#: 이보다 짧은 값은 가리지 않는다 — 한두 글자 값으로 응답 전체를 망가뜨리지 않게(그런 값은 비밀이라 볼 수 없다)
REDACT_MIN = 4
REDACTED = "[비밀 값 가림]"


def redact(obj, used: list[str]):
    """응답 · 감사 · 검사 기록에 실릴 값에서 실행 때 채운 비밀 값을 지운다. 서버가 토큰을 되돌려 주거나(오류 본문 · 에코 도구)
    stdio 서버가 stderr 에 환경 변수를 찍어도 값이 화면 · 저장소로 새지 않게 한다."""
    secrets = sorted({v for v in used or [] if isinstance(v, str) and len(v) >= REDACT_MIN}, key=len, reverse=True)
    if not secrets:
        return obj

    def walk(v):
        if isinstance(v, str):
            for s in secrets:
                if s in v:
                    v = v.replace(s, REDACTED)
            return v
        if isinstance(v, dict):
            return {walk(k) if isinstance(k, str) else k: walk(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return type(v)(walk(x) for x in v)
        return v
    return walk(obj)


# ---------------------------------------------------------------- 동작 (API 가 부른다)
def overview(repo, tenant_id: str, servers: dict, environ=None) -> dict:
    """이름 · 고친 시각 · 쓰는 서버 · 값 있음 여부. 값은 싣지 않는다."""
    stored = {r["key"]: r for r in store_for(repo).keys(tenant_id)}
    env = env_values(environ)
    used: dict[str, list[str]] = {}
    for name, entry in (servers or {}).items():
        for key in references(entry):
            used.setdefault(key, []).append(name)
    keys = sorted(set(stored) | set(used))
    return {"tenant": tenant_id, "rule": "비밀 값은 저장만 하고 다시 보여 주지 않습니다. 서버 설정의 headers · env 에 ${SECRET:이름} 으로 적으면 "
                                         "연결 검사 · 시스템 task · 에이전트 실행 직전에 채웁니다.",
            "secrets": [{"key": k, "stored": k in stored, "from_env": k in env and k not in stored,
                         "updated_at": (stored.get(k) or {}).get("updated_at"), "updated_by": (stored.get(k) or {}).get("updated_by"),
                         "used_by": used.get(k, []), "missing": k not in stored and k not in env} for k in keys]}


def put(repo, tenant_id: str, key: str, value, by: str, now: str) -> dict:
    if not valid_key(key):
        raise SecretError(422, "key: 대문자 · 숫자 · 밑줄(_) 64자 이내, 첫 글자는 대문자여야 합니다 (예: GOOGLE_TOKEN)")
    if not isinstance(value, str) or not value.strip():
        raise SecretError(422, "value: 비밀 값이 비었습니다")
    if len(value) > MAX_VALUE:
        raise SecretError(422, f"value: {MAX_VALUE}자 이하여야 합니다")
    if "${SECRET:" in value:
        raise SecretError(422, "value: 비밀 값 안에 다른 자리표시자를 쓸 수 없습니다")
    store_for(repo).put(tenant_id, key, value.strip(), by, now)
    return {"key": key, "stored": True, "updated_by": by, "updated_at": now}


def remove(repo, tenant_id: str, key: str) -> dict:
    if not store_for(repo).delete(tenant_id, key):
        raise SecretError(404, f"비밀 값 '{key}' 가 없습니다")
    return {"key": key, "deleted": True}


def mount(app, *, runtime_factory, audit):
    import asyncio

    from fastapi import HTTPException

    from . import mcp_check, mcp_registry

    def runtime():
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(503, "비밀 값에는 instance 실행 서비스가 필요합니다 (PROCESS_MODE=instance)")
        return rt

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except (SecretError, mcp_registry.RegistryError) as e:
            raise HTTPException(e.status, e.reason) from e

    @app.get("/api/mcp/secrets")
    async def list_secrets():
        rt = runtime()
        return await run(lambda: overview(rt.repo, rt.tenant_id, mcp_registry.store_for(rt.repo).servers(rt.tenant_id)))

    @app.put("/api/mcp/secrets/{key}")
    async def put_secret(key: str, body: dict | None = None):
        rt = runtime()
        body = body or {}
        by = str(body.get("by") or "포털")[:60]

        def work():
            out = put(rt.repo, rt.tenant_id, key, body.get("value"), by, mcp_check._now_z())
            audit("-", by, "MCP_SECRET_SET", {"key": key})                       # 값은 감사 기록에도 남기지 않는다
            return out
        return await run(work)

    @app.delete("/api/mcp/secrets/{key}")
    async def delete_secret(key: str, by: str = "포털"):
        rt = runtime()

        def work():
            out = remove(rt.repo, rt.tenant_id, key)
            audit("-", by[:60], "MCP_SECRET_DELETED", {"key": key})
            return out
        return await run(work)
