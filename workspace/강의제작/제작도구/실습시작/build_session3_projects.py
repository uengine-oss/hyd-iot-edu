"""냉각 경보 조치 판단 네 랩을 새 프로젝트 구조(코딩랩.md K-5~K-7)로 만든다 — 지정한 랩 하나만, 다른 랩 · 강사 참조는 다시 만들지 않는다.

통합반 03회차 실습2 action-criteria-lab · 실습3 judgement-lab, 실전반 02회차 실습5 condition-table-lab · 03회차 실습2 action-review-lab.
판단 · 자료 · 난도는 기존 생성기(build_judgement_labs.py)의 정의를 그대로 쓴다: 그 랩 정의 · 원자료 코어(data_conditions.py) · 강사 검증 판(reference/session3/criteria.py) ·
제공 코드(judgement_tools/) · 검사기 · 결과 화면 함수를 임시 폴더의 기존 구조로 한 번 만든 뒤, 경로 · 파일 이름만 영어로 바꿔(convert) 프로젝트로 옮긴다.
조치 기준 랩의 설비 모델은 통합02와 같은 생성기 함수(build_labs.reference_model · session2_project.convert)에서 받는다 — 다른 랩의 산출물/ 바이트를 읽지 않는다.

python build_session3_projects.py criteria|judge|conditions|review --dest 작업/검사/<새 폴더> [--completed]
python build_session3_projects.py criteria|judge|conditions|review --apply [--completed]
  --dest  검증 사본(package-index에 등록하지 않음)   --apply  검증 사본을 만든 뒤 그 랩 하나만 정본 자리에 바꿔 끼우고 등록
  --completed  학생용 완성본(실습 ZIP 밖의 별도 묶음)도 기본 갈래 채움으로 실제 실행해 만든다(유료 AI 호출 없음)
"""
from pathlib import Path
import argparse
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile

import build_judgement_labs as BJ
import build_labs as B
import data_conditions as DC
import data_session2 as D2
import lab_frame as F
import session2_project as P
from lab_package import ROOT, entry, pack, register, student_files, write_zip
from project_layout import errors, write_metadata

CR = BJ.CR
VERSION = 'v2-project'   # 2026-11-11: 독립 검토 고침 + 공용 고침
WORK = ROOT/'작업/검사/session3-projects'
KEYS = {'criteria': 'integrated-03-criteria', 'judge': 'integrated-03-judge', 'conditions': 'practical-02-conditions', 'review': 'practical-03-review'}
PROJECT = {   # 프로젝트 폴더 = 실라버스 행 제목의 뜻(한 회차 랩 폴더 안에서 겹치지 않게)
    'integrated-03-criteria': 'action-criteria-lab',     # 작업 절차와 판단 조건을 연결해 조치 기준 만들기
    'integrated-03-judge': 'judgement-lab',              # 조치를 비교하는 판단 기능 만들기
    'practical-02-conditions': 'condition-table-lab',    # 복합 조건과 예외를 조치 조건표로 표현하기
    'practical-03-review': 'action-review-lab',          # 판정 · 성과 비교를 조치 검토 결과로 완성하기
}
COURSE = {'integrated-03-criteria': ('통합반', '03'), 'integrated-03-judge': ('통합반', '03'),
          'practical-02-conditions': ('실전반', '02'), 'practical-03-review': ('실전반', '03')}
JUDGE = ('integrated-03-judge', 'practical-03-review')

