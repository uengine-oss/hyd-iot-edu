"""Copy today's local LiteLLM settings to the existing offline lab, without printing them."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('OPENAI_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL')
ASSIGNMENT = re.compile(r'^\s*([A-Z_][A-Z_0-9]*)\s*=')


def values(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        match = ASSIGNMENT.match(line)
        if not match:
            continue
        value = line[match.end():].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[match[1]] = value
    return result


def sync(root: Path) -> str:
    source = values((root / '.env').read_text(encoding='utf-8-sig'))
    # A managed classroom credential is not a direct LiteLLM key.
    if source.get('HYD_CLASSROOM_URL'):
        return 'managed'
    if any(not source.get(key) or any(ord(c) < 32 for c in source[key]) for key in FIELDS):
        raise ValueError('수업 중계 주소·키·모델 설정을 확인하세요.')
    lab = root / 'course' / 'labs' / 'offline' / '05-2-cause-agent'
    if not lab.is_dir():
        return 'absent'
    target = lab / '.env'
    if target.exists():
        with target.open('r', encoding='utf-8-sig', newline='') as stream:
            original = stream.read()
    else:
        original = ''
    lines = original.splitlines(keepends=True)
    kept = []
    for line in lines:
        match = ASSIGNMENT.match(line)
        if not match or match[1] not in FIELDS:
            kept.append(line)
    newline = '\r\n' if '\r\n' in original else '\n'
    body = ''.join(kept)
    if body and not body.endswith(('\n', '\r')):
        body += newline
    body += ''.join(f'{key}={source[key]}{newline}' for key in FIELDS)
    if target.exists() and body == original:
        return 'unchanged'
    fd, name = tempfile.mkstemp(prefix='.env.sync-', dir=lab)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return 'updated'


if __name__ == '__main__':
    try:
        state = sync(ROOT)
    except (OSError, UnicodeError, ValueError):
        raise SystemExit('실습랩 수업 키 설정을 준비하지 못했습니다. .env와 폴더 쓰기 권한을 확인하세요.') from None
    print({'updated':'실습랩 수업 키 연결 준비 완료', 'unchanged':'실습랩 수업 키 연결 유지',
           'managed':'관리 서버 방식은 실습랩 키를 별도로 설정합니다',
           'absent':'실습랩 폴더가 없어 키 연결을 건너뜁니다'}[state])
