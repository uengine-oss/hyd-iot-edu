FROM python:3.12-slim
WORKDIR /srv
COPY it/enterprise-mcp/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY it/enterprise-mcp/enterprise_mcp /srv/enterprise_mcp
COPY common/hydcommon /srv/hydcommon
ENV PYTHONUNBUFFERED=1
EXPOSE 8199
CMD ["python", "-m", "enterprise_mcp.server"]
