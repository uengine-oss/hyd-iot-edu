"""Shift handover contracts. Confirmation records communication, never repairs."""
from copy import deepcopy
from datetime import datetime
import json

from hydcommon import topics

from . import ask

DEFINITION_ID = 'shift_handover'
DRAFT = 'shift-handover-draft-v1'
SENDER = 'shift-handover-sender-v1'
RECEIVER = 'shift-handover-receiver-v1'
AREAS = {'equipment', 'work_orders', 'parts', 'work_notes'}
START_INPUTS = frozenset({'asset', 'shift_label', 'as_of', 'work_notes'})


def optional_inputs(form):
    contract = (form or {}).get('contract')
    return {'sender_notes', 'receiver_notes'} if contract == DRAFT else {'receiver_notes'} if contract == SENDER else set()


def validate_start(values):
    if not isinstance(values, dict) or set(values) != START_INPUTS:
        raise ValueError('인수인계 시작에는 설비·교대·기준시각·작업 메모만 입력하세요')
    for key, maximum in [('asset', 80), ('shift_label', 120), ('work_notes', 4000), ('as_of', 80)]:
        value = values[key]
        if not isinstance(value, str) or not value.strip() or len(value)>maximum:
            raise ValueError('인수인계 시작 입력이 비어 있거나 한도를 넘었습니다: '+key)
    if values['asset'].strip() not in topics.ASSETS:
        raise ValueError(f"없는 설비입니다: {values['asset']} — 설비는 {', '.join(topics.ASSETS)} 중 하나입니다")
    try:
        moment = datetime.fromisoformat(values['as_of'].replace('Z', '+00:00'))
        if moment.utcoffset() is None: raise ValueError()
    except ValueError:
        raise ValueError('기준시각에는 시간대가 포함된 ISO 시각을 입력하세요') from None


def validate_result(form, inst, output):
    contract = (form or {}).get('contract')
    if contract == DRAFT:
        # The worker adds transport text/session metadata after reading the
        # structured result. These are not process-variable declarations.
        if set(output) - {'text', 'cliagents_session_id'} != {'handover_summary', 'checks', 'evidence'}:
            raise ValueError('인계안은 handover_summary·checks·evidence만 제출하세요')
        checks, evidence = output['checks'], output['evidence']
        if not isinstance(checks, list) or len(checks) != 4 or \
                any(not isinstance(c, dict) for c in checks) or {c.get('area') for c in checks} != AREAS:
            raise ValueError('설비·열린 작업지시·부품·작업 메모를 각각 한 번씩 확인하세요')
        if not isinstance(evidence, list) or len(evidence)>40:
            raise ValueError('조회 근거는 40개 이하 목록이어야 합니다')
        if evidence:
            ask.validate_answer(dict(status='answered', answer=output['handover_summary'], evidence=evidence))
        for check in checks:
            if set(check) != {'area', 'state', 'finding', 'next_action', 'evidence_indices'}:
                raise ValueError('각 확인 항목에는 area·state·finding·next_action·evidence_indices가 필요합니다')
            if check['state'] not in ('observed', 'needs_check', 'conflict'):
                raise ValueError('확인 상태는 observed·needs_check·conflict 중 하나입니다')
            if any(not isinstance(check[k], str) or not check[k].strip() or len(check[k])>2000 for k in ('finding', 'next_action')):
                raise ValueError('확인 사실과 다음 근무자가 확인할 일을 구체적으로 적으세요')
            refs = check['evidence_indices']
            if not isinstance(refs, list) or any(type(i) is not int or not 0 <= i < len(evidence) for i in refs):
                raise ValueError('근거 번호는 evidence의 0부터 시작하는 유효한 번호여야 합니다')
            if check['state'] != 'needs_check' and check['area'] != 'work_notes' and not refs:
                raise ValueError('조회 근거가 없으면 확인 필요(needs_check)로 남기세요')
    elif contract in (SENDER, RECEIVER):
        prefix = 'sender' if contract == SENDER else 'receiver'
        decision = output.get(prefix+'_decision')
        choices = ('approve', 'revise', 'reject') if contract == SENDER else ('confirm', 'revise')
        if decision not in choices:
            raise ValueError('인수인계 검토 선택이 올바르지 않습니다')
        note = output.get(prefix+'_notes')
        if not isinstance(note, str) or not note.strip() or len(note)>2000:
            raise ValueError('확인 사항 또는 보완·반려 사유를 적으세요')
        if contract == RECEIVER and decision == 'confirm' and output.get('communication_only') is not True:
            raise ValueError('인계 확인은 설비 조치·발주·정비 완료가 아님을 확인하세요')


