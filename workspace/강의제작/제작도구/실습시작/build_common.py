"""온라인2 과정별 조회 안내와 포털 탐색의 시작본을 연결."""
from build_labs import ROOT,OUT,COURSES,page,write,dump,pack
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
    for number,name,kind in [(1,'02일차_실습1_관계조회','relations'),(2,'02일차_실습2_지식지도탐색','map')]:
        if args.lab is not None and args.lab!=kind:continue
        titles = ('Cypher로 그래프를 생성·조회·수정·삭제하고 설비 관계 탐색하기', '설비 지식의 구조와 연결 관계 탐색하기') if course=='통합반' else ('Cypher로 그래프를 다루고 설비 조회 결과 해석하기', '기준 설비 지식의 실제 연결 구조 확인하기')
        title = titles[number-1]
        folder=OUT/course/'실습/02회차/랩'/name
        if kind == 'relations':
            from graph_guide import common_basic_sections, sections as graph_sections
            for filename in ('lab_db.py', 'prepare_example.py'):
                shutil.copy2(HERE/filename, folder/filename)
            shared=json.loads((ROOT/'workspace/강의제작/제작도구/촬영/neo4j/공통_Cypher_큐.json').read_text(encoding='utf-8'))
            prepare=('실습 DB에 연결하기', '<p>Docker가 실행 중인 PC에서 시작 도구의 관계 조회 실습을 고르고 「새로 시작」을 누르세요. '
                     '이미 이 가이드와 Neo4j Browser가 열렸다면 Browser의 연결 창을 보세요. '
                     '시작 도구에 표시된 실습용 주소와 Connection URL의 주소가 맞는지 확인합니다. '
                     'Protocol은 bolt://를 고르고, Database user에 neo4j를 넣고 Password는 비워 둔 채 Connect를 누르세요. '
                     '연결 뒤 첫 사용 안내 「Work in tabs」가 입력칸을 가리면 Dismiss를 눌러 닫으세요.</p>'
                     '<p>이 주소는 지금 연 실습 전용 데이터베이스입니다. 아래에서 만든 노드와 관계는 여기에 저장됩니다. '
                     '포털 지식 지도는 별도의 기준 데이터베이스에서 읽습니다.</p>')
            sections=graph_sections(shared,prepare)
            sections=sections[:1]+common_basic_sections(shared)+sections[1:]
            queries=[c['query'] for c in shared['cues'] if 'query' in c and c['id'].startswith('common')]
            write(folder/'기본문법_연습.cypher','// Browser 입력칸에서 한 문장씩 실행합니다. CREATE는 한 번만 실행하세요.\n\n'+'\n\n'.join(queries)+'\n')
            # 종전 생성기의 고정 파일만 정리한다. 학생 폴더와 실제 화면 사진은 대상이 아니다.
            for filename in ('AGENTS.md','CLAUDE.md','.github/copilot-instructions.md','조회_기록.md',
                             '조회_작성.cypher','결과/README.md','START.md','준비_안내.md'):
                (folder/filename).unlink(missing_ok=True)
            for sub in ('.github','결과'):
                old=folder/sub
                if old.is_dir() and not any(old.iterdir()):
                    old.rmdir()
        else:
            opening = '포털 시작 결과에 표시된 주소 또는 강사가 안내한 주소를 브라우저에서 엽니다. 왼쪽 메뉴에서 「지식」 → 「지식 지도」를 누르고 설비 칸에서 HYD-01을 선택하세요.'
            if course == '통합반':
                actions = [
                    ('설비에서 오일 쿨러 찾기', opening+' 지도의 설비 열에서 HYD-01 유압 파워팩을 누르세요. 보이지 않으면 이름 검색에 HYD-01을 입력해 강조된 설비를 찾으세요. 지도 아래 상세 칸에서 나가는 관계를 찾고 「구성 요소」 옆 오일 쿨러를 누르세요. 지도에서 항목을 찾기 어렵다면 이름 검색 칸에 오일 쿨러를 입력해 강조된 항목을 찾을 수 있습니다.', 'map-01-search'),
                    ('센서와 교체 부품 찾기', '지도 아래 상세 칸에서 종류와 별칭을 읽으세요. 나가는 관계에서 유온 센서와 교체 부품을 찾아 오일 쿨러와 어떻게 이어지는지 살펴보세요.', 'map-02-cooler'),
                    ('부품 번호 대조하기', '오일 쿨러의 나가는 관계에서 교체 부품인 쿨러 코어를 누르세요. 지도 아래 상세 칸의 품번을 앞 실습에서 확인한 P-CLR-CORE와 대조하세요. 들어오는 관계에서 오일 쿨러를 눌러 같은 연결을 거슬러 돌아오세요.', None),
                    ('센서의 속성 읽기', '유온 센서를 눌러 종류와 tag, unit을 확인하세요. 이 센서에서 나가는 「읽는 상태 변수」 관계를 찾으세요.', 'map-03-sensor'),
                    ('센서가 읽는 물리량 확인하기', '유온이라는 링크가 두 군데 있습니다. 「나가는 관계 → 읽는 상태 변수」 옆의 유온을 누르세요. 센서의 태그와 물리량의 별칭에 TS1이 쓰입니다. 상세 칸에서 종류와 속성이 어떻게 달라졌는지 확인하세요.', 'map-04-statevar'),
                    ('식별자로 다시 찾기', '지도 검색 칸에 sen:ts1을 입력하고 강조된 유온 센서를 누르세요. 이번에는 sv:ts1을 입력하고 강조된 유온을 누르세요. 앞서 관계를 따라 찾은 두 대상 중 어느 쪽이 센서이고 어느 쪽에 한계가 표시되나요?', None),
                    ('예제 그래프와 비교하기', '검색 칸을 비우고 설비를 HYD-02로 바꾸세요. 오일 쿨러를 눌러 들어오는 설비와 나가는 센서를 앞서 본 경로와 비교하세요. 검색 칸에 sen:ts1을 입력해 어느 센서가 강조되는지 확인하세요. 앞의 Cypher 예제에는 설비 한 대가 있었습니다. 수업 기준 지도에서 설비를 바꿨을 때 어떤 연결이 바뀌고 어떤 센서 ID는 그대로였나요?', 'map-05-hyd02'),
                    ('같은 센서명으로 두 계측 채널 찾기', '검색을 지우고 지도 위 이름 공간에서 day02-sensors를 고르세요. 목록에 없으면 「다시 읽기」를 한 번 누르고, 여전히 없으면 강사가 안내한 비교용 포털 주소를 확인하세요. 이름 검색에 유온 센서를 넣으세요. 같은 이름으로 몇 항목이 강조되나요? 검색을 HYD-01:TS1로 바꾸어 강조된 센서를 누르고 asset_code와 instrument_tag를 읽으세요. HYD-02:TS1로도 검색해 어떤 값이 같고 어떤 값이 달라지는지 비교하세요. 이미 상세가 열려 있으면 그 값을 바로 읽으세요.', None),
                    ('수업 기준 지도로 돌아가기', '검색을 지우고 이름 공간을 수업 기준으로 돌리세요. sen:ts1을 검색해 유온 센서를 열어 보세요. 기준 지도에서 센서 종류를 찾을 때와 현장 계기 한 대를 지정할 때 각각 어떤 식별자가 필요할까요?', None),
                ]
            else:
                actions = [
                    ('펌프 축 씰 키트 찾기', opening+' 검색 칸에 씰을 입력하고 펌프 축 씰 키트를 선택하세요.', 'map-01-search'),
                    ('부품 번호 확인하기', '지도 아래 상세 칸에서 종류와 partNo를 확인하세요. 나가는 관계와 들어오는 관계 중 어느 쪽에서 이 부품을 사용하는 구성 요소를 찾을 수 있나요?', 'map-02-part'),
                    ('식별자로 부품 다시 찾기', '이름 검색의 씰을 part:pump-seal로 바꾸세요. 강조된 항목과 상세의 partNo를 처음 보았던 품번과 대조하세요. 상세가 닫혀 있을 때만 해당 부품을 누르세요. 검색에 쓴 그래프 식별자와 부품을 주문할 때 쓰는 품번은 어디에서 확인했나요?', None),
                    ('구성 요소에서 설비로 이동하기', '들어오는 관계에서 주 펌프를 누르고, 상세 칸에서 주 펌프가 속한 설비를 확인하세요.', 'map-03-pump'),
                    ('공급 연결 읽기', '다시 부품을 선택하고 연결된 공급사를 눌러 화면에 표시되는 속성을 읽으세요. 공급 관계만으로 현재 재고와 납품 가능 여부까지 확인할 수 있을까요?', 'map-04-supplier'),
                    ('다른 설비의 사용처 비교하기', '설비를 HYD-02로 바꾸고 이름 검색에 part:pump-seal을 입력하세요. 펌프 축 씰 키트를 열어 partNo를 대조한 뒤 들어오는 「교체 부품」의 주 펌프 (A)를 누르세요. 주 펌프의 들어오는 「구성 요소」에서 어느 설비가 보이나요?', 'map-05-hyd02'),
                    ('세 번째 설비에서 품번 확인하기', 'HYD-03에서도 part:pump-seal로 찾아 상세의 partNo를 대조하세요. 주 펌프에서 소속 설비까지 확인하고, 나가는 관계를 따라 주 펌프와 씰 키트로 돌아오세요.', 'map-06-hyd03'),
                    ('구매 기준 문서 찾기', '씰 키트의 들어오는 관계에서 「순정(OEM) 공급사 표준 발주」를 누르세요. 그 상세의 들어오는 「적용 대상」 중 “승인되지 않은 공급사는”으로 시작하는 규칙을 고르세요. 연결된 「승인 공급사(AVL)」 절을 누르고 PR-07_spare-parts-standard.md를 여세요. 지도 아래 종류가 지식 출처로 바뀌면 문서 이름을 확인하세요. 발주 절차나 규칙이 보이지 않으면 강사가 안내한 구매 기준서가 준비된 지도를 확인하세요.', None),
                    ('공급 승인과 재고 구별하기', '이름 검색에서 part:pump-seal로 부품을 다시 찾아 B-OEM (순정)을 누르세요. avl에 표시된 값을 읽으세요. 이번에는 씰 키트 가용을 검색해 입력 데이터를 열고 「데이터 출처」가 가리키는 시스템을 찾으세요. 지도에서 현재 수량도 확인할 수 있었나요? part:pump-seal을 검색해 부품 상세로 돌아오세요. 공급사 승인 표시만으로 지금 몇 개를 언제 받을 수 있는지 답할 수 있나요?', None),
                ]
            sections = []
            for heading, action, image in actions:
                if image is None:
                    sections.append((heading, f'<p>{action}</p>'))
                    continue
                photo = folder/'images'/f'{image}.jpg'
                if not photo.is_file():
                    raise FileNotFoundError(photo)
                figure = f'<figure><a href="images/{image}.jpg"><img src="images/{image}.jpg" alt="{heading}"></a></figure>'
                sections.append((heading, f'<p>{action}</p>'+figure))
            write(folder/'준비_안내.md', '포털을 열고 [가이드](guide.html)의 화면 순서대로 진행하세요.\n')
            (folder/'START.md').unlink(missing_ok=True)
        for file in ['guide.html','안내.html']:write(folder/file,page(title,'연결된 대상을 확인하고, 결과의 근거를 원자료와 대조합니다.',sections))
        archive=pack(folder)
        catalog['labs'].append({'id':f'{slug}-02-{kind}','course':course,'session':'온라인 02회차','title':title,'version':'2026-11-02-browser-only' if number==1 else '2026-11-02-map-v5-portal','folder':'02회차/랩/'+name,'path':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
        catalog['labs'][-1]['entry']='guide' if kind=='map' else 'neo4j'
catalog['labs'].sort(key=lambda x:(x['course'],x['session'],x['folder']))
dump(HERE/'package-index.json',catalog)
print('두 과정 조회 가이드·독립 시작본과 포털 탐색 연결')
