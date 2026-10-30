"""서비스 이미지(각 Dockerfile) — 이미지에 넣는 폴더만으로 그 서비스의 진입 모듈이 가져와지는가, 이미지 판(Python 3.12) 문법인가.

지운 모듈을 다른 서비스가 아직 가져오면 스택이 켜지지 않는다(2026-10-30 실측: agent 서비스의 LLM 도우미 모듈을 지운 뒤 dmn-mcp 가 ImportError 로
「unhealthy」, 시작.bat 4단계에서 멈춤). Dockerfile 의 COPY 줄대로 /srv 같은 폴더를 만들고 CMD 의 모듈을 실제로 가져온다.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILES = sorted(p for p in ROOT.glob('**/Dockerfile') if 'workspace' not in p.parts and '작업' not in p.parts)
IMAGE_PYTHON = (3, 12)                     # 모든 서비스 Dockerfile 의 FROM python:3.12-slim
# 가져올 때 읽는 값(compose 가 넘기는 것과 같은 이름) — 값 자체는 이 테스트에서 쓰이지 않는다
ENV = {'PROCESS_CALLER_TOKEN': 'test-caller', 'AI_MODE': 'replay', 'PYTHONUTF8': '1', 'TIME_SCALE': '20',
       'CMD_FINGERPRINT_KEY': 'test-fingerprint'}


def image_layout(dockerfile):
    """COPY <저장소 경로> /srv/<이름> 줄 → [(원본, /srv 아래 이름)], CMD 의 모듈 이름."""
    text = dockerfile.read_text(encoding='utf8')
    copies = [(ROOT / src, dst[len('/srv/'):]) for src, dst in re.findall(r'^COPY\s+(\S+)\s+(/srv/\S+)\s*$', text, re.M)
              if not dst.endswith('requirements.txt')]
    cmd = re.search(r'^CMD\s+\[(.+)\]\s*$', text, re.M).group(1)
    words = [w.strip().strip('"') for w in cmd.split(',')]
    module = words[words.index('-m') + 1] if '-m' in words else words[1].split(':')[0]
    return copies, module


def build_srv(dockerfile, into):
    copies, module = image_layout(dockerfile)
    for src, name in copies:
        assert src.exists(), f'{dockerfile.relative_to(ROOT)}: COPY 원본 {src.relative_to(ROOT)} 이 없다'
        target = into / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy2(src, target)
    return module


@pytest.mark.parametrize('dockerfile', DOCKERFILES, ids=[str(p.parent.relative_to(ROOT)) for p in DOCKERFILES])
def test_이미지에_넣는_폴더만으로_진입_모듈이_가져와진다(dockerfile, tmp_path):
    module = build_srv(dockerfile, tmp_path)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHONPATH', 'HYD_'))} | ENV
    key = tmp_path / 'runtime.key'
    key.write_text('k' * 48, encoding='utf8')
    env['HYD_WORKER_RUNTIME_KEY_FILE'] = str(key)
    env['PROCESS_STATE_PATH'] = str(tmp_path / 'state' / 'process.sqlite3')
    run = subprocess.run([sys.executable, '-I', '-c', f'import sys; sys.path.insert(0, "."); import {module}'],
                         cwd=tmp_path, env=env, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=180)
    tail = '\n'.join((run.stderr or '').strip().splitlines()[-4:])
    assert run.returncode == 0, f'{dockerfile.relative_to(ROOT)}: `import {module}` 실패\n{tail}'


@pytest.mark.parametrize('dockerfile', DOCKERFILES, ids=[str(p.parent.relative_to(ROOT)) for p in DOCKERFILES])
def test_이미지에_넣는_파이썬_파일은_이미지_판_문법이다(dockerfile):
    copies, _ = image_layout(dockerfile)
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
