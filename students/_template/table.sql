-- T3 학생 업무 표 DDL 출발본 (전체 과정 랩업 G5 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2 · 6.1).
-- s00 을 내 ID 로 바꿔 Supabase SQL 편집기(또는 psql -h 127.0.0.1 -p 54322 -U postgres)에서 실행한다. 암호(change-me)도 바꾼다 —
-- T4 서버는 STUDENT_DSN 암호가 change-me 그대로면 뜨지 않는다.
-- 만드는 것: 스키마 stu_s00 · 읽기 전용 계정 stu_s00_reader(이 스키마 SELECT 만) · 예시 표 2개와 행(3절 회의 준비 예시).
-- 수업 업무 DB(ent)와 같은 규칙: 읽기 계정은 슈퍼유저 · 역할 만들기 · RLS 우회 권한이 없다(T4 서버가 접속 때 확인한다).
-- 지우기(수업 뒤): drop schema stu_s00 cascade; drop role stu_s00_reader;

create schema if not exists stu_s00;
comment on schema stu_s00 is '학생 s00 업무 표 (전체 과정 랩업)';

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'stu_s00_reader') then
    create role stu_s00_reader login password 'change-me' nosuperuser nocreaterole nocreatedb nobypassrls;
  end if;
end $$;
alter role stu_s00_reader set default_transaction_read_only = on;
grant usage on schema stu_s00 to stu_s00_reader;
alter default privileges in schema stu_s00 grant select on tables to stu_s00_reader;

create table if not exists stu_s00.meeting (
  id text primary key,
  name text not null,
  kind text not null check (kind in ('customer_review', 'internal')),
  starts_at timestamptz,
  room_seats integer
);
comment on table stu_s00.meeting is '준비하는 회의 (온톨로지 Meeting 과 같은 id)';
comment on column stu_s00.meeting.room_seats is '잡은 회의실 좌석 수 — 고객 회의는 6 이상(D1 규칙)';

create table if not exists stu_s00.attendee (
  meeting_id text not null references stu_s00.meeting(id) on delete cascade,
  email text not null,
  required boolean not null default true,
  response text not null default 'none' check (response in ('none', 'accepted', 'declined')),
  primary key (meeting_id, email)
);
comment on table stu_s00.attendee is '참석자와 응답 — 필수 참석자 전원 accepted 여야 확정(D1 규칙)';

insert into stu_s00.meeting (id, name, kind, starts_at, room_seats) values
  ('s00:meeting-q3', '3분기 고객 리뷰', 'customer_review', null, 4)          -- 일부러 좌석 미달(지는 가지)
on conflict (id) do nothing;
insert into stu_s00.attendee (meeting_id, email, required, response) values
  ('s00:meeting-q3', 'lead@example.com', true, 'accepted'),
  ('s00:meeting-q3', 'customer@example.com', true, 'none'),                  -- 무응답(미달 가지)
  ('s00:meeting-q3', 'observer@example.com', false, 'declined')
on conflict do nothing;

grant select on all tables in schema stu_s00 to stu_s00_reader;
