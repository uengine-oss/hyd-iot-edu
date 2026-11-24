"""AI 지시문(worker/prompt.py) — 업무 · 지시(입력 [InputData] 포함) · 앞서 낸 결과 · 피드백 · 결과 제출 형식."""
import json

import pytest

from worker import prompt

ROW = {'activity_name': '원인 진단', 'query': '진단하라\n[InputData] {"asset": "HYD-01"}'}
FORM = [{'key': 'cause', 'label': '원인', 'type': 'text'}, {'key': 'approve', 'label': '승인', 'items': [{'yes': '예'}, {'no': '아니오'}]}]


@pytest.mark.parametrize('output, expect', [
    (None, None), ({'cliagents_session_id': 's'}, None), ({'cause': 'c', 'cliagents_session_id': 's'}, {'cause': 'c'}), ('{"a": 1}', {'a': 1}),
], ids=['첫 실행', '세션 id 만', '앞서 낸 결과', '글로 저장된 JSON'])
def test_앞서_낸_결과는_작업_행_결과에서_세션_id_를_빼고_읽는다(output, expect):
    """G1-27: 「입력 데이터」(context/input.json)는 실제 입력이 아니라 이 값(+ 진행 중 초안)이었고 첫 실행마다 null 파일을 읽게 했다."""
    assert prompt.previous_result({'output': output, 'draft': {'cliagents_session_id': 'x'}}) == expect


def test_첫_실행의_지시문에는_앞서_낸_결과_칸이_없고_입력은_지시의_InputData_라고_말한다():
    text = prompt.build(ROW, {'form_fields': FORM}, workdir='/w')
    assert '## 이 작업이 앞서 낸 결과' not in text and 'context/input.json' not in text and '[InputData]' in text
    assert prompt.PREVIOUS_RESULT_FILE in text      # runner 가 쓰는 그 파일 이름(G1-27 — 상수 한 곳)


def test_재작업_지시문에는_앞서_낸_결과와_피드백이_있다():
    text = prompt.build(dict(ROW, output={'cause': '이전'}), {'form_fields': FORM, 'summarized_feedback': '근거가 약함'}, workdir='/w')
    assert '## 이 작업이 앞서 낸 결과\n{\n  "cause": "이전"\n}' in text and '근거가 약함' in text


def test_결과_형식은_칸_허용값_골격을_싣고_파일과_메시지_두_길을_말한다():
    contract = prompt.output_contract(FORM)
    assert '`approve`: 승인' in contract and '`yes`(예)' in contract and 'output/result.json' in contract
    assert json.loads(contract.split('```json\n')[1].split('\n```')[0]) == {'cause': '', 'approve': ''}
    assert prompt.output_contract([]) .startswith('## 결과 제출 형식\n작업을 마치면 마지막 메시지에')


def test_긴_앞선_결과는_잘라_보이고_전체는_파일에_있다고_말한다():
    big = {'text': 'x' * (prompt.INLINE_INPUT_LIMIT + 100)}
    text = prompt.build(dict(ROW, output=big), {}, workdir='/w')
    assert '[잘림: ' in text and prompt.PREVIOUS_RESULT_FILE in text


def test_입력의_긴_글은_파일로_빼고_지시에는_그_경로를_적어_어느_줄도_읽기_도구가_다_읽을_수_있다():
    """처리 엔진은 입력 전체를 한 줄 JSON 으로 지시 끝에 붙인다. 학생 매뉴얼(1만 1천 자) + 지식 목록이 한 줄 2만 9천 토큰이 되어, 읽기 도구(한 번에
    약 2만 5천 토큰 · 한 줄은 쪼개 읽지 못함)가 그 줄을 읽지 못한 AI가 같은 줄을 거듭 열다 한 번 실행의 호출 한도를 다 썼다(2026-11-23 실측).
    실제 학생 매뉴얼 원문이 든 입력으로: 긴 글은 그 글 그대로 파일에, 지시의 줄은 모두 짧고, 짧은 값 · JSON 꼴은 그대로다."""
    import apu_document as apu
    text = apu.RAW.decode('utf-8')
    catalog = {'components': [{'id': f'comp:c{i}', 'name': f'구성 요소 {i}'} for i in range(300)]}
    inputs = {'manual_source': {'source_id': 'manual:x', 'status': 'READY', 'pages': [{'page': 1, 'text': text}]}, 'ontology_catalog': catalog}
    query = '원문 근거로 SOP 를 제안하라\n\n[InputData]\n' + json.dumps(inputs, ensure_ascii=False)
    assert max(map(len, query.splitlines())) > 20_000                                     # 고치기 전: 한 줄에 원문과 목록 전부
    shown, files = prompt.input_files(query)
    assert files == {'context/input/manual_source.pages.0.text.txt': text}                 # 그 글 그대로(줄바꿈 포함 — 인용을 그대로 할 수 있다)
    head, _, tail = shown.partition('[InputData]')
    assert head == '원문 근거로 SOP 를 제안하라\n\n'
    data = json.loads(tail)
    assert data['manual_source']['source_id'] == 'manual:x' and data['ontology_catalog'] == catalog      # 짧은 값은 그대로
    pointer = data['manual_source']['pages'][0]['text']
    assert 'context/input/manual_source.pages.0.text.txt' in pointer and f'{len(text):,}자' in pointer
    assert max(map(len, shown.splitlines())) <= prompt.LONG_INPUT_CHARS + 200               # 어느 줄도 읽기 도구가 다 보여 준다
    assert prompt.input_files('진단하라') == ('진단하라', {})                                  # 입력이 없는 지시는 그대로
    assert prompt.input_files(ROW['query'])[1] == {}                                          # 긴 글이 없으면 파일도 없다


