"""Read-only planner on a new real HTTP/PG human workflow; no rework execution/Codex/PLC."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8080'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False); checks = []
    def save(name, value):
        (out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    def call(path, body=None):
        request = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)}); save('checks', checks)
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        assert passed, name
    raw = json.loads(Path('docs/examples/inspection-review-v1.json').read_text(encoding='utf8'))
    raw['processDefinitionId'] = 'rework_plan_' + uuid.uuid4().hex[:10]
    raw['processDefinitionName'] = '[회귀 검사] 재작업 의존 미리보기 인수 시험'
    second = deepcopy(raw['activities'][0]); second.update(id='task:confirm', name='[회귀 검사] 바뀐 점수 확인', inputData=['score'])
    raw['activities'].append(second)
    raw['sequences'][1]['target'] = second['id']
    raw['sequences'].append({'id': 'confirm-choice', 'source': second['id'], 'target': 'choice'})
    save('definition', raw); save('registered', call('/api/process/definitions', {'definition': raw}))
    opened = call('/api/instances/start', {'definition_id': raw['processDefinitionId'], 'version': raw['version'],
                  'event_id': 'A037-' + uuid.uuid4().hex, 'variables': {'score': 2}})
    pid = opened['proc_inst_id']; path = '/api/instances/' + pid
    before = call(path); save('opened', before)
    first = next(w for w in before['workitems'] if w['activity_id'] == 'task:review')
    preview_path = path + '/rework-preview?workitem_id=' + first['id']
    initial = call(preview_path); save('initial-plan', initial)
    check('server computes new definition dependencies',
          {'task:review', 'task:confirm', 'choice', 'accepted', 'rejected'} == set(initial['affected_nodes']))
    check('preview reports separate explicit request availability', initial['execution_available'] is True and not initial['blockers'])
    check('repeated preview leaves instance workitems and events unchanged',
          call(preview_path) == initial and call(path) == before)
    call('/api/todolist/' + first['id'] + '/submit', {'by': '[회귀 검사] A037 검토자', 'output': {'score': 7}})
    current = call(path); save('after-review', current)
    second_row = next(w for w in current['workitems'] if w['activity_id'] == second['id'])
    check('normal execution preserves original score while passing result to next task',
          current['instance']['initial_variables'] == {'score': 2}
          and second_row['status'] == 'IN_PROGRESS' and '7' in second_row['query'])
    plan = call(preview_path); save('after-review-plan', plan)
    check('invalid output restores true start value and cancels only live affected rows',
          plan['candidate_variables'] == {'score': 2} and plan['invalidated_variables'] == ['score']
          and plan['restored_input_variables'] == ['score'] and plan['cancel_workitems'] == [second_row['id']])
    check('snapshot token changes after accepted work', plan['snapshot_token'] != initial['snapshot_token'])
    check('completed work and current result survive planning untouched', call(path) == current)
    # Existing completed instance is only read: no legacy seeds are fabricated.
    old_path = '/api/instances/anomaly_response.d6a2392c-f5b2-4772-9593-b7b104c8a493'
    old = call(old_path); old_task = next(w for w in old['workitems'] if w['activity_id'] == 'task:diagnose')
    old_plan = call(old_path + '/rework-preview?workitem_id=' + old_task['id']); save('legacy-plan', old_plan)
    check('legacy missing inputs and cancelled instance stay explicit',
          {'initial_inputs_unavailable', 'instance_not_running'} <= {b['code'] for b in old_plan['blockers']}
          and call(old_path) == old)
    status = None
    try: call(path + '/rework-preview?workitem_id=' + old_task['id'])
    except HTTPError as error: status = error.code
    check('foreign workitem cannot be a restart point', status == 409)
    # Finish the ordinary workflow so this probe leaves no pending human task.
    call('/api/todolist/' + second_row['id'] + '/submit', {'by': '[회귀 검사] A037 확정자', 'output': {'score': 8}})
    final = call(path); save('final', final)
    check('ordinary workflow finishes and planner does not reopen it',
          final['instance']['status'] == 'COMPLETED' and final['instance']['end_event'] == 'accepted'
          and 'instance_not_running' in {b['code'] for b in call(preview_path)['blockers']})
    save('result', {'scope': __doc__, 'instance': pid, 'checks': checks})
    print(f'{len(checks)}/{len(checks)} passed', flush=True)


if __name__ == '__main__': main()
