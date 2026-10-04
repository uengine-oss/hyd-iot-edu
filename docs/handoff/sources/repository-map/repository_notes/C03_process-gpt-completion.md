### C03 · process-gpt-completion
- Git: https://github.com/uengine-oss/process-gpt-completion
- Clone: `https://github.com/uengine-oss/process-gpt-completion.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/completion`
- 역할: 프로세스 정의·인스턴스·역할·폼 응답을 받아 업무 실행과 완료 처리를 수행한다.
- 연결: API와 polling_service/가 같은 저장소에 있다. 워크아이템 상태를 선택된 에이전트 실행 경로와 연결한다.
- 확인 경로: `main.py · polling_service/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-completion/blob/main/README.md)

## 연결 목록

- C01 process-gpt → C03 process-gpt-completion / 등록 / services/completion / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → C03 process-gpt-completion / 호출 / 업무 실행·검증 API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
