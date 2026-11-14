"""Atomic knowledge authoring with optimistic review and durable request receipts."""
from copy import deepcopy
import hashlib
import json
import uuid
from . import kgadmin, manual_graph


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


def failure_mode_rule_id(failure_mode):
    """화면에서 연결한 조치 방법을 후보로 내는 규칙의 id — 고장 유형마다 하나(rule:cand-<고장 유형>)."""
    return 'rule:cand-' + failure_mode.split(':', 1)[-1]


def ensure_candidate_rule(tx, failure_mode):
    """이 고장 유형만으로 고르는 후보 규칙이 없으면 하나 만든다(있으면 그대로). 조치 방법 화면에서 고장 유형에 연결한 조치 방법은 이 규칙의
    결과로 판단 후보가 된다 — 「이 고장 유형에 쓸 수 있는 조치 방법은 무엇인가」(dec:action-candidates 의 물음) 그대로다. 수업 지식의 후보 규칙은
    문서가 경보 · 원인 조건으로 진술한 것뿐이라, 이 규칙이 없으면 화면에서 만든 조치 방법은 저장만 되고 어느 판단에도 나오지 않았다.
    모양은 시드 · 문서 적재의 규칙과 같다: 결정표의 한 행, when 은 TESTS 를 그대로 적은 글(시드 검사 seed_checks 가 대조한다)."""
    if candidate_rules(tx, failure_mode):
        return
    made = tx.run(
        "MATCH (t:DecisionTable {id:'dt:action-candidates'}), (i:InputData {id:'in:failure-mode'}), (f:FailureMode {id:$fm}) "
        "OPTIONAL MATCH (t)-[:HAS_RULE]->(other:Rule) WITH t, i, f, coalesce(max(other.order), 0) + 1 AS ord "
        "CREATE (r:Rule {id:$id, order:ord, effect:'SELECT', `when`:i.variable + ' == ' + \"'\" + $fm + \"'\", "
        "annotation:'「' + coalesce(f.name, $fm) + '」(으)로 판정되면 조치 방법 화면에서 이 고장 유형에 연결한 조치 방법을 후보로 낸다'}) "
        "CREATE (t)-[:HAS_RULE]->(r) CREATE (r)-[:TESTS {operator:'==', value:$fm}]->(i) RETURN r.id AS id",
        id=failure_mode_rule_id(failure_mode), fm=failure_mode).data()
    if len(made) != 1:
        raise ValueError('조치 후보 결정표(dt:action-candidates)나 고장 유형 입력(in:failure-mode)이 지식에 없어 후보 규칙을 만들지 못했습니다 — 저장하지 않았습니다')


def link_candidate_rules(tx, sid, failure_mode):
    """A075 (meeting L253~302, L301): a skill matched to a failure mode joins that failure mode's candidate rules (OUTPUTS),
    so the DMN judgment (dec:action-candidates → compliance → rank) can offer it. Idempotent; returns the rule ids."""
    rules = candidate_rules(tx, failure_mode)
    for rule in rules:
        tx.run('MATCH (r:Rule {id:$rule}),(k:Skill {id:$id}) MERGE (r)-[:OUTPUTS]->(k)', rule=rule, id=sid).consume()
    return rules


def _relation_refused(rel):
    return f"고장 유형과 조치 방법의 관계 '{rel}' 은(는) 쓸 수 없습니다 — 근본 조치 · 즉시 완화 · 예방 조치 가운데 고르세요"


