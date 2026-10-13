# -*- coding: utf-8 -*-
"""강의 프로젝트 구조를 **스스로 찾는다.** 경로를 하드코딩하지 않기 위한 것.

    python 프로젝트탐지.py             현재 위치에서 찾아 사람이 읽는 표로
    python 프로젝트탐지.py --json      다른 스크립트가 쓸 JSON
    python 프로젝트탐지.py <경로>      그 경로에서 시작

왜 필요한가
    같은 워크스페이스인데 프로젝트마다 구조가 다르다 —

      「2일 리허설」   핸드오프.md · 강의/ · 제작/빌드도구/ · 강의/.venv (uv)
      「9월 본강의」   HANDOFF.md · 문서/ · 실습자산/ · 실습자산/.venv312 (pip)

    **경로를 박으면 다른 프로젝트에서 안 돈다.** 그래서 찾는다.

무엇을 찾나
    루트 · 인계문서 · 문서폴더 · 코드폴더 · 가이드 · 그림 · 파이썬 · 빌드도구 · 검사도구

찾는 방법
    **파일 이름을 여러 개 후보로 두고, 없으면 「없다」고 돌려준다.**
    억지로 만들어내지 않는다 — 없는 것을 있다고 하면 그 뒤가 전부 틀어진다.
"""
from __future__ import annotations

import json
import os
import re as _re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W = 78

# ── 이름 후보 — 프로젝트마다 다르게 부른다 ───────────────────────────
인계문서_후보 = ["인계.md", "인수인계.md", "HANDOFF.md", "핸드오프.md",
                 "handoff.md", "HANDOFF.MD",
                 # 프로젝트마다 앞에 말을 붙인다 — 「다음세션_인계」·「인계문서」.
                 # 이름 하나가 어긋나면 프로젝트를 통째로 못 찾는다 【2026-09-18 실제로 당함】.
                 "다음세션_인계.md", "인계문서.md", "다음세션인계.md"]
문서폴더_후보 = ["설계문서", "설계", "문서", "docs", "documents", "자료"]
코드폴더_후보 = ["실습코드", "실습자산", "완성본", "강의", "labs", "실습", "src"]
가이드_패턴 = ["실습가이드*", "*가이드*.md", "Day*.md", "*일차*.md", "guide*"]
그림폴더_후보 = ["그림", "images", "img", "figures", "캡처"]

# ★ 폴더 이름이 「가이드」면 그 안의 .md 는 파일명이 뭐든 가이드다.
#   `01_골격이_선다.md` 처럼 이름에 「가이드」·「Day」·「일차」가 없는 프로젝트가 있다.
#   패턴만 보면 그런 프로젝트의 가이드를 통째로 놓친다.
가이드폴더_후보 = ["가이드", "실습가이드", "guides", "guide"]

# 워크스페이스 전체에서 찾을 도구 — 프로젝트를 넘나든다
도구_후보 = {
    "터미널그림": ["터미널그림.py", "terminal_image.py"],
    "일치검사": ["일치검사.py", "consistency_check.py"],
    "검토자료만들기": ["검토자료만들기.py", "make_zip.py"],
    "회귀": ["회귀.py", "regression.py"],
    "md2pdf": ["md2pdf.py"],
}

건너뛸폴더 = {".git", "__pycache__", "node_modules", ".pytest_cache",
              "_참고원본", ".claude", "venv", "env"}


def _건너뛸까(name: str) -> bool:
    """`.venv*` 는 **이름이 뭐든** 가상환경이다. 박아 두면 새 이름을 놓친다."""
    return name in 건너뛸폴더 or name.startswith(".venv")


@dataclass
class 프로젝트:
    루트: str = ""
    이름: str = ""
    인계문서: str = ""
    인계폴더: str = ""            # 인계가 파일 하나가 아니라 **폴더로 쪼개진** 경우
    인계폴더파일: list[str] = field(default_factory=list)
    문서폴더: str = ""
    코드폴더: str = ""
    가이드폴더: str = ""
    그림폴더: str = ""
    파이썬: str = ""
    파이썬종류: str = ""          # uv | venv | system
    워크스페이스: str = ""
    도구: dict[str, str] = field(default_factory=dict)
    가이드파일: list[str] = field(default_factory=list)
    랩개수: int = 0
    경고: list[str] = field(default_factory=list)


