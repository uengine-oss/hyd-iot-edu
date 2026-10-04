"""Actual Codex MCP connection + same-session resume, using the tenant bridge.

Writes JSONL evidence, no business write tools are requested.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ("it/agent-worker", "it/process", "common")]

from cliagents import ExecRequest, Permission, run_exec
from procsvc.procdb import PgRepo
from worker import bridge
from worker.runner import _resolve_provider


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".evidence/reaudit/codex-probe")
    args = ap.parse_args()
    dest = ROOT / args.out
    dest.mkdir(parents=True, exist_ok=False)
    config = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    before = hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None
    tenant = PgRepo("postgresql://postgres:postgres@127.0.0.1:54322/postgres").get_tenant("hyd")
    bridged = bridge.install(dest, tenant["mcp"], provider_id="codex", host_rewrite=bridge.parse_host_rewrite(
        "neo4j:7687=127.0.0.1:7687,enterprise-mcp:8199=127.0.0.1:8199,dmn-mcp:8198=127.0.0.1:8198"))
    provider = _resolve_provider("codex")
    session = None
    failures = []
    successful_tools = set()
    prompts = [
        "Call neo4j get_neo4j_schema and report the actual number of labels. Call enterprise describe_schema and hyd-dmn inputs. Do not use shell, do not write. Return brief JSON with counts from actual results only.",
        "Without calling tools, repeat the label count you just observed and say this is a resumed session. Return brief JSON.",
    ]
    with (dest / "events.jsonl").open("w", encoding="utf-8") as log:
        for index, prompt in enumerate(prompts):
            request = ExecRequest(prompt=prompt, workdir=str(dest), permission=Permission.READ_ONLY,
                                  resume_session=session, extra_args=bridged.extra_args)
            def record(event):
                log.write(json.dumps({"phase": index, "kind": event.kind.value, "session_id": event.session_id,
                                      "tool": event.tool, "text": event.text, "error": event.is_error,
                                      "raw": event.raw}, ensure_ascii=False, default=str) + "\n")
                log.flush()
                item = event.raw.get("item") or {}
                if item.get("type") == "mcp_tool_call" and event.kind.value == "tool_end":
                    if item.get("status") == "failed" or item.get("error"):
                        failures.append(item)
                    else:
                        successful_tools.add(item.get("server"))
            result = run_exec(provider, request, env=bridged.env or None, on_event=record)
            (dest / f"stderr-{index}.log").write_text(result.stderr, encoding="utf-8")
            if not result.ok:
                raise RuntimeError(f"CLI exit={result.returncode}: {result.stderr[-3000:]}")
            session = result.session_id or session
            if not session:
                raise RuntimeError("No session id observed")
    after = hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None
    summary = {"session_id": session, "user_config_unchanged": before == after, "config_sha256": after,
               "successful_mcp_servers": sorted(successful_tools), "failed_tools": len(failures)}
    (dest / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    if failures or successful_tools != {"neo4j", "enterprise", "hyd-dmn"}:
        raise RuntimeError("MCP tool verification failed; see raw events")


if __name__ == "__main__":
    main()
