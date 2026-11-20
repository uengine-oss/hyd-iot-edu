# 통합반 3회차 실습 04 「운전 조건과 성과 기준에 따른 조치 결과 비교하기」(2026-11 새 포털 판)의 큐 JSON을 대본에서 만든다. 손으로 고치지 않는다.
#   python3 통합_03_04_조치결과비교_큐만들기.py [<대본.md>]  → 같은 폴더의 통합_03_04_조치결과비교_큐.json
#   python3 통합_03_04_조치결과비교_큐만들기.py --고르기 <처음 큐>-<끝 큐> <출력.json>  → 그 범위(대본 표의 차례 기준)의 큐만 담은 사본(git 밖에 둔다)
#     대표 구간(영상 길 14)처럼 구간 일부만 찍을 때 쓴다. take.mjs는 고른 구간의 모든 큐에 음성이 있어야 녹화하므로, 산 큐만 담은 사본을 준다.
#   대본을 주지 않으면 산출물/통합반/실습/03회차/대본/04_실습_조치결과비교.md를 읽는다.
# 대본 「## 절」 하나가 구간 하나이고, 표의 한 줄(| tNNNN | 발화 | 조작 |)이 큐 하나다. 큐의 차례는 표의 차례다(번호의 차례가 아니다). 글은 발화 칸 그대로다.
# 쉼(gap, 초): 조작 칸의 「쉼: 큐 1.3 · 구간 2.3 · 결과 뒤 2.0 · 잇기 0.6」은 그 큐의 말이 끝난 뒤 다음 큐를 시작할 때까지의 쉼이다(영상 V-14).
#   map.mjs의 gap은 「이 큐 앞 쉼」이므로, 큐의 gap에는 바로 앞 큐의 조작 칸 값을 넣는다. 첫 큐는 2.3이고, 「쉼:」이 없어도 되는 큐는 마지막 큐 하나뿐이다.
# 조작은 아래 표(OPS, 큐 id → 촬영도구/segs/map.mjs 조작 [조작, 대상, 시점])다. 시점은 {'at': '발화 속 구절'}(그 구절이 시작하는 글자 비율)이거나 생략(앞 조작이 끝나면 바로).
# 강조(영상 V-14 · V-11): 조작 칸에서 짚는 대상 뒤의 (밑줄) · (띠) · (테두리)마다 그 짚기 대상에 hl(underline · band · box)을 준다. 「(띠 둘)」 · 「(띠 셋 — …)」은 그 수만큼이다.
#   keep은 앞 강조를 지우지 않고 함께 두는 자리다(조작 칸의 「함께 둔다 · 둔다 · 둘 · 셋」 — True는 모두, 1은 먼저 뜬 하나만 남긴다).
# 멈춘다(큐 id를 대며): 대본의 큐에 조작 표가 없을 때, 조작 표에 대본에 없는 큐가 있을 때, 시점 구절이 발화에 없거나 차례가 거꾸로일 때,
#   조작 칸의 모양 표시 수 · 모양과 그 큐의 hl 수 · 모양이 다를 때, 「쉼:」을 읽지 못할 때.
# 대상은 main 305a5405의 포털 코드(hitl.js · enterprise.js · whatif.js · kpi.js · app.js)와 그 판으로 떠 있는 포털의 화면에서 찾았다. 녹화 모듈은 촬영도구/segs/act04.mjs(→ map.mjs).
# 시작 상태 확인을 겸하는 기다림(다르면 그 큐에서 멈춘다): 홈 「0건 처리 완료」(t0101), 조치 방법 목록 첫 줄 「팬 최대 운전」(t0102), 규칙 판단 · 조건별 손익의 설비 HYD-01 · 이상 패턴 쿨러 성능 저하(t0301 · t0501),
#   처음 판단의 「가정한 조건 없음」 · 1순위 팬 최대 운전 · 「4개 가능」(t0302), 원격 수동의 「1개 가능 · 3개 제외」와 1순위 바뀜(t0402), 팬 30시간의 1순위 바뀜(t0405), 지난 판단 다섯 줄(t0407),
#   조건별 손익의 결론 「판단 순위와 손익 순위 모두 「팬 최대 운전」이 1순위입니다.」(t0502), 「1순위가 바뀌는 값」 둘째 줄이 납기 지연 위약금 · 바뀐 1순위 쿨러 핀 세척(t0508),
#   값을 넣은 뒤의 결론(t0514), 성과 지표 기간 「최근 24시간」 · 미달 0개 · 「달성」이 눌림(t0601), 인터록 여유 원래 목표 10 ℃ · 달성(t0607).
# 고르기 칸(select)은 글자 상자를 잴 수 없어 밑줄 대신 둘레 선을 준다(t0401 — 대본 조작 칸도 테두리). 태그가 갈린 글(「달성 → <b>미달</b>」)은 구절 하나로 잴 수 없어 밑줄 둘을 잇는다(t0608).
import json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PICK = sys.argv[2:4] if sys.argv[1:2] == ['--고르기'] else None
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not PICK else ROOT / 'workspace/강의제작/산출물/통합반/실습/03회차/대본/04_실습_조치결과비교.md'
OUT = HERE / '통합_03_04_조치결과비교_큐.json'
VOICE, MODEL = 'tlxL9ilynpbOVf9sZXKh', 'eleven_v4'      # 영상 V-4
GAP_FIRST = 2.3
SHAPE = {'밑줄': 'underline', '띠': 'band', '테두리': 'box'}
TIMES = {'': 1, ' 둘': 2, ' 셋': 3}


