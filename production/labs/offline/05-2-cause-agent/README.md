# 05-2-cause-agent — 설비 이상의 원인을 추론하는 에이전트 (강사용)

통합반 오프라인 5회차 실습 2. 학생에게 나가는 폴더는 `course/labs/offline/05-2-cause-agent/` 하나다. 이 폴더(`production/labs/offline/`)의 것은 학생에게 나가지 않는다.

## 무엇이 어디에 있나

| 경로 | 내용 |
|---|---|
| `course/labs/offline/05-2-cause-agent/` | 학생이 받아 VS Code로 여는 폴더. `guide.html`이 실습 가이드다 |
| `solution/` | 끝까지 마친 상태. `tools.py`, `agent.py`, 사례 열한 건의 `plan/` 포함 |
| `screenshots.md` | 가이드의 「화면 1~10」 자리에 넣을 사진 목록 |
| `record/README.md` | 실제로 돌린 것과 확인하지 못한 것 |
| `record/prompts/` | 가이드에 실은 요청 글 원문 |
| `record/runs/` | 단계별 실행 결과와 그때의 설정 |
| `build_guide.py` | `guide.html`을 만든다. 스타일은 `../guide.css` |

## 수업 전에 준비할 것

- 학생마다 LLM 서버 접속 정보 세 값(`OPENAI_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`)을 나눠 준다. 학생은 `.env.example`을 복사해 `.env`로 만들고 값을 적는다.
- 학생 PC에서 서버에 닿는지 확인한다: 학생 폴더에서 `python llm_client.py`.
- Python 3(표준 라이브러리만 쓴다), VS Code, GitHub Copilot 채팅.

## 완성본을 돌려 보려면

`solution/`에서 `.env.example`을 `.env`로 복사해 접속 정보를 적고 `python agent.py`를 실행한다. 열한 건에 1분쯤 걸린다. `.env`는 저장소에 올리지 않는다.
