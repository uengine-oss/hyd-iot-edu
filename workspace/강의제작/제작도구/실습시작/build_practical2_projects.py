"""실전02의 지정 프로젝트 하나만 생성한다(설계 `ontology-lab` · 그래프 `graph-lab`). 다른 과정·회차·강사 참조를 재생성하지 않는다.

통합02 생성기(build_session2_projects.py)와 같은 공용 함수(session2_project · session2_graph_project)를 쓰고,
실전반 차이(제공 설비·부품 모델 위에 공급 연결을 학생이 작성, 그래프 랩에 수정본 반영 없음)만 이 파일에 둔다.
랩 정의·원자료·판단 빈 틀·정답은 기존 판(build_labs.design_practical · graph_lab('실전반'), session2_answers)에서 받는다.

python build_practical2_projects.py ontology --dest 작업/검사/...
python build_practical2_projects.py ontology --apply [--completed]
"""
from pathlib import Path
import argparse
from contextlib import nullcontext
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile

import build_labs as B
import build_session2_projects as S2
import data_session2 as D
import lab_frame as F
from lab_package import ROOT, pack, entry, register, student_files, write_zip
from project_layout import write_metadata, errors, DB_RULE
import session2_project as P
import session2_project_guides as G
import session2_graph_project as GP

DEST = ROOT / 'workspace/강의제작/산출물/실전반/실습/02회차/랩'
VERSION = 'v23-practical'   # 2026-11-12: 공용 원자료 보강(친절한 비고 걷기 · 3라인 계장태그 · 리턴 필터 후보 둘 · 품번 합치기 역할 근거 · 제작 사실 걷기), 제공 모델 카디널리티 표기 · 검사기 카디널리티 검사 · 대조 단추 글자 — 작업 판정/보강_20261112
WORK = ROOT / '작업/검사/practical2-projects'
PR07 = 'purchasing_standard_pr07.md'
LABS = {'ontology': 'ontology-lab', 'graph': 'graph-lab'}
NL = chr(10)


def convert(text):
    """통합02의 경로 변환에 실전반 원자료 하나(구매 기준서 발췌)의 영어 이름을 더한다.
    확장자 없이 적은 원자료 이름(「승인공급사_목록(SCM 등록)」)도 그 파일의 영어 이름으로 바꾼다."""
    text = text.replace(D.PR07_FILE, PR07)
    for name in SOURCE_NAMES:
        stem, suffix = name.rsplit('.', 1)
        text = re.sub(re.escape(stem) + r'(?!\.' + suffix + ')', name, text)
    return P.convert(text)


SOURCE_NAMES = tuple(n for n in D.source_texts(True) if n != D.PR07_FILE)   # 원자료 파일 이름(열 이름과 겹치지 않는다)
KOREAN_NAMES = tuple(n.rsplit('.', 1)[0] for n in SOURCE_NAMES) + (D.PR07_FILE.rsplit('.', 1)[0],)   # 새 프로젝트에 남으면 안 되는 옛 이름


def write(path, text):
    F.write(path, text)


