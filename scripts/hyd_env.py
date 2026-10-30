"""저장소 루트 .env 를 읽고 고치는 한 벌 — 시작 · 점검 · 포트 준비가 모두 이것만 쓴다(셸 · PowerShell 이 따로 해석하지 않는다).

읽는 규칙은 Docker Compose(v5.6.1)가 같은 파일을 읽는 규칙과 같다 — 컨테이너가 받는 값과 시작이 판단한 값이 갈라지지 않게:
  · 맨 앞 BOM, 줄 끝 CR 은 무시한다. 빈 줄과 # 로 시작하는 줄은 주석이다. `export KEY=값` 도 받는다.
  · `KEY = 값` 처럼 = 앞뒤 공백은 지운다. 키에 공백이 있으면 그 줄 번호로 오류를 낸다(Compose 도 거절한다).
  · 따옴표 없는 값: 처음 나오는 「공백 + #」 부터 줄 끝까지가 주석이고, 끝 공백을 지운다(`a#b` · `x<탭># y` 는 값 그대로).
  · '…' 은 글자 그대로, "…" 은 \\n · \\" · \\\\ 를 풀고 여러 줄도 받는다. 닫는 따옴표 뒤의 글자는 버린다.
  · 같은 키가 여러 번 있으면 마지막 값이 쓰인다. 값 안의 $변수 치환은 하지 않는다(시작이 읽는 키는 쓰지 않는다).
쓸 때는 그 키가 있는 줄을 모두 새 값으로 바꾸고(없으면 끝에 붙임 · 공백 · # 이 든 값은 따옴표로 감쌈) 나머지 줄은 그대로 둔다.
줄 끝은 LF, BOM 없이, 같은 폴더의 임시 파일(.env.hyd-tmp — git · Docker 가 무시)을 거쳐 한 번에 바꾼다.

    python scripts/hyd_env.py ai-mode [--record]   # 키 유무로 AI 단계 방식(live · replay · record)을 정해 .env 의 AI_MODE 에 적고 그 낱말을 출력
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_.-]*')
ESCAPES = {'n': '\n', 'r': '\r', 't': '\t', '"': '"', '\\': '\\', '$': '$'}


class EnvFileError(ValueError):
    """.env 의 한 줄을 읽을 수 없다 — 줄 번호와 무엇이 틀렸는지를 학생 말로."""


def _assignments(text: str):
    """(키, 값, 시작 줄 번호, 끝 줄 번호) — 주석 · 빈 줄은 건너뛴다."""
    lines = text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i = 0
    while i < len(lines):
        first = i
        line = lines[i].lstrip()
        i += 1
        if not line or line.startswith('#'):
            continue
        if line.startswith('export ') or line.startswith('export\t'):
            line = line[7:].lstrip()
        cut = min((p for p in (line.find('='), line.find(':')) if p >= 0), default=-1)
        if cut < 0:
            raise EnvFileError(f'.env {first + 1}번째 줄에 「이름=값」 모양이 아닌 글이 있습니다. 그 줄을 지우거나 맨 앞에 #를 붙이세요.')
        name = line[:cut].strip()
        if not KEY.fullmatch(name):
            raise EnvFileError(f'.env {first + 1}번째 줄의 이름 「{name}」을 읽을 수 없습니다(이름에는 공백 · 한글을 쓰지 않습니다).')
        rest = line[cut + 1:].lstrip(' \t')
        if rest[:1] in ('"', "'"):
            quote, body, j = rest[0], rest[1:], 0
            buf: list[str] = []
            while True:
                while j < len(body):
                    ch = body[j]
                    if quote == '"' and ch == '\\' and j + 1 < len(body):
                        buf.append(ESCAPES.get(body[j + 1], '\\' + body[j + 1]))
                        j += 2
                        continue
                    if ch == quote:
                        break
                    buf.append(ch)
                    j += 1
                if j < len(body):
                    break
                if i >= len(lines):
                    raise EnvFileError(f'.env {first + 1}번째 줄에서 연 따옴표({quote})가 닫히지 않았습니다.')
                buf.append('\n')
                body, j = lines[i], 0
                i += 1
            value = ''.join(buf)
        else:
            value = rest.split(' #', 1)[0].rstrip()
        yield name, value, first, i - 1


def parse(text: str) -> dict[str, str]:
    """.env 글 → {키: 값}. 같은 키는 마지막 값."""
    return {name: value for name, value, _, _ in _assignments(text)}


def read(path: Path) -> dict[str, str]:
    return parse(path.read_text(encoding='utf-8')) if path.exists() else {}


def _formatted(name: str, value: str) -> str:
    """값을 다시 읽었을 때 같은 값이 되는 줄 — 공백 · # · 따옴표 · \\ 가 있으면 "…"로 감싼다($ 가 있으면 치환되지 않게 '…')."""
    if not KEY.fullmatch(name):
        raise EnvFileError(f'.env 에 쓸 이름 「{name}」이 올바르지 않습니다.')
    if '\n' in value or '\r' in value:
        raise EnvFileError(f'.env 의 {name} 에 여러 줄 값은 쓰지 않습니다.')
    if not re.search(r'[\s#"\'\\$]', value):
        return f'{name}={value}'
    if '$' in value and "'" not in value:
        return f"{name}='{value}'"
    if '$' in value:
        raise EnvFileError(f'.env 의 {name} 에 $ 와 작은따옴표가 함께 든 값은 쓰지 않습니다.')
    return f'{name}="' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def with_updates(text: str, updates: dict[str, str]) -> str:
    """키가 있는 줄을 모두 새 값으로, 없는 키는 끝에 붙인다. 나머지 줄은 그대로, 줄 끝 LF."""
    formatted = {name: _formatted(name, value) for name, value in updates.items()}
    lines = text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    spans = {}
    for name, _, first, last in _assignments(text):
        spans.setdefault(name, []).append((first, last))
    drop: set[int] = set()
    for name, line in formatted.items():
        for first, last in spans.get(name, []):
            lines[first] = line
            drop.update(range(first + 1, last + 1))   # 여러 줄 값의 나머지 줄
    out = [line for n, line in enumerate(lines) if n not in drop]
    out.extend(line for name, line in formatted.items() if name not in spans)
    return '\n'.join(out) + '\n'


