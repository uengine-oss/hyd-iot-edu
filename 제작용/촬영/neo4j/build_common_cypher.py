"""C57 공통 Cypher: 실제 기본 그래프 CRUD 뒤 검증된 설비 탐색으로 연결."""
from pathlib import Path
import copy,json
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent

def build():
    old=json.loads((HERE/'통합반_기본과설비탐색_큐.json').read_text(encoding='utf-8'))
    data=copy.deepcopy(old); cs=copy.deepcopy(old['cues'][:7]); count=0
    cs[0].update(id='common_intro',text='앞 이론에서 사이퍼로 노드와 관계를 표현하는 방법을 배웠습니다. 이번에는 작은 그래프를 직접 만들고, 찾아보고, 속성을 바꾸고, 지우는 데까지 해보겠습니다. 문장을 실행할 때마다 그림과 결과를 확인할게요. 기본 문법을 익힌 다음에는 준비된 설비 데이터에서 여러 단계의 연결을 찾고 필요한 값을 모아 보겠습니다. 먼저 실습 데이터베이스에 접속하겠습니다.')
    def add(text,op,**kw):
        nonlocal count
        count+=1; c=dict(id=f'common{count:03}',segment=1,text=text,op=op,**kw);cs.append(c);return c
    def query(text,q,answer,*,nodes=None,edges=0,rows=None,run=None,check=None):
        add(text,'query',query=q)
        add(run or ('실행해서 그래프를 보겠습니다.' if nodes is not None else '실행해서 결과를 확인하겠습니다.'),'run',graph=nodes is not None,nodes=nodes,edges=edges if nodes is not None else None,rows=rows,expected=check)
        return add(answer,'graphResult' if nodes is not None else 'result')
    def clear(text):add(text,'clear')
    def select(label,verify,text,answer,edge=False):
        add(text,'edge' if edge else 'node',label=label,verify=verify,guided_focus=True)
        add(answer,'details')
    add('이 예제에는 연습장치와 연습센서라는 레이블을 쓰겠습니다. 준비된 설비와 구분해서, 우리가 만든 것만 찾아 수정하고 정리할 수 있게 하려는 겁니다. 먼저 펌프와 팬 두 노드를 만들겠습니다.','intro')
    query('위쪽 입력칸에 크리에이트 문장을 넣겠습니다. 소괄호 하나가 노드 하나를 나타냅니다. 에이와 비는 이 문장 안에서 노드를 가리키는 변수이고, 콜론 뒤 연습장치는 레이블입니다. 중괄호에는 아이디, 이름, 점수를 속성으로 넣었습니다. 마지막에 에이와 비 자체를 반환해서 두 노드를 그림으로 보겠습니다.',"CREATE (a:연습장치 {id:'basic-A', name:'연습 펌프', score:40}),\n       (b:연습장치 {id:'basic-B', name:'연습 팬', score:70})\nRETURN a,b;",'노드 두 개가 생겼습니다. 아직 관계를 만들지 않았으므로 사이에 연결선은 없습니다. 원 안의 이름은 저장한 이름 속성이고, 쿼리에 쓴 에이와 비는 이번 문장의 변수입니다.',nodes=2)
    add('그림을 넓게 보도록 왼쪽 도구 패널을 접겠습니다. 그래프의 화면 맞춤 버튼도 눌러 두 노드가 잘 보이게 하겠습니다.','basicFit')
    select('연습 펌프','basic-A','그래프의 빈 곳을 누르고 화면을 맞추겠습니다. 연습 펌프를 읽기 편한 위치와 크기로 옮긴 다음 눌러 볼게요. 오른쪽에 노드 정보가 열리는지 보겠습니다.','연습장치는 이 노드의 레이블입니다. 아래 속성에서 아이디는 베이직 에이, 이름은 연습 펌프, 점수는 사십인 것을 확인할 수 있습니다. 레이블, 속성, 쿼리의 변수를 이렇게 구분해서 읽으면 됩니다.')
    clear('생성된 모습을 확인했으니 앞의 결과 카드를 정리하고, 같은 노드를 다시 찾아보겠습니다. 콜론 클리어는 화면만 비웁니다. 방금 만든 데이터는 남아 있습니다.')
    query('이번에는 크리에이트 대신 매치를 쓰겠습니다. 연습장치 레이블을 가진 노드를 찾아 엔에 담고, 리턴 엔으로 노드 자체를 받겠습니다. 새로 만드는 문장이 아니라 저장된 대상을 찾는 문장입니다.',"MATCH (n:연습장치)\nRETURN n;",'화면을 비웠어도 두 노드가 다시 나옵니다. 데이터베이스에 저장돼 있기 때문입니다. 이제 같은 노드에서 이름과 점수만 꺼내 보겠습니다.',nodes=2)
    query('리턴 뒤를 엔 점 이름과 엔 점 점수로 바꾸겠습니다. 점 뒤에는 꺼낼 속성 이름을 씁니다. 에이에스는 결과 열 제목을 정하고, 오더 바이는 점수를 기준으로 작은 값부터 정렬합니다.',"MATCH (n:연습장치)\nRETURN n.name AS name,n.score AS score\nORDER BY score;",'펌프 사십, 팬 칠십이 두 행으로 나옵니다. 노드 자체를 반환하면 그래프로, 속성값을 반환하면 표로 확인할 수 있습니다. 같은 데이터를 질문에 맞는 형태로 보는 겁니다.',rows=2,check='70')
    query('이제 매치와 리턴 사이에 웨어를 넣겠습니다. 점수가 오십 이상인 노드만 고르는 조건입니다. 이번에는 노드 자체를 반환해서 어떤 원이 남는지 보겠습니다.',"MATCH (n:연습장치)\nWHERE n.score >= 50\nRETURN n;",'점수가 칠십인 팬만 보입니다. 펌프를 삭제한 것은 아닙니다. 이번 조회 조건에서 제외된 것입니다. 조건을 낮춰 확인해 보겠습니다.',nodes=1)
    query('오십을 삼십으로 바꾸고 다시 실행하겠습니다. 데이터를 수정하는 것이 아니라, 조회 조건 하나만 바꾸는 겁니다.',"MATCH (n:연습장치)\nWHERE n.score >= 30\nRETURN n;",'펌프와 팬이 다시 함께 보입니다. 매치로 찾고, 웨어로 고르고, 리턴으로 무엇을 보여 줄지 정한다는 흐름이 여기까지입니다.',nodes=2)
    clear('조회 결과를 정리하고 센서 하나를 추가하겠습니다. 이번에는 새로 만들기 전에 같은 대상이 있는지 확인하는 머지를 사용하겠습니다.')
    query('머지에는 연습센서 레이블과 아이디를 적겠습니다. 같은 패턴이 있으면 찾아 쓰고, 없으면 만듭니다. 셋으로 이름과 단위를 지정하고, 센서 노드 자체를 반환하겠습니다.',"MERGE (s:연습센서 {id:'basic-S1'})\nSET s.name='연습 온도 센서', s.unit='℃'\nRETURN s;",'연습 온도 센서가 하나 나옵니다. 지금 반환한 것은 센서 하나이므로 앞에서 만든 펌프와 팬은 이 그림에 나오지 않습니다. 다음에는 같은 문장을 다시 실행해 센서가 늘어나는지 보겠습니다.',nodes=1)
    query('머지와 셋은 그대로 다시 실행하고, 뒤에서 센서 수를 세겠습니다. 중간의 위드는 앞의 처리 결과를 다음 절로 넘기는 연결입니다. 뒤의 매치로 연습센서를 찾고 카운트로 개수를 받겠습니다.',"MERGE (s:연습센서 {id:'basic-S1'})\nSET s.name='연습 온도 센서', s.unit='℃'\nWITH s\nMATCH (n:연습센서)\nRETURN count(n) AS sensor_count;",'센서는 여전히 하나입니다. 같은 아이디의 패턴을 찾아 썼기 때문입니다. 크리에이트는 실행할 때마다 새 노드를 만들고, 머지는 적은 패턴을 먼저 찾습니다. 여기서는 한 사람이 순서대로 실행한 결과를 비교하고 있습니다.',rows=1,check='1')
    query('이제 펌프와 센서를 연결하겠습니다. 매치로 두 대상을 찾고, 머지에 펌프에서 센서로 향하는 화살표를 적었습니다. 대괄호 안의 알은 관계 변수, 콜론 뒤 관측은 관계 유형입니다. 피, 알, 에스를 모두 반환해 연결을 보겠습니다.',"MATCH (p:연습장치 {id:'basic-A'}),(s:연습센서 {id:'basic-S1'})\nMERGE (p)-[r:관측]->(s)\nRETURN p,r,s;",'펌프에서 온도 센서로 관측 관계가 생겼습니다. 노드 두 개에 연결선 하나입니다. 이름이 비슷해서 자동으로 연결된 것이 아니라, 방금 쓴 관계 패턴으로 연결한 것입니다.',nodes=2,edges=1)
    select('관측','Relationship details','빈 곳을 눌러 선택을 풀고 화면을 맞추겠습니다. 펌프와 센서 사이의 관측 화살표가 잘 보이게 옮긴 뒤, 이번에는 노드가 아니라 선을 눌러 볼게요.','오른쪽이 관계 정보로 바뀌었습니다. 관측은 관계 유형입니다. 연습장치와 연습센서라는 노드 레이블과 구분해야 합니다. 화살표는 펌프에서 센서로 향하는 관계 방향을 나타냅니다.',True)
    clear('연결을 확인했으니 앞 카드를 비우고, 같은 센서의 이름을 수정하겠습니다. 연결은 그대로 둔 채 속성만 바꿔 보겠습니다.')
    query('매치에서 센서 아이디로 같은 노드를 찾겠습니다. 셋으로 이름을 연습 유온 센서로 바꾸고 센서를 반환합니다. 찾을 기준인 아이디는 유지하고, 바꿀 속성만 셋에 적습니다.',"MATCH (s:연습센서 {id:'basic-S1'})\nSET s.name='연습 유온 센서'\nRETURN s;",'원에 표시되는 이름이 연습 유온 센서로 바뀌었습니다. 새 센서를 만든 것이 아니라 기존 노드의 이름 속성을 바꾼 결과입니다. 속성과 연결도 확인해 보겠습니다.',nodes=1)
    select('연습 유온 센서','basic-S1','빈 곳에서 선택을 풀고 화면을 맞춘 다음, 이름을 바꾼 센서를 누르겠습니다. 오른쪽 속성에서 무엇이 바뀌고 무엇이 남았는지 볼게요.','아이디는 그대로이고 이름만 연습 유온 센서로 바뀌었습니다. 단위도 섭씨로 남아 있습니다. 셋에 적지 않은 속성까지 모두 바뀌는 것은 아닙니다.')
    query('앞에서 만든 관측 관계를 다시 찾겠습니다. 이번에는 문장에 경로를 담을 변수 피를 두고, 그 경로 전체를 반환하겠습니다. 펌프에서 센서로 이어지는 연결을 한 덩어리로 받을 수 있습니다.',"MATCH p=(:연습장치 {id:'basic-A'})-[:관측]->(:연습센서 {id:'basic-S1'})\nRETURN p;",'이름이 바뀐 센서가 펌프와 그대로 연결돼 있습니다. 속성 수정과 관계 생성은 서로 다른 작업이라는 것을 그림으로 확인했습니다.',nodes=2,edges=1)
    clear('이제 삭제를 해보겠습니다. 먼저 관계만 지우고 두 노드는 남겨 두겠습니다. 화면 카드를 비우는 콜론 클리어와 데이터 삭제를 구분해서 보세요.')
    query('매치로 펌프와 센서 사이의 관측 관계를 찾아 알에 담겠습니다. 딜리트 알은 그 관계만 삭제합니다. 리턴에는 남겨 둘 펌프와 센서를 적어, 선이 사라지고 원은 남는지 확인하겠습니다.',"MATCH (p:연습장치 {id:'basic-A'})-[r:관측]->(s:연습센서 {id:'basic-S1'})\nDELETE r\nRETURN p,s;",'원 두 개는 남아 있고 연결선은 없어졌습니다. 관계를 지워도 양 끝 노드를 함께 지우는 것은 아닙니다. 최신 결과 카드의 두 원을 확인하세요.',nodes=2)
    query('다음 삭제 방법을 비교하기 위해 같은 관계를 머지로 다시 연결하겠습니다. 노드를 다시 만드는 것이 아니라, 남아 있는 펌프와 센서 사이의 관계를 복구하는 겁니다.',"MATCH (p:연습장치 {id:'basic-A'}),(s:연습센서 {id:'basic-S1'})\nMERGE (p)-[r:관측]->(s)\nRETURN p,r,s;",'두 노드 사이에 관측 관계가 다시 생겼습니다. 이번에는 연결된 센서 노드를 지워 보겠습니다.',nodes=2,edges=1)
    query('아이디로 연습 센서를 찾고 디태치 딜리트를 쓰겠습니다. 관계가 연결된 노드를 지울 때, 그 관계도 함께 정리하는 명령입니다. 일반 딜리트로 노드만 지우려면 연결된 관계가 없어야 합니다. 이번에는 센서와 그 연결을 함께 지웁니다.',"MATCH (s:연습센서 {id:'basic-S1'})\nDETACH DELETE s\nRETURN count(s) AS removed_sensors;",'센서 하나를 삭제했습니다. 펌프까지 지운 것은 아닙니다. 조회를 다시 실행해서 남은 그래프를 확인하겠습니다.',rows=1,check='1')
    query('연습장치와 연습센서를 다시 찾겠습니다. 웨어의 오어는 두 조건 중 하나를 만족하면 고릅니다. 지금은 펌프와 팬만 남아 있어야 합니다.',"MATCH (n)\nWHERE n:연습장치 OR n:연습센서\nRETURN n;",'펌프와 팬 두 노드만 남았습니다. 센서와 관측 관계는 사라졌습니다. 앞의 결과 카드는 실행 당시 결과이므로, 삭제 뒤 상태는 이렇게 새 조회로 확인합니다.',nodes=2)
    query('남은 두 장치도 정리하겠습니다. 연습장치 레이블에서 이번에 만든 두 아이디만 고르고 딜리트로 삭제합니다. 이제 이 노드들에는 관계가 없으므로 일반 딜리트를 사용할 수 있습니다.',"MATCH (n:연습장치)\nWHERE n.id IN ['basic-A','basic-B']\nDELETE n\nRETURN count(n) AS removed_devices;",'남은 장치 두 개도 삭제했습니다. 준비된 설비 데이터는 대상에 넣지 않았습니다. 연습 데이터가 정말 남지 않았는지 마지막으로 조회해 보겠습니다.',rows=1,check='2')
    query('연습장치 또는 연습센서 레이블을 가진 노드 수를 다시 세겠습니다. 삭제 명령의 출력과 별개로, 저장된 상태를 재조회하는 확인입니다.',"MATCH (n)\nWHERE n:연습장치 OR n:연습센서\nRETURN count(n) AS remaining_practice_nodes;",'남은 연습 노드 수는 영입니다. 생성, 조회, 조건 선택, 속성 수정, 관계 연결과 삭제, 노드 삭제까지 직접 실행하고 결과를 확인했습니다.',rows=1,check='0')
    clear('작은 예제에서 문법을 직접 써 보고 그래프가 어떻게 바뀌는지 확인했습니다. 이제 같은 문법으로 준비된 설비 데이터를 살펴보겠습니다. 지금 사용할 것은 실습용 설비 예제이고, 실제 포털의 지식 지도는 다음 실습에서 탐색합니다. 앞 카드를 비우고 전체 연결부터 보겠습니다.')
    # C57 follow-up: compare RETURN omission and expression grouping explicitly.
    lookup={c['id']:c for c in cs}
    lookup['common002'].update(text='위쪽 입력칸에 크리에이트 문장을 넣겠습니다. 소괄호 하나가 노드 하나를 나타냅니다. 에이와 비는 이 문장 안에서 노드를 가리키는 변수이고, 콜론 뒤 연습장치는 레이블입니다. 중괄호에는 아이디, 이름, 점수를 넣었습니다. 이번에는 리턴 없이 생성만 실행해 보겠습니다.',query="CREATE (a:연습장치 {id:'basic-A', name:'연습 펌프', score:40}),\n       (b:연습장치 {id:'basic-B', name:'연습 팬', score:70});")
    lookup['common003'].update(text='실행해서 노드를 만들겠습니다.',op='runSummary',verify='Created 2 nodes')
    def extra(id,text,op,**kw):return dict(id=id,segment=1,text=text,op=op,**kw)
    idx=next(i for i,c in enumerate(cs) if c['id']=='common004')
    cs[idx:idx]=[
        extra('common003a','노드 두 개를 만들었다는 안내가 나왔습니다. 지금은 그래프가 보이지 않지만 생성은 끝난 상태입니다. 리턴을 쓰지 않아 보여 줄 대상을 돌려받지 않은 겁니다. 생성 문장을 다시 실행하지 않고, 방금 만든 노드를 조회해 보겠습니다.','summaryTalk'),
        extra('common003b','크리에이트를 매치로 바꾸고 연습장치 레이블을 찾겠습니다. 이번에는 리턴 엔을 붙여 찾은 노드 자체를 돌려받습니다. 리턴이 데이터를 만드는 명령은 아닙니다. 실행한 문장에서 무엇을 결과로 받을지 정하는 절입니다.','query',query='MATCH (n:연습장치)\nRETURN n;'),
        extra('common003c','실행해서 저장된 두 노드를 그래프로 보겠습니다.','run',graph=True,nodes=2,edges=0,rows=None)]
    lookup['common004']['text']='연습 펌프와 연습 팬, 두 노드가 보입니다. 앞의 생성 안내에서 확인한 두 노드입니다. 아직 관계를 만들지 않았으므로 사이에 연결선은 없습니다. 원 안의 이름은 저장한 이름 속성이고, 엔은 조회 문장에서 대상을 가리키는 변수입니다.'
    idx=next(i for i,c in enumerate(cs) if c['id']=='common021')
    cs[idx:idx]=[
        extra('common020a','조건 하나의 역할을 확인했으니 조건 두 개를 함께 써보겠습니다. 앞 카드를 정리하고, 펌프나 팬 중에서 점수가 오십 이상인 것만 고르겠습니다.','clear'),
        extra('common020b','괄호 안의 오어는 펌프이거나 팬이면 된다는 뜻입니다. 그 묶음에 앤드로 점수 조건을 붙였습니다. 장치 이름 조건과 점수 조건이 모두 맞아야 남습니다. 먼저 괄호가 있는 문장을 실행해 보겠습니다.','query',query="MATCH (n:연습장치)\nWHERE (n.name='연습 펌프' OR n.name='연습 팬')\n  AND n.score >= 50\nRETURN n;"),
        extra('common020c','실행해서 두 조건을 모두 만족하는 노드를 보겠습니다.','run',graph=True,nodes=1,edges=0,rows=None),
        extra('common020d','팬 하나만 남았습니다. 펌프도 이름 조건은 맞지만 점수가 사십이므로 점수 조건에서 빠집니다. 이번에는 같은 식에서 괄호만 빼보겠습니다.','graphResult'),
        extra('common020e','괄호 없이 적으면 앤드가 오어보다 먼저 묶입니다. 이 문장은 펌프이거나, 팬이면서 점수가 오십 이상인 것을 찾습니다. 앞에서 말한 질문과 범위가 달라진다는 점을 결과로 확인하겠습니다.','query',query="MATCH (n:연습장치)\nWHERE n.name='연습 펌프' OR n.name='연습 팬'\n  AND n.score >= 50\nRETURN n;"),
        extra('common020f','괄호를 뺀 문장을 실행해 보겠습니다.','run',graph=True,nodes=2,edges=0,rows=None),
        extra('common020g','이번에는 펌프도 나왔습니다. 펌프라는 앞 조건만 맞으면 통과하기 때문입니다. 두 문장 모두 실행은 되지만 답은 다릅니다. 펌프나 팬을 고르고, 그중 점수가 오십 이상인 것만 남긴다는 질문이라면 앞의 괄호 있는 식이 맞습니다.','graphResult')]
    # Preserved, validated application footage begins after its whole-map layout cue.
    tail=copy.deepcopy([c for c in old['cues'] if c['id'].startswith('forest') and int(c['id'][6:])>=8 or c['id'] in ['full046','full047']])
    for c in tail:
        if c['id']=='forest010':c['text']='이제 설비 전체를 보기 좋게 배치하겠습니다. 도구 패널은 접어 둔 상태로 보고, 그래프 아래 배치 메뉴에서 계층형 배치를 고르겠습니다. 화면 맞춤을 눌러 전체 연결이 들어오게 할게요. 노드와 관계는 그대로이고 화면 배치만 바꾸는 겁니다.'
    data.update(cues=cs+tail,course='공통',decision='C57',basic_only=False)
    prefix=copy.deepcopy(data);prefix['cues']=cs+tail[:3]
    (HERE/'공통_Cypher_큐.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (HERE/'공통_기본문법_촬영큐.json').write_text(json.dumps(prefix,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('common cues',len(data['cues']),'prefix',len(prefix['cues']),'queries',sum('query'in c for c in cs))

if __name__=='__main__':build()
