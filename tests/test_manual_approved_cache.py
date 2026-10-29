"""Real provided documents through the normal runtime; no model test double."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest

from hydcommon import course_access as rules
from procsvc import engine, manual_api, manual_cache, manual_extraction
from procsvc.manual_approved_cache import ApprovedExtractions, BUNDLE
from procsvc.manual_sources import ManualSources
from test_instances import rt


ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT / '문서/시스템/참조/수업_문서_원문'


@pytest.fixture
def provided(tmp_path):
    cache = ApprovedExtractions()
    archive = ManualSources(tmp_path / 'manuals.sqlite3')
    sources = [archive.get('hyd', archive.save('hyd', e['filename'],
               (ORIGINALS/e['filename']).read_bytes())['source_id']) for e in cache.payload['documents'].values()]
    return cache, archive, sources


def test_all_four_proposals_complete_normally_without_becoming_worker_jobs(rt, provided):
    runtime, _ = rt
    cache, archive, sources = provided
    expected = [(7, 25), (8, 33), (4, 16), (3, 12)]
    for source, counts in zip(sources, expected):
        run = cache.start(runtime, source, str(uuid4()), None)
        assert run['status'] == 'SUBMITTED'
        assert not runtime.repo.fetch_pending_task('cliagents', 'must-never-run')
        assert runtime.poll_once() == 1
        result = manual_cache.result(runtime, archive, source, run['instance'], 'current-head')
        assert result['status'] == 'DONE' and result['cache']['validated']
        preview = result['preview']
        assert (len(preview['procedures']), sum(len(p['steps']) for p in preview['procedures'])) == counts
        assert preview['extraction']['session_id'] is None
        assert preview['extraction']['cache']['origin']['bundle'] == cache.digest
        assert preview['previous_batch'] == 'current-head'
        assert 'reviewed' not in preview and 'by' not in preview
        assert runtime.repo.get_instance(run['instance'])['status'] == 'COMPLETED'
        assert not runtime.repo.fetch_pending_task('cliagents', 'must-never-run')


def test_concurrent_renamed_uploads_join_and_recover_after_process_recreation(rt, provided):
    from procsvc.instances import InstanceRuntime
    runtime, hooks = rt
    cache, archive, sources = provided
    original = sources[0]
    alias = archive.save('hyd', '학생이 바꾼 이름.md', archive.original('hyd', original['source_id']))
    alias = archive.get('hyd', alias['source_id'])
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(lambda i: cache.start(runtime, original if i%2 else alias, str(uuid4()), {}), range(6)))
    assert len({r['instance'] for r in runs}) == 1
    assert sum(not r['cache']['reused'] for r in runs) == 1
    recovered = InstanceRuntime(runtime.repo, runtime.defn, hooks, tenant_id='hyd')
    assert recovered.poll_once() == 1
    value = manual_cache.result(recovered, archive, alias, runs[0]['instance'], None)
    assert value['status'] == 'DONE'
    assert value['preview']['filename'] == alias['filename']
    assert value['preview']['procedures'][0]['anchor']['source_id'] == alias['source_id']
    assert not recovered.repo.fetch_pending_task('cliagents', 'never')


def test_unknown_content_parser_drift_and_reextraction_do_not_enqueue(rt, provided):
    runtime, _ = rt
    cache, archive, sources = provided
    own = archive.save('hyd', '개인문서.md', b'# private\nnew content')
    for source in (own, dict(sources[0], pages=[{'page':1, 'text':'changed'}]),
                   dict(sources[0], extractor='different-parser')):
        with pytest.raises(ValueError):cache.start(runtime, source, str(uuid4()), None)
    with pytest.raises(ValueError, match='검토 화면'):
        cache.start(runtime, sources[0], str(uuid4()), None,
                    {'by':'학생','items':[{'target':'x','verdict':'MISSING','note':'더 써줘'}]})
    assert not runtime.repo.list_workitems(limit=None)


def test_bundle_signature_blocks_modified_outputs_and_missing_approval(tmp_path, provided):
    cache, _, sources = provided
    envelope = json.loads(BUNDLE.read_text(encoding='utf8'))
    first = next(iter(envelope['payload']['documents'].values()))
    first['proposal']['procedures'][0]['steps'][0]['text'] = '변조'
    bad = tmp_path/'tampered.json'
    bad.write_text(json.dumps(envelope), encoding='utf8')
    with pytest.raises(ValueError, match='서명'):ApprovedExtractions(bad)
    cache.payload['documents'].pop(sources[0]['sha256'])
    with pytest.raises(ValueError):cache.authorize(sources[0])


def test_cached_creation_is_atomic_if_persistence_fails(rt, provided, monkeypatch):
    runtime, _ = rt
    cache, _, sources = provided
    insert = runtime.repo.insert_workitems
    def fail(items):
        assert all(i['status'] == 'SUBMITTED' for i in items)
        raise RuntimeError('disk failure')
    monkeypatch.setattr(runtime.repo, 'insert_workitems', fail)
    with pytest.raises(RuntimeError, match='disk failure'):
        cache.start(runtime, sources[0], str(uuid4()), None)
    assert not runtime.repo.list_workitems(limit=None)
    assert not runtime.repo.instances
    monkeypatch.setattr(runtime.repo, 'insert_workitems', insert)
    run = cache.start(runtime, sources[0], str(uuid4()), None)
    assert run['status'] == 'SUBMITTED'


def test_approved_http_path_history_and_commit_keep_the_same_cache_binding(rt, provided, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    runtime, _ = rt
    cache, archive, sources = provided
    class Graph:
        def __enter__(self):return self
        def __exit__(self, *args):pass
        def session(self):return self
        def execute_read(self, fn):return []
    monkeypatch.setattr(manual_api.manual_knowledge, 'catalog', lambda _: {})
    monkeypatch.setattr(manual_api.manual_graph, 'head', lambda *a: None)
    monkeypatch.setattr(manual_api.manual_graph, 'sop_conflicts', lambda *a: [])
    monkeypatch.setattr(manual_api.manual_knowledge, 'conflicts', lambda *a: [])
    monkeypatch.setattr(manual_api.manual_preflight, 'validate', lambda *a: {'errors':[]})
    monkeypatch.setattr(manual_api.manual_knowledge, 'check_graph', lambda *a: None)
    monkeypatch.setattr(manual_api.manual_graph, 'commit', lambda s,p: dict(batch=p['batch'], source_id=p['source_id'],
                       filename=p['filename'], sections=len(p['sections']), procedures=len(p['procedures']),steps=12))
    app = FastAPI()
    manual_api.register(app, archive_factory=lambda:archive, driver_factory=Graph, tenant='hyd',
                        audit=lambda *a:None, runtime_factory=lambda:runtime, approved_cache=cache)
    client = TestClient(app)
    source = sources[-1]
    path = '/api/kg/manuals/sources/'+source['source_id']+'/extractions'
    started = client.post(path, json={'request_id':str(uuid4()), 'model':'forged','force':True})
    assert started.status_code == 200, started.text
    pid = started.json()['instance']
    runtime.poll_once()
    result = client.get(path+'/'+pid)
    assert result.status_code == 200, result.text
    preview = result.json()['preview']
    assert client.get(path).json()['items'][0]['proc_inst_id'] == pid
    # A cache flag appended by the read endpoint must not make normal review
    # fail the commit-time extraction-generation comparison.
    preview.update(by='학생 검토',reviewed=True,links={p['id']:p['link'] for p in preview['procedures']})
    committed = client.post('/api/kg/manuals/commit', json=preview)
    assert committed.status_code == 200, committed.text
    assert not runtime.repo.fetch_pending_task('cliagents','never')


def test_a_cache_miss_cannot_fall_back_to_student_live_extraction():
    # Course actions are open, but an extraction reaching the live worker is a cache miss, never a paid fallback.
    with pytest.raises(ValueError):
        rules.authorize_task({'processDefinitionId':manual_extraction.DEFINITION_ID},
                             manual_extraction.ACTIVITY, {'manual_source':{'sha256':rules.CONTENT['document_hashes'][0]}})
