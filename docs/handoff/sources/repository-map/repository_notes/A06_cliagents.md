### A06 · cliagents
- Git: https://github.com/uengine-oss/cliagents
- Clone: `https://github.com/uengine-oss/cliagents.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: CLI별 호출·이벤트·지침·스킬·MCP 설정 차이를 공통 인터페이스로 묶는 라이브러리.
- 연결: A05가 의존한다. CLI 제공자 등록을 관리하며 별도 ProcessGPT 웹 서버는 아니다.
- 확인 경로: `README.md`
- 근거: [README.md](https://github.com/uengine-oss/cliagents/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md)

## 연결 목록

- A05 process-gpt-cli-agent → A06 cliagents / 의존 / CLI 제공자별 동작 / [근거](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md)
