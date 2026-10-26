from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from procsvc import main
from dmn_mcp.tools import agent_view


def test_same_task_concurrent_submission_and_changed_body(monkeypatch):
    book = {}
    monkeypatch.setattr(main, 'book', book)
    monkeypatch.setattr(main, '_audit', lambda *a, **kw: None)
    monkeypatch.setattr(main.instance_mode, 'bridge_legacy_agent', lambda d: None)
    base = {'asset': 'HYD-01', 'recommended': 's1', 'options': [{'id': 's1'}],
            'origin': {'process_scope': {'tenant': 't', 'instance': 'i', 'workitem': 'w', 'generation': 0, 'version': 'v'}}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(main._store_decision, [dict(deepcopy(base), id='a'), dict(deepcopy(base), id='b')]))
    assert len(book) == 1 and replies[0]['id'] == replies[1]['id']
    changed = dict(deepcopy(base), id='c', recommended='s2')
    with pytest.raises(HTTPException) as error:
        main._store_decision(changed)
    assert error.value.status_code == 409 and replies[0]['id'] in error.value.detail
    assert len(book) == 1
    changed['origin']['process_scope']['workitem'] = 'new-workitem'
    main._store_decision(changed)
    assert len(book) == 2


def test_fact_source_failure_remains_visible_in_summary_and_detail():
    provenance = [{'variable': 'spare_gap', 'source': 'sys:erp', 'error': 'ERP unavailable'},
                  {'variable': 'ts1', 'source': 'sen:ts1', 'value': 55}]
    rec = {'facts': {'spare_gap': None}, 'provenance': provenance,
           'result': {'options': [{'id': 's1'}]}}
    summary = agent_view(rec)
    assert summary['source_errors'] == [provenance[0]]
    assert 'provenance' not in summary
    assert agent_view(rec, 's1')['provenance'] == provenance
