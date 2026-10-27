"""통합반 첫 Cypher 본편의 실제 큐와 대본을 동기화한다."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
SPEC=Path(__file__).with_name('통합반_그래프탐색_큐.json')
OUTPUT=ROOT/'산출물/통합반/실습/02회차/대본/04_실습_관계조회.md'

def render():
    data=json.loads(SPEC.read_text(encoding='utf-8'))
    titles={'forest001':'앞 이론에서 전체 설비 지도로','forest008':'전체 연결과 노드 속성 읽기','forest016':'한 노드에서 센서 관계로','forest031':'물리량과 조건 탐색','forest047':'교체 부품 경로','forest053':'그림과 집계 대조','forest060':'전체 구조로 돌아와 저장'}
    actions={'mapLayout':'패널 접기 → Select layout → Hierarchical layout → Zoom to fit. 모두 실제 UI로 수행.', 'mapTour':'설명하는 노드로 커서를 연속 이동하며 전체 구조를 짚는다.', 'graphTalk':'화면에 나온 경로를 짚으며 해석한다.', 'node':'대상 노드로 이동·클릭 → 실제 속성 표시 확인. 결과 설명은 확인 뒤.', 'edge':'관계 화살표를 클릭 → Relationship details 확인.', 'details':'선택한 노드/관계의 실제 속성을 읽는다.', 'png':'상세 창 접기·선택 해제·화면 맞춤 → PNG 실제 다운로드.', 'intro':'학생 실습 DB 링크의 자동 연결 창. 이전 결과·열린 메뉴 없음.', 'connect':'자동 입력된 접속값을 설명하며 가리키고 Connect 클릭. 실제 연결 완료를 기다린다.', 'connected':'실제 연결 주소·DB 이름을 짚는다.', 'clear':'입력칸 선택 → :clear → Enter → 카드 정리 완료 확인 → 입력 비움. DB 데이터는 보존한다.', 'overview':'Collapse Sidebar → Open Sidebar → Database overview. 전환을 설명하며 수행한다.', 'overviewResult':'실제 노드20·관계19와 레이블·관계 유형을 짚는다.', 'editorTour':'입력칸·Run·결과 영역을 짚는다.', 'query':'입력할 위치와 작업이 전달된 뒤 문장을 넣는다. 한 글자씩 느리게 입력하지 않는다.', 'editorPoint':'설명 중 해당 문장의 위치를 가리킨다.', 'result':'새 결과가 실제로 나타난 뒤 표를 짚어 해석한다.', 'graphResult':'실제 Graph의 노드3·관계2를 확인한 뒤 해석한다.', 'newSaved':'Queries → Add new tab.', 'saveText':'실제로 실행한 문장과 확인 기록을 주석과 함께 입력한다. Ctrl+Home으로 첫 주석 제목을 확인한다.', 'reopen':'자동 저장 목록 확인 → 탭 닫기 → 목록에서 다시 열기 → 문장·기록 보존 확인.', 'download':'Download all → 실제 CSV 내려받기 완료 확인.', 'savedResult':'CSV의 실제 문장·주석과 원본 일치를 확인. 학교 초기화 후 로컬 보존을 약속하지 않는다.', 'outro':'이번 수행과 다음 포털 탐색의 연결을 마무리한다.'}
    out=['# 통합반 2회차 실습 1 — Cypher로 전체 연결을 탐색하고 검증하기','> 강사 단독 진행. 조작 메모는 낭독하지 않는다. 이 원고는 실습 DB 준비 이후 자동 연결 창부터 Browser 저장까지의 본편이다. 자료 다운로드·VS Code 준비 화면은 별도 촬영 의존성이며 본편에서 수행했다고 말하지 않는다.']
    for cue in data['cues']:
        if cue['id'] in titles:out.append('## '+titles[cue['id']])
        out.append(cue['text'])
        if cue.get('label'):out.append(f"> [선택 대상] {cue['label']} · 실제 확인: {cue.get('verify','')}")
        if 'query'in cue:out.append('```cypher\n'+cue['query']+'\n```')
        action=actions.get(cue['op'],'Run 클릭 → 새 결과 렌더 확인. 다음 발화는 결과 확인 후 시작.')
        out.append(f"> [{cue['id']} · 조작] {action}")
    return '\n\n'.join(out)+'\n'

if __name__=='__main__':
    OUTPUT.write_text(render(),encoding='utf-8')
    print('통합반 첫 Cypher 본편 큐·대본 동기화')
