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


def why(text):
    return '**왜** ' + text


def todo(text):
    return '**할 일** ' + text


def ok(text):
    return '**확인** ' + text


def setup(folder, first=True):
    text = [why('랩은 이 폴더 하나로 돌고, 내 입력은 터미널 명령과 Codex 채팅뿐입니다. 파일은 Codex가 `app/features/`의 빈 틀에만 채웁니다.'),
            todo(f'ZIP을 풀고 VS Code **파일 → 폴더 열기**로 안쪽 `{folder}` 폴더(`run.py`가 든 폴더)를 엽니다. 바깥 폴더를 열면 Codex가 정답이 든 가이드까지 읽습니다. '
                 '신뢰를 물으면 **예, 작성자를 신뢰합니다**를 고릅니다. **터미널 → 새 터미널**에서 명령 블록을 복사해 붙여 넣습니다(오타를 줄이려고). '
                 + ('명령은 Codex에게 실행을 맡겨도 됩니다.' if first else '랩 DB를 쓰는 명령은 02단계의 까닭으로 터미널에서만 실행합니다.'))]
    return section('폴더 열고 자료 확인하기', text, cmd='python run.py',
                   check=ok('원자료 줄 수가 보이고 결과 화면이 열리면 됩니다. 안 열리면 Windows 탐색기에서 `output/result.html`을 엽니다. 이후 명령 뒤에는 그 화면에서 F5를 누릅니다.'))


APPROVE_NOTE = '파일 수정 승인 창이 뜨면 `app/features/` 안이면 **Allow once**, 밖이면 **Deny**를 누릅니다. 요청 속 파일 이름은 백틱(`)으로 감쌉니다. '
DECIDE_NOTE = '결정을 좌우하는 근거 줄을 한두 곳 열어 본 뒤, 고른 것과 내 이유를 Codex에게 말해 `decisions.csv`의 이 지점 줄에 적게 합니다(비어 있으면 아래 명령이 멈춥니다). '
ASK_INSTEAD = '정할 것이 헷갈리면 「알아서 해 줘」 대신 「내가 정할 것을 하나씩 물어봐 줘」라고 합니다. '   # 요령 ③을 처음 쓰는 결정 자리
NEW_CHAT = '두 번 고쳐도 안 되면 「다시 해 줘」 대신 새 대화를 열어 알게 된 것을 담아 다시 부탁합니다. '   # 요령 ⑧


def decide_request(point):
    """결정을 Codex에게 적게 하는 정답 토글 요청 — ○○ 자리는 학생이 고른 것과 자기 이유로 채운다(AGENTS.md: 이유 없는 결정은 받지 않는다)."""
    return f'「{point}」 지점은 「○○」로 정했어. 이유는 ○○이고, 열어 본 근거 줄은 ○○야. `decisions.csv`의 이 지점 줄에 적어 줘. 다른 파일은 바꾸지 마.'


def closing(step, tail):
    """마지막 단계의 명령들 뒤에 붙일 HTML(구조 검사와 내 말로 되짚기) — 가이드가 명령 확인 문장으로 끝나지 않게 한다(코딩랩 머리말 · 가이드 P-5)."""
    return dict(step, body=step['body'] + tail)


KEEP = '재부팅하면 학교 PC가 초기화될 수 있으니 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다.'