def _인계폴더찾기(root: Path, 가이드: Path | None) -> tuple[Path | None, list[Path]]:
    """인계가 **파일 하나가 아니라 폴더로 쪼개진** 경우를 찾는다.

    ⚠ 파일 하나만 찾다가 `핸드오프_v2/` 11개 220KB 를 통째로 놓쳤다.
      훅이 「읽어야 할 것 4개」라고 말했는데 **진짜 정본이 그 폴더 안에 있었다.**

    두 가지 중 하나면 인계 묶음이다 —
      · 폴더 이름에 핸드오프·인계·handoff·지시 가 들어간다
      · `00_`·`01_` 처럼 **번호가 붙은 md** 가 셋 이상이다
    학생용 가이드 폴더는 뺀다 — 그건 우리가 읽을 것이 아니다.
    """
    이름표 = ("핸드오프", "인계", "handoff", "지시", "인수인계")
    번호 = __import__("re").compile(r"^\d{1,2}[_\-. ]")
    best: tuple[int, Path | None, list[Path]] = (0, None, [])

    for d in sorted(p for p in root.iterdir() if p.is_dir() and not _건너뛸까(p.name)):
        if 가이드 and d.resolve() == 가이드.resolve():
            continue
        mds = sorted(f for f in d.glob("*.md") if f.is_file())
        if not mds:
            continue
        번호붙은 = [f for f in mds if 번호.match(f.name)]
        점수 = 0
        if any(k in d.name for k in 이름표):
            점수 += 100
        if len(번호붙은) >= 3:
            점수 += 10 * len(번호붙은)
        if 점수 > best[0]:
            best = (점수, d, mds)
    return best[1], best[2]


# 인계 문서가 없어도 **강의 프로젝트인 증거** — 하나라도 있으면 인정한다.
#   ⚠ 인계 문서만 찾다가 `대본.md` 하나짜리 특강 프로젝트를 통째로 거부했다.
#     작은 프로젝트에도 덱·동기화 스킬은 써야 한다.
증거_파일 = ("대본.md", "덱구성서.md", "커리큘럼.md", "강의안.md")
증거_폴더 = ("가이드", "실습가이드", "강의덱", "덱", "강의", "설계", "실습코드", "실습자산")


def _강의프로젝트인가(d: Path) -> bool:
    if any((d / n).is_file() for n in 증거_파일):
        return True
    if any((d / n).is_dir() for n in 증거_폴더):
        return True
    # 루트에 `*대본*.md`·`*가이드*.md` 가 있으면 강의 자료다
    return any(d.glob("*대본*.md")) or any(d.glob("*가이드*.md"))


def _루트찾기(start: Path) -> tuple[Path | None, Path | None]:
    """위로 올라가며 인계 문서가 있는 폴더를 찾는다.

    못 찾으면 **인계 문서 없는 강의 프로젝트**인지 본다.
    있으면 루트만 돌려주고 인계문서는 비운다 — 「없다」고 정직하게 말한다.
    """
    cur = start.resolve()
    for _ in range(8):
        for name in 인계문서_후보:
            f = cur / name
            if f.exists():
                return cur, f
        # ★ 문서를 한 폴더에 모으는 구조가 있다 — `00_문서/0_인계.md`.
        #   루트만 보면 그런 프로젝트를 통째로 못 찾는다 【2026-09-08 실제로 당함】.
        for d in sorted(p for p in cur.iterdir() if p.is_dir() and not _건너뛸까(p.name)) \
                if cur.is_dir() else []:
            if _re.sub(r"^\d+[_\-. ]*", "", d.name) not in 문서폴더_후보:
                continue
            for f in sorted(d.glob("*.md")):
                if _re.sub(r"^\d+[_\-. ]*", "", f.name) in 인계문서_후보:
                    return cur, f
        if cur.parent == cur:
            break
        cur = cur.parent

    cur = start.resolve()
    for _ in range(3):                 # 인계 없는 프로젝트는 얕게만 본다
        if _강의프로젝트인가(cur):
            return cur, None
        if cur.parent == cur:
            break
        cur = cur.parent
    return None, None


def _워크스페이스찾기(root: Path) -> Path:
    """`.claude` 가 있는 상위 폴더. 없으면 프로젝트의 부모."""
    cur = root
    for _ in range(6):
        if (cur / ".claude").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return root.parent


def _첫폴더(root: Path, 후보: list[str]) -> Path | None:
    """★ 이름 앞에 정렬용 숫자가 붙어도 찾는다 — `00_문서` · `10_실습` · `20_도구`.

    폴더를 읽는 순서를 정하려고 숫자를 붙이는 프로젝트가 있다.
    이름을 통째로만 비교하면 **그 프로젝트를 통째로 못 찾는다** 【2026-09-08 실제로 당함】.

    ★ 한 단계 아래도 본다 — `10_실습/가이드` 처럼 묶어 놓는 구조가 있다.
    """
    for name in 후보:
        p = root / name
        if p.is_dir():
            return p
    # 숫자 접두어 — `00_문서` 형태
    for d in sorted(root.iterdir() if root.is_dir() else []):
        if not d.is_dir() or _건너뛸까(d.name):
            continue
        벗김 = _re.sub(r"^\d+[_\-. ]*", "", d.name)
        if 벗김 in 후보:
            return d
    # 한 단계 아래 — `10_실습/가이드`
    for 상위 in sorted(root.iterdir() if root.is_dir() else []):
        if not 상위.is_dir() or _건너뛸까(상위.name):
            continue
        for name in 후보:
            p = 상위 / name
            if p.is_dir():
                return p
    return None


