"""강사 참조 검토 — 학생 배포 금지(실습5 입력으로만 HM-8 검토본을 제공).

추출결과/*_후보.json을 원문과 대조한 사람의 결정을 적용해 검토결과/*_검토.json과 검토 표를 만든다.
결정은 아래 표에 후보 id별로 적었다. 표에 없는 후보는 원문 문장·종류·값을 대조해 그대로 채택한 것이다.
후보 id가 바뀌면(추출 함수 수정 후) 표를 다시 대조해야 하므로, 후보의 quote가 기록과 다르면 실패한다.
"""
from pathlib import Path
import copy
import json
import sys

HERE = Path(__file__).resolve().parent
REVIEWER = '강사 참조 검토(원문 대조, 2026-10-28)'
REVIEWED_AT = '2026-10-28T00:00:00+09:00'

DIAG = '고장 판정·원인 판별 조건이다. 계약의 precondition(작업 전 확인 조건)과 뜻이 다르고 계약에 맞는 종류가 없어 적재하지 않고 보류한다.'
NAME_NUM = '패키지·점검 이름 안의 수치이며 기준값이 아니다. 기준값으로 적재하면 근거 없는 기준이 된다.'

# id: (결정, 이유, 수정할 필드 또는 None, quote 앞부분 — 표와 후보가 같은지 확인)
DECISIONS = {
    'HM-8': {
        'HM-8-007': ('제외', '베어링 표면 온도 점검 단계이며 작업 전 조건이 아니다. 같은 문장은 단계(HM-8-006)와 기준값(HM-8-008)으로 이미 표현된다.', None, '베어링 소음과'),
        'HM-8-022': ('제외', '일반 산업 설비의 경보 수준을 설명한 괄호 문장이다. 이 설비의 기준값이 아니므로 적재하면 근거 없는 기준이 된다.', None, '아래 값은 교육용'),
        'HM-8-029': ('보류', DIAG, None, '유온이 55 ℃를 넘고'),
        'HM-8-032': ('수정', '같은 절 표의 인터록 칸 「65 ℃ 이상 (설비 정지)」과 같은 기준이다. 「65 ℃에서」는 도달 시점을 말하므로 비교 기호를 >=로 맞춘다.', {'comparator': '>='}, '이 상태로 두면'),
        'HM-8-033': ('보류', DIAG, None, '최근 30초'),
        'HM-8-038': ('보류', DIAG, None, '최근 2분 캐비닛'),
        'HM-8-041': ('보류', DIAG, None, '최근 2분 팬 진동'),
        'HM-8-044': ('보류', DIAG, None, '경보 패턴 COOLER'),
        'HM-8-047': ('제외', '같은 문장이 금지 후보(HM-8-048)로 이미 있다. 「REMOTE_MANUAL이면」은 금지의 적용 범위이지 실행 전 충족할 조건이 아니다.', None, '현장에서 수동 조작이'),
        'HM-8-100': ('수정', '24시간 제한(HM-8-055)의 이유를 말하는 제한 문장이다. 실행 전 충족할 조건이 아니라 금지·제한으로 분류한다.', {'kind': 'prohibition'}, '팬 100 % 연속 운전이'),
    },
    'PM-02': {
        'PM-02-004': ('보류', '표 칸에 시행 차례가 여럿(2,000 · 6,000 · 10,000 h)인데 단위가 붙은 마지막 값만 추출됐다. 계약의 value 하나로는 차례 목록을 표현할 수 없어 보류한다.', None, '2,000 · 6,000'),
        'PM-02-005': ('보류', '표 칸의 시행 차례 목록 중 마지막 값만 추출됐다(4,000 누락).', None, '4,000 · 12,000'),
        'PM-02-006': ('제외', NAME_NUM, None, '2,000 h 패키지 + 어큐뮬레이터'),
        'PM-02-007': ('제외', NAME_NUM, None, '2,000 h 패키지와 같음'),
        'PM-02-008': ('보류', '표 칸의 시행 차례 목록 중 마지막 값만 추출됐다(8,000 누락).', None, '8,000 · 16,000'),
        'PM-02-009': ('제외', NAME_NUM, None, '4,000 h 패키지 + 주 펌프'),
        'PM-02-010': ('제외', NAME_NUM, None, '4,000 h 부품'),
        'PM-02-014': ('수정', '상한을 넘긴 시행의 결과를 말하는 제한 문장이다. 실행 전 조건이 아니라 금지·제한으로 분류한다.', {'kind': 'prohibition'}, '2,200 h를 넘겨'),
        'PM-02-017': ('보류', 'CMMS가 경보를 내는 조건이며 작업자가 실행 전에 확인할 조건이 아니다. 계약에 맞는 종류가 없어 보류한다.', None, 'CMMS는 마지막'),
        'PM-02-030': ('수정', '「24시간 안에」는 24시간 이내를 뜻한다. 규칙이 「안」을 비교 표현으로 읽지 못했다.', {'comparator': '<='}, '생산: 납기가'),
        'PM-02-035': ('수정', '「4명보다 적으면」은 4명 미만이다. 규칙이 「보다 적으면」을 비교 표현으로 읽지 못했다.', {'comparator': '<'}, '그 시간의 정비 인원이'),
        'PM-02-054': ('제외', '다음 단계에 쓸 정보를 확인하는 단계이며 조건이 아니다. 단계 후보(PM-02-053)로 충분하다.', None, '그다음 예정된 정비 시간과'),
        'PM-02-080': ('수정', '「2,000 h 정기 점검」은 SOP-PM-21의 이름이다. ID 없이 이름으로 가리켜 규칙이 참조를 놓쳤다.', {'refs': ['SOP-PM-21']}, '2,000 h 정기 점검의 1~6단계'),
        'PM-02-081': ('제외', NAME_NUM, None, '2,000 h 정기 점검의 1~6단계'),
        'PM-02-087': ('수정', '「4,000 h 정기 점검」은 SOP-PM-22의 이름이다. ID 없이 이름으로 가리켜 규칙이 참조를 놓쳤다.', {'refs': ['SOP-PM-22']}, '4,000 h 정기 점검의 1~3단계'),
        'PM-02-088': ('제외', NAME_NUM, None, '4,000 h 정기 점검의 1~3단계'),
        'PM-02-104': ('보류', DIAG, None, '최근 1분 토출 압력'),
        'PM-02-107': ('보류', DIAG, None, '최근 1분 유량'),
        'PM-02-110': ('보류', DIAG, None, '경보 패턴 PUMP_LEAKAGE'),
    },
}

