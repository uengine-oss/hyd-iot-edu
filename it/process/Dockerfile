FROM python:3.12-slim
WORKDIR /srv
COPY it/process/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/process/procsvc /srv/procsvc
COPY it/process/definitions /srv/definitions
ENV PYTHONUNBUFFERED=1 PROCESS_DEFINITIONS=/srv/definitions
EXPOSE 8080
CMD ["uvicorn", "procsvc.main:app", "--host", "0.0.0.0", "--port", "8080"]
