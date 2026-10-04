"""Actual Kafka with the built detector in an isolated container/topic group.

Synthetic source records never enter production plant.tag or alerts topics.
"""
import json
from pathlib import Path
import subprocess

OUT=Path('.evidence/reaudit/a054-kafka');OUT.mkdir(exist_ok=True)
code=r"""import asyncio,json,time,uuid
from datetime import datetime,timezone
from aiokafka.admin import AIOKafkaAdminClient,NewTopic
from hydcommon import kafka,topics
from det import main

async def check_run():
 nonce='a054-'+uuid.uuid4().hex[:10]
 names=[nonce+'.'+key.lower() for key in ('tag','wave','status','feat','alerts')]
 for key,name in zip(('K_TAG','K_WAVE','K_STATUS','K_FEAT','K_ALERTS'),names):setattr(topics,key,name)
 admin=AIOKafkaAdminClient(bootstrap_servers='redpanda:9092')
 await admin.start()
 try:await admin.create_topics([NewTopic(t,1,1,topic_configs={'retention.ms':'3600000'}) for t in names])
 finally:await admin.close()
 clients=[];received={};checks={};result={'topics':names,'synthetic_records':True}
 def check(name,ok):
  checks[name]=bool(ok)
  if not ok:raise AssertionError(name)
 async def detector_consumer(*args,**kw):
  kw['group']=nonce
  c=await kafka.consumer(*args,**kw);clients.append(c);received['consumer']=c;return c
 async def detector_producer():
  p=await kafka.producer();clients.append(p);return p
 main.make_consumer=detector_consumer;main.make_producer=detector_producer
 task=asyncio.create_task(main.run())
 publisher=await kafka.producer()
 output=await kafka.consumer([topics.K_ALERTS],group=nonce+'-output',from_latest=False)
 try:
  for _ in range(100):
   if received.get('consumer') and received['consumer'].assignment():break
   await asyncio.sleep(.1)
  else:raise RuntimeError('isolated detector has no Kafka assignment')
  # Assignment precedes initial latest-offset resolution. Finish that before
  # sending the first fixture record, otherwise the probe can skip its own input.
  for partition in received['consumer'].assignment():
   await received['consumer'].position(partition)
  async def processed(count):
   for _ in range(100):
    if task.done():await task
    if main.state['tags']+main.state.get('test_status_count',0)>=count:return
    await asyncio.sleep(.05)
   raise RuntimeError('detector did not process published tag')
  async def tag(name,value,stamp=None,quality='good',asset='FIXTURE'):
   count=main.state['tags']+1
   stamp=stamp or datetime.now(timezone.utc).isoformat()
   await publisher.send_and_wait(topics.K_TAG,key=asset,value=dict(asset=asset,name=name,t=stamp,v=value,q=quality))
   await processed(count)
   return stamp
  async def frame(value,delay=1.05):
   if delay:await asyncio.sleep(delay)
   stamp=datetime.now(timezone.utc).isoformat()
   await tag('CE',40,stamp);await tag('TS1',value,stamp)
  await frame(57,0);await frame(58)
  a=main.assets['FIXTURE']
  check('actual_kafka_candidate_started',a.cep_state.phase=='CANDIDATE')
  await frame(59,4.2)
  result['after_raise_gap']=main.detector_state()
  check('gap_does_not_raise',a.cep_state.phase=='IDLE' and main.state['alerts']==0)
  for v in (59.1,59.2,59.3,59.4):await frame(v)
  aid=a.cep_state.alert_id
  check('new_contiguous_window_raises',a.cep_state.phase=='RAISED' and aid is not None and main.state['alerts']==1)
  await frame(50)
  check('recovery_hold_started',a.cep_state.phase=='CLEARING')
  await frame(49,4.2)
  result['after_clear_gap']=main.detector_state()
  check('gap_preserves_raised_alert_id',a.cep_state.phase=='CLEARING' and a.cep_state.alert_id==aid and main.state['alerts']==1)
  for v in (48.9,48.8,48.7,48.6):await frame(v)
  check('fresh_recovery_clears_once',a.cep_state.phase=='IDLE' and main.state['alerts']==2)
  before=a.latest['TS1']
  await tag('TS1',99,'2020-01-01T00:00:00Z')
  check('late_record_does_not_overwrite_latest',a.latest['TS1']==before)
  await tag('CE',None,quality='bad')
  await tag('TS1',48.5)
  check('bad_quality_is_explicit_unknown',a.data_quality['COOLER_DEGRADATION']['status']=='UNKNOWN' and 'CE' in a.data_quality['COOLER_DEGRADATION']['problems'])
  await tag('TS1',59,asset='MISSING-INPUT-FIXTURE')
  check('missing_input_is_not_default_value',main.assets['MISSING-INPUT-FIXTURE'].data_quality['COOLER_DEGRADATION']['problems']['CE']=='MISSING')
  alerts=[]
  for _ in range(20):
   records=await output.getmany(timeout_ms=200)
   alerts.extend(record.value for batch in records.values() for record in batch)
   if len(alerts)>=2:break
  result['alerts']=alerts
  check('actual_output_topic_has_matching_raise_clear',len(alerts)==2 and [x['state'] for x in alerts]==['RAISE','CLEAR'] and all(x['alertId']==aid for x in alerts))
  check('events_record_time_contract',all(x['evidence']['observation']['time_scale']==20 and x['evidence']['observation']['profile']=='lite' for x in alerts))
  result['final']=main.detector_state();result['checks']=checks
  print(json.dumps(result,default=str))
 finally:
  task.cancel()
  await asyncio.gather(task,return_exceptions=True)
  await publisher.stop();await output.stop()
  for client in reversed(clients):await client.stop()
asyncio.run(check_run())
"""
run=subprocess.run(['docker','run','--rm','-i','--network','hyd-iot-edu_it-net',
                    '-e','KAFKA_BOOTSTRAP=redpanda:9092','-e','TIME_SCALE=20','-e','DAQ_PROFILE=lite',
                    'hyd-iot-edu-detector','python','-'],input=code,text=True,encoding='utf8',capture_output=True,timeout=120)
(OUT/'stderr.log').write_text(run.stderr,encoding='utf8');(OUT/'result.json').write_text(run.stdout,encoding='utf8')
assert run.returncode==0,run.stderr
data=json.loads(run.stdout)
(OUT/'checks.json').write_text(json.dumps(data['checks'],indent=2),encoding='utf8')
for name,passed in data['checks'].items():print(('PASS ' if passed else 'FAIL ')+name)
assert all(data['checks'].values())
