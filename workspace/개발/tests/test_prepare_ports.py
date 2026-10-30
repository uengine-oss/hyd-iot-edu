"""시작 2단계(scripts/prepare_ports.py) — 이 폴더 · 이 PC의 프로젝트 이름과 포트를 정하고, git 이 추적하는 파일은 바꾸지 않는다.

규칙(정답의 출처):
  · 시작 뒤 `git status` 에 바뀐 파일이 없다(인수조건 22). 이 PC 값은 .hyd-runtime/ · .env · it/supabase/.env(모두 git 밖)에만.
  · 앞 판 시작이 config.toml 에 써 넣은 업무 DB 이름 · 포트를 이어받아 기존 볼륨(supabase_db_<이름>)에 그대로 붙는다.
  · 같은 폴더(두 번째 · 껐다 켜기 · 컨테이너만 지운 경우)는 이름 · 포트가 그대로, 옮긴 폴더는 실습 기록을 이어 쓰고,
    복사한 폴더 · 다른 폴더가 있는 새 폴더는 원래 폴더의 데이터를 건드리지 않고 따로 시작하며 그 사실을 알린다.
Docker · 운영체제는 바깥이라 대체물을 쓴다: 컨테이너 · 볼륨 라벨(이 PC에서 읽은 실제 모양), 포트 빈자리(probe), 폴더 존재(exists).
git 은 실제 git 으로 임시 저장소를 만든다.
"""
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

import hyd_env
import prepare_ports as pp

REPO = Path(__file__).resolve().parents[3]
FREE = lambda port: True


def committed_config() -> str:
    return subprocess.run(['git', '-C', str(REPO), 'show', 'HEAD:it/supabase/config.toml'], capture_output=True, check=True).stdout.decode('utf-8')


def dirty_config(project_id='hyd-system-audit-20261026', shift=10000, portal=8088) -> str:
    """앞 판 시작(옛 prepare_ports)이 고쳐 쓴 모양 — project_id 와 업무 DB 포트, [auth] 의 포털 포트만 다르다."""
    text = committed_config()
    text = text.replace('project_id = "hyd-portal-latest"', f'project_id = "{project_id}"')
    for port in (54321, 54322, 54323, 54324, 54325, 54326):
        text = text.replace(f'= {port}\n', f'= {port + shift}\n')
    return text.replace('localhost:8088', f'localhost:{portal}')


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True, text=True, encoding='utf-8').stdout


def make_checkout(root: Path, *, config=None, env='LLM_API_KEY=\n', commit=True) -> Path:
    """학생이 받은 폴더 한 벌(시작이 읽는 파일만): compose.yaml · .gitignore · config.toml · .env."""
    (root / 'it' / 'supabase').mkdir(parents=True)
    shutil.copyfile(REPO / 'compose.yaml', root / 'compose.yaml')
    shutil.copyfile(REPO / '.gitignore', root / '.gitignore')
    (root / 'it' / 'supabase' / 'config.toml').write_text(committed_config(), encoding='utf-8', newline='\n')
    if commit:
        git(root, 'init', '-q')
        git(root, '-c', 'user.email=t@t', '-c', 'user.name=t', 'add', 'compose.yaml', '.gitignore', 'it/supabase/config.toml')
        git(root, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'base')
    if config is not None:
        (root / 'it' / 'supabase' / 'config.toml').write_text(config, encoding='utf-8', newline='\n')
    (root / '.env').write_text(env, encoding='utf-8')
    return root


def remove_tree(path):
    """git 객체 파일은 읽기 전용이라 Windows 에서 지우기 전에 쓰기 권한을 준다."""
    shutil.rmtree(path, onexc=lambda fn, p, exc: (os.chmod(p, stat.S_IWRITE), fn(p)))


def empty_inventory():
    return {'compose': {}, 'supabase': {}}


