-- A4 (U6) AI 판단 채점.
-- judgment_golden_items: 정답표 항목. 사람이 포털 · CLI · API 로 적는 데이터다 — 시드 없음(처음엔 비어 있다).
--   item 은 경보 상황(설비 · 패턴 · 가정 사실) + 기대 원인 · 고장 유형 + 허용 1위 조치 + 빠질 조치 + 있어야 할 근거 id.
--   고치면 덮어쓰고 item_hash(채점에 쓰는 필드의 지문)가 바뀐다 — 실행마다 항목 지문을 남기므로 전·후 비교가 '정답표 바뀜'을 가린다.
-- judgment_eval_runs: 채점 실행 한 건 = 행 하나(불변). 항목별 결과(items)와 집계(summary), 실행 시점의 지식 상태
--   (knowledge: 그래프 지문 · 노드 · 관계 수 · 마지막 변경 · 관계 목록 스냅숏)를 함께 남겨 두 실행을 골라 지식 고치기 전·후를 비교한다.
create table if not exists public.judgment_golden_items (
  tenant_id  text not null,
  id         text not null check (id ~ '^[a-z0-9][a-z0-9-]{1,63}$'),
  item       jsonb not null,
  item_hash  text not null,
  updated_by text not null,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, id)
);

create table if not exists public.judgment_eval_runs (
  id             text primary key,
  tenant_id      text not null,
  created_at     timestamptz not null default now(),
  created_by     text not null,
  path           text not null check (path in ('decide', 'evaluate', 'worker')),
  repeats        integer not null check (repeats between 1 and 50),
  golden_version text not null,
  knowledge      jsonb not null,
  summary        jsonb not null,
  items          jsonb not null,
  note           text not null default ''
);
create index if not exists judgment_eval_runs_tenant_created_idx on public.judgment_eval_runs (tenant_id, created_at desc);

alter table public.judgment_golden_items enable row level security;
revoke all on public.judgment_golden_items from public, anon, authenticated;
grant select, insert, update, delete on public.judgment_golden_items to service_role;
alter table public.judgment_eval_runs enable row level security;
revoke all on public.judgment_eval_runs from public, anon, authenticated;
grant select, insert on public.judgment_eval_runs to service_role;   -- 실행 기록은 고치지 않는다