def T(css, **k): return dict(css=css, **k)
def at(s): return [{'at': s}] if s else []
def P(t, s=None): return ['point', t, *at(s)]
def H(t, shape, s=None, keep=None): return ['point', {**t, 'hl': shape, **({'keep': keep} if keep else {})}, *at(s)]
def C(t, s=None): return ['click', t, *at(s)]
def SEL(t, label, s=None): return ['select', t, label, *at(s)]
def TYPE(text, s=None): return ['type', text, *at(s)]
def KEY(k, s=None): return ['key', k, *at(s)]
def CLEAR(): return ['clear']      # 들어가 있는 입력칸의 글 전체 고르기(뒤에 KEY('Delete'))
def SCROLL(t, s=None, **k): return ['scroll', {**t, **k}, *at(s)]      # top=창 위에서 대상 위끝까지 px, bottom=창 아래에서 대상 아래끝까지 px
def W(t, secs=15): return ['wait', t, secs]
def LONG(t, secs): return ['wait', {**t, 'long': True}, secs]      # 서버가 다시 계산하는 자리 — 6초를 넘어도 리허설 실패가 아니다
def SETTLE(secs=10): return ['settle', None, secs]
def TEXT(css, **k): return T(css, also=[], text=True, **k)      # 요소 상자가 아니라 그 안 글자만 두르거나 칠한다(줄 전체가 칸인 요소)
def BOTH(css, *more, **k): return T(css, also=[{'css': c} for c in more], **k)      # 대상과 more를 함께 두르는 상자 하나(화살표는 대상에 둔다)


MID = dict(anchor='margin')      # 줄 가운데 낱말은 그 줄 왼쪽 여백을 짚는다(낱말 바로 뒤를 짚으면 화살표가 이어지는 글을 덮는다)
MENU = lambda m: T(f'#menuList summary[data-menu="{m}"]')
TAB = lambda t: T(f'#menuList a[data-tab="{t}"]')
HEAD = lambda v: T(f'#view-{v} .page-head h1', anchor='after', dy=-8)      # 화면 제목 — 메뉴를 누른 뒤 화살표를 메뉴 줄에서 떼어 둘 자리

# 2절. 조치 방법(hitl.js renderSkillList · renderSkillDetail)
SL, SK = '#skillList', '#skillDetail'
SROW = lambda i: f'{SL} .row[data-skill="skill:{i}"]'
FAN, FIN = 'sop-cool-11', 'sop-cool-14'
OPENED = lambda i, name: W(T(f'{SK}[data-key="skill:{i}"] .pane-title h2', contains=name), 10)
STEPS = f'{SK} ol.sk-steps'
STEP = lambda n, **k: T(f'{STEPS} li:nth-child({n})', **k)
SM = dict(anchor='margin', dx=-18)      # 번호 줄 가운데 낱말: 번호 왼쪽 빈자리(여백 바로 왼쪽은 번호 글자다)
TAG = lambda name: T(f'{SK} .pane-title h2 .tag', exact=name, anchor='after', dy=-10)      # 이름 옆 종류 알약(화살표가 아랫줄 설명 글을 덮지 않게 조금 위)
KV1 = f'{SK} .panel-sec:not(.pane-fold) > dl.kv'      # 「대상 고장 유형」 · 「승인 역할」
KV1ROW = lambda name: T(f'{KV1} dt', exact=name, also=['next'], text=True)
KFOLD = f'{SK} .pane-fold details.fold'      # 접힌 「연결된 지식」
KV2 = f'{KFOLD} dl.kv'
RULES = lambda phrase, **k: T(f'{KV2} dd', contains='제외 — PLC 운전 모드가', phrase=phrase, **k)      # 「적용 규칙」의 값 칸(줄은 <br>로 갈린 글자 조각이다 — 줄의 차례는 정해져 있지 않아 글로 찾는다)
R_OUT = '제외 — PLC 운전 모드가 REMOTE_AUTO가 아니면 원격 조치 SOP-COOL-11~13을 쓰지 않는다.'
R_PEN = '감점 — 팬 100 % 연속 운전이 이미 24시간을 넘긴 경우 팬 수명 손실 20만 원 감점. 감점 지표는 원문에 특정되지 않아 보전비를 검토용으로 연결함.'

# 3 · 4절. 규칙 판단(index.html #decForm, enterprise.js renderDecision · renderDecPast)
DR = '#decResult'
FIELD = lambda i, **k: BOTH(f'#decForm label[for="{i}"]', f'#{i}', **k)      # 칸 이름과 입력 칸을 함께(화살표는 칸 이름 뒤 빈자리)
RUN = T('#decRun')
FACT = lambda n: f'{DR} .turn-facts > div:nth-child({n})'      # 결론 아래 숫자 넷(셋째가 「조치 후보」)
ASSUMED = lambda s: T(f'{DR} .panel-sec > p.muted', contains=s)      # 「가정한 조건 …」 줄
CHANGED = f'{DR} p[data-dec-change]'      # 「앞 판단과 견주면 …」 줄
OPTS = f'{DR} table.opts'
OROW = lambda code: T(f'{OPTS} tbody tr', contains=code)      # 조치 후보 줄(절차 번호로 찾는다)
MORE = f'{DR} details.dec-more'
INP = f'{MORE} [data-dec-body="inputs"] table'
IROW = lambda name: T(f'{INP} tbody tr', contains=name)
RUL = f'{MORE} [data-dec-body="rules"] table'
REMOTE_ROW = dict(exact='PLC 운전 모드가 REMOTE_AUTO가 아니면 원격 조치 SOP-COOL-11~13을 쓰지 않는다.규정 적합성팬 최대 운전해당 없음')      # 대상이 「팬 최대 운전」인 원격 자동 규칙 줄
PAST = lambda n: T(f'#decPast .row[data-dec-past="{n}"]')
MODE = T('#decMode')
FANH = T('#decFan', anchor='center')      # 숫자 칸의 오른쪽 끝은 올림 · 내림 단추다 — 가운데를 누른다

