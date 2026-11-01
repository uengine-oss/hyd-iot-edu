-- 2026-10-30 시스템 건강검진(작업/2026-10-30_시스템-건강검진/검진/FE_고침.md) — 업무 DB 고침. 이미 쓰던 학생 PC 의 DB 에도 같은 결과가 되게 쓴다.
--  1. 쓰지 않는 쓰기 길 닫기(G2-02): 제품 화면용으로 들여온 「로그인한 누구나 모든 표 쓰기」 정책 · 권한을 지우고, 재작업 영수증 표를 잠근다.
--     process · 워커는 postgres 소유자 연결, 에이전트 읽기는 hyd_enterprise_reader 라 영향이 없다. Supabase API · 가입은 config.toml 에서 끈다.
--  2. 수업 neo4j 조회 도구를 dmn-mcp 의 HTTP 주소로(결정 3, H-4) — 기준 설정(stdio python -m hydcommon.neo4j_mcp)일 때만 바꾼다.
--  3. 예비품 구매 기준 스킬 본문을 seed 와 같게(G2-08) — 053 의 새 판일 때만 바꾼다(학생이 고친 본문은 그대로).
--  4. 업무 거래 함수 한 벌(G2-01 · 05 · 09 · 10 · 16, H-11): 거래 계약 표(ent.skill_contracts) 한 곳. exec_skill · exec_compensation 이 이름을 바꿔 감싸던 사슬(…_before_pm54 · _before_pm56)을
--     한 함수씩으로 합친다. 계약 입력이 없으면 기본값으로 채우지 않고 거절한다(설비 HYD-01 · 공급사 sup:b · 작업 'SOP-COOL-02' · 부품 '쿨러 코어' ·
--     정비 시점 'derate' 글자 규칙). 재고가 모자란 소모 · 검수 불합격 입고는 거절한다. process 가 부르지 않는 거래(issue-spare · pm-advance ·
--     옛 A 표본 reallocate-production · hold-lot · release-lot · substitute-shipment · demand-control 과 그 되돌리기)는 지운다. 거절 문장은 한국어.
--     되돌리기는 원거래 id(compensates)가 있어야 하고, 그 원거래의 스킬이 맞는 되돌리기여야 한다 — 되돌리기 계약의 주인이 이 함수다.
--     원문 정비 범위 검사(pm_scope_check) · B · C 초기화의 영어 거절 문장도 한국어로(본문은 그대로).
--  5. 부르는 곳 없는 업무 전체 초기화 · 보관(ent.reset_executions · execution_archive_read · execution_archive) 삭제(G2-10).
--  6. CMMS 정비 이력(G2-11 · 15): 작업지시는 최근 20건(전체 수는 따로), 「다음 야간 정비 시간」은 예정된 정비 시간 규칙 한 곳에서 계산 — 프로필의 고정 시각 칸을 지운다.
--  7. 에이전트 · 학생이 읽는 업무 표 설명에서 개발 작업 번호 · 개발자 말을 뺀다(G2-16).
--  8. 068 이 닫은 중복 처리 건에 남은 승인 전달 대기 행을 폐기로(G2-24).
--  9. CMMS 표준 작업을 지금 지식의 SOP 번호로(FG 넘김 — 옛 번호라 손익이 모든 작업지시 카드에서 「미확인」이었다). 옛 번호 행은 지운다.
-- 10. 설비 상태에 실려 1초마다 쌓인 같은 명령 응답의 중복 접수 행 정리(P2-01 — 코드는 FB 가 고쳤다, 이미 쌓인 행만).
-- 11. 처리 기록 스트림 위치를 events 칸 하나로(G2-11 · FA1 넘김 — 조회마다 events 전체를 훑던 별도 표를 지운다), 부르는 곳 없는 30분 정리 함수 삭제.

-- ---------------------------------------------------------------- 1. 쓰지 않는 쓰기 길
do $$ declare r record; begin
  for r in select schemaname, tablename, policyname from pg_policies
            where schemaname = 'public' and policyname like '%\_write\_authenticated' escape '\' loop
    execute format('drop policy %I on %I.%I', r.policyname, r.schemaname, r.tablename);
  end loop;
end $$;
revoke insert, update, delete, truncate, references, trigger on all tables in schema public from anon, authenticated;
alter default privileges in schema public revoke insert, update, delete, truncate, references, trigger on tables from anon, authenticated;
alter table public.process_rework_receipt enable row level security;
revoke all on public.process_rework_receipt from public, anon, authenticated;
grant select, insert, update, delete on public.process_rework_receipt to service_role;

-- ---------------------------------------------------------------- 2. 수업 neo4j 조회 도구 주소
update public.tenants
   set mcp = jsonb_set(mcp, '{mcpServers,neo4j}',
                       '{"type": "url", "url": "http://dmn-mcp:8198/neo4j/mcp", "transport": "streamable_http"}'::jsonb)
 where mcp->'mcpServers'->'neo4j'->>'command' in ('python', 'python3')
   and mcp->'mcpServers'->'neo4j'->'args' = '["-m", "hydcommon.neo4j_mcp"]'::jsonb;

-- ---------------------------------------------------------------- 3. 예비품 구매 기준 스킬 본문
update public.tenant_skills
   set content = $seed$# 예비품 구매 (시나리오 C)

예비품 재고 기준 이탈 경보(SPARE_BELOW_MIN, ERP 재고) 한 건에서 실제 부족부품과 필요량을 확인하고 공급사를 비교해 발주 카드를 올린다.
구매 업무는 부품이 근거다. 고장 원인·고장 유형을 구매 근거로 대신하지 않는다. 승인 전에는 조회·계산·판단 카드 등록만 한다. 발주·메일·입고는 구매 담당의 승인 뒤 시스템이 한다.

## 절차
1. `context/task.json`의 입력에서 asset·pattern·alert.evidence(부품·가용·부족량·필요량)·incident·alert.alertId를 UTF-8로 읽는다.
2. enterprise-purchase `spare_stock(part)`에서 재주문점 아래인 실제 부품 번호와 필요량을 확인한다. part는 부품 번호이며 비우면 전체를 조회한다. 부품을 하나로 확정할 근거가 없으면 지어내지 않고 보류한다.
3. hyd-dmn `purchase_context(asset, part_no)`로 해당 부품에 적용되는 원문 구매 절차와 실행 여부를 확인한다. 참고 보관 절차를 실행 후보로 바꾸지 않는다.
4. enterprise-purchase `part_quotes(part)`로 해당 부품의 공급사별 단가·리드타임·불량률·AVL을 확인한다. `scm_suppliers`는 별도 등록 자료이므로 그 결과가 0건이라는 이유로 실제 견적을 없다고 판단하지 않는다.
5. hyd-dmn `evaluate_purchase(asset, part_no)`로 원문에 명시된 발주 대안의 금액·납기·AVL·불량 비용·규정·순위를 비교한다. 최단 납기 절차는 전체 견적에서 먼저 최단을 선택한 뒤 AVL을 확인하며, 미승인 공급사를 다른 공급사로 바꿔 적합하게 만들지 않는다.
   300만 원 초과는 전결 기준 초과 표시와 구매팀장 보고 대상이며 추가 승인이 아니다. 승인은 구매 담당 한 번이다.
