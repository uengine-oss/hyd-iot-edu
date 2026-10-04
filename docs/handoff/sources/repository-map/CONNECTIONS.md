# 연결 관계 전체 목록

총 67개. 이 목록의 선은 실행 순서뿐 아니라 등록·의존·공유·배포 관계를 포함한다.

- **등록**: 상위 저장소의 .gitmodules에 등록. 런타임 호출과 다름.
- **호출**: 읽은 코드·문서·프록시에 서비스 연결이 있음. 실제 운영 활성은 미검증.
- **의존**: 공통 라이브러리 또는 실행 계약을 사용.
- **선택 라우팅**: 환경·배포 방식에 따라 사용하는 경로.
- **설정 연결**: 서비스 주소가 설정에 지정됨.
- **공유 구성**: 별도 제품이 같은 구성요소를 공유. 상하 종속을 뜻하지 않음.
- **관련 기술**: 기술 계열의 관계만 확인. 직접 호출·호환성을 보증하지 않음.
- **화면 사용**: 기존 웹 포털 또는 앱 에셋을 사용.
- **배포**: Compose의 서비스·이미지 구성.
- **배포 정의**: Kubernetes 설정 파일이 존재. 실제 배포 중인지는 미확인.

| 출발 | 도착 | 종류 | 의미 | 근거 |
|---|---|---|---|---|
| C01 process-gpt | C02 process-gpt-vue3 | 등록 | services/frontend | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | C03 process-gpt-completion | 등록 | services/completion | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | A01 process-gpt-deepagents | 등록 | services/deepagents | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | A02 process-gpt-base-agent-langchain-react | 등록 | services/base-agent-langchain-react | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | A03 process-gpt-a2a-orch | 등록 | services/a2a-orch | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | A07 process-gpt-openai-deep-research | 등록 | services/openai-deep-research | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | A08 process-gpt-deep-research | 등록 | services/deep-research | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | A09 process-gpt-react-voice-agent | 등록 | services/react-voice-agent | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | T01 process-gpt-memento | 등록 | services/memento | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | T02 process-gpt-bpmn-extractor | 등록 | services/bpmn-extractor | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | T03 process-gpt-office-mcp | 등록 | services/office-mcp | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | T04 process-gpt-mcp-validator | 등록 | services/mcp-validator | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | T08 process-gpt-computer-use | 등록 | services/computer-use | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | P01 process-gpt-analytic | 등록 | services/analytic | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | P02 process-gpt-instance-classifier | 등록 | services/instance-classifier | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | P03 process-gpt-strategy | 등록 | services/strategy | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | P04 process-gpt-agent-feedback | 등록 | services/agent-feedback | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | O01 ontology-studio | 등록 | services/ontology-studio | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | D01 bpmn-process-generation-skill | 등록 | skills/bpmn-process-generation-skill | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | D02 process-gpt-strategy-skill | 등록 | skills/bsc-strategy-interview | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | D03 process-gpt-docs.github.io | 등록 | docs/doc-site | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | D04 process-gpt-agents.github.io | 등록 | services/agents.github.io | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C01 process-gpt | D05 process-gpt-sample-app-wms | 등록 | services/sample-app-wms | [파일](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) |
| C02 process-gpt-vue3 | C03 process-gpt-completion | 호출 | 업무 실행·검증 API | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | T01 process-gpt-memento | 호출 | 문서·검색 API | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | A01 process-gpt-deepagents | 호출 | Deepagents 채팅 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | A02 process-gpt-base-agent-langchain-react | 호출 | /agent/ ReAct API | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | A04 process-gpt-codex | 호출 | Codex 채팅 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | A05 process-gpt-cli-agent | 호출 | CLI 선택·실행·파일 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | T04 process-gpt-mcp-validator | 호출 | MCP 설정 검사 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | P01 process-gpt-analytic | 호출 | 분석 API | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | P02 process-gpt-instance-classifier | 호출 | 분류·유사 업무 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | P03 process-gpt-strategy | 호출 | 전략·KPI·온톨로지 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | P04 process-gpt-agent-feedback | 호출 | 피드백 제안 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | T07 process-gpt-claude-skills | 호출 | 일부 스킬 검사 경로 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| C02 process-gpt-vue3 | C04 process-gpt-gateway | 선택 라우팅 | 에이전트 요청을 게이트웨이 경유 또는 실행체 직결로 전달(환경별 선택) | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/src/services/agentProxyRules.js) |
| A01 process-gpt-deepagents | C07 process-gpt-agent-sdk | 의존 | 채팅·폴링 공통 계약 | [파일](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/requirements.txt) |
| A03 process-gpt-a2a-orch | C07 process-gpt-agent-sdk | 의존 | A2A 실행 이벤트 | [파일](https://github.com/uengine-oss/process-gpt-a2a-orch/blob/main/README.md) |
| A04 process-gpt-codex | C07 process-gpt-agent-sdk | 의존 | 요청·SSE·채팅 저장 | [파일](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md) |
| A05 process-gpt-cli-agent | A06 cliagents | 의존 | CLI 제공자별 동작 | [파일](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md) |
| X03 process-gpt-crewai-action | C07 process-gpt-agent-sdk | 의존 | 작업 폴링·결과 이벤트 | [파일](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt) |
| X03 process-gpt-crewai-action | X07 process-gpt-agent-utils | 의존 | 도구·지식·DB 보조 기능 | [파일](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt) |
| A01 process-gpt-deepagents | T01 process-gpt-memento | 호출 | 자료 조회·메모리 또는 산출물 보관 | [파일](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/README.md) |
| A02 process-gpt-base-agent-langchain-react | T01 process-gpt-memento | 호출 | 자료 조회·메모리 또는 산출물 보관 | [파일](https://github.com/uengine-oss/process-gpt-base-agent-langchain-react/blob/main/README.md) |
| A04 process-gpt-codex | T01 process-gpt-memento | 호출 | 자료 조회·메모리 또는 산출물 보관 | [파일](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md) |
| A08 process-gpt-deep-research | T01 process-gpt-memento | 호출 | 자료 조회·메모리 또는 산출물 보관 | [파일](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md) |
| T03 process-gpt-office-mcp | T01 process-gpt-memento | 호출 | 자료 조회·메모리 또는 산출물 보관 | [파일](https://github.com/uengine-oss/process-gpt-office-mcp/blob/main/README.md) |
| A01 process-gpt-deepagents | T03 process-gpt-office-mcp | 설정 연결 | Office MCP 주소가 배포 환경에 지정됨 | [파일](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml) |
| A08 process-gpt-deep-research | T03 process-gpt-office-mcp | 설정 연결 | 문서 출력 시 선택 연동 | [파일](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md) |
| C08 process-gpt-session-router | A01 process-gpt-deepagents | 선택 라우팅 | 대화별 런너 Pod / 비채팅은 shared 서비스 | [파일](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md) |
| C08 process-gpt-session-router | A04 process-gpt-codex | 선택 라우팅 | 대화별 런너 Pod / 비채팅은 shared 서비스 | [파일](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md) |
| P04 process-gpt-agent-feedback | A01 process-gpt-deepagents | 호출 | 승인된 스킬 변경을 현재 스킬 API에 전달 | [파일](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) |
| O02 ontologic | O01 ontology-studio | 공유 구성 | 별도 플랫폼이 Studio를 공유; ProcessGPT의 하위라는 뜻은 아님 | [파일](https://github.com/uengine-oss/ontologic/blob/main/.gitmodules) |
| O02 ontologic | T02 process-gpt-bpmn-extractor | 공유 구성 | BPMN 추출·표현 구성 공유 | [파일](https://github.com/uengine-oss/ontologic/blob/main/.gitmodules) |
| O03 ontological-db | O04 ontological-db-enterprise-custom | 관련 기술 | 같은 Ontological 계열 설명. 기능 차이·호환성은 미확인 | [파일](https://github.com/uengine-oss/ontological-db-enterprise-custom/blob/main/README.md) |
| X01 process-gpt-mobile | C02 process-gpt-vue3 | 화면 사용 | 웹 포털 + mobile-live/shell 앱 에셋 | [파일](https://github.com/uengine-oss/process-gpt-mobile/blob/main/README.md) |
| C04 process-gpt-gateway | X02 process-gpt-billing | 호출 | /payments 경로 | [파일](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml) |
| C05 process-gpt-infra-docker | T06 process-gpt-glossary | 배포 | ProcessGPT용 용어집 이미지·포트 구성 | [파일](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml) |
| C06 process-gpt-k8s | A01 process-gpt-deepagents | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | A04 process-gpt-codex | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | A05 process-gpt-cli-agent | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | T05 process-gpt-visionparser | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | X03 process-gpt-crewai-action | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | X04 process-gpt-crewai-deep-research | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | X05 process-gpt-langchain-react | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | X06 process-gpt-browser-use | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
| C06 process-gpt-k8s | C08 process-gpt-session-router | 배포 정의 | 정의 존재만 확인; 운영 활성 여부 미검증 | [파일](https://github.com/uengine-oss/process-gpt-k8s/tree/main/deployments) |
