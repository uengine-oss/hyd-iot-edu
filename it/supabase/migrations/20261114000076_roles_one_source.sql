-- 역할의 정본을 업무 DB 하나로 (2026-11-14) — 지식 그래프의 Role 과 이 표의 역할이 서로 다른 목록이던 것을 맞춘다.
--
-- 앞 판: 지식 그래프(it/neo4j/v2/instances.cypher)에는 역할 일곱(운전원 · 생산관리자 · 설비보전팀장 · 구매 담당 · 구매팀장 · 품질팀장 · 공장장),
-- 이 표에는 일곱(품질팀장 · 공장장 대신 인계자 · 인수자)이 따로 있었다. 문서가 「품질팀장 승인」을 쓰면 적재는 되는데(적재 검사는 그래프를 본다)
-- 승인은 「구성원 아님」으로 막혔고(승인은 이 표의 구성원으로 판정한다 — procsvc/inbox.py check_actor), 포털에서 만든 역할은 이 표에만 생겨
-- 문서의 승인 역할로 쓸 수 없었다.
--
-- 이제 어떤 역할이 있고 누가 그 역할인지는 이 표(users 의 role:* 행 · role_members)가 정하고, process 가 지식 그래프의 Role 노드를 이 목록으로
-- 맞춘다(procsvc/agent_authoring.py project_roles — 만들 때 · 지울 때 · 1분마다). 이 파일은 지식이 가리키던 두 역할을 이 표에 넣는다.
-- 담당자(user:me)는 모든 역할의 구성원이다(000072).
--
-- 새로 만든 DB에서는 이 파일이 시드보다 먼저 돈다(테넌트가 아직 없다) — 그때는 아무것도 하지 않고 seed.sql 이 같은 모습을 넣는다.

do $$
begin
  if not exists (select 1 from public.tenants where id = 'hyd') then
    return;
  end if;

  insert into public.users (id, email, username, role, is_agent, agent_type, tenant_id) values
    ('role:quality-mgr', 'qualitymgr@hyd.local', '품질팀장', 'manager', false, null, 'hyd'),
    ('role:plant-mgr',   'plantmgr@hyd.local',   '공장장',   'manager', false, null, 'hyd')
  on conflict (id) do nothing;

  insert into public.role_members (tenant_id, role_id, user_id)
    select 'hyd', r.id, 'user:me' from (values ('role:quality-mgr'), ('role:plant-mgr')) as r(id)
     where exists (select 1 from public.users u where u.tenant_id = 'hyd' and u.id = 'user:me')
  on conflict do nothing;
end $$;
