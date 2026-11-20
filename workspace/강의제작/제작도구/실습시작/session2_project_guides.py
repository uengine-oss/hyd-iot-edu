"""통합02 가이드 원고(단계의 정본). 단계 이름은 그 단계에서 배우는 원리를 앞에 두고, 시나리오는 예로 쓴다(코딩랩 K-3).
section · render · SAVE_NOTE · ASK_NOTE는 실전02 생성기도 쓴다."""
import lab_frame as F


def paragraph(text):
    return '<p>' + F.inline(text) + '</p>'


def commands(items):
    return ''.join(F.command_block(cmd) + '<p class="check">' + F.inline(check) + '</p>' for cmd, check in items)


SAVE_NOTE = '파일을 손으로 고친 뒤에는 **Ctrl+S**로 저장합니다(탭 이름 옆 ●가 사라지면 저장됨). 저장하지 않으면 명령이 고치기 전 내용을 읽어 0행으로 보입니다.'
ASK_NOTE = ('요청에 파일 이름을 쓸 때는 키보드 숫자 1 왼쪽의 백틱 기호로 앞뒤를 감쌉니다. 채팅 입력이 밑줄(_)을 서식으로 바꾸기 때문입니다. '
            '`python run.py` 명령은 내 터미널에서 실행하고, 터미널 출력과 결과 화면으로 확인합니다.')
IMPL_NOTE = ('Codex가 파일을 바꾸려 하면 편집 승인 창이 뜹니다. `app/features/` 아래 요청한 파일이면 **Allow once**, 그 밖의 경로면 **Deny**를 누릅니다. ' + ASK_NOTE)


def section(name, text, *, prompt=None, cmd=None, check='', ai=False, extra='', recovery=None, followup=None, when_new=None, lead=''):
    """prompt = 정답 토글의 요청 하나(글) 또는 차례로 보낼 요청 여럿(tuple) — 한 요청에 기능 하나씩(코딩랩 K-3).
    lead = 본문 바로 뒤 · 정답 토글 앞에 둘 HTML(학생이 토글보다 먼저 볼 표), extra = 토글 뒤 · 명령 앞."""
    body = ''.join(t if t.startswith('<') else paragraph(t) for t in text) + lead   # '<'로 시작하는 칸은 본문 사이에 둘 블록 HTML(F.block)
    if isinstance(prompt, tuple):
        body += F.answer_html(F.A('막히면 지금까지 확인한 내용에 이어서 아래 요청을 차례로 보냅니다. 앞 요청의 결과를 본 뒤 다음 요청을 보냅니다.',
                                  *[F.ask_ai(p) for p in prompt]))
    elif prompt:
        body += F.answer_html(F.A('막히면 지금까지 확인한 내용에 이어서 요청합니다.', F.ask_ai(prompt)))
    body += extra
    if cmd:
        body += F.command_block(cmd)
    if check:
        body += '<p class="check">' + F.inline(check) + '</p>'
    if when_new:
        body += '<details><summary>새 랩 DB가 만들어졌다는 안내가 나왔을 때 — 먼저 실행</summary>' + commands(when_new) + '</details>'
    if followup:
        body += commands(followup)
    if recovery:
        body += '<details><summary>고친 뒤 다시 확인</summary>' + commands(recovery) + '</details>'
    return dict(name=name, body=body, ai=ai)


ONTOLOGY_PURPOSE = ('이론에서 배운 클래스 · 인스턴스 · 식별자로, 포털 지식 지도에서 살펴본 연결을 직접 설계합니다. '
                    '온톨로지 → 에이전트 → 프로세스로 이어지는 과정의 첫 단계로, 기종(모델)이 셋인 유압 파워팩 다섯 대의 원자료에서 설비별 센서와 함께 쓰는 부품을 찾는 온톨로지를 만듭니다. 결과는 사람마다 조금씩 달라도 되고, 내가 먼저 정한 기대 답과 맞으면 됩니다.')
