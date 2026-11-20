# 2회차 실습 04 관계조회(통합반 2회차 04 · 실전반 2회차 05 공통, 2026-11 새로 찍는 판)의 큐 JSON을 대본 표에서 만든다. 손으로 고치지 않는다.
#   <py> 통합_02_04_관계조회_큐만들기.py [<대본.md>]  → 같은 폴더의 통합_02_04_관계조회_큐.json
#   <py> 통합_02_04_관계조회_큐만들기.py --고르기 <처음 큐>-<끝 큐> <출력.json>  → 그 범위(표의 차례 기준)의 큐만 담은 사본(git 밖에 둔다)
#     대표 구간(영상 길 14)처럼 일부만 찍을 때 쓴다. 녹화기는 찍는 큐마다 음성이 있어야 하므로 산 큐만 담은 사본을 준다. 조작은 전체 큐와 같다.
#   대본을 주지 않으면 산출물/통합반/실습/02회차/대본/04_실습_관계조회.md를 읽는다.
# 대본 「## 절」 하나가 구간 하나이고, 표의 한 줄(| gNNNN | 발화 | 조작 |)이 큐 하나다. 글은 발화 칸 그대로다.
# 쉼(gap, ms — 앞 말과 앞 조작이 끝난 뒤 이 말을 시작할 때까지, 영상 V-14)은 앞 큐 조작 칸의 「쉼: <이름> <초>」이고 첫 큐는 0.3초다.
#   앞 큐의 글이 끝맺음 없이 끝났는데 「잇기」가 아니거나, 절의 마지막 큐인데 「구간」이 아니면 멈춘다.
# 조작은 아래 표(OPS: 큐 id → 걸음들)이고, 붙여 넣는 쿼리는 칸 원고 통합반_관계조회_칸.json에서 읽는다(안내 문서의 칸 번호 = 칸 원고의 차례 + 앞의 명령 칸 둘).
#   걸음의 시점은 발화 속 구절이다(그 구절이 시작하는 글자 비율 — 녹화기가 큐 시작 + 말 길이 × 비율에 한다). 구절을 주지 않은 걸음은 앞 걸음에 바로 잇는다.
#   발화에 없는 구절, 거꾸로 된 시점, 표에 없는 큐, 대본에 없는 큐의 조작이 있으면 그 큐 id를 대며 멈춘다.
# 강조(영상 V-14 · V-11): 조작 칸에서 짚는 대상 뒤의 (밑줄) · (띠) · (테두리)마다 그 짚기에 hl(underline · band · box)을 준다.
#   큐마다 조작 칸의 모양 표시 수와 hl 수가 모양별로 같아야 하고, 다르면 그 큐 id를 대며 멈춘다. 함께 짚는 대상(also)은 강조 하나다.
# 조작 꼴은 record_graph_lesson.mjs 머리말(mark · press · runCard · gShow · gCopy · mainShow · paste · tour · fit), 대상 꼴은 mark_targets.mjs 머리말.
#   대상은 길뚫기(2026-11-20 이 PC, Neo4j 5.26 Browser — 근거 폴더 길뚫기/04_길뚫기.md)로 찾았다.
import json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PICK = sys.argv[2:4] if sys.argv[1:2] == ['--고르기'] else None
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not PICK else ROOT / 'workspace/강의제작/산출물/통합반/실습/02회차/대본/04_실습_관계조회.md'
CELLS_FILE = HERE / '통합반_관계조회_칸.json'
OUT = HERE / '통합_02_04_관계조회_큐.json'
VOICE, MODEL = 'tlxL9ilynpbOVf9sZXKh', 'eleven_v4'      # 영상 V-4
GAP_NAMES = {'잇기': 0.6, '큐': 1.3, '결과 뒤': 2.0, '구간': 2.3}      # 영상 V-14 실습 값
SHAPES = {'밑줄': 'underline', '띠': 'band', '테두리': 'box'}
FIRST_GAP = 300
SHELL_BLOCKS = 2      # 안내 문서에서 쿼리 칸 앞에 오는 명령 칸(prepare_example.py · lab_db.py) 수
REST = {'x': 1180, 'y': 113}      # 붙여 넣은 뒤 화살표를 두는 자리(입력칸 첫 줄 오른쪽 빈 곳 — 가장 긴 쿼리 줄도 여기까지 오지 않는다)

