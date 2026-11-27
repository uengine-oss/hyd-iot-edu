"""실전반 2회차 설계 랩(공장 규모)의 강사 참조 답과 독립 기대 값 — 답은 학생 폴더에 들어가지 않는다.

통합반 답(session2_answers.integrated_design)과 같은 표 · 같은 결정 지점 둘에, 공장 규모 자료에만 있는 사실(옛 코드 설비 줄 · 점검표에 다시 적힌 센서 줄 ·
설비에 바로 붙는 센서 · 단위 칸이 빈 센서)을 받는 줄과, 끝의 응용(구매팀 질문 — 공급사 · 견적 클래스와 셋째 결정 지점)을 더한다.
기대 값(literal)은 제공 코드를 거치지 않고 자료 생성기의 정의(data_session2)에서 바로 센다 — 모델을 자기 자신과 견주지 않으려는 것이다.
공장 규모는 data_session2의 기본 규모라 for_course 없이 돈다(통합반 규모에서 부르면 멈춘다).
"""
import csv
import io
import re

import build_labs as B
import data_session2 as D
import lab_frame as F
import session2_answers as A
from session2_factory import SUPPLY_POINT

BRANCHES = ('A', 'B', 'C', 'E')                 # 설비 쪽 결정 지점 둘의 갈래(build_labs.POLICY — 통합반과 같다)
SUPPLY_BRANCHES = ('늦은 줄', '이른 줄', '줄마다')    # 셋째 결정 지점: 같은 공급사 · 같은 부품의 견적 두 줄
PROVIDED_SUPPLY = '줄마다'                       # 설계 랩 완성본과 그래프 랩 제공 모델이 쓰는 셋째 결정의 갈래 — 받은 견적을 모두 담아, 그래프 랩의 구매팀 쿼리가 기준일로 걸러야 답이 맞다
DECISION_POINTS = [*A.DECISION_POINTS, SUPPLY_POINT]
ASKED_PART = 'P-FAN-BRG'                         # 구매팀 질문이 묻는 부품 — 셋째 결정이 답을 바꾸는 부품(이론 01편이 공급한다 N:M의 예로 든 팬 베어링)
PURCHASE_QUESTION = '이 부품을 어느 설비가 쓰고, 기준일에 어느 공급사에서 어떤 조건(승인 상태 · 단가 · 불량률 · 납기)으로 살 수 있는가?'


def memo_line(text):
    hits = [i for i, x in enumerate(D.memo(True).splitlines(), 1) if text in x]
    if len(hits) != 1:
        raise ValueError(f'현장 메모(공장 규모)에서 「{text}」 줄을 하나로 찾지 못함: {hits}')
    return hits[0]


def facts():
    """공장 규모 자료에서 줄 번호로 짚을 사실들."""
    assets, comps, sensors = B.numbered('설비_대장.csv'), B.numbered('구성요소_목록.csv'), B.numbered('센서_목록.csv')
    legacy = B.legacy_rows([a for _, a in assets])
    seen, repeats = {}, []
    for i, s in sensors:
        key = (s['설비코드'], s['태그'])
        if key in seen:
            repeats.append((seen[key], i))
        seen.setdefault(key, i)
    (gone, now, removed), = A.removed_rows()
    quotes = B.numbered(D.QUOTE_FILE)
    return dict(legacy=[i for i, a in assets if a['설비코드'] in legacy], repeats=repeats, gone=gone, now=now, removed=removed,
                wide=[i for i, s in sensors if s['붙은곳'] == '설비 전체'], blank_unit=[i for i, s in sensors if not s['단위']],
                motor=next(i for i, c in comps if c['구성요소'] == '구동 모터'),
                expired=[i for i, q in quotes if q['유효기한'] < D.REF_DATE],
                several={k: v for k, v in D.TRUTH['several_live'].items()})


