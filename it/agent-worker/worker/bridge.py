"""Registering the tenant's MCP tools (process-gpt-cli-agent/core/bridge.py).

Tools reach a CLI agent as MCP servers registered per run. The servers come from `tenants.mcp` in the product's own
shape — `mcpServers: {name: {command, args, env}}` for stdio servers, `{type: "url", url, transport}` for streamable-HTTP
servers (the shape process-gpt-sample-app-wms documents). Claude Code reads the run's `.mcp.json`
(--mcp-config --strict-mcp-config), so one run's tools stay in one run's workspace; HTTP servers are written in Claude Code's
native `{type: "http", url, headers}` form.

G2 (PBL — 학생이 등록한 서버):
  ⓪ an HTTP server's `headers` (a token-protected server such as Google's) are written into .mcp.json with it — the
     portal's connection check (procsvc/mcp_check._StreamableHttp) and the system task after approval already send them,
     so without this the agent alone failed authentication. cleanup() removes them after the run like `env`.
  ① `${SECRET:KEY}` placeholders in headers/env are filled here, right before the file is written (ProcessGPT mcp-hub
     catalog.py resolve_template, 115~137). The values come from context.prepare (the mcp_secrets table + HYD_SECRET_*),
     carried next to mcpServers under SECRETS_KEY so select_servers/gate_servers pass them through without a runner change;
     the gate leaves out a server whose secret has no value, with a reason the runner already reports. Fingerprints are
     computed on the placeholder form, so swapping a token keeps the connection-check stamp.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from cliagents import McpServer
from procsvc import mcp_secrets

MCP_CONFIG_FILENAME = ".mcp.json"
CONFIG_HOME_DIRNAME = ".agent-home"
#: B2: the HYD-only key of a tenants.mcp entry (origin · connection-check stamp). Never written to .mcp.json.
META_KEY = "hyd"
#: G2: top-level key of the run's tenant_mcp copy that carries secret values from context.prepare to install(). Never written out.
SECRETS_KEY = "hydSecrets"
#: G2: why the secret lookup failed (context.with_secrets) — the drop reason names it instead of "no value"
SECRETS_ERROR_KEY = "hydSecretsError"
RUNTIME_KEY = "hydRuntimeCredentials"
_PRIVATE_KEYS = (SECRETS_KEY, SECRETS_ERROR_KEY, RUNTIME_KEY)


@dataclass
class BridgeResult:
    servers: list[str] = field(default_factory=list)
    config_path: str | None = None
    env: dict[str, str] = field(default_factory=dict)       # environment the run must inherit (config-dir isolation)
    extra_args: list[str] = field(default_factory=list, repr=False)
    dropped: dict[str, str] = field(default_factory=dict)   # G2: server -> why install left it out (a secret without a value)
    redaction_values: list[str] = field(default_factory=list, repr=False)


def cleanup(workdir: Path) -> list[str]:
    """A096 (process-gpt-cli-agent RuntimeLease: provider files are restored after the run because they carry tenant MCP
    credentials): the run is over, so the servers' env (DSNs, passwords) is removed from the workspace's .mcp.json — the
    directory is kept for 72 h for resumes, and every run calls install() again before it starts. Returns the server names
    whose env was removed."""
    path = Path(workdir) / MCP_CONFIG_FILENAME
    if not path.exists():
        return []
    try:
        config = json.loads(path.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return []
    entries = config.get("mcpServers") if isinstance(config.get("mcpServers"), dict) else {}
    # G2 ⓪: an HTTP server's headers carry its token the same way a stdio server's env does
    removed = [name for name, entry in entries.items()
               if isinstance(entry, dict) and [entry.pop(k) for k in ("env", "headers") if entry.get(k)]]
    if removed:
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return removed


def select_servers(tenant_mcp: dict | None, tools: list[str] | None) -> tuple[dict | None, list[str]]:
    """A095 (process-gpt-base-agent executor: per-task MCP server selection): when the activity declares `tools`, only those
    tenant servers are registered for the run. Returns (filtered config, declared names that the tenant does not have —
    the designer's intent that cannot be met, logged by the caller). No declaration (None) = every tenant server, as before;
    an empty list (U2: the agent's servers and the activity's declaration do not overlap) = no server."""
    if tools is None:
        return tenant_mcp, []
    config = (tenant_mcp or {}).get("mcpServers")
    if not isinstance(config, dict):
        return tenant_mcp, list(tools)
    wanted = [str(t) for t in tools]
    chosen = {name: spec for name, spec in config.items() if name in wanted}
    missing = [t for t in wanted if t not in config]
    return dict(tenant_mcp, mcpServers=chosen), missing


def attach_secrets(tenant_mcp: dict | None, values: dict[str, str] | None, *, error: str | None = None) -> dict | None:
    """G2: a copy of tenant_mcp carrying the values of the secrets its servers name (only those) under SECRETS_KEY.
    error: the secret table could not be read — carried so a server left without its value says why."""
    config = (tenant_mcp or {}).get("mcpServers")
    if not isinstance(config, dict):
        return tenant_mcp
    wanted = {k for spec in config.values() for k in mcp_secrets.references(spec)}
    if not wanted:
        return tenant_mcp
    out = dict(tenant_mcp, **{SECRETS_KEY: {k: v for k, v in (values or {}).items() if k in wanted}})
    if error:
        out[SECRETS_ERROR_KEY] = error
    return out


def without_secrets(tenant_mcp: dict | None) -> dict | None:
    """The tenant config as anything but install() may see it (prompt extras, logs)."""
    if isinstance(tenant_mcp, dict) and any(k in tenant_mcp for k in _PRIVATE_KEYS):
        return {k: v for k, v in tenant_mcp.items() if k not in _PRIVATE_KEYS}
    return tenant_mcp


def _secret_values(tenant_mcp: dict | None) -> dict[str, str]:
    held = (tenant_mcp or {}).get(SECRETS_KEY) if isinstance(tenant_mcp, dict) else None
    return dict(held) if isinstance(held, dict) else {}


def _missing_reason(tenant_mcp: dict | None, missing: list[str], tail: str) -> str:
    """Why a server was left out: the secrets without a value, and the lookup failure when that is the cause."""
    error = tenant_mcp.get(SECRETS_ERROR_KEY) if isinstance(tenant_mcp, dict) else None
    why = "비밀 값 " + " · ".join(missing) + " 이(가) 없" + tail
    return f"{why} — 비밀 값 표를 읽지 못함: {error}" if error else why


def config_fingerprint(entry: dict) -> str:
    """B2: hash of one server entry without the HYD key — the same computation as procsvc/mcp_registry.fingerprint
    (tests compare the two), so a stamp from the portal's connection check matches only the config it checked."""
    body = {k: v for k, v in (entry or {}).items() if k != META_KEY}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


@dataclass
class Gate:
    config: dict | None
    read_tools: dict[str, list[str]] = field(default_factory=dict)      # gated server -> tools it may call
    blocked_tools: dict[str, list[str]] = field(default_factory=dict)   # gated server -> tools the check found not read-only
    dropped: dict[str, str] = field(default_factory=dict)               # server -> why it is not registered for this run


def gate_servers(tenant_mcp: dict | None, trusted: set[str] | list[str]) -> Gate:
    """B2 (DECISIONS 110 ①: an agent gets only tools of a server that passed the connection check, and only read-only ones).
    Servers the worker's allowed list names (`trusted` — the seed's three, with their own narrower entries) pass as before.
    Any other server (a student's — portal or wrap-up SQL) is registered only when its `hyd.gate` stamp was made for the
    config it has now; the run then pre-approves the stamp's read_tools and denies its blocked_tools. Without a matching
    stamp the server is left out and the reason is returned (the runner says it in the task's log)."""
    config = (tenant_mcp or {}).get("mcpServers")
    if not isinstance(config, dict):
        return Gate(config=tenant_mcp)
    kept: dict = {}
    out = Gate(config=None)
    values = _secret_values(tenant_mcp)
    for name, spec in config.items():
        if isinstance(spec, dict) and (spec.get(META_KEY) or {}).get("oauth_connection"):
            held = ((tenant_mcp or {}).get(RUNTIME_KEY) or {}).get(name) or {}
            if held.get("fingerprint") != config_fingerprint(spec) or not held.get("headers"):
                raise RuntimeError("로그인 연결의 실행 자격증명이 없습니다. 다시 연결을 확인하세요")
        missing = [k for k in mcp_secrets.references(spec) if not values.get(k)]
        if missing:                     # G2: never start a server with an empty token — say which secret is missing
            out.dropped[name] = _missing_reason(tenant_mcp, missing, "는 서버(포털 MCP 화면 '비밀 값'에 넣기)")
            continue
        if name in trusted or not isinstance(spec, dict):
            kept[name] = spec
            continue
        meta = spec.get(META_KEY) if isinstance(spec.get(META_KEY), dict) else {}
        stamp = meta.get("gate") if isinstance(meta.get("gate"), dict) else None
        if stamp is None:
            out.dropped[name] = "연결 검사를 통과하지 않은 서버"
        elif stamp.get("fingerprint") != config_fingerprint(spec):
            out.dropped[name] = "검사한 뒤 설정이 바뀐 서버(다시 연결 검사 필요)"
        elif not stamp.get("read_tools"):
            out.dropped[name] = "읽기 전용으로 표시한 도구가 없는 서버"
        else:
            kept[name] = spec
            out.read_tools[name] = [str(t) for t in stamp["read_tools"]]
            out.blocked_tools[name] = [str(t) for t in stamp.get("blocked_tools") or []]
    out.config = dict(tenant_mcp, mcpServers=kept)
    return out


def _resolved(tenant_mcp: dict | None) -> tuple[dict | None, dict[str, str]]:
    """G2: tenant_mcp with every server's ${SECRET:KEY} filled (SECRETS_KEY dropped); servers whose secret has no value are left out."""
    config = (tenant_mcp or {}).get("mcpServers")
    if not isinstance(config, dict):
        return without_secrets(tenant_mcp), {}
    values, kept, dropped = _secret_values(tenant_mcp), {}, {}
    for name, spec in config.items():
        filled, missing = mcp_secrets.resolve(spec, values)
        if missing:
            dropped[name] = _missing_reason(tenant_mcp, missing, "음")
        else:
            held = ((tenant_mcp or {}).get(RUNTIME_KEY) or {}).get(name) or {}
            if isinstance(spec, dict) and (spec.get(META_KEY) or {}).get("oauth_connection"):
                if held.get("fingerprint") != config_fingerprint(spec) or not held.get("headers"):
                    raise RuntimeError("로그인 연결의 실행 자격증명이 없습니다")
                filled = dict(filled, url=held["url"], headers=dict(held["headers"]))
            kept[name] = filled
    return dict(without_secrets(tenant_mcp), mcpServers=kept), dropped


def _headers(tenant_mcp: dict | None, name: str) -> dict[str, str]:
    """G2 ⓪: an HTTP server's headers as registered (already resolved by install)."""
    spec = ((tenant_mcp or {}).get("mcpServers") or {}).get(name) or {}
    headers = spec.get("headers") if isinstance(spec, dict) else None
    return {str(k): str(v) for k, v in headers.items()} if isinstance(headers, dict) else {}


def servers_of(tenant_mcp: dict | None, *, extra_env: dict[str, str] | None = None,
               host_rewrite: dict[str, str] | None = None) -> tuple[list[McpServer], dict[str, str]]:
    """Split a tenant MCP config into stdio servers (McpServer) and HTTP servers (name -> url).

    host_rewrite maps container host:port pairs to what this machine can reach (MCP_HOST_REWRITE): the classroom runs the
    worker on the host with the lecturer's own Claude Code login while the servers live in compose."""
    stdio: list[McpServer] = []
    http: dict[str, str] = {}
    config = (tenant_mcp or {}).get("mcpServers")
    if not isinstance(config, dict):
        return stdio, http
    rw = host_rewrite or {}
    for name, spec in config.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("command"):
            from hydcommon.neo4j_mcp import local_launch
            command, args = local_launch(str(spec['command']), list(spec.get('args') or []))
            env = {k: _rewrite(str(v), rw) for k, v in (spec.get("env") or {}).items()}
            env.update(extra_env or {})
            stdio.append(McpServer(name=str(name), command=command, args=[_rewrite(str(a), rw) for a in args], env=env))
        elif spec.get("url"):
            http[str(name)] = _rewrite(str(spec["url"]), rw)
    return stdio, http


def _http_type(tenant_mcp: dict | None, name: str) -> str:
    """B2: a server registered with the legacy SSE transport is written as Claude Code's `sse` type, others as `http`."""
    spec = ((tenant_mcp or {}).get("mcpServers") or {}).get(name) or {}
    return "sse" if str(spec.get("transport") or spec.get("type") or "").lower() == "sse" else "http"


def _rewrite(text: str, host_rewrite: dict[str, str]) -> str:
    for src, dst in host_rewrite.items():
        text = text.replace(src, dst)
    return text


def parse_host_rewrite(value: str | None) -> dict[str, str]:
    """'neo4j:7687=127.0.0.1:7687,enterprise-mcp:8199=127.0.0.1:8199' -> {src: dst}."""
    out: dict[str, str] = {}
    for pair in (value or "").split(","):
        if "=" in pair:
            src, dst = pair.split("=", 1)
            if src.strip() and dst.strip():
                out[src.strip()] = dst.strip()
    return out


_AUTH_SCHEMES = ("Bearer ", "Basic ", "Token ", "HydRuntime ")
#: a value kept under a secret-looking name (NEO4J_PASSWORD, Authorization …) written as is — shorter values ("none", "true")
#: are settings, not secrets, and hiding them would blank ordinary words in every event
_LITERAL_SECRET_MIN = 8


def _written_secrets(original: dict | None, resolved: dict | None, stdio: list[McpServer], http: dict[str, str]) -> list[str]:
    """W2 (2026-10-23 검수): every secret this run writes in clear into the workspace config (.mcp.json) —
    the values filled from ${SECRET:KEY} (and the header/env values they were filled into) and the literal values under a
    secret-looking header or env name (a stdio server's NEO4J_PASSWORD). The agent can Read its workspace, so these join
    the redaction list: trace, events rows, stored tool outputs and CLI errors must not carry them."""
    from procsvc.mcp_check import is_secret_key
    values, out = _secret_values(original), []
    kept = ((resolved or {}).get("mcpServers") or {})
    for name, spec in (((original or {}).get("mcpServers") or {}) if isinstance(original, dict) else {}).items():
        if name not in kept or not isinstance(spec, dict):
            continue
        out += [str(values[k]) for k in mcp_secrets.references(spec) if values.get(k)]
        for fld in mcp_secrets.FIELDS:
            block, filled = spec.get(fld), (kept[name] or {}).get(fld) if isinstance(kept[name], dict) else None
            if isinstance(block, dict) and isinstance(filled, dict):
                out += [str(filled[k]) for k, v in block.items() if isinstance(v, str) and "${SECRET:" in v and filled.get(k)]
    literal = [(k, v) for s in stdio for k, v in s.env.items()] + [(k, v) for name in http for k, v in _headers(resolved, name).items()]
    out += [str(v) for k, v in literal if is_secret_key(k) and len(str(v)) >= _LITERAL_SECRET_MIN and "${SECRET:" not in str(v)]
    return out


#: 이번 실행의 process_scope 를 헤더로 받는 HYD 판단 서버(dmn-mcp run_scope). 학생 · 외부 서버에는 싣지 않는다.
RUN_SCOPE_SERVERS = ("hyd-dmn",)


def install(workdir: Path, tenant_mcp: dict | None, *, extra_env: dict[str, str] | None = None,
            host_rewrite: dict[str, str] | None = None, run_headers: dict[str, str] | None = None) -> BridgeResult:
    """Register the tenant's servers for one run in `workdir` (idempotent: rewrites the same entries). A gated server's
    read-only tools reach Claude Code through --allowedTools / --disallowedTools in the runner."""
    private = ((tenant_mcp or {}).get(RUNTIME_KEY) or {}).values()
    redaction_values = [value for held in private for value in (held.get("headers") or {}).values()]
    original = tenant_mcp
    tenant_mcp, dropped = _resolved(tenant_mcp)
    stdio, http = servers_of(tenant_mcp, extra_env=extra_env, host_rewrite=host_rewrite)
    redaction_values += _written_secrets(original, tenant_mcp, stdio, http)
    # 2026-10-25: 이번 실행의 process_scope 를 모델이 옮겨 적지 않게 판단 서버 연결에 헤더로 싣는다(UUID 오기 409)
    headers_of = lambda name: dict(_headers(tenant_mcp, name), **((run_headers or {}) if name in RUN_SCOPE_SERVERS else {}))   # noqa: E731
    redaction_values += [value.removeprefix(scheme) for value in redaction_values for scheme in _AUTH_SCHEMES if value.startswith(scheme)]
    redaction_values = list(dict.fromkeys(redaction_values))
    path = workdir / MCP_CONFIG_FILENAME
    # A resumed workspace may have had a different capability selection. Rebuild
    # the entire run-local registry instead of retaining previously allowed tools.
    config: dict = {}
    entries: dict = {}
    for s in stdio:
        entry: dict = {"command": s.command, "args": list(s.args)}
        if s.env:
            entry["env"] = dict(s.env)
        entries[s.name] = entry
    for name, url in http.items():
        entries[name] = {"type": _http_type(tenant_mcp, name), "url": url}
        headers = headers_of(name)
        if headers:                     # G2 ⓪: was dropped — a token-protected server failed only for the agent
            entries[name]["headers"] = headers
    for name in dropped:
        entries.pop(name, None)         # an earlier run's entry for a server this run cannot start
    config["mcpServers"] = entries
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return BridgeResult(servers=list(entries), config_path=str(path), env=runtime_env(workdir),
                        dropped=dropped, redaction_values=redaction_values, extra_args=["--mcp-config", str(path), "--strict-mcp-config"])


def runtime_env(workdir: Path) -> dict[str, str]:
    """Per-run config home for Claude Code (the product's RuntimeLease). The CLI authenticates only with this run's gateway token
    (course_access.permit), never with a personal login, so no shared config dir is ever needed."""
    home = workdir / CONFIG_HOME_DIRNAME / "claude-code"
    home.mkdir(parents=True, exist_ok=True)
    return {"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "CLAUDE_CONFIG_DIR": str(home)}
