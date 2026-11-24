"""문서 추출 제안 계약(procsvc/manual_extraction.py) — AI(또는 강사 서명 묶음)의 제안을 원문 인용 · 절 · 단계 · 지식으로 검사하고, 고칠 수 있는
결함(인용 · 절 제목 · 판정 기준 절의 절차 · 원자 조치 값)을 교정 사유로 돌려보낸다. 원문의 특정 문장 모양으로 그 문서의 규칙을 강제하지는 않는다(2026-11-22).
제안 표본은 강사 서명 묶음의 검토본이고 원문은 실제 보관소에 올린 제공 문서다. 처리 건 쪽(시작 · 결과 · 검토 · 적재)은 test_class_knowledge 의 포털 길(portal_commit)과 test_manual_approved_cache 가 본다."""
from copy import deepcopy

import pytest

import class_knowledge
from conftest import WWW
from procsvc import manual_extraction as mx, manual_segments
from procsvc.manual_sources import ManualSources

#: 강사 서명 묶음의 문서 넷 — 시작이 넣는 셋과, 학생이 실습에서 넣는 교대 인계 문서(HI-01, 실행 후보가 아닌 참고 절차). HI-01 을 빼고 돌면 참고
#: 절차 갈래의 인용 계약 · 내용 검사가 깨져도 초록이다(전수검사 13B-1).
DOCS = {item['doc']: item for item in class_knowledge.reviewed(order=class_knowledge.ORDER + ('HI-01',))}


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
    assert mx.content_issues(checked, source, None, criteria_scope=True, package_scope=True) == []


@pytest.mark.parametrize('doc, drop', [
    ('HM-8', lambda p: p['knowledge'].update(rules=[r for r in p['knowledge']['rules'] if r['id'] != 'rule:cooler-forecast-temperature-warning'])),
    ('HM-8', lambda p: p['knowledge'].update(rules=[r for r in p['knowledge']['rules'] if r.get('effect') != 'PENALTY'])),
    ('PR-07', lambda p: [(q.get('link') or {}).pop('purchase_comparison_policy', None) for q in p['procedures']]),
], ids=['예측 유온 경고 규칙 없음', '감점 규칙 없음', '구매 총비용 정책 없음'])
def test_원문의_문장_모양으로_그_문서의_규칙을_교정_사유로_강제하지_않는다(archive, doc, drop):
    """전수 대조 03-2~4 · 가짜 11(2026-11-22 지움): 추출 검사가 수업 문서 한 편의 문장(「예측 유온이 55 ℃ 이상이면 … 실패 … 비교」 · 「N만 원을 감점」 ·
    「불량 1건 손실 … 만 원」)을 찾아 그 규칙 · 정책을 교정 사유로 강제했다. 같은 꼴을 쓴 학생 문서에는 유압 실습장의 입력(in:forecast-ts1 · ℃)을 강제했고,
    금액만 맞으면 대상이 틀린 규칙도 통과시켰다. 이제 그 규칙 · 정책이 빠진 제안도 추출 계약은 지나고, 빠진 것은 사람 검토가 원문과 견주어 본다
    (실행 구매 절차의 정책 누락은 적재 전 검사가 일반 규칙으로 알린다 — test_manual_preflight)."""
    source, proposal = proposal_of(archive, doc)
    drop(proposal)
    assert mx.content_issues(mx.validate_proposal(source, proposal), source, None) == []


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


def test_구간_작업은_담당_구간의_원문만_본다(archive):
    big = ('# 1장\n' + '가' * 3000 + '\n# 2장\n' + '나' * 3000).encode()
    source = archive.save('hyd', 'big.md', big)
    seg = manual_segments.segments(source, 4000)[1]
    view = mx.segment_view(source, seg)
    assert view['source_id'] == source['source_id'] and view['pages'][0]['text'].startswith('# 2장')


@pytest.mark.parametrize('filename, raw, name', [('a.md', b'# HM-8 \xec\xbf\xa8\xeb\x9f\xac\n', 'HM-8 쿨러'), ('a.txt', b'plain\n', 'a.txt'),
                                                 # 학생 문서 제목의 괄호는 그대로 — 문서 번호가 있어도 「교육용 예시」 꼴이 아니면 떼지 않는다
                                                 ('b.md', '# 펌프 점검표 (2024년판)\n'.encode(), '펌프 점검표 (2024년판)'),
                                                 ('c.md', '# 펌프 점검표 (PM-02, 사내 기준)\n'.encode(), '펌프 점검표 (PM-02, 사내 기준)')])
