import concurrent.futures, datetime, json, pathlib, urllib.request

OUT = pathlib.Path(__file__).with_name('registered-capabilities.json')
NAMES = ['neo4j', 'hyd-dmn', 'enterprise', 'enterprise-maint', 'enterprise-purchase']
def inspect(name):
    row = {'server': name, 'method': 'GET tool catalog only'}
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/mcp/servers/' + name + '/tools?timeout=5', timeout=20) as response:
            payload = json.load(response)
            row['http_status'] = response.status
        tools = payload.get('tools', []) if isinstance(payload, dict) else []
        row['response_field_names'] = sorted(payload) if isinstance(payload, dict) else []
        row['tools'] = [{'name': t.get('name'), 'readOnlyHint': t.get('annotations', {}).get('readOnlyHint'), 'required_input_fields': t.get('inputSchema', {}).get('required', [])} for t in tools if isinstance(t, dict)]
        row['tool_count'] = len(row['tools'])
    except Exception as exc:
        row['error_type'] = type(exc).__name__
        row['http_status'] = getattr(exc, 'code', None)
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    rows = list(pool.map(inspect, NAMES))
OUT.write_text(json.dumps({'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'catalogs': rows, 'tools_call_count': 0, 'registration_writes': 0, 'credential_contents_read': False}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'output': str(OUT), 'results': [{'server': r['server'], 'http_status': r.get('http_status'), 'tool_count': r.get('tool_count'), 'error_type': r.get('error_type')} for r in rows]}))
