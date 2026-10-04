### X07 · process-gpt-agent-utils
- Git: https://github.com/uengine-oss/process-gpt-agent-utils
- Clone: `https://github.com/uengine-oss/process-gpt-agent-utils.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: MCP 도구 로딩·지식 검색·사용자 확인·DMN·DB·이벤트 보조 기능 라이브러리.
- 연결: X03의 requirements.txt에 실제 의존성이 있다. Agent SDK와 역할·버전 범위를 구분한다.
- 확인 경로: `README.md · requirements.txt`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-agent-utils/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)

## 연결 목록

- X03 process-gpt-crewai-action → X07 process-gpt-agent-utils / 의존 / 도구·지식·DB 보조 기능 / [근거](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)
