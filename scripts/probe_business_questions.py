"""A081 — unprefixed business questions answered by the real Claude Code worker from live metadata (meeting L289~350:
규칙·DDL·메타데이터로 미리 고정되지 않은 조건/컬럼의 질의를 만들어 실행한다).

    .venv314/Scripts/python scripts/probe_business_questions.py --out .evidence/reaudit/a081-questions-<n>

One registered definition (business_question) whose single agent task receives a question as pinned input and must answer it
from the enterprise MCP (describe_catalog/describe_schema → guarded SELECT via query). Nothing in the definition names a
table or column. Each question's ground truth is computed here by direct SQL before the run. The agent's answer must match,
the SQL it reports must be one the tool actually executed successfully, and it must name the tables it used.
Requires: host worker (scripts/run_worker_host.sh) and process with AGENT_BRIDGE=off. No PLC/enterprise writes.
"""
import argparse
import json
import re
import sys
import shutil
import time
import uuid
from decimal import Decimal
from pathlib import Path

import psycopg
from probe_definition_registry import http, DSN, ROOT
sys.path.insert(0, str(ROOT / 'common'))
from hydcommon.sql_read import guard  # noqa: E402 — the enterprise MCP's own SQL normalizer (A086)

QUESTIONS = [
    dict(key='q1', question='HYD-02 설비의 현재 생산오더는 납기까지 몇 시간 남았고, 그 설비 판매 계약의 고객 등급은 무엇인가?',
         truth="select ent.hours_from_now(o.due_at), c.customer_tier from ent.production_orders o join ent.sales_contracts c on c.asset=o.asset where o.asset='HYD-02'",
         tolerance={0: 0.1},   # A086: hours until the stored due date keep moving between the truth query and the agent's
         expect_tables={'production_orders', 'sales_contracts'}),
    dict(key='q2', question='완제품 재고 수량이 가장 적은 설비 코드와 그 재고 수량은?',
         truth="select asset, fg_stock from ent.fg_inventory order by fg_stock asc limit 1", expect_tables={'fg_inventory'}),
    dict(key='q3', question='다음 출하까지 남은 시간이 가장 짧은 설비 코드와 그 시간(시간 단위)은?',
         truth="select asset, ent.hours_from_now(ship_at) from ent.fg_inventory order by ship_at asc limit 1", expect_tables={'fg_inventory'},
         tolerance={1: 0.1}),
]
FIELDS = [{'key': 'answer', 'type': 'text', 'text': '질문에 대한 답. 실제 조회 결과의 값만 쓴다'},
          {'key': 'values', 'type': 'array', 'text': '답의 근거가 된 값들을 조회 결과 순서대로'},
          {'key': 'sql', 'type': 'text', 'text': '답을 낸 최종 SELECT 한 문장(실제로 실행해 성공한 것)'},
          {'key': 'tables', 'type': 'array', 'text': '사용한 ent 테이블 이름 목록'},
          {'key': 'note', 'type': 'text', 'text': '어떤 메타데이터(주석·컬럼)로 표·컬럼을 골랐는지'}]


def definition(did):
    return {'processDefinitionId': did, 'processDefinitionName': '업무 질문 조회 (메타데이터 기반)', 'version': '1',
            'roles': [{'name': '조회 담당', 'endpoint': 'sys:agent'}],
            'data': [{'name': 'question', 'type': 'Text'}] + [{'name': f['key'], 'type': {'array': 'Array', 'text': 'Text'}[f['type']]} for f in FIELDS],
            'forms': {'business_answer': {'fields_json': FIELDS}},
            'activities': [{'id': 'answer', 'type': 'businessRuleTask', 'name': '업무 질문에 답하기', 'role': '조회 담당',
                            'agentMode': 'COMPLETE', 'orchestration': 'cliagents', 'tool': 'formHandler:business_answer',
                            'agentConfig': {'cli': 'claude-code'},        # not read_only: cliagents maps it to Claude Code plan mode, which blocks every MCP call (a081-questions-1)
                            'inputData': ['question'], 'outputData': [f['key'] for f in FIELDS],
                            'instruction': ('입력 데이터의 question에 업무 DB로 답하세요. 표·컬럼을 추측하지 말고 enterprise describe_catalog(컬럼 주석)와 '
                                            'describe_schema로 현재 메타데이터를 읽은 뒤 SELECT를 직접 작성해 enterprise query로 실행하세요. '
                                            '실행에 성공한 결과의 값만 answer·values에 쓰고, 그 SELECT를 sql에, 사용한 테이블을 tables에, '
                                            '표·컬럼을 고른 메타데이터 근거를 note에 적으세요. 결과가 없으면 지어내지 말고 answer에 그 사실을 쓰세요. '
                                            '이 작업은 조회이며 설비 조치·판단 카드 제출이 아닙니다. 쓰기는 금지합니다.')}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}], 'gateways': [],
            'sequences': [{'id': 's1', 'source': 'start', 'target': 'answer'}, {'id': 's2', 'source': 'answer', 'target': 'end'}]}


