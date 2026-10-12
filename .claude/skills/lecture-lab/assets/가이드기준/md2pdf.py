"""마크다운 → PDF. 학생이 드라이브에서 **클릭 한 번으로 열 수 있게** 만든다.

    python md2pdf.py <입력.md> <출력.pdf> [제목]

왜 필요한가
    `.md` 를 드라이브에 올리면 미리보기가 안 되고, 받아도 메모장에서
    `**굵게**` `|표|` 가 그대로 보인다. 학생이 이틀 내내 볼 문서다.

무엇으로 만드나
    playwright(크롬 엔진). 슬라이드 렌더링에 이미 쓰고 있어 새로 깔 것이 없다.
    pandoc·LibreOffice 는 이 PC 에 없다.

한글 폰트
    맑은 고딕을 쓴다. 크롬이 시스템 폰트를 그대로 쓰므로 깨지지 않는다.
"""

from __future__ import annotations

import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import html
import re
import sys
from pathlib import Path

CSS = """
/* ─────────────────────────────────────────────────────────────────────────
   역할마다 생김새가 달라야 한다.
   전에는 큰 단계·작은 단계·터미널 명령·파일에 쓰는 코드가 **전부 같은 회색 상자**라
   학생이 「치는 것」과 「쓰는 것」을 구별하지 못했다.
   ───────────────────────────────────────────────────────────────────────── */

@page { size: A4; margin: 20mm 17mm 18mm; }

body { font-family: "Malgun Gothic","맑은 고딕",sans-serif; font-size: 10.5pt;
       line-height: 1.85; color: #1f2429;
       /* 한국어는 어절 단위로 끊는다 — 안 두면 낱말이 두 줄로 쪼개진다. */
       word-break: keep-all; overflow-wrap: break-word; }

/* 한글이 든 명령을 Consolas 로만 찍으면 한글이 다른 글꼴로 튀어 자간이 벌어진다.
   («cd 2일차/실습» 이 «cd  2일차 /실 습» 으로 보이던 자리)
   DotumChe(돋움체)는 한글 고정폭이라 폭이 맞는다. */
:root { --mono: Consolas,"DotumChe","돋움체","Cascadia Mono",monospace; }

h1 { font-size: 20pt; margin: 0 0 26px; padding-bottom: 10px; color: #14335e;
     border-bottom: 3px solid #1b4b8f; letter-spacing: -.01em; }

/* 큰 단계 — 여기서 확실히 끊긴다. 위에 굵은 줄, 아래위로 넉넉히. */
h2 { font-size: 15.5pt; color: #14335e; letter-spacing: -.01em;
     margin: 40px 0 16px; padding: 15px 0 0;
     border-top: 2.5px solid #1b4b8f; }

h3 { font-size: 12pt; margin: 34px 0 10px; color: #24405f; }

/* 소단계 문단 — `**1. …**` 시작. 위를 띄워 단계 경계가 지면에서 보인다. */
p.nstep { margin-top: 30px; }

p  { margin: 11px 0; }
ul, ol { margin: 11px 0; padding-left: 25px; }
li { margin: 6px 0; }

/* 글 속의 짧은 코드 */
code { font-family: var(--mono); font-size: 9.5pt; background: #eef1f5;
       padding: 1px 5px; border-radius: 3px; color: #a83232;
       letter-spacing: 0; }

/* ── 터미널에 치는 것 — 검은 화면. 한눈에 「이건 친다」 ─────────────────── */
.term { background: #1b2029; border-radius: 7px; margin: 14px 0 20px;
        padding: 11px 15px 13px; page-break-inside: avoid; }
.term .h { font-size: 8pt; color: #7f93ad; letter-spacing: .09em;
           margin: 0 0 7px; font-weight: 700; }
.term pre { margin: 0; padding: 0; background: none; border: 0; }
/* 긴 명령(예: psql 한 줄 질의)은 접어서 다 보이게 한다. `pre` 로 두면
   오른쪽이 잘려 나가 학생이 무엇을 치는지 못 본다. `pre-wrap` 은 부드러운
   줄바꿈이라 복사할 때는 여전히 한 줄로 붙는다. */
.term code { background: none; padding: 0; color: #eaf0f7; font-size: 10pt;
             white-space: pre-wrap; overflow-wrap: anywhere;
             letter-spacing: 0; }
.term .g { color: #63d68f; }                      /* > 프롬프트 */

/* ── 파일에 쓰는 코드 — 밝은 카드 + 위에 라벨 ────────────────────────────── */
.codecard { border: 1px solid #d5dbe3; border-radius: 7px; margin: 14px 0 20px;
            overflow: hidden; page-break-inside: avoid; }
.codecard .h { background: #eef2f7; border-bottom: 1px solid #d5dbe3;
               font-size: 8pt; color: #46587a; letter-spacing: .09em;
               font-weight: 700; padding: 6px 14px; }
.codecard pre { margin: 0; border: 0; border-radius: 0; background: #fbfcfe;
                padding: 12px 15px; }
/* 긴 줄은 접어서 보여 준다. `pre` 로 두면 주소처럼 긴 값이 오른쪽에서 **잘려** 안 보이는데,
   종이는 옆으로 스크롤할 수가 없다(실측 2026-09-17: 중계 주소가 `/v1/resp` 에서 끊겼다).
   **매달린 들여쓰기(text-indent 음수)는 여기서 안 통한다.** 코드칸 전체가 글자 덩어리 하나라
   그 규칙이 「각 줄」이 아니라 「덩어리의 첫 줄」에만 걸린다. 접힌 뒷줄은 왼쪽 끝으로 나와
   구조가 무너진다(같은 날 실측). 접히는 것 자체를 줄이려면 **원문 들여쓰기를 얕게** 쓴다 —
   9.5pt 기준 한 줄에 약 85자가 들어가므로, 탭(8칸)보다 2칸 들여쓰기가 안전하다. */
.codecard code { background: none; padding: 0; color: #1f2429; font-size: 9.5pt;
                 white-space: pre-wrap; overflow-wrap: anywhere; }

/* 위 둘에 안 걸린 나머지 */
pre { background: #f7f8fa; border: 1px solid #dde1e6; border-radius: 5px;
      padding: 11px 14px; margin: 14px 0; page-break-inside: avoid; }
pre code { font-family: var(--mono); background: none; padding: 0; color: #1f2429; }

table { border-collapse: collapse; width: 100%; margin: 16px 0 20px;
        font-size: 9.5pt; page-break-inside: avoid; }
th { background: #eef2f7; border: 1px solid #c9d2dc; padding: 8px 10px;
     text-align: left; font-weight: 700; color: #24405f; }
td { border: 1px solid #d8dee6; padding: 8px 10px; vertical-align: top; }
/* 크롬은 `table` 에 건 break-inside 를 잘 안 지킨다 — 실측(2026-08-22): 결측 표가
   머리행 「적는 값」 글자 중간에서 쪼개져 다음 쪽으로 넘어갔다.
   행 단위로 걸어 두면 최소한 줄 가운데서 끊기지 않고, 표가 쪽을 넘길 때는
   머리행이 다음 쪽에도 다시 찍힌다. */
tr, th, td { page-break-inside: avoid; break-inside: avoid; }
thead { display: table-header-group; }

blockquote { border-left: 4px solid #f0a500; background: #fffaf0; margin: 16px 0;
             padding: 11px 16px; page-break-inside: avoid; }
blockquote p { margin: 5px 0; }

/* 세로로 긴 캡처가 쪽에 안 들어가면 통째로 다음 쪽에 밀려 큰 공백이 남는다 —
   높이를 눌러 밀림 자체를 줄인다. 사진+설명은 figure 한 덩어리라
   쪽 경계에서 서로 갈라지지 않는다. */
figure { margin: 14px 0 18px; page-break-inside: avoid; break-inside: avoid; }
/* 이미지는 **본문 폭을 꽉 채우는 것이 기본**이다.
   높이 상한을 낮게 걸면 세로로 긴 화면이 눌려 폭까지 같이 줄고, 그만큼 쪽 아래에 여백이 남는다.
   실측(2026-09-17): 90mm 상한에서 33장 중 15장이 폭 176mm 를 못 채웠고 세로로 긴 확장 화면은 63mm 까지 줄었다.
   A4 본문 높이는 259mm 이므로 130mm 는 한 쪽에 캡처 둘이 들어가는 크기다. */
img { max-width: 100%; max-height: 90mm; border: 1px solid #c9d2dc;
      border-radius: 6px; margin: 0 0 4px; display: block; }

/* 세로로 아주 긴 화면(세로가 가로의 1.2배 초과)만 더 허용한다 — 이것까지 130mm 로 누르면 글자가 안 읽힌다. */
img.tall { max-height: 120mm; }
.cap { font-size: 9pt; color: #5a6672; margin: 0; }

/* 작은 단계 ①②③ — 상자를 없앤다. 숨 막히던 원인이 이것이다.
   왼쪽에 짧은 막대 하나만 두고 글씨로 승부한다. */
.step { margin: 24px 0 10px; padding: 0 0 0 13px; font-size: 11.5pt;
        font-weight: 700; color: #14335e; letter-spacing: -.01em;
        border-left: 4px solid #f0a500; page-break-after: avoid; }

/* 구역 이름 — 조용하게 */
.label { margin: 24px 0 8px; font-size: 9pt; font-weight: 700;
         color: #7a848f; letter-spacing: .09em; page-break-after: avoid; }
.label .x { color: #7a848f; font-weight: 400; }
/* 스텝 뒤에 붙는 자리 표시 `▸ VS Code 터미널` — 조작보다 한 칸 뒤로 */
.step .x { color: #7a848f; font-weight: 400; font-size: 10pt; letter-spacing: 0; }

/* 마무리 한 문장 */
.punch { margin: 18px 0; padding: 11px 15px; font-weight: 700; color: #1f4636;
         background: #f2f8f4; border-left: 4px solid #4f8f68; border-radius: 5px; }
.punch code { background: #e2efe7; color: #1f4636; }

.trouble { border: 1px solid #e6d2d2; border-left: 5px solid #c0392b;
           background: #fdf8f7; border-radius: 5px; padding: 10px 14px;
           margin: 10px 0; page-break-inside: avoid; }
.trouble .t { margin: 0 0 5px; font-weight: 700; color: #8a2020; font-size: 10pt; }
.trouble .t code { background: #f6e7e7; color: #8a2020; }
.trouble .b { margin: 0; font-size: 10pt; }

hr { border: 0; border-top: 1px solid #e4e8ed; margin: 30px 0; }
hr:has(+ h2) { display: none; }        /* 큰 단계가 제 윗줄을 갖는다 */
h1 + hr { display: none; }
/* 제목 바로 밑 큰 단계는 제 윗줄을 안 그린다 — h1 밑줄과 겹쳐 빈 띠로 보인다 */
h1 + h2, h1 + hr + h2 { border-top: 0; margin-top: 24px; padding-top: 0; }
strong { color: #14335e; }
h1, h2, h3 { page-break-after: avoid; }

/* 스텝 제목 · 치는 명령 · 그 결과 화면을 한 덩어리로 붙여 둔다.
   크롬은 `break-after: avoid` 를 잘 안 지킨다 — 실측(2026-08-22): 1쪽 끝이
   `http://localhost:8000` 인데 그 주소로 열리는 대시보드 캡처가 2쪽으로 넘어갔고,
   `① 7일치에 돌립니다` 와 그 명령칸도 6·7쪽으로 갈라졌다.
   `break-inside` 는 확실히 지키므로, 갈라지면 안 되는 것끼리 감싸 둔다. */
.keep { page-break-inside: avoid; break-inside: avoid; }
"""


