"""Narrow, idempotent tenant MCP dependency migration; preserves other settings."""
import json
import psycopg
from pathlib import Path

with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres") as conn:
    row = conn.execute("select mcp from tenants where id = %s for update", ("hyd",)).fetchone()
    config = row[0]
    if isinstance(config, str):
        config = json.loads(config)
    server = config["mcpServers"]["neo4j"]
    args = server["args"]
    if server['command'] == 'uvx' and args in (["mcp-neo4j-cypher@0.4.1", "--transport", "stdio"],
            ["--with", "fastmcp==2.13.0.2", "mcp-neo4j-cypher@0.4.1", "--transport", "stdio"]):
        migration = Path(__file__).resolve().parents[1] / 'it/supabase/migrations/20261026000063_bounded_neo4j_mcp.sql'
        conn.execute(migration.read_text(encoding='utf-8'))
        print("Updated known Neo4j adapter; other tenant MCP fields preserved")
    elif server['command'] == 'python' and args == ['-m', 'hydcommon.neo4j_mcp']:
        print("Already using the bounded adapter")
    else:
        raise RuntimeError("Unrecognized neo4j args; no changes applied")
