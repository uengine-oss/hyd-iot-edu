"""정의 판본 비교(procsvc/definition_diff.py) — [기준과 비교]가 사람이 읽는 말로, 바뀐 것을 빠짐없이 말한다."""
import json
from copy import deepcopy

import pytest

from procsvc.definition_diff import align_import, compare, compare_import

from conftest import DEFINITIONS

BASE = json.loads((DEFINITIONS / 'anomaly_response_v22.json').read_text(encoding='utf8'))


def _changed(edit):
    after = deepcopy(BASE)
    edit(after)
    after['version'] = '9.9'
    return compare(BASE, after)


def test_같은_원문이면_차이가_없고_판본_번호만_달라도_차이가_없다():
    same = compare(BASE, deepcopy(BASE))
    renumbered = compare(BASE, dict(deepcopy(BASE), version='9.9'))
    assert same['same'] and renumbered['same'] and renumbered['counts'] == {'추가': 0, '삭제': 0, '변경': 0}


@pytest.mark.parametrize('edit, kind, label', [
    (lambda d: d['activities'][0].update(instruction='새 지시'), '단계', '지시문'),
    (lambda d: d['activities'][0].update(duration=5), '단계', '예상 시간'),
    (lambda d: d['activities'][0].update(checkpoints=['확인']), '단계', '확인 항목'),
    (lambda d: d.update(loopPolicy='guarded'), '정의', '반복 허용'),
    (lambda d: d.update(contractProvenance={'source': 'x'}), '정의', '계약 출처'),
    (lambda d: d.update(somethingNew=1), '정의', '기타 설정(somethingNew)'),
])
def test_바뀐_칸은_사람_이름으로_말하고_목록에_없던_최상위_칸도_놓치지_않는다(edit, kind, label):
    """P1-24: 전에는 instruction · duration 같은 칸이 영문 그대로 보였고, loopPolicy · contractProvenance 가 바뀐 판본을 「차이 없음」으로 말했다."""
    diff = _changed(edit)
    assert not diff['same']
    change = next(c for c in diff['changes'] if c['kind'] == kind)
    assert label in change['text'] or label in [f['label'] for f in change['fields']], change


def test_폼_항목은_자료형도_한국어로_말한다():
    def edit(d):
        form = next(iter(d['forms'].values()))
        form['fields_json'].append({'key': 'extra', 'type': 'array', 'text': '추가 목록'})
    change = next(c for c in _changed(edit)['changes'] if c['kind'] == '폼')
    assert '추가 목록(목록)' in change['fields'][0]['after'] and 'array' not in change['fields'][0]['after']


def test_단계를_지우고_더하면_삭제_추가로_세고_흐름선은_양_끝_이름으로_말한다():
    def edit(d):
        d['sequences'][0] = dict(d['sequences'][0], target=d['sequences'][0]['target'])
        d['sequences'].append({'id': 'flow-new', 'source': d['activities'][0]['id'], 'target': d['activities'][1]['id']})
        d['activities'].pop()
    diff = _changed(edit)
    assert diff['counts']['삭제'] >= 1 and diff['counts']['추가'] >= 1
    added = next(c for c in diff['changes'] if c['id'] == 'flow-new')
    assert added['flow']['from'] == BASE['activities'][0]['name'] and '→' in added['text']


def test_그림에서_가져온_흐름은_고른_부품으로_기준_단계와_맞춰_비교한다():
    """bpmn.io 그림 id(Activity_…)는 기준 id 와 달라 id 로만 맞추면 전부 「삭제 + 추가」가 된다 — 고른 부품으로 맞춘다."""
    drawn = deepcopy(BASE)
    first = drawn['activities'][0]
    old_id, new_id = first['id'], 'Activity_0abc12'
    first['id'] = new_id
    for s in drawn['sequences']:
        for end in ('source', 'target'):
            if s[end] == old_id:
                s[end] = new_id
    drawn['bpmnImport'] = {'mapping': {'tasks': {new_id: {'part': old_id}}}}
    assert align_import(BASE, drawn)[new_id] == old_id
    diff = compare_import(BASE, drawn)
    assert not any(c['id'] == old_id and c['change'] == '삭제' for c in diff['changes'])
    assert all('Activity_0abc12' not in c['text'] for c in diff['changes']), '무작위 그림 id 는 글에 보이지 않는다'
