"""지식 관리 검사(procsvc/kgadmin.py) — 조치 방법(스킬 = SOP) 고치기 · 새로 만들기, 영향 연결 한 벌(관리 화면 · 문서 검토 공통 — P2-12).
검사 문장은 학생에게 그대로 보인다: 합니다체, 화면 말(영문 칸 이름 없음 — P2-19)."""
import re

import pytest

from procsvc import kgadmin


def new_skill(**over):
    return {**dict(name='쿨러 팬 최대 운전', sopId='SOP-COOL-11', steps=['팬을 100 %로 올린다.'], failureMode='fm:cooler-cooling-loss'), **over}


def test_새_조치_방법은_SOP_번호_단계_고장_유형_관계로_만든다():
    out = kgadmin.validate_skill(new_skill(relation='MITIGATED_BY', kind='control', approver='role:operator'), create=True)
    assert (out['sopId'], out['steps'], out['failureMode'], out['relation'], out['kind'], out['approver']) == \
        ('SOP-COOL-11', ['팬을 100 %로 올린다.'], 'fm:cooler-cooling-loss', 'MITIGATED_BY', 'control', 'role:operator')


def test_관계와_종류를_적지_않으면_근본_조치_작업지시다():
    out = kgadmin.validate_skill(new_skill(), create=True)
    assert (out['relation'], out['kind']) == ('REMEDIED_BY', 'work_order')


@pytest.mark.parametrize('name, over, says', [
    ('이름 없음', dict(name=''), '이름이 비어'),
    ('이름 81자', dict(name='가' * 81), '80자'),
    ('SOP 번호 소문자', dict(sopId='sop.fan.05'), 'SOP-'),
    ('단계 없음', dict(steps=[]), '절차 단계'),
    ('고장 유형 없음', dict(failureMode=''), '고장 유형'),
    ('종류 틀림', dict(kind='robot'), '설비 명령'),
    ('관계 틀림', dict(relation='CAUSES'), 'MITIGATED_BY'),
    ('구매 칸을 고장 조치에', dict(parts=['part:x']), '구매'),
    ('업무 범위 틀림', dict(scope='hr'), '업무 범위'),
])
def test_새_조치_방법의_잘못된_칸은_학생이_읽을_합니다체_문장으로_거절한다(name, over, says):
    with pytest.raises(ValueError) as refused:
        kgadmin.validate_skill(new_skill(**over), create=True)
    text = str(refused.value)
    assert says in text and not re.search(r'(이다|있다|한다)\b|\(failureMode\)', text)


def test_80자_이름은_받는다():
    assert kgadmin.validate_skill(new_skill(name='가' * 80), create=True)['name'] == '가' * 80


def test_조치_방법_고치기는_고장_유형을_다시_이을_수_있고_구매_SOP는_매뉴얼_검토_길에서만_다룬다():
    out = kgadmin.validate_skill({'name': '이름', 'failureMode': 'fm:x'})
    assert (out['failureMode'], out['relation']) == ('fm:x', 'REMEDIED_BY')
    with pytest.raises(ValueError, match='매뉴얼'):
        kgadmin.validate_skill({'name': '이름', 'scope': 'purchase', 'executable': True, 'parts': ['part:x'],
                                'actions': [{'action': 'action:purchase-request', 'value': None}], 'supplier_policy': 'oem'})


def test_원문_정책은_원문_검토_생성_길에서만_붙인다():
    with pytest.raises(ValueError, match='매뉴얼 검토 생성'):
        kgadmin.validate_skill(new_skill(maintenance_policy={'version': 1}), create=True, source_backed=False)


# ---------------------------------------------------------------- 영향 연결(한 벌)
@pytest.mark.parametrize('value, want', [
    (None, []),
    ([], []),
    ([{'target': 'sv:ts1', 'sign': '-'}], [('sv:ts1', 'StateVariable', -1)]),
    ([{'target': 'msr:maint-cost', 'sign': 1, 'note': '부품비'}], [('msr:maint-cost', 'Measure', 1)]),
    ([{'target': f'sv:a{i}', 'sign': '+'} for i in range(kgadmin.AFFECTS_MAX)], [(f'sv:a{i}', 'StateVariable', 1) for i in range(kgadmin.AFFECTS_MAX)]),
], ids=['없음', '빈 목록', '상태 변수', '성과 지표', '한도 개수'])
def test_영향_연결은_대상_종류와_방향을_정해_돌려준다(value, want):
    assert [(a['target'], a['label'], a['sign']) for a in kgadmin.validate_affects(value, 'SOP-X')] == want


@pytest.mark.parametrize('value, says', [
    ('sv:ts1', '목록'),
    ([{'target': f'sv:a{i}', 'sign': '+'} for i in range(kgadmin.AFFECTS_MAX + 1)], f'최대 {kgadmin.AFFECTS_MAX}개'),
    (['sv:ts1'], '객체'),
    ([{'target': 'sv:TS1', 'sign': '+'}], '소문자'),
    ([{'target': 'part:seal', 'sign': '+'}], '상태 변수'),
    ([{'target': 'sv:ts1', 'sign': '?'}], '방향'),
    ([{'target': 'sv:ts1', 'sign': '+'}, {'target': 'sv:ts1', 'sign': '-'}], '두 번'),
], ids=['목록 아님', '한도 넘음', '항목이 객체 아님', '대문자 id', '다른 종류 id', '방향 틀림', '같은 대상 두 번'])
def test_잘못된_영향_연결은_SOP_번호와_함께_거절한다(value, says):
    with pytest.raises(ValueError) as refused:
        kgadmin.validate_affects(value, 'SOP-X')
    assert str(refused.value).startswith('SOP-X: ') and says in str(refused.value)


def test_영향_메모는_300자까지_남긴다():
    [one] = kgadmin.validate_affects([{'target': 'sv:ts1', 'sign': '+', 'note': '가' * 400}])
    assert len(one['note']) == 300


def test_관리_화면의_조치_방법_고치기도_같은_영향_규칙을_쓴다():
    out = kgadmin.validate_skill({'name': '이름', 'affects': [{'target': 'sv:ts1', 'sign': '-'}]})
    assert out['affects'] == kgadmin.validate_affects([{'target': 'sv:ts1', 'sign': '-'}])
    with pytest.raises(ValueError, match='소문자'):
        kgadmin.validate_skill({'name': '이름', 'affects': [{'target': 'sv:TS1', 'sign': '-'}]})


@pytest.mark.parametrize('sop, skill', [('SOP-FAN-05', 'skill:sop-fan-05'), ('SOP-PM-2-9', 'skill:sop-pm-2-9')])
def test_조치_방법_id는_SOP_번호에서_만든다(sop, skill):
    assert kgadmin.skill_id(sop) == skill


@pytest.mark.parametrize('line, ok', [('### SOP-COOL-11 팬 최대 운전', True), ('## HM-8.1 쿨러 팬 벨트 점검', False), ('SOP-cool-1 소문자', False)])
def test_절차_제목_줄은_대문자_SOP_번호와_이름이다(line, ok):
    assert bool(kgadmin.SOP_RE.match(line)) is ok
