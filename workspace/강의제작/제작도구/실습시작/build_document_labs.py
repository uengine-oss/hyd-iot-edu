"""문서 지식 묶음 네 랩 — 추출 둘(통합반 04회차 실습2 문서지식추출 · 실전반 03회차 실습4 지식추출)과 그래프 반영 둘(통합반 04회차 실습3 그래프반영과검증 ·
실전반 03회차 실습5 그래프반영 — 작업 확인 카드)의 학생 폴더 · ZIP · 폴더 밖 가이드를 만든다.

설계 정본: 작업 폴더 구성안50_문서지식.md · 공용틀_계약.md. 학생은 방향이 갈리는 판단만 결과/의 정할 자리(빈 틀)에 AI와 채우고,
일반 로직(읽기 · 글자 방식 · 조각 · 보내기 · 후보화 · 인용 줄 · 검토 결과 쓰기 · 적재 · 조회 · 내보내기 · 카드 글)은 제공 코드(doc_extract.py · doc_graph.py)가 한다.
학생 명령은 `python show_result.py` 하나 — 채운 정할 자리까지 lab_steps.py의 단계를 돌려 결과/보기.html을 다시 쓴다(공용 틀 lab_frame · show_result).
문서 자료는 data_documents.py 한 벌(네 랩 같은 바이트). 추출 랩 입력/ = 3회차 판정 랩 입력 · 강사 판 결과, 그래프 랩 입력/ = 2회차 실습4 입력 + 3회차 판 +
추출 랩의 강사 검토 판(reference/session3_docs/branches.py — 지점5 나 · 지점6 가, 후보는 강사 추출 실행 run1). 그래서 추출 랩을 먼저 만든다.
정답 보기 토글의 내용은 reference/session3_docs/fills.py 한 곳(기본 갈래)이다 — 같은 판을 학생용 완성본과 강사 참조 갈래 실행이 쓴다.

이 파일의 랩 정의 · 원문 · 검사기 · 결과 화면 함수(build · gbuild · lab · glab …)는 build_session4_projects.py가 입력으로 쓴다. 그 생성기가
legacy()로 산출물 경로 · 입력 경로 · 사건(incident)을 작업 자리로 돌린 뒤 build · gbuild를 부르고, 영어 경로로 옮겨 정본 자리에 쓴다.
이 파일을 직접 돌리면 멈춘다: 정본 자리에 옛 구조를 쓰던 길의 대조 기준(옛 구조 3회차 판정 랩 · 2회차 실습4 입력 · 3회차 학생용 완성본)이
새 구조(judgement-lab · action-review-lab · graph-lab)로 바뀌어 지워졌기 때문이다.
"""
from pathlib import Path
import csv
import hashlib
import html as _html
import io
import json
import re
import shutil
import sys

import lab_frame as F
import build_labs as B
import build_judgement_labs as BJ
import data_documents as DD
import lab_llm as LLM                                # 학생 폴더 llm_client.py의 원본 — 안내용 상한 값 한 곳(LLM.MAX_SENT)
from lab_package import pack

OUT = F.OUT
TOOLS = F.HERE
REF = TOOLS/'reference/session3_docs'
sys.path.insert(0, str(REF))
import fills as FL                                   # noqa: E402 — 정답 보기 · 학생용 완성본 · 갈래 실행이 같이 쓰는 정할 자리 판

write = F.write
LABS = {'integrated-04-extract': OUT/'통합반/실습/04회차/랩/04일차_실습2_문서지식추출',
        'practical-03-extract': OUT/'실전반/실습/03회차/랩/03일차_실습4_지식추출'}
TITLES = {'integrated-04-extract': '문서에서 근거 있는 지식을 추출하는 기능 만들기',
          'practical-03-extract': '문서에서 작업 조건과 근거를 추출하는 기능 만들기'}
NEXT = {'integrated-04-extract': '검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기',
        'practical-03-extract': '검토 지식으로 작업 확인 카드 만들기'}
JUDGED = {'integrated-04-extract': 'result.json', 'practical-03-extract': '조치검토결과.json'}   # 3회차 판정 랩의 결과 이름 그대로
S3_JUDGE = {'integrated-04-extract': 'integrated-03-judge', 'practical-03-extract': 'practical-03-review'}
BASE_JUDGED = B.TEACHER/'session3/갈래/판정_가-가'   # 3회차 강사 판 — 3회차 학생용 완성본과 같은 바이트
REC = '결과/검토_기록.md'
TASK = 'SOP-COOL-14'                                  # 이 사건의 작업(판정 뒤에 남은 근본 조치 — 쿨러 핀 세척). 사건이 정한다
ASSET = 'HYD-02'
EVENT_UTC = '2026-10-26T16:59:00Z'                    # 사건 경보 10월 27일 01:59(한국) — START의 사건 시각
OTHER_DOCS = ['PM-02_정기점검표.md', 'PR-07_예비품기준.md', 'HI-01_보충매뉴얼.md']   # 행 「제공 정기 점검표 · 예비품 기준 같은 다른 문서」
USB = F.USB
PROVIDED_EXTRACT = ['show_result.py', 'lab_steps.py', 'doc_extract.py', 'llm_client.py', 'check.py']
PROVIDED_GRAPH = ['show_result.py', 'lab_steps.py', 'doc_graph.py', 'lab_cypher.py', 'lab_db.py', 'check.py']


def incident():
    """사건 이름 · 시각 — build_session4_projects.legacy()가 data_conditions 판으로 바꿔 끼운다(옛 3회차 판정 랩 START.md는 지웠다)."""
    raise RuntimeError('incident()는 build_session4_projects.py의 legacy() 안에서만 정해집니다 — build_session4_projects.py로 만듭니다.')


def csv_body(text):
    """fills의 CSV 글에서 머리 줄을 뺀 행들(정답 보기에 붙여 넣는 줄)."""
    return ''.join(text.splitlines(keepends=True)[1:])


def chosen_upto(rows):
    """결과/정한_것.csv — 빈 틀 머리(「제공 빈 틀」 줄 · 열 이름) + 지금까지 정한 행."""
    return F.CHOSEN_TEMPLATE + ''.join(rows)


# ───────────── 입출력 계약(형식과 뜻만 — K-7) ─────────────
INPUT_TABLE = ('- `입력/조건표.csv` — 조건표. 열 `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section`. '
               '비교 하나가 한 행이고, 같은 `rule_id` · `action`의 행이 한 규칙 묶음이다. `action`은 그 규칙이 걸리는 조치(SOP ID), `input` · `operator` · `value` · `unit`은 비교, '
               '`result`는 `WARN`(경고) · `PENALTY`(감점) · `EXCLUDE`(제외), `reason`은 규칙의 이유, `source_section`은 그 규칙을 가져온 곳이다.\n')
INPUT_SOP = ('- `입력/sop.json` — SOP 구조. `document`가 가리키는 문서(식별자 · 판 · 파일)의 조치 절차를 구조로 옮긴 것이다. ' + BJ.SOP_KEYS)
INPUT_JUDGED = {
    'integrated-04-extract': ('- `입력/result.json` — 조건표로 경보마다 조치 후보를 판정한 결과. `events`의 경보마다 `id` · `asset` 설비 · `decision_time` 판정을 요청한 시각(UTC) · '
                              '`candidates` 후보 판정(`sop` · `status` 유지 · 제외 · 보류 · `inputs` 판단 입력 · `warnings` 경고 · `penalties` 감점 · `exclusions` 제외 — 맞은 규칙의 `rule_id`와 '
                              '조건마다 실제 값 `actual` · `unknown` 입력이 없어 맞는지 알 수 없는 규칙 · `comparison` 비교값) · `ranking` 순위 · `selection` 고른 까닭.\n'),
    'practical-03-extract': ('- `입력/조치검토결과.json` — 조건표로 경보마다 조치 후보를 판정 · 비교한 조치 검토 결과. `events`의 경보마다 `id` · `asset` 설비 · `decision_time` 판정을 요청한 시각(UTC) · '
                             '`candidates` 후보(`sop` · `status` 유지 · 제외 · 보류 · `inputs` 판단 입력 · `reasons` 이유 — 맞은 규칙의 `rule_id` · `result` · `actual_inputs` 실제 입력 · '
                             '`comparison` 비교값 · `rank` 순위 · `approval` 승인) · `review` 검토 의견(`top` 승인 요청을 검토할 후보 · `reason` · `checks`).\n')}
CONTRACT = '''# 입출력 계약

입력과 결과 파일의 형식과 뜻만 정한다. 어떤 문장을 어떤 후보로 만들지, 문서를 어떤 단위로 나눌지는 정하지 않는다. 다음 실습은 같은 모양의 검토 결과를 입력으로 읽는다. `check.py`가 이 계약의 구조와 인용을 검사한다.

## 1. 입력(읽기만)

__INPUTS__- `자료/문서_목록.csv` — 첫 줄은 내보내기 머리, 둘째 줄이 열 이름이다. 열: 문서 식별자 · 제목 · 판 · 상태 · 시행일 · 소유 부서 · 대체 관계 · 파일 · SHA-256 · 비고. 파일 칸이 빈 행은 목록에만 있고 받은 파일이 없는 문서다.
- `결과/내_입력/` — 내 앞 결과를 쓸 때 위 `입력/`의 파일과 같은 이름으로 둔다. 있으면 `check.py`는 그 파일을 기준으로 본다.

## 2. 응답 기록 (`결과/응답_기록/<요청 해시>.json` — `llm_client.py`가 쓴다)

- 키: `request_hash` 요청 해시, `model` `.env`의 모델 이름, `response_model` 응답의 model, `system_fingerprint`, `finish_reason` 답이 끝난 까닭, `method` 보낸 방법(`모델 서버` · `채팅으로 받음`), `attempt` 같은 요청을 보낸 차례, `received_at` 받은 시각, `folder_mark` 이 폴더의 표지(`결과/폴더_표지.txt`), `request` 보낸 요청, `response_text` 받은 답 글, `usable` 답에 쓸 내용이 있는지(빈 답 · 서버가 걸러 낸 답 · 거절이면 `false`), `note` `usable`이 `false`인 까닭, `response_raw` 받은 응답 원문, `usage` 토큰 수.
- 응답 기록은 고치지 않는다. `folder_mark`가 이 폴더의 `결과/폴더_표지.txt`와 다른 기록(다른 폴더에서 옮겨 온 기록)은 이 폴더에서 받은 답이 아니므로 `llm_client.py`가 다시 쓰지 않고, 그 기록으로 만든 후보는 계약 오류다. `usable`이 `false`인 기록으로는 후보를 만들지 않는다.

## 3. 후보 파일 (`결과/후보/<문서 식별자>_<판>.json` — 판이 빈 문서는 식별자만)

```json
{
  "doc_id": "문서 목록의 문서 식별자",
  "rev": "문서 목록의 판",
  "doc_status": "문서 목록의 상태",
  "source_file": "자료/ 안의 파일 이름",
  "source_sha256": "실제로 읽은 파일의 SHA-256",
  "encoding": "그 파일을 읽은 글자 방식(Python이 쓰는 이름)",
  "extractor": "이 결과를 만든 실행(코드 파일과 옵션)",
  "generated_at": "실행 시각(ISO 8601)",
  "model_run": [ {"record": "결과/응답_기록/….json", "request_hash": "…", "model": "…", "method": "…", "reused_from": null} ],
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

## 5. 검토 결과 파일 (`결과/검토/<문서 식별자>_<판>_검토.json`)

후보 파일을 복사해 아래를 더한 별도 파일이다. 후보 파일 원본은 그대로 둔다.

```json
{
  ...후보 파일의 최상위 필드...,
  "review": {"reviewer": "검토자", "reviewed_at": "시각", "candidates_file": "결과/후보/….json", "candidates_sha256": "검토를 시작할 때 후보 파일의 SHA-256",
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
- `rule_links`는 조건표의 조건__RULE_SCOPE__과 이 문서 후보의 근거 대조다. `rule_id`는 기준 조건표의 `rule_id`(기준 조건표에 없는 규칙이면 그 규칙을 가져온 곳에 적힌 규칙 id), `candidates`는 근거로 본 이 파일의 후보 id, `match`는 원문과 조건이 맞는 정도, `note`는 그렇게 본 까닭(원문이 말하는 대상 · 때와 조건이 거는 대상 · 때)이다. 근거 원문을 찾지 못하면 `match`를 `원문 없음`으로 두고 `candidates`를 비운다.
- 다음 단계에는 `approved` 후보만 쓴다.
__SELECTED__'''
SELECTED = '''
## 6. 선택한 작업의 조건 (`결과/선택작업_조건.json`)

```json
{
  "task": "이 사건의 작업 SOP ID",
  "basis": "이 사건의 작업인 근거 — 사건 경보가 든 판정 결과의 파일:줄",
  "preparation": [ {항목} ], "prohibitions": [ {항목} ], "completion": [ {항목} ],
  "remaining_questions": [ {"item": "…", "kind": "보류 | 원문 미확인 | 제공되지 않은 절", "source": "…", "note": "…"} ],
  "sop_diff": [ {"item": "…", "where": "카드에만 | SOP 구조에만", "note": "…"} ]
}
```

- 항목: `{"candidate": "결과/검토/…_검토.json#후보 id", "doc_id": "…", "rev": "…", "section": "…", "quote": "…", "decision": "…"}` — 검토 결과의 `approved` 후보를 가리키고, `doc_id` · `rev` · `section` · `quote`는 그 후보의 값이다.
- 아직 정하지 못한 것(보류 · 원문을 확인하지 못한 것 · 제공되지 않은 절)은 `remaining_questions`에 둔다. 원문과 대조해 제외한 후보는 넣지 않는다(결정 · 까닭은 검토 결과에 있다).
- 방법 단계는 넣지 않는다 — 단계 순서는 받은 SOP 구조와 원문 절차가 가진다. 첫 단계가 작업 전에 하는 확인 · 조치이면 준비로 둔다.
- `sop_diff`는 받은 SOP 구조(`입력/sop.json`)의 이 작업 항목과 견주어 다른 곳이다: 모은 항목 가운데 SOP 구조의 어느 문장(단계 · 승인 역할 포함)과도 같지 않은 것은 `카드에만`(`note`에 어느 문서 · 절에서 왔는지), SOP 구조의 준비(첫 단계 포함) · 금지 · 완료 문장 가운데 모은 항목에 없는 것은 `SOP 구조에만`(`note`에 그 필드). 문장은 글자 · 숫자만 남겨 짧은 쪽의 80 % 이상이 같은 순서로 겹치면 같은 것으로 본다. 다른 곳이 없으면 `[]`.
'''


# ───────────── 정할 자리 빈 틀(답 0 — 열 이름과 칸 이름만) ─────────────
SPLIT_BLANK = json.dumps({'제공 빈 틀 — 보관 없이 바로 채웁니다. 칸의 뜻은 입출력_계약.md 「정할 자리」': '', '단위': '', '글자_상한': None, '시험_조각': '',
                          '보낼_문서': [], '다시_보낼_문서': [], '쓸_기록': {}}, ensure_ascii=False, indent=2) + '\n'
PROMPT_BLANK = ('> 제공 빈 틀 — 수업 모델에 보낼 요청 글을 내 말로 씁니다. 이 줄은 모델에 보내지 않습니다.\n\n# 뽑을 것\n\n# 지킬 것\n\n# 하지 말 것\n\n# 모르면\n\n# 답의 꼴\n')


XBASIS = '근거 = 원문 파일 이름:줄(여럿이면 「 · 」로 잇기)'
XCOLS = {   # 추출 랩 정할 자리 표의 칸 뜻 — 빈 틀 둘째 줄 · 그 단계 힌트 「지킬 것」 · 정답 보기 머리가 같은 글(값은 넣지 않는다)
    '기대_항목.csv': '파일 = 자료/ 안의 파일 이름 · 줄 = 그 파일의 줄 번호 · 종류 = step · precondition · prohibition · completion · unit_value 가운데 하나(한 줄에 두 종류면 두 행)',
    '검토_결정.csv': ('파일 · 줄 · 종류 = 기대 항목의 그 줄(줄을 비운 행은 판단 규칙 — 그 파일의 기대 줄 가운데 따로 적은 행이 없는 줄 전부, 종류를 적으면 그 종류만) · '
                   '결정 = 채택 · 수정 · 제외 · 보류 · ' + XBASIS + ' · 까닭 = 원문 근거를 든 이유 한 줄 · 고친_인용 = 수정일 때만 그 줄의 원문 문장 그대로'),
    '조건_대조.csv': 'rule_id = 조건표의 rule_id · ' + XBASIS + '(원문 없음이면 비움) · match = 일치 · 불일치 · 원문 없음 · 보류 · 까닭 = 원문의 대상 · 때와 조건의 대상 · 때 · 요청할_것 = 없으면 「없음」',
    '역할.csv': ('종류 = 후보의 종류 · 인용에_든_글자 = 이 글자가 든 후보만(비우면 그 종류 전부, 위 행이 먼저) · 항목 = 준비 · 금지 · 완료 · 순서 · 승인 · 넣지 않음 가운데 하나 · '
              '근거 = 원문 파일:줄 또는 입출력_계약.md 절 — 행이 없는 종류는 계약 6절의 기본(precondition 준비 · prohibition 금지 · completion 완료 · unit_value 완료 · step 넣지 않음)'),
}


XCOLS_P = {   # 실전(한 칸의 첫 랩 — 같은 뜻, 짧게)
    '기대_항목.csv': '파일 = 자료/ 안의 파일 이름 · 줄 · 종류(step · precondition · prohibition · completion · unit_value, 한 줄에 둘이면 두 행)',
    '검토_결정.csv': '파일 · 줄 · 종류 = 기대 항목의 그 줄(줄을 비운 행은 판단 규칙 — 그 파일의 남은 기대 줄 전부) · 결정 = 채택 · 수정 · 제외 · 보류 · 근거 = 파일:줄(여럿이면 「 · 」) · 까닭 · 고친_인용 = 수정일 때 원문 그대로',
    '조건_대조.csv': 'rule_id · 근거 = 파일:줄(원문 없음이면 비움) · match = 일치 · 불일치 · 원문 없음 · 보류 · 까닭 = 원문과 조건의 대상 · 때 · 요청할_것(없으면 「없음」)',
    '역할.csv': '종류 · 인용에_든_글자(비우면 그 종류 전부, 위 행이 먼저) · 항목 = 준비 · 금지 · 완료 · 순서 · 승인 · 넣지 않음 · 근거 — 행이 없는 종류는 계약 6절의 기본',
}


def xcol(name, practical):
    return XCOLS_P.get(name, XCOLS[name]) if practical else XCOLS[name]


def xblank(name, columns, explain, practical=False):
    head, cols = F.blank_csv(columns, explain).split('\n', 1)
    return f'{head}\n# {xcol(name, practical)}\n{cols}'


def extract_blanks(key):
    practical = key == 'practical-03-extract'
    out = {'결과/나누기.json': SPLIT_BLANK, '결과/prompt.md': PROMPT_BLANK,
           '결과/기대_항목.csv': xblank('기대_항목.csv', ['파일', '줄', '종류'], '실행 전에 원문에서 찾은 항목', practical),
           '결과/검토_결정.csv': xblank('검토_결정.csv', ['파일', '줄', '종류', '결정', '근거', '까닭', '고친_인용'], '원문과 대조한 결정', practical),
           '결과/조건_대조.csv': xblank('조건_대조.csv', ['rule_id', '근거', 'match', '까닭', '요청할_것'], '조건표의 조건마다 근거 원문 · 맞는 정도 · 까닭 · 요청할 것', practical),
           F.CHOSEN_FILE: F.CHOSEN_TEMPLATE}
    if practical:
        out['결과/역할.csv'] = xblank('역할.csv', ['종류', '인용에_든_글자', '항목', '근거'], '승인 후보의 종류를 이 작업의 준비 · 금지 · 완료 가운데 어디에 둘지(계약 기본과 다르게 둘 것만)', practical)
    return out


SLOT_CONTRACT = '''
## __N__. 정할 자리 (`결과/` — 내가 AI와 채우는 빈 틀)

첫머리에 「제공 빈 틀」 표시가 있는 파일이다. `python show_result.py`가 채운 자리까지 제공 코드(`doc_extract.py`)를 돌려 위 결과 파일을 쓰고 `결과/보기.html`에 보인다. 빈 칸이나 꼴이 틀린 칸이 있으면 그 파일 · 칸과 함께 멈춘다.

- `결과/나누기.json` — `단위`: 문서를 요청에 보낼 조각으로 끊는 단위 — `절`(절 머리 「## 」 · 「제N조(」 · 「절 표기 제목」 줄) · `절차`(절 머리와 「### 」 줄) · `쪽`(쪽 꼬리 「- N -」 줄 — 꼬리가 없는 문서는 문서 하나가 한 단위) · `글자`(줄 하나씩). `글자_상한`: 이어진 단위를 묶을 조각 하나의 글자 수 상한(0이면 묶지 않음, 단위가 `글자`면 1 이상). `시험_조각`: 먼저 보내 볼 조각 — 「자료 파일 이름:줄 번호」(그 줄이 든 조각). `보낼_문서`: 문서 전체를 보낼 자료 파일 이름 목록. `다시_보낼_문서`: 후보 파일이 이미 있는 문서 가운데 지금 요청 글 · 나누기로 다시 보낼 것(적지 않은 문서는 그 후보 파일을 만든 판 그대로 둔다 — 결과 화면 표에 문서마다 어느 판인지 보인다). `쓸_기록`: 같은 요청의 응답 기록이 둘 이상일 때 검토에 쓸 기록 — `{"요청 해시": "응답 기록 파일 이름"}`.
- `결과/prompt.md` — 수업 모델에 보낼 요청 글. 첫 줄의 「제공 빈 틀」 표시 줄은 보내지 않는다. 답은 JSON 하나로 받아 4절의 필드로 읽는다(`candidates` 목록 · `warnings` 목록).
- `결과/기대_항목.csv` — 열 `파일,줄,종류`. 실행 전에 원문에서 찾은 항목 — `파일`은 `자료/` 안의 파일 이름, `줄`은 그 파일의 줄 번호, `종류`는 4절의 다섯 종류 가운데 하나.
- `결과/검토_결정.csv` — 열 `파일,줄,종류,결정,근거,까닭,고친_인용`. 줄 · 종류가 같은 후보에 결정을 건다(같은 줄 · 종류의 후보가 여럿이면 앞의 것에 걸고 나머지는 중복으로 뺀다). `결정`은 `채택` · `수정` · `제외` · `보류`, `근거`는 「파일:줄」(여럿이면 「 · 」로), `까닭`은 원문 근거를 든 결정 이유, `고친_인용`은 `수정`일 때 그 줄의 원문 문장 그대로. `줄`을 비운 행은 판단 규칙이다 — 그 파일(`종류`를 적으면 그 종류)의 기대 항목 줄 가운데 따로 적은 행이 없는 줄 전부에 같은 결정을 둔다(수정은 줄을 적은 행에서만). 결정 표에 없는 후보는 보류(원문과 대조하지 않음)로 둔다. 그 줄 · 종류의 후보가 없고 코드가 줄을 정하지 못한 인용(`unlocated`)이 그 줄에 맞으면 검토자가 더한 후보로, 그것도 없으면 `missing`으로 적는다.
- `결과/조건_대조.csv` — 열 `rule_id,근거,match,까닭,요청할_것`. __RULES__ `근거`는 「파일:줄」(여럿이면 「 · 」로 — 그 줄의 후보가 `rule_links.candidates`가 된다), `match`는 `일치` · `불일치` · `원문 없음` · `보류`(원문 없음이면 근거를 비운다).
__ROLE__- `결과/정한_것.csv` — 열 `지점,고른_것,근거,바뀌는_답`. 「학생이 정할 것」의 지점과 작업 중 정한 것(나누는 단위 · 요청 글 등)마다 한 줄. 근거는 「파일:줄」.
'''
ROLE_CONTRACT = ('- `결과/역할.csv` — 열 `종류,인용에_든_글자,항목,근거`. 승인 후보를 6절의 준비 · 금지 · 완료 가운데 어디에 둘지 — 종류가 같고 인용에 그 글자가 든 첫 행을 쓴다(글자 칸이 비면 그 종류 전부). '
                 '`항목`은 `준비` · `금지` · `완료` · `순서` · `승인` · `넣지 않음`(6절에는 준비 · 금지 · 완료만 들어간다). 맞는 행이 없는 종류는 기본 — precondition 준비 · prohibition 금지 · completion 완료 · unit_value 완료(이 작업의 기준값은 완료 확인의 값) · step 넣지 않음(방법 단계). 이 작업의 원문 줄은 `결과/기대_항목.csv`의 줄이다.\n')


def contract(key):
    practical = key == 'practical-03-extract'
    inputs = INPUT_TABLE + INPUT_SOP + INPUT_JUDGED[key]
    rules = (f'행은 조건표에서 이 작업(`{TASK}`)에 걸린 조건(`action`이 이 작업인 `rule_id`)마다 하나.' if practical else '행은 조건표의 조건(`rule_id`)마다 하나.')
    slot = SLOT_CONTRACT.replace('__N__', '7' if practical else '6').replace('__RULES__', rules).replace('__ROLE__', ROLE_CONTRACT if practical else '')
    return (CONTRACT.replace('__INPUTS__', inputs).replace('__SELECTED__', (SELECTED if practical else '') + slot)
            .replace('__RULE_SCOPE__', f'(이 작업 `{TASK}`에 걸린 조건 — `action`이 이 작업인 행)' if practical else '')
            .replace('`extractor` | 이 결과를 만든 실행(코드 파일과 옵션)', '`extractor` | 이 결과를 만든 실행(제공 코드와 정할 자리 설정)'))


def record_template(key):
    practical = key == 'practical-03-extract'
    task = '## 이 사건의 작업\n\n- 작업:\n- 근거(파일:줄):\n\n' if practical else ''
    return ('# 문서 지식 검토 기록\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n## 목표와 질문\n\n## 이 답을 쓰는 사람과 쓰는 곳\n\n' + task +
            f'## 정한 것\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `{F.CHOSEN_FILE}`에 적습니다.\n\n'
            '## 기대 항목\n\n기대 항목은 `결과/기대_항목.csv`에 적습니다.\n\n- 기대 칸을 쓴 시각:\n\n'
            '## 기대와 다른 줄\n\n| 문서 · 줄 · 종류 | 결과 화면의 표시 | 차이 종류 | 까닭(원문 줄) |\n|---|---|---|---|\n| | | | |\n\n'
            '## 같은 요청을 한 번 더 보낸 결과\n\n| 첫 응답 기록 | 다시 보낸 응답 기록 | 다른 점 | 검토에 쓸 기록과 까닭 |\n|---|---|---|---|\n| | | | |\n\n'
            '## 다른 문서에 적용\n\n| 문서 · 판 | 후보 수 | 실제 누락 | 근거 없는 생성 | 고친 점 | 고친 뒤 다시 센 수 |\n|---|---|---|---|---|---|\n| | | | | | |\n\n'
            '## 남은 질문\n\n## 저장 기록\n\n- 기준일:\n- 저장 시점:\n- 확인하지 못한 점:\n')


ENV_EXAMPLE = '''# 이 파일을 복사해 이름을 .env로 바꾸고, 아래 세 줄을 강의에서 받은 접속 세 줄로 바꿔 붙여 넣은 뒤 저장합니다.
OPENAI_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
'''


def result_readme(key):
    extra = ' · `선택작업_조건.json`' if key == 'practical-03-extract' else ''
    return ('이번 과제의 정할 자리(「제공 빈 틀」 파일)를 여기서 채웁니다. `python show_result.py`가 채운 자리까지 제공 코드를 돌려 후보(`후보/`) · 검토 결과(`검토/`)' + extra +
            ' · 시험 조각 결과를 쓰고 `보기.html`에 보입니다.\n'
            '`응답_기록/` · `요청/` · `폴더_표지.txt`는 `llm_client.py`가 쓰므로 고치지 않습니다.\n'
            '다시 열 때는 `검토_기록.md`의 기준일 · 저장 시점과 `python check.py`의 출력을 함께 봅니다.\n')


def input_readme(key, n_events):
    judged = JUDGED[key]
    what = '판정한 결과' if key == 'integrated-04-extract' else '판정 · 비교한 조치 검토 결과'
    return ('# 입력 — 읽기만 합니다\n\n조치를 판정하는 실습의 결과와 같은 꼴로 검증해 제공하는 판입니다. 형식과 키의 뜻은 `입출력_계약.md` 「입력」에 있습니다.\n\n'
            '- `조건표.csv` — 냉각 계통 조치의 조건표(규칙마다 비교 · 결과 · 이유 · 가져온 곳).\n'
            '- `sop.json` — SOP 구조. `document`가 가리키는 문서의 조치 절차를 구조로 옮긴 것입니다.\n'
            f'- `{judged}` — 사건 경보를 포함한 지난 30일(2026-09-28 ~ 10-27) 경보 {n_events}건을 위 조건표로 {what}.\n')


