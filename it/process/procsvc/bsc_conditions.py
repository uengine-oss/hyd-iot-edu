"""Atomic, review-bound interpretation of an existing BSC relationship condition."""
import json
import uuid
from hydcommon import bsc, ranking
from .skill_graph import Conflict

MATCH = 'MATCH (a)-[r]->(b) WHERE type(r) IN ["AFFECTS","INFLUENCES"] '
RETURN = ('RETURN elementId(r) AS key,type(r) AS type,a.id AS source,b.id AS target,'
          'properties(r) AS properties,a.source_document AS source_document,b.source_document AS target_document')


def view(row):
    result=dict(row,revision=ranking.fingerprint(row),policy=None)
    raw=row['properties'].get('conditionPolicy')
    if raw is not None:
        try: result['policy']=bsc.validate_policy(raw)
        except ValueError as exc: result['error']=str(exc)
    return result


def read(session, key=None):
    query=MATCH+('AND elementId(r)=$key ' if key is not None else '')+RETURN+' ORDER BY key'
    rows=session.run(query,key=key).data()
    if key is not None:
        if len(rows)!=1: raise KeyError('BSC relationship no longer exists')
        return view(rows[0])
    return [view(row) for row in rows]


def write(session,key,body):
    if set(body)!={'policy','expected_revision','request_id','by','reason'}:
        raise ValueError('policy, expected_revision, request_id, by and reason are required')
    policy=None if body['policy'] is None else bsc.validate_policy(body['policy'])
    for name in ('expected_revision','request_id','by','reason'):
        if not isinstance(body[name],str) or not body[name].strip() or len(body[name])>2000:
            raise ValueError(name+' must be a nonempty string (up to2000 characters)')
    rid=str(uuid.UUID(body['request_id']))
    digest=ranking.fingerprint(dict(body,policy=policy,edge=key))
    session.run('CREATE CONSTRAINT knowledge_edit_id IF NOT EXISTS FOR (r:KnowledgeEdit) REQUIRE r.id IS UNIQUE').consume()
    def run(tx):
        rows=tx.run(MATCH+'AND elementId(r)=$key SET a.id=a.id,b.id=b.id,r.sign=r.sign '+RETURN,key=key).data()
        if len(rows)!=1: raise KeyError('BSC relationship no longer exists')
        receipt=tx.run('MATCH (e:KnowledgeEdit {id:$id}) RETURN e.fingerprint AS fingerprint,e.result AS result',id=rid).single()
        if receipt:
            if receipt['fingerprint']!=digest: raise Conflict('request_id already names another edit')
            return json.loads(receipt['result'])
        before=view(rows[0]); props=before['properties']
        if before['revision']!=body['expected_revision']: raise Conflict('BSC relationship changed after review')
        if before['source_document'] or before['target_document'] or props.get('source_document') or props.get('_ingest_batches'):
            raise Conflict('source-owned BSC relationship requires its source review')
        if policy is not None:
            if policy['description']!=(props.get('condition') or ''):
                raise ValueError('policy description must match the reviewed condition text exactly')
            for source in policy['inputs'].values():
                query='MATCH (i:InputData {variable:$variable}) RETURN i.id AS id' if source['source']=='fact' else 'MATCH (i:StateVariable {id:$variable}) RETURN i.id AS id'
                if len(tx.run(query,variable=source['variable']).data())!=1:
                    raise ValueError('BSC condition input is missing or ambiguous: '+source['variable'])
        tx.run(MATCH+'AND elementId(r)=$key SET r.conditionPolicy=$policy',key=key,
               policy=ranking.canonical(policy) if policy is not None else None).consume()
        result=view(tx.run(MATCH+'AND elementId(r)=$key '+RETURN,key=key).data()[0])
        tx.run('CREATE (e:KnowledgeEdit {id:$id,kind:"bsc_condition",edge:$edge,fingerprint:$fingerprint,'
            'actor:$actor,reason:$reason,created_at:datetime(),before:$before,result:$result})',
            id=rid,edge=key,fingerprint=digest,actor=body['by'],reason=body['reason'],
            before=ranking.canonical(before),result=ranking.canonical(result)).consume()
        return result
    return session.execute_write(run)
