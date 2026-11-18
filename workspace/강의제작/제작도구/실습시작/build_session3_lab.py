"""통합반 3회차 두 랩(v5-lab) — 조치 기준 만들기 action-criteria-lab · 판단 기능 만들기 judgement-lab. 지정한 랩 하나만 만든다.

build_session3_projects.py criteria|judge가 이 파일을 부른다(실전반 두 랩 conditions · review는 그 파일의 옛 경로 그대로).
- 자료: data_session3_lab.py(원자료 코어의 부분 — 실습 랩 규모). 제공 설비 모델은 통합 2회차 그래프 랩과 같은 생성기 함수에서 받는다
  (build_labs.reference_model · GRAPH_LAB_INPUT['통합반'] · student_schema · session2_project.convert — 산출물/ 폴더를 입력으로 읽지 않는다).
- 제공 코드: session3_lab/의 파일을 그대로 학생 폴더 app/utils/에 쓴다(그 폴더의 파일이 곧 학생 파일). 결과 화면 · run.py는 2회차 새 구조와 같은 원본.
- 판단 기능 랩의 제공 조치 기준(data/criteria/)은 조치 기준 랩을 강사 참조 기본 갈래로 채워 실제로 돌린 output/ 두 파일이다.
- 가이드 원고: session3_lab_guides.py. 강사 참조(갈래 채움 · 기대 판정): reference/session3/lab_answers.py. 시험: reference/session3/project_trials.py.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile

import build_labs as B
import build_session2_projects as B2
import data_session2 as D2
import data_session3_lab as D
import lab_frame as F
import session2_project as P
from lab_package import ROOT, entry, pack, register, student_files, write_zip
from project_layout import errors, write_metadata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'reference/session3'))
import lab_answers as A  # noqa: E402

VERSION = 'v6-lab'   # 2026-11-19: 독립 검토(판정/검토_통합3_*_v5.json) 고침 — 쿨러 핀 세척 예측을 덱 · 사실표와 같게, 복수 조건 규칙, 기대를 걸린 규칙까지 대조, 「쓰는 사람에 따라 갈리는 답」을 1순위로 내줄 기준으로. 앞 판 v5-lab 2026-11-18: 실습 랩 규모로 다시 만듦(코딩랩 K-3) — 제공 설비 모델은 2회차 v31의 다섯 대, 정할 지점은 랩마다 하나, 이름은 3회차 덱과 장부. 작업 2026-11-17_코딩랩-원리중심-학생결정자
SRC = HERE / 'session3_lab'
WORK = ROOT / '작업/검사/session3-projects'
DEST = F.OUT / '통합반/실습/03회차/랩'
PROJECT = {'criteria': 'action-criteria-lab', 'judge': 'judgement-lab'}
ID = {'criteria': 'integrated-03-criteria', 'judge': 'integrated-03-judge'}
TITLE = {'criteria': '작업 절차와 판단 조건을 연결해 조치 기준 만들기', 'judge': '설비 조건별 최적의 조치를 비교하는 판단 기능 만들기'}
MARK = F.MARK
DECISIONS_HEAD = (f'# {MARK} — 원자료만으로 하나로 정해지지 않아 내가 정하는 지점마다 한 줄. 이 # 줄들은 지우지 않아도 됩니다.\n'
                  '# 지점 = 정할 지점의 이름(미리 적혀 있음) · 고른_것 = 내가 정한 것 한 줄 · 근거 = 그렇게 정한 내 이유와, 그 결정을 좌우해 열어 본 원문 줄 파일:줄'
                  '(꼴: data/파일.csv:12, 여럿이면 「 · 」로 잇기) · 바뀌는_답 = 이 선택으로 결과가 어떻게 달라지는지\n')
DECISIONS_COLUMNS = '지점,고른_것,근거,바뀌는_답\n'
STATEMENT_HEAD = ('# 「비교 기준 문장」 줄은 고르는 지점이 아니라 내 말로 쓰는 줄입니다. 고른_것 칸에 내가 쓴 문장을, 근거 칸에 읽은 줄(파일:줄)을 적고 바뀌는_답 칸은 비워 둡니다.\n')
TEMPLATES = {
    'criteria': {
        'sop_items.csv': F.blank_csv(['sop_id', '항목', '원문', '규칙'],
                                     '한 줄이 조건 문장 묶음 하나 · sop_id = data/targets.csv의 SOP ID(같은 문장이 여러 SOP에 걸리면 ;로 잇는다) · '
                                     '항목 = 적용 대상 · 작업 전제 조건 · 안전 조건 · 준비사항 · 금지 사항 · 제한 · 담당 역할 · 완료 확인 기준 가운데 하나'
                                     '(수행 단계는 제공 코드가 매뉴얼의 번호 줄을 옮기므로 적지 않는다) · 원문 = 근거 문장 번호(python run.py 화면의 「매뉴얼 문장 번호」 표의 번호, 여럿이면 ;) · '
                                     '규칙 = 이 조건을 옮긴 결정표의 rule_id(여럿이면 ;, 규칙으로 옮기지 않았으면 빈칸)'),
        'relations.csv': F.blank_csv(['type', 'from', 'to', '원문'],
                                     '한 줄이 관계 하나 · type = MITIGATED_BY(고장 유형 → 완화 조치 SOP) · REMEDIED_BY(고장 유형 → 근본 조치 SOP) · ADDRESSES(SOP → 그 SOP가 맞는 원인) 가운데 하나 · '
                                     'from · to = 양 끝 ID(고장 유형 · 원인은 data/failure_modes.csv, SOP는 data/targets.csv의 ID) · 원문 = 근거 문장 번호(여럿이면 ;)'),
        'scope.csv': F.blank_csv(['sop_id', '구성_요소', '설비', '까닭'],
                                 'SOP마다 한 줄 · sop_id = data/targets.csv의 SOP ID · 구성_요소 = 이 SOP가 다루는 구성 요소의 이름(설비 모델에 적힌 이름, 여럿이면 ;) · '
                                 '설비 = 이 SOP를 걸 설비 ID(설비 모델의 ID, 여럿이면 ;, 걸 설비가 없으면 빈칸) · 까닭 = 그렇게 건 까닭과 걸지 않은 설비의 까닭 한 줄'),
        'decision_table.csv': F.blank_csv(['rule_id', '결과', '감점_만원', '적용_대상', '입력', '연산자', '기준값', '단위', '이유', '출처'],
                                          '조건 하나가 한 줄 · rule_id = 규칙 이름(같은 rule_id의 줄은 한 규칙의 조건들이고 모두 맞아야 그 규칙이 맞는다) · 결과 = 제외 · 감점 · 경고 가운데 하나 · '
                                          '감점_만원 = 결과가 감점일 때만 금액 · 적용_대상 = 이 규칙을 댈 SOP ID(여럿이면 ;) · 입력 = 입력 데이터 이름(in:plc-mode 운전 모드 · '
                                          'in:fan100-hours 팬 100 % 연속 운전시간 · in:forecast-ts1 조치 후 예측 유온 · in:ts1 유온 · in:ce 냉각 효율) · 연산자 = >= > <= < == != 가운데 하나 · '
                                          '기준값 · 단위 = 견줄 값과 그 단위 · 이유 = 판정에 붙일 문장 · 출처 = 근거가 적힌 매뉴얼 절 번호(여럿이면 ;)'),
        'expected.csv': F.blank_csv(['사례', '후보', '기대_판정', '기대_규칙', '근거'],
                                    '한 줄에 확인 사례 하나의 후보 하나, 결정표를 대기 전에 정한 값 · 사례 = data/check_cases.csv의 경보_ID · 후보 = data/targets.csv의 SOP ID · '
                                    '기대_판정 = 허용 · 제외 · 후보 아님 가운데 하나(후보 아님 = 그 경보의 고장 유형 · 확인된 원인 · 설비에 걸리지 않는 SOP) · '
                                    '기대_규칙 = 그 후보에 걸릴 규칙의 rule_id(맞을 규칙과, 값이 비어 확인되지 않은 조건으로 남을 규칙. 여럿이면 ;, 없으면 빈칸 — 결정표를 만든 뒤에 채운다) · 근거 = 파일:줄(여럿이면 ;)'),
        'decisions.csv': DECISIONS_HEAD + DECISIONS_COLUMNS + '적용 범위,,,\n',
        'requirements.md': '# 요구사항\n\n## 목적과 답을 쓸 사람\n\n## 확인할 질문과 쓸 자료\n\n## 지킬 조건 · 범위 밖\n\n## 대조 결과 · 고친 점\n\n## 저장 시점 · 확인하지 못한 점\n',
    },
    'judge': {
        'compare_rule.py': ('"""' + MARK + ' — 정할 지점 「쓰는 사람에 따라 갈리는 답」을 구현하는 함수입니다.\n\n'
                            '허용된 후보는 경고나 감점이 붙어도 모두 비교값을 냅니다. 제공 코드(app/utils/actions.py)가 경보마다 비교값이 나온 후보 목록으로 이 함수를 부르고,\n'
                            '돌려준 후보는 1순위로 내주지 않고 다른 후보 뒤에 까닭과 함께 보입니다. 비교값과 비교값 순위는 그대로 남습니다.\n'
                            "kept(읽기만): [{'sop': 후보 ID, 'warnings': 그 후보에 붙은 경고 규칙 이름들(값이 비어 경고로 남은 규칙 포함), 'penalties': 맞은 감점 규칙 이름들}, ...]\n"
                            '돌려줄 값: {뒤에 보일 후보 ID: 까닭 글} — 뒤로 미룰 후보가 없으면 빈 dict\n"""\n\n\n'
                            "def hold_back(kept):\n    raise NotImplementedError('빈 틀: app/features/compare_rule.py hold_back')\n"),
        'expected.csv': F.blank_csv(['사례_종류', '사례', '후보', '기대_판정', '기대_규칙', '근거'],
                                    '한 줄에 경보 하나의 후보 하나, 실행 전에 정한 값 · 사례_종류 = 정상 · 경계 · 복수 조건 · 모두 제외 · 필수값 누락 가운데 하나(다섯 종류마다 경보를 하나 이상) · '
                                    '사례 = data/alarms.csv의 경보_ID · 후보 = 조치 기준의 SOP ID · 기대_판정 = 허용 · 제외 · 후보 아님 가운데 하나'
                                    '(후보 아님 = 그 경보의 고장 유형 · 확인된 원인 · 설비에 걸리지 않는 SOP) · '
                                    '기대_규칙 = 그 후보에 걸릴 규칙의 rule_id(맞을 규칙과, 값이 비어 확인되지 않은 조건으로 남을 규칙. 여럿이면 ;, 없으면 빈칸) · 근거 = 파일:줄(여럿이면 ;)'),
        'decisions.csv': DECISIONS_HEAD + STATEMENT_HEAD + DECISIONS_COLUMNS + '쓰는 사람에 따라 갈리는 답,,,\n비교 기준 문장,,,\n',
        'review.md': '# 기대 결과와 실제 대조\n\n## 질문 · 쓸 자료 · 지킬 조건\n\n## 기대 판정과 실제 결과 · 고친 점\n\n## 손으로 해 본 계산\n\n## 저장 시점 · 확인하지 못한 점\n',
    },
}
EXTRA_RULES = {
    'criteria': ('- 학생이 AI와 채우는 파일: `app/features/`의 `sop_items.csv` · `relations.csv` · `scope.csv` · `decision_table.csv` · `expected.csv` · `decisions.csv` · `requirements.md`. '
                 '`output/sop.json`과 결과 화면은 `python run.py <기능>`이 쓴다. 직접 쓰지 않는다.\n'
                 '- 정할 지점은 「적용 범위」 하나다. 매뉴얼에 적용 범위가 없어 SOP를 어느 설비에 걸지는 학생이 정한다. `scope.csv`와, 적용 범위에 따라 달라지는 경보의 '
                 '`expected.csv` 줄은 학생이 `decisions.csv`의 「적용 범위」 줄을 정한 뒤에만 쓴다. 그 전에는 선택지와 각 선택의 결과를 보이고 묻는다.\n'
                 '- `decisions.csv`의 고른_것 · 근거와 `expected.csv`의 기대 판정 · 기대 규칙에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 판정 후보도 된다). '
                 '기대 판정 후보는 원자료에서 찾아 근거 줄과 함께 내고, `python run.py`가 낸 판정을 기대 판정으로 옮기지 않는다.\n'
                 '- 한 번에 요청받은 파일 하나만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. 「다 해 줘」처럼 여러 기능을 한꺼번에 부탁받아도 파일 하나를 고친 뒤 멈추고 다음 기능을 할지 묻는다.\n'
                 '- 이번 범위 밖: 설비 모델(`data/model/`)을 고치는 일, 원문에서 조건을 자동으로 뽑는 일, 허용 후보를 손익으로 견주는 일.'),
    'judge': ('- 학생이 AI와 채우는 파일: `app/features/`의 `compare_rule.py`(빈 함수) · `expected.csv` · `decisions.csv` · `review.md`. '
              '`output/judgement.json`과 결과 화면은 `python run.py <기능>`이 쓴다. 직접 쓰지 않는다. 규칙은 결정표에서 읽으므로 함수에 다시 적지 않는다.\n'
              '- 정할 지점은 「쓰는 사람에 따라 갈리는 답」 하나다. 경고가 붙은 허용 후보를 1순위로 내줄지는 이 답을 누가 쓰는지에 달려 있고 학생이 정한다. '
              '`compare_rule.py`는 학생이 `decisions.csv`의 「쓰는 사람에 따라 갈리는 답」 줄을 정한 뒤에만 채운다. 그 전에는 선택지와 각 선택의 결과를 보이고 묻는다.\n'
              '- `decisions.csv`의 「비교 기준 문장」 줄은 정할 지점이 아니라 학생이 자기 말로 쓰는 줄이다. 학생이 말한 문장을 다듬지 않고 받아 적는다. 문장을 지어 주거나 고친 안을 내지 않고, '
              '학생이 물으면 `data/metrics/metric_definitions.md`의 근거 줄과 그 문장이 그 줄과 맞지 않는 곳만 짚는다.\n'
              '- `decisions.csv`의 고른_것 · 근거와 `expected.csv`의 기대 판정 · 기대 규칙에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 판정 후보도 된다). '
              '기대 판정 후보는 원자료에서 찾아 근거 줄과 함께 내고, `python run.py`가 낸 판정을 기대 판정으로 옮기지 않는다.\n'
              '- 한 번에 요청받은 파일 하나만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. 「다 해 줘」처럼 여러 기능을 한꺼번에 부탁받아도 파일 하나를 고친 뒤 멈추고 다음 기능을 할지 묻는다.\n'
              '- 이번 범위 밖: 결정표와 SOP 구조(`data/criteria/`)를 고치는 일, 비교 산식을 바꾸는 일, 실제 설비 조작과 실행 승인.'),
}
CONTRACT = {
    'criteria': '''# 결과 파일의 꼴

`python run.py rules`가 `output/`에 두 파일을 씁니다. 판단 기능 만들기 실습이 이 꼴을 그대로 읽습니다.

## output/sop.json

- `model`: 쓴 설비 모델의 자리
- `failure_modes`: 고장 유형마다 `id` · `name` · `component` · `causes`(원인의 `id` · `name`)
- `sops`: SOP마다 `id` · `name` · `kind`(원격 조치 · 정비 요청) · `source_section` · `steps`(수행 단계 — 매뉴얼 번호 줄의 `order` · `text` · `line`) ·
  `items`(조건 문장 — `item` 항목 · `refs` 원문 번호 · `text` 원문 인용 · `rules` 옮긴 규칙) · `components` · `assets`(건 설비) · `scope_reason`
- `relations`: 관계마다 `type` · `from` · `to` · `source` · `text`

## output/decision_table.csv

`app/features/decision_table.csv`와 같은 내용입니다. 열 이름과 쓸 수 있는 값은 그 파일 첫 줄에 있습니다.
''',
    'judge': '''# 결과 파일의 꼴

`python run.py write`가 `output/judgement.json`을 씁니다.

- `criteria`: 쓴 조치 기준의 자리
- `decisions`: 정한 것(1순위로 내줄 기준)과 비교 기준 문장
- `events`: 경보마다
  - `id` · `asset`
  - `candidates`: 조치 후보마다 `sop` · `status`(허용 · 제외) · `hits`(맞은 규칙 — `rule_id` · `result` · `reason` · `source` · `conditions`) ·
    `unknown`(확인되지 않은 조건이 있는 규칙 — `missing`에 값이 빈 입력) · `comparison`(비용 · 생산 · 품질 · 에너지 · 감점 · 비교값, 견주지 않았으면 null) ·
    `not_compared`(값이 없어 견주지 못한 까닭) · `rank`(비교값 순위) · `held_back`(1순위로 내주지 않고 뒤에 보이는 까닭)
  - `not_candidates`: 후보가 아닌 SOP와 까닭
  - `order`: 내줄 차례 · `top`: 1순위로 내줄 후보

## 내 조치 기준을 쓸 때

조치 기준 만들기 실습의 `output/sop.json`과 `output/decision_table.csv`를 `app/features/criteria/`에 함께 복사하면 그 기준으로 판정합니다. 제공 기준 `data/criteria/`는 그대로 둡니다.
''',
}
PROVENANCE = '''# 제공된 조치 기준의 근거

이 폴더의 `decision_table.csv`와 `sop.json`은 `hm8_manual.md`의 작업 절차와 판단 조건을 옮긴 조치 기준입니다. 조치 기준 만들기 실습의 결과 파일과 같은 꼴이고, 이번 실습의 판정 결과가 아닙니다.

- 규칙: 매뉴얼의 조건 가운데 그때의 값과 견줘야 하는 것만 결정표의 규칙으로 옮겼습니다. 규칙마다 출처 칸에 매뉴얼 절이 있습니다.
- 고장 유형과 원인: 쿨러 핀 세척은 원인이 쿨러 핀 오염일 때, 쿨러 팬 점검은 원인이 팬 구동 불량일 때 쓰는 조치 방법으로 이었습니다.
- 적용 범위: 매뉴얼에 적용 범위가 없어, SOP가 다루는 구성 요소(쿨러 팬 · 오일 쿨러 · 주 펌프)가 모두 설비 모델에 있는 설비에만 걸었습니다. 건 설비는 `sop.json`의 `assets`에 있습니다. `sop.json`의 `model` 값은 조치 기준을 만들 때 쓴 설비 모델의 자리이고 이 폴더에는 그 모델이 없습니다.
'''
MODEL_NOTE = '''# 제공된 설비 모델

이 폴더의 `schema.json`과 `graph.json`은 2회차 그래프 구현 실습의 제공 모델과 같은 설비 모델입니다. 2라인 유압 파워팩 다섯 대의 원자료와 현장 메모로 만든 것이고, 이번 실습은 이 모델을 읽기만 합니다.

- 구성 요소(Component)는 설비 안의 구성 요소 자리입니다. 설비마다 다르게 적혀 있던 이름은 하나로 맞추고 원래 이름은 aliases에 남겼습니다.
- 설비의 식별자는 설비 코드(HYD-01 …)이고, 구성 요소의 식별자는 설비 코드 뒤에 자리 이름을 붙인 것입니다.
- 센서 · 물리량 · 부품 · 실물도 들어 있지만 이번 실습이 쓰는 것은 설비와 그 구성 요소입니다.
'''
JUDGE_DATA = ('hm8_manual.md', 'night_operation_rule.md', 'alarms.csv', 'metrics/metric_definitions.md', 'metrics/business_values.json', 'metrics/candidate_settings.csv')
RUNS = {'criteria': ['sop', 'relations', 'scope', 'rules', 'check'], 'judge': ['judge', 'compare', 'write', 'cases', 'check']}


