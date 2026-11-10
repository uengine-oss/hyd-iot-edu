# 입출력 계약

입력 · 빈 틀 · 결과 파일의 형식과 뜻만 정한다. 판정 원칙은 원문(`data/hm8_manual.md` · `data/work_standard.md` · `data/hi01_supplement.md`), 원천의 기록 방식은 `data/collection_notes.md`에 있다.

## 입력

- `data/criteria/condition_table.csv` — 조건표(아래 「조건표」). 제공 코드는 규칙을 이 파일에서 읽는다. 열 이름이 계약과 다르면 파일 · 행을 밝혀 멈춘다.
- `data/criteria/sop.json` — SOP 구조(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인과 원문 출처). 키의 뜻은 아래 「제공 입력」에 있다.
- `data/`의 원천 네 개(`alarms.csv` · `plc_status.csv` · `fan_counter.csv` · `forecasts.csv`), `data/orders.csv`, `data/metrics/`(`metric_definitions.md` · `business_values.json` · `candidate_settings.csv`).
- 내 앞 결과를 쓸 때는 `app/features/criteria/`에 같은 이름으로 둔다. 제공 코드와 구조 검사는 그 폴더에 있는 파일을 기준으로 본다.

## 판단 입력

- 경보 하나(`alarms.csv`의 RAISE 행)가 사례 하나이고, 사례마다 `data/targets.csv`의 후보를 판정한다.
- 후보마다 아래 「조건표」의 입력 이름 일곱 개를 모두 만든다(조건표가 지금 쓰지 않는 입력도). 단위는 그 표의 단위다.
- `skill_kind` · `skill_code`는 `targets.csv`의 `kind` · `codes`(`;`로 나눈 목록)다.
- 값을 정할 수 없는 입력은 `null`이고, 왜 없는지(원천 · 시각)를 함께 적는다.

## 조건표 (`data/criteria/condition_table.csv`)

열: `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section`

- 비교 하나가 한 행이다. 같은 `rule_id` · `action`의 행은 한 규칙 묶음이고 `condition_index`를 1부터 차례로 적으며 `logic`은 `AND`다. OR는 다른 `rule_id`로 나눈다.
- `action`: `data/targets.csv`의 SOP ID 하나. 같은 규칙을 여러 조치에 걸면 조치마다 묶음 전체를 적는다. 표에 없는 조치 · 규칙 조합은 그 조치에 그 규칙을 걸지 않는다는 뜻이다.
- `result`: `WARN`(경고) · `PENALTY`(감점) · `EXCLUDE`(제외). 같은 묶음의 `result` · `penalty_manwon` · `reason` · `source_section`은 모든 행에서 같다. `PENALTY`만 `penalty_manwon`(만원)을 적고 나머지는 빈칸이다.
- `operator`: `>=` · `>` · `<=` · `<` · `==` · `!=` · `has_other_than`(목록 입력에 기준값이 아닌 항목이 하나라도 있음). `boundary_included`: 기준값 자체가 조건에 들어가면 `예`, 들어가지 않으면 `아니오`, 글자 · 목록 비교는 `해당없음`.
- `input`과 단위: `forecast_ts1`(조치 후 예측 유온, ℃) · `forecast_ps1`(조치 후 예측 토출 압력, bar) · `fan100_hours`(팬 100 % 연속 운전 시간, h) · `plc_mode`(`REMOTE_AUTO` · `REMOTE_MANUAL` · `LOCAL`) · `plc_state`(`RUN` · `TRIP` · `STOP`) · `skill_kind`(조치 종류 `control` · `work_order`) · `skill_code`(실행 코드 목록). `skill_kind` · `skill_code` 값이 오는 곳: `targets.csv`의 `kind` · `codes`. 숫자 입력은 `unit`을 적는다.
- 목록 입력(`skill_code`)에는 `has_other_than`만 쓴다.
- `source_section`: 이 행의 근거를 다른 사람이 다시 찾을 수 있게 적는다 — HM-8 매뉴얼 원문의 근거는 절 · SOP 단계 · 승인 줄을 ;로 잇고 문서 이름 · 판은 붙이지 않는다(꼴: HM-8.<절>; HM-8.<절> SOP-<ID> 단계 <n>; HM-8.<절> SOP-<ID> 승인), 자료 파일의 줄은 파일:줄, 결정표에서 가져온 행은 「판단 시스템 결정표 rule:<id>; 출처 <그 규칙의 출처>」 뒤에 HM-8 매뉴얼 원문에서 그 출처를 찾았는지를 적고, 결정표 규칙을 고쳐 HM-8 매뉴얼 원문 근거로 옮긴 행은 원문 출처 뒤에 「판단 시스템 결정표 rule:<id>」를 덧붙인다(결과 화면은 rule:<id>가 있어야 그 규칙을 출처로 든 것으로 읽는다).

## 빈 틀 (`app/features/gap_rule.py` · `app/features/compare_rule.py` — 「제공 빈 틀」 빈 함수)

제공 코드 `judge_tools.py`가 부르는 함수 둘이다. 입력과 돌려줄 값의 꼴은 각 파일 머리에 있다. 함수가 꼴과 다른 값을 돌려주면 제공 코드가 그 파일 · 경보를 밝혀 멈춘다.
`app/features/decisions.csv`의 `빈 값의 뜻` · `쓰는 사람에 따라 갈리는 답` 행의 `고른_것`은 결과의 `decisions`에, `비교 기준 문장` 행의 `고른_것`은 결과의 `comparison_basis`에 그대로 옮겨진다.

## 고른 것 (`app/features/decisions.csv`) · 기대 판정 (`app/features/expected.csv`)

