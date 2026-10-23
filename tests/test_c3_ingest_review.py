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


def test_execution_body_mutation_cannot_rewrite_review_record_or_extraction(doc):
    _, source, preview = doc
    record = review(links=fix_13())
    original_record, original_preview = copy.deepcopy(record), copy.deepcopy(preview)
    body, changes = c3_ingest.apply_review('PR-07', preview, source, record)
    body['links']['SOP-PUR-13']['actions'][0]['value'] = 'sup:b'
    body['extraction']['instance'] = 'another-extraction'
    assert record == original_record and preview == original_preview
    assert changes[0]['after']['actions'][0]['value'] == 'sup:c'


def test_delegated_review_preserves_actor_method_and_explicit_empty_link(doc):
    _, source, preview = doc
    preview['links'] = {'SOP-PUR-13': {}}
    before = copy.deepcopy(preview)
    body, _ = c3_ingest.apply_review('PR-07', preview, source,
                                  review(by='사용자 위임 Codex', method='user-delegated-ai-review'))
    assert body['method'] == 'user-delegated-ai-review' and body['by'] == '사용자 위임 Codex'
    assert body['links']['SOP-PUR-13'] == {} and preview == before


def test_delegated_review_does_not_replace_real_extraction_contract(doc):
    from procsvc.manual_extraction import CONTRACT
    archive, source, preview = doc
    preview['method'] = CONTRACT
    original = copy.deepcopy(preview)
    body, _ = c3_ingest.apply_review('PR-07', preview, source,
                                  review(by='사용자 위임 Codex', method='user-delegated-ai-review'))
    assert body['method'] == CONTRACT and body['extraction'] == preview['extraction']
    assert body['review_method'] == 'user-delegated-ai-review' and preview == original
    plan = manual_review.validate(archive, 'hyd', body)
    assert plan['method'] == CONTRACT and plan['review_method'] == 'user-delegated-ai-review'


def test_commit_checks_provided_extraction_even_if_contract_marker_is_changed(doc):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import manual_api
    archive, source, preview = doc
    body, _ = c3_ingest.apply_review('PR-07', preview, source, review())
    body.update(method='human-reviewed', extraction={'instance': None})
    graph_calls = []
    def graph():
        graph_calls.append(True)
        raise AssertionError('Invalid extraction reached graph writes')
    app = FastAPI()
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=graph, tenant='hyd', audit=lambda *a: None)
    with TestClient(app) as client:
        response = client.post('/api/kg/manuals/commit', json=body)
    assert response.status_code == 400 and '실제 작업 연결' in response.json()['detail']
    assert graph_calls == []


def test_source_step_review_anchors_every_text_and_keeps_original_proposal(doc):
    _, source, preview = doc
    original = copy.deepcopy(preview)
    p = next(p for p in preview['procedures'] if p['id'] == 'SOP-PUR-13')
    steps = [dict(order=s['order'], manual=s['manual'], text=s['anchor']['quote'], quote=s['anchor']['quote']) for s in p['steps']]
    record = review(procedures={'SOP-PUR-13': dict(set={'steps': steps}, quote=STEP1, reason='원문 문장과 단계별 인용을 정확히 보존')})
    body, changes = c3_ingest.apply_review('PR-07', preview, source, record)
    checked = next(p for p in body['procedures'] if p['id'] == 'SOP-PUR-13')['steps']
    assert len(checked) == len(p['steps']) and changes[0]['kind'] == 'procedure'
    for step in checked:
        at = step['anchor']
        assert source['pages'][at['page']-1]['text'][at['start']:at['end']] == step['text']
    assert preview == original
    record['procedures']['SOP-PUR-13']['set']['steps'][0]['text'] = '승인 없이 실행한다'
    with pytest.raises(c3_ingest.ReviewError, match='정확한 원문 텍스트'):
        c3_ingest.apply_review('PR-07', preview, source, record)


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


