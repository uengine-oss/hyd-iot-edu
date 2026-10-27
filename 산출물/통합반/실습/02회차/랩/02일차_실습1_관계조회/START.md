# Cypher로 설비 전체 연결 탐색하기

1. Docker를 실행하고 VS Code 터미널에서 `python prepare_example.py`를 실행합니다.
2. 「예제 준비 완료: 노드 20개 · 관계 19개」를 확인합니다.
3. `python lab_db.py`를 실행해 Browser를 엽니다. Protocol은 bolt://, Connection URL은 출력 주소의 127.0.0.1:포트 부분, Database user는 neo4j, Password는 빈칸으로 연결합니다.
4. 가이드에서 전체 설비 지도를 펼치고 노드·관계의 정보를 확인한 뒤, 질문에 맞춰 경로·조건·집계를 조회합니다.
5. Queries에 문장과 실제 확인 기록을 저장하고 다시 엽니다. CSV와 전체 그래프 PNG를 내려받습니다. 조회_기록.md에도 실제 행·집계·원자료 근거를 남깁니다.

작성한 결과를 다시 열어 확인하고 재부팅 전에 보관할 파일을 USB 또는 개인 클라우드로 복사합니다.
