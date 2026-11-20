# 1회차 실습 06 전체과정관찰(두 과정 공통, 2026-11 새 포털 판)의 큐 JSON을 확정 대본에서 만든다. 손으로 고치지 않는다.
#   python3 통합_01_06_전체과정관찰_큐만들기.py [<대본.md>]  → 같은 폴더의 통합_01_06_전체과정관찰_큐.json
#   python3 통합_01_06_전체과정관찰_큐만들기.py --고르기 <처음 큐>-<끝 큐> <출력.json>  → 그 범위(차례 기준)의 큐만 담은 사본(git 밖에 둔다)
#     대표 구간(영상 길 14)처럼 구간 일부만 찍을 때 쓴다. take.mjs는 고른 구간의 모든 큐에 음성이 있어야 녹화하므로, 산 큐만 담은 사본을 준다.
#     조작이 같아서 전체 큐로 통과한 리허설 표시가 그대로 맞는다.
#   대본을 주지 않으면 산출물/통합반/실습/01회차/대본/06_실습_전체과정관찰.md(실전반 파일과 제목 줄만 다르다)를 읽는다.
# 대본 「## 절」 하나가 구간 하나이고, 표의 한 줄(| vNNNN | 발화 | 조작 |)이 큐 하나다. 글은 발화 칸 그대로, 조작은 아래 표(OPS), 쉼(gap, 초)은 영상 V-14.
# 조작 형식은 촬영도구/segs/map.mjs 머리말: [조작, 대상, 시점]. 시점은 {'at': '대사 속 구절'}(그 구절이 시작하는 글자 비율 — map.mjs가 큐 시작 + 길이 × 비율 − 300ms에 한다)
#   이거나 생략(앞 조작이 끝나면 바로). wait · settle은 시점이 없다. 대상은 길뚫기(2026-11-17, main f805fd43 포털 DOM)로 찾았다.
# 녹화 모듈은 촬영도구/segs/one06.mjs(→ map.mjs). 영상 V-13: 추천안 이름 · 후보 비교 4번 줄 · 펼친 가지 않은 단계 이름 · 효과 확인의 설비 시간 괄호는
#   대본과 같은지 wait(정확한 글)로 확인한다 — 다르면 리허설 · 녹화가 그 큐에서 멈추고, 그때는 대본의 그 큐 말을 바꾼다.
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PICK = sys.argv[2:4] if sys.argv[1:2] == ['--고르기'] else None
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not PICK else ROOT / 'workspace/강의제작/산출물/통합반/실습/01회차/대본/06_실습_전체과정관찰.md'
OUT = HERE / '통합_01_06_전체과정관찰_큐.json'
VOICE, MODEL = 'tlxL9ilynpbOVf9sZXKh', 'eleven_v4'      # 영상 V-4
# 2026-11-20: v0614(따로 뽑는 까닭)는 고장 유형 · 원인 줄이 보이는 v0617 뒤로 옮겼다(적대 검토 지적 2)
ORDER = ([f'v06{n:02d}' for n in range(1, 13)] + ['v0658', 'v0613', 'v0615', 'v0616', 'v0617', 'v0614'] + [f'v06{n:02d}' for n in range(18, 36)] + ['v0656']
         + [f'v06{n:02d}' for n in range(38, 53)] + ['v0657', 'v0654', 'v0655', 'v0659'])
GAP_JOIN, GAP_CUE, GAP_RESULT, GAP_SEG = 0.6, 1.3, 2.0, 2.3      # 영상 V-14 실습 값(잇기 · 큐 사이 · 조작 결과가 뜬 뒤 · 구간이 바뀌는 곳)


