"""K1 real authoring/bundle APIs, no live stack or external service mutations."""
import json
from copy import deepcopy

import pytest

from procsvc import config_bundle, student_cases
from test_b6_config_bundle import env, http, build_student, ok, TOKEN, BEARER, SKILL, state


def tag(c, kind, aid, label):
    return c.put('/api/config/cases/tag', json={'kind':kind,'asset_id':aid,'label':label})


def skill(c):
    ok(c.post('/api/skills', json={'skill_name':'cooler-check','description':'쿨러 점검','content':SKILL}),201)


@pytest.mark.parametrize('bad',[None, [], '가'*61, '숨김\u0000문자', '한 줄\n다음 줄'])
def test_invalid_tag_does_not_change_saved_value(env,bad):
    skill(env)
    ok(tag(env,'skills','cooler-check','첫 사례'))
    assert tag(env,'skills','cooler-check',bad).status_code == 422
    assert env.get('/api/config/cases').json()['assets'][0]['label']=='첫 사례'


def test_tag_edit_remove_baseline_and_tenant_boundaries(env):
    skill(env)
    student_cases.Store(env.repo,'other').set('skills','cooler-check','다른 노트북')
    assert tag(env,'agents','sys:agent','덮어쓰기').status_code==404
    assert tag(env,'skills','missing','없는 자산').status_code==404
    ok(tag(env,'skills','cooler-check','  회의 준비  '))
    assert env.get('/api/config/cases').json()['labels']==['회의 준비']
    ok(tag(env,'skills','cooler-check','정비 준비'))
    assert env.get('/api/config/cases').json()['labels']==['정비 준비']
    ok(tag(env,'skills','cooler-check',''))
    assert env.get('/api/config/cases').json()['labels']==[]
    assert student_cases.Store(env.repo,'other').rows()[0]['label']=='다른 노트북'
    assert env.repo.get_skill('hyd','fan-vibration-check')


def test_selected_case_closes_dependencies_masks_secrets_and_roundtrips(env,http):
    c=env
    ids=build_student(c,http)
    ok(tag(c,'flows','my_cooler','쿨러 사례'))
    ok(tag(c,'agents',ids['a2'],'다른 사례'))
    out=ok(c.get('/api/config/export',params={'case':'쿨러 사례'}))
    assert {f['definition_id'] for f in out['content']['flows']}=={'my_cooler'}
    assert {a['id'] for a in out['content']['agents']}=={ids['a1']}
    assert {s['skill_name'] for s in out['content']['skills']}=={'cooler-check'}
    assert {s['name'] for s in out['content']['mcp_servers']}=={'my-fake','my-http'}
    assert out['case_selection']['direct_count']==1 and out['case_selection']['dependency_count']==4
    assert TOKEN not in json.dumps(out) and BEARER not in json.dumps(out)
    assert out['case_tags']==[{'kind':'flows','asset_id':'my_cooler','label':'쿨러 사례'}]
    secrets={'my-fake':{'env.FAKE_TOKEN':TOKEN},'my-http':{'headers.Authorization':'Bearer '+BEARER}}
    ok(c.post('/api/config/reset',json={}))
    assert student_cases.Store(c.repo,'hyd').rows()==[]
    result=ok(c.post('/api/config/import',json={'bundle':out,'secrets':secrets}))
    assert result['verified']
    again=ok(c.get('/api/config/export'))
    assert again['content']==out['content']
    assert again['case_tags']==out['case_tags']
    assert c.get('/api/config/export',params={'case':'다른 사례'}).status_code==404


def test_whole_bundle_labels_restore_on_import_failure_and_bad_label_rejects_before_reset(env,monkeypatch):
    skill(env)
    ok(tag(env,'skills','cooler-check','보존 사례'))
    before=ok(env.get('/api/config/export'))
    bad=deepcopy(before);bad['case_tags'][0]['asset_id']='missing'
    assert env.post('/api/config/import',json={'bundle':bad}).status_code==422
    assert ok(env.get('/api/config/export'))['case_tags']==before['case_tags']
    original=config_bundle._apply
    count=0
    def fail_once(*args):
        nonlocal count
        count+=1
        if count==1: raise config_bundle._StepFailed('skills','시험 저장 실패',[],[])
        return original(*args)
    monkeypatch.setattr(config_bundle,'_apply',fail_once)
    result=env.post('/api/config/import',json={'bundle':before})
    assert result.status_code==422 and result.json()['detail']['rolled_back']
    assert ok(env.get('/api/config/export'))['case_tags']==before['case_tags']
    assert env.repo.get_skill('hyd','cooler-check')['content']==SKILL


def test_single_asset_deletion_removes_tags_and_reused_names_start_untagged(env,http):
    ids=build_student(env,http)
    targets=[('flows','oil_check','/api/flows/oil_check'),('agents',ids['a2'],'/api/agents/'+ids['a2']),
             ('skills','cooler-check','/api/skills/cooler-check'),('mcp_servers','my-http','/api/mcp/servers/my-http?force=true')]
    for kind,aid,url in targets:
        ok(tag(env,kind,aid,'삭제 시험'))
        ok(env.delete(url))
        assert not any(r['kind']==kind and r['asset_id']==aid for r in student_cases.Store(env.repo,'hyd').rows())
    skill(env)
    row=next(r for r in env.get('/api/config/cases').json()['assets'] if r['kind']=='skills')
    assert row['label']==''