# ───────────── 결과 화면의 단계(lab_steps.py — 제공 파일, 답 0) ─────────────
EXTRACT_STEPS = r'''"""__TITLE__ — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 고치지 않는다.
단계마다 정할 자리(결과/의 「제공 빈 틀」 파일)를 채웠으면 제공 코드(doc_extract.py)를 돌려 그 결과를 결과/보기.html에 보인다."""
from pathlib import Path
import json
import show_result as R
import doc_extract as X

HERE = Path(__file__).resolve().parent
TITLE = '__TITLE__'
PRACTICAL = __PRACTICAL__
TASK, ASSET, EVENT_UTC, JUDGED = '__TASK__', '__ASSET__', '__EVENT__', '__JUDGED__'
OTHER_DOCS = __OTHER__


def owner(where):
    """그 파일을 정할 자리로 가진 단계 — 「N단계 「이름」의 정할 자리」(STEPS는 이 파일 끝에서 정한다)."""
    rel = str(where).split(':')[0].split(' ')[0]
    hit = next((x for x in STEPS if rel in x['slots']), None)
    return f' — {hit["no"]}단계 「{hit["name"]}」의 정할 자리' if hit else ''


def guard(fn):
    """제공 코드의 꼴 문제(Problem) · 수업 모델 멈춤(llm_client Stop)을 결과 화면의 빨간 칸으로."""
    def run(previous):
        try:
            return fn(previous)
        except X.Problem as e:
            raise R.Stop(str(e) + owner(e.where))
        except SystemExit:
            raise R.Stop('수업 모델에 보내지 못하고 멈췄습니다 — 터미널에 찍힌 까닭을 봅니다(키가 없으면 보낼 글이 결과/요청/에 남습니다).')
    return run


def settings():
    cfg = X.settings()
    if cfg is None:
        raise R.Blank('결과/나누기.json 「단위」가 비어 있습니다.')
    return cfg


def prompt():
    p = X.prompt_text()
    if not p:
        raise R.Blank('결과/prompt.md에 요청 글이 아직 없습니다.')
    return p


def event():
    data = json.loads((X.basis(JUDGED)).read_text(encoding='utf-8'))
    near = [e for e in data['events'] if e['asset'] == ASSET]
    gap = lambda e: abs(int(e['decision_time'][8:10]) * 1440 + int(e['decision_time'][11:13]) * 60 + int(e['decision_time'][14:16])
                       - (int(EVENT_UTC[8:10]) * 1440 + int(EVENT_UTC[11:13]) * 60 + int(EVENT_UTC[14:16])))
    return min(near, key=gap), data


@guard
def look(previous):
    e, _ = event()
    ranks = {r['sop']: r['rank'] for r in e.get('ranking', [])}
    rows = [[c['sop'], c['status'], c.get('rank', ranks.get(c['sop'], ''))] for c in e['candidates']]
    sop = json.loads(X.basis('sop.json').read_text(encoding='utf-8'))
    rel = [[r['type'], r['from'], r['to'], r.get('source', '')] for r in sop['relations'] if TASK in (r['from'], r['to'])]
    docs = [[row['문서 식별자'], row['판'], row['상태'], row['파일'] or '(받은 파일 없음)', enc or '', len(text.splitlines()) if text else '',
             len(X.section_heads(text)) if text else '', (text.splitlines()[0][:60] if text else why)] for row, text, enc, raw, why in X.documents()]
    rules = sorted({r['rule_id'] for r in X.csv_rows(X.basis('조건표.csv')) if not PRACTICAL or r.get('action') == TASK})
    return [R.table(f'사건 경보 {e["id"]}(판정 요청 {e["decision_time"]} UTC)의 조치 후보', ['조치', '판정', '순위'], rows),
            R.table(f'받은 SOP 구조에서 {TASK}가 걸린 관계', ['관계', '시작', '끝', '출처'], rel),
            R.table('문서 묶음 — 목록의 판 · 상태와 읽은 결과(SHA-256이 목록과 같은 파일만 읽음)', ['문서', '판', '상태', '파일', '글자 방식', '줄 수', '절 머리 수', '첫 줄 또는 읽지 못한 까닭'], docs),
            R.note(('이 작업에 걸린 조건' if PRACTICAL else '조건표의 조건') + ': ' + ', '.join(rules))]


def connect(previous):
    import llm_client as L
    conf = L.settings()
    have = [n for n in L.NAMES if conf[n]]
    return [R.counts('수업 모델 연결 값과 응답 기록(값은 보이지 않음)', [('.env에 채운 줄', f'{len(have)} / 3'), ('응답 기록 수', len(L.records())),
                                                         ('이 폴더의 안내용 상한까지 남은 수', L.MAX_SENT - L.sent_count())]),
            R.note('연결 확인은 터미널에서 `python llm_client.py`로 합니다 — 결과 화면은 모델을 부르지 않습니다.')]


@guard
def expect(previous):
    rows = X.expected_rows()
    if not rows:
        raise R.Blank('결과/기대_항목.csv에 행이 없습니다.')
    out = [R.table('기대 항목 — 내가 적은 줄의 원문', ['파일', '줄', '종류', '원문'], [[f, n, k, X.source_line(f, n)] for f, n, k in rows])]
    for name in dict.fromkeys(f for f, _, _ in rows):
        lines = [n for f, n, _ in rows if f == name]
        out.append(R.source_lines(HERE / '자료' / name, min(lines), max(lines)))
    return out


@guard
def split(previous):
    cfg = settings()
    docs = X.by_file()
    rows = []
    for name, (row, text, enc, raw) in docs.items():
        for no, (first, body) in enumerate(X.split_chunks(text, cfg['단위'], cfg['글자_상한']), 1):
            a, b = X.chunk_range(first, body)
            rows.append([name, no, f'{a}~{b}', len(body), body.splitlines()[0][:50]])
    per = {}
    for r in rows:
        per[r[0]] = per.get(r[0], 0) + 1
    out = [R.counts('문서마다 조각 수', sorted(per.items()) + [('전체 조각', len(rows))]),
           R.table('조각 목록', ['파일', '조각', '줄 범위', '글자 수', '첫 줄'], rows)]
    try:
        need, left = X.to_send(cfg, X.prompt_text() or '(요청 글 없음)', cfg['보낼_문서'])
        out.append(R.counts('보낼 문서의 요청 수(보내지 않고 셈)', [('보낼 요청', need), ('이 폴더의 안내용 상한까지 남은 수', left)]))
    except X.Problem as e:
        out.append(R.note(f'보낼 수를 세지 못함 — {e}'))
    return out


@guard
def trial(previous):
    cfg = settings()
    p = prompt()
    if not cfg['시험_조각']:
        raise R.Blank('결과/나누기.json 「시험_조각」이 비어 있습니다 — 먼저 보내 볼 조각의 「파일:줄」을 적습니다.')
    got = X.trial(cfg, p)
    out = [R.note(f'시험 조각: {got["source_file"]} {got["chunk"][0]}~{got["chunk"][1]}줄 · 요청 해시 {got["request_hash"]}')]
    sop = json.loads(X.basis('sop.json').read_text(encoding='utf-8'))
    for a in got['answers']:
        out.append(R.table(f'{a["record"]}의 후보(끝난 까닭 {a["finish_reason"]})', ['id', '종류', '절', '절차', '줄', '찾은 방법', '인용'],
                           [[c['id'], c['kind'], c['section'], c['procedure'] or '', f'{c["line_start"]}~{c["line_end"]}', c['quote_match'], c['quote']] for c in a['candidates']]
                           + [[u['id'], u['kind'], u['section'], u['procedure'] or '', '', '찾지 못함', u['quote']] for u in a['unlocated']],
                           note=' · '.join(a['warnings'][:5])))
    if len(got['answers']) == 2:
        q = [{X.squash(c['quote']) for c in a['candidates']} for a in got['answers']]
        out.append(R.counts('같은 요청 두 답', [('두 답에 함께 있는 인용', len(q[0] & q[1])), ('첫 답에만', len(q[0] - q[1])), ('다시 보낸 답에만', len(q[1] - q[0]))]))
    procs = {c['procedure'] for a in got['answers'] for c in a['candidates'] if c['procedure']}
    rows = []
    for s in sop['sops']:
        if s['id'] in procs:
            for f in ('apply_conditions', 'prohibitions', 'steps', 'completion'):
                for x in s.get(f, []):
                    t = x.get('text') if isinstance(x, dict) else str(x)
                    hit = [c['id'] for c in got['answers'][0]['candidates'] if X.squash(c['quote']) and (X.squash(c['quote']) in X.squash(t) or X.squash(t) in X.squash(c['quote']))]
                    rows.append([s['id'], f, t, ' · '.join(hit) or '짝 없음'])
    if rows:
        out.append(R.table('받은 SOP 구조의 같은 작업 항목 ↔ 첫 답의 후보(글자 짝 — 뜻이 같은지는 원문 줄로 본다)', ['조치', '칸', '받은 SOP 구조의 글', '짝지은 후보'], rows))
    return out


@guard
def split_trial(previous):
    return split(previous) + trial(previous)


@guard
def main_run(previous):
    cfg = settings()
    p = prompt()
    if not cfg['보낼_문서']:
        raise R.Blank('결과/나누기.json 「보낼_문서」가 비어 있습니다.')
    done = X.extract(cfg, p, cfg['보낼_문서'])
    rows = []
    for name, what in done:
        data = X.load_candidates(name)
        cut = sum(1 for w in data['warnings'] if '길이 상한' in w)
        empty, loose = X.coverage(cfg, name)
        rows.append([name, len(data['candidates']), len(data['unlocated']), cut, ' · '.join(empty) or '없음', len(loose), X.made_with(data), what])
    out = [R.table('보낸 문서 — 후보 파일(「찾지 못한 인용」은 누락이 아님 — 누락은 후보 0개 조각 · 후보가 걸리지 않은 내용 줄을 원문으로 열어 판단한다)',
                   ['파일', '후보', '찾지 못한 인용', '길이 상한에서 잘린 답', '후보 0개 조각(줄)', '후보가 걸리지 않은 내용 줄', '후보를 만든 판', '이번 실행'], rows)]
    exp, extra = X.compare_expected()
    out.append(R.table('기대 항목 ↔ 후보(줄 · 종류로 짝 — 뜻이 같은지는 원문 줄로 본다)', ['파일', '줄', '종류', '원문', '표시', '후보'], [list(r) for r in exp]))
    if extra:
        out.append(R.table('기대 줄 사이에 있는데 기대에 없는 후보', ['파일', '줄', '종류', '후보', '인용'], [list(r) for r in extra]))
    return out


@guard
def review(previous):
    if not X.decision_rows():
        raise R.Blank('결과/검토_결정.csv에 행이 없습니다.')
    written = X.apply_review(TASK if PRACTICAL else None)
    rows, task_rows = [], []
    exp = {(f, n) for f, n, _ in X.expected_rows()}
    for path in written:
        d = json.loads(path.read_text(encoding='utf-8'))
        count = {}
        for c in d['candidates']:
            count[c['decision']] = count.get(c['decision'], 0) + 1
            if any(f == d['source_file'] and c['line_start'] <= n <= c['line_end'] for f, n in exp):
                task_rows.append([d['doc_id'], d['rev'], c['line_start'], c['kind'], c['decision'], c['quote'][:80]])
        rows.append([path.name, count.get('채택', 0), count.get('수정', 0), count.get('제외', 0), count.get('보류', 0), len(d['missing']),
                     sum(1 for m in d['missing'] if m.get('added'))])
    return [R.table('검토 결과 파일', ['파일', '채택', '수정', '제외', '보류', '누락 기록', '검토자가 더한 후보'], rows),
            R.table('기대 항목 줄의 결정(이 작업의 조건이 될 것)', ['문서', '판', '줄', '종류', '결정', '인용'], task_rows)]


@guard
def rules(previous):
    linked, known = X.rule_rows(TASK if PRACTICAL else None)
    if not linked:
        raise R.Blank('결과/조건_대조.csv에 행이 없습니다.')
    X.apply_review(TASK if PRACTICAL else None)
    _, data = event()
    out = []
    rows = []
    for r in linked:
        hit = []
        for e in data['events']:
            for c in e['candidates']:
                excluded_by = {x.get('rule_id') for x in c.get('exclusions', [])} | {x.get('rule_id') for x in c.get('reasons', []) if x.get('result') == 'EXCLUDE'}
                if c['sop'] == TASK and c['status'] == '제외' and r['rule_id'] in excluded_by:
                    hit.append(e['id'])
        rows.append([r['rule_id'], r['match'], r['근거'] or '(근거 없음)', r['까닭'], r['요청할_것'], ', '.join(hit) or '없음'])
        for f, n in r['refs']:
            out.append(R.source_lines(HERE / '자료' / f, n))
    missing = [x for x in known if x not in {r['rule_id'] for r in linked}]
    head = [R.table(f'조건마다 근거 대조 — 「바뀌는 답」 칸은 그 조건이 {TASK}를 제외한 지난 판정', ['rule_id', 'match', '근거', '까닭', '요청할 것', f'{TASK}를 제외한 지난 판정'], rows)]
    if missing:
        head.append(R.note('아직 근거 대조가 없는 조건: ' + ', '.join(missing)))
    return head + out


@guard
def other(previous):
    cfg = settings()
    if not set(cfg['보낼_문서']) & set(OTHER_DOCS):
        raise R.Blank('결과/나누기.json 「보낼_문서」에 다른 문서(' + ' · '.join(OTHER_DOCS) + ')가 아직 없습니다.')
    X.extract(cfg, prompt(), cfg['보낼_문서'])
    rows = []
    for name in cfg['보낼_문서']:
        d = X.load_candidates(name)
        empty, loose = X.coverage(cfg, name)
        rows.append([name, len(d['candidates']), len(d['unlocated']), sum(1 for w in d['warnings'] if '계약 꼴' in w), ' · '.join(empty) or '없음', len(loose), ' '.join(map(str, loose[:40])), X.made_with(d)])
    name, data, pairs = X.compare_baseline()
    out = [R.table('문서마다 후보와 누락을 가를 재료 — 후보 0개 조각은 그 조각의 답이 비었다는 뜻(원문 문장을 모델이 지시로 읽었는지 요청 글로 본다)',
                   ['파일', '후보', '찾지 못한 인용', '계약 꼴 아님', '후보 0개 조각(줄)', '후보가 걸리지 않은 내용 줄', '그 줄 번호(앞 40개)', '후보를 만든 판'], rows)]
    if data is None:
        out.append(R.note(f'받은 SOP 구조가 옮긴 문서({name})의 후보 파일이 아직 없습니다 — 보낼_문서에 넣습니다.'))
    else:
        out.append(R.table(f'받은 SOP 구조 ↔ {name} 후보(글자 짝 없음 = 원문 줄을 열어 실제 누락인지 내가 본다)', ['조치', '칸', '글', '짝지은 후보'], [list(p) for p in pairs]))
    return out


@guard
def collect(previous):
    if not X.role_rows():
        raise R.Blank('결과/역할.csv에 행이 없습니다.')
    e, _ = event()
    src = X.basis(JUDGED)
    n = next((i for i, x in enumerate(src.read_text(encoding='utf-8').splitlines(), 1) if f'"{e["id"]}"' in x), 0)
    got = X.collect_task(TASK, f'{src.relative_to(HERE).as_posix()}:{n}')
    out = [R.counts('이 작업의 조건', [(k, len(got[k])) for k in ('preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff')])]
    for k in ('preparation', 'prohibitions', 'completion'):
        out.append(R.table(k, ['검토 후보', '문서', '판', '절', '인용'], [[i['candidate'], i['doc_id'], i['rev'], i['section'], i['quote']] for i in got[k]]))
    out.append(R.table('sop_diff', ['where', 'item', 'note'], [[d['where'], d['item'], d['note']] for d in got['sop_diff']]))
    return out


@guard
def main_other(previous):
    out = main_run(previous)
    try:
        out += other(previous)
    except R.Blank as e:
        out.append(R.note(str(e)))
    return out


def save(previous):
    import subprocess, sys
    run = subprocess.run([sys.executable, str(HERE / 'check.py')], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    tail = run.stdout.strip().splitlines()[-12:]
    return [R.note('python check.py 출력(끝 12줄, 종료 코드 ' + str(run.returncode) + ')\n' + '\n'.join(tail))]


__STEPS__
'''


def extract_steps_source(key, L):
    practical = key == 'practical-03-extract'
    runs = {'start': 'look', 'connect': 'connect', 'expect': 'expect', 'split': 'split', 'prompt': 'split_trial' if practical else 'trial',
            'main': 'main_other' if practical else 'main_run', 'rev1': 'review', 'rev2': 'rules', 'other': 'other', 'collect': 'collect', 'save': 'save'}
    slots = {'expect': ['결과/기대_항목.csv'], 'split': ['결과/나누기.json'], 'prompt': (['결과/나누기.json'] if practical else []) + ['결과/prompt.md'], 'rev1': ['결과/검토_결정.csv'],
             'rev2': ['결과/조건_대조.csv'], 'collect': ['결과/역할.csv']}
    lines = ['STEPS = [']
    for no, (k, s) in enumerate(zip(step_order(key), L['steps']), 1):
        lines.append(f'    dict(no={no}, name={s["name"]!r}, slots={slots.get(k, [])!r}, run={runs[k]}),')
    lines.append(']')
    return (EXTRACT_STEPS.replace('__TITLE__', L['title']).replace('__PRACTICAL__', str(practical)).replace('__TASK__', TASK).replace('__ASSET__', ASSET)
            .replace('__EVENT__', EVENT_UTC).replace('__JUDGED__', JUDGED[key]).replace('__OTHER__', repr(OTHER_DOCS)).replace('__STEPS__', '\n'.join(lines) + '\n'))


# ───────────── 단계(한 단계 = 판단 하나 또는 일곱 단계의 한 몫) ─────────────
H, S, A = F.H, F.S, F.A
SHOW = F.SHOW_CMD
WHY_SPLIT = ('한 번에 보내는 글이 길면 답이 길이 상한에서 잘리거나 빠뜨리는 것이 늘고, 너무 짧게 자르면 조건과 그 대상이 다른 조각으로 갈라집니다. '
             '문서마다 보관 단위(절 · 절차 · 쪽)가 달라 어디서 끊을지가 결과를 가르고, 조각 수만큼 요청을 보냅니다.')
WHY_PROMPT = ('요청 글은 모델에게 주는 작업 지시이고, 구조화 출력은 답의 모양만 맞춰 줄 뿐 그 안의 사실이 원문과 같은지는 따로 확인해야 합니다. '
              '같은 요청에도 답은 매번 다를 수 있어, 문서 전체에 보내기 전에 한 조각을 두 번 보내 검토된 구조와 견주고 요청 글을 굳힙니다.')
WHY_MAIN = ('한 조각에서 맞은 요청 글도 문서 전체에서는 빠뜨리거나 다른 절에 잇는 것이 생깁니다. 실행 전에 원문에서 적은 기대와 줄마다 견주어야 차이가 나눈 단위 · 요청 글 때문인지 모델 응답 때문인지 나눌 수 있습니다.')
WHY_REV1 = ('사람 검토의 네 결정은 채택 · 수정 · 제외 · 보류이고, 보류는 근거가 더 필요하다는 기록이지 버린 것이 아니며 원문과 대조하지 않은 후보는 승인하지 않습니다. '
            '같은 작업을 사내 문서와 제조사 지침이 함께 말하면 어느 쪽을 작업 조건으로 둘지 문서의 머리말 · 문서 관리 기준을 읽고 정합니다.')
WHY_REV2 = '허용 · 제외 조건은 출처로 돌아갈 수 있어야 고칠 수 있습니다. 원문이 말하는 대상 · 때와 조건이 거는 대상 · 때가 같은지 견주어야, 그 원문이 그 조건의 근거인지 말할 수 있습니다.'
WHY_OTHER = ('누락은 원문에 있는데 후보에 없는 것, 근거 없는 생성은 후보에 있는데 원문에 없는 것이고, 한 문서에서 맞은 요청 글이 형식이 다른 문서에서도 맞는지는 돌려 세어 봐야 압니다. '
             '받은 SOP 구조의 한 칸은 여러 절을 합쳐 적은 것이 있어, 코드가 낸 「짝 없음」은 원문 줄을 열어 실제 누락만 셉니다.')


def PX(N, judged, xcols):
    """실전 추출 랩 단계 글(한 칸에 두 랩 — 실전반 지침 P-9: 기본 조작은 한두 문장, 결과 해석과 선택 이유). 남기는 것: 판단 · 원문 근거 · 결과 확인 · 실제로 막혔던 자리의 「다를 때」."""
    C = F.CHOSEN_FILE
    return {
        'start': dict(why=F.WHY_START,
                      do=f'`{SHOW}`로 결과 화면을 열어 사건 경보의 조치 후보 · 핀 세척이 걸린 관계 · 문서 표를 보고, AI에게 파일을 바꾸지 말고 핀 세척 원문의 절 · 줄을 물어 직접 연 뒤 `{REC}` 「이 사건의 작업」에 적습니다.',
                      ask='핀 세척이 근본 조치라는 근거 줄을 묻습니다.', evidence=f'1단계 표가 보이고, {F.EVIDENCE_LOOK}',
                      hint=H('핀 세척 원문의 자리를 찾는다', f'결과 화면 1단계, `입력/{judged}` · `입력/sop.json`, `자료/`', '파일을 바꾸지 않는다. 파일:줄을 먼저 댄다', '문서마다 절 · 줄 목록', '짚은 줄을 직접 연다')),
        'connect': dict(why='첫 요청은 1분쯤 걸려 여기서 미리 한 번 보냅니다.',
                        do='`.env.example`을 `.env`로 복사해 받은 세 줄을 붙여 넣고 저장한 뒤 `python llm_client.py`를 실행합니다.',
                        ask='키가 없으면 학생용 완성본으로 결과를 볼지 정합니다.', evidence='「연결됨」과 모델 이름이 나옵니다.',
                        hint=H('수업 모델 연결을 확인한다', '`.env.example`, 받은 세 줄', '키를 채팅 · 파일 · 기록에 붙이지 않는다', '`python llm_client.py` 출력', '첫 줄과 모델 이름'),
                        differ='「요청을 보내지 못했습니다」 뒤의 문장이 고칠 곳입니다.'),
        'expect': dict(why='모델의 답을 본 뒤에 기대를 적으면 빠진 것과 지어낸 것이 기대에 섞여 보이지 않습니다.',
                       do=f'`결과/기대_항목.csv`에 핀 세척 작업의 원문 줄을 파일 · 줄 · 종류로, `{REC}`에 목표 · 쓰는 사람 · 기대 칸을 쓴 시각을 적고 `{SHOW}`로 그 줄의 원문을 봅니다.' + F.REQ_AFTER,
                       ask='줄마다 종류를 내 말로 정합니다.', evidence=f'{N["expect"]}단계에 적은 줄의 원문과 종류가 보이고, 기대 칸을 쓴 시각이 있습니다.',
                       hint=H('실행 전에 기대를 원문에서 적는다', '1단계에서 찾은 줄, `입출력_계약.md` 4절 「종류의 뜻」', 'AI 출력을 기대로 옮기지 않는다.' + xcols('기대_항목.csv'),
                              '`결과/기대_항목.csv`의 행', f'{N["expect"]}단계 원문 줄'),
                       differ='되짚기가 내 뜻과 다르면 고쳐 다시 되짚게 합니다.'),
        'prompt': dict(why='글이 길면 답이 잘리고 짧으면 조건과 대상이 갈라지며, 구조화 출력은 모양만 맞추므로 한 조각을 두 번 보내 검토된 구조와 견줘 요청 글을 굳힙니다.',
                       do=f'`결과/나누기.json`에 단위 · 글자 상한 · 「시험_조각」(핀 세척 줄 「파일:줄」)을, `결과/prompt.md`에 요청 글을 쓰고 단위의 까닭을 `{C}`에 적은 뒤 `{SHOW}`를 실행합니다.',
                       ask='어디서 끊을지와 무엇을 뽑게 할지 · 원문 그대로 · 하지 말 것 · 모르면 경고 · 답의 꼴을 정하고, 두 답이 SOP 구조와 다른 까닭을 묻습니다.',
                       evidence=f'{N["prompt"]}단계에 핀 세척 절차가 한 조각 안이고 보낼 요청 수가 남은 수 안이며, 두 답과 SOP 구조의 짝 표가 보입니다.',
                       hint=H('조각 단위와 요청 글을 정한다', '1단계 절 머리 수, 원문, 계약 「정할 자리」 · 「후보 하나」, `입력/sop.json`',
                              '조건과 대상이 갈라지지 않게, 원문에 없거나 번역한 것을 만들지 않게 한다. 모델을 부르는 명령은 내 터미널에서. 인용이 원문 여러 곳에 맞으면 줄을 정하지 못해 「찾지 못한 인용」이 된다', '`결과/나누기.json` · `결과/prompt.md` · 정한 것 한 줄', f'{N["prompt"]}단계 짝 표'),
                       differ='AI 채팅이 대신 실행하면 「[Errno 1] Operation not permitted」로 멈춥니다 — 내 터미널에서 실행합니다. 후보 표가 비면 요청 글에 답의 필드 이름을 직접 적었는지 봅니다. 「같은 요청은 2번까지」면 요청 글을 고칩니다.'),
        'main': dict(why='한 조각에서 맞은 요청 글도 다른 절 · 다른 문서에서는 빠뜨리거나 지어냅니다.',
                     do=f'「보낼_문서」에 핀 세척 · 조건 근거 문서와 다른 문서(정기 점검표 · 예비품 기준 · 보충 매뉴얼)를 적고 `{SHOW}`를 실행해, 기대와 다른 줄의 차이 종류와 다른 문서의 실제 누락 · 근거 없는 생성 수를 `{REC}`에 적습니다.',
                     ask='차이가 단위 · 요청 글 때문인지 모델 응답 때문인지 묻습니다.',
                     evidence=f'{N["main"]}단계에 문서마다 후보 · 잘린 답 · 후보 0개 조각 · 후보가 걸리지 않은 내용 줄, 기대 항목마다 맞음 · 누락이 보이고, 그 줄을 원문으로 가른 수가 기록에 있습니다.',
                     hint=H('후보를 기대와, 다른 문서 결과를 원문과 견준다', f'{N["main"]}단계, `결과/기대_항목.csv`, 원문', '기대를 결과에 맞추지 않는다. 글자 짝이 없다고 누락으로 세지 않는다. 같은 요청의 기록이 둘이면 두 답을 원문 줄과 견줘(빠진 줄 · 잘린 답 · 근거 없는 후보) 고르고 그 까닭을 기록에 적는다', '기록 두 표', '다른 줄 · 짝 없는 칸을 원문 줄로 연다'),
                     differ='「같은 요청의 기록이 … 개」면 「쓸_기록」에 고른 기록을 적습니다. 「길이 상한에서 잘린 답」이 핀 세척 조각이면 단위 · 상한을 줄여 다시 실행합니다(새 요청이라 상한에 셈).'),
        'rev1': dict(why='원문과 대조하지 않은 후보는 승인하지 않고, 사내 문서와 제조사 지침이 함께 말하면 머리말 · 문서 관리 기준으로 어느 쪽을 둘지 정합니다.',
                     do=f'`결과/검토_결정.csv`에 기대 줄의 결정 · 근거 · 까닭을(같은 결정은 줄 칸을 비운 규칙 한 행으로), 제조사 항목을 어떻게 둘지 `{C}`에 적고 `{SHOW}`로 봅니다.',
                     ask='제조사 지침이 사내 기준과 다르게 정한 것과 정하지 않은 것을 각각 어떻게 둘지 원문으로 정합니다.',
                     evidence=f'{N["rev1"]}단계에 결정 수와 기대 줄의 결정이 보이고, 채택 · 수정 · 제외마다 근거가 있습니다.',
                     hint=H('후보마다 결정과 근거를 남긴다', f'결과 화면 {N["main"]} · {N["rev1"]}단계, 원문, 문서 관리 기준', '원문과 대조하지 않은 후보를 채택하지 않는다.' + xcols('검토_결정.csv'), '결정 표 · 정한 것 한 줄', f'{N["rev1"]}단계 표'),
                     differ='같은 문장이 여러 곳이라 줄을 정하지 못한 인용은 결정 표에 그 줄을 적으면 검토자가 더한 후보가 됩니다.'),
        'rev2': dict(why='원문이 말하는 대상 · 때와 조건이 거는 대상 · 때가 같아야 그 원문이 그 조건의 근거입니다.',
                     do=f'`결과/조건_대조.csv`에 이 작업에 걸린 조건마다 근거 · 맞는 정도 · 까닭 · 요청할 것을 적고 고른 것을 `{C}`에 적은 뒤 `{SHOW}`로 봅니다. 조건표는 고치지 않습니다.',
                     ask='맞는 정도와, 근거를 못 찾은 조건에 무엇을 요청할지 정합니다.',
                     evidence=f'{N["rev2"]}단계에 조건마다 근거 원문 줄 · 맞는 정도 · 그 조건이 핀 세척을 제외한 지난 판정이 보입니다.',
                     hint=H('조건마다 근거를 잇고 맞는 정도를 정한다', '`입력/조건표.csv`, 결과 화면, 원문', '조건표 · 판정 결과를 바꾸지 않는다.' + xcols('조건_대조.csv'), '조건 대조 행 · 정한 것 한 줄', f'{N["rev2"]}단계 원문 줄'),
                     differ='「그 줄에 후보가 없음」이면 그 줄을 결정 표에 넣고 다시 실행합니다.'),
        'collect': dict(why='준비 · 금지 · 완료는 절차 밖 절이나 다른 문서에도 있어 모아 둡니다.',
                        do=f'`결과/역할.csv`에 계약 기본과 다르게 둘 종류 · 글자만 적고 `{SHOW}`로 `결과/선택작업_조건.json`의 항목과 sop_diff를 원문 줄로 확인합니다.',
                        ask='작업 전 확인 단계와 끝나지 않았을 때의 처리를 어느 항목에 둘지 정합니다.',
                        evidence=f'{N.get("collect")}단계에 준비 · 금지 · 완료 · 남은 질문 · sop_diff 수와 항목마다 인용이 보입니다.',
                        hint=H('카드에 넣을 조건을 모을 규칙을 정한다', '검토 결과, `입출력_계약.md` 6 · 7절', '승인한 후보만 넣는다.' + xcols('역할.csv'), '`결과/역할.csv`의 행', f'{N.get("collect")}단계 표'),
                        differ='「어느 행에도 맞지 않는 승인 후보」면 그 종류의 행을 더합니다.'),
        'save': dict(why=F.WHY_SAVE,
                     do=f'적어 둔 누락 하나를 판단 자리에서 고쳐 그 문서를 「다시_보낼_문서」에 적고 다시 실행해 센 수를 `{REC}`에 적고, 저장 뒤 폴더를 닫았다 다시 열어 `{SHOW}`를 실행하고 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
                     ask='확인하지 못한 점으로 무엇을 남길지 정합니다.', evidence='다시 연 뒤에도 단계가 같고, 결과 화면 마지막 단계의 check.py 출력에 「구조상 빠진 단계는 없습니다」가 있습니다.', cmd=SHOW,
                     hint=H('고친 판을 다시 세고 다시 열어 본다', f'결과 화면, `{REC}`', '원자료 · 응답 기록을 바꾸지 않는다. 이미 후보가 있는 문서는 그 판 그대로 두고, 고친 요청 글로 다시 보낼 문서만 「다시_보낼_문서」에 적는다(결과 화면 「후보를 만든 판」 칸으로 문서마다 본다)', '기록의 고친 점 · 다시 센 수 · 저장 기록', '다시 연 뒤 마지막 단계의 check.py 출력'),
                     differ='「완료 아님 — 남은 것:」 줄마다 남은 일을 채웁니다.'),
    }


def step_order(key):
    """단계 열쇠의 차례 — START 「진행 단계」 · 가이드 절 · lab_steps.STEPS가 같은 차례를 쓴다."""
    if key == 'practical-03-extract':
        return ['start', 'connect', 'expect', 'prompt', 'main', 'rev1', 'rev2', 'collect', 'save']
    return ['start', 'connect', 'expect', 'split', 'prompt', 'main', 'rev1', 'rev2', 'other', 'save']