_cells = json.loads(CELLS_FILE.read_text(encoding='utf-8'))['cells']
QUERY = {c['id']: c['query'] for c in _cells}
BLOCK = {c['id']: i + SHELL_BLOCKS for i, c in enumerate(_cells)}

# ── 대상
INST = '[data-testid="instance-menu-button"]'
DBB = '[data-testid="database-menu-button"]'
RUNB = '[data-testid="run-button"]'
PORT = {'css': INST, 'inner': 'bolt://', 'match': r'\d+$'}      # 연결 주소 끝 숫자(PC마다 다르다)
ADDR = {'css': INST, 'inner': 'bolt://', 'match': r'bolt://[\d.:]+'}      # 맨 위 Instance 옆 연결 주소 전체
DIALOG_ADDR = {'css': '[role="dialog"]', 'inner': 'bolt://127.0.0.1:'}      # 연결 창 제목 아래에 크게 적힌 주소(lab_db.py가 늘 127.0.0.1로 연다)
HEADING = 'h1,h2,h3,h4,h5,h6,[role="heading"]'
DBNAME = {'css': DBB, 'inner': 'Database:neo4j'}


def ED(s, **k): return {'ed': s, **k}                     # 입력칸의 글 조각
def EL(n): return {'edLine': n}                           # 입력칸의 그 줄 전체
def ROW(n, **k): return {'row': n, **k}
def HAS(s, **k): return {'rowHas': s, **k}
def COL(s, **k): return {'col': s, **k}
def CELL(r, c, **k): return {'cell': [r, c], **k}
def NODE(s): return {'node': s}
def EDGE(a, b): return {'edge': [a, b]}
def DET(s): return {'det': s}
def FOOT(s): return {'foot': s}
def CSS(s, **k): return {'css': s, **k}
def WITH(t, *more, **k): return {**t, 'also': list(more), **k}      # 함께 짚는 대상


# ── 걸음
def U(t, at=None): return ('mark', t, at, 'underline')
def B(t, at=None): return ('mark', t, at, 'band')
def X(t, at=None): return ('mark', t, at, 'box')
def MV(t, at=None): return ('mark', t, at, None)          # 강조 없이 화살표만
def PRESS(t, at, expect=None, point=None): return ('press', t, at, expect, point)
def RUN(at=None, **want): return ('run', at, want)        # at이 없으면 말이 끝날 때
def OP(op, at=None, **k): return ('op', op, at, k)


def PASTE(cell, show, copy=None, back=None):
    """안내 문서 탭 → 그 칸 [복사] → Neo4j Browser 탭 → 입력칸에 붙여 넣기. show · copy · back = 그 걸음을 시작할 발화 속 구절."""
    return [('gshow', cell, show), ('gcopy', cell, copy), OP('mainShow', back), ('paste', cell, None)]


PUMP, FAN, S_OLD, S_NEW = '연습 펌프', '연습 팬', '연습 온도 센서', '연습 유온 센서'
COMPS, PARTS = ['오일 쿨러', '주 펌프 (A)', '쿨러 팬'], ['쿨러 코어', '펌프 축 씰 키트', '팬 베어링']
PAREN_A = "(:연습장치 {id:'basic-A', name:'연습 펌프', score:40})"
PAREN_B = "(:연습장치 {id:'basic-B', name:'연습 팬', score:70})"
PATH_6_1 = "(p:연습장치 {id:'basic-A'})-[r:감시된다]->(s:연습센서 {id:'basic-S1'})"
PATH_10_1 = "(:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(:Part)"