def write(path, text, bom=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8-sig' if bom else 'utf-8', newline='\n')


def model_files():
    """설비 모델 — schema.json · graph.json은 통합 2회차 그래프 랩 제공 모델과 같은 바이트. {이름: 글}."""
    with D2.for_course('통합반'):
        D2.require('통합반')
        schema, graph = B.reference_model(False, B.GRAPH_LAB_INPUT['통합반'])
        out = {name: P.convert(json.dumps(value, ensure_ascii=False, indent=2) + '\n') for name, value in (('schema.json', B.student_schema(schema)), ('graph.json', graph))}
    out['provenance.md'] = MODEL_NOTE      # 두 json은 2회차와 같은 바이트, 설명은 이 랩의 글(2회차 글은 이 랩에 없는 원자료 줄과 적재를 가리킨다)
    return out


def provided(kind, folder):
    utilities, ui = B2.result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    names = {'criteria': ['rules.py', 'sop.py'], 'judge': ['rules.py', 'compare.py']}[kind]
    for name in names:
        write(folder / 'app/utils' / name, (SRC / name).read_text(encoding='utf-8'))
    write(folder / 'app/utils/actions.py', (SRC / f'{kind}_actions.py').read_text(encoding='utf-8'))
    write(folder / 'run.py', B2.run_source())


def checker(kind, folder):
    names = sorted(p.relative_to(folder).as_posix() for p in student_files(folder)
                   if p.relative_to(folder).as_posix().startswith(('app/ui/', 'app/utils/', 'data/')) or p.name == 'run.py')
    write(folder / 'app/utils/check.py', F.provided_guard(folder, names) + (SRC / f'{kind}_check.py').read_text(encoding='utf-8'))


def run(folder, commands):
    logs = {}
    for cmd in commands:
        p = subprocess.run([sys.executable, '-B', 'run.py', cmd, '--no-open'], cwd=folder, capture_output=True, text=True, encoding='utf-8')
        logs[cmd] = {'exit': p.returncode, 'output': (p.stdout + p.stderr).strip()}
        if p.returncode:
            raise RuntimeError(f'{Path(folder).name}: python run.py {cmd} 실패\n{logs[cmd]["output"][:3000]}')
    return logs


def fill(kind, folder, data, branch=None):
    """강사 참조 한 갈래로 app/features를 채운다."""
    fn, base = (A.criteria_fill, A.BASE_SCOPE) if kind == 'criteria' else (A.judge_fill, A.BASE_ORDER)
    if kind == 'judge':      # 근거 줄을 제공 조치 기준의 실제 줄로 적는다
        data = {**data, **{f'criteria/{n}': (Path(folder) / 'data/criteria' / n).read_text(encoding='utf-8') for n in ('decision_table.csv', 'sop.json')}}
    for name, text in fn(branch or base, data, TEMPLATES[kind]).items():
        write(Path(folder) / 'app/features' / name, text)


def build(kind, folder, data, work, guide=True):
    """랩 하나를 folder에 쓴다. 돌려주는 값 = 가이드 단계 목록. guide=False면 가이드를 쓰지 않는다(다른 랩의 제공 입력을 만들 때)."""
    import session3_lab_guides as G
    folder = Path(folder)
    if kind == 'criteria':
        for name in ('hm8_manual.md', 'decision_table_export.txt', 'targets.csv', 'failure_modes.csv', 'check_cases.csv'):
            write(folder / 'data' / name, data[name])
        for name, text in model_files().items():
            write(folder / 'data/model' / name, text)
    else:
        for name in JUDGE_DATA:
            write(folder / 'data' / name, data[name])
        base = Path(work) / 'criteria-base' / PROJECT['criteria']      # 제공 조치 기준 = 조치 기준 랩을 기본 갈래로 채워 돌린 결과
        build('criteria', base, data, work, guide=False)
        fill('criteria', base, data)
        run(base, ['rules', 'check'])
        table = (base / 'output/decision_table.csv').read_text(encoding='utf-8')
        if not table.startswith(f'# {MARK} — '):
            raise ValueError('조치 기준 랩 결정표의 첫 줄이 빈 틀 표시가 아닙니다.')
        write(folder / 'data/criteria/decision_table.csv', table.replace(f'# {MARK} — ', '# 제공 조치 기준의 결정표 — ', 1))      # 채워서 주는 표가 스스로를 빈 틀이라 부르지 않게
        write(folder / 'data/criteria/sop.json', (base / 'output/sop.json').read_text(encoding='utf-8'))
        write(folder / 'data/criteria/provenance.md', PROVENANCE)
    write(folder / 'data/contract.md', CONTRACT[kind], bom=True)
    for name, text in TEMPLATES[kind].items():
        write(folder / 'app/features' / name, text)
    provided(kind, folder)
    write_metadata(folder, TITLE[kind], G.PURPOSE[kind], extra_rules=EXTRA_RULES[kind])
    checker(kind, folder)
    steps = G.steps(kind)
    if guide:
        F.write_guide(folder, G.render(TITLE[kind], G.PURPOSE[kind], steps), ai_turns=sum(int(s['ai']) for s in steps))
    return steps


def validate(kind, folder, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    item = entry(ID[kind], '통합반', '온라인 03회차', TITLE[kind], VERSION, folder, guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    problems = check_zip(folder.with_suffix('.zip'), folder)[0]
    if problems:
        raise ValueError(problems)
    verify_lab(item)
    return item


def completed(kind, starter, destination, work, data):
    """학생용 완성본(실습 ZIP 밖의 별도 묶음) — 강사 참조 기본 갈래로 채워 실제로 실행한다. 유료 AI 호출 없음."""
    folder = Path(work) / 'completed' / starter.name
    shutil.copytree(starter, folder)
    fill(kind, folder, data)
    lines = '\n'.join(f'python run.py {c}' for c in RUNS[kind])
    write_metadata(folder, TITLE[kind] + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 정할 지점마다 한 가지를 골라 적용했으며 고른 것과 이유는 app/features/decisions.csv에 있습니다.',
                   command=lines, extra_rules=EXTRA_RULES[kind])
    logs = run(folder, RUNS[kind])
    Path(destination).mkdir(parents=True, exist_ok=True)
    archive = Path(destination) / (starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    write(Path(destination) / (starter.name + '-completed-execution.json'), json.dumps(logs, ensure_ascii=False, indent=2) + '\n')
    return archive


def generate(kind, dest=None, apply=False, with_completed=False):
    data = D.build()
    WORK.mkdir(parents=True, exist_ok=True)
    if dest is not None:
        parent = Path(dest).resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()):
            raise SystemExit('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent / PROJECT[kind]
        if folder.exists():
            raise SystemExit('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        with tempfile.TemporaryDirectory(dir=WORK, prefix='lab-') as temp:
            steps = build(kind, folder, data, temp)
            validate(kind, folder, steps)
            if with_completed:
                completed(kind, folder, parent, temp, data)
        print(folder)
        return 0
    with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
        source = Path(temp) / 'out' / PROJECT[kind]
        steps = build(kind, source, data, temp)
        validate(kind, source, steps)
        archive = completed(kind, source, Path(temp) / 'done', temp, data) if with_completed else None
        target = DEST / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        for suffix in ('_guide.html', '.zip'):
            shutil.copyfile(source.parent / (source.name + suffix), target.parent / (target.name + suffix))
        register([validate(kind, target, steps)])
        if archive:
            done = DEST.parent / '완성본' / archive.name
            done.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, done)
    print(target)
    return 0
