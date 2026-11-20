"""Neo4j 관계 조회 안내 문서(02회차 실습1)의 단계 글. 쿼리는 원고의 글자를 그대로 복사 블록(lab_frame.block)으로 싣는다.
- 두 과정 공통(2회차 실습 04 영상 「관계조회-04」, 대본 `산출물/통합반/실습/02회차/대본/04_실습_관계조회.md` = 실전반 05): `integrated_relations` — 원고는
  `촬영/neo4j/통합반_관계조회_칸.json`(칸 id 「절-차례」), 영상이 입력칸에 넣는 쿼리와 같은 글이다. 2~11절에는 원고의 칸 말고 다른 Cypher 블록을 넣지 않는다.
  사진은 그 영상의 녹화 프레임에서 `촬영/neo4j/사진_만들기.py`가 뽑는다(가이드 P-8). `Shots`가 랩 폴더에 있는 사진만 싣고 없는 자리는 미촬영으로 알린다.
- 옛 판(2026-11-06 녹화본의 차례, 실전반이 새 영상으로 바뀌기 전): `common_basic_sections` · `sections` — 원고는 촬영 큐 `촬영/neo4j/공통_Cypher_큐.json`."""
import html

from lab_frame import block


def b(text):
    """화면의 메뉴 · 단추 이름은 굵게(P-6)."""
    return '<b>'+html.escape(text)+'</b>'


def check(text):
    return '<p class="check">'+text+'</p>'


def figure(name, caption, show=True):
    """사진 하나. show=False면 설명 글을 사진 대체 글로만 두고 아래에는 「누르면 크게 보기」만 쓴다 — 바로 위 글 · 확인 줄이 이미 말한 것을 되풀이하지 않게(가이드 P-5)."""
    return (f'<figure><a href="images/{name}.jpg" target="_blank"><img src="images/{name}.jpg" alt="{caption}"></a>'
            f'<figcaption>{caption + " · " if show else ""}누르면 크게 보기</figcaption></figure>')


class Shots:
    """사진 자리. 사진 폴더(folder/images/)에 그 사진이 있으면 그림으로 싣고, 없으면 싣지 않고 missing에 남긴다.
    미촬영 자리가 남은 판은 게시하지 않는다(가이드 P-8) — 생성기가 끝에 그 목록을 찍는다."""
    def __init__(self, folder):
        self.folder, self.used, self.missing = folder, [], []

    def __call__(self, name, caption, show=True):
        if (self.folder/'images'/f'{name}.jpg').is_file():
            self.used.append(name)
            return figure(name, caption, show)
        self.missing.append((name, caption))
        return ''

    def report(self):
        """가이드가 쓰지 않는 사진이 폴더에 있으면 멈추고, 미촬영 자리를 찍는다."""
        have = {p.stem for p in (self.folder/'images').glob('*.jpg')} if (self.folder/'images').is_dir() else set()
        extra = sorted(have - set(self.used))
        if extra:
            raise SystemExit(f'{self.folder}/images: 가이드가 쓰지 않는 사진 {extra} — 지우거나 사진 자리 이름과 맞춘다')
        print(f'{self.folder.name}: 사진 {len(self.used)}장 실음, 미촬영 {len(self.missing)}장(게시 전에 새 영상에서 뽑는다 — 가이드 P-8)')
        for name, caption in self.missing:
            print(f'  미촬영 images/{name}.jpg — {caption}')


CLEAR = '입력칸에 <code>:clear</code>를 넣고 Enter를 눌러 앞 결과를 비운 뒤 다음 문장을 실행하세요.'
FIT = b('Zoom to fit')


