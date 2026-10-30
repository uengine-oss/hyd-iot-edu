"""에이전트 실행의 고정 규칙(procsvc/work_rules.py) — 공통부 + 업무부. 작업 한 건의 지시(worker/prompt.py)와 겹치지 않는다."""
import re

import pytest

from procsvc import work_rules
from worker import prompt
from worker.settings import BLOCKED_SHELL_TOOLS


@pytest.mark.parametrize('key, title', [
    (None, '# ProcessGPT 업무 에이전트 작업 규칙'),
    ('', '# ProcessGPT 업무 에이전트 작업 규칙'),
    ('hyd-plant', '# HYD 설비 이상 조치 — ProcessGPT 업무 에이전트 작업 규칙'),
    (' hyd-handover ', '# HYD 교대 인수인계 — ProcessGPT 업무 에이전트 작업 규칙'),
])
def test_에이전트의_업무_규칙_칸이_고정_규칙의_업무부를_고른다(key, title):
    text = work_rules.constitution(work_rules.rules_for(key))
    assert text.splitlines()[0] == title and '## 절대 금지' in text


@pytest.mark.parametrize('key', ['hyd-unknown', 'HYD-PLANT'])
def test_모르는_업무_규칙은_다른_규칙으로_대신하지_않고_실행을_멈춘다(key):
    with pytest.raises(work_rules.UnknownWorkRules) as caught:
        work_rules.rules_for(key)
    assert 'hyd-handover' in str(caught.value) and 'hyd-plant' in str(caught.value)
    card = work_rules.rule_card(key)
    assert card['content'] is None and card['error'] == str(caught.value)


@pytest.mark.parametrize('key', [None, *sorted(work_rules.RULES)])
def test_고정_규칙은_워커가_막은_셸_실행을_안내하지_않는다(key):
    """워커는 Bash · PowerShell 을 금지 도구로 넘긴다(settings.BLOCKED_SHELL_TOOLS) — 「python <파일>로 실행」 같은 안내는 틀린 말이다."""
    text = work_rules.constitution(work_rules.rules_for(key))
    assert not re.search(r'`python |스크립트.*실행|' + '|'.join(BLOCKED_SHELL_TOOLS), text), text


@pytest.mark.parametrize('key', [None, *sorted(work_rules.RULES)])
def test_제출_형식_보류_객체_언어_규칙은_작업_지시_한_곳에만_있다(key):
    """같은 규칙이 두 곳이면 한쪽만 고쳐져 갈린다(보류 status 규칙이 실제로 갈려 있었다). 주인은 작업 지시(폼마다 다르고 이어 하기에도 붙는다)."""
    task = prompt.output_contract([{'key': 'summary', 'label': '요약'}]) + prompt.LANGUAGE_RULE
    text = work_rules.constitution(work_rules.rules_for(key))
    for marker in ('__deferred__', 'output/result.json', '## 언어', 'context/schema_prompt.md'):
        owner = task + prompt.build({'activity_name': 'x'}, {}, workdir='/w')
        assert marker in owner, f'작업 지시에 {marker} 가 없다 — 주인이 사라졌다'
        assert marker not in text, f'고정 규칙이 작업 지시의 {marker} 를 되풀이한다'


def test_포털_에이전트_화면은_워커가_넘기는_글과_같은_글을_본다():
    for key, rule in work_rules.RULES.items():
        assert work_rules.rule_card(key) == {'key': key, 'label': rule.title, 'content': work_rules.constitution(rule)}
    assert work_rules.rule_card(None) is None
