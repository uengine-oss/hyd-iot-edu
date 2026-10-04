"""Durable source receipts used by the instance-mode Kafka/HTTP delivery path.

Kafka coordinates identify a delivery; business identity identifies the event.
All deliveries retain their payload. Duplicate and conflicting deliveries never
replace the first event's payload or its pinned execution policy.
"""
from copy import deepcopy
import base64
from datetime import datetime, timezone
import hashlib
import json
import uuid

from hydcommon import topics

_DECODED = object()


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def source_record(topic, partition, offset, payload, *, source='kafka', wire=_DECODED):
    if topic not in (topics.K_ALERTS, topics.K_STATUS):
        raise ValueError('unsupported source topic')
    if source not in ('kafka','http'):
        raise ValueError('unsupported source transport')
    if source=='kafka' and any(type(v) is not int or v < 0 for v in (partition, offset)):
        raise ValueError('Kafka partition and offset must be nonnegative integers')
    if source=='http' and (topic!=topics.K_ALERTS or partition is not None or offset is not None):
        raise ValueError('HTTP alarm receipts must not invent Kafka coordinates')
    if not isinstance(payload, dict):
        raise ValueError('source payload must be the decoded object, including malformed _raw values')
    value = deepcopy(payload)
    asset = value.get('asset')
    asset = asset if isinstance(asset, str) and asset.strip() else None
    origin = [source,topic,partition,offset] if source=='kafka' else [source,topic,digest(value)]
    kind, identity, semantic, error = 'STATUS', ['delivery', *origin], value, None
    if topic == topics.K_ALERTS:
        aid, state = value.get('alertId'), value.get('state')
        if asset and isinstance(aid, str) and aid.strip() and state in ('RAISE', 'CLEAR'):
            kind, identity = state, ['alert', aid, state]
        else:
            kind, error = 'INVALID', 'alert requires asset, alertId and RAISE/CLEAR'
    elif not asset or '_raw' in value:
        kind, error = 'INVALID', 'plant status requires an asset and an object payload'
    elif isinstance(value.get('cmdId'), str) and value['cmdId'] and value.get('result') in ('DONE', 'REJECTED'):
        kind, identity = 'ACK', ['command-ack', value['cmdId']]
        # The PLC repeats its retained ACK in later heartbeats. Changing sensor
        # values or heartbeat timestamps does not change that command's result.
        semantic = {k: value.get(k) for k in ('asset', 'cmdId', 'result', 'reason', 'interlock')}
    if wire is _DECODED:
        wire_kind='decoded';wire_bytes=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    elif wire is None:
        wire_kind='tombstone';wire_bytes=b''
    elif isinstance(wire,bytes):
        wire_kind='bytes';wire_bytes=wire
    else:raise ValueError('wire input must be bytes or a Kafka tombstone')
    return dict(source=source,delivery_key=digest(origin),topic=topic, partition_no=partition, offset_no=offset, asset=asset, kind=kind,
                event_key=json.dumps(identity, ensure_ascii=False, separators=(',', ':')),
                payload=value, payload_sha=digest(value), semantic_sha=digest(semantic), error=error,
                wire_kind=wire_kind,wire_base64=base64.b64encode(wire_bytes).decode('ascii'),
                wire_sha=hashlib.sha256(wire_bytes).hexdigest())


def kafka_record(record):
    """Must receive bytes before a Kafka value deserializer loses information."""
    raw=record.value
    if raw is not None and not isinstance(raw,bytes):raise ValueError('raw Kafka consumer required')
    try:
        value=json.loads(raw.decode('utf-8')) if raw is not None else {'_raw':None}
        if not isinstance(value,dict):raise ValueError('source JSON must be an object')
        digest(value)
    except (UnicodeDecodeError,ValueError):
        value={'_raw':raw.decode('utf-8',errors='replace') if raw is not None else None}
    return source_record(record.topic,record.partition,record.offset,value,wire=raw)


def source_time(payload):
    try:
        t=datetime.fromisoformat(payload['t'].replace('Z','+00:00'))
        return t.astimezone(timezone.utc) if t.tzinfo is not None else None
    except (KeyError,TypeError,AttributeError,ValueError):return None


