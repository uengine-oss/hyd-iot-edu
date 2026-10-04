# ProcessGPT 저장소 지도

**기준: 2026-10-03 · 소스코드 미포함 · Robo 계열 제외**

47개 저장소 · 메인 직접 하위 23개 · 내부 경로 8개 · 근거를 붙인 관계 67개

## 1. 범위와 읽는 법

ProcessGPT 프런트엔드·백엔드와 실제 연결 구성을 중심으로 정리했다. 온톨로지 자체 성격의 저장소는 별도 영역에 보존하고, `ontologic`은 관련 플랫폼 노드로만 표시한다. Robo 하위 저장소는 포함하지 않는다.
등록·호출·라이브러리 의존·배포·공유 기술 관계를 구분한다. 저장소가 존재하거나 배포 정의가 있다는 사실은 현재 운영에서 활성화되어 있음을 뜻하지 않는다.
직접 하위 23개 대조 완료. 연결·배포·관련 기술은 구분했으며, 모든 중첩 의존성 전수조사 또는 운영 활성·통합 실행 보증은 아님.

Git URL은 탐색용이다. PRIVATE 링크는 해당 저장소 권한이 있는 GitHub 계정으로 열어야 한다. URL을 제공한다고 권한이 부여되지는 않는다. 아래 공개/비공개 표시는 이 대화에서 확인한 상태이며 변경될 수 있다.

## 2. 대표 연결

