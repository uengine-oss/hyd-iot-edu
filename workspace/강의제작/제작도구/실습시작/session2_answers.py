"""2회차 네 랩 가이드의 「정답 보기」 내용 — 강사 참조(build_labs.reference_model 갈래 · data_session2 원자료)에서 만든다. 학생 폴더에는 들어가지 않는다.

정할 자리 파일의 정답 내용(apply)과 기대 답 표를 돌려준다. verify_reference.py의 토글 재생이 이 내용을 새 랩 사본에 써 넣고
`python show_result.py`를 돌려 강사 참조와 같은 답이 나오는지 본다(DoD 11).
"""
import csv
import io
import re

import build_labs as B
import data_session2 as D
import lab_frame as F


def csv_text(explain, columns, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(columns)
    for r in rows:
        w.writerow(r)
    return f'# {F.MARK} — {explain}\n' + buf.getvalue()


# ───────────── 통합 02-3 ─────────────
DESIGN_EXPLAIN = {
    '설계.csv': '대상(설비 · 구성 요소 · 센서 · 물리량 · 부품, 구성 요소 자리와 그 실물을 나눌 때만 실물)마다 ID를 무엇으로 지을지 — {열 이름}과 글자를 이은 꼴. 쓸 수 있는 열: 설비 = 설비코드 · 모델 · 기능위치 · 일련번호 / 구성 요소 = 설비코드 · 구성요소(5단계에서 정한 이름) · 계통 / 센서 = 설비코드 · 태그 · 계장태그 / 물리량 = 물리량(6단계에서 정한 이름) / 부품 = 품번 / 실물 = 설비코드 · 구성요소 · 일련번호',
    '관계.csv': '연결(설비-구성 요소 · 구성 요소-센서 · 설비-센서(붙은곳이 설비 전체인 센서만) · 센서-물리량 · 구성 요소-부품, 쓸 때만 부품-부품 · 구성 요소-실물 · 구성 요소-부품 후보)마다 관계 이름(영어 대문자) · 시작(그 연결의 두 대상 가운데 하나) · 카디널리티(1:1 · 1:N · N:1 · N:M — 시작 쪽 수:끝 쪽 수, 1은 많아야 하나). 부품-부품은 같은 규격을 한 물품으로 이을 때, 구성 요소-실물은 구성 요소 자리와 그 실물을 나눌 때, 구성 요소-부품 후보는 확인 필요로 남길 때',
    '이름.csv': '내 규칙(name_rules.py)으로 정해지지 않는 원자료 구성 요소 이름(붙은곳 · 쓰는곳 포함)만 — 내가 정한 이름. 적지 않은 이름은 규칙대로, 규칙에도 묶이지 않으면 원자료 이름 그대로 — 모델이 비면 모든 모델',
    '행_처리.csv': '겹치거나 기준일에 살아 있지 않은 원자료 행을 어떻게 할지 — 파일(설비_대장.csv · 구성요소_목록.csv · 센서_목록.csv) · 행(편집기 줄 번호) · 처리(빼기 · 하나로:<남길 행> · 옛 코드:<설비코드> · 지난 실물:<지금 실물 행> — 지난 실물은 구성 요소 자리와 그 실물을 나눌 때 구성요소_목록.csv만)',
    '물리량.csv': '내 규칙(quantity_rules.py)으로 정해지지 않는 것만 — 대상(재는것 글자, 또는 센서 행 하나 센서_목록.csv:<행>) · 묶을 물리량 이름 · 종류(실측 · 계산값 · 설정값). 센서 행으로 적은 것이 재는것 글자보다 먼저. 적지 않은 것은 규칙대로',
    '단위.csv': '내 규칙(unit_rules.py)으로 정해지지 않는 것만 — 물리량의 기준 단위, 또는 단위 칸이 빈 센서 행(센서_목록.csv:<행>)의 단위나 미확인. 적지 않은 것은 규칙대로',
}
DESIGN_COLUMNS = {'설계.csv': ['대상', 'ID_만드는_법', '근거'], '관계.csv': ['연결', '관계_이름', '시작', '카디널리티', '근거'],
                  '이름.csv': ['원자료_이름', '모델', '구성요소_이름', '근거'], '행_처리.csv': ['파일', '행', '처리', '근거'],
                  '물리량.csv': ['대상', '물리량', '종류', '근거'], '단위.csv': ['대상', '값', '근거']}
EXPECT_COLUMNS_DESIGN = ['질문', '물을_값', '항목', '기대_답', '근거']
EXPECT_FORMAT = '여러 값은 「 · 」로 잇고, 값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」'   # 2회차 네 랩 기대 답 표의 같은 꼴(결과 화면이 이 꼴로 견줌)
# 기대 답 표의 칸 뜻 — 2회차 네 랩이 이 한 곳에서 빈 틀 첫 줄과 3단계 힌트 「지킬 것」을 가져간다(값은 넣지 않고 꼴과 뜻만 — K-4)
EXPECT_EXPLAIN_DESIGN = ('한 줄 = (질문 · 물을_값 · 항목) 하나. 질문 = 1 · 2 · 3. 물을_값 = 질문 1은 설비 코드, 질문 2는 물리량 이름(6단계에서 정할 이름), 질문 3은 품번이나 표기. '
                         '항목 = 질문 1은 구성 요소 이름(5단계에서 정한 이름), 질문 2는 비우거나(그 물리량을 재는 센서 목록) 설비코드:태그(그 센서의 값), 질문 3은 찾을 사내 품번(확인 필요로 남긴 설비는 「사내 품번(확인 필요)」 줄, 원자료에 없는 품번이면 비움). 질문 1의 센서에는 계산값 · 설정값도 듦. '
                         '기대_답 = 질문 1은 센서 태그들, 질문 2는 설비코드:태그들 또는 「단위 · 정상값 · 한계 · 한계구분」 차례의 값, 질문 3은 쓰는 설비 코드들(원자료에 없는 품번은 「없음」). '
                         '근거 = 파일:줄(원자료에 없는 품번은 찾아본 파일 이름만 「data/파일.csv · data/파일.csv에 없음」). ' + EXPECT_FORMAT)

NAME_RULES_BLANK = f'''# {F.MARK} — 같은 장치를 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_device(a, b):
    """원자료 구성 요소 행 두 개(a, b)를 같은 장치로 볼지. 제공 코드가 모든 짝에 부르고, True인 짝끼리 이어 한 묶음으로 만든다.
    a, b = {{'설비코드', '모델', '계통', '이름'(원자료 이름), '태그'(그 자리에 붙은 센서 태그 목록),
            '부품'(제공 코드가 괄호 속 품번 · 사내 품번 · 품번 교차표로 푼 사내 품번, 못 풀면 ''), '줄'(구성요소_목록.csv:<행>)}}.
    돌려줄 것: True 또는 False."""
    raise NotImplementedError


def group_name(members):
    """같은 장치로 묶인 행들(위와 같은 dict, 구성 요소 목록 차례)에 쓸 이름 하나. 돌려줄 것: 이름(str)."""
    raise NotImplementedError
'''

QUANTITY_RULES_BLANK = f'''# {F.MARK} — 같은 물리량과 센서 종류를 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_quantity(a, b):
    """센서 행 두 개(a, b)를 같은 물리량을 재는 것으로 볼지. 제공 코드가 모든 짝에 부르고, True인 짝끼리 이어 한 묶음으로 만든다.
    a, b = {{'설비코드', '모델', '제조사', '태그', '계장태그', '재는것', '단위', '수집방식', '비고',
            '붙은곳'(5단계에서 정한 구성 요소 이름, 설비에 바로 붙었으면 '설비 전체'), '계통'(그 구성 요소의 계통),
            '같은_계통_계장태그'(같은 설비 · 같은 계통에 붙은 다른 센서의 계장태그, 없으면 태그), '줄'(센서_목록.csv:<행>)}}.
    돌려줄 것: True 또는 False."""
    raise NotImplementedError


def quantity_name(members):
    """한 묶음의 센서 행들(위와 같은 dict, 센서 목록 차례)에 쓸 물리량 이름 하나. 서로 다른 묶음에는 다른 이름을 줍니다. 돌려줄 것: 이름(str)."""
    raise NotImplementedError


def kind_of(row):
    """센서 행 하나(위와 같은 dict)의 종류. 돌려줄 것: '실측' · '계산값' · '설정값' 가운데 하나."""
    raise NotImplementedError
'''

UNIT_RULES_BLANK = f'''# {F.MARK} — 기준 단위와 빈 단위 칸을 정하는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def base_unit(quantity, units):
    """물리량 하나(quantity = 6단계에서 정한 이름)의 기준 단위. units = 그 물리량 센서 행들의 단위 칸 글자(빈칸 뺌, 센서 목록 차례).
    돌려줄 것: 단위(str). 다른 단위의 값은 제공 코드가 이 단위로 환산한다."""
    raise NotImplementedError


def blank_unit(row, candidates):
    """단위 칸이 빈 센서 행(row)의 단위. row · candidates = {{'설비코드', '모델', '태그', '단위', '정상값', '한계', '한계구분', '물리량', '줄'}},
    candidates = 같은 물리량에서 단위 칸이 찬 센서 행들. 돌려줄 것: 단위(str) 또는 '미확인'."""
    raise NotImplementedError
'''


def memo_line(text):
    """현장 메모에서 text가 든 줄 번호(편집기 줄). 없으면 멈춘다."""
    hits = [i for i, x in enumerate(D.memo().splitlines(), 1) if text in x]
    if len(hits) != 1:
        raise ValueError(f'현장 메모에서 「{text}」 줄을 하나로 찾지 못함: {hits}')
    return hits[0]


def name_rules_answer():
    return f'''# {F.MARK} — 같은 장치를 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_device(a, b):
    """근거: 현장 메모 {memo_line('같은 모델(HPP-45A)')}행(HYD-01 ~ 03은 같은 모델) · {memo_line('태그 이름(TS1')}행(한일유압 설비는 태그 이름이 같음) —
    같은 모델에서 같은 태그가 붙은 자리는 같은 장치. 예비품 목록의 사내 품번 — 같은 교체 부품을 쓰는 자리는 같은 장치. 계통이 다르면 다른 장치."""
    if a['계통'] != b['계통']:
        return False
    if a['모델'] == b['모델'] and set(a['태그']) & set(b['태그']):
        return True
    return a['부품'] != '' and a['부품'] == b['부품']


def group_name(members):
    """근거: 구성 요소 목록에서 가장 앞선 행(HYD-01)의 이름을 묶음의 이름으로 쓴다."""
    return members[0]['이름']
'''


def quantity_rules_answer(scope='종류'):
    """같은 물리량의 범위 — '종류'(재는 값의 종류: 무엇의 어떤 값, 자리는 붙은 구성 요소가 말함) · '자리'(같은 종류이면서 붙은 계통 · 측정 지점까지 같아야)."""
    common = f'''# {F.MARK} — 같은 물리량과 센서 종류를 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.
import re

NAMES = {{'T': '작동유 온도', 'T:제어반': '제어반 온도', 'P': '작동유 압력', 'PD': '차압', 'F': '작동유 유량', 'F:냉각수': '냉각수 유량',
         'V': '진동', 'J': '모터 출력', 'I': '모터 전류', 'L': '레벨'}}


def value_kind(tag, row=None):
    """재는 값의 종류: 계장태그 앞 글자(ISA-5.1 첫 글자 = 재는 변수, PDT = 차압)와 매체. 계장태그가 없으면 TI-1 같은 현장 지시계 태그로 본다.
    계기 없는 계산값 · 설정값은 None(현장 메모 {memo_line('계장 도면에는')}행)."""
    m = re.match(r'([A-Z]+)-\\d', tag or '')
    if not m:
        return None
    letters = m.group(1)
    v = 'PD' if letters.startswith('PD') else letters[0]
    if row is not None and '냉각수' in row['재는것']:
        return v + ':냉각수'
    if row is not None and v == 'T' and row['계통'] == '제어':
        return 'T:제어반'
    return v


def kind(row):
    return value_kind(row['계장태그'] or row['태그'], row)


def loop(tag):
    """계장태그 「TT-231」 → ('TT', '1'): 기능 글자와 루프 번호에서 앞 두 자리(설비)를 뺀 나머지. 3라인 도면은 끝자리를 맞추지 않았다(현장 메모 {memo_line('3라인 도면은')}행)."""
    m = re.fullmatch(r'([A-Z]+)-\\d\\d(\\d+)', tag)
    return m.groups() if m else None


def same_label(a, b):
    """재는것이 같거나, 한일유압 설비끼리 태그가 같거나, 같은 라인 도면의 루프가 같다(현장 메모 {memo_line('태그 이름(TS1')}행)."""
    return (a['재는것'] == b['재는것'] or (a['제조사'] == b['제조사'] and a['태그'] == b['태그'])
            or (loop(a['계장태그']) is not None and loop(a['계장태그']) == loop(b['계장태그'])))


def kind_of(row):
    """근거: 센서_목록.csv 비고 「계기 없음」은 계산값, 수집방식 「설정값」은 설정값, 나머지는 계기가 잰 실측."""
    if '계기 없음' in row['비고']:
        return '계산값'
    if '설정값' in row['수집방식']:
        return '설정값'
    return '실측'
'''
    if scope == '종류':
        return common + '''

def same_quantity(a, b):
    """근거: 재는 값의 종류가 같으면 같은 물리량 — 어디에 붙었는지는 센서가 붙은 구성 요소(붙은곳)가 따로 말한다. 계기 없는 값은 재는것 · 태그로 묶는다."""
    if kind(a) is None or kind(b) is None:
        return kind(a) is None and kind(b) is None and same_label(a, b)
    return kind(a) == kind(b)


def quantity_name(members):
    """근거: 재는 값의 종류 이름. 계기 없는 값은 묶음에서 가장 많이 쓴 재는것(같은 수면 먼저 나온 것)."""
    k = kind(members[0])
    if k is not None:
        return NAMES[k]
    names = [m['재는것'] for m in members]
    return max(names, key=lambda n: (names.count(n), -names.index(n)))
'''
    return common + '''

def only_one(row):
    """같은 설비 · 같은 계통에 이 종류 계기가 이것 하나뿐인가."""
    return not any(value_kind(t) == kind(row) for t in row['같은_계통_계장태그'])


def same_quantity(a, b):
    """근거: 재는 값의 종류가 같고 붙은 계통도 같아야 같은 물리량. 그 계통에 같은 종류 계기가 둘 이상이면(쿨러 입구 · 출구 유온) 재는것 · 태그 · 루프로 지점을 가르고,
    하나뿐이면 같은 지점이다(탱크에 붙은 유온계 하나 = 탱크 유온)."""
    if kind(a) != kind(b) or a['계통'] != b['계통']:
        return False
    if kind(a) is None:
        return same_label(a, b)
    return same_label(a, b) or (only_one(a) and only_one(b))


def quantity_name(members):
    """근거: 묶음에서 가장 많이 쓴 재는것(같은 수면 먼저 나온 것) — 지점을 가리키는 이름."""
    names = [m['재는것'] for m in members]
    return max(names, key=lambda n: (names.count(n), -names.index(n)))
'''


def unit_rules_answer():
    return f'''# {F.MARK} — 기준 단위와 빈 단위 칸을 정하는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def base_unit(quantity, units):
    """근거: 그 물리량에서 원자료가 가장 많이 쓴 단위(같은 수면 센서 목록에서 먼저 나온 것)."""
    return max(units, key=lambda u: (units.count(u), -units.index(u)))


def blank_unit(row, candidates):
    """근거: 같은 모델 · 같은 태그 · 같은 정상값 · 한계 · 한계구분의 줄이 단위 하나를 말할 때만 그 단위, 아니면 미확인(짐작하지 않음)."""
    key = ('모델', '태그', '정상값', '한계', '한계구분')
    same = {{c['단위'] for c in candidates if all(c[k] == row[k] for k in key)}}
    return same.pop() if len(same) == 1 else '미확인'
'''

PART_RULES_BLANK = f'''# {F.MARK} — 교체 부품을 잇는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def find_part(cell, asset, component, spares, cross, same_component, same_model):
    """구성요소_목록.csv의 교체부품 칸을 제공 코드가 바로 풀지 못한 행(빈칸 · 품명 · 짧은 표기)에서 부른다.
    cell = 교체부품 칸 글자(빈칸이면 ''), asset = {{'설비코드', '모델'}}, component = 내가 정한 구성 요소 이름,
    spares = 예비품_목록.csv 행들(dict), cross = 품번_교차표.csv 행들(dict),
    same_component(원자료 이름) = 그 이름이 이 구성 요소와 같은 것인지(5단계에서 정한 이름 기준 — 그 모델의 구성 요소에 없는 이름은 원자료 이름 그대로 견줌) True · False,
    same_model = 같은 모델의 다른 설비에서 같은 구성 요소의 교체부품 칸이 품번으로 풀린 것 [{{'설비코드', '품번'}}, ...](없으면 빈 목록).
    돌려줄 것: 이을 사내 품번(str), None(잇지 않음), 또는 확인이 필요한 후보 사내 품번 목록(list — 「확인 필요」로 남김)."""
    raise NotImplementedError


def same_item(maker_code, internal_codes):
    """같은 제조사 품번(maker_code)으로 등록된 사내 품번이 둘 이상일 때 부른다(internal_codes = 그 사내 품번들).
    돌려줄 것: True(한 물품으로 잇는다) 또는 False(따로 둔다)."""
    raise NotImplementedError
'''


def part_rules_answer(same, mode='이음'):
    """part_rules.py — 같은 규격(same: True = 한 물품)과 품번이 적히지 않은 칸의 갈래(mode: 이음 · 확인 · 안 이음 — build_labs.LINK_MODE)."""
    if mode == '이음':
        find = """    hits = sorted(s['품번'] for s in spares if applies(asset['모델'], s['적용모델']) and same_component(s['쓰는곳']))
    if len(hits) == 1:
        return hits[0]
    used = sorted({m['품번'] for m in same_model if m['품번'] in hits})
    return used[0] if len(used) == 1 else None"""
        why = ('근거: 예비품_목록.csv의 적용모델 · 쓰는곳 — 같은 모델의 같은 구성 요소에 쓰는 예비품이 하나면 그것. '
               '둘 이상이면 같은 모델의 다른 설비가 그 자리에 품번으로 적은 것이 그 가운데 하나를 가리킬 때만 그것(같은 모델은 같은 부품을 씀).')
    elif mode == '확인':
        find = """    hits = sorted(s['품번'] for s in spares if applies(asset['모델'], s['적용모델']) and same_component(s['쓰는곳']))
    if not hits:
        return None
    if cell and len(hits) == 1:
        return hits[0]
    return hits"""
        why = ('근거: 품명만 적혀 있고 같은 모델 · 같은 쓰는곳의 예비품이 하나면 그것. 칸이 비었거나(구성요소_목록.csv 비고 「교체부품 칸 확인 못 함」) '
               '후보가 둘 이상이면 원자료가 품번을 정하지 않은 것이라 후보를 확인 필요로 남긴다.')
    else:
        find = """    return None"""
        why = '근거: 칸에 품번이 없으면 원자료가 그 부품을 말하지 않은 것 — 예비품 목록으로 짐작해 잇지 않는다(작업 규칙 3).'

    return f'''# {F.MARK} — 교체 부품을 잇는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def applies(model, text):
    """예비품 목록 적용모델 칸 — 「전 모델」, 「HPP-45A」, 「HPP-45A·45B」 꼴."""
    if text == '전 모델':
        return True
    head, *rest = text.split('·')
    prefix = head.rsplit('-', 1)[0] + '-'
    return model in [head, *[prefix + x for x in rest]]


def find_part(cell, asset, component, spares, cross, same_component, same_model):
    """구성요소_목록.csv의 교체부품 칸을 제공 코드가 바로 풀지 못한 행(빈칸 · 품명 · 짧은 표기)에서 부른다.
    {why}"""
{find}


def same_item(maker_code, internal_codes):
    """근거: 현장 메모 {memo_line('합칠지 검토')}행(3라인 자재는 따로 등록, 합칠지 검토 중), 공급_조건.csv의 두 품번 견적(공급사 · 단가가 다름), 품번_교차표.csv의 같은 제조사 품번 줄."""
    return {same}
'''


def integrated_design(branch='A'):
    """통합 02-3 빈 틀의 정답 내용 {경로: 글}. 갈래는 build_labs.POLICY(A~E)."""
    src = {n: B.rows(n) for n in ['설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv', '예비품_목록.csv']}
    same, mode, unit, scope = B.policy(branch)
    split = unit == '나눔'
    files = {}
    memo = lambda text: f'자료/현장_메모.md:{memo_line(text)}'
    comp_line = {(c['설비코드'], c['구성요소']): i for i, c in enumerate(src['구성요소_목록.csv'], 2) if '철거' not in c['비고']}
    sensor_line = {(s['설비코드'], s['태그']): i for i, s in reversed(list(enumerate(src['센서_목록.csv'], 2)))}
    spare_line = {p['품번']: i for i, p in enumerate(src['예비품_목록.csv'], 2)}
    cl, sl, pl = (lambda code, name: f'자료/구성요소_목록.csv:{comp_line[(code, name)]}'), (lambda code, tag: f'자료/센서_목록.csv:{sensor_line[(code, tag)]}'), \
        (lambda pid: f'자료/예비품_목록.csv:{spare_line[pid]}')
    files['결과/설계.csv'] = csv_text(DESIGN_EXPLAIN['설계.csv'], DESIGN_COLUMNS['설계.csv'], [
        ['설비', '{설비코드}', f'{memo("설비코드 체계")} — 설비코드 체계가 바뀌어 옛 코드 줄이 있음(행_처리에서 정함)'],
        ['구성 요소', '{설비코드}:{구성요소}', f'{memo("같은 모델(HPP-45A)")} — 같은 모델의 같은 품목이 여러 설비에 있으므로 설비코드를 붙임'],
        ['센서', '{설비코드}:{태그}', f'{memo("태그 이름(TS1")} — 태그 이름은 같은 회사 설비가 모두 같은 이름을 씀'],
        ['물리량', '{물리량}', f'{memo("재는 값의 이름도")} — 재는 값의 이름도 사람마다 다름'],
        ['부품', '{품번}', '자료/예비품_목록.csv:1 품번 칸(사내 품번)'],
        *([['실물', '{일련번호}', f'{memo("구성 요소 목록의 일련번호")} — 구성 요소의 일련번호는 거기 달린 장치 한 대']] if split else [])])
    files['결과/관계.csv'] = csv_text(DESIGN_EXPLAIN['관계.csv'], DESIGN_COLUMNS['관계.csv'], [
        ['설비-구성 요소', 'HAS_COMPONENT', '설비', '1:N', '자료/구성요소_목록.csv:1 — 설비마다 구성 요소 여러 줄, 한 줄은 설비 하나'],
        ['구성 요소-센서', 'MONITORED_BY', '구성 요소', '1:N', '자료/센서_목록.csv:1 붙은곳 칸 — 한 구성 요소에 센서 여럿, 센서 하나는 한 구성 요소'],
        ['설비-센서', 'MONITORED_BY', '설비', '1:N', f'{sl("HYD-01", "SE")} — 붙은곳이 설비 전체'],
        ['센서-물리량', 'OBSERVES', '센서', 'N:1', '자료/센서_목록.csv:1 재는것 칸 — 센서 하나는 물리량 하나를 잰다'],
        ['구성 요소-부품', 'USES_PART', '구성 요소', 'N:1', '자료/구성요소_목록.csv:1 교체부품 칸 — 한 구성 요소에 칸 하나, 한 부품을 여러 구성 요소가 씀'],
        *([['부품-부품', 'SAME_ITEM_AS', '부품', 'N:1', '자료/품번_교차표.csv:1 표기종류 「제조사 품번」']] if same == '한 물품' else []),
        *([['구성 요소-실물', 'INSTALLED_UNIT', '구성 요소', '1:N', f'{memo("구성 요소 목록의 일련번호")} · {cl("HYD-02", "유압 펌프")} — 한 구성 요소 자리에 지금 실물과 지난 실물']] if split else []),
        *([['구성 요소-부품 후보', 'CANDIDATE_PART', '구성 요소', 'N:M', f'{cl("HYD-03", "리턴 필터")} · {pl("P-RTN-FLT")} · {pl("P-RTN-FLT-25")} — 한 구성 요소에 후보 여럿']] if mode == '확인' else [])])
    files['결과/name_rules.py'] = name_rules_answer()
    rows = [  # 규칙(같은 모델의 같은 태그 · 같은 교체 부품)이 묶지 못한 이름 — 근거는 그 행과 견준 행
        ['스탠바이 펌프', 'HPP-45A', '예비 펌프 (B)', f'{cl("HYD-02", "스탠바이 펌프")} · {cl("HYD-01", "예비 펌프 (B)")} — 같은 모델 · 동력 계통의 둘째 펌프(주 펌프 다음 줄)'],
        ['축 커플링', 'HPP-45A', '커플링', f'{cl("HYD-03", "축 커플링")} 교체부품 「커플링 고무」 · {pl("P-CPL-ELM")} 쓰는곳 커플링'],
        ['축압기', 'HPP-45A', '어큐뮬레이터', f'{cl("HYD-03", "축압기")} 교체부품 「블래더」 · {pl("P-ACC-BLD")} 어큐뮬레이터 블래더'],
        ['오일 쿨러(공랭)', 'DPU-30', '오일 쿨러', f'{cl("HYD-05", "오일 쿨러(공랭)")} · {sl("HYD-05", "T_OIL")} 유온을 재는 자리(공랭식 오일 쿨러)'],
        ['모터', 'HPP-22M', '구동 모터', f'{cl("HYD-07", "모터")} · {cl("HYD-01", "구동 모터")} — 동력 계통의 모터 한 대'],
        ['펌프', 'HPP-22M', '메인 펌프', f'{cl("HYD-07", "펌프")} · {cl("HYD-05", "메인 펌프")} — 펌프가 한 대(주 · 예비 구분 없음)'],
    ]
    files['결과/이름.csv'] = csv_text(DESIGN_EXPLAIN['이름.csv'], DESIGN_COLUMNS['이름.csv'], rows)
    handle = []
    old = B.legacy_rows(src['설비_대장.csv'])
    for i, a in enumerate(src['설비_대장.csv'], 2):
        if a['설비코드'] in old:
            now = next(j for j, x in enumerate(src['설비_대장.csv'], 2) if x['설비코드'] == old[a['설비코드']])
            handle.append(['설비_대장.csv', i, f'옛 코드:{old[a["설비코드"]]}', f'자료/설비_대장.csv:{i} · {now} 같은 기능위치 · 일련번호 · 설치일, 상태 「{a["상태"]}」 · {memo("설비코드 체계")}'])
    for i, c in enumerate(src['구성요소_목록.csv'], 2):
        if '철거' in c['비고']:
            now = comp_line[(c['설비코드'], c['구성요소'])]
            handle.append(['구성요소_목록.csv', i, f'지난 실물:{now}' if split else '빼기',
                           f'자료/구성요소_목록.csv:{i} 비고 「{c["비고"]}」 · {now}행 「교체 설치」' + (' — 그 자리의 지난 실물' if split else ' — 기준일에 달려 있지 않은 실물')])
    seen = {}
    for i, s in enumerate(src['센서_목록.csv'], 2):
        k = (s['설비코드'], s['태그'])
        if k in seen:
            handle.append(['센서_목록.csv', i, f'하나로:{seen[k]}', f'자료/센서_목록.csv:{i} · {seen[k]} — 같은 설비 · 같은 태그 · 같은 계장태그(표본주기 · 수집방식이 빈 옮겨 적은 줄)'])
        else:
            seen[k] = i
    files['결과/행_처리.csv'] = csv_text(DESIGN_EXPLAIN['행_처리.csv'], DESIGN_COLUMNS['행_처리.csv'], handle)
    files['결과/quantity_rules.py'] = quantity_rules_answer(scope)
    files['결과/물리량.csv'] = csv_text(DESIGN_EXPLAIN['물리량.csv'], DESIGN_COLUMNS['물리량.csv'], [])   # 두 범위 모두 규칙으로 정해진다 — 예외 줄 없음
    files['결과/unit_rules.py'] = unit_rules_answer()
    files['결과/part_rules.py'] = part_rules_answer(same == '한 물품', mode)
    return files


def integrated_chosen(branch='A'):
    """결정 지점 넷의 정한_것.csv 행(빈 틀의 지점 줄과 같은 이름 · 차례). 갈래는 build_labs.POLICY."""
    same_, mode, unit, scope = B.policy(branch)
    comps = list(enumerate(B.rows('구성요소_목록.csv'), 2))
    sensors = list(enumerate(B.rows('센서_목록.csv'), 2))
    spares = {p['품번']: i for i, p in enumerate(B.rows('예비품_목록.csv'), 2)}
    place = next(a['기능위치'] for a in B.rows('설비_대장.csv') if a['설비코드'] == 'HYD-03')
    receipts = next(i for i, r in enumerate(B.rows('입고_이력.csv'), 2) if place in r['비고'] and r['품번'] == 'P-PMP-SEAL')
    quotes = [i for i, q in enumerate(B.rows('공급_조건.csv'), 2) if q['품번'] in ('P-FAN-BRG', 'P-BRG-6205')]
    cross = [i for i, c in enumerate(B.rows('품번_교차표.csv'), 2) if c['다른표기'] == '6205-2RS']
    line = lambda code, name, note='': next(i for i, c in comps if c['설비코드'] == code and c['구성요소'] == name and note in c['비고'])
    sline = lambda code, tag: next(i for i, s in sensors if s['설비코드'] == code and s['태그'] == tag)
    place = [['구성 요소 자리와 그 실물', '나눔(일련번호가 붙은 실물을 따로 두고 철거된 실물을 남김)' if unit == '나눔' else '한 대상(일련번호는 구성 요소의 속성)',
              f'자료/구성요소_목록.csv:{line("HYD-02", "유압 펌프", "철거")} · {line("HYD-02", "유압 펌프", "교체 설치")} · 자료/현장_메모.md:{memo_line("구성 요소 목록의 일련번호")}',
              ('HYD-02 주 펌프 자리에 KP-2603-114(지금)와 KP-1902-551(지난)이 실물로 남음 — 보전팀은 철거해 수리 보낸 펌프가 예비로 돌아오면 그 실물의 이력을 이어 봄'
               if unit == '나눔' else 'HYD-02 주 펌프 구성 요소에 지금 일련번호 KP-2603-114만 속성으로 남음 — 철거한 펌프는 그래프에서 물을 수 없어, 보전팀은 수리 이력을 CMMS에서 따로 찾음')]]
    quantity = [['같은 물리량의 범위', '붙은 자리까지 같아야 묶음' if scope == '자리' else '재는 값의 종류로 묶음(자리는 붙은 구성 요소로 봄)',
                 f'자료/센서_목록.csv:{sline("HYD-07", "TI-1")} · {sline("HYD-01", "TS1")} · {sline("HYD-01", "TS2")} · {sline("HYD-01", "TS3")} · 자료/현장_메모.md:{memo_line("계장 도면에는")}',
                 ('유온 · 쿨러 출구 유온 · 탱크 유온이 따로 묶이고 HYD-07 유온계는 탱크 유온에 듦 — 운전은 그 45 ℃를 탱크 유온 정상값 40 ℃와 바로 견줌'
                  if scope == '자리' else
                  '작동유 온도 하나에 쿨러 입구 · 출구 · 탱크 센서가 함께 듦 — 운전은 견줄 정상값을 고를 때 센서가 붙은 구성 요소(HYD-07 유온계는 탱크)를 함께 보고 탱크 쪽 정상값 40 ℃를 고름')]]
    same = [['같은 규격의 다른 사내 품번', '한 물품' if same_ == '한 물품' else '따로',
             '자료/품번_교차표.csv:' + ' · '.join(map(str, cross)) + f' · 자료/현장_메모.md:{memo_line("합칠지 검토")} · 자료/공급_조건.csv:' + ' · '.join(map(str, quotes)),
             ('P-FAN-BRG · P-BRG-6205를 물으면 다섯 대(HYD-01~03 · 05 · 06) — 보전팀은 3라인 팬 베어링이 떨어지면 2라인 재고를 대체품으로 꺼내 쓰고, 구매팀은 두 품번 재고를 합쳐 셈'
              if same_ == '한 물품' else
              'P-FAN-BRG는 2라인 설비만, P-BRG-6205는 3라인 설비만 — 구매팀은 품번마다 계약 단가로 발주하고, 보전팀은 3라인 팬 베어링 재고가 떨어지면 대체품을 따로 확인 요청')]]
    basis = (f'자료/구성요소_목록.csv:{line("HYD-03", "주 펌프 A")} · {line("HYD-03", "리턴 필터")} · '
             f'자료/예비품_목록.csv:{spares["P-PMP-SEAL"]} · {spares["P-RTN-FLT"]} · {spares["P-RTN-FLT-25"]} · 자료/입고_이력.csv:{receipts}')
    link = [['품번이 적히지 않은 교체부품 칸', {'이음': '예비품 목록으로 이음(후보가 여럿이면 같은 모델 설비가 적은 품번)', '안 이음': '잇지 않음',
                                       '확인': '확인 필요로 남김(빈칸이거나 후보가 여럿이면)'}[mode], basis,
             {'이음': 'P-PMP-SEAL · P-RTN-FLT의 사용 설비에 HYD-03이 듦 — 구매팀은 HYD-03까지 넣어 재고 소요를 셈',
              '안 이음': 'HYD-03이 P-PMP-SEAL · P-RTN-FLT · P-FAN-BRG의 사용 설비에서 빠짐 — HYD-03 펌프 정비 때 예비품을 미리 준비하지 않음',
              '확인': 'HYD-03은 P-PMP-SEAL · P-RTN-FLT의 「확인 필요」 줄에만 나옴 — 보전팀이 전기계장 담당에게 HYD-03 품번 확인을 요청하고, 구매팀은 확인 전까지 재고 소요에 넣지 않음'}[mode]]]
    return place + quantity + same + link
DECISION_POINTS = ['구성 요소 자리와 그 실물', '같은 물리량의 범위', '같은 규격의 다른 사내 품번', '품번이 적히지 않은 교체부품 칸']   # 정한_것.csv 빈 틀에 미리 두는 지점 줄(쓰는 단계 차례)


# ───────────── 실전 02-3 ─────────────
QUOTE_RULE_BLANK = f'''# {F.MARK} — 기준일에 쓸 견적을 고르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def use_quote(quotes, as_of):
    """같은 공급사 · 같은 부품의 견적 줄들(공급_조건.csv 행 dict — 원자료 칸 그대로와 '줄' = 편집기 줄 번호)을 받는다. as_of = 자료 기준일('YYYY-MM-DD').
    돌려줄 것: 기준일 조건으로 쓸 줄 하나(받은 dict 그대로) 또는 None(이 쌍은 기준일에 쓸 조건이 없음)."""
    raise NotImplementedError
'''

APPROVAL_RULE_BLANK = f'''# {F.MARK} — 승인과 구매 담당이 함께 볼 것을 담는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def approval(entry, as_of):
    """SCM 승인 목록(승인공급사_목록.csv)의 그 공급사 · 부품 등록(dict — 원자료 칸 그대로와 '줄') 또는 None(등록 없음)을 받는다.
    돌려줄 것: {{'approved': True 또는 False, ...}} — approved 말고 남길 속성(이름은 영어 snake_case)도 이 dict에 함께."""
    raise NotImplementedError


def buyer_info(pair):
    """쌍 하나(공급사 · 부품 · 단가 · 불량률 · 납기 · 승인 결과 등 지금까지 붙은 값의 dict)를 받는다.
    돌려줄 것: 구매 담당이 공급사를 비교할 때 함께 봐야 해서 이 쌍에 더 남길 속성 dict(남길 것이 없으면 {{}}). 이미 있는 속성은 덮어쓰지 않는다."""
    raise NotImplementedError
'''

QUOTE_RULE_ANSWER = f'''# {F.MARK} — 기준일에 쓸 견적을 고르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def use_quote(quotes, as_of):
    """근거: 자료/현장_메모.md 6절(견적을 쌓아 둔 표), 공급_조건.csv 유효기한 칸 — 기준일에 기한이 지난 견적은 쓰지 않고, 남은 것 가운데 견적일이 가장 늦은 줄."""
    live = [q for q in quotes if q['유효기한'] >= as_of]
    return max(live, key=lambda q: q['견적일']) if live else None
'''


def approval_rule_answer(branch):
    """A = 조건부 승인도 승인 · 빈 조건은 조건 없음 · 7.4 정보 안 남김(ㄱ), B = 조건부 승인은 비승인, ㄴ = A + 7.4 정보, ㄷ = A + 빈 조건이 7.4에 걸리면 확인 필요."""
    ok = "('승인', '조건부 승인')" if branch != 'B' else "('승인',)"
    if branch == 'ㄴ':
        info = (f"    if pair['approved'] and round(pair['defect_rate'] * 100, 6) > {D.PR74_RATE_PCT}:\n"
                f"        return {{'inspection': '입고 전수 검사', 'compare_extra_manwon': {float(D.PR74_EXTRA_MANWON)}, 'rule_source': {B.PR74_SOURCE!r}}}\n"
                "    return {}\n")
        why = f'근거: {B.PR74_SOURCE} — 불량률이 {D.PR74_RATE_PCT} %를 넘는 승인 공급사는 입고 전수 검사, 비교 때 {D.PR74_EXTRA_MANWON}만 원을 더함'
    elif branch == 'ㄷ':
        info = (f"    if pair['approved'] and round(pair['defect_rate'] * 100, 6) > {D.PR74_RATE_PCT} and not pair.get('condition'):\n"
                f"        return {{'pending_check': 'SCM 등록에는 조건이 없고 {B.PR74_SOURCE}는 입고 전수 검사 · 비교 비용 +{D.PR74_EXTRA_MANWON}만 원 — 등록 확인 필요'}}\n"
                "    return {}\n")
        why = f'근거: {B.PR74_SOURCE}와 SCM 등록의 빈 조건 칸이 맞지 않는 쌍은 확인 필요로 표시'
    else:
        info = '    return {}\n'
        why = '근거: 구매기준서 7.3 — 승인 여부는 SCM 등록을 따른다. 그 밖에 더 남길 것 없음'
    return f'''# {F.MARK} — 승인과 구매 담당이 함께 볼 것을 담는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def approval(entry, as_of):
    """근거: 자료/구매기준서_PR-07_발췌.md 7.3(승인 여부는 SCM 등록을 따른다), 승인공급사_목록.csv 유효기한 칸."""
    if entry is None:
        return {{'approved': False, 'approval_status': '미등록'}}
    status = entry['승인상태']
    if entry['유효기한'] and entry['유효기한'] < as_of:
        status = '유효기한 경과'
    out = {{'approved': status in {ok}, 'approval_status': status}}
    if entry['조건']:
        out['condition'] = entry['조건']
    return out


def buyer_info(pair):
    """{why}"""
{info}'''


def practical_chosen(branch='ㄴ'):
    a = 'B' if branch == 'B' else 'A'
    return [['조건이 붙은 승인', '승인으로 담고 조건을 함께' if a == 'A' else '비승인으로', '자료/승인공급사_목록.csv:10 · 자료/구매기준서_PR-07_발췌.md:24',
             'A정밀 · 쿨러 코어의 approved ' + ('참' if a == 'A' else '거짓')],
            ['빈 값의 뜻', '조건 없음' if branch != 'ㄷ' else '미결(등록 확인 필요)', '자료/승인공급사_목록.csv:2', 'A정밀 · 펌프 축 씰 키트 ' + ('표시 없음' if branch != 'ㄷ' else 'pending_check 붙음')],
            ['쓰는 사람에 따라 갈리는 답', '7.4 정보를 함께 남김' if branch == 'ㄴ' else '승인 여부 · 단가 · 불량률 · 납기만', '자료/구매기준서_PR-07_발췌.md:30',
             'A정밀 · 펌프 축 씰 키트 ' + ('입고 전수 검사 · +20만 원' if branch == 'ㄴ' else '추가 칸 없음')]]


EXPECT_COLUMNS_SUPPLY = ['질문', '물을_값', '항목', '기대_답', '근거']
EXPECT_EXPLAIN_SUPPLY = ('한 줄 = (질문 · 물을_값 · 항목) 하나. 질문 = 1(사용 설비) · 2(공급 조건) — 질문 3은 질문 1 · 2 줄에 다른 표기 · 없는 품번을 물을_값으로 씀. '
                         '물을_값 = 모델에 물을 품번이나 표기 하나. 항목 = 질문 1은 찾을 사내 품번, 질문 2는 사내 품번/공급사. '
                         '기대_답 = 질문 1은 쓰는 설비 코드들, 질문 2는 「승인 여부 · 단가(만원) · 불량률(0~1) · 납기(일)」를 한 칸에. 근거 = 파일:줄. ' + EXPECT_FORMAT)


# ───────────── 실습4(그래프) ─────────────
GRAPH_EXPECT_COLUMNS = ['질문', '물을_값', '볼_열', '기대_답', '근거']
GRAPH_EXPECT_EXPLAIN = {course: ('(질문 · 물을_값) 짝마다 한 줄만 쓰고, 그 줄에서 견줄 열(볼_열)은 하나. 같은 짝의 다른 열을 견주려면 같은 대상의 다른 표기를 물을_값으로 쓴 줄을 더함. 질문 = query.cypher의 「// 질문 N」 번호. '
                                  f'물을_값 = $ 자리에 넣을 값 하나({ask}). 볼_열 = 그 조회 결과에서 견줄 열 이름 하나. '
                                  '기대_답 = 그 열의 값들(결과 줄마다 하나). 근거 = 파일:줄. ' + EXPECT_FORMAT)
                        for course, ask in [('통합반', '질문 1 · 2는 설비 코드, 질문 3은 품번이나 표기'), ('실전반', '질문 1 · 2 모두 품번이나 표기')]}
LOAD_BLANK = F.blank_text('적재 파일 — 문장마다 바로 위에 「// 넣을 것: <종류 또는 관계>」 한 줄, 행은 $rows로 받음(python show_result.py가 실행).\n'
                          '넣을 수 있는 종류 · 관계는 입력/schema.json에 있습니다.', '//')
QUERY_BLANK = F.blank_text('조회 파일 — 조회마다 바로 위에 「// 질문 <번호>」 한 줄, 물을 값은 $ 자리 하나로 받고, 조회 끝에 ;를 붙임(빠지면 다음 질문이 앞 조회에 묻힘).', '//')
UPDATE_BLANK = F.blank_text('수정 파일 — 수정본의 줄을 이미 넣은 그래프에 반영하는 문장들(문장 끝 ;). 전체를 지우는 문장은 실행되지 않습니다.', '//')


def load_answer(graph):
    labels = sorted({n['labels'][0] for n in graph['nodes']})
    types = sorted({r['type'] for r in graph['rels']})
    lines = ['// 적재 — 노드는 id로 같은 대상을 알아보고(MERGE), 값은 처음 만들 때만 넣는다(ON CREATE SET — 다시 적재해도 수정본이 고친 값을 되돌리지 않음). 관계는 양 끝 id와 관계 이름으로 알아본다.']
    for l in labels:
        lines += [f'// 넣을 것: {l}', f'UNWIND $rows AS row MERGE (n:{l} {{id: row.id}}) ON CREATE SET n = row;', '']
    for t in types:
        lines += [f'// 넣을 것: {t}', f'UNWIND $rows AS row MATCH (a {{id: row.a}}), (b {{id: row.b}}) MERGE (a)-[r:{t}]->(b) ON CREATE SET r = row.props;', '']
    return '\n'.join(lines).rstrip() + '\n'


QUERY_INTEGRATED = {
    1: ('// 질문 1 — 설비 하나의 구성 요소별 센서(설비에 바로 붙은 센서는 「(설비 전체)」)',
        "MATCH (a:Asset {id: $asset})-[:HAS_COMPONENT*0..1]->(x)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(q:Quantity)\n"
        "RETURN CASE WHEN x = a THEN '(설비 전체)' ELSE x.id END AS attached_to, s.id AS sensor, s.tag AS tag, s.kind AS kind,\n"
        "       q.name AS quantity, s.unit AS unit, s.normal AS normal, s.limit AS limit, s.limit_direction AS direction\n"
        "ORDER BY attached_to, tag;"),
    2: ('// 질문 2 — 설비 하나의 구성 요소마다 교체 부품(없으면 빈 칸으로 남김)',
        "MATCH (a:Asset {id: $asset})-[:HAS_COMPONENT]->(c:Component)\n"
        "OPTIONAL MATCH (c)-[:USES_PART]->(p:Part)\n"
        "RETURN c.id AS component, c.name AS component_name, p.id AS part, p.name AS part_name\n"
        "ORDER BY component;"),
}
QUERY_PART_USAGE = {
    '상태와 함께': ('// 질문 3 — 품번이나 다른 표기로 부품을 찾고 쓰는 설비 · 구성 요소와 설비 상태(가동이 아닌 설비도 상태와 함께)',
                 "OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])\n"
                 "OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p)\n"
                 "RETURN p.id AS part, a.id AS asset, a.status AS status, c.id AS component,\n"
                 "       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN a IS NULL THEN '쓰는 설비 없음' END AS note\n"
                 "ORDER BY part, asset, component;"),
    '빠짐': ('// 질문 3 — 품번이나 다른 표기로 부품을 찾고 지금 가동하는 설비만',
           "OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])\n"
           "OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p) WHERE a.status = '가동'\n"
           "RETURN p.id AS part, a.id AS asset, a.status AS status, c.id AS component,\n"
           "       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN a IS NULL THEN '가동 설비에서는 쓰지 않음' END AS note\n"
           "ORDER BY part, asset, component;")}
QUERY_PRACTICAL = {
    1: {'ㄱ': ('// 질문 1 — 부품 하나의 사용 설비 · 구성 요소와 공급사마다 공급 조건(승인 상태 · 출처 포함)',
               "OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])\n"
               "OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p)\n"
               "WITH p, collect(DISTINCT a.id) AS assets, collect(DISTINCT c.id) AS components\n"
               "OPTIONAL MATCH (s:Supplier)-[r:SUPPLIES]->(p)\n"
               "RETURN p.id AS part, assets, components, s.name AS supplier, r.approved AS approved, r.approval_status AS approval_status, r.condition AS condition,\n"
               "       r.price_manwon AS price_manwon, r.defect_rate AS defect_rate, r.lead_days AS lead_days,\n"
               "       r.quote_source AS quote_source, r.quote_date AS quote_date, r.approval_source AS approval_source, r.as_of AS as_of\n"
               "ORDER BY supplier;"),
        'ㄴ': ('// 질문 1 — 부품 하나의 사용 설비 · 구성 요소와 공급사마다 공급 조건(승인 상태 · 출처, 구매 기준서 7.4 정보 포함)',
               "OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])\n"
               "OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p)\n"
               "WITH p, collect(DISTINCT a.id) AS assets, collect(DISTINCT c.id) AS components\n"
               "OPTIONAL MATCH (s:Supplier)-[r:SUPPLIES]->(p)\n"
               "RETURN p.id AS part, assets, components, s.name AS supplier, r.approved AS approved, r.approval_status AS approval_status, r.condition AS condition,\n"
               "       r.price_manwon AS price_manwon, r.defect_rate AS defect_rate, r.lead_days AS lead_days,\n"
               "       r.inspection AS inspection, r.compare_extra_manwon AS compare_extra_manwon, r.rule_source AS rule_source,\n"
               "       r.quote_source AS quote_source, r.quote_date AS quote_date, r.approval_source AS approval_source, r.as_of AS as_of\n"
               "ORDER BY supplier;")},
    2: ('// 질문 2 — 정식 품번 · 예전 품번 · 다른 표기로 같은 부품을 찾고, 없는 품번은 한 줄로 알림(비슷한 이름은 합치지 않음)',
        "OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])\n"
        "OPTIONAL MATCH (s:Supplier)-[r:SUPPLIES]->(p)\n"
        "RETURN p.id AS part, CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN p.id = $part THEN '정식 품번' ELSE '다른 표기' END AS found_by,\n"
        "       s.name AS supplier, r.approved AS approved, r.approval_status AS approval_status\n"
        "ORDER BY part, supplier;")}


def query_text(blocks):
    return '\n\n'.join(f'{head}\n{body}' for head, body in blocks) + '\n'
CONFIRM_PART = ("MATCH (c:Component {id: 'HYD-03:pump-a'}), (p:Part {id: 'P-PMP-SEAL'}) MERGE (c)-[u:USES_PART]->(p) SET u.source_text = 'P-PMP-SEAL';\n"
                "MATCH (c:Component {id: 'HYD-03:rtn-filter'})-[u:USES_PART]->(p:Part) WHERE p.id <> 'P-RTN-FLT-25' DELETE u;\n"
                "MATCH (c:Component {id: 'HYD-03:rtn-filter'}), (p:Part {id: 'P-RTN-FLT-25'}) MERGE (c)-[u:USES_PART]->(p) SET u.source_text = 'P-RTN-FLT-25';\n")


UPDATE_INTEGRATED = {
    '남김': ("// 수정본 반영 — 불용 결정 설비는 대장에 남기고 상태로 구별(설비_대장_변경.csv 3줄), 이름 표준화(2줄), 값 보완(센서_변경.csv 2 · 3줄),\n"
            "// 교체부품 확인 · 변경(구성요소_변경.csv 2 · 3줄 — 3줄은 잇는 부품이 바뀌므로 옛 관계를 지우고 새로 잇는다). 센서_변경.csv 4줄 「삭제」는 같은 센서를 점검표에서 옮겨 적은 중복 행 정리라 그래프의 센서는 그대로 둔다.\n"
            "MATCH (a:Asset {id: 'HYD-02'}) SET a.name = 'HYD-02 2라인 2호 파워팩';\n"
            "MATCH (a:Asset {id: 'HYD-07'}) SET a.status = '불용(매각 예정)';\n"
            "MATCH (s:Sensor {id: 'HYD-03:VS1'}) SET s.unit = 'mm/s', s.normal = 0.6;\n"
            "MATCH (s:Sensor {id: 'HYD-06:I_MOTOR'}) SET s.unit = 'A', s.normal = 18.5;\n" + CONFIRM_PART),
    '삭제': ("// 수정본 반영 — 불용 결정 설비는 그 설비에만 딸린 구성 요소 · 실물 · 센서와 함께 지운다(공용 부품 · 물리량은 남김). 나머지는 남김 갈래와 같다.\n"
            "MATCH (a:Asset {id: 'HYD-02'}) SET a.name = 'HYD-02 2라인 2호 파워팩';\n"
            "MATCH (a:Asset {id: 'HYD-07'}) OPTIONAL MATCH (a)-[:HAS_COMPONENT]->(c:Component) OPTIONAL MATCH (c)-[:MONITORED_BY]->(s:Sensor) OPTIONAL MATCH (a)-[:MONITORED_BY]->(s2:Sensor) OPTIONAL MATCH (c)-[:INSTALLED_UNIT]->(u:Unit)\n"
            "WITH a, collect(DISTINCT c) + collect(DISTINCT s) + collect(DISTINCT s2) + collect(DISTINCT u) AS sub FOREACH (x IN sub | DETACH DELETE x) DETACH DELETE a;\n"
            "MATCH (s:Sensor {id: 'HYD-03:VS1'}) SET s.unit = 'mm/s', s.normal = 0.6;\n"
            "MATCH (s:Sensor {id: 'HYD-06:I_MOTOR'}) SET s.unit = 'A', s.normal = 18.5;\n" + CONFIRM_PART)}