def ontology():
    import session2_answers as ANS   # 역량 질문 문장은 강사 참조와 한 곳에서 쓴다
    questions = '① ' + ANS.COMPETENCY_QUESTIONS[0] + ' ② ' + ANS.COMPETENCY_QUESTIONS[1] + ' ③ ' + ANS.COMPETENCY_QUESTIONS[2]
    return [setup('ontology-lab'),
        section('Codex에게 물어 자료 파악하기', [
            why('온톨로지에는 원자료에 있는 것만 담으므로 무엇이 있는지부터 압니다.'),
            todo('Codex 채팅을 열고(계정이 없으면 따로 받는 완성본 ZIP으로 결과만 봅니다), 파일을 바꾸지 말고 표마다 뜻 · 줄 수 · 잇는 열과 다르게 적은 곳을 예 줄(파일:줄)과 개수로 짚어 달라고 합니다. 짚어 준 줄 한두 곳을 열어 봅니다. ' + F.TIP_DATA)],
            check=ok('설비 · 구성 요소 · 센서 · 부품이 어디 있고 무엇으로 잇는지 말할 수 있으면 됩니다. 이 단계에서는 파일 수정 승인 창에 **Deny**를 누릅니다.'), ai=1),
        section('역량 질문과 기대 답 정하기', [
            why('모델이 맞는지 가릴 기대 답을 결과보다 먼저 정해야, 틀린 결과가 맞아 보이지 않습니다.'),
            todo('이번 **역량 질문**(스키마가 답해야 할 질문) 셋을 Codex에게 알리고, 기대 답 후보를 근거 줄과 함께 받습니다. ' + questions
                 + ' 몇 줄 열어 본 뒤 받아들인 줄을 `expected.csv`에 적게 하고, 파일을 열어 봅니다. ' + F.TIP_PROOF + '펌프 자리 줄과 질문 2의 줄은 05 · 06단계에서 고른 뒤에 넣습니다. ' + APPROVE_NOTE)],
            prompt=('세 역량 질문의 기대 답 후보를 원자료에서 찾아 근거 줄(파일:줄)과 함께 표로 보여 줘. ' + questions
                    + ' 꼴은 `expected.csv` 빈 틀의 첫 줄을 따르고, 파일은 바꾸지 마. 구성 요소 자리와 실물, 같은 물리량의 범위처럼 내가 정해야 답이 갈리는 줄은 갈래마다 답이 어떻게 달라지는지만 보여 주고 정하지는 마.',
                    '방금 표의 줄 가운데 펌프 자리의 실물 줄과 질문 2의 줄을 뺀 나머지를 `expected.csv`에 적어 줘. 다른 파일은 바꾸지 마.'),
            cmd='python run.py expected', check=ok('화면의 기대 답 표가 내가 받아들인 줄과 같으면 됩니다.'), ai=2),
        section('클래스와 식별자, 관계 방향과 카디널리티 정하기', [
            why('식별자가 겹치면 다른 대상이 하나로 합쳐집니다. 태그 TS1은 네 대에 다 있습니다.'),
            todo('클래스는 설비 · 구성 요소 · 센서 · 부품 · 물리량(센서가 재는 것) 다섯입니다. Codex에게 겹치지 않는 **식별자**, 관계 방향, **카디널리티**(한쪽 하나에 반대쪽이 많아야 몇 개)의 추천안과 까닭을 받아 정하고, `design.csv` · `relations.csv`에 반영하게 합니다. '
                 '부탁에는 목적 · 쓸 자료 · 지킬 조건 · 확인 사례(TS1이 설비마다 따로인지)를 담습니다. ' + F.TIP_REQUEST)],
            prompt='세 역량 질문에 답하는 모델을 만들려고 해. 지금 정한 식별자와 관계 방향 · 카디널리티를 `app/features/design.csv`와 `relations.csv`에 반영해 줘. 같은 이름의 다른 대상이 한 식별자로 합쳐지면 안 돼. 반영한 뒤 TS1이 설비마다 다른 식별자가 되는지 원자료 열로 확인해 줘. 실물 행과 구성 요소-실물 행은 내가 정할 때까지 넣지 말고, 다른 파일은 바꾸지 마.',
            cmd='python run.py design', check=ok('「식별자가 겹치는 원자료 행(이름을 맞추기 전)」 표에 HYD-02 펌프 두 줄만 나오면 됩니다(다음 단계에서 정할 자리). `design.csv`가 이 랩의 스키마입니다.'), ai=3),
        section('새 클래스를 만들지 정하기: 구성 요소 자리와 실물', [
            why('따로 가리켜 물을 대상은 클래스와 인스턴스로, 대상을 설명하는 값은 속성으로 둡니다. HYD-02 펌프 자리를 거쳐 간 펌프까지 물으려면 실물을 따로 두어야 합니다.'),
            todo('Codex에게 두 갈래(일련번호를 속성으로 / 실물을 클래스로)의 질문 1 답과 추천안을 묻고 내 이유로 고릅니다. ' + F.TIP_CHOOSE + ASK_INSTEAD + F.TIP_ASK + DECIDE_NOTE
                 + '그다음 고른 갈래의 펌프 자리 줄을 `expected.csv`에, 표를 고른 대로 맞추게 합니다. 두 요청은 나눕니다. ' + F.TIP_ONE)],
            prompt=(decide_request('구성 요소 자리와 그 실물'),
                    '앞에서 갈래마다 보여 준 후보 가운데 `decisions.csv`에 적은 내 선택(구성 요소 자리와 그 실물)에 맞는 펌프 자리 줄을 `expected.csv` 질문 1에 더해 줘. 다른 파일은 바꾸지 마.',
                    '`decisions.csv`에 적은 내 선택(구성 요소 자리와 그 실물)대로 `row_rules.csv`의 떼어 낸 펌프 줄과 `design.csv` · `relations.csv`를 맞춰 줘. 근거 칸에는 내가 말한 이유를 적어 줘. 판단 함수 파일(.py)과 `expected.csv`는 바꾸지 마.'),
            cmd='python run.py names', check=ok('실물을 따로 두었으면 「구성 요소 자리마다 실물(일련번호)」 표에 HYD-02의 지금 · 지난 펌프가 보입니다. 두지 않았으면 떼어 낸 펌프는 물을 수 없다는 안내가 나옵니다.'), ai=3),
        section('같은 대상으로 볼 범위 정하기: 같은 물리량', [
            why('무엇을 인스턴스 하나로 셀지는 그래프가 답할 질문이 정합니다.'),
            todo('쿨러의 유온과 쿨러 출구 유온처럼 재는 값이 같은 센서를 한 물리량으로 묶을지, 재는 지점마다 나눌지 정합니다. Codex에게 갈래마다 질문 2의 묶음과 HYD-07 현장 지시계가 어디로 가는지 예 줄로 묻고, 골라서 `decisions.csv`에 적게 합니다. '
                 '질문 2 줄을 `expected.csv`에 더하게 한 뒤 `quantity_rules.py`에 구현하게 하고, 그 파일을 열어 내 선택이 든 조건 줄을 봅니다.')],
            prompt=(decide_request('같은 물리량의 범위'),
                    '앞에서 갈래마다 보여 준 후보 가운데 `decisions.csv`에 적은 내 선택(같은 물리량의 범위)에 맞는 질문 2의 묶음 줄과 센서 값 줄을 `expected.csv`에 더해 줘. 물을 값의 물리량 이름은 내가 말한 이름으로 적어 줘. 다른 파일은 바꾸지 마.',
                    '`decisions.csv`에 적은 내 선택(같은 물리량의 범위)을 `quantity_rules.py`의 두 함수에 규칙으로 구현해 줘. 센서를 한 줄씩 이름표로 옮기지 말고 태그 · 재는것 · 붙은곳 입력으로 가르게 해 줘. 서로 다른 묶음에는 다른 이름을 주고, 내가 `expected.csv` 질문 2에 적은 물리량 이름을 써 줘. 다른 파일은 바꾸지 마.'),
            cmd='python run.py quantities', check=ok('「물리량마다 묶인 센서(same_quantity · quantity_name)」 표가 기대 답의 묶음과 같고, 현장 지시계 두 줄이 내가 정한 물리량에 들어갔으면 됩니다.'), ai=3),
        section('식별자와 다른 이름 잇기: 부품과 품번 표기', [
            why('품번 표기마다 부품을 따로 만들면 「이 부품을 어느 설비가 쓰는가」의 답이 흩어집니다.'),
            todo('예전 품번 · 줄여 쓴 표기 · 제조사 품번은 사내 품번의 **다른 이름**으로 남깁니다. 잇는 일과 모델 파일(`output/schema.json` · `graph.json`) 만들기는 아래 명령이 합니다.')],
            cmd='python run.py parts', check=ok('「사내 품번을 찾지 못한 교체부품 칸(잇지 않음)」 표가 비어 있으면 됩니다(「교체부품 칸이 빈 구성 요소(잇지 않음)」 표의 구동 모터 줄은 정상). `output/schema.json`을 열어 내가 정한 클래스 · 관계를 봅니다.'), ai=0),
        section('역량 질문으로 모델 검증하기', [
            why('처음 고른 사례에서만 맞는 규칙이 아닌지 가려야 합니다.'),
            todo('처음 고르지 않은 설비와 예전 품번 · 원자료에 없는 품번도 결과를 보기 전에 `expected.csv`에 더하게 한 뒤 묻습니다. 다른 줄이 나오면 물은 값 · 기대 답 · 실제 답을 함께 보여 원인부터 묻습니다. ' + F.TIP_DIFF + NEW_CHAT + F.TIP_FRESH)],
            prompt=('처음 고르지 않은 설비 하나와 예전 품번 · 원자료에 없는 품번을 원자료에서 골라, 기대 답을 근거 줄과 함께 `expected.csv`에 더해 줘. 다른 파일은 바꾸지 마.',
                    '결과 화면의 「질문별 대조」 표에서 「같음」이 아닌 줄 하나의 물은 값, `expected.csv`의 기대 답과 근거, 실제 답을 견줘 원인을 설명해 줘. 먼저 파일은 바꾸지 마. 원인을 확인하면 그 판단 함수 파일만 고치도록 요청할게.'),
            cmd='python run.py query', check=ok('줄마다 「같음」이거나 차이를 원자료로 설명할 수 있으면 됩니다. 결과에 맞춰 기대 답을 바꾸지 않습니다.'), ai=2,
            followup=[('python run.py check', '「구조 검사 통과」가 보이면 됩니다. 구조 검사는 모양만 보고, 답이 맞는지는 위의 대조가 가립니다.')],
            recovery=[('python run.py parts', '고친 기준으로 모델이 생성됐는지 봅니다.'),
                      ('python run.py query', 'F5를 눌러 고친 질문의 기대 답과 실제 답을 대조합니다.'),
                      ('python run.py check', '구조 검사를 통과하는지 확인합니다.')]),
        closing(section('저장하고 다시 확인하기', [
            why('다시 연 폴더에서 같은 답이 나와야 저장된 것입니다.'),
            todo('폴더를 닫았다 다시 열고 아래 명령을 실행합니다.')],
            cmd='python run.py parts', check=ok('모델이 생성되면 됩니다.'),
            followup=[('python run.py query', 'F5를 눌러 답이 그대로인지 봅니다.')]),
            paragraph(KEEP)
            + paragraph('**내 말로** 두 지점을 왜 그렇게 골랐고 그래서 질문 1 · 2의 줄이 어떻게 나왔는지, 다른 쪽이었다면 무엇이 달라졌을지 말해 봅니다. 내 프로젝트에서도 같은 차례(파악 → 기대 답 먼저 → 갈리는 곳은 내가 고르기 → 질문으로 검증)로 합니다.'))]


