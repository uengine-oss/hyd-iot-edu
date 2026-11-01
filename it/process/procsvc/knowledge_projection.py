"""Reconcile graph joins after knowledge changes without replaying business work.

The inventory covers lookup keys used by case/execution projections, including
physical node identity (Asset · AnomalyPattern · Cause · Decision · Skill · Role · System · Process). Projection-owned nodes
are excluded so reconciliation cannot trigger itself forever. This is eventual
join repair, not a new diagnosis, approval, or graph-backup recovery protocol.
"""
import hashlib
import json
import logging
import time

log=logging.getLogger('process.knowledge_projection')
INVENTORY_Q='''
MATCH (n) WHERE n:Asset OR n:AnomalyPattern OR n:Cause OR n:Decision OR n:Skill OR n:Role OR n:System OR n:Process
RETURN 'node' AS kind, elementId(n) AS identity, n.id AS id,n.code AS code,
       [label IN labels(n) WHERE label IN ['Asset','AnomalyPattern','Cause','Decision','Skill','Role','System','Process']] AS labels,
       null AS source,null AS target
'''


def digest(rows):
    rows=[dict(r,labels=sorted(r.get('labels') or [])) for r in rows]
    encoded=sorted(json.dumps(row,sort_keys=True,separators=(',',':')) for row in rows)
    return hashlib.sha256(json.dumps(encoded).encode()).hexdigest()


class KnowledgeReconciler:
    def __init__(self,store,query,tenant,repo,interval=15):
        # repo = 처리 건 저장소(PgRepo — 실행 그래프 반영 대기열). key 는 SQLite 검사점 이름이라 저장된 값과 같게 둔다
        self.store,self.query,self.tenant,self.repo=store,query,tenant,repo
        self.key=tenant+':instance'
        self.interval=interval;self.next_check=0;self.last_checked=None;self.last_error=None;self.observed=None

    def status(self):
        return dict(last_checked=self.last_checked,last_error=self.last_error,observed_digest=self.observed,
                    queued=self.store.knowledge_projection_checkpoint(self.key))

    def scan(self):
        """PG enqueue first; SQLite intents and checkpoint then commit together.

        A crash between stores repeats PG enqueue after restart. Duplicate jobs
        are safe; advancing the checkpoint before both queues would lose work.
        """
        self.last_checked=time.time()
        try:
            self.observed=digest(self.query(INVENTORY_Q))
            old=self.store.knowledge_projection_checkpoint(self.key)
            if old and old['digest']==self.observed:
                self.last_error=None
                return False
            self.repo.enqueue_knowledge_projections(self.tenant)
            self.store.enqueue_knowledge_cases(self.key,self.observed)
            self.last_error=None
            return True
        except Exception as error:
            self.last_error=f'{type(error).__name__}: {str(error)[:1000]}'
            log.warning('knowledge join reconciliation pending: %s',self.last_error)
            return False

    def poll(self):
        now=time.monotonic()
        if now<self.next_check:return False
        self.next_check=now+self.interval
        return self.scan()
