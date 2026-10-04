"""SQLite source snapshot and graph intent share one commit; no network under lock."""
import hashlib
import json
import time


class CaseProjectionStore:
    def _init_case_projection(self):
        with self._lock,self.db:
            self.db.execute('''create table if not exists case_projection_source (
                kind text not null, source_id text not null, digest text not null,
                primary key(kind,source_id))''')
            self.db.execute('''create table if not exists case_projection_outbox (
                id integer primary key autoincrement, kind text not null, source_id text not null,
                body text not null, created_at real not null, processed_at real,
                attempts integer not null default 0, last_error text, retry_at real not null default 0)''')
            self.db.execute('''create index if not exists case_projection_pending
                on case_projection_outbox(kind,source_id,id) where processed_at is null''')
            self.db.execute('''create table if not exists knowledge_projection_checkpoint (
                consumer text primary key,digest text not null,queued_at real not null)''')
            self.db.execute('''create table if not exists projection_repairs (
                request_id text primary key,fingerprint text not null,result text not null)''')
            row=self.db.execute('select body from snapshot where id=1').fetchone()
            if row:self._enqueue_case_snapshot(json.loads(row[0]))

    def _enqueue_case_snapshot(self,data,force=False):
        # Caller holds both Store lock and SQLite transaction. Serialize from the
        # exact saved snapshot, never from mutable live objects a second time.
        values={('Incident',i['id']):i for i in data.get('incidents',[])}
        values.update({('DecisionCase',key):value for key,value in data.get('book',{}).items()})
        known={(kind,sid):digest for kind,sid,digest in self.db.execute('select kind,source_id,digest from case_projection_source')}
        encoded={key:json.dumps(values.get(key),ensure_ascii=False,sort_keys=True,separators=(',',':')) for key in values.keys() | known.keys()}
        digests={key:hashlib.sha256(body.encode()).hexdigest() for key,body in encoded.items()}
        changed_incidents={sid for (kind,sid),digest in digests.items() if kind=='Incident' and known.get((kind,sid))!=digest}
        for key in values.keys() | known.keys():
            body,digest=encoded[key],digests[key]
            dependency_changed=(key[0]=='DecisionCase' and ((values.get(key) or {}).get('origin') or {}).get('incident') in changed_incidents)
            if not force and known.get(key)==digest and not dependency_changed:continue
            self.db.execute('insert into case_projection_outbox(kind,source_id,body,created_at) values(?,?,?,?)',(*key,body,time.time()))
            self.db.execute('insert or replace into case_projection_source values(?,?,?)',(*key,digest))

    def knowledge_projection_checkpoint(self,consumer):
        with self._lock:
            row=self.db.execute('select digest,queued_at from knowledge_projection_checkpoint where consumer=?',(consumer,)).fetchone()
            return dict(digest=row[0],queued_at=row[1]) if row else None

    def enqueue_knowledge_cases(self,consumer,digest):
        with self._lock,self.db:
            row=self.db.execute('select body from snapshot where id=1').fetchone()
            # Includes known deletions; never restore a tombstoned judgment from
            # an old payload merely because the knowledge graph changed.
            self._enqueue_case_snapshot(json.loads(row[0]) if row else {},force=True)
            self.db.execute('insert or replace into knowledge_projection_checkpoint values(?,?,?)',(consumer,digest,time.time()))

    def case_projection_batch(self,limit=20):
        with self._lock:
            keys=self.db.execute('''select kind,source_id from case_projection_outbox
                where processed_at is null group by kind,source_id
                having min(retry_at)<=? and max(case when last_error like 'ProjectionConflict:%' then 1 else 0 end)=0
                order by case kind when 'Incident' then 0 else 1 end,min(id) limit ?''',
                (time.time(),limit)).fetchall()
            batch=[]
            for kind,sid in keys:
                rows=self.db.execute('''select id,body from case_projection_outbox
                    where kind=? and source_id=? and processed_at is null order by id''',(kind,sid)).fetchall()
                batch.append({'kind':kind,'source_id':sid,'revision':rows[-1][0],
                              'body':json.loads(rows[-1][1]),'ids':[r[0] for r in rows]})
            return batch

    def finish_case_projection(self,job,error=None):
        with self._lock,self.db:
            self.db.executemany('''update case_projection_outbox set attempts=attempts+1,
                processed_at=?,last_error=?,retry_at=? where id=? and processed_at is null''',
                [(None if error else time.time(),error,time.time()+5,jid) for jid in job['ids']])

    def case_projection_status(self,limit=100):
        with self._lock:
            pending=self.db.execute('select count(*) from case_projection_outbox where processed_at is null').fetchone()[0]
            rows=self.db.execute('''select kind,source_id,count(*),max(attempts),max(last_error)
                from case_projection_outbox where processed_at is null group by kind,source_id order by min(id) limit ?''',(limit,)).fetchall()
            return {'pending':pending,'items':[dict(zip(('kind','source_id','pending','attempts','last_error'),row)) for row in rows]}
