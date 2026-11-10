"""통합02 가이드 원고. 지금 필요한 이유·행동·확인만 기능 순서로 제공한다."""
import lab_frame as F


def paragraph(text):
    return '<p>' + F.inline(text) + '</p>'


def commands(items):
    return ''.join(F.command_block(cmd) + '<p class="check">' + F.inline(check) + '</p>' for cmd, check in items)


def section(name, text, *, prompt=None, cmd=None, check='', ai=False, extra='', recovery=None, followup=None):
    body = ''.join(paragraph(t) for t in text)
    if prompt:
        body += F.answer_html(F.A('막히면 지금까지 확인한 내용에 이어서 요청합니다.', F.ask_ai(prompt)))
    body += extra
    if cmd:
        body += F.command_block(cmd)
    if check:
        body += '<p class="check">' + F.inline(check) + '</p>'
    if followup:
        body += commands(followup)
    if recovery:
        body += '<details><summary>고친 뒤 다시 확인</summary>' + commands(recovery) + '</details>'
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
        text += ['`README.md`에서 폴더 역할을 봅니다. `AGENTS.md`는 Codex의 공통 작업 원칙입니다. `data/model/`에는 바로 쓸 수 있는 모델이 있어 자기 모델이 없어도 시작할 수 있습니다.']
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
            recovery=[('python run.py parts', '고친 기준으로 모델이 생성됐는지 봅니다.'),
                      ('python run.py query', 'F5를 눌러 고친 질문의 기대 답과 실제 답을 대조합니다.')]),
        section('구조 확인하기', [
            '답의 의미를 확인했으므로 식별자 중복과 잘못된 연결도 검사합니다. 오류가 있으면 명령과 출력 전문을 Codex에 보내 어느 구현에서 생겼는지 찾습니다.',
            '기준이나 기능을 고쳤다면 `python run.py parts`로 모델을 다시 만들고 아래 검사를 실행합니다. 그 뒤 `python run.py query`로 질문의 답도 달라졌는지 봅니다.'],
            prompt='구조 검사 출력이 가리키는 대상과 관계를 찾아, app/features의 어떤 기준에서 생긴 문제인지 설명해 줘. 원자료와 검사 기준은 바꾸지 마. 내가 원인을 확인하면 필요한 부분만 고쳐 줘.',
            cmd='python run.py check', check='구조 검사 통과를 확인합니다. 구조가 맞아도 질문의 답이 맞는지는 앞의 원자료 대조로 판단합니다.',
            recovery=[('python run.py parts', '고친 기준으로 모델이 생성됐는지 봅니다.'),
                      ('python run.py check', '구조 오류가 사라졌는지 확인합니다.'),
                      ('python run.py query', 'F5를 눌러 질문의 답도 원자료와 대조합니다.')]),
        section('저장하고 다시 확인하기', [
            '**파일 → 모두 저장**을 선택합니다. 같은 폴더를 닫았다 다시 열고 아래 명령으로 모델과 답을 다시 확인합니다.',
            'requirements.md에 기준일·저장 시점·확인하지 못한 점을 짧게 남깁니다. 재부팅하면 학교 PC 파일이 초기화될 수 있으므로 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다.'],
            cmd='python run.py parts', check='다시 연 파일로 모델이 생성되는지 봅니다.',
            followup=[('python run.py query', 'F5를 눌러 다시 조회한 답이 유지되는지 봅니다.'),
                      ('python run.py check', '구조 검사를 통과하는지 확인합니다. 이어서 할 때는 보관한 같은 폴더를 엽니다.')])]


def render(title, purpose, steps):
    return F.step_page(title, F.inline(purpose), [(s['name'], s['body']) for s in steps])