def T(css, **k): return dict(css=css, **k)
def at(s): return [{'at': s}] if s else []
def P(t, s=None): return ['point', t, *at(s)]
def C(t, s=None): return ['click', t, *at(s)]
def SEL(t, label, s=None): return ['select', t, label, *at(s)]
def SC(t, s=None): return ['scroll', t, *at(s)]
def W(t, secs=15): return ['wait', t, secs]
def LONG(t, secs): return ['wait', {**t, 'long': True}, secs]      # 일부러 기다리는 자리(6초 넘어도 리허설 실패가 아니다)
def SETTLE(secs=10): return ['settle', None, secs]
def CY(i): return {'cy': i}
def BELOW(css, **k): return T(css, anchor='center', dy=22, **k)       # 누르지 않는 단추는 바로 밑 빈자리를 짚는다(촬영준비 길 4 — 마우스 올림 색)
def ABOVE(css, **k): return T(css, anchor='center', dy=-18, **k)      # 밑에 다른 글이 붙은 단추는 바로 위 끝을 짚는다(화살표 몸통은 그 단추 위에 놓인다)


STAGE = lambda n: T('#mainStages a.stat', nth=n - 1)
LABEL = lambda n: T(f'#mainStages a.stat:nth-child({n}) .stat-label')
HERO = '#mainHero'
ITEM = lambda key: f'#manualItems [data-item="{key}"]'
FM = ITEM('know:failure_modes:fm:cooler-cooling-loss')
VS_OK = ITEM('know:evidence:evd:cooler-fouling-vs1-normal')
VS_HI = ITEM('know:evidence:evd:fan-drive-vibration-high')
PANE = lambda key: f'#manualPanes [data-pane="{key}"]'
U = lambda n: f'#units [data-asset="HYD-0{n}"]'
RISE = '#labFollow li[data-step="rise"] .lv-note'
SHEET = 'dialog[open] [data-cr-sheet-body]'
OPT = lambda n: f'{SHEET} table.opts tbody tr:nth-child({n})'
STEP = lambda name: T('#instRecord [data-cr-steps] .step-title', exact=name)
SUB = lambda has, **k: T('#instRecord [data-cr-steps] .step-sub', contains=has, **k)
SKIP = '#instRecord details.cr-skipped .fold-body p'