def test_commit_conflict_preserves_reviewed_body_and_never_drops_or_retries(doc, tmp_path, monkeypatch):
    import json
    _, source, preview = doc
    preview['knowledge_conflicts'] = [{'id': preview['knowledge']['rules'][0]['id']}]
    rec = dict(preview=preview, source_id=source['source_id'], instance=preview['extraction']['instance'])
    (tmp_path/'proposal-PR-07.json').write_text(json.dumps(rec), encoding='utf-8')
    review_file = tmp_path/'review.json'
    review_file.write_text(json.dumps(review()), encoding='utf-8')
    monkeypatch.setattr(c3_ingest, 'OUT', tmp_path)
    writes = []
    def call(method, path, body=None, timeout=120):
        if method == 'GET': return 200, source
        writes.append(copy.deepcopy(body))
        return 409, {'error': 'Existing knowledge belongs to another document'}
    monkeypatch.setattr(c3_ingest, 'call', call)
    assert c3_ingest.commit('PR-07', review_file) == 409
    assert len(writes) == 1 and writes[0]['knowledge'] == preview['knowledge']
    result = json.loads((tmp_path/'ingest-PR-07.json').read_text(encoding='utf-8'))
    assert result['dropped_conflicts'] == [] and result['commit_status'] == 409


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


def _fake_api(monkeypatch, sources, runs, previews):
    """원문 목록 · 추출 이력 · 추출 결과만 답하는 가짜 process API. 새 추출 시작(POST)은 시험 실패로 둔다."""
    posted = []
    def call(method, path, body=None):
        if method != "GET":
            posted.append(path)
            raise AssertionError(f"--reuse 가 새 추출을 시작했다: {path}")
        if path.startswith("/api/kg/manuals/sources?"):
            return 200, dict(items=sources, next_offset=None)
        sid, _, rest = path[len("/api/kg/manuals/sources/"):].partition("/extractions")
        if rest == "":
            return 200, dict(items=[dict(proc_inst_id=i) for i in runs.get(sid, [])])
        inst = rest.lstrip("/")
        return 200, ({"preview": previews[inst]} if inst in previews else {"status": "COMPLETED", "preview": None})
    monkeypatch.setattr(c3_ingest, "call", call)
    return posted


def test_reuse_finds_the_finished_extraction_on_an_older_source_of_the_same_content(monkeypatch):
    # 2026-10-23 리허설: 원문을 다시 올리면 판본 id 가 새로 생겨, 이번 판본만 보던 --reuse 가 검토 없는 새 추출을 시작했다
    src = lambda doc, sha="s" * 64, fname="PR-07_spare-parts-standard.md": dict(source_id=f"manual:{doc}:{sha}", sha256=sha, filename=fname)
    sources = [src("new"), src("old"), src("other", sha="t" * 64)]
    posted = _fake_api(monkeypatch, sources, runs={"manual:new:" + "s" * 64: ["closed"], "manual:old:" + "s" * 64: ["passed"]},
                       previews={"passed": {"procedures": []}})
    sid, inst = c3_ingest.finished_extraction("PR-07", "PR-07_spare-parts-standard.md", "s" * 64)
    assert (sid, inst) == ("manual:old:" + "s" * 64, {"instance": "passed", "reused": True}) and posted == []


def test_reuse_stops_instead_of_starting_an_unreviewed_extraction(monkeypatch):
    sources = [dict(source_id="manual:new:" + "s" * 64, sha256="s" * 64, filename="PR-07_spare-parts-standard.md")]
    posted = _fake_api(monkeypatch, sources, runs={"manual:new:" + "s" * 64: ["closed"]}, previews={})
    with pytest.raises(SystemExit, match="다시 쓸 끝난 추출이 없습니다"):
        c3_ingest.finished_extraction("PR-07", "PR-07_spare-parts-standard.md", "s" * 64)
    assert posted == []


