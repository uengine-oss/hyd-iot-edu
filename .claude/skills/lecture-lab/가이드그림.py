# -*- coding: utf-8 -*-
"""실습 가이드의 그림을 만든다 — **본문은 실제 실행 결과만.**

    python 가이드그림.py 수집   <랩경로> [--이름 D02_1_청킹]
    python 가이드그림.py 쳐보기 "<명령>" --이름 <세션> [--셸 pwsh|cmd] [--이어서]
    python 가이드그림.py 그림   <세션|출력파일> <그림이름> [--자름 5] [--줄 24] [--강조 "말"]
    python 가이드그림.py 편집기 <파일경로> <그림이름> [--표식 "빈칸 1"] [--찾기 "빈칸 1"]
    python 가이드그림.py 대조                     가이드가 부르는 그림 vs 있는 그림
    python 가이드그림.py 회귀                     랩이 다 도나 + 코드가 도는 시간

원칙
    **지어낸 화면은 넣지 않는다.** 「✔ 이 화면이 나오면 정상입니다」 칸에 들어갈 것은
    반드시 **실제로 돌려서 나온 출력**이어야 한다.

    터미널 그림은 **재현 그림이지 실제 캡처가 아니다.** 그래서 로그 본문만 실제를 쓴다.
    브라우저 화면 · VS Code 의 메뉴와 대화상자는 **사람이 찍는다** — 「대조」가 그 목록을 뽑는다.
    편집기 그림도 **코드는 실제 파일에서 읽는다.** 틀만 그린다.

    ⚠ VS Code 안에서 우리가 직접 칠 수 없으므로 **cmd · PowerShell 로 돌린다.**
      「쳐보기」가 그 실행을 대신하고, 나온 로그를 그대로 VS Code 터미널 모양으로 낸다.

규격
    강사 PC 의 실제 VS Code 화면(1536×864)에서 픽셀로 재서 뽑았다.
      셀 폭 9.0px · 줄 높이 22px · 배경 #191A1B
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lecture-common"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from 프로젝트탐지 import 탐지  # noqa: E402

W = 78

# ── 실측 규격 ────────────────────────────────────────────────────────
셀폭, 줄높이 = 9.0, 22
글자크기 = 셀폭 / 0.5498
왼여백, 위여백 = 20, 12
배경, 본문, 밝은흰 = "#191A1B", "#CCCCCC", "#E5E5E5"
청록, 노랑, 흐림, 구분선 = "#11A8CD", "#F5F543", "#727373", "#2A2B2C"
색표 = {"y": 노랑, "c": 청록, "w": 밝은흰, "d": 흐림}
마크 = re.compile(r"\[([ycwd])\](.*?)\[/\]", re.S)

TEMPLATE = """<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  html,body {{ background:{배경} }}
  #판 {{
    width:{폭}px; background:{배경}; position:relative;
    padding:{위여백}px 0 14px {왼여백}px;
    font-family:Consolas,'D2Coding','Cascadia Mono','Courier New',monospace;
    font-size:{글자크기}px; line-height:{줄높이}px;
    color:{본문}; letter-spacing:0; -webkit-font-smoothing:antialiased;
  }}
  #판 > div.줄 {{ white-space:pre; height:{줄높이}px }}
  #선 {{ position:absolute; top:0; right:8px; width:1px; height:100%; background:{구분선} }}