- `app/features/decisions.csv` — 열 `지점,고른_것,근거,바뀌는_답`. 칸마다 뜻은 그 파일 첫머리 `#` 줄에 있다. 같은 종류의 지점이 여럿이면 지점마다 한 줄.
- `app/features/expected.csv` — 열 `사례,후보,기대_판정,근거`. `사례`는 `data/alarms.csv`의 RAISE 행 경보_ID. 제공 코드를 돌리기 전에 원자료 · 조건표 · 원문으로 손으로 구한 기대. `기대_판정`은 `유지` · `제외` · `보류`(뜻은 `data/work_standard.md` 4절), `근거`는 `파일:줄`.

## 결과 (`output/judgement.json` — 제공 코드가 쓴다)

```
{
  "comparison_basis": "이 비교값이 무엇을 견주는 값인지, 정책 점수와 어떻게 다른지",
  "decisions": [ {"item": "...", "decision": "판단 입력을 만든 방법 · 견주는 후보 등 정한 것", "basis": "파일 · 절"} ],
  "events": [
    {"id": "경보_ID", "asset": "HYD-..", "decision_time": "판정_요청_시각",
     "candidates": [ 후보 판정 ],
     "ranking": [ {"rank": 1, "sop": "...", "total": 0.0} ],
     "selection": {"reason": "1위를 고른 까닭 또는 순위가 없는 까닭", "checks": ["추가로 확인할 사항"]}}
  ]
}
```

후보 판정:

```
{"sop": "SOP-...", "status": "유지 | 제외 | 보류",
 "inputs": {"forecast_ts1": 숫자 또는 null, "forecast_ps1": ..., "fan100_hours": ..., "plc_mode": ..., "plc_state": ..., "skill_kind": ..., "skill_code": [...]},
 "missing_reasons": {"null인 입력": "왜 없는지(원천 · 시각)"},
 "warnings":   [ {"rule_id": "...", "reason": "...", "source_section": "...", "conditions": [ {"input": "...", "actual": 값, "operator": "...", "value": "...", "unit": "..."} ]} ],
 "penalties":  [ {위와 같음, "penalty_manwon": 숫자} ],
 "exclusions": [ {위와 같음} ],
 "unknown":    [ {"rule_id": "...", "result": "...", "missing": ["빠진 입력"], "source_section": "..."} ],
 "comparison": {"cost": 0, "production": 0, "quality": 0, "energy": 0, "penalty": 0, "total": 0} 또는 null,
 "no_comparison_reason": ["유지 후보인데 비교값이 없는 까닭"]}
```

- 키의 뜻: `comparison_basis` 비교 기준 문장, `decisions` 정한 것(`item` 항목 · `decision` 정한 방법 · `basis` 근거), `decision_time` 판정을 요청한 시각, `status` 판정,
  `inputs` 판단 입력, `missing_reasons` 값이 없는 까닭, `comparison` 비교값(`cost` 비용 · `production` 생산 · `quality` 품질 · `energy` 에너지 · `penalty` 감점 · `total` 합계, 만원),
  `no_comparison_reason` 비교값이 없는 까닭, `rank` 순위.
- 사례의 순서는 `data/alarms.csv`의 RAISE 행 순서, 후보의 순서는 `data/targets.csv`의 순서다.
- `status`는 `유지` · `제외` · `보류` 가운데 하나이고, 세 말의 뜻은 `data/work_standard.md` 4절의 말이다.
- `comparison`이 있는 후보는 `유지` 후보다. 비교값이 없는 유지 후보는 `no_comparison_reason`에 그 까닭을 적는다.
- 금액은 `metric_definitions.md` 식의 원값을 소수 둘째 자리로 반올림해 적고, `total`은 네 손실과 감점의 원값을 더한 뒤 반올림한다.
  반올림은 사사오입이다 — 셋째 자리가 5 이상이면 올린다(0.125는 0.13). 부동소수 계산의 작은 오차로 끝자리 5가 4999…가 되어 내려가지 않게 한다.
- 순위는 비교값이 있는 후보마다 하나이고 `total`이 작은 순서다. 같은 `total`은 같은 순위다(1, 1, 3).
- 이 결과만의 키: `warnings` 경고 · `penalties` 감점 · `exclusions` 제외(맞은 규칙과 조건마다 실제 값 `actual`), `penalty_manwon` 감점 금액(만원),
  `unknown` 입력이 없어 맞는지 알 수 없는 규칙(`missing` 빠진 입력), `ranking` 순위 목록, `selection` 고른 까닭(`reason` · `checks`).
- `ranking`은 사례마다 비교값이 있는 후보의 순위 목록이고 `total`은 그 후보의 `comparison.total`과 같다.
- `selection`의 `reason`은 1위를 고른 까닭(순위가 없으면 그 까닭), `checks`는 실행 전후에 추가로 확인할 사항이다.

## 제공 입력 (`data/criteria/`)

냉각 계통 조치의 조건표(condition_table.csv)와 SOP 구조(sop.json)입니다. 이 폴더는 읽기만 합니다.

sop.json 키의 뜻: `document` 원문 문서, `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차(`id` · `name` 이름 · `kind` 조치 종류(없으면 null) · `codes` 실행 코드 · `source` 출처 · `failure_mode` 고장 유형 · `model_refs` 모델 참조 · `apply_conditions` 적용 조건 · `prohibitions` 금지 조건 · `steps` 수행 단계 · `completion` 완료 기준 · `approval` 승인(`role` 역할)), `relations` 관계 목록. 항목마다 `text`는 원문 문장, `rules`는 그 조건을 옮긴 조건표의 `rule_id`다.
