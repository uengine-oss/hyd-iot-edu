"""Narrow, idempotent tenant MCP dependency migration; preserves other settings."""
import json
import psycopg

with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres") as conn:
    row = conn.execute("select mcp from tenants where id = %s for update", ("hyd",)).fetchone()
    config = row[0]
    if isinstance(config, str):
        config = json.loads(config)
    server = config["mcpServers"]["neo4j"]
    args = server["args"]
    if args == ["mcp-neo4j-cypher@0.4.1", "--transport", "stdio"]:
        args[:0] = ["--with", "fastmcp==2.13.0.2"]
        from psycopg.types.json import Jsonb
        conn.execute("update tenants set mcp = %s where id = %s", (Jsonb(config), "hyd"))
        print("Updated only neo4j args; other tenant MCP fields preserved")
    elif args[:2] == ["--with", "fastmcp==2.13.0.2"]:
        print("Already pinned")
    else:
        raise RuntimeError("Unrecognized neo4j args; no changes applied")