OPS = {
 # 포털 홈 — 시작 상태 확인(처리 건 0건). 화살표는 위 막대 「홈」 오른쪽 빈자리(one06.mjs의 rest)
 'v0601': [W(T('#mainStages a.stat:nth-child(4) .stat-value', contains='0건 처리 완료'), 20), W(T('#mainStages a.stat:nth-child(3) .stat-value', contains='0건 진행 중'), 5)],
 # 홈에서 보는 목표와 방향
 'v0603': [P(T('#healthDots', anchor='center', dy=14), '왼쪽 아래를')],
 'v0604': [P(T('#view-main .page-head p'), '맨 위 한 줄에는')],
 'v0605': [P(T(f'{HERO} svg.m-hero-svg', anchor='center'), '아래 그림은'), P(T(f'{HERO} text.m-zone', exact='OT · 현장 설비'), '왼쪽 설비에서'),
           P(T(f'{HERO} text.m-zone', exact='값이 지나는 길'), '가운데를'), P(T(f'{HERO} g.m-agent text.m-agent-s'), '오른쪽 AI')],
 'v0606': [P(T(f'{HERO} g.m-node', contains='증상 · 유온 상승', anchor='left'), 'AI 둘레의'),      # 증상 점은 글 끝 오른쪽이 아래 「원인 · 쿨러 핀 오염」을 덮어 점 왼쪽을 짚는다
           P(T(f'{HERO} g.m-node text', exact='고장 유형 · 냉각 상실'), '점들은'),
           P(T(f'{HERO} g.m-node text', exact='원인 · 쿨러 핀 오염'), 'AI가 아는')],
 'v0607': [P(T(f'{HERO} text.m-loop-t', exact='사람이 승인한 조치'), '거꾸로 설비'), P(T(f'{HERO} path.m-loop', pathAt=0.97), '위에 있는 점선'),
           P(T(f'{HERO} text.m-loop-t', exact='사람이 승인한 조치'), '사람이 승인한'), P(T(f'{HERO} text.m-zone', exact='값이 지나는 길'), '올라가는 길과'),
           P(T(f'{HERO} path.m-loop', pathAt=0.4), '내려가는 길,')],
 'v0608': [SC(T('#mainStages', bottom=12), '아래 네 칸은'), P(LABEL(1), '지식을 넣어'), P(LABEL(2), '설비에 고장이'), P(LABEL(3), 'AI의 판단과'), P(LABEL(4), '결과가 남죠'),
           P(T('#menuList summary[data-menu="knowledge"] > span'), '지식,'), P(T('#menuList summary[data-menu="plant"] > span'), '유압 설비,'),
           P(T('#menuList a[data-menu="instances"] > span', exact='처리 건'), '처리 건이')],
 # 매뉴얼을 지식으로 넣기 — 문서 등록
 'v0609': [P(LABEL(1), '이런 지식은'),      # 앞 구간이 왼쪽 메뉴 「처리 건」을 짚고 끝나, 그대로 두면 그 줄이 마우스 올림 색으로 20초쯤 남는다 — 지식을 모아 두는 첫 칸으로 옮긴다
           P(T('#mainStages a.stat[data-go-tab="knowledge"] .go'), '첫 칸 아래'), C(T('#mainStages a.stat[data-go-tab="knowledge"] .go'), '누르시면'),
           W(T('#providedDocs button.row[data-provided="HM-8_cooler-fan-manual.md"]'))],
 'v0610': [P(T('#manualSteps .phase', exact='올리기'), '올리기,'), P(T('#manualSteps .phase', exact='AI 추출'), 'AI 추출,'), P(T('#manualSteps .phase', exact='검토'), '검토,'),
           P(T('#manualSteps .phase', exact='적재'), '적재 순서')],
 'v0611': [P(ABOVE('#manualPick button[data-pick-mode="file"]'), '여기, 내 파일'), P(T('#providedDocs .doc-prov', anchor='margin'), '그 아래 목록'),
           P(T('#providedDocs button.row[data-provided="HM-8_cooler-fan-manual.md"] .row-title'), '쿨러 팬 정비'),
           C(T('#providedDocs button.row[data-provided="HM-8_cooler-fan-manual.md"] .row-title', anchor='after'), '누르면'), W(T('#manualAgentExtract'))],      # 누르기 기본 자리(요소 오른쪽 끝)는 줄 끝 「›」라 바로 옆 「원문 보기」를 누르는 것처럼 보인다 — 짚던 제목 끝에서 누른다
 'v0612': [P(T('#manualResult .result-label', exact='이미 적재된 문서', anchor='margin'), '이미 적재된'), P(T('#manualStageNote', anchor='margin'), '이 매뉴얼은'),
           C(T('#manualAgentExtract', anchor='center'), '누를게요')],
 # 추출을 기다리는 동안 흐르는 단계 줄(.doc-trail — 기다리는 동안은 실시간 칸 맨 위, 결과가 뜨면 결과 요약 밑으로 같은 칸이 옮겨진다).
 # 결과가 뜨면 줄 자리가 바뀌므로 둘째 줄은 결과를 기다린 뒤 짚는다(결과가 늦으면 그만큼 늦게 짚는다)
 # 단계 줄의 이름은 포털 화면 글 고침(저장된 결과를 말하는 글을 없앰)으로 바뀌므로 이름이 아니라 단계 자리(data-step)로 짚는다
 'v0658': [P(T('.doc-trail li[data-step="open"] .line-text > b'), '단계가 하나씩'), W(T('#manualReview'), 20),
           P(T('.doc-trail li[data-step="verify"] .line-text > b'), '대조하는')],
 'v0613': [P(T('#manualReview .result-main'), '결과가 나왔습니다')],      # 그 밑 줄(#manualAgentStatus)은 짚지 않는다 — 포털에서 없어질 글이고 대본도 말하지 않는다(영상 V-13)
 'v0615': [SC(T('#manualReview .doc-review .doc-review-bar', top=70), '밑으로 내려'), P(T(ITEM('proc:SOP-FAN-11') + ' .row-title'), '처음 보이는'),
           P(T(ITEM('proc:SOP-FAN-11') + ' .row-meta', phrase='쿨러 냉각 성능 상실'), '줄마다'),
           P(T('#manualReview button[data-review-kind="know"]'), '목록 위에 있는'), C(T('#manualReview button[data-review-kind="know"]', anchor='center'), '누르면'),
           W(T(FM))],
 'v0616': [P(T(FM + ' .row-title'), '맨 위 줄을'), P(T(FM + ' .row-meta', phrase='유온 상승, 냉각 효율 저하'), '밑에 작은'),
           P(T(FM + ' .row-title'), '맨 위의 쿨러'), P(T(FM + ' .row-meta', phrase='고장 유형'), '이론에서 본')],
 'v0617': [P(T(ITEM('know:causes:cause:cooler-fin-fouling') + ' .row-title'), '아래 세 줄은'), P(T(ITEM('know:causes:cause:ambient-temperature-rise') + ' .row-title'), '일으킬 수'),
           P(T(ITEM('know:causes:cause:fan-drive-fault') + ' .row-title'), '원인입니다')],
 # 고장 유형 한 줄과 원인 세 줄이 따로 놓인 화면에서 「이렇게 따로따로」를 말한다(2026-11-20에 v0613 뒤에서 옮김 — 말은 그대로)
 'v0614': [P(T(FM + ' .row-title'), '무슨 고장인지'), P(T(ITEM('know:causes:cause:cooler-fin-fouling') + ' .row-title'), '그 고장의 원인을')],
 'v0618': [P(T(PANE('know:failure_modes:fm:cooler-cooling-loss') + ' blockquote'), '그 원문이')],
 'v0619': [SC(T(VS_OK, top=330), '조금 내리면'), P(T(VS_OK + ' .row-title'), '팬 진동 줄이'), P(T(VS_HI + ' .row-title'), '둘 있는데'),
           P(T(VS_OK + ' .row-title'), '위쪽,'), C(T(VS_OK, anchor='center'), '누르시면'),
           W(T(PANE('know:evidence:evd:cooler-fouling-vs1-normal') + ' blockquote', contains='(팬은 정상)이면 핀 오염으로 판정한다'), 5)],
 'v0620': [P(T(VS_OK + ' .row-meta', phrase='진동 평균 120초 < 0.9 → 쿨러 핀 오염'), '이 줄은'),
           P(T(PANE('know:evidence:evd:cooler-fouling-vs1-normal') + ' blockquote', phrase='팬은 정상'), '오른쪽 원문에도'),
           P(T(PANE('know:evidence:evd:cooler-fouling-vs1-normal') + ' blockquote', phrase='핀 오염으로 판정한다'), '같은 말이')],
 'v0621': [P(T(PANE('know:evidence:evd:cooler-fouling-vs1-normal') + ' label.doc-check', anchor='margin'), '여기, 적재에서')],
 'v0622': [P(T('#manualReview .doc-confirm label.doc-check', anchor='margin'), '맨 아래로'), C(T('#manualReviewed', anchor='center'), '체크하고'),
           C(T('#manualCommit', anchor='center'), '누르겠습니다'), W(T('#manualCommitSteps li[data-step="commit"] b'), 10)],
 # 적재가 끝나 「지식 지도에 적재했습니다」가 뜬 뒤에 다음 말(v0624)을 시작한다 — 세 단계가 약 6초 흐른다
 'v0623': [P(T('#manualCommitSteps li[data-step="commit"] b')), LONG(T('#manualCommitTitle', exact='지식 지도에 적재했습니다'), 60)],
 'v0624': [P(T('#manualCommitTitle'), '지식 지도에 적재했다고')],
 # 지식 지도에서 이어진 길 보기
 'v0625': [P(T('#manualDone a.go[data-go-tab="ontology"]'), '밑에 있는 지식 지도에서'), C(T('#manualDone a.go[data-go-tab="ontology"]'), '눌러서'),
           W(T('#ontoFocus')), W(CY('@node'), 30), SETTLE(8)],
 'v0626': [P(CY('@node'), '점 하나가'), P(CY('@edge'), '선은')],
 'v0627': [P(T('#ontoFocus'), '위에 보이는'), SEL(T('#ontoFocus'), '쿨러 성능 저하', '고르시면'),
           W(T('#ontoHint', contains='「쿨러 성능 저하」 경보에서'), 10), SETTLE(5)],
 'v0628': [P(CY('head:B:이상 패턴'), '왼쪽부터'), P(CY('pattern:cooler-degradation'), '쿨러 성능 저하는'), P(CY('sym:ce-drop'), '냉각 효율 저하와'),
           P(CY('sym:ts1-rise'), '유온 상승이고'), P(CY('fm:cooler-cooling-loss'), '쿨러 냉각 성능 상실입니다'), P(CY('head:R:원인'), '원인 셋과'),
           P(CY('head:R:조치 방법'), '조치들이')],
 'v0629': [P(CY('fm:cooler-cooling-loss'), '그 길이 이렇게'), P(CY('cause:cooler-fin-fouling'), '원인도'), P(CY('skill:sop-fan-11'), '조치도')],
 # 결함 시뮬레이션에서 고장 내기
 'v0630': [C(T('#menuList summary[data-menu="plant"]'), '펼쳐서'), C(T('#menuList a[data-tab="scenario"]'), '열게요'),
           W(T(U(1) + ' button[data-act="degrade"]'))],
 'v0631': [P(T('#view-scenario .page-head p'), '결함 시뮬레이션은'), P(T(U(1) + ' h3'), '설비 세 대는'), P(T(U(2) + ' h3'), '컴퓨터 안에서'),
           P(T(U(3) + ' h3'), '가상 설비예요'), P(T('#view-scenario p.scope span'), '이 화면에서 누르는')],
 'v0632': [W(T(U(1) + ' [data-f="fact"]', exact='유온 48.0 ℃ · 쿨러 성능 100 %'), 5), P(T(U(1) + ' [data-f="state"] .tag', exact='운전 중'), '첫 번째 설비는'),
           P(T(U(1) + ' [data-f="fact"]'), '유온 사십팔'), P(T(U(2) + ' .lab-what > span', exact='업무 사건 · 정기 정비'), '옆의 두 대에서는'),
           P(T(U(3) + ' .lab-what > span', exact='업무 사건 · 예비품 구매'), '예비품 구매'), P(T(U(2) + ' .biz-alert .tag', anchor='center', dy=-15), '빨간 표시는'),
           P(T(U(3) + ' .biz-alert .tag', anchor='center', dy=-15), '그 업무를'), P(T(U(1) + ' h3'), '오늘은 첫 번째')],
 'v0633': [P(T(U(1) + ' button[data-act="degrade"]', anchor='center'), '여기 쿨러'), C(T(U(1) + ' button[data-act="degrade"]', anchor='center'), '누르시면'),
           W(T('#labFollow li[data-step="inject"].ok')), SC(T('#labFollowPanel', bottom=6))],
 'v0634': [W(T(RISE, contains='지금 유온'), 10), P(T(RISE, phrase='지금 유온'), '유온이 조금씩')],
 # 말이 끝나면 「처리 건이 열렸습니다」까지(주입 뒤 약 44초) 말 없이 기다린다 — 합성 뒤 cut.py로 가운데를 줄인다
 'v0635': [P(T(RISE, phrase='경보 조건 55 ℃'), '오십오 도를'), LONG(T('#labFollow li[data-step="case"].ok'), 180)],
 'v0656': [P(T('#labFollow li[data-step="alert"] .line-text b'), '경보가 나고'), P(T('#labFollow li[data-step="case"] .line-text b'), '처리 건이 열렸다고'),
           P(T(U(1) + ' [data-f="state"] .tag', exact='경보 발생'), '경보 한 건이'), W(T('#navTodo', exact='1'), 30), P(T('#navTodo'), '숫자가 하나'),
           C(T('#labFollow [data-lv-go="case"]'), '눌러 들어가'), W(T('#todoPanel .turn-head h3'), 60), SETTLE(8)],
 # 처리 건에서 AI 판단 읽기 — 추천안이 대본과 같은지 확인(영상 V-13)
 'v0638': [W(T('#todoPanel .turn-head h3', exact='팬 최대 운전을 승인할까요?'), 5), P(T('#instList button.row[data-todo-task] .row-title'), '왼쪽 목록 맨 위'),
           P(T('#instDetail .case-title > span', exact='냉각 긴급 대응 HYD-01'), '오른쪽에 그 내용이'), P(T('#todoPanel .turn-eyebrow', phrase='내가 할 일 · 승인'), '맨 위 카드가')],
 'v0639': [P(T('#todoPanel .turn-head h3'), '카드 제목에'), P(T('#todoPanel .turn-ai p b', exact='AI 판단'), '밑의 AI 판단'),
           P(T('#todoPanel .turn-ai p', phrase='쿨러 핀 오염'), '원인을 쿨러'), P(T('#todoPanel [data-open-tab="judge"]'), '바로 밑의 판단 근거'),
           C(T('#todoPanel [data-open-tab="judge"]', anchor='center'), '누르면'), W(T('dialog[open] [data-cr-tab="judge"][aria-selected="true"]'), 10),
           W(T(f'{SHEET} ul.evid'), 10)],
 'v0640': [P(T(f'{SHEET} h4.cr-h', exact='근거'), '결론 밑의'), P(T(f'{SHEET} ul.evid > li', nth=0, anchor='margin'), '첫 줄은'),
           P(T(f'{SHEET} ul.evid > li', nth=1), '팬 진동은'), P(T(f'{SHEET} ul.evid > li', nth=2), '냉각 효율은')],
 'v0641': [P(T(f'{SHEET} ul.evid > li', nth=1, anchor='margin'), '아까 원문과')],
 'v0642': [W(T(OPT(1) + ' .opts-name b', exact='팬 최대 운전'), 5), W(T(OPT(4) + ' .opts-name b', exact='쿨러 핀 세척'), 5),
           W(T(OPT(4) + ' .opts-why', contains='정비하는 동안 설비 정지'), 5),
           P(T(f'{SHEET} h4.cr-h', contains='후보 비교'), '밑의 후보 비교는'), P(T(OPT(1) + ' .opts-name b'), '팬 최대 운전을 추천'),
           P(T(OPT(4) + ' .opts-name b'), '쿨러 핀 세척은'), P(T(OPT(4) + ' .opts-why', phrase='정비하는 동안 설비 정지'), '정비하는 동안'),
           P(T(OPT(4) + ' .opts-why', phrase='납기에서 뒤짐'), '납기 손해가')],
 # 승인하고 결과 따라가기
 'v0643': [C(T('dialog[open] [data-cr-sheet-close]', anchor='center'), '근거를 닫고'), P(T('#todoPanel .turn-foot .who'), '오른쪽 아래에')],
 'v0644': [P(BELOW('#tdRejectOpen'), '승인 옆의 반려는'), P(BELOW('#tdMore'), '그 옆에 보이는'), C(T('#tdGo', anchor='center'), '승인해 보겠습니다')],
 # 승인 뒤 기다림(냉각 명령 줄 · 기록이 따라 내려가 멈추기)은 이 큐의 말이 흐르는 동안 한다. v0644 끝에서 기다리면 그만큼 v0648이 늦어져,
 # 효과 확인 줄의 「(설비 시간 15분)」이 사라지는 승인 뒤 약 48초(연장될 때)보다 늦게 짚었다(구간 7 실측 계산: 48.7초 → 44.3초).
 # 설비가 실행 완료로 답한 뒤에 다음 말(v0646)을 시작한다
 'v0645': [SETTLE(4), P(STEP('운전원 승인'), '사람이 할 일은'), W(STEP('냉각 명령'), 30), P(STEP('냉각 명령'), '여기서부터는'),
           LONG(SUB('설비가 실행 완료로 답했습니다'), 60)],
 'v0646': [P(STEP('냉각 명령'), '냉각 명령 줄을'), P(SUB('설비가 실행 완료로 답했습니다', phrase='설비가 실행 완료로 답했습니다'), '설비가 실행했다고')],
 'v0647': [P(SUB('(안전 연동 통과)', phrase='(안전 연동 통과)'), '괄호 안의 안전')],
 # 말이 끝나면 효과 확인이 끝날 때까지(승인 뒤 약 66초) 말 없이 기다린다 — 처리 건이 끝나며 맨 위에 결과 칸이 끼어드니 화면이 멈춘 뒤 다음 말
 'v0648': [P(STEP('효과 확인'), '지금은 효과 확인'), W(SUB('(설비 시간 15분)', phrase='(설비 시간 15분)'), 30),
           P(SUB('(설비 시간 15분)', phrase='(설비 시간 15분)'), '괄호 안의 설비'), P(T('#railScale'), '왼쪽 아래 이십'),
           LONG(SUB('회복으로 판정했습니다'), 180), W(T('#caseTop .case-result'), 20), SETTLE(10),
           # 다음 말(v0649)을 시작하기 전에 효과 확인 줄이 보이게 굴려 둔다 — 게시본은 말이 시작할 때 맨 위 결과 카드가 보이고 말 가운데에야 내려갔다(적대 검토 지적 9)
           ['scroll', {**SUB('회복으로 판정했습니다'), 'top': 220}], SETTLE(4)],
 'v0649': [P(SUB('회복으로 판정했습니다'), '효과 확인이 끝나면서'), P(STEP('정비 요청 등록'), '정비 요청 등록과'), P(STEP('결과 보고: 정상'), '결과 보고까지')],
 'v0650': [P(T('#caseTop .case-result header .tag', exact='정상'), '맨 위로'), P(T('#caseTop .case-result .result-main', phrase='유온 정상 · 경보 해제'), '유온이 기준')],
 'v0651': [P(T('#caseTop .case-result .result-main'), '그 줄 끝에는')],
 'v0652': [P(T('#instDetail .case-progress > header h3', exact='진행 상황'), '진행 상황을'), P(STEP('원인 진단 · 냉각 조치 제안'), 'AI의 추천은'),
           P(STEP('운전원 승인'), '사람의 승인은'), P(STEP('냉각 명령'), '설비로 간 명령은'),
           P(SUB('추천안 그대로 승인했습니다', phrase='추천안 그대로 승인했습니다'), '승인 줄에는')],
 # 홈에서 마무리
 'v0657': [C(T('#menuList a[data-tab="main"]'), '홈으로'), W(T('#mainStages a.stat')), P(T('#view-main .page-head p'), '맨 위 한 줄을')],
 # 「2건」: 쿨러 처리 건과 함께 v0612의 AI 추출도 처리 건 하나(「… 추출 제안」, 흐름 manual_source_extraction)로 끝나 세어진다 — 대본 v0654 「하나 세어져」와 어긋남(보고)
 'v0654': [W(T('#mainStages a.stat:nth-child(4) .stat-value', contains='2건 처리 완료'), 10), P(T('#mainStages a.stat:nth-child(4) .stat-value'), '아래 결과 보기')],
 'v0655': [P(T('#mainStages a.stat[data-go-tab="scenario"] .go'), '결함 시뮬레이션에서')],
 'v0659': [],
}


