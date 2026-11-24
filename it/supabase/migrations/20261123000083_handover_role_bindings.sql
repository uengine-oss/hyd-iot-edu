-- 2026-11-23 진행 중이던 교대 인수인계 처리 건의 역할 묶음에 남은 지운 직원 id 를 역할 id 로 바꾼다.
--
-- 072(사람 고르기 삭제)는 가짜 직원 여섯을 지우면서 열린 작업 · 알림만 담당자에게 넘겼다. 교대 인수인계 정의는 그 전 판에서 인계자 · 인수자를
-- 가짜 직원 둘(user:kim-op · user:choi-op)에 묶었고, 그때 열린 처리 건은 그 묶음을 처리 건에 복사해 들고 있다(bpm_proc_inst.role_bindings —
-- 처리 건의 묶음이 정의의 묶음보다 먼저다, engine.instance_binding). 그래서 072 를 지난 PC 에서 진행 중이던 교대 처리 건의 다음 사람 단계는
-- 지운 사람 앞으로 열려 아무도 제출할 수 없었다(「이 작업 또는 질문에 배정된 담당자만 제출할 수 있습니다」).
-- 진행 중인 처리 건의 묶음에서 두 id 를 072 가 정의에서 바꾼 것과 같은 역할(role:shift-out · role:shift-in)로 바꾼다. 끝난 처리 건의 기록은 그대로 둔다.
-- 다른 가짜 직원 넷은 어느 정의의 역할 묶음에도 쓰인 적이 없다(정의 파일 이력 — 072 커밋이 바꾼 묶음은 이 둘뿐).

update public.bpm_proc_inst i
   set role_bindings = (
         select jsonb_agg(case b->>'endpoint'
                            when 'user:kim-op'  then jsonb_set(b, '{endpoint}', '"role:shift-out"')
                            when 'user:choi-op' then jsonb_set(b, '{endpoint}', '"role:shift-in"')
                            else b end order by ord)
           from jsonb_array_elements(i.role_bindings) with ordinality as t(b, ord))
 where i.status = 'RUNNING'
   and jsonb_typeof(i.role_bindings) = 'array'
   and exists (select 1 from jsonb_array_elements(i.role_bindings) b where b->>'endpoint' in ('user:kim-op', 'user:choi-op'));
