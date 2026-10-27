"""통합반 첫 Cypher 본편의 실제 큐와 대본을 동기화한다."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
SPEC=Path(__file__).with_name('통합반_첫Cypher_전체큐.json')
OUTPUT=ROOT/'산출물/통합반/실습/02회차/대본/04_실습_관계조회.md'

def render():
    data=json.loads(SPEC.read_text(encoding='utf-8'))
    titles={'full001':'앞 이론에서 이번 실습으로','full004':'첫 화면과 주요 영역','full008':'노드 하나와 조건 바꾸기','full015':'센서 관계와 표·그래프 비교','full023':'여러 단계 경로와 WHERE','full034':'교체 부품 조회','full038':'센서 목록으로 집계 확인','full043':'저장·재열기·다음 실습'}
    actions={'intro':'학생 실습 DB 링크의 자동 연결 창. 이전 결과·열린 메뉴 없음.', 'connect':'자동 입력된 접속값을 설명하며 가리키고 Connect 클릭. 실제 연결 완료를 기다린다.', 'connected':'실제 연결 주소·DB 이름을 짚는다.', 'clear':'입력칸 선택 → :clear → Enter → 카드 정리 완료 확인 → 입력 비움. DB 데이터는 보존한다.', 'overview':'Collapse Sidebar → Open Sidebar → Database overview. 전환을 설명하며 수행한다.', 'overviewResult':'실제 노드20·관계19와 레이블·관계 유형을 짚는다.', 'editorTour':'입력칸·Run·결과 영역을 짚는다.', 'query':'입력할 위치와 작업이 전달된 뒤 문장을 넣는다. 한 글자씩 느리게 입력하지 않는다.', 'editorPoint':'설명 중 해당 문장의 위치를 가리킨다.', 'result':'새 결과가 실제로 나타난 뒤 표를 짚어 해석한다.', 'graphResult':'실제 Graph의 노드3·관계2를 확인한 뒤 해석한다.', 'newSaved':'Queries → Add new tab.', 'saveText':'실제로 실행한 문장과 확인 기록을 주석과 함께 입력한다. 첫 주석 제목을 확인한다.', 'reopen':'자동 저장 목록 확인 → 탭 닫기 → 목록에서 다시 열기 → 문장·기록 보존 확인.', 'download':'Download all → 실제 CSV 내려받기 완료 확인.', 'savedResult':'CSV의 실제 문장·주석과 원본 일치를 확인. 학교 초기화 후 로컬 보존을 약속하지 않는다.', 'outro':'이번 수행과 다음 포털 탐색의 연결을 마무리한다.'}
    out=['# 통합반 2회차 실습 1 — Cypher 기본 문법 적용과 관계 조회','> 강사 단독 진행. 조작 메모는 낭독하지 않는다. 이 원고는 실습 DB 준비 이후 자동 연결 창부터 Browser 저장까지의 본편이다. 자료 다운로드·VS Code 준비 화면은 별도 촬영 의존성이며 본편에서 수행했다고 말하지 않는다.']
    for cue in data['cues']:
        if cue['id'] in titles:out.append('## '+titles[cue['id']])
        out.append(cue['text'])
        if 'query'in cue:out.append('```cypher\n'+cue['query']+'\n```')
        action=actions.get(cue['op'],'Run 클릭 → 새 결과 렌더 확인. 다음 발화는 결과 확인 후 시작.')
        out.append(f"> [{cue['id']} · 조작] {action}")
    return '\n\n'.join(out)+'\n'

if __name__=='__main__':
    OUTPUT.write_text(render(),encoding='utf-8')
    print('통합반 첫 Cypher 본편 큐·대본 동기화')