def extract_steps(key):
    practical = key == 'practical-03-extract'
    N = {k: i for i, k in enumerate(step_order(key), 1)}
    judged, event = JUDGED[key], incident()
    base = FL.extract_files('나', '가', practical)
    chosen = FL.chosen('나', '가')
    xb = extract_blanks(key)
    def tog(name, text):
        return ghead(xb['결과/' + name], text)
    def cols(name):
        return ' 칸 — ' + xcol(name, practical)
    split0 = json.dumps({**json.loads(base['나누기.json']), '시험_조각': '', '보낼_문서': []}, ensure_ascii=False, indent=2) + '\n'
    split1 = json.dumps({**json.loads(base['나누기.json']), '보낼_문서': []}, ensure_ascii=False, indent=2) + '\n'

    def chosen_csv(idx):
        return chosen_upto(csv_body(FL.csv_text(F.CHOSEN_COLUMNS, [chosen[i] for i in idx])))
    rules_scope = '이 작업에 걸린 조건' if practical else '조건표의 조건'
    task_note = f' 확인한 작업과 그 줄을 `{REC}` 「이 사건의 작업」에 적습니다.' if practical else ''
    steps = [
        S('폴더 · 사건 · 문서 묶음 파악', '① 파악',
          f'터미널에서 `{SHOW}`를 실행해 결과 화면을 엽니다. 사건 경보({event})의 조치 후보와 핀 세척(`{TASK}`)이 걸린 관계, 문서 묶음의 판 · 상태 · 글자 방식을 보고, '
          'AI에게 파일을 바꾸지 말고 핀 세척 작업의 원문이 문서마다 어느 절 · 줄에 있는지 물어 그 줄을 직접 엽니다.' + task_note,
          '이 답을 쓰는 사람과 해결할 질문, 핀 세척이 즉시 완화가 아니라 근본 조치라는 근거 줄을 묻습니다.',
          '결과 화면 1단계에 사건 경보의 조치 후보 · 핀 세척이 걸린 관계 · 문서 표가 보입니다. ' + F.EVIDENCE_LOOK,
          H('사건과 문서 묶음의 모양을 파악하고 핀 세척 원문의 자리를 찾는다', f'결과 화면 1단계, `입력/{judged}` · `입력/sop.json`, `자료/`의 원문, START.md 「목표」',
            '파일을 바꾸지 않는다. 짚을 때는 파일:줄을 먼저 댄다', '문서마다 핀 세척 작업의 절 · 줄 목록', '짚은 줄을 내가 직접 연다'),
          cmd=SHOW, why=F.WHY_START + ' 판정 결과의 시각은 UTC라 한국 시각보다 9시간 이릅니다.',
          differ=F.DIFFER_LOOK),
        S('수업 모델 연결 확인', '① 파악',
          '`.env.example`을 복사해 이름을 `.env`로 바꾸고, 강의에서 받은 접속 세 줄을 그대로 붙여 넣어 저장합니다. 터미널에서 `python llm_client.py`를 실행해 연결을 확인합니다.',
          '키가 없으면 실습 폴더와 따로 받는 학생용 완성본 묶음으로 결과를 볼지 정합니다.',
          '「연결됨」 줄과 모델 이름 · 짧은 답이 나옵니다. 키를 채팅 · 다른 파일 · 기록에 붙이지 않았습니다.',
          H('수업 모델에 연결되는지 확인한다', '`.env.example`, 강의에서 받은 접속 세 줄', '키를 채팅 · 다른 파일 · 기록에 붙이지 않는다. `.env`는 내가 편집기에서 만든다',
            '`python llm_client.py`의 출력', '출력의 첫 줄과 모델 이름을 본다'),
          cmd='python llm_client.py',
          why='키는 이 폴더의 `.env`에만 둡니다 — 키가 새면 다른 사람이 내 한도로 모델을 부를 수 있고, 학생 AI는 폴더의 글을 읽어 답에 옮길 수 있습니다. 첫 요청은 모델 서버가 준비되느라 1분쯤 걸릴 수 있어 여기서 미리 한 번 보냅니다.',
          differ='「요청을 보내지 못했습니다」 뒤의 문장이 고칠 곳입니다. 받은 세 줄을 그대로 다시 붙여 넣고 저장한 뒤 다시 실행합니다.'),
        S('기대 항목 먼저', '② 요구',
          f'`결과/기대_항목.csv`에 핀 세척 작업(준비 · 방법 · 금지 · 완료 · 승인)의 원문 줄을 파일 · 줄 · 종류로 적고, `{REC}`에 목표 · 쓰는 사람 · 기대 칸을 쓴 시각을 적은 뒤 `{SHOW}`로 그 줄의 원문을 봅니다.' + F.REQ_AFTER,
          '줄마다 어느 종류(단계 · 시작 조건 · 금지 · 완료 · 기준값)인지 내 말로 정합니다.',
          f'결과 화면 {N["expect"]}단계에 내가 적은 줄의 원문이 보이고, 줄마다 종류가 있습니다. 기대 칸을 쓴 시각이 있습니다. AI의 되짚기가 내 뜻과 같고 바뀐 파일이 없습니다.',
          H('실행 전에 기대를 원문에서 적는다', f'1단계에서 찾은 핀 세척 줄, `입출력_계약.md` 4절 「종류의 뜻」', 'AI 출력을 기대로 옮기지 않는다.' + cols('기대_항목.csv'),
            '`결과/기대_항목.csv`의 행(파일 · 줄 · 종류)', f'`{SHOW}` — {N["expect"]}단계의 원문 줄을 읽는다'),
          cmd=SHOW, why='판정 기법은 기대 결과를 원문에서 먼저 적고 실행 결과와 견주는 것입니다. 모델의 답을 본 뒤에 기대를 적으면 빠진 것과 지어낸 것이 기대에 섞여 보이지 않습니다.',
          differ=F.DIFFER_REQ.format(rec='결과/기대_항목.csv'),
          answer=A('핀 세척 두 절 — 사내 현행 매뉴얼 HM-8.7의 근본 조치 문장 · SOP-COOL-14 세 단계와, 제조사 지침 T-7.1 여섯 단계의 줄입니다.',
                   F.paste('결과/기대_항목.csv', tog('기대_항목.csv', base['기대_항목.csv'])))),
        S('판단① 문서를 나누는 단위', '③ 계획 · 판단',
          f'`결과/나누기.json`에 단위 · 글자 상한을 정하고 그 까닭을 `{F.CHOSEN_FILE}`에 한 줄 적은 뒤 `{SHOW}`로 조각 목록과 보낼 요청 수를 봅니다.',
          '문서를 어떤 단위(절 · 절차 · 쪽 · 글자)로 나눌지와 그 까닭을 정합니다. AI에게는 단위마다 핀 세척 절이 몇 조각에 걸치는지, 요청 수가 몇이 되는지 묻습니다.',
          '결과 화면 4단계에 문서마다 조각 수와 조각 목록(줄 범위)이 보이고, 핀 세척 절차가 한 조각 안에 있는지 말할 수 있습니다. 보낼 요청 수가 남은 수 안입니다.',
          H('문서를 요청에 보낼 조각으로 끊을 단위를 정한다', '결과 화면 1단계의 절 머리 수, 원문의 절 · 절차 · 쪽 머리, `입출력_계약.md` 「정할 자리」', '조각 경계에서 조건과 그 대상이 갈라지지 않게 한다. 정하는 것은 내가 하고 AI는 단위마다 결과를 설명한다',
            '`결과/나누기.json`의 단위 · 글자 상한, `결과/정한_것.csv` 한 줄', f'`{SHOW}` — 4단계의 핀 세척 조각 줄 범위'),
          cmd=SHOW, why=WHY_SPLIT, differ='핀 세척 절차가 두 조각으로 갈라지거나 보낼 요청 수가 남은 수보다 많으면 단위나 상한을 바꿔 다시 봅니다.',
          answer=A('강사 판은 절 머리에서 끊고 1,000자 안에서 이어진 절을 묶는 단위입니다(조각 33개, 핀 세척 절차가 한 조각 안).',
                   F.paste('결과/나누기.json', split0), F.paste(F.CHOSEN_FILE, chosen_csv([2]))),
          ),
        S('판단② 요청 글과 한 조각', '④ 구현 · 판단',
          f'`결과/prompt.md`에 수업 모델에 보낼 요청 글을 쓰고, `결과/나누기.json` 「시험_조각」에 먼저 보내 볼 핀 세척 줄(「파일:줄」)을 적은 뒤 `{SHOW}`를 실행합니다 — 그 조각을 보내고 같은 요청을 한 번 더 보내, '
          '두 답의 후보를 받은 SOP 구조의 같은 작업 항목과 견줍니다. 다르면 요청 글을 고쳐 다시 실행합니다.',
          '무엇을 뽑게 할지 · 원문 그대로 · 하지 말 것 · 모르면 경고 · 답의 꼴을 내 말로 정하고, 받은 답이 SOP 구조와 다른 곳이 요청 글 때문인지 모델 응답 때문인지 묻습니다.',
          '결과 화면 5단계에 두 답의 후보 표(종류 · 절 · 줄 · 찾은 방법 · 인용)와 받은 SOP 구조 항목과의 짝이 보이고, 다른 곳을 원문 줄로 말할 수 있습니다. 요청 글을 굳혔습니다.',
          H('한 조각에서 계약 꼴 후보를 받아 낼 요청 글을 짠다', '`입출력_계약.md` 「후보 하나」 · 「종류의 뜻」, 핀 세척 조각, `입력/sop.json`', '원문에 없는 것을 만들지 않게, 원문을 번역하거나 고쳐 쓰지 않게 한다. 모델을 부르는 명령은 내 터미널에서 실행한다. 인용이 원문 여러 곳에 맞으면 줄을 정하지 못해 「찾지 못한 인용」이 된다',
            '`결과/prompt.md`, 나누기.json 「시험_조각」', f'`{SHOW}` — 5단계의 두 답과 SOP 구조 짝 표'),
          cmd=SHOW, why=WHY_PROMPT,
          differ=('결과 화면의 후보 표가 비고 「종류를 알 수 없는 후보」 · 「확인할 수 없어」 같은 경고 줄만 있으면, 모델은 이 폴더의 파일(계약 등)을 읽지 못하므로 요청 글에 답의 필드 이름과 값을 직접 적었는지 봅니다. 터미널에 「모델 서버에 닿지 못했습니다」가 나오면 인터넷 연결을 보고 1분쯤 뒤 다시 실행합니다. AI 채팅이 대신 실행했다면 그 실행 환경은 바깥 연결이 막혀 「[Errno 1] Operation not permitted」로 멈춥니다 — 같은 명령을 내 터미널에서 실행합니다. '
                  '「같은 요청은 2번까지」가 나오면 이미 두 번 받은 것이니 요청 글을 고쳐야 새 요청이 됩니다. ' + F.FIX_LOOP),
          answer=A('강사 판 요청 글 — 다섯 종류의 뜻, 원문 그대로 · 번역하지 않음, 같은 문장이 여러 곳이면 앞뒤를 붙여 한 곳만, 판단할 것은 경고로, 답의 꼴(JSON 하나)을 적습니다. 시험 조각은 사내 현행 매뉴얼의 핀 세척 1단계 줄입니다.',
                   F.paste('결과/prompt.md', base['prompt.md']), F.paste('결과/나누기.json', split1), apply={'결과/prompt.md': base['prompt.md'], '결과/나누기.json': split1, F.CHOSEN_FILE: chosen_csv([2, 3])})),
        S('주 대상 문서에 실행하고 기대와 대조', '⑤ 대조',
          f'`결과/나누기.json` 「보낼_문서」에 핀 세척 원문과 {rules_scope}의 근거를 가진 문서를 적고 `{SHOW}`를 실행해 후보 파일을 만든 뒤, 기대 항목과 다른 줄 두세 개의 차이 종류(누락 · 부정 빠짐 · 단위 · 수치 오류 · 다른 절 연결 · 근거 없는 생성)를 `{REC}` 「기대와 다른 줄」에 적습니다.',
          '기대와 다른 줄이 나눈 단위 · 요청 글의 문제인지 모델 응답의 문제인지 묻습니다.',
          '결과 화면 6단계에 문서마다 후보 · 찾지 못한 인용 · 잘린 답 수와, 기대 항목마다 맞음 · 종류 다름 · 줄 못 정함 · 누락이 보입니다. 다른 줄의 차이 종류가 기록에 있습니다.',
          H('주 대상 문서의 후보를 기대와 견준다', '결과 화면 6단계, `결과/기대_항목.csv`, 원문', '기대를 결과에 맞춰 고치지 않는다. 모델을 부르는 명령은 내 터미널에서 실행한다. 같은 요청의 기록이 둘이면 두 답을 원문 줄과 견줘(빠진 줄 · 잘린 답 · 근거 없는 후보) 고르고 그 까닭을 기록에 적는다',
            f'`{REC}` 「기대와 다른 줄」 표', '다른 줄마다 원문 줄을 연다'),
          cmd=SHOW, why=WHY_MAIN,
          differ=(f'「같은 요청의 기록이 … 개 — 검토에 쓸 기록 파일 이름을 적습니다」로 멈추면 5단계에서 같은 조각을 두 번 받은 것이니, 두 답을 견준 결과로 `결과/나누기.json` 「쓸_기록」에 고른 기록을 적습니다. 「후보 0」인 문서가 있으면 경고 칸의 글로 까닭을 봅니다. 「길이 상한에서 잘린 답」 칸이 0이 아니면 그 조각의 뒷부분 후보는 없습니다 — 핀 세척 조각이면 단위나 글자 상한을 줄여(새 요청이 되어 상한에 셉니다) 다시 실행하고, 아니면 「확인하지 못한 점」에 적습니다. '
                  f'「보낼 요청 …개가 … 남은 …개보다 많습니다」로 멈추면 보낼 문서를 줄이거나 조각을 크게 묶습니다.'),
          answer=A('주 대상은 사내 현행 · 옛 판 · 개정 요청 매뉴얼, 스캔본, 설비안전규정, 제조사 지침입니다(나머지 다른 문서는 다른 문서 단계에서).',
                   F.paste('결과/나누기.json', json.dumps({**json.loads(base['나누기.json']), '보낼_문서': FL.MAIN_DOCS}, ensure_ascii=False, indent=2) + '\n'))),
        S('판단③ 검토 — 사내 문서와 제조사 지침', '④ 판단',
          f'`결과/검토_결정.csv`에 기대 항목의 줄마다 결정(채택 · 수정 · 제외 · 보류) · 근거 · 까닭을 적고(같은 결정이 이어지는 줄은 줄 칸을 비운 판단 규칙 한 행으로), 제조사 지침이 사내 기준과 다르게 정하거나 정하지 않은 줄을 어떻게 둘지 `{F.CHOSEN_FILE}`에 적은 뒤 `{SHOW}`로 검토 결과를 봅니다.',
          '제조사 지침의 항목 가운데 사내 기준이 정하지 않은 것과 다르게 정한 것을 각각 어떻게 둘지 정합니다. AI가 고를 것을 내놓거나 「권장」을 붙여도 원문 머리말 · 문서 관리 기준 줄을 열어 내 말로 정합니다.',
          f'결과 화면 {N["rev1"]}단계에 검토 결과 파일마다 결정 수와, 기대 항목 줄의 결정이 보입니다. 채택 · 수정 · 제외마다 원문 근거가 있고, 원문과 대조하지 않은 후보는 보류입니다.',
          H('핀 세척 작업 후보마다 결정과 근거를 남긴다', f'결과 화면 {N["main"]} · {N["rev1"]}단계, 원문, `자료/문서_목록.csv`, 문서 관리 기준', '원문과 대조하지 않은 후보를 채택하지 않는다.' + cols('검토_결정.csv'),
            '`결과/검토_결정.csv`의 행, `결과/정한_것.csv` 한 줄', f'`{SHOW}` — {N["rev1"]}단계 표, 결정 몇 개를 원문 줄로'),
          cmd=SHOW, why=WHY_REV1, differ='빨간 칸에 결정 표의 행 번호와 까닭이 나오면 그 행을 고칩니다. 같은 문장이 여러 곳에 있어 코드가 줄을 정하지 못한 인용은 결정 표에 그 줄을 적으면 검토자가 더한 후보가 됩니다.',
          answer=A('갈래 가(사내 기준이 정하지 않은 제조사 항목은 보류 — 소유 부서에 묻는다) · 나(까닭을 적고 채택) 가운데 하나를 고르고 근거를 적습니다. 사내와 다르게 정한 항목(저압수)은 두 갈래 모두 사내 기준을 따라 뺍니다.',
                   F.paste('결과/검토_결정.csv', tog('검토_결정.csv', FL.csv_text(['파일', '줄', '종류', '결정', '근거', '까닭', '고친_인용'], FL.decisions('가', True)))),
                   F.paste('결과/검토_결정.csv', tog('검토_결정.csv', FL.csv_text(['파일', '줄', '종류', '결정', '근거', '까닭', '고친_인용'], FL.decisions('나', True)))),
                   apply={'결과/검토_결정.csv': tog('검토_결정.csv', base['검토_결정.csv']), F.CHOSEN_FILE: chosen_csv([2, 3, 1])})),
        S(f'판단④ {rules_scope}의 근거', '④ 판단',
          f'`결과/조건_대조.csv`에 {rules_scope}(`rule_id`)마다 근거 원문(파일:줄) · 맞는 정도 · 까닭 · 요청할 것을 적고 고른 것을 `{F.CHOSEN_FILE}`에 적은 뒤 `{SHOW}`로 근거 원문과 그 조건이 걸었던 지난 판정을 봅니다. 조건표 · 판정 결과는 고치지 않습니다.',
          '원문이 말하는 대상 · 때와 조건이 거는 대상 · 때가 같은지 견주어 맞는 정도를 정하고, 근거 원문을 찾지 못한 조건은 무엇을 요청할지 정합니다.',
          f'결과 화면 {N["rev2"]}단계에 조건마다 근거 원문 줄 · match · 그 조건이 `{TASK}`를 제외한 지난 판정이 보이고, 아직 근거 대조가 없는 조건이 남지 않았습니다.',
          H(f'{rules_scope}마다 근거 원문을 잇고 맞는 정도와 까닭을 적는다', f'`입력/조건표.csv`(rule_id · reason · source_section), 결과 화면 1 · {N["rev2"]}단계, 원문', '조건표 · 판정 결과를 바꾸지 않는다 — 바꿀 것은 요청할 것 칸에.' + cols('조건_대조.csv'),
            '`결과/조건_대조.csv`의 행, `결과/정한_것.csv` 한 줄', f'`{SHOW}` — {N["rev2"]}단계의 원문 줄'),
          cmd=SHOW, why=WHY_REV2, differ='「그 줄에 후보가 없음」이 나오면 그 줄을 검토_결정.csv에 넣어 검토 결과에 후보를 둔 뒤 다시 실행합니다.',
          answer=A('갈래 가(그 조항을 R4 전체의 근거로 일치) · 나(원문 범위가 운전 중 조치라 핀 세척의 R4는 불일치) · 다(해석 받을 때까지 보류) 가운데 하나를 고르고 근거를 적습니다. 원문이 없는 조건은 원문 없음과 원본 요청입니다.',
                   *[F.paste('결과/조건_대조.csv', tog('조건_대조.csv', FL.csv_text(['rule_id', '근거', 'match', '까닭', '요청할_것'], FL.rules(p5, practical)))) for p5 in ('가', '나', '다')],
                   apply={'결과/조건_대조.csv': tog('조건_대조.csv', base['조건_대조.csv']), F.CHOSEN_FILE: chosen_csv([2, 3, 1, 0])})),
        S('다른 문서에 다시 적용', '⑤ 대조',
          f'`결과/나누기.json` 「보낼_문서」에 정기 점검표 · 예비품 기준 · 보충 매뉴얼을 더하고 `{SHOW}`를 실행해, 문서마다 후보 수와 받은 SOP 구조 ↔ 사내 현행 매뉴얼 후보의 짝 표를 봅니다. 짝이 없는 칸 두세 개는 원문 줄을 열어 실제 누락인지 보고 `{REC}` 「다른 문서에 적용」에 적습니다.',
          '한 문서에 맞춘 단위 · 요청 글이 다른 문서에서 놓치거나 지어내는 것이 무엇인지 묻습니다.',
          f'결과 화면 9단계에 문서마다 후보 · 찾지 못한 인용 수와 짝 표가 보이고, `{REC}` 「다른 문서에 적용」에 실제 누락 · 근거 없는 생성 수가 있습니다.',
          H('같은 단위 · 요청 글을 다른 문서에 적용해 누락 · 근거 없는 생성을 센다', '결과 화면 9단계, 원문, `입력/sop.json`', '원문에 맞추려고 원문을 바꾸지 않는다. 글자 짝이 없다고 누락으로 세지 않는다 — 원문 줄로 본다',
            f'`{REC}` 「다른 문서에 적용」 표', '짝 없는 칸 두세 개를 원문 줄로 연다'),
          cmd=SHOW, why=WHY_OTHER,
          differ='센 수가 원문과 맞지 않아 보이면 어느 문서 · 절에서 다른지 AI에게 짚게 해 기록에 적습니다. 고치는 일은 마지막 단계에서 합니다.',
          answer=A('보낼 문서에 나머지 셋을 더하면 문서 관리 기준을 뺀 아홉 문서가 됩니다.', F.paste('결과/나누기.json', base['나누기.json']))),
    ]
    if practical:
        steps.append(S('판단⑤ 이 작업의 준비 · 금지 · 완료 모으기', '④ 판단',
                       f'`결과/역할.csv`에 승인 후보의 종류(와 인용에 든 글자)를 이 작업의 준비 · 금지 · 완료 가운데 어디에 둘지 적고 `{SHOW}`로 `결과/선택작업_조건.json`을 봅니다. 항목 두세 개를 원문 줄로 열고, 받은 SOP 구조와 다른 곳(sop_diff)을 확인합니다.',
                       '절차의 단계 · 절차 밖 절 · 다른 문서의 조건 가운데 이 작업의 준비 · 금지 · 완료로 둘 것을 정합니다(방법 단계는 넣지 않고, 첫 단계가 작업 전 확인이면 준비로).',
                       f'결과 화면 {N.get("collect")}단계에 준비 · 금지 · 완료 · 남은 질문 · sop_diff 수와 항목 표가 보이고, 항목마다 원문 인용이 있습니다.',
                       H('작업 확인 카드에 들어갈 조건을 검토 결과에서 모을 규칙을 정한다', f'검토 결과(결과 화면 {N["rev1"]}단계), `입출력_계약.md` 6 · 7절, `입력/sop.json`', '승인한 후보만 항목으로 넣는다. 승인하지 않은 것은 남은 질문으로 둔다.' + (cols('역할.csv') if practical else ''),
                         '`결과/역할.csv`의 행', f'`{SHOW}` — {N.get("collect")}단계 표, 항목 두세 개를 원문 줄로'),
                       cmd=SHOW, why='작업 전에 확인할 조건은 그 작업의 절차 안에만 있지 않습니다 — 시작 전 조건 · 금지 방법 · 완료 확인이 다른 절이나 다른 문서에 있을 수 있어, 모아 두어야 작업자가 한 번에 되짚습니다.',
                       differ='「어느 행에도 맞지 않는 승인 후보」가 나오면 그 종류의 행을 더합니다.',
                       answer=A('종류마다 한 행, 작업 전 정지 · 잠금 · 대기 · 점검 단계는 준비, 막힘이 남을 때의 교체는 완료로 두는 행을 앞에 둡니다.', F.paste('결과/역할.csv', tog('역할.csv', base['역할.csv'])))))
    steps.append(S('고침 · 저장하고 다시 열기', '⑥ 고침 · ⑦ 저장 · 다시 열기',
                   f'앞에서 적어 둔 누락 · 근거 없는 생성 가운데 하나를 판단 자리(나누는 단위 · 요청 글 · 결정 표)에서 고쳐, 그 문서를 `결과/나누기.json` 「다시_보낼_문서」에 적고 다시 실행해 다시 센 수를 `{REC}`에 적습니다. 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 `{SHOW}`를 다시 실행하고, `{REC}` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
                   '무엇을 고쳤고, 확인하지 못한 점으로 무엇을 남길지 정합니다.',
                   f'다시 연 뒤에도 결과 화면의 단계가 같고, 마지막 단계의 `python check.py` 출력에 「구조상 빠진 단계는 없습니다」가 있습니다. `{REC}`의 고친 점 · 다시 센 수 · 저장 기록이 채워져 있습니다.',
                   H('고친 판을 다시 세고, 저장해 다시 열어 같은지 본다', f'결과 화면, `{REC}`', '검사 기준 · 원자료 · 응답 기록을 바꾸지 않는다. 확인하지 못한 것은 확인하지 못했다고 적는다. 이미 후보가 있는 문서는 그 판 그대로 두고, 고친 요청 글로 다시 보낼 문서만 「다시_보낼_문서」에 적는다(결과 화면 「후보를 만든 판」 칸으로 문서마다 본다)',
                     f'`{REC}`의 고친 점 · 다시 센 수 · 저장 기록', '다시 연 뒤 결과 화면과 check.py 출력을 앞과 견준다'),
                   cmd=f'{SHOW}\npython check.py', why=F.WHY_SAVE + ' 구조 검사는 모양만 보고, 무엇을 채택할지는 원문 대조로 판단합니다.',
                   differ='「완료 아님 — 남은 것:」 아래 줄마다 남은 일이 하나씩 적혀 있습니다. 줄마다 어느 파일인지 보고 채운 뒤 다시 실행합니다.'))
    if practical:
        D = dict(zip(['start', 'connect', 'expect', 'split', 'prompt', 'main', 'rev1', 'rev2', 'other', 'collect', 'save'], steps))
        D['prompt'] = S('판단① 나누는 단위와 요청 글 — 한 조각으로 시험', '③ 계획 · ④ 구현 · 판단',
          f'`결과/나누기.json`에 단위 · 글자 상한과 「시험_조각」(먼저 보내 볼 핀 세척 줄 「파일:줄」)을, `결과/prompt.md`에 수업 모델에 보낼 요청 글을 쓰고 단위의 까닭을 `{F.CHOSEN_FILE}`에 적은 뒤 '
          f'`{SHOW}`를 실행합니다 — 조각 목록 · 보낼 요청 수와, 시험 조각을 두 번 보낸 두 답의 후보 ↔ 받은 SOP 구조의 같은 작업 항목이 보입니다. 다르면 요청 글을 고쳐 다시 실행합니다.',
          '어디서 끊을지(절 · 절차 · 쪽 · 글자)와 무엇을 뽑게 할지 · 원문 그대로 · 하지 말 것 · 모르면 경고 · 답의 꼴을 내 말로 정하고, 두 답이 SOP 구조와 다른 곳이 요청 글 때문인지 모델 응답 때문인지 묻습니다.',
          f'결과 화면 {N["prompt"]}단계에 핀 세척 절차가 한 조각 안에 있고 보낼 요청 수가 남은 수 안이며, 두 답의 후보 표와 SOP 구조 짝 표가 보입니다. 다른 곳을 원문 줄로 말할 수 있고, 요청 글을 굳혔습니다.',
          H('조각 단위를 정하고 한 조각에서 계약 꼴 후보를 받아 낼 요청 글을 짠다', '결과 화면 1단계의 절 머리 수, 원문, `입출력_계약.md` 「정할 자리」 · 「후보 하나」 · 「종류의 뜻」, `입력/sop.json`',
            '조각 경계에서 조건과 그 대상이 갈라지지 않게, 원문에 없는 것을 만들거나 번역하지 않게 한다. 모델을 부르는 명령은 내 터미널에서 실행한다',
            '`결과/나누기.json` · `결과/prompt.md`, `결과/정한_것.csv` 한 줄', f'`{SHOW}` — {N["prompt"]}단계의 조각 줄 범위 · 두 답 짝 표'),
          cmd=SHOW, why=WHY_SPLIT.split('. ')[0] + '. ' + WHY_PROMPT.split('. ')[1],
          differ=('후보 표가 비고 경고 줄만 있으면 모델은 이 폴더의 파일을 읽지 못하므로 요청 글에 답의 필드 이름과 값을 직접 적었는지 봅니다. '
                  'AI 채팅이 대신 실행하면 「[Errno 1] Operation not permitted」로 멈춥니다 — 같은 명령을 내 터미널에서 실행합니다. 「같은 요청은 2번까지」가 나오면 요청 글을 고쳐야 새 요청이 됩니다. '
                  '핀 세척 절차가 두 조각으로 갈라지면 단위나 상한을 바꿉니다.'),
          answer=A('강사 판은 절 머리에서 끊고 1,000자 안에서 이어진 절을 묶는 단위(조각 33개)와, 다섯 종류의 뜻 · 원문 그대로 · 판단할 것은 경고로 · 답의 꼴(JSON 하나)을 적은 요청 글입니다. 시험 조각은 사내 현행 매뉴얼의 핀 세척 1단계 줄입니다.',
                   F.paste('결과/나누기.json', split1), F.paste('결과/prompt.md', base['prompt.md']),
                   apply={'결과/prompt.md': base['prompt.md'], '결과/나누기.json': split1, F.CHOSEN_FILE: chosen_csv([2, 3])}))
        D['main'] = S('문서 묶음에 실행하고 기대 · 다른 문서와 대조', '⑤ 대조',
          f'`결과/나누기.json` 「보낼_문서」에 핀 세척 원문 · 이 작업에 걸린 조건의 근거를 가진 문서와 다른 문서(정기 점검표 · 예비품 기준 · 보충 매뉴얼)를 적고 `{SHOW}`를 실행합니다. '
          f'기대 항목과 다른 줄 두세 개의 차이 종류(누락 · 부정 빠짐 · 단위 · 수치 오류 · 다른 절 연결 · 근거 없는 생성)를 `{REC}` 「기대와 다른 줄」에, '
          f'받은 SOP 구조 ↔ 사내 현행 매뉴얼 후보의 짝 없는 칸 두세 개를 원문 줄로 열어 본 실제 누락 · 근거 없는 생성 수를 「다른 문서에 적용」에 적습니다.',
          '기대와 다른 줄이 나눈 단위 · 요청 글의 문제인지 모델 응답의 문제인지, 다른 문서에서 놓치거나 지어낸 것이 무엇인지 묻습니다.',
          f'결과 화면 {N["main"]}단계에 문서마다 후보 · 찾지 못한 인용 · 잘린 답 수, 기대 항목마다 맞음 · 종류 다름 · 줄 못 정함 · 누락, 짝 표가 보이고, 기록 두 표가 있습니다.',
          H('문서 묶음의 후보를 기대와, 다른 문서의 결과를 원문과 견준다', f'결과 화면 {N["main"]}단계, `결과/기대_항목.csv`, 원문, `입력/sop.json`',
            '기대를 결과에 맞춰 고치지 않는다. 글자 짝이 없다고 누락으로 세지 않는다 — 원문 줄로 본다. 모델을 부르는 명령은 내 터미널에서 실행한다',
            f'`{REC}` 「기대와 다른 줄」 · 「다른 문서에 적용」 표', '다른 줄 · 짝 없는 칸마다 원문 줄을 연다'),
          cmd=SHOW, why=WHY_MAIN.split('. ')[0] + '. ' + WHY_OTHER.split('. ')[1],
          differ=(f'「같은 요청의 기록이 … 개」로 멈추면 시험 조각을 두 번 받은 것이니 두 답을 견준 결과로 `결과/나누기.json` 「쓸_기록」에 고른 기록을 적습니다. '
                  '「길이 상한에서 잘린 답」이 0이 아니면 그 조각의 뒷부분 후보는 없습니다 — 핀 세척 조각이면 단위나 글자 상한을 줄여(새 요청이라 상한에 셈) 다시 실행하고, 아니면 「확인하지 못한 점」에 적습니다. '
                  '「보낼 요청 …개가 … 남은 …개보다 많습니다」로 멈추면 조각을 크게 묶습니다.'),
          answer=A('보낼 문서는 문서 관리 기준을 뺀 아홉 문서입니다.', F.paste('결과/나누기.json', base['나누기.json'])))
        steps = [D[k] for k in step_order(key)]
        steps = [dict(s_, **PX(N, judged, xcols=lambda n: ' 칸 — ' + xcol(n, True)).get(k, {})) for k, s_ in zip(step_order(key), steps)]
    if len(steps) != len(N):
        raise RuntimeError(f'단계 {len(steps)}개 ≠ 단계 차례 {len(N)}개')
    return steps, N


