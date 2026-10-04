### A07 · process-gpt-openai-deep-research
- Git: https://github.com/uengine-oss/process-gpt-openai-deep-research
- Clone: `https://github.com/uengine-oss/process-gpt-openai-deep-research.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/openai-deep-research`
- 역할: 별도 딥리서치 서비스. FastAPI 시작 시 연결을 초기화하고 todolist 폴링을 시작한다.
- 연결: main.py → core.polling_manager. 보고서 알고리즘은 research/·flows/에서 확인한다. A08과 별도 구현이다.
- 확인 경로: `main.py · core/polling_manager.py · research/`
- 근거: [main.py](https://github.com/uengine-oss/process-gpt-openai-deep-research/blob/main/main.py) · [readme.md](https://github.com/uengine-oss/process-gpt-openai-deep-research/blob/main/readme.md)

## 연결 목록

- C01 process-gpt → A07 process-gpt-openai-deep-research / 등록 / services/openai-deep-research / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
