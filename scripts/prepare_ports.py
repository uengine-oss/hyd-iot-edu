"""시작 2단계 — 이 폴더 · 이 PC의 값(Compose · 업무 DB 프로젝트 이름, 바깥 포트)을 정한다. git 이 추적하는 파일은 바꾸지 않는다.

기록(git 밖, 이 폴더 전용 — .hyd-runtime/):
  project.json  이 폴더 경로와 Compose · 업무 DB(Supabase) 프로젝트 이름. 다음 시작이 「같은 폴더 · 옮긴 폴더 · 복사한 폴더」를 가른다
  ports.json    기본 포트 → 이 PC의 바깥 포트(시작 · 점검 · 개발 도구가 읽는다)
만드는 것(git 밖):
  .env              Compose 가 읽는 이 PC 값(COMPOSE_PROJECT_NAME · HYD_PORT_* · HYD_PORTS · 업무 DB 주소 · 메일함 SMTP 포트,
                    없을 때 한 번 만드는 내부 확인 값 PROCESS_CALLER_TOKEN · CMD_FINGERPRINT_KEY)
  it/supabase/.env  Supabase CLI 가 스스로 읽어 config.toml 값을 덮어쓰는 이 PC 값(SUPABASE_PROJECT_ID · SUPABASE_*_PORT · 로그인 주소).
                    근거(CLI 2.119.0 소스, 태그 커밋 3cb948c5): start · stop 은 apps/cli/src/command-internal/local-config-values.ts 의
                    envOverride("SUPABASE_<설정 경로>") — <workdir>/supabase/.env 값을 먼저, 없으면 셸 환경. migration up 은
                    db-config.toml-read.ts 의 loadProjectEnv(<workdir>/supabase/.env · <workdir>/.env). workdir 는 it/ 다.
it/supabase/config.toml 은 커밋된 값 그대로 둔다. 앞 판 시작이 이 파일에 써 넣은 이 PC 값(업무 DB 이름 · 포트)은 첫 실행에서 위 기록으로
옮긴 뒤, 그 칸들만 다를 때에 한해 커밋된 내용으로 되돌린다(다른 칸까지 고친 파일은 건드리지 않고 알린다).

    python scripts/prepare_ports.py            # 시작이 부른다
    python scripts/prepare_ports.py port 8088  # 기본 포트 8088 의 이 PC 바깥 포트
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hyd_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('it/supabase/config.toml')
SUPABASE_ENV = Path('it/supabase/.env')
RUNTIME = Path('.hyd-runtime')
BASE_NAMES = ('hyd-iot-edu', 'hyd-portal-latest')   # compose.yaml 의 name · 커밋된 config.toml 의 project_id
SUPABASE_NAME_MAX = 29                               # 이름 + '-' + 10자 ≤ 40(CLI 가 project_id 를 40자로 자른다)
# config.toml 칸 → (기본 포트 = ports.json 의 열쇠, Supabase CLI 덮어쓰기 변수). [inbucket] 은 CLI 2.119.0 에서 [local_smtp] 의 옛 이름
DB_FIELDS = {
    ('api', 'port'): (54321, 'SUPABASE_API_PORT'),
    ('db', 'port'): (54322, 'SUPABASE_DB_PORT'),
    ('db', 'shadow_port'): (54320, 'SUPABASE_DB_SHADOW_PORT'),
    ('db.pooler', 'port'): (54329, 'SUPABASE_DB_POOLER_PORT'),
    ('studio', 'port'): (54323, 'SUPABASE_STUDIO_PORT'),
    ('local_smtp', 'port'): (54324, 'SUPABASE_LOCAL_SMTP_PORT'),
    ('local_smtp', 'smtp_port'): (54325, 'SUPABASE_LOCAL_SMTP_SMTP_PORT'),
    ('local_smtp', 'pop3_port'): (54326, 'SUPABASE_LOCAL_SMTP_POP3_PORT'),
    ('analytics', 'port'): (54327, 'SUPABASE_ANALYTICS_PORT'),
    ('analytics', 'vector_port'): (54328, 'SUPABASE_ANALYTICS_VECTOR_PORT'),
}
SECTION_ALIAS = {'inbucket': 'local_smtp'}
SUPABASE_ENV_HEAD = '# 시작(scripts/prepare_ports.py)이 만드는 이 PC의 업무 DB 이름 · 포트 — Supabase CLI 가 읽는다. 손으로 고치지 않는다(git 에 올라가지 않는다).'
# 이 PC 안에서만 쓰는 확인 값 — process 만 업무 쓰기 · 메일 도구를 부르게(enterprise-sim · effects-mcp), 승인 장부 지문(cmd-gateway)
PC_SECRETS = ('PROCESS_CALLER_TOKEN', 'CMD_FINGERPRINT_KEY')
LOCAL_DSNS = {
    'SUPABASE_DSN': 'postgresql://postgres:postgres@host.docker.internal:54322/postgres',
    'ENTERPRISE_READ_DSN': 'postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@host.docker.internal:54322/postgres',
    'HYD_MCP_OAUTH_CALLBACK_URL': 'http://localhost:8088/api/mcp/connections/callback',
}


class PrepareError(RuntimeError):
    """학생에게 그대로 보이는 까닭(무엇이 · 어디서 · 무엇을 하면 되는지)."""


def norm(path) -> str:
    return str(path or '').replace('\\', '/').rstrip('/').casefold()


# ---------------------------------------------------------------- config.toml(커밋된 것 · 앞 판이 고친 것)
def read_config(text: str, where: str = str(CONFIG)) -> dict:
    """project_id · 업무 DB 포트(기본 포트 → 적힌 포트) · 로그인 주소."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PrepareError(f'{where} 를 읽을 수 없습니다({exc}). git 으로 받은 폴더면 「git checkout -- {where}」로 되돌린 뒤 다시 시작하세요.') from None
    for old, new in SECTION_ALIAS.items():
        if old in data and new not in data:
            data[new] = data[old]
    ports = {}
    for (section, key), (default, _) in DB_FIELDS.items():
        node = data
        for part in section.split('.'):
            node = node.get(part) if isinstance(node, dict) else None
        value = node.get(key) if isinstance(node, dict) else None
        if not isinstance(value, int):
            raise PrepareError(f'{where} 의 [{section}] {key} 칸이 없거나 숫자가 아닙니다.')
        ports[default] = value
    auth = data.get('auth') or {}
    return {'project_id': data.get('project_id'), 'ports': ports,
            'site_url': auth.get('site_url'), 'redirects': list(auth.get('additional_redirect_urls') or [])}