# ───────────── 검사기(구조만 — 의미 정답은 판정하지 않는다, K-7) ─────────────
CHECKER = r'''"""결과/의 후보 파일 · 검토 결과 · 응답 기록 짝과 검토_기록.md 칸의 구조 검사. 생성 · 수정 · 네트워크 접속을 하지 않는다.
후보의 인용이 짝지은 응답 기록의 답 글에 있는지(글자 · 숫자만 남겨 소문자로 비교)도 본다 — 답 글에 있다고 원문과 뜻이 맞는 것은 아니다.
어떤 후보가 맞는지, 빠진 지식, 어느 원문을 근거로 둘지는 판정하지 않는다 — 의미와 질문별 답은 원자료와 따로 대조한다.
사용:
  python check.py                                   단계별 상태(무엇이 있고 무엇이 비었는지)
  python check.py 결과/후보/<파일>.json [...]         파일별 계약 검사(후보 파일 · 검토 결과 파일)
"""
from pathlib import Path
import csv, hashlib, io, json, re, sys

HERE = Path(__file__).resolve().parent
RESULT = HERE / '결과'
JUDGED = '__JUDGED__'
PRACTICAL = __PRACTICAL__
TASK = '__TASK__' if PRACTICAL else None          # 실전반: 이 사건의 작업 — 조건 근거 대조는 이 작업에 걸린 조건만 본다
SENT = '모델 서버'
PASTED = '채팅으로 받음'
KINDS = {'step', 'precondition', 'prohibition', 'completion', 'unit_value'}
COMPARATORS = {None, '>=', '>', '<=', '<', '=', 'range', '±'}
STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}
MATCH = {'일치', '불일치', '원문 없음', '보류'}
TOP = ['doc_id', 'rev', 'doc_status', 'source_file', 'source_sha256', 'encoding', 'extractor', 'generated_at', 'model_run', 'candidates', 'unlocated']
REQUIRED = ['id', 'section', 'procedure', 'kind', 'text', 'quote', 'quote_match', 'line_start', 'line_end', 'refs', 'status']
FOOTER = re.compile(r'^-\s*(\S+)\s*-$')
LANG = re.compile(r'^\s*(?:\d+\.\s*)?(EN|KO):')
END = '의미와 질문별 답은 원자료와 따로 대조합니다.'


def squash(text):
    """글자 · 숫자만 남기고 소문자로 — 계약 「인용」의 normalized 비교."""
    return ''.join(c for c in str(text).lower() if c.isalnum())


def reply_strings(record):
    """응답 기록의 답 글에서 비교할 글들 — 답 글 그대로와, 답 글 안 JSON(처음 { 부터 끝 } 까지)을 풀어 낸 글 값 전부."""
    raw = str(record.get('response_text') or '')
    out = [raw]
    start, end = raw.find('{'), raw.rfind('}')
    if 0 <= start < end:
        try:
            stack = [json.loads(raw[start:end + 1])]
        except ValueError:
            stack = []
        while stack:
            x = stack.pop()
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                stack += list(x.values())
            elif isinstance(x, list):
                stack += x
    return out


def in_replies(quote, records):
    """인용 전체(여러 줄이면 모든 줄)가 응답 기록들의 답 글 한 곳에 있는가 — 글자 · 숫자만 남겨 소문자로 비교한다."""
    key = squash(quote)
    return bool(key) and any(key in squash(s) for r in records for s in reply_strings(r))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_rows(path):
    lines = [x for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def register():
    return {r['파일']: r for r in csv_rows(HERE / '자료/문서_목록.csv') if r.get('파일')}


def basis(name):
    mine = RESULT / '내_입력' / name
    return mine if mine.is_file() else HERE / '입력' / name


def rule_ids():
    """검토 결과의 rule_links가 받는 규칙 id — 기준 조건표의 rule_id와, 제공 · 기준 조건표의 출처 칸에 적힌 규칙 id."""
    ids = set()
    for path in {basis('조건표.csv'), HERE / '입력/조건표.csv'}:
        for r in csv_rows(path):
            if path == basis('조건표.csv'):
                ids.add(r.get('rule_id'))
            ids |= set(re.findall(r'rule:[a-z0-9-]+', r.get('source_section') or ''))
    return ids - {None, ''}


def mark():
    path = RESULT / '폴더_표지.txt'
    return path.read_text(encoding='utf-8').strip() if path.is_file() else None


def locate(text, quote):
    """(정확히 찾힌 수, 글자 · 숫자 비교로 찾힌 수) — 파일 전체에서."""
    return text.count(quote), squash(text).count(squash(quote)) if squash(quote) else 0


def check(path):
    errors, notes = [], []
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        return ['최상위가 객체가 아닙니다.'], notes
    missing = [k for k in TOP if k not in data]
    if missing:
        return [f'최상위 필드 없음: {missing}'], notes
    source = HERE / '자료' / str(data['source_file'])
    if not source.is_file():
        return [f'자료/{data["source_file"]} 파일이 없습니다.'], notes
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != data['source_sha256']:
        errors.append('source_sha256이 자료/의 파일과 다릅니다(다른 파일을 읽었거나 해시를 지어냈음).')
    row = register().get(data['source_file'])
    if row is None:
        errors.append('자료/문서_목록.csv에 없는 파일입니다.')
    else:
        notes.append(f'문서 목록: {row["문서 식별자"]} {row["판"]}판 · 상태 {row["상태"]}')
        for key, col in [('doc_id', '문서 식별자'), ('rev', '판'), ('doc_status', '상태'), ('source_sha256', 'SHA-256')]:
            if str(data[key]) != row[col]:
                errors.append(f'{key} {data[key]!r}가 문서 목록의 {col} {row[col]!r}와 다릅니다.')
    try:
        text = raw.decode(str(data['encoding']))
    except (LookupError, UnicodeDecodeError) as e:
        return errors + [f'encoding {data["encoding"]!r}로 원문을 읽지 못했습니다({e.__class__.__name__}).'], notes
    if '�' in text:
        errors.append(f'encoding {data["encoding"]!r}로 읽은 원문에 깨진 글자(�)가 있습니다.')
    lines = text.splitlines()
    bilingual = any(LANG.match(x) for x in lines)
    scanned = row is not None and '스캔본' in row['상태']
    # 응답 기록 짝
    here = mark()
    runs = data['model_run'] if isinstance(data['model_run'], list) else []
    if not runs:
        errors.append('model_run이 비어 있습니다 — 후보 파일은 응답 기록에서 만듭니다.')
    paired = []
    for run in runs:
        rec_path = HERE / str(run.get('record', ''))
        if not run.get('record') or not rec_path.is_file():
            errors.append(f'model_run의 응답 기록이 없습니다: {run.get("record")!r}')
            continue
        rec = json.loads(rec_path.read_text(encoding='utf-8'))
        if rec.get('usable') is False:
            errors.append(f'{run.get("record")}: 쓸 내용이 없는 답의 기록입니다(usable false — {rec.get("note")}) — 이 기록으로 후보를 만들지 않습니다.')
        else:
            paired.append(rec)
        for key in ['request_hash', 'model', 'method']:
            if run.get(key) != rec.get(key):
                errors.append(f'model_run {run.get("record")}: {key} {run.get(key)!r}가 응답 기록의 {rec.get(key)!r}와 다릅니다.')
        if not rec.get('model') or not rec.get('received_at'):
            errors.append(f'{run.get("record")}: 응답 기록에 model · 받은 시각이 없습니다.')
        if here is not None and rec.get('folder_mark') != here:
            errors.append(f'{run.get("record")}: 다른 폴더의 응답 기록입니다(기록의 폴더 표지 {rec.get("folder_mark")!r}, 이 폴더 {here!r}) — '
                          '후보는 이 폴더에서 수업 모델을 불러 받은 답으로 만듭니다.')
        if run.get('reused_from') is not None:
            errors.append(f'model_run {run.get("record")}: reused_from {run.get("reused_from")!r} — 다른 폴더의 응답 기록으로는 후보를 만들지 않습니다.')
        if rec.get('method') == PASTED:
            notes.append(f'{run.get("record")}: 채팅으로 받은 답 — 수업 모델을 부른 기록으로 세지 않습니다.')
    if here is None and len({str(r.get('folder_mark')) for r in paired}) > 1:
        errors.append('결과/폴더_표지.txt가 없는데 짝지은 응답 기록의 폴더 표지가 여럿입니다 — 여러 폴더의 응답 기록을 섞었습니다.')
    reviewed = 'review' in data
    added = {(m.get('kind'), str(m.get('quote')), m.get('line_start')) for m in data.get('missing', []) if isinstance(m, dict) and m.get('added') is True} if reviewed else set()
    seen, dup, cands = set(), set(), {}
    for i, c in enumerate(data['candidates'] if isinstance(data['candidates'], list) else []):
        where = c.get('id', f'#{i}') if isinstance(c, dict) else f'#{i}'
        if not isinstance(c, dict):
            errors.append(f'{where}: 후보가 객체가 아님')
            continue
        miss = [k for k in REQUIRED if k not in c]
        if miss:
            errors.append(f'{where}: 필수 필드 없음 {miss}')
            continue
        cands[c['id']] = c
        if c['id'] in seen:
            errors.append(f'{where}: 중복 id')
        seen.add(c['id'])
        if c['kind'] not in KINDS:
            errors.append(f'{where}: 알 수 없는 kind {c["kind"]!r}')
        if not str(c['text']).strip():
            errors.append(f'{where}: text가 비어 있음')
        if not str(c['section']).strip():
            errors.append(f'{where}: section이 비어 있음')
        elif c['section'] != '머리말' and squash(str(c['section'])) not in squash(text):
            errors.append(f'{where}: 원문에 없는 절 표기 — section {c["section"]!r}')
        if c['procedure'] is not None and squash(str(c['procedure'])) not in squash(text):
            errors.append(f'{where}: 원문에 없는 절차 표기 — procedure {c["procedure"]!r}')
        if not isinstance(c['refs'], list):
            errors.append(f'{where}: refs는 목록이어야 함')
        ls, le, quote = c['line_start'], c['line_end'], str(c['quote'])
        if not (isinstance(ls, int) and isinstance(le, int) and not isinstance(ls, bool) and 1 <= ls <= le <= len(lines)):
            errors.append(f'{where}: line_start · line_end가 원문 줄 범위(1~{len(lines)}) 안의 정수가 아님')
            continue
        segment = '\n'.join(lines[ls - 1:le])
        exact, near = locate(text, quote)
        by_reviewer = reviewed and c.get('origin') == 'reviewer'    # 같은 문장이 여러 곳이면 코드는 줄을 정하지 못한다 — 검토자가 고른 줄은 받는다
        if not quote.strip():
            errors.append(f'{where}: quote가 비어 있음')
        elif c['quote_match'] == 'exact':
            if quote not in segment:
                errors.append(f'{where}: quote가 {ls}~{le}줄에 글자 그대로 없음' + ('(파일의 다른 줄에 있음)' if exact else ''))
            elif exact > 1 and not by_reviewer:
                errors.append(f'{where}: quote가 원문 {exact}곳에 맞음 — 코드가 찾은 인용이 여러 곳에 맞으면 찾지 못한 것(unlocated)으로 두고, 그 줄은 검토자가 골라 더한다')
        elif c['quote_match'] == 'normalized':
            if quote in segment:
                errors.append(f'{where}: 글자 그대로 찾히는 인용은 quote_match가 exact')
            elif squash(quote) not in squash(segment):
                errors.append(f'{where}: quote가 {ls}~{le}줄에서 글자 · 숫자 비교로도 찾히지 않음')
            elif near > 1 and not by_reviewer:
                errors.append(f'{where}: quote가 글자 · 숫자 비교로 원문 {near}곳에 맞음 — 코드가 찾은 인용이면 찾지 못한 것(unlocated)으로 두고, 그 줄은 검토자가 골라 더한다')
        else:
            errors.append(f'{where}: quote_match는 exact 또는 normalized')
        if reviewed and c.get('origin') == 'reviewer':
            if (c['kind'], quote, ls) not in added:
                errors.append(f'{where}: origin reviewer인데 같은 종류 · 인용 · 줄의 missing 항목(added: true)이 없음 — 검토자가 더한 후보는 missing에 함께 적습니다')
        elif paired:
            said = str((c.get('before') or {}).get('quote', quote)) if reviewed else quote    # 검토에서 인용을 고쳤으면(수정) 고치기 전 인용으로 본다
            if said.strip() and not in_replies(said, paired):
                errors.append(f'{where}: 인용이 짝지은 응답 기록의 답 글에 없음 — 후보는 모델의 답에서 만듭니다' + ('(검토에서 고친 인용은 before.quote로 봄)' if reviewed else ''))
        if bilingual:
            said = {m.group(1) for x in lines[ls - 1:le] for m in [LANG.match(x)] if m}
            if c.get('lang') not in ('ko', 'en'):
                errors.append(f'{where}: 영문 원본과 번역이 함께 있는 문서라 lang(ko · en)이 필요')
            elif len(said) == 1 and said != {c['lang'].upper()}:
                errors.append(f'{where}: lang {c["lang"]!r}가 인용한 줄({", ".join(sorted(said))})과 다름')
        if scanned:
            foot = next((FOOTER.match(x.strip()).group(1) for x in lines[le - 1:] if FOOTER.match(x.strip())), None)
            if not c.get('page'):
                errors.append(f'{where}: 스캔본에서 인용한 후보는 page가 필요')
            elif foot != c['page']:
                errors.append(f'{where}: page {c["page"]!r}가 그 줄이 있는 쪽 꼬리({foot})와 다름')
        if c['kind'] == 'step' and not (isinstance(c.get('order'), int) and not isinstance(c.get('order'), bool) and c['order'] >= 1):
            errors.append(f'{where}: step에는 1 이상의 정수 order가 필요')
        if c['kind'] == 'unit_value':
            if not isinstance(c.get('value'), (int, float)) or isinstance(c.get('value'), bool):
                errors.append(f'{where}: unit_value의 value는 숫자여야 함')
            if not c.get('unit'):
                errors.append(f'{where}: unit_value에 unit이 없음')
            if c.get('comparator', 'missing') not in COMPARATORS:
                errors.append(f'{where}: comparator가 계약 값이 아님 {c.get("comparator", "(필드 없음)")!r}')
            if c.get('comparator') == 'range' and not isinstance(c.get('value_max'), (int, float)):
                errors.append(f'{where}: range에는 value_max가 필요')
            if not c.get('value_text') or str(c['value_text']) not in quote:
                errors.append(f'{where}: value_text가 quote 안에 그대로 없음')
        key = (c['kind'], c['section'], c['procedure'], c['text'], quote, c.get('value_text'))
        if key in dup:
            errors.append(f'{where}: 같은 종류 · 절 · 내용 · 인용 · 값의 후보가 이미 있음')
        dup.add(key)
        if reviewed:
            dec = c.get('decision')
            if dec not in STATUS:
                errors.append(f'{where}: decision은 채택 · 수정 · 제외 · 보류 중 하나')
            elif c['status'] != STATUS[dec]:
                errors.append(f'{where}: {dec}이면 status는 {STATUS[dec]}')
            if not str(c.get('reason', '')).strip():
                errors.append(f'{where}: 결정 이유(reason)가 없음')
            if dec == '수정' and not c.get('before'):
                errors.append(f'{where}: 수정에는 바꾸기 전 값(before)이 필요')
            if c.get('origin') not in ('extractor', 'reviewer'):
                errors.append(f'{where}: origin은 extractor 또는 reviewer')
        elif c['status'] != 'pending':
            errors.append(f'{where}: 추출 직후 status는 pending')
    for u in data['unlocated'] if isinstance(data['unlocated'], list) else []:
        if not isinstance(u, dict) or not u.get('quote') or not u.get('note'):
            errors.append('unlocated의 항목마다 quote와 찾지 못한 까닭(note)이 필요')
        elif 1 in locate(text, str(u['quote'])):
            notes.append(f'참고: unlocated의 인용 「{str(u["quote"])[:30]}」은 원문 한 곳에서 찾힙니다.')
    if reviewed:
        rv = data['review'] if isinstance(data['review'], dict) else {}
        for key in ['reviewer', 'reviewed_at', 'candidates_file', 'candidates_sha256']:
            if not rv.get(key):
                errors.append(f'review.{key} 없음')
        original = HERE / str(rv.get('candidates_file', ''))
        if rv.get('candidates_file') and not original.is_file():
            errors.append(f'review.candidates_file이 없습니다: {rv.get("candidates_file")}')
        elif rv.get('candidates_file') and sha(original) != rv.get('candidates_sha256'):
            errors.append('후보 파일 원본의 SHA-256이 review.candidates_sha256과 다릅니다(검토 뒤 후보 원본이 바뀜).')
        for m in data.get('missing', []):
            if not isinstance(m, dict) or not m.get('quote') or not any(locate(text, str(m['quote']))):
                errors.append(f'missing {m.get("section") if isinstance(m, dict) else m}: quote가 원문에 없음')
        known = rule_ids()
        for link in data.get('rule_links', []):
            if not isinstance(link, dict):
                errors.append('rule_links의 항목이 객체가 아님')
                continue
            rid, ids = link.get('rule_id'), link.get('candidates')
            if rid not in known:
                errors.append(f'rule_links {rid!r}: 기준 조건표의 rule_id나 그 출처 칸의 규칙 id가 아님')
            if link.get('match') not in MATCH:
                errors.append(f'rule_links {rid}: match는 일치 · 불일치 · 원문 없음 · 보류 중 하나')
            if not str(link.get('note', '')).strip():
                errors.append(f'rule_links {rid}: 까닭(note)이 없음')
            if not isinstance(ids, list) or any(x not in cands for x in ids):
                errors.append(f'rule_links {rid}: candidates는 이 파일 후보 id의 목록')
            elif link.get('match') in ('일치', '불일치') and not ids:
                errors.append(f'rule_links {rid}: {link.get("match")}이면 근거 후보 id가 필요')
            elif link.get('match') == '원문 없음' and ids:
                errors.append(f'rule_links {rid}: 원문 없음이면 candidates는 빈 목록')
    kinds = {}
    for c in cands.values():
        kinds[c.get('kind')] = kinds.get(c.get('kind'), 0) + 1
    notes.append(f'후보 {len(cands)}개, 종류별 {kinds}, 찾지 못한 인용 {len(data["unlocated"]) if isinstance(data["unlocated"], list) else 0}개')
    if reviewed:
        dec = {}
        for c in cands.values():
            dec[c.get('decision')] = dec.get(c.get('decision'), 0) + 1
        notes.append(f'결정별 {dec}, 누락 기록 {len(data.get("missing", []))}개, 조건 근거 대조 {len(data.get("rule_links", []))}개')
    return errors, notes


def seen_list(path):
    """통과 줄이 말할 「본 것」 — 그 파일에서 실제로 본 검사만."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return ['필드']
    if not isinstance(data, dict) or 'candidates' not in data:
        return ['필드']
    out = ['필드', '인용이 선언한 줄에 있는지']
    if data.get('model_run'):
        out += ['응답 기록 짝(모델 · 받은 시각 · ' + ('이 폴더의 기록인지)' if mark() else '기록끼리 한 폴더의 것인지 — 이 폴더의 표지가 없어 이 폴더의 기록인지는 보지 못함)'),
                '모델 답에서 온 후보의 인용이 짝지은 답 글에 있는지']
    if 'review' in data:
        out += ['결정 · 상태 · 이유', '검토자가 더한 후보마다 missing 항목이 있는지', '조건 근거 대조의 꼴']
    return out


def run(path):
    try:
        return check(path)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as e:
        return [f'읽기 실패: {e}'], []


def check_selected(path):
    """결과/선택작업_조건.json — 항목마다 검토 결과의 승인 후보를 가리키는지."""
    errors = []
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    for key in ['task', 'basis', 'preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff']:
        if key not in data:
            errors.append(f'필드 없음: {key}')
    if 'task' in data and data['task'] != TASK:
        errors.append(f'task {data["task"]!r}가 이 사건의 작업 {TASK}와 다름')
    for part in ['preparation', 'prohibitions', 'completion']:
        for item in data.get(part, []):
            ref = str(item.get('candidate', ''))
            file, _, cid = ref.partition('#')
            target = HERE / file
            if not target.is_file():
                errors.append(f'{part}: {ref!r}의 검토 결과 파일이 없음')
                continue
            review = json.loads(target.read_text(encoding='utf-8-sig'))
            cand = next((c for c in review.get('candidates', []) if c.get('id') == cid), None)
            if cand is None:
                errors.append(f'{part}: {ref!r}의 후보가 없음')
            elif cand.get('status') != 'approved':
                errors.append(f'{part}: {ref!r}는 승인(approved) 후보가 아님 — 보류 · 원문 미확인은 remaining_questions에')
            else:
                for key in ['section', 'quote']:
                    if item.get(key) != cand.get(key):
                        errors.append(f'{part}: {ref!r}의 {key}가 검토 결과와 다름')
                for key in ['doc_id', 'rev']:
                    if item.get(key) != review.get(key):
                        errors.append(f'{part}: {ref!r}의 {key}가 검토 결과와 다름')
    for q in data.get('remaining_questions', []):
        if not isinstance(q, dict) or not q.get('item') or not q.get('note'):
            errors.append('remaining_questions의 항목마다 item과 note가 필요')
    for d in data.get('sop_diff', []):
        if not isinstance(d, dict) or not d.get('item') or not d.get('note') or d.get('where') not in ('카드에만', 'SOP 구조에만'):
            errors.append('sop_diff의 항목마다 item · note와 where(카드에만 · SOP 구조에만)가 필요')
    return errors


def empty_tables(md):
    """기록 파일의 절별 표 행 수 · 빈 칸 수 · 칸 수가 머리 줄과 다른 행 수."""
    out, sec, width = {}, '머리', None
    for line in md.splitlines():
        if line.startswith('## '):
            sec, width = line[3:].strip(), None
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                out.setdefault(sec, [0, 0, 0])
                continue
            if width is None:
                width = len(cells)
                continue
            out.setdefault(sec, [0, 0, 0])
            out[sec][0] += 1
            out[sec][1] += sum(1 for c in cells if not c)
            out[sec][2] += len(cells) != width
        elif not line.strip():
            width = None
    return out


def slot_errors():
    """정할 자리의 꼴 — 제공 코드(doc_extract.py)의 검사로 본다. 비어 있는 자리는 결과 화면의 단계 띠에서 짚으므로 여기서는 꼴만."""
    import doc_extract as X
    out = []
    for fn in (X.settings, X.expected_rows, X.decision_rows, lambda: X.rule_rows(TASK), (X.role_rows if PRACTICAL else (lambda: None))):
        try:
            fn()
        except X.Problem as e:
            out.append(f'정할 자리: {e}')
        except OSError as e:
            out.append(f'정할 자리 파일을 읽지 못함: {e}')
    return out


def stages():
    todo = []
    print(f'기준 입력: {basis("조건표.csv").relative_to(HERE).as_posix()} · {basis(JUDGED).relative_to(HERE).as_posix()}')
    here = mark()
    recs = []
    for p in sorted((RESULT / '응답_기록').glob('*.json')):
        try:
            recs.append(json.loads(p.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            todo.append(f'응답_기록/{p.name}을 읽지 못했습니다.')
    sent = sum(1 for r in recs if r.get('method') == SENT and r.get('folder_mark') == here)
    empty = sum(1 for r in recs if r.get('usable') is False)
    chat = sum(1 for r in recs if r.get('method') == PASTED)
    other = sum(1 for r in recs if r.get('folder_mark') != here)
    print(f'[1] 응답 기록 {len(recs)}개(이 폴더에서 모델 서버로 보낸 요청 {sent} · 쓸 내용이 없던 답 {empty} · 채팅으로 받음 {chat} · 다른 폴더 기록 {other})')
    import doc_extract as _X
    try:
        has_prompt = bool(_X.prompt_text())
    except _X.Problem:
        has_prompt = False
    print(f'[2] 요청 글 결과/prompt.md: {"있음" if has_prompt else "없음(빈 틀)"}')
    if not has_prompt:
        todo.append('요청 글 결과/prompt.md가 아직 빈 틀입니다.')
    files = sorted((RESULT / '후보').glob('*.json'))
    print(f'[3] 후보 파일 {len(files)}개')
    first = []
    for f in files:
        errors, notes = run(f)
        print(f'    {f.name}: {"구조 검사 통과" if not errors else f"계약 확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        if errors:
            todo.append(f'{f.name} 계약 오류(파일 이름을 인자로 주고 실행하면 목록이 나옵니다).')
        try:
            first.append(str(json.loads(f.read_text(encoding='utf-8-sig')).get('generated_at')))
        except (OSError, ValueError, AttributeError):
            pass
    if len(files) < 2:
        todo.append('다른 문서에 다시 실행한 후보 파일이 아직 없습니다.')
    reviews = sorted((RESULT / '검토').glob('*.json'))
    print(f'[4] 검토 결과 {len(reviews)}개')
    linked = set()
    for f in reviews:
        errors, notes = run(f)
        print(f'    {f.name}: {"구조 검사 통과" if not errors else f"계약 확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        if errors:
            todo.append(f'{f.name} 계약 오류.')
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        cands = [c for c in data.get('candidates', []) if isinstance(c, dict)]
        linked |= {x.get('rule_id') for x in data.get('rule_links', []) if isinstance(x, dict)}
        if not any(c.get('status') == 'approved' for c in cands):
            print(f'    참고: {f.name}에 approved 후보가 없습니다 — 다음 실습은 approved 후보만 씁니다.')
        elif cands and all(c.get('decision') == '채택' for c in cands) and not data.get('missing'):
            print(f'    참고: {f.name}는 모든 후보가 「채택」이고 누락 기록이 0개입니다 — 원문과 줄마다 대조했는지 검토 기록에 남깁니다.')
    if not reviews:
        todo.append('검토 결과가 없습니다.')
    table = {r.get('rule_id') for r in csv_rows(basis('조건표.csv')) if TASK is None or r.get('action') == TASK} - {None, ''}
    rest = sorted(table - linked)
    scope = f'이 작업({TASK})에 걸린 조건' if TASK else '조건표의 조건'
    print(f'[5] 조건 근거 대조: {scope} {len(table)}개 가운데 rule_links가 있는 것 {len(table & linked)}개' + (f' — 없는 것 {", ".join(rest)}' if rest else ''))
    if rest:
        todo.append(f'{scope}마다 검토 결과의 rule_links가 필요합니다: ' + ', '.join(rest))
    if PRACTICAL:
        sel = RESULT / '선택작업_조건.json'
        if not sel.is_file():
            print('[6] 선택작업_조건.json: 없음')
            todo.append('결과/선택작업_조건.json이 없습니다.')
        else:
            try:
                errs = check_selected(sel)
            except (OSError, ValueError, AttributeError) as e:
                errs = [f'읽기 실패: {e}']
            print(f'[6] 선택작업_조건.json: {"구조 검사 통과" if not errs else f"계약 확인 필요 {len(errs)}건"}')
            for e in errs:
                print('    - ' + e)
            if errs:
                todo.append('선택작업_조건.json 계약 오류.')
    record = RESULT / '검토_기록.md'
    print(f'[{7 if PRACTICAL else 6}] 검토_기록.md')
    if not record.is_file():
        todo.append('검토_기록.md가 없습니다.')
    else:
        text = record.read_text(encoding='utf-8-sig')
        for line in text.splitlines():
            if re.match(r'^- [^:]+:\s*$', line):
                print(f'    빈 항목: {line.strip()}')
                todo.append(f'검토_기록.md의 빈 항목 「{line.strip()}」')
        for sec, (n, blanks, shifted) in empty_tables(text).items():
            state = '표에 기록 없음' if n == 0 else f'{n}행' + (f', 빈 칸 {blanks}개' if blanks else '') + (f', 칸 수가 머리 줄과 다른 행 {shifted}개' if shifted else '')
            print(f'    「{sec}」: {state}')
            if n == 0 or blanks or shifted:
                todo.append(f'검토_기록.md 「{sec}」 — {state}')
        when = re.search(r'^- 기대 칸을 쓴 시각:[ \t]*(\S.*)$', text, re.M)
        stamp = lambda x: x.replace('T', ' ')[:16]
        if when and first and stamp(min(first)) < stamp(when.group(1).strip()):
            todo.append(f'검토_기록.md의 기대 칸을 쓴 시각({when.group(1).strip()})이 첫 후보 파일({min(first)})보다 뒤입니다.')
    todo += slot_errors() + chosen_errors(HERE) + provided_errors(HERE)
    print()
    if todo:
        print('완료 아님 — 남은 것:')
        for t in todo:
            print('  - ' + t)
        print(END)
        return 1
    print('구조상 빠진 단계는 없습니다. ' + END)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(stages())
    failed = False
    for arg in sys.argv[1:]:
        errors, notes = run(arg)
        print(f'== {arg}')
        for n in notes:
            print('  ' + n)
        if errors:
            failed = True
            print(f'  계약 확인 필요 {len(errors)}건')
            for e in errors[:40]:
                print('  - ' + e)
            if len(errors) > 40:
                print(f'  … 외 {len(errors) - 40}건')
        else:
            print('  구조 검사 통과 — 본 것: ' + ' · '.join(seen_list(arg)) + '.')
    print(END)
    sys.exit(1 if failed else 0)
'''


def checker(key):
    return CHECKER.replace('__JUDGED__', JUDGED[key]).replace('__PRACTICAL__', str(key == 'practical-03-extract')).replace('__TASK__', TASK)


# ═════════════ 그래프 반영 랩 둘 — 통합반 04회차 실습3 · 실전반 03회차 실습5(작업 확인 카드) ═════════════
import importlib.util as _ilu

GLABS = {'integrated-04-graph': OUT/'통합반/실습/04회차/랩/04일차_실습3_그래프반영과검증',
         'practical-03-card': OUT/'실전반/실습/03회차/랩/03일차_실습5_그래프반영'}
GTITLES = {'integrated-04-graph': '검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기',
           'practical-03-card': '검토 지식으로 작업 확인 카드 만들기'}
GNEXT = {'integrated-04-graph': '설비 이상 원인을 추론하고 다음 점검 작업 결정하기',
         'practical-03-card': '원인 분석을 점검 요청 초안으로 연결하기'}
GCOURSE = {'integrated-04-graph': '통합반', 'practical-03-card': '실전반'}
GEXTRACT = {'integrated-04-graph': 'integrated-04-extract', 'practical-03-card': 'practical-03-extract'}
GREC = '결과/구축_기록.md'
LAB2_INPUT = {}   # 그래프 랩 입력/모델의 원천 — build_session4_projects.legacy()가 과정마다 채운다(B.reference_model)
CARD_HEADINGS = ['대상 작업', '준비 조건', '금지 · 제한', '작업 순서', '완료 기준', '작업 직전 확인할 현재 값', '승인', '남은 질문']
LATER_DOCS = ['OEM-HPP45A-MM', 'PR-07']        # 통합 04-3 행 「다른 문서의 추가 반영」 — 연결 규칙을 그 단계에서 채우는 문서


def branches_module():
    """강사 검토 갈래(reference/session3_docs/branches.py) — 다음 실습 입력을 그 판으로 만든다(같은 사실 한 곳)."""
    spec = _ilu.spec_from_file_location('branches', REF/'branches.py')
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def instructor_reviews(key):
    """{입력/검토결과/ 안 이름: 바이트} — 강사 추출 실행 run1의 후보를 강사 판 갈래(지점5 나 · 지점6 가)로 검토한 결과."""
    BR = branches_module()
    course = GCOURSE[key]
    lab_folder = LABS[GEXTRACT[key]]
    judged = json.loads((lab_folder/'입력'/JUDGED[GEXTRACT[key]]).read_text(encoding='utf-8'))
    cands, when = BR.base_candidates()
    out, _ = BR.build(lab_folder, cands, judged, *BR.BASE, course, reviewed_at=when)
    files = {rel.split('/', 1)[1]: data for rel, data in out.items() if rel.startswith('검토/')}
    if course == '실전반':
        files['선택작업_조건.json'] = out['선택작업_조건.json']
    return files


SHAPE_BLANK = json.dumps({'제공 빈 틀 — 보관 없이 바로 채웁니다. 칸의 뜻은 입출력_계약.md 「정할 자리」': '',
                          '이름': {k: '' for k in ('문서', '판', '절', '지식', '문서의_판', '판의_절', '지식의_출처', '판의_대체', '규칙의_근거')},
                          '뜻': {k: '' for k in ('문서', '판', '절', '지식', '문서의_판', '판의_절', '지식의_출처', '판의_대체', '규칙의_근거')},
                          '판을_따로_둠': None, 'ID': {k: '' for k in ('문서', '판', '절', '지식')}}, ensure_ascii=False, indent=2) + '\n'


BASIS_COL = '근거 = 원문 파일:줄(꼴: 자료/파일.md:12 또는 파일 이름:12, 여럿이면 「 · 」로 잇기)'
BASIS_SHORT = '근거 = 원문 파일 이름:줄(여럿이면 「 · 」로 잇기)'   # 실전 카드 랩(한 칸의 둘째 랩 — 꼴은 앞 랩에서 봄)
GCOLS = {   # 정할 자리 표의 칸 뜻 — 빈 틀 둘째 줄과 그 단계 힌트 「지킬 것」이 같은 글을 쓴다(값은 넣지 않는다)
    '기대_답.csv': ('질문 = 「질문 1」 ~ 「질문 5」로 시작(한 질문을 여러 줄로 나누면 뒤에 무엇인지 짧게) · 기대_답 = 조회 전에 원문에서 찾은 답 한 줄(문서 · 판 · 절과 내용, 여럿이면 「 · 」, 없으면 「없음」) · ' + BASIS_COL),
    '기대_답.csv실전': ('질문 = 카드 항목 이름 하나(「준비 조건」 「금지 · 제한」 「작업 순서」 「완료 기준」 「작업 직전 확인할 현재 값」 「승인」 「남은 질문」 「대상 작업」) · '
                   '기대_답 = 그 항목의 내용 한 줄(여럿이면 「 · 」, 없으면 「없음」) · ' + BASIS_COL),
    '다른문서_조건.csv실전': '문서 · 판 · 절 = 그 조건의 doc_id · rev · 절 표기 · 인용에_든_글자 · 작업 = 조치 ID · 잇는다 = 예 · 아니오(아니오도 행으로) · 관계 = 예일 때 영문 이름 · 근거',
    '연결_규칙.csv': ('문서 · 판 = 검토 결과의 doc_id · rev 그대로 · 절 = 그 문서의 절 표기(비우면 그 문서 전체) · 잇는_방법 = 절차 표기와 같은 조치 · 정한 대상 · 별칭 · 잇지 않음 가운데 하나 · '
                   '관계 = 영문 관계 이름(잇지 않음이면 비움) · 대상 = 정한 대상일 때 기존 ID(여럿이면 빈칸으로) · 까닭 = 한 줄 · ' + BASIS_COL),
    '별칭.csv': '원문_이름 = 원문에 적힌 이름 · 품번 그대로(그 글자가 인용에 든 후보가 이어짐) · 기존_ID = 설비 모델 · SOP 구조 · 조건표의 ID(여럿이면 빈칸으로) · ' + BASIS_COL,
    '역할.csv': ('종류 = step · precondition · prohibition · completion · unit_value 가운데 하나 · 인용에_든_글자 = 이 글자가 인용에 든 후보만(비우면 그 종류 전부, 위 행이 먼저) · '
              '항목 = 준비 · 금지 · 순서 · 완료 · 승인 · 넣지 않음 가운데 하나(넣지 않음 = 잇기는 연결 규칙대로 하되 어느 항목에도 두지 않음) · 근거 = 원문 파일:줄 또는 입출력_계약.md 절'),
    '다른문서_조건.csv': ('문서 · 판 · 절 = 그 조건이 있는 검토 결과의 doc_id · rev · 절 표기 · 인용에_든_글자 = 그 후보 인용에 든 글자 · 작업 = 이을 조치 ID · 잇는다 = 예 또는 아니오(아니오도 행으로 남김) · '
                    '관계 = 예일 때 영문 관계 이름 · ' + BASIS_COL),
    '질문_값.csv': '질문 · 이름 = 입출력_계약.md 「정할 자리」의 짝 그대로(q1 asset 같은 꼴) · 값 = 그 자리에 넣을 ID(hold ids는 검토 결과 파일 이름#후보 id, 여럿이면 빈칸으로)',
    '질문_값.csv실전': '질문 · 이름 = 계약 「정할 자리」의 짝(card sop 카드 작업 · card_other sop 다른 작업 · hold ids 보류 후보 · q5_target · q5_section 제공되지 않은 것) · 값 = 그 자리의 ID(여럿이면 빈칸으로)',
    '연결_규칙.csv실전': '문서 · 판 = 검토 결과의 doc_id · rev · 절 = 절 표기(비우면 문서 전체) · 잇는_방법 = 절차 표기와 같은 조치 · 정한 대상 · 별칭 · 잇지 않음 · 관계 = 영문 이름 · 대상 = 정한 대상의 기존 ID(여럿이면 빈칸) · 까닭 · 근거',
    '별칭.csv실전': '원문_이름 = 원문의 이름 · 품번 그대로 · 기존_ID = 설비 모델의 ID · 근거',
    '역할.csv실전': '종류 = 후보의 종류 · 인용에_든_글자 = 이 글자가 든 후보만(비우면 그 종류 전부) · 항목 = 준비 · 금지 · 순서 · 완료 · 승인 · 넣지 않음 · 근거 — 행이 없는 종류는 기본(precondition 준비 · prohibition 금지 · completion 완료 · unit_value 완료 · step 순서)',
    '현재값_원천.csv': '작업 = 조치 ID · 확인할_값 = 작업 직전에 볼 값의 이름(값은 적지 않음) · 읽을_원천 = 그 값을 읽는 시스템 이름 · ' + BASIS_COL,
}


def gcols(name, practical=False):
    text = GCOLS[name + '실전'] if practical and name + '실전' in GCOLS else GCOLS[name]
    return text.replace(BASIS_COL, BASIS_SHORT) if practical else text


def gblank(name, columns, explain, practical=False):
    """빈 틀: 첫 줄 「제공 빈 틀 — 설명」, 둘째 줄 칸 뜻(# 줄), 셋째 줄 열 이름."""
    head, cols = F.blank_csv(columns, explain).split('\n', 1)
    return f'{head}\n# {gcols(name, practical)}\n{cols}'


def ghead(blank, filled):
    """정답 보기에 붙여 넣는 표 — 빈 틀의 # 줄들 + fills의 열 이름 · 행(빈 틀 첫 줄 · 정답 첫 줄 · 힌트 「지킬 것」이 같은 칸 뜻)."""
    return ''.join(x for x in blank.splitlines(keepends=True) if x.startswith('#')) + filled


def graph_blanks(key):
    practical = key == 'practical-03-card'
    return {'결과/기대_답.csv': gblank('기대_답.csv', ['질문', '기대_답', '근거'], ('카드 항목' if practical else '질문') + '마다 조회 전에 원문 · 검토 결과에서 찾은 기대 답과 근거', practical),
            '결과/그래프_모양.json': SHAPE_BLANK,
            '결과/연결_규칙.csv': gblank('연결_규칙.csv', ['문서', '판', '절', '잇는_방법', '관계', '대상', '까닭', '근거'], '검토 결과의 문서(와 절)마다 승인 후보를 어느 기존 ID에 어떤 관계로 이을지', practical),
            '결과/별칭.csv': gblank('별칭.csv', ['원문_이름', '기존_ID', '근거'], '원문에 적힌 이름 · 품번이 가리키는 설비 모델의 기존 ID', practical),
            '결과/다른문서_조건.csv': gblank('다른문서_조건.csv', ['문서', '판', '절', '인용에_든_글자', '작업', '잇는다', '관계', '근거'], '다른 문서가 정한 조건 · 시간 · 승인을 이 작업에 이을지', practical),
            '결과/역할.csv': gblank('역할.csv', ['종류', '인용에_든_글자', '항목', '근거'], '조치에 잇는 지식의 종류를 준비 · 금지 · 순서 · 완료 · 승인 가운데 어디에 둘지', practical),
            '결과/질문_값.csv': gblank('질문_값.csv', ['질문', '이름', '값'], '조회에 넣을 값', practical),
            '결과/현재값_원천.csv': gblank('현재값_원천.csv', ['작업', '확인할_값', '읽을_원천', '근거'], '작업 직전에 확인할 현재 값과 그 값을 읽을 원천(시스템 이름) — 값 자체는 적지 않음', practical),
            F.CHOSEN_FILE: F.CHOSEN_TEMPLATE}


GSLOT_CONTRACT = '''
## __N__. 정할 자리 (`결과/` — 내가 AI와 채우는 빈 틀)

첫머리에 「제공 빈 틀」 표시가 있는 파일이다. `python show_result.py`가 채운 자리까지 제공 코드(`doc_graph.py` · `lab_cypher.py`)를 돌려 3절의 결과 파일을 쓰고 랩 DB에 적재 · 조회해 `결과/보기.html`에 보인다. 적재 문장은 모두 MERGE · SET이라 다시 실행해도 늘지 않는다. 빈 칸이나 꼴이 틀린 칸이 있으면 그 파일 · 칸과 함께 멈춘다.

- `결과/기대_답.csv` — 열 `질문,기대_답,근거`. 조회 전에 원문 · 검토 결과에서 찾은 기대 답과 근거(파일:줄).
- `결과/그래프_모양.json` — `이름`: 새 종류(`문서` · `판` · `절` · `지식`)와 새 관계(`문서의_판` · `판의_절` · `지식의_출처` · `판의_대체` · `규칙의_근거`)의 영문 이름(설비 모델 · 조치 기준이 쓰는 종류 이름은 쓰지 않는다). `뜻`: 같은 열쇠마다 뜻. `판을_따로_둠`: `true`면 판마다 노드를 두고 `false`면 절을 문서에 바로 잇는다(그때 판 · 문서의_판 · 판의_대체는 비워 둔다). `ID`: 새 대상의 ID를 짓는 꼴 — `{문서}` · `{판}` · `{절}` · `{후보}`(검토 결과의 후보 id) 자리로 쓴다. 지식 노드는 속성 `doc_id` · `rev` · `section` · `candidate`(검토 결과 파일 이름#후보 id) · 인용 · 줄 · 결정을 가진다.
- `결과/연결_규칙.csv` — 열 `문서,판,절,잇는_방법,관계,대상,까닭,근거`. 검토 결과의 문서 · 판(과 절 — 비우면 그 문서 전체, 절을 적은 행이 먼저. 다만 절차 안의 후보는 그 절차 표기가 조치 ID이고 그 문서(그 절)에 `절차 표기와 같은 조치` 행이 있으면 그 행을 따른다)마다 승인 후보를 잇는 방법: `절차 표기와 같은 조치`(후보의 절차 표기가 조치 ID면 그 조치에, 단계면 그 단계에) · `정한 대상`(`대상` 칸의 기존 ID, 여럿이면 빈칸으로) · `별칭`(`결과/별칭.csv`의 원문 이름이 인용에 들면 그 기존 ID에) · `잇지 않음`(출처 절에만). `관계`는 영문 관계 이름. 잇는 방법을 정한 문서만 적재한다.
- `결과/별칭.csv` — 열 `원문_이름,기존_ID,근거`. 원문에 적힌 이름 · 품번 · 모델이 가리키는 기존 ID(여럿이면 빈칸으로).
- `결과/다른문서_조건.csv` — 열 `문서,판,절,인용에_든_글자,작업,잇는다,관계,근거`. 다른 문서가 정한 조건을 이 작업(조치 ID)에 이을지 — `잇는다`는 `예` · `아니오`(아니오도 고른 것이라 행으로 남긴다), 예면 `관계` 이름.
- `결과/역할.csv` — 열 `종류,인용에_든_글자,항목,근거`. 조치에 잇는 지식의 관계 속성 `role` — 종류가 같고 인용에 그 글자가 든 첫 행(글자 칸이 비면 그 종류 전부). `항목`은 `준비` · `금지` · `순서` · `완료` · `승인` · `넣지 않음`(잇는지는 연결 규칙이 정하고, `넣지 않음`은 이어진 지식을 어느 항목에도 두지 않는다 — 질문 1의 항목 칸이 「넣지 않음」).
- `결과/질문_값.csv` — 열 `질문,이름,값`. 조회에 넣는 값(짝마다 무엇을 묻는지): __QPAIRS__.
- `결과/현재값_원천.csv` — 열 `작업,확인할_값,읽을_원천,근거`. 작업 직전에 확인할 현재 값과 그 값을 읽을 원천(시스템 이름). 값 자체는 적지 않는다 — 남은 질문(`현재 값 필요`)과 질문 3__CARDN__에 쓴다.
- `결과/정한_것.csv` — 열 `지점,고른_것,근거,바뀌는_답`. 「학생이 정할 것」의 지점과 작업 중 정한 것(그래프 모양 · 연결 규칙 등)마다 한 줄.
'''


