"""강사 참조: 자료 생성 → 2판 추출 → 원문 대조 검토 → 판단 갈래 산출. 학생 배포 금지.

결정은 아래 표에 「종류 + 인용 조각(+ 값 조각)」으로 적었다(후보 id는 추출 함수가 바뀌면 달라지므로 쓰지 않는다).
표의 한 줄이 한 후보에도 맞지 않으면 실패한다(표와 추출 결과가 어긋난 것). 표에 없는 후보는 원문 문장·절·종류·값을
대조해 그대로 채택한 것이다.

판단 갈래(학생이 정할 것, 두 갈래 모두 실행):
  판·상태  A: 현행·보충·참고만 추출(기본)   B: 폐기 1.0판도 추출해 전부 제외하고 판 대응표를 만든다
  언어     EN: 영문 원본을 인용 근거로(기본, 문서 머리말 「뜻이 다르면 영문 원본」)   KO: 사내 번역을 인용 근거로
사용: python review_reference.py
"""
from pathlib import Path
import copy
import csv
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import data_documents as dd  # noqa: E402
import extract_reference as ex  # noqa: E402

REVIEWER = '강사 참조 검토(원문 대조, 2026-10-28)'
REVIEWED_AT = '2026-10-28T00:00:00+09:00'
DIAG = '고장 판정·원인 판별 조건이다. 계약의 precondition(작업 전 확인 조건)과 뜻이 다르고 계약에 맞는 종류가 없어 적재하지 않고 보류한다.'
LIST = '표 칸에 시행 차례가 여럿(예: 2,000 · 6,000 · 10,000 h)인데 단위가 붙은 마지막 값만 추출됐다. 계약의 value 하나로는 차례 목록을 표현할 수 없어 보류한다.'
EQ = '「0 psi/0 bar인지」는 값이 그와 같아야 한다는 뜻이다. 비교 기호를 =로 맞춘다.'

DOCS = {  # 문서 식별자: (파일, 기본 언어)
    'HM-8': ('HM-8_cooler-fan-manual.md', 'ko'),
    'PM-02': ('PM-02_powerpack-pm-checklist.md', 'ko'),
    'PR-07': ('PR-07_spare-parts-standard.md', 'ko'),
    'HI-01': ('HI-01_shift-inspection-supplement.md', 'ko'),
    'OEM-HPP45A-MM': ('OEM-HPP45A-MM_maintenance-excerpt.md', 'en'),
}

