"""2회차 네 랩의 빈 틀과 강사 참조 답 — 강사 참조(build_labs.reference_model 갈래 · data_session2 원자료)에서 만든다. 답은 학생 폴더에 들어가지 않는다.

빈 틀(학생 폴더의 `app/features/`)과 그 갈래별 정답 내용 · 기대 답 표를 돌려준다. 강사 참조 시험(reference/session2_project_trials.py ·
session2_graph_trials.py · practical2_project_trials.py)이 이 내용을 새 랩 사본에 써 넣고 실행해 갈래마다 답을 확인한다.
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


# ───────────── 통합 02-3(실습 랩 규모) ─────────────
DESIGN_REASON = ' · 근거 = 그 줄을 그렇게 정한 내 이유(정할 때 열어 본 원문 줄이 있으면 파일:줄을 함께)'   # 세 틀의 근거 칸 뜻(코딩랩 함정 「칸 뜻」)
DESIGN_EXPLAIN = {
    '설계.csv': '대상(설비 · 구성 요소 · 센서 · 물리량 · 부품, 구성 요소 자리와 그 실물을 나눌 때만 실물)마다 식별자를 무엇으로 지을지 — {열 이름}과 글자를 이은 꼴. 쓸 수 있는 열: 설비 = 설비코드 · 모델 · 기능위치 · 일련번호 / 구성 요소 = 설비코드 · 구성요소(같은 모델의 설비끼리 하나로 맞춘 이름) · 계통 / 센서 = 설비코드 · 태그 / 물리량 = 물리량(같은 물리량끼리 묶어 정한 이름) / 부품 = 품번 / 실물 = 설비코드 · 구성요소 · 일련번호' + DESIGN_REASON,
    '관계.csv': '연결(설비-구성 요소 · 구성 요소-센서 · 센서-물리량 · 구성 요소-부품, 구성 요소 자리와 그 실물을 나눌 때만 구성 요소-실물)마다 관계 이름(영어 대문자) · 시작(그 연결의 두 대상 가운데 하나) · 카디널리티(1:1 · 1:N · N:1 · N:M — 시작 쪽 수:끝 쪽 수, 1은 많아야 하나)' + DESIGN_REASON,
    '행_처리.csv': '기준일에 달려 있지 않거나 겹친 원자료 행을 어떻게 할지 — 파일(구성요소_목록.csv · 센서_목록.csv · 설비_대장.csv) · 행(편집기 줄 번호) · 처리(빼기 · 지난 실물:<지금 실물 행> — 지난 실물은 구성 요소 자리와 그 실물을 나눌 때 구성요소_목록.csv만)' + DESIGN_REASON,
}
DESIGN_COLUMNS = {'설계.csv': ['대상', 'ID_만드는_법', '근거'], '관계.csv': ['연결', '관계_이름', '시작', '카디널리티', '근거'], '행_처리.csv': ['파일', '행', '처리', '근거']}
EXPECT_COLUMNS_DESIGN = ['질문', '물을_값', '항목', '기대_답', '근거']
EXPECT_FORMAT = '여러 값은 「 · 」로 잇고, 값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」'   # 2회차 네 랩 기대 답 표의 같은 꼴(결과 화면이 이 꼴로 견줌)
# 기대 답 표의 칸 뜻 — 빈 틀 첫 줄에 싣는다(값은 넣지 않고 꼴과 뜻만 — K-4)
EXPECT_EXPLAIN_DESIGN = ('한 줄 = (질문 · 물을_값 · 항목) 하나. 질문 = 1 · 2 · 3. 물을_값 = 질문 1은 설비 코드, 질문 2는 물리량 이름(내가 묶어 정한 이름), 질문 3은 품번이나 표기 — '
                         '설비 코드와 품번은 식별자를 어떻게 지었든 원자료에 적힌 그대로 적음. '
                         '항목 = 질문 1은 구성 요소 이름(그 설비의 원자료에 적힌 이름) 또는 「구성 요소 이름 실물」(그 자리에 달린 장치), 질문 2는 비우거나(그 물리량을 재는 센서 목록) 설비코드:태그(그 센서의 값), '
                         '질문 3은 찾을 사내 품번(물은 표기를 그대로 옮기지 않고 그 표기가 가리키는 사내 품번을 적음. 원자료에 없는 품번이면 비움). '
                         '기대_답 = 질문 1은 센서 태그들 또는 일련번호(실물을 따로 두는 모델이면 「일련번호(지금)」 · 「일련번호(지난)」 꼴), 질문 2는 설비코드:태그들 또는 「단위 · 정상값 · 한계 · 한계구분」 차례의 값(물리량의 기준 단위로 맞춘 값 — 기준 단위는 그 물리량에 묶인 센서 줄이 가장 많이 쓴 단위이고, 다른 단위로 적힌 줄은 그 단위로 바꾼 값을 적음), '
                         '질문 3은 쓰는 설비 코드들(원자료에 없는 품번은 「없음」). 근거 = 파일:줄(원자료에 없는 품번은 찾아본 파일 이름만 「data/파일.csv · data/파일.csv에 없음」). ' + EXPECT_FORMAT)

QUANTITY_RULES_BLANK = f"""# {F.MARK} — 같은 물리량을 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_quantity(a, b):
    \"\"\"센서 행 두 개(a, b)를 같은 물리량을 재는 것으로 볼지. 제공 코드가 모든 짝에 부르고, True인 짝끼리 이어 한 묶음으로 만든다.
    a, b = {{'설비코드', '태그', '센서명', '재는것', '단위', '붙은곳'(센서가 붙은 구성 요소의 이름 — 같은 모델의 설비끼리는 하나로 맞춘 이름), '계통'(그 구성 요소의 계통), '줄'(센서_목록.csv:<행>)}}.
    돌려줄 것: True 또는 False.\"\"\"
    raise NotImplementedError


