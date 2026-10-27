"""온라인2 과정별 조회 안내와 포털 탐색의 시작본을 연결."""
from build_labs import ROOT,OUT,COURSES,page,write,dump,pack,RULES
from pathlib import Path
import json,hashlib,shutil,html,argparse
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--course',choices=[name for name,_ in COURSES])
args=parser.parse_args()
active_courses=[item for item in COURSES if args.course is None or item[0]==args.course]
catalog=json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
ids={f'{slug}-02-{kind}' for _,slug in active_courses for kind in ['relations','map']}
catalog['labs']=[x for x in catalog['labs'] if x['id'] not in ids]
for course,slug in active_courses:
    for number,name,title,kind in [(1,'02일차_실습1_관계조회','관계를 따라 센서와 부품 조회하기','relations'),(2,'02일차_실습2_지식지도탐색','포털에서 기준 지식의 연결 탐색하기','map')]:
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
        else:
            steps='''1. 학교 PC에 준비된 HYD 포털에서 지식 지도를 엽니다. 기본 로컬 주소는 http://127.0.0.1:8088 입니다.
2. 설비 HYD-01과 오일 쿨러를 찾아 ID·클래스·속성을 탐색_기록.md에 기록합니다.
3. 센서에서 상태 변수로, 고장 유형에서 구성요소와 원인 후보로 이어진 관계의 시작·끝을 확인합니다.
4. 현재 화면에서 확인한 것만 기록하고 결과/에 저장합니다. 편집·설비 조작·명령 승인은 하지 않습니다.'''
            sections=[('지식 지도 열기','<p><a href="http://127.0.0.1:8088" target="_blank" rel="noopener">학교 PC의 HYD 포털 열기</a></p><p>포털의 지식 지도를 열고 HYD-01을 선택하세요. 학교에서 별도 주소를 안내받았다면 그 주소를 사용합니다.</p><p>탐색_기록.md에 포털 주소와 확인 시각을 적습니다. 앞 실습의 예제 DB와는 별개입니다.</p>'),('대상의 종류와 속성 보기','<p>오일 쿨러를 찾아 ID와 클래스를 확인하세요. 연결된 센서의 태그를 보고, 상태 변수까지 따라가 단위·한계를 기록합니다.</p><p class="check">이름만 적지 않고 대상 ID와 값을 함께 남깁니다. 화면에 표시되지 않은 항목은 미확인으로 둡니다.</p>'),('들어오는 관계 따라가기','<p>쿨러에 연결된 고장 유형과 원인 후보를 찾아 관계 이름·시작 ID·끝 ID를 기록하세요. 탐색한 방향과 저장된 화살표 방향을 구별합니다.</p><p class="check">원인 후보의 연결을 찾은 것과 현재 고장의 원인을 확정한 것은 다릅니다. 이번에는 표시된 지식의 연결을 확인합니다.</p>'),('기록 확인하고 저장하기','<p>설비 → 구성요소 → 센서 → 상태 변수의 경로와 고장·원인 경로를 기록에서 다시 읽어 보세요. 빠진 시작·끝 ID는 화면으로 돌아가 확인합니다.</p><p>결과/에 탐색 기록을 저장하고 다시 엽니다. 다음 모델 설계는 별도 시작본을 사용합니다.</p>')]
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
        for file in ['AGENTS.md','CLAUDE.md','.github/copilot-instructions.md']:write(folder/file,rules)
        write(folder/'START.md',f'# {title}\n\n{steps}\n\n작성한 결과를 다시 열어 확인하고 재부팅 전에 보관할 파일을 USB 또는 개인 클라우드로 복사합니다.\n')
        for file in ['guide.html','안내.html']:write(folder/file,page(title,'연결된 대상을 확인하고, 결과의 근거를 원자료와 대조합니다.',sections))
        archive=pack(folder)
        catalog['labs'].append({'id':f'{slug}-02-{kind}','course':course,'session':'온라인 02회차','title':title,'version':('2026-10-27-continuous-v6' if course=='통합반' else '2026-10-27-cypher-v2') if number==1 else '2026-10-26-common-v1','folder':'02회차/랩/'+name,'path':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
catalog['labs'].sort(key=lambda x:(x['course'],x['session'],x['folder']))
dump(HERE/'package-index.json',catalog)
print('두 과정 조회 가이드·독립 시작본과 포털 탐색 연결')
