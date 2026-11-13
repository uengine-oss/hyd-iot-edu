"""제공 정의 파일(it/process/definitions/*.json) — 같은 판본 번호의 원문은 바꾸지 않는다(P1-18).

process 는 켜질 때 이 파일들을 불변 판본으로 등록한다. 이미 그 판본이 들어 있는 학생 PC 에서 같은 번호로 원문만 바뀌면 등록이 거절되어
process 가 뜨지 않는다(git pull 뒤 계속 다시 켜짐). 그래서 지금 원문은 그 판본 번호가 처음 커밋된 원문과 같아야 한다 — 고쳤으면 판본을 올린다.
"""
import json
import subprocess

import pytest

from conftest import DEFINITIONS, ROOT


def _git(*args):
    out = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True)
    return out.stdout.decode('utf8')


def _history(path):
    """(커밋, 그 커밋에서의 파일 경로) — 오래된 것부터, 이름이 바뀐 것도 따라간다."""
    rel = path.relative_to(ROOT).as_posix()
    lines = [l for l in _git('log', '--follow', '--name-only', '--format=%H', '--', rel).splitlines() if l.strip()]
    pairs, commit = [], None
    for line in lines:
        if len(line) == 40 and all(c in '0123456789abcdef' for c in line):
            commit = line
        else:
            pairs.append((commit, line))
    return list(reversed(pairs))


def _committed(commit, rel):
    try:
        return json.loads(_git('show', f'{commit}:{rel}'))
    except (subprocess.CalledProcessError, ValueError):
        return None


FILES = sorted(p for p in DEFINITIONS.glob('*.json') if 'version' in json.loads(p.read_text(encoding='utf8')))


def test_판본을_가진_제공_정의_파일이_있다():
    assert {json.loads(p.read_text(encoding='utf8'))['processDefinitionId'] for p in FILES} >= {
        'anomaly_response', 'alert_triage', 'ask_agent', 'shift_handover'}


def _changed_in_place(path, now):
    """now(원문)가 그 판본 번호가 처음 커밋된 원문과 다르면 까닭 한 줄, 같거나 아직 커밋된 적 없는 새 판본이면 None."""
    first = next((raw for commit, rel in _history(path) if (raw := _committed(commit, rel))
                  and raw.get('processDefinitionId') == now['processDefinitionId'] and raw.get('version') == now['version']), None)
    if first is None or first == now:
        return None
    return (f"{path.name}: 판본 {now['version']} 의 원문이 처음 커밋된 원문과 다르다 — 원문을 고쳤으면 판본 번호를 올린다 "
            '(같은 번호의 다른 원문은 이미 그 판본이 있는 학생 PC 에서 process 등록을 막는다)')


@pytest.mark.parametrize('path', FILES, ids=lambda p: p.name)
def test_정의_원문은_그_판본_번호가_처음_커밋된_원문과_같다(path):
    assert _changed_in_place(path, json.loads(path.read_text(encoding='utf8'))) is None


def test_같은_판본_번호로_설명만_고친_원문은_잡히고_판본을_올리면_통과한다():
    """검사가 실제로 잡는지(헌법: 일부러 깨뜨려 본다) — 이력에 있는 판본의 원문에서 설명 한 줄만 바꾼다."""
    path = DEFINITIONS / 'alert_triage_v1.json'
    commit, rel = next((c, r) for c, r in _history(path) if _committed(c, r))
    first = _committed(commit, rel)
    edited = dict(first, description=first['description'] + ' (고침)')
    assert '판본 번호를 올린다' in _changed_in_place(path, edited)
    assert _changed_in_place(path, dict(edited, version=first['version'] + '.9')) is None
