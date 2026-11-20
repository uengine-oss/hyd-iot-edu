# 통합반 2회차 실습 05 「포털 지식 지도 탐색」(2026-11 새 포털 판, 다시 찍는 판)의 큐 JSON을 대본에서 만든다. 손으로 고치지 않는다.
#   python3 통합_02_05_지식지도탐색_큐만들기.py [<대본.md>]  → 같은 폴더의 통합_02_05_지식지도탐색_큐.json
#   python3 통합_02_05_지식지도탐색_큐만들기.py --고르기 <처음 큐>-<끝 큐> <출력.json>  → 그 범위(대본 표의 차례 기준)의 큐만 담은 사본(git 밖에 둔다)
#     대표 구간(영상 길 14)처럼 구간 일부만 찍을 때 쓴다. take.mjs는 고른 구간의 모든 큐에 음성이 있어야 녹화하므로, 산 큐만 담은 사본을 준다.
#   대본을 주지 않으면 산출물/통합반/실습/02회차/대본/05_실습_지식지도탐색.md를 읽는다.
# 대본 「## 절」 하나가 구간 하나이고, 표의 한 줄(| kNNNN | 발화 | 조작 |)이 큐 하나다. 큐의 차례는 표의 차례다(번호의 차례가 아니다). 글은 발화 칸 그대로다.
# 쉼(gap, 초): 조작 칸의 「쉼: 큐 1.3 · 구간 2.3 · 결과 뒤 2.0 · 잇기 0.6」은 그 큐의 말이 끝난 뒤 다음 큐를 시작할 때까지의 쉼이다(영상 V-14).
#   map.mjs의 gap은 「이 큐 앞 쉼」이므로, 큐의 gap에는 바로 앞 큐의 조작 칸 값을 넣는다. 첫 큐는 2.3이고, 「쉼:」이 없어도 되는 큐는 마지막 큐 하나뿐이다.
# 조작은 아래 표(OPS, 큐 id → 촬영도구/segs/map.mjs 조작 [조작, 대상, 시점])다. 시점은 {'at': '발화 속 구절'}(그 구절이 시작하는 글자 비율)이거나 생략(앞 조작이 끝나면 바로).
# 강조(영상 V-14 · V-11): 조작 칸에서 짚는 대상 뒤의 (밑줄) · (띠) · (테두리)마다 그 짚기 대상에 hl(underline · band · box)을 준다.
#   keep은 앞 강조를 지우지 않고 함께 두는 자리다(조작 칸의 「함께 둔다 · 둔 채」 — True는 모두, 1은 먼저 뜬 하나만 남긴다).
# 멈춘다(큐 id를 대며): 대본의 큐에 조작 표가 없을 때, 조작 표에 대본에 없는 큐가 있을 때, 시점 구절이 발화에 없거나 차례가 거꾸로일 때,
#   조작 칸의 모양 표시 수 · 모양과 그 큐의 hl 수 · 모양이 다를 때, 「쉼:」을 읽지 못할 때.
# 대상은 길뚫기(2026-11-20, 이 PC, main 295777676 포털, 근거 폴더 길뚫기/05_길뚫기.md)로 찾았다. 녹화 모듈은 촬영도구/segs/map05.mjs(→ map.mjs).
# 시작 상태 확인을 겸하는 기다림: 홈 「0건 처리 완료」(k0101), 지도 「항목 334 · 연결 729」(k0102), 강조 구절 「항목 334」 · 「연결 729」(k0202) — 다르면 그 큐에서 멈춘다.
import json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PICK = sys.argv[2:4] if sys.argv[1:2] == ['--고르기'] else None
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not PICK else ROOT / 'workspace/강의제작/산출물/통합반/실습/02회차/대본/05_실습_지식지도탐색.md'
OUT = HERE / '통합_02_05_지식지도탐색_큐.json'
VOICE, MODEL = 'tlxL9ilynpbOVf9sZXKh', 'eleven_v4'      # 영상 V-4
GAP_FIRST = 2.3
SHAPE = {'밑줄': 'underline', '띠': 'band', '테두리': 'box'}


