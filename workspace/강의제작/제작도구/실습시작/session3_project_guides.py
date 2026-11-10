"""냉각 경보 조치 판단 네 프로젝트의 가이드 원고 — 단계마다 지금 하는 이유, 어디서 무엇을 먼저 하는지, 무엇을 확인하는지만 쓴다.
단계 순서는 기존 랩 정의(build_judgement_labs.py)의 순서를 기능 단위로 옮긴 것이다. 정답 토글은 앞 단계에서 정한 자료 · 요구 · 선택을 전제로 지금 기능만 요청한다.
이름은 과정 용어 장부를 따른다: 조건표(줄 하나 = 규칙), 비교값, 정책 점수, 판정 요청, 정할 지점, HM-8 매뉴얼 원문."""
import csv
import io

import build_judgement_labs as BJ
import lab_frame as F
from session2_project_guides import section

PURPOSE = {
    'integrated-03-criteria': '포털의 조치 방법 · 판단 규칙 화면에서 본 근거를 HM-8 매뉴얼 원문에서 직접 찾습니다. 작업 절차(SOP 구조)와 판단 조건(조건표)으로 나누고 제공된 설비 모델(2회차 그래프 구현 실습과 같은 모델)의 ID에 잇습니다.',
    'integrated-03-judge': '포털은 사실을 자동으로 모아 경보 한 건씩 판단했습니다. 이번에는 조치 기준 만들기와 같은 꼴로 제공된 조건표로 원천 기록에서 냉각 조치 후보를 직접 판정하고 주어진 비교 산식으로 견주며, 지난 30일 경보 전체로 기능을 검증합니다.',
    'practical-02-conditions': '포털 판단 규칙 화면에서 본 허용 · 제외의 근거를 HM-8 매뉴얼 원문에서 직접 뽑아 조치 조건표로 만듭니다. 판단 시스템에 등록된 결정표와 줄마다 출처를 견줍니다.',
    'practical-03-review': '포털에서 순위가 높아도 금지 조건에 걸리면 고를 수 없는 이유를 결과에서 찾았습니다. 이번에는 조치 조건표와 같은 꼴로 제공된 조건표로 사건과 지난 30일 경보를 원천 기록에서 직접 판정하고 견주어, 담당자가 읽고 바로 결정할 수 있는 조치 검토 결과로 완성합니다.',
}
STAGE = {'integrated-03-criteria': '판단 지식 — 절차와 판단 조건을 원문에서 구조화해 설비 모델에 잇는 일 — ',
         'practical-02-conditions': '판단 지식 — 작업 기준의 조건을 판단 규칙으로 옮기는 일 — ',
         'integrated-03-judge': '판단 지식 — 조건표로 조치를 판정하고 견주는 일 — ', 'practical-03-review': '판단 지식 — 조건표로 조치를 판정하고 견주는 일 — '}
SESSION = {'integrated-03-criteria': 3, 'integrated-03-judge': 3, 'practical-02-conditions': 2, 'practical-03-review': 3}
MANUAL = 'HM-8 매뉴얼 원문(`data/hm8_manual.md`, 현행 1.1판)'
TABLE_TERM = ('조건표는 판단 규칙을 한 줄씩 적은 표로, DMN(판단을 표준 모양으로 적는 방식)의 결정표와 같은 꼴입니다. 한 줄이 규칙 하나이고, 어떤 입력이 어떤 값일 때 조치를 경고 · 감점 · 제외하는지 적습니다. '
              '「이상 · 이하」는 기준값을 포함하고 「초과 · 미만」은 포함하지 않아 기준값과 같은 값에서 결과가 갈립니다. 여러 규칙이 함께 맞으면 경고 · 감점 · 제외를 모두 모읍니다.')
WORDS = ('**경고**는 그 조치에 주의할 점이 있다는 사유, **감점**은 비교할 때 금액으로 깎는 사유, **제외**는 그 조치를 쓸 수 없는 사유입니다. '
         '판정은 그 사유를 모아 **유지** · **제외** · **보류**로 나뉩니다. **보류**는 정보가 부족해 판정을 미룬 것으로, 제외 사유는 없지만 입력이 없어 맞는지 알 수 없는 규칙(화면의 「미확인」)이 있는 후보입니다. '
         '세 말의 뜻은 `data/work_standard.md` 4절에 있습니다.')
UNKNOWN = '입력이 없어 확인할 수 없는 조건은 거짓과 달라 보류로 남고, 이미 확인된 제외 사유는 다른 입력이 빠져도 그대로입니다.'
SOURCE = '판단 시스템의 결정표는 만들 때의 판으로 적혀 있어, 어느 줄이 지금 원문의 어느 문장과 같은지 찾은 근거를 남겨야 다른 사람이 같은 판단을 다시 할 수 있습니다.'
OPEN_RESULT = ('결과는 `output/result.html`에 저장됩니다. 브라우저가 열리지 않으면 Windows 파일 탐색기로 이 실습 폴더의 output 폴더를 열고 result.html을 두 번 누릅니다'
               '(VS Code 탐색기에서 누르면 화면이 아니라 HTML 글이 열립니다). 이후에는 명령을 실행한 뒤 열린 화면에서 F5를 누릅니다.')
SAVE_USB = '재부팅하면 학교 PC 파일이 초기화될 수 있으므로 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다.'
DECIDE = '고른 것은 의견처럼 말하지 않고 무엇으로 정했는지와 근거 줄을 단정해서 말합니다. AI가 고르거나 「권장」을 붙여도 따르지 말고 원문 줄을 열어 내 선택을 말합니다.'
HANDS = '손으로 고친 파일은 **Ctrl+S**로 저장한 뒤 명령을 실행합니다(저장하지 않으면 화면에 0행으로 보입니다).'
EDIT = ('Codex가 파일을 고치려 할 때 승인 창이 뜨면 `app/features/` 아래 파일일 때만 **Allow once**를 누르고, 다른 경로면 거절합니다. '
        '명령은 내가 터미널에서 실행하고, Codex가 옮겨 적은 출력이 아니라 터미널 출력과 결과 화면으로 확인합니다.')
