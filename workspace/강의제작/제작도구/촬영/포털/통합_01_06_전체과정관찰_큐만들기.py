# 1회차 실습 06 전체과정관찰(두 과정 공통, 2026-11 새 포털 판)의 큐 JSON을 확정 대본에서 만든다. 손으로 고치지 않는다.
#   python3 통합_01_06_전체과정관찰_큐만들기.py [<대본.md>]  → 같은 폴더의 통합_01_06_전체과정관찰_큐.json
#   python3 통합_01_06_전체과정관찰_큐만들기.py --고르기 <처음 큐>-<끝 큐> <출력.json>  → 그 범위(차례 기준)의 큐만 담은 사본(git 밖에 둔다)
#     대표 구간(영상 길 14)처럼 구간 일부만 찍을 때 쓴다. take.mjs는 고른 구간의 모든 큐에 음성이 있어야 녹화하므로, 산 큐만 담은 사본을 준다.
#     조작이 같아서 전체 큐로 통과한 리허설 표시가 그대로 맞는다.
#   대본을 주지 않으면 산출물/통합반/실습/01회차/대본/06_실습_전체과정관찰.md(실전반 파일과 같은 바이트)를 읽는다.
# 대본 「## 절」 하나가 구간 하나이고, 표의 한 줄(| vNNNN | 발화 | 조작 |)이 큐 하나다. 글은 발화 칸 그대로, 조작은 아래 표(OPS), 쉼(gap, 초)은 영상 V-14.
# 조작 형식은 촬영도구/segs/map.mjs 머리말: [조작, 대상, 시점]. 시점은 {'at': '대사 속 구절'}(그 구절이 시작하는 글자 비율 — map.mjs가 큐 시작 + 길이 × 비율 − 300ms에 한다)
#   이거나 생략(앞 조작이 끝나면 바로). wait · settle은 시점이 없다. 대상은 길뚫기(2026-11-17, main f805fd43 포털 DOM)로 찾았고, 2026-11-20 main 39e93119a(포털 화면 글 고침)의 코드로 다시 맞췄다.
# 강조(영상 V-14 · V-11): 조작 칸에서 짚는 대상 뒤의 (밑줄) · (띠) · (테두리)마다 그 짚기 대상에 hl(underline · band · box)을 준다(H). keep은 앞 강조를 지우지 않고 함께 두는 자리다
#   (조작 칸의 「함께 둔다」 — 말이 둘 이상을 함께 가리키거나 차례로 늘어놓는 자리). 강조 대상은 main 305a5405의 포털 코드와 그 앞 판 39e93119의 학생 길 그림으로 정했다.
#   강조 없이 화살표만 옮기는 짚기(P)는 넷이다: v0601 쉬는 자리로 돌아가기, v0607 점선의 출발점, v0635 기다리는 동안의 자리, v0658 흐르는 단계 줄(결과가 뜨면 줄 자리가 옮겨져 강조가 어긋난다).
# 멈춘다(큐 id를 대며): 대본의 큐 차례가 다를 때, 조작 표에 대본에 없는 큐가 있을 때, 시점 구절이 대사에 없거나 차례가 거꾸로일 때,
#   조작 칸의 모양 표시 수 · 모양과 그 큐의 hl 수 · 모양이 다를 때, 강조를 그린 구절에서 그것을 지우는 조작(누르기 · 고르기 · 굴리기 · 입력, keep 없는 다음 강조, 강조 없는 짚기)의
#   구절까지 말이 MIN_HL초(시간계산.py의 말 길이 계수)보다 짧을 때 — 3회차 04에서 짚는 구절과 누르는 구절이 한두 낱말 차이라 강조가 0초 · 0.27초만 보였다. 그런 자리는 짚는 구절을 앞으로 당긴다.
# 녹화 모듈은 촬영도구/segs/one06.mjs(→ map.mjs). 영상 V-13: 추천안 이름 · 후보 비교 4번 줄 · 효과 확인의 설비 시간 괄호는
#   대본과 같은지 wait(정확한 글)로 확인한다 — 다르면 리허설 · 녹화가 그 큐에서 멈추고, 그때는 대본의 그 큐 말을 바꾼다.
import json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
from 시간계산 import load_coef, speech_seconds      # 말 길이 계수(시간계수.json) — 강조가 보이는 시간을 어림한다

PICK = sys.argv[2:4] if sys.argv[1:2] == ['--고르기'] else None
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not PICK else ROOT / 'workspace/강의제작/산출물/통합반/실습/01회차/대본/06_실습_전체과정관찰.md'
OUT = HERE / '통합_01_06_전체과정관찰_큐.json'
VOICE, MODEL = 'tlxL9ilynpbOVf9sZXKh', 'eleven_v4'      # 영상 V-4
# 2026-11-20: v0614(따로 뽑는 까닭)는 고장 유형 · 원인 줄이 보이는 v0617 뒤로 옮겼다(적대 검토 지적 2)
ORDER = ([f'v06{n:02d}' for n in range(1, 13)] + ['v0658', 'v0613', 'v0615', 'v0616', 'v0617', 'v0614'] + [f'v06{n:02d}' for n in range(18, 36)] + ['v0656']
         + [f'v06{n:02d}' for n in range(38, 53)] + ['v0657', 'v0654', 'v0655', 'v0659'])
GAP_JOIN, GAP_CUE, GAP_RESULT, GAP_SEG = 0.6, 1.3, 2.0, 2.3      # 영상 V-14 실습 값(잇기 · 큐 사이 · 조작 결과가 뜬 뒤 · 구간이 바뀌는 곳)
SHAPE = {'밑줄': 'underline', '띠': 'band', '테두리': 'box'}
MIN_HL = 1.4      # 강조를 그린 구절에서 그것을 지우는 조작의 구절까지 말 길이(초)의 하한 — 화살표 이동(최대 0.62초)과 상자 재기를 빼고 0.7초 넘게 보이게


