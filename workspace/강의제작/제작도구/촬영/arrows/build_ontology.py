"""ARROWS 실습 원본: 교재 SLIDE 67·73·74의 쿨러 지식 그래프를 arrows.app에서 그리는 큐(발화+조작).
이 파일 하나가 음성 목록·촬영 조작·수업 원고·두 과정 랩 산출물의 원본이다. 앱·음성 API는 호출하지 않는다.
사용: python build_ontology.py cues <cues.json 출력 경로>   # 촬영용 큐
      python build_ontology.py sync                       # 수업원고·시간·두 과정 대본/랩/가이드/ZIP 동기화
"""
import json, re, sys
from pathlib import Path

# 원: Caption, Label. 이름·관계는 it/neo4j/v2/instances.cypher와 랩 HM-8 발췌를 따른다. 배치는 촬영 중 화면을 보고 정한다.
NODES = [
    ('HYD-01 유압 파워팩', 'Asset'),
    ('오일 쿨러', 'Component'),
    ('유온 센서 TS1', 'Sensor'),
    ('유온 상승', 'Symptom'),
    ('쿨러 냉각 성능 상실', 'FailureMode'),
    ('쿨러 핀 오염', 'Cause'),
    ('팬 최대 운전', 'Skill'),
    ('쿨러 핀 세척', 'Skill'),
    ('HM-8.5 즉시 완화 조치', 'ManualSection'),
    ('HM-8.7 근본 조치', 'ManualSection'),
    ('팬 구동 불량', 'Cause'),
    ('팬 점검', 'Skill'),
    ('HM-8.1 팬 벨트 점검', 'ManualSection'),
    ('주변 온도 상승', 'Cause'),
    ('캐비닛 환기 보강', 'Skill'),
    ('팬 베어링 열화', 'FailureMode'),
    ('진동 증가', 'Symptom'),
]
RELS = [
    ('HYD-01 유압 파워팩', 'HAS_COMPONENT', '오일 쿨러'),
    ('오일 쿨러', 'MONITORED_BY', '유온 센서 TS1'),
    ('유온 상승', 'OBSERVED_BY', '유온 센서 TS1'),
    ('유온 상승', 'INDICATES', '쿨러 냉각 성능 상실'),
    ('쿨러 냉각 성능 상실', 'OCCURS_IN', '오일 쿨러'),
    ('쿨러 핀 오염', 'CAUSES', '쿨러 냉각 성능 상실'),
    ('쿨러 냉각 성능 상실', 'MITIGATED_BY', '팬 최대 운전'),
    ('쿨러 냉각 성능 상실', 'REMEDIED_BY', '쿨러 핀 세척'),
    ('쿨러 핀 세척', 'ADDRESSES', '쿨러 핀 오염'),
    ('팬 최대 운전', 'REFERS_TO', 'HM-8.5 즉시 완화 조치'),
    ('쿨러 핀 세척', 'REFERS_TO', 'HM-8.7 근본 조치'),
    ('팬 구동 불량', 'CAUSES', '쿨러 냉각 성능 상실'),
    ('쿨러 냉각 성능 상실', 'REMEDIED_BY', '팬 점검'),
    ('팬 점검', 'ADDRESSES', '팬 구동 불량'),
    ('팬 점검', 'REFERS_TO', 'HM-8.1 팬 벨트 점검'),
    ('주변 온도 상승', 'CAUSES', '쿨러 냉각 성능 상실'),
    ('캐비닛 환기 보강', 'ADDRESSES', '주변 온도 상승'),
    ('쿨러 냉각 성능 상실', 'REMEDIED_BY', '캐비닛 환기 보강'),
    ('캐비닛 환기 보강', 'REFERS_TO', 'HM-8.7 근본 조치'),
    ('팬 베어링 열화', 'LEADS_TO', '쿨러 냉각 성능 상실'),
    ('진동 증가', 'INDICATES', '팬 베어링 열화'),
]
PROPS = {
    '쿨러 핀 오염': [('냉각 효율', '30초 평균 < 70 %'), ('팬 진동', '2분 평균 < 0.9 mm/s')],
    '팬 구동 불량': [('팬 진동', '2분 평균 ≥ 0.9 mm/s')],
    '주변 온도 상승': [('캐비닛 온도', '2분 평균 ≥ 35 ℃')],
}
KIND = dict(NODES)

def new_node(caption):
    """빈 곳 클릭은 별도 큐에서 한다. 여기서는 Caption·Label 입력만."""
    return [['click', 'caption'], ['type', caption], ['click', 'labelPlus'], ['click', 'labelInput'], ['type', KIND[caption]], ['key', 'Tab']]

def grow(source, deg):
    """선택한 원의 테두리를 deg 방향의 빈 곳으로 끌어 새 원+화살표를 만든다(빈 곳은 촬영 코드가 찾는다)."""
    return [['grow', source, deg]]

def name_edge(a, b, typ):
    return [['edge', a, b], ['click', 'type'], ['type', typ]]

# 정리 배치: 사용자가 ego에서 직접 잡은 15개 배치(그림 `zo9DD…`의 저장 좌표) + 새 원 2개(팬 베어링 열화 · 진동 증가)를 비어 있는 왼쪽 위에 둔다.
# 촬영 때 현재 그림 범위에 비율로 맞춘다. ORDER는 녹화 전 계산(촬영도구/plan_order.py)으로 정한 순서다:
# 어느 단계에서도 아직 안 옮긴 원 자리에 놓지 않고, 그림 범위가 줄지 않는다(화면 맞춤 폭주 방지).
USER = {'HYD-01 유압 파워팩': (129, 351), '오일 쿨러': (348, 351), '유온 센서 TS1': (348, 616), '유온 상승': (614, 616), '쿨러 냉각 성능 상실': (614, 351),
        '쿨러 핀 오염': (1003, 532), '팬 최대 운전': (851, 709), '쿨러 핀 세척': (1003, 351), 'HM-8.5 즉시 완화 조치': (1173, 709), 'HM-8.7 근본 조치': (1278, 351),
        '팬 구동 불량': (604, -124), '팬 점검': (941, -124), 'HM-8.1 팬 벨트 점검': (1278, -124), '주변 온도 상승': (1003, 56), '캐비닛 환기 보강': (1278, 56),
        '팬 베어링 열화': (350, 100), '진동 증가': (129, 100)}
ORDER = ['HYD-01 유압 파워팩', '팬 최대 운전', '유온 상승', '쿨러 냉각 성능 상실', '쿨러 핀 세척', '팬 구동 불량', '쿨러 핀 오염', '팬 점검', 'HM-8.7 근본 조치',
         '주변 온도 상승', '캐비닛 환기 보강', '팬 베어링 열화', '진동 증가', 'HM-8.1 팬 벨트 점검', 'HM-8.5 즉시 완화 조치', '유온 센서 TS1', '오일 쿨러']
xs = [p[0] for p in USER.values()]; ys = [p[1] for p in USER.values()]
NORM = [[c, round((USER[c][0] - min(xs)) / (max(xs) - min(xs)), 4), round((USER[c][1] - min(ys)) / (max(ys) - min(ys)), 4)] for c in ORDER]


