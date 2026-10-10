# 강사용 — 랩 정답 예와 검증 도구

학생에게 나눠 주지 않는다. 학생 배포본은 `../kit/`이다.

## 랩과 실라버스 행

| 랩 | 실라버스 행 | 학생이 만드는 것 (`work/` 기준) | 자동 확인이 보는 것 |
|---|---|---|---|
| 2-1 | 23 | `schema.json` · `apply_schema.py` | 필수 클래스 · 속성 · 관계 방향 · 중복 금지, 그래프의 고유 제약 |
| 2-2 | 24 | `load_csv.py` | 노드 · 관계가 CSV와 같음, 중복 0, 확인이 한 번 더 적재해도 수가 그대로 |
| 2-3 | 25 | `find_related.py` | 설비별 센서 · 부품, 이름 조회, LIMIT, 없는 설비 번호는 빈 결과 |
| 3-1 | 34 | `decision_table.json` · `evaluate.py` | 규칙 11개, 조치별 결과 · 적용 규칙, 같은 입력 같은 결과 |
| 3-2 | 35 | (3-1 수정) | 준비된 입력 3종, 경계값 48가지, 기준 밖 입력은 오류 |
| 3-3 | 36 | `load_effects.py` · `action_effects.py` | 조치 → 지표 관계와 방향, 추정 숫자 미저장, 긍정 · 부정 함께 반환 |
| 4-1 | 44 | `split_manual.py` · `sections.json` · `candidates.json` | 구간 · 줄 번호 보존, 인용 문장이 그 줄의 원문 |
| 4-2 | 45 | `review.json` · `register_candidates.py` | 채택한 것만 등록, 원문으로 확인되는 것 빠짐없음, 원문에 없는 연결 미등록, 출처 속성 |
| 4-3 | 46 | `lookup.py`(current) | 현재 값 = DB 최신값, 기준 넘긴 고장만, 원문 위치 |
| 4-4 | 47 | `lookup.py`(failure) | 고장별 원인 · 조치, 없는 고장 · 값 없는 센서 · 없는 설비는 근거 없음 |
| 5-1 | 57 | `agent/system_prompt.md` · `agent/agent.py` · `agent/answers/draft_q1.json` | 지침과 답의 모양(내용 품질은 보지 않음) |
| 5-2 | 58 | `agent/tools.py` · `agent/answers/q1.json` · `q2.json` | 도구 3개의 반환값, 호출 기록, 답의 근거가 도구 반환값에 있는지 |
| 5-3 | 59 | `agent/answers/q3.json`~`q5.json` | 도구가 죽지 않고 이유 반환, 답이 보류 · 부족한 정보 기재 · 지어낸 조치 없음 |
| 6-1 | 67 | `.claude/skills/meeting-notes/SKILL.md` · `meeting/memo1~2.result.json` | Skill 머리말 · 출력 칸, 결정사항 · 담당자 · 기한 |
| 6-2 | 68 | `.mcp.json` · `mcp/q_relations.json` | 실제 MCP 서버의 도구 목록, 스키마 → 질의 순서, 기록 = 그래프 = MCP 재호출 |
| 6-3 | 69 | `mcp/chain.json` | 첫 도구 결과가 둘째 도구 입력에 그대로, 판정 = 판단 MCP 재호출 |
| 6-4 | 70 | `meeting/change_spec.md` · Skill 수정 · `meeting/memo3~4.result.json` | 명세의 구성, 담당자 없는 할 일 표시, 예전 결과 유지 |
| 6-5 | 71 | `.mcp.json`의 `notion` | 연결 설정과 토큰 자리표시자만(연결 자체는 보지 않음) |
| 7-1 | 79 | `recommend.py` · `day7/proposal_base.json` · `proposal_whatif.json` | 작업 가능 시간 5가지의 순위, 순편익, 경고 표시, 제외 조치 미추천, 제어 없음 |
| 7-2 | 80 | `review.py` · `day7/review_*.json` | 추천안 5종의 판정과 지적 종류 |
| 7-3 | 81 | `hitl.py` | 질문 대기 · 상태 저장 · 잘못된 답 거절 · 재개 · 바로 완료 |