6. hyd-dmn `submit_purchase(asset, part_no, incident, alert_id, process_scope)`로 승인 대기 판단을 등록한다. 이 작업의 process_scope를 그대로 전달한다. 반환 status가 SUBMITTED인지 확인하고 그 판단 id를 decision_id로 낸다. 평가 실행 id나 과거 판단을 제출하지 않는다.

## 결과
공통 결과 폼의 cause·failure_mode·guide_card는 빈 값으로 두고, decision{recommended, explanation, order}·decision_id를 실제 구매 판단으로 채운다. 빈 고장 필드는 구매 업무의 근거가 없다는 뜻이며 고장 ID를 생성하라는 뜻이 아니다.
explanation은 한국어 두세 문장으로 추천 공급사·수량·금액과 근거, 지는 공급사의 이유(AVL·납기·불량)를 적는다. 실제 원천이나 후보가 부족하면 폼을 억지로 채우지 않고 근거와 함께 보류한다.
$seed$, updated_at = now()
 where skill_name = 'spare-purchase-planning' and origin = 'seed'
   and content = $old$# 예비품 구매 (시나리오 C)

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
$old$;

-- ---------------------------------------------------------------- 4. 업무 거래 함수 한 벌
-- 거래 계약 한 곳: 스킬 → 시스템 · 종류(원거래 forward / 되돌리기 inverse) · 되돌리기 스킬 · 되돌릴 수 없는 까닭. exec_skill · exec_compensation 이
-- 이것으로 받을 거래를 정하고, enterprise-sim 의 거래 기록(/api/transactions)이 거래마다 inverse · irreversible_reason 으로 싣는다 —
-- process 는 자기 표 없이 이 칸을 읽는다(검진 G2-05 · P4-09: entsim · process · DB 세 벌이 어긋났다).
create or replace view ent.skill_contracts as
select * from (values
  ('skill:schedule-maintenance',        'sys:cmms', 'forward', 'skill:cancel-work-order',         null),
  ('skill:schedule-maintenance-scoped', 'sys:cmms', 'forward', 'skill:cancel-maintenance-scoped', null),
  ('skill:procure-part',                'sys:erp',  'forward', 'skill:cancel-purchase-request',   null),
  ('skill:reschedule-maintenance',      'sys:cmms', 'forward', null, '정비 일정은 기존 오더 상태와 기한을 다시 검토한 새 일정 변경으로 정정한다'),
  ('skill:complete-maintenance',        'sys:cmms', 'forward', null, '정비는 현장에서 이미 수행되어 되돌릴 수 없다'),
  ('skill:pm-reset',                    'sys:cmms', 'forward', null, '정기 정비가 끝나 다음 주기가 시작됐다(정정은 새 기록으로)'),
  ('skill:receive-goods',               'sys:erp',  'forward', null, '입고 · 검수는 실물이 창고에 들어와 되돌릴 수 없다(반품은 별도 절차)'),
  ('skill:delay-delivery',              'sys:scm',  'forward', null, '공급사가 알린 납기 변경이라 되돌리지 않는다'),
  ('skill:cancel-work-order',           'sys:cmms', 'inverse', null, null),
  ('skill:cancel-purchase-request',     'sys:erp',  'inverse', null, null),
  ('skill:cancel-maintenance-scoped',   'sys:cmms', 'inverse', null, null)
) c(skill, system, kind, inverse, irreversible_reason);
comment on view ent.skill_contracts is '업무 거래 계약: 거래 스킬 → 시스템 · 원거래/되돌리기 · 되돌리기 스킬 · 되돌릴 수 없는 까닭';
grant select on ent.skill_contracts to service_role, hyd_enterprise_reader;

-- 입고 시간 근거(검진 H-11): 수업 흐름은 리드타임을 기다리지 않거나 줄여 입고한다 — 그 근거 글을 입고 · 발주 기록에 남긴다(process 가 만든다)
alter table ent.goods_receipts add column if not exists basis text;
alter table ent.purchase_requests add column if not exists receipt_basis text;
comment on column ent.goods_receipts.basis is '입고 시각의 근거(수업 시스템이 리드타임을 줄여 입고했을 때 그 까닭). 없으면 업무 시각 그대로';
comment on column ent.purchase_requests.receipt_basis is '입고 시각의 근거(goods_receipts.basis 와 같은 글)';
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

  elsif v_skill = 'skill:receive-goods' then              -- 발주 한 건의 입고 · 검수 (공급사 납품 모사 포함)
    if length(v_params->>'basis') > 300 then
      raise exception '입고 시간 근거(basis)는 300자까지입니다' using errcode = '22023';
    end if;
    if v_params ? 'inspection' and v_params->>'inspection' is distinct from '합격' then
      raise exception '검수 불합격 입고는 이 업무 시스템이 처리하지 않습니다(반품은 별도 절차)' using errcode = '22023';
    end if;
    select * into v_pr from ent.purchase_requests where id = v_params->>'ref' for update;
    if not found then raise exception '없는 발주입니다: %', v_params->>'ref' using errcode = '22023'; end if;
    if v_pr.qty is null then raise exception '발주 %에는 입고할 수량이 없습니다', v_pr.id using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then
      raise exception '발주 %는 지금 상태(%)에서 입고할 수 없습니다', v_pr.id, v_pr.status using errcode = '22023';
    end if;
    v_before := to_jsonb(v_pr);
    v_ref := ent.new_ref('GR');
    v_lot := coalesce(v_params->>'lot', 'LOT-' || to_char(now(), 'YYMMDD') || '-' || upper(substr(md5(random()::text), 1, 3)));
    insert into ent.goods_receipts (id, pr_id, part_no, qty, lot, inspection, decision_id, basis)
    values (v_ref, v_pr.id, v_pr.part_no, v_pr.qty, v_lot, '합격', v_decision, nullif(v_params->>'basis', ''));
    update ent.purchase_requests set status = '입고 완료', received_at = now(), receipt_basis = nullif(v_params->>'basis', '') where id = v_pr.id;
    update ent.spare_stock set on_hand = on_hand + v_pr.qty, on_order = greatest(on_order - v_pr.qty, 0) where part_no = v_pr.part_no
      returning * into v_stock;
    if v_stock.part_no is not null then
      perform ent.refresh_spare_flag(v_pr.part_no);
      insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
      values (v_pr.part_no, 'RECEIPT', v_pr.qty, v_asset, v_ref, p->>'by', format('발주 %s 입고', v_pr.id), v_stock.on_hand,
              v_stock.on_hand - v_stock.reserved + v_stock.on_order);
    end if;
    v_detail := format('%s %s개 입고 · 검수 합격 (발주 %s, 로트 %s)', v_pr.part, v_pr.qty, v_pr.id, v_lot)
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

