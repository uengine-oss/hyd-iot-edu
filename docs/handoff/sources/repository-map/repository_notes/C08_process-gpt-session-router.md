### C08 · process-gpt-session-router
- Git: https://github.com/uengine-oss/process-gpt-session-router
- Clone: `https://github.com/uengine-oss/process-gpt-session-router.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 대화별 런너 Pod로 요청을 전달하고 필요 시 생성·유휴 회수한다.
- 연결: Deepagents·Codex 앞단의 세션 라우팅. 비채팅 요청은 기존 서비스로 전달한다.
- 확인 경로: `README.md · cmd/session-router/ · internal/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md)

## 연결 목록

- C08 process-gpt-session-router → A01 process-gpt-deepagents / 선택 라우팅 / 대화별 런너 Pod / 비채팅은 shared 서비스 / [근거](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md)
- C08 process-gpt-session-router → A04 process-gpt-codex / 선택 라우팅 / 대화별 런너 Pod / 비채팅은 shared 서비스 / [근거](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md)
- C06 process-gpt-k8s → C08 process-gpt-session-router / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
