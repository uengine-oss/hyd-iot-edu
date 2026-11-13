"""긴 문서 나누기 · 합치기(procsvc/manual_segments.py) — 큰 문서는 제목 경계로 구간을 나눠 구간마다 추출하고, 결과를 한 문서 제안으로 합친다.
구간은 빈 줄 → 줄바꿈 → 문장 끝에서 자르고(P2-22), 합칠 때 구간 밖 인용 · 겹친 절 · 잘린 절차 · 다른 구간을 가리키는 규칙을 정해진 규칙으로 다룬다."""
import pytest

from procsvc import manual_segments as ms


def doc(*texts):
    return {'source_id': 'src-1', 'pages': [{'page': i + 1, 'text': t} for i, t in enumerate(texts)]}


def cuts(source, size):
    return [(r['page'], r['start'], r['end']) for s in ms.segments(source, size) for r in ms.ranges_of(s)]


def test_한_번에_들어가는_문서는_나누지_않는다():
    assert ms.segments(doc('가' * ms.MIN_SEGMENT_CHARS), ms.MIN_SEGMENT_CHARS) == []


def test_구간_크기가_너무_작으면_거절한다():
    with pytest.raises(ValueError, match='too small'):
        ms.segments(doc('가' * 10), ms.MIN_SEGMENT_CHARS - 1)


@pytest.mark.parametrize('text, ends_with', [
    ('문단입니다\n\n' * 900, '\n\n'),            # 빈 줄이 있으면 마지막 빈 줄 뒤
    ('줄입니다\n' * 1500, '\n'),                 # 빈 줄이 없으면 마지막 줄바꿈 뒤
    ('문장입니다. ' * 900, '. '),                # 줄바꿈도 없으면 마지막 문장 끝 뒤
], ids=['빈 줄', '줄바꿈', '문장 끝'])
def test_큰_블록은_줄이나_문장_한가운데서_자르지_않는다(text, ends_with):
    """P2-22: 빈 줄이 없으면 정확히 한도 글자에서 잘라 한 줄 · 한 문장이 두 구간으로 갈렸다."""
    first = cuts(doc(text), 4000)[0]
    assert text[:first[2]].endswith(ends_with)


def test_줄_문장_끝이_없는_한_덩어리_글만_한도에서_자른다():
    assert cuts(doc('a' * 9000), 4000) == [(1, 0, 4000), (1, 4000, 8000), (1, 8000, 9000)]


def test_자를_자리는_빈_줄_줄바꿈_문장_끝_순서로_고른다():
    text = '앞 문장. 뒤 문장\n다음 줄\n\n새 문단'
    assert ms.cut_point(text, 0, len(text)) == text.index('\n\n') + 2
    assert ms.cut_point(text, 0, text.index('\n\n')) == text.index('\n') + 1
    assert ms.cut_point(text, 0, text.index('\n')) == text.index('. ') + 2


def test_제목_경계는_구간을_나누는_자리가_되고_쪽을_넘지_않는다():
    page1 = '# 1장\n' + '가' * 2500 + '\n# 2장\n' + '나' * 2500
    got = ms.segments(doc(page1, '다' * 100), 3000)
    assert [s['index'] for s in got] == list(range(1, len(got) + 1)) and all(s['total'] == len(got) for s in got)
    starts = {r['start'] for s in got for r in ms.ranges_of(s) if r['page'] == 1}
    assert page1.index('# 2장') in starts


def anchor(page, start, end):
    return {'source_id': 'src-1', 'page': page, 'start': start, 'end': end, 'quote': 'x'}


def part(seg_index, total, ranges, **prop):
    return ({'index': seg_index, 'total': total, 'ranges': ranges}, {'sections': [], 'procedures': [], 'page_reviews': [], 'warnings': [], **prop})


def test_구간_밖을_인용한_제안은_합치지_않고_거절한다():
    seg = part(1, 1, [{'page': 1, 'start': 0, 'end': 10}], sections=[{'ref': 'A-1', 'anchor': anchor(1, 20, 30)}])
    with pytest.raises(ValueError, match='담당 구간 밖'):
        ms.merge(doc('가' * 40), [seg])


def test_두_구간이_같은_절을_내면_첫_제안을_두고_경고한다():
    a = part(1, 2, [{'page': 1, 'start': 0, 'end': 10}], sections=[{'ref': 'A-1', 'title': '첫', 'anchor': anchor(1, 0, 5)}])
    b = part(2, 2, [{'page': 1, 'start': 10, 'end': 20}], sections=[{'ref': 'A-1', 'title': '둘', 'anchor': anchor(1, 12, 15)}])
    merged = ms.merge(doc('가' * 20), [b, a])
    assert [s['title'] for s in merged['sections']] == ['첫'] and any('A-1' in w for w in merged['warnings'])


def steps(*orders, page=1, at=0):
    return [{'order': o, 'text': f'단계 {o}', 'anchor': anchor(page, at + i, at + i + 1)} for i, o in enumerate(orders)]


@pytest.mark.parametrize('later_orders, joined', [((3, 4), True), ((1, 2), False), ((4, 5), False)],
                         ids=['번호가 이어짐 — 이어 붙임', '번호가 다시 1부터 — 겹침 경고', '번호가 건너뜀 — 겹침 경고'])
def test_구간_경계에서_잘린_절차는_번호가_바로_이어질_때만_이어_붙인다(later_orders, joined):
    a = part(1, 2, [{'page': 1, 'start': 0, 'end': 10}], procedures=[{'id': 'SOP-A-1', 'anchor': anchor(1, 0, 1), 'steps': steps(1, 2, at=1)}])
    b = part(2, 2, [{'page': 1, 'start': 10, 'end': 20}], procedures=[{'id': 'SOP-A-1', 'anchor': anchor(1, 10, 11), 'steps': steps(*later_orders, at=11)}])
    merged = ms.merge(doc('가' * 20), [a, b])
    orders = [st['order'] for st in merged['procedures'][0]['steps']]
    assert orders == ([1, 2, *later_orders] if joined else [1, 2])
    assert any(('이어붙임' if joined else '첫 제안을 유지') in w for w in merged['warnings'])


def test_어느_구간에서도_추출되지_않은_SOP를_가리키는_규칙은_빼고_경고한다():
    rules = [{'id': 'rule:only-missing', 'effect': 'SELECT', 'outputs': ['SOP-NONE-1'], 'anchor': anchor(1, 0, 1)},
             {'id': 'rule:partly', 'effect': 'WARN', 'applies_to': ['SOP-A-1', 'SOP-NONE-1'], 'anchor': anchor(1, 1, 2)}]
    a = part(1, 1, [{'page': 1, 'start': 0, 'end': 20}], procedures=[{'id': 'SOP-A-1', 'anchor': anchor(1, 2, 3), 'steps': steps(1, at=3)}],
             knowledge={'rules': rules})
    merged = ms.merge(doc('가' * 20), [a])
    assert [(r['id'], r.get('applies_to')) for r in merged['knowledge']['rules']] == [('rule:partly', ['SOP-A-1'])]
    assert sum('SOP-NONE-1' in w for w in merged['warnings']) == 2


def test_인용은_자기_구간_안에_있어야_한다():
    seg = {'ranges': [{'page': 1, 'start': 10, 'end': 20}]}
    assert ms.within(anchor(1, 10, 20), seg) and not ms.within(anchor(1, 9, 12), seg) and not ms.within(anchor(2, 10, 12), seg)