def config_shape(text: str) -> list[str]:
    """앞 판 시작이 고쳐 쓰던 칸(project_id · 업무 DB 포트 · [auth] 의 localhost 포트)만 지운 줄 목록 — 나머지가 같으면 되돌려도 된다."""
    section, out = '', []
    for line in text.replace('\r\n', '\n').split('\n'):
        if m := re.match(r'\s*\[([^]]+)\]', line):
            section = SECTION_ALIAS.get(m[1], m[1])
        if re.match(r'\s*project_id\s*=', line):
            line = 'project_id = <이 PC>'
        elif (m := re.match(r'(\s*(\w+)\s*=\s*)\d+(.*)$', line)) and (section, m[2]) in DB_FIELDS:
            line = f'{m[1]}<포트>{m[3]}'
        elif section == 'auth':
            line = re.sub(r'(https?://(?:localhost|127\.0\.0\.1)):\d+', r'\1:<포트>', line)
        out.append(line.rstrip())
    while out and not out[-1]:
        out.pop()
    return out


def committed_config(root: Path) -> str | None:
    """git 이 있는 폴더면 HEAD 의 config.toml, ZIP 폴더면 None(되돌릴 기준이 없다)."""
    if not (root / '.git').exists():
        return None
    try:
        out = subprocess.run(['git', '-C', str(root), 'show', f'HEAD:{CONFIG.as_posix()}'], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, 'stderr', b'') or str(exc).encode()
        raise PrepareError(f'git 으로 {CONFIG.as_posix()} 의 커밋된 내용을 읽지 못했습니다: {detail.decode("utf-8", "replace").strip()[:300]}') from None
    return out.stdout.decode('utf-8')


def restore_config(root: Path, current: str, committed: str | None) -> str | None:
    """앞 판이 고친 칸만 다르면 커밋된 내용으로 되돌리고 알린다. 다른 칸까지 다르면 그대로 두고 알린다. 같으면 None."""
    if committed is None or current.replace('\r\n', '\n') == committed.replace('\r\n', '\n'):
        return None
    if config_shape(current) != config_shape(committed):
        return (f'{CONFIG.as_posix()} 에 이 PC에서 고친 내용이 있어 그대로 둡니다. 다음 업데이트(git pull)가 이 파일 때문에 막히면 '
                f'강사에게 알려 주세요(이 PC의 업무 DB 이름 · 포트는 이미 .hyd-runtime 에 기록했습니다).')
    atomic_write(root / CONFIG, committed)
    return f'앞 판 시작이 {CONFIG.as_posix()} 에 써 넣었던 이 PC의 업무 DB 이름 · 포트를 기록으로 옮기고, 파일은 받은 그대로 되돌렸습니다.'


