from copy import deepcopy
from types import SimpleNamespace

import pytest

from procsvc import mcp_check, mcp_registry, mcp_secrets
from procsvc.classroom_read_tools import ReadRouter


@pytest.fixture
def local(monkeypatch):
    entries={'enterprise':{'url':'http://student-enterprise/mcp','type':'streamable_http'}}
    monkeypatch.setattr(mcp_registry,'store_for',lambda repo:SimpleNamespace(servers=lambda tenant:deepcopy(entries)))
    monkeypatch.setattr(mcp_secrets,'runtime_spec',lambda *args:(args[-1],[]))
    calls=[]
    def call(spec,tool,args,**kw):
        calls.append((spec,tool,args,kw))
        return {'status':'ok','result':{'text':'{"available":7}', 'json':True,'is_error':False,'truncated':False}}
    monkeypatch.setattr(mcp_check,'call',call)
    return entries,calls,ReadRouter(object(),'student-1',['enterprise/spare_stock'])


def test_reads_current_registered_student_endpoint(local):
    entries,calls,router=local
    assert router('enterprise/spare_stock',{'part':'P-PMP-SEAL'})=={'is_error':False,'result':{'available':7}}
    assert calls[0][0]['url']=='http://student-enterprise/mcp'
    assert calls[0][0]['transport']=='streamable_http'
    assert calls[0][1:3]==('spare_stock',{'part':'P-PMP-SEAL'})
    assert calls[0][3]['max_chars']==32000
    entries['enterprise']['url']='http://different-host/mcp'
    assert router('enterprise/spare_stock',{})['is_error']
    assert len(calls)==1


def test_base_stdio_configuration_is_normalized_before_call(local):
    entries,calls,_=local
    entries['neo4j']={'command':'uvx','args':['mcp-neo4j-cypher'],'env':{'NEO4J_URI':'bolt://student:7687'}}
    router=ReadRouter(object(),'student-1',['neo4j/read_neo4j_cypher'])
    assert not router('neo4j/read_neo4j_cypher',{'query':'RETURN 1'})['is_error']
    assert calls[0][0]['transport']=='stdio'
    assert calls[0][0]['command']=='uvx'


def test_unknown_or_write_tool_cannot_be_selected_by_queue(local):
    _,calls,router=local
    assert router('enterprise/PR_CREATE',{})['is_error']
    assert router('http://arbitrary-host/tool',{})['is_error']
    assert not calls


@pytest.mark.parametrize('response',[
    {'status':'refused','error':'secret-value'},
    {'status':'failed','error':'secret-value'},
    {'status':'ok','result':{'truncated':True,'text':'partial'}},
    {'status':'ok','result':{'json':True,'text':'bad JSON'}},
])
def test_failure_or_partial_data_never_becomes_success(local,monkeypatch,response):
    _,_,router=local
    monkeypatch.setattr(mcp_check,'call',lambda *a,**kw:response)
    value=router('enterprise/spare_stock',{})
    assert value['is_error'] and 'secret-value' not in str(value)


def test_tool_error_and_json_array_are_preserved(local,monkeypatch):
    _,_,router=local
    monkeypatch.setattr(mcp_check,'call',lambda *a,**kw:{'status':'ok','result':{
        'text':'[{"status":"open"}]','json':True,'is_error':False,'truncated':False}})
    assert router('enterprise/spare_stock',{})=={'is_error':False,'result':[{'status':'open'}]}
    monkeypatch.setattr(mcp_check,'call',lambda *a,**kw:{'status':'ok','result':{
        'text':'{"error":"missing"}','json':True,'is_error':True,'truncated':False}})
    assert router('enterprise/spare_stock',{})=={'is_error':True,'result':{'error':'missing'}}


def test_custom_server_needs_matching_read_gate(local):
    entries,calls,_=local
    entries['custom']={'url':'http://student-custom/mcp'}
    router=ReadRouter(object(),'student-1',['custom/read_state'])
    assert router('custom/read_state',{})['is_error'] and not calls
