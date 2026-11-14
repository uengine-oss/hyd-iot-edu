-- 2026-11-14 포털 개편 「학생의 선택이 결과로 돌아오게」 — 입고 · 검수(skill:receive-goods).
--
-- 전에는 어느 공급사에 발주했든 입고 검사가 늘 「합격」이었고, 공급사 로트 번호를 난수로 지어 넣었다(069). 구매 판단은 공급사를 불량률 ·
-- 가격 · 납기로 비교하게 하는데 그 불량률이 결과와 이어지지 않았다.
--
-- 모의 공급사 · 입고 검사의 규칙(이 업무 시스템이 흉내 내는 바깥세상이다. 무작위가 없다 — 같은 공급사 · 같은 수량이면 늘 같은 결과):
--   * 불합격 수량 = 발주 수량 × 그 공급사 견적의 불량률(ent.quote_rows.fail_rate)을 반올림한 개수. 수업 문서 PR-07 「PR-7.4」의 기대 불량
--     (수량 × 불량률)을 개수로 옮긴 것이고, 반올림은 이 시뮬레이터의 가정이다(원문은 기대값만 말한다). 입고 기록 글이 그 계산을 적는다.
--   * 불합격분은 반품하고 다시 들어오지 않는다(재납품은 새 발주다). 합격분만 실물 재고에 올리고, 입고 예정에서는 발주 수량 전부를 뺀다.
--   * 불합격이 0개면 발주는 「입고 완료」, 있으면 「부분 입고」다(PR-07 「PR-7.7」: 입고 수량이 발주 수량과 같고 로트가 기록되고 입고 검사에
--     합격해야 입고 완료). 처리 엔진은 입고 기록의 rejected_qty 로 흐름을 가른다(procsvc/service_parts._run_goods_receipt).
--   * 로트 번호는 발주 번호에서 만든다('LOT-' || 발주 번호). 부르는 쪽이 검사 결과 · 로트를 정해 보내면 거절한다.
--
-- 시드(seed.sql)에는 이 함수 · 이 칸이 없다(시드는 데이터만 넣는다) — 새 PC 와 쓰던 PC 모두 이 마이그레이션으로 같아진다.

alter table ent.goods_receipts add column if not exists ordered_qty integer;
alter table ent.goods_receipts add column if not exists rejected_qty integer not null default 0 check (rejected_qty >= 0);
alter table ent.goods_receipts add column if not exists fail_rate numeric;
alter table ent.goods_receipts drop constraint if exists goods_receipts_qty_check;
alter table ent.goods_receipts add constraint goods_receipts_qty_check check (qty >= 0);       -- 전부 불합격이면 입고 0개
update ent.goods_receipts set ordered_qty = qty where ordered_qty is null;
comment on column ent.goods_receipts.qty is '실물 재고에 올린 수량(입고 검사 합격분)';
comment on column ent.goods_receipts.ordered_qty is '발주 수량';
comment on column ent.goods_receipts.rejected_qty is '입고 검사 불합격 · 반품 수량(발주 수량 × 공급사 불량률을 반올림 — 모의 공급사 규칙)';
comment on column ent.goods_receipts.fail_rate is '검사 때 읽은 그 공급사 견적의 불량률';
comment on column ent.goods_receipts.basis is '입고 시각의 근거(처리 엔진이 리드타임 대기를 줄여 입고했을 때 그 까닭). 없으면 업무 시각 그대로';

create or replace function ent.exec_skill(p jsonb) returns jsonb
language plpgsql
as $$
declare
  v_skill text := p->>'skill';
  v_asset text := p->>'asset';
  v_decision text := p->>'decision';
  v_params jsonb := coalesce(p->'params', '{}'::jsonb);
  v_plan jsonb := p->'params'->'plan';
  v_fp text;
  v_prior ent.transactions; v_row ent.transactions;
  v_system text; v_ref text; v_detail text; v_before jsonb; v_after jsonb;
  v_sup text; v_sup_name text; v_part text; v_lot text;
  v_part_no text; v_qty integer; v_quote record; v_window record; v_window_label text; v_window_id text; v_window_at timestamptz;
  v_pr ent.purchase_requests; v_wo ent.work_orders; v_stock ent.spare_stock; v_std ent.task_standards;
  v_pm ent.pm_counters; v_pmset ent.pm_settings; v_status record; v_done numeric; v_days numeric;
  v_member jsonb; v_item jsonb; v_group text; v_first text;
  v_accepted integer; v_rejected integer;
