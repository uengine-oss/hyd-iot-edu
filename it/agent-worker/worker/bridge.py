"""Registering the tenant's MCP tools (process-gpt-cli-agent/core/bridge.py).

Tools reach a CLI agent as MCP servers registered per run. The servers come from `tenants.mcp` in the product's own
shape — `mcpServers: {name: {command, args, env}}` for stdio servers, `{type: "url", url, transport}` for streamable-HTTP
servers (the shape process-gpt-sample-app-wms documents). Claude Code reads a project-scoped `.mcp.json`, so one run's
tools stay in one run's workspace; HTTP servers are written in Claude Code's native `{type: "http", url}` form.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from cliagents import McpServer

MCP_CONFIG_FILENAME = ".mcp.json"
CONFIG_HOME_DIRNAME = ".agent-home"
#: B2: the HYD-only key of a tenants.mcp entry (origin · connection-check stamp). Never written to .mcp.json / codex config.
META_KEY = "hyd"


@dataclass
class BridgeResult:
    servers: list[str] = field(default_factory=list)
    config_path: str | None = None
    env: dict[str, str] = field(default_factory=dict)       # environment the run must inherit (config-dir isolation)
    extra_args: list[str] = field(default_factory=list)


def cleanup(workdir: Path) -> list[str]:
    """A096 (process-gpt-cli-agent RuntimeLease: provider files are restored after the run because they carry tenant MCP
    credentials): the run is over, so the servers' env (DSNs, passwords) is removed from the workspace's .mcp.json — the
    directory is kept for 72 h for resumes, and every run calls install() again before it starts. Returns the server names
    whose env was removed."""
    # A114 (A113 r14 A4): the Codex path wrote the same server env (DSNs, the Neo4j password) into codex-mcp.toml — a copy
    # of what is passed with -c — and left it in the 72 h workspace. install() rewrites it before every run, so it goes.
    codex_copy = Path(workdir) / "codex-mcp.toml"
    if codex_copy.exists():
        codex_copy.unlink()
    path = Path(workdir) / MCP_CONFIG_FILENAME
    if not path.exists():
        return []
    try:
        config = json.loads(path.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return []
    entries = config.get("mcpServers") if isinstance(config.get("mcpServers"), dict) else {}
    removed = [name for name, entry in entries.items() if isinstance(entry, dict) and entry.pop("env", None)]
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
    for name, spec in config.items():
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
            env = {k: _rewrite(str(v), rw) for k, v in (spec.get("env") or {}).items()}
            env.update(extra_env or {})
            stdio.append(McpServer(name=str(name), command=str(spec["command"]), args=[_rewrite(str(a), rw) for a in (spec.get("args") or [])], env=env))
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


def install(workdir: Path, tenant_mcp: dict | None, *, provider_id: str = "claude-code", isolate_config_dir: bool = False,
            extra_env: dict[str, str] | None = None, host_rewrite: dict[str, str] | None = None,
            read_tools: dict[str, list[str]] | None = None) -> BridgeResult:
    """Register the tenant's servers for one run in `workdir` (idempotent: rewrites the same entries).
    read_tools (B2, from gate_servers): a gated server's read-only tools — Codex enables only those (Claude Code gets them
    through --allowedTools / --disallowedTools in the runner)."""
    stdio, http = servers_of(tenant_mcp, extra_env=extra_env, host_rewrite=host_rewrite)
    if provider_id == "codex":
        # cliagents' installed McpServer/install_bridge only supports stdio.
        # Native per-invocation overrides support both transports and keep the
        # user's config, login and session store intact. Never register tenant
        # servers globally: another tenant could overwrite them during a run.
        entries = {s.name: {"command": s.command, "args": s.args, "env": s.env} for s in stdio}
        entries.update({name: {"url": url} for name, url in http.items()})
        for name, entry in entries.items():
            entry.update(required=True, startup_timeout_sec=60, default_tools_approval_mode="approve")
            if name == "neo4j":
                entry["enabled_tools"] = ["get_neo4j_schema", "read_neo4j_cypher"]
            elif name in (read_tools or {}):
                entry["enabled_tools"] = list(read_tools[name])
        path = workdir / "codex-mcp.toml"
        config = "mcp_servers=" + _inline_toml(entries)
        path.write_text(config + "\n", encoding="utf-8")
        return BridgeResult(servers=list(entries), config_path=str(path),
                            extra_args=["--ignore-user-config", "--disable", "apps",
                                        "-c", "project_doc_max_bytes=0", "-c", config])
    path = workdir / MCP_CONFIG_FILENAME
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            config = {}
    entries = config.get("mcpServers") if isinstance(config.get("mcpServers"), dict) else {}
    for s in stdio:
        entry: dict = {"command": s.command, "args": list(s.args)}
        if s.env:
            entry["env"] = dict(s.env)
        entries[s.name] = entry
    for name, url in http.items():
        entries[name] = {"type": _http_type(tenant_mcp, name), "url": url}
    config["mcpServers"] = entries
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return BridgeResult(servers=list(entries), config_path=str(path), env=runtime_env(workdir, provider_id, isolate_config_dir))


def _inline_toml(value) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(str(k)) + "=" + _inline_toml(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_inline_toml(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def runtime_env(workdir: Path, provider_id: str, isolate_config_dir: bool) -> dict[str, str]:
    """Per-run config home for Claude Code (the product's RuntimeLease) — only when an API key authenticates the CLI;
    a subscription login lives in the shared config dir and would be lost (docs/handoff/DECISIONS.md 12)."""
    if provider_id != "claude-code" or not isolate_config_dir:
        return {}
    home = workdir / CONFIG_HOME_DIRNAME / provider_id
    home.mkdir(parents=True, exist_ok=True)
    return {"CLAUDE_CONFIG_DIR": str(home)}
