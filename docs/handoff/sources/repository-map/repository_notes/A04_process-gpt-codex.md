### A04 · process-gpt-codex
- Git: https://github.com/uengine-oss/process-gpt-codex
- Clone: `https://github.com/uengine-oss/process-gpt-codex.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Vue 채팅을 Codex App Server에 연결하는 파일·문서 작업 실행체.
- 연결: Memento에서 입력 파일을 가져오고 작업 결과를 보관·반환한다. SDK와 역할을 나눠 채팅을 처리한다.
- 확인 경로: `app/executor.py · docs/DEPLOYMENT.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md)

## 연결 목록

- C02 process-gpt-vue3 → A04 process-gpt-codex / 호출 / Codex 채팅 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- A04 process-gpt-codex → C07 process-gpt-agent-sdk / 의존 / 요청·SSE·채팅 저장 / [근거](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md)
- A04 process-gpt-codex → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md)
- C08 process-gpt-session-router → A04 process-gpt-codex / 선택 라우팅 / 대화별 런너 Pod / 비채팅은 shared 서비스 / [근거](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md)
- C06 process-gpt-k8s → A04 process-gpt-codex / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
