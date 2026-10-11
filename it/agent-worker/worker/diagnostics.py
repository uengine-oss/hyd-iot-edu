"""Bound CLI diagnostics without losing the final failure or exposing credentials."""
import re


def excerpt(value, limit=800):
    text = str(value)
    text = re.sub(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@', r'\1[redacted]@', text)
    text = re.sub(r'(?i)(\bBearer\s+)[^\s,;"\']+', r'\1[redacted]', text)
    text = re.sub(r'''(?ix)(\b(?:[a-z0-9_]*(?:password|passwd|secret|token|api_key|apikey)[a-z0-9_]*)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''',
                  r'\1[redacted]', text)
    if len(text) <= limit:
        return text
    marker = '\n… [중간 생략] …\n'
    head = max(1, (limit - len(marker)) // 4)
    return text[:head] + marker + text[-(limit - len(marker) - head):]