# ---------------------------------------------------------------- 이 PC의 Docker(라벨만 읽는다 — 컨테이너 환경 변수는 보지 않는다)
def _labels(kind: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    fmt = '{{json .Config.Labels}}' if kind == 'container' else '{{json .Labels}}'
    out = subprocess.check_output(['docker', kind, 'inspect', '--format', fmt, *ids], text=True, encoding='utf-8')
    return [json.loads(line) or {} for line in out.splitlines() if line.strip()]


def docker_inventory() -> dict:
    """{'compose' | 'supabase': {프로젝트 이름: {'roots': {그 컨테이너를 만든 폴더…}, 'volumes': 데이터 볼륨이 있는가}}}."""
    containers = _labels('container', subprocess.check_output(['docker', 'ps', '-aq'], text=True).split())
    volumes = _labels('volume', subprocess.check_output(['docker', 'volume', 'ls', '-q'], text=True).split())
    return inventory_from_labels(containers, volumes)


def inventory_from_labels(containers: list[dict], volumes: list[dict]) -> dict:
    inv: dict = {'compose': {}, 'supabase': {}}
    entry = lambda kind, name: inv[kind].setdefault(name, {'roots': set(), 'volumes': False})
    for labels in containers:
        if supa := labels.get('com.supabase.cli.project'):
            workdir = labels.get('com.supabase.cli.workdir') or ''
            root = workdir[:-3] if norm(workdir).endswith('/it') else workdir   # Supabase workdir 는 <폴더>/it
            if root:
                entry('supabase', supa)['roots'].add(root)
            else:
                entry('supabase', supa)
        elif project := labels.get('com.docker.compose.project'):
            workdir = labels.get('com.docker.compose.project.working_dir') or ''
            if workdir:
                entry('compose', project)['roots'].add(workdir)
            else:
                entry('compose', project)
    for labels in volumes:
        if supa := labels.get('com.supabase.cli.project'):            # Supabase 볼륨에는 compose 라벨도 같은 값으로 붙는다
            entry('supabase', supa)['volumes'] = True
        elif project := labels.get('com.docker.compose.project'):
            entry('compose', project)['volumes'] = True
    return inv


# ---------------------------------------------------------------- 이름: 같은 폴더 · 옮긴 폴더 · 복사한 폴더 · 새 폴더
def _unique(base: str, here: str, owners: dict, limit: int) -> str:
    suffix = hashlib.sha256(here.encode('utf8')).hexdigest()[:10]
    taken = lambda name: any(norm(r) != here for r in (owners.get(name) or {}).get('roots', ()))
    candidate, index = f'{base[:limit]}-{suffix}', 1
    while taken(candidate):
        index += 1
        candidate = f'{base[:limit - 3]}-{suffix}-{index}'
    return candidate


def choose_names(root, record, base, inventory, *, saved, pinned=False, exists=os.path.isdir):
    """(Compose 이름, 업무 DB 이름), 학생에게 알릴 말, 이 폴더 것으로 보는 폴더 경로(정규화) 집합.

    record   .hyd-runtime/project.json — {'root', 'compose', 'supabase'} 또는 None
    base     기록이 없을 때의 후보 이름(.env · it/supabase/.env · config.toml 에서)
    saved    기록이 없을 때 이 폴더가 앞 판으로 시작한 적이 있는가(.hyd-runtime/ports.json 이 있다)
    pinned   셸 환경의 COMPOSE_PROJECT_NAME(개발자가 고른 이름 — 바꾸지 않고 겹치면 멈춘다)
    """
    here = norm(root)
    notes: list[str] = []
    mine = {here}
    claimed = bool(record) and norm(record['root']) == here
    if claimed:
        wanted, ours = (record['compose'], record['supabase']), True
    elif record and exists(record['root']):
        wanted, ours = (record['compose'], record['supabase']), False
        notes.append(f'이 폴더는 {record["root"]} 폴더를 복사한 것입니다. 그 폴더의 실습 기록은 그 폴더에서 이어지고, 이 폴더는 빈 시스템으로 따로 시작합니다.')
    elif record:
        wanted, ours = (record['compose'], record['supabase']), True
        mine.add(norm(record['root']))
        notes.append(f'폴더를 옮긴 것으로 봅니다({record["root"]} → {root}). 실습 기록을 그대로 이어 씁니다.')
    else:
        wanted, ours = tuple(base), saved
    names = []
    for kind, name, limit in (('compose', wanted[0], 50), ('supabase', wanted[1], SUPABASE_NAME_MAX)):
        owner = inventory[kind].get(name) or {'roots': set(), 'volumes': False}
        others = sorted(r for r in owner['roots'] if norm(r) not in mine)
        live = [r for r in others if exists(r)]
        mine.update(norm(r) for r in others if not exists(r))      # 없어진 폴더가 만든 컨테이너 = 옮겨 온 이 폴더의 것
        if live and (claimed or (pinned and kind == 'compose')):
            raise PrepareError(f'다른 폴더({live[0]})가 이 폴더의 수업 시스템 이름({name})을 쓰고 있어 실습 기록을 지키려고 멈췄습니다. '
                               f'두 폴더 중 하나만 쓰세요 — 이 폴더를 쓰려면 그 폴더를 지운 뒤(실습 기록은 남습니다) 다시 시작하세요.')
        if live:
            names.append(_unique(name, here, inventory[kind], limit))
            notes.append(f'이 PC에는 다른 폴더({live[0]})의 수업 시스템이 있습니다. 그 실습 기록은 그 폴더의 시작 파일로 이어지고(새 판은 그 폴더에서 git pull), '
                         f'이 폴더는 빈 시스템으로 따로 시작합니다.')
        elif not owner['roots'] and owner['volumes'] and not ours:
            names.append(_unique(name, here, inventory[kind], limit))
            notes.append('이 PC에 어느 폴더 것인지 알 수 없는 수업 데이터가 남아 있어, 섞지 않고 이 폴더는 빈 시스템으로 따로 시작합니다.')
        else:
            names.append(name)
    return tuple(names), list(dict.fromkeys(notes)), mine


# ---------------------------------------------------------------- 포트
def available(port):
    # Binding catches other Docker projects and Windows reserved ports as well
    # as ordinary processes; a process-name whitelist cannot distinguish them.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def docker_ports(names, mine) -> tuple[set, set]:
    """(이 폴더 프로젝트가 지금 잡고 있는 바깥 포트, 켜진 컨테이너가 잡고 있는 바깥 포트 전부)."""
    ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    if not ids:
        return set(), set()
    return ports_from_containers(json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True, encoding='utf-8')), names, mine)