def render(title, purpose, steps):
    return F.step_page(title, F.inline(purpose), [(s['name'], s['body']) for s in steps])


GRAPH_QUESTIONS = ('① 설비의 구성 요소마다 어떤 센서가 붙는가? ② 설비의 구성 요소마다 어떤 교체 부품이 들어가는가? '
                   '③ 부품을 어느 설비가 쓰고 그 설비의 상태는 무엇인가? 예전 품번이나 원자료에 없는 품번으로 물으면 어떻게 구별되는가?')


def own_model():
    """선택: 설계 실습에서 만든 내 모델 쓰기(접힌 안내) — Codex는 폴더 밖을 읽지 않으므로 복사는 터미널 명령으로 한다(학생의 입력은 터미널과 Codex뿐)."""
    return ('<details><summary>선택: 설계 실습에서 만든 내 모델을 쓰려면</summary>'
            + paragraph('Codex는 이 폴더 밖을 읽지 않으므로 터미널에서 복사합니다. <설계 실습 폴더>를 내 경로로 바꿔 실행하고, Codex에게 `data/model/graph.json`과 같은 꼴인지 확인받습니다. 다르면 그 폴더를 지우게 하고 제공 모델로 갑니다.')
            + F.command_block('mkdir app\\features\\model -Force; Copy-Item "<설계 실습 폴더>\\output\\schema.json","<설계 실습 폴더>\\output\\graph.json" app\\features\\model\\')
            + '</details>')