</style>
<div id="판"><div id="선"></div>{줄들}{덧}</div>
"""

# 진행바·경고는 실제 화면에도 안 남는 잡음이다
잡음 = ("Loading weights", "it/s]", "Downloading", "%|")


def _칠하기(줄: str) -> str:
    나온다, 끝 = [], 0
    for m in 마크.finditer(줄):
        나온다.append(html.escape(줄[끝:m.start()]))
        나온다.append(f'<span style="color:{색표[m.group(1)]}">{html.escape(m.group(2))}</span>')
        끝 = m.end()
    나온다.append(html.escape(줄[끝:]))
    return "".join(나온다)


def _한줄(줄: str) -> str:
    # `#원문` — 실행 출력 그대로. 색 표시를 **해석하지 않는다.**
    # 출력 안에 우연히 `[y]`·`[/]` 가 들어 있으면 색표시로 잡아먹혀 글자가 사라진다.
    if 줄.startswith("#원문"):
        본 = html.escape(줄[len("#원문"):].removeprefix(" "))
        return f'<div class="줄">{본 or "&nbsp;"}</div>'

    커서 = False
    if 줄.rstrip().endswith("#커서"):
        줄, 커서 = 줄.rstrip()[:-3].rstrip(), True
    # `#프롬프트c` 는 cmd — `PS` 가 붙지 않는다. 셸을 속이면 학생이 다른 창을 연다
    if 줄.startswith("#프롬프트c"):
        경로, _, 뒤 = 줄[len("#프롬프트c"):].lstrip().partition(">")
        줄 = f"[c]{경로.rstrip()}[/][w]> [/]" + 뒤.lstrip()
    elif 줄.startswith("#프롬프트"):
        경로, _, 뒤 = 줄[len("#프롬프트"):].lstrip().partition(">")
        줄 = f"[w]PS [/][c]{경로.rstrip()}[/][w]> [/]" + 뒤.lstrip()
    본 = _칠하기(줄)
    if 커서:
        본 += f'<span style="background:{본문};color:{배경}">&nbsp;</span>'
    return f'<div class="줄">{본 or "&nbsp;"}</div>'


# ── 실행 출력을 화면에 나온 모양으로 되돌린다 ────────────────────────
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")


def _화면줄(덩이: str) -> list[str]:
    """캡처한 stdout 을 **터미널에 실제로 남은 모양**으로 바꾼다.

    진행바는 `\\r` 로 같은 줄을 덮어쓴다. 그대로 두면 한 줄이 수백 줄이 된다 —
    `\\r` 로 갈라 **마지막 조각만** 남기는 것이 화면에 남는 것이다.
    """
    줄들: list[str] = []
    for 줄 in _ANSI.sub("", 덩이).replace("\x00", "").split("\n"):
        줄 = 줄.split("\r")[-1] if "\r" in 줄 else 줄
        줄들.append(줄.rstrip())
    while 줄들 and not 줄들[-1]:
        줄들.pop()
    return 줄들


def _칸수(s: str) -> float:
    """등폭 글꼴에서 **몇 칸을 차지하나.** 한글은 두 칸이다 —
    글자 수로 세면 빨간 네모가 한글 줄에서 절반쯤 어긋난다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _보이는글자(줄: str) -> str:
    """원고 한 줄이 **화면에 실제로 찍는 글자.** 색표시·지시어를 걷어낸다."""
    if 줄.startswith("#원문"):
        return 줄[len("#원문"):].removeprefix(" ")
    if 줄.rstrip().endswith("#커서"):
        줄 = 줄.rstrip()[:-3].rstrip()
    if 줄.startswith("#프롬프트c"):
        경로, _, 뒤 = 줄[len("#프롬프트c"):].lstrip().partition(">")
        줄 = f"{경로.rstrip()}> " + 뒤.lstrip()
    elif 줄.startswith("#프롬프트"):
        경로, _, 뒤 = 줄[len("#프롬프트"):].lstrip().partition(">")
        줄 = f"PS {경로.rstrip()}> " + 뒤.lstrip()
    return 마크.sub(lambda m: m.group(2), 줄)


def _짚기(원고: list[str], 말: str, 라벨: str | None, 폭: int) -> str:
    """**빨간 네모 + 라벨.** `references/그림요구.md` 「사람이 찍는 규격」과 같은 표시다 — 색만 바꾸면 눈에 안 띈다.

    등폭이라 칸으로 세면 좌표가 정확히 나온다. 눈으로 맞추지 않는다.
    """
    for i, 줄 in enumerate(원고):
        보임 = _보이는글자(줄)
        j = 보임.find(말)
        if j < 0:
            continue
        x = 왼여백 + _칸수(보임[:j]) * 셀폭
        y = 위여백 + i * 줄높이
        w = _칸수(말) * 셀폭
        상자 = (f'<div style="position:absolute;left:{x - 4:.1f}px;top:{y - 1}px;'
                f'width:{w + 8:.1f}px;height:{줄높이}px;border:2px solid #E51400;'
                f'border-radius:3px;pointer-events:none"></div>')
        if not 라벨:
            return 상자
        글폭 = _칸수(라벨) * 8.0 + 30
        오른쪽 = x + w + 14 + 글폭 < 폭
        자리 = (f"left:{x + w + 14:.1f}px" if 오른쪽
                else f"left:{max(x - 14 - 글폭, 6):.1f}px")
        화살 = "◀ " if 오른쪽 else ""
        꼬리 = "" if 오른쪽 else " ▶"
        딱지 = (f'<div style="position:absolute;{자리};top:{y - 2}px;'
                f'height:{줄높이 + 2}px;line-height:{줄높이 + 2}px;color:#FF6B5E;'
                f'font-family:\'Malgun Gothic\',sans-serif;font-size:14px;'
                f'white-space:pre">{화살}{html.escape(라벨)}{꼬리}</div>')
        return 상자 + 딱지
    print(f"  ⚠ 짚을 말을 화면에서 못 찾았다: 「{말}」 — 네모 없이 간다")
    return ""


