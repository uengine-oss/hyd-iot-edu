"""A093 — heading-bounded segmentation and deterministic merge of per-segment proposals (bpmn-extractor chunk → merge)."""
import json
from uuid import uuid4

import pytest

from procsvc import engine, manual_extraction as extraction, manual_segments as ms
from procsvc.manual_sources import ManualSources
from worker.runner import Runner
from test_worker import _settings, _fake_exec
from test_instances import rt


def _doc(chapters, lines=60, page_split=None):
    text = ''
    for c in range(1, chapters + 1):
        text += f'# {c}장 장비\n\n## HM-{c}.1 기준\n\n' + f'{c}장 판정 기준 설명 문장입니다. 임계값 {c}.0 bar 이상은 이상.\n' * lines
        text += f'\n### SOP-HM{c}-1 조치\n선행 조건: 정비 관리자 승인.\n1. 전원을 차단한다({c}장).\n2. 필터를 교체한다({c}장).\n\n'
    return text


def _source(text, sid='manual:doc:abc'):
    return {'source_id': sid, 'document_id': 'doc', 'filename': 'm.md', 'status': 'READY', 'pages': [{'page': 1, 'text': text}]}


def test_small_document_is_not_segmented_and_large_one_splits_only_at_headings():
    assert ms.segments(_source(_doc(1))) == []
    src = _source(_doc(12))
    segs = ms.segments(src, max_chars=6000)
    text = src['pages'][0]['text']
    R = lambda s: s['ranges'][0]
    assert len(segs) > 1 and R(segs[0])['start'] == 0 and R(segs[-1])['end'] == len(text) and all(len(s['ranges']) == 1 for s in segs)
    assert all(R(a)['end'] == R(b)['start'] for a, b in zip(segs, segs[1:]))        # contiguous, no gap, no overlap
    assert all(s['chars'] <= 6000 for s in segs)
    assert all(text[R(s)['start']:].startswith('#') for s in segs[1:])              # every cut lands on a heading
    assert [s['index'] for s in segs] == list(range(1, len(segs) + 1)) and {s['total'] for s in segs} == {len(segs)}


def test_one_oversized_block_is_cut_at_a_paragraph_break_never_mid_line():
    big = '# 유일한 장\n\n' + ''.join(f'문단 {i} 내용입니다.\n\n' for i in range(900))
    src = _source(big)
    segs = ms.segments(src, max_chars=3000)
    text = src['pages'][0]['text']
    assert len(segs) > 1 and segs[-1]['ranges'][-1]['end'] == len(text)
    for s in segs[1:]:
        a = s['ranges'][0]['start']
        assert text[a - 2:a] == '\n\n' and text[a:a + 3].startswith('문단')
    assert ''.join(text[r['start']:r['end']] for s in segs for r in s['ranges']) == text


def test_many_short_pages_pack_into_few_segments_at_page_boundaries():
    """A094: a real PDF manual is 50~80 pages of 1~6 K chars; whole pages are packed, never one task per page."""
    pages = [{'page': i, 'text': f'Chapter {i}. TOPIC {i}\n' + f'Line {i} of the manual body text, with a value of {i * 3} bar.\n' * 40} for i in range(1, 81)]
    src = {'source_id': 'manual:doc:pdf', 'document_id': 'doc', 'filename': 'm.pdf', 'status': 'READY', 'pages': pages}
    total = sum(len(p['text']) for p in pages)
    segs = ms.segments(src, max_chars=40000)
    assert 2 <= len(segs) <= 6 and segs[-1]['total'] == len(segs)
    assert all(s['chars'] <= 40000 for s in segs) and sum(s['chars'] for s in segs) == total
    covered = [(r['page'], r['start'], r['end']) for s in segs for r in s['ranges']]
    assert covered == [(p['page'], 0, len(p['text'])) for p in pages]                 # every page whole, in order, once
    assert all(len({r['page'] for r in s['ranges']}) == len(s['ranges']) for s in segs)  # a page appears once per segment
    view = extraction.segment_view(src, segs[1])
    assert [p['page'] for p in view['pages']] == [r['page'] for r in segs[1]['ranges']] and view['source_id'] == src['source_id']


