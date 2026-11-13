"""서비스 이미지 — compose 가 띄우는 서비스마다, 그 Dockerfile 이 이미지에 넣는 폴더만으로 진입 모듈이 가져와지는가, 이미지 판(Python 3.12)
문법인가, 서비스끼리 · 개발 환경과 라이브러리 판이 같은가.

지운 모듈을 다른 서비스가 아직 가져오면 스택이 켜지지 않는다(2026-10-30 실측: agent 서비스의 LLM 도우미 모듈을 지운 뒤 dmn-mcp 가 ImportError 로
「unhealthy」, 시작.bat 4단계에서 멈춤). Dockerfile 의 COPY 줄대로 /srv 를 임시 폴더에 만들고, 컨테이너가 받는 환경(Dockerfile ENV + compose 의
environment — 학생 PC 기본값, 시작 파일이 정하는 ${…:?} 값은 시험 값)만으로 CMD 의 모듈을 실제로 가져온다. 컨테이너 안 절대 경로(/srv · /data …)는
임시 폴더 아래로 옮긴다. 이 테스트 묶음이 바꾼 환경(conftest)은 물려주지 않는다 — 운영체제가 파이썬을 띄우는 데 필요한 값만 넘긴다.
라이브러리 판의 정본은 서비스 요구 파일이다. 개발 환경(workspace/requirements-dev.txt — 서비스 요구 파일을 그대로 읽는다)이 그 판이어야 테스트가
이미지와 같은 라이브러리로 서비스 코드를 돈다.
"""
import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest
import yaml

from conftest import ROOT
COMPOSE = yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf8'))['services']
DOCKERFILES = sorted(p for p in ROOT.glob('**/Dockerfile') if 'workspace' not in p.parts and '작업' not in p.parts)
BUILT = {name: ROOT / svc['build']['dockerfile'] for name, svc in COMPOSE.items() if 'dockerfile' in (svc.get('build') or {})}
REQUIREMENTS = sorted({p.parent / 'requirements.txt' for p in DOCKERFILES if (p.parent / 'requirements.txt').exists()})
IMAGE_PYTHON = (3, 12)                     # 모든 서비스 Dockerfile 의 FROM python:3.12-slim
# 시작 파일이 .env 에 정하는 값(compose 의 ${이름:?…}) — 키 없는 학생 PC 처음 시작과 같은 모양의 시험 값
STARTED = {'AI_MODE': 'replay'}
OS_ENV = ('SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'COMSPEC', 'TEMP', 'TMP', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA',
          'LOCALAPPDATA', 'PROGRAMDATA', 'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'OS', 'HOME', 'LANG')


def image_layout(dockerfile):
    """COPY <저장소 경로> /srv/<이름> 줄 → [(원본, /srv 아래 이름)], ENV 값, CMD 의 모듈 이름."""
    text = dockerfile.read_text(encoding='utf8')
    copies = [(ROOT / src, dst[len('/srv/'):]) for src, dst in re.findall(r'^COPY\s+(\S+)\s+(/srv/\S+)\s*$', text, re.M)
              if not dst.endswith('requirements.txt')]
    env = {}
    for line in re.findall(r'^ENV\s+(.+)$', text, re.M):
        env.update(word.split('=', 1) for word in shlex.split(line))
    cmd = re.search(r'^CMD\s+\[(.+)\]\s*$', text, re.M).group(1)
    words = [w.strip().strip('"') for w in cmd.split(',')]
    module = words[words.index('-m') + 1] if '-m' in words else words[1].split(':')[0]
    return copies, env, module


def build_srv(dockerfile, into):
    copies, env, module = image_layout(dockerfile)
    for src, name in copies:
        assert src.exists(), f'{dockerfile.relative_to(ROOT)}: COPY 원본 {src.relative_to(ROOT)} 이 없다'
        target = into / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy2(src, target)
    return env, module


def compose_value(name, value):
    """compose 가 컨테이너에 넣는 값: ${이름:-기본} → 기본(학생 PC 기본), ${이름:?…} → 시작 파일이 정하는 시험 값."""
    def one(m):
        var, op, rest = m.group(1), m.group(2), m.group(3)
        if op == ':-':
            return rest
        if op == ':?':
            return STARTED.get(var, f'test-{var.lower()}')
        raise AssertionError(f'compose 의 {name}: 기본값 없는 ${{{var}}} — 학생 PC에서 무엇이 들어가는지 알 수 없다')
    return re.sub(r'\$\{(\w+)(:-|:\?)?([^}]*)\}', one, str(value))


def container_env(service, srv: Path):
    """컨테이너가 받는 환경 — 컨테이너 안 절대 경로는 임시 폴더로(/srv = 이미지 작업 폴더)."""
    dockerfile = BUILT[service]
    env, module = build_srv(dockerfile, srv)
    env.update({k: compose_value(f'{service}.{k}', v) for k, v in (COMPOSE[service].get('environment') or {}).items() if v is not None})
    def local(value):
        if not value.startswith('/'):
            return value
        path = srv / value[len('/srv/'):] if value.startswith('/srv/') else srv / '_root' / value.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)
    env = {k: local(v) for k, v in env.items()}
    return env, module