def T(css, **k): return dict(css=css, **k)
def at(s): return [{'at': s}] if s else []
def P(t, s=None): return ['point', t, *at(s)]
def H(t, shape, s=None, keep=None): return ['point', {**t, 'hl': shape, **({'keep': keep} if keep else {})}, *at(s)]
def C(t, s=None): return ['click', t, *at(s)]
def SEL(t, label, s=None): return ['select', t, label, *at(s)]
def SC(t, s=None): return ['scroll', t, *at(s)]
def W(t, secs=15): return ['wait', t, secs]
def LONG(t, secs): return ['wait', {**t, 'long': True}, secs]      # 일부러 기다리는 자리(6초 넘어도 리허설 실패가 아니다)
def SETTLE(secs=10): return ['settle', None, secs]
def CY(i, **k): return {'cy': i, **k}
def EDGE(a, b): return {'cy': f'{a}>{b}'}      # 지식 지도의 두 항목을 잇는 선 하나
def BELOW(css, **k): return T(css, anchor='center', dy=22, **k)       # 누르지 않는 단추는 바로 밑 빈자리를 짚는다(촬영준비 길 4 — 마우스 올림 색)
def ABOVE(css, **k): return T(css, anchor='center', dy=-18, **k)      # 밑에 다른 글이 붙은 단추는 바로 위 끝을 짚는다(화살표 몸통은 그 단추 위에 놓인다)
def TEXT(css, **k): return T(css, also=[], text=True, **k)      # 요소 상자가 아니라 그 안 글자만 칠하거나 두른다(줄 전체가 칸인 블록 요소 · SVG 글)
def BOTH(css, *more, **k): return T(css, also=[{'css': c} for c in more], **k)      # 대상과 more를 함께 두르는 상자 하나(화살표는 대상에 둔다)


REST = T('#pageLocation', anchor='after', dx=56)      # 쉬는 화살표 자리(one06.mjs의 rest와 같다 — 위 막대 「홈」 오른쪽 빈자리)
MENU = lambda m: T(f'#menuList summary[data-menu="{m}"] > span')
# 홈(main.js heroSvg · renderLive): 그림은 SVG — 글(text)은 TEXT로 잰다
HERO = '#mainHero'
ZONE = lambda name: TEXT(f'{HERO} text.m-zone', exact=name)      # 영역 이름(「OT · 현장 설비」 · 「값이 지나는 길」)
ZTAG = lambda z: TEXT(f'{HERO} text.hm-zone-tag', exact=z)      # 가운데 칸 안의 영역 꼬리표 OT · DMZ · IT
BUS = BOTH(f'{HERO} text.m-zone', f'{HERO} g.m-bus', exact='값이 지나는 길')      # 가운데 칸(값이 지나는 길) — 화살표는 칸 이름 뒤
AGENT = BOTH(f'{HERO} g.m-agent text.m-agent-s', f'{HERO} g.m-agent')      # 인공지능 에이전트 원
NODE = lambda name, **k: T(f'{HERO} g.m-node', contains=name, **k)      # 지식 점(알약)
LOOP = lambda f: T(f'{HERO} path.m-loop', pathAt=f)      # 사람이 승인한 조치가 내려가는 점선(상자는 선 전체)
LOOPT = lambda name: TEXT(f'{HERO} text.m-loop-t', exact=name)
STAGES = '#mainStages'
STAGE = lambda n: f'{STAGES} a.stat:nth-child({n})'
LABEL = lambda n: T(f'{STAGE(n)} .stat-label')
CARDS = T(f'{STAGE(1)} .stat-label', also=[{'css': STAGES}])      # 단계 카드 넷(화살표는 첫 카드 이름 뒤)
# 문서 등록(hitl.js)
PHASE = lambda name: T('#manualSteps .phase', exact=name)
HM8 = '#providedDocs button.row[data-provided="HM-8_cooler-fan-manual.md"]'
TRAIL = lambda step: T(f'.doc-trail li[data-step="{step}"] .line-text > b')
ITEM = lambda key: f'#manualItems [data-item="{key}"]'
ROW = lambda key: BOTH(ITEM(key) + ' .row-title', ITEM(key))      # 목록 한 줄(화살표는 이름 뒤)
META = lambda key, phrase, **k: T(ITEM(key) + ' .row-meta', phrase=phrase, **k)      # 이름 밑 작은 글의 구절
FMK, PROC1, PROC7 = 'know:failure_modes:fm:cooler-cooling-loss', 'proc:SOP-FAN-11', 'proc:SOP-COOL-15'
CAUSE = lambda c: f'know:causes:cause:{c}'
VS_OK_K, VS_HI_K = 'know:evidence:evd:cooler-fouling-vs1-normal', 'know:evidence:evd:fan-drive-vibration-high'
FM, VS_OK = ITEM(FMK), ITEM(VS_OK_K)
PANE = lambda key: f'#manualPanes [data-pane="{key}"]'
PROCS = BOTH(ITEM(PROC1) + ' .row-title', ITEM(PROC1), ITEM(PROC7))      # 조치 방법 일곱 줄
FMCAUSES = BOTH(ITEM(FMK) + ' .row-title', ITEM(FMK), ITEM(CAUSE('fan-drive-fault')))      # 고장 유형 한 줄과 원인 세 줄
# 지식 지도(enterprise.js) — 이상 패턴 경로의 마지막 줄은 원인(위)과 조치 방법(아래)이 한 줄로 선다(kgPathLay)
PAT, FMN = 'pattern:cooler-degradation', 'fm:cooler-cooling-loss'
CAUSES = ['cause:cooler-fin-fouling', 'cause:ambient-temperature-rise', 'cause:fan-drive-fault']
SKILLS = ['skill:sop-fan-11', 'skill:sop-fan-12', 'skill:sop-cool-11', 'skill:sop-cool-12', 'skill:sop-cool-13', 'skill:sop-cool-14', 'skill:sop-cool-15']
CAUSEBOX = CY('head:R:원인', also=[{'cy': c} for c in CAUSES])
SKILLBOX = CY('head:R:조치 방법', also=[{'cy': s} for s in SKILLS])
PATHBOX = CY(FMN, also=[{'cy': i} for i in ['head:B:이상 패턴', PAT, 'head:R:원인', *SKILLS]])      # 밝게 남은 길 전체(화살표는 고장 유형)
# 결함 시뮬레이션(app.js)
U = lambda n: f'#units [data-asset="HYD-0{n}"]'
UNIT = lambda n: BOTH(U(n) + ' h3', U(n))      # 설비 카드 하나(화살표는 카드 이름 뒤)
RISE = '#labFollow li[data-step="rise"] .lv-note'
FOLLOW = lambda step: T(f'#labFollow li[data-step="{step}"] .line-text b')
# 처리 건(instances.js · caseRecord.js)
TODO_ROW = '#instList button.row[data-todo-task]'
SHEET = 'dialog[open] [data-cr-sheet-body]'
OPT = lambda n: f'{SHEET} table.opts tbody tr:nth-child({n})'
EVID = lambda n, **k: T(f'{SHEET} ul.evid > li', nth=n, **k)
STEP = lambda name: T('#instRecord [data-cr-steps] .step-title', exact=name)
SUB = lambda has, **k: T('#instRecord [data-cr-steps] .step-sub', contains=has, **k)
PROGRESS = T('#instDetail .case-progress > header h3', exact='진행 상황')

