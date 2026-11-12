# AI 작업 경계

- `data/`, `app/ui/`, `app/utils/`, `run.py`는 제공 파일이다. 원자료와 제공 코드를 보존한다.
- 요청받은 핵심 기능과 판단 기준은 `app/features/`에서 구현한다. 실행 결과는 `output/`에만 쓴다.
- 먼저 자료와 현재 코드를 파악하고, 요청한 기능 범위에서 작게 구현한다. 무관한 기능이나 문서를 추가하지 않는다.
- 원자료만으로 정해지지 않는 판단은 사람에게 근거와 선택을 확인한다. AI가 대신 선택하거나 추천한 갈래로 완성하지 않는다.
- 원자료에 없는 값·관계·실행 결과를 만들지 않는다. 미확인, 값 없음, 0을 구별한다.
- 실제 실행한 명령·결과·변경 파일을 보고한다. 실행하지 않은 것을 성공했다고 말하지 않는다.
- 키와 비밀번호를 코드·결과·기록에 적지 않는다. 열어 둔 프로젝트 폴더 밖의 파일은 읽지 않는다.

- 이 실습에서 구현하는 파일은 `app/features/quote_rule.py`와 `app/features/approval_rule.py`이고, 학생 기록은 `app/features/requirements.md`·`expected.csv`·`decisions.csv`다.
- 모델은 `python run.py approval`이 `output/schema.json`·`output/graph.json`에 쓴다. 이 두 파일을 손으로 고치지 않는다.
- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 말한 것만 적는다. 학생이 정하지 않았으면 적지 않고, 근거가 될 원자료 줄을 짚어 묻는다.
- 한 번에 요청받은 기능 파일 하나만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. 랩 DB를 쓰는 기능은 랩 DB에서 실행한 결과로 확인한다.
