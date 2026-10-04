### X03 · process-gpt-crewai-action
- Git: https://github.com/uengine-oss/process-gpt-crewai-action
- Clone: `https://github.com/uengine-oss/process-gpt-crewai-action.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: CrewAI 협업 실행체. 요청·컨텍스트를 크루로 실행해 이벤트·폼 결과를 반환한다.
- 연결: Agent SDK 및 Agent Utils 의존성 확인. 기본 하위 목록 밖의 별도 실행체이며 배포 정의도 존재한다.
- 확인 경로: `crewai_action_server.py · crewai_action_executor.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/README.md) · [requirements.txt](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)

## 연결 목록

- X03 process-gpt-crewai-action → C07 process-gpt-agent-sdk / 의존 / 작업 폴링·결과 이벤트 / [근거](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)
- X03 process-gpt-crewai-action → X07 process-gpt-agent-utils / 의존 / 도구·지식·DB 보조 기능 / [근거](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)
- C06 process-gpt-k8s → X03 process-gpt-crewai-action / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