QPAIRS_HOLD = '`hold ids` = 그래프에 없어야 할 보류 후보(검토 결과 파일 이름#후보 id, 여럿이면 빈칸으로) · `q5_target target` = 제공되지 않은 작업 · 대상의 ID · `q5_section section` = 제공되지 않은 절 표기'
QPAIRS = ('`q1 asset` = 그 설비에 걸린 조치마다 이은 지식(질문 1) · `q3 sop` · `q3 asset` = 그 작업이 그 설비에서 확인하는 센서(질문 3) · '
          '`q4 doc` = 더한 문서의 지식이 걸리는 대상(질문 4) · ' + QPAIRS_HOLD)
QPAIRS_CARD = '`card sop` = 카드를 만들 작업 · `card_other sop` = 같은 방법을 대 볼 다른 작업 · ' + QPAIRS_HOLD


def graph_contract(key):
    practical = key == 'practical-03-card'
    judge = (INPUT_TABLE.replace('`입력/조건표.csv` — 조건표.', '`입력/조건표.csv` — 냉각 계통 조치의 조건표.') + INPUT_SOP
             + (INPUT_JUDGED['practical-03-extract'] if practical else ''))
    selected = ('- `입력/검토결과/선택작업_조건.json` — 이 사건의 작업(`task`)의 준비 · 금지 · 완료 항목(`preparation` · `prohibitions` · `completion` — 항목마다 검토 결과의 승인 후보 `candidate` · `doc_id` · `rev` · `section` · `quote` · `decision`)과 '
                '`remaining_questions`(승인하지 않은 것 · 원문을 확인하지 못한 것 · 제공되지 않은 절).\n' if practical else '')
    slot = (GSLOT_CONTRACT.replace('__N__', '5' if practical else '4')
            .replace('__QPAIRS__', QPAIRS_CARD if practical else QPAIRS)
            .replace('__CARDN__', ' · 카드 「작업 직전 확인할 현재 값」' if practical else ''))
    text = (GRAPH_CONTRACT.replace('__INPUT_JUDGE__', judge).replace('__INPUT_SELECTED__', selected)
            .replace('__CARD__', (CARD_CONTRACT if practical else '') + slot))
    return (text.replace('(`python lab_cypher.py model`이 랩 DB에 올리는 것)', '(`python show_result.py`가 랩 DB에 올리는 것 — 공용 `lab_cypher.py`의 model)')
            .replace('있으면 `lab_cypher.py model`과 `check.py`는 그 파일을 쓴다.', '있으면 제공 코드와 `check.py`는 그 파일을 쓴다.')
            .replace('`python lab_cypher.py export 결과/지식_내보내기.json`이 쓴다.', '`python show_result.py`의 마지막 단계가 쓴다.'))


def graph_record(key):
    practical = key == 'practical-03-card'
    head = '카드 항목' if practical else '질문'
    later = '' if practical else '## 다른 문서 추가 뒤 기존 연결\n\n| 확인한 것 | 추가 전 | 추가 뒤 | 같음 · 다름 |\n|---|---|---|---|\n| | | | |\n\n'
    other = ('## 다른 작업 · 제공되지 않은 것\n\n| 물은 것 | 결과 | 원문 · 목록 근거 |\n|---|---|---|\n| | | |\n\n' if practical else
             '## 보류 후보 · 제공되지 않은 것 조회\n\n| 물은 것 | 결과 | 원문 · 목록 근거 |\n|---|---|---|\n| | | |\n\n')
    scope = ('그래프로 답함 · 현재 값 필요 · 승인 필요 · 공급 정보 · 원문에 없음' if practical else '그래프로 답함 · 현재 값 필요 · 추가 자료 필요 · 원문에 없음')
    return ('# 온톨로지 구축 기록\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n## 목표와 질문\n\n## 이 답을 쓰는 사람과 쓰는 곳\n\n'
            f'## 정한 것\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `{F.CHOSEN_FILE}`에 적습니다.\n\n'
            f'## {head}별 기대와 실제\n\n기대 답은 `결과/기대_답.csv`에 적습니다.\n\n- 기대 칸을 쓴 시각:\n\n| {head} | 실제 결과(결과 화면) | 같음 · 다름과 까닭 |\n|---|---|---|\n| | | |\n\n'
            '## 적재 수\n\n| 시점 | 노드 수 | 관계 수 | 확인한 것 |\n|---|---|---|---|\n| 설비 모델 · 조치 기준 적재 뒤 | | | |\n| 첫 적재 뒤 | | | |\n| 같은 적재 다시 | | | |\n'
            + ('' if practical else '| 다른 문서 추가 뒤 | | | |\n') + '\n' + later + other +
            f'## 답할 수 있는 것과 없는 것\n\n| 질문 | {scope} | 근거(원천 이름 · 파일) |\n|---|---|---|\n| | | |\n\n'
            '## 남은 질문\n\n## 저장 기록\n\n- 랩 DB 주소(인증값 제외):\n- 기준일:\n- 저장 시점:\n- 확인하지 못한 점:\n')


def graph_result_readme(key):
    card = ' · 작업 확인 카드(`작업확인카드_<SOP ID>.md`)' if key == 'practical-03-card' else ''
    return ('이번 과제의 정할 자리(「제공 빈 틀」 파일)를 여기서 채웁니다. `python show_result.py`가 채운 자리까지 적재 · 조회를 돌려 스키마 확장(`schema_ext.json`) · 적재 파일(`load.cypher`) · '
            f'조회문(`query.cypher`) · 남은 질문(`남은_질문.json`) · 내보내기(`지식_내보내기.json`){card}를 쓰고 `보기.html`에 보입니다.\n'
            '내 앞 결과를 쓰면 `내_입력/`에 `입력/`과 같은 이름 · 같은 자리로 복사해 둡니다.\n'
            '다시 열 때는 `python lab_db.py`로 랩 DB를 다시 켜고 `python show_result.py`를 실행해, `구축_기록.md`의 적재 수와 결과 화면을 함께 봅니다.\n')


def graph_input_readme(key, files, n_events):
    practical = key == 'practical-03-card'
    names = sorted(n[:-len('_검토.json')] for n in files if n.endswith('_검토.json'))
    return ('# 입력 — 읽기만 합니다\n\n조치를 판정하는 실습과 문서에서 지식을 추출 · 검토하는 실습을 하지 않았거나 PC가 초기화돼도 시작할 수 있게, 그 실습들의 결과와 같은 꼴로 검증해 제공하는 판입니다. '
            '형식과 키의 뜻은 `입출력_계약.md` 「입력」에 있습니다.\n\n'
            '- `모델/schema.json` · `모델/graph.json` — 설비 · 구성 요소 · 센서 · 물리량 · 부품' + (' · 공급사' if practical else '') + ' 모델(원자료 기준일 2026-10-15). 그 뒤 들어온 수정본은 냉각 계통의 ID를 바꾸지 않아 이 판을 그대로 씁니다.\n'
            '- `조건표.csv` · `sop.json` — 냉각 계통 조치의 조건표와 SOP 구조.\n'
            + (f'- `조치검토결과.json` — 지난 30일(2026-09-28 ~ 10-27) 경보 {n_events}건을 위 조건표로 판정 · 비교한 조치 검토 결과.\n' if practical else '')
            + f'- `검토결과/` — 문서 {len(names)}개({", ".join(names)})에서 뽑은 후보를 원문과 대조해 결정을 적은 검토 결과' + (' · 이 사건의 작업의 조건(`선택작업_조건.json`)' if practical else '') + '.\n')


GRAPH_STEPS = r'''"""__TITLE__ — 결과 화면의 단계(START.md 「진행 단계」와 같은 번호 · 이름). 제공 파일 — 고치지 않는다.
단계마다 정할 자리(결과/의 「제공 빈 틀」 파일)를 채웠으면 제공 코드(doc_graph.py · lab_cypher.py)를 돌려 랩 DB에 적재 · 조회하고 결과/보기.html에 보인다."""
from pathlib import Path
import json
import show_result as R
import doc_graph as G

HERE = Path(__file__).resolve().parent
TITLE = '__TITLE__'
PRACTICAL = __PRACTICAL__
TASK = '__TASK__'
LATER_DOCS = __LATER__
ITEMS = __ITEMS__                     # 기대_답.csv 질문 칸이 받는 카드 항목 이름(통합반은 None — 「질문 N」)
if PRACTICAL:                         # 실전 카드 랩: 종류마다 계약의 기본 항목, 역할.csv는 다르게 둘 것만
    G.ROLE_DEFAULT.update({'precondition': '준비', 'prohibition': '금지', 'completion': '완료', 'unit_value': '완료', 'step': '순서'})


def guard(fn):
    def run(previous):
        try:
            return fn(previous)
        except G.Problem as e:
            raise R.Stop(str(e))
    return run


def known():
    return G.model_ids()[0]


def shape():
    sh = G.shape()
    if sh is None:
        raise R.Blank('결과/그래프_모양.json이 아직 비어 있습니다.')
    return sh


def table_of(name, values, title):
    got = G.ask(name, values)
    if got is None:
        return R.note(f'{title} — 결과/질문_값.csv에 {name}의 값을 아직 적지 않았습니다.')
    return R.table(title, got[0], got[1])


@guard
def look(previous):
    rows, ok = [], []
    for fname, data in G.reviews():
        n = {}
        for c in data['candidates']:
            n[c['status']] = n.get(c['status'], 0) + 1
            if c['status'] == 'approved':
                ok.append([fname, c['id'], c['section'], c.get('procedure') or '', c['kind'], c['line_start'], c['quote']])
        rows.append([fname, data['doc_id'], data.get('rev'), n.get('approved', 0), n.get('pending', 0), n.get('excluded', 0),
                     ', '.join(f'{x["rule_id"]} {x["match"]}' for x in data.get('rule_links', []))])
    ids, _, sop = G.model_ids()
    kinds = {}
    for v in ids.values():
        kinds[v] = kinds.get(v, 0) + 1
    return [R.table('검토 결과 — 문서마다 승인 · 보류 · 제외 수와 조건 근거 대조', ['파일', '문서', '판', '승인', '보류', '제외', '조건 근거'], rows),
            R.counts('기존 ID(설비 모델 · SOP 구조 · 조건표)', sorted(kinds.items())),
            R.table('승인 후보 찾아보기(적재할 것)', ['검토 파일', '후보', '절', '절차', '종류', '줄', '인용'], ok)]


def look_db(previous):
    return look(previous) + db(previous)


@guard
def expect(previous):
    rows = G.expect_rows(ITEMS)
    if not rows:
        raise R.Blank('결과/기대_답.csv에 행이 없습니다.')
    out = [R.table('조회 전에 적은 기대', ['질문', '기대 답', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in rows])]
    for r in rows:                                   # 근거마다 첫 줄을 원문 그대로(글자 방식은 저절로 — 내가 적은 줄이 그 내용인지 본다)
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / '자료' / f).is_file():
                out.append(R.source_lines(HERE / '자료' / f, n))
    return out


@guard
def db(previous):
    import lab_cypher
    lab_cypher.model()
    c = G.counts()
    return [R.counts('랩 DB — 설비 모델과 조치 기준 적재 뒤', [('노드', c['nodes']), ('관계', c['rels'])] + sorted(c['labels'].items()))]


@guard
def plan(previous):
    sh = shape()
    p = G.preview(sh)
    out = [R.counts('승인 후보 전부를 이 모양으로 지으면(적재하지 않고 셈)', [('승인 후보', p['approved'])] + sorted(p['merges'].items())),
           R.counts('적재하지 않는 후보', sorted((k, v) for k, v in p['statuses'].items() if k != 'approved'))]
    if p['clash']:
        out.append(R.error('같은 ID에 서로 다른 대상이 겹침 — ID 짓는 꼴을 고칩니다', '\n'.join(f'{i}: {", ".join(w)}' for i, w in p['clash'][:20])))
    return out


@guard
def link(previous):
    sh = shape()
    rules = G.link_rows(known())
    if not rules:
        raise R.Blank('결과/연결_규칙.csv에 잇는 방법을 정한 행이 없습니다.')
    if not G.role_rows():
        raise R.Blank('결과/역할.csv에 행이 없습니다.')
    st = G.load_all()
    out = [R.counts('적재 전후', [('노드', st['after']['nodes']), ('관계', st['after']['rels']), ('적재한 지식', st['knowledge']), ('기존 ID에 이은 지식', st['linked'])]),
           R.table('적재한 문서', ['문서', '판'], st['docs'])]
    if st['clash']:
        out.append(R.error('같은 ID에 서로 다른 대상이 겹침', '\n'.join(f'{i}: {", ".join(w)}' for i, w in st['clash'][:20])))
    if st['notes']:
        out.append(R.note('\n'.join(st['notes'][:20])))
    cols, rows = G.linked_to(sh, TASK)
    out.append(R.table(f'핀 세척({TASK})과 그 단계에 이은 지식 — 원문 줄로 확인', ['이은 대상', '관계', '항목', '문서', '판', '절', '줄', '인용'], rows))
    for r in rules[:12]:
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / '자료' / f).is_file():
                out.append(R.source_lines(HERE / '자료' / f, n))
    return out


@guard
def other(previous):
    shape()
    rows = G.other_rows(known())
    if not rows:
        raise R.Blank('결과/다른문서_조건.csv에 행이 없습니다 — 잇지 않기로 했어도 그 행을 「아니오」로 남깁니다.')
    st = G.load_all()
    vals = G.ask_values()
    out = [R.counts('다시 적재한 뒤(직전 실행과 같으면 늘지 않은 것)', [('노드', st['after']['nodes']), ('관계', st['after']['rels'])]),
           R.table('다른 문서의 조건', ['문서', '판', '절', '글자', '작업', '잇는다', '관계', '근거'], [[r['문서'], r['판'], r['절'], r['인용에_든_글자'], r['작업'], r['잇는다'], r.get('관계', ''), r['근거']] for r in rows])]
    for r in rows:
        for f, n in G.basis_lines(r['근거'])[:1]:
            if (HERE / '자료' / f).is_file():
                out.append(R.source_lines(HERE / '자료' / f, n))
    return out


@guard
def ask123(previous):
    sh = shape()
    vals = G.ask_values()
    if not vals:
        raise R.Blank('결과/질문_값.csv에 값이 없습니다.')
    G.write(HERE / '결과/query.cypher', G.query_file(sh, vals))
    exp = G.expect_rows(ITEMS)
    state = json.loads((HERE / '랩_연결.json').read_text(encoding='utf-8')) if (HERE / '랩_연결.json').is_file() else {}
    return [R.table('내 기대', ['질문', '기대 답', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in exp]),
            table_of('q1', vals, '질문 1 — 조치마다 단계 · 준비 · 금지 · 완료 · 승인과 근거'),
            table_of('q2', vals, '질문 2 — 규칙마다 근거 원문과 맞는 정도'),
            table_of('q3', vals, '질문 3 — 이 작업이 확인하는 센서(값은 그래프 밖)'),
            table_of('hold', vals, '보류 후보가 그래프에 있는가'),
            R.note('Neo4j Browser로 모양을 볼 때: ' + (state.get('browser') or '랩_연결.json의 Browser 주소') + ' — 결과/query.cypher에서 그 질문의 「// Browser:」 줄의 :param부터 붙여 넣습니다. 터미널로는 「// 터미널:」 줄의 명령을 실행합니다.')]


@guard
def more(previous):
    rules = G.link_rows(known())
    have = {r['문서'] for r in rules}
    if not set(LATER_DOCS) <= have:
        raise R.Blank('결과/연결_규칙.csv에 다른 문서(' + ' · '.join(LATER_DOCS) + ')의 행이 아직 없습니다.')
    st = G.load_all()
    vals = G.ask_values()
    c = st['compare']
    out = [R.counts('다른 문서 추가 전후', [('노드', st['after']['nodes']), ('관계', st['after']['rels'])])]
    if c is None:
        out.append(R.note('추가 전 내보내기가 없습니다 — 다른 문서의 행을 처음부터 함께 채워 적재했습니다(추가 전후를 견줄 기준이 없음).'))
    else:
        out.append(R.counts('추가 전 그래프와 비교', [('늘어난 노드', c['added_nodes']), ('늘어난 관계', c['added_rels']), ('속성이 바뀐 기존 노드', len(c['changed_nodes'])),
                                                 ('사라진 노드', len(c['gone_nodes'])), ('사라진 관계', len(c['lost_rels'])), ('속성이 바뀐 기존 관계', len(c['changed_rels']))]))
        if c['changed_nodes'] or c['gone_nodes'] or c['lost_rels']:
            out.append(R.table('바뀌거나 사라진 기존 것', ['무엇', 'ID'], [['속성 바뀜', x] for x in c['changed_nodes']] + [['사라진 노드', x] for x in c['gone_nodes']]
                               + [['사라진 관계', ' '.join(map(str, x))] for x in c['lost_rels']]))
    out += [table_of('q1', vals, '질문 1 — 다시'), table_of('q4', vals, '질문 4 — 더한 문서의 지식이 걸리는 대상')]
    return out


@guard
def card(previous):
    sh = shape()
    vals = G.ask_values()
    if 'card' not in vals or not G.now_rows():
        raise R.Blank('결과/질문_값.csv의 card sop와 결과/현재값_원천.csv를 채웁니다.')
    G.write(HERE / '결과/query.cypher', G.query_file(sh, vals))
    G.write(HERE / '결과/남은_질문.json', G.dump(G.remaining(vals)))
    sop = vals['card']['sop']
    text = G.card_text(sop)
    if text is None:
        return [R.note(f'{sop}: 그래프에 그 작업이 없습니다 — 결과 없음.')]
    G.write(HERE / f'결과/작업확인카드_{sop}.md', text)
    exp = G.expect_rows(ITEMS)
    return [R.table('내 기대', ['카드 항목', '기대', '근거'], [[r['질문'], r['기대_답'], r['근거']] for r in exp]), R.note(text)]


@guard
def card_other(previous):
    vals = G.ask_values()
    if 'card_other' not in vals:
        raise R.Blank('결과/질문_값.csv의 card_other sop를 채웁니다.')
    sop = vals['card_other']['sop']
    text = G.card_text(sop)
    out = []
    if text is None:
        out.append(R.note(f'{sop}: 그래프에 그 작업이 없습니다 — 결과 없음.'))
    else:
        G.write(HERE / f'결과/작업확인카드_{sop}.md', text)
        out.append(R.note(text))
    out += [table_of('q5_target', vals, '제공되지 않은 작업 · 대상'), table_of('q5_section', vals, '제공되지 않은 절')]
    return out


@guard
def other_scope(previous):
    vals = G.ask_values()
    extra = [table_of('q4', vals, '질문_값.csv의 q4 doc — 그 문서의 지식이 걸리는 대상')] if 'q4' in vals else []   # 계약 밖 짝이지만 적었으면 결과를 보인다
    return card_other(previous) + [table_of('hold', vals, '보류 후보가 그래프에 있는가(찾은 수 0이어야 함)')] + extra + scope(previous)


@guard
def scope(previous):
    rows = G.now_rows()
    if not rows:
        raise R.Blank('결과/현재값_원천.csv에 행이 없습니다.')
    vals = G.ask_values()
    rq = G.remaining(vals)
    G.write(HERE / '결과/남은_질문.json', G.dump(rq))
    kinds = {}
    for x in rq:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    out = [R.table('작업 직전 확인할 현재 값과 읽을 원천(그래프에 넣지 않음)', ['작업', '확인할 값', '읽을 원천', '근거'], [[r['작업'], r['확인할_값'], r['읽을_원천'], r['근거']] for r in rows]),
           R.counts('남은 질문(결과/남은_질문.json)', sorted(kinds.items()))]
    if not PRACTICAL:
        out += [table_of('q3', vals, '질문 3 — 이 작업이 확인하는 센서'), table_of('q5_target', vals, '질문 5 — 제공되지 않은 작업 · 대상'), table_of('q5_section', vals, '질문 5 — 제공되지 않은 절')]
    return out


@guard
def save(previous):
    import lab_cypher, subprocess, sys
    vals = G.ask_values()
    G.write(HERE / '결과/남은_질문.json', G.dump(G.remaining(vals)))
    graph = G.export_graph()
    graph['remaining_questions'] = json.loads((HERE / '결과/남은_질문.json').read_text(encoding='utf-8'))
    G.write(HERE / '결과/지식_내보내기.json', G.dump(graph))
    c = G.counts()
    run = subprocess.run([sys.executable, str(HERE / 'check.py')], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    return [R.counts('내보내기(결과/지식_내보내기.json)', [('노드', len(graph['nodes'])), ('관계', len(graph['rels'])), ('남은 질문', len(graph['remaining_questions'])),
                                                     ('랩 DB 노드', c['nodes']), ('랩 DB 관계', c['rels'])]),
            R.note('python check.py 출력(끝 12줄, 종료 코드 ' + str(run.returncode) + ')\n' + '\n'.join(run.stdout.strip().splitlines()[-12:]))]


__STEPS__
'''


def gstep_order(key):
    if key == 'practical-03-card':
        return ['db', 'expect', 'plan', 'link', 'other', 'card', 'other_scope', 'save']
    return ['look', 'expect', 'db', 'plan', 'link', 'other', 'ask123', 'more', 'scope', 'save']


def graph_steps_source(key, L):
    slots = {'expect': ['결과/기대_답.csv'], 'plan': ['결과/그래프_모양.json'], 'link': ['결과/연결_규칙.csv', '결과/역할.csv'], 'other': ['결과/다른문서_조건.csv'],
             'ask123': ['결과/질문_값.csv'], 'card': ['결과/현재값_원천.csv'], 'scope': ['결과/현재값_원천.csv'], 'other_scope': ['결과/현재값_원천.csv']}
    runs = {'db': 'look_db' if key == 'practical-03-card' else 'db', 'look': 'look', 'expect': 'expect', 'plan': 'plan', 'link': 'link', 'other': 'other', 'ask123': 'ask123', 'more': 'more', 'card': 'card',
            'card_other': 'card_other', 'scope': 'scope', 'other_scope': 'other_scope', 'save': 'save'}
    lines = ['STEPS = [']
    for no, (k, s) in enumerate(zip(gstep_order(key), L['steps']), 1):
        lines.append(f'    dict(no={no}, name={s["name"]!r}, slots={slots.get(k, [])!r}, run={runs[k]}),')
    lines.append(']')
    return (GRAPH_STEPS.replace('__TITLE__', L['title']).replace('__PRACTICAL__', str(key == 'practical-03-card')).replace('__TASK__', TASK)
            .replace('__LATER__', repr(LATER_DOCS)).replace('__ITEMS__', repr(CARD_HEADINGS if key == 'practical-03-card' else None)).replace('__STEPS__', '\n'.join(lines) + '\n'))


GRAPH_CONTRACT = '''# 입출력 계약

입력과 결과 파일의 형식과 뜻만 정한다. 무엇을 어떤 종류 · 관계로 담을지, 새 대상의 ID를 어떻게 지을지는 정하지 않는다. `check.py`가 이 계약의 구조를 검사한다.

## 1. 입력(읽기만)

- `입력/모델/schema.json` · `입력/모델/graph.json` — 설비 모델. 형식은 schema.json 그대로다: `classes`(종류마다 뜻 · 필수 · 선택 속성) · `relations`(관계마다 시작 · 끝 종류) · `constraints`. graph.json은 `nodes`(`labels` · `props`)와 `rels`(`type` · `a` 시작 ID · `b` 끝 ID · `props`)이고, ID는 그래프 전체에서 고유하다.
__INPUT_JUDGE__- `입력/검토결과/<문서 식별자>_<판>_검토.json` — 문서에서 뽑은 후보를 원문과 대조해 결정을 적은 검토 결과. 최상위에 `doc_id` · `rev` · `doc_status` · `source_file` · `source_sha256`(읽은 파일의 SHA-256) · `encoding`(그 파일을 읽은 글자 방식) · `extractor`(후보를 만든 실행 — 코드 파일 · 요청 글 · 조각 나누기) · `generated_at`(후보를 만든 시각) · `model_run`(후보를 만든 모델 응답 기록마다 `record` · `request_hash` · `model` · `method` · `reused_from` — 응답 기록 파일은 이 폴더에 없으므로 출처 표시로만 읽는다) · `unlocated`(원문 한 곳에서 인용을 찾지 못해 후보로 두지 않은 것) · `warnings`(추출 중 판단하지 못한 것)와 `review`(검토자 · 시각 · 검토한 후보 파일과 그 SHA-256 · 이 사건의 작업 `selected_task` · 검토 전체에 적용한 결정 `decisions`)가 있다. `candidates`의 후보 하나는 `id`(파일 안에서 고유) · `section`(그 문서의 절 표기 그대로) · `procedure`(절차 안이면 절차 표기, 아니면 `null`) · `kind`(`step` 단계 · `precondition` 시작 조건과 승인 · `prohibition` 금지와 제한 · `completion` 완료 기준 · `unit_value` 숫자와 단위가 있는 기준값) · `text` · `quote`(원문 그대로) · `quote_match`(인용을 찾은 방법 — `exact` 그 줄에 글자 그대로, `normalized` 글자 · 숫자만 남겨 비교하면 그 줄에 있음) · `line_start` · `line_end`(원문 파일의 줄) · `refs`(인용이 가리키는 다른 절 · 절차) · `status`와 검토 필드 `decision`(`채택` · `수정` · `제외` · `보류`) · `status`(채택 · 수정 → `approved`, 제외 → `excluded`, 보류 → `pending`) · `reason`(결정 이유) · `origin`(`extractor` 모델 답에서 온 후보, `reviewer` 검토자가 원문 문장으로 더한 후보) · `before`(`수정`일 때 바꾸기 전 필드 값 — 인용 · 줄 · 비교 등)이다. 단계는 `order`(절차 안 번호), 스캔본은 `page`, 영문 원본과 번역이 함께 있는 문서는 `lang`이 더 있고, 기준값은 `value` · `unit` · `comparator` · `value_text`(값이 적힌 원문 조각)와 범위면 `value_max`(큰 값)가 더 있다. `missing`은 원문에 있는데 그 항목을 담은 후보가 없던 것(`note` 까닭 · `added` 검토자가 원문 문장으로 후보를 더했는지), `rule_links`는 조건표의 조건(`rule_id`)마다 근거로 본 후보 id(`candidates`) · 맞는 정도(`match`: 일치 · 불일치 · 원문 없음 · 보류) · 까닭(`note`)이다. 적재에는 `approved` 후보만 쓴다.
__INPUT_SELECTED__- `자료/` — 검토한 문서의 원문과 `자료/문서_목록.csv`(첫 줄은 내보내기 머리, 둘째 줄이 열 이름: 문서 식별자 · 제목 · 판 · 상태 · 시행일 · 소유 부서 · 대체 관계 · 파일 · SHA-256 · 비고 — 파일 칸이 빈 행은 목록에만 있고 받은 파일이 없는 문서).
- `결과/내_입력/` — 내 앞 결과를 쓸 때 위 `입력/`의 파일과 같은 이름 · 같은 자리(`결과/내_입력/검토결과/` 등)로 둔다. 있으면 `lab_cypher.py model`과 `check.py`는 그 파일을 쓴다.

## 2. 설비 모델과 조치 기준의 그래프 (`python lab_cypher.py model`이 랩 DB에 올리는 것)

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

- `결과/schema_ext.json` — 문서 근거를 담으려고 더한 종류 · 관계. 꼴은 `입력/모델/schema.json`과 같다(`classes` · `relations`). 기존 종류 · 관계 이름은 그 뜻 그대로 다시 쓰고, 새 이름에는 뜻을 적는다.
- `결과/` 아래 적재 파일(`.cypher`, 또는 적재 문장을 만드는 코드와 그 출력) — 같은 파일을 다시 실행해도 노드 · 관계 수가 늘지 않는다. 전체를 지우는 문장은 쓰지 않는다.
- `결과/query.cypher` — 질문마다의 조회문(읽기만).
- `결과/지식_내보내기.json` — `python lab_cypher.py export 결과/지식_내보내기.json`이 쓴다. 꼴은 `입력/모델/graph.json`과 같고(`nodes` · `rels`), `remaining_questions`가 더 있다. 다음 실습에 넘길 판본이다.
- `결과/남은_질문.json` — 그래프에 넣지 않은 것 가운데 답하려면 더 알아야 하는 것. `[{"item": "…", "kind": "보류 | 원문 미확인 | 제공되지 않은 절 | 제공되지 않은 대상 | 제공되지 않은 문서 | 현재 값 필요", "source": "…", "note": "…"}]`. 내보내기가 이 목록을 `remaining_questions`에 넣는다.
- `결과/구축_기록.md` — 「제공 빈 틀」의 칸대로 채운다.
__CARD__'''
CARD_CONTRACT = '''
## 4. 작업 확인 카드 (`결과/작업확인카드_<SOP ID>.md`)

카드는 아래 제목을 이 순서로 가진다. 해당하는 것이 없으면 「없음」과 까닭을 적는다.

''' + '\n'.join(f'- `## {h}`' for h in CARD_HEADINGS) + '''

- 원문에서 온 항목은 문서 식별자 · 판 · 절과 「원문 그대로 인용」을 함께 적는다.
- `대상 작업`에는 SOP ID · 이름, 그 근거 문서의 식별자 · 판 · 상태를 적는다.
- `작업 직전 확인할 현재 값`은 문서의 기준값과 구별하고, 그 값을 읽을 원천(시스템 이름)을 적는다. 값 자체는 카드에 적지 않는다.
- `승인`은 원문에 적힌 승인 역할이다. 카드는 승인을 대신하지 않는다.
- `남은 질문`에는 원문이 정하지 않은 것, 적재하지 않은 후보 때문에 답하지 못하는 것, 원문 절 · 문서가 제공되지 않은 것을 적는다.
'''