GRAPH_PURPOSE = ('설계 실습에서 다룬 클래스 · 식별자 · 관계를 Neo4j 실습에서 써 본 MERGE로 이 폴더 전용 그래프 DB(랩 DB)에 옮깁니다. '
                 '과정의 첫 단계인 온톨로지를 그래프 DB에서 실제로 묻고 고쳐 보며, 역량 질문마다 쿼리를 돌린 결과와 수정본을 반영한 결과를 원자료와 대조합니다. 결과는 사람마다 조금씩 달라도 되고, 내가 먼저 정한 기대 답과 맞으면 됩니다.')


def ok(text):
    return '**확인** ' + text


def hint(question, items):
    """힌트 — 물음 하나와 그 답이 되는 단어 · 짧은 구 목록. 학생은 이 항목을 자기 말로 엮어 Codex에 묻는다.
    그대로 보내면 되는 부탁 글과 작업 지시 문구는 쓰지 않고, 부탁 글은 정답 보기에만 둔다(가이드 P-3 · P-4 · P-5 —
    사용자 2026-11-20 「정답을 단어형태로 알려주는건 좋은데 프롬포트 자체를 주면안됨」 · 「그냥 딱 행위 설명만 … 군더더기 다 빼고」)."""
    return ('<div class="hint ai"><p class="kind">힌트</p>'
            f'<p><b>{F.inline(question)}</b></p><ul>' + ''.join(f'<li>{F.inline(i)}</li>' for i in items) + '</ul></div>')


APPROVE = 'Codex가 파일을 고치려 하면 `app/features/` 안이면 **Allow once**, 밖이면 **Deny**를 누릅니다. 부탁 속 파일 이름은 백틱 기호(키보드 숫자 1 왼쪽)로 감쌉니다.'


def setup(folder, first=True):
    text = [f'ZIP을 풀고 VS Code **파일 → 폴더 열기**로 안쪽 `{folder}` 폴더(`run.py`가 든 폴더)를 엽니다(바깥 폴더를 열면 Codex가 정답이 든 이 가이드까지 읽습니다). '
            '신뢰를 물으면 **예, 작성자를 신뢰합니다**를 누르고, **터미널 → 새 터미널**에 아래 명령을 복사해 붙여 넣습니다(손으로 치면 오타가 납니다).'
            + ('' if first else ' 랩 DB를 쓰는 명령은 터미널에서만 실행합니다(02단계).')]
    return section('폴더 열고 자료 확인하기', text, cmd='python run.py',
                   check=ok('원자료 줄 수가 보이고 결과 화면이 열리면 됩니다. 안 열리면 탐색기에서 `output/result.html`을 엽니다. 이후 명령 뒤에는 결과 화면에서 F5를 누릅니다.'))


def decide_request(point):
    """결정을 Codex에게 적게 하는 정답 토글 요청 — ○○ 자리는 학생이 고른 것과 자기 이유로 채운다(AGENTS.md: 이유 없는 결정은 받지 않는다)."""
    return f'「{point}」 지점은 「○○」로 정했어. 이유는 ○○이고, 열어 본 근거 줄은 ○○야. `decisions.csv`의 이 지점 줄에 적어 줘. 다른 파일은 바꾸지 마.'


def closing(step, tail):
    """마지막 단계의 명령들 뒤에 붙일 HTML(내 말로 되짚기) — 가이드가 명령 확인 문장으로 끝나지 않게 한다(코딩랩 머리말 · 가이드 P-5)."""
    return dict(step, body=step['body'] + tail)


KEEP = '학교 PC는 재부팅하면 초기화될 수 있으니 폴더를 USB나 개인 클라우드에 보관합니다.'