# (종류, 인용 조각, 값 조각 또는 None, 결정, 이유, 바꿀 필드 또는 None)
RULES = {
    'HM-8': [
        ('precondition', '베어링 소음과', None, '제외', '베어링 표면 온도 점검 단계이며 작업 전 조건이 아니다. 같은 문장은 단계와 기준값으로 이미 표현된다.', None),
        ('unit_value', '아래 값은 교육용', '80 ℃', '제외', '일반 산업 설비의 경보 수준을 설명한 괄호 문장이다. 이 설비의 기준값이 아니므로 적재하면 근거 없는 기준이 된다.', None),
        ('precondition', '유온이 55 ℃를 넘고', None, '보류', DIAG, None),
        ('unit_value', '이 상태로 두면', '65 ℃', '수정', '같은 절 표의 인터록 칸 「65 ℃ 이상 (설비 정지)」과 같은 기준이다. 「65 ℃에서」는 도달 시점을 말하므로 비교 기호를 >=로 맞춘다.', {'comparator': '>='}),
        ('precondition', '최근 30초', None, '보류', DIAG, None),
        ('precondition', '최근 2분 캐비닛', None, '보류', DIAG, None),
        ('precondition', '최근 2분 팬 진동 VS1 평균이 0.9 mm/s 이상이면', None, '보류', DIAG, None),
        ('precondition', '경보 패턴 COOLER', None, '보류', DIAG, None),
        ('precondition', '현장에서 수동 조작이', None, '제외', '같은 문장이 금지 후보로 이미 있다. 「REMOTE_MANUAL이면」은 금지의 적용 범위이지 실행 전 충족할 조건이 아니다.', None),
        ('precondition', '팬 100 % 연속 운전이', None, '수정', '24시간 제한의 이유를 말하는 제한 문장이다. 실행 전 충족할 조건이 아니라 금지·제한으로 분류한다.', {'kind': 'prohibition'}),
        ('unit_value', '이미 24시간을 넘겼다면', '24시간을 넘', '채택', '「팬 최대 운전 조치」를 추출 함수가 SOP-COOL-11의 이름으로 연결했다. SOP-COOL-12(팬 최대 운전과 부하 80 %)도 팬 100 %를 쓰므로 포함 여부는 원문으로 정해지지 않는다 — 남은 질문.', None),
    ],
    'PM-02': [
        ('unit_value', '1~3호기', '1~3호기', '제외', '적용 설비 범위(호기 번호)이며 기준값이 아니다. 기준값으로 적재하면 근거 없는 기준이 된다.', None),
        ('unit_value', '2,000 · 6,000', None, '보류', LIST, None),
        ('unit_value', '4,000 · 12,000', None, '보류', LIST, None),
        ('unit_value', '8,000 · 16,000', None, '보류', LIST, None),
        ('precondition', '2,200 h를 넘겨', None, '수정', '상한을 넘긴 시행의 결과를 말하는 제한 문장이다. 실행 전 조건이 아니라 금지·제한으로 분류한다.', {'kind': 'prohibition'}),
        ('precondition', 'CMMS는 마지막', None, '보류', 'CMMS가 경보를 내는 조건이며 작업자가 실행 전에 확인할 조건이 아니다. 계약에 맞는 종류가 없어 보류한다.', None),
        ('precondition', '그다음 예정된 정비 시간과', None, '제외', '다음 단계에 쓸 정보를 확인하는 단계이며 조건이 아니다. 단계 후보로 충분하다.', None),
        ('unit_value', '압력계 PS1이 0 bar인지', '0 bar', '수정', EQ, {'comparator': '='}),
        ('precondition', '최근 1분 토출 압력', None, '보류', DIAG, None),
        ('precondition', '최근 1분 유량', None, '보류', DIAG, None),
        ('precondition', '경보 패턴 PUMP_LEAKAGE', None, '보류', DIAG, None),
    ],
    'HI-01': [
        ('prohibition', '인계자 검토와 인수자 확인', None, '제외', '추출 범위를 정하는 문서 관리 문장이며 작업의 금지 사항이 아니다.', None),
        ('precondition', '실제 스키마에서 해당 설비 작업지시', None, '제외', '조회할 필드를 확인하는 단계이며 작업 전 조건이 아니다. 단계 후보로 충분하다.', None),
    ],
    'PR-07': [],
    'OEM-HPP45A-MM': {
        'en': [
            ('precondition', '회사 기준과의 관계', None, '보류', '문서끼리의 우선순위 규칙이다. 다섯 종류 어디에도 맞지 않아 후보로 적재하지 않고 검토 결정(review.decisions)에 반영한다.', None),
            ('unit_value', 'Do not open the circuit until', '0 psi', '수정', EQ, {'comparator': '='}),
            ('unit_value', 'confirm that the gauge reads 0 psi', '0 psi', '수정', EQ, {'comparator': '='}),
            ('unit_value', 'The fluid side must read 0 psi', '0 psi', '수정', EQ, {'comparator': '='}),
            ('precondition', 'Use dry nitrogen only.', None, '수정', '쓸 수 있는 기체를 질소로 제한하는 문장이다. 금지·제한으로 분류한다.', {'kind': 'prohibition'}),
            ('unit_value', 'Fit a new 10 µm element (part no.', '10 µm', '수정', '약어 「no.」에서 문장이 잘려 인용이 단계 문장의 앞부분만 가리켰다. 같은 단계 문장 전체로 인용을 넓힌다.',
             {'quote': 'Fit a new 10 µm element (part no. HI-RF-10) with a new O-ring and tighten the bowl to 35 N·m.'}),
            ('unit_value', 'HI-RF-10) with a new O-ring', '35 N·m', '수정', '약어 「no.」에서 문장이 잘려 인용이 단계 문장의 뒷부분만 가리켰다. 같은 단계 문장 전체로 인용을 넓힌다.',
             {'quote': 'Fit a new 10 µm element (part no. HI-RF-10) with a new O-ring and tighten the bowl to 35 N·m.'}),
            ('unit_value', 'Maximum operating fluid temperature', '158 °F', '제외', '바로 앞 70 °C를 화씨로 옮긴 같은 기준이다. 따로 적재하면 같은 한계가 두 개가 된다.', None),
        ],
        'ko': [
            ('precondition', '회사 기준과의 관계', None, '보류', '문서끼리의 우선순위 규칙이다. 다섯 종류 어디에도 맞지 않아 후보로 적재하지 않고 검토 결정(review.decisions)에 반영한다.', None),
            ('unit_value', '시스템 압력계가 0 psi를', '0 psi', '수정', EQ, {'comparator': '='}),
            ('unit_value', '압력계가 0 psi인지 확인한다', '0 psi', '수정', EQ, {'comparator': '='}),
            ('unit_value', '유압 쪽이 0 psi여야', '0 psi', '수정', EQ, {'comparator': '='}),
            ('unit_value', '작동유 최고 운전 온도', '158 °F', '제외', '바로 앞 70 °C를 화씨로 옮긴 같은 기준이다. 따로 적재하면 같은 한계가 두 개가 된다.', None),
        ],
    },
}

