# 세 출처의 스키마와 준비 자료

모든 행은 이번 제작에서 작성한 수업용 가상 입력이다. 실제 조회 결과·현재 재고·이번 실행 결과가 아니다. 이벤트는 alertId/asset/pattern/severity/state/t/evidence 구조, 정비 이력은 it/supabase/seed.sql의 ent.maintenance_history(asset,wo,task,performed_at), 부품은 같은 파일의 ent.spare_stock 필드 구조를 따른다.

이벤트의 t는 사건 시각, performed_at은 정비 수행 시각이다. 부품 파일에는 관측·갱신 시각이 없으므로 현재 재고라고 단정하지 않는다. 조회 시각은 제공하지 않았으므로 수업에서 실제로 읽은 시각을 별도 기록한다. 과거 정비 이력이 이후 경보의 해소나 현재 작업 완료를 증명하지 않는다. HYD-02용 부품을 HYD-01 경보에 근거 없이 연결하지 않는다. 새 경보의 작업지시·미완료 요청 여부는 앞 실습 결과 또는 추가 근거가 없으면 미확인이다.
