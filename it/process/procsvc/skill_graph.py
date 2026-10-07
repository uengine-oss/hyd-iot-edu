"""Atomic knowledge authoring with optimistic review and durable request receipts."""
from copy import deepcopy
import hashlib
import json
import uuid
from . import manual_graph


class Conflict(ValueError):
    pass


def canonical(value):
    if isinstance(value,dict):return {k:canonical(v) for k,v in sorted(value.items())}
    if isinstance(value,list):return [canonical(v) for v in value]
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(canonical(value),ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def stamp(rows):
    result=[]
    for row in rows:
        basis={k:v for k,v in row.items() if k!='revision'}
        # Collection order is unspecified for relationships; action/step order
        # is meaningful and must never be erased from the review identity.
        for key in ('failureModes','causes','rules','affects','performers'):
            if key in basis:
                basis[key]=sorted(basis[key],key=lambda v:json.dumps(canonical(v),ensure_ascii=False,sort_keys=True))
        result.append(dict(row,revision=fingerprint(basis)))
    return result


CANDIDATE_RULES_Q = (
    "MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]->(r:Rule)-[t:TESTS]->(i:InputData) "
    "WITH r, collect({input:i.id, operator:t.operator, value:t.value}) AS tests "
    "WHERE size(tests)=1 AND tests[0].input='in:failure-mode' AND tests[0].operator='==' AND tests[0].value=$fm "
    "RETURN r.id AS id ORDER BY r.id")


def candidate_rules(tx, failure_mode):
    """dec:action-candidates rules that select by this failure mode alone (rules with extra tests such as plc_state are not
    widened). These are the rules whose OUTPUTS a skill must join to be judged at runtime."""
    return [row['id'] for row in tx.run(CANDIDATE_RULES_Q, fm=failure_mode).data()]


def link_candidate_rules(tx, sid, failure_mode):
    """A075 (meeting L253~302, L301): a skill matched to a failure mode joins that failure mode's candidate rules (OUTPUTS),
    so the DMN judgment (dec:action-candidates → compliance → rank) can offer it. Idempotent; returns the rule ids."""
    rules = candidate_rules(tx, failure_mode)
    for rule in rules:
        tx.run('MATCH (r:Rule {id:$rule}),(k:Skill {id:$id}) MERGE (r)-[:OUTPUTS]->(k)', rule=rule, id=sid).consume()
    return rules


def write(session, query, sid, values, *, create=False, expected_revision=None, request_id=None, by='지식 관리자'):
    """The receipt, properties, steps and all relationships commit together.

    Manual-owned skills must be revised through their source review, preserving
    provenance and rollback ownership. Creating an existing SOP never replaces it.
    """
    if request_id is not None and not isinstance(request_id,str):raise ValueError('request_id는 UUID 문자열이어야 합니다')
    rid=str(uuid.UUID(request_id)) if request_id is not None else str(uuid.uuid4())
    intent={'skill':sid,'values':deepcopy(values),'create':create,'revision':expected_revision,'by':by}
    digest=fingerprint(intent)
    manual_graph.ensure_schema(session)
    session.run('CREATE CONSTRAINT knowledge_edit_id IF NOT EXISTS FOR (r:KnowledgeEdit) REQUIRE r.id IS UNIQUE').consume()

    def run(tx):
        manual_graph._lock(tx)
        receipt=tx.run('MATCH (r:KnowledgeEdit {id:$id}) RETURN r.fingerprint AS fingerprint,r.result AS result',id=rid).single()
        if receipt:
            if receipt['fingerprint']!=digest:raise Conflict('같은 요청 ID에 다른 지식 변경을 사용할 수 없습니다')
            return json.loads(receipt['result'])
        tx.run('MATCH (k:Skill {id:$id}) SET k.id=k.id',id=sid).consume()
        current=stamp(tx.run(query,id=sid).data())
        if create:
            if current or tx.run('MATCH (k:Skill {sopId:$sop}) RETURN k.id AS id',sop=values['sopId']).single():
                raise Conflict('이 SOP 또는 스킬이 이미 존재합니다. 기존 원문을 덮어쓰지 않았습니다')
        else:
            if not current:raise KeyError('no such skill')
            if len(current)!=1:raise Conflict('스킬의 승인 관계가 중복되어 먼저 정합성 검토가 필요합니다')
            if current[0].get('source_document'):
                raise Conflict('원문에서 적재한 스킬입니다. 해당 문서의 개정·검토 경로에서 수정하세요')
            if not expected_revision:raise ValueError('조회한 스킬의 revision이 필요합니다. 현재 지식을 다시 확인하세요')
            if expected_revision!=current[0]['revision']:raise Conflict('조회 후 지식이 변경됐습니다. 현재 내용을 다시 검토하세요')
        role=values.get('approver') or ('role:maint-mgr' if create else None)
        if role:
            target=tx.run('MATCH (r:Role {id:$id}) SET r.id=r.id RETURN r.id AS id',id=role).data()
            if len(target)!=1:raise ValueError('승인 역할이 없거나 중복되어 변경하지 않았습니다')
        if create:
            performer='sys:scada' if values['kind']=='control' else 'sys:cmms'
            for label,nid in [('FailureMode',values['failureMode']),('System',performer)]:
                target=tx.run(f'MATCH (n:{label} {{id:$id}}) SET n.id=n.id RETURN n.id AS id',id=nid).data()
                if len(target)!=1:raise ValueError(f'{label} 대상이 없거나 중복되어 생성하지 않았습니다')
            step_ids=[sid+'/step/'+str(i) for i in range(1,len(values['steps'])+1)]
            if tx.run('MATCH (n:Step) WHERE n.id IN $ids RETURN n.id AS id LIMIT 1',ids=step_ids).single():
                raise Conflict('기존 단계 ID와 충돌합니다. 다른 지식의 단계를 교체하지 않았습니다')
            tx.run('CREATE (k:Skill {id:$id,sopId:$sop,kind:$kind})',id=sid,sop=values['sopId'],kind=values['kind']).consume()
            for i,text in enumerate(values['steps'],1):
                tx.run('MATCH (k:Skill {id:$id}) CREATE (s:Step {id:$sid,order:$order,text:$text}) CREATE (k)-[:HAS_STEP]->(s)',id=sid,sid=step_ids[i-1],order=i,text=text).consume()
            rel=values['relation']
            if rel not in {'MITIGATED_BY','REMEDIED_BY'}:raise ValueError('unsupported failure relation')
            tx.run(f'MATCH (f:FailureMode {{id:$fm}}),(k:Skill {{id:$id}}),(s:System {{id:$performer}}) CREATE (f)-[:{rel}]->(k) CREATE (s)-[:HAS_SKILL]->(k)',fm=values['failureMode'],id=sid,performer=performer).consume()
        elif values.get('failureMode'):
            rel=values.get('relation') or 'REMEDIED_BY'
            if rel not in {'MITIGATED_BY','REMEDIED_BY'}:raise ValueError('unsupported failure relation')
            target=tx.run('MATCH (n:FailureMode {id:$id}) SET n.id=n.id RETURN n.id AS id',id=values['failureMode']).data()
            if len(target)!=1:raise ValueError('FailureMode 대상이 없거나 중복되어 변경하지 않았습니다')
            tx.run('MATCH (:FailureMode)-[old:MITIGATED_BY|REMEDIED_BY]->(k:Skill {id:$id}) DELETE old',id=sid).consume()
            tx.run('MATCH (r:Rule)-[old:OUTPUTS]->(k:Skill {id:$id}) WHERE r.id STARTS WITH "rule:cand-" DELETE old',id=sid).consume()
            tx.run(f'MATCH (f:FailureMode {{id:$fm}}),(k:Skill {{id:$id}}) CREATE (f)-[:{rel}]->(k)',fm=values['failureMode'],id=sid).consume()
        if values.get('failureMode'):
            link_candidate_rules(tx,sid,values['failureMode'])
        tx.run('MATCH (k:Skill {id:$id}) SET k.name=$name,k.description=$description',id=sid,name=values['name'],description=values['description']).consume()
        if role:
            tx.run('MATCH (k:Skill {id:$id})-[old:APPROVED_BY]->() DELETE old',id=sid).consume()
            tx.run('MATCH (k:Skill {id:$id}),(r:Role {id:$role}) CREATE (k)-[:APPROVED_BY]->(r)',id=sid,role=role).consume()
        result=stamp(tx.run(query,id=sid).data())[0]
        tx.run('CREATE (r:KnowledgeEdit {id:$id,skill:$skill,fingerprint:$fingerprint,actor:$actor,created_at:datetime(),before:$before,result:$result})',
               id=rid,skill=sid,fingerprint=digest,actor=by,before=json.dumps(current,ensure_ascii=False),result=json.dumps(result,ensure_ascii=False)).consume()
        return result
    return session.execute_write(run)