def _훑을폴더(root: Path, 깊이: int = 4) -> list[Path]:
    """루트에서 `깊이` 단계까지 내려가며 폴더를 모은다. 건너뛸 폴더는 **들어가지도 않는다.**

    ★ 바로 아래 한 단계만 보면 `완성본/<프로젝트>/backend/.venv` 같은 것을 놓친다.
      실제로 그래서 「가상환경을 못 찾았다」가 떴다.
    """
    모음, 층 = [root], [root]
    for _ in range(깊이):
        다음: list[Path] = []
        for d in 층:
            try:
                다음 += [p for p in d.iterdir() if p.is_dir() and not _건너뛸까(p.name)]
            except OSError:
                pass
        if not 다음:
            break
        모음 += 다음
        층 = 다음
    return 모음


def _파이썬찾기(root: Path) -> tuple[Path | None, str]:
    """가상환경을 찾는다. Windows 는 Scripts/, 그 외는 bin/."""
    sub = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    후보: list[tuple[Path, str]] = []
    for d in _훑을폴더(root):
        for venv in sorted((p.name for p in d.iterdir()
                            if p.is_dir() and (p.name.startswith(".venv")
                                               or p.name in ("venv", "env"))),
                           reverse=True):   # 최신 이름 우선 (.venv314 > .venv312)
            p = d / venv / sub
            if p.exists():
                종류 = "uv" if (d / "uv.lock").exists() else "venv"
                후보.append((p, 종류))
    if 후보:
        # uv 프로젝트를 먼저, 그다음 경로가 짧은 것
        후보.sort(key=lambda x: (x[1] != "uv", len(str(x[0]))))
        return 후보[0]
    return None, "system"


def _가이드점수(f: Path) -> int:
    """이름이 얼마나 「학생용 가이드」다운가.

    ⚠ 개수만 보면 틀린다 — `검증리서치/원문/` 에 `*일차*.md` 가 3개 있어서
      실제 가이드 2개를 이겼다. **이름이 개수보다 세다.**
    """
    n = f.name
    if "실습가이드" in n or n.lower().startswith("guide"):
        return 10
    if n.startswith("Day") or n.startswith("day"):
        return 10
    if "가이드" in n:
        return 6
    if "일차" in n:
        return 3
    return 1


def _가이드찾기(root: Path) -> tuple[Path | None, list[Path]]:
    """가이드가 모인 폴더 — **점수 합이 가장 높은 곳.**"""
    best: tuple[int, Path | None, list[Path]] = (0, None, [])
    for d in [root] + [p for p in root.rglob("*") if p.is_dir()
                       and not any(_건너뛸까(x) for x in p.parts)]:
        found: list[Path] = []
        for pat in 가이드_패턴:
            found += [f for f in d.glob(pat) if f.is_file() and f.suffix == ".md"]
        # 폴더 이름이 「가이드」면 안의 .md 는 파일명과 무관하게 전부 가이드다
        폴더가가이드 = d.name in 가이드폴더_후보
        if 폴더가가이드:
            found += [f for f in d.glob("*.md") if f.is_file()]
        found = sorted(set(found))
        if not found:
            continue
        점수 = sum(10 if 폴더가가이드 else _가이드점수(f) for f in found)
        if 점수 > best[0]:
            best = (점수, d, found)
    return best[1], best[2]


def _그림찾기(guide_dir: Path, files: list[Path]) -> Path | None:
    """**가이드가 실제로 참조하는 경로**에서 찾는다.

    폴더 이름을 맞히려 들면 틀린다 — `figures/실습/` 처럼 한 단계 더 들어가 있을 수 있다.
    `![](…)` 안의 경로를 읽으면 정확하다.
    """
    import re
    from collections import Counter

    쓰인곳: Counter[str] = Counter()
    for f in files[:12]:
        try:
            for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", f.read_text(encoding="utf-8")):
                p = (guide_dir / m.group(1)).resolve()
                if p.parent.is_dir():
                    쓰인곳[str(p.parent)] += 1
        except Exception:
            pass
    if 쓰인곳:
        return Path(쓰인곳.most_common(1)[0][0])

    # 참조가 없으면 이름으로 — 하위까지 훑는다
    for cand in [guide_dir] + [p for p in guide_dir.rglob("*") if p.is_dir()]:
        if cand.name in 그림폴더_후보:
            return cand
    return None


