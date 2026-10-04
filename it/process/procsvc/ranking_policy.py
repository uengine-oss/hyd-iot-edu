"""Review-bound graph policy edits with atomic, replayable KnowledgeEdit receipts."""
import json
import uuid

from hydcommon import ranking
from .skill_graph import Conflict


def view(props):
    raw = props.get('rankingPolicy')
    result = {'rule':props['id'], 'annotation':props.get('annotation'), 'policy':None,
              'revision':ranking.fingerprint({'rule':props['id'], 'policy':raw, 'annotation':props.get('annotation')})}
    try:
        result['policy'] = ranking.validate(raw)
        result['policy_sha256'] = ranking.fingerprint(result['policy'])
    except ValueError as exc:
        result['error'] = str(exc)
    return result


QUERY = ('MATCH (:Decision {id:"dec:rank-actions"})-[:IMPLEMENTED_BY]->(:DecisionTable)-[:HAS_RULE]->'
         '(r:Rule {id:$id}) RETURN properties(r) AS p')


def read(session, rule):
    rows=session.run(QUERY,id=rule).data()
    if not rows: raise KeyError('ranking rule does not exist')
    if len(rows)!=1: raise Conflict('ranking rule is ambiguous')
    return view(rows[0]['p'])


def write(session, rule, body):
    if set(body) != {'policy','expected_revision','request_id','annotation','reason','by'}:
        raise ValueError('policy, expected_revision, request_id, annotation, reason and by are required')
    policy=ranking.validate(body.get('policy'))
    revision=body.get('expected_revision')
    if not isinstance(revision,str) or not revision:
        raise ValueError('expected_revision from the current policy is required')
    for key in ('annotation','reason','by'):
        if not isinstance(body.get(key),str) or not body[key].strip() or len(body[key])>2000:
            raise ValueError(f'{key} is required (up to2000 characters)')
    if not isinstance(body['request_id'],str): raise ValueError('request_id must be a UUID string')
    rid=str(uuid.UUID(body['request_id']))
    intent={'rule':rule,'policy':policy,'expected_revision':revision,
            **{k:body[k] for k in ('annotation','reason','by')}}
    digest=ranking.fingerprint(intent)
    session.run('CREATE CONSTRAINT knowledge_edit_id IF NOT EXISTS FOR (r:KnowledgeEdit) REQUIRE r.id IS UNIQUE').consume()
    def run(tx):
        # Serialize matching requests and preserve the same response after retries.
        tx.run('MATCH (r:Rule {id:$id}) SET r.id=r.id',id=rule).consume()
        receipt=tx.run('MATCH (e:KnowledgeEdit {id:$id}) RETURN e.fingerprint AS fingerprint,e.result AS result',id=rid).single()
        if receipt:
            if receipt['fingerprint']!=digest: raise Conflict('request_id already names a different change')
            return json.loads(receipt['result'])
        rows=tx.run(QUERY,id=rule).data()
        if not rows: raise KeyError('ranking rule does not exist')
        if len(rows)!=1: raise Conflict('ranking rule is ambiguous')
        props=rows[0]['p']; before=view(props)
        if props.get('source_document') or props.get('_ingest_batches'):
            raise Conflict('source-owned rule must be changed through its source review')
        if before['revision']!=revision: raise Conflict('ranking policy changed after review')
        for variable in set(policy['inputs'].values()):
            matches=tx.run('MATCH (i:InputData {variable:$variable}) RETURN i.id AS id',variable=variable).data()
            if len(matches)!=1: raise ValueError('policy input requires exactly one declared InputData: '+variable)
        rows=tx.run('MATCH (r:Rule {id:$id}) SET r.rankingPolicy=$policy,r.annotation=$annotation RETURN properties(r) AS p',
            id=rule,policy=ranking.canonical(policy),annotation=body['annotation']).data()
        result=view(rows[0]['p'])
        tx.run('CREATE (e:KnowledgeEdit {id:$id,kind:"ranking_policy",rule:$rule,fingerprint:$fingerprint,'
            'actor:$actor,reason:$reason,created_at:datetime(),before:$before,result:$result})',
            id=rid,rule=rule,fingerprint=digest,actor=body['by'],reason=body['reason'],
            before=ranking.canonical(before),result=ranking.canonical(result)).consume()
        return result
    return session.execute_write(run)
