"""Lossless bounded evidence access, separate from current-state evaluation."""
import hashlib
import json

import pytest

from dmn_mcp.tools import DmnTools, enveloped
from test_dmn_mcp import FakeKG, FakeTSDB
from test_purchase_part_route import part_pipeline
from test_purchase_candidate_scope import pipeline


def record():
    return dict(id='EVAL-test', created='2026-10-27T00:00:00Z', status='EVALUATED',
                provenance=[dict(source='TSDB', error='관측 없음')], recommended='skill:a',
                result=dict(options=[dict(id='skill:a', sopId='SOP-A',
                    rankingEvidence={'한글': ['원문 "\\\n' * 3000, '마지막 승인 제한']}, steps=['조치 전 확인'])]))


def test_every_character_retrievable_from_frozen_evaluation_without_recalculation():
    tools = DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    rec = record()
    expected = json.dumps(rec['result']['options'][0]['rankingEvidence'], ensure_ascii=False)
    view = tools._evaluation_view(rec)
    rec['result']['options'][0]['rankingEvidence'] = '현재 값으로 변경'
    offset, chunks = 0, []
    while offset is not None:
        page = tools.read_evaluation_evidence(view['evidence_ref'], 'SOP-A', 'rankingEvidence', offset)
        assert len(json.dumps(page, ensure_ascii=False)) < 20000
        assert page['evaluation_id'] == view['id'] and page['evaluated_at'] == rec['created']
        assert page['sha256'] == hashlib.sha256(expected.encode()).hexdigest()
        chunks.append(page['content'])
        offset = page['next_offset']
    assert ''.join(chunks) == expected
    assert json.loads(''.join(chunks))['한글'][-1] == '마지막 승인 제한'
    assert tools.kg.calls == []


@pytest.mark.parametrize('change', [
    {'evidence_ref': 'EVAL-test'}, {'evidence_ref': 'another-student'}, {'option': 'SOP-MISSING'},
    {'field': 'secret'}, {'offset': -1}, {'offset': True}, {'offset': 1000000},
])
def test_invalid_access_is_explicit_error(change):
    tools = DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    view = tools._evaluation_view(record())
    args = dict(evidence_ref=view['evidence_ref'], option='SOP-A', field='steps', offset=0)
    args.update(change)
    assert enveloped(tools.read_evaluation_evidence)(**args)['result'] == 'error'


def test_expired_and_evicted_evidence_never_falls_back_to_current_state(monkeypatch):
    import time
    tools = DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    now = time.monotonic()
    monkeypatch.setattr(time, 'monotonic', lambda: now)
    first = tools._evaluation_view(record())
    for _ in range(64):
        latest = tools._evaluation_view(record())
    assert len(tools._evidence) == 64
    for token in (first['evidence_ref'],):
        with pytest.raises(ValueError, match='만료'):
            tools.read_evaluation_evidence(token, 'SOP-A', 'steps')
    monkeypatch.setattr(time, 'monotonic', lambda: now + 600)
    with pytest.raises(ValueError, match='만료'):
        tools.read_evaluation_evidence(latest['evidence_ref'], 'SOP-A', 'steps')


def test_purchase_route_exposes_evidence_without_second_evaluation(part_pipeline):
    tools, _, facts, _, _, submitted = part_pipeline
    view = tools.evaluate_purchase('HYD-03', 'P-KIT')
    facts['spare_gap'] = -999
    page = tools.read_evaluation_evidence(view['evidence_ref'], 'skill:purchase', 'steps')
    assert page['evaluation_id'] == view['id'] and page['next_offset'] is None
    assert submitted == []
    assert json.loads(page['content'])


def test_mcp_wire_exposes_read_only_continuation(monkeypatch):
    import asyncio
    from fastmcp import Client
    from dmn_mcp import server
    tools = DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    monkeypatch.setattr(server, 'tools', tools)
    view = tools._evaluation_view(record())
    async def run():
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            tool = next(t for t in listing if t.name == 'read_evaluation_evidence')
            assert tool.annotations.readOnlyHint
            reply = await client.call_tool(tool.name, dict(evidence_ref=view['evidence_ref'], option='SOP-A', field='rankingEvidence'))
            result = json.loads(next(c.text for c in reply.content if c.type == 'text'))
            assert result['result'] == 'ok'
            assert result['document']['next_offset'] == 4000
            assert len(json.dumps(result, ensure_ascii=False)) < 20000
    asyncio.run(run())


def test_large_summary_is_rejected_instead_of_unbounded_agent_output():
    tools = DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    rec = record()
    rec['facts'] = {'large': '큰 값' * 10000}
    with pytest.raises(ValueError, match='응답 한도'):
        tools._evaluation_view(rec)


def test_pm_source_rows_do_not_overflow_list_and_are_losslessly_available():
    tools = DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    rec = record()
    rec['facts'] = {'hours_at_next_window': 1951, 'pm_context': {
        'records': [{'asset': 'HYD-'+str(i), 'note': '원천 점검 기록'*200} for i in range(20)],
        'parts': [{'part_no':'P-SEAL', 'on_hand':3, 'reserved':2}]}}
    plan = {'scope':'single', 'parts_totals':[{'part_no':'P-SEAL','qty':1,'available':1}],
            'staffing':{'confirmed':False}}
    rec['result']['options'][0]['maintenancePlan'] = plan
    rec['result']['options'][0]['facts'] = {'target_hours':1951}
    expected = json.dumps(rec['facts'], ensure_ascii=False)
    view = tools._evaluation_view(rec)
    assert len(json.dumps(view, ensure_ascii=False)) < 20000
    assert view['facts']['hours_at_next_window'] == 1951
    assert 'pm_context' not in view['facts']
    assert view['facts_omitted'] == ['pm_context'] and 'option=null' in view['facts_detail']
    assert view['options'][0]['maintenancePlan'] == plan
    rec['facts']['pm_context']['parts'].clear()
    chunks, offset = [], 0
    while offset is not None:
        page=tools.read_evaluation_evidence(view['evidence_ref'],None,'facts',offset)
        chunks.append(page['content']); offset=page['next_offset']
    assert ''.join(chunks) == expected
    assert json.loads(tools.read_evaluation_evidence(view['evidence_ref'],'SOP-A','facts')['content']) == {'target_hours':1951}
    assert tools.kg.calls == []
