### T04 · process-gpt-mcp-validator
- Git: https://github.com/uengine-oss/process-gpt-mcp-validator
- Clone: `https://github.com/uengine-oss/process-gpt-mcp-validator.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/mcp-validator`
- 역할: MCP 설정을 검사하고 실제 연결 상태·도구 목록·오류 진단을 반환한다.
- 연결: Vue의 /mcp-validator/ → /validate API. 업무 수행 에이전트와 도구 설정 검증 서비스를 구분한다.
- 확인 경로: `main.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-mcp-validator/blob/main/README.md)

## 연결 목록

- C01 process-gpt → T04 process-gpt-mcp-validator / 등록 / services/mcp-validator / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → T04 process-gpt-mcp-validator / 호출 / MCP 설정 검사 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
