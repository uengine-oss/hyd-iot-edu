"""Unknown alarms must remain observable without borrowing another fault's recovery."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest
from fastapi import HTTPException

from procsvc import alert_policy, definition, engine, instance_mode, machine
from procsvc.definition_registry import validate_definition
from procsvc.store import Store
from test_instance_mode import world, ALERT, DEFS, NoFx

NOW = datetime(2026,10,4,tzinfo=timezone.utc)


@pytest.mark.parametrize('pattern',[None,'UNRECOGNIZED','OVERHEAT_TRIP','LOW_PRESSURE_TRIP','HIGH_VIBRATION_TRIP','PLC_TRIP'])
def test_unknown_alarm_is_human_review_with_raw_source_and_no_effects(world,pattern):
    rt=world['rt'];alert=dict(ALERT,pattern=pattern,evidence={'trip':'RAW_PLC_CAUSE'})
    inst=rt.on_alert_raise(alert);inc=next(iter(world['incidents'].values()))
    assert (inst['proc_def_id'],inst['proc_def_version'])==('alert_triage','1.0')
    assert inc.state=='ESCALATED' and inc.recovery is None and inc.cmd_id is None
    assert inc.reason=='UNSUPPORTED_ALERT_PATTERN' and inc.card['alert']==alert
    rows=rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])
    task=next(w for w in rows if w['status']=='IN_PROGRESS')
    assert task['activity_id']=='task:triage' and not task.get('agent_orch') and not task.get('agent_mode')
    assert rt.workitem_view(task['id'])['inputs']['alert']==alert
    assert rt.on_alert_raise(alert) is None and len(world['incidents'])==1
    with pytest.raises(ValueError):rt.hooks.update_incident_card(inc.id,{'recommended':[{'code':'RESET'}]})
    with pytest.raises(ValueError):machine.on_approve(inc,'manager',[{'code':'RESET'}],NOW,NoFx())
    machine.on_alert(inc,dict(alert,state='CLEAR'),NoFx())
    result=rt.submit(task['id'],{'note':'원문 사유 확인. 현장 격리 후 별도 조사.'},'현장검토자')
    assert result['instance']['end_event']=='ev:review-recorded'
    assert result['instance']['status']=='COMPLETED' and inc.state=='ESCALATED'
    assert not inc.cmd_id and not inc.work_order and not world['executed']


def test_recovery_snapshot_survives_new_definition_and_store_restart(world,tmp_path):
    rt=world['rt'];rt.on_alert_raise(ALERT);inc=next(iter(world['incidents'].values()))
    changed=deepcopy(rt.defn.raw);changed['version']='2.2-test'
    changed['alertPolicy']['patterns']['COOLER_DEGRADATION']['limit']=99
    rt.register_definition(changed)
    saved=Store(tmp_path/'state.db');saved.save(world['incidents'],{},[])
    restored,_,_=saved.restore();other=restored[inc.id]
    assert other.recovery==('TS1','<',55) and other.recovery_policy['version']=='2.2'   # A116: runtime default definition 2.2
    other.state='RE_OBSERVING';other.cleared=True
    machine.on_timer(other,'reobs',NOW,80,NoFx())
    assert other.state=='ESCALATED' and other.work_order is None


def test_triage_projects_original_incident_before_instance_and_on_orphan_replay(world):
    from procsvc import main
    records=[]
    world['ctx'].record_incident=lambda inc: records.append(main._incident_params(inc))
    alert=dict(ALERT,pattern='LOW_PRESSURE_TRIP',evidence={'trip':'LOW_PRESSURE','raw':[1,2]})
    inst=world['rt'].on_alert_raise(alert)
    inc=next(iter(world['incidents'].values()))
    assert len(records)==1 and records[0]['id']==inc.id
    assert records[0]['pattern']=='LOW_PRESSURE_TRIP' and records[0]['trip']=='LOW_PRESSURE'
    assert json.loads(records[0]['source_alert'])==alert
    assert world['cypher'][0]['incident']==records[0]['id']
    assert inc.state=='ESCALATED' and inc.cmd_id is None
    # Replay of a persisted Incident before its PG instance existed repairs its graph source too.
    assert world['rt'].hooks.new_incident(alert)=={'id':inc.id}
    assert len(records)==2 and records[1]==records[0] and len(world['incidents'])==1


def test_new_explicit_pattern_uses_definition_criterion_without_machine_change(world):
    rt=world['rt'];raw=deepcopy(rt.defn.raw);raw['version']='custom-pattern-test'
    raw['alertPolicy']['patterns']['CUSTOM_FILTER_PRESSURE']={'tag':'FILTER_DP','op':'<','limit':7,'requireClear':True}
    rt.register_definition(raw)
    inst=rt.start_definition(raw['processDefinitionId'],raw['version'],'custom',
         alert=dict(ALERT,alertId='custom',pattern='CUSTOM_FILTER_PRESSURE'))
    inc=world['incidents'][engine.variables(inst)['incident']]
    assert inc.recovery==('FILTER_DP','<',7)
    inc.state='RE_OBSERVING';inc.cleared=True
    machine.on_timer(inc,'reobs',NOW,6,NoFx())
    assert inc.state=='RESOLVED' and inc.work_order is None


@pytest.mark.parametrize('state',['AWAITING_APPROVAL','RE_OBSERVING'])
def test_old_unknown_incident_cannot_recover_from_cool_sensor(state):
    inc=machine.Incident('old','HYD-01','unknown',{'alert':dict(ALERT,pattern='UNKNOWN')},state=state)
    inc.alert_id=inc.card['alert']['alertId']
    machine.on_alert(inc,dict(inc.card['alert'],state='CLEAR'),NoFx())
    machine.on_timer(inc,'reobs',NOW,35,NoFx())
    assert inc.state=='ESCALATED' and not inc.work_order and not inc.cmd_id


def test_agent_cannot_replace_alarm_source(world):
    rt=world['rt'];rt.on_alert_raise(ALERT);inc=next(iter(world['incidents'].values()))
    with pytest.raises(ValueError,match='원천'):
        rt.hooks.update_incident_card(inc.id,{'alert':dict(ALERT,pattern='FAN_VIBRATION')})
    assert inc.pattern=='COOLER_DEGRADATION'
    card={'alert':dict(ALERT,evidence={'invented':True}),'recommended':[]}
    rt.hooks.update_incident_card(inc.id,card)
    assert inc.card['alert']==ALERT


def test_late_http_guide_or_decision_cannot_upgrade_triage(world,monkeypatch):
    from procsvc import main
    rt=world['rt'];alert=dict(ALERT,pattern='LOW_PRESSURE_TRIP')
    inst=rt.on_alert_raise(alert);inc=next(iter(world['incidents'].values()))
    monkeypatch.setattr(main,'incidents',world['incidents']);monkeypatch.setattr(main,'book',{})
    result=asyncio.run(main.create_incident({'alert':alert,'recommended':[{'code':'RESET'}]}))
    assert result['duplicate'] and result['state']=='ESCALATED' and len(world['incidents'])==1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.create_decision({'id':'late','asset':inc.asset,'origin':{'incident':inc.id},'options':[{'id':'reset'}]}))
    assert exc.value.status_code==409 and not main.book and not inc.card['recommended']


@pytest.mark.parametrize('change',[{'op':'=='},{'limit':float('nan')},{'limit':True},{'requireClear':False},{'tag':''}])
def test_invalid_recovery_contract_is_rejected(change):
    raw=json.loads((DEFS/'anomaly_response_v21.json').read_text(encoding='utf-8'))
    raw['alertPolicy']['patterns']['COOLER_DEGRADATION'].update(change)
    with pytest.raises(ValueError):validate_definition(raw)


def test_unsupported_cannot_use_normal_service_workflow_as_fallback(world):
    rt=world['rt'];raw=deepcopy(rt.defn.raw);raw['version']='unsafe-fallback-test'
    raw['alertPolicy']['unsupported']={'definition':raw['processDefinitionId'],'version':raw['version']}
    rt.register_definition(raw)
    with pytest.raises(ValueError,match='사람 검토'):
        rt.start_definition(raw['processDefinitionId'],raw['version'],'unsafe',alert=dict(ALERT,pattern='UNKNOWN'))
    assert not world['incidents'] and not world['executed']
