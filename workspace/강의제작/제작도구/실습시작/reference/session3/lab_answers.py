"""통합반 3회차 두 랩(v6-lab)의 강사 참조 — 갈래마다 학생 파일에 채울 내용과, 손으로 정한 기대 판정 · 걸릴 규칙 · 1순위 · 다음 행동. 학생 ZIP에 넣지 않는다.

조치 기준 랩의 정할 지점 「적용 범위」 갈래(SCOPES): 구성요소(기본 — 판단 기능 랩의 제공 조치 기준이 이 갈래) · 가동설비 · 부하절차.
판단 기능 랩의 정할 지점 「쓰는 사람에 따라 갈리는 답」 갈래(ORDERS): 비교값순(기본 — 매뉴얼 HM-8.6대로 견준 차례 그대로) · 경고뒤로(야간 운전 기준대로 경고가 붙은 후보를 뒤에).
판정(허용 · 제외 · 경고 · 감점)은 갈래와 상관없이 덱 31 · 32장대로다. 갈래가 바꾸는 것은 견준 후보 가운데 무엇을 1순위로 내주느냐뿐이다.
기대 판정과 걸릴 규칙(EXPECTED_*), 1순위(TOPS)는 제공 코드의 결과를 옮긴 것이 아니라 매뉴얼 · 경보 표 · 비교 산식으로 따로 구한 값이다 — 강사 참조 시험(lab_trials.py)이 제공 코드의 결과와 견준다.
"""
import csv
import io
import re

FM = 'fm:cooler-cooling-loss'
REMOTE = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13']
SENTENCE = re.compile(r'(?<=\.)\s+')


def sentence_numbers(manual):
    """매뉴얼 글 → [(번호, SOP, 글)] — 학생 폴더 제공 코드(app/utils/sop.py sentences)와 같은 번호 규칙을 따로 구현한 것."""
    section = sop = None
    out = []
    for no, line in enumerate(manual.splitlines(), 1):
        if m := re.match(r'## (HM-\d+\.\d+) ', line):
            section, sop = m.group(1), None
        elif m := re.match(r'### (SOP-[A-Z]+-\d+) ', line):
            sop = m.group(1)
        elif section and line.strip() and not line.startswith(('#', '|')):
            m = re.match(r'(\d+)\. (.+)', line) if sop else None
            parts = SENTENCE.split(m.group(2) if m else line.lstrip('- ').strip())
            out += [(str(no) if len(parts) == 1 else f'{no}.{i}', sop, s) for i, s in enumerate(parts, 1)]
    return out


def finder(manual):
    numbered = sentence_numbers(manual)

    def find(snippet, sop=None):
        hits = [no for no, s, text in numbered if snippet in text and (sop is None or s == sop)]
        if len(hits) != 1:
            raise ValueError(f'매뉴얼에서 「{snippet}」({sop})을 가진 문장이 {len(hits)}개입니다(하나여야 함).')
        return hits[0]
    return find