def test_reuse_with_a_loaded_document_picks_only_that_documents_extraction(monkeypatch):
    # audit2 I4: 같은 파일을 「새 문서」로 다시 올린 적이 있으면 최근순 첫 판본이 다른 문서의 것이라, 적재가 지금 문서가 소유한
    # 절차를 덮어쓰지 못해 409 로 거절됐다. 지금 적재된 문서가 있으면 그 문서의 판본만 본다.
    sha = "s" * 64
    sources = [dict(source_id=f"manual:doc-again:{sha}", document_id="doc-again", sha256=sha, filename="PR-07_spare-parts-standard.md"),
               dict(source_id=f"manual:doc-now:{sha}", document_id="doc-now", sha256=sha, filename="PR-07_spare-parts-standard.md")]
    posted = _fake_api(monkeypatch, sources, runs={f"manual:doc-again:{sha}": ["other-doc"], f"manual:doc-now:{sha}": ["this-doc"]},
                       previews={"other-doc": {"procedures": []}, "this-doc": {"procedures": []}})
    assert c3_ingest.finished_extraction("PR-07", "PR-07_spare-parts-standard.md", sha, "doc-now") == (
        f"manual:doc-now:{sha}", {"instance": "this-doc", "reused": True})
    # 처음 적재(지금 적재된 문서 없음)는 문서를 가리지 않고 최근 판본부터 본다
    assert c3_ingest.finished_extraction("PR-07", "PR-07_spare-parts-standard.md", sha)[0] == f"manual:doc-again:{sha}"
    assert posted == []


def test_reuse_does_not_fall_back_to_another_documents_extraction(monkeypatch):
    # 지금 문서에 끝난 추출이 없으면 다른 문서의 끝난 추출로 넘어가지 않고 멈춘다(목록 행에 document_id 가 없으면 source_id 로 가린다)
    sha = "s" * 64
    sources = [dict(source_id=f"manual:doc-again:{sha}", sha256=sha, filename="PR-07_spare-parts-standard.md"),
               dict(source_id=f"manual:doc-now:{sha}", sha256=sha, filename="PR-07_spare-parts-standard.md")]
    posted = _fake_api(monkeypatch, sources, runs={f"manual:doc-again:{sha}": ["other-doc"], f"manual:doc-now:{sha}": ["closed"]},
                       previews={"other-doc": {"procedures": []}})
    with pytest.raises(SystemExit, match="지금 적재된 문서 doc-now의 .*원문 판본 1개"):
        c3_ingest.finished_extraction("PR-07", "PR-07_spare-parts-standard.md", sha, "doc-now")
    assert posted == []


def test_extract_reuse_looks_only_at_the_loaded_document(monkeypatch, tmp_path):
    # extract --reuse 는 원문을 올릴 때 쓴 지금 적재된 문서 id 를 끝난 추출 찾기에도 그대로 넘긴다
    sha = "s" * 64
    docs = tmp_path / "문서/시스템/참조/수업_문서_원문"
    docs.mkdir(parents=True)
    (docs / "PR-07_spare-parts-standard.md").write_bytes((c3_ingest.ROOT / "문서/시스템/참조/수업_문서_원문/PR-07_spare-parts-standard.md").read_bytes())
    monkeypatch.setattr(c3_ingest, "ROOT", tmp_path)
    monkeypatch.setattr(c3_ingest, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(c3_ingest, "loaded_document", lambda fname: "doc-now")
    seen = {}
    def call(method, path, body=None, timeout=120):
        if path == "/api/kg/manuals/preview":
            seen["upload_document"] = body["document_id"]
            return 200, {"source_id": f"manual:doc-now:{sha}"}
        assert method == "GET", path
        return 200, {"preview": {"procedures": [], "extraction": {"instance": "this-doc"}}}
    def finished(key, fname, got_sha, document_id=None):
        seen["reuse_document"], seen["sha"] = document_id, got_sha
        return f"manual:doc-now:{sha}", {"instance": "this-doc", "reused": True}
    monkeypatch.setattr(c3_ingest, "call", call)
    monkeypatch.setattr(c3_ingest, "finished_extraction", finished)
    rec = c3_ingest.extract("PR-07", reuse=True)
    assert seen == {"upload_document": "doc-now", "reuse_document": "doc-now", "sha": sha}
    assert rec["source_id"] == f"manual:doc-now:{sha}" and rec["reused_extraction"] is True
