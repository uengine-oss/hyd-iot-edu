"""라이브 적재 스크립트(scripts/c3_ingest.py)는 사람의 검토 기록 없이 적재하지 않는다.

2026-10-10 전에는 추출 제안을 손대지 않고 reviewed=true · 지어낸 검토자 이름으로 적재했다. 라이브 4차 C 판단은 그 검토되지 않은
지식(SOP-PUR-13 → A정밀, 원문 1단계 "견적 공급사 중 리드타임이 가장 짧은 공급사를 고른다"와 다름)으로 돌았다.
여기서는 네트워크 없이 검토 적용(apply_review)만 본다. 제안은 C1 시험 대역(원문 인용에 묶인 결정론 제안)으로 만든다.
"""
import copy
import sys
from pathlib import Path

import pytest

import c1_fixtures as fx
from procsvc import manual_review
from procsvc.manual_sources import ManualSources

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import c3_ingest  # noqa: E402

STEP1 = '견적 공급사 중 리드타임이 가장 짧은 공급사를 고른다.'


@pytest.fixture
def doc(tmp_path):
    """라이브 4차와 같은 오연결(SOP-PUR-13 → sup:a)을 가진 PR-07 추출 제안."""
    archive = ManualSources(tmp_path / 'manuals.sqlite')
    source = archive.save('hyd', fx.DOC_C.name, fx.DOC_C.read_bytes())
    links = copy.deepcopy(fx.C_LINKS)
    links['SOP-PUR-13']['actions'] = [dict(action='action:purchase-request', value='sup:a')]
    preview = fx.proposal(source, fx.C_KNOWLEDGE, links)
    preview.update(batch=manual_review.proposal(source)['batch'], extraction=dict(instance='manual_source_extraction.x1'),
                   warnings=['SOP-PUR-13 공급사 값은 추론 — 사람 검토가 필요하다'])
    return archive, source, preview


def review(**kw):
    return dict(dict(doc='PR-07', by='정구매', extraction='manual_source_extraction.x1', warnings_read=True), **kw)


def fix_13(quote=STEP1, **kw):
    return {'SOP-PUR-13': dict(dict(set={'actions': [dict(action='action:purchase-request', value='sup:c')]},
                                    reason='1단계 기준(견적 중 최단 리드타임)은 C트레이딩 1일. AVL 아님은 2단계 규정(EXCLUDE)이 판단', quote=quote), **kw)}


def test_reviewer_link_correction_is_applied_with_reason_and_source_coordinates(doc):
    archive, source, preview = doc
    body, changes = c3_ingest.apply_review('PR-07', preview, source, review(links=fix_13()))
    assert body['links']['SOP-PUR-13']['actions'] == [dict(action='action:purchase-request', value='sup:c')]
    assert body['links']['SOP-PUR-11'] == preview['procedures'][0]['link']               # 검토가 고치지 않은 연결은 제안 그대로
    assert body['by'] == '정구매' and body['reviewed'] is True
    (c,) = changes
    assert c['kind'] == 'link' and c['before'] == {'actions': [dict(action='action:purchase-request', value='sup:a')]}
    text = source['pages'][c['anchor']['page'] - 1]['text']
    assert text[c['anchor']['start']:c['anchor']['end']] == STEP1
    plan = manual_review.validate(archive, 'hyd', body)                                     # 적재 API 의 검증을 그대로 통과한다
    assert next(p for p in plan['procedures'] if p['id'] == 'SOP-PUR-13')['actions'][0]['value'] == 'sup:c'


def test_accepting_the_proposal_as_is_is_still_an_explicit_reviewed_decision(doc):
    archive, source, preview = doc
    body, changes = c3_ingest.apply_review('PR-07', preview, source, review())
    assert changes == [] and body['by'] == '정구매'
    assert body['links']['SOP-PUR-13']['actions'][0]['value'] == 'sup:a'
    manual_review.validate(archive, 'hyd', body)


