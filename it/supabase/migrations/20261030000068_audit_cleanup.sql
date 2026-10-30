-- 2026-10-30 전체 점검 · 결함 수정이 바꾼 DB 구조(이 파일 하나에 모은다).
-- 원격 수업 관리 서버(강사 서버가 학생 PC의 도구 호출을 중계하던 갈래)를 지웠다(2026-10-30).
-- 그 갈래만 쓰던 도구 입출력 대기열 표를 지운다. 학생 PC 안의 로컬 중계 관문 장부(hyd_classroom_grants · hyd_classroom_runs)는 남는다.
DROP TABLE IF EXISTS hyd_classroom_tool_io;

-- 로컬 중계 관문 장부(procsvc/course_ledger.py): 이름을 학생 PC 수업 장부로 바꾸고(hyd_classroom_* → hyd_course_* — 지운 원격 서버와 헷갈리지 않게),
-- 원격 규칙(같은 입력 = 같은 유료 실행, 끝은 강사 서버가 확정)을 「장부 실행 하나 = 워커 점유 한 번」으로 바꾼다. 옛 규칙의 실행 행은 새 규칙으로
-- 이어 쓸 수 없어 지운다. PC 누적 사용량은 계정 행에 남긴다 — 계정은 PC의 테넌트 하나다(옛 행은 워커 인증 파일 HMAC 이 열쇠라 파일을 새로
-- 만들면 사용량이 0부터였다). 원격 전용 열(cache_key · result_ref · request_key · 승인 판본 · 만료 · 사용 여부)은 없앤다.
ALTER TABLE hyd_classroom_grants RENAME TO hyd_course_grants;
DROP TABLE hyd_classroom_runs;
ALTER TABLE hyd_course_grants DROP CONSTRAINT hyd_classroom_grants_pkey;
CREATE TEMP TABLE hyd_course_usage AS
    SELECT subject AS account, (array_agg(policy ORDER BY calls DESC))[1] AS policy,
           sum(calls)::bigint AS calls, sum(input_bytes)::bigint AS input_bytes, sum(output_tokens)::bigint AS output_tokens
    FROM hyd_course_grants GROUP BY subject;
DELETE FROM hyd_course_grants;
ALTER TABLE hyd_course_grants RENAME COLUMN key_hash TO account;
ALTER TABLE hyd_course_grants DROP COLUMN subject, DROP COLUMN scope, DROP COLUMN enabled, DROP COLUMN expires_at;
ALTER TABLE hyd_course_grants ADD PRIMARY KEY (account);
INSERT INTO hyd_course_grants(account, policy, calls, input_bytes, output_tokens)
    SELECT account, policy, calls, input_bytes, output_tokens FROM hyd_course_usage;
DROP TABLE hyd_course_usage;
CREATE TABLE hyd_course_runs (
    id uuid PRIMARY KEY,
    account text NOT NULL REFERENCES hyd_course_grants(account),
    todo_id text NOT NULL,
    generation integer NOT NULL,
    consumer text NOT NULL,
    state text NOT NULL CHECK (state IN ('OPEN','ENDED','EXPIRED')),   -- OPEN = 점유가 살아 있음, ENDED = 점유가 끝남, EXPIRED = 실행 기한 · 임대 끊김
    created_at timestamptz NOT NULL DEFAULT now(),
    deadline timestamptz NOT NULL,
    calls bigint NOT NULL DEFAULT 0 CHECK (calls >= 0),
    input_bytes bigint NOT NULL DEFAULT 0 CHECK (input_bytes >= 0),
    output_tokens bigint NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    UNIQUE (account, todo_id, consumer)
);
CREATE INDEX hyd_course_runs_open ON hyd_course_runs(account, state);
CREATE INDEX hyd_course_runs_task ON hyd_course_runs(account, todo_id);
REVOKE ALL ON hyd_course_grants, hyd_course_runs FROM PUBLIC, anon, authenticated;
ALTER TABLE hyd_course_runs ENABLE ROW LEVEL SECURITY;

-- ---- engine 갈래(프로세스 엔진) --------------------------------------------------------------------------------------------
-- A-01 설비 상태(STATUS) 수신은 설비별 최신 상태 한 줄(process_source_state)만 갱신하고 접수 기록(process_source_inbox)으로 남기지 않는다
-- (procsvc/source_inbox.py — 20배속에서 초당 약 3.6건이 원문과 함께 영구 행으로 쌓였다). 최신 상태 줄은 ACK 접수만 가리킨다.
-- parent_id(자기 표를 가리키는 외래 키)에 색인이 없으면 행 하나를 지울 때마다 표 전체를 다시 훑는다 — 이 PC 실측: 62만 행 · 1.7 GB에서
-- 아래 삭제가 24분 넘게 끝나지 않았다. 지우기 전에 색인을 만든다(접수 행을 지울 때마다 쓰이므로 계속 둔다).
CREATE INDEX IF NOT EXISTS source_inbox_parent ON public.process_source_inbox(parent_id) WHERE parent_id IS NOT NULL;
ALTER TABLE public.process_source_state ALTER COLUMN receipt_id DROP NOT NULL;
UPDATE public.process_source_state s SET receipt_id = NULL
    FROM public.process_source_inbox r WHERE r.id = s.receipt_id AND r.kind = 'STATUS';
