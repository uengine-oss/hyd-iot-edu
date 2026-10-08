"""Actual stack: change PLC mode AFTER cards exist, then attempt that old choice.

Writes only this run's simulated plant/approval and preserves failed observations.
The expected boundary is rejection before action.cmd, not merely PLC refusal.
"""
import argparse
import json
from pathlib import Path
import time

import scenario_instance_test as s


def main(destination):
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    report = {'checks': []}
    pid = None

    def save(name, value):
        (out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    def check(name, passed, detail=None):
        report['checks'].append(dict(name=name, passed=bool(passed), detail=detail))
        save('report', report)
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)

    try:
        mode = s.get(s.PROCESS + '/api/process/mode')
        assert mode['mode'] == 'instance' and mode['agent_bridge'] == 'legacy', mode
        s.post(s.PLANT + '/api/reset')
        time.sleep(2)
        s.post(s.PLANT + '/api/fault', {'asset': 'HYD-01', 'type': 'cooler_degradation'})
        detector, _ = s.wait_for(lambda: (v if (v := s.get(s.DETECTOR + '/api/detector/state')['assets'].get('HYD-01', {})).get('phase') == 'RAISED' else None), 200)
        assert detector, 'no raised alert'
        inst, _ = s.wait_for(lambda: s.instance_for(detector['alert_id']), 30)
        assert inst, 'no instance'
        pid = inst['proc_inst_id']
        report.update(instance=pid, incident=s.variables(inst).get('incident'))
        save('opened-instance', s.view(pid))
        rows, _ = s.wait_for(lambda: (v if (v := s.items(pid)).get('task:select', {}).get('status') == 'IN_PROGRESS' else None), 120)
        assert rows, 'selection not reached'
        before = s.view(pid)
        variables = s.variables(before['instance'])
        inc_id = variables['incident']
        decision = s.get(s.PROCESS + '/api/decisions/' + variables['decision_id'])
        save('before-instance', before)
        save('decision', decision)
        report.update(instance=pid, incident=inc_id, decision=decision['id'])
        option = next(o for o in decision['options'] if o['id'] == 'skill:fan-max-derate')
        assert option['feasible'], option
        assessment_input = {'decision': decision, 'option': option['id'], 'role': 'role:prod-mgr'}
        baseline = s.post(s.H + ':8091/api/agent/approval-check', assessment_input, timeout=25)
        save('baseline-assessment', baseline)
        check('same card is allowed before the mode change', baseline.get('allowed') is True, baseline.get('reasons'))
        changed_value = s.post(s.PROCESS + '/api/todolist/' + rows['task:select']['id'] + '/select',
                        {'decision':decision['id'], 'option':option['id'], 'by':'[회귀 검사] 바뀐 조치 검사기',
                         'role':'role:prod-mgr', 'fan_pct':95, 'reason':'[회귀 검사] 바뀐 값은 아직 검토되지 않음'})
        save('unreviewed-action',changed_value)
        check('different fan value cannot reuse the default-card forecast',changed_value.get('error') in (400,409)
              and '조치값' in changed_value.get('body',''),changed_value)
        check('unreviewed value leaves selection open and creates no command',
              s.items(pid)['task:select']['status']=='IN_PROGRESS'
              and s.get(s.PROCESS+'/api/incidents/'+inc_id).get('cmdId') is None)
        s.post(s.PLANT + '/api/mode', {'asset': 'HYD-01', 'mode': 'REMOTE_MANUAL'})
        current, _ = s.wait_for(lambda: (v if (v := s.get(s.PROCESS + '/api/plant/HYD-01/status')).get('mode') == 'REMOTE_MANUAL' else None), 15)
        assert current, 'mode not visible to process'
        save('current-plant', current)
        result = s.post(s.PROCESS + '/api/todolist/' + rows['task:select']['id'] + '/select',
                        {'decision': decision['id'], 'option': option['id'], 'by': '[회귀 검사] 지난 승인 검사기',
                         'role': 'role:prod-mgr', 'reason': '[회귀 검사] 지난 운전 모드 검증'})
        save('approval-response', result)
        check('changed mode is rejected before approval acceptance', result.get('error') in (400, 409), result)
        after = s.get(s.PROCESS + '/api/incidents/' + inc_id)
        check('no command identity created for stale choice', after.get('cmdId') is None, after.get('cmdId'))
        check('human selection remains open after rejection', s.items(pid)['task:select']['status'] == 'IN_PROGRESS')
        if after.get('cmdId'):
            terminal, _ = s.wait_for(lambda: (v if (v := s.get(s.PROCESS + '/api/incidents/' + inc_id)).get('terminal') else None), 45)
            save('after-incident', terminal or after)
            save('gateway', s.get('http://localhost:8090/api/gateway/log'))
        else:
            save('after-incident', after)
        save('after-instance', s.view(pid))
        save('audit', s.get(s.PROCESS + '/api/audit'))
        s.post(s.PLANT + '/api/mode', {'asset': 'HYD-01', 'mode': 'REMOTE_AUTO'})
        restored, _ = s.wait_for(lambda: (v if (v := s.get(s.PROCESS + '/api/plant/HYD-01/status')).get('mode') == 'REMOTE_AUTO' else None), 15)
        assert restored, 'restored mode not visible to process'
        reassessed = s.post(s.H + ':8091/api/agent/approval-check', assessment_input, timeout=25)
        save('restored-assessment', reassessed)
        # Mode restoration does not roll back physical heating. A030 predicts
        # from current TS1: the old consent can still require review for that
        # independently observed adverse change. Do not loosen the model gate.
        reasons=reassessed.get('reasons') or []
        check('mode restoration clears mode exclusion without ignoring adverse prediction changes',
              reassessed['facts']['plc_mode']=='REMOTE_AUTO' and reassessed['current_option']['feasible']
              and (reassessed.get('allowed') is True or (bool(reasons) and all(
                  reason.startswith(('예측 ts1 ', '예측 ts1_peak ', '예측 vs1 ', '예측 vs1_peak ')) for reason in reasons))),reasons)
        fresh=s.post(s.H+':8091/api/agent/decide',{'asset':decision['asset'],'pattern':decision['origin']['pattern']},timeout=25)
        save('fresh-readonly-evaluation',fresh)
        fresh_decision=dict(fresh,options=fresh['result']['options'])
        fresh_assessment=s.post(s.H+':8091/api/agent/approval-check',
            {'decision':fresh_decision,'option':option['id'],'role':'role:prod-mgr'},timeout=25)
        save('fresh-assessment',fresh_assessment)
        check('new read-only evaluation reflects current inputs and passes assessment',fresh_assessment.get('allowed') is True,
              fresh_assessment.get('reasons'))
    finally:
        # Preserve the failed state first. A new process can inspect every event.
        if pid:
            view = s.view(pid)
            save('final-observed-instance', view)
            review = next((w for w in view['workitems'] if w['activity_id'] == 'task:escalate' and w['status'] == 'IN_PROGRESS'), None)
            if review:
                save('fixture-review', s.post(s.PROCESS + '/api/todolist/' + review['id'] + '/submit',
                     {'by': '[회귀 검사] 지난 승인 검사기', 'output': {'note': '[회귀 검사] 실제 반례 상태와 명령 거절을 보존하고 시험을 종료함'}}))
        save('plant-reset', s.post(s.PLANT + '/api/reset'))
        save('report', report)
    raise SystemExit(0 if report['checks'] and all(c['passed'] for c in report['checks']) else 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    main(parser.parse_args().out)