@pytest.mark.parametrize('bad, message', [
    (dict(doc='HM-8'), '이 문서의 검토 기록이 아닙니다'),
    (dict(by=' '), '검토한 사람'),
    (dict(extraction='manual_source_extraction.other'), '다른 제안을 검토했습니다'),
    (dict(warnings_read=None), 'warnings_read'),
    (dict(links=fix_13(quote='원문에 없는 문장')), '인용문이 원문에 한 번만'),
    (dict(links=fix_13(quote='승인: 구매 담당.')), '인용문이 원문에 한 번만'),          # 세 번 나오는 문장은 근거 좌표가 정해지지 않는다
    (dict(links=fix_13(reason='')), '검토 사유'),
    (dict(links={'SOP-PUR-99': fix_13()['SOP-PUR-13']}), '제안에 없는 SOP'),
    (dict(links={'SOP-PUR-13': dict(fix_13()['SOP-PUR-13'], set={'steps': []})}), 'set 은 연결 필드'),
    (dict(drop={'rule:nope': dict(reason='x', quote=STEP1)}), '제안 지식에 없는 id'),
])
def test_review_records_that_do_not_match_the_proposal_or_the_source_are_refused(doc, bad, message):
    _, source, preview = doc
    with pytest.raises(c3_ingest.ReviewError, match=message):
        c3_ingest.apply_review('PR-07', preview, source, review(**bad))


def test_reviewer_can_drop_and_add_rules_only_with_a_quote_from_the_source(doc):
    archive, source, preview = doc
    lead = next(r for r in fx.C_KNOWLEDGE['rules'] if r['id'] == 'rule:pur-lead')
    added = dict({k: v for k, v in lead.items() if k != 'quote'}, id='rule:pur-lead-2', quote=lead['quote'], reason='다시 넣기 시험')
    body, changes = c3_ingest.apply_review('PR-07', preview, source, review(
        drop={'rule:pur-lead': dict(reason='중복 시험', quote=lead['quote'])}, add={'rules': [added]}))
    ids = [r['id'] for r in body['knowledge']['rules']]
    assert 'rule:pur-lead' not in ids and 'rule:pur-lead-2' in ids
    assert [c['kind'] for c in changes] == ['drop', 'add']
    new = next(r for r in body['knowledge']['rules'] if r['id'] == 'rule:pur-lead-2')
    assert 'quote' not in new and 'reason' not in new and new['anchor']['quote'] == lead['quote']
    manual_review.validate(archive, 'hyd', body)


def test_commit_without_a_review_file_does_not_run():
    assert c3_ingest.main(['commit', 'PR-07']) == 2
    assert c3_ingest.main(['load', 'PR-07']) == 2


def _history(monkeypatch, status, rows):
    monkeypatch.setattr(c3_ingest, 'call', lambda method, path, body=None, timeout=120: (status, rows))


def test_reextraction_revises_the_loaded_document_instead_of_creating_a_new_one(monkeypatch):
    """같은 파일을 다시 뽑을 때는 지금 적재된 문서 id 로 올린다(포털 [개정]과 같은 계약). 새 문서로 올리면 적재가 옛 문서의 절차를
    덮어쓰지 못해 409 — 2026-10-10 라이브에서 실제로 났다. 지난 판 · 다른 파일은 고르지 않는다."""
    _history(monkeypatch, 200, [dict(filename='PR-07_spare-parts-standard.md', document_id='doc-old', current=False),
                                dict(filename='PR-07_spare-parts-standard.md', document_id='doc-now', current=True),
                                dict(filename='HM-8_cooler-fan-manual.md', document_id='doc-hm8', current=True)])
    assert c3_ingest.loaded_document('PR-07_spare-parts-standard.md') == 'doc-now'
    assert c3_ingest.loaded_document('PM-02_powerpack-pm-checklist.md') is None    # 처음 적재는 새 문서


@pytest.mark.parametrize('status, rows, message', [
    (500, {'error': 'neo4j down'}, '적재 이력 읽기 실패'),
    (200, [dict(filename='PR-07_spare-parts-standard.md', document_id=d, current=True) for d in ('doc-a', 'doc-b')], '2개'),
])
def test_unreadable_or_ambiguous_load_history_stops_instead_of_guessing(monkeypatch, status, rows, message):
    _history(monkeypatch, status, rows)
    with pytest.raises(SystemExit, match=message):
        c3_ingest.loaded_document('PR-07_spare-parts-standard.md')
