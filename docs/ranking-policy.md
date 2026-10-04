# 실행 가능한 조치 순위 정책

조치 후보와 실행 가능 여부는 기존 후보·준수 규칙으로 판단한다. 가능한 후보의 순위는 Neo4j `Rule.rankingPolicy`에 저장한 명시적인 식으로 계산한다. `annotation`과 `when`은 설명이며 계산식으로 해석하지 않는다. 정책이 없거나 입력/계산이 잘못되면 판단을 실패로 반환한다. Python의 이전 점수식으로 대체하지 않는다.

## 현재 정책 조회·변경

`GET /api/kg/ranking-policy/rule%3Arank-value`는 현재 `policy`, 설명, `revision`, `policy_sha256`을 반환한다. 처음 적재할 정책은 [ranking-default.json](../common/hydcommon/ranking-default.json)이다. 기존 일곱 점수 성분을 명시한 초기 정책이며 런타임 기본값으로 몰래 적용하지 않는다. 신규 seed는 정책이 없는 기본 규칙에만 이 값을 적재한다. 실행 중인 그래프에 seed 전체를 다시 적용하지 않는다.

읽은 결과를 검토한 뒤 같은 경로에 PUT한다. 아래 필드는 모두 필요하다.

```json
{
  "expected_revision": "GET 응답의 revision",
  "request_id": "새 UUID",
  "by": "지식 작성자",
  "reason": "변경 이유와 근거",
  "annotation": "사람이 읽을 새 판단 기준",
  "policy": {
    "version": 1,
    "inputs": {"due": "order_due_h"},
    "components": {
      "delivery": "(24 - due) if production == 'keep' else 0",
      "forecast": "-forecast_ts1"
    },
    "tieBreak": "lower_approver"
  }
}
```

예시 식은 작성 형식을 보여 주며 운영에 권장하는 가중치가 아니다. 실제 업무 단위·목표·입력 없음의 의미와 조치 간 비교를 검토해야 한다. 기존 정책에 없는 이름이나 식을 추가할 때에는 현재 사실·예측으로 계산 결과를 확인한다.

조회 뒤 정책이나 설명이 바뀌었으면 409로 거절한다. 같은 요청 ID와 내용의 재시도는 당시 영수증을 돌려주며 현재 정책을 과거로 되돌리지 않는다. 같은 ID에 다른 변경을 넣을 수 없다. 원문 적재가 소유한 규칙은 이 API로 수정하지 않는다. 현재 로컬 지식 관리 API의 권한 범위를 따르며 운영용 다중 사용자 인증·분리 승인을 새로 제공하는 API는 아니다.

변경 전 내용과 결과는 기존 `KnowledgeEdit`에 원자적으로 기록된다. 되돌릴 때도 현재 정책을 먼저 읽고, 이전 `policy`와 설명을 새로운 요청 ID 및 현재 revision으로 PUT한다. 다른 작성자의 중간 변경을 덮어쓰는 강제 복원은 없다.

## 계산 계약

- `inputs`는 식 안의 별칭을 그래프에 선언된 정확한 InputData 변수에 연결한다. 예를 들어 새 DDL 컬럼의 `db_…` 변수도 연결할 수 있다. 같은 변수의 선언이 여러 개이거나 없으면 변경을 거절한다. 실제 조회는 [물리 입력 계약](enterprise-catalog.md)을 따른다.
- 후보별 기본 특징은 `forecast_ts1`, `warning_count`, `penalty_total`, `precedent_share`, `production`과 `bsc_gain`, `bsc_loss`, `bsc_conditional_gain`, `bsc_conditional_loss`다. `production`은 현재 PLC 조치에서 읽은 keep/reduce/stop 분류다. 분류의 기존 설계 부하 기준을 임의 사업의 생산 모델로 확대하지 않는다.
- 식은 수치 사칙연산, 비교, 불리언 and/or/not, `A if 조건 else B`, `min`, `max`, `abs`, `round`, `clamp`를 지원한다. 속성 접근·객체 생성·인덱스·반복문·거듭제곱·모듈 호출·파일·네트워크·Python eval은 지원하지 않는다. 길이/깊이/노드 수/함수 인수 개수도 제한한다.
- 미확인 입력은 None이다. `x is None` 같은 명시적 분기만 이를 처리할 수 있다. None 산술, 불리언의 수치 강제 변환, 무한값, NaN, 0 나눗셈은 실패다. 정책 작성자가 명시적으로 미확인을 0으로 취급한 분기는 그 정책의 업무 가정이며 실제 값 확인을 뜻하지 않는다.
- 각 성분을 소수 둘째 자리로 반올림한 뒤 합산한다. 유한 부동소수 계산이며 임의 정밀도 회계 계산은 아니다. 제외된 카드는 뒤로 정렬하고, 같은 점수에서는 낮은 승인 직급을 우선한다.
- 후보별로 맞는 RANK 규칙이 정확히 하나여야 한다. TESTS가 없는 RANK는 무조건 적용하고, 조건이 미확인이거나 여러 RANK가 동시에 맞으면 자동으로 첫 규칙을 고르지 않는다.

