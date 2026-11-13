"""문서 추출 제안 계약(procsvc/manual_extraction.py) — AI(또는 강사 서명 묶음)의 제안을 원문 인용 · 절 · 단계 · 지식으로 검사하고, 원문이 정한
기준(예측 유온 경고 · 감점 · 구매 총비용 비교)을 빠뜨린 제안을 교정 사유로 돌려보낸다. 제안 표본은 강사 서명 묶음의 검토본이고 원문은 실제 보관소에
올린 제공 문서다. 처리 건 쪽(start · result)은 test_manual_api 의 API 끝까지 시험이 본다."""
from copy import deepcopy

import pytest

import class_knowledge
from procsvc import manual_extraction as mx, manual_segments
from procsvc.manual_sources import ManualSources

DOCS = {item['doc']: item for item in class_knowledge.reviewed()}


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite3')


def proposal_of(archive, doc):
    item = DOCS[doc]
    source = archive.save('hyd', item['filename'], item['raw'])
    return source, class_knowledge.rebased(deepcopy(item['proposal']), source['source_id'])


@pytest.mark.parametrize('doc', sorted(DOCS))
def test_강사_검토본은_원문_인용_계약과_내용_검사를_모두_지난다(archive, doc):
    source, proposal = proposal_of(archive, doc)
    checked = mx.validate_proposal(source, proposal)
    assert mx.content_issues(checked, source, None, criteria_scope=True, package_scope=True, forecast_scope=True) == []


def test_원문이_정한_예측_유온_경고를_빠뜨린_냉각_제안은_교정_사유가_된다(archive):
    """P2-02: 지운 시작 사본이 바로 이 규칙 없이 학생 PC에 들어가 있었다."""
    source, proposal = proposal_of(archive, 'HM-8')
    proposal['knowledge']['rules'] = [r for r in proposal['knowledge']['rules'] if r['id'] != 'rule:cooler-forecast-temperature-warning']
    issues = mx.content_issues(mx.validate_proposal(source, proposal), source, None)
    assert any('예측 유온 55 ℃' in i for i in issues)


def test_앞_단계까지_품은_단계_인용은_그_단계_문장만_인용하라고_거절한다(archive):
    """P2-02: 지운 시작 사본의 PM-02 SOP-PM-22 단계 4 인용이 앞 단계 2~3줄까지 품었다(묶음 검토가 고친 자리)."""
    source, proposal = proposal_of(archive, 'PM-02')
    sop = next(p for p in proposal['procedures'] if p['id'] == 'SOP-PM-22')
    prev, last = sop['steps'][-2]['anchor'], sop['steps'][-1]['anchor']
    text = source['pages'][0]['text']
    wide = text[prev['start']:last['end']]
    sop['steps'][-1]['anchor'] = {'source_id': source['source_id'], 'page': 1, 'quote': wide}
    with pytest.raises(ValueError, match='다른 단계'):
        mx.validate_proposal(source, proposal)


def test_원문이_정한_감점을_규칙으로_옮기지_않은_제안은_그_문장을_짚어_돌려보낸다(archive):
    source, proposal = proposal_of(archive, 'HM-8')
    proposal['knowledge']['rules'] = [r for r in proposal['knowledge']['rules'] if r.get('effect') != 'PENALTY']
    issues = mx.content_issues(mx.validate_proposal(source, proposal), source, None)
    assert any('감점 규칙이 없습니다' in i and '만 원' in i for i in issues)


def test_원문의_구매_총비용_기준이_있는데_실행_구매_절차에_정책이_없으면_돌려보낸다(archive):
    source, proposal = proposal_of(archive, 'PR-07')
    for p in proposal['procedures']:
        (p.get('link') or {}).pop('purchase_comparison_policy', None)
    issues = mx.content_issues(mx.validate_proposal(source, proposal), source, None)
    assert any('purchase_comparison_policy' in i for i in issues)


def _unknown_top(p):
    p['rules'] = []


def _foreign_source(p):
    p['source_id'] = 'manual:other'


def _missing_page_review(p):
    p['page_reviews'] = []


def _dup_sop(p):
    p['procedures'].append(deepcopy(p['procedures'][0]))


def _bad_sop_id(p):
    p['procedures'][0]['id'] = 'SOP-cool.1'


def _gap(p):
    p['procedures'][0]['steps'][0]['order'] = 3