# 원문에 있지만 후보가 없는 것. add=True이면 검토자가 근거 문장으로 후보를 추가한다(origin=reviewer).
MISSING = {
    'HM-8': [
        dict(section='HM-8.7', procedure=None, kind='precondition', quote='원인에 맞는 근본 조치를 CMMS 작업지시로 발행한다.',
             note='근본 조치(SOP-COOL-14·15)는 CMMS 작업지시로 발행한다는 실행 전 조건. 규칙의 조건 표현 목록에 없는 평서문이라 놓쳤다.', add=True),
        dict(section='HM-8.7', procedure='SOP-COOL-14', kind='precondition', quote='설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다.',
             note='핀 세척 1단계의 정지·LOCAL·잠금은 이후 단계의 안전 준비 조건이다. 단계(HM-8-088)로만 잡혔다.', add=True),
        dict(section='HM-8.1', procedure='SOP-FAN-11', kind='precondition', quote='설비를 정지하고 현장 패널에서 LOCAL로 전환한다.',
             note='팬 점검 1단계의 정지·LOCAL 전환도 같은 기준으로 준비 조건에 추가한다.', add=True),
        dict(section='HM-8.8', procedure=None, kind='precondition', quote='이미 24시간을 넘겼다면 팬 최대 운전 조치는 팬 수명 손실로 20만 원을 감점해서 비교한다.',
             note='「~다면」 조건을 규칙이 읽지 못했다. 「팬 최대 운전 조치」가 SOP-COOL-11만인지 팬 100 %를 쓰는 SOP-COOL-12까지인지 원문이 ID로 정하지 않아 추가하지 않고 남은 질문으로 둔다.', add=False),
    ],
    'PM-02': [
        dict(section='PM-2.3', procedure=None, kind='precondition', quote='허용 오차 안에서 일찍 시행해도 다음 주기는 시행한 때부터 다시 센다.', note='주기 계산 규칙. 조건 표현이 「~해도」라 놓쳤다. 다섯 종류 중 맞는 것이 없어 계약 보완이 필요하다.', add=False),
        dict(section='PM-2.3', procedure=None, kind='completion', quote='시행 기록에는 패키지, 시행 때의 운전시간, 교체 부품 로트, 시운전 값을 남긴다.', note='완료 때 남길 기록 요건인데 완료 표현 목록에 없어 놓쳤다.', add=False),
        dict(section='PM-2.5', procedure=None, kind='precondition', quote='부품: 두 대를 묶으려면 씰 키트가 2개 이상 있어야 한다.', note='「~려면 ~있어야 한다」 조건을 규칙이 읽지 못했다. 값(PM-02-042)만 남았다.', add=False),
        dict(section='PM-2.6', procedure=None, kind='prohibition', quote='잔압이 남은 유압 회로를 열면 작동유가 분출해 다칠 수 있다.', note='금지(PM-02-068)의 이유인 위험 문장. 「열면」이 조건 표현 목록에 없다.', add=False),
        dict(section='PM-2.1', procedure=None, kind='completion', quote='계수기는 마지막 정기 정비 뒤 운전시간을 세고, 정비를 마치면 0으로 되돌린다.', note='완료 후 처리. PM-2.9의 같은 내용(PM-02-100)은 잡혔다.', add=False),
    ],
}

STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}


def review(doc, selected=None):
    source = json.loads((HERE / '추출결과' / f'{doc}_후보.json').read_text(encoding='utf-8'))
    table = DECISIONS[doc]
    ids = {c['id'] for c in source['candidates']}
    unknown = set(table) - ids
    if unknown:
        raise SystemExit(f'{doc}: 결정 표의 후보가 추출 결과에 없음 {sorted(unknown)}')
    items = []
    for c in source['candidates']:
        item = copy.deepcopy(c)
        decision, reason, change, head = table.get(c['id'], ('채택', '원문 문장·절·종류·값을 대조해 일치한다.', None, None))
        if head and head not in c['quote'] and head not in c['text']:
            raise SystemExit(f'{c["id"]}: 결정 표의 문장과 후보가 다름 — 표를 다시 대조하세요')
        if change:
            item['before'] = {k: c.get(k) for k in change}
            item.update(change)
        item.update(decision=decision, status=STATUS[decision], reason=reason, origin='extractor')
        items.append(item)
    n = len(items)
    for m in MISSING[doc]:
        if not m['add']:
            continue
        n += 1
        items.append({'id': f'{doc}-R{n:03d}', 'doc_id': doc, 'section': m['section'], 'procedure': m['procedure'],
                      'kind': m['kind'], 'text': m['quote'], 'quote': m['quote'], 'refs': [], 'status': 'approved',
                      'decision': '채택', 'reason': '검토자 추가: ' + m['note'], 'origin': 'reviewer'})
    out = {k: source[k] for k in ['doc_id', 'source_file', 'source_sha256', 'extractor', 'generated_at']}
    out['review'] = {'reviewer': REVIEWER, 'reviewed_at': REVIEWED_AT, 'candidates_file': f'{doc}_후보.json', 'selected_task': selected}
    out['candidates'] = items
    out['missing'] = [{k: m[k] for k in ['section', 'procedure', 'kind', 'quote', 'note']} | {'added': m['add']} for m in MISSING[doc]]
    dest = HERE / '검토결과' / f'{doc}_검토.json'
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    counts = {}
    for i in items:
        counts[i['decision']] = counts.get(i['decision'], 0) + 1
    print(f'{doc}: 검토 {len(items)}건 {counts}, 누락 기록 {len(MISSING[doc])}건 → {dest.name}')
    return out


if __name__ == '__main__':
    review('HM-8', 'SOP-COOL-11')
    review('PM-02')