def test_처리_건_이름은_마크다운이면_첫_제목_아니면_파일_이름이다(archive, filename, raw, name):
    assert mx.display_name(archive.save('hyd', filename, raw)) == name


def test_제공_문서의_처리_건_이름은_원문_첫_제목에서_끝의_출처_괄호만_뗀_것이다(archive):
    """제공 문서 원문의 첫 제목 끝 「(HM-8, 교육용 예시)」 꼴은 제작 흔적이라 처리 건 목록(「… 추출 제안」)에 보이지 않는다. 원문 바이트는 서명
    묶음이 걸려 그대로 둔다 — 실제 제공 문서 파일로 이름을 짓는다."""
    names = {}
    for f in sorted((WWW / 'samples').glob('*.md')):
        head = f.read_text(encoding='utf-8').splitlines()[0][2:]
        names[f.name] = (head, mx.display_name(archive.save('hyd', f.name, f.read_bytes())))
    assert sum('교육용 예시' in head for head, _ in names.values()) == 3          # 괄호가 붙은 제공 문서 셋(HM-8 · PM-02 · PR-07)
    for f, (head, name) in names.items():      # 뗀 것은 제목 끝의 「(문서 번호, 교육용 예시)」 하나뿐이다
        code = f.split('_')[0]
        assert head in (name, f'{name} ({code}, 교육용 예시)'), (head, name)
    assert names['HM-8_cooler-fan-manual.md'][1] == '유압 파워유닛 쿨러 팬 정비 매뉴얼'
    assert names['HI-01_shift-inspection-supplement.md'][1] == names['HI-01_shift-inspection-supplement.md'][0]   # 괄호 없는 제목은 그대로


def test_추출_정의는_판본과_계약을_싣는다():
    d = mx.definition()
    assert (d['processDefinitionId'], d['version'], d['forms']['manual_proposal']['contract']) == (mx.DEFINITION_ID, mx.VERSION, mx.CONTRACT)


def test_추출_지시문의_예시는_제공_문서의_글이나_번호가_아니다():
    """전수 대조 03-6(2.20에 고침): 지시문은 수업 문서가 틀릴 때마다 그 문서의 글(「### SOP-COOL-11 팬 최대 운전」 · 「## PR-7.6 발주 절차」 · 「원인은 아래 세 가지」 ·
    「출고를 예약한다」)과 설비 코드(1~3호기 → HYD-01 …)를 예시로 더해 왔다. 제공 문서는 서명 묶음에서 나오므로 그 예시가 쓰이는 곳은 학생이 올린 다른 문서의
    추출뿐이고, 거기서는 수업 문서의 글이 정답 꼴로 읽힌다. 지시문의 따옴표 예시(한글이 든 것)가 제공 문서 넷의 본문에 없고, 제공 문서의 절 번호 · 절차 번호와
    이 시스템의 설비 코드를 지시문이 부르지 않는다."""
    import re
    texts = {name: re.sub(r'\s+', '', item['raw'].decode('utf-8')) for name, item in DOCS.items()}
    quoted = [a or b for a, b in re.findall(r"'([^'\n]+)'|\"([^\"\n]+)\"", mx.INSTRUCTION)]
    found = sorted({(piece, name) for q in quoted for piece in q.split('…') if len(re.findall(r'[가-힣]', piece)) >= 3
                    for name, text in texts.items() if re.sub(r'\s+', '', piece) in text})
    assert found == [], found
    seed = (WWW.parents[2] / 'it' / 'neo4j' / 'v2' / 'instances.cypher').read_text(encoding='utf-8')
    codes = set(re.findall(r"\['asset:[a-z0-9-]+','([A-Z0-9-]+)'\]", seed))
    assert codes, '시드에서 설비 코드를 읽지 못했다'
    names = codes | {s['ref'] for i in DOCS.values() for s in i['proposal']['sections']} | {p['id'] for i in DOCS.values() for p in i['proposal']['procedures']}
    assert sorted(n for n in names if re.search(r'(?<![\w.-])' + re.escape(n) + r'(?![\w-]|\.\d)', mx.INSTRUCTION)) == []


@pytest.mark.parametrize('version, at_least', [('2.18', True), ('2.13', True), ('2.12', False), ('10.0', True), ('2.x', False), (None, False)])
def test_판본_문턱은_그_판_이후_실행에만_내용_검사를_건다(version, at_least):
    assert mx.contract_at_least({'proc_def_version': version}, mx.CRITERIA_FROM) is at_least


