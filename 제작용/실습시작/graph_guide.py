"""실제 그래프 탐색 큐와 동일한 통합반 학생 가이드 단계."""
import html

def basic_sections(spec):
    by_id={c['id']:c for c in spec['cues']}
    def q(n):return '<pre>'+html.escape(by_id[f'basic{n:03}']['query'])+'</pre>'
    def check(text):return '<p class="check">'+text+'</p>'
    def image(name,caption):return f'<figure><a href="images/basic-{name}.jpg" target="_blank"><img src="images/basic-{name}.jpg" alt="{caption}"></a><figcaption>{caption} · 누르면 크게 보기</figcaption></figure>'
    return [
      ('작은 예제 만들고 조회하기','<p>위쪽 입력칸에서 한 문장씩 실행합니다. CREATE는 새 노드를 만듭니다. 이 생성 문장은 한 번 실행하세요.</p>'+q(2)+check('연습 펌프의 score는40, 연습 팬은70입니다.')+'<p>MATCH로 연습장치를 찾고 RETURN에 이름과 점수를 적습니다. ORDER BY score는 점수가 작은 순서로 정렬합니다.</p>'+q(5)+check('연습 펌프40, 연습 팬70의 두 행이 나옵니다.')+image('nodes','만든 노드 두 개를 MATCH로 다시 조회')),
      ('조건을 바꾸고 결과 비교하기','<p>WHERE로 score가50 이상인 행을 고릅니다.</p>'+q(8)+check('연습 팬70 한 행만 나옵니다.')+'<p>50을30으로 바꾸고 다시 실행합니다.</p>'+q(11)+check('연습 펌프40과 연습 팬70이 다시 나옵니다. 조건에서 제외된 노드도 저장돼 있습니다.')+image('filter','조건에 따라 달라지는 조회 결과')),
      ('같은 대상 찾아 수정하기','<p>MERGE는 패턴이 있으면 찾아 쓰고 없으면 만듭니다. id로 찾을 대상을 정하고 SET에 저장할 속성을 적습니다.</p>'+q(14)+'<p>같은 MERGE와 SET을 다시 실행하고 등록된 센서 수를 확인합니다.</p>'+q(17)+check('sensor_count는1입니다. WITH s는 앞 단계의 변수 s를 다음 단계로 넘깁니다. 여기서는 이어지는 MATCH로 전체 연습센서를 찾아 셉니다.')+'<p>이번에는 SET의 이름만 바꿉니다.</p>'+q(20)+check('id와 unit은 그대로이고 name은 연습 유온 센서로 바뀝니다. MERGE와 동시 등록의 중복을 막는 유일 제약은 구분합니다.')+image('update','식별자는 유지하고 이름만 수정')),
      ('관계 만들고 그림으로 확인하기','<p>MATCH로 두 노드를 찾고 MERGE로 관측 관계를 만듭니다.</p>'+q(23)+check('연습 펌프 → 관측 → 연습 유온 센서의 한 행이 나옵니다.')+'<p>같은 연결에서 속성값 대신 노드·관계를 반환합니다.</p>'+q(26)+check('Graph에 노드2개·관계1개가 나옵니다. 변수 p·s는 노드, r은 관계를 가리킵니다.')+image('relation','표에서 확인한 같은 연결을 Graph로 보기')),
      ('연습 정리하고 설비에 적용하기','<p>이번에 만든 연습장치와 연습센서만 찾아 삭제합니다. DETACH DELETE는 해당 노드와 연결된 관계를 함께 지웁니다.</p>'+q(29)+check('removed는3입니다. 준비된 설비의 노드20개·관계19개는 남습니다.')+'<p>입력칸에서 <code>:clear</code>를 실행해 카드만 비웁니다. 이제 같은 문법으로 아래 설비 연결을 탐색합니다. 실행한 문장은 <a href="기본문법_연습.cypher">기본문법_연습.cypher</a>에서도 확인할 수 있습니다.</p>')]