def test_찾지_못한_사실은_담당자에게_되묻지_않고_결과_형식의_길로_끝내라고_묻는_형식보다_먼저_말한다():
    """2026-11-23 수업 한 바퀴: 지식에 없는 것을 물은 질문에 실제 AI가 「답할 수 없음」 대신 질문한 사람에게 「확인되는 자료를 알려 달라」고 되묻고
    멈췄다(같은 질문의 2026-11-01 저장 응답은 답할 수 없음). 지시문의 「담당자에게 질문」 조건(필수 업무 정보가 없고 조회 도구로도 확인할 수 없으면)에
    「작업이 찾아야 할 사실을 찾지 못함」도 들어맞았기 때문이다. 실제 질문 정의(ask_agent)의 지시 · 폼으로 만든 지시문에서: 가르는 기준이 묻는 형식
    (__human_input__)보다 앞에 있고, 그 기준이 가리키는 길(근거를 얻지 못했을 때 쓰는 허용값)이 그 지시문의 결과 형식에 실제로 있다."""
    from pathlib import Path
    defn = json.loads((Path(prompt.__file__).parents[2] / 'process' / 'definitions' / 'ask_agent_v1.json').read_text(encoding='utf-8'))
    act = defn['activities'][0]
    text = prompt.build({'activity_name': act['name'], 'query': act['instruction'] + '\n[InputData] {"question": "q"}'},
                        {'form_fields': defn['forms']['ask_answer']['fields_json']}, workdir='/w')
    section = text.split('## 담당자에게 업무 정보 질문\n')[1].split('\n\n## ')[0]
    assert prompt.HUMAN_QUESTION_SCOPE in section and section.index(prompt.HUMAN_QUESTION_SCOPE) < section.index('__human_input__')
    assert '담당자에게 되묻지 마세요' in prompt.HUMAN_QUESTION_SCOPE and '허용값' in prompt.HUMAN_QUESTION_SCOPE
    assert '`cannot_answer`' in prompt.output_contract(defn['forms']['ask_answer']['fields_json'])      # 그 길이 이 작업의 결과 형식에 있다
    plain = prompt.build(ROW, {'form_fields': FORM}, workdir='/w')                                       # 「할 수 없음」 허용값이 없는 작업 — 보류 객체가 그 길
    assert prompt.HUMAN_QUESTION_SCOPE in plain and '__deferred__' in plain


def _engine_query(base, inputs, condition=None):
    """처리 엔진(engine.reach)이 작업 행에 붙이는 꼴 그대로 — 지시 글, 입력 JSON 한 줄, 있으면 재작업 계획의 조건 값 JSON 한 줄."""
    from procsvc import engine
    query = f"{base}\n\n{engine.INPUT_MARK}\n{json.dumps(inputs, ensure_ascii=False)}"
    if condition is not None:
        query += f"\n\n{engine.CONDITION_MARK}\n{json.dumps(condition, ensure_ascii=False)}"
    return query


def test_재작업_계획의_조건_값이_붙은_지시도_읽고_입력과_조건_값을_모두_보인다():
    """엔진은 [다시 수행]의 재작업 계획이 조건을 가진 단계에 [InputData] 뒤로 [ConditionData] 를 붙인다(engine.reach). 워커가 [InputData] 뒤를
    통째로 JSON 하나로 읽어 「Extra data」로 그 단계가 늘 실패했다(2026-11-24 검토 가-1)."""
    from procsvc import engine
    long_text = '가' * (prompt.LONG_INPUT_CHARS + 1)
    query = _engine_query('점검하라', {'asset': 'HYD-01', 'note': long_text}, {'approval': '승인', 'retry': 2})
    assert engine.query_parts(query) == ('점검하라', {'asset': 'HYD-01', 'note': long_text}, {'approval': '승인', 'retry': 2})
    shown, files = prompt.input_files(query)
    assert files == {'context/input/note.txt': long_text}
    _, inputs, condition = engine.query_parts(shown)                     # AI에게 보이는 지시도 같은 꼴이다
    assert inputs['asset'] == 'HYD-01' and 'context/input/note.txt' in inputs['note'] and condition == {'approval': '승인', 'retry': 2}
    assert engine.query_parts(_engine_query('점검하라', {'asset': 'HYD-01'})) == ('점검하라', {'asset': 'HYD-01'}, None)
    assert engine.query_parts('점검하라') == ('점검하라', None, None)
    with pytest.raises(ValueError, match=r'\[InputData\] 값 뒤에 모르는 글'):
        engine.query_parts(_engine_query('점검하라', {'a': 1}) + '\n덧붙인 글')


def test_길이가_같은_한글_변수_이름의_긴_입력도_서로_다른_파일에_제_글로_들어간다():
    """흐름 변수 이름은 한글도 된다(bpmn_import 의 isidentifier). 파일 이름을 영문 · 숫자만 남겨 만들면 「본문」 · 「요약」이 둘 다 __.txt 가 되어 뒤 값이
    앞 값을 덮었다 — AI가 다른 글로 판단(2026-11-24 검토 가-2)."""
    body, summary = '본' * (prompt.LONG_INPUT_CHARS + 1), '요' * (prompt.LONG_INPUT_CHARS + 2)
    shown, files = prompt.input_files(_engine_query('정리하라', {'본문': body, '요약': summary}))
    assert sorted(files.values(), key=len) == [body, summary] and len(files) == 2
    from procsvc import engine
    pointers = engine.query_parts(shown)[1]
    assert {k: files[next(p for p in files if p in v)] for k, v in pointers.items()} == {'본문': body, '요약': summary}
