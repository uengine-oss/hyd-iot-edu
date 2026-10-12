# 예비품 구매 (시나리오 C)

예비품 재고 기준 이탈 경보(SPARE_BELOW_MIN, ERP 재고) 한 건에서 실제 부족부품과 필요량을 확인하고 공급사를 비교해 발주 카드를 올린다.
구매 업무는 부품이 근거다. 고장 원인·고장 유형을 구매 근거로 대신하지 않는다. 승인 전에는 조회·계산·판단 카드 등록만 한다. 발주·메일·입고는 구매 담당의 승인 뒤 시스템이 한다.

## 절차
1. `context/task.json`의 입력에서 asset·pattern·alert.evidence(부품·가용·부족량·필요량)·incident·alert.alertId를 UTF-8로 읽는다.
2. enterprise-purchase `spare_stock(asset)`에서 재주문점 아래인 실제 부품 번호와 필요량을 확인한다. 부품을 하나로 확정할 근거가 없으면 지어내지 않고 보류한다.
3. hyd-dmn `purchase_context(asset, part_no)`로 해당 부품에 적용되는 원문 구매 절차와 실행 여부를 확인한다. 참고 보관 절차를 실행 후보로 바꾸지 않는다.
4. enterprise-purchase `part_quotes(asset, part)`로 공급사별 단가·리드타임·불량률·AVL을 확인한다. `scm_suppliers`는 별도 등록 자료이므로 그 결과가 0건이라는 이유로 실제 견적을 없다고 판단하지 않는다.
5. hyd-dmn `evaluate_purchase(asset, part_no)`로 원문에 명시된 발주 대안의 금액·납기·AVL·불량 비용·규정·순위를 비교한다. 최단 납기 절차는 전체 견적에서 먼저 최단을 선택한 뒤 AVL을 확인하며, 미승인 공급사를 다른 공급사로 바꿔 적합하게 만들지 않는다.
   300만 원 초과는 전결 기준 초과 표시와 구매팀장 보고 대상이며 추가 승인이 아니다. 승인은 구매 담당 한 번이다.
6. hyd-dmn `submit_purchase(asset, part_no, incident, alert_id, process_scope)`로 승인 대기 판단을 등록한다. 이 작업의 process_scope를 그대로 전달한다. 반환 status가 SUBMITTED인지 확인하고 그 판단 id를 decision_id로 낸다. 평가 실행 id나 과거 판단을 제출하지 않는다.

## 결과
공통 결과 폼의 cause·failure_mode·guide_card는 빈 값으로 두고, decision{recommended, explanation, order}·decision_id를 실제 구매 판단으로 채운다. 빈 고장 필드는 구매 업무의 근거가 없다는 뜻이며 고장 ID를 생성하라는 뜻이 아니다.
explanation은 한국어 두세 문장으로 추천 공급사·수량·금액과 근거, 지는 공급사의 이유(AVL·납기·불량)를 적는다. 실제 원천이나 후보가 부족하면 폼을 억지로 채우지 않고 근거와 함께 보류한다.
