### P01 · process-gpt-analytic
- Git: https://github.com/uengine-oss/process-gpt-analytic
- Clone: `https://github.com/uengine-oss/process-gpt-analytic.git`
- 구분: 직접 등록 / private / 브랜치 `main`
- 메인 경로: `services/analytic`
- 역할: 실행 통계·피벗·타임라인·자연어 SQL 분석을 제공한다.
- 연결: Vue의 /api/analytics 연결. 저장소 내부 backend/와 자체 frontend/를 별도 Git 저장소로 세지 않는다.
- 확인 경로: `backend/app/main.py · frontend/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-analytic/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)

## 연결 목록

- C01 process-gpt → P01 process-gpt-analytic / 등록 / services/analytic / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → P01 process-gpt-analytic / 호출 / 분석 API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
