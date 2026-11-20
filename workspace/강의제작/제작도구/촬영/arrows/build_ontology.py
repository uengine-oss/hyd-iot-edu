"""ARROWS 실습 원본: 쿨러 고장 이야기의 관계 그림(원 17 · 관계 21)을 arrows.app에서 그리는 큐(발화+조작).
이 파일 하나가 음성 목록·촬영 조작·수업 원고·두 과정 랩 산출물의 원본이다. 앱·음성 API는 호출하지 않는다.
사용: python build_ontology.py cues <cues.json 출력 경로>   # 촬영용 큐
      python build_ontology.py sync                       # 수업원고·시간·두 과정 대본 · 한 파일 가이드 동기화
"""
import json, re, sys
from pathlib import Path

# 원: Caption, Label. 이름·관계는 it/neo4j/v2/instances.cypher와 랩 HM-8 발췌를 따른다. 자리는 아래 POS다.
NODES = [
    ('HYD-01 유압 파워팩', 'Asset'),
    ('오일 쿨러', 'Component'),
    ('유온 센서 TS1', 'Sensor'),
    ('유온 상승', 'Symptom'),
    ('쿨러 냉각 성능 상실', 'FailureMode'),
    ('쿨러 핀 오염', 'Cause'),
    ('팬 최대 운전', 'Skill'),
    ('쿨러 핀 세척', 'Skill'),
    ('HM-8.5 즉시 완화 조치', 'ManualSection'),
    ('HM-8.7 근본 조치', 'ManualSection'),
    ('팬 구동 불량', 'Cause'),
    ('팬 점검', 'Skill'),
    ('HM-8.1 팬 벨트 점검', 'ManualSection'),
    ('주변 온도 상승', 'Cause'),
    ('캐비닛 환기 보강', 'Skill'),
    ('팬 베어링 열화', 'FailureMode'),
    ('진동 증가', 'Symptom'),
]
RELS = [
    ('HYD-01 유압 파워팩', 'HAS_COMPONENT', '오일 쿨러'),
    ('오일 쿨러', 'MONITORED_BY', '유온 센서 TS1'),
    ('유온 상승', 'OBSERVED_BY', '유온 센서 TS1'),
    ('유온 상승', 'INDICATES', '쿨러 냉각 성능 상실'),
    ('쿨러 냉각 성능 상실', 'OCCURS_IN', '오일 쿨러'),
    ('쿨러 핀 오염', 'CAUSES', '쿨러 냉각 성능 상실'),
    ('쿨러 냉각 성능 상실', 'MITIGATED_BY', '팬 최대 운전'),
    ('쿨러 냉각 성능 상실', 'REMEDIED_BY', '쿨러 핀 세척'),
    ('쿨러 핀 세척', 'ADDRESSES', '쿨러 핀 오염'),
    ('팬 최대 운전', 'REFERS_TO', 'HM-8.5 즉시 완화 조치'),
    ('쿨러 핀 세척', 'REFERS_TO', 'HM-8.7 근본 조치'),
    ('팬 구동 불량', 'CAUSES', '쿨러 냉각 성능 상실'),
    ('쿨러 냉각 성능 상실', 'REMEDIED_BY', '팬 점검'),
    ('팬 점검', 'ADDRESSES', '팬 구동 불량'),
    ('팬 점검', 'REFERS_TO', 'HM-8.1 팬 벨트 점검'),
    ('주변 온도 상승', 'CAUSES', '쿨러 냉각 성능 상실'),
    ('캐비닛 환기 보강', 'ADDRESSES', '주변 온도 상승'),
    ('쿨러 냉각 성능 상실', 'REMEDIED_BY', '캐비닛 환기 보강'),
    ('캐비닛 환기 보강', 'REFERS_TO', 'HM-8.7 근본 조치'),
    ('팬 베어링 열화', 'LEADS_TO', '쿨러 냉각 성능 상실'),
    ('진동 증가', 'INDICATES', '팬 베어링 열화'),
]
PROPS = {
    '쿨러 핀 오염': [('냉각 효율', '30초 평균 < 70 %'), ('팬 진동', '2분 평균 < 0.9 mm/s')],
    '팬 구동 불량': [('팬 진동', '2분 평균 ≥ 0.9 mm/s')],
    '주변 온도 상승': [('캐비닛 온도', '2분 평균 ≥ 35 ℃')],
}
KIND = dict(NODES)