GRAPH_CHECKER = r'''"""적재 파일 · 랩 DB · 내보내기 · 구축_기록.md__CARD_DOC__의 구조 검사. 생성 · 수정 · DB 변경을 하지 않는다(랩 DB는 읽기 조회만).
무엇을 어디에 이어야 맞는지, 조회 결과가 질문에 맞게 답하는지는 판정하지 않는다 — 의미와 질문별 답은 원자료와 따로 대조한다.
사용: python check.py
"""
from pathlib import Path
import csv, io, json, re, sys, urllib.request, urllib.error

HERE = Path(__file__).resolve().parent
RESULT = HERE / '결과'
PRACTICAL = __PRACTICAL__
HEADINGS = __HEADINGS__
END = '의미와 질문별 답은 원자료와 따로 대조합니다.'
WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)
DELETE = re.compile(r'\bDELETE\b', re.I)
ID_LITERAL = re.compile(r'\bid\s*:\s*[\'"]([^\'"]+)[\'"]')
SHAPES = [re.compile(p) for p in (r'^HYD-\d\d(?::[\w-]+)?$', r'^P-[A-Z0-9]+(?:-[A-Z0-9]+)*$', r'^SOP-[A-Z]+-\d+(?::\d+)?$', r'^fm:[\w-]+$', r'^cause:[\w-]+$', r'^R\d+$')]
NOW_KEYS = re.compile(r'on_hand|reserved|on_order|stock|현재고|예약|입고|재고', re.I)
QUOTE = re.compile(r'「([^」]+)」')


def read(path):
    raw = Path(path).read_bytes()
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def csv_rows(path):
    lines = [x for x in read(path).splitlines() if x.strip() and not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def basis(rel):
    mine = RESULT / '내_입력' / rel
    return mine if mine.exists() else HERE / '입력' / rel


def known_ids():
    """설비 모델 · SOP 구조 · 조건표가 만드는 기존 ID."""
    graph = json.loads(read(basis('모델/graph.json')))
    sop = json.loads(read(basis('sop.json')))
    ids = {n['props']['id'] for n in graph['nodes']}
    ids |= {x['id'] for x in sop['failure_modes'] + sop['causes']}
    for s in sop['sops']:
        ids.add(s['id'])
        ids |= {f'{s["id"]}:{st["order"]}' for st in s['steps']}
    ids |= {r['rule_id'] for r in csv_rows(basis('조건표.csv'))}
    return ids


def reviews():
    """[(문서 식별자, 판, 후보 id, 상태, 인용)] — 기준 검토 결과의 후보 전부. 후보 id는 파일 안에서만 고유하다."""
    out = []
    for f in sorted(basis('검토결과').glob('*_검토.json')):
        data = json.loads(read(f))
        for c in data.get('candidates', []):
            out.append((str(data.get('doc_id')), str(data.get('rev') or ''), c['id'], c.get('status'), c.get('quote')))
    return out


def approved_values():
    """승인(approved) 후보가 가진 글 값 전부(인용 · 내용 · 값 글 · 절 · 절차) — 같은 글이 다른 문서의 승인하지 않은 후보 인용과 겹쳐도 승인한 지식의 값이다."""
    out = set()
    for f in sorted(basis('검토결과').glob('*_검토.json')):
        for c in json.loads(read(f)).get('candidates', []):
            if c.get('status') == 'approved':
                out |= {v for v in c.values() if isinstance(v, str)}
    return out


def points_to(value, cands):
    """값(ID · 글)이 가리키는 후보들 — 후보 id 그대로이거나, 문서 식별자를 품고 후보 id로 끝나는 값(판이 보이면 그 판으로 좁힘)."""
    hits = [c for c in cands if value == c[2] or (value.endswith(c[2]) and c[0] in value)]
    narrowed = [c for c in hits if c[1] and c[1] in value.replace(c[2], '')]
    return narrowed or hits


def held(value, cands):
    """값이 승인(approved)이 아닌 후보만 가리키는가."""
    hits = points_to(value, cands)
    return bool(hits) and all(c[3] != 'approved' for c in hits)


def headings():
    """자료/ 원문에 절 머리로 있는 표기 — 「## 」 · 「### 」 줄의 첫 낱말, 「제N조」, 「HM-9.x 제목」 꼴 줄."""
    out = set()
    for f in (HERE / '자료').iterdir():
        if f.suffix not in ('.md', '.txt'):
            continue
        for line in read(f).splitlines():
            m = re.match(r'^#{2,3}\s+(\S+)', line) or re.match(r'^(제\d+조)\(', line) or re.match(r'^([A-Z]{2}-\d+(?:\.\d+)?)\s+\S+\s*\S*$', line.strip())
            if m and '....' not in line:
                out.add(m.group(1))
    return out


def labels_in(text):
    return set(re.findall(r'\b[A-Z]{2}-\d+\.\d+\b|\bT-\d+\.\d+\b|제\d+조', text))


def missing_docs():
    """문서 목록에 있지만 받은 파일이 없는 문서 식별자."""
    return {r['문서 식별자'] for r in csv_rows(HERE / '자료/문서_목록.csv') if not r.get('파일')}


def db():
    state = HERE / '랩_연결.json'
    if not state.is_file():
        return None
    url = json.loads(read(state))['http'] + '/db/neo4j/tx/commit'
    def run(statements):
        body = json.dumps({'statements': [{'statement': s, 'parameters': p} for s, p in statements]}).encode()
        req = urllib.request.Request(url, body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if data.get('errors'):
            raise RuntimeError('; '.join(e.get('message', '') for e in data['errors']))
        return [[row['row'] for row in res['data']] for res in data['results']]
    return run


def check_loads(todo, known, cands):
    files = sorted(p for p in RESULT.glob('*.cypher'))
    print(f'[2] 결과/의 Cypher 파일 {len(files)}개: ' + ', '.join(p.name for p in files))
    loads = [p for p in files if p.name != 'query.cypher']
    if not loads:
        todo.append('결과/에 적재 파일(.cypher)이 없습니다.')
    seen_ids = set()
    for p in files:
        text = read(p)
        body = '\n'.join(l for l in text.splitlines() if not l.lstrip().startswith('//'))
        if WIPE.search(body):
            todo.append(f'{p.name}: 전체를 지우는 문장이 있습니다.')
        dels = [n for n, l in enumerate(text.splitlines(), 1) if DELETE.search(l) and not l.lstrip().startswith('//')]
        if dels and p.name == 'query.cypher':
            todo.append(f'query.cypher {", ".join(map(str, dels))}줄: 조회문은 읽기만 합니다(DELETE).')
        elif dels:
            print(f'    참고: {p.name} {", ".join(map(str, dels))}줄에 DELETE — 적재문은 만들고 고치는 문장만 두어 다시 실행해도 같은 결과가 나오게 합니다.')
        tokens = set(re.findall(r'[\w:.@#-]+', body))
        used = sorted(x for x in tokens if held(x, cands)) if p.name != 'query.cypher' else []   # 조회문은 보류 확인에서 보류 후보를 일부러 묻는다
        if used:
            todo.append(f'{p.name}: 승인(approved)이 아닌 후보 id를 가리킵니다 — {", ".join(used[:8])}')
        for lit in ID_LITERAL.findall(body):
            seen_ids.add(lit)
            if any(s.match(lit) for s in SHAPES) and lit not in known:
                todo.append(f'{p.name}: 기존 ID 꼴인데 설비 모델 · SOP 구조 · 조건표에 없는 ID — {lit}')
    return seen_ids


def check_db(todo, known, cands):
    run = db()
    if run is None:
        print('[3] 랩 DB: 랩_연결.json 없음(python lab_db.py)')
        todo.append('랩 DB를 아직 준비하지 않았습니다.')
        return
    try:
        ok_values = approved_values()
        bad_quotes = {c[4] for c in cands if c[3] != 'approved' and c[4] and c[4] not in ok_values}
        ids = sorted(known)
        res = run([('MATCH (n) WHERE n.id IS NULL OR NOT n.id IN $ids RETURN count(n)', {'ids': ids}),
                   ('MATCH (m)-[r]-(k) WHERE m.id IN $ids AND (k.id IS NULL OR NOT k.id IN $ids) RETURN labels(m)[0], type(r), count(DISTINCT r) ORDER BY 1, 2', {'ids': ids}),
                   ('MATCH (n) WHERE n.id IS NULL OR NOT n.id IN $ids UNWIND keys(n) AS k WITH n, k WHERE n[k] IS :: STRING RETURN coalesce(n.id, "(id 없음)"), k, n[k]', {'ids': ids}),
                   ('MATCH (n) UNWIND keys(n) AS k RETURN DISTINCT k', {}),
                   ('MATCH (n) WHERE n.id IS NULL OR NOT n.id IN $ids RETURN n.id', {'ids': ids})])
    except (OSError, urllib.error.URLError, RuntimeError, ValueError) as e:
        print(f'[3] 랩 DB 조회 실패: {e}')
        todo.append(f'랩 DB를 조회하지 못했습니다({e}). python lab_db.py 로 다시 켜고 실행합니다.')
        return
    extra, links, keys, new_ids = res[0][0][0], res[1], [r[0] for r in res[3]], [r[0] for r in res[4]]
    held_props = []
    for nid, k, value in res[2]:
        if (k == 'id' or len(value) < 80) and held(value, cands) or value in bad_quotes:
            held_props.append((nid, k))
        if len(held_props) >= 20:
            break
    total = sum(r[2] for r in links)
    print(f'[3] 랩 DB: 설비 모델 · 조치 기준 밖에서 적재한 노드 {extra}개, 그 노드와 기존 ID를 잇는 관계 {total}개'
          + (' — ' + ', '.join(f'{a} {t} {n}개' for a, t, n in links[:12]) if links else ''))
    if extra == 0:
        todo.append('랩 DB에 설비 모델 · 조치 기준 밖의 노드가 없습니다 — 적재 파일을 아직 실행하지 않았습니다.')
    elif total == 0:
        todo.append(f'적재한 노드 {extra}개가 기존 ID와 하나도 이어지지 않았습니다.')
    for nid, k in held_props:
        todo.append(f'랩 DB 노드 {nid}의 {k}: 승인(approved)이 아닌 후보의 id · 인용입니다.')
    now = sorted(k for k in keys if NOW_KEYS.search(k))
    if now:
        todo.append(f'랩 DB에 현재 값(재고 · 예약 · 입고) 속성이 있습니다 — {", ".join(now)}. 현재 값은 그래프에 두지 않고 읽을 원천을 가리킵니다.')
    if any(x is None for x in new_ids):
        todo.append('랩 DB에 id가 없는 노드가 있습니다(새 대상도 ID로 찾아 다시 적재해도 늘지 않게 합니다).')
    present = headings()
    for nid in [x for x in new_ids if x]:
        ghost = sorted(lab for lab in labels_in(nid) if lab not in present)
        if ghost:
            todo.append(f'랩 DB 노드 {nid}: 원문에 절 머리가 없는 절 표기({", ".join(ghost)}) — 제공되지 않은 절은 노드로 만들지 않고 남은 질문으로 둡니다.')
        for doc in missing_docs():
            if doc in nid:
                todo.append(f'랩 DB 노드 {nid}: 받은 파일이 없는 문서({doc}) — 제공되지 않은 문서는 노드로 만들지 않고 남은 질문으로 둡니다.')


def check_export(todo):
    path = RESULT / '지식_내보내기.json'
    if not path.is_file():
        print('[4] 결과/지식_내보내기.json: 없음')
        todo.append('결과/지식_내보내기.json이 없습니다(python lab_cypher.py export 결과/지식_내보내기.json).')
        return
    try:
        data = json.loads(read(path))
        ids = [n['props'].get('id') for n in data['nodes']]
        dup = sorted({i for i in ids if ids.count(i) > 1 and i is not None})
        ends = set(ids)
        dangling = [r for r in data['rels'] if r.get('a') not in ends or r.get('b') not in ends]
        questions = data.get('remaining_questions')
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        todo.append(f'지식_내보내기.json의 꼴이 계약과 다릅니다({e}).')
        return
    print(f'[4] 결과/지식_내보내기.json: 노드 {len(ids)}개 · 관계 {len(data["rels"])}개 · 남은 질문 {len(questions or [])}개')
    if None in ids:
        todo.append('지식_내보내기.json에 id가 없는 노드가 있습니다.')
    if dup:
        todo.append(f'지식_내보내기.json에 같은 id의 노드가 둘 이상 — {", ".join(dup[:6])}')
    if dangling:
        todo.append(f'지식_내보내기.json에 끝점이 없는 관계 {len(dangling)}개 — 예: {dangling[0].get("type")} {dangling[0].get("a")} → {dangling[0].get("b")}')
    if not isinstance(questions, list):
        todo.append('지식_내보내기.json에 remaining_questions 목록이 없습니다.')
    else:
        for q in questions:
            if not isinstance(q, dict) or not q.get('item') or not q.get('note'):
                todo.append('remaining_questions의 항목마다 item과 note가 필요합니다.')
                break


def empty_tables(md):
    out, sec, width = {}, '머리', None
    for line in md.splitlines():
        if line.startswith('## '):
            sec, width = line[3:].strip(), None
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                out.setdefault(sec, [0, 0])
                continue
            if width is None:
                width = len(cells)
                continue
            out.setdefault(sec, [0, 0])
            out[sec][0] += 1
            out[sec][1] += sum(1 for c in cells if not c)
        elif not line.strip():
            width = None
    return out


def check_record(todo, n):
    record = RESULT / '구축_기록.md'
    print(f'[{n}] 구축_기록.md')
    if not record.is_file():
        todo.append('구축_기록.md가 없습니다.')
        return
    text = read(record)
    for line in text.splitlines():
        if re.match(r'^- [^:]+:[ \t]*$', line):
            todo.append(f'구축_기록.md의 빈 항목 「{line.strip()}」')
    for sec, (rows, blanks) in empty_tables(text).items():
        state = '표에 기록 없음' if rows == 0 else f'{rows}행' + (f', 빈 칸 {blanks}개' if blanks else '')
        print(f'    「{sec}」: {state}')
        if rows == 0 or blanks:
            todo.append(f'구축_기록.md 「{sec}」 — {state}(실제로 센 수 · 조회 결과로 채웁니다)')


def card_sources():
    out = []
    for f in sorted((HERE / '자료').iterdir()):
        if f.suffix in ('.md', '.txt', '.csv'):
            out.append((f.name, read(f)))
    return out


def check_card(path, docs, parts):
    errors, notes = [], []
    md = read(path)
    secs, cur = {}, None
    for line in md.splitlines():
        if line.startswith('## '):
            cur = line[3:].strip()
            secs[cur] = []
        elif cur is not None and line.strip():
            secs[cur].append(line)
    for h in HEADINGS:
        if h not in secs:
            errors.append(f'제목 「## {h}」 없음')
        elif not secs[h]:
            errors.append(f'「{h}」 아래가 비어 있음(없으면 「없음」과 까닭)')
    order = [h for h in secs if h in HEADINGS]
    if order != [h for h in HEADINGS if h in secs]:
        errors.append('제목의 순서가 계약과 다름')
    for h in ['준비 조건', '금지 · 제한', '작업 순서', '완료 기준']:
        for line in secs.get(h, []):
            if line.lstrip().startswith(('-', '*')) or re.match(r'^\s*\d+\.', line):
                if not QUOTE.search(line) and '없음' not in line:
                    errors.append(f'「{h}」 항목에 「원문 인용」이 없음: {line.strip()[:60]}')
    quotes = QUOTE.findall(md)
    for q in quotes:
        if not any(q in text for _, text in docs):
            errors.append(f'자료/ 어디에도 그대로 없는 인용: 「{q[:50]}」')
    for p in sorted(set(re.findall(r'\bP-[A-Z0-9]+(?:-[A-Z0-9]+)*', md))):
        if p not in parts:
            errors.append(f'설비 모델에 없는 품번 {p}')
    notes.append(f'인용 {len(quotes)}개')
    return errors, notes


def check_cards(todo):
    docs = card_sources()
    graph = json.loads(read(basis('모델/graph.json')))
    parts = {n['props']['id'] for n in graph['nodes'] if n['labels'][0] == 'Part'}
    cards = sorted(RESULT.glob('작업확인카드_*.md'))
    print(f'[6] 작업 확인 카드 {len(cards)}개')
    for c in cards:
        errors, notes = check_card(c, docs, parts)
        print(f'    {c.name}: {"형식 통과" if not errors else f"확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        for e in errors[:20]:
            print('      - ' + e)
        if errors:
            todo.append(f'{c.name} 형식 확인 필요.')
    if len(cards) < 2:
        todo.append('이 사건의 작업과 다른 작업 하나 이상의 카드가 필요합니다.')


def slot_errors():
    """정할 자리의 꼴 — 제공 코드(doc_graph.py)의 검사로 본다."""
    import doc_graph as G
    out = []
    known = G.model_ids()[0]
    for fn in (G.shape, lambda: G.link_rows(known), lambda: G.alias_rows(known), lambda: G.other_rows(known), G.role_rows, G.now_rows):
        try:
            fn()
        except G.Problem as e:
            out.append(f'정할 자리: {e}')
    return out


def main():
    todo = []
    known = known_ids()
    cands = reviews()
    print(f'[1] 기준 입력: {basis("검토결과").relative_to(HERE).as_posix()}(후보 {len(cands)}개, 승인 {sum(1 for c in cands if c[3] == "approved")}개) · '
          f'{basis("모델/graph.json").relative_to(HERE).as_posix()} · {basis("sop.json").relative_to(HERE).as_posix()} · {basis("조건표.csv").relative_to(HERE).as_posix()}')
    schema = RESULT / 'schema_ext.json'
    if not schema.is_file():
        todo.append('결과/schema_ext.json이 없습니다.')
    else:
        try:
            ext = json.loads(read(schema))
            print(f'    schema_ext.json: 종류 {len(ext.get("classes", {}))}개 · 관계 {len(ext.get("relations", {}))}개')
        except ValueError as e:
            todo.append(f'schema_ext.json을 읽지 못했습니다({e}).')
    check_loads(todo, known, cands)
    check_db(todo, known, cands)
    check_export(todo)
    check_record(todo, 5)
    if PRACTICAL:
        check_cards(todo)
    todo += slot_errors() + chosen_errors(HERE) + provided_errors(HERE)
    print()
    if todo:
        print('완료 아님 — 남은 것:')
        for t in todo:
            print('  - ' + t)
        print(END)
        return 1
    print('구조상 빠진 단계는 없습니다. ' + END)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as e:
        print('실행 확인 필요: ' + str(e))
        sys.exit(1)
'''


def graph_checker(key):
    practical = key == 'practical-03-card'
    return (GRAPH_CHECKER.replace('__PRACTICAL__', str(practical)).replace('__HEADINGS__', repr(CARD_HEADINGS))
            .replace('__CARD_DOC__', ' · 작업 확인 카드' if practical else ''))


WHY_SHAPE = ('스키마의 종류(이론의 클래스)는 그래프의 레이블이 되고, 대상 하나(이론의 인스턴스)를 저장한 것이 노드입니다. '
             'ID는 그래프 전체에서 하나여야 해서, ID를 어떻게 짓느냐에 따라 서로 다른 대상(문서가 다른 같은 번호의 절, 판이 다른 같은 문서)이 한 노드로 합쳐지거나 다시 적재할 때 늘어납니다.')
WHY_LINK = ('문서 속 대상은 모델과 다른 이름(설비 모델명 · 제조사 품번)으로 적혀 있어, 어느 기존 ID를 가리키는지 정해야 새 대상을 지어내지 않고 기존 ID에 잇습니다. '
            '승인한 것만 이어야 이 지식을 쓰는 쪽이 근거 있는 지식만 씁니다.')
WHY_AGAIN = 'CREATE는 실행할 때마다 새로 만들고 MERGE는 같은 ID가 있으면 찾으므로, ID가 맞아야 다시 넣어도 늘지 않습니다.'


def PG(N, rec, cols):
    """실전 카드 랩 단계 글(실전반 지침 P-9 — 앞 실습과 같은 도구 · 기본 조작은 되풀이하지 않고 판단 · 근거 · 결과 확인만)."""
    C = F.CHOSEN_FILE
    return {
        'db': dict(why='이 폴더 전용 랩 DB에서 하므로 포털에 영향이 없고, 먼저 수를 적어 두어야 뒤에서 늘어난 수를 셉니다.',
                   do=f'`python lab_db.py`로 랩 DB를 켜고 `{SHOW}`를 실행해 설비 모델 · 조치 기준의 종류별 수를 `{rec}` 「적재 수」 첫 줄에 적습니다.',
                   ask='주소가 `127.0.0.1`의 이 폴더 전용인지 봅니다.', evidence=f'「랩 DB 준비 완료」가 나오고 1단계 수를 적었습니다.',
                   hint=H('랩 DB를 켜고 앞 판을 올려 센다', '`lab_db.py`, `입력/`', '포털 DB에 접속하지 않는다', '「적재 수」 첫 줄', '`입력/` 파일에서 센 수와 견준다'),
                   differ=''),
        'expect': dict(why='조회 결과를 본 뒤에 기대를 적으면 빠진 연결이 기대에 맞춰 사라집니다.',
                       do=f'`결과/기대_답.csv`에 카드 항목마다 기대를 원문 · 검토 결과의 파일:줄로, `{rec}`에 목표 · 쓰는 사람 · 기대 칸을 쓴 시각을 적습니다.' + F.REQ_AFTER,
                       ask='기대를 1단계 승인 후보와 원문 줄에서 찾습니다.', evidence=f'{N["expect"]}단계에 기대와 근거마다 원문 줄이 보입니다.',
                       hint=H('조회 전에 카드 기대를 적는다', '결과 화면, `자료/` 원문, `입력/검토결과/선택작업_조건.json`', 'AI 출력을 기대로 옮기지 않는다.' + cols('기대_답.csv'), '`결과/기대_답.csv`의 행', f'{N["expect"]}단계 표'),
                       differ='원문 글자가 깨져 보이면 VS Code 오른쪽 아래 **UTF-8** → **Reopen with Encoding → Korean (EUC-KR)**으로 엽니다.'),
        'plan': dict(why='ID를 어떻게 짓느냐에 따라 다른 대상이 한 노드로 합쳐지거나 다시 적재할 때 늘어납니다.',
                     do=f'`결과/그래프_모양.json`에 문서 · 판 · 절 · 지식과 관계의 이름 · 뜻 · ID 꼴을 정하고 까닭을 `{C}`에 적은 뒤 `{SHOW}`로 적재 없이 센 수를 봅니다.',
                     ask='무엇으로 같은 대상을 알아볼지(ID) 정합니다.', evidence=f'{N["plan"]}단계에 지을 노드 수가 보이고 겹침이 없습니다.',
                     hint=H('모양과 ID 꼴을 정한다', '`입력/모델/schema.json`, 계약 「정할 자리」', '기존 종류 이름을 다른 뜻으로 쓰지 않는다. 다시 적재해도 늘지 않게', '`결과/그래프_모양.json` · 정한 것 한 줄', f'{N["plan"]}단계 겹침 목록'),
                     differ='「같은 ID에 서로 다른 대상이 겹침」이면 ID 꼴에 빠진 자리(문서 · 판)를 더합니다. 지식을 조치에 잇는 관계는 다음 단계 연결 규칙에서 정합니다.'),
        'link': dict(why='승인한 것만 기존 ID에 이어야 카드가 근거 있는 지식만 씁니다.',
                     do=f'`결과/연결_규칙.csv`에 카드에 닿는 문서(와 절)의 승인 후보를 어느 기존 ID에 이을지, 필요하면 `결과/별칭.csv` · `결과/역할.csv`를 적고 `{SHOW}`로 적재합니다.',
                     ask='문서마다 잇는 방법과 그 근거를 정합니다.', evidence=f'{N["link"]}단계에 적재 전후 수와 「핀 세척과 그 단계에 이은 지식」 표가 보이고, 몇 행을 원문 줄로 확인했습니다.',
                     hint=H('승인 후보를 기존 ID에 잇는 규칙을 정한다', '결과 화면, `입력/모델/graph.json` · `입력/sop.json`, 원문', '승인 후보만, 모델에 없는 ID를 지어내지 않는다.' + cols('연결_규칙.csv') + ' 별칭' + cols('별칭.csv') + ' 역할' + cols('역할.csv'),
                            '세 표의 행', f'{N["link"]}단계 표'),
                     differ='빨간 칸의 파일:줄을 고칩니다.'),
        'other': dict(why='다른 문서의 조건은 그 문서의 적용 범위와 이 작업을 말하는 사내 문장이 어긋날 수 있어 사람이 정합니다.',
                      do=f'핀 세척에 걸 다른 문서의 조건(시간 · 승인 · 준비)을 `결과/다른문서_조건.csv`에 잇는다 · 잇지 않는다로, 고른 것을 `{C}`에 적고 `{SHOW}`를 두 번 실행해 수가 늘지 않는지 봅니다.',
                      ask='적용 범위 절과 이 작업을 말하는 사내 문장을 열어 정하고, 잇지 않는 문장도 「아니오」 행으로 남깁니다.',
                      evidence=f'{N["other"]}단계에 고른 행 · 근거 원문 줄이 보이고 두 번째 수가 직전과 같습니다.',
                      hint=H('다른 문서의 조건을 이을지 정한다', '원문, 결과 화면', '이 작업에 걸 조건만 정한다.' + cols('다른문서_조건.csv'), '`결과/다른문서_조건.csv` · 정한 것 한 줄', '두 번 실행 — 수가 같음'),
                      differ='두 번째에 수가 늘면 ID 꼴을 고칩니다.'),
        'card': dict(why='기준값은 문서에서, 작업 직전의 현재 값은 원천에서 오므로 섞지 않습니다.',
                     do=f'`결과/질문_값.csv`에 물을 작업 · 절을, `결과/현재값_원천.csv`에 확인할 현재 값과 원천을 적고 `{SHOW}`로 `결과/작업확인카드_{TASK}.md`를 기대와 견줘 `{rec}`에 적습니다.',
                     ask='작업 직전에 다시 볼 값과 그 원천을 정합니다(값은 적지 않음).', evidence=f'{N["card"]}단계 카드의 준비 · 금지 · 순서 · 완료마다 원문 인용이 있고, 현재 값 칸에는 원천 이름만 있습니다.',
                     hint=H('카드를 만들고 현재 값은 읽을 곳만 적는다', '결과 화면, `결과/기대_답.csv`, 원문', '현재 값 · 승인을 추정으로 채우지 않는다. 질문 값' + cols('질문_값.csv') + ' 현재 값' + cols('현재값_원천.csv'),
                            '두 표의 행', '카드 항목 몇 개를 원문 줄로 연다'),
                     differ=F.FIX_LOOP),
        'other_scope': dict(why='같은 방법이 다른 작업에도 통하고 없는 것에 「결과 없음」을 돌려줘야 기능입니다.',
                            do=f'`{SHOW}`로 다른 작업의 카드 · 제공되지 않은 작업과 절 · 남은 질문을 보고 `{rec}` 「다른 작업 · 제공되지 않은 것」과 「답할 수 있는 것과 없는 것」에 적습니다.',
                            ask='질문마다 그래프로 답함 · 현재 값 · 승인 · 공급 정보 · 원문에 없음 가운데 어느 쪽인지와 근거를 말합니다.',
                            evidence=f'{N["other_scope"]}단계에 두 번째 카드 · 「찾은 수 0」 · 남은 질문 수가 보이고 두 표에 근거가 있습니다.',
                            hint=H('다른 작업 · 없는 것에 대 보고 답할 범위를 나눈다', '`입력/조치검토결과.json`의 `review`, `자료/문서_목록.csv`', '원문에 없는 작업 · 절을 만들지 않는다', '기록 두 표', '문서 목록과 원문 목차를 직접 본다'),
                            differ=F.FIX_LOOP),
        'save': dict(why=F.WHY_SAVE,
                     do=f'`{SHOW}`의 마지막 단계가 내보내기와 `python check.py`를 돌립니다. 저장 뒤 폴더를 닫았다 다시 열어 `python lab_db.py` · `{SHOW}`를 다시 실행하고 `{rec}` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
                     ask='확인하지 못한 점으로 무엇을 남길지 정합니다.', evidence='다시 연 뒤에도 수와 카드가 같고, 마지막 단계의 check.py 출력에 「구조상 빠진 단계는 없습니다」가 있습니다.', cmd=f'python lab_db.py\n{SHOW}',
                     hint=H('내보내고 다시 열어 같은지 본다', '결과 화면, 「저장 기록」', '내보내기를 손으로 고치지 않는다', '저장 기록', '다시 연 뒤 수를 앞과 견준다'),
                     differ='「이 PC의 Docker에 없습니다」면 새 빈 랩 DB이니 `python show_result.py`가 다시 적재합니다.'),
    }