def norm(v):
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def numbers_in(text):
    return [n.rstrip('.0') if '.' in n and float(n).is_integer() else n for n in re.findall(r'\d+(?:\.\d+)?', text or '')]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--only', default='')
    args = ap.parse_args(); out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    did = 'business-question-' + uuid.uuid4().hex[:8]
    report = {'scope': __doc__, 'definition_id': did, 'cases': {}, 'checks': {}}
    def save(): (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save()
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:260]), flush=True)
    raw = definition(did); (out / 'definition.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf8')
    code, body = http('/api/process/definitions', {'definition': raw}); assert code == 201, (code, body)
    with psycopg.connect(DSN) as c:
        for q in QUESTIONS:
            q['expected'] = [norm(v) for v in c.execute(q['truth']).fetchone()]
    for q in QUESTIONS:
        if args.only and q['key'] not in args.only.split(','):
            continue
        code, body = http('/api/instances/start', {'definition_id': did, 'version': '1', 'event_id': did + '-' + q['key'],
                                                   'variables': {'question': q['question']}})
        assert code == 200, (code, body)
        pid = body['proc_inst_id']; t0 = time.monotonic(); print(q['key'], 'instance', pid, flush=True)
        until = time.monotonic() + 900
        while time.monotonic() < until:
            code, view = http('/api/instances/' + pid); assert code == 200, (code, view)
            wi = view['workitems'][0]
            if view['instance']['status'] == 'COMPLETED' or wi.get('draft_status') in ('FAILED', 'HUMAN_ASKED') or wi['status'] == 'PENDING':
                break
            time.sleep(3)
        elapsed = round(time.monotonic() - t0, 1)
        (out / f"{q['key']}-instance.json").write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding='utf8')
        starts = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_started']
        ends = [e['data'] for e in view['events'] if e['event_type'] == 'tool_usage_finished']
        tools = [e.get('tool') for e in starts]
        def tool_is(name, *wanted): return any(name == w or name == 'mcp__' + w.replace('/', '__') for w in wanted)
        def envelope(out):
            # Codex path: {'content','structured_content'}; Claude Code path: the JSON text of the tool result
            if isinstance(out, dict):
                return out.get('structured_content') or out
            try:
                return json.loads(out) if isinstance(out, str) else None
            except ValueError:
                return None
        queries = [env for env in (envelope(e.get('output')) for e in ends if tool_is(e.get('tool'), 'enterprise/query')) if isinstance(env, dict)]
        good = [x for x in queries if x.get('result') == 'ok']
        def canon(sql): return re.sub(r'\s+', ' ', re.sub(r'\s+limit\s+\d+\s*;?\s*$', '', (sql or '').strip().rstrip(';'), flags=re.I)).strip().lower()
        output = wi.get('output') or {}
        case = dict(instance=pid, status=wi['status'], elapsed_s=elapsed, expected=q['expected'], output=output, tools=tools,
                    executed=[x.get('document', {}).get('statement') or x.get('statement') for x in queries],
                    rejected=[x.get('message') for x in queries if x.get('result') != 'ok'])
        report['cases'][q['key']] = case; save()
        for src in (ROOT / '.evidence/workspace/hyd' / wi['id']).glob('*.events.jsonl'):
            shutil.copy2(src, out / f"{q['key']}-{src.name}")
        check(f"{q['key']}_completed_without_human_help", wi['status'] == 'DONE' and view['instance']['status'] == 'COMPLETED', dict(status=wi['status'], draft=wi.get('draft_status'), elapsed=elapsed))
        check(f"{q['key']}_read_metadata_before_querying", any(tool_is(t, 'enterprise/describe_catalog', 'enterprise/describe_schema') for t in tools) and any(tool_is(t, 'enterprise/query') for t in tools), tools[:8])
        answer_text = json.dumps([output.get('answer'), output.get('values')], ensure_ascii=False)
        def found(text, i, v):
            tol = (q.get('tolerance') or {}).get(i)
            return v in text if tol is None else any(abs(float(n) - float(v)) <= tol for n in re.findall(r'-?\d+(?:\.\d+)?', text))
        check(f"{q['key']}_answer_matches_direct_sql", all(found(answer_text, i, v) for i, v in enumerate(q['expected'])), dict(expected=q['expected'], answer=output.get('answer'), values=output.get('values')))
        stmts = [s for s in case['executed'] if s]
        reported = (output.get('sql') or '').strip().rstrip(';')
        rows_text = json.dumps([g.get('document', {}).get('rows') for g in good], ensure_ascii=False)
        check(f"{q['key']}_answer_values_came_from_an_executed_query", bool(good) and all(found(rows_text, i, v) for i, v in enumerate(q['expected'])), dict(executed_ok=[(g.get('document') or {}).get('statement', '')[:120] for g in good]))
        try:   # the enterprise MCP executes guard()'s normalized form (e.g. now() → CURRENT_TIMESTAMP); compare like with like
            reported_norm = guard(reported)
        except Exception:  # noqa: BLE001
            reported_norm = reported
        check(f"{q['key']}_reported_sql_is_one_it_executed", bool(good) and any(canon(reported_norm) == canon((g.get('document') or {}).get('statement')) for g in good), dict(reported=reported[:160], executed_ok=[(g.get('document') or {}).get('statement', '')[:120] for g in good]))
        used = {t.split('.')[-1].strip('"').lower() for t in (output.get('tables') or []) if isinstance(t, str)}
        check(f"{q['key']}_named_the_right_tables", q['expect_tables'] <= used, dict(used=sorted(used), expected=sorted(q['expect_tables'])))
        check(f"{q['key']}_no_rejected_or_write_queries", not case['rejected'], case['rejected'][:2])
    passed = sum(c['passed'] for c in report['checks'].values()); total = len(report['checks'])
    print(f"checks passed {passed}/{total}", flush=True)
    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