# ── 큐 원본 ──────────────────────────────────────────────────────────────────
# 낭독 글은 대본원고.md(사용자가 확정한 대본의 발화 칸 그대로, 큐 id도 그대로)이고, 여기 MAP이 큐 id마다 그 글의 ▸ 자리 차례대로 조작을 단다.
# MAP의 한 칸 = ('A', 조작들): 큐 끝의 ▸ — 그 말이 끝날 때 한다 · ('P', 조작들): 바로 뒤 낱말을 말할 때 짚는다
#             · ('T', 조작들): 말 속 그 자리에서 바로 한다(말하면서 하는 누르기 · 적기 · Ctrl로 함께 고르기).
# 짚기에는 강조(영상 V-14 · V-11 — 합성 때 그리는 밑줄 · 띠 · 테두리 · 동그라미)가 붙는다. 모양은 대상 종류마다 기본값(hl_default)이고,
# P(대상, hl='underline' | 'band' | 'box' | 'circle')로 바꾸거나 hl='none'으로 뺀다. 큐에는 ['point', 대상, 모양]으로 나가고, 강조가 없으면 ['point', 대상]이다.
# 쉼은 큐 글과 조작으로 정한다(GAP과 gap_before) — 원고에 쉼 표시를 두지 않는다.
# 원은 처음부터 끝 자리에 놓는다: POS = 첫 원(HYD-01)을 (0, 0)으로 둔 끝 그림의 그림 좌표다(직각 격자 — 열 0 · 330 · 630 · 936 · 1260, 줄 −452 · −228 · 0 · 220 · 440).
# 첫 원은 새 그림의 빈 원을 원 안쪽을 잡고 왼쪽으로 끌어 옮긴 것이고(FIRST_X), 새 원을 놓는 자리는 그 첫 원의 화면 자리에서 잰다(촬영도구 ui.mjs growTo).
H, K, S, U, F = 'HYD-01 유압 파워팩', '오일 쿨러', '유온 센서 TS1', '유온 상승', '쿨러 냉각 성능 상실'
PO, MX, PC, M85, M87 = '쿨러 핀 오염', '팬 최대 운전', '쿨러 핀 세척', 'HM-8.5 즉시 완화 조치', 'HM-8.7 근본 조치'
FD, FI, M81, AT, CV, BR, VB = '팬 구동 불량', '팬 점검', 'HM-8.1 팬 벨트 점검', '주변 온도 상승', '캐비닛 환기 보강', '팬 베어링 열화', '진동 증가'
POS = {H: (0, 0), K: (330, 0), S: (330, 220), U: (630, 220), F: (630, 0), PO: (1260, -228), MX: (936, -228), PC: (1260, 0), M85: (936, -452),
       M87: (1260, 220), FD: (330, -228), FI: (330, -452), M81: (0, -452), AT: (936, 440), CV: (1260, 440), BR: (630, -228), VB: (630, -452)}
# 이 배치는 그림판 1703×1125px(CSS) · 원 크기 60 · 보기 배율 1 · 관계 글 가로(detail-orientation horizontal)에서 잘린 글 · 겹침이 없다. 그림판이 더 작은 화면 값에서는 들어가지 않는다.
FIRST_X = 130   # 첫 원을 끌어 놓는 자리: 그림판 왼쪽 끝에서 130px(높이는 그대로). 가장자리 114px(반지름 60 + 54) 안으로 끌면 arrows가 그림 전체를 줄인다
RED, GREEN = '#fca5a5', '#86efac'
# 판단할 사건 값 글상자(화면 위에 얹는 글 — 낭독하지 않음). 자리 'tr' = 그림판 오른쪽 위(이 배치에서 원이 없는 구석)
CASE = '냉각 효율 30초 평균 46.2 %\n팬 진동 2분 평균 0.575 mm/s\n캐비닛 온도 2분 평균 28 ℃'
CASE14 = '팬 진동 2분 평균 1.4 mm/s'
CASE38 = '냉각 효율 30초 평균 46.2 %\n팬 진동 2분 평균 0.575 mm/s\n캐비닛 온도 2분 평균 38 ℃'

def cap(c):
    return [['click', 'caption'], ['type', c]]
def lab(c):
    return [['click', 'labelPlus'], ['click', 'labelInput'], ['type', KIND[c]], ['key', 'Tab']]
def nn(c):
    return cap(c) + lab(c)
def gt(src, dst, click=True):
    return ([['click', 'node:' + src]] if click else []) + [['growTo', src, *POS[dst], H]]
def ty(t):
    return [['click', 'type'], ['type', t]]
def et(a, b, t=None, rev=False):
    return [['edge', a, b]] + ([['click', 'reverse']] if rev else []) + (ty(t) if t else [])
def con(a, b):
    return [['click', 'node:' + a], ['connect', a, b]]
def pv(k, v):   # 속성 값 뒤에는 Tab — 값 칸에서 엔터를 치면 빈 속성 줄이 하나 더 생긴다
    return [['click', 'propKey'], ['type', k], ['click', 'propVal'], ['type', v], ['key', 'Tab']]
def sop(a, b, v):
    return [['edge', a, b], ['click', 'propPlus']] + pv('절차', v)
def color(v):
    return [['click', 'style:node-color'], ['key', 'ControlOrMeta+A'], ['type', v], ['key', 'Tab']]
HL_SHAPES = ('underline', 'band', 'box', 'circle')   # 포털 촬영도구 hl.mjs SHAPES
HL_BOX = {'caption', 'type', 'labelInput', 'propKey', 'propVal', 'customize', 'reverse', 'labelPlus', 'propPlus', 'export', 'done'}


