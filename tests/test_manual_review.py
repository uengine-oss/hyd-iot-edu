import copy

import pytest

from procsvc.manual_sources import ManualSources
from procsvc import manual_review, manual_graph


TEXT = '# 정비\nHM-8.1 팬 벨트\n긴 원문 설명\nSOP-REF-91 벨트 점검\n1. 정지한다.\n2. 벨트를 확인한다.\n'


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite')


def reviewed(archive, text=TEXT, **kwargs):
    source = archive.save('hyd', 'manual.md', text.encode(), **kwargs)
    body = manual_review.proposal(source)
    body.update(by='검토자', reviewed=True,
                links={p['id']: {'failureMode': 'fm:bearing-degradation'} for p in body['procedures']})
    return source, body


def test_all_lines_have_exact_source_coordinates_and_graph_keeps_full_text(archive):
    source, body = reviewed(archive, TEXT.replace('긴 원문 설명', '원문 ' * 300))
    plan = manual_review.validate(archive, 'hyd', body)
    assert len(plan['sections'][0]['excerpt']) > 200
    for item in plan['sections'] + plan['procedures'] + plan['procedures'][0]['steps']:
        archive.validate_anchor('hyd', item['anchor'])
    graph = manual_graph.desired(plan)
    assert len([n for n in graph['nodes'] if n['labels'] == ['Step']]) == 2
    assert all(n['props']['source_id'] == source['source_id'] for n in graph['nodes'])
    assert not any(e['type'] == 'OUTPUTS' for e in graph['edges'])


def test_same_ref_in_two_documents_has_distinct_graph_identity(archive):
    _, a = reviewed(archive)
    _, b = reviewed(archive)
    graphs = [manual_graph.desired(manual_review.validate(archive, 'hyd', p)) for p in (a, b)]
    sections = [{n['props']['id'] for n in g['nodes'] if n['labels'] == ['ManualSection']} for g in graphs]
    assert sections[0].isdisjoint(sections[1])


@pytest.mark.parametrize('change', [
    lambda p: p.update(reviewed=False),
    lambda p: p.update(by=' '),
    lambda p: p['sections'][0]['anchor'].update(quote='위조'),
    lambda p: p['procedures'][0]['steps'][0]['anchor'].update(end=99999),
    lambda p: p['procedures'].append(copy.deepcopy(p['procedures'][0])),
    lambda p: p['sections'].append(copy.deepcopy(p['sections'][0])),
    lambda p: p['procedures'][0]['steps'][0].update(order=2),
    lambda p: p['procedures'][0]['steps'][0].update(manual='missing'),
    lambda p: p['procedures'][0].update(name=''),
    lambda p: p.update(links={}),
    lambda p: p['sections'].append(None),
    lambda p: p['procedures'].append('not-an-object'),
    lambda p: p['procedures'][0]['steps'].append('not-a-step'),
    lambda p: p.update(links=['not-a-mapping']),
])
def test_invalid_review_is_rejected_before_graph_io(archive, change):
    _, body = reviewed(archive)
    change(body)
    with pytest.raises(ValueError):
        manual_review.validate(archive, 'hyd', body)


def test_different_valid_source_anchor_cannot_be_smuggled_in(archive):
    _, a = reviewed(archive)
    _, b = reviewed(archive)
    a['procedures'][0]['steps'][0]['anchor'] = b['procedures'][0]['steps'][0]['anchor']
    with pytest.raises(ValueError, match='다른 문서'):
        manual_review.validate(archive, 'hyd', a)


def test_more_than_30_steps_are_preserved(archive):
    text = TEXT.split('1.')[0] + ''.join(f'{i}. 확인 {i}\n' for i in range(1, 106))
    _, body = reviewed(archive, text)
    plan = manual_review.validate(archive, 'hyd', body)
    assert len(plan['procedures'][0]['steps']) == 105
    assert len([n for n in manual_graph.desired(plan)['nodes'] if n['labels'] == ['Step']]) == 105


def test_ocr_required_is_not_partially_committed(archive):
    from pypdf import PdfWriter
    import io
    pdf = PdfWriter()
    pdf.add_blank_page(100, 100)
    stream = io.BytesIO()
    pdf.write(stream)
    source = archive.save('hyd', 'empty.pdf', stream.getvalue())
    body = manual_review.proposal(source) | {'by': '검토자', 'reviewed': True}
    with pytest.raises(ValueError, match='OCR'):
        manual_review.validate(archive, 'hyd', body)


def test_other_tenant_cannot_review_source(archive):
    _, body = reviewed(archive)
    with pytest.raises(KeyError):
        manual_review.validate(archive, 'elsewhere', body)


def test_archived_pending_sources_are_paginated_and_tenant_scoped(archive):
    for i in range(4):
        archive.save('hyd', f'file-{i}.md', TEXT.encode())
    archive.save('another', 'hidden.md', TEXT.encode())
    page1 = archive.list('hyd', 2, 0)
    page2 = archive.list('hyd', 2, page1['next_offset'])
    assert page1['total'] == 4 and page2['next_offset'] is None
    assert len({p['source_id'] for p in page1['items'] + page2['items']}) == 4
    assert not archive.list('missing')['items']
    with pytest.raises(ValueError):
        archive.list('hyd', 200, 0)
