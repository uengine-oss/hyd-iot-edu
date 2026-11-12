# 통합 1회차 04 포털 둘러보기(다시 찍을 판)의 큐 JSON을 확정 대본에서 만든다.
#   python3 통합_01_04_포털둘러보기_큐만들기.py <확정 대본.md>  → 같은 폴더의 통합_01_04_포털둘러보기_큐.json
# 대본 2절의 「### N.」 단계가 구간 N이다. 줄 안의 ‖는 쉼 자리, ▸는 조작 자리다.
# 큐: ‖로 나눈 덩이를 문장으로 쪼개고, 이미 조작이 있는 큐 뒤에 ▸가 든 문장이 오면 새 큐를 연다(영상 길 15 — 두 조작을 서로 다른 문장에서 말하면 큐를 나눈다).
# 시점: ▸가 놓인 글자 자리 ÷ 큐 글 길이(segs/map.mjs가 큐 시작 + 길이 × 비율 − 300ms에 조작한다).
# 쉼: 같은 덩이 안 큐 0.6 · ‖ 뒤 1.3 · 앞 큐가 누르기로 끝났으면 2.0 · 단계가 바뀌면 2.3초(사용자 2026-11-12 「이어지는 말 0.6초, 큐 사이 1.3초, 결과 뒤 2.0초, 구간 사이 2.3」 — 영상 V-14의 1회차 값 대신).
# 조작 표(OPS)의 대상은 길뚫기(포털 DOM 조사)로 찾은 것이다. ▸ 수와 조작 수가 다르면 멈춘다.
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / '통합_01_04_포털둘러보기_큐.json'
VOICE, MODEL = '1PdAOcPlPTz12RwMyFVp', 'eleven_v4'


def TAB(t):
    return ['click', {'css': f'.rail nav button[data-tab="{t}"]'}]


def P(css, **kw):
    return ['point', {'css': css, **kw}]


def V(view, sel, **kw):
    return P(f'#view-{view} {sel}', **kw)


def RAIL(t):
    return P(f'.rail nav button[data-tab="{t}"]')


GRAPH = {'css': '#pTs1', 'anchor': 'center', 'dx': 110}

