# Host subscription login; no API key or user config edits.
param([string]$Provider = 'codex')
$ErrorActionPreference = 'Continue'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = 'it/agent-worker;it/process;common'
$env:SUPABASE_DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'
$env:MCP_HOST_REWRITE = 'neo4j:7687=127.0.0.1:7687,enterprise-mcp:8199=127.0.0.1:8199,dmn-mcp:8198=127.0.0.1:8198'
$env:CLIAGENTS_WORKSPACE_ROOT = Join-Path (Get-Location) '.evidence/workspace'
$env:SCHEMA_PROMPT = Join-Path (Get-Location) 'it/neo4j/v2/schema_prompt.md'
$env:CONSUMER_ID = "agent-worker:$Provider-host"
$env:CLIAGENTS_DEFAULT_CLI = $Provider
$env:CLIAGENTS_DEFAULT_PERMISSION = 'read_only'
$env:HEALTH_PORT = '8097'
& .venv314/Scripts/python.exe -m worker.main
exit $LASTEXITCODE