def 인라인(t: str) -> str:
    """굵게·코드·링크만 바꾼다. 순서가 중요하다 — 코드 안은 건드리지 않는다."""
    조각: list[str] = []

    def 보관(m: re.Match) -> str:
        조각.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(조각) - 1}\x00"

    t = re.sub(r"`([^`]+)`", 보관, t)
    t = html.escape(t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)          # 링크는 글자만 남긴다
    t = re.sub(r"\x00(\d+)\x00", lambda m: 조각[int(m.group(1))], t)
    return t


# 구역 이름 — 조작이 아니라 「여기부터 이런 내용」을 알리는 표찰이다.
# 조용하게 두고 위에 선만 그어 구역을 뗀다 (굵게 강조하면 조작 단계와 뒤섞인다).
구역이름 = ("먼저 나오는 화면", "이어서 나오는 화면", "나오는 화면",
         "승인 요청 화면", "안 되면", "막혔으면", "읽는 법")


def 특수한줄(l: str) -> bool:
    """문단에 이어 붙이면 안 되는 줄 — 표·목록·그림·코드·**줄 전체가 굵은 것**.

    `**` 로 시작만 하는 줄은 이어지는 문장이다.
    (`**전부 정상**입니다. 원래 …` — 이걸 제외하면 한 문장이 중간에서 벌어진다)
    """
    s = l.strip()
    return (s.startswith(("#", "|", "```", "!", ">", "→", "<!--", "---"))
            or bool(re.fullmatch(r"\*\*[^*].*\*\*", s))     # 줄 전체가 굵은 것만
            or bool(re.match(r"^\s*[-*]\s+", l))
            or bool(re.match(r"^\s*\d+\.\s+", l)))


