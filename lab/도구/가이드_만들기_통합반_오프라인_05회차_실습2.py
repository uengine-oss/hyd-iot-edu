"""통합반 오프라인 5회차 실습 2 「설비 이상의 원인을 추론하는 에이전트」의 가이드.html을 만든다.

    python3 lab/도구/가이드_만들기_통합반_오프라인_05회차_실습2.py [묶음 폴더]

- 요청 글은 묶음의 `기록/*_요청.txt`에서, 화면에 싣는 결과는 `기록/`과 `완성/결과/`의 파일에서 읽는다.
- 스타일은 `lab/도구/가이드_스타일_길잡이.css`에서 읽는다.
"""
import html
import json
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
묶음 = Path(sys.argv[1]) if len(sys.argv) > 1 else 여기.parent / "통합반_오프라인" / "05회차_실습2_원인_추론_에이전트"
기록 = 묶음 / "기록"

e = html.escape
사진_수 = 0
복사_수 = 0

채팅 = ("w-chat", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="22" y="3" width="9" height="16" rx="2" fill="#6d28d9"/></svg>')
편집 = ("w-code", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="3" y="3" width="8" height="16" rx="2" fill="#1d4ed8"/></svg>')
터미널 = ("w-term", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="3" y="13" width="28" height="6" rx="2" fill="#0f766e"/></svg>')
안내 = ("w-page", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="6" y="6" width="22" height="2.5" rx="1" fill="#374151"/><rect x="6" y="11" width="22" height="2.5" rx="1" fill="#374151"/><rect x="6" y="16" width="14" height="2.5" rx="1" fill="#374151"/></svg>')


def 할_일(번호, 곳, 곳_이름, 제목, *몸):
    return (f'<section class="do {곳[0]}" data-n="{번호}"><span class="where {곳[0]}">{곳[1]}{곳_이름}</span>'
            f'<h2>{제목}</h2>{"".join(몸)}</section>')


def 글(*문장):
    return "".join(f"<p>{m}</p>" for m in 문장)


def 차례(*줄):
    return '<ol class="todo">' + "".join(f"<li><span>{m}</span></li>" for m in 줄) + "</ol>"


def 요청(이름):
    global 복사_수
    복사_수 += 1
    본문 = (기록 / f"{이름}_요청.txt").read_text(encoding="utf-8").strip()
    return (f'<div class="copy"><div class="copy-top"><span>Copilot에게 보낼 요청</span><button data-copy="c{복사_수}">복사</button></div>'
            f'<div class="copy-text pre" id="c{복사_수}">{e(본문)}</div>'
            f'<div class="copy-foot">붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸 · 붙여넣고 Enter</div></div>')


def 명령(글자):
    global 복사_수
    복사_수 += 1
    return f'<div class="cmd"><span id="c{복사_수}">{e(글자)}</span><button data-copy="c{복사_수}">복사</button></div>'


def 사진(보이는_것):
    global 사진_수
    사진_수 += 1
    return f'<div class="shot"><div><b>화면 {사진_수}</b><span>{보이는_것}</span></div></div>'


def 되면(제목, 내용):
    return f'<div class="ok"><b>{제목}</b>{내용}</div>'


def 다르면(*쌍):
    return '<div class="if">' + "".join(f"<div><b>{a}</b>{b}</div>" for a, b in 쌍) + "</div>"


def 출력(글자):
    return f'<div class="out">{e(글자)}</div>'


def 머리(번호, 제목, 한_일, 끝나면):
    return (f'<section class="hero"><div class="no">{번호}</div><h1>{제목}</h1><p>{한_일}</p>'
            f'<div class="facts"><div><small>이 단계가 끝나면</small>{끝나면}</div></div></section>')


def 화면_줄(결과):
    return f"{결과['번호']}  {결과['근거_상태']}  도구 호출 {len(결과['호출_기록'])}번  대조 어긋남 {len(결과['대조'])}건  ({결과['멈춤']})"


def _json(경로):
    return json.loads(Path(경로).read_text(encoding="utf-8"))


둘 = _json(기록 / "3_결과_S01.json")[0]
셋 = _json(기록 / "4_결과_S01.json")[0]
넷 = _json(기록 / "7_결과.json")
끝 = _json(묶음 / "완성" / "결과" / "점검_계획.json")
규칙 = _json(묶음 / "완성" / "에이전트_정의.json")["작업_규칙"]

이름들 = ["준비", "1. 읽게 한다", "2. 규칙을 정한다", "3. 도구 둘로 한 건", "4. 센서 도구 붙이기",
       "5. 결과를 맞춰 본다", "6. 규칙을 건드려 본다", "7. 조치 도구 붙이기", "8. 되돌려 준다"]

단계 = []

# ── 준비 ─────────────────────────────────────────────────────────────
def 파일(이름, 설명, 종류=""):
    return f'<div class="{종류}"><tt>{이름}</tt><span>{설명}</span></div>'


순서 = [("읽게 한다", "만들기 전에 Copilot에게 자료를 읽고 한 건을 대어 보게 한다"),
      ("규칙을 정한다", "비어 있는 다섯 가지를 내가 정하고 만들 계획을 받는다"),
      ("도구 둘로 한 건", "도구.py와 에이전트.py를 만들어 사례 하나를 돌린다"),
      ("센서 도구 붙이기", "센서 값을 읽는 도구를 더해 열한 건을 돌린다"),
      ("결과를 맞춰 본다", "에이전트의 답이 맞는지 내 눈으로 가린다"),
      ("규칙을 건드려 본다", "어긋나는 요청을 보내 Copilot이 거절하는지 본다"),
      ("조치 도구 붙이기", "점검마다 절차 번호가 달리게 한다"),
      ("되돌려 준다", "아쉬운 곳을 말로 짚어 고치게 한다")]

단계.append(
    '<section class="hero"><div class="no">준비</div><h1><small>통합반 오프라인 5회차 · 실습 2</small>'
    '온톨로지와 센서 값으로<br>원인을 가리는 에이전트를 만든다</h1>'
    '<p>경보가 뜬 사례를 받으면 에이전트가 도구로 온톨로지와 센서 값을 읽고, 확인된 원인과 가설을 갈라 다음에 점검할 것을 낸다. '
    '도구를 하나씩 붙여 가며 같은 사례의 답이 어떻게 달라지는지 본다.</p></section>'
    '<section class="sect"><h2>오늘 만드는 것</h2>'
    '<div class="pipe"><div><b>공용 온톨로지</b>원인, 증거의 기준, 조치 방법<small>온톨로지 폴더</small></div><span>+</span>'
    '<div><b>센서 입력</b>경보가 뜬 사례 11건<small>입력 폴더</small></div><span>→</span>'
    '<div class="made"><b>점검 계획</b>후보 원인, 점검 순서, 호출 기록<small>결과 폴더</small></div></div></section>'
    '<section class="sect"><h2>받은 폴더 <code>시작</code>에 들어 있는 것</h2><div class="files">'
    + 파일("온톨로지/", "설비 지식이 들어 있는 폴더", "dir")
    + 파일("<i>├─ </i>읽는_법.md", "그래프를 읽는 법. 가장 먼저 읽는다")
    + 파일("<i>├─ </i>그래프.json", "원인, 증거의 기준, 조치 방법이 이어져 있는 그래프")
    + 파일("<i>└─ </i>스키마.json", "그래프에 어떤 종류의 것이 있는지 적은 정의")
    + 파일("입력/", "에이전트가 받는 사례가 들어 있는 폴더", "dir")
    + 파일("<i>├─ </i>센서_입력.json", "경보가 뜬 사례 11건의 센서 값")
    + 파일("<i>└─ </i>입력_설명.md", "입력의 칸마다 무슨 뜻인지")
    + 파일("결과/", "에이전트가 낸 점검 계획이 생기는 폴더. 지금은 비어 있다", "dir")
    + 파일("에이전트_정의.json", "에이전트의 목표, 쓸 수 있는 도구, 따를 규칙. 오늘 여러 번 고친다")
    + 파일("연결.py", "사내 AI 서버에 연결하는 코드. 고치지 않는다")
    + 파일("접속_정보.txt", "수업에서 받은 접속 정보를 적는 곳")
    + 파일(".github/copilot-instructions.md", "Copilot이 이 폴더에서 지킬 규칙. Copilot이 정해 둔 이름이라 영어다")
    + 파일("도구.py", "<em>오늘 만든다.</em> 온톨로지와 센서 값을 읽어 주는 도구", "new")
    + 파일("에이전트.py", "<em>오늘 만든다.</em> 도구를 부르고 점검 계획을 내는 프로그램", "new")
    + '</div></section>'
    '<section class="sect"><h2>오늘의 순서</h2><ol class="flow">'
    + "".join(f'<li data-go="{i}"><em>{i}</em><div><b>{a}</b><span>{b}</span></div></li>' for i, (a, b) in enumerate(순서, 1))
    + '</ol></section>'
    '<section class="sect"><h2>걸음마다 붙은 색</h2><ul class="key">'
    + "".join(f'<li><span class="where {곳[0]}">{곳[1]}{이름}</span>{뜻}</li>' for 곳, 이름, 뜻 in
              [(채팅, "Copilot 채팅", "요청을 보내고 답을 읽는다"), (편집, "편집기", "파일을 열어 읽거나 고친다"),
               (터미널, "터미널", "명령을 실행한다"), (안내, "이 화면", "읽고 정한다")])
    + '</ul></section>'
    + 할_일(1, 편집, "VS Code · 탐색기", "받은 폴더 <code>시작</code>을 VS Code로 연다",
          글("「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 위 표의 폴더와 파일이 보이면 된다."),
          사진("시작 폴더를 연 VS Code. 왼쪽 탐색기에 폴더 넷과 파일 셋이 보인다."))
    + 할_일(2, 편집, "VS Code · 편집기", "받은 접속 정보를 넣는다",
          차례("탐색기에서 <code>접속_정보.txt</code>를 연다.",
             "수업에서 받은 세 값을 위의 세 줄 등호 뒤에 하나씩 붙여 적는다. 등호 뒤에 빈칸을 두지 않는다. 맨 아래 줄은 그대로 둔다.",
             "저장한다(Ctrl+S)."),
          되면("주의", "키는 채팅에 붙여넣지 않는다. 이 파일에만 적는다."))
    + 할_일(3, 터미널, "VS Code · 터미널", "사내 AI 서버에 연결되는지 확인한다",
          글("「터미널 → 새 터미널」을 열고 아래 명령을 실행한다."),
          명령("python 연결.py"),
          되면("이렇게 나오면 된다", "첫 줄이 <code>연결됨</code>으로 시작하고, 둘째 줄에 인사 한 줄이 나온다."),
          다르면(("비어 있다고 나온다", "<code>접속_정보.txt</code>에 값을 적고 저장했는지 본다. 탭에 흰 점이 있으면 아직 저장되지 않은 것이다."),
              ("키가 맞지 않는다 · 닿지 못했다고 나온다", "<code>접속_정보.txt</code>의 세 값을 받은 것과 다시 견준다. 앞뒤에 따옴표나 빈칸이 들어갔는지 본다. 그래도 안 되면 강사에게 알린다.")))
    + 할_일(4, 편집, "VS Code · 편집기와 종이", "사례 S01을 손으로 먼저 대어 본다",
          글("뒤에서 에이전트의 답이 맞는지 가리려면 내 답이 하나 있어야 한다."),
          차례("<code>온톨로지/읽는_법.md</code>에서 「경보에서 원인과 조치까지 가는 길」을 읽는다.",
             "<code>입력/센서_입력.json</code> 맨 위의 <code>S01</code>에서 CE 평균, VS1 평균, TS4 평균을 찾는다.",
             "아래 표의 빈칸을 종이에 채운다."),
          '<table class="res"><tr><th>원인 후보</th><th>증거의 기준</th><th>S01의 값</th><th>맞음 / 아님</th></tr>'
          '<tr><td rowspan="2">쿨러 핀 오염</td><td>CE 30초 평균이 70 미만</td><td></td><td></td></tr>'
          '<tr><td>VS1 120초 평균이 0.9 미만</td><td></td><td></td></tr>'
          '<tr><td>주변 온도 상승</td><td>TS4 120초 평균이 35 이상</td><td></td><td></td></tr>'
          '<tr><td>팬 구동 불량</td><td>VS1 120초 평균이 0.9 이상</td><td></td><td></td></tr></table>')
)

# ── 1단계 ────────────────────────────────────────────────────────────
단계.append(
    머리("1단계", "만들기 전에,<br>읽고 대어 보게 한다",
       "바로 만들어 달라고 하지 않는다. 먼저 자료를 읽고 한 건을 대어 보게 해서, Copilot이 온톨로지를 나와 같게 읽는지 본다.",
       "Copilot이 읽은 길과 S01의 표, 나에게 묻는 것이 채팅에 있다. 새 파일은 없다")
    + 할_일(1, 채팅, "Copilot 채팅", "채팅을 열고 입력 칸 아래를 본다",
          글("VS Code 오른쪽의 Copilot 채팅을 연다. 입력 칸 아래에 <b>에이전트</b>와 <b>GPT-6 Luna</b>가 골라져 있는지 본다. 다르면 그 글자를 눌러 바꾼다."),
          사진("Copilot 채팅이 열린 VS Code. 입력 칸 아래에 에이전트와 GPT-6 Luna가 보인다."))
    + 할_일(2, 채팅, "Copilot 채팅 · 입력 칸", "아래 요청을 복사해 보낸다", 요청("1"))
    + 할_일(3, 채팅, "Copilot 채팅 · 답", "답에서 세 가지를 본다",
          사진("Copilot의 답. 관계를 한 줄씩 적은 부분, S01의 표, 끝에서 묻는 부분이 보인다."),
          '<div class="find">'
          '<div><i>①</i><p style="margin:0"><b>길</b><span>이상 패턴 → 증상 → 고장 유형 → 원인 → 증거의 순서로 적혀 있다.</span></p></div>'
          '<div><i>②</i><p style="margin:0"><b>S01의 표</b><span>내 종이와 같다. 쿨러 핀 오염의 증거 둘은 맞음(46.2 &lt; 70, 0.575 &lt; 0.9), 나머지 둘은 아님이다.</span></p></div>'
          '<div><i>③</i><p style="margin:0"><b>되묻는 것</b><span>「확인됨」을 무엇으로 볼지 같은 것을 스스로 정하지 않고 나에게 물었다.</span></p></div></div>',
          다르면(("파일이 생겼다", "생긴 파일을 지우고 요청을 다시 복사해 보낸다."),
              ("표가 내 종이와 다르다", "어느 칸이 어떻게 다른지를 말해 준다. 예: 「팬 구동 불량의 기준은 0.9 이상인데 값은 0.575야.」")))
)

# ── 2단계 ────────────────────────────────────────────────────────────
단계.append(
    머리("2단계", "에이전트가 따를 규칙을 정하고,<br>계획을 받는다",
       "Copilot이 물은 것은 이 폴더의 규칙이 일부러 비워 둔 다섯 가지다. 내가 정하면 그 문장이 <code>에이전트_정의.json</code>의 작업 규칙에 들어가고, 에이전트는 그 문장을 읽고 판단한다.",
       "작업 규칙이 일곱 줄이 되고, 만들 계획이 채팅에 있다")
    + 할_일(1, 안내, "이 화면", "다섯 가지를 어떻게 정할지 읽는다",
          '<table class="res"><tr><th>비어 있는 것</th><th>오늘 정하는 답</th></tr>'
          '<tr><td>값이 없거나 관측이 모자란 증거, 신선하지 않은 사례</td><td>판정을 <b>확인하지_못함</b>으로 둔다</td></tr>'
          '<tr><td>원인의 구분</td><td>증거가 모두 맞음이면 <b>확인됨</b>, 모두 아님이면 <b>해당_없음</b>, 그 밖은 <b>가설</b></td></tr>'
          '<tr><td>증거가 등록되지 않은 원인</td><td><b>가설</b>로 둔다</td></tr>'
          '<tr><td>사례의 근거 상태</td><td>확인됨이 하나라도 있으면 <b>SUPPORTED</b>, 모두 해당_없음이면 <b>UNSUPPORTED</b>, 그 밖은 <b>UNKNOWN</b></td></tr>'
          '<tr><td>점검 순서</td><td>확인하지 못한 값 다시 확인 → 확인됨 → 가설. 해당_없음은 넣지 않는다</td></tr></table>',
          글("다르게 정하고 싶으면 아래 요청의 문장을 고쳐서 보낸다."))
    + 할_일(2, 채팅, "Copilot 채팅 · 입력 칸 (같은 대화)", "정한 것을 보내고 계획을 받는다", 요청("2"))
    + 할_일(3, 편집, "VS Code · 편집기와 채팅", "두 가지를 확인한다",
          차례("<code>에이전트_정의.json</code>을 연다. <code>작업_규칙</code>이 세 줄에서 일곱 줄로 늘었다.",
             "채팅의 계획에 실행 고리의 다섯 가지(지시, 도구 실행, 호출 기록, 멈춤, 대조)가 모두 있다."),
          사진("Copilot의 계획. 도구.py와 에이전트.py에 둘 것이 나뉘어 적혀 있다."),
          다르면(("도구.py나 에이전트.py가 벌써 생겼다", "지우고, 「계획만 말해 줘」라고 다시 보낸다."),
              ("계획 끝에 더 묻는 것이 있다", "읽고 답해 준다. 모르겠으면 「이 폴더의 규칙대로, 규칙에 없으면 가장 단순하게」라고 답한다.")))
)

# ── 3단계 ────────────────────────────────────────────────────────────
단계.append(
    머리("3단계", "도구 둘로 만들어<br>한 건만 돌린다",
       "지금 허용 목록의 도구는 <code>원인_후보</code>와 <code>증거_기준</code> 둘이다. 센서 값을 읽는 도구가 없는 에이전트가 무엇을 내는지 먼저 본다.",
       "도구.py와 에이전트.py가 있고, S01의 결과가 결과 폴더에 있다")
    + 할_일(1, 채팅, "Copilot 채팅 · 입력 칸 (같은 대화)", "만들어 달라고 한다", 요청("3"),
          글("파일을 만들어도 되는지 물으면 허용한다. 끝나면 탐색기에 <code>도구.py</code>와 <code>에이전트.py</code>가 생긴다."))
    + 할_일(2, 터미널, "VS Code · 터미널", "S01 한 건을 돌린다",
          명령("python 에이전트.py S01"),
          글("몇 초 뒤 한 줄이 나온다. 아래는 한 번 돌린 결과다. 숫자와 괄호 안의 글은 사람마다 다를 수 있다."),
          출력(화면_줄(둘)))
    + 할_일(3, 편집, "VS Code · 편집기", "<code>결과/점검_계획.md</code>를 열어 세 곳을 본다",
          '<div class="find">'
          '<div><i>①</i><p style="margin:0"><b>근거 상태가 UNKNOWN이다</b><span>세 원인이 모두 가설이고, 증거는 모두 확인하지_못함이다. 값을 읽을 도구가 없기 때문이다.</span></p></div>'
          f'<div><i>②</i><p style="margin:0"><b>호출 기록</b><span>에이전트가 부른 도구가 순서대로 적혀 있다. 한 번 돌린 결과에서는 {" → ".join(h["도구"] for h in 둘["호출_기록"])}였다. 허용 목록에 없는 <code>센서_집계</code>는 없다.</span></p></div>'
          f'<div><i>③</i><p style="margin:0"><b>대조</b><span>에이전트가 호출 기록에 없는 것을 답에 적으면 여기에 잡힌다. 한 번 돌린 결과에서는 조치 칸에 매뉴얼의 절 번호를 적어 「{e(둘["대조"][0])}」가 {len(둘["대조"])}건 잡혔다.</span></p></div></div>',
          사진("결과/점검_계획.md의 미리 보기. S01의 근거 상태, 대조, 호출 기록이 보인다."),
          다르면(("오류가 나고 멈춘다", "터미널의 마지막 몇 줄을 복사해 채팅에 붙이고 「이 오류를 고쳐 줘」라고 보낸다."),
              ("근거 상태가 SUPPORTED로 나온다", "읽지 않은 값을 지어낸 것이다. 대조에 무엇이 적혔는지 본다. 그대로 두고 다음 단계로 간다.")))
)

# ── 4단계 ────────────────────────────────────────────────────────────
단계.append(
    머리("4단계", "센서 값을 읽는<br>도구를 붙인다",
       "허용 목록은 사람이 고친다. 내가 목록에 <code>센서_집계</code>를 더하고, Copilot에게 그 도구를 만들게 한다.",
       "S01이 SUPPORTED로 바뀌고, 열한 건의 결과가 있다")
    + 할_일(1, 편집, "VS Code · 편집기", "허용 목록에 한 줄을 더한다",
          글("<code>에이전트_정의.json</code>의 <code>도구</code>를 아래처럼 고치고 저장한다. 앞 줄 끝의 쉼표를 빠뜨리지 않는다."),
          '<div class="tree">"도구": [\n  "원인_후보",\n  "증거_기준"<b>,</b>\n  <b>"센서_집계"</b>\n],</div>')
    + 할_일(2, 채팅, "Copilot 채팅 · 입력 칸 (같은 대화)", "도구를 만들어 달라고 한다", 요청("4"))
    + 할_일(3, 터미널, "VS Code · 터미널", "S01을 다시 돌리고, 이어서 열한 건을 돌린다",
          명령("python 에이전트.py S01"),
          출력(화면_줄(셋)),
          글("S01이 SUPPORTED로 바뀌었으면 인자 없이 한 번 더 실행한다. 열한 건에 1분쯤 걸린다."),
          명령("python 에이전트.py"),
          사진("터미널에 사례 열한 건이 한 줄씩 찍힌 화면."),
          다르면(("JSON 오류가 난다", "<code>에이전트_정의.json</code>에서 쉼표와 따옴표를 본다."),
              ("S01이 여전히 UNKNOWN이다", "결과의 호출 기록에 <code>센서_집계</code>가 있는지 본다. 없으면 허용 목록에 더한 것을 저장했는지 확인한다.")))
)

# ── 5단계 ────────────────────────────────────────────────────────────
표 = "".join(
    f'<tr><td class="nw">{r["번호"]}</td><td>{r["근거_상태"]}</td>'
    f'<td>{", ".join(c["이름"] for c in r["후보_원인"] if c.get("구분") == "확인됨") or "—"}</td>'
    f'<td>{", ".join(c["이름"] for c in r["후보_원인"] if c.get("구분") == "가설") or "—"}</td>'
    f'<td>{len(r["대조"])}</td></tr>' for r in 끝)
단계.append(
    머리("5단계", "결과를<br>내 눈으로 맞춰 본다",
       "에이전트가 낸 답이 맞는지는 내가 가린다. 손으로 대어 본 S01부터 보고, 나머지는 대조와 호출 기록으로 본다. 이 단계에서는 Copilot에게 시키는 일이 없다.",
       "어느 사례가 맞고 어느 사례가 어긋났는지 안다")
    + 할_일(1, 편집, "VS Code · 편집기", "S01을 내 종이와 견준다",
          글("<code>결과/점검_계획.md</code>의 S01을 본다. 쿨러 핀 오염이 확인됨, 나머지 둘이 해당 없음이고, 읽은 값이 46.2 · 0.575 · 28.0이면 내 종이와 같다."))
    + 할_일(2, 편집, "VS Code · 편집기", "열한 건의 대조를 훑는다",
          글("사례마다 「대조」 아래를 본다. 「어긋남 없음」이 아니면 에이전트의 답이 호출 기록과 다른 것이다. 아래는 완성 폴더의 결과다. 내 결과와 줄마다 견준다."),
          f'<table class="res"><tr><th>사례</th><th>근거 상태</th><th>확인된 원인</th><th>가설</th><th>대조 어긋남</th></tr>{표}</table>',
          글("에이전트의 답은 돌릴 때마다, 사람마다 조금씩 다를 수 있다. 다르다는 것만으로 틀린 것은 아니다. 다른 사례는 다음 걸음처럼 원인을 찾는다."))
    + 할_일(3, 편집, "VS Code · 편집기", "다른 사례 하나를 골라 까닭을 찾는다",
          차례("그 사례의 「호출 기록」에서 에이전트가 읽은 값을 본다.",
             "<code>온톨로지/그래프.json</code>에서 그 증거의 기준(<code>expect</code>, <code>threshold</code>)을 찾는다.",
             "작업 규칙대로 내가 직접 가려 본다. 에이전트의 답과 내 답 가운데 어느 쪽이 규칙에 맞는가."),
          사진("결과 md와 입력 json을 좌우로 나란히 연 화면."),
          되면("적어 둔다", "규칙과 다르게 나온 사례 번호와 무엇이 다른지를 한 줄 적어 둔다. 8단계에서 쓴다."))
)

# ── 6단계 ────────────────────────────────────────────────────────────
단계.append(
    머리("6단계", "규칙을<br>일부러 건드려 본다",
       "이 폴더의 규칙 파일은 요청을 받아도 바꾸지 않는 것을 정해 두었다. 어긋나는 요청 둘을 보내 Copilot이 어떻게 답하는지 본다.",
       "두 요청이 모두 거절되고, 파일은 바뀌지 않았다")
    + 할_일(1, 채팅, "Copilot 채팅 · 입력 칸 (같은 대화)", "없는 값을 채워 달라고 한다", 요청("6a"),
          사진("Copilot이 입력을 고치지 않고 어느 규칙 때문인지 밝힌 답."))
    + 할_일(2, 채팅, "Copilot 채팅 · 입력 칸 (같은 대화)", "허용 목록을 대신 고쳐 달라고 한다", 요청("6b"))
    + 할_일(3, 편집, "VS Code · 편집기", "규칙 파일에서 그 줄을 찾는다",
          글("<code>.github/copilot-instructions.md</code>를 열어 「하면 안 되는 것」에서 두 답이 든 규칙의 번호를 찾는다."),
          되면("이렇게 되면 된다", "<code>입력/센서_입력.json</code>과 <code>에이전트_정의.json</code>이 바뀌지 않았다. 탐색기에서 파일 이름 옆에 수정 표시(M)가 없다."),
          다르면(("Copilot이 요청대로 고쳐 버렸다", "「방금 고친 것을 되돌려 줘. 이 폴더의 규칙 1번과 6번을 다시 읽어 줘.」라고 보낸다. 되돌려졌는지 파일을 열어 본다.")))
)

# ── 7단계 ────────────────────────────────────────────────────────────
단계.append(
    머리("7단계", "도구를 하나 더 붙여<br>조치 방법을 단다",
       "원인만으로는 현장에서 움직일 수 없다. <code>조치_방법</code> 도구를 붙여 점검마다 절차 번호가 달리게 한다. 4단계와 같은 순서다.",
       "점검 순서에 절차 번호(SOP-…)가 달려 있다")
    + 할_일(1, 편집, "VS Code · 편집기", "허용 목록에 한 줄을 더한다",
          '<div class="tree">"도구": [\n  "원인_후보",\n  "증거_기준",\n  "센서_집계"<b>,</b>\n  <b>"조치_방법"</b>\n],</div>')
    + 할_일(2, 채팅, "Copilot 채팅 · 입력 칸 (같은 대화)", "도구와 규칙 한 줄을 더해 달라고 한다", 요청("7"))
    + 할_일(3, 터미널, "VS Code · 터미널", "열한 건을 다시 돌린다",
          명령("python 에이전트.py"),
          글("아래는 한 번 돌린 결과다."),
          출력("\n".join(화면_줄(r) for r in 넷)),
          글("<code>결과/점검_계획.md</code>에서 S01의 「점검 순서」를 본다. 조치에 <code>SOP-COOL-</code>로 시작하는 절차 번호가 있다. 그 번호가 호출 기록의 <code>조치_방법</code>이 돌려준 것 가운데 있는지 본다."),
          사진("결과 md의 S01 점검 순서. 근거와 조치(절차 번호)가 보인다."),
          다르면(("조치가 비어 있다", "<code>에이전트_정의.json</code>의 작업 규칙이 여덟 줄인지, 허용 목록에 <code>조치_방법</code>이 있는지 본다."),
              ("괄호 안에 「횟수 한도에 닿아 멈춤」이 나온 사례가 있다", "에이전트가 답을 내지 못한 것이다. 그 사례만 한 번 더 돌린다. 예: <code>python 에이전트.py S09</code>")))
)

# ── 8단계 ────────────────────────────────────────────────────────────
어긋난 = [r for r in 끝 if r["대조"]]
단계.append(
    머리("8단계", "아쉬운 곳을<br>되돌려 준다",
       "5단계에서 적어 둔 것을 Copilot에게 되돌려 준다. 「이상해, 고쳐 줘」가 아니라 무엇이, 왜, 어디를, 어디까지인지를 말한다.",
       "고친 뒤의 결과에서 그 문제가 대조에 잡힌다")
    + 할_일(1, 안내, "이 화면", "되돌려 줄 것을 하나 고른다",
          글("5단계에서 적어 둔 것이 있으면 그것으로 한다. 없으면 아래에서 고른다."),
          '<table class="res"><tr><th>거리</th><th>무엇이 문제인가</th></tr>'
          '<tr><td class="nw">근거 상태</td><td>확인됨인 원인이 있는데 근거 상태가 SUPPORTED가 아닌 사례가 있다. 지금 대조는 판정과 값만 보고 근거 상태는 보지 않는다.</td></tr>'
          '<tr><td class="nw">결과의 모양</td><td>결과 md의 호출 기록이 길어서 점검 순서가 눈에 들어오지 않는다.</td></tr></table>')
    + 할_일(2, 채팅, "이 화면의 글 칸 → Copilot 채팅 (같은 대화)", "네 가지를 넣어 쓴다",
          글("무엇이 문제인지, 왜 문제인지, 어디를 고칠지, 건드리지 말 곳. 네 문장이면 된다."),
          '<textarea id="w8" data-draft="w8" placeholder="무엇이 문제인지, 왜 문제인지, 어디를 고칠지, 건드리지 말 곳을 적는다."></textarea>'
          '<div class="wfoot"><button data-copy="w8">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸</span></div>'
          '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary>' + 요청("8") + '</details>')
    + 할_일(3, 터미널, "VS Code · 터미널", "다시 돌려 확인한다",
          명령("python 에이전트.py"),
          글("근거 상태를 고른 경우, 완성 폴더의 결과에서는 아래 두 사례가 대조에 잡혔다."),
          출력("\n".join(f"{r['번호']}  {r['대조'][0]}" for r in 어긋난)),
          사진("Copilot이 에이전트.py의 바뀐 부분을 보여 주는 화면."),
          되면("끝", "<code>도구.py</code>, <code>에이전트.py</code>, <code>결과/점검_계획.json</code>과 <code>.md</code>가 남았다. 받은 <code>완성</code> 폴더와 견주어 본다."))
    + '<section class="sect"><h2>시간이 남으면</h2>'
      '<p><b>멈춤 조건을 줄여 본다.</b> <code>에이전트_정의.json</code>의 <code>최대_횟수</code>를 3으로 바꾸고 <code>python 에이전트.py S01</code>을 돌린다. 괄호 안의 글과 결과가 어떻게 바뀌는지 보고, 값을 원래대로 돌려놓는다.</p>'
      '<p><b>같은 사례를 두 번 돌려 본다.</b> <code>python 에이전트.py S09</code>를 두 번 실행해 근거 상태와 호출 수가 같은지 본다.</p>'
      '<p><b>작업 규칙 한 줄을 바꿔 본다.</b> 「증거가 하나라도 맞음이면 확인됨」으로 바꾸고 열한 건을 다시 돌려, 근거 상태가 바뀐 사례를 센다. 끝나면 원래대로 돌려놓는다.</p></section>'
)

# ── 조립 ─────────────────────────────────────────────────────────────
짧은_제목 = ["오늘 만드는 것과 준비"] + [n.split(". ", 1)[1] for n in 이름들[1:]]
글자 = []
for i, 몸 in enumerate(단계):
    꼬리 = ""
    if i < len(단계) - 1:
        꼬리 += (f'<div class="next"><div><small>다음 단계</small><b>{이름들[i + 1]}</b></div>'
               f'<a data-go="{i + 1}">다음으로 →</a></div>')
    if i > 0:
        꼬리 += f'<a class="back" data-go="{i - 1}">← 이전 단계로</a>'
    글자.append(f'<article class="step">{몸}{꼬리}</article>')

스크립트 = """const KEY='hyd-off-05-2b-';const names=__NAMES__;const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));""".replace("__NAMES__", json.dumps(이름들, ensure_ascii=False))

점 = "".join(f'<i data-go="{i}" title="{e(n)}"></i>' for i, n in enumerate(이름들))
문서 = (
    '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>실습 가이드 · 설비 이상의 원인을 추론하는 에이전트</title>'
    f'<style>{(여기 / "가이드_스타일_길잡이.css").read_text(encoding="utf-8")}</style></head>'
    f'<body><div class="bar"><div class="bar-in"><b>온톨로지 + 센서 값 → 원인 추론 에이전트</b><div class="track">{점}</div><span id="pos"></span></div></div>'
    f'<main class="page">{"".join(글자)}</main><div id="toast"></div><script>{스크립트}</script></body></html>\n'
)
(묶음 / "가이드.html").write_text(문서, encoding="utf-8")
print(f"가이드.html {len(문서):,}자 · 단계 {len(단계)} · 복사 {복사_수} · 사진 자리 {사진_수}")