def graph(portal_table):
    return [setup('graph-lab', first=False),
        section('랩 DB 준비하기', [
            '모델을 넣고 조회할 공간을 준비합니다. Docker Desktop을 켜고 실행 중인지 본 뒤 아래 명령을 실행합니다. 이 폴더 전용의 별도 랩 DB가 만들어집니다.'],
            cmd='python run.py db', check='모델 파일의 개수와 랩 DB 개수가 나란히 보입니다. 처음 만든 DB는 0이며, 이어서 작업하는 DB는 이전에 넣은 개수입니다.'),
        section('Codex와 모델 파악하기', [
            '무엇을 넣을지 알아야 적재한 결과를 검증할 수 있습니다. Codex 채팅을 열어 로그인하고, 파일을 바꾸지 말고 `data/model/schema.json`과 `graph.json`의 종류·식별자·관계 방향을 설명해 달라고 요청합니다. 계정이 없거나 막히면 클래스룸에서 별도로 받는 `graph-lab-completed.zip`을 실행해 볼 수 있습니다.',
            '설비 하나를 골라 센서와 부품까지 가는 길을 원자료 행과 함께 짚어 봅니다. `data/model/provenance.md`에서 모델에 적용된 기준도 확인합니다.',
            '자기 온톨로지 모델을 쓰는 것은 선택입니다. 사용할 때만 기준일·종류·식별자·관계의 형식을 확인하고, 두 JSON 파일을 `app/features/model/`에 함께 복사합니다. 제공 모델은 보존합니다.'],
            cmd='python run.py', check='현재 사용하는 모델 경로와 개수를 확인합니다. 자기 모델을 골랐다면 이후 질문과 쿼리도 그 모델에 맞춥니다.', ai=True),
        section('질문과 기대 답 정하기', [
            '보전팀이 가동 중인 설비의 예비품을 준비할 때 쓸 답을 만듭니다. `app/features/review.md`에 질문·사용할 자료·기준일·지킬 조건을 자기 말로 적습니다. 공급 조건·입고 판단과 모델 정의 변경은 이번 범위에서 제외합니다.',
            '설비별 센서, 설비별 교체 부품, 부품의 사용 설비를 조회할 것입니다. `expected.csv`에 원자료에서 찾은 답과 근거를 먼저 적습니다. 설비 하나의 센서와 부품, 공용 부품, 다른 표기, 없는 품번을 확인할 값을 고릅니다. 볼 열은 조회 결과에서 비교할 열 이름입니다.',
            '가동하지 않는 설비를 사용 설비 조회에서 어떻게 보일지 정합니다. `data/changes/2026-10-20/`의 수정본도 읽고 불용으로 바뀐 설비를 상태로 남길지, 그 설비에만 속한 대상과 함께 지울지 선택합니다. 선택과 근거를 `decisions.csv`에 적고 AI의 추천은 원자료로 다시 확인합니다.'],
            prompt='내 review.md, expected.csv, decisions.csv를 읽고 방금 확인한 모델·원자료·수정본과 맞는지 짚어 줘. 파일은 바꾸지 마. 기대 답에 필요한 조건이나 내 선택이 빠졌으면 먼저 물어봐.',
            cmd='python run.py expected', check='화면에 내가 적은 입력·기대 답·근거가 보입니다. 이 답으로 조회 결과를 대조합니다.', ai=True),
        section('모델 적재하기', [
            '같은 대상을 무엇으로 알아볼지 Codex와 정합니다. 다시 적재할 때 이미 고친 값을 유지할지 원자료 값으로 되돌릴지도 검토합니다.',
            '계획을 확인한 뒤 `app/features/load.cypher`만 작성하도록 요청합니다. 종류·관계마다 문장을 나누고, 바로 위에 `// 넣을 것: <종류 또는 관계>`를 적습니다. 제공 도구가 해당 행을 `$rows`로 넘겨 실행합니다.'],
            prompt='지금 검토한 식별 기준과 재적재 시 값 처리 방식을 load.cypher에 구현해 줘. schema.json의 종류와 관계 방향을 따르고 행은 $rows로 받아 줘. 같은 대상을 중복 생성하거나 전체를 지우지 마. 조회와 수정은 아직 작성하지 마.',
            cmd='python run.py load', check='모델 파일과 DB의 종류별 개수가 같은지 봅니다. 다르면 해당 종류의 입력 행과 적재 문장을 Codex와 대조합니다.', ai=True),
        section('같은 적재 다시 확인하기', [
            '같은 파일을 다시 넣어도 설비와 센서가 늘어나면 안 됩니다. 아래 명령으로 적재를 한 번 더 실행하고 전후 개수를 비교합니다.'],
            prompt='지금 적재 전후 개수에서 늘어난 종류가 있다면 load.cypher가 같은 대상을 어떻게 찾는지 설명해 줘. 전체 삭제는 하지 마. 원인을 확인한 뒤 필요한 문장과 실제 중복 대상만 정리할게.',
            cmd='python run.py repeat', check='늘거나 사라진 항목이 없는지 봅니다. 개수를 `review.md`에 짧게 남깁니다.'),
        section('설비별 센서 조회하기', [
            '적재한 그래프에서 설비의 센서를 찾아봅니다. Codex에게 고른 설비에서 센서까지 어떤 관계를 따라갈지 먼저 설명하게 합니다. 설비에 바로 붙은 센서와 한계가 없는 센서를 어떻게 보여 줄지도 정합니다.',
            '`app/features/query.cypher`의 `// 질문 1` 아래에 현재 조회만 작성합니다. 물을 값은 `$` 자리 하나로 받고, 결과에는 구성 요소·센서 식별자와 물리량·단위·정상값·한계를 담습니다.'],
            prompt='지금 확인한 경로와 표시 기준으로 query.cypher의 질문 1만 작성해 줘. 설비 코드는 $ 자리 하나로 받아 expected.csv의 입력마다 실행할 수 있게 해 줘. 근거 없는 한계를 0으로 채우지 마.',
            cmd='python run.py sensors', check='기대 답과 실제 센서를 원자료로 대조합니다. 다른 설비도 expected.csv에 추가해 확인하고, 차이가 나면 입력·기대 답·실제 결과로 원인부터 찾습니다.', ai=True),
        section('설비별 교체 부품 조회하기', [
            '센서를 찾은 설비에서 교체 부품도 찾습니다. 부품이 없는 구성 요소를 빼거나 빈칸으로 남기는 두 방식 중 답을 쓸 사람이 구별하기 쉬운 방식을 정합니다.',
            'Codex와 관계 방향을 확인한 뒤 `query.cypher`의 `// 질문 2` 아래에 조회를 추가합니다. 질문 1은 유지합니다.'],
            prompt='방금 정한 부품 없는 구성 요소의 표시 방식으로 질문 2를 추가해 줘. 설비 코드는 $ 자리 하나로 받고 구성 요소와 교체 부품을 돌려줘. 자료에 없는 품번을 만들지 말고 질문 1은 유지해 줘.',
            cmd='python run.py parts', check='원자료의 교체부품 칸과 조회 결과가 맞는지, 부품이 없는 구성 요소가 내 선택대로 보이는지 봅니다.', ai=True),
        section('부품의 사용 설비 조회하기', [
            '이번에는 부품에서 출발해 함께 쓰는 설비를 찾습니다. 정식 품번·다른 표기·없는 품번을 구별하는 방법을 Codex와 정하고, 설비 상태는 `decisions.csv`의 선택을 따릅니다.',
            '`query.cypher`의 `// 질문 3` 아래에 조회를 추가합니다. 앞의 두 조회는 유지합니다.'],
            prompt='지금 확인한 품번 찾기 기준과 decisions.csv의 설비 상태 선택으로 질문 3만 추가해 줘. 품번이나 표기를 $ 자리 하나로 받아 사용 설비와 구성 요소를 돌려줘. 없는 품번과 쓰는 설비가 없는 부품을 구별해 줘.',
            cmd='python run.py usage', check='공용·전용 부품, 다른 표기, 없는 품번을 원자료와 대조합니다. 가동하지 않는 설비가 내 선택대로 보이는지도 확인합니다.', ai=True),
        section('수정본 반영하기', [
            '기준일 이후 바뀐 내용을 반영합니다. Codex에게 수정본의 각 줄이 원자료 어느 대상을 가리키는지 물어보고 그 줄을 직접 엽니다. 행의 삭제와 실제 대상의 삭제가 같은 뜻인지 확인합니다.',
            '불용 설비의 처리는 기록한 선택을 따릅니다. 수정본을 근거로 달라질 기대 답을 먼저 갱신한 뒤, 필요한 대상·관계만 고치는 문장을 `app/features/update.cypher`에 작성하도록 요청합니다.'],
            prompt='지금 원자료와 대조한 수정본 줄과 decisions.csv의 불용 설비 처리 선택을 update.cypher에 반영해 줘. 이름이 바뀌어도 같은 대상의 식별자는 유지하고 전체를 지우지 마. 삭제 범위가 불명확하면 실행 전에 물어봐.',
            cmd='python run.py update', check='바뀐 대상·값·개수를 수정본과 대조하고 원자료에서 다시 셉니다. 실제 센서가 잘못 사라지지 않았는지 봅니다. 같은 수정을 다시 실행한 결과도 함께 표시되며 추가 변경이 없어야 합니다.', ai=True,
            followup=[('python run.py usage', 'F5를 눌러 선택한 상태가 조회에 반영됐는지 확인합니다.')]),
        section('기준 지도와 비교하기', [
            '같은 대상을 서로 어떻게 연결했는지 살펴봅니다. 아래 포털 기준 지도와 내 그래프의 설비·쿨러·센서 식별자와 관계 방향을 비교합니다. 포털을 다시 열 필요는 없습니다.',
            '`review.md`에 같은 곳과 다른 곳, 그 까닭을 짧게 적습니다. 차이를 없애려고 모델을 바꾸지 말고 각 설계가 무엇을 구분하는지 설명합니다.'],
            prompt='지금 내가 대조한 두 지도에서 식별자와 관계 방향이 다른 곳을 짚었어. 내 설명이 내 그래프의 실제 대상·관계와 맞는지 확인해 줘. 파일과 모델은 바꾸지 마.',
            cmd='python run.py compare', check='설비·쿨러·센서의 식별자와 방향을 두 표의 실제 줄로 설명할 수 있으면 저장합니다.', extra='<div style="overflow-x:auto">' + portal_table + '</div>', ai=True),
        section('저장하고 다시 확인하기', [
            '**파일 → 모두 저장**을 선택하고 같은 폴더를 닫았다 다시 엽니다. 아래 명령으로 랩 DB를 켜고 조회 결과와 저장한 그래프를 확인합니다.',
            '`review.md`에 기준일·수정본 날짜·저장 시점·확인하지 못한 점을 짧게 남깁니다. 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다. 계정 없이 결과를 실행할 때는 클래스룸의 별도 `graph-lab-completed.zip`을 사용합니다.'],
            cmd='python run.py db',
            check='같은 폴더의 DB가 열렸는지 봅니다. 수정 뒤 개수는 제공 모델과 다를 수 있습니다. 새 DB를 만들었다는 안내가 나오면 아래 접힌 안내에서 저장한 적재·수정을 먼저 실행합니다.',
            followup=[('python run.py usage', 'F5를 눌러 수정 뒤 조회 결과가 유지되는지 봅니다.'),
                      ('python run.py export', '`output/schema.json`과 `graph.json`에 저장한 개수를 확인합니다.'),
                      ('python run.py check', '구조 검사를 통과하는지 확인합니다.')],
            recovery=[('python run.py load', '새 DB에 넣은 개수가 사용한 모델과 같은지 봅니다.'),
                      ('python run.py update', '수정본의 값과 선택한 삭제 범위가 반영됐는지 봅니다. 위의 조회·저장·구조 검사를 차례로 이어갑니다.')])]