def graph(portal_table):
    return [setup('graph-lab', first=False),
        section('랩 DB 준비하기', [
            why('쿼리를 돌릴 이 폴더 전용 그래프 DB가 필요합니다. Docker가 Neo4j 그래프 DB를 컨테이너로 띄웁니다.'),
            todo('Docker Desktop을 켜고 아래 명령을 터미널에서 실행합니다. Codex의 작업 공간은 Docker에 닿지 못하므로, Codex가 실행하려 하면 승인 창에 **Deny**를 누릅니다. 처음 한 번은 이미지를 받느라 오래 걸립니다.')],
            cmd='python run.py db', check=ok('「랩 DB 준비 완료」가 나오고 모델과 랩 DB 개수가 나란히 보이면 됩니다(처음은 0).')),
        section('Codex에게 물어 제공 모델 파악하기', [
            why('적재가 맞았는지 세려면 모델에 무엇이 몇 개 있는지 먼저 압니다.'),
            todo('Codex에게 파일을 바꾸지 말고 `data/model/`의 종류별 수 · 관계 수 · 식별자 짓는 법 · 관계 방향을 예와 원자료 줄로 짚어 달라고 합니다. 화면의 「종류」는 클래스이고 그래프에서는 노드의 **레이블**입니다. 원자료 구성 요소 41줄과 모델 40개가 다른 까닭도 묻습니다. ' + F.TIP_DATA)],
            extra=own_model(), check=ok('01단계 화면의 개수가 Codex의 설명과 같으면 됩니다.'), ai=1),
        section('역량 질문과 기대 답 정하기', [
            why('쿼리 결과를 견줄 기대 답을 결과보다 먼저 정해야, 틀린 결과가 맞아 보이지 않습니다.'),
            todo('이번 **역량 질문** 셋을 Codex에게 알리고 기대 답 후보를 받습니다. ' + GRAPH_QUESTIONS
                 + ' 부탁에는 목적 · 볼 자료 · 지킬 조건 · 확인할 답을 담습니다. ' + F.TIP_REQUEST
                 + '받아들인 줄을 `expected.csv`에 적게 하고 열어 봅니다. ' + F.TIP_PROOF
                 + '볼_열은 쿼리가 돌려줄 열 이름(`tag` · `part` · `asset` · `status` · `note`)이고, 질문 ③의 부품은 수정본에서 상태가 바뀌는 HYD-07도 쓰는 부품으로 고릅니다. ' + APPROVE_NOTE)],
            prompt=('세 역량 질문의 기대 답 후보를 원자료와 제공 모델에서 찾아 근거 줄(파일:줄)과 함께 표로 보여 줘. ' + GRAPH_QUESTIONS + ' 꼴은 `expected.csv` 빈 틀의 첫 줄을 따르고, 볼_열은 tag · part · asset · status · note 가운데 그 줄에 맞는 이름으로 붙여 줘. 질문 3은 수정본을 반영하기 전의 답으로 해 줘. 파일은 바꾸지 마.',
                    '방금 표의 줄을 `expected.csv`에 적어 줘. 다른 파일은 바꾸지 마.'),
            cmd='python run.py expected', check=ok('화면의 기대 답 표가 내가 받아들인 줄과 같으면 됩니다.'), ai=2),
        section('그래프에 남길지 정하기: 불용 결정 설비', [
            why('불용 설비를 남기느냐 지우느냐에 따라 질문 ③의 답과 보전팀이 준비할 예비품이 달라집니다.'),
            todo('수정본(`data/changes/2026-10-20/`)을 Codex에게 물어 파악하고, 상태만 바꿔 남길지 · 그 설비 몫과 함께 지울지 갈래별 결과와 추천안을 받아 내 이유로 고릅니다. ' + F.TIP_CHOOSE + ASK_INSTEAD + F.TIP_ASK
                 + DECIDE_NOTE.replace('아래 명령이', '10단계가'))],
            prompt=decide_request('불용 결정 설비'),
            check=ok('`decisions.csv`의 이 지점 줄에 고른 것과 내 이유가 내 말대로 적혔으면 됩니다.'), ai=2),
        section('스키마를 그래프로 옮기기: 적재와 다시 적재', [
            why('MERGE는 적은 패턴이 있으면 찾고 없을 때만 만들어, 다시 돌려도 늘지 않습니다(CREATE는 늘 새로 만듭니다).'),
            todo('클래스는 레이블, 인스턴스는 노드가 됩니다. 바뀌지 않는 식별자만 MERGE의 패턴에 적고 이름은 SET으로 넣는 적재 쿼리를 `load.cypher`에만 작성하게 합니다(조회 쿼리는 아직). ' + F.TIP_ONE)],
            prompt='MERGE의 패턴에는 바뀌지 않는 식별자(`schema.json`의 식별자)만 적고 이름 같은 값은 SET으로 넣어 `load.cypher`를 구현해 줘. `schema.json`의 종류와 관계 방향을 따르고 행은 $rows로 받아 줘. 종류 · 관계마다 쿼리를 나누고 바로 위에 `// 넣을 것: <종류 또는 관계>`를 적어 줘. 같은 대상을 중복 생성하거나 전체를 지우지 마. 조회 쿼리와 수정 쿼리는 아직 작성하지 마.',
            cmd='python run.py load', check=ok('모델과 랩 DB의 종류별 개수가 같으면 됩니다. MERGE 줄 하나를 열어 패턴과 SET을 봅니다.'), ai=2,
            followup=[('python run.py repeat', '한 번 더 적재해도 개수가 같으면 됩니다. 늘었으면 Codex에게 MERGE의 패턴을 고치게 합니다.')]),
        section('역량 질문을 쿼리로 묻기: 질문 1 구성 요소별 센서', [
            why('MATCH는 관계 유형과 방향을 따라가므로, 방향이 틀리면 결과가 비어 나옵니다.'),
            todo('`query.cypher`의 `// 질문 1`에 설비 코드를 `$` 자리(실행할 때 값을 넣는 자리)로 받아 구성 요소별 센서를 돌려주는 쿼리를 요청합니다. 열 이름은 볼_열(`tag`)로 받습니다.')],
            prompt='`query.cypher`에 질문 1만 작성해 줘. 설비 코드를 $ 자리 하나로 받아 구성 요소와 거기 붙은 센서의 태그(tag) · 물리량 · 단위 · 정상값 · 한계를 돌려줘. 없는 한계를 0으로 채우지 마. 질문 2와 3은 내가 결과를 본 뒤 하나씩 요청할게.',
            cmd='python run.py sensors', check=ok('센서 태그가 기대 답과 같으면 됩니다. MATCH 줄의 화살표 방향을 `schema.json`과 견줍니다. 다르면 물은 값 · 기대 답 · 실제 결과를 함께 보여 원인부터 묻습니다. ' + F.TIP_DIFF + NEW_CHAT + F.TIP_FRESH), ai=1),
        section('질문 2: 구성 요소마다 교체 부품', [
            why('질문 1과 같은 설비에서 시작해, 센서 대신 부품으로 가는 관계만 바꾸면 됩니다.'),
            todo('`// 질문 2`에 구성 요소마다 교체 부품(`part`)을 돌려주는 쿼리를 더하게 합니다.')],
            prompt='`query.cypher`에 질문 2만 더해 줘. 설비 코드를 $ 자리 하나로 받아 그 설비의 구성 요소마다 이어진 교체 부품의 사내 품번(part)과 품명을 돌려줘. 질문 1은 그대로 두고, 질문 3은 내가 결과를 본 뒤 요청할게.',
            cmd='python run.py parts', check=ok('다른 표기로 적힌 교체부품도 사내 품번으로 나오면 됩니다.'), ai=1),
        section('질문 3: 다른 표기로 부품 찾기와 사용 설비', [
            why('결과가 0줄이면 없는 품번인지 쿼리가 틀렸는지 가릴 수 없으므로, 없는 품번은 note로 알리게 합니다.'),
            todo('`// 질문 3`에 다른 표기로도 부품을 찾아 쓰는 설비(`asset`)와 상태(`status`)를 돌려주고, 없는 품번은 `note`에 한 줄로 알리는 쿼리를 더하게 합니다.')],
            prompt='`query.cypher`에 질문 3만 더해 줘. 품번이나 다른 표기를 $ 자리 하나로 받아 사내 품번이나 다른 이름(other_codes)으로 부품을 찾고, 찾은 사내 품번(part), 그 부품을 쓰는 설비 코드(asset)와 상태(status)를 돌려줘. 원자료에 없는 품번이면 note에 원자료에 없는 품번이라고 한 줄 돌려줘. 질문 1 · 2는 그대로 둬.',
            cmd='python run.py usage', check=ok('다른 표기로 물어도 같은 부품이 나오고, 없는 품번이 note로 구별되면 됩니다.'), ai=1),
        section('바뀐 것만 고치기: 수정본 반영', [
            why('전체를 지우고 다시 넣으면 걸린 연결이 끊기므로, 식별자로 찾아 바뀐 값만 고칩니다.'),
            todo('05단계 선택대로 질문 3의 기대 답부터 고치게 하고, 설비마다 있어야 할 구성 요소 · 센서 수를 원자료로 세게 한 뒤, `update.cypher`를 작성하게 합니다.')],
            prompt=('`decisions.csv`의 내 선택(불용 결정 설비)대로 수정본을 반영한 뒤의 답으로 `expected.csv` 질문 3 줄을 고쳐 줘. 다른 파일은 바꾸지 마.',
                    '수정본을 반영한 뒤 설비마다 있어야 할 구성 요소 수와 센서 수를 원자료 줄로 세어 줘. 파일은 바꾸지 마.',
                    '수정본의 줄과 `decisions.csv`의 내 선택(불용 결정 설비)을 `update.cypher`에 반영해 줘. 이름이 바뀐 설비는 식별자를 그대로 두고 이름만 고치고, 전체를 지우지 마. 지우는 범위가 분명하지 않으면 작성하기 전에 물어봐.'),
            cmd='python run.py update', check=ok('바뀐 대상과 개수를 수정본으로 설명할 수 있고, 화면의 두 번째 실행에서 더 바뀐 것이 없으면 됩니다. `update.cypher`의 MATCH · SET 줄을 봅니다.'), ai=3,
            followup=[('python run.py status', '랩 DB의 종류별 개수가 Codex가 센 수와 같으면 됩니다.'),
                      ('python run.py usage', 'F5를 눌러 내 선택이 질문 3에 반영됐는지 봅니다.')]),
        section('포털 기준 지도와 견주기', [
            why('무엇을 인스턴스 하나로 셀지는 답할 질문이 정하므로, 포털 지식 지도(여기서는 기준 지도)와 달라도 모델을 바꾸지 않고 까닭을 압니다.'),
            todo('아래 명령으로 「내 그래프」 표를 띄워 그 아래 기준 지도 표와 쿨러를 어떻게 셌는지부터 견줍니다. 기준 지도의 상태 변수 줄은 내 모델의 물리량 자리이고, CE 센서는 이 원자료 밖입니다.')],
            check=ok('두 표의 차이와 그 까닭을 실제 줄로 말할 수 있으면 됩니다.'), ai=0,
            lead=commands([('python run.py compare', '결과 화면에 「내 그래프」 표가 보이면 아래 기준 지도 표와 견줍니다.')]) + '<div style="overflow-x:auto">' + portal_table + '</div>'),
        closing(section('저장하고 다시 확인하기', [
            why('다시 연 폴더에서 같은 결과가 나와야 저장된 것입니다.'),
            todo('폴더를 닫았다 다시 열고 아래 명령으로 랩 DB를 켭니다.')],
            cmd='python run.py db',
            check=ok('같은 랩 DB가 열리면 됩니다. 새 랩 DB를 만들었다고 나오면 접힌 안내의 적재 · 수정을 먼저 실행합니다.'),
            when_new=[('python run.py load', '넣은 개수가 모델과 같은지 봅니다.'),
                      ('python run.py update', '수정본과 내 선택이 반영됐는지 봅니다.')],
            followup=[('python run.py usage', 'F5를 눌러 결과가 그대로인지 봅니다.'),
                      ('python run.py export', '랩 DB의 그래프를 `output/schema.json` · `graph.json`으로 저장합니다.'),
                      ('python run.py check', '「구조 검사 통과」가 보이면 됩니다. 구조 검사는 모양만 봅니다.')]),
            paragraph(KEEP)
            + paragraph('**내 말로** 불용 설비를 왜 그렇게 처리했고 질문 ③이 어떻게 나왔는지, 다시 적재해도 늘지 않은 까닭(MERGE의 패턴), 기준 지도와 식별자가 다른 까닭을 말해 봅니다. 다음 회차에는 이 설비 모델에 작업 절차와 판단 조건을 잇습니다.'))]