def test_segment_size_floor_and_empty_pages():
    with pytest.raises(ValueError):
        ms.segments(_source(_doc(12)), max_chars=100)
    src = {'source_id': 'manual:doc:abc', 'document_id': 'doc', 'filename': 'm.md', 'status': 'READY',
           'pages': [{'page': 1, 'text': ''}, {'page': 2, 'text': _doc(12)}]}
    segs = ms.segments(src, max_chars=6000)
    assert {r['page'] for s in segs for r in s['ranges']} == {2}
    merged = ms.merge(src, [(s, {'sections': [], 'procedures': [], 'page_reviews': [{'page': 2, 'note': f'구간 {s["index"]} 검토'}], 'warnings': []}) for s in segs])
    assert [r['page'] for r in merged['page_reviews']] == [1, 2] and '글자가 없는' in merged['page_reviews'][0]['note']
    assert merged['page_reviews'][1]['note'].count('[구간') == len(segs)


def _anchor(src, seg, quote):
    text = src['pages'][0]['text']
    start = text.index(quote, seg['ranges'][0]['start'])
    return {'source_id': src['source_id'], 'page': 1, 'start': start, 'end': start + len(quote), 'quote': quote}


def _proposal_for(src, seg):
    """What a correct agent returns for one segment, already in whole-document coordinates."""
    r = seg['ranges'][0]
    text = src['pages'][0]['text'][r['start']:r['end']]
    secs, procs = [], []
    import re
    for m in re.finditer(r'^## (HM-(\d+)\.1) 기준', text, re.M):
        ref, c = m.group(1), m.group(2)
        secs.append({'ref': ref, 'title': f'{c}장 기준', 'excerpt': f'임계값 {c}.0 bar 이상은 이상.', 'anchor': _anchor(src, seg, f'임계값 {c}.0 bar 이상은 이상.')})
        if f'### SOP-HM{c}-1' in text:
            steps = [f'전원을 차단한다({c}장).', f'필터를 교체한다({c}장).']
            procs.append({'id': f'SOP-HM{c}-1', 'name': f'{c}장 조치', 'section': ref, 'anchor': _anchor(src, seg, f'### SOP-HM{c}-1 조치'),
                          'steps': [{'order': i, 'text': t, 'manual': ref, 'anchor': _anchor(src, seg, t)} for i, t in enumerate(steps, 1)]})
    return {'source_id': src['source_id'], 'sections': secs, 'procedures': procs, 'warnings': [f'SOP-HM1-1 등록 제안'] if seg['index'] == 1 else [],
            'page_reviews': [{'page': 1, 'note': f'구간 {seg["index"]} 검토'}]}


def test_merge_keeps_order_rejects_out_of_range_citations_and_flags_duplicates():
    src = _source(_doc(12))
    segs = ms.segments(src, max_chars=6000)
    parts = [(s, _proposal_for(src, s)) for s in segs]
    merged = ms.merge(src, parts)
    assert [s['ref'] for s in merged['sections']] == [f'HM-{c}.1' for c in range(1, 13)]
    assert [p['id'] for p in merged['procedures']] == [f'SOP-HM{c}-1' for c in range(1, 13)]
    assert merged['warnings'] == ['[구간 1/%d] SOP-HM1-1 등록 제안' % len(segs)]
    extraction.validate_proposal(src, merged)                                        # the whole-document contract holds
    # a segment citing outside its own range is refused, even if the quote is real elsewhere in the document
    bad = [(s, json.loads(json.dumps(p))) for s, p in parts]
    bad[1][1]['sections'][0]['anchor'] = parts[0][1]['sections'][0]['anchor']
    with pytest.raises(ValueError, match='담당 구간 밖'):
        ms.merge(src, bad)
    # the same SOP proposed by two segments keeps the first and warns
    dup = [(s, json.loads(json.dumps(p))) for s, p in parts]
    dup[1][1]['procedures'].append(json.loads(json.dumps(dup[1][1]['procedures'][0])) | {'id': parts[0][1]['procedures'][0]['id']})
    dup[1][1]['procedures'][-1]['anchor'] = dup[1][1]['procedures'][0]['anchor']
    m2 = ms.merge(src, dup)
    assert [p['id'] for p in m2['procedures']] == [p['id'] for p in merged['procedures']] and any('에서도 제안됨' in w for w in m2['warnings'])
    # a reviewer's MISSING item that no segment produced is surfaced instead of vanishing
    m3 = ms.merge(src, parts, review_feedback={'items': [{'target': 'SOP-GHOST-9', 'verdict': 'MISSING', 'note': '있을 텐데'}]})
    assert any('SOP-GHOST-9' in w and 'MISSING' in w for w in m3['warnings'])