begin
  select c.system into v_system from ent.skill_contracts c where c.skill = v_skill and c.kind = 'forward';
  if v_system is null then
    raise exception '업무 시스템에 없는 거래입니다: % (되돌리기 거래는 원거래 id compensates 와 함께 보냅니다)', coalesce(v_skill, '스킬 없음')
      using errcode = '22023';
  end if;
  if coalesce(v_asset, '') = '' then
    raise exception '거래 대상 설비(asset)가 없습니다 — 승인한 판단의 설비를 함께 보내야 합니다' using errcode = '22023';
  end if;
  if not exists (select 1 from ent.assets where code = v_asset) then
    raise exception '등록되지 않은 설비입니다: %', v_asset using errcode = '22023';
  end if;
  -- 원문 정비 범위 오더는 현장 · 시운전 기록 확인 뒤에만 끝난다
  if v_skill = 'skill:pm-reset' and exists (select 1 from ent.work_orders w join ent.pm_counters c on c.plan_wo = w.id
       where c.asset = v_asset and w.maintenance_plan is not null) then
    raise exception '원문 정비 범위 오더가 걸린 설비는 현장 · 시운전 완료 확인 뒤에 운전시간 계수기를 리셋합니다' using errcode = '22023';
  end if;
  if v_skill = 'skill:complete-maintenance' and exists (select 1 from ent.work_orders where id = v_params->>'ref' and maintenance_plan is not null) then
    raise exception '원문 정비 범위 오더의 완료는 현장 기록과 시운전 기록이 확인되어야 합니다' using errcode = '22023';
  end if;

  -- ---- 기존 정기 정비 오더 일정 변경 (054 · 058)
  if v_skill = 'skill:reschedule-maintenance' then
    if coalesce(v_decision, '') = '' or coalesce(p->>'by', '') = '' or coalesce(p->>'option', '') = '' or coalesce(v_params->>'ref', '') = ''
       or coalesce(v_params->>'window_id', '') = '' or jsonb_typeof(v_params->'expected_order') is distinct from 'object' then
      raise exception '정비 일정 변경에는 승인 · 기존 오더 사진(expected_order) · 정확한 목표 정비 시간(window_id)이 필요합니다' using errcode = '22023';
    end if;
    if v_plan is not null then
      perform ent.pm_scope_check(v_plan, v_asset, false);
      p := jsonb_set(p, array['params', 'expected_order'], (p->'params'->'expected_order') - 'reserved_parts');
      v_params := p->'params';
    end if;
    v_fp := md5(jsonb_build_object('decision', p->'decision', 'option', p->'option', 'skill', p->'skill', 'asset', p->'asset', 'params', p->'params')::text);
    perform pg_advisory_xact_lock(hashtextextended('ent.exec_skill:' || v_decision || ':' || v_skill, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and compensates is null;
    if found then
      if v_prior.fingerprint is distinct from v_fp then
        raise exception '같은 판단의 같은 거래가 다른 입력으로 이미 실행됐습니다(멱등 충돌)' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
    select * into v_pm from ent.pm_counters where asset = v_asset for update;
    if not found or v_pm.plan_wo is distinct from v_params->>'ref' or v_pm.cycle is distinct from (v_params->>'cycle')::integer then
      raise exception '오더 %는 이번 정기 정비 차례의 오더가 아닙니다', v_params->>'ref' using errcode = '22023';
    end if;
    select * into v_wo from ent.work_orders where id = v_pm.plan_wo and asset = v_asset for update;
    if not found or v_wo.status <> '배정됨' or v_wo.completed_at is not null or to_jsonb(v_wo) is distinct from v_params->'expected_order' then
      raise exception '승인한 뒤 오더 %가 바뀌었거나 일정을 바꿀 수 없는 상태입니다', v_params->>'ref' using errcode = '22023';
    end if;
    select * into v_status from ent.pm_status where asset = v_asset;
    if v_status.following_window_id is distinct from v_params->>'window_id'
       or v_status.hours_at_following_window is null
       or v_status.hours_at_following_window > v_status.pm_interval_h * (1 + v_status.pm_tolerance_pct / 100) then
      raise exception '목표 정비 시간 %가 그다음 예정된 정비 시간이 아니거나 정기 정비 허용 한계를 넘습니다', v_params->>'window_id' using errcode = '22023';
    end if;
    select * into v_window from ent.next_maintenance_windows(v_asset, 14) where id = v_params->>'window_id';
    if not found then
      raise exception '목표 정비 시간 %가 정비 일정에 없습니다', v_params->>'window_id' using errcode = '22023';
    end if;
    v_before := to_jsonb(v_wo);
    update ent.work_orders set window_id = v_window.id, window_starts_at = v_window.starts_at, window_label = v_window.label where id = v_wo.id;
    update ent.pm_counters set plan_window = v_window.label, planned_at = now(), updated_at = now() where asset = v_asset;
    select to_jsonb(w) into v_after from ent.work_orders w where id = v_wo.id;
    insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, before, after)
    values (ent.new_ref('TX'), v_system, v_skill, v_wo.id,
            format('%s 정기 정비 오더 %s 일정 변경 — %s %s', v_asset, v_wo.id, v_window.label,
                   to_char(v_window.starts_at at time zone 'Asia/Seoul', 'MM-DD HH24:MI')),
            v_asset, v_decision, p->>'option', p->>'by', v_fp, v_before, v_after)
    returning * into v_row;
    return ent.tx_response(v_row);
  end if;

  v_fp := md5(jsonb_build_object('decision', p->'decision', 'option', p->'option', 'skill', p->'skill', 'asset', p->'asset', 'params', p->'params')::text);

  -- ---- 원문 정비 범위 오더 등록 (056 · 058)
  if v_skill = 'skill:schedule-maintenance-scoped' then
    if coalesce(v_decision, '') = '' or coalesce(p->>'by', '') = '' or coalesce(p->>'option', '') = '' or v_plan->>'code' is distinct from 'WO_CREATE' then
      raise exception '원문 정비 범위 오더 등록에는 승인한 정비 계획(WO_CREATE)이 필요합니다' using errcode = '22023';
    end if;
    perform pg_advisory_xact_lock(hashtextextended('ent.exec_skill:' || v_decision || ':' || v_skill, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and compensates is null;
    if found then
      if v_prior.fingerprint is distinct from v_fp then
        raise exception '같은 판단의 같은 거래가 다른 입력으로 이미 실행됐습니다(멱등 충돌)' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
    perform ent.pm_scope_check(v_plan, v_asset, true);
    v_group := 'PM-SCOPE-' || md5(v_decision || ':' || (p->>'option'));
    for v_member in select x from jsonb_array_elements(v_plan->'assets') x loop
      v_ref := ent.new_ref('WO');
      if v_first is null then v_first := v_ref; end if;
      insert into ent.work_orders (id, asset, task, window_label, decision_id, option_id, requested_by, window_id, window_starts_at, scope_group, maintenance_plan, package)
      values (v_ref, v_member->>'asset', coalesce(v_params->>'task', v_member->'service'->>'package_name'),
              coalesce(v_plan->'window'->>'label', case when (v_plan->'window'->>'immediate')::boolean then '즉시' else '예정된 정비 시간' end),
              v_decision, p->>'option', p->>'by',
              case when (v_member->'window'->>'immediate')::boolean then null else v_member->'window'->>'id' end,
              (v_member->'window'->>'starts_at')::timestamptz, v_group, v_plan, v_member->'service');
      update ent.pm_counters set plan_wo = v_ref, plan_window = coalesce(v_plan->'window'->>'label', '예정된 정비 시간'), planned_at = now(), updated_at = now()
       where asset = v_member->>'asset';
      for v_item in select x from jsonb_array_elements(v_member->'parts') x loop
        insert into ent.pm_part_reservations (work_order, part_no, qty, stock_effect)
        values (v_ref, v_item->>'part_no', (v_item->>'qty')::numeric, v_plan->>'stock_effect');
      end loop;
    end loop;
    for v_item in select x from jsonb_array_elements(v_plan->'parts_totals') x loop
      if v_plan->>'stock_effect' = 'reserve' then
        update ent.spare_stock set reserved = reserved + (v_item->>'qty')::numeric, updated_at = now() where part_no = v_item->>'part_no';
      else
        update ent.spare_stock set on_hand = on_hand - (v_item->>'qty')::numeric, updated_at = now() where part_no = v_item->>'part_no';
      end if;
      perform ent.refresh_spare_flag(v_item->>'part_no');
    end loop;
    select jsonb_build_object('plan', v_plan, 'orders', jsonb_agg(to_jsonb(w) || jsonb_build_object('ref', w.id) order by w.asset)) into v_after
      from ent.work_orders w where scope_group = v_group;
    insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, before, after)
    values (ent.new_ref('TX'), v_system, v_skill, v_first,
            '원문 정비 범위 ' || (select string_agg(x->>'asset', ', ' order by ord) from jsonb_array_elements(v_plan->'assets') with ordinality as a(x, ord)) || ' 오더 등록',
            v_asset, v_decision, p->>'option', p->>'by', v_fp, null, v_after)
    returning * into v_row;
    return ent.tx_response(v_row);
  end if;

  -- ---- 나머지 거래(045 본문 · 060 번호): 결정이 있으면 결정 · 스킬마다 한 번
  if v_decision is not null then
    perform pg_advisory_xact_lock(hashtextextended('ent.exec_skill:' || v_decision || ':' || v_skill, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and compensates is null;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception '같은 판단의 같은 거래가 다른 입력으로 이미 실행됐습니다(멱등 충돌)' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
  end if;

  if v_skill = 'skill:schedule-maintenance' then
    if coalesce(v_params->>'task', '') = '' then
      raise exception '정비 작업지시에 작업 내용(task)이 없습니다' using errcode = '22023';
    end if;
    v_window_label := nullif(v_params->>'window', '');
    if v_params ? 'window_id' then                       -- 승인된 예정된 정비 시간 id → 라벨 · 시작 시각 (설비가 다르거나 없는 창은 거절)
      select * into v_window from ent.next_maintenance_windows(v_asset, 14) w where w.id = v_params->>'window_id';
      if not found then
        raise exception '%의 정비 일정에 없는 정비 시간입니다: %', v_asset, v_params->>'window_id' using errcode = '22023';
      end if;
      v_window_id := v_window.id; v_window_at := v_window.starts_at;
      v_window_label := coalesce(v_window_label, v_window.label || ' ' || to_char(v_window.starts_at at time zone 'Asia/Seoul', 'MM-DD HH24:MI'));
    elsif v_params ? 'window_starts_at' then
      v_window_at := (v_params->>'window_starts_at')::timestamptz;
      v_window_label := coalesce(v_window_label, '예정된 정비 시간 ' || to_char(v_window_at at time zone 'Asia/Seoul', 'MM-DD HH24:MI'));
    end if;
    if v_window_label is null then
      raise exception '정비 작업지시에 정비 시점(window · window_id · window_starts_at)이 없습니다' using errcode = '22023';
    end if;
    v_ref := ent.new_ref('WO');
    insert into ent.work_orders (id, asset, task, window_label, decision_id, option_id, requested_by, window_id, window_starts_at)
    values (v_ref, v_asset, v_params->>'task', v_window_label, v_decision, p->>'option', p->>'by', v_window_id, v_window_at);
    v_detail := format('%s %s — %s', v_asset, v_params->>'task', v_window_label);
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_ref;

  elsif v_skill = 'skill:procure-part' then
    v_sup := nullif(v_params->>'supplier', '');
    if v_sup is null then
      raise exception '구매요청에 승인한 공급사(supplier)가 없습니다 — 다른 공급사로 대신 발주하지 않습니다' using errcode = '22023';
    end if;
    select name into v_sup_name from ent.suppliers where id = v_sup;
    if not found then
      raise exception '등록되지 않은 공급사입니다: %', v_sup using errcode = '22023';
    end if;
    v_ref := ent.new_ref('PR');
    if v_params ? 'part_no' then                         -- 부품 번호 · 수량이 있는 발주 — 견적 · AVL · 금액을 ERP 가 다시 확인한다
      v_part_no := v_params->>'part_no';
      v_qty := (v_params->>'qty')::integer;
      if v_qty is null or v_qty <= 0 then
        raise exception '발주 수량은 1 이상이어야 합니다' using errcode = '22023';
      end if;
      select name into v_part from ent.parts where part_no = v_part_no;
      if not found then
        raise exception '등록되지 않은 부품 번호입니다: %', v_part_no using errcode = '22023';
      end if;
      select * into v_quote from ent.quote_rows(v_part_no) q where q.supplier_id = v_sup;
      if not found then
        raise exception '공급사 %에는 %의 견적이 없습니다', v_sup, v_part_no using errcode = '22023';
      end if;
      if not v_quote.avl then
        raise exception '공급사 %는 승인 공급사 목록(AVL)에 없어 발주하지 않습니다', v_sup using errcode = '22023';
      end if;
      if v_params ? 'amount' and (v_params->>'amount')::numeric <> v_quote.price * v_qty then
        raise exception '승인한 금액 %만원이 견적 %개 × %만원과 다릅니다', v_params->>'amount', v_qty, v_quote.price using errcode = '22023';
      end if;
      insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by,
                                         part_no, qty, unit_price, amount, lead_d, expected_at)
      values (v_ref, v_part, v_sup, v_sup_name, v_asset, v_decision, p->>'option', p->>'by',
              v_part_no, v_qty, v_quote.price, v_quote.price * v_qty, v_quote.lead_d, now() + make_interval(days => v_quote.lead_d));
      update ent.spare_stock set on_order = on_order + v_qty, updated_at = now() where part_no = v_part_no returning * into v_stock;
      if v_stock.part_no is not null then
        perform ent.refresh_spare_flag(v_part_no);
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_part_no, 'ORDER', v_qty, v_asset, v_ref, p->>'by', format('발주 %s 입고 예정', v_ref), v_stock.on_hand,
                v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
      v_detail := format('%s %s개 발주 — %s, %s만원, 리드타임 %s일', v_part, v_qty, v_sup_name, v_quote.price * v_qty, v_quote.lead_d);
    else                                                 -- 부품 번호 없는 구매요청(시나리오 A 쿨러 코어 교체 카드): 품목 이름이 있어야 한다
      v_part := nullif(v_params->>'part', '');
      if v_part is null then
        raise exception '구매요청에 품목(part 또는 part_no)이 없습니다' using errcode = '22023';
      end if;
      insert into ent.purchase_requests (id, part, supplier, supplier_name, asset, decision_id, option_id, requested_by)
      values (v_ref, v_part, v_sup, v_sup_name, v_asset, v_decision, p->>'option', p->>'by');
      v_detail := format('%s 구매요청 — %s', v_part, v_sup_name);
    end if;
    select to_jsonb(r) into v_after from ent.purchase_requests r where r.id = v_ref;

  elsif v_skill = 'skill:receive-goods' then              -- 발주 한 건의 입고 · 검수 (모의 공급사의 납품 · 입고 검사 포함 — 머리말의 규칙)
    if length(v_params->>'basis') > 300 then
      raise exception '입고 시간 근거(basis)는 300자까지입니다' using errcode = '22023';
    end if;
    if v_params ? 'inspection' or v_params ? 'lot' then
      raise exception '입고 검사 결과와 로트 번호는 부르는 쪽이 정하지 않습니다 — 업무 시스템이 발주와 공급사 견적으로 정합니다' using errcode = '22023';
    end if;
    select * into v_pr from ent.purchase_requests where id = v_params->>'ref' for update;
    if not found then raise exception '없는 발주입니다: %', v_params->>'ref' using errcode = '22023'; end if;
    if v_pr.qty is null then raise exception '발주 %에는 입고할 수량이 없습니다', v_pr.id using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then
      raise exception '발주 %는 지금 상태(%)에서 입고할 수 없습니다', v_pr.id, v_pr.status using errcode = '22023';
    end if;
    select * into v_quote from ent.quote_rows(v_pr.part_no) q where q.supplier_id = v_pr.supplier;
    if not found then
      raise exception '발주 %의 공급사 % 견적(불량률)이 없어 입고 검사 결과를 정할 수 없습니다', v_pr.id, v_pr.supplier using errcode = '22023';
    end if;
    v_before := to_jsonb(v_pr);
    v_ref := ent.new_ref('GR');
    v_lot := 'LOT-' || v_pr.id;                                   -- 모의 공급사의 로트 = 발주 번호에서 만든다(난수로 짓지 않는다)
    v_rejected := least(v_pr.qty, round(v_pr.qty * v_quote.fail_rate)::integer);   -- 기대 불량(수량 × 불량률)을 반올림
    v_accepted := v_pr.qty - v_rejected;
    insert into ent.goods_receipts (id, pr_id, part_no, qty, lot, inspection, decision_id, basis, ordered_qty, rejected_qty, fail_rate)
    values (v_ref, v_pr.id, v_pr.part_no, v_accepted, v_lot,
            case when v_rejected = 0 then '합격' else format('%s개 불합격 · 반품', v_rejected) end,
            v_decision, nullif(v_params->>'basis', ''), v_pr.qty, v_rejected, v_quote.fail_rate);
    update ent.purchase_requests set status = case when v_rejected = 0 then '입고 완료' else '부분 입고' end, received_at = now(),
           receipt_basis = nullif(v_params->>'basis', '') where id = v_pr.id;
    -- 반품한 수량은 다시 들어오지 않는다(재납품은 새 발주) — 입고 예정에서 발주 수량 전부를 빼고, 실물은 합격분만 올린다
    update ent.spare_stock set on_hand = on_hand + v_accepted, on_order = greatest(on_order - v_pr.qty, 0) where part_no = v_pr.part_no
      returning * into v_stock;
    if v_stock.part_no is not null then
      perform ent.refresh_spare_flag(v_pr.part_no);
      if v_accepted > 0 then
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_pr.part_no, 'RECEIPT', v_accepted, v_asset, v_ref, p->>'by',
                format('발주 %s 입고', v_pr.id) || case when v_rejected > 0 then format(' (검수 불합격 %s개 반품)', v_rejected) else '' end,
                v_stock.on_hand, v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
    end if;
    v_detail := case when v_rejected = 0
        then format('%s %s개 입고 · 검수 합격 (발주 %s, 로트 %s)', v_pr.part, v_pr.qty, v_pr.id, v_lot)
        else format('%s 발주 %s개 중 %s개 입고 · %s개 검수 불합격 반품 (발주 %s, 로트 %s, %s 불량률 %s %% × %s개 = 기대 불량 %s개)',
                    v_pr.part, v_pr.qty, v_accepted, v_rejected, v_pr.id, v_lot, v_pr.supplier_name,
                    trim_scale(v_quote.fail_rate * 100), v_pr.qty, trim_scale(v_pr.qty * v_quote.fail_rate)) end
      || coalesce(' — ' || nullif(v_params->>'basis', ''), '');
    select to_jsonb(g) into v_after from ent.goods_receipts g where g.id = v_ref;

  elsif v_skill = 'skill:complete-maintenance' then       -- 작업지시 완료 + SOP 표준 부품 소모
    select * into v_wo from ent.work_orders where id = v_params->>'ref' for update;
    if not found then raise exception '없는 작업지시입니다: %', v_params->>'ref' using errcode = '22023'; end if;
    if v_wo.status <> '배정됨' then
      raise exception '작업지시 %는 지금 상태(%)에서 완료할 수 없습니다', v_wo.id, v_wo.status using errcode = '22023';
    end if;
    v_before := to_jsonb(v_wo);
    select * into v_std from ent.task_standards where sop = v_params->>'sop';
    if found and v_std.part_no is not null and v_std.part_qty > 0 then
      select * into v_stock from ent.spare_stock where part_no = v_std.part_no for update;
      if found and v_stock.on_hand < v_std.part_qty then
        raise exception '%는 실물 %개뿐이라 정비 소모 %개를 기록할 수 없습니다', v_std.part_no, v_stock.on_hand, v_std.part_qty using errcode = '22023';
      end if;
    end if;
    update ent.work_orders set status = '완료', completed_at = now() where id = v_wo.id;
    insert into ent.maintenance_history (asset, wo, task, performed_at) values (v_wo.asset, v_wo.id, v_wo.task, now());
    if v_std.part_no is not null and v_std.part_qty > 0 then
      update ent.spare_stock set on_hand = on_hand - v_std.part_qty where part_no = v_std.part_no returning * into v_stock;
      if v_stock.part_no is not null then
        perform ent.refresh_spare_flag(v_std.part_no);
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_std.part_no, 'CONSUME', v_std.part_qty, v_wo.asset, v_wo.id, p->>'by', format('%s 정비 소모', v_params->>'sop'),
                v_stock.on_hand, v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
    end if;
    v_ref := v_wo.id;
    v_detail := format('%s 작업지시 %s 완료 (%s)%s', v_wo.asset, v_wo.id, v_wo.task,
                       case when v_std.part_no is not null then format(' — %s %s개 소모', v_std.part_no, v_std.part_qty) else '' end);
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_wo.id;

  elsif v_skill = 'skill:pm-reset' then                   -- 시나리오 B: 시운전 통과 뒤 계수기 리셋 · 다음 기한 기록
    select * into v_pm from ent.pm_counters where asset = v_asset for update;
    if not found then raise exception '%에는 정기 정비 계획이 없습니다', v_asset using errcode = '22023'; end if;
    v_before := to_jsonb(v_pm); v_done := v_pm.since_pm_h;
    update ent.pm_counters set since_pm_h = 0, cycle = cycle + 1, last_done_at = now() where asset = v_asset;
    perform ent.refresh_pm_flag(v_asset);
    select * into v_pm from ent.pm_counters where asset = v_asset;
    select * into v_pmset from ent.pm_settings where id = 1;
    v_ref := ent.new_ref('PMR');
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (v_asset, 'RESET', -v_done, 0, v_pm.total_h, v_pm.cycle, v_ref, p->>'by',
            coalesce(v_params->>'reason', format('정기 정비 완료 (%s)', coalesce(v_params->>'ref', '-'))));
    v_detail := format('%s 운전시간 계수기 리셋 (%s h 에 정기 정비) — 다음 기한 %s h (허용 %s~%s h)', v_asset, v_done, v_pmset.interval_h,
                       trim_scale(round(v_pmset.interval_h * (1 - v_pmset.tolerance_pct / 100), 1)), trim_scale(round(v_pmset.interval_h * (1 + v_pmset.tolerance_pct / 100), 1)));
    v_after := to_jsonb(v_pm);

  elsif v_skill = 'skill:delay-delivery' then             -- 시나리오 C 미달 가지: 공급사 납기 지연 통보
    v_days := (v_params->>'days')::numeric;
    if v_days is null or v_days <= 0 or v_days > 60 then
      raise exception '지연 일수(days)는 0 초과 60 이하여야 합니다' using errcode = '22023';
    end if;
    select * into v_pr from ent.purchase_requests r
     where r.status = '승인됨 → 발주' and r.qty is not null
       and (not v_params ? 'ref' or r.id = v_params->>'ref') and (not v_params ? 'part_no' or r.part_no = v_params->>'part_no')
     order by r.created_at desc limit 1 for update;
    if not found then raise exception '납기를 늦출 열린 발주가 없습니다' using errcode = '22023'; end if;
    v_before := to_jsonb(v_pr);
    update ent.purchase_requests set delay_d = delay_d + v_days, expected_at = expected_at + make_interval(secs => v_days * 86400)
     where id = v_pr.id returning * into v_pr;
    v_ref := v_pr.id;
    v_detail := format('발주 %s 납기 %s일 지연 통보 — 리드타임 %s+%s일', v_pr.id, v_days, v_pr.lead_d, v_pr.delay_d);
    v_after := to_jsonb(v_pr);
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, before, after)
  values (ent.new_ref('TX'), v_system, v_skill, v_ref, v_detail, v_asset, v_decision, p->>'option', p->>'by', v_fp, v_before, v_after)
  returning * into v_row;
  return ent.tx_response(v_row);
end $$;

revoke execute on function ent.exec_skill(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_skill(jsonb) to service_role;