# 명령·출력·파일코드·수식·지시문은 **하는 일이 다르다.**
# 전에는 전부 같은 회색 상자라 학생이 명령을 파일에 붙여넣는 일이 났다.
#
# ★ 여기 없는 낱말로 시작하면 「화면에 이렇게 나옵니다」로 뒤집힌다 —
#   치라고 준 명령에 「나옵니다」가 붙으면 학생은 그 상자가 입력인지 결과인지
#   모른다. 실제로 docker·wsl·powershell 이 빠져 다섯 곳이 그랬다.
#   명령을 새로 쓰면 그 첫 낱말이 여기 있는지 본다.
명령시작 = ("uv ", "cd ", "python ", "py ", "git ", "pip ", "code ", "npx ",
        "docker ", "wsl ", "powershell ", "gcloud ", "curl ", "tr ", "for ")

# 말머리(``` 뒤에 적는 것) → (칸 종류, 위에 붙일 라벨)
칸종류 = {
    "python": ("codecard", "파일에 씁니다"),
    "py":     ("codecard", "파일에 씁니다"),
    "json":   ("codecard", "파일에 이렇게 있습니다"),
    "모양":    ("codecard", "이런 모양으로 돌려줍니다"),
    "지시문":  ("codecard", "AI 에게 주는 말 — 그대로 씁니다"),
    "주소":    ("term",     "크롬 주소창에 붙여넣습니다"),
    "쿼리":    ("term",     "Neo4j 입력칸에 붙여넣고 Ctrl + Enter"),   # 그래프 DB 브라우저에 치는 Cypher 
    "수식":    ("plain",    ""),
}


