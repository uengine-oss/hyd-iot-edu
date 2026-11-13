-- 사람 고르기 삭제 (2026-11-13) — 로그인이 없고 한 사람이 자기 PC에서 쓰는 포털에서, 쓰는 사람은 늘 담당자 한 명이다.
--
-- 앞 판은 로그인 대신 가짜 직원 여섯 명(김운전 · 최운전 · 이생산 · 박정비 · 정구매 · 한구매) 가운데 하나를 「나」로 고르게 했다.
-- 고르기 전에는 승인 단추가 꺼져 있었고, 이름이 사람인지 직책인지 화면만으로는 알 수 없었다(사용자 2026-11-13 「이름인 줄 몰랐어요
-- 그런 거 있으면 안 됩니다 … 로그인 개념이 없으니까요 … 상시 그냥 내가 담당자인 거고요」).
--
-- 이제 사람은 담당자(user:me) 한 명이고, 모든 역할의 구성원이다. 서버 규칙은 그대로다(procsvc/inbox.py):
--   - 역할의 구성원이 한 명이면 그 역할의 사람 단계가 그 사람에게 바로 배정된다(resolve) → 모든 사람 단계가 담당자에게 온다.
--   - 그 역할의 구성원만 그 역할로 승인한다(check_actor) → 담당자는 어느 역할로든 승인하고, 기록에는 승인한 역할이 남는다.
-- 교대 인수인계의 인계자 · 인수자는 가짜 직원 두 명에게 묶여 있었다 → 역할 두 개(role:shift-out · role:shift-in)로 등록한다
-- (정의 definitions/shift_handover_v1.json 이 이 역할을 가리킨다).
--
-- 새로 만든 DB에서는 이 파일이 시드보다 먼저 돈다(테넌트가 아직 없다) — 그때는 아무것도 하지 않고 seed.sql 이 같은 모습을 넣는다.

do $$
declare
  fakes text[] := array['user:kim-op', 'user:choi-op', 'user:lee-prod', 'user:park-maint', 'user:jung-buy', 'user:han-buymgr'];
begin
  if not exists (select 1 from public.tenants where id = 'hyd') then
    return;
  end if;

  insert into public.users (id, email, username, role, is_agent, agent_type, tenant_id) values
    ('role:shift-out', 'shiftout@hyd.local', '인계자', 'operator', false, null, 'hyd'),
    ('role:shift-in',  'shiftin@hyd.local',  '인수자', 'operator', false, null, 'hyd'),
    ('user:me',        'me@hyd.local',       '담당자', 'manager',  false, null, 'hyd')
  on conflict (id) do update set email = excluded.email, username = excluded.username, role = excluded.role;

  -- 담당자는 모든 역할(포털에서 만든 역할 포함)의 구성원이다
  insert into public.role_members (tenant_id, role_id, user_id)
    select 'hyd', u.id, 'user:me' from public.users u
     where u.tenant_id = 'hyd' and u.id like 'role:%' and not u.is_agent
  on conflict do nothing;

  -- 가짜 직원 앞으로 열려 있던 일과 알림은 담당자에게 넘긴다(닫힌 일의 기록은 그대로 둔다)
  update public.todolist set user_id = 'user:me'
   where tenant_id = 'hyd' and user_id = any(fakes) and status not in ('DONE', 'CANCELLED');
  update public.notifications set user_id = 'user:me'
   where tenant_id = 'hyd' and user_id = any(fakes);

  -- 가짜 직원 삭제(role_members 는 users 를 따라 지워진다)
  delete from public.users where tenant_id = 'hyd' and id = any(fakes);
end $$;
