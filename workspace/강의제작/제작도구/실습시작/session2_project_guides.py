"""통합02 가이드 원고. 지금 필요한 이유·행동·확인만 기능 순서로 제공한다."""
import lab_frame as F


def paragraph(text):
    return '<p>' + F.inline(text) + '</p>'


def section(name, text, *, prompt=None, cmd=None, check='', ai=False, extra='', recovery=None):
    body = ''.join(paragraph(t) for t in text)
    if prompt:
        body += F.answer_html(F.A('막히면 지금까지 확인한 내용에 이어서 요청합니다.', F.ask_ai(prompt)))
    body += extra
    if cmd:
        body += F.command_block(cmd)
    if check:
        body += '<p class="check">' + F.inline(check) + '</p>'
    if recovery:
        body += '<details><summary>고친 뒤 다시 확인</summary>' + F.command_block(recovery) + '</details>'
    return dict(name=name, body=body, ai=ai)


ONTOLOGY_PURPOSE = '포털 지식 지도에서 살펴본 연결을 직접 설계합니다. 원자료로 온톨로지를 만들어 설비별 센서와 공용 부품을 찾습니다.'
GRAPH_PURPOSE = '설비·센서·부품의 온톨로지를 별도 랩 DB에 구현합니다. 조회와 부분 수정 결과를 원자료와 대조합니다.'


def setup(folder, first=True):
    text = [f'클래스룸의 2회차 실습 자료에서 ZIP을 받아 **압축 풀기**를 선택합니다. VS Code의 **파일 → 폴더 열기**에서 `{folder}` 폴더를 엽니다. 함께 풀린 가이드는 브라우저로 엽니다.',
            '신뢰 여부를 물으면 **예, 작성자를 신뢰합니다**(Yes, I trust the authors)를 선택합니다. 제한 모드에서는 Codex를 사용할 수 없습니다.']
    if first:
        text += ['왼쪽 탐색기는 파일을 고르는 곳, 가운데 편집기는 내용을 보는 곳입니다. `README.md`를 열어 폴더 역할을 봅니다. `data/`는 자료, `app/features/`는 AI와 구현할 기능입니다. 화면 표시와 공통 처리는 제공됩니다.',
                 '`AGENTS.md`는 Codex가 지킬 공통 원칙을 담은 헌법 파일입니다. 코드를 직접 외울 필요는 없습니다. 무엇을 만들지 설명하고 결과를 확인하는 일을 맡습니다.']
    else:
        text += ['`data/model/`에는 바로 쓸 수 있는 모델이 있습니다. 자기 모델이 없어도 이 폴더 하나로 시작할 수 있습니다.']
    text += ['**터미널 → 새 터미널**을 엽니다. 오타를 줄이도록 명령 블록의 **복사**를 눌러 붙여 넣고 Enter를 누릅니다.']
    return section('폴더 열고 자료 확인하기', text, cmd='python run.py',
                   check='원자료 파일과 행 수가 보이는지 봅니다. 결과는 `output/result.html`에 저장됩니다. 브라우저가 열리지 않으면 탐색기에서 이 파일을 찾아 엽니다. 이후에는 명령을 실행한 뒤 열린 화면에서 F5를 누릅니다.')