def common_basic_sections(spec):
    by_id = {c['id']: c for c in spec['cues']}
    def q(n): return block('cypher', by_id[n if isinstance(n, str) else f'common{n:03}']['query'])
    def img(name, caption): return figure('common-'+name, caption)
    return [
      ('노드 만들고 RETURN으로 그래프 보기', '<p>연습용 노드 두 개를 만들고, 만든 노드를 조회해 그래프로 봅니다. Browser 위쪽 입력칸에 다음 문장을 붙여 넣고 '+b('Run')+'을 누르세요. CREATE는 새 노드를 만듭니다. 이 생성 문장은 한 번만 실행합니다. 다시 실행하면 같은 노드가 하나씩 더 생기기 때문입니다.</p>'+q(2)+check('Created 2 nodes가 나옵니다. RETURN이 없어 그래프는 표시되지 않지만 노드는 생성됐습니다.')+img('no-return', 'RETURN 없이 실행한 생성 결과 안내')+'<p>CREATE를 다시 실행하지 않고 MATCH로 만든 노드를 찾습니다. RETURN n으로 노드 자체를 받습니다.</p>'+q('common003b')+check('Graph에 연습 펌프와 연습 팬 두 노드가 나타납니다. 관계는 아직 없습니다.')+img('created', '만든 두 노드를 MATCH와 RETURN으로 확인')+'<p>'+b('Stream')+' 탭 왼쪽의 패널 단추로 왼쪽 도구 패널을 접고, 그래프 오른쪽 아래 '+FIT+'을 누릅니다. 연습 펌프를 클릭해 오른쪽 '+b('Node details')+'를 확인하세요.</p>'+check('레이블은 연습장치, id는 basic-A, name은 연습 펌프, score는 40입니다. n은 조회 문장의 변수입니다.')+img('properties', '패널을 접고 화면을 맞춘 뒤 펌프 노드를 클릭해 레이블과 속성 확인')),
      ('같은 노드를 그래프와 표로 조회하기', '<p>화면을 비워도 저장된 노드가 남는지 보고, 같은 노드를 표로도 받아 봅니다. <code>:clear</code>를 실행해 앞 결과를 비웁니다. 데이터는 삭제되지 않습니다. MATCH로 저장된 노드를 다시 찾으세요.</p>'+q(9)+check('두 노드가 다시 나옵니다.')+'<p>이번에는 노드 대신 이름과 점수를 반환합니다. AS는 열 이름, ORDER BY는 정렬 기준입니다.</p>'+q(12)+check('펌프 40 · 팬 70의 두 행이 나옵니다. 노드·관계·경로는 Graph로, 속성값은 Table로 확인합니다.')+img('table', '같은 노드의 이름과 점수만 표로 받기')),
      ('조건을 바꾸고 그래프 비교하기', '<p>WHERE로 조건에 맞는 노드만 고르고, 조건을 바꿔 결과를 비교합니다. WHERE에 score가 50 이상이라는 조건을 넣습니다.</p>'+q(15)+check('팬 한 노드만 나타납니다. 펌프는 삭제되지 않았습니다.')+img('filtered', '조건을 만족하는 팬만 조회')+'<p>50을 30으로 바꿔 실행합니다.</p>'+q(18)+check('펌프와 팬 두 노드가 다시 나타납니다.')+'<p>결과를 비우고 이름 조건을 OR로 묶은 뒤 AND로 점수 조건을 붙입니다.</p>'+q('common020b')+check('두 조건이 모두 맞는 팬 하나가 나옵니다.')+'<p>같은 조건에서 괄호만 뺍니다.</p>'+q('common020e')+check('펌프와 팬 두 개가 나옵니다. AND가 OR보다 먼저 묶여 펌프는 점수 조건 없이 통과합니다. 두 장치 모두에 점수 조건을 적용하려면 앞의 괄호 있는 식을 씁니다.')+img('conditions', '괄호를 뺀 식의 결과: 펌프도 함께 나옴')),
      ('센서를 만들고 관계 연결하기', '<p>센서 노드를 하나 더 만들고 펌프와 관계로 잇습니다. <code>:clear</code>로 결과를 비웁니다. MERGE는 적은 패턴이 있으면 찾아 쓰고 없으면 만듭니다. SET은 속성값을 지정합니다.</p>'+q(22)+check('연습 온도 센서 하나가 나타납니다.')+'<p>같은 MERGE·SET을 다시 실행하고 센서 수를 확인합니다. WITH는 앞 처리에서 다음 절로 이어 줍니다.</p>'+q(25)+check('sensor_count는 1입니다. 이미 있는 센서를 찾아 썼으므로 새로 만들지 않았습니다.')+'<p>펌프와 센서를 찾아 관측 관계로 연결합니다.</p>'+q(28)+check('노드 2개 · 관계 1개입니다. p·s는 노드 변수, r은 관계 변수, 관측은 관계 유형입니다. 아래에 「This query builds a cartesian product」 안내가 보여도 실패가 아닙니다.')+img('linked', '펌프와 센서를 연결한 관측 관계')+'<p>빈 곳을 눌러 선택을 풀고 '+FIT+'으로 맞춘 뒤 두 원 사이의 관측 선을 클릭합니다.</p>'+check('오른쪽 제목이 '+b('Relationship details')+'로 바뀌고 관계 유형 관측이 보입니다.')+img('relationship', '관측 선을 클릭해 관계 정보 확인')),
      ('속성을 수정하고 연결 확인하기', '<p>연결은 그대로 둔 채 센서의 이름 속성만 바꿉니다. 결과를 비우고 id가 basic-S1인 센서의 이름만 바꿉니다.</p>'+q(34)+check('노드에 표시되는 이름이 연습 유온 센서로 바뀝니다.')+'<p>빈 곳에서 선택을 풀고 '+FIT+'을 누른 뒤 센서를 클릭해 속성을 확인하세요.</p>'+check('id는 basic-S1, unit은 ℃로 유지되고 name만 바뀝니다.')+img('updated', '같은 센서의 이름 속성 수정')+'<p>경로 전체를 p에 담아 반환합니다.</p>'+q(39)+check('펌프와 이름을 바꾼 센서가 여전히 관측 관계로 연결돼 있습니다.')),
      ('관계만 삭제하고 노드는 남기기', '<p>관계를 지워도 양 끝 노드는 남는지 봅니다. 결과를 비운 뒤 관측 관계를 찾아 DELETE r로 관계만 삭제합니다.</p>'+q(43)+check('펌프·센서 두 원은 남고 연결선은 없어집니다.')+img('unlinked', '관계 삭제 후 남은 두 노드')+'<p>다음 삭제 방법을 비교하기 위해 남아 있는 두 노드 사이를 다시 연결합니다.</p>'+q(46)+check('관측 선 하나가 다시 생깁니다. 새 노드를 만든 것은 아닙니다.')),
      ('노드 삭제와 정리 확인하기', '<p>연결된 노드와 연결 없는 노드를 각각 지우고, 연습 데이터가 남지 않았는지 다시 셉니다. DETACH DELETE로 연습 센서와 그 연결을 함께 삭제합니다.</p>'+q(49)+check('removed_sensors는 1입니다.')+'<p>연습 데이터를 다시 조회합니다. 아래의 이전 결과는 실행 당시 모습이므로 맨 위에 새로 나온 결과를 봅니다.</p>'+q(52)+check('펌프와 팬 두 노드만 남습니다. 센서와 관측 관계는 없습니다.')+img('remaining', '센서 삭제 뒤 새 조회로 확인한 장치 두 개')+'<p>관계가 없는 두 장치를 일반 DELETE로 삭제합니다.</p>'+q(55)+check('removed_devices는 2입니다.')+'<p>연습 노드 수를 다시 셉니다.</p>'+q(58)+check('remaining_practice_nodes는 0입니다. 준비된 설비 20노드 · 19관계는 유지됩니다.')+img('clean', '연습 데이터가 0개인지 재조회')+'<p><code>:clear</code>로 결과를 비운 뒤 아래 설비 예제로 이어갑니다. 실행 문장은 <a href="기본문법_연습.cypher">기본문법_연습.cypher</a>에도 있습니다.</p>')]


