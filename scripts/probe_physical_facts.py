"""Actual PG -> ingested Neo4j -> deployed DMN MCP -> agent approval check.

Unique owned fixture and rule; no Codex, decision submission or PLC command.
"""
import argparse
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
import uuid

import psycopg
from psycopg import sql
from neo4j import GraphDatabase


def http(port, path, body=None, method=None):
    req = urllib.request.Request(f'http://127.0.0.1:{port}'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True)
    out = Path(parser.parse_args().out); out.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex[:10]
    table, column, rule = 'A068 order '+token, 'due "hours"', 'rule:a068:'+token
    report = dict(scope='actual PG/HTTP/Neo4j/MCP/approval check; no Codex or PLC', checks={})
    args = dict(asset='HYD-01', pattern='COOLER_DEGRADATION', cause='cause:cooler-fin-fouling', failure_mode='fm:cooling-loss')
    def check(name, value):
        report['checks'][name] = bool(value)
        print(('PASS ' if value else 'FAIL ')+name, flush=True)
        save()
    def save():
        (out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def mcp(name, params):
        code = '''import asyncio,json
from fastmcp import Client
async def main():
 async with Client('http://127.0.0.1:8198/mcp',timeout=40) as client:
  result=await client.call_tool(NAME,PARAMS)
  print(next(x.text for x in result.content if getattr(x,'type',None)=='text'))
asyncio.run(main())
'''.replace('NAME', repr(name)).replace('PARAMS', repr(params))
        proc = subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-'],
            input=code, text=True, encoding='utf8', capture_output=True, timeout=55)
        if proc.returncode: raise RuntimeError(proc.stderr)
        result = json.loads(proc.stdout)
        if result.get('result') != 'ok': raise RuntimeError(str(result))
        return result['document']
    env = dict(x.split('=',1) for x in json.loads(subprocess.check_output(
        ['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    batch = None
    item = None
    with GraphDatabase.driver('bolt://127.0.0.1:7687', auth=tuple(env['NEO4J_AUTH'].split('/',1))) as graph, \
            psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres', autocommit=True) as db:
        def cypher(query, **params):
            with graph.session() as session: return session.run(query, **params).data()
        def set_value(value):
            db.execute(sql.SQL('update {} set {}=%s').format(sql.Identifier('ent',table), sql.Identifier(column)), (value,))
        try:
            ddl = sql.SQL('create table {} (asset text, {} numeric(10,3))').format(sql.Identifier('ent',table), sql.Identifier(column)).as_string()
            db.execute(ddl)
            db.execute(sql.SQL('grant select on {} to hyd_enterprise_reader').format(sql.Identifier('ent',table)))
            db.execute(sql.SQL('insert into {} values (%s,%s)').format(sql.Identifier('ent',table)), ('HYD-01',2.125))
            plan = http(8080,'/api/kg/ddl/preview',dict(text=ddl,filename='actual-a068.sql',
                selection={'ent.'+sql.Identifier(table).as_string():[column]}, systems={'ent.'+sql.Identifier(table).as_string():'sys:mes'}))
            batch = plan['batch']; report['plan'] = plan; save()
            http(8080,'/api/kg/ddl/commit',plan)
            item = plan['inputs'][0]; var = item['variable']; iid = item['id']
            created = cypher('MATCH (t:DecisionTable {id:"dt:compliance"}), (i:InputData {id:$iid}), (s:Skill {id:"skill:fan-max"}), '
                '(k:ManualSection {id:"HM-7.3"}) CREATE (r:Rule {id:$rule, effect:"EXCLUDE", order:990, '
                'annotation:"A068 owned source fixture", when:"physical value < 1"}) '
                'CREATE (t)-[:HAS_RULE]->(r), (r)-[:TESTS {operator:"<",value:1}]->(i), '
                '(r)-[:APPLIES_TO]->(s), (r)-[:DERIVED_FROM]->(k) RETURN r.id', iid=iid, rule=rule)
            if len(created) != 1:
                raise RuntimeError('owned fixture rule was not created')
            projection = next(i for i in mcp('inputs',{}) if i['id']==iid)
            check('MCP_inputs_preserve_physical_binding',all(projection[k]==item[k] for k in ('datasource','catalog','schema','table','column','assetColumn','sqlType')))
            facts = mcp('gather_facts',args); report['initial_facts'] = facts
            check('MCP_reads_exact_decimal_from_quoted_column',facts['facts'][var]=='2.125')
            rec = mcp('evaluate_cards',args); report['evaluation'] = rec
            check('new_physical_rule_is_evaluated',any(r['rule']==rule and r['fired'] is False and not r['unknown'] for r in rec['result']['trace']))
            decision = dict(rec, options=rec['result']['options'])
            def assess(name):
                result = http(8091,'/api/agent/approval-check',dict(decision=decision,option='skill:fan-max',role='role:prod-mgr'))
                report[name] = result; save(); return result
            baseline = assess('baseline')
            check('unchanged_current_source_allows_approval_check',baseline['allowed'])
            set_value(2.250)
            changed = assess('value_changed')
            check('changed_business_value_requires_new_review',not changed['allowed'] and any(var in r for r in changed['reasons']))
            set_value(2.125)
            cypher('MATCH (i:InputData {id:$iid}) SET i.name="changed source meaning"',iid=iid)
            changed = assess('meaning_changed')
            check('equal_value_with_changed_meaning_requires_review',not changed['allowed'] and any('물리 출처' in r for r in changed['reasons']))
            cypher('MATCH (i:InputData {id:$iid}) SET i.name=$name',iid=iid,name=item['name'])
            set_value(0.5)
            changed = assess('threshold_crossed')
            check('actual_source_threshold_excludes_selected_card',any(v['rule']==rule for v in changed['current_option']['violations']))
            db.execute(sql.SQL('insert into {} values (%s,%s)').format(sql.Identifier('ent',table)),('HYD-01',2.125))
            duplicate = mcp('gather_facts',args)
            check('multiple_asset_rows_are_unknown',duplicate['facts'][var] is None and any(p['variable']==var and 'row count' in p.get('error','') for p in duplicate['provenance']))
            changed = assess('ambiguous_rows')
            check('ambiguous_source_cannot_authorize',not changed['allowed'] and any(var in r['variables'] for r in changed['unknown']))
            db.execute(sql.SQL('delete from {}').format(sql.Identifier('ent',table)))
            missing = mcp('gather_facts',args)
            check('missing_asset_row_is_unknown',missing['facts'][var] is None)
            db.execute(sql.SQL('insert into {} values (%s,NULL)').format(sql.Identifier('ent',table)),('HYD-01',))
            check('null_source_is_unknown',mcp('gather_facts',args)['facts'][var] is None)
            set_value(2.125)
            db.execute(sql.SQL('alter table {} alter column {} type text using {}::text').format(
                sql.Identifier('ent',table), sql.Identifier(column), sql.Identifier(column)))
            drift = mcp('gather_facts',args)
            check('source_type_drift_is_unknown_without_coercion',drift['facts'][var] is None and
                any(p['variable']==var and 'typeRef' in p.get('error','') for p in drift['provenance']))
            db.execute(sql.SQL('alter table {} alter column {} type numeric(10,3) using {}::numeric').format(
                sql.Identifier('ent',table), sql.Identifier(column), sql.Identifier(column)))
            cypher('MATCH (i:InputData {id:$iid}) SET i.catalog="wrong-database"',iid=iid)
            wrong = mcp('gather_facts',args)
            check('catalog_mismatch_does_not_read_other_database',wrong['facts'][var] is None)
            cypher('MATCH (i:InputData {id:$iid}) SET i.catalog=$catalog',iid=iid,catalog=item['catalog'])
            cypher('MATCH (i:InputData {id:$iid}) REMOVE i.assetColumn',iid=iid)
            check('missing_asset_binding_is_not_guessed',mcp('gather_facts',args)['facts'][var] is None)
        finally:
            cypher('MATCH (r:Rule {id:$rule}) DETACH DELETE r',rule=rule)
            if item:
                cypher('MATCH (i:InputData {id:$iid}) SET i.name=$name, i.catalog=$catalog, i.assetColumn=$assetColumn',
                    iid=item['id'], name=item['name'], catalog=item['catalog'], assetColumn=item['assetColumn'])
            if batch:
                http(8080,'/api/kg/ingests/'+urllib.parse.quote(batch,safe=''),method='DELETE')
            db.execute(sql.SQL('drop table if exists {}').format(sql.Identifier('ent',table)))
            report['fixture_cleanup'] = True; save()
    return 0 if report['checks'] and all(report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
