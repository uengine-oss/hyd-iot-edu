"""05-2-cause-agent 의 guide.html 을 만든다.

    python3 build_guide.py            guide.html 을 쓴다
    python3 build_guide.py --collect  윤문에 보낼 문장만 record/guide_text.json 에 모은다

- 요청 글은 record/prompts/, 화면에 싣는 실행 결과는 record/runs/ 와 solution/plan/ 에서 읽는다.
- record/guide_polish.json({원문: 윤문})이 있으면 그 문장으로 바꿔 싣는다.
- 스타일은 ../guide.css 에서 읽는다.
"""
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDENT = HERE.parents[4] / "course" / "labs" / "offline" / HERE.name
PROMPTS = HERE / "record" / "prompts"
RUNS = HERE / "record" / "runs"
POLISH_FILE = HERE / "record" / "guide_polish.json"

e = html.escape
shots = 0
copies = 0
collected = []
POLISH = json.loads(POLISH_FILE.read_text(encoding="utf-8")) if POLISH_FILE.exists() else {}


def t(text):
    """가이드에 싣는 문장. 윤문본이 있으면 그것을 쓴다."""
    if text not in collected:
        collected.append(text)
    return POLISH.get(text, text)


CHAT = ("w-chat", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="22" y="3" width="9" height="16" rx="2" fill="#6d28d9"/></svg>')
EDITOR = ("w-code", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="3" y="3" width="8" height="16" rx="2" fill="#1d4ed8"/></svg>')
TERMINAL = ("w-term", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="3" y="13" width="28" height="6" rx="2" fill="#0f766e"/></svg>')
PAGE = ("w-page", '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff"/><rect x="6" y="6" width="22" height="2.5" rx="1" fill="#374151"/><rect x="6" y="11" width="22" height="2.5" rx="1" fill="#374151"/><rect x="6" y="16" width="14" height="2.5" rx="1" fill="#374151"/></svg>')


def task(no, place, place_name, title, *body):
    return (f'<section class="do {place[0]}"><header><em>{no}</em><div><span class="where {place[0]}">{place[1]}{place_name}</span>'
            f'<h2>{t(title)}</h2></div></header><div class="body">{"".join(body)}</div></section>')


def para(*lines):
    return "".join(f"<p>{t(m)}</p>" for m in lines)


def steps(*lines):
    return '<ol class="todo">' + "".join(f"<li><span>{t(m)}</span></li>" for m in lines) + "</ol>"


def prompt(name):
    global copies
    copies += 1
    text = (PROMPTS / f"{name}.txt").read_text(encoding="utf-8").strip()
    return (f'<div class="copy"><div class="copy-top"><span>Copilot에게 보낼 요청</span><button data-copy="c{copies}">복사</button></div>'
            f'<div class="copy-text pre" id="c{copies}">{e(text)}</div>'
            f'<div class="copy-foot">붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸 · 붙여넣고 Enter</div></div>')


def command(text):
    global copies
    copies += 1
    return f'<div class="cmd"><span id="c{copies}">{e(text)}</span><button data-copy="c{copies}">복사</button></div>'


def shot(what):
    global shots
    shots += 1
    return f'<div class="shot"><div><b>화면 {shots}</b><span>{t(what)}</span></div></div>'


def good(title, text):
    return f'<div class="ok"><b>{t(title)}</b>{t(text)}</div>'


def otherwise(*pairs):
    return '<div class="if">' + "".join(f"<div><b>{t(a)}</b>{t(b)}</div>" for a, b in pairs) + "</div>"


def output(text):
    return f'<div class="out">{e(text)}</div>'


def code(text):
    return f'<div class="tree">{text}</div>'


def look_for(*pairs):
    marks = "①②③④⑤"
    return '<div class="find">' + "".join(
        f'<div><i>{marks[i]}</i><p style="margin:0"><b>{t(a)}</b><span>{t(b)}</span></p></div>' for i, (a, b) in enumerate(pairs)) + "</div>"


def table(head, *rows, polish=True):
    f = t if polish else (lambda x: x)
    return ('<table class="res"><tr>' + "".join(f"<th>{f(h)}</th>" for h in head) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{f(c)}</td>" for c in row) + "</tr>" for row in rows) + "</table>")


def head(no, title, what, done):
    return (f'<section class="hero"><div class="no">{no}</div><h1>{t(title)}</h1><p>{t(what)}</p>'
            f'<div class="facts"><div><small>이 단계가 끝나면</small>{t(done)}</div></div></section>')


def line(plan):
    return f"{plan['id']}  {plan['status']}  도구 호출 {len(plan['calls'])}번  대조 어긋남 {len(plan['mismatches'])}건  ({plan['stopped']})"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def explorer(root, *rows):
    """VS Code 탐색기 모양. rows: (깊이, 종류, 이름, 설명, 강조). 폴더 줄을 누르면 접히고 펴진다."""
    out = [f'<div class="xp"><div class="xp-row xp-head"><div class="xp-l">탐색기</div><div class="xp-r">무엇인가</div></div>'
           f'<div class="xp-row xp-root xp-dir" data-d="-1"><div class="xp-l"><i class="chev">⌄</i>{root}</div><div class="xp-r">{t("VS Code로 여는 실습 폴더")}</div></div>']
    for depth, kind, name, text, *flag in rows:
        icon = '<i class="chev">⌄</i>' if kind == "dir" else f'<i class="ic {kind}"></i>'
        cls = "xp-row" + (" xp-dir" if kind == "dir" else "") + (" xp-new" if flag else "")
        mark = '<u>새 파일</u>' if flag else ""
        out.append(f'<div class="{cls}" data-d="{depth}"><div class="xp-l" style="padding-left:{20 + depth * 18}px">{icon}<span>{name}</span>{mark}</div>'
                   f'<div class="xp-r">{t(text)}</div></div>')
    return "".join(out) + "</div>"


two = load(RUNS / "step3_S01.json")[0]
three = load(RUNS / "step4_S01.json")[0]
three_all = load(RUNS / "step4_all.json")
four_all = load(RUNS / "step7_all.json")
final = load(HERE / "solution" / "plan" / "plan.json")

NAMES = ["준비", "1. 자료 해석 확인", "2. 판정 규칙 확정", "3. 도구 2개로 구현", "4. 센서 조회 도구 추가",
         "5. 점검 계획 검증", "6. 규칙 위반 요청 시험", "7. 조치 조회 도구 추가", "8. 실패 사례 개선"]

ORDER = [
    ("자료 해석 확인", "Copilot이 온톨로지와 사례 한 건을 읽고 증거 기준과 비교한 표가 내 계산과 같은지 확인한다"),
    ("판정 규칙 확정", "증거, 원인, 사례를 어떻게 판정할지 네 문장으로 정해 에이전트 설정에 넣고 구현 계획을 받는다"),
    ("도구 2개로 구현", "원인 후보와 증거 기준을 조회하는 도구만으로 에이전트를 만들어 한 건을 실행한다. 센서 값을 읽지 못해 판정이 보류되는 것을 확인한다"),
    ("센서 조회 도구 추가", "허용 목록에 도구를 더해 같은 사례를 다시 실행하고, 열한 건 전체를 실행한다"),
    ("점검 계획 검증", "에이전트의 판정이 센서 값과 기준에 맞는지 대조 항목과 호출 기록으로 사례별로 확인한다"),
    ("규칙 위반 요청 시험", "없는 값을 채워 달라는 요청과 허용 목록을 대신 고쳐 달라는 요청이 거절되는지 확인한다"),
    ("조치 조회 도구 추가", "점검 항목마다 표준 작업 절차 번호가 붙게 하고 열한 건을 다시 실행한다"),
    ("실패 사례 개선", "호출 한도에 걸려 답을 내지 못한 사례의 호출 기록을 근거로 규칙 한 줄을 추가하고 다시 실행한다"),
]

pages = []

# ── 준비 ─────────────────────────────────────────────────────────────
pages.append(
    '<section class="hero"><div class="no">준비</div><h1><small>통합반 오프라인 5회차 · 실습 2</small>'
    + t("설비 이상의 원인을 추론하는<br>에이전트를 만든다") + '</h1><p>'
    + t("경보가 뜬 설비 사례를 받아, 온톨로지에서 원인 후보와 증거 기준을 찾고 센서 집계값과 비교해, 원인마다 확인·가설·해당 없음을 판정하고 점검 순서를 내는 도구 호출형 에이전트를 만든다.")
    + '</p></section>'
    '<section class="sect"><h2>오늘 만드는 것</h2><div class="pipe">'
    f'<div><b>{t("입력")}</b>{t("경보가 뜬 설비 사례 11건. 사례마다 경보 패턴과 센서 집계값이 있다")}</div><span>→</span>'
    f'<div><b>{t("에이전트")}</b>{t("온톨로지에서 원인 후보와 증거 기준을 조회하고, 센서 값과 비교해 판정한다")}</div><span>→</span>'
    f'<div class="made"><b>{t("산출물")}</b>{t("사례별 점검 계획. 원인별 판정, 점검 순서, 조치 절차 번호, 판정의 근거가 된 조회 기록")}</div></div></section>'
    '<section class="sect"><h2>오늘의 순서</h2><ol class="flow">'
    + "".join(f'<li data-go="{i}"><em>{i}</em><b>{t(a)}</b><span>{t(b)}</span></li>' for i, (a, b) in enumerate(ORDER, 1))
    + '</ol></section>'
    '<section class="sect"><h2>받은 폴더의 구성</h2>'
    + explorer("05-2-CAUSE-AGENT",
               (0, "dir", ".github", "Copilot에게 주는 지침을 두는 폴더"),
               (1, "md", "copilot-instructions.md", "Copilot이 이 실습에서 지켜야 할 규칙"),
               (0, "dir", "cases", "에이전트가 진단할 설비 사례"),
               (1, "json", "cases.json", "경보가 발생한 설비 사례 11건과 그때의 센서 측정값"),
               (1, "md", "README.md", "사례 파일을 읽는 법"),
               (0, "dir", "ontology", "설비 고장에 대한 지식"),
               (1, "json", "graph.json", "어떤 경보가 어떤 고장과 원인으로 이어지는지, 무엇으로 확인하고 어떻게 조치하는지를 정리한 지식"),
               (1, "md", "README.md", "지식 파일을 읽는 법"),
               (1, "json", "schema.json", "지식 파일에 쓰는 항목의 종류와 관계를 정한 정의"),
               (0, "dir", "plan", "에이전트가 만든 점검 계획이 저장되는 폴더"),
               (0, "env", ".env", "LLM 서버 접속 정보를 적는 파일"),
               (0, "json", "agent_config.json", "에이전트의 목표, 쓸 수 있는 도구, 판정 규칙을 정하는 설정"),
               (0, "py", "llm_client.py", "LLM 서버에 요청을 보내는 코드"),
               (0, "html", "guide.html", "실습 가이드(이 문서)"),
               (0, "py", "tools.py", "오늘 만든다. 지식과 사례에서 필요한 내용을 찾아 주는 도구", True),
               (0, "py", "agent.py", "오늘 만든다. 도구를 사용해 원인을 판정하고 점검 계획을 만드는 에이전트", True))
    + '</section>'
    '<section class="sect last"><h2>걸음마다 붙은 색</h2><ul class="key">'
    + "".join(f'<li><span class="where {p[0]}">{p[1]}{name}</span>{t(mean)}</li>' for p, name, mean in
              [(CHAT, "Copilot 채팅", "요청을 보내고 답을 읽는다"), (EDITOR, "편집기", "파일을 열어 읽거나 고친다"),
               (TERMINAL, "터미널", "명령을 실행한다"), (PAGE, "이 화면", "읽고 정한다")])
    + '</ul></section>'
    + task(1, EDITOR, "VS Code · 탐색기", "받은 폴더를 VS Code로 연다",
           para("「파일 → 폴더 열기」에서 받은 폴더 <code>05-2-cause-agent</code>를 고른다. 폴더를 신뢰하는지 물으면 신뢰한다고 답한다. 왼쪽 탐색기가 위 표와 같으면 된다."),
           shot("받은 폴더를 연 VS Code. 왼쪽 탐색기에 폴더 넷과 파일 넷이 보인다."))
    + task(2, EDITOR, "VS Code · 탐색기와 편집기", "LLM 서버 접속 정보를 넣는다",
           steps("탐색기에서 <code>.env</code>를 연다.",
                 "수업에서 받은 주소를 <code>OPENAI_BASE_URL=</code> 뒤에, 받은 키를 <code>LLM_API_KEY=</code> 뒤에 적는다. <code>LLM_MODEL=</code> 뒤에는 모델 이름 <code>coding</code>을 적는다. 등호 뒤에 빈칸을 두지 않는다.",
                 "저장한다(Ctrl+S)."),
           good("주의", "API 키는 <code>.env</code>에만 적는다. 채팅이나 다른 파일에 붙여넣지 않는다."))
    + task(3, TERMINAL, "VS Code · 터미널", "LLM 서버에 연결되는지 확인한다",
           para("「터미널 → 새 터미널」을 열고 아래 명령을 실행한다."),
           command("python llm_client.py"),
           good("정상", "첫 줄이 <code>연결됨</code>으로 시작하고, 둘째 줄에 서버가 보낸 인사 한 문장이 나온다."),
           otherwise(("값이 비어 있다고 나온다", "<code>.env</code>에 값을 적은 뒤 저장했는지 확인한다. 탭 이름 옆에 흰 점이 있으면 아직 저장되지 않은 것이다."),
                     ("LLM_API_KEY · LLM_MODEL · OPENAI_BASE_URL이 다르다고 나온다", "문구가 가리키는 줄을 받은 값과 다시 비교한다. 값 앞뒤에 따옴표나 빈칸이 들어갔는지 확인한다. <code>LLM_MODEL</code>은 <code>coding</code>이다."),
                     ("서버에 닿지 못했다 · 강사에게 알린다고 나온다", "내 <code>.env</code>가 아니라 네트워크나 서버 쪽 문제다. 강사에게 화면을 보여 준다.")))
    + task(4, EDITOR, "VS Code · 편집기와 종이", "사례 S01을 직접 판정해 둔다",
           para("이후 단계에서 에이전트의 판정이 맞는지 가리려면 기준이 되는 내 계산이 하나 필요하다."),
           steps("<code>ontology/README.md</code>에서 경보에서 원인과 조치까지 따라가는 경로를 읽는다.",
                 "<code>cases/cases.json</code> 맨 위의 <code>S01</code>에서 CE 30초 평균, VS1 120초 평균, TS4 120초 평균을 찾는다.",
                 "아래 표의 빈칸을 종이에 채운다."),
           '<table class="res"><tr><th>원인 후보</th><th>증거 기준</th><th>S01의 값</th><th>맞음 / 아님</th></tr>'
           '<tr><td rowspan="2">쿨러 핀 오염</td><td>CE 30초 평균이 70 미만</td><td></td><td></td></tr>'
           '<tr><td>VS1 120초 평균이 0.9 미만</td><td></td><td></td></tr>'
           '<tr><td>주변 온도 상승</td><td>TS4 120초 평균이 35 이상</td><td></td><td></td></tr>'
           '<tr><td>팬 구동 불량</td><td>VS1 120초 평균이 0.9 이상</td><td></td><td></td></tr></table>')
)

# ── 1단계 ────────────────────────────────────────────────────────────
pages.append(
    head("1단계", "구현 전에<br>Copilot의 자료 해석을 확인한다",
         "바로 구현을 요청하지 않는다. 먼저 자료를 읽고 S01을 증거 기준과 비교하게 해서, Copilot이 온톨로지를 나와 같게 해석하는지 확인한다. 해석이 다르면 그 위에 만든 코드도 다르게 동작한다.",
         "채팅에 Copilot이 따라간 관계, S01 비교표, 나에게 묻는 질문이 있다. 새로 생긴 파일은 없다.")
    + task(1, CHAT, "Copilot 채팅", "채팅을 열고 모드를 확인한다",
           para("VS Code 오른쪽의 Copilot 채팅을 연다. 입력 칸 아래에 <b>에이전트</b>와 <b>GPT-6 Luna</b>가 선택되어 있는지 확인한다. 다르면 그 글자를 눌러 바꾼다."),
           shot("Copilot 채팅이 열린 VS Code. 입력 칸 아래에 에이전트와 GPT-6 Luna가 보인다."))
    + task(2, CHAT, "Copilot 채팅 · 입력 칸", "아래 요청을 복사해 보낸다", prompt("1"))
    + task(3, CHAT, "Copilot 채팅 · 답", "답에서 세 가지를 확인한다",
           shot("Copilot의 답. 관계를 한 줄씩 적은 부분, S01 비교표, 끝의 질문이 보인다."),
           look_for(("관계 경로", "이상 패턴 → 증상 → 고장 유형 → 원인 → 증거의 순서로 적혀 있다."),
                    ("S01 비교표", "내 계산과 같다. 쿨러 핀 오염의 증거 둘은 맞음(46.2 &lt; 70, 0.575 &lt; 0.9), 나머지 두 원인의 증거는 아님이다."),
                    ("질문", "원인을 「확인됨」으로 볼 조건처럼 규칙에 없는 것은 스스로 정하지 않고 나에게 물었다.")),
           otherwise(("파일이 생겼다", "생긴 파일을 지우고 요청을 다시 보낸다."),
                     ("비교표가 내 계산과 다르다", "어느 칸이 어떻게 다른지 구체적으로 알려 준다. 예: 「팬 구동 불량의 기준은 0.9 이상인데 값은 0.575야.」")))
)

# ── 2단계 ────────────────────────────────────────────────────────────
pages.append(
    head("2단계", "판정 규칙을 정하고<br>구현 계획을 받는다",
         "Copilot이 물은 것은 이 폴더의 규칙 파일이 일부러 비워 둔 다섯 가지다. 내가 정한 문장은 코드가 아니라 <code>agent_config.json</code>의 <code>rules</code>에 들어가고, 에이전트는 실행할 때 이 문장을 지시로 읽는다.",
         "<code>rules</code>가 세 줄에서 일곱 줄이 되고, 채팅에 구현 계획이 있다.")
    + task(1, PAGE, "이 화면", "비어 있는 다섯 가지와 오늘 쓸 답을 읽는다",
           table(("정해져 있지 않은 것", "오늘 정하는 답"),
                 ("값이 없거나 관측이 부족한 증거, 신선하지 않은 사례", "증거의 <code>result</code>를 <b>NOT_CHECKED</b>로 둔다"),
                 ("원인의 <code>verdict</code>", "증거가 모두 MATCH이면 <b>CONFIRMED</b>, 모두 NO_MATCH이면 <b>RULED_OUT</b>, 그 밖은 <b>HYPOTHESIS</b>"),
                 ("증거가 등록되지 않은 원인", "<b>HYPOTHESIS</b>로 둔다"),
                 ("사례의 <code>status</code>", "CONFIRMED가 하나라도 있으면 <b>SUPPORTED</b>, 모두 RULED_OUT이면 <b>UNSUPPORTED</b>, 그 밖은 <b>UNKNOWN</b>"),
                 ("점검 순서(<code>checks</code>)", "확인하지 못한 값의 재확인 → CONFIRMED인 원인 → HYPOTHESIS인 원인. RULED_OUT은 넣지 않는다")),
           para("다르게 정하려면 아래 요청의 문장을 고쳐서 보낸다."))
    + task(2, CHAT, "Copilot 채팅 · 입력 칸 (같은 대화)", "규칙을 보내고 구현 계획을 받는다", prompt("2"))
    + task(3, EDITOR, "VS Code · 편집기와 채팅", "두 가지를 확인한다",
           steps("<code>agent_config.json</code>을 연다. <code>rules</code>가 세 줄에서 일곱 줄로 늘었다.",
                 "채팅의 계획에 에이전트가 사례마다 하는 다섯 가지(지시, 도구 실행, 호출 기록, 멈춤, 대조)가 모두 있다."),
           shot("Copilot의 구현 계획. tools.py와 agent.py에 둘 것이 나뉘어 적혀 있다."),
           otherwise(("tools.py나 agent.py가 이미 생겼다", "두 파일을 지우고 「계획만 말해 줘」라고 다시 보낸다."),
                     ("계획 끝에 추가 질문이 있다", "읽고 답한다. 판단하기 어려우면 「이 폴더의 규칙대로, 규칙에 없으면 가장 단순하게」라고 답한다.")))
)

# ── 3단계 ────────────────────────────────────────────────────────────
pages.append(
    head("3단계", "도구 2개로 구현하고<br>S01 한 건을 실행한다",
         "지금 허용 목록의 도구는 <code>find_causes</code>와 <code>get_evidence</code> 둘이다. 센서 값을 읽는 도구가 없는 에이전트가 무엇을 내는지 먼저 확인한다.",
         "<code>tools.py</code>와 <code>agent.py</code>가 있고, <code>plan</code> 폴더에 S01의 점검 계획이 있다.")
    + task(1, CHAT, "Copilot 채팅 · 입력 칸 (같은 대화)", "구현을 요청한다", prompt("3"),
           para("파일 생성을 허용할지 물으면 허용한다. 끝나면 탐색기에 <code>tools.py</code>와 <code>agent.py</code>가 생긴다."))
    + task(2, TERMINAL, "VS Code · 터미널", "S01 한 건을 실행한다",
           command("python agent.py S01"),
           para("몇 초 뒤 한 줄이 출력된다. 아래는 한 번 실행한 예시 출력이다. 호출 수와 괄호 안의 문구는 실행마다 다를 수 있다."),
           output(line(two)))
    + task(3, EDITOR, "VS Code · 편집기", "<code>plan/plan.md</code>에서 세 곳을 확인한다",
           look_for(("근거 상태가 UNKNOWN이다", "세 원인이 모두 HYPOTHESIS이고 증거는 모두 NOT_CHECKED다. 센서 값을 읽을 도구가 없기 때문이다."),
                    ("호출 기록", f"에이전트가 호출한 도구가 순서대로 적혀 있다. 예시 실행에서는 {' → '.join(c['tool'] for c in two['calls'])}였다. 허용 목록에 없는 <code>read_sensor</code>는 없다."),
                    ("대조", f"답에 호출 기록에 없는 내용이 있으면 여기에 적힌다. 예시 실행에서는 조치 칸에 매뉴얼의 절 번호를 적어 「{e(two['mismatches'][0])}」가 {len(two['mismatches'])}건 나왔다.")),
           shot("plan/plan.md의 미리 보기. S01의 근거 상태, 대조, 호출 기록이 보인다."),
           otherwise(("오류가 나고 멈춘다", "터미널의 마지막 몇 줄을 복사해 채팅에 붙이고 「이 오류를 고쳐 줘」라고 보낸다."),
                     ("근거 상태가 SUPPORTED로 나온다", "읽지 않은 값을 지어낸 것이다. 대조에 무엇이 적혔는지 확인하고, 그대로 두고 다음 단계로 간다.")))
)

# ── 4단계 ────────────────────────────────────────────────────────────
pages.append(
    head("4단계", "센서 값을 조회하는<br>도구를 추가한다",
         "허용 목록은 사람이 고친다. 내가 목록에 <code>read_sensor</code>를 추가하고, Copilot에게 그 도구의 구현을 요청한다.",
         "S01의 근거 상태가 SUPPORTED로 바뀌고, 열한 건의 점검 계획이 있다.")
    + task(1, EDITOR, "VS Code · 편집기", "허용 목록에 도구를 추가한다",
           para("<code>agent_config.json</code>의 <code>tools</code>를 아래처럼 고치고 저장한다. 앞줄 끝의 쉼표를 빠뜨리지 않는다."),
           code('"tools": [\n  "find_causes",\n  "get_evidence"<b>,</b>\n  <b>"read_sensor"</b>\n],'))
    + task(2, CHAT, "Copilot 채팅 · 입력 칸 (같은 대화)", "도구 구현을 요청한다", prompt("4"))
    + task(3, TERMINAL, "VS Code · 터미널", "S01을 다시 실행하고, 이어서 열한 건을 실행한다",
           command("python agent.py S01"),
           output(line(three)),
           para("S01이 SUPPORTED로 바뀌었으면 사례 번호 없이 한 번 더 실행한다. 열한 건에 1분쯤 걸린다."),
           command("python agent.py"),
           shot("터미널에 사례 열한 건이 한 줄씩 출력된 화면."),
           otherwise(("JSON 오류가 난다", "<code>agent_config.json</code>에서 쉼표와 따옴표를 확인한다."),
                     ("S01이 여전히 UNKNOWN이다", "<code>plan/plan.md</code>의 호출 기록에 <code>read_sensor</code>가 있는지 확인한다. 없으면 허용 목록을 고친 뒤 저장했는지 확인한다.")))
)

# ── 5단계 ────────────────────────────────────────────────────────────
KOREAN = {"CONFIRMED": "확인", "HYPOTHESIS": "가설"}
rows = "".join(
    f'<tr><td class="nw">{r["id"]}</td><td>{r["status"]}</td>'
    f'<td>{", ".join(c["name"] for c in r["causes"] if c.get("verdict") == "CONFIRMED") or "—"}</td>'
    f'<td>{", ".join(c["name"] for c in r["causes"] if c.get("verdict") == "HYPOTHESIS") or "—"}</td>'
    f'<td>{len(r["mismatches"])}</td></tr>' for r in three_all)
status_miss = next(r for r in three_all if any(m.startswith("status") for m in r["mismatches"]))
verdict_miss = next(r for r in three_all if any("verdict" in m and not m.startswith("status") for m in r["mismatches"]))
pages.append(
    head("5단계", "점검 계획을<br>값과 기준으로 검증한다",
         "에이전트의 판정이 맞는지는 사람이 확인한다. 직접 계산해 둔 S01부터 비교하고, 나머지는 대조 항목과 호출 기록으로 확인한다. 이 단계에서는 Copilot에게 요청하지 않는다.",
         "어느 사례의 판정이 규칙과 어긋났는지, 무엇이 어긋났는지 적어 둔 메모가 있다.")
    + task(1, EDITOR, "VS Code · 편집기", "S01을 내 계산과 비교한다",
           para("<code>plan/plan.md</code>의 S01을 본다. 쿨러 핀 오염이 확인된 원인, 나머지 둘이 해당 없음이고, 읽은 값이 46.2 · 0.575 · 28.0이면 내 계산과 같다."))
    + task(2, EDITOR, "VS Code · 편집기", "열한 건의 대조 항목을 확인한다",
           para("사례마다 「대조」 아래를 본다. 「어긋남 없음」이 아니면 에이전트의 답이 호출 기록이나 판정 규칙과 다른 것이다. 아래는 예시 실행의 결과다. 내 결과와 사례별로 비교한다."),
           f'<table class="res"><tr><th>사례</th><th>근거 상태</th><th>확인된 원인</th><th>가설</th><th>대조 어긋남</th></tr>{rows}</table>',
           para("에이전트의 답은 실행마다 조금씩 다를 수 있으므로 표와 달라도 오류는 아니다. 판정이 맞는지는 다음 걸음처럼 값과 기준으로 확인한다."))
    + task(3, EDITOR, "VS Code · 편집기", "대조에 걸린 사례 하나의 원인을 찾는다",
           para("예시 실행에서는 대조에 세 종류가 나왔다."),
           table(("대조에 적힌 것", "뜻", "예"),
                 ("호출 기록에 없는 절차 번호", "조치 칸에 도구가 돌려주지 않은 번호를 적었다. 조치를 조회하는 도구가 아직 없어 매뉴얼의 절 번호를 대신 적은 것이다", "S01"),
                 ("verdict가 증거의 result와 다르다", "증거 판정은 맞게 했으나 원인의 판정을 규칙과 다르게 냈다", f'{verdict_miss["id"]}'),
                 ("status가 원인의 verdict와 다르다", "원인 판정은 했으나 사례의 근거 상태를 규칙과 다르게 냈다", f'{status_miss["id"]}')),
           steps("대조에 걸린 사례 하나를 골라, 그 사례의 「호출 기록」에서 에이전트가 읽은 값을 확인한다.",
                 "<code>ontology/graph.json</code>에서 그 증거의 기준(<code>expect</code>, <code>threshold</code>)을 찾는다.",
                 "<code>agent_config.json</code>의 <code>rules</code>대로 직접 판정한다. 에이전트의 답과 내 판정 중 어느 쪽이 규칙에 맞는지 확인한다."),
           shot("plan/plan.md와 cases/cases.json을 좌우로 나란히 연 화면."),
           good("메모", "규칙과 다르게 나온 사례 번호와 무엇이 달랐는지를 한 줄로 적어 둔다."))
)

# ── 6단계 ────────────────────────────────────────────────────────────
pages.append(
    head("6단계", "규칙에 어긋나는 요청을<br>보내 본다",
         "이 폴더의 규칙 파일에는 요청을 받아도 하지 않는 일이 정해져 있다. 규칙에 어긋나는 요청 둘을 보내 Copilot이 어떻게 답하는지 확인한다.",
         "두 요청이 모두 거절되고, 파일은 바뀌지 않았다.")
    + task(1, CHAT, "Copilot 채팅 · 입력 칸 (같은 대화)", "없는 센서 값을 채워 달라고 요청한다", prompt("6a"),
           shot("Copilot이 사례 파일을 고치지 않고 어느 규칙 때문인지 밝힌 답."))
    + task(2, CHAT, "Copilot 채팅 · 입력 칸 (같은 대화)", "허용 목록을 대신 고쳐 달라고 요청한다", prompt("6b"))
    + task(3, EDITOR, "VS Code · 편집기", "규칙 파일에서 근거가 된 항목을 찾는다",
           para("<code>.github/copilot-instructions.md</code>를 열어 「하면 안 되는 것」에서 두 답이 근거로 든 항목의 번호를 찾는다."),
           good("정상", "<code>cases/cases.json</code>과 <code>agent_config.json</code>이 바뀌지 않았다. 탐색기의 파일 이름 옆에 수정 표시(M)가 없다."),
           otherwise(("Copilot이 요청대로 고쳤다", "「방금 고친 것을 되돌려 줘. 이 폴더의 규칙 1번과 6번을 다시 읽어 줘.」라고 보낸다. 되돌려졌는지 파일을 열어 확인한다.")))
)

# ── 7단계 ────────────────────────────────────────────────────────────
limit = [r for r in four_all if r["stopped"].startswith("횟수")]
pages.append(
    head("7단계", "조치 방법을 조회하는<br>도구를 추가한다",
         "원인만으로는 현장에서 조치할 수 없다. <code>get_actions</code> 도구를 추가해 점검 항목마다 표준 작업 절차 번호가 붙게 한다. 순서는 4단계와 같다.",
         "점검 순서에 절차 번호(SOP-…)가 붙어 있다.")
    + task(1, EDITOR, "VS Code · 편집기", "허용 목록에 도구를 추가한다",
           code('"tools": [\n  "find_causes",\n  "get_evidence",\n  "read_sensor"<b>,</b>\n  <b>"get_actions"</b>\n],'))
    + task(2, CHAT, "Copilot 채팅 · 입력 칸 (같은 대화)", "도구 구현과 규칙 한 줄 추가를 요청한다", prompt("7"))
    + task(3, TERMINAL, "VS Code · 터미널", "열한 건을 다시 실행한다",
           command("python agent.py"),
           para("아래는 예시 실행의 출력이다."),
           output("\n".join(line(r) for r in four_all)),
           para("<code>plan/plan.md</code>에서 S01의 「점검 순서」를 본다. 조치에 <code>SOP-COOL-</code>로 시작하는 절차 번호가 있다. 그 번호가 호출 기록의 <code>get_actions</code>가 돌려준 것 가운데 있는지 확인한다."),
           shot("plan/plan.md의 S01 점검 순서. 근거와 조치(절차 번호)가 보인다."),
           otherwise(("조치가 비어 있다", "<code>agent_config.json</code>의 <code>rules</code>가 여덟 줄인지, 허용 목록에 <code>get_actions</code>가 있는지 확인한다."),
                     ("괄호 안에 「횟수 한도에 닿아 멈춤」이 나온 사례가 있다", f"에이전트가 호출 한도 안에 답을 내지 못한 것이다. 예시 실행에서도 {', '.join(r['id'] for r in limit)}이 그랬다. 그대로 두고 8단계로 간다.")))
)

# ── 8단계 ────────────────────────────────────────────────────────────
s03_before = limit[0]
s03_after = next(r for r in final if r["id"] == s03_before["id"])
extra = [c for c in s03_before["calls"] if c["tool"] == "read_sensor" and isinstance(c["args"], dict) and c["args"].get("tag") == "TS1"]
pages.append(
    head("8단계", "실패한 사례의 원인을 찾아<br>규칙으로 고친다",
         "「이상해, 고쳐 줘」로는 고쳐지지 않는다. 호출 기록에서 원인을 찾고, 무엇이 문제인지, 무엇을 어디에 더할지, 건드리지 말 곳이 어디인지를 구체적으로 전달한다.",
         "호출 한도에 걸렸던 사례가 답을 낸다.")
    + task(1, EDITOR, "VS Code · 편집기", "호출 한도에 걸린 사례의 호출 기록을 읽는다",
           para(f"<code>plan/plan.md</code>에서 괄호 안이 「횟수 한도에 닿아 멈춤」인 사례의 「호출 기록」을 본다. 예시 실행에서는 {s03_before['id']}이 도구를 {len(s03_before['calls'])}번 호출하고도 답을 내지 못했다."),
           look_for(("필요한 조회는 끝났다", "원인 후보, 증거 기준, 증거가 쓰는 센서 값은 앞쪽 호출에서 모두 읽었다."),
                    ("증거에 없는 값을 계속 읽었다", f"그 뒤 증거 기준에 없는 태그 TS1을 구간만 바꿔 가며 {len(extra)}번 더 읽었다. 인자가 매번 달라 같은 호출의 반복으로 잡히지 않았다."),
                    ("고칠 곳은 규칙이다", "코드의 오류가 아니라, 무엇을 읽어도 되는지를 규칙이 정하지 않은 것이다.")),
           para("내 실행에서 한도에 걸린 사례가 없으면, 5단계에서 적어 둔 사례로 같은 방법을 적용한다."))
    + task(2, CHAT, "이 화면의 글 칸 → Copilot 채팅 (같은 대화)", "원인과 고칠 내용을 적어 보낸다",
           para("무엇이 문제인지, 근거가 무엇인지, 무엇을 어디에 더할지, 건드리지 말 곳이 어디인지를 적는다."),
           '<textarea id="w8" data-draft="w8" placeholder="무엇이 문제인지, 근거가 무엇인지, 무엇을 어디에 더할지, 건드리지 말 곳이 어디인지를 적는다."></textarea>'
           '<div class="wfoot"><button data-copy="w8">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸</span></div>'
           '<details><summary>글이 막힐 때 참고할 요청</summary>' + prompt("8") + '</details>')
    + task(3, TERMINAL, "VS Code · 터미널", "다시 실행해 확인한다",
           command("python agent.py"),
           para("아래는 규칙 한 줄을 더한 뒤의 예시 출력이다."),
           output("\n".join(line(r) for r in final)),
           look_for((f"{s03_after['id']}이 답을 냈다", f"도구 호출이 {len(s03_before['calls'])}번에서 {len(s03_after['calls'])}번으로 줄었고 판정이 나왔다."),
                    ("새 어긋남이 드러났다", f"답이 나오자 대조에 「{e(s03_after['mismatches'][0])}」가 잡혔다. 판정 자체는 아직 규칙과 다르다는 뜻이다."),
                    ("대조는 계속 본다", "규칙을 고칠 때마다 대조 항목이 어떻게 바뀌는지로 효과를 확인한다.")),
           shot("규칙을 더한 뒤 다시 실행한 터미널. 열한 건이 모두 답을 냈다."))
    + '<section class="sect"><h2>시간이 남으면</h2>'
    + para("<b>호출 한도를 줄여 본다.</b> <code>agent_config.json</code>의 <code>max_turns</code>를 3으로 바꾸고 <code>python agent.py S01</code>을 실행한다. 출력과 점검 계획이 어떻게 바뀌는지 확인하고 값을 되돌린다.",
           "<b>같은 사례를 두 번 실행한다.</b> <code>python agent.py S09</code>를 두 번 실행해 근거 상태와 호출 수가 같은지 확인한다.",
           "<b>판정 규칙 한 줄을 바꾼다.</b> 원인의 verdict 규칙을 「증거가 하나라도 MATCH이면 CONFIRMED」로 바꾸고 열한 건을 다시 실행해, 근거 상태가 바뀐 사례를 센다. 끝나면 되돌린다.")
    + '</section>'
)

if "--collect" in sys.argv:
    (HERE / "record" / "guide_text.json").write_text(json.dumps(collected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"문장 {len(collected)}개 · {sum(map(len, collected)):,}자")
    sys.exit(0)

# ── 조립 ─────────────────────────────────────────────────────────────
parts = []
for i, body in enumerate(pages):
    tail = ""
    if i < len(pages) - 1:
        tail += (f'<div class="next"><div><small>다음 단계</small><b>{NAMES[i + 1]}</b></div>'
                 f'<a data-go="{i + 1}">다음으로 →</a></div>')
    if i > 0:
        tail += f'<a class="back" data-go="{i - 1}">← 이전 단계로</a>'
    parts.append(f'<article class="step">{body}{tail}</article>')

SCRIPT = """const KEY='hyd-off-05-2c-';const names=__NAMES__;const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
document.querySelectorAll('.xp-dir').forEach(r=>r.addEventListener('click',()=>{const d=+r.dataset.d;const shut=r.classList.toggle('shut');let n=r.nextElementSibling;while(n&&+n.dataset.d>d){if(shut){n.hidden=true}else{n.hidden=false;n.classList.remove('shut')}n=n.nextElementSibling}}));
go(location.hash.slice(1));""".replace("__NAMES__", json.dumps(NAMES, ensure_ascii=False))

dots = "".join(f'<i data-go="{i}" title="{e(n)}"></i>' for i, n in enumerate(NAMES))
doc = (
    '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>실습 가이드 · 설비 이상의 원인을 추론하는 에이전트</title>'
    f'<style>{(HERE.parent / "guide.css").read_text(encoding="utf-8")}</style></head>'
    f'<body><div class="bar"><div class="bar-in"><b>5회차 실습 2 · 원인 추론 에이전트</b><div class="track">{dots}</div><span id="pos"></span></div></div>'
    f'<main class="page">{"".join(parts)}</main><div id="toast"></div><script>{SCRIPT}</script></body></html>\n'
)
(STUDENT / "guide.html").write_text(doc, encoding="utf-8")
print(f"guide.html {len(doc):,}자 · 단계 {len(pages)} · 복사 {copies} · 사진 자리 {shots} · 윤문 적용 {sum(1 for c in collected if c in POLISH)}/{len(collected)}")
