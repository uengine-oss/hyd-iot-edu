"""Deterministic cache behavior, never evidence of independent AI quality."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest

from procsvc import manual_cache, manual_extraction as extraction
from test_manual_extraction import document, rt


PROFILE = dict(model='classroom-model', revision='instructor-config-1')


def start(runtime, source, **kwargs):
    args = dict(scope='class-1/approved-v1', profile=PROFILE)
    args.update(kwargs)
    return manual_cache.start(runtime, source, str(uuid4()), None, **args)


def complete(runtime, proposal):
    wi = runtime.repo.fetch_pending_task('cliagents', 'cache-test')[0]
    runtime.repo.save_task_result(wi['id'], {'proposal': deepcopy(proposal)}, final=True)
    runtime.poll_once()


def test_concurrent_new_request_ids_join_one_persistent_extraction(rt, document):
    runtime, _ = rt
    archive, source, _ = document
    source = archive.get('hyd', source['source_id'])
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: start(runtime, source), range(8)))
    assert len({r['instance'] for r in replies}) == 1
    assert sum(not r['cache']['reused'] for r in replies) == 1
    assert all(not r['cache']['validated'] for r in replies)
    assert len(runtime.repo.list_workitems(proc_inst_id=replies[0]['instance'])) == 1


def test_renamed_identical_upload_reuses_result_but_keeps_new_review_identity(rt, document):
    runtime, _ = rt
    archive, source, proposal = document
    source = archive.get('hyd', source['source_id'])
    first = start(runtime, source)
    complete(runtime, proposal)
    other = archive.save('hyd', 'new-name.txt', archive.original('hyd', source['source_id']))
    other = archive.get('hyd', other['source_id'])
    again = start(runtime, other)
    assert again['instance'] == first['instance'] and again['cache']['reused']
    result = manual_cache.result(runtime, archive, other, again['instance'], 'current-graph-head')
    preview = result['preview']
    assert result['cache']['validated'] and result['status'] == 'DONE'
    assert preview['source_id'] == other['source_id']
    assert preview['filename'] == 'new-name.txt' and preview['document_id'] == other['document_id']
    assert preview['previous_batch'] == 'current-graph-head' and 'reviewed' not in preview
    extraction.validate_proposal(other, {k: v for k, v in preview.items() if k in extraction.PROPOSAL_KEYS})
    assert preview['procedures'][0]['anchor']['source_id'] == other['source_id']


@pytest.mark.parametrize('change', ['scope', 'profile', 'catalog', 'source', 'instruction', 'tenant'])
def test_cache_key_separates_all_extraction_inputs(document, monkeypatch, change):
    _, source, _ = document
    args = dict(tenant='hyd', source=deepcopy(source), catalog={}, scope='class-1', profile=PROFILE)
    before = manual_cache.identity(**args)
    if change == 'scope': args['scope'] = 'class-2'
    if change == 'profile': args['profile'] = dict(PROFILE, revision='new')
    if change == 'catalog': args['catalog'] = {'schema_version': 'next'}
    if change == 'source': args['source']['pages'][0]['text'] += '다른 내용'
    if change == 'instruction': monkeypatch.setattr(extraction, 'INSTRUCTION', extraction.INSTRUCTION+' 새 지시')
    if change == 'tenant': args['tenant'] = 'other-student'
    assert manual_cache.identity(**args) != before


@pytest.mark.parametrize('damage', ['semantic', 'citation'])
def test_completed_cache_is_revalidated_before_reuse(rt, document, damage):
    runtime, _ = rt
    archive, source, proposal = document
    source = archive.get('hyd', source['source_id'])
    first = start(runtime, source)
    complete(runtime, proposal)
    assert manual_cache.result(runtime, archive, source, first['instance'], None)['cache']['validated']
    # Simulate damaged persisted output, after the normal completion gate.
    wi = runtime.repo.list_workitems(proc_inst_id=first['instance'])[0]
    stored = runtime.repo.workitems[wi['id']]['output']['proposal']
    if damage == 'semantic':
        stored['sections'][0]['title'] = 'section-1 정비 절차'
    else:
        stored['procedures'][0]['anchor']['quote'] = '원문에 없는 근거'
    again = start(runtime, source)
    assert again['instance'] == first['instance'] and again['cache']['reused']
    with pytest.raises(ValueError):
        manual_cache.result(runtime, archive, source, again['instance'], None)
    assert len(runtime.repo.list_workitems(proc_inst_id=first['instance'])) == 1
    assert not runtime.repo.fetch_pending_task('cliagents', 'cache-retry')


def test_failed_or_unverified_run_is_not_success_and_does_not_spawn_paid_retry(rt, document):
    runtime, _ = rt
    archive, source, _ = document
    source = archive.get('hyd', source['source_id'])
    first = start(runtime, source)
    wi = runtime.repo.fetch_pending_task('cliagents', 'cache-test')[0]
    runtime.repo.save_task_result(wi['id'], {'proposal': {}}, final=True)
    runtime.poll_once()
    again = start(runtime, source)
    assert again['instance'] == first['instance']
    result = manual_cache.result(runtime, archive, source, first['instance'], None)
    assert result['preview'] is None and not result['cache']['validated']
    runtime.repo.update_task_error(wi['id'])
    failed = manual_cache.result(runtime, archive, source, first['instance'], None)
    assert failed['status'] == 'FAILED' and not failed['cache']['validated']
    runtime.close_agent_task(wi['id'], 'teacher', '추출 중단')
    stopped = start(runtime, source)
    assert stopped['instance'] == first['instance']
    assert manual_cache.result(runtime, archive, source, first['instance'], None)['status'] == 'CANCELLED'


def test_other_content_or_tenant_cannot_read_cached_proposal(rt, document):
    runtime, _ = rt
    archive, source, proposal = document
    source = archive.get('hyd', source['source_id'])
    run = start(runtime, source)
    complete(runtime, proposal)
    other = archive.save('hyd', 'other.txt', b'not the same document')
    with pytest.raises(ValueError, match='캐시 원문'):
        manual_cache.result(runtime, archive, other, run['instance'], None)
    runtime.tenant_id = 'other-student'
    with pytest.raises(KeyError):
        manual_cache.result(runtime, archive, source, run['instance'], None)


def test_http_request_cannot_choose_its_own_cache_scope_or_model(rt, document, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from procsvc import manual_api
    runtime, _ = rt
    archive, source, _ = document
    class Graph:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def session(self): return self
    allowed = [True]
    def authority(source, feedback):
        if not allowed[0]: raise HTTPException(403, '승인 취소')
        return dict(scope='teacher-v1', profile=PROFILE)
    monkeypatch.setattr(manual_api.manual_knowledge, 'catalog', lambda _: {})
    app = FastAPI()
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=Graph,
                        tenant='hyd', audit=lambda *a: None, runtime_factory=lambda: runtime,
                        cache_context=authority)
    client = TestClient(app)
    path = '/api/kg/manuals/sources/'+source['source_id']+'/extractions'
    first = client.post(path, json={'request_id': str(uuid4())}).json()
    second = client.post(path, json=dict(request_id=str(uuid4()), scope='forged', profile={'model': 'other'},
                                         reextract=True, force=True)).json()
    assert first['instance'] == second['instance'] and second['cache']['reused']
    assert client.get(path).json()['items'][0]['proc_inst_id'] == first['instance']
    allowed[0] = False
    assert client.post(path, json={'request_id': str(uuid4())}).status_code == 403
    assert client.get(path+'/'+first['instance']).status_code == 403
    assert client.get(path).status_code == 403


def test_partial_segment_creation_recovers_once_with_original_source_identity(rt, document, monkeypatch):
    from procsvc import engine, manual_segments
    runtime, _ = rt
    archive, source, _ = document
    source = archive.get('hyd', source['source_id'])
    alias = archive.save('hyd', 'renamed.txt', archive.original('hyd', source['source_id']))
    alias = archive.get('hyd', alias['source_id'])
    monkeypatch.setattr(manual_segments, 'DEFAULT_MAX_CHARS', 2000)
    create = runtime.start_definition
    owner, follower = str(uuid4()), str(uuid4())
    def interrupted(*args, **kwargs):
        if args[2].endswith(':2'): raise RuntimeError('simulated process interruption')
        return create(*args, **kwargs)
    monkeypatch.setattr(runtime, 'start_definition', interrupted)
    with pytest.raises(RuntimeError, match='simulated'):
        start(runtime, source, execution_run_id=owner)
    monkeypatch.setattr(runtime, 'start_definition', create)
    recovered = start(runtime, alias, execution_run_id=follower)
    assert recovered['cache']['reused'] and recovered['segments'] > 1
    for i in range(1, recovered['segments']+1):
        inst = runtime.repo.find_event_instance('hyd', extraction.DEFINITION_ID,
                'manual-extraction:cache:'+recovered['cache']['key']+':'+str(i))
        assert engine.variables(inst)['manual_source']['source_id'] == source['source_id']
        assert engine.variables(inst)['extraction_cache']['execution_run_id'] == owner
        assert len(runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])) == 1
    result = manual_cache.result(runtime, archive, alias, recovered['instance'], None)
    assert result['progress']['total'] == recovered['segments'] and not result['cache']['validated']