# 재는것 이름을 적은 사람마다 다르게 부른 말 → 한 이름(현장 메모 「사람마다 다르게 부르는 이름」). 강사 참조 규칙이 쓰는 표다.
POINT_NAMES = {'오일 온도': '유온', '탱크 온도': '탱크 유온', '펌프 압력': '토출 압력', '메인 압력': '토출 압력', '토출 유량': '유량', '메인 유량': '유량',
               '진동': '팬 진동', '쿨러 효율': '냉각 효율'}


def quantity_rules_answer(scope='종류'):
    head = f'# {F.MARK} — 같은 물리량을 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.\n'
    common = f'''
SAME_NAME = {POINT_NAMES!r}


def point(row):
    """재는 자리까지 가리키는 이름 — 적은 사람마다 다르게 부른 재는것 이름을 하나로 맞춘다(현장 메모 {memo_line('재는 값의 이름도')}행).
    통신 없는 현장 지시계의 유온계는 탱크에 붙어 있어 탱크 유온이다(센서_목록.csv 붙은곳 칸)."""
    name = SAME_NAME.get(row['재는것'], row['재는것'])
    if '현장 지시' in row['센서명'] and name == '유온' and row['계통'] == '저장·여과':
        return '탱크 유온'
    return name
'''
    if scope == '자리':
        return head + common + '''

def same_quantity(a, b):
    """근거: 붙은 자리까지 같아야 같은 물리량 — 맞춘 이름이 같으면 같은 자리에서 같은 것을 잰다(태그 이름은 제조사마다 달라 태그로는 가르지 않는다)."""
    return point(a) == point(b)


def quantity_name(members):
    """근거: 묶음의 맞춘 이름 — 붙은 자리를 가리키는 이름(유온 · 쿨러 출구 유온 · 탱크 유온)."""
    return point(members[0])
'''
    return head + common + '''

def value_kind(row):
    """재는 값의 종류(무엇의 어떤 값). 계기 없이 계산한 값과 설정값은 저마다 다른 종류로 둔다."""
    name = point(row)
    if '설정값' in name or name in ('냉각 효율', '냉각 동력', '시스템 효율'):
        return name
    for word, kind in (('냉각수', '냉각수 유량'), ('차압', '차압'), ('제어반', '제어반 온도'), ('온도', '작동유 온도'), ('유온', '작동유 온도'),
                       ('압력', '작동유 압력'), ('유량', '작동유 유량'), ('진동', '진동'), ('레벨', '레벨')):
        if word in name:
            return kind
    return name


def same_quantity(a, b):
    """근거: 재는 값의 종류가 같으면 같은 물리량 — 어디서 쟀는지는 센서 이름과 센서가 붙은 구성 요소(붙은곳)로 따로 읽는다."""
    return value_kind(a) == value_kind(b)


def quantity_name(members):
    """근거: 묶음의 재는 값의 종류를 그대로 이름으로."""
    return value_kind(members[0])
'''


SUPPLY_CLASS_ROWS = lambda mode: [
    ['공급사', '부품을 파는 회사. 승인 공급사 목록에 적힌 이름마다 하나', '{공급사}', f'자료/{D.AVL_FILE}:1 공급사 칸 — 견적표의 괄호 풀이를 뗀 이름과 같음'],
    ['견적', '공급사 하나가 부품 하나에 내준 조건 한 건', '{공급사}:{품번}:{견적일}' if mode == '줄마다' else '{공급사}:{품번}',
     f'자료/{D.QUOTE_FILE}:1 — ' + ('같은 공급사 · 같은 부품의 견적을 받은 날마다 따로 둠' if mode == '줄마다' else '공급사 · 부품 한 쌍에 견적 하나')]]