def test_optional_postgres_label_store_transaction_and_tenant_cleanup():
    import os
    from uuid import uuid4
    from procsvc import procdb
    dsn=os.getenv('HYD_BACKEND_PG_DSN')
    if not dsn: pytest.skip('HYD_BACKEND_PG_DSN must be a disposable migrated database')
    repo=procdb.PgRepo(dsn);tenant='case-test-'+uuid4().hex
    with repo._conn() as cx: cx.execute('insert into tenants(id,name) values (%s,%s)',(tenant,'사례 저장 시험'))
    try:
        store=student_cases.Store(repo,tenant)
        store.set('skills','one','첫 사례')
        assert student_cases.Store(procdb.PgRepo(dsn),tenant).rows()==[{'kind':'skills','asset_id':'one','label':'첫 사례'}]
        with pytest.raises(Exception): store.replace([{'kind':'skills','asset_id':'one','label':'바뀜'},{'kind':'invalid','asset_id':'two','label':'실패'}])
        assert store.rows()[0]['label']=='첫 사례'
        store.remove('skills','one');assert store.rows()==[]
    finally:
        with repo._conn() as cx: cx.execute('delete from tenants where id=%s',(tenant,))


def test_prose_names_ids_and_arguments_do_not_pull_other_cases_into_export(env):
    # Minimal bundle graph isolates the dependency contract from registration.
    content={'mcp_servers':[{'name':'calendar','description':'다른 사례 서버','secrets':[]}],
             'skills':[{'skill_name':'local','description':'calendar','content':'calendar'}, {'skill_name':'unrelated','description':'다른 스킬','content':'calendar'}],
             'agents':[{'id':'agent:a','name':'calendar','persona':'calendar','goal':'unrelated','tools':['neo4j'],'skills':['local']}],
             'flows':[{'definition_id':'calendar','versions':[], 'draft':{'mapping':{'name':'calendar','tasks':{'t':{'agent':'agent:a','instruction':'calendar','description':'unrelated','config':{'arguments':{'server':'calendar'}}}}}}}],
             'assignments':[],'role_members':[],'deployments':{'flows':[],'reference':None}}
    bundle={'content':content,'case_tags':[{'kind':'flows','asset_id':'calendar','label':'내 사례'}]}
    out=student_cases.select_bundle(env.rt,bundle,'내 사례')
    assert out['content']['mcp_servers']==[]
    assert [r['skill_name'] for r in out['content']['skills']]==['local']
    assert out['case_selection']['dependency_count']==2
    # Declaring that same server in the actual service field does include it.
    content['flows'][0]['draft']['mapping']['tasks']['t']['config']['server']='calendar'
    connected=student_cases.select_bundle(env.rt,bundle,'내 사례')
    assert [r['name'] for r in connected['content']['mcp_servers']]==['calendar']


@pytest.mark.parametrize('compiled',[False,True])
def test_mail_delivery_dependency_is_exported_but_argument_names_are_not(env,compiled):
    content={'mcp_servers':[{'name':n,'secrets':[]} for n in ('mailbox','unrelated')],
             'skills':[],'agents':[], 'flows':[{'definition_id':'mail-flow','versions':[],
             'draft':{'mapping':{'tasks':{'send':{'config':{'mail':{'server':'mailbox','tool':'send_mail','arguments':{'server':'unrelated'}}}}}}}}],
             'assignments':[],'role_members':[],'deployments':{'flows':[],'reference':None}}
    if compiled:
        content['flows'][0].update(draft=None,versions=[{'version':'1'}])
        env.repo.upsert_proc_def({'processDefinitionId':'mail-flow','version':'1','activities':[{'service':{'mail':{'server':'mailbox','arguments':{'server':'unrelated'}}}}]})
    bundle={'content':content,'case_tags':[{'kind':'flows','asset_id':'mail-flow','label':'메일 사례'}]}
    out=student_cases.select_bundle(env.rt,bundle,'메일 사례')
    assert [r['name'] for r in out['content']['mcp_servers']]==['mailbox']


def test_query_credentials_are_masked_in_whole_and_case_export_and_required_on_import(env,http):
    from urllib.parse import parse_qsl,urlsplit
    canary='CANARY&=한글+/?'
    from urllib.parse import quote
    original=http+'?view=a%20b&token='+quote(canary,safe='')+'&token=SECOND_CANARY&empty=&page=2'
    ok(env.post('/api/mcp/servers',json={'name':'query-mail','transport':'streamable_http','url':original}),201)
    ok(tag(env,'mcp_servers','query-mail','비밀 시험'))
    for params in ({},{'case':'비밀 시험'}):
        bundle=ok(env.get('/api/config/export',params=params))
        serialized=json.dumps(bundle)
        assert 'CANARY' not in serialized and quote(canary,safe='') not in serialized
        item=bundle['content']['mcp_servers'][0]
        assert item['url'].endswith('&empty=&page=2') and '?view=a%20b&' in item['url']
        assert {s['slot'] for s in item['secrets']}=={'url.query.1','url.query.2'}
        before=state(env)
        failed=env.post('/api/config/import',json={'bundle':bundle})
        assert failed.status_code==422 and failed.json()['detail']['needs_secrets']
        assert state(env)==before
        values={'url.query.1':canary,'url.query.2':'SECOND_CANARY'}
        body=config_bundle.register_body(item,values)
        assert parse_qsl(urlsplit(body['url']).query,keep_blank_values=True)==parse_qsl(urlsplit(original).query,keep_blank_values=True)
        restored=ok(env.post('/api/config/import',json={'bundle':bundle,'secrets':{'query-mail':values}}))
        assert restored['verified']
        assert ok(env.get('/api/config/export'))['content']==bundle['content']
