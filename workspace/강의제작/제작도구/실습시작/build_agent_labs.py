"""통합05 원인 후보와 다음 점검 계획 프로젝트 하나를 만든다. 공용 목록은 부모가 갱신한다."""
from pathlib import Path
import argparse
import ast
import base64
import csv
import hashlib
import html
import json
import shutil
import time
import lab_frame as frame
from lab_package import pack, entry
from project_layout import write_metadata, errors as layout_errors
import data_agent_evidence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LAB = ROOT / 'workspace/강의제작/산출물/통합반/실습/05회차/랩/root-cause-lab'
LEGACY = LAB.parent / '05일차_실습2_원인추론과점검계획'
REF = HERE / 'reference/session5_root'
VERSION = '2026-11-10-agent-root-guide-fixes'
DEFAULT_REQUEST = 'ALT-hyd03-0289-060b'
LEAD = '앞에서 배운 지식·현재값·출처 확인을 바탕으로, 제공된 4회차의 원인 후보와 문서 조건을 이번 사건의 관측값과 연결하는 원인·점검 계획 에이전트를 만듭니다.'
TITLE = '원인 후보와 다음 점검 계획'


def policy_text(branch):
    common = (REF / 'policy_common.py').read_text(encoding='utf-8').replace('강사 참조의 공통 판단. 학생 묶음에는 복사하지 않는다.', '조회 범위와 증거 대조를 구성한다.')
    return common + '\n' + (REF / f'delivery_{branch}.py').read_text(encoding='utf-8') + '\ndef build_plan(request, ledger, model_report):\n    return compose(request, ledger, model_report, delivery)\n'


def reference_features(branch):
    """학생 폴더 밖 검증·완성본 도구가 사용한다. 시작 프로젝트에는 넣지 않는다."""
    common = (REF / 'policy_common.py').read_text(encoding='utf-8')
    nodes = ast.parse(common).body
    query = 'from datetime import datetime, timedelta\n\n' + '\n\n'.join(ast.get_source_segment(common, n) for n in nodes if isinstance(n, ast.FunctionDef) and n.name in ['instructions', 'prepare_query'])
    assess = '\n\n'.join(ast.get_source_segment(common,n) for n in nodes if not isinstance(n, ast.Expr) and not (isinstance(n,ast.FunctionDef) and n.name in ['instructions','prepare_query']))
    assess += '\ndef assess(request, ledger):\n    safety_refs = []\n    def capture(candidates, unresolved, refs):\n        safety_refs.extend(refs)\n        return [], ""\n    value = compose(request, ledger, {}, capture)\n    return {k:value[k] for k in ["candidates","unresolved","safety"]} | {"safety_refs":safety_refs}\n'
    deliver = (REF / f'delivery_{branch}.py').read_text(encoding='utf-8')
    deliver += '\ndef deliver(request, assessment, choices):\n    checks, reason = delivery(assessment["candidates"], assessment["unresolved"], assessment["safety_refs"])\n    selected = " / ".join(item["choice"] + " (근거: " + item["source"] + ")" for item in choices)\n    return {"next_checks":checks,"delivery_reason":reason + " 적용한 요구: " + selected}\n'
    return {'query.py':query,'assess.py':assess,'deliver.py':deliver}


def reference_choices(branch):
    """갈래별 참조 실행의 요구. 학생 시작 폴더에는 넣지 않는다."""
    if branch == 'partial':
        choice = '확인된 범위의 점검 제안을 먼저 전달하고 미확인 자료는 해당 역할에 따로 확인한다'
        action = '운전 조건은 운전원에게 확인하고 후보별 자료 확인은 보전팀에 나누어 요청한다'
    elif branch == 'bundle':
        choice = '요청 전체의 근거를 보완해 받은 뒤 점검 제안을 묶어서 검토한다'
        action = '설비보전팀이 미확인 목록을 모아 운전원과 조회 담당자에게 보완받은 뒤 점검을 검토한다'
    else: raise ValueError('알 수 없는 참조 갈래')
    return 'decision,choice,source,changed_action\ndeliver,' + choice + ',data/field_notes.md:32-34의 미정 요구를 읽고 정한 참조 실행 방침,' + action + '\n'


