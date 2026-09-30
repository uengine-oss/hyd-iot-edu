FROM python:3.12-slim
WORKDIR /srv
COPY dmz/cmd-gateway/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY dmz/cmd-gateway/gw /srv/gw
ENV PYTHONUNBUFFERED=1
EXPOSE 8090
CMD ["uvicorn", "gw.main:app", "--host", "0.0.0.0", "--port", "8090"]