OPS = {
 # 1. 여는 말 — 연결 창. 화살표는 연결 창 오른쪽 빈 곳(설정의 pointer)
 'g0106': [X(CSS('[role="dialog"]', clip=True), '이 연결 창이')],
 # 2. 연결
 'g0201': [X(WITH(CSS('input[name="hostname"]'), CSS('input[name="username"]')), '주소와 사용자 이름이'), U(DIALOG_ADDR, '위쪽에 크게 적힌'), X(CSS('input[name="password"]'), '비밀번호 칸은'),
           PRESS(CSS('button', text='Connect'), '누르세요', {'css': '[data-testid="connection-status-indicator-success"]', 'button': 'Dismiss'}, 'Connect를')],
 'g0202': [OP('tour', '닫으시면', button='Dismiss')],
 'g0203': [MV(CSS(INST, under=True))],
 'g0204': [X(CSS(INST, inner='Instance:bolt://'), '맨 위, Instance라고'), U(PORT, '끝의 숫자는')],
 'g0206': [U(DBNAME, '그 옆에 Database라고'), U(ADDR, '주소로 구분합니다')],
 'g0205': [X(CSS('[data-testid="frame"]', contains=':welcome', clip=True))],
 # 3. 무엇이 들어 있나 — 왼쪽 패널
 'g0301': [X(CSS(HEADING, text='Queries'), '왼쪽에는 Queries라고'), PRESS(CSS('button[aria-label="Database overview"]'), '누르시면', {'css': 'button[aria-label="All Nodes"]'}, '맨 왼쪽')],
 'g0302': [X(CSS('h3', contains='Nodes (20)'), '노드가'), X(CSS('h3', contains='(19)'), '관계가')],
 'g0303': [X(CSS('[aria-label="Run query for node labels"]'), '색깔 단추들이'), X(CSS('button[title="Asset"]'), '설비가 Asset'), X(CSS('button[title="Component"]'), '구성 요소가 Component'),
           X(CSS('[aria-label="Run query for relationship types"]'), '그 아래 단추들은'), X(CSS('[aria-label="Run query for property keys"]'), '맨 아래 단추들은')],
 'g0304': [PRESS(CSS('button[title="Collapse Sidebar"]'), '이 단추로', {'css': 'button[title="Open Sidebar"]'}, 'Stream이라고')],
 # 4. CREATE
 'g0401': [('gshow', '2-1', '옆 탭의'), X(CSS('#s2 h2'), '2번'), X(CSS('.block pre', nth=BLOCK['2-1']), '칸 아래'), ('gcopy', '2-1', '누르고')],
 'g0402': [OP('mainShow', '이쪽으로'), ('paste', '2-1', '위쪽 입력칸에')],
 'g0403': [U(ED('CREATE'), '맨 앞의 CREATE'), U(ED(PAREN_A), '둥근 괄호가'), U(ED(PAREN_B), '괄호 하나가')],
 'g0404': [U(ED(':연습장치', line=1), '쌍점이 있죠'), U(ED(':연습장치', line=2), '우리 것은')],
 'g0407': [U(ED("{id:'basic-A', name:'연습 펌프', score:40}"), '중괄호 안이'), U(ED("name:'연습 펌프'"), '쌍점 왼쪽이'), U(ED("id:'basic-A', name:'연습 펌프', score:40"), '아이디와 이름'),
           U(ED('score:40'), '점수는 조금')],
 'g0408': [U(ED("'연습 펌프'"), '글자로 된 값은'), U(ED('40'), '숫자는'), U(ED(';'), '맨 끝의 세미콜론은')],
 'g0405': [MV(CSS(RUNB), '입력칸 오른쪽 끝의'), RUN('누르면', summary='Created 2 nodes')],
 'g0406': [U(FOOT('Created 2 nodes'), '노드 두 개를'), U(FOOT('set 6 properties, added 2 labels'), '속성 여섯 개를')],
 # 5. MATCH · RETURN, 그림과 표
 'g0501': PASTE('3-1', '안내 문서 3번의', '가져옵니다', '앞으로도'),
 'g0502': [U(ED('MATCH'), '첫 줄 MATCH는'), U(ED('연습장치'), '쌍점 뒤에'), U(ED('(n:', sub=[1, 1]), '글자가 하나 있죠')],
 'g0511': [U(ED('RETURN'), '둘째 줄 RETURN은'), U(ED('RETURN n', sub=[7, 1]), '변수 하나만')],
 'g0513': [X(CSS(RUNB, under=True), '입력칸 옆의'), X({'cardRun': True, 'under': True}, '아래 결과에'), RUN(graph=True, nodes=2, edges=0)],
 'g0503': [X(NODE(PUMP), '방금 만든 펌프와'), X(NODE(FAN), '팬이고'), MV({'mid': [PUMP, FAN]}, '선은 없어요')],
 'g0504': [X(NODE(PUMP), '원 안에는'), PRESS(NODE(PUMP), '눌러 보세요', {'details': 'basic-A'}, '펌프를')],
 'g0505': [X({'detChip': True}, '맨 위 색깔 이름표가'), B(WITH(DET('id'), DET('name'), DET('score')), '아이디와 이름'), B(DET('<id>'), '표 맨 윗줄')],
 'g0506': [X(WITH({'tab': 'Graph'}, {'tab': 'Table'}), 'Graph와 Table이'), PRESS({'tab': 'Table'}, '누르면', {'tab': 'Table', 'rows': 2}, 'Table을 누르면')],
 'g0507': [B(WITH(ROW(1), ROW(2)), '찾은 노드 하나가'), B({'colHead': 'n'}, '표 머리의 글자는'), U({'head': 'RETURN n'}, 'RETURN에 적은'),
           PRESS({'tab': 'Graph'}, 'Graph를 누르면', {'tab': 'Graph', 'css': '[data-testid="nvl-c2d-canvas"]'})],
 'g0508': PASTE('3-2', '다음 칸은', '같은 노드에서', '이름과 점수만'),
 'g0509': [U(EL(2), 'RETURN 줄이'), U(ED('n.name'), '변수에 점을 찍고'), U(ED('n.score'), '찾은 노드의 점수')],
 'g0512': [U(WITH(ED('AS 이름'), ED('AS 점수')), 'AS는 받은'), U(ED('ORDER BY 점수'), '마지막 줄 ORDER BY는'), RUN(rows=2)],
 'g0510': [B({'headRow': True}, '표 머리에는'), B(COL('점수'), '점수가 작은'), X(WITH({'tab': 'Table'}, {'tab': 'Raw'}), '그림은 노드나')],
 # 6. WHERE
 'g0601': PASTE('4-1', '4번 칸을'),
 'g0602': [U(EL(2), '가운데 줄이'), U(ED('>='), '크다는 표시와'), U(ED('50'), '50 이상인'), RUN(graph=True, nodes=1, edges=0)],
 'g0603': [X(NODE(FAN))],
 # 7. MERGE · SET
 'g0701': PASTE('5-1', '5번의 첫 칸'),
 'g0702': [U(ED('MERGE'), 'MERGE는 적은'), U(ED("(s:연습센서 {id:'basic-S1'})"), '패턴은 괄호로')],
 'g0708': [U(ED(':연습센서'), '레이블은 센서용으로'), U(ED("id:'basic-S1'"), '중괄호 안에는')],
 'g0707': [U(ED('SET'), '맨 앞에 적힌 SET이'), U(ED("s.name = '연습 온도 센서'"), '변수에 점을 찍어'), U(ED("s.unit = '℃'"), '쉼표 뒤는')],
 'g0703': [U(ED("id:'basic-S1'"), '괄호 안에 적은 것이 전부'), U(ED("'연습 온도 센서'"), '이름까지 넣어 두면'), U(ED("id:'basic-S1'"), '아이디만 적어 두면'),
           RUN(graph=True, nodes=1, edges=0, summary='Created 1 node')],
 'g0704': [X(NODE(S_OLD), '센서 노드가'), U(FOOT('Created 1 node'), '아래 글에도')],
 'g0705': [*PASTE('5-2', '다음 칸은'), X({'edAll': True, 'under': True}, 'CREATE였다면'), RUN('돌려 봅니다', graph=True, nodes=1, edges=0, summary='Set 2 properties')],
 'g0706': [U(FOOT('Set 2 properties'), '아래 글을'), X(NODE(S_OLD), '노드는 이미')],
 # 8. 관계 잇기
 'g0801': PASTE('5-3', '5번의 마지막 칸'),
 'g0802': [U(WITH(EL(1), EL(2)), '위 두 줄이'), U(WITH(ED('(p:', sub=[1, 1]), ED('(s:', sub=[1, 1])), '괄호 맨 앞을 보면'), U(WITH(ED('(p)'), ED('(s)')), '양 끝 괄호에는')],
 'g0805': [U(ED('-[r:감시된다]->'), '빼기 표시와'), U(ED('[r:', sub=[1, 1]), '쌍점 앞은'), U(ED(':감시된다'), '쌍점 뒤가')],
 'g0803': [U(ED('MERGE'), '관계도 MERGE로'), U(ED('RETURN p, r, s'), '마지막 줄 RETURN에는'), RUN(graph=True, nodes=2, edges=1)],
 'g0804': [X(EDGE(PUMP, S_OLD), '화살표가 하나'), X({'edgeLabel': '감시된다'}, '선 위에'),
           X(CSS('[data-testid="frame"]', contains='Created 1 relationship', inner='감시된다(1)'), '오른쪽 목록에도'), X(WITH(NODE(PUMP), NODE(S_OLD)), '두 원의 색이')],
 # 9. SET으로 고치기
 'g0901': PASTE('6-1', '6번 칸이에요'),
 'g0902': [U(ED(PATH_6_1), '괄호와 화살표를'), U(EL(2), '둘째 줄 SET이'), U(ED('RETURN p, r, s'), '마지막 줄은'), RUN(graph=True, nodes=2, edges=1)],
 'g0903': [X(NODE(S_NEW), '센서 이름이'), X(EDGE(PUMP, S_NEW), '펌프와 이어진 선은'), PRESS(NODE(S_NEW), '눌러 보면', {'details': 'basic-S1'}, '센서를')],
 'g0904': [B(WITH(DET('id'), DET('unit')), '아이디와 단위는'), B(DET('name'), '이름만')],
 # 10. 지우기
 'g1001': [U(ADDR, '맨 위 주소가')],
 'g1002': PASTE('7-1', '7번의 첫 칸'),
 'g1003': [U(ED('DELETE'), '지우는 절은 DELETE'), U(ED('DETACH'), '앞에 DETACH가'), X(EDGE(PUMP, S_NEW), '센서로 가는 관계가'), X(NODE(PUMP), '펌프만 지우면')],
 'g1004': [U(ED('DETACH DELETE'), 'DETACH DELETE는'), RUN(summary='Deleted 1 node, deleted 1 relationship')],
 'g1005': [U(FOOT('Deleted 1 node, deleted 1 relationship')), *PASTE('7-2', '그래서')],
 'g1006': [U(WITH(ED('연습장치'), ED('연습센서')), '장치에 붙인 레이블과'), U(ED('|'), '레이블 사이의 세로줄이'), RUN(graph=True, nodes=2, edges=0)],
 'g1007': [X(NODE(FAN), '팬과'), X(NODE(S_NEW), '센서,')],
 'g1008': PASTE('7-3', '남은 둘은'),
 'g1009': [U(ED('DELETE n'), 'DELETE를'), U(ED('연습장치|연습센서'), '레이블이 달라서'), RUN(summary='Deleted 2 nodes')],
 'g1010': [U(FOOT('Deleted 2 nodes')), *PASTE('7-4', '이번에도')],
 'g1011': [U(ED('count'), 'count로 세어'), U(ED('(n)'), '뒤에 붙은 괄호는'), RUN(rows=1)],
 'g1012': [B(ROW(1))],
 # 11. 설비 데이터 — 레이블마다 세기
 'g1102': PASTE('8-1', '8번 칸은'),
 'g1103': [U(ED('MATCH (n)'), 'MATCH의 괄호에'), U(ED('count(n)'), 'count 앞에'), U(ED('labels(n)'), 'labels가')],
 'g1106': [U(WITH(ED('labels(n)'), ED('count(n)')), '옆에 레이블을 함께'), U(ED('DESC'), 'DESC를 붙이면'), RUN(rows=5)],
 'g1107': [B(COL('레이블'))],
 'g1104': [B(HAS('Component'), '구성 요소인'), B(HAS('Sensor'), '센서가 다섯'), B(HAS('Part'), '부품인 Part'), B(HAS('Asset'), '설비인 Asset'), B(HAS('StateVariable'), 'StateVariable은')],
 'g1105': [B(COL('개수'))],
 # 12. 한 단계
 'g1201': PASTE('9-1', '9번 칸으로'),
 'g1202': [U(ED("{code:'HYD-01'}"), '첫 괄호는'), U(ED('-[:HAS_COMPONENT]->'), '가진다는 관계'), U(ED('RETURN c.name'), '구성 요소의 이름을'), U(WITH(ED('(:'), ED('[:')), '쌍점 앞이 비어'), RUN(rows=6)],
 'g1203': [B(COL('구성요소'), '여섯 행이'), B(WITH(HAS('작동유 탱크'), HAS('구동 모터')), '탱크와 모터'), B(WITH(HAS('예비 펌프 (B)'), HAS('주 펌프 (A)')), '펌프 둘'),
           B(WITH(HAS('쿨러 팬'), HAS('오일 쿨러')), '그리고 쿨러 팬과')],
 'g1204': [U({'head': '-[:HAS_COMPONENT]->'}, '관계를 한 번 건너서')],
 # 13. 두 단계 경로
 'g1301': PASTE('10-1', '10번 첫 칸은'),
 'g1302': [U(ED('-[:USES_PART]->(:Part)'), '화살표와 괄호가'), U(ED(PATH_10_1), '줄줄이 이어진 길을')],
 'g1303': [U(WITH(ED('(:Component)'), ED('(:Part)')), '괄호 안에 변수가 없고'), U(ED('path ='), '패턴 맨 앞에'), U(ED('RETURN path'), 'RETURN에 그 변수를'), RUN(graph=True, nodes=7, edges=6)],
 'g1304': [X(NODE('HYD-01'), '설비에서'), X(WITH(*map(NODE, COMPS)), '구성 요소 셋으로'), X(WITH(*map(NODE, PARTS)), '부품 셋으로')],
 'g1305': [X(CSS('[data-testid="frame"]', contains='RETURN path', inner='Component(3)'), '그림에는 셋만'), X(WITH(*map(NODE, COMPS)), '부품까지 이어진')],
 'g1306': PASTE('10-2', '오일 쿨러에'),
 'g1307': [U(WITH(ED('(c:', sub=[1, 1]), ED('(pt:', sub=[1, 2])), '변수가 하나씩'), U(EL(2), 'WHERE에는'), U(WITH(ED('pt.name AS 부품'), ED('pt.partNo AS 품번')), '부품의 이름과 품번을'), RUN(rows=1)],
 'g1308': [B(CELL(1, '부품'), '쿨러 코어고'), B(CELL(1, '품번'), '이 값이에요')],
 # 14. 원래 행 · 조건 · 집계
 'g1401': PASTE('11-1', '11번의 첫 칸'),
 'g1402': [U(ED('-[:MONITORED_BY]->'), 'MONITORED_BY를'), U(EL(2), 'RETURN에는'), U(ED('s.virtual AS 가상'), '가상이라는 속성을'), RUN(rows=5)],
 'g1403': [B(WITH(ROW(1), ROW(2)), '오일 쿨러가 두 행'), B(WITH(ROW(3), ROW(4)), '주 펌프가 두 행'), B(ROW(5), '쿨러 팬이 한 행')],
 'g1404': [B(COL('가상')), B(ROW(1), '냉각 효율은')],
 'g1405': [B(ROW(1), '첫 행 하나가'), B(WITH(ROW(2), ROW(3), ROW(4), ROW(5)), '아래 네 행이')],
 'g1406': [*PASTE('11-2', '다음 칸은'), U(EL(2), '가상이 false인'), RUN(rows=4)],
 'g1407': [B(WITH(ROW(1), ROW(2), ROW(3), ROW(4)), '네 행이 나왔고'), B(COL('가상'), '가상 열이'), B(ROW(1, card=1), '맨 위 냉각 효율')],
 'g1408': PASTE('11-3', '다음은 세는 쿼리'),
 'g1409': [U(WITH(ED('c.name AS 구성요소'), ED('count(s)')), '구성 요소 이름과 count를'), U(ED('collect(s.name)'), '옆의 collect는'), RUN(rows=3)],
 'g1410': [B(COL('센서수')), B(COL('센서목록'), '오른쪽 목록에는'), B(ROW(1), '이름을 세어 보면')],
 'g1411': [B(CELL(1, '센서수'), '오일 쿨러 행의 숫자'), B(CELL(1, '센서목록', phrase='냉각 효율 (가상)'), '냉각 효율까지')],
 'g1412': [B(COL('구성요소'))],
}


