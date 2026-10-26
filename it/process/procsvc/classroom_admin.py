"""Instructor-host CLI only; never mounted on the classroom HTTP service.

The database and archived originals are supplied by the instructor host. Keys
are read from a local file at execution and only their hashes enter PostgreSQL.
Updating an existing grant never resets its accumulated spend.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .classroom_authority import Denied, key_hash, validate_policy


def approve(authority, archive, *, key, subject, scope, expires_at, policy, runtime=None):
    validate_policy(policy)
    agents = policy.get('agents') or {}
    if not isinstance(agents, dict):
        raise Denied('에이전트 승인 목록이 올바르지 않습니다')
    if 'agent_run' in policy['actions'] and not agents:
        raise Denied('에이전트 실행을 허용하려면 승인 판본이 필요합니다')
    if not agents:
        return _approve(authority, archive, key=key, subject=subject, scope=scope, expires_at=expires_at, policy=policy)
    if runtime is None or runtime.tenant_id != subject:
        raise Denied('승인할 교육 공간의 실제 작업 저장소가 필요합니다')
    from .classroom_agents import checked
    # Import and grant may use different DBs. Commit source import first;
    # grant only after rechecking it under the same authoring boundary.
    with runtime.repo.classroom_authoring_transaction(subject):
        for reference, approval in agents.items():
            if not isinstance(reference, str) or not reference.strip():
                raise Denied('에이전트 승인 참조 이름이 필요합니다')
            checked(runtime, approval)
        return _approve(authority, archive, key=key, subject=subject, scope=scope, expires_at=expires_at, policy=policy)


def _approve(authority, archive, *, key, subject, scope, expires_at, policy):
    from psycopg.types.json import Jsonb
    hashed = key_hash(key)
    if not subject.strip() or not scope.strip():
        raise Denied('강사 교육 공간·승인 범위 판본이 필요합니다')
    if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
        raise Denied('만료 시각은 시간대가 있는 미래 시각이어야 합니다')
    validate_policy(policy)
    for sha, document in policy['documents'].items():
        if not re.fullmatch('[0-9a-f]{64}', sha) or not isinstance(document, dict):
            raise Denied('승인 문서 해시 형식이 올바르지 않습니다')
        source = archive.get(subject, document.get('source_id', ''))
        if source['sha256'] != sha or source['status'] != 'READY':
            raise Denied('강사 보관 원문의 해시·준비 상태가 승인 목록과 다릅니다')
    with authority.connect() as db:
        old = db.execute('SELECT subject,scope FROM hyd_classroom_grants WHERE key_hash=%s FOR UPDATE', (hashed,)).fetchone()
        if old and old['subject'] != subject:
            raise Denied('기존 접속 키를 다른 교육 공간으로 옮길 수 없습니다')
        db.execute('''INSERT INTO hyd_classroom_grants(key_hash,subject,scope,policy,expires_at)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(key_hash) DO UPDATE
            SET scope=EXCLUDED.scope,policy=EXCLUDED.policy,expires_at=EXCLUDED.expires_at,enabled=true
            WHERE hyd_classroom_grants.subject=EXCLUDED.subject''',
            (hashed, subject, scope, Jsonb(policy), expires_at))
        # The row lock and ON CONFLICT cover simultaneous instructor invocations.
        row = db.execute('SELECT subject,scope,enabled,calls,input_bytes,output_tokens FROM hyd_classroom_grants WHERE key_hash=%s', (hashed,)).fetchone()
        if row['subject'] != subject:
            raise Denied('동시에 다른 교육 공간에 등록된 키입니다')
    return dict(row, documents=len(policy['documents']))


def revoke(authority, key):
    with authority.connect() as db:
        row = db.execute('UPDATE hyd_classroom_grants SET enabled=false WHERE key_hash=%s RETURNING subject,enabled',
                         (key_hash(key),)).fetchone()
        if row is None:
            raise Denied('등록된 수업 접속 키가 없습니다')
    return row


def main():
    parser = argparse.ArgumentParser(description='강사 관리 서버의 승인 자료·키·예산 등록 (HTTP 관리 경로 없음)')
    parser.add_argument('action', choices=['approve','revoke'])
    parser.add_argument('--key-file', required=True)
    parser.add_argument('--manifest', help='subject,scope,expires_at,policy JSON; 키를 넣지 않습니다')
    args = parser.parse_args()
    try:
        import psycopg
        from psycopg.rows import dict_row
        from .classroom_authority import Authority
        from .manual_sources import ManualSources
        dsn = os.environ['HYD_CLASSROOM_AUTHORITY_DSN']
        authority = Authority(lambda: psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5))
        key = Path(args.key_file).read_text(encoding='utf8').strip()
        if args.action == 'revoke':
            result = revoke(authority, key)
        else:
            manifest = json.loads(Path(args.manifest).read_text(encoding='utf8'))
            if set(manifest) != {'subject','scope','expires_at','policy'}:
                raise Denied('승인 명세의 필드가 올바르지 않습니다')
            manifest['expires_at'] = datetime.fromisoformat(manifest['expires_at'])
            archive = ManualSources(Path(os.getenv('PROCESS_STATE_PATH','/data/process.sqlite3')).with_name('manuals.sqlite3'))
            runtime = None
            if manifest['policy'].get('agents'):
                from types import SimpleNamespace
                from .procdb import PgRepo
                runtime = SimpleNamespace(repo=PgRepo(os.environ['SUPABASE_DSN']), tenant_id=manifest['subject'])
            result = approve(authority, archive, key=key, runtime=runtime, **manifest)
        print(json.dumps(result, ensure_ascii=False))
    except Exception:
        # Database/OS exceptions can carry credentials or private paths.
        print('강사 승인 변경 실패: 명세·보관 원문·키 파일·관리 DB 설정을 확인하세요.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