def _도구찾기(ws: Path) -> dict[str, str]:
    """워크스페이스 전체에서 도구를 찾는다 — 프로젝트를 넘나들어 쓴다."""
    out: dict[str, str] = {}
    for key, names in 도구_후보.items():
        for f in ws.rglob("*.py"):
            if any(_건너뛸까(x) for x in f.parts):
                continue
            if f.name in names:
                out[key] = str(f)
                break
    return out


def 탐지(start: Path | None = None) -> 프로젝트:
    start = (start or Path.cwd()).resolve()
    p = 프로젝트()

    root, handoff = _루트찾기(start)
    if root is None:
        p.경고.append(
            "강의 프로젝트가 아니다 — 인계 문서(" + " · ".join(인계문서_후보[:3]) + " 등)도 "
            "강의 자료(대본·가이드·덱·설계 폴더)도 없다. 프로젝트 폴더 안에서 실행하라")
        return p

    p.루트, p.이름 = str(root), root.name
    p.인계문서 = str(handoff) if handoff else ""
    if not handoff:
        p.경고.append(
            "인계 문서가 없다 — 강의 자료로 프로젝트를 인정했다. "
            "이어받을 사람이 있으면 공용 `handoff` 스킬로 하나 세운다")
    ws = _워크스페이스찾기(root)
    p.워크스페이스 = str(ws)

    d = _첫폴더(root, 문서폴더_후보)
    p.문서폴더 = str(d) if d else ""
    if not d:
        p.경고.append("문서 폴더가 없다 — 문서/ · docs/ 중 하나를 찾는다")

    c = _첫폴더(root, 코드폴더_후보)
    p.코드폴더 = str(c) if c else ""
    if c:
        p.랩개수 = sum(1 for f in c.rglob("*.py")
                       if not any(_건너뛸까(x) for x in f.parts))

    g, files = _가이드찾기(root)
    if g:
        p.가이드폴더 = str(g)
        p.가이드파일 = [f.name for f in files]
        img = _그림찾기(g, files)
        p.그림폴더 = str(img) if img else ""

    # 인계가 **폴더로 쪼개진** 경우 — 파일 하나만 보면 정본을 통째로 놓친다
    hd, hfiles = _인계폴더찾기(root, g)
    if hd:
        p.인계폴더 = str(hd)
        p.인계폴더파일 = [f.name for f in hfiles]

    py, kind = _파이썬찾기(root)
    p.파이썬, p.파이썬종류 = (str(py) if py else sys.executable), kind
    if py is None:
        p.경고.append("가상환경을 못 찾았다 — 시스템 파이썬을 쓴다")

    p.도구 = _도구찾기(ws)
    return p


def 표로(p: 프로젝트) -> None:
    print("=" * W)
    print("  강의 프로젝트 탐지")
    print("=" * W)
    if not p.루트:
        print()
        for w in p.경고:
            print(f"  ❌ {w}")
        print("=" * W)
        return

    행 = [
        ("프로젝트", p.이름),
        ("루트", p.루트),
        ("워크스페이스", p.워크스페이스),
        ("인계 문서", Path(p.인계문서).name if p.인계문서 else "— 없음"),
        ("인계 묶음", f"{Path(p.인계폴더).name}/  ({len(p.인계폴더파일)}개)"
                      if p.인계폴더 else "— 없음"),
        ("문서 폴더", Path(p.문서폴더).name if p.문서폴더 else "— 없음"),
        ("코드 폴더", f"{Path(p.코드폴더).name}  ({p.랩개수}개 .py)" if p.코드폴더 else "— 없음"),
        ("가이드", f"{Path(p.가이드폴더).name}  ({len(p.가이드파일)}개)" if p.가이드폴더 else "— 없음"),
        ("그림", Path(p.그림폴더).name if p.그림폴더 else "— 없음"),
        ("파이썬", f"{p.파이썬종류}  {p.파이썬}"),
    ]
    print()
    for k, v in 행:
        print(f"  {k:<14}{v}")

    if p.도구:
        print()
        print("─" * W)
        print("  워크스페이스에서 찾은 도구")
        print("─" * W)
        for k, v in sorted(p.도구.items()):
            rel = v.replace(p.워크스페이스 + os.sep, "")
            print(f"    {k:<16}{rel}")

    if p.경고:
        print()
        for w in p.경고:
            print(f"  ⚠ {w}")

    print()
    print("=" * W)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    start = Path(args[0]) if args else None
    p = 탐지(start)
    if "--json" in sys.argv:
        print(json.dumps(asdict(p), ensure_ascii=False, indent=2))
    else:
        표로(p)
    sys.exit(0 if p.루트 else 1)


if __name__ == "__main__":
    main()
