### T03 · process-gpt-office-mcp
- Git: https://github.com/uengine-oss/process-gpt-office-mcp
- Clone: `https://github.com/uengine-oss/process-gpt-office-mcp.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/office-mcp`
- 역할: HWPX·DOCX·슬라이드 생성·편집·저장을 MCP 도구로 제공한다.
- 연결: Memento 자료 검색, Supabase 보관, 이미지·웹 검색 연동. Deepagents·Deep Research가 활용한다.
- 확인 경로: `main.py · office_mcp/mcp_server.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-office-mcp/blob/main/README.md)

## 연결 목록

- C01 process-gpt → T03 process-gpt-office-mcp / 등록 / services/office-mcp / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- T03 process-gpt-office-mcp → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-office-mcp/blob/main/README.md)
- A01 process-gpt-deepagents → T03 process-gpt-office-mcp / 설정 연결 / Office MCP 주소가 배포 환경에 지정됨 / [근거](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)
- A08 process-gpt-deep-research → T03 process-gpt-office-mcp / 설정 연결 / 문서 출력 시 선택 연동 / [근거](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md)
