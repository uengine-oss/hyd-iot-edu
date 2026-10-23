-- 2026-10-23 전수 검수: 팬 베어링(P-FAN-BRG)의 ERP 재주문점 · 목표 재고(1 · 3, 마이그레이션 045)가 수업 문서 PR-07 PR-7.2 표(2 · 4)와 달랐다.
-- 문서가 정본이다(검토된 수업 문서, 예비품 기준의 주인). 적재한 PR-07을 읽은 판단과 ERP 재고 감시가 다른 기준을 쓰지 않게 맞춘다.
-- 실물 3 · 예약 0이라 가용 3 ≥ 2 — 수업 시작 상태에 재고 기준 이탈 경보는 생기지 않는다. 강사가 값을 바꿔 둔 PC는 덮어쓰지 않는다(옛 값일 때만).
update ent.spare_stock set reorder_point = 2, target_stock = 4, updated_at = now()
 where part_no = 'P-FAN-BRG' and reorder_point = 1 and target_stock = 3;
select ent.refresh_spare_flag('P-FAN-BRG');