FEATURES = {
'query.py':'''"""모델이 필요한 도구를 고르도록 지침과 조회 범위를 구현합니다."""
def instructions(request):
    """request: requests.csv 한 행. 반환: 필요한 근거·조회 범위·미확인 처리에 관한 문자열."""
    raise NotImplementedError("query.py: 내 요구와 원문 근거에 맞는 조회 지침을 구현합니다.")


def prepare_query(name, arguments, request):
    """모델 도구 이름과 인수, 요청을 받아 실제 실행할 인수 dict를 반환합니다.
    도구 계약은 app/utils/evidence.py의 TOOL_CONTRACT입니다.
    원래 인수와 반환 인수는 수집 기록에 따로 남습니다.
    """
    raise NotImplementedError("query.py: 내가 고른 설비·기간·원문 범위 기준을 구현합니다.")
''',
'assess.py':'''"""수집된 실제 근거로 후보별 증거 대조를 구현합니다. 모델을 다시 호출하지 않습니다."""
def assess(request, ledger):
    """request는 요청 한 행, ledger는 실제 도구 반환 목록입니다.
    각 반환: id(T식별자), tool, model_arguments, arguments, status(ok/error), result 또는 error.
    반환 dict:
      candidates: cause_id/name/status(충족·해당 없음·보류)/reason/evidence_refs 목록.
      unresolved: needed(더 필요한 근거)/evidence_refs 목록. cause_id는 해당할 때만.
      safety_refs: 실제로 받은 작업 전제 원문 T식별자 목록.
      safety: field_confirmed(실제 현장 확인 여부)/meaning(문서 전제와 현장 상태의 구분).
    없던 반환·숫자·관계를 만들지 않고 값 없음, 0, 조건 불충족을 구분합니다.
    """
    raise NotImplementedError("assess.py: 원문 적용 조건과 관측을 대조해 후보·미확인을 반환합니다.")
''',
'deliver.py':'''"""내가 선택한 전달 방침으로 다음 역할의 확인 항목을 만듭니다."""
def deliver(request, assessment, choices):
    """request는 요청 한 행, assessment는 현재 후보 판정입니다.
    choices는 choices.csv에서 decision=deliver인 실제 입력 행 목록입니다.
    각 행은 choice(전달 요구), source(선택 근거), changed_action(달라질 행동), input_file/input_line을 가집니다.
    이 요구를 후보 상태와 미확인 근거에 적용하는 판단을 구현합니다. 요구의 출처를 AI가 만들지 않습니다.
    반환 dict:
      next_checks: recipient(받을 역할)/action(할 일)/preconditions(작업 전제 문자열 목록)/evidence_refs 목록.
      delivery_reason: 선택한 방침이 이 요청의 다음 행동을 어떻게 바꿨는지 설명.
      delivery_questions: 요구가 더 필요하면 recipient/question 목록. 이때 next_checks는 비웁니다.
    원인·관측의 판정을 이 함수에서 새로 만들지 않습니다. 실제 승인·작업 발행도 하지 않습니다.
    """
    raise NotImplementedError("deliver.py: 선택과 근거를 실제 점검 전달 순서에 반영합니다.")
'''}


def paragraph(text): return '<p>' + frame.inline(text) + '</p>'
def command(text): return frame.command_block(text)
def answer(text, reason='앞에서 파악한 자료와 내가 적은 선택을 전제로, 지금 기능만 요청합니다.'):
    return frame.answer_html(frame.A(reason, frame.ask_ai(text)))


def definition(identity):
    return {'title':TITLE, 'lead':LEAD, 'request':identity,
            'steps':[{'name':name} for name in ['자료와 질문 파악','요구와 기대 답 정하기','조회와 판단 계획 검토','작게 구현하고 실행','실제 결과를 원문과 견주기','다른 입력으로 고치기','저장하고 다시 열기']],
            'decisions':['근거를 읽을 범위와 넓히는 조건','일부 근거가 비었을 때 다음 역할로 전달할 단위와 순서'],
            'cases':['문서 조건에 맞는 관측','조건·판본·기간이 다른 근거','수집 공백·오래된 값·빈 조회·실제 오류','다른 설비 또는 날짜'],
            'ai_turns':8}


