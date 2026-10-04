### P02 · process-gpt-instance-classifier
- Git: https://github.com/uengine-oss/process-gpt-instance-classifier
- Clone: `https://github.com/uengine-oss/process-gpt-instance-classifier.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/instance-classifier`
- 역할: 처음 입력된 업무 요청을 유사 유형으로 분류하고 Top 요청·과거 처리결과를 제공한다.
- 연결: 폴링 → 요청 텍스트·임베딩 → 유사 매칭·재분류 → 조회 API. pgvector 저장과 BERTopic 분류는 다른 역할이다.
- 확인 경로: `app/poller.py · app/ingest.py · app/server.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-instance-classifier/blob/main/README.md)

## 연결 목록

- C01 process-gpt → P02 process-gpt-instance-classifier / 등록 / services/instance-classifier / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → P02 process-gpt-instance-classifier / 호출 / 분류·유사 업무 / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
