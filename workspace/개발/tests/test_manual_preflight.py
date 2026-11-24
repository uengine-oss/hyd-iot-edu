"""적재 전 기계 검사(procsvc/manual_preflight.py) — 검토 화면이 보이는 검사(무엇이 지금 지식에 없는지 · 판단이 이 절차를 후보로 낼 길이 있는지 ·
정기 정비 · 구매 실행에 필요한 원문 정책). 사람 검토도 적재 허락도 아니다. 실제 그래프(kg-seed 가 끝난 그래프)의 카탈로그와 강사 서명 묶음의
검토본으로 판정한다. 검사 문장은 학생에게 보이므로 화면 말이다(P2-19)."""
import re
from copy import deepcopy

import pytest

import class_knowledge
from procsvc import manual_knowledge, manual_preflight

DOCS = {i['doc']: i for i in class_knowledge.reviewed(order=class_knowledge.ORDER + ('HI-01',))}     # 서명 묶음의 문서 넷(HI-01 = 참고 절차)


@pytest.fixture
def catalog(seeded_graph, pg_dsn):
    """kg-seed 뒤 업무 DB 의 공급사 · 견적을 그래프로 옮긴 카탈로그(시작이 지식 적재 전에 하는 것과 같다)."""
    import psycopg
    from hydcommon import graphdb
    from procsvc import scm_sync
    scm_sync.sync(lambda cypher, **params: seeded_graph.query(cypher, **params), lambda: psycopg.connect(pg_dsn))
    with graphdb.connect() as driver, driver.session() as session:
        return manual_knowledge.catalog(session)


def proposal(doc):
    return deepcopy(DOCS[doc]['proposal'])


def codes(result):
    return {i['code'] for i in result['issues']}


@pytest.mark.parametrize('doc', sorted(DOCS))
def test_강사가_서명한_묶음에는_후보_규칙이_없다는_검토_필요가_없다(catalog, doc):
    """서명한 묶음에서 이 항목이 「검토 필요」로 늘 뜨면 학생이 맞는 추출을 고칠 곳으로 읽는다(사용자 2026-11-14). 정비 묶음이 부르는 절차
    (PM-02 의 SOP-PM-21~23)는 알리지 않고, 같은 원인의 다른 절차가 후보로 나오는 절차는 참고로만 알린다."""
    result = manual_preflight.validate(proposal(doc), catalog)
    assert [i for i in result['issues'] if i['code'] == 'CANDIDATE_RULE_MISSING'] == [], result['issues']


def test_점검_뒤에_이어지는_교체는_검토_필요가_아니라_참고로_알린다(catalog):
    """HM-8: 벨트 교체(SOP-FAN-12)는 점검(SOP-FAN-11)이 후보로 나오는 원인을 함께 맡는다(문서: 「기준을 벗어나면 교체한다」). 이어지는 절차인지
    빠뜨린 대안인지는 검사기가 가를 수 없다 — 지우지 않고 참고로 남겨 사람이 정한다."""
    result = manual_preflight.validate(proposal('HM-8'), catalog)
    notes = [(n['code'], n['sop'], n['siblings']) for n in result['notices']]
    assert notes == [('CANDIDATE_NOT_DIRECT', 'SOP-FAN-12', ['SOP-FAN-11'])], result['notices']


def test_같은_원인의_어느_절차도_후보로_나오지_않으면_검토_필요로_알린다(catalog):
    """PBL 문서에서 원인 하나의 조치가 통째로 후보에서 빠지면 판단이 보류된다(2026-10-23 리허설) — 참고로 낮추지 않는다."""
    p = proposal('HM-8')
    gone = {'SOP-FAN-11', 'SOP-FAN-12'}
    for r in p['knowledge']['rules']:
        if r.get('table') == 'dt:action-candidates':
            r['outputs'] = [o for o in r.get('outputs') or [] if o not in gone]
    result = manual_preflight.validate(p, catalog)
    found = {i['sop'] for i in result['issues'] if i['code'] == 'CANDIDATE_RULE_MISSING'}
    assert gone <= found and not [n for n in result['notices'] if n['sop'] in gone], (result['issues'], result['notices'])


