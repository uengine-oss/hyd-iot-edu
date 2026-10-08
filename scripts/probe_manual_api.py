"""Deployed process HTTP/manual archive/Neo4j checks, including process restart.

Only this run's reviewed fixture batches are rolled back. Original uploads and
receipts are retained as verification evidence, including rejected proposals.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import uuid

BASE = 'http://localhost:8080'


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if 'application/json' in r.headers.get('Content-Type', '') else raw
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def main():
    unique = uuid.uuid4().hex[:10].upper()
    dest = Path('.evidence/reaudit/manual-api-live') / unique
    dest.mkdir(parents=True)
    report = {'checks': [], 'fixture': unique}
    batches = []
    saved = {}

    def check(name, ok, detail=None):
        report['checks'].append(dict(name=name, passed=bool(ok), detail=detail))
        (dest / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        assert ok, name

    def upload(suffix, extra='벨트를 확인한다.', document_id=None):
        raw = f'HM-8.1 확인\nSOP-API-{unique}-{suffix} 확인 절차\n1. 설비를 정지한다.\n2. {extra}\n'.encode()
        status, result = request('/api/kg/manuals/preview', dict(filename='같은 이름.md', data=base64.b64encode(raw).decode(), document_id=document_id))
        assert status == 200, (status, result)
        saved[result['source_id']] = raw
        result.update(by='[회귀 검사] 매뉴얼 API 검사기', reviewed=True,
                      links={p['id']: {'failureMode': 'fm:bearing-degradation'} for p in result['procedures']})
        return result

    def commit(body):
        status, result = request('/api/kg/manuals/commit', body)
        if status == 200:
            batches.append(body['batch'])
        return status, result

    def undo(batch):
        return request('/api/kg/manuals/batches/' + batch + '/rollback', {'by': '[회귀 검사] 매뉴얼 API 검사기'})

    try:
        check('malformed base64 rejected', request('/api/kg/manuals/preview', {'filename': 'x.md', 'data': '!not-base64!'})[0] == 400)
        a = upload('A')
        (dest / 'preview-a.json').write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding='utf-8')
        check('preview persists source with anchors but does not commit', len(a['procedures']) == 1 and len(a['sections']) == 1 and
              not any(r['batch'] == a['batch'] for r in request('/api/kg/manuals')[1]), a['source_id'])
        raw = request('/api/kg/manuals/sources/' + a['source_id'] + '/original')[1]
        check('download bytes exactly match original upload', raw == saved[a['source_id']], hashlib.sha256(raw).hexdigest())
        source = request('/api/kg/manuals/sources/' + a['source_id'])[1]
        check('API returns complete source text and extractor', source['pages'][0]['text'] == saved[a['source_id']].decode() and bool(source['extractor']))
        no_review = dict(a, reviewed=False)
        check('unreviewed graph write rejected', commit(no_review)[0] == 400)
        forged = copy.deepcopy(a)
        forged['procedures'][0]['steps'][0]['anchor']['quote'] = '없는 원문'
        check('forged citation rejected before commit', commit(forged)[0] == 400)
        invalid = copy.deepcopy(a)
        invalid['links'][a['procedures'][0]['id']]['failureMode'] = 'fm:no-such-' + unique
        check('missing graph target returns conflict and no batch', commit(invalid)[0] == 409 and
              not any(r['batch'] == a['batch'] for r in request('/api/kg/manuals')[1]))
        status, first = commit(a)
        check('reviewed source graph commits through HTTP', status == 200 and first['steps'] == 2 and first['candidate_activation'] == 'NOT_CHANGED', first)
        check('repeat HTTP commit returns same receipt', commit(a)[1].get('replayed') is True)
        b = upload('B')
        check('same filename and section from another document accepted', commit(b)[0] == 200 and a['document_id'] != b['document_id'])
        rev = upload('A', extra='개정한 장력을 확인한다.', document_id=a['document_id'])
        check('revision preview carries expected previous batch', rev['previous_batch'] == a['batch'])
        stale = dict(rev, previous_batch=None)
        check('stale revision refused', commit(stale)[0] == 409)
        check('explicit reviewed revision commits', commit(rev)[0] == 200)
        rows = request('/api/kg/manuals')[1]
        check('history distinguishes current and superseded versions',
              next(r for r in rows if r['batch'] == a['batch'])['status'] == 'SUPERSEDED' and
              next(r for r in rows if r['batch'] == rev['batch'])['current'] is True)
        check('out-of-order rollback rejected by HTTP', undo(a['batch'])[0] == 409)
        pdf_raw = Path('tests/fixtures/manuals/two-page-manual.pdf').read_bytes()
        status, pdf = request('/api/kg/manuals/preview', dict(filename='two-page-source.pdf', data=base64.b64encode(pdf_raw).decode()))
        check('PDF pages retained without pretending unsupported text is an SOP', status == 200 and not pdf['procedures'] and
              len(request('/api/kg/manuals/sources/' + pdf['source_id'])[1]['pages']) == 2 and
              request('/api/kg/manuals/sources/' + pdf['source_id'] + '/original')[1] == pdf_raw)
        source_page = request('/api/kg/manuals/sources?limit=1')[1]
        check('source listing includes pagination and pending originals', source_page['total'] >= 4 and len(source_page['items']) == 1 and source_page['next_offset'] == 1)
        started = time.time()
        result = subprocess.run(['docker', 'compose', 'restart', 'process'], capture_output=True, text=True)
        (dest / 'restart.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0
        ready = False
        while time.time() - started < 60:
            try:
                if request('/healthz')[1].get('ok'):
                    ready = True
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        check('actual process restart recovered HTTP', ready)
        check('restart preserves original bytes and committed history', all(request('/api/kg/manuals/sources/' + key + '/original')[1] == value for key, value in saved.items()) and
              any(r['batch'] == rev['batch'] and r['current'] for r in request('/api/kg/manuals')[1]))
        status, reopened = request('/api/kg/manuals/sources/' + a['source_id'] + '/preview', {})
        check('archived older source can be re-reviewed against latest head', status == 200 and reopened['source_id'] == a['source_id'] and reopened['previous_batch'] == rev['batch'])
        check('latest rollback restores preceding current batch', undo(rev['batch'])[0] == 200 and
              any(r['batch'] == a['batch'] and r['current'] for r in request('/api/kg/manuals')[1]))
        (dest / 'history.json').write_text(json.dumps(request('/api/kg/manuals')[1], ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{len(report['checks'])}/{len(report['checks'])} PASS: {dest}", flush=True)
    finally:
        report['cleanup'] = []
        for batch in reversed(list(dict.fromkeys(batches))):
            report['cleanup'].append(dict(batch=batch, result=undo(batch)))
        (dest / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
