# hyd-dmn MCP: the agent service's deterministic engine (agentsvc) served as MCP tools. Same templates, same env as `agent`.
FROM python:3.12-slim
WORKDIR /srv
COPY it/dmn-mcp/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/neo4j/templates /srv/templates
COPY it/agent/agentsvc /srv/agentsvc
COPY it/dmn-mcp/dmn_mcp /srv/dmn_mcp
ENV PYTHONUNBUFFERED=1 KG_TEMPLATES=/srv/templates
EXPOSE 8198
CMD ["python", "-m", "dmn_mcp.server"]
