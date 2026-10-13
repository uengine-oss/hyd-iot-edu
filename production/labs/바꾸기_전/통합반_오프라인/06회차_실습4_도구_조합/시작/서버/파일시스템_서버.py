"""파일시스템 MCP 서버 — 허용한 폴더 안의 파일을 읽고 쓰는 도구를 내준다.

실행 방법
    python 파일시스템_서버.py [--read-only] <허용할 폴더> [<허용할 폴더> …]

    <허용할 폴더>   이 서버의 도구가 드나들 수 있는 폴더. 하나 이상 적는다. 적지 않으면 서버가 뜨지 않는다.
                    여기에 적지 않은 폴더는 어떤 도구로도 읽거나 쓸 수 없다(접근 거부).
    --read-only     읽는 도구만 내준다. 이 옵션을 주면 write_file이 도구 목록에서 빠진다.

경로 인수는 절대경로로 적거나, 첫째 허용 폴더를 기준으로 한 상대경로로 적는다.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from mcp_기본 import 기록, 도구_오류, 서버

인수들 = sys.argv[1:]
읽기_전용 = "--read-only" in 인수들
폴더들 = [a for a in 인수들 if not a.startswith("--")]
if not 폴더들:
    기록("시작하지 못함: 허용할 폴더를 하나 이상 적어야 한다. 예: python 파일시스템_서버.py --read-only <폴더>")
    sys.exit(2)
허용 = []
for 폴더 in 폴더들:
    p = Path(폴더).expanduser().resolve()
    if not p.is_dir():
        기록(f"시작하지 못함: 허용할 폴더가 없다 — {폴더}")
        sys.exit(2)
    허용.append(p)

s = 서버("filesystem", "1.0.0")
경로_설명 = "절대경로, 또는 첫째 허용 폴더를 기준으로 한 상대경로"


def 풀기(경로: str) -> Path:
    """경로를 실제 위치로 풀고, 허용한 폴더 안인지 확인한다."""
    p = Path(경로).expanduser()
    p = (p if p.is_absolute() else 허용[0] / p).resolve()
    if not any(p == a or a in p.parents for a in 허용):
        raise 도구_오류(f"접근 거부: {경로} 는 허용된 폴더 밖이다. 허용된 폴더: {', '.join(str(a) for a in 허용)}")
    return p


def 보이기(p: Path) -> str:
    for a in 허용:
        if p == a or a in p.parents:
            return (a.name + "/" + p.relative_to(a).as_posix()).rstrip("/")
    return str(p)


@s.도구("list_allowed_directories", "이 서버의 도구가 드나들 수 있는 폴더의 목록을 돌려준다. 서버를 띄울 때 정해지며 호출로는 바꿀 수 없다.")
def list_allowed_directories():
    return "\n".join(str(a) for a in 허용)


@s.도구("list_directory", "폴더 하나의 내용을 한 줄에 하나씩 돌려준다. 폴더는 [DIR], 파일은 [FILE]로 표시한다.",
        {"path": {"type": "string", "description": 경로_설명}}, 필수=("path",))
def list_directory(path):
    p = 풀기(path)
    if not p.is_dir():
        raise 도구_오류(f"폴더가 아니다: {path}")
    줄 = [("[DIR]  " if c.is_dir() else "[FILE] ") + c.name for c in sorted(p.iterdir(), key=lambda c: (c.is_file(), c.name)) if c.name != ".git"]
    return "\n".join(줄) if 줄 else "(비어 있음)"


@s.도구("read_text_file", "글 파일 하나의 내용을 그대로 돌려준다. head를 주면 앞의 그 줄 수만 돌려준다.",
        {"path": {"type": "string", "description": 경로_설명},
         "head": {"type": "integer", "description": "앞에서부터 읽을 줄 수(없으면 전부)"}}, 필수=("path",))
def read_text_file(path, head=None):
    p = 풀기(path)
    if not p.is_file():
        raise 도구_오류(f"파일이 없다: {path}")
    try:
        글 = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise 도구_오류(f"글 파일이 아니다(UTF-8로 읽을 수 없다): {path}")
    if head is not None:
        글 = "\n".join(글.splitlines()[: int(head)])
    return 글


@s.도구("get_file_info", "파일이나 폴더 하나의 크기(바이트), 고친 시각, 종류를 돌려준다.",
        {"path": {"type": "string", "description": 경로_설명}}, 필수=("path",))
def get_file_info(path):
    p = 풀기(path)
    if not p.exists():
        raise 도구_오류(f"파일이나 폴더가 없다: {path}")
    st = p.stat()
    return f"path: {보이기(p)}\ntype: {'directory' if p.is_dir() else 'file'}\nsize: {st.st_size}\nmodified: {datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}"


@s.도구("search_files", "폴더 아래의 글 파일에서 낱말이 든 줄을 찾아 「파일:줄 번호: 그 줄」로 돌려준다. 찾은 것이 없으면 「없음」을 돌려준다.",
        {"path": {"type": "string", "description": "찾기 시작할 폴더. " + 경로_설명},
         "query": {"type": "string", "description": "찾을 낱말(대소문자를 가리지 않는다)"}}, 필수=("path", "query"))
def search_files(path, query):
    p = 풀기(path)
    if not p.is_dir():
        raise 도구_오류(f"폴더가 아니다: {path}")
    찾은_것 = []
    for f in sorted(p.rglob("*")):
        if not f.is_file() or ".git" in f.parts:
            continue
        try:
            줄들 = f.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        찾은_것 += [f"{보이기(f)}:{n}: {줄.strip()}" for n, 줄 in enumerate(줄들, 1) if query.lower() in 줄.lower()]
    return "\n".join(찾은_것) if 찾은_것 else "없음"


if not 읽기_전용:
    @s.도구("write_file", "파일 하나를 새로 만들거나 통째로 덮어쓴다. 이미 있는 내용은 사라진다.",
            {"path": {"type": "string", "description": 경로_설명},
             "content": {"type": "string", "description": "파일에 쓸 내용 전체"}}, 필수=("path", "content"), 읽기_전용=False)
    def write_file(path, content):
        p = 풀기(path)
        if p.is_dir():
            raise 도구_오류(f"폴더에는 쓸 수 없다: {path}")
        if not p.parent.is_dir():
            raise 도구_오류(f"파일을 둘 폴더가 없다: {path}")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return f"썼다: {보이기(p)} ({len(content.encode('utf-8'))} 바이트)"

if __name__ == "__main__":
    기록(f"허용된 폴더: {', '.join(str(a) for a in 허용)} · 읽기 전용: {'예' if 읽기_전용 else '아니오'}")
    s.실행()
