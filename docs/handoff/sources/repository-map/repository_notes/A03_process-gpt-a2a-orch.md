### A03 · process-gpt-a2a-orch
- Git: https://github.com/uengine-oss/process-gpt-a2a-orch
- Clone: `https://github.com/uengine-oss/process-gpt-a2a-orch.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/a2a-orch`
- 역할: 외부 A2A 에이전트로 요청을 전달하고 중간 진행과 결과를 수신하는 프록시 실행체.
- 연결: Agent SDK와 연계. 비동기 모드의 executor와 webhook receiver를 구분하며 수락을 완료로 취급하지 않는다.
- 확인 경로: `a2a_agent_executor.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-a2a-orch/blob/main/README.md)

## 연결 목록

- C01 process-gpt → A03 process-gpt-a2a-orch / 등록 / services/a2a-orch / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- A03 process-gpt-a2a-orch → C07 process-gpt-agent-sdk / 의존 / A2A 실행 이벤트 / [근거](https://github.com/uengine-oss/process-gpt-a2a-orch/blob/main/README.md)