# ───────────── 경로 · 파일 이름 변환(원자료 내용은 그대로, 이름만 영어) ─────────────
NAMES = {
    'HM-8_매뉴얼.md': 'hm8_manual.md', 'HM-8_1.0판_매뉴얼.md': 'hm8_manual_v1_0.md', 'HI-01_보충매뉴얼.md': 'hi01_supplement.md',
    '작업기준.md': 'work_standard.md', '판단시스템_결정표_내보내기.txt': 'decision_table_export.txt', '작업지시_이력.csv': 'work_orders.csv',
    '사건_기록_HYD-02_1027.md': 'incident_hyd02_1027.md', '확인_사례.csv': 'check_cases.csv', '수집_설명.md': 'collection_notes.md',
    '경보_목록.csv': 'alarms.csv', 'PLC_상태_수신.csv': 'plc_status.csv', '팬_운전_카운터.csv': 'fan_counter.csv', '예측_결과.csv': 'forecasts.csv',
    '오더_현황.csv': 'orders.csv', '지표_정의.md': 'metric_definitions.md', '업무_값.json': 'business_values.json', '후보_설정.csv': 'candidate_settings.csv',
    '설비_대장.csv': 'equipment.csv',
    '조건표.csv': 'condition_table.csv', '조건_분류.csv': 'condition_classes.csv', '관계.csv': 'relations.csv', '설비_연결_기준.csv': 'equipment_links.csv',
    '정한_것.csv': 'decisions.csv', '기대_판정.csv': 'expected.csv', '요구사항.md': 'requirements.md', '승인.csv': 'approvals.csv',
    '판단기록.md': 'judgement_record.md', '기대결과.md': 'review.md', '조치검토결과.json': 'action_review.json', '조치검토결과.md': 'action_review.md',
    '보기.html': 'result.html', '입출력_계약.md': 'data/contract.md',
}
TEXT = [('(입출력_계약)', '(data/contract.md)'), ('START.md 「학생이 정할 것」의 이름 그대로', 'AGENTS.md에 적힌 지점 이름 그대로'),
        ('START.md 「학생이 정할 것」의 그 자리 이름', 'AGENTS.md에 적힌 정할 지점의 이름'), ('START.md 「학생이 정할 것」의 ', '정할 지점: '),
        ('보관하지 말고 바로 채웁니다', '이 파일을 바로 고쳐 채웁니다'),
        ('5단계에서 내 판단 함수로 처음 실행한 시각(내 PC 시계 그대로 — 1단계의 결과 화면 열기는 세지 않음)', '판단 함수로 처음 실행한 시각(내 PC 시계 그대로 — 자료 확인 화면 열기는 세지 않음)'),
        ('(앞 단계를 아직 채우는 중이면 그 단계의 자리가 짚힙니다)', '(아직 채우지 않은 파일이 있으면 그 파일이 짚힙니다)'),
        ('「{point}」로 시작하는', '「{point}」(으)로 시작하는'),
        ('비교 합계가', '비교값이'), ('비교 합계와', '비교값과'), ('비교 합계는', '비교값은'), ('비교 합계로', '비교값으로'), ('비교 합계', '비교값'), ('포털 성과 지표의 점수', '정책 점수'), ('받은 원문', 'HM-8 매뉴얼 원문'), ('즉시 완화', '완화 조치'), ('포털 성과 지표 점수', '정책 점수'),
        ('python show_result.py', 'python run.py'), ('python check.py', 'python run.py check'), ('show_result.py', 'run.py'), ('START.md', '가이드')]