@pytest.mark.parametrize('service', sorted(BUILT))
def test_이미지에_넣는_폴더와_컨테이너_환경만으로_진입_모듈이_가져와진다(service, tmp_path):
    env, module = container_env(service, tmp_path)
    if 'HYD_WORKER_RUNTIME_KEY_FILE' in env:                       # process 가 만들고 워커가 읽는 인증 파일 — 이 PC에서 시작한 뒤의 모양
        Path(env['HYD_WORKER_RUNTIME_KEY_FILE']).write_text('k' * 48, encoding='utf8')
    env |= {k: os.environ[k] for k in OS_ENV if k in os.environ}
    run = subprocess.run([sys.executable, '-I', '-c', f'import sys; sys.path.insert(0, "."); import {module}'],
                         cwd=tmp_path, env=env, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=180)
    tail = '\n'.join((run.stderr or '').strip().splitlines()[-4:])
    assert run.returncode == 0, f'{service}({BUILT[service].relative_to(ROOT)}): `import {module}` 실패\n{tail}'


def test_저장소의_Dockerfile은_모두_compose_서비스가_쓴다():
    unused = sorted(str(p.relative_to(ROOT)) for p in DOCKERFILES if p not in BUILT.values())
    assert not unused, f'어느 compose 서비스도 빌드하지 않는 Dockerfile: {unused}'


@pytest.mark.parametrize('dockerfile', DOCKERFILES, ids=[str(p.parent.relative_to(ROOT)) for p in DOCKERFILES])
def test_이미지에_넣는_파이썬_파일은_이미지_판_문법이다(dockerfile):
    copies, _, _ = image_layout(dockerfile)
    bad = []
    for src, _ in copies:
        for py in ([src] if src.is_file() else src.rglob('*.py')) if src.suffix in ('', '.py') else []:
            try:
                ast.parse(py.read_text(encoding='utf8'), filename=str(py), feature_version=IMAGE_PYTHON)
            except SyntaxError as exc:
                bad.append(f'{py.relative_to(ROOT)}:{exc.lineno} {exc.msg}')
    assert not bad, f'Python {IMAGE_PYTHON[0]}.{IMAGE_PYTHON[1]} 에서 읽히지 않는 파일: ' + '; '.join(bad)


def test_가져오기에_실패하는_모듈은_잡힌다(tmp_path):
    """이 테스트가 무엇을 잡는지의 확인: 진입 모듈이 없는 모듈을 가져오면 같은 방식의 실행이 실패한다."""
    (tmp_path / 'svc').mkdir()
    (tmp_path / 'svc' / '__init__.py').write_text('', encoding='utf8')
    (tmp_path / 'svc' / 'main.py').write_text('from svc import removed_module\n', encoding='utf8')
    run = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, "."); import svc.main'],
                         cwd=tmp_path, capture_output=True, text=True, encoding='utf8', errors='replace')
    assert run.returncode != 0 and 'ImportError' in run.stderr


# ---------------------------------------------------------------- 라이브러리 판(정본 = 서비스 요구 파일)
def pins(path: Path) -> dict[str, str]:
    """요구 파일의 `이름[extra]==판` 줄 → {정규화한 이름: 판}. git+ · 범위(>=)는 고정이 아니라 뺀다."""
    out = {}
    for line in path.read_text(encoding='utf8').splitlines():
        line = line.split('#', 1)[0].strip()
        if m := re.fullmatch(r'([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*==\s*(\S+)', line):
            out[re.sub(r'[-_.]+', '-', m.group(1)).lower()] = m.group(2)
    return out


def test_서비스_요구_파일끼리_같은_라이브러리를_다른_판으로_고정하지_않는다():
    seen: dict[str, dict[str, list[str]]] = {}
    for req in REQUIREMENTS:
        for name, version in pins(req).items():
            seen.setdefault(name, {}).setdefault(version, []).append(str(req.parent.relative_to(ROOT)))
    split = {name: versions for name, versions in seen.items() if len(versions) > 1}
    assert not split, '서비스마다 판이 다른 라이브러리(한 판으로 맞춘다): ' + '; '.join(
        f'{name} ' + ' · '.join(f'{v}({", ".join(where)})' for v, where in versions.items()) for name, versions in sorted(split.items()))


def test_개발_환경의_라이브러리는_서비스_고정판과_같다():
    wanted = {}
    for req in REQUIREMENTS:
        wanted.update(pins(req))
    differ = []
    for name, version in sorted(wanted.items()):
        try:
            got = metadata.version(name)
        except metadata.PackageNotFoundError:
            got = '없음'
        if got != version:
            differ.append(f'{name} 개발 {got} · 서비스 {version}')
    assert not differ, ('테스트가 서비스와 다른 판으로 돈다 — `pip install -r workspace/requirements-dev.txt`로 맞추거나 서비스 요구 파일을 올린다: '
                        + '; '.join(differ))


def test_개발_요구_파일은_모든_서비스_요구_파일을_읽는다():
    dev = (ROOT / 'workspace' / 'requirements-dev.txt').read_text(encoding='utf8')
    included = {(ROOT / 'workspace' / m).resolve() for m in re.findall(r'^-r\s+(\S+)', dev, re.M)}
    missing = sorted(str(r.relative_to(ROOT)) for r in REQUIREMENTS if r.resolve() not in included)
    assert not missing, f'workspace/requirements-dev.txt 가 읽지 않는 서비스 요구 파일: {missing}'
