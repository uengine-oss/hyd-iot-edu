"""AI 실행 화면 기록(worker/events.py) — 에이전트가 연 스킬 파일을 이번 실행에 준 스킬과 견주고, 키 없는 PC의 재생이면 녹화한 실행의 것으로 적는가.

입력은 저장소의 실제 교대 녹화본(보완 1 초안)이 낸 도구 시작 기록이다 — 그 실행은 스킬 `my-shift-handover-review`의 SKILL.md를 연다.
"""
import gzip
import json
from pathlib import Path

import pytest
from cliagents import ExecEvent, ExecEventKind

from worker.events import SkillReads

REPLAY = Path(__file__).resolve().parents[3] / 'it' / 'agent-worker' / 'replay'
RECORDED_SKILL = 'my-shift-handover-review'


def recorded_tool_starts(slot):
    for path in REPLAY.glob('*.json.gz'):
        doc = json.loads(gzip.decompress(path.read_bytes()))
        if doc['slot'] == slot:
            return [ExecEvent(**{**e, 'kind': ExecEventKind(e['kind'])}) for run in doc['runs'] for e in run['events'] if e['kind'] == 'tool_start']
    raise AssertionError(f'저장소에 {slot} 녹화가 없다')


def skill(name):
    return {'name': name, 'sha256': 'a' * 64, 'version': 3, 'source': 'tenant', 'title': '교대 인수인계 대조'}


def reads(provided, **kw):
    sr = SkillReads(provided, **kw)
    return [u.data for ev in recorded_tool_starts('handover/draft-2') for u in sr.on_tool_start(ev)]


@pytest.mark.parametrize('provided, recorded, expect', [
    ([skill(RECORDED_SKILL)], False, dict(known=True, version=3, title='교대 인수인계 대조')),     # 이번 실행에 준 스킬을 엶
    ([skill('my-handover')], False, dict(known=False)),                                         # 준 적 없는 스킬을 엶 — 경고 자리
    ([skill('my-handover')], True, dict(known=None, recorded=True)),                            # 재생: 학생이 이름을 달리 지은 스킬
    ([], True, dict(known=None, recorded=True)),                                                # 재생: 학생 에이전트에 스킬이 없음
])
def test_스킬_파일_읽기는_이번_실행에_준_스킬과_견주고_재생이면_녹화한_실행의_것으로_적는다(provided, recorded, expect):
    [read] = reads(provided, recorded=recorded)
    assert read['skill'] == RECORDED_SKILL and read['file'] == 'SKILL.md'
    assert {k: read.get(k) for k in expect} == expect
    assert read['content'].startswith('강사가 저장한 답의 실행이 ') == recorded