def 코드칸(줄: list[str], 말: str) -> str:
    """말머리로 갈라 놓고, 안 적었으면 명령인지 화면 출력인지 스스로 가른다."""
    본문 = "\n".join(줄).rstrip()
    안전 = html.escape(본문)
    종류, 라벨 = 칸종류.get(말, (None, None))

    if 종류 == "plain":
        return f"<pre><code>{안전}</code></pre>"
    if 종류 == "codecard":
        return (f'<div class="codecard"><div class="h">{라벨}</div>'
                f'<pre><code>{안전}</code></pre></div>')
    if 종류 == "term":
        return (f'<div class="term"><div class="h">{라벨}</div>'
                f'<pre><code>{안전}</code></pre></div>')

    쓸것 = [x for x in 줄 if x.strip()]
    if 쓸것 and all(x.lstrip().startswith(명령시작) for x in 쓸것):
        몸 = "\n".join(html.escape(x.strip()) for x in 쓸것)
        return ('<div class="term"><div class="h">터미널에 칩니다</div>'
                f'<pre><code>{몸}</code></pre></div>')

    return ('<div class="term"><div class="h">화면에 이렇게 나옵니다</div>'
            f'<pre><code>{안전}</code></pre></div>')


def _세로로긴가(경로: Path, 기준: float = 1.2) -> bool:
    """세로가 가로의 `기준` 배를 넘는가. 못 읽으면 False — 크기 판정 하나로 문서 생성을 막지 않는다."""
    try:
        from PIL import Image
        w, h = Image.open(경로).size
        return h / w > 기준
    except Exception:
        return False