def test_지금_지식에_없는_고장_유형을_가리키면_칸_이름과_함께_알린다(catalog):
    p = proposal('HM-8')
    p['procedures'][0]['link']['failureMode'] = 'fm:no-such-mode'
    result = manual_preflight.validate(p, catalog)
    found = [i for i in result['issues'] if i['code'] == 'REFERENCE_NOT_FOUND']
    assert found and '고장 유형 칸에 적은 fm:no-such-mode' in found[0]['message'] and not re.search(r'link\.', found[0]['message'])


def test_후보로_낼_규칙이_없는_절차는_조치_후보_규칙을_더하라고_화면_말로_알린다(catalog):
    p = proposal('HM-8')
    p['knowledge']['rules'] = [r for r in p['knowledge']['rules'] if r.get('table') != 'dt:action-candidates']
    found = [i for i in manual_preflight.validate(p, catalog)['issues'] if i['code'] == 'CANDIDATE_RULE_MISSING']
    assert found and all('조치 후보 규칙' in i['message'] and 'dt:' not in i['message'] for i in found)


def test_고장_유형을_고르지_않은_고장_조치는_고르라고_알린다(catalog):
    p = proposal('HM-8')
    sop = p['procedures'][0]
    sop['link'] = {k: v for k, v in sop['link'].items() if k not in ('failureMode', 'relation', 'addresses')}
    found = [i for i in manual_preflight.validate(p, catalog)['issues'] if i['sop'] == sop['id'] and i['code'] == 'FAILURE_MODE_REQUIRED']
    assert found and '고장 유형' in found[0]['message'] and 'failureMode' not in found[0]['message']


def test_검토_화면의_빈_연결로_제안_연결을_지울_수_있다(catalog):
    p = proposal('HM-8')
    sop = p['procedures'][0]['id']
    p['links'] = {sop: {}}
    assert 'FAILURE_MODE_REQUIRED' in codes(manual_preflight.validate(p, catalog))


def test_정비_시행_절차는_구조_검사만_했다고_실행_때_다시_확인한다고_알린다(seeded_graph, catalog):
    """PM-02 는 냉각 문서의 고장 유형 · 부품을 쓴다 — 시작과 같은 순서로 HM-8 지식이 있는 그래프가 아니면 참조가 비므로 그 사실만 본다."""
    result = manual_preflight.validate(proposal('PM-02'), catalog)
    pm = [e for e in result.get('execution') or [] if any(i['code'] == 'PM_ACTUAL_CONTEXT_REQUIRED' for i in e['issues'])]
    assert pm and all(e['ready'] is False and e['evaluation_mode'] == 'structural' for e in pm)
    assert all('정기 정비' in i['message'] or '실제 운전 시간' in i['message'] for e in pm for i in e['issues'] if i['code'].startswith('PM_'))


def test_실행_구매_절차에_총비용_정책이_없으면_구매_판단_준비가_안_됐다고_알린다(catalog):
    p = proposal('PR-07')
    for x in p['procedures']:
        (x.get('link') or {}).pop('purchase_comparison_policy', None)
    result = manual_preflight.validate(p, catalog)
    buying = [e for e in result.get('execution') or [] if e['executable'] is True]
    assert buying and all(any(i['code'] == 'PURCHASE_COMPARISON_POLICY_REQUIRED' for i in e['issues']) for e in buying)
    assert result['executable_ready'] is False


def test_적재할_절차가_없으면_그렇게_말한다(catalog):
    result = manual_preflight.validate({'sections': [], 'procedures': []}, catalog)
    assert codes(result) == {'NO_PROCEDURES'}


