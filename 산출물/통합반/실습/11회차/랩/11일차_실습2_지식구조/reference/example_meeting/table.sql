-- T8 예시 묶음 — 업무 표 DDL (형식은 T3 students/_template/table.sql 과 같다. 내용은 설계 3.4 표 3개).
-- 시연용 ID 는 demo(스키마 stu_demo). Supabase SQL 편집기(또는 psql -h 127.0.0.1 -p 54322 -U postgres)에서 실행한다.
-- 암호(change-me)는 바꾼다 — T4 서버는 STUDENT_DSN 암호가 change-me 그대로면 뜨지 않는다.
-- 사람 · 회사 · 메일은 모두 가상이다(example.com). 실제 개인 정보를 넣지 않는다.
-- 일부러 넣은 지는 가지: 4인실 A(고객 회의 6인 규칙 미달), 필수 참석자 박임원(가상)은 목요일 14시 불가(캘린더 쪽 — 표에는 없음).
-- 지우기(수업 뒤): drop schema stu_demo cascade; drop role stu_demo_reader;

create schema if not exists stu_demo;
comment on schema stu_demo is '시연 demo 업무 표 (전체 과정 랩업 T8 예시)';

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'stu_demo_reader') then
    create role stu_demo_reader login password 'change-me' nosuperuser nocreaterole nocreatedb nobypassrls;
  end if;
end $$;
alter role stu_demo_reader set default_transaction_read_only = on;
grant usage on schema stu_demo to stu_demo_reader;
alter default privileges in schema stu_demo grant select on tables to stu_demo_reader;

create table if not exists stu_demo.meeting_request (
  request_id text primary key,
  customer text not null,
  title text not null,
  kind text not null check (kind in ('qbr', 'weekly')),
  duration_min integer not null check (duration_min > 0),
  due_by date not null,
  organizer_email text not null,
  status text not null default 'requested' check (status in ('requested', 'scheduled', 'unconfirmed', 'cancelled'))
);
comment on table stu_demo.meeting_request is '회의 요청 한 건 = 처리 건 하나 (시작 폼의 request_id)';
comment on column stu_demo.meeting_request.due_by is '고객이 요청한 마감일 — 넘기는 시간 후보는 감점(D1 6)';

create table if not exists stu_demo.attendee (
  request_id text not null references stu_demo.meeting_request(request_id) on delete cascade,
  name text not null,
  email text not null,
  required boolean not null default false,
  primary key (request_id, email)
);
comment on table stu_demo.attendee is '부를 사람 — required 가 true 인 사람은 전원 가능해야 확정(D1 1). 응답(수락 · 거절)은 캘린더가 원본';

create table if not exists stu_demo.room (
  room_id text primary key,
  capacity integer not null check (capacity > 0),
  calendar_id text not null
);
comment on table stu_demo.room is '회의실 — 고객 회의는 6인 이상(D1 4). calendar_id 는 회의실 캘린더(예시본은 가상 값)';

insert into stu_demo.meeting_request (request_id, customer, title, kind, duration_min, due_by, organizer_email) values
  ('QBR-2026-Q4-01', '가온상사(가상)', '가온상사 4분기 리뷰', 'qbr', 60, '2026-10-16', 'organizer@example.com')
on conflict (request_id) do nothing;
insert into stu_demo.attendee (request_id, name, email, required) values
  ('QBR-2026-Q4-01', '김주관(가상)', 'organizer@example.com', true),
  ('QBR-2026-Q4-01', '박임원(가상)', 'customer-exec@example.com', true),      -- 필수 · 거절 · 무응답 가지를 밟을 사람(시험 계정)
  ('QBR-2026-Q4-01', '이담당(가상)', 'customer-staff@example.com', false),
  ('QBR-2026-Q4-01', '최기술(가상)', 'engineer@example.com', false),
  ('QBR-2026-Q4-01', '정품질(가상)', 'quality@example.com', false),
  ('QBR-2026-Q4-01', '한재무(가상)', 'finance@example.com', false)
on conflict do nothing;
insert into stu_demo.room (room_id, capacity, calendar_id) values
  ('room-a', 4, 'example-room-a-calendar'),      -- 4인실: 고객 회의 규칙 미달(지는 가지)
  ('room-b', 6, 'example-room-b-calendar'),
  ('room-c', 10, 'example-room-c-calendar')
on conflict (room_id) do nothing;

grant select on all tables in schema stu_demo to stu_demo_reader;