def _segment_exec(src, requests):
    """Test double: answers each segment task with the correct proposal for *its* pinned slice (local coordinates)."""
    from pathlib import Path
    from cliagents import ExecEvent, ExecEventKind
    from worker.runner import PROMPT_FILE
    def fn(provider, request, env):
        requests.append(request)
        prompt = request.prompt
        if PROMPT_FILE in prompt:
            prompt = (Path(request.workdir) / PROMPT_FILE).read_text(encoding='utf8')
        inputs = json.loads(prompt.split('[InputData]\n')[1].split('\n\n##')[0])
        seg = inputs['segment']; view = inputs['manual_source']
        r = seg['ranges'][0]
        assert view['pages'] == [{'page': r['page'], 'text': src['pages'][0]['text'][r['start']:r['end']]}]
        prop = _proposal_for(src, seg)
        for a in [s['anchor'] for s in prop['sections']] + [x for p in prop['procedures'] for x in [p['anchor'], *[st['anchor'] for st in p['steps']]]]:
            a['start'] -= r['start']; a['end'] -= r['start']                         # the agent cites what it sees
        yield ExecEvent(kind=ExecEventKind.RUN_START, text='claude', session_id='sess-' + str(seg['index']))
        yield ExecEvent(kind=ExecEventKind.RESULT, text=json.dumps({'proposal': prop}, ensure_ascii=False), session_id='sess-' + str(seg['index']))
    return fn


def test_large_document_runs_one_task_per_segment_and_reports_one_merged_result(rt, tmp_path, monkeypatch):
    runtime, _ = rt
    monkeypatch.setattr(ms, 'DEFAULT_MAX_CHARS', 6000)
    archive = ManualSources(tmp_path / 'manual.sqlite3')
    source = archive.save('hyd', 'powerpack.md', _doc(12).encode())
    n = len(ms.segments(source, 6000)); assert n >= 3
    rid = str(uuid4())
    lead = extraction.start(runtime, source, rid)
    assert extraction.start(runtime, source, rid)['proc_inst_id'] == lead['proc_inst_id']               # idempotent per request
    runs = runtime.repo.list_source_runs('hyd', extraction.DEFINITION_ID, 'manual-extraction:' + source['source_id'] + ':')
    assert len(runs) == n
    assert engine.variables(lead)['segment']['index'] == 1 and len(json.dumps(engine.variables(lead)['manual_source'])) < len(json.dumps(source)) / 2
    before = extraction.result(runtime, source, lead['proc_inst_id'], None)
    assert before['preview'] is None and before['progress'] == {'done': 0, 'total': n} and len(before['segments']) == n
    reqs = []
    runner = Runner(_settings(tmp_path / 'worker'), runtime.repo, exec_fn=_segment_exec(source, reqs), schema_prompt='x', resolve_provider=lambda _: object())
    done = 0
    for _ in range(n):
        done += runner.poll_once()
    assert done == n and runtime.poll_once() >= 1
    while runtime.poll_once():
        pass
    # any sibling id reports the same group under the lead instance; the merged proposal is whole-document
    for run in runs:
        res = extraction.result(runtime, source, run['proc_inst_id'], None)
        assert res['status'] == 'DONE' and res['instance'] == lead['proc_inst_id'] and res['progress'] == {'done': n, 'total': n}
    pv = res['preview']
    assert [s['ref'] for s in pv['sections']] == [f'HM-{c}.1' for c in range(1, 13)]
    assert {p['id']: len(p['steps']) for p in pv['procedures']} == {f'SOP-HM{c}-1': 2 for c in range(1, 13)}
    text = source['pages'][0]['text']
    assert all(text[st['anchor']['start']:st['anchor']['end']] == st['anchor']['quote'] for p in pv['procedures'] for st in p['steps'])
    assert len(pv['extraction']['segments']) == n and pv['extraction']['instance'] == lead['proc_inst_id'] and pv['page_reviews'][0]['note'].count('[구간') == n
    assert pv['coverage']['ratio'] > 0
    # a tampered sibling input (not the archive's text at its coordinates) is refused as a whole
    sib = runtime.repo.get_instance(runs[-1]['proc_inst_id'])
    import copy
    wrong = copy.deepcopy(sib); engine.variables(wrong)['manual_source']['pages'][0]['text'] += '!'
    runtime.repo.update_instance(wrong)
    with pytest.raises(ValueError, match='보관 원문이 다릅니다'):
        extraction.result(runtime, source, lead['proc_inst_id'], None)