def T(css, **k): return dict(css=css, **k)
def at(s): return [{'at': s}] if s else []
def P(t, s=None): return ['point', t, *at(s)]
def H(t, shape, s=None, keep=None): return ['point', {**t, 'hl': shape, **({'keep': keep} if keep else {})}, *at(s)]
def C(t, s=None): return ['click', t, *at(s)]
def SEL(t, label, s=None): return ['select', t, label, *at(s)]
def TYPE(text, s): return ['type', text, *at(s)]
def KEY(k, s): return ['key', k, *at(s)]
def W(t, secs=15): return ['wait', t, secs]
def LONG(t, secs): return ['wait', {**t, 'long': True}, secs]      # 지도를 읽어 다시 그리는 자리(이 PC 3.5~9초) — 6초를 넘어도 리허설 실패가 아니다
def SETTLE(secs=10): return ['settle', None, secs]
def CY(i, **k): return {'cy': i, **k}
def EDGE(a, b, *more): return {'cy': f'{a}>{b}', **({'also': [{'cy': f'{x}>{y}'} for x, y in more]} if more else {})}      # 지도의 화살표(여럿이면 함께 두르는 상자 하나)


# 지식 지도 화면
SUB = T('#view-ontology .page-head p', phrase='AI가 판단할 때 읽는 온톨로지입니다.', anchor='below')
STATS = lambda phrase: T('#ontoStats', phrase=phrase, anchor='below')      # 글 끝 오른쪽을 짚으면 같은 줄의 다음 숫자를 덮는다 — 구절 바로 밑
SEARCH = '#ontoSearch'
ASSET = T('#ontoAsset', anchor='center', dy=24)      # 누르지 않고 짚을 때는 칸 바로 밑(칸 위에 올리면 마우스 올림 테두리가 생긴다)
# 오른쪽 판(#ontoNode): 맨 위 「묶음 · 클래스」 · 큰 글 이름 · 회색 식별자, 속성 줄(dl.kv의 dt · dd), 「이어진 항목」 아래 관계 묶음(section.rel-group, data-dir=out | in)
N = '#ontoNode'
PANEL = T(N, anchor='center', dx=120, dy=-272)      # 판 전체를 두를 때 화살표는 판 머리 오른쪽 빈자리
MID = dict(anchor='margin')      # 줄 가운데 낱말은 그 줄 왼쪽 여백을 짚는다(낱말 바로 뒤를 짚으면 화살표가 이어지는 글을 덮는다)
KIND = lambda phrase, **k: T(f'{N} .node-head .gtag', phrase=phrase, **k)
NAME = lambda name, **k: T(f'{N} .node-head h2', phrase=name, **k)      # 구절을 주어 글만 칠한다(h2 상자는 판 너비다)
NID = lambda phrase=None, **k: T(f'{N} .node-head p.mono', **({'phrase': phrase} if phrase else {}), **k)
KV = f'{N} .node-sec:not(.node-fold) dl.kv'
ROW = lambda name: T(f'{KV} dt', exact=name, also=['next'], text=True)      # 속성 한 줄(이름 dt + 값 dd)의 글만
LINKS = T(f'{N} .node-sec > h3', phrase='이어진 항목')
G = lambda d, chip: f'{N} section.rel-group[data-dir="{d}"]:has(.chip[data-go="{chip}"])'      # 그 칩이 든 묶음(d: out 나가는 · in 들어오는)
GBOX = lambda d, chip, *more: T(G(d, chip) + ' > h4 .num', also=[{'css': G(d, chip)}, *({'css': G(dd, c)} for dd, c in more)])      # 묶음 전체(여럿이면 한데) — 화살표는 묶음 머리의 수 뒤
GHEAD = lambda d, chip, title: T(G(d, chip) + ' > h4', phrase=title, dx=22)      # 화살표는 이름 옆 수를 지나서(수를 덮지 않게)      # 묶음 머리의 이름
GNOTE = lambda d, chip: T(G(d, chip) + ' > h4 .rel-note', anchor='below')      # 들어오는 묶음 머리 오른쪽 끝의 작은 글(관계 이름)
CHIPS = lambda d, chip: T(G(d, chip) + ' .chips', dx=6)
CHIP = lambda i: T(f'{N} .chip[data-go="{i}"]')
CHIPP = lambda i: T(f'{N} .chip[data-go="{i}"]', dx=6)      # 누르지 않고 짚을 때는 칩 바로 오른쪽 틈(칩 위에 올리면 마우스 올림 색이 든다)
OPENED = lambda i, head: [W(NID() | {'exact': i}, 10), W(CY(head), 10)]      # 판이 그 항목으로 바뀌고 지도에 이웃이 모일 때까지