# 단계마다 ▸ 차례대로 하나씩. 목록 안의 목록은 한 ▸에서 잇달아 하는 조작이다(둘째부터는 앞 조작 바로 뒤).
OPS = {
    2: [P('main span', exact='설비'), P('main span', exact='열린 사건'), P('main span', exact='지식 항목'),
        P('main span', exact='시간 배율'), P('#openCount'), P('#healthDots'), P('#shellMe'), P('#shellBell', anchor='center', dx=4, dy=6)],
    3: [P('main text', exact='현장 설비'), P('main text', exact='관제 · 데이터'), P('main text', exact='인공지능'),
        P('main text', exact='고장 유형 · 냉각 상실'), P('main text', exact='승인된 조치 → 검증 → 설비'),
        P('.rail .navgroup', exact='작업', anchor='after', dy=-7), P('.rail .navgroup', exact='시스템', anchor='after', dy=-7)],
    4: [TAB('scenario'), V('scenario', 'strong', exact='HYD-01'), V('scenario', 'span.v', nth=0, anchor='center', dx=18, dy=6),
        V('scenario', '.threshold-note', nth=0), V('scenario', '.kv span', exact='냉각 효율CE', nth=0),
        V('scenario', 'span.chip', exact='감시 중', nth=0), V('scenario', 'span.chip.tone-success', nth=0),
        V('scenario', 'span.chip', exact='정기 점검 도래'), V('scenario', 'button', exact='쿨러 열화 주입'),
        TAB('trends'), ['point', {**GRAPH, 'dy': 66}], ['point', {**GRAPH, 'dy': -74}], ['point', {**GRAPH, 'dy': 9}],
        TAB('oil'), V('oil', 'label', contains='측정값 (mgKOH/g)'), V('oil', 'label', contains='기준 이탈 여부'),
        TAB('incidents'), V('incidents', 'text', contains='탱크', nth=0), V('incidents', 'text', exact='P', nth=0, anchor='center', dy=-10),
        V('incidents', 'text', contains='팬', nth=0, anchor='center', dx=-35, dy=-17), V('incidents', 'b', exact='사건 없음', anchor='after', dy=-8),
        V('incidents', 'b', exact='설비를 선택하세요', anchor='after', dy=-8)],
    5: [TAB('ontology'), P('#ontoMap text', exact='전략 목표'), P('#ontoMap text', exact='자원'),
        P('#ontoMap text', exact='프로세스', anchor='center', dx=-70, dy=200), P('#ontoMap text', exact='이상 패턴 · 9'),
        P('#ontoMap text', exact='조치 방법과 규칙'),
        TAB('skills'), V('skills', 'span.sub', nth=0, anchor='left'), V('skills', 'span.chip', exact='정비 요청', nth=0),
        V('skills', 'span.sub', nth=0), V('skills', 'span.sub', contains='(근본 조치)', nth=0), V('skills', 'label', exact='승인 역할'),
        V('skills', 'h3', exact='절차'),
        TAB('knowledge'), V('knowledge', 'span.btn', exact='파일 선택', nth=0, anchor='center', dx=12, dy=-6), [['scroll', {'css': '#view-knowledge h2', 'contains': '등록된 매뉴얼', 'top': 70}], V('knowledge', 'h2', contains='등록된 매뉴얼')],
        V('knowledge', 'h3', contains='PR-07', anchor='center', dx=40, dy=-4), V('knowledge', 'h3', contains='PM-02', anchor='center', dx=40, dy=-4), V('knowledge', 'h3', contains='HM-8', anchor='center', dx=40, dy=-4),
        TAB('fabric'), V('fabric', 'b', exact='연결됨', nth=1, anchor='after', dy=-8), V('fabric', 'b', exact='없음', anchor='after', dy=-8)],
    6: [[TAB('ask'), V('ask', 'textarea')], V('ask', 'button.btn.small', nth=0),
        TAB('agents'), V('agents', 'strong', exact='교대 인수인계 에이전트', anchor='after', dy=-8), V('agents', 'strong', exact='냉각 긴급 대응 에이전트', anchor='after', dy=-8),
        V('agents', 'strong', exact='예비품 구매 에이전트', anchor='after', dy=-8), V('agents', 'button', exact='새 에이전트'),
        TAB('mcp'), V('mcp', 'h3', exact='판단 시스템', anchor='center', dx=20, dy=-4), V('mcp', 'span.chip.tone-success', nth=1),
        TAB('compare'), TAB('eval')],
    7: [TAB('decision'), V('decision', 'label', exact='설비'), V('decision', 'label', exact='이상 패턴'), P('#decRun'),
        V('decision', 'b', contains='판단을 실행하세요', anchor='after', dy=-8),
        TAB('whatif'), V('whatif', 'span', contains='카드별 손익'),
        TAB('flows'),
        TAB('process'), V('process', 'b', contains='처리 건의 흐름'), V('process', 'b', exact='아직 제출된 판단이 없습니다', anchor='after', dy=-8),
        [['scroll', {'css': '#view-process h2', 'contains': '기업 시스템 현황', 'top': 70}], V('process', 'h2', contains='기업 시스템 현황')], V('process', 'th', exact='납기까지 (시간)')],
    8: [[TAB('inbox'), P('select[data-inbox-me]')], V('inbox', 'p.field-hint'), P('select[data-inbox-me]'),
        TAB('instances'), V('instances', 'span', exact='진행 중'), V('instances', 'span', exact='내 차례'),
        V('instances', 'b', exact='아직 처리 건이 없습니다', anchor='after', dy=-8), V('instances', 'b', exact='처리 건을 선택하세요', anchor='after', dy=-8)],
    9: [TAB('kpi'), V('kpi', 'h3', exact='에너지비', anchor='center', dx=10, dy=-4), V('kpi', 'h3', contains='설비 가동률', anchor='center', dx=20, dy=-4),
        RAIL('main'), TAB('home'), V('home', 'strong', exact='프로세스 · 승인 · 앱', anchor='center', dx=20, dy=-10), V('home', 'span.role-desc', nth=0),
        V('home', '.dot', nth=0, anchor='center', dy=6), RAIL('admin')],
    10: [TAB('main'), P('nav.page-navigation button.next'), P('main text', exact='인공지능')],
}

