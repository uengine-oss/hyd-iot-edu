"""ARROWS 실습 원본: 교재 SLIDE 67·73·74의 쿨러 지식 그래프를 arrows.app에서 그리는 큐(발화+조작).
이 파일 하나가 음성 목록·촬영 조작·수업 원고·두 과정 랩 산출물의 원본이다. 앱·음성 API는 호출하지 않는다.
사용: python build_ontology.py cues <cues.json 출력 경로>   # 촬영용 큐
      python build_ontology.py sync                       # 수업원고·시간·두 과정 대본 · 한 파일 가이드 동기화
"""
import json, re, sys
from pathlib import Path

# 원: Caption, Label. 이름·관계는 it/neo4j/v2/instances.cypher와 랩 HM-8 발췌를 따른다. 배치는 촬영 중 화면을 보고 정한다.
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

# ── 큐 원본(2026-11-12 다시 찍을 판) ──────────────────────────────────────────────
# 낭독 글은 대본원고.md(사용자가 확정한 대본 「2. 새 대본 전문」)이고, 여기 MAP이 그 글의 ▸ 자리마다 조작을 단다.
# MAP의 한 칸 = ('A', 조작들): 그 말이 끝날 때 하고 큐를 끊는다 · ('P', 조작들): 바로 뒤 낱말을 말할 때 짚는다(끊지 않음)
#             · ('T', 조작들): 말 속 그 자리에서 바로 한다(끊지 않음, Ctrl로 함께 고르기처럼 말하면서 하는 조작).
# 쉼: ▸로 끊은 다음 큐 · ‖ 뒤 · 조작 결과 뒤 ‖ · 따라 적은(type) 뒤 ‖ · 단계가 바뀌는 곳 — 값은 아래 GAP.
# 원은 처음부터 끝 자리에 놓는다(사용자 「정돈하기 … 더 자연스러운 방향」): POS = 끝 그림의 그림 좌표(HYD-01 = 새 그림의 빈 원 (0, 0)).
H, K, S, U, F = 'HYD-01 유압 파워팩', '오일 쿨러', '유온 센서 TS1', '유온 상승', '쿨러 냉각 성능 상실'
PO, MX, PC, M85, M87 = '쿨러 핀 오염', '팬 최대 운전', '쿨러 핀 세척', 'HM-8.5 즉시 완화 조치', 'HM-8.7 근본 조치'
FD, FI, M81, AT, CV, BR, VB = '팬 구동 불량', '팬 점검', 'HM-8.1 팬 벨트 점검', '주변 온도 상승', '캐비닛 환기 보강', '팬 베어링 열화', '진동 증가'
POS = {H: (0, 0), K: (290, 0), S: (290, 260), U: (550, 260), F: (550, 0), PO: (945, 175), MX: (720, 330), PC: (830, 0), M85: (1120, 330),
       M87: (1120, 0), FD: (520, -385), FI: (810, -420), M81: (1120, -430), AT: (830, -260), CV: (1120, -295), BR: (290, -220), VB: (0, -220)}
# 원 크기 60 · 110 % 화면. 그림판이 좁아 원 사이를 줄였고, 관계 이름 끝 글자 몇 곳(HAS_COMPONENT · MONITORED_BY · OBSERVED_BY · 핀 세척→핀 오염 ADDRESSES)과 핀 오염 증거 끝 「mm/s」가 원 · 칸 가장자리에 조금 걸린다(사용자 「노드가 가려지는 것만 아니면 상관없는데」). 원끼리는 겹치지 않는다.
# WHEEL = 배율 1에서 끝 그림이 그림판(CSS 1744×981의 1319×909)에 다 들어오는 보기 위치. 새 그림의 빈 원은 가운데에 있으므로 2단계 말 「마우스 휠로」에서 휠로 옮긴다.
# arrows는 보기 배율이 그림 맞춤보다 작으면 누를 때 맞춤으로 되돌리므로(촬영준비 함정) 배율은 1 그대로 둔다.
WHEEL = (114, 500)   # 원이 하나일 때 arrows가 왼쪽으로 옮기는 한계는 반지름 + 54(원 70에서 x 124를 잼)
RED, GREEN = '#fca5a5', '#86efac'
CASE = '쿨러 사건\n냉각 효율 30초 평균 46.2 %\n팬 진동 2분 평균 0.575 mm/s\n캐비닛 온도 2분 평균 28 ℃'
CASE38 = '냉각 효율 30초 평균 46.2 %\n팬 진동 2분 평균 0.575 mm/s\n캐비닛 온도 2분 평균 38 ℃'