def ports_from_containers(containers: list[dict], names, mine) -> tuple[set, set]:
    owned, occupied = set(), set()
    for container in containers:
        labels = container['Config'].get('Labels') or {}
        if supa := labels.get('com.supabase.cli.project'):
            workdir = labels.get('com.supabase.cli.workdir') or ''
            own = supa == names[1] and norm(workdir[:-3] if norm(workdir).endswith('/it') else workdir) in mine
        else:
            own = labels.get('com.docker.compose.project') == names[0] and norm(labels.get('com.docker.compose.project.working_dir')) in mine
        for bindings in (container['NetworkSettings'].get('Ports') or {}).values():
            for binding in bindings or []:
                port = int(binding['HostPort'])
                occupied.add(port)
                if own:
                    owned.add(port)
    return owned, occupied


def allocate(defaults, previous, owned, occupied, probe=available):
    selected = {}
    reserved = set(defaults)
    for default in sorted(defaults):
        current = int(previous.get(default, default))
        if not 1 <= current <= 65535:
            raise PrepareError(f'저장된 포트 표(.hyd-runtime/ports.json)의 {default} 값 {current} 이 포트 범위(1~65535) 밖입니다. 그 파일을 지우고 다시 시작하세요.')
        def usable(port):
            return port not in selected.values() and ((port == current and port in owned) or (port not in occupied and probe(port)))
        if usable(current):
            selected[default] = current
            continue
        # Search the entire non-privileged range, including when a saved port
        # or the usual +10000 fallback is itself occupied.
        start = default + 10000 if default + 10000 <= 65535 else 1024
        for candidate in list(range(start, 65536)) + list(range(1024, start)):
            if candidate not in reserved and usable(candidate):
                selected[default] = candidate
                break
        else:
            raise PrepareError(f'포트 {default} 대신 쓸 빈 포트가 이 PC에 없습니다. 쓰지 않는 프로그램을 닫고 다시 시작하세요.')
    return selected


