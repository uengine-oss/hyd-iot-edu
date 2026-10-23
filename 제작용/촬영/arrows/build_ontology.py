"""ARROWS 실습 원본: 교재 SLIDE 64·70·71의 쿨러 지식 그래프를 arrows.app에서 그리는 큐(발화+조작).
이 파일 하나가 음성 목록·촬영 조작·수업 원고·두 과정 랩 산출물의 원본이다. 앱·음성 API는 호출하지 않는다.
사용: python build_ontology.py cues <cues.json 출력 경로>   # 촬영용 큐
      python build_ontology.py sync                       # 수업원고·시간·두 과정 대본/랩/가이드/ZIP 동기화
"""
import json, sys
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

# (구간, 발화, 조작). 조작은 발화의 마지막 행동 문장에서 가리키기 시작해 문장 끝 직전에 실행한다.
CUES = [
 (1, '이번 실습에서는 교재에서 본 지식 그래프 지도를 직접 그려 볼게요. 설비와 센서, 증상과 고장, 원인과 조치까지 쿨러 사례로 이어 보겠습니다.', []),
 (1, '검색 결과에서 Arrows.app을 눌러 들어갈게요.', [['openLink']]),
 (1, 'Arrows는 원과 화살표로 관계를 그리는 웹 도구예요. 왼쪽 넓은 곳이 그림 영역이고, 오른쪽은 선택한 대상의 내용을 바꾸는 패널입니다.', [['at', 0.35], ['point', 'canvasMid'], ['at', 0.7], ['point', 'panelMid']]),
 (1, '처음 기본 원은 긴 이름을 넣기에 조금 작아요. 오른쪽 STYLE에서 Customize를 누를게요.', [['click', 'customize']]),
 (1, 'Nodes 아래 radius가 원의 크기예요. 50을 70으로 바꾸고 Tab 키로 확정하겠습니다.', [['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '70'], ['key', 'Tab']]),
 (1, '이제 위쪽의 파란 Add Node를 눌러 첫 원을 만들게요.', [['click', 'addNode']]),
 (1, '원이 생기고 오른쪽에 내용 칸이 열렸어요. Caption은 원 안에 보일 이름입니다. 이 칸을 누르고 HYD-01 유압 파워팩이라고 적을게요.', [['click', 'caption'], ['type', 'HYD-01 유압 파워팩']]),
 (1, 'Label은 이 대상이 어떤 종류인지 적는 곳이에요. Label 옆 더하기를 누를게요.', [['click', 'labelPlus']]),
 (1, '새로 생긴 칸을 누르고, 설비를 뜻하는 Asset을 적은 뒤 Tab 키로 확정하겠습니다.', [['click', 'labelInput'], ['type', 'Asset'], ['key', 'Tab']]),
 
 (2, '원 안에 이름과 종류가 함께 보이죠. 이렇게 원 하나에 대상 하나를 적습니다.', []),
 (2, '다음은 이 설비의 구성 요소인 오일 쿨러예요. 이번에는 원에서 바로 이어서 만들어 볼게요. 선택한 원의 테두리 바로 바깥을 잡고 빈 곳으로 끌어 놓으면 화살표와 새 원이 함께 생깁니다.', grow('HYD-01 유압 파워팩', 0)),
 (2, '새 원이 선택된 상태예요. Caption에 오일 쿨러, Label에는 구성 요소를 뜻하는 Component를 적을게요.', new_node('오일 쿨러')),
 (2, '이제 화살표에 이름을 붙일게요. 두 원 사이의 화살표를 누르면 오른쪽에 Type 칸이 나와요.', [['edge', 'HYD-01 유압 파워팩', '오일 쿨러']]),
 (2, 'Type 칸을 누르고, 구성 요소로 가진다는 뜻의 HAS_COMPONENT를 적을게요.', [['click', 'type'], ['type', 'HAS_COMPONENT']]),
 (2, '설비가 오일 쿨러를 구성 요소로 가진다. 이렇게 출발에서 도착 쪽으로 읽으면 됩니다.', [['at', 0.1], ['point', 'look:HYD-01 유압 파워팩'], ['at', 0.45], ['point', 'look:오일 쿨러']]),
 (2, '오일 쿨러에서 같은 방법으로 왼쪽 아래에 원을 하나 더 만들게요.', grow('오일 쿨러', 135)),
 (2, 'Caption은 유온 센서 TS1, Label은 센서를 뜻하는 Sensor라고 적겠습니다.', new_node('유온 센서 TS1')),
 (2, '화살표를 누르고 Type에 계측된다는 뜻의 MONITORED_BY를 적을게요. 오일 쿨러는 유온 센서로 계측됩니다.', name_edge('오일 쿨러', '유온 센서 TS1', 'MONITORED_BY')),

 (3, '이제 진단 쪽으로 갑니다. 유온이 오르는 현상, 즉 증상을 만들게요. 유온 센서에서 오른쪽으로 원을 끌어낼게요.', grow('유온 센서 TS1', 0)),
 (3, 'Caption은 유온 상승, Label은 Symptom이라고 적을게요.', new_node('유온 상승')),
 (3, '그런데 이 화살표는 센서에서 증상 쪽으로 나가 있죠. 증상이 센서에서 관측된다는 뜻이니 방향을 바꿔야 해요. 화살표를 누르고 오른쪽의 Reverse를 누르면 방향이 뒤집힙니다.', [['edge', '유온 센서 TS1', '유온 상승'], ['click', 'reverse']]),
 (3, 'Type에는 관측된다는 뜻의 OBSERVED_BY를 적을게요.', [['click', 'type'], ['type', 'OBSERVED_BY']]),
 (3, '가운데에는 고장 유형을 놓겠습니다. 유온 상승에서 오른쪽 위로 끌어낼게요.', grow('유온 상승', -30)),
 (3, 'Caption은 쿨러 냉각 성능 상실, Label은 FailureMode라고 적을게요.', new_node('쿨러 냉각 성능 상실')),
 (3, '화살표를 누르고 Type에 가리킨다는 뜻의 INDICATES를 적겠습니다.', name_edge('유온 상승', '쿨러 냉각 성능 상실', 'INDICATES')),
 (3, '고장이 어느 부품에서 생기는지도 이어야겠죠. 쿨러 냉각 성능 상실을 선택하고, 이번에는 테두리를 빈 곳이 아니라 오일 쿨러 위에 놓을게요.', [['click', 'node:쿨러 냉각 성능 상실'], ['connect', '쿨러 냉각 성능 상실', '오일 쿨러']]),
 (3, '이미 있는 원 위에 놓으면 화살표만 생겨요. Type에 OCCURS_IN이라고 적겠습니다.', [['click', 'type'], ['type', 'OCCURS_IN']]),
 (3, '여기까지 읽어 볼게요. 유온 상승은 유온 센서에서 관측되고, 쿨러 냉각 성능 상실을 가리킵니다. 그 고장은 오일 쿨러에서 일어나죠.', [['at', 0.15], ['point', 'look:유온 상승'], ['at', 0.5], ['point', 'look:쿨러 냉각 성능 상실'], ['at', 0.8], ['point', 'look:오일 쿨러']]),

 (4, '원인과 조치를 붙일 자리를 만들게요. 쿨러 냉각 성능 상실 원의 가운데를 잡고 오른쪽 아래로 조금 옮기겠습니다. 원을 옮겨도 화살표는 그대로 따라와요.', [['move', '쿨러 냉각 성능 상실', 48, 116]]),
 (4, '이제 왜 그런 고장이 났는지, 원인을 붙일게요. 쿨러 냉각 성능 상실에서 오른쪽 위로 원을 끌어낼게요.', grow('쿨러 냉각 성능 상실', -50)),
 (4, 'Caption은 쿨러 핀 오염, Label은 Cause라고 적을게요.', new_node('쿨러 핀 오염')),
 (4, '원인이 고장을 일으키는 거니까 방향을 뒤집어야겠죠. 화살표를 누르고 Reverse를 누른 뒤, Type에 일으킨다는 뜻의 CAUSES를 적겠습니다.', [['edge', '쿨러 냉각 성능 상실', '쿨러 핀 오염'], ['click', 'reverse'], ['click', 'type'], ['type', 'CAUSES']]),
 (4, '핀 오염인지는 매뉴얼 8.4절의 기준으로 가려요. 이런 조건은 Property에 적을 수 있어요. 쿨러 핀 오염 원을 다시 선택할게요.', [['click', 'node:쿨러 핀 오염']]),
 (4, '오른쪽 Property 옆 더하기를 누르면 왼쪽에 항목 이름, 오른쪽에 내용을 적는 칸이 생겨요.', [['click', 'propPlus']]),
 (4, '왼쪽 칸에는 냉각 효율이라고 적을게요.', [['click', 'propKey'], ['type', '냉각 효율']]),
 (4, '오른쪽 칸에는 30초 평균 70퍼센트 미만이라고 적겠습니다.', [['click', 'propVal'], ['type', '30초 평균 < 70 %']]),
 (4, 'Property를 하나 더 추가해서, 팬 진동은 2분 평균 0.9 미만이라고 적을게요.', [['click', 'propPlus'], ['click', 'propKey'], ['type', '팬 진동'], ['click', 'propVal'], ['type', '2분 평균 < 0.9 mm/s']]),
 (4, '두 조건을 함께 만족해야 핀 오염으로 판단해요. 팬 진동이 정상이어야 한다는 점이 중요합니다.', [['at', 0.2], ['point', 'props:쿨러 핀 오염']]),
 (4, '이제 조치를 붙일게요. 먼저 유온을 바로 낮추는 팬 최대 운전입니다. 쿨러 냉각 성능 상실에서 아래로 원을 끌어낼게요.', grow('쿨러 냉각 성능 상실', 100)),
 (4, 'Caption은 팬 최대 운전, Label은 조치 방법을 뜻하는 Skill이라고 적을게요.', new_node('팬 최대 운전')),
 (4, '화살표를 누르고 Type에 완화된다는 뜻의 MITIGATED_BY를 적겠습니다.', name_edge('쿨러 냉각 성능 상실', '팬 최대 운전', 'MITIGATED_BY')),
 (4, '팬을 세게 돌리면 온도는 내려가지만 막힌 핀은 그대로죠. 원인을 없애는 핀 세척도 놓을게요. 쿨러 냉각 성능 상실에서 오른쪽으로 끌어낼게요.', grow('쿨러 냉각 성능 상실', -5)),
 (4, 'Caption은 쿨러 핀 세척, Label은 Skill이라고 적을게요.', new_node('쿨러 핀 세척')),
 (4, '화살표를 누르고 Type에 근본적으로 해결된다는 뜻의 REMEDIED_BY를 적을게요.', name_edge('쿨러 냉각 성능 상실', '쿨러 핀 세척', 'REMEDIED_BY')),
 (4, '다만 핀 세척은 핀 오염일 때만 맞는 조치예요. 쿨러 핀 세척에서 쿨러 핀 오염 위로 끌어 놓고, ADDRESSES라고 적겠습니다.', [['click', 'node:쿨러 핀 세척'], ['connect', '쿨러 핀 세척', '쿨러 핀 오염'], ['click', 'type'], ['type', 'ADDRESSES']]),

 (5, '조치마다 근거 문서도 이어 둘게요. 팬 최대 운전에서 왼쪽 아래로 원을 끌어낼게요.', grow('팬 최대 운전', 150)),
 (5, 'Caption은 매뉴얼 8.5절 즉시 완화 조치, Label은 매뉴얼 절을 뜻하는 ManualSection이라고 적을게요.', new_node('HM-8.5 즉시 완화 조치')),
 (5, '화살표를 누르고 Type에 REFERS_TO라고 적겠습니다.', name_edge('팬 최대 운전', 'HM-8.5 즉시 완화 조치', 'REFERS_TO')),
 (5, '실제 데이터에서는 절차의 단계를 거쳐 매뉴얼로 이어지는데, 교재 지도처럼 한 번에 이었어요.', []),
 (5, '근본 조치의 근거도 만들게요. 쿨러 핀 세척에서 오른쪽으로 끌어낼게요.', grow('쿨러 핀 세척', -20)),
 (5, 'Caption은 매뉴얼 8.7절 근본 조치, Label은 ManualSection이라고 적을게요.', new_node('HM-8.7 근본 조치')),
 (5, '화살표를 누르고 REFERS_TO라고 적을게요.', name_edge('쿨러 핀 세척', 'HM-8.7 근본 조치', 'REFERS_TO')),

 (6, '이제 같은 고장의 다른 원인을 더해 볼게요. 처음부터 새로 그리지 않고 이 그림에 가지를 늘립니다. 쿨러 냉각 성능 상실에서 오른쪽 아래로 끌어낼게요.', grow('쿨러 냉각 성능 상실', 55)),
 (6, 'Caption은 팬 구동 불량, Label은 Cause라고 적겠습니다.', new_node('팬 구동 불량')),
 (6, '이것도 원인이니 화살표를 누르고 Reverse로 뒤집은 다음, CAUSES라고 적을게요.', [['edge', '쿨러 냉각 성능 상실', '팬 구동 불량'], ['click', 'reverse'], ['click', 'type'], ['type', 'CAUSES']]),
 (6, '이 원인의 판별 기준도 적을게요. 팬 구동 불량 원을 선택하고 Property 더하기를 누르겠습니다.', [['click', 'node:팬 구동 불량'], ['click', 'propPlus']]),
 (6, '왼쪽 칸에 팬 진동, 오른쪽 칸에 2분 평균 0.9 이상이라고 적을게요.', [['click', 'propKey'], ['type', '팬 진동'], ['click', 'propVal'], ['type', '2분 평균 ≥ 0.9 mm/s']]),
 (6, '같은 팬 진동을 보지만 핀 오염은 0.9 미만, 팬 구동 불량은 0.9 이상이에요. 증거는 같아도 조건이 반대입니다.', [['at', 0.15], ['point', 'props:쿨러 핀 오염'], ['at', 0.45], ['point', 'props:팬 구동 불량']]),
 (6, '팬 쪽 원인에는 팬 점검이 맞는 조치예요. 쿨러 냉각 성능 상실에서 하나 더 끌어낼게요.', grow('쿨러 냉각 성능 상실', 25)),
 (6, 'Caption은 팬 점검, Label은 Skill이라고 적을게요.', new_node('팬 점검')),
 (6, '화살표를 누르고 REMEDIED_BY라고 적겠습니다.', name_edge('쿨러 냉각 성능 상실', '팬 점검', 'REMEDIED_BY')),
 (6, '팬 점검에서 팬 구동 불량 위로 끌어 놓고 ADDRESSES라고 적을게요.', [['click', 'node:팬 점검'], ['connect', '팬 점검', '팬 구동 불량'], ['click', 'type'], ['type', 'ADDRESSES']]),
 (6, '근거 문서도 이어 둘게요. 팬 점검에서 오른쪽으로 끌어낼게요.', grow('팬 점검', 10)),
 (6, 'Caption은 매뉴얼 8.1절 팬 벨트 점검, Label은 ManualSection이라고 적을게요.', new_node('HM-8.1 팬 벨트 점검')),
 (6, '화살표를 누르고 REFERS_TO라고 적겠습니다.', name_edge('팬 점검', 'HM-8.1 팬 벨트 점검', 'REFERS_TO')),
 (7, '원이 많아져서 화살표가 얽혔죠. 흐름이 보이도록 정리해 볼게요. 먼저 빈 곳을 눌러 선택을 풀겠습니다.', [['click', 'blank']]),
 (7, '자리를 만들려고 원 크기를 조금 줄일게요. 오른쪽 STYLE의 Customize에서 radius를 70에서 47로 바꾸고 Tab 키로 확정하겠습니다.', [['click', 'customize'], ['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '47'], ['key', 'Tab']]),
 (7, '이제 원 가운데를 잡고 하나씩 옮겨서 왼쪽에서 오른쪽으로 읽히게 놓겠습니다. 원을 옮겨도 화살표는 그대로 따라와요.', [['layout', [["팬 구동 불량", 593, -136], ["HM-8.7 근본 조치", 1106, 173], ["HM-8.5 즉시 완화 조치", 960, 576], ["오일 쿨러", 220, 220], ["유온 센서 TS1", 220, 485], ["유온 상승", 485, 485], ["쿨러 냉각 성능 상실", 485, 220], ["쿨러 핀 오염", 817, 373], ["팬 최대 운전", 685, 526], ["쿨러 핀 세척", 847, 173], ["팬 점검", 799, 21], ["HYD-01 유압 파워팩", 0, 220], ["HM-8.1 팬 벨트 점검", 1089, -7]], ['HYD-01 유압 파워팩', 'HM-8.1 팬 벨트 점검']]]),
 (7, '다 됐네요. 오른쪽 위의 줄 세 개 버튼을 누르면 패널이 접혀서 그림을 넓게 볼 수 있어요.', [['click', 'panelToggle']]),
 (7, '쿨러 냉각 성능 상실로 들어오는 CAUSES를 거슬러 가면 원인 후보가 두 개 나와요. 핀 오염과 팬 구동 불량이죠. 화살표를 뒤집지 않아도 거꾸로 따라가며 찾을 수 있습니다.', [['at', 0.1], ['point', 'look:쿨러 냉각 성능 상실'], ['at', 0.45], ['point', 'look:쿨러 핀 오염'], ['at', 0.6], ['point', 'look:팬 구동 불량']]),
 (7, '냉각 효율이 낮은데 팬 진동 2분 평균이 0.9 이상이라면 어떨까요? 핀 오염 조건은 진동이 0.9 미만이어야 하니 맞지 않아요. 팬 구동 불량 쪽으로 가서 팬 점검과 매뉴얼 8.1절을 확인하면 됩니다.', [['at', 0.3], ['point', 'props:쿨러 핀 오염'], ['at', 0.62], ['point', 'look:팬 구동 불량'], ['at', 0.78], ['point', 'look:팬 점검'], ['at', 0.9], ['point', 'look:HM-8.1 팬 벨트 점검']]),
 (7, '팬 진동 자료를 아직 못 받았다면요? 냉각 효율이 낮으면 핀 오염을 먼저 의심하지만, 진동 조건을 확인하기 전에는 원인을 정할 수 없어요. 핀 세척도 팬 점검도 아직 고르지 않고 진동 자료부터 확인합니다.', [['at', 0.25], ['point', 'props:쿨러 핀 오염'], ['at', 0.7], ['point', 'look:쿨러 핀 세척'], ['at', 0.8], ['point', 'look:팬 점검']]),
 (7, '이렇게 그림이 있으면 어떤 값을 더 봐야 하는지, 어느 조치로 가야 하는지 따라갈 수 있어요.', []),

 (8, '이제 저장할게요. 위쪽 Download / Export를 누르겠습니다.', [['click', 'export']]),
 (8, 'JSON 탭은 나중에 다시 편집할 수 있는 데이터예요. JSON을 누르고 Download로 내려받을게요.', [['click', 'tab:JSON'], ['download', 'json']]),
 (8, 'PNG 탭에서는 그림 파일을 받을 수 있어요. PNG를 누르고 Download를 누르겠습니다.', [['click', 'tab:PNG'], ['download', 'png']]),
 (8, 'Done을 눌러 그림으로 돌아갈게요.', [['click', 'done']]),
 (8, '저장한 데이터가 제대로 열리는지 새 그림에서 확인해 볼게요. 왼쪽 위 로고 메뉴를 누르겠습니다.', [['click', 'logo']]),
 (8, 'New에 마우스를 올리고 Web Browser storage를 누르면 빈 그림이 새로 열려요.', [['point', 'menu:New'], ['click', 'menu:newLocal']]),
 (8, '다시 로고 메뉴를 열고 Import를 누를게요.', [['click', 'logo'], ['click', 'menu:Import']]),
 (8, 'Choose File을 눌러 방금 내려받은 JSON 파일을 고르겠습니다.', [['choose', 'json']]),
 (8, '아래 Import 버튼을 누르면 그림이 들어옵니다.', [['click', 'importButton']]),
 (8, '새 그림에 처음부터 있던 빈 원이 하나 남아 있네요. 이 원을 눌러 선택하고 Delete 키로 지우겠습니다.', [['click', 'node:'], ['key', 'Delete']]),
 (8, '원 열세 개와 화살표 열다섯 개, 원인의 조건까지 그대로 돌아왔네요.', [['verify'], ['at', 0.3], ['point', 'look:쿨러 핀 오염'], ['at', 0.6], ['point', 'look:팬 구동 불량']]),

 (9, '저장한 데이터는 이렇게 다시 열어서 이어서 고칠 수 있어요. 오른쪽 위의 줄 세 개 버튼을 눌러 패널을 다시 열게요.', [['click', 'panelToggle']]),
 (9, '매뉴얼 8.4절에는 원인이 하나 더 있었죠. 주변 온도가 높아서 냉각이 안 되는 경우예요. 쿨러 냉각 성능 상실에서 왼쪽 위로 원을 끌어낼게요.', grow('쿨러 냉각 성능 상실', -125)),
 (9, 'Caption은 주변 온도 상승, Label은 Cause라고 적을게요.', new_node('주변 온도 상승')),
 (9, '원인이니까 화살표를 누르고 Reverse로 뒤집은 다음, CAUSES라고 적겠습니다.', [['edge', '쿨러 냉각 성능 상실', '주변 온도 상승'], ['click', 'reverse'], ['click', 'type'], ['type', 'CAUSES']]),
 (9, '판별 기준도 적을게요. 주변 온도 상승 원을 선택하고 Property 더하기를 누르겠습니다.', [['click', 'node:주변 온도 상승'], ['click', 'propPlus']]),
 (9, '왼쪽 칸에 캐비닛 온도, 오른쪽 칸에 2분 평균 35도 이상이라고 적을게요.', [['click', 'propKey'], ['type', '캐비닛 온도'], ['click', 'propVal'], ['type', '2분 평균 ≥ 35 ℃']]),
 (9, '주변 온도가 원인이면 조치는 캐비닛 환기 보강이에요. 주변 온도 상승에서 옆으로 원을 하나 끌어낼게요.', grow('주변 온도 상승', 180)),
 (9, 'Caption은 캐비닛 환기 보강, Label은 Skill이라고 적을게요.', new_node('캐비닛 환기 보강')),
 (9, '조치가 원인을 해결하는 방향이니 화살표를 누르고 Reverse로 뒤집은 뒤 ADDRESSES라고 적겠습니다.', [['edge', '주변 온도 상승', '캐비닛 환기 보강'], ['click', 'reverse'], ['click', 'type'], ['type', 'ADDRESSES']]),
 (9, '쿨러 냉각 성능 상실에서 캐비닛 환기 보강 위로 끌어 놓고 REMEDIED_BY라고 적을게요.', [['click', 'node:쿨러 냉각 성능 상실'], ['connect', '쿨러 냉각 성능 상실', '캐비닛 환기 보강'], ['click', 'type'], ['type', 'REMEDIED_BY']]),
 (9, '근거는 핀 세척과 같은 매뉴얼 8.7절이에요. 캐비닛 환기 보강에서 HM-8.7 위로 끌어 놓고 REFERS_TO라고 적겠습니다.', [['click', 'node:캐비닛 환기 보강'], ['connect', '캐비닛 환기 보강', 'HM-8.7 근본 조치'], ['click', 'type'], ['type', 'REFERS_TO']]),
 (9, '이제 원인이 세 가지가 됐네요. 같은 고장이라도 캐비닛 온도, 팬 진동, 냉각 효율을 보고 어느 가지로 갈지 정하는 거예요.', [['at', 0.2], ['point', 'look:주변 온도 상승'], ['at', 0.45], ['point', 'look:팬 구동 불량'], ['at', 0.7], ['point', 'look:쿨러 핀 오염']]),
 (9, '종류가 한눈에 보이도록 색을 칠해 볼게요. 쿨러 핀 오염을 누르고, Ctrl 키를 누른 채 나머지 원인 두 개를 눌러 함께 선택하겠습니다.', [['click', 'node:쿨러 핀 오염'], ['ctrlclick', 'node:팬 구동 불량'], ['ctrlclick', 'node:주변 온도 상승']]),
 (9, '오른쪽 STYLE의 node-color 칸에 연한 빨간색 색상값을 적고 Tab 키로 확정할게요.', [['click', 'style:node-color'], ['key', 'ControlOrMeta+A'], ['type', '#fde2e2'], ['key', 'Tab']]),
 (9, '조치 원 네 개도 같은 방법으로 함께 선택해서 연한 초록색을 칠하겠습니다.', [['click', 'node:팬 최대 운전'], ['ctrlclick', 'node:쿨러 핀 세척'], ['ctrlclick', 'node:팬 점검'], ['ctrlclick', 'node:캐비닛 환기 보강'], ['click', 'style:node-color'], ['key', 'ControlOrMeta+A'], ['type', '#dcfce7'], ['key', 'Tab']]),
 (9, '원인은 빨간색, 조치는 초록색이라 어느 쪽인지 바로 구별되네요. 빈 곳을 눌러 선택을 풀겠습니다.', [['click', 'blank']]),
 (9, '이 그림은 데이터베이스에 넣는 명령으로도 바꿀 수 있어요. 위쪽 Download / Export를 누르고 Cypher 탭을 누르겠습니다.', [['click', 'export'], ['click', 'tab:Cypher']]),
 (9, 'CREATE로 시작하는 문장이 보이죠. 원과 관계, 조건이 Neo4j에 바로 넣을 수 있는 명령으로 바뀌었어요. 이 형태는 다음 실습에서 직접 다뤄 보겠습니다.', [['at', 0.15], ['point', 'cypherText']]),
 (9, '고친 그림도 저장해 둘게요. JSON 탭을 누르고 Download로 내려받겠습니다.', [['click', 'tab:JSON'], ['download', 'json', '쿨러_지식그래프_보강']]),
 (9, 'Done을 눌러 그림으로 돌아갈게요.', [['click', 'done']]),
 (9, '이 그림은 다음 실습에서 대상과 관계를 더 구체적으로 정리할 때 그대로 이어 쓰겠습니다.', []),
]

def cues():
    out = []
    for i, (seg, text, ops) in enumerate(CUES, 1):
        out.append({'id': f'o{i:03}', 'segment': seg, 'text': text, 'ops': ops})
    return out

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
EVID = REPO / '.evidence' / 'arrows-ontology-20261023'
VIDEO = EVID / 'ARROWS-온톨로지-최종'
SEGMENT_TITLE = {9: '다시 열어 보강 · 세 번째 원인 · 색 · Cypher', 1: 'arrows.app 열기 · 원 크기 · 첫 원', 2: '구성 요소 · 센서 · 첫 관계', 3: '증상 · 고장 유형', 4: '원인 · 조건 · 조치',
                 5: '매뉴얼 절', 6: '팬 구동 불량 가지', 7: '배치 정리 · 완성 그림 읽기', 8: '저장 · 다시 열기'}
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
    if k == 'layout':
        return '원 가운데를 잡아 차례로 옮기기: ' + ', '.join(m[0] for m in a[0]) + ' (왼쪽→오른쪽 흐름, 화살표 교차 없음)'
    if k == 'download':
        return 'Download 클릭 → 파일 저장 확인'
    if k == 'ctrlclick':
        return f'Ctrl 누른 채 ‘{a[0][5:]}’ 원 클릭(함께 선택)'
    if k == 'choose':
        return 'Choose File로 방금 저장한 JSON 선택'
    if k == 'verify':
        return '원 13 · 화살표 15 · 원인 조건 속성 복원 확인'
    return k


def manuscript():
    out = ['''# ARROWS 실습 — 쿨러 고장의 지식 그래프 그리기

2026-10-23 촬영판. 교재 SLIDE 64(지식 그래프 지도) · 70 · 71(핀 오염 기본도 → 팬 구동 불량 가지 → 비교 · 저장 · 다시 열기)의 실습이다. 다시 연 그림에 HM-8.4의 세 번째 원인(주변 온도 상승) 가지, 종류별 색칠, Cypher 내보내기를 이어 간다. 두 과정 공통.

## 진행 메모 — 낭독하지 않음

- 실제 촬영한 큐 그대로다. 표 왼쪽 발화로 대상과 행동을 먼저 알리고, 행동 문장이 끝나기 약 0.25초 전에 오른쪽 조작을 실행한 뒤 결과가 보이면 다음 발화로 간다.
- 원 위치는 고정 좌표가 아니다. 테두리 끌기로 원을 만들 때 빈 곳을 찾아 놓고, 7구간에서 흐름이 보이게 정리한다. arrows.app은 그림 전체를 화면에 자동으로 맞춘다.
- 첫 원만 Add Node로 만들고 나머지는 원 테두리를 빈 곳으로 끌어 원과 화살표를 함께 만든다. 원인 → 고장(CAUSES)과 증상 → 센서(OBSERVED_BY)는 만든 뒤 Reverse로 방향을 뒤집는다.
- 입력값 출처: 클래스 · 관계 이름은 `문서/시스템/참조/ontology/schema-v2.md` · `it/neo4j/v2/instances.cypher`, 판별 기준은 랩 `매뉴얼_발췌.md` HM-8.4, 조치 근거는 HM-8.1 · 8.5 · 8.7.
- 영상: `.evidence/arrows-ontology-20261023/ARROWS-온톨로지-최종/ARROWS-온톨로지-최종_안치윤_1080p.mp4`(로컬 근거, Git 미포함). 구간 · 시간 · 측정은 제작용 [예상시간](예상시간.md).
''']
    seg = 0
    for c in cues():
        if c['segment'] != seg:
            seg = c['segment']
            out.append(f'\n## {seg}구간 · {SEGMENT_TITLE[seg]}\n\n| 발화 | 조작·결과 확인 — 비낭독 |\n|---|---|')
        acts = [x for x in (act(o) for o in c['ops']) if x]
        out.append(f"| {c['text']} | {' → '.join(acts) if acts else '—'} |")
    out.append('\n# 촬영 본문 끝\n\n## 제작 확인용 — 낭독하지 않음\n\n'
               '- 판별 조건은 HM-8.4 원문 기준이다(핀 오염: CE 30초 평균 < 70 % 이고 VS1 2분 평균 < 0.9 mm/s, 팬 구동 불량: VS1 2분 평균 ≥ 0.9 mm/s, 주변 온도 상승: TS4 2분 평균 ≥ 35 ℃). 캐비닛 환기 보강은 랩 발췌 HM-8.7의 SOP-COOL-15다. 이번 그림은 판별 기준을 담은 지식 구조이며 새 진단 실행 결과가 아니다.\n'
               '- REFERS_TO는 실제 데이터에서 Skill → Step → ManualSection 두 단계(HAS_STEP · REFERS_TO)다. 교재 지도처럼 한 번에 이었다고 영상에서 말한다.\n'
               '- 7구간 배치는 사용자가 정한 완성 배치를 비율대로 줄여 따랐다(원 크기 70 → 47). 9구간의 캐비닛 환기 보강 → HM-8.7 화살표는 그림을 가로지른다(사소, 유지).\n')
    return '\n'.join(out) + '\n'


def write_all():
    import hashlib, html, re, shutil, zipfile
    final = json.loads((EVID / 'saved' / '쿨러_지식그래프_보강.json').read_text(encoding='utf-8'))
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
측정: 이동 {ver['motion_summary']['count']}회 중 최대 프레임 공백 {ver['motion_summary']['max_gap_ms_max']}ms, 100ms 이상 {len(ver['motion_summary']['over_100ms'])}회(7구간 원 크기 변경 직후 다시 그리기). 문장 끝보다 늦게 실행된 조작 0건.
영상 안에는 원 끌어내기를 한 번 헛잡고 다시 잡는 장면(4구간)이 그대로 있다. 직접 청취 · 사용자 재생 확인은 미확인이다.
'''
    (ROOT / '예상시간.md').write_text(timing, encoding='utf-8')
    nodes_md = '# 쿨러 지식 그래프 — 그릴 대상과 관계\n\n교재 SLIDE 64의 클래스로 오일 쿨러 사례를 그린다. 아래는 촬영에서 실제로 만들어 내려받은 완성본(`완성_쿨러_지식그래프.json`)의 내용이다. 직접 만든 결과와 구별하는 참조본이다.\n\n| 이름(Caption) | 종류(Label) | 조건(Property) |\n|---|---|---|\n'
    for n in final['nodes']:
        props = ' / '.join(f'{k}: {v}' for k, v in n.get('properties', {}).items())
        nodes_md += f"| {n['caption']} | {', '.join(n['labels'])} | {props or '—'} |\n"
    nodes_md += '\n## 관계 — 출발 · 이름 · 도착\n\n| 출발 | 관계 이름(Type) | 도착 | 문장으로 읽기 |\n|---|---|---|---|\n'
    reads = {'HAS_COMPONENT': '구성 요소로 가진다', 'MONITORED_BY': '로 계측된다', 'OBSERVED_BY': '에서 관측된다', 'INDICATES': '를 가리킨다', 'OCCURS_IN': '에서 일어난다',
             'CAUSES': '를 일으킨다', 'MITIGATED_BY': '로 완화된다', 'REMEDIED_BY': '로 근본 해결된다', 'ADDRESSES': '를 해결 대상으로 한다', 'REFERS_TO': '의 근거로 이어진다'}
    for r in final['relationships']:
        nodes_md += f"| {by[r['fromId']]} | {r['type']} | {by[r['toId']]} | {reads.get(r['type'], '')} |\n"
    nodes_md += '\n출처: 클래스 · 관계 `문서/시스템/참조/ontology/schema-v2.md`, 이름 `it/neo4j/v2/instances.cypher`, 조건 `매뉴얼_발췌.md` HM-8.4, 조치 근거 HM-8.1 · 8.5 · 8.7.\n'
    review = '''# 관계 검토표 — 쿨러 지식 그래프

| 출발 | 관계 이름 | 도착 | 문장으로 읽은 뜻 | 원문 근거 | 고칠 부분 |
|---|---|---|---|---|---|
| | | | | | |

## 확인할 것

- 쿨러 냉각 성능 상실로 들어오는 CAUSES를 거슬러 원인 후보 세 개(핀 오염 · 팬 구동 불량 · 주변 온도 상승)를 찾을 수 있는가. 화살표를 뒤집지 않고 거슬러 읽었는가.
- 세 원인의 판별 조건이 HM-8.4와 같은가: 핀 오염은 냉각 효율 30초 평균 < 70 % 이고 팬 진동 2분 평균 < 0.9 mm/s, 팬 구동 불량은 팬 진동 2분 평균 ≥ 0.9 mm/s, 주변 온도 상승은 캐비닛 온도 2분 평균 ≥ 35 ℃.
- 팬 최대 운전(완화)과 핀 세척 · 팬 점검 · 캐비닛 환기 보강(근본 조치)을 구별했는가. 각 근본 조치가 맞는 원인에만 ADDRESSES로 이어졌는가.
- 원인 · 조치를 색으로 구별했는가. Cypher로 내보낸 문장에서 원 · 관계 · 조건을 찾을 수 있는가.
- 조치마다 매뉴얼 절(HM-8.5 · 8.7 · 8.1)로 근거가 이어졌는가(캐비닛 환기 보강도 HM-8.7).
- 팬 진동이 0.9 이상이면 어느 가지로 가는가. 팬 진동 자료가 없으면 왜 원인을 정하지 않고 보류하는가.

## 저장 확인

편집 데이터 JSON / 그림 PNG / 새 그림에서 Import로 다시 연 결과(원 · 화살표 · 조건 수) / 고친 점:
'''
    screens = f'''# 화면 — 촬영 완료

2026-10-23 촬영 영상(로컬 근거) `{VIDEO.relative_to(REPO).as_posix()}/` 의 실제 화면이다. 완성 그림은 `완성_쿨러_지식그래프.png`, 편집 데이터는 `완성_쿨러_지식그래프.json`(촬영 중 arrows.app에서 내려받은 참조본).

| 구간 | 보여 준 것 | 확인한 결과 |
|---|---|---|
''' + ''.join(f'| {k} | {v} | 실제 화면 |\n' for k, v in SEGMENT_TITLE.items())
    record = '''# 실습 기록 — 쿨러 지식 그래프

- 그린 원 · 관계 수:
- 두 원인의 판별 조건과 근거 절:
- 완화 조치와 근본 조치의 구별:
- 팬 진동 ≥ 0.9일 때 따라간 경로:
- 자료가 없을 때 보류한 이유:
- 저장한 JSON · PNG 파일 이름과 다시 연 결과:
'''
    for course in ['실전반', '통합반']:
        day = REPO / '산출물' / course / '실습/01회차'
        lab = day / '랩/01일차_실습4_관계그림'
        (day / '대본/08_실습_관계그림.md').write_text(script.replace('(예상시간.md)', '(../랩/01일차_실습4_관계그림/예상시간.md)'), encoding='utf-8')
        for name, content in [('대상_목록.md', nodes_md), ('관계_검토표.md', review), ('채울_화면.md', screens), ('실습_기록.md', record), ('예상시간.md', timing.replace('[수업원고](수업원고.md)', '[대본](../../대본/08_실습_관계그림.md)'))]:
            (lab / name).write_text(content, encoding='utf-8')
        shutil.copyfile(EVID / 'saved' / '쿨러_지식그래프_보강.json', lab / '완성_쿨러_지식그래프.json')
        shutil.copyfile(EVID / 'saved' / '쿨러_지식그래프_보강.png', lab / '완성_쿨러_지식그래프.png')
        body = []
        for line in script.split('# 촬영 본문 끝')[0].split('## 진행 메모 — 낭독하지 않음')[0].splitlines()[2:]:
            body.append(line)
        steps = ''
        seg = 0
        for c in cues():
            if c['segment'] != seg:
                if seg:
                    steps += '</tbody></table>'
                seg = c['segment']
                steps += f'<h2>{seg}. {html.escape(SEGMENT_TITLE[seg])}</h2><table><tbody>'
            acts = [x for x in (act(o) for o in c['ops']) if x]
            steps += f"<tr><td>{html.escape(c['text'])}</td><td>{html.escape(' → '.join(acts) if acts else '—')}</td></tr>"
        steps += '</tbody></table>'
        guide = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ARROWS — 쿨러 고장의 지식 그래프</title><style>body{{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:1120px;margin:36px auto;padding:0 24px;color:#22303e}}table{{width:100%;border-collapse:collapse;table-layout:fixed;margin:16px 0}}td{{border:1px solid #cbd5e1;padding:10px;vertical-align:top;overflow-wrap:anywhere}}td:last-child{{color:#475569;font-size:15px}}h2{{margin-top:36px}}img{{max-width:100%;border:1px solid #cbd5e1}}a{{color:#145ca4}}aside{{background:#f0f4f7;padding:12px}}</style></head><body>
<h1>쿨러 고장의 지식 그래프 그리기</h1><p>교재의 지식 그래프 지도(설비 · 구성 요소 · 센서 · 증상 · 고장 유형 · 원인 · 조치 방법 · 매뉴얼 절)를 오일 쿨러 사례로 arrows.app에 직접 그립니다. 핀 오염 가지를 그린 뒤 팬 구동 불량 가지를 더해 증거와 조치를 비교하고, 저장한 데이터를 다시 열어 세 번째 원인(주변 온도 상승)을 이어 그립니다. 종류별로 색을 칠하고 Cypher 명령으로 내보내 봅니다.</p>
<nav><a href="대상_목록.md">대상 · 관계</a> · <a href="매뉴얼_발췌.md">판별 기준 · 조치 근거(HM-8)</a> · <a href="관계_검토표.md">검토표</a> · <a href="예상시간.md">시간</a> · <a href="실습_기록.md">기록</a> · <a href="완성_쿨러_지식그래프.json">완성 참조 JSON</a></nav>
<h2>완성 그림(참조)</h2><p><img src="완성_쿨러_지식그래프.png" alt="완성된 쿨러 지식 그래프"></p><aside>촬영 중 arrows.app에서 실제로 내려받은 완성본입니다. 직접 그린 결과와 대조하는 참조본이며, 처음부터 열어 쓰는 시작 파일이 아닙니다.</aside>
<p>왼쪽은 강사가 하는 말, 오른쪽은 그때 하는 조작입니다.</p>{steps}
</body></html>'''
        (lab / '가이드.html').write_text(guide, encoding='utf-8')
        zip_path = lab.with_suffix('.zip')
        with zipfile.ZipFile(zip_path) as old:
            first = old.namelist()[0]
            prefix = first.split(lab.name + '/')[0] + lab.name + '/'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(lab.rglob('*')):
                if f.is_file():
                    z.write(f, prefix + f.relative_to(lab).as_posix())
        with zipfile.ZipFile(zip_path) as z:
            names = set(z.namelist())
            for f in lab.rglob('*'):
                if f.is_file():
                    assert z.read(prefix + f.relative_to(lab).as_posix()) == f.read_bytes(), f
            assert len(names) == sum(1 for f in lab.rglob('*') if f.is_file()), zip_path
        for href in re.findall(r'(?:href|src)="([^"]+)"', guide):
            assert (lab / href).is_file(), href
    files = [ROOT / '수업원고.md', ROOT / '예상시간.md'] + [REPO / '산출물' / c / '실습/01회차' / x for c in ['실전반', '통합반'] for x in
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
