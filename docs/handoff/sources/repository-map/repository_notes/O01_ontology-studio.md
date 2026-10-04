### O01 · ontology-studio
- Git: https://github.com/uengine-oss/ontology-studio
- Clone: `https://github.com/uengine-oss/ontology-studio.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/ontology-studio`
- 역할: 온톨로지 스키마를 설계하고 문서의 엔티티·관계를 Neo4j에 적재·조회하는 앱.
- 연결: 자체 프런트·백엔드·읽기 전용 MCP 보유. ontology_query는 answer와 sources를 반환하며 출처가 비어 있을 수도 있다.
- 확인 경로: `README.md · docs/ontology-mcp-server.md`
- 근거: [README.md](https://github.com/uengine-oss/ontology-studio/blob/main/README.md) · [docs/ontology-mcp-server.md](https://github.com/uengine-oss/ontology-studio/blob/main/docs/ontology-mcp-server.md)

## 연결 목록

- C01 process-gpt → O01 ontology-studio / 등록 / services/ontology-studio / [근거](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules)
- O02 ontologic → O01 ontology-studio / 공유 구성 / 별도 플랫폼이 Studio를 공유; ProcessGPT의 하위라는 뜻은 아님 / [근거](https://github.com/uengine-oss/ontologic/blob/main/.gitmodules)
