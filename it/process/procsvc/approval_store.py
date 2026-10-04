"""Durable approval intents. Call mutations under the owning instance lock.

The payload is immutable; only delivery status/results/history may change.
These mixins share the same connection/rollback scope as the process rows.
"""
from copy import deepcopy


class MemoryApprovals:
    def insert_approval(self, row):
        with self._lock:
            wi = self.workitems.get(row['todo_id'])
            if not wi or (wi['tenant_id'], wi['proc_inst_id']) != (row['tenant_id'], row['proc_inst_id']):
                raise ValueError('approval work item ownership mismatch')
            if row['todo_id'] in self.approvals or any(
                (x['tenant_id'], x['decision_id']) == (row['tenant_id'], row['decision_id'])
                for x in self.approvals.values()
            ):
                raise ValueError('decision already has an approval intent')
            self.approvals[row['todo_id']] = deepcopy(row)

    def get_approval(self, todo_id, tenant_id):
        with self._lock:
            row = self.approvals.get(todo_id)
            return deepcopy(row) if row and row['tenant_id'] == tenant_id else None

    def update_approval(self, row):
        with self._lock:
            prior = self.approvals.get(row['todo_id'])
            if not prior or prior['tenant_id'] != row['tenant_id']:
                raise KeyError('no such approval')
            for key in ('status', 'attempts', 'results', 'error', 'history'):
                prior[key] = deepcopy(row[key])

    def list_approvals(self, proc_inst_id, tenant_id):
        with self._lock:
            return [deepcopy(x) for x in self.approvals.values()
                    if x['proc_inst_id'] == proc_inst_id and x['tenant_id'] == tenant_id]

    def pending_approvals(self, tenant_id, after_id=None, limit=100):
        with self._lock:
            rows = [x for x in self.approvals.values()
                    if x['tenant_id'] == tenant_id and x['status'] == 'PENDING'
                    and (after_id is None or x['todo_id'] > after_id)
                    and self.instances.get(x['proc_inst_id'], {}).get('status') == 'RUNNING'
                    and not self.instances[x['proc_inst_id']].get('is_deleted')
                    and self.workitems.get(x['todo_id'], {}).get('status') == 'SUBMITTED']
            return deepcopy(sorted(rows, key=lambda x: x['todo_id'])[:limit])


class PgApprovals:
    def insert_approval(self, row):
        columns = ('todo_id', 'proc_inst_id', 'tenant_id', 'decision_id', 'payload',
                   'status', 'attempts', 'results', 'error', 'history')
        values = [self._Jsonb(row[k]) if k in ('payload', 'results', 'history') else row[k] for k in columns]
        with self._conn() as c:
            inserted = c.execute('''insert into process_approval_outbox
                (todo_id,proc_inst_id,tenant_id,decision_id,payload,status,attempts,results,error,history)
                select %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                where exists(select 1 from todolist w join bpm_proc_inst i using(proc_inst_id)
                    where w.id=%s and w.proc_inst_id=%s and w.tenant_id=%s and i.tenant_id=%s)
                on conflict do nothing returning todo_id''',
                (*values, row['todo_id'], row['proc_inst_id'], row['tenant_id'], row['tenant_id'])).fetchone()
            if inserted is None:
                raise ValueError('decision already has an approval intent or ownership mismatch')

    def get_approval(self, todo_id, tenant_id):
        with self._conn() as c:
            return self._row(c.execute('select * from process_approval_outbox where todo_id=%s and tenant_id=%s',
                                      (todo_id, tenant_id)).fetchone())

    def update_approval(self, row):
        with self._conn() as c:
            result = c.execute('''update process_approval_outbox set status=%s, attempts=%s,
                results=%s, error=%s, history=%s, updated_at=now() where todo_id=%s and tenant_id=%s''',
                (row['status'], row['attempts'], self._Jsonb(row['results']), row['error'],
                 self._Jsonb(row['history']), row['todo_id'], row['tenant_id']))
            if result.rowcount != 1:
                raise KeyError('no such approval')

    def list_approvals(self, proc_inst_id, tenant_id):
        with self._conn() as c:
            return [self._row(x) for x in c.execute('''select * from process_approval_outbox
                where proc_inst_id=%s and tenant_id=%s order by created_at,todo_id''',
                (proc_inst_id, tenant_id)).fetchall()]

    def pending_approvals(self, tenant_id, after_id=None, limit=100):
        with self._conn() as c:
            return [self._row(x) for x in c.execute('''select a.* from process_approval_outbox a
                join bpm_proc_inst i on i.proc_inst_id=a.proc_inst_id join todolist w on w.id=a.todo_id
                where a.tenant_id=%s and i.tenant_id=%s and w.tenant_id=%s
                and a.status='PENDING' and i.status='RUNNING' and not i.is_deleted and w.status='SUBMITTED'
                and (%s::uuid is null or a.todo_id>%s::uuid) order by a.todo_id limit %s''',
                (tenant_id, tenant_id, tenant_id, after_id, after_id, limit)).fetchall()]