SUPPLY_PROPERTY_ROWS = [
    ('공급사', 'name', '공급사', '글자', '예', '', f'자료/{D.AVL_FILE}:1 — 질문 5의 답이 공급사 이름으로 나옴'),
    ('견적', 'price_manwon', '단가(만원)', '수', '예', '', f'자료/{D.QUOTE_FILE}:1'), ('견적', 'defect_rate', '불량률', '수', '예', '', f'자료/{D.QUOTE_FILE}:1 — 0~1 비율'),
    ('견적', 'lead_days', '납기(일)', '수', '예', '', f'자료/{D.QUOTE_FILE}:1'), ('견적', 'quote_date', '견적일', '날짜', '예', '', f'자료/{D.QUOTE_FILE}:1'),
    ('견적', 'valid_until', '유효기한', '날짜', '예', '', f'자료/{D.QUOTE_FILE}:1 — 기준일에 유효한 견적만 답하려고'),
    ('견적', 'approval', '승인상태', '글자', '예', '', f'자료/{D.AVL_FILE}:1 — 승인 여부는 SCM 등록을 따름(자료/{D.PR07_FILE} 7.3)'),
    ('견적', 'approval_condition', '승인조건', '글자', '아니오', '', f'자료/{D.AVL_FILE}:1 조건 칸 — 조건이 붙은 등록만 값이 있음'),
    ('견적', 'quote_source', '견적출처', '글자', '예', '', '구매팀이 근거 줄을 되짚으려고'), ('견적', 'approval_source', '승인출처', '글자', '아니오', '', '등록이 없는 견적은 빈 값')]
SUPPLY_RELATION_ROWS = [
    ['OFFERS', '내놓는다', '공급사', '견적', '1:N', '종료마다', f'자료/{D.QUOTE_FILE}:1 — 공급사 하나가 견적을 여럿 내고, 견적은 낸 공급사가 꼭 하나'],
    ['QUOTES_PART', '값을 매긴다', '견적', '부품', 'N:1', '시작마다', f'자료/{D.QUOTE_FILE}:1 품번 칸 — 견적 하나는 부품 하나의 조건이고, 견적이 없는 부품도 있음']]


