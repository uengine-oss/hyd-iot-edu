import json

import pytest

from hydcommon.process_contracts import validate_output
from worker import outcome, prompt

FIELDS = [{'key':'decision','type':'object'}, {'key':'decision_id','type':'text'}]


def output(text):
    return {'decision': {'recommended':'skill:sop-pm-11','explanation':text}, 'decision_id':'DEC-test'}


@pytest.mark.parametrize('text', [
    '2026-10-26 20:55 야간 정비 시간에 단독 시행을 권고합니다.',
    '05:55에 시행합니다.',
    '2026-10-27T05:55:48에 시행합니다.',
    '2026-02-30T05:55:00+09:00에 시행합니다.',
    '2026-10-27T05:55:00+09:00 / 다음 대안은 06:55',
])
def test_ambiguous_or_invalid_clock_is_rejected_by_shared_and_worker_contract(text):
    with pytest.raises(ValueError, match='날짜·시간대'):
        validate_output({'fields_json':FIELDS},output(text))
    value=outcome.interpret(json.dumps(output(text)),FIELDS,versioned=True)
    assert not value.contract_met and 'window.starts_at' in value.mismatch_reason


@pytest.mark.parametrize('text', [
    '이번 예정된 정비 시간에 단독 시행합니다.',
    '2026-10-27T05:55:48.478475+09:00 에 시행합니다.',
    '2026-10-26T20:55:48Z 에 시행합니다.',
    '2026-10-26 20:55 UTC 정비 시간입니다.',
    '2026-10-27 05:55 (KST) 정비 시간입니다.',
    '2026-10-27 05:55(+09:00) 정비 시간입니다.',
    '2026-10-27T05:55:48+09:00에 시행합니다.',
    '2026-10-26T20:55Z까지 확인합니다.',
])
def test_explicit_source_times_and_window_names_are_valid(text):
    validate_output({'fields_json':FIELDS},output(text))


def test_other_business_forms_do_not_acquire_a_decision_contract():
    validate_output({'fields_json':[{'key':'notes','type':'text'}]}, {'notes':'05:55은 원문 인용'})


def test_time_instruction_is_present_in_correction_prompt():
    text=prompt.format_correction('날짜·시간대 필요',FIELDS)
    assert 'window.starts_at' in text and '추측하지' in text


def test_runner_corrects_ambiguous_time_in_same_session_without_new_decision(tmp_path):
    from pathlib import Path
    from cliagents import ExecEvent, ExecEventKind
    from worker.runner import Runner
    from test_worker import _repo, _settings, DEF_PATH
    definition=json.loads(DEF_PATH.read_text(encoding='utf8'))
    definition['forms']={'diagnose':{'fields_json':FIELDS}}
    activity=next(a for a in definition['activities'] if a['id']=='task:diagnose')
    activity['tool']='formHandler:diagnose'
    activity['outputData']=['decision','decision_id']
    path=tmp_path/'definition.json';path.write_text(json.dumps(definition),encoding='utf8')
    repo,inst=_repo(path)
    requests=[]
    answers=iter([output('2026-10-26 20:55에 시행합니다.'),output('2026-10-26T20:55:00Z에 시행합니다.')])
    def execute(provider,request,env):
        requests.append(request)
        yield ExecEvent(kind=ExecEventKind.RUN_START,session_id='same-decision-session')
        target=Path(request.workdir)/'output/result.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(next(answers)),encoding='utf8')
        yield ExecEvent(kind=ExecEventKind.RESULT,text='파일 작성 완료',session_id='same-decision-session')
    runner=Runner(_settings(tmp_path),repo,exec_fn=execute,schema_prompt='',resolve_provider=lambda _:object())
    assert runner.poll_once()==1
    row=next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:diagnose')
    assert row['status']=='SUBMITTED' and row['output']['decision_id']=='DEC-test'
    assert row['output']['decision']['explanation']=='2026-10-26T20:55:00Z에 시행합니다.'
    assert len(requests)==2 and requests[1].resume_session=='same-decision-session'
    assert '날짜·시간대' in requests[1].prompt and '조회나 분석을 다시 하지 말고' in requests[1].prompt