# (구간, 발화, 조작). 조작은 발화의 마지막 행동 문장에서 가리키기 시작해 문장 끝 직전에 실행한다.
CUES = [
 (1, '지금까지 배운 대로 쿨러 고장 이야기를 그래프로 그려 볼게요. 먼저 쉬운 예로 감을 잡아 볼게요. 여기 안치윤이라는 사람이 있어요. 동그라미 하나 그리고 이름을 써요. 이 사람은 학생이죠. 그래서 『학생』이라는 꼬리표를 붙여요. 이게 레이블이에요. 학생이면 학번이나 학년 같은 정보가 있잖아요. 그런 건 동그라미에 같이 적어 둬요. 이게 속성이에요. 그런데 이 학생은 학교에 다니죠. 학교도 하나 있어야겠네요. 동그라미를 하나 더 그리고 『학교』라고 써요. 이제 둘을 선으로 잇고, 선에 『다닌다』라는 이름을 붙여요. 이게 관계예요. 화살표는 학생에서 학교 쪽으로 그려요. 『학생이 학교에 다닌다』로 읽히게요. 쿨러 고장 이야기도 이렇게 하나씩 이어 가면 돼요.', []),
 (1, '검색 결과에서 Arrows.app을 눌러 들어갈게요.', [['openLink']]),
 (1, 'Arrows는 원과 화살표로 관계를 그리는 웹 도구예요. 왼쪽 넓은 곳이 그림 영역이고, 오른쪽은 선택한 대상의 내용을 바꾸는 패널입니다.', [['at', 0.35], ['point', 'canvasMid'], ['at', 0.7], ['point', 'panelMid']]),
 (1, '처음 기본 원은 긴 이름을 넣기에 조금 작아요. 오른쪽 STYLE에서 Customize를 누를게요.', [['click', 'customize']]),
 (1, 'Nodes 아래 radius가 원의 크기예요. 50을 70으로 바꾸고 Tab 키로 확정하겠습니다.', [['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '70'], ['key', 'Tab']]),
 (1, '맨 먼저 그릴 건 유압 설비예요. 쿨러도 센서도 모두 이 설비에 딸린 것들이니까요. 원 하나가 노드 하나라서, 원을 만드는 버튼 이름도 Add Node예요. 위쪽의 파란 Add Node를 눌러 첫 원을 만들게요.', [['click', 'addNode']]),
 (1, '원이 생기고 오른쪽에 내용 칸이 열렸어요. Caption은 원 안에 보일 이름입니다. 이 칸을 누르고 HYD-01 유압 파워팩이라고 적을게요.', [['click', 'caption'], ['type', 'HYD-01 유압 파워팩']]),
 (1, '아까 학생에 붙인 꼬리표처럼, 이 대상이 어떤 종류인지 적는 곳이 Label이에요. Label 옆 더하기를 누를게요.', [['click', 'labelPlus']]),
 (1, '새로 생긴 칸을 누르고, 설비를 뜻하는 Asset을 적은 뒤 Tab 키로 확정하겠습니다.', [['click', 'labelInput'], ['type', 'Asset'], ['key', 'Tab']]),
 
 (2, '원 안에 이름과 종류가 함께 보이죠. 이렇게 원 하나에 대상 하나를 적습니다.', []),
 (2, '이 설비 안에는 기름을 식혀 주는 오일 쿨러가 들어 있어요. 설비를 이루는 부품, 구성 요소죠. 쿨러도 따로 원으로 그려 둬야, 나중에 『쿨러에 문제가 있다』고 짚을 수 있어요. 이번에는 원에서 바로 이어서 만들어 볼게요. 선택한 원의 테두리 바로 바깥을 잡고 빈 곳으로 끌어 놓으면 화살표와 새 원이 함께 생깁니다.', grow('HYD-01 유압 파워팩', 0)),
 (2, '새 원이 선택된 상태예요. Caption에 오일 쿨러, Label에는 구성 요소를 뜻하는 Component를 적을게요.', new_node('오일 쿨러')),
 (2, '쿨러가 이 설비의 부품이라는 사실은 두 원을 잇는 화살표에 남겨요. 선만 있으면 무슨 사이인지 알 수 없으니, 화살표에 이름을 붙일게요. 두 원 사이의 화살표를 누르면 오른쪽에 Type 칸이 나와요.', [['edge', 'HYD-01 유압 파워팩', '오일 쿨러']]),
 (2, 'Type 칸을 누르고, 구성 요소로 가진다는 뜻의 HAS_COMPONENT를 적을게요.', [['click', 'type'], ['type', 'HAS_COMPONENT']]),
 (2, '설비가 오일 쿨러를 구성 요소로 가진다. 이렇게 출발에서 도착 쪽으로 읽으면 됩니다. 화살표를 설비에서 쿨러 쪽으로 그린 것도 그래서예요. 거꾸로 그리면 쿨러가 설비를 갖는다는 말이 돼 버리거든요.', [['at', 0.1], ['point', 'look:HYD-01 유압 파워팩'], ['at', 0.45], ['point', 'look:오일 쿨러']]),
 (2, '쿨러가 기름을 잘 식히는지는 유온 센서가 재고 있어요. 그래서 다음은 센서예요. 오일 쿨러에서 같은 방법으로 왼쪽 아래에 원을 하나 더 만들게요.', grow('오일 쿨러', 135)),
 (2, 'Caption은 유온 센서 TS1, Label은 센서를 뜻하는 Sensor라고 적겠습니다.', new_node('유온 센서 TS1')),
 (2, '화살표를 누르고 Type에 계측된다는 뜻의 MONITORED_BY를 적을게요. 오일 쿨러는 유온 센서로 계측됩니다. 이렇게 이어 두면 쿨러 상태를 보고 싶을 때 어느 센서 값을 읽어야 하는지 따라갈 수 있어요.', name_edge('오일 쿨러', '유온 센서 TS1', 'MONITORED_BY')),

 (3, '어느 날 유온이 자꾸 올라간다고 해 볼게요. 이렇게 눈에 보인 이상이 증상이에요. 센서는 값을 재는 장치이고 유온 상승은 그 값에서 드러난 일이라, 둘은 다른 원으로 그려요. 유온 센서에서 오른쪽으로 원을 끌어낼게요.', grow('유온 센서 TS1', 0)),
 (3, 'Caption은 유온 상승, Label은 Symptom이라고 적을게요.', new_node('유온 상승')),
 (3, '끌어서 만들었더니 화살표가 센서에서 증상 쪽으로 나가 있죠. 그런데 남기려는 문장은 『유온 상승은 유온 센서에서 관측된다』예요. 증상이 주어니까 화살표도 증상에서 출발해야 해요. 화살표를 누르고 오른쪽의 Reverse를 누르면 방향이 뒤집힙니다.', [['edge', '유온 센서 TS1', '유온 상승'], ['click', 'reverse']]),
 (3, 'Type에는 관측된다는 뜻의 OBSERVED_BY를 적을게요.', [['click', 'type'], ['type', 'OBSERVED_BY']]),
 (3, '유온이 오른다는 건, 쿨러가 열을 내보내는 기능에 탈이 났다는 신호예요. 이렇게 어떤 기능을 잃었는지를 말하는 게 고장 유형이에요. 고장 유형은 그림 가운데에 둬요. 증상에서 출발하든 원인에서 출발하든 모두 여기를 거쳐 가게요. 유온 상승에서 오른쪽 위로 끌어낼게요.', grow('유온 상승', -30)),
 (3, 'Caption은 쿨러 냉각 성능 상실, Label은 FailureMode라고 적을게요.', new_node('쿨러 냉각 성능 상실')),
 (3, '『유온 상승은 쿨러 냉각 성능 상실을 가리킨다』, 유온이 오르면 이 고장을 의심하라는 뜻이에요. 증상이 주어라서 화살표는 유온 상승에서 고장 쪽으로 나가요. 화살표를 누르고 Type에 가리킨다는 뜻의 INDICATES를 적겠습니다.', name_edge('유온 상승', '쿨러 냉각 성능 상실', 'INDICATES')),
 (3, '이 고장은 오일 쿨러에서 일어난 일이죠. 쿨러 원은 이미 있으니 새로 그리지 않고, 있는 원에 이어요. 같은 쿨러를 원 두 개로 그리면 한 부품이 두 대상으로 갈라지거든요. 쿨러 냉각 성능 상실을 선택하고, 이번에는 테두리를 빈 곳이 아니라 오일 쿨러 위에 놓을게요.', [['click', 'node:쿨러 냉각 성능 상실'], ['connect', '쿨러 냉각 성능 상실', '오일 쿨러']]),
 (3, '이미 있는 원 위에 놓으면 화살표만 생겨요. 이 화살표는 고장에서 쿨러 쪽이라 『쿨러 냉각 성능 상실은 오일 쿨러에서 일어난다』로 읽혀요. Type에 OCCURS_IN이라고 적겠습니다.', [['click', 'type'], ['type', 'OCCURS_IN']]),
 (3, '여기까지 읽어 볼게요. 유온 상승은 유온 센서에서 관측되고, 쿨러 냉각 성능 상실을 가리킵니다. 그 고장은 오일 쿨러에서 일어나죠.', [['at', 0.15], ['point', 'look:유온 상승'], ['at', 0.5], ['point', 'look:쿨러 냉각 성능 상실'], ['at', 0.8], ['point', 'look:오일 쿨러']]),

 (4, '원인과 조치를 붙일 자리를 만들게요. 쿨러 냉각 성능 상실 원의 가운데를 잡고 오른쪽 아래로 조금 옮기겠습니다. 원을 옮겨도 화살표는 그대로 따라와요.', [['move', '쿨러 냉각 성능 상실', 48, 116]]),
 (4, '이제 이 고장이 왜 났는지를 그려요. 쿨러 핀에 먼지가 꼈을 수도 있죠. 이게 원인이에요. 고장은 쿨러가 식히지 못한다는 모습이고 원인은 그렇게 된 까닭이라, 원인도 따로 원으로 둬요. 쿨러 냉각 성능 상실에서 오른쪽 위로 원을 끌어낼게요.', grow('쿨러 냉각 성능 상실', -50)),
 (4, 'Caption은 쿨러 핀 오염, Label은 Cause라고 적을게요.', new_node('쿨러 핀 오염')),
 (4, '화살표를 보면 고장에서 원인 쪽으로 나가 있죠. 남기려는 문장은 『쿨러 핀 오염은 쿨러 냉각 성능 상실을 일으킨다』예요. 원인이 주어니까 원인에서 출발해야 해요. 일으킨다는 관계는 원인에서 고장 유형으로만 잇는다는 제약도 있었죠. 화살표를 누르고 Reverse를 누른 뒤, Type에 일으킨다는 뜻의 CAUSES를 적겠습니다.', [['edge', '쿨러 냉각 성능 상실', '쿨러 핀 오염'], ['click', 'reverse'], ['click', 'type'], ['type', 'CAUSES']]),
 (4, '핀 오염이 정말 원인인지는 값을 봐야 가릴 수 있어요. 어떤 값을 어떤 기준과 견줄지, 그러니까 원인을 가리는 증거는 매뉴얼 8.4절에 정해져 있어요. 이 기준을 원인 원에 같이 적어 두면, 그림만 봐도 무엇을 확인할지 알 수 있죠. 아까 학생의 학번처럼 원에 적는 정보가 속성이고, 여기서는 Property 칸에 적어요. 쿨러 핀 오염 원을 다시 선택할게요.', [['click', 'node:쿨러 핀 오염']]),
 (4, '오른쪽 Property 옆 더하기를 누르면 왼쪽에 항목 이름, 오른쪽에 내용을 적는 칸이 생겨요.', [['click', 'propPlus']]),
 (4, '왼쪽 칸에는 냉각 효율이라고 적을게요.', [['click', 'propKey'], ['type', '냉각 효율']]),
 (4, '오른쪽 칸에는 30초 평균 70퍼센트 미만이라고 적겠습니다.', [['click', 'propVal'], ['type', '30초 평균 < 70 %']]),
 (4, 'Property를 하나 더 추가해서, 팬 진동은 2분 평균 0.9 미만이라고 적을게요.', [['click', 'propPlus'], ['click', 'propKey'], ['type', '팬 진동'], ['click', 'propVal'], ['type', '2분 평균 < 0.9 mm/s']]),
 (4, '두 조건을 함께 만족해야 핀 오염으로 판단해요. 쿨러가 열을 못 빼내는데 팬은 조용하다, 그러면 팬 탓이 아니라 핀이 막혔다고 볼 수 있는 거죠.', [['at', 0.2], ['point', 'props:쿨러 핀 오염']]),
 (4, '원인을 그렸으니 이제 조치를 이어요. 조치에는 완화 조치와 근본 조치가 있었죠. 먼저 유온을 바로 낮추는 완화 조치, 팬 최대 운전이에요. 쿨러 냉각 성능 상실에서 아래로 원을 끌어낼게요.', grow('쿨러 냉각 성능 상실', 100)),
 (4, 'Caption은 팬 최대 운전, Label은 조치 방법을 뜻하는 Skill이라고 적을게요.', new_node('팬 최대 운전')),
 (4, '『쿨러 냉각 성능 상실은 팬 최대 운전으로 완화된다』로 읽혀야 하니, 이번엔 화살표를 뒤집지 않아요. 화살표를 누르고 Type에 완화된다는 뜻의 MITIGATED_BY를 적겠습니다.', name_edge('쿨러 냉각 성능 상실', '팬 최대 운전', 'MITIGATED_BY')),
 (4, '팬을 세게 돌리면 온도는 내려가지만 막힌 핀은 그대로죠. 원인을 없애는 핀 세척도 놓을게요. 쿨러 냉각 성능 상실에서 오른쪽으로 끌어낼게요.', grow('쿨러 냉각 성능 상실', -5)),
 (4, 'Caption은 쿨러 핀 세척, Label은 Skill이라고 적을게요.', new_node('쿨러 핀 세척')),
 (4, '같은 고장에서 나가는 선이라도 이름을 달리 붙여야, 온도만 낮추는 조치와 근본 조치가 갈려요. 화살표를 누르고 Type에 근본적으로 해결된다는 뜻의 REMEDIED_BY를 적을게요.', name_edge('쿨러 냉각 성능 상실', '쿨러 핀 세척', 'REMEDIED_BY')),
 (4, '다만 핀 세척은 핀 오염일 때만 맞는 조치예요. 팬이 상한 거라면 핀을 닦아도 소용없죠. 그래서 이 조치가 어느 원인에 맞는지도 이어 둬요. 화살표는 조치에서 원인 쪽, 『쿨러 핀 세척은 쿨러 핀 오염을 해결한다』로 읽히게요. 쿨러 핀 세척에서 쿨러 핀 오염 위로 끌어 놓고, ADDRESSES라고 적겠습니다.', [['click', 'node:쿨러 핀 세척'], ['connect', '쿨러 핀 세척', '쿨러 핀 오염'], ['click', 'type'], ['type', 'ADDRESSES']]),

 (5, '조치마다 근거 문서도 이어 둘게요. 그래야 AI가 조치를 추천할 때 매뉴얼의 어느 절에 근거했는지 함께 내놓고, 사람은 승인하기 전에 그 원문을 확인할 수 있어요. 팬 최대 운전에서 왼쪽 아래로 원을 끌어낼게요.', grow('팬 최대 운전', 150)),
 (5, 'Caption은 매뉴얼 8.5절 즉시 완화 조치, Label은 매뉴얼 절을 뜻하는 ManualSection이라고 적을게요.', new_node('HM-8.5 즉시 완화 조치')),
 (5, '이 화살표는 『팬 최대 운전은 매뉴얼 8.5절을 근거로 한다』는 뜻이라, 조치에서 매뉴얼 쪽으로 그대로 둬요. 화살표를 누르고 Type에 REFERS_TO라고 적겠습니다.', name_edge('팬 최대 운전', 'HM-8.5 즉시 완화 조치', 'REFERS_TO')),
 (5, '', []),
 (5, '근본 조치의 근거도 만들게요. 쿨러 핀 세척에서 오른쪽으로 끌어낼게요.', grow('쿨러 핀 세척', -20)),
 (5, 'Caption은 매뉴얼 8.7절 근본 조치, Label은 ManualSection이라고 적을게요.', new_node('HM-8.7 근본 조치')),
 (5, '화살표를 누르고 REFERS_TO라고 적을게요.', name_edge('쿨러 핀 세척', 'HM-8.7 근본 조치', 'REFERS_TO')),

 (6, '유온이 오르는 게 핀 오염 때문만은 아니에요. 팬이 제대로 돌지 않아도 쿨러는 열을 못 내보내죠. 같은 고장의 다른 원인을 더해 볼게요. 처음부터 새로 그리지 않고 이 그림에 가지를 늘립니다. 쿨러 냉각 성능 상실에서 오른쪽 아래로 끌어낼게요.', grow('쿨러 냉각 성능 상실', 55)),
 (6, 'Caption은 팬 구동 불량, Label은 Cause라고 적겠습니다.', new_node('팬 구동 불량')),
 (6, '이것도 원인이니 화살표를 누르고 Reverse로 뒤집은 다음, CAUSES라고 적을게요.', [['edge', '쿨러 냉각 성능 상실', '팬 구동 불량'], ['click', 'reverse'], ['click', 'type'], ['type', 'CAUSES']]),
 (6, '이 원인의 판별 기준도 적을게요. 팬 구동 불량 원을 선택하고 Property 더하기를 누르겠습니다.', [['click', 'node:팬 구동 불량'], ['click', 'propPlus']]),
 (6, '왼쪽 칸에 팬 진동, 오른쪽 칸에 2분 평균 0.9 이상이라고 적을게요.', [['click', 'propKey'], ['type', '팬 진동'], ['click', 'propVal'], ['type', '2분 평균 ≥ 0.9 mm/s']]),
 (6, '같은 팬 진동을 보지만 핀 오염은 0.9 미만, 팬 구동 불량은 0.9 이상이에요. 보는 값은 같아도 기준이 반대라서, 팬 진동 하나로 두 원인이 갈려요.', [['at', 0.15], ['point', 'props:쿨러 핀 오염'], ['at', 0.45], ['point', 'props:팬 구동 불량']]),
 (6, '팬 쪽 원인에는 팬 점검이 맞는 조치예요. 쿨러 냉각 성능 상실에서 하나 더 끌어낼게요.', grow('쿨러 냉각 성능 상실', 25)),
 (6, 'Caption은 팬 점검, Label은 Skill이라고 적을게요.', new_node('팬 점검')),
 (6, '화살표를 누르고 REMEDIED_BY라고 적겠습니다.', name_edge('쿨러 냉각 성능 상실', '팬 점검', 'REMEDIED_BY')),
 (6, '팬 점검에서 팬 구동 불량 위로 끌어 놓고 ADDRESSES라고 적을게요.', [['click', 'node:팬 점검'], ['connect', '팬 점검', '팬 구동 불량'], ['click', 'type'], ['type', 'ADDRESSES']]),
 (6, '근거 문서도 이어 둘게요. 팬 점검에서 오른쪽으로 끌어낼게요.', grow('팬 점검', 10)),
 (6, 'Caption은 매뉴얼 8.1절 팬 벨트 점검, Label은 ManualSection이라고 적을게요.', new_node('HM-8.1 팬 벨트 점검')),
 (6, '화살표를 누르고 REFERS_TO라고 적겠습니다.', name_edge('팬 점검', 'HM-8.1 팬 벨트 점검', 'REFERS_TO')),
 (7, '원인이 하나 더 있어요. 쿨러가 놓인 캐비닛 안 공기가 더우면, 쿨러도 팬도 멀쩡한데 열을 잘 못 내보내요. 이게 주변 온도 상승이에요. 쿨러 냉각 성능 상실에서 왼쪽 위로 원을 끌어낼게요.', grow('쿨러 냉각 성능 상실', -125)),
 (7, 'Caption은 주변 온도 상승, Label은 Cause라고 적을게요.', new_node('주변 온도 상승')),
 (7, '원인이니까 화살표를 누르고 Reverse로 뒤집은 다음, CAUSES라고 적겠습니다.', [['edge', '쿨러 냉각 성능 상실', '주변 온도 상승'], ['click', 'reverse'], ['click', 'type'], ['type', 'CAUSES']]),
 (7, '판별 기준도 적을게요. 주변 온도 상승 원을 선택하고 Property 더하기를 누르겠습니다.', [['click', 'node:주변 온도 상승'], ['click', 'propPlus']]),
 (7, '왼쪽 칸에 캐비닛 온도, 오른쪽 칸에 2분 평균 35도 이상이라고 적을게요.', [['click', 'propKey'], ['type', '캐비닛 온도'], ['click', 'propVal'], ['type', '2분 평균 ≥ 35 ℃']]),
 (7, '주변 온도가 원인이면 조치는 캐비닛 환기 보강이에요. 주변 온도 상승에서 옆으로 원을 하나 끌어낼게요.', grow('주변 온도 상승', 180)),
 (7, 'Caption은 캐비닛 환기 보강, Label은 Skill이라고 적을게요.', new_node('캐비닛 환기 보강')),
 (7, '조치가 원인을 해결하는 방향이니 화살표를 누르고 Reverse로 뒤집은 뒤 ADDRESSES라고 적겠습니다.', [['edge', '주변 온도 상승', '캐비닛 환기 보강'], ['click', 'reverse'], ['click', 'type'], ['type', 'ADDRESSES']]),
 (7, '쿨러 냉각 성능 상실에서 캐비닛 환기 보강 위로 끌어 놓고 REMEDIED_BY라고 적을게요.', [['click', 'node:쿨러 냉각 성능 상실'], ['connect', '쿨러 냉각 성능 상실', '캐비닛 환기 보강'], ['click', 'type'], ['type', 'REMEDIED_BY']]),
 (7, '근거는 핀 세척과 같은 매뉴얼 8.7절이에요. 같은 절을 원 두 개로 그리면 한 문서가 둘로 갈라지니까, 있는 원에 이어요. 캐비닛 환기 보강에서 HM-8.7 위로 끌어 놓고 REFERS_TO라고 적겠습니다.', [['click', 'node:캐비닛 환기 보강'], ['connect', '캐비닛 환기 보강', 'HM-8.7 근본 조치'], ['click', 'type'], ['type', 'REFERS_TO']]),

 (8, '고장이 다른 고장으로 이어지기도 해요. 팬 축을 받쳐서 부드럽게 돌게 해 주는 부품을 베어링이라고 하는데요, 이게 닳으면 팬이 바람을 덜 보내서 결국 냉각 성능 상실로 이어질 수 있죠. 쿨러 냉각 성능 상실에서 원을 하나 끌어낼게요.', grow('쿨러 냉각 성능 상실', 120)),
 (8, 'Caption은 팬 베어링 열화, Label은 고장 유형이니 FailureMode라고 적을게요.', new_node('팬 베어링 열화')),
 (8, '이번에는 CAUSES를 쓰지 않아요. 일으킨다는 관계는 원인에서 고장 유형으로만 잇는다는 제약이 있었죠. 팬 베어링 열화는 원인이 아니라 그 자체로 고장 유형이라서, 고장이 고장으로 번지는 관계를 따로 써요. 베어링 열화가 냉각 성능 상실로 이어지는 방향이니 화살표를 누르고 Reverse로 뒤집은 뒤, 이어진다는 뜻의 LEADS_TO라고 적겠습니다.', [['edge', '쿨러 냉각 성능 상실', '팬 베어링 열화'], ['click', 'reverse'], ['click', 'type'], ['type', 'LEADS_TO']]),
 (8, '이 고장은 팬 진동이 커지는 증상으로 나타나요. 팬 베어링 열화에서 원을 끌어낼게요.', grow('팬 베어링 열화', 180)),
 (8, 'Caption은 진동 증가, Label은 Symptom이라고 적을게요.', new_node('진동 증가')),
 (8, '증상이 고장을 가리키는 방향이니 화살표를 누르고 Reverse로 뒤집은 다음 INDICATES라고 적겠습니다.', [['edge', '팬 베어링 열화', '진동 증가'], ['click', 'reverse'], ['click', 'type'], ['type', 'INDICATES']]),
 (8, '팬 진동이 커지면 지금은 팬 구동 불량으로 보여도, 베어링이 닳아 냉각 성능 상실까지 갈 수 있다는 걸 그림으로 남겨 둔 거예요.', [['at', 0.15], ['point', 'look:진동 증가'], ['at', 0.4], ['point', 'look:팬 베어링 열화'], ['at', 0.7], ['point', 'look:쿨러 냉각 성능 상실']]),

 (9, '화살표에도 속성을 적을 수 있어요. 매뉴얼에는 조치마다 따라 할 절차 번호가 있는데요, 이 번호는 조치 하나에만 딸린 게 아니라 이 조치를 그 매뉴얼 절의 어느 절차대로 하는지를 말해 줘요. 그래서 조치와 매뉴얼 절을 잇는 화살표에 적어요. 팬 최대 운전에서 HM-8.5로 가는 화살표를 누르겠습니다.', [['edge', '팬 최대 운전', 'HM-8.5 즉시 완화 조치']]),
 (9, '관계를 선택해도 오른쪽에 Property가 있어요. 더하기를 누르고 왼쪽 칸에 절차, 오른쪽 칸에 팬 최대 운전의 절차 번호를 적을게요.', [['click', 'propPlus'], ['click', 'propKey'], ['type', '절차'], ['click', 'propVal'], ['type', 'SOP-COOL-11']]),
 (9, '핀 세척에서 HM-8.7로 가는 화살표에도 핀 세척 절차 번호를 적겠습니다.', [['edge', '쿨러 핀 세척', 'HM-8.7 근본 조치'], ['click', 'propPlus'], ['click', 'propKey'], ['type', '절차'], ['click', 'propVal'], ['type', 'SOP-COOL-14']]),
 (9, '캐비닛 환기 보강에서 HM-8.7로 가는 화살표에는 환기 보강 절차 번호를 적을게요.', [['edge', '캐비닛 환기 보강', 'HM-8.7 근본 조치'], ['click', 'propPlus'], ['click', 'propKey'], ['type', '절차'], ['click', 'propVal'], ['type', 'SOP-COOL-15']]),
 (9, '팬 점검에서 HM-8.1로 가는 화살표에는 팬 점검 절차 번호를 적겠습니다.', [['edge', '팬 점검', 'HM-8.1 팬 벨트 점검'], ['click', 'propPlus'], ['click', 'propKey'], ['type', '절차'], ['click', 'propVal'], ['type', 'SOP-FAN-11']]),
 (9, '이렇게 적어 두면 화살표를 따라가다가 바로 실행할 절차를 찾을 수 있어요. 같은 매뉴얼 8.7절이라도 핀 세척과 환기 보강은 절차가 다르다는 것도 보이죠.', [['at', 0.2], ['point', 'look:HM-8.7 근본 조치']]),

 (10, '원이 많아져서 화살표가 얽혔죠. 흐름이 보이도록 정리해 볼게요. 먼저 빈 곳을 눌러 선택을 풀겠습니다.', [['click', 'blank']]),
 (10, '자리를 만들려고 원 크기를 조금 줄일게요. 오른쪽 STYLE의 Customize에서 radius를 70에서 47로 바꾸고 Tab 키로 확정하겠습니다.', [['click', 'customize'], ['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '47'], ['key', 'Tab']]),
 (10, '이제 원 가운데를 잡고 하나씩 옮겨서 왼쪽에서 오른쪽으로 읽히게 놓겠습니다. 원을 옮겨도 화살표는 그대로 따라와요.', [['layoutNorm', NORM, ['HYD-01 유압 파워팩', 'HM-8.1 팬 벨트 점검']]]),
 (10, '종류가 한눈에 보이도록 색을 칠해 볼게요. 쿨러 핀 오염을 누르고, Ctrl 키를 누른 채 나머지 원인 두 개를 눌러 함께 선택하겠습니다.', [['click', 'node:쿨러 핀 오염'], ['ctrlclick', 'node:팬 구동 불량'], ['ctrlclick', 'node:주변 온도 상승']]),
 (10, '오른쪽 STYLE의 node-color 칸에 연한 빨간색 색상값을 적고 Tab 키로 확정할게요.', [['click', 'style:node-color'], ['key', 'ControlOrMeta+A'], ['type', '#fde2e2'], ['key', 'Tab']]),
 (10, '조치 원 네 개도 같은 방법으로 함께 선택해서 연한 초록색을 칠하겠습니다.', [['click', 'node:팬 최대 운전'], ['ctrlclick', 'node:쿨러 핀 세척'], ['ctrlclick', 'node:팬 점검'], ['ctrlclick', 'node:캐비닛 환기 보강'], ['click', 'style:node-color'], ['key', 'ControlOrMeta+A'], ['type', '#dcfce7'], ['key', 'Tab']]),
 (10, '원인은 빨간색, 조치는 초록색이라 어느 쪽인지 바로 구별되네요. 빈 곳을 눌러 선택을 풀겠습니다.', [['click', 'blank']]),

 (11, '이제 완성된 그림을 읽어 볼게요. 그림을 넓게 보려고 오른쪽 위의 줄 세 개 버튼을 눌러 패널을 접겠습니다.', [['click', 'panelToggle']]),
 (11, '쿨러 냉각 성능 상실로 들어오는 CAUSES를 거슬러 가면 원인 후보가 세 개 나와요. 핀 오염, 팬 구동 불량, 주변 온도 상승이죠. 저장된 방향은 원인에서 고장 쪽이지만, 찾을 때는 이렇게 거슬러 따라가면 돼요. 반대쪽 화살표를 따로 그릴 필요가 없어요.', [['at', 0.1], ['point', 'look:쿨러 냉각 성능 상실'], ['at', 0.45], ['point', 'look:쿨러 핀 오염'], ['at', 0.55], ['point', 'look:팬 구동 불량'], ['at', 0.65], ['point', 'look:주변 온도 상승']]),
 (11, '이 그림으로 실제 사건을 판단해 볼게요. 교재에서 본 쿨러 사건의 값은 냉각 효율 30초 평균이 46.2퍼센트, 팬 진동 2분 평균이 초당 0.575밀리미터, 캐비닛 온도 2분 평균이 28도였어요.', [['at', 0.4], ['point', 'look:유온 상승']]),
 (11, '세 원인의 조건과 비교하면, 냉각 효율이 70퍼센트 미만이고 팬 진동이 0.9 미만이니 핀 오염 조건에 맞아요. 팬 구동 불량은 진동이 0.9 이상이어야 하고, 주변 온도 상승은 캐비닛 온도가 35도 이상이어야 하니 둘 다 아닙니다.', [['at', 0.15], ['point', 'props:쿨러 핀 오염'], ['at', 0.6], ['point', 'props:팬 구동 불량'], ['at', 0.8], ['point', 'props:주변 온도 상승']]),
 (11, '그러면 핀 오염을 해결하는 핀 세척을 찾고, 근거인 매뉴얼 8.7절로 갑니다. 세척하려면 설비를 세워야 하니, 그 전에 유온부터 낮추는 팬 최대 운전과 8.5절도 함께 확인하겠습니다.', [['at', 0.1], ['point', 'look:쿨러 핀 세척'], ['at', 0.3], ['point', 'look:HM-8.7 근본 조치'], ['at', 0.65], ['point', 'look:팬 최대 운전'], ['at', 0.85], ['point', 'look:HM-8.5 즉시 완화 조치']]),
 (11, '값이 달라지면 어떨까요? 냉각 효율은 낮은데 팬 진동이 1.4면 팬 구동 불량 쪽이에요. 팬 점검과 매뉴얼 8.1절로 가고, 팬 자체가 의심되니 팬 최대 운전부터 고르지는 않습니다. 진동이 계속 커지면 베어링 열화도 함께 봐야겠죠.', [['at', 0.2], ['point', 'props:팬 구동 불량'], ['at', 0.4], ['point', 'look:팬 점검'], ['at', 0.55], ['point', 'look:HM-8.1 팬 벨트 점검'], ['at', 0.85], ['point', 'look:팬 베어링 열화']]),
 (11, '캐비닛 온도가 38도라면 주변 온도 상승이에요. 캐비닛 환기 보강과 매뉴얼 8.7절로 이어집니다.', [['at', 0.25], ['point', 'props:주변 온도 상승'], ['at', 0.55], ['point', 'look:캐비닛 환기 보강'], ['at', 0.85], ['point', 'look:HM-8.7 근본 조치']]),
 (11, '팬 진동 자료를 아직 못 받았다면요? 냉각 효율이 낮으면 핀 오염을 먼저 의심하지만, 진동 조건을 확인하기 전에는 원인을 정할 수 없어요. 그래서 원인을 고르지 않고 보류한 채, 진동 값부터 확인해요.', [['at', 0.3], ['point', 'props:쿨러 핀 오염']]),
 (11, '이렇게 그림이 있으면 어떤 값을 더 봐야 하는지, 어느 조치로 가야 하는지 따라갈 수 있어요.', []),
 (12, '이제 저장할게요. 위쪽 Download / Export를 누르겠습니다.', [['click', 'export']]),
 (12, 'JSON 탭은 나중에 다시 편집할 수 있는 데이터예요. JSON을 누르고 Download로 내려받을게요.', [['click', 'tab:JSON'], ['download', 'json', '쿨러_지식그래프_최종']]),
 (12, 'PNG 탭에서는 그림 파일을 받을 수 있어요. PNG를 누르고 Download를 누르겠습니다.', [['click', 'tab:PNG'], ['download', 'png', '쿨러_지식그래프_최종']]),
 (12, 'Done을 눌러 그림으로 돌아갈게요.', [['click', 'done']]),
 (12, '저장한 데이터가 제대로 열리는지 새 그림에서 확인해 볼게요. 왼쪽 위 로고 메뉴를 누르겠습니다.', [['click', 'logo']]),
 (12, 'New에 마우스를 올리고 Web Browser storage를 누르면 빈 그림이 새로 열려요.', [['point', 'menu:New'], ['click', 'menu:newLocal']]),
 (12, '다시 로고 메뉴를 열고 Import를 누를게요.', [['click', 'logo'], ['click', 'menu:Import']]),
 (12, 'Choose File을 눌러 방금 내려받은 JSON 파일을 고르겠습니다.', [['choose', 'json']]),
 (12, '아래 Import 버튼을 누르면 그림이 들어옵니다.', [['click', 'importButton']]),
 (12, '새 그림에 처음부터 있던 빈 원이 하나 남아 있네요. 이 원을 눌러 선택하고 Delete 키로 지우겠습니다.', [['click', 'node:'], ['key', 'Delete']]),
 (12, '원 열일곱 개와 화살표 스물한 개, 조건과 절차 번호까지 그대로 돌아왔네요.', [['verify'], ['at', 0.3], ['point', 'look:쿨러 핀 오염'], ['at', 0.6], ['point', 'look:팬 구동 불량']]),
 (13, '마지막으로, 이 그림은 데이터베이스에 넣는 명령으로도 바꿀 수 있어요. 관계 그림은 사람이 보기 좋게 그린 것이고, 컴퓨터가 찾아 쓰려면 그래프 DB에 담아야 하거든요. Cypher는 그래프 DB인 Neo4j에 쓰는 명령 언어예요. 위쪽 Download / Export를 누르고 Cypher 탭을 누르겠습니다.', [['click', 'export'], ['click', 'tab:Cypher']]),
 (13, 'CREATE로 시작하는 문장이 보이죠. 원과 관계, 조건이 Neo4j에 바로 넣을 수 있는 명령으로 바뀌었어요.', [['at', 0.15], ['point', 'cypherText']]),
 (13, 'Done을 눌러 그림으로 돌아갈게요.', [['click', 'done']]),
 (13, '이제 증상에서 원인과 조치, 근거 문서까지 이 그림 한 장으로 따라갈 수 있습니다.', []),
]

def cues():
    out = []
    i = 0
    for seg, text, ops, *own in CUES:
        if not own:
            i += 1
        out.append({'id': own[0] if own else f'o{i:03}', 'segment': seg, 'text': text, 'ops': ops})
    return out

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
EVID = REPO / '작업' / '촬영' / 'arrows'
VIDEO = EVID / 'ARROWS-온톨로지-최종배치'
SEGMENT_TITLE = {1: 'arrows.app 열기 · 원 크기 · 첫 원', 2: '구성 요소 · 센서 · 첫 관계', 3: '증상 · 고장 유형', 4: '원인 · 조건 · 조치', 5: '매뉴얼 절', 6: '팬 구동 불량 가지',
                 7: '세 번째 원인 · 주변 온도 상승', 8: '고장이 고장으로 · 팬 베어링 열화', 9: '화살표에 절차 번호', 10: '배치 정리 · 종류별 색칠', 11: '완성 그림 읽고 판단하기', 12: '저장 · 다시 열기', 13: 'Cypher로 내보내기 · 마무리'}
TARGET = {'addNode': 'Add Node 클릭', 'caption': 'Caption 입력칸 클릭', 'labelPlus': 'Label 옆 + 클릭', 'labelInput': '새 Label 입력칸 클릭',
          'propPlus': 'Property 옆 + 클릭', 'propKey': '새 속성의 왼쪽(이름) 칸 클릭', 'propVal': '오른쪽(내용) 칸 클릭', 'type': 'Type 입력칸 클릭',
          'blank': '그림의 빈 곳 클릭(선택 해제)', 'customize': 'STYLE의 Customize 클릭', 'style:radius': 'radius 입력칸 클릭',
          'reverse': 'Reverse 클릭(화살표 방향 뒤집기)', 'export': 'Download / Export 클릭', 'tab:JSON': 'JSON 탭 클릭', 'tab:PNG': 'PNG 탭 클릭',
          'done': 'Done 클릭', 'logo': '왼쪽 위 로고 메뉴 클릭', 'menu:newLocal': 'New ▸ Web Browser storage 클릭(새 그림)', 'menu:Import': 'Import 클릭',
          'importButton': '창 아래 Import 버튼 클릭', 'panelToggle': '오른쪽 위 ☰ 클릭(패널 접기)', 'canvasMid': '그림 영역 가리키기', 'panelMid': '오른쪽 패널 가리키기',
          'menu:New': 'New에 커서 올리기', 'node:': '빈 원 클릭', 'cypherText': 'Cypher 문장 가리키기', 'tab:Cypher': 'Cypher 탭 클릭', 'style:node-color': 'node-color 입력칸 클릭'}


def act(op):
    k, *a = op
    if k == 'at':
        return None
    if k == 'openLink':
        return '검색 결과의 Arrows.app 링크 클릭 → arrows.app 열림 확인'
    if k in ('click', 'point'):
        t = a[0]
        if t in TARGET:
            return TARGET[t]
        for pre, word in (('node:', '원 클릭'), ('look:', '원 가리키기'), ('props:', '원의 조건 가리키기')):
            if t.startswith(pre):
                return f'‘{t[len(pre):]}’ {word}' if k == 'click' or pre != 'node:' else f'‘{t[5:]}’ 원 가리키기'
        return t
    if k == 'type':
        return f'`{a[0]}` 입력'
    if k == 'key':
        return {'ControlOrMeta+A': 'Ctrl+A(칸 전체 선택)'}.get(a[0], a[0] + ' 키')
    if k == 'grow':
        return f'‘{a[0]}’ 원 테두리 바로 바깥을 잡아 빈 곳으로 끌기 → 새 원과 화살표 생성'
    if k == 'edge':
        return f'‘{a[0]}’–‘{a[1]}’ 사이 화살표 클릭(관계 선택)'
    if k == 'connect':
        return f'‘{a[0]}’ 테두리를 잡아 ‘{a[1]}’ 원 위에 놓기 → 화살표 생성'
    if k == 'move':
        return f'‘{a[0]}’ 원 가운데를 잡아 오른쪽 아래로 조금 옮기기'
    if k in ('layout', 'layoutNorm'):
        return '원 가운데를 잡아 차례로 옮기기: ' + ', '.join(m[0] for m in a[0]) + ' (왼쪽→오른쪽 흐름, 화살표 교차 없음)'
    if k == 'download':
        return 'Download 클릭 → 파일 저장 확인'
    if k == 'ctrlclick':
        return f'Ctrl 누른 채 ‘{a[0][5:]}’ 원 클릭(함께 선택)'
    if k == 'choose':
        return 'Choose File로 방금 저장한 JSON 선택'
    if k == 'verify':
        return '원 17 · 화살표 21 · 원인 조건 · 절차 번호 복원 확인'
    return k


def manuscript():
    out = ['''# ARROWS 실습 — 쿨러 고장의 지식 그래프 그리기

2026-10-23 촬영판. 교재 SLIDE 67(지식 그래프 지도) · 73 · 74(핀 오염 기본도 → 팬 구동 불량 가지 → 비교 · 저장 · 다시 열기)의 실습이다. HM-8.4의 세 번째 원인(주변 온도 상승), 고장이 다른 고장으로 이어지는 팬 베어링 열화, 화살표의 절차 번호까지 그린 뒤 정리 · 색칠하고, 완성 그림으로 판단해 보고, 저장 · 다시 열기와 Cypher 내보내기로 마친다. 두 과정 공통.

## 진행 메모 — 낭독하지 않음

- 실제 촬영한 큐 그대로다. 표 왼쪽 발화로 대상과 행동을 먼저 알리고, 행동 문장이 끝나기 약 0.25초 전에 오른쪽 조작을 실행한 뒤 결과가 보이면 다음 발화로 간다.
- 원 위치는 고정 좌표가 아니다. 테두리 끌기로 원을 만들 때 빈 곳을 찾아 놓고, 10구간에서 흐름이 보이게 정리한다. arrows.app은 그림 전체를 화면에 자동으로 맞춘다.
- 첫 원만 Add Node로 만들고 나머지는 원 테두리를 빈 곳으로 끌어 원과 화살표를 함께 만든다. 원인 → 고장(CAUSES)과 증상 → 센서(OBSERVED_BY)는 만든 뒤 Reverse로 방향을 뒤집는다.
- 입력값 출처: 클래스 · 관계 이름은 `workspace/개발/문서/ontology/schema-v2.md` · `it/neo4j/v2/instances.cypher`, 판별 기준은 랩 `매뉴얼_발췌.md` HM-8.4, 조치 근거는 HM-8.1 · 8.5 · 8.7.
- 영상: `workspace/강의제작/산출물/영상/통합반/통합반_01회차_08_실습_관계그림.mp4`(로컬 근거, Git 미포함). 구간 · 시간 · 측정은 제작용 [예상시간](예상시간.md).
''']
    seg = 0
    for c in cues():
        if c['segment'] != seg:
            seg = c['segment']
            out.append(f'\n## {seg}구간 · {SEGMENT_TITLE[seg]}\n\n| 발화 | 조작·결과 확인 — 비낭독 |\n|---|---|')
        acts = [x for x in (act(o) for o in c['ops']) if x]
        fix = '' if re.fullmatch(r'o\d{3}', c['id']) else '촬영 중 수습 — 다시 할 때는 없음 · '
        out.append(f"| {c['text']} | {fix}{' → '.join(acts) if acts else '—'} |")
    out.append('\n# 촬영 본문 끝\n\n## 제작 확인용 — 낭독하지 않음\n\n'
               '- 판별 조건은 HM-8.4 원문 기준이다(핀 오염: CE 30초 평균 < 70 % 이고 VS1 2분 평균 < 0.9 mm/s, 팬 구동 불량: VS1 2분 평균 ≥ 0.9 mm/s, 주변 온도 상승: TS4 2분 평균 ≥ 35 ℃). 캐비닛 환기 보강은 랩 발췌 HM-8.7의 SOP-COOL-15다. 이번 그림은 판별 기준을 담은 지식 구조이며 새 진단 실행 결과가 아니다.\n'
               '- REFERS_TO는 실제 데이터에서 Skill → Step → ManualSection 두 단계(HAS_STEP · REFERS_TO)다. 교재 지도처럼 한 번에 이었다고 영상에서 말한다.\n'
               '- 10구간 배치는 사용자가 ego에서 직접 잡은 15개 배치를 비율대로 따랐다(원 크기 70 → 47). 그 배치에 없던 팬 베어링 열화 · 진동 증가는 비어 있는 왼쪽 위에 두었다.\n')
    return '\n'.join(out) + '\n'


def write_all():
    import hashlib, re, shutil
    final = json.loads((EVID / 'saved' / '쿨러_지식그래프_최종.json').read_text(encoding='utf-8'))
    by = {n['id']: n['caption'] for n in final['nodes']}
    ver = json.loads((VIDEO / 'verification.json').read_text(encoding='utf-8'))
    script = manuscript()
    (ROOT / '수업원고.md').write_text(script, encoding='utf-8')
    spoken = sum(json.loads((EVID / 'audio' / (c['id'] + '.json')).read_text(encoding='utf-8'))['duration_ms'] for c in cues()) / 1000
    used = [(s['segment'], s['used_ms'] / 1000) for s in ver['segments']]
    timing = f'''# ARROWS 실습 시간 — 실측

대상: 2026-10-23 촬영판 [수업원고](수업원고.md). **실측 영상 길이 {ver['duration_s'] / 60:.1f}분({ver['duration_s']:.0f}초)**, 음성 {ver['speech_cues']}큐(음성만 합하면 {spoken / 60:.1f}분). 설명하면서 조작한 실제 타임라인의 합이며 배속 · 중간 컷이 없다. 원래 배정 30분보다 짧지만 필요한 내용을 자연스럽게 진행한 결과로 그대로 둔다.

| 촬영 조각 | 사용 길이(초) |
|---|---|
''' + ''.join(f'| {n} | {t:.1f} |\n' for n, t in used) + f'''
측정: 이동 {ver['motion_summary']['count']}회 중 최대 프레임 공백 {ver['motion_summary']['max_gap_ms_max']}ms, 100ms 이상 {len(ver['motion_summary']['over_100ms'])}회(각각 한 번의 짧은 끊김). 문장 끝보다 늦게 실행된 조작 0건.
영상 안에는 원 끌어내기를 헛잡고 다시 잡는 장면이 그대로 있다. 사용자가 영상을 재생해 확인하고 이 판으로 확정했다(2026-10-23).
'''
    (ROOT / '예상시간.md').write_text(timing, encoding='utf-8')
    nodes_md = '# 쿨러 지식 그래프 — 그릴 대상과 관계\n\n교재 75장의 클래스로 오일 쿨러 사례를 그립니다. 아래는 강사 화면에서 완성한 그림(`완성_쿨러_지식그래프.json`)의 내용입니다. 직접 만든 결과와 비교할 때 참고합니다.\n\n| 이름(Caption) | 종류(Label) | 조건(Property) |\n|---|---|---|\n'
    for n in final['nodes']:
        props = ' / '.join(f'{k}: {v}' for k, v in n.get('properties', {}).items())
        nodes_md += f"| {n['caption']} | {', '.join(n['labels'])} | {props or '—'} |\n"
    nodes_md += '\n## 관계 — 출발 · 이름 · 도착\n\n| 출발 | 관계 이름(Type) | 도착 | 문장으로 읽기 |\n|---|---|---|---|\n'
    reads = {'HAS_COMPONENT': '구성 요소로 가진다', 'MONITORED_BY': '로 계측된다', 'OBSERVED_BY': '에서 관측된다', 'INDICATES': '를 가리킨다', 'OCCURS_IN': '에서 일어난다',
             'CAUSES': '를 일으킨다', 'MITIGATED_BY': '로 완화된다', 'REMEDIED_BY': '로 근본 해결된다', 'ADDRESSES': '를 해결 대상으로 한다', 'REFERS_TO': '의 근거로 이어진다'}
    for r in final['relationships']:
        nodes_md += f"| {by[r['fromId']]} | {r['type']} | {by[r['toId']]} | {reads.get(r['type'], '')} |\n"
    nodes_md += '\n근거: 조건은 `매뉴얼_발췌.md` HM-8.4, 조치는 HM-8.1 · 8.5 · 8.7입니다.\n'
    screens = f'''# 화면 — 촬영 완료

2026-10-23 촬영 영상(로컬 근거) `{VIDEO.relative_to(REPO).as_posix()}/` 의 실제 화면이다. 완성 그림은 `완성_쿨러_지식그래프.png`, 편집 데이터는 `완성_쿨러_지식그래프.json`(촬영 중 arrows.app에서 내려받은 참조본).

| 구간 | 보여 준 것 | 확인한 결과 |
|---|---|---|
''' + ''.join(f'| {k} | {v} | 실제 화면 |\n' for k, v in SEGMENT_TITLE.items())
    (ROOT / '촬영화면.md').write_text(screens, encoding='utf-8')
    sys.path.insert(0, str(REPO / 'workspace/강의제작/제작도구/실습시작'))
    from lab_package import pack
    for course in ['실전반', '통합반']:
        day = REPO / 'workspace/강의제작/산출물' / course / '실습/01회차'
        lab = day / '랩/01일차_실습4_관계그림'
        (day / '대본/08_실습_관계그림.md').write_text(script.replace('(예상시간.md)', '(../../../../../제작도구/촬영/arrows/예상시간.md)'), encoding='utf-8')
        (lab / '대상_목록.md').write_text(nodes_md, encoding='utf-8')
        shutil.copyfile(EVID / 'saved' / '쿨러_지식그래프_최종.json', lab / '완성_쿨러_지식그래프.json')
        shutil.copyfile(EVID / 'saved' / '쿨러_지식그래프_최종.png', lab / '완성_쿨러_지식그래프.png')
        pack(lab)   # 가이드.html은 build_student_guide.py가 쓴다 — 여기서 덮지 않는다
    files = [ROOT / '수업원고.md', ROOT / '예상시간.md', ROOT / '촬영화면.md'] + [REPO / 'workspace/강의제작/산출물' / c / '실습/01회차' / x for c in ['실전반', '통합반'] for x in
             ['대본/08_실습_관계그림.md', '랩/01일차_실습4_관계그림/가이드.html', '랩/01일차_실습4_관계그림/대상_목록.md', '랩/01일차_실습4_관계그림.zip']]
    (ROOT / '동기화판본.json').write_text(json.dumps({f.relative_to(REPO).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('synced', ver['duration_s'], 's;', len(final['nodes']), 'nodes', len(final['relationships']), 'rels')


if __name__ == '__main__':
    if sys.argv[1] == 'cues':
        data = {'voice_id': '1PdAOcPlPTz12RwMyFVp', 'model_id': 'eleven_v4', 'nodes': [list(n) for n in NODES],
                'relationships': RELS, 'properties': PROPS, 'cues': cues()}
        Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        print(len(data['cues']), 'cues')
    elif sys.argv[1] == 'sync':
        write_all()
    else:
        raise SystemExit('usage: build_ontology.py cues <path> | sync')
