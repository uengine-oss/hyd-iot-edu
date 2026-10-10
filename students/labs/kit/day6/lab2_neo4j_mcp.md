# 6-2 · 관계를 찾는 도구를 MCP로 연결해 호출하기

## 만들 것

연습용 그래프를 Claude Code에 MCP로 연결하는 설정 `.mcp.json`, 그리고 Claude Code가 MCP 도구로 설비 질문에 답한 과정을 적은 기록 `work/mcp/q_relations.json`.

## 왜 만드나

5일차의 조회 도구는 내가 만든 에이전트 프로그램 안에서만 쓸 수 있었습니다. MCP로 연결하면 같은 그래프를 Claude Code를 비롯한 다른 프로그램도 같은 방식으로 불러 쓸 수 있습니다. 이번에는 미리 만든 조회 함수가 없습니다. 에이전트가 먼저 스키마를 읽어 무엇이 있는지 알아낸 다음, 필요한 관계를 찾는 질의를 스스로 만듭니다.

## 주어지는 자료

- `day6/mcp/lab.mcp.json` — 준비된 연결 설정. 서버 두 개가 들어 있다
  - `lab-neo4j`: 공개된 Neo4j MCP 서버. 도구는 `get_neo4j_schema`(스키마 읽기)와 `read_neo4j_cypher`(조회 질의 실행). 조회 전용으로 연결한다
  - `lab-judge`: 판단 MCP(다음 랩에서 쓴다)
- 연습용 그래프. 2~4일차 랩을 마치지 못했다면 `python -m labkit.prepared_graph`로 준비된 그래프를 넣는다
- `uv`가 깔려 있어야 한다(Neo4j MCP 서버를 `uvx`로 실행한다)

## Claude Code에 전달할 요구사항의 뼈대

**첫째, 연결합니다.** 설정 파일을 이 폴더에 `.mcp.json`으로 복사합니다. 비밀번호는 파일에 적혀 있지 않고 `${LAB_NEO4J_PASSWORD}`처럼 이름만 있습니다. 값은 `.env`에서 터미널로 읽어 들인 뒤 Claude Code를 실행해야 채워집니다.

```
cp day6/mcp/lab.mcp.json .mcp.json
set -a; source .env; set +a
claude
```

Claude Code가 새 MCP 서버를 쓸지 물으면 허용합니다. `/mcp`를 입력해 `lab-neo4j`가 연결됐는지 봅니다.

**둘째, 묻습니다.**

- **목표**: MCP 도구만으로 "CL-01에는 어떤 부품이 있고, 과열의 원인으로 등록된 것은 무엇인가?"에 답한다.
- **꼭 지킬 것**
  - 먼저 `get_neo4j_schema`로 스키마를 읽고, 그다음 `read_neo4j_cypher`로 질의한다.
  - 답에는 만든 Cypher와 반환된 줄을 그대로 보여 준다.
- **기록**(`work/mcp/q_relations.json`): 부른 도구를 순서대로, 입력과 반환값을 고치지 않고 적게 한다.

```json
{"question": "…", "calls": [
  {"tool": "get_neo4j_schema", "input": {}, "output": {}},
  {"tool": "read_neo4j_cypher", "input": {"query": "MATCH …"}, "output": [{"…": "…"}]}
]}
```

- **완료 기준**: 반환값에 CL-01의 부품 네 개와 과열의 원인이 모두 들어 있다.

콘솔에서 두 도구 호출을 찾아, 스키마를 읽은 결과가 다음 질의에 어떻게 쓰였는지 봅니다. 그리고 기록의 Cypher를 Neo4j Browser(`http://127.0.0.1:17474`)에 붙여 넣어 같은 줄이 나오는지 대조합니다.

**여기서 에러가 나면** — `lab-neo4j`가 `failed`로 나오면 `set -a; source .env; set +a`를 하지 않고 `claude`를 실행한 경우가 많습니다. Claude Code를 끝내고 세 줄을 다시 칩니다.

## 무엇이 나오면 성공

```
python -m labcheck 6-2
```

- `.mcp.json`에 `lab-neo4j`가 있고 비밀번호를 파일에 직접 적지 않았다
- 서버에 스키마 읽기 · 조회 도구가 있고 쓰기 도구는 없다
- 스키마를 먼저 읽고 그다음 질의했다
- 기록된 반환값이 같은 질의를 그래프에 직접 돌린 결과, MCP로 다시 부른 결과와 같다
- 반환값에 CL-01의 부품과 과열의 원인이 모두 있다

## 다음 랩에서 어떻게 쓰이나

다음 랩에서 이 조회 도구가 찾은 조치 후보를 두 번째 MCP 도구(판단)에 넘깁니다. 첫 도구의 결과가 둘째 도구의 입력이 됩니다.
