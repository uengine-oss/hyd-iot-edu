# Cypher로 그래프를 만들고 수정·삭제한 뒤 설비 탐색하기

1. Docker를 실행하고 VS Code 터미널에서 `python prepare_example.py`를 실행합니다.
2. 「예제 준비 완료: 노드 20개 · 관계 19개」를 확인합니다.
3. `python lab_db.py`를 실행해 Browser를 엽니다. Protocol은 bolt://, Connection URL은 출력 주소의 127.0.0.1:포트 부분, Database user는 neo4j, Password는 빈칸으로 연결합니다.
4. 가이드의 기본 예제를 생성·조회·수정·삭제하고 결과를 확인한 뒤, 준비된 설비의 경로·조건·집계를 조회합니다.
5. 조회_기록.md에 실제 행·집계·원자료 근거를 적고 결과/에 질의와 기록을 저장합니다.

작성한 결과를 다시 열어 확인하고 재부팅 전에 보관할 파일을 USB 또는 개인 클라우드로 복사합니다.
