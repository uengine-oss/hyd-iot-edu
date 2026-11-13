"""문서별 골든 질문(procsvc/manual_golden.py) — 「이 문서 덕분에 지식이 답할 수 있게 된 질문」 보고의 계약(받은 질문 그대로 · 이 문서의 노드만
인용 · 답할 수 있다면 실제 조회)과, 실제 도구 호출 기록에 비춘 근거 대조(기록에 없으면 「답 못함」으로 낮춤). 골든 질문 요청 자체는 수업 단계에서
막히고(PBL), 계약 · 근거 대조는 두 단계 공통이다. 도구 호출 기록은 워커가 남기는 모양(ask.tool_calls 의 결과)이다."""
import pytest

from procsvc import manual_golden as mg

REQ = {'batch': 'b1', 'document': 'doc', 'source_id': 's', 'filename': 'HM-8.md', 'questions': ['쿨러 즉시 조치는?', '팬 점검 기준은?'],
       'knowledge': {'ids': ['skill:sop-cool-11', 'section:hm-8-5'], 'sections': [], 'skills': [], 'steps': 0}, 'by': '강사'}


def item(question, **over):
    return {'question': question, 'answer': 'SOP-COOL-11 팬 최대 운전', 'status': 'answerable', 'confidence': 'high',
            'cited': ['skill:sop-cool-11'], 'cypher': "MATCH (k:Skill {id:'skill:sop-cool-11'}) RETURN k.id", **over}


def report(*items):
    return {'items': list(items), 'summary': '두 질문'}


@pytest.mark.parametrize('questions, ok', [
    (['하나'], True), ([f'질문 {i}' for i in range(mg.MAX_QUESTIONS)], True), (['가' * mg.MAX_QUESTION_CHARS], True),
    ([], False), ([f'질문 {i}' for i in range(mg.MAX_QUESTIONS + 1)], False), (['가' * (mg.MAX_QUESTION_CHARS + 1)], False),
    (['같음', ' 같음 '], False), (['  '], False), ('질문', False),
], ids=['1개', '한도 개수', '한도 길이', '없음', '개수 초과', '길이 초과', '겹침', '빈 질문', '목록 아님'])
def test_질문은_1개에서_20개까지_비지_않고_겹치지_않게_받는다(questions, ok):
    if ok:
        assert mg.validate_questions(questions) == [q.strip() for q in questions]
    else:
        with pytest.raises(ValueError):
            mg.validate_questions(questions)


def test_받은_질문_그대로_이_문서의_노드를_인용한_보고는_받는다():
    out = mg.validate_report(REQ, report(item(REQ['questions'][0]), item(REQ['questions'][1], status='not_yet_answerable', cited=[], cypher=None)))
    assert [i['status'] for i in out['items']] == ['answerable', 'not_yet_answerable']


@pytest.mark.parametrize('items, says', [
    ([item('쿨러 즉시 조치는?')], '질문 수'),
    ([item('바꾼 질문'), item('팬 점검 기준은?')], '받은 질문과 같아야'),
    ([item('쿨러 즉시 조치는?', cited=['skill:other-doc']), item('팬 점검 기준은?')], '이 문서에 없는 노드'),
    ([item('쿨러 즉시 조치는?', cited=[]), item('팬 점검 기준은?')], '근거 없는 판정'),
    ([item('쿨러 즉시 조치는?', cypher=''), item('팬 점검 기준은?')], 'cypher가 필요'),
    ([item('쿨러 즉시 조치는?', status='maybe'), item('팬 점검 기준은?')], 'status'),
    ([item('쿨러 즉시 조치는?', answer=' '), item('팬 점검 기준은?')], 'answer'),
], ids=['개수 다름', '질문 바꿈', '다른 문서 노드', '인용 없는 답', '조회 없는 답', '없는 상태', '빈 답'])
def test_계약에_맞지_않는_보고는_에이전트가_고칠_까닭을_준다(items, says):
    with pytest.raises(ValueError, match=says):
        mg.validate_report(REQ, report(*items))


def call(cypher, output, *, ok=True, complete=True):
    return {'id': 'c1', 'tool': 'neo4j/read_neo4j_cypher', 'ok': ok, 'data': True, 'output_complete': complete,
            '_input': {'query': cypher}, '_output': output}


def test_실제_조회_결과에_인용한_노드가_있으면_근거가_확인된다():
    it = item(REQ['questions'][0])
    out = mg.ground_report(report(it), [call(it['cypher'], '[{"k.id": "skill:sop-cool-11"}]')])
    assert out['items'][0]['grounding'] == {'verified': True, 'calls': ['c1'], 'missing': []} and out['items'][0]['status'] == 'answerable'


@pytest.mark.parametrize('calls', [
    [],                                                                          # 조회 기록 없음
    [call("MATCH (n) RETURN n", '[{"k.id": "skill:sop-cool-11"}]')],             # 다른 질의
    [call("MATCH (k:Skill {id:'skill:sop-cool-11'}) RETURN k.id", '[]')],        # 결과에 그 노드가 없음
    [call("MATCH (k:Skill {id:'skill:sop-cool-11'}) RETURN k.id", '[{"k.id": "skill:sop-cool-11"}]', complete=False)],   # 잘린 결과
], ids=['조회 없음', '다른 질의', '결과에 없음', '잘린 결과'])
def test_조회_기록으로_확인되지_않는_답은_답_못함으로_낮추고_원래_답을_남긴다(calls):
    it = item(REQ['questions'][0])
    out = mg.ground_report(report(it), calls)['items'][0]
    assert (out['status'], out['confidence'], out['claimed_status']) == ('not_yet_answerable', 'low', 'answerable')
    assert out['grounding']['verified'] is False and out['claimed_answer'] == it['answer']


def test_골든_질문_요청은_이_문서의_노드_목록과_다듬은_질문을_싣는다():
    record = {k: REQ[k] for k in ('batch', 'document', 'source_id', 'filename', 'knowledge')}
    req = mg.request(record, [' 쿨러 즉시 조치는? '], '  강사  ')
    assert (req['questions'], req['by'], req['knowledge']['ids']) == (['쿨러 즉시 조치는?'], '강사', REQ['knowledge']['ids'])


def test_골든_질문_정의는_계약과_판본을_싣는다():
    d = mg.definition()
    assert (d['processDefinitionId'], d['version'], d['forms']['golden_report']['contract']) == (mg.DEFINITION_ID, mg.VERSION, mg.CONTRACT)


def test_지금_판이_아닌_배치는_골든_질문을_묻지_않는다(seeded_graph):
    seeded_graph.query("CREATE (:ManualIngestionBatch {id:'b-old', tenant:'hyd', status:'ACTIVE', document:'d1', receipt:'{}'}) "
                       "CREATE (:ManualIngestionDocument {id:'d1', tenant:'hyd', head:'b-new', snapshot:'{}'})")
    with seeded_graph.driver.session() as session:
        with pytest.raises(ValueError, match='현재 판본'):
            mg.batch_knowledge(session, 'hyd', 'b-old')
        with pytest.raises(KeyError):
            mg.batch_knowledge(session, 'hyd', 'b-none')