def test_이미_지식에_있는_항목을_다시_정의한_제안은_누가_가졌는지와_할_일을_말하고_그_정의를_빼면_풀린다(catalog):
    """전에는 「cause:…: 기존 지식의 소유권 충돌입니다. 원문과 기존 지식을 대조하세요」 — 무엇이 누구 것과 겹치는지도, 검토 화면에서 무엇을 하면 되는지도
    없었다(2026-11-23). 가진 문서는 서버가 준 파일 이름으로 부르고(manual_knowledge.conflicts), 할 일(적재에서 제외)을 말한다. 그 정의를 뺀 검토본에는 남지 않는다."""
    p = proposal('PM-02')
    cause = p['knowledge']['causes'][0]['id']
    p['knowledge_conflicts'] = [dict(id=cause, label='Cause', owner='tenant:doc', kind='other_document', owner_name='다른 펌프 매뉴얼.md'),
                                dict(id=p['knowledge']['failure_modes'][0]['id'], label='FailureMode', owner='seed', kind='seed_or_admin')]
    said = {i['sop']: i['message'] for i in manual_preflight.validate(p, catalog)['issues'] if i['code'] == 'KNOWLEDGE_OWNERSHIP_CONFLICT'}
    assert said[cause] == (f"{cause}: 같은 원인이 이미 지식에 있습니다(다른 문서 「다른 펌프 매뉴얼.md」가 넣은 것) — 이 문서로 덮어쓰지 않으니 이 항목을 "
                           "적재에서 제외하세요. 이 문서의 다른 항목은 이미 있는 그 항목을 가리킵니다")
    assert '같은 고장 유형이 이미 지식에 있습니다(기본 제공 지식이나 「지식 › 조치 방법」 화면에서 만든 것)' in said[p['knowledge']['failure_modes'][0]['id']]
    p['knowledge']['causes'] = [c for c in p['knowledge']['causes'] if c['id'] != cause]
    left = {i['sop'] for i in manual_preflight.validate(p, catalog)['issues'] if i['code'] == 'KNOWLEDGE_OWNERSHIP_CONFLICT'}
    assert left == {p['knowledge']['failure_modes'][0]['id']}


def test_검사는_제안을_고치지_않는다(catalog):
    p = proposal('HM-8')
    before = deepcopy(p)
    manual_preflight.validate(p, catalog)
    assert p == before


def test_다른_분야_문서가_새_항목으로_제안하지_않은_구성_요소와_증상을_가리키면_그_사실과_할_일을_말한다(catalog):
    """전수검사 10-G7: 유압 밸브 블록 매뉴얼처럼 지금 지식에 없는 구성 요소 · 증상을 쓰는 문서는 「지금 지식에 없습니다」만으로는 문서를 고칠지 지식에
    먼저 넣을지 알 수 없었다. 2026-11-22: 문서는 그 설비의 구성 요소 · 증상 · 센서를 원문 인용과 함께 새 항목으로 제안할 수 있다(사람이 넣기를 고른다) —
    전에 이 시험은 「문서 적재는 구성 요소를 새로 만들지 않아」를 정답으로 지켰다. 새 항목 제안에도 없는 것을 가리키면 그 사실을 말하고, 검토 화면에는
    새 항목을 만드는 칸이 없으므로(C13 — 고를 칸이 없는 학생에게 「고르세요」라고 하지 않는다) 그 항목을 적재에서 제외하라고 한다."""
    p = proposal('HM-8')
    mode = p['knowledge']['failure_modes'][0]
    mode['component'], mode['symptoms'] = 'comp:valve-block', ['sym:valve-response-lag']
    p['procedures'][0]['link']['failureMode'] = 'fm:no-such-mode'
    said = {i['field']: i['message'] for i in manual_preflight.validate(p, catalog)['issues'] if i['code'] == 'REFERENCE_NOT_FOUND'}
    assert '구성 요소 칸에 적은 comp:valve-block가 지금 지식에 없습니다 — 이 문서의 새 항목 제안에도 없습니다' in said['component']
    assert 'AI 추출이 원문 인용과 함께 제안한 것만 넣을 수 있으니, 이 항목을 적재에서 제외하세요' in said['component'] and '고르세요' not in said['component']
    assert '증상 칸에 적은 sym:valve-response-lag가 지금 지식에 없습니다 — 이 문서의 새 항목 제안에도 없습니다' in said['symptoms']
    assert '이 문서의 고장 유형 목록에 넣거나' in said['link.failureMode'] and '새로 만들지 않습니다' not in said['link.failureMode']