def csv_text(head_comment, columns, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(columns)
    w.writerows(rows)
    return head_comment + buf.getvalue()


def comment(template):
    """빈 틀의 # 줄들(열 이름 줄 앞까지)."""
    return ''.join(line for line in template.splitlines(keepends=True) if line.lstrip().startswith('#'))


def line_of(text, start):
    """text에서 start로 시작하는 줄의 번호(하나여야 한다)."""
    hits = [no for no, line in enumerate(text.splitlines(), 1) if line.lstrip().startswith(start)]
    if len(hits) != 1:
        raise ValueError(f'「{start}」로 시작하는 줄이 {len(hits)}개입니다(하나여야 함).')
    return hits[0]


# ───────────── 조치 기준 랩 ─────────────
def item_rows(find):
    r3 = ';'.join(REMOTE)
    rows = [
        ['SOP-FAN-11', '적용 대상', [find('팬 지시값은 정상인데'), find('HM-8.1 점검으로 넘어간다')], ''],
        ['SOP-FAN-11', '안전 조건', [find('현장 패널에서 LOCAL로 전환한다.')], ''],
        ['SOP-FAN-11', '완료 확인 기준', [find('재가동 후 VS1이')], ''],
        [r3, '적용 대상', [find('쿨러 냉각 성능 상실로 본다')], ''],
        [r3, '작업 전제 조건', [find('REMOTE_AUTO일 때만 한다'), find('REMOTE_MANUAL이면')], 'R1'],
        [r3, '금지 사항', [find('REMOTE_AUTO가 아닐 때 쓰지 않는다')], 'R1'],
        ['SOP-COOL-12;SOP-COOL-13', '금지 사항', [find('60 % 아래로 내리지 않는다'), find('60 % 미만으로 설정하지 않는다')], ''],
        ['SOP-COOL-11', '제한', [find('24시간 이내로 한다')], 'R2'],
        ['SOP-COOL-11;SOP-COOL-12', '제한', [find('24시간을 넘으면'), find('이미 24시간을 넘겼다면')], 'R2'],
        [r3, '제한', [find('조치 후 예측 유온이 55 ℃ 이상이면')], 'R3'],
        [r3, '제한', [find('냉각 효율 CE가 30 % 미만으로'), find('이때는 경고를 달아')], 'R4'],
        [r3, '완료 확인 기준', [find('완화에 성공한 것이다')], ''],
    ]
    for sop in REMOTE:
        rows += [[sop, '작업 전제 조건', [find('REMOTE_AUTO인지 확인한다', sop)], 'R1'],
                 [sop, '완료 확인 기준', [find('15분 재관측으로', sop)], ''],
                 [sop, '담당 역할', [find('승인: 운전원', sop)], '']]
    rows += [
        ['SOP-COOL-14', '적용 대상', [find('쿨러 핀 오염(먼지')], ''],
        ['SOP-COOL-14', '작업 전제 조건', [find('CMMS 정비 요청으로 발행한다')], ''],
        ['SOP-COOL-14', '담당 역할', [find('승인은 설비보전팀장이 한다')], ''],
        ['SOP-COOL-14', '안전 조건', [find('잠금(LOTO)을 건다')], ''],
        ['SOP-COOL-14', '준비사항', [find('압축공기로')], ''],
        ['SOP-COOL-14', '금지 사항', [find('고압수는 쓰지 않는다')], ''],
        ['SOP-COOL-14', '완료 확인 기준', [find('80 % 이상으로 돌아왔는지')], ''],
    ]
    return [[a, b, ';'.join(c), d] for a, b, c, d in rows]


def relation_rows(find):
    done = find('완화에 성공한 것이다')
    return [*[['MITIGATED_BY', FM, sop, done] for sop in REMOTE],
            ['REMEDIED_BY', FM, 'SOP-COOL-14', find('원인은 남아 있다') + ';' + find('CMMS 정비 요청으로 발행한다')],
            ['REMEDIED_BY', FM, 'SOP-FAN-11', find('HM-8.1 점검으로 넘어간다')],
            ['ADDRESSES', 'SOP-COOL-14', 'cause:cooler-fin-fouling', find('쿨러 핀 오염(먼지')],
            ['ADDRESSES', 'SOP-FAN-11', 'cause:fan-drive-fault', find('HM-8.1 점검으로 넘어간다')]]


FAN_UP = 'SOP-COOL-11;SOP-COOL-12'      # 팬을 100 %로 올리는 단계가 있는 두 SOP(덱 31장 「팬을 100 %로 올리는 두 조치」)
RULE_ROWS = [
    ['R1', '제외', '', ';'.join(REMOTE), 'in:plc-mode', '!=', 'REMOTE_AUTO', '', '원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다', 'HM-8.5; HM-8.8'],
    ['R2', '감점', '20', FAN_UP, 'in:fan100-hours', '>', '24', 'h', '팬 100 % 연속 운전이 24시간을 넘었으면 팬 수명 손실로 20만 원을 감점해 비교한다', 'HM-8.8'],
    ['R3', '경고', '', ';'.join(REMOTE), 'in:forecast-ts1', '>=', '55', '℃', '조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있어 다른 조치와 비교한다', 'HM-8.6'],
    ['R4', '경고', '', ';'.join(REMOTE), 'in:ce', '<', '30', '%', '냉각 효율이 30 % 미만인 설비에서 조치 후 예측 유온이 55 ℃ 이상이면 효과가 오래가지 않아 근본 조치와 함께 비교한다', 'HM-8.8'],
    ['R4', '', '', '', 'in:forecast-ts1', '>=', '55', '℃', '', ''],      # 같은 rule_id의 둘째 조건 — 둘 다 맞아야 맞는다(덱 29장의 복수 조건)
]
# 고의 손상 — 기준값을 틀리게 옮긴 결정표(시험이 경계 · 복수 조건 사례에서 「다름」으로 잡히는지 본다)
WRONG_THRESHOLDS = [('R3', 'in:forecast-ts1', ('>=', '55'), ('>', '55')), ('R2', 'in:fan100-hours', ('>', '24'), ('>=', '25')), ('R4', 'in:ce', ('<', '30'), ('<', '35'))]
COMPONENTS = {'SOP-FAN-11': '쿨러 팬', 'SOP-COOL-11': '쿨러 팬', 'SOP-COOL-12': '쿨러 팬;주 펌프 (A)', 'SOP-COOL-13': '주 펌프 (A);오일 쿨러', 'SOP-COOL-14': '오일 쿨러'}
AIR, RUNNING = 'HYD-01;HYD-02;HYD-03', 'HYD-01;HYD-02;HYD-03;HYD-04'
NO_SCOPE, BY_CAUSE = ('후보 아님', '', 'scope'), ('후보 아님', '', 'cause')
SCOPES = {
    '구성요소': dict(
        chosen='SOP가 다루는 구성 요소가 모두 설비 모델에 있는 설비에만 건다',
        why='매뉴얼의 절차는 쿨러 팬과 오일 쿨러 핀을 다루는데 HYD-04는 수냉 열교환기라 둘 다 없다. 없는 구성 요소의 절차가 후보로 뜨면 운전원이 쓸 수 없는 조치를 받는다',
        changes='HYD-04 경보에는 걸린 SOP가 없어 후보가 나오지 않는다. 운전원은 보전팀에 수냉 열교환기 절차를 확인한다',
        assets={s: AIR for s in COMPONENTS},
        reason='다루는 구성 요소가 모델에 있는 HYD-01~03에 건다. HYD-04는 쿨러 팬 · 오일 쿨러가 없고 HYD-07은 냉각 구성 요소가 없어 걸지 않는다',
        hyd04={'SOP-FAN-11': BY_CAUSE, 'SOP-COOL-11': NO_SCOPE, 'SOP-COOL-12': NO_SCOPE, 'SOP-COOL-13': NO_SCOPE, 'SOP-COOL-14': BY_CAUSE},
        next='HYD-04 경보에 후보가 하나도 없다는 답을 받는다. 운전원은 원격 조치를 하지 않고 보전팀에 수냉 열교환기 절차를 확인한다'),
    '가동설비': dict(
        chosen='원문에 적용 범위가 없으니 가동 중인 2라인 유압 파워팩 네 대에 모두 건다',
        why='매뉴얼 제목이 유압 파워유닛 전체를 가리키고, 걸어 두지 않으면 HYD-04 경보에 아무 후보도 나오지 않는다',
        changes='HYD-04 경보에 팬 조치 둘이 확인되지 않은 조건으로 제외되고 부하 70 %와 야간 핀 세척이 허용으로 나온다',
        assets={s: RUNNING for s in COMPONENTS},
        reason='가동 중인 HYD-01~04에 건다. 예비로 보관 중이고 통신이 없는 HYD-07은 걸지 않는다',
        hyd04={'SOP-FAN-11': BY_CAUSE, 'SOP-COOL-11': ('제외', 'R2;R3', 'fan'), 'SOP-COOL-12': ('제외', 'R2;R3', 'fan'), 'SOP-COOL-13': ('허용', '', 'none'), 'SOP-COOL-14': BY_CAUSE},
        next='HYD-04 경보에 팬 조치 둘이 「확인되지 않은 조건으로 제외」로 뜨고 부하 70 %와 야간 핀 세척이 허용으로 뜬다. 운전원은 HYD-04에 없는 팬의 운전시간과 예측 값을 확인하려 들고, 부하를 낮춘다'),
    '부하절차': dict(
        chosen='팬과 핀을 다루는 SOP는 그 구성 요소가 있는 설비에만, 부하만 낮추는 원격 조치가 든 SOP는 주 펌프가 있는 가동 설비에 건다',
        why='부하를 낮추는 조치는 냉각 방식과 상관없이 발열을 줄이므로 HYD-04에서도 쓸 수 있다고 봤다',
        changes='HYD-04 경보에 부하 70 %와 야간 핀 세척 하나만 후보로 나오고 허용이다. 팬 조치 둘은 후보로 뜨지 않는다',
        assets={'SOP-FAN-11': AIR, 'SOP-COOL-11': AIR, 'SOP-COOL-12': AIR, 'SOP-COOL-13': RUNNING, 'SOP-COOL-14': AIR},
        reason='팬 · 핀 절차는 HYD-01~03, 부하를 낮추는 SOP-COOL-13은 주 펌프가 있는 가동 설비 HYD-01~04에 건다. HYD-07은 예비 보관이라 걸지 않는다',
        hyd04={'SOP-FAN-11': BY_CAUSE, 'SOP-COOL-11': NO_SCOPE, 'SOP-COOL-12': NO_SCOPE, 'SOP-COOL-13': ('허용', '', 'none'), 'SOP-COOL-14': BY_CAUSE},
        next='HYD-04 경보에 부하 70 %와 야간 핀 세척 하나만 허용으로 뜨고 팬 조치는 뜨지 않는다. 운전원은 확인할 값 없이 바로 부하를 낮춘다'),
}
BASE_SCOPE = '구성요소'
HYD04_CASE = 'ALT-hyd04-0031-7c2e'
OK, FAN = ('허용', '', 'none'), ('후보 아님', '', 'causefan')
# 확인 사례의 기대(손으로 정함) — {경보: {SOP: (판정, 걸릴 규칙, 근거 열쇠)}}. HYD-04 사례는 갈래마다 다르다(SCOPES[..]['hyd04']).
# 근거 열쇠: none 걸리는 규칙 없음 · mode 원격 자동 · fan 팬 연속 24시간 · warn 예측 55 ℃ · and 냉각 효율과 예측 · cause 핀 오염에 맞춘 조치 · causefan 팬 구동 불량에 맞춘 조치 · scope 적용 범위
EXPECTED_CRITERIA = {
    # 원격 자동 · 팬 연속 0시간 · 예측이 모두 55 ℃ 미만 — 걸리는 규칙이 없다
    'ALT-hyd03-0280-beaf': {'SOP-FAN-11': FAN, 'SOP-COOL-11': OK, 'SOP-COOL-12': OK, 'SOP-COOL-13': OK, 'SOP-COOL-14': OK},
    # 운전 모드 REMOTE_MANUAL — 원격 조치 셋 제외, 핀 세척은 원격 조치가 아니다
    'ALT-hyd03-0282-df83': {'SOP-FAN-11': FAN, 'SOP-COOL-11': ('제외', 'R1', 'mode'), 'SOP-COOL-12': ('제외', 'R1', 'mode'), 'SOP-COOL-13': ('제외', 'R1', 'mode'), 'SOP-COOL-14': OK},
    # 운전 모드가 빈 값 — 제외 규칙의 확인되지 않은 조건은 제외 쪽
    'ALT-hyd01-0196-c7e2': {'SOP-FAN-11': FAN, 'SOP-COOL-11': ('제외', 'R1', 'mode'), 'SOP-COOL-12': ('제외', 'R1', 'mode'), 'SOP-COOL-13': ('제외', 'R1', 'mode'), 'SOP-COOL-14': OK},
    # REMOTE_MANUAL이고 예측이 비어 경고 규칙이 확인되지 않은 조건으로 남는다. 원인 미확정이라 핀 세척은 후보가 아니다
    'ALT-hyd02-0165-f047': {'SOP-FAN-11': FAN, 'SOP-COOL-11': ('제외', 'R1;R3', 'mode'), 'SOP-COOL-12': ('제외', 'R1;R3', 'mode'), 'SOP-COOL-13': ('제외', 'R1;R3', 'mode'), 'SOP-COOL-14': BY_CAUSE},
    # 예측 55.0 ℃는 55 ℃ 이상(경고), 팬 연속 32.49시간은 24시간 초과(감점). 냉각 효율 31.7 %는 30 % 미만이 아니다
    'ALT-hyd01-0205-9348': {'SOP-FAN-11': FAN, 'SOP-COOL-11': ('허용', 'R2;R3', 'warn'), 'SOP-COOL-12': ('허용', 'R2;R3', 'warn'), 'SOP-COOL-13': OK, 'SOP-COOL-14': OK},
    # 팬 연속 운전시간이 빈 값 — 감점 규칙의 확인되지 않은 조건은 제외 쪽. 팬 최대 운전의 예측 58.4 ℃는 경고도 맞는다
    'ALT-hyd01-0204-a3de': {'SOP-FAN-11': FAN, 'SOP-COOL-11': ('제외', 'R2;R3', 'fan'), 'SOP-COOL-12': ('제외', 'R2', 'fan'), 'SOP-COOL-13': OK, 'SOP-COOL-14': OK},
    # 냉각 효율 29.7 %(30 % 미만)이고 예측이 55 ℃ 이상인 후보에만 두 조건 규칙이 맞는다(52.1 ℃인 후보는 맞지 않는다)
    'ALT-hyd02-0171-051f': {'SOP-FAN-11': FAN, 'SOP-COOL-11': ('허용', 'R3;R4', 'and'), 'SOP-COOL-12': OK, 'SOP-COOL-13': ('허용', 'R3;R4', 'and'), 'SOP-COOL-14': OK},
}
EVIDENCE = {'mode': 'REMOTE_AUTO가 아닐 때 쓰지 않는다', 'fan': '이미 24시간을 넘겼다면', 'warn': '조치 후 예측 유온이 55 ℃ 이상이면', 'and': '냉각 효율 CE가 30 % 미만으로',
            'cause': '쿨러 핀 오염(먼지', 'causefan': 'HM-8.1 점검으로 넘어간다'}


def case_line(table_text, alarm_id):
    return line_of(table_text, alarm_id + ',')


def expected_criteria_rows(scope, cases_text, find):
    def evidence(alarm, key):
        cited = [f'data/check_cases.csv:{case_line(cases_text, alarm)}']
        if key == 'scope':
            cited.append('app/features/decisions.csv:4')
        elif key != 'none':
            cited.append(f'data/hm8_manual.md:{find(EVIDENCE[key]).split(".")[0]}')
        return ';'.join(cited)
    return [[alarm, sop, verdict, rules, evidence(alarm, key)]
            for alarm, verdicts in {**EXPECTED_CRITERIA, HYD04_CASE: SCOPES[scope]['hyd04']}.items() for sop, (verdict, rules, key) in verdicts.items()]


def decisions_text(template, rows):
    """빈 틀의 # 줄과 열 이름은 그대로 두고 지점 줄을 채운다. rows = {지점: (고른_것, 근거, 바뀌는_답)}."""
    out = []
    for line in template.splitlines():
        cells = line.split(',')
        if not line.startswith('#') and cells[0] in rows:
            buf = io.StringIO()
            csv.writer(buf, lineterminator='').writerow([cells[0], *rows[cells[0]]])
            line = buf.getvalue()
        out.append(line)
    return '\n'.join(out) + '\n'


REQUIREMENTS = '''# 요구사항

## 목적과 답을 쓸 사람

HM-8 매뉴얼의 작업 절차와 판단 조건을 SOP 구조와 결정표로 옮겨 설비 모델의 식별자에 건다. 이 조치 기준은 쿨러 성능 저하 경보가 났을 때 운전원이 받는 조치 후보의 판정에 쓰인다.

## 확인할 질문과 쓸 자료

확인 사례의 경보마다 SOP 다섯 가운데 어느 것이 후보이고, 후보마다 허용인지 제외인지, 어느 규칙이 걸리는지. 자료는 `data/hm8_manual.md`, `data/decision_table_export.txt`, `data/check_cases.csv`, `data/model/`이다.

## 지킬 조건 · 범위 밖

원문의 이상 · 초과 · 미만을 그대로 옮긴다. 설비 모델에 없는 식별자를 만들지 않는다. 판정 결과를 기대 판정으로 옮기지 않는다. 손익 비교와 원문에서 조건을 자동으로 뽑는 일은 범위 밖이다.

## 대조 결과 · 고친 점

기대 판정 · 기대 규칙과 결정표를 댄 판정이 모두 같다.

## 저장 시점 · 확인하지 못한 점

저장 시점: 2026-11-19. 확인하지 못한 점: 수냉 열교환기 HYD-04에 맞는 절차는 이 매뉴얼에 없다.
'''


def criteria_fill(scope, data, templates):
    """조치 기준 랩의 app/features 채움 — {파일 이름: 글}. data = 랩 자료 글({이름: 글}), templates = 빈 틀 글."""
    find = finder(data['hm8_manual.md'])
    s = SCOPES[scope]
    line04 = case_line(data['check_cases.csv'], HYD04_CASE)
    return {
        'sop_items.csv': csv_text(comment(templates['sop_items.csv']), ['sop_id', '항목', '원문', '규칙'], item_rows(find)),
        'relations.csv': csv_text(comment(templates['relations.csv']), ['type', 'from', 'to', '원문'], relation_rows(find)),
        'scope.csv': csv_text(comment(templates['scope.csv']), ['sop_id', '구성_요소', '설비', '까닭'], [[sop, COMPONENTS[sop], s['assets'][sop], s['reason']] for sop in COMPONENTS]),
        'decision_table.csv': csv_text(comment(templates['decision_table.csv']), ['rule_id', '결과', '감점_만원', '적용_대상', '입력', '연산자', '기준값', '단위', '이유', '출처'], RULE_ROWS),
        'expected.csv': csv_text(comment(templates['expected.csv']), ['사례', '후보', '기대_판정', '기대_규칙', '근거'], expected_criteria_rows(scope, data['check_cases.csv'], find)),
        'decisions.csv': decisions_text(templates['decisions.csv'], {'적용 범위': (s['chosen'], f'{s["why"]} · data/check_cases.csv:{line04}', s['changes'])}),
        'requirements.md': REQUIREMENTS,
    }


def wrong_table(table_text):
    """결정표 글에서 기준값 셋을 틀리게 바꾼 글(고의 손상)."""
    rows = list(csv.reader(io.StringIO(''.join(x for x in table_text.splitlines(keepends=True) if not x.startswith('#')))))
    for rule, name, (op, value), (new_op, new_value) in WRONG_THRESHOLDS:
        hit = [r for r in rows if r[0] == rule and r[4] == name and r[5] == op and r[6] == value]
        if len(hit) != 1:
            raise ValueError(f'결정표에서 {rule} {name} {op} {value} 줄이 {len(hit)}개입니다.')
        hit[0][5], hit[0][6] = new_op, new_value
    return csv_text(comment(table_text), rows[0], rows[1:])


# ───────────── 판단 기능 랩 ─────────────
ORDERS = {
    '비교값순': dict(
        chosen='경고가 붙은 후보도 비교값이 가장 작으면 1순위로 내주고 경고를 이유로 함께 보인다(매뉴얼 HM-8.6 기준). 이 답은 설비보전팀장이 조치를 검토할 때 쓰는 것으로 정했다',
        why='매뉴얼은 경고가 붙은 조치도 다른 조치와 비교하라고 하고, 검토하는 사람은 손실이 가장 작은 조치를 놓치면 안 된다',
        changes='경고가 붙은 팬 최대 운전이 1순위인 경보가 생긴다',
        body="    return {}\n"),
    '경고뒤로': dict(
        chosen='경고가 붙은 후보는 비교값이 작아도 1순위로 내주지 않고 경고 없는 후보 뒤에 까닭과 함께 보인다(야간 운전 기준). 이 답은 야간 운전원이 바로 쓰는 것으로 정했다',
        why='야간 근무조는 한 명이라 15분 재관측에서 회복하지 않으면 다시 대응할 인원이 없고, 운전 기준이 경고가 없는 조치부터 쓰라고 한다',
        changes='경고가 붙은 후보가 1순위이던 경보의 1순위가 경고 없는 후보로 바뀐다',
        body="    return {k['sop']: '경고 ' + ' · '.join(k['warnings']) + '가 붙어 뒤에 보임' for k in kept if k['warnings']}\n"),
}
BASE_ORDER = '비교값순'
STATEMENT = ('비교값은 이 오더의 납기까지 예상되는 손실을 만 원으로 더한 값이라 작을수록 앞이고, 정책 점수는 판단 시스템의 순위 규칙이 성과 득실과 납기 긴급도까지 넣어 매긴 점수라 높을수록 앞이다. '
             '두 값은 식과 방향이 달라 같은 후보의 순위가 다를 수 있고, 비교값으로 정한 1순위는 견준 결과일 뿐 실행 승인이 아니다')
OKJ, NONE14 = ('허용', ''), ('후보 아님', '')
# 사례 다섯 종류의 기대(손으로 정함, 제공 조치 기준 = 구성요소 갈래) — [(종류, 경보, {SOP: (판정, 걸릴 규칙)})]
EXPECTED_JUDGE = [
    ('정상', 'ALT-hyd03-0280-beaf', {'SOP-FAN-11': ('후보 아님', ''), 'SOP-COOL-11': OKJ, 'SOP-COOL-12': OKJ, 'SOP-COOL-13': OKJ, 'SOP-COOL-14': OKJ}),
    # 예측 55.0 ℃(이상 → 경고), 팬 연속 32.49시간(초과 → 감점), 냉각 효율 31.7 %(30 % 미만이 아님)
    ('경계', 'ALT-hyd01-0205-9348', {'SOP-COOL-11': ('허용', 'R2;R3'), 'SOP-COOL-12': ('허용', 'R2;R3'), 'SOP-COOL-13': OKJ}),
    # 팬 연속 24.01시간(24시간 초과 → 감점). 팬 최대 운전과 부하 80 %는 예측이 비어 경고 규칙이 확인되지 않은 조건으로 남는다
    ('경계', 'ALT-hyd02-0172-54a5', {'SOP-COOL-11': ('허용', 'R2;R3'), 'SOP-COOL-12': ('허용', 'R2;R3'), 'SOP-COOL-13': OKJ}),
    # 한 규칙의 두 조건: 냉각 효율 28.1 %(30 % 미만)인데 예측 51.8 ℃인 후보는 맞지 않고, 56.2 · 58.1 ℃인 후보는 둘 다 맞는다
    ('복수 조건', 'ALT-hyd03-0296-2adb', {'SOP-COOL-11': OKJ, 'SOP-COOL-12': ('허용', 'R3;R4'), 'SOP-COOL-13': ('허용', 'R3;R4')}),
    # 예측 57.1 ℃는 맞지만 냉각 효율 30.3 %는 30 % 미만이 아니라 두 조건 규칙은 맞지 않는다
    ('복수 조건', 'ALT-hyd02-0170-3589', {'SOP-COOL-12': OKJ, 'SOP-COOL-13': ('허용', 'R3')}),
    ('모두 제외', 'ALT-hyd02-0165-f047', {'SOP-COOL-11': ('제외', 'R1;R3'), 'SOP-COOL-12': ('제외', 'R1;R3'), 'SOP-COOL-13': ('제외', 'R1;R3'), 'SOP-COOL-14': NONE14}),
    ('필수값 누락', 'ALT-hyd01-0196-c7e2', {'SOP-COOL-11': ('제외', 'R1'), 'SOP-COOL-12': ('제외', 'R1'), 'SOP-COOL-13': ('제외', 'R1'), 'SOP-COOL-14': OKJ}),
    ('필수값 누락', 'ALT-hyd01-0204-a3de', {'SOP-COOL-11': ('제외', 'R2;R3'), 'SOP-COOL-12': ('제외', 'R2'), 'SOP-COOL-13': OKJ}),
]
# 갈래마다 1순위가 갈리는 경보(손계산 — lab_trials.py의 두 번째 구현으로 다시 구해 견준다). 세 경보 모두 판정 요청 때 팬이 이미 100 %다(팬100_연속_h > 0).
TOPS = {
    'ALT-hyd03-0299-374a': {'비교값순': 'SOP-COOL-11', '경고뒤로': 'SOP-COOL-14'},
    'ALT-hyd01-0205-9348': {'비교값순': 'SOP-COOL-11', '경고뒤로': 'SOP-COOL-14'},
    'ALT-hyd02-0172-54a5': {'비교값순': 'SOP-COOL-11', '경고뒤로': 'SOP-COOL-14'},
}
# 그 답을 받은 사람의 다음 행동(1순위 후보마다). 팬 최대 운전은 팬이 이미 100 %인 경보의 것이다.
NEXT = {
    'SOP-COOL-11': '팬은 이미 100 %라 새로 내릴 원격 명령이 없다. 답을 받은 사람은 설비를 세우지 않고 팬 100 %를 이어 가며 15분 재관측으로 회복 판정을 한다. 경보가 풀리지 않을 수 있다는 경고를 함께 받는다',
    'SOP-COOL-14': '원격 조치를 더 하지 않고 쿨러 핀 세척 정비 요청을 올려 설비보전팀장의 승인을 받는다. 설비를 세우는 작업이다',
}
REVIEW = '''# 기대 결과와 실제 대조

## 질문 · 쓸 자료 · 지킬 조건

쿨러 성능 저하 경보마다 어느 조치 후보가 허용이고 어느 규칙이 걸리는가, 허용된 후보 가운데 손실이 가장 작은 것은 무엇이고 무엇을 1순위로 내줄 것인가. 자료는 `data/alarms.csv`, `data/criteria/`, `data/metrics/`, `data/night_operation_rule.md`다. 빈 값을 0으로 채우지 않고, 판정 결과를 기대 판정으로 옮기지 않는다.

## 기대 판정과 실제 결과 · 고친 점

사례 다섯 종류의 기대 판정 · 기대 규칙과 판정이 모두 같다.

## 손으로 해 본 계산

`data/metrics/metric_definitions.md`의 예(ALT-hyd03-0280-beaf, SOP-COOL-12)와 결과 화면의 비교값이 같다.

## 저장 시점 · 확인하지 못한 점

저장 시점: 2026-11-19. 확인하지 못한 점: 예측 유온이 빈 후보는 비교값을 내지 못했다.
'''


def compare_file(template, branch):
    head = template[:template.index('def hold_back')]
    return head + 'def hold_back(kept):\n' + ORDERS[branch]['body']


def judge_fill(branch, data, templates):
    """판단 기능 랩의 app/features 채움. data에는 'criteria/decision_table.csv' · 'criteria/sop.json'(제공 조치 기준 글)도 있어야 한다."""
    table, sop = data['criteria/decision_table.csv'], data['criteria/sop.json']
    rule_line = {r: line_of(table, r + ',') for r in ('R1', 'R2', 'R3')}
    rule_line['R4'] = min(no for no, x in enumerate(table.splitlines(), 1) if x.startswith('R4,'))
    cause_line = {'SOP-COOL-14': line_of(sop, '"to": "cause:cooler-fin-fouling"'), 'SOP-FAN-11': line_of(sop, '"to": "cause:fan-drive-fault"')}
    rows = []
    for kind, alarm, verdicts in EXPECTED_JUDGE:
        line = case_line(data['alarms.csv'], alarm)
        for candidate, (verdict, rules) in verdicts.items():
            cited = [f'data/alarms.csv:{line}'] + [f'data/criteria/decision_table.csv:{rule_line[r]}' for r in rules.split(';') if r]
            if verdict == '후보 아님':
                cited.append(f'data/criteria/sop.json:{cause_line[candidate]}')
            rows.append([kind, alarm, candidate, verdict, rules, ';'.join(cited)])
    c = ORDERS[branch]
    night = line_of(data['night_operation_rule.md'], '- 그래서 야간 근무조는')
    manual = finder(data['hm8_manual.md'])('조치 후 예측 유온이 55 ℃ 이상이면').split('.')[0]
    metric = line_of(data['metrics/metric_definitions.md'], '## 정책 점수')
    return {
        'compare_rule.py': compare_file(templates['compare_rule.py'], branch),
        'expected.csv': csv_text(comment(templates['expected.csv']), ['사례_종류', '사례', '후보', '기대_판정', '기대_규칙', '근거'], rows),
        'decisions.csv': decisions_text(templates['decisions.csv'], {
            '쓰는 사람에 따라 갈리는 답': (c['chosen'], f'{c["why"]} · data/hm8_manual.md:{manual} · data/night_operation_rule.md:{night}', c['changes']),
            '비교 기준 문장': (STATEMENT, f'data/metrics/metric_definitions.md:{metric}', '')}),
        'review.md': REVIEW,
    }
