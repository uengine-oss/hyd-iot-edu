# 7. Neo4j MCP: 스키마를 받고 질의를 만든다 (2부, 180분: 설명 60 / 실습 90 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
사람 대신 코딩 에이전트(Claude Code 또는 Codex)가 그래프를 걷게 한다. 그래프 서버(MCP)를 CLI에 붙이고, 에이전트가 스키마를 먼저 읽은 뒤 Cypher를 만들어 실행하는 두 단계를 본다.
끝나면 에이전트가 실제로 호출한 도구 2개(`get_neo4j_schema` → `read_neo4j_cypher`)와 만들어진 Cypher, 그 결과 노드·관계가 남는다.

## 준비
- Neo4j 켜짐. 호스트에 `uvx`(uv 0.12.5)와 로그인된 `claude` CLI(제작자 PC 2026-10-07 `claude --version` 2.1.292; Codex 0.151.0은 선택).
- 서버 설정 원본: `it/supabase/seed.sql` 57~63행(`tenants.mcp`). 워커가 이 설정을 작업 폴더의 `.mcp.json`으로 쓰는 코드: `it/agent-worker/worker/bridge.py`(`install`, 108행; Codex는 `codex-mcp.toml`).
- 비교용 정답 질의: `it/neo4j/v2/queries.cypher`, 에이전트용 스키마 설명: `it/neo4j/v2/schema_prompt.md`.

## 실행 장면
1. [파일] 빈 폴더(예 `~/hyd-mcp-lab`)에 `.mcp.json`을 만든다. 내용은 `seed.sql`의 `neo4j` 항목을 호스트용으로 바꾼 것:
   `{"mcpServers":{"neo4j":{"command":"uvx","args":["--with","fastmcp==2.13.0.2","mcp-neo4j-cypher@0.4.1","--transport","stdio"],"env":{"NEO4J_URI":"bolt://127.0.0.1:7687","NEO4J_USERNAME":"neo4j","NEO4J_PASSWORD":"hydpass123","NEO4J_READ_ONLY":"true"}}}}`
   → [확인] 파일 저장. (Claude Code는 프로젝트 폴더의 `.mcp.json`을 읽는다 — `bridge.py` 5행 주석.)
2. [명령] 그 폴더에서 `claude` 실행 → 처음 뜨는 MCP 서버 승인에 동의 → `/mcp` → [관찰] `neo4j` 서버와 도구 `get_neo4j_schema`, `read_neo4j_cypher` → [확인] 도구 2개가 보인다.
3. [입력] "HYD-01 펌프 누설의 원인 후보와 조치 방법은? 먼저 스키마를 읽고 Cypher로 답해." → [관찰] 에이전트가 `get_neo4j_schema`를 먼저 부르고, 그 다음 `read_neo4j_cypher`에 Cypher를 넣어 실행한다 → [확인] 호출 순서와 생성된 Cypher를 복사해 둔다.
4. [비교] 생성된 Cypher를 `queries.cypher`의 `q2-diagnosis-path`(`:param symptom => 'sym:ps1-drop'`)와 Neo4j Browser에서 나란히 실행 → [확인] 원인 후보·조치 방법(SOP-PMP-01 예비 펌프 전환 등)이 겹치는지, 다르면 무엇이 빠졌는지.
5. [입력] 같은 질문을 Codex로(선택): 워커가 만드는 `codex-mcp.toml` 모양은 `bridge.py` 123행 근처 참고. → [확인] 같은 두 도구가 호출되는지.
6. [정리] 서버가 에이전트에 어떤 권한만 주는지: `compose.yaml` 478행 agent-worker의 `ALLOWED_TOOLS`(`mcp__neo4j__get_neo4j_schema,mcp__neo4j__read_neo4j_cypher,…`)와 `NEO4J_READ_ONLY=true` → [확인] 쓰기 Cypher(`CREATE …`)를 시키면 서버가 `Only MATCH queries are allowed for read-query`로 거절하고, `write_neo4j_cypher` 도구 자체가 목록에 없다.

## 막혔을 때
- `uvx`가 없다: uv 설치(`pip install uv` 또는 공식 설치) 뒤 다시. Windows Smart App Control이 uv 파이썬을 막으면(HANDOFF A105) 서버가 못 뜬다 — 그때는 컨테이너 워커 경로로 바꾸거나 강사 시연으로 대체.
- 도구가 안 보인다: `.mcp.json` JSON 문법, 폴더 위치(현재 디렉터리) 확인.
- 에이전트가 스키마를 안 읽고 바로 질의한다: 지시문에 "먼저 get_neo4j_schema"를 명시한다. 워커의 상시 지시문은 `it/agent-worker/worker/workspace.py`.

## 증거
- `.evidence/sessions/07/`(2026-10-07 제작자, `run.py`·`commands.md`): 1단계 `.mcp.json`을 실제로 만들고(`01_mcp_json.json`), 그 설정 그대로 `uvx … mcp-neo4j-cypher@0.4.1 --transport stdio` 서버를 띄워 파이썬 MCP 클라이언트(`mcp_client_probe.py`, `uv run --with fastmcp==2.13.0.2`)로 호출 — 도구 목록 `get_neo4j_schema`·`read_neo4j_cypher` 2개, 스키마 읽기, `sym:ps1-drop` 질의 성공, `CREATE` 거절·쓰기 도구 없음(`03_mcp_server_probe.json`) — **검증됨**. 4단계 정답 질의(`sym:ps1-drop` 4행, SOP-PMP-01~04)·6단계 권한 줄 — **검증됨**. **2·3·5단계(학생이 `claude`/`codex` CLI를 띄워 질문하고 호출 순서를 보는 것)는 돌리지 않았다 — 미검증.**
- 제작자 증거: 호스트 워커(Claude Code)가 Neo4j MCP로 규칙 질의를 실제 수행한 이벤트 스트림 `.evidence/reaudit/a086-rules-2/*.events.jsonl`(`probe_rule_questions.py`), Codex 단독 MCP 연결 `.evidence/reaudit/codex-probe/`·`codex-tool-scope-*`(`probe_codex_worker.py`, `probe_codex_tool_scope.py`). 학생 완주 증거 아님.
