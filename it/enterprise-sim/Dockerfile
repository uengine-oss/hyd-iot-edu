FROM python:3.12-slim
WORKDIR /srv
COPY it/enterprise-sim/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/enterprise-sim/entsim /srv/entsim
ENV PYTHONUNBUFFERED=1
EXPOSE 8095
CMD ["uvicorn", "entsim.main:app", "--host", "0.0.0.0", "--port", "8095"]
