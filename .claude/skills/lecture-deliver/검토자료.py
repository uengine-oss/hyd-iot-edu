# -*- coding: utf-8 -*-
"""검토용 zip 을 만든다 — **개인 정보는 가리고, 중복은 빼고, 위험하면 안 만든다.**

    python 검토자료.py                     만든다
    python 검토자료.py --미리보기           무엇이 들어가는지만 본다
    python 검토자료.py --이름 검토자료_0829  파일 이름 지정

세 가지를 한다
    ① **가린다**   이메일 · 프로젝트 ID · 결제계정 번호 · API 키
                  지우지 않고 **자리는 남긴다** — 형식이 보여야 무엇인지 안다
    ② **뺀다**     남의 원본 · 이미 보낸 것 · 그림으로 들어간 원본 텍스트
    ③ **막는다**   나가면 안 되는 것이 남아 있으면 **zip 을 안 만든다**

실제 ZIP 생성에는 --목록 <상대경로 JSON 배열>이 필요하다. 자동 탐지는 미리보기 전용이다.
검사·예시라는 단어로 검출을 우회하지 않는다. 기존 ZIP은 덮어쓰지 않는다.
"""
from __future__ import annotations

import re
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lecture-common"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from 프로젝트탐지 import 탐지  # noqa: E402

W = 78

# ── 빼는 것 ──────────────────────────────────────────────────────────
#   `_` 로 시작하는 폴더는 **원본·보관**이다. 검토자가 준 것을 되돌려 보낼 이유가 없다.
#   그리고 **돌리면 다시 생기는 것**은 안 보낸다 — 벡터 저장소·검사 결과물·빌드 산출물.
#   무겁기만 하고 받는 쪽에서 다시 만들면 된다. 게다가 안에 **우리 PC 의 흔적**이 들어 있다.
빼는폴더 = {"__pycache__", ".git", ".pytest_cache", "node_modules", "출력", ".claude",
            "chroma_db", ".chroma", ".chroma_test", "test-results", "playwright-report",
            "dist", "uploads", "build", ".next", ".cache"}


def _가상환경인가(name: str) -> bool:
    """`.venv` · `.venv312` · `.venv314` … **이름을 박지 않는다.**

    ⚠ `.venv312` 만 박아 뒀다가 `.venv314` 를 새로 만들자
      검사기가 그 안의 .py 13,237개를 **우리 랩으로 세었다.**
    """
    return name.startswith(".venv") or name in ("venv", "env")
# ★ `.gitignore` 를 빼지 않는다.
#   ⚠ 전에는 「잡파일」로 보고 뺐다. 그런데 **학생에게 나가는 틀에서는 산출물**이다 —
#     그것이 없으면 학생이 `git add .` 할 때 `.env` 가 저장소에 들어간다.
#     검토자에게 「무엇을 주고 무엇을 안 주는지 봐 달라」고 해 놓고 **그 파일만 안 보였다.**
#   재는 법 — 묶은 zip 을 열어 틀 폴더의 파일 수가 **실물과 같은지** 센다.
빼는파일 = {".env", "uv.lock"}

# 프로젝트가 **스스로 선언**하는 제외 목록 — 루트의 `.검토제외` 한 줄에 하나.
#   ⚠ 파일명을 스킬에 박으면 다른 프로젝트에서 안 맞는다.
#     내부 작업 문서(작업 대사·메모)는 프로젝트마다 이름이 다르다.
def _선언된제외(root) -> set[str]:
    f = root / ".검토제외"
    if not f.exists():
        return set()
    out = set()
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#")[0].strip()
        if line:
            out.add(line)
    return out
빼는확장 = {".pyc", ".zip", ".log", ".pyo"}


# 프로젝트가 **스스로 선언**하는 차단 예외 — 루트의 `.차단예외` 한 줄에 하나.
#   값이긴 한데 비밀이 아닌 것이 있다. 컨테이너 안에서만 닿는 DB 주소 같은 것.
#   ⚠ 정규식을 느슨하게 풀면 **진짜 접속 문자열까지 같이 새어 나간다.**
#     그래서 규칙이 아니라 **그 프로젝트가 그 줄 하나를** 지목하게 한다.
#   ⚠ 그리고 **통과시킨 것을 반드시 찍는다.** 조용히 지나가면 다음 사람이 모른다.
def _차단예외(root) -> list[str]:
    f = Path(root) / ".차단예외"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(line)
    return out