def write(session, query, sid, values, *, create=False, expected_revision=None, request_id=None, by):
    """The receipt, properties, steps and all relationships commit together.

    Manual-owned skills must be revised through their source review, preserving
    provenance and rollback ownership. Creating an existing SOP never replaces it.
    """
    if values.get('scope') == 'purchase':
        raise ValueError('원문 구매 SOP는 원문·인용·업무 범위를 검증하는 매뉴얼 검토/개정 경로에서만 변경합니다')
    if request_id is not None and not isinstance(request_id,str):raise ValueError('request_id는 UUID 문자열이어야 합니다')
    rid=str(uuid.UUID(request_id)) if request_id is not None else str(uuid.uuid4())
    intent={'skill':sid,'values':deepcopy(values),'create':create,'revision':expected_revision,'by':by}
    digest=fingerprint(intent)
    manual_graph.ensure_schema(session)     # 영수증(KnowledgeEdit.id) 유일 제약은 그래프 적재 때 한 곳(it/neo4j/v2/constraints.cypher)

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
            if not current:raise KeyError(sid)
            if len(current)!=1:raise Conflict('스킬의 승인 관계가 중복되어 먼저 정합성 검토가 필요합니다')
            if current[0].get('source_document'):
                raise Conflict('원문에서 적재한 스킬입니다. 해당 문서의 개정·검토 경로에서 수정하세요')
            if not expected_revision:raise ValueError('조회한 스킬의 revision이 필요합니다. 현재 지식을 다시 확인하세요')
            if expected_revision!=current[0]['revision']:raise Conflict('조회 후 지식이 변경됐습니다. 현재 내용을 다시 검토하세요')
        role=values.get('approver')
        if create and not role:
            # 승인 역할을 서버가 지어 넣지 않는다(전에는 비면 설비보전팀장) — 사람이 고르지 않은 역할이 그 조치의 승인 카드에 나왔다
            raise ValueError('승인 역할을 고르세요 — 새 조치 방법은 누가 승인하는지 정해야 합니다')
        if role:
            target=tx.run('MATCH (r:Role {id:$id}) SET r.id=r.id RETURN r.id AS id',id=role).data()
            if len(target)!=1:raise ValueError('승인 역할이 없거나 중복되어 변경하지 않았습니다')
        if create:
            if values['kind']=='control':
                # 설비 명령 조치는 어떤 명령을 어떤 값으로 내는지(원자 조치)가 있어야 실행된다. 이 화면은 그 칸이 없어, 만들어도 승인 뒤 「실행할 조치
                # 없음」으로 끝났다 — 저장을 받지 않고 길을 말한다.
                raise ValueError('설비 명령 조치 방법은 이 화면에서 만들 수 없습니다 — 어떤 명령을 어떤 값으로 낼지(팬 속도 · 부하 등)는 원문 절차에서 '
                                 '정하므로 [문서 등록]으로 넣으세요. 이 화면에서는 작업지시 조치 방법을 만듭니다')
            performer='sys:cmms'
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
            if rel not in kgadmin.FAILURE_RELATIONS:raise ValueError(_relation_refused(rel))
            tx.run(f'MATCH (f:FailureMode {{id:$fm}}),(k:Skill {{id:$id}}),(s:System {{id:$performer}}) CREATE (f)-[:{rel}]->(k) CREATE (s)-[:HAS_SKILL]->(k)',fm=values['failureMode'],id=sid,performer=performer).consume()
            # 작업지시 조치 방법의 원자 조치: 이 SOP 로 정비 작업지시를 낸다(문서에서 온 작업지시 조치와 같은 모양 — CONSISTS_OF {value: SOP 번호}).
            # 없으면 승인 뒤 흐름이 이 SOP 가 아니라 「선택한 조치 이후 정비 점검」이라는 일반 오더를 냈다.
            if len(tx.run("MATCH (k:Skill {id:$id}),(a:Action {code:'WO_CREATE'}) CREATE (k)-[:CONSISTS_OF {seq:1,value:$sop}]->(a) RETURN a.id AS id",
                          id=sid,sop=values['sopId']).data())!=1:
                raise ValueError('정비 작업지시 동작(WO_CREATE)이 지식에 없거나 중복되어 생성하지 않았습니다')
        elif values.get('failureMode'):
            rel=values.get('relation') or 'REMEDIED_BY'
            if rel not in kgadmin.FAILURE_RELATIONS:raise ValueError(_relation_refused(rel))
            target=tx.run('MATCH (n:FailureMode {id:$id}) SET n.id=n.id RETURN n.id AS id',id=values['failureMode']).data()
            if len(target)!=1:raise ValueError('FailureMode 대상이 없거나 중복되어 변경하지 않았습니다')
            tx.run('MATCH (:FailureMode)-[old:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY]->(k:Skill {id:$id}) DELETE old',id=sid).consume()
            tx.run('MATCH (r:Rule)-[old:OUTPUTS]->(k:Skill {id:$id}) WHERE r.id STARTS WITH "rule:cand-" DELETE old',id=sid).consume()
            tx.run(f'MATCH (f:FailureMode {{id:$fm}}),(k:Skill {{id:$id}}) CREATE (f)-[:{rel}]->(k)',fm=values['failureMode'],id=sid).consume()
        # 예방 조치(PREVENTED_BY, 정기 정비) 스킬은 경보 대응 후보 규칙에 합류시키지 않는다 — 정기 정비 도래 후보는 문서의 규칙이 정한다
        if values.get('failureMode') and (values.get('relation') or 'REMEDIED_BY') in kgadmin.CORRECTIVE_RELATIONS:
            ensure_candidate_rule(tx,values['failureMode'])
            link_candidate_rules(tx,sid,values['failureMode'])
        tx.run('MATCH (k:Skill {id:$id}) SET k.name=$name,k.description=$description',id=sid,name=values['name'],description=values['description']).consume()
        if values.get('affects') is not None:
            # A098: the admin's impact links replace the skill's admin-owned AFFECTS edges; manual-owned ones (review commit,
            # _manual_document) stay with their batch. Every target must exist as a StateVariable or Measure.
            for a in values['affects']:
                if not tx.run('MATCH (t {id:$t}) WHERE t:StateVariable OR t:Measure RETURN t.id AS id',t=a['target']).data():
                    raise ValueError(f"영향 대상이 온톨로지에 없습니다: {a['target']}")
            tx.run('MATCH (k:Skill {id:$id})-[old:AFFECTS]->() WHERE old._manual_document IS NULL DELETE old',id=sid).consume()
            for a in values['affects']:
                tx.run('MATCH (k:Skill {id:$id}),(t {id:$t}) WHERE t:StateVariable OR t:Measure CREATE (k)-[:AFFECTS {sign:$sign,note:$note}]->(t)',
                       id=sid,t=a['target'],sign=a['sign'],note=a['note'] or None).consume()
        if role:
            tx.run('MATCH (k:Skill {id:$id})-[old:APPROVED_BY]->() DELETE old',id=sid).consume()
            tx.run('MATCH (k:Skill {id:$id}),(r:Role {id:$role}) CREATE (k)-[:APPROVED_BY]->(r)',id=sid,role=role).consume()
        result=stamp(tx.run(query,id=sid).data())[0]
        tx.run('CREATE (r:KnowledgeEdit {id:$id,skill:$skill,fingerprint:$fingerprint,actor:$actor,created_at:datetime(),before:$before,result:$result})',
               id=rid,skill=sid,fingerprint=digest,actor=by,before=json.dumps(current,ensure_ascii=False),result=json.dumps(result,ensure_ascii=False)).consume()
        return result
    return session.execute_write(run)


