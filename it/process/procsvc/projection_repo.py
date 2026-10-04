"""Durable execution projection delivery, separate from business transactions.

Only the exact queue rows seen in a consistent source snapshot are acknowledged.
Sequence order is not commit order: acknowledging `id <= max_id` could lose an
uncommitted older enqueue. Projection revisions fence delayed graph deliveries.
"""
from contextlib import contextmanager


class MemoryProjection:
    def enqueue_knowledge_projections(self,tenant):
        with self._lock:
            pids={p['proc_inst_id'] for p in self.instances.values() if p['tenant_id']==tenant}
            pids.update(j['proc_inst_id'] for j in list(self.projection_jobs.values()) if j['tenant_id']==tenant)
            for pid in pids:self._enqueue_projection(dict(tenant_id=tenant,proc_inst_id=pid))

    def enqueue_incident_projections(self,tenant,incident):
        with self._lock:
            for inst in self.instances.values():
                if inst['tenant_id']==tenant and any(v.get('key')=='incident' and v.get('value')==incident for v in inst.get('variables_data') or []):
                    self._enqueue_projection(inst)

    def _enqueue_projection(self, row):
        if row.get('proc_inst_id'):
            self._projection_sequence += 1
            self.projection_jobs[self._projection_sequence] = {
                'id': self._projection_sequence, 'tenant_id': row['tenant_id'],
                'proc_inst_id': row['proc_inst_id'], 'processed_at': None,
                'attempts': 0, 'last_error': None}

    def pending_projections(self, tenant, limit=20):
        with self._lock:
            blocked={j['proc_inst_id'] for j in self.projection_jobs.values() if not j['processed_at'] and (j['last_error'] or '').startswith('ProjectionConflict:')}
            return list(dict.fromkeys(j['proc_inst_id'] for j in self.projection_jobs.values()
                                      if j['tenant_id'] == tenant and not j['processed_at'] and j['proc_inst_id'] not in blocked))[:limit]

    @contextmanager
    def projection_snapshot(self, tenant, pid):
        # Memory adapter uses its transaction lock; production holds no source
        # row lock during graph IO.
        with self._lock:
            jobs = [j['id'] for j in self.projection_jobs.values()
                    if j['tenant_id'] == tenant and j['proc_inst_id'] == pid and not j['processed_at']]
            if not jobs or any((self.projection_jobs[j]['last_error'] or '').startswith('ProjectionConflict:') for j in jobs):
                yield None
                return
            self._projection_sequence += 1
            inst = self.get_instance(pid)
            yield {'ids': jobs, 'revision': self._projection_sequence, 'instance': inst,
                   'items': self.list_workitems(proc_inst_id=pid, limit=None)}

    def finish_projection(self, snapshot, error=None):
        with self._lock:
            for jid in snapshot['ids']:
                j = self.projection_jobs[jid]
                j.update(attempts=j['attempts'] + 1, last_error=error,
                         processed_at=None if error else True, revision=snapshot['revision'])

    def projection_status(self, tenant, pid):
        with self._lock:
            jobs = [j for j in self.projection_jobs.values() if j['tenant_id'] == tenant and j['proc_inst_id'] == pid]
            pending = [j for j in jobs if not j['processed_at']]
            return {'pending': len(pending), 'last_error': next((j['last_error'] for j in reversed(pending) if j['last_error']), None),
                    'last_revision': max((j.get('revision', 0) for j in jobs if j['processed_at']), default=None)}


class PgProjection:
    def enqueue_knowledge_projections(self,tenant):
        # Retain deleted source identities too so reconciliation preserves their
        # graph tombstones. Append behind in-flight snapshots, never mark them done.
        with self._conn() as c:
            c.execute('''insert into execution_projection_outbox(tenant_id,proc_inst_id)
                select tenant_id,proc_inst_id from bpm_proc_inst where tenant_id=%s
                union select tenant_id,proc_inst_id from execution_projection_outbox where tenant_id=%s''',(tenant,tenant))

    def enqueue_incident_projections(self,tenant,incident):
        # Always append: a pending older snapshot may already be in flight.
        with self._conn() as c:
            c.execute('''insert into execution_projection_outbox(tenant_id,proc_inst_id)
                select tenant_id,proc_inst_id from bpm_proc_inst where tenant_id=%s
                and variables_data @> %s''',(tenant,self._Jsonb([{'key':'incident','value':incident}])))

    def pending_projections(self, tenant, limit=20):
        with self._conn() as c:
            return [r['proc_inst_id'] for r in c.execute('''select proc_inst_id from execution_projection_outbox
                where tenant_id=%s and processed_at is null
                group by proc_inst_id having min(retry_at)<=now() and not bool_or(coalesce(last_error,'') like 'ProjectionConflict:%%')
                order by min(id) limit %s''', (tenant, limit)).fetchall()]

    @contextmanager
    def projection_snapshot(self, tenant, pid):
        if getattr(self._local, 'connection', None) is not None:
            raise RuntimeError('projection must run after source commit')
        # Dedicated session-level delivery lock, not a business row lock.
        with self._psycopg.connect(self.dsn, autocommit=True, connect_timeout=5,
                                  row_factory=self._dict_row) as c:
            key = 'execution-projection:' + tenant + ':' + pid
            locked = c.execute('select pg_try_advisory_lock(hashtextextended(%s,0)) as ok', (key,)).fetchone()['ok']
            if not locked:
                yield None
                return
            try:
                with c.transaction():
                    c.execute('set transaction isolation level repeatable read')
                    jobs = c.execute('''select id,last_error from execution_projection_outbox
                        where tenant_id=%s and proc_inst_id=%s and processed_at is null order by id''', (tenant, pid)).fetchall()
                    ids=[] if any((j['last_error'] or '').startswith('ProjectionConflict:') for j in jobs) else [j['id'] for j in jobs]
                    snapshot = None
                    if ids:
                        c.execute("select pg_advisory_xact_lock(hashtextextended('hyd-projection-revision',0))")
                        revision = c.execute("select nextval('hyd_projection_revision') as n").fetchone()['n']
                        self._local.connection = c
                        try:
                            snapshot = {'ids': ids, 'revision': revision, 'instance': self.get_instance(pid),
                                        'items': self.list_workitems(proc_inst_id=pid, limit=None)}
                        finally:
                            del self._local.connection
                yield snapshot
            finally:
                c.execute('select pg_advisory_unlock(hashtextextended(%s,0))', (key,))

    def finish_projection(self, snapshot, error=None):
        with self._conn() as c:
            c.execute('''update execution_projection_outbox set attempts=attempts+1,last_error=%s,revision=%s,
                processed_at=case when %s::text is null then now() else null end,
                retry_at=now()+interval '5 seconds' where id=any(%s) and processed_at is null''',
                      (error, snapshot['revision'], error, snapshot['ids']))

    def projection_status(self, tenant, pid):
        with self._conn() as c:
            return dict(c.execute('''select count(*) filter(where processed_at is null) as pending,
                max(revision) filter(where processed_at is not null) as last_revision,
                (array_agg(last_error order by id desc) filter(where processed_at is null and last_error is not null))[1] as last_error
                from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s''', (tenant,pid)).fetchone())
