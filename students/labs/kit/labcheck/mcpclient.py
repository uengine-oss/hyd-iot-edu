"""프로젝트의 .mcp.json 에 적힌 MCP 서버에 실제로 붙어 도구를 불러 보는 확인용 클라이언트."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from labkit.settings import project_dir, setting

PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")
MCP_TIMEOUT_SECONDS = 120


def mcp_config_path():
    return project_dir() / ".mcp.json"


def literal_values(server: dict) -> dict[str, str]:
    """서버 설정에서 ${이름} 자리표시자가 아닌 채로 적힌 env 값."""
    return {key: value for key, value in (server.get("env") or {}).items() if not PLACEHOLDER.fullmatch(str(value))}


def expand(value: Any) -> Any:
    """${이름} 을 .env 의 값으로 바꾼다(Claude Code 가 하는 일과 같다)."""
    if isinstance(value, str):
        return PLACEHOLDER.sub(lambda match: setting(match.group(1)), value)
    if isinstance(value, dict):
        return {key: expand(child) for key, child in value.items()}
    if isinstance(value, list):
        return [expand(child) for child in value]
    return value


def parse_result(result) -> Any:
    if result.structured_content is not None:
        content = result.structured_content
        return content.get("result", content) if set(content) == {"result"} else content
    text = "".join(block.text for block in result.content if getattr(block, "text", None))
    return json.loads(text)


async def _session(server: dict, calls: list[tuple[str, dict]]) -> dict:
    from fastmcp import Client  # 6일차 확인에서만 필요하다. 다른 날 확인이 이 패키지 없이도 돌게 여기서 불러온다.

    async with Client({"mcpServers": {"server": expand(server)}}, timeout=MCP_TIMEOUT_SECONDS) as client:
        tools = sorted(tool.name for tool in await client.list_tools())
        results = [parse_result(await client.call_tool(name, arguments)) for name, arguments in calls]
    return {"tools": tools, "results": results}


def use_server(server: dict, calls: list[tuple[str, dict]] | None = None) -> dict:
    """서버에 붙어 도구 목록을 읽고, calls 의 도구를 차례로 불러 결과를 돌려준다."""
    return asyncio.run(_session(server, calls or []))