# 5절. 조건별 손익(whatif.js)
WI = '#whatifView'
WO = f'{WI} .io-out'
WHEAD = f'{WO} .panel-head h2'
BASE_SAYS = '판단 순위와 손익 순위 모두 「팬 최대 운전」이 1순위입니다.'
WOPT = f'{WO} table.opts'
COL = lambda n, **k: BOTH(f'{WOPT} thead th:nth-child({n})', f'{WOPT} tbody tr:last-child td:nth-child({n})', **k)      # 표의 열 하나(1 순위 · 3 정책 점수 · 5 손익 순위 · 6 예상 손익)
WCELL = lambda r, n, **k: T(f'{WOPT} tbody tr:nth-child({r}) td:nth-child({n})', **k)
MON = f'{WO} .panel-sec:has(> .seg[aria-label="내역을 볼 조치"])'      # 「손익 내역」 절
ITEMS = f'{MON} > .table-container table'
ITEM = lambda name: T(f'{ITEMS} tbody tr', contains=name)
CARD = lambda i: f'{MON} .seg button[data-wi-card="skill:{i}"]'
CALC = f'{MON} details.fold table'      # 접힌 「항목별 계산식과 출처」
FV = lambda v: f'#wiForm .field:has([data-wi-var="{v}"])'      # 업무 값 칸 하나(칸 이름 · 입력 칸 · 아래 작은 글)
FVBOX = lambda v: BOTH(f'{FV(v)} label', FV(v))
PEN, HOURV, DUE = 'penalty_per_h', 'hour_value', 'due_h'
BND = f'{WO} .panel-sec:has([data-wi-bound])'      # 「1순위가 바뀌는 값」 절
BT = f'{BND} table'
BTBOX = BOTH(f'{BND} > h3', BT, phrase='1순위가 바뀌는 값')
BR = f'{BT} tbody tr:nth-child(2)'      # 둘째 줄 = 납기 지연 위약금(t0508이 확인한다)
BCELL = lambda n, **k: T(f'{BR} td:nth-child({n})', **k)      # 1 순위 · 2 바꾸는 값 · 3 지금 · 4 바뀌는 값 · 5 바뀐 1순위
BGO = f'{BR} [data-wi-bound]'

# 6절. 성과 지표(kpi.js)
K = '#kpiView'
STAT = lambda g, **k: T(f'{K} [data-kpi-group="{g}"]', **k)      # 숫자 카드 넷(missed 미달 · met 달성 · open 판정하지 않음 · dead 계산할 수 없음)
KC = lambda i: f'{K} .kpi-card[data-kpi="msr:{i}"]'
AVAIL, MARGIN = 'availability', 'safety-margin'
SH = 'dialog[data-kpi-sheet][open]'
SHROW = lambda sec, name: T(f'{SH} {sec} dt', exact=name, also=['next'], text=True)
TRIAL = f'{K} details.kpi-trial'
TT = f'{TRIAL} table'
TROW = f'{TT} tbody tr:has([data-kpi-target="msr:{MARGIN}"])'      # 「인터록 여유」 줄
AL = f'{K} .alert:has([data-kpi-trial-reset])'      # 시험 판정 알림
WHY = f'{AL} .kpi-why li'

# 7절. 실시간 모니터링(app.js renderTrends)
U1 = '#monUnits .unit[data-asset="HYD-01"] .unit-head'