def hl_default(t):
    """짚기 대상의 기본 강조 모양. 화살표 끝 · 넓은 자리 · 메뉴 줄처럼 여기 없는 대상은 강조가 없다(None)."""
    if t.startswith(('look:', 'ring:', 'node:', 'inner:')):
        return 'circle'       # 원 둘레의 동그라미
    if t.startswith(('ctext:', 'ctextL:', 'ctextR:', 'props:')) or t in ('selCount', 'cypherHead'):
        return 'underline'    # 그림판 글자(관계 이름 · Label 띠 · 절차 번호) · 증거 줄 · 개수 줄 · Cypher 첫 낱말
    if t.startswith('noteLine:') or t == 'cypherText':
        return 'band'         # 글상자 줄 · Cypher 글
    if t in HL_BOX or t.startswith(('style:', 'styleSel:', 'tab:')):
        return 'box'          # 오른쪽 칸의 입력칸 · 단추
    return None


def P(t, hl=None):
    shape = hl_default(t) if hl is None else None if hl == 'none' else hl
    if shape is not None and shape not in HL_SHAPES:
        raise SystemExit(f"P({t!r}): 모르는 강조 모양 {hl!r} — {' | '.join(HL_SHAPES)} | none (build_ontology.py)")
    return ('P', [['point', t] + ([shape] if shape else [])])


A = lambda *ops: ('A', [o for x in ops for o in x])
T = lambda *ops: ('T', [o for x in ops for o in x])
L = lambda c, hl=None: P('look:' + c, hl)          # 원(테두리 오른쪽 아래)
EF = lambda a, b: P(f'edgeFrom:{a}>{b}')           # 화살표가 나가는 끝
ET = lambda a, b: P(f'edgeTo:{a}>{b}')             # 화살표가 닿는 끝
N = lambda text: ('P', [['note', text, 'tr']])     # 글상자 띄우기
OFF = ('P', [['note', None]])                      # 글상자 내리기
ck = lambda t: [['click', t]]

