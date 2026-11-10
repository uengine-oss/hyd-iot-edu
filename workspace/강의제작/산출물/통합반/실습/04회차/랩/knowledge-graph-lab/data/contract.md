# 입출력 계약

입력과 결과 파일의 형식과 뜻만 정한다. 무엇을 어떤 종류 · 관계로 담을지, 새 대상의 ID를 어떻게 지을지는 정하지 않는다. `python run.py check`가 이 계약의 구조를 검사한다.

## 1. 입력(읽기만)

- `data/model/schema.json` · `data/model/graph.json` — 설비 모델. 형식은 schema.json 그대로다: `classes`(종류마다 뜻 · 필수 · 선택 속성) · `relations`(관계마다 시작 · 끝 종류) · `constraints`. graph.json은 `nodes`(`labels` · `props`)와 `rels`(`type` · `a` 시작 ID · `b` 끝 ID · `props`)이고, ID는 그래프 전체에서 고유하다.
- `data/conditions.csv` — 냉각 계통 조치의 조건표. 열 `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section`. 비교 하나가 한 행이고, 같은 `rule_id` · `action`의 행이 한 규칙 묶음이다. `action`은 그 규칙이 걸리는 조치(SOP ID), `input` · `operator` · `value` · `unit`은 비교, `result`는 `WARN`(경고) · `PENALTY`(감점) · `EXCLUDE`(제외), `reason`은 규칙의 이유, `source_section`은 그 규칙을 가져온 곳이다.
- `data/sop.json` — SOP 구조. `document`가 가리키는 문서(식별자 · 판 · 파일)의 조치 절차를 구조로 옮긴 것이다. sop.json 키의 뜻: `document` 원문 문서, `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차(`id` · `name` 이름 · `kind` 조치 종류(없으면 null) · `codes` 실행 코드 · `source` 출처 · `failure_mode` 고장 유형 · `model_refs` 모델 참조 · `apply_conditions` 적용 조건 · `prohibitions` 금지 조건 · `steps` 수행 단계 · `completion` 완료 기준 · `approval` 승인(`role` 역할)), `relations` 관계 목록. 항목마다 `text`는 원문 문장, `rules`는 그 조건을 옮긴 조건표의 `rule_id`다.
- `data/reviews/<문서 식별자>_<판>_review.json` — 문서에서 뽑은 후보를 원문과 대조해 결정을 적은 검토 결과. 최상위에 `doc_id` · `rev` · `doc_status` · `source_file` · `source_sha256`(읽은 파일의 SHA-256) · `encoding`(그 파일을 읽은 글자 방식) · `extractor`(후보를 만든 실행 — 코드 파일 · 요청 글 · 조각 나누기) · `generated_at`(후보를 만든 시각) · `model_run`(후보를 만든 모델 응답 기록마다 `record` · `request_hash` · `model` · `method` · `reused_from` — 응답 기록 파일은 이 폴더에 없으므로 출처 표시로만 읽는다) · `unlocated`(원문 한 곳에서 인용을 찾지 못해 후보로 두지 않은 것) · `warnings`(추출 중 판단하지 못한 것)와 `review`(검토자 · 시각 · 검토한 후보 파일과 그 SHA-256 · 이 사건의 작업 `selected_task` · 검토 전체에 적용한 결정 `decisions`)가 있다. `candidates`의 후보 하나는 `id`(파일 안에서 고유) · `section`(그 문서의 절 표기 그대로) · `procedure`(절차 안이면 절차 표기, 아니면 `null`) · `kind`(`step` 단계 · `precondition` 시작 조건과 승인 · `prohibition` 금지와 제한 · `completion` 완료 기준 · `unit_value` 숫자와 단위가 있는 기준값) · `text` · `quote`(원문 그대로) · `quote_match`(인용을 찾은 방법 — `exact` 그 줄에 글자 그대로, `normalized` 글자 · 숫자만 남겨 비교하면 그 줄에 있음) · `line_start` · `line_end`(원문 파일의 줄) · `refs`(인용이 가리키는 다른 절 · 절차) · `status`와 검토 필드 `decision`(`채택` · `수정` · `제외` · `보류`) · `status`(채택 · 수정 → `approved`, 제외 → `excluded`, 보류 → `pending`) · `reason`(결정 이유) · `origin`(`extractor` 모델 답에서 온 후보, `reviewer` 검토자가 원문 문장으로 더한 후보) · `before`(`수정`일 때 바꾸기 전 필드 값 — 인용 · 줄 · 비교 등)이다. 단계는 `order`(절차 안 번호), 스캔본은 `page`, 영문 원본과 번역이 함께 있는 문서는 `lang`이 더 있고, 기준값은 `value` · `unit` · `comparator` · `value_text`(값이 적힌 원문 조각)와 범위면 `value_max`(큰 값)가 더 있다. `missing`은 원문에 있는데 그 항목을 담은 후보가 없던 것(`note` 까닭 · `added` 검토자가 원문 문장으로 후보를 더했는지), `rule_links`는 조건표의 조건(`rule_id`)마다 근거로 본 후보 id(`candidates`) · 맞는 정도(`match`: 일치 · 불일치 · 원문 없음 · 보류) · 까닭(`note`)이다. 적재에는 `approved` 후보만 쓴다.
- `data/documents/` — 검토한 문서의 원문과 `data/documents/catalog.csv`(첫 줄은 내보내기 머리, 둘째 줄이 열 이름: 문서 식별자 · 제목 · 판 · 상태 · 시행일 · 소유 부서 · 대체 관계 · 파일 · SHA-256 · 비고 — 파일 칸이 빈 행은 목록에만 있고 받은 파일이 없는 문서).
- `app/features/my_inputs/` — 내 앞 결과를 쓸 때 위 `data/`의 파일과 같은 이름 · 같은 자리(`app/features/my_inputs/reviews/` 등)로 둔다. 있으면 제공 코드와 `python run.py check`는 그 파일을 쓴다.

## 2. 설비 모델과 조치 기준의 그래프 (`python run.py db`가 랩 DB에 올리는 것 — 공용 `app/utils/cypher.py`의 model)

설비 모델의 노드 · 관계를 그대로 올리고, SOP 구조와 조건표를 아래 이름으로 더한다. 다시 실행해도 늘지 않는다(ID로 찾고 없으면 만든다).

| 종류 | ID | 속성 |
|---|---|---|
| `FailureMode` 고장 유형 | sop.json의 `failure_modes[].id` | `name` · `source` |
| `Cause` 원인 | `causes[].id` | `name` · `source` |
| `Skill` 조치 방법(SOP 하나) | `sops[].id` | `name` · `kind` · `codes` · `source` · `apply_conditions` · `prohibitions` · `completion`(각 항목의 문장 목록) · `approval_role` · `approval_source` |
| `Step` SOP 단계 | `<SOP ID>:<단계 번호>` | `order` · `text` · `source` |
| `Rule` 조건표의 규칙 | 조건표의 `rule_id` | `effect`(`WARN` · `PENALTY` · `EXCLUDE`) · `when`(비교를 사람이 읽게 이은 글) · `penalty_manwon` |

| 관계 | 시작 → 끝 | 뜻 · 속성 |
|---|---|---|
| `HAS_STEP` | Skill → Step | SOP의 단계 |
| `MITIGATED_BY` · `REMEDIED_BY` | FailureMode → Skill | 즉시 완화 · 근본 조치(`source`) |
| `ADDRESSES` | Skill → Cause | 근본 조치가 없애는 원인(`source`) |
| `ACTS_ON` | Skill → Component | 조치가 다루는 구성 요소(sop.json `model_refs.components`) |
| `CHECKS` | Skill → Sensor | 조치의 판정 · 완료 확인에 쓰는 센서(`model_refs.sensors`) |
| `OUTPUTS` | Rule → Skill | 그 규칙이 걸리는 조치(`reason` · `source_section` — 조건표 그 행의 값) |

## 3. 결과

- `output/schema_ext.json` — 문서 근거를 담으려고 더한 종류 · 관계. 꼴은 `data/model/schema.json`과 같다(`classes` · `relations`). 기존 종류 · 관계 이름은 그 뜻 그대로 다시 쓰고, 새 이름에는 뜻을 적는다.
- `app/features/` 아래 적재 파일(`.cypher`, 또는 적재 문장을 만드는 코드와 그 출력) — 같은 파일을 다시 실행해도 노드 · 관계 수가 늘지 않는다. 전체를 지우는 문장은 쓰지 않는다.
- `output/query.cypher` — 질문마다의 쿼리(읽기만).
- `output/knowledge_export.json` — `python run.py export`가 쓴다. 꼴은 `data/model/graph.json`과 같고(`nodes` · `rels`), `remaining_questions`가 더 있다. 다음 실습에 넘길 판본이다.
- `output/remaining_questions.json` — 그래프에 넣지 않은 것 가운데 답하려면 더 알아야 하는 것. `[{"item": "…", "kind": "보류 | 원문 미확인 | 제공되지 않은 절 | 제공되지 않은 대상 | 제공되지 않은 문서 | 현재값 필요", "source": "…", "note": "…"}]`. 내보내기가 이 목록을 `remaining_questions`에 넣는다.
- `app/features/build_record.md` — 「제공 빈 틀」의 칸대로 채운다.

## 4. 정할 자리 (`app/features/` — 내가 AI와 채우는 빈 틀)

첫머리에 「제공 빈 틀」 표시가 있는 파일이다. 명령마다(`python run.py <명령>`) 그 명령이 쓰는 정할 자리까지 제공 코드(`app/utils/graph.py` · `app/utils/cypher.py`)를 돌려 3절의 결과 파일을 쓰고 랩 DB에 적재 · 조회해 `output/result.html`에 보인다. 적재 문장은 모두 MERGE · SET이라 다시 실행해도 늘지 않는다. 빈 칸이나 꼴이 틀린 칸이 있으면 그 파일 · 칸과 함께 멈춘다.

- `app/features/expected.csv` — 열 `질문,기대_답,근거`. 조회 전에 원문 · 검토 결과에서 찾은 기대 답과 근거(파일:줄).
- `app/features/graph_shape.json` — `이름`: 새 종류(`문서` · `판` · `절` · `지식`)와 새 관계(`문서의_판` · `판의_절` · `지식의_출처` · `판의_대체` · `규칙의_근거`)의 영문 이름(설비 모델 · 조치 기준이 쓰는 종류 이름은 쓰지 않는다). `뜻`: 같은 열쇠마다 뜻. `판을_따로_둠`: `true`면 판마다 노드를 두고 `false`면 절을 문서에 바로 잇는다(그때 판 · 문서의_판 · 판의_대체는 비워 둔다). `ID`: 새 대상의 ID를 짓는 꼴 — `{문서}` · `{판}` · `{절}` · `{후보}`(검토 결과의 후보 id) 자리로 쓴다. 지식 노드는 속성 `doc_id` · `rev` · `section` · `candidate`(검토 결과 파일 이름#후보 id) · 인용 · 줄 · 결정을 가진다.
- `app/features/link_rules.csv` — 열 `문서,판,절,잇는_방법,관계,대상,까닭,근거`. 검토 결과의 문서 · 판(과 절 — 비우면 그 문서 전체, 절을 적은 행이 먼저. 다만 절차 안의 후보는 그 절차 표기가 조치 ID이고 그 문서(그 절)에 `절차 표기와 같은 조치` 행이 있으면 그 행을 따른다)마다 승인 후보를 잇는 방법: `절차 표기와 같은 조치`(후보의 절차 표기가 조치 ID면 그 조치에, 단계면 그 단계에) · `정한 대상`(`대상` 칸의 기존 ID, 여럿이면 빈칸으로) · `별칭`(`app/features/aliases.csv`의 원문 이름이 인용에 들면 그 기존 ID에) · `잇지 않음`(출처 절에만). `관계`는 영문 관계 이름. 잇는 방법을 정한 문서만 적재한다.
- `app/features/aliases.csv` — 열 `원문_이름,기존_ID,근거`. 원문에 적힌 이름 · 품번 · 모델이 가리키는 기존 ID(여럿이면 빈칸으로).
- `app/features/other_doc_conditions.csv` — 열 `문서,판,절,인용에_든_글자,작업,잇는다,관계,근거`. 다른 문서가 정한 조건을 이 작업(조치 ID)에 이을지 — `잇는다`는 `예` · `아니오`(아니오도 고른 것이라 행으로 남긴다), 예면 `관계` 이름.
- `app/features/roles.csv` — 열 `종류,인용에_든_글자,항목,근거`. 조치에 잇는 지식의 관계 속성 `role` — 종류가 같고 인용에 그 글자가 든 첫 행(글자 칸이 비면 그 종류 전부). `항목`은 `준비` · `금지` · `순서` · `완료` · `승인` · `넣지 않음`(잇는지는 연결 규칙이 정하고, `넣지 않음`은 이어진 지식을 어느 항목에도 두지 않는다 — 질문 1의 항목 칸이 「넣지 않음」).
- `app/features/query_values.csv` — 열 `질문,이름,값`. 조회에 넣는 값(짝마다 무엇을 묻는지): `q1 asset` = 그 설비에 걸린 조치마다 이은 지식(질문 1) · `q3 sop` · `q3 asset` = 그 작업이 그 설비에서 확인하는 센서(질문 3) · `q4 doc` = 더한 문서의 지식이 걸리는 대상(질문 4) · `hold ids` = 그래프에 없어야 할 보류 후보(검토 결과 파일 이름#후보 id, 여럿이면 빈칸으로) · `q5_target target` = 제공되지 않은 작업 · 대상의 ID · `q5_section section` = 제공되지 않은 절 표기.
- `app/features/current_value_sources.csv` — 열 `작업,확인할_값,읽을_원천,근거`. 작업 직전에 확인할 현재값과 그 값을 읽을 원천(시스템 이름). 값 자체는 적지 않는다 — 추가 자료가 필요한 질문(`현재값 필요`)과 질문 3에 쓴다.
- `app/features/decisions.csv` — 열 `지점,고른_것,근거,바뀌는_답`. 「학생이 정할 것」의 지점과 작업 중 정한 것(그래프 모양 · 연결 규칙 등)마다 한 줄.
