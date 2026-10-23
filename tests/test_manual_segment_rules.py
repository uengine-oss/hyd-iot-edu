"""I3 (2026-10-23 검수): 긴 문서를 구간으로 나눠 추출할 때, 한 구간의 조치 후보 규칙이 다른 구간의 SOP를 가리켜도 거부하지 않는다.
SOP 존재는 합친 전체 문서 기준으로 본다 — 어느 구간에도 없는 SOP는 규칙에서 빠지고 경고로 남는다(합친 결과가 막히지 않는다)."""
import copy
from uuid import uuid4

import pytest

from procsvc import manual_extraction as extraction, manual_segments as ms
from procsvc.manual_sources import ManualSources
from worker.runner import Runner
from test_worker import _settings
from test_instances import rt  # noqa: F401 — fixture
from test_manual_segments import _doc, _source, _proposal_for, _segment_exec


def _rule(src, seg, rid, outputs, effect='SELECT', key='outputs'):
    from test_manual_segments import _anchor
    rule = {'id': rid, 'table': 'dt:action-candidates' if effect == 'SELECT' else 'dt:compliance', 'effect': effect,
            'tests': [{'input': 'in:pattern', 'operator': '==', 'value': 'FILTER_CLOG', 'unit': None}],
            'section': 'HM-1.1', 'anchor': _anchor(src, seg, '임계값 1.0 bar 이상은 이상.'), 'annotation': '필터 막힘 조치 후보'}
    rule[key] = outputs
    return rule


def test_a_segment_rule_naming_another_segments_sop_passes_the_segment_check_and_the_whole_document():
    src = _source(_doc(12))
    segs = ms.segments(src, max_chars=6000)
    first, last = segs[0], segs[-1]
    prop = _proposal_for(src, first)
    assert 'SOP-HM12-1' not in {p['id'] for p in prop['procedures']}
    prop['knowledge'] = {'rules': [_rule(src, first, 'rule:hm-filter', ['SOP-HM1-1', 'SOP-HM12-1'])]}
    local = copy.deepcopy(prop)
    r = first['ranges'][0]
    view = extraction.segment_view(src, first)
    for a in [s['anchor'] for s in local['sections']] + [x for p in local['procedures'] for x in [p['anchor'], *[st['anchor'] for st in p['steps']]]] \
            + [k['anchor'] for k in local['knowledge']['rules']]:
        a['start'] -= r['start']; a['end'] -= r['start']
    with pytest.raises(ValueError, match='이 문서의 SOP가 아닙니다'):          # the whole-document rule still refuses it alone
        extraction.validate_proposal(view, copy.deepcopy(local))
    extraction.validate_proposal(view, copy.deepcopy(local), segment=True)     # the segment check defers it
    parts = [(s, _proposal_for(src, s)) for s in segs]
    parts[0] = (first, prop)
    merged = ms.merge(src, parts)
    checked = extraction.validate_proposal(src, merged)                        # and the merged document has SOP-HM12-1
    assert checked['knowledge']['rules'][0]['outputs'] == ['SOP-HM1-1', 'SOP-HM12-1']
    assert last['index'] == len(segs)


def test_an_sop_no_segment_extracted_leaves_the_rule_with_a_warning_not_a_dead_merged_result():
    src = _source(_doc(12))
    segs = ms.segments(src, max_chars=6000)
    first = segs[0]
    prop = _proposal_for(src, first)
    prop['knowledge'] = {'rules': [_rule(src, first, 'rule:partly', ['SOP-HM1-1', 'SOP-GHOST-1']),
                                   _rule(src, first, 'rule:ghost-only', ['SOP-GHOST-2']),
                                   _rule(src, first, 'rule:exclude-ghost', ['SOP-GHOST-3'], effect='EXCLUDE', key='applies_to')]}
    parts = [(s, _proposal_for(src, s)) for s in segs]
    parts[0] = (first, prop)
    merged = ms.merge(src, parts)
    checked = extraction.validate_proposal(src, merged)
    rules = {r['id']: r for r in checked['knowledge']['rules']}
    assert rules['rule:partly']['outputs'] == ['SOP-HM1-1']
    assert 'rule:ghost-only' not in rules
    assert 'rule:exclude-ghost' not in rules               # an emptied applies_to would have meant "every candidate"
    assert sum('SOP-GHOST' in w for w in checked['warnings']) == 3


def test_segmented_extraction_with_a_cross_segment_rule_finishes_through_the_worker(rt, tmp_path, monkeypatch):  # noqa: F811
    """Worker submission (validate_result on the segment view) → merged result: no correction round, the rule kept."""
    import test_manual_segments as tms
    runtime, _ = rt
    monkeypatch.setattr(ms, 'DEFAULT_MAX_CHARS', 6000)
    archive = ManualSources(tmp_path / 'manual.sqlite3')
    source = archive.save('hyd', 'powerpack.md', _doc(12).encode())
    lead = extraction.start(runtime, source, str(uuid4()))
    n = len(ms.segments(source, 6000))
    original = tms._proposal_for

    def with_rule(src, seg):            # the rule's offsets stay whole-document; the server re-finds its quote in the view
        prop = original(src, seg)
        if seg['index'] == 1:
            prop['knowledge'] = {'rules': [_rule(src, seg, 'rule:hm-filter', ['SOP-HM12-1'])]}
        return prop
    monkeypatch.setattr(tms, '_proposal_for', with_rule)
    runner = Runner(_settings(tmp_path / 'worker'), runtime.repo, exec_fn=_segment_exec(source, []), schema_prompt='x',
                    resolve_provider=lambda _: object())
    for _ in range(n):
        runner.poll_once()
    while runtime.poll_once():
        pass
    res = extraction.result(runtime, source, lead['proc_inst_id'], None)
    assert res['status'] == 'DONE' and not res.get('corrections'), res.get('corrections')
    assert res['preview']['knowledge']['rules'][0]['outputs'] == ['SOP-HM12-1']
