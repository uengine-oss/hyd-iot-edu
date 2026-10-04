### T02 · process-gpt-bpmn-extractor
- Git: https://github.com/uengine-oss/process-gpt-bpmn-extractor
- Clone: `https://github.com/uengine-oss/process-gpt-bpmn-extractor.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/bpmn-extractor`
- 역할: 업무 문서에서 프로세스·태스크·역할을 추출해 BPMN·DMN·스킬을 생성한다.
- 연결: Neo4j와 연결하며 API·에이전트 서버·자체 frontend/를 보유한다.
- 확인 경로: `run.py · pdf2bpmn_agent_server.py · frontend/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-bpmn-extractor/blob/main/README.md)

## 연결 목록

- C01 process-gpt → T02 process-gpt-bpmn-extractor / 등록 / services/bpmn-extractor / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- O02 ontologic → T02 process-gpt-bpmn-extractor / 공유 구성 / BPMN 추출·표현 구성 공유 / [근거](https://github.com/uengine-oss/ontologic/blob/main/.gitmodules)
