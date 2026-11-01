-- 2026-10-30 시스템 건강검진 뒤 독립 검증에서 남은 것(작업/2026-10-30_시스템-건강검진/검진/FE_검증.md · FE_고침.md).
--  1. 원천 접수가 명령 관문의 거절(감사 토픽 audit 의 CMD_REJECTED)을 종류 REJECT 로 받는다(G3b-9, FB 요청) — 토픽 · 종류 검사에 더한다.
--  2. 순정(OEM) 공급사 여부의 주인은 업무 DB 공급사 원장이다(G3b-27, FK 요청): ent.suppliers.oem, 견적 읽기(quote_rows · part_quotes_read)에 싣는다.
--     공급사 · 견적의 정본은 업무 DB 이고 그래프의 SUPPLIED_BY · Supplier 는 process 동기화(scm_sync)가 만드는 사본이다
--     (045 머리말의 「값은 온톨로지와 같다」는 적용된 파일이라 그대로 둔다 — 이 줄이 이긴다).
--  3. 069 §9 가 SOP-FAN-11(쿨러 팬 점검) · SOP-FAN-12(벨트 교체)에 팬 베어링 소모 · 정지 · 작업비를 넣었다 — 강사 서명 원문
--     (course_extractions.json)에 그 값이 없다(점검은 교체 없음, 벨트 교체는 베어링이 아님). 지어낸 값이라 지운다. 그 카드의 손익은
--     「표준 작업 없음」으로 미확인이 맞다(값이 원문에 생기면 그때 넣는다).
--  4. 쓰는 거래가 없어진 업무 표(069 가 대체 출하 · 로트 처분 · 수요 제어 거래를 지움) — 성과 지표도 읽지 않는다(FD) — 를 지운다.

-- ---------------------------------------------------------------- 1. 관문 거절 접수
alter table public.process_source_inbox drop constraint if exists process_source_inbox_topic_check;
alter table public.process_source_inbox add constraint process_source_inbox_topic_check
  check (topic in ('alerts', 'plant.status', 'audit'));
alter table public.process_source_inbox drop constraint if exists process_source_inbox_kind_check;
alter table public.process_source_inbox add constraint process_source_inbox_kind_check
  check (kind in ('RAISE', 'CLEAR', 'ACK', 'REJECT', 'STATUS', 'INVALID'));

-- ---------------------------------------------------------------- 2. 순정 공급사
alter table ent.suppliers add column if not exists oem boolean not null default false;
update ent.suppliers set oem = (id = 'sup:b') where id in ('sup:a', 'sup:b', 'sup:c');
comment on column ent.suppliers.oem is '설비 제조사 순정(OEM) 공급사인가. 구매 판단의 「순정 우선」이 이 칸을 읽는다(표시 이름 글자로 가리지 않는다)';

drop function if exists ent.quote_rows(text);
create function ent.quote_rows(p_part text) returns table (part_no text, supplier_id text, supplier_name text, price numeric,
                                                          fail_rate numeric, lead_d integer, avl boolean, oem boolean)
language sql stable as $$
  select q.part_no, q.supplier_id, s.name, q.price, q.fail_rate, q.lead_d, s.avl, s.oem
    from ent.part_quotes q join ent.suppliers s on s.id = q.supplier_id where q.part_no = p_part
  union all
  select s.part_no, s.id, s.name, s.price, s.fail_rate, s.lead_d, s.avl, s.oem
    from ent.suppliers s where s.part_no = p_part and not exists (select 1 from ent.part_quotes q where q.part_no = p_part)
$$;
comment on function ent.quote_rows(text) is '부품 하나의 공급사 견적(부품별 견적 우선, 없으면 공급사 원장의 그 부품 행). 견적의 정본 — 그래프는 동기화 사본';

create or replace function ent.part_quotes_read(p_part text) returns jsonb language sql stable as $$
  select jsonb_build_object('system', 'SCM',
    'facts', case when not exists (select 1 from ent.parts where part_no = p_part) then null
                  else jsonb_build_object('part_no', p_part, 'std_price', (select std_price from ent.parts where part_no = p_part)) end,
    'records', coalesce((select jsonb_agg(jsonb_build_object('supplier', q.supplier_id, 'name', q.supplier_name, 'price', q.price,
                                          'fail_rate', q.fail_rate, 'lead_d', q.lead_d, 'avl', q.avl, 'oem', q.oem) order by q.supplier_id)
                         from ent.quote_rows(p_part) q), '[]'::jsonb))
$$;
revoke execute on function ent.quote_rows(text) from public, anon, authenticated;
grant execute on function ent.quote_rows(text) to service_role, hyd_enterprise_reader;
grant execute on function ent.part_quotes_read(text) to service_role, hyd_enterprise_reader;

-- ---------------------------------------------------------------- 3. 원문에 없는 표준 작업 값
delete from ent.task_standards where sop in ('SOP-FAN-11', 'SOP-FAN-12');

-- ---------------------------------------------------------------- 4. 쓰는 길 없는 업무 표
drop table if exists ent.shipments;
drop table if exists ent.lot_dispositions;
drop table if exists ent.ems_actions;