OPS = {
 # 포털 홈 — 시작 상태 확인(처리 건 0건). 화살표는 위 막대 「홈」 오른쪽 빈자리(one06.mjs의 rest). 브랜드는 바로 밑을 짚는다(브랜드 줄에 올리면 마우스 올림 색)
 'v0601': [W(T('#mainStages a.stat:nth-child(4) .stat-value', contains='0건 처리 완료'), 20), W(T('#mainStages a.stat:nth-child(3) .stat-value', contains='0건 진행 중'), 5),
           H(T('#brandHome .brand-name', anchor='below', dy=4), 'underline', '이름은'), P(REST, '설비에 고장을')],
 # 홈에서 보는 목표와 방향
 'v0603': [H(T('#healthDots', anchor='center', dy=14), 'underline', '왼쪽 아래를'), H(T('#healthDots b.num', anchor='center', dy=14), 'underline', '앞뒤 숫자가')],
 'v0604': [H(TEXT('#view-main .page-head p'), 'band', '맨 위 한 줄에는')],
 # 말이 값의 길을 왼쪽에서 오른쪽으로 따라가는 자리는 강조를 함께 두어 쌓는다(OT 이름 → 가운데 칸 → AI, 꼬리표 OT → DMZ → IT)
 'v0605': [H(T(f'{HERO} svg.m-hero-svg', anchor='center'), 'box', '아래 그림은'), H(ZONE('OT · 현장 설비'), 'underline', '왼쪽이 공장'),
           H(BUS, 'box', '가운데 칸을', keep=True), H(AGENT, 'box', '오른쪽 AI', keep=True),
           H(ZTAG('OT'), 'underline', 'OT, DMZ'), H(ZTAG('DMZ'), 'underline', 'DMZ, IT가', keep=True), H(ZTAG('IT'), 'underline', 'IT가 차례로', keep=True),
           H(ZTAG('OT'), 'underline', '공장 안 OT에서'), H(ZTAG('DMZ'), 'underline', '중간 구역', keep=True), H(ZTAG('IT'), 'underline', '사무실 쪽', keep=True),
           H(ZONE('값이 지나는 길'), 'underline', '값이 올라가는 길이라고')],      # 영역 꼬리표 셋(main.js BUS의 zone) — 2026-11-20 이론의 세 보안 영역을 화면에서 짚는다
 'v0606': [H(AGENT, 'box', '오른쪽 한가운데가'), H(NODE('증상 · 유온 상승', anchor='left'), 'box', '둘레의 점들은'),      # 증상 점은 글 끝 오른쪽이 아래 「원인 · 쿨러 핀 오염」을 덮어 점 왼쪽을 짚는다
           H(NODE('고장 유형 · 냉각 상실'), 'box', '고장 유형,', keep=True), H(NODE('원인 · 쿨러 핀 오염'), 'box', '원인 같은', keep=True),
           H(AGENT, 'box', 'AI 에이전트는')],
 'v0607': [P(T(f'{HERO} text.m-loop-t', exact='사람이 승인한 조치'), '거꾸로 설비'), H(LOOP(0.97), 'box', '위에 있는 점선'),
           H(LOOPT('사람이 승인한 조치'), 'band', '사람이 승인한'), H(LOOPT('명령 관문 · DMZ'), 'underline', '가는 길에'),
           H(BUS, 'box', '올라가는 길과'), H(LOOP(0.4), 'box', '내려가는 길,', keep=True)],
 'v0608': [SC(T(STAGES, bottom=12), '아래 네 칸은'), H(CARDS, 'box'), H(LABEL(1), 'underline', '지식을 넣어'), H(LABEL(2), 'underline', '설비에 고장이', keep=True),
           H(LABEL(3), 'underline', 'AI의 판단과', keep=True), H(LABEL(4), 'underline', '결과가 남죠', keep=True),
           H(MENU('knowledge'), 'underline', '지식,'), H(MENU('plant'), 'underline', '유압 설비,', keep=True),
           H(T('#menuList a[data-menu="instances"] > span', exact='처리 건'), 'underline', '처리 건이', keep=True)],
 # 매뉴얼을 지식으로 넣기 — 문서 등록
 'v0609': [H(T(f'{STAGE(1)} .stat-label', also=[{'css': STAGE(1)}]), 'box', '이런 지식은'),      # 앞 구간이 왼쪽 메뉴 「처리 건」을 짚고 끝나, 그대로 두면 그 줄이 마우스 올림 색으로 20초쯤 남는다 — 지식을 모아 두는 첫 칸으로 옮긴다
           H(T('#mainStages a.stat[data-go-tab="knowledge"] .go'), 'underline', '첫 칸 아래'), C(T('#mainStages a.stat[data-go-tab="knowledge"] .go'), '누르시면'),
           W(T('#providedDocs button.row[data-provided="HM-8_cooler-fan-manual.md"]'))],
 'v0610': [H(T('#manualSteps .phase', exact='올리기', also=[{'css': '#manualSteps'}]), 'box', '위쪽에 단계가'),
           H(PHASE('올리기'), 'underline', '올리기,'), H(PHASE('AI 추출'), 'underline', 'AI 추출,', keep=True), H(PHASE('검토'), 'underline', '검토,', keep=True),
           H(PHASE('적재'), 'underline', '적재 순서', keep=True), H(PHASE('적재'), 'underline', '적재라고')],
 'v0611': [H(ABOVE('#manualPick button[data-pick-mode="file"]'), 'box', '여기, 내 파일'), H(T('#providedDocs .doc-prov', anchor='margin'), 'box', '그 아래 목록'),
           H(BOTH(HM8 + ' .row-title', HM8), 'band', '쿨러 팬 정비'),
           C(T(HM8 + ' .row-title', anchor='after'), '누르면'), W(T('#manualAgentExtract'))],      # 누르기 기본 자리(요소 오른쪽 끝)는 줄 끝 「›」라 바로 옆 「원문 보기」를 누르는 것처럼 보인다 — 짚던 제목 끝에서 누른다
 'v0612': [H(TEXT('#manualResult .result-label', exact='이미 적재된 문서', anchor='margin'), 'band', '이미 적재된'),
           H(T('#manualStageNote', phrase='이 원문으로 만든 판본이 지식 지도에 적재돼 있습니다', anchor='margin'), 'band', '이 매뉴얼은'),
           H(T('#manualAgentExtract', anchor='center'), 'box', '그 과정을'), C(T('#manualAgentExtract', anchor='center'), '누를게요')],
 # 추출을 기다리는 동안 흐르는 단계 줄(.doc-trail — 기다리는 동안은 실시간 칸 맨 위, 결과가 뜨면 결과 요약 밑으로 같은 칸이 옮겨진다).
 # 흐르는 동안은 화살표만 첫 줄에 두고(결과가 뜨면 줄 자리가 옮겨져 강조가 어긋난다), 결과가 뜬 뒤 옮겨진 자리의 첫 줄에 띠를 그린다. 둘째 줄은 그 뒤에 짚는다
 # 단계 줄의 이름은 포털 화면 글 고침(저장된 결과를 말하는 글을 없앰)으로 바뀌므로 이름이 아니라 단계 자리(data-step)로 짚는다
 'v0658': [P(TRAIL('open'), '단계가 하나씩'), W(T('#manualReview'), 20), H(TRAIL('open'), 'band'), H(TRAIL('verify'), 'band', '대조하는')],
 'v0613': [H(TEXT('#manualReview .result-main'), 'band', '결과가 나왔습니다')],      # 그 밑 줄(#manualAgentStatus)은 짚지 않는다 — 포털에서 없어질 글이고 대본도 말하지 않는다(영상 V-13)
 'v0615': [SC(T('#manualReview .doc-review .doc-review-bar', top=70), '밑으로 내려'), H(PROCS, 'box', '처음 보이는'),
           H(META(PROC1, '쿨러 냉각 성능 상실'), 'underline', '줄마다'),
           H(T('#manualReview button[data-review-kind="know"]'), 'box', '목록 위에 있는'), C(T('#manualReview button[data-review-kind="know"]', anchor='center'), '누르면'),
           W(T(FM))],
 'v0616': [H(ROW(FMK), 'band', '맨 위 줄을'), H(META(FMK, '유온 상승, 냉각 효율 저하'), 'band', '이름 밑에'),
           H(META(FMK, '유온 상승'), 'underline', '기름 온도는 오르고'), H(META(FMK, '냉각 효율 저하'), 'underline', '냉각 효율은 떨어져', keep=True),
           H(TEXT(FM + ' .row-title'), 'band', '쿨러 냉각 성능 상실이라는'), H(META(FMK, '고장 유형'), 'underline', '이론에서 본')],
 'v0617': [H(ROW(CAUSE('cooler-fin-fouling')), 'band', '아래 세 줄은'), H(ROW(CAUSE('ambient-temperature-rise')), 'band', '일으킬 수', keep=True),
           H(ROW(CAUSE('fan-drive-fault')), 'band', '원인 후보입니다', keep=True)],
 # 고장 유형 한 줄과 원인 세 줄이 따로 놓인 화면에서 「이렇게 따로따로」를 말한다(2026-11-20에 v0613 뒤에서 옮김 — 말은 그대로). 조치는 목록 위 「조치 방법」 단추의 바로 위를 짚는다
 'v0614': [H(FMCAUSES, 'box', '고장과 원인,'), H(ROW(FMK), 'band', '무슨 고장인지'), H(ROW(CAUSE('cooler-fin-fouling')), 'band', '그 고장의 원인을'),
           H(ABOVE('#manualReview button[data-review-kind="proc"]'), 'box', '원인에 맞는 조치를'), H(FMCAUSES, 'box', '하나씩 뽑아서')],
 'v0618': [H(ROW(FMK), 'band', '지금 고른 줄이'), H(T(PANE(FMK) + ' blockquote'), 'box', '그 원문이'),
           H(ROW(FMK), 'band', '줄마다'), H(T(PANE(FMK) + ' blockquote'), 'box', '이 원문 한 문장과', keep=True)],
 'v0619': [SC(T(VS_OK, top=330), '조금 내리면'), H(ROW(VS_OK_K), 'band', '팬 진동 줄이'), H(ROW(VS_HI_K), 'band', '팬 진동 줄이', keep=True),
           H(ROW(VS_OK_K), 'band', '위쪽,'), H(T(VS_OK + ' .row-title', phrase='정상 범위'), 'underline', '이름이 정상', keep=True), C(T(VS_OK, anchor='center'), '누르시면'),
           W(T(PANE(VS_OK_K) + ' blockquote', contains='(팬은 정상)이면 핀 오염으로 판정한다'), 5)],
 'v0620': [H(META(VS_OK_K, '진동 평균 120초 < 0.9 → 쿨러 핀 오염'), 'band', '이 줄은'),
           H(T(VS_OK + ' .row-title', phrase='정상 범위'), 'underline', '팬 진동이 정상'), H(META(VS_OK_K, '쿨러 핀 오염'), 'underline', '쿨러 핀 오염으로 봅니다', keep=True),
           H(T(PANE(VS_OK_K) + ' blockquote', phrase='팬은 정상'), 'underline', '오른쪽 원문에도'),
           H(T(PANE(VS_OK_K) + ' blockquote', phrase='핀 오염으로 판정한다'), 'underline', '같은 말이', keep=True),
           H(META(VS_OK_K, '진동 평균 120초 < 0.9 → 쿨러 핀 오염'), 'band', '이 줄은 맞게')],
 'v0621': [H(T(PANE(VS_OK_K) + ' label.doc-check', anchor='margin'), 'box', '여기, 적재에서')],
 # 체크 칸은 굴린 뒤 「맨 아래로」에서 두른다 — 「검토했다는 칸에」에서 두르면 바로 뒤 「체크하고」의 누르기까지 1초 남짓이라 거의 보이지 않는다
 'v0622': [H(ROW(VS_OK_K), 'band', '이 줄은 원문과'), H(T('#manualReview .doc-confirm label.doc-check', anchor='margin'), 'box', '맨 아래로'),
           C(T('#manualReviewed', anchor='center'), '체크하고'), C(T('#manualCommit', anchor='center'), '누르겠습니다'), W(T('#manualCommitSteps li[data-step="commit"] b'), 10)],
 # 적재가 끝나 「지식 지도에 적재했습니다」가 뜬 뒤에 다음 말(v0624)을 시작한다 — 두 단계(개정으로 빠지는 항목 확인 · 적재)가 약 5초 흐른다
 'v0623': [H(T('#manualCommitSteps li[data-step="commit"] b'), 'band'), LONG(T('#manualCommitTitle', exact='지식 지도에 적재했습니다'), 60)],
 'v0624': [H(TEXT('#manualCommitTitle'), 'band', '지식 지도에 적재했다고'), H(PHASE('올리기'), 'underline', '올리고,'), H(PHASE('AI 추출'), 'underline', '뽑고,', keep=True),
           H(PHASE('검토'), 'underline', '검토해서', keep=True), H(PHASE('적재'), 'underline', '넣는 순서로', keep=True)],
 # 지식 지도에서 이어진 길 보기
 'v0625': [H(T('#manualDone a.go[data-go-tab="ontology"]'), 'underline', '밑에 있는 지식 지도에서'), C(T('#manualDone a.go[data-go-tab="ontology"]'), '눌러서'),
           W(T('#ontoFocus')), W(CY('@node'), 30), SETTLE(8)],
 # 점과 선은 2회차 05(k0201)와 같은 것: 이름표가 보이는 「팬 진동 상승」 점, 그 점과 이웃 점(진동 상승)을 잇는 짧은 선(전체 지도에서 선은 흐려서 가운데 가까운 선 하나만 두르면 무엇을 두른 것인지 보이지 않는다)
 'v0626': [H(T('#view-ontology .page-head h1', anchor='below'), 'underline', '이렇게 지식 지도에'), H(CY('pattern:fan-vibration'), 'box', '점 하나가'),
           H(EDGE('pattern:fan-vibration', 'sym:vs1-rise'), 'box', '선은'), H(T('#ontoStats', anchor='below'), 'underline', '점과 선이')],
 'v0627': [H(T('#ontoFocus'), 'box', '위에 보이는'), SEL(T('#ontoFocus'), '쿨러 성능 저하', '고르시면'),
           W(T('#ontoHint', contains='「쿨러 성능 저하」 경보에서'), 10), SETTLE(5)],
 'v0628': [H(CY('head:B:이상 패턴'), 'underline', '왼쪽부터'), H(CY(PAT), 'box', '쿨러 성능 저하는'), H(CY('sym:ce-drop'), 'box', '냉각 효율 저하와'),
           H(CY('sym:ts1-rise'), 'box', '유온 상승이고', keep=True), H(CY(FMN), 'box', '가리키는 고장 유형이'), H(CAUSEBOX, 'box', '원인 셋과'),
           H(SKILLBOX, 'box', '조치들이', keep=True)],
 'v0629': [H(PATHBOX, 'box', '그 길이 이렇게'), H(CY(FMN), 'box', '고장 하나에'), H(CAUSEBOX, 'box', '원인도', keep=True), H(SKILLBOX, 'box', '조치도', keep=True)],
 # 결함 시뮬레이션에서 고장 내기
 'v0630': [C(T('#menuList summary[data-menu="plant"]'), '펼쳐서'), C(T('#menuList a[data-tab="scenario"]'), '열게요'),
           W(T(U(1) + ' button[data-act="degrade"]'))],
 'v0631': [H(TEXT('#view-scenario .page-head p'), 'band', '결함 시뮬레이션은'), H(UNIT(1), 'box', '설비 세 대는'), H(UNIT(2), 'box', '컴퓨터 안에서', keep=True),
           H(UNIT(3), 'box', '가상 설비예요', keep=True), H(T('#view-scenario p.scope span'), 'band', '이 화면에서 누르는')],
 'v0632': [W(T(U(1) + ' [data-f="fact"]', exact='유온 48.0 ℃ · 쿨러 성능 100 %'), 5), H(TEXT(U(1) + ' [data-f="fact"]'), 'band', '첫 번째 설비는'),
           H(T(U(1) + ' [data-f="state"] .tag', exact='운전 중'), 'box', '퍼센트로 잘', keep=True),
           H(T(U(2) + ' .lab-what > span', exact='업무 사건 · 정기 정비', phrase='정기 정비'), 'underline', '옆의 두 대에서는'),
           H(T(U(3) + ' .lab-what > span', exact='업무 사건 · 예비품 구매', phrase='예비품 구매'), 'underline', '예비품 구매', keep=True),
           H(T(U(2) + ' .biz-alert .tag', anchor='center', dy=-15), 'box', '빨간 표시는'), H(T(U(3) + ' .biz-alert .tag', anchor='center', dy=-15), 'box', '그 업무를', keep=True),
           H(UNIT(1), 'box', '오늘은 첫 번째')],
 'v0633': [H(T(U(1) + ' button[data-act="degrade"]', anchor='center'), 'box', '여기 쿨러'), C(T(U(1) + ' button[data-act="degrade"]', anchor='center'), '누르시면'),
           W(T('#labFollow li[data-step="inject"].ok')), SC(T('#labFollowPanel', bottom=6))],
 'v0634': [W(T(RISE, contains='지금 유온'), 10), H(T(RISE, phrase='지금 유온'), 'underline', '유온이 조금씩'), H(FOLLOW('rise'), 'band', '유온 상승이 지금')],
 # 유온이 경보 조건을 넘으면(주입 뒤 약 39초) 이 줄의 글이 바뀌고 그 아래 줄들이 옮겨진다 — 그 전에 강조를 지우려고 「그 상태가 얼마간」에서 화살표를 이 줄 왼쪽으로 옮겨 둔다(강조 없음).
 # 말이 끝나면 「처리 건이 열렸습니다」까지(주입 뒤 약 44초) 말 없이 기다린다 — 합성 뒤 cut.py로 가운데를 줄인다
 'v0635': [H(T(RISE, phrase='경보 조건 55 ℃'), 'underline', '경보 조건 오십오'), H(FOLLOW('detect'), 'band', '쿨러가 식히는'),
           P(T('#labFollow li[data-step="rise"] .line-text b', anchor='margin'), '그 상태가 얼마간'), LONG(T('#labFollow li[data-step="case"].ok'), 180)],
 'v0656': [H(FOLLOW('rise'), 'band', '유온이 오십오'), H(T('#labFollow li[data-step="detect"] .lv-note'), 'band', '조건이 이어지는지'),
           H(FOLLOW('alert'), 'band', '경보가 났죠'), H(FOLLOW('case'), 'band', '처리 건이 열렸다고'),
           H(T(U(1) + ' [data-f="state"] .tag', exact='경보 발생'), 'box', '경보 한 건이'), W(T('#navTodo', exact='1'), 30), H(T('#navTodo'), 'box', '처리 건 옆에도'),
           H(T('#labFollow [data-lv-go="case"]'), 'underline', '아래쪽에 있는'), C(T('#labFollow [data-lv-go="case"]'), '눌러 들어가'),
           W(T('#todoPanel .turn-head h3'), 60), SETTLE(8)],
 # 처리 건에서 AI 판단 읽기 — 추천안이 대본과 같은지 확인(영상 V-13)
 'v0638': [W(T('#todoPanel .turn-head h3', exact='팬 최대 운전을 승인할까요?'), 5),
           H(T('#instList .rows-group', contains='내가 할 일', phrase='내가 할 일'), 'underline', '왼쪽 목록 맨 위'),
           H(BOTH(TODO_ROW + ' .row-title', TODO_ROW), 'band', '방금 생긴'), H(T(TODO_ROW + ' .row-title', phrase='냉각 긴급 대응'), 'underline', '이름은 냉각'),
           H(T('#instDetail .case-title > span', exact='냉각 긴급 대응 HYD-01'), 'band', '오른쪽에 그 내용이'),
           H(T('#todoPanel .turn-eyebrow', phrase='내가 할 일 · 승인', also=[{'css': '#todoPanel section.turn'}]), 'box', '맨 위 카드를'),
           H(T('#todoPanel .turn-eyebrow', phrase='내가 할 일 · 승인'), 'underline', '지금 할 일이', keep=True)],
 'v0639': [H(TEXT('#todoPanel .turn-head h3'), 'band', '카드 제목에'), H(T('#todoPanel .turn-head h3', phrase='팬 최대 운전'), 'underline', '팬 최대 운전을', keep=True),
           H(T('#todoPanel .turn-ai p b', exact='AI 판단', also=[{'css': '#todoPanel .turn-ai p'}], text=True), 'band', '밑의 AI 판단'),
           H(T('#todoPanel .turn-ai p', phrase='쿨러 핀 오염'), 'underline', '원인을 쿨러', keep=True),
           H(T('#todoPanel [data-open-tab="judge"]'), 'box', '바로 밑의 판단 근거'),
           C(T('#todoPanel [data-open-tab="judge"]', anchor='center'), '누르면'), W(T('dialog[open] [data-cr-tab="judge"][aria-selected="true"]'), 10),
           W(T(f'{SHEET} ul.evid'), 10)],
 'v0640': [H(T(f'{SHEET} h4.cr-h', exact='근거', also=[{'css': f'{SHEET} ul.evid'}]), 'box', '결론 밑의'),
           H(EVID(0, anchor='margin'), 'band', '첫 줄은'), H(EVID(1, anchor='margin'), 'band', '그 밑 두 줄에'), H(EVID(2, anchor='margin'), 'band', '그 밑 두 줄에', keep=True),
           H(EVID(1, phrase='정상 범위'), 'underline', '팬 진동은'), H(EVID(2, phrase='평균 저하'), 'underline', '냉각 효율은', keep=True),
           H(EVID(1, phrase='맞음'), 'underline', '둘 다 핀 오염일'), H(EVID(2, phrase='맞음'), 'underline', '둘 다 핀 오염일', keep=True)],
 'v0641': [H(EVID(1, phrase='최근 2분 팬 진동 평균 정상 범위', anchor='margin'), 'band', '아까 원문과')],
 'v0642': [W(T(OPT(1) + ' .opts-name b', exact='팬 최대 운전'), 5), W(T(OPT(4) + ' .opts-name b', exact='쿨러 핀 세척'), 5),
           W(T(OPT(4) + ' .opts-why', contains='정비하는 동안 설비 정지'), 5),
           H(T(f'{SHEET} h4.cr-h', contains='후보 비교', phrase='후보 비교'), 'underline', '밑의 후보 비교는'), H(T(OPT(1) + ' .opts-name b'), 'underline', '팬 최대 운전을 추천'),
           H(T(OPT(4) + ' .opts-name b'), 'underline', '쿨러 핀 세척은'), H(T(OPT(4) + ' .opts-why', phrase='정비하는 동안 설비 정지'), 'underline', '정비하는 동안'),
           H(T(OPT(4) + ' .opts-why', phrase='납기에서 뒤짐'), 'underline', '납기 손해가', keep=True),
           H(T(f'{SHEET} h4.cr-h', contains='후보 비교', phrase='후보 비교'), 'underline', '조치 하나에')],
 # 승인하고 결과 따라가기
 'v0643': [C(T('dialog[open] [data-cr-sheet-close]', anchor='center'), '근거를 닫고'), H(T('#todoPanel .turn-foot .who'), 'band', '오른쪽 아래에')],
 'v0644': [H(BELOW('#tdRejectOpen'), 'box', '승인 옆의 반려는'), H(BELOW('#tdMore'), 'box', '그 옆에 보이는'), C(T('#tdGo', anchor='center'), '승인해 보겠습니다')],
 # 승인 뒤 기다림(냉각 명령 줄 · 기록이 따라 내려가 멈추기)은 이 큐의 말이 흐르는 동안 한다. v0644 끝에서 기다리면 그만큼 v0648이 늦어져,
 # 효과 확인 줄의 「(설비 시간 15분)」이 사라지는 승인 뒤 약 48초(연장될 때)보다 늦게 짚었다(구간 7 실측 계산: 48.7초 → 44.3초).
 # 설비가 실행 완료로 답한 뒤에 다음 말(v0646)을 시작한다
 'v0645': [SETTLE(4), H(STEP('운전원 승인'), 'band', '사람이 할 일은'), W(STEP('냉각 명령'), 30), H(STEP('냉각 명령'), 'band', '여기서부터는'),
           H(PROGRESS, 'underline', '진행 상황에 줄이'), LONG(SUB('설비가 실행 완료로 답했습니다'), 60)],
 'v0646': [H(STEP('냉각 명령'), 'band', '냉각 명령 줄을'), H(SUB('설비가 실행 완료로 답했습니다', phrase='설비가 실행 완료로 답했습니다'), 'underline', '설비가 실행했다고')],
 'v0647': [H(SUB('(안전 연동 통과)', phrase='(안전 연동 통과)'), 'underline', '괄호 안의 안전')],
 # 말이 끝나면 효과 확인이 끝날 때까지(승인 뒤 약 66초) 말 없이 기다린다 — 처리 건이 끝나며 맨 위에 결과 칸이 끼어드니 화면이 멈춘 뒤 다음 말.
 # 괄호의 밑줄은 「실제보다 스무 배」에서 왼쪽 아래 「20배속」의 밑줄로 넘긴다 — 연장이 나면 승인 뒤 약 48초에 괄호가 사라지므로 그 밑줄을 오래 두지 않는다.
 # 「20배속」은 고정된 메뉴 줄에 있어, 결과 칸이 끼어들어 진행 상황이 밀리는 기다림 동안 남아도 자리가 어긋나지 않는다
 'v0648': [H(STEP('효과 확인'), 'band', '지금은 효과 확인'), W(SUB('(설비 시간 15분)', phrase='(설비 시간 15분)'), 30),
           H(SUB('(설비 시간 15분)', phrase='(설비 시간 15분)'), 'underline', '괄호 안에는'), H(T('#railScale'), 'underline', '실제보다 스무 배'),
           LONG(SUB('회복으로 판정했습니다'), 180), W(T('#caseTop .case-result'), 20), SETTLE(10),
           # 다음 말(v0649)을 시작하기 전에 효과 확인 줄이 보이게 굴려 둔다 — 게시본은 말이 시작할 때 맨 위 결과 카드가 보이고 말 가운데에야 내려갔다(적대 검토 지적 9)
           ['scroll', {**SUB('회복으로 판정했습니다'), 'top': 220}], SETTLE(4)],
 # 효과 확인 줄은 main 39e93119a부터 판정 글이 줄 가운데다(「… 경보도 꺼져 회복으로 판정했습니다 (설비 시간 … 동안 …).」) — 줄 끝이 아니라 그 구절을 짚는다
 'v0649': [H(STEP('효과 확인'), 'band', '효과 확인이 끝났습니다'), H(TEXT('#instRecord [data-cr-steps] .step-sub', contains='회복으로 판정했습니다'), 'band', '유온이 기준'),
           H(SUB('회복으로 판정했습니다', phrase='회복으로 판정했습니다'), 'underline', '회복으로 판정했다고', keep=True),
           H(STEP('정비 요청 등록'), 'band', '정비 요청 등록과'), H(STEP('결과 보고: 정상'), 'band', '결과 보고까지', keep=True)],
 'v0650': [H(T('#caseTop .case-result header .tag', exact='정상', also=[{'css': '#caseTop .case-result'}]), 'box', '맨 위로'),
           H(T('#caseTop .case-result header .tag', exact='정상'), 'box', '정상,'), H(T('#caseTop .case-result .result-main', phrase='유온 정상 · 경보 해제'), 'underline', '유온이 기준', keep=True)],
 'v0651': [H(T('#caseTop .case-result .result-main', phrase='정비 요청'), 'underline', '그 줄 끝에는')],      # 번호(WO-…)는 실행마다 달라 구절로 잴 수 없다 — 「정비 요청」에 긋는다
 'v0652': [H(PROGRESS, 'underline', '진행 상황을'), H(STEP('원인 진단 · 냉각 조치 제안'), 'band', 'AI의 추천은'),
           H(STEP('운전원 승인'), 'band', '사람의 승인은', keep=True), H(STEP('냉각 명령'), 'band', '설비로 간 명령은', keep=True),
           H(SUB('추천안 그대로 승인했습니다', phrase='추천안 그대로 승인했습니다'), 'underline', '승인 줄에는')],
 # 홈에서 마무리
 'v0657': [C(T('#menuList a[data-tab="main"]'), '홈으로'), W(T('#mainStages a.stat')), H(TEXT('#view-main .page-head p'), 'band', '맨 위 한 줄을')],
 # 「1건」: main 39e93119a부터 v0612의 AI 추출(「… 추출 제안」, 흐름 manual_source_extraction)은 시스템 작업이라 이 수에 들지 않고(ui.js isSystemJob) 쿨러 처리 건만 세어진다.
 # 카드는 홈 첫 화면에서 아래가 잘려(카드 아래끝 약 778px) 테두리를 그릴 수 없으므로 v0608처럼 카드 넷이 다 보이게 굴린 뒤 두른다
 'v0654': [W(T('#mainStages a.stat:nth-child(4) .stat-value', contains='1건 처리 완료'), 10), SC(T(STAGES, bottom=12), '아래 결과 보기'),
           H(T(f'{STAGE(4)} .stat-value', also=[{'css': STAGE(4)}]), 'box'), H(T(f'{STAGE(4)} .stat-value'), 'underline', '처리 완료로')],
 'v0655': [H(T('#mainStages a.stat[data-go-tab="scenario"] .go'), 'underline', '결함 시뮬레이션에서')],
 # 앞 큐의 밑줄을 지우고, 「큰 흐름」을 단계 카드 넷(v0608 「지금 본 흐름을 일의 차례대로 나눠 놓은 것」)으로 두른 채 끝낸다
 'v0659': [H(CARDS, 'box', '큰 흐름을')],
}