def design(branch='E', supply=None, lap=True, properties=None, relations=None, rows=None):
    """공장 규모 설계 랩 빈 틀의 정답 내용 {경로: 글}. branch = 설비 쪽 갈래(A · B · C · E), supply = None(응용 앞까지) 또는 SUPPLY_BRANCHES 가운데 하나.
    properties · relations · rows = 속성 표 · 관계 표 · 행 처리 표의 줄을 바꾸는 함수(강사 참조 시험이 다른 선택의 결과를 볼 때)."""
    D.require('실전반')
    _, _, unit, scope = B.policy(branch)
    split = unit == '나눔'
    f = facts()
    memo = lambda text: f'자료/현장_메모.md:{memo_line(text)}'
    files = {}
    files['결과/클래스.csv'] = A.csv_text(A.DESIGN_EXPLAIN['클래스.csv'], A.DESIGN_COLUMNS['클래스.csv'], [
        ['설비', A.MEANING['설비'], '{설비코드}', '자료/설비_대장.csv:1 설비코드 칸 — 설비마다 하나'],
        ['구성 요소', A.MEANING['구성 요소'] + ('가 놓이는 자리' if split else ''), '{설비코드}:{구성요소}', f'{memo("같은 모델(HPP-45A)")} — 같은 모델의 같은 품목이 설비마다 있으므로 설비코드를 붙임'],
        ['센서', A.MEANING['센서'], '{설비코드}:{태그}', f'{memo("태그 이름(TS1")} — 태그 이름은 한일유압 설비가 모두 같아 설비코드를 붙임'],
        ['물리량', A.MEANING['물리량'], '{물리량}', f'{memo("재는 값의 이름도")} — 재는 값의 이름이 사람마다 달라 묶어 정한 이름 하나를 씀'],
        ['부품', A.MEANING['부품'], '{품번}', '자료/예비품_목록.csv:1 품번 칸(사내 품번) — 다른 표기는 식별자가 아니라 부품의 다른 이름'],
        *([['실물', A.MEANING['실물'], '{일련번호}', f'{memo("구성 요소 목록의 일련번호")} — 일련번호는 그 자리에 달린 장치 한 대']] if split else []),
        *(SUPPLY_CLASS_ROWS(supply) if supply else [])])
    props = [list(r) for r in A.PROPERTY_ROWS + ([A.LAP_ROW] if lap else []) + (A.UNIT_PROPERTY_ROWS if split else [A.SEAT_SERIAL_ROW]) + (SUPPLY_PROPERTY_ROWS if supply else [])]
    for r in props:      # 공장 규모에는 단위 칸이 빈 센서 줄이 있다 — 단위를 필수로 두면 그 줄이 걸린다
        if r[:2] == ['센서', 'unit']:
            r[4], r[6] = '아니오', f'자료/센서_목록.csv:{f["blank_unit"][0]} — 단위 칸이 빈 줄이 있어 필수로 두지 않음'
    files['결과/속성.csv'] = A.csv_text(A.DESIGN_EXPLAIN['속성.csv'], A.DESIGN_COLUMNS['속성.csv'], properties(props) if properties else props)
    rels = [
        ['HAS_COMPONENT', '가진다', '설비', '구성 요소', '1:N', '종료마다', '자료/구성요소_목록.csv:1 — 설비 하나에 구성 요소 여러 줄, 구성 요소는 설비 하나에만 달리고 설비 없는 구성 요소는 없어야 함'],
        ['MONITORED_BY', '감시된다', '구성 요소', '센서', '1:N', '없음', f'자료/센서_목록.csv:{f["wide"][0]} — 한 구성 요소에 센서 여럿. 설비 전체에 붙은 센서는 구성 요소가 없어 「적어도 하나」를 두지 않음'],
        ['ASSET_MONITORED_BY', '통째로 감시된다', '설비', '센서', '1:N', '없음', f'자료/센서_목록.csv:{" · ".join(map(str, f["wide"]))} 붙은곳 「설비 전체」 — 구성 요소 하나가 아니라 설비에 붙는 값'],
        ['OBSERVES', '잰다', '센서', '물리량', 'N:1', '시작마다', '자료/센서_목록.csv:1 재는것 칸 — 센서 하나는 물리량 하나를 재고, 무엇을 재는지 없는 센서는 없어야 함'],
        ['USES_PART', '쓴다', '구성 요소', '부품', 'N:M', '없음', f'자료/구성요소_목록.csv:{f["motor"]} — 구성 요소 하나가 부품을 여럿 쓸 수 있고 한 부품을 여러 구성 요소가 씀. 교체부품 칸이 빈 구성 요소도 있음'],
        *([['INSTALLED_UNIT', '달고 있다', '구성 요소', '실물', '1:N', '종료마다', f'자료/구성요소_목록.csv:{f["gone"]} · {f["now"]} — 한 자리에 지금 실물과 지난 실물이 이어지고, 실물은 달린 자리가 꼭 하나']] if split else []),
        *(SUPPLY_RELATION_ROWS if supply else [])]
    files['결과/관계.csv'] = A.csv_text(A.DESIGN_EXPLAIN['관계.csv'], A.DESIGN_COLUMNS['관계.csv'], relations(rels) if relations else rels)
    handled = [
        ['구성요소_목록.csv', f['gone'], f'지난 실물:{f["now"]}' if split else '빼기',
         f'자료/구성요소_목록.csv:{f["gone"]} 비고 「{f["removed"]["비고"]}」 · {f["now"]}행 「교체 설치」' + (' — 그 자리의 지난 실물' if split else ' — 기준일에 달려 있지 않은 실물')],
        *[['설비_대장.csv', i, '빼기', f'자료/설비_대장.csv:{i} — 다른 줄과 기능위치 · 일련번호가 같은 옛 설비코드 줄({memo("설비코드 체계를 바꿨습니다")})'] for i in f['legacy']],
        *[['센서_목록.csv', again, '빼기', f'자료/센서_목록.csv:{first} · {again} — 같은 설비 · 같은 태그를 다시 적은 줄(표본주기 · 수집방식 칸이 빈 쪽)'] for first, again in f['repeats']]]
    if supply:
        handled += [[D.QUOTE_FILE, i, '빼기', f'자료/{D.QUOTE_FILE}:{i} 유효기한 칸 — 기준일에 기한이 지난 견적'] for i in f['expired']] if supply != '줄마다' else []
        if supply != '줄마다':
            (pair, lines), = f['several'].items()
            drop = min(lines) if supply == '늦은 줄' else max(lines)
            handled.append([D.QUOTE_FILE, drop, '빼기', f'자료/{D.QUOTE_FILE}:{" · ".join(map(str, lines))} — {pair[0]} · {pair[1]}의 견적 두 줄 가운데 ' + ('먼저 받은 줄' if supply == '늦은 줄' else '나중에 받은 줄')])
    files['결과/행_처리.csv'] = A.csv_text(A.DESIGN_EXPLAIN['행_처리.csv'].replace('설비_대장.csv)', f'설비_대장.csv · {D.QUOTE_FILE})'), A.DESIGN_COLUMNS['행_처리.csv'], rows(handled) if rows else handled)
    files['결과/quantity_rules.py'] = quantity_rules_answer(scope)
    return files


