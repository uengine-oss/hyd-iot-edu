### T01 · process-gpt-memento
- Git: https://github.com/uengine-oss/process-gpt-memento
- Clone: `https://github.com/uengine-oss/process-gpt-memento.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/memento`
- 역할: 문서를 파싱해 원문 페이지·문서/폴더 카드·탐색·검색·파일 접근을 제공한다.
- 연결: 에이전트 입력·메모리·산출물 보관에 연결한다. 벡터 검색은 탐색 보조이며 전체 역할이 아니다.
- 확인 경로: `main.py · docs/specs/ · sql/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-memento/blob/main/README.md)

## 연결 목록

- C01 process-gpt → T01 process-gpt-memento / 등록 / services/memento / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- C02 process-gpt-vue3 → T01 process-gpt-memento / 호출 / 문서·검색 API / [근거](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)
- A01 process-gpt-deepagents → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/README.md)
- A02 process-gpt-base-agent-langchain-react → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-base-agent-langchain-react/blob/main/README.md)
- A04 process-gpt-codex → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md)
- A08 process-gpt-deep-research → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md)
- T03 process-gpt-office-mcp → T01 process-gpt-memento / 호출 / 자료 조회·메모리 또는 산출물 보관 / [근거](https://github.com/uengine-oss/process-gpt-office-mcp/blob/main/README.md)