DONE = {
    'integrated-03-criteria': '사건 네 후보의 기대 판정과 조건표를 댄 판정이 같고, 정할 지점마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으며, SOP 구조와 조건표의 항목마다 HM-8 매뉴얼 원문 문장으로 돌아갈 수 있으면 완료입니다.',
    'practical-02-conditions': '조건표의 줄마다 원문 문장으로 돌아갈 수 있고, 먼저 적은 기대 판정과 조건표를 댄 판정이 같고, 정할 지점의 근거와 그 선택으로 바뀌는 사례를 설명할 수 있으며, 남은 후보와 실행 승인을 따로 말할 수 있으면 완료입니다.',
    'integrated-03-judge': '사례 종류마다 먼저 적은 기대와 실행 결과가 같거나 다른 까닭을 review.md에 적었고, 손계산 예의 네 손실이 프로그램 값과 같으며, 정할 지점의 근거와 그 선택으로 바뀌는 판단 입력 · 순위를 설명할 수 있으면 완료입니다.',
    'practical-03-review': '사례 종류마다 먼저 적은 기대와 실행 결과가 같거나 다른 까닭을 review.md에 적었고, 손계산 예의 네 손실이 프로그램 값과 같으며, 사건 절만 읽고 후보마다 판정 · 까닭 · 승인 역할 · 먼저 확인할 값을 말할 수 있고, 정할 지점의 근거와 그 선택으로 바뀌는 검토 의견을 설명할 수 있으면 완료입니다.',
}


def project(key):
    return __import__('build_session3_projects').PROJECT[key]


def setup(key, line, check):
    practical = key.startswith('practical')
    text = [f'클래스룸의 {SESSION[key]}회차 실습 자료에서 ZIP을 받아 **압축 풀기**를 선택합니다. VS Code의 **파일 → 폴더 열기**에서 `{project(key)}` 폴더를 엽니다. '
            '그 위 폴더를 열면 AI가 함께 풀린 가이드까지 읽으므로 이 폴더를 엽니다. 가이드는 브라우저로 엽니다.',
            '신뢰 여부를 물으면 **예, 작성자를 신뢰합니다**(Yes, I trust the authors)를 선택합니다. 제한 모드에서는 Codex를 사용할 수 없습니다.']
    if practical:
        text.append('`README.md`에서 폴더 역할을 봅니다. `data/`는 읽기만 하는 자료, `app/features/`는 AI와 채울 판단 자리이고, 화면과 공통 처리는 제공됩니다. '
                    '`AGENTS.md`는 Codex의 공통 작업 원칙, `data/contract.md`는 채울 파일의 모양입니다.')
    else:
        text.append('`README.md`를 열어 폴더 역할을 봅니다. `data/`는 읽기만 하는 자료, `app/features/`는 AI와 채울 판단 자리입니다. 화면 표시와 공통 처리(파일 읽기 · 원문 인용 · 조건표 적용 · 검사)는 제공됩니다. '
                    '`AGENTS.md`는 Codex가 지킬 공통 원칙을 담은 헌법 파일이고, `data/contract.md`는 채울 파일의 모양(열 · 키와 그 뜻)을 정한 문서입니다.')
    text += [line, '**터미널 → 새 터미널**을 엽니다. 오타를 줄이도록 명령 블록의 **복사**를 눌러 붙여 넣고 Enter를 누릅니다.']
    return section('폴더 열고 자료 확인하기', text, cmd='python run.py', check=check + ' ' + OPEN_RESULT)


def login(key):
    return (f'Codex 확장 아이콘을 눌러 채팅을 열고 계정에 로그인합니다. 계정이 없거나 구현 중 막히면 클래스룸에서 실습 폴더와 따로 받는 완성본 ZIP(`{project(key)}-completed.zip`)으로 결과를 실행해 볼 수 있습니다.')


def points(L):
    return ('정할 지점은 ' + ' · '.join(f'「{name}」' for name, _ in L['decide']) + '입니다. 여기서는 어떤 지점이 있는지만 봐 두고, 그 지점을 다루는 단계에서 원문을 열어 정한 뒤 '
            '`app/features/decisions.csv`의 지점 칸에 그 이름을 그대로 써서 한 줄씩 적습니다(열의 뜻은 파일 첫 줄). AI의 추천은 선택 근거가 되지 않습니다.')


def questions(L):
    return '질문: ' + ' '.join(f'{"①②③"[i]} {q}' for i, q in enumerate(L['questions'])).replace('판단 요청', '판정 요청').replace('포털 성과 지표의 점수', '정책 점수')


def structure_check(record, recovery):
    return section('구조 확인하기', [
        '답의 의미를 확인했으므로 식별자 · 열 · 짝의 모양을 검사합니다. 오류가 있으면 명령과 출력 전문을 Codex에 보내 어느 파일의 어느 줄에서 생겼는지 찾습니다.',
        f'고친 뒤에는 그 기능을 다시 실행하고 검사합니다. 고친 근거는 `{record}`에 짧게 남깁니다.'],
        prompt='구조 검사 출력이 가리키는 파일과 줄을 찾아, `app/features`의 어느 기준에서 생긴 문제인지 설명해 줘. 원자료 · 제공 코드 · 검사 기준은 바꾸지 마. 내가 원인을 확인하면 그 줄만 고쳐 줘.',
        cmd='python run.py check', check='「구조 검사 통과」 줄이 나오는지 봅니다. 구조가 맞아도 판정이 맞는지는 앞의 원문 대조로 판단합니다.',
        recovery=recovery)


