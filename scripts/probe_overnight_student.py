"""Live student API paths; root operator alone runs this under LIVE_LOCK.

No DB writes outside product APIs, no bulk reset, no simulated worker output.
Artifacts and owned IDs remain in --out for inspection/targeted cleanup.
U9 system PENDING close is deliberately distinct from K4 agent PENDING close.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class Probe:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.run = 'overnight-20261012-' + uuid.uuid4().hex[:8]
        self.owned = {'prefix': self.run, 'flows': [], 'instances': []}
        self.checks = []
        self.sequence = 0
        self.rows = {'table': 'attendee', 'columns': ['email', 'required', 'response'],
                     'where': {'meeting_id': args.meeting}, 'limit': 100}

    def save(self, name, value):
        (self.out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    def check(self, name, passed, detail=None):
        self.checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
        self.save('checks', self.checks)
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        if not passed:
            raise RuntimeError(name)

    def request(self, method, path, body=None, expected=(200, 201)):
        self.sequence += 1
        req = urllib.request.Request(self.args.process.rstrip('/') + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        data = json.loads(raw) if raw else None
        self.save(f'http-{self.sequence:04}', {'method': method, 'path': path, 'body': body,
                                              'status': status, 'response': data})
        if status not in expected:
            raise RuntimeError(f'{method} {path}: HTTP {status}: {str(data)[:600]}')
        return data

    def wait(self, path, predicate, label):
        deadline = time.monotonic() + self.args.timeout
        while time.monotonic() < deadline:
            value = self.request('GET', path)
            if predicate(value):
                self.save(label, value)
                return value
            time.sleep(3)
        raise TimeoutError(f'{label}: {self.args.timeout}s (last response retained)')

    def mcp(self):
        name = self.run + '-table'
        result = self.request('POST', '/api/mcp/servers', {
            'name': name, 'transport': 'streamable_http', 'url': self.args.mcp_url,
            'description': '독립 검증 DB 학생 표 읽기', 'timeout': 20, 'by': self.run})
        self.owned['mcp'] = name
        self.save('owned', self.owned)
        self.check('U18 register connection', result['check']['status'] == 'ok', result['check'])
        checked = self.request('POST', f'/api/mcp/servers/{name}/check', {'timeout': 20, 'by': self.run})
        self.check('U18 connection recheck', checked['check']['status'] == 'ok')
        result = self.request('POST', f'/api/mcp/servers/{name}/tools/read_rows/call',
                              {'arguments': self.rows, 'timeout': 20, 'by': self.run})
        payload = json.loads(result['result']['text'])
        self.save('read-rows', payload)
        self.check('U18 real rows returned', payload.get('result') == 'ok' and
                   payload.get('document', {}).get('row_count', 0) > 0, payload)
        self.check('U18 input preserved', result['arguments'] == self.rows)
        self.expected_rows = payload['document']['rows']

    def agent(self):
        body = {'name': '학생 참석 응답 확인 ' + self.run.rsplit('-', 1)[-1], 'role': '학생 표 조회 담당',
                'goal': '실제 참석 응답 표를 읽고 출처와 함께 한국어로 보고한다.',
                'persona': '추정하지 않는다. 외부 일정이나 메일을 변경하지 않는다.',
                'tools': [self.owned['mcp']], 'skills': [], 'work_rules': 'hyd-plant', 'by': self.run}
        if self.args.model:
            body['model'] = self.args.model
        result = self.request('POST', '/api/agents', body)
        self.owned['agent'] = result['id']
        self.save('owned', self.owned)
        self.check('U17 profile and work_rules saved', result.get('username') == body['name'] and
                   result.get('goal') == body['goal'] and result.get('role') == body['role'] and
                   result.get('work_rules') == 'hyd-plant' and self.owned['mcp'] in result.get('tools', ''))
        # Plant-specific rules are verified, then removed for this local read-only personal example.
        body['work_rules'] = None
        result = self.request('PUT', '/api/agents/' + self.owned['agent'], body)
        self.check('U17 common rules selected', result.get('work_rules') is None)

    def question(self):
        return (f"등록된 {self.owned['mcp']} 서버의 read_rows를 실제 호출하세요. 입력은 "
                f"{json.dumps(self.rows, ensure_ascii=False)} 입니다. 반환된 각 email/required/response를 "
                "한국어로 보고하세요. 결과를 추측하거나 일정 확정·외부 쓰기를 하지 마세요. "
                "근거에는 실제 호출 입력을 그대로 query로 적어 호출 기록과 대조할 수 있게 하세요.")

    def ask(self):
        self.request('GET', '/api/ask/status')
        # ask.start validates uuid.UUID; the portal sends crypto.randomUUID().
        request_id = str(uuid.uuid4())
        self.owned['ask_request_id'] = request_id
        self.save('owned', self.owned)
        result = self.request('POST', '/api/ask', {'question': self.question(), 'agent': self.owned['agent'],
                              'by': self.run, 'request_id': request_id})
        pid = result['id']
        self.owned['instances'].append(pid)
        self.save('owned', self.owned)
        final = self.wait('/api/ask/' + pid,
                          lambda x: x['state'] not in {'waiting', 'running', 'submitted', 'correcting', 'asking'}, 'ask-final')
        self.check('U17 actual worker answered with verified evidence', final['state'] == 'done' and
                   (final.get('result') or {}).get('kind') == 'answered' and
                   (final.get('result') or {}).get('verified', 0) > 0, final.get('result'))
        calls = [c for c in final.get('tool_calls', []) if c.get('ok') and
                 'read_rows' in str(c.get('raw_tool')) and
                 self.owned['mcp'].replace('-', '_') in str(c.get('raw_tool')).replace('-', '_')]
        self.check('U17 actual student read_rows input', any(c.get('input', {}).get('where') == self.rows['where']
                   and c.get('input', {}).get('table') == 'attendee' for c in calls), calls)
        history = self.request('GET', '/api/mcp/calls?' + urllib.parse.urlencode({'server': self.owned['mcp'], 'tool': 'read_rows'}))
        self.check('U18 actual worker call history visible', bool(history.get('calls')), history)

    def register_flow(self, suffix, tasks):
        did = self.run + '-' + suffix
        nodes = '<bpmn:startEvent id="Start"/>'
        previous = 'Start'
        for index, (tid, mapping) in enumerate(tasks.items()):
            tag = 'task' if mapping['part'] == 'agent' else 'serviceTask'
            label = {'Read': '참석 응답 읽기', 'Report': '조회 결과 보고', 'BrokenRead': '읽기 결과 경로 확인'}[tid]
            nodes += f'<bpmn:{tag} id="{tid}" name="{label}"/><bpmn:sequenceFlow id="F{index}" sourceRef="{previous}" targetRef="{tid}"/>'
            previous = tid
        nodes += f'<bpmn:endEvent id="End"/><bpmn:sequenceFlow id="Fend" sourceRef="{previous}" targetRef="End"/>'
        xml = '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="hyd"><bpmn:process id="Student">' + nodes + '</bpmn:process></bpmn:definitions>'
        self.request('POST', '/api/flows/import', {'definition_id': did, 'file_name': did + '.bpmn', 'xml': xml})
        self.owned['flows'].append(did)
        self.save('owned', self.owned)
        display_name = ('학생 참석 응답 확인' if suffix == 'read' else '학생 읽기 실패와 단계 닫기') + ' ' + self.run.rsplit('-', 1)[-1]
        mapping = {'name': display_name, 'start': {'kind': 'human', 'fields': []}, 'lanes': {}, 'tasks': tasks, 'flows': {}}
        checked = self.request('POST', f'/api/flows/{did}/check', {'mapping': mapping})
        self.check(suffix + ' flow preflight', checked['check']['ok'], checked['check'].get('problems'))
        registered = self.request('POST', f'/api/flows/{did}/register', {'mapping': mapping})
        started = self.request('POST', '/api/instances/start', {'definition_id': did, 'version': registered['version'],
                              'event_id': did + '-start', 'variables': {}, 'name': display_name})
        pid = started['proc_inst_id']
        self.owned['instances'].append(pid)
        self.save('owned', self.owned)
        return did, pid

    def personal_flow(self):
        tasks = {'Read': {'part': 'agent', 'agent': self.owned['agent'], 'inputs': [],
                         'instruction': self.question() + ' 읽은 결과와 근거를 summary 문자열로 제출하세요.',
                         'outputs': [{'key': 'summary', 'text': '참석 응답 조회 결과와 근거', 'type': 'textarea'}]},
                 'Report': {'part': 'svc:report', 'inputs': ['summary'],
                            'config': {'outcome': '정상', 'title': '로컬 표 읽기 결과', 'summary': '{summary}'}}}
        did, pid = self.register_flow('read', tasks)
        final = self.wait('/api/instances/' + pid, lambda x: x.get('instance', x).get('status') in
                          {'COMPLETED', 'FAILED', 'CANCELLED', 'TERMINATED'}, 'flow-final')
        instance = final.get('instance', final)
        self.check('U21 local personal flow completed', instance.get('status') == 'COMPLETED', final)
        workitems = final.get('workitems', [])
        self.check('U21 actual agent and report both done', all(any(w.get('activity_id') == tid and w.get('status') == 'DONE'
                   for w in workitems) for tid in ('Read', 'Report')), workitems)
        read = next(w for w in workitems if w.get('activity_id') == 'Read')
        detail = self.request('GET', '/api/todolist/' + read['id'])
        self.save('personal-agent-detail', detail)
        history = self.request('GET', '/api/mcp/calls?' + urllib.parse.urlencode({'server': self.owned['mcp'], 'tool': 'read_rows'}))
        calls = [c for c in history.get('calls', []) if c.get('todo_id') == read['id'] and c.get('state') == 'done']
        self.check('U21 agent task has actual successful tool trace', bool(calls), calls)
        values = {v['key']: v.get('value') for v in instance.get('variables_data', [])}
        self.check('U21 report includes returned attendee data', isinstance(values.get('summary'), str) and
                   all(row['email'] in values['summary'] for row in self.expected_rows), values.get('summary'))

    def failed_system(self):
        tasks = {'BrokenRead': {'part': 'svc:mcp-call', 'config': {
            'server': self.owned['mcp'], 'tool': 'read_rows', 'arguments': self.rows, 'effect': False,
            'extract': {'missing_value': {'path': 'document.overnight_missing_field', 'type': 'Text'}}}}}
        did, pid = self.register_flow('pending', tasks)
        final = self.wait('/api/instances/' + pid,
                          lambda x: any(w.get('activity_id') == 'BrokenRead' and w.get('status') == 'PENDING'
                                        for w in x.get('workitems', [])), 'pending-final')
        wi = next(w for w in final['workitems'] if w.get('activity_id') == 'BrokenRead')
        self.check('U9 pending caused by missing real result path',
                   'overnight_missing_field' in str(wi.get('log') or ''), wi.get('log'))
        self.request('DELETE', '/api/flows/' + did, expected=(409,))
        self.request('POST', '/api/todolist/' + wi['id'] + '/close',
                     {'by': self.run, 'reason': '검증: 실제 읽기 결과에 없는 추출 경로로 실패한 시스템 단계를 닫음'})
        closed = self.request('GET', '/api/instances/' + pid)
        instance = closed.get('instance', closed)
        self.check('U9 real failed system task closed', instance.get('status') == 'COMPLETED' and
                   instance.get('end_event') == 'closed-by-human' and
                   any(w['id'] == wi['id'] and w.get('status') == 'CANCELLED' for w in closed.get('workitems', [])), closed)
        deleted = self.request('DELETE', '/api/flows/' + did)
        self.check('F2 projection queue drained', deleted.get('projection_pending') == 0, deleted)
        self.request('GET', '/api/flows/' + did, expected=(404,))
        self.save('scope-limit', {'K4': 'not covered: this is a real system PENDING task, not an agent PENDING task',
                                 'projection': 'API queue result only; root must separately inspect Neo4j projection absence'})

    def run_all(self):
        for name, fn in [('mcp', self.mcp), ('agent', self.agent), ('ask', self.ask),
                         ('personal_flow', self.personal_flow), ('failed_system', self.failed_system)]:
            try:
                fn()
            except Exception as error:
                self.checks.append({'name': name, 'passed': False, 'error': str(error)})
                print('FAIL ' + name + ': ' + str(error), flush=True)
                if name in {'mcp', 'agent'}:
                    break
            finally:
                self.save('checks', self.checks)
                self.save('owned', self.owned)
        failed = [x for x in self.checks if not x['passed']]
        self.save('summary', {'passed': not failed, 'checks': self.checks, 'owned': self.owned,
                             'cleanup': 'No bulk reset. Owned resources retained for root inspection and targeted cleanup.'})
        return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--process', default='http://127.0.0.1:8080')
    parser.add_argument('--mcp-url', default='http://host.docker.internal:8311/mcp')
    parser.add_argument('--meeting', default='s00:meeting-q3')
    parser.add_argument('--model', default='')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--out', required=True)
    return Probe(parser.parse_args()).run_all()


if __name__ == '__main__':
    raise SystemExit(main())
