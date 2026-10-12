"""Read-only K3 registration/credential-existence audit. Never reads credential contents."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

T = Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
R = Path('D:/work/study/hyd-iot-edu')
H = Path(__file__).resolve().parent
H.mkdir(parents=True, exist_ok=True)

def get(path):
    try:
        with urlopen('http://127.0.0.1:8080'+path, timeout=10) as response:
            return json.load(response), response.status
    except HTTPError as exc:
        return {'error_type': type(exc).__name__}, exc.code
    except (URLError, TimeoutError) as exc:
        return {'error_type': type(exc).__name__}, None

raw, status = get('/api/mcp/servers')
servers = []
for row in raw.get('servers', []):
    # server_view already masks secrets; do not save arbitrary values anyway.
    spec = row.get('config') or row.get('spec') or {}
    safe = {'name': row.get('name'), 'row_field_names': sorted(row),
            'transport': row.get('transport'), 'type': row.get('type'),
            'configuration_field_names': sorted(spec) if isinstance(spec, dict) else []}
    for value in [row.get('url'), spec.get('url') if isinstance(spec, dict) else None]:
        if isinstance(value, str):
            u = urlsplit(value)
            safe['endpoint'] = {'scheme': u.scheme, 'host': u.hostname, 'port': u.port,
                                'path': u.path, 'has_query': bool(u.query)}
    servers.append(safe)
names = [r['name'] for r in servers if isinstance(r['name'], str)]
relevant = [n for n in names if re.search(r'google|gcal|gdrive|calendar|drive', n, re.I)]
capabilities = []
for name in relevant:
    from urllib.parse import quote
    response, code = get('/api/mcp/servers/'+quote(name, safe='')+'/tools?timeout=5')
    capabilities.append({'server': name, 'http_status': code, 'status': response.get('status'),
                         'error_kind': response.get('error_kind'),
                         'tools': [{'name': t.get('name'),
                                    'read_only': t.get('read_only'),
                                    'input_required': (t.get('input_schema') or {}).get('required', [])}
                                   for t in response.get('tools', [])]})
env_keys = {}
for envfile in (R/'.env', T/'.env'):
    env_keys[str(envfile)] = sorted({line.partition('=')[0].strip() for line in
        envfile.read_text(encoding='utf-8-sig').splitlines()
        if '=' in line and not line.lstrip().startswith('#')}) if envfile.is_file() else None
base = Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')/'HYD/google-meeting'
credential_files = [{'kind': 'default_token', 'path': str(base/'token.json'), 'exists': (base/'token.json').is_file()},
                    {'kind': 'documented_client_location', 'path': str(base/'client.json'), 'exists': (base/'client.json').is_file()}]
override = os.environ.get('GOOGLE_MEETING_TOKEN_FILE')
if override:
    credential_files.append({'kind': 'process_env_token_override', 'path': override,
                             'exists': Path(override).is_file()})
health = []
for port in (8511, 8512):
    try:
        with urlopen(f'http://127.0.0.1:{port}/healthz', timeout=3) as r:
            data = json.load(r)
            health.append({'port': port, 'status': r.status,
                           'credential_configured': data.get('credential_configured'),
                           'google_read_verified': data.get('google_read_verified')})
    except HTTPError as exc:
        health.append({'port': port, 'status': exc.code})
    except (URLError, TimeoutError) as exc:
        health.append({'port': port, 'status': None, 'error_type': type(exc).__name__})
source_paths = ['it/process/procsvc/mcp_api.py', 'it/process/procsvc/mcp_check.py',
                'it/process/procsvc/mcp_secrets.py', 'it/agent-worker/worker/bridge.py',
                'it/agent-worker/worker/context.py', 'students/_template/google_meeting_mcp/auth.py',
                'students/_template/google_meeting_mcp/server.py', 'scripts/google_meeting_auth.py']
data = {'created_utc': datetime.now(timezone.utc).isoformat(), 'method': 'GET and file existence only',
        'registration_http_status': status, 'registered_servers': servers,
        'google_named_registered_servers': relevant, 'live_capabilities': capabilities,
        'credential_file_existence': credential_files, 'credential_contents_read': False,
        'environment_file_keys_only': env_keys, 'local_google_server_health': health,
        'override_boundary': 'Process env override checked by existence; .env values are not read. '
                             'A different external configured token location is not inferred.',
        'source_sha256': {p: hashlib.sha256((T/p).read_bytes()).hexdigest() for p in source_paths},
        'tests_run': 0, 'writes_or_registration': 0, 'google_calendar_calls': 0,
        'cli_settings_read': False}
(H/'runtime-boundary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'registered_server_count': len(servers), 'google_named_servers': relevant,
                  'credential_file_exists': {r['kind']: r['exists'] for r in credential_files},
                  'local_health': health, 'no_secrets_read_or_output': True}))