# ▸ 말고 대사 구절에 맞춰 더 하는 조작: (구간, 구절) → 조작(목록이면 그 구절에서 잇달아). 그 구절이 든 큐에서, 구절이 시작하는 글자 비율에 넣는다.
# 모두 화면대조에서 「말하는 대상이 그 순간 화면에 없음」으로 걸린 꼴을 화면 쪽에서 고친 것이다(대사는 그대로).
#  · 「이 그림」처럼 화면 전체를 받는 말에서 커서가 엉뚱한 데 남음(1~3구간 t4-03-01)
#  · 「이 카드 숫자가」에서 화면이 버튼 쪽으로 내려가 숫자가 안 보임(3~4구간 t4-04-09) — 숫자를 다시 짚어 본문이 말없이 올라오게
#  · 두 카드의 승인 역할을 말하는데 커서가 한 곳(5구간 t4-05-10)
#  · 메뉴 제목(설비 · 판단 · 인공지능 설정 …)을 말하는데 그 제목이 메뉴 밖(6~7구간 t4-06-01 · t4-07-01) — 메뉴 제목을 말하는 모든 자리에 건다
#  · 종 그림 옆 빈 자리를 짚음(2구간 t4-02-06 — 그림 단추는 가운데를 짚는다), 길 위 MQTT · DMZ와 메뉴 제목 「설비」를 부르는데 커서가 그 위에 없음(3구간 t4-03-02 · t4-03-05)
#  · 맺음에서 설비 → AI → 승인 → 설비 흐름을 부르는데 커서가 인공지능 마디에만 있음(10구간 t4-10-03)
#  · 「가운데 운전 모드」에서 커서가 아래 안내 글(t4-07-03), 생산 · 정비 · 구매를 말하는데 구매 칸이 화면 밖(t4-07-08 — 「밑으로 내려 보시면」에서 실제로 내리고 칸마다)
ENT = '#view-process h3, #view-process strong, #view-process b'


def GROUP(t, top=None):
    o = P('.rail .navgroup', exact=t, anchor='after', dy=-7)
    return [['scroll', {'css': '.rail .navgroup', 'exact': t, 'top': top}], o] if top else o


EXTRA = {
    (3, '밑에 이 그림은'): P('#view-main svg.m-hero-svg', anchor='center'),
    (3, 'MQTT랑'): P('main text', exact='MQTT'),
    (3, 'DMZ를'): P('main text', exact='DMZ'),
    (3, '설비 이렇게'): GROUP('설비'),
    (4, '이 숫자들이 시간에'): V('scenario', 'span.v', nth=0, anchor='center', dx=18, dy=6),
    (5, '지식 아래 지식 지도'): GROUP('지식'),
    (5, '팬 최대 운전은'): V('skills', 'span.sub', nth=0),
    (5, '쿨러 핀 세척은'): V('skills', 'span.sub', contains='(근본 조치)', nth=0),
    (6, '인공지능 설정 쪽'): GROUP('인공지능 설정', top=300),
    (7, '판단 쪽 메뉴'): GROUP('판단'),
    (7, '가운데 운전 모드'): V('decision', 'label', exact='운전 모드'),
    (7, '생산,'): P(ENT, exact='생산 관리'),
    (7, '정비,'): P(ENT, exact='정비 관리'),
    (7, '구매에'): P(ENT, exact='구매 · 재고 관리'),
    (8, '작업 아래, 내 작업함'): GROUP('작업'),
    (9, '성과 아래 성과 지표'): GROUP('성과'),
    (9, '마지막 시스템 아래에는'): GROUP('시스템'),
    (10, '설비에서 값이'): P('main text', exact='현장 설비'),
    (10, 'AI가 지식을'): P('main text', exact='인공지능'),
    (10, '사람이 승인하면'): P('main text', exact='승인된 조치 → 검증 → 설비'),
}

GAP_IN, GAP_PAUSE, GAP_RESULT, GAP_SEG = 0.6, 1.3, 2.0, 2.3


def body(md):
    s = md.split('## 2. 새 대본 전문', 1)[1].split('# 촬영 본문 끝', 1)[0]
    segs = {}
    for m in re.finditer(r'^### (\d+)\.[^\n]*\n(.*?)(?=^### |\Z)', s, re.S | re.M):
        segs[int(m.group(1))] = [ln.strip() for ln in m.group(2).strip().split('\n') if ln.strip()]
    return segs


def clean(t):
    return re.sub(r'\s+', ' ', t.replace('▸', ' ')).strip()


