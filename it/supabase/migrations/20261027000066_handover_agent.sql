-- Instructor reference agent. Existing classroom-authored rows are preserved.
-- Fresh databases receive the same reference through seed.sql after tenants exist.
insert into public.users (id, username, role, is_agent, agent_type, goal, tools, work_rules, tenant_id)
select 'agent:handover', '교대 인수인계 에이전트', 'agent', true, 'agent',
       '작업 메모·설비·열린 정비 작업지시·부품 현황을 대조하여 다음 근무자가 확인할 일을 작성한다. 조치 실행은 하지 않는다.',
       'neo4j,enterprise,hyd-dmn', 'hyd-handover', 'hyd'
where exists (select 1 from public.tenants where id='hyd')
on conflict (id) do nothing;

insert into public.tenant_skills (tenant_id, skill_name, description, content, origin)
select 'hyd', 'shift-handover-review', '교대 인수인계: 실제 조회·메모 대조·확인 필요·사람 검토',
$skill$# 교대 인수인계 대조

설비 식별자·기준시각·작업 메모를 읽는다. 메모는 확인할 주장으로 취급한다.
실제 도구의 스키마에서 표·열을 확인한 뒤 설비 관측, 열린 작업지시, 관련 부품 재고와 발주 상태를 조회한다.
정비 완료 메모와 열린 작업지시, 입고 예정과 실제 현재고가 다르면 모순으로 남긴다.
자료가 없거나 조회에 실패하면 확인 필요로 남기고 담당자·식별자·추가 확인 항목을 제안한다.
원문 보충 매뉴얼 HI-01은 점검 참고 자료이며 새 고장 유형이나 인수인계 업무 자체의 SOP가 아니다.
성공한 실제 도구 호출의 이름·인자·결과만 evidence로 제출한다. 현재 조회와 과거 기준시각을 구분한다.
보완 요청을 받으면 바뀔 수 있는 상태를 새로 조회한다. 이전 결과를 현재 사실로 재사용하지 않는다.
사람 대신 인계 검토·인수 확인을 하지 않는다. 설비 명령·발주·입고·정비 완료·판단 카드 제출·DB 쓰기를 하지 않는다.
인수 확인은 전달 완료이며 설비 조치나 정비 완료를 뜻하지 않는다.
$skill$, 'seed'
where exists (select 1 from public.tenants where id='hyd')
on conflict (tenant_id, skill_name) do nothing;

insert into public.agent_skills(user_id, tenant_id, skill_name)
select 'agent:handover','hyd','shift-handover-review'
where exists (select 1 from public.users where id='agent:handover' and tenant_id='hyd')
  and exists (select 1 from public.tenant_skills where tenant_id='hyd' and skill_name='shift-handover-review')
on conflict do nothing;