@pytest.mark.parametrize('change, says', [
    (_unknown_top, '정해지지 않은 칸'), (_foreign_source, '원문 판본'), (_missing_page_review, '검토 기록이 없는'),
    (_dup_sop, 'SOP ID 중복'), (_bad_sop_id, 'SOP ID 형식'), (_gap, '1부터 연속'),
], ids=['맨 위 칸 rules', '다른 원문', '쪽 검토 기록 없음', 'SOP 겹침', 'SOP 번호 꼴', '단계 번호 건너뜀'])
def test_계약에_맞지_않는_제안은_에이전트가_고칠_수_있게_까닭을_준다(archive, change, says):
    source, proposal = proposal_of(archive, 'HM-8')
    change(proposal)
    with pytest.raises(ValueError, match=says):
        mx.validate_proposal(source, proposal)


def test_정책이_불완전하면_거부하지_않고_그_정책만_빼고_경고한다(archive):
    source, proposal = proposal_of(archive, 'PR-07')
    p = next(p for p in proposal['procedures'] if (p.get('link') or {}).get('purchase_comparison_policy'))
    p['link']['purchase_comparison_policy'] = {'version': 1}
    checked = mx.validate_proposal(source, proposal)
    assert 'purchase_comparison_policy' not in next(x for x in checked['procedures'] if x['id'] == p['id'])['link']
    assert any(p['id'] in w and '정책 제외' in w for w in checked['warnings'])


def test_절_제목에_절_번호를_넣은_제안은_번호를_빼라고_돌려보낸다(archive):
    source, proposal = proposal_of(archive, 'HM-8')
    s = proposal['sections'][0]
    s['title'] = s['ref'] + ' ' + s['title']
    assert any('절 번호' in i for i in mx.content_issues(mx.validate_proposal(source, proposal), source, None))


@pytest.mark.parametrize('feedback, ok', [
    (None, True),
    ({'items': [{'target': 'SOP-COOL-11', 'verdict': 'OK'}]}, False),            # 검토자 이름 없음
    ({'by': '강사', 'items': [{'target': 'SOP-COOL-11', 'verdict': 'WRONG', 'note': '단계 3 빠짐'}]}, True),
    ({'by': '강사', 'items': [{'target': 'SOP-COOL-11', 'verdict': 'WRONG'}]}, False),   # 이유 없음
    ({'by': '강사', 'items': [{'target': 'x', 'verdict': 'MAYBE', 'note': 'n'}]}, False),
    ({'by': '강사', 'items': [{'target': f't{i}', 'verdict': 'OK'} for i in range(mx.REVIEW_FEEDBACK_MAX + 1)]}, False),
], ids=['없음', '검토자 없음', '정상', '이유 없음', '없는 판정', '항목 수 초과'])
def test_사람_검토_의견은_정해진_꼴만_다음_추출에_싣는다(feedback, ok):
    if ok:
        mx.validate_review_feedback(feedback)
    else:
        with pytest.raises(ValueError):
            mx.validate_review_feedback(feedback)


def test_구간_작업은_담당_구간의_원문만_본다(archive):
    big = ('# 1장\n' + '가' * 3000 + '\n# 2장\n' + '나' * 3000).encode()
    source = archive.save('hyd', 'big.md', big)
    seg = manual_segments.segments(source, 4000)[1]
    view = mx.segment_view(source, seg)
    assert view['source_id'] == source['source_id'] and view['pages'][0]['text'].startswith('# 2장')


@pytest.mark.parametrize('filename, raw, name', [('a.md', b'# HM-8 \xec\xbf\xa8\xeb\x9f\xac\n', 'HM-8 쿨러'), ('a.txt', b'plain\n', 'a.txt')])
def test_처리_건_이름은_마크다운이면_첫_제목_아니면_파일_이름이다(archive, filename, raw, name):
    assert mx.display_name(archive.save('hyd', filename, raw)) == name


def test_추출_정의는_판본과_계약을_싣는다():
    d = mx.definition()
    assert (d['processDefinitionId'], d['version'], d['forms']['manual_proposal']['contract']) == (mx.DEFINITION_ID, mx.VERSION, mx.CONTRACT)


@pytest.mark.parametrize('version, at_least', [('2.18', True), ('2.13', True), ('2.12', False), ('10.0', True), ('2.x', False), (None, False)])
def test_판본_문턱은_그_판_이후_실행에만_내용_검사를_건다(version, at_least):
    assert mx.contract_at_least({'proc_def_version': version}, mx.CRITERIA_FROM) is at_least


def test_판본마다_받는_내용_검사가_정해진다():
    assert mx.scopes({'proc_def_version': '2.16'}) == dict(criteria_scope=True, package_scope=True, forecast_scope=False)