# ---------------------------------------------------------------- 화면에서 만든 조치 방법 지우기
#: 화면(조치 방법)에서 만든 것 = 문서 소유가 아닌 Skill. 바탕 지식(시드)에는 Skill 이 없고, 문서에서 온 Skill 은 그 문서의 묶음이 소유한다
SCREEN_SKILLS_Q = ('MATCH (k:Skill) WHERE k._manual_document IS NULL '
                   'RETURN k.id AS id, k.sopId AS sopId, k.name AS name ORDER BY k.id')
USES_Q = ('MATCH (k:Skill {id:$id}) '
          'RETURN k._manual_document AS document, k.sopId AS sopId, k.name AS name, '
          "COLLECT { MATCH (r:Rule)-[:OUTPUTS|APPLIES_TO]->(k) WHERE NOT r.id STARTS WITH 'rule:cand-' RETURN r.id } AS rules, "
          'COLLECT { MATCH (st:Step)-[:DOCUMENTS]->(k) RETURN st.id } AS cited, '
          'COUNT { (:DecisionCase)-[:CHOSE]->(k) } AS cases')


def screen_skills(session):
    """화면에서 만든 조치 방법 [{id, sopId, name}] — 「기준으로 되돌리기」가 지울 목록(문서에서 적재한 것은 그 묶음 되돌리기가 지운다)."""
    return session.execute_read(lambda tx: tx.run(SCREEN_SKILLS_Q).data())


