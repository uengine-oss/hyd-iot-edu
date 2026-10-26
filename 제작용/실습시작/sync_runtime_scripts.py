"""시작 도구와 전용 DB 준비 절차를 강사 대본에 맞춘다. 발화 전체 윤문은 별도다."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    for course in ['통합반','실전반']:
        folder=ROOT/'산출물'/course/'실습/02회차/대본'
        query=next(folder.glob('*_관계조회.md'))
        text=query.read_text(encoding='utf-8')
        start=text.index('## 자료를 내려받고 작업 공간 열기')
        end=text.index('## 한 단계 연결을 조회하기')
        text=text[:start]+'''## 자료를 내려받고 작업 공간 열기

이번에는 설비에서 센서와 교체 부품을 찾아볼게요. 결과가 몇 행 나왔는지만 보지 않고, 어떤 대상이 연결돼서 나온 행인지 확인하겠습니다. 실습 시작 도구에서 관계 조회를 선택하고 새로 시작을 누릅니다.

> [조작] 현재 과정·온라인 02회차·관계 조회 선택 → 새로 시작. VS Code에서 열린 폴더와 START.md를 확인한다. 수동으로 시작할 때는 해당 ZIP만 풀고 그 폴더를 연다.

먼저 조회할 예제를 준비할게요. Docker가 실행된 상태에서 VS Code 터미널에 파이썬 준비 명령을 넣겠습니다. 이 폴더에서 쓸 DB와 예제만 준비하는 명령입니다.

> [조작] `python prepare_example.py` 실행. 노드 20개·관계 19개 준비 완료 표시를 확인한 뒤 이어 간다.

이제 브라우저를 열겠습니다. 터미널에 나온 접속 주소를 사용할 거예요. 앞에서 쓰던 포털의 DB 주소를 넣으면 다른 데이터를 보게 됩니다.

> [조작] `python lab_db.py` 실행 → 열린 Neo4j Browser의 Connect URL에 출력된 bolt 주소 입력. Username은 neo4j, Password는 비움. 연결 완료 후 조회_작성.cypher와 조회_기록.md를 연다.

이 예제에는 설비 한 대의 구성과 계측 채널이 들어 있습니다. 먼저 쿨러에서 센서로 가는 연결 하나부터 조회해 볼게요.

'''+text[end:]
        text=text.replace('이번 제작에서는 실습·캡처를 하지 않았다.','제공 예제 적재·조회는 실행 검증했다. 브라우저 조작·촬영은 별도 확인한다.')
        query.write_text(text,encoding='utf-8')
        graph=next(folder.glob('*_그래프구현과검증.md'))
        text=graph.read_text(encoding='utf-8')
        text=text.replace('적재.cypher','결과/load.cypher').replace('조회.cypher','결과/query.cypher')
        text=text.replace('제공된 랩 DB 주소와 대상 DB를 확인한다. 예제 조회 DB 또는 HYD 기준 DB에 덮어쓰지 않고, 준비된 별도 실습 DB를 사용한다.', '`python lab_db.py`를 실행하고 터미널의 Connect URL로 연결한다. Username은 neo4j, Password는 비운다. 이 폴더 전용 DB를 사용한다.')
        text=text.replace('이번 제작에서는 코드·DB·실습·캡처를 실행하지 않았다.','강사 참조 모델의 DB 검증과 학생 AI 수행·화면 촬영은 구분한다.')
        graph.write_text(text,encoding='utf-8')
    from sync_entry_scripts import main as sync_entries
    sync_entries()
    print('관계 조회·그래프 구현 대본의 시작 절차와 파일명 동기화')

if __name__=='__main__':main()