def 그림만들기(원고: list[str], 나갈곳: Path, 폭: int = 1076, 덧: str = "") -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ❌ playwright 가 없다 —  pip install playwright")
        return False

    본문html = "".join(_한줄(l) for l in 원고)
    페이지 = TEMPLATE.format(배경=배경, 본문=본문, 구분선=구분선, 폭=폭,
                            위여백=위여백, 왼여백=왼여백,
                            글자크기=f"{글자크기:.2f}", 줄높이=줄높이,
                            줄들=본문html, 덧=덧)
    나갈곳.parent.mkdir(parents=True, exist_ok=True)
    임시 = 나갈곳.with_suffix(".html")
    임시.write_text(페이지, encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 폭, "height": 200}, device_scale_factor=1)
            pg.goto(임시.resolve().as_uri())
            잰값 = pg.evaluate("""() => {
                const 판 = getComputedStyle(document.getElementById('판'));
                const s = document.createElement('span');
                s.style.cssText = 'position:absolute;visibility:hidden;white-space:pre';
                s.style.font = 판.fontSize + ' ' + 판.fontFamily;
                s.textContent = 'M'.repeat(100);
                document.body.appendChild(s);
                const w = s.getBoundingClientRect().width / 100;
                s.remove(); return w;
            }""")
            pg.query_selector("#판").screenshot(path=str(나갈곳))
            b.close()
    finally:
        임시.unlink(missing_ok=True)
    상태 = "맞음" if abs(잰값 - 셀폭) < 0.15 else f"어긋남 (기준 {셀폭})"
    print(f"    {나갈곳.name}  줄 {len(원고)}개 · 셀폭 {잰값:.3f}px — {상태}")
    return True


# ── 랩 출력을 모아 두는 폴더 — 프로젝트마다 이름이 다르다 ──────────────
출력폴더_후보 = ["실행화면", "출력", "outputs", "output"]


def _출력폴더(p) -> Path:
    base = Path(p.가이드폴더 or p.루트)
    for n in 출력폴더_후보:
        if (base / n).is_dir():
            return base / n
    return base / 출력폴더_후보[0]


# ══ 수집 ═══════════════════════════════════════════════════════════
def 수집(p, 랩: str, 이름: str | None) -> None:
    """랩을 **실제로 돌려** 출력을 저장한다."""
    f = Path(랩)
    if not f.exists() and p.코드폴더:
        찾음 = list(Path(p.코드폴더).rglob(f.name))
        if 찾음:
            f = 찾음[0]
    if not f.exists():
        print(f"  ❌ 랩을 못 찾았다: {랩}")
        sys.exit(1)

    out = _출력폴더(p)
    out.mkdir(exist_ok=True)
    이름 = 이름 or f.stem
    dst = out / f"{이름}.txt"

    print(f"  ▶ {f.name}  ({f.parent.name})")
    r = subprocess.run([p.파이썬, f.name], cwd=str(f.parent),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900, stdin=subprocess.DEVNULL,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    body = r.stdout or r.stderr or ""
    dst.write_text(body, encoding="utf-8")
    표시 = "✅" if r.returncode == 0 else "❌"
    print(f"  {표시} {dst.name}  {len(body.splitlines())}줄  exit={r.returncode}")
    if r.returncode != 0:
        print("     ⚠ 실패한 출력은 가이드에 넣지 마라. 랩을 먼저 고쳐라")


# ══ 쳐보기 ═════════════════════════════════════════════════════════
def _세션(p, 이름: str) -> Path:
    return _출력폴더(p) / f"{이름}.세션.json"


def _셸명령(셸: str, 명령: str) -> list[str]:
    """윈도우 셸을 **UTF-8 로** 띄운다.

    기본 코드페이지(949)로 받으면 한글 출력이 깨진 채 그림에 박힌다.
    깨진 글자는 학생 화면과 다르므로 **지어낸 화면과 같은 죄**다.
    """
    if 셸 == "cmd":
        return ["cmd", "/d", "/c", f"chcp 65001>nul & {명령}"]
    exe = shutil.which("pwsh") or "powershell"
    앞 = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
          "$ProgressPreference='SilentlyContinue'; ")
    return [exe, "-NoProfile", "-NonInteractive", "-Command", 앞 + 명령]