class PgSourceInbox:
    """Uses the existing PgRepo connection contract; each receipt commits alone.

The caller may acknowledge its Kafka offset only after receive() returns. This
class does not execute a process, issue a command or declare business completion.
"""
    def __init__(self, repo, tenant_id='hyd'):
        self.repo, self.tenant_id = repo, tenant_id

    def receive(self, record, policy=None):
        if getattr(self.repo._local, 'connection', None) is not None:
            raise RuntimeError('source receipt requires its own committed transaction')
        record = deepcopy(record)
        if record['kind'] == 'RAISE' and not isinstance(policy, dict):
            raise ValueError('RAISE requires the policy selected at receipt time')
        pinned = deepcopy(policy)
        digest(pinned)  # JSON validity, including no non-finite policy numbers.
        with self.repo._conn() as c, c.transaction():
            origin = [self.tenant_id,record['delivery_key']]
            c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',
                      (json.dumps(['source-origin', *origin]),))
            prior = c.execute('''select * from process_source_inbox
                where tenant_id=%s and delivery_key=%s for update''', origin).fetchone()
            if prior:
                if any(prior[k]!=record[k] for k in ('payload_sha','wire_kind','wire_sha')):
                    raise ValueError('same Kafka coordinates contain a different payload')
                return self.repo._row(prior)
            c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',
                      (json.dumps(['source-event', self.tenant_id, record['event_key']]),))
            first = c.execute('''select * from process_source_inbox
                where tenant_id=%s and event_key=%s and parent_id is null for update''',
                (self.tenant_id, record['event_key'])).fetchone()
            status, parent, error = ('INVALID' if record['kind'] == 'INVALID' else 'PENDING'), None, record['error']
            observed_at=source_time(record['payload']) if record['topic']==topics.K_STATUS else None
            if record['kind']=='STATUS' and observed_at is None:
                status,error='INVALID','status requires an explicit source timestamp with timezone'
            if first:
                parent = first['id']
                status = 'DUPLICATE' if first['semantic_sha'] == record['semantic_sha'] else 'CONFLICT'
                pinned = first['policy']
                if status == 'CONFLICT':
                    error = 'same business event identity contains conflicting source data'
            row = c.execute('''insert into process_source_inbox
                (tenant_id,source,delivery_key,topic,partition_no,offset_no,event_key,asset,kind,payload,payload_sha,
                 semantic_sha,policy,status,parent_id,error,wire_kind,wire_base64,wire_sha)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *''',
                (self.tenant_id,record['source'],record['delivery_key'],record['topic'], record['partition_no'], record['offset_no'],
                 record['event_key'], record['asset'], record['kind'], self.repo._Jsonb(record['payload']),
                 record['payload_sha'], record['semantic_sha'], self.repo._Jsonb(pinned), status, parent, error,
                 record['wire_kind'],record['wire_base64'],record['wire_sha'])).fetchone()
            if record['kind'] in ('STATUS','ACK') and observed_at is not None:
                c.execute('''insert into process_source_state(tenant_id,asset,source_time,receipt_id,payload)
                    values(%s,%s,%s,%s,%s) on conflict(tenant_id,asset) do update set
                    source_time=excluded.source_time,receipt_id=excluded.receipt_id,payload=excluded.payload
                    where process_source_state.source_time<excluded.source_time''',
                    (self.tenant_id,record['asset'],observed_at,row['id'],self.repo._Jsonb(record['payload'])))
                if record['kind']=='STATUS' and status=='PENDING':
                    row=c.execute("""update process_source_inbox set status='HANDLED',handled_at=now(),
                        result='{"observation":"source timestamp compared; latest state retained"}'::jsonb
                        where id=%s returning *""",(row['id'],)).fetchone()
            return self.repo._row(row)

    def latest_states(self):
        with self.repo._conn() as c:
            return {r['asset']:r['payload'] for r in c.execute(
                'select asset,payload from process_source_state where tenant_id=%s',(self.tenant_id,)).fetchall()}

    def get(self, receipt_id):
        with self.repo._conn() as c:
            return self.repo._row(c.execute('select * from process_source_inbox where tenant_id=%s and id=%s',
                                           (self.tenant_id, receipt_id)).fetchone())

    def list(self, *, after_id=0, limit=100, status=None):
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('limit must be between 1 and 500')
        if status is not None and status not in {'PENDING','CLAIMED','HANDLED','WAITING','FAILED','DUPLICATE','CONFLICT','INVALID'}:
            raise ValueError('unknown source status')
        with self.repo._conn() as c:
            return [self.repo._row(r) for r in c.execute('''select * from process_source_inbox
                where tenant_id=%s and id>%s and (%s::text is null or status=%s) order by id limit %s''',
                (self.tenant_id,after_id,status,status,limit)).fetchall()]

    def _standalone(self):
        if getattr(self.repo._local, 'connection', None) is not None:
            raise RuntimeError('source processing requires its own committed transaction')

    @staticmethod
    def _seconds(value):
        if type(value) is not int or not 1 <= value <= 3600:
            raise ValueError('duration must be an integer between 1 and 3600 seconds')
        return value

    def claim(self, owner, *, lease_s=60, max_failures=3):
        """One live receipt per asset; unrelated assets may run concurrently.

        WAITING does not block a later RAISE that can satisfy an unmatched CLEAR.
        Lease expiry is a failed attempt, never evidence of successful handling.
        """
        self._standalone();self._seconds(lease_s)
        if not isinstance(owner,str) or not owner.strip():
            raise ValueError('claim owner required')
        if type(max_failures) is not int or not 1 <= max_failures <= 100:
            raise ValueError('max_failures must be between 1 and 100')
        with self.repo._conn() as c, c.transaction():
            # Serialize only the short scheduling decision, not business work.
            # SKIP LOCKED alone cannot exclude another pending row of one asset.
            c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',
                      (json.dumps(['source-scheduler',self.tenant_id]),))
            c.execute('''update process_source_inbox set
                status=case when failures+1 >= %s then 'FAILED' else 'PENDING' end,
                failures=failures+1,owner=null,claim_token=null,lease_until=null,
                error='source handler lease expired',next_attempt_at=now(),
                history=history || jsonb_build_array(jsonb_build_object(
                    'event','lease_expired','at',now(),'owner',owner,'token',claim_token,'attempt',attempts))
                where tenant_id=%s and status='CLAIMED' and lease_until<=now()''',
                (max_failures,self.tenant_id))
            row=c.execute('''select r.id from process_source_inbox r
                where r.tenant_id=%s and r.status in ('PENDING','WAITING') and r.next_attempt_at<=now()
                  and not exists(select 1 from process_source_inbox live
                    where live.tenant_id=r.tenant_id and live.asset is not distinct from r.asset
                      and live.status='CLAIMED' and live.lease_until>now())
                order by r.id limit 1 for update of r''',(self.tenant_id,)).fetchone()
            if row is None:return None
            token=str(uuid.uuid4())
            return self.repo._row(c.execute('''update process_source_inbox set status='CLAIMED',
                owner=%s,claim_token=%s,lease_until=now()+(%s*interval '1 second'),attempts=attempts+1,
                history=history || jsonb_build_array(jsonb_build_object(
                    'event','claimed','at',now(),'owner',%s::text,'token',%s::text,'attempt',attempts+1))
                where tenant_id=%s and id=%s returning *''',
                (owner,token,lease_s,owner,token,self.tenant_id,row['id'])).fetchone())

    def _owned(self, receipt, assignments, params):
        self._standalone()
        with self.repo._conn() as c:
            return self.repo._row(c.execute('update process_source_inbox set '+assignments+'''
                where tenant_id=%s and id=%s and status='CLAIMED' and owner=%s
                  and claim_token=%s and lease_until>now() returning *''',
                (*params,self.tenant_id,receipt['id'],receipt['owner'],receipt['claim_token'])).fetchone())

    def renew(self, receipt, *, lease_s=60):
        self._seconds(lease_s)
        return self._owned(receipt,"lease_until=now()+(%s*interval '1 second')",(lease_s,))

    def finish(self, receipt, result):
        if not isinstance(result,dict):raise ValueError('observed handling result required')
        digest(result)
        return self._owned(receipt,'''status='HANDLED',result=%s,handled_at=now(),error=null,
            history=history || jsonb_build_array(jsonb_build_object('event','handled','at',now(),
                'owner',owner,'token',claim_token,'attempt',attempts)),
            owner=null,claim_token=null,lease_until=null''',(self.repo._Jsonb(result),))

    def defer(self, receipt, reason, *, delay_s=5, result=None):
        """An unmatched CLEAR/ACK waits visibly without consuming failure budget."""
        self._seconds(delay_s)
        if not isinstance(reason,str) or not reason.strip():raise ValueError('waiting reason required')
        digest(result)
        return self._owned(receipt,'''status='WAITING',error=%s,result=%s,
            next_attempt_at=now()+(%s*interval '1 second'),
            history=history || jsonb_build_array(jsonb_build_object('event','waiting','at',now(),
                'owner',owner,'token',claim_token,'reason',%s::text)),
            owner=null,claim_token=null,lease_until=null''',
            (reason,self.repo._Jsonb(result),delay_s,reason))

    def fail(self, receipt, error, *, delay_s=5, max_failures=3):
        self._seconds(delay_s)
        if not isinstance(error,str) or not error.strip():raise ValueError('failure evidence required')
        if type(max_failures) is not int or not 1<=max_failures<=100:raise ValueError('invalid failure limit')
        return self._owned(receipt,'''status=case when failures+1 >= %s then 'FAILED' else 'PENDING' end,
            failures=failures+1,error=%s,next_attempt_at=now()+(%s*interval '1 second'),
            history=history || jsonb_build_array(jsonb_build_object('event','failed_attempt','at',now(),
                'owner',owner,'token',claim_token,'error',%s::text,'attempt',attempts)),
            owner=null,claim_token=null,lease_until=null''',(max_failures,error,delay_s,error))

    def retry_failed(self, receipt_id, *, by, reason):
        self._standalone()
        if any(not isinstance(v,str) or not v.strip() for v in (by,reason)):
            raise ValueError('explicit retry actor and reason required')
        with self.repo._conn() as c:
            return self.repo._row(c.execute('''update process_source_inbox set status='PENDING',
                failures=0,next_attempt_at=now(),
                history=history || jsonb_build_array(jsonb_build_object('event','explicit_retry',
                    'at',now(),'by',%s::text,'reason',%s::text,'prior_failures',failures))
                where tenant_id=%s and id=%s and status='FAILED' returning *''',
                (by,reason,self.tenant_id,receipt_id)).fetchone())
