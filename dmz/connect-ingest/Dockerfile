FROM python:3.12-slim
WORKDIR /srv
COPY dmz/connect-ingest/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY dmz/connect-ingest/app /srv/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8093
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8093"]