def ontology():
    return [setup('ontology-lab'),
        section('Codex와 자료 파악하기', [
            '같은 이름이 같은 대상을 뜻하는지 확인해야 센서와 부품이 잘못 연결되지 않습니다. Codex 확장 아이콘을 눌러 채팅을 열고 계정에 로그인합니다. 계정이 없거나 구현 중 막히면 클래스룸에서 실습 폴더와 따로 받는 완성본 ZIP(`ontology-lab-completed.zip`)으로 결과를 실행해 볼 수 있습니다.',
            '`data/equipment.csv`에서 설비 하나를 고릅니다. 파일을 바꾸지 말고 그 설비의 구성 요소·센서·부품이 어느 자료에 있는지 파일과 줄 번호로 짚어 달라고 요청합니다. 이름이 다르거나 빈칸인 곳도 물어봅니다.',
            '답에 나온 줄을 직접 열어 봅니다. 연결의 출발 그림은 `data/relationships.json`, 현장 표기의 맥락은 `data/field_notes.md`에서 확인합니다.'],
            check='어떤 자료로 설비별 센서와 공용 부품을 찾을지 말할 수 있으면 이어갑니다. Codex가 파일을 바꾸려 하면 취소하고 자료 설명만 요청합니다.', ai=True),
        section('질문과 판단 기준 정하기', [
            '만들 모델을 확인할 기준부터 정합니다. `app/features/requirements.md`에 답을 쓸 사람, 기준일, 아래 세 질문을 자기 말로 짧게 적습니다.',
            '① 설비의 구성 요소마다 어떤 센서가 붙는가? ② 같은 물리량을 재는 센서의 단위·정상값·한계는 무엇인가? ③ 부품을 어느 설비가 함께 쓰며, 다른 품번 표기로 물어도 찾을 수 있는가?',
            '방금 찾은 자료 중 이 질문에 쓸 자료와 지킬 조건도 적습니다. 공급·입고 판단은 이번 범위에서 제외하고, 근거 없는 값과 연결을 만들지 않는 조건을 자기 말로 남깁니다.',
            '`app/features/expected.csv`에 원자료에서 찾은 답과 근거 줄을 적습니다. 질문 1은 고른 설비의 구성 요소 셋, 질문 2는 물리량 한 묶음, 질문 3은 공용 부품·다른 표기·없는 품번을 하나씩 확인합니다. 열의 뜻은 파일 첫 줄에 있습니다.',
            '같은 제조사 품번의 사내 품번들을 한 물품으로 볼지, 품번이 없거나 품명만 있는 행을 예비품 목록으로 연결할지 정합니다. 답을 쓸 사람과 원자료를 근거로 선택하고 `app/features/decisions.csv`에 적습니다. AI의 추천은 선택 근거가 되지 않습니다.'],
            prompt='내가 작성한 requirements.md, expected.csv, decisions.csv를 읽고 자료에서 확인한 내용과 맞는지 되짚어 줘. 파일은 바꾸지 말고, 서로 다른 뜻으로 읽히거나 근거가 없는 곳만 짚어 줘. 내가 아직 선택하지 않은 판단은 먼저 물어봐.',
            cmd='python run.py expected', check='화면의 기대 답과 근거가 내가 적은 내용인지 봅니다. 이 표는 구현 결과와 견줄 기준입니다.', ai=True),
        section('식별자와 관계 방향 정하기', [
            '이름이 같아도 다른 설비의 센서는 구분해야 합니다. Codex에게 자료의 어떤 열로 대상을 구별하고 관계를 어느 방향으로 연결할지 계획을 설명하게 합니다.',
            '그 계획이 세 질문에 답할 수 있는지 검토한 뒤 `app/features/design.csv`와 `relations.csv`에 반영하도록 요청합니다. 식별자에 쓸 열은 `{열 이름}`으로 적습니다.'],
            prompt='지금 검토한 식별 기준과 관계 방향을 app/features/design.csv와 relations.csv에 반영해 줘. 같은 이름의 다른 대상이 합쳐지지 않는지 원자료 열로 확인해 줘. 아직 합의하지 않은 기준은 구현 전에 물어봐. 다른 기능은 만들지 마.',
            cmd='python run.py design', check='겹친 식별자가 같은 대상의 중복 행인지 원문에서 확인합니다. 다른 대상이 섞였다면 해당 행을 들어 식별 기준을 고칩니다.', ai=True),
        section('같은 장치의 이름 정리하기', [
            '표기가 다른 같은 장치를 하나로 찾아야 센서와 부품을 연결할 수 있습니다. Codex와 모델·계통·붙은 센서·교체 부품을 비교해 같은 장치로 볼 기준을 정합니다.',
            '기준을 `app/features/name_rules.py`에 구현하도록 요청합니다. 중복·옛 코드·철거 행은 `row_rules.csv`, 기준만으로 묶이지 않는 이름은 `name_overrides.csv`에 근거와 함께 남깁니다.'],
            prompt='지금 확인한 같은 장치의 기준으로 name_rules.py의 두 함수를 구현해 줘. 검토한 중복·옛 기록의 처리는 row_rules.csv에 반영하고, 규칙으로 해결되지 않는 이름만 name_overrides.csv에 남겨 줘. data와 제공 코드는 보존하고 판단이 남으면 먼저 물어봐.',
            cmd='python run.py names', check='묶음에 다른 장치가 섞이지 않았는지, 묶이지 않은 이름을 그대로 둘지 봅니다. expected.csv의 질문 1 항목을 내가 정한 구성 요소 이름에 맞춥니다.', ai=True),
        section('같은 물리량의 센서 모으기', [
            '태그가 달라도 같은 물리량을 재는 센서를 모아야 설비 사이를 비교할 수 있습니다. `data/sensors.csv`와 현장 메모에서 계장태그·재는것·수집방식·비고를 함께 확인합니다.',
            '같은 물리량으로 볼 기준과 실측·계산값·설정값을 구분할 기준을 Codex와 정해 `app/features/quantity_rules.py`에 구현합니다. 규칙과 다르게 둘 항목만 `quantity_overrides.csv`에 적습니다.'],
            prompt='지금 원자료에서 확인한 물리량과 종류 구분 기준을 quantity_rules.py의 세 함수에 구현해 줘. 같은 태그라도 다른 회로를 재는 항목이 섞이지 않는지 확인하고, 합의한 예외만 quantity_overrides.csv에 적어 줘.',
            cmd='python run.py quantities', check='내가 기대한 센서 묶음에 다른 물리량이 섞이지 않았는지 봅니다. expected.csv 질문 2의 물을 값을 내가 정한 물리량 이름에 맞춥니다.', ai=True),
        section('단위와 빈칸 처리하기', [
            '단위가 다른 숫자를 그대로 비교하지 않도록 기준 단위를 정합니다. 빈 단위의 근거가 되는 다른 행도 찾아봅니다. 정상값·한계가 없는 경우는 0과 구분합니다.',
            '확인한 기준을 `app/features/unit_rules.py`에 구현하도록 요청합니다. 환산 계산은 제공 코드가 합니다. 규칙 밖의 단위만 `unit_overrides.csv`에 적습니다.'],
            prompt='지금 정한 기준 단위와 빈 단위 처리 방식을 unit_rules.py의 두 함수에 구현해 줘. 근거가 없는 단위를 추측하거나 빈 정상값·한계를 0으로 만들지 마. 환산 계산은 제공 코드를 사용해 줘.',
            cmd='python run.py units', check='원래 단위와 바뀐 값이 원자료에 맞는지, 빈칸이 근거 또는 미확인으로 남는지 봅니다.', ai=True),
        section('공용 부품 연결하기', [
            '한 부품을 쓰는 설비를 모으려면 다른 품번 표기와 빈칸을 어떻게 연결할지 정해야 합니다. `data/spare_parts.csv`와 `part_aliases.csv`를 열고 내가 기록한 선택을 다시 확인합니다.',
            '`app/features/part_rules.py`에 그 선택을 구현하도록 요청합니다. 일반적인 품번 읽기와 모델 파일 생성은 제공 코드가 맡습니다.'],
            prompt='decisions.csv에 내가 적은 선택과 지금 확인한 품번 근거를 따라 part_rules.py의 두 함수를 구현해 줘. 품번이 명시되지 않은 행의 연결 여부와 같은 제조사 품번의 묶음 여부를 내 선택대로 처리해 줘. 미결인 선택을 대신 정하지 마.',
            cmd='python run.py parts', check='부품별 사용 설비, 연결하지 않은 행, 같은 규격의 처리 결과를 선택 근거와 견줍니다. `output/schema.json`과 `graph.json`이 생성됩니다.', ai=True),
        section('질문으로 결과 검증하기', [
            '처음 적은 기대 답과 모델에 물은 답을 비교합니다. 다른 설비와 없는 품번도 확인해 처음 고른 사례에서만 맞는 규칙인지 살펴봅니다.',
            '다른 줄이 있으면 입력·기대 답·실제 결과를 Codex에 함께 보여 줍니다. 원자료로 원인을 확인한 뒤 해당 기능만 고칩니다. 고쳤을 때는 `python run.py parts`로 모델을 다시 만든 뒤 아래 조회를 실행합니다.'],
            prompt='지금 결과에서 다른 줄 하나의 입력, expected.csv의 근거, 실제 답을 비교해 원인을 설명해 줘. 먼저 파일은 바꾸지 마. 원인을 확인하면 해당 판단 함수나 기준 표만 고치도록 요청할게.',
            cmd='python run.py query', check='답이 맞거나 차이를 원자료로 설명할 수 있어야 합니다. 결과에 맞추려고 기대 답을 바꾸지 않습니다. 고친 근거는 requirements.md에 짧게 남깁니다.', ai=True,
            recovery='python run.py parts\npython run.py query'),
        section('구조 확인하기', [
            '답의 의미를 확인했으므로 식별자 중복과 잘못된 연결도 검사합니다. 오류가 있으면 명령과 출력 전문을 Codex에 보내 어느 구현에서 생겼는지 찾습니다.',
            '기준이나 기능을 고쳤다면 `python run.py parts`로 모델을 다시 만들고 아래 검사를 실행합니다. 그 뒤 `python run.py query`로 질문의 답도 달라졌는지 봅니다.'],
            prompt='구조 검사 출력이 가리키는 대상과 관계를 찾아, app/features의 어떤 기준에서 생긴 문제인지 설명해 줘. 원자료와 검사 기준은 바꾸지 마. 내가 원인을 확인하면 필요한 부분만 고쳐 줘.',
            cmd='python run.py check', check='구조 검사 통과를 확인합니다. 구조가 맞아도 질문의 답이 맞는지는 앞의 원자료 대조로 판단합니다.',
            recovery='python run.py parts\npython run.py check\npython run.py query'),
        section('저장하고 다시 확인하기', [
            '**파일 → 모두 저장**을 선택합니다. 같은 폴더를 닫았다 다시 열고 아래 명령으로 모델과 답을 다시 확인합니다.',
            'requirements.md에 기준일·저장 시점·확인하지 못한 점을 짧게 남깁니다. 재부팅하면 학교 PC 파일이 초기화될 수 있으므로 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다.'],
            cmd='python run.py parts\npython run.py query\npython run.py check', check='다시 연 파일과 조회 결과가 유지되는지 봅니다. 이어서 할 때는 보관한 같은 폴더를 엽니다.')]


def render(title, purpose, steps):
    return F.step_page(title, F.inline(purpose), [(s['name'], s['body']) for s in steps])
