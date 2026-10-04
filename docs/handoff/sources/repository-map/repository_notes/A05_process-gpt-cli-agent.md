### A05 · process-gpt-cli-agent
- Git: https://github.com/uengine-oss/process-gpt-cli-agent
- Clone: `https://github.com/uengine-oss/process-gpt-cli-agent.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 워크아이템 또는 채팅을 CLI 코딩 에이전트에 위임한다.
- 연결: agent_orch=cliagents. 브라우저의 CLI 선택·인증 가능 여부·실행 파일·SSE를 cliagents 라이브러리와 연결한다.
- 확인 경로: `server.py · executor.py · core/bridge.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md)

## 연결 목록

- C02 process-gpt-vue3 → A05 process-gpt-cli-agent / 호출 / CLI 선택·실행·파일 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- A05 process-gpt-cli-agent → A06 cliagents / 의존 / CLI 제공자별 동작 / [근거](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md)
- C06 process-gpt-k8s → A05 process-gpt-cli-agent / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