def md2html(
md: str, 제목: str, 기준폴더: Path | None = None) -> str:
    out: list[str] = []
    줄들 = md.splitlines()
    i = 0
    while i < len(줄들):
        line = 줄들[i]

        # 그림 — `![설명](경로)`. 상대 경로는 md 파일 위치 기준으로 절대화한다.
        if m := re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip()):
            설명, 경로 = m.group(1), Path(m.group(2))
            if not 경로.is_absolute() and 기준폴더 is not None:
                경로 = (기준폴더 / 경로).resolve()
            # 그림이 없으면 PDF 에 깨진 자리만 남는다 — 학생이 받는 문서다. 여기서 멈춘다.
            if not 경로.is_file():
                raise SystemExit(f"안내문이 가리키는 그림이 없습니다: {경로}\n"
                                 f"  (원본 캡처를 제작/빌드도구/그림표시.py 로 만들어 두세요)")
            # 사진과 설명 글귀는 한 덩어리 — 쪽 경계에서 따로 갈라지면 안 된다.
            꼬리 = f'<div class="cap">{html.escape(설명)}</div>' if 설명 else ""
            # 세로로 긴 화면은 높이 상한을 더 준다. 안 그러면 폭까지 같이 줄어 쪽에 여백만 남는다.
            클래스 = ' class="tall"' if _세로로긴가(경로) else ""
            out.append(f'<figure><img{클래스} src="{경로.as_uri()}" '
                       f'alt="{html.escape(설명)}">{꼬리}</figure>')
            i += 1
            continue

        if line.startswith("```"):                                  # 코드블록
            말 = line[3:].strip().lower()
            i += 1
            buf = []
            while i < len(줄들) and not 줄들[i].startswith("```"):
                buf.append(줄들[i])
                i += 1
            i += 1
            out.append(코드칸(buf, 말))
            continue

        # 주석 — `<!-- 사진 … -->`. 아직 안 찍은 화면의 자리를 가이드에 표시해 둔 것이다.
        # 그냥 두면 인라인()이 `<` 를 이스케이프해 **학생 PDF 에 태그가 그대로 찍힌다.**
        # 코드블록 안의 `<!--` 는 위에서 이미 소비되므로 여기 안 온다.
        if line.strip().startswith("<!--"):
            while i < len(줄들) and "-->" not in 줄들[i]:
                i += 1
            i += 1                                                  # `-->` 가 있는 줄까지 버린다
            continue

        if re.match(r"^\s*\|.*\|\s*$", line):                       # 표
            표 = []
            while i < len(줄들) and re.match(r"^\s*\|.*\|\s*$", 줄들[i]):
                표.append(줄들[i])
                i += 1
            칸 = [[c.strip() for c in r.strip().strip("|").split("|")] for r in 표]
            머리 = 칸[0]
            몸 = [r for r in 칸[1:] if not re.match(r"^[\s:\-]+$", "".join(r))]
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{인라인(c)}</th>" for c in 머리)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{인라인(c)}</td>" for c in r)
                                 + "</tr>" for r in 몸)
                       + "</tbody></table>")
            continue

        if m := re.match(r"^(#{1,4})\s+(.*)$", line):
            n = len(m.group(1))
            out.append(f"<h{min(n,3)}>{인라인(m.group(2))}</h{min(n,3)}>")
        elif line.startswith(">"):
            buf = []
            while i < len(줄들) and 줄들[i].startswith(">"):
                buf.append(줄들[i].lstrip(">").strip())
                i += 1
            # 원본에서 보기 좋게 줄바꿈한 자리가 문단 나눔이 되면 안 된다 —
            # 빈 `>` 줄에서만 문단을 가르고, 이어지는 줄은 한 문단으로 붙인다.
            문단들: list[str] = []
            모음: list[str] = []
            for x in buf:
                if x and not x.startswith(("-", "→")):
                    모음.append(x)
                    continue
                if 모음:
                    문단들.append(" ".join(모음))
                    모음 = []
                if x:
                    문단들.append(x)
            if 모음:
                문단들.append(" ".join(모음))
            out.append("<blockquote>"
                       + "".join(f"<p>{인라인(x)}</p>" for x in 문단들)
                       + "</blockquote>")
            continue
        elif re.match(r"^\s*[-*]\s+", line):
            # 들여쓴 이어짐 줄은 그 항목의 뒷문장이다 — 따로 내보내면
            # 항목 밖으로 떨어져 나가 문장이 끊긴다.
            buf: list[str] = []
            while i < len(줄들):
                if re.match(r"^\s*[-*]\s+", 줄들[i]):
                    buf.append(re.sub(r"^\s*[-*]\s+", "", 줄들[i]))
                elif (buf and 줄들[i].startswith((" ", "\t")) and 줄들[i].strip()
                      and not 줄들[i].lstrip().startswith(("![", "```", "|", ">"))):
                    buf[-1] += " " + 줄들[i].strip()
                else:
                    break
                i += 1
            out.append("<ul>" + "".join(f"<li>{인라인(x)}</li>" for x in buf) + "</ul>")
            continue
        elif re.match(r"^\s*\d+\.\s+", line):
            # 항목 사이에 사진이 끼면 목록이 여기서 끊겼다 다시 시작한다 —
            # 원문의 숫자를 살려야 「2. 3. 4.」가 전부 「1.」로 리셋되지 않는다.
            첫숫자 = int(re.match(r"^\s*(\d+)\.", line).group(1))
            buf = []
            while i < len(줄들):
                if re.match(r"^\s*\d+\.\s+", 줄들[i]):
                    buf.append(re.sub(r"^\s*\d+\.\s+", "", 줄들[i]))
                elif (buf and 줄들[i].startswith((" ", "\t")) and 줄들[i].strip()
                      and not 줄들[i].lstrip().startswith(("![", "```", "|", ">"))):
                    buf[-1] += " " + 줄들[i].strip()
                else:
                    break
                i += 1
            시작 = f' start="{첫숫자}"' if 첫숫자 != 1 else ""
            out.append(f"<ol{시작}>" + "".join(f"<li>{인라인(x)}</li>" for x in buf) + "</ol>")
            continue
        # ── 「안 되면」 카드 ──────────────────────────────────────────────
        #    **화면에 뜬 문구**
        #    → 무슨 뜻인가 — 이렇게 하세요
        #    두 줄을 한 박스로 묶는다. 따로 <p> 로 내보내면 경계가 안 보인다.
        elif (re.fullmatch(r"\*\*[^*].*\*\*", line.strip())
              and i + 1 < len(줄들) and 줄들[i + 1].lstrip().startswith("→")):
            제목 = line.strip()[2:-2]
            본문 = 줄들[i + 1].lstrip()[1:].strip()      # `→` 는 표시일 뿐, 지면엔 안 낸다
            i += 2                                      # `line` 은 아직 안 소비됐다 — 둘 다 넘긴다
            out.append(f'<div class="trouble"><p class="t">{인라인(제목)}</p>'
                       f'<p class="b">{인라인(본문)}</p></div>')
            continue
        # ── 조작 단계 — `**① …**`. 학생이 실제로 하는 것이라 제일 세워 둔다
        #    뒤에 `▸ VS Code 터미널` 같은 자리 표시가 붙어도 스텝이다. 전에는
        #    `fullmatch` 가 `**` 에서 끝나기를 요구해, 자리 표시가 붙은 스텝만
        #    보통 문단으로 떨어졌다 — 주황 막대도 안 붙고 쪽 묶음에서도 빠졌다.
        elif m := re.fullmatch(r"\*\*([①-⑳㉑-㉟])\s*(.+)\*\*(\s*▸\s*.+)?", line.strip()):
            자리 = (m.group(3) or "").strip()
            꼬리 = f' <span class="x">{인라인(자리)}</span>' if 자리 else ""
            out.append(f'<p class="step">{m.group(1)} {인라인(m.group(2))}{꼬리}</p>')

        # ── 구역 이름 — `**안 되면**`, `**나오는 화면** — 덧말`
        elif m := re.fullmatch(r"\*\*(" + "|".join(구역이름) + r")\*\*(.*)", line.strip()):
            덧말 = m.group(2).strip()
            꼬리 = f' <span class="x">{인라인(덧말)}</span>' if 덧말 else ""
            out.append(f'<p class="label">{m.group(1)}{꼬리}</p>')

        # ── 마무리 한 문장 — 줄 전체가 굵고 위 둘이 아닌 것.
        #    코드만 굵은 것(에러 카드 제목)은 여기 안 온다 — 위에서 이미 소비된다.
        elif (re.fullmatch(r"\*\*[^*].*\*\*", line.strip())
              and not line.strip().startswith("**`")):
            out.append(f'<p class="punch">{인라인(line.strip()[2:-2])}</p>')

        elif re.match(r"^\s*---+\s*$", line):
            out.append("<hr>")

        # ── 보통 문단 — **이어지는 줄은 한 문단으로 붙인다.**
        #    한 줄이 곧 한 문단이 되면, 원본에서 보기 좋게 줄바꿈한 자리가
        #    지면에서 문단 나눔이 되어 **한 문장이 중간에서 벌어진다.**
        elif line.strip():
            묶음 = [line.strip()]
            i += 1
            while i < len(줄들) and 줄들[i].strip() and not 특수한줄(줄들[i]):
                묶음.append(줄들[i].strip())
                i += 1
            # `**1. …**` 로 시작하는 문단은 큰 단계의 소단계다 — 위를 띄워
            # 어디서 새 단계가 시작되는지 지면에서 보이게 한다.
            칸이름 = "nstep" if re.match(r"\*\*\d+\.", 묶음[0]) else ""
            붙임 = f' class="{칸이름}"' if 칸이름 else ""
            out.append(f"<p{붙임}>{인라인(' '.join(묶음))}</p>")
            continue
        elif line.strip():
            out.append(f"<p>{인라인(line)}</p>")
        i += 1

    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(제목)}</title><style>{CSS}</style></head>"
            f"<body>{''.join(붙여두기(out))}</body></html>")


