"""통합반 첫 Cypher 본편의 실제 큐와 대본을 동기화한다."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
SPEC=Path(__file__).with_name('공통_Cypher_큐.json')
OUTPUT=ROOT/'산출물/통합반/실습/02회차/대본/04_실습_관계조회.md'

def render(spec=None, course='통합반'):
    data=json.loads((spec or SPEC).read_text(encoding='utf-8'))
    titles={'forest001':'앞 이론에서 전체 설비 지도로','forest008':'전체 연결과 노드 속성 읽기','forest016':'한 노드에서 센서 관계로','forest031':'물리량과 조건 탐색','forest047':'교체 부품 경로','forest053':'그림과 집계 대조','forest060':'전체 구조로 돌아와 저장'}
    titles.update({'common001':'생성 안내와 RETURN의 그래프 비교','common009':'MATCH와 반환 형태','common015':'WHERE에서 AND·OR 조합으로','common021':'MERGE와 관계 연결','common033':'SET으로 속성 수정','common042':'관계·노드 삭제와 재조회'})
    actions={'mapLayout':'패널 접기 → Select layout → Hierarchical layout → Zoom to fit. 모두 실제 UI로 수행.', 'mapTour':'설명하는 노드로 커서를 연속 이동하며 전체 구조를 짚는다.', 'graphTalk':'화면에 나온 경로를 짚으며 해석한다.', 'node':'선택 해제·전체 맞춤 → 대상이 읽히도록 실제 줌·이동 → 노드 클릭·속성 확인. 결과 설명은 확인 뒤.', 'edge':'선택 해제·전체 맞춤 → 관계를 화면 안으로 실제 이동 → 화살표 클릭·Relationship details 확인.', 'details':'선택한 노드/관계의 실제 속성을 읽는다.', 'png':'상세 창 접기·선택 해제·화면 맞춤 → PNG 실제 다운로드.', 'intro':'학생 실습 DB 링크의 자동 연결 창. 이전 결과·열린 메뉴 없음.', 'connect':'자동 입력된 접속값을 설명하며 가리키고 Connect 클릭. 실제 연결 완료를 기다린다.', 'connected':'실제 연결 주소·DB 이름을 짚는다.', 'clear':'입력칸 선택 → :clear → Enter → 카드 정리 완료 확인 → 입력 비움. DB 데이터는 보존한다.', 'overview':'Collapse Sidebar → Open Sidebar → Database overview. 전환을 설명하며 수행한다.', 'overviewResult':'실제 노드20·관계19와 레이블·관계 유형을 짚는다.', 'editorTour':'입력칸·Run·결과 영역을 짚는다.', 'query':'입력할 위치와 작업이 전달된 뒤 문장을 넣는다. 한 글자씩 느리게 입력하지 않는다.', 'editorPoint':'설명 중 해당 문장의 위치를 가리킨다.', 'result':'새 결과가 실제로 나타난 뒤 표를 짚어 해석한다.', 'graphResult':'실제 Graph의 노드3·관계2를 확인한 뒤 해석한다.', 'newSaved':'Queries → Add new tab.', 'saveText':'실제로 실행한 문장과 확인 기록을 주석과 함께 입력한다. Ctrl+Home으로 첫 주석 제목을 확인한다.', 'reopen':'자동 저장 목록 확인 → 탭 닫기 → 목록에서 다시 열기 → 문장·기록 보존 확인.', 'download':'Download all → 실제 CSV 내려받기 완료 확인.', 'savedResult':'CSV의 실제 문장·주석과 원본 일치를 확인. 학교 초기화 후 로컬 보존을 약속하지 않는다.', 'outro':'이번 수행과 다음 포털 탐색의 연결을 마무리한다.'}
    out=['# 통합반 2회차 실습 1 — Cypher로 전체 연결을 탐색하고 검증하기','> 강사 단독 진행. 조작 메모는 낭독하지 않는다. 이 원고는 실습 DB 준비 이후 자동 연결 창부터 Browser 저장까지의 본편이다. 자료 다운로드·VS Code 준비 화면은 별도 촬영 의존성이며 본편에서 수행했다고 말하지 않는다.']
    for cue in data['cues']:
        if cue['id'] in titles:out.append('## '+titles[cue['id']])
        out.append(cue['text'])
        if cue.get('label'):out.append(f"> [선택 대상] {cue['label']} · 실제 확인: {cue.get('verify','')}")
        if 'query'in cue:out.append('```cypher\n'+cue['query']+'\n```')
        if cue['op']=='graphResult':
            action='최신 Graph의 노드·관계와 직전 변경 결과를 확인한 뒤 해석한다.'
        elif cue['op']=='basicFit':
            action='왼쪽 도구 패널 접기 → 상세 창 닫기 → Zoom to fit.'
        elif cue['op']=='runSummary':
            action='Run 클릭 → 실제 Created 2 nodes 결과 안내 확인. 그래프를 반환하지 않은 상태를 보여준다.'
        elif cue['op']=='summaryTalk':
            action='실제 생성 안내와 그래프가 반환되지 않은 화면을 짚어 설명한다.'
        elif cue['op']=='intro' and cue['id'].startswith('common0'):
            action='현재 편집기·결과 영역에서 다음 예제의 목적을 안내한다.'
        else:
            action=actions.get(cue['op'],'Run 클릭 → 새 결과 렌더 확인. 다음 발화는 결과 확인 후 시작.')
        out.append(f"> [{cue['id']} · 조작] {action}")
    out[0]='# 두 과정 공통 Cypher 실습 — 그래프를 만들고 수정·삭제한 뒤 설비 연결 탐색하기'
    return '\n\n'.join(out)+'\n'

if __name__=='__main__':
    for course, name in [('통합반','통합반_기본과설비탐색_큐.json'),('실전반','실전반_설비탐색_큐.json')]:
        number='04' if course=='통합반' else '05'
        output=ROOT/f'산출물/{course}/실습/02회차/대본/{number}_실습_관계조회.md'
        output.write_text(render(SPEC,course),encoding='utf-8')
    print('C57 공통 Cypher 큐·두 과정 대본 동기화')
