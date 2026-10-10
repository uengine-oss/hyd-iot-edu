FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY engine.py server.py decision_table.json /srv/
ENV PYTHONUNBUFFERED=1
EXPOSE 18198
CMD ["python", "server.py"]