def sections(spec, prepare):
    by_title={c['title']:c['query'] for c in spec['cues'] if c['op']=='query'}
    def q(title):return '<pre>'+html.escape(by_title[title])+'</pre>'
    def img(name,caption):return f'<figure><a href="images/forest-{name}.jpg" target="_blank"><img src="images/forest-{name}.jpg" alt="{caption}"></a><figcaption>{caption} · 누르면 크게 보기</figcaption></figure>'
    def check(text):return '<p class="check">'+text+'</p>'
    return [prepare,
      ('전체 설비 지도 읽기','<p>Browser 위쪽 입력칸에 문장을 넣고 Run을 누르세요. HYD-01에서 한 단계부터 세 단계까지 이어지는 경로를 봅니다.</p>'+q('전체 설비 지도')+'<p>왼쪽 패널과 그래프 상세 창을 접습니다. 그래프 아래 Select layout → Hierarchical layout을 선택하고 Zoom to fit을 누르세요.</p>'+check('설비 아래 구성요소가 있고, 구성요소에서 센서·부품으로 갈라집니다. 센서 아래에는 물리량이 있습니다. 전체 노드20개·관계19개입니다.')+img('whole','설비 → 구성요소 → 센서·부품 → 물리량')+'<p>상세 창을 열고 빈 배경을 클릭한 뒤 Zoom to fit을 누르세요. 빈 배경을 끌어 위치를 옮기고 노드 위에서 휠을 올려 확대합니다. HYD-01과 오일 쿨러를 차례로 클릭해 오른쪽 Node details를 읽으세요.</p>'+check('HYD-01은 Asset, 오일 쿨러는 Component입니다. 쿨러의 id는 comp:cooler입니다.')+img('cooler','오일 쿨러 선택과 식별자·이름 확인')),
      ('쿨러 하나를 쿼리로 찾기','<p>입력칸에서 <code>:clear</code>를 실행해 앞 카드를 정리한 뒤 다음 문장을 실행하세요. :clear는 DB 데이터를 삭제하지 않습니다.</p>'+q('쿨러 한 개')+'<p><code>c</code>는 찾은 노드를 가리키는 변수, <code>Component</code>는 노드의 레이블입니다. <code>id</code>는 속성 이름, <code>comp:cooler</code>는 찾을 속성값입니다. 그림에 표시된 오일 쿨러는 <code>name</code> 속성값입니다.</p><p>쿨러 노드를 클릭해 id와 name을 확인하세요.</p>'+check('노드 하나가 나오며 id는 comp:cooler, 이름은 오일 쿨러입니다. 관계가 사라진 것이 아니라 이번 결과에 노드만 반환한 것입니다.')),
      ('센서와 관계를 클릭해서 읽기',q('쿨러와 센서')+'<p><code>c</code>와 <code>s</code>는 노드 변수, <code>r</code>은 관계 변수입니다. <code>Component</code>·<code>Sensor</code>는 노드 레이블, <code>MONITORED_BY</code>는 관계 유형입니다.</p>'+check('쿨러1개·센서2개, 노드3개·관계2개입니다.')+'<p>유온 센서를 클릭해 tag·unit·virtual을 읽고 냉각 효율 노드와 비교하세요.</p>'+check('유온 센서는 TS1·℃·virtual=false입니다. 냉각 효율은 CE·%·virtual=true입니다.')+img('sensor','유온 센서의 태그와 단위')+'<p>MONITORED_BY 화살표를 클릭하세요. 오른쪽이 Relationship details로 바뀝니다. 쿨러에서 센서로 향하는 관계이며 배관의 흐름을 뜻하지 않습니다.</p>'+img('relationship','노드 정보와 구별되는 관계 정보')),
      ('센서에서 물리량까지 따라가기',q('설비에서 물리량까지')+check('센서가 연결된 구성요소3개에서 관측 경로5개가 이어집니다. 결과는 노드14개·관계13개입니다.')+'<p>유온 센서 아래의 <strong>유온</strong>을 클릭하세요. 센서와 물리량 노드를 구분해 읽습니다.</p>'+check('유온은 StateVariable, id는 sv:ts1입니다. 단위 ℃, normal=48, limit=65는 등록된 기준이며 현재 측정값이 아닙니다.')+img('quantity','유온 노드를 클릭해 등록된 기준 확인')),
      ('질문에 맞춰 조건과 반환값 바꾸기',q('TS1 경로만 선택')+check('HYD-01 → 오일 쿨러 → 유온 센서 → 유온의 경로만 남습니다. 노드4개·관계3개입니다. 다른 센서를 삭제한 것이 아닙니다.')+img('filtered','TS1 조건으로 좁힌 경로')+'<p>같은 경로에서 필요한 속성만 받아 표로 비교합니다.</p>'+q('TS1 속성 표')+check('TS1·유온·℃·48·65가 한 행에 나옵니다. 방금 클릭한 노드의 값과 대조하세요.')+'<p>이번에는 전체 관측 경로에서 한계가 등록된 항목만 고릅니다.</p>'+q('한계가 있는 항목')+check('PS1·TS1·VS1 세 행이 나옵니다. CE·FS1은 한계가 없어 제외됐습니다. null은 0이 아닙니다.')),
      ('교체 부품 가지 탐색하기',q('장치와 교체 부품')+check('설비 → 장치3개 → 부품3개, 노드7개·관계6개입니다.')+'<p>쿨러 코어 노드를 클릭해 레이블·이름·품번을 확인하세요.</p>'+check('쿨러 코어는 Part이며 partNo=P-CLR-CORE입니다. 오일 쿨러 장치와 별개입니다. 등록된 사용 관계만으로 현재 재고나 교체 필요를 판단하지 않습니다.')+img('part','쿨러 코어의 품번 확인')),
      ('그림에서 센 수와 집계 비교하기',q('센서 연결과 직접 세기')+'<p>쿨러·주 펌프·팬 아래 센서를 직접 센 뒤 같은 연결을 집계하세요.</p>'+q('센서 목록과 집계')+check('쿨러 CE·TS1은2개, 주 펌프 FS1·PS1은2개, 팬 VS1은1개입니다. tags 목록의 개수와 channels를 비교합니다.')+img('count','목록과 개수를 함께 확인')),
      ('전체 지도에서 정리하고 저장하기',q('전체 설비 지도')+'<p>예비 펌프를 클릭해 노드가 존재함을 확인하세요. 센서 집계에서 빠진 까닭을 전체 지도에서 찾아봅니다.</p>'+check('comp:pump-b 노드는 존재하지만 제공 예제에는 센서로 이어지는 경로가 없습니다. 표에서 빠졌다는 사실과 장치가 없다는 판단은 다릅니다.')+'<p>상세 창을 접고 빈 배경을 눌러 선택을 푼 뒤 Zoom to fit을 누릅니다. 그래프 오른쪽 위 Download as PNG로 그림을 받으세요.</p><p>왼쪽 패널의 Queries → 위쪽 +로 새 쿼리 탭을 엽니다. 첫 줄은 <code>// 설비 연결 탐색</code>으로 적고 실행한 문장과 실제 확인 기록을 넣으세요. 탭을 닫고 왼쪽 목록에서 다시 엽니다.</p>'+check('작성한 문장과 확인 기록이 그대로 보입니다.')+'<p>Queries의 Download all로 CSV를 받습니다. PNG와 CSV를 재부팅 전에 USB 또는 개인 클라우드에 보관하세요. 다음 포털 탐색은 별도 시작본으로 시작합니다.</p>')]