def rows(md):
    """대본 본문(# 촬영 본문 끝 앞)의 절과 큐 줄 → [(구간 번호, 절 이름, 큐 id, 발화)]."""
    body, out, seg, name = md.split('# 촬영 본문 끝', 1)[0], [], 0, ''
    for line in body.splitlines():
        if line.startswith('## '):
            seg, name = seg + 1, line[3:].strip()
            continue
        m = re.match(r'\| (v\d{4}) \| (.+?) \| (.+?) \|$', line)
        if m:
            out.append((seg, name, m.group(1), m.group(2).strip()))
    return out


def result_last(ops):
    """앞 큐가 조작 결과를 띄우며 끝났나: 끝에서부터 기다림 · 굴리기를 건너 처음 만나는 것이 누르기 · 고르기이거나, 일부러 기다린 자리(long)면 그렇다."""
    for o in reversed(ops):
        if o[0] == 'wait' and o[1].get('long'):
            return True
        if o[0] in ('wait', 'settle', 'scroll'):
            continue
        return o[0] in ('click', 'select')
    return False


def build(md):
    rs, cues = rows(md), []
    ids = [r[2] for r in rs]
    if ids != ORDER:
        sys.exit(f'대본의 큐 차례가 다르다 — 대본 {ids}')
    if set(OPS) - set(ids):
        sys.exit(f'대본에 없는 큐의 조작: {sorted(set(OPS) - set(ids))}')
    for seg, name, cid, text in rs:
        ops, last = OPS.get(cid, []), -1.0
        for o in ops:
            v = o[-1]
            if isinstance(v, dict) and 'at' in v:
                if v['at'] not in text:
                    sys.exit(f'{cid}: 대사에 없는 구절 「{v["at"]}」')
                f = text.index(v['at']) / len(text)
                if f < last:
                    sys.exit(f'{cid}: 조작 시점이 거꾸로 — 「{v["at"]}」')
                last = f
        prev = cues[-1] if cues else None
        if prev is None or prev['segment'] != seg:
            gap = GAP_SEG
        elif not re.search(r'[.?!]["」』]?$', prev['text']):
            gap = GAP_JOIN      # 한 문장이 두 큐로 나뉜 자리(영상 V-14 「잇기」)
        elif result_last(prev['ops']):
            gap = GAP_RESULT
        else:
            gap = GAP_CUE
        cues.append({'id': cid, 'segment': seg, 'section': name, 'text': text, 'gap': gap, 'ops': ops})
    return cues