def rows(md):
    """대본 본문(# 촬영 본문 끝 앞)의 절과 큐 줄 → [(구간 번호, 절 이름, 큐 id, 발화, 조작 칸)]."""
    body, out, seg, name = md.split('# 촬영 본문 끝', 1)[0], [], 0, ''
    for line in body.splitlines():
        if line.startswith('## '):
            seg, name = seg + 1, line[3:].strip()
            continue
        m = re.match(r'\| (v\d{4}) \| (.+?) \| (.+?) \|$', line)
        if m:
            out.append((seg, name, m.group(1), m.group(2).strip(), m.group(3).strip()))
    return out


def marks(note):
    """조작 칸의 모양 표시 → Counter(모양: 수). 「(밑줄)」 · 「(띠 — …)」은 하나다."""
    return Counter(SHAPE[s] for s in re.findall(r'[(\s](밑줄|띠|테두리)(?:\)| — )', note))


def result_last(ops):
    """앞 큐가 조작 결과를 띄우며 끝났나: 끝에서부터 기다림 · 굴리기를 건너 처음 만나는 것이 누르기 · 고르기이거나, 일부러 기다린 자리(long)면 그렇다."""
    for o in reversed(ops):
        if o[0] == 'wait' and o[1].get('long'):
            return True
        if o[0] in ('wait', 'settle', 'scroll'):
            continue
        return o[0] in ('click', 'select')
    return False


