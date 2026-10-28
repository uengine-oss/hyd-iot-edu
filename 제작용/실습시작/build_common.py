"""온라인2 과정별 조회 안내와 포털 탐색의 시작본을 연결."""
from build_labs import ROOT,OUT,COURSES,page,write,dump,pack,RULES
from pathlib import Path
import json,hashlib,shutil,html,argparse
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--course',choices=[name for name,_ in COURSES])
parser.add_argument('--lab',choices=['relations','map'],help='변경한 실습만 재생성한다. 생략하면 기존처럼 두 실습을 만든다.')
args=parser.parse_args()
active_courses=[item for item in COURSES if args.course is None or item[0]==args.course]
catalog=json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
ids={f'{slug}-02-{kind}' for _,slug in active_courses for kind in ['relations','map'] if args.lab is None or args.lab==kind}
catalog['labs']=[x for x in catalog['labs'] if x['id'] not in ids]
for course,slug in active_courses:
    for number,name,title,kind in [(1,'02일차_실습1_관계조회','관계를 따라 센서와 부품 조회하기','relations'),(2,'02일차_실습2_지식지도탐색','포털에서 기준 지식의 연결 탐색하기','map')]:
        if args.lab is not None and args.lab!=kind:continue
        folder=OUT/course/'실습/02회차/랩'/name
        write(folder/'결과/README.md','작성한 질의와 실제 확인 기록을 여기에 보관합니다.\n')
        rules=RULES.replace('입력/와 자료/는 보존한다.','제공 예제와 원자료는 보존한다.')
        if number==1:
            for file in ['lab_db.py','prepare_example.py']:shutil.copy2(HERE/file,folder/file)
            write(folder/'준비_안내.md', '''# 관계 조회 준비

Docker를 실행하고 VS Code 터미널에서 `python prepare_example.py`를 실행합니다. 이 폴더 전용 랩 DB를 만들고 제공 예제를 적재합니다. HYD 포털 DB와 다른 실습의 DB는 사용하지 않습니다. 접속 주소는 터미널과 랩_연결.json에서 확인합니다.

예제_그래프.json과 예제_적재.cypher는 HYD-01의 구성·계측 채널을 발췌한 교육용 부분집합입니다. 시계열 실측값이 아닙니다. 제공 예제를 준비한 뒤 조회_작성.cypher에 직접 질의를 작성합니다.

준비 완료 표시는 노드 20개·관계 19개입니다. 설비 1개, 구성요소 6개, 센서 5개, 상태 변수 5개, 부품 3개로 구성됩니다. 쿨러 센서는 TS1·CE, 주 펌프 센서는 PS1·FS1, 팬 센서는 VS1입니다. 나머지 구성요소는 이 예제에서 센서가 없습니다.

교체 부품은 쿨러 코어(P-CLR-CORE), 펌프 축 씰 키트(P-PMP-SEAL), 팬 베어링(P-FAN-BRG)입니다. USES_PART의 방향과 품번을 원자료에서 확인합니다. 예제의 virtual·kind는 원본 스키마의 속성입니다.
''')
            steps='''1. Docker를 실행하고 VS Code 터미널에서 `python prepare_example.py`를 실행합니다.
2. 「예제 준비 완료: 노드 20개 · 관계 19개」를 확인합니다.
3. `python lab_db.py`를 실행해 Browser를 열고 출력된 Connect URL로 연결합니다. Username은 neo4j, Password는 비워 둡니다.
4. 조회_작성.cypher의 여섯 질문에 맞춰 질의를 작성하고 한 문장씩 실행합니다.
5. 조회_기록.md에 실제 행·집계·원자료 근거를 적고 결과/에 질의와 기록을 저장합니다.'''
            sections=[('예제 준비하기','<p>VS Code 터미널에서 실행하세요.</p><pre>python prepare_example.py</pre><p class="check">예제 준비 완료: 노드 20개 · 관계 19개가 표시됩니다. 이 예제는 HYD-01 한 대의 설비 구성입니다.</p><pre>python lab_db.py</pre><p>열린 Browser의 Connect URL에 터미널의 bolt 주소를 넣으세요. Username은 neo4j, Password는 비워 둡니다.</p>'),('쿨러에서 센서 찾기',"<p>Browser 입력칸에 아래 질의를 넣고 Run을 누르세요. 조회_작성.cypher에도 저장합니다.</p><pre>MATCH (c:Component {id:'comp:cooler'})-[:MONITORED_BY]-&gt;(s:Sensor)\nRETURN c.id, c.name, s.id, s.tag;</pre><p class=\"check\">센서 TS1과 CE 두 행이 나옵니다. 반복된 쿨러 ID는 같은 출발점입니다.</p><p>관계에 변수 r을 붙이고 c, r, s를 반환하도록 바꿔 표와 그래프의 대상을 비교하세요.</p>"),('설비에서 물리량·부품 따라가기','<p>HYD-01에서 구성요소 → 센서 → StateVariable까지 연결해 태그·물리량·단위·한계를 조회하세요. 한계가 있는 행만 남겼을 때 빠지는 항목을 기록합니다.</p><p class="check">센서는 5개이며 한계가 없는 CE·FS1도 원래 조회에는 포함됩니다. 값 없음과 0을 구별하세요.</p><p>이번에는 구성요소의 USES_PART 관계로 부품과 partNo를 조회하세요.</p><p class="check">쿨러 코어 P-CLR-CORE, 펌프 축 씰 키트 P-PMP-SEAL, 팬 베어링 P-FAN-BRG의 세 연결을 원자료와 대조합니다.</p>'),('집계와 원래 행 비교하기','<p>구성요소별로 서로 다른 센서를 세고 원래 센서 ID 목록과 비교하세요.</p><p class="check">쿨러 2개, 주 펌프 2개, 팬 1개입니다. 센서까지 연결되는 MATCH에는 센서가 없는 구성요소가 나오지 않습니다.</p><p>조회_기록.md의 표에 원래 목록·직접 센 수·질의 결과를 기록합니다.</p>'),('저장하기','<p>질의와 기록을 결과/에 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드로 복사합니다.</p><p>다음 포털 탐색은 별도 시작본으로 엽니다.</p>')]
        elif course=='통합반':
            # 실라버스 통합반 21행: 설비 선택→센서·부품 펼치기→ID·속성·관계 방향→같은 이름과 다른 식별자→랩 모델과 기준 지도 비교.
            # 지식 지도는 고른 설비 하나와 설비에 묶이지 않은 지식 노드를 그린다(it/neo4j/templates/t0_graph_nodes.cypher).
            # 포털 기준 모델은 같은 모델 세 대가 구성요소·센서 노드를 함께 쓴다(it/neo4j/v2/instances.cypher).
            steps='''1. 학교 PC에 준비된 HYD 포털에서 지식 지도를 엽니다. 기본 로컬 주소는 http://127.0.0.1:8088 입니다.
2. 설비 HYD-01을 선택하고 자원 칸의 오일 쿨러를 누릅니다. 강조된 연결과 상세 칸의 나가는 관계·들어오는 관계에서 센서와 교체 부품을 찾아 ID·클래스·속성을 탐색_기록.md에 적습니다.
3. 관계 이름과 화살표 방향을 시작 ID → 끝 ID로 적습니다.
4. 이름 TS1이 센서와 상태 변수 양쪽에 보이면 두 노드의 ID와 클래스를 나란히 적어 서로 다른 대상인지 판단합니다.
5. 설비를 HYD-02로 바꿔 같은 센서 노드가 이어지는지 보고, 포털 기준 지도가 세 설비를 어떻게 표현하는지 적습니다. 다음 실습에서 설비별로 센서를 구별하는 모델을 만들 때 비교할 질문을 남깁니다.
6. 현재 화면에서 확인한 것만 기록하고 결과/에 저장합니다. 편집·설비 조작·명령 승인은 하지 않습니다.'''
            sections=[('지식 지도 열기','<p><a href="http://127.0.0.1:8088" target="_blank" rel="noopener">학교 PC의 HYD 포털 열기</a></p><p>포털의 지식 지도를 열고 HYD-01을 선택하세요. 학교에서 별도 주소를 안내받았다면 그 주소를 사용합니다.</p><p>탐색_기록.md에 포털 주소와 확인 시각을 적습니다. 앞 실습의 예제 DB와는 별개의 기준 그래프입니다.</p>'),('센서와 부품 찾기','<p>자원 칸에서 오일 쿨러를 누르세요. 연결된 관계가 강조되고 상세 칸에 나가는 관계와 들어오는 관계가 나옵니다. 센서와 교체 부품을 눌러 ID·클래스·속성을 기록합니다. 검색으로 이름을 찾아도 됩니다.</p><p class="check">이름만 적지 않고 대상 ID와 값을 함께 남깁니다. 화면에 표시되지 않은 항목은 미확인으로 둡니다.</p>'),('관계 방향 읽기','<p>쿨러와 센서, 쿨러와 부품 사이의 관계 이름을 시작 ID → 끝 ID로 적으세요. 화면에서 따라간 방향과 저장된 화살표 방향을 구별합니다.</p>'),('같은 이름, 다른 대상','<p>TS1이라는 이름이 센서와 상태 변수에 모두 보이면 두 노드의 ID와 클래스를 나란히 적으세요.</p><p class="check">이름이 같아도 ID와 클래스가 다르면 다른 대상입니다. 센서는 재는 장치, 상태 변수는 재는 값의 종류입니다.</p>'),('기준 지도와 다음 모델 비교','<p>설비를 HYD-02로 바꿔 같은 센서 노드가 다시 이어지는지 확인하세요. 포털 기준 지도가 같은 모델의 세 설비를 어떻게 표현하는지 기록합니다.</p><p>다음 실습에서는 설비별 센서를 구별하는 모델을 직접 만듭니다. 그때 비교할 질문을 하나 적어 두세요.</p>'),('기록 확인하고 저장하기','<p>설비 → 구성요소 → 센서, 구성요소 → 부품 경로를 기록에서 다시 읽어 보세요. 빠진 시작·끝 ID는 화면으로 돌아가 확인합니다.</p><p>결과/에 탐색 기록을 저장하고 다시 엽니다. 다음 모델 설계는 별도 시작본을 사용합니다.</p>')]
            write(folder/'탐색_기록.md','# 지식 지도 탐색 기록\n\n- 포털 주소와 확인 시각:\n- 선택한 설비:\n\n## 연결\n\n| 시작 ID·클래스 | 관계 이름 | 끝 ID·클래스 | 확인한 속성 | 화면에서 미확인 |\n|---|---|---|---|---|\n| | | | | |\n\n## 같은 이름, 다른 대상\n\n| 보이는 이름 | ID | 클래스 | 같은 대상인가와 이유 |\n|---|---|---|---|\n| | | | |\n\n## 설비를 바꿔 본 결과\n\n- HYD-02에서 같은 노드가 이어졌는가:\n- 기준 지도가 세 설비를 표현하는 방식:\n- 다음 모델에서 비교할 질문:\n')
        else:
            # 실라버스 실전반 21행: 부품·문서 연결, 한 부품을 쓰는 설비, 연결≠재고·공급 확보, 다음 랩에서 공급 자료로 답할 질문.
            # 지식 지도 실측(2026-10-28 촬영, it/portal/www/enterprise.js): 부품 상세 = partNo·나가는 공급사 3(avl만)·들어오는 6(교체 부품·원인·발주 조치 방법). 단가·납기·재고는 지도에 없다.
            steps='''1. 학교 PC에 준비된 HYD 포털에서 지식 지도를 엽니다. 기본 로컬 주소는 http://127.0.0.1:8088 입니다.
2. 설비 HYD-01을 선택하고 자원 칸에서 펌프 축 씰 키트(P-PMP-SEAL) 부품을 찾아 누릅니다. 부품을 쓰는 구성요소, 연결된 공급사와 관계의 속성, 이어지는 문서·매뉴얼 출처를 ID와 관계 이름으로 탐색_기록.md에 적습니다.
3. 설비를 HYD-02, HYD-03으로 바꿔 같은 부품이 이어지는지 확인하고 이 부품을 쓰는 설비를 적습니다.
4. 화면에 있는 것과 없는 것을 나눕니다. 공급 관계가 있어도 재고 수량·발주 상태는 지도에 없으면 확보 여부를 판단하지 않습니다.
5. 다음 실습에서 제공 공급 자료로 답할 질문을 두세 개 정해 적습니다.
6. 현재 화면에서 확인한 것만 기록하고 결과/에 저장합니다. 편집·설비 조작·명령 승인은 하지 않습니다.'''
            sections=[('지식 지도 열기','<p><a href="http://127.0.0.1:8088" target="_blank" rel="noopener">학교 PC의 HYD 포털 열기</a></p><p>포털의 지식 지도를 열고 HYD-01을 선택하세요. 학교에서 별도 주소를 안내받았다면 그 주소를 사용합니다.</p><p>탐색_기록.md에 포털 주소와 확인 시각을 적습니다.</p>'),('부품에서 연결 따라가기','<p>자원 칸이나 검색으로 펌프 축 씰 키트(P-PMP-SEAL)를 찾아 누르세요. 상세 칸의 나가는 관계·들어오는 관계에서 이 부품을 쓰는 구성요소, 연결된 공급사, 관계에 붙은 값, 이어지는 문서·매뉴얼 출처를 기록하세요.</p><p class="check">관계 이름과 시작 ID → 끝 ID를 함께 남깁니다. 화면에 표시되지 않은 연결은 미확인으로 둡니다.</p>'),('이 부품을 쓰는 설비','<p>설비를 HYD-02, HYD-03으로 바꿔 같은 부품이 이어지는지 확인하세요. 부품을 쓰는 설비를 모두 적습니다.</p>'),('연결과 확보를 구별하기','<p>공급 관계는 견적 조건입니다. 재고 수량이나 발주 상태가 지도에 없다면 부품이 확보됐다고 판단하지 않습니다. 화면에 있는 값과 없는 값을 나누어 적으세요.</p>'),('다음 실습의 질문 정하기','<p>다음 실습에서는 제공 공급 자료를 모델에 연결합니다. 그 모델로 답할 질문을 두세 개 정해 적으세요. 예: 이 부품을 쓰는 설비와 구성요소는 무엇인가.</p>'),('기록 확인하고 저장하기','<p>기록의 각 행에 시작·끝 ID와 확인 시각이 있는지 보세요. 결과/에 탐색 기록을 저장하고 다시 엽니다. 다음 모델 설계는 별도 시작본을 사용합니다.</p>')]
            if (folder/'images/map-01-search.jpg').exists():
                def shot(name,caption):return f'<figure><a href="images/{name}.jpg" target="_blank"><img src="images/{name}.jpg" alt="{caption}"></a><figcaption>{caption} · 누르면 크게 보기</figcaption></figure>'
                sections=[('기록 틀 준비하기','<p>실습 시작 도구가 연 VS Code에서 왼쪽 탐색기(Explorer)의 <code>탐색_기록.md</code>를 마우스 오른쪽 버튼으로 누르고 Copy를 고릅니다. 이어서 <code>결과</code> 폴더를 오른쪽 버튼으로 누르고 Paste를 고릅니다.</p><p class="check">결과 폴더 안에 <code>탐색_기록.md</code> 사본이 생깁니다. 원래 틀은 그대로 두고 사본을 열어 기록합니다.</p>'),
                 ('지식 지도에서 부품 찾기','<p><a href="http://127.0.0.1:8088" target="_blank" rel="noopener">학교 PC의 HYD 포털 열기</a> → 왼쪽 메뉴 지식 묶음의 「지식 지도」를 누릅니다. 위쪽 설비 칸이 HYD-01인지 확인하고, 검색 칸에 <code>씰</code>을 입력합니다.</p><p class="check">「검색 결과 7개」가 나오고 지도가 첫 결과로 옮겨 가 노랗게 표시합니다. 자원 묶음의 「펌프 축 씰 키트」를 누릅니다.</p>'+shot('map-01-search','검색 「씰」 뒤 노랗게 표시된 펌프 축 씰 키트')),
                 ('상세 칸 읽기','<p>상세 칸은 지도 <b>아래</b>에 나옵니다. 화면을 내려 종류(부품), partNo, 나가는 관계·들어오는 관계를 읽습니다. 관계 이름과 방향(→ 나가는, ← 들어오는)을 그대로 적습니다.</p><p class="check">partNo가 앞 실습에서 조회한 품번과 같은지 봅니다. 보이는 이름보다 품번이 같은 부품인지 판단하는 기준입니다.</p>'+shot('map-02-part','펌프 축 씰 키트의 partNo와 나가는·들어오는 관계')),
                 ('구성 요소를 거쳐 설비까지','<p>들어오는 관계에서 부품을 교체 부품으로 가리키는 구성 요소를 누릅니다. 그 구성 요소의 들어오는 관계에서 어느 설비의 구성 요소인지 확인합니다.</p><p class="check">설비 → 구성 요소 → 부품으로 이어지는 경로를 기록합니다. 링크를 누르면 상세 칸이 그 항목으로 바뀌고, 다시 부품 링크를 눌러 돌아올 수 있습니다.</p>'+shot('map-03-pump','구성 요소 상세의 교체 부품과 소속 설비')),
                 ('공급사의 승인 여부','<p>부품으로 돌아가 나가는 관계의 공급사를 하나씩 누릅니다. 공급사 상세의 <code>avl</code>은 승인 공급사 목록(Approved Vendor List)에 들어 있는지를 뜻합니다.</p><p class="check">공급사마다 avl 값을 적습니다. 단가·납기·재고 수량은 부품에도 공급사에도 없습니다 — 없는 값은 미확인으로 두고, 연결만으로 부품이 확보됐다고 판단하지 않습니다.</p>'+shot('map-04-supplier','공급사 상세의 avl 값과 들어오는 관계')),
                 ('설비를 바꿔 같은 부품 확인하기','<p>화면을 올려 설비 칸을 HYD-02로 바꿉니다. 검색어가 남아 있어 지도가 같은 부품을 다시 표시합니다. 부품 → 구성 요소를 눌러 소속 설비를 확인하고, HYD-03도 같은 방법으로 봅니다.</p><p class="check">설비마다 부품까지 이어진 경로를 「이 부품을 쓰는 설비」 표에 적습니다.</p>'+shot('map-05-hyd02','HYD-02에서 같은 구성 요소의 소속 설비')+shot('map-06-hyd03','HYD-03에서 같은 구성 요소의 소속 설비')),
                 ('기록하고 다음 질문 정하기','<p>결과/의 <code>탐색_기록.md</code>에 포털 주소·확인 시각·부품, 연결 표, 설비 표를 채웁니다. 「화면에 있는 것과 없는 것」에는 지도에서 확인한 공급 조건과 지도에 없어 판단하지 않은 값을 나눠 적습니다. 마지막으로 다음 실습에서 공급 자료로 답할 질문을 두세 개 적습니다.</p>'),
                 ('저장하고 다시 열기','<p><code>Ctrl+S</code>로 저장하고 탭을 닫았다가 결과 폴더에서 다시 엽니다.</p><p class="check">적은 내용이 그대로 남아 있습니다. 학교 PC는 재부팅하면 초기화되니 결과 폴더를 USB 또는 개인 클라우드에 복사합니다.</p>')]
            write(folder/'탐색_기록.md','# 지식 지도 탐색 기록 — 부품과 공급 연결\n\n- 포털 주소와 확인 시각:\n- 확인한 부품:\n\n## 부품에서 이어진 연결\n\n| 시작 ID·클래스 | 관계 이름 | 끝 ID·클래스 | 관계·노드의 값 | 화면에서 미확인 |\n|---|---|---|---|---|\n| | | | | |\n\n## 이 부품을 쓰는 설비\n\n| 선택한 설비 | 부품까지 이어진 경로 |\n|---|---|\n| | |\n\n## 화면에 있는 것과 없는 것\n\n- 지도에서 확인한 공급 조건:\n- 지도에 없어 판단하지 않은 것(재고·발주 등):\n\n## 다음 실습에서 답할 질문\n\n1.\n2.\n')
        if number==1:
            connection='열린 연결 창의 Protocol이 bolt://이고 Connection URL이 터미널의 현재 주소와 같은지 확인하세요. Database user는 neo4j, Password는 비워 두고 Connect를 누릅니다. 주소가 비어 있다면 터미널의 127.0.0.1:포트 값을 넣으세요.'
            sections[0]=(sections[0][0],sections[0][1].replace('열린 Browser의 Connect URL에 터미널의 bolt 주소를 넣으세요. Username은 neo4j, Password는 비워 둡니다.',connection))
            steps=steps.replace('열고 출력된 Connect URL로 연결합니다. Username은 neo4j, Password는 비워 둡니다.','엽니다. Protocol은 bolt://, Connection URL은 출력 주소의 127.0.0.1:포트 부분, Database user는 neo4j, Password는 빈칸으로 연결합니다.')
            def figure(name,caption):
                return f'<figure style="margin:24px 0"><a href="images/{name}.png" target="_blank"><img src="images/{name}.png" alt="{caption}" style="border:1px solid #dce5df;border-radius:8px"></a><figcaption><small>{caption} · 누르면 크게 보기</small></figcaption></figure>'
            sections[1]=(sections[1][0],sections[1][1]+figure('01-cooler','같은 쿨러에서 센서 CE·TS1 두 행 확인'))
            text=sections[2][1]
            text=text.replace('<p>이번에는 구성요소의 USES_PART 관계로',figure('02-quantity-compact','태그 5개와 물리량·단위·한계 확인. unit_limit은 단위 / 한계를 함께 표시한 열')+'<p>이번에는 구성요소의 USES_PART 관계로')
            sections[2]=(sections[2][0],text+figure('03-parts','구성요소별 교체 부품과 품번 세 연결 확인'))
            sections[3]=(sections[3][0],sections[3][1]+figure('04-counts','태그 목록과 집계 비교: 쿨러 2개·팬 1개·주 펌프 2개'))
            def captured(name,caption):
                return f'<figure><a href="images/{name}.jpg" target="_blank"><img src="images/{name}.jpg" alt="{caption}"></a><figcaption>{caption} · 누르면 크게 보기</figcaption></figure>'
            sections[0]=(sections[0][0],sections[0][1]+captured('00-connect','실습 링크를 열면 나타나는 연결 창. 주소는 자신의 터미널 출력과 대조하세요.'))
            if course=='통합반':
                starter=folder/'조회_작성.cypher'
                original=starter.read_text(encoding='utf-8')
                if not original.startswith('// 0.'):
                    write(starter,'// 0. 쿨러 노드 하나의 식별자와 이름 조회\n\n'+original)
                sections.insert(1,('노드 하나부터 조회하기', '<p>위쪽 입력칸에 아래 문장을 작성하세요. 줄바꿈은 Shift+Enter, 실행은 오른쪽 Run입니다.</p><pre>MATCH (c:Component {id:\'comp:cooler\'})\nRETURN c.id AS id, c.name AS name;</pre><p class="check">comp:cooler와 오일 쿨러가 한 행으로 나옵니다. MATCH는 대상을 찾고 RETURN은 볼 항목을 정합니다.</p>'+captured('00-node','노드 하나의 식별자와 이름을 조회한 결과')))
                steps=steps.replace('4. 조회_작성.cypher의 여섯 질문에 맞춰 질의를 작성하고 한 문장씩 실행합니다.','4. 가이드에서 쿨러 노드 하나를 먼저 조회한 뒤 조회_작성.cypher의 질문에 맞춰 관계·조건·집계를 확장합니다.')
                full_cues=ROOT/'제작용/촬영/neo4j/통합반_첫Cypher_전체큐.json'
                if full_cues.exists():
                    recorded=json.loads(full_cues.read_text(encoding='utf-8'))
                    queries=[c['query'] for c in recorded['cues'] if c['op']=='query']
                    labels=['쿨러 노드','팬으로 대상 바꾸기','쿨러의 센서','같은 연결을 그래프로 보기','설비에서 물리량까지','한계가 있는 항목','온도 센서만 고르기','교체 부품','센서 목록과 집계']
                    blocks=[f'<h3>{label}</h3><pre>{html.escape(query)}</pre>' for label,query in zip(labels,queries)]
                    sections[1]=(sections[1][0],sections[1][1]+blocks[1]+'<p class="check">comp:fan과 팬이 한 행으로 나옵니다. 조회 대상만 바뀌었습니다.</p>')
                    sections[2]=(sections[2][0],'<p>쿨러에서 센서로 관계를 하나 붙입니다. 문장을 넣고 Run을 누르세요.</p>'+blocks[2]+'<p class="check">같은 쿨러에 연결된 CE·TS1 두 행이 나옵니다.</p>'+captured('full-sensors','쿨러에 연결된 센서 두 행')+blocks[3]+'<p class="check">그래프의 노드는 3개, 관계는 2개입니다. 표의 두 행과 같은 연결입니다.</p>'+captured('full-graph','같은 연결을 그래프로 확인'))
                    sections[3]=(sections[3][0],blocks[4]+'<p class="check">태그·물리량·단위·한계가 5행으로 나옵니다. CE·FS1의 null은 0이 아니라 값 없음입니다.</p>'+captured('full-quantity','물리량 5행과 단위·한계')+blocks[5]+'<p class="check">한계가 없는 CE·FS1이 빠지고 3행이 남습니다.</p>'+blocks[6]+'<p class="check">TS1 한 행만 남습니다. 여기의 한계는 등록된 기준이며 현재 측정값이 아닙니다.</p>'+captured('full-filter','온도 센서 TS1 한 행')+blocks[7]+'<p class="check">쿨러 코어·펌프 축 씰 키트·팬 베어링의 세 연결과 품번을 원자료와 대조하세요.</p>'+captured('full-parts','구성요소와 교체 부품 세 연결'))
                    sections[4]=(sections[4][0],blocks[8]+'<p class="check">쿨러 CE·TS1은 2개, 주 펌프 FS1·PS1은 2개, 팬 VS1은 1개입니다. 목록을 직접 세어 channels와 비교하세요. 센서까지 연결되는 MATCH에서는 센서가 없는 구성요소가 결과에 나오지 않습니다.</p>'+captured('full-counts','센서 목록과 집계 대조'))
                    sections[-1]=('저장하고 다시 열기','<p>Browser 왼쪽 Queries를 누르고 위쪽 +로 새 쿼리 탭을 여세요. 실행한 문장과 실제 확인 결과를 넣습니다. 첫 줄에 <code>// 첫 사이퍼 실습</code>을 적으면 목록에서 제목으로 찾을 수 있습니다.</p><p>탭을 닫고 왼쪽 목록의 제목을 눌러 다시 여세요.</p><p class="check">작성한 문장과 확인 기록이 그대로 보입니다.</p><p>Queries 제목 오른쪽 Download all을 눌러 CSV 파일을 받으세요. 브라우저 목록만으로는 학교 PC 초기화 후 보존되지 않습니다. 받은 파일을 USB 또는 개인 클라우드에 보관합니다.</p><p>조회_작성.cypher와 조회_기록.md에 기록하는 방식도 사용할 수 있습니다. 다음 포털 탐색은 별도 시작본으로 엽니다.</p>')
                graph_cues=ROOT/'제작용/촬영/neo4j/통합반_그래프탐색_큐.json'
                if graph_cues.exists():
                    from graph_guide import sections as graph_sections
                    sections=graph_sections(json.loads(graph_cues.read_text(encoding='utf-8')),sections[0])
                    title='Cypher로 설비 전체 연결 탐색하기'
                    steps=steps.replace('가이드에서 쿨러 노드 하나를 먼저 조회한 뒤 조회_작성.cypher의 질문에 맞춰 관계·조건·집계를 확장합니다.','가이드에서 전체 설비 지도를 펼치고 노드·관계의 정보를 확인한 뒤, 질문에 맞춰 경로·조건·집계를 조회합니다.')
                    steps=steps.replace('5. 조회_기록.md에 실제 행·집계·원자료 근거를 적고 결과/에 질의와 기록을 저장합니다.','5. Queries에 문장과 실제 확인 기록을 저장하고 다시 엽니다. CSV와 전체 그래프 PNG를 내려받습니다. 조회_기록.md에도 실제 행·집계·원자료 근거를 남깁니다.')
            else:
                sections[1]=('점검할 센서 확인하기',sections[1][1])
                sections[2]=('기준값과 교체 부품 확인하기',sections[2][1])
                sections[3]=('센서 목록으로 집계 검증하기',sections[3][1])
        if number==1:
            from graph_guide import sections as graph_sections, common_basic_sections
            shared=json.loads((ROOT/'제작용/촬영/neo4j/공통_Cypher_큐.json').read_text(encoding='utf-8'))
            sections=graph_sections(shared,sections[0])
            sections=sections[:1]+common_basic_sections(shared)+sections[1:]
            title='Cypher로 그래프를 만들고 수정·삭제한 뒤 설비 탐색하기'
            steps='\n'.join('4. 가이드의 기본 예제를 생성·조회·수정·삭제하고 결과를 확인한 뒤, 준비된 설비의 경로·조건·집계를 조회합니다.' if line.startswith('4. ') else line for line in steps.splitlines())
            basic_queries=[c['query'] for c in shared['cues'] if c['id'].startswith('common') and 'query' in c]
            write(folder/'기본문법_연습.cypher','// 위에서부터 한 문장씩 실행합니다. 전체 파일을 한 번에 실행하지 않습니다.\n// CREATE 문장은 한 번 실행합니다. 준비된 설비와 별도의 연습장치·연습센서만 수정·삭제합니다.\n\n'+'\n\n'.join(basic_queries)+'\n')
        for file in ['AGENTS.md','CLAUDE.md','.github/copilot-instructions.md']:write(folder/file,rules)
        write(folder/'START.md',f'# {title}\n\n{steps}\n\n작성한 결과를 다시 열어 확인하고 재부팅 전에 보관할 파일을 USB 또는 개인 클라우드로 복사합니다.\n')
        for file in ['guide.html','안내.html']:write(folder/file,page(title,'연결된 대상을 확인하고, 결과의 근거를 원자료와 대조합니다.',sections))
        archive=pack(folder)
        catalog['labs'].append({'id':f'{slug}-02-{kind}','course':course,'session':'온라인 02회차','title':title,'version':'2026-10-27-common-graph-v8' if number==1 else ('2026-10-28-map-v2-screens' if course=='실전반' else '2026-10-26-common-v1'),'folder':'02회차/랩/'+name,'path':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
catalog['labs'].sort(key=lambda x:(x['course'],x['session'],x['folder']))
dump(HERE/'package-index.json',catalog)
print('두 과정 조회 가이드·독립 시작본과 포털 탐색 연결')
