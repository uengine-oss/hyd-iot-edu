# -*- coding: utf-8 -*-
"""문서와 실물이 어긋났는지 본다 — **어느 강의 프로젝트에서든.**

    python 문서검사.py                모든 검사
    python 문서검사.py --항목 참조     한 항목만
    python 문서검사.py --조용          어긋난 것만

무엇을 보나
    ① 참조 무결성   문서가 부르는 **파일·그림·경로**가 실제로 있나
    ② 이름 무결성   문서가 부르는 **코드 이름**(빈칸·함수·상수)이 실물에 있나
    ③ 개수 일치     같은 대상의 **개수**가 문서마다 같은가
    ④ 레거시        **끝난 것·취소선**이 남아 있나
    ⑤ 프로젝트 규칙 `문서검사.규칙.json` 이 있으면 그것도

프로젝트별 값은 `문서검사.규칙.json` 에 둔다 (문서 폴더 또는 프로젝트 루트)
    {"랩아닌파일": ["회귀.py", "lab_common.py"],   랩 개수에서 뺄 도구·배관 파일 이름
     "남의것":     ["원본저장소이름"],             이 말이 든 줄은 남의 코드 이야기로 본다
     "남의문서":   ["원본저장소이름"],             파일 이름에 이 말이 들면 남의 문서로 본다
     "금지":       [{"패턴": "손상 21", "까닭": "7종 기준은 24다"}]}
    파일이 없거나 키가 없으면 빈 목록이다. 특정 강의의 이름을 이 도구에 박지 않는다.

왜 필요한가
    한 곳을 고치면 다른 곳이 어긋난다. 그런데 **아무도 모른다.**

    실제로 있었던 일 —
      · 검색 수치가 **BM25 78 ↔ 다국어 89 로 뒤바뀐 채** 문서 다섯 곳에 있었다
      · 문서가 부르는 `SPLIT_RULE` 이 **실물 랩에 없었다.** 판단 자리가 하루씩 밀려 있었다
      · 같은 파일 안에 마스터 개수가 **15 · 12 · 5** 세 가지로 적혀 있었다

    **숫자는 문서를 믿지 말고 실물에서 다시 센다.** 이 도구가 그걸 한다.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lecture-common"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from 프로젝트탐지 import 탐지  # noqa: E402

W = 78


@dataclass
class 어긋남:
    항목: str
    파일: str
    줄: int
    내용: str
    까닭: str
    심각: str = "틀림"      # 틀림 | 대기   — 「대기」는 아직 안 만든 것이라 잘못이 아니다


# ── 이력 행은 건드리지 않는다 ────────────────────────────────────────
#   `| 2026-08-27 | …` 처럼 날짜가 붙었거나 「당시」가 있으면 **그때는 맞았다.**
#   이력을 현재값으로 바꾸면 그게 기록 왜곡이다.
# 날짜는 `2026-08-28` 도 `08-27` 도 이력 표시다. **둘 다 잡는다**
이력 = re.compile(r"(20\d\d[-.])?\d\d[-.]\d\d\s*(에|엔|,|\)|아침|저녁|오전|오후)")
이력어 = ("당시", "그때는", "겪은 것", "그날", "이력", "기록이다", "옛", "예전",
          "때는", "때의", "시절", "일 때", "이었다", "였다", "아침에는",
          # 「부르는데 없었다」는 **값이 아니라 사고 기록**이다.
          # ⚠ **높임말도 같이 넣는다** — 검토자에게 나가는 문서는 「없었습니다」로 쓴다
          "없었다", "없었습니다", "없다고", "틀렸", "틀렸습니다",
          "잘못", "사건", "놓쳤", "달랐다", "달랐습니다", "밀려")


# `| 랩 40파일 | **52파일** |` 처럼 **왼쪽이 옛 값, 오른쪽이 지금 값**인 표가 있다.
#   ⚠ 왼쪽만 보고 「40은 틀렸다」고 하면 **대조표 자체를 없애라는 말**이 된다.
_대조표 = re.compile(r"^\s*\|[^|]+\|.*\*\*[^*]+\*\*")


def _대조표인가(line: str) -> bool:
    """왼쪽 칸이 옛 값이고 **오른쪽 칸이 강조된 지금 값**인 줄."""
    return bool(_대조표.match(line)) and line.count("|") >= 3


def _인용인가(line: str) -> bool:
    """「…」 이나 *"…"* 안의 값은 **남의 말을 옮긴 것**이다."""
    return "「" in line or '*"' in line or "「" in line


def _이력인가(line: str) -> bool:
    """**날짜가 줄 어디에 있어도** 이력이다.

    ⚠ 표 맨 앞만 보다가 `**겪은 것 (2026-08-28)** — 랩 24개…` 를 놓쳤다.
      그때는 24개가 맞았다. **이력을 현재값으로 고치면 그게 기록 왜곡이다.**
    """
    return (bool(이력.search(line))
            or any(k in line for k in 이력어)
            or _대조표인가(line)
            or _인용인가(line))


# ── 코드 심볼이 아닌 것 ──────────────────────────────────────────────
#   `U002`·`L260812` 처럼 **글자 한둘 + 숫자**는 데이터 식별자다.
#   인물 ID·LOT 번호를 코드에서 찾으면 당연히 없다.
식별자 = re.compile(r"[A-Z]{1,3}\d{3,}")

#   같은 줄이 **남의 것**을 말하면 우리 코드에 없는 게 맞다.
#   예) 참고 원본의 `RAGAS_JUDGE_MODEL` · LangChain 의 `APPROVED`
#   특정 원본 저장소의 이름은 프로젝트 규칙의 "남의것" 에 더한다.
남의것 = ("원본", "LangChain", "langchain", "공식 문서", "원문",
          "라이브러리", "프레임워크", "표준", "외부", "그들은",
          "RAGAS", "Ragas", "환경변수", "슬라이드", "도장", "명패")

흔한말 = {"README", "HANDOFF", "TODO", "NOTE", "WARNING", "OK", "PASS", "FAIL",
          # 2026-09-03 추가 — **설정으로 넣는 값**이지 우리 코드의 이름이 아니다.
          #   가이드가 「이 모델은 LOW·MEDIUM·HIGH 만 받습니다」라고 쓴 것을 잡았다.
          "LOW", "MEDIUM", "HIGH", "NONE", "TRUE", "FALSE", "AUTO", "DEBUG",
          "INFO", "ERROR", "GET", "POST", "PUT", "DELETE", "JSON", "CSV", "PDF",
          # Dockerfile · SQL · 셸 명령어 — 우리 코드의 이름이 아니다
          "COPY", "FROM", "RUN", "CMD", "WORKDIR", "EXPOSE", "ENV", "ENTRYPOINT",
          "SELECT", "INSERT", "UPDATE", "CREATE", "GRANT", "COMMIT"}

# 환경변수 이름 — `_URL`·`_KEY`·`_TOKEN` 으로 끝나면 설정값이지 코드 심볼이 아니다
_환경변수꼴 = re.compile(r"^[A-Z][A-Z0-9_]*_(URL|KEY|TOKEN|SECRET|PATH|HOST|PORT|DSN|ID)$")

#   **파일 이름**이 남의 것을 다룬다고 말하면, 그 안의 코드 이름은 남의 것이다.
#   ⚠ `04_원본조사.md` 의 `retrieval/utils.py:267-284` 를 우리 코드에서 찾으면 당연히 없다.
#   특정 원본 저장소의 이름은 프로젝트 규칙의 "남의문서" 에 더한다.
남의문서 = ("조사", "원본", "리서치", "검토의견", "설계안",
            # 2026-09-03 추가 — 「어디서 가져왔나」를 적는 문서는 **남의 파일 목록**이다.
            #   `이식명세.md` 가 원본 24개를 대조표로 적었는데 25건이 전부 오탐으로 나왔다.
            "이식명세", "이식", "대조표", "출처")


def _남의문서인가(f, p) -> bool:
    """파일 이름으로 못 가르면 **문서가 스스로 뭐라고 하는지** 본다.

    이름이 중립적인데 안에서 남의 코드를 대조하는 문서가 있다.
    첫머리에 「원본을 이식」·「원자료」라고 밝혀 두므로 그것으로 가른다.
    """
    if any(k in f.name for k in 남의문서 + tuple(_설정(p)["남의문서"])):
        return True
    try:
        머리 = f.read_text(encoding="utf-8", errors="replace")[:600]
    except Exception:
        return False
    return any(k in 머리 for k in ("원본을 이식", "원자료", "대조 대상", "원본 대조"))



_캐시: dict[str, object] = {}


# ── 프로젝트 규칙 파일 ────────────────────────────────────────────────
#   특정 강의의 도구 이름·원본 저장소 이름을 여기에 박으면 다른 강의에서 틀린다.
#   그래서 프로젝트가 `문서검사.규칙.json` 으로 선언한다. 없으면 빈 목록이다.
_목록키 = ("랩아닌파일", "남의것", "남의문서")


def _규칙파일(p) -> Path | None:
    for c in (Path(p.문서폴더 or p.루트) / "문서검사.규칙.json",
              Path(p.루트) / "문서검사.규칙.json"):
        if c.exists():
            return c
    return None


def _설정(p) -> dict:
    """규칙 파일을 한 번만 읽는다. 목록 키가 없으면 빈 목록으로 채운다."""
    if "설정" not in _캐시:
        f = _규칙파일(p)
        cfg = json.loads(f.read_text(encoding="utf-8")) if f else {}
        if not isinstance(cfg, dict):
            raise ValueError(f"{f}: 규칙 파일은 JSON 객체여야 한다")
        for k in _목록키:
            v = cfg.get(k, [])
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise ValueError(f"{f}: \"{k}\" 는 문자열 목록이어야 한다")
            cfg[k] = list(v)
        _캐시["설정"] = cfg
    return _캐시["설정"]          # type: ignore[return-value]


# 랩이 아닌 것 — **학생이 빈칸을 채우는 파일만 「랩」이다.**
#   운영 도구는 우리가 쓰고, 공용 배관은 여러 랩이 import 한다.
#   ⚠ 섞어 세면 문서마다 숫자가 달라진다. 실제로 52·55·56 세 값이 돌아다녔다.
#   어떤 파일이 도구·배관인지는 강의마다 다르므로 규칙 파일의 "랩아닌파일" 이 정한다.
def _도구인가(f: Path, p) -> bool:
    return f.name in _설정(p)["랩아닌파일"]


def _남의것인가(f: Path) -> bool:
    """`_` 로 시작하는 폴더는 **원본·보관**이다. 우리가 만든 것이 아니다.

    ⚠ 이걸 안 걸러서 랩이 **143개**로 세어졌다. 실제 우리 랩은 52개다.
    """
    return any(part.startswith("_") or part.startswith(".venv")
               or part in ("__pycache__", "venv", "env", "node_modules",
                           # ⚠ **생성물은 우리 랩이 아니다.** `참고답안/` 은
                           #   원본 랩에 정답을 끼워 만든 사본이라 세면 **두 번 센다.**
                           #   실제로 랩이 46 → 66 으로 부풀었다(2026-09-02).
                           "참고답안", "정답", "answers")
               for part in f.parts)


def _py파일들(p) -> set[str]:
    """**워크스페이스 전체**의 `.py` 이름 — 도구는 프로젝트를 넘나든다.

    ⚠ `터미널그림.py` 는 다른 프로젝트에 있다. 프로젝트 안만 보면 「없다」가 된다.
    """
    if "py이름" not in _캐시:
        names: set[str] = set()
        for f in Path(p.워크스페이스).rglob("*.py"):
            if any(x == "__pycache__" or x.startswith(".venv") for x in f.parts):
                continue
            names.add(f.name)
        names |= _학생이만들것(p)
        _캐시["py이름"] = names
    return _캐시["py이름"]          # type: ignore[return-value]


def _학생이만들것(p) -> set[str]:
    """**학생이 만들 파일은 저장소에 없는 것이 맞다.**

    문서가 `chunker.py` 를 부르는데 저장소에 없다고 「어긋남」이라 하면
    **정상인 것을 고치라고 시키는 셈**이다.

    ⚠ **목록을 여기 적지 않는다**(규약 10). `도구/계약.py` 의 `만들것` 에서 읽는다.
      계약이 바뀌면 검사기가 저절로 따라간다.
    """
    이름들: set[str] = set()
    for 계약 in Path(p.워크스페이스).rglob("계약.py"):
        if any(x == "__pycache__" or x.startswith(".venv") for x in 계약.parts):
            continue
        본문 = 계약.read_text(encoding="utf-8", errors="replace")
        블록 = re.search(r"만들것\s*=\s*\[(.*?)\n\]", 본문, re.S)
        if not 블록:
            continue
        이름들 |= {Path(m).name for m in re.findall(r'"([^"]+\.py)"', 블록.group(1))}
    return 이름들


def _만들어지는파일(p) -> set[str]:
    """**도구가 그때 만들어 넣는 파일**은 저장소에 없는 것이 맞다.

    ⚠ `스냅샷묶기.py` 가 zip 안에 `받은뒤_읽어보기.md` 를 `writestr` 로 넣는다.
      저장소에서 찾으면 당연히 없고, 잡으면 오탐이다.
    """
    if "생성파일" in _캐시:
        return _캐시["생성파일"]          # type: ignore[return-value]
    이름: set[str] = set()
    for 뿌리 in {x for x in (p.코드폴더, p.루트) if x}:
        for f in Path(뿌리).rglob("*.py"):
            if _남의것인가(f):
                continue
            try:
                글 = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in re.finditer(r"""(?:writestr|write_text|open)\s*\(\s*["'][^"']*?([\w가-힣_.-]+\.(?:md|txt|json|bat|sh))""", 글):
                이름.add(Path(m.group(1)).name)
    _캐시["생성파일"] = 이름
    return 이름


def _md파일들(p) -> set[str]:
    """**워크스페이스 전체**의 `.md` 이름.

    ⚠ `_` 로 시작하는 것도 **센다.** 보관본이라도 존재하면 존재하는 것이다.
      문서가 `_검토안_최종_20260831.md` 를 부르는데 「없다」고 하면 오탐이다.
    """
    if "md이름" not in _캐시:
        names: set[str] = set()
        for f in Path(p.워크스페이스).rglob("*.md"):
            if any(x == "__pycache__" or x.startswith(".venv")
                   or x == "node_modules" for x in f.parts):
                continue
            names.add(f.name)
        _캐시["md이름"] = names
    return _캐시["md이름"]          # type: ignore[return-value]


# 문서가 **스스로 「아직 없다」고 말하는** 줄 — 잘못이 아니라 **대기**다
아직없음 = ("신설", "만든다", "만들 것", "아직", "예정", "필요하다", "없다",
            "미결", "새로 쓴다", "작성해야")

# 같은 줄이 **지웠다고 말하면** 없는 게 맞다 — 그 기록이 그 줄의 본체다
지웠음 = ("삭제", "지웠", "지운", "폐기", "없앴", "제거", "deleted/", "버렸",
          "빼냈", "옮겼", "이관", "불필요", "안 만들", "만들지 않")

# 명령 사용법의 **자리표시자**는 파일명이 아니다 — `md2pdf.py 입력.md 출력.pdf`
자리표시자 = {"입력.md", "출력.md", "파일.md", "이름.md", "문서.md",
              "input.md", "output.md", "file.md", "example.md", "foo.md"}


def _코드전문(p) -> str:
    """우리 소스를 이어붙인 것 — **한 번만 읽는다.**

    ⚠ 코드 폴더만 보면 안 된다. **코드가 거기만 있지 않다.**
      리허설은 `제작/덱빌드/build_3일차.py` 에 `W.NOHAND` 를 두고 있었는데
      코드 폴더 밖이라 못 읽었고, 문서가 부르는 이름을 「없다」고 잡았다.
      **루트 전체에서 읽되 남의 것·가상환경만 뺀다.**
    """
    if "코드" not in _캐시:
        뿌리 = Path(p.루트) if p.루트 else None
        if 뿌리 is None:
            _캐시["코드"] = ""
        else:
            buf = []
            for f in 뿌리.rglob("*.py"):
                if _남의것인가(f):
                    continue
                try:
                    buf.append(f.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    continue
            _캐시["코드"] = "\n".join(buf)
    return _캐시["코드"]            # type: ignore[return-value]


def _찍을것인가(p, 이름: str) -> bool:
    """체크리스트에 「사람이 찍을 것」으로 올라 있나 — 그러면 잘못이 아니라 **대기**다."""
    if "체크리스트" not in _캐시:
        buf = ""
        for base in (p.가이드폴더, p.루트, p.문서폴더):
            if not base:
                continue
            for f in Path(base).glob("*체크리스트*.md"):
                buf += f.read_text(encoding="utf-8", errors="replace")
        _캐시["체크리스트"] = buf
    return 이름 in _캐시["체크리스트"]      # type: ignore[operator]


def _문서들(p) -> list[Path]:
    """검사할 문서 — **루트의 안내 md 를 빠뜨리지 않는다.**

    ⚠ 인계문서 하나만 보다가 `READ_FIRST.md` 를 놓쳤다.
      그 파일이 **삭제된 도구를 아직 부르고 있었다.**
      검토자가 **가장 먼저 여는 문서**라 여기가 틀리면 첫인상이 틀린다.
    """
    out: list[Path] = []
    if p.인계문서:
        out.append(Path(p.인계문서))
    # 루트의 다른 안내 문서 — `_` 로 시작하는 것은 보관본이라 뺀다
    for f in sorted(Path(p.루트).glob("*.md")):
        if f.name.startswith("_") or f in out:
            continue
        out.append(f)
    if p.문서폴더:
        out += sorted(Path(p.문서폴더).glob("*.md"))
    if p.코드폴더:
        r = Path(p.코드폴더) / "README.md"
        if r.exists():
            out.append(r)
    if p.가이드폴더:
        out += sorted(Path(p.가이드폴더).glob("*.md"))
    return out


# ══ ① 참조 무결성 ═══════════════════════════════════════════════════
def 검사_참조(p, docs: list[Path]) -> list[어긋남]:
    """문서가 부르는 **파일·그림**이 실제로 있나."""
    bad: list[어긋남] = []
    py이름 = _py파일들(p)
    md이름 = _md파일들(p)

    for f in docs:
        if _남의문서인가(f, p):
            continue          # 남의 것을 다루는 문서다
        base = f.parent
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            # 그림 — ![](경로)
            for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", line):
                t = m.group(1).split("#")[0].strip()
                if t.startswith(("http://", "https://", "data:")):
                    continue
                if not (base / t).exists():
                    # 체크리스트에 「사람이 찍을 것」으로 올라 있으면 **대기**다
                    대기 = _찍을것인가(p, Path(t).name)
                    bad.append(어긋남(
                        "참조", f.name, i, t,
                        "아직 안 찍었다 — 체크리스트에 있다" if 대기 else "그림 파일이 없다",
                        "대기" if 대기 else "틀림"))

            # 같은 줄이 **남의 코드**를 말하면 우리 워크스페이스에 없는 게 맞다.
            #   예) 참고 원본의 `retrieval/utils.py:267-284`
            if any(k in line for k in 남의것 + tuple(_설정(p)["남의것"])):
                continue
            # 같은 줄이 **지웠다·안 만들었다**고 말하면 없는 게 맞다 — 그 기록이 그 줄의 본체다.
            #   ⚠ 이 걸림돌이 `.md` 앞에만 있어서 **`.py` 만 자기 기록을 결함으로 잡았다.**
            #     「`app/middleware_skills.py` 는 만들지 않았다」를 적었더니 그 줄을 잡았다.
            # 같은 줄이 **지웠다·안 만들었다**고 말하면 없는 게 맞다 — 그 기록이 그 줄의 본체다.
            #   ⚠ 이 걸림돌이 `.md` 앞에만 있어서 **`.py` 만 자기 기록을 결함으로 잡았다.**
            #     「`app/middleware_skills.py` 는 만들지 않았다」를 적었더니 그 줄을 잡았다.
            if any(k in line for k in 지웠음):
                continue
            # 코드 파일 — `이름.py` 꼴. **와일드카드는 패턴이지 파일명이 아니다**
            #   ⚠ 백틱 안에 설명이 같이 들어 있으면 `…\.py)`$ 로는 안 걸린다.
            #     `` `도구/일치검사.py — 숫자를 다시 센다` `` 를 놓쳤다.
            #     **백틱 안 어디에 있든** `.py` 를 집는다.
            for m in re.finditer(r"`[^`]*?([\w./\가-힣-]+\.py)[^`]*`", line):
                raw = m.group(1)
                if "*" in raw or "?" in raw:
                    continue
                name = Path(raw).name
                if name not in py이름:
                    bad.append(어긋남("참조", f.name, i, raw,
                                      "이 이름의 .py 가 워크스페이스에 없다"))

            # 문서 파일 — `이름.md` 꼴.
            #   ⚠ 문서가 **부르는 문서**가 사라진 것을 아무도 못 본다.
            #     실제로 인계 문서가 `완주해보기.md` 를 **다섯 곳**에서 부르는데
            #     그 파일이 없었고, `.py` 만 보던 검사기는 통과시켰다.
            for m in re.finditer(r"`[^`]*?([\w./\\가-힣-]+\.md)[^`]*`", line):
                raw = m.group(1).replace("\\", "/")
                if "*" in raw or "?" in raw:
                    continue
                # `...` 로 줄여 적은 이름은 **실제 파일명이 아니다.**
                #   가이드가 `IR-BRK_..._2026-07_표붕괴.md` 처럼 길어서 줄여 쓴다.
                if "..." in raw or "…" in raw:
                    continue
                name = Path(raw).name
                if name in md이름 or name in 자리표시자:
                    continue
                if name in _만들어지는파일(p):
                    continue        # 도구가 그때 만들어 넣는다
                # 같은 백틱 안에 명령이 같이 있으면 **사용법 예시**다
                if ".py " in m.group(0) or ".exe " in m.group(0):
                    continue
                # 문서가 스스로 「아직 없다·만들 것」이라고 말하면 **대기**다
                대기 = any(k in line for k in 아직없음)
                bad.append(어긋남(
                    "참조", f.name, i, raw,
                    "아직 안 만들었다 — 문서가 그렇게 말한다" if 대기
                    else "이 이름의 .md 가 워크스페이스에 없다",
                    "대기" if 대기 else "틀림"))
    return bad


# ══ ② 이름 무결성 ═══════════════════════════════════════════════════
def 검사_이름(p, docs: list[Path]) -> list[어긋남]:
    """문서가 부르는 **코드 이름**이 실물에 있나.

    ⚠ 이게 `SPLIT_RULE` 사건을 잡는다 — 문서에 다섯 곳,
      **실물 랩에는 없었다.**
    """
    if not p.코드폴더:
        return []
    src = _코드전문(p)

    bad: list[어긋남] = []
    for f in docs:
        if _남의문서인가(f, p):
            continue          # 남의 것을 다루는 문서다
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _이력인가(line):
                continue
            # 같은 줄이 **남의 것**을 말하면 우리 코드에 없는 게 맞다
            if any(k in line for k in 남의것 + tuple(_설정(p)["남의것"])):
                continue
            # 「그림 — …」 은 슬라이드 묘사다. 그 안의 대문자는 도장 글자지 코드가 아니다
            if line.lstrip().startswith(("그림 —", "그림—", "그림:", "왼쪽", "오른쪽")):
                continue
            # 백틱 안의 대문자 상수 · 함수 호출 꼴
            for m in re.finditer(r"`([A-Z][A-Z0-9_]{3,})`|`([a-z_]{4,}\(\))`", line):
                name = (m.group(1) or m.group(2) or "").replace("()", "")
                if not name or name in 흔한말 or _환경변수꼴.match(name):
                    continue
                if name.startswith("_"):
                    continue                      # 내부 헬퍼 인용
                if 식별자.fullmatch(name):
                    continue                      # 데이터 ID 지 코드 심볼이 아니다
                if name not in src:
                    bad.append(어긋남("이름", f.name, i, name,
                                      "문서가 부르는데 코드에 없다"))
    return bad


# ══ ③ 개수 일치 ═════════════════════════════════════════════════════
def 검사_개수(p, docs: list[Path]) -> list[어긋남]:
    """같은 대상의 **개수**가 문서마다 같은가 — 실물에서 다시 세서 대조."""
    bad: list[어긋남] = []
    실물: dict[str, int] = {}

    if p.코드폴더:
        실물["랩"] = sum(1 for f in Path(p.코드폴더).rglob("*.py")
                         if not _남의것인가(f) and not _도구인가(f, p))
        blanks = _코드전문(p).count("═══ 빈칸")
        if blanks:
            실물["빈칸"] = blanks
    if p.가이드폴더:
        실물["가이드"] = len(list(Path(p.가이드폴더).glob("*.md")))
    if p.그림폴더:
        실물["그림"] = len(list(Path(p.그림폴더).glob("*.png")))

    # 「랩 52파일」 「판단 자리 20」 「그림 33장」 꼴
    패턴 = {
        "랩": re.compile(r"랩\s*(\d+)\s*파일|랩\s*(\d+)\s*개"),
        "빈칸": re.compile(r"판단\s*자리\s*(\d+)|빈칸\s*(\d+)\s*개"),
        # ⚠ 「부르는 37장」과 「있는 33장」은 다른 수다. **「있는」만 본다**
        "그림": re.compile(r"(?<!부르는 )그림\s*(\d+)\s*장(?!.*부르)"),
    }
    # 전체를 말하는 곳만 본다 — 「R-4 랩 5개」 같은 묶음은 전체가 아니다
    최소 = {"랩": 20, "빈칸": 10, "그림": 10}

    for f in docs:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _이력인가(line):
                continue
            for key, pat in 패턴.items():
                if key not in 실물:
                    continue
                for m in pat.finditer(line):
                    v = int(next(g for g in m.groups() if g))
                    if v < 최소.get(key, 0):
                        continue
                    if v != 실물[key]:
                        bad.append(어긋남("개수", f.name, i, f"{key} {v}",
                                          f"실물은 {실물[key]}"))
    return bad, 실물


# ══ ④ 레거시 ═══════════════════════════════════════════════════════
def 검사_레거시(p, docs: list[Path]) -> list[어긋남]:
    """끝난 것이 남아 있나.

    **취소선은 「폐기된 판단」 절에서만 허용한다** — 거긴 되살리기 방지가 목적이다.
    그 밖의 취소선·「완료」·「닫힘」은 지워야 할 레거시다.
    """
    bad: list[어긋남] = []
    허용절 = ("폐기된 판단", "폐기 판단", "되살리지 마라", "폐기된 것")

    for f in docs:
        절 = ""
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("#"):
                절 = line
            if "~~" not in line:
                continue
            if any(k in 절 for k in 허용절):
                continue
            # 정정 기록은 둔다 —
            #   문장 안 대조 `~~A~~ → B`
            #   표 행  `| ~~옛 판정~~ | 실제 사실 |`  ← 뒤 칸에 근거가 온다
            if "→" in line or "->" in line or "도 맞지만" in line:
                continue
            if line.strip().startswith("|") and line.count("|") >= 3:
                뒤 = line.split("~~")[-1]
                if "|" in 뒤 and 뒤.split("|", 1)[1].strip():
                    continue
            bad.append(어긋남("레거시", f.name, i, line.strip()[:60],
                              "취소선 — 「폐기된 판단」 절 밖이면 지운다"))
    return bad


# ══ ⑤ 프로젝트 규칙 ═════════════════════════════════════════════════
def 검사_규칙(p, docs: list[Path]) -> list[어긋남]:
    """`문서검사.규칙.json` 의 "금지" 규칙도 본다.

    형식
        {"금지": [{"패턴": "손상 21", "까닭": "7종 기준은 24다"}]}
    """
    cfg = _설정(p)

    bad: list[어긋남] = []
    for rule in cfg.get("금지", []):
        pat = re.compile(rule["패턴"])
        for f in docs:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if _이력인가(line):
                    continue
                # 규칙 **자체를 설명하는 줄**은 값이 아니다 (검사기가 자기를 잡는 것과 같다)
                if any(w in line for w in ("규칙", "금지", "막는", "되살아", "패턴")):
                    continue
                if pat.search(line):
                    bad.append(어긋남("규칙", f.name, i, rule["패턴"],
                                      rule.get("까닭", "규칙 위반")))
    return bad


# ══ 실행 ═══════════════════════════════════════════════════════════
# ══ ⑥ 코드 블록 ═══════════════════════════════════════════════════
_울타리 = re.compile(r"^```(\w*)\s*$")
_조각표시 = ("...", "…", "← ", "# ←")
_파이썬냄새 = ("def ", "import ", "return ", "print(", ".join(", "chat(")

# 파이썬처럼 보이지만 **복붙할 코드가 아닌 것.** 잡으면 전부 오탐이다.
#   실제로 8건이 오탐으로 나왔다 — 함수 서명 계약표(`def f(...) -> list[dict]` 콜론 없음),
#   에러 메시지(`ImportError: cannot import name 'FastMCP'`),
#   버전 표(`langgraph==1.0.10 → ...`), 표 행이 통째로 들어온 것.
def _복붙할코드인가(코드: str) -> bool:
    줄 = [x for x in 코드.splitlines() if x.strip()]
    if not 줄:
        return False
    첫 = 줄[0].strip()

    # 에러·트레이스백을 붙여 놓은 블록 — 보여주는 것이지 치는 것이 아니다
    에러꼴 = ("Error:", "Exception", "Traceback", "Warning:", "error:")
    if any(k in 첫 for k in 에러꼴):
        return False

    # 표가 통째로 들어온 것 — 울타리 없이 탭·여러 칸으로 벌린 표도 포함
    if 첫.startswith("|") or "→" in 코드:
        return False
    if all(re.search(r"\S {3,}\S", x) for x in 줄):
        return False        # 모든 줄이 공백 세 칸 이상으로 벌어져 있다 = 표다

    # 함수 **서명만** 적은 계약 표기 — `def ...` 인데 콜론으로 안 끝난다
    if 첫.startswith("def ") and not 첫.rstrip().endswith(":"):
        return False

    # 버전 고정 표기(`pkg==1.2.3`)만 있는 블록
    if all(("==" in x or not x.strip()) for x in 줄):
        return False

    return True


def 검사_코드블록(p, docs: list[Path]) -> list[어긋남]:
    """가이드의 파이썬 블록이 **문법적으로 성립하나.**

    **학생은 이 블록을 복사해 붙인다.** 죽으면 그 자리에서 수업이 멈춘다.
    ⚠ 실제로 있었던 일 — `Day04` 의 블록에 `\\n` 이 **실제 개행으로** 들어가
      문자열이 안 닫혔다. 복붙하면 `SyntaxError` 로 죽는다.
      **낱말 검사·개수 검사로는 안 걸린다.** 09-01 완주에서 잡혔다.
    """
    import ast

    bad: list[어긋남] = []
    # ⚠ `p.가이드파일` 은 **경로가 아니라 이름 문자열**이다.
    #   그걸 `Path()` 로 열면 전부 실패하고 **한 건도 검사 안 된다.**
    #   09-01 에 그렇게 만들어 놓고 「✅ 없음」을 보고 통과한 줄 알았다.
    #   **`docs` 는 Path 목록이고 가이드도 그 안에 들어 있다.** 이것만 본다.
    for f in docs:
        f = Path(f)
        if not f.is_file():
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        안, 말, 시작, buf = False, "", 0, []
        for i, line in enumerate(lines, 1):
            m = _울타리.match(line)
            if m and not 안:
                안, 말, 시작, buf = True, m.group(1), i, []
                continue
            if 안 and line.strip() == "```":
                안 = False
                코드 = "\n".join(buf)
                if not 코드.strip():
                    continue
                파이썬 = (말 == "python") or (
                    not 말 and any(h in 코드 for h in _파이썬냄새))
                if not 파이썬 or any(t in 코드 for t in _조각표시):
                    continue
                if not _복붙할코드인가(코드):
                    continue
                try:
                    ast.parse(코드)
                except SyntaxError as e:
                    try:   # 들여쓰기만 어긋난 조각은 감싸서 다시 본다
                        ast.parse("if True:\n" + "\n".join(
                            "    " + x for x in 코드.splitlines()))
                        continue
                    except SyntaxError:
                        pass
                    bad.append(어긋남(
                        "코드블록", Path(f).name, 시작,
                        (코드.splitlines() or [""])[0][:60],
                        f"복붙하면 죽는다 — {e.msg} (블록 {e.lineno}번째 줄)"))
                continue
            if 안:
                buf.append(line)
    return bad


def main() -> None:
    조용 = "--조용" in sys.argv
    골라 = None
    if "--항목" in sys.argv:
        골라 = sys.argv[sys.argv.index("--항목") + 1]

    p = 탐지()
    if not p.루트:
        print("❌ 강의 프로젝트를 못 찾았다. 프로젝트 폴더 안에서 실행하라.")
        sys.exit(1)

    docs = _문서들(p)
    print("=" * W)
    print(f"  문서 검사 — {p.이름}")
    print("=" * W)
    print(f"\n  문서 {len(docs)}개 · 랩 {p.랩개수}개 · 가이드 {len(p.가이드파일)}개\n")

    모두: list[어긋남] = []
    개수결과, 실물 = 검사_개수(p, docs)

    항목들 = [
        ("참조", "문서가 부르는 파일·그림이 있나", lambda: 검사_참조(p, docs)),
        ("이름", "문서가 부르는 코드 이름이 있나", lambda: 검사_이름(p, docs)),
        ("개수", "같은 대상의 개수가 문서마다 같나", lambda: 개수결과),
        ("레거시", "끝난 것이 남아 있나", lambda: 검사_레거시(p, docs)),
        ("코드블록", "학생이 복붙할 코드가 문법에 맞나", lambda: 검사_코드블록(p, docs)),
        ("규칙", "프로젝트 규칙", lambda: 검사_규칙(p, docs)),
    ]

    for key, 설명, fn in 항목들:
        if 골라 and 골라 != key:
            continue
        found = fn()
        모두 += found
        if 조용 and not found:
            continue
        print("─" * W)
        extra = ""
        if key == "개수" and 실물:
            extra = "   실물: " + " · ".join(f"{k} {v}" for k, v in 실물.items())
        print(f"  {key} — {설명}{extra}")
        print("─" * W)
        if not found:
            print("    ✅ 없음")
        for b in found[:25]:
            mark = "⚠" if b.심각 == "대기" else "❌"
            print(f"    {mark} {b.파일}:{b.줄}  {b.내용}")
            print(f"       {b.까닭}")
        if len(found) > 25:
            print(f"    … 그 밖에 {len(found)-25}건")
        print()

    틀림 = [b for b in 모두 if b.심각 != "대기"]
    대기 = [b for b in 모두 if b.심각 == "대기"]

    print("=" * W)
    if 대기 and not 틀림:
        print(f"  ✅ 어긋남 없음  ·  ⚠ 대기 {len(대기)}건 (아직 안 만든 것)")
        print("=" * W)
        sys.exit(0)
    if 틀림:
        print(f"  ❌ 어긋남 {len(틀림)}건" + (f"  ·  ⚠ 대기 {len(대기)}건" if 대기 else ""))
        묶음: dict[str, int] = {}
        for b in 틀림:
            묶음[b.항목] = 묶음.get(b.항목, 0) + 1
        for k, v in 묶음.items():
            print(f"     · {k} {v}건")
        print()
        print("  ⚠ **낡은 값은 지운다. 취소선으로 남기지 않는다.**")
        print("     예외는 「폐기된 판단」 절 하나뿐 — 거긴 되살리기 방지가 목적이다.")
    else:
        print("  ✅ 어긋남 없음 — 문서와 실물이 일치한다")
    print("=" * W)
    sys.exit(1 if 틀림 else 0)


if __name__ == "__main__":
    main()
