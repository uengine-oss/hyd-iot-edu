"""인용 위치 찾기(procsvc/manual_locate.py) — 에이전트가 적은 인용 글을 원문에서 한 곳으로 정한다(정확 → 글자 · 숫자만 → 낱말 사이 끼어듦).
여러 곳에 맞으면 짐작하지 않고 더 긴 인용을 요구한다. 원문은 실제 제공 문서(HM-8)와 짧은 표본 글이다."""

import pytest

from conftest import SAMPLES

from procsvc import manual_locate
from procsvc.manual_locate import Ambiguous, locate

HM8 = {1: (SAMPLES / 'HM-8_cooler-fan-manual.md').read_text(encoding='utf-8')}
PAGES = {1: '1. 팬을 멈춘다.\n2. 벨트 장력을 잰다.\n', 2: '1. 팬을 멈춘다.\n3. 다시 켠다.\n'}


@pytest.mark.parametrize('anchor, want', [
    ({'page': 1, 'quote': '2. 벨트 장력을 잰다.'}, (1, 'exact')),                             # 정확히 한 곳
    ({'page': 1, 'quote': '2.벨트   장력을 잰다'}, (1, 'normalized')),                       # 띄어쓰기 · 마침표 차이
    ({'quote': '3. 다시 켠다.'}, (2, 'exact')),                                             # 쪽을 안 적으면 모든 쪽에서
    ({'page': 2, 'quote': '1. 팬을 멈춘다.'}, (2, 'exact')),                                 # 쪽을 적으면 그 쪽에서만
])
def test_인용_글은_원문의_한_곳으로_정해지고_원문_글자로_돌려준다(anchor, want):
    got = locate(PAGES, anchor)
    page, how = want
    assert got['page'] == page and got.get('located', 'exact') == how
    assert PAGES[page][got['start']:got['end']] == got['quote']


def test_적어_보낸_좌표가_맞으면_그대로_쓴다():
    text = PAGES[1]
    start = text.index('2.')
    anchor = {'page': 1, 'start': start, 'end': start + 4, 'quote': text[start:start + 4]}
    assert locate(PAGES, anchor) == {'page': 1, 'start': start, 'end': start + 4, 'quote': text[start:start + 4]}


def test_여러_곳에_맞는_짧은_인용은_정하지_않고_더_긴_인용을_요구한다():
    with pytest.raises(Ambiguous, match='2곳'):
        locate(PAGES, {'quote': '1. 팬을 멈춘다.'})


def test_여러_곳에_맞아도_그_절차_블록_안의_한_곳이면_그것으로_정한다():
    second = len(PAGES[1])                     # 2쪽 전체를 블록으로
    got = locate(PAGES, {'quote': '1. 팬을 멈춘다.'}, within=((2, 0), (2, len(PAGES[2]))))
    assert (got['page'], got['start']) == (2, 0) and second > 0


@pytest.mark.parametrize('anchor, says', [
    ({'quote': ''}, 'quote'),
    ({'quote': '   '}, 'quote'),
    ({'page': 9, 'quote': '팬'}, '페이지'),
    ({'page': '1', 'quote': '팬'}, '페이지'),
    ({'quote': '원문에 없는 문장입니다'}, '찾지 못했습니다'),
])
def test_찾을_수_없는_인용은_까닭과_함께_거절한다(anchor, says):
    with pytest.raises(ValueError, match=says):
        locate(PAGES, anchor)


def test_실제_제공_문서에서_절차_제목_줄을_찾는다():
    title = next(line for line in HM8[1].splitlines() if line.startswith('### SOP-COOL-11'))
    got = locate(HM8, {'page': 1, 'quote': title})
    assert HM8[1][got['start']:got['end']] == title


def test_낱말_사이에_다른_글이_끼어도_낱말이_차례로_있으면_찾는다():
    pages = {1: '팬 벨트의 장력이 (규정값 10 mm) 기준보다 크면 교체한다.'}
    got = locate(pages, {'quote': '팬 벨트의 장력이 기준보다 크면 교체한다'})
    assert got['located'] == 'loose' and got['quote'].startswith('팬 벨트의') and manual_locate.WORD_GAP > 0
