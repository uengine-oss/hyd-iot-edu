"""K1/G6: durable grouping of student configuration on an independent laptop.

No owner or authentication semantics. Reuse the existing bundle and its secret
redaction; selection closes over referenced student assets before export.
"""
from __future__ import annotations

from copy import deepcopy
import unicodedata

KINDS = {'flows': '흐름', 'agents': '에이전트', 'skills': '스킬', 'mcp_servers': '도구 서버'}
KEYS = {'flows': 'definition_id', 'agents': 'id', 'skills': 'skill_name', 'mcp_servers': 'name'}


class Store:
    def __init__(self, repo, tenant):
        self.repo, self.tenant = repo, tenant

    def rows(self):
        if hasattr(self.repo, '_conn'):
            with self.repo._conn() as c:
                return [dict(r) for r in c.execute('select kind, asset_id, label from hyd_student_case_tags where tenant_id=%s order by kind, asset_id', (self.tenant,)).fetchall()]
        return [dict(kind=k, asset_id=a, label=v) for (t, k, a), v in sorted(getattr(self.repo, '_student_cases', {}).items()) if t == self.tenant]

    def set(self, kind, asset_id, label):
        if hasattr(self.repo, '_conn'):
            with self.repo._conn() as c:
                if label:
                    c.execute('insert into hyd_student_case_tags(tenant_id,kind,asset_id,label) values (%s,%s,%s,%s) on conflict(tenant_id,kind,asset_id) do update set label=excluded.label', (self.tenant, kind, asset_id, label))
                else:
                    c.execute('delete from hyd_student_case_tags where tenant_id=%s and kind=%s and asset_id=%s', (self.tenant, kind, asset_id))
        else:
            with self.repo._lock:
                if not hasattr(self.repo, '_student_cases'): self.repo._student_cases = {}
                key = (self.tenant, kind, asset_id)
                if label: self.repo._student_cases[key] = label
                else: self.repo._student_cases.pop(key, None)

    def remove(self, kind, asset_id=None):
        if hasattr(self.repo, '_conn'):
            with self.repo._conn() as c:
                c.execute('delete from hyd_student_case_tags where tenant_id=%s and kind=%s and (%s::text is null or asset_id=%s)', (self.tenant, kind, asset_id, asset_id))
        else:
            with self.repo._lock:
                rows = getattr(self.repo, '_student_cases', {})
                for key in list(rows):
                    if key[0] == self.tenant and key[1] == kind and (asset_id is None or key[2] == asset_id): del rows[key]

    def replace(self, rows):
        # One transaction: a failed import must not leave half the labels behind.
        if hasattr(self.repo, '_conn'):
            with self.repo._conn() as c, c.transaction():
                c.execute('delete from hyd_student_case_tags where tenant_id=%s', (self.tenant,))
                for r in rows:
                    c.execute('insert into hyd_student_case_tags(tenant_id,kind,asset_id,label) values (%s,%s,%s,%s)', (self.tenant, r['kind'], r['asset_id'], r['label']))
        else:
            with self.repo._lock:
                old = getattr(self.repo, '_student_cases', {})
                self.repo._student_cases = {k:v for k,v in old.items() if k[0] != self.tenant} | {(self.tenant,r['kind'],r['asset_id']):r['label'] for r in rows}


def assets(content):
    return {(kind, row[KEYS[kind]]): row for kind in KINDS for row in content.get(kind, [])}


def clean_label(value, *, allow_empty=False):
    from .config_bundle import BundleError
    if not isinstance(value, str): raise BundleError(422, '사례 이름은 글자로 적으세요')
    label = unicodedata.normalize('NFC', value.strip())
    if (not label and not allow_empty) or len(label) > 60 or any(unicodedata.category(c).startswith('C') for c in value):
        raise BundleError(422, '사례 이름은 제어 문자 없이 1~60자로 적으세요')
    return label


def validate_tags(rows, content):
    from .config_bundle import BundleError
    if not isinstance(rows, list): raise BundleError(422, '사례 꼬리표는 목록이어야 합니다')
    known, seen, out = assets(content), set(), []
    for row in rows:
        if not isinstance(row, dict): raise BundleError(422, '사례 꼬리표 항목이 올바르지 않습니다')
        key = (row.get('kind'), row.get('asset_id'))
        if not all(isinstance(v, str) for v in key) or key not in known or key in seen:
            raise BundleError(422, '사례 꼬리표의 자산이 없거나 중복되었습니다')
        seen.add(key)
        out.append(dict(kind=key[0], asset_id=key[1], label=clean_label(row.get('label'))))
    return sorted(out, key=lambda r: (r['kind'], r['asset_id']))


def live_tags(rt, content):
    known = assets(content)
    store = Store(rt.repo, rt.tenant_id)
    rows = store.rows()
    for row in rows:
        if (row['kind'],row['asset_id']) not in known:
            # An unreadable server is deliberately absent from a bundle, but
            # editing its configuration must not erase its existing label.
            if row['kind'] == 'mcp_servers':
                from .mcp_registry import store_for
                if row['asset_id'] in store_for(rt.repo).servers(rt.tenant_id): continue
            store.set(row['kind'],row['asset_id'], '')
    return [r for r in rows if (r['kind'],r['asset_id']) in known]


