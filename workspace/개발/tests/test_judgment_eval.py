"""AI 판단 채점(procsvc/judgment_eval.py) — 정답표 모양 검사 · 채점 · 반복 집계 · 지식 차이 · 저장소(실제 DB)."""
import pytest

from procsvc import judgment_eval as je

ITEM = {'id': 'cooler-auto', 'title': '쿨러 성능 저하 · 원격 자동', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION',
        'facts': {'plc_mode': 'REMOTE_AUTO'}, 'expected': {'cause': 'cause:fouling', 'failure_mode': 'fm:cooler-cooling-loss'},
        'allowed_top': ['skill:sop-cool-11'], 'forbidden': [{'skill': 'skill:stop', 'expect': 'excluded'}],
        'required_evidence': ['evd:ts1', 'rule:r1']}
NO_FORBIDDEN = dict(ITEM, forbidden=[])


def judged(cause='cause:fouling', fm='fm:cooler-cooling-loss', rec='skill:sop-cool-11', options=None, cited=('evd:ts1', 'rule:r1'), status='EVALUATED'):
    options = options if options is not None else [{'id': 'skill:sop-cool-11', 'rank': 1, 'feasible': True, 'score': 1, 'violations': []},
                                                   {'id': 'skill:stop', 'rank': None, 'feasible': False, 'score': 0, 'violations': ['rule:x']}]
    return {'status': status, 'cause': cause, 'failure_mode': fm, 'recommended': rec, 'options': options, 'cited': list(cited), 'facts_used': {}}


# ---------------------------------------------------------------- 정답표 모양 (학생 말로 거절)
@pytest.mark.parametrize('change, says', [
    ({'id': 'X'}, '항목 이름은 영문 소문자'),
    ({'title': ''}, '제목 칸이 비어 있습니다'),
    ({'asset': ' '}, '설비 칸이 비어 있습니다'),
    ({'pattern': None}, '이상 패턴 칸이 비어 있습니다'),
    ({'facts': []}, '가정 사실은 이름 → 값 묶음'),
    ({'expected': {'cause': 'fouling', 'failure_mode': 'fm:x'}}, '기대 원인(cause:…)과 고장 유형(fm:…)'),
    ({'allowed_top': []}, '1위로 허용되는 조치(skill:…)를 하나 이상'),
    ({'forbidden': [{'skill': 'skill:a', 'expect': 'maybe'}]}, '빠져야 할 조치 1번째 줄은'),
    ({'forbidden': [{'skill': 'skill:sop-cool-11', 'expect': 'excluded'}]}, '1위로 허용되는 조치에도 있습니다'),
    ({'required_evidence': []}, '근거에 있어야 할 지식 id 를 하나 이상'),
], ids=['항목 이름', '제목', '설비', '패턴', '가정 사실', '기대 원인', '허용 1위', '빠질 조치 기대', '허용과 겹침', '근거'])
def test_정답표_항목의_틀린_칸은_화면_이름으로_까닭을_말한다(change, says):
    with pytest.raises(ValueError) as refused:
        je.validate_item(dict(ITEM, **change))
    assert says in str(refused.value)
    assert not any(word in str(refused.value) for word in ('allowed_top', 'required_evidence', 'forbidden[', 'expected 에'))


# ---------------------------------------------------------------- 채점
@pytest.mark.parametrize('item, j, score', [
    (ITEM, judged(), 100.0),
    (ITEM, judged(cause='cause:other', rec='skill:other', cited=()), 20.0),          # 빠질 조치만 맞음(0.2)
    (NO_FORBIDDEN, judged(cause='cause:other', rec='skill:other', cited=()), 0.0),   # 검사할 것이 없는 칸은 점수에 넣지 않는다
    (NO_FORBIDDEN, judged(rec='skill:other', cited=()), 37.5),                       # 원인 0.3 / (0.3+0.3+0.2)
    (NO_FORBIDDEN, judged(), 100.0),
    (ITEM, judged(status='WITHHELD'), 0.0),
    (NO_FORBIDDEN, judged(status='WITHHELD'), 0.0),                                  # 보류여도 적지 않은 검사는 점수 밖(P3-11)
], ids=['모두 맞음', '빠질 조치만 맞음', '빠질 조치 없는 항목 모두 틀림', '빠질 조치 없는 항목 원인만', '빠질 조치 없는 항목 모두 맞음', '보류',
        '빠질 조치 없는 항목 보류'])
def test_채점은_정답표가_적은_검사만_가중치로_나눠_100점_만점으로_센다(item, j, score):
    out = je.score_judgement(item, j)
    assert out['score'] == score
    assert out['checks']['forbidden']['scored'] is bool(item['forbidden'])


def test_반복_집계는_평균과_검사마다_맞은_횟수를_함께_준다():
    runs = [judged(), judged(rec='skill:other'), judged()]
    out = je.aggregate(ITEM, runs)
    assert (out['repeats'], out['score'], out['min'], out['max']) == (3, 90.0, 70.0, 100.0)
    assert out['check_hits'] == {'cause': 3, 'top': 2, 'forbidden': 3, 'evidence': 3}
    assert out['checks']['top']['ok'] is True and out['identical'] is False         # checks 는 마지막 회차


