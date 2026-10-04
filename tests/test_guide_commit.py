"""Actual MCP diagnostic cards omit event IDs; failed persistence must not mean DONE."""
from copy import deepcopy
import pytest
from test_instance_mode import world, ALERT
from test_instance_recovery import runtime
from test_instances import AGENT_OUTPUTS, NOW, _by


def test_partial_diagnostic_source_is_bound_to_existing_incident(world):
    rt=world['rt'];rt.on_alert_raise(ALERT);inc=next(iter(world['incidents'].values()))
    card={'incident':None,'alert':{'asset':ALERT['asset'],'pattern':ALERT['pattern']},
          'recommended':[{'code':'FAN_SET','kind':'command','param':'fan_pct','paramRange':[0,100]}]}
    rt.hooks.update_incident_card(inc.id,card)
    assert inc.card['alert']==ALERT and inc.card['incident']==inc.id
    assert inc.card['recommended']==card['recommended'] and inc.cmd_id is None


@pytest.mark.parametrize('bad',[{'alert':{'alertId':'another-event'}},
                              {'alert':{'asset':'HYD-03'}},
                              {'alert':{'pattern':'OTHER'}},
                              {'alert':{'alertId':None}},
                              {'incident':'another-incident'}])
def test_explicit_source_conflicts_do_not_replace_the_card(world,bad):
    rt=world['rt'];rt.on_alert_raise(ALERT);inc=next(iter(world['incidents'].values()))
    before=deepcopy(inc.card)
    with pytest.raises(ValueError):rt.hooks.update_incident_card(inc.id,bad)
    assert inc.card==before and inc.cmd_id is None


def test_missing_incident_is_not_a_successful_guide_update(world):
    with pytest.raises(ValueError):world['rt'].hooks.update_incident_card('not-an-incident',{'recommended':[]})


def test_guide_persist_failure_blocks_next_task_then_retries_original_output():
    rt,hooks,inst=runtime()
    wi,=rt.repo.fetch_pending_task('cliagents','worker')
    original=deepcopy(AGENT_OUTPUTS['task:diagnose'])
    rt.repo.save_task_result(wi['id'],original,True)
    def unavailable(*_):raise OSError('fixture guide store unavailable')
    hooks.update_incident_card=unavailable
    assert rt.poll_once(now=NOW)==1
    failed=rt.repo.get_workitem(wi['id'])
    assert failed['status']=='SUBMITTED' and failed['retry']==1 and failed['output']==original
    assert _by(rt,inst,'task:candidates')['status']=='TODO'
    assert 'TASK_COMPLETED' not in hooks.audits and not hooks.calls
    hooks.update_incident_card=lambda inc,card:hooks.cards.append((inc,deepcopy(card)))
    assert rt.poll_once(now=NOW)==1
    assert rt.repo.get_workitem(wi['id'])['status']=='DONE'
    assert _by(rt,inst,'task:candidates')['status']=='IN_PROGRESS'
    assert hooks.cards==[('INC-1003-01',original['guide_card'])]