def converter(key, prose=True):
    """그 랩의 경로 변환. 입력/ · 결과/내_입력/은 조치 기준 랩이 설비 모델, 판정 랩이 조건표 · SOP 구조라 자리가 다르다."""
    model = key == 'integrated-03-criteria'
    given, mine = ('data/model', 'app/features/model') if model else ('data/criteria', 'app/features/criteria')
    # 판정 랩의 결과 계약 파일은 output/judgement.json — output/result.json은 run.py가 쓰는 결과 화면 기록이라 이름을 나눈다.
    paths = [('결과/내_입력', mine), ('결과/sop.json', 'output/sop.json'), ('결과/result.json', 'output/judgement.json'), ('(result.json)', '(judgement.json)'),
             ('결과/action_review.json', 'output/action_review.json'), ('결과/action_review.md', 'output/action_review.md'),
             ('결과/result.html', 'output/result.html'), ('입력/자료/equipment.csv', 'data/model/equipment.csv'),
             ('입력/', given + '/'), ('자료/', 'data/'), ('결과/', 'app/features/')]

    def convert(text):
        for old, new in sorted(NAMES.items(), key=lambda x: -len(x[0])):
            text = text.replace(old, new).replace(old.replace('.', r'\.'), new.replace('.', r'\.'))
        for old, new in paths:
            text = text.replace(old, new)
        for word, new in (('자료', 'data'), ('결과', 'app/features'), ('입력', given)):   # 경로 잇기의 낱말만(칸 이름 '결과' · '입력'은 그대로)
            text = re.sub(r"(/\s*)'" + word + "'", r"\1'" + new + "'", text)
        for old, new in (TEXT if prose else []):   # 원자료(prose=False)는 파일 이름 · 경로만 바꾼다
            text = text.replace(old, new)
        return P.fill_term(text) if prose else text   # 옛 「정할 자리」(채울 파일)는 「빈 틀」 — 결정 지점의 이름 「정할 지점」과 나눈다
    return convert


