"""교대 인수인계 계약(procsvc/handover.py) — 시작 입력 · 인계안 네 영역 · 근거 번호 · 인계자/인수자 선택."""
import pytest

from procsvc import handover as h

START = {'asset': 'HYD-01', 'shift_label': '야간 → 주간', 'as_of': '2026-10-30T06:00:00+09:00', 'work_notes': '쿨러 정비 완료라고 전달받음'}


@pytest.mark.parametrize('values, error', [
    (START, None),
    (dict(START, asset='아무 설비'), '없는 설비입니다: 아무 설비'),
    (dict(START, extra='x'), '설비·교대·기준시각·작업 메모만'),
    ({k: v for k, v in START.items() if k != 'work_notes'}, '설비·교대·기준시각·작업 메모만'),
    (dict(START, shift_label='  '), '비어 있거나 한도를 넘었습니다: shift_label'),
    (dict(START, work_notes='가' * 4001), '한도를 넘었습니다: work_notes'),
    (dict(START, as_of='2026-10-30T06:00:00'), '시간대가 포함된 ISO 시각'),
    (dict(START, as_of='어제 밤'), '시간대가 포함된 ISO 시각'),
], ids=['정상', '없는 설비', '모르는 칸', '빠진 칸', '빈 교대 이름', '메모 4001자', '시간대 없음', '시각 아님'])
def test_인수인계_시작은_있는_설비와_시간대가_있는_기준시각만_받는다(values, error):
    """P4-23: 전에는 설비 칸이 아무 글이나 받아 없는 설비로 인계안을 만들었다(AI 호출 낭비)."""
    if error is None:
        h.validate_start(values)
    else:
        with pytest.raises(ValueError, match=error):
            h.validate_start(values)


def _check(area, state='observed', refs=(0,)):
    return {'area': area, 'state': state, 'finding': f'{area} 확인', 'next_action': '다음 근무자가 볼 것', 'evidence_indices': list(refs)}


EVIDENCE = [{'tool': 'enterprise/query', 'query': {'sql': 'select 1'}, 'result': '1행'}]
DRAFT = {'handover_summary': '요약', 'evidence': EVIDENCE,
         'checks': [_check('equipment'), _check('work_orders'), _check('parts'), _check('work_notes', refs=())]}


def _draft(**changes):
    return dict(DRAFT, **changes)


@pytest.mark.parametrize('output, error', [
    (DRAFT, None),
    (_draft(text='전송 글', cliagents_session_id='s1'), None),
    (_draft(extra=1), 'handover_summary·checks·evidence만'),
    (_draft(checks=DRAFT['checks'][:3]), '각각 한 번씩'),
    (_draft(checks=DRAFT['checks'][:3] + [_check('equipment')]), '각각 한 번씩'),
    (_draft(checks=DRAFT['checks'][:3] + [_check('work_notes', state='done')]), 'observed·needs_check·conflict'),
    (_draft(checks=[_check('equipment', refs=(5,))] + DRAFT['checks'][1:]), '유효한 번호'),
    (_draft(checks=[_check('equipment', refs=())] + DRAFT['checks'][1:]), '확인 필요\\(needs_check\\)로'),
    (_draft(checks=[_check('equipment', state='needs_check', refs=())] + DRAFT['checks'][1:]), None),
    (_draft(evidence=EVIDENCE * 41), '40개 이하'),
], ids=['정상', '전송 칸은 무시', '모르는 칸', '영역 셋', '영역 겹침', '모르는 상태', '없는 근거 번호', '근거 없이 확인됨', '근거 없으면 확인 필요', '근거 41개'])
def test_인계안은_네_영역을_한_번씩_근거_번호와_함께_낸다(output, error):
    form = {'contract': h.DRAFT}
    if error is None:
        h.validate_result(form, {}, output)
    else:
        with pytest.raises(ValueError, match=error):
            h.validate_result(form, {}, output)


@pytest.mark.parametrize('contract, output, error', [
    (h.SENDER, {'sender_decision': 'approve', 'sender_notes': '확인함'}, None),
    (h.SENDER, {'sender_decision': 'confirm', 'sender_notes': '확인함'}, '선택이 올바르지 않습니다'),
    (h.RECEIVER, {'receiver_decision': 'confirm', 'receiver_notes': '받음', 'communication_only': True}, None),
    (h.RECEIVER, {'receiver_decision': 'confirm', 'receiver_notes': '받음'}, '설비 조치·발주·정비 완료가 아님'),
    (h.RECEIVER, {'receiver_decision': 'revise', 'receiver_notes': ' '}, '사유를 적으세요'),
], ids=['인계자 승인', '인계자에게 없는 선택', '인수 확인', '전달만이라는 확인 없음', '빈 보완 사유'])
def test_인계자와_인수자의_선택은_정해진_값과_사유만_받는다(contract, output, error):
    if error is None:
        h.validate_result({'contract': contract}, {}, output)
    else:
        with pytest.raises(ValueError, match=error):
            h.validate_result({'contract': contract}, {}, output)


@pytest.mark.parametrize('contract, optional', [(h.DRAFT, {'sender_notes', 'receiver_notes'}), (h.SENDER, {'receiver_notes'}),
                                                (h.RECEIVER, set()), (None, set())],
                         ids=['인계안 작성', '인계자 검토', '인수자 확인', '다른 폼'])
def test_보완_메모는_그_단계가_받을_때만_선택_입력이다(contract, optional):
    assert h.optional_inputs({'contract': contract}) == optional
