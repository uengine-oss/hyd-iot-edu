"""Source identity is not Kafka delivery identity or the current default policy."""
from copy import deepcopy
import base64
from types import SimpleNamespace
import pytest
from procsvc.source_inbox import source_record, kafka_record


def test_redelivery_keeps_business_identity_but_retains_every_raw_payload():
    value={'asset':'HYD-02','alertId':'pressure-17','state':'RAISE','pattern':'LOW_PRESSURE_TRIP'}
    a=source_record('alerts',0,17,value)
    b=source_record('alerts',2,91,value)
    assert a['event_key']==b['event_key'] and a['payload_sha']==b['payload_sha']
    value['asset']='HYD-01'
    c=source_record('alerts',2,92,value)
    assert c['event_key']==a['event_key'] and c['semantic_sha']!=a['semantic_sha']
    assert a['payload']['asset']=='HYD-02'


def test_clear_is_distinct_from_raise_for_same_alarm():
    value={'asset':'HYD-02','alertId':'pressure-17','state':'RAISE'}
    raised=source_record('alerts',0,0,value)
    cleared=source_record('alerts',0,1,dict(value,state='CLEAR'))
    assert raised['event_key']!=cleared['event_key'] and cleared['kind']=='CLEAR'


def test_retained_ack_heartbeat_is_duplicate_but_contradictory_result_is_not():
    value={'asset':'HYD-02','cmdId':'cmd-1','result':'DONE','interlock':'PASS','t':'first','tags':{'PS1':182}}
    a=source_record('plant.status',0,0,value)
    b=source_record('plant.status',0,1,dict(value,t='later',tags={'PS1':181}))
    c=source_record('plant.status',0,2,dict(value,result='REJECTED'))
    assert a['kind']=='ACK' and a['event_key']==b['event_key']==c['event_key']
    assert a['semantic_sha']==b['semantic_sha'] and a['payload_sha']!=b['payload_sha']
    assert c['semantic_sha']!=a['semantic_sha']


@pytest.mark.parametrize('value',[{'_raw':'not JSON'}, {'asset':'HYD-02'}, {'asset':[], 'alertId':'x','state':'RAISE'}])
def test_invalid_alarm_remains_an_explicit_receipt(value):
    row=source_record('alerts',0,0,value)
    assert row['kind']=='INVALID' and row['error'] and row['payload']==value


@pytest.mark.parametrize('partition,offset',[(True,1),(0,False),(-1,0),(0,-1),(0,1.5)])
def test_invalid_kafka_coordinates_are_rejected(partition,offset):
    with pytest.raises(ValueError):source_record('alerts',partition,offset,{})


def test_status_heartbeats_have_delivery_identity():
    value={'asset':'HYD-03','state':'RUN'}
    a=source_record('plant.status',0,1,value);b=source_record('plant.status',0,2,value)
    assert a['kind']=='STATUS' and a['event_key']!=b['event_key']


@pytest.mark.parametrize('wire',[b'\xffinvalid',b'{broken',b'[1,2]',b'{"value":NaN}',b'',None])
def test_malformed_wire_or_tombstone_is_preserved_before_decoding(wire):
    row=kafka_record(SimpleNamespace(topic='alerts',partition=2,offset=9,value=wire))
    assert row['kind']=='INVALID'
    assert base64.b64decode(row['wire_base64'])==(wire or b'')
    assert row['wire_kind']==('tombstone' if wire is None else 'bytes')


def test_http_identity_does_not_invent_kafka_coordinates():
    value={'asset':'HYD-02','alertId':'http-test','state':'RAISE'}
    http=source_record('alerts',None,None,value,source='http')
    kafka=source_record('alerts',0,9,value)
    assert http['event_key']==kafka['event_key'] and http['delivery_key']!=kafka['delivery_key']
    assert http['partition_no'] is None and http['offset_no'] is None and http['wire_kind']=='decoded'


def test_instance_mode_refuses_a_memory_repo_with_a_clear_message():
    """A143 (remaining-sweep 14): PROCESS_MODE=instance + PROCESS_REPO=memory used to die at startup with
    AttributeError('MemoryRepo' object has no attribute '_conn') from latest_states (main.py startup). The inbox is
    PostgreSQL-only, so the refusal is explicit and names the setting to change."""
    from procsvc import procdb
    from procsvc.source_inbox import PgSourceInbox
    with pytest.raises(RuntimeError, match='PROCESS_REPO=pg'):
        PgSourceInbox(procdb.MemoryRepo(), 'hyd')
    class PgLike:                                    # the contract the inbox actually uses
        _local = SimpleNamespace(connection=None)
        def _conn(self): raise AssertionError('not called by the constructor')
    assert PgSourceInbox(PgLike(), 'hyd').tenant_id == 'hyd'
