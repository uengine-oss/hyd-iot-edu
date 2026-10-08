-- U4 (mini ProcessGPT TODO 4, 2026-10-08) → B4 재기반(000028 → 000044): "배포된 판본" — 정의 id별 운영 판본 하나와 배포 이력.
-- B4: 경보는 패턴별로 "배포된 흐름"이 연다 — alertPolicy.patterns에 그 패턴이 있는 배포 흐름 중 가장 최근 배포, 없으면 기준 흐름(anomaly_response).
--     withdraw = 학생 흐름을 경보 경로에서 내림(prod_version null, version null), reset = 기준 흐름 포인터를 기준 판본으로(POST /api/flows/deploy-reset).
-- 지금까지 proc_def.prod_version은 "마지막에 등록한 판본"이었다(upsert_proc_def가 등록할 때마다 덮어씀, 기동 때 파일 판본으로 되돌아감).
-- 이제부터 prod_version은 배포 API(또는 기동 시드)만 바꾸는 "경보가 여는 운영 판본" 포인터이고,
-- 등록(POST /api/process/definitions)은 proc_def_version에 불변 판본만 더한다. 이력은 아래 표에 쌓인다(누가·언제·사유·이전 판본).
create table if not exists public.proc_def_deployment (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null references public.tenants(id) on update cascade on delete cascade,
  proc_def_id text not null,
  version text,                                          -- 배포된 판본 (proc_def_version.version, version_tag='hyd-immutable'); withdraw만 null
  previous_version text,                                 -- 직전 운영 판본 (되돌리기 대상)
  action text not null check (action in ('seed', 'deploy', 'rollback', 'reset', 'withdraw')),
  actor text not null,
  reason text not null,
  created_at timestamptz not null default now(),
  check (version is not null or action = 'withdraw')
);
create index if not exists ix_proc_def_deployment_lookup on public.proc_def_deployment (tenant_id, proc_def_id, created_at desc);

-- 백필: 지금 proc_def.prod_version이 가리키는 판본(마지막 등록 판본)을 그대로 첫 배포 기록으로 남긴다. 운영 중인 경보 경로가 바뀌지 않도록
-- 포인터 값은 건드리지 않는다. 불변 판본 행이 없는 포인터(옛 백필 전 행)는 기록하지 않고, 기동 시드가 파일로 등록·배포한다.
insert into public.proc_def_deployment (tenant_id, proc_def_id, version, previous_version, action, actor, reason)
select d.tenant_id, d.id, d.prod_version, null, 'seed', 'migration',
       '마이그레이션 000044: 기존 proc_def.prod_version(마지막 등록 판본)을 배포 판본으로 기록'
from public.proc_def d
where not d.isdeleted and coalesce(d.prod_version, '') <> ''
  and exists (select 1 from public.proc_def_version v
              where v.tenant_id = d.tenant_id and v.proc_def_id = d.id and v.version = d.prod_version and v.version_tag = 'hyd-immutable')
  and not exists (select 1 from public.proc_def_deployment x where x.tenant_id = d.tenant_id and x.proc_def_id = d.id);

alter table public.proc_def_deployment enable row level security;
drop policy if exists proc_def_deployment_read_all on public.proc_def_deployment;
create policy proc_def_deployment_read_all on public.proc_def_deployment for select to anon, authenticated using (true);
drop policy if exists proc_def_deployment_write_authenticated on public.proc_def_deployment;
create policy proc_def_deployment_write_authenticated on public.proc_def_deployment for all to authenticated using (true) with check (true);
grant select on public.proc_def_deployment to anon;
grant all on public.proc_def_deployment to authenticated, service_role;
