"""A118 (r14 B3, ontology-studio `ontology_build_report.golden_questions`): after a manual is ingested, "which questions can
the ontology now answer *because of this document*?" — one report per document batch, question by question, with
status answerable | partially_answerable | not_yet_answerable and confidence high | medium | low, like the studio's build
report. HYD's whole-graph audit (queries.cypher Q01~Q22) checks connectivity; it cannot say what one document added.

Unlike the studio (the agent's self-report is taken as is), each answer must cite node ids that belong to this batch's
document, and the server checks them: an "answerable" item without a grounded citation goes back to the agent as a
correction (same bounded loop as the extraction proposal, A077). The agent is a product-shaped agent task (A116) and
reads the graph through the Neo4j MCP only.
"""
from copy import deepcopy
from uuid import UUID, uuid4

from . import engine

DEFINITION_ID = 'manual_golden_check'
VERSION = '1.0'
ACTIVITY = 'task:golden'
CONTRACT = 'manual-golden-report-v1'
STATUSES = ('answerable', 'partially_answerable', 'not_yet_answerable')
CONFIDENCES = ('high', 'medium', 'low')
MAX_QUESTIONS = 20
MAX_QUESTION_CHARS = 500
EVENT_PREFIX = 'manual-golden:'

INSTRUCTION = '''golden_request에 문서(매뉴얼) 하나가 온톨로지에 적재된 뒤의 골든 퀘스천 목록이 있습니다.
질문마다 **지금 온톨로지(Neo4j MCP 조회)만으로** 답할 수 있는지 판정하고 답을 적으세요. 원문 PDF·외부 지식·추측으로 답하지 않습니다.
golden_request.knowledge에 이 문서가 넣은 노드(절 ManualSection · SOP Skill · 단계 Step)의 id가 있습니다. 답의 근거는 그 id들로 인용합니다.
Cypher로 실제 조회한 결과만 근거로 삼고, 쓴 Cypher를 cypher에 남기세요.
status: answerable = 이 문서의 노드로 완전히 답함 · partially_answerable = 일부만(빠진 것을 answer에 적음) · not_yet_answerable = 이 문서로는 못 답함(이유를 적음).
confidence: high | medium | low. 답할 수 없는 질문을 답할 수 있다고 쓰지 마세요. 질문 문장은 받은 그대로 유지합니다.
최종 응답은 {"golden_report": {"items": [{"question": "받은 질문 그대로", "answer": "답 또는 못 답하는 이유", "status": "...",
"confidence": "...", "cited": ["이 문서의 노드 id"], "cypher": "실제 실행한 조회"}], "summary": "한 줄 요약"}} 하나입니다.'''


def definition():
    return dict(processDefinitionId=DEFINITION_ID, processDefinitionName='문서별 골든 퀘스천 확인', version=VERSION,
                roles=[dict(name='AI 에이전트', endpoint='sys:agent')],
                data=[dict(name='golden_request', type='Object'), dict(name='golden_report', type='Object')],
                events=[dict(id='start', type='startEvent', name='골든 퀘스천 확인 요청'),
                        dict(id='end', type='endEvent', name='보고 완료')],
                activities=[dict(id=ACTIVITY, name='이 문서로 답할 수 있는 질문 확인', type='userTask',   # A116 product shape
                                 role='AI 에이전트', agentMode='COMPLETE', orchestration='cliagents',
                                 tool='formHandler:golden_report', inputData=['golden_request'], outputData=['golden_report'],
                                 instruction=INSTRUCTION)],
                gateways=[], sequences=[dict(id='s1', source='start', target=ACTIVITY), dict(id='s2', source=ACTIVITY, target='end')],
                forms={'golden_report': dict(contract=CONTRACT, fields_json=[
                    dict(key='golden_report', type='object', text='문서별 골든 퀘스천 보고', required=True)])})


def validate_questions(questions):
    if not isinstance(questions, list) or not 1 <= len(questions) <= MAX_QUESTIONS:
        raise ValueError(f'골든 퀘스천은 1~{MAX_QUESTIONS}개의 목록이어야 합니다')
    out = []
    for q in questions:
        if not isinstance(q, str) or not q.strip() or len(q) > MAX_QUESTION_CHARS:
            raise ValueError(f'질문은 비어 있지 않은 {MAX_QUESTION_CHARS}자 이하 문자열이어야 합니다')
        if q.strip() in out:
            raise ValueError('같은 질문이 두 번 있습니다')
        out.append(q.strip())
    return out


def batch_knowledge(session, tenant, batch):
    """What this batch's document holds in the graph right now (the ids an answer may cite). Only the current head batch
    of a document is checked: a superseded or rolled-back batch's nodes are gone."""
    import json
    def read(tx):
        row = tx.run('MATCH (b:ManualIngestionBatch {id:$id, tenant:$tenant}) OPTIONAL MATCH (d:ManualIngestionDocument {id:b.document}) '
                     'RETURN properties(b) AS b, d.head AS head', id=batch, tenant=tenant).single()
        if not row:
            raise KeyError(batch)
        record = row['b']
        if record['status'] != 'ACTIVE' or row['head'] != batch:
            raise ValueError('현재 판본(head)인 배치만 골든 퀘스천을 확인할 수 있습니다')
        # C1: what the document owns is its journal (head snapshot) — knowledge labels carry no _manual_document property
        snap = tx.run('MATCH (d:ManualIngestionDocument {id:$id}) RETURN d.snapshot AS s', id=record['document']).single()
        nodes = sorted(({'labels': n['labels'], 'p': n['props']} for n in json.loads(snap['s'] if snap and snap['s'] else '{}').get('nodes', [])),
                       key=lambda n: n['p']['id'])
        receipt = json.loads(record['receipt'])
        sections = [dict(id=n['p']['id'], ref=n['p'].get('ref'), title=n['p'].get('title')) for n in nodes if 'ManualSection' in n['labels']]
        skills = [dict(id=n['p']['id'], sopId=n['p'].get('sopId'), name=n['p'].get('name')) for n in nodes if 'Skill' in n['labels']]
        steps = sum(1 for n in nodes if 'Step' in n['labels'])
        return dict(batch=batch, document=record['document'], source_id=receipt.get('source_id'), filename=receipt.get('filename'),
                    knowledge=dict(ids=sorted(n['p']['id'] for n in nodes), sections=sections, skills=skills, steps=steps))
    return session.execute_read(read)