def write(path, text, bom=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8-sig' if bom else 'utf-8', newline='\n')


# ───────────── 기존 구조 정의를 임시 폴더에 한 번 만든다(정본 자리는 건드리지 않음) ─────────────
def model_inputs():
    """통합02 그래프 랩과 같은 생성기 함수에서 받은 설비 모델 — (schema, graph, 설비 대장 CSV)."""
    schema, graph = B.reference_model(False, B.LAB4_INPUT_BRANCH['통합반'])
    return B.student_schema(schema), graph, D2._csv(D2.ASSET_COLS, D2.asset_rows())


def old_lab(key, files, folder):
    """build_judgement_labs.build와 같은 순서로 기존 구조를 folder에 쓰고 랩 정의를 돌려준다(학생 가이드 · START · ZIP은 만들지 않음)."""
    folder = Path(folder)
    if folder.exists():
        raise ValueError(f'{folder}: 새 임시 폴더여야 합니다.')
    for name, core in BJ.DATA[key]:
        F.write(folder/'자료'/name, files[core])
    if key == 'integrated-03-criteria':
        schema, graph, assets = model_inputs()
        F.dump(folder/'입력/schema.json', schema)
        F.dump(folder/'입력/graph.json', graph)
        F.write(folder/'입력/자료/설비_대장.csv', assets)
    if key in JUDGE:
        BJ.judge_inputs(folder)
    for name in BJ.PROVIDED[key]:
        F.write(folder/name, (BJ.PROVIDED_SRC/name).read_text(encoding='utf-8'))
    L = BJ.BUILDERS[key](files, folder)
    for name, text in L['files'].items():
        F.write(folder/name, text)
    F.write_provided(folder, BJ.steps_source(key, L))
    F.write(folder/'check.py', BJ.check_source(key, folder))
    return L


# ───────────── 제공 코드(app/utils · app/ui) ─────────────
STEPS_DOC = re.compile(r'^""".*?"""\n', re.S)
COMMANDS = {
    'integrated-03-criteria': [('sources', '받은 자료', 'overview'), ('export', '판단 시스템 결정표 규칙', 'facts'), ('expected', '기대 판정', 'expected_view'),
                               ('classify', '조건 문장과 SOP 구조', 'classify'), ('relations', '고장 유형 · 원인 · 조치 관계', 'relations'),
                               ('links', '설비 모델 연결', 'models'), ('rules', '조건표 규칙과 사건 판정', 'rules'),
                               ('provenance', '출처가 확인되지 않는 규칙', 'sources'), ('check', '구조 검사', 'run_check')],
    'practical-02-conditions': [('sources', '받은 자료', 'overview'), ('export', '판단 시스템 결정표 규칙', 'facts'), ('expected', '기대 판정', 'expected_view'),
                                ('rules', '조건표 규칙과 사례 판정', 'rules'), ('provenance', '출처가 확인되지 않는 규칙', 'sources'),
                                ('approvals', '남은 후보와 실행 승인', 'approvals'), ('check', '구조 검사', 'run_check')],
    'integrated-03-judge': [('sources', '판정 요청 직전 원천 기록', 'overview'), ('expected', '기대 판정', 'expected_view'),
                            ('inputs', '끊긴 카운터 기록과 판정', 'inputs_view'), ('compare', '견줄 후보와 순위', 'compare_view'),
                            ('write', '비교 기준 문장과 결과 파일', 'written'), ('cases', '사례 대조', 'cases_view'), ('check', '구조 검사', 'run_check')],
    'practical-03-review': [('sources', '판정 요청 직전 원천 기록', 'overview'), ('expected', '기대 판정', 'expected_view'),
                            ('inputs', '끊긴 카운터 기록과 판정', 'inputs_view'), ('compare', '견줄 후보 · 순위와 조치 검토 결과', 'compare_and_write'),
                            ('cases', '검토 결과와 사례 대조', 'cases_view'), ('check', '구조 검사', 'run_check')],
}
PREVIOUS = '''

def keep_previous(fn):
    """개수 칸 옆에 직전 실행(output/result.json)의 같은 이름 값을 붙인다 — 결정을 바꾼 뒤 무엇이 바뀌었는지 본다."""
    def run(previous):
        blocks = fn(previous)
        p = HERE/'output/result.json'
        try:
            before = json.loads(p.read_text(encoding='utf-8')).get('blocks', []) if p.is_file() else []
        except ValueError:
            before = []
        old = {(b.get('title'), k): v for b in before if b.get('kind') == 'counts' for k, v in b.get('items', [])}
        for b in blocks:
            if b['kind'] == 'counts':
                b['items'] = [(k, v if (b['title'], k) not in old or str(old[(b['title'], k)]).split(' ')[0] == str(v) else f"{v} (직전 실행 {str(old[(b['title'], k)]).split(' ')[0]})")
                              for k, v in b['items']]
        return blocks
    return run
'''


def actions_source(key, L, convert, incident):
    text = BJ.steps_source(key, L)
    text = text[:text.rindex('\nSTEPS = ')]
    text = STEPS_DOC.sub('"""' + L['title'] + ' — 기능마다 결과 화면에 보일 표를 만든다(제공 — 고치지 않는다). 판단의 답은 이 파일에 없다."""\n', text, count=1)
    text = text.replace("HERE = Path(__file__).resolve().parent\nif str(HERE) not in sys.path:\n    sys.path.insert(0, str(HERE))\n"
                        "from show_result import compare, counts, error, note, read_table, table  # noqa: E402\nimport condition_tools as C  # noqa: E402\n",
                        "import json\n\nHERE = Path(__file__).resolve().parents[2]\nfrom app.utils.results import compare, counts, error, note, read_table, table  # noqa: E402\n"
                        "from app.utils import condition_tools as C  # noqa: E402\n")
    for tool in ('sop_tools as S', 'judge_tools as T'):
        text = text.replace(f'import {tool}  # noqa: E402', f'from app.utils import {tool}  # noqa: E402')
    text = re.sub(r"NAMES = \[.*?\]\n", '', text, count=1, flags=re.S)
    text = re.sub(r"\n\ndef step\(no, slots=\(\), run=None\):\n    return dict\(.*?\)\n", '\n', text, count=1)
    text = text.replace("[sys.executable, 'check.py']", "[sys.executable, '-m', 'app.utils.check']").replace("'python check.py 출력'", "'python run.py check 출력'")
    if 'import subprocess' not in text or 'NAMES[' in text or 'show_result' in text:
        raise RuntimeError(f'{key}: 결과 화면 단계 원본의 꼴이 바뀌었습니다 — build_session3_projects.actions_source를 그 꼴에 맞춥니다.')
    text = convert(text)
    for old, new, needed in PATCHES:
        if old not in text and needed(key):
            raise RuntimeError(f'{key}: 결과 화면 원본에 「{old[:40]}」가 없습니다 — actions_source의 PATCHES를 맞춥니다.')
        text = text.replace(old, new)
    text += SHORT_SRC + f'\nINCIDENT = {incident!r}\nLABEL = {LABEL!r}\n' + PREVIOUS
    rows = ''.join(f'    {cmd!r}: ({label!r}, guarded(keep_previous({fn}))),\n' for cmd, label, fn in COMMANDS[key])
    return text + '\n\nCOMMANDS = {\n' + rows + '}\n'


SHORT_SRC = """

def short(j):
    # 판정 한 칸 — 「제외(R1 · 미확인 R4)」 · 「유지(경고 R3 · 감점 R2)」. 판정과 같은 이름의 사유 낱말은 되풀이하지 않는다.
    parts = [('' if k == j['status'] else k + ' ') + ','.join(h['rule_id'] for h in j[key]) for k, key in (('경고', 'warnings'), ('감점', 'penalties'), ('제외', 'exclusions')) if j[key]]
    if j['unknown']:
        parts.append('미확인 ' + ','.join(u['rule_id'] for u in j['unknown']))
    return j['status'] + ('(' + ' · '.join(parts) + ')' if parts else '')
"""
LABEL = {'forecast_ts1': '조치 후 예측 유온(℃)', 'forecast_ps1': '조치 후 예측 토출 압력(bar)', 'fan100_hours': '팬 100 % 연속 시간(h)'}
JUDGES = lambda key: key in JUDGE
PATCHES = [   # (원본 글, 새 글, 그 글이 있어야 하는 랩)
    ("'관계' not in t and '설비_연결' not in t", "'relations.csv' not in t and 'equipment_links.csv' not in t", lambda key: key == 'integrated-03-criteria'),   # classify는 조건 분류만 판정
    ("['경보', '설비', 'fan100_hours', '값이 없는 까닭']", "['경보', '설비', '팬 100 % 연속 시간(h)', '값이 없는 까닭']", JUDGES),
    ("near.append([name, ", "near.append([LABEL.get(name, name), ", JUDGES),
    ("        first = next(iter(sorted({r['사례 / 후보'].split(' / ')[0] for r in expected_rows()})), None)\n", "        first = INCIDENT\n", JUDGES),
    ("            part = md.split(f'## {first}', 1)[1].split('\\n## ', 1)[0]\n", "            part = f'## {first}' + md.split(f'## {first}', 1)[1].split('\\n## ', 1)[0]\n", JUDGES),
    ('C.short(', 'short(', lambda key: key not in JUDGE),
]


def tool_source(name, convert):
    text = convert((BJ.PROVIDED_SRC/name).read_text(encoding='utf-8'))
    return text.replace('from condition_tools import', 'from app.utils.condition_tools import')


def check_messages(key):
    """검사기 본문에서 안내 글만 바꾸는 자리(판정 알고리즘은 그대로) — 기능 이름과 실제 명령 · 결과 파일 이름."""
    return [('python run.py가 판단 표로 만듭니다', 'python run.py classify가 판단 표로 만듭니다'),
            ('python run.py가 빈 틀을 채운 단계까지 만듭니다', 'python run.py ' + ('compare' if key == 'practical-03-review' else 'write') + '가 만듭니다'),
            ("report([('result.json', state", "report([('judgement.json', state")]


def checker_source(key, folder, convert):
    doc, parts = BJ.CHECKS[key]
    provided = sorted(p.relative_to(folder).as_posix() for p in student_files(folder)
                      if p.relative_to(folder).as_posix().startswith(('app/ui/', 'app/utils/')) or p.name == 'run.py')
    head = BJ.check_head(doc).replace('root = Path(__file__).resolve().parent', 'root = Path(__file__).resolve().parents[2]')
    body = convert(''.join(parts))
    for old, new in check_messages(key):
        body = body.replace(old, new)
    return convert(head + BJ.READ_CSV + F.CHOSEN_CHECK) + F.provided_guard(folder, provided) + body


# ───────────── 프로젝트 쓰기 ─────────────
EXTRA_RULES = {
    'integrated-03-criteria': ('- 학생이 AI와 채우는 파일: `app/features/`의 판단 표 셋(`condition_classes.csv` · `relations.csv` · `equipment_links.csv`), `condition_table.csv`, '
                               '`decisions.csv`, `expected.csv`, `requirements.md`. 「제공 빈 틀」 표시가 있는 파일은 바로 고쳐 채운다.\n'
                               '- `output/sop.json`과 결과 화면은 `python run.py <기능>`이 판단 표로 쓴다. 직접 쓰지 않는다. 파일의 모양은 `data/contract.md`에 있다.'),
    'practical-02-conditions': ('- 학생이 AI와 채우는 파일: `app/features/`의 `condition_table.csv` · `approvals.csv` · `decisions.csv` · `expected.csv` · `judgement_record.md`. '
                                '「제공 빈 틀」 표시가 있는 파일은 바로 고쳐 채운다.\n- 결과 화면은 `python run.py <기능>`이 쓴다. 파일의 모양은 `data/contract.md`에 있다.'),
    'integrated-03-judge': ('- 학생이 AI와 채우는 파일: `app/features/`의 `gap_rule.py` · `compare_rule.py`(빈 함수), `decisions.csv` · `expected.csv` · `review.md`. '
                            '「제공 빈 틀」 표시가 있는 파일은 바로 고쳐 채운다. 규칙은 조건표에서 읽으므로 함수에 다시 적지 않는다.\n'
                            '- `output/judgement.json`과 결과 화면은 `python run.py <기능>`이 쓴다. 직접 쓰지 않는다. 파일의 모양은 `data/contract.md`에 있다.'),
    'practical-03-review': ('- 학생이 AI와 채우는 파일: `app/features/`의 `gap_rule.py` · `compare_rule.py`(빈 함수), `decisions.csv` · `expected.csv` · `review.md`. '
                            '「제공 빈 틀」 표시가 있는 파일은 바로 고쳐 채운다. 규칙은 조건표에서 읽으므로 함수에 다시 적지 않는다.\n'
                            '- `output/action_review.json` · `output/action_review.md`와 결과 화면은 `python run.py <기능>`이 쓴다. 직접 쓰지 않는다. 파일의 모양은 `data/contract.md`에 있다.'),
}


OUTSIDE = {
    'integrated-03-criteria': '설비 모델(`data/model/`)을 고치거나 그래프 DB에 적재하는 일, 원문에서 조건을 자동으로 뽑는 일, 조건표로 원천 기록을 판정하고 견주는 기능',
    'practical-02-conditions': 'SOP 구조 전체(적용 · 금지 · 수행 단계 · 완료 · 승인)를 만드는 일, 원천 기록에서 판단 입력을 만들고 후보를 견주는 기능',
    'integrated-03-judge': '조건표 · SOP 구조를 고치는 일, 비교 산식을 바꾸는 일, 원문에서 작업 조건을 뽑는 일, 실제 설비 조작과 실행 승인',
    'practical-03-review': '조건표 · SOP 구조를 고치는 일, 비교 산식을 바꾸는 일, 원문에서 작업 조건을 뽑는 일, 실제 설비 조작과 실행 승인',
}


def agent_rules(key, L):
    """랩별 작업 경계 — 채울 파일 · 정할 지점의 이름(답 없음) · 범위 밖."""
    points = ' · '.join(f'「{name}」' for name, _ in L['decide'])
    return (EXTRA_RULES[key] + f'\n- 정할 지점: {points}. `app/features/decisions.csv`의 지점 칸에 이 이름을 그대로 쓴다. 이 지점은 학생에게 근거와 선택을 먼저 묻고, '
            '다 해 달라는 요청에도 대신 정하지 않는다. 학생이 근거와 선택을 말하기 전에는 그 지점에 걸린 결과를 만들지 않는다.'
            f'\n- 이번 범위 밖: {OUTSIDE[key]}.')


def contract_text(key, L):
    text = L['files']['입출력_계약.md']
    given = L['files'].get('입력/README.md')
    text = text.replace('조건표는 다음 실습의 판정 기능이 그대로 읽는 입력이다. 열 이름을 바꾸면 다음 단계에서 읽지 못한다.',
                        ('3회차 조치 검토 결과 실습' if key == 'practical-02-conditions' else '판단 기능 만들기 실습') + '의 판정 기능이 조건표를 이 꼴 그대로 읽는다. 열 이름을 바꾸면 그 기능이 읽지 못한다.')
    if key == 'integrated-03-criteria':
        given = '제공된 설비 모델(2회차 그래프 구현 실습과 같은 모델) — 설비 7대의 schema.json · graph.json — 과 그 설비 대장(입력/자료/설비_대장.csv)입니다. 이 폴더는 읽기만 합니다.\n'
    if given:
        given = given.replace('조건표의 형식은 입출력_계약.md에 있습니다. ', '')
        text = text.replace('키의 뜻은 `입력/README.md`에 있다', '키의 뜻은 아래 「제공 입력」에 있다')
        text = text.rstrip('\n') + '\n\n## 제공 입력 (`입력/`)\n\n' + given
    return text


def build_project(key, files, folder, work):
    """기존 구조 정의 → 새 프로젝트. 돌려주는 값 = (기존 랩 정의 L, 가이드 단계 목록, 기존 임시 폴더)."""
    import session3_project_guides as G
    convert = converter(key)
    old = Path(work)/'old'/BJ.LABS[key].name
    L = old_lab(key, files, old)
    raw = converter(key, prose=False)
    for name, core in BJ.DATA[key]:
        write(folder/'data'/raw(name), raw(files[core]))
    if key == 'integrated-03-criteria':
        schema, graph, assets = model_inputs()
        for name, value in (('schema.json', schema), ('graph.json', graph)):
            write(folder/'data/model'/name, P.convert(json.dumps(value, ensure_ascii=False, indent=2) + '\n'))
        write(folder/'data/model/equipment.csv', P.convert(assets))
    if key in JUDGE:
        write(folder/'data/criteria/condition_table.csv', convert(CR.table_csv(CR.BASE[1])))
        write(folder/'data/criteria/sop.json', convert(CR.sop_json(*CR.BASE)))
    write(folder/'data/contract.md', convert(contract_text(key, L)), bom=True)
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            write(folder/convert(name), convert(text))
    for name in BJ.PROVIDED[key]:
        write(folder/'app/utils'/name, tool_source(name, convert))
    utilities, ui = P.result_sources()
    write(folder/'app/utils/results.py', utilities)
    write(folder/'app/ui/render.py', ui)
    write(folder/'app/utils/actions.py', actions_source(key, L, convert, BJ.incident_line(files).split('`')[1]))
    write(folder/'run.py', P.RUN)
    write_metadata(folder, L['title'], G.PURPOSE[key], extra_rules=agent_rules(key, L))
    write(folder/'app/utils/check.py', checker_source(key, folder, convert))
    steps = G.steps(key, L, files)
    F.write_guide(folder, G.render(L['title'], key, L, files, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps, old


def validate(key, folder, L, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    course, n = COURSE[key]
    item = entry(key, course, f'온라인 {n}회차', L['title'], VERSION, folder, guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    problems = check_zip(folder.with_suffix('.zip'), folder)[0]
    if problems:
        raise ValueError(problems)
    verify_lab(item)
    return item


# ───────────── 학생용 완성본(별도 묶음, 기본 갈래 채움 — 유료 AI 호출 없음) ─────────────
RECORD = {'integrated-03-criteria': '요구사항.md', 'practical-02-conditions': '판단기록.md', 'integrated-03-judge': '기대결과.md', 'practical-03-review': '기대결과.md'}
RUNS = {'integrated-03-criteria': ['classify', 'relations', 'links', 'rules', 'provenance', 'check'],
        'practical-02-conditions': ['rules', 'provenance', 'approvals', 'check'],
        'integrated-03-judge': ['inputs', 'compare', 'write', 'cases', 'check'],
        'practical-03-review': ['inputs', 'compare', 'cases', 'check']}


def base_answers(key, L):
    """기존 정답 토글이 단계 차례로 채우던 기본 갈래(강사 참조 criteria.py · judge_actions.py) — {기존 경로: 내용}, 뒤 단계가 같은 파일을 다시 쓰면 그 판."""
    out = {}
    for s in L['steps']:
        out.update(((s.get('answer') or {}).get('apply') or {}))
    import run_reference as RR
    out['결과/' + RECORD[key]] = RR.record_text(key, L)
    return out


def run_commands(folder, commands):
    logs = {}
    for cmd in commands:
        p = subprocess.run([sys.executable, '-B', 'run.py', cmd, '--no-open'], cwd=folder, capture_output=True, text=True, encoding='utf-8')
        logs[cmd] = {'exit': p.returncode, 'output': (p.stdout + p.stderr).strip()}
        if p.returncode:
            raise RuntimeError(f'{folder.name}: python run.py {cmd} 실패\n{logs[cmd]["output"][:3000]}')
    return logs


def completed(key, starter, destination, work, L):
    convert = converter(key)
    folder = Path(work)/'completed'/starter.name
    shutil.copytree(starter, folder)
    for rel, text in base_answers(key, L).items():
        write(folder/convert(rel), convert(text))
    commands = RUNS[key]
    write_metadata(folder, L['title'] + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단마다 한 가지를 골라 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.',
                   command='python run.py', extra_rules=agent_rules(key, L))
    readme = (folder/'README.md').read_text(encoding='utf-8-sig')
    run_lines = '\n'.join(f'python run.py {c}' for c in commands)
    write(folder/'README.md', readme.replace('실행: `python run.py`\n', f'실행(차례로):\n\n```text\n{run_lines}\n```\n'), bom=True)
    logs = run_commands(folder, commands)
    destination.mkdir(parents=True, exist_ok=True)
    archive = Path(destination)/(starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    write(Path(work)/'completed-execution.json', json.dumps(logs, ensure_ascii=False, indent=2) + '\n')
    return archive, logs


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('lab', choices=sorted(KEYS))
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더; 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 그 랩 하나만 정본 자리에 바꿔 끼우고 등록')
    parser.add_argument('--completed', action='store_true')
    args = parser.parse_args()
    key = KEYS[args.lab]
    files, _ = DC.build()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT/'작업').resolve()):
            parser.error('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent/PROJECT[key]
        if folder.exists():
            parser.error('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        with tempfile.TemporaryDirectory(dir=WORK, prefix='old-') as temp:
            L, steps, _ = build_project(key, files, folder, temp)
            validate(key, folder, L, steps)
            if args.completed:
                archive, _ = completed(key, folder, parent, temp, L)
                shutil.copyfile(Path(temp)/'completed-execution.json', parent/(PROJECT[key] + '-completed-execution.json'))
        print(folder)
        return 0
    course, n = COURSE[key]
    target_parent = F.OUT/course/'실습'/f'{n}회차'/'랩'
    with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
        source = Path(temp)/PROJECT[key]
        L, steps, _ = build_project(key, files, source, temp)
        validate(key, source, L, steps)
        archive = completed(key, source, Path(temp), temp, L)[0] if args.completed else None
        target = target_parent/source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        for suffix in ('_guide.html', '.zip'):
            shutil.copyfile(source.parent/(source.name + suffix), target.parent/(target.name + suffix))
        register([validate(key, target, L, steps)])
        if archive:
            done = target_parent.parent/'완성본'/archive.name
            done.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, done)
    print(target)
    return 0


if __name__ == '__main__':
    sys.exit(main())
