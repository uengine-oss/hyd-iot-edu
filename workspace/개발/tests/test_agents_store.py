"""에이전트 설정 · 스킬 읽기(procsvc/agents_store.py) — 워커가 실행마다 읽는 한 곳. 스킬 자리는 워커 CLI(Claude Code)의 자리 하나."""
from procsvc import agents_store
from worker.settings import PROVIDER


def _settings(profile=None, **fields):
    return agents_store.AgentSettings(agent_id='agent:cooling', profile=profile, **fields)


def test_스킬_자리는_워커가_실행하는_CLI_하나의_자리다():
    assert set(agents_store.SKILL_ROOTS) == {PROVIDER}


def test_배정된_스킬은_작업_폴더의_SKILL_파일_자리와_함께_지시에_실린다():
    skills = [{'skill_name': 'fan-max', 'description': '팬 최대', 'content': '# 팬'}, {'skill_name': 'load-cut', 'content': '# 부하'}]
    text = _settings(profile={'username': '냉각 담당', 'role': 'agent', 'goal': '원인 정리'}, skills=skills).instructions()
    root = agents_store.SKILL_ROOTS[PROVIDER]
    assert '- 역할: AI 에이전트' in text and '- 목표: 원인 정리' in text
    assert f'- `fan-max`: 팬 최대 — `{root}/fan-max/SKILL.md`' in text and f'`{root}/load-cut/SKILL.md`' in text
    assert f'작업 디렉터리의 `{root}/<이름>/SKILL.md`' in text


def test_프로필도_스킬도_없는_작업은_지시를_더하지_않는다():
    assert _settings().instructions() == ''