def rows(md):
    """대본 본문(# 촬영 본문 끝 앞)의 절과 큐 줄 → [(구간 번호, 절 이름, 큐 id, 발화, 조작 칸)]."""
    body, out, seg, name = md.split('# 촬영 본문 끝', 1)[0], [], 0, ''
    for line in body.splitlines():
        if line.startswith('## '):
            seg, name = seg + 1, line[3:].strip()
            continue
        m = re.match(r'\| (g\d{4}) \| (.+?) \| (.+) \|$', line)
        if m:
            out.append((seg, name, m.group(1), m.group(2).strip(), m.group(3).strip()))
        elif line.startswith('| g'):
            sys.exit(f'읽지 못한 큐 줄: {line[:40]}')
    return out


def steps_to_ops(cid, text, steps):
    """걸음 목록 → 녹화기 조작 목록. 시점 구절을 글자 비율로 바꾸고, 이어진 짚기는 mark 하나로 묶는다."""
    ops, last = [], 0.0

    def frac(phrase, default=None):
        nonlocal last
        if phrase is None:
            f = last if default is None else max(last, default)
        else:
            if text.count(phrase) == 0:
                sys.exit(f'{cid}: 발화에 없는 구절 「{phrase}」')
            f = round(text.index(phrase) / len(text), 4)
            if f < last:
                sys.exit(f'{cid}: 조작 시점이 거꾸로 — 「{phrase}」')
        last = f
        return f

    for s in steps:
        kind = s[0]
        if kind == 'mark':
            _, t, at, hl = s
            point = {**t, 'at': frac(at, 0.02), **({'hl': hl} if hl else {})}
            if ops and ops[-1]['op'] == 'mark':
                ops[-1]['points'].append(point)
            else:
                ops.append({'op': 'mark', 'points': [point]})
        elif kind == 'press':
            _, t, at, expect, point = s
            pa = frac(point) if point else None
            a = frac(at)
            ops.append({'op': 'press', **t, 'at': a, 'point_at': pa if pa is not None else max(0.0, round(a - 0.12, 4)), **({'expect': expect} if expect else {})})
        elif kind == 'run':
            _, at, want = s
            ops.append({'op': 'runCard', 'at': frac(at, 0.97), **want})
        elif kind == 'gshow':
            ops.append({'op': 'gShow', 'block': BLOCK[s[1]], 'query': QUERY[s[1]], 'at': frac(s[2])})
        elif kind == 'gcopy':
            before = last
            a = frac(s[2])
            ops.append({'op': 'gCopy', 'block': BLOCK[s[1]], 'at': a, 'point_at': before})
        elif kind == 'paste':
            ops.append({'op': 'paste', 'query': QUERY[s[1]], 'at': frac(s[2]), 'rest': REST})
        elif kind == 'op':
            _, op, at, k = s
            ops.append({'op': op, 'at': frac(at), **k})
        else:
            sys.exit(f'{cid}: 모르는 걸음 {kind}')
    return ops


