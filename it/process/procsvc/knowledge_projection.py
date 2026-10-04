"""Reconcile graph joins after knowledge changes without replaying business work.

The inventory covers lookup keys used by case/execution projections, including
physical node identity and Process/HAS_NODE membership. Projection-owned nodes
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
UNION ALL
MATCH (p:Process)-[r:HAS_NODE]->(n:FlowNode)
RETURN 'membership' AS kind,elementId(r) AS identity,n.id AS id,null AS code,
       [] AS labels,elementId(p) AS source,elementId(n) AS target
'''


def digest(rows):
    rows=[dict(r,labels=sorted(r.get('labels') or [])) for r in rows]
    encoded=sorted(json.dumps(row,sort_keys=True,separators=(',',':')) for row in rows)
    return hashlib.sha256(json.dumps(encoded).encode()).hexdigest()


class KnowledgeReconciler:
    def __init__(self,store,query,tenant,repo=None,interval=15):
        self.store,self.query,self.tenant,self.repo=store,query,tenant,repo
        self.key=tenant+(':instance' if repo is not None else ':legacy')
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
            if self.repo is not None:self.repo.enqueue_knowledge_projections(self.tenant)
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