OPS = {
 # 1. 여는 말 — 포털 홈(학생 첫 화면: 처리 건 0건). 화살표는 위 막대 「홈」 오른쪽 빈자리(act04.mjs의 rest)
 't0101': [W(T('#mainStages a.stat:nth-child(4) .stat-value', contains='0건 처리 완료'), 20)],
 't0102': [C(MENU('knowledge'), '펼쳐서'), C(TAB('skills'), '열게요'), W(T(f'{SL} .row:first-child[aria-current="true"] .row-title', exact='팬 최대 운전'), 15), OPENED(FAN, '팬 최대 운전')],
 # 2. 조치 방법에서 SOP 찾기
 # 목록은 열아홉 줄이라 한 화면에 다 들어오지 않는다 — 첫 줄에서 보이는 줄까지 두른다
 't0201': [P(HEAD('skills'), '여기가'), H(BOTH(f'{SL} .row:first-child .row-title', f'{SL} .row:first-child', f'{SL} .row:nth-child(8)'), 'box', '왼쪽 목록의'), H(T(f'{SL} .row:first-child'), 'band', '한 줄이')],
 't0202': [H(T(f'{SL} .row:first-child .row-meta', phrase='설비 제어', **MID), 'underline', '앞의 것은'), H(T(f'{SL} .row:first-child .row-meta', phrase='쿨러 냉각 성능 상실'), 'underline', '뒤의 것은', keep=True),
           H(T(f'{SK} .pane-title h2', phrase='팬 최대 운전'), 'band', '오른쪽에는'), C(T(f'{SROW(FIN)} .row-title', exact='쿨러 핀 세척', anchor='after'), '누를게요'), OPENED(FIN, '쿨러 핀 세척')],
 't0203': [H(T(STEPS), 'box', '번호 붙은 줄 셋이')],
 't0204': [H(TEXT(f'{STEPS} li:nth-child(1)', contains='설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.'), 'band', '1번은'), H(STEP(1, phrase='LOCAL', **SM), 'underline', 'LOCAL,'),
           H(STEP(1, phrase='잠금(LOTO)', **SM), 'underline', '잠금이 따로', keep=True)],
 't0205': [H(STEP(2, phrase='고압수는 쓰지 않는다.', **SM), 'underline', '세게 쏘는 물은'), H(TEXT(f'{STEPS} li:nth-child(3)', contains='재가동 후 냉각 효율 CE가'), 'band', '3번은'), H(STEP(3, phrase='80 % 이상', **SM), 'underline', '기준 이상으로')],
 't0206': [H(T(f'{STEPS} li:nth-child(1) .sk-ref', exact='HM-8.7'), 'underline', '작은 글씨로'),
           H(BOTH(f'{STEPS} li:nth-child(1) .sk-ref', f'{STEPS} li:nth-child(2) .sk-ref', f'{STEPS} li:nth-child(3) .sk-ref'), 'box', '작업 단계마다')],
 't0207': [H(KV1ROW('대상 고장 유형'), 'band', '첫 줄은'), H(KV1ROW('승인 역할'), 'band', '승인 역할은'), H(T(f'{KV1} dd', exact='설비보전팀장'), 'underline', '설비보전팀장이라고')],
 't0208': [H(TAG('정비 요청'), 'box', '이름 옆에 붙은'), H(T(f'{KV1} dd .muted', exact='(근본 조치)'), 'underline', '괄호 안의')],
 't0209': [C(T(f'{SL} .row:first-child .row-title', exact='팬 최대 운전', anchor='after'), '팬 최대 운전입니다'), OPENED(FAN, '팬 최대 운전')],
 't0210': [H(TAG('설비 제어'), 'box', '종류가 설비 제어예요'), H(TEXT(f'{STEPS} li:nth-child(1)', contains='PLC 운전 모드가 REMOTE_AUTO인지 확인한다.'), 'band', '1번 단계가'),
           H(STEP(1, phrase='REMOTE_AUTO', **SM), 'underline', 'REMOTE_AUTO인지')],
 't0211': [H(STEP(2, phrase='100 % 연속 운전은 24시간 이내로 한다.', **SM), 'underline', '2번에는'), H(TEXT(f'{STEPS} li:nth-child(3)', contains='15분 재관측으로 HM-8.6 회복 판정을 한다.'), 'band', '3번은'),
           H(T(f'{KV1} dd .muted', exact='(완화 조치)'), 'underline', '완화 조치라고'), H(T(f'{KV1} dd', exact='운전원'), 'underline', '승인 역할도 운전원으로')],
 # 접힌 줄을 펼치면 「적용 규칙」의 아래 줄이 화면 밖으로 나간다 — 네 줄이 다 보이게 굴려 들인다
 't0212': [H(T(f'{KFOLD} > summary', phrase='연결된 지식'), 'band', '줄이 하나 접혀'), C(T(f'{KFOLD} > summary', phrase='연결된 지식', anchor='after'), '펼쳐 보겠습니다'),
           W(RULES(R_OUT), 5), SCROLL(T(f'{KV2} dd', contains='제외 — PLC 운전 모드가'), bottom=90)],
 't0213': [H(T(f'{KV2} dt', exact='적용 규칙'), 'underline', '적용 규칙을'), H(RULES(R_OUT, **MID), 'band', '제외라는 말로 시작하는'), H(RULES(R_PEN, **MID), 'band', '감점으로 시작하는 줄에는'),
           H(RULES(R_OUT, **MID), 'band', '이론의 결정표에서'), H(RULES(R_PEN, **MID), 'band', keep=True)],
 't0214': [P(RULES(R_OUT, anchor='margin', dx=-6), '절차는')],      # 강조 없는 이동 — 앞 큐의 띠 둘을 지운다
 # 3. 규칙 판단 — 입력값 · 적용 규칙 · 조치 후보
 't0301': [C(MENU('trial'), '누르고'), C(TAB('decision'), '열게요'), W(T('#decAsset:has(option[value="HYD-01"]:checked)'), 15), W(T('#decPattern:has(option[value="COOLER_DEGRADATION"]:checked)'), 5),
           W(T(f'{DR} .empty'), 5)],
 't0302': [P(HEAD('decision'), '여기는'), H(FIELD('decAsset'), 'box', '설비 칸에는'), H(FIELD('decPattern'), 'box', '이상 패턴 칸에는'), C(RUN, '누릅니다'),
           W(ASSUMED('없음 — 설비의 지금 값으로 판단했습니다.'), 10), W(T(f'{OPTS} tbody tr[data-pick] .opts-name b', exact='팬 최대 운전'), 5), W(T(f'{FACT(3)} dd', exact='4개 가능'), 5)],
 # 표의 줄이 두 줄씩이라 결과 첫 화면에서는 표 아래가 잘린다 — 표 제목을 위로 올려 표 전체를 들인다
 't0303': [SCROLL(T(f'{DR} .panel-sec:has(table.opts) > h3'), '오늘은 가운데', top=76), H(T(OPTS), 'box', '조치 후보 표를')],
 't0305': [H(T(f'{OPTS} thead tr'), 'band', '표의 줄마다'), H(T(f'{OPTS} tbody tr:first-child .badge'), 'underline', '종류와 승인 역할은'), H(T(f'{OPTS} tbody tr:first-child td.opts-role'), 'underline', keep=True),
           H(T(FACT(3)), 'box', '조치 후보 칸에는')],
 # 펼치면 탭 넷과 「판단에 쓴 값」 표(열 줄, 높이 약 640px)가 나온다 — 접힌 줄을 위로 올려 탭과 표 머리를 보이고(t0306), 표를 두를 때는 표 머리를 위 막대 바로 밑에 둔다(t0307)
 't0306': [H(T(f'{MORE} > summary', phrase='자세히 보기'), 'band', '자세히 보기라는'), C(T(f'{MORE} > summary', phrase='자세히 보기', anchor='after'), '펼치면'), W(T(INP), 5),
           SCROLL(T(f'{MORE} > summary'), top=64)],
 't0307': [SCROLL(T(INP), top=66), H(T(INP), 'box', '이 표가'), H(IROW('PLC 운전 모드'), 'band', '운전 모드 줄을'), H(T(f'{INP} tbody td', exact='SCADA · PLC (설비 제어)'), 'underline', '옆에 출처가'),
           H(IROW('팬 100 % 연속 운전 시간'), 'band', '팬 연속 운전 시간 줄은'), H(T(f'{INP} tbody td', exact='0 시간'), 'underline', '시간이라는 단위가'),
           H(IROW('PLC 운전 모드'), 'band', '이 둘이에요'), H(IROW('팬 100 % 연속 운전 시간'), 'band', keep=True)],
 # 「적용한 규칙」 표는 열아홉 줄이라 한 화면에 다 들어오지 않는다 — 열은 머리 칸에서 보이는 줄까지 칠한다
 't0308': [C(T(f'{MORE} [data-dec-pane="rules"]'), '누르면'), W(T(RUL), 5), SCROLL(T(f'{MORE} > summary'), top=64),
           H(BOTH(f'{RUL} thead th:nth-child(1)', f'{RUL} tbody tr:nth-child(6) td:nth-child(1)'), 'band', '줄 맨 앞의 문장이'),
           H(BOTH(f'{RUL} thead th:nth-child(2)', f'{RUL} tbody tr:nth-child(6) td:nth-child(2)'), 'band', '가운데 칸은')],
 't0310': [H(T(f'{RUL} tbody tr', **REMOTE_ROW), 'band', '가운데 칸이 팬 최대 운전인'), H(T(f'{RUL} tbody tr', phrase='해당 없음', **REMOTE_ROW), 'underline', '해당 없음이라고', keep=True)],
 't0309': [],      # 앞 큐의 띠와 밑줄을 그대로 둔다
 # 4. 조건 바꿔 보기 — 제외와 감점
 't0401': [P(T('#decForm details.io-more > summary', phrase='조건 바꿔 보기'), '왼쪽으로 돌아가서'), C(T('#decForm details.io-more > summary', phrase='조건 바꿔 보기', anchor='after'), '펼치면'),
           H(T('#decForm details.io-more .fold-body'), 'box', '칸이 넷'), H(BOTH('#decMode'), 'box', '지금 값 그대로라고')],
 't0402': [H(FIELD('decMode'), 'box', '여기서'), SEL(MODE, '원격 수동', '바꿔 볼게요'), C(RUN, '다시 누릅니다'), W(T(f'{FACT(3)} dd', exact='1개 가능 · 3개 제외'), 10),
           W(T(CHANGED, contains='1순위가 팬 최대 운전에서 쿨러 핀 세척(으)로 바뀌었습니다'), 5)],
 # 제외된 줄은 이름 아래 걸린 규칙 글이 붙어 높다 — 세 줄이 한 화면에 들어오게 표 머리를 위로 올린다
 't0403': [H(T(FACT(3)), 'box', '조치 후보 칸에'), SCROLL(T(f'{OPTS} thead'), '표에서는', top=70), H(BOTH(f'{OPTS} tbody tr[data-out]:nth-child(2)', f'{OPTS} tbody tr[data-out]:nth-child(4)'), 'box', '설비 제어가 들어 있는'),
           W(T(f'{OPTS} tbody tr:nth-child(2) .opts-name b', exact='팬 최대 운전'), 5),
           H(T(f'{OPTS} tbody tr:nth-child(2) td.num', exact='제외'), 'underline', '제외라고 적혀'), H(T(f'{OPTS} tbody tr:nth-child(2) .opts-why small', contains='제외 — PLC 운전 모드가'), 'underline', '어느 규칙에 걸렸는지도')],
 't0404': [H(T(f'{OPTS} tbody tr[data-pick]', contains='쿨러 핀 세척'), 'band', '남은 건'), H(T(f'{FACT(3)} dd small', phrase='개 가능'), 'underline', '가능이라니')],
 't0410': [H(TEXT(f'{DR} .panel-sec > p.muted', contains='가정한 조건 운전 모드 원격 수동'), 'band', '가정한 조건이라고'), H(TEXT(CHANGED), 'band', '그 아래 줄에는')],
 't0409': [SEL(MODE, '지금 값 그대로', '돌려놓고'), C(RUN, '다시 누르면'), W(ASSUMED('없음 — 설비의 지금 값으로 판단했습니다.'), 10), W(T(f'{FACT(3)} dd', exact='4개 가능'), 5),
           H(T(OPTS), 'box', '후보로 돌아옵니다')],
 't0405': [H(FIELD('decFan'), 'box', '맨 아래에 보이는 칸은'), H(T('#decForm label[for="decFan"]', phrase='(시간)'), 'underline', '단위는'), C(FANH, '삼십을 넣고'), TYPE('30'), C(RUN, '누릅니다'),
           W(T(CHANGED, contains='1순위가 팬 최대 운전에서 부하 70 %와 야간 핀 세척(으)로 바뀌었습니다'), 10)],
 't0406': [SCROLL(T(f'{OPTS} thead'), top=70), H(OROW('SOP-COOL-11'), 'band', '빠지지 않고 남아'), H(OROW('SOP-COOL-12'), 'band', keep=True),
           H(T(f'{OPTS} tbody tr:nth-child(2) .opts-why small', contains='감점 — 팬 100 % 연속 운전이 이미 24시간을 넘긴 경우'), 'underline', '감점이라고 적힌 글이')],
 't0411': [H(OROW('SOP-COOL-11'), 'band', '제외는'), H(OROW('SOP-COOL-12'), 'band', keep=True), H(TEXT(CHANGED), 'band', '표 위 줄을 보면')],
 't0407': [H(FIELD('decFan'), 'box', '넣어 본 값을'), C(FANH, '비우고'), CLEAR(), KEY('Delete'), C(RUN, '누르면'), W(ASSUMED('없음 — 설비의 지금 값으로 판단했습니다.'), 10),
           W(T('#decPast h3 .num', exact='5'), 5)],
 't0408': [H(T(f'{OPTS} tbody tr[data-pick]', contains='팬 최대 운전'), 'band', '처음과 같은 결과가'), H(T('#decPast'), 'box', '지난 판단 목록에는'),
           H(PAST(5), 'band', '지금 값 그대로인 줄은'), H(PAST(3), 'band', keep=True), H(PAST(1), 'band', keep=True)],
 # 5. 조건별 손익 — 값 하나를 바꿔 손익과 순위 보기
 't0501': [C(TAB('whatif'), '열게요'), W(T('#wiLoad', exact='기준 계산'), 15), W(T('#wiAsset:has(option:first-child:checked)'), 5), W(T('#wiPattern:has(option[value="COOLER_DEGRADATION"]:checked)'), 5)],
 't0502': [H(BOTH(f'{WI} label[for="wiAsset"]', '#wiAsset', '#wiPattern'), 'box', '설비와 이상 패턴은'), C(T('#wiLoad'), '누릅니다'), LONG(T(WHEAD, exact=BASE_SAYS), 30)],
 't0503': [H(T(WOPT), 'box', '결과 표에는'), H(COL(1, anchor='center'), 'band', '맨 앞의 순위는'), H(T(f'{WOPT} thead th', exact='정책 점수'), 'underline', '정책 점수라고'),
           H(COL(5), 'band', '오른쪽의 손익 순위는'), H(COL(6), 'band', '예상 손익으로')],
 't0520': [H(COL(1, anchor='center'), 'band', '그 두 길이'), H(COL(5), 'band', keep=True), H(T(f'{WOPT} tbody tr:first-child td.opts-rank .rank', exact='1'), 'underline', '추천은 앞의')],
 't0504': [H(TEXT(WHEAD), 'band', '맨 위 결론에'), H(T(f'{WO} .turn-facts dt', exact='판단 1순위'), 'underline', '판단 순위라고'), H(WCELL(1, 6), 'underline', '빼기 표시는')],
 't0505': [SCROLL(T(f'{MON} > h3'), '이 금액이', top=70), H(T(ITEMS), 'box', '항목마다 금액이'), H(T(f'{ITEMS} tbody tr:last-child', contains='합계'), 'band', '합계입니다'),
           H(T(f'{CARD(FAN)}[aria-pressed="true"]', exact='팬 최대 운전', anchor='below'), 'box', '팬 최대 운전이 골라져'), H(ITEM('에너지비(팬)'), 'band', '에너지비와'), H(ITEM('고장 위험'), 'band', '고장 위험이라는', keep=True)],
 't0506': [C(T(CARD(FIN), exact='쿨러 핀 세척'), '바꿔 보면'), W(T(f'{CARD(FIN)}[aria-pressed="true"]'), 5), H(ITEM('생산 감소'), 'band', '생산 감소와'), H(ITEM('납기 지연 위약금'), 'band', '납기 지연 위약금,', keep=True),
           H(ITEM('정비 작업비'), 'band', '정비 작업비입니다', keep=True)],
 # 계산식 표의 한 줄은 출처가 여러 줄이라 높다 — 줄은 항목 이름만 칠한다
 't0507': [C(T(f'{MON} details.fold:not(.raw) > summary', phrase='항목별 계산식과 출처', anchor='after'), '펼치면'), W(T(CALC), 5),
           H(TEXT(f'{CALC} tbody td:first-child', exact='납기 지연 위약금'), 'band', '납기 지연 위약금은'), H(T(f'{CALC} tbody td:nth-child(2)', phrase='위약금 120만원/시간 × 지연', contains='위약금 120만원/시간 × 지연', **MID), 'underline', '한 시간 늦을 때마다'),
           H(T(f'{CALC} tbody td:nth-child(3)', contains='납기 지연 위약금 120 만원/시간'), 'box', '출처 칸에는'),
           H(T(f'{CALC} tbody td:nth-child(3) div', exact='데이터 · 업무 DB ERP · 납기 지연 위약금 120 만원/시간', phrase='업무 DB', **MID), 'underline', '업무 DB라고')],
 # 업무 값을 고르면 왼쪽 판이 길어져(칸 아홉) 화면과 함께 굴러간다. map.mjs는 붙박이(sticky) 칸 안의 대상을 굴려 들이지 못하므로, 오른쪽 결과의 한 자리를 굴려
 # 왼쪽 칸과 오른쪽 표가 함께 보이는 자리를 잡는다(t0508 · t0511 · t0513 · t0515). 「1순위가 바뀌는 값」 제목을 위에서 99px에 두면 왼쪽 칸 여섯과 그 표가 함께 보인다
 't0508': [H(T('#wiForm legend', exact='바꿔 볼 것'), 'underline', '바꿔 볼 것이라고'), C(T(f'{WI} [data-wi-tab="values"]'), '누릅니다'), LONG(T(BGO), 40), SCROLL(T(f'{BND} > h3'), top=99),
           W(BCELL(2, exact='납기 지연 위약금'), 5), W(BCELL(5, exact='쿨러 핀 세척'), 5)],
 # 업무 값 칸은 아홉이라 한 화면에 다 들어오지 않는다 — 첫 칸에서 보이는 여섯째 칸까지 두른다
 't0509': [H(BOTH(f'{FV(DUE)} label', FV(DUE), FV('mtbf_h')), 'box', '칸이 여러 개'), H(T(f'{FV(DUE)} label', phrase='(시간)'), 'underline', '칸 이름 옆 괄호가'), H(T(f'{FV(DUE)} .field-hint'), 'underline', '칸 아래 작은 글씨는', keep=True),
           H(FVBOX(PEN), 'box', '납기 지연 위약금을'), H(T(f'{FV(PEN)} .field-hint', phrase='120 만원/시간'), 'underline', '백이십만 원입니다')],
 # 줄의 띠는 그 줄을 읽는 동안(t0510 · t0517) 두고, 밑줄만 옮긴다
 't0510': [H(BTBOX, 'box', '1순위가 바뀌는 값이라는'), H(T(BR, contains='납기 지연 위약금'), 'band', '납기 지연 위약금 줄을'), H(BCELL(3), 'underline', '지금 값과 바뀌는 값이', keep=1), H(BCELL(4), 'underline', keep=True),
           H(BCELL(5), 'underline', '바뀐 1순위가', keep=1)],
 't0517': [H(BCELL(1, exact='판단 순위'), 'underline', '줄 맨 앞에는', keep=1), H(BCELL(4), 'underline', '두 선이 엇갈리던 곳이', keep=1)],
 't0519': [H(FVBOX(HOURV), 'box', '시간당 생산 가치 칸도'), H(BTBOX, 'box', '이 표에는'), H(T(BR, contains='납기 지연 위약금'), 'band', '납기 지연 위약금이 답을')],
 't0514': [H(T(BGO, anchor='right'), 'box', '줄 끝에 있는 단추'), C(T(BGO), '누르면'), W(T('#wiReset'), 15),
           W(T(WHEAD, contains='판단 1순위는 「쿨러 핀 세척」, 손익 1순위는 「팬 최대 운전」입니다'), 5), H(FVBOX(PEN), 'box', '왼쪽 칸에 그 값이')],
 't0511': [SCROLL(T(f'{WO} .panel-sec:has(table.opts) > h3'), '위쪽 결과 표를', top=70), H(T(f'{WO} .panel-sec > h3 .muted', exact='기준 → 시험값'), 'underline', '화살표 앞이'), H(TEXT(f'{WOPT} tbody tr:first-child td.opts-name', contains='쿨러 핀 세척'), 'band', '맨 위로 올라왔습니다'),
           H(WCELL(1, 6, anchor='below'), 'underline', '예상 손익의 손해가'), H(WCELL(1, 3, anchor='below'), 'underline', '점수도 올라서', keep=True)],
 't0518': [H(COL(5), 'band', '손익 순위는 그대로'), W(T(f'{WOPT} tbody tr:nth-child(2) .opts-name b', exact='팬 최대 운전'), 5), H(WCELL(2, 5, exact='1위'), 'underline', '팬 최대 운전이 가장'),
           H(TEXT(WHEAD), 'band', '맨 위 결론에도')],
 't0512': [H(BCELL(3), 'underline', '지금 값과 바뀌는 값이'), H(BCELL(4), 'underline', keep=True)],
 't0513': [H(T(f'{WO} .panel-sec:has(#wiReset) [role="status"]'), 'band', '안내가 한 줄'), C(T('#wiReset'), '누를게요'), W(T(WHEAD, exact=BASE_SAYS), 10), SCROLL(T(WOPT), top=150),
           H(T(WOPT), 'box', '표가 기준 값으로'), H(FVBOX(PEN), 'box', '왼쪽 칸도')],
 # [기준 다시 계산]은 결과와 왼쪽 칸을 지웠다가 다시 그린다(약 5초) — 「1순위가 바뀌는 값」의 단추가 다시 뜰 때까지 기다린다
 't0515': [H(T('#wiLoad', exact='기준 다시 계산', anchor='right'), 'box', '기준 다시 계산 단추를'), C(T('#wiLoad'), '누르면'), LONG(T(BGO), 40), W(T(WHEAD, exact=BASE_SAYS), 5), SCROLL(T(WOPT), top=150)],
 't0516': [H(T(f'{FV(PEN)} .field-hint', phrase='120 만원/시간'), 'underline', '칸 아래를')],
 # 6. 성과 지표 — KPI 목표를 바꿔 판정 보기
 't0601': [C(MENU('system'), '펼치고'), C(TAB('kpi'), '엽니다'), LONG(T(f'{K} .kpi-stats'), 40), W(T(f'{K} [data-kpi-period="24h"][aria-pressed="true"]'), 5),
           W(T(f'{K} [data-kpi-group="missed"] .stat-value', exact='0개'), 5), W(T(f'{K} [data-kpi-group="met"][aria-pressed="true"]'), 5)],
 't0602': [H(T(KC(AVAIL)), 'box', '카드 하나가'), H(T(f'{K} .kpi-persp .sec-head h2', exact='내부 프로세스'), 'underline', '내부 프로세스라는')],
 't0611': [H(T(f'{K} .kpi-stats'), 'box', '위쪽 숫자 네 칸은'), H(STAT('missed', anchor='below'), 'box', '앞의 두 칸이'), H(STAT('met', anchor='below'), 'box', keep=True),
           H(STAT('open', anchor='below'), 'box', '나머지 두 칸은'), H(STAT('dead', anchor='below'), 'box', keep=True), H(STAT('met', anchor='below'), 'box', '지금 눌려 있는')],
 't0603': [H(T(f'{KC(AVAIL)} .stat-value'), 'underline', '큰 숫자가'), H(T(f'{KC(AVAIL)} .stat-note', phrase='목표 95 %'), 'underline', '그 아래에는 목표값이'), H(T(f'{KC(AVAIL)} .stat-pill .tag', exact='달성'), 'box', '달성이라고'),
           C(T(f'{KC(AVAIL)} .kpi-name', anchor='after'), '누르면'), W(T(f'{SH} .sheet-head h2', contains='설비 가동률'), 10)],
 't0604': [H(T(f'{SH} .sheet-head p.muted', exact='내부 프로세스 › 설비 가용성 확보'), 'underline', '맨 위 작은 글씨에는'), H(SHROW('.sheet-body > dl.kv', '지표 종류'), 'band', '지표 종류는'),
           H(SHROW('.sheet-body > dl.kv', '받치는 목표'), 'band', '받치는 목표에는', keep=True)],
 't0605': [H(SHROW('.kpi-sheet-sec dl.kv', '식'), 'band', '식과 원천이'), H(SHROW('.kpi-sheet-sec dl.kv', '원천'), 'band', keep=True),
           H(T(f'{SH} .kpi-sheet-sec dl.kv dd', contains='Σ(관측 분', phrase='보호 정지 분', **MID), 'underline', '보호 정지로')],
 't0606': [C(T(f'{SH} [data-kpi-sheet-close]'), '닫으면'), H(T(f'{TRIAL} > summary', phrase='목표값 바꿔 보기'), 'band', '목표값 바꿔 보기라는'), C(T(f'{TRIAL} > summary', phrase='목표값 바꿔 보기', anchor='after'), '펼치면'),
           W(T(TT), 5), SCROLL(T(f'{TRIAL} > summary'), top=70), H(T(f'{TT} thead th', exact='원래 목표'), 'underline', '원래 목표와'), H(T(f'{TT} thead th', exact='시험 목표'), 'underline', keep=True)],
 # 시험 목표 칸에는 id가 없어 map.mjs의 type(들어가 있는 칸의 id를 확인한다)을 쓰지 못한다 — 숫자 키 둘로 넣는다
 't0607': [H(T(TROW, contains='인터록 여유'), 'band', '인터록 여유 줄을'), H(T(f'{TROW} td:nth-child(2)', exact='10 ℃'), 'underline', '원래 목표는'), H(T(f'{TROW} td:nth-child(4)', exact='달성'), 'underline', '지금 판정은'),
           C(T(f'{TROW} input', anchor='center'), '이십을 넣고'), KEY('2'), KEY('0'), C(T(f'{K} [data-kpi-trial-run]'), '누릅니다'), LONG(T(f'{AL} h2', exact='시험 목표 1개를 적용해 판정한 결과입니다'), 30)],
 # 알림의 한 줄은 「…목표 10 → <b>20</b> · 달성 → <b>미달</b>」로 태그가 갈려 있다 — 밑줄 둘을 이어 한 줄로 보이게 한다
 't0608': [H(BOTH(f'{AL} h2', AL), 'box', '안내가 떴어요'), H(T(WHY, phrase='달성 →', **MID), 'underline', '달성에서 미달로'), H(T(f'{WHY} b:last-child', exact='미달'), 'underline', keep=True),
           H(T(WHY, phrase='목표 10 →', **MID), 'underline', '목표를 십에서 이십으로', keep=True), H(T(f'{WHY} b:nth-of-type(2)', exact='20'), 'underline', keep=True), H(STAT('missed', anchor='below'), 'box', '숫자 칸의 미달도')],
 't0609': [H(T(f'{AL} section p:first-child', phrase='지식 그래프의 목표값(Measure.target)은 읽기만 했고 그대로입니다'), 'underline', '읽기만 했고'), C(T(f'{AL} [data-kpi-trial-reset]'), '눌러 볼게요'),
           LONG(T(f'{K} [data-kpi-group="missed"] .stat-value', exact='0개'), 30), W(T(KC(MARGIN)), 5)],
 't0610': [H(T(KC(MARGIN)), 'box', '달성으로 돌아왔고'), H(T(f'{KC(MARGIN)} .stat-note', phrase='목표 10 ℃'), 'underline', '목표도 십 도')],
 # 7. 설비는 그대로인지 확인하기
 't0701': [C(MENU('plant'), '눌러 펼치고'), C(TAB('trends'), '엽니다'), W(T(f'{U1} b', exact='HYD-01'), 15), SETTLE(6)],
 't0702': [H(TEXT(U1), 'band', '맨 위 줄을'), H(T(f'{U1} [data-f="state"] .tag', exact='운전 중'), 'box', '운전 중이라고'), H(T(f'{U1} [data-f="mode"]', exact='원격 자동'), 'underline', '운전 모드는 원격 자동입니다')],
 't0704': [H(T('#menuList a[data-menu="instances"]', anchor='right', dx=44), 'box', '처리 건 옆에')],      # 메뉴 줄 바로 오른쪽 빈자리(줄 위에 올리면 마우스 올림 색이 든다)
 't0705': [P(T('#view-trends .page-head p'), '오늘은')],      # 강조 없는 이동 — 앞 큐의 테두리를 지운다
}


