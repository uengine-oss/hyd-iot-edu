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
A = lambda *ops: ('A', [o for x in ops for o in x])
T = lambda *ops: ('T', [o for x in ops for o in x])
P = lambda t: ('P', [['point', t]])
L = lambda c: P('look:' + c)                       # 원(테두리 오른쪽 아래)
EF = lambda a, b: P(f'edgeFrom:{a}>{b}')           # 화살표가 나가는 끝
ET = lambda a, b: P(f'edgeTo:{a}>{b}')             # 화살표가 닿는 끝
N = lambda text: ('P', [['note', text, 'tr']])     # 글상자 띄우기
OFF = ('P', [['note', None]])                      # 글상자 내리기
ck = lambda t: [['click', t]]

MAP = {
 # 1구간 — 검색해서 들어가기 · 원 크기 · 관계 글 가로 · 첫 원 옮기기
 'e003': [A([['click', 'sel:#sb_form_q'], ['type', 'arrows.app'], ['key', 'Enter'], ['reinstall']])],
 'e004': [A([['openLink', 'result:arrows.app']])],
 'e005': [A(ck('text:Use necessary cookies only'))],
 'e006': [A(ck('done'))],
 'e007': [P('canvasMid'), P('panelMid'), L('')],
 'e008': [A(ck('customize'))],
 'e009': [P('style:radius'), T([['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '60'], ['key', 'Tab']])],
 'e010b': [T([['panelScroll', 'styleSel:detail-orientation']]), P('styleSel:detail-orientation'),
           A([['click', 'styleSel:detail-orientation'], ['click', 'styleOpt:detail-orientation=horizontal'], ['panelScroll']])],
 'e011': [T([['drag', '', FIRST_X, None]])],
 # 2구간
 'e012': [A(ck('node:'))], 'e013': [P('caption'), A(cap(H))], 'e015': [A(ck('labelPlus'))],
 'e016': [T([['click', 'labelInput'], ['type', 'Asset'], ['key', 'Tab']])], 'e017': [P('ctext:Asset')],
 'e019': [T(ck('node:' + H)), P('ring:' + H), P('node:' + H), P('ring:' + H), A(gt(H, K, click=False))],
 'e020': [A(nn(K))], 'e021': [EF(H, K), ET(H, K)], 'e022': [L(H), L(K)],
 'e023': [T([['edge', H, K]]), P('type'), A(ty('HAS_COMPONENT'))],
 'e024': [P('ctext:HAS_COMPONENT'), P('ctextL:HAS_COMPONENT'), P('ctextR:HAS_COMPONENT')],
 'e025': [EF(H, K), ET(H, K), L(H), L(K), P('ctext:HAS_COMPONENT')], 'e026': [L(H), ET(H, K)],
 'e027': [L(K), P('ctext:HAS_COMPONENT'), L(H), L(K)], 'e028': [L(K)], 'e029': [A(gt(K, S))], 'e030': [T(nn(S))],
 'e031': [L(S), L(K), L(K), L(S)], 'e032': [L(S), EF(K, S)], 'e033': [L(K), EF(K, S), ET(K, S), A(et(K, S, 'MONITORED_BY'))],
 'e034': [L(K), L(S), P('ctext:MONITORED_BY'), L(H), L(K), L(S)],
 # 3구간
 'e035': [A(gt(S, U))], 'e036': [T(cap(U)), A(lab(U))], 'e037': [L(U), L(S)], 'e038': [L(U), EF(S, U), ET(S, U)],
 'e039': [T([['edge', S, U]]), P('reverse'), A(ck('reverse'))], 'e040': [A(ty('OBSERVED_BY'))], 'e041': [L(U), L(S), P('ctext:OBSERVED_BY')],
 'e042': [L(U), EF(U, S), L(S)], 'e043': [L(U), L(K)], 'e044': [A(gt(U, F))], 'e045': [T(cap(F)), A(lab(F))],
 'e046': [L(U), L(F), A(et(U, F, 'INDICATES'))], 'e047': [L(K), A(con(F, K))], 'e048': [L(F), L(K), A(et(F, K, 'OCCURS_IN'))],
 'e049': [L(U), L(S), L(F), L(K)],
 # 4구간
 'e050': [L(K)], 'e051': [A(gt(F, PO))], 'e052': [A(nn(PO))], 'e053': [L(PO), L(F), EF(F, PO), ET(F, PO)], 'e054': [A(et(F, PO, 'CAUSES', rev=True))],
 'e055': [L(PO), L(F), L(F), L(PO)], 'e057': [T(ck('node:' + PO)), A(ck('propPlus'))],
 'e058': [P('propKey'), P('propVal'), A([['click', 'propKey'], ['type', '냉각 효율']])],
 'e059': [T([['click', 'propVal'], ['type', '30초 평균 < 70 %']]), T([['key', 'Tab']])], 'e060': [P('props:' + PO)],
 'e061': [T(ck('propPlus')), A(pv('팬 진동', '2분 평균 < 0.9 mm/s'))], 'e062': [P('props:' + PO)],
 # 5구간
 'e064': [A(gt(F, MX))], 'e065': [T(nn(MX))], 'e066': [L(F), L(MX)], 'e067': [A(et(F, MX, 'MITIGATED_BY'))], 'e068': [A(gt(F, PC))], 'e069': [A(nn(PC))],
 'e070': [T(et(F, PC, 'REMEDIED_BY')), L(F), L(PC), P('ctext:REMEDIED_BY')], 'e071': [P('ctext:MITIGATED_BY'), P('ctext:REMEDIED_BY')],
 'e072': [A(con(PC, PO))], 'e073': [L(PC), L(PO), A(et(PC, PO, 'ADDRESSES'))], 'e074': [A(gt(MX, M85))], 'e075': [T(cap(M85)), A(lab(M85))],
 'e076': [L(MX), L(M85), A(et(MX, M85, 'REFERS_TO'))], 'e077': [T(gt(PC, M87)), A(nn(M87))], 'e078': [A(et(PC, M87, 'REFERS_TO'))],
 'e079': [L(PO), L(PC), L(M87)],
 # 6구간
 'e080': [L(PO)], 'e081': [A(gt(F, FD))], 'e082': [T(cap(FD)), A(lab(FD))], 'e083': [A(et(F, FD, 'CAUSES', rev=True))],
 'e084': [A([['click', 'node:' + FD], ['click', 'propPlus']], pv('팬 진동', '2분 평균 ≥ 0.9 mm/s'))], 'e085': [P('props:' + PO + '#2'), P('props:' + FD)],
 'e086': [A(gt(F, FI))], 'e087': [T(cap(FI)), T(lab(FI)), A(et(F, FI, 'REMEDIED_BY'))], 'e088': [A(con(FI, FD), et(FI, FD, 'ADDRESSES'))],
 'e089': [T(gt(FI, M81)), A(nn(M81))], 'e089b': [A(et(FI, M81, 'REFERS_TO'))],
 # 7구간
 'e090b': [A(gt(F, AT))], 'e091': [T(nn(AT)), A(et(F, AT, 'CAUSES', rev=True))],
 'e092': [A([['click', 'node:' + AT], ['click', 'propPlus']], pv('캐비닛 온도', '2분 평균 ≥ 35 ℃'))], 'e093': [A(gt(AT, CV))], 'e094': [A(nn(CV))],
 'e095': [L(CV), L(AT), EF(AT, CV), ET(AT, CV), A(et(AT, CV, 'ADDRESSES', rev=True))], 'e096': [A(con(F, CV), et(F, CV, 'REMEDIED_BY'))],
 'e097': [A(con(CV, M87), et(CV, M87, 'REFERS_TO'))], 'e098': [L(PC), L(M87), L(CV)], 'e099': [L(PO), L(PC), L(FD), L(FI), L(AT), L(CV)],
 # 8구간
 'e101': [L(FD)], 'e102': [A(gt(F, BR))], 'e103': [A(nn(BR))], 'e104': [L(BR), L(F)], 'e105': [A(et(F, BR, 'LEADS_TO', rev=True))],
 'e106': [P('props:' + FD), L(BR)], 'e107': [L(U), A(gt(BR, VB))], 'e108': [T(nn(VB)), A(et(BR, VB, 'INDICATES', rev=True))], 'e109': [L(VB), L(BR), L(F)],
 'e110': [L(M87), L(PC), L(CV)], 'e111': [A([['edge', FI, M81]])], 'e112': [A(ck('propPlus'), pv('절차', 'SOP-FAN-11'))],
 'e113': [A(sop(CV, M87, 'SOP-COOL-15'))], 'e114': [A(sop(PC, M87, 'SOP-COOL-14'))], 'e115': [A(sop(MX, M85, 'SOP-COOL-11'))],
 'e116': [P('ctext:SOP-COOL-14'), P('ctext:SOP-COOL-15')],
 # 9구간 — 색칠
 'e117': [T(ck('node:' + PO)), T([['ctrlclick', 'node:' + FD]]), T([['ctrlclick', 'node:' + AT]])], 'e118': [P('selCount'), P('style:node-color'), A(color(RED))],
 'e119': [T(ck('node:' + MX)), T([['ctrlclick', 'node:' + PC]]), T([['ctrlclick', 'node:' + CV]]), T([['ctrlclick', 'node:' + FI]]), P('selCount')], 'e120': [A(color(GREEN))],
 # 10구간 — 그림으로 판단하기
 'e121': [T(ck('blank')), L(U), L(F), L(PO), L(FD), L(AT)], 'e122': [N(CASE), P('noteLine:1'), P('noteLine:2'), P('noteLine:3')],
 'e123': [P('props:' + PO + '#1'), P('props:' + PO + '#2')], 'e124': [P('props:' + FD), P('props:' + AT), L(PO)],
 'e125': [OFF, L(PO), L(PC), L(M87), P('ctext:SOP-COOL-14'), L(MX)], 'e126': [N(CASE14), P('props:' + FD), L(FI), L(M81), P('ctext:SOP-FAN-11')],
 'e126b': [L(VB), L(BR), L(MX)], 'e127': [OFF, L(PC), L(FI)], 'e128': [N(CASE38), P('props:' + AT), P('props:' + PO), L(CV), L(PC)],
 'e129': [OFF, P('props:' + PO + '#2')],
 # 11구간 — 내보내기 · 새 그림 · 가져오기
 'e130': [A(ck('export'))], 'e131': [P('tab:PNG'), A([['download', 'png', 'Untitled graph']])], 'e132': [A([['click', 'tab:JSON'], ['download', 'json', 'Untitled graph']])],
 'e133': [A(ck('done'))], 'e134': [A(ck('blank'))], 'e135': [A(ck('logo'))],
 'e136': [P('menu:New'), P('menu:Open'), A([['point', 'menu:New'], ['click', 'menu:newLocal']])], 'e137': [L(''), A(ck('blank'))],
 'e138': [A([['click', 'logo'], ['click', 'menu:Import']])], 'e139': [A([['choose', 'json']])], 'e140': [A(ck('importButton'))],
 # e141: 다시 연 그림은 관계 글이 화살표를 따라 서서 세로 화살표의 절차 번호 셋이 원에 가려 잘린다 — 온전히 보이는 가로 화살표의 번호를 짚는다
 'e141': [P('selCount'), P('props:' + PO), P('ctext:SOP-FAN-11'), L(PC)], 'e142': [L(F), P('ctext:LEADS_TO')],
 'e143': [A([['click', 'blank'], ['click', 'node:'], ['click', 'text:Delete'], ['verify']])],
 # 12구간 — Cypher
 'e145': [A(ck('export'))], 'e146': [A(ck('tab:Cypher'))], 'e147': [P('cypherText'), P('cypherHead'), A(ck('done'))],
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
        for pre, word in (('node:', '원'), ('look:', '원'), ('ring:', '원 둘레의 하늘색 띠'), ('ctextL:', '글자의 앞'), ('ctextR:', '글자의 끝'), ('ctext:', '글자'), ('text:', '단추')):
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
    timing = f'''# ARROWS 실습 시간 — 실측

대상: [수업원고](수업원고.md). **실측 영상 길이 {dur / 60:.1f}분({dur:.1f}초)**, 음성 {len(cs)}큐(음성만 합하면 {spoken / 60:.1f}분). 쉼은 이어지는 말 0.6초 · 큐 사이 1.3초 · 결과 뒤 2.0초 · 구간 사이 2.3초다.

| 구간 | 녹화 조각(take) | 길이(초) |
|---|---|---|
''' + rows + f'''
합성한 뒤 말 없이 화면이 서 있는 곳 {len(cuts)}곳에서 쉼 기준을 넘는 {cut_s:.1f}초를 잘라 냈다(`잘라냄_통합1-08.json`, 구간 길이는 잘라 내기 전 값).

측정: 구간마다 `measure.py`의 0.5초 넘는 이동 공백 0, 튐은 모두 클릭이 만든 변화(오른쪽 칸 접기 · 내보내기 · 불러오기 창 · 지우기), 합성의 최대 프레임 간격 {rec['motion_summary']['max_gap_ms_max']}ms.
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
        data = {'voice_id': '1PdAOcPlPTz12RwMyFVp', 'model_id': 'eleven_v4', 'nodes': [list(n) for n in NODES],
                'relationships': RELS, 'properties': PROPS, 'cues': cues()}
        Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        print(len(data['cues']), 'cues')
    elif sys.argv[1] == 'sync':
        write_all()
    else:
        raise SystemExit('usage: build_ontology.py cues <path> | sync')