UNMATCHED_SHOWN = 5     # 돌려보내는 글에 싣는 맞지 않는 근거 수
CALLS_SHOWN = 5         # 그 근거의 도구를 실제로 부른 인자를 싣는 수(서로 다른 것만)
ARGUMENT_CHARS = 700    # 인자 하나를 싣는 길이 — 넘는 인자(긴 SQL)는 싣지 않고 길이만 말한다(잘린 인자를 옮겨 적으면 또 맞지 않는다)


def _arguments(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= ARGUMENT_CHARS else f'({len(text):,}자 인자 — 이 작업의 그 호출 기록에 있는 그대로)'


def unmatched_evidence(evidence, checked, calls) -> str:
    """실제 호출과 맞지 않는 근거를 번호 · 도구 · 적은 인자와, 그 도구를 이 작업에서 성공적으로 부른 실제 인자로 적는다(돌려보내는 글).
    전에는 「모든 조회 근거가 … 일치해야 합니다」뿐이라 AI가 어느 근거가 틀렸는지 모르고 차례마다 모든 조회를 처음부터 다시 한 뒤 같은 곳을 또
    틀렸다(2026-11-23 실습 17: 근거 14개 중 8번째 하나 — 적은 인자 {"table":…,"offset":0,"limit":20}, 실제 호출 인자에는 offset 이 없음 — 가
    두 번 돌려보내지고 세 번째 차례는 호출 12번 · 입력 7.67 MB 로 한 번 실행의 한도에 닿았다)."""
    lines = []
    wrong = [i for i, e in enumerate(checked) if not e['verified']]
    for i in wrong[:UNMATCHED_SHOWN]:
        item = evidence[i] if isinstance(evidence[i], dict) else {}
        same_tool = []
        for call in calls:
            if call.get('data') and call.get('ok') and ask._matches(dict(item, query=call.get('_input')), call):
                text = _arguments(call.get('_input'))
                if text not in same_tool:
                    same_tool.append(text)
        actual = (('이 작업에서 이 도구를 성공적으로 부른 인자: ' + ' · '.join(same_tool[:CALLS_SHOWN])
                   + (f' 외 {len(same_tool) - CALLS_SHOWN}개' if len(same_tool) > CALLS_SHOWN else '')) if same_tool
                  else '이 작업에서 이 도구를 성공적으로 부른 기록이 없습니다')
        lines.append(f"evidence[{i}] {ask.short_tool(item.get('tool'))} 에 적은 query {_arguments(item.get('query'))} — 이 인자 그대로 성공한 호출이 "
                     f'없습니다({actual})')
    more = f' 외 {len(wrong) - UNMATCHED_SHOWN}개' if len(wrong) > UNMATCHED_SHOWN else ''
    return (f'맞지 않는 근거 {len(wrong)}개: ' + '; '.join(lines) + more + '. 이 근거만 고치세요 — query 를 실제로 부른 인자와 글자 그대로 같게 하거나, '
            '그 인자로 부른 적이 없는 근거는 빼고 evidence_indices 를 맞추세요. 나머지 근거는 이미 실제 호출과 일치하므로 같은 조회를 다시 하지 않아도 됩니다.')


def validate_trace(repo, wi, form, output):
    if (form or {}).get('contract') != DRAFT or not output.get('evidence'):
        return
    calls = ask.tool_calls(repo.list_events(todo_id=wi['id']), repo.get_event_payload)
    verdict = ask.verdict(dict(answer=output['handover_summary'], evidence=output['evidence']), calls)
    evidence = verdict.get('evidence') or []
    if len(evidence) != len(output['evidence']):
        # 판정이 근거를 하나도 견주지 못했다 — 이 작업에 성공한 조회가 없다(ask.verdict)
        raise ValueError('인계안의 모든 조회 근거가 현재 작업의 성공한 실제 도구 호출과 일치해야 합니다 — 이 작업에서 성공한 조회 도구 호출이 하나도 없습니다')
    if any(not e['verified'] for e in evidence):
        raise ValueError('인계안의 모든 조회 근거가 현재 작업의 성공한 실제 도구 호출과 일치해야 합니다 — '
                         + unmatched_evidence(output['evidence'], evidence, calls))


def reconcile_trace(repo, wi, form, output):
    """Derive a citation's actual query only from one identical, complete tool response.

    This does not repair the narrative or trust a model's guessed SQL. Ambiguous,
    truncated, altered or incomplete evidence is returned unchanged and must
    still pass the normal validator. The original output is never modified.
    """
    if (form or {}).get('contract') != DRAFT or not isinstance(output,dict) or not output.get('evidence'):
        return output, []
    from hydcommon.sql_read import guard
    calls = ask.tool_calls(repo.list_events(todo_id=wi['id']), repo.get_event_payload)
    verdict = ask.verdict(dict(answer=output.get('handover_summary'), evidence=output['evidence']), calls)
    checked = verdict.get('evidence') or []
    if len(checked) != len(output['evidence']):return output, []
    proposed = deepcopy(output)
    changes = []
    def same(left,right):
        try:return json.dumps(left,sort_keys=True,allow_nan=False)==json.dumps(right,sort_keys=True,allow_nan=False)
        except (ValueError,TypeError):return False
    for index, evidence in enumerate(output['evidence']):
        if checked[index].get('verified'):continue
        query=evidence.get('query');claimed=evidence.get('result')
        if (ask.short_tool(evidence.get('tool'))!='enterprise/query' or not isinstance(query,dict)
                or set(query)!={'sql'} or not isinstance(claimed,dict) or set(claimed)!={'result','document'}
                or claimed.get('result')!='ok' or not isinstance(claimed.get('document'),dict)):
            return output, []
        doc=claimed['document'];required={'statement','columns','rows','row_count'}
        if not required <= set(doc) or not isinstance(doc['rows'],list) or type(doc['row_count']) is not int:
            return output, []
        try:guard(query['sql'])
        except (ValueError,TypeError):return output, []
        candidates=[]
        for call in calls:
            actual=call.get('_input');response=ask._envelope(call.get('_output'))
            if (call.get('tool')!='enterprise/query' or call.get('ok') is not True or not call.get('output_complete')
                    or not isinstance(actual,dict) or set(actual)!={'sql'} or not isinstance(response,dict)
                    or response.get('result')!='ok' or not isinstance(response.get('document'),dict)):
                continue
            source=response['document']
            if source.get('at_row_limit') is not False or not all(k in source and same(v,source[k]) for k,v in doc.items()):
                continue
            try:
                if guard(actual['sql']) != source.get('statement'):continue
            except (ValueError,TypeError):continue
            candidates.append(call)
        if len(candidates)!=1:return output, []
        actual=candidates[0]['_input']
        proposed['evidence'][index]['query']=deepcopy(actual)
        changes.append({'index':index,'tool':'enterprise/query','call_id':candidates[0]['id'],
                        'original_query':deepcopy(query),'actual_query':deepcopy(actual)})
    if changes:
        result=ask.verdict(dict(answer=proposed.get('handover_summary'),evidence=proposed['evidence']),calls)
        if len(result.get('evidence') or [])!=len(proposed['evidence']) or not all(e['verified'] for e in result['evidence']):
            return output, []
    return proposed, changes