def ontology():
    import session2_answers as ANS   # 역량 질문 문장은 강사 참조와 한 곳에서 쓴다
    questions = '① ' + ANS.COMPETENCY_QUESTIONS[0] + ' ② ' + ANS.COMPETENCY_QUESTIONS[1] + ' ③ ' + ANS.COMPETENCY_QUESTIONS[2]
    return [setup('ontology-lab'),
        section('Codex에게 물어 자료 파악하기', [
            'Codex 채팅을 열고 원자료(`data/`)를 물어 파악합니다(계정이 없으면 따로 받는 완성본 ZIP으로 결과만 봅니다).',
            hint('무엇을 물어볼까?', ['표마다 무엇이 들었고 몇 줄인가', '표끼리 잇는 열', '같은 것을 다르게 적은 곳 — 예 줄(파일:줄)과 개수'])],
            prompt='파일은 바꾸지 말고 `data/` 폴더를 살펴봐 줘. 표마다 무엇이 들어 있고 몇 줄인지, 어떤 열로 서로 이어지는지, 같은 것을 다르게 적은 곳은 어디인지 예 줄(파일:줄)과 개수로 짚어 줘.',
            check=ok('짚어 준 줄 한두 곳을 열어 설명과 같으면 됩니다. 이 단계에서 승인 창이 뜨면 **Deny**를 누릅니다.'), ai=1),
        section('역량 질문과 기대 답 정하기', [
            '결과를 보기 전에 세 **역량 질문**(스키마가 답해야 할 질문)의 기대 답을 Codex에게 받아 `expected.csv`에 적게 합니다. ' + questions,
            hint('기대 답은 무엇을 받아 정할까?', ['질문마다 물을 값 · 기대 답 · 근거 줄(파일:줄)', '내가 정해야 답이 갈리는 줄 — 05 · 06단계에서 고른 뒤 넣음']),
            APPROVE + ' 적었다고 하면 `expected.csv`를 열어 봅니다.'],
            prompt=('세 역량 질문의 기대 답 후보를 원자료에서 찾아 근거 줄(파일:줄)과 함께 표로 보여 줘. ' + questions
                    + ' 꼴은 `expected.csv` 빈 틀의 첫 줄을 따르고, 파일은 바꾸지 마. 구성 요소 자리와 실물, 같은 물리량의 범위처럼 내가 정해야 답이 갈리는 줄은 갈래마다 답이 어떻게 달라지는지만 보여 주고 정하지는 마.',
                    '방금 표의 줄 가운데 펌프 자리의 실물 줄과 질문 2의 줄을 뺀 나머지를 `expected.csv`에 적어 줘. 다른 파일은 바꾸지 마.'),
            cmd='python run.py expected', check=ok('기대 답 표가 내가 받아들인 줄과 같으면 됩니다.'), ai=2),
        section('클래스와 식별자, 관계 방향과 카디널리티 정하기', [
            'Codex의 추천안을 받아 클래스 다섯(설비 · 구성 요소 · 센서 · 부품 · 물리량)의 식별자와 관계를 정하고, `design.csv` · `relations.csv`에 반영하게 합니다.',
            hint('태그 TS1이 네 대에 다 있는데, 무엇을 정해야 할까?', ['**식별자**(하나를 가리키는 이름)', '관계 방향', '**카디널리티**(한쪽 하나에 반대쪽이 많아야 몇 개)', 'TS1이 설비마다 따로 되나'])],
            prompt='세 역량 질문에 답하는 모델을 만들려고 해. 지금 정한 식별자와 관계 방향 · 카디널리티를 `app/features/design.csv`와 `relations.csv`에 반영해 줘. 같은 이름의 다른 대상이 한 식별자로 합쳐지면 안 돼. 반영한 뒤 TS1이 설비마다 다른 식별자가 되는지 원자료 열로 확인해 줘. 실물 행과 구성 요소-실물 행은 내가 정할 때까지 넣지 말고, 다른 파일은 바꾸지 마.',
            cmd='python run.py design', check=ok('「식별자가 겹치는 원자료 행(이름을 맞추기 전)」 표에 HYD-02 펌프 두 줄만 남으면 됩니다(다음 단계에서 정함).'), ai=3),
        section('새 클래스를 만들지 정하기: 구성 요소 자리와 실물', [
            'HYD-02 펌프 자리의 두 줄(떼어 낸 펌프 · 지금 펌프)을 어떻게 둘지 내가 고릅니다. 정답은 없습니다. 고른 것과 이유를 Codex에게 말해 `decisions.csv`에 적게 하고, 이어서 펌프 자리 줄을 `expected.csv`에 더하게 한 뒤 표를 맞추게 합니다.',
            hint('무엇을 따져 보고 고를까?', ['일련번호를 구성 요소의 속성으로 두면 → 질문 1의 답', '실물을 클래스로 따로 두면 → 질문 1의 답', 'Codex의 추천안과 까닭', '헷갈리면 「내가 정할 것을 하나씩 물어봐 줘」'])],
            prompt=(decide_request('구성 요소 자리와 그 실물'),
                    '앞에서 갈래마다 보여 준 후보 가운데 `decisions.csv`에 적은 내 선택(구성 요소 자리와 그 실물)에 맞는 펌프 자리 줄을 `expected.csv` 질문 1에 더해 줘. 다른 파일은 바꾸지 마.',
                    '`decisions.csv`에 적은 내 선택(구성 요소 자리와 그 실물)대로 `row_rules.csv`의 떼어 낸 펌프 줄과 `design.csv` · `relations.csv`를 맞춰 줘. 근거 칸에는 내가 말한 이유를 적어 줘. 판단 함수 파일(.py)과 `expected.csv`는 바꾸지 마.'),
            cmd='python run.py names', check=ok('실물을 따로 두었으면 「구성 요소 자리마다 실물(일련번호)」 표에 HYD-02의 지금 · 지난 펌프가 보이고, 두지 않았으면 떼어 낸 펌프는 물을 수 없다는 안내가 나옵니다.'), ai=3),
        section('같은 대상으로 볼 범위 정하기: 같은 물리량', [
            '재는 값은 같고 지점이 다른 센서(쿨러의 유온 · 쿨러 출구 유온)를 한 물리량으로 묶을지 나눌지 내가 고릅니다. 고른 것과 이유를 `decisions.csv`에 적게 하고, 질문 2 줄을 `expected.csv`에 더하게 한 뒤 `quantity_rules.py`에 구현하게 합니다.',
            hint('무엇을 따져 보고 고를까?', ['재는 값의 종류로 묶으면 → 질문 2의 묶음', '재는 지점마다 나누면 → 질문 2의 묶음', 'HYD-07 현장 지시계 두 줄이 가는 곳'])],
            prompt=(decide_request('같은 물리량의 범위'),
                    '앞에서 갈래마다 보여 준 후보 가운데 `decisions.csv`에 적은 내 선택(같은 물리량의 범위)에 맞는 질문 2의 묶음 줄과 센서 값 줄을 `expected.csv`에 더해 줘. 물을 값의 물리량 이름은 내가 말한 이름으로 적어 줘. 다른 파일은 바꾸지 마.',
                    '`decisions.csv`에 적은 내 선택(같은 물리량의 범위)을 `quantity_rules.py`의 두 함수에 규칙으로 구현해 줘. 센서를 한 줄씩 이름표로 옮기지 말고 태그 · 재는것 · 붙은곳 입력으로 가르게 해 줘. 서로 다른 묶음에는 다른 이름을 주고, 내가 `expected.csv` 질문 2에 적은 물리량 이름을 써 줘. 다른 파일은 바꾸지 마.'),
            cmd='python run.py quantities', check=ok('「물리량마다 묶인 센서(same_quantity · quantity_name)」 표가 기대 답의 묶음과 같으면 됩니다. `quantity_rules.py`를 열어 내 선택이 든 조건 줄을 봅니다.'), ai=3),
        section('식별자와 다른 이름 잇기: 부품과 품번 표기', [
            '아래 명령이 예전 품번 · 줄여 쓴 표기 · 제조사 품번을 사내 품번의 **다른 이름**으로 잇고, 모델 파일(`output/schema.json` · `graph.json`)을 만듭니다.'],
            cmd='python run.py parts', check=ok('「사내 품번을 찾지 못한 교체부품 칸(잇지 않음)」 표가 비어 있으면 됩니다(「교체부품 칸이 빈 구성 요소(잇지 않음)」 표의 구동 모터 줄은 정상).'), ai=0),
        section('역량 질문으로 모델 검증하기', [
            '처음 고르지 않은 설비와 예전 품번 · 원자료에 없는 품번의 기대 답을 먼저 더하게 한 뒤, 모델의 답과 대조합니다.',
            hint('「같음」이 아닌 줄이 나오면, 무엇을 보여 물을까?', ['물은 값 · 기대 답 · 실제 답', '원인과 고칠 판단 함수 파일', '두 번 고쳐도 안 되면 새 대화에서'])],
            prompt=('처음 고르지 않은 설비 하나와 예전 품번 · 원자료에 없는 품번을 원자료에서 골라, 기대 답을 근거 줄과 함께 `expected.csv`에 더해 줘. 다른 파일은 바꾸지 마.',
                    '결과 화면의 「질문별 대조」 표에서 「같음」이 아닌 줄 하나의 물은 값, `expected.csv`의 기대 답과 근거, 실제 답을 견줘 원인을 설명해 줘. 먼저 파일은 바꾸지 마. 원인을 확인하면 그 판단 함수 파일만 고치도록 요청할게.'),
            cmd='python run.py query', check=ok('줄마다 「같음」이거나 차이를 원자료로 설명할 수 있으면 됩니다. 결과에 맞춰 기대 답을 바꾸지 않습니다.'), ai=2,
            followup=[('python run.py check', '「구조 검사 통과」가 보이면 됩니다.')],
            recovery=[('python run.py parts', '고친 기준으로 모델이 생성됐는지 봅니다.'),
                      ('python run.py query', 'F5를 눌러 고친 질문의 기대 답과 실제 답을 대조합니다.'),
                      ('python run.py check', '구조 검사를 통과하는지 봅니다.')]),
        closing(section('저장하고 다시 확인하기', [
            '폴더를 닫았다 다시 열고 아래 명령을 실행합니다. ' + KEEP],
            cmd='python run.py parts', check=ok('모델이 생성되면 됩니다.'),
            followup=[('python run.py query', 'F5를 눌러 답이 그대로인지 봅니다.')]),
            paragraph('**내 말로** 두 지점을 왜 그렇게 골랐고 그래서 질문 1 · 2의 줄이 어떻게 나왔는지 말해 봅니다.'))]