def guide_sections(L):
    identity=L['request']; run='python run.py'; collect=f'{run} --collect --request {identity}'
    source=f'{run} --source data/documents/hm_8_1_1.md --start 25 --end 43'
    sections=[]
    body=paragraph('온톨로지에서 찾은 원인 후보는 이번 사건의 확정 원인이 아닙니다. 문서 조건과 현재 관측을 따로 찾는 **에이전트 단계**에서, 정비 담당자가 검토할 후보·다음 점검·추가 자료가 필요한 질문을 만듭니다. 자료 파악 → 내 요구와 기대 → 계획 → 기능별 구현·실행 → 원문과 견주기 → 다른 입력 확인 → 저장 순서로 진행합니다.')
    body+=paragraph('클래스룸 **🧪 05회차 실습 자료**에서 ZIP을 내려받아 **압축 풀기**를 합니다. VS Code의 **파일 → 폴더 열기**에서 `root-cause-lab` 폴더만 엽니다. 가이드는 옆의 `root-cause-lab_guide.html`을 브라우저로 엽니다. 위 폴더까지 열면 Codex가 답이 든 가이드를 읽을 수 있습니다. 직접 받은 폴더인지 확인한 뒤 신뢰 창에서 신뢰합니다.')
    body+=frame.block('tree','root-cause-lab/\n├ README.md\n├ AGENTS.md\n├ data/\n├ app/\n│  ├ features/\n│  ├ ui/\n│  └ utils/\n└ run.py')
    body+=paragraph('탐색기에서 `README.md`로 목적과 첫 명령을 봅니다. `AGENTS.md`는 Codex가 지킬 공통 작업 원칙입니다. VS Code의 Codex 채팅을 열고 로그인이 필요한 경우 개인 GPT 계정으로 로그인합니다. **터미널 → 새 터미널**에서 현재 위치가 `root-cause-lab`인지 봅니다. 명령과 글은 오타로 다른 파일을 다루지 않도록 **복사** 단추로 가져옵니다.')
    body+=command(run+' --inspect')
    body+=paragraph('터미널에는 제공 지식의 노드·관계 수, 요청 수와 읽기 도구가 나옵니다. `data/requests.csv`에서 기본 요청의 설비와 기준시각을 찾고, `data/source_manifest.json`과 `data/field_notes.md`에서 문서 판본·수집 범위를 연결합니다. 10초 자료는 개별 관측 표본이며 평균이 아닙니다. 질문에 필요한 값이 어느 출처에 있는지 알아야 다음에 기대 답을 정할 수 있습니다.')
    body+=paragraph('Codex에게 기본 요청의 질문을 받는 역할과 문서·그래프·관측의 위치를 물어봅니다. 파일을 바꾸지 말고 근거를 찾게 한 뒤, 답에 나온 문서의 판본과 줄을 직접 열어 확인합니다. 찾지 못한 항목은 모르는 것으로 남깁니다.')
    sections.append((L['steps'][0]['name'],body))

    body=paragraph('누가 이 결과로 무엇을 할지 먼저 정합니다. `app/features/requirements.md`에 받을 역할·질문·지킬 조건을 내 말로 적고, `choices.csv`에 선택·원문 근거·그 선택으로 달라질 다음 행동을 적습니다. **증거 대조**는 원인 후보의 조건과 현재 관측을 비교해 충족·해당 없음·보류를 구분하는 일입니다.')
    body+=paragraph('하나는 **근거 묶음**입니다. 숫자 한 줄로 충분한지, 표머리·적용 조건·인접절이나 같은 운전 조건의 다른 기간이 필요한지 정합니다. 다른 하나는 **점검 전달**입니다. 근거가 일부 비었을 때 확인한 범위부터 나눠 보낼지, 요청 전체의 근거를 모아 전달할지 대상과 받을 역할에 맞춰 정합니다. 문서의 안전 조건을 바꾸는 선택은 아닙니다. AI가 권장안을 붙이면 원문을 열어 내 선택과 이유를 다시 말합니다.')
    body+=command(source)
    body+=paragraph('원문 도구는 줄 번호와 글을 그대로 보여 줍니다. 목록의 원래 파일 이름은 `source_manifest.json`의 `catalog_file`에서 실제 `file`로 연결합니다. `expected.csv`에는 세 후보의 적용 조건, 관측을 쓸 수 있는 기준, 작업 전제 등 이번 요청에서 확인할 질문과 기대·출처를 먼저 적습니다. 관측을 아직 조회하지 않았다면 수치나 상태를 짐작하지 말고 미확인으로 둡니다. 그래야 이후 실제 반환을 원문과 견줄 수 있습니다.')
    body+=paragraph('내가 찾은 원문과 수집 조건을 Codex에게 설명하고, 선택에 따라 달라질 조회 범위와 다음 행동을 함께 짚습니다. `data/field_notes.md`의 업무 범위에는 수신 역할이 아직 정하지 않은 전달 요구가 있습니다. 문서 조건과 사람의 업무 선택을 구분하고 내 요구와 이유를 말합니다. choices.csv의 decision에는 적용 기능인 query 또는 deliver를, 나머지 칸에는 내 선택·출처·달라질 행동을 적습니다. 전달 요구가 비어 있으면 수집·판정은 볼 수 있어도 다음 점검을 정한 것으로 보지 않습니다.')
    body+=answer('우리가 파일을 바꾸지 않고 파악한 요청과 원문을 바탕으로 내가 적은 app/features/requirements.md, choices.csv, expected.csv를 읽어줘. 선택이 미정이면 내게 근거와 선택을 물어봐. 선택을 대신하지 말고, 선택한 근거 범위와 전달 방침이 다음 역할의 행동을 어떻게 바꾸는지 확인해줘. 기대값을 AI 답으로 채우지 말고 내가 제시한 원문 줄에서 확인되는 조건과 아직 모르는 관측을 나눠줘. 지금은 판단 코드를 만들지 마.')
    body+=command(run+' --show')+paragraph('`output/result.html`을 탐색기에서 **파일 탐색기에 표시**한 뒤 두 번 클릭해 브라우저로 엽니다. 내가 실제 작성한 요구·선택·기대만 보입니다. 이후 명령을 실행한 뒤에는 이 화면을 새로고침합니다.')
    sections.append((L['steps'][1]['name'],body))

    body=paragraph('한 번에 전체 결과를 만들면 어느 선택이 잘못됐는지 찾기 어렵습니다. `app/features/plan.md`에서 조회 범위 → 증거 대조 → 점검 전달로 기능을 나눕니다. 각 기능의 입력과 확인할 출력, 다른 문서 판본·기간·공백이 섞일 때 확인할 근거를 검토합니다. 파일 읽기·모델 호출·계약 조립·화면은 제공됩니다.')
    body+=paragraph('Codex에게 내 요구·선택·기대와 세 파일의 함수 설명을 읽게 합니다. 어떤 입력을 받아 무엇을 반환하고 어느 원문으로 확인할지 기능별로 제안받습니다. 모델의 도구 선택이 고정 순서의 답 조회로 바뀌지 않는지 계획에서 확인합니다.')
    body+=answer('내 요구와 choices.csv의 선택을 바꾸지 말고 plan.md에 작은 구현 계획을 제안해줘. query.py는 필요한 도구를 모델이 고르게 하고 실제 인수를 내 기준에 맞춘다. assess.py는 그 실제 반환으로 후보와 미확인을 판정한다. deliver.py는 그 판정을 받아 내가 정한 전달 방침을 적용한다. 각 기능에서 원문·관측의 무엇을 대조할지 적어줘. 내가 계획을 확인하기 전에는 세 기능을 구현하지 마.')
    body+=paragraph('조회 전략이 기준 방법보다 복잡해졌다면 필요한 근거를 더 잘 보존하는지 따져 봅니다. 단순한 방법이 충분하면 유지합니다. 문서 전체를 다시 지식화하거나 뒤 회차의 Skill·명세 도구를 만들지는 않습니다.')
    sections.append((L['steps'][2]['name'],body))

    body=paragraph('계획의 기능 하나씩 Codex에 요청하고 실행 결과를 봅니다. 첫 기능이 실제 근거를 모으면, 그 반환을 그대로 다음 두 기능에 사용합니다. 판단이나 전달만 고칠 때는 모델을 다시 부르지 않습니다.')
    body+='<h3>조회 범위를 구현하고 실제 근거 보기</h3>'
    body+=paragraph('query.py의 두 함수가 무엇을 받는지 Codex에게 먼저 설명받습니다. 내 질문에 필요한 근거를 모델이 고르도록 지침을 만들고, 내가 선택한 원문·설비·기간 기준을 실제 인수에 반영하게 요청합니다. 실행 뒤 모델 인수와 반영 뒤 인수, 반환된 원문 범위를 나란히 봅니다.')
    body+=answer('앞에서 검토한 plan.md와 내가 고른 근거 묶음을 적용해 app/features/query.py의 instructions와 prepare_query만 구현해줘. 실제 도구의 인수 계약을 읽고, 어떤 문서 판본·설비·기간을 요청할지 모델이 반환을 보고 선택하게 해줘. 내가 확인한 적용 조건과 주변 원문을 잃지 않도록 범위를 반영하되 조회 결과나 값을 지어내지 마. assess.py와 deliver.py는 바꾸지 마. 실행 명령과 변경 파일을 알려줘.')
    body+=paragraph('모델 접속 세 줄을 받았다면 `.env.example`을 복사해 `.env`로 이름을 바꾸고 받은 세 줄 그대로 저장합니다. 키를 채팅이나 공유 파일에 넣지 않습니다. 개인 GPT 로그인은 API 키와 별개입니다. 세 줄이 없으면 아래 채팅 경로를 사용합니다.')
    body+=command(collect)
    body+=paragraph('API 키가 없으면 터미널에 `output/model_requests/`의 요청 글과 붙여넣기 명령이 나옵니다. 이 폴더를 모르는 별도 Codex 채팅에 요청 글을 보내 JSON 답을 받습니다. 터미널에 나온 `python run.py --paste … --model …`을 그대로 실행해 답을 붙여 넣고, 새 줄에서 **Ctrl+Z → Enter**로 끝냅니다. 같은 수집 명령을 다시 실행하면 그 반환부터 이어집니다. 필요한 조회가 남으면 이 동선을 반복합니다. 모델이 독립 조회를 묶으면 한 답에서 여러 도구가 실행됩니다.')
    body+=paragraph('결과 화면의 **조회 근거**에서 실제 도구·출처·시각을 보고 **입력·반환 원문 펼치기**로 모델 인수와 실제 인수·반환을 견줍니다. 수집이 끝나면 **모델이 쓴 요약**도 보입니다. 그 요약은 검토 대상입니다. 도구 오류가 있으면 실제 오류와 빠진 근거를 확인합니다. 필요한 근거가 없으면 조회 기능을 고쳐 수집하며, 기준이나 자료가 바뀌면 이전 반환은 이전판으로 구분됩니다.')
    body+='<h3>같은 반환으로 후보 판정 보기</h3>'
    body+=paragraph('수집 기록에서 내 기대를 검증할 반환을 Codex와 찾습니다. 적용 조건·창·품질·표본·시각이 충분한 경우에만 수치를 대조하도록 assess.py를 구현합니다. 값 없음·0·조건 불충족을 구분하고, 실제로 받은 출처만 후보의 상태·이유·근거에 연결합니다.')
    body+=answer('방금 수집한 실제 원 반환과 내가 먼저 작성한 expected.csv를 읽고 app/features/assess.py만 구현해줘. 원문의 적용 조건이 현재 관측에 맞는지 확인한 뒤 수치를 대조하고, 채택 지식에서 실제 원문으로 연결된 반환을 근거에 붙여줘. 값 없음이나 조건 미확인을 False 또는 0으로 바꾸지 마. 다른 요청에도 같은 근거 판정이 작동하게 하고 모르는 것은 추가 확인으로 남겨줘. 반환 계약에 맞춰 후보·미확인·안전 근거를 돌려주되 전달 방침은 구현하지 마.')
    body+=command(f'{run} --assess --request {identity}')
    body+=paragraph('화면의 **원인 후보의 증거 대조**를 보고, 추가 자료가 필요한 질문은 **추가 확인할 근거**에서 찾습니다. 후보 근거 링크를 눌러 실제 원문·판본·시각으로 따라갑니다. 이 명령은 저장된 원 반환을 계산하므로 모델 응답을 새로 받지 않습니다. 잘못된 후보가 있으면 원문 기대와 실제 반환을 전해 판정 기능만 고칩니다.')
    body+='<h3>후보 판정으로 다음 점검 보기</h3>'
    body+=paragraph('현재 후보와 미확인을 읽고 내가 choices.csv에서 고른 방침을 Codex에게 다시 말합니다. deliver.py는 제공 코드가 읽어 준 deliver 행을 실제 입력으로 받습니다. 그 요구를 후보 상태에 적용해 받을 역할·할 일·작업 전제·근거를 만들고, 일부 근거가 없을 때 역할과 확인 순서가 어떻게 달라지는지 봅니다. 문서상의 전제를 실제 현장 확인이나 승인으로 바꾸지 않습니다.')
    body+=answer('현재 assessment.json과 내 choices.csv의 점검 전달 선택을 사용해 app/features/deliver.py만 구현해줘. 확인한 범위를 먼저 나누어 보낼지 요청 전체를 묶을지는 내가 고른 방침을 그대로 적용해줘. 어떤 근거가 비었는지에 따라 다음 역할이 할 일이 실제로 달라져야 해. 안전 원문을 실제 현장 확인·승인으로 바꾸지 말고, 기존 후보 판정을 이 함수에서 다시 만들지 마. run.py의 전달 명령으로 결과를 확인할 수 있게 해줘.')
    body+=command(f'{run} --deliver --request {identity}')
    body+=paragraph('**다음 점검**과 **점검 전달에 사용한 요구**에서 실제 입력·출처·후속 행동을 함께 봅니다. **전달 요구 확인 필요**는 업무 입력이 미정이라는 뜻이며 점검 계획이 아닙니다. 선택을 바꾸면 옛 전달 결과는 현재 화면에서 빠집니다. 바뀐 요구에 맞춰 전달 기능을 고쳐 같은 명령으로 실행하며 수집·판정은 반복하지 않습니다. 출처만 정정해도 전달 명령으로 입력판을 다시 연결합니다.')
    sections.append((L['steps'][3]['name'],body))

    body=paragraph('화면이 나왔다고 뜻까지 맞은 것은 아닙니다. `app/features/review.csv`에 미리 적은 기대, 실제 결과, 견준 원문과 일치·불일치·미확인을 적습니다. 세 후보마다 적용 조건·문서 상태·관측 창·통계량·단위·표본·공백·최신 시각을 확인하고, 근거 연결에서 실제로 받은 지식과 원문이 이어지는지 봅니다.')
    body+=paragraph('압축 관측의 근거 행은 **조회 근거** 상세에 있습니다. 다음 명령의 파일과 시작·끝 줄을 실제 반환이 가리킨 것으로 바꿉니다. 첫값·평균·마지막값을 구분합니다. 모델이 쓴 요약도 원문과 견주고, 틀린 문장을 원 응답에서 지우지 말고 review.csv에 정정합니다.')
    body+=command(run+' --source <실제 반환의 data/observations/파일.csv.gz> --start <시작 줄> --end <끝 줄>')
    body+=paragraph('원문으로 먼저 적은 expected.csv와 실제 반환·모델 요약·점검 계획을 함께 펼칩니다. 부하·판본·표본·시각·안전 전제가 일치하는지 확인하고 review.csv에 기대·실제·근거·판정을 남깁니다. 실제 출력에 맞춰 기대를 고치지 않습니다.')
    body+=answer('내 expected.csv와 실제 결과를 원문과 견준 내용을 기준으로 review.csv의 빠진 비교를 짚어줘. 후보 상태뿐 아니라 모델 요약의 첫값·평균·마지막값 표현, 뒤에 성공한 조회의 반영, 지식에서 원문까지의 실제 근거 연결을 따로 봐줘. 원 응답을 수정하지 말고 틀린 표현은 내 검토 기록에만 구별해 적도록 도와줘. 내가 직접 확인하지 않은 줄이나 결과는 확인했다고 쓰지 마.')
    body+=command(f'{run} --check --request {identity}')
    body+=paragraph('구조 검사는 필수 칸·중복·없는 근거 참조를 확인합니다. 오류가 0개여도 업무 의미는 원문과 견주어 판단합니다. 실제 오류가 있으면 실행 명령·오류 전문·해당 화면과 기대 근거를 Codex에 보내 그 기능만 고칩니다.')
    sections.append((L['steps'][4]['name'],body))

    body=paragraph('기본 요청에만 맞춘 코드인지 확인할 차례입니다. `data/requests.csv`에서 다른 설비나 날짜의 요청 하나를 직접 고릅니다. 운전 조건이 다르거나 수집 공백이 있는지 원문 이력과 자료 범위를 먼저 보고, expected.csv에 새 요청의 기대와 아직 모르는 항목을 적습니다. 기존 요청 ID를 억지로 바꾸거나 관측값을 채우지 않습니다.')
    body+=command(run+' --collect --request <내가 고른 다른 요청 식별자>')
    body+=paragraph('새 요청은 새 수집이 필요합니다. 조회 결과가 기존 기대와 다르면 이유가 자료인지 코드인지 구분합니다. 수집된 근거가 충분하면 아래 두 기능을 실행합니다. 후보 판정이나 전달만 고쳤다면 수집을 반복하지 않습니다. 조회 범위·자료를 바꿨다면 새 수집을 해야 하며, 완료되지 않은 새 판에서 이전 계획은 현재 결과로 표시되지 않습니다.')
    body+=command(run+' --assess --request <같은 요청 식별자>')+command(run+' --deliver --request <같은 요청 식별자>')
    body+=paragraph('새 요청에서 먼저 적은 기대와 실제 원 반환을 Codex에게 보여 줍니다. 근거가 없을 때 보류되는지, 내 전달 방침에 맞춰 다음 역할과 확인 순서가 달라지는지 봅니다. 근거가 충분해 두 방침의 행동이 같다면 그대로 기록합니다. 차이를 만들려고 관측을 바꾸거나 근거를 빼지 않습니다. 이미 맞은 코드에는 오류를 넣지 않고 review.csv에 원문과 견준 근거를 남깁니다.')
    body+=answer('내가 새 요청에서 먼저 확인한 기대·원문과 실제 결과를 비교해줘. 다르면 원인을 query.py의 조회 범위, assess.py의 근거 판정, deliver.py의 전달 가운데 해당 기능으로 좁혀 그 파일만 고쳐줘. 후처리만 바뀌면 저장된 원 반환으로 판정·전달만 다시 실행하고, 조회 기준이나 자료가 바뀌면 새 수집이 필요한 이유를 말해줘. 이미 맞으면 고치지 말고 다른 입력에서 확인한 근거를 남기자.')
    body+=paragraph('자기 4회차 결과 사용은 선택입니다. 별도 폴더에 내보내기·확장 스키마·그래프 모양을 `graph.json`·`schema.json`·`shape.json`으로 복사합니다. 수집·판정·전달 명령 모두에 `--graph-folder "<별도 폴더 경로>"`를 더하고, 확인할 때도 아래처럼 같은 요청과 그래프를 함께 지정합니다. 뜻 대응과 출처 속성 계약을 검사하며 지원하지 않는 모양은 빠진 칸을 알리고 멈춥니다. 원본을 덮지 말고 계약을 맞추거나 기본 제공판으로 시작합니다.')
    body+=command(run+' --check --request <같은 요청 식별자> --graph-folder "<별도 폴더 경로>"\n'+run+' --show --request <같은 요청 식별자> --graph-folder "<별도 폴더 경로>"')
    body+=paragraph('검사는 이 요청과 그래프의 현재 결과를 확인하고, 화면은 그 결과만 보여 줍니다. 요청마다 다른 그래프를 썼다면 각 요청에 사용한 폴더 경로도 plan.md에 남깁니다. 다른 그래프를 지정했을 때 이전 결과로 구분되는 것은 새 입력의 결과로 볼 수 없기 때문입니다.')
    sections.append((L['steps'][5]['name'],body))

    body=paragraph('수정 파일을 저장한 뒤 같은 `root-cause-lab` 폴더를 닫았다 다시 엽니다. 새 ZIP을 다시 풀면 다른 시작 폴더가 되므로 지금 작업한 폴더를 엽니다. 학교 PC가 초기화되기 전에 개인 저장소나 USB에 이 폴더를 보관합니다. 자기 그래프를 썼다면 별도 그래프 폴더도 함께 보관하고, 옮겨진 경로를 명령에 사용합니다. 접속 키는 공유하지 않습니다.')
    body+=command(run+' --show --request <다시 볼 요청 식별자>')
    body+=paragraph('제공 그래프로 실행한 요청은 위 명령을 쓰고, 자기 그래프로 실행한 요청은 앞 절의 `--graph-folder`를 포함한 검사·화면 명령을 같은 요청과 그래프 경로로 다시 실행합니다. `app/features/`의 내 판단 코드·선택·기대·검토 기록과 `output/result.html`에서 각 요청의 실제 근거·후보·다음 점검을 다시 봅니다. `output/runs/<요청 식별자>/`의 `collection.json`은 수집 원 반환, `assessment.json`은 후보 판정, `root_plan.json`은 점검 전달 결과입니다. 입력이나 코드가 달라진 결과는 이전판으로 구분합니다. 모델 요약과 내가 정정한 검토 기록이 섞이지 않는지 확인합니다.')
    body+=paragraph('끝낼 조건은 실제 도구 선택과 반환, 원문에 근거한 후보 상태, 내 선택이 바꾼 조회 범위·다음 행동, 다른 요청의 결과를 원문과 견준 기록이 모두 남는 것입니다. 충족을 현장 원인 확정·작업 완료로 쓰지 않습니다. 계정이 없거나 정답을 보고도 막히면 실습 폴더와 따로 받는 학생용 완성본으로 결과를 봅니다.')
    sections.append((L['steps'][6]['name'],body))
    return sections


