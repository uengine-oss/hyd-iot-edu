"""Idempotent installation of the three shipped classroom flows, never a flag
for arbitrary authoring. Only in-process ASGI calls carry bootstrap authority.
"""
import asyncio
import json
from pathlib import Path

import httpx
from fastapi import HTTPException, Request
from hydcommon import course_access

FLOWS = json.loads(Path(course_access.__file__).with_name('course_flows.json').read_text(encoding='utf8'))
PATHS = {'/api/flows/import'} | {
    path for did in FLOWS for path in (f'/api/flows/{did}/check',f'/api/flows/{did}/register',
                                      f'/api/process/definitions/{did}/deploy')}


def mount(app):
    lock = asyncio.Lock()

    async def internal(scope,receive,send):
        if scope['type']=='http' and scope['method']=='POST' and scope['path'] in PATHS:
            scope['state'] = dict(scope.get('state') or {}, _course_bootstrap=('POST',scope['path']))
        await app(scope,receive,send)

    @app.post('/api/course-bootstrap')
    async def ensure(request:Request):
        raw=await request.body()
        try:
            if len(raw)>32 or raw and json.loads(raw)!={}:raise ValueError()
        except ValueError:raise HTTPException(422,'기본 수업 흐름 확인에는 설정값을 받지 않습니다.') from None
        async with lock:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=internal),base_url='http://course-bootstrap',timeout=120) as client:
                async def call(method,path,body=None):
                    response=await client.request(method,path,json=body)
                    if response.status_code>=400:
                        raise HTTPException(503,'기본 수업 흐름 준비에 실패했습니다. 기존 자료를 보존한 채 서버 기록을 확인하세요.')
                    return response.json()
                deployed=await call('GET','/api/flows/deployments')
                present={r['definition'] for r in deployed.get('flows',[]) if r.get('class_flow')}
                result=[]
                for did,(filename,xml,mapping) in FLOWS.items():
                    if did in present:
                        result.append({'definition':did,'reused':True});continue
                    await call('POST','/api/flows/import',{'xml':xml,'file_name':filename,'definition_id':did,'class_flow':True})
                    checked=await call('POST',f'/api/flows/{did}/check',{'mapping':mapping})
                    if (checked.get('check') or checked).get('problems'):
                        raise HTTPException(503,'기본 수업 흐름 검사를 통과하지 못했습니다. 등록하지 않았습니다.')
                    registered=await call('POST',f'/api/flows/{did}/register',{'mapping':mapping,'class_flow':True})
                    await call('POST',f'/api/process/definitions/{did}/deploy',{'version':registered['version'],
                        'by':'c3-assembly','reason':'C3 확정 흐름 배포','class_flow':True})
                    result.append({'definition':did,'reused':False})
                return {'status':'ok','flows':result}
