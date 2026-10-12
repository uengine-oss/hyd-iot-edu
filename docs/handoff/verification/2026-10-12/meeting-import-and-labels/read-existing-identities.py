import datetime, json, pathlib, urllib.request
OUT = pathlib.Path(__file__).parent
results = {}
for path in ['/api/agents', '/api/flows/catalog', '/api/mcp/servers']:
    with urllib.request.urlopen('http://127.0.0.1:8080' + path, timeout=20) as response:
        data = json.loads(response.read().decode('utf-8'))
    if path == '/api/agents':
        results['agents'] = [{k: r.get(k) for k in ['id','name','kind','tools','skills']} for r in data]
    elif path == '/api/flows/catalog':
        results['roles'] = data.get('roles', [])
        results['catalog_agents'] = data.get('agents', [])
        # Keep actual importer catalog; excludes credential values.
        (OUT/'actual-import-catalog.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        rows = data.get('servers',[]) if isinstance(data,dict) else data
        results['registered_server_names'] = [r.get('name') for r in rows]
results['observed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
results['method'] = 'GET only; no identity creation, registration, Google call or credentials'
(OUT/'existing-identities.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False))
