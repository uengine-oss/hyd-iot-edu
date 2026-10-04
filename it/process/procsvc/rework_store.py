"""Immutable request/result receipts, committed with the owning generation."""
from copy import deepcopy


class MemoryReworks:
    def get_rework(self, tenant_id, proc_inst_id, request_id):
        with self._lock:
            return deepcopy(self.reworks.get((tenant_id, proc_inst_id, request_id)))

    def list_reworks(self, tenant_id, proc_inst_id):
        with self._lock:
            return sorted((deepcopy(r) for key, r in self.reworks.items() if key[:2] == (tenant_id, proc_inst_id)),
                          key=lambda r: r['generation'])

    def insert_rework(self, row):
        key = (row['tenant_id'], row['proc_inst_id'], row['request_id'])
        with self._lock:
            inst = self.instances.get(row['proc_inst_id'])
            if not inst or inst['tenant_id'] != row['tenant_id']:
                raise ValueError('rework ownership mismatch')
            if key in self.reworks or any(r['generation'] == row['generation'] for r in self.list_reworks(*key[:2])):
                raise ValueError('rework request or generation already exists')
            self.reworks[key] = deepcopy(row)


class PgReworks:
    def get_rework(self, tenant_id, proc_inst_id, request_id):
        with self._conn() as c:
            return self._row(c.execute('''select * from process_rework_receipt
                where tenant_id=%s and proc_inst_id=%s and request_id=%s''',
                (tenant_id, proc_inst_id, request_id)).fetchone())

    def list_reworks(self, tenant_id, proc_inst_id):
        with self._conn() as c:
            return [self._row(r) for r in c.execute('''select * from process_rework_receipt
                where tenant_id=%s and proc_inst_id=%s order by generation''', (tenant_id, proc_inst_id)).fetchall()]

    def insert_rework(self, row):
        with self._conn() as c:
            result = c.execute('''insert into process_rework_receipt
                (tenant_id,proc_inst_id,request_id,generation,request,result)
                select %s,%s,%s,%s,%s,%s where exists
                (select 1 from bpm_proc_inst where tenant_id=%s and proc_inst_id=%s)''',
                (row['tenant_id'], row['proc_inst_id'], row['request_id'], row['generation'],
                 self._Jsonb(row['request']), self._Jsonb(row['result']), row['tenant_id'], row['proc_inst_id']))
            if result.rowcount != 1:
                raise ValueError('rework ownership mismatch')
