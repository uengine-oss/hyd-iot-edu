-- A7 (U12, 2026-10-08) 손익 · What-if: 조치 카드의 돈 항목(작업 정지 시간 · 작업비 · 부품비)을 업무 DB 값에서 계산하려면
-- CMMS에 "SOP별 표준 작업"이 있어야 한다. 지금까지는 쿨러 핀 세척(maintenance_profiles.clean_h · clean_cost)만 있었고,
-- 씰 · 베어링 교체의 정지 시간 · 작업비 · 부품 단가는 업무 DB 어디에도 없어 손익을 "출처 없는 값" 없이 계산할 수 없었다.
-- 추가만 한다(기존 표 · 행 · 함수 변경 없음). 값은 다른 ent 시드와 같은 교육용 가상 값이며 entsim/data.py(memory 백엔드)와 같다.
--   SOP-COOL-04 쿨러 핀 세척은 설비별 정비 기준(maintenance_profiles)을 그대로 따른다(from_profile) — 같은 값을 두 곳에 두지 않는다.
--   씰 · 베어링 공급사 견적(그래프 SUPPLIED_BY)은 ent.suppliers의 키가 공급사 하나당 한 부품이라 넣지 않고, 부품 표준단가만 둔다.

insert into ent.parts (part_no, name, std_price) values
  ('P-PMP-SEAL', '펌프 축 씰 키트', 50),
  ('P-FAN-BRG', '팬 베어링', 25)
on conflict (part_no) do nothing;

create table if not exists ent.task_standards (           -- CMMS: SOP별 표준 작업 (계획 정지 · 작업비 · 필요 부품)
  sop text primary key,                                     -- 온톨로지 Skill.sopId / 작업지시 WO_CREATE 값
  name text not null,
  from_profile boolean not null default false,              -- true: 설비별 maintenance_profiles.clean_h · clean_cost 사용
  stop_h numeric check (stop_h is null or stop_h >= 0),     -- 생산을 멈추는 시간(h)
  labor_cost numeric check (labor_cost is null or labor_cost >= 0),   -- 작업비(만원)
  part_no text references ent.parts(part_no),
  part_qty integer not null default 0 check (part_qty >= 0),
  check (from_profile or (stop_h is not null and labor_cost is not null))
);

insert into ent.task_standards (sop, name, from_profile, stop_h, labor_cost, part_no, part_qty) values
  ('SOP-COOL-04', '쿨러 핀 세척', true, null, null, null, 0),
  ('SOP-COOL-05', '캐비닛 환기 개선', false, 0, 30, null, 0),
  ('SOP-PMP-04', '펌프 축 씰 교체', false, 4, 60, 'P-PMP-SEAL', 1),
  ('SOP-FAN-04', '팬 베어링 교체', false, 3, 50, 'P-FAN-BRG', 1)
on conflict (sop) do nothing;

alter table ent.task_standards enable row level security;
drop policy if exists task_standards_read_all on ent.task_standards;
create policy task_standards_read_all on ent.task_standards for select to anon, authenticated using (true);
drop policy if exists enterprise_mcp_reader on ent.task_standards;
create policy enterprise_mcp_reader on ent.task_standards for select to hyd_enterprise_reader using (true);
grant select on ent.task_standards to hyd_enterprise_reader;

-- 읽기 RPC: 설비의 정비 기준과 합친 표준 작업 목록. 설비가 없으면 facts null (enterprise-sim이 404로 돌려준다).
create or replace function ent.cmms_tasks(p_asset text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'CMMS',
    'facts', case when mp.asset is null then null else '{}'::jsonb end,
    'records', case when mp.asset is null then '[]'::jsonb else coalesce((
      select jsonb_agg(jsonb_build_object(
               'sop', t.sop, 'name', t.name,
               'stop_h', case when t.from_profile then mp.clean_h else t.stop_h end,
               'labor_cost', case when t.from_profile then mp.clean_cost else t.labor_cost end,
               'part_no', t.part_no, 'part_qty', t.part_qty,
               'source', case when t.from_profile then 'maintenance_profiles' else 'task_standards' end) order by t.sop)
      from ent.task_standards t), '[]'::jsonb) end)
  from (select 1) one left join ent.maintenance_profiles mp on mp.asset = p_asset
$$;

grant execute on function ent.cmms_tasks(text) to anon, authenticated, service_role, hyd_enterprise_reader;
