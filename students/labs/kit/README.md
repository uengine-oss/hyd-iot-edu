# 소형 냉각장치 랩 키트

2일차부터 7일차까지의 랩에서 쓰는 자료입니다. 랩은 모두 **소형 냉각장치**라는 작은 연습용 설비 하나로 이어집니다(6일차의 문서 랩만 회의 메모를 씁니다). 설비 소개는 `cooler/cooler.md`에 있습니다.

랩에서는 코드를 직접 치지 않습니다. VS Code 터미널에서 Claude Code에게 **무엇을 만들지, 어떤 자료로, 무엇을 지켜서, 무엇이 나오면 끝인지**를 말로 전하고, 만들어진 결과가 요구대로인지 확인합니다.

## 처음 한 번 준비합니다

**① 이 폴더(`kit`)를 VS Code로 열고 터미널을 엽니다.** 아래 명령은 모두 이 폴더에서 칩니다.

**② 내 설정 파일을 만듭니다.**

```
cp .env.example .env
```

`.env`를 열어 `LAB_NEO4J_PASSWORD`와 `LAB_DB_PASSWORD` 두 줄에 내가 정한 비밀번호(영문·숫자 8자 이상)를 적습니다. 나머지 줄은 그대로 둡니다. AI 키와 Notion 토큰 줄은 5일차 · 6일차에 강사가 알려 줄 때 채웁니다.

**③ 필요한 파이썬 패키지를 깝니다.**

```
python -m pip install -r requirements.txt
```

**④ 연습용 실행 환경을 켭니다.**

```
docker compose up -d --wait
```

연습용 지식 그래프, 연습용 DB, 판단 MCP 세 가지가 켜집니다. 수업에서 보는 유압설비 공장과는 이름도 포트도 다른 별개의 환경이라 서로 영향을 주지 않습니다.

**⑤ 켜졌는지 확인합니다.**

```
docker compose ps
```

세 줄 모두 `healthy`면 준비가 끝났습니다. 크롬에서 `http://127.0.0.1:17474`를 열면 연습용 그래프 화면(Neo4j Browser)이 뜹니다. 사용자 이름은 `neo4j`, 비밀번호는 ②에서 정한 `LAB_NEO4J_PASSWORD`입니다.

**여기서 에러가 나면** — `LAB_NEO4J_PASSWORD 를 정해 주세요`라고 나오면 ②를 건너뛴 것입니다. `port is already allocated`라고 나오면 같은 키트가 이미 켜져 있는 것이니 `docker compose ps`로 확인합니다.

## 랩을 하는 순서

1. 그날의 랩 안내(`dayN/labM_*.md`)를 읽습니다. 한 쪽입니다.
2. 터미널에서 `claude`를 실행하고, 안내의 「요구사항의 뼈대」를 내 말로 풀어 전합니다.
3. Claude Code가 만든 파일은 `work/` 폴더에 모읍니다. 파일 이름은 안내에 적힌 대로 합니다.
4. 자동 확인을 돌립니다. 랩 번호는 "날-순서"입니다(2일차 첫째 랩은 `2-1`).

```
python -m labcheck 2-1
```

`[통과]`와 `[미통과]`가 기준마다 한 줄씩 나옵니다. `[미통과]` 아래의 화살표 줄이 무엇이 어긋났는지 알려 줍니다. 그 내용을 Claude Code에게 전해 고치게 하고 다시 확인합니다.

## 랩 목록

| 날 | 번호 | 랩 | 안내 |
|---|---|---|---|
| 2일차 | 2-1 | 연습용 설비의 클래스·관계 스키마 만들기 | `day2/lab1_schema.md` |
| | 2-2 | 설비·부품·센서 자료를 그래프에 등록하기 | `day2/lab2_load.md` |
| | 2-3 | 설비 이름으로 센서와 부품 찾기 | `day2/lab3_find.md` |
| 3일차 | 3-1 | 조치를 허용·경고·제외하는 결정표 만들기 | `day3/lab1_decision_table.md` |
| | 3-2 | 조건을 바꿔 규칙 결과가 달라지는지 확인하기 | `day3/lab2_boundaries.md` |
| | 3-3 | 조치가 지표에 미치는 영향 관계 만들기 | `day3/lab3_effects.md` |
| 4일차 | 4-1 | 짧은 매뉴얼에서 고장·원인·조치 후보 추출하기 | `day4/lab1_extract.md` |
| | 4-2 | 원문과 비교한 후보만 그래프에 등록하기 | `day4/lab2_review.md` |
| | 4-3 | 현재 설비 값과 문서의 조치 지식을 함께 조회하기 | `day4/lab3_lookup.md` |
| | 4-4 | 질문을 바꿔 답변 근거가 유지되는지 확인하기 | `day4/lab4_questions.md` |
| 5일차 | 5-1 | 작은 에이전트의 역할·입력·출력 정의하기 | `day5/lab1_agent_role.md` |
| | 5-2 | 조회 도구를 연결해 근거로 답하는 에이전트 만들기 | `day5/lab2_tools.md` |
| | 5-3 | 근거가 부족한 질문은 보류하게 만들기 | `day5/lab3_hold.md` |
| 6일차 | 6-1 | 회의 메모를 정리하는 Skill 만들기 | `day6/lab1_skill.md` |
| | 6-2 | 관계를 찾는 도구를 MCP로 연결해 호출하기 | `day6/lab2_neo4j_mcp.md` |
| | 6-3 | 지식 조회와 조치 판단을 두 MCP 도구로 잇기 | `day6/lab3_two_mcp.md` |
| | 6-4 | Skill에 새 요구를 넣고 예전 결과도 유지하기 | `day6/lab4_skill_change.md` |
| | 6-5 | Notion 자료로 짧은 퀴즈·Q&A 실행하기 | `day6/lab5_notion.md` |
| 7일차 | 7-1 | 조치별 예상 효과와 근거를 정리해 추천하기 | `day7/lab1_recommend.md` |
| | 7-2 | 검토 에이전트가 근거와 조건을 확인하게 만들기 | `day7/lab2_review.md` |
| | 7-3 | 필요한 운전 조건을 사람에게 묻고 판단 이어 가기 | `day7/lab3_ask_human.md` |

## 미리 준비돼 있는 것

| 폴더 | 무엇 |
|---|---|
| `cooler/` | 설비 소개와 스키마 설명 |
| `dayN/` | 그날의 랩 안내와 자료 |
| `labkit/` | 연결을 대신해 주는 공용 도구. `labkit.settings`(.env 읽기) · `labkit.graph`(그래프 연결) · `labkit.db`(DB 연결). Claude Code에게 "연결은 labkit을 쓰라"고 하면 됩니다 |
| `labcheck/` | 자동 확인 |
| `work/` | 내 결과가 쌓이는 곳 |

프로그램은 `python work/이름.py`처럼 이 폴더에서 실행합니다. `ModuleNotFoundError: No module named 'labkit'`이 나오면 준비 ③을 다시 합니다.

## 끄기, 처음부터 다시 하기

- 수업이 끝나면 끕니다. 넣어 둔 연습 자료는 남습니다.

```
docker compose down
```

- 그래프를 비우고 2일차부터 다시 하고 싶을 때만 씁니다. 연습용 그래프의 자료가 모두 지워집니다.

```
python -m labkit.reset_graph --yes
```

- 앞의 랩을 못 끝냈는데 6일차 MCP 랩을 해야 하면, 준비된 그래프를 넣습니다. 2~4일차를 마친 상태와 같은 그래프가 됩니다.

```
python -m labkit.prepared_graph
```
