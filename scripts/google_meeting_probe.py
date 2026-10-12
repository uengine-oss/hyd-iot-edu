"""Local real HTTP/MCP negative probe. Never uses an existing Google token.

The OAuth file is deliberately missing in a temporary directory. No external
account calls, no portal registration, no successful-account claims.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]


async def probe(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hyd-google-noauth-") as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env["GOOGLE_MEETING_TOKEN_FILE"] = str(Path(temp) / "missing-token.json")
        env["PYTHONUTF8"] = "1"
        env.pop("HYD_GOOGLE_MCP_KEY", None)
        command = [sys.executable, str(ROOT / "students/_template/google_meeting_mcp/server.py"), "--port", str(port)]
        with (output / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            try:
                health = None
                async with httpx.AsyncClient() as http:
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError("Local MCP exited before health check")
                        try:
                            health = await http.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
                            break
                        except httpx.TransportError:
                            await asyncio.sleep(0.1)
                if health is None:
                    raise RuntimeError("Local MCP did not start")
                checks = {"health_without_google_auth_is_503": health.status_code == 503 and health.json().get("ok") is False}
                records = {"health": {"http_status": health.status_code, "body": health.json()}}
                async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                    tools = await client.list_tools()
                    (output / "tools.json").write_text(json.dumps([tool.model_dump(mode="json") for tool in tools], ensure_ascii=False, indent=2), encoding="utf-8")
                    checks["actual_http_mcp_has_five_contracts"] = {t.name for t in tools} == {"search_files", "read_file", "free_busy", "get_event", "create_event"}
                    checks["write_is_not_read_only"] = next(t for t in tools if t.name == "create_event").annotations.readOnlyHint is False
                    read = await client.call_tool("search_files", {"text": "회의"}, raise_on_error=False)
                    read_body = json.loads(read.content[0].text)
                    records["unauthenticated_read"] = {"is_error": read.is_error, "body": read_body}
                    checks["mcp_noauth_is_error503"] = read.is_error and read_body.get("status") == 503 and read_body.get("error_kind") == "AUTH_REQUIRED"
                    arguments = {"calendar_id": "primary", "idempotency_key": "no-auth-probe", "summary": "읽기 전용 검사",
                                 "start": "2026-10-20T14:00:00+09:00", "end": "2026-10-20T15:00:00+09:00", "time_zone": "Asia/Seoul",
                                 "room_email": "room@resource.calendar.google.com", "attendees": [{"email": "participant@company.co.kr", "required": True}]}
                    blocked = await client.call_tool("create_event", arguments, raise_on_error=False)
                    blocked_body = json.loads(blocked.content[0].text)
                    records["disabled_write"] = {"is_error": blocked.is_error, "body": blocked_body}
                    checks["default_write_is_error403"] = blocked.is_error and blocked_body.get("status") == 403
                    arguments["attendees"] *= 2
                    duplicate = await client.call_tool("create_event", arguments, raise_on_error=False)
                    duplicate_body = json.loads(duplicate.content[0].text)
                    records["duplicate_input"] = {"is_error": duplicate.is_error, "body": duplicate_body}
                    checks["duplicate_input_is_error422"] = duplicate.is_error and duplicate_body.get("status") == 422
                cli = subprocess.run([sys.executable, str(ROOT / "scripts/google_meeting_auth.py"), "status"],
                                     env=env, capture_output=True, text=True, encoding="utf-8", timeout=10)
                cli_body = json.loads(cli.stdout)
                records["oauth_status"] = {"exit_code": cli.returncode, "body": cli_body}
                checks["oauth_status_is_incomplete_exit2"] = cli.returncode == 2 and cli_body.get("credential_configured") is False
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            checks["owned_server_stopped"] = process.poll() is not None
            result = {"checks": checks, "passed": all(checks.values()), "records": records,
                      "actual_google_authentication": False, "actual_google_read": False,
                      "actual_external_writes": 0, "used_existing_credential": False}
            (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"passed": result["passed"], "checks": checks, "actual_google_authentication": False, "actual_external_writes": 0}))
            return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return asyncio.run(probe(parser.parse_args().output.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
