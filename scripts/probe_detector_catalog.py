"""Isolated real Neo4j/Kafka/HTTP detector process, including forced process restart."""
import argparse
import json
from pathlib import Path
import subprocess

CODE = r'''
import asyncio,json,os,subprocess,sys,time,uuid,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from aiokafka.admin import AIOKafkaAdminClient,NewTopic
from neo4j import GraphDatabase
from hydcommon import kafka

async def main():
 nonce='a057-'+uuid.uuid4().hex[:10];checks={};evidence={'scope':nonce,'synthetic_inputs':True};child=None
 names=[nonce+'.'+name for name in ('tag','wave','status','feat','alerts')]
 driver=GraphDatabase.driver('bolt://neo4j:7687',auth=('neo4j','hydpass123'))
 admin=AIOKafkaAdminClient(bootstrap_servers='redpanda:9092');await admin.start()
 try:await admin.create_topics([NewTopic(name,1,1,topic_configs={'retention.ms':'3600000'}) for name in names])
 finally:await admin.close()
 publisher=await kafka.producer();output=await kafka.consumer([names[-1]],group=nonce+'-output',from_latest=False)
 serverlog=open('/tmp/detector-probe.log','w')
 env=os.environ|dict(DETECTOR_TOPIC_PREFIX=nonce,DETECTOR_PATTERN_SCOPE=nonce,DETECTOR_STATE_PATH='/tmp/probe.sqlite3',TIME_SCALE='20')
 def check(name,value):
  checks[name]=bool(value)
  if not value:raise AssertionError(name)
 async def request(path,post=False):
  def run():
   req=urllib.request.Request('http://127.0.0.1:18992'+path,data=b'{}' if post else None,headers={'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=3) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
  return await asyncio.to_thread(run)
 async def wait_api():
  for _ in range(100):
   if child.poll() is not None:raise RuntimeError('detector child exited')
   try:return await request('/api/detector/patterns')
   except OSError:await asyncio.sleep(.1)
  raise RuntimeError('detector API unavailable')
 def start():return subprocess.Popen([sys.executable,'-m','uvicorn','det.main:app','--host','127.0.0.1','--port','18992'],env=env,stdout=serverlog,stderr=serverlog)
 async def reload():return await request('/api/detector/patterns/reload',True)
 async def wait_input():
  for _ in range(300):
   _,health=await request('/healthz')
   if health.get('kafka'):return
   if child.poll() is not None:raise RuntimeError('detector child exited during assignment')
   await asyncio.sleep(.1)
  raise RuntimeError('consumer assignment not ready')
 async def frame(value,asset='FIXTURE',delay=1.05):
  await asyncio.sleep(delay)
  before=(await request('/api/detector/state'))[1]['tags'];stamp=datetime.now(timezone.utc).isoformat()
  for tag,val in [('VS1',value),('TS1',48)]:
   await publisher.send_and_wait(names[0],key=asset,value=dict(asset=asset,name=tag,v=val,t=stamp,q='good'))
  for _ in range(100):
   data=(await request('/api/detector/state'))[1]
   if data['tags']>=before+2:return data
   await asyncio.sleep(.05)
  raise RuntimeError('Kafka input was not consumed')
 def update(query):
  with driver.session() as s:s.run(query,id=nonce).consume()
 alerts=[]
 async def read_alerts():
  rows=await output.getmany(timeout_ms=500)
  alerts.extend(record.value for batch in rows.values() for record in batch)
  return alerts
 try:
  child=start();await wait_api()
  status,health=await request('/healthz')
  check('missing_source_is_unhealthy_without_builtin_fallback',status==503 and not health['patterns']['ready'])
  update("""CREATE (p:AnomalyPattern {id:$id,code:'DYNAMIC_PROBE',name:'isolated',detectorScope:$id,fixture:$id,
   detectionMode:'held',severity:'HIGH',rule:'fixture prose',holdSeconds:60,clearRule:'VS1 < 1.1',
   clearHoldSeconds:40,slopeWindowSeconds:60})
   CREATE (i:InputData {id:$id+'-input',variable:'vs1',fixture:$id})
   CREATE (p)-[:TESTS {operator:'>',value:1.2}]->(i)""")
  status,loaded=await reload();check('actual_http_reload_reads_graph',status==200 and 'DYNAMIC_PROBE' in loaded['applied']['catalog'])
  # Resolve the consumer group's initial latest offset before publishing fixtures.
  await wait_input()
  await frame(1.3);await frame(1.3)
  update("MATCH (p:AnomalyPattern {id:$id})-[t:TESTS]->() SET p.holdSeconds=100,t.value=1.4")
  status,changed=await reload();check('changed_threshold_and_duration_applied',status==200 and changed['applied']['catalog']['DYNAMIC_PROBE']['holdSeconds']==100)
  for _ in range(3):await frame(1.3)
  check('old_threshold_does_not_raise_after_change',not await read_alerts())
  for _ in range(5):await frame(1.5)
  check('longer_hold_not_completed_early',not await read_alerts())
  await frame(1.5);await read_alerts()
  check('real_kafka_output_raises_new_definition',len(alerts)==1 and alerts[0]['state']=='RAISE')
  raised=alerts[0];revision=raised['evidence']['definition']['revision']
  update("MATCH (p:AnomalyPattern {id:$id}) SET p.clearRule='VS1 < .7'")
  status,changed=await reload();check('active_alert_pins_old_revision',status==200 and changed['applied']['assets']['FIXTURE']['DYNAMIC_PROBE']['revision']==revision and changed['applied']['catalog']['DYNAMIC_PROBE']['revision']!=revision)
  child.kill();child.wait(timeout=10);check('detector_process_really_killed',child.returncode!=0)
  update("MATCH (p:AnomalyPattern {id:$id})-[t:TESTS]->() SET t.operator='invalid'")
  child=start();await wait_api()
  status,loaded=await request('/api/detector/patterns')
  check('restart_retains_alert_id_and_definition',loaded['applied']['assets']['FIXTURE']['DYNAMIC_PROBE']['alert_id']==raised['alertId'] and loaded['applied']['assets']['FIXTURE']['DYNAMIC_PROBE']['revision']==revision)
  check('invalid_source_after_restart_is_exposed',not loaded['source']['ready'])
  # Restored running consumer uses committed offsets, and only fresh input may clear.
  await wait_input()
  for _ in range(4):await frame(.9)
  await read_alerts()
  check('fresh_input_clears_pinned_alert_while_new_source_rejected',len(alerts)==2 and alerts[1]['state']=='CLEAR' and alerts[1]['alertId']==raised['alertId'] and alerts[1]['evidence']['definition']['revision']==revision)
  for _ in range(6):await frame(1.5,asset='SECOND')
  check('invalid_source_blocks_new_alerts',len(await read_alerts())==2)
  update("MATCH (p:AnomalyPattern {id:$id})-[t:TESTS]->() SET t.operator='>'")
  status,_=await reload();check('source_recovery_applies_valid_definition',status==200)
  _,state=await request('/api/detector/patterns')
  check('outbox_drained',state['pending_alerts']==0)
  evidence.update(alerts=alerts,final=state,topics=names)
 finally:
  if child is not None and child.poll() is None:child.terminate();child.wait(timeout=15)
  await publisher.stop();await output.stop()
  with driver.session() as s:
   evidence['fixture_removed']=s.run('MATCH (n {fixture:$id}) WITH collect(n) AS ns FOREACH (n IN ns | DETACH DELETE n) RETURN size(ns) AS n',id=nonce).single()['n']
  driver.close();serverlog.close()
  evidence.update(checks=checks,server_log=Path('/tmp/detector-probe.log').read_text(),child_returncode=child.returncode if child else None)
  print(json.dumps(evidence,default=str),flush=True)
asyncio.run(main())
'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    run=subprocess.run(['docker','run','--rm','-i','--network','hyd-iot-edu_it-net',
                        '-e','KAFKA_BOOTSTRAP=redpanda:9092','hyd-iot-edu-detector','python','-'],
                       input=CODE,text=True,encoding='utf8',capture_output=True,timeout=180)
    (out/'stderr.log').write_text(run.stderr,encoding='utf8')
    (out/'result.json').write_text(run.stdout,encoding='utf8')
    if run.stdout.strip():
        data=json.loads(run.stdout);(out/'checks.json').write_text(json.dumps(data['checks'],indent=2),encoding='utf8')
        for name,ok in data['checks'].items():print(('PASS ' if ok else 'FAIL ')+name)
    if run.returncode:raise RuntimeError(run.stderr[-5000:])


if __name__=='__main__':main()