## 폴더

| 경로 | 내용 |
|---|---|
| `answers/work/` | 정답 예. 학생의 `work/`와 같은 모양 |
| `answers/.claude/` | 6-4까지 마친 Skill |
| `answers/lab6_1/` | 6-1을 마친 시점의 Skill과 결과(6-4에서 "바꾸기 전"이 된다) |
| `run_all.py` | 정답 예로 랩 21개를 순서대로 수행하고 랩마다 자동 확인을 돌린다 |
| `wrong_results.py` | 틀린 결과 55가지를 하나씩 넣어 자동 확인이 잡는지 본다 |
| `tools/build_kit_data.py` | 자료에서 계산해 만드는 키트 파일을 다시 만든다 |
| `tools/expected_answers.py` | 5일차 답 파일의 기대 출력 예를 도구 반환값으로 조립한다 |
| `tools/mcp_records.py` | 6-2 · 6-3의 MCP 호출 기록 예를 실제 MCP 호출로 만든다 |

## 검증하는 법

`kit/`에서 랩용 실행 환경을 켠 뒤(`kit/README.md`의 준비 ①~⑤) `students/labs/`에서 실행한다.

```
python instructor/run_all.py          # 21/21 통과가 나와야 한다. 연습용 그래프를 비우고 시작한다
python instructor/wrong_results.py    # 틀린 결과 55개를 모두 잡고, 되돌린 뒤 전체 통과가 나와야 한다
```

단위 시험은 레포 루트에서 `pytest tests/test_labs_kit.py tests/test_labs_checks.py`. 실행 환경이 필요한 시험(`tests/test_labs_live.py`)은 `LAB_LIVE=1`일 때만 돈다.

## 자료를 고칠 때

- CSV · 매뉴얼 · 결정표(`kit/day6/judge_mcp/decision_table.json`) · 준비된 후보를 고치면 `python instructor/tools/build_kit_data.py`로 결정표 기대값 · 준비된 그래프 · 검토용 추천안을 다시 만든다. 고치고 안 돌리면 단위 시험이 알려 준다.
- 매뉴얼의 줄이 밀리면 `kit/day4/candidates/prepared_candidates.json`과 `kit/day7/inputs/*.json`의 줄 번호도 함께 고친다.
- 결정표는 `kit/day6/judge_mcp/decision_table.json`이 정본이다. `kit/day3/decision_rules.md`(학생이 읽는 글)와 `answers/work/decision_table.json`을 같이 맞춘다.

## 알아 둘 것

- **5일차 에이전트(`answers/work/agent/agent.py`)는 실제 AI 호출로 돌려 보지 않았다.** `run_all.py`가 쓰는 답 파일은 도구의 실제 반환값으로 조립한 기대 출력 예다. 수업 전에 키를 넣고 q1~q5를 한 번 돌려 본다. 모델 이름은 `.env`의 `LAB_AGENT_MODEL`(없으면 `claude-opus-5-5`).
- **6-5 Notion 연결은 해 보지 않았다.** 설정 틀(`kit/day6/notion/notion.mcp.example.json`)의 서버 이름과 환경 변수는 수업 전에 실제 토큰으로 확인한다.
- 6-2는 학생 PC에 `uv`가 있어야 한다(공개 Neo4j MCP 서버 `mcp-neo4j-cypher@0.4.1`을 `uvx`로 실행). 처음 실행은 내려받느라 오래 걸린다.
- 자동 확인은 학생 결과의 모양과 값을 본다. Claude Code에게 어떻게 요구했는지는 보지 않는다.
- 하루치씩 나눠 주려면 `kit/dayN/`만 그날 더한다. 6일차의 `judge_mcp/`에는 3일차 결정표가 들어 있으므로 3일차 전에 주지 않는다.