def nn(c):
    return [['click', 'caption'], ['type', c], ['click', 'labelPlus'], ['click', 'labelInput'], ['type', KIND[c]], ['key', 'Tab']]
def gt(src, dst):
    return [['growTo', src, *POS[dst]]]
def et(a, b, t=None, rev=False):
    return [['edge', a, b]] + ([['click', 'reverse']] if rev else []) + ([['click', 'type'], ['type', t]] if t else [])
def ty(t):
    return [['click', 'type'], ['type', t]]
def con(a, b, t=None):
    return [['click', 'node:' + a], ['connect', a, b]] + (ty(t) if t else [])
def pv(k, v):
    return [['click', 'propKey'], ['type', k], ['click', 'propVal'], ['type', v]]
def color(v):
    return [['click', 'style:node-color'], ['key', 'ControlOrMeta+A'], ['type', v], ['key', 'Tab']]
A = lambda *ops: ('A', [o for x in ops for o in x])
P = lambda t: ('P', [['point', t]])
N = lambda text: ('P', [['note', text, 'tl']])
T = lambda *ops: ('T', [o for x in ops for o in x])
L = lambda c: P('look:' + c)

MAP = {
 1: [A([['click', 'text:Use necessary cookies only']]), A([['click', 'done']]), P('canvasMid'), P('node:'), P('panelMid'), P('samples'), P('orange')],
 2: [P('node:'), A([['click', 'customize']]), A([['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '60'], ['key', 'Tab']]), T([['wheelTo', *WHEEL]])],
 3: [A([['click', 'node:']]), A([['click', 'caption'], ['type', H]]), A([['click', 'labelPlus']]), A([['click', 'labelInput'], ['type', 'Asset'], ['key', 'Tab']]), P('ctext:Asset')],
 4: [A(gt(H, K)), A(nn(K)), A([['edge', H, K]]), A(ty('HAS_COMPONENT')), P('ctext:HAS_COMPONENT'), L(H), L(K)],
 5: [A(gt(K, S)), A(nn(S)), A(et(K, S, 'MONITORED_BY'))],
 6: [A(gt(S, U)), A(nn(U)), P(f'edgeMid:{S}>{U}'), A(et(S, U, rev=True)), A(ty('OBSERVED_BY')), P('ctext:MONITORED_BY'), P('ctext:OBSERVED_BY')],
 7: [A(gt(U, F)), A(nn(F)), A(et(U, F, 'INDICATES')), A(con(F, K)), A(ty('OCCURS_IN')), L(U), L(S), L(F), L(K)],
 8: [A(gt(F, PO)), A(nn(PO)), P(f'edgeMid:{F}>{PO}'), A(et(F, PO, rev=True)), A(ty('CAUSES'))],
 9: [A([['click', 'node:' + PO]]), A([['click', 'propPlus']]), P('propKey'), P('propVal'),
     A([['click', 'propKey'], ['type', '냉각 효율']]), A([['click', 'propVal'], ['type', '30초 평균 < 70 %']]), A([['click', 'propPlus']]),
     A(pv('팬 진동', '2분 평균 < 0.9 mm/s')), P('props:' + PO)],
 10: [A(gt(F, MX)), A(nn(MX)), A(et(F, MX, 'MITIGATED_BY')), A(gt(F, PC)), A(nn(PC)), A(et(F, PC, 'REMEDIED_BY')), A(con(PC, PO)), A(ty('ADDRESSES'))],
 11: [A(gt(MX, M85)), A([['click', 'caption'], ['type', M85]]), A([['click', 'labelPlus'], ['click', 'labelInput'], ['type', 'ManualSection'], ['key', 'Tab']]),
      A(et(MX, M85, 'REFERS_TO')), A(gt(PC, M87)), A(nn(M87)), A(et(PC, M87, 'REFERS_TO'))],
 12: [A(gt(F, FD)), A(nn(FD)), A(et(F, FD, 'CAUSES', rev=True)), A([['click', 'node:' + FD], ['click', 'propPlus']]), A(pv('팬 진동', '2분 평균 ≥ 0.9 mm/s')),
      P('props:' + PO), P('props:' + FD), A(gt(F, FI)), A(nn(FI)), A(et(F, FI, 'REMEDIED_BY')), A(con(FI, FD, 'ADDRESSES')), A(gt(FI, M81)), A(nn(M81), et(FI, M81, 'REFERS_TO'))],
 13: [A(gt(F, AT)), A(nn(AT)), A(et(F, AT, 'CAUSES', rev=True)), A([['click', 'node:' + AT], ['click', 'propPlus']]), A(pv('캐비닛 온도', '2분 평균 ≥ 35 ℃')),
      A(gt(AT, CV)), A(nn(CV)), P(f'edgeMid:{AT}>{CV}'), A(et(AT, CV, 'ADDRESSES', rev=True)), A(con(F, CV, 'REMEDIED_BY')), A(con(CV, M87, 'REFERS_TO'))],
 14: [A(gt(F, BR)), A(nn(BR)), A(et(F, BR, rev=True)), A(ty('LEADS_TO')), A(gt(BR, VB)), A(nn(VB)), A(et(BR, VB, 'INDICATES', rev=True)), L(VB), L(BR), L(F)],
 15: [A([['edge', MX, M85]]), A([['click', 'propPlus']], pv('절차', 'SOP-COOL-11')), P('ctext:SOP-COOL-11'),
      A([['edge', PC, M87], ['click', 'propPlus']], pv('절차', 'SOP-COOL-14')), A([['edge', CV, M87], ['click', 'propPlus']], pv('절차', 'SOP-COOL-15')),
      A([['edge', FI, M81], ['click', 'propPlus']], pv('절차', 'SOP-FAN-11')), P('ctext:SOP-COOL-14'), P('ctext:SOP-COOL-15')],
 16: [L(H), L(F), L(PC), L(M87), T([['click', 'node:' + PO], ['ctrlclick', 'node:' + FD]]), T([['ctrlclick', 'node:' + AT]]), ('P', []), P('selCount'), A(color(RED)),
      T([['click', 'node:' + MX]]), T([['ctrlclick', 'node:' + PC]]), T([['ctrlclick', 'node:' + FI]]), T([['ctrlclick', 'node:' + CV]]), ('A', []), A(color(GREEN)),
      L(FD), L(PC), A([['click', 'blank'], ['click', 'panelToggle']])],
 17: [L(F), L(PO), L(FD), L(AT), N(CASE), P('props:' + PO), P('props:' + FD), P('props:' + AT), L(PO),
      L(PC), L(M87), L(MX), L(M85), N('팬 진동 2분 평균 1.4 mm/s'), P('props:' + FD), L(FI), L(M81), L(BR), N(CASE38), P('props:' + AT), P('props:' + PO), L(CV), L(PC), P('props:' + PO)],
 18: [A([['click', 'export']]), A([['download', 'png', 'Untitled graph']]), A([['click', 'tab:JSON'], ['download', 'json', 'Untitled graph']]), A([['click', 'done']]),
      A([['click', 'logo']]), A([['point', 'menu:New'], ['click', 'menu:newLocal']]), P('node:'), A([['click', 'logo'], ['click', 'menu:Import']]), A([['choose', 'json']]),
      P('importText'), A([['click', 'importButton']]), A([['click', 'panelToggle']]), P('selCount'), P('props:' + PO), P('ctext:SOP-COOL-14'), P('node:'),
      A([['click', 'node:'], ['click', 'text:Delete'], ['verify']])],
 19: [A([['click', 'export']]), A([['click', 'tab:Cypher']]), P('cypherText'), A([['click', 'done']])],
 20: [],
}
SEG_OF = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3, 8: 4, 9: 4, 10: 5, 11: 5, 12: 6, 13: 7, 14: 8, 15: 8, 16: 9, 17: 10, 18: 11, 19: 12, 20: 12}
# 쉼(ms): 사용자 2026-11-12 「이어지는 말 0.6초, 큐 사이 1.3초, 결과 뒤 2.0초, 구간 사이 2.3」(영상 V-14 2회차 값과 같다). 따라 적은 뒤도 결과 뒤와 같은 2.0초. 5초씩 멈춰 있는 자리만 없게 한다(사용자 「쉼 없이 하라는 게 아니라 5초 이런 것만 막는 거」).
GAP = {'join': 600, 'pause': 1300, 'result': 2000, 'follow': 2000, 'stage': 2300}


def stages():
    """대본원고.md → [(단계 번호, 제목, 본문)]."""
    t = (ROOT / '대본원고.md').read_text(encoding='utf-8')
    out = []
    for x in re.split(r'^### ', t, flags=re.M)[1:]:
        head, body = x.split('\n', 1)
        n = int(head.split('.')[0])
        out.append((n, head.strip(), ' '.join(body.split())))
    return out


def cues():
    """낭독 원고의 ▸ · ‖ · 〔글상자〕와 MAP으로 큐를 만든다. MAP 칸 수가 ▸ 수와 다르면 단계 번호와 함께 멈춘다."""
    out = []

    def flush(cur, marks, acts, gap, seg, cut):
        raw = cur
        text = raw.strip()
        if not text and not marks and not acts:
            return None
        lead = len(raw) - len(raw.lstrip())
        ops = []
        for pos, o in marks:
            frac = 0.0 if not text else max(0.0, min(0.95, (pos - lead) / len(text)))
            ops += [['at', round(frac, 3)]] + o
        if acts:
            ops += ([['atend']] if marks else []) + acts
        c = {'id': f'a{len(out) + 1:03}', 'segment': seg, 'text': ' '.join(text.split()), 'ops': ops, 'gap': gap}
        if acts and not marks:
            c['cut'] = True
        out.append(c)
        return c

    for n, head, body in stages():
        seg, m = SEG_OF[n], list(MAP[n])
        want = body.count('▸')
        if len(m) != want:
            raise SystemExit(f'{n}단계 「{head}」: ▸ {want}곳인데 MAP 칸이 {len(m)}개다 (build_ontology.py MAP)')
        body = re.sub(r'〔글상자:[^〕]*〕', '', body)
        toks = re.split(r'(▸|‖|〔글상자 내림〕)', body)
        cur, marks, acts, gap = '', [], [], GAP['stage']
        for tok in toks:
            if tok == '▸':
                kind, ops = m.pop(0)
                if kind == 'A':
                    acts += ops
                    c = flush(cur, marks, acts, gap, seg, True)
                    cur, marks, acts, gap = '', [], [], GAP['join']
                else:
                    marks.append((len(cur), ops))
            elif tok == '〔글상자 내림〕':
                marks.append((len(cur), [['note', None]]))
            elif tok == '‖':
                c = flush(cur, marks, acts, gap, seg, False)
                if c is None and out:
                    c = out[-1]
                typed = c and any(o[0] == 'type' for o in c['ops'])
                acted = c and any(o[0] not in ('at', 'point', 'note') for o in c['ops'])
                cur, marks, acts = '', [], []
                gap = GAP['follow'] if typed else GAP['result'] if acted else GAP['pause']
            else:
                cur += tok
        flush(cur, marks, acts, gap, seg, False)
    for c in out:
        if not c['text']:
            raise SystemExit(f"{c['id']}: 말이 빈 큐 — ▸ 자리를 원고에서 확인 (조작 {c['ops'][:2]})")
    return out


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
EVID = REPO / '작업' / '촬영' / 'arrows'          # 녹화 원본 · 합성 출력(git 밖)
FINAL = '통합1-08-관계그림'                        # 합성 출력 이름(포털 encode.py --도구 arrows) — 합성기록/<FINAL>.json
VIDEO_NAME = '통합반_01회차_08_실습_관계그림.mp4'
SEGMENT_TITLE = {1: 'arrows.app 열기 · 원 크기 · 첫 원(설비)', 2: '쿨러 · 센서 · 첫 관계', 3: '증상 · 방향 뒤집기 · 고장 유형', 4: '원인 · 증거(속성)',
                 5: '완화 · 근본 조치 · 근거 매뉴얼', 6: '두 번째 원인 · 팬 구동 불량', 7: '세 번째 원인 · 주변 온도 상승', 8: '고장이 고장으로 · 절차 번호',
                 9: '원인 · 조치 색칠', 10: '그림으로 판단하기', 11: '파일로 남기고 다시 열기', 12: 'Cypher로 바꿔 보기 · 맺음'}
TARGET = {'caption': 'Caption 입력칸 클릭', 'labelPlus': 'Label 옆 + 클릭', 'labelInput': '새 Label 입력칸 클릭',
          'propPlus': 'Property 옆 + 클릭', 'propKey': '새 속성의 왼쪽(이름) 칸 클릭', 'propVal': '오른쪽(내용) 칸 클릭', 'type': 'Type 입력칸 클릭',
          'blank': '그림의 빈 곳 클릭(선택 해제)', 'customize': 'STYLE의 Customize 클릭', 'style:radius': 'radius 입력칸 클릭',
          'reverse': 'Reverse 클릭(화살표 방향 뒤집기)', 'export': 'Download / Export 클릭', 'tab:JSON': 'JSON 탭 클릭', 'tab:PNG': 'PNG 탭 클릭',
          'done': 'Done 클릭', 'logo': '왼쪽 위 로고 메뉴 클릭', 'menu:newLocal': 'New ▸ Web Browser storage 클릭(새 그림)', 'menu:Import': 'Import 클릭',
          'menu:New': 'New에 커서 올리기', 'importButton': '창 아래 Import 버튼 클릭', 'panelToggle': '오른쪽 위 ☰ 클릭(오른쪽 칸 접기 · 펴기)',
          'canvasMid': '그림 영역 가리키기', 'panelMid': '오른쪽 칸 가리키기', 'samples': '모양 견본 가리키기', 'orange': '주황 Save to Google Drive 가리키기',
          'node:': '빈 원 클릭', 'cypherText': 'Cypher 글 가리키기', 'tab:Cypher': 'Cypher 탭 클릭', 'style:node-color': 'node-color 입력칸 클릭',
          'selCount': '오른쪽 nodes 개수 가리키기', 'importText': '가져오기 칸에 채워진 파일 내용 가리키기', 'download': 'Download 클릭'}


def act(op):
    k, *a = op
    if k in ('at', 'atend'):
        return None
    if k in ('click', 'point'):
        t = a[0]
        if t in TARGET:
            return TARGET[t]
        for pre, word in (('node:', '원'), ('look:', '원'), ('props:', '원의 증거 줄'), ('ctext:', '글자'), ('text:', '단추')):
            if t.startswith(pre):
                return f'‘{t[len(pre):]}’ {word} ' + ('클릭' if k == 'click' else '가리키기')
        if t.startswith('edgeMid:'):
            x, y = t[8:].split('>')
            return f'‘{x}’ → ‘{y}’ 화살표 가리키기'
        return t
    if k == 'type':
        return f'`{a[0]}` 입력'
    if k == 'key':
        return {'ControlOrMeta+A': 'Ctrl+A(칸 전체 선택)', 'Tab': 'Tab(입력 마침)'}.get(a[0], a[0] + ' 키')
    if k == 'growTo':
        return f'‘{a[0]}’ 원 테두리 바로 바깥을 잡아 빈 곳으로 끌기 → 새 원과 화살표 생성'
    if k == 'wheelTo':
        return '마우스 휠로 그림판 옮기기(왼쪽으로)'
    if k == 'edge':
        return f'‘{a[0]}’–‘{a[1]}’ 사이 화살표 클릭(관계 선택)'
    if k == 'connect':
        return f'‘{a[0]}’ 테두리를 잡아 ‘{a[1]}’ 원 위에 놓기 → 화살표 생성'
    if k == 'download':
        return 'Download 클릭 → 파일 저장 확인'
    if k == 'ctrlclick':
        return f'Ctrl 누른 채 ‘{a[0][5:]}’ 원 클릭(함께 선택)'
    if k == 'choose':
        return 'Choose File로 방금 저장한 JSON 선택'
    if k == 'verify':
        return '원 17 · 화살표 21 · 원인 증거 · 절차 번호 복원 확인'
    if k == 'note':
        return '화면 위에 사건 값 글상자 띄우기' if a[0] else '글상자 내리기'
    return k


def manuscript():
    out = [f'''# ARROWS 실습 — 쿨러 고장의 지식 그래프 그리기

2026-11-12 다시 찍은 판이다. 사용자가 확정한 대본(윤문 4차)을 클라우드 Playwright 녹화기로 찍고(브라우저 배율 약 110 %, 원 크기 60), 화면은 그대로 둔 채 말만 다듬은 윤문 5 · 6차의 음성으로 합성했다. 영상은 `{VIDEO_NAME}`(정본은 Release 「영상」 — 영상 V-7)이고, 구간 · 시간은 제작용 [예상시간](예상시간.md)에 있다.

## 진행 메모 — 낭독하지 않음

- 실제로 찍은 큐 그대로다. 발화로 대상과 까닭을 먼저 말하고, 조작은 그 말 끝(짚기는 그 낱말을 말할 때)에 한다. 결과가 보이면 다음 말로 간다.
- 원은 처음부터 끝 자리에 놓는다(정리 단계 없음). 새 그림의 빈 원을 첫 원으로 쓰고, 나머지는 원 테두리를 빈 곳으로 끌어 원과 화살표를 함께 만든다. 원인 → 고장(CAUSES), 증상 → 센서(OBSERVED_BY), 고장 → 고장(LEADS_TO), 증상 → 고장(INDICATES), 조치 → 원인(ADDRESSES)은 끌어낸 방향이 반대면 Reverse로 뒤집는다.
- 색은 판단 앞에서 Ctrl로 함께 골라 한 번에 칠한다: 원인 셋 `#fca5a5`(연한 빨강), 조치 넷 `#86efac`(연한 초록).
- 입력값 출처: 클래스 · 관계 이름은 `workspace/개발/문서/ontology/schema-v2.md` · `it/neo4j/v2/instances.cypher`, 판별 기준은 랩 `매뉴얼_발췌.md` HM-8.4, 조치 근거는 HM-8.1 · 8.5 · 8.7.
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

대상: 2026-11-12 판 [수업원고](수업원고.md). **실측 영상 길이 {dur / 60:.1f}분({dur:.1f}초)**, 음성 {len(cs)}큐(음성만 합하면 {spoken / 60:.1f}분). 쉼은 이어지는 말 0.6초 · 큐 사이 1.3초 · 결과 뒤 2.0초 · 구간 사이 2.3초다.

| 구간 | 녹화 조각(take) | 길이(초) |
|---|---|---|
''' + rows + f'''
합성한 뒤 말 없이 화면이 서 있는 곳 {len(cuts)}곳에서 쉼 기준을 넘는 {cut_s:.1f}초를 잘라 냈다(`잘라냄_통합1-08.json`, 구간 길이는 잘라 내기 전 값).

측정: 구간마다 `measure.py`의 0.5초 넘는 이동 공백 0, 튐은 모두 클릭이 만든 변화(오른쪽 칸 접기 · 내보내기 · 불러오기 창 · 지우기), 합성의 최대 프레임 간격 {rec['motion_summary']['max_gap_ms_max']}ms.
'''
    (ROOT / '예상시간.md').write_text(timing, encoding='utf-8')
    screens = f'''# 화면 — 촬영 완료

1회차 실습 4 영상(`{VIDEO_NAME}`)의 실제 화면이다(클라우드 Playwright, 브라우저 배율 약 110 %, 프레임 1920×1080).

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
