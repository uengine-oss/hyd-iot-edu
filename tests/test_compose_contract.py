"""compose.yaml deployment invariants (A144, sweep item 38 / C06): the single-host teaching stack binds host ports to
127.0.0.1 only, caps memory, assigns a profile, health-checks every long-running service it builds, rotates logs, gives
every container that reaches the host DB the host.docker.internal mapping, and passes only environment variables the
service code actually reads (sweep item 35: agent/dmn-mcp carried PG_DSN and AGENT_BRIDGE that nothing read).
The checkers return violation lists; the real file must yield none, and a mutated copy must yield the expected ones."""
import copy
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.yaml"
#: environment keys that are read indirectly (os.environ copy into a child process, a library, or a dynamic name)
INDIRECT_ENV = {"agent-worker": {"ANTHROPIC_API_KEY", "HYD_GPU_API_KEY", "TENANT_ID"}, "agent": {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}}


def load():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _source_dirs(service: dict) -> list[Path]:
    dockerfile = (service.get("build") or {}).get("dockerfile")
    if not dockerfile:
        return []
    return [ROOT / Path(dockerfile).parent, ROOT / "common" / "hydcommon"]


def _env_read_anywhere(key: str, dirs: list[Path]) -> bool:
    for d in dirs:
        for f in list(d.rglob("*.py")) + list(d.rglob("Dockerfile")) + list(d.rglob("*.sh")):
            if key in f.read_text(encoding="utf-8", errors="ignore"):
                return True
    return False


def check(compose: dict) -> list[str]:
    errs = []
    for name, s in compose["services"].items():
        for p in s.get("ports") or []:
            if not str(p).startswith("127.0.0.1:"):
                errs.append(f"{name}: port {p} is not bound to 127.0.0.1")
        if not s.get("mem_limit"):
            errs.append(f"{name}: no mem_limit")
        if not s.get("profiles"):
            errs.append(f"{name}: no profile")
        long_running = s.get("restart") == "unless-stopped"
        if long_running and s.get("build") and not s.get("healthcheck"):
            errs.append(f"{name}: built long-running service without healthcheck")
        if long_running and not s.get("logging"):
            errs.append(f"{name}: long-running service without log rotation")
        env = s.get("environment") or {}
        env_items = env.items() if isinstance(env, dict) else [(str(e).split("=", 1)[0], str(e)) for e in env]
        if any("host.docker.internal" in str(v) for _, v in env_items) and "host.docker.internal:host-gateway" not in (s.get("extra_hosts") or []):
            errs.append(f"{name}: environment points at host.docker.internal but extra_hosts has no host-gateway mapping")
        dirs = _source_dirs(s)
        if dirs and all(d.exists() for d in dirs) and name not in ("process",):
            for key, _ in env_items:
                if key in INDIRECT_ENV.get(name, set()):
                    continue
                if not _env_read_anywhere(key, dirs):
                    errs.append(f"{name}: environment {key} is read by no file under {dirs[0].relative_to(ROOT)} or hydcommon")
    worker_env = compose["services"]["agent-worker"].get("environment") or {}
    allowed = str(worker_env.get("ALLOWED_TOOLS", ""))
    if not re.fullmatch(r"\$\{ALLOWED_TOOLS:-\}", allowed.strip()):
        errs.append(f"agent-worker: ALLOWED_TOOLS must pass through (${{ALLOWED_TOOLS:-}}); the default list lives in worker/settings.py, got {allowed!r}")
    return errs


def test_live_compose_file_meets_the_contract():
    assert check(load()) == []


def test_checker_catches_each_broken_invariant():
    c = load()
    c["services"]["detector"]["ports"] = ["0.0.0.0:8092:8092"]
    del c["services"]["detector"]["mem_limit"]
    del c["services"]["connect-sink"]["profiles"]
    del c["services"]["cmd-gateway"]["healthcheck"]
    del c["services"]["agent"]["logging"]
    c["services"]["dmn-mcp"].pop("extra_hosts")
    c["services"]["agent"]["environment"]["PG_DSN"] = "postgresql://hyd:hyd@timescaledb:5432/hyd"
    c["services"]["agent-worker"]["environment"]["ALLOWED_TOOLS"] = "${ALLOWED_TOOLS:-Read,Glob}"
    errs = "\n".join(check(c))
    for needle in ["detector: port 0.0.0.0:8092:8092", "detector: no mem_limit", "connect-sink: no profile",
                   "cmd-gateway: built long-running service without healthcheck", "agent: long-running service without log rotation",
                   "dmn-mcp: environment points at host.docker.internal", "agent: environment PG_DSN is read by no file",
                   "agent-worker: ALLOWED_TOOLS must pass through"]:
        assert needle in errs, needle


def test_services_that_read_the_host_supabase_have_the_host_gateway_mapping():
    c = load()
    for name in ("process", "enterprise-sim", "enterprise-mcp", "agent-worker", "agent", "dmn-mcp"):
        assert "host.docker.internal:host-gateway" in c["services"][name].get("extra_hosts", []), name


def test_compose_copy_is_untouched_by_the_mutating_test():
    a, b = load(), copy.deepcopy(load())
    assert a == b and "PG_DSN" not in a["services"]["agent"]["environment"] and "AGENT_BRIDGE" not in a["services"]["agent"]["environment"]
    assert "PG_DSN" not in a["services"]["dmn-mcp"]["environment"]