def run(root, inventory=None, *, probe=FREE, exists=None, environ=None, container_ports=()):
    return pp.prepare(root, inventory=inventory or empty_inventory(), container_ports=list(container_ports), probe=probe,
                      exists=exists or (lambda p: Path(p).is_dir()), environ=environ or {})


def outputs(root: Path) -> dict:
    return {name: (root / name).read_bytes() for name in ('.env', 'it/supabase/.env', '.hyd-runtime/ports.json', '.hyd-runtime/project.json')}


def record(root):
    return json.loads((root / '.hyd-runtime' / 'project.json').read_text(encoding='utf-8'))


def ports(root):
    return {int(k): v for k, v in json.loads((root / '.hyd-runtime' / 'ports.json').read_text(encoding='utf-8')).items()}


# ---------------------------------------------------------------- git 이 추적하는 파일을 바꾸지 않는다
@pytest.mark.parametrize('config', [None, dirty_config(), dirty_config('hyd-portal-latest-05e566f4a3', 10000, 18088)],
                         ids=['받은_그대로', '앞_판이_이름_포트를_고침', '앞_판이_포털_포트까지_고침'])
@pytest.mark.parametrize('busy', [(), (8088, 54322, 54324)], ids=['포트_비어_있음', '포털_업무DB_메일함_포트를_남이_씀'])
def test_시작_뒤_git_status에_바뀐_파일이_없다(tmp_path, config, busy):
    root = make_checkout(tmp_path / 'hyd', config=config)
    run(root, probe=lambda p: p not in busy)
    run(root, probe=lambda p: p not in busy)                          # 두 번째 시작도
    assert git(root, 'status', '--porcelain') == ''


def test_앞_판이_고친_config의_업무_DB_이름과_포트를_이어받아_같은_볼륨에_붙는다(tmp_path):
    root = make_checkout(tmp_path / 'hyd', config=dirty_config(), env='COMPOSE_PROJECT_NAME=hyd-system-audit-20261026\n')
    (root / '.hyd-runtime').mkdir()
    (root / '.hyd-runtime' / 'ports.json').write_text(json.dumps({'54322': 64322, '8088': 8088}), encoding='utf-8')
    here = str(root)
    inventory = {'compose': {'hyd-system-audit-20261026': {'roots': {here}, 'volumes': True}},
                 'supabase': {'hyd-system-audit-20261026': {'roots': {here}, 'volumes': True},
                              'hyd-portal-latest': {'roots': set(), 'volumes': True}}}   # 다른 사본이 남긴 옛 볼륨
    run(root, inventory)
    supa = hyd_env.read(root / 'it' / 'supabase' / '.env')
    assert supa['SUPABASE_PROJECT_ID'] == 'hyd-system-audit-20261026'
    assert supa['SUPABASE_DB_PORT'] == '64322' and supa['SUPABASE_API_PORT'] == '64321' and supa['SUPABASE_LOCAL_SMTP_SMTP_PORT'] == '64325'
    assert record(root)['supabase'] == 'hyd-system-audit-20261026' and record(root)['compose'] == 'hyd-system-audit-20261026'
    assert (root / 'it' / 'supabase' / 'config.toml').read_text(encoding='utf-8') == committed_config()