def build(md):
    segs, cues = body(md), []
    for n in sorted(segs):
        ops = [o if isinstance(o[0], list) else [o] for o in OPS.get(n, [])]
        marks = sum(ln.count('▸') for ln in segs[n])
        if marks != len(ops):
            sys.exit(f'단계 {n}: 대본 ▸ {marks}개 · 조작 표 {len(ops)}개 — 맞춰야 한다')
        k, seq, first = 0, 0, True
        for ln in segs[n]:
            for chunk in [c.strip() for c in ln.split('‖') if c.strip()]:
                groups = []
                for snt in re.split(r'(?<=[.?!])\s+', chunk):
                    if groups and '▸' in snt and any('▸' in s for s in groups[-1]):
                        groups.append([snt])
                    elif groups:
                        groups[-1].append(snt)
                    else:
                        groups.append([snt])
                for gi, g in enumerate(groups):
                    raw = ' '.join(g)
                    text, qops = clean(raw), []
                    parts = raw.split('▸')
                    for i in range(1, len(parts)):
                        head = clean('▸'.join(parts[:i]))
                        pos = len(head) + 1 if head else 0
                        grp = ops[k]; k += 1
                        qops.append([*grp[0], round(min(0.98, pos / len(text)), 3)])
                        qops.extend(grp[1:])
                    seq += 1
                    if first:
                        gap = GAP_SEG
                    elif gi > 0:
                        gap = GAP_IN
                    else:
                        prev = cues[-1]['ops']
                        gap = GAP_RESULT if prev and prev[-1][0] == 'click' else GAP_PAUSE
                    first = False
                    cues.append({'id': f't4-{n:02d}-{seq:02d}', 'segment': n, 'text': text, 'gap': gap, 'ops': qops})
    for (n, at), o in EXTRA.items():
        hit = [c for c in cues if c['segment'] == n and at in c['text']]
        if len(hit) != 1:
            sys.exit(f'EXTRA ({n}, {at}): 그 구절이 든 큐 {len(hit)}개 — 하나여야 한다')
        c, grp = hit[0], (o if isinstance(o[0], list) else [o])
        f = round(c['text'].index(at) / len(c['text']), 3)
        units, cur = [], None   # 시점이 있는 조작 + 그 뒤 시점 없는 조작 = 한 덩이. 시점 차례로 끼운다
        for op in c['ops']:
            if isinstance(op[-1], (int, float)) and not isinstance(op[-1], bool) and op[0] != 'wait':
                cur = [op]; units.append(cur)
            else:
                cur.append(op)
        units.append([[*grp[0], f], *grp[1:]])
        units.sort(key=lambda u: u[0][-1])
        c['ops'] = [op for u in units for op in u]
    # 메뉴를 누른 뒤 화면은 서버 응답으로 그려진다 — 누르기 바로 뒤에 다음 가리킬 대상이 나타날 때까지 기다린다(이미 있으면 바로 지나간다)
    flat = [(c, i) for c in cues for i in range(len(c['ops']))]
    for j, (c, i) in enumerate(flat):
        o = c['ops'][i]
        if o[0] != 'click' or 'data-tab' not in o[1]['css']:
            continue
        nxt = flat[j + 1][0]['ops'][flat[j + 1][1]] if j + 1 < len(flat) and flat[j + 1][0]['segment'] == c['segment'] else None
        if nxt and nxt[0] == 'point':
            c.setdefault('_waits', []).append((i, {k: v for k, v in nxt[1].items() if k in ('css', 'contains', 'exact')}))
    for c in cues:
        for i, t in sorted(c.pop('_waits', []), key=lambda x: -x[0]):
            c['ops'].insert(i + 1, ['wait', t, 15])
    return cues


def main():
    src = Path(sys.argv[1])
    cues = build(src.read_text(encoding='utf-8'))
    doc = {'voice_id': VOICE, 'model_id': MODEL,
           'note': f'통합 1회차 04 포털 둘러보기(다시 찍을 판). {src.name}에서 통합_01_04_포털둘러보기_큐만들기.py로 만든다 — 손으로 고치지 않는다. 모듈 segs/tour04.mjs',
           'cues': cues}
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    by = {}
    for c in cues:
        by.setdefault(c['segment'], []).append(c)
    for n, cs in by.items():
        print(f'구간 {n}: 큐 {len(cs)} · 조작 {sum(len(c["ops"]) for c in cs)} · 글자 {sum(len(c["text"]) for c in cs)}')
    print(f'모두 큐 {len(cues)} · 글자 {sum(len(c["text"]) for c in cues)} → {OUT.name}')


if __name__ == '__main__':
    main()
