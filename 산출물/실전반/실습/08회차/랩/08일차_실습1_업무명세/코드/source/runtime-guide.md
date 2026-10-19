# 실제 작업 위치와 명령

제공 load_graph.py는 단독 배포 프로그램이 아니라 HYD 저장소의 scripts/ontology_v2.py를 사용하는 참조 도구다. 수업에서는 HYD 저장소의 students/<내이름공간>/에 작성 파일과 load_graph.py를 둔다. <내이름공간>을 실제 값으로 바꾼 뒤 저장소 루트에서 다음 순서를 사용한다. 이 문서 제작에서는 명령을 실행하지 않았다.

1. python students/<내이름공간>/load_graph.py check
2. 준비된 DB 접속 환경에서 python students/<내이름공간>/load_graph.py load
3. python students/<내이름공간>/load_graph.py ask

정적 검사와 DB 적재·조회 결과를 구분한다. 참조 example_meeting의 demo는 예시다. 실제 작업 ns와 모든 id 접두어·질의 매개변수를 같은 값으로 맞춘다. 기준 스키마와 다른 작업은 보존한다.

reference는 코드 폴더 밖의 참고 완성 예다. gcal/gdrive, 에이전트 ID, extract 경로에는 실제 연결을 확인해 채울 자리가 있다. 이 예제를 그대로 가져오면 등록을 보장하지 않는다. 이번 작은 업무는 명세에 정한 읽기·제안·사람 확인·보고만 구성하며 외부 일정 생성은 완료로 적지 않는다.