def quantity_name(members):
    \"\"\"한 묶음의 센서 행들(위와 같은 dict, 센서 목록 차례)에 쓸 물리량 이름 하나. 서로 다른 묶음에는 다른 이름을 줍니다. 돌려줄 것: 이름(str).\"\"\"
    raise NotImplementedError
"""


def memo_line(text):
    """현장 메모에서 text가 든 줄 번호(편집기 줄). 없으면 멈춘다."""
    hits = [i for i, x in enumerate(D.memo().splitlines(), 1) if text in x]
    if len(hits) != 1:
        raise ValueError(f'현장 메모에서 「{text}」 줄을 하나로 찾지 못함: {hits}')
    return hits[0]


def quantity_rules_answer(scope='종류'):
    """같은 물리량의 범위 — '종류'(재는 값의 종류: 작동유의 온도 · 압력 · 유량은 어디에 붙었든 종류마다 하나. 어디서 쟀는지는 센서 이름과 붙은 구성 요소로 읽는다 —
    쿨러에는 유온과 쿨러 출구 유온 센서가 함께 붙어 있어 구성 요소만으로는 가려지지 않는다) ·
    '자리'(붙은 자리까지 같아야 — 같은 종류이고 태그가 같은 센서끼리, 태그가 없는 현장 지시계는 같은 종류 · 같은 계통의 센서와)."""
    head = f'# {F.MARK} — 같은 물리량을 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.\n'
    common = f'''

def value_kind(row):
    """재는 값의 종류(무엇의 어떤 값) — 재는것 이름에 든 말로 가른다. 작동유의 온도 · 압력 · 유량과, 따로 재는 냉각수 유량
    (현장 메모 {memo_line('냉각수 유량을 잽니다')}행) · 필터 차압 · 진동은 다른 종류다."""
    what = row['재는것']
    for word, kind in (('냉각수', '냉각수 유량'), ('차압', '차압'), ('온도', '작동유 온도'), ('유온', '작동유 온도'),
                       ('압력', '작동유 압력'), ('유량', '작동유 유량'), ('진동', '진동')):
        if word in what:
            return kind
    return what


def common_name(members):
    """묶음에서 가장 많이 쓴 재는것(같은 수면 센서 목록에서 먼저 나온 것)."""
    names = [m['재는것'] for m in members]
    return max(names, key=lambda n: (names.count(n), -names.index(n)))
'''
    if scope == '종류':
        return head + common + '''

def same_quantity(a, b):
    """근거: 재는 값의 종류가 같으면 같은 물리량 — 어디서 쟀는지는 센서 이름과 센서가 붙은 구성 요소(붙은곳)로 따로 읽는다."""
    return value_kind(a) == value_kind(b)


def quantity_name(members):
    """근거: 묶음의 재는 값의 종류를 그대로 이름으로 — 서로 다른 묶음은 종류가 달라 이름도 다르다."""
    return value_kind(members[0])
'''
    return head + common + f'''

def local_gauge(row):
    """통신 없이 손으로 읽는 현장 지시계 — SCADA 태그가 없다(현장 메모 {memo_line('현장 지시계는 SCADA 태그가 없어')}행)."""
    return '현장 지시' in row['센서명']


def same_quantity(a, b):
    """근거: 붙은 자리까지 같아야 같은 물리량. HPP-45A · 45B는 같은 자리의 센서에 같은 태그를 쓰므로(현장 메모 {memo_line('태그 이름(TS1')}행)
    종류와 태그가 같으면 같은 자리다(HYD-04의 FS2는 태그가 같아도 냉각수 유량이라 다르다). 태그가 없는 현장 지시계는 종류와 붙은 구성 요소의 계통이
    같은 센서와 같은 자리로 본다(탱크의 유온계는 탱크 유온, 펌프의 압력계는 토출 압력)."""
    if value_kind(a) != value_kind(b):
        return False
    if local_gauge(a) == local_gauge(b):
        return a['태그'] == b['태그']
    return a['계통'] == b['계통']


def quantity_name(members):
    """근거: 묶음에서 가장 많이 쓴 재는것 — 붙은 자리를 가리키는 이름(유온 · 쿨러 출구 유온 · 탱크 유온)."""
    return common_name(members)
'''


def removed_rows():
    """구성요소_목록.csv에서 철거된 실물 줄과 그 자리에 지금 달린 실물 줄 [(철거 줄, 지금 줄, 행)]."""
    comps = B.numbered('구성요소_목록.csv')
    return [(i, next(j for j, x in comps if (x['설비코드'], x['구성요소']) == (c['설비코드'], c['구성요소']) and '철거' not in x['비고']), c) for i, c in comps if '철거' in c['비고']]


OTHER_IDS = {'설비': 'EQ-{설비코드}', '구성 요소': 'EQ-{설비코드}/{구성요소}', '센서': '{태그}@{설비코드}', '물리량': 'Q-{물리량}', '부품': 'PART-{품번}', '실물': 'SN-{일련번호}'}


def integrated_design(branch='A', ids=None):
    """통합 02-3 빈 틀의 정답 내용 {경로: 글}. 갈래는 build_labs.POLICY(A · B · C · E).
    ids = 대상마다 식별자 틀을 달리 지은 사본({대상: 틀}, 예 OTHER_IDS) — 식별자를 어떻게 지어도 질문별 대조가 서는지 강사 참조 시험이 본다."""
    D.require('통합반')
    made = lambda kind, default: (ids or {}).get(kind, default)
    _, _, unit, scope = B.policy(branch)
    split = unit == '나눔'
    memo = lambda text: f'자료/현장_메모.md:{memo_line(text)}'
    (gone, now, removed), = removed_rows()
    files = {}
    files['결과/설계.csv'] = csv_text(DESIGN_EXPLAIN['설계.csv'], DESIGN_COLUMNS['설계.csv'], [
        ['설비', made('설비', '{설비코드}'), '자료/설비_대장.csv:1 설비코드 칸 — 설비마다 하나'],
        ['구성 요소', made('구성 요소', '{설비코드}:{구성요소}'), f'{memo("같은 모델(HPP-45A)")} — 같은 모델의 같은 품목이 설비마다 있으므로 설비코드를 붙임'],
        ['센서', made('센서', '{설비코드}:{태그}'), f'{memo("태그 이름(TS1")} — 태그 이름은 HPP-45A · 45B 네 대가 모두 같아 설비코드를 붙임'],
        ['물리량', made('물리량', '{물리량}'), f'{memo("재는 값의 이름도")} — 재는 값의 이름이 사람마다 달라 묶어 정한 이름 하나를 씀'],
        ['부품', made('부품', '{품번}'), '자료/예비품_목록.csv:1 품번 칸(사내 품번) — 다른 표기는 식별자가 아니라 부품의 다른 이름'],
        *([['실물', made('실물', '{일련번호}'), f'{memo("구성 요소 목록의 일련번호")} — 일련번호는 그 자리에 달린 장치 한 대']] if split else [])])
    files['결과/관계.csv'] = csv_text(DESIGN_EXPLAIN['관계.csv'], DESIGN_COLUMNS['관계.csv'], [
        ['설비-구성 요소', 'HAS_COMPONENT', '설비', '1:N', '자료/구성요소_목록.csv:1 — 설비마다 구성 요소 여러 줄, 한 줄은 설비 하나'],
        ['구성 요소-센서', 'MONITORED_BY', '구성 요소', '1:N', '자료/센서_목록.csv:1 붙은곳 칸 — 한 구성 요소에 센서 여럿, 센서 하나는 한 구성 요소'],
        ['센서-물리량', 'OBSERVES', '센서', 'N:1', '자료/센서_목록.csv:1 재는것 칸 — 센서 하나는 물리량 하나를 잰다'],
        ['구성 요소-부품', 'USES_PART', '구성 요소', 'N:1', '자료/구성요소_목록.csv:1 교체부품 칸 — 한 구성 요소에 칸 하나, 한 부품을 여러 구성 요소가 씀'],
        *([['구성 요소-실물', 'INSTALLED_UNIT', '구성 요소', '1:N', f'자료/구성요소_목록.csv:{gone} · {now} — 한 구성 요소 자리에 지금 실물과 지난 실물']] if split else [])])
    files['결과/행_처리.csv'] = csv_text(DESIGN_EXPLAIN['행_처리.csv'], DESIGN_COLUMNS['행_처리.csv'], [
        ['구성요소_목록.csv', gone, f'지난 실물:{now}' if split else '빼기',
         f'자료/구성요소_목록.csv:{gone} 비고 「{removed["비고"]}」 · {now}행 「교체 설치」' + (' — 그 자리의 지난 실물' if split else ' — 기준일에 달려 있지 않은 실물')]])
    files['결과/quantity_rules.py'] = quantity_rules_answer(scope)
    return files


def integrated_chosen(branch='A'):
    """결정 지점 둘의 정한_것.csv 행(빈 틀의 지점 줄과 같은 이름 · 차례). 갈래는 build_labs.POLICY."""
    D.require('통합반')
    _, _, unit, scope = B.policy(branch)
    (gone, now, removed), = removed_rows()
    code, key, old_serial, _ = D.REMOVED_PUMP
    new_serial = D.SERIALS[(code, key)]
    import verify_reference as V
    sline = {(x['설비코드'], x['태그']): i for i, x in B.numbered('센서_목록.csv')}
    temps = sorted(i for (c, tag), i in sline.items() if c == 'HYD-01' and tag.startswith('TS'))
    t = D.TRUTH['assets']['HYD-01']['sensors']
    members = V.expected('통합반', branch)['quantity_members']
    tank = [s for s in members.get('quantity:TS3', []) if not s.endswith(':TS3')]          # 붙은 자리까지 갈래에서 탱크 유온에 함께 드는 현장 지시계
    # 근거 칸 = 내 이유와, 그 결정을 좌우해 열어 본 원문 줄(lab_frame.CHOSEN_TEMPLATE)
    place = [['구성 요소 자리와 그 실물', '나눔(일련번호가 붙은 실물을 따로 두고 철거된 실물을 남김)' if unit == '나눔' else '한 대상(일련번호는 구성 요소의 속성)',
              ('떼어 낸 펌프도 일련번호가 붙은 장치 한 대라 그 자리를 거쳐 간 장치를 물을 수 있게 하려고' if unit == '나눔' else
               '보전팀이 묻는 것은 지금 달린 펌프라 모델을 단순하게 두려고')
              + f' — 자료/구성요소_목록.csv:{gone} · {now} · 자료/현장_메모.md:{memo_line("구성 요소 목록의 일련번호")}',
              (f'{code} 주 펌프 자리에 {new_serial}(지금)와 {old_serial}(지난)이 실물로 남음 — 보전팀은 떼어 낸 펌프가 수리를 마치고 돌아오면 그 실물의 이력을 이어 봄'
               if unit == '나눔' else f'{code} 주 펌프 구성 요소에 지금 일련번호 {new_serial}만 속성으로 남음 — 떼어 낸 펌프는 이 모델에서 물을 수 없어, 보전팀은 그 이력을 CMMS에서 따로 찾음')]]
    quantity = [['같은 물리량의 범위', '붙은 자리까지 같아야 묶음' if scope == '자리' else '재는 값의 종류로 묶음(어디서 쟀는지는 센서 이름과 붙은 구성 요소로 봄)',
                 ('운전 담당은 같은 자리의 값끼리 정상값과 견주므로' if scope == '자리' else
                  '유온 · 쿨러 출구 유온 · 탱크 유온 모두 작동유의 온도라 한 번에 모아 보고 어디서 쟀는지는 센서 이름과 붙은 구성 요소로 읽으려고')
                 + ' — 자료/센서_목록.csv:' + ' · '.join(map(str, temps)) + f' · 자료/현장_메모.md:{memo_line("태그 이름(TS1")}',
                 (f'유온 · 쿨러 출구 유온 · 탱크 유온이 따로 묶이고 탱크 유온에는 {" · ".join(tank)} 현장 지시계까지 센서 {len(members["quantity:TS3"])}개 — '
                  f'운전은 탱크 유온을 물으면 탱크의 값만 받아 정상값(HPP-45A {t["TS3"]["normal"]:g} ℃)과 바로 견줌' if scope == '자리' else
                  f'작동유 온도 하나에 온도 센서 {len(members["quantity:oil-temp"])}개가 함께 듦 — 운전은 작동유 온도를 한 번에 모아 보되, '
                  f'견줄 정상값(HPP-45A {t["TS1"]["normal"]:g} · {t["TS2"]["normal"]:g} · {t["TS3"]["normal"]:g} ℃)은 센서 이름과 설비 모델을 함께 보고 고름'
                  '(유온과 쿨러 출구 유온은 둘 다 쿨러에 붙어 구성 요소만으로는 가려지지 않음)')]]
    return place + quantity


DECISION_POINTS = ['구성 요소 자리와 그 실물', '같은 물리량의 범위']   # 정한_것.csv 빈 틀에 미리 두는 지점 줄(쓰는 단계 차례)
COMPETENCY_QUESTIONS = ('설비의 구성 요소마다 어떤 센서가 붙고, 그 자리에 어떤 장치(일련번호)가 달렸는가?',
                        '같은 물리량을 재는 센서는 어느 것이고, 각각의 단위 · 정상값 · 한계는 무엇인가?',
                        '부품을 어느 설비가 함께 쓰며, 예전 품번이나 다른 표기로 물어도 찾을 수 있는가?')   # 가이드 03단계와 같은 문장(session2_project_guides)




# ───────────── 실전 02-3 ─────────────
QUOTE_POINT = '기준일에 유효한 견적이 여럿인 쌍'   # 정한_것.csv 지점 줄 — 견적 단계(lab_steps quotes)가 이 줄이 비었으면 멈춘다
QUOTE_RULE_BLANK = f'''# {F.MARK} — 기준일에 쓸 견적을 고르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def use_quote(quotes, as_of):
    """같은 공급사 · 같은 부품의 견적 줄들(공급_조건.csv 행 dict — 원자료 칸 그대로와 '줄' = 편집기 줄 번호)을 받는다. as_of = 자료 기준일('YYYY-MM-DD').
    돌려줄 것: 기준일 조건으로 쓸 줄 하나(받은 dict 그대로) 또는 None(이 쌍은 기준일에 쓸 조건이 없음).
    기준일에 유효한 줄이 둘 이상이면 정한_것.csv 「{QUOTE_POINT}」 줄에 내가 고른 대로 한다(그 줄이 비어 있으면 견적 단계가 멈춘다)."""
    raise NotImplementedError
'''

APPROVAL_RULE_BLANK = f'''# {F.MARK} — 승인과 구매 담당이 함께 볼 것을 담는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def approval(entry, as_of):
    """SCM 승인 목록(승인공급사_목록.csv)의 그 공급사 · 부품 등록(dict — 원자료 칸 그대로와 '줄') 또는 None(등록 없음)을 받는다.
    돌려줄 것: {{'approved': True 또는 False, ...}} — approved 말고 남길 속성(이름은 영어 snake_case)도 이 dict에 함께."""
    raise NotImplementedError


def buyer_info(pair):
    """쌍 하나(공급사 · 부품 · 단가 · 불량률 · 납기 · 승인 결과 등 지금까지 붙은 값의 dict)를 받는다.
    돌려줄 것: 구매 담당이 공급사를 비교할 때 함께 봐야 해서 이 쌍에 더 남길 속성 dict(남길 것이 없으면 {{}}). 이미 있는 속성은 덮어쓰지 않는다.
    pair에 값이 없으면(키가 없거나 None) 0 같은 값으로 채우지 않고, 판단할 수 없는 값으로 다룬다(미확인 · 값 없음 · 0은 서로 다르다)."""
    raise NotImplementedError
'''

def quote_rule_answer(branch='ㄴ'):
    """견적 갈래(build_labs.supply_branch → D.QUOTE_MODES)마다의 use_quote — 기한 지난 줄은 모든 갈래에서 쓰지 않는다."""
    mode = B.supply_branch(branch)[1]
    many = {D.QUOTE_MODES[0]: ('견적일이 가장 늦은 줄(새 견적이 앞 견적을 대신함)', "    return max(live, key=lambda q: q['견적일'])\n"),
            D.QUOTE_MODES[1]: ('견적일이 가장 이른 줄(공급사가 유효기한까지 약속한 조건)', "    return min(live, key=lambda q: q['견적일'])\n"),
            D.QUOTE_MODES[2]: ('쓰지 않음 — 공급사에 어느 견적이 유효한지 확인할 때까지 그 쌍을 비교에서 뺌', '    return None\n')}[mode]
    return f'''# {F.MARK} — 기준일에 쓸 견적을 고르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def use_quote(quotes, as_of):
    """근거: 공급_조건.csv 유효기한 칸 — 기준일에 기한이 지난 견적은 쓰지 않는다. 유효한 줄이 둘 이상이면 정한_것.csv 「{QUOTE_POINT}」대로 {many[0]}."""
    live = [q for q in quotes if q['유효기한'] >= as_of]
    if len(live) <= 1:
        return live[0] if live else None
{many[1]}'''


def approval_rule_answer(branch):
    """A = 조건부 승인도 승인 · 빈 조건은 조건 없음 · 7.4 정보 안 남김(ㄱ), B = 조건부 승인은 비승인, ㄴ = A + 7.4 정보, ㄷ = A + 빈 조건이 7.4에 걸리면 확인 필요. ㄹ · ㅁ은 승인이 ㄴ(견적 갈래만 다름)."""
    branch = B.supply_branch(branch)[0]
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
    branch, mode = B.supply_branch(branch)
    a = 'B' if branch == 'B' else 'A'
    if len(D.TRUTH['several_live']) != 1:
        raise ValueError(f"「{QUOTE_POINT}」 예시 줄은 갈리는 쌍 하나를 짚는다 — 지금 {sorted(D.TRUTH['several_live'])}")
    (sup, pid), lines = next(iter(D.TRUTH['several_live'].items()))
    where = ' · '.join(f'자료/{D.QUOTE_FILE}:{n}' for n in lines)
    v = D.TRUTH['supply_modes'][mode].get((sup, pid))
    quote = [QUOTE_POINT, mode, where, f'{sup} · {pid} ' + (f"{v['quote_date']} 견적(단가 {v['price_manwon']:g} · 납기 {v['lead_days']}일)" if v else '쌍이 빠짐(확인 전까지 비교 제외)')]
    return [quote, ['조건이 붙은 승인', '승인으로 담고 조건을 함께' if a == 'A' else '비승인으로', '자료/승인공급사_목록.csv:10 · 자료/구매기준서_PR-07_발췌.md:24',
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
                                  '기대_답 = 그 열의 값들(결과 줄마다 하나, 줄 순서는 보지 않음). 근거 = 파일:줄(원자료에 없는 품번은 찾아본 파일 이름만). ' + EXPECT_FORMAT)
                        for course, ask in [('통합반', '질문 1 · 2는 설비 코드, 질문 3은 품번이나 표기'), ('실전반', '질문 1 · 2 모두 품번이나 표기')]}
GRAPH_EXPECT_EXPLAIN['통합반'] = ('한 줄 = (질문 · 물을_값) 하나이고, 그 줄에서 견줄 열(볼_열)은 하나. 같은 대상의 다른 열도 견주려면 그 대상을 다른 표기로 물은 줄을 더함. '
                                 '질문 = query.cypher의 「// 질문 N」 번호(역량 질문의 번호). 물을_값 = $ 자리에 넣을 값 하나(질문 1 · 2는 설비 코드, 질문 3은 품번이나 표기). '
                                 '볼_열 = 그 쿼리 결과에서 견줄 열 이름 하나. 기대_답 = 그 열의 값들(결과 줄마다 하나, 줄 순서는 보지 않음). 근거 = 파일:줄(원자료에 없는 품번은 찾아본 파일 이름만). ' + EXPECT_FORMAT)
LOAD_BLANK = F.blank_text('적재 파일 — 문장마다 바로 위에 「// 넣을 것: <종류 또는 관계>」 한 줄, 행은 $rows로 받음(python show_result.py가 실행).\n'
                          '넣을 수 있는 종류 · 관계는 입력/schema.json에 있습니다.', '//')
QUERY_BLANK = F.blank_text('조회 파일 — 조회마다 바로 위에 「// 질문 <번호>」 한 줄, 물을 값은 $ 자리 하나로 받고, 조회 끝에 ;를 붙임(빠지면 다음 질문이 앞 조회에 묻힘).', '//')
UPDATE_BLANK = F.blank_text('수정 파일 — 수정본의 줄을 이미 넣은 그래프에 반영하는 문장들(문장 끝 ;). 전체를 지우는 문장은 실행되지 않습니다.', '//')
# 통합반 그래프 랩의 빈 틀 — 이론이 세운 이름 「쿼리」 하나로 부른다(과정 용어 장부). 위 셋은 실전반 랩이 쓴다.
BLANKS_INTEGRATED = {
    '결과/load.cypher': F.blank_text('적재 쿼리 파일 — 쿼리마다 바로 위에 「// 넣을 것: <종류 또는 관계>」 한 줄, 행은 $rows로 받음(python show_result.py가 실행).\n'
                                   '넣을 수 있는 종류 · 관계는 입력/schema.json에 있습니다.', '//'),
    '결과/query.cypher': F.blank_text('조회 쿼리 파일 — 쿼리마다 바로 위에 「// 질문 <번호>」 한 줄(역량 질문의 번호), 물을 값은 $ 자리 하나로 받고, 쿼리 끝에 ;를 붙임(빠지면 다음 질문이 앞 쿼리에 묻힘).', '//'),
    '결과/update.cypher': F.blank_text('수정 쿼리 파일 — 수정본의 줄을 이미 넣은 그래프에 반영하는 쿼리들(쿼리 끝 ;). 전체를 지우는 쿼리는 실행되지 않습니다.', '//')}


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
    1: ('// 질문 1 — 설비 하나의 구성 요소별 센서',
        "MATCH (a:Asset {id: $asset})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor)-[:OBSERVES]->(q:Quantity)\n"
        "RETURN c.id AS component, s.id AS sensor, s.tag AS tag,\n"
        "       q.name AS quantity, s.unit AS unit, s.normal AS normal, s.limit AS limit, s.limit_direction AS direction\n"
        "ORDER BY component, tag;"),
    2: ('// 질문 2 — 설비 하나의 구성 요소마다 교체 부품(없으면 빈 칸으로 남김)',
        "MATCH (a:Asset {id: $asset})-[:HAS_COMPONENT]->(c:Component)\n"
        "OPTIONAL MATCH (c)-[:USES_PART]->(p:Part)\n"
        "RETURN c.id AS component, c.name AS component_name, p.id AS part, p.name AS part_name\n"
        "ORDER BY component;"),
    3: ('// 질문 3 — 품번이나 다른 표기로 부품을 찾고 쓰는 설비 · 구성 요소와 설비 상태',
        "OPTIONAL MATCH (p:Part) WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])\n"
        "OPTIONAL MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(p)\n"
        "RETURN p.id AS part, a.id AS asset, a.status AS status, c.id AS component,\n"
        "       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN a IS NULL THEN '쓰는 설비 없음' END AS note\n"
        "ORDER BY part, asset, component;"),
}
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


def update_integrated(change):
    """통합반 수정본(D.changes — 이름이 바뀐 설비 하나 · 불용이 된 설비 하나)을 반영하는 수정 쿼리. change = 남김(불용 설비를 상태로 남김) · 삭제(그 설비에만 딸린 대상과 함께 지움)."""
    D.require('통합반')
    (renamed, name), (retired, status) = D.LAB_RENAMED, D.LAB_RETIRED
    head = f"MATCH (a:Asset {{id: '{renamed}'}}) SET a.name = '{name}';\n"
    if change == '남김':
        return ('// 수정본 반영 — 이름이 바뀐 설비는 같은 식별자의 이름만 고치고, 불용 결정 설비는 그래프에 남겨 상태로 구별한다.\n' + head +
                f"MATCH (a:Asset {{id: '{retired}'}}) SET a.status = '{status}';\n")
    if change == '삭제':
        return ('// 수정본 반영 — 이름이 바뀐 설비는 같은 식별자의 이름만 고치고, 불용 결정 설비는 그 설비에만 딸린 구성 요소 · 실물 · 센서와 함께 지운다(공용 부품 · 물리량은 남김).\n' + head +
                f"MATCH (a:Asset {{id: '{retired}'}}) OPTIONAL MATCH (a)-[:HAS_COMPONENT]->(c:Component) OPTIONAL MATCH (c)-[:MONITORED_BY]->(s:Sensor) OPTIONAL MATCH (c)-[:INSTALLED_UNIT]->(u:Unit)\n"
                'WITH a, collect(DISTINCT c) + collect(DISTINCT s) + collect(DISTINCT u) AS sub FOREACH (x IN sub | DETACH DELETE x) DETACH DELETE a;\n')
    raise ValueError(f'수정본 갈래 {change!r} — 남김 · 삭제 가운데 하나입니다.')
