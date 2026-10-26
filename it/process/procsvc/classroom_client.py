"""Student-side transport. Approval and paid-work limits live on the server.

The local SQLite index is only a durable UI history, never an authorization or
successful-result cache. Every result fetch is authorized again by the server.
"""
import hashlib
import asyncio
import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException

from . import manual_cache, manual_extraction


class Client:
    def __init__(self, url, key_loader, path, *, transport=None, timeout=30):
        self.url = url.rstrip('/')
        parsed = urlsplit(self.url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('수업 관리 서버 주소는 인증 정보가 없는 HTTPS 주소여야 합니다')
        self.key_loader, self.path, self.transport = key_loader, Path(path), transport
        if not 0<timeout<=30:raise ValueError('수업 관리 서버 요청 대기는 30초 이내여야 합니다')
        self.timeout=timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS runs (
                scope TEXT, tenant TEXT, source_id TEXT, run_id TEXT, status TEXT,
                created TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(scope,tenant,source_id,run_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS tool_replies (
                scope TEXT, run_id TEXT, request_id TEXT, request_hash TEXT, body TEXT,
                PRIMARY KEY(scope,run_id,request_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS agent_runs (
                scope TEXT, task TEXT, request_hash TEXT, run_id TEXT,
                PRIMARY KEY(scope,task), UNIQUE(scope,run_id))''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def credential(self):
        key = self.key_loader()
        if not isinstance(key, str) or not 32 <= len(key.strip()) <= 512:
            raise HTTPException(503, '수업 접속 키를 설정하세요')
        return key.strip()

    def scope(self):
        return hashlib.sha256((self.url+'\n'+self.credential()).encode()).hexdigest()

    def request(self, method, path, body=None):
        key = self.credential()
        async def load():
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, transport=self.transport) as client:
                async with client.stream(method, self.url+path, headers={'Authorization': 'Bearer '+key}, json=body) as response:
                    if response.status_code != 200:
                        code = response.status_code if response.status_code in (401, 403, 409, 422, 429, 503) else 502
                        raise HTTPException(code, '관리 서버가 요청을 완료하지 못했습니다. 승인·예산·실행 상태를 확인하세요')
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(data)+len(chunk)>16_000_000:
                            raise HTTPException(502, '관리 서버의 결과 크기 한도를 초과했습니다')
                        data.extend(chunk)
                    value = json.loads(data)
                    if not isinstance(value, dict): raise ValueError()
                    return value
        async def bounded():
            return await asyncio.wait_for(load(),self.timeout)
        try:
            return asyncio.run(bounded())
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, '관리 서버 연결 또는 응답 형식에 오류가 있습니다') from None

    def agent_contract(self,definition,version,activity):
        return self.request('GET','/v1/classroom/agents/contract?'+urlencode(
            dict(definition=definition,version=version,activity=activity)))

    def start_agent(self,task,reference,inputs,revision):
        """Persist local ownership before starting. Reclaims keep the same run.
        A lost start response may rejoin only the server's still-active run;
        terminal uncertainty stays an explicit review case, never new paid work.
        """
        from .classroom_authority import digest
        request_hash=digest([reference,revision,inputs])
        scope=self.scope()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM agent_runs WHERE scope=? AND task=?',(scope,task)).fetchone()
            if old and old['request_hash']!=request_hash:
                raise HTTPException(409,'이 학생 작업에 연결된 승인 판본·입력을 바꿀 수 없습니다')
            if old and old['run_id']:return old['run_id']
            db.execute('INSERT OR IGNORE INTO agent_runs VALUES (?,?,?,NULL)',(scope,task,request_hash))
        value=self.request('POST','/v1/classroom/agents',{'reference':reference,'inputs':inputs,'expected_revision':revision})
        run_id=str(UUID(value['run_id']))
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            owner=db.execute('SELECT task FROM agent_runs WHERE scope=? AND run_id=?',(scope,run_id)).fetchone()
            if owner and owner['task']!=task:
                raise HTTPException(409,'다른 학생 작업에 연결된 실행을 재사용할 수 없습니다')
            db.execute('UPDATE agent_runs SET run_id=? WHERE scope=? AND task=?',(run_id,scope,task))
        return run_id

    def agent_result(self,task,run_id):
        run_id=self.agent_run_for(task,run_id)
        return self.request('GET','/v1/classroom/agents/runs/'+run_id+'/result')

    def cancel_agent(self,task,run_id):
        run_id=self.agent_run_for(task,run_id)
        return self.request('POST','/v1/classroom/agents/runs/'+run_id+'/cancel')

    def respond_agent(self,task,run_id,kind,request_id,text):
        run_id=self.agent_run_for(task,run_id)
        return self.request('POST','/v1/classroom/agents/runs/'+run_id+'/respond',
                            {'kind':kind,'request_id':request_id,'text':text})

    def agent_run_for(self,task,run_id):
        run_id=str(UUID(run_id))
        with self.db() as db:
            row=db.execute('SELECT run_id FROM agent_runs WHERE scope=? AND task=?',(self.scope(),task)).fetchone()
            if not row or row['run_id']!=run_id:
                raise HTTPException(403,'이 학생 작업에 연결된 관리 실행이 아닙니다')
        return run_id

    def authorize_hash(self, sha256):
        if len(sha256) != 64 or any(c not in '0123456789abcdef' for c in sha256):
            raise ValueError('원문 해시 형식이 올바르지 않습니다')
        return self.request('GET', '/v1/classroom/documents/'+sha256)

    def exchange_tool(self, run_id, execute_read):
        """One bounded reverse-RPC step. execute_read must use the local gated
        router (reads or claim-bound DMN proposals), never a caller-chosen URL.
        Persist the observation before sending: an uncertain HTTP outcome may
        replay that exact reply, never a fresh reading labelled as the old one.
        Different runs/requests always obtain their own current observation.
        """
        from .classroom_authority import digest
        run_id = str(UUID(str(run_id)))
        pending = self.request('GET', f'/v1/classroom/runs/{run_id}/tool-requests').get('requests')
        if not isinstance(pending,list) or len(pending)>1:
            raise HTTPException(502, '관리 도구 조회 요청 형식이 올바르지 않습니다')
        if not pending:
            return {'status':'IDLE'}
        query = pending[0]
        if (not isinstance(query,dict) or set(query)!={'id','tool','arguments'}
                or not isinstance(query['tool'],str) or not isinstance(query['arguments'],dict)):
            raise HTTPException(502, '관리 도구 조회 계약이 올바르지 않습니다')
        request_id = str(UUID(str(query['id'])))
        scope, fingerprint = self.scope(), digest(query)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT request_hash,body FROM tool_replies WHERE scope=? AND run_id=? AND request_id=?',
                                  (scope,run_id,request_id)).fetchone()
            if previous:
                if previous['request_hash'] != fingerprint:
                    raise HTTPException(409, '같은 조회 요청의 내용이 바뀌었습니다')
                body = json.loads(previous['body'])
            else:
                try:
                    reply = execute_read(query['tool'],deepcopy(query['arguments']))
                    if not isinstance(reply,dict) or set(reply)!={'result','is_error'} or type(reply['is_error']) is not bool:
                        raise ValueError()
                    size = len(json.dumps(reply['result'],ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8'))
                    if size>128000:
                        reply = {'is_error':True,'result':{'error':'도구 응답 한도 초과: 조회 범위를 줄이거나 상세 페이지로 나누세요'}}
                except Exception:
                    reply = {'is_error':True,'result':{'error':'학생 현재 상태를 조회하지 못했습니다. 완료·정상으로 추정하지 마세요'}}
                body = dict(run_id=run_id,request_id=request_id,**reply)
                db.execute('INSERT INTO tool_replies VALUES (?,?,?,?,?)',
                           (scope,run_id,request_id,fingerprint,json.dumps(body,ensure_ascii=False,allow_nan=False)))
        return self.request('POST','/v1/classroom/tool-results',body)

    def start(self, tenant, source, feedback=None):
        if feedback:
            raise HTTPException(403, '재추출 지시 변경은 강사 관리 서버에서 승인해야 합니다')
        result = self.request('POST', '/v1/classroom/extractions', {'sha256': source['sha256']})
        run_id = str(UUID(result['run_id']))
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO runs(scope,tenant,source_id,run_id,status) VALUES (?,?,?,?,?)',
                       (self.scope(), tenant, source['source_id'], run_id, result['state']))
        return dict(instance=run_id, source_id=source['source_id'], status=result['state'], managed=True,
                    cache=dict(reused=result['reused'], validated=False))

    def history(self, tenant, source, limit, offset):
        self.authorize_hash(source['sha256'])
        if not 1 <= limit <= 100 or offset < 0: raise ValueError('목록 범위가 올바르지 않습니다')
        with self.db() as db:
            rows = db.execute('''SELECT run_id AS proc_inst_id,status,created AS start_date FROM runs
                WHERE scope=? AND tenant=? AND source_id=? ORDER BY created DESC,run_id LIMIT ? OFFSET ?''',
                (self.scope(), tenant, source['source_id'], limit+1, offset)).fetchall()
        return dict(items=[dict(row) for row in rows[:limit]], limit=limit, offset=offset,
                    next_offset=offset+limit if len(rows)>limit else None)

    def result(self, tenant, source, run_id, previous_batch):
        run_id = str(UUID(run_id))
        with self.db() as db:
            row = db.execute('SELECT 1 FROM runs WHERE scope=? AND tenant=? AND source_id=? AND run_id=?',
                             (self.scope(), tenant, source['source_id'], run_id)).fetchone()
        if row is None: raise KeyError('이 문서에서 요청한 추출 실행이 아닙니다')
        value = self.request('GET', '/v1/classroom/runs/'+run_id+'/result')
        value['managed'] = True
        if value.get('preview'):
            if value.get('source_fingerprint') != manual_cache.source_fingerprint(source) or \
                    value.get('status') != 'DONE' or not value.get('cache', {}).get('validated'):
                raise ValueError('관리 서버 결과와 로컬 원문·파서 판본 또는 검증 상태가 다릅니다')
            remote_id = value['preview']['source_id']
            def remap(item):
                if isinstance(item, dict):
                    return {k: source['source_id'] if k == 'source_id' and v == remote_id else remap(v) for k,v in item.items()}
                if isinstance(item, list): return [remap(v) for v in item]
                return deepcopy(item)
            proposal = remap({k: v for k,v in value['preview'].items() if k in manual_extraction.PROPOSAL_KEYS})
            proposal = manual_extraction.validate_proposal(source, proposal)
            value['preview'] = manual_extraction._preview(source, proposal, previous_batch,
                dict(instance=run_id, managed=True, cache=value['cache']))
        with self.db() as db:
            db.execute('UPDATE runs SET status=? WHERE scope=? AND tenant=? AND source_id=? AND run_id=?',
                       (value['status'], self.scope(), tenant, source['source_id'], run_id))
        return value