A1, A2 = 'asset:hyd-01', 'asset:hyd-02'
COOLER, TS1, SYM, FM, CAUSE, PART = 'comp:cooler', 'sen:ts1', 'sym:ts1-rise', 'fm:cooler-cooling-loss', 'cause:cooler-fin-fouling', 'part:cooler-core'

OPS = {
 # 1. 여는 말 — 포털 홈(학생 첫 화면: 처리 건 0건). 화살표는 위 막대 「홈」 오른쪽 빈자리(map05.mjs의 rest)
 'k0101': [W(T('#mainStages a.stat:nth-child(4) .stat-value', contains='0건 처리 완료'), 20)],
 'k0102': [C(T('#menuList summary[data-menu="knowledge"]'), '펼치고'), C(T('#menuList a[data-tab="ontology"]'), '열게요'),
           LONG(T('#ontoStats', exact='항목 334 · 연결 729'), 30), W(CY('@node'), 30), SETTLE(8)],
 'k0103': [H(SUB, 'underline', '이 지도에 담긴')],
 # 2. 지도에서 설비 고르기 — 점은 이름표가 보이는 「팬 진동 상승」, 선은 그 점과 이웃 점(진동 상승)을 잇는 짧은 선(전체 지도에서 선은 흐려서 가운데 가까운 선 하나만 두르면 무엇을 두른 것인지 보이지 않는다)
 'k0201': [H(CY('pattern:fan-vibration'), 'box', '점 하나가'), H(EDGE('pattern:fan-vibration', 'sym:vs1-rise'), 'box', '점 사이의'),
           H(CY('title:resource'), 'underline', '자원,'), H(CY('title:diagnosis'), 'underline', '설비 진단 같은', keep=True)],
 'k0202': [H(STATS('항목 334'), 'underline', '항목 몇 개,'), H(STATS('연결 729'), 'underline', '연결 몇 개라고')],
 'k0203': [C(T(SEARCH), '지도 바로 위'), TYPE('유압 파워팩', '유압 파워팩이라고'), W(T('#ontoStats', contains='검색 결과 1개'), 10),
           KEY('Enter', '엔터를 누르면'), *OPENED(A1, 'head:R:HAS_COMPONENT')],
 # 3. 노드 읽기 — 클래스 · 이름 · 식별자
 'k0301': [H(PANEL, 'box', '오른쪽에 열린'), H(CY(A1), 'box', '이 노드 하나에', keep=True)],
 'k0302': [P(KIND('자원 · 설비'), '맨 위에'), H(KIND('설비'), 'underline', '뒤의 설비가'), H(KIND('자원', **MID), 'underline', '앞의 자원은'),
           H(NAME('HYD-01 유압 파워팩'), 'band', '큰 글씨가'), H(KIND('설비'), 'underline', '그러니까'), H(NAME('HYD-01 유압 파워팩'), 'band', keep=True)],
 'k0303': [H(NID(), 'underline', '이름 밑의'), H(NID('hyd-01'), 'underline', '쌍점 뒤에'), H(NAME('HYD-01', **MID), 'underline', '이름 앞에 붙은', keep=True),
           H(NID('asset', **MID), 'underline', '영어 낱말을')],      # 쌍점 한 글자의 밑줄은 보이지 않아 뺐다
 'k0304': [H(NID(), 'underline', '이렇게'), H(NAME('HYD-01 유압 파워팩'), 'band', '이름은'), H(NID(), 'underline', '이 값은')],
 # 4. 관계의 방향 읽기 — 지도의 화살표 묶음을 상자로 두르면 상자 선이 점 이름(「작동유 탱크」 · 가운데 「HYD-01 유압 파워팩」)을 가로지른다. 그래서 설비 점에서 건너편 점으로 화살표를 따라 옮긴 뒤 선 위 관계 이름(「→ 구성 요소」)에 밑줄을 긋는다. 화살표 하나(k0503 · k0504)는 그 선만 두른다
 'k0401': [H(LINKS, 'underline', '이어진 항목이라고'), H(GBOX('out', COOLER), 'box', '오른쪽 화살표가'), H(GBOX('in', 'proc:anomaly-response'), 'box', '왼쪽 화살표가'),
           H(GBOX('out', COOLER), 'box', '나가는 쪽부터')],
 'k0402': [H(GHEAD('out', COOLER, '구성 요소'), 'underline', '구성 요소라고'), H(CHIPS('out', COOLER), 'box', '그 아래 여섯 개가'),
           P(CY(A1), '가진다라고'), P(CY('comp:motor')), H(CY('head:R:HAS_COMPONENT'), 'underline'),
           H(CHIPS('out', COOLER), 'box', '가진다의 건너편에')],
 'k0403': [H(GBOX('out', COOLER), 'box', '그러니'), C(CHIP(COOLER), '가 볼게요'), *OPENED(COOLER, 'head:R:MONITORED_BY')],
 # 5. 구성 요소 — 오일 쿨러
 'k0501': [H(KIND('구성 요소'), 'underline', '오일 쿨러의'), H(NID(), 'underline', '이름 밑의 식별자도'), H(NID('comp', **MID), 'underline', '쌍점 앞이'),
           H(ROW('다른 이름'), 'band', '다른 이름이라는 칸도'), H(T(f'{KV} dd', phrase='열교환기'), 'underline', '열교환기라고도')],
 'k0502': [P(CY(COOLER), '나가는 묶음은'), P(CY('sen:ce')), H(CY('head:R:MONITORED_BY'), 'underline'), H(CY('head:R:USES_PART'), 'underline', keep=True),
           H(GBOX('out', TS1), 'box', '관측 센서 묶음은'), H(GBOX('out', PART), 'box', '교체 부품 묶음은'),
           H(GBOX('out', TS1), 'box', '이 쿨러는 센서'), H(GBOX('out', PART), 'box', '부품 하나를')],
 'k0503': [H(GBOX('in', A1), 'box', '이번에는'), H(GHEAD('in', A1, '설비'), 'underline', '설비라고'), H(CHIPP(A1), 'underline', '유압 파워팩이'),
           P(CY(A1), '가진다라는 관계를'), H(EDGE(A1, COOLER), 'box')],
 'k0504': [P(CY(A1), '이 화살표는'), H(EDGE(A1, COOLER), 'box'), H(CHIPP(A1), 'underline', '설비가 이 쿨러를'), H(GBOX('in', A1), 'box', '들어오는 묶음은')],
 'k0505': [H(ROW('다른 이름'), 'band', '쿨러의 판에는'), H(GBOX('out', TS1), 'box', '감시된다라는 관계를'), C(CHIP(TS1), '누를게요'), *OPENED(TS1, 'head:R:OBSERVES')],
 # 6. 센서 — 속성값과 관계
 'k0602': [H(ROW('단위'), 'band', '단위 칸에'), H(GBOX('in', COOLER), 'box', '관계를 건너'), H(ROW('단위'), 'band', '이 노드의 칸에서')],
 'k0601': [H(T(KV), 'box', '나머지 칸도'), H(ROW('가상 값'), 'band', '가상 값 칸에'), H(ROW('태그'), 'band', '태그는'), H(NID(), 'underline', '식별자와는')],
 'k0603': [H(NAME('유온 센서'), 'band', '센서 값이'), H(GBOX('in', SYM), 'box', '증상 묶음이에요'), H(GHEAD('in', SYM, '증상'), 'underline', '건너편 증상이'), H(CHIPP(SYM), 'underline', '유온 상승은')],
 'k0605': [H(GBOX('in', COOLER), 'box', '바로 위'), H(GBOX('in', SYM), 'box', '둘 다 이 센서에', keep=True),
           H(GNOTE('in', COOLER), 'underline', '오른쪽 끝에는'), H(GNOTE('in', SYM), 'underline', keep=True)],
 'k0604': [P(CHIPP(SYM), '여기서부터'), C(CHIP(SYM), '누릅니다'), *OPENED(SYM, 'head:R:INDICATES')],
 # 7. 증상에서 부품까지 — 1회차에 본 길
 'k0701': [H(KIND('설비 진단', **MID), 'underline', '판 맨 위'), H(GBOX('out', FM), 'box', '나가는 쪽에는'), C(CHIP(FM), '누를게요'), *OPENED(FM, 'head:R:OCCURS_IN')],
 'k0702': [H(GBOX('out', 'skill:sop-cool-14', ('out', 'skill:sop-cool-11')), 'box', '위쪽 두 묶음은'), H(GBOX('out', COOLER), 'box', '발생 위치라고'),
           H(CHIPP(COOLER), 'underline', '오일 쿨러에서')],
 'k0705': [H(GBOX('in', CAUSE), 'box', '원인은'), H(CHIPS('in', CAUSE), 'box', '이 원인 후보 셋에'), H(CHIPP(CAUSE), 'underline', '쿨러 핀 오염이었죠'),
           C(CHIP(CAUSE), '가 볼게요'), *OPENED(CAUSE, 'head:R:INVOLVES_PART')],
 'k0704': [H(NAME('쿨러 핀 오염'), 'band', '쿨러 핀 오염에서'), H(GBOX('out', PART), 'box', '관련 부품이라는'), C(CHIP(PART), '누릅니다'), *OPENED(PART, 'head:R:SUPPLIED_BY')],
 # 8. 부품 — 품번, 그리고 다시 쿨러로
 'k0801': [H(KIND('부품'), 'underline', '쿨러 코어의'), H(ROW('부품 번호'), 'band', '부품 번호가'), H(NID(), 'underline', '여기서는 식별자가'),
           H(ROW('부품 번호'), 'band', '품번은 속성으로'), H(GBOX('out', 'sup:c'), 'box', '공급사와'), H(GBOX('in', 'skill:sop-pur-11'), 'box', '조치 방법 묶음은')],
 'k0802': [H(GBOX('in', COOLER), 'box', '들어오는 쪽'), H(CHIPP(COOLER), 'underline', '오일 쿨러가')],
 'k0803': [H(KIND('자원', **MID), 'underline', '그 사이'), H(CHIPP(COOLER), 'underline', '이 오일 쿨러를'), C(CHIP(COOLER), '돌아가 볼게요'), *OPENED(COOLER, 'head:R:MONITORED_BY')],
 # 9. 다른 설비의 지도에서 같은 쿨러 찾기
 'k0901': [H(NAME('오일 쿨러'), 'band', '오일 쿨러도'), H(ASSET, 'box', '오른쪽 위 이 칸에서'), H(ASSET, 'box', '첫 번째 설비의')],
 'k0902': [H(NID(), 'underline', '이름 밑의 식별자를'), H(NAME('오일 쿨러'), 'band', '이름은 똑같이', keep=True)],
 # 설비를 바꾸면 지도를 다시 읽어 그린 뒤(이 PC 4~6.5초: 지도 응답 1~2초 + 흐름 이름 응답 약 1초 + 배치 약 2초) 판이 닫히고 지도가 전체로 돌아간다. 그동안 찾기 칸 아래 글은 「불러오는 중…」이다.
 # 찾기 칸의 「유압 파워팩」은 남아 둘째 설비의 점 하나가 밝다 — 그 안내 글이 뜰 때까지 기다린다. k0903의 둘째 문장(「몇 초 걸려요」)은 다시 그리는 동안의 말이고,
 # 판이 닫혔다는 말은 판이 닫힌 뒤의 새 큐 k0909가 한다(영상 V-2 — 길뚫기 말 제안 1)
 'k0903': [P(ASSET, '오른쪽 위 칸에서'), SEL(T('#ontoAsset'), 'HYD-02', '두 번째 설비'), LONG(T('#ontoHint', contains='「유압 파워팩」 글자가 든 항목 1개'), 30),
           W(T('#ontoStats', exact='항목 334 · 연결 729 · 검색 결과 1개'), 5)],
 'k0909': [W(T('#ontoStats', exact='항목 334 · 연결 729 · 검색 결과 1개'), 5)],
 # 찾기 칸에 글이 있으면 칸 오른쪽 끝에 ✕가 뜬다(마우스를 올리거나 칸에 들어가 있을 때) — 누르기의 기본 자리(칸 오른쪽 끝에서 20px 안쪽)가 그 ✕다
 # 자리 글 「ID」 바로 밑을 짚으면 화살표가 아래 줄 숫자(729)를 덮는다 — 자리 글 끝 바로 뒤(구절 가운데에서 오른쪽 47px)를 짚는다
 'k0904': [P(T(SEARCH), '지도 바로 위'), C(T(SEARCH), '지우면'), W(T('#ontoStats', exact='항목 334 · 연결 729'), 5),
           H(T(SEARCH, ph='ID', anchor='center', dx=47), 'underline', '이 ID가'), TYPE('comp:cooler', '넣고'), W(T('#ontoStats', contains='검색 결과 1개'), 10)],
 'k0905': [KEY('Enter', '누르면'), *OPENED(COOLER, 'head:L:HAS_COMPONENT')],
 'k0906': [H(NID(), 'underline', '이 식별자를'), H(ROW('다른 이름'), 'band', '다른 이름도', keep=1), H(GBOX('out', TS1, ('out', PART)), 'box', '센서와 부품도', keep=1),
           H(CHIPP(A2), 'band', '달라진 건', keep=1)],
 'k0907': [H(NID(), 'underline', '식별자가 같으면'), H(ASSET, 'box', '세 번째 설비로'), H(NAME('오일 쿨러'), 'band', '노드 하나로'), H(GBOX('in', A2), 'box', '그 노드를 가진다고')],
 # 10. 왜 하나로 세었나
 'k1001': [H(NAME('오일 쿨러'), 'band', '이론과 다르게')],
 'k1002': [H(GBOX('out', TS1), 'box', '어떤 센서가'), H(GBOX('in', FM), 'box', '어떤 고장이'), H(GBOX('out', PART), 'box', '갈아 끼울 부품이')],
 'k1007': [H(NAME('오일 쿨러'), 'band', '그래서'), H(CHIPP(PART), 'underline', '쿨러 코어를', keep=True)],
 'k1008': [P(ASSET, '어느 설비의')],      # 강조 없는 이동 — 앞 큐의 강조를 지운다. 사건 노드는 이 화면에 없어 짚지 않는다
 'k1003': [H(NAME('오일 쿨러'), 'band', '쿨러를 하나로 세면'), H(ASSET, 'box', '설비 세 대가', keep=True)],
 # 11. 맺음
 'k1101': [H(KIND('구성 요소'), 'underline', '클래스,'), H(NID(), 'underline', '식별자,'), H(ROW('다른 이름'), 'band', '속성,'),
           H(T(f'{N} .node-sec > h3', phrase='이어진 항목', also=[{'css': f'{N} .node-sec:has(> h3)'}]), 'box', '관계의 방향')],
 'k1102': [H(T(SEARCH, anchor='right', dy=-22), 'box', '찾기 칸에')],      # 칸에 글(comp:cooler)이 있어 칸 위에 올리면 ✕가 뜬다 — 칸 바로 위를 짚는다
}


def rows(md):
    """대본 본문(# 촬영 본문 끝 앞)의 절과 큐 줄 → [(구간 번호, 절 이름, 큐 id, 발화, 조작 칸)]."""
    body, out, seg, name = md.split('# 촬영 본문 끝', 1)[0], [], 0, ''
    for line in body.splitlines():
        if line.startswith('## '):
            seg, name = seg + 1, line[3:].strip()
            continue
        m = re.match(r'\| (k\d{4}) \| (.+?) \| (.+?) \|$', line)
        if m:
            out.append((seg, name, m.group(1), m.group(2).strip(), m.group(3).strip()))
    return out


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
        want = Counter(SHAPE[m] for m in re.findall(r'\((밑줄|띠|테두리)(?:\)| —)', note))
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
          'note': f'통합반 2회차 실습 05 포털 지식 지도 탐색(새 포털 main 295777676, 다시 찍는 판). {SRC.name}에서 {Path(__file__).name}로 만든다 — 손으로 고치지 않는다. '
                  '모듈 segs/map05.mjs → segs/map.mjs. gap은 앞 말이 끝나고 이 말을 시작할 때까지의 초(영상 V-14, 앞 큐 조작 칸의 「쉼:」).',
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
