"""A086 — rule-based queries (meeting L289~302: DMN 규칙 → 질의): given only a rule id, the real Claude Code worker reads the
rule's tests, finds each tested input's source from the ontology, queries those sources itself, and says whether the
condition holds now — with "unknown" when a source has no value (R05: 데이터 없음은 거짓이 아니다).

    .venv314/Scripts/python scripts/probe_rule_questions.py --out .evidence/reaudit/a086-rules-<n>

Ground truth is computed here straight from the same sources with the same formulas the deterministic engine uses
(CMMS standby_ready; TimescaleDB FanSpeedSP ≥ 99 % time over 48 h = agentsvc.tools.mcp_tsdb.fan100_hours; latest PS1).
Requires host worker + process AGENT_BRIDGE=off. No writes.
"""
import argparse
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from probe_definition_registry import http, ROOT

FIELDS = [{'key': 'holds', 'type': 'text', 'text': '규칙 조건이 지금 성립하는지: true / false / unknown 중 하나'},
          {'key': 'values', 'type': 'array', 'text': '규칙이 검사하는 입력마다 "변수=값" (값이 없으면 "변수=없음")'},
          {'key': 'queries', 'type': 'array', 'text': '값을 얻으려고 실제로 실행해 성공한 질의들'},
          {'key': 'note', 'type': 'text', 'text': '어떤 규칙 정의와 입력 출처 메타데이터로 질의를 만들었는지'}]


