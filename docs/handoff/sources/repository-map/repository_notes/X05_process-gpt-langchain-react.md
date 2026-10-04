### X05 · process-gpt-langchain-react
- Git: https://github.com/uengine-oss/process-gpt-langchain-react
- Clone: `https://github.com/uengine-oss/process-gpt-langchain-react.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: MCP Python 인터프리터와 연결하는 별도 ReAct 클라이언트.
- 연결: Python·파일·환경 작업용이다. A02의 업무 보조 서비스와 이름이 유사하지만 다른 저장소다.
- 확인 경로: `mcp_react_client/main.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-langchain-react/blob/main/README.md)

## 연결 목록

- C06 process-gpt-k8s → X05 process-gpt-langchain-react / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