def 쳐보기(p, 명령: str, 이름: str, 셸: str, 폴더: str | None,
           보일경로: str | None, 이어서: bool, 시간제한: int) -> None:
    """**cmd · PowerShell 로 진짜 친다.** 여기서 나온 것만 그림이 된다.

    VS Code 안에서 우리가 직접 칠 수 없으니 셸로 대신 치고, 그 로그를 쓴다.
    한 세션에 여러 명령을 `--이어서` 로 쌓으면 **실제 터미널처럼** 이어진 그림이 나온다.
    """
    일할곳 = Path(폴더) if 폴더 else Path(p.코드폴더 or p.루트)
    if not 일할곳.is_dir():
        print(f"  ❌ 실행할 폴더가 없다: {일할곳}")
        sys.exit(1)

    print(f"  ▶ [{셸}] {명령}")
    print(f"     ({일할곳})")
    잰시작 = time.perf_counter()
    try:
        r = subprocess.run(_셸명령(셸, 명령), cwd=str(일할곳),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=시간제한,
                           stdin=subprocess.DEVNULL,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        출력, 코드 = (r.stdout or "") + (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired:
        print(f"  ❌ {시간제한}초를 넘겼다 — 명령을 줄이거나 --시간제한 을 올려라")
        sys.exit(1)

    줄들 = _화면줄(출력)
    보일 = 보일경로 or str(일할곳)
    사용자 = os.environ.get("USERNAME") or os.environ.get("USER") or ""

    세션경로 = _세션(p, 이름)
    세션경로.parent.mkdir(parents=True, exist_ok=True)
    묶음 = {"이름": 이름, "만든때": datetime.now().isoformat(timespec="seconds"),
            "보일경로": 보일, "셸": 셸, "블록": []}
    if 이어서 and 세션경로.exists():
        묶음 = json.loads(세션경로.read_text(encoding="utf-8"))
        묶음["보일경로"] = 보일
    묶음["블록"].append({"명령": 명령, "셸": 셸, "폴더": str(일할곳),
                         "exit": 코드, "초": round(time.perf_counter() - 잰시작, 2),
                         "출력": 줄들})
    세션경로.write_text(json.dumps(묶음, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    표시 = "✅" if 코드 == 0 else "❌"
    print(f"  {표시} {세션경로.name}  블록 {len(묶음['블록'])}개 · "
          f"이번 {len(줄들)}줄 · exit={코드} · {묶음['블록'][-1]['초']}초")
    if 코드 != 0:
        print("     ⚠ 실패한 출력은 가이드의 「정상입니다」에 넣지 마라.")
        print("       에러 화면으로 쓸 것이면 그렇다고 캡션에 적어라 (references/그림요구.md)")
    if 사용자 and 사용자.lower() in 보일.lower():
        print(f"     ⚠ 보일 경로에 계정 이름 「{사용자}」 이 들어 있다 — "
              f"--보일경로 로 바꿔라. 학생 전원에게 나간다")


# ══ 그림 ═══════════════════════════════════════════════════════════
def _세션원고(묶음: dict, 자름: int, 줄수: int) -> list[str]:
    """세션 JSON → 터미널 원고. **명령도 실제로 친 그것을 쓴다.**"""
    보일, 원고 = 묶음.get("보일경로", ""), []
    표식 = "#프롬프트c" if 묶음.get("셸") == "cmd" else "#프롬프트"
    for i, b in enumerate(묶음["블록"]):
        if i:
            원고.append("")
        원고.append(f"{표식} {보일}> [y]{b['명령']}[/]")
        본 = [l for l in b["출력"] if not any(k in l for k in 잡음)]
        if 자름:
            본 = 본[자름:]
        if 줄수:
            본 = 본[:줄수]
        원고 += [f"#원문 {l}" for l in 본]
    원고 += ["", f"{표식} {보일}> #커서"]
    return 원고


def 그림(p, 출력: str, 이름: str, 명령: str | None,
         자름: int, 줄수: int, 경로: str | None, 강조: str | None = None,
         짚기: str | None = None, 라벨: str | None = None) -> None:
    out = _출력폴더(p)

    # ① 「쳐보기」 세션이 있으면 그것이 먼저다 — 명령·셸·경로가 다 들어 있다
    후보 = [Path(출력), out / 출력, _세션(p, 출력), out / f"{출력}.txt"]
    src = next((f for f in 후보 if f.exists()), None)
    if src is None:
        print(f"  ❌ 출력이 없다: {출력}   (먼저 `쳐보기` 또는 `수집` 하라)")
        sys.exit(1)

    if src.name.endswith(".세션.json"):
        묶음 = json.loads(src.read_text(encoding="utf-8"))
        if 경로:
            묶음["보일경로"] = 경로
        나쁨 = [b["명령"] for b in 묶음["블록"] if b["exit"] != 0]
        if 나쁨:
            print(f"  ⚠ exit≠0 인 블록이 {len(나쁨)}개 있다: {나쁨[0]}")
            print("    「정상입니다」 칸에 쓸 그림이면 랩을 고치고 다시 쳐라")
        원고 = _세션원고(묶음, 자름, 줄수)
    else:
        raw = src.read_text(encoding="utf-8", errors="replace").rstrip("\n").split("\n")
        body = [l for l in raw if not any(k in l for k in 잡음)]
        if 자름:
            body = body[자름:]
        if 줄수:
            body = body[:줄수]
        cwd = 경로 or str(Path(p.코드폴더 or p.루트))
        cmd = 명령 or f"python {src.stem}.py"
        원고 = ([f"#프롬프트 {cwd}> [y]{cmd}[/]"] + [f"#원문 {l}" for l in body]
                + ["", f"#프롬프트 {cwd}> #커서"])

    if 강조:
        원고 = _강조하기(원고, 강조)
    덧 = _짚기(원고, 짚기, 라벨, 1076) if 짚기 else ""

    이름 = 이름 if 이름.endswith(".png") else f"{이름}.png"
    dst = Path(p.그림폴더 or (Path(p.가이드폴더 or p.루트) / "그림")) / 이름
    그림만들기(원고, dst, 덧=덧)


def _강조하기(원고: list[str], 말: str) -> list[str]:
    """출력 안의 한 마디를 밝게 — **화살표 대신 색으로 짚는다.**"""
    친것, 나온다 = 0, []
    for 줄 in 원고:
        if 줄.startswith("#원문") and 말 in 줄:
            벗김 = 줄[len("#원문"):].removeprefix(" ")
            # 색표시가 이미 들어 있으면 손대지 않는다 — 겹치면 글자가 사라진다
            if 마크.search(벗김) or "[/]" in 벗김:
                나온다.append(줄)
                continue
            나온다.append(벗김.replace(말, f"[w]{말}[/]"))
            친것 += 1
        else:
            나온다.append(줄)
    if not 친것:
        print(f"  ⚠ 강조할 말을 출력에서 못 찾았다: 「{말}」 — 그대로 간다")
    else:
        print(f"    강조 「{말}」 {친것}줄")
    return 나온다


# ══ 편집기 ═════════════════════════════════════════════════════════
# VS Code Dark 실측 색 — 터미널 규격과 따로다 (편집기는 #1E1E1E, 터미널은 #191A1B)
편_배경, 편_사이드, 편_탭줄, 편_경계 = "#1E1E1E", "#252526", "#2D2D2D", "#3C3C3C"
편_본문, 편_줄번호, 편_주석, 편_문자열 = "#D4D4D4", "#6E7681", "#6A9955", "#CE9178"
편_키워드, 편_숫자 = "#C586C0", "#B5CEA8"

_키워드 = (r"\b(def|class|return|if|elif|else|for|while|in|is|not|and|or|None|"
           r"True|False|import|from|as|with|try|except|finally|raise|yield|"
           r"async|await|lambda|pass|break|continue)\b")


def _색칠(줄: str) -> str:
    """한 줄을 VS Code 색으로. **완전한 파서가 아니다** — 그림에 필요한 만큼만."""
    t = html.escape(줄)
    벗 = 줄.lstrip()
    if 벗.startswith("#") or 벗.startswith("//"):
        return f'<span style="color:{편_주석}">{t}</span>'
    t = re.sub(r"(&quot;.*?&quot;|&#x27;.*?&#x27;)",
               rf'<span style="color:{편_문자열}">\1</span>', t)
    t = re.sub(_키워드, rf'<span style="color:{편_키워드}">\1</span>', t)
    t = re.sub(r"\b(\d+\.?\d*)\b", rf'<span style="color:{편_숫자}">\1</span>', t)
    return t


# 학생 화면에 **절대 나오면 안 되는 것** — 우리 작업 흔적과 답
# 실제로 새는 사고가 있었다: 탐색기 그림에 `핸드오프.md` 와 `실행화면/` 이 찍혔다
기본숨김 = {"__pycache__", ".git", ".pytest_cache", "node_modules", ".venv",
            "실행화면", "출력", "outputs", "output", "제작", "검증리서치",
            "정답", "answers", "핸드오프.md", "HANDOFF.md", "인계.md",
            "handoff.md", "HANDOFF.MD", "verify_lab.py",
            # 런타임에 쌓이는 데이터 — 이름이 UUID 라 학생이 읽을 것이 없다.
            # 접지 않으면 탐색기의 좋은 자리를 통째로 차지한다
            "uploads", "chroma_db", "chroma", "data", "logs", "tmp", "cache",
            ".chroma", "storage", "내작업"}


def _탐색기(뿌리: Path, 연것: Path, 숨김: set[str],
            깊이제한: int = 3) -> list[tuple[int, str, bool]]:
    """탐색기 나무를 **폴더에서 읽어** 만든다.

    손으로 적어 두면 파일이 늘 때마다 그림이 거짓이 된다 — 실제로 그랬다.
    새로 생긴 파일이 그림에 없었고, 지운 파일이 그림에 남아 있었다.
    """

    def 훑기(d: Path, 깊이: int) -> list[tuple[int, str, bool]]:
        if 깊이 > 깊이제한:
            return []
        나무: list[tuple[int, str, bool]] = []
        try:
            것들 = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except OSError:
            return []
        for x in 것들:
            if x.name.startswith(".") or x.name in 숨김:
                continue
            if x.is_dir():
                나무.append((깊이, f"{x.name}/", False))
                나무 += 훑기(x, 깊이 + 1)
            else:
                나무.append((깊이, x.name, x.resolve() == 연것.resolve()))
        return 나무

    return 훑기(뿌리, 1)


def 편집기(p, 파일: str, 이름: str, 표식: str | None, 위: int, 아래: int,
           강조줄: int | None, 찾기: str | None, 트리: str | None,
           빼기: str | None = None) -> None:
    """실제 파일 → VS Code 편집기 화면 그림. **코드는 지어내지 않는다.**"""
    f = Path(파일)
    if not f.exists() and p.코드폴더:
        찾음 = list(Path(p.코드폴더).rglob(f.name))
        if 찾음:
            f = 찾음[0]
    if not f.exists():
        print(f"  ❌ 파일을 못 찾았다: {파일}")
        sys.exit(1)

    줄들 = f.read_text(encoding="utf-8", errors="replace").splitlines()
    첫줄 = 1
    if 표식:
        # 주석 줄만 잡는다. 설명문에도 같은 말이 나와 엉뚱한 데를 자른 적이 있다
        자리 = next((i for i, l in enumerate(줄들)
                     if 표식 in l and l.lstrip()[:2] in ("# ", "//", "#\t")
                     or (표식 in l and l.lstrip().startswith("#"))), None)
        if 자리 is None:
            print(f"  ❌ 표식을 못 찾았다: 「{표식}」 — 파일에 그 주석이 없다")
            sys.exit(1)
        첫줄 = max(자리 - 위, 0) + 1
        조각 = 줄들[첫줄 - 1:자리 + 아래 + 1]
        강조줄 = 강조줄 or (자리 + 1)
    else:
        조각 = 줄들[:위 or 26]

    뿌리 = (Path(트리) if 트리 else f.parent).resolve()
    숨김 = 기본숨김 | {x.strip() for x in (빼기 or "").split(",") if x.strip()}
    나무 = _탐색기(뿌리, f, 숨김)
    if not any(선택 for _, _, 선택 in 나무):
        print(f"  ⚠ 연 파일이 탐색기 나무에 없다 — --트리 를 {f.parent} 위로 잡아라")

    # ★ 탐색기가 코드보다 길면 그림이 세로로 늘어나 **코드가 귀퉁이로 밀린다.**
    #   실제로 코드 12줄 · 탐색기 72줄이 나와, `uploads/` 의 UUID 파일만 가득한
    #   못 쓰는 그림이 됐다. 학생이 봐야 할 것은 코드다.
    나무 = _나무줄이기(나무, 최대=max(len(조각) + 6, 20))
    dst = Path(p.그림폴더 or (Path(p.가이드폴더 or p.루트) / "그림"))
    dst.mkdir(parents=True, exist_ok=True)
    _편집기그리기(뿌리.name, 나무, f.name, 조각, 첫줄, 강조줄, 찾기,
                  dst / (이름 if 이름.endswith(".png") else f"{이름}.png"))


def _나무줄이기(나무: list[tuple[int, str, bool]],
                최대: int) -> list[tuple[int, str, bool]]:
    """탐색기가 길면 **연 파일 둘레만 남기고 접는다.**

    실제 VS Code 도 폴더가 크면 스크롤될 뿐 전부 펼쳐 보이지 않는다.
    **연 파일과 그 형제, 그리고 위로 가는 길**만 남기면 그림이 뜻을 잃지 않는다.
    """
    if len(나무) <= 최대:
        return 나무

    고른 = next((i for i, (_, _, s) in enumerate(나무) if s), 0)
    앞 = max(고른 - 최대 // 2, 0)
    뒤 = min(앞 + 최대, len(나무))
    앞 = max(뒤 - 최대, 0)

    남김 = list(나무[앞:뒤])
    # 위로 가는 길(조상 폴더)은 잘려도 다시 붙인다 — 없으면 어디인지 모른다
    깊이 = 남김[0][0] if 남김 else 0
    길: list[tuple[int, str, bool]] = []
    for i in range(앞 - 1, -1, -1):
        d, n, s = 나무[i]
        if d < 깊이:
            길.insert(0, (d, n, s))
            깊이 = d
            if d == 0:
                break
    잘린앞, 잘린뒤 = 앞 - len(길), len(나무) - 뒤
    if 잘린앞 > 0:
        길.append((깊이 + 1, f"⋯ {잘린앞}개 더", False))
    if 잘린뒤 > 0:
        남김.append((남김[-1][0], f"⋯ {잘린뒤}개 더", False))
    return 길 + 남김


def _편집기그리기(제목: str, 나무: list[tuple[int, str, bool]], 탭: str,
                  코드: list[str], 첫줄: int, 강조줄: int | None,
                  찾기: str | None, 나갈곳: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ❌ playwright 가 없다 —  pip install playwright && playwright install chromium")
        sys.exit(1)

    나무html = ""
    for 깊이, 이름, 선택 in 나무:
        bg = "background:#37373D;" if 선택 else ""
        화살 = "▾ " if 이름.endswith("/") else ""
        나무html += (f'<div style="padding:3px 0 3px {14 + 깊이 * 16}px;{bg}'
                     f'color:#CCCCCC">{화살}{html.escape(이름.rstrip("/"))}</div>')

    줄html = ""
    for i, 줄 in enumerate(코드):
        번호 = 첫줄 + i
        bg = "background:#2A2D2E;" if 강조줄 == 번호 else ""
        줄html += (f'<div style="display:flex;{bg}">'
                   f'<span style="width:44px;text-align:right;padding-right:16px;'
                   f'color:{편_줄번호};flex:none">{번호}</span>'
                   f'<span style="white-space:pre">{_색칠(줄)}</span></div>')

    찾기html = ""
    if 찾기:
        찾기html = (
            '<div style="position:absolute;top:30px;right:18px;z-index:5;'
            'background:#252526;border:1px solid #454545;border-radius:3px;'
            'box-shadow:0 2px 8px rgba(0,0,0,.36);padding:5px 8px;'
            'display:flex;align-items:center;gap:8px">'
            '<span style="color:#CCCCCC;font-size:13px">&#9662;</span>'
            '<span style="background:#3C3C3C;border:1px solid #007FD4;border-radius:2px;'
            "padding:3px 8px;min-width:190px;color:#CCCCCC;font-family:Consolas,monospace;"
            f'font-size:13px">{html.escape(찾기)}</span>'
            '<span style="color:#CCCCCC;font-size:13px">&#8593; &#8595; &#10005;</span></div>')

    높이 = max(300, 58 + max(len(코드), len(나무)) * 20 + 26)
    페이지 = f"""<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ background:{편_배경}; width:1360px;
         font-family:"Malgun Gothic",sans-serif; font-size:13px }}
  .mono {{ font-family:Consolas,"D2Coding","Cascadia Mono",monospace;
           font-size:14px; line-height:20px; color:{편_본문} }}
</style>
<div style="display:flex;height:{높이}px">
  <div style="width:52px;background:#333333;flex:none;padding-top:12px;text-align:center">
    <div style="font-size:20px;color:#FFFFFF;margin-bottom:18px">&#128459;</div>
    <div style="font-size:20px;color:#858585">&#128269;</div>
  </div>
  <div style="width:238px;background:{편_사이드};flex:none;border-right:1px solid {편_경계}">
    <div style="padding:10px 14px;color:#BBBBBB;font-size:11px;letter-spacing:.06em">탐색기</div>
    <div style="padding:4px 14px;color:#CCCCCC;font-weight:700;font-size:12px">▾ {html.escape(제목)}</div>
    {나무html}
  </div>
  <div style="flex:1;display:flex;flex-direction:column;position:relative">
    {찾기html}
    <div style="background:{편_탭줄};display:flex">
      <div style="background:{편_배경};color:#FFFFFF;padding:8px 16px;font-size:13px;
                  border-top:1px solid #0078D4">{html.escape(탭)}</div>
    </div>
    <div class="mono" style="flex:1;padding:10px 0;overflow:hidden">{줄html}</div>
  </div>
</div>"""

    나갈곳.parent.mkdir(parents=True, exist_ok=True)
    임시 = 나갈곳.with_suffix(".html")
    임시.write_text(페이지, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1360, "height": 높이})
            pg.goto(임시.resolve().as_uri())
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(나갈곳))
            b.close()
    finally:
        임시.unlink(missing_ok=True)
    print(f"    {나갈곳.name}  코드 {len(코드)}줄 · 탐색기 {len(나무)}줄")


# ══ 대조 ═══════════════════════════════════════════════════════════
def 대조(p) -> None:
    """가이드가 부르는 그림 vs 있는 그림 — **없는 것이 「사람이 찍을 것」이다.**"""
    if not p.가이드폴더:
        # 가이드가 없는 프로젝트도 있다(대본만 있는 특강 등).
        # **할 일이 없는 것은 실패가 아니다.** 실패로 끝내면 회귀에서 거짓 경보가 난다.
        print("  가이드 폴더가 없다 — 대조할 그림이 없다.")
        print("  가이드를 만들 자리면 `lecture-lab/references/실습가이드-틀.md` 형식으로 먼저 쓴다.")
        return
    gdir = Path(p.가이드폴더)
    있는것 = {f.name for f in Path(p.그림폴더).glob("*.png")} if p.그림폴더 else set()

    print("=" * W)
    print("  가이드가 부르는 그림 대조")
    print("=" * W)
    없는것: list[tuple[str, str, str]] = []
    for md in sorted(gdir.glob("*.md")):
        쓴것 = [(m.group(2), m.group(1)) for m in
                re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", md.read_text(encoding="utf-8"))]
        if not 쓴것:
            continue
        ok = sum(1 for f, _ in 쓴것 if Path(f).name in 있는것)
        모자람 = len(쓴것) - ok
        표시 = "" if 모자람 == 0 else f"  **없음 {모자람}**"
        print(f"\n  {md.stem[:28]:<30}부름 {len(쓴것):>2} · 있음 {ok:>2}{표시}")
        for f, cap in 쓴것:
            if Path(f).name not in 있는것:
                없는것.append((md.stem, Path(f).name, cap))
                print(f"      ❌ {Path(f).name}")
                print(f"         「{cap}」")

    print()
    print("=" * W)
    print(f"  사람이 찍을 것 **{len(없는것)}장**")
    print("=" * W)
    if 없는것:
        print("\n  체크리스트에 붙일 표 —\n")
        print("  | ☐ | 파일명 | 무엇이 보여야 하나 |")
        print("  |:---:|---|---|")
        for _, f, cap in 없는것:
            print(f"  | ☐ | `{f}` | {cap} |")
        print("\n  ⚠ **찍는 규격** — 1536×864 · VS Code Dark Modern · 계정 이메일은 가린다")


# ══ 회귀 ═══════════════════════════════════════════════════════════
def 회귀(p) -> None:
    """랩이 다 도나 + **코드가 도는 시간.**

    「4시간에 되는가」의 절반은 기계가 잰다. 나머지 절반(학생이 생각하는 시간)은 사람이 잰다.
    """
    도구 = p.도구.get("회귀")
    if 도구 and Path(도구).exists():
        subprocess.run([p.파이썬, 도구, "--offline"], cwd=p.루트,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return
    print("  ⚠ 회귀 도구가 없다. 랩을 하나씩 돌려 본다.")
    if not p.코드폴더:
        return
    ok = fail = 0
    for f in sorted(Path(p.코드폴더).rglob("*.py")):
        if any(x.startswith("_") or x.startswith(".venv") or x == "__pycache__"
               for x in f.parts):
            continue
        r = subprocess.run([p.파이썬, f.name], cwd=str(f.parent), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=600, stdin=subprocess.DEVNULL,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode == 0:
            ok += 1
        else:
            fail += 1
            print(f"    ❌ {f.name}")
    print(f"\n  PASS {ok} · FAIL {fail}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    p = 탐지()
    if not p.루트:
        print("❌ 강의 프로젝트를 못 찾았다. 프로젝트 폴더 안에서 실행하라.")
        sys.exit(1)

    def opt(name: str, default=None):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

    cmd = sys.argv[1]
    if cmd == "수집":
        수집(p, sys.argv[2], opt("--이름"))
    elif cmd == "쳐보기":
        이름 = opt("--이름")
        if not 이름:
            print("  ❌ --이름 <세션이름> 이 있어야 한다")
            sys.exit(1)
        쳐보기(p, sys.argv[2], 이름, opt("--셸", "pwsh"), opt("--폴더"),
               opt("--보일경로"), "--이어서" in sys.argv,
               int(opt("--시간제한", 300)))
    elif cmd == "그림":
        그림(p, sys.argv[2], sys.argv[3], opt("--명령"),
             int(opt("--자름", 0)), int(opt("--줄", 0)), opt("--경로"),
             opt("--강조"), opt("--짚기"), opt("--라벨"))
    elif cmd == "편집기":
        강조줄 = opt("--강조줄")
        편집기(p, sys.argv[2], sys.argv[3], opt("--표식"),
               int(opt("--위", 16)), int(opt("--아래", 5)),
               int(강조줄) if 강조줄 else None, opt("--찾기"), opt("--트리"),
               opt("--빼기"))
    elif cmd == "대조":
        대조(p)
    elif cmd == "회귀":
        회귀(p)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