def graph_steps(key):
    practical = key == 'practical-03-card'
    base = FL.graph_files('가', practical)
    order = gstep_order(key)
    import collections
    N = collections.defaultdict(str, {k: i for i, k in enumerate(order, 1)})   # 이 반에 없는 단계의 글은 쓰지 않는다
    rec = GREC
    links_all = base['연결_규칙.csv']
    if practical:
        links_first = links_all
    else:
        rows = list(csv.reader(io.StringIO(links_all)))
        links_first = FL.csv_text(rows[0], [r for r in rows[1:] if r[0] not in LATER_DOCS])
    blanks = graph_blanks(key)
    def tog(name, text):
        return ghead(blanks['결과/' + name], text)
    def cols(name):
        return ' 칸 — ' + gcols(name, practical)
    links_first, links_all = tog('연결_규칙.csv', links_first), tog('연결_규칙.csv', links_all)
    other_rows = [tog('다른문서_조건.csv', FL.csv_text(['문서', '판', '절', '인용에_든_글자', '작업', '잇는다', '관계', '근거'], FL.OTHER[p])) for p in ('가', '나')]
    values = tog('질문_값.csv', base['질문_값.csv'])
    T = {n: tog(n, base[n]) for n in ('별칭.csv', '역할.csv', '현재값_원천.csv')}
    chosen = list(csv.reader(io.StringIO(base['정한_것.csv'])))[1:]
    def chosen_csv(idx):
        return chosen_upto(FL.csv_text(F.CHOSEN_COLUMNS, [chosen[i] for i in idx]).splitlines(keepends=True)[1:])
    S_ = {}
    S_['look'] = S('폴더 · 입력 파악', '① 파악',
                   f'터미널에서 `{SHOW}`를 실행해 결과 화면을 엽니다. 검토 결과마다 승인 · 보류 · 제외 수와 조건 근거 대조, 기존 ID 수, 승인 후보 찾아보기 표를 보고, AI에게 파일을 바꾸지 말고 후보가 가리키는 대상이 설비 모델 · SOP 구조 · 조건표의 어느 ID인지 물어 짚은 ID를 모델 파일에서 직접 엽니다.',
                   '이 답을 쓰는 사람과 해결할 질문, 후보가 가리키는 대상(설비 · 구성 요소 · 부품 · SOP · 단계 · 규칙)이 어느 기존 ID인지 묻습니다.',
                   '결과 화면 1단계에 검토 결과 표 · 기존 ID 수 · 승인 후보 찾아보기가 보입니다. ' + F.EVIDENCE_LOOK,
                   H('무엇을 어디에 이을지 파악한다', '결과 화면 1단계, `입력/` 전부, `자료/문서_목록.csv`', '파일을 바꾸지 않는다. 짚을 때는 파일:줄 또는 ID를 먼저 댄다',
                     '후보 대상 ↔ 기존 ID 짝 몇 개', '짚은 ID를 `입력/모델/graph.json` · `입력/sop.json`에서 직접 연다'),
                   cmd=SHOW, why=F.WHY_START + ' 문서 속 대상은 모델의 ID와 다른 이름 · 번호로 적혀 있을 수 있어, 어느 기존 ID를 가리키는지 먼저 봅니다.', differ=F.DIFFER_LOOK)
    S_['expect'] = S('기대 카드 먼저' if practical else '질문과 기대 답 먼저', '② 요구',
                     (f'`결과/기대_답.csv`에 핀 세척 카드의 항목(준비 · 금지 · 순서 · 완료 · 작업 직전 확인할 현재 값 · 승인 · 남은 질문)마다 기대를 원문 · 검토 결과의 파일:줄로 적고' if practical else
                      f'`결과/기대_답.csv`에 질문 1 · 2의 기대 답을 문서 · 절로, 질문 3은 읽을 원천 이름으로 적고(근거는 파일:줄)') +
                     f' `{rec}`에 목표 · 쓰는 사람 · 기대 칸을 쓴 시각을 적습니다.' + F.REQ_AFTER,
                     '기대를 결과 화면 1단계의 승인 후보 찾아보기와 원문 줄에서 찾습니다. 「학생이 정할 것」은 내가 고릅니다.',
                     '결과 화면 2단계에 내 기대와 근거마다 첫 원문 줄이 보이고, 그 줄이 내가 적은 내용입니다. 기대 칸을 쓴 시각이 있습니다. AI의 되짚기가 내 뜻과 같고 바뀐 파일이 없습니다.',
                     H('조회 전에 기대를 원문 · 검토 결과에서 적는다', '결과 화면 1단계의 승인 후보 찾아보기, `자료/`의 원문' + (', `입력/검토결과/선택작업_조건.json`' if practical else ''),
                       'AI 출력을 기대로 옮기지 않는다. 후보 id까지 적지 않아도 된다 — 문서 · 절 · 줄로 적는다.' + cols('기대_답.csv'), '`결과/기대_답.csv`의 행', f'`{SHOW}` — 2단계 표'),
                     cmd=SHOW, why='질문이 모델의 범위를 정합니다. 조회 결과를 본 뒤에 기대를 적으면 빠진 연결이 기대에 맞춰 사라지므로, 원문과 검토 결과로 먼저 적어 둡니다.',
                     differ=F.DIFFER_REQ.format(rec='결과/기대_답.csv') + ' 원문 글자가 깨져 보이면 VS Code 오른쪽 아래 **UTF-8**을 눌러 **Reopen with Encoding → Korean (EUC-KR)**으로 다시 엽니다.',
                     answer=A('기대는 문서 · 절 수준으로 적습니다 — 핀 세척의 준비 · 금지 · 완료 · 승인은 사내 현행 매뉴얼 HM-8.7 · SOP-COOL-14와 그 줄, 규칙은 검토 결과의 조건 근거 대조에서 옵니다.',
                              F.paste('결과/기대_답.csv', tog('기대_답.csv', FL.EXPECT_CARD if practical else FL.EXPECT_GRAPH))))
    S_['db'] = S('랩 DB 준비와 설비 모델 · 조치 기준 적재' if not practical else '새 폴더 · 랩 DB 준비',
                 '④ 구현' if False else '① 파악',
                 ('VS Code로 이 실습 폴더를 엽니다. ' if practical else '') + f'터미널에서 `python lab_db.py`로 이 폴더 전용 랩 DB를 켜고 `{SHOW}`를 실행합니다 — 설비 모델과 조치 기준(SOP 구조 · 조건표)이 랩 DB에 올라가고 종류별 수가 보입니다.',
                 '출력된 주소가 `127.0.0.1`의 이 폴더 전용 주소인지 확인합니다.',
                 f'「랩 DB 준비 완료」와 주소가 나왔고, 결과 화면 {N["db"]}단계의 종류별 수를 `{rec}` 「적재 수」 첫 줄에 적었습니다.',
                 H('이 폴더 전용 랩 DB를 켜고 앞 단계 판을 올려 센다', '`lab_db.py`, `입력/모델/` · `입력/sop.json` · `입력/조건표.csv`', '포털 DB에 접속하지 않는다. 명령은 내가 터미널에서 실행한다',
                   f'결과 화면의 수와 `{rec}` 「적재 수」 첫 줄', '종류별 수를 `입력/` 파일에서 센 수와 견준다'),
                 cmd=f'python lab_db.py\n{SHOW}',
                 why='이 실습의 적재 · 조회는 이 폴더에만 딸린 그래프 DB(별도 랩 DB)에서 합니다. 포털 DB와 떨어져 있어 여러 번 넣어도 포털에 영향이 없고, 먼저 수를 적어 두어야 뒤에서 늘어난 수가 이번에 넣은 것임을 셀 수 있습니다.',
                 differ='결과 화면에 「랩 DB 꺼짐」이 나오면 `python lab_db.py`가 「랩 DB 준비 완료」까지 갔는지 보고, Docker Desktop이 켜져 있는지 봅니다.')
    S_['plan'] = S('판단① 그래프 모양 — 종류 · 관계 · ID', '③ 계획 · 판단',
                   f'`결과/그래프_모양.json`에 문서 · 판 · 절 · 지식과 그 관계의 이름 · 뜻, 판을 따로 둘지, 새 대상의 ID를 짓는 꼴을 정하고 그 까닭을 `{F.CHOSEN_FILE}`에 적은 뒤 `{SHOW}`로 적재하지 않고 센 결과를 봅니다.',
                   '문서 근거를 어떤 종류 · 관계로 담고, 무엇으로 같은 대상을 알아볼지(ID) 정합니다. AI에게는 처음 정한 질문 하나를 이 모양에 대어 어느 노드 · 관계를 따라 답이 나오는지 짚게 합니다.',
                   f'결과 화면 {N["plan"]}단계에 지을 노드 수가 보이고 「같은 ID에 서로 다른 대상이 겹침」이 없습니다. 적재하지 않는 보류 · 제외 수가 보입니다.',
                   H('문서 근거를 담을 모양과 ID 꼴을 정한다', '`입력/모델/schema.json`, `입출력_계약.md` 「정할 자리」, 결과 화면 1단계', '기존 종류 이름을 다른 뜻으로 쓰지 않는다. 현재 값을 그래프에 넣지 않는다. 다시 적재해도 늘지 않게 ID를 짓는다',
                     '`결과/그래프_모양.json`, `결과/정한_것.csv` 한 줄', f'`{SHOW}` — {N["plan"]}단계의 겹침 목록'),
                   cmd=SHOW, why=WHY_SHAPE, differ='「같은 ID에 서로 다른 대상이 겹침」이 나오면 그 ID들이 어느 문서 · 판 · 절인지 보고 ID 꼴에 빠진 자리를 더합니다. ' + F.DIFFER_PLAN,
                   answer=A('강사 판은 문서 · 판 · 절 · 지식을 따로 두고 ID에 문서와 판을 넣습니다(절 = 문서@판#절, 지식 = 문서@판:후보) — 다른 문서의 같은 절 번호가 겹치지 않습니다.',
                            F.paste('결과/그래프_모양.json', base['그래프_모양.json']), apply={'결과/그래프_모양.json': base['그래프_모양.json'], F.CHOSEN_FILE: chosen_csv([1])}))
    S_['link'] = S('판단② 연결 규칙 · 별칭 · 역할', '④ 구현 · 판단',
                   f'`결과/연결_규칙.csv`에 검토 결과의 문서마다(필요하면 절마다) 승인 후보를 어느 기존 ID에 어떤 관계로 이을지, `결과/별칭.csv`에 원문의 이름 · 품번이 가리키는 기존 ID, `결과/역할.csv`에 조치에 잇는 지식의 항목을 적고 `{SHOW}`로 적재합니다.'
                   + ('' if practical else ' 제조사 지침과 예비품 기준의 행은 다른 문서 추가 단계에서 채웁니다.'),
                   '문서마다 잇는 방법(절차 표기와 같은 조치 · 정한 대상 · 별칭 · 잇지 않음)과 그 근거를 정합니다. 기존 ID를 찾지 못한 대상은 무엇으로 남길지 정합니다.',
                   f'결과 화면 {N["link"]}단계에 적재 전후 수와 기존 ID에 이은 지식 수가 보이고, 「모델에 없는 ID」 오류가 없습니다. 「핀 세척과 그 단계에 이은 지식」 표의 몇 행을 그 줄 번호로 원문에서 열어 확인했습니다.',
                   H('승인 후보를 출처 절과 기존 ID에 잇는 규칙을 정한다', '결과 화면 1단계, `입력/모델/graph.json` · `입력/sop.json` · `입력/조건표.csv`, 원문', '승인 후보만 잇는다. 모델에 없는 ID를 지어내지 않는다. 현재 값을 넣지 않는다.' + cols('연결_규칙.csv') + ' 별칭' + cols('별칭.csv') + ' 역할' + cols('역할.csv'),
                     '`결과/연결_규칙.csv` · `결과/별칭.csv` · `결과/역할.csv`의 행', f'`{SHOW}` — {N["link"]}단계 수, 이은 지식 몇 개를 원문 줄로'),
                   cmd=SHOW, why=WHY_LINK, differ='빨간 칸의 파일 · 행 번호를 고칩니다. 「역할.csv에 맞는 행이 없어」가 나오면 그 종류의 행을 더합니다. ' + F.FIX_LOOP,
                   answer=A('강사 판 — 사내 현행 매뉴얼은 절차 표기와 같은 조치에, 절차 밖 절은 원격 조치 셋 · 고장 유형에, 원인 절은 본문의 원인 이름으로, 스캔본 · 규정은 출처 절에만(규정은 조건 근거로), 다른 문서는 본문의 설비 · 부품 이름으로 잇습니다.',
                            F.paste('결과/연결_규칙.csv', links_first), F.paste('결과/별칭.csv', T['별칭.csv']), F.paste('결과/역할.csv', T['역할.csv']),
                            apply={'결과/연결_규칙.csv': links_first, '결과/별칭.csv': T['별칭.csv'], '결과/역할.csv': T['역할.csv'], F.CHOSEN_FILE: chosen_csv([1, 2])}))
    S_['other'] = S('판단③ 다른 문서의 조건 · 반복 적재', '④ 판단',
                    f'핀 세척(`{TASK}`)에 걸 다른 문서의 조건(시간 · 승인 · 준비)을 찾아 `결과/다른문서_조건.csv`에 잇는다 · 잇지 않는다와 근거를 적고 고른 것을 `{F.CHOSEN_FILE}`에 적은 뒤 `{SHOW}`를 두 번 실행해, 두 번째에도 수가 늘지 않는지 봅니다.',
                    '다른 문서가 정한 조건을 이 작업에 이을지 — 그 문서의 적용 범위 절과, 이 작업을 말하는 사내 문장을 원문으로 열어 정합니다. 후보가 여러 문서에서 나오면 이 작업을 언제 · 누가 승인해 · 무엇을 갖추고 하는지 정하는 문장만 행으로 적고, 보고도 잇지 않기로 한 문장은 「아니오」 행으로 남깁니다.',
                    f'결과 화면 {N["other"]}단계에 고른 행과 그 근거 원문 줄이 보이고, 두 번째 실행의 수가 직전 실행과 같습니다(같음 표시). `{rec}` 「적재 수」에 두 줄이 있습니다.',
                    H('다른 문서의 조건을 이 작업에 이을지 정하고, 같은 적재를 다시 해도 수가 같은지 본다', '원문(다른 문서의 적용 범위 절 · 이 작업을 말하는 사내 문장), 결과 화면', '이 작업(핀 세척)에 걸 조건만 정한다. 지우는 문장으로 수를 맞추지 않는다.' + cols('다른문서_조건.csv'),
                      '`결과/다른문서_조건.csv`의 행, `결과/정한_것.csv` 한 줄', f'`{SHOW}` 두 번 — 수가 같음'),
                    cmd=SHOW, why=WHY_AGAIN + ' 다른 문서의 조건은 그 문서의 적용 범위와 이 작업을 말하는 사내 문장이 어긋날 수 있어 사람이 정합니다.',
                    differ='두 번째에 수가 늘었으면 늘어난 종류를 보고 ID 꼴을 고칩니다(그래프 모양 단계). 랩 DB를 새로 준비하려면 그 폴더의 랩 DB 컨테이너를 지우고 `python lab_db.py`부터 다시 합니다.',
                    answer=A('갈래 가(정기 점검표의 예정된 정비 시간 조건을 핀 세척 준비로 잇는다 — 사내 매뉴얼이 같은 말을 씀) · 나(잇지 않는다 — 그 문서의 범위는 정기 정비) 가운데 하나를 고르고 근거를 적습니다.',
                             F.paste('결과/다른문서_조건.csv', other_rows[0]), F.paste('결과/다른문서_조건.csv', other_rows[1]),
                             apply={'결과/다른문서_조건.csv': other_rows[0], F.CHOSEN_FILE: chosen_csv([1, 2, 0])}))
    S_['ask123'] = S('판단④ 질문 1 ~ 3 조회와 보류 확인', '④ 구현 · 판단',
                     f'`결과/질문_값.csv`에 질문 1 · 3에 넣을 설비 · 작업과 확인할 보류 후보 둘(검토 결과 파일#후보 id)을 적고 `{SHOW}`로 조회 결과를 봅니다. 기대와 같음 · 다름과 까닭을 `{rec}` 「질문별 기대와 실제」에 적고, Neo4j Browser로 한 번 모양을 봅니다.',
                     '물을 값을 무엇으로 할지와, 결과가 기대와 다를 때 원인이 연결 규칙 · 그래프 모양 중 어디인지 묻습니다.',
                     f'결과 화면 {N["ask123"]}단계에 질문 1 · 2 · 3 결과와 보류 조회(찾은 수 0)가 보이고, 기록에 같음 · 다름과 까닭이 있습니다. `결과/query.cypher`가 생겼습니다.',
                     H('처음 정한 질문을 그래프로 답하고 기대와 견준다', '결과 화면, `결과/기대_답.csv`, `입력/검토결과/`(보류 후보)', '조회만 한다. 원자료를 다시 읽어 답을 만들지 않는다.' + cols('질문_값.csv'),
                       '`결과/질문_값.csv`의 행, 기록의 같음 · 다름', '결과 항목 몇 개를 원문 인용으로 직접 연다'),
                     cmd=f'{SHOW}\npython lab_cypher.py query 결과/query.cypher <번호> --param <이름>=<값>',
                     run=('터미널로 한 질문만 다시 볼 때는 `결과/query.cypher`에서 그 질문(`// 질문 <번호>`) 아래 `// 터미널:` 줄의 명령을 복사해 실행합니다 — 꼴은 아래 블록 둘째 줄이고, '
                          '값이 여럿(보류 후보)이면 빈칸으로 이어 `--param "ids=<파일#id> <파일#id>"`처럼 큰따옴표로 감쌉니다. 출력 「-- 질문 <번호> (결과/query.cypher:<줄>)」 아래 표가 결과 화면의 같은 질문 표와 같아야 합니다. '
                          'Neo4j Browser로 볼 때는 그 질문의 `// Browser:` 줄에서 `:param …` 부분만 먼저 붙여 넣어 실행한 뒤 그 아래 조회문을 붙여 넣어 **Run**을 누릅니다.'),
                     why='조회가 성공했다고 답이 맞는 것은 아니므로, 결과 항목을 원문 인용으로 돌아가 견줍니다. 보류는 버린 것이 아니라 근거가 더 필요하다는 기록이라 그래프에 없어야 합니다.',
                     differ=F.FIX_LOOP,
                     answer=A('설비는 HYD-02, 작업은 핀 세척, 보류 후보는 스캔본 · 제조사 지침의 보류 후보 하나씩입니다.', F.paste('결과/질문_값.csv', values)))
    S_['more'] = S('다른 문서 추가 반영과 기존 연결 비교', '④ 구현 · 판단',
                   f'`결과/연결_규칙.csv`에 제조사 지침과 예비품 기준의 행을, 필요하면 `결과/별칭.csv`에 설비 모델명 · 제조사 품번을 더하고 `{SHOW}`를 실행합니다. 추가 전 그래프와 견준 수(속성이 바뀐 기존 노드 · 사라진 관계)와 질문 1 · 4를 보고 `{rec}` 「다른 문서 추가 뒤 기존 연결」에 적습니다.',
                   '설비 모델명 · 제조사 품번으로 적힌 대상이 어느 기존 ID인지, 추가로 바뀐 기존 연결이 있다면 왜인지 묻습니다.',
                   f'결과 화면 {N["more"]}단계에 늘어난 수와 「속성이 바뀐 기존 노드 0 · 사라진 관계 0」(또는 그 목록)이 보이고, 질문 1에서 늘어난 행을 원문으로 설명할 수 있습니다.',
                   H('다른 문서를 더하고 앞의 연결이 그대로인지 본다', '결과 화면, 더할 문서의 원문, `입력/모델/graph.json`', '기존 연결을 지우거나 덮지 않는다. 별칭은 원문 줄을 근거로 적는다',
                     '`결과/연결_규칙.csv` · `결과/별칭.csv`에 더한 행, 기록 표', f'`{SHOW}` — 추가 전후 비교 수'),
                   cmd=SHOW, why='여러 문서가 같은 대상을 말할 때, 뒤에 넣은 문서가 앞의 연결을 덮거나 같은 번호의 다른 절을 같은 대상으로 합치면 앞에서 맞던 답이 바뀝니다. 더한 뒤 기존 노드 · 관계를 견주어야 반영 범위를 압니다.',
                   differ='「추가 전 내보내기가 없습니다」가 나오면 다른 문서의 행을 앞 단계에서 이미 채운 것입니다 — 그 경우 견줄 기준이 없다고 기록합니다. ' + F.FIX_LOOP,
                   answer=A('제조사 지침은 모델명으로 세 설비에, 코어 세척 절은 핀 세척 조치에, 예비품 기준은 품번 · 부품 이름으로 잇습니다.', F.paste('결과/연결_규칙.csv', links_all)))
    S_['card'] = S('판단④ 작업 확인 카드 — 현재 값을 읽을 원천', '④ 구현 · 판단',
                   f'`결과/질문_값.csv`에 카드를 만들 작업(`card sop`)과 다른 작업 · 제공되지 않은 작업 · 절의 값을, `결과/현재값_원천.csv`에 작업 직전 확인할 현재 값과 읽을 원천을 적고 `{SHOW}`로 `결과/작업확인카드_{TASK}.md`를 봅니다. 기대와 같음 · 다름을 `{rec}`에 적습니다.',
                   '작업 직전에 다시 볼 현재 값이 무엇이고 그 값을 어느 시스템에서 읽는지 정합니다(값은 적지 않습니다). 카드 항목마다 무엇을 근거로 넣었는지 말합니다.',
                   f'결과 화면 {N["card"]}단계에 카드가 보이고 준비 · 금지 · 순서 · 완료 항목마다 원문 인용이 있습니다. 현재 값 칸에 원천 이름만 있고, 승인은 원문의 역할입니다.',
                   H('조회 결과로 카드를 만들고 현재 값은 읽을 곳만 적는다', '결과 화면, `결과/기대_답.csv`, `입력/sop.json`의 센서 연결, 원문', '현재 값 · 승인을 추정으로 채우지 않는다. 카드는 승인을 대신하지 않는다. 질문 값' + cols('질문_값.csv') + ' 현재 값' + cols('현재값_원천.csv'),
                     '`결과/질문_값.csv` · `결과/현재값_원천.csv`의 행', '카드 항목 몇 개를 원문 줄로 연다'),
                   cmd=SHOW, why='카드의 기준값은 문서에서 오고, 작업 직전의 현재 값은 시계열 · CMMS · ERP · MES 같은 원천에서 옵니다. 카드에는 기준값과 그 값을 읽을 원천을 나란히 두되 섞지 않아야 작업자가 무엇을 지금 다시 봐야 하는지 압니다.',
                   differ=F.FIX_LOOP,
                   answer=A('현재 값은 냉각 효율 · 유온(시계열), PLC 운전 모드(PLC 상태 수신)이고, 다른 문서의 조건을 이었다면 생산 오더가 없는 시간(MES 생산 계획)도 더합니다.',
                            F.paste('결과/질문_값.csv', values), F.paste('결과/현재값_원천.csv', T['현재값_원천.csv'])))
    S_['card_other'] = S('다른 작업 카드 · 제공되지 않은 작업 · 절', '⑤ 대조',
                         f'`{SHOW}`로 다른 작업(사건 경보의 검토 의견이 먼저 검토할 후보로 둔 작업)의 카드와, 제공되지 않은 작업 · 절의 조회를 보고 `{rec}` 「다른 작업 · 제공되지 않은 것」에 적습니다.',
                         '다른 작업의 SOP ID가 `입력/조치검토결과.json`의 어느 값에서 왔는지, 제공되지 않은 것을 무엇으로 알아봤는지 말합니다.',
                         f'결과 화면 {N["card_other"]}단계에 두 번째 카드와 「찾은 수 0」 조회가 보입니다. 같은 방법으로 다른 작업의 카드가 만들어졌습니다.',
                         H('같은 방법을 다른 작업과 없는 것에 대어 본다', '`입력/조치검토결과.json`의 `review`, `자료/문서_목록.csv`, 원문 목차', '원문에 없는 작업 · 절을 만들지 않는다',
                           f'`{rec}` 표', '문서 목록의 파일 칸과 원문 목차를 직접 본다'),
                         cmd=SHOW, why='같은 방법이 다른 작업에도 통해야 기능입니다. 원문이 없는 것을 물었을 때 「결과 없음」과 「조회가 틀림」을 구별해 보여야 그 답을 믿고 쓸 수 있습니다.', differ=F.FIX_LOOP)
    S_['scope'] = S('답할 수 있는 것과 현재 값 · 승인 · 공급 정보' if practical else '답할 수 있는 것과 현재 값 · 추가 자료가 필요한 것', '⑤ 대조',
                    (f'`결과/현재값_원천.csv`를 다시 보고 `{SHOW}`로 남은 질문을 쓴 뒤, 질문마다 그래프로 답하는지, 현재 값 · 승인이 있어야 하는지, 공급 조건(설비 모델의 부품 · 공급사)과 그날의 재고를 어디까지 답하는지 `{rec}` 「답할 수 있는 것과 없는 것」에 적습니다.' if practical else
                     f'`결과/현재값_원천.csv`에 핀 세척 전에 확인할 현재 값과 읽을 원천을 적고 `{SHOW}`로 질문 3 · 5와 남은 질문을 본 뒤, 질문마다 그래프로 답하는지 · 현재 값 · 추가 자료가 필요한지 · 원문에 없는지를 `{rec}` 「답할 수 있는 것과 없는 것」에 적습니다.'),
                    '질문마다 어느 쪽인지와 그 근거(원천 이름 · 파일)를 말합니다.',
                    f'결과 화면 {N["scope"]}단계에 현재 값 · 원천 표와 남은 질문 수가 보이고, 기록 표에 질문마다 분류와 근거가 있습니다.',
                    H('질문마다 답할 수 있는 범위를 나눈다', '결과 화면, `입력/sop.json`의 센서 연결, `입력/모델/graph.json`', '현재 값을 추정으로 채우지 않는다.' + ('' if practical else cols('현재값_원천.csv')), f'`{rec}` 표' + ('' if practical else ', `결과/현재값_원천.csv`'), '원천 이름을 다시 본다'),
                    cmd=SHOW, why='문서의 판단 기준은 그래프에 있지만, 작업 직전의 센서 값 · 작업지시 상태 · 재고는 시계열 · CMMS · ERP · MES에서 읽어야 합니다. 그래프가 무엇에 답하고 무엇에 답하지 못하는지 밝혀 두어야 이 지식을 쓰는 쪽이 읽을 곳을 압니다.',
                    differ=F.FIX_LOOP, answer=None if practical else A('현재 값은 냉각 효율 · 유온(시계열), PLC 운전 모드, 생산 오더가 없는 시간(MES)입니다.', F.paste('결과/현재값_원천.csv', T['현재값_원천.csv'])))
    S_['save'] = S('내보내기 · 저장하고 다시 열기', '⑥ 고침 · ⑦ 저장 · 다시 열기',
                   f'`{SHOW}`의 마지막 단계가 `결과/지식_내보내기.json`을 쓰고 `python check.py`를 돌립니다. 짚은 문제를 고친 뒤, 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 열어 `python lab_db.py`와 `{SHOW}`를 다시 실행합니다. `{rec}` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
                   '확인하지 못한 점으로 무엇을 남길지 정합니다.',
                   f'다시 연 뒤에도 수와 조회 결과가 같고, 마지막 단계의 check.py 출력에 「구조상 빠진 단계는 없습니다」가 있습니다. 내보내기의 노드 · 관계 수가 랩 DB 수와 같습니다.',
                   H('다음 실습에 넘길 판을 내보내고 다시 열어 같은지 본다', f'결과 화면, `{rec}` 「저장 기록」', '내보내기 파일을 손으로 고치지 않는다. 확인하지 못한 것은 확인하지 못했다고 적는다',
                     f'`{rec}`의 저장 기록', '다시 연 뒤 결과 화면의 수 · 조회 결과를 앞과 견준다'),
                   cmd=f'python lab_db.py\n{SHOW}\npython check.py', why='학교 PC는 재부팅하면 초기화될 수 있습니다. 폴더를 닫았다 다시 연 뒤 랩 DB를 다시 켜도 같은 수와 조회 결과가 나와야 저장된 것입니다.',
                   differ='「이 PC의 Docker에 없습니다」 줄이 나왔다면 새 빈 랩 DB를 만든 것입니다 — `python show_result.py`가 정할 자리대로 다시 적재합니다.')
    S_['other_scope'] = S('다른 작업 카드와 답할 수 있는 범위', '⑤ 대조',
                          f'`{SHOW}`로 다른 작업(사건 경보의 검토 의견이 먼저 검토할 후보로 둔 작업)의 카드, 제공되지 않은 작업 · 절의 조회, 남은 질문을 보고 `{rec}` 「다른 작업 · 제공되지 않은 것」과 '
                          '「답할 수 있는 것과 없는 것」(그래프로 답함 · 현재 값 · 승인 · 공급 정보 · 원문에 없음)에 적습니다.',
                          '다른 작업의 SOP ID가 `입력/조치검토결과.json`의 어느 값에서 왔는지, 질문마다 어느 쪽인지와 그 근거(원천 이름 · 파일)를 말합니다.',
                          f'결과 화면 {N["other_scope"]}단계에 두 번째 카드 · 「찾은 수 0」 조회 · 남은 질문 수가 보이고, 기록 두 표에 근거가 있습니다.',
                          H('같은 방법을 다른 작업과 없는 것에 대고, 답할 수 있는 범위를 나눈다', '`입력/조치검토결과.json`의 `review`, `자료/문서_목록.csv`, 원문 목차, 결과 화면',
                            '원문에 없는 작업 · 절을 만들지 않는다. 현재 값 · 승인을 추정으로 채우지 않는다', f'`{rec}` 두 표', '문서 목록의 파일 칸과 원문 목차를 직접 본다'),
                          cmd=SHOW, why='같은 방법이 다른 작업에도 통하고 없는 것에 「결과 없음」을 돌려줘야 기능입니다. 작업 직전의 센서 값 · 작업지시 상태 · 재고는 시계열 · CMMS · ERP · MES에서 읽어야 하므로, 그래프가 답하는 범위를 밝혀 둡니다.',
                          differ=F.FIX_LOOP)
    steps = [S_[k] for k in order]
    if practical:
        steps = [dict(s_, **PG(N, rec, cols).get(k, {})) for k, s_ in zip(order, steps)]
    return steps, N


def glab(key):
    practical = key == 'practical-03-card'
    course = GCOURSE[key]
    steps, N = graph_steps(key)
    N = {k: n for k, n in N.items() if n != ''}
    event = incident()
    handoff = '`결과/지식_내보내기.json` · `결과/query.cypher` · `결과/구축_기록.md`' + (f' · `결과/작업확인카드_{TASK}.md`' if practical else '')
    if practical:
        goal = ['포털 데이터 연결에서 현재 값을 문서의 기준값과 나란히 놓고 구분했습니다. 이번에는 검토한 문서 지식을 별도 랩 DB의 기존 ID에 잇고 핀 세척의 작업 확인 카드를 만듭니다. '
                f'사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건인 {event}이고, 그 판정 뒤에 남은 근본 조치가 핀 세척(`{TASK}`)입니다.']
        user = '이 답은 보전 야간조가 핀 세척 전에 카드로 준비 · 금지 · 완료를 원문으로 되짚고, 설비보전팀장이 승인할 때 씁니다.'
        questions = ['HYD-02 핀 세척 카드의 항목마다 내용과 원문 절 · 인용은?', '다른 작업의 카드도 만들어지고, 원문이 없는 작업 · 절은 「결과 없음」으로 구별되는가?',
                     '다시 적재해도 수가 같은가? 공급 정보 · 작업 조건을 어디까지 답하고, 현재 값 · 승인 없이 정할 수 없는 것은?']
        lead = '검토한 지식을 랩 DB의 기존 ID에 이어 핀 세척 작업 확인 카드를 만들고, 다른 작업 · 제공되지 않은 절 · 반복 적재를 확인해 저장합니다.'
    else:
        goal = ['포털에서 검토를 마친 후보를 적재하고 지식 지도에서 조치 · 원인 · 근거 문서의 연결을 찾았습니다. 이번에는 검토한 문서 지식을 별도 랩 DB의 설비 모델과 조치 기준에 직접 잇고, 처음 정한 질문에 그 지식이 원문대로 답하는지 확인합니다. '
                f'사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건인 {event}이고, 그 판정 뒤에 남은 근본 조치가 핀 세척(`{TASK}`)입니다.']
        user = '이 답은 설비보전팀장이 핀 세척과 냉각 조치의 조건 · 근거를 그래프로 찾을 때 씁니다.'
        questions = ['HYD-02 냉각 성능 상실에서 쓸 수 있는 조치(즉시 완화 · 근본 조치)마다 수행 단계 · 준비 · 금지 · 완료 기준 · 승인은 무엇이고, 근거 문서 · 판 · 절 · 인용은?',
                     '판정에 쓴 규칙마다 근거 원문이 있는가 — 있으면 어디이고, 조건과 무엇이 다른가?',
                     '핀 세척 전에 확인할 현재 값은 무엇이고 어디서 읽는가(그래프로 답하지 않는 것)?',
                     '다른 문서를 더 반영하면 그 문서의 작업은 어느 설비 · 구성 요소 · 부품에 걸리고, 앞서 넣은 연결은 그대로인가?',
                     '제공되지 않은 작업이나 절을 물으면 그래프는 무엇을 돌려주는가?']
        lead = ('검토를 마친 문서 지식을 별도 랩 DB의 설비 모델과 조치 기준에 기존 ID로 잇는 모양 · 규칙을 정해 적재 · 조회합니다. 처음 정한 질문에 그 지식이 원문대로 답하는지, 보류 후보가 빠지는지, '
                '다시 적재해도 늘지 않는지, 다른 문서를 더해도 앞의 연결이 그대로인지 확인한 뒤 하나의 온톨로지 구축 결과로 저장합니다.')
    make = ('만들 것: 정할 자리(그래프 모양 · 연결 규칙 · 별칭 · 다른 문서의 조건 · 역할 · 질문 값 · 현재 값 원천 · 기대 답 · 고른 것)와, 결과 화면이 그 자리로 만드는 스키마 확장 `결과/schema_ext.json` · 적재 파일 `결과/load.cypher` · 조회문 `결과/query.cypher`'
            + (' · 작업 확인 카드 둘(`결과/작업확인카드_<SOP ID>.md`)' if practical else '') + f' · 남은 질문 `결과/남은_질문.json` · 내보내기 `결과/지식_내보내기.json`, `{GREC}`.')
    save_txt = ((f'다음 실습 「{GNEXT[key]}」에 넘길 판본은 {handoff}입니다. ' + USB) if practical else
                (f'`결과/`의 정할 자리 · 구축 기록 · 스키마 확장 · 적재 · 조회 · 내보내기를 함께 보관합니다. 다음 실습 「{GNEXT[key]}」에 넘길 판본은 {handoff}입니다. ' + USB))
    goal += ['과정은 온톨로지 → 에이전트 → 프로세스 순서로 올라갑니다. 이 실습은 온톨로지 단계의 마지막 — 검토한 문서 지식을 그래프에 잇고 질문으로 확인하는 일 — 을 맡습니다.']
    mine = ('내 앞 결과를 쓸 때: 제공 입력은 그대로 두고 내 검토 결과 · 모델 등을 `결과/내_입력/`에 `입력/`과 같은 이름 · 같은 자리로 복사해, 형식이 `입출력_계약.md` 「입력」과 같은지 먼저 견준 뒤 씁니다. '
            '제공 코드와 `check.py`는 `결과/내_입력/`에 있는 파일을 씁니다. 내 결과가 없어도 제공된 입력으로 끝까지 할 수 있습니다.')
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 무엇을 어떤 종류 · 관계로 담을지, 새 대상의 ID를 어떻게 지을지, 무엇을 어느 기존 ID에 이을지는 정할 자리에 내가 정합니다.\n\n'
               f'- 정할 자리 — `결과/기대_답.csv` · `결과/그래프_모양.json` · `결과/연결_규칙.csv` · `결과/별칭.csv` · `결과/다른문서_조건.csv` · `결과/역할.csv` · `결과/질문_값.csv` · `결과/현재값_원천.csv` · `{F.CHOSEN_FILE}`(계약 「정할 자리」).\n'
               '- 결과 화면이 쓰는 것 — `결과/schema_ext.json` · `결과/load.cypher` · `결과/query.cypher` · `결과/남은_질문.json` · `결과/지식_내보내기.json`' + (' · `결과/작업확인카드_<SOP ID>.md`' if practical else '') + ' · `결과/보기.html`.\n'
               f'- `{GREC}` — 「제공 빈 틀」의 칸대로 채웁니다.\n\n'
               '## 지킬 조건\n\n- `입력/` · `자료/`는 읽기만 합니다. 제공 파일(`show_result.py` · `lab_steps.py` · `doc_graph.py` · `lab_cypher.py` · `lab_db.py` · `check.py`)은 고치지 않습니다.\n- 승인(`approved`) 후보만 적재합니다.\n'
               '- 기존 ID를 바꾸지 않고, 모델에 없는 기존 ID를 지어내지 않습니다.\n- 현재 값(재고 · 작업지시 상태 · 센서 값)은 그래프에 넣지 않고 읽을 원천을 가리킵니다.\n- 전체를 지우는 문장을 쓰지 않습니다.\n']
    cases = (['보류 · 제외 후보가 그래프와 카드에 들어가지 않았는지', '같은 적재를 두 번 했을 때의 수', '절차 밖 절 · 다른 절차 · 다른 문서에 있는 작업 조건',
              '설비 별칭 · 제조사 품번으로 적힌 대상', '다른 작업의 카드', '제공되지 않은 작업 · 절을 묻는 질문', '공급 조건(설비 모델)과 그날의 재고 · 승인의 경계'] if practical else
             ['보류 · 제외 후보가 그래프에 들어가지 않았는지', '같은 적재를 두 번 했을 때의 수', '다른 문서를 더한 뒤 기존 노드 · 관계의 수와 기존 ID의 속성', '같은 번호를 쓰는 다른 문서의 절',
              '설비 별칭 · 제조사 품번으로 적힌 대상', '근거 원문이 있는 규칙 · 범위가 다른 원문 · 원문이 없는 규칙', '판이 다른 같은 문서', '제공되지 않은 작업 · 절을 묻는 질문',
              '그래프로 답하지 않는 현재 값'])
    ix = {k: n - 1 for k, n in N.items()}
    first_tools = ['ai', 'review', 'terminal', 'result']
    extra = ({ix['db']: ['docker']} if practical else
             {ix['look']: first_tools, ix['db']: ['docker'], ix['link']: ['run_approve']})
    return dict(
        title=GTITLES[key], rec=GREC, readonly='`입력/` · `자료/`가', decide_step=ix['other'], course=course,
        goal=goal, make=make,
        start=['`입력/모델/` — 설비 모델(schema.json · graph.json). `입력/조건표.csv` · `입력/sop.json` — 냉각 계통 조치의 조건표와 SOP 구조.'
               + (' `입력/조치검토결과.json` — 그 조건표로 지난 30일 경보를 판정 · 비교한 조치 검토 결과.' if practical else ''),
               '`입력/검토결과/` — 문서마다 후보와 결정(채택 · 수정 · 제외 · 보류) · 근거를 적은 검토 결과' + (' · 이 사건의 작업의 조건(`선택작업_조건.json`)' if practical else '') + '. 문서에서 지식을 추출 · 검토하는 실습의 결과와 같은 꼴로 검증해 제공하는 판입니다.',
               mine,
               '`자료/` — 검토한 문서의 원문과 `자료/문서_목록.csv`(문서마다 판 · 상태 · 시행일 · 파일 · SHA-256).',
               f'`{SHOW}` · `lab_steps.py` — 결과 화면(`결과/보기.html`)을 쓰는 제공 파일. `doc_graph.py` — 정할 자리대로 적재 · 조회 · 카드 · 내보내기를 하는 제공 코드. `lab_db.py` — 이 폴더 전용 랩 DB(그래프 DB)를 켜는 도구. `lab_cypher.py` — 랩 DB에 Cypher를 실행하는 공용 도구.',
               '`입출력_계약.md` — 입력 · 정할 자리 · 결과 파일의 형식. `check.py` — 결과의 구조 검사.',
               f'`결과/` — 정할 자리(「제공 빈 틀」 파일)와 `{Path(GREC).name}`.', BJ.RULES_LINE],
        tools=[f'`python lab_db.py` — 이 폴더 전용 랩 DB를 켭니다(Docker Desktop이 켜져 있어야 함).',
               f'`{SHOW}` — 채운 정할 자리까지 적재 · 조회를 돌려 `결과/보기.html`을 다시 씁니다. 처음 한 번은 브라우저로 엽니다.'],
        user=user, questions=questions, decide=([('다른 문서의 조건', f'다른 문서의 조건 · 시간 · 승인을 핀 세척(`{TASK}`)에 이을지'), ('그래프 모양과 연결', '어떤 종류 · 관계 · ID로 담고 어느 기존 ID에 이을지')] if practical else
                                               [('다른 문서의 조건', f'다른 문서가 정한 조건 · 시간 · 승인을 핀 세척(`{TASK}`)에 이을지 — 어느 문서의 어느 문장인지는 탐색에서 찾습니다'),
                                               ('그래프 모양과 연결', '문서 근거를 어떤 종류 · 관계 · ID로 담고, 승인 후보를 어느 기존 ID에 이을지')]),
        outside=['문서에서 후보를 다시 뽑거나 검토 결정을 바꾸는 일 — 바꿀 것은 남은 질문으로 남깁니다', '포털 DB에 접속하거나 포털 자료를 랩 DB에 넣는 일',
                 '현재 값(재고 · 작업지시 상태 · 센서 값)을 그래프에 넣는 일', '설비 모델의 기존 ID · 기존 종류 · 관계의 뜻을 바꾸는 일'],
        formats=formats, steps=steps, cases=cases,
        commands=f'python lab_db.py\n{SHOW}\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. ' + ('카드 항목마다 먼저 적은 기대와 실제 카드가 원문 줄로 맞고, 다른 작업 카드와 「결과 없음」이 구별되며, ' if practical else
              '질문마다 먼저 적은 기대 답과 실제 조회 결과가 원문 인용으로 맞고, 다른 문서를 더해도 앞의 수 · 연결이 그대로이며, ')
              + f'같은 적재를 다시 해도 수가 같고, `{F.CHOSEN_FILE}`의 근거와 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. 답하지 못한 것은 남은 질문으로 남깁니다.'),
        save=save_txt, reopen=(f'`python lab_db.py` 뒤 결과 화면의 수 · 카드' if practical else f'`python lab_db.py` 뒤 `{SHOW}`의 수 · 조회 결과, `{Path(GREC).name}`의 적재 수 · 기준일 · 저장 시점 · 확인하지 못한 점'),
        tree=F.tree(GLABS[key].name, short_tree(practical, [('.github/', 'Copilot 작업 규칙'), ('결과/', '정할 자리(빈 틀)와 구축 기록'), ('입력/', '모델 · 조건표 · SOP 구조 · 검토 결과(읽기만)'),
                                       ('자료/', '원문과 문서 목록(읽기만)'), ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'),
                                       ('doc_graph.py', '적재 · 조회 · 카드 제공 코드'), ('lab_cypher.py', '랩 DB 실행 도구'), ('lab_db.py', '이 폴더 전용 랩 DB 켜기'),
                                       ('lab_steps.py', '결과 화면의 단계'), ('show_result.py', '결과 화면 쓰기'), ('START.md', '이번 과제와 진행 단계'), ('입출력_계약.md', '입력 · 정할 자리 · 결과의 형식')])),
        lead=lead, need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot, 랩 DB를 켤 Docker Desktop.',
        terms=(TERMS_GRAPH_PRACTICAL + TERMS_CARD) if practical else (TERMS_GRAPH + BJ.CONTRACT_TERM), first_more=[] if practical else [mine],
        tools_from=TITLES['practical-03-extract'] if practical else None,
        guide_extra=extra, guide_after={ix['db']: ['db_stuck'] if practical else ['db', 'db_stuck']})   # 실전 카드 랩은 Neo4j Browser를 쓰지 않는다