def source_data(folder):
    WORK.mkdir(parents=True, exist_ok=True)
    work = WORK.resolve()
    names = P.NAMES | {D.PR07_FILE: PR07}
    with tempfile.TemporaryDirectory(dir=work, prefix='data-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(work) and raw != work
        D.write_sources(raw, practical=True)
        for path in raw.iterdir():
            write(folder / 'data' / names[path.name], convert(path.read_text(encoding='utf-8-sig')))


def model_files(folder, supply):
    """제공 모델: 설계 랩은 설비·부품 모델(공급 정보 없음), 그래프 랩은 앞 단계 완성 모델(갈래 ㄴ)과 자료 처리 근거."""
    schema, graph = B.reference_model(supply, B.GRAPH_LAB_INPUT['실전반']) if supply else B.reference_model(False, B.PROVIDED_BRANCH)
    for name, value in [('schema.json', B.student_schema(schema)), ('graph.json', graph)]:
        write(folder / 'data/model' / name, convert(json.dumps(value, ensure_ascii=False, indent=2) + '\n'))
    if supply:
        write(folder / 'data/model/provenance.md', convert(B.provided_basis(True)))


def drop_functions(source, names):
    """제공 코드에서 이 랩이 쓰지 않는 함수(통합반 수정본 반영 · 포털 비교 · 질문 3)를 뺀다."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    cut = sorted(((n.lineno - 1, n.end_lineno) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names), reverse=True)
    if len(cut) != len(names):
        raise ValueError(f'뺄 함수를 다 찾지 못했습니다: {sorted(names)}')
    for start, end in cut:
        while end < len(lines) and not lines[end].strip():
            end += 1
        del lines[start:end]
    return ''.join(lines)


def commands_source(commands):
    return '\nCOMMANDS = {\n' + ''.join(f'    {cmd!r}: ({label!r}, {fn}),\n' for cmd, (label, fn) in commands.items()) + '}\n'


def supply_source():
    """공급 정보를 모델에 더하는 제공 코드. 판단 함수는 app/features에서 읽고 모델은 output/에 쓴다."""
    text = convert((P.HERE / 'session2_supply_tool.py').read_text(encoding='utf-8'))
    text = text.replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    text = text.replace("OUT = HERE / 'app/features'", "OUT = HERE / 'app/features'\nOUTPUT = HERE / 'output'")
    for name in ('schema.json', 'graph.json'):
        text = text.replace(f"OUT / '{name}'", f"OUTPUT / '{name}'")
    text = text.replace('OUT.mkdir(exist_ok=True)', 'OUTPUT.mkdir(exist_ok=True)')
    text = text.replace('`app/features/schema.json` · `app/features/graph.json`', '`output/schema.json` · `output/graph.json`')
    text = text.replace('`data/` 모델과 원자료', '`data/model/`의 모델과 `data/`의 원자료')
    text = text.replace('직접 실행하지 않는다 — `python show_result.py`가 단계마다 부른다.', '직접 실행하지 않는다 — 루트 run.py가 요청한 기능을 실행한다.')
    return text


def checker(folder, L):
    """통합02의 검사기에 설계 랩만 공급 조건 계약 검사(build_labs.SUPPLY_CHECK)를 더한다."""
    text = S2.checker(folder, L)
    if L['kind'] == 'design_practical':
        supply = convert(B.SUPPLY_CHECK).replace('(가이드 「공급 조건 형식」)', '')
        if text.count(B.CHECK_ANCHOR) != 1 or 'python run.py parts로 모델을 생성' not in text:
            raise ValueError('통합02 검사기의 꼴이 바뀌었습니다 — 공급 조건 검사를 넣을 자리를 다시 봅니다.')
        text = text.replace(B.CHECK_ANCHOR, supply + B.CHECK_ANCHOR)
        text = text.replace('python run.py parts로 모델을 생성', 'python run.py approval로 모델을 생성')
    usage = ('사용: python check.py            (output/schema.json·graph.json)' + NL +
             '      python check.py 폴더        (다른 폴더의 schema.json·graph.json)' + NL)
    if text.count(usage) != 1:
        raise ValueError('검사기 머리말의 사용법 줄을 찾지 못했습니다.')
    return text.replace(usage, '사용: python run.py check   (output/schema.json·graph.json)' + NL)


# ───────────── 가이드 원고(실전반: 기본 조작은 짧게, 결과 해석과 선택 이유) ─────────────
ONTOLOGY_PURPOSE = '포털 지식 지도에서 본 부품·설비 연결에 공급 조건을 더합니다. 제공된 설비·부품 모델을 확장해 부품별 사용 설비와 공급사별 승인 여부·단가·불량률·납기를 찾습니다.'
GRAPH_PURPOSE = '설비·부품·공급 모델을 이 폴더 전용 그래프 DB(랩 DB)에 구현합니다. 부품별 사용 설비와 공급 조건을 돌려주는 조회 결과를 원자료와 대조합니다.'
ONTOLOGY_LEAD = (ONTOLOGY_PURPOSE + ' 이 모델은 공급사를 골라 주지 않고, 고를 때 필요한 정보를 찾아 주는 구조입니다. '
                 '줄기(온톨로지 → 에이전트 → 프로세스)에서 첫 단계 온톨로지의 설계를 맡습니다.')
GRAPH_LEAD = (GRAPH_PURPOSE + ' 스키마의 식별자와 관계 방향이 그래프의 노드·관계로 옮겨지는 것을 다시 짚습니다. '
              '줄기(온톨로지 → 에이전트 → 프로세스)에서 첫 단계 온톨로지의 구현과 검증을 맡습니다.')
OPEN_RESULT = ('결과는 `output/result.html`에 저장됩니다. 브라우저가 열리지 않으면 Windows 파일 탐색기로 이 실습 폴더의 output 폴더를 열고 result.html을 두 번 누릅니다'
               '(VS Code 탐색기에서 누르면 화면이 아니라 HTML 글이 열립니다). 이후에는 명령을 실행한 뒤 열린 화면에서 F5를 누릅니다.')


EDIT_WINDOW = ('Codex가 파일을 바꾸려 하면 편집 승인 창이 뜹니다. 경로가 `app/features/` 아래인 요청한 변경만 **Allow once**, 그 밖은 **Deny**를 누릅니다. '
               'Codex가 단계를 마칠 때마다 보고한 바뀐 파일이 요청한 파일뿐인지 봅니다.')


def setup(folder, model_line, check):
    """받기 · 폴더 열기 · 신뢰 · 폴더 역할 · 터미널. 랩마다 따로 받아 시작하므로 두 랩 모두 같은 길을 짧게 적는다."""
    text = [f'클래스룸의 2회차 실습 자료에서 이 실습의 ZIP을 받아 압축을 풀고, VS Code의 **파일 → 폴더 열기**로 `{folder}` 폴더를 엽니다. 그 위 폴더를 열면 AI가 정답이 든 이 가이드까지 읽습니다. '
            '신뢰 여부를 물으면 **예, 작성자를 신뢰합니다**(Yes, I trust the authors)를 고릅니다. 제한 모드에서는 Codex를 쓸 수 없습니다.',
            f'`README.md`에서 폴더 역할을 봅니다. {model_line} `AGENTS.md`는 Codex가 지킬 공통 작업 원칙입니다.',
            '**터미널 → 새 터미널**을 열고, 오타를 줄이도록 명령 블록의 **복사**로 붙여 넣습니다.']
    return G.section('폴더 열고 자료 확인하기', text, cmd='python run.py', check=check + ' ' + OPEN_RESULT)


def ontology():
    section = G.section
    return [setup('ontology-lab', '`data/`는 원자료, `data/model/`은 제공된 설비·부품 모델, `app/features/`는 AI와 구현할 판단입니다.',
                  '제공 모델의 종류별 개수와 원자료 행 수가 보입니다. 공급사 종류가 아직 없다는 것이 이번에 더할 자리입니다.'),
        section('Codex와 자료 파악하기', [
            '공급 조건은 견적표·승인 목록·구매 기준서에 흩어져 있어 한 자료만 보면 어긋난 곳을 놓칩니다. 왼쪽 활동 표시줄의 Codex 아이콘을 눌러 채팅을 열고 로그인합니다. 계정이 없거나 구현 중 막히면 클래스룸에서 실습 폴더와 따로 받는 완성본 ZIP(`ontology-lab-completed.zip`)으로 결과를 실행해 볼 수 있습니다.',
            '**승인 공급사**는 구매팀이 사도 된다고 등록한 공급사, **불량률**은 입고 물량 가운데 불량 비율, **납기**는 주문부터 받기까지 날수, **기준일**은 자료를 뽑은 날입니다.',
            '파일을 바꾸지 말고 펌프 축 씰 키트에 관한 줄을 자료마다 파일과 줄 번호로 짚어 달라고 요청합니다. 공급 조건·승인·비교 기준이 어느 자료에 있는지와 자료끼리 다르게 말하는 곳도 묻습니다.',
            f'답에 나온 줄을 직접 엽니다. 자료의 출처와 맥락은 `data/field_notes.md`, 구매 기준은 `data/{PR07}`에 있습니다.'],
            check='질문에 쓸 자료와 자료끼리 어긋난 곳을 내 말로 댈 수 있으면 이어갑니다. 이 단계에서는 파일을 바꾸지 않습니다. ' + EDIT_WINDOW, ai=True),
        section('질문과 판단 기준 정하기', [
            '구매 담당이 다음 발주에서 공급사를 비교할 때 쓸 답을 만듭니다. 고르는 것은 구매 담당입니다. `app/features/requirements.md`에 답을 쓸 사람, 기준일, 아래 세 질문을 자기 말로 짧게 적습니다.',
            f'① 펌프 축 씰 키트를 쓰는 설비는 어디인가? ② 기준일({D.REF_DATE})에 펌프 축 씰 키트를 어느 공급사에서 어떤 조건(승인 여부·단가·불량률·납기)으로 살 수 있고, 각 값은 어느 파일·어느 줄에서 왔는가? '
            '③ 이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물으면 결과가 서로 구별되는가?',
            '지킬 조건도 적습니다. 공급사를 고르거나 점수·순위를 매기는 일, 입고 이력으로 실측 납기를 세는 일, 제공 모델의 설비·부품 부분을 고치는 일은 이번 범위에서 제외합니다. 공용 부품을 설비별로 따로 만들지 않고 단위와 출처를 남긴다는 조건을 자기 말로 남깁니다.',
            '`app/features/expected.csv`에 원자료에서 찾은 답과 근거 줄을 적습니다. 질문 1은 사용 설비 코드를 적습니다. 질문 2는 항목에 「사내 품번/공급사」(공급사는 `data/approved_suppliers.csv`의 이름), 기대_답에 「승인 또는 비승인 · 단가(만원 숫자) · 불량률(0~1 소수) · 납기(일 수)」를 적습니다. '
            '질문 3은 질문 1·2 줄에 다른 표기와 없는 품번을 물을 값으로 쓰고, 원자료에 없는 품번은 항목을 비우고 기대_답에 「없음」, 근거에 찾아본 파일 이름(예: 「data/spare_parts.csv · data/part_aliases.csv에 없음」)을 적습니다. 줄의 꼴은 `질문,물을_값,항목,기대_답,근거`이고 근거는 `data/파일.csv:줄`입니다.',
            '`app/features/decisions.csv`에 미리 있는 세 지점 줄에 고른 것을 적습니다(비어 있으면 승인 기능이 그 줄을 짚고 멈춥니다). **조건이 붙은 승인**은 조건을 달아 등록된 쌍을 승인 여부(참·거짓)에 어떻게 담고 그 조건을 어떻게 보여 줄지, **빈 값의 뜻**은 `data/approved_suppliers.csv`에서 조건 칸이 빈 승인 줄을 「조건 없음」으로 읽을지, 구매 기준서 7.4처럼 조건이 붙어야 할 쌍이면 「적지 않음(등록 확인 필요)」으로 읽을지, '
            '**쓰는 사람에 따라 갈리는 답**은 구매 담당이 공급사를 비교할 때 함께 봐야 할 것이 자료에 있으면 그것을 모델에 어떻게 남길지입니다. 선택마다 근거 줄과 그 선택으로 바뀌는 답을 적습니다. AI의 추천은 선택 근거가 되지 않습니다.', G.SAVE_NOTE],
            prompt='질문 1~3마다 `data/`의 원자료에서 답과 근거 줄(파일:줄)을 함께 찾아, `expected.csv`의 열 꼴대로 한 줄씩 적을 내용을 보여 줘. 파일은 바꾸지 마. 값은 내가 그 줄을 열어 확인한 뒤 적을게. '
                   '`decisions.csv`의 세 지점은 내가 정하니, 지점마다 근거가 될 줄만 짚어 주고 선택은 하지 마. 원자료에 없는 품번 줄은 근거 칸에 찾아본 파일 이름만 적는 꼴로 보여 줘.',
            cmd='python run.py expected', check='화면의 기대 답과 근거가 내가 적은 내용인지 봅니다. 이 표는 모델의 답과 견줄 기준입니다.', ai=True),
        section('기준일에 쓸 견적 고르기', [
            '같은 공급사·부품에 견적이 여러 줄이면 기준일에 쓸 것은 하나여야 구매 담당이 같은 조건을 봅니다. 기한 지난 줄을 빼는지, 가장 늦은 줄을 쓰는지에 따라 쌍마다 단가·납기·견적일이 달라집니다.',
            'Codex와 `data/supply_terms.csv`의 견적일·유효기한과 현장 메모 6절을 보며 기준을 정하고 `app/features/quote_rule.py`에 구현하도록 요청합니다. 공급사 이름·품번 찾기·단위 맞추기와 출처 남기기는 제공 코드가 합니다. 가장 싼 줄을 고르는 것은 범위 밖입니다.', G.ASK_NOTE],
            prompt='지금 확인한 견적일·유효기한 기준으로 `quote_rule.py`의 `use_quote`를 구현해 줘. 쌍마다 받은 견적 줄 하나나 None을 돌려주고, 단가나 점수로 고르지 마. 정하지 않은 기준이 남았으면 먼저 물어봐.',
            cmd='python run.py quotes',
            check=('「씀」과 「기준일에 안 씀」의 합이 견적 줄 수와 같은지, 펌프 축 씰 키트 세 쌍의 단가·불량률·납기가 기대 답과 같은지 봅니다. 바꾼 불량률·납기는 원래 표기와 함께 보입니다. '
                   '같은 공급사를 다르게 적은 이름과 품번 칸에 품명이 적힌 줄이 어느 쌍으로 갔는지도 봅니다. 기준일에 쓸 견적이 없어 쌍 표에서 빠진 쌍이 있으면 그 쌍과 까닭을 `requirements.md`에 남깁니다.'), ai=True),
        section('승인과 함께 볼 정보 담기', [
            '승인 여부는 그 부품을 그 공급사에서 사도 되는지를 정하는 값이라, 출처마다 다르게 적혀 있으면 어느 것을 따랐는지가 결과의 뜻을 바꿉니다. 조건부 승인을 승인으로 담느냐 비승인으로 담느냐에 따라 승인 여부가 바뀌고, 함께 볼 정보를 남기면 그 쌍에 속성이 더 생깁니다.',
            '`app/features/approval_rule.py`의 두 함수를 `decisions.csv`의 세 선택대로 구현하도록 요청합니다. 출처마다 다른 승인 정보와 기한 지난 등록은 어느 자료를 따랐는지 쌍마다 근거 줄로 묻습니다.'],
            prompt='`decisions.csv`에 내가 적은 세 선택과 지금 확인한 승인 근거를 따라 `approval_rule.py`의 `approval`과 `buyer_info`를 구현해 줘. 같은 선택을 모든 쌍에 같은 방식으로 적용하고, 미결인 선택은 미결로 두고 값을 지어내지 마. 공급사를 고르거나 점수를 매기지 마.',
            cmd='python run.py approval',
            check=('출처마다 다른 승인 정보와 기한이 지난 등록을 어느 자료로 정했는지, 기준서의 기준값과 같거나 가까운 값을 가진 쌍이 내 선택대로 처리됐는지 쌍마다 근거 줄로 짚을 수 있는지 봅니다. '
                   '`output/schema.json`과 `graph.json`이 생성됩니다.'), ai=True),
        section('질문으로 결과 검증하기', [
            '처음 적은 기대 답과 모델에 물은 답을 비교하고 구조 검사도 함께 봅니다. 비슷한 이름의 다른 품번·예전 품번·없는 품번이 서로 구별돼야 구매 담당이 엉뚱한 부품의 조건을 보지 않습니다.',
            '대조 표의 「다름」은 같은 짝의 값이 다른 것, 「기대 밖」은 모델이 기대 답에 없는 짝을 더 돌려준 것입니다. 질문 1의 사용 설비는 제공 모델이 정한 것(같은 모델 공용 연결 포함, `data/model/provenance.md`)이고, 세 결정의 결과는 대조 표 아래 「세 결정이 닿은 곳」 표에서 봅니다.',
            '다른 줄이 있으면 입력·기대 답·실제 결과와 그 쌍의 견적·승인 원자료 줄을 Codex에 함께 보여 줍니다. 원인을 확인한 뒤 해당 판단 함수만 고칩니다. 고쳤으면 아래 「고친 뒤 다시 확인」의 순서로 다시 실행합니다.'],
            prompt='지금 결과에서 다른 줄 하나의 입력, `expected.csv`의 근거, 실제 답과 그 쌍의 견적·승인 원자료 줄을 비교해 원인을 설명해 줘. 먼저 파일은 바꾸지 마. 원인을 확인하면 해당 판단 함수만 고치도록 요청할게.',
            cmd='python run.py query', check='답이 맞거나 차이를 원자료로 설명할 수 있고, 구조 검사 통과가 보여야 합니다. 결과에 맞추려고 기대 답을 바꾸지 않습니다. 고친 근거는 `requirements.md`에 짧게 남깁니다.', ai=True,
            recovery=[('python run.py approval', '고친 기준으로 모델이 생성됐는지 봅니다.'),
                      ('python run.py query', 'F5를 눌러 고친 질문의 기대 답과 실제 답, 구조 검사를 봅니다.')]),
        section('저장하고 다시 확인하기', [
            '**파일 → 모두 저장**을 선택합니다. 같은 폴더를 닫았다 다시 열고 아래 명령으로 모델과 답을 다시 확인합니다.',
            '`requirements.md`에 기준일·저장 시점·확인하지 못한 점을 짧게 남깁니다. 다음 그래프 구현 실습은 이 판본이나 제공 모델로 시작하므로 `output/`의 두 파일과 `app/features/`를 함께 둡니다. 재부팅하면 학교 PC 파일이 초기화될 수 있으므로 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다.'],
            cmd='python run.py approval', check='다시 연 파일로 모델이 생성되는지 봅니다.',
            followup=[('python run.py query', 'F5를 눌러 다시 조회한 답과 구조 검사가 유지되는지 봅니다. 이어서 할 때는 보관한 같은 폴더를 엽니다.')])]


LOOK_COLUMN = ' 조회를 만든 뒤 `expected.csv`의 볼_열을 이 조회가 돌려주는 열 이름으로 채울 수 있게, 돌려주는 열 이름을 알려 줘. 볼_열과 기대 답은 내가 적을게.'


def graph():
    section = G.section
    return [setup('graph-lab', '`data/`는 원자료, `data/model/`은 공급 조건까지 담은 설비·부품·공급 모델이라 자기 모델이 없어도 시작할 수 있고, `app/features/`는 AI와 구현할 Cypher 쿼리와 기록입니다.',
                  '원자료 파일과 사용할 모델의 개수가 보입니다.'),
        section('랩 DB 준비하기', [
            '모델을 넣고 조회할 **랩 DB**를 준비합니다. 랩 DB는 이 실습 폴더에만 쓰는 그래프 DB로, Docker가 새로 띄웁니다. Docker Desktop을 켠 뒤 아래 명령을 실행합니다. 처음 한 번은 DB 이미지를 받느라 오래 걸립니다.',
            'Docker와 랩 DB 명령은 내 터미널에서 실행합니다. Codex가 이런 명령을 실행하려 하면 실행 승인 창에서 **Deny**를 누르고 그 명령을 터미널에 붙여 넣습니다.'],
            cmd='python run.py db',
            check=('모델 파일의 개수와 랩 DB 개수가 나란히 보입니다. 처음 만든 랩 DB는 0이며, 이어서 작업하는 랩 DB는 이전에 넣은 개수입니다. '
                   '「랩 DB 준비 확인 필요」가 나오면 Docker Desktop이 켜져 있는지 보고 다시 실행합니다. 뒤 단계에서 「랩 DB가 꺼져 있습니다」가 나오면 이 명령으로 다시 켭니다.')),
        section('Codex와 모델 파악하기', [
            '적재가 맞았는지 세려면 모델에 무엇이 몇 개 있는지 먼저 알아야 합니다. 왼쪽 활동 표시줄의 Codex 아이콘을 눌러 채팅을 열고 로그인한 뒤, 파일을 바꾸지 말고 `data/model/graph.json`의 종류별 대상·관계 수와 펌프 축 씰 키트에 닿는 관계, 그 값의 원자료 줄을 짚어 달라고 요청합니다. '
            '계정이 없거나 막히면 클래스룸에서 별도로 받는 `graph-lab-completed.zip`을 실행해 볼 수 있습니다.',
            '제공 모델의 식별자와 공급 조건 관계에 붙은 속성(값과 출처)도 묻습니다. `data/model/provenance.md`에서 모델에 적용된 기준을 확인합니다.',
            '설계 실습에서 만든 자기 온톨로지 모델을 쓰는 것은 선택입니다. 사용할 때만 기준일·종류·식별자·관계의 형식을 확인하고, 두 JSON 파일을 `app/features/model/`에 함께 복사합니다. 제공 모델은 보존합니다.'],
            cmd='python run.py', check='현재 사용하는 모델 경로와 개수를 확인합니다. 자기 모델을 골랐다면 이후 질문과 Cypher 쿼리도 그 모델에 맞춥니다. ' + EDIT_WINDOW, ai=True),
        section('질문과 기대 답 정하기', [
            '보전·구매 담당이 예비품을 쓰는 설비와 공급사별 조건을 함께 볼 때 쓸 답을 만듭니다. 고르는 것은 구매 담당입니다. `app/features/review.md`에 질문·사용할 자료·기준일·지킬 조건을 자기 말로 적습니다. 공급사를 고르거나 점수·순위를 매기는 일, 입고 이력으로 실측 납기를 세는 일, 모델 정의 변경은 이번 범위에서 제외합니다.',
            '① 세 설비가 함께 쓰는 펌프 축 씰 키트를 어느 설비·구성 요소에서 쓰고, 기준일의 세 공급 조건(승인 여부·단가·불량률·납기)은 무엇이며 각 값은 어느 파일·어느 줄에서 왔는가? '
            '② 이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물으면 결과가 서로 구별되는가? 비승인 공급사는 승인 상태와 함께 구별되는가? ③ 같은 적재를 다시 실행해도 대상과 관계가 늘지 않는가?',
            '`app/features/expected.csv`에 기대 답과 근거를 먼저 적습니다. 질문 1은 펌프 축 씰 키트의 사용 설비와 공급사 · 승인 여부 열, 질문 2는 다른 표기 · 없는 품번 · 사내 품번 둘에 걸리는 표기(제조사 규격 번호 6205-2RS 등)로 찾은 방식 열을 적습니다. '
            '단가 · 불량률 · 납기 · 출처 값은 설계 실습에서 기대 답으로 이미 견줬으므로 여기서는 조회 결과 표를 원자료 줄과 직접 견줍니다. 원자료에 없는 품번은 근거에 찾아본 파일 이름만 적습니다. 한 물을 값에 견줄 열이 여럿이면 줄을 나눠 씁니다. '
            '볼_열은 조회를 만든 뒤(사용 설비와 공급 조건 조회, 다른 표기 조회) 그 조회가 돌려주는 열 이름으로 채우므로 지금은 비워 둡니다. 여러 값은 「 · 」로 잇습니다.',
            '**쓰는 사람에 따라 갈리는 답**을 정합니다. 구매 담당이 공급사를 비교할 때 승인 여부·단가·불량률·납기 말고도 함께 봐야 할 것이 모델에 있으면, 그것을 조회 결과에 함께 돌려줄지와 어떻게 보일지입니다. 선택과 근거를 `decisions.csv`에 적고 AI의 추천은 원자료로 다시 확인합니다.', G.SAVE_NOTE],
            prompt='내 `review.md`, `expected.csv`, `decisions.csv`를 읽고 방금 확인한 모델·원자료와 맞는지 짚어 줘. 파일은 바꾸지 마. 기대 답에 필요한 조건이나 내 선택이 빠졌으면 먼저 물어봐.',
            cmd='python run.py expected', check='화면에 내가 적은 입력·기대 답·근거가 보입니다. 이 답으로 조회 결과를 대조합니다.', ai=True),
        section('모델 적재하기', [
            '이론에서 본 대로 스키마의 종류(클래스) 이름은 그래프의 레이블이 되고, 대상 하나(인스턴스)는 노드, 관계 정의의 시작·끝은 관계의 방향이 됩니다. CREATE는 실행할 때마다 새로 만들고, MERGE는 같은 것이 있으면 찾고 없으면 만듭니다. '
            '그래서 다시 적재해도 늘지 않으려면 같은 대상을 무엇으로 알아볼지(MERGE의 열쇠) 먼저 Codex와 정합니다.',
            '계획을 확인한 뒤 적재 Cypher 쿼리를 `app/features/load.cypher`에만 작성하도록 요청합니다. 종류·관계마다 쿼리를 나누고, 바로 위에 `// 넣을 것: <종류 또는 관계>`를 적습니다. 제공 도구가 해당 행을 `$rows`로 넘겨 실행합니다.', G.ASK_NOTE],
            prompt='지금 검토한 식별 기준을 `load.cypher`에 구현해 줘. `schema.json`의 종류와 관계 방향을 따르고 행은 $rows로 받아 줘. 같은 대상을 중복 생성하거나 전체를 지우지 마. 조회는 아직 작성하지 마.',
            cmd='python run.py load', check='모델 파일과 랩 DB의 종류별 개수가 같은지 봅니다. 다르면 해당 종류의 입력 행과 적재 쿼리를 Codex와 대조합니다.', ai=True,
            followup=[('python run.py repeat', '같은 적재를 한 번 더 실행한 전후 개수에서 늘거나 사라진 항목이 없는지 봅니다. 늘었으면 같은 대상을 알아보는 기준을 고칩니다. 개수를 `review.md`에 짧게 남깁니다.')]),
        section('사용 설비와 공급 조건 조회하기', [
            '공급 조건은 공급사와 부품 사이 관계의 값이라, 부품에서 설비 쪽과 공급사 쪽 두 길을 따라가야 한 번에 나옵니다. 무엇을 함께 돌려줄지는 결과를 쓰는 사람이 공급사를 무엇으로 견주는지에 따라 정하고, 그 선택에 따라 결과의 열이 달라집니다.',
            '`app/features/query.cypher`의 `// 질문 1` 아래에 품번 하나로 사용 설비·구성 요소와 공급사별 공급 조건(승인 상태·출처 포함)을 돌려주는 Cypher 쿼리를 작성합니다. 비승인 공급사를 어떻게 구별해 보일지와 `decisions.csv`의 선택대로 무엇을 함께 돌려줄지 Codex에게 말합니다. '
            '쿼리를 만든 뒤 `expected.csv` 질문 1 줄의 볼_열을 돌려받은 열 이름으로 채웁니다.'],
            prompt=('지금 확인한 두 길과 `decisions.csv`의 선택으로 `query.cypher`의 질문 1만 작성해 줘. 품번은 $ 자리 하나로 받고 사용 설비·구성 요소와 공급사별 승인 상태·단가·불량률·납기·출처를 돌려줘. 공급사를 고르거나 순위를 매기지 마.' + LOOK_COLUMN),
            cmd='python run.py usage', check='사용 설비 세 대와 세 공급 조건이 출처 줄과 함께 보이고 비승인 공급사가 구별되는지 원자료와 대조합니다. 목록으로 돌려받은 열은 「 · 」로 이어 견주고, 공급사 줄마다 같은 목록이면 한 번만 견줍니다. 차이가 나면 입력·기대 답·실제 결과로 원인부터 찾습니다.', ai=True),
        section('다른 표기와 없는 품번 구별하기', [
            '같은 부품을 예전 품번이나 다른 표기로 적은 자료가 있어, 정식 품번으로만 찾으면 다른 표기로 물은 사람은 「없음」을 받습니다. 조회가 찾지 못하면 결과가 0줄이므로 없는 품번을 어떻게 보일지(0줄 또는 「없는 품번」 한 줄)도 함께 정합니다.',
            '`query.cypher`의 `// 질문 2` 아래에 Cypher 쿼리를 추가합니다. 질문 1은 유지합니다. 쿼리를 만든 뒤 `expected.csv` 질문 2 줄의 볼_열을 채웁니다.'],
            prompt=('지금 정한 없는 품번의 표시 방식으로 `query.cypher`에 질문 2를 추가해 줘. 정식 품번·예전 품번·다른 표기를 $ 자리 하나로 받아 같은 부품을 찾고, 비슷한 다른 품번은 합치지 마. 없는 품번에 값을 지어내지 말고 질문 1은 유지해 줘.' + LOOK_COLUMN),
            cmd='python run.py aliases', check='예전 품번·다른 표기로 물어도 정식 품번과 같은 부품이 나오고, 비슷한 다른 품번과 없는 품번이 구별되는지 원자료와 대조합니다.', ai=True),
        section('저장하고 다시 확인하기', [
            '**파일 → 모두 저장**을 선택하고 같은 폴더를 닫았다 다시 엽니다. 아래 명령으로 랩 DB를 켜고 조회 결과와 저장한 그래프를 확인합니다.',
            '`review.md`에 기준일·저장 시점·확인하지 못한 점을 짧게 남깁니다. 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다. 계정 없이 결과를 실행할 때는 클래스룸의 별도 `graph-lab-completed.zip`을 사용합니다.'],
            cmd='python run.py db',
            check='같은 폴더의 랩 DB가 열렸는지 봅니다. 새로 만든 랩 DB라 비어 있다는 안내가 나오면 바로 아래 접힌 안내의 적재를 먼저 실행합니다.',
            when_new=[('python run.py load', '새 랩 DB에 넣은 개수가 사용한 모델과 같은지 봅니다.')],
            followup=[('python run.py usage', 'F5를 눌러 조회 결과가 유지되는지 봅니다.'),
                      ('python run.py aliases', '다른 표기와 없는 품번의 결과도 유지되는지 봅니다.'),
                      ('python run.py export', '`output/schema.json`과 `graph.json`에 저장한 개수를 확인합니다.'),
                      ('python run.py check', '구조 검사를 통과하는지 확인합니다.')])]


# ───────────── 프로젝트 ─────────────
ONTOLOGY_RULES = ('- 이 실습에서 구현하는 파일은 `app/features/quote_rule.py`와 `app/features/approval_rule.py`이고, 학생 기록은 `app/features/requirements.md`·`expected.csv`·`decisions.csv`다.' + NL +
                  '- 모델은 `python run.py approval`이 `output/schema.json`·`output/graph.json`에 쓴다. 이 두 파일을 손으로 고치지 않는다.')
GRAPH_RULES = ('- 이 실습에서 구현하는 파일은 `app/features/load.cypher`와 `app/features/query.cypher`이고, 학생 기록은 `app/features/review.md`·`expected.csv`·`decisions.csv`다.' + NL +
               '- 실행 결과와 내보낸 그래프는 `output/`에 생긴다. 자기 모델을 쓰면 `app/features/model/`에 schema.json과 graph.json을 함께 둔다.')
ONTOLOGY_EXPECT = [('질문 2는 사내 품번/공급사.', '질문 2는 사내 품번/공급사(공급사는 approved_suppliers.csv의 이름), 원자료에 없는 품번은 비움.'),
                   ('「승인 여부 · 단가(만원) · 불량률(0~1) · 납기(일)」', '「승인 또는 비승인 · 단가(만원 숫자) · 불량률(0~1 소수) · 납기(일 수)」'),
                   ('값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」', '원자료에 없는 품번은 「없음」. 숫자는 0.30과 0.3처럼 같은 값이면 같게 견줌')]
ONTOLOGY_ASK_OLD = """    key = lambda r: f"{r['질문']} | {r['물을_값']} | {r.get('항목', '')}"
    exp = [{'짝': key(r), '답': r['기대_답']} for r in rows]
    act = [{'짝': key(r), '답': r['답']} for r in got]"""
ONTOLOGY_ASK_NEW = """    key = lambda r: f"{r['질문']} | {r['물을_값']} | {item(r.get('항목', ''))}"
    exp = [{'짝': key(r), '답': r['기대_답']} for r in rows]
    act = [{'짝': key(r), '답': r['답']} for r in got]"""
ONTOLOGY_HELPERS = """

def item(text):
    \"\"\"항목 칸 견주기: 없는 품번의 「없음」은 빈칸과 같고, 공급사는 견적표 괄호 앞 이름(승인 목록의 이름)으로 맞춘다.\"\"\"
    text = str(text or '').strip()
    if text == '없음':
        return ''
    if '/' in text:
        part, supplier = text.split('/', 1)
        return part.strip() + '/' + M.supplier_name(supplier)
    return text

"""
GRAPH_EXPECT = [('(질문 · 물을_값) 짝마다 한 줄만 쓰고, 그 줄에서 견줄 열(볼_열)은 하나. 같은 짝의 다른 열을 견주려면 같은 대상의 다른 표기를 물을_값으로 쓴 줄을 더함.', '한 줄 = (질문 · 물을_값 · 볼_열) 하나 — 한 물을 값에 견줄 열이 여럿이면 볼_열마다 한 줄.'),
                ('볼_열 = 그 조회 결과에서 견줄 열 이름 하나.', '볼_열 = 그 조회 결과에서 견줄 열 이름 하나(조회를 만든 뒤 채움).'),
                ('기대_답 = 그 열의 값들(결과 줄마다 하나, 줄 순서는 보지 않음).', '기대_답 = 그 열의 값들(결과 줄마다 하나, 줄 순서는 보지 않음, 목록 칸은 「 · 」로 잇고 모든 줄에서 같은 목록이면 한 번만).')]
GRAPH_ASK = """

def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], ['질문', '물을_값', '볼_열', '기대_답'])
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '볼_열', '기대_답', '근거'], rows,
                    note='볼_열은 조회를 만든 뒤 그 조회가 돌려주는 열 이름으로 채웁니다. 한 물을 값에 견줄 열이 여럿이면 볼_열마다 한 줄씩 씁니다.')]