def rows(md):
    """대본 본문(# 촬영 본문 끝 앞)의 절과 큐 줄 → [(구간 번호, 절 이름, 큐 id, 발화, 조작 칸)]."""
    body, out, seg, name = md.split('# 촬영 본문 끝', 1)[0], [], 0, ''
    for line in body.splitlines():
        if line.startswith('## '):
            seg, name = seg + 1, line[3:].strip()
            continue
        m = re.match(r'\| (t\d{4}) \| (.+?) \| (.+?) \|$', line)
        if m:
            out.append((seg, name, m.group(1), m.group(2).strip(), m.group(3).strip()))
    return out


def marks(note):
    """조작 칸의 모양 표시 → Counter(모양: 수). 「(밑줄)」 · 「(띠 — …)」은 하나, 「(띠 둘)」 · 「(… 띠 둘)」은 둘, 「(띠 셋 — …)」은 셋."""
    want = Counter()
    for shape, n in re.findall(r'[(\s](밑줄|띠|테두리)( 둘| 셋)?(?:\)| — )', note):
        want[SHAPE[shape]] += TIMES[n]
    return want


def build(md):
    rs, cues = rows(md), []
    ids = [r[2] for r in rs]
    if len(set(ids)) != len(ids):
        sys.exit(f'대본에 같은 큐 id가 두 번: {sorted(i for i, n in Counter(ids).items() if n > 1)}')
    if set(ids) - set(OPS):
        sys.exit(f'조작 표(OPS)에 없는 대본 큐: {[i for i in ids if i not in OPS]}')
    if set(OPS) - set(ids):
        sys.exit(f'대본에 없는 큐의 조작: {sorted(set(OPS) - set(ids))}')
    gap = GAP_FIRST
    for k, (seg, name, cid, text, note) in enumerate(rs):
        ops, last = OPS[cid], -1.0
        for o in ops:
            v = o[-1]
            if isinstance(v, dict) and 'at' in v:
                if v['at'] not in text:
                    sys.exit(f'{cid}: 발화에 없는 구절 「{v["at"]}」')
                f = text.index(v['at']) / len(text)
                if f < last:
                    sys.exit(f'{cid}: 조작 시점이 거꾸로 — 「{v["at"]}」')
                last = f
        # 조작 칸의 모양 표시와 hl: 수와 모양이 같아야 한다
        want = marks(note)
        got = Counter(o[1]['hl'] for o in ops if o[0] == 'point' and o[1].get('hl'))
        if want != got:
            sys.exit(f'{cid}: 조작 칸의 모양 표시 {dict(want)} ≠ 조작 표의 hl {dict(got)}')
        cues.append({'id': cid, 'segment': seg, 'section': name, 'text': text, 'gap': gap, 'ops': ops})
        m = re.search(r'쉼: (큐|구간|결과 뒤|잇기) (\d+(?:\.\d+)?)', note)
        if not m and k != len(rs) - 1:
            sys.exit(f'{cid}: 조작 칸에 「쉼: 큐 · 구간 · 결과 뒤 · 잇기 <초>」가 없다')
        gap = float(m.group(2)) if m else None
    return cues


