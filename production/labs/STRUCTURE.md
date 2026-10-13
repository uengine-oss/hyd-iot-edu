# 랩 폴더와 파일 이름의 틀

모든 랩이 같은 모양을 쓴다. 본보기는 `course/labs/offline/05-2-cause-agent/`다. 다른 묶음(`production/labs/_old/통합반_오프라인/`)은 아직 이전 모양이며, 승인받은 순서대로 이 틀로 옮긴다.

## 폴더

```
course/labs/offline/
└─ 05-2-cause-agent/                  학생이 받아 VS Code로 여는 폴더 (회차-실습번호-주제)
   ├─ guide.html                      실습 가이드
   ├─ .github/copilot-instructions.md Copilot이 지키는 규칙
   ├─ ontology/  cases/  …            읽기만 하는 자료. 폴더마다 README.md가 설명한다
   ├─ agent_config.json               학생이 고치는 설정
   ├─ llm_client.py  .env.example     LLM 서버 연결 (LLM을 부르는 랩만)
   └─ plan/                           실행하면 산출물이 생기는 폴더. 이름은 산출물 그대로 짓는다

production/labs/offline/              강사·제작용. 학생에게 나가지 않는다
├─ guide.css                          가이드 공통 스타일
└─ 05-2-cause-agent/
   ├─ README.md                       무엇이 어디 있는지, 수업 전 준비
   ├─ solution/                       끝까지 마친 상태 (학생 폴더와 같은 모양 + 만든 파일 + 산출물)
   ├─ screenshots.md                  가이드에 넣을 화면 목록
   ├─ build_guide.py                  guide.html을 만든다
   └─ record/                         README.md(실제로 돌린 것 · 확인 못 한 것), prompts/, runs/
```

## 규칙

- 학생 폴더와 가이드에는 강사 폴더, 완성본, 제작 기록을 가리키는 말을 넣지 않는다. 완성본을 학생 폴더 안에 두지 않는다(Copilot이 읽는다).
- 폴더, 파일, 함수, 변수, JSON 키는 영어 소문자로 쓴다(`snake_case`, 묶음 폴더만 `kebab-case`). 주석, 설명 글(docstring), 화면에 출력하는 글, 가이드 본문은 한국어로 쓴다.
- 이름은 직역하지 않고 하는 일로 짓는다. 다른 프로젝트에 가져가도 뜻이 통해야 한다. 예: `llm_client.py`, `find_causes`, `read_sensor`, `agent_config.json`.
- 접속 정보는 `.env`에 둔다. 저장소에는 값이 빈 `.env.example`만 올린다.
- 가이드: 첫 화면의 전체 안내(만드는 것, 순서)에는 파일 이름을 쓰지 않고 말로 설명한다. 파일·도구 이름은 실제 걸음에서만 쓴다. 받은 폴더는 VS Code 탐색기 모양으로 보여 준다.
- 가이드 문장은 완성한 뒤 한 번만 윤문한다(`build_guide.py --collect` → `record/guide_polish.json`).