# 원문에 있지만 후보가 없는 것. add=True이면 검토자가 근거 문장으로 후보를 추가한다(origin=reviewer).
MISSING = {
    'HM-8': [
        dict(section='HM-8.7', procedure=None, kind='precondition', quote='원인에 맞는 근본 조치를 CMMS 작업지시로 발행한다.',
             note='근본 조치(SOP-COOL-14·15)는 CMMS 작업지시로 발행한다는 실행 전 조건. 조건 표현이 없는 평서문이라 놓쳤다.', add=True),
        dict(section='HM-8.7', procedure='SOP-COOL-14', kind='precondition', quote='설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.',
             note='핀 세척 1단계의 정지·LOCAL·잠금은 이후 단계의 안전 준비 조건이다. 단계로만 잡혔다.', add=True),
        dict(section='HM-8.1', procedure='SOP-FAN-11', kind='precondition', quote='설비를 정지하고 현장 패널에서 LOCAL로 전환한다.',
             note='팬 점검 1단계의 정지·LOCAL 전환도 같은 기준으로 준비 조건에 추가한다.', add=True),
        dict(section='HM-8.8', procedure=None, kind='precondition', quote='이미 24시간을 넘겼다면 팬 최대 운전 조치는 팬 수명 손실로 20만 원을 감점해서 비교한다.',
             note='「~다면」 조건을 규칙이 읽지 못했다. 「팬 최대 운전 조치」가 SOP-COOL-11만인지 팬 100 %를 쓰는 SOP-COOL-12까지인지 원문이 ID로 정하지 않아 추가하지 않고 남은 질문으로 둔다.', add=False),
    ],
    'PM-02': [
        dict(section='PM-2.6', procedure='SOP-PM-21', kind='precondition', quote='설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.',
             note='2,000 h 점검 1단계의 정지·LOCAL·잠금은 배관 개방 전 안전 준비 조건이다(PM-2.6 머리 문장과 같은 뜻). 단계로만 잡혔다.', add=True),
        dict(section='PM-2.6', procedure='SOP-PM-21', kind='precondition', quote='펌프 모터 전원을 차단하고 어큐뮬레이터 잔압을 탱크로 배출한다.',
             note='잔압 배출은 3단계 배관 개방의 선행 조건이다. 단계로만 잡혔다.', add=True),
        dict(section='PM-2.3', procedure=None, kind='completion', quote='시행 기록에는 패키지, 시행 때의 운전시간, 교체 부품 로트, 시운전 값을 남긴다.',
             note='완료 때 남길 기록 요건인데 완료 표현 목록에 없어 놓쳤다. 지난 시행 기록을 판단하는 근거라 검토자가 추가한다.', add=True),
        dict(section='PM-2.3', procedure=None, kind='precondition', quote='허용 오차 안에서 일찍 시행해도 다음 주기는 시행한 때부터 다시 센다.',
             note='주기 계산 규칙. 다섯 종류 중 맞는 것이 없어 계약 보완이 필요하다.', add=False),
        dict(section='PM-2.6', procedure=None, kind='prohibition', quote='잔압이 남은 유압 회로를 열면 작동유가 분출해 다칠 수 있다.',
             note='금지(배관 개방 금지)의 이유인 위험 문장. 「열면」이 조건 표현 목록에 없다. 금지 후보가 이미 있어 추가하지 않는다.', add=False),
        dict(section='PM-2.1', procedure=None, kind='completion', quote='계수기는 마지막 정기 정비 뒤 운전시간을 세고, 정비를 마치면 0으로 되돌린다.',
             note='완료 후 처리. PM-2.9의 같은 내용은 잡혔다.', add=False),
    ],
    'HI-01': [
        dict(section='HI-1.2', procedure='SOP-HI-02', kind='completion', quote='작업 메모에 정비 완료라고 적혀 있어도 작업지시가 열려 있거나 완료시각이 없으면 불일치 또는 확인 필요로 남긴다.',
             note='정비 완료를 무엇으로 보는지 정하는 기준이다. 조건 후보로만 잡혔고 완료 종류가 없다. 지난 시행 기록 판단에 쓰므로 추가한다.', add=True),
    ],
    'PR-07': [],
    'OEM-HPP45A-MM': {
        'en': [
            dict(section='1', procedure=None, kind='precondition', quote='Allow the fluid to cool below 40 °C before draining.',
                 note='「before」가 소문자라 조건 표현 규칙이 놓쳤다. 값(40 °C)만 남았다.', add=True),
            dict(section='4', procedure='T-4.1', kind='completion', quote='Record the corrected value, the date and the hour meter reading, and set the next check from Section 4.',
                 note='점검 완료 때 남길 기록과 다음 점검 결정. 완료 표현 규칙에 「Record」가 없다.', add=True),
            dict(section='4', procedure=None, kind='precondition', quote='Recharge if the precharge is below 90 % of the nameplate value.',
                 note='문장 가운데의 소문자 「if」를 조건 표현 규칙이 놓쳤다. 값(90 %)만 남았다.', add=True),
            dict(section='2', procedure=None, kind='precondition', quote='Intervals are counted from commissioning or from the last completed service, whichever is later.',
                 note='주기 계산 규칙. 다섯 종류 중 맞는 것이 없다.', add=False),
            dict(section='2', procedure=None, kind='unit_value', quote='Return filter element, 10 µm / 리턴 필터 엘리먼트 10 µm',
                 note='표의 항목 칸(첫 칸)에 적힌 여과 등급 10 µm·125 µm는 추출 규칙이 값 칸만 읽어 놓쳤다. 리턴 필터 10 µm는 T-3.1 4단계에서 잡혔다.', add=False),
        ],
        'ko': [
            dict(section='1', procedure=None, kind='precondition', quote='배유 전에 작동유를 40 °C 아래로 식힌다.',
                 note='「배유 전에」 조건을 규칙이 놓쳤다. 값만 남았다.', add=True),
            dict(section='4', procedure=None, kind='prohibition', quote='건조 질소만 쓴다.',
                 note='제한 문장인데 금지 표현이 없어 놓쳤다.', add=True),
            dict(section='4', procedure='T-4.1', kind='completion', quote='보정한 값과 날짜, 운전시간 계수기 값을 기록하고 4절에 따라 다음 점검을 정한다.',
                 note='점검 완료 때 남길 기록과 다음 점검 결정.', add=True),
            dict(section='2', procedure=None, kind='unit_value', quote='| Return filter element, 10 µm / 리턴 필터 엘리먼트 10 µm | Indicator red, or every 1,000 h or 6 months, whichever comes first / 지시기 적색 또는 1,000 h마다 | Replace / 교체 | 3 |',
                 note='한글 번역 칸에 영문 원본의 「6 months, whichever comes first」가 없다. 한글을 근거로 쓰면 6개월 주기가 사라진다. 문서 머리말에 따라 영문 원본이 우선이므로 남은 질문으로 둔다.', add=False),
        ],
    },
}

