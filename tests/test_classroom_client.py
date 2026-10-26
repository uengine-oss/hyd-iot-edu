"""Student transport and source review boundaries; no paid model calls."""
import base64
import json
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from procsvc import classroom_client, manual_cache, manual_api, manual_extraction
from test_manual_extraction import document


@pytest.fixture
def remote(tmp_path, document):
    archive, source, proposal = document
    run_id = str(uuid4())
    state = dict(allowed=True, fail=False, requests=[])
    value = dict(status='DONE', cache=dict(validated=True, stored=True, key='test-cache'),
                 preview=manual_extraction._preview(source, proposal, None, {}),
                 source_fingerprint=manual_cache.source_fingerprint(source))
    state['value'] = value
    def respond(request):
        state['requests'].append(request)
        if state['fail']: raise httpx.ConnectError('private upstream detail')
        if not state['allowed']: return httpx.Response(403, text='private upstream detail')
        if request.method == 'POST':
            assert json.loads(request.content) == {'sha256': source['sha256']}
            return httpx.Response(200, json=dict(run_id=run_id, state='RESERVED', reused=True))
        if request.url.path.endswith('/result'): return httpx.Response(200, json=state['value'])
        return httpx.Response(200, json=dict(scope='teacher-scope', profile={'model':'approved','revision':'1'}))
    client = classroom_client.Client('https://class.example', lambda: 'test-key-'+'x'*40,
        tmp_path/'history.sqlite3', transport=httpx.MockTransport(respond))
    return client, state, archive, source, run_id


def test_remote_result_rebinds_renamed_source_and_keeps_local_review(remote):
    client, state, archive, source, run_id = remote
    alias = archive.save('hyd', 'renamed.txt', archive.original('hyd', source['source_id']))
    alias = archive.get('hyd', alias['source_id'])
    assert client.start('hyd', alias)['instance'] == run_id
    result = client.result('hyd', alias, run_id, 'current-local-head')
    preview = result['preview']
    assert preview['previous_batch'] == 'current-local-head' and 'reviewed' not in preview
    assert preview['source_id'] == alias['source_id'] and preview['filename'] == 'renamed.txt'
    assert preview['procedures'][0]['anchor']['source_id'] == alias['source_id']
    assert client.history('hyd', alias, 50, 0)['items'][0]['status'] == 'DONE'
    state['allowed'] = False
    with pytest.raises(HTTPException): client.result('hyd', alias, run_id, None)
    with pytest.raises(HTTPException): client.history('hyd', alias, 50, 0)


@pytest.mark.parametrize('tamper', ['fingerprint', 'anchor', 'validation'])
def test_remote_unverified_or_wrong_source_results_are_rejected(remote, tamper):
    client, state, _, source, run_id = remote
    client.start('hyd', source)
    if tamper == 'fingerprint': state['value']['source_fingerprint'] = 'wrong'
    if tamper == 'anchor': state['value']['preview']['procedures'][0]['anchor']['quote'] = 'invented'
    if tamper == 'validation': state['value']['cache']['validated'] = False
    with pytest.raises(ValueError): client.result('hyd', source, run_id, None)


def test_local_history_cannot_authorize_another_source_or_tenant(remote):
    client, _, _, source, run_id = remote
    client.start('hyd', source)
    with pytest.raises(KeyError): client.result('other', source, run_id, None)
    other = deepcopy(source); other['source_id'] = 'another-source'
    with pytest.raises(KeyError): client.result('hyd', other, run_id, None)


def test_portal_rejects_unapproved_upload_and_never_falls_back_on_remote_failure(remote, monkeypatch):
    client, state, archive, source, _ = remote
    app = FastAPI()
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=lambda: None,
        tenant='hyd', audit=lambda *a: None, runtime_factory=lambda: pytest.fail('local AI fallback'), managed_client=client)
    portal = TestClient(app)
    state['allowed'] = False
    before = archive.list('hyd')['total']
    assert portal.post('/api/kg/manuals/preview', json=dict(filename='not-approved.txt',
        data=base64.b64encode(b'not approved').decode())).status_code == 403
    assert archive.list('hyd')['total'] == before
    state['allowed'], state['fail'] = True, True
    response = portal.post('/api/kg/manuals/sources/'+source['source_id']+'/extractions', json={'request_id':str(uuid4())})
    assert response.status_code == 502 and 'private upstream detail' not in response.text


def test_student_feedback_cannot_create_new_paid_extraction_conditions(remote):
    client, state, _, source, _ = remote
    with pytest.raises(HTTPException): client.start('hyd', source, {'instruction':'override'})
    assert not state['requests']