def chosen(branch='E', supply=None):
    """결정 지점의 정한_것.csv 행(빈 틀의 지점 줄과 같은 이름 · 차례). supply가 None이면 셋째 줄은 빈 채로 둔다(응용 앞)."""
    D.require('실전반')
    _, _, unit, scope = B.policy(branch)
    f = facts()
    exp = literal(branch)
    code, key, old_serial, _ = D.REMOVED_PUMP
    new_serial = D.SERIALS[(code, key)]
    temps = sorted(i for i, s in B.numbered('센서_목록.csv') if s['설비코드'] == 'HYD-01' and s['태그'].startswith('TS') and i not in [x[1] for x in f['repeats']])
    place = ['구성 요소 자리와 그 실물', '나눔(일련번호가 붙은 실물을 따로 두고 철거된 실물을 남김)' if unit == '나눔' else '한 대상(일련번호는 구성 요소의 속성)',
             ('떼어 낸 펌프도 일련번호가 붙은 장치 한 대라 그 자리를 거쳐 간 장치를 물을 수 있게 하려고' if unit == '나눔' else '보전팀이 묻는 것은 지금 달린 펌프라 모델을 단순하게 두려고')
             + f' — 자료/구성요소_목록.csv:{f["gone"]} · {f["now"]} · 자료/현장_메모.md:{memo_line("구성 요소 목록의 일련번호")}',
             (f'{code} 주 펌프 자리에 {new_serial}(지금)와 {old_serial}(지난)이 실물로 남음' if unit == '나눔' else f'{code} 주 펌프 구성 요소에 지금 일련번호 {new_serial}만 속성으로 남음')]
    q = exp['sensor_props']['HYD-01:TS1'][0]
    quantity = ['같은 물리량의 범위', '붙은 자리까지 같아야 묶음' if scope == '자리' else '재는 값의 종류로 묶음(어디서 쟀는지는 센서 이름과 붙은 구성 요소로 봄)',
                ('운전 담당은 같은 자리의 값끼리 정상값과 견주므로' if scope == '자리' else '작동유의 온도는 어디서 쟀든 한 번에 모아 보고 어디서 쟀는지는 센서 이름과 붙은 구성 요소로 읽으려고')
                + ' — 자료/센서_목록.csv:' + ' · '.join(map(str, temps)) + f' · 자료/현장_메모.md:{memo_line("재는 값의 이름도")}',
                f'HYD-01 TS1이 든 물리량에 센서 {len(exp["quantity_members"][q])}개가 묶임']
    third = [SUPPLY_POINT, '', '', '']
    if supply:
        (pair, lines), = f['several'].items()
        v = purchase_literal(supply)[pair]
        third = [SUPPLY_POINT, {'늦은 줄': '나중에 받은 견적 하나만 담음', '이른 줄': '먼저 받은 견적 하나만 담음', '줄마다': '받은 날마다 견적을 따로 담음(식별자에 견적일)'}[supply],
                 {'늦은 줄': '새로 받은 견적이 앞 견적을 대신한다고 보고', '이른 줄': '먼저 받은 견적도 유효기한까지는 공급사가 약속한 조건이라', '줄마다': '둘 다 기준일에 유효해 어느 쪽을 쓸지는 구매팀이 공급사에 확인할 일이라 둘 다 보이려고'}[supply]
                 + ' — ' + ' · '.join(f'자료/{D.QUOTE_FILE}:{n}' for n in lines) + f' · 자료/현장_메모.md:{memo_line("받은 견적을 쌓아 둔 것")}',
                 f'{pair[0]} · {pair[1]} 답: {v}']
    return [place, quantity, third]


