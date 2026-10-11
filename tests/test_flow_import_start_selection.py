"""Portal's explicit empty selection is opt-in; legacy API defaults remain intact."""
from test_bpmn_import import api, REDRAW, BASE, HUMAN_START


def test_import_default_empty_explicit_and_reimport_preservation(api):
    client, _, _, _ = api
    body = {'xml': REDRAW, 'file_name': 'flow.bpmn'}
    default = client.post('/api/flows/import', json=dict(body, definition_id='legacy')).json()
    assert default['mapping']['start']['patterns'] == list(BASE['alertPolicy']['patterns'])
    empty = client.post('/api/flows/import', json=dict(body, definition_id='empty', start_patterns=[])).json()
    assert empty['mapping']['start'] == {'kind': 'alert', 'patterns': []}
    assert any(p['field']=='start.patterns' for p in empty['check']['problems'])
    explicit = client.post('/api/flows/import', json=dict(body, definition_id='selected', start_patterns=['PM_DUE'])).json()
    assert explicit['mapping']['start']['patterns'] == ['PM_DUE']
    assert not any(p['field']=='start.patterns' for p in explicit['check']['problems'])
    for did, requested, expected in [('legacy', [], list(BASE['alertPolicy']['patterns'])), ('selected', [], ['PM_DUE']), ('empty', ['PM_DUE'], [])]:
        reimport = client.post('/api/flows/import', json=dict(body, definition_id=did, start_patterns=requested)).json()
        assert reimport['reimport']['previous'] is True
        assert reimport['mapping']['start']['patterns'] == expected
        assert client.get('/api/flows/'+did).json()['mapping']['start']['patterns'] == expected


def test_import_override_does_not_change_human_start_and_unknown_pattern_is_checked(api):
    client, _, _, _ = api
    human = client.post('/api/flows/import', json={'xml': HUMAN_START, 'definition_id': 'human', 'start_patterns': []}).json()
    assert human['mapping']['start'] == {'kind': 'human', 'fields': []}
    unknown = client.post('/api/flows/import', json={'xml': REDRAW, 'definition_id': 'unknown', 'start_patterns': ['UNKNOWN']}).json()
    assert unknown['mapping']['start']['patterns'] == ['UNKNOWN']
    assert any(p['field']=='start.patterns' and 'UNKNOWN' in p['reason'] for p in unknown['check']['problems'])
    assert client.post('/api/flows/unknown/register', json={}).status_code == 400
