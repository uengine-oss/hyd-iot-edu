-- B-ERP-20261012-v1: official educational ERP initialization, not observed real inventory.
-- PM-02 source requires one return-filter element in base and 4,000h packages.
-- The existing graph maps P-RTN-FLT, but the ERP initializer omitted its master/stock rows.
-- Price 12 (만원), on-hand 2, reorder 1 and target 2 are educational design values.
-- Design/provenance: docs/handoff/verification/2026-10-12/education-fixture-correction/b-spec.md
-- Missing rows only: existing names/prices/stock/reservations/orders remain immutable here.
-- No oil part/quantity, source policy, window, staffing, or A/C fixture changes.

insert into ent.parts (part_no, name, std_price) values
  ('P-RTN-FLT', '리턴 필터 엘리먼트', 12)
on conflict (part_no) do nothing;

insert into ent.spare_stock (part_no, on_hand, reserved, on_order, reorder_point, target_stock,
                            reserved_for, base_on_hand, base_reserved, need_by_days) values
  ('P-RTN-FLT', 2, 0, 0, 1, 2, 'HYD-02', 2, 0, null)
on conflict (part_no) do nothing;
