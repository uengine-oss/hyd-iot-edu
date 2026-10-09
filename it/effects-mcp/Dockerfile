FROM python:3.12-slim
WORKDIR /srv
COPY it/effects-mcp/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY it/effects-mcp/effects_mcp /srv/effects_mcp
ENV PYTHONUNBUFFERED=1
EXPOSE 8197
CMD ["python", "-m", "effects_mcp.server"]
