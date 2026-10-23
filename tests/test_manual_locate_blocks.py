"""I1 · I2 (2026-10-23 검수): 절차 블록 안 찾기가 쪽을 넘고(PDF에서 절차 제목이 쪽 끝, 단계가 다음 쪽), 블록 밖의 유일한
정확 일치보다 같은 글자의 블록 안 위치를 먼저 본다(PDF 줄바꿈으로 그 절차 쪽 문장만 두 줄로 나뉜 경우)."""
import copy

import pytest
from procsvc import manual_extraction as extraction
from procsvc import manual_locate as L

SID = 'manual:00000000-0000-0000-0000-000000000001:abc'
STEP = '1. 모드가 자동인지 확인한다.'


def src(*pages):
    return dict(source_id=SID, status='READY', pages=[dict(page=i, text=t) for i, t in enumerate(pages, 1)])


def q(quote, page=None):
    a = dict(source_id=SID, quote=quote)
    if page is not None:
        a['page'] = page
    return a


def proposal(source, procs):
    return dict(source_id=SID, sections=[dict(ref='8.5', title='즉시 완화', anchor=q('## 8.5 즉시 완화'))],
                procedures=procs, page_reviews=[dict(page=p['page'], note='검토') for p in source['pages']], warnings=[])


def proc(sid, head, steps, pages=None):
    return dict(id=sid, name=head, section='8.5', anchor=q('### ' + sid + ' ' + head),
                steps=[dict(order=i, text=t, manual='8.5', anchor=q(t, (pages or {}).get(i))) for i, t in enumerate(steps, 1)])


def test_a_procedure_whose_steps_start_on_the_next_page_finds_its_own_repeated_step():
    p1 = '## 8.5 즉시 완화\n### SOP-A 팬 최대\n'
    p2 = STEP + '\n2. 팬을 100 %로 올린다.\n### SOP-B 부하 저감\n' + STEP + '\n2. 부하를 80 %로 내린다.\n'
    source = src(p1, p2)
    prop = proposal(source, [proc('SOP-A', '팬 최대', [STEP, '2. 팬을 100 %로 올린다.']),
                             proc('SOP-B', '부하 저감', [STEP, '2. 부하를 80 %로 내린다.'])])
    checked = extraction.validate_proposal(source, copy.deepcopy(prop))
    a1, b1 = (checked['procedures'][i]['steps'][0]['anchor'] for i in (0, 1))
    b_head = p2.index('### SOP-B')
    assert (a1['page'], a1['start']) == (2, 0)                          # SOP-A's step 1 is the one before SOP-B's title
    assert b1['page'] == 2 and b1['start'] == p2.index(STEP, b_head)     # SOP-B's is its own


def test_a_procedure_over_three_pages_and_the_page_given_by_the_agent():
    p1 = '## 8.5 즉시 완화\n### SOP-A 팬 최대\n'
    p2 = '2. 팬을 100 %로 올린다.\n'
    p3 = STEP + '\n### SOP-B 부하 저감\n' + STEP + '\n'
    source = src(p1, p2, p3)
    prop = proposal(source, [proc('SOP-A', '팬 최대', ['2. 팬을 100 %로 올린다.', STEP], pages={2: 3}),
                             proc('SOP-B', '부하 저감', [STEP], pages={1: 3})])
    checked = extraction.validate_proposal(source, copy.deepcopy(prop))
    assert checked['procedures'][0]['steps'][1]['anchor']['start'] == 0
    assert checked['procedures'][1]['steps'][0]['anchor']['start'] == p3.index(STEP, p3.index('### SOP-B'))


def test_the_last_procedure_block_runs_to_the_end_of_the_document():
    p1 = '## 8.5 즉시 완화\n### SOP-A 팬 최대\n' + STEP + '\n### SOP-B 부하 저감\n'
    p2 = STEP + '\n'
    source = src(p1, p2)
    prop = proposal(source, [proc('SOP-A', '팬 최대', [STEP]), proc('SOP-B', '부하 저감', [STEP])])
    checked = extraction.validate_proposal(source, copy.deepcopy(prop))
    assert checked['procedures'][0]['steps'][0]['anchor']['page'] == 1
    assert (checked['procedures'][1]['steps'][0]['anchor']['page'], checked['procedures'][1]['steps'][0]['anchor']['start']) == (2, 0)


def test_a_line_broken_copy_inside_the_own_block_wins_over_a_unique_exact_hit_in_another_procedure():
    text = ('## 8.5 즉시 완화\n### SOP-A 팬 최대\n' + STEP + '\n2. 팬을 100 %로 올린다.\n'
            '### SOP-B 부하 저감\n1. 모드가 자동인지\n확인한다.\n2. 부하를 80 %로 내린다.\n')
    source = src(text)
    prop = proposal(source, [proc('SOP-A', '팬 최대', [STEP, '2. 팬을 100 %로 올린다.']),
                             proc('SOP-B', '부하 저감', [STEP, '2. 부하를 80 %로 내린다.'])])
    checked = extraction.validate_proposal(source, copy.deepcopy(prop))
    a1 = checked['procedures'][0]['steps'][0]['anchor']
    b1 = checked['procedures'][1]['steps'][0]['anchor']
    b_head = text.index('### SOP-B')
    assert a1['start'] < b_head < b1['start']
    assert b1['quote'] == '1. 모드가 자동인지\n확인한다.'                 # the source's own characters at SOP-B


def test_a_loose_match_inside_the_block_does_not_override_an_exact_hit_outside():
    text = '### SOP-A\n' + STEP + '\n### SOP-B\n1. 모드가 반드시 자동인지 다시 확인한다.\n'
    b = text.index('### SOP-B')
    got = L.locate({1: text}, {'page': 1, 'quote': STEP}, within=((1, b), (1, len(text))))
    assert got['start'] == text.index(STEP) and got['located'] == 'exact'     # another sentence is not guessed


def test_two_hits_inside_the_block_are_still_ambiguous_across_pages():
    pages = {1: '### SOP-A\n' + STEP + '\n', 2: STEP + '\n'}
    with pytest.raises(L.Ambiguous, match='2곳'):
        L.locate(pages, {'quote': STEP}, within=((1, 0), (2, len(pages[2]))))