def save(key, record, first, rest, what):
    return section('저장하고 다시 확인하기', [
        '**파일 → 모두 저장**을 선택하고 같은 폴더를 닫았다 다시 엽니다. 아래 명령으로 ' + what + ' 다시 확인합니다.',
        f'`{record}` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 짧게 남깁니다. ' + SAVE_USB,
        '**완료 판정** ' + DONE[key] + ' 구조 검사 통과나 실행 성공만으로는 완료가 아닙니다.'],
        cmd=f'python run.py {first}', check='다시 연 파일로 같은 결과가 나오는지 봅니다.',
        followup=rest + [('python run.py check', '구조 검사를 통과하는지 확인합니다. 이어서 할 때는 보관한 같은 폴더를 엽니다.')])


def criteria(L, files):
    key = 'integrated-03-criteria'
    return [
        setup(key, f'`data/model/`에는 제공된 설비 모델(2회차 그래프 구현 실습과 같은 모델) — 설비 7대의 schema.json · graph.json과 설비 대장 — 이 있습니다. '
              f'그 모델에는 조치 절차와 판단 규칙이 아직 없습니다. 원문은 {MANUAL}와 옛 판 · 보충 기준 · 작업 기준이고, 판단 시스템 결정표 내보내기, 작업 이력, 사건 메모, 확인 사례가 함께 있습니다. '
              '`app/features/`의 **판단 표** 셋(`condition_classes.csv` · `relations.csv` · `equipment_links.csv`)은 원문 문장을 SOP 구조의 칸 · 관계 · 설비에 나눠 적는 표이고, 제공 코드가 이 셋으로 `output/sop.json`을 만듭니다.',
              '매뉴얼 원문 문장 · 판단 시스템 결정표 규칙 · 확인 사례 · 냉각 계통 SOP의 개수와, 판단 표의 원문 칸에 쓰는 원문 문장 번호 표가 보입니다.'),
        section('Codex와 자료 파악하기', [
            '조치 기준에는 원문에 있는 것만 담아야 하므로 먼저 자료가 무엇을 말하는지 봅니다. 현행 판 · 옛 판 · 시스템 내보내기 · 작업 기록은 만든 때와 사람이 달라 같은 일도 다르게 적혀 있을 수 있습니다. ' + login(key),
            'Codex에게 파일을 바꾸지 말고, `data/targets.csv`의 냉각 계통 조치마다 그 조치를 말하는 줄을 자료마다 찾아 파일:줄로 짚어 달라고 요청합니다. 번호 · 표기 · 경계 낱말이 자료마다 다른 곳도 물어봅니다. '
            '요청에 파일 이름을 쓸 때는 백틱(`)으로 감쌉니다. 채팅 입력이 밑줄(_)을 서식으로 바꾸기 때문입니다.',
            '짚은 줄을 직접 열어 봅니다. 판단 시스템 결정표의 규칙마다 그 출처 절이 HM-8 매뉴얼 원문에 있는지, 냉각 계통 밖을 다루는 줄이 어느 것인지는 아래 명령의 표로 봅니다.'],
            cmd='python run.py export', check='조치마다 근거 줄을 말할 수 있고, 결정표의 옛 판 번호를 현행 번호와 구별할 수 있으면 이어갑니다. Codex가 파일을 바꾸려 하면 취소하고 자료 설명만 요청합니다.', ai=True),
        section('요구와 기대 판정 정하기', [
            '결과를 견줄 기준부터 정합니다. `app/features/requirements.md`에 목표 · 이 답을 쓰는 사람 · 쓸 판본 · 지킬 조건을 자기 말로 적습니다. ' + L['user'],
            questions(L),
            '사건 네 후보가 조건표에서 유지 · 제외 · 보류 가운데 무엇이 될지 원문과 사건 메모(`data/incident_hyd02_1027.md`)에서 먼저 찾아 `app/features/expected.csv`에 근거 줄과 함께 적습니다. '
            '사건 메모의 값 가운데 조건에 그대로 대어 볼 수 없는 값(빈 칸 · 다른 단위)이 있는지도 내가 정합니다. ' + WORDS + ' ' + HANDS,
            points(L)],
            prompt='내가 작성한 `requirements.md`와 `expected.csv`를 읽고 자료에서 확인한 내용과 맞는지 되짚어 줘. 파일은 바꾸지 말고, 근거 줄이 없거나 원문과 다르게 읽히는 곳만 짚어 줘.',
            cmd='python run.py expected', check='화면의 기대 판정과 근거가 내가 적은 내용인지 봅니다. 이 표가 뒤에서 조건표를 댄 판정과 견줄 기준입니다.', ai=True),
        section('조건 문장을 SOP 구조로 나누기', [
            'SOP(표준 작업 절차)는 사람이 따라 하는 절차를 담습니다. SOP 구조의 칸은 적용 조건(작업 전제 조건) · 금지 조건(금지 사항) · 수행 단계 · 완료 기준(완료 확인 기준) · 승인이고, 아래에서는 적용 · 금지 · 완료 칸이라 부릅니다. '
            '같은 사실도 적용과 금지 가운데 어느 칸에 두느냐에 따라 「쓸 수 있다」와 「쓸 수 없다」로 갈리므로 칸마다 원문 자리를 붙입니다.',
            'Codex에게 먼저 SOP 구조와 조건표에 무엇을 나눠 담을지 계획을 설명하게 합니다. 같은 원문 문장이 SOP의 칸과 조건표의 규칙 둘 다에 걸리면 규칙 칸으로 잇는지 확인한 뒤, 절차마다 칸과 원문 자리를 `app/features/condition_classes.csv`에 채우도록 요청합니다. ' + EDIT,
            '「~일 때만」 「~하지 않는다」 「이내」 문장을 어느 칸에 둘지, 승인 줄이 없는 절차의 승인을 무엇으로 적을지, 다른 절 · 다른 SOP를 가리키는 문장을 어디에 둘지는 내가 원문 줄을 보고 정합니다. 원문 인용과 수행 단계는 제공 코드가 매뉴얼에서 옮깁니다.'],
            prompt='지금 함께 정한 칸 나누기 기준으로 `app/features/condition_classes.csv`를 채워 줘. 원문 칸에는 `data/hm8_manual.md`의 줄 번호(또는 줄.문장)를 쓰고, 승인 줄이 없는 절차는 역할을 만들지 말고 「미확인」으로 시작해 찾아본 결과를 적어 줘. 판단 시스템 결정표에만 있고 원문 근거가 없는 규칙은 아직 넣지 마. 다른 파일은 바꾸지 마.',
            cmd='python run.py classify', check='절차 일곱이 모두 보이고 칸마다 원문 인용과 출처가 붙었는지 봅니다. 「아직 채우지 않은 곳」 칸이 남으면 그 줄을 Codex에 보여 줍니다. 관계와 설비 연결은 다음 두 기능에서 채우며, `output/sop.json`이 생성됩니다.', ai=True),
        section('고장 유형 · 원인 · 조치 잇기', [
            '완화 조치는 증상을 우선 낮추는 조치이고, 근본 조치는 원인을 없애는 조치입니다. 같은 고장 유형이라도 원인에 따라 맞는 근본 조치가 다르므로 관계가 있어야 원인에 맞지 않는 조치를 고르지 않습니다.',
            '매뉴얼의 원인 절과 `data/failuremodes.csv`를 열고, 조치가 특정 원인에만 맞는지와 그 근거 줄, 점검 · 확인만 하는 절차를 근본 조치로 이을 수 있는지 내가 정합니다. 정한 기준으로 `app/features/relations.csv`를 채우도록 요청합니다.'],
            prompt='지금 원문 줄로 확인한 고장 유형 · 원인 · 조치의 연결을 `app/features/relations.csv`에 적어 줘. type은 `data/contract.md`의 셋만 쓰고 원문에 없는 연결은 만들지 마. 점검만 하는 절차는 내가 정한 대로 이어 줘.',
            cmd='python run.py relations', check='「양 끝이 sop.json에 없는 관계」 칸이 없고, 원인마다 이어진 조치를 원문 줄로 말할 수 있는지 봅니다.', ai=True),
        section('적용 범위와 설비 모델 ID 잇기', [
            '제공된 설비 모델의 ID를 그대로 써야 조치 기준이 모델과 이어집니다. 새 ID를 지으면 같은 설비가 두 이름으로 갈라져 판단이 설비를 찾지 못합니다. '
            '내 모델을 쓰는 것은 선택입니다. 쓸 때만 2회차 실습 폴더(`ontology-lab` 또는 `graph-lab`)의 `output/schema.json` · `output/graph.json`을 함께 이 폴더의 `app/features/model/`에 복사하고, ID 짓는 법이 제공 모델과 같은지 먼저 견줍니다. 제공 모델은 보존합니다.',
            '정할 지점 「적용 범위」: 원문에 적용 범위 문장이 없을 때 이 조치 기준을 어느 설비에 걸지 설비 대장과 모델 관계로 내가 정하고, `app/features/decisions.csv`에 한 줄 적습니다. ' + DECIDE,
            '그 선택으로 절차마다 걸 설비 · 구성 요소 · 센서와 걸지 않은 까닭을 `app/features/equipment_links.csv`에 채우도록 요청합니다. 조치에 필요한 구성 요소 · 센서가 모델에 없는 설비가 있는지도 봅니다.'],
            prompt='`decisions.csv`에 내가 적은 적용 범위 선택과 지금 모델에서 확인한 관계를 따라 `app/features/equipment_links.csv`를 채워 줘. 모델에 있는 ID만 쓰고, 걸지 않은 대상은 까닭을 적어 줘. 내가 정하지 않은 설비가 남으면 먼저 물어봐.',
            cmd='python run.py links', check='「모델에서 찾지 못한 ID」 칸이 없거나 그 까닭이 걸지 않은 대상에 적혀 있는지, 설비마다 걸었음 · 뺐음을 대장 · 모델 줄로 말할 수 있는지 봅니다.', ai=True),
        section('조건표 규칙 만들기', [
            TABLE_TERM,
            '원문의 경고 · 감점 · 제외 조건을 Codex와 규칙 묶음 하나씩 `app/features/condition_table.csv`에 계약 모양(`data/contract.md` 「조건표」)으로 옮기고, `condition_classes.csv`의 규칙 칸에 그 rule_id를 적게 합니다. '
            '여러 조건을 한 묶음(AND)으로 둘지, 원문끼리 경계 낱말이 다른 곳을 무엇으로 정할지, 규칙을 어느 조치에 걸지는 원문 낱말로 내가 정합니다.'],
            prompt='지금 원문 낱말로 정한 경계와 묶음 기준으로 `condition_table.csv`에 경고 · 감점 · 제외 규칙을 옮기고, `condition_classes.csv`의 해당 줄 규칙 칸에 rule_id를 적어 줘. 판단 시스템 결정표에만 있는 규칙은 아직 넣지 마. source_section은 `contract.md`의 꼴을 지켜 줘.',
            cmd='python run.py rules', check='규칙마다 출처 칸의 원문이 보이고, 「기대 판정 ↔ 조건표를 댄 판정」이 같거나 다른 줄의 까닭을 원문 줄로 말할 수 있는지 봅니다. 결과에 맞추려고 기대를 바꾸지 않습니다.', ai=True),
        section('출처가 확인되지 않는 규칙 정하기', [
            SOURCE + ' ' + UNKNOWN,
            '먼저 아래 명령을 한 번 실행해 지금 판정 개수를 봐 둡니다. 정할 지점 「출처가 확인되지 않는 기준」: 결정표에 있는데 HM-8 매뉴얼 원문에서 근거 문장을 찾을 수 없는 규칙마다 옮김 · 고침(대상을 바꿈) · 뺌 가운데 무엇으로 할지 '
            '현행 판 · 옛 판 · 작업 기준을 열어 내가 정하고, 규칙마다 `decisions.csv`에 한 줄씩 적습니다. ' + DECIDE,
            '결정이 바꿀 확인 사례 하나(`data/check_cases.csv`)를 골라, 내가 택한 선택으로 그 사례의 기대 판정을 원천 줄에서 먼저 구해 `expected.csv`에 더합니다. 그 뒤 선택을 `condition_table.csv` · `condition_classes.csv`에 반영하도록 요청하고 같은 명령을 다시 실행합니다.'],
            prompt='`decisions.csv`에 내가 규칙마다 적은 선택(옮김 · 고침 · 뺌)대로 `condition_table.csv`와 `condition_classes.csv`에 반영해 줘. 원문에서 찾지 못한 근거는 출처 칸에 찾지 못했다고 적고, 이름만 보고 잇지 마. 내가 정하지 않은 규칙이 남으면 먼저 물어봐.',
            cmd='python run.py provenance', check='결정표 규칙 표의 「내_조건표」 칸이 내 결정과 같고, 판정 개수 옆 「직전 실행」 값과의 차이를 내 결정으로 설명할 수 있는지, 새로 더한 확인 사례의 기대와 판정이 같은지 봅니다.', ai=True),
        structure_check('app/features/requirements.md', [('python run.py classify', '고친 판단 표로 SOP 구조가 다시 생성됐는지 봅니다.'), ('python run.py check', '구조 오류가 사라졌는지 확인합니다.')]),
        save(key, 'app/features/requirements.md', 'classify', [('python run.py provenance', 'F5를 눌러 판정과 결정표 대조가 유지되는지 봅니다.')], 'SOP 구조와 판정을'),
    ]