def render(title, purpose, steps):
    return F.step_page(title, F.inline(purpose), [(s['name'], s['body']) for s in steps])


GRAPH_QUESTIONS = ('① 설비의 구성 요소마다 어떤 센서가 붙는가? ② 설비의 구성 요소마다 어떤 교체 부품이 들어가는가? '
                   '③ 부품을 어느 설비가 쓰고 그 설비의 상태는 무엇인가? 예전 품번이나 원자료에 없는 품번으로 물으면 어떻게 구별되는가?')


def own_model():
    """선택: 설계 실습에서 만든 내 모델 쓰기(접힌 안내) — Codex는 폴더 밖을 읽지 않으므로 복사는 터미널 명령으로 한다(학생의 입력은 터미널과 Codex뿐)."""
    return ('<details><summary>선택: 설계 실습에서 만든 내 모델을 쓰려면</summary>'
            + paragraph('<설계 실습 폴더>를 내 경로로 바꿔 터미널에서 실행하고, Codex에게 `data/model/graph.json`과 같은 꼴인지 확인받습니다. 다르면 그 폴더를 지우게 하고 제공 모델로 갑니다.')
            + F.command_block('mkdir app\\features\\model -Force; Copy-Item "<설계 실습 폴더>\\output\\schema.json","<설계 실습 폴더>\\output\\graph.json" app\\features\\model\\')
            + '</details>')