# ───────────── 독립 기대 값(자료 생성기의 정의에서 바로) ─────────────
def literal_part(code, key):
    """그 설비 · 구성 요소의 교체부품 칸에 적힌 글이 가리키는 사내 품번 — 괄호 속 품번 · 사내 품번 · 교차표에 하나로 적힌 표기 · 예비품 목록의 품명과 글자까지 같은 것 하나. 그 밖(빈칸 · 줄여 쓴 품명)은 None."""
    text = D.PART_TEXT.get(code, {}).get(key, '')
    parts = {p[0]: p[1] for p in D.PARTS}
    m = re.search(r'\((P-[A-Z0-9-]+)\)', text)
    if m:
        return m.group(1)
    if text in parts:
        return text
    hits = sorted({c[0] for c in D.CROSS if c[1] == text})
    if len(hits) == 1:
        return hits[0]
    named = [p for p, name in parts.items() if name == text]
    return named[0] if text and len(named) == 1 else None


def literal(branch):
    """verify_reference.expected와 같은 꼴의 기대 값 — 다만 원자료에 적힌 그대로다: 교체부품 칸은 적힌 글이 가리키는 품번만 잇고(같은 모델의 다른 설비로 미루어 잇지 않음),
    단위 칸이 빈 센서의 단위는 없음이다. 단위 글자는 견줄 때 L/min과 l/min을 같게 본다(same_unit)."""
    D.require('실전반')
    pol = B.POLICY[branch]
    t = D.TRUTH
    sensors, members, sprops, parts = {}, {}, {}, {}
    for aid, a in t['assets'].items():
        for tag, s in a['sensors'].items():
            sensors.setdefault(aid, {}).setdefault(s['component'] or '(설비 전체)', []).append(tag)
            q = 'quantity:TS3' if (pol[3] == '자리' and s['quantity'] == 'quantity:TS1' and s['component'] == 'tank') else s['quantity']
            q = D.QUANTITY_KINDS[q][0] if pol[3] == '종류' else q
            members.setdefault(q, []).append(f'{aid}:{tag}')
            unit = None if (aid, tag) == ('HYD-03', 'VS1') else s['unit']      # 센서 목록에서 단위 칸을 비워 둔 줄(data_session2.sensor_rows)
            sprops[f'{aid}:{tag}'] = [q, unit, s['normal'], s['limit'], s['direction']]
        parts[aid] = {key: literal_part(aid, key) for key in a['components']}
    units = {f'{aid}:{key}': [[s, True]] for (aid, key), s in sorted(D.SERIALS.items())}
    units[f'{D.REMOVED_PUMP[0]}:{D.REMOVED_PUMP[1]}'].append([D.REMOVED_PUMP[2], False])
    return {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors.items())},
            'quantity_members': {k: sorted(v) for k, v in sorted(members.items())}, 'sensor_props': dict(sorted(sprops.items())),
            'parts_by_asset': {a: dict(sorted(d.items())) for a, d in sorted(parts.items())},
            'units': {k: sorted(v) for k, v in units.items()} if pol[2] == '나눔' else {}}