def short_hl(text, ops, coef):
    """강조가 짧게 떴다 지워지는 곳 → [(강조 구절 앞부분, 지우는 조작, 말 길이 초)]. 강조를 지우는 것은 map.mjs와 같다: 누르기 · 고르기 · 굴리기 · 입력,
    강조 없는 짚기(화살표가 떠난다), keep 없는 다음 강조. 시점이 없는 조작은 앞 조작의 시점에 하는 것으로 어림하고, 사이에 기다림이 있으면 알 수 없어 넘긴다."""
    pos, cur = [], 0
    for o in ops:
        v = o[-1]
        own = isinstance(v, dict) and 'at' in v
        if own:
            cur = text.index(v['at'])
        pos.append((cur, own))
    bad = []
    for i, o in enumerate(ops):
        if o[0] != 'point' or not o[1].get('hl'):
            continue
        waited = False
        for j in range(i + 1, len(ops)):
            q = ops[j]
            if q[0] in ('wait', 'settle'):
                waited = True
                continue
            if q[0] == 'point' and q[1].get('hl') and q[1].get('keep') is True:
                continue
            if not pos[j][1] and waited:
                break
            secs = speech_seconds(text[pos[i][0]:pos[j][0]], coef)
            if secs < MIN_HL:
                bad.append((text[pos[i][0]:pos[i][0] + 12], q[0], round(secs, 2)))
            break
    return bad


