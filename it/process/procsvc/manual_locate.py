"""A117 (r14 B2, process-gpt-memento `citations.document_locate`): the server finds where a quoted passage sits in the
archived source; the agent only has to quote it (page + quote). Character offsets were the agent's job before and the
place it was weakest — a 40-page manual needed two correction rounds for offsets alone (A094).

Resolution order, like memento: the exact string, then the same letters and digits ignoring whitespace and punctuation
(the quote is then replaced by the source's own characters), then the words with short gaps allowed between them.
A quote that matches several places is not guessed: the agent is asked for a longer quote. Offsets the agent does send
are honoured when they are right, so pre-A117 proposals still validate unchanged.
"""
from __future__ import annotations

import re

WORD_GAP = 40          # characters allowed between consecutive words of a quote in the loose pass (memento _WORD_GAP)
MIN_LOOSE_WORDS = 3


class Ambiguous(ValueError):
    pass


def _squash(text: str) -> tuple[str, list[int]]:
    """letters and digits only, with a map from squashed index → original index"""
    out, index = [], []
    for i, ch in enumerate(text):
        if ch.isalnum():
            out.append(ch.lower()); index.append(i)
    return ''.join(out), index


def _all(haystack: str, needle: str) -> list[int]:
    found, pos = [], 0
    while (at := haystack.find(needle, pos)) >= 0:
        found.append(at); pos = at + 1
    return found


def _exact(text: str, quote: str) -> list[tuple[int, int]]:
    return [(s, s + len(quote)) for s in _all(text, quote)]


def _edges(text: str, quote: str, start: int, end: int) -> tuple[int, int]:
    """A squashed match covers the first to the last letter/digit; give back the quote's own leading/trailing
    punctuation (a closing period, a bullet, a quotation mark) when the source has the same characters there."""
    i = len(quote)
    while i > 0 and not quote[i - 1].isalnum():
        i -= 1
    tail = quote[i:].strip()
    j = 0
    while j < len(quote) and not quote[j].isalnum():
        j += 1
    head = quote[:j].strip()
    if tail and text[end:end + len(tail)] == tail:
        end += len(tail)
    if head and text[start - len(head):start] == head:
        start -= len(head)
    return start, end


def _squashed(text: str, quote: str) -> list[tuple[int, int]]:
    hay, index = _squash(text)
    needle, _ = _squash(quote)
    if not needle:
        return []
    return [_edges(text, quote, index[s], index[s + len(needle) - 1] + 1) for s in _all(hay, needle)]


def _loose(text: str, quote: str) -> list[tuple[int, int]]:
    hay, index = _squash(text)
    words = [re.escape(_squash(w)[0]) for w in quote.split() if _squash(w)[0]]
    if len(words) < MIN_LOOSE_WORDS:
        return []
    rx = re.compile(f'.{{0,{WORD_GAP}}}?'.join(words))
    out, pos = [], 0
    while (m := rx.search(hay, pos)):
        start, end = m.start(), m.end()
        while (tighter := rx.search(hay, start + 1)) and tighter.end() <= end:   # latest start inside the same end (memento)
            start, end = tighter.start(), tighter.end()
        out.append((index[start], index[end - 1] + 1)); pos = end
    return out


def locate(pages: dict[int, str], anchor: dict) -> dict:
    """pages: {page: text}. anchor: {page?, start?, end?, quote}. Returns {page, start, end, quote} with the quote taken
    from the source text; raises ValueError (Ambiguous when several places match) with a message for the agent."""
    quote = anchor.get('quote')
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError('원문 인용 문자열(quote)이 필요합니다')
    page, start, end = (anchor.get(k) for k in ('page', 'start', 'end'))
    if page is not None and (type(page) is not int or page not in pages):
        raise ValueError('원문 인용 페이지가 올바르지 않습니다')
    if page is not None and type(start) is int and type(end) is int and 0 <= start < end <= len(pages[page]) \
            and pages[page][start:end] == quote:
        return {'page': page, 'start': start, 'end': end, 'quote': quote}
    candidates = [page] if page is not None else sorted(pages)
    for finder, how in ((_exact, 'exact'), (_squashed, 'normalized'), (_loose, 'loose')):
        hits = [(p, s, e) for p in candidates for s, e in finder(pages[p], quote)]
        if not hits:
            continue
        if len(hits) > 1 and type(start) is int:
            exact_given = [h for h in hits if h[1] == start]
            if len(exact_given) == 1:
                hits = exact_given
        if len(hits) > 1:
            where = ', '.join(f'페이지 {p} {s}~{e}' for p, s, e in hits[:5])
            raise Ambiguous(f'원문 인용이 {len(hits)}곳에 있어 한 곳을 정할 수 없습니다 ({where}). 앞뒤를 더 붙인 긴 인용으로 한 곳을 특정하세요: {quote[:60]!r}')
        p, s, e = hits[0]
        return {'page': p, 'start': s, 'end': e, 'quote': pages[p][s:e], 'located': how}
    scope = f'페이지 {page}' if page is not None else '전체 페이지'
    raise ValueError(f'원문 인용 문자열을 {scope}에서 찾지 못했습니다 (글자·숫자만 비교해도 없음): quote={quote[:60]!r}')