DECISIONS_NOTE = {
    'OEM-HPP45A-MM': {'en': ['인용 근거는 영문 원본(EN)으로 한다. 근거: 문서 머리말 「번역은 참고이며 뜻이 다르면 영문 원본을 따른다」.',
                           '이 문서와 PM-02가 같은 항목을 다르게 정하면 PM-02를 따른다(머리말). 같은 항목인지는 카드 단계에서 항목별로 판단한다.'],
                    'ko': ['인용 근거는 사내 번역(KO)으로 한다. 현장 작업자가 읽는 문장과 카드 문장을 맞추기 위해서다.',
                           '번역이 영문 원본과 다른 곳은 missing에 남긴다. 문서 머리말에 따라 그곳은 영문 원본이 우선한다.']},
}
STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}


def matches(c, rule):
    kind, frag, vtext = rule[:3]
    return c['kind'] == kind and frag in c['quote'] and (vtext is None or c.get('value_text') == vtext or vtext in str(c.get('value_text')))


def review(source, rules, missing, selected=None, decisions=None, out_name=None):
    used = [0] * len(rules)
    items = []
    for c in source['candidates']:
        item = copy.deepcopy(c)
        hit = [i for i, r in enumerate(rules) if matches(c, r)]
        if len(hit) > 1:
            raise SystemExit(f'{c["id"]}: 결정 표의 두 줄 이상이 맞음 — 표를 좁히세요 {[rules[i][1] for i in hit]}')
        if hit:
            used[hit[0]] += 1
            _, _, _, decision, reason, change = rules[hit[0]]
        else:
            decision, reason, change = '채택', '원문 문장·절·종류·값을 대조해 일치한다.', None
        if change:
            item['before'] = {k: c.get(k) for k in change}
            item.update(change)
        item.update(decision=decision, status=STATUS[decision], reason=reason, origin='extractor')
        items.append(item)
    unused = [rules[i][1] for i, n in enumerate(used) if n == 0]
    if unused:
        raise SystemExit(f'{source["doc_id"]}: 결정 표의 줄이 어느 후보에도 맞지 않음 {unused}')
    n = len(items)
    for m in missing:
        if not m['add']:
            continue
        n += 1
        items.append({'id': f'{source["doc_id"]}-R{n:03d}', 'doc_id': source['doc_id'], 'section': m['section'], 'procedure': m['procedure'],
                      'kind': m['kind'], 'text': m['quote'], 'quote': m['quote'], 'refs': [], 'status': 'approved',
                      'decision': '채택', 'reason': '검토자 추가: ' + m['note'], 'origin': 'reviewer'})
    out = {k: source[k] for k in ['doc_id', 'source_file', 'source_sha256', 'extractor', 'generated_at']}
    out['review'] = {'reviewer': REVIEWER, 'reviewed_at': REVIEWED_AT, 'candidates_file': out_name or f'{source["doc_id"]}_후보.json',
                     'selected_task': selected, 'decisions': decisions or []}
    out['candidates'] = items
    out['missing'] = [{k: m[k] for k in ['section', 'procedure', 'kind', 'quote', 'note']} | {'added': m['add']} for m in missing]
    return out


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def counts(data):
    out = {}
    for i in data['candidates']:
        out[i['decision']] = out.get(i['decision'], 0) + 1
    return out


