"""Immutable definition publishing and old-instance execution on real Postgres."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'it/process'), str(ROOT / 'it/agent-worker'), str(ROOT / 'common')]
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from procsvc import engine, instances, procdb
from worker.context import prepare, activity_capabilities

DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def main():
    schema = 'reaudit_versions_' + uuid.uuid4().hex[:12]
    report = {'schema': schema, 'checks': {}}
    target = ROOT / '.evidence/reaudit/definition-versions-postgres.json'

    def check(name, passed, detail=None):
        report['checks'][name] = {'passed': bool(passed), 'detail': detail}
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'PASS' if passed else 'FAIL', flush=True)
        assert passed, name

    try:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            for table in ('proc_def', 'proc_def_version', 'proc_def_deployment', 'bpm_proc_inst', 'todolist', 'events', 'form_def', 'users', 'tenants'):
                c.execute(sql.SQL('CREATE TABLE {}.{} (LIKE public.{} INCLUDING ALL)').format(
                    sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)))
            c.execute(sql.SQL('CREATE UNIQUE INDEX ux_probe_versions ON {}.proc_def_version '
                             "(tenant_id,proc_def_id,version) WHERE version_tag='hyd-immutable'").format(sql.Identifier(schema)))
        repo = procdb.PgRepo(make_conninfo(DSN, options=f'-c search_path={schema},public'))
        v1 = engine.Definition.load(ROOT / 'it/process/definitions/anomaly_response.json').raw
        v1['activities'][0]['agentConfig'] = {'model': 'old-model'}
        rt1 = instances.InstanceRuntime(repo, engine.Definition.from_dict(v1), instances.Hooks())
        old = rt1.on_alert_raise({'alertId': 'old-event', 'asset': 'AUDIT'})
        wi = next(w for w in repo.list_workitems(proc_inst_id=old['proc_inst_id']) if w['status'] == 'IN_PROGRESS')
        v2 = deepcopy(v1); v2['version'] = '2.0'; v2['ontologyRef'] = 'proc:changed'
        v2['activities'][0]['agentConfig'] = {'model': 'new-model'}
        projected = []
        rt2 = instances.InstanceRuntime(repo, engine.Definition.from_dict(v2),
            instances.Hooks(record_cypher=lambda q, **p: projected.append(p)))
        check('old_version_stored_separately', repo.get_proc_def(rt1.defn.id, version='1.0')['definition'] == v1)
        out = rt2.submit(wi['id'], {'cause': 'c', 'failure_mode': 'f', 'guide_card': {}})
        check('old_instance_uses_original_version', out['workitem']['status'] == 'DONE' and projected[-1]['process'] == v1['ontologyRef'])
        check('old_worker_uses_original_capabilities', activity_capabilities(prepare(repo, wi, 'hyd').definition,
                                                                          wi['activity_id'])['agent_config']['model'] == 'old-model')
        new = rt2.on_alert_raise({'alertId': 'new-event', 'asset': 'AUDIT'})
        check('new_instance_uses_new_version', new['proc_def_version'] == '2.0' and projected[-1]['process'] == v2['ontologyRef'])
        invalid = deepcopy(v1); invalid['description'] = 'overwrite'
        try:
            repo.upsert_proc_def(invalid)
        except ValueError:
            check('changed_version_rejected_without_head_change', repo.get_proc_def(rt1.defn.id)['definition'] == v2)
        else:
            check('changed_version_rejected_without_head_change', False)
        check('missing_exact_version_returns_none', repo.get_proc_def(rt1.defn.id, version='unknown') is None)

        def publish(n):
            raw = deepcopy(v2); raw['version'] = '3.0'; raw['description'] = 'candidate-'+str(n % 2)
            try:
                repo.upsert_proc_def(raw)
                return {'accepted': True, 'description': raw['description']}
            except ValueError:
                return {'accepted': False, 'description': raw['description']}
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(publish, range(16)))
        accepted = {r['description'] for r in results if r['accepted']}
        current = repo.get_proc_def(rt1.defn.id)['definition']
        check('concurrent_publish_has_one_content_winner', len(accepted) == 1 and current['description'] in accepted
              and repo.get_proc_def(rt1.defn.id, version='3.0')['definition'] == current, results)
        rt_other = instances.InstanceRuntime(repo, engine.Definition.from_dict(dict(v1, processDefinitionId='other-definition')),
                                            instances.Hooks())
        other = rt_other.on_alert_raise({'alertId': 'other-event', 'asset': 'AUDIT'})
        other_wi = next(w for w in repo.list_workitems(proc_inst_id=other['proc_inst_id']) if w['status'] == 'IN_PROGRESS')
        check('one_runtime_handles_other_definition_by_instance',
              rt2.submit(other_wi['id'], {'cause': 'c', 'failure_mode': 'f', 'guide_card': {}})['workitem']['status'] == 'DONE')
    finally:
        assert schema.startswith('reaudit_versions_') and len(schema) == 29
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        report['temporary_schema_removed'] = True
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
