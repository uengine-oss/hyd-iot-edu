"""Live process HTTP/PG/Neo4j: human rework generations, concurrency and restart. No Codex or PLC."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8080'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False); checks = []
    def save(name, value): (out/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    def call(path, data=None):
        req = Request(BASE+path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=30) as response: return response.status, json.load(response)
        except HTTPError as error: return error.code, json.load(error)
    def ok(path, data=None):
        status, body = call(path, data)
        assert status in (200, 201, 202), (status, body)
        return body
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)}); save('checks', checks)
        print(('PASS ' if passed else 'FAIL ') + name, flush=True); assert passed, name
    def latest(view, aid):
        return max((w for w in view['workitems'] if w['activity_id'] == aid), key=lambda w: (w.get('generation') or 0, w['start_date']))
    raw = json.loads(Path('docs/examples/rework-inspection-v1.json').read_text(encoding='utf8'))
    raw['processDefinitionId'] += '_' + uuid.uuid4().hex[:8]
    save('definition', raw); ok('/api/process/definitions', {'definition': raw})
    inst = ok('/api/instances/start', {'definition_id': raw['processDefinitionId'], 'version': '1',
              'event_id': 'A038-' + uuid.uuid4().hex, 'variables': {'score': 2}})
    path = '/api/instances/' + inst['proc_inst_id']; view = ok(path)
    first = latest(view, 'measure'); ok('/api/todolist/' + first['id'] + '/submit', {'by': 'A038 measurer', 'output': {'score': 7}})
    second = latest(ok(path), 'check'); ok('/api/todolist/' + second['id'] + '/submit', {'by': 'A038 checker', 'output': {'score': 9}})
    before = ok(path); save('before', before)
    preview = ok(path + '/rework-preview?workitem_id=' + second['id']); save('preview', preview)
    check('restarting overwriter reuses real preceding output 7 instead of seed 2', preview['candidate_variables'] == {'score': 7} and preview['execution_available'])
    req = {'workitem_id': second['id'], 'request_id': str(uuid.uuid4()), 'snapshot_token': preview['snapshot_token'],
           'by': 'A038 reviewer', 'role': 'role:operator', 'reason': 'Measurement review changed; retain earlier measurement'}
    check('unknown requester role is rejected without mutation', call(path + '/rework', dict(req, role='outsider'))[0] == 403 and ok(path) == before)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: call(path + '/rework', req), range(4)))
    save('concurrent-same', responses); result = responses[0][1]
    check('four concurrent HTTP requests commit one generation and same receipt', all(status == 200 and body == result for status, body in responses) and len(ok(path)['reworks']) == 1)
    after = ok(path); save('after-generation1', after)
    check('original DONE output and preceding work remain intact',
          next(w for w in after['workitems'] if w['id'] == second['id']) == next(w for w in before['workitems'] if w['id'] == second['id'])
          and latest(after, 'measure') == latest(before, 'measure'))
    next_check = latest(after, 'check'); timer = latest(after, 'deadline')
    check('new UUID generation and timer replace older work with predecessor link',
          next_check['id'] != second['id'] and next_check['generation'] == 1 and next_check['supersedes_id'] == second['id']
          and next_check['reference_ids'] == [first['id']] and timer['generation'] == 1)
    old_finish = latest(before, 'finish')
    stale = call('/api/todolist/' + old_finish['id'] + '/submit', {'by': 'late person', 'output': {'note': 'obsolete'}})
    check('cancelled prior human submission is rejected', stale[0] == 400 and latest(ok(path), 'check')['output'] is None)
    check('request ID cannot be reused with changed reason', call(path + '/rework', dict(req, reason='different'))[0] == 409)
    preview2 = ok(path + '/rework-preview?workitem_id=' + next_check['id'])
    requests = [dict(req, workitem_id=next_check['id'], request_id=str(uuid.uuid4()), snapshot_token=preview2['snapshot_token']) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool: raced = list(pool.map(lambda request: call(path + '/rework', request), requests))
    save('concurrent-different', raced)
    check('different concurrent requests from same snapshot yield one success one conflict', sorted(status for status, _ in raced) == [200, 409] and len(ok(path)['reworks']) == 2)
    current = ok(path); saved = deepcopy(current); save('before-restart', current)
    restart = subprocess.run(['docker', 'compose', 'restart', 'process'], capture_output=True)
    (out/'restart.log').write_bytes(restart.stdout + restart.stderr); restart.check_returncode()
    deadline = time.monotonic() + 45
    while True:
        try:
            if ok('/healthz').get('ok'): break
        except Exception:
            if time.monotonic() > deadline: raise
        time.sleep(0.5)
    current = ok(path); save('after-restart', current)
    check('process restart retains exact generation rows and receipts', current == saved and ok(path + '/rework', req) == result)
    check_row = latest(current, 'check'); ok('/api/todolist/' + check_row['id'] + '/submit', {'by': 'A038 rechecker', 'output': {'score': 11}})
    finish = latest(ok(path), 'finish'); ok('/api/todolist/' + finish['id'] + '/submit', {'by': 'A038 confirmer', 'output': {'note': 'New generation compared with preserved history'}})
    final = ok(path); save('final', final)
    check('generation 2 completes with changed output and original input', final['instance']['status'] == 'COMPLETED'
          and final['instance']['initial_variables'] == {'score': 2}
          and next(v['value'] for v in final['instance']['variables_data'] if v['key'] == 'score') == 11)
    graph = ok(path + '/graph'); save('graph', graph)
    graph_rows = {w['id']: w for w in graph['graph']['workitems']}
    check('actual Neo4j preserves each workitem UUID generation and replacement link',
          all(graph_rows[w['id']]['generation'] == w['generation'] and graph_rows[w['id']]['status'] == w['status']
              and graph_rows[w['id']].get('supersedes_id') == w.get('supersedes_id') for w in final['workitems'])
          and graph['graph']['instance']['rework_generation'] == 2)
    save('result', {'scope': __doc__, 'instance': inst['proc_inst_id'], 'checks': checks})
    print(f'{len(checks)}/{len(checks)} passed', flush=True)


if __name__ == '__main__': main()