def cell(value):
    \"\"\"조회 결과 칸 하나를 견줄 글로: 값 없음은 「없음」, 목록은 「 · 」로 잇는다.\"\"\"
    if value is None or value == '':
        return '없음'
    if isinstance(value, list):
        return ' · '.join(cell(v) for v in value) or '없음'
    return str(value)


def ask_question(number):
    rows = [r for r in expected_rows(['질문', '물을_값', '기대_답'], ['질문', '물을_값', '볼_열', '기대_답']) if r['질문'] == str(number)]
    path = HERE / 'app/features/query.cypher'
    try:
        qs = C.questions(path)
    except RuntimeError as e:
        raise R.Stop(str(e))
    if str(number) not in qs:
        raise R.Blank(f'app/features/query.cypher에 「// 질문 {number}」 조회가 아직 없습니다.')
    line, text = qs[str(number)]
    names = sorted(set(C.PARAM.findall(text)))
    if len(names) > 1:
        raise R.Stop(f'app/features/query.cypher:{line}: 질문 {number}의 $ 자리가 {len(names)}개({", ".join(names)}) — 물을 값 하나를 $ 자리 하나로 받습니다.')
    seen = {}
    for r in rows:
        if r.get('볼_열'):
            pair = (r['물을_값'], r['볼_열'])
            if pair in seen:
                raise R.Stop(f'app/features/expected.csv: 질문 {number}의 물을_값 「{pair[0]}」 · 볼_열 「{pair[1]}」이 두 줄입니다 — 한 열에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
            seen[pair] = True
    blocks, exp, act, ran = [], [], [], {}
    for r in rows or [{'물을_값': '', '볼_열': ''}]:
        value = r['물을_값']
        if value not in ran:
            params = {names[0]: value} if names else {}
            (_, _, cols, data), = db(C.query, path, str(number), params)
            ran[value] = (cols, data)
            blocks.append(R.table(f'질문 {number} — 물은 값 「{value}」', cols, [[cell(v) for v in row] for row in data]))
        cols, data = ran[value]
        if r.get('볼_열'):
            if r['볼_열'] not in cols:
                raise R.Stop(f'app/features/expected.csv: 볼_열 「{r["볼_열"]}」이 질문 {number} 결과의 열({", ".join(cols)})에 없습니다.')
            i = cols.index(r['볼_열'])
            pair = value + ' | ' + r['볼_열']
            exp.append({'짝': pair, '답': r['기대_답']})
            values = [row[i] for row in data]
            if values and all(isinstance(v, list) for v in values) and all(v == values[0] for v in values):
                values = values[:1]   # 모아 돌려준 목록이 줄마다 되풀이되면 한 번만 견준다
            act.append({'짝': pair, '답': ' · '.join(cell(v) for v in values) or '0줄'})
    if exp:
        blocks.insert(0, R.compare(f'질문 {number} 기대 답 ↔ 조회 결과(물을 값 | 볼_열)', '짝', exp, act, ['답'], same=same,
                                   note=SAME_NOTE + ' 값 없음(null)과 빈 글자 칸은 「없음」으로 견줍니다.'))
    elif rows:
        blocks.insert(0, R.note('기대 답의 볼_열이 비어 있어 대조하지 않았습니다. 이 조회가 돌려주는 열 이름으로 볼_열을 채우면 대조합니다.'))
    return blocks
"""


def build_ontology(folder):
    L = B.design_practical()
    source_data(folder)
    model_files(folder, supply=False)
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith(('README.md', '요구사항.md')):
            if name == '결과/기대_답.csv':
                text = replace_all(text, ONTOLOGY_EXPECT)
            write(folder / convert(name), convert(text))
    write(folder / 'app/features/requirements.md', '# 요구사항\n\n## 답을 쓸 사람·질문·기준일\n\n## 지킬 조건\n\n## 대조 결과·고친 점\n\n## 저장 시점·확인하지 못한 점\n')
    utilities, ui = S2.result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/supply.py', supply_source())
    actions = P.actions_source(L)
    if 'import supply_tool as M' not in actions:
        raise ValueError('실전 설계 랩 단계 코드의 제공 코드 import가 바뀌었습니다.')
    actions = actions.replace('import supply_tool as M', 'from app.utils import supply as M')
    if 'def check(' in actions:
        raise ValueError('실전 설계 랩 단계 코드에 구조 검사 기능이 생겼습니다 — 여기서 더하지 않습니다.')
    actions = replace_all(actions, [(ONTOLOGY_ASK_OLD, ONTOLOGY_ASK_NEW)]).rstrip('\n') + ONTOLOGY_HELPERS + '\n\ndef check(previous):\n    return run_check()\n\n'
    actions += commands_source({'sources': ('원자료와 제공 모델', 'sources'), 'expected': ('기대 답', 'expected'),
                                'quotes': ('기준일에 쓸 견적', 'quotes'), 'approval': ('승인과 함께 볼 정보', 'approval'),
                                'query': ('질문별 대조와 구조 검사', 'ask'), 'check': ('구조 검사', 'check')})
    write(folder / 'app/utils/actions.py', convert(actions))
    write(folder / 'run.py', S2.run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], ONTOLOGY_PURPOSE, extra_rules=ONTOLOGY_RULES + '\n' + S2.DECISION_RULE)
    steps = ontology()
    F.write_guide(folder, G.render(L['title'], ONTOLOGY_LEAD, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


GRAPH_REVIEW = '# 실행 기록\n\n## 질문·사용할 자료·지킬 조건\n\n## 적재 전후 개수\n\n## 기대 답과 실제 결과·고친 근거\n\n## 기준일·저장 시점·확인하지 못한 점\n'
EXPECT_OLD = '값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」'
EXPECT_NEW = '조회가 0행이면 「0줄」, 반환된 행의 빈 칸은 「없음」. 없는 품번을 설명하는 행을 반환하면 그 설명을 그대로 적음'


def build_graph(folder):
    L = B.graph_lab('실전반')
    source_data(folder)
    model_files(folder, supply=True)
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            if name == '결과/기대_답.csv':
                text = replace_all(text, [(EXPECT_OLD, EXPECT_NEW)] + GRAPH_EXPECT)
            write(folder / convert(name), convert(text).replace('python show_result.py가 실행', 'python run.py load가 실행'))
    write(folder / 'app/features/review.md', GRAPH_REVIEW)
    utilities, ui = S2.result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/db.py', replace_all(GP.db_source(), [('저장해 둔 적재 · 수정 파일을 같은 순서로 다시 실행하세요.', '저장해 둔 적재 파일부터 다시 실행하세요.')]))
    write(folder / 'app/utils/cypher.py', GP.cypher_source())
    actions = drop_functions(P.actions_source(L), {'load_and_again', 'q3', 'change', 'portal', 'expected', 'ask_question'}).rstrip(NL) + GRAPH_ASK
    extra = GP.EXTRA_ACTIONS.split('\nCOMMANDS = {', 1)[0]
    actions += extra + commands_source({
        'sources': ('원자료와 모델', 'sources'), 'db': ('랩 DB 준비', 'prepare'), 'status': ('모델과 DB 개수', 'start'),
        'expected': ('기대 답', 'expected'), 'load': ('모델 적재', 'load'), 'repeat': ('같은 적재 다시 실행', 'again'),
        'usage': ('사용 설비와 공급 조건', 'q1'), 'aliases': ('다른 표기와 없는 품번', 'q2'),
        'export': ('그래프 저장', 'export'), 'check': ('구조 검사', 'check')})
    write(folder / 'app/utils/actions.py', convert(actions))
    write(folder / 'run.py', S2.run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], GRAPH_PURPOSE, extra_rules=GRAPH_RULES + '\n' + S2.GRAPH_DECISION_RULE + '\n' + DB_RULE)
    steps = graph()
    F.write_guide(folder, G.render(L['title'], GRAPH_LEAD, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def validate(folder, L, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    leftover = [f'{p.relative_to(folder).as_posix()}: {w}' for p in student_files(folder) if p.suffix in ('.py', '.md', '.csv', '.json', '.cypher')
                for w in ('결과/', '입력/', '자료/', 'show_result.py', 'lab_steps.py', 'START.md', *KOREAN_NAMES) if w in p.read_text(encoding='utf-8-sig')]
    if leftover:
        raise ValueError(f'옛 경로·이름이 남음: {leftover[:8]}')
    pack(folder)
    item = entry('practical-02-' + folder.name.removesuffix('-lab'), '실전반', '온라인 02회차', L['title'], VERSION, folder,
                 guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    problems = check_zip(folder.with_suffix('.zip'), folder)[0]
    if problems:
        raise ValueError(problems)
    verify_lab(item)
    return item


def replace_generated(source, target):
    """검사가 끝난 이 생성기의 프로젝트 하나만 정본에 반영한다."""
    target = target.resolve()
    if target.parent != DEST.resolve() or target.name != source.name or target.name not in LABS.values():
        raise ValueError('지정한 실전02 프로젝트 밖에는 반영하지 않습니다.')
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    for suffix in ('_guide.html', '.zip'):
        shutil.copyfile(source.parent / (source.name + suffix), target.parent / (target.name + suffix))


def put(folder, files):
    """옛 경로(결과/ · 입력/자료/)로 적힌 정답 파일을 새 경로와 이름으로 옮겨 쓴다."""
    for name, text in files.items():
        write(folder / convert(name), convert(text))


def fill_graph(folder, branch='ㄴ'):
    """정답 토글 기본 갈래(build_labs.default_graph_branch) — 조회 갈래 ㄴ은 7.4 정보를 함께, ㄱ은 네 값만."""
    import session2_answers as A
    graph = json.loads((folder / 'data/model/graph.json').read_text(encoding='utf-8'))
    expected = replace_all(B.graph_expect_text(B.graph_expect_rows('실전반', graph), '실전반'), [(EXPECT_OLD, EXPECT_NEW)] + GRAPH_EXPECT)
    load = replace_all(A.load_answer(graph), [('(ON CREATE SET — 다시 적재해도 수정본이 고친 값을 되돌리지 않음)', '(ON CREATE SET — 처음 만들 때만 넣음)')])
    put(folder, {'결과/load.cypher': load,
                 '결과/query.cypher': A.query_text([A.QUERY_PRACTICAL[1][branch], A.QUERY_PRACTICAL[2]]),
                 '결과/정한_것.csv': B.chosen_text([B.graph_chosen('실전반')[branch]]),
                 '결과/기대_답.csv': expected})


def fill_ontology(folder, branch='ㄴ'):
    import session2_answers as A
    put(folder, {'결과/quote_rule.py': A.QUOTE_RULE_ANSWER, '결과/approval_rule.py': A.approval_rule_answer(branch),
                 '결과/정한_것.csv': B.chosen_text(A.practical_chosen(branch)), '결과/기대_답.csv': expect_supply_text()})


def expect_supply_text():
    """설계 랩 기대 답 예(완성본 · 참조 시험) — build_labs.expect_supply_text의 값에 질문 1 근거를 파일:줄로 적고 머리줄을 이 판 꼴로."""
    import csv, io
    text = replace_all(B.expect_supply_text(), ONTOLOGY_EXPECT)
    graph = B.reference_model(True, 'ㄴ')[1]
    owner = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    comps = list(enumerate(csv.DictReader(io.StringIO(D.source_texts(True)['구성요소_목록.csv'])), 2))
    cross = list(enumerate(csv.DictReader(io.StringIO(D.source_texts(True)['품번_교차표.csv'])), 2))
    placeholder = '자료/구성요소_목록.csv 교체부품 칸 · 자료/품번_교차표.csv'
    out = []
    for line in text.splitlines():
        if placeholder in line:
            code, pid = next(csv.reader([line]))[1:3]
            used = []
            for rel in graph['rels']:
                if rel['type'] == 'USES_PART' and rel['b'] == pid:
                    asset, key = owner[rel['a']], rel['a'].split(':', 1)[1]
                    keys = {k for k, *_ in D.MODEL_COMPONENTS[D.model_of(asset)]}
                    used += [n for n, row in comps if row['설비코드'] == asset and '철거' not in row['비고'] and B.comp_key(row['구성요소'], keys) == key]
            if not used:
                raise ValueError(f'{pid}: 구성요소_목록.csv에서 근거 줄을 찾지 못했습니다.')
            basis = '자료/구성요소_목록.csv:' + ' · '.join(map(str, sorted(used)))
            if code != pid:
                hits = [n for n, row in cross if row['사내품번'] == pid and row['다른표기'] == code]
                if not hits:
                    raise ValueError(f'{code}: 품번_교차표.csv에서 근거 줄을 찾지 못했습니다.')
                basis += ' · 자료/품번_교차표.csv:' + ' · '.join(map(str, hits))
            line = line.replace(placeholder, basis)
        out.append(line)
    return NL.join(out) + NL


def replace_all(text, pairs):
    """고칠 글이 정확히 한 번 있어야 바꾼다 — 원본 문구가 바뀌면 조용히 지나가지 않고 멈춘다."""
    for old, new in pairs:
        if text.count(old) != 1:
            raise ValueError(f'바꿀 글을 한 곳에서 찾지 못했습니다({text.count(old)}곳): {old[:60]}')
        text = text.replace(old, new)
    return text


def completed(starter, destination, work):
    """학생용 완성본은 별도 묶음이며 시작 ZIP에 넣지 않는다. 유료 AI 호출 없음."""
    folder = work / 'completed' / starter.name
    shutil.copytree(starter, folder)
    if starter.name == 'ontology-lab':
        fill_ontology(folder)
        title, initial = B.design_practical()['title'], 'python run.py approval\npython run.py query'
        context, actions = nullcontext(), ('quotes', 'approval', 'check', 'query')
    else:
        from reference.session2_graph_trials import instance
        fill_graph(folder)
        title, initial = B.graph_lab('실전반')['title'], 'python run.py db\npython run.py load\npython run.py usage'
        context, actions = instance(folder), ('load', 'repeat', 'usage', 'aliases', 'export', 'check', 'usage')
    write_metadata(folder, title + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단 기준 한 가지를 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.'
                   + (' Docker Desktop을 켠 뒤 실행합니다.' if starter.name == 'graph-lab' else ''), command=initial,
                   extra_rules=ONTOLOGY_RULES if starter.name == 'ontology-lab' else GRAPH_RULES)
    logs = {}
    with context:
        for action in actions:
            run = subprocess.run([sys.executable, 'run.py', action, '--no-open'], cwd=folder,
                                 capture_output=True, text=True, encoding='utf-8')
            logs[action] = run.stdout + run.stderr
            if run.returncode:
                raise RuntimeError(logs[action])
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    write(work / 'completed-execution.json', json.dumps(logs, ensure_ascii=False, indent=2) + '\n')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lab', choices=list(LABS))
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더; 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 지정한 실전02 랩만 교체')
    parser.add_argument('--completed', action='store_true', help='별도 학생용 완성본도 실제 실행해 생성')
    args = parser.parse_args()
    build = build_ontology if args.lab == 'ontology' else build_graph
    WORK.mkdir(parents=True, exist_ok=True)
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()):
            parser.error('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent / LABS[args.lab]
        if folder.exists():
            parser.error('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        L, steps = build(folder)
        validate(folder, L, steps)
        if args.completed:
            completed(folder, parent, parent)
    else:
        with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
            work = Path(temp).resolve()
            assert work.is_relative_to(WORK.resolve()) and work != WORK.resolve()
            source = work / LABS[args.lab]
            L, steps = build(source)
            validate(source, L, steps)
            archive = completed(source, work, work) if args.completed else None
            folder = DEST / source.name
            replace_generated(source, folder)
            register([validate(folder, L, steps)])
            if archive:
                target = DEST.parent / '완성본' / archive.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archive, target)
                shutil.copyfile(work / 'completed-execution.json', WORK / (args.lab + '-completed-execution.json'))
    print(folder)


if __name__ == '__main__':
    main()
