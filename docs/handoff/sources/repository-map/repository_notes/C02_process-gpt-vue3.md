### C02 · process-gpt-vue3
- Git: https://github.com/uengine-oss/process-gpt-vue3
- Clone: `https://github.com/uengine-oss/process-gpt-vue3.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/frontend`
- 역할: 주 웹 포털. 프로세스·폼·업무·채팅·분석·온톨로지 화면과 API 연결을 관리한다.
- 연결: Completion, Memento, 에이전트, 분석·전략 서비스로 라우팅한다. ontology/와 DB 마이그레이션도 내부 구성이다.
- 확인 경로: `vite.config.ts · src/services/agentProxyRules.js · ontology/`
- 근거: [vite.config.ts](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) · [src/services/agentProxyRules.js](https://github.com/uengine-oss/process-gpt-vue3/blob/main/src/services/agentProxyRules.js) · [ontology/README.md](https://github.com/uengine-oss/process-gpt-vue3/blob/main/ontology/README.md)

## 연결 목록

- C01 process-gpt → C02 process-gpt-vue3 / 등록 / services/frontend / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → C03 process-gpt-completion / 호출 / 업무 실행·검증 API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → T01 process-gpt-memento / 호출 / 문서·검색 API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → A01 process-gpt-deepagents / 호출 / Deepagents 채팅 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → A02 process-gpt-base-agent-langchain-react / 호출 / /agent/ ReAct API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → A04 process-gpt-codex / 호출 / Codex 채팅 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → A05 process-gpt-cli-agent / 호출 / CLI 선택·실행·파일 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → T04 process-gpt-mcp-validator / 호출 / MCP 설정 검사 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → P01 process-gpt-analytic / 호출 / 분석 API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → P02 process-gpt-instance-classifier / 호출 / 분류·유사 업무 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → P03 process-gpt-strategy / 호출 / 전략·KPI·온톨로지 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → P04 process-gpt-agent-feedback / 호출 / 피드백 제안 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → T07 process-gpt-claude-skills / 호출 / 일부 스킬 검사 경로 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C02 process-gpt-vue3 → C04 process-gpt-gateway / 선택 라우팅 / 에이전트 요청을 게이트웨이 경유 또는 실행체 직결로 전달(환경별 선택) / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/src/services/agentProxyRules.js)
- X01 process-gpt-mobile → C02 process-gpt-vue3 / 화면 사용 / 웹 포털 + mobile-live/shell 앱 에셋 / [근거](https://github.com/uengine-oss/process-gpt-mobile/blob/main/README.md)