def rewrite_url(value, replacements):
    """Only rewrite local host endpoints, preserving custom remote DB settings."""
    url = urlsplit(value)
    if url.hostname not in {"localhost", "127.0.0.1", "host.docker.internal"}:
        return value
    if url.port not in replacements:
        return value
    netloc = url.netloc.rsplit(":", 1)[0] + ":" + str(replacements[url.port])
    return urlunsplit(url._replace(netloc=netloc))


def read_saved_ports(path: Path) -> dict[int, int]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        return {int(k): int(v) for k, v in raw.items()}
    except (ValueError, TypeError, AttributeError) as exc:
        raise PrepareError(f'저장된 포트 표({path.as_posix()})를 읽을 수 없습니다({exc}). 그 파일을 지우고 다시 시작하세요.') from None


# ---------------------------------------------------------------- 쓰기
def atomic_write(path: Path, text: str) -> None:
    temp = path.with_name(path.name + '.hyd-tmp')
    temp.write_bytes(text.encode('utf-8'))
    os.replace(temp, path)


def supabase_env_text(project_id: str, ports: dict, site_url, redirects, portal_before: set) -> str:
    def portal(url):
        for before in portal_before:
            url = re.sub(rf'(https?://(?:localhost|127\.0\.0\.1)):{before}(?=[/"\s]|$)', rf'\g<1>:{ports[8088]}', url)
        return url
    lines = [SUPABASE_ENV_HEAD, f'SUPABASE_PROJECT_ID={project_id}']
    lines += [f'{var}={ports[default]}' for default, var in DB_FIELDS.values()]
    if site_url:
        lines.append(f'SUPABASE_AUTH_SITE_URL={portal(site_url)}')
    if redirects:
        lines.append(f'SUPABASE_AUTH_ADDITIONAL_REDIRECT_URLS={",".join(portal(u) for u in redirects)}')
    return '\n'.join(lines) + '\n'


