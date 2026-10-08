"""Real HTTP/PG/graph end barrier, process kill/restart, rework and concurrency."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from probe_definition_registry import http, ROOT, DSN
import psycopg


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    checks = []
    def save(name, value):
        (out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, value):
        checks.append({'name': name, 'passed': bool(value)})
        save('checks', checks); print(('PASS ' if value else 'FAIL ') + name, flush=True)
        assert value, name
    def request(path, data=None):
        status, value = http(path, data)
        assert status in (200, 201), (status, value)
        return value
    def wait_health():
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if http('/healthz')[0] == 200: return
            except OSError: pass
            time.sleep(.5)
        raise TimeoutError('process health')
    wait_health()
    raw = json.loads((ROOT / 'docs/examples/independent-reviews-v1.json').read_text())
    raw['processDefinitionId'] += '-' + uuid.uuid4().hex[:10]
    request('/api/process/definitions', {'definition': raw}); save('definition', raw)
    def start(definition_id=None):
        inst = request('/api/instances/start', {'definition_id': definition_id or raw['processDefinitionId'], 'version': '1', 'event_id': str(uuid.uuid4())})
        pid = inst['proc_inst_id']
        rows = {w['activity_id']: w for w in request('/api/instances/' + pid)['workitems']}
        return pid, rows
    def submit(row, value):
        return request('/api/todolist/' + row['id'] + '/submit', {'output': {row['activity_id']: value}, 'by': '[회귀 검사] A062 검사기'})
    if '--shared-only' in sys.argv:
        shared = deepcopy(raw)
        shared['processDefinitionId'] += '-shared'
        shared['sequences'][-1]['target'] = 'end-a'
        request('/api/process/definitions', {'definition': shared}); save('shared-definition', shared)
        pid, rows = start(shared['processDefinitionId'])
        submit(rows['b'], 'unaffected result')
        before = request('/api/instances/' + pid); save('shared-before', before)
        check('shared_end_waits_for_other_live_path', before['instance']['status'] == 'RUNNING')
        preview = request('/api/instances/' + pid + '/rework-preview?workitem_id=' + rows['a']['id'])
        result = request('/api/instances/' + pid + '/rework', dict(workitem_id=rows['a']['id'], request_id=str(uuid.uuid4()),
            snapshot_token=preview['snapshot_token'], by='[회귀 검사] A062 검사기', role='role:operator', reason='[회귀 검사] 공유 끝점 재작업'))
        after = request('/api/instances/' + pid); save('shared-rework', after)
        check('shared_end_keeps_unaffected_producer_arrival', after['instance']['flow_state']['end_arrivals']
              == before['instance']['flow_state']['end_arrivals'])
        current = next(w for w in after['workitems'] if w['id'] == result['start_workitem'])
        submit(current, 'revised result')
        final = request('/api/instances/' + pid); save('shared-final', final)
        check('shared_end_records_both_generations_at_completion', final['instance']['status'] == 'COMPLETED'
              and len(final['instance']['flow_state']['end_arrivals']) == 2
              and {a['generation'] for a in final['instance']['flow_state']['end_arrivals']} == {0, 1})
        graph = request('/api/instances/' + pid + '/graph'); save('shared-graph', graph)
        check('shared_end_graph_matches_source_state_and_rows', graph['graph']['instance']['status'] == final['instance']['status']
              and {w['id']: w['status'] for w in graph['graph']['workitems']} == {w['id']: w['status'] for w in final['workitems']})
        return
    pid, rows = start()
    submit(rows['a'], 'first result')
    before = request('/api/instances/' + pid); save('first-end', before)
    check('first_end_waits_with_other_work_live', before['instance']['status'] == 'RUNNING' and before['instance']['end_event'] is None)
    with psycopg.connect(DSN) as conn:
        stored = conn.execute('select flow_state from bpm_proc_inst where proc_inst_id=%s', (pid,)).fetchone()[0]
    check('end_arrival_is_in_actual_postgresql', stored == before['instance']['flow_state'] and stored['end_arrivals'][0]['workitem'] == rows['a']['id'])
    killed = subprocess.run(['docker', 'kill', 'hyd-iot-edu-process-1'], capture_output=True, text=True, check=True)
    save('kill', {'exit_code': killed.returncode, 'stdout': killed.stdout})
    subprocess.run(['docker', 'start', 'hyd-iot-edu-process-1'], capture_output=True, check=True)
    wait_health()
    resumed = request('/api/instances/' + pid); save('after-restart', resumed)
    check('restart_preserves_waiting_end_and_remaining_work', resumed['instance']['flow_state'] == stored
          and resumed['instance']['status'] == 'RUNNING'
          and next(w for w in resumed['workitems'] if w['id'] == rows['b']['id'])['status'] == 'IN_PROGRESS')
    preview = request('/api/instances/' + pid + '/rework-preview?workitem_id=' + rows['a']['id'])
    reworked = request('/api/instances/' + pid + '/rework', dict(workitem_id=rows['a']['id'], request_id=str(uuid.uuid4()),
        snapshot_token=preview['snapshot_token'], by='[회귀 검사] A062 검사기', role='role:operator', reason='[회귀 검사] 첫 검토 다시'))
    current = request('/api/instances/' + pid)
    state = current['instance']['flow_state']
    check('rework_retires_only_old_end_and_preserves_evidence', not state['end_arrivals']
          and state['superseded_end_arrivals'][0]['arrivals'] == stored['end_arrivals'])
    submit(rows['b'], 'second result')
    check('unaffected_path_end_waits_for_new_generation', request('/api/instances/' + pid)['instance']['status'] == 'RUNNING')
    new_a = next(w for w in current['workitems'] if w['id'] == reworked['start_workitem'])
    submit(new_a, 'revised first result')
    final = request('/api/instances/' + pid); save('final', final)
    check('new_generation_and_unaffected_path_finish_together', final['instance']['status'] == 'COMPLETED'
          and {a['event']: a['generation'] for a in final['instance']['flow_state']['end_arrivals']} == {'end-a': 1, 'end-b': 0})
    check('old_completed_output_is_preserved', next(w for w in final['workitems'] if w['id'] == rows['a']['id'])['output'] == {'a': 'first result'})
    pid2, parallel = start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda key: submit(parallel[key], key), ('a', 'b')))
    concurrent = request('/api/instances/' + pid2); save('concurrent', concurrent)
    check('concurrent_http_commits_both_results_and_arrivals', concurrent['instance']['status'] == 'COMPLETED'
          and len(concurrent['instance']['flow_state']['end_arrivals']) == 2
          and all(w['status'] == 'DONE' for w in concurrent['workitems']))
    for name, target in [('rework', pid), ('concurrent', pid2)]:
        graph = request('/api/instances/' + target + '/graph'); save('graph-' + name, graph)
        # Preserve the complete response for semantic review; counts alone are not graph truth.
    print(out, flush=True)


if __name__ == '__main__': main()