create or replace function ent.exec_compensation(p jsonb) returns jsonb
language plpgsql
as $$
declare
  v_skill text := p->>'skill';
  v_ref text := p->'params'->>'ref';
  v_decision text := p->>'decision';
  v_compensates text := p->>'compensates';
  v_fp text := md5(jsonb_build_object('decision', p->'decision', 'option', p->'option', 'skill', p->'skill', 'asset', p->'asset', 'params', p->'params')::text);
  v_forward_skill text;
  v_prior ent.transactions; v_row ent.transactions; v_forward ent.transactions;
  v_system text; v_detail text; v_asset text; v_before jsonb; v_after jsonb;
  v_wo ent.work_orders; v_pr ent.purchase_requests; v_stock ent.spare_stock;
  v_order ent.work_orders; v_counter ent.pm_counters; v_group text; v_part record;
begin
  -- 되돌리기 계약(ent.skill_contracts): 이 되돌리기 스킬이 되돌리는 원거래 스킬. 다른 거래는 되돌리기가 없다(실물 · 외부가 움직였거나 새 기록으로 바로잡는다)
  select c.system, f.skill into v_system, v_forward_skill
    from ent.skill_contracts c join ent.skill_contracts f on f.inverse = c.skill
   where c.skill = v_skill and c.kind = 'inverse';
  if v_system is null then
    raise exception '되돌리기 거래가 아닙니다: %', coalesce(v_skill, '스킬 없음') using errcode = '22023';
  end if;
  if coalesce(v_ref, '') = '' then
    raise exception '%에는 되돌릴 기록 번호(params.ref)가 필요합니다', v_skill using errcode = '22023';
  end if;
  if coalesce(v_compensates, '') = '' then
    raise exception '%에는 되돌릴 원거래 id(compensates)가 필요합니다', v_skill using errcode = '22023';
  end if;
  if p->>'asset' is not null and not exists (select 1 from ent.assets where code = p->>'asset') then
    raise exception '등록되지 않은 설비입니다: %', p->>'asset' using errcode = '22023';
  end if;
  select * into v_forward from ent.transactions where id = v_compensates and compensates is null;
  if not found or v_forward.ref is distinct from v_ref or v_forward.skill is distinct from v_forward_skill then
    raise exception '원거래 %는 기록 %의 %가 아니라 %로 되돌릴 수 없습니다', v_compensates, v_ref, v_forward_skill, v_skill using errcode = '22023';
  end if;

  if v_skill = 'skill:cancel-maintenance-scoped' then          -- 원문 정비 범위 전체 취소 (056)
    if coalesce(v_decision, '') = '' or coalesce(p->>'by', '') = '' then
      raise exception '원문 정비 범위 취소에는 검토한 판단과 승인자가 필요합니다' using errcode = '22023';
    end if;
    perform pg_advisory_xact_lock(hashtextextended('ent.pm_scope.cancel:' || v_ref, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and ref = v_ref and compensates is not null;
    if found then
      if v_prior.fingerprint is distinct from v_fp then
        raise exception '같은 판단의 같은 되돌리기가 다른 입력으로 이미 실행됐습니다(멱등 충돌)' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
    select scope_group into v_group from ent.work_orders where id = v_ref;
    if v_group is null then raise exception '원문 정비 범위의 오더 묶음을 찾을 수 없습니다: %', v_ref using errcode = '22023'; end if;
    if v_forward.after->'plan'->>'stock_effect' = 'issue' then
      raise exception '실제로 출고한 부품은 반납 확인 뒤에만 전체를 되돌립니다' using errcode = '22023';
    end if;
    perform 1 from ent.pm_counters c where c.asset in (select asset from ent.work_orders where scope_group = v_group) order by c.asset for update;
    perform 1 from ent.work_orders w where scope_group = v_group order by w.asset for update;
    perform 1 from ent.spare_stock s where s.part_no in (select part_no from ent.pm_part_reservations
       where work_order in (select id from ent.work_orders where scope_group = v_group)) order by s.part_no for update;
    if (select count(*) from ent.work_orders where scope_group = v_group) <> jsonb_array_length(v_forward.after->'orders') then
      raise exception '원문 정비 범위의 오더 묶음이 등록 때와 다릅니다' using errcode = '22023';
    end if;
    for v_order in select * from ent.work_orders where scope_group = v_group order by asset loop
      select * into v_counter from ent.pm_counters where asset = v_order.asset;
      if v_order.status <> '배정됨' or v_counter.plan_wo is distinct from v_order.id
         or not exists (select 1 from jsonb_array_elements(v_forward.after->'plan'->'assets') x
                         where x->>'asset' = v_order.asset and (x->'expected_counter'->>'cycle')::integer = v_counter.cycle)
         or not exists (select 1 from jsonb_array_elements(v_forward.after->'orders') x where x = to_jsonb(v_order) || jsonb_build_object('ref', v_order.id))
         or exists (select 1 from ent.pm_part_reservations where work_order = v_order.id and released_at is not null)
         or (select count(*) from ent.pm_part_reservations where work_order = v_order.id) is distinct from
            (select jsonb_array_length(x->'parts') from jsonb_array_elements(v_forward.after->'plan'->'assets') x where x->>'asset' = v_order.asset)
         or exists (select 1 from jsonb_array_elements(v_forward.after->'plan'->'assets') x,
                    lateral jsonb_array_elements(x->'parts') required where x->>'asset' = v_order.asset and not exists
                    (select 1 from ent.pm_part_reservations r where r.work_order = v_order.id and r.part_no = required->>'part_no'
                      and r.qty = (required->>'qty')::numeric and r.released_at is null)) then
        raise exception '범위 안 설비 %의 오더가 진행돼 전체 취소를 다시 검토해야 합니다', v_order.asset using errcode = '22023';
      end if;
    end loop;
    select jsonb_build_object('plan', v_forward.after->'plan', 'orders', jsonb_agg(to_jsonb(w) || jsonb_build_object('ref', w.id) order by w.asset)) into v_before
      from ent.work_orders w where scope_group = v_group;
    for v_part in select r.part_no, sum(r.qty) qty from ent.pm_part_reservations r join ent.work_orders w on w.id = r.work_order
       where w.scope_group = v_group and r.released_at is null group by r.part_no loop
      if not exists (select 1 from ent.spare_stock where part_no = v_part.part_no and reserved >= v_part.qty) then
        raise exception '%의 실제 예약 수량이 등록 때와 달라 전체 취소를 다시 검토해야 합니다', v_part.part_no using errcode = '22023';
      end if;
      update ent.spare_stock set reserved = reserved - v_part.qty, updated_at = now() where part_no = v_part.part_no;
      perform ent.refresh_spare_flag(v_part.part_no);
    end loop;
    update ent.work_orders set status = '취소', cancelled_at = now() where scope_group = v_group;
    update ent.pm_part_reservations set released_at = now() where work_order in (select id from ent.work_orders where scope_group = v_group);
    update ent.pm_counters set plan_wo = null, plan_window = null, planned_at = null, updated_at = now()
     where plan_wo in (select id from ent.work_orders where scope_group = v_group);
    select jsonb_build_object('plan', v_forward.after->'plan', 'orders', jsonb_agg(to_jsonb(w) || jsonb_build_object('ref', w.id) order by w.asset)) into v_after
      from ent.work_orders w where scope_group = v_group;
    insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, compensates, before, after)
    values (ent.new_ref('TX'), v_system, v_skill, v_ref,
            '원문 정비 범위 ' || (select string_agg(x->>'asset', ', ' order by x->>'asset') from jsonb_array_elements(v_forward.after->'plan'->'assets') x) || ' 오더 전체 취소',
            p->>'asset', v_decision, p->>'option', p->>'by', v_fp, v_forward.id, v_before, v_after)
    returning * into v_row;
    return ent.tx_response(v_row);
  end if;

  if v_skill = 'skill:cancel-work-order' and exists (select 1 from ent.work_orders where id = v_ref and scope_group is not null) then
    raise exception '원문 정비 범위 오더는 묶음 전체로만 취소합니다(skill:cancel-maintenance-scoped)' using errcode = '22023';
  end if;
  if v_decision is not null then
    perform pg_advisory_xact_lock(hashtextextended('ent.exec_compensation:' || v_decision || ':' || v_skill || ':' || v_ref, 0));
    select * into v_prior from ent.transactions where decision_id = v_decision and skill = v_skill and ref = v_ref and compensates is not null;
    if found then
      if v_prior.fingerprint <> v_fp then
        raise exception '같은 판단의 같은 되돌리기가 다른 입력으로 이미 실행됐습니다(멱등 충돌)' using errcode = '23505';
      end if;
      return ent.tx_response(v_prior);
    end if;
  end if;

  if v_skill = 'skill:cancel-work-order' then
    -- 잠금 순서: 계수기 → 작업지시 (원문 범위 전체 취소 · B [초기화]와 같은 순서)
    perform 1 from ent.pm_counters where plan_wo = v_ref order by asset for update;
    select * into v_wo from ent.work_orders where id = v_ref for update;
    if not found then raise exception '없는 작업지시입니다: %', v_ref using errcode = '22023'; end if;
    if v_wo.status <> '배정됨' then
      raise exception '작업지시 %는 지금 상태(%)에서 취소할 수 없습니다', v_ref, v_wo.status using errcode = '22023';
    end if;
    v_before := to_jsonb(v_wo);
    update ent.work_orders set status = '취소', cancelled_at = now() where id = v_ref;
    -- 이 오더가 '이번 회차 정기 정비 오더'(trigger ent.mark_pm_plan)였으면 표시를 지운다 — 남기면 정기 정비 도래 경보가 꺼진 채 B가 거절됐다
    update ent.pm_counters set plan_wo = null, plan_window = null, planned_at = null, updated_at = now() where plan_wo = v_ref;
    select to_jsonb(w) into v_after from ent.work_orders w where w.id = v_ref;
    v_asset := v_wo.asset; v_detail := format('%s 작업지시 %s 취소 (%s)', v_wo.asset, v_ref, v_wo.task);
  else                                                         -- skill:cancel-purchase-request
    select * into v_pr from ent.purchase_requests where id = v_ref for update;
    if not found then raise exception '없는 구매요청입니다: %', v_ref using errcode = '22023'; end if;
    if v_pr.status <> '승인됨 → 발주' then
      raise exception '구매요청 %는 지금 상태(%)에서 취소할 수 없습니다', v_ref, v_pr.status using errcode = '22023';
    end if;
    v_before := to_jsonb(v_pr);
    update ent.purchase_requests set status = '취소', cancelled_at = now() where id = v_ref;
    -- 수량 발주면 재고의 입고 예정을 되돌린다 — 남기면 취소한 발주가 가용을 부풀려 '재고 보충 필요'가 꺼진 채였다
    if v_pr.qty is not null and v_pr.part_no is not null then
      select * into v_stock from ent.spare_stock where part_no = v_pr.part_no for update;
      if found then
        if v_stock.on_order < v_pr.qty then
          raise exception '%의 입고 예정 %개가 구매요청 %의 %개보다 적어 되돌릴 수 없습니다', v_pr.part_no, v_stock.on_order, v_ref, v_pr.qty
            using errcode = '22023';
        end if;
        update ent.spare_stock set on_order = on_order - v_pr.qty, updated_at = now() where part_no = v_pr.part_no returning * into v_stock;
        perform ent.refresh_spare_flag(v_pr.part_no);
        insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
        values (v_pr.part_no, 'CANCEL', v_pr.qty, v_pr.asset, v_ref, p->>'by', format('발주 %s 취소', v_ref), v_stock.on_hand,
                v_stock.on_hand - v_stock.reserved + v_stock.on_order);
      end if;
    end if;
    select to_jsonb(r) into v_after from ent.purchase_requests r where r.id = v_ref;
    v_asset := v_pr.asset; v_detail := format('구매요청 %s 취소 (%s — %s)', v_ref, v_pr.part, v_pr.supplier_name);
  end if;

  insert into ent.transactions (id, system, skill, ref, detail, asset, decision_id, option_id, requested_by, fingerprint, compensates, before, after)
  values (ent.new_ref('TX'), v_system, v_skill, v_ref, v_detail, coalesce(p->>'asset', v_asset), v_decision, p->>'option', p->>'by', v_fp,
          v_compensates, v_before, v_after)
  returning * into v_row;
  return ent.tx_response(v_row);
end $$;

drop function if exists ent.exec_skill_before_pm56(jsonb);
drop function if exists ent.exec_skill_before_pm54(jsonb);
drop function if exists ent.exec_compensation_before_pm56(jsonb);
revoke execute on function ent.exec_skill(jsonb), ent.exec_compensation(jsonb) from public, anon, authenticated;
grant execute on function ent.exec_skill(jsonb), ent.exec_compensation(jsonb) to service_role;
comment on function ent.exec_skill(jsonb) is
  '사람이 승인한 업무 거래 하나(CMMS 작업지시 · 일정 변경 · 원문 범위 오더 · 완료 · 계수기 리셋, ERP 구매요청 · 입고, SCM 납기 지연). 결정 · 스킬마다 한 번(같은 입력은 같은 결과)';
comment on function ent.exec_compensation(jsonb) is
  '되돌리기 거래 하나(작업지시 취소 · 구매요청 취소 · 원문 정비 범위 전체 취소). 원거래 id(compensates)와 그 기록 번호(params.ref)가 맞아야 한다';

-- ---------------------------------------------------------------- 4b. 원문 정비 범위 검사 · B · C 초기화의 거절 문장(056 · 060 본문 그대로, 문장만 한국어)
-- pm_scope_check: 같은 본문, 거절 문장만 한국어(23개)
CREATE OR REPLACE FUNCTION ent.pm_scope_check(p_plan jsonb, p_asset text, p_create boolean)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
declare
  v_member jsonb;v_policy jsonb:=p_plan->'policy';v_contract_package jsonb;v_part jsonb;v_total jsonb;
  v_pm ent.pm_counters;v_stock ent.spare_stock;v_row jsonb;v_expected jsonb;
  v_interval numeric;v_tolerance numeric;v_previous numeric;v_position integer;v_period numeric;v_hours numeric;
  v_needed jsonb:='{}'::jsonb;v_crew numeric;v_prefix text;v_count integer;v_code text;v_peer text;v_peers text[];
begin
  if jsonb_typeof(p_plan) is distinct from 'object' or jsonb_typeof(v_policy) is distinct from 'object'
     or coalesce(p_plan->>'source_id','')='' or v_policy->'anchor'->>'source_id' is distinct from p_plan->>'source_id'
     or v_policy->'model_anchor'->>'source_id' is distinct from p_plan->>'source_id'
     or v_policy->>'scope' is distinct from p_plan->>'scope' then
    raise exception '승인한 정비 계획에 검토된 원문 정비 규정이 없습니다' using errcode='22023';
  end if;
  if p_plan->>'stock_effect' is distinct from v_policy->>'stock_effect'
     or (p_create and p_plan->>'stock_effect' not in ('reserve','issue'))
     or (not p_create and p_plan->>'stock_effect' is distinct from 'preserve') then
    raise exception '정비 계획에 부품을 예약할지 · 출고할지가 적혀 있지 않습니다' using errcode='22023';end if;
  v_interval:=(v_policy->>'interval_h')::numeric;v_tolerance:=(v_policy->>'tolerance_pct')::numeric;
  if v_interval<=0 or v_tolerance<0 or v_tolerance>=100 then raise exception '정비 계획의 정기 정비 주기 · 허용 오차 값이 올바르지 않습니다' using errcode='22023'; end if;
  v_count:=jsonb_array_length(p_plan->'assets');
  if v_count <> (case when p_plan->>'scope'='bundle' then 2 else 1 end)
     or (select count(distinct x->>'asset') from jsonb_array_elements(p_plan->'assets') x)<>v_count
     or p_plan->'assets'->0->>'asset' is distinct from p_asset then
    raise exception '정비 범위는 실제 설비 한 대 또는 두 대여야 합니다' using errcode='22023';
  end if;
  if (select count(*) from ent.assets a where (v_policy->'model_assets') ? a.code)<>jsonb_array_length(v_policy->'model_assets') then
    raise exception '정비 계획의 같은 기종 설비 목록이 실제 설비와 다릅니다' using errcode='22023';
  end if;
  -- Stable global lock order. Every verification completes before any write.
  perform 1 from ent.pm_counters c where c.asset in(select x->>'asset' from jsonb_array_elements(p_plan->'assets') x) order by c.asset for update;
  perform 1 from ent.spare_stock s where s.part_no in(select x->>'part_no' from jsonb_array_elements(p_plan->'parts_totals') x) order by s.part_no for update;
  if v_count=2 then
    select array_agg(v.asset order by v.asset) into v_peers from ent.pm_status v
      where v.asset<>p_asset and (v_policy->'model_assets') ? v.asset
        and v.pm_since_h>=v_interval*(1-v_tolerance/100)
        and v.night_window_at=(p_plan->'window'->>'starts_at')::timestamptz;
    if array_length(v_peers,1) is distinct from 1 then
      raise exception '함께 정비할 같은 기종 설비가 없거나 하나로 정해지지 않습니다' using errcode='22023';end if;
    v_peer:=v_peers[1];
  end if;
  for v_member in select x from jsonb_array_elements(p_plan->'assets') x loop
    v_code:=v_member->>'asset';
    if not (v_policy->'model_assets') ? v_code or (v_code<>p_asset and v_code is distinct from v_peer) then
      raise exception '함께 정비할 설비가 같은 기종의 정비 대상이 아닙니다' using errcode='22023';
    end if;
    select * into v_pm from ent.pm_counters where asset=v_code;
    if not found then raise exception '설비의 운전시간 계수기가 없습니다' using errcode='22023'; end if;
    v_row:=ent.pm_scope_row(v_code);
    v_expected:=jsonb_build_object('cycle',v_pm.cycle,'pm_since_h',v_pm.since_pm_h,'pm_total_h',v_pm.total_h,
      'pm_planned_wo',v_pm.plan_wo,'service_position',v_pm.service_position);
    if v_expected is distinct from v_member->'expected_counter' or (p_create and v_pm.plan_wo is not null)
       or (v_row->>'pm_interval_h')::numeric is distinct from v_interval
       or (v_row->>'pm_tolerance_pct')::numeric is distinct from v_tolerance
       or v_pm.since_pm_h<v_interval*(1-v_tolerance/100) then
      raise exception '승인한 뒤 정비 범위 · 운전시간 · 규정이 바뀌었거나 묶음 설비가 아직 허용 하한에 이르지 않았습니다 — 다시 판단하세요' using errcode='22023';
    end if;
    if coalesce((p_plan->'window'->>'immediate')::boolean,false) then
      if v_count<>1 then raise exception '두 대 묶음 정비에는 함께 쓰는 예정된 정비 시간이 하나 있어야 합니다' using errcode='22023'; end if;
      v_hours:=v_pm.since_pm_h;
    else
      v_prefix:=case when p_plan->'window'->>'basis'='hours_at_following_window' then 'following' else 'night' end;
      if coalesce(v_member->'window'->>'id','')='' or v_member->'window'->>'id' is distinct from v_row->>(v_prefix||'_window_id')
         or (v_member->'window'->>'starts_at')::timestamptz is distinct from (v_row->>(v_prefix||'_window_at'))::timestamptz
         or (p_plan->'window'->>'starts_at')::timestamptz is distinct from (v_row->>(v_prefix||'_window_at'))::timestamptz then
        raise exception '함께 쓰려던 예정된 정비 시간이 바뀌었거나 없습니다 — 다시 판단하세요' using errcode='22023';
      end if;
      v_hours:=(v_row->>(case when v_prefix='following' then 'hours_at_following_window' else 'hours_at_next_window' end))::numeric;
    end if;
    if v_hours is null or v_hours>v_interval*(1+v_tolerance/100) then
      raise exception '정비 시점의 운전시간이 정기 정비 허용 한계를 넘습니다' using errcode='22023';
    end if;
    v_previous:=v_pm.total_h-v_pm.since_pm_h;
    if v_previous<0 then raise exception '누적 운전시간과 정비 뒤 운전시간이 서로 맞지 않습니다' using errcode='22023'; end if;
    if v_pm.service_position is not null then v_position:=v_pm.service_position+1;
    elsif mod(v_previous,v_interval)=0 then v_position:=(v_previous/v_interval)::integer+1;
    else raise exception '지난 정비 차례(몇 번째 정비인지)를 확인할 수 없습니다' using errcode='22023'; end if;
    select x into v_contract_package from jsonb_array_elements(v_policy->'packages') x
      where mod(v_position::numeric,(x->>'interval_h')::numeric/v_interval)=0 order by (x->>'interval_h')::numeric desc limit 1;
    v_period:=(v_contract_package->>'interval_h')::numeric;
    if v_period is null or (v_member->'service'->>'service_position')::integer is distinct from v_position
       or (v_member->'service'->>'next_due_total_h')::numeric is distinct from v_previous+v_interval
       or (v_member->'service'->>'package_interval_h')::numeric is distinct from v_period
       or v_member->'service'->>'package_sop' is distinct from v_contract_package->>'sop'
       or jsonb_array_length(v_member->'parts')<>jsonb_array_length(v_contract_package->'parts') then
      raise exception '이번 정비 차례 · 정비 패키지가 원문 규정과 다릅니다' using errcode='22023';
    end if;
    if v_member->'service' is distinct from jsonb_build_object('interval_h',v_interval,'since_pm_h',v_pm.since_pm_h,
       'total_h',v_pm.total_h,'last_service_total_h',v_previous,'next_due_total_h',v_previous+v_interval,
       'service_position',v_position,'package_interval_h',v_period,'package_sop',v_contract_package->>'sop',
       'package_name',v_contract_package->>'name') then
      raise exception '정비 패키지 이름과 원문 근거가 서로 다릅니다' using errcode='22023';end if;
    for v_part in select x from jsonb_array_elements(v_contract_package->'parts') x loop
      select * into v_stock from ent.spare_stock where part_no=v_part->>'part_no';
      if not found or v_part->>'qty' is null or (v_part->>'qty')::numeric<=0 then
        raise exception '정비 패키지 부품 수량 또는 실제 재고를 확인할 수 없습니다' using errcode='22023';
      end if;
      if not exists(select 1 from jsonb_array_elements(v_member->'parts') x where x->>'part_no'=v_stock.part_no
         and (x->>'qty')::numeric=(v_part->>'qty')::numeric and (x->>'available')::numeric=v_stock.on_hand-v_stock.reserved+v_stock.on_order
         and x->'verified'='true'::jsonb) then
        raise exception '승인한 뒤 정비 패키지 부품 근거가 바뀌었습니다 — 다시 판단하세요' using errcode='22023';
      end if;
      if p_plan->>'stock_effect'='preserve' and not exists(select 1 from ent.pm_part_reservations r
         where r.work_order=v_pm.plan_wo and r.part_no=v_stock.part_no and r.qty>=(v_part->>'qty')::numeric
           and r.released_at is null and r.stock_effect='reserve'
           and exists(select 1 from jsonb_array_elements(v_member->'parts') x
             where x->>'part_no'=r.part_no and (x->>'owned_qty')::numeric=r.qty)) then
        raise exception '기존 정기 정비 오더가 잡은 부품 예약을 찾을 수 없습니다' using errcode='22023';end if;
      v_needed:=jsonb_set(v_needed,array[v_stock.part_no],to_jsonb(coalesce((v_needed->>v_stock.part_no)::numeric,0)+(v_part->>'qty')::numeric));
    end loop;
    v_crew:=least(v_crew,(v_row->>'pm_crew_available')::numeric);
    if v_row->>'pm_crew_available' is null then raise exception '정비 시간의 정비 인원을 확인할 수 없습니다' using errcode='22023'; end if;
  end loop;
  if (select count(*) from jsonb_object_keys(v_needed))<>jsonb_array_length(p_plan->'parts_totals') then
    raise exception '정비 범위 전체의 부품 합계가 설비별 부품과 맞지 않습니다' using errcode='22023';
  end if;
  for v_total in select x from jsonb_array_elements(p_plan->'parts_totals') x loop
    select * into v_stock from ent.spare_stock where part_no=v_total->>'part_no';
    if not found or (v_total->>'qty')::numeric is distinct from (v_needed->>v_stock.part_no)::numeric
       or (v_total->>'available')::numeric is distinct from v_stock.on_hand-v_stock.reserved+v_stock.on_order
       or (p_plan->>'stock_effect'='reserve' and v_stock.on_hand-v_stock.reserved+v_stock.on_order<(v_total->>'qty')::numeric)
       or (p_plan->>'stock_effect'='issue' and v_stock.on_hand-v_stock.reserved<(v_total->>'qty')::numeric) then
      raise exception '정비 범위 전체에 필요한 부품의 실제 가용 재고가 모자랍니다' using errcode='22023';
    end if;
  end loop;
  if (p_plan->'staffing'->>'available')::numeric is distinct from v_crew or p_plan->'staffing'->'confirmed' is distinct from 'false'::jsonb
     or (v_count=2 and ((p_plan->'staffing'->>'required')::numeric is distinct from 4
       or (p_plan->'staffing'->>'shortfall')::numeric is distinct from greatest(4-v_crew,0)
       or (p_plan->'staffing'->>'arrangement_required')::boolean is distinct from (v_crew<4))) then
    raise exception '정비 인원 요구(두 대 묶음 4명) 또는 부족 인원 표시가 실제와 다릅니다' using errcode='22023';
  end if;
end $function$;

-- reset_spare_stock: 같은 본문, 거절 문장만 한국어(1개)
CREATE OR REPLACE FUNCTION ent.reset_spare_stock(p_part text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
declare r ent.spare_stock; v_pr record; v_held_reserved integer; v_held_issued integer; v_open integer; v_closed jsonb; v_x jsonb; v_after ent.spare_stock;
begin
  perform 1 from ent.purchase_requests where status = '승인됨 → 발주' and qty is not null and part_no is not null
     and (p_part is null or part_no = p_part) order by id for update;
  for r in select * from ent.spare_stock where p_part is null or part_no = p_part order by part_no for update loop
    select coalesce(sum(x.qty) filter (where x.stock_effect = 'reserve'), 0)::integer, coalesce(sum(x.qty) filter (where x.stock_effect = 'issue'), 0)::integer
      into v_held_reserved, v_held_issued
      from ent.pm_part_reservations x join ent.work_orders w on w.id = x.work_order
     where x.part_no = r.part_no and x.released_at is null and w.status = '배정됨';
    if r.base_on_hand - v_held_issued < 0 then
      raise exception '%의 실물 %개가 진행 중인 정기 정비 오더에 출고돼 있습니다 — 시나리오 B를 먼저 초기화하세요', r.part_no, v_held_issued using errcode = '22023';
    end if;
    with closed as (
      update ent.purchase_requests set status = '취소', cancelled_at = now()
       where part_no = r.part_no and status = '승인됨 → 발주' and qty is not null
      returning id, qty, asset)
    select coalesce(jsonb_agg(jsonb_build_object('id', id, 'qty', qty, 'asset', asset) order by id), '[]'::jsonb) into v_closed from closed;
    select coalesce(sum(qty), 0)::integer into v_open from ent.purchase_requests
     where part_no = r.part_no and status = '승인됨 → 발주' and qty is not null;
    update ent.spare_stock set on_hand = base_on_hand - v_held_issued, reserved = base_reserved + v_held_reserved, on_order = v_open,
           below_since = null, updated_at = now()
     where part_no = r.part_no;
    perform ent.refresh_spare_flag(r.part_no);
    select * into v_after from ent.spare_stock where part_no = r.part_no;
    for v_x in select x from jsonb_array_elements(v_closed) x loop
      insert into ent.stock_movements (part_no, kind, qty, asset, ref, by_whom, reason, on_hand_after, available_after)
      values (r.part_no, 'CANCEL', (v_x->>'qty')::integer, v_x->>'asset', v_x->>'id', 'instructor', format('수업 초기화 — 발주 %s 취소', v_x->>'id'),
              v_after.on_hand, v_after.on_hand - v_after.reserved + v_after.on_order);
    end loop;
    insert into ent.stock_movements (part_no, kind, qty, ref, by_whom, reason, on_hand_after, available_after)
    values (r.part_no, 'RESET', v_after.on_hand - r.on_hand, 'RESET', 'instructor', '수업 초기화', v_after.on_hand,
            v_after.on_hand - v_after.reserved + v_after.on_order);
  end loop;
  return ent.spare_stock_read(p_part);
end $function$;

-- reset_pm_counters: 같은 본문, 거절 문장만 한국어(2개)
CREATE OR REPLACE FUNCTION ent.reset_pm_counters(p_asset text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
declare r ent.pm_counters; v_rel jsonb; v_x jsonb; v_stock ent.spare_stock; v_qty integer;
begin
  perform 1 from ent.pm_counters where p_asset is null or asset = p_asset order by asset for update;
  with open_orders as (
    update ent.work_orders w set status = '취소', cancelled_at = now()
     where w.status = '배정됨' and (p_asset is null or w.asset = p_asset)
       and exists (select 1 from ent.pm_part_reservations x where x.work_order = w.id and x.released_at is null)
    returning w.id),
  released as (
    update ent.pm_part_reservations x set released_at = now()
     where x.released_at is null and x.work_order in (select id from open_orders)
    returning x.work_order, x.part_no, x.qty, x.stock_effect)
  select coalesce(jsonb_agg(jsonb_build_object('part_no', part_no, 'stock_effect', stock_effect, 'qty', qty, 'orders', orders)
                            order by part_no, stock_effect), '[]'::jsonb)
    into v_rel
    from (select part_no, stock_effect, sum(qty) qty, string_agg(work_order, ', ' order by work_order) orders
            from released group by part_no, stock_effect) g;
  for v_x in select x from jsonb_array_elements(v_rel) x loop
    v_qty := (v_x->>'qty')::numeric::integer;
    select * into v_stock from ent.spare_stock where part_no = v_x->>'part_no' for update;
    if not found then
      raise exception '%는 관리 예비품이 아닙니다', v_x->>'part_no' using errcode = '22023';
    end if;
    if v_x->>'stock_effect' = 'reserve' then
      if v_stock.reserved < v_qty then
        raise exception '%의 예약 %개가 진행 중인 정기 정비 오더가 잡은 %개보다 적습니다 — 재고 원장을 확인해야 합니다',
          v_stock.part_no, v_stock.reserved, v_qty using errcode = '22023';
      end if;
      update ent.spare_stock set reserved = reserved - v_qty, updated_at = now() where part_no = v_stock.part_no;
    else
      update ent.spare_stock set on_hand = on_hand + v_qty, updated_at = now() where part_no = v_stock.part_no;
    end if;
    perform ent.refresh_spare_flag(v_stock.part_no);
    select * into v_stock from ent.spare_stock where part_no = v_stock.part_no;
    insert into ent.stock_movements (part_no, kind, qty, ref, by_whom, reason, on_hand_after, available_after)
    values (v_stock.part_no, 'RESET', case when v_x->>'stock_effect' = 'issue' then v_qty else 0 end, 'RESET', 'instructor',
            format('수업 초기화 — 정비 오더 %s %s', v_x->>'orders', case when v_x->>'stock_effect' = 'issue' then '출고 반납' else '예약 해제' end),
            v_stock.on_hand, v_stock.on_hand - v_stock.reserved + v_stock.on_order);
  end loop;
  for r in select * from ent.pm_counters where p_asset is null or asset = p_asset order by asset loop
    update ent.pm_counters set since_pm_h = base_since_pm_h, total_h = base_total_h, cycle = 1, last_done_at = null, due_since = null,
           plan_wo = null, plan_window = null, planned_at = null, updated_at = now() where asset = r.asset;
    perform ent.refresh_pm_flag(r.asset);
    insert into ent.pm_counter_log (asset, kind, delta_h, since_after, total_after, cycle, ref, by_whom, reason)
    values (r.asset, 'BASE', r.base_since_pm_h - r.since_pm_h, r.base_since_pm_h, r.base_total_h, 1, 'RESET', 'instructor', '수업 초기화');
  end loop;
  return ent.pm_status_read(p_asset);
end $function$;

-- ---------------------------------------------------------------- 5. 부르는 곳 없는 업무 전체 초기화 · 보관
drop function if exists ent.reset_executions();
drop function if exists ent.execution_archive_read(text);
drop table if exists ent.execution_archive;

-- ---------------------------------------------------------------- 6. CMMS 정비 이력
create or replace function ent.cmms_history(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'CMMS',
    'facts', (select to_jsonb(m) - 'asset'
                     || jsonb_build_object(
                          'night_in_h', ent.hours_from_now((select min(w.starts_at) from ent.next_maintenance_windows(m.asset, 1) w where w.kind = 'N')),
                          'cleans_60d', (select count(*) from ent.maintenance_history h where h.asset = m.asset and h.task like '쿨러 핀 세척%' and h.performed_at > now() - interval '60 days'),
                          'last_clean_days', (select floor(extract(epoch from now() - max(h.performed_at)) / 86400)::int from ent.maintenance_history h where h.asset = m.asset and h.task like '쿨러 핀 세척%'))
                from ent.maintenance_profiles m where m.asset = p_asset),
    'records', coalesce((select jsonb_agg(jsonb_build_object('wo', h.wo, 'task', h.task, 'performed_at', h.performed_at,
                                                             'days_ago', floor(extract(epoch from now() - h.performed_at) / 86400)::int) order by h.performed_at desc)
                from (select * from ent.maintenance_history where asset = p_asset order by performed_at desc limit 20) h), '[]'::jsonb),
    'records_total', (select count(*) from ent.maintenance_history where asset = p_asset),
    'work_orders', coalesce((select jsonb_agg(to_jsonb(w) - 'maintenance_plan' order by w.created_at desc)
                from (select * from ent.work_orders where asset = p_asset order by created_at desc limit 20) w), '[]'::jsonb),
    'work_orders_total', (select count(*) from ent.work_orders where asset = p_asset),
    'note', '이력 · 작업지시는 최근 20건씩(전체 수는 records_total · work_orders_total). 원문 정비 계획은 pm_status 의 existing_pm_order 에 있다',
    'as_of', now())
$$;
grant execute on function ent.cmms_history(text) to anon, authenticated, service_role, hyd_enterprise_reader;

create or replace function ent.reanchor_scenario_times() returns void language plpgsql as $$
begin
  update ent.production_orders o set due_at = now() + make_interval(hours => s.due_h), alt_free_at = now() + make_interval(hours => s.alt_h)
    from (values ('MO-0930-0412', 6, 8), ('MO-0930-0415', 20, 4), ('MO-0930-0419', 3, 2)) s(order_id, due_h, alt_h)
   where o.order_id = s.order_id;
  update ent.fg_inventory i set ship_at = now() + make_interval(hours => s.h)
    from (values ('HYD-01', 2), ('HYD-02', 10), ('HYD-03', 3)) s(asset, h) where i.asset = s.asset;
  update ent.maintenance_history h set performed_at = now() - make_interval(days => s.d)
    from (values ('WO-HIST-01-1', 21), ('WO-HIST-01-2', 38), ('WO-HIST-01-3', 55), ('WO-HIST-02-1', 21), ('WO-HIST-03-P', 80)) s(wo, d)
   where h.wo = s.wo;
  -- 예정된 정비 시간 규칙의 첫 창 = 지금 + 9 h(야간) · + 105 h(주말) · + 280 h(월간). 「다음 야간 정비 시간」은 이 규칙 한 곳에서 나온다
  update ent.maintenance_window_rules set first_at = now() + make_interval(hours => case kind when 'N' then 9 when 'W' then 105 else 280 end);
end $$;
alter table ent.maintenance_profiles drop column if exists night_window_at;

-- ---------------------------------------------------------------- 7. 업무 표 설명(에이전트 describe_* · 학생 도구 써 보기에 그대로 보인다)
comment on column ent.maintenance_profiles.standby_ready is '예비 펌프로 바로 전환할 수 있는가(값이 없던 옛 행은 수업 기본값 true 로 채웠다)';
comment on column ent.transactions.before is '거래가 바꾼 기록의 실행 전 상태(바꾸는 거래만, 새로 만드는 거래는 비어 있음)';
comment on column ent.transactions.after is '거래가 만들거나 바꾼 기록의 실행 후 상태';
comment on table ent.spare_stock is 'ERP 중요 예비품 재고. 가용 = 실물(on_hand) - 예약(reserved) + 입고 예정(on_order). 가용이 재주문점(reorder_point)보다 작으면 재고 기준 이탈(SPARE_BELOW_MIN)';
comment on column ent.purchase_requests.amount is '발주 금액(만원) = 수량 × 단가. 승인한 판단이 정한 값';
comment on column ent.purchase_requests.expected_at is '입고 예정 시각(발주 시각 + 리드타임). 수업 시스템은 입고 대기를 줄여 몇 분 뒤 입고한다';
comment on view ent.pm_status is '설비별 정기 정비 상태(운전시간 · 주기 · 허용 오차 · 예정된 정비 시간까지 · 묶음 후보 · 부품 영향)';

-- ---------------------------------------------------------------- 8. 068 이 닫은 중복 처리 건의 승인 전달 대기
update public.process_approval_outbox o
   set status = 'DISCARDED', updated_at = now(),
       history = o.history || jsonb_build_array(jsonb_build_object(
         'status', 'DISCARDED', 'previous_status', o.status, 't', now(), 'by', 'migration 20261030000069', 'role', 'system',
         'reason', '같은 경보로 두 번 열린 처리 건을 닫아(마이그레이션 068) 이 승인은 전달하지 않습니다'))
 where o.status = 'PENDING'
   and exists (select 1 from public.bpm_proc_inst i where i.proc_inst_id = o.proc_inst_id and i.end_event = 'duplicate-closed');

-- ---------------------------------------------------------------- 9. CMMS 표준 작업(지금 SOP 번호)
-- 값의 출처: 옛 행(037)과 같은 작업 — 쿨러 핀 세척은 설비별 정비 기준(maintenance_profiles)을 그대로, 캐비닛 환기는 정지 없이 30만 원,
-- 팬 점검 · 벨트 교체는 정지 3 h · 50만 원 · 팬 베어링 1개(옛 SOP-FAN-04). 정기 정비 패키지(SOP-PM-*)는 정비 계획(pm_status · 원문 패키지)이
-- 정지 시간 · 부품을 정하므로 이 표에 두지 않는다(값을 지어내지 않는다).
insert into ent.task_standards (sop, name, from_profile, stop_h, labor_cost, part_no, part_qty) values
  ('SOP-COOL-14', '쿨러 핀 세척', true, null, null, null, 0),
  ('SOP-COOL-15', '캐비닛 환기 보강', false, 0, 30, null, 0),
  ('SOP-FAN-11', '쿨러 팬 점검 절차', false, 3, 50, 'P-FAN-BRG', 1),
  ('SOP-FAN-12', '벨트 교체 절차', false, 3, 50, 'P-FAN-BRG', 1)
on conflict (sop) do update set name = excluded.name, from_profile = excluded.from_profile, stop_h = excluded.stop_h,
  labor_cost = excluded.labor_cost, part_no = excluded.part_no, part_qty = excluded.part_qty;
delete from ent.task_standards where sop in ('SOP-COOL-04', 'SOP-COOL-05', 'SOP-PMP-04', 'SOP-FAN-04');

-- ---------------------------------------------------------------- 10. 쌓인 명령 응답 중복 접수 행
update public.process_source_state s set receipt_id = r.parent_id
  from public.process_source_inbox r where r.id = s.receipt_id and r.kind = 'ACK' and r.status = 'DUPLICATE';
delete from public.process_source_inbox where kind = 'ACK' and status = 'DUPLICATE';
create temp table hyd_ack_conflict_keep as
  select distinct on (tenant_id, event_key, semantic_sha) id, tenant_id, event_key, semantic_sha
    from public.process_source_inbox where kind = 'ACK' and status = 'CONFLICT' order by tenant_id, event_key, semantic_sha, id;
update public.process_source_state s set receipt_id = k.id
  from public.process_source_inbox r join hyd_ack_conflict_keep k using (tenant_id, event_key, semantic_sha)
 where r.id = s.receipt_id and r.kind = 'ACK' and r.status = 'CONFLICT' and r.id <> k.id;
delete from public.process_source_inbox r using hyd_ack_conflict_keep k
 where r.kind = 'ACK' and r.status = 'CONFLICT' and r.tenant_id = k.tenant_id and r.event_key = k.event_key
   and r.semantic_sha = k.semantic_sha and r.id <> k.id;
drop table hyd_ack_conflict_keep;

-- ---------------------------------------------------------------- 11. 처리 기록 스트림 위치
alter table public.events add column if not exists stream_position bigint;
update public.events e set stream_position = s.position from public.event_stream_positions s where s.event_id = e.id;
create sequence if not exists public.events_stream_position_seq;
select setval('public.events_stream_position_seq', coalesce((select max(stream_position) from public.events), 0) + 1, false);
create unique index if not exists events_stream_position_key on public.events (stream_position) where stream_position is not null;
create index if not exists events_stream_pending on public.events ("timestamp", id) where stream_position is null;
grant usage, select on sequence public.events_stream_position_seq to service_role;
-- 커밋된 기록에 순서대로 위치를 매긴다(쓰는 트랜잭션이 끝난 뒤 따로 부른다 — 늦게 커밋된 낮은 번호를 놓치지 않게). 매긴 수를 돌려준다.
create or replace function public.publish_event_positions() returns integer language plpgsql as $$
declare r record; n integer := 0;
begin
  perform pg_advisory_xact_lock(hashtextextended('public.publish_event_positions', 0));
  for r in select id from public.events where stream_position is null order by "timestamp", id for update loop
    update public.events set stream_position = nextval('public.events_stream_position_seq') where id = r.id;
    n := n + 1;
  end loop;
  return n;
end $$;
revoke execute on function public.publish_event_positions() from public, anon, authenticated;
grant execute on function public.publish_event_positions() to service_role;
drop table if exists public.event_stream_positions;
drop function if exists public.cleanup_stale_consumers(integer);
