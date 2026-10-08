"""Actual archive/PG/API/Neo4j lifecycle with explicitly synthetic worker output.

Does not start Codex, claim extraction accuracy or issue any plant command.
Preserves originals/process records and rolls back only its own graph batch.
"""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from probe_definition_registry import http, ROOT, DSN
from procsvc.procdb import PgRepo


def main():
    tag=uuid.uuid4().hex[:10].upper()
    dest=ROOT/'.evidence/reaudit/a050-live'/tag;dest.mkdir(parents=True)
    checks=[]
    def save(name,value):(dest/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    def request(path,body=None):
        status,data=http(path,body);assert status==200,(status,data);return data
    text='벨트 정비 지침\n'+'일반 설명 문장입니다.\n'*900+'설비를 정지한 후 전원을 차단한다.\n벨트 균열을 확인하고 결과를 기록한다.\n'
    raw=text.encode()
    upload=request('/api/kg/manuals/preview',dict(filename='A050-'+tag+'.txt',data=base64.b64encode(raw).decode()))
    sid=upload['source_id'];root='/api/kg/manuals/sources/'+sid
    source=request(root);save('source',source)
    check('general prose is archived completely and structured parser proposes no SOP',not upload['procedures'] and source['pages'][0]['text']==text)
    rid=str(uuid.uuid4());inst=request(root+'/extractions',dict(request_id=rid));pid=inst['instance'];save('request',dict(source_id=sid,request_id=rid,instance=pid))
    check('same extraction request returns one existing instance',request(root+'/extractions',dict(request_id=rid))['instance']==pid)
    pending=request(root+'/extractions/'+pid)
    check('unexecuted extraction has no preview',pending['status']=='IN_PROGRESS' and pending['preview'] is None)
    other=request('/api/kg/manuals/preview',dict(filename='A050-other-'+tag+'.txt',data=base64.b64encode(b'other document').decode()))
    check('result cannot be attached to another source',http('/api/kg/manuals/sources/'+other['source_id']+'/extractions/'+pid)[0]==400)
    def anchor(quote):
        start=text.index(quote);return dict(source_id=sid,page=1,start=start,end=start+len(quote),quote=quote)
    sop='SOP-A050-'+tag
    proposal=dict(source_id=sid,sections=[dict(ref='section-1',title='벨트 정비 지침',excerpt=text,anchor=anchor('벨트 정비 지침'))],
        procedures=[dict(id=sop,name='벨트 점검',section='section-1',anchor=anchor('설비를 정지한 후 전원을 차단한다.'),steps=[
            dict(order=1,text='설비를 정지한 후 전원을 차단한다.',manual='section-1',anchor=anchor('설비를 정지한 후 전원을 차단한다.')),
            dict(order=2,text='벨트 균열을 확인하고 결과를 기록한다.',manual='section-1',anchor=anchor('벨트 균열을 확인하고 결과를 기록한다.'))])],
        page_reviews=[dict(page=1,note='[회귀 검사] 검사기가 직접 작성한 계약 검증용 제안. 실제 AI 추출 아님.')],warnings=['합성 작업 출력이며 에이전트 추출 정확도 근거가 아닙니다.'])
    save('synthetic-output',proposal)
    repo=PgRepo(DSN)
    rows=repo.fetch_pending_task('cliagents','a050-synthetic-contract-probe',tenant_id='hyd',proc_inst_id=pid)
    assert len(rows)==1
    wi=rows[0];check('full source tail is pinned in actual PG worker input',json.loads(wi['query'].split('[InputData]\n')[1])['manual_source']==source)
    assert repo.save_task_result(wi['id'],dict(proposal=proposal),final=True,expected_consumer=wi['consumer'])
    end=time.monotonic()+40
    while time.monotonic()<end:
        result=request(root+'/extractions/'+pid)
        if result['preview']:break
        time.sleep(1)
    else:raise TimeoutError(result)
    save('result',result);review=result['preview']
    check('actual engine produces cited preview without claimed CLI session',result['status']=='DONE' and review['extraction']['session_id'] is None)
    check('proposal alone cannot authorize graph commit',http('/api/kg/manuals/commit',review)[0]==400)
    review.update(reviewed=True,by='[회귀 검사] A050 계약 검사기',links={sop:dict(failureMode='fm:bearing-degradation')})
    forged=copy.deepcopy(review);forged['extraction']['workitem']='forged'
    check('forged production task binding is rejected',http('/api/kg/manuals/commit',forged)[0]==400)
    forged=copy.deepcopy(review);forged['procedures'][0]['steps'][1]['anchor']['quote']='forged'
    check('changed citation is rejected before graph commit',http('/api/kg/manuals/commit',forged)[0]==400)
    receipt=request('/api/kg/manuals/commit',review);save('receipt',receipt)
    check('reviewed batch preserves actual production task and two steps',receipt['extraction']==review['extraction'] and receipt['steps']==2)
    replay=request('/api/kg/manuals/commit',review)
    check('same reviewed batch is idempotent',replay['replayed'] and replay['batch']==receipt['batch'])
    rollback=request('/api/kg/manuals/batches/'+receipt['batch']+'/rollback',dict(by='[회귀 검사] A050 계약 검사기'))
    check('only this graph batch rolls back while original source survives',rollback['status']=='ROLLED_BACK' and request(root)==source)
    restart=subprocess.run(['docker','compose','restart','process'],cwd=ROOT,capture_output=True,timeout=60)
    (dest/'restart.log').write_bytes(restart.stdout+restart.stderr);assert restart.returncode==0
    end=time.monotonic()+45
    while time.monotonic()<end:
        try:
            if http('/healthz')[0]==200:break
        except OSError:pass
        time.sleep(1)
    recovered=request(root+'/extractions/'+pid)
    check('service restart preserves source and extraction workitem result',recovered['preview']['procedures']==result['preview']['procedures'] and recovered['workitem']==result['workitem'])
    save('after-restart',recovered)
    print(dest,flush=True)


if __name__=='__main__':main()