def build(md):
    rs, cues, coef = rows(md), [], load_coef()
    ids = [r[2] for r in rs]
    if ids != ORDER:
        sys.exit(f'대본의 큐 차례가 다르다 — 대본 {ids}')
    if set(OPS) - set(ids):
        sys.exit(f'대본에 없는 큐의 조작: {sorted(set(OPS) - set(ids))}')
    for seg, name, cid, text, note in rs:
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
        # 조작 칸의 모양 표시와 hl: 수와 모양이 같아야 한다
        want, got = marks(note), Counter(o[1]['hl'] for o in ops if o[0] == 'point' and o[1].get('hl'))
        if want != got:
            sys.exit(f'{cid}: 조작 칸의 모양 표시 {dict(want)} ≠ 조작 표의 hl {dict(got)}')
        bad = short_hl(text, ops, coef)
        if bad:
            sys.exit(f'{cid}: 강조가 짧게 떴다 지워진다(말 {MIN_HL}초 미만) — ' + ', '.join(f'「{a}…」→ {b} {s}초' for a, b, s in bad) + ' — 짚는 구절을 앞으로 당긴다')
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


def dump(doc, path):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')


def main():
    cues = build(SRC.read_text(encoding='utf-8'))
    if PICK:
        a, z = PICK[0].split('-')
        if a not in ORDER or z not in ORDER or ORDER.index(a) > ORDER.index(z):
            sys.exit(f'--고르기 범위가 큐 차례에 없다: {PICK[0]}')
        part = cues[ORDER.index(a):ORDER.index(z) + 1]
        dump({'voice_id': VOICE, 'model_id': MODEL, 'note': f'{OUT.name}의 {PICK[0]} 사본(--고르기)', 'cues': part}, PICK[1])
        print(f'{PICK[0]}: 큐 {len(part)} · 구간 {sorted({c["segment"] for c in part})} · 글자 {sum(len(c["text"]) for c in part)} → {PICK[1]}')
        return
    dump({'voice_id': VOICE, 'model_id': MODEL,
          'note': f'1회차 실습 06 전체과정관찰(두 과정 공통, 새 포털 main 305a5405). {SRC.name}에서 {Path(__file__).name}로 만든다 — 손으로 고치지 않는다. '
                  '모듈 segs/one06.mjs → segs/map.mjs. gap은 앞 말이 끝나고 이 말을 시작할 때까지의 초(영상 V-14).',
          'cues': cues}, OUT)
    by = {}
    for c in cues:
        by.setdefault((c['segment'], c['section']), []).append(c)
    hl = lambda cs, s=None: sum(1 for c in cs for o in c['ops'] if o[0] == 'point' and o[1].get('hl') and (s is None or o[1]['hl'] == s))
    for (n, name), cs in by.items():
        print(f'구간 {n} {name}: 큐 {len(cs)} · 조작 {sum(len(c["ops"]) for c in cs)} · 강조 {hl(cs)} · 글자 {sum(len(c["text"]) for c in cs)}')
    print(f'모두 큐 {len(cues)} · 구간 {len(by)} · 강조 {hl(cues)}(밑줄 {hl(cues, "underline")} · 띠 {hl(cues, "band")} · 테두리 {hl(cues, "box")}) · 글자 {sum(len(c["text"]) for c in cues)} → {OUT.name}')


if __name__ == '__main__':
    main()