DELETE FROM public.process_source_inbox c
    WHERE c.parent_id IN (SELECT id FROM public.process_source_inbox WHERE kind = 'STATUS' AND status = 'HANDLED');
DELETE FROM public.process_source_inbox WHERE kind = 'STATUS' AND status = 'HANDLED';

-- A-01 그래프 반영 대기열(execution_projection_outbox)은 처리한 행을 처리 건마다 마지막 하나만 남긴다(procsvc/projection_repo.py
-- finish_projection 이 이어서 지운다 — 처리 표시만 하고 지우지 않아 작업 행이 바뀔 때마다 한 줄씩 끝없이 쌓였다).
DELETE FROM public.execution_projection_outbox o
    WHERE o.processed_at IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.execution_projection_outbox n
        WHERE n.tenant_id = o.tenant_id AND n.proc_inst_id = o.proc_inst_id AND n.processed_at IS NOT NULL AND n.id > o.id);

-- B-10 사건 하나에 진행 중 처리 건 하나 — 경보로 처리 건을 여는 길을 원천 접수 하나로 모은 뒤(main._admit_alert → InstanceRuntime.receive_alert)
-- 저장소도 같은 규칙을 지킨다. 옛 판(여는 길 넷)이 이미 같은 사건에 처리 건을 둘 이상 열어 둔 DB는 규칙을 걸기 전에 정해진 규칙으로 정리한다:
-- 가장 먼저 열린 처리 건 하나를 남기고, 나중에 열린 것은 열린 단계를 취소하고 「중복으로 열려 닫음」(end_event duplicate-closed)으로 끝내며
-- 그 처리 건 기록에 까닭을 남긴다. 학생은 어느 쪽을 닫을지 정할 수 없어, 정리 없이 실패시키면 시작.bat 이 업무 DB 업데이트에서 멈춘다.
CREATE TEMP TABLE hyd_duplicate_instances AS
    SELECT proc_inst_id FROM (
        SELECT proc_inst_id, row_number() OVER (
                   PARTITION BY tenant_id, jsonb_path_query_first(variables_data, '$[*] ? (@.key == "incident").value') #>> '{}'
                   ORDER BY start_date NULLS LAST, proc_inst_id) AS n
        FROM public.bpm_proc_inst
        WHERE status = 'RUNNING' AND NOT is_deleted
          AND jsonb_path_exists(variables_data, '$[*] ? (@.key == "incident" && @.value != null)')) ranked
    WHERE n > 1;
UPDATE public.todolist SET status = 'CANCELLED', end_date = now(),
       log = coalesce(log, '') || 'cancelled: duplicate instance of the same incident closed by migration 068; '
    WHERE proc_inst_id IN (SELECT proc_inst_id FROM hyd_duplicate_instances) AND status NOT IN ('DONE', 'CANCELLED');
UPDATE public.bpm_proc_inst SET status = 'CANCELLED', end_event = 'duplicate-closed', end_date = now(), current_activity_ids = '{}'
    WHERE proc_inst_id IN (SELECT proc_inst_id FROM hyd_duplicate_instances);
INSERT INTO public.events (id, job_id, proc_inst_id, event_type, crew_type, data, "timestamp")
    SELECT gen_random_uuid()::text, 'INSTANCE_DUPLICATE_CLOSED', proc_inst_id, 'error', 'system',
           jsonb_build_object('name', '중복 처리 건 닫음',
                              'friendly', '같은 경보로 처리 건이 두 번 열려 있어(옛 판의 결함) 먼저 열린 처리 건만 남기고 이 처리 건은 닫았습니다.'),
           now()
    FROM hyd_duplicate_instances;
DROP TABLE hyd_duplicate_instances;
CREATE UNIQUE INDEX IF NOT EXISTS bpm_proc_inst_one_running_per_incident ON public.bpm_proc_inst
    (tenant_id, (jsonb_path_query_first(variables_data, '$[*] ? (@.key == "incident").value') #>> '{}'))
    WHERE status = 'RUNNING' AND NOT is_deleted
      AND jsonb_path_exists(variables_data, '$[*] ? (@.key == "incident" && @.value != null)');

-- 처리 건 원천 표(마이그레이션 001)는 만들기만 하고 코드 · SQL 함수 · 뷰 어디서도 쓰지 않았다(행 0, 외래 키 · 뷰 의존 0 — 2026-10-30 확인)
DROP TABLE IF EXISTS public.proc_inst_source;

-- 시스템 수행자 이름에서 실행기 제품 이름을 뺀다(학생 화면의 내부어 — 시드 seed.sql 과 같은 값)
UPDATE public.users SET username = '인공지능 에이전트' WHERE id = 'sys:agent' AND username = 'AI 에이전트 (Claude Code)';
