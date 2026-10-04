### A02 · process-gpt-base-agent-langchain-react
- Git: https://github.com/uengine-oss/process-gpt-base-agent-langchain-react
- Clone: `https://github.com/uengine-oss/process-gpt-base-agent-langchain-react.git`
- 구분: 직접 등록 / private / 브랜치 `main`
- 메인 경로: `services/base-agent-langchain-react`
- 역할: ReAct 방식으로 MCP 도구를 사용하는 업무 보조 실행체. SSE·세션·할당 스킬을 지원한다.
- 연결: Vue의 /agent/ 경로, Memento 메모리, 스킬 API에 연결한다. Deepagents와 별도 구현이다.
- 확인 경로: `work_assistant_agent.server · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-base-agent-langchain-react/blob/main/README.md)

## 연결 목록

- C01 process-gpt → A02 process-gpt-base-agent-langchain-react / 등록 / services/base-agent-langchain-react / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → A02 process-gpt-base-agent-langchain-react / 호출 / /agent/ ReAct API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- A02 process-gpt-base-agent-langchain-react → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-base-agent-langchain-react/blob/main/README.md)