def conditions(L, files):
    key = 'practical-02-conditions'
    return [
        setup(key, f'{MANUAL}가 이번에 쓰는 냉각 계통 SOP이고, 보충 기준 · 작업 기준, 판단 시스템 결정표 내보내기, 이번 경보에서 검토하는 후보 넷, 사건 메모, 확인 사례가 함께 있습니다.',
              '매뉴얼 원문 문장 · 결정표 규칙 · 확인 사례 · 후보의 개수와 원문 문장 표가 보입니다.'),
        section('Codex와 자료 파악하기', [
            '조건표에는 원문에 있는 조건만 담아야 합니다. 원문 · 시스템 내보내기 · 기록은 만든 때와 사람이 달라 같은 조건도 다르게 적혀 있을 수 있으므로 자료마다 어느 판 · 시점인지 먼저 압니다. ' + login(key),
            'Codex에게 파일을 바꾸지 말고, HM-8 매뉴얼 원문의 조건 문장 · 판단 시스템 결정표의 줄 · 사건 메모 · 확인 사례가 각각 무엇을 담는지 파일:줄로 짚어 달라고 합니다. 확인 사례의 값이 비는 까닭이 몇 가지인지도 묻습니다. '
            '요청에 파일 이름을 쓸 때는 백틱(`)으로 감쌉니다. 짚은 줄을 직접 열어 봅니다.'],
            cmd='python run.py export', check='자료마다 판 · 시점과 조건이 오는 곳을 말할 수 있고, 결정표 규칙마다 「출처_절」이 원문에 있는지 보이면 이어갑니다.', ai=True),
        section('요구와 기대 판정 정하기', [
            '`app/features/judgement_record.md`에 목표 · 쓰는 사람 · 지킬 조건을 적습니다. ' + L['user'] + ' ' + questions(L),
            '사건과 확인 사례 두세 개 — 경계값과 같은 사례(같은 값이 없으면 없다고 적고 가장 가까운 사례로 경계를 봅니다), 입력이 빠졌는데 제외 사유도 있는 사례 — 의 네 후보가 유지 · 제외 · 보류 가운데 무엇이 될지 원문에서 먼저 찾아 '
            '`app/features/expected.csv`에 근거 줄과 함께 적습니다. AI에게는 판정을 빼고 위치만 찾게 합니다. ' + WORDS + ' ' + HANDS,
            points(L)],
            prompt='내가 작성한 `judgement_record.md`와 `expected.csv`를 읽고 자료에서 확인한 내용과 맞는지 되짚어 줘. 파일은 바꾸지 말고, 근거 줄이 없거나 원문과 다르게 읽히는 곳만 짚어 줘.',
            cmd='python run.py expected', check='기대 판정마다 근거 파일:줄이 있고 화면에 내가 적은 값이 보이는지 봅니다.', ai=True),
        section('조건표 규칙 만들기', [
            TABLE_TERM,
            'Codex에게 먼저 조건표에 넣을 규칙과 옮길 순서, 옮기지 않을 원문 조건과 그 까닭을 계획으로 설명하게 하고 검토합니다. 그 뒤 원문의 경고 · 감점 · 제외 조건을 규칙 묶음 하나씩 `app/features/condition_table.csv`에 계약 모양(`data/contract.md` 「조건표」)으로 옮기도록 요청합니다. '
            '여러 조건을 한 묶음(AND)으로 둘지, 원문끼리 경계 낱말이 다른 곳을 무엇으로 정할지는 원문 낱말로 내가 정합니다. ' + EDIT],
            prompt='지금 검토한 계획과 원문 낱말로 정한 경계대로 `condition_table.csv`에 경고 · 감점 · 제외 규칙을 묶음 하나씩 옮겨 줘. 판단 시스템 결정표에만 있는 규칙은 아직 넣지 말고, 원문에 없는 기준값을 더하지 마. source_section은 `contract.md`의 꼴을 지켜 줘.',
            cmd='python run.py rules', check='「기대 판정 ↔ 조건표를 댄 판정」이 같거나 다른 줄의 까닭을 원문으로 말할 수 있는지 봅니다. 한 후보에 경고와 감점이 함께 맞은 줄, 제외와 미확인이 함께 있는 줄, 값이 비어 있어도 그 후보에는 해당 규칙이 걸리지 않는 줄(적용 대상 밖)이 보이는지도 봅니다.', ai=True),
        section('출처가 확인되지 않는 규칙 정하기', [
            SOURCE + ' ' + UNKNOWN,
            '먼저 아래 명령을 한 번 실행해 지금 판정 개수를 봐 둡니다. 정할 지점 「출처가 확인되지 않는 기준」: 결정표에 있는데 HM-8 매뉴얼 원문에서 근거 문장을 찾을 수 없는 규칙마다 옮김 · 고침 · 뺌 가운데 무엇으로 할지 원문과 작업 기준을 열어 정하고, '
            '규칙마다 `decisions.csv`에 한 줄씩 적습니다. ' + DECIDE + ' 그 선택을 `condition_table.csv`에 반영하도록 요청하고 같은 명령을 다시 실행합니다.'],
            prompt='`decisions.csv`에 내가 규칙마다 적은 선택(옮김 · 고침 · 뺌)대로 `condition_table.csv`에 반영해 줘. 원문에서 찾지 못한 근거는 출처 칸에 찾지 못했다고 적고, 이름만 보고 잇지 마. 내가 정하지 않은 규칙이 남으면 먼저 물어봐.',
            cmd='python run.py provenance', check='판정 개수 옆 「직전 실행」 값과의 차이를 내 결정으로 설명할 수 있는지(바뀌지 않았으면 그 까닭과 뺀 규칙이 바꿨을 사례), 조건표의 출처 칸이 원문으로 돌아가거나 찾지 못했다고 적혀 있는지 봅니다.', ai=True),
        section('남은 후보와 실행 승인 적기', [
            '판단 규칙이 후보를 남겼다는 것은 쓸 수 있다는 뜻일 뿐 실행해도 된다는 허락이 아닙니다. 실행은 정해진 사람이 한 번 승인한 뒤에 하므로 누가 승인하는지를 원문에서 따로 확인합니다.',
            '후보마다 승인 역할과 원문 승인 줄을 `app/features/approvals.csv`에 적습니다. 정할 지점 「승인 역할」: 원문의 승인 줄이 하나로 읽히지 않는 후보를 무엇으로 적을지 정해 `decisions.csv`에 적습니다. 승인 줄이 없으면 역할을 만들지 않습니다.'],
            prompt='지금 원문에서 확인한 승인 줄과 `decisions.csv`의 승인 역할 선택대로 `approvals.csv`에 후보마다 한 줄을 적어 줘. 원문 칸은 `data/hm8_manual.md`의 줄 번호로 쓰고, 승인 줄을 찾지 못한 후보는 「미확인」으로 시작해 찾아본 결과를 적어 줘.',
            cmd='python run.py approvals', check='남은 후보(보류 표시 포함)마다 승인 역할과 원문 승인 줄이 보이고, 후보가 남은 것과 실행 승인의 차이를 내 말로 말할 수 있는지 봅니다.', ai=True),
        structure_check('app/features/judgement_record.md', [('python run.py rules', '고친 조건표로 판정이 다시 나오는지 봅니다.'), ('python run.py check', '구조 오류가 사라졌는지 확인합니다.')]),
        save(key, 'app/features/judgement_record.md', 'rules', [('python run.py approvals', 'F5를 눌러 남은 후보와 승인이 유지되는지 봅니다.')], '조건표 판정을'),
    ]


