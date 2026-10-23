"""A117 (r14 B2, memento document_locate): the agent quotes, the server finds the place."""
import pytest

from procsvc import manual_locate as L

PAGES = {1: '1. 안전\n작업 전 전원을 차단한다.\n2. 점검\n벨트 장력을 확인한다. 벨트 장력을 확인한다.\n',
         2: '3. 교체\n작업 전 전원을 차단한다.\n오일 교환 주기: 2,000 h · 필터 교환 주기: 1,000 h.\n'}


def test_offsets_are_not_required_when_the_quote_is_unique_on_the_page():
    got = L.locate(PAGES, {'page': 2, 'quote': '오일 교환 주기: 2,000 h'})
    assert got == {'page': 2, 'start': PAGES[2].index('오일'), 'end': PAGES[2].index('오일') + len('오일 교환 주기: 2,000 h'),
                   'quote': '오일 교환 주기: 2,000 h', 'located': 'exact'}


def test_correct_offsets_from_the_agent_are_kept_as_given():
    s = PAGES[1].index('작업 전')
    got = L.locate(PAGES, {'page': 1, 'start': s, 'end': s + 13, 'quote': PAGES[1][s:s + 13]})
    assert got == {'page': 1, 'start': s, 'end': s + 13, 'quote': PAGES[1][s:s + 13]}


def test_wrong_offsets_with_a_right_quote_are_corrected_instead_of_rejected():
    got = L.locate(PAGES, {'page': 2, 'start': 0, 'end': 5, 'quote': '필터 교환 주기: 1,000 h.'})
    assert (got['start'], got['end']) == (PAGES[2].index('필터'), PAGES[2].index('필터') + len('필터 교환 주기: 1,000 h.'))


def test_whitespace_and_punctuation_differences_resolve_to_the_sources_own_text():
    got = L.locate(PAGES, {'page': 2, 'quote': '오일  교환주기 : 2000h - 필터 교환 주기 1,000 h.'})
    assert got['located'] == 'normalized' and got['quote'] == '오일 교환 주기: 2,000 h · 필터 교환 주기: 1,000 h.'
    assert PAGES[2][got['start']:got['end']] == got['quote']


def test_short_gaps_between_words_are_allowed_as_a_last_resort():
    got = L.locate(PAGES, {'page': 2, 'quote': '오일 교환 필터 교환 1,000'})
    assert got['located'] == 'loose' and got['quote'].startswith('오일 교환 주기') and got['quote'].endswith('1,000')


def test_a_quote_found_in_several_places_is_not_guessed():
    with pytest.raises(L.Ambiguous, match='2곳'):
        L.locate(PAGES, {'page': 1, 'quote': '벨트 장력을 확인한다.'})
    with pytest.raises(L.Ambiguous, match='2곳'):
        L.locate(PAGES, {'quote': '작업 전 전원을 차단한다.'})                        # no page: both pages have it


def test_offsets_pick_one_of_several_places_when_they_are_right():
    second = PAGES[1].rindex('벨트 장력을 확인한다.')
    got = L.locate(PAGES, {'page': 1, 'start': second, 'end': second + 11, 'quote': '벨트 장력을 확인한다.'})
    assert got['start'] == second


def test_a_quote_the_source_does_not_contain_is_still_refused():
    with pytest.raises(ValueError, match='찾지 못했습니다'):
        L.locate(PAGES, {'page': 1, 'quote': '허구의 문장입니다 여기 없음'})
    with pytest.raises(ValueError, match='페이지가 올바르지'):
        L.locate(PAGES, {'page': 9, 'quote': '1. 안전'})
    with pytest.raises(ValueError, match='quote'):
        L.locate(PAGES, {'page': 1, 'quote': ' '})


def test_page_may_be_omitted_when_the_quote_is_unique_in_the_document():
    assert L.locate(PAGES, {'quote': '3. 교체'})['page'] == 2


def test_the_block_a_quote_belongs_to_picks_one_of_several_places():
    # 2026-10-23 리허설: 세 절차에 같은 단계 문장이 있어 추출이 세 번 다 거부됐다 — 단계는 자기 절차 블록 안의 것이다
    text = '### SOP-A\n1. 모드를 확인한다.\n2. 팬을 올린다.\n### SOP-B\n1. 모드를 확인한다.\n2. 부하를 내린다.\n'
    b = text.index('### SOP-B')
    got = L.locate({1: text}, {'page': 1, 'quote': '1. 모드를 확인한다.'}, within=(1, b, len(text)))
    assert got['start'] == text.index('1. 모드', b)
    with pytest.raises(L.Ambiguous, match='2곳'):        # 블록이 둘 다 품으면 여전히 정하지 않는다
        L.locate({1: text}, {'page': 1, 'quote': '1. 모드를 확인한다.'}, within=(1, 0, len(text)))
    with pytest.raises(L.Ambiguous, match='2곳'):        # 블록 밖(다른 쪽)이면 여전히 정하지 않는다
        L.locate({1: text}, {'page': 1, 'quote': '1. 모드를 확인한다.'}, within=(2, 0, 10))
