"""Durable effect receipts (compensation deliveries and human acknowledgements), replayed by request id (A072).

Same connection/rollback scope as the process rows; mutations run under the owning instance transition lock.
"""
from copy import deepcopy
from datetime import datetime, timezone

MUTABLE = ("status", "results", "error", "history")


class MemoryEffects:
    def insert_effect_receipt(self, row):
        key = (row["tenant_id"], row["proc_inst_id"], row["request_id"])
        with self._lock:
            inst = self.instances.get(row["proc_inst_id"])
            if not inst or inst["tenant_id"] != row["tenant_id"]:
                raise ValueError("effect receipt ownership mismatch")
            if key in self.effect_receipts:
                raise ValueError("effect receipt request already exists")
            stored = deepcopy(row)
            stored["created_at"] = stored["updated_at"] = datetime.now(timezone.utc).isoformat()   # as the PG table stamps
            self.effect_receipts[key] = stored

    def update_effect_receipt(self, row):
        key = (row["tenant_id"], row["proc_inst_id"], row["request_id"])
        with self._lock:
            prior = self.effect_receipts.get(key)
            if prior is None:
                raise KeyError("no such effect receipt")
            for k in MUTABLE:
                prior[k] = deepcopy(row[k])
            prior["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_effect_receipt(self, tenant_id, proc_inst_id, request_id):
        with self._lock:
            return deepcopy(self.effect_receipts.get((tenant_id, proc_inst_id, request_id)))

    def list_effect_receipts(self, tenant_id, proc_inst_id):
        with self._lock:   # insertion order == creation order, as the PG table orders by created_at
            return [deepcopy(r) for key, r in self.effect_receipts.items() if key[:2] == (tenant_id, proc_inst_id)]


class PgEffects:
    def insert_effect_receipt(self, row):
        with self._conn() as c:
            result = c.execute('''insert into process_effect_receipt
                (tenant_id,proc_inst_id,request_id,kind,status,request,effects,results,error,history)
                select %s,%s,%s,%s,%s,%s,%s,%s,%s,%s where exists
                (select 1 from bpm_proc_inst where tenant_id=%s and proc_inst_id=%s)''',
                (row["tenant_id"], row["proc_inst_id"], row["request_id"], row["kind"], row["status"],
                 self._Jsonb(row["request"]), self._Jsonb(row["effects"]), self._Jsonb(row["results"]), row.get("error"),
                 self._Jsonb(row["history"]), row["tenant_id"], row["proc_inst_id"]))
            if result.rowcount != 1:
                raise ValueError("effect receipt ownership mismatch")

    def update_effect_receipt(self, row):
        with self._conn() as c:
            result = c.execute('''update process_effect_receipt set status=%s, results=%s, error=%s, history=%s, updated_at=now()
                where tenant_id=%s and proc_inst_id=%s and request_id=%s''',
                (row["status"], self._Jsonb(row["results"]), row.get("error"), self._Jsonb(row["history"]),
                 row["tenant_id"], row["proc_inst_id"], row["request_id"]))
            if result.rowcount != 1:
                raise KeyError("no such effect receipt")

    def get_effect_receipt(self, tenant_id, proc_inst_id, request_id):
        with self._conn() as c:
            return self._row(c.execute('''select * from process_effect_receipt
                where tenant_id=%s and proc_inst_id=%s and request_id=%s''', (tenant_id, proc_inst_id, request_id)).fetchone())

    def list_effect_receipts(self, tenant_id, proc_inst_id):
        with self._conn() as c:
            return [self._row(r) for r in c.execute('''select * from process_effect_receipt
                where tenant_id=%s and proc_inst_id=%s order by created_at, request_id''', (tenant_id, proc_inst_id)).fetchall()]