def _apu():
    import apu_document as apu
    return apu.proposal('manual:apu')


def _plant_symptom(p):
    p['knowledge']['failure_modes'][0]['symptoms'].append('sym:ps1-drop')


def _plant_tag(p):
    p['knowledge']['evidence'][0]['tag'] = 'PS1'


def _sensor_on_plant(p):
    p['knowledge']['sensors'][0]['component'] = 'comp:cooler'


def _unknown_tag(p):
    p['knowledge']['evidence'][0]['tag'] = 'No_such_signal'


def _fm_on_plant(p):
    p['knowledge']['failure_modes'][0]['component'] = 'comp:tank'


def _apu_cause(p, cid):
    return next(c for c in p['knowledge']['causes'] if c['id'] == cid)


def _apu_sop(p, sop):
    return next(x for x in p['procedures'] if x['id'] == sop)['link']


def _plant_part(p):
    _apu_cause(p, 'cause:apu-oil-seal-wear')['parts'] = ['part:pump-seal']        # 오일 실 마모 ↔ 유압 펌프의 축 씰 키트 — 이름이 닮아 AI가 고를 수 있는 꼴


def _plant_variable(p):
    _apu_cause(p, 'cause:apu-joint-leak')['disturbs'] = [{'target': 'sv:ts1', 'sign': 1}]


def _plant_action(p):
    link = _apu_sop(p, 'SOP-APU-12')
    link['actions'] = [{'action': 'action:work-order', 'value': 'SOP-APU-12'}]
    link['affects'] = [{'target': 'sv:ts1', 'sign': '-'}, {'target': 'msr:maint-cost', 'sign': '+'}]      # 성과 지표는 회사의 지표라 가리킬 수 있다


@pytest.mark.parametrize('change, found', [
    (_plant_symptom, {('PLANT_SYMPTOM_ON_OTHER', 'fm:apu-air-leak', 'symptoms')}),
    (_plant_tag, {('PLANT_TAG_ON_OTHER', 'evd:apu-load-ratio-high', 'tag')}),
    (_sensor_on_plant, {('NEW_ITEM_ON_PLANT', 'sen:apu-tp2', 'component')}),
    (_unknown_tag, {('REFERENCE_NOT_FOUND', 'evd:apu-load-ratio-high', 'tag')}),
    (_fm_on_plant, {('NEW_ITEM_ON_PLANT', 'fm:apu-air-leak', 'symptoms'), ('NEW_ITEM_ON_PLANT', 'evd:apu-load-ratio-high', 'tag'),
                    ('NEW_ITEM_ON_PLANT', 'evd:apu-leak-test-drop', 'tag'),
                    # 설비의 고장 유형이 되면 판단 엔진이 닿는다 — 그 절차들은 다시 조치 후보 규칙이 필요하다(설비 밖이라는 참고가 아니라 검토 필요)
                    *{('CANDIDATE_RULE_MISSING', sop, 'knowledge.rules') for sop in ('SOP-APU-05', 'SOP-APU-11', 'SOP-APU-12', 'SOP-APU-13')}}),
    (_plant_part, {('PLANT_LINK_ON_OTHER', 'cause:apu-oil-seal-wear', 'parts')}),
    (_plant_variable, {('PLANT_LINK_ON_OTHER', 'cause:apu-joint-leak', 'disturbs')}),
    (_plant_action, {('PLANT_LINK_ON_OTHER', 'SOP-APU-12', 'link.actions'), ('PLANT_LINK_ON_OTHER', 'SOP-APU-12', 'link.affects')}),
], ids=['다른 설비 고장에 설비 증상', '다른 설비 증거에 유압 수집 값', '새 센서를 설비 구성 요소에', '아무 센서도 아닌 태그', '새 증상 · 센서 증거를 설비 고장에',
        '다른 설비 원인에 설비 부품', '다른 설비 원인이 설비 상태 변수를 흔듦', '다른 설비 절차에 이 시스템의 원자 조치 · 설비 상태 변수 영향'])