def hl_count(ops):
    return Counter(p['hl'] for o in ops if o['op'] == 'mark' for p in o['points'] if p.get('hl'))


def build(md):
    rs, cues = rows(md), []
    ids = [r[2] for r in rs]
    if len(set(ids)) != len(ids):
        sys.exit(f'대본에 큐 id가 겹친다: {[i for i, n in Counter(ids).items() if n > 1]}')
    if set(OPS) - set(ids):
        sys.exit(f'대본에 없는 큐의 조작: {sorted(set(OPS) - set(ids))}')
    gap_after = None
    for k, (seg, name, cid, text, note) in enumerate(rs):
        ops = steps_to_ops(cid, text, OPS.get(cid, []))
        want = Counter({en: note.count(f'({ko})') for ko, en in SHAPES.items() if note.count(f'({ko})')})
        got = hl_count(ops)
        if want != got:
            sys.exit(f'{cid}: 조작 칸의 모양 표시 {dict(want)}와 큐의 hl {dict(got)}가 다르다')
        if not ops and not re.search(r'조작 없음', note):
            sys.exit(f'{cid}: 조작 칸에 조작이 적혀 있는데 조작 표(OPS)에 이 큐가 없다')
        cues.append({'id': cid, 'segment': seg, 'section': name, 'text': text, 'gap': FIRST_GAP if gap_after is None else gap_after, 'ops': ops or [{'op': 'none'}]})
        last_of_all, last_of_seg = k == len(rs) - 1, k == len(rs) - 1 or rs[k + 1][0] != seg
        m = re.search(r'쉼: (잇기|큐|결과 뒤|구간) ([\d.]+)', note)
        if last_of_all:
            if m:
                sys.exit(f'{cid}: 마지막 큐에 쉼이 적혀 있다')
            continue
        if not m:
            sys.exit(f'{cid}: 조작 칸에 「쉼: <이름> <초>」가 없다')
        kind, secs = m.group(1), float(m.group(2))
        if GAP_NAMES[kind] != secs:
            sys.exit(f'{cid}: 쉼 「{kind} {secs}」가 영상 V-14의 값 {GAP_NAMES[kind]}와 다르다')
        joined = not re.search(r'[.?!]["」』]?$', text)
        if joined != (kind == '잇기'):
            sys.exit(f'{cid}: 글이 끝맺음 {"없이" if joined else "으로"} 끝나는데 쉼이 「{kind}」다(끝맺음 없이 끝나는 큐만 잇기 — 영상 V-14)')
        if last_of_seg != (kind == '구간'):
            sys.exit(f'{cid}: 절의 {"마지막" if last_of_seg else "가운데"} 큐인데 쉼이 「{kind}」다')
        gap_after = round(secs * 1000)
    return cues


