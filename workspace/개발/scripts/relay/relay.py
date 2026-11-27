"""강의 중계(LiteLLM)를 GCP 프로젝트 하나에 올리고, 키를 만들고, 시스템이 기대는 약속대로 답하는지 재는 강사 도구.

언제: 강의 중계를 새 GCP 프로젝트로 옮기거나 다시 올릴 때, 강사 · 학생 키를 만들 때, 중계가 약속을 지키는지 잴 때.

  <py> workspace/개발/scripts/relay/relay.py 올리기 --project <프로젝트 ID>
  <py> workspace/개발/scripts/relay/relay.py 키 --project <ID> --이름 <별칭> --한도 <달러> [--모델 coding haiku]   → 작업/_로컬/relay_key_<별칭>.env
  <py> workspace/개발/scripts/relay/relay.py 확인 --project <ID>   (또는 --url <주소> --master-env <파일>: 이 PC 에서 띄운 같은 이미지)

먼저: 그 프로젝트의 소유 계정으로 `gcloud auth login`(사용자가 브라우저에서 한다). 모델 회사 키는 그 비밀이 Secret Manager 에 아직 없을 때만
git 밖 파일에서 읽는다 — `작업/_로컬/openai.env`(`OPENAI_API_KEY=…` 한 줄), `작업/_로컬/anthropic.env`(`ANTHROPIC_API_KEY=…` 한 줄).
키를 바꿀 때는 `gcloud secrets versions add <비밀> --data-file=-`로 새 판을 넣고 다시 올린다. 이 도구는 비밀값을 출력하지 않는다 — Secret Manager 와
`작업/_로컬/` 파일에만 쓴다.

시스템이 기대는 약속(확인이 하나씩 잰다):
 - process 관문(it/process/procsvc/course_model.py)의 Anthropic 방식 POST /v1/messages(스트리밍) · /v1/messages/count_tokens,
   머리글 x-api-key. 시작 8단계 · 점검(scripts/relay_probe.py)은 GET /v1/models 에 수업 모델이 있는지 본다.
 - 코딩 랩(workspace/강의제작/제작도구/실습시작/lab_llm.py)의 OpenAI 방식 POST <OPENAI_BASE_URL>/chat/completions, Bearer 키.
 - 시스템과 랩이 부르는 모델 이름은 coding(gpt-6-luna) 하나. 옆에 haiku(Claude Haiku 5.5)를 세워 두고, 그 이름을 허락한 키로만 닿는다.
   키에 없는 모델은 거절(관문이 relay_model 로 가른다). 키마다 비용 한도(가상 키 — Cloud SQL Postgres) — 호출 값은 LiteLLM 가격표로 셈한다.
 - 최소 인스턴스 0 — 첫 요청이 콜드스타트로 느린 것은 의도한 동작이다(CLAUDE.md 4절).

만드는 것(이름은 고정, 다시 돌리면 있는 것은 건너뛴다): Artifact Registry `hyd-relay`, 서비스 계정 `hyd-relay`, Cloud SQL `hyd-relay-db`
(POSTGRES_15 · db-f1-micro · HDD 10GB), 비밀 `hyd-relay-openai-key` · `hyd-relay-anthropic-key` · `hyd-relay-master-key` · `hyd-relay-database-url`,
Cloud Run `hyd-relay`. 지역은 asia-northeast3(서울). 크레딧에서 나가는 것은 주로 Cloud SQL 이고, AI 호출 값은 OpenAI · Anthropic 계정에서 따로 나간다.
"""
from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOCAL = ROOT / '작업' / '_로컬'
REGION = 'asia-northeast3'
REPO, IMAGE, SERVICE, ACCOUNT, DB = 'hyd-relay', 'litellm', 'hyd-relay', 'hyd-relay', 'hyd-relay-db'
SECRET = {'OPENAI_API_KEY': 'hyd-relay-openai-key', 'ANTHROPIC_API_KEY': 'hyd-relay-anthropic-key',
          'LITELLM_MASTER_KEY': 'hyd-relay-master-key', 'DATABASE_URL': 'hyd-relay-database-url'}
KEY_FILES = {'OPENAI_API_KEY': 'openai.env', 'ANTHROPIC_API_KEY': 'anthropic.env'}   # 모델 회사 키 — 그 비밀이 아직 없을 때만 읽는다
APIS = ['run.googleapis.com', 'sqladmin.googleapis.com', 'secretmanager.googleapis.com', 'artifactregistry.googleapis.com', 'iam.googleapis.com']
MODEL = 'coding'   # 시스템과 랩이 부르는 이름(config.yaml)
SIDE = 'haiku'     # 옆에 세워 둔 이름 — 그 이름을 허락한 키로만 닿는다


