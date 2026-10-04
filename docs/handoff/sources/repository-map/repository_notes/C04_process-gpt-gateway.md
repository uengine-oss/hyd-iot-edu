### C04 · process-gpt-gateway
- Git: https://github.com/uengine-oss/process-gpt-gateway
- Clone: `https://github.com/uengine-oss/process-gpt-gateway.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Spring Cloud Gateway 기반 API 진입점. 경로·환경 프로필에 따라 요청을 전달한다.
- 연결: 실행·Memento·음성·결제·MCP 등의 라우팅 담당. Docker의 nginx와 같은 저장소가 아니다.
- 확인 경로: `src/main/resources/application.yml`
- 근거: [src/main/resources/application.yml](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml) · [README.md](https://github.com/uengine-oss/process-gpt-gateway/blob/main/README.md)

## 연결 목록

- C02 process-gpt-vue3 → C04 process-gpt-gateway / 선택 라우팅 / 에이전트 요청을 게이트웨이 경유 또는 실행체 직결로 전달(환경별 선택) / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/src/services/agentProxyRules.js)
- C04 process-gpt-gateway → X02 process-gpt-billing / 호출 / /payments 경로 / [근거](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml)