def sections(spec, prepare):
    by_title = {c['title']: c['query'] for c in spec['cues'] if c['op'] == 'query' and 'title' in c}
    def q(title): return block('cypher', by_title[title])
    def img(name, caption): return figure('forest-'+name, caption)
    return [prepare,
      ('전체 설비 지도 읽기', '<p>준비된 설비 예제 전체를 한 번에 펼쳐 봅니다. Browser 위쪽 입력칸에 문장을 붙여 넣고 '+b('Run')+'을 누르세요. HYD-01에서 한 단계부터 세 단계까지 이어지는 경로를 봅니다.</p>'+q('전체 설비 지도')+'<p>왼쪽 패널은 접어 두고, 그래프 오른쪽 정보 칸은 펴 둡니다. 그 칸에 노드와 관계의 수가 보입니다. 그래프 오른쪽 아래 맨 끝의 배치 단추를 눌러 '+b('Hierarchical layout')+'을 고르고, 그 옆 '+FIT+'을 누르세요.</p>'+img('layout', '배치 단추를 눌러 Hierarchical layout 고르기')+check('설비 아래 구성 요소가 있고, 구성 요소에서 센서·부품으로 갈라집니다. 센서 아래에는 물리량이 있습니다. 전체 노드 20개 · 관계 19개입니다.')+img('whole', '설비 → 구성 요소 → 센서·부품 → 물리량')+'<p>설비 바로 밑 줄이 구성 요소이고, 오일 쿨러는 그 줄 맨 오른쪽 끝에 있습니다. 원이 작으면 빈 배경을 끌어 옮기고 휠로 키운 뒤 오일 쿨러를 클릭해 오른쪽 '+b('Node details')+'를 읽으세요.</p>'+check('맨 위 이름표가 Component입니다. 쿨러의 id는 comp:cooler이고, 다음 절에서 이 값으로 쿨러를 찾습니다.')+img('cooler', '오일 쿨러 선택과 식별자·이름 확인')),
      ('쿨러 하나를 쿼리로 찾기', '<p>상세 창에서 읽은 쿨러의 id로 그 노드 하나만 직접 찾습니다. '+CLEAR+'</p>'+q('쿨러 한 개')+'<p><code>c</code>는 찾은 노드를 가리키는 변수, <code>Component</code>는 노드의 레이블입니다. <code>id</code>는 속성 이름, <code>comp:cooler</code>는 찾을 속성값입니다. 그림에 표시된 오일 쿨러는 <code>name</code> 속성값입니다.</p>'+check('오일 쿨러 노드 하나만 나옵니다. 관계가 사라진 것이 아니라 이번 결과에 노드만 반환한 것입니다.')),
      ('쿨러에 달린 센서 찾기', '<p>쿨러에 어떤 센서가 붙어 있는지 관계까지 함께 받아 봅니다. '+CLEAR+'</p>'+q('쿨러와 센서')+'<p><code>c</code>와 <code>s</code>는 노드 변수, <code>r</code>은 관계 변수입니다. <code>Component</code>·<code>Sensor</code>는 노드 레이블, <code>MONITORED_BY</code>는 관계 유형입니다.</p>'+check('쿨러 1개 · 센서 2개, 노드 3개 · 관계 2개입니다.')+'<p>센서 둘은 유온 센서와 냉각 효율 센서입니다. 유온 센서를 클릭해 오른쪽 정보를 읽으세요.</p>'+check('이름표는 Sensor이고, tag 칸의 TS1이 이 센서의 태그입니다. 뒤에서 이 태그로 유온 센서만 골라냅니다.')+img('sensor', '유온 센서의 이름표와 tag 칸 TS1')),
      ('센서에서 물리량까지 따라가기', '<p>센서가 무엇을 관측하는지 보려고 설비에서 물리량까지 경로를 넓힙니다. '+CLEAR+'</p>'+q('설비에서 물리량까지')+check('센서가 달린 구성 요소 3개에서 관측 경로 5개가 이어집니다. 결과는 노드 14개 · 관계 13개입니다.')+'<p>쿨러에서 유온 센서를 거쳐 내려오는 가지 끝의 <b>유온</b>을 클릭하세요. 기준값은 센서가 아니라 센서가 재는 물리량 노드에 있습니다.</p>'+check('이름표는 StateVariable(상태 변수)입니다. limit 65는 넘으면 문제로 보는 한계, normal 48은 평소의 정상값이며 둘 다 미리 정해 둔 기준이라 지금 온도가 아닙니다.')+img('quantity', '유온 노드를 클릭해 등록된 기준 확인')),
      ('질문에 맞춰 조건과 반환값 바꾸기', '<p>앞 경로에서 질문에 필요한 줄기와 값만 골라냅니다. 이번에는 결과를 비우지 않고 다음 문장을 실행합니다. 아래에 남은 이전 그림과 견주기 위해서입니다.</p>'+q('TS1 경로만 선택')+check('HYD-01 → 오일 쿨러 → 유온 센서 → 유온의 경로만 남습니다. 노드 4개 · 관계 3개입니다. 다른 센서를 삭제한 것이 아닙니다.')+img('filtered', 'TS1 조건으로 좁힌 경로')+'<p>같은 경로에서 필요한 속성만 받아 표로 비교합니다.</p>'+q('TS1 속성 표')+check('TS1·유온·℃·48·65가 한 행에 나옵니다. 방금 클릭한 노드의 값과 대조하세요.')+'<p>이번에는 전체 관측 경로에서 한계가 등록된 항목만 고릅니다. '+CLEAR+'</p>'+q('한계가 있는 항목')+check('PS1·TS1·VS1 세 행이 나옵니다. CE·FS1은 한계가 적혀 있지 않아 빠졌습니다.')),
      ('교체 부품 가지 탐색하기', '<p>구성 요소에서 센서가 아니라 부품으로 이어지는 관계를 따라갑니다. '+CLEAR+'</p>'+q('장치와 교체 부품')+check('설비 → 구성 요소 3개 → 부품 3개, 노드 7개 · 관계 6개입니다.')+'<p>쿨러 코어 노드를 클릭해 이름표와 품번을 확인하세요.</p>'+check('쿨러 코어는 Part이며 partNo는 P-CLR-CORE입니다. 이름에 쿨러가 들어가도 오일 쿨러와는 레이블이 다른 노드입니다.')+img('part', '쿨러 코어의 품번 확인')),
      ('그림에서 센 수와 집계 비교하기', '<p>구성 요소마다 센서가 몇 개인지 먼저 그림에서 세고, 같은 수가 집계로도 나오는지 견줍니다. '+CLEAR+'</p>'+q('센서 연결과 직접 세기')+check('오일 쿨러 밑에 둘, 쿨러 팬 밑에 하나, 주 펌프 밑에 둘입니다.')+'<p>그림에서 센 수를 쿼리로 세어 견줍니다.</p>'+q('센서 목록과 집계')+check('쿨러 CE·TS1은 2개, 주 펌프 FS1·PS1은 2개, 팬 VS1은 1개입니다. tags 목록의 개수와 channels를 비교합니다.')+img('count', '목록과 개수를 함께 확인')),
      ('전체 지도에서 정리하고 저장하기', '<p>처음의 전체 지도를 다시 열어 지금까지 본 가지의 자리를 확인하고, 그림과 실행한 문장을 저장합니다. '+CLEAR+'</p>'+q('전체 지도에서 정리')+''+check('오른쪽 세 구성 요소 밑이 지금까지 따라간 센서 · 물리량과 부품 가지입니다. 왼쪽의 작동유 탱크, 구동 모터, 예비 펌프 밑으로는 아무것도 없어서 센서 집계 표에도 없었습니다.')+'<p>정보 창을 닫고 '+FIT+'으로 화면을 맞춘 뒤, 쿼리 결과 오른쪽 위 내려받기 단추('+b('Download as PNG')+')를 누르세요. 받은 파일은 브라우저 위쪽 받은 파일 목록에서 눌러 열 수 있습니다.</p>'+img('png', '쿼리 결과 오른쪽 위의 내려받기 단추(Download as PNG)')+'<p>Neo4j Browser로 돌아와 왼쪽 패널을 펼치고 위에서 두 번째 단추 '+b('Queries')+'를 누릅니다. 위 입력칸에서 돌린 문장은 여기 저절로 남지 않고 새 탭에 적은 것만 보관되므로, 위 탭 줄의 '+b('+')+'로 새 쿼리 탭을 엽니다.</p>'+img('queries', '왼쪽 Queries 단추와 탭 줄의 더하기 단추')+'<p>새 탭에 다음 글을 붙여 넣습니다. 첫 줄 <code>// 설비 연결 탐색</code>이 목록에 보이는 이름이 됩니다. 둘째·셋째 줄의 개수와 식별자는 위에서 직접 확인한 값입니다.</p>'+block('cypher_tab', spec['saved_query'])+check('처음 붙이면 Discover more actions 안내 창이 뜹니다. '+b('OK, got it')+'으로 닫으면 왼쪽 '+b('Drafts')+' 아래에 설비 연결 탐색이 보입니다.')+'<p>탭 이름 옆 '+b('×')+'로 탭을 닫고, 왼쪽 목록의 설비 연결 탐색을 눌러 다시 엽니다.</p>'+check('작성한 문장과 확인 기록이 그대로 보입니다.')+img('saved', '다시 연 쿼리 탭과 Drafts 목록의 설비 연결 탐색')+'<p>이 목록은 지금 쓰는 브라우저 안에만 저장돼 다른 컴퓨터에서는 보이지 않습니다. '+b('Queries')+' 제목 오른쪽의 내려받기 단추를 눌러 CSV 파일로도 받아 두세요. 다른 컴퓨터에서는 바로 옆 올리기 단추로 이 파일을 다시 불러옵니다.</p>'+check('보관한 쿼리가 CSV 파일 하나로 받아집니다.')+img('csv', 'Queries 제목 오른쪽의 내려받기 단추와 옆 올리기 단추'))]