def prepare(root: Path, *, inventory=None, container_ports=None, probe=available, exists=os.path.isdir,
            environ=os.environ) -> list[str]:
    """이 폴더의 이름 · 포트를 정해 기록하고 알릴 말을 돌려준다. inventory · container_ports · probe · exists 는 Docker · 운영체제 자리."""
    runtime = root / RUNTIME
    compose_text = (root / 'compose.yaml').read_text(encoding='utf-8')
    service_ports = {int(p) for p in re.findall(r'\$\{HYD_PORT_(\d+):-', compose_text)}
    env_path = root / '.env'
    try:
        values = hyd_env.read(env_path)
        supa_values = hyd_env.read(root / SUPABASE_ENV)
    except UnicodeDecodeError:
        raise PrepareError('.env 를 UTF-8 글자로 읽을 수 없습니다. 메모장에서 열어 「다른 이름으로 저장 → 인코딩 UTF-8」로 저장한 뒤 다시 시작하세요.') from None
    config_text = (root / CONFIG).read_text(encoding='utf-8')
    config = read_config(config_text)
    record_path, ports_path = runtime / 'project.json', runtime / 'ports.json'
    record = None
    if record_path.exists():
        try:
            record = json.loads(record_path.read_text(encoding='utf-8'))
        except ValueError:
            record = None
        if not isinstance(record, dict) or not all(isinstance(record.get(k), str) and record[k] for k in ('root', 'compose', 'supabase')):
            raise PrepareError(f'{record_path.relative_to(root).as_posix()} 를 읽을 수 없습니다. 그 파일을 지우고 다시 시작하세요.')
    pinned = environ.get('COMPOSE_PROJECT_NAME')
    inventory = docker_inventory() if inventory is None else inventory
    # 기록이 없을 때(앞 판에서 올라온 첫 실행): 이 폴더가 띄운 컨테이너의 이름이 가장 센 근거다(.env 에 이름 줄이 없어도 이어받는다)
    built_here = lambda kind: sorted(n for n, o in inventory[kind].items() if any(norm(r) == norm(root) for r in o['roots']))
    local_compose, local_supabase = built_here('compose'), built_here('supabase')
    base = (pinned or values.get('COMPOSE_PROJECT_NAME') or (local_compose[0] if len(local_compose) == 1 else BASE_NAMES[0]),
            supa_values.get('SUPABASE_PROJECT_ID') or config['project_id'] or BASE_NAMES[1])
    if not supa_values.get('SUPABASE_PROJECT_ID') and len(local_supabase) == 1 and base[1] not in local_supabase:
        base = (base[0], local_supabase[0])
    if pinned and record and record['compose'] != pinned:
        record = dict(record, compose=pinned)
    names, notes, mine = choose_names(root, record, base, inventory,
                                      saved=ports_path.exists(), pinned=bool(pinned), exists=exists)
    saved = read_saved_ports(ports_path)
    previous = {p: int(saved.get(p) or values.get(f'HYD_PORT_{p}') or p) for p in service_ports}
    for default, var in DB_FIELDS.values():
        previous[default] = int(saved.get(default) or supa_values.get(var) or config['ports'][default])
    owned, occupied = docker_ports(names, mine) if container_ports is None else ports_from_containers(container_ports, names, mine)
    ports = allocate(service_ports | {d for d, _ in DB_FIELDS.values()}, previous, owned, occupied, probe)

    updates = {'COMPOSE_PROJECT_NAME': names[0], **{f'HYD_PORT_{p}': str(port) for p, port in ports.items()},
               'HYD_PORTS': ' '.join(f'{p}={port}' for p, port in sorted(ports.items()) if p != port)}
    replacements = {54322: ports[54322], 8088: ports[8088], previous[54322]: ports[54322], previous[8088]: ports[8088]}
    for key, default in LOCAL_DSNS.items():
        updates[key] = rewrite_url(values.get(key, default), replacements)
    if values.get('EFFECTS_SMTP_PORT', str(previous[54325])) == str(previous[54325]):
        updates['EFFECTS_SMTP_PORT'] = str(ports[54325])
    for key in PC_SECRETS:                            # 없을 때 한 번만 만든다(있는 값은 그대로 — 바꾸면 진행 중인 승인 장부가 어긋난다)
        if not values.get(key, '').strip():
            updates[key] = secrets.token_urlsafe(32)
    supa_path = root / SUPABASE_ENV
    if supa_path.exists() and not supa_path.read_text(encoding='utf-8').startswith(SUPABASE_ENV_HEAD):
        raise PrepareError(f'{SUPABASE_ENV.as_posix()} 가 시작이 만든 파일이 아닙니다. 그 안의 값을 다른 곳에 옮긴 뒤 파일을 지우고 다시 시작하세요.')

    runtime.mkdir(exist_ok=True)
    hyd_env.write_updates(env_path, updates)
    atomic_write(supa_path, supabase_env_text(names[1], ports, config['site_url'], config['redirects'], {8088, previous[8088]}))
    atomic_write(ports_path, json.dumps({str(k): v for k, v in sorted(ports.items())}, indent=2) + '\n')
    atomic_write(record_path, json.dumps({'root': str(root), 'compose': names[0], 'supabase': names[1]}, ensure_ascii=False, indent=2) + '\n')
    try:
        committed = committed_config(root)
    except PrepareError as exc:                       # 시작은 계속한다 — 되돌리지 못한 까닭을 그대로 보인다
        notes.append(f'{exc} 그래서 {CONFIG.as_posix()} 는 그대로 둡니다.')
    else:
        if note := restore_config(root, config_text, committed):
            notes.append(note)
    moved =[f'{p}→{port}' for p, port in sorted(ports.items()) if p != port and port != previous.get(p)]
    if moved:
        notes.append('다른 프로그램이 쓰는 포트를 피해 옮겼습니다: ' + ' · '.join(moved) + ' (포털 주소는 시작이 끝날 때 다시 보여 줍니다).')
    return notes


def saved_port(root: Path, default: int) -> int:
    ports = read_saved_ports(root / RUNTIME / 'ports.json')
    if not ports:
        raise PrepareError('포트 표(.hyd-runtime/ports.json)가 없습니다. 시작 파일을 먼저 실행하세요.')
    return ports.get(default, default)


def main(argv: list[str], root: Path = ROOT) -> int:
    args = argv[1:]
    try:
        if args == []:
            for note in prepare(root):
                print(note)
            return 0
        if len(args) == 2 and args[0] == 'port' and args[1].isdigit():
            print(saved_port(root, int(args[1])))
            return 0
    except (PrepareError, hyd_env.EnvFileError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, subprocess.CalledProcessError) as exc:
        # 명령 · 파일 이름까지만 보인다(.env 값은 예외 글에 들어가지 않는다)
        print(f'포트 준비가 실패했습니다 — {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    print('사용: prepare_ports.py | prepare_ports.py port <기본 포트>', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
