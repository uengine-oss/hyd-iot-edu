"""A083 — unprefixed time-series questions (TimescaleDB SQL · PromQL) answered by the real Claude Code worker from live
metadata (meeting L289~350; the R06 remainder after A081's business-DB questions).

    .venv314/Scripts/python scripts/probe_timeseries_questions.py --out .evidence/reaudit/a083-timeseries-<n>

Fixed UTC windows keep the ground truth stable while the plant keeps producing. The definition names no table, column or
metric; the agent must read hyd-dmn `timeseries_schema` / `prometheus_metadata` first and then run the guarded
`timeseries_query` / `prometheus_query`. Requires host worker + process AGENT_BRIDGE=off + prometheus (compose profile
monitor). No writes.
"""
import argparse
import json
import re
import shutil
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from probe_definition_registry import http, ROOT

PROM = 'http://127.0.0.1:9090'
W0, W1 = '2026-10-06T14:00:00Z', '2026-10-06T14:10:00Z'
AT = int(time.time()) - 120          # the PromQL question's evaluation instant: two minutes before the probe starts (prometheus was started today)
FIELDS = [{'key': 'answer', 'type': 'text', 'text': '질문에 대한 답. 실제 조회 결과의 값만 쓴다'},
          {'key': 'values', 'type': 'array', 'text': '답의 근거가 된 값들'},
          {'key': 'query', 'type': 'text', 'text': '답을 낸 최종 질의(SQL 또는 PromQL) 한 문장. 실제로 실행해 성공한 것'},
          {'key': 'tool', 'type': 'text', 'text': '실행에 쓴 도구 이름'},
          {'key': 'note', 'type': 'text', 'text': '어떤 메타데이터(테이블·열·메트릭 설명)로 대상을 골랐는지'}]