def request(record, questions, by):
    return dict(batch=record['batch'], document=record['document'], source_id=record['source_id'], filename=record['filename'],
                questions=validate_questions(questions), knowledge=record['knowledge'], by=str(by or '').strip()[:120])


def start(rt, req, request_id):
    request_id = str(UUID(request_id))
    rt.register_definition(definition())
    event_id = EVENT_PREFIX + req['batch'] + ':' + request_id
    inst = rt.start_definition(DEFINITION_ID, VERSION, event_id, values={'golden_request': req},
                               name=f"{req['filename']} 골든 퀘스천 {len(req['questions'])}개")
    return inst or rt.repo.find_event_instance(rt.tenant_id, DEFINITION_ID, event_id)


def validate_report(req, report):
    """Structure, the questions verbatim, enum values, and grounding: an answerable/partial item cites ids of this
    document; an id outside the document is a defect. Raises ValueError (→ correction feedback for the agent)."""
    if not isinstance(req, dict) or not isinstance(report, dict):
        raise ValueError('골든 퀘스천 보고가 필요합니다')
    items = report.get('items')
    questions = req.get('questions') or []
    if not isinstance(items, list) or len(items) != len(questions):
        raise ValueError(f'보고 항목은 질문 수({len(questions)})와 같아야 합니다')
    known = set((req.get('knowledge') or {}).get('ids') or [])
    for i, (item, question) in enumerate(zip(items, questions), 1):
        if not isinstance(item, dict):
            raise ValueError(f'{i}번 항목은 객체여야 합니다')
        if item.get('question') != question:
            raise ValueError(f'{i}번 항목의 question은 받은 질문과 같아야 합니다: {question[:60]!r}')
        if not isinstance(item.get('answer'), str) or not item['answer'].strip():
            raise ValueError(f'{i}번 항목의 answer가 비어 있습니다')
        if item.get('status') not in STATUSES:
            raise ValueError(f"{i}번 항목의 status는 {' | '.join(STATUSES)} 중 하나여야 합니다")
        if item.get('confidence') not in CONFIDENCES:
            raise ValueError(f"{i}번 항목의 confidence는 {' | '.join(CONFIDENCES)} 중 하나여야 합니다")
        cited = item.get('cited')
        if not isinstance(cited, list) or any(not isinstance(c, str) for c in cited):
            raise ValueError(f'{i}번 항목의 cited는 노드 id 문자열 목록이어야 합니다')
        foreign = sorted(c for c in cited if c not in known)
        if foreign:
            raise ValueError(f"{i}번 항목이 이 문서에 없는 노드를 인용했습니다: {', '.join(foreign[:5])} (이 문서의 노드 id만 근거로 쓰세요)")
        if item['status'] != 'not_yet_answerable' and not cited:
            raise ValueError(f'{i}번 항목: 답할 수 있다고 하려면 이 문서의 노드 id를 하나 이상 인용해야 합니다 (근거 없는 판정)')
        if item.get('cypher') is not None and not isinstance(item['cypher'], str):
            raise ValueError(f'{i}번 항목의 cypher는 문자열이어야 합니다')
    if report.get('summary') is not None and not isinstance(report['summary'], str):
        raise ValueError('summary는 문자열이어야 합니다')
    return deepcopy(report)


def validate_result(form, inst, output):
    if form and form.get('contract') == CONTRACT:
        validate_report(engine.variables(inst).get('golden_request'), (output or {}).get('golden_report'))


def result(rt, batch):
    """The latest golden check of a batch: task state and, when done, the validated report with server-side counts."""
    runs = rt.repo.list_source_runs(rt.tenant_id, DEFINITION_ID, EVENT_PREFIX + batch + ':')
    if not runs:
        raise KeyError(batch)
    inst = rt.repo.get_instance(max(runs, key=lambda i: i.get('start_date') or '')['proc_inst_id'])   # newest request
    req = engine.variables(inst).get('golden_request') or {}
    items = rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None)
    wi = max([w for w in items if w['activity_id'] == ACTIVITY], key=engine.workitem_order)
    out = dict(batch=batch, instance=inst['proc_inst_id'], workitem=wi['id'], status=wi['status'], questions=len(req.get('questions') or []),
               filename=req.get('filename'), report=None)
    feedback = wi.get('feedback') if isinstance(wi.get('feedback'), dict) else {}
    if feedback.get('kind') == 'validation':
        out['corrections'] = dict(attempts=feedback.get('attempt'), reasons=list(feedback.get('history') or []))
    if wi['status'] != 'DONE':
        return out
    report = validate_report(req, (wi.get('output') or {}).get('golden_report'))
    counts = {s: sum(1 for it in report['items'] if it['status'] == s) for s in STATUSES}
    out.update(report=report, **counts, grounded=sum(1 for it in report['items'] if it['cited']))
    return out