def test_판본마다_받는_내용_검사가_정해진다():
    assert mx.scopes({'proc_def_version': '2.16'}) == dict(criteria_scope=True, package_scope=True)


def test_지식_항목의_인용이_원문_두_곳에_있으면_그_항목이_적은_절_안의_것으로_정하고_절_밖에만_있으면_앞_글과_함께_되묻는다(tmp_path):
    """2026-11-23 실측: 다른 설비 매뉴얼의 두 고장 절(APU-6.3 오일 누설 · APU-6.4 건조 타워 전환 불량)이 원인 줄을 같은 꼬리 문장으로 맺어, 원인 인용이
    교정 세 차례 모두 「2곳에 있어」로 거부됐다(자리 좌표만 받은 AI가 같은 인용을 냈다). 항목은 자기 절을 적는다 — 그 절 안에 한 곳이면 그곳이다
    (절차 단계와 같은 규칙). 그 절 밖에만 있으면 정하지 않고, 자리마다 앞 글을 보여 어디로 늘릴지 알린다."""
    import apu_document as apu
    source = ManualSources(tmp_path / 'm.sqlite3').save('hyd', apu.FILENAME, apu.RAW)
    text = {p['page']: p['text'] for p in source['pages']}
    [page] = text
    tail = '보전 기록에서 60 %를 차지한다.'
    assert text[page].count(tail) == 2
    p = apu.proposal(source['source_id'])
    causes = {c['id']: c for c in p['knowledge']['causes']}
    for cid in ('cause:apu-oil-seal-wear', 'cause:apu-tower-valve-stuck'):                 # APU-6.3 · APU-6.4 의 원인
        causes[cid]['anchor'] = {'source_id': source['source_id'], 'page': page, 'quote': tail}
    checked = {c['id']: c['anchor'] for c in mx.validate_proposal(source, p)['knowledge']['causes']}
    assert checked['cause:apu-oil-seal-wear']['start'] == text[page].index(tail)
    assert checked['cause:apu-tower-valve-stuck']['start'] == text[page].rindex(tail)
    wrong = apu.proposal(source['source_id'])
    joint = next(c for c in wrong['knowledge']['causes'] if c['id'] == 'cause:apu-joint-leak')    # APU-6.2 — 그 꼬리 문장이 없는 절
    joint['anchor'] = {'source_id': source['source_id'], 'page': page, 'quote': tail}
    with pytest.raises(ValueError, match='2곳에 있어') as caught:
        mx.validate_proposal(source, wrong)
    assert str(caught.value).count('앞 글 「') == 2 and '오일이 샌다.' in str(caught.value), str(caught.value)



@pytest.mark.parametrize('given, ok', [
    (None, True), ('', True), ('document', True), ('full', True), ('other-document', False), ('manual:', False),
], ids=['비움', '빈 글', '같은 문서 id(판본 sha256 을 자름)', '그대로', '다른 문서', '머리만'])
def test_인용의_원문_판본_id_는_비우거나_같은_문서_id_만_적으면_서버가_채우고_다른_문서면_거절한다(tmp_path, given, ok):
    """2026-11-23 실측: 다른 설비 매뉴얼 추출이 내용은 다 맞춘 셋째 교정에서 인용 몇 곳의 판본 id 끝(sha256)을 잘라 통째로 거부됐다. 인용은 지금 검사하는 이
    원문의 것이고 인용 글이 이 원문에 있는지는 서버가 찾는다(A117) — 판본 id 를 AI가 옮겨 적게 하지 않는다. 다른 문서의 id 는 그대로 거절한다."""
    import apu_document as apu
    archive = ManualSources(tmp_path / 'm.sqlite3')
    source = archive.save('hyd', apu.FILENAME, apu.RAW)
    other = archive.save('hyd', 'other.md', '# 다른 문서\n\n다른 내용이다.\n'.encode('utf-8'))
    value = {'document': source['source_id'].rsplit(':', 1)[0], 'full': source['source_id'],
             'other-document': other['source_id'].rsplit(':', 1)[0]}.get(given, given)
    p = apu.proposal(source['source_id'])
    p['knowledge']['causes'][0]['anchor']['source_id'] = value
    if ok:
        checked = mx.validate_proposal(source, p)
        assert checked['knowledge']['causes'][0]['anchor']['source_id'] == source['source_id']
    else:
        with pytest.raises(ValueError, match='원문 판본의 인용이 필요합니다'):
            mx.validate_proposal(source, p)
