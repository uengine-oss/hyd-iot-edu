FROM python:3.12-slim
WORKDIR /srv
COPY it/agent/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/neo4j/templates /srv/templates
COPY it/agent/agentsvc /srv/agentsvc
ENV PYTHONUNBUFFERED=1 KG_TEMPLATES=/srv/templates
EXPOSE 8091
CMD ["uvicorn", "agentsvc.main:app", "--host", "0.0.0.0", "--port", "8091"]