def remove(session, sid, *, by, request_id=None):
    """화면에서 만든 조치 방법 하나를 지운다(Skill · 그 단계 · 화면이 만든 후보 규칙 연결). 영수증(KnowledgeEdit)과 한 트랜잭션.
      * 문서에서 적재한 조치 방법은 지우지 않는다 — 그 문서의 묶음 되돌리기가 지운다(소유 · 되돌리기 기록이 묶음에 있다).
      * 문서의 규칙이 결과 · 적용 대상으로 가리키거나 다른 문서의 단계가 인용하는 조치 방법도 지우지 않는다 — 지우면 그 문서의 적재 기록과
        그래프가 어긋나 그 문서를 되돌릴 수 없게 된다. 그 문서를 먼저 되돌리라고 말한다.
      * 이 조치 방법을 고른 판단 기록(DecisionCase)은 남는다. 그 기록에서 이 조치 방법으로 가는 연결만 없어지고, 몇 건인지 돌려준다.
      * 이 조치 방법만 내던 화면 후보 규칙(rule:cand-<고장 유형>)은 함께 지운다(결과 없는 규칙을 남기지 않는다).
    돌려줌 = {id, sopId, name, deleted: True, decision_cases, removed_rules}. 없으면 KeyError."""
    if not isinstance(by, str) or not by.strip():
        raise ValueError('지우는 담당자가 필요합니다')
    if request_id is not None and not isinstance(request_id, str):
        raise ValueError('request_id는 UUID 문자열이어야 합니다')
    rid = str(uuid.UUID(request_id)) if request_id is not None else str(uuid.uuid4())
    digest = fingerprint({'skill': sid, 'delete': True, 'by': by})
    manual_graph.ensure_schema(session)

    def run(tx):
        manual_graph._lock(tx)
        receipt = tx.run('MATCH (r:KnowledgeEdit {id:$id}) RETURN r.fingerprint AS fingerprint,r.result AS result', id=rid).single()
        if receipt:
            if receipt['fingerprint'] != digest:
                raise Conflict('같은 요청 ID에 다른 지식 변경을 사용할 수 없습니다')
            return json.loads(receipt['result'])
        found = tx.run(USES_Q, id=sid).single()
        if not found:
            raise KeyError(sid)
        if found['document']:
            raise Conflict('문서에서 적재한 조치 방법입니다 — 「지식 › 문서 등록」의 등록 이력에서 그 문서를 되돌리면 함께 지워집니다')
        if found['rules'] or found['cited']:
            what = ' · '.join(filter(None, [f"문서의 규칙 {len(found['rules'])}개({', '.join(found['rules'][:3])})" if found['rules'] else '',
                                            f"다른 문서의 단계 {len(found['cited'])}개" if found['cited'] else '']))
            from hydcommon.words import josa
            raise Conflict(f"{josa(what, '이')} 이 조치 방법을 가리킵니다 — 그 문서를 「지식 › 문서 등록」의 등록 이력에서 먼저 되돌린 뒤 지우세요")
        tx.run('MATCH (k:Skill {id:$id}) OPTIONAL MATCH (k)-[:HAS_STEP]->(st:Step) DETACH DELETE st', id=sid).consume()
        rules = [r['id'] for r in tx.run("MATCH (r:Rule)-[:OUTPUTS]->(:Skill {id:$id}) WHERE r.id STARTS WITH 'rule:cand-' RETURN r.id AS id", id=sid).data()]
        tx.run('MATCH (k:Skill {id:$id}) DETACH DELETE k', id=sid).consume()
        removed = [r['id'] for r in tx.run('MATCH (r:Rule) WHERE r.id IN $ids AND NOT (r)-[:OUTPUTS]->() WITH r, r.id AS id DETACH DELETE r RETURN id', ids=rules).data()]
        result = {'id': sid, 'sopId': found['sopId'], 'name': found['name'], 'deleted': True, 'decision_cases': found['cases'],
                  'removed_rules': sorted(removed)}
        tx.run('CREATE (r:KnowledgeEdit {id:$id,skill:$skill,fingerprint:$fingerprint,actor:$actor,created_at:datetime(),before:$before,result:$result})',
               id=rid, skill=sid, fingerprint=digest, actor=by.strip(), before=json.dumps({'sopId': found['sopId'], 'name': found['name']}, ensure_ascii=False),
               result=json.dumps(result, ensure_ascii=False)).consume()
        return result
    return session.execute_write(run)