def test_판단_결과가_없으면_집계하지_않는다():
    with pytest.raises(ValueError):
        je.aggregate(ITEM, [])


def test_두_실행의_지식_차이는_끊긴_관계와_바뀐_항목을_보인다():
    a = je.knowledge_state([{'nodes': 2, 'rels': 1}], [{'a': 'x', 't': 'R', 'b': 'y'}], [{'id': 'x', 'labels': ['A'], 'props': {'v': 1}}])
    b = je.knowledge_state([{'nodes': 2, 'rels': 0}], [], [{'id': 'x', 'labels': ['A'], 'props': {'v': 2}}])
    d = je.knowledge_diff(a, b)
    assert d['changed'] and d['removed_rels'] == [{'from': 'x', 'type': 'R', 'to': 'y'}] and d['changed_nodes'] == ['x']


@pytest.mark.parametrize('path, by, says', [('other', '강사', 'path'), ('decide', ' ', '누가 실행했는지')], ids=['없는 경로', '실행자 없음'])
def test_실행_기록은_경로와_실행자가_있어야_만든다(path, by, says):
    result = je.aggregate(ITEM, [judged()])
    with pytest.raises(ValueError) as refused:
        je.new_run(path=path, by=by, repeats=1, knowledge={}, results=[result])
    assert says in str(refused.value)


def test_경로_안내는_학생_말이다():
    for note in je.PATH_NOTES.values():
        assert not any(word in note for word in ('/api/', 'LLM', '결정론', '파이프라인', '가드레일', '워커', 'N>1'))


# ---------------------------------------------------------------- 저장소
def test_되돌리기는_이_테넌트의_정답표와_채점_실행을_지운다(pg_dsn):
    store, other = je.PgEvalStore(pg_dsn, 'hyd'), je.PgEvalStore(pg_dsn, 'other-tenant')
    item = je.validate_item(ITEM)
    for s in (store, other):
        s.reset()
        s.golden_put(item, '강사', create=True)
        s.put(je.new_run(path='decide', by='강사', repeats=1, knowledge={'fingerprint': None}, results=[je.aggregate(item, [judged()])]))
    assert store.reset() == {'golden_items': 1, 'runs': 1}
    assert (store.golden_list(), store.list(10)) == ([], [])
    assert len(other.golden_list()) == 1 and len(other.list(10)) == 1                 # 다른 테넌트는 그대로
    other.reset()


def test_지식_차이와_한쪽에만_있는_정답표_항목은_id_와_함께_이름을_싣는다():
    """전 · 후 비교가 「한쪽 실행에만 있는 항목: trial-cooler, review5-cooler」 · 바뀐 지식을 id 로만 보였다 — 화면이 이름으로 말할 재료가 없었다."""
    a = je.knowledge_state([{'nodes': 2, 'rels': 1}], [{'a': 'cause:x', 't': 'CAUSES', 'b': 'fm:y'}],
                           [{'id': 'cause:x', 'labels': ['Cause'], 'props': {'name': '쿨러 핀 오염'}}, {'id': 'fm:y', 'labels': ['FailureMode'], 'props': {'name': '냉각 성능 상실'}}])
    b = je.knowledge_state([{'nodes': 2, 'rels': 0}], [],
                           [{'id': 'cause:x', 'labels': ['Cause'], 'props': {'name': '쿨러 핀 오염', 'prior': 0.2}}, {'id': 'rule:z', 'labels': ['Rule'], 'props': {}}])
    d = je.knowledge_diff(a, b)
    assert d['removed_rels'] == [{'from': 'cause:x', 'type': 'CAUSES', 'to': 'fm:y'}] and d['added_nodes'] == ['rule:z']
    assert d['names'] == {'cause:x': '쿨러 핀 오염', 'fm:y': '냉각 성능 상실'}          # 이름이 없는 항목(rule:z)은 지어내지 않는다
    before = je.new_run(path='decide', by='담당자', repeats=1, knowledge=a, results=[je.aggregate(ITEM, [judged()])])
    other = dict(ITEM, id='pump-leak', title='펌프 내부 누설')
    after = je.new_run(path='decide', by='담당자', repeats=1, knowledge=b, results=[je.aggregate(other, [judged()])])
    out = je.compare(before, after)
    assert (out['only_before'], out['only_after']) == (['cooler-auto'], ['pump-leak'])
    assert out['item_titles'] == {'cooler-auto': ITEM['title'], 'pump-leak': '펌프 내부 누설'}


def test_지난_처리_건에_맞는_정답표_항목이_없거나_여럿이면_처리_건_안쪽_번호와_경보_코드_없이_까닭을_말한다():
    candidate = {'instance': 'c3_cooling.a5727cb6-0000-4000-8000-000000000000', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': {}}
    with pytest.raises(ValueError) as none:
        je.match_item([], candidate)
    with pytest.raises(ValueError) as many:
        je.match_item([ITEM, dict(ITEM, id='cooler-auto-2', title='쿨러 성능 저하 · 둘째')], candidate)
    for said in (str(none.value), str(many.value)):
        assert 'c3_cooling' not in said and 'COOLER_DEGRADATION' not in said and 'cooler-auto' not in said, said
    assert '「쿨러 성능 저하 · 둘째」' in str(many.value)