class Stop(Exception):
    """사람이 읽는 멈춤 까닭."""


def tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise Stop(f'{name} 를 PATH 에서 찾지 못했습니다')
    return path


def run(*args: str, data: bytes | None = None, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    proc = subprocess.run(list(args), input=data, capture_output=True)
    if proc.returncode not in ok:
        err = proc.stderr.decode('utf-8', 'replace').strip().splitlines()
        raise Stop(f'명령 실패({proc.returncode}): {" ".join(args[:4])} … — {" / ".join(err[-3:])}')
    return proc


def out(*args: str) -> str:
    return run(*args).stdout.decode('utf-8', 'replace').strip()


def exists(*args: str) -> bool:
    return run(*args, ok=(0, 1)).returncode == 0


def read_env(path: Path, name: str) -> str:
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith(name + '='):
            value = line.split('=', 1)[1].strip()
            if value:
                return value
    raise Stop(f'{path} 에 {name}= 줄이 없습니다')


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(''.join(f'{k}={v}\n' for k, v in values.items()).encode())


class Gcp:
    def __init__(self, project: str):
        self.g, self.project = tool('gcloud'), project
        self.number = out(self.g, 'projects', 'describe', project, '--format=value(projectNumber)')
        self.sa = f'{ACCOUNT}@{project}.iam.gserviceaccount.com'
        self.registry = f'{REGION}-docker.pkg.dev'
        self.image = f'{self.registry}/{project}/{REPO}/{IMAGE}'
        self.connection = f'{project}:{REGION}:{DB}'

    def __call__(self, *args: str, data: bytes | None = None, ok=(0,)):
        return run(self.g, *args, f'--project={self.project}', '--quiet', data=data, ok=ok)

    def has(self, *args: str) -> bool:
        return self(*args, ok=(0, 1)).returncode == 0

    def secret(self, name: str, value: bytes) -> None:
        if self.has('secrets', 'describe', name):
            return
        self('secrets', 'create', name, '--replication-policy=automatic', '--data-file=-', data=value)
        say(f'비밀 {name} 만듦')

    def secret_value(self, name: str) -> str:
        return self('secrets', 'versions', 'access', 'latest', f'--secret={name}').stdout.decode().strip()

    def url(self) -> str:
        return self('run', 'services', 'describe', SERVICE, f'--region={REGION}', '--format=value(status.url)').stdout.decode().strip()


def say(text: str) -> None:
    print(text, flush=True)


def deploy(gcp: Gcp) -> None:
    # 없는 비밀의 키 파일은 무엇을 만들기 전에 읽는다 — 파일이 없으면 여기서 멈춘다
    vendor_keys = {env: read_env(LOCAL / file, env) for env, file in KEY_FILES.items() if not gcp.has('secrets', 'describe', SECRET[env])}
    say(f'프로젝트 {gcp.project}(번호 {gcp.number}) · 지역 {REGION}')
    gcp('services', 'enable', *APIS)
    say('API 켬: ' + ' · '.join(a.split('.')[0] for a in APIS))
    if not gcp.has('artifacts', 'repositories', 'describe', REPO, f'--location={REGION}'):
        gcp('artifacts', 'repositories', 'create', REPO, '--repository-format=docker', f'--location={REGION}')
        say(f'이미지 저장소 {REPO} 만듦')
    if not gcp.has('iam', 'service-accounts', 'describe', gcp.sa):
        gcp('iam', 'service-accounts', 'create', ACCOUNT, '--display-name=강의 중계')
        say(f'서비스 계정 {gcp.sa} 만듦')
    for role in ('roles/secretmanager.secretAccessor', 'roles/cloudsql.client'):
        gcp('projects', 'add-iam-policy-binding', gcp.project, f'--member=serviceAccount:{gcp.sa}', f'--role={role}', '--condition=None')
    if not gcp.has('sql', 'instances', 'describe', DB):
        say(f'Cloud SQL {DB} 만드는 중(5~10분)')
        gcp('sql', 'instances', 'create', DB, '--database-version=POSTGRES_15', '--edition=enterprise', '--tier=db-f1-micro',
            f'--region={REGION}', '--storage-type=HDD', '--storage-size=10', '--no-storage-auto-increase', '--availability-type=zonal')
    if not gcp.has('sql', 'databases', 'describe', 'litellm', f'--instance={DB}'):
        gcp('sql', 'databases', 'create', 'litellm', f'--instance={DB}')
    if not gcp.has('secrets', 'describe', SECRET['DATABASE_URL']):
        password = secrets.token_urlsafe(24)
        users = gcp('sql', 'users', 'list', f'--instance={DB}', '--format=value(name)').stdout.decode().split()
        gcp('sql', 'users', 'set-password' if 'litellm' in users else 'create', 'litellm', f'--instance={DB}', f'--password={password}')
        gcp.secret(SECRET['DATABASE_URL'], f'postgresql://litellm:{password}@localhost/litellm?host=/cloudsql/{gcp.connection}'.encode())
    for env, value in vendor_keys.items():
        gcp.secret(SECRET[env], value.encode())
    gcp.secret(SECRET['LITELLM_MASTER_KEY'], ('sk-' + secrets.token_urlsafe(32)).encode())
    docker = tool('docker')
    tag = f'{gcp.image}:{time.strftime("%Y%m%d-%H%M%S")}'
    run(gcp.g, 'auth', 'configure-docker', gcp.registry, '--quiet')
    run(docker, 'build', '-t', tag, str(HERE))
    run(docker, 'push', tag)
    say(f'이미지 올림 {tag}')
    gcp('run', 'deploy', SERVICE, f'--image={tag}', f'--region={REGION}', '--port=4000', f'--service-account={gcp.sa}',
        f'--add-cloudsql-instances={gcp.connection}', '--allow-unauthenticated', '--min-instances=0', '--max-instances=2',
        '--memory=2Gi', '--cpu=1', '--cpu-boost', '--timeout=1800', '--concurrency=40',
        '--set-secrets=' + ','.join(f'{env}={name}:latest' for env, name in SECRET.items()))
    url = gcp.url()
    write_env(LOCAL / 'relay.env', {'LLM_RELAY_URL': url})
    say(f'중계 주소 {url} (작업/_로컬/relay.env 에 적음)')


def call(url: str, path: str, key: str, body: dict | None = None, *, stream: bool = False, timeout: float = 120,
         seen: dict | None = None):
    """seen 을 주면 응답 머리글(소문자 이름)을 담는다 — 중계가 셈한 호출 값은 x-litellm-response-cost 에 온다."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url.rstrip('/') + path, data=data, method='POST' if data else 'GET', headers={
        'x-api-key': key, 'Authorization': f'Bearer {key}', 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if seen is not None:
                seen.update((k.lower(), v) for k, v in r.headers.items())
            raw = r.read()
            return r.status, (raw.decode('utf-8', 'replace') if stream else json.loads(raw or b'null'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300]


def make_key(url: str, master: str, alias: str, budget: float, models=(MODEL,)) -> str:
    status, body = call(url, '/key/generate', master, {'models': list(models), 'max_budget': budget, 'key_alias': alias})
    if status != 200 or not isinstance(body, dict) or not body.get('key'):
        raise Stop(f'키를 만들지 못했습니다({status}): {body}')
    return body['key']


def drop_key(url: str, master: str, key: str) -> None:
    call(url, '/key/delete', master, {'keys': [key]})


def text_of(body) -> str:
    """Anthropic 방식(content) · OpenAI 방식(choices) 답의 글. 답이 아니면 받은 것 그대로."""
    if not isinstance(body, dict):
        return str(body)
    if body.get('choices'):
        return body['choices'][0].get('message', {}).get('content') or ''
    return ''.join(c.get('text', '') for c in body.get('content', []))


def check(url: str, master: str, with_db: bool = True) -> list[tuple[str, bool, str]]:
    """약속 하나마다 (이름, 통과, 본 것). 키 한도 · 모델 제한은 가상 키가 있어야 재므로 with_db 일 때만 잰다.
    키는 이름 하나씩만 허락한다 — coding 키(시스템 · 랩과 같은 꼴)와 haiku 키."""
    results, stamp = [], int(time.time())
    key, side = (make_key(url, master, f'check-{stamp}', 0.5) if with_db else master), None
    try:
        side = make_key(url, master, f'check-{SIDE}-{stamp}', 0.5, models=(SIDE,)) if with_db else master
        status, body = call(url, '/v1/models', key, timeout=180)
        ids = [m.get('id') for m in body.get('data', [])] if isinstance(body, dict) else []
        results.append(('GET /v1/models 에 coding', status == 200 and MODEL in ids, f'{status} {ids}'))
        msg = {'model': MODEL, 'max_tokens': 32, 'messages': [{'role': 'user', 'content': 'Reply with exactly: OK'}]}
        costs = {}
        for model, k in ((MODEL, key), (SIDE, side)):
            seen = {}
            status, body = call(url, '/v1/messages', k, {**msg, 'model': model}, seen=seen)
            text, costs[model] = text_of(body), float(seen.get('x-litellm-response-cost') or 0)
            results.append((f'POST /v1/messages 답({model})', status == 200 and 'OK' in text,
                            f'{status} {text[:60]!r} model={body.get("model") if isinstance(body, dict) else "-"}'))
            status, body = call(url, '/chat/completions', k, {'model': model, 'messages': msg['messages'], 'max_completion_tokens': 32})
            text = text_of(body)
            results.append((f'POST /chat/completions 답({model}, 코딩 랩 방식)', status == 200 and 'OK' in text, f'{status} {text[:60]!r}'))
        # 값이 0 이면 키 한도가 그 모델에서 늘 남는다 — LiteLLM 가격표에 그 모델이 없다는 뜻이다
        results.append(('호출 값을 셈한다(키 한도의 바탕)', all(v > 0 for v in costs.values()), ' · '.join(f'{m} ${v:.8f}' for m, v in costs.items())))
        status, raw = call(url, '/v1/messages', key, {**msg, 'stream': True}, stream=True)
        events = [line[7:] for line in raw.splitlines() if line.startswith('event: ')]
        results.append(('POST /v1/messages 스트리밍', status == 200 and 'content_block_delta' in events and 'message_stop' in events,
                        f'{status} 사건 {sorted(set(events))}'))
        status, body = call(url, '/v1/messages/count_tokens', key, {'model': MODEL, 'messages': msg['messages']})
        results.append(('POST /v1/messages/count_tokens', status == 200 and isinstance(body, dict) and int(body.get('input_tokens', 0)) > 0, f'{status} {body}'))
        if with_db:
            status, body = call(url, '/v1/messages', key, {**msg, 'model': SIDE})
            results.append((f'{MODEL} 만 허락한 키로 {SIDE} 는 거절', status in (400, 401, 403) and 'model' in str(body).lower(), f'{status} {str(body)[:120]}'))
            broke = make_key(url, master, f'check-budget-{int(time.time())}', 0.0)
            try:
                status, body = call(url, '/v1/messages', broke, msg)
                # 번호는 판본마다 다르다(v1.106.6 은 422) — 관문(course_model.classify_relay)은 글의 budget 으로 relay_budget 을 가른다
                results.append(('한도 0 인 키는 거절', status >= 400 and 'budget' in str(body).lower(), f'{status} {str(body)[:120]}'))
            finally:
                drop_key(url, master, broke)
    finally:
        if with_db:
            drop_key(url, master, key)
            if side:
                drop_key(url, master, side)
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('올리기', '키', '확인'):
        s = sub.add_parser(name)
        s.add_argument('--project')
        if name == '키':
            s.add_argument('--이름', required=True)
            s.add_argument('--한도', type=float, required=True, help='이 키의 비용 한도(달러)')
            s.add_argument('--모델', nargs='+', choices=(MODEL, SIDE), default=[MODEL], help=f'이 키가 부를 수 있는 이름(기본 {MODEL})')
        if name == '확인':
            s.add_argument('--url')
            s.add_argument('--master-env', help='LITELLM_MASTER_KEY= 줄이 있는 git 밖 파일(이 PC 에서 띄운 같은 이미지를 잴 때)')
            s.add_argument('--db-없음', action='store_true', help='가상 키가 없는 중계(DB 없이 띄운 시험판) — 키 한도 · 모델 제한은 재지 않는다')
    a = p.parse_args(argv)
    try:
        if a.cmd == '올리기':
            deploy(Gcp(a.project or p.error('--project')))
            return 0
        if a.cmd == '확인' and a.url:
            url, master = a.url, read_env(Path(a.master_env), 'LITELLM_MASTER_KEY')
        else:
            gcp = Gcp(a.project or p.error('--project'))
            url, master = gcp.url(), gcp.secret_value(SECRET['LITELLM_MASTER_KEY'])
        if a.cmd == '키':
            path = LOCAL / f'relay_key_{a.이름}.env'
            write_env(path, {'LLM_API_KEY': make_key(url, master, a.이름, a.한도, a.모델)})
            say(f'키 {a.이름}(한도 ${a.한도:g} · 모델 {" ".join(a.모델)}) → {path}')
            return 0
        results = check(url, master, with_db=not a.db_없음)
        for name, passed, seen in results:
            say(f'{"통과" if passed else "실패"}  {name}  — {seen}')
        return 0 if all(r[1] for r in results) else 1
    except Stop as e:
        say(f'멈춤: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
