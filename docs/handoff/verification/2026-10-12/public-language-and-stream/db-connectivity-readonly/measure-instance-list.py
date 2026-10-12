import datetime,json,pathlib,time,urllib.request
start=time.monotonic()
result={'method':'One GET; body not persisted','url':'http://127.0.0.1:8080/api/instances?limit=50','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
    with urllib.request.urlopen(result['url'],timeout=30) as response:
        body=response.read()
        rows=json.loads(body)
        result.update(status=response.status,bytes=len(body),row_count=len(rows),max_row_json_bytes=max((len(json.dumps(row,ensure_ascii=False).encode()) for row in rows),default=0))
except Exception as exc:
    result.update(error_type=type(exc).__name__)
result['elapsed_seconds']=time.monotonic()-start
pathlib.Path(__file__).with_name('instance-list-timing.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