def lab(key, files):
    practical = key == 'practical-03-extract'
    course = '실전반' if practical else '통합반'
    title, judged, event = TITLES[key], JUDGED[key], incident()
    steps, N = extract_steps(key)
    if practical:
        user = '이 답은 보전 야간조가 핀 세척 전에 준비 · 금지 · 완료를 원문으로 되짚고, 설비보전팀장이 작업지시를 승인할 때 씁니다.'
        questions = ['핀 세척 후보의 결정(채택 · 수정 · 제외 · 보류)과 근거(문서 · 판 · 절 · 인용)는?',
                     '핀 세척의 준비 · 금지 · 완료 조건과, 이 작업에 걸린 조건마다의 근거 원문은?',
                     '같은 기능을 다른 문서에 적용하면 누락 · 근거 없는 생성은 몇 건이고, 무엇을 고쳐 다시 셌나?']
        goal = [f'포털에서 매뉴얼을 추출 · 대조 · 적재해 본 일을 직접 만듭니다. 포털에서 본 경보와 같은 종류의 다른 경보 한 건인 {event}의 판정 뒤에 남은 근본 조치 쿨러 핀 세척(`{TASK}`)의 준비 · 금지 · 완료 조건을 문서 묶음 전체에서 모읍니다.']
        save = (f'정할 자리 · 검토 결과 · `결과/선택작업_조건.json` · `{REC}` · 응답 기록을 함께 보관합니다. 다음 실습 「{NEXT[key]}」가 이 판으로 카드를 만듭니다(제공 판으로도 시작). ' + USB)
    else:
        user = '이 답은 설비보전팀장이 HYD-02 핀 세척 작업지시를 내기 전에, 이 작업의 조건과 판정에 쓴 조건이 문서 어디에서 왔는지 원문 인용으로 확인할 때 씁니다.'
        questions = ['핀 세척 작업의 원문을 가진 문서들에서 기능이 뽑은 준비 · 방법 · 금지 · 완료 · 승인 후보는 무엇인가? 원문과 대조한 결정(채택 · 수정 · 제외 · 보류)과 근거(문서 · 판 · 절 · 인용)는?',
                     '받은 조건표의 조건마다 근거 원문은 어느 문서 · 절 · 인용에 있고, 그 근거에 따라 조건을 어떻게 두나?',
                     '같은 기능을 검토된 기준선 문서(받은 SOP 구조가 구조로 옮긴 문서)와 다른 문서(정기 점검표 · 예비품 기준 · 보충 매뉴얼)에 적용하면 누락 · 근거 없는 생성은 몇 건이고, 무엇을 고쳐 다시 실행했나?']
        goal = ['포털 지식 관리에서 매뉴얼을 올려 추출을 요청하고, 후보를 원문과 나란히 놓고 고쳐 적재하는 것을 봤습니다. 이번에는 그 일을 직접 합니다 — 문서를 어떤 단위로 나눌지와 수업 모델에 보낼 요청 글을 내가 정하고, '
                f'받은 후보를 원문과 대조해 결정하고, 판정에 쓴 조건이 어느 문서의 어느 문장에서 왔는지 확인합니다. 사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건인 {event}이고, '
                f'그 판정 뒤에 남은 근본 조치 — 쿨러 핀 세척(`{TASK}`) — 의 작업지시를 내기 전입니다.']
        save = (f'`결과/`의 정할 자리 · 검토 결과 · `{REC}`와 응답 기록을 함께 보관합니다. 다음 실습 「{NEXT[key]}」는 이 검토 결과의 승인 후보를 그래프에 잇습니다. '
                '그 실습도 제공된 검토 결과로 시작할 수 있습니다. ' + USB)
    n_docs = sum(1 for r in DD.REGISTER if r[7])
    goal += [f'문서 {n_docs}개는 판 · 상태 · 언어 · 형식이 다르고, 모델의 답은 같은 요청에도 달라 원문 줄과 대조해야 씁니다.' if practical else
             f'문서 묶음은 {n_docs}개입니다 — 같은 매뉴얼의 판이 여럿이고, 판 · 상태 · 언어 · 형식이 문서마다 다릅니다. 모델의 답은 같은 요청에도 매번 다를 수 있어서, 받은 후보를 원문 줄과 대조해야 업무에 쓸 수 있습니다.',
             '과정은 온톨로지 → 에이전트 → 프로세스 순서로 올라갑니다. 이 실습은 첫 단계인 온톨로지의 문서 지식 — 원문에서 근거 있는 후보를 뽑아 사람이 검토하는 일 — 을 맡습니다.']
    make = ('만들 것: 정할 자리(나누는 단위 `결과/나누기.json` · 요청 글 `결과/prompt.md` · 기대 항목 · 검토 결정 · 조건 근거' + (' · 역할' if practical else '') + f' · 고른 것)와, 결과 화면이 그 자리로 만드는 '
            '후보 파일(`결과/후보/`) · 검토 결과(`결과/검토/`)' + (' · `결과/선택작업_조건.json`' if practical else '') + f', `{REC}`.')
    mine = (f'내 앞 결과를 쓸 때: 제공 입력은 그대로 두고 내 `조건표.csv` · `sop.json` · `{judged}`을 `결과/내_입력/`에 복사해, 열 이름 · 키가 `입출력_계약.md` 「입력」과 같은지 먼저 견준 뒤 씁니다. '
            '제공 코드와 구조 검사는 `결과/내_입력/`에 있는 파일을 기준으로 봅니다. 내 결과가 없어도 제공된 입력으로 끝까지 할 수 있습니다.')
    slots = '`결과/나누기.json` · `결과/prompt.md` · `결과/기대_항목.csv` · `결과/검토_결정.csv` · `결과/조건_대조.csv`' + (' · `결과/역할.csv`' if practical else '') + f' · `{F.CHOSEN_FILE}`'
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 문서를 어떤 단위로 나눌지, 무엇을 뽑게 할지, 어떤 후보를 채택할지, 어느 원문을 조건의 근거로 둘지는 정할 자리에 내가 정합니다.\n\n'
               f'- 정할 자리 — {slots}(계약 「정할 자리」).\n'
               '- 결과 화면이 쓰는 것 — `결과/후보/<문서 식별자>_<판>.json` · `결과/검토/<문서 식별자>_<판>_검토.json`' + (' · `결과/선택작업_조건.json`' if practical else '') + ' · `결과/시험_조각.json` · `결과/보기.html`. `결과/응답_기록/`은 `llm_client.py`가 씁니다(고치지 않습니다).\n'
               f'- `{REC}` — 「제공 빈 틀」의 칸대로 채웁니다.\n\n'
               '## 지킬 조건\n\n- `입력/` · `자료/`는 읽기만 합니다. 제공 파일(`show_result.py` · `lab_steps.py` · `doc_extract.py` · `llm_client.py` · `check.py`)은 고치지 않습니다.\n'
               '- 후보는 모델의 답에서 만듭니다 — `입력/`의 SOP 구조 · 조건표를 후보로 옮기지 않습니다.\n'
               '- 후보 파일 원본은 남기고, 검토는 별도 파일에 씁니다. 원문과 대조하지 않은 후보는 보류로 둡니다.\n'
               '- 조건표 · 판정 결과는 바꾸지 않고, 바꿀 것은 요청으로 남깁니다.\n'
               '- 키 · 접속 값을 채팅 · 파일 · 기록에 붙이지 않습니다.\n']
    cases = ['판이 다른 같은 문서에서 같은 작업의 조건이 달라지는 곳', '같은 작업을 사내 문서와 제조사 지침이 함께 말하는 곳', '영문 원본과 번역이 함께 있는 줄',
             '부정 조건(「~하지 않는다」)과 범위 참조(「~부터 ~까지」)', '경계 낱말(초과 · 이상 · 미만 · 이내)이 문서마다 다른 곳', '글자 그대로는 찾히지 않는 인용과 원문 여러 곳에 맞는 인용',
             ('이 작업에 걸린 조건표 조건마다' if practical else '조건표 조건마다') + ' 근거 원문 — 원문이 말하는 대상 · 때가 조건과 같은 곳, 다른 곳, 근거 원문을 찾지 못하는 조건',
             '같은 요청을 한 번 더 보낸 응답', '받은 SOP 구조가 이미 구조로 옮긴 문서에 같은 기능을 적용한 결과', '정기 점검표 · 예비품 기준 · 보충 매뉴얼에 같은 기능을 적용한 결과'] + (['이 작업의 조건이 절차 밖 절 · 다른 문서에 있는 곳'] if practical else [])
    ix = {k: n - 1 for k, n in N.items()}
    return dict(
        title=title, rec=REC, readonly='`입력/` · `자료/`가', decide_step=ix['rev1'], course=course, goal=goal, make=make,
        start=[f'`입력/조건표.csv` · `입력/sop.json` · `입력/{judged}` — 냉각 계통 조치의 조건표 · SOP 구조와, 그 조건표로 지난 30일 경보를 판정한 결과. 조치를 판정하는 실습의 결과와 같은 꼴로 검증해 제공하는 판입니다.',
               mine,
               f'`자료/` — 문서 {n_docs}개와 `자료/문서_목록.csv`(문서마다 판 · 상태 · 시행일 · 소유 부서 · 파일 · SHA-256 — 파일 내용으로 계산한 지문 같은 값이라 한 글자만 달라도 바뀝니다). 문서 목록은 10월 28일 07:30에 내보낸 것입니다.',
               f'`{SHOW}` · `lab_steps.py` — 결과 화면(`결과/보기.html`)을 쓰는 제공 파일. `doc_extract.py` — 정할 자리대로 문서를 읽고 나누어 모델에 보내고, 답을 후보로 바꾸고 인용 줄을 찾고, 검토 결과를 쓰는 제공 코드.',
               '`.env.example` · `llm_client.py` — 수업 모델 연결 값의 틀과 연결 도구. 보낸 요청과 받은 답은 `결과/응답_기록/`에 남습니다.',
               '`입출력_계약.md` — 입력 · 정할 자리 · 결과 파일의 형식. `check.py` — 결과의 구조 검사.',
               f'`결과/` — 정할 자리(「제공 빈 틀」 파일)와 `{Path(REC).name}`.', BJ.RULES_LINE],
        tools=['`python llm_client.py` — 수업 모델에 짧은 질문 하나를 보내 연결을 확인합니다. `--count`는 보내지 않고 응답 기록 수와 이 폴더의 안내용 상한까지 남은 수를 보입니다.',
               f'`{SHOW}` — 채운 정할 자리까지 제공 코드를 돌려 `결과/보기.html`을 다시 씁니다(처음 한 번은 브라우저로 엽니다). 모델을 부르는 단계가 있으므로 이 명령은 내 터미널에서 실행합니다. 같은 요청은 다시 보내지 않고 남은 응답 기록을 씁니다.',
               '키가 없으면 `llm_client.py`는 요청을 보내지 않고, 보낼 글을 `결과/요청/`에 남긴 뒤 무엇을 했는지 알리고 멈춥니다.'],
        user=user, questions=questions,
        decide=([('조건의 근거', '이 작업에 걸린 조건마다 근거 원문과 그에 따른 조건의 자리'), ('사내 문서와 제조사 지침', '제조사 지침이 말하는 것을 작업 조건에 어떻게 둘지'),
                 ('나누는 단위와 요청 글', '어떤 단위로 나누고 무엇을 뽑게 할지')] if practical else
                [('조건의 근거', '받은 조건표의 조건마다 무엇을 근거 원문으로 두고, 그 근거에 따라 조건을 어떻게 둘지'),
                ('사내 문서와 제조사 지침', '핀 세척 작업에 대해 제조사 지침이 말하는 것을 작업 조건에 어떻게 둘지'),
                ('나누는 단위와 요청 글', '문서를 어떤 단위로 나누어 보내고, 무엇을 뽑게 할지')]),
        outside=['그래프 DB에 적재하는 일(다음 실습)', '조건표 · SOP 구조 · 판정 결과를 고치는 일 — 바꿀 것은 요청으로 남깁니다', '포털에 문서를 올리거나 포털의 추출 기능을 부르는 일',
                 '문서를 고쳐 쓰거나 번역하는 일'],
        formats=formats, steps=steps, cases=cases,
        commands=f'python llm_client.py\npython llm_client.py --count\n{SHOW}\npython check.py\npython check.py 결과/후보/<파일 이름>.json',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 실행 전에 원문에서 적은 기대 항목과 실제 후보를 줄마다 견준 기록이 있고, '
              + ('핀 세척의 준비 · 금지 · 완료 후보의 결정과 이 작업에 걸린 조건마다의 근거 대조가 ' if practical else '핀 세척 작업 후보의 결정과 조건표 조건마다의 근거 대조가 ')
              + f'원문 줄로 설명되며, 다른 문서의 누락 · 근거 없는 생성 수와 고친 뒤 다시 센 수가 있고, `{F.CHOSEN_FILE}`의 근거와 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. '
              '키가 없어 모델을 부르지 못한 단계는 그렇다고 적습니다.'),
        save=save, reopen=('결과 화면의 단계 띠와 마지막 단계의 check.py 출력' if practical else f'`{SHOW}`의 단계 띠와 `python check.py`의 출력, `{Path(REC).name}`의 기준일 · 저장 시점 · 확인하지 못한 점'),
        tree=F.tree(LABS[key].name, short_tree(practical, [('.github/', 'Copilot 작업 규칙'), ('결과/', '정할 자리(빈 틀)와 검토 기록'), ('입력/', '조건표 · SOP 구조 · 판정 결과(읽기만)'),
                                      ('자료/', '문서 묶음과 문서 목록(읽기만)'), ('.env.example', '수업 모델 연결 값의 틀'), ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'),
                                      ('CLAUDE.md', '작업 규칙(같은 내용)'), ('doc_extract.py', '추출 · 검토 제공 코드'), ('lab_steps.py', '결과 화면의 단계'), ('llm_client.py', '수업 모델 연결'),
                                      ('show_result.py', '결과 화면 쓰기'), ('START.md', '이번 과제와 진행 단계'), ('입출력_계약.md', '입력 · 정할 자리 · 결과의 형식')])),
        lead=('나누는 단위와 요청 글을 정해 문서에서 근거 있는 후보를 받고, 원문과 대조해 결정한 뒤 핀 세척의 준비 · 금지 · 완료 조건을 모아 다음 실습에 넘깁니다.'
              if practical else '문서를 나눌 단위와 수업 모델에 보낼 요청 글을 내가 정해 문서에서 작업 순서 · 조건 · 단위 · 금지 후보를 문서 · 판 · 절 · 인용과 함께 받아 냅니다. '
              '후보마다 채택 · 수정 · 제외 · 보류와 근거를 정하고, 조건표의 조건마다 근거 원문을 대조한 뒤 같은 방법을 다른 문서에 적용해 빠뜨리거나 지어낸 것을 셉니다.'),
        need=f'VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot, 강의에서 받은 수업 모델 접속 세 줄(없으면 학생용 완성본 묶음).',
        terms=TERMS_EXTRACT_PRACTICAL if practical else TERMS_EXTRACT, first_more=[MINE_SHORT] if practical else [mine],
        guide_extra={ix['start']: ['ai', 'review', 'terminal', 'result'], ix['connect']: [] if practical else [para(ENV_HOWTO[course])], ix['prompt']: [] if practical else ['run_approve']},
        guide_after={ix['connect']: [STUCK_ENV_P] if practical else [WAIT_FIRST, STUCK_ENV], ix['main']: [WAIT_MANY_P if practical else WAIT_MANY]})


def short_tree(practical, rows):
    """실전(한 칸에 두 랩): 탐색기 모양의 설명은 학생이 손댈 자리 · 읽을 자리만 — 제공 파일 이름은 그대로 보인다."""
    keep = {'결과/', '입력/', '자료/', 'START.md', '입출력_계약.md'}
    return [(k, v if k in keep or not practical else '') for k, v in rows]


def para(text):
    return f'<p>{F.inline(text)}</p>'


TERMS_EXTRACT = ('**수업 모델**은 강의에서 쓰는 언어 모델이고, 이 폴더의 `llm_client.py`가 `.env`의 접속 세 줄(접속 주소 · 키 · 모델 이름)로 모델 서버에 요청을 보내 부릅니다. '
                 '**요청 글**(프롬프트)은 모델에게 보내는 작업 지시입니다. **후보**는 모델의 답에서 뽑아 계약 꼴로 적은 조건 · 단계 하나이고, 사람이 원문과 대조해 결정하기 전에는 지식으로 쓰지 않습니다. '
                 '**인용**은 후보의 근거가 되는 원문 부분을 글자 그대로 옮긴 것, **응답 기록**은 보낸 요청과 받은 답을 `결과/응답_기록/`에 남긴 파일입니다. '
                 '**정할 자리**는 결과/의 「제공 빈 틀」 파일 — 방향이 갈리는 판단을 내가 AI와 채우는 곳이고, 나머지 일은 제공 코드가 합니다. '
                 '**조건표**는 조치마다 어떤 입력이 어떤 값일 때 경고 · 감점 · 제외하는지 적은 판단 조건의 표, **SOP 구조**는 조치의 작업 절차를 구조로 옮긴 것, '
                 '**판정 결과**는 그 조건표로 지난 경보마다 조치 후보를 판정한 결과입니다. ' + BJ.CONTRACT_TERM)
TERMS_EXTRACT_PRACTICAL = ('**후보**는 수업 모델의 답에서 뽑아 계약 꼴로 적은 조건 · 단계 하나(사람이 원문과 대조해 결정하기 전에는 지식이 아님), **인용**은 그 근거인 원문 부분 그대로입니다. '
                           '**정할 자리**는 결과/의 「제공 빈 틀」 파일 — 방향이 갈리는 판단만 내가 채우고 나머지는 제공 코드가 합니다. **계약**은 그 파일들의 모양을 정한 `입출력_계약.md`입니다.')
MINE_SHORT = '내 앞 결과를 쓸 때는 `결과/내_입력/`에 `입력/`과 같은 이름으로 복사해 계약 「입력」과 견준 뒤 씁니다 — 없어도 제공 입력으로 끝까지 합니다.'
TERMS_GRAPH = ('**적재**는 대상 · 관계를 그래프 DB에 넣는 일이고, **스키마 확장**은 문서 근거를 담으려고 설비 모델에 더하는 새 종류 · 관계와 그 뜻입니다. '
               '**정할 자리**는 결과/의 「제공 빈 틀」 파일 — 그래프의 모양과 무엇을 어디에 이을지를 내가 AI와 채우는 곳이고, 적재 · 조회 · 내보내기는 제공 코드가 합니다. '
               '**기존 ID**는 설비 모델 · SOP 구조 · 조건표가 이미 가진 대상의 ID이고, **승인 후보**는 검토 결과에서 채택 · 수정으로 `approved`가 된 후보입니다. ')
TERMS_GRAPH_PRACTICAL = ('**적재**는 대상 · 관계를 그래프 DB에 넣는 일이고, **기존 ID**는 설비 모델 · SOP 구조 · 조건표가 이미 가진 대상의 ID, **승인 후보**는 검토 결과에서 approved가 된 후보입니다. '
                         '정할 자리 · 계약은 문서에서 작업 조건과 근거를 추출하는 실습과 같은 뜻입니다. ')
TERMS_CARD = '**작업 확인 카드**는 작업자가 작업 전에 준비 · 금지 · 순서 · 완료와 그 원문 출처를 되짚는 표이고, 승인과 현재 상태 확인을 대신하지 않습니다. '
ENV_HOWTO = {
    '통합반': ('**`.env` 만들기** 왼쪽 탐색기에서 `.env.example`을 오른쪽 클릭해 **복사**(Copy)를 누르고, 탐색기의 빈 곳을 오른쪽 클릭해 **붙여넣기**(Paste)를 누릅니다. '
              '새로 생긴 사본을 오른쪽 클릭해 **이름 바꾸기**(Rename)로 이름을 `.env`로 바꿉니다. `.env`를 열어 등호(=) 뒤가 비어 있는 세 줄을 지우고, 그 자리에 강의에서 받은 세 줄을 그대로 붙여 넣은 뒤 '
              '**Ctrl+S**로 저장합니다. 세 줄은 주소 · 키 · 모델 이름이고, 내가 손으로 정하거나 고칠 값은 없습니다.'),
    '실전반': '**`.env` 만들기** 탐색기에서 `.env.example`을 **복사**(Copy) · **붙여넣기**(Paste)한 사본의 이름을 **이름 바꾸기**(Rename)로 `.env`로 바꾸고, 빈 세 줄 자리에 받은 세 줄을 그대로 붙여 넣어 **Ctrl+S**로 저장합니다.'}
WAIT_FIRST = para(f'**기다릴 때** 터미널에 「수업 모델에 요청을 보냅니다(요청 해시 …, 이 폴더 기록 1번째 · 안내용 상한 {LLM.MAX_SENT}개) — 첫 요청은 1분쯤 걸릴 수 있습니다.」 줄이 나온 뒤 답이 바로 오지 않아도 기다립니다. '
                  f'한 요청은 {LLM.TIMEOUT_S}초까지 기다리고, 그 안에 답이 없으면 「모델 서버에 닿지 못했습니다(timed out).」로 시작하는 줄을 내고 멈춥니다 — 그때는 1분쯤 뒤 같은 명령을 다시 실행합니다.')
STUCK_ENV = para('**막히면** 출력의 첫 줄로 고칠 곳을 찾습니다. 「키가 없어 연결을 확인하지 않았습니다(.env가 없거나 LLM_API_KEY가 비어 있음).」이면 파일 이름이 `.env`가 아니거나 붙여 넣은 뒤 저장하지 않은 것이니, '
                 '탐색기에서 이름을 보고 탭 이름 옆 점(●)이 없는지 확인합니다. 「.env의 … 값이 비어 있습니다.」처럼 이름이 찍히면 받은 세 줄 가운데 그 줄이 빠진 것이니 세 줄을 다시 붙여 넣습니다.')
WAIT_FIRST_P = para(f'**기다릴 때** 첫 요청은 1분쯤 걸릴 수 있습니다. {LLM.TIMEOUT_S}초 안에 답이 없으면 「모델 서버에 닿지 못했습니다(timed out).」로 멈추니 1분쯤 뒤 다시 실행합니다.')
STUCK_ENV_P = para('**막히면** 「키가 없어 연결을 확인하지 않았습니다」는 파일 이름이 `.env`가 아니거나 저장하지 않은 것(탭 이름 옆 ●), 「.env의 … 값이 비어 있습니다」는 그 줄이 빠진 것이니 세 줄을 다시 붙여 넣습니다.')
WAIT_MANY_P = para(f'**기다릴 때** 조각 수만큼 요청을 보내므로 그만큼 기다립니다. 받은 조각은 다시 보내지 않고, 보낸 기록이 {LLM.MAX_SENT}개가 되면 더 보내지 않습니다(이 폴더의 안내용 상한).')
WAIT_MANY = para(f'**기다릴 때** 이 단계는 조각마다 요청을 하나씩 보내므로 조각 수만큼 기다립니다. 같은 요청은 다시 보내지 않으므로, 중간에 멈춰 다시 실행해도 이미 받은 조각은 다시 보내지 않습니다. '
                 f'`결과/응답_기록/`에 모델 서버로 보낸 기록이 {LLM.MAX_SENT}개가 되면 더 보내지 않습니다 — 비용을 지키는 이 폴더의 안내용 상한입니다. 결과 화면 4단계의 「보낼 요청」 수를 먼저 봅니다.')


# ───────────── 설계 조건 검사 ─────────────
# 학생 문장 · 제공 코드 · 가이드의 정답 토글 밖 본문에 두지 않는 말 — 결정 지점 · 함정의 답과 그 실마리. 글자 방식은 제공 코드가 풀어 결과 화면에 보이므로 함정이 아니다.
LEAKS = ['SR-04', '설비안전규정', 'HM-9.4', '9-7', '9-6', '9-8', '쪽이 빠', '빠진 쪽', '인식 오류', '문자 인식', 'OCR', '번역 메모', 'REM0TE', '판독',
         '저압수', '고압수', '코어 교체', '유온 차', '입구와 출구', 'T-7.1', '작업 근거가 아니', '승인 전', '미승인', '0171', '051f', '10월 26일', '다가가', '실측',
         '규칙 기반', '비교용', '(권장)', '외부 모델 호출', 'SOP-PM-21', 'SOP-PM-22', 'T-3.1', 'T-4.1', 'R4', 'R5', 'ts1-hard', 'trip-reset', '인터록 한계', 'PM-2.4']
NAME_LEAKS = ['근거', '빠진', '깨진', '오류', '미확인', 'cp949', '0171', '교체', '저압', '스캔오류', '인터록']   # 파일 · 폴더 이름(열 이름은 정할 자리의 「근거」 칸을 받는다)
STUDENT_TEXT = ['START.md', 'AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md', '입출력_계약.md', '입력/README.md', '결과/README.md', REC, 'check.py', 'llm_client.py',
                '.env.example', 'doc_extract.py', 'lab_steps.py']
GUIDE_WORDS = ['SDD', 'Spec Kit', '명세', '강사 참조', 'reference', '재생', '캐시', '저장된 응답', '시작본', '이미 있는 추출 결과', '앞 실습에서', '앞 이론', '방금 실습에서',
               '랩 그래프', '교육용', '강의용', '수업용', '(가정)', '(예시)', '실제와 다르', '제작 참고', '낭독']
OPS_WORDS = ['중계', '깨어나', '60번', '고른 작업', '작업 고르기']


def guide_text(html_text, answers=False):
    """가이드 글(태그 · 스타일 · 스크립트를 뺀 것). answers=False면 「정답 보기」 토글 안은 뺀다(P-3 — 토글 밖 본문만 본다)."""
    t = re.sub(r'<(style|script)>.*?</\1>', '', html_text, flags=re.S)
    if not answers:
        t = re.sub(r'<details class="answer">.*?</details>', '', t, flags=re.S)
    return _html.unescape(re.sub(r'<[^>]+>', '\n', t))


def guide_checks(folder, L, leaks):
    """폴더 밖 가이드: 절 = START 「진행 단계」(번호 · 이름 · 개수), 구현 · 판단 단계마다 정답 토글, 토글 밖 본문에 두지 않는 말 0, 폴더 · ZIP 안 가이드 0."""
    bad = []
    path = F.guide_path(folder)
    if any((folder/n).exists() for n in F.LEGACY_GUIDES):
        bad.append('랩 폴더 안에 guide.html · 안내.html이 남음')
    guide = path.read_text(encoding='utf-8')
    heads = re.findall(r'<section id="s(\d+)"><h2>(\d\d) ([^<]+)</h2>', guide)
    start = re.findall(r'^(\d+)\. \*\*([^*]+)\*\*', (folder/'START.md').read_text(encoding='utf-8-sig'), re.M)
    if [(int(a), _html.unescape(c)) for a, _, c in heads] != [(int(a), b) for a, b in start] or len(heads) != len(L['steps']):
        bad.append(f'가이드 절({len(heads)}) ≠ START 진행 단계({len(start)}) — 번호 · 이름이 같아야 함')
    for i, s in enumerate(L['steps'], 1):
        section = re.search(rf'<section id="s{i}">.*?</section>', guide, re.S).group()
        if F.needs_answer(s) and '<details class="answer">' not in section:
            bad.append(f'{i}단계 「{s["name"]}」에 정답 보기 토글 없음')
    text = guide_text(guide)
    for word in [w for w in leaks if w != '(권장)'] + GUIDE_WORDS + OPS_WORDS:
        for n, line in enumerate(text.splitlines(), 1):
            if word in line:
                bad.append(f'가이드 토글 밖 글 {n}줄: 「{word}」')
    return bad


def text_leaks(folder, rels, leaks):
    bad = []
    for rel in rels:
        text = (folder/rel).read_text(encoding='utf-8-sig')
        for word in leaks + OPS_WORDS:
            for n, line in enumerate(text.splitlines(), 1):
                if word in line:
                    bad.append(f'{rel}:{n}: 「{word}」')
    return bad


def blank_checks(folder):
    """처음 폴더의 결과/: README와 「제공 빈 틀」 표시가 첫 3줄 안에 있는 파일뿐, 정할 자리는 비어 있다(K-7)."""
    bad = []
    for p in sorted((folder/'결과').rglob('*')):
        if p.is_file() and p.name != 'README.md':
            head = '\n'.join(p.read_text(encoding='utf-8-sig').splitlines()[:3])
            if F.MARK not in head:
                bad.append(f'결과/{p.relative_to(folder/"결과").as_posix()}: 첫 3줄에 「{F.MARK}」 없음')
    return bad


GLEAKS = ['HM-9.4', '9-7', 'HPP-45B', 'OEM-HPP45B', 'PM-2.4', '예정된 정비', '생산 오더', 'T-3.1', 'T-4.1', 'T-7.1', '코어 교체', '유온 차', '0171', '051f', 'HI-CC-45A', 'HI-RF-10',
          '1~3호기', '주로 야간', '야간 예정', 'MES 계획', '규칙 기반', '두 번째 구현', 'reference', '강사 참조', '갈래']
GSTUDENT_TEXT = ['START.md', 'AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md', '입출력_계약.md', '입력/README.md', '결과/README.md', GREC, 'check.py', 'lab_steps.py', 'doc_graph.py']


# ───────────── 쓰기 ─────────────
def fresh(folder):
    """폴더를 통째로 다시 쓴다(옛 판 찌꺼기가 남지 않게)."""
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)


def finish(folder, L, steps_source, check_source, provided):
    """제공 결과 화면 두 파일 · 검사기(제공 파일 해시 대조를 넣어) · START · 폴더 밖 가이드."""
    F.write_provided(folder, steps_source)
    at = check_source.rindex("\nif __name__ == '__main__':")
    write(folder/'check.py', check_source[:at] + '\n' + F.CHOSEN_CHECK + '\n' + F.provided_guard(folder, [p for p in provided if p != 'check.py']) + check_source[at:])
    write(folder/'START.md', F.step_start(L).replace('`결과/schema.json`처럼', '`결과/prompt.md`처럼' if 'doc_extract.py' in provided else '`결과/연결_규칙.csv`처럼'))
    F.write_guide(folder, F.step_guide(L))


def build(key):
    folder = LABS[key]
    files = DD.bundle()
    L = lab(key, files)
    fresh(folder)
    F.write_rules(folder)
    (folder/'자료').mkdir()
    for name, data in files.items():
        (folder/'자료'/name).write_bytes(data)
    BJ.judge_inputs(folder)
    judged = (BASE_JUDGED/JUDGED[key]).read_bytes()
    (folder/'입력'/JUDGED[key]).write_bytes(judged)
    n_events = len(json.loads(judged)['events'])
    for name, text in {'입출력_계약.md': contract(key), REC: record_template(key), '결과/README.md': result_readme(key),
                       '입력/README.md': input_readme(key, n_events), '.env.example': ENV_EXAMPLE, **extract_blanks(key)}.items():
        write(folder/name, text)
    (folder/'llm_client.py').write_bytes((TOOLS/'lab_llm.py').read_bytes())
    (folder/'doc_extract.py').write_bytes((TOOLS/'doc_extract.py').read_bytes())
    finish(folder, L, extract_steps_source(key, L), checker(key), PROVIDED_EXTRACT)
    return folder, L


def gbuild(key):
    folder = GLABS[key]
    course = GCOURSE[key]
    practical = key == 'practical-03-card'
    L = glab(key)
    fresh(folder)
    F.write_rules(folder)
    (folder/'자료').mkdir()
    for f in sorted((LABS[GEXTRACT[key]]/'자료').iterdir()):
        (folder/'자료'/f.name).write_bytes(f.read_bytes())
    (folder/'입력/모델').mkdir(parents=True)
    for name in ['schema.json', 'graph.json']:
        (folder/'입력/모델'/name).write_bytes((LAB2_INPUT[course]/name).read_bytes())
    BJ.judge_inputs(folder)
    n_events = 0
    if practical:
        judged = (BASE_JUDGED/'조치검토결과.json').read_bytes()
        (folder/'입력/조치검토결과.json').write_bytes(judged)
        n_events = len(json.loads(judged)['events'])
    reviews = instructor_reviews(key)
    for name, data in reviews.items():
        (folder/'입력/검토결과'/name).parent.mkdir(parents=True, exist_ok=True)
        (folder/'입력/검토결과'/name).write_bytes(data)
    for name in ['lab_db.py', 'lab_cypher.py', 'doc_graph.py']:
        (folder/name).write_bytes((TOOLS/name).read_bytes())
    for name, text in {'입출력_계약.md': graph_contract(key), GREC: graph_record(key), '결과/README.md': graph_result_readme(key),
                       '입력/README.md': graph_input_readme(key, reviews, n_events), **graph_blanks(key)}.items():
        write(folder/name, text)
    finish(folder, L, graph_steps_source(key, L), graph_checker(key), PROVIDED_GRAPH)
    return folder, L


def main(argv=None):
    raise SystemExit('build_document_labs.py는 정본 자리에 옛 구조 랩을 쓰지 않습니다. 대조 기준이던 옛 구조 3회차 판정 랩 · 2회차 실습4 · '
                     '3회차 학생용 완성본이 새 구조(judgement-lab · action-review-lab · graph-lab)로 바뀌었습니다. '
                     '문서 지식 네 랩은 build_session4_projects.py <lab …> --dest|--apply [--completed]로 만듭니다.')


if __name__ == '__main__':
    sys.exit(main())
