"""Actual Codex repairs an obsolete column using MCP error + live schema.

The obsolete query is an explicit fault injection. The result must come from a
successful subsequent query. This does not prove all SQL repairs or MCP isolation.
"""
import json
import shutil
import time
import uuid

import psycopg
from probe_definition_registry import ROOT, DSN, http
from probe_registered_codex import definition


def main():
    did = 'codex-sql-repair-' + uuid.uuid4().hex[:8]
    out = ROOT / '.evidence/reaudit' / did; out.mkdir()
    raw = definition(did, '2')
    raw['processDefinitionName'] = '업무 조회 오류와 현재 스키마 대조'
    original = "SELECT COUNT(asset_code) AS count FROM ent.assets WHERE asset_code = 'HYD-01'"
    raw['activities'][0]['instruction'] = (
        f'업무 인수 자료의 다음 SELECT를 enterprise query로 먼저 그대로 실행하세요: {original}\n'
        '오류가 나면 오류를 보존하고 enterprise describe_schema에서 현재 표/컬럼을 읽으세요. '
        'HYD-01 설비 수 집계라는 업무 의도를 유지하며 필요한 부분만 고친 SELECT를 enterprise query로 실행하세요. '
        '수정 시도는 최대 두 번입니다. 쓰기는 금지합니다. 성공한 실제 DB 결과만 count에, 실행한 SQL을 sql에, '
        '원래 오류와 스키마 근거를 note에 적으세요. 조회 실패를 0으로 대체하지 마세요.')
    report = {'definition_id': did, 'original_sql': original, 'passed': False}
    def save():
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'definition.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    with psycopg.connect(DSN) as c:
        expected = c.execute("select count(*) from ent.assets where code='HYD-01'").fetchone()[0]
    code, body = http('/api/process/definitions', {'definition': raw}); assert code == 201, (code, body)
    code, body = http('/api/instances/start', {'definition_id': did, 'version': '2', 'event_id': did}); assert code == 200, (code, body)
    pid = body['proc_inst_id']; report['instance_id'] = pid; save(); print('instance', pid, flush=True)
    until = time.monotonic() + 240
    while time.monotonic() < until:
        code, view = http('/api/instances/' + pid); assert code == 200
        wi = view['workitems'][0]
        if view['instance']['status'] == 'COMPLETED': break
        if wi.get('draft_status') in ('FAILED', 'HUMAN_ASKED'): break
        time.sleep(1)
    (out / 'instance.json').write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding='utf-8')
    starts = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_started']
    ends = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_finished']
    queries = [e for e in ends if e.get('tool') == 'enterprise/query']
    envelopes = [e['output']['structured_content'] for e in queries]
    report.update(expected=expected, output=wi.get('output'), status=wi['status'], query_results=envelopes,
                  tools=[e.get('tool') for e in starts])
    save()
    assert wi['status'] == 'DONE' and wi['output']['count'] == expected and wi['output']['note']
    assert 2 <= len(envelopes) <= 3
    assert envelopes[0]['result'] == 'error' and envelopes[0]['statement'] == original
    assert 'asset_code' in envelopes[0]['message']
    assert report['tools'][0] == 'enterprise/query' and 'enterprise/describe_schema' in report['tools']
    successful = [e['document'] for e in envelopes[1:] if e.get('result') == 'ok']
    assert any(e['rows'] == [[expected]] for e in successful)
    report['raw_cli_traces'] = []
    for src in (ROOT / '.evidence/workspace/hyd' / wi['id']).glob('*.events.jsonl'):
        shutil.copy2(src, out / src.name); report['raw_cli_traces'].append(src.name)
    assert report['raw_cli_traces']
    report['passed'] = True; save()
    print('actual Codex obsolete-column repair PASS', out, flush=True)


if __name__ == '__main__':
    main()