def steps_of(md):
    """절차 ID → [(번호, 단계 문장)]. 영한 병기는 한글 줄을 쓴다(판 대응 비교용)."""
    out, proc, pending = {}, None, None
    for line in md.splitlines():
        m = re.match(r'^###\s+(\S+)', line)
        if m:
            proc = m.group(1); out[proc] = []; continue
        if line.startswith('## '):
            proc = None; continue
        s = re.match(r'^(\d+)\.\s+(.*)$', line.strip())
        if proc and s:
            out[proc].append((int(s.group(1)), s.group(2)))
    return out


def edition_map(old_md, new_md):
    """판 대응표: 구판 절차 → 현행 절차. 절차 이름이 같은 것을 짝짓고, 단계 문장이 달라진 수를 함께 남긴다."""
    def titles(md):
        return {m.group(1): m.group(2).strip() for m in re.finditer(r'^###\s+(\S+)\s+(.*)$', md, re.M)}
    def norm(t):
        return re.sub(r'HM-\d+\.\d+에 따라 |HM-\d+\.\d+ 조건을 확인한다|HM-\d+\.\d+|SOP-[A-Z]+-\d+|\s', '', t)
    old_t, new_t = titles(old_md), titles(new_md)
    old_s, new_s = steps_of(old_md), steps_of(new_md)
    rows = []
    for op, title in old_t.items():
        match = [np_ for np_, t in new_t.items() if t == title]
        if not match:
            rows.append([op, title, '', '', '이름이 같은 현행 절차 없음']); continue
        np_ = match[0]
        a = [norm(t) for _, t in old_s[op]]; b = [norm(t) for _, t in new_s[np_]]
        changed = len(set(a) ^ set(b))
        rows.append([op, title, np_, f'1.0판 {len(a)}단계 · 1.1판 {len(b)}단계 · 양쪽에서 짝 없는 단계 문장 {changed}개', '절차 이름 같음'])
    return rows


