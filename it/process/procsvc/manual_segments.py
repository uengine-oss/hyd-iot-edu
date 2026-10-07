"""A093 — large documents are extracted per segment and merged deterministically (process-gpt-bpmn-extractor: section
boundary → per-section extraction → merge; test_chunk_integration). Anchors stay absolute page coordinates, so every
segment proposal is validated against the same pinned source and the merged proposal passes the unchanged contract.

A segment is a list of page ranges (`ranges`): a PDF manual of 80 short pages packs many whole pages into one segment
(A094, real Daikin manuals: 50~80 pages of 1~6 K chars), a Markdown manual with one huge page is cut at headings."""
from __future__ import annotations

import re

HEADING = re.compile(r'^(#{1,3}) ', re.M)
DEFAULT_MAX_CHARS = 40_000
MIN_SEGMENT_CHARS = 2_000


def ranges_of(seg: dict) -> list[dict]:
    """Page ranges of a segment; a segment pinned before A094 carried a single page/start/end."""
    if seg.get('ranges'):
        return seg['ranges']
    return [{'page': seg['page'], 'start': seg['start'], 'end': seg['end']}]


def _blocks(source: dict, max_chars: int):
    """Heading-bounded blocks (page, start, end) in document order; a block never straddles a heading or a page, and a
    block longer than max_chars is cut at the last paragraph break before the limit (never mid-line)."""
    for page in source['pages']:
        text = page['text']
        if not text:
            continue
        cuts = sorted({0, *(m.start() for m in HEADING.finditer(text)), len(text)})
        for a, b in zip(cuts, cuts[1:]):
            while b - a > max_chars:
                cut = text.rfind('\n\n', a, a + max_chars)
                cut = cut + 2 if cut > a else a + max_chars
                yield page['page'], a, cut
                a = cut
            if b > a:
                yield page['page'], a, b


def segments(source: dict, max_chars: int | None = None) -> list[dict]:
    """Pack heading-bounded blocks into segments of at most `max_chars` characters, in order, whole pages first.
    Returns [] when the whole document fits in one task."""
    max_chars = max_chars or DEFAULT_MAX_CHARS
    if max_chars < MIN_SEGMENT_CHARS:
        raise ValueError('segment size too small')
    if sum(len(p['text']) for p in source['pages']) <= max_chars:
        return []
    out, cur, size = [], [], 0
    for page, a, b in _blocks(source, max_chars):
        if size and size + (b - a) > max_chars:
            out.append(cur); cur, size = [], 0
        if cur and cur[-1]['page'] == page and cur[-1]['end'] == a:
            cur[-1]['end'] = b
        else:
            cur.append({'page': page, 'start': a, 'end': b})
        size += b - a
    if cur:
        out.append(cur)
    return [{'index': i + 1, 'total': len(out), 'ranges': r, 'chars': sum(x['end'] - x['start'] for x in r)} for i, r in enumerate(out)]


def within(anchor: dict, seg: dict) -> bool:
    return any(anchor.get('page') == r['page'] and r['start'] <= anchor.get('start', -1) and anchor.get('end', 10**12) <= r['end']
               for r in ranges_of(seg))


def merge(source: dict, parts: list[tuple[dict, dict]], review_feedback: dict | None = None) -> dict:
    """parts: [(segment, proposal)] with whole-document anchors. Sections and procedures are concatenated; a ref or SOP id
    that two segments both propose keeps the first and records the duplicate as a warning (a reviewer decides); page
    reviews are joined per page, a page with no text gets a deterministic note; every anchor must lie inside its own
    segment (a segment may not cite outside its range). A reviewer's MISSING item that no segment produced is recorded,
    because each segment was told to ignore items outside its range."""
    merged = {'source_id': source['source_id'], 'sections': [], 'procedures': [], 'page_reviews': [], 'warnings': []}
    seen_ref, seen_sop, reviews = {}, {}, {}
    for seg, prop in sorted(parts, key=lambda x: x[0]['index']):
        tag = f"[구간 {seg['index']}/{seg['total']}]"
        for s in prop.get('sections') or []:
            if not within(s.get('anchor') or {}, seg):
                raise ValueError(f"{tag} 절 {s.get('ref')}의 인용이 담당 구간 밖입니다")
            if s['ref'] in seen_ref:
                merged['warnings'].append(f"{tag} 절 {s['ref']}이(가) 구간 {seen_ref[s['ref']]}에서도 제안됨 — 첫 제안을 유지, 검토 필요")
                continue
            seen_ref[s['ref']] = seg['index']; merged['sections'].append(s)
        for p in prop.get('procedures') or []:
            if not within(p.get('anchor') or {}, seg) or any(not within(st.get('anchor') or {}, seg) for st in p.get('steps') or []):
                raise ValueError(f"{tag} SOP {p.get('id')}의 인용이 담당 구간 밖입니다")
            if p['id'] in seen_sop:
                merged['warnings'].append(f"{tag} SOP {p['id']}이(가) 구간 {seen_sop[p['id']]}에서도 제안됨 — 첫 제안을 유지, 검토 필요")
                continue
            seen_sop[p['id']] = seg['index']; merged['procedures'].append(p)
        for r in prop.get('page_reviews') or []:
            reviews.setdefault(r['page'], []).append(f"{tag} {r['note']}")
        merged['warnings'] += [f"{tag} {w}" for w in prop.get('warnings') or []]
    for page in source['pages']:
        if not page['text'] and page['page'] not in reviews:
            reviews[page['page']] = ['원문 글자가 없는 페이지 — 구간 추출 대상이 아니었음(빈 페이지 검토는 원문 보관 단계에서 끝남)']
    merged['page_reviews'] = [{'page': page, 'note': ' / '.join(notes)} for page, notes in sorted(reviews.items())]
    for item in (review_feedback or {}).get('items') or []:
        target = item.get('target') or ''
        if item.get('verdict') == 'MISSING' and target not in seen_ref and target not in seen_sop \
                and not any(target in w for w in merged['warnings']):
            merged['warnings'].append(f"검토 항목 {target}(MISSING): 어느 구간도 원문에서 찾지 못했고 이유도 남기지 않음 — 사람이 원문을 다시 확인")
    return merged
