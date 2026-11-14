"""수업 흐름 A · B · C(course_flows.json) 설치 — 시작 6단계(scripts/c3_flows.py)가 부른다. 임의 흐름을 만드는 길이 아니다.

배포된 수업 흐름의 내용(등록 정의의 bpmnImport: 그림 sha256 · 연결)이 course_flows.json 과 같으면 아무것도 바꾸지 않고, 없거나
다르면(강사가 흐름을 고쳐 push 한 뒤의 시작) 가져오기 → 사전 검사 → 새 판본 등록 → 배포를 한다. 옛 판본은 지우지 않는다(그 판으로
진행 중인 처리 건은 그 판으로 끝난다). 「수업 흐름」 표시는 프로세스 안 호출만 실을 수 있다(course_policy 문지기 — internal_client).
"""
import asyncio
import contextlib
import json
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request

from .bpmn_import import xml_sha256
from .course_policy import COURSE_FLOWS as FLOWS
PATHS = {'/api/flows/import'} | {
    path for did in FLOWS for path in (f'/api/flows/{did}/check', f'/api/flows/{did}/register',
                                       f'/api/process/definitions/{did}/deploy')}


def same_content(definition: dict, xml: str, mapping: dict) -> bool:
    """등록 정의가 이 그림 · 연결로 만든 것인가(bpmn_import.check 가 정의에 남기는 bpmnImport 칸으로)."""
    made = (definition or {}).get('bpmnImport') or {}
    return made.get('sha256') == xml_sha256(xml) and made.get('mapping') == mapping


@contextlib.asynccontextmanager
async def internal_client(app):
    """process 안 호출 — 수업 흐름 설치 경로(PATHS)에만 「수업 흐름 설치」 표시를 싣는다(밖에서 오는 요청은 실을 수 없다)."""
    async def internal(scope, receive, send):
        if scope['type'] == 'http' and scope['method'] == 'POST' and scope['path'] in PATHS:
            scope['state'] = dict(scope.get('state') or {}, _course_bootstrap=('POST', scope['path']))
        await app(scope, receive, send)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=internal), base_url='http://course-bootstrap', timeout=120) as client:
        yield client


async def _call(client, method, path, body=None, step=''):
    response = await client.request(method, path, json=body)
    if response.status_code >= 400:
        try:
            detail = response.json().get('detail')
        except ValueError:
            detail = response.text
        raise HTTPException(503, f'기본 제공 흐름 준비에 실패했습니다({step} {method} {path} → {response.status_code}: '
                                 f'{str(detail)[:300]}). 기존 자료는 그대로입니다.')
    return response.json()


async def install(client, did, filename, xml, mapping) -> str:
    """흐름 하나를 수업 흐름으로 가져오기 → 사전 검사 → 새 판본 등록 → 배포. 돌려줌 = 배포한 판본."""
    await _call(client, 'POST', '/api/flows/import', {'xml': xml, 'file_name': filename, 'definition_id': did, 'class_flow': True}, '가져오기')
    checked = await _call(client, 'POST', f'/api/flows/{did}/check', {'mapping': mapping, 'class_flow': True}, '사전 검사')
    problems = (checked.get('check') or checked).get('problems')
    if problems:
        raise HTTPException(503, f'기본 제공 흐름 {did} 가 사전 검사를 통과하지 못해 등록하지 않았습니다: '
                                 + ' / '.join(str(p.get('reason')) for p in problems)[:400])
    registered = await _call(client, 'POST', f'/api/flows/{did}/register', {'mapping': mapping, 'class_flow': True}, '등록')
    await _call(client, 'POST', f'/api/process/definitions/{did}/deploy',
                {'version': registered['version'], 'by': 'c3-assembly', 'reason': '기본 제공 흐름 설치', 'class_flow': True}, '배포')
    return registered['version']


async def ensure_flows(client) -> list[dict]:
    """course_flows.json 의 흐름마다: 배포된 수업 흐름이 같은 내용이면 그대로, 없거나 다르면 새 판본 설치."""
    deployed = await _call(client, 'GET', '/api/flows/deployments', step='배포 확인')
    heads = {r['definition']: r for r in deployed.get('flows', []) if r.get('class_flow')}
    result = []
    for did, (filename, xml, mapping) in FLOWS.items():
        head = heads.get(did)
        if head:
            current = await _call(client, 'GET', f"/api/process/definitions/{quote(did)}?version={quote(str(head['version']))}", step='배포된 판 읽기')
            if same_content(current, xml, mapping):
                result.append({'definition': did, 'reused': True, 'version': head['version']})
                continue
        version = await install(client, did, filename, xml, mapping)
        result.append({'definition': did, 'reused': False, 'version': version, 'replaced': head['version'] if head else None})
    return result


def mount(app):
    lock = asyncio.Lock()

    @app.post('/api/course-bootstrap')
    async def ensure(request: Request):
        raw = await request.body()
        try:
            if len(raw) > 32 or raw and json.loads(raw) != {}:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, '기본 제공 흐름 확인에는 설정값을 받지 않습니다.') from None
        async with lock:
            async with internal_client(app) as client:
                return {'status': 'ok', 'flows': await ensure_flows(client)}
