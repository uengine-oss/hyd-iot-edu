# agent-worker: Claude Code (npm) + uv (for the Neo4j MCP) + the worker. The CLI authenticates with ANTHROPIC_API_KEY.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @anthropic-ai/claude-code \
 && pip install --no-cache-dir uv \
 && apt-get purge -y --auto-remove && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY it/agent-worker/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/process/procsvc/procdb.py /srv/procsvc/procdb.py
COPY it/process/procsvc/task_deferral.py /srv/procsvc/task_deferral.py
RUN touch /srv/procsvc/__init__.py
COPY it/neo4j/v2/schema_prompt.md /srv/ontology/schema_prompt.md
COPY it/agent-worker/worker /srv/worker
ENV PYTHONUNBUFFERED=1 WORKSPACE_ROOT=/workspace SCHEMA_PROMPT=/srv/ontology/schema_prompt.md
VOLUME ["/workspace"]
EXPOSE 8097
CMD ["python", "-m", "worker.main"]