def usage(part):
    """그 사내 품번을 쓰는 설비 코드들(원자료에 적힌 그대로)."""
    return sorted(a for a, comps in D.TRUTH['assets'].items() if any(literal_part(a, k) == part for k in comps['components']))


def quote_text(v):
    return ' · '.join([v['avl_status'] if 'avl_status' in v else '미등록', '%g' % v['price_manwon'], '%g' % v['defect_rate'], '%g' % v['lead_days']])


def purchase_literal(mode):
    """셋째 결정의 갈래마다 {(공급사, 사내 품번): 질문 5의 답 글}. 기준일에 유효한 견적만(data_session2.TRUTH — 견적표를 다시 읽지 않는다)."""
    late, early = D.TRUTH['supply_modes'][D.QUOTE_MODES[0]], D.TRUTH['supply_modes'][D.QUOTE_MODES[1]]
    if mode == '늦은 줄':
        return {k: quote_text(v) for k, v in late.items()}
    if mode == '이른 줄':
        return {k: quote_text(v) for k, v in early.items()}
    return {k: quote_text(early[k]) + (' / ' + quote_text(late[k]) if late[k]['quote_line'] != early[k]['quote_line'] else '') for k in late}


EXPECT_ASSET, EXPECT_UNIT_ASSET = 'HYD-01', 'HYD-02'
EXPECT_SENSORS = ('HYD-01:TS1', 'HYD-02:PS1', 'HYD-05:DP_FILTER', 'HYD-07:TI-1')   # 둘째는 한계 칸에 단위가 붙어 적힌 줄, 셋째는 다른 단위(kPa)로 적은 다른 제조사 설비, 넷째는 현장 지시계
EXPECT_CODES = ('P-PMP-SEAL', 'PS-4510', 'RF-10', 'P-PMP-SEAL-X')
PURCHASE_CODES = (ASKED_PART, 'P-CLR-CORE', 'HI-CC-45A', 'P-PMP-SEAL-X')            # 구매팀 질문: 사내 품번 둘 · 다른 표기 · 없는 품번


