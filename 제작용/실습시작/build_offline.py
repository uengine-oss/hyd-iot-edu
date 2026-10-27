"""오프라인1 공통 가이드와 제공 적재 시작본. 온라인 구현 과제와 분리."""
from build_labs import ROOT,OUT,COURSES,page,write,dump
from pathlib import Path
import shutil,json,zipfile,hashlib
HERE=Path(__file__).resolve().parent
NAME='01일차_오프라인_모델과질문'
query='''// 설비별 센서
MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:MONITORED_BY]->(s:Sensor)
RETURN a.id AS asset, collect(s.tag) AS sensors, count(s) AS count;

// 부품별 사용 설비
MATCH (a:Asset)-[:HAS_COMPONENT]->(:Component)-[:USES_PART]->(p:Part)
RETURN p.id AS part, collect(DISTINCT a.id) AS assets;
'''
catalog=json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
catalog['labs']=[x for x in catalog['labs'] if '-01-offline' not in x['id']]
for course,slug in COURSES:
    folder=OUT/course/'실습/01회차/랩'/NAME
    for filename in ['lab_db.py','offline_load.py']:write(folder/filename,(HERE/filename).read_text(encoding='utf-8'))
    (folder/'입력').mkdir(parents=True,exist_ok=True)
    for filename in ['schema.json','graph.json']:
        shutil.copy2(HERE/'reference/통합반'/filename,folder/'입력'/filename)
    write(folder/'질문.cypher',query)
    write(folder/'결과/README.md','적재 확인과 질문별 결과, 바꾼 모델을 저장합니다.\n')
    write(folder/'START.md','# 랩 그래프 적재와 질문\n\n앞 단계 완성 모델로 시작합니다. 개인 모델은 선택 입력입니다.\n\n1. Docker가 실행 중인지 확인합니다.\n2. VS Code 터미널에서 `python offline_load.py`를 실행합니다.\n3. 「적재 완료」와 노드 44개·관계 57개를 확인합니다.\n4. `python lab_db.py`로 Browser를 엽니다. Protocol은 bolt://, Connection URL은 출력 주소의 127.0.0.1:포트 부분, Database user는 neo4j, Password는 빈칸으로 연결합니다.\n5. 질문.cypher의 문장을 하나씩 실행하고 원자료와 대조합니다.\n6. 같은 적재 명령을 다시 실행해 개수가 유지되는지 확인합니다.\n\n개인 모델을 적용할 때는 제공 입력을 먼저 보관합니다. 종류나 관계 이름을 바꿨으면 질의도 함께 수정합니다. 삭제·종류 변경은 추가 적재만으로 기존 대상을 지우지 않으므로 시작 도구의 새로 시작으로 별도 DB에서 확인합니다.\n\n결과/를 USB 또는 개인 클라우드에 복사하고 복사본을 열어 확인합니다.\n')
    content=[('모델 적재하기','<p>Docker를 실행하고 VS Code 터미널에 입력하세요.</p><pre>python offline_load.py</pre><p class="check">제공 모델은 노드 44개·관계 57개입니다. 「적재 완료」와 결과/적재_확인.json을 확인하세요.</p>'),('질문 실행하기','<pre>python lab_db.py</pre><p>열린 Browser의 Protocol에서 bolt://를 선택하고 Connection URL에는 출력 주소의 127.0.0.1:포트 부분만 넣으세요. Database user는 neo4j, Password는 비워 두고 Connect를 누릅니다.</p><p>질문.cypher에서 문장 하나를 복사해 Browser 입력칸에 넣고 Run을 누르세요.</p><p class="check">설비 3대에 센서가 각각 5개씩 조회됩니다. 부품 3종은 각각 HYD-01·02·03과 연결됩니다.</p>'),('다시 확인하고 저장하기','<p>같은 적재 명령을 다시 실행해 44개·57개가 유지되는지 확인하세요. 질문 결과와 원자료에서 확인한 행을 결과/에 기록하세요.</p><p>개인 모델을 적용할 때는 제공 입력을 보관하고, 바꾼 종류·관계 이름에 맞춰 질문도 수정합니다. 대상 삭제·종류 변경을 확인할 때는 시작 도구에서 새로 시작해 별도 DB를 사용하세요.</p><p>보관할 파일은 재부팅 전에 USB 또는 개인 클라우드로 복사합니다.</p>')]
    write(folder/'guide.html',page('랩 그래프 적재와 질문','앞 단계의 제공 모델로 시작합니다. 포털과 분리된 실습 폴더 전용 DB를 사용합니다.',content))
    archive=folder.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob('*')):
            if f.is_file():z.write(f,Path('01회차/랩')/NAME/f.relative_to(folder))
    catalog['labs'].append({'id':slug+'-01-offline','course':course,'session':'오프라인 01회차','title':'랩 그래프 적재와 질문','version':'2026-10-26-offline-v1-connection2','folder':'01회차/랩/'+NAME,'path':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
    sections=[('관계 그림 확장하기','<p>쿨러와 센서부터 시작해 고장·원인·조치를 관련 단위로 추가하세요. 각 단계의 사진에서 새로 연결할 대상을 확인합니다.</p><p><a class="button" href="랩/01일차_실습4_관계그림/가이드.html">ARROWS 단계별 가이드</a></p><p class="check">화살표를 문장으로 읽고, 저장한 JSON을 다시 열어 연결을 확인하세요.</p>'),('최소 모델 만들기','<p>시작 도구에서 통합반 → 온라인 02회차 → 「현장 자료를 질문에 답하는 모델로 만들기」를 선택하세요. 이 단계는 두 과정 공통입니다.</p><p><a href="../../../통합반/실습/02회차/랩/02일차_실습3_온톨로지설계/guide.html">모델 작업 가이드</a></p><p>현장 목록으로 설비·센서·부품의 종류, 식별자, 속성, 연결을 정하고 schema.json·graph.json을 만드세요.</p><p class="check">설비가 다른 TS1은 구별되고, 같은 품번의 부품은 공유됩니다. 질문의 답을 원자료와 대조하세요.</p>'),('랩 그래프에 적재하고 질문하기',f'<p>시작 도구에서 오프라인 01회차 → 「랩 그래프 적재와 질문」을 선택하세요. 앞 단계 완성 모델이 들어 있습니다.</p><p><a class="button" href="랩/{NAME}/guide.html">제공 적재 절차와 확인 결과</a> · <a href="랩/{NAME}.zip">수동 ZIP</a></p>'),('포털의 기준 지도와 비교하기','<p>학교 PC의 HYD 포털에서 지식 지도를 열고 설비를 선택하세요. 구성요소와 센서의 종류·속성·연결 방향을 개인 모델과 비교합니다.</p><p class="check">같은 의미를 표현하는 부분과 다르게 표현한 부분을 짚어 보세요. 개인 모델은 포털에 자동 반영되지 않습니다.</p>'),('모델과 질문 보완하기','<p>아직 답하지 못한 질문 하나를 고르고 필요한 관계·속성을 원자료에서 찾으세요. AI에 변경할 범위와 확인 사례를 전달해 모델과 질의를 수정합니다.</p><p class="check">수정한 질문과 기존 질문을 다시 실행하고, 결과가 달라진 이유를 자료로 설명하세요.</p>'),('결과 보관하기','<p>관계도 JSON, schema.json, graph.json, 질의와 확인 기록을 저장하세요. USB 또는 개인 클라우드에 복사한 뒤 복사본을 다시 열어 확인합니다.</p><p>다음 실습은 시작 도구에서 새로 선택합니다. 이전 개인 결과 없이도 제공 시작본으로 이어갈 수 있습니다.</p>')]
    write(OUT/course/'실습/01회차/오프라인_가이드.html',page('관계 그림에서 질문 가능한 모델까지','관련 대상을 묶어 그림을 확장하고, 모델과 실제 조회 결과를 원자료에 대조합니다.<br><a href="../../../../제작용/실습시작/index.html">실습 시작 도구 받기</a>',sections))
dump(HERE/'package-index.json',catalog)
print('오프라인1 공통 가이드와 제공 적재 ZIP 2개 생성')
