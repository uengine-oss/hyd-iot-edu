# 확정 대본(05_새대본_다시찍을판.md 2절)을 ▸ · ‖에서 잘라 큐 JSON을 만든다. 조작은 아래 OPS 표, 쉼은 영상 V-14(2회차) 값.
# 쓰는 법: python3 큐만들기.py <대본.md> <출력 큐.json>
import json, re, sys
src, dst = sys.argv[1:3]
s = open(src, encoding='utf-8').read()
body = s[s.index('### 1. 여는 말'):s.index('---\n', s.index('## 2. 새 대본 전문'))]
cues = []
for m in re.finditer(r'### (\d)\. [^\n]*\n(.*?)(?=\n### |\Z)', body, re.S):
    seg = int(m[1]); parts = re.split(r'\s*(▸|‖)\s*', m[2].replace('\n', ' ')); k = 0
    for i in range(0, len(parts) - 1, 2):
        t = parts[i].strip()
        if not t: cues[-1]['_after'] += parts[i + 1]; continue
        k += 1; cues.append({'id': f'm05-{seg}{k:02d}', 'segment': seg, 'text': t, '_after': parts[i + 1]})

def L(i): return {'css': f'#ontoNode a[data-go="{i}"]'}
def LX(t): return {'css': '#ontoNode a[data-go]', 'exact': t}
def K(k): return {'css': '#ontoNode .kvt th', 'exact': k}
def H(w): return {'css': '#ontoNode h4', 'contains': w}
def N(i): return {'css': f'#ontoMap .o-node[data-id="{i}"]'}
def LAB(t): return {'css': '#ontoMap .o-lab', 'exact': t}
def COLH(t): return {'css': '#ontoMap .o-colh', 'exact': t}
KIND = {'css': '#ontoNode .o-kind'}; H3 = {'css': '#ontoNode h3'}; MATCH = {'css': '#ontoMap .o-node.match'}
TH0 = {'css': '#ontoNode .kvt th', 'nth': 0}; DETAIL = {'css': '#ontoNode', 'top': 96}
def at(x): return {'at': x}
def kind(t): return ['wait', {'css': '#ontoNode .o-kind', 'exact': t}, 10]
OPS = {
 '102': [['click', {'css': '.rail nav button[data-tab=ontology]'}, at('지식 지도를')], ['wait', {'css': '#ontoMap .o-node'}, 20]],
 '103': [['point', {'css': '#ontoStats'}, at('이 지도에 담긴')]],
 '201': [['point', {'css': '#ontoAsset'}, at('설비 칸')]],
 '202': [['point', {'css': '#ontoNs'}, 0.1], ['point', {'css': '#ontoFocus'}, 0.6]],
 '203': [['point', {'css': '#ontoSearch'}, 0.1]],
 '204': [['point', {'css': '#ontoReload'}, 0.1]],
 '205': [['point', COLH('전략 목표'), at('세로 칸')], ['point', COLH('설비 진단'), at('영역을')], ['point', COLH('자원'), at('설비와 센서')]],
 '206': [['point', COLH('설비 진단'), 0.3]],
 '207': [['point', COLH('조치 방법과 규칙'), 0.3]],
 '208': [['point', LAB('부서 · 7'), 0.15], ['point', LAB('설비 · 1'), at('설비는 그 밑')]],
 '209': [['point', {'css': '#ontoStats'}, at('이 줄 끝')]],
 '210': [['point', {'css': '#ontoLayers .chiptoggle', 'contains': '전략 목표'}, at('위의 단추')]],
 '211': [['chip', '전략 목표', 0.1]],
 '212': [['chip', '프로세스', 0.1]],
 '213': [['chip', '외부 변수', at('외부 변수')]],
 '214': [['chip', '내 업무 개념', 0.1]],
 '215': [['point', {'css': '#ontoStats'}, at('좌우로')]],
 '301': [['click', {'css': '#ontoSearch'}, at('검색 칸을')], ['type', '유압 파워팩', at('쳐 보세요')]],
 '303': [['wait', MATCH, 10], ['point', MATCH, 0.2]],
 '304': [['point', LAB('설비 · 1'), 0.3]],
 '305': [['point', LAB('구성 요소 · 6'), at('구성 요소 머리글')]],
 '306': [['point', N('comp:cooler'), 0.05], ['point', N('comp:fan'), at('쿨러 팬')], ['point', N('comp:pump-a'), at('주 펌프')]],
 '307': [['click', MATCH, at('눌러 보세요')], ['wait', H3, 10]],
 '308': [['point', MATCH, 0.2]],
 '309': [['scroll', DETAIL, at('내려 볼게요')]],
 '310': [['point', KIND, 0.3]],
 '311': [['point', H3, 0.2]],
 '313': [['point', TH0, 0.05], ['point', K('code'), at('둘째 줄이')]],
 '314': [['point', K('forecastModel'), at('나머지 줄은')]],
 '315': [['point', H('나가는'), at('나가는 관계는')]],
 '316': [['point', H('들어오는'), 0.1]],
 '318': [['point', {'css': '#ontoNode ul.rels li span', 'nth': 0}, at('화살표가')], ['point', LX('작동유 탱크'), at('파란 글씨가')]],
 '319': [['point', LX('작동유 탱크'), at('작동유 탱크부터')]],
 '320': [['point', LX('오일 쿨러'), 0.1]],
 '322': [['point', H('들어오는'), 0.05]],
 '401': [['click', L('comp:cooler'), at('눌러 주세요')], kind('구성 요소')],
 '402': [['point', KIND, 0.3]],
 '403': [['point', K('aliases'), 0.3]],
 '405': [['point', L('part:cooler-core'), at('쿨러 코어')]],
 '406': [['point', L('sen:ts1'), at('유온 센서')]],
 '407': [['point', L('sen:ce'), at('냉각 효율')]],
 '409': [['point', L('part:cooler-core'), 0.2]],
 '410': [['point', L('asset:hyd-01'), 0.3]],
 '411': [['point', L('fm:cooler-cooling-loss'), at('쿨러 냉각 성능 상실')]],
 '501': [['click', L('sen:ts1'), at('눌러 주세요')], kind('센서')],
 '502': [['point', KIND, 0.2]],
 '503': [['point', K('virtual'), 0.2]],
 '504': [['point', K('tag'), 0.2]],
 '506': [['point', L('sv:ts1'), at('읽는 상태 변수')]],
 '507': [['point', L('in:ts1'), at('데이터 출처')]],
 '508': [['click', L('in:ts1'), at('눌러 볼게요')], kind('입력 데이터')],
 '509': [['point', KIND, 0.2]],
 '510': [['point', TH0, at('속성 두 줄')], ['point', L('sv:ts1'), at('나가는 쪽에도')], ['click', L('sv:ts1'), at('눌러 보면')], kind('상태 변수')],
 '511': [['point', KIND, 0.3]],
 '513': [['point', K('normal'), at('정상값')]],
 '514': [['point', K('limit'), 0.2]],
 '516': [['point', K('aliases'), 0.2]],
 '518': [['point', H3, at('여기까지')]],
 '519': [['point', K('kind'), 0.2]],
 '520': [['point', L('sen:ts1'), at('유온 센서')]],
 '601': [['click', L('sen:ts1'), at('눌러')], kind('센서')],
 '602': [['point', L('sym:ts1-rise'), at('유온 상승')]],
 '603': [['click', L('sym:ts1-rise'), at('눌러 보세요')], kind('증상')],
 '604': [['point', KIND, at('클래스가')]],
 '605': [['point', K('aliases'), 0.2]],
 '606': [['point', LX('쿨러 성능 저하'), at('쿨러 성능 저하')]],
 '608': [['point', L('fm:cooler-cooling-loss'), at('쿨러 냉각')]],
 '609': [['click', L('fm:cooler-cooling-loss'), at('넘어가 볼게요')], kind('고장 유형')],
 '610': [['point', KIND, 0.2]],
 '611': [['point', LX('쿨러 핀 세척'), 0.3]],
 '612': [['point', LX('팬 최대 운전'), 0.1]],
 '614': [['point', L('comp:cooler'), 0.3]],
 '616': [['point', H('들어오는'), 0.2]],
 '617': [['point', L('sym:ts1-rise'), 0.1], ['point', LX('팬 구동 불량'), at('세 원인')]],
 '618': [['point', LX('팬 구동 불량'), at('팬 구동 불량')], ['point', LX('주변 온도 상승'), at('주변 온도')], ['point', L('cause:cooler-fin-fouling'), at('핀이 오염')],
         ['click', L('cause:cooler-fin-fouling'), at('가 볼게요')], kind('원인')],
 '619': [['point', KIND, 0.2]],
 '620': [['point', L('fm:cooler-cooling-loss'), at('일으키는 고장')], ['point', L('part:cooler-core'), at('관련 부품')]],
 '621': [['point', K('prior'), at('속성의 숫자')], ['click', L('part:cooler-core'), at('눌러 보세요')], kind('부품')],
 '622': [['point', KIND, 0.2]],
 '623': [['point', K('partNo'), at('품번 줄')]],
 '624': [['point', H('나가는'), at('공급사들')]],
 '625': [['point', L('comp:cooler'), 0.15], ['point', L('cause:cooler-fin-fouling'), at('방금 건너온')]],
 '626': [['point', {'css': '#ontoNode ul.rels li', 'contains': '발주', 'nth': 0}, 0.1]],
 '627': [['point', L('comp:cooler'), at('다시 쿨러로')]],
 '701': [['click', {'css': '#ontoSearch'}, at('지울게요')], ['clear', None], ['key', 'Backspace']],
 '702': [['select', {'css': '#ontoAsset'}, 'HYD-02', at('골라 주세요')], ['wait', {'css': '#ontoMap .o-node[data-id="asset:hyd-02"]'}, 20]],
 '703': [['point', {'css': '#ontoAsset'}, 0.2]],
 '704': [['point', N('asset:hyd-02'), 0.3]],
 '705': [['click', {'css': '#ontoSearch'}, at('검색 칸에 쳐')], ['type', 'comp:cooler', at('쳐 보세요')]],
 '706': [['wait', MATCH, 10], ['point', MATCH, 0.2]],
 '707': [['point', {'css': '#ontoSearch'}, 0.3]],
 '709': [['click', MATCH, at('눌러서')], ['wait', H3, 10], ['scroll', DETAIL, at('밑을 볼게요')]],
 '710': [['point', H('나가는'), 0.2]],
 '711': [['point', L('asset:hyd-02'), 0.3]],
 '713': [['select', {'css': '#ontoAsset'}, 'HYD-01', at('바꿔 볼게요')], ['wait', {'css': '#ontoMap .o-node[data-id="asset:hyd-01"]'}, 20]],
 '714': [['wait', MATCH, 10], ['point', N('asset:hyd-01'), 0.3]],
 '715': [['point', MATCH, 0.3]],
 '716': [['point', MATCH, at('노드 하나로')], ['point', N('asset:hyd-01'), at('설비마다 그 노드를')]],
 '801': [['click', MATCH, at('눌러 두고')], ['wait', H3, 10], ['scroll', DETAIL, at('정리해')]],
 '802': [['point', KIND, 0.3]],
 '803': [['point', K('aliases'), at('이름과 다른 이름')], ['point', L('asset:hyd-01'), at('이어진 설비')], ['point', {'css': '#ontoSearch'}, at('검색 칸에')]],
 '804': [['point', TH0, 0.2]],
 '805': [['point', H('나가는'), 0.3]],
}
FOLLOW = {'215': 6.0, '303': 5.0, '308': 4.0, '402': 4.0, '502': 4.0, '602': 4.0, '604': 4.0, '622': 4.0, '703': 4.0, '706': 6.0, '714': 4.0}
used = set()
for i, q in enumerate(cues):
    key = q['id'][4:]; q['ops'] = OPS.get(key, []); used.add(key)
    if i == 0: q['gap'] = 0.6
    elif q['segment'] != cues[i - 1]['segment']: q['gap'] = 2.3
    else:
        a = cues[i - 1]['_after']; q['gap'] = 2.0 if a == '▸‖' else 1.3 if '‖' in a else 0.6
    if key in FOLLOW: q['gap'] = max(q['gap'], FOLLOW[key])
missing = set(OPS) - used
assert not missing, f'대본에 없는 큐 번호의 조작: {sorted(missing)}'
for q in cues: q.pop('_after')
doc = {'note': '통합반 2회차 실습 05 「설비 지식의 구조와 연결 관계 탐색하기」 다시 찍을 판. 확정 대본(사용자 「go」 2026-11-12, workspace dea33058)을 큐만들기.py로 잘랐다(작업 폴더 근거/2026-11-12_통합2-05-포털-다시찍기). 구간 = 대본의 단계(1~8). 모듈 촬영도구/segs/map.mjs, 쉼은 영상 V-14 2회차 값과 따라하기 쉼.',
       'voice_id': '1PdAOcPlPTz12RwMyFVp', 'model_id': 'eleven_v4', 'cues': cues}
open(dst, 'w', encoding='utf-8', newline='').write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
print(len(cues), '큐 ·', sum(len(q['ops']) for q in cues), '조작 →', dst)