def dump(doc, path):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')


def main():
    cues = build(SRC.read_text(encoding='utf-8'))
    order = [c['id'] for c in cues]
    if PICK:
        a, z = PICK[0].split('-')
        if a not in order or z not in order or order.index(a) > order.index(z):
            sys.exit(f'--고르기 범위가 큐 차례에 없다: {PICK[0]}')
        part = cues[order.index(a):order.index(z) + 1]
        dump({'voice_id': VOICE, 'model_id': MODEL, 'note': f'{OUT.name}의 {PICK[0]} 사본(--고르기)', 'cues': part}, PICK[1])
        print(f'{PICK[0]}: 큐 {len(part)} · 구간 {sorted({c["segment"] for c in part})} · 글자 {sum(len(c["text"]) for c in part)} → {PICK[1]}')
        return
    dump({'voice_id': VOICE, 'model_id': MODEL,
          'note': f'통합반 3회차 실습 04 조치 결과 비교(새 포털 main 305a5405). {SRC.name}에서 {Path(__file__).name}로 만든다 — 손으로 고치지 않는다. '
                  '모듈 segs/act04.mjs → segs/map.mjs. gap은 앞 말이 끝나고 이 말을 시작할 때까지의 초(영상 V-14, 앞 큐 조작 칸의 「쉼:」).',
          'cues': cues}, OUT)
    by = {}
    for c in cues:
        by.setdefault((c['segment'], c['section']), []).append(c)
    hl = lambda cs: sum(1 for c in cs for o in c['ops'] if o[0] == 'point' and o[1].get('hl'))
    for (n, name), cs in by.items():
        print(f'구간 {n} {name}: 큐 {len(cs)} · 조작 {sum(len(c["ops"]) for c in cs)} · 강조 {hl(cs)} · 글자 {sum(len(c["text"]) for c in cs)}')
    print(f'모두 큐 {len(cues)} · 구간 {len(by)} · 강조 {hl(cues)} · 글자 {sum(len(c["text"]) for c in cues)} → {OUT.name}')


if __name__ == '__main__':
    main()