def build(report, refresh_data=False, photos=None):
    started=time.perf_counter(); report=Path(report); report.parent.mkdir(parents=True,exist_ok=True)
    if refresh_data:
        source=report.parent/'data_generation'
        data_agent_evidence.build(source,report.with_name('원인랩_자료생성.json'))
        data_agent_evidence.project_data(source,LAB,report.with_name('원인랩_경로와원문대응.json'))
    elif not (LAB/'data/data_manifest.json').exists():
        data_agent_evidence.project_data(LEGACY,LAB,report.with_name('원인랩_경로와원문대응.json'))
    data=json.loads((LAB/'data/data_manifest.json').read_text(encoding='utf-8'))
    requests=list(csv.DictReader(line for line in (LAB/'data/requests.csv').read_text(encoding='utf-8-sig').splitlines() if not line.startswith('#')))
    if DEFAULT_REQUEST not in {row['request_id'] for row in requests}: raise ValueError('기본 요청이 원자료에 없습니다.')
    previous_default=data['default_request']; data['default_request']=DEFAULT_REQUEST
    frame.dump(LAB/'data/data_manifest.json',data); L=definition(DEFAULT_REQUEST)
    if (LAB/'output').exists(): raise ValueError('생성 대상에 실행 결과가 있습니다. 학생 작업 폴더를 덮어쓰지 않습니다.')
    for name in ['evidence.py','workflow.py','contracts.py','source_cli.py']:
        frame.write(LAB/'app/utils'/name,(HERE/'agent_tools'/name).read_text(encoding='utf-8'))
    frame.write(LAB/'app/ui/render.py',(HERE/'agent_tools/result_steps.py').read_text(encoding='utf-8'))
    for name in ['app/__init__.py','app/features/__init__.py','app/ui/__init__.py','app/utils/__init__.py']: frame.write(LAB/name,'')
    frame.write(LAB/'app/utils/llm_client.py',(HERE/'lab_llm.py').read_text(encoding='utf-8'))
    frame.write(LAB/'run.py','from pathlib import Path\nfrom app.utils.workflow import main\n\nif __name__ == "__main__":\n    raise SystemExit(main(Path(__file__).resolve().parent))\n')
    frame.write(LAB/'.env.example','OPENAI_BASE_URL=\nLLM_API_KEY=\nLLM_MODEL=\n')
    write_metadata(LAB,TITLE,LEAD,'python run.py --inspect', '조회·판정·전달은 각각 query.py·assess.py·deliver.py에서 구현한다. 요구·선택·기대·대조 기록도 app/features/에 둔다. field_notes.md에 정해지지 않았다고 적힌 전달 시점·확인 역할은 사람의 요구를 확인하고 choices.csv에 그 선택과 근거를 남긴 뒤 구현한다. 선택·근거를 AI가 만들어 채우지 않는다. 출력 계약의 조립과 모델 호출은 제공 기능을 사용한다.')
    for name,text in FEATURES.items(): frame.write(LAB/'app/features'/name,text)
    fields={'choices.csv':(['decision','choice','source','changed_action'],'decision=적용 기능 query/deliver, choice=내가 정한 기준 또는 전달 요구, source=원문 위치와 사람이 확인한 업무 근거, changed_action=달라지는 조회 또는 다음 행동'),
            'expected.csv':(['request_id','question','expected','source'],'request_id=요청 식별자, question=확인할 질문, expected=원문으로 먼저 정한 기대 또는 미확인, source=원문 파일:줄'),
            'review.csv':(['request_id','question','expected','actual','source','judgment'],'request_id=요청 식별자, question=질문, expected=미리 적은 기대, actual=실행에서 본 내용, source=대조 근거, judgment=일치/불일치/미확인')}
    for name,(columns,note) in fields.items(): frame.write(LAB/'app/features'/name,frame.blank_csv(columns,note))
    frame.write(LAB/'app/features/requirements.md','# 받을 역할과 질문\n\n# 결과가 담을 것과 지킬 조건\n')
    frame.write(LAB/'app/features/plan.md','# 기능별 입력·할 일·확인 근거\n')
    frame.write(LAB/'data/field_notes.md',(HERE/'agent_tools/data_notes.txt').read_text(encoding='utf-8'))
    sections=guide_sections(L); guide=frame.step_page(TITLE,LEAD,sections)
    guide=guide.replace('</style>','main,section,.block{min-width:0}pre,code,p,li{overflow-wrap:anywhere}table{word-break:keep-all} .hint p{margin:10px 0}@media(max-width:600px){main{padding:20px 12px}section{padding:18px 14px}}'+'</style>')
    if photos:
        for photo in json.loads(Path(photos).read_text(encoding='utf-8')):
            raw=Path(photo['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=photo['sha256']: raise ValueError('사진 해시 불일치')
            marker=f'<section id="s{photo["stage"]}">'; tag=f'<figure><img alt="{html.escape(photo["description"])}" src="data:image/png;base64,{base64.b64encode(raw).decode()}"><figcaption>{html.escape(photo["description"])}</figcaption></figure>'
            guide=guide.replace(marker,marker+tag,1)
    frame.write_guide(LAB,guide,ai_turns=L['ai_turns'])
    files={p.relative_to(LAB).as_posix():p.read_bytes() for p in LAB.rglob('*') if p.is_file() and p.suffix!='.pyc'}
    errors=layout_errors(files,LAB.name)
    if errors: raise ValueError('\n'.join(errors))
    archive=pack(LAB); item=entry('integrated-05-root-cause','통합반','05',TITLE,VERSION,LAB,guide_steps=[name for name,_ in sections])
    result={'version':VERSION,'seconds':round(time.perf_counter()-started,3),'folder':LAB.relative_to(ROOT).as_posix(),'zip_bytes':archive.stat().st_size,'package_entry':item,'definition':L,'default_request_change':{'before':previous_default,'after':DEFAULT_REQUEST,'raw_request_rows_changed':False},'guide_cost':frame.guide_cost(guide,ai_turns=L['ai_turns']),
            'largest_files':sorted([{'path':p.relative_to(LAB).as_posix(),'bytes':p.stat().st_size} for p in LAB.rglob('*') if p.is_file()],key=lambda x:x['bytes'],reverse=True)[:8],
            'unverified':['새 입력의 실제 모델 호출 영향','새 AI 작업 규칙의 장난감 시험','기능별 가이드 토글의 변경 영향','새 입력의 완성본'],
            'deferred_by_user':['새 화면 캡처·촬영·네이티브 받기 장면은 후속 요청 때 수행']}
    frame.dump(report,result); print(json.dumps(result,ensure_ascii=False,indent=2));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh-data',action='store_true');parser.add_argument('--report',type=Path,default=ROOT/'작업/2026-11-10_통합5-에이전트랩-개편/판정/원인랩_새구조생성.json');parser.add_argument('--photos',type=Path)
    args=parser.parse_args();build(args.report,args.refresh_data,args.photos)
