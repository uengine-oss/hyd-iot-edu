"""Durable execution projection delivery, separate from business transactions.

Only the exact queue rows seen in a consistent source snapshot are acknowledged.
Sequence order is not commit order: acknowledging `id <= max_id` could lose an
uncommitted older enqueue. Projection revisions fence delayed graph deliveries.
"""
from contextlib import contextmanager


class PgProjection:
    def enqueue_projection_cleanup(self, tenant, pid):
        with self._conn() as c:
            c.execute('''insert into execution_projection_outbox(tenant_id,proc_inst_id)
                select %s,%s where not exists(select 1 from execution_projection_outbox
                    where tenant_id=%s and proc_inst_id=%s and processed_at is null)''', (tenant,pid,tenant,pid))

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
        """스냅숏이 본 대기열 행을 처리 표시한다. A-01: 처리한 행은 처리 건마다 마지막 하나(마지막 반영 판 last_revision 의 원천)만 남기고
        지운다 — 처리 표시만 하고 지우지 않아 작업 행이 바뀔 때마다 한 줄씩 끝없이 쌓였다. 아직 처리하지 않은 행은 건드리지 않는다."""
        with self._conn() as c:
            done = c.execute('''update execution_projection_outbox set attempts=attempts+1,last_error=%s,revision=%s,
                processed_at=case when %s::text is null then now() else null end,
                retry_at=now()+interval '5 seconds' where id=any(%s) and processed_at is null
                returning tenant_id,proc_inst_id,id''',
                      (error, snapshot['revision'], error, snapshot['ids'])).fetchall()
            if error is None and done:
                c.execute('''delete from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s
                    and processed_at is not null and id < %s''', (done[0]['tenant_id'], done[0]['proc_inst_id'], max(r['id'] for r in done)))

    def projection_status(self, tenant, pid):
        with self._conn() as c:
            return dict(c.execute('''select count(*) filter(where processed_at is null) as pending,
                max(revision) filter(where processed_at is not null) as last_revision,
                (array_agg(last_error order by id desc) filter(where processed_at is null and last_error is not null))[1] as last_error
                from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s''', (tenant,pid)).fetchone())