def write(path, doc):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')


def main():
    cues = build(SRC.read_text(encoding='utf-8'))
    order = [c['id'] for c in cues]
    if PICK:
        a, z = PICK[0].split('-')
        if a not in order or z not in order or order.index(a) > order.index(z):
            sys.exit(f'--고르기 범위가 큐 차례에 없다: {PICK[0]}')
        part = cues[order.index(a):order.index(z) + 1]
        write(PICK[1], {'voice_id': VOICE, 'model_id': MODEL, 'note': f'{OUT.name}의 {PICK[0]} 사본(--고르기)', 'cues': part})
        print(f'{PICK[0]}: 큐 {len(part)} · 구간 {sorted({c["segment"] for c in part})} · 글자 {sum(len(c["text"]) for c in part)} → {PICK[1]}')
        return
    write(OUT, {'voice_id': VOICE, 'model_id': MODEL,
                'note': f'2회차 실습 04 관계조회(통합반 2회차 04 · 실전반 2회차 05 공통). {SRC.name}에서 {Path(__file__).name}로 만든다 — 손으로 고치지 않는다. '
                        '녹화기 record_graph_lesson.mjs(대상 찾기 mark_targets.mjs). gap은 앞 말과 앞 조작이 끝난 뒤 이 말을 시작할 때까지의 ms(영상 V-14).',
                'cues': cues})
    total = Counter()
    by = {}
    for c in cues:
        by.setdefault((c['segment'], c['section']), []).append(c)
        total += hl_count(c['ops'])
    for (n, name), cs in by.items():
        print(f'구간 {n} {name}: 큐 {len(cs)} · 강조 {sum(sum(hl_count(c["ops"]).values()) for c in cs)} · 글자 {sum(len(c["text"]) for c in cs)}')
    print(f'모두 큐 {len(cues)} · 구간 {len(by)} · 강조 {sum(total.values())}(밑줄 {total["underline"]} · 띠 {total["band"]} · 테두리 {total["box"]}) · 글자 {sum(len(c["text"]) for c in cues)} → {OUT.name}')


if __name__ == '__main__':
    main()
