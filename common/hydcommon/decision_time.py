"""Require explicit dates/zones for numeric clock times in decision prose.

This checks unambiguous notation, not whether every natural-language time claim
is true. Structured window validation remains the authority for execution.
"""
from datetime import datetime
import re

CLOCK = re.compile(r'(?<!\d)\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?!\d)')
STAMP = re.compile(
    r'(?<!\d)(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<clock>\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)'
    r'\s*\(?(?P<zone>Z|[+-]\d{2}:\d{2}|UTC|KST)\)?(?![A-Za-z0-9_:+-])')


def validate_explanation(output):
    decision = output.get('decision')
    text = decision.get('explanation') if isinstance(decision, dict) else None
    if not isinstance(text, str):
        return
    spans = []
    for match in STAMP.finditer(text):
        zone = {'UTC': '+00:00', 'KST': '+09:00', 'Z': '+00:00'}.get(match['zone'], match['zone'])
        try:
            datetime.fromisoformat(match['date']+'T'+match['clock']+zone)
        except ValueError:
            continue
        spans.append(match.span())
    if any(not any(start <= clock.start() and clock.end() <= end for start, end in spans)
           for clock in CLOCK.finditer(text)):
        raise ValueError('decision.explanation의 숫자 시각에는 날짜·시간대가 필요합니다. '
                         '도구의 실제 window.starts_at을 시간대까지 그대로 쓰거나, 정확한 시각을 확인할 수 없으면 '
                         '“이번 예정된 정비 시간”처럼 카드의 이름을 쓰세요. UTC/KST·날짜를 추측해서 붙이지 마세요.')