def integrated_relations(spec, shot):
    """관계 조회 가이드(두 과정 공통 — 2회차 실습 04 영상 「관계조회-04」를 따른다): (여는 글, [(절 제목, HTML)]). 절 번호는 page()가 01부터 붙인다.
    01은 준비 · 연결 · 들어 있는 것 보기, 02~11은 칸 원고의 절 번호(2-1 ~ 11-3)이고 영상의 차례와 같다. 글은 「무엇을 하면 → 무엇이 나온다」와 한두 문장의 까닭만 두고,
    쿼리 풀이는 영상이 한다(가이드 P-5). 사진 자리 이름은 촬영/neo4j/사진_만들기.py의 PHOTOS와 같다."""
    by_id = {c['id']: c['query'] for c in spec['cells']}
    used = []
    def q(n):
        used.append(n)
        return block('cypher', by_id[n])
    run = '입력칸 오른쪽 끝의 '+b('Run')
    intro = ('Cypher 쿼리를 Neo4j Browser에서 직접 돌려 봅니다. 예제 DB에 노드와 관계를 만들고, 찾고, 고치고, 지운 다음, '
             '처음부터 들어 있던 설비 데이터에서 관계를 한 번, 두 번 건너 답을 꺼내고, 조건 없이 받은 행과 맞춰 그 답이 맞는지 봅니다. 온톨로지 → 에이전트 → 프로세스 가운데 온톨로지를 다루는 실습입니다.')
    prepare = ('예제 준비하고 연결하기',
        '<p>먼저 '+b('Docker Desktop')+'을 켭니다. 이 실습의 DB가 Docker에서 돌아갑니다.</p>'
        '<p>명령과 쿼리는 칸 아래 '+b('복사')+' 단추로 복사해 붙여 넣으세요. 손으로 옮기면 따옴표 하나만 빠져도 돌지 않습니다.</p>'
        '<p>클래스룸 02회차 실습 자료에서 받은 ZIP의 압축을 풀고, prepare_example.py와 lab_db.py가 들어 있는 <code>02일차_실습1_관계조회</code> 폴더(이 가이드가 든 폴더)를 파일 탐색기로 엽니다. 주소 표시줄에 powershell을 넣고 Enter를 누르면 그 폴더에서 PowerShell이 열립니다.</p>'
        +shot('00-explorer', '실습 폴더 주소 표시줄에 powershell을 넣은 모습', False)
        +'<p>두 명령을 차례로 실행하세요. 첫 명령은 DB를 띄우고 예제를 넣는 동안 아무 글 없이 잠시 기다리니, 창을 닫지 말고 끝날 때까지 둡니다.</p>'
        +block('shell', 'python prepare_example.py')+check('예제 준비 완료: 노드 20개 · 관계 19개가 나옵니다.')
        +block('shell', 'python lab_db.py')+check('랩 DB 준비 완료와 Connect URL 주소가 나오고, 브라우저에 Neo4j Browser의 연결 창이 열립니다. 여기서 랩 DB는 방금 띄운 예제 DB를 가리킵니다.')
        +shot('00-powershell', '두 명령의 출력. 이 사진과 아래 연결 창 사진은 다른 때 찍어 끝 숫자가 다릅니다 — 내 화면의 두 숫자를 견주세요')
        +'<p>연결 창의 주소와 사용자 이름은 이미 채워져 있습니다. 이 DB는 비밀번호 없이 띄웠으니(PowerShell 출력의 Password: 비워 둠) '+b('Password')+'는 비워 둔 채 '+b('Connect')+'를 누르세요.</p>'
        +shot('q01-connect', '채워진 주소 · 사용자 칸, 빈 Password 칸과 Connect 단추')
        +'<p>새 기능 안내 창('+b('Work in tabs')+')이 뜨면 '+b('Dismiss')+'로 닫습니다.</p>'
        +shot('q01-dismiss', 'Work in tabs 안내 창의 Dismiss 단추')
        +'<p>맨 위 '+b('Instance')+'(지금 연결한 DB를 가리키는 화면 글자) 주소의 끝 숫자가 PowerShell의 Connect URL 끝 숫자와 같은지 봅니다. 같으면 방금 띄운 예제 DB에 붙은 것입니다. '
        '포털의 지식 지도가 담긴 DB는 주소가 다른 DB라서, 여기서 무엇을 만들고 지워도 포털의 지식은 바뀌지 않습니다.</p>'
        +shot('q01-address', '맨 위 Instance 주소의 끝 숫자')
        +'<p>왼쪽 맨 위의 원통 모양 단추를 누르면 이 DB에 무엇이 들어 있는지 나옵니다. 색깔 단추가 레이블, 그 아래가 관계 유형, 맨 아래가 속성 이름입니다.</p>'
        +check('Nodes (20), Relationships (19)가 나옵니다.')
        +shot('q01-overview', '원통 모양 단추와 Nodes (20) · Relationships (19)')
        +'<p>'+b('Stream')+' 바로 왼쪽 단추로 이 패널을 접어 결과 자리를 넓힙니다. 아래 넓은 칸의 시작 안내 카드는 쓰지 않으니 그냥 둡니다. 쿼리는 맨 위 입력칸에만 넣습니다.</p>'
        +shot('q01-collapse', 'Stream 왼쪽의 패널 접기 단추'))
    body = [prepare,
      ('노드 만들기: CREATE',
        '<p>아래 칸을 복사해 맨 위 입력칸에 붙여 넣습니다. CREATE는 적은 모양대로 노드를 새로 만드는 절입니다.</p>'+q('2-1')
        +shot('q02-paste', '맨 위 입력칸에 붙여 넣은 CREATE 쿼리와 오른쪽 끝의 Run')
        +'<p>'+run+'을 한 번만 누르세요. 다시 누르면 같은 노드가 둘 더 생깁니다.</p>'
        +check('Created 2 nodes, set 6 properties, added 2 labels가 나옵니다.')
        +shot('q02-created', '결과 아래 글 Created 2 nodes', False)),
      ('찾아서 돌려받기: MATCH · RETURN',
        '<p>만든 노드를 찾아 돌려받습니다. 쿼리는 늘 '+run+'으로 돌립니다. 결과마다 붙은 Run은 그 쿼리를 한 번 더 돌리는 단추라, 잘못 누르면 앞의 CREATE가 또 돌아갑니다.</p>'+q('3-1')
        +check('원 둘(연습 펌프 · 연습 팬)이 그려지고 선은 없습니다.')
        +shot('q03-graph', '원 둘, 선 없음', False)
        +'<p>원 '+b('연습 펌프')+'를 누르면 오른쪽에 그 노드의 레이블과 속성이 나옵니다.</p>'
        +check('PracticeDevice 이름표 아래 id basic-A, name 연습 펌프, score 40이 있습니다. 맨 윗줄 &lt;id&gt;는 Neo4j가 노드마다 매기는 번호라 쿼리에 적은 id와 다릅니다.')
        +shot('q03-details', '연습 펌프를 누른 뒤 오른쪽 Node details')
        +'<p>결과 칸 왼쪽 위의 '+b('Table')+'을 누르면 같은 결과가 표로 바뀝니다. 찾은 노드 하나가 한 행입니다. '+b('Graph')+'를 누르면 그림으로 돌아옵니다.</p>'
        +shot('q03-table', '결과 칸 왼쪽 위의 Table과 두 행짜리 표')
        +'<p>이번에는 노드 대신 속성 값만 받습니다. AS 뒤 낱말이 표의 열 이름이 되고, ORDER BY가 늘어놓는 차례를 정합니다.</p>'+q('3-2')
        +check('표만 나옵니다. 이름 · 점수 열에 연습 펌프 40, 연습 팬 70 차례입니다.')
        +shot('q03-values', '이름 · 점수 열의 두 행', False)),
      ('조건 더하기: WHERE',
        '<p>WHERE로 점수가 50 이상인 노드만 찾습니다.</p>'+q('4-1')
        +check('연습 팬 하나만 나옵니다. 연습 펌프는 이번 결과에서 빠졌을 뿐 DB에는 남아 있습니다.')
        +shot('q04-where', 'WHERE 결과: 연습 팬 하나', False)),
      ('있으면 찾고 없으면 만들기: MERGE · SET, 관계 잇기',
        '<p>펌프에 달 센서를 만듭니다. MERGE는 적은 패턴이 있으면 찾고, 없을 때만 만듭니다. 괄호 안에 적은 것이 모두 같아야 같은 노드로 보기 때문에, 괄호에는 식별자인 id만 적고 이름과 단위는 SET 줄에 적었습니다.</p>'+q('5-1')
        +check('연습 온도 센서 원 하나가 나오고, 아래 글에 Created 1 node가 있습니다. 없던 센서라 만들었습니다.')
        +shot('q05-merge-new', '첫 MERGE 결과와 아래 글 Created 1 node', False)
        +'<p>같은 쿼리를 한 번 더 돌립니다.</p>'+q('5-2')
        +check('아래 글이 Set 2 properties뿐이고 Created가 없습니다. 새로 만들지 않고 이미 있는 센서를 찾아, SET이 같은 이름과 단위를 다시 적었습니다.')
        +shot('q05-merge-again', '같은 MERGE를 다시 돌린 결과: Set 2 properties', False)
        +'<p>펌프와 센서를 id로 하나씩 찾아, 펌프가 이 센서로 감시된다는 뜻의 관계 유형 MONITORED_BY로 펌프에서 센서로 잇습니다.</p>'+q('5-3')
        +check('펌프에서 센서로 가는 화살표가 하나 생기고, 선 위에 MONITORED_BY가 적혀 있습니다. 오른쪽 목록에도 MONITORED_BY (1)이 보입니다.')
        +shot('q05-linked', '펌프에서 센서로 가는 MONITORED_BY 화살표와 오른쪽 목록', False)),
      ('속성 고치기: SET',
        '<p>펌프에서 MONITORED_BY를 건너 닿는 센서를 찾아 이름을 연습 유온 센서로 고칩니다.</p>'+q('6-1')
        +'<p>바뀐 센서 원을 눌러 오른쪽 속성을 봅니다.</p>'
        +check('name만 연습 유온 센서로 바뀌고 id basic-S1, unit ℃는 그대로입니다. 펌프와 이은 선도 남아 있습니다.')
        +shot('q06-set', '이름이 바뀐 센서와 오른쪽 속성')),
      ('지우고 다시 찾기: DETACH DELETE · DELETE',
        '<p>지운 것은 되돌릴 수 없으니, 맨 위 주소의 끝 숫자가 예제 DB의 숫자인지 한 번 더 보고 시작합니다.</p>'
        '<p>펌프는 센서와 관계로 이어져 있어 DELETE만으로는 지워지지 않습니다. DETACH DELETE는 붙은 관계를 떼어 함께 지웁니다.</p>'+q('7-1')
        +check('Deleted 1 node, deleted 1 relationship이 나옵니다. 그 아래에 아직 보이는 펌프 그림은 지우기 전에 돌린 결과가 남은 것입니다. 결과 칸은 돌릴 때마다 위에 쌓이니, 지금 무엇이 남았는지는 다음 칸으로 다시 찾습니다.')
        +shot('q07-detach', 'Deleted 1 node, deleted 1 relationship', False)
        +'<p>레이블 사이의 세로줄은 「또는」입니다.</p>'+q('7-2')
        +check('연습 팬과 연습 유온 센서만 남고 선은 없습니다.')
        +shot('q07-left', '펌프를 지운 뒤 남은 둘', False)
        +'<p>남은 둘은 관계가 없어 DELETE로 지워집니다.</p>'+q('7-3')
        +check('Deleted 2 nodes가 나옵니다.')
        +'<p>count로 몇 개 남았는지 셉니다.</p>'+q('7-4')
        +check('남은수 0이 나옵니다.')
        +shot('q07-zero', '남은수 0', False)),
      ('설비 데이터를 레이블마다 세기',
        '<p>이제 처음부터 들어 있던 설비 데이터를 봅니다. 레이블이 같은 것끼리 묶어 셉니다.</p>'+q('8-1')
        +check('레이블은 ["Component"]처럼 대괄호와 따옴표에 싸여 나오니 안의 낱말만 봅니다. Component 6, Sensor 5, StateVariable 5, Part 3, Asset 1의 다섯 행이고, 더하면 처음 본 노드 수 20과 같아 설비 데이터는 그대로입니다.')
        +shot('q08-labels', '레이블마다 센 다섯 행', False)),
      ('관계를 한 번 건너기: 한 단계',
        '<p>설비 HYD-01에서 HAS_COMPONENT를 한 번 건너 구성 요소의 이름을 받습니다.</p>'+q('9-1')
        +check('작동유 탱크, 구동 모터, 예비 펌프 (B), 주 펌프 (A), 쿨러 팬, 오일 쿨러의 여섯 행입니다.')
        +shot('q09-one-hop', '구성 요소 이름 여섯 행', False)),
      ('관계를 두 번 건너기: 경로',
        '<p>구성 요소에서 USES_PART를 한 번 더 건너 부품까지 갑니다. 맨 앞의 path = 는 길 전체를 path라는 이름으로 받는다는 뜻입니다.</p>'+q('10-1')
        +check('오른쪽 목록에 Asset (1) · Component (3) · Part (3)이 나옵니다. 구성 요소는 여섯인데 셋만 나온 것은 부품까지 이어진 구성 요소만 찾았기 때문입니다.')
        +shot('q10-path', '설비 · 구성 요소 셋 · 부품 셋의 경로와 오른쪽 목록', False)
        +'<p>같은 패턴에 오일 쿨러라는 조건을 걸고 부품의 이름과 품번을 받습니다.</p>'+q('10-2')
        +check('오일 쿨러 · 쿨러 코어 · P-CLR-CORE 한 행입니다.')
        +shot('q10-part', '오일 쿨러의 부품과 품번', False)),
      ('답이 맞는지 맞춰 보기: 원래 행 · 조건 · 집계',
        '<p>쿼리는 조건을 잘못 적어도 오류 없이 그럴듯한 표를 내놓습니다. 그래서 조건을 걸거나 세기 전에 받은 행(원래 행)과 맞춰 봅니다. 먼저 구성 요소에 MONITORED_BY로 이어진 센서를 조건 없이 받습니다. 센서의 <code>virtual</code> 속성은 계산으로 낸 값인지를 적어 둔 속성이고, 표에는 AS로 붙인 이름인 가상 열로 나옵니다. 쿼리에 쓸 때는 <code>s.virtual</code>입니다.</p>'+q('11-1')
        +check('다섯 행이 원래 행입니다. 가상 열은 계산으로 낸 값이면 TRUE, 실제로 달린 센서면 FALSE이고, 맨 위 오일 쿨러 · 냉각 효율 (가상)만 TRUE입니다.')
        +shot('q11-rows', '원래 행 다섯, 첫 행만 TRUE', False)
        +'<p>이번에는 실제로 달린 센서만 받습니다. 돌리기 전에 답을 정해 둡니다. 가상이 false인 것만 받으면 첫 행이 빠지고 네 행이 남아야 합니다.</p>'+q('11-2')
        +check('네 행이 나오고 가상 열이 모두 FALSE입니다. 정해 둔 답과 같습니다.')
        +shot('q11-where', '조건을 건 네 행', False)
        +'<p>이번에는 구성 요소마다 센서를 셉니다. count는 묶음마다 수를 세고, collect는 그 묶음의 센서 이름을 한 줄로 모읍니다.</p>'+q('11-3')
        +check('오일 쿨러 2, 주 펌프 (A) 2, 쿨러 팬 1이고, 오른쪽 목록의 이름 수가 왼쪽 숫자와 같습니다. 오일 쿨러의 2에는 계산값인 냉각 효율 (가상)이 들어 있어, 실제로 달린 센서 수보다 하나 많습니다. '
               '그리고 이 표에는 센서가 달린 구성 요소 셋만 나옵니다. 센서가 없는 셋은 0인 행도 없이 빠집니다.')
        +shot('q11-aggregate', '구성 요소마다 센서 수와 센서 목록', False))]
    ids = [c['id'] for c in spec['cells']]
    if used != ids:
        raise SystemExit(f'가이드의 칸 차례가 원고와 다르다 — 원고 {ids}, 가이드 {used}')
    for number, (title, content) in enumerate(body, 1):
        want = [i for i in ids if int(i.split('-')[0]) == number]
        got = content.count('<div class="block cypher">')
        if got != len(want):
            raise SystemExit(f'{number:02d}절 「{title}」: Cypher 칸 {got}개 — 원고는 {want}')
    return intro, body