def expect_text(branch='E', supply=None, lap=True):
    """기대 답 표 — 독립 기대 값(literal · purchase_literal)에서 만든다."""
    exp = literal(branch)
    pol = B.POLICY[branch]
    names = B.quantities_of(pol)
    f = facts()
    skip = {again for _, again in f['repeats']}
    line = {(s['설비코드'], s['태그']): i for i, s in B.numbered('센서_목록.csv') if i not in skip}
    own = sorted(i for (code, _), i in line.items() if code == EXPECT_ASSET)
    rows = []
    per = {k: v for k, v in exp['sensors_by_asset'][EXPECT_ASSET].items() if k != '(설비 전체)'}
    for key, tags in sorted(sorted(per.items(), key=lambda x: B.CANON_NAME[x[0]]), key=lambda x: -len(x[1]))[:3]:
        rows.append(['1', EXPECT_ASSET, B.CANON_NAME[key], ' · '.join(sorted(tags)), f'자료/센서_목록.csv:{own[0]}~{own[-1]} 붙은곳 칸'])
    rows.append(['1', EXPECT_ASSET, '설비 전체', ' · '.join(exp['sensors_by_asset'][EXPECT_ASSET]['(설비 전체)']), f'자료/센서_목록.csv:{f["wide"][0]} 붙은곳 칸'])
    key = D.REMOVED_PUMP[1]
    serials = (' · '.join(f'{s}({"지금" if current else "지난"})' for s, current in sorted(exp['units'][f'{EXPECT_UNIT_ASSET}:{key}'], key=lambda x: not x[1]))
               if pol[2] == '나눔' else D.SERIALS[(EXPECT_UNIT_ASSET, key)])
    rows.append(['1', EXPECT_UNIT_ASSET, B.CANON_NAME[key] + ' 실물', serials, f'자료/구성요소_목록.csv:{f["gone"]} · {f["now"]} 일련번호 · 비고 칸'])
    props = exp['sensor_props']
    q = props[EXPECT_SENSORS[0]][0]
    rows.append(['2', names[q][0], '', ' · '.join(exp['quantity_members'][q]), '자료/센서_목록.csv 태그 · 재는것 · 붙은곳 칸'])
    for sid in EXPECT_SENSORS:
        q, unit, normal, limit, direction = props[sid]
        value = ' · '.join([unit or '없음', '없음' if normal is None else '%g' % normal, '없음' if limit is None else '%g' % limit, {'upper': '상한', 'lower': '하한'}.get(direction, '없음')])
        rows.append(['2', names[q][0], sid, value, f'자료/센서_목록.csv:{line[tuple(sid.split(":"))]} 단위 · 정상값 · 한계 · 한계구분 칸'])
    cross = lambda code: [i for i, c in B.numbered('품번_교차표.csv') if c['다른표기'] == code]
    part_of = lambda code: code if code in D.TRUTH['parts'] else next(iter(sorted({c[0] for c in D.CROSS if c[1] == code})), None)
    for code in EXPECT_CODES:
        pid = part_of(code)
        if pid is None:
            rows.append(['3', code, '', '없음', '자료/예비품_목록.csv · 자료/품번_교차표.csv에 없음'])
            continue
        rows.append(['3', code, pid, ' · '.join(usage(pid)) or '쓰는 설비 없음', (f'자료/품번_교차표.csv:{cross(code)[0]} · ' if cross(code) else '') + '자료/구성요소_목록.csv 교체부품 칸'])
    if lap:
        rows.append(A.lap_question())
    if supply:
        answers = purchase_literal(supply)
        qline = {}
        for i, r in B.numbered(D.QUOTE_FILE):
            qline.setdefault((next(s for s in D.SUPPLIERS if r['공급사'].startswith(s)), r['품번']), []).append(i)
        for code in PURCHASE_CODES:
            pid = part_of(code)
            if pid is None:
                rows.append(['5', code, '', '없음', '자료/예비품_목록.csv · 자료/품번_교차표.csv에 없음'])
                continue
            rows.append(['5', code, pid, ' · '.join(usage(pid)) or '쓰는 설비 없음', '자료/구성요소_목록.csv 교체부품 칸'])
            for (sup, p), text in sorted(answers.items()):
                if p == pid:
                    name = next((n for n in (pid, D.TRUTH['parts'][pid]) if (sup, n) in qline), pid)
                    rows.append(['5', code, f'{pid}/{sup}', text, f'자료/{D.QUOTE_FILE}:' + ' · '.join(map(str, qline[(sup, name)])) + f' · 자료/{D.AVL_FILE} 승인상태 · 유효기한 칸'])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(A.EXPECT_COLUMNS_DESIGN)
    for r in rows:
        w.writerow(r)
    return f'# {F.MARK} — {EXPECT_EXPLAIN}\n' + buf.getvalue()


EXPECT_EXPLAIN = (A.EXPECT_EXPLAIN_DESIGN.replace('질문 = 1 · 2 · 3(와 내가 더하는 4)', '질문 = 1 · 2 · 3(와 내가 더하는 4, 구매팀이 묻는 5)')
                  .replace(' ' + A.EXPECT_FORMAT, ' 질문 5 = 구매팀이 묻는 질문: 물을_값은 품번이나 표기, 항목은 찾을 사내 품번(답 = 그 부품을 쓰는 설비 코드들) 또는 「사내 품번/공급사 이름」'
                           '(답 = 기준일에 유효한 견적의 「승인상태 · 단가(만원) · 불량률(0~1) · 납기(일)」 — 한 공급사에 견적이 여럿이면 견적일 차례로 「 / 」로 이음). ' + A.EXPECT_FORMAT))
if '질문 5 = 구매팀' not in EXPECT_EXPLAIN or '구매팀이 묻는 5)' not in EXPECT_EXPLAIN:
    raise ValueError('기대 답 틀의 칸 뜻 문장이 바뀌었습니다 — 질문 5 풀이를 넣을 자리를 다시 봅니다.')
