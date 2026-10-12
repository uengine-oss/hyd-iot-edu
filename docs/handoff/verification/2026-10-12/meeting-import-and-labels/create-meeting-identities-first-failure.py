import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path('D:/work/study/hyd-iot-edu')
OUT = Path(__file__).parent
LOCK = ROOT / '.evidence/LIVE_LOCK'
def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
def call(path, body=None):
    request = Request('http://127.0.0.1:8080' + path,
                      data=None if body is None else json.dumps(body).encode('utf8'),
                      headers={} if body is None else {'Content-Type': 'application/json'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)

owner = 'Codex Sol6.1 ' + datetime.now(timezone.utc).isoformat() + ' meeting configuration only, 20 min'
with LOCK.open('x', encoding='utf8') as stream:
    stream.write(owner + '\n')
save('identity-live-lock.json', {'owner': owner})
catalog = call('/api/flows/catalog')
agents = call('/api/agents')
save('identity-catalog-before.json', catalog)
save('identity-agents-before.json', agents)
plan = json.loads((OUT / 'identity-setup-plan.json').read_text(encoding='utf8-sig'))
role_body = plan['create_role']['body']
agent_body = dict(plan['create_agent']['body'], model='')
save('identity-create-requests.json', {'role': role_body, 'agent': agent_body,
    'model_policy': 'inherit configured portal execution model; development Sol6.1 does not override product model',
    'preparation_only': True})
created_role = call('/api/roles', role_body)
save('identity-created-role.json', created_role)
created_agent = call('/api/agents', agent_body)
save('identity-created-agent.json', created_agent)
after_catalog = call('/api/flows/catalog')
after_agents = call('/api/agents')
save('identity-catalog-after.json', after_catalog)
save('identity-agents-after.json', after_agents)
save('identity-create-result.json', {'role': created_role, 'agent': created_agent,
    'google_calls': 0, 'flow_registration': 0, 'execution_ready': False,
    'role_member_assigned': False, 'lock_retained_for_root_capture': True})
print(json.dumps({'created': True, 'execution_ready': False, 'google_calls': 0}))