def graph(portal_table):
    return [setup('graph-lab', first=False),
        section('랩 DB 준비하기', [
            'Docker Desktop을 켜고 아래 명령을 터미널에서 실행해, 이 폴더 전용 Neo4j 그래프 DB(랩 DB)를 띄웁니다. Codex가 이 명령을 실행하려 하면 **Deny**를 누릅니다(Codex는 Docker에 닿지 못합니다). 처음 한 번은 이미지를 받느라 오래 걸립니다.'],
            cmd='python run.py db', check=ok('「랩 DB 준비 완료」가 나오고 모델과 랩 DB 개수가 나란히 보이면 됩니다(처음은 0).')),
        section('Codex에게 물어 제공 모델 파악하기', [
            'Codex에게 제공 모델(`data/model/`)의 짜임과 개수를 물어 파악합니다. 화면의 「종류」는 클래스이고, 그래프에서는 노드의 **레이블**입니다.',
            hint('무엇을 물어볼까?', ['종류마다 개수', '관계의 개수와 방향', '식별자를 지은 법', '원자료 줄 수와 다른 곳과 그 까닭'])],
            prompt='파일은 바꾸지 말고 `data/model/schema.json`과 `graph.json`을 살펴봐 줘. 종류마다 몇 개인지, 관계는 몇 개이고 어느 쪽에서 어느 쪽으로 가는지, 식별자는 어떻게 지었는지 알려 주고, 원자료 줄 수와 다른 곳이 있으면 원자료 줄(파일:줄)로 까닭을 짚어 줘.',
            extra=own_model(), check=ok('01단계 화면의 개수와 같고, 원자료 구성 요소 41줄과 모델 40개가 다른 까닭을 말할 수 있으면 됩니다.'), ai=1),
        section('역량 질문과 기대 답 정하기', [
            '쿼리를 쓰기 전에 세 **역량 질문**의 기대 답을 Codex에게 받아 `expected.csv`에 적게 합니다. ' + GRAPH_QUESTIONS,
            hint('기대 답은 무엇을 받아 정할까?', ['물을 값 · 기대 답 · 근거 줄', '볼_열 — `tag` · `part` · `asset` · `status` · `note`', '질문 ③의 부품 — HYD-07도 쓰는 것, 수정본 반영 전 답']),
            APPROVE + ' 적었다고 하면 `expected.csv`를 열어 봅니다.'],
            prompt=('세 역량 질문의 기대 답 후보를 원자료와 제공 모델에서 찾아 근거 줄(파일:줄)과 함께 표로 보여 줘. ' + GRAPH_QUESTIONS + ' 꼴은 `expected.csv` 빈 틀의 첫 줄을 따르고, 볼_열은 tag · part · asset · status · note 가운데 그 줄에 맞는 이름으로 붙여 줘. 질문 3은 수정본을 반영하기 전의 답으로 해 줘. 파일은 바꾸지 마.',
                    '방금 표의 줄을 `expected.csv`에 적어 줘. 다른 파일은 바꾸지 마.'),
            cmd='python run.py expected', check=ok('기대 답 표가 내가 받아들인 줄과 같으면 됩니다.'), ai=2),
        section('그래프에 남길지 정하기: 불용 결정 설비', [
            '수정본(`data/changes/2026-10-20/`)에서 불용이 된 설비를 그래프에서 어떻게 할지 내가 고릅니다. 정답은 없습니다. 고른 것과 이유를 Codex에게 말해 `decisions.csv`에 적게 합니다.',
            hint('무엇을 따져 보고 고를까?', ['상태만 바꿔 남기면 → 질문 ③의 답', '그 설비에만 속한 노드와 함께 지우면 → 질문 ③의 답', '보전팀이 준비할 예비품', 'Codex의 추천안과 까닭', '헷갈리면 「내가 정할 것을 하나씩 물어봐 줘」'])],
            prompt=decide_request('불용 결정 설비'),
            check=ok('`decisions.csv`의 이 지점 줄에 고른 것과 내 이유가 내 말대로 적혔으면 됩니다.'), ai=2),
        section('스키마를 그래프로 옮기기: 적재와 다시 적재', [
            'Codex에게 `load.cypher`를 구현하게 해 모델을 랩 DB로 옮기고, 한 번 더 적재해 개수가 그대로인지 봅니다. 클래스는 레이블, 인스턴스는 노드가 됩니다.',
            hint('다시 적재해도 늘지 않으려면, 무엇을 정해 말할까?', ['MERGE — 있으면 찾고 없을 때만 만듦(CREATE는 늘 새로 만듦)', 'MERGE 패턴 — 바뀌지 않는 식별자만', '이름 같은 값 — SET', '행 — `$rows`(실행할 때 값을 넣는 자리)', '종류 · 관계마다 쿼리 하나'])],
            prompt='MERGE의 패턴에는 바뀌지 않는 식별자(`schema.json`의 식별자)만 적고 이름 같은 값은 SET으로 넣어 `load.cypher`를 구현해 줘. `schema.json`의 종류와 관계 방향을 따르고 행은 $rows로 받아 줘. 종류 · 관계마다 쿼리를 나누고 바로 위에 `// 넣을 것: <종류 또는 관계>`를 적어 줘. 같은 대상을 중복 생성하거나 전체를 지우지 마. 조회 쿼리와 수정 쿼리는 아직 작성하지 마.',
            cmd='python run.py load', check=ok('모델과 랩 DB의 종류별 개수가 같으면 됩니다.'), ai=2,
            followup=[('python run.py repeat', '한 번 더 적재해도 개수가 같으면 됩니다. 늘었으면 Codex에게 MERGE의 패턴을 고치게 합니다.')]),
        section('역량 질문을 쿼리로 묻기: 질문 1 구성 요소별 센서', [
            'Codex에게 `query.cypher`의 질문 ① 쿼리를 쓰게 하고 실행합니다.',
            hint('결과가 비어 나오지 않으려면, 무엇을 짚을까?', ['설비 → 구성 요소 → 센서의 관계 방향(`schema.json`)', '설비 코드 — `$` 자리 하나', '돌려줄 열 — `tag`', '한계가 없는 센서 — 0이 아니라 빈칸', '결과가 다르면 물은 값 · 기대 답 · 실제 결과를 보여 원인부터'])],
            prompt='`query.cypher`에 질문 1만 작성해 줘. 설비 코드를 $ 자리 하나로 받아 구성 요소와 거기 붙은 센서의 태그(tag) · 물리량 · 단위 · 정상값 · 한계를 돌려줘. 없는 한계를 0으로 채우지 마. 질문 2와 3은 내가 결과를 본 뒤 하나씩 요청할게.',
            cmd='python run.py sensors', check=ok('센서 태그가 기대 답과 같으면 됩니다.'), ai=1),
        section('질문 2: 구성 요소마다 교체 부품', [
            'Codex에게 질문 ② 쿼리를 더하게 하고 실행합니다.',
            hint('질문 ①과 무엇이 다를까?', ['구성 요소 → 부품의 관계 방향', '돌려줄 열 — `part`'])],
            prompt='`query.cypher`에 질문 2만 더해 줘. 설비 코드를 $ 자리 하나로 받아 그 설비의 구성 요소마다 이어진 교체 부품의 사내 품번(part)과 품명을 돌려줘. 질문 1은 그대로 두고, 질문 3은 내가 결과를 본 뒤 요청할게.',
            cmd='python run.py parts', check=ok('다른 표기로 적힌 교체부품도 사내 품번으로 나오면 됩니다.'), ai=1),
        section('질문 3: 다른 표기로 부품 찾기와 사용 설비', [
            'Codex에게 질문 ③ 쿼리를 더하게 하고 실행합니다.',
            hint('0줄이 나와도 까닭을 가리려면, 무엇을 짚을까?', ['다른 이름(`other_codes`)으로도 찾기', '돌려줄 열 — `part` · `asset` · `status`', '원자료에 없는 품번 — `note`에 한 줄'])],
            prompt='`query.cypher`에 질문 3만 더해 줘. 품번이나 다른 표기를 $ 자리 하나로 받아 사내 품번이나 다른 이름(other_codes)으로 부품을 찾고, 찾은 사내 품번(part), 그 부품을 쓰는 설비 코드(asset)와 상태(status)를 돌려줘. 원자료에 없는 품번이면 note에 원자료에 없는 품번이라고 한 줄 돌려줘. 질문 1 · 2는 그대로 둬.',
            cmd='python run.py usage', check=ok('다른 표기로 물어도 같은 부품이 나오고, 없는 품번이 note로 구별되면 됩니다.'), ai=1),
        section('바뀐 것만 고치기: 수정본 반영', [
            '05단계 선택대로 수정본을 반영합니다. Codex에게 전체를 지우지 않고 식별자로 찾아 바뀐 값만 고치는 `update.cypher`를 쓰게 합니다.',
            hint('무엇을 차례로 할까?', ['질문 ③의 기대 답 고치기', '반영 뒤 설비마다 있어야 할 구성 요소 · 센서 수', '`update.cypher` — 식별자는 그대로, 바뀐 값만'])],
            prompt=('`decisions.csv`의 내 선택(불용 결정 설비)대로 수정본을 반영한 뒤의 답으로 `expected.csv` 질문 3 줄을 고쳐 줘. 다른 파일은 바꾸지 마.',
                    '수정본을 반영한 뒤 설비마다 있어야 할 구성 요소 수와 센서 수를 원자료 줄로 세어 줘. 파일은 바꾸지 마.',
                    '수정본의 줄과 `decisions.csv`의 내 선택(불용 결정 설비)을 `update.cypher`에 반영해 줘. 이름이 바뀐 설비는 식별자를 그대로 두고 이름만 고치고, 전체를 지우지 마. 지우는 범위가 분명하지 않으면 작성하기 전에 물어봐.'),
            cmd='python run.py update', check=ok('바뀐 대상과 개수를 수정본으로 설명할 수 있고, 두 번째 실행에서 더 바뀐 것이 없으면 됩니다.'), ai=3,
            followup=[('python run.py status', '랩 DB의 종류별 개수가 Codex가 센 수와 같으면 됩니다.'),
                      ('python run.py usage', 'F5를 눌러 내 선택이 질문 3에 반영됐는지 봅니다.')]),
        section('포털 기준 지도와 견주기', [
            '아래 명령으로 「내 그래프」 표를 띄워, 그 아래 포털 지식 지도(기준 지도) 표와 쿨러를 어떻게 셌는지 견줍니다. 기준 지도의 상태 변수 줄은 내 모델의 물리량 자리이고, CE 센서는 이 원자료 밖입니다.'],
            check=ok('두 표의 차이와 그 까닭을 실제 줄로 말할 수 있으면 됩니다. 모델은 바꾸지 않습니다.'), ai=0,
            lead=commands([('python run.py compare', '결과 화면에 「내 그래프」 표가 보이면 아래 기준 지도 표와 견줍니다.')]) + '<div style="overflow-x:auto">' + portal_table + '</div>'),
        closing(section('저장하고 다시 확인하기', [
            '폴더를 닫았다 다시 열고 아래 명령으로 랩 DB를 켭니다. ' + KEEP],
            cmd='python run.py db',
            check=ok('같은 랩 DB가 열리면 됩니다. 새 랩 DB를 만들었다고 나오면 접힌 안내의 적재 · 수정을 먼저 실행합니다.'),
            when_new=[('python run.py load', '넣은 개수가 모델과 같은지 봅니다.'),
                      ('python run.py update', '수정본과 내 선택이 반영됐는지 봅니다.')],
            followup=[('python run.py usage', 'F5를 눌러 결과가 그대로인지 봅니다.'),
                      ('python run.py export', '랩 DB의 그래프를 `output/schema.json` · `graph.json`으로 저장합니다.'),
                      ('python run.py check', '「구조 검사 통과」가 보이면 됩니다.')]),
            paragraph('**내 말로** 불용 설비를 왜 그렇게 처리했고 질문 ③이 어떻게 나왔는지, 다시 적재해도 늘지 않은 까닭을 말해 봅니다.'))]
