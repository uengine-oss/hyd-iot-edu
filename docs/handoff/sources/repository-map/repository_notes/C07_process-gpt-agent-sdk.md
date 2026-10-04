### C07 · process-gpt-agent-sdk
- Git: https://github.com/uengine-oss/process-gpt-agent-sdk
- Clone: `https://github.com/uengine-oss/process-gpt-agent-sdk.git`
- 구분: 연결 확인 / public / 브랜치 `deploy`
- 메인 직접 하위: 아님
- 역할: 작업 폴링·컨텍스트·이벤트/결과 저장·SSE 채팅·테넌트 인증·산출물 공통 기능.
- 연결: 여러 실행체가 사용한다. 소비자별 고정 버전이 다르므로 SDK 최신본 하나로 호환을 가정하지 않는다.
- 확인 경로: `README.md · processgpt_agent_sdk/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-agent-sdk/blob/deploy/README.md)

## 연결 목록

- A01 process-gpt-deepagents → C07 process-gpt-agent-sdk / 의존 / 채팅·폴링 공통 계약 / [근거](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/requirements.txt)
- A03 process-gpt-a2a-orch → C07 process-gpt-agent-sdk / 의존 / A2A 실행 이벤트 / [근거](https://github.com/uengine-oss/process-gpt-a2a-orch/blob/main/README.md)
- A04 process-gpt-codex → C07 process-gpt-agent-sdk / 의존 / 요청·SSE·채팅 저장 / [근거](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md)
- X03 process-gpt-crewai-action → C07 process-gpt-agent-sdk / 의존 / 작업 폴링·결과 이벤트 / [근거](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)
