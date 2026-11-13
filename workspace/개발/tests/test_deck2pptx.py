"""덱 빌더(.claude/skills/hyd-course-deck/scripts/deck2pptx.py)의 그림 캐시와 렌더 잠금 — 실행이 달라도 같은 그림은 같은 캐시 파일,
두 렌더는 운영체제(이 PC는 Windows) 잠금으로 한 번에 하나씩.

옛 판은 캐시 이름을 파이썬 hash()(실행마다 바뀜)로 정해 캐시가 맞지 않고 끝없이 쌓였고(G4-7, 이 PC 실측 549개 · 63 MB), 잠금은 fcntl 이
없는 Windows에서 조용히 없었다(G4-8). 빌더를 하위 프로세스로 따로 띄워 본다(캐시 · 임시 폴더는 이 테스트의 임시 폴더).
"""
import os
import subprocess
import sys
from pathlib import Path

from conftest import ROOT

BUILDER = ROOT / '.claude' / 'skills' / 'hyd-course-deck' / 'scripts'
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#123456"/></svg>'


def run(tmp_path, code):
    env = dict(os.environ, DECK2PPTX_CACHE=str(tmp_path / 'cache'), TMP=str(tmp_path), TEMP=str(tmp_path), PYTHONUTF8='1')
    return subprocess.run([sys.executable, '-c', f'import sys; sys.path.insert(0, {str(BUILDER)!r}); import deck2pptx as d\n{code}'],
                          capture_output=True, text=True, encoding='utf-8', env=env, timeout=120)


def cache_file(tmp_path, scale):
    out = run(tmp_path, f'print(d.svg_to_png({SVG!r}.encode(), {scale}, "t"))')
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_같은_그림과_배율은_실행이_달라도_같은_캐시_파일이다(tmp_path):
    first, second = cache_file(tmp_path, 2), cache_file(tmp_path, 2)
    assert first == second and Path(first).is_file() and len(list((tmp_path / 'cache').iterdir())) == 1


def test_배율이_다르면_다른_캐시_파일이다(tmp_path):
    assert cache_file(tmp_path, 2) != cache_file(tmp_path, 3)


def test_두_렌더는_한_번에_하나씩_돈다(tmp_path):
    """첫 렌더는 테스트가 놓으라고 할 때까지 잠금을 쥔다. 둘째가 「잡으려 함」을 알린 뒤에 놓게 하고, 둘째가 잡은 시각이 놓은 시각 뒤인지 본다."""
    env = dict(os.environ, TMP=str(tmp_path), TEMP=str(tmp_path), PYTHONUTF8='1')
    head = f'import sys, time; sys.path.insert(0, {str(BUILDER)!r}); import deck2pptx as d\n'
    holder = head + 'with d._render_lock():\n    print("held", flush=True)\n    sys.stdin.readline()\n    print(time.time(), flush=True)'
    waiter = head + 'try:\n    with d._render_lock(wait_s=0):\n        print("got")\nexcept d.DeckError as e:\n    print("blocked", e)'
    first = subprocess.Popen([sys.executable, '-c', holder], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    assert first.stdout.readline().strip() == 'held'
    while_held = subprocess.run([sys.executable, '-c', waiter], capture_output=True, text=True, env=env, timeout=60).stdout
    first.stdin.write('놓기\n'); first.stdin.flush()
    first.stdout.readline(); first.wait(timeout=30)
    after = subprocess.run([sys.executable, '-c', waiter], capture_output=True, text=True, env=env, timeout=60).stdout
    assert while_held.startswith('blocked') and '20분' in while_held and after.strip() == 'got'