카드의 `rankingEvidence`에는 실제 정책, 해시, 적용 규칙과 BSC 득실이 남는다. 포털의 점수 성분은 정책의 실제 키를 사용하며 출처 상세에서 계산식과 입력 연결을 보여 준다. 승인 시 정책과 BSC 근거를 다시 읽는다. 규칙이나 BSC 근거, 명시 순위 입력의 값 또는 물리 원천의 의미가 바뀌면 새 검토가 필요하다. 과거 카드에 실행 정책 근거가 없으면 현재 검토본을 다시 만들어야 한다.

## 검증된 범위와 남은 일

A069 전체 검사는 961 passed/6warnings다. 실제 `scripts/probe_ranking_policy.py --out <새 폴더>`의 16항목은 `.evidence/reaudit/a069-live-final/`에 있다. HTTP 저장→Neo4j→MCP 실행 식 전달, 식 변경에 따른 권고 역전, 오래된 승인 보류, 수정 충돌/재요청, 잘못된 식/원천 변수 거절, 0 나눗셈 실패, 새 실제 PG 컬럼의 값 변경→순위 역전/승인 보류, NULL 판단 실패와 정책 복원을 확인했다. 시험 표와 InputData는 정리하고 수정 영수증은 보존한다.

기존 BSC `condition`은 자연어 설명이다. A070은 개별 경로·관계·원문을 보존하고, 검토된 명시 조건식으로 TRUE/FALSE/UNKNOWN을 평가한다. 확인된 최대 영향과 그보다 큰 미확인 영향의 증가분을 나누어 중복 계산을 막는다. [BSC 조건 운영 계약](bsc-conditions.md)을 따른다. 원문만 있는 조건은 UNKNOWN이며 초기 정책의 0.5는 명시적인 추정 계수다. 회의에서 정한 수치나 조건이 참이라는 증거가 아니다. 전체 원문의 업무 의미·정량 인과 모델·실제 AI 해석은 남는다.

참고 근거는 회의2 385~413행의 업무 데이터와 대안 판단, D02 `f4d050df`의 전략맵 품질 검토, P03 `1db85d3b`의 `app/contribution.py`217~273 및 `app/ai.py`1~64, P04 `e58f4d13`의 `feedback_batch_manager.py`565~658이다. P03은 KPI 성과자의 중요도 가중 기여도를 계산하며 HYD의 PLC 조치 순위식과 동일한 기능이 아니다. P04는 검토 대상의 정확한 ID를 유지하고 DMN 초안/병합 요청을 저장한다. 이 코드를 참고해 정확한 대상·수정 충돌·변경 근거를 유지했으며, HYD가 전체 DMN/FEEL·제품 PR 워크플로를 이식했다고 주장하지 않는다. 식 언어는 HYD의 명시적 실행 계약이다.

최종 배포본의 기존 쿨러 회귀는 `.evidence/reaudit/a069-cooler-final/`의42/42다. 동일20배속/허용치의 legacy bridge에서 사람 검토·PLC ACK·재관측·실제CMMS·종결과 Execution 투영을 확인했다.

새 Codex에 의한 정책 작성/질의·직접 UI 검수는 이번 검사에 포함하지 않는다. 기존 정책 차단을 우회하지 않는다.
