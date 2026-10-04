### T08 · process-gpt-computer-use
- Git: https://github.com/uengine-oss/process-gpt-computer-use
- Clone: `https://github.com/uengine-oss/process-gpt-computer-use.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/computer-use`
- 역할: 세션별 Kubernetes Pod에서 셸·코드·파일 작업을 수행하는 MCP 서버.
- 연결: 세션 생성·실시간 출력·수명 연장·유휴 정리를 제공한다. 브라우저 전용 서버와 구분한다.
- 확인 경로: `run_server.py · k8s/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-computer-use/blob/main/README.md)

## 연결 목록

- C01 process-gpt → T08 process-gpt-computer-use / 등록 / services/computer-use / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
