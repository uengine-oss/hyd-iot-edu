# 제공된 모델의 자료 처리 근거

이 모델(schema.json · graph.json)은 원자료와 현장 메모로 만든 설계 단계의 완성 모델입니다. 이번 실습의 적재 · 조회 결과가 아닙니다. 처리 기준은 schema.json의 constraints에 적혀 있습니다.

- 설비: 다른 줄과 기능위치 · 일련번호 · 설치일이 같고 가동 중이 아닌 옛 코드 줄은 대상을 새로 만들지 않고 legacy_codes로 남겼습니다.
- 구성 요소와 실물: 구성 요소(Component)는 설비 안의 구성 요소 자리이고, 구성 요소 목록에 일련번호가 적힌 장치는 실물(Unit)로 따로 두었습니다. INSTALLED_UNIT의 current가 true면 지금 달린 실물, false면 철거된 실물입니다.
- 센서: 같은 설비 · 태그의 점검표 재기입 행은 하나로 두었습니다. 단위는 물리량 기준 단위로 맞추고 바꾼 경우 source_unit을 남겼습니다. 계산값 · 설정값은 kind로 구별했습니다. 한계가 없으면 limit을 생략했습니다. 같은 물리량은 재는 값의 종류와 붙은 계통까지 같아야 묶었습니다(탱크에 붙은 유온계는 탱크 유온, 쿨러 입구와 출구 유온은 따로).
- 센서 HYD-03:VS1: `data/sensors.csv` 54행은 단위 칸이 비어 있어, 같은 모델 · 같은 태그로 정상값 · 한계까지 같은 줄(16행 · 35행)을 근거로 단위를 mm/s로 두었습니다.
- 부품: 교체부품 칸의 품명 · 표기 변형 · 제조사 품번은 품번 교차표와 예비품 목록의 적용 모델 · 쓰는곳으로 사내 품번에 이었습니다. 같은 규격의 다른 사내 품번은 따로 두었습니다. 같은 모델 · 같은 쓰는곳의 예비품이 둘 이상이면 같은 모델의 다른 설비가 그 구성 요소에 적은 품번으로 이었습니다.
- HYD-03 주 펌프: `data/components.csv` 29행은 교체부품 칸이 비어 있습니다. 같은 모델(HPP-45A)의 주 펌프에 적용되는 예비품이 `data/spare_parts.csv` 2행 P-PMP-SEAL 하나뿐이고, `data/receipts.csv` 15행 비고의 정비 예약 기능위치 CW1-L2-HPU-03가 설비 대장의 HYD-03이라 P-PMP-SEAL로 이었습니다.
- 공급: 공급사 · 품번마다 기준일에 유효한 최신 견적 하나를 SUPPLIES로 두었습니다. 공급사 이름은 approved_suppliers.csv(SCM 등록)의 이름입니다(견적표의 공급사 칸은 그 이름으로 시작합니다). 승인 여부는 approved_suppliers.csv과 기준일로 정했습니다(조건부 승인은 approved=true, 조건은 condition). 단가는 만원, 불량률은 0~1 비율, 납기는 일로 맞추고, 바꾼 불량률 · 납기는 원래 표기를 defect_rate_original · lead_days_original로 남겼습니다.
- 출처: SUPPLIES마다 값이 온 곳을 남겼습니다 — quote_source = 그 쌍에 쓴 견적의 `data/supply_terms.csv` 줄(견적일은 quote_date), approval_source = `data/approved_suppliers.csv`의 등록 줄, as_of = 승인 · 유효기한을 판단한 기준일, rule_source = inspection · compare_extra_manwon 값이 온 `data/purchasing_standard_pr07.md` 줄. 줄 번호는 편집기에 보이는 번호(머리줄이 1행)입니다.