def main():
    cues = build(SRC.read_text(encoding='utf-8'))
    if PICK:
        a, z = PICK[0].split('-')
        if a not in ORDER or z not in ORDER or ORDER.index(a) > ORDER.index(z):
            sys.exit(f'--고르기 범위가 큐 차례에 없다: {PICK[0]}')
        part = cues[ORDER.index(a):ORDER.index(z) + 1]
        doc = {'voice_id': VOICE, 'model_id': MODEL, 'note': f'{OUT.name}의 {PICK[0]} 사본(--고르기)', 'cues': part}
        with open(PICK[1], 'w', encoding='utf-8', newline='\n') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(f'{PICK[0]}: 큐 {len(part)} · 구간 {sorted({c["segment"] for c in part})} · 글자 {sum(len(c["text"]) for c in part)} → {PICK[1]}')
        return
    doc = {'voice_id': VOICE, 'model_id': MODEL,
           'note': f'1회차 실습 06 전체과정관찰(두 과정 공통, 새 포털 main f805fd43). {SRC.name}에서 {Path(__file__).name}로 만든다 — 손으로 고치지 않는다. '
                   '모듈 segs/one06.mjs → segs/map.mjs. gap은 앞 말이 끝나고 이 말을 시작할 때까지의 초(영상 V-14).',
           'cues': cues}
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    by = {}
    for c in cues:
        by.setdefault((c['segment'], c['section']), []).append(c)
    for (n, name), cs in by.items():
        print(f'구간 {n} {name}: 큐 {len(cs)} · 조작 {sum(len(c["ops"]) for c in cs)} · 글자 {sum(len(c["text"]) for c in cs)}')
    print(f'모두 큐 {len(cues)} · 글자 {sum(len(c["text"]) for c in cues)} → {OUT.name}')


if __name__ == '__main__':
    main()