- **제품 · 화면:** [process-gpt](https://github.com/uengine-oss/process-gpt) → [process-gpt-vue3](https://github.com/uengine-oss/process-gpt-vue3) — 메인 등록 목록에서 주 Vue 포털로. 서비스별 폴더·Git 이름을 구분합니다.
- **업무 실행:** [process-gpt-vue3](https://github.com/uengine-oss/process-gpt-vue3) → [process-gpt-completion](https://github.com/uengine-oss/process-gpt-completion) — 프런트엔드 요청 → Completion. polling_service/는 같은 저장소 내부입니다.
- **에이전트 작업:** [process-gpt-deepagents](https://github.com/uengine-oss/process-gpt-deepagents) → [process-gpt-agent-sdk](https://github.com/uengine-oss/process-gpt-agent-sdk) — Deepagents 등 실행체가 공통 SDK와 작업·채팅·이벤트 계약을 공유합니다.
- **문서 · 파일:** [process-gpt-deepagents](https://github.com/uengine-oss/process-gpt-deepagents) → [process-gpt-memento](https://github.com/uengine-oss/process-gpt-memento) — 실행체 → Memento. 자료 탐색과 산출물 보관을 연결합니다.
- **전략 · 온톨로지:** [process-gpt-vue3](https://github.com/uengine-oss/process-gpt-vue3) → [process-gpt-strategy](https://github.com/uengine-oss/process-gpt-strategy) — Vue의 전략 화면 → Strategy. AGE 스키마는 Vue 내부 구성도 함께 봅니다.
- **별도 온톨로지:** [ontologic](https://github.com/uengine-oss/ontologic) → [ontology-studio](https://github.com/uengine-oss/ontology-studio) — Ontologic은 관련 플랫폼으로만 표시. Robo 하위 서비스는 펼치지 않습니다.

## 3. 온톨로지 구분

- `process-gpt-vue3/ontology/`: ProcessGPT 내부 AGE 스키마·SQL·명세. 별도 저장소가 아니다.
- `process-gpt-strategy`: 전략·KPI·운영 온톨로지 서비스.
- `ontology-studio`: 문서에서 엔티티·관계를 적재하고 Neo4j·읽기 전용 MCP로 조회하는 앱.
- `ontologic`: 별도 플랫폼. 공유 구성만 표시하며 하위 서비스는 범위 밖이다.
- `ontological-db` / `ontological-db-enterprise-custom`: 별도 PostgreSQL 온톨로지 DB 계열. ProcessGPT 직접 실행 의존성은 미확인이다.
- `process-gpt-knowledge-graph`: main 트리에서 README와 .gitignore만 확인. 현행 그래프 실행체로 단정하지 않는다.

## 메인 · 프런트엔드 · 공통 기반

### C01 · process-gpt
- Git: https://github.com/uengine-oss/process-gpt
- Clone: `https://github.com/uengine-oss/process-gpt.git`
- 구분: 메인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 제품 메타 프로젝트. 서비스·스킬·문서·예제를 등록하고 통합 안내를 제공한다.
- 연결: 23개 직접 하위 저장소의 출발점. 각 하위의 고정 커밋과 원격 최신 브랜치는 별개다.
- 확인 경로: `.gitmodules · README.md`
- 근거: [.gitmodules](https://github.com/uengine-oss/process-gpt/blob/main/.gitmodules) · [README.md](https://github.com/uengine-oss/process-gpt/blob/main/README.md)

### C02 · process-gpt-vue3
- Git: https://github.com/uengine-oss/process-gpt-vue3
- Clone: `https://github.com/uengine-oss/process-gpt-vue3.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/frontend`
- 역할: 주 웹 포털. 프로세스·폼·업무·채팅·분석·온톨로지 화면과 API 연결을 관리한다.
- 연결: Completion, Memento, 에이전트, 분석·전략 서비스로 라우팅한다. ontology/와 DB 마이그레이션도 내부 구성이다.
- 확인 경로: `vite.config.ts · src/services/agentProxyRules.js · ontology/`
- 근거: [vite.config.ts](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts) · [src/services/agentProxyRules.js](https://github.com/uengine-oss/process-gpt-vue3/blob/main/src/services/agentProxyRules.js) · [ontology/README.md](https://github.com/uengine-oss/process-gpt-vue3/blob/main/ontology/README.md)

### C03 · process-gpt-completion
- Git: https://github.com/uengine-oss/process-gpt-completion
- Clone: `https://github.com/uengine-oss/process-gpt-completion.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/completion`
- 역할: 프로세스 정의·인스턴스·역할·폼 응답을 받아 업무 실행과 완료 처리를 수행한다.
- 연결: API와 polling_service/가 같은 저장소에 있다. 워크아이템 상태를 선택된 에이전트 실행 경로와 연결한다.
- 확인 경로: `main.py · polling_service/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-completion/blob/main/README.md)

### C04 · process-gpt-gateway
- Git: https://github.com/uengine-oss/process-gpt-gateway
- Clone: `https://github.com/uengine-oss/process-gpt-gateway.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Spring Cloud Gateway 기반 API 진입점. 경로·환경 프로필에 따라 요청을 전달한다.
- 연결: 실행·Memento·음성·결제·MCP 등의 라우팅 담당. Docker의 nginx와 같은 저장소가 아니다.
- 확인 경로: `src/main/resources/application.yml`
- 근거: [src/main/resources/application.yml](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml) · [README.md](https://github.com/uengine-oss/process-gpt-gateway/blob/main/README.md)

### C05 · process-gpt-infra-docker
- Git: https://github.com/uengine-oss/process-gpt-infra-docker
- Clone: `https://github.com/uengine-oss/process-gpt-infra-docker.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 로컬 배포 정의. 애플리케이션과 Supabase·Neo4j·LiteLLM·nginx를 묶는다.
- 연결: 자체 서비스 서브모듈과 DB 초기화·라우팅 파일을 보유한다. 문서상 경로와 실제 등록은 대조해야 한다.
- 확인 경로: `docker-compose.yml · .gitmodules · nginx/ · volumes/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/README.md) · [.gitmodules](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/.gitmodules) · [docker-compose.yml](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)

### C06 · process-gpt-k8s
- Git: https://github.com/uengine-oss/process-gpt-k8s
- Clone: `https://github.com/uengine-oss/process-gpt-k8s.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Kubernetes Deployment·Service·런너 템플릿 등 배포 구성을 모은다.
- 연결: 메인 하위 목록에 없는 선택 실행체도 나타난다. 배포 파일 존재와 현재 운영 중임은 다르다.
- 확인 경로: `deployments/ · services/`
- 근거: [deployments/process-gpt-deepagents.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-deepagents.yaml) · [deployments/process-gpt-codex.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-codex.yaml) · [deployments/agent-runner-templates.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/agent-runner-templates.yaml)

### C07 · process-gpt-agent-sdk
- Git: https://github.com/uengine-oss/process-gpt-agent-sdk
- Clone: `https://github.com/uengine-oss/process-gpt-agent-sdk.git`
- 구분: 연결 확인 / public / 브랜치 `deploy`
- 메인 직접 하위: 아님
- 역할: 작업 폴링·컨텍스트·이벤트/결과 저장·SSE 채팅·테넌트 인증·산출물 공통 기능.
- 연결: 여러 실행체가 사용한다. 소비자별 고정 버전이 다르므로 SDK 최신본 하나로 호환을 가정하지 않는다.
- 확인 경로: `README.md · processgpt_agent_sdk/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-agent-sdk/blob/deploy/README.md)

### C08 · process-gpt-session-router
- Git: https://github.com/uengine-oss/process-gpt-session-router
- Clone: `https://github.com/uengine-oss/process-gpt-session-router.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 대화별 런너 Pod로 요청을 전달하고 필요 시 생성·유휴 회수한다.
- 연결: Deepagents·Codex 앞단의 세션 라우팅. 비채팅 요청은 기존 서비스로 전달한다.
- 확인 경로: `README.md · cmd/session-router/ · internal/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-session-router/blob/main/README.md)

## 에이전트 실행체

### A01 · process-gpt-deepagents
- Git: https://github.com/uengine-oss/process-gpt-deepagents
- Clone: `https://github.com/uengine-oss/process-gpt-deepagents.git`
- 구분: 직접 등록 / private / 브랜치 `master`
- 메인 경로: `services/deepagents`
- 역할: 채팅·워크아이템을 받아 도구를 실행하고 프로세스 정의·스킬·문서를 만든다.
- 연결: Agent SDK가 채팅 경로를 제공한다. Memento·Supabase·Docker 샌드박스와 연결한다.
- 확인 경로: `server.py · executor.py · core/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/README.md) · [requirements.txt](https://github.com/uengine-oss/process-gpt-deepagents/blob/master/requirements.txt)

### A02 · process-gpt-base-agent-langchain-react
- Git: https://github.com/uengine-oss/process-gpt-base-agent-langchain-react
- Clone: `https://github.com/uengine-oss/process-gpt-base-agent-langchain-react.git`
- 구분: 직접 등록 / private / 브랜치 `main`
- 메인 경로: `services/base-agent-langchain-react`
- 역할: ReAct 방식으로 MCP 도구를 사용하는 업무 보조 실행체. SSE·세션·할당 스킬을 지원한다.
- 연결: Vue의 /agent/ 경로, Memento 메모리, 스킬 API에 연결한다. Deepagents와 별도 구현이다.
- 확인 경로: `work_assistant_agent.server · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-base-agent-langchain-react/blob/main/README.md)

### A03 · process-gpt-a2a-orch
- Git: https://github.com/uengine-oss/process-gpt-a2a-orch
- Clone: `https://github.com/uengine-oss/process-gpt-a2a-orch.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/a2a-orch`
- 역할: 외부 A2A 에이전트로 요청을 전달하고 중간 진행과 결과를 수신하는 프록시 실행체.
- 연결: Agent SDK와 연계. 비동기 모드의 executor와 webhook receiver를 구분하며 수락을 완료로 취급하지 않는다.
- 확인 경로: `a2a_agent_executor.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-a2a-orch/blob/main/README.md)

### A04 · process-gpt-codex
- Git: https://github.com/uengine-oss/process-gpt-codex
- Clone: `https://github.com/uengine-oss/process-gpt-codex.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Vue 채팅을 Codex App Server에 연결하는 파일·문서 작업 실행체.
- 연결: Memento에서 입력 파일을 가져오고 작업 결과를 보관·반환한다. SDK와 역할을 나눠 채팅을 처리한다.
- 확인 경로: `app/executor.py · docs/DEPLOYMENT.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-codex/blob/main/README.md)

### A05 · process-gpt-cli-agent
- Git: https://github.com/uengine-oss/process-gpt-cli-agent
- Clone: `https://github.com/uengine-oss/process-gpt-cli-agent.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 워크아이템 또는 채팅을 CLI 코딩 에이전트에 위임한다.
- 연결: agent_orch=cliagents. 브라우저의 CLI 선택·인증 가능 여부·실행 파일·SSE를 cliagents 라이브러리와 연결한다.
- 확인 경로: `server.py · executor.py · core/bridge.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md)

### A06 · cliagents
- Git: https://github.com/uengine-oss/cliagents
- Clone: `https://github.com/uengine-oss/cliagents.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: CLI별 호출·이벤트·지침·스킬·MCP 설정 차이를 공통 인터페이스로 묶는 라이브러리.
- 연결: A05가 의존한다. CLI 제공자 등록을 관리하며 별도 ProcessGPT 웹 서버는 아니다.
- 확인 경로: `README.md`
- 근거: [README.md](https://github.com/uengine-oss/cliagents/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md](https://github.com/uengine-oss/process-gpt-cli-agent/blob/main/README.md)

### A07 · process-gpt-openai-deep-research
- Git: https://github.com/uengine-oss/process-gpt-openai-deep-research
- Clone: `https://github.com/uengine-oss/process-gpt-openai-deep-research.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/openai-deep-research`
- 역할: 별도 딥리서치 서비스. FastAPI 시작 시 연결을 초기화하고 todolist 폴링을 시작한다.
- 연결: main.py → core.polling_manager. 보고서 알고리즘은 research/·flows/에서 확인한다. A08과 별도 구현이다.
- 확인 경로: `main.py · core/polling_manager.py · research/`
- 근거: [main.py](https://github.com/uengine-oss/process-gpt-openai-deep-research/blob/main/main.py) · [readme.md](https://github.com/uengine-oss/process-gpt-openai-deep-research/blob/main/readme.md)

### A08 · process-gpt-deep-research
- Git: https://github.com/uengine-oss/process-gpt-deep-research
- Clone: `https://github.com/uengine-oss/process-gpt-deep-research.git`
- 구분: 직접 등록 / public / 브랜치 `master`
- 메인 경로: `services/deep-research`
- 역할: 웹·내부 자료를 결합해 리서치 보고서·차트·이미지·템플릿 문서를 생성한다.
- 연결: Tavily·선택적 Memento·Office MCP·Supabase 및 SDK 폴링에 연결한다.
- 확인 경로: `main.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-deep-research/blob/master/README.md)

### A09 · process-gpt-react-voice-agent
- Git: https://github.com/uengine-oss/process-gpt-react-voice-agent
- Clone: `https://github.com/uengine-oss/process-gpt-react-voice-agent.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/react-voice-agent`
- 역할: ProcessGPT 음성 상호작용 서비스. 이름만 보고 React 화면 전용 저장소로 보면 안 된다.
- 연결: 조회한 README의 실행 진입점은 Python server/app.py이며 OpenAI·Supabase 설정을 사용한다.
- 확인 경로: `server/app.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-react-voice-agent/blob/main/README.md)

## 지식 · 문서 · 도구

### T01 · process-gpt-memento
- Git: https://github.com/uengine-oss/process-gpt-memento
- Clone: `https://github.com/uengine-oss/process-gpt-memento.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/memento`
- 역할: 문서를 파싱해 원문 페이지·문서/폴더 카드·탐색·검색·파일 접근을 제공한다.
- 연결: 에이전트 입력·메모리·산출물 보관에 연결한다. 벡터 검색은 탐색 보조이며 전체 역할이 아니다.
- 확인 경로: `main.py · docs/specs/ · sql/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-memento/blob/main/README.md)

### T02 · process-gpt-bpmn-extractor
- Git: https://github.com/uengine-oss/process-gpt-bpmn-extractor
- Clone: `https://github.com/uengine-oss/process-gpt-bpmn-extractor.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/bpmn-extractor`
- 역할: 업무 문서에서 프로세스·태스크·역할을 추출해 BPMN·DMN·스킬을 생성한다.
- 연결: Neo4j와 연결하며 API·에이전트 서버·자체 frontend/를 보유한다.
- 확인 경로: `run.py · pdf2bpmn_agent_server.py · frontend/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-bpmn-extractor/blob/main/README.md)

### T03 · process-gpt-office-mcp
- Git: https://github.com/uengine-oss/process-gpt-office-mcp
- Clone: `https://github.com/uengine-oss/process-gpt-office-mcp.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/office-mcp`
- 역할: HWPX·DOCX·슬라이드 생성·편집·저장을 MCP 도구로 제공한다.
- 연결: Memento 자료 검색, Supabase 보관, 이미지·웹 검색 연동. Deepagents·Deep Research가 활용한다.
- 확인 경로: `main.py · office_mcp/mcp_server.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-office-mcp/blob/main/README.md)

### T04 · process-gpt-mcp-validator
- Git: https://github.com/uengine-oss/process-gpt-mcp-validator
- Clone: `https://github.com/uengine-oss/process-gpt-mcp-validator.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/mcp-validator`
- 역할: MCP 설정을 검사하고 실제 연결 상태·도구 목록·오류 진단을 반환한다.
- 연결: Vue의 /mcp-validator/ → /validate API. 업무 수행 에이전트와 도구 설정 검증 서비스를 구분한다.
- 확인 경로: `main.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-mcp-validator/blob/main/README.md)

### T05 · process-gpt-visionparser
- Git: https://github.com/uengine-oss/process-gpt-visionparser
- Clone: `https://github.com/uengine-oss/process-gpt-visionparser.git`
- 구분: 연결 확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: PDF·이미지 OCR과 스키마 기반 구조화 정보 추출 파이프라인.
- 연결: Agent SDK/A2A·Supabase로 작업 관리·진행 이벤트를 연결한다. Kubernetes 배포 정의도 확인된다.
- 확인 경로: `README.md · pyproject.toml`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-visionparser/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-visionparser.yaml](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/process-gpt-visionparser.yaml)

### T06 · process-gpt-glossary
- Git: https://github.com/uengine-oss/process-gpt-glossary
- Clone: `https://github.com/uengine-oss/process-gpt-glossary.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 용어집·용어·태그 등 메타데이터와 일괄 가져오기·추출 기능을 제공한다.
- 연결: 자체 backend/·frontend/와 Postgres 저장. ProcessGPT Compose에 연결된 용어집 구성만 다룬다.
- 확인 경로: `backend/main.py · frontend/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-glossary/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml](https://github.com/uengine-oss/process-gpt-infra-docker/blob/main/docker-compose.yml)

### T07 · process-gpt-claude-skills
- Git: https://github.com/uengine-oss/process-gpt-claude-skills
- Clone: `https://github.com/uengine-oss/process-gpt-claude-skills.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 스킬 검색·문서 읽기·점진적 로딩을 제공하는 별도 스킬 서비스.
- 연결: Vue에 일부 경로가 남지만 주요 스킬 관리 API는 Deepagents로 이동했다. 모든 스킬 API의 소유자로 보면 안 된다.
- 확인 경로: `README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-claude-skills/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)

### T08 · process-gpt-computer-use
- Git: https://github.com/uengine-oss/process-gpt-computer-use
- Clone: `https://github.com/uengine-oss/process-gpt-computer-use.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/computer-use`
- 역할: 세션별 Kubernetes Pod에서 셸·코드·파일 작업을 수행하는 MCP 서버.
- 연결: 세션 생성·실시간 출력·수명 연장·유휴 정리를 제공한다. 브라우저 전용 서버와 구분한다.
- 확인 경로: `run_server.py · k8s/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-computer-use/blob/main/README.md)

## 분석 · 성과 · 개선

### P01 · process-gpt-analytic
- Git: https://github.com/uengine-oss/process-gpt-analytic
- Clone: `https://github.com/uengine-oss/process-gpt-analytic.git`
- 구분: 직접 등록 / private / 브랜치 `main`
- 메인 경로: `services/analytic`
- 역할: 실행 통계·피벗·타임라인·자연어 SQL 분석을 제공한다.
- 연결: Vue의 /api/analytics 연결. 저장소 내부 backend/와 자체 frontend/를 별도 Git 저장소로 세지 않는다.
- 확인 경로: `backend/app/main.py · frontend/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-analytic/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)

### P02 · process-gpt-instance-classifier
- Git: https://github.com/uengine-oss/process-gpt-instance-classifier
- Clone: `https://github.com/uengine-oss/process-gpt-instance-classifier.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/instance-classifier`
- 역할: 처음 입력된 업무 요청을 유사 유형으로 분류하고 Top 요청·과거 처리결과를 제공한다.
- 연결: 폴링 → 요청 텍스트·임베딩 → 유사 매칭·재분류 → 조회 API. pgvector 저장과 BERTopic 분류는 다른 역할이다.
- 확인 경로: `app/poller.py · app/ingest.py · app/server.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-instance-classifier/blob/main/README.md)

### P03 · process-gpt-strategy
- Git: https://github.com/uengine-oss/process-gpt-strategy
- Clone: `https://github.com/uengine-oss/process-gpt-strategy.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/strategy`
- 역할: BSC 전략목표·KPI·실행과제·설문·성과 측정과 기업 운영 온톨로지를 관리한다.
- 연결: 실행 데이터에서 성과를 수집하며 AGE 그래프를 조회·동기화한다. DB_*와 GRAPH_DB_* 설정을 구분한다.
- 확인 경로: `app/main.py · docker-compose.age.yml · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-strategy/blob/main/README.md)

### P04 · process-gpt-agent-feedback
- Git: https://github.com/uengine-oss/process-gpt-agent-feedback
- Clone: `https://github.com/uengine-oss/process-gpt-agent-feedback.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/agent-feedback`
- 역할: 피드백을 스킬·DMN·프로세스 개선 제안으로 만들고 승인·반려를 처리한다.
- 연결: 완료 업무 피드백 → target별 제안 → 스킬 API 또는 초안·병합 요청. 초안 생성과 운영 정의 반영은 별개다.
- 확인 경로: `main.py · core/ · readme.md`
- 근거: [readme.md](https://github.com/uengine-oss/process-gpt-agent-feedback/blob/main/readme.md)

## 온톨로지 · 지식그래프

### O01 · ontology-studio
- Git: https://github.com/uengine-oss/ontology-studio
- Clone: `https://github.com/uengine-oss/ontology-studio.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/ontology-studio`
- 역할: 온톨로지 스키마를 설계하고 문서의 엔티티·관계를 Neo4j에 적재·조회하는 앱.
- 연결: 자체 프런트·백엔드·읽기 전용 MCP 보유. ontology_query는 answer와 sources를 반환하며 출처가 비어 있을 수도 있다.
- 확인 경로: `README.md · docs/ontology-mcp-server.md`
- 근거: [README.md](https://github.com/uengine-oss/ontology-studio/blob/main/README.md) · [docs/ontology-mcp-server.md](https://github.com/uengine-oss/ontology-studio/blob/main/docs/ontology-mcp-server.md)

### O02 · ontologic
- Git: https://github.com/uengine-oss/ontologic
- Clone: `https://github.com/uengine-oss/ontologic.git`
- 구분: 관련 플랫폼 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Ontologic Platform의 메타 프로젝트. 별도 데이터·온톨로지 플랫폼의 구성을 묶는다.
- 연결: ProcessGPT의 직접 하위가 아니다. 공유 구성과 플랫폼 관계만 표시하며 자체 하위 서비스는 이 지도에서 펼치지 않는다.
- 확인 경로: `.gitmodules`
- 근거: [.gitmodules](https://github.com/uengine-oss/ontologic/blob/main/.gitmodules)

### O03 · ontological-db
- Git: https://github.com/uengine-oss/ontological-db
- Clone: `https://github.com/uengine-oss/ontological-db.git`
- 구분: 관련 기술 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: PostgreSQL 내부에서 동작하는 온톨로지 그래프 DB. 타입 계층·관계·벡터 및 Cypher/TypeQL 질의를 제공한다.
- 연결: 온톨로지 자체 기술로 포함한다. Apache AGE와 별개 프로젝트이며 ProcessGPT의 필수 실행 의존성은 미확인이다.
- 확인 경로: `README.md · engine/ · portal/`
- 근거: [README.md](https://github.com/uengine-oss/ontological-db/blob/main/README.md)

### O04 · ontological-db-enterprise-custom
- Git: https://github.com/uengine-oss/ontological-db-enterprise-custom
- Clone: `https://github.com/uengine-oss/ontological-db-enterprise-custom.git`
- 구분: 관련 기술 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Ontological 계열의 별도 Enterprise/custom 저장소. 조회한 README의 기본 설명은 O03과 같다.
- 연결: 비공개 관련 기술로 포함한다. 공개판 대비 기업 전용 기능 차이와 ProcessGPT 직접 호출은 확정하지 않았다.
- 확인 경로: `README.md`
- 근거: [README.md](https://github.com/uengine-oss/ontological-db-enterprise-custom/blob/main/README.md)

### O05 · process-gpt-knowledge-graph
- Git: https://github.com/uengine-oss/process-gpt-knowledge-graph
- Clone: `https://github.com/uengine-oss/process-gpt-knowledge-graph.git`
- 구분: 구현 미확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: Knowledge Graph 이름의 저장소. 확인한 main 트리에는 README.md와 .gitignore만 있다.
- 연결: 주소는 보존하되 현행 그래프 엔진이나 실행 서비스로 표시하지 않는다. 과거 목적·현재 용도는 미확인이다.
- 확인 경로: `README.md · main 트리`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-knowledge-graph/blob/main/README.md) · [https://api.github.com/repos/uengine-oss/process-gpt-knowledge-graph/git/trees/main?recursive=1](https://api.github.com/repos/uengine-oss/process-gpt-knowledge-graph/git/trees/main?recursive=1)

## 스킬 · 문서 · 예제

### D01 · bpmn-process-generation-skill
- Git: https://github.com/uengine-oss/bpmn-process-generation-skill
- Clone: `https://github.com/uengine-oss/bpmn-process-generation-skill.git`
- 구분: 직접 등록 / 미확인 / 브랜치 `main`
- 메인 경로: `skills/bpmn-process-generation-skill`
- 역할: 업무 요청·문서에서 프로세스 JSON과 스킬·에이전트·DMN·폼을 만드는 절차 스킬.
- 연결: CLI와 Deepagents 환경별 지침을 구분한다. 생성 산출물과 서비스 DB 등록은 별도 단계다.
- 확인 경로: `SKILL.md · references/`
- 근거: [SKILL.md](https://github.com/uengine-oss/bpmn-process-generation-skill/blob/main/SKILL.md)

### D02 · process-gpt-strategy-skill
- Git: https://github.com/uengine-oss/process-gpt-strategy-skill
- Clone: `https://github.com/uengine-oss/process-gpt-strategy-skill.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `skills/bsc-strategy-interview`
- 역할: 대화형 질문과 검토로 BSC 전략맵·비즈니스 모델 캔버스를 구성하는 스킬.
- 연결: 기존 전략 조회·수정 흐름과 연계한다. P03의 서버 코드가 아니라 실행 지침 저장소다.
- 확인 경로: `SKILL.md · references/`
- 근거: [SKILL.md](https://github.com/uengine-oss/process-gpt-strategy-skill/blob/main/SKILL.md)

### D03 · process-gpt-docs.github.io
- Git: https://github.com/uengine-oss/process-gpt-docs.github.io
- Clone: `https://github.com/uengine-oss/process-gpt-docs.github.io.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `docs/doc-site`
- 역할: ProcessGPT 문서 사이트 저장소. 메인에 문서 하위 프로젝트로 등록되어 있다.
- 연결: 제품 실행체가 아니다. 조회한 README는 제목 수준이므로 상세 문서 구성은 사이트 파일에서 확인한다.
- 확인 경로: `README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-docs.github.io/blob/main/README.md)

### D04 · process-gpt-agents.github.io
- Git: https://github.com/uengine-oss/process-gpt-agents.github.io
- Clone: `https://github.com/uengine-oss/process-gpt-agents.github.io.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/agents.github.io`
- 역할: 별도 에이전트 웹 프로젝트. 메인 서비스 목록에 등록되어 있다.
- 연결: 조회한 README는 Node/npm 개발·실행 안내 중심이다. 주 Vue 포털과 동일한 화면이라고 단정하지 않는다.
- 확인 경로: `README.md · package.json`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-agents.github.io/blob/main/README.md)

### D05 · process-gpt-sample-app-wms
- Git: https://github.com/uengine-oss/process-gpt-sample-app-wms
- Clone: `https://github.com/uengine-oss/process-gpt-sample-app-wms.git`
- 구분: 직접 등록 / public / 브랜치 `main`
- 메인 경로: `services/sample-app-wms`
- 역할: 조달·입고·품질·창고 흐름을 ProcessGPT와 연결하는 예제 앱.
- 연결: 자체 frontend/·mcp/·supabase/ 보유. install_processgpt_integration.py로 연결하며 제품 전체 ERP는 아니다.
- 확인 경로: `frontend/ · mcp/main.py · supabase/ · scripts/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-sample-app-wms/blob/main/README.md)

## 선택 구성 · 보조 라이브러리

### X01 · process-gpt-mobile
- Git: https://github.com/uengine-oss/process-gpt-mobile
- Clone: `https://github.com/uengine-oss/process-gpt-mobile.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 운영 웹 포털을 여는 모바일 앱 껍데기. 푸시·네이티브 이동·오프라인 안내를 담당한다.
- 연결: 주 화면은 Vue 포털이며 mobile-live/shell/은 앱 에셋이다. 웹 배포와 앱 재배포를 구분한다.
- 확인 경로: `capacitor.config.json · android/ · ios/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-mobile/blob/main/README.md)

### X02 · process-gpt-billing
- Git: https://github.com/uengine-oss/process-gpt-billing
- Clone: `https://github.com/uengine-oss/process-gpt-billing.git`
- 구분: 선택 구성 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 결제 생성·검증·웹훅·사용량 차감과 Supabase 저장을 담당하는 백엔드.
- 연결: Gateway의 /payments 경로와 연결한다. 결제 제공자 자격증명은 저장소 지도에 포함하지 않는다.
- 확인 경로: `app/main.py · app/api/routes/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-billing/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml)

### X03 · process-gpt-crewai-action
- Git: https://github.com/uengine-oss/process-gpt-crewai-action
- Clone: `https://github.com/uengine-oss/process-gpt-crewai-action.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: CrewAI 협업 실행체. 요청·컨텍스트를 크루로 실행해 이벤트·폼 결과를 반환한다.
- 연결: Agent SDK 및 Agent Utils 의존성 확인. 기본 하위 목록 밖의 별도 실행체이며 배포 정의도 존재한다.
- 확인 경로: `crewai_action_server.py · crewai_action_executor.py`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/README.md) · [requirements.txt](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)

### X04 · process-gpt-crewai-deep-research
- Git: https://github.com/uengine-oss/process-gpt-crewai-deep-research
- Clone: `https://github.com/uengine-oss/process-gpt-crewai-deep-research.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: CrewAI 병렬 보고서·다중 형식 생성 구성. README에 실험·데모 목적이 명시된다.
- 연결: 작업 폴링·MCP·Supabase 이벤트와 연결. 배포 파일 존재만으로 현재 기본 실행체라고 보지 않는다.
- 확인 경로: `main.py · src/parallel/`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-crewai-deep-research/blob/main/README.md)

### X05 · process-gpt-langchain-react
- Git: https://github.com/uengine-oss/process-gpt-langchain-react
- Clone: `https://github.com/uengine-oss/process-gpt-langchain-react.git`
- 구분: 선택 구성 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: MCP Python 인터프리터와 연결하는 별도 ReAct 클라이언트.
- 연결: Python·파일·환경 작업용이다. A02의 업무 보조 서비스와 이름이 유사하지만 다른 저장소다.
- 확인 경로: `mcp_react_client/main.py · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-langchain-react/blob/main/README.md)

### X06 · process-gpt-browser-use
- Git: https://github.com/uengine-oss/process-gpt-browser-use
- Clone: `https://github.com/uengine-oss/process-gpt-browser-use.git`
- 구분: 선택 구성 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 브라우저 인스턴스와 Consumer ID 기반 라우팅·VNC·API 접근을 묶는 배포 프로젝트.
- 연결: browser-use/와 gateway/를 구분한다. T08의 일반 Pod 셸 MCP와 동일 구현이 아니다.
- 확인 경로: `browser-use/ · gateway/ · README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-browser-use/blob/main/README.md)

### X07 · process-gpt-agent-utils
- Git: https://github.com/uengine-oss/process-gpt-agent-utils
- Clone: `https://github.com/uengine-oss/process-gpt-agent-utils.git`
- 구분: 연결 확인 / public / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: MCP 도구 로딩·지식 검색·사용자 확인·DMN·DB·이벤트 보조 기능 라이브러리.
- 연결: X03의 requirements.txt에 실제 의존성이 있다. Agent SDK와 역할·버전 범위를 구분한다.
- 확인 경로: `README.md · requirements.txt`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-agent-utils/blob/main/README.md) · [https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt](https://github.com/uengine-oss/process-gpt-crewai-action/blob/main/requirements.txt)

### X08 · process-gpt-llm-factory
- Git: https://github.com/uengine-oss/process-gpt-llm-factory
- Clone: `https://github.com/uengine-oss/process-gpt-llm-factory.git`
- 구분: 연결 미확인 / private / 브랜치 `main`
- 메인 직접 하위: 아님
- 역할: 다양한 LLM 제공자를 공통 생성 인터페이스로 사용하는 Python 라이브러리.
- 연결: 저장소 기능은 확인했다. 현재 어떤 실행체가 직접 소비하는지는 추가 대조가 필요하다.
- 확인 경로: `README.md`
- 근거: [README.md](https://github.com/uengine-oss/process-gpt-llm-factory/blob/main/README.md)

## 저장소 내부 경로

- **I01 / process-gpt-vue3** — [ontology/](https://github.com/uengine-oss/process-gpt-vue3/tree/main/ontology): ProcessGPT 데이터의 AGE 그래프 스키마·명세·SQL·통합 가이드.
- **I02 / process-gpt-vue3** — [supabase/migrations/](https://github.com/uengine-oss/process-gpt-vue3/tree/main/supabase/migrations): DB 변경·온톨로지 RPC. 그래프 코드와 함께 확인할 내부 구성.
- **I03 / process-gpt-completion** — [polling_service/](https://github.com/uengine-oss/process-gpt-completion/tree/main/polling_service): 별도 실행 프로세스여도 Completion 저장소 내부.
- **I04 / process-gpt-analytic** — [backend/ · frontend/](https://github.com/uengine-oss/process-gpt-analytic): 분석 기능의 서버와 자체 화면. 두 개의 Git 저장소가 아님.
- **I05 / process-gpt-bpmn-extractor** — [frontend/](https://github.com/uengine-oss/process-gpt-bpmn-extractor/tree/main/frontend): BPMN 추출 결과용 자체 UI. 주 Vue 포털과 구분.
- **I06 / process-gpt-sample-app-wms** — [frontend/ · mcp/ · supabase/](https://github.com/uengine-oss/process-gpt-sample-app-wms): WMS 예제의 화면·도구 서버·DB 정의.
- **I07 / process-gpt-vue3** — [mobile-live/shell/](https://github.com/uengine-oss/process-gpt-vue3/tree/main/mobile-live/shell): 모바일 앱에 복사되는 연결 실패 화면·앱 에셋.
- **I08 / ontology-studio** — [backend/src/modules/ontology_mcp/](https://github.com/uengine-oss/ontology-studio/blob/main/docs/ontology-mcp-server.md): 읽기 전용 검색 MCP. answer/sources 및 스키마·엔티티 조회.

## 원본 주소 또는 연결 미확정 항목

- **agent-router / agent-runtime-template** / 이미지·배포 연결만 확인 — 에이전트별 런너 라우팅의 원본 Git 주소는 미확정. C08 session-router와 동일시하지 않음. [확인 위치](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/agent-router-deployment.yaml)
- **mcp-proxy-service** / Gateway 연결만 확인 — MCP 생성·상태·요청 경로는 있으나 대응 원본 Git 저장소는 미확정. [확인 위치](https://github.com/uengine-oss/process-gpt-gateway/blob/main/src/main/resources/application.yml)
- **fcm-service** / 배포 파일 존재 — 알림 관련 배포 파일은 있으나 독립 저장소인지 내부 서비스인지 미확정. [확인 위치](https://github.com/uengine-oss/process-gpt-k8s/blob/main/deployments/fcm-service-deployment.yaml)
- **PAL / 대체 엔진 경로** / 환경별 선택 연결 — Vue 프록시의 대상·모드 확인이 필요. 별도 제품의 전체 저장소로 범위를 확장하지 않음. [확인 위치](https://github.com/uengine-oss/process-gpt-vue3/blob/main/vite.config.ts)

## 검증 경계

메인 .gitmodules의 직접 하위 23개는 모두 대응된다. 추가 의존성은 읽은 코드·설정·문서에 근거한 지도이며 모든 저장소의 모든 중첩 의존성을 전수 검증한 결과는 아니다. 설명이 짧다는 이유로 불확실한 연결을 확정하거나 관련 플랫폼을 직접 의존성으로 바꾸지 않았다.

라이브러리 최신 브랜치와 소비자가 고정한 버전, 메인의 submodule 고정 커밋은 서로 다를 수 있다. 통합 실행 검증은 하지 않았다. 이 묶음은 주소·설명 지도이지 설치 패키지나 소스 백업이 아니다.
