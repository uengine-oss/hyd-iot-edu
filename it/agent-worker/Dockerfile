# agent-worker: Claude Code (npm) + uv (for the Neo4j MCP) + the worker. The CLI authenticates with ANTHROPIC_API_KEY.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y --no-install-recommends nodejs \
 && node -e "const [a,b,c]=process.versions.node.split('.').map(Number); if(a!==22 || b<23 || (b===23 && c<4)) throw Error('Node.js 22.23.4 or newer 22.x security release required')" \
 && npm install -g @anthropic-ai/claude-code@2.1.310 \
 && pip install --no-cache-dir uv \
 && apt-get purge -y --auto-remove && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY it/agent-worker/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
# the whole package (the worker imports procdb · task_deferral · agents_store · mcp_secrets · mcp_check · result_correction …, and
# procdb pulls the stores it is built from). A hand-picked file list drifted and the container worker died on start
# (2026-10-25: procdb → approval_store missing); tests/test_worker_image_contract.py guards the import closure.
COPY it/process/procsvc /srv/procsvc
COPY it/neo4j/v2/schema_prompt.md /srv/ontology/schema_prompt.md
COPY it/agent-worker/worker /srv/worker
ENV PYTHONUNBUFFERED=1 WORKSPACE_ROOT=/workspace SCHEMA_PROMPT=/srv/ontology/schema_prompt.md
VOLUME ["/workspace"]
EXPOSE 8097
CMD ["python", "-m", "worker.main"]
