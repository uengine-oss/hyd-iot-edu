"""HTTP ownership contract on the deployed process service."""
import copy
import json
from pathlib import Path
import urllib.parse
import uuid
from probe_ingest_identity import api


def main():
    ds = 'http_' + uuid.uuid4().hex[:12]
    report = {'datasource': ds, 'checks': {}}
    path = Path('.evidence/reaudit/ingest-ownership-http.json')
    batches = []

    def check(name, passed, detail):
        report['checks'][name] = {'passed': bool(passed), 'detail': detail}
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'PASS' if passed else 'FAIL', flush=True)
        assert passed, name

    def clear(batch):
        return api('/api/kg/ingests/' + urllib.parse.quote(batch, safe=''), method='DELETE')

    try:
        request = {'filename': 'http.sql', 'text': 'CREATE TABLE public.readings (asset text, value numeric);', 'datasource': ds}
        status, error = api('/api/kg/ddl/preview', dict(request, datasource=''))
        check('blank_source_rejected', status == 400, error)
        status, p = api('/api/kg/ddl/preview', request)
        check('preview', status == 200, p)
        batches.append(p['batch'])
        status, result = api('/api/kg/ddl/commit', p)
        check('commit', status == 200 and not result['replayed'], result)
        status, result = api('/api/kg/ddl/commit', p)
        check('replay', status == 200 and result['replayed'], result)
        changed = copy.deepcopy(p); changed['inputs'][0]['name'] = 'different'
        status, result = api('/api/kg/ddl/commit', changed)
        check('changed_content_returns_409', status == 409, result)
        status, p2 = api('/api/kg/ddl/preview', dict(request, filename='renamed.sql'))
        assert status == 200
        batches.append(p2['batch'])
        status, result = api('/api/kg/ddl/commit', p2)
        check('second_batch', status == 200, result)
        status, listing = api('/api/kg/ingests')
        check('both_batches_visible', status == 200 and set(batches) <= {r['batch'] for r in listing},
              [r for r in listing if r['batch'] in batches])
        status, result = clear(p['batch'])
        check('earlier_clear_retains_shared_nodes', status == 200 and result['deleted'] == 0 and result['retained'] == 3, result)
        status, result = clear(p2['batch'])
        check('last_clear_removes_generated_nodes', status == 200 and result['deleted'] == 3, result)
        status, result = api('/api/kg/ddl/commit', p2)
        check('cleared_batch_returns_409', status == 409, result)
        status, result = clear(p2['batch'])
        check('clear_replay', status == 200 and result['replayed'], result)
        status, result = clear('not-found-' + ds)
        check('missing_batch_returns_404', status == 404, result)
    finally:
        report['cleanup'] = [clear(b) for b in batches]
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
