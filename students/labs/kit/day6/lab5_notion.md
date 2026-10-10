# 6-5 · Notion 자료로 짧은 퀴즈·Q&A 실행하기

## 만들 것

Notion을 Claude Code에 MCP로 연결하는 설정(`.mcp.json`에 `notion` 서버 추가). 그리고 내 Notion 페이지를 읽어 문제 하나를 내거나 질문에 답하게 해 봅니다.

## 왜 만드나

앞의 두 랩에서 그래프와 판단 도구를 MCP로 연결했습니다. 같은 연결 방식이 설비 지식뿐 아니라 내 학습 노트 같은 개인 자료에도 그대로 통한다는 것을 한 번 겪어 봅니다. 학습 서비스를 만드는 랩이 아닙니다. 연결하고, 한 번 묻고, 답이 자료에 근거하는지 확인하면 끝입니다.

## 주어지는 자료

- `day6/notion/notion.mcp.example.json` — Notion MCP 서버 설정 틀. 토큰 자리는 `${NOTION_TOKEN}`
- `day6/notion/example_page.md` — 읽을 페이지가 없을 때 Notion에 붙여 넣을 예제 내용
- 강사가 알려 주는 Notion 토큰(`.env`의 `NOTION_TOKEN`에 넣는다)
- Node.js가 깔려 있어야 한다(Notion MCP 서버를 `npx`로 실행한다)

## Claude Code에 전달할 요구사항의 뼈대

**첫째, 연결합니다.**

1. `.env`의 `NOTION_TOKEN` 줄에 강사가 알려 준 값을 넣는다. 설정 파일에는 값을 적지 않는다.
2. `day6/notion/notion.mcp.example.json`의 `notion` 부분을 내 `.mcp.json`의 `mcpServers` 안에 더한다(Claude Code에게 "이 서버를 .mcp.json에 더해 줘"라고 해도 된다).
3. 읽을 페이지를 Notion에서 그 연결에 공유한다. 1일차에 만든 학습 노트가 있으면 그것을, 없으면 예제 내용으로 새 페이지를 만든다.
4. Claude Code를 다시 실행한다.

```
set -a; source .env; set +a
claude
```

**둘째, 묻습니다.**

- **목표**: 내 Notion 페이지의 내용만으로 문제 하나를 내거나 질문 하나에 답한다.
- **꼭 지킬 것**
  - 페이지에 없는 내용은 답하지 않는다. 없으면 없다고 한다.
  - 답과 함께 근거가 된 페이지의 문장을 그대로 보여 준다.
- **완료 기준**: 답의 근거 문장을 Notion 페이지에서 내가 직접 찾을 수 있다.

콘솔에서 Notion 도구 호출을 찾아, 어떤 페이지를 읽었는지 확인합니다. 페이지에 없는 것(예: "오늘 점심 메뉴는?")도 하나 물어봅니다.

## 무엇이 나오면 성공

```
python -m labcheck 6-5
```

- `.mcp.json`에 `notion` 서버가 있고 실행 명령이 적혀 있다
- 토큰을 파일에 직접 적지 않고 `${NOTION_TOKEN}`으로 연결했다

자동 확인은 **연결 설정**만 봅니다. 답이 페이지에 근거하는지는 근거 문장을 Notion에서 직접 찾아 확인합니다.

## 다음 랩에서 어떻게 쓰이나

마지막 날 종합 랩에서 같은 연결로 수업 내용을 Notion 노트에 기록합니다.