# ── 가리는 것 — 자리는 남기고 값만 ───────────────────────────────────
#   ⚠ **가리기는 차단(`금지`)이 끝난 뒤에 돈다.** 순서가 바뀌면 키·이메일이
#     `sk-****` 로 바뀐 뒤라 차단이 **영원히 못 잡는다.** 실측으로 확인된 결함이다.
가림 = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "****@****"),
    (re.compile(r"project-[0-9a-f]{8}-[0-9a-f-]+"), "project-********"),
    (re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b"), "******-******-******"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "sk-****"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "AIza****"),
    # 우리 PC 흔적 — 사용자 홈 경로. lecture-deliver 의 「가리기」 항목이 요구한다
    #   ⚠ `C:\Users\...\k-precision-lab` 처럼 **이미 가려 둔 자리는 다시 가리지 않는다.**
    #     학생 문서의 예시 화면이 `...` 에서 `****` 로 바뀌어 원본과 달라졌다.
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/](?![\*.])[^\\/\s\"'<>|]+"), r"C:\\Users\\****"),
    (re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+"), "/home/****"),
]


def 실명목록(root) -> list[str]:
    """`.가릴이름` 이 선언한 실명·사내 고유명. 한 줄에 하나.

    실명은 정규식으로 못 찾는다. **프로젝트가 선언해야 가릴 수 있다.**
    """
    f = Path(root) / ".가릴이름"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#")[0].strip()
        if line:
            out.append(line)
    return out

# ── 나가면 안 되는 것 ────────────────────────────────────────────────
금지 = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "OpenAI 키"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "Google API 키"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub 토큰"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "이메일"),
    (re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b"), "결제계정 번호"),
    (re.compile(r"admin1234|root1234|password123"), "기본 비밀번호"),
    (re.compile(r"\b\d{6}-[1-4]\d{6}\b"), "주민등록번호 꼴"),
    # 접속 문자열 — 한때 지침에만 있고 패턴이 없었다. lecture-deliver 의 차단 대상이다
    (re.compile(r"(?:postgres|postgresql|mysql|mongodb|redis|amqp)://[^\s\"'<>]+"),
     "접속 문자열"),
    # ⚠ `*` 만 자리표시자로 봤다가 `C:\Users\...` 를 **우리 PC 경로로 읽어 zip 을 막았다.**
    #   학생 문서가 사용자 이름을 `...` 로 가려 둔 예시 화면이었다. 점도 자리표시자다.
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/](?![\*.])[^\\/\s\"'<>|]+"), "우리 PC 경로"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "개인키"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack 토큰"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS 액세스 키"),
]

# 검사·예시·더미 같은 단어로 검출을 건너뛰는 목록은 두지 않는다.
#   공개 가능한 줄은 프로젝트가 `.차단예외` 에 **전체 줄**로 지목한다.

글자파일 = {".md", ".py", ".txt", ".csv", ".json", ".yml", ".yaml", ".toml", ".lock"}


def 가리기(text: str) -> tuple[str, int]:
    n = 0
    for pat, rep in 가림:
        text, k = pat.subn(rep, text)
        n += k
    return text, n


def 모으기(p, 목록=None) -> list[tuple[Path, str]]:
    """무엇을 넣을지 — **탐지된 구조에서 고른다.** 경로를 박지 않는다."""
    root = Path(p.루트)
    대상: list[tuple[Path, str]] = []

    제외 = _선언된제외(root)
    if 목록 is not None:
        names = json.loads(Path(목록).read_text(encoding='utf-8-sig'))
        if not isinstance(names,list) or not names:
            raise ValueError('파일 목록은 비어 있지 않은 JSON 배열이어야 합니다')
        seen = set()
        for name in names:
            if not isinstance(name,str) or not name or '\\' in name:
                raise ValueError('목록 경로는 / 구분의 상대 파일 경로여야 합니다')
            rel=Path(name)
            src=root/rel
            if rel.is_absolute() or '..' in rel.parts or ':' in name or not src.resolve().is_relative_to(root.resolve()):
                raise ValueError('목록 경로가 프로젝트 밖을 가리킵니다')
            key=name.casefold()
            if key in seen or src.resolve() in seen:
                raise ValueError('중복된 배포 파일입니다')
            if 제외 & set(rel.parts) or any(x in 빼는폴더 or _가상환경인가(x) for x in rel.parts) or rel.name == '.env':
                raise ValueError('제외 대상이 배포 목록에 포함됐습니다')
            if not src.is_file():
                raise ValueError(f'배포 파일이 없습니다: {name}')
            seen.update((key,src.resolve()))
            대상.append((src,rel.as_posix()))
        return 대상

    # 루트의 안내 문서
    for f in root.glob("*.md"):
        if f.name.startswith("_") or f.name in 제외:
            continue
        대상.append((f, f.name))

    # 폴더들
    for d in (p.문서폴더, p.가이드폴더, p.코드폴더):
        if not d:
            continue
        base = Path(d)
        if base == root:
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            if any(x in 빼는폴더 or _가상환경인가(x) or x.startswith("_")
                   for x in f.parts):
                continue
            if f.name in 빼는파일 or f.suffix.lower() in 빼는확장:
                continue
            # ★ `.검토제외` 는 **파일 이름만이 아니라 폴더 이름에도** 걸린다.
            #   폴더로 선언할 수 없으면 프로젝트가 자기 부산물을 못 뺀다.
            if 제외 & set(f.relative_to(base).parts):
                continue
            대상.append((f, f"{base.name}/{f.relative_to(base).as_posix()}"))

    # ── 그 밖의 곁폴더 — **이름을 박지 않는다** ────────────────────────
    #   ⚠ 전에는 `("강의안","슬라이드","덱")` 으로 박아 뒀다가
    #     실제 폴더 이름이 `강의덱` 인 프로젝트에서 **덱이 통째로 빠졌다**(2026-08-31).
    #     프로젝트마다 이름이 다르므로 **훑고, 뺄 것만 뺀다.**
    #   뺄 것 — `_` 로 시작(남의 원본·보관) · 이미 담은 폴더 · 가상환경 ·
    #           `.검토제외` 가 선언한 것(학생 산출물처럼 되살릴 수 있는 것)
    담은폴더 = {Path(d).name for d in (p.문서폴더, p.가이드폴더, p.코드폴더) if d}
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if (d.name.startswith("_") or d.name.startswith(".")
                or d.name in 담은폴더 or d.name in 빼는폴더
                or d.name in 제외 or _가상환경인가(d.name)):
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            if any(x in 빼는폴더 or _가상환경인가(x) or x.startswith("_")
                   for x in f.relative_to(d).parts):
                continue
            if (f.name in 빼는파일 or f.suffix.lower() in 빼는확장
                    or 제외 & set(f.relative_to(d).parts)):
                continue
            대상.append((f, f"{d.name}/{f.relative_to(d).as_posix()}"))

    # ── 같은 파일이 두 번 들어가지 않게 ────────────────────────────────
    #   ⚠ 전에는 **목적지 이름**으로만 걸렀다. 그래서 가이드 폴더가 코드 폴더 **안에**
    #     있는 구조에서 같은 파일이 `가이드/01.md` 와 `10_실습/가이드/01.md` 두 이름으로
    #     들어갔다 — **16개가 통째로 중복**됐다 (2026-09-08 실측).
    #     목적지가 다르니 그때는 안 걸렸다. **원본 파일로 걸러야 한다.**
    #   ★ 남길 쪽은 **경로가 깊은 것** — 프로젝트 트리 모양 그대로가 되어야
    #     안내문이 가리키는 경로(`10_실습/가이드/…`)와 어긋나지 않는다.
    골라둠: dict[Path, tuple[Path, str]] = {}
    for f, dst in 대상:
        키 = f.resolve()
        기존 = 골라둠.get(키)
        if 기존 is None or dst.count("/") > 기존[1].count("/"):
            골라둠[키] = (f, dst)

    본것: set[str] = set()
    끝: list[tuple[Path, str]] = []
    for f, dst in 대상:
        골라진 = 골라둠[f.resolve()][1]
        if dst != 골라진 or dst in 본것:
            continue
        본것.add(dst)
        끝.append((f, dst))
    return 끝


def main() -> None:
    미리 = "--미리보기" in sys.argv
    이름 = None
    if "--이름" in sys.argv:
        이름 = sys.argv[sys.argv.index("--이름") + 1]

    p = 탐지()
    if not p.루트:
        print("❌ 강의 프로젝트를 못 찾았다. 프로젝트 폴더 안에서 실행하라.")
        sys.exit(1)

    목록 = None
    if '--목록' in sys.argv:
        목록 = sys.argv[sys.argv.index('--목록') + 1]
    files = 모으기(p, 목록)
    print("=" * W)
    print(f"  검토자료 — {p.이름}")
    print("=" * W)
    print(f"\n  대상 {len(files)}개\n")

    구성: dict[str, int] = {}
    for _, dst in files:
        k = dst.split("/")[0] if "/" in dst else "(루트)"
        구성[k] = 구성.get(k, 0) + 1
    print("─" * W)
    print("  구성")
    print("─" * W)
    for k, v in sorted(구성.items(), key=lambda x: -x[1]):
        print(f"    {k:<26}{v:>5}개")

    print()
    print("─" * W)
    print("  뺀 것")
    print("─" * W)
    if 목록 is not None:
        print("    명시 목록 밖의 파일은 포함하지 않습니다. 파일 역할과 의존성을 따로 확인하세요.")
    else:
        print("    자동 탐지의 제외 추정: _ 접두사 · 출력 · 환경/캐시 · ZIP")
        print("    이 추정은 배포 계약이 아닙니다. 실제 생성에는 명시 목록이 필요합니다.")
    제외 = _선언된제외(Path(p.루트))
    if 제외:
        print(f"    `.검토제외` 선언   {' · '.join(sorted(제외))}")

    if 미리:
        print()
        print("=" * W)
        print("  (미리보기 — zip 을 만들지 않았다)")
        print("=" * W)
        return

    # ★ `.검토제외` 가 없으면 만들지 않는다.
    #   실측에서 그것 없이 **783개**(내부 기록·실험 폴더 포함)를 그냥 만들었다.
    #   무엇을 뺄지는 프로젝트가 선언해야 한다. 우리가 짐작해서 정하지 않는다.
    if 목록 is None:
        print()
        print("=" * W)
        print("  ⛔ 명시 파일 목록이 없다 — 미리보기만 가능합니다")
        print("=" * W)
        print("  대상 파일의 상대 경로 JSON 배열을 만들고 --목록 경로.json을 지정하세요.")
        print("  수신자와 요청 범위를 기준으로 목록을 확인하세요. 자동 수집은 구성 확정이 아닙니다.")
        print("=" * W)
        sys.exit(2)

    stem = 이름 or (p.이름 + '_검토자료')
    if any(c in stem for c in '/\\:') or stem in ('.','..'):
        raise ValueError('산출물 이름에는 경로를 넣을 수 없습니다')
    out = Path(p.루트) / f"{stem}.zip"
    if out.exists():
        raise FileExistsError('기존 ZIP을 보존합니다. 새 산출물 이름을 지정하세요')

    이름들 = 실명목록(p.루트)
    예외들 = _차단예외(p.루트)
    가린수, 문제, 통과 = 0, [], []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, dst in files:
            if src.suffix.lower() in 글자파일:
                원문 = src.read_text(encoding="utf-8", errors="replace")

                # ★ 차단이 **먼저**다. 가리고 나서 검사하면 이미 `sk-****` 라 못 잡는다.
                for pat, 이름표 in 금지:
                    for line in 원문.splitlines():
                        m = pat.search(line)
                        if not m:
                            continue
                        if line.strip() in 예외들:
                            통과.append(f"{dst}  —  {이름표}  (명시된 전체 줄 예외)")
                            continue      # 프로젝트가 「비밀이 아니다」라고 지목했다
                        문제.append(f"{dst}  —  {이름표}  (값은 출력하지 않음)")
                        break

                # 그다음에 가린다
                body, k = 가리기(원문)
                for 실명 in 이름들:            # 실명은 선언해야 가릴 수 있다
                    body, k2 = re.subn(re.escape(실명), "○○○", body)
                    k += k2
                가린수 += k
                z.writestr(dst, body)
            else:
                z.write(src, dst)

    print()
    print("─" * W)
    print(f"  가린 자리 {가린수}곳  (이메일 · 프로젝트 ID · 결제계정 · 키)")
    print("─" * W)

    if 통과:
        print()
        print("─" * W)
        print(f"  ⚠ `.차단예외` 로 통과시킨 것 {len(통과)}건 — **나간다.** 맞는지 눈으로 본다")
        print("─" * W)
        for x in 통과:
            print(f"    {x}")
    print()

    if 문제:
        print("=" * W)
        print(f"  ❌ **나가면 안 되는 것이 {len(문제)}건 남아 있다**")
        for x in 문제[:20]:
            print(f"     {x}")
        print("=" * W)
        out.unlink(missing_ok=True)
        print("  → zip 을 지웠다. 고치고 다시 돌려라.")
        print("     검사 단어로 우회하지 않습니다. 공개 가능한 예시는 전체 줄 단위로 검토하세요.")
        sys.exit(1)

    mb = out.stat().st_size / 1024 / 1024
    print("=" * W)
    print(f"  ✅ {out.name}   {len(files)}개 · {mb:.2f} MB")
    print("     비밀 검사 통과 — 키·이메일·계정번호 0건")
    print("=" * W)


if __name__ == "__main__":
    main()