def 붙여두기(out: list[str]) -> list[str]:
    """쪽 경계에서 갈라지면 안 되는 것끼리 `.keep` 으로 감싼다.

    붙이는 짝은 둘이다.
      ① 스텝 제목  +  바로 뒤 블록(명령칸·코드칸·그림)
         ①②③ 큰 단계뿐 아니라 `**3. …**` 소단계(`nstep`)도 같다. 전에는 큰 단계만
         잡아서, 소단계 제목만 쪽 끝에 남고 그 화면이 다음 쪽으로 넘어갔다(실측 2026-09-17).
      ② 치는 명령  +  그 명령이 띄우는 화면 캡처
      ③ 한 항목짜리 번호 목록  +  그 항목의 화면 캡처
         `1. …` 아래에 그림을 들여 쓰면 목록이 거기서 끊기고 `<ol start=n>` 하나 +
         `<figure>` 로 나온다. 묶지 않으면 「아래 사진과 같으면 된 것입니다」만
         쪽 끝에 남는다(실측 2026-09-17).

    ②까지 묶는 이유 — 명령은 이 쪽에 있고 결과 화면은 다음 쪽에 있으면
    학생이 「이게 맞게 나온 건가」를 쪽을 넘겨 가며 대조해야 한다.
    """
    덩어리 = ('<div class="term">', '<div class="codecard">', '<figure>', '<pre>')
    묶음: list[str] = []
    i = 0
    while i < len(out):
        조각 = [out[i]]
        j = i + 1
        if out[i].startswith(('<p class="step">', '<p class="nstep">')) and j < len(out)                 and out[j].startswith(덩어리):
            조각.append(out[j]); j += 1
        # 명령칸 뒤에 곧바로 캡처가 오면 그것까지 한 덩어리
        if 조각[-1].startswith(('<div class="term">', '<pre>')) and j < len(out)                 and out[j].startswith('<figure>'):
            조각.append(out[j]); j += 1
        # 한 항목짜리 번호 목록 뒤의 캡처도 그 항목의 것이다
        if len(조각) == 1 and out[i].startswith('<ol') and out[i].count('<li>') == 1                 and j < len(out) and out[j].startswith('<figure>'):
            조각.append(out[j]); j += 1
        if len(조각) > 1:
            묶음.append('<div class="keep">' + "".join(조각) + "</div>")
        else:
            묶음.append(out[i])
        i = j
    return 묶음


