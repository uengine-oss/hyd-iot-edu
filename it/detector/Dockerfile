FROM python:3.12-slim
WORKDIR /srv
COPY it/detector/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/detector/det /srv/det
ENV PYTHONUNBUFFERED=1
EXPOSE 8092
CMD ["uvicorn", "det.main:app", "--host", "0.0.0.0", "--port", "8092"]
