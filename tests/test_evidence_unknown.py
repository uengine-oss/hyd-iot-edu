import pytest

from agentsvc import card, guardrail
from dmn_mcp import tools as dmn
from test_dmn_mcp import FakeKG, FakeTSDB


@pytest.mark.parametrize('result', [{}, {'value': None, 'passed': False}, {'value': None, 'passed': False, 'error': 'source unavailable'}])
def test_missing_evidence_remains_unknown_through_rank_and_card(result):
    rows = FakeKG().t1_causes('X', 'A')[:1]
    ranked = card.rank_causes(rows, {'ev:ce-high': result})
    evidence = ranked[0]['evidence'][0]
    assert evidence['passed'] is None and evidence['status'] == 'UNKNOWN'
    if 'error' in result:
        assert evidence['error'] == result['error']
    assert ranked[0]['score'] is None
    guide = card.build_card(None, {'asset': 'A', 'pattern': 'X'}, ranked, {}, {'ok': True})
    assert guide['withheld'] and guide['topCause'] is None and guide['recommended'] == []
    assert guardrail.check(guide)


def test_unknown_alternative_prevents_presenting_known_candidate_as_winner(monkeypatch):
    monkeypatch.setattr(dmn.mcp_prom, 'freshness', lambda *_: {'ok': True})
    db = FakeTSDB()
    db.evaluate = lambda *_: {'ev:ce-high': {'value': 91, 'passed': True},
                             'ev:ambient': {'value': None, 'passed': None, 'status': 'UNKNOWN', 'error': 'query failed'}}
    kg = FakeKG()
    result = dmn.DmnTools(kg, db).diagnose('A', 'X')
    assert result['withheld'] and result['top_cause'] is None and result['card'] is None
    assert result['evidence_status']['unknown'] == ['ev:ambient']
    assert not any(call[0] == 't2' for call in kg.calls)


def test_all_disproven_does_not_recommend_first_candidate(monkeypatch):
    monkeypatch.setattr(dmn.mcp_prom, 'freshness', lambda *_: {'ok': True})
    db = FakeTSDB()
    db.evaluate = lambda evidence, _: {e['id']: dict(value=0, passed=False, status='FAIL') for e in evidence}
    result = dmn.DmnTools(FakeKG(), db).diagnose('A', 'X')
    assert result['withheld'] and result['evidence_status']['status'] == 'UNSUPPORTED'


def test_manual_source_failure_never_reaches_decision_engine(monkeypatch):
    from agentsvc import main
    from fastapi import HTTPException
    def broken(*_):raise OSError('source unavailable')
    monkeypatch.setattr(main.tsdb, 'evaluate', broken)
    monkeypatch.setattr(main.decidelib, 'decide', lambda *a, **kw: pytest.fail('unverified cause reached decision engine'))
    with pytest.raises(HTTPException) as caught:
        main._manual_decide(FakeKG(), main.DecideReq(asset='A', pattern='X'))
    assert caught.value.status_code == 503


def test_manual_override_does_not_bypass_unknown_evidence(monkeypatch):
    from agentsvc import main
    from fastapi import HTTPException
    monkeypatch.setattr(main.tsdb, 'evaluate', lambda *_: {})
    monkeypatch.setattr(main.decidelib, 'decide', lambda *a, **kw: pytest.fail('override bypassed unknown source'))
    with pytest.raises(HTTPException) as caught:
        main._manual_decide(FakeKG(), main.DecideReq(asset='A', pattern='X', facts={'cause':'cause:cooler-fin-fouling'}))
    assert caught.value.status_code == 409


def test_legacy_pipeline_stops_before_action_lookup_and_submission(monkeypatch):
    from agentsvc import main
    from agentsvc.runs import Run
    kg = FakeKG()
    monkeypatch.setattr(main, 'kg', kg)
    monkeypatch.setattr(main.decidelib, '_get_json', lambda *_: {'route': 'response'})
    monkeypatch.setattr(main.mcp_prom, 'freshness', lambda *_: {'ok': True})
    monkeypatch.setattr(main.tsdb, 'evaluate', lambda *_: {})
    monkeypatch.setattr(main, 'submit_card', lambda *_: pytest.fail('unknown card submitted'))
    run = Run('fixture', 'fixture-alert', 'A', {'asset':'A','pattern':'X'})
    main.pipeline(run)
    assert run.status == 'WITHHELD' and run.incident_id is None
    assert run.card['withheld'] and run.card['recommended'] == []
    assert not any(call[0] == 't2' for call in kg.calls)


def test_guardrail_rejects_explicit_unknown_even_without_withheld_flag():
    from copy import deepcopy
    from test_guardrail import GOOD
    guide = deepcopy(GOOD)
    guide['causes'][0]['evidence'][0].update(passed=None, status='UNKNOWN')
    assert any('unknown' in error for error in guardrail.check(guide))
