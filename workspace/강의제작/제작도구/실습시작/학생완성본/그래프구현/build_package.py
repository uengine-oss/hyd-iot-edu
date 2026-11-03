"""두 과정 2회차 그래프 구현 완성본만 생성한다.

`결과/검증_기록.md`는 시작본의 「제공 빈 틀」과 같은 칸(머리 · 표 머리가 같아야 한다 — 다르면 멈춘다)으로 채운다. 기대 답은 `입력/자료/`(통합반은 수정본 포함)의
원자료 줄에서, 실제 결과는 이 완성본을 실제 랩 DB에서 실행한 `완성결과/<과정>.json`에서 따로 가져와 둘이 같은지 확인한다. 통합반의 「포털 기준 지도와 비교」는
포털이 적재하는 시드(build_labs.portal_map — 가이드 12단계 표와 같은 곳)와 실행 결과의 식별자 · 관계를 견준다.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from graph_model import load_model
from run_graph import batches

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import data_session2 as D   # noqa: E402  PR-07 7.4 값 한 곳
import build_labs as B      # noqa: E402  질문 · 쓰는 사람 · 포털 기준 지도 · 빈 단위 근거
COURSE_ROOT = HERE.parents[3] / '산출물'
LAB = '02일차_실습4_그래프구현과검증'


def numbered(path, keep=lambda r: True):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [(i, r) for i, r in enumerate(csv.DictReader(f), 2) if keep(r)]


def ref(name, nums):
    """파일과 줄 번호. 이어지는 줄(셋 이상)은 「a ~ b」로 줄인다."""
    nums, parts = sorted(set(nums)), []
    for n in nums:
        if parts and parts[-1][1] == n - 1:
            parts[-1][1] = n
        else:
            parts.append([n, n])
    return f'`{name}` ' + ' · '.join(f'{a} ~ {b}' if b - a >= 2 else ' · '.join(str(x) for x in range(a, b + 1)) for a, b in parts) + '행'


def table(head, rows_):
    return '| ' + ' | '.join(head) + ' |\n|' + '---|' * len(head) + '\n' + ''.join('| ' + ' | '.join(str(x) for x in r) + ' |\n' for r in rows_)


def same(expected, actual, what):
    if expected != actual:
        raise ValueError(f'완성본 {what}: 원자료에서 찾은 기대 답 {expected!r} ≠ 실제 결과 {actual!r}')
    return '같음'


def headings(text):
    """칸의 뼈대: 머리(#), 표 머리(바로 다음 줄이 |---), 「- 이름:」 꼴 항목의 이름."""
    lines = text.splitlines()
    out = [x for i, x in enumerate(lines) if x.startswith('#') or (i + 1 < len(lines) and lines[i + 1].startswith('|---'))]
    return out + sorted({x.split(':', 1)[0] for x in lines if x.startswith('- ') and ':' in x and x.split(':', 1)[0].count(' ') <= 6 and x.rstrip().endswith(':')})


def integrated_record(lab, run):
    data, change = lab/'입력/자료', next((lab/'입력/자료_변경분').glob('*수정본'))
    rel = lambda name: f'입력/자료/{name}'
    sensors = run['sensors']
    hyd01 = [r for r in sensors if r['asset'] == 'HYD-01']
    rows01 = numbered(data/'센서_목록.csv', lambda r: r['설비코드'] == 'HYD-01')
    exp_tags = sorted({r['태그'] for _, r in rows01})
    no_limit = [(i, r) for i, r in rows01 if not r['한계'] and r['태그'] == 'TS2']
    parts01 = numbered(data/'구성요소_목록.csv', lambda r: r['설비코드'] == 'HYD-01')
    got_parts = [r for r in run['asset_parts'] if r['asset'] == 'HYD-01']
    variants = run['revised_part_assets']
    seal = numbered(data/'구성요소_목록.csv', lambda r: '철거' not in r['비고'] and 'PMP-SEAL' in r['교체부품'] and 'HT' not in r['교체부품'] and '22' not in r['교체부품'])
    seal_fix = numbered(change/'구성요소_변경.csv')
    old_code = numbered(data/'품번_교차표.csv', lambda r: r['다른표기'] in ('PS-4510', 'PMP-SEAL'))
    model = {r['설비코드']: r['모델'] for _, r in numbered(data/'설비_대장.csv')}
    applies = next(r['적용모델'] for _, r in numbered(data/'예비품_목록.csv', lambda r: r['품번'] == 'P-RTN-FLT'))
    rtn = numbered(data/'구성요소_목록.csv', lambda r: r['구성요소'] == '리턴 필터' and B.model_match(model[r['설비코드']], applies))
    asset_rows = numbered(change/'설비_대장_변경.csv')
    hyd07 = numbered(data/'설비_대장.csv', lambda r: r['설비코드'] == 'HYD-07')
    pump22 = numbered(data/'구성요소_목록.csv', lambda r: r['교체부품'] == 'P-PMP-SEAL-22')
    sensor_fix = numbered(change/'센서_변경.csv')
    checks = {c['line']: c for c in run['sensor_change_check']}
    dup = numbered(data/'센서_목록.csv', lambda r: r['설비코드'] == 'HYD-01' and r['태그'] == 'TS1')
    basis = B.blank_unit_basis(data)
    vs1 = basis['HYD-03:VS1']
    names = dict((x['id'], x['name']) for x in run['revised'][2])
    statuses = dict((x['id'], x['status']) for x in run['revised'][2])
    running = [r['asset'] for r in variants['P-RTN-FLT']]
    exp_running = sorted({r['설비코드'] for _, r in rtn} - {r['설비코드'] for _, r in asset_rows if not r['상태'] == '가동'})
    decided = [['시점과 상태',
                '불용 · 예비 설비도 그래프에 남기고 상태 속성(status)만 수정본대로 바꾼다. 부품의 사용 설비 조회는 지금 가동하는 설비만 답으로 돌려주고, 가동이 아닌 설비는 그 설비 · 상태를 따로 보인다',
                f'{ref(rel("설비_대장.csv"), [i for i, _ in hyd07])}(「{hyd07[0][1]["상태"]}」 · {hyd07[0][1]["비고"]}), '
                f'{ref("입력/자료_변경분/" + change.name + "/설비_대장_변경.csv", [i for i, r in asset_rows if r["설비코드"] == "HYD-07"])}(「불용(매각 예정)」 · 매각 전까지 대장에 남김), START.md 「해결할 질문」(지금 가동하는 설비의 예비품)',
                f'P-RTN-FLT → {" · ".join(running)}(HYD-07은 「{", ".join(variants["P-RTN-FLT"][0]["not_running"])}」로 따로). HYD-07만 쓰는 P-PMP-SEAL-22는 「지금 가동하는 설비에서는 쓰지 않음」 한 줄이라 원자료에 없는 품번과 갈린다. 상태와 함께 다 보이게 했다면 P-RTN-FLT가 다섯 대']]
    answers = [
        ['질문 1 · HYD-01 구성 요소별 센서', f'{ref(rel("센서_목록.csv"), [i for i, _ in rows01])} — 센서 {len(exp_tags)}개({ref(rel("센서_목록.csv"), [i for i, _ in dup])}은 같은 TS1)',
         f'{len(hyd01)}줄(구성 요소 {len({r["attached_to"] for r in hyd01 if r["attached_to"] != "(설비 전체)"})}곳 · 설비 전체 1개)', same(exp_tags, sorted(r['tag'] for r in hyd01), 'HYD-01 센서')],
        ['질문 1 · 한계가 없는 센서(HYD-01 TS2)', f'{ref(rel("센서_목록.csv"), [i for i, _ in no_limit])} 한계 칸 빔 → 한계 없음(0이 아님)',
         'limit null', same(None, next(r['limit'] for r in hyd01 if r['tag'] == 'TS2'), 'TS2 한계')],
        ['질문 2 · HYD-01 구성 요소별 교체 부품', f'{ref(rel("구성요소_목록.csv"), [i for i, _ in parts01])} — 구성 요소 {len(parts01)}개, 교체부품 칸이 빈 것 {sum(1 for _, r in parts01 if not r["교체부품"])}개',
         f'{len(got_parts)}줄, 부품 없음 {sum(1 for r in got_parts if r["part"] is None)}줄(null)',
         same([len(parts01), sum(1 for _, r in parts01 if not r['교체부품'])], [len(got_parts), sum(1 for r in got_parts if r['part'] is None)], 'HYD-01 교체 부품')],
        ['질문 2 · 공용 부품 P-PMP-SEAL(PS-4510 · PMP-SEAL로도)', f'{ref(rel("구성요소_목록.csv"), [i for i, _ in seal])}, 수정본 {ref("구성요소_변경.csv", [i for i, _ in seal_fix])}(HYD-03 교체부품 확인), {ref(rel("품번_교차표.csv"), [i for i, _ in old_code])}(다른 표기) → HYD-01 · HYD-02 · HYD-03',
         ' · '.join(r['asset'] for r in variants['P-PMP-SEAL']) + ' — 세 표기 모두 같은 줄', same(['HYD-01', 'HYD-02', 'HYD-03'], [r['asset'] for r in variants['P-PMP-SEAL']], 'P-PMP-SEAL')],
        ['질문 2 · 가동이 아닌 설비도 쓰는 P-RTN-FLT', f'{ref(rel("구성요소_목록.csv"), [i for i, _ in rtn])}(리턴 필터) — 그 가운데 수정본에서 가동이 아닌 HYD-07을 빼면 ' + ' · '.join(exp_running),
         ' · '.join(running) + f', 따로: {", ".join(variants["P-RTN-FLT"][0]["not_running"])}', same(exp_running, running, 'P-RTN-FLT')],
        ['질문 2 · HYD-07만 쓰는 P-PMP-SEAL-22', f'{ref(rel("구성요소_목록.csv"), [i for i, _ in pump22])} → HYD-07(수정본에서 불용)',
         f'「{variants["P-PMP-SEAL-22"][0]["note"]}」, 따로: {", ".join(variants["P-PMP-SEAL-22"][0]["not_running"])}', same(['HYD-07 불용(매각 예정)'], variants['P-PMP-SEAL-22'][0]['not_running'], 'P-PMP-SEAL-22')],
        ['질문 2 · 원자료에 없는 품번(미등록-품번)', '어느 자료에도 없음', f'「{variants["미등록-품번"][0]["note"]}」 한 줄', same('원자료에 없는 품번', variants['미등록-품번'][0]['note'], '없는 품번')],
        ['질문 3 · 이름이 바뀐 설비의 ID', f'{ref("설비_대장_변경.csv", [i for i, r in asset_rows if r["설비코드"] == "HYD-02"])} → HYD-02 이름만 「HYD-02 2라인 2호 파워팩」',
         f'ID HYD-02 · 이름 「{names["HYD-02"]}」', same('HYD-02 2라인 2호 파워팩', names['HYD-02'], 'HYD-02 이름')],
        ['질문 3 · 「삭제」 줄 HYD-01 TS1', f'{ref("센서_변경.csv", [i for i, r in sensor_fix if r["변경"] == "삭제"])} = {ref(rel("센서_목록.csv"), [i for i, r in dup if r["비고"]])}(점검표에서 다시 옮겨 적은 같은 센서) → 센서는 남는다',
         f'HYD-01:TS1 남음(정상값 {checks[4]["observed"]["normal"]:g})', same('HYD-01:TS1', checks[4]['observed']['id'], 'HYD-01 TS1')],
        ['질문 3 · 수정본 HYD-03 VS1 「단위 보완」', f'{ref("센서_변경.csv", [2])} mm/s — {ref(rel("센서_목록.csv"), [vs1["line"]])}의 빈 단위를 근거 줄({ref(rel("센서_목록.csv"), vs1["basis"])})로 둔 {vs1["unit"]}와 같다',
         f'unit {checks[2]["observed"]["unit"]}(바뀐 값 없음)', same(vs1['unit'], checks[2]['observed']['unit'], 'HYD-03 VS1 단위')],
        ['질문 3 · 수정본 HYD-06 I_MOTOR 정상값', f'{ref("센서_변경.csv", [3])} 18.5(전에는 미확인)', f'normal {checks[3]["observed"]["normal"]:g}', same(18.5, checks[3]['observed']['normal'], 'I_MOTOR')],
        ['질문 3 · 수정본 HYD-07 상태', f'{ref("설비_대장_변경.csv", [i for i, r in asset_rows if r["설비코드"] == "HYD-07"])} → 불용(매각 예정), 대상은 남김', f'status 「{statuses["HYD-07"]}」',
         same('불용(매각 예정)', statuses['HYD-07'], 'HYD-07 상태')]]
    nodes = run['baseline'][0][0]['nodes'], run['baseline'][1][0]['relationships']
    revised = run['revised'][0][0]['nodes'], run['revised'][1][0]['relationships']
    counts = [['첫 적재', nodes[0], nodes[1], '`입력/graph.json`의 노드 · 관계 수와 같음'],
              ['같은 적재 다시', nodes[0], nodes[1], '늘지 않음(같은 대상을 id로 MERGE)'],
              ['수정본 반영', revised[0], revised[1], f'개수 변화 없음 — 수정본 {sum(len(numbered(f)) for f in change.glob("*.csv"))}줄 가운데 「삭제」 줄은 같은 센서의 중복 행이고, 나머지는 이름 · 상태 · 값 · 교체 부품 근거만 바꿈'],
              ['같은 수정본 다시', revised[0], revised[1], '늘지 않음']]
    # 포털 기준 지도와 비교 — 시드(포털) 쪽과 이 완성본 실행 결과(랩 DB) 쪽의 식별자 · 관계
    pnodes, prels, ko = B.portal_map()
    cooler = sorted(r['sensor'] for r in hyd01 if r['attached_to'] == 'HYD-01:cooler')
    ts1 = next(r for r in hyd01 if r['tag'] == 'TS1')
    p_assets = sorted(a for a, t, b in prels if t == 'HAS_COMPONENT' and b == B.PORTAL_COMPONENT)
    p_sensors = sorted(b for a, t, b in prels if a == B.PORTAL_COMPONENT and t == 'MONITORED_BY')
    p_sv = next(b for a, t, b in prels if a == 'sen:ts1' and t == 'OBSERVES')
    assert ('asset:hyd-01', 'HAS_COMPONENT', 'comp:cooler') in prels and ('comp:cooler', 'MONITORED_BY', 'sen:ts1') in prels
    portal = [
        ['설비 HYD-01', f'`{B.PORTAL_ASSET}`(code {pnodes[B.PORTAL_ASSET]["code"]})', '`HYD-01`', '다름(식별자 꼴)',
         '포털은 종류 접두어를 붙인 소문자 id에 설비코드를 code 속성으로, 이 모델은 설비코드 자체가 id'],
        ['설비 → 오일 쿨러', f'`asset:hyd-01` —{ko["HAS_COMPONENT"]}(HAS_COMPONENT)→ `comp:cooler`. 같은 `comp:cooler`에 ' + ' · '.join(f'`{a}`' for a in p_assets) + '가 함께 이어짐',
         '`HYD-01` —HAS_COMPONENT→ `HYD-01:cooler`', '방향 같음 · 식별자 다름',
         '포털의 구성 요소는 형식 노드 하나를 같은 모델의 설비 셋이 함께 가리키고, 이 모델은 설비마다 따로(설비코드:구성 요소) — 설비마다 실물 · 교체 부품이 다를 수 있어 따로 둠'],
        ['오일 쿨러 → 유온 센서', f'`comp:cooler` —{ko["MONITORED_BY"]}(MONITORED_BY)→ `sen:ts1`', f'`HYD-01:cooler` —MONITORED_BY→ `{ts1["sensor"]}`', '방향 같음 · 식별자 다름',
         '포털 센서도 설비 셋이 함께 쓰는 노드, 이 모델은 설비마다 센서(설비코드:태그) — 같은 태그가 여러 설비에 있어 설비코드를 붙임'],
        ['오일 쿨러의 센서 수', ' · '.join(f'`{s}`' for s in p_sensors), ' · '.join(f'`{s}`' for s in cooler), '다름',
         f'포털 기준 지도는 쿨러에 센서 {len(p_sensors)}개만, 이 모델은 원자료 센서 목록의 {len(cooler)}개를 모두'],
        ['유온 센서 → 재는 것', f'`sen:ts1` —{ko["OBSERVES"]}(OBSERVES)→ `{p_sv}`(상태 변수, 정상 {pnodes[p_sv]["normal"]:g} · 한계 {pnodes[p_sv]["limit"]:g})',
         f'`{ts1["sensor"]}` —OBSERVES→ `{ts1["quantity_id"]}`(물리량), 정상 {ts1["normal"]:g} · 한계 {ts1["limit"]:g}는 센서에', '방향 같음 · 끝 종류와 한계 자리 다름',
         '포털은 한계를 상태 변수에 두고, 이 모델은 센서에 둠 — 같은 물리량이라도 설비마다 한계가 다를 수 있음(HYD-05 · 06 오일 온도 한계 70)']]
    unknown = ['Neo4j Browser 화면(연결 창 · Table)은 이 기록에 옮기지 않았다 — 같은 조회를 `run_graph.py`로 실행한 결과 파일로 확인',
               '포털 쪽은 포털 실습에서 펼쳐 본 지도의 식별자 · 관계(가이드 12단계 표)로 견줬고 포털 DB에는 접속하지 않았다']
    return decided, answers, counts, portal, unknown


def practical_record(lab, run):
    data = lab/'입력/자료'
    rel = lambda name: f'입력/자료/{name}'
    usage, terms = run['part_usage'], run['supply_terms']
    seal = numbered(data/'구성요소_목록.csv', lambda r: '철거' not in r['비고'] and 'PMP-SEAL' in r['교체부품'] and 'HT' not in r['교체부품'] and '22' not in r['교체부품'])
    blank = numbered(data/'구성요소_목록.csv', lambda r: r['설비코드'] == 'HYD-03' and r['구성요소'] == '주 펌프 A')
    shared = numbered(data/'예비품_목록.csv', lambda r: r['품번'] == 'P-PMP-SEAL')
    pr = data/D.PR07_FILE
    line74 = next(i for i, x in enumerate(pr.read_text(encoding='utf-8').splitlines(), 1) if '전수 검사 비용' in x)
    line_price = next(i for i, x in enumerate(pr.read_text(encoding='utf-8').splitlines(), 1) if '단가만 보지 않는다' in x)
    flagged = [r for r in terms['P-PMP-SEAL'] if r['inspection']]
    decided = [['쓰는 사람에 따라 갈리는 답', '구매 기준서 7.4에 걸리는 쌍의 입고 검사 · 비교 가산 비용 · 근거 줄을 공급사 줄마다 따로 된 칸으로 함께 돌려준다(단가에 더하지 않음, 걸리지 않는 줄은 빈 칸)',
                f'{ref(rel(D.PR07_FILE), [line_price])}(단가만 보지 않는다) · {line74}행(7.4)',
                ' · '.join(f'{r["name"]} 줄에 「{r["inspection"]}」 · +{r["compare_extra_manwon"]:g}만 원 · {r["rule_source"]}' for r in flagged) + '. 돌려주지 않으면 그 공급사는 단가 · 불량률만 보인다'],
               ['원자료에 없는 품번 · 공급 조건이 없는 부품을 보이는 법(9단계)', '0줄로 끝내지 않고 「원자료에 없는 품번」 · 「기준일에 쓸 공급 조건 없음」 한 줄로 돌려준다',
                '작업 규칙 4번(미확인 · 값 없음 · 0 구별), 가이드 9단계 「왜 하는가」(MATCH가 못 찾으면 0줄)',
                f'미등록-품번 → 「{terms["미등록-품번"][0]["note"]}」, P-CLR-PLT → 「{terms["P-CLR-PLT"][0]["note"]}」 — 둘 다 0줄이면 구별되지 않는다']]
    quotes = dict(numbered(data/D.QUOTE_FILE))
    avl = dict(numbered(data/D.AVL_FILE))
    answers = [['질문 1 · 펌프 축 씰 키트를 쓰는 설비',
                f'{ref(rel("구성요소_목록.csv"), [i for i, _ in seal])}, {ref(rel("구성요소_목록.csv"), [i for i, _ in blank])}(교체부품 칸 빔 — {ref(rel("예비품_목록.csv"), [i for i, _ in shared])} 「{shared[0][1]["비고"]}」) → HYD-01 · HYD-02 · HYD-03 주 펌프 (A)',
                ' · '.join(f'{r["asset"]} {r["component_name"]}' for r in usage['P-PMP-SEAL']), same(['HYD-01', 'HYD-02', 'HYD-03'], [r['asset'] for r in usage['P-PMP-SEAL']], '사용 설비')]]
    for r in terms['P-PMP-SEAL']:
        q, a = quotes[int(r['quote_source'].split()[1][:-1])], avl[int(r['approval_source'].split()[1][:-1])]
        answers.append([f'질문 1 · {r["name"]} 공급 조건과 출처',
                        f'{ref(rel(D.QUOTE_FILE), [int(r["quote_source"].split()[1][:-1])])}: {q["단가(만원)"]}만 원 · 불량률 {q["불량률"]} · 납기 {q["납기(일)"]}일(견적일 {q["견적일"]}), '
                        f'{ref(rel(D.AVL_FILE), [int(r["approval_source"].split()[1][:-1])])}: {a["승인상태"]}, 기준일 {D.REF_DATE}',
                        f'approved {str(r["approved"]).lower()} · {r["approval_status"]} · {r["price_manwon"]:g}만 원 · {r["defect_rate"]:g} · {r["quoted_days"]}일 · 출처 {r["quote_source"]} · {r["approval_source"]} · 기준일 {r["as_of"]}',
                        same([float(q['단가(만원)']), float(q['불량률']), int(q['납기(일)']), a['승인상태'], D.REF_DATE],
                             [r['price_manwon'], r['defect_rate'], r['quoted_days'], r['approval_status'], r['as_of']], r['name'])])
    old = numbered(data/'품번_교차표.csv', lambda r: r['다른표기'] in ('PS-4510', 'PMP-SEAL'))
    answers.append(['질문 2 · 예전 품번 PS-4510 · 다른 표기 PMP-SEAL', f'{ref(rel("품번_교차표.csv"), [i for i, _ in old])} → P-PMP-SEAL',
                    '정식 품번과 같은 줄 — 그래프 부품의 다른 표기(other_codes, 품번 교차표에서 온 값)로 찾음', same(usage['P-PMP-SEAL'], usage['PS-4510'], 'PS-4510')])
    ht = numbered(data/'예비품_목록.csv', lambda r: r['품번'] == 'P-PMP-SEAL-HT')
    answers.append(['질문 2 · 이름이 비슷한 다른 품번 P-PMP-SEAL-HT', f'{ref(rel("예비품_목록.csv"), [i for i, _ in ht])}(「{ht[0][1]["비고"]}」) → HYD-04, 다른 공급 조건',
                    ' · '.join(r['asset'] for r in usage['P-PMP-SEAL-HT']) + ' · 공급사 ' + ' · '.join(f'{r["name"]} {r["price_manwon"]:g}만 원' for r in terms['P-PMP-SEAL-HT']),
                    same(['HYD-04'], [r['asset'] for r in usage['P-PMP-SEAL-HT']], 'P-PMP-SEAL-HT')])
    answers.append(['질문 2 · 원자료에 없는 품번(미등록-품번)', '어느 자료에도 없음', f'「{usage["미등록-품번"][0]["note"]}」 한 줄', same('원자료에 없는 품번', usage['미등록-품번'][0]['note'], '없는 품번')])
    c = next(r for r in terms['P-PMP-SEAL'] if not r['approved'])
    answers.append(['질문 2 · 비승인 공급사', f'{ref(rel(D.AVL_FILE), [int(c["approval_source"].split()[1][:-1])])}: {avl[int(c["approval_source"].split()[1][:-1])]["승인상태"]}',
                    f'{c["name"]} approved false · 「{c["approval_status"]}」 — 결과에서 빼지 않고 승인 상태와 함께', same('비승인', c['approval_status'], '비승인')])
    nodes = run['baseline'][0][0]['nodes'], run['baseline'][1][0]['relationships']
    answers.append(['질문 3 · 같은 적재 두 번', f'`입력/graph.json`의 노드 {nodes[0]} · 관계 {nodes[1]}', f'두 번째 적재 뒤에도 노드 {nodes[0]} · 관계 {nodes[1]}', same('기준 2회 동일', run['repeat_load'], '다시 적재')])
    counts = [['첫 적재', nodes[0], nodes[1], '`입력/graph.json`의 노드 · 관계 수와 같음'], ['같은 적재 다시', nodes[0], nodes[1], '늘지 않음(같은 대상을 id로 MERGE)']]
    unknown = ['Neo4j Browser 화면(연결 창 · Table)은 이 기록에 옮기지 않았다 — 같은 조회를 `run_graph.py`로 실행한 결과 파일로 확인',
               '견적의 납기는 견적서 값이다 — 입고 실측과 견주는 일은 이번 범위 밖']
    return decided, answers, counts, None, unknown


def fill_record(course, lab, run):
    """제공 빈 틀(`결과/검증_기록.md`)의 칸대로 채운다. 머리와 표 머리가 빈 틀과 다르면 멈춘다."""
    practical = course == '실전반'
    template = (lab/'결과/검증_기록.md').read_text(encoding='utf-8')
    L = B.graph_lab(course)
    decided, answers, counts, portal, unknown = practical_record(lab, run) if practical else integrated_record(lab, run)
    dates = '기준일' if practical else '기준일 · 수정본 날짜'
    date_value = D.REF_DATE if practical else f'{D.REF_DATE} · {D.CHANGE_DATE}'
    rules = ['원자료 · 제공된 모델(`입력/`)은 읽기만 하고, 만든 것은 `결과/`에 둔다', '이 폴더의 랩 DB에만 넣고 전체 삭제문을 쓰지 않는다', 'ID를 바꾸지 않는다', '조회는 그래프를 바꾸지 않는다',
             '미확인 · 값 없음 · 0을 구별한다']
    text = (f'# 실습 확인 기록\n\n## 목표와 질문\n\n{L["lead"]}\n\n' + ''.join(f'{i}. {q}\n' for i, q in enumerate(L['questions'], 1))
            + f'\n## 이 답을 쓰는 사람과 쓰는 곳\n\n{L["user"]}\n\n'
            + '## 사용한 입력과 랩 DB\n\n- 사용한 모델(제공된 모델 · 내 모델): 제공된 모델(`입력/schema.json` · `입력/graph.json`)\n'
            + '- 랩 DB 주소(인증값 제외): 이 폴더의 `lab_db.py`가 켠 127.0.0.1 주소(`랩_연결.json` — 다시 켜면 포트가 바뀔 수 있음)\n'
            + f'- {dates}: {date_value}\n\n'
            + '## 지킬 조건\n\n' + ''.join(f'- {x}\n' for x in rules) + '\n'
            + '## 정한 것\n\n' + table(['지점(종류)', '고른 것', '근거(파일 · 줄)', '이 선택으로 바뀌는 답'], decided) + '\n'
            + '## 기대 답과 실제 결과\n\n' + table(['질문 · 물은 대상', '원자료에서 먼저 찾은 기대 답(파일 · 줄)', '실제 결과', '고친 점 · 다시 확인'], answers) + '\n'
            + ('## 적재 · 다시 적재\n\n' if practical else '## 적재 · 다시 적재 · 수정본\n\n') + table(['단계', '노드 수', '관계 수', '확인한 것'], counts) + '\n'
            + ('' if practical else '## 포털 기준 지도와 비교\n\n' + table(['대상', '포털의 식별자 · 관계 방향', '내 그래프의 식별자 · 관계 방향', '같음 · 다름', '다른 까닭'], portal) + '\n')
            + f'## 저장 기록\n\n- {dates}: {date_value}\n- 저장 시점: {date_value.split(" · ")[-1]} 자료로 만든 판(' + ('같은 적재를' if practical else '같은 적재 · 같은 수정을') + ' 두 번 실행해 개수와 설비 이름 · 상태가 같음 — `결과/run_result.json`의 repeat_load)\n'
            + '- 확인하지 못한 점: ' + ' '.join(x + '.' for x in unknown) + '\n')
    want, got = headings(template), headings(text)
    labels = [x for x in want if x.startswith('- ')]
    missing = [x for x in labels if not any(line.startswith(x + ':') for line in text.splitlines())]
    if [x for x in want if not x.startswith('- ')] != [x for x in got if not x.startswith('- ')] or missing:
        raise ValueError(f'{course} 완성본 검증_기록.md의 칸이 제공 빈 틀과 다릅니다:\n빈 틀 {want}\n완성본 {got}')
    return text


def package(course):
    practical = course == '실전반'
    base = COURSE_ROOT/course/'실습/02회차'
    lab = base/'랩'/LAB
    target = base/'완성본'/(LAB+'_학생용완성본.zip')
    files = {}
    for p in lab.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts: continue
        name = p.relative_to(lab).as_posix()
        if p.name == '.env': files[name] = b''; continue
        if p.suffix in {'.pyc', '.zip'} or p.name == '랩_연결.json': raise ValueError('시작본에 생성 파일이 있습니다: '+name)
        files[name] = p.read_bytes()
    source_names = ['run_graph.py', 'graph_model.py']
    source_names += ['queries/part_usage.cypher', 'queries/supply_terms.cypher'] if practical else \
                    ['queries/part_assets.cypher', 'queries/asset_sensors.cypher', 'queries/asset_parts.cypher', 'queries/asset_counts.cypher']
    for name in source_names: files[name] = (HERE/name).read_bytes()
    inputs = lab/'입력'
    g = load_model(inputs); summary = {'input_nodes': len(g['nodes']), 'input_edges': len(g['rels'])}
    if not practical:   # 수정본 반영은 통합반 실습4만
        delta = batches(load_model(inputs, True), g)
        summary.update(patch_statements=len(delta), patch_targets=[x['parameters'].get('key') or [x['parameters'].get('a'), x['parameters'].get('b')] for x in delta])
    files['결과/input_check.json'] = (json.dumps(summary, ensure_ascii=False, indent=2)+'\n').encode()
    selections = (f'견적 단가는 최신 적용 견적에서, 승인 상태는 품목별 SCM 승인 목록에서 읽습니다. 구매 기준서 PR-07 7.4에 걸리는 승인 공급사(불량률 {D.PR74_RATE_PCT} % 초과)는 승인 상태를 바꾸지 않고, '
                  f'입고 전수 검사와 비교에 더할 비용 {D.PR74_EXTRA_MANWON}만 원을 근거 줄과 함께 조회 결과에 돌려줍니다. 비승인 공급사도 빼지 않고 승인 상태와 함께 돌려줍니다. 값마다 출처(견적 줄 · 승인 등록 줄 · 기준일)는 모델에 들어 있는 속성을 조회로 돌려받은 것이니, 그 줄을 `입력/자료/`에서 열어 함께 확인하세요.' if practical else
                  '설비별 센서는 구성 요소에 붙은 것과 설비 전체에 붙은 것을 함께 조회합니다. 단위·정상값·한계·상한/하한을 구별하고 없는 값은 null로 남깁니다. 설비별 교체 부품은 교체 부품이 없는 구성 요소도 null로 남깁니다. '
                  '부품의 사용 설비는 지금 가동하는 설비만 답으로 돌려주고, 가동이 아닌 설비는 not_running에 상태와 함께 따로 보입니다.')
    prep_tail = ' 결과가' if practical else ' 수정본에서 바뀌는 대상이'
    run_tail = ('합니다.' if practical else '하고, 수정본의 바뀐 속성과 연결만 두 번 적용해 ID 유지와 중복 여부를 검사합니다.')
    look = '품번별 사용처와 공급 조건(값마다 출처 포함)' if practical else '기준·수정 설비 목록, 품번별 사용처, 설비별 센서 · 교체 부품'
    asset_param = '' if practical else " 설비 질의는 `:param asset => 'HYD-01'`(전체 설비는 `''`)을 먼저 실행합니다."
    guide = f'''# {course} 그래프 구현 완성본 실행

압축을 새 폴더에 풀고 `run_graph.py`가 있는 폴더를 VS Code에서 여세요. 이 완성본은 AI 계정 없이 Python 표준 라이브러리와 Docker로 실행할 수 있습니다.

1. 터미널에서 `python run_graph.py --prepare`를 실행하세요. 입력 ID와 관계 끝점을 확인하고{prep_tail} `결과/input_check.json`에 기록됩니다.
2. Docker Desktop이 실행 중일 때 `python run_graph.py`를 실행하세요. 이 폴더의 `lab_db.py`가 전용 Neo4j를 준비합니다. 기준 모델을 두 번 넣어 대상·관계 수를 비교{run_tail}
3. `결과/run_result.json`의 {look}를 원자료와 비교하세요. 질문마다 원자료에서 찾은 기대 답과 이 결과를 나란히 적은 것은 `결과/검증_기록.md`에 있습니다. `python run_graph.py --part P-FAN-BRG`로 다른 부품도 조회할 수 있습니다. 동봉된 결과는 이 입력으로 실행해 얻은 값입니다. 결과 파일을 보관하려면 다른 품번 실행 전에 사본을 남기세요.
4. `python lab_db.py`로 같은 랩 DB의 Browser를 열어 `queries/`의 질의를 직접 실행할 수도 있습니다. 품번 질의는 `:param part => 'P-PMP-SEAL'`을 먼저 실행합니다.{asset_param}

{selections}

원자료와 제공 모델은 `입력/`에 남고, 결과는 `결과/`에 저장됩니다. 실습을 마친 뒤 같은 폴더를 다시 열어 결과 파일을 확인하세요.
'''
    files['결과/run_result.json'] = (HERE/'완성결과'/(course+'.json')).read_bytes()
    files['완성본_실행.md'] = guide.encode()
    files['결과/검증_기록.md'] = fill_record(course, lab, json.loads(files['결과/run_result.json'])).encode()
    files['결과/query.cypher'] = ('\n\n'.join('// '+n+'\n'+files[n].decode('utf-8-sig').strip()+';' for n in source_names if n.endswith('.cypher'))+'\n').encode()
    target.parent.mkdir(parents=True, exist_ok=True); tmp = target.with_suffix('.tmp')
    with ZipFile(tmp, 'w') as z:
        for name, body in sorted(files.items()):
            info = ZipInfo(LAB+'/'+name, (2026, 1, 1, 0, 0, 0)); info.compress_type = ZIP_DEFLATED; z.writestr(info, body)
    with ZipFile(tmp) as z:
        assert set(z.namelist()) == {LAB+'/'+n for n in files}
        assert all(z.read(LAB+'/'+n) == v for n, v in files.items())
    tmp.replace(target)
    return {'과정': course, '경로': target.relative_to(COURSE_ROOT.parent).as_posix(), '파일수': len(files), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), '입력': summary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('course', choices=['통합반', '실전반']); a = parser.parse_args(); print(json.dumps(package(a.course), ensure_ascii=False))
