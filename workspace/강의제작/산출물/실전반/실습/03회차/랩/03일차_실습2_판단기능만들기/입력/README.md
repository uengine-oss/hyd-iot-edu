냉각 계통 조치의 조치 조건표(조건표.csv)와 제공 SOP 구조(sop.json)입니다. 조건표의 형식은 입출력_계약.md에 있습니다. 이 폴더는 읽기만 합니다.

sop.json 키의 뜻: `document` 원문 문서, `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차(`id` · `name` 이름 · `kind` 조치 종류(없으면 null) · `codes` 실행 코드 · `source` 출처 · `failure_mode` 고장 유형 · `model_refs` 모델 참조 · `apply_conditions` 적용 조건 · `prohibitions` 금지 조건 · `steps` 수행 단계 · `completion` 완료 기준 · `approval` 승인(`role` 역할)), `relations` 관계 목록. 항목마다 `text`는 원문 문장, `rules`는 그 조건을 옮긴 조건표의 `rule_id`다.