def main():
    dd.write_all(HERE, dd.ALL, records=True)
    src = HERE / '자료/원문'
    reg = {r[4]: r for r in dd.REGISTER if r[4]}
    summary = []
    # 기본 갈래: 현행·보충·참고 문서 추출과 검토
    for doc, (name, lang) in DOCS.items():
        result = ex.extract(src / name, doc, lang)
        ex.save(result, HERE / '추출결과' / f'{doc}_후보.json')
        rules = RULES[doc][lang] if isinstance(RULES[doc], dict) else RULES[doc]
        missing = MISSING[doc][lang] if isinstance(MISSING[doc], dict) else MISSING[doc]
        notes = DECISIONS_NOTE.get(doc, {}).get(lang, [])
        if doc in ('HM-8', 'PM-02', 'HI-01', 'OEM-HPP45A-MM'):
            data = review(result, rules, missing, selected='SOP-COOL-14' if doc == 'HM-8' else None, decisions=notes)
            write(HERE / '검토결과' / f'{doc}_검토.json', data)
            summary.append(f'{doc} {reg[name][1]}판: 후보 {len(result["candidates"])}개 → 검토 {len(data["candidates"])}건 {counts(data)}, 누락 기록 {len(data["missing"])}건')
        else:
            summary.append(f'{doc} {reg[name][1]}판: 후보 {len(result["candidates"])}개(검토 대상 아님)')
    # 언어 갈래 KO: 같은 문서를 사내 번역으로 추출·검토
    name = DOCS['OEM-HPP45A-MM'][0]
    ko = ex.extract(src / name, 'OEM-HPP45A-MM', 'ko')
    ex.save(ko, HERE / '갈래' / 'OEM-HPP45A-MM_KO_후보.json')
    kod = review(ko, RULES['OEM-HPP45A-MM']['ko'], MISSING['OEM-HPP45A-MM']['ko'], decisions=DECISIONS_NOTE['OEM-HPP45A-MM']['ko'], out_name='OEM-HPP45A-MM_KO_후보.json')
    write(HERE / '갈래' / 'OEM-HPP45A-MM_KO_검토.json', kod)
    summary.append(f'갈래 KO OEM: 후보 {len(ko["candidates"])}개 → 검토 {len(kod["candidates"])}건 {counts(kod)}, 누락 기록 {len(kod["missing"])}건')
    # 판 갈래 B: 폐기 1.0판도 추출하고 전부 제외, 판 대응표를 만든다
    old = ex.extract(src / dd.HM8_OLD_FILE, 'HM-8', 'ko')
    ex.save(old, HERE / '갈래' / 'HM-8_1.0_후보.json')
    oldr = review(old, [], [], decisions=['문서 목록 상태 「폐기」(2026-09-01 1.1판으로 대체). 모든 후보를 적재하지 않는다. 판 대응표와 옛 작업지시 해석에만 쓴다.'],
                  out_name='HM-8_1.0_후보.json')
    for c in oldr['candidates']:
        c.update(decision='제외', status='excluded', reason='폐기 판(1.0) 문장이다. 현행 1.1판의 같은 절차와 대응만 기록하고 적재하지 않는다.')
    write(HERE / '갈래' / 'HM-8_1.0_검토.json', oldr)
    rows = edition_map((src / dd.HM8_OLD_FILE).read_text(encoding='utf-8'), (src / 'HM-8_cooler-fan-manual.md').read_text(encoding='utf-8'))
    with (HERE / '갈래' / 'HM-8_판대응표.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(['1.0판 절차', '절차 이름', '1.1판 절차', '단계 비교', '대응 근거']); w.writerows(rows)
    summary.append(f'갈래 B HM-8 1.0판: 후보 {len(old["candidates"])}개 전부 제외, 판 대응 {len(rows)}건 → 갈래/HM-8_판대응표.csv')
    print('\n'.join(summary))


if __name__ == '__main__':
    main()
