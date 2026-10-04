### P04 · process-gpt-agent-feedback
- Git: https://github.com/uengine-oss/process-gpt-agent-feedback
- Clone: `https://github.com/uengine-oss/process-gpt-agent-feedback.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/agent-feedback`
- 역할: 피드백을 스킬·DMN·프로세스 개선 제안으로 만들고 승인·반려를 처리한다.
- 연결: 완료 업무 피드백 → target별 제안 → 스킬 API 또는 초안·병합 요청. 초안 생성과 운영 정의 반영은 별개다.
- 확인 경로: `main.py · core/ · readme.md`
- 근거: [readme.md](https://github.com/uengine-oss/process-gpt-agent-feedback/blob/main/readme.md)

## 연결 목록

- C01 process-gpt → P04 process-gpt-agent-feedback / 등록 / services/agent-feedback / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → P04 process-gpt-agent-feedback / 호출 / 피드백 제안 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- P04 process-gpt-agent-feedback → A01 process-gpt-deepagents / 호출 / 승인된 스킬 변경을 현재 스킬 API에 전달 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
