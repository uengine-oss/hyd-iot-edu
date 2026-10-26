from pathlib import Path

from procsvc import manual_review, manual_graph, work_rules
from procsvc.manual_sources import ManualSources
from worker.settings import handover_allowed_tools, DEFAULT_ALLOWED_TOOLS
from test_inbox import rt

ROOT = Path(__file__).parents[1]
MANUAL = ROOT/'문서/시스템/참조/수업_문서_원문/HI-01_shift-inspection-supplement.md'


def test_supplement_is_three_reference_procedures_without_fault_or_execution_edges(tmp_path):
    archive = ManualSources(tmp_path/'manuals.sqlite3')
    old = archive.save('hyd', 'existing.txt', b'Existing approved document')
    source = archive.save('hyd', MANUAL.name, MANUAL.read_bytes())
    preview = manual_review.proposal(source)
    assert [p['id'] for p in preview['procedures']] == ['SOP-HI-01', 'SOP-HI-02', 'SOP-HI-03']
    assert [len(p['steps']) for p in preview['procedures']] == [4, 4, 4]
    preview.update(by='강사 검토', reviewed=True,
        links={p['id']: dict(kind='reference', executable=False) for p in preview['procedures']})
    plan = manual_review.validate(archive, 'hyd', preview)
    desired = manual_graph.desired(plan)
    assert all(p['failureMode'] is None and p['executable'] is False for p in plan['procedures'])
    assert {e['type'] for e in desired['edges']} <= {'PART_OF', 'HAS_STEP', 'REFERS_TO'}
    assert archive.get('hyd', old['source_id'])['sha256'] == old['sha256']
    assert archive.list('hyd')['total'] == 2


def test_handover_rules_do_not_allow_decision_submission_or_treat_arrivals_as_stock():
    text = work_rules.constitution(work_rules.rules_for('hyd-handover'))
    assert 'on_order' in text and 'on_hand' in text and '현재 상태로 재사용하지 않습니다' in text
    assert '선택할 카드의 제출만 허용' not in text
    tools = handover_allowed_tools(DEFAULT_ALLOWED_TOOLS.split(',')+['Bash', 'mcp__other__*'],
                                   ['neo4j', 'enterprise', 'hyd-dmn', 'other'])
    assert not any('*' in t or 'submit_decision' in t or 'other' in t for t in tools)
    assert 'Bash' not in tools and 'mcp__enterprise__query' in tools
    assert 'mcp__hyd-dmn__timeseries_query' in tools


def test_worker_applies_handover_contract_tool_limits_to_the_actual_request(rt, tmp_path):
    import json
    from test_handover import begin, unknown_draft
    from test_worker import TENANT_MCP, _settings, _fake_exec
    from worker.runner import Runner
    runtime, _ = rt
    begin(runtime)
    runtime.repo.upsert_tenant(dict(id='hyd', name='hyd', mcp=TENANT_MCP))
    agent = runtime.repo.list_users(['agent:handover'], 'hyd')[0]
    agent.update(work_rules='hyd-handover', tools='neo4j,enterprise,hyd-dmn')
    runtime.repo.upsert_user(agent)
    requests = []
    runner = Runner(_settings(tmp_path), runtime.repo,
        exec_fn=_fake_exec(json.dumps(unknown_draft()), requests=requests), schema_prompt='# schema', resolve_provider=lambda _: object())
    assert runner.poll_once() == 1
    assert requests
    args = requests[0][0].extra_args
    allowed = args[args.index('--allowedTools')+1]
    denied = args[args.index('--disallowedTools')+1]
    assert '*' not in allowed and 'submit_decision' not in allowed
    assert 'mcp__hyd-dmn__submit_decision' in denied
    # Exercise the runtime handoff too: Runner appends text/session metadata.
    assert runtime.poll_once() == 1
    workitems = runtime.repo.list_workitems(limit=None)
    assert any(w['activity_name']=='인계자 검토' and w['status']=='IN_PROGRESS' for w in workitems)
    assert not any((w.get('feedback') or {}).get('kind')=='validation' for w in workitems)