def catalog(bundle):
    tags = {(r['kind'],r['asset_id']):r['label'] for r in bundle.get('case_tags', [])}
    rows = []
    for (kind, aid), row in assets(bundle['content']).items():
        if kind == 'flows':
            mapping = (row.get('draft') or {}).get('mapping') or next((v.get('mapping') for v in reversed(row.get('versions', [])) if v.get('mapping')), {})
            name = mapping.get('name') or '이름 없는 가져온 흐름'
        else: name = row.get('description') if kind in ('skills','mcp_servers') else row.get('name')
        rows.append({'kind':kind,'asset_id':aid,'kind_name':KINDS[kind], 'name':name or ('이름 없는 '+KINDS[kind]), 'label':tags.get((kind,aid),'')})
    return {'assets':rows, 'labels':sorted(set(tags.values()))}


def declared_refs(task, *, mapping=False):
    """Only schema fields may create edges. Prose, ids and tool arguments cannot."""
    from .agents_store import csv_list
    refs = set()
    if isinstance(task.get('agent'), str): refs.add(('agents',task['agent']))
    for name in csv_list(task.get('skills')): refs.add(('skills',name))
    for name in csv_list(task.get('tools')):
        server = name.split('__')[1] if name.startswith('mcp__') and len(name.split('__')) >= 3 else name
        refs.add(('mcp_servers',server))
    config = task.get('config' if mapping else 'service')
    if isinstance(config,dict) and isinstance(config.get('server'),str):
        refs.add(('mcp_servers',config['server']))
    if isinstance(config,dict) and isinstance(config.get('mail'),dict) and isinstance(config['mail'].get('server'),str):
        refs.add(('mcp_servers',config['mail']['server']))
    return refs


def select_bundle(rt, bundle, label):
    from .config_bundle import BundleError
    label = clean_label(label)
    out = deepcopy(bundle)
    content, known = out['content'], assets(out['content'])
    chosen = {(r['kind'],r['asset_id']) for r in out.get('case_tags',[]) if r['label'] == label}
    if not chosen: raise BundleError(404, '이 사례에 묶인 구성이 없습니다')
    direct = set(chosen)
    # Follow declared references only. Descriptions and instructions are not
    # dependency edges even if their complete text happens to equal an asset id.
    while True:
        before = set(chosen)
        for key in list(chosen):
            row = known[key]
            refs = set()
            if key[0] == 'flows':
                refs.update(('agents',m['agent_id']) for m in content['assignments'] if m['definition_id'] == key[1])
                for source in [row.get('draft') or {}, *row.get('versions',[])]:
                    for task in (source.get('mapping') or {}).get('tasks',{}).values():
                        if isinstance(task,dict): refs.update(declared_refs(task,mapping=True))
                for version in row.get('versions',[]):
                    raw = (rt.repo.get_proc_def(key[1],rt.tenant_id,version=version['version']) or {}).get('definition') or {}
                    for task in raw.get('activities',[]): refs.update(declared_refs(task))
            elif key[0] == 'agents':
                refs.update(declared_refs(row))
            chosen.update(refs & known.keys())
            if key[0] == 'agents' and not row.get('tools'):
                chosen.update(k for k in known if k[0] == 'mcp_servers')
        if chosen == before: break
    for kind in KINDS: content[kind] = [r for r in content[kind] if (kind,r[KEYS[kind]]) in chosen]
    flow_ids = {aid for k,aid in chosen if k == 'flows'}
    content['assignments'] = [r for r in content['assignments'] if r['definition_id'] in flow_ids]
    content['deployments']['flows'] = [r for r in content['deployments']['flows'] if r['definition_id'] in flow_ids]
    content['deployments']['reference'] = None
    roles = set()
    for flow in content['flows']:
        for version in flow['versions']:
            raw = (rt.repo.get_proc_def(flow['definition_id'], rt.tenant_id, version=version['version']) or {}).get('definition') or {}
            roles.update(r.get('endpoint') for r in raw.get('roles',[]))
    content['role_members'] = [r for r in content['role_members'] if r['role_id'] in roles]
    out['case_tags'] = [r for r in out.get('case_tags',[]) if (r['kind'],r['asset_id']) in chosen]
    out['case_selection'] = {'label':label, 'direct_count':len(direct), 'dependency_count':len(chosen-direct),
                             'dependencies':[{'kind_name':KINDS[k], 'name':next(a['name'] for a in catalog(bundle)['assets'] if a['kind']==k and a['asset_id']==aid)} for k,aid in sorted(chosen-direct)]}
    out['summary'] = {k:len(content[k]) for k in ('mcp_servers','skills','agents','role_members','flows','assignments')}
    out['summary'].update(flow_versions=sum(len(f['versions']) for f in content['flows']), deployments=len(content['deployments']['flows']), secrets_needed=sum(len(s['secrets']) for s in content['mcp_servers']))
    return out


def register(app, runtime, base_loader, run):
    from . import config_bundle as B

    @app.get('/api/config/cases')
    async def get_cases():
        return await run(lambda: catalog(B.export_bundle(runtime(), base_loader)))

    @app.put('/api/config/cases/tag')
    async def put_tag(body: dict):
        def save():
            rt = runtime()
            kind, aid = body.get('kind'), body.get('asset_id')
            if not isinstance(kind,str) or not isinstance(aid,str): raise B.BundleError(422, '꼬리표를 붙일 구성을 고르세요')
            label = clean_label(body.get('label'), allow_empty=True)
            if not B._LOCK.acquire(blocking=False): raise B.BundleError(409, '다른 구성 작업이 진행 중입니다. 끝난 뒤 다시 저장하세요')
            try:
                bundle = B.export_bundle(rt, base_loader)
                if (kind,aid) not in assets(bundle['content']): raise B.BundleError(404, '학생이 만든 구성을 찾지 못했습니다. 목록을 다시 읽으세요')
                Store(rt.repo, rt.tenant_id).set(kind,aid,label)
                return {'ok':True, 'label':label}
            finally: B._LOCK.release()
        return await run(save)
