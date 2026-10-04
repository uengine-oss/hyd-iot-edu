"""Project only durably saved case sources; no command or approval replay."""
import json
import logging
from dataclasses import asdict
from .projection_receipt import digest,require

log=logging.getLogger('process.case_projection')

FENCE='''
MERGE (f:CaseProjection {id:$key}) SET f.lock=coalesce(f.lock,0)+1
WITH f WHERE coalesce(f.revision,0)<$revision OR (f.revision=$revision AND f.payload_hash=$payload_hash)
SET f.revision=$revision,f.payload_hash=$payload_hash
WITH f
'''

INCIDENT_Q=FENCE+'''
MERGE (i:Incident {id:$id})
SET i.alertId=$alert, i.openedAt=datetime($created), i.sourcePattern=$pattern,
    i.sourceTrip=$trip, i.sourceAlert=$source_alert, i.status=$status, i.reason=$reason,
    i.closedAt=CASE WHEN $closed IS NULL THEN null ELSE datetime($closed) END,
    i.cleared=$cleared, i.command_id=$command, i.work_order_ref=$work_order,
    i.projection_revision=$revision, i.projection_warnings=[]
WITH i
CALL (i) { OPTIONAL MATCH (i)-[old:ON_ASSET|RAISED_BY|DIAGNOSED_AS]->() DELETE old RETURN count(*) AS removed }
OPTIONAL MATCH (a:Asset {code:$asset})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (i)-[:ON_ASSET]->(a))
FOREACH (_ IN CASE WHEN a IS NULL THEN [1] ELSE [] END | SET i.projection_warnings=i.projection_warnings+['asset missing: '+coalesce($asset,'null')])
WITH i OPTIONAL MATCH (p:AnomalyPattern {code:$pattern})
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (i)-[:RAISED_BY]->(p))
FOREACH (_ IN CASE WHEN p IS NULL AND $pattern IS NOT NULL THEN [1] ELSE [] END | SET i.projection_warnings=i.projection_warnings+['pattern missing: '+$pattern])
WITH i OPTIONAL MATCH (c:Cause {id:$cause})
FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (i)-[:DIAGNOSED_AS]->(c))
FOREACH (_ IN CASE WHEN c IS NULL AND $cause IS NOT NULL THEN [1] ELSE [] END | SET i.projection_warnings=i.projection_warnings+['cause missing: '+$cause])
RETURN i.id AS id, i.projection_warnings AS warnings,$key AS projection_key,$revision AS projection_revision,$payload_hash AS projection_hash
'''

DECISION_CASE_Q=FENCE+'''
MERGE (x:DecisionCase {id:$id})
SET x.decidedAt=datetime($at),x.reason=$reason,x.followedRecommendation=$followed,
    x.status=$status,x.source_incident_id=$incident,x.projection_revision=$revision,x.projection_warnings=[]
WITH x
CALL (x) { OPTIONAL MATCH (x)-[old:INSTANCE_OF|CHOSE|DECIDED_BY|FOR_INCIDENT]->() DELETE old RETURN count(*) AS removed }
OPTIONAL MATCH (d:Decision {id:'dec:rank-actions'})
FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END | MERGE (x)-[:INSTANCE_OF]->(d))
FOREACH (_ IN CASE WHEN d IS NULL THEN [1] ELSE [] END | SET x.projection_warnings=x.projection_warnings+['decision model missing: dec:rank-actions'])
WITH x OPTIONAL MATCH (s:Skill {id:$skill})
FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END | MERGE (x)-[:CHOSE]->(s))
FOREACH (_ IN CASE WHEN s IS NULL THEN [1] ELSE [] END | SET x.projection_warnings=x.projection_warnings+['skill missing: '+coalesce($skill,'null')])
WITH x OPTIONAL MATCH (r:Role {id:$role})
FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (x)-[:DECIDED_BY]->(r))
FOREACH (_ IN CASE WHEN r IS NULL THEN [1] ELSE [] END | SET x.projection_warnings=x.projection_warnings+['role missing: '+coalesce($role,'null')])
WITH x OPTIONAL MATCH (i:Incident {id:$incident})
FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (x)-[:FOR_INCIDENT]->(i))
FOREACH (_ IN CASE WHEN i IS NULL AND $incident IS NOT NULL THEN [1] ELSE [] END |
    SET x.projection_warnings=x.projection_warnings+['incident source not projected: '+$incident])
RETURN x.id AS id,x.projection_warnings AS warnings, i IS NULL AND $incident IS NOT NULL AS dependency_pending,
       $key AS projection_key,$revision AS projection_revision,$payload_hash AS projection_hash
'''


def incident_params(inc):
    inc=asdict(inc) if not isinstance(inc,dict) else inc
    card=inc.get('card') or {};source=card.get('alert') or {}
    return {'id':inc['id'],'alert':inc['alert_id'],'created':inc['created'],'asset':inc['asset'],
            'pattern':source.get('pattern'),'cause':card.get('topCause'),
            'trip':(source.get('evidence') or {}).get('trip'),'source_alert':json.dumps(source,ensure_ascii=False),
            'status':inc['state'],'reason':inc.get('reason'),'closed':inc.get('closed'),
            'cleared':inc.get('cleared',False),'command':inc.get('cmd_id'),
            'work_order':json.dumps(inc.get('work_order'),ensure_ascii=False) if inc.get('work_order') else None}


class CaseProjector:
    def __init__(self,store,query,incident_projected=lambda sid:None):
        self.store,self.query,self.incident_projected=store,query,incident_projected

    def deliver(self,job):
        try:
            kind,sid,body=job['kind'],job['source_id'],job['body']
            common={'key':kind+':'+sid,'revision':job['revision'],'payload_hash':digest({'kind':kind,'body':body})}
            if body is None or (kind=='DecisionCase' and (body.get('state') not in ('APPROVED','EXECUTED','PARTIAL') or not body.get('chosen'))):
                # Kind comes from our own queue constructor, never request text.
                if kind not in ('Incident','DecisionCase'):raise ValueError('unknown source kind')
                rows=self.query(FENCE+f'OPTIONAL MATCH (n:{kind} {{id:$id}}) DETACH DELETE n RETURN $key AS projection_key,$revision AS projection_revision,$payload_hash AS projection_hash',
                           **common,id=sid if kind=='Incident' else 'case:'+sid)
            elif kind=='Incident':
                rows=self.query(INCIDENT_Q,**common,**incident_params(body))
            elif kind=='DecisionCase':
                at=next((h['t'] for h in reversed(body.get('history') or []) if h.get('state')=='APPROVED'),body['created'])
                rows=self.query(DECISION_CASE_Q,**common,id='case:'+sid,at=at,reason=body.get('reason') or '',
                    followed=not body.get('override'),skill=body['chosen'],role=body.get('approvedRole'),
                    incident=(body.get('origin') or {}).get('incident'),status=body['state'])
                if any(r.get('dependency_pending') for r in rows):
                    raise RuntimeError('incident source not projected; graph relationship repair pending')
            else:raise ValueError('unknown source kind')
            require(rows,common['key'],common['revision'],common['payload_hash'])
            if kind=='Incident':self.incident_projected(sid)
            self.store.finish_case_projection(job)
            return True
        except Exception as exc:
            try:self.store.finish_case_projection(job,f'{type(exc).__name__}: {str(exc)[:1000]}')
            except Exception:log.exception('case projection receipt failed; intent stays pending')
            log.warning('case graph pending %s/%s: %s',job['kind'],job['source_id'],exc)
            return False

    def drain(self,limit=20):
        return sum(self.deliver(job) for job in self.store.case_projection_batch(limit))