def alarm_count(files):
    return sum(1 for r in csv.DictReader(io.StringIO(files['경보_목록.csv'])) if r['구분'] == 'RAISE' and r['판정_요청_시각'])


def judge_common(key, L, files):
    review = key == 'practical-03-review'
    n = alarm_count(files)
    sop_line = ('SOP 구조(sop.json)는 HM-8 매뉴얼 원문의 조치 절차마다 적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인 역할과 그 출처를 담은 파일이고, 이 실습에서는 승인 역할과 확인할 조건을 읽는 데 씁니다. ' if review else '')
    source = ('조치 조건표 실습 폴더(`condition-table-lab`)의 `app/features/condition_table.csv`' if review else
              '조치 기준 만들기 실습 폴더(`action-criteria-lab`)의 `app/features/condition_table.csv`와 `output/sop.json`')
    mine = ('`data/criteria/`에는 ' + ('조치 조건표' if review else '조치 기준 만들기') + '와 같은 꼴로 검증해 제공하는 조건표(condition_table.csv)와 SOP 구조(sop.json)가 있습니다. ' + sop_line
            + f'내 결과를 쓰는 것은 선택입니다. 쓸 때만 {source}을 이 폴더의 `app/features/criteria/`에 같은 이름으로 복사하고 열 이름 · ID가 `data/contract.md`와 같은지 먼저 견줍니다. '
            '제공 입력은 그대로 둡니다. 원천 기록 네 개(경보 · PLC 상태 · 팬 카운터 · 예측)와 수집 설명, 오더 현황, 비교 산식(`data/metrics/`)은 `data/`에 있습니다.')
    steps = [
        setup(key, mine, '경보마다 판정 요청 직전 원천 기록(PLC 마지막 수신 · 카운터 마지막 기록 · 예측 행) 표가 보입니다.'),
        section('Codex와 원천 기록 파악하기', [
            '판단 입력은 원천 네 곳에 흩어져 있고, 원천마다 기록 주기 · 단위 · 시각 표기와 값이 비는 까닭이 다릅니다. 시각 맞추기 · 단위 · 하트비트 · 유효 시간 같은 일반 처리는 제공 코드가 `data/collection_notes.md`대로 하고, '
            '끊긴 기록을 어떻게 볼지와 어느 후보를 견줄지만 내가 정합니다. ' + login(key),
            'Codex에게 파일을 바꾸지 말고 원천 네 개와 조건표 · 계약이 각각 무엇을 어떤 모양으로 담는지 파일:줄로 짚어 달라고 합니다. 값이 비는 까닭을 칸이 빔 · 와야 할 기록이 오지 않음 · 유효 시간이 지남으로 나눠 묻습니다. '
            '이어서 판정 · 순위는 빼고, 카운터 기록이 끊긴 경보 · 모든 후보가 제외될 것 같은 경보 · 예측 값이 조건표 기준값과 같거나 가장 가까운 경보의 위치(경보 ID와 원천 줄)만 목록으로 달라고 합니다. 요청에 파일 이름을 쓸 때는 백틱(`)으로 감쌉니다.',
            '앞 화면에서 판정 요청 직전 기록이 그 원천의 주기보다 오래된 경보 하나를 골라 원천 줄을 직접 엽니다.'],
            check='원천마다 기록 주기 · 단위와 값이 비는 까닭을 원천 줄로 말할 수 있고, 다음 단계에서 기대를 적을 경보의 위치 목록이 있으면 이어갑니다. Codex가 파일을 바꾸려 하면 취소하고 자료 설명만 요청합니다.', ai=True),
        section('기대 판정 먼저 적기', [
            '실행하기 전에 기대를 적어 두어야 결과가 다를 때 판단 입력 · 판정 · 기대 가운데 어디가 틀렸는지 근거로 가릴 수 있습니다. AI가 낸 결과를 기대로 옮기면 틀린 결과도 맞아 보입니다.',
            '`app/features/review.md`에 목표 · 쓰는 사람 · 지킬 조건을 적습니다. ' + L['user'] + ' ' + questions(L),
            '사건의 네 후보와, 앞 단계 목록의 카운터 기록이 끊긴 경보 하나 · 모든 후보가 제외될 것 같은 경보 하나 · 경계 경보 하나의 기대 판정을 원천 줄 · 조건표 · 원문으로 손으로 구해 '
            '`app/features/expected.csv`에 근거 줄과 함께 적고, review.md에 「기대 칸을 쓴 시각」을 적습니다. 카운터 기록이 끊긴 경보의 기대는 다음 단계에서 정할 「빈 값의 뜻」에 달려 있으므로, 내가 택할 뜻으로 구하고 그 뜻을 review.md에 한 줄 남깁니다. '
            + WORDS + ' ' + HANDS,
            points(L)],
            prompt='내가 작성한 `review.md`와 `expected.csv`를 읽고 원천 기록과 조건표에서 확인한 내용과 맞는지 되짚어 줘. 파일은 바꾸지 말고, 근거 줄이 없거나 원천과 다르게 읽히는 곳만 짚어 줘.',
            cmd='python run.py expected', check='기대 판정마다 근거 파일:줄이 있고 화면에 내가 적은 값이 보이는지 봅니다. 「기대 칸을 쓴 시각」이 다음 단계의 첫 실행보다 앞입니다.', ai=True),
        section('끊긴 카운터 기록의 값 정하기', [
            '값이 없는 입력은 0이나 앞 값으로 채우지 않고 까닭과 함께 남겨야 규칙이 무엇을 근거로 판정했는지 따라갈 수 있습니다. ' + UNKNOWN,
            'Codex에게 제공 코드(`app/utils/judge_tools.py`)가 판단 입력 → 판정 → 비교 → 결과 쓰기 가운데 어디서 `app/features/gap_rule.py`의 함수를 부르는지 먼저 짚게 합니다. '
            '정할 지점 「빈 값의 뜻」: 카운터 기록이 판정 요청 전에 끊긴 경보에서 끊긴 구간을 이을지, 잇는다면 원천의 무엇을 근거로 할지 `data/collection_notes.md`의 팬 카운터 절과 원천 줄로 내가 정하고 `decisions.csv`에 적습니다. ' + DECIDE,
            '그 선택대로 gap_rule.py의 함수를 채우도록 요청합니다. 받는 값과 돌려줄 값의 꼴은 파일 머리에 있습니다. ' + EDIT],
            prompt='`decisions.csv`에 내가 적은 빈 값의 뜻 선택과 지금 원천 줄로 확인한 근거대로 `app/features/gap_rule.py`의 `fan_hours_when_gap`만 채워 줘. 파일 머리의 꼴을 지키고, 판정 요청 시각 뒤의 기록은 쓰지 마. 까닭 없이 0이나 앞 값으로 채우지 마.',
            cmd='python run.py inputs', check='「카운터 기록이 끊긴 경보」 표가 내 결정대로이고 값이 없으면 까닭이 붙었는지, 「기대 판정 ↔ 판정」이 같거나 다른 줄의 까닭을 원천 줄로 말할 수 있는지 봅니다.', ai=True),
        section('견줄 후보 정하기', [
            '후보마다 비용 · 생산 · 품질 · 에너지처럼 서로 다른 성과가 함께 움직이므로, 한 가지 값으로 견주려면 주어진 산식(`data/metrics/metric_definitions.md`)이 필요합니다. **비교값**은 네 손실과 감점을 더한 값이고 작을수록 유리합니다.',
            '정할 지점 「쓰는 사람에 따라 갈리는 답」은 경고가 붙은 유지 후보를 비교 산식으로 견줄지입니다. HM-8 매뉴얼 원문 HM-8.6과 작업 기준 4절로 내가 정하고 `decisions.csv`에 적습니다. ' + DECIDE,
            '그 선택대로 `app/features/compare_rule.py`의 함수를 채우도록 요청합니다. 산식은 바꾸지 않고, 견주지 않는 후보는 까닭을 남깁니다.'],
            prompt='`decisions.csv`에 내가 적은 「쓰는 사람에 따라 갈리는 답」 선택대로 `app/features/compare_rule.py`의 `choose_compared`만 채워 줘. 파일 머리의 꼴을 지키고 비교 산식과 조건표는 바꾸지 마. 견주지 않는 후보에는 까닭 글을 남겨 줘.',
            cmd='python run.py compare', check='경보마다 순위와 견주지 않은 후보 · 까닭이 보이고, `metric_definitions.md` 손계산 예의 네 손실이 프로그램 값과 같은지 봅니다. 사건의 한 후보는 손으로 다시 계산해 견줍니다.', ai=True),
        section('비교 기준 문장과 ' + ('검토 결과' if review else '결과') + ' 쓰기', [
            '비교값은 후보를 견주는 계산이고 포털의 **정책 점수**(`data/metrics/metric_definitions.md` 「포털의 성과 지표 점수」 절)와 다른 값입니다. 1위도 실행 허가가 아닙니다. 실행은 정해진 사람이 한 번 승인한 뒤에 합니다.',
            '정할 지점 「비교 기준 문장」: `decisions.csv`에 지점 칸이 「비교 기준 문장」으로 시작하는 새 줄을 더하고, 고른_것 칸에 이 비교값이 무엇을 견주는 값인지, 정책 점수 · 실행 승인과 어떻게 다른지를 내 말로 적습니다. 근거 칸에는 그 절의 파일:줄을 적습니다.'],
            prompt='`decisions.csv`의 「비교 기준 문장」 줄을 `data/metrics/metric_definitions.md`의 「포털의 성과 지표 점수」 절과 견주어, 맞지 않거나 1위를 실행 승인처럼 읽히게 쓴 곳만 짚어 줘. 파일은 바꾸지 마.',
            cmd='python run.py ' + ('compare' if review else 'write'),
            check=('`output/action_review.json` · `output/action_review.md`를 썼다는 줄이 보이고, 결과의 비교 기준 문장이 내가 적은 문장인지 봅니다.' if review else
                   '`output/judgement.json`을 썼다는 줄과 내 비교 기준 문장, 기대를 적은 경보의 선택 이유 · 추가로 확인할 사항이 보이는지 봅니다.'), ai=True),
        section('검토 결과로 사례 검증하기' if review else '사례로 결과 검증하기', [
            f'사건 한 건이 맞아도 다른 경보에서 틀릴 수 있고, 경보 {n}건마다 후보가 넷이라 손으로 다 맞출 수 없습니다. 결과가 갈리는 종류를 지난 경보 전체에서 골라 대조해야 기능을 다른 경보에도 쓸 수 있습니다.',
            ('`output/action_review.md`의 사건 절(화면의 「action_review.md — 사건 경보 ID 절」 표)만 읽고 후보마다 판정 · 까닭 · 승인 역할과 먼저 확인할 값을 말해 봅니다. ' if review else '')
            + '앞에서 적은 기대와 대조를 견주고, 「후보마다 판정 내용」 표를 걸러 다음 종류의 사례를 더 고르면 원천 줄로 기대를 먼저 적어 더한 뒤 견줍니다: '
            + ('조건표 숫자 기준값마다 같은 값과 바로 위 · 아래(단위가 다른 원천 포함), 확인된 제외 사유와 입력 누락이 한 후보에 겹친 경우, 모든 후보가 제외된 경보, 값이 비는 까닭이 서로 다른 경보(그 값이 필요한 규칙에만 영향이 가는지), 정할 지점의 선택에 따라 검토 의견이 바뀌는 경보.'
               if review else
               '규칙이 하나도 맞지 않는 후보(정상), 조건표 숫자 기준값마다(예측 유온 · 팬 100 % 연속 시간 24 h) 같은 값과 바로 위 · 아래(단위가 다른 원천 포함), 경고 · 감점 · 제외가 한 후보에 함께 맞는 경우(감점이 규칙마다 한 번인지), '
               '모든 후보가 제외된 경보, 값이 비는 까닭이 서로 다른 경보(그 값이 필요한 규칙에만 영향이 가는지), 정할 지점의 선택에 따라 판단 입력 · 순위가 바뀌는 경보.')
            + ' 다른 줄의 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 `app/features/review.md`의 표에 적습니다.'],
            prompt='지금 결과 화면에서 기대와 다른 줄 하나의 원천 줄 · 조건표 규칙 · 실제 판정을 비교해 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 설명해 줘. 먼저 파일은 바꾸지 마. 원인을 확인하면 해당 함수나 기대 줄만 고치도록 요청할게.',
            cmd='python run.py cases', check='사례 종류마다 원천 줄을 연 경보가 하나 이상 있고, 다른 줄마다 원인이 review.md에 있는지 봅니다. 결과에 맞추려고 기대를 바꾸지 않습니다.', ai=True),
        structure_check('app/features/review.md', [('python run.py compare', '고친 함수로 비교가 다시 나오는지 봅니다.'), ('python run.py check', '구조 오류가 사라졌는지 확인합니다.')]),
        save(key, 'app/features/review.md', 'compare' if review else 'write', [('python run.py cases', 'F5를 눌러 사례 대조가 유지되는지 봅니다.')], '판정과 결과 파일을'),
    ]
    return steps


def steps(key, L, files):
    if key == 'integrated-03-criteria':
        return criteria(L, files)
    if key == 'practical-02-conditions':
        return conditions(L, files)
    return judge_common(key, L, files)


def render(title, key, L, files, steps_):
    lead = PURPOSE[key] + ' ' + BJ.incident_line(files) + ' ' + F.STAGE_LINE.format(what=STAGE[key])
    return F.step_page(title, F.inline(lead), [(s['name'], s['body']) for s in steps_])