def test_새_항목과_다른_설비의_증거는_가상_설비의_구조를_넓히지_않고_그_까닭을_말한다(catalog, change, found):
    """가상 설비(HYD-01~03)의 구조(설비에 딸린 구성 요소 · 경보가 감지하는 증상 · 수집 태그)는 넓히지 않는다 — 다른 설비의 지식이 그 설비의 경보 · 판단에
    닿지 않게, 그리고 다른 설비의 증거가 이 시스템의 수집 값을 읽지 않게. 다른 설비 문서(apu_document)의 한 곳을 바꾸면 그곳만 짚는다(나머지는 그대로 지난다)."""
    p = _apu()
    assert [i for i in manual_preflight.validate(deepcopy(p), catalog)['issues']] == []
    change(p)
    issues = manual_preflight.validate(p, catalog)['issues']
    assert {(i['code'], i['sop'], i['field']) for i in issues} == found, issues
    assert all('설비 HYD-01 · HYD-02 · HYD-03의 구성 요소' in i['message'] for i in issues if i['code'] == 'NEW_ITEM_ON_PLANT')
    # 다른 설비의 지식이 이 시스템 설비의 무엇을 가리켰는지를 이름으로, 그 고장이 어디서 생기는지와 함께 말한다(학생 화면 말 — 내부 id 를 늘어놓지 않는다)
    named = {'parts': '부품 「펌프 축 씰 키트」', 'disturbs': '상태 변수 「유온」', 'link.affects': '상태 변수 「유온」', 'link.actions': '원자 조치 「정비 작업지시 발행」'}
    for i in issues:
        if i['code'] == 'PLANT_LINK_ON_OTHER':
            assert named[i['field']] in i['message'] and '설비에 딸리지 않은 구성 요소 「' in i['message'] and '도구 서버' in i['message'], i['message']


def test_다른_설비_절차에_이_시스템의_원자_조치를_이은_추출은_AI에게_교정_사유로_돌려보낸다(catalog, tmp_path):
    """검토 화면에는 원자 조치를 고칠 칸이 없다(검토 화면의 절차 판) — 다른 설비의 절차에 이 시스템의 원자 조치를 이은 제안은 추출이 제출할 때 교정 사유로
    돌려보내 AI가 고친다(manual_extraction.AGENT_FIXABLE_ISSUES 의 PLANT_LINK_ON_OTHER). 실제 보관소에 올린 다른 설비 문서와 실제 그래프의 카탈로그로 판정한다."""
    import apu_document as apu
    from procsvc import manual_extraction
    from procsvc.manual_sources import ManualSources
    source = ManualSources(tmp_path / 'm.sqlite3').save('hyd', apu.FILENAME, apu.RAW)
    p = apu.proposal(source['source_id'])
    assert manual_extraction.content_issues(manual_extraction.validate_proposal(source, deepcopy(p)), source, catalog) == []
    _plant_action(p)
    [issue] = manual_extraction.content_issues(manual_extraction.validate_proposal(source, p), source, catalog)
    assert '원자 조치 「정비 작업지시 발행」' in issue and '상태 변수 「유온」' in issue and 'assets 가 없는 구성 요소의 고장에는' in issue, issue


