"""2회차 네 랩의 빈 틀과 강사 참조 답 — 강사 참조(build_labs.reference_model 갈래 · data_session2 원자료)에서 만든다. 답은 학생 폴더에 들어가지 않는다.

빈 틀(학생 폴더의 `app/features/`)과 그 갈래별 정답 내용 · 기대 답 표를 돌려준다. 강사 참조 시험(reference/session2_project_trials.py ·
session2_graph_trials.py · practical2_design_trials.py · practical2_graph_trials.py)이 이 내용을 새 랩 사본에 써 넣고 실행해 갈래마다 답을 확인한다.
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
DESIGN_REASON = ' · 근거 = 그 줄을 그렇게 정한 내 이유(정할 때 열어 본 원문 줄이 있으면 파일:줄을 함께)'   # 스키마 표의 근거 칸 뜻(코딩랩 함정 「칸 뜻」)
# 스키마는 학생이 정한 표 세 장이다(클래스 · 속성 · 관계). 칸마다 뜻만 적고 값은 넣지 않는다(K-4).
DESIGN_EXPLAIN = {
    '클래스.csv': '클래스마다 한 줄. 클래스 = 설비 · 구성 요소 · 센서 · 물리량 · 부품(구성 요소 자리와 그 실물을 나눌 때만 실물도) · 의미 = 무엇을 이 클래스의 인스턴스 하나로 세는지 한 문장 · ID_만드는_법 = 식별자를 무엇으로 지을지 — {칸 이름}과 글자를 이은 꼴이고, 칸 이름은 그 클래스의 원자료 표에 있는 칸(구성 요소의 구성요소 칸은 같은 모델의 설비끼리 하나로 맞춘 이름, 물리량은 내가 묶어 정한 이름 「물리량」, 실물은 구성 요소 목록의 칸)' + DESIGN_REASON,
    '속성.csv': '속성마다 한 줄(모델의 id 칸은 클래스 표의 식별자 틀이 지으므로 「id」 줄은 적지 않음 — 식별자 틀에 쓴 원자료 칸도 질문이 묻거나 답으로 보일 값이면 속성으로 따로 담음: 예 설비의 설비코드 · 센서의 태그 · 부품의 품번). 클래스 = 클래스 표의 이름 · 속성 = 모델에 담을 이름(영어 소문자와 밑줄) · 원자료_칸 = 그 값이 오는 원자료 표의 칸 이름(제공 코드가 채워 주는 칸: 구성 요소의 「다른이름」, 부품의 「다른표기」, 물리량의 「물리량」 · 「기준단위」) · 자료형 = 글자 · 수 · 날짜 · 목록(목록은 「다른이름」 · 「다른표기」 칸만) · 필수 = 예(모든 인스턴스에 값이 있어야 함) 또는 아니오(비어도 됨) · 단위 = 센서의 수 속성에만 「기준 단위」(그 센서가 재는 물리량의 기준 단위로 바꿔 담음) 또는 「적힌 그대로」, 그 밖의 줄은 비움' + DESIGN_REASON,
    '관계.csv': '관계마다 한 줄. 관계_이름 = 영어 대문자와 밑줄 · 읽는_말 = 화살표를 「시작 → (읽는 말) → 종료」로 읽을 때의 우리말 · 시작 · 종료 = 클래스 표의 이름(시작 클래스에서 종료 클래스로 화살표를 긋는다) · 카디널리티 = 1:1 · 1:N · N:1 · N:M(시작 쪽 수:종료 쪽 수 — 이어질 수 있는 개수이고, 1은 많아야 하나) · 적어도_하나 = 없음 · 시작마다(시작 클래스의 인스턴스마다 이 관계가 하나는 있어야 함) · 종료마다(종료 클래스의 인스턴스마다) · 양쪽' + DESIGN_REASON,
    '행_처리.csv': '기준일에 달려 있지 않거나 겹친 원자료 행을 어떻게 할지 — 파일(구성요소_목록.csv · 센서_목록.csv · 설비_대장.csv) · 행(편집기 줄 번호) · 처리(빼기 · 지난 실물:<지금 실물 행> — 지난 실물은 구성 요소 자리와 그 실물을 나눌 때 구성요소_목록.csv만)' + DESIGN_REASON,
}
DESIGN_COLUMNS = {'클래스.csv': ['클래스', '의미', 'ID_만드는_법', '근거'], '속성.csv': ['클래스', '속성', '원자료_칸', '자료형', '필수', '단위', '근거'],
                  '관계.csv': ['관계_이름', '읽는_말', '시작', '종료', '카디널리티', '적어도_하나', '근거'], '행_처리.csv': ['파일', '행', '처리', '근거']}
EXPECT_COLUMNS_DESIGN = ['질문', '물을_값', '항목', '기대_답', '근거']
EXPECT_FORMAT = '여러 값은 「 · 」로 잇고, 값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」'   # 2회차 네 랩 기대 답 표의 같은 꼴(결과 화면이 이 꼴로 견줌)
# 기대 답 표의 칸 뜻 — 빈 틀 첫 줄에 싣는다(값은 넣지 않고 꼴과 뜻만 — K-4)
EXPECT_EXPLAIN_DESIGN = ('한 줄 = (질문 · 물을_값 · 항목) 하나. 질문 = 1 · 2 · 3(와 내가 더하는 4). 물을_값 = 질문 1은 설비 코드, 질문 2는 물리량 이름(내가 묶어 정한 이름), 질문 3은 품번이나 표기 — '
                         '설비 코드와 품번은 식별자를 어떻게 지었든 원자료에 적힌 그대로 적음. '
                         '항목 = 질문 1은 구성 요소 이름(그 설비의 원자료에 적힌 이름) 또는 「구성 요소 이름 실물」(그 자리에 달린 장치), 질문 2는 비우거나(그 물리량을 재는 센서 목록) 설비코드:태그(그 센서의 값), '
                         '질문 3은 찾을 사내 품번(물은 표기를 그대로 옮기지 않고 그 표기가 가리키는 사내 품번을 적음. 원자료에 없는 품번이면 비움). '
                         '기대_답 = 질문 1은 센서 태그들 또는 일련번호(실물을 따로 두는 모델이면 「일련번호(지금)」 · 「일련번호(지난)」 꼴), 질문 2는 설비코드:태그들 또는 「단위 · 정상값 · 한계 · 한계구분」 차례의 값(속성 표에서 센서의 수 속성을 「기준 단위」로 정했으면 그 물리량의 기준 단위로 바꾼 값 — 기준 단위는 그 물리량에 묶인 센서 줄이 가장 많이 쓴 단위 — 이고, 「적힌 그대로」면 원자료에 적힌 값), '
                         '질문 3은 쓰는 설비 코드들(원자료에 없는 품번은 「없음」). 근거 = 파일:줄(원자료에 없는 품번은 찾아본 파일 이름만 「data/파일.csv · data/파일.csv에 없음」). '
                         '질문 4 = 세 질문 뒤에 내가 더하는 질문: 물을_값은 「클래스.속성 조건」 꼴(클래스 = 클래스 표의 이름, 속성 = 속성 표에 적은 속성 이름 — 원자료 칸 이름이 아님. 조건 = 「= 값」 · 「> 값」 · 「< 값」 · 없음 · 있음 · 가장 큰 · 가장 작은 · 가장 이른 · 가장 늦은, 여럿이면 「 & 」로 이음), 항목은 답으로 볼 그 클래스의 속성 이름, 기대_답은 그 속성의 값들. ' + EXPECT_FORMAT)

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


MEANING = {'설비': '설비 대장에 올려 한 대씩 관리하는 기계', '구성 요소': '설비를 이루는 기계 하나하나', '센서': '구성 요소에 붙어 값을 재는 계기',
           '물리량': '센서가 재는 것. 같은 것을 재는 센서를 여기에 모은다', '부품': '구성 요소 안에서 닳으면 갈아 끼우는 것. 사내 품번마다 하나이고 다른 표기는 다른 이름으로 남긴다',
           '실물': '구성 요소 자리에 달리는 일련번호가 붙은 기계 한 대'}   # 이론의 클래스 정의(이름과 의미 한 문장)
# 속성 표의 강사 참조 줄: (클래스, 속성, 원자료 칸, 자료형, 필수, 단위, 근거). 한계는 인터록이 없는 센서가 많아 선택이고, 센서의 수는 물리량의 기준 단위로 맞춘다.
PROPERTY_ROWS = [
    ('설비', 'code', '설비코드', '글자', '예', '', '자료/설비_대장.csv:1 — 질문 1 · 3이 설비 코드로 묻고 답함'), ('설비', 'name', '설비명', '글자', '예', '', '자료/설비_대장.csv:1'),
    ('설비', 'model', '모델', '글자', '예', '', '자료/설비_대장.csv:1 — 같은 모델끼리 견줌'), ('설비', 'status', '상태', '글자', '예', '', '자료/설비_대장.csv:1'),
    ('설비', 'maker', '제조사', '글자', '아니오', '', '자료/설비_대장.csv:1'), ('설비', 'serial', '일련번호', '글자', '아니오', '', '자료/설비_대장.csv:1'),
    ('설비', 'functional_location', '기능위치', '글자', '아니오', '', '자료/설비_대장.csv:1'),
    ('구성 요소', 'name', '구성요소', '글자', '예', '', '자료/구성요소_목록.csv:1 — 질문 1의 항목'), ('구성 요소', 'group', '계통', '글자', '예', '', '자료/구성요소_목록.csv:1'),
    ('구성 요소', 'aliases', '다른이름', '목록', '아니오', '', '현장이 섞어 쓰는 이름으로도 찾으려고'),
    ('센서', 'tag', '태그', '글자', '예', '', '자료/센서_목록.csv:1 — 질문 1 · 2의 답'), ('센서', 'name', '센서명', '글자', '아니오', '', '자료/센서_목록.csv:1'),
    ('센서', 'unit', '단위', '글자', '예', '', '자료/센서_목록.csv:1 — 단위 없는 값은 견줄 수 없음'), ('센서', 'normal', '정상값', '수', '아니오', '기준 단위', '자료/센서_목록.csv:1 — 설비끼리 견주려고 기준 단위로'),
    ('센서', 'limit', '한계', '수', '아니오', '기준 단위', '자료/센서_목록.csv:3 — 인터록이 없는 센서는 한계 칸이 비어 있어 필수로 두지 않음'),
    ('센서', 'limit_direction', '한계구분', '글자', '아니오', '', '자료/센서_목록.csv:3 — 한계가 없으면 함께 비어 있음'),
    ('물리량', 'name', '물리량', '글자', '예', '', '질문 2가 이 이름으로 물음'), ('물리량', 'unit', '기준단위', '글자', '아니오', '', '센서 값을 견줄 단위'),
    ('부품', 'part_no', '품번', '글자', '예', '', '자료/예비품_목록.csv:1 — 질문 3의 답'), ('부품', 'name', '품명', '글자', '예', '', '자료/예비품_목록.csv:1'),
    ('부품', 'other_codes', '다른표기', '목록', '아니오', '', '자료/품번_교차표.csv:1 — 예전 품번 · 다른 표기로 물어도 찾으려고')]
UNIT_PROPERTY_ROWS = [('실물', 'serial', '일련번호', '글자', '예', '', '자료/구성요소_목록.csv:1 — 실물 한 대를 가리키는 번호'),
                      ('실물', 'note', '비고', '글자', '아니오', '', '자료/구성요소_목록.csv:1 — 달고 뗀 날짜가 비고에 적혀 있음')]
SEAT_SERIAL_ROW = ('구성 요소', 'serial', '일련번호', '글자', '아니오', '', '자료/구성요소_목록.csv:1 — 지금 달린 장치의 번호. 펌프 줄에만 적혀 있음')
# 둘째 바퀴(세 질문 뒤에 내가 더하는 질문 4): 세 질문에는 필요 없어 처음 스키마에는 없고, 새 질문 때문에 더하는 속성 한 줄
LAP_ROW = ('설비', 'installed', '설치일', '날짜', '아니오', '', '자료/설비_대장.csv:1 — 질문 4가 설치한 앞뒤를 견주므로 날짜')


def lap_question():
    """둘째 바퀴의 질문 4 한 줄(기대 답 표의 줄) — 가동 중인 설비 가운데 가장 먼저 설치한 것. 기대 답은 설비 대장 원자료에서 센다."""
    running = [r for r in B.rows('설비_대장.csv') if r['상태'] == '가동']
    first = min(r['설치일'] for r in running)
    lines = [str(i) for i, r in B.numbered('설비_대장.csv') if r['상태'] == '가동' and r['설치일'] == first]
    return ['4', '설비.status = 가동 & 설비.installed 가장 이른', 'code', ' · '.join(sorted(r['설비코드'] for r in running if r['설치일'] == first)),
            '자료/설비_대장.csv:' + ' · '.join(lines) + ' 설치일 · 상태 칸']


def integrated_design(branch='A', ids=None, properties=None, relations=None, lap=False):
    """통합 02-3 빈 틀의 정답 내용 {경로: 글}. 갈래는 build_labs.POLICY(A · B · C · E). lap = 둘째 바퀴(질문 4)까지 마친 판 — 속성 표에 LAP_ROW가 더해진다.
    ids = 대상마다 식별자 틀을 달리 지은 사본({대상: 틀}, 예 OTHER_IDS) — 식별자를 어떻게 지어도 질문별 대조가 서는지 강사 참조 시험이 본다.
    properties · relations = 속성 표 · 관계 표의 줄을 바꾸는 함수(강사 참조 시험이 다른 선택의 결과를 볼 때)."""
    D.require('통합반')
    made = lambda kind, default: (ids or {}).get(kind, default)
    _, _, unit, scope = B.policy(branch)
    split = unit == '나눔'
    memo = lambda text: f'자료/현장_메모.md:{memo_line(text)}'
    (gone, now, removed), = removed_rows()
    files = {}
    files['결과/클래스.csv'] = csv_text(DESIGN_EXPLAIN['클래스.csv'], DESIGN_COLUMNS['클래스.csv'], [
        ['설비', MEANING['설비'], made('설비', '{설비코드}'), '자료/설비_대장.csv:1 설비코드 칸 — 설비마다 하나'],
        ['구성 요소', MEANING['구성 요소'] + ('가 놓이는 자리' if split else ''), made('구성 요소', '{설비코드}:{구성요소}'), f'{memo("같은 모델(HPP-45A)")} — 같은 모델의 같은 품목이 설비마다 있으므로 설비코드를 붙임'],
        ['센서', MEANING['센서'], made('센서', '{설비코드}:{태그}'), f'{memo("태그 이름(TS1")} — 태그 이름은 HPP-45A · 45B 네 대가 모두 같아 설비코드를 붙임'],
        ['물리량', MEANING['물리량'], made('물리량', '{물리량}'), f'{memo("재는 값의 이름도")} — 재는 값의 이름이 사람마다 달라 묶어 정한 이름 하나를 씀'],
        ['부품', MEANING['부품'], made('부품', '{품번}'), '자료/예비품_목록.csv:1 품번 칸(사내 품번) — 다른 표기는 식별자가 아니라 부품의 다른 이름'],
        *([['실물', MEANING['실물'], made('실물', '{일련번호}'), f'{memo("구성 요소 목록의 일련번호")} — 일련번호는 그 자리에 달린 장치 한 대']] if split else [])])
    rows = [list(r) for r in PROPERTY_ROWS + ([LAP_ROW] if lap else []) + (UNIT_PROPERTY_ROWS if split else [SEAT_SERIAL_ROW])]
    files['결과/속성.csv'] = csv_text(DESIGN_EXPLAIN['속성.csv'], DESIGN_COLUMNS['속성.csv'], properties(rows) if properties else rows)
    rows = [
        ['HAS_COMPONENT', '가진다', '설비', '구성 요소', '1:N', '종료마다', '자료/구성요소_목록.csv:1 — 설비 하나에 구성 요소 여러 줄, 구성 요소는 설비 하나에만 달리고 설비 없는 구성 요소는 없어야 함'],
        ['MONITORED_BY', '감시된다', '구성 요소', '센서', '1:N', '종료마다', '자료/센서_목록.csv:1 붙은곳 칸 — 한 구성 요소에 센서 여럿(센서가 없는 구성 요소도 있음), 센서는 붙은 구성 요소가 꼭 하나'],
        ['OBSERVES', '잰다', '센서', '물리량', 'N:1', '시작마다', '자료/센서_목록.csv:1 재는것 칸 — 센서 하나는 물리량 하나를 재고, 무엇을 재는지 없는 센서는 없어야 함'],
        ['USES_PART', '쓴다', '구성 요소', '부품', 'N:M', '없음', f'{memo("구동 모터는 교체 부품을 따로 두지 않아")} — 구성 요소 하나가 부품을 여럿 쓸 수 있고 한 부품을 여러 구성 요소가 씀. 교체 부품이 없는 구성 요소도 있음'],
        *([['INSTALLED_UNIT', '달고 있다', '구성 요소', '실물', '1:N', '종료마다', f'자료/구성요소_목록.csv:{gone} · {now} — 한 자리에 지금 실물과 지난 실물이 이어지고(일련번호가 없는 자리도 있음), 실물은 달린 자리가 꼭 하나']] if split else [])]
    files['결과/관계.csv'] = csv_text(DESIGN_EXPLAIN['관계.csv'], DESIGN_COLUMNS['관계.csv'], relations(rows) if relations else rows)
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


# ───────────── 실습4(그래프) ─────────────
GRAPH_EXPECT_COLUMNS = ['질문', '물을_값', '볼_열', '기대_답', '근거']
GRAPH_EXPECT_EXPLAIN = {}
GRAPH_EXPECT_EXPLAIN['통합반'] = ('한 줄 = (질문 · 물을_값 · 볼_열) 하나. 같은 값으로 물은 결과의 다른 열도 견주려면 볼_열만 바꾼 줄을 더함. '
                                 '질문 = query.cypher의 「// 질문 N」 번호(역량 질문의 번호). 물을_값 = $ 자리에 넣을 값 하나(질문 1 · 2는 설비 코드, 질문 3은 품번이나 표기). '
                                 '볼_열 = 그 쿼리 결과에서 견줄 열 이름 하나, 또는 결과 줄마다 두 열을 짝지어 견줄 때 「열+열」. 기대_답 = 그 열의 값들(결과 줄마다 하나, 줄 순서는 보지 않음) — 「열+열」 줄은 줄마다 「값=값」. '
                                 '근거 = 파일:줄(원자료에 없는 품번은 찾아본 파일 이름만). ' + EXPECT_FORMAT)
# 유일 제약 걸음의 빈 틀(두 반 공용 — 실전반 그래프 랩을 다시 만들 때 그 랩의 빈 틀 목록에 이 줄을 더한다). 식별자 속성 이름과 쿼리 꼴은 적지 않는다(코딩랩 K-4).
CONSTRAINT_FILE = '결과/constraints.cypher'
CONSTRAINT_BLANK = F.blank_text('제약 쿼리 파일 — 종류마다 식별자에 유일 제약을 거는 쿼리들(쿼리 끝 ;). 데이터를 넣는 쿼리는 여기에 쓰지 않습니다(python run.py constraints가 실행).\n'
                                '종류와 그 식별자는 입력/schema.json에 있습니다.', '//')
# 통합반 그래프 랩의 빈 틀 — 이론이 세운 이름 「쿼리」 하나로 부른다(과정 용어 장부). 위 셋은 실전반 랩이 쓴다.
# 통합반 그래프 랩에서 학생이 쓰는 적재 쿼리 셋 — 까닭이 서로 다르다: 설비 노드(원자료 표의 줄에서 식별자로 쓸 열과 열 → 속성 짝을 정한다) ·
# 설비와 구성 요소를 잇는 관계(끝 노드가 먼저 있어야 이어진다 — 쿼리의 차례와 양 끝을 찾는 법) · 구성 요소와 부품을 잇는 관계(관계에 붙는 값). 나머지는 제공 코드가 넣는다(lab_cypher.provided_queries).
STUDENT_LOAD = ('Asset', '설비-구성 요소', '구성 요소-부품')   # 종류(레이블) 이름 또는 두 클래스의 짝(관계 이름은 스키마의 links에서 읽는다 — 내 모델을 쓰면 내가 지은 관계 이름이 된다)
RAW_LOAD = {'Asset': '설비_대장.csv'}                         # 이 종류의 행은 원자료 표의 줄 그대로 넘긴다
ADDITION_COLUMNS = ['클래스', '속성', '자료형', '필수', '근거']
BLANKS_INTEGRATED = {
    CONSTRAINT_FILE: CONSTRAINT_BLANK,
    '결과/load.cypher': F.blank_text('적재 쿼리 파일 — 쿼리마다 바로 위에 「// 넣을 것: <종류 또는 관계>」 한 줄, 행은 $rows로 받음(python show_result.py가 실행).\n'
                                   '여기에 쓰는 것은 셋입니다: Asset 노드, 설비와 구성 요소를 잇는 관계, 구성 요소와 부품을 잇는 관계(관계 이름과 시작 · 종료는 입력/schema.json에 있습니다).\n'
                                   'Asset의 행은 입력/자료/설비_대장.csv의 줄 그대로입니다(열 이름과 값이 모두 글자). 관계의 행은 {a: 시작 쪽 식별자, b: 종료 쪽 식별자, props: 관계에 붙는 값}입니다.\n'
                                   '나머지 종류 · 관계는 제공 코드가 넣고, 실행한 쿼리는 output/load_provided.cypher에 남습니다.', '//'),
    '결과/스키마_추가.csv': F.blank_csv(ADDITION_COLUMNS, '수정본을 반영하면서 스키마에 없던 속성을 그래프에 남기기로 했을 때만 한 줄씩 적습니다(더할 것이 없으면 그대로 둡니다). '
                                     '클래스 = 그 속성을 둘 클래스의 레이블(입력/schema.json의 classes에 있는 이름) · 속성 = 영어 소문자와 밑줄 · 자료형 = 글자 · 수 · 날짜 · 목록 · 필수 = 예 또는 아니오 · '
                                     '근거 = 이 속성을 왜 더하는지(열어 본 수정본 줄이 있으면 파일:줄을 함께)'),
    '결과/query.cypher': F.blank_text('조회 쿼리 파일 — 쿼리마다 바로 위에 「// 질문 <번호>」 한 줄(역량 질문의 번호), 물을 값은 $ 자리 하나로 받고, 쿼리 끝에 ;를 붙임(빠지면 다음 질문이 앞 쿼리에 묻힘).', '//'),
    '결과/update.cypher': F.blank_text('수정 쿼리 파일 — 쿼리마다 바로 위에 「// 반영할 것: <수정본 파일 이름> <변경>」 한 줄(변경 = 그 파일 「변경」 칸의 값). 그 파일에서 변경 칸이 그 값인 줄이 $rows로 넘어옴(쿼리 끝 ;).\n'
                                     '줄의 열 이름과 값은 수정본에 적힌 그대로이고 값은 모두 글자입니다. 전체를 지우는 쿼리는 실행되지 않습니다.', '//')}


def constraint_answer(schema):
    """모델의 종류마다 식별자(id)에 유일 제약을 건다 — 이미 있으면 그대로 둔다(IF NOT EXISTS). 두 반 공용."""
    lines = ['// 유일 제약 — 종류(레이블)마다 식별자 id가 겹치는 노드를 저장할 때 DB가 막는다. 이미 걸려 있으면 그대로 둔다(IF NOT EXISTS).']
    lines += [f'CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE;' for label in sorted(schema['classes'])]
    return '\n'.join(lines) + '\n'


def schema_names(schema):
    """참조 답이 쓰는 이름을 스키마에서 읽는다 — rel(두 클래스의 짝) = 관계 이름, prop(레이블, 원자료 칸) = 그 칸을 담은 속성 이름, arrow(짝, 앞 변수, 뒤 변수) = 그은 방향대로 적은 패턴 조각.
    설계 실습의 모델 꼴(links · source · identity)을 읽으므로, 식별자와 이름을 다르게 지은 내 모델에서도 같은 답이 선다."""
    rel = lambda link: schema['links'][link]
    prop = lambda label, column: next(p for p, c in schema['classes'][label]['source'].items() if c == column)

    def arrow(link, a, b, first):
        """first = 앞 변수의 레이블. 화살표를 그 반대로 그은 스키마면 머리를 반대로 적는다."""
        name = rel(link)
        return f'({a})-[:{name}]->({b})' if schema['relations'][name]['from'] == first else f'({a})<-[:{name}]-({b})'
    return rel, prop, arrow


def id_expr(template, columns=None, row='row'):
    """식별자 틀(「{설비코드}:{태그}」)을 Cypher 식으로 — row.설비코드 + ':' + row.태그. columns = 틀의 칸 이름 → 넘어오는 줄의 열 이름(다를 때만)."""
    out = []
    for piece in re.split(r'(\{[^}]*\})', template):
        if piece.startswith('{'):
            out.append(f'{row}.{(columns or {}).get(piece[1:-1], piece[1:-1])}')
        elif piece:
            out.append("'" + piece + "'")
    return ' + '.join(out)


def load_student_answer(schema):
    """통합반 그래프 랩에서 학생이 쓰는 적재 쿼리 셋(STUDENT_LOAD)의 참조 답 — 설비 노드는 원자료 표의 줄에서(식별자 틀과 속성 → 원자료 칸 짝은 스키마에서), 관계 둘은 양 끝을 레이블과 식별자로 찾아 잇는다."""
    rel, prop, _ = schema_names(schema)
    sets = ', '.join(f'n.{p} = row.{c}' for p, c in schema['classes']['Asset']['source'].items())
    lines = ['// 내 적재 쿼리 — 설비는 원자료 표의 줄을 스키마대로 옮기고(식별자로 같은 대상을 알아보는 MERGE, 값은 처음 만들 때만), 관계는 양 끝을 레이블과 식별자로 찾아 잇는다.',
             '// 넣을 것: Asset', f"UNWIND $rows AS row MERGE (n:Asset {{id: {id_expr(schema['identity']['Asset'])}}}) ON CREATE SET {sets};", '']
    for link, more in (('설비-구성 요소', ''), ('구성 요소-부품', ' ON CREATE SET r.source_text = row.props.source_text')):
        name = rel(link)
        spec = schema['relations'][name]
        lines += [f'// 넣을 것: {name}', f"UNWIND $rows AS row MATCH (a:{spec['from']} {{id: row.a}}), (b:{spec['to']} {{id: row.b}}) MERGE (a)-[r:{name}]->(b){more};", '']
    return '\n'.join(lines).rstrip() + '\n'


def query_integrated(schema, status=False):
    """통합반 그래프 랩 조회 쿼리 셋의 참조 답 {번호: (머리 주석, 쿼리)}. 물을 값은 설비 코드 · 품번(식별자를 어떻게 지었든 그 값을 담은 속성으로 찾는다).
    status = 목록에서 빠진 센서를 상태로 남기는 갈래에서 수정본 반영 뒤: 질문 1이 센서의 상태도 돌려준다."""
    rel, prop, arrow = schema_names(schema)
    code, astatus, cname = prop('Asset', '설비코드'), prop('Asset', '상태'), prop('Component', '구성요소')
    tag, unit, normal, limit, direction = (prop('Sensor', c) for c in ('태그', '단위', '정상값', '한계', '한계구분'))
    qname, no, pname, other = prop('Quantity', '물리량'), prop('Part', '품번'), prop('Part', '품명'), prop('Part', '다른표기')
    has, mon, obs, uses = (lambda a, b, f: arrow('설비-구성 요소', a, b, f)), (lambda a, b, f: arrow('구성 요소-센서', a, b, f)), (lambda a, b, f: arrow('센서-물리량', a, b, f)), (lambda a, b, f: arrow('구성 요소-부품', a, b, f))
    chain = has(f'a:Asset {{{code}: $asset}}', 'c:Component', 'Asset') + mon('', 's:Sensor', 'Component')[2:] + obs('', 'q:Quantity', 'Sensor')[2:]
    return {
        1: ('// 질문 1 — 설비 하나의 구성 요소별 센서',
            f"MATCH {chain}\n"
            f"RETURN c.{cname} AS component, s.{tag} AS tag, q.{qname} AS quantity,\n"
            f"       s.{unit} AS unit, s.{normal} AS normal, s.{limit} AS limit, s.{direction} AS direction" + (', s.status AS status' if status else '') + "\n"
            "ORDER BY component, tag;"),
        2: ('// 질문 2 — 설비 하나의 구성 요소마다 교체 부품(없으면 빈 칸으로 남김)',
            f"MATCH {has(f'a:Asset {{{code}: $asset}}', 'c:Component', 'Asset')}\n"
            f"OPTIONAL MATCH {uses('c', 'p:Part', 'Component')}\n"
            f"RETURN c.{cname} AS component, p.{no} AS part, p.{pname} AS part_name\n"
            "ORDER BY component;"),
        3: ('// 질문 3 — 품번이나 다른 표기로 부품을 찾고 쓰는 설비 · 구성 요소와 설비 상태',
            f"OPTIONAL MATCH (p:Part) WHERE p.{no} = $part OR $part IN coalesce(p.{other}, [])\n"
            f"OPTIONAL MATCH {has('a:Asset', 'c:Component', 'Asset')[:-1]}){uses('', 'p', 'Component')[2:]}\n"
            f"RETURN p.{no} AS part, a.{code} AS asset, a.{astatus} AS status, c.{cname} AS component,\n"
            "       CASE WHEN p IS NULL THEN '원자료에 없는 품번' WHEN a IS NULL THEN '쓰는 설비 없음' END AS note\n"
            "ORDER BY part, asset, component;"),
    }


def query_text(blocks):
    return '\n\n'.join(f'{head}\n{body}' for head, body in blocks) + '\n'


SENSOR_KEPT = '떼어 냄'      # 목록에서 빠진 센서를 상태로 남기는 갈래가 그 센서에 적는 상태 값


def addition_answer(change):
    """스키마에 더할 속성 표(결과/스키마_추가.csv)의 참조 답 — 센서를 상태로 남기는 갈래만 센서에 상태 속성 한 줄을 더한다(설비의 상태는 스키마에 이미 있다)."""
    rows = [['Sensor', 'status', '글자', '아니오', '떼어 낸 센서를 지우지 않고 남기려면 그 상태를 적을 자리가 있어야 해서 — 입력/자료_변경분/' + D.CHANGE_DATE + '_수정본/센서_변경.csv:3']] if change == '남김' else []
    return csv_text(BLANKS_INTEGRATED['결과/스키마_추가.csv'].split('\n', 1)[0].removeprefix(f'# {F.MARK} — '), ADDITION_COLUMNS, rows)


def update_integrated(change, schema, course='통합반'):
    """통합반 수정본(D.changes — 추가 · 수정 · 삭제가 섞여 온다)을 반영하는 수정 쿼리. 줄은 수정본의 열 이름 그대로 $rows로 받고, 대상은 스키마의 식별자 틀대로 지은 식별자로 찾는다.
    change = 남김(불용 설비와 목록에서 빠진 센서를 상태로 남김) · 삭제(불용 설비는 그 설비에만 딸린 대상과 함께, 빠진 센서는 그 노드를 지움)."""
    D.require(course)      # 수정본은 두 과정이 같은 다섯 줄이다(data_session2.changes) — 표의 열만 그 과정 규모의 것
    if change not in ('남김', '삭제'):
        raise ValueError(f'수정본 갈래 {change!r} — 남김 · 삭제 가운데 하나입니다.')
    rel, prop, arrow = schema_names(schema)
    ident = schema['identity']
    a_id, s_id, p_id = id_expr(ident['Asset']), id_expr(ident['Sensor']), id_expr(ident['Part'], {'품번': '사내품번'})
    asset = ('// 반영할 것: 설비_대장_변경.csv 수정\n'
             f"UNWIND $rows AS row MATCH (a:Asset {{id: {a_id}}}) SET a.{prop('Asset', '설비명')} = row.설비명, a.{prop('Asset', '상태')} = row.상태;\n")
    if change == '삭제':
        unit = f" OPTIONAL MATCH {arrow('구성 요소-실물', 'c', 'u:Unit', 'Component')}" if '구성 요소-실물' in schema['links'] else ''
        asset += ('\n// 반영할 것: 설비_대장_변경.csv 수정\n'
                  f"UNWIND $rows AS row MATCH (a:Asset {{id: {a_id}}}) WHERE row.상태 STARTS WITH '불용'\n"
                  f"OPTIONAL MATCH {arrow('설비-구성 요소', 'a', 'c:Component', 'Asset')} OPTIONAL MATCH {arrow('구성 요소-센서', 'c', 's:Sensor', 'Component')}{unit}\n"
                  'WITH a, collect(DISTINCT c) + collect(DISTINCT s)' + (' + collect(DISTINCT u)' if unit else '') + ' AS sub FOREACH (x IN sub | DETACH DELETE x) DETACH DELETE a;\n')
    sensor = ('\n// 반영할 것: 센서_변경.csv 수정\n'
              f"UNWIND $rows AS row MATCH (s:Sensor {{id: {s_id}}}) SET s.{prop('Sensor', '정상값')} = toFloat(row.정상값), s.{prop('Sensor', '한계')} = toFloat(row.한계);\n"
              '\n// 반영할 것: 센서_변경.csv 삭제\n'
              f"UNWIND $rows AS row MATCH (s:Sensor {{id: {s_id}}}) "
              + (f"SET s.status = '{SENSOR_KEPT}';\n" if change == '남김' else 'DETACH DELETE s;\n'))
    other = prop('Part', '다른표기')
    alias = ('\n// 반영할 것: 품번_교차표_변경.csv 추가\n'
             f'UNWIND $rows AS row MATCH (p:Part {{id: {p_id}}}) WHERE NOT row.다른표기 IN coalesce(p.{other}, [])\n'
             f'SET p.{other} = coalesce(p.{other}, []) + row.다른표기;\n')
    head = ('// 수정본 반영 — 줄은 수정본의 열 이름 그대로 받아 식별자로 찾고, 바뀐 값만 고친다. 불용 설비와 목록에서 빠진 센서는 '
            + ('그래프에 남겨 상태로 구별한다.\n' if change == '남김' else '지운다(불용 설비는 그 설비에만 딸린 구성 요소 · 실물 · 센서와 함께, 공용 부품 · 물리량은 남김).\n'))
    return head + asset + sensor + alias
