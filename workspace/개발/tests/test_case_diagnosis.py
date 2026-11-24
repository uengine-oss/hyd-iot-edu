"""처리 건의 원인 진단 · 사건 카드 = 판단 엔진이 판단을 등록할 때 다시 한 진단(판단 기록 origin.diagnosis — dmn-mcp _submitted_diagnosis).

AI 가 결과 칸에 옮겨 적은 guide_card · cause 는 서버가 대조하지 않은 글이다. 전에는 그 guide_card 가 그대로 사건 카드(그래프의 진단 원인 ·
화면의 원인 후보와 잰 값)가 됐고, 결과의 cause 가 등록한 판단의 원인과 달라도 처리 건 값 · 지표의 판정 원인이 됐다(2026-11-22 탐사 N1).
AI 단계는 AI 가 부르는 판단 엔진 도구 그대로 한다(test_instances._dmn — 이 묶음의 실제 dmn-mcp): 단계 점유 → 원인 진단 → 판단 등록 → 결과.
"""
import uuid

import pytest

from conftest import COOLING
from procsvc import case_projection
from test_instances import _dmn


def _cooling_at_agent(world):
    """HYD-01 쿨러 오염(수업 강도)이 끝까지 진행된 설비 → 냉각 경보 → 처리 건 c3_cooling 의 AI 단계(아직 아무도 점유하지 않음)."""
    pattern, asset = COOLING
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.report(asset)
    tags = world.plant.tags(asset)
    alert, pid = world.raise_alert(pattern, asset, ts1=tags['TS1'], ce=tags['CE'])
    assert world.inst(pid)['proc_def_id'] == 'c3_cooling'
    return alert, pid


@pytest.mark.parametrize('written', ['판단과 같은 원인', '다른 원인'])
def test_사건_카드와_처리_건의_원인은_AI가_옮겨_적은_글이_아니라_판단_엔진이_등록할_때_한_진단이다(world, written):
    alert, pid = _cooling_at_agent(world)
    consumer = 'diagnosis-test:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    scope = {'tenant': 'hyd', 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
             'version': world.inst(pid)['proc_def_version'], 'consumer': consumer}
    with world.reporting():
        # 설비는 1초마다 보고한다 — 경보 접수 · 처리 건 열기에 걸린 몇 초 동안 빈 근거 구간을 진단 전에 채운다(전에는 한 묶음의 첫 시험에서 근거 구간
        # 끝이 비어 진단이 보류되고 판단 등록이 원인 없이 거절됐다 — _decided_by_engine 과 같은 차례)
        world.report(alert['asset'])
        diag = _dmn(world, 'diagnose', asset=alert['asset'], pattern=alert['pattern'], alert_id=alert['alertId'])
        assert diag.get('withheld') is False and diag.get('top_cause'), {k: diag.get(k) for k in ('withheld', 'evidence_status', 'freshness')}
        world.report(alert['asset'])          # 설비는 1초마다 상태를 보고한다 — 판단 등록은 15초 안의 설비 상태만 쓴다(진단이 그보다 오래 걸렸다)
        made = _dmn(world, 'submit_decision', asset=alert['asset'], pattern=alert['pattern'], cause=diag['top_cause'],
                    failure_mode=diag['failure_mode'], incident=world.values(pid)['incident'], alert_id=alert['alertId'], process_scope=scope)
    dx = world.main.book[made['id']]['origin']['diagnosis']
    others = [c['id'] for c in diag['causes'] if c['id'] != diag['top_cause']]
    assert others, f'냉각 경보의 원인 후보가 하나뿐이라 다른 원인을 적어 볼 수 없다: {diag["causes"]}'
    # AI 가 옮겨 적으며 바꾼 가이드 카드 — 1순위를 다른 원인으로 적었다. 사건 카드 · 화면의 근거가 이것을 따르면 안 된다
    forged = dict(diag['card'], topCause=others[0], skills=[{'id': 'skill:forged', 'name': '지어낸 조치'}])
    cause = diag['top_cause'] if written == '판단과 같은 원인' else others[0]
    output = {'cause': cause, 'failure_mode': diag['failure_mode'], 'guide_card': forged,
              'decision': {'recommended': made['recommended']}, 'decision_id': made['id']}
    assert world.rt.repo.save_task_result(wi['id'], output, True, consumer)
    world.poll()
    card = world.incident(pid).card
    if written == '판단과 같은 원인':
        assert world.row(pid, 'T_agent')['status'] == 'DONE'
        assert (card['source'], card['decision'], card['topCause'], card['failureMode']) == ('decision', made['id'], dx['top_cause'], dx['failure_mode']), card
        assert card['causes'] == dx['causes'] and 'skills' not in card, card
        # 화면이 그리는 칸(잰 값의 태그 · 관측 구간, 원인의 고장 유형 · 증상)이 서버 진단에도 있다 — 진단 도구가 낸 값 그대로
        said = {c['id']: c for c in diag['causes']}
        assert all((c['failureModeId'], c['symptoms']) == (said[c['id']]['failureModeId'], said[c['id']]['symptoms']) and c['symptoms']
                   for c in dx['causes']), dx['causes']
        evidence = {e['id']: e for c in diag['causes'] for e in c['evidence']}
        # 관측 구간(coverage)은 진단할 때마다 다시 잰 값(표본 수 · 가장 긴 틈)이라 판단 등록 때의 것이다 — 칸이 있고 그 창을 다 봤는지만 견준다
        assert all(e['tag'] == evidence[e['id']]['tag'] and e['tag'] and ('coverage' in e) == ('coverage' in evidence[e['id']])
                   and (e['coverage']['covered'] is True if 'coverage' in e else True)
                   for c in dx['causes'] for e in c['evidence']), dx['causes']
        assert any('coverage' in e for c in dx['causes'] for e in c['evidence']), '시계열 창 근거의 관측 구간이 서버 진단에 없다'
        assert case_projection.incident_params(world.incident(pid))['cause'] == dx['top_cause']        # 그래프에 진단 원인으로 투영되는 값
        assert world.values(pid)['cause'] == dx['top_cause']
    else:
        row = world.row(pid, 'T_agent')
        assert row['status'] != 'DONE' and '이 단계가 등록한 판단' in (row.get('log') or '') and others[0] in row['log'], (row['status'], row.get('log'))
        assert world.values(pid).get('cause') is None, '판단과 다른 원인이 처리 건 값이 됐다'
        assert card.get('topCause') is None and card.get('source') is None, card                   # 사건 카드는 바뀌지 않았다