def _여백만큼_키우기(pdf: Path, pg, tmp: Path, 여백: dict, 최소남김: float = 12.0) -> bool:
    """뽑아 놓은 PDF 를 읽어 쪽마다 남은 높이를 재고, 그 쪽 캡처를 남은 만큼 키운다.

    돌려주는 값 — 하나라도 키웠으면 True(그러면 부르는 쪽에서 다시 뽑는다).
    pymupdf 가 없거나 못 읽으면 조용히 False. 크기 조정 하나로 문서 생성을 막지 않는다.
    """
    try:
        import pymupdf
    except ModuleNotFoundError:
        return False
    try:
        doc = pymupdf.open(pdf)
        아래여백pt = 18 / 25.4 * 72
        키울것: dict[int, float] = {}          # 화면에서 몇 번째 img 인가 → 더할 mm
        본순서 = 0
        for i in range(doc.page_count):
            page = doc[i]
            상자 = [page.get_image_bbox(b) for b in page.get_images(full=True)]
            글 = [b[3] for b in page.get_text("blocks")]
            바닥 = max([r.y1 for r in 상자] + 글) if (상자 or 글) else 0.0
            남음mm = (page.rect.height - 아래여백pt - 바닥) / 72 * 25.4
            for r in 상자:
                if 남음mm > 최소남김 and len(상자) >= 1:
                    키울것[본순서] = (남음mm - 최소남김) / len(상자)
                본순서 += 1
        doc.close()
        if not 키울것:
            return False
        # 화면의 img 를 순서대로 찾아 인라인 높이를 준다. 폭은 CSS 가 100% 로 잡고 있으므로
        # 높이만 올리면 원본 비율 안에서 커진다 (원본보다 커지지는 않는다).
        pg.evaluate(
            """(더할) => {
                const imgs = [...document.querySelectorAll('figure img')];
                for (const [k, mm] of Object.entries(더할)) {
                    const im = imgs[+k];
                    if (!im) continue;
                    const 지금 = im.getBoundingClientRect().height / 96 * 25.4;
                    im.style.maxHeight = (지금 + mm) + 'mm';
                }
            }""", {str(k): v for k, v in 키울것.items()})
        tmp.write_text(pg.content(), encoding="utf-8")
        return False        # 화면에 이미 반영했으므로 reload 없이 바로 다시 뽑게 한다
    except Exception:
        return False


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    제목 = sys.argv[3] if len(sys.argv) > 3 else dst.stem

    if not src.is_file():
        print(f"입력 파일이 없습니다: {src}", file=sys.stderr)
        return 1

    html_str = md2html(src.read_text(encoding="utf-8"), 제목, 기준폴더=src.parent)
    tmp = dst.with_suffix(".tmp.html")
    tmp.write_text(html_str, encoding="utf-8")

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("playwright 가 없습니다 —  pip install playwright  후  playwright install chromium",
              file=sys.stderr)
        return 1

    dst.parent.mkdir(parents=True, exist_ok=True)
    여백 = {"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(tmp.resolve().as_uri())
        pg.pdf(path=str(dst), format="A4", print_background=True, margin=여백)

        # ── 쪽에 남는 높이만큼 그 쪽의 캡처를 키운다 (영역 관리)
        #
        # CSS 의 높이 상한은 고정값이라 「이 쪽에 얼마나 남았는지」를 모른다. 그래서 상한을 올리면
        # 캡처가 커진 만큼 다음 덩어리가 밀려 **한 쪽에 캡처 하나만 남고 아래가 비는** 일이 생긴다.
        # 실측(2026-09-17 준비안내): 상한 90mm → 여백 80mm 넘는 쪽 4개, 130mm 로 올리면 16개.
        #
        # 그래서 한 번 뽑아 본 뒤 쪽마다 바닥에 남은 높이를 재고, 그 쪽에 있는 캡처에만
        # 남은 만큼을 더해 다시 뽑는다. 쪽이 늘지 않는 선까지만 키운다.
        _여백만큼_키우기(dst, pg, tmp, 여백)
        pg.pdf(path=str(dst), format="A4", print_background=True, margin=여백)
        b.close()
    tmp.unlink(missing_ok=True)
    print(f"  만듦  {dst.name}  ({dst.stat().st_size / 1024:.0f}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