MAP = {
 # 1구간 — 검색해서 들어가기 · 원 크기 · 관계 글 가로 · 첫 원 옮기기
 'g004': [A([['click', 'sel:#sb_form_q'], ['type', 'arrows.app'], ['key', 'Enter'], ['reinstall']])],
 'g005': [A([['openLink', 'result:arrows.app']])],
 'g006': [A([['click', 'text:Use necessary cookies only'], ['click', 'done']])],
 'g007': [P('canvasMid'), L('')],
 'g008': [A(ck('customize'))],
 'g009': [P('style:radius'), T([['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '60'], ['key', 'Tab']])],
 'g010': [T([['panelScroll', 'styleSel:detail-orientation']]), P('styleSel:detail-orientation'),
          A([['click', 'styleSel:detail-orientation'], ['click', 'styleOpt:detail-orientation=horizontal'], ['panelScroll']])],
 'g011': [T([['drag', '', FIRST_X, None]])],
 # 2구간 — 설비 · 쿨러 · 센서
 'g012': [A(ck('node:'))], 'g013': [P('caption'), A(cap(H))], 'g015': [P('labelPlus'), A(ck('labelPlus'))],
 'g016': [A([['click', 'labelInput'], ['type', 'Asset'], ['key', 'Tab']])], 'g017': [P('ctext:Asset')], 'g018': [L(H)],
 'g019': [P('inner:' + H), P('ring:' + H), A(gt(H, K, click=False))],
 'g020': [A(nn(K))], 'g021': [EF(H, K)], 'g022': [L(H), L(K)],
 'g023': [T([['edge', H, K]]), P('type'), A(ty('HAS_COMPONENT'))],
 'g024': [EF(H, K), ET(H, K)], 'g026': [L(K), P('ctext:HAS_COMPONENT')], 'g027': [L(K)],
 'g028': [A(gt(K, S))], 'g029': [T(nn(S))], 'g030': [L(K), L(S)], 'g031': [T([['edge', K, S]]), A(ty('MONITORED_BY'))], 'g032': [L(K), L(S)],
 # 3구간 — 증상 · 방향 뒤집기 · 고장 유형
 'g033': [L(S)], 'g034': [A(gt(S, U))], 'g035': [T(cap(U)), A(lab(U))], 'g036': [L(U), L(S)], 'g037': [EF(S, U), L(U)],
 'g038': [T([['edge', S, U]]), P('reverse'), A(ck('reverse'))], 'g039': [A(ty('OBSERVED_BY'))], 'g040': [L(U), L(S)],
 'g042': [L(U)], 'g043': [A(gt(U, F))], 'g044': [T(cap(F)), A(lab(F))],
 'g045': [L(U), L(F), A(et(U, F, 'INDICATES'))], 'g046': [A(con(F, K))], 'g047': [L(F), L(K), A(et(F, K, 'OCCURS_IN'))],
 'g048': [L(S), L(U), L(F), L(K)],
 # 4구간 — 원인 · 증거
 'g049': [L(K)], 'g050': [L(F), A(gt(F, PO))], 'g051': [A(nn(PO))], 'g052': [L(PO), L(F), EF(F, PO)], 'g053': [A(et(F, PO, 'CAUSES', rev=True))],
 'g054': [P('ctext:CAUSES')], 'g056': [T(ck('node:' + PO)), P('propPlus'), A(ck('propPlus'))],
 'g057': [P('propKey'), P('propVal'), A([['click', 'propKey'], ['type', '냉각 효율']])],
 'g058': [T([['click', 'propVal'], ['type', '30초 평균 < 70 %']]), T([['key', 'Tab']])], 'g059': [P('props:' + PO)],
 'g060': [T(ck('propPlus')), A(pv('팬 진동', '2분 평균 < 0.9 mm/s'))], 'g061': [P('props:' + PO + '#1'), P('props:' + PO + '#2')],
 # 5구간 — 완화 조치 · 근본 조치 · 근거 매뉴얼
 'g063': [A(gt(F, MX))], 'g064': [T(nn(MX))], 'g065': [L(F), L(MX), A(et(F, MX, 'MITIGATED_BY'))], 'g066': [A(gt(F, PC))], 'g067': [A(nn(PC))],
 'g068': [L(F), L(PC), A(et(F, PC, 'REMEDIED_BY'))], 'g069': [P('ctext:MITIGATED_BY'), P('ctext:REMEDIED_BY')],
 'g070': [L(PC), A(con(PC, PO))], 'g071': [L(PC), L(PO), A(et(PC, PO, 'ADDRESSES'))], 'g073': [A(gt(MX, M85))], 'g074': [T(cap(M85)), A(lab(M85))],
 'g075': [L(MX), L(M85), A(et(MX, M85, 'REFERS_TO'))], 'g076': [T(gt(PC, M87)), A(nn(M87))], 'g077': [A(et(PC, M87, 'REFERS_TO'))],
 'g078': [L(PO), L(PC), L(M87)],
 # 6구간 — 두 번째 원인
 'g080': [A(gt(F, FD))], 'g081': [T(cap(FD)), A(lab(FD))], 'g082': [A(et(F, FD, 'CAUSES', rev=True))],
 'g083': [A([['click', 'node:' + FD], ['click', 'propPlus']], pv('팬 진동', '2분 평균 ≥ 0.9 mm/s'))], 'g084': [P('props:' + PO + '#2'), P('props:' + FD)],
 'g085': [A(gt(F, FI))], 'g086': [T(nn(FI)), A(et(F, FI, 'REMEDIED_BY'))], 'g087': [A(con(FI, FD), et(FI, FD, 'ADDRESSES'))],
 'g088': [A(gt(FI, M81), nn(M81))], 'g089': [A(et(FI, M81, 'REFERS_TO'))],
 # 7구간 — 세 번째 원인
 'g091': [A(gt(F, AT))], 'g092': [T(nn(AT)), A(et(F, AT, 'CAUSES', rev=True))],
 'g093': [A([['click', 'node:' + AT], ['click', 'propPlus']], pv('캐비닛 온도', '2분 평균 ≥ 35 ℃'))], 'g094': [A(gt(AT, CV))], 'g095': [A(nn(CV))],
 'g096': [L(CV), L(AT), EF(AT, CV), A(et(AT, CV, 'ADDRESSES', rev=True))], 'g097': [A(con(F, CV), et(F, CV, 'REMEDIED_BY'))],
 'g098': [A(con(CV, M87), et(CV, M87, 'REFERS_TO'))], 'g099': [L(PC), L(M87), L(CV)], 'g100': [L(FD), L(FI), L(PO), L(PC), L(AT), L(CV)],
 # 8구간 — 고장이 고장으로 · 절차 번호
 'g102': [L(F), A(gt(F, BR))], 'g103': [A(nn(BR))], 'g104': [L(BR), L(F)], 'g105': [A(et(F, BR, 'LEADS_TO', rev=True))],
 'g106': [P('props:' + FD), A(gt(BR, VB))], 'g107': [T(nn(VB)), A(et(BR, VB, 'INDICATES', rev=True))], 'g108': [L(VB), L(BR), L(F)],
 'g110': [L(M87)], 'g111': [A([['edge', CV, M87]])], 'g112': [T(ck('propPlus')), A(pv('절차', 'SOP-COOL-15'))],
 'g113': [A(sop(PC, M87, 'SOP-COOL-14'))], 'g114': [P('ctext:SOP-COOL-14'), P('ctext:SOP-COOL-15')],
 'g115': [A(sop(MX, M85, 'SOP-COOL-11'))], 'g116': [A(sop(FI, M81, 'SOP-FAN-11'))],
 # 9구간 — 색칠
 'g117': [T(ck('node:' + PO)), T([['ctrlclick', 'node:' + FD]]), T([['ctrlclick', 'node:' + AT]])], 'g118': [P('selCount'), P('style:node-color'), A(color(RED))],
 'g119': [T(ck('node:' + MX)), T([['ctrlclick', 'node:' + PC]]), T([['ctrlclick', 'node:' + CV]]), T([['ctrlclick', 'node:' + FI]]), A(color(GREEN))],
 # 10구간 — 그림으로 판단하기
 'g120': [T(ck('blank')), L(U), L(F), L(FD), L(AT), L(PO)], 'g121': [N(CASE), P('noteLine:1'), P('noteLine:2'), P('noteLine:3')],
 'g122': [P('props:' + PO + '#1'), P('props:' + PO + '#2')], 'g123': [P('props:' + FD), P('props:' + AT), L(PO)],
 'g124': [OFF, L(PO), L(PC), P('ctext:SOP-COOL-14'), L(M87), L(MX)], 'g125': [N(CASE14), P('props:' + PO + '#2'), P('props:' + FD), L(FI), P('ctext:SOP-FAN-11'), L(M81)],
 'g126': [L(VB), L(BR)], 'g127': [N(CASE38), P('props:' + PO), P('props:' + AT), L(CV), L(PC)], 'g128': [OFF, P('props:' + PO + '#2')],
 'g129': [L(U), L(PC), L(FI)],
 # 11구간 — 파일로 남기기 · Cypher · 맺음(화면을 열지 않고 단추만 짚는다)
 'g130': [P('export', hl='underline')],   # 화면 맨 위 단추라 테두리는 화면 밖으로 나간다 — 글자 밑줄로 짚는다
}
# 쉼(ms, 영상 V-14): 한 문맥으로 이어지는 큐 0.6초 · 큐 사이 1.3초 · 조작 결과 뒤와 따라 적은 뒤 2.0초 · 구간이 바뀌는 곳 2.3초.
GAP = {'join': 600, 'pause': 1300, 'result': 2000, 'stage': 2300}


def gap_before(prev):
    """앞 큐에서 이 큐 앞의 쉼을 정한다. 앞 큐가 끝맺음(. ? !) 없이 끝나면 한 문장이 두 큐로 나뉜 자리라 늘 잇기다(영상 V-14)."""
    if prev is None:
        return GAP['stage']
    if prev['text'][-1] not in '.?!':
        return GAP['join']
    acted = any(o[0] not in ('at', 'atend', 'point', 'note') for o in prev['ops'])
    return GAP['result'] if acted else GAP['pause']


def script():
    """대본원고.md → [(구간 번호, 구간 제목, 큐 id, ▸가 든 글)]. 표의 줄이 아닌 것은 읽지 않는다."""
    out, seg, title = [], 0, ''
    for n, line in enumerate((ROOT / '대본원고.md').read_text(encoding='utf-8').split('\n'), 1):
        m = re.match(r'## (\d+)구간 · (.+)$', line)
        if m:
            seg, title = int(m[1]), m[2].strip()
            continue
        m = re.match(r'\| (\S+) \| (.+) \|$', line)
        if m and m[1] not in ('큐', '---'):
            if not seg:
                raise SystemExit(f'대본원고.md {n}행: 구간 제목(## N구간 · …) 앞에 큐 {m[1]}가 있다')
            out.append((seg, title, m[1], m[2]))
    return out


def cues():
    """낭독 원고의 ▸와 MAP으로 큐를 만든다. 큐의 ▸ 수와 MAP 칸 수가 다르거나, 큐 끝이 아닌 ▸에 A 칸이 걸리면 큐 id와 함께 멈춘다."""
    out, ids, prev_seg = [], set(), 0
    for seg, _, cid, raw in script():
        if cid in ids:
            raise SystemExit(f'{cid}: 대본원고.md에 큐 id가 두 번 나온다')
        ids.add(cid)
        parts, m = raw.split('▸'), MAP.get(cid, [])
        if len(m) != len(parts) - 1:
            raise SystemExit(f'{cid}: ▸ {len(parts) - 1}곳인데 MAP 칸이 {len(m)}개다 (build_ontology.py MAP)')
        text = ''.join(parts)
        if text != ' '.join(text.split()) or not text:
            raise SystemExit(f'{cid}: 낭독 글이 비었거나 앞뒤 · 겹친 공백이 있다 (대본원고.md)')
        ops, pos, acts = [], 0, []
        for i, (kind, o) in enumerate(m):
            pos += len(parts[i])
            if kind == 'A':
                if i != len(m) - 1 or pos != len(text):
                    raise SystemExit(f'{cid}: A 칸은 큐 끝의 ▸에만 건다 (build_ontology.py MAP)')
                acts = o
            else:
                if pos == len(text):
                    raise SystemExit(f'{cid}: 큐 끝의 ▸에는 A 칸을 건다 (build_ontology.py MAP)')
                ops += [['at', round(min(0.95, pos / len(text)), 3)]] + o
        marks = bool(ops)
        ops += ([['atend']] if marks and acts else []) + acts
        c = {'id': cid, 'segment': seg, 'text': text, 'ops': ops, 'gap': gap_before(out[-1] if out and seg == prev_seg else None)}
        if acts and not marks:
            c['cut'] = True
        out.append(c); prev_seg = seg
    extra = set(MAP) - ids
    if extra:
        raise SystemExit(f'MAP에 대본원고.md에 없는 큐가 있다: {sorted(extra)}')
    return out


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
EVID = REPO / '작업' / '촬영' / 'arrows'          # 녹화 원본 · 합성 출력(git 밖)
FINAL = '통합1-08-관계그림'                        # 합성 출력 이름(포털 encode.py --도구 arrows) — 합성기록/<FINAL>.json
VIDEO_NAME = '통합반_01회차_08_실습_관계그림.mp4'
SEGMENT_TITLE = {seg: title for seg, title, _, _ in script()}   # 구간 제목은 대본원고.md의 「## N구간 · 제목」 하나가 갖는다
TARGET = {'caption': 'Caption 입력칸 클릭', 'labelPlus': 'Label 옆 + 클릭', 'labelInput': '새 Label 입력칸 클릭',
          'propPlus': 'Property 옆 + 클릭', 'propKey': '새 속성의 왼쪽(이름) 칸 클릭', 'propVal': '오른쪽(내용) 칸 클릭', 'type': 'Type 입력칸 클릭',
          'blank': '그림의 빈 곳 클릭(고른 것 풀기)', 'customize': 'STYLE의 Customize 클릭', 'style:radius': 'radius 입력칸 클릭',
          'reverse': 'Reverse 클릭(화살표 방향 뒤집기)', 'export': 'Download / Export 클릭', 'tab:JSON': 'JSON 탭 클릭', 'tab:PNG': 'PNG 탭 클릭',
          'done': 'Done 클릭', 'logo': '왼쪽 위 로고 메뉴 클릭', 'menu:newLocal': 'New ▸ Web Browser storage 클릭(새 그림)', 'menu:Import': 'Import 클릭',
          'menu:New': 'New에 커서 올리기', 'menu:Open': 'Open에 커서 올리기', 'importButton': '창 아래 Import 버튼 클릭',
          'canvasMid': '그림 영역 가리키기', 'panelMid': '오른쪽 칸 가리키기', 'node:': '빈 원 클릭', 'look:': '빈 원 가리키기',
          'cypherText': 'Cypher 글 가리키기', 'cypherHead': 'Cypher 글 맨 앞 CREATE 가리키기', 'tab:Cypher': 'Cypher 탭 클릭', 'style:node-color': 'node-color 입력칸 클릭',
          'selCount': '오른쪽 nodes 개수 가리키기', 'download': 'Download 클릭', 'sel:#sb_form_q': '검색 칸 클릭',
          'styleSel:detail-orientation': 'detail-orientation 고르는 칸 클릭', 'styleOpt:detail-orientation=horizontal': 'horizontal 고르기'}
POINTED = {'click': '클릭', 'point': '가리키기'}


def act(op):
    """큐의 조작 하나를 대본의 「조작 · 결과 확인」 칸 글로 바꾼다. 화면에 보이지 않는 것(말 속 시각 · 포인터 다시 심기)은 None."""
    k, *a = op
    if k in ('at', 'atend', 'reinstall'):
        return None
    if k in ('click', 'point'):
        t = a[0]
        if t in TARGET:
            return TARGET[t] if k == 'click' else TARGET[t].replace('클릭', '가리키기')
        for pre, word in (('node:', '원'), ('look:', '원'), ('inner:', '원 안쪽'), ('ring:', '원 둘레의 하늘색 띠'), ('ctextL:', '글자의 앞'), ('ctextR:', '글자의 끝'), ('ctext:', '글자'), ('text:', '단추')):
            if t.startswith(pre):
                return f'‘{t[len(pre):]}’ {word} ' + POINTED[k]
        if t.startswith('noteLine:'):
            return f'글상자의 {t[9:]}째 줄 가리키기'
        if t.startswith('props:'):
            c, _, n = t[6:].partition('#')
            return f'‘{c}’ 원의 증거 ' + (f'{n}째 줄' if n else '줄') + ' 가리키기'
        for pre, word in (('edgeFrom:', '화살표가 나가는 끝'), ('edgeTo:', '화살표가 닿는 끝')):
            if t.startswith(pre):
                x, y = t[len(pre):].split('>')
                return f'‘{x}’ → ‘{y}’ {word} 가리키기'
        raise SystemExit(f'act: 이름표가 없는 대상 {t} (build_ontology.py TARGET)')
    if k == 'type':
        return f'`{a[0]}` 입력'
    if k == 'key':
        return {'ControlOrMeta+A': 'Ctrl+A(칸 전체 선택)', 'Tab': 'Tab(입력 마침)'}.get(a[0], a[0] + ' 키')
    if k == 'growTo':
        return f'‘{a[0]}’ 원 둘레의 하늘색 띠를 잡아 빈 곳으로 끌기 → 새 원과 화살표 생성'
    if k == 'drag':
        return f'‘{a[0]}’ 원 안쪽을 잡아 왼쪽으로 끌어 옮기기(화면 끝에서 원 하나만큼 띄운 자리)' if a[0] else '빈 원 안쪽을 잡아 왼쪽으로 끌어 옮기기(화면 끝에서 원 하나만큼 띄운 자리)'
    if k == 'panelScroll':
        return '오른쪽 칸 위에서 휠을 내려 그 칸이 보이게' if a else '오른쪽 칸을 다시 맨 위로'
    if k == 'openLink':
        return '검색 결과 가운데 주소가 arrows.app인 줄 클릭 → arrows.app 첫 화면'
    if k == 'edge':
        return f'‘{a[0]}’–‘{a[1]}’ 사이 화살표 클릭(관계 선택)'
    if k == 'connect':
        return f'‘{a[0]}’ 둘레의 띠를 잡아 ‘{a[1]}’ 원 위에 놓기 → 화살표만 생성'
    if k == 'download':
        return 'Download 클릭 → 파일 저장 확인'
    if k == 'ctrlclick':
        return f'Ctrl 누른 채 ‘{a[0][5:]}’ 원 클릭(함께 선택)'
    if k == 'choose':
        return 'Choose File로 방금 저장한 JSON 선택'
    if k == 'verify':
        return '원 17 · 화살표 21 · 원인 증거 · 절차 번호 복원 확인'
    if k == 'note':
        return '화면 오른쪽 위에 사건 값 글상자 띄우기' if a[0] else '글상자 내리기'
    raise SystemExit(f'act: 모르는 조작 {k} (build_ontology.py act)')


def manuscript():
    out = [f'''# ARROWS 실습 — 쿨러 고장 이야기를 관계 그림으로 그리기

영상은 `{VIDEO_NAME}`(정본은 Release 「영상」 — 영상 V-7)이고, 구간 · 시간은 제작용 [예상시간](예상시간.md)에 있다.

## 진행 메모 — 낭독하지 않음

- 실제로 찍은 큐 그대로다. 화살표는 늘 「둘 사이를 한 문장으로 말한다 → 화살표가 그 문장의 주어에서 나가 있는지 본다 → 반대면 Reverse로 뒤집는다 → 이름을 적는다」 차례다.
- 화면은 처음부터 끝까지 한 화면(보기 배율 1)이다. 새 그림의 빈 원을 원 안쪽을 잡고 왼쪽으로 옮겨 첫 원으로 쓰고, 나머지는 원 둘레의 띠를 끌어 원과 화살표를 함께 만든다. 원은 처음부터 끝 자리에 놓는다.
- 속성 값 칸과 radius 칸은 Tab으로 마친다(값 칸의 엔터는 빈 속성 줄을, 아무것도 고르지 않은 채 radius 칸의 엔터는 원을 하나 더 만든다).
- 색: 원인 셋 `#fca5a5`(연한 빨강), 조치 넷 `#86efac`(연한 초록).
- 입력값 출처: 종류 · 관계 이름은 `workspace/개발/문서/ontology/schema-v2.md` · `it/neo4j/v2/instances.cypher`, 판별 기준은 랩 `매뉴얼_발췌.md` HM-8.4, 조치 근거는 HM-8.1 · 8.5 · 8.7.
''']
    seg = 0
    for c in cues():
        if c['segment'] != seg:
            seg = c['segment']
            out.append(f'\n## {seg}구간 · {SEGMENT_TITLE[seg]}\n\n| 큐 | 발화 | 조작·결과 확인 — 비낭독 |\n|---|---|---|')
        acts = [x for x in (act(o) for o in c['ops']) if x]
        out.append(f"| {c['id']} | {c['text']} | {' → '.join(acts) if acts else '—'} |")
    out.append('\n# 촬영 본문 끝\n\n## 제작 확인용 — 낭독하지 않음\n\n'
               '- 판별 조건은 HM-8.4 원문 기준이다(핀 오염: CE 30초 평균 < 70 % 이고 VS1 2분 평균 < 0.9 mm/s, 팬 구동 불량: VS1 2분 평균 ≥ 0.9 mm/s, 주변 온도 상승: TS4 2분 평균 ≥ 35 ℃).\n'
               '- REFERS_TO는 실제 데이터에서 Skill → Step → ManualSection 두 단계(HAS_STEP · REFERS_TO)다. 교재 지도처럼 한 번에 잇고, 절차 번호는 그 화살표의 속성으로 적는다.\n'
               '- 증거도 실제 데이터에서는 원인에 이어진 Evidence 노드(EVIDENCED_BY)이고, 이 그림에서는 원인의 속성으로 줄여 적는다.\n'
               '- 원 자리 · 쉼 · 조작은 `workspace/강의제작/제작도구/촬영/arrows/build_ontology.py`(POS · GAP · MAP), 낭독 글은 같은 폴더 `대본원고.md`, 찍는 법은 `촬영준비.md`에 있다.\n')
    return '\n'.join(out) + '\n'


def write_all():
    import hashlib
    rec = json.loads((ROOT / '합성기록' / f'{FINAL}.json').read_text(encoding='utf-8'))
    script = manuscript()
    (ROOT / '수업원고.md').write_text(script, encoding='utf-8')
    cs = cues()
    spoken = sum(json.loads((ROOT / '음성' / (c['id'] + '.json')).read_text(encoding='utf-8'))['duration_ms'] for c in cs) / 1000
    cuts = json.loads((ROOT / f'잘라냄_통합1-08.json').read_text(encoding='utf-8'))   # cut.py로 잘라 낸 멈춘 화면 [시작, 끝]초(합성 영상 기준)
    cut_s = sum(e - s for s, e in cuts)
    dur = rec['duration_s'] - cut_s
    segs = [g for g in rec['segments']]
    rows = ''.join(f"| {n} · {SEGMENT_TITLE[n]} | {g['segment']} | {g['used_ms'] / 1000:.1f} |\n" for n, g in enumerate(segs, 1))
    gaim = ' 낸 판은 검색 결과 맨 위 광고 칸을 흐리게 가렸다(합성기록 「가림」).' if rec.get('가림') else ''
    timing = f'''# ARROWS 실습 시간 — 실측

대상: [수업원고](수업원고.md). **실측 영상 길이 {dur / 60:.1f}분({dur:.1f}초)**, 음성 {len(cs)}큐(음성만 합하면 {spoken / 60:.1f}분). 쉼은 이어지는 말 0.6초 · 큐 사이 1.3초 · 결과 뒤 2.0초 · 구간 사이 2.3초다.

| 구간 | 녹화 조각(take) | 길이(초) |
|---|---|---|
''' + rows + f'''
합성한 뒤 말 없이 화면이 서 있는 곳 {len(cuts)}곳에서 쉼 기준을 넘는 {cut_s:.1f}초를 잘라 냈다(`잘라냄_통합1-08.json`, 구간 길이는 잘라 내기 전 값).

측정: `measure.py`의 0.5초 넘는 이동 공백은 5구간(0.9초)과 6구간(1.2초)에 한 번씩이고, 둘 다 커서가 오른쪽 칸에서 미끄러지다 잠깐 멈춘 것이다. 조작 없이 화면 전체가 바뀐 곳은 1구간(검색 결과 → arrows.app)과 11구간(내보내기 · 새 그림 · 불러오기 창)뿐이고, 모두 클릭이 연 화면이다. 합성의 최대 프레임 간격은 {rec['motion_summary']['max_gap_ms_max']}ms다.{gaim}
'''
    (ROOT / '예상시간.md').write_text(timing, encoding='utf-8')
    screens = f'''# 화면 — 촬영 완료

1회차 실습 4 영상(`{VIDEO_NAME}`)의 실제 화면이다(Playwright 헤드리스, 프레임 1920×1080 — 화면 값은 촬영준비 「자료」).

| 구간 | 보여 준 것 | 확인한 결과 |
|---|---|---|
''' + ''.join(f'| {k} | {v} | 실제 화면 |\n' for k, v in SEGMENT_TITLE.items())
    (ROOT / '촬영화면.md').write_text(screens, encoding='utf-8')
    sys.path.insert(0, str(REPO / 'workspace/강의제작/제작도구/실습시작'))
    from lab_package import pack_page
    for course in ['실전반', '통합반']:
        day = REPO / 'workspace/강의제작/산출물' / course / '실습/01회차'
        lab = day / '랩/01일차_실습4_관계그림'
        (day / '대본/08_실습_관계그림.md').write_text(script.replace('(예상시간.md)', '(../../../../../제작도구/촬영/arrows/예상시간.md)'), encoding='utf-8')
        pack_page(lab)   # 가이드.html은 build_student_guide.py가 쓴다 — 여기서 덮지 않는다
    files = [ROOT / '수업원고.md', ROOT / '예상시간.md', ROOT / '촬영화면.md'] + [REPO / 'workspace/강의제작/산출물' / c / '실습/01회차' / x for c in ['실전반', '통합반'] for x in
             ['대본/08_실습_관계그림.md', '랩/01일차_실습4_관계그림/가이드.html', '랩/01일차_실습4_관계그림.html']]
    (ROOT / '동기화판본.json').write_text(json.dumps({f.relative_to(REPO).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('synced', dur, 's;', len(cs), 'cues')


if __name__ == '__main__':
    if sys.argv[1] == 'cues':
        data = {'voice_id': 'tlxL9ilynpbOVf9sZXKh', 'model_id': 'eleven_v4', 'nodes': [list(n) for n in NODES],
                'relationships': RELS, 'properties': PROPS, 'cues': cues()}
        Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        print(len(data['cues']), 'cues')
    elif sys.argv[1] == 'sync':
        write_all()
    else:
        raise SystemExit('usage: build_ontology.py cues <path> | sync')