def truth_sql(sql):
    """Ground truth straight from the TimescaleDB container (the host has no reader port mapped)."""
    import subprocess
    r = subprocess.run(['docker', 'exec', 'hyd-iot-edu-timescaledb-1', 'sh', '-c', 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "' + sql.replace('"', '\\"') + '"'],
                       capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert r.returncode == 0, r.stderr
    return [v.strip() for v in r.stdout.strip().split('|')]


def truth_prom(expr):
    with urllib.request.urlopen(PROM + '/api/v1/query?' + urllib.parse.urlencode({'query': expr}), timeout=10) as r:
        d = json.load(r)['data']['result']
    return sorted(f"{s['metric'].get('asset') or s['metric'].get('instance')}={float(s['value'][1]):.3f}" for s in d)


QUESTIONS = [
    dict(key='t1', question=f'HYD-01 설비의 {W0}부터 {W1}까지(UTC) 팬 진동 센서 VS1 값의 최대값은? 소수 셋째 자리까지.',
         truth=lambda: truth_sql(f"select round(max(value)::numeric,3) from public.tag_1s where asset='HYD-01' and name='VS1' and time >= '{W0}' and time < '{W1}'"),
         tools=('hyd-dmn/timeseries_schema', 'hyd-dmn/timeseries_query')),
    dict(key='t2', question=f'HYD-02 설비의 {W0}부터 {W1}까지(UTC) VS1 평균값은? 소수 둘째 자리까지.',
         truth=lambda: truth_sql(f"select round(avg(value)::numeric,2) from public.tag_1s where asset='HYD-02' and name='VS1' and time >= '{W0}' and time < '{W1}'"),
         tools=('hyd-dmn/timeseries_schema', 'hyd-dmn/timeseries_query')),
    dict(key='p1', question=f'Prometheus에서 감지기 이상 점수 메트릭의 epoch {AT} 시점 기준 직전 5분 최대값을 설비(asset 라벨)별로 소수 셋째 자리까지 알려 달라.',
         truth=lambda: truth_prom(f'max_over_time(detector_anomaly_score[5m] @ {AT})'),
         tools=('hyd-dmn/prometheus_metadata', 'hyd-dmn/prometheus_query')),
]


def peak_instant(asset='HYD-01', back_s=7200, floor_s=420):
    """A086: an evaluation instant whose answer clearly differs from now — the highest 5-minute max of the anomaly score in
    the last two hours (e.g. a fault scenario), at least `floor_s` old so it has left the current 5-minute window."""
    now = int(time.time())
    q = urllib.parse.urlencode({'query': f'max_over_time(detector_anomaly_score{{asset="{asset}"}}[5m])', 'start': now - back_s, 'end': now - floor_s, 'step': 30})
    with urllib.request.urlopen(PROM + '/api/v1/query_range?' + q, timeout=10) as r:
        series = json.load(r)['data']['result']
    t, v = max(series[0]['values'], key=lambda x: float(x[1]))
    return int(float(t)), float(v)


def effective_instant(doc):
    """The instant a PromQL tool call actually evaluated: an `@ <epoch>` in the expression wins over the request time."""
    m = re.search(r'@\s*(\d+(?:\.\d+)?)', (doc or {}).get('expression') or '')
    if m:
        return float(m.group(1))
    return ((doc or {}).get('parameters') or {}).get('time')


def definition(did):
    return {'processDefinitionId': did, 'processDefinitionName': '시계열 질문 조회 (메타데이터 기반)', 'version': '1',
            'roles': [{'name': '조회 담당', 'endpoint': 'sys:agent'}],
            'data': [{'name': 'question', 'type': 'Text'}] + [{'name': f['key'], 'type': {'array': 'Array', 'text': 'Text'}[f['type']]} for f in FIELDS],
            'forms': {'timeseries_answer': {'fields_json': FIELDS}},
            'activities': [{'id': 'answer', 'type': 'userTask', 'name': '시계열 질문에 답하기', 'role': '조회 담당',
                            'agentMode': 'COMPLETE', 'orchestration': 'cliagents', 'tool': 'formHandler:timeseries_answer',
                            'agentConfig': {'cli': 'claude-code'},
                            'inputData': ['question'], 'outputData': [f['key'] for f in FIELDS],
                            'instruction': ('입력 데이터의 question에 센서 원천으로 답하세요. 테이블·열·메트릭 이름을 추측하지 말고 hyd-dmn의 '
                                            'timeseries_schema(TimescaleDB 테이블·열·최근 관측 태그) 또는 prometheus_metadata(메트릭 설명)를 먼저 읽은 뒤, '
                                            'timeseries_query(SQL) 또는 prometheus_query(PromQL)를 직접 작성해 실행하세요. 질문의 시간 구간과 시점은 그대로 '
                                            '지키세요(UTC). 실행에 성공한 결과의 값만 answer·values에, 그 질의를 query에, 도구 이름을 tool에, 메타데이터 근거를 note에 '
                                            '적으세요. 결과가 없으면 지어내지 말고 그 사실을 answer에 쓰세요. 이 작업은 조회이며 설비 조치·판단 카드 제출이 아닙니다.')}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}], 'gateways': [],
            'sequences': [{'id': 's1', 'source': 'start', 'target': 'answer'}, {'id': 's2', 'source': 'answer', 'target': 'end'}]}


def main():
    import urllib.parse  # noqa: F401 — used by truth_prom
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--only', default='')
    args = ap.parse_args(); out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    did = 'timeseries-question-' + uuid.uuid4().hex[:8]
    report = {'scope': __doc__, 'definition_id': did, 'window': [W0, W1, AT], 'cases': {}, 'checks': {}}
    def save(): (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save()
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:260]), flush=True)
    raw = definition(did); (out / 'definition.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf8')
    code, body = http('/api/process/definitions', {'definition': raw}); assert code == 201, (code, body)
    def tool_is(name, *wanted): return any(name == w or name == 'mcp__' + w.replace('/', '__') for w in wanted)
    def envelope(o):
        if isinstance(o, dict): return o.get('structured_content') or o
        try: return json.loads(o) if isinstance(o, str) else None
        except ValueError: return None
    if not args.only or 'p2' in args.only.split(','):
        at2, peak = peak_instant(); report['p2_instant'] = dict(at=at2, peak=peak)
        QUESTIONS.append(dict(key='p2', at=at2,
            question=f'Prometheus에서 HYD-01 설비의 감지기 이상 점수 메트릭에 대해, epoch {at2} 시점을 기준으로 직전 5분 최대값을 소수 셋째 자리까지 알려 달라.',
            truth=lambda: truth_prom(f'max_over_time(detector_anomaly_score{{asset="HYD-01"}}[5m] @ {at2})'),
            now_value=lambda: truth_prom('max_over_time(detector_anomaly_score{asset="HYD-01"}[5m])'),
            tools=('hyd-dmn/prometheus_metadata', 'hyd-dmn/prometheus_query')))
    for q in QUESTIONS:
        if args.only and q['key'] not in args.only.split(','):
            continue
        expected = q['truth'](); q['expected'] = expected
        code, body = http('/api/instances/start', {'definition_id': did, 'version': '1', 'event_id': did + '-' + q['key'], 'variables': {'question': q['question']}})
        assert code == 200, (code, body)
        pid = body['proc_inst_id']; t0 = time.monotonic(); print(q['key'], 'instance', pid, 'expected', expected, flush=True)
        until = time.monotonic() + 900
        while time.monotonic() < until:
            try:
                code, view = http('/api/instances/' + pid)
            except Exception as exc:  # noqa: BLE001 — transient (e.g. the process lost its DB route for a moment); keep polling
                print('poll retry:', str(exc)[:120], flush=True); time.sleep(5); continue
            if code != 200:
                time.sleep(5); continue
            wi = view['workitems'][0]
            if view['instance']['status'] == 'COMPLETED' or wi.get('draft_status') in ('FAILED', 'HUMAN_ASKED') or wi['status'] == 'PENDING':
                break
            time.sleep(3)
        elapsed = round(time.monotonic() - t0, 1)
        (out / f"{q['key']}-instance.json").write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding='utf8')
        starts = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_started']
        ends = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_finished']
        tools = [e.get('tool') for e in starts]
        runs = [env for env in (envelope(e.get('output')) for e in ends if tool_is(e.get('tool'), q['tools'][1])) if isinstance(env, dict)]
        good = [x for x in runs if x.get('result') == 'ok']
        output = wi.get('output') or {}
        report['cases'][q['key']] = dict(instance=pid, status=wi['status'], elapsed_s=elapsed, expected=expected, output=output, tools=tools,
                                         executed=[(x.get('document') or {}).get('statement') or (x.get('document') or {}).get('expression') or x.get('statement') for x in runs],
                                         errors=[x.get('message') for x in runs if x.get('result') != 'ok']); save()
        for src in (ROOT / '.evidence/workspace/hyd' / wi['id']).glob('*.events.jsonl'):
            shutil.copy2(src, out / f"{q['key']}-{src.name}")
        check(f"{q['key']}_completed_without_human_help", wi['status'] == 'DONE' and view['instance']['status'] == 'COMPLETED', dict(status=wi['status'], draft=wi.get('draft_status'), elapsed=elapsed))
        check(f"{q['key']}_read_metadata_then_queried_the_right_source", any(tool_is(t, q['tools'][0]) for t in tools) and any(tool_is(t, q['tools'][1]) for t in tools), tools[:8])
        text = json.dumps([output.get('answer'), output.get('values')], ensure_ascii=False)
        def present(v):
            m = re.fullmatch(r'(.*?=)?(-?\d+\.\d+)', v)
            if m:
                num = float(m.group(2)); label = (m.group(1) or '')
                return (label.rstrip('=') in text if label else True) and any(abs(float(x) - num) < 0.0051 for x in re.findall(r'-?\d+\.\d+', text))
            return v in text
        check(f"{q['key']}_answer_matches_direct_source", all(present(v) for v in expected), dict(expected=expected, answer=output.get('answer'), values=output.get('values')))
        check(f"{q['key']}_a_successful_query_produced_the_values", bool(good), dict(executed=report['cases'][q['key']]['executed'][:3], errors=report['cases'][q['key']]['errors'][:2]))
        if q.get('at'):   # A086: the asked instant must be the evaluated instant, and the answer must not be today's value
            instants = [effective_instant(x.get('document')) for x in good]
            now_value = q['now_value'](); report['cases'][q['key']]['now_value'] = now_value; save()
            check(f"{q['key']}_evaluated_at_the_asked_instant", any(i is not None and abs(float(i) - q['at']) <= 1 for i in instants), dict(asked=q['at'], evaluated=instants[:4]))
            differs = abs(float(expected[0].split('=')[-1]) - float(now_value[0].split('=')[-1])) > 0.05
            check(f"{q['key']}_the_asked_instant_differs_from_now", differs, dict(at_value=expected, now_value=now_value))
    passed = sum(c['passed'] for c in report['checks'].values()); total = len(report['checks'])
    print(f"checks passed {passed}/{total}", flush=True)
    return 0 if passed == total else 1


if __name__ == '__main__':
    import urllib.parse
    raise SystemExit(main())