def write_updates(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    new = with_updates(text, updates)
    if new == text:
        return
    temp = path.with_name(path.name + '.hyd-tmp')
    temp.write_bytes(new.encode('utf-8'))
    os.replace(temp, path)


def ai_mode(values: dict[str, str], record: bool = False) -> str:
    """AI 단계 방식: 키가 있으면 live(실제 AI · 강의 중계), 없으면 replay(강사가 저장한 응답), --record 는 키가 있어야 한다."""
    has_key = bool(values.get('LLM_API_KEY', '').strip())
    if record:
        if not has_key:
            raise EnvFileError('AI 응답 저장은 실제 AI로 진행합니다. .env의 LLM_API_KEY= 뒤에 강의 중계 키를 넣고 다시 실행하세요.')
        return 'record'
    return 'live' if has_key else 'replay'


def main(argv: list[str], root: Path = ROOT) -> int:
    args = argv[1:]
    if not args or args[0] != 'ai-mode' or args[1:] not in ([], ['--record']):
        print('사용: hyd_env.py ai-mode [--record]', file=sys.stderr)
        return 2
    env = root / '.env'
    try:
        mode = ai_mode(read(env), record=args[1:] == ['--record'])
        write_updates(env, {'AI_MODE': mode})
    except EnvFileError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print('.env 를 UTF-8 글자로 읽을 수 없습니다. 메모장에서 열어 「다른 이름으로 저장 → 인코딩 UTF-8」로 저장한 뒤 다시 시작하세요.', file=sys.stderr)
        return 1
    print(mode)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
