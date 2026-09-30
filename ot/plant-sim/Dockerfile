FROM python:3.12-slim
WORKDIR /srv
COPY ot/plant-sim/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY ot/plant-sim/plantsim /srv/plantsim
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "plantsim.main:app", "--host", "0.0.0.0", "--port", "8000"]
