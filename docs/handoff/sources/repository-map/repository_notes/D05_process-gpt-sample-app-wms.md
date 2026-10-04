### D05 · process-gpt-sample-app-wms
- Git: https://github.com/uengine-oss/process-gpt-sample-app-wms
- Clone: `https://github.com/uengine-oss/process-gpt-sample-app-wms.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/sample-app-wms`
- 역할: 조달·입고·품질·창고 흐름을 ProcessGPT와 연결하는 예제 앱.
- 연결: 자체 frontend/·mcp/·supabase/ 보유. install_processgpt_integration.py로 연결하며 제품 전체 ERP는 아니다.
- 확인 경로: `frontend/ · mcp/main.py · supabase/ · scripts/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-sample-app-wms/blob/main/README.md)

## 연결 목록

- C01 process-gpt → D05 process-gpt-sample-app-wms / 등록 / services/sample-app-wms / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