def tsdb(sql):
    r = subprocess.run(['docker', 'exec', 'hyd-iot-edu-timescaledb-1', 'psql', '-U', 'hyd', '-d', 'hyd', '-tAc', sql], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def ent(sql):
    r = subprocess.run(['docker', 'exec', 'supabase_db_hyd-iot-edu', 'psql', '-U', 'postgres', '-d', 'postgres', '-tAc', sql], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def truth_standby():
    v = ent("select standby_ready from ent.maintenance_profiles where asset='HYD-03'")
    return {'holds': 'unknown' if v == '' else ('true' if v == 'f' else 'false'), 'value': None if v == '' else v}


def truth_fan24():
    """HM-7.3 / rule:fan-24h: the current continuous run at ≥ 99 % (same as agentsvc.tools.mcp_tsdb.fan100_hours since A086)."""
    row = tsdb("""WITH s AS (SELECT time, value FROM tag_1s WHERE asset = 'HYD-01' AND name = 'FanSpeedSP' AND time > now() - interval '48 hours'),
                       newest AS (SELECT time, value FROM s ORDER BY time DESC LIMIT 1), broke AS (SELECT max(time) AS t FROM s WHERE value < 99)
                  SELECT (SELECT value FROM newest), extract(epoch FROM (SELECT time FROM newest) - (SELECT min(time) FROM s WHERE time > coalesce((SELECT t FROM broke), '-infinity'::timestamptz))) / 3600.0""")
    value, run = (row.split('|') + [''])[:2]
    v = 0.0 if float(value) < 99 or not run else round(float(run), 2)
    return {'holds': 'true' if v > 24 else 'false', 'value': v}


def truth_ps1():
    v = float(tsdb("select value from tag_1s where asset='HYD-02' and name='PS1' order by time desc limit 1"))
    return {'holds': 'true' if v < 165 else 'false', 'value': round(v, 1)}


QUESTIONS = [
    dict(key='r1', question='규칙 rule:standby 의 조건이 설비 HYD-03에서 지금 성립하는가?', truth=truth_standby, tol=None, var='standby_ready'),
    dict(key='r2', question='규칙 rule:fan-24h 의 조건이 설비 HYD-01에서 지금 성립하는가? 그 입력 값도 알려 달라.', truth=truth_fan24, tol=0.1, var='fan100_hours'),
    dict(key='r3', question='규칙 rule:dx-pump 의 센서 조건이 설비 HYD-02에서 지금 성립하는가? 경보 패턴은 PUMP_LEAKAGE로 주어졌다고 보고, 센서 입력의 현재 값을 직접 조회해 판단하라.',
         truth=truth_ps1, tol=5.0, var='ps1'),
]


def definition(did):
    return {'processDefinitionId': did, 'processDefinitionName': '규칙 조건 조회 (규칙 → 질의)', 'version': '1',
            'roles': [{'name': '조회 담당', 'endpoint': 'sys:agent'}],
            'data': [{'name': 'question', 'type': 'Text'}] + [{'name': f['key'], 'type': {'array': 'Array', 'text': 'Text'}[f['type']]} for f in FIELDS],
            'forms': {'rule_answer': {'fields_json': FIELDS}},
            'activities': [{'id': 'answer', 'type': 'userTask', 'name': '규칙 조건 확인하기', 'role': '조회 담당',
                            'agentMode': 'COMPLETE', 'orchestration': 'cliagents', 'tool': 'formHandler:rule_answer',
                            'agentConfig': {'cli': 'claude-code'},
                            'inputData': ['question'], 'outputData': [f['key'] for f in FIELDS],
                            'instruction': ('입력 데이터의 question이 가리키는 규칙을 hyd-dmn dmn_rules로 읽고, 규칙이 검사하는 입력마다 hyd-dmn inputs로 '
                                            '출처(센서·시스템)를 확인하세요. 그 출처의 원천(hyd-dmn timeseries_schema/timeseries_query 또는 enterprise '
                                            'describe_catalog/query)에서 현재 값을 직접 질의해 조건을 평가하세요. 값이 없으면 거짓으로 간주하지 말고 unknown으로 답하세요. '
                                            'holds·values·queries·note를 채우세요. 이 작업은 조회이며 설비 조치·판단 카드 제출이 아닙니다. 쓰기는 금지합니다.')}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}], 'gateways': [],
            'sequences': [{'id': 's1', 'source': 'start', 'target': 'answer'}, {'id': 's2', 'source': 'answer', 'target': 'end'}]}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--only', default='')
    args = ap.parse_args(); out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    did = 'rule-question-' + uuid.uuid4().hex[:8]
    report = {'scope': __doc__, 'definition_id': did, 'cases': {}, 'checks': {}}
    def save(): (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save()
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:300]), flush=True)
    raw = definition(did); (out / 'definition.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf8')
    code, body = http('/api/process/definitions', {'definition': raw}); assert code == 201, (code, body)
    def tool_is(name, *wanted): return any(name == w or name == 'mcp__' + w.replace('/', '__') for w in wanted)
    def envelope(o):
        if isinstance(o, dict): return o.get('structured_content') or o
        try: return json.loads(o) if isinstance(o, str) else None
        except ValueError: return None
    for q in QUESTIONS:
        if args.only and q['key'] not in args.only.split(','):
            continue
        code, body = http('/api/instances/start', {'definition_id': did, 'version': '1', 'event_id': did + '-' + q['key'], 'variables': {'question': q['question']}})
        assert code == 200, (code, body)
        pid = body['proc_inst_id']; t0 = time.monotonic(); print(q['key'], 'instance', pid, flush=True)
        until = time.monotonic() + 900
        while time.monotonic() < until:
            try:
                code, view = http('/api/instances/' + pid)
            except Exception as exc:  # noqa: BLE001
                print('poll retry:', str(exc)[:120], flush=True); time.sleep(5); continue
            if code != 200:
                time.sleep(5); continue
            wi = view['workitems'][0]
            if view['instance']['status'] == 'COMPLETED' or wi.get('draft_status') in ('FAILED', 'HUMAN_ASKED') or wi['status'] == 'PENDING':
                break
            time.sleep(3)
        truth = q['truth']()                                       # right after the answer: the closest "now"
        elapsed = round(time.monotonic() - t0, 1)
        (out / f"{q['key']}-instance.json").write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding='utf8')
        starts = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_started']
        ends = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_finished']
        tools = [e.get('tool') for e in starts]
        source_runs = [env for env in (envelope(e.get('output')) for e in ends if tool_is(e.get('tool'), 'hyd-dmn/timeseries_query', 'enterprise/query')) if isinstance(env, dict)]
        good = [x for x in source_runs if x.get('result') == 'ok']
        output = wi.get('output') or {}
        holds = str(output.get('holds') or '').strip().lower()
        holds = 'unknown' if holds in ('unknown', '미확인', 'none', 'null', '') else holds
        report['cases'][q['key']] = dict(instance=pid, status=wi['status'], elapsed_s=elapsed, truth=truth, output=output, tools=tools,
                                         executed=[(x.get('document') or {}).get('statement') or x.get('statement') for x in source_runs]); save()
        for src in (ROOT / '.evidence/workspace/hyd' / wi['id']).glob('*.events.jsonl'):
            shutil.copy2(src, out / f"{q['key']}-{src.name}")
        check(f"{q['key']}_completed_without_human_help", wi['status'] == 'DONE' and view['instance']['status'] == 'COMPLETED', dict(status=wi['status'], draft=wi.get('draft_status'), elapsed=elapsed))
        check(f"{q['key']}_read_the_rule_and_the_input_sources", any(tool_is(t, 'hyd-dmn/dmn_rules') for t in tools)
              and any(tool_is(t, 'hyd-dmn/inputs', 'hyd-dmn/timeseries_schema', 'enterprise/describe_catalog', 'enterprise/describe_schema') for t in tools), tools[:10])
        check(f"{q['key']}_queried_the_source_itself", bool(good), dict(executed=report['cases'][q['key']]['executed'][:3]))
        check(f"{q['key']}_condition_verdict_matches", holds == truth['holds'], dict(answer=output.get('holds'), truth=truth))
        if q['tol'] is not None:
            # the value reported for the rule's variable ("<var>=<number>"), not any number in the text (a086-rules-1 matched "1.5 s")
            first = next((m for v in output.get('values') or [] for m in [re.match(rf"\s*{q['var']}\s*=\s*(-?\d+(?:\.\d+)?)", str(v))] if m), None)
            reported = float(first.group(1)) if first else None
            check(f"{q['key']}_input_value_matches_the_source", reported is not None and abs(reported - truth['value']) <= q['tol'], dict(reported=reported, values=output.get('values'), truth=truth['value'], tol=q['tol']))
        else:
            check(f"{q['key']}_missing_value_is_reported_as_missing", 'false' not in holds and any(w in json.dumps(output.get('values'), ensure_ascii=False).lower() for w in ('없음', 'null', 'none', 'unknown', '미확인')),
                  dict(values=output.get('values')))
    passed = sum(c['passed'] for c in report['checks'].values()); total = len(report['checks'])
    print(f"checks passed {passed}/{total}", flush=True)
    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