def test_고장_유형을_하나도_내지_않아_실행_절차가_모두_막힌_추출만_AI에게_교정_사유로_돌려보낸다(catalog, tmp_path):
    """2026-11-23 학생 대역 실측: 다른 설비(APU) 매뉴얼을 실제 AI로 추출하니 「기존 목록과 일치하는 항목이 없어 제안하지 않았다」며 knowledge 를 통째로
    비웠고, 실행 절차 11개가 모두 고장 유형 없음으로 막힌 채 사람 검토로 넘어갔다 — 학생이 고를 고장 유형이 하나도 없었다. 그 꼴은 추출이 제출할 때
    교정 사유로 돌려보낸다(원문의 고장을 만들거나 · 있는 고장 유형을 가리키거나 · 고장을 말하지 않는 절차면 참고 절차로). 고장 유형을 낸 제안에서 한
    절차의 칸만 빈 것은 사람이 검토 화면에서 고른다(교정 사유 아님). 서명 묶음의 수업 문서 넷은 걸리지 않는다."""
    import apu_document as apu
    from procsvc import manual_extraction
    from procsvc.manual_sources import ManualSources
    source = ManualSources(tmp_path / 'm.sqlite3').save('hyd', apu.FILENAME, apu.RAW)
    p = apu.proposal(source['source_id'])
    emptied = deepcopy(p)
    emptied.pop('knowledge', None)                     # 실측 꼴: knowledge 칸 없음, 실행 절차의 link 없음, 참고 절차만 link
    for proc in emptied['procedures']:
        if (proc.get('link') or {}).get('kind') != 'reference':
            proc['link'] = None
    [issue] = manual_extraction.content_issues(manual_extraction.validate_proposal(source, emptied), source, catalog)
    assert 'knowledge.failure_modes 가 비었습니다' in issue and 'knowledge.components' in issue and '"kind":"reference"' in issue, issue
    one = deepcopy(p)                                  # 고장 유형을 낸 제안에서 한 절차만 고장 유형을 모름 — 사람이 고른다
    next(x for x in one['procedures'] if (x.get('link') or {}).get('failureMode'))['link'] = None
    assert manual_extraction.content_issues(manual_extraction.validate_proposal(source, one), source, catalog) == []
    for doc in sorted(DOCS):
        try:
            manual_extraction.check_action_values(proposal(doc), catalog)
        except ValueError as exc:
            assert 'knowledge.failure_modes 가 비었습니다' not in str(exc), (doc, str(exc))


def test_새_센서의_태그를_지금_지식의_다른_센서가_쓰면_그_센서를_말한다(catalog):
    taken = deepcopy(catalog)
    taken['sensors'].append({'id': 'sen:other-doc', 'name': '다른 문서의 압력 센서', 'tag': 'TP2', 'unit': 'bar', 'components': []})
    [issue] = [i for i in manual_preflight.validate(_apu(), taken)['issues']]
    assert (issue['code'], issue['sop']) == ('SENSOR_TAG_TAKEN', 'sen:apu-tp2') and '「다른 문서의 압력 센서」' in issue['message'], issue


def test_설비_목록이_없는_옛_카탈로그로는_설비_구조를_판정하지_않았다고_말한다(catalog):
    """그 칸이 생기기 전에 추출 작업에 고정한 카탈로그(센서 목록 · 구성 요소의 설비가 없다)로 검사하면, 조용히 지나지 않고 판정하지 않았다고 한 건으로 말한다."""
    old = {k: v for k, v in deepcopy(catalog).items() if k != 'sensors'}
    issues = manual_preflight.validate(proposal('HM-8'), old)['issues']
    assert [i['code'] for i in issues if i['code'] == 'CATALOG_OUTDATED'] == ['CATALOG_OUTDATED']
