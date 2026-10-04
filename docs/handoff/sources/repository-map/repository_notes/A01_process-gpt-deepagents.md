### A01 · process-gpt-deepagents
- Git: https://github.com/uengine-oss/process-gpt-deepagents
- Clone: `https://github.com/uengine-oss/process-gpt-deepagents.git`
- 구분: 직접 등록 / private / 브랜치 `master`
- 메인 경로: `services/deepagents`
- 역할: 채팅·워크아이템을 받아 도구를 실행하고 프로세스 정의·스킬·문서를 만든다.
- 연결: Agent SDK가 채팅 경로를 제공한다. Memento·Supabase·Docker 샌드박스와 연결한다.
- 확인 경로: `server.py · executor.py · core/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/README.md) · [requirements.txt](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/requirements.txt)

## 연결 목록

- C01 process-gpt → A01 process-gpt-deepagents / 등록 / services/deepagents / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → A01 process-gpt-deepagents / 호출 / Deepagents 채팅 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- A01 process-gpt-deepagents → C07 process-gpt-agent-sdk / 의존 / 채팅·폴링 공통 계약 / [근거](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/requirements.txt)
- A01 process-gpt-deepagents → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/README.md)
- A01 process-gpt-deepagents → T03 process-gpt-office-mcp / 설정 연결 / Office MCP 주소가 배포 환경에 지정됨 / [근거](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)
- C08 process-gpt-session-router → A01 process-gpt-deepagents / 선택 라우팅 / 대화별 런너 Pod / 비채팅은 shared 서비스 / [근거](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md)
- P04 process-gpt-agent-feedback → A01 process-gpt-deepagents / 호출 / 승인된 스킬 변경을 현재 스킬 API에 전달 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- C06 process-gpt-k8s → A01 process-gpt-deepagents / 배포 정의 / 정의 존재만 확인; 운영 활성 여부 미검증 / [근거](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments)
