# 입출력 계약

입력과 결과 파일의 형식과 뜻만 정한다. 어떤 문장을 어떤 후보로 만들지, 문서를 어떤 단위로 나눌지는 정하지 않는다. 다음 실습은 같은 모양의 검토 결과를 입력으로 읽는다. `python run.py check`가 이 계약의 구조와 인용을 검사한다.

## 1. 입력(읽기만)

- `data/conditions.csv` — 조건표. 열 `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section`. 비교 하나가 한 행이고, 같은 `rule_id` · `action`의 행이 한 규칙 묶음이다. `action`은 그 규칙이 걸리는 조치(SOP ID), `input` · `operator` · `value` · `unit`은 비교, `result`는 `WARN`(경고) · `PENALTY`(감점) · `EXCLUDE`(제외), `reason`은 규칙의 이유, `source_section`은 그 규칙을 가져온 곳이다.
- `data/sop.json` — SOP 구조. `document`가 가리키는 문서(식별자 · 판 · 파일)의 조치 절차를 구조로 옮긴 것이다. sop.json 키의 뜻: `document` 원문 문서, `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차(`id` · `name` 이름 · `kind` 조치 종류(없으면 null) · `codes` 실행 코드 · `source` 출처 · `failure_mode` 고장 유형 · `model_refs` 모델 참조 · `apply_conditions` 적용 조건 · `prohibitions` 금지 조건 · `steps` 수행 단계 · `completion` 완료 기준 · `approval` 승인(`role` 역할)), `relations` 관계 목록. 항목마다 `text`는 원문 문장, `rules`는 그 조건을 옮긴 조건표의 `rule_id`다.
- `data/action_review.json` — 조건표로 경보마다 조치 후보를 판정 · 비교한 조치 검토 결과. `events`의 경보마다 `id` · `asset` 설비 · `decision_time` 판정을 요청한 시각(UTC) · `candidates` 후보(`sop` · `status` 유지 · 제외 · 보류 · `inputs` 판단 입력 · `reasons` 이유 — 맞은 규칙의 `rule_id` · `result` · `actual_inputs` 실제 입력 · `comparison` 비교값 · `rank` 순위 · `approval` 승인) · `review` 검토 의견(`top` 승인 요청을 검토할 후보 · `reason` · `checks`).
- `data/documents/catalog.csv` — 첫 줄은 내보내기 머리, 둘째 줄이 열 이름이다. 열: 문서 식별자 · 제목 · 판 · 상태 · 시행일 · 소유 부서 · 대체 관계 · 파일 · SHA-256 · 비고. 파일 칸이 빈 행은 목록에만 있고 받은 파일이 없는 문서다.
- `app/features/my_inputs/` — 내 앞 결과를 쓸 때 위 `data/`의 파일과 같은 이름으로 둔다. 있으면 `python run.py check`는 그 파일을 기준으로 본다.

## 2. 응답 기록 (`output/model_responses/<요청 해시>.json` — `app/utils/llm_client.py`가 쓴다)

- 키: `request_hash` 요청 해시, `model` `.env`의 모델 이름, `response_model` 응답의 model, `system_fingerprint`, `finish_reason` 답이 끝난 까닭, `method` 보낸 방법(`모델 서버` · `채팅으로 받음`), `attempt` 같은 요청을 보낸 차례, `received_at` 받은 시각, `folder_mark` 이 폴더의 표지(`output/.folder_mark`), `request` 보낸 요청, `response_text` 받은 답 글, `usable` 답에 쓸 내용이 있는지(빈 답 · 서버가 걸러 낸 답 · 거절이면 `false`), `note` `usable`이 `false`인 까닭, `response_raw` 받은 응답 원문, `usage` 토큰 수.
- 응답 기록은 고치지 않는다. `folder_mark`가 이 폴더의 `output/.folder_mark`와 다른 기록(다른 폴더에서 옮겨 온 기록)은 이 폴더에서 받은 답이 아니므로 `app/utils/llm_client.py`가 다시 쓰지 않고, 그 기록으로 만든 후보는 계약 오류다. `usable`이 `false`인 기록으로는 후보를 만들지 않는다.

## 3. 후보 파일 (`output/candidates/<문서 식별자>_<판>.json` — 판이 빈 문서는 식별자만)

```json
{
  "doc_id": "문서 목록의 문서 식별자",
  "rev": "문서 목록의 판",
  "doc_status": "문서 목록의 상태",
  "source_file": "data/documents/ 안의 파일 이름",
  "source_sha256": "실제로 읽은 파일의 SHA-256",
  "encoding": "그 파일을 읽은 글자 방식(Python이 쓰는 이름)",
  "extractor": "이 결과를 만든 실행(코드 파일과 옵션)",
  "generated_at": "실행 시각(ISO 8601)",
  "model_run": [ {"record": "output/model_responses/….json", "request_hash": "…", "model": "…", "method": "…", "reused_from": null} ],
  "candidates": [ { 후보 }, ... ],
  "unlocated": [ { 후보와 같은 모양, "note": "인용을 찾지 못한 까닭" } ],
  "warnings": ["추출 중 판단하지 못한 것"]
}
```

- `model_run`은 이 후보를 만든 응답 기록마다 한 항목이다. `request_hash` · `model` · `method`는 그 기록의 값이고, `reused_from`은 `null`이다(다른 폴더의 응답 기록으로는 후보를 만들지 않는다).
- 후보는 `model_run`이 가리키는 응답 기록의 답에서 만든다 — 후보의 `quote`는 그 기록들의 답 글(`response_text`)에 있는 글이다.
- 원문 어디에서도 인용을 찾지 못한 것은 후보(`candidates`)로 쓰지 않고 `unlocated`에 둔다.

## 4. 후보 하나

| 필드 | 필수 | 뜻 |
|---|---|---|
| `id` | 예 | 파일 안에서 고유한 문자열 |
| `section` | 예 | 그 내용이 있는 절 — 그 문서의 절 표기 그대로(문서마다 다르다: `HM-8.2` · `PM-2.2` · `5` · `제1조` · `HM-9.1`). 첫 절 앞의 글은 `머리말` |
| `procedure` | 예 | 그 내용이 절차 안이면 절차 표기(`SOP-FAN-12` 등), 절차 밖이면 `null` |
| `kind` | 예 | `step` · `precondition` · `prohibition` · `completion` · `unit_value` 중 하나 |
| `text` | 예 | 후보의 내용을 사람이 읽을 수 있게 적은 것 |
| `quote` | 예 | 근거가 되는 원문 문자열. 원문 글자를 고치거나 옮겨 쓰지 않은 연속 문자열이다 |
| `quote_match` | 예 | 인용을 찾은 방법 — `exact`(그 줄에 글자 그대로 있음) · `normalized`(글자 · 숫자만 남겨 소문자로 비교하면 그 줄에 있음). 코드가 찾은 인용이 원문 여러 곳에 맞으면 찾지 못한 것으로 본다 — 같은 문장 가운데 어느 줄인지는 검토자가 골라 더한다(5절 `missing`) |
| `line_start` · `line_end` | 예 | 인용이 있는 원문 파일의 줄 번호(1부터, `encoding`으로 읽은 줄) |
| `page` | 문서 목록 상태가 참고(스캔본)이면 예 | 인용이 있는 쪽 — 그 쪽 꼬리의 쪽 번호 표기 그대로 |
| `lang` | 영문 원본과 번역이 함께 있는 문서면 예 | 인용한 줄의 말 — `en` · `ko` |
| `refs` | 예 | `quote`가 가리키는 다른 절 · 절차의 표기 목록(원문의 표기). 없으면 `[]` |
| `status` | 예 | 추출 직후에는 `pending` |
| `order` | `step`이면 예 | 절차 안 번호(1부터) |
| `value` | `unit_value`이면 예 | 숫자. 범위면 작은 값 |
| `value_max` | 범위이면 예 | 범위의 큰 값 |
| `unit` | `unit_value`이면 예 | 원문에 적힌 단위 |
| `comparator` | `unit_value`이면 예 | `>=` `>` `<=` `<` `=` `range` `±` 중 하나, 원문에 비교 표현이 없으면 `null` |
| `value_text` | `unit_value`이면 예 | 값 · 단위 · 비교 표현이 적힌 원문 조각 그대로. `quote` 안에 있어야 한다 |

종류의 뜻:

- `step`: 절차의 번호 단계.
- `precondition`: 작업을 하기 전에 충족 · 확인해야 하는 조건과 승인.
- `prohibition`: 금지와 제한.
- `completion`: 끝났다고 보는 기준과 끝나지 않았을 때의 처리.
- `unit_value`: 숫자와 단위가 있는 기준값.

## 5. 검토 결과 파일 (`output/reviews/<문서 식별자>_<판>_review.json`)

후보 파일을 복사해 아래를 더한 별도 파일이다. 후보 파일 원본은 그대로 둔다.

```json
{
  ...후보 파일의 최상위 필드...,
  "review": {"reviewer": "검토자", "reviewed_at": "시각", "candidates_file": "output/candidates/….json", "candidates_sha256": "검토를 시작할 때 후보 파일의 SHA-256",
             "selected_task": "이 사건의 작업 SOP ID(작업을 정한 검토) 또는 null", "decisions": ["검토 전체에 적용한 결정과 근거"]},
  "candidates": [ {후보 필드 + 아래 검토 필드} ],
  "missing": [ {"section": "…", "procedure": null, "kind": "…", "quote": "원문 그대로", "line_start": 1, "line_end": 1, "note": "왜 빠졌는지", "added": false} ],
  "rule_links": [ {"rule_id": "…", "candidates": ["후보 id"], "match": "일치 | 불일치 | 원문 없음 | 보류", "note": "까닭"} ]
}
```

| 검토 필드 | 뜻 |
|---|---|
| `decision` | `채택` · `수정` · `제외` · `보류` |
| `status` | 채택 · 수정 → `approved`, 제외 → `excluded`, 보류 → `pending` |
| `reason` | 원문 근거를 든 결정 이유 |
| `before` | `수정`일 때 바꾸기 전 필드 값 |
| `origin` | 모델 답에서 온 후보는 `extractor`, 검토자가 원문 문장으로 더한 후보는 `reviewer` |

- `missing`은 원문에 있는데 후보가 없는 것이다. 검토자가 근거 문장으로 후보를 더했으면 `added: true`로 두고 그 후보의 `origin`을 `reviewer`로 둔다. 원문 여러 곳에 같은 문장이 있어 `unlocated`로 간 인용은 검토자가 그 절차의 줄을 골라 이렇게 더하고, `note`에 그 줄을 고른 까닭을 적는다.
- 검토의 결정은 후보의 절 · 종류 · 인용으로도 알아볼 수 있게 `reason`에 적는다 — 후보 파일을 다시 만들면 `candidates_sha256`이 바뀌어 검토 결과를 새 후보 파일로 다시 만들어야 하기 때문이다.
- `rule_links`는 조건표의 조건(이 작업 `SOP-COOL-14`에 걸린 조건 — `action`이 이 작업인 행)과 이 문서 후보의 근거 대조다. `rule_id`는 기준 조건표의 `rule_id`(기준 조건표에 없는 규칙이면 그 규칙을 가져온 곳에 적힌 규칙 id), `candidates`는 근거로 본 이 파일의 후보 id, `match`는 원문과 조건이 맞는 정도, `note`는 그렇게 본 까닭(원문이 말하는 대상 · 때와 조건이 거는 대상 · 때)이다. 근거 원문을 찾지 못하면 `match`를 `원문 없음`으로 두고 `candidates`를 비운다.
- 다음 단계에는 `approved` 후보만 쓴다.

## 6. 선택한 작업의 조건 (`output/selected_task.json`)

```json
{
  "task": "이 사건의 작업 SOP ID",
  "basis": "이 사건의 작업인 근거 — 사건 경보가 든 판정 결과의 파일:줄",
  "preparation": [ {항목} ], "prohibitions": [ {항목} ], "completion": [ {항목} ],
  "remaining_questions": [ {"item": "…", "kind": "보류 | 원문 미확인 | 제공되지 않은 절", "source": "…", "note": "…"} ],
  "sop_diff": [ {"item": "…", "where": "카드에만 | SOP 구조에만", "note": "…"} ]
}
```

- 항목: `{"candidate": "output/reviews/…_review.json#후보 id", "doc_id": "…", "rev": "…", "section": "…", "quote": "…", "decision": "…"}` — 검토 결과의 `approved` 후보를 가리키고, `doc_id` · `rev` · `section` · `quote`는 그 후보의 값이다.
- 아직 정하지 못한 것(보류 · 원문을 확인하지 못한 것 · 제공되지 않은 절)은 `remaining_questions`에 둔다. 원문과 대조해 제외한 후보는 넣지 않는다(결정 · 까닭은 검토 결과에 있다).
- 방법 단계는 넣지 않는다 — 단계 순서는 받은 SOP 구조와 원문 절차가 가진다. 첫 단계가 작업 전에 하는 확인 · 조치이면 준비로 둔다.
- `sop_diff`는 받은 SOP 구조(`data/sop.json`)의 이 작업 항목과 견주어 다른 곳이다: 모은 항목 가운데 SOP 구조의 어느 문장(단계 · 승인 역할 포함)과도 같지 않은 것은 `카드에만`(`note`에 어느 문서 · 절에서 왔는지), SOP 구조의 준비(첫 단계 포함) · 금지 · 완료 문장 가운데 모은 항목에 없는 것은 `SOP 구조에만`(`note`에 그 필드). 문장은 글자 · 숫자만 남겨 짧은 쪽의 80 % 이상이 같은 순서로 겹치면 같은 것으로 본다. 다른 곳이 없으면 `[]`.

## 7. 정할 자리 (`app/features/` — 내가 AI와 채우는 빈 틀)

첫머리에 「제공 빈 틀」 표시가 있는 파일이다. 명령마다(`python run.py <명령>`) 그 명령이 쓰는 정할 자리까지 제공 코드(`app/utils/extract.py`)를 돌려 위 결과 파일을 쓰고 `output/result.html`에 보인다. 빈 칸이나 꼴이 틀린 칸이 있으면 그 파일 · 칸과 함께 멈춘다.

- `app/features/split.json` — `단위`: 문서를 요청에 보낼 조각으로 끊는 단위 — `절`(절 머리 「## 」 · 「제N조(」 · 「절 표기 제목」 줄) · `절차`(절 머리와 「### 」 줄) · `쪽`(쪽 꼬리 「- N -」 줄 — 꼬리가 없는 문서는 문서 하나가 한 단위) · `글자`(줄 하나씩). `글자_상한`: 이어진 단위를 묶을 조각 하나의 글자 수 상한(0이면 묶지 않음, 단위가 `글자`면 1 이상). `시험_조각`: 먼저 보내 볼 조각 — 「자료 파일 이름:줄 번호」(그 줄이 든 조각). `보낼_문서`: 문서 전체를 보낼 자료 파일 이름 목록. `다시_보낼_문서`: 후보 파일이 이미 있는 문서 가운데 지금 요청 글 · 나누기로 다시 보낼 것(적지 않은 문서는 그 후보 파일을 만든 판 그대로 둔다 — 결과 화면 표에 문서마다 어느 판인지 보인다). `쓸_기록`: 같은 요청의 응답 기록이 둘 이상일 때 검토에 쓸 기록 — `{"요청 해시": "응답 기록 파일 이름"}`.
- `app/features/prompt.md` — 수업 모델에 보낼 요청 글. 첫 줄의 「제공 빈 틀」 표시 줄은 보내지 않는다. 답은 JSON 하나로 받아 4절의 필드로 읽는다(`candidates` 목록 · `warnings` 목록).
- `app/features/expected.csv` — 열 `파일,줄,종류`. 실행 전에 원문에서 찾은 항목 — `파일`은 `data/documents/` 안의 파일 이름, `줄`은 그 파일의 줄 번호, `종류`는 4절의 다섯 종류 가운데 하나.
- `app/features/review_decisions.csv` — 열 `파일,줄,종류,결정,근거,까닭,고친_인용`. 줄 · 종류가 같은 후보에 결정을 건다(같은 줄 · 종류의 후보가 여럿이면 앞의 것에 걸고 나머지는 중복으로 뺀다). `결정`은 `채택` · `수정` · `제외` · `보류`, `근거`는 「파일:줄」(여럿이면 「 · 」로), `까닭`은 원문 근거를 든 결정 이유, `고친_인용`은 `수정`일 때 그 줄의 원문 문장 그대로. `줄`을 비운 행은 판단 규칙이다 — 그 파일(`종류`를 적으면 그 종류)의 기대 항목 줄 가운데 따로 적은 행이 없는 줄 전부에 같은 결정을 둔다(수정은 줄을 적은 행에서만). 결정 표에 없는 후보는 보류(원문과 대조하지 않음)로 둔다. 그 줄 · 종류의 후보가 없고 코드가 줄을 정하지 못한 인용(`unlocated`)이 그 줄에 맞으면 검토자가 더한 후보로, 그것도 없으면 `missing`으로 적는다.
- `app/features/rule_links.csv` — 열 `rule_id,근거,match,까닭,요청할_것`. 행은 조건표에서 이 작업(`SOP-COOL-14`)에 걸린 조건(`action`이 이 작업인 `rule_id`)마다 하나. `근거`는 「파일:줄」(여럿이면 「 · 」로 — 그 줄의 후보가 `rule_links.candidates`가 된다), `match`는 `일치` · `불일치` · `원문 없음` · `보류`(원문 없음이면 근거를 비운다).
- `app/features/roles.csv` — 열 `종류,인용에_든_글자,항목,근거`. 승인 후보를 6절의 준비 · 금지 · 완료 가운데 어디에 둘지 — 종류가 같고 인용에 그 글자가 든 첫 행을 쓴다(글자 칸이 비면 그 종류 전부). `항목`은 `준비` · `금지` · `완료` · `순서` · `승인` · `넣지 않음`(6절에는 준비 · 금지 · 완료만 들어간다). 맞는 행이 없는 종류는 기본 — precondition 준비 · prohibition 금지 · completion 완료 · unit_value 완료(이 작업의 기준값은 완료 확인의 값) · step 넣지 않음(방법 단계). 이 작업의 원문 줄은 `app/features/expected.csv`의 줄이다.
- `app/features/decisions.csv` — 열 `지점,고른_것,근거,바뀌는_답`. 「학생이 정할 것」의 지점과 작업 중 정한 것(나누는 단위 · 요청 글 등)마다 한 줄. 근거는 「파일:줄」.