def test_기록도_env_이름_줄도_없으면_이_폴더가_띄운_컨테이너의_이름을_이어받는다(tmp_path):
    """앞 판에서 올라온 PC: .env 에 COMPOSE_PROJECT_NAME 이 없고 config.toml 은 받은 그대로여도, 이 폴더가 띄운 스택에 붙는다
    (다른 사본이 남긴 기본 이름 볼륨 hyd-iot-edu_* · supabase_db_hyd-portal-latest 에 붙지 않는다)."""
    root = make_checkout(tmp_path / 'hyd')
    (root / '.hyd-runtime').mkdir()
    (root / '.hyd-runtime' / 'ports.json').write_text('{"8088": 8088}', encoding='utf-8')
    here = str(root)
    inventory = {'compose': {'hyd-iot-edu': {'roots': set(), 'volumes': True},
                             'hyd-system-audit-20261026': {'roots': {here}, 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': set(), 'volumes': True},
                              'hyd-system-audit-20261026': {'roots': {here}, 'volumes': True}}}
    run(root, inventory)
    assert (record(root)['compose'], record(root)['supabase']) == ('hyd-system-audit-20261026', 'hyd-system-audit-20261026')


@pytest.mark.parametrize('edit, restored', [
    (lambda t: t, False),                                                        # 받은 그대로 — 할 일 없음
    (lambda t: dirty_config(), True),                                            # 앞 판이 고친 칸만 다름 → 되돌림
    (lambda t: dirty_config().replace('enable_signup = true', 'enable_signup = false', 1), False),   # 다른 칸도 고침 → 그대로
    (lambda t: t.replace('[inbucket]', '[local_smtp]'), False),                  # 이 PC에서 섹션 이름을 고침 → 그대로
], ids=['받은_그대로', '앞_판이_고친_칸만', '다른_칸도_고침', '섹션_이름을_고침'])
def test_config는_앞_판이_고친_칸만_다를_때만_받은_그대로_되돌린다(tmp_path, edit, restored):
    root = make_checkout(tmp_path / 'hyd')
    current = edit(committed_config())
    (root / 'it' / 'supabase' / 'config.toml').write_text(current, encoding='utf-8', newline='\n')
    note = pp.restore_config(root, current, committed_config())
    after = (root / 'it' / 'supabase' / 'config.toml').read_text(encoding='utf-8')
    if current == committed_config():
        assert note is None and after == current
    elif restored:
        assert after == committed_config() and '되돌렸습니다' in note
    else:
        assert after == current and '그대로 둡니다' in note


def test_git_없는_ZIP_폴더에서도_시작한다(tmp_path):
    root = make_checkout(tmp_path / 'hyd', config=dirty_config(), commit=False)
    notes = run(root)
    assert hyd_env.read(root / 'it' / 'supabase' / '.env')['SUPABASE_PROJECT_ID'] == 'hyd-system-audit-20261026'
    assert not any('되돌' in n for n in notes)


# ---------------------------------------------------------------- 처음 · 두 번째 · 껐다 켜기 · 컨테이너만 지운 경우
def test_처음_시작은_기본_이름과_기본_포트를_쓴다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    notes = run(root)
    assert record(root) == {'root': str(root), 'compose': 'hyd-iot-edu', 'supabase': 'hyd-portal-latest'}
    assert all(k == v for k, v in ports(root).items()) and notes == []
    env = hyd_env.read(root / '.env')
    assert env['COMPOSE_PROJECT_NAME'] == 'hyd-iot-edu' and env['HYD_PORT_8088'] == '8088' and env['HYD_PORTS'] == ''


@pytest.mark.parametrize('state', ['running', 'stopped', 'containers_removed'])
def test_두_번째_시작은_같은_이름_같은_포트에_파일도_그대로다(tmp_path, state):
    root = make_checkout(tmp_path / 'hyd')
    run(root, probe=lambda p: p != 8088)                       # 처음: 8088 을 다른 프로그램이 써서 옮김
    first = outputs(root)
    here = str(root)
    roots = set() if state == 'containers_removed' else {here}
    inventory = {'compose': {'hyd-iot-edu': {'roots': roots, 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': roots, 'volumes': True}}}
    portal = ports(root)[8088]
    running = [{'Config': {'Labels': {'com.docker.compose.project': 'hyd-iot-edu', 'com.docker.compose.project.working_dir': here}},
                'NetworkSettings': {'Ports': {'80/tcp': [{'HostPort': str(portal)}]}}}] if state == 'running' else []
    # 켜져 있으면 우리 컨테이너가 그 포트를 잡고 있어 probe 는 실패하지만 우리 것이라 다시 쓴다
    notes = run(root, inventory, probe=lambda p: p not in (8088, portal) if state == 'running' else p != 8088, container_ports=running)
    assert outputs(root) == first and notes == []


# ---------------------------------------------------------------- 새 폴더 · 옮긴 폴더 · 복사한 폴더
def test_옮긴_폴더는_이름을_이어받아_실습_기록을_이어_쓴다(tmp_path):
    old = make_checkout(tmp_path / 'old')
    run(old)
    new = tmp_path / 'new'
    shutil.copytree(old, new)
    remove_tree(old)
    inventory = {'compose': {'hyd-iot-edu': {'roots': {str(old)}, 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': {str(old)}, 'volumes': True}}}
    notes = run(new, inventory)
    assert (record(new)['compose'], record(new)['supabase']) == ('hyd-iot-edu', 'hyd-portal-latest')
    assert record(new)['root'] == str(new) and any('옮긴' in n for n in notes)


def test_복사한_폴더는_원래_폴더의_시스템을_건드리지_않고_따로_시작한다(tmp_path):
    original = make_checkout(tmp_path / 'original')
    run(original)
    copy = tmp_path / 'copy'
    shutil.copytree(original, copy)
    inventory = {'compose': {'hyd-iot-edu': {'roots': {str(original)}, 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': {str(original)}, 'volumes': True}}}
    notes = run(copy, inventory)
    names = (record(copy)['compose'], record(copy)['supabase'])
    assert names[0].startswith('hyd-iot-edu-') and names[1].startswith('hyd-portal-latest-')
    assert len(names[1]) <= 40                                       # Supabase CLI 가 40자로 자른다
    assert any(str(original) in n for n in notes)
    assert record(original)['compose'] == 'hyd-iot-edu'               # 원래 폴더의 기록은 그대로


def test_다른_폴더의_시스템이_있는_새_폴더는_그_폴더를_알려_주고_따로_시작한다(tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    root = make_checkout(tmp_path / 'hyd')
    inventory = {'compose': {'hyd-iot-edu': {'roots': {str(other)}, 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': {str(other)}, 'volumes': True}}}
    notes = run(root, inventory)
    assert record(root)['compose'] != 'hyd-iot-edu' and any(str(other) in n and 'git pull' in n for n in notes)


def test_지워진_폴더가_남긴_시스템은_새_폴더가_이어받는다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    gone = str(tmp_path / 'deleted')
    inventory = {'compose': {'hyd-iot-edu': {'roots': {gone}, 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': {gone}, 'volumes': True}}}
    run(root, inventory)
    assert (record(root)['compose'], record(root)['supabase']) == ('hyd-iot-edu', 'hyd-portal-latest')


@pytest.mark.parametrize('saved, adopted', [(False, False), (True, True)])
def test_주인을_모르는_볼륨은_이_폴더가_전에_시작한_적이_있을_때만_이어받는다(tmp_path, saved, adopted):
    root = make_checkout(tmp_path / 'hyd')
    if saved:                                                         # 앞 판 시작이 남긴 포트 표 = 이 폴더가 쓰던 볼륨(컨테이너만 지운 경우)
        (root / '.hyd-runtime').mkdir()
        (root / '.hyd-runtime' / 'ports.json').write_text('{"8088": 8088}', encoding='utf-8')
    inventory = {'compose': {'hyd-iot-edu': {'roots': set(), 'volumes': True}},
                 'supabase': {'hyd-portal-latest': {'roots': set(), 'volumes': True}}}
    notes = run(root, inventory)
    assert (record(root)['supabase'] == 'hyd-portal-latest') is adopted
    assert any('알 수 없는' in n for n in notes) is not adopted


def test_이_폴더의_이름을_다른_살아_있는_폴더가_쓰면_데이터를_지키려고_멈춘다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    run(root)
    other = tmp_path / 'other'
    other.mkdir()
    inventory = {'compose': {'hyd-iot-edu': {'roots': {str(other)}, 'volumes': True}}, 'supabase': {}}
    with pytest.raises(pp.PrepareError, match='other'):
        run(root, inventory)


def test_개발자가_고른_compose_이름은_바꾸지_않고_겹치면_멈춘다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    other = tmp_path / 'other'
    other.mkdir()
    inventory = {'compose': {'dev': {'roots': {str(other)}, 'volumes': False}}, 'supabase': {}}
    with pytest.raises(pp.PrepareError):
        run(root, inventory, environ={'COMPOSE_PROJECT_NAME': 'dev'})


# ---------------------------------------------------------------- 포트 · 주소
def test_포털_포트가_겹치면_옮기고_업무_DB_로그인_주소도_따라간다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    notes = run(root, probe=lambda p: p not in (8088, 54322))
    portal, db = ports(root)[8088], ports(root)[54322]
    assert portal != 8088 and db != 54322
    env, supa = hyd_env.read(root / '.env'), hyd_env.read(root / 'it' / 'supabase' / '.env')
    assert env['HYD_PORT_8088'] == str(portal) and f'8088={portal}' in env['HYD_PORTS'].split()
    assert f':{db}/' in env['SUPABASE_DSN'] and supa['SUPABASE_DB_PORT'] == str(db)
    assert supa['SUPABASE_AUTH_SITE_URL'] == f'http://localhost:{portal}'
    assert any(f'8088→{portal}' in n for n in notes)


def test_원격_업무_DB_주소는_바꾸지_않는다(tmp_path):
    remote = 'postgresql://u:p@db.example.com:5432/postgres'
    root = make_checkout(tmp_path / 'hyd', env=f'SUPABASE_DSN={remote}\n')
    run(root, probe=lambda p: p != 54322)
    assert hyd_env.read(root / '.env')['SUPABASE_DSN'] == remote


def test_빈_포트가_없으면_무엇을_할지_알리고_멈춘다():
    with pytest.raises(pp.PrepareError, match='빈 포트'):
        pp.allocate({8088}, {}, set(), set(), probe=lambda p: False)


@pytest.mark.parametrize('content', ['{망가짐', '{"8088": "글자"}', '[1, 2]'])
def test_망가진_포트_표는_그_파일을_가리키며_멈춘다(tmp_path, content):
    root = make_checkout(tmp_path / 'hyd')
    (root / '.hyd-runtime').mkdir()
    (root / '.hyd-runtime' / 'ports.json').write_text(content, encoding='utf-8')
    with pytest.raises(pp.PrepareError, match='ports.json'):
        run(root)


@pytest.mark.parametrize('content', ['{망가짐', '[]', '{"root": "x"}', '{"root": "", "compose": "a", "supabase": "b"}'])
def test_망가진_폴더_기록은_그_파일을_가리키며_멈춘다(tmp_path, content):
    root = make_checkout(tmp_path / 'hyd')
    (root / '.hyd-runtime').mkdir()
    (root / '.hyd-runtime' / 'project.json').write_text(content, encoding='utf-8')
    with pytest.raises(pp.PrepareError, match='project.json'):
        run(root)


def test_다른_인코딩으로_저장한_env는_다시_저장하라고_알린다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    (root / '.env').write_bytes('# 수업 키\nLLM_API_KEY=\n'.encode('cp949'))
    with pytest.raises(pp.PrepareError, match='UTF-8'):
        run(root)


def test_시작이_만들지_않은_업무_DB_env는_덮어쓰지_않는다(tmp_path):
    root = make_checkout(tmp_path / 'hyd')
    (root / 'it' / 'supabase' / '.env').write_text('SUPABASE_AUTH_EXTERNAL_GITHUB_SECRET=x\n', encoding='utf-8')
    with pytest.raises(pp.PrepareError, match='it/supabase/.env'):
        run(root)
    assert (root / 'it' / 'supabase' / '.env').read_text(encoding='utf-8') == 'SUPABASE_AUTH_EXTERNAL_GITHUB_SECRET=x\n'


def test_실패하면_까닭을_보이고_1로_끝난다(tmp_path, capsys):
    root = make_checkout(tmp_path / 'hyd')
    (root / '.hyd-runtime').mkdir()
    (root / '.hyd-runtime' / 'ports.json').write_text('{망가짐', encoding='utf-8')
    assert pp.main(['prepare_ports.py', 'port', '8088'], root=root) == 1
    assert 'ports.json' in capsys.readouterr().err


def test_포트_조회는_저장된_바깥_포트를_낸다(tmp_path, capsys):
    root = make_checkout(tmp_path / 'hyd')
    run(root, probe=lambda p: p != 8088)
    assert pp.main(['prepare_ports.py', 'port', '8088'], root=root) == 0
    assert int(capsys.readouterr().out) == ports(root)[8088] != 8088


# ---------------------------------------------------------------- compose 가 시작에게 요구하는 값
def test_compose가_시작에게_요구하는_값은_시작이_모두_env에_적는다(tmp_path):
    """compose.yaml 의 ${이름:?…} 는 「시작 파일이 정한다」는 뜻 — 시작 2단계(키 판정 + 포트 준비) 뒤 .env 에 모두 있어야 한다."""
    import re
    root = make_checkout(tmp_path / 'hyd')
    assert hyd_env.main(['hyd_env.py', 'ai-mode'], root=root) == 0
    run(root)
    required = set(re.findall(r'\$\{([A-Z_0-9]+):\?', (REPO / 'compose.yaml').read_text(encoding='utf-8')))
    env = hyd_env.read(root / '.env')
    assert required and not {k for k in required if not env.get(k)}


def test_내부_확인_값은_처음_한_번_만들고_다음_시작은_그대로_둔다(tmp_path):
    root = make_checkout(tmp_path / 'hyd', env='LLM_API_KEY=\nCMD_FINGERPRINT_KEY=teacher-key\n')    # 강사가 정해 둔 값
    run(root)
    first = hyd_env.read(root / '.env')
    run(root)
    second = hyd_env.read(root / '.env')
    assert len(first['PROCESS_CALLER_TOKEN']) >= 32 and first['PROCESS_CALLER_TOKEN'] == second['PROCESS_CALLER_TOKEN']
    assert first['CMD_FINGERPRINT_KEY'] == second['CMD_FINGERPRINT_KEY'] == 'teacher-key'
    other = make_checkout(tmp_path / 'other')
    run(other)
    assert hyd_env.read(other / '.env')['PROCESS_CALLER_TOKEN'] != first['PROCESS_CALLER_TOKEN']   # PC(폴더)마다 다른 값


# ---------------------------------------------------------------- 이 PC의 Docker 라벨 읽기
def test_라벨에서_폴더를_읽고_업무_DB_볼륨을_compose_볼륨으로_세지_않는다():
    containers = [
        {'com.docker.compose.project': 'hyd-system-audit-20261026', 'com.docker.compose.project.working_dir': 'D:\\work\\hyd'},
        {'com.supabase.cli.project': 'hyd-system-audit-20261026', 'com.supabase.cli.workdir': 'D:\\work\\hyd\\it'},
    ]
    volumes = [{'com.supabase.cli.project': 'hyd-portal-latest', 'com.docker.compose.project': 'hyd-portal-latest'},
               {'com.docker.compose.project': 'hyd-iot-edu'}]
    inv = pp.inventory_from_labels(containers, volumes)
    assert inv['supabase']['hyd-system-audit-20261026']['roots'] == {'D:\\work\\hyd'}
    assert inv['supabase']['hyd-portal-latest'] == {'roots': set(), 'volumes': True}
    assert 'hyd-portal-latest' not in inv['compose'] and inv['compose']['hyd-iot-edu']['volumes'] is True
