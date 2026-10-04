"""Real Neo4j definitions into the generic engine, with explicitly synthetic observations.

No operational Kafka topics, PLC commands, or process instances are produced.
Only nodes carrying this probe's unpredictable fixture identifier are removed.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/detector'),str(ROOT/'common')]
from neo4j import GraphDatabase
from det.patterns import DefinitionError, compile_catalog
from det.pattern_source import read_patterns
from det.pattern_runtime import PatternRuntime


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    checks={};evidence={};fixture='a056-'+str(uuid.uuid4());code='A056_CHANGED_PATTERN'
    def save():
        (out/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
        (out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks[name]=bool(ok);print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok:raise AssertionError(name)
    with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=('neo4j','hydpass123'),connection_timeout=5) as driver:
        with driver.session() as s:
            before=read_patterns(driver);evidence['source_before']=before
            check('three_existing_patterns_compile',{'COOLER_DEGRADATION','PUMP_LEAKAGE','FAN_VIBRATION'} <= set(compile_catalog(before)))
            try:
                s.run("""CREATE (p:AnomalyPattern {id:$id, code:$code, name:'isolated definition probe',
                    fixture:$id,detectorScope:$id,detectionMode:'held',severity:'HIGH',rule:'human-readable probe summary',
                    holdSeconds:60,clearRule:'VS1 < 1.1',clearHoldSeconds:40,slopeWindowSeconds:60})
                    CREATE (v:InputData {id:$id+'-v',variable:'vs1',fixture:$id})
                    CREATE (s:InputData {id:$id+'-s',variable:'vs1_slope',fixture:$id})
                    CREATE (p)-[:TESTS {operator:'>',value:1.2}]->(v)
                    CREATE (p)-[:TESTS {operator:'>',value:0}]->(s)""",id=fixture,code=code).consume()
                def source():return read_patterns(driver)+read_patterns(driver,scope=fixture)
                rows=source();engine=PatternRuntime(rows);evidence['initial_catalog']=engine.describe()['catalog']
                events=[]
                def frame(t,value,quality='good'):
                    events.extend(engine.observe(fixture,'VS1',value,t,quality))
                    events.extend(engine.observe(fixture,'TS1',48,t))
                def own():return [event for event in events if event['pattern']==code]
                for t in range(5):frame(t,1.25+t*.01)
                check('new_code_raises_from_actual_graph_tests',len(own())==1 and own()[0]['state']=='RAISE')
                first=deepcopy(own()[0]);old_revision=first['evidence']['definition']['revision']
                s.run("""MATCH (p:AnomalyPattern {id:$id})-[t:TESTS]->(i:InputData {variable:'vs1'})
                    SET p.holdSeconds=100,p.clearRule='VS1 < .7',t.value=1.4""",id=fixture).consume()
                changed=source();engine.replace(changed)
                check('graph_threshold_and_hold_loaded',engine.catalog[code].hold==100 and engine.catalog[code].revision!=old_revision)
                for t in range(5,10):frame(t,.9)
                check('raised_alert_clears_with_pinned_prior_definition',len(own())==2 and own()[1]['state']=='CLEAR'
                      and own()[1]['alertId']==first['alertId'] and own()[1]['evidence']['definition']['revision']==old_revision)
                for t in range(10,17):frame(t,1.25+(t-10)*.01)
                check('changed_threshold_prevents_old_match',len(own())==2)
                for t in range(17,22):frame(t,1.45+(t-17)*.01)
                check('changed_hold_waits_full_duration',len(own())==2)
                frame(22,1.51)
                check('changed_hold_then_raises',len(own())==3 and own()[-1]['state']=='RAISE')
                applied=engine.catalog[code].revision
                s.run("""MATCH (p:AnomalyPattern {id:$id})-[t:TESTS]->(i:InputData {variable:'vs1'})
                    SET t.operator='unsupported'""",id=fixture).consume()
                try:engine.replace(source())
                except DefinitionError as exc:evidence['rejected_update']=str(exc)
                else:raise AssertionError('invalid source accepted')
                check('invalid_source_rejected_atomically',engine.catalog[code].revision==applied)
                frame(23,None,'bad')
                for t in range(24,30):events.extend(engine.observe(fixture,'TS1',48,t))
                check('unknown_samples_do_not_clear',len(own())==3 and engine.describe()['assets'][fixture][code]['quality']['status']=='UNKNOWN')
                s.run("""MATCH (p:AnomalyPattern {id:$id})-[t:TESTS]->(i:InputData {variable:'vs1'})
                    SET t.operator='>'""",id=fixture).consume()
                engine.replace(source())
                for t in range(30,37):frame(t,.6)
                check('fresh_recovery_clears_same_alert',len(own())==4 and own()[-1]['state']=='CLEAR'
                      and own()[-1]['alertId']==own()[-2]['alertId'])
                evidence.update(fixture=fixture,observations='synthetic seconds and values, no Kafka publication',
                                events=events,final=engine.describe())
            finally:
                removed=s.run('MATCH (n {fixture:$id}) WITH collect(n) AS ns FOREACH (n IN ns | DETACH DELETE n) RETURN size(ns) AS removed',id=fixture).single()['removed']
                evidence['fixture_nodes_removed']=removed
                check('only_three_owned_fixture_nodes_removed',removed==3)
                after=read_patterns(driver);evidence['source_after']=after
                check('original_source_catalog_unchanged',after==before)
                save()
    print(f'{sum(checks.values())}/{len(checks)} passed')


if __name__=='__main__':main()
