"""학생 PC 로컬 중계 관문의 실행 장부(표 hyd_course_grants · hyd_course_runs). 비용 경계가 아니다 — 최종 방어는 강의 중계 키의 한도다.

장부 실행 하나 = AI 워커의 점유 한 번(작업 행 todo_id + 점유 표시 consumer — 워커는 점유마다 새 consumer 를 쓴다).
  · 점유가 끝나면 그 실행도 끝난다: 결과 제출 · 실패 · 사람 대기 · 보류 · 취소 · 임대 만료. 끝은 장부에 따로 적지 않고 작업 행(todolist)의
    지금 상태에서 읽는다 — 워커가 끝을 쓰는 그 행이 정본이다(_close_ended).
  · 같은 작업의 정당한 이어 하기(사람 답 · 재평가 · 질문 재개 · 결과 교정 · 워커 재시작)는 새 점유라 새 실행이다. 남용은 작업 단위 누적 상한
    (POLICY['task'] — 그 작업의 모든 실행을 더한 호출 · 입력 바이트 · 출력 토큰)이 막는다.
  · 시간 기한은 한 번의 실행에만 있다(POLICY['run']['seconds']).
  · 동시 한도는 지금 살아 있는 점유(STARTED · 같은 consumer · 임대 안)의 실행만 센다.
한도는 이 파일의 POLICY 한 곳이 정한다. 계정 행(PC의 테넌트 하나)은 누적 사용량과 마지막으로 적용한 정책을 담고, 판본이 다르면 로그에 알리고
바꾼다(사용량은 그대로). 계정은 테넌트라 워커 인증 파일을 새로 만들어도 사용량이 0이 되지 않는다.

거절은 Denied(code) — 사유 표 REASONS 한 곳이 학생에게 보일 문장을 갖는다. 관문(course_model)은 모델 호출 거절에 [HYD:<code>] 를 실어
보내고, AI 워커는 CLI 오류 글에서 그 코드를 찾아 같은 표의 문장을 처리 기록에 남긴다(worker/runner.py). 표준 라이브러리만 쓴다(워커 이미지가 읽는다).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from uuid import uuid4

log = logging.getLogger('procsvc.course_ledger')

POLICY = dict(
    revision='2026-10-30-1',
    model='coding',
    max_concurrency=1,
    # 한 번의 실행(점유 한 번): 강사 녹화의 실행 하나는 모델 호출 8~32회였다(교대 인계안 첫 실행 32회 — 저장소 녹화 message_start 수).
    # 그 1.5배. 출력 상한은 호출마다 미리 적는 max_tokens(32,000) × 호출 수
    run=dict(seconds=600, calls=48, input_bytes=8_000_000, output_tokens=1_536_000),
    # 한 작업의 모든 실행 합(이어 하기 · 재평가 · 재개 · 교정 · 재시작 포함) — 한 번의 실행 다섯 번 몫
    task=dict(calls=240, input_bytes=40_000_000, output_tokens=7_680_000),
    # 이 PC의 수업 전체
    pc=dict(calls=600, input_bytes=100_000_000, output_tokens=20_000_000),
)
USAGE = ('calls', 'input_bytes', 'output_tokens')


@dataclass(frozen=True)
class Reason:
    text: str            # 학생이 읽는 문장(내부어 없음)
    status: int          # 관문 HTTP 상태
    retry: bool          # CLI 가 다시 보내도 되는가(x-should-retry)


REASONS = {
    'concurrent': Reason('이 PC에서 다른 AI 단계가 아직 실행 중입니다. 그 단계가 끝난 뒤 이 단계를 다시 실행하세요.', 429, False),
    'run_limit': Reason('이 단계의 한 번 실행에서 AI를 부를 수 있는 횟수 · 분량을 다 썼습니다. 같은 단계를 다시 실행하면 새로 시작합니다.', 429, False),
    'run_time': Reason('이 단계의 한 번 실행 시간(10분)을 넘었습니다. 같은 단계를 다시 실행하면 새로 시작합니다.', 429, False),
    'task_limit': Reason('이 단계에서 AI를 부를 수 있는 전체 횟수 · 분량(다시 실행 · 재평가 · 이어 하기를 합친 한도)을 다 썼습니다. '
                         '더 실행하려면 강사에게 알려 주세요.', 429, False),
    'pc_limit': Reason('이 PC의 수업 전체 AI 사용 한도를 다 썼습니다. 강사에게 알려 주세요.', 429, False),
    'claim_ended': Reason('이 단계를 맡았던 실행이 끝났거나 다른 실행으로 바뀌어 AI를 더 부르지 않습니다.', 409, False),
    'token': Reason('AI 실행 권한이 없거나 만료됐습니다. 같은 단계를 다시 실행하세요.', 403, False),
    'bad_request': Reason('수업 모델이 아니거나 분량 한도를 적지 않은 요청이라 보내지 않았습니다.', 422, False),
    'too_large': Reason('AI에 보낼 입력이 한 번에 보낼 수 있는 크기를 넘었습니다. 입력을 줄여 다시 실행하세요.', 413, False),
    'relay_config': Reason('이 PC에 강의 중계 설정(.env의 LLM_API_KEY)이 없어 실제 AI를 부를 수 없습니다. 키를 넣고 시작.bat을 다시 실행하세요.', 503, False),
    'relay_auth': Reason('강의 중계가 이 PC의 키를 받지 않습니다(틀렸거나 만료). .env의 LLM_API_KEY가 수업에서 받은 키와 같은지 확인하고 '
                         '시작.bat을 다시 실행하세요.', 502, False),
    'relay_budget': Reason('강의 중계 키의 사용 한도를 다 썼습니다. 강사에게 알려 주세요.', 429, False),
    'relay_model': Reason('강의 중계가 수업 모델을 받지 않습니다. 강사에게 알려 주세요.', 502, False),
    'relay_busy': Reason('강의 중계가 지금 붐벼 요청을 받지 못했습니다. 1분쯤 뒤 이 단계를 다시 실행하세요.', 429, True),
    'relay_rejected': Reason('강의 중계가 이 요청을 받지 않았습니다. 처리 과정을 강사에게 보여 주세요.', 502, False),
    'relay_failed': Reason('강의 중계에 닿지 못했거나 중계가 응답을 끝내지 못했습니다. 잠시 뒤 다시 실행하고, 계속되면 강사에게 알려 주세요.', 502, True),
}
_CODE = re.compile(r'\[HYD:([a-z_]+)\]')


class Denied(ValueError):
    """장부 · 관문 거절. str() 은 학생에게 보일 문장(사유 표, 또는 수업 경계 판정이 준 문장)."""

    def __init__(self, code: str, text: str | None = None):
        self.code = code
        super().__init__(text or REASONS[code].text)


def coded(code: str) -> str:
    """모델 호출 거절에 싣는 글: 코드(워커가 찾는 표시)와 문장."""
    return f'[HYD:{code}] {REASONS[code].text}'


def reason_in(text: str) -> str | None:
    """CLI 오류 글 안의 관문 거절 문장(워커가 처리 기록에 남긴다). 표에 없는 코드 · 코드 없음 = None."""
    for code in _CODE.findall(str(text or '')):
        if code in REASONS:
            return REASONS[code].text
    return None


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


class CourseLedger:
    def __init__(self, connect, policy: dict = POLICY):
        # connect() → psycopg 연결(dict_row). 연결 하나 = 거래 하나(with 블록이 끝나면 커밋).
        self.connect, self.policy = connect, policy

    # ---- 계정(PC의 테넌트 하나)
    def _account(self, db, tenant: str) -> dict:
        from psycopg.types.json import Jsonb
        db.execute('INSERT INTO hyd_course_grants(account,policy) VALUES(%s,%s) ON CONFLICT(account) DO NOTHING',
                   (tenant, Jsonb(self.policy)))
        row = db.execute('SELECT * FROM hyd_course_grants WHERE account=%s FOR UPDATE', (tenant,)).fetchone()
        if (row['policy'] or {}).get('revision') != self.policy['revision']:
            log.warning('수업 실행 장부 정책 판본을 %s → %s 로 바꿉니다(이 PC의 누적 사용량 호출 %s · 입력 %s B · 출력 %s 토큰은 그대로)',
                        (row['policy'] or {}).get('revision'), self.policy['revision'], row['calls'], row['input_bytes'], row['output_tokens'])
            db.execute('UPDATE hyd_course_grants SET policy=%s WHERE account=%s', (Jsonb(self.policy), tenant))
        return row

    def _close_ended(self, db, tenant: str) -> None:
        """작업 행이 더는 그 점유가 아니면 실행을 닫는다: 점유가 끝남 → ENDED, 실행 기한이 지났거나 임대가 끊김(워커가 끝을 못 씀) → EXPIRED."""
        db.execute('''WITH held AS (
                SELECT r.id, r.deadline <= now() AS late,
                       coalesce(w.consumer = r.consumer AND w.status = 'IN_PROGRESS' AND w.draft_status = 'STARTED', false) AS owned,
                       coalesce(w.lease_until > now(), false) AS leased
                FROM hyd_course_runs r LEFT JOIN todolist w ON w.id::text = r.todo_id
                WHERE r.account = %s AND r.state = 'OPEN')
            UPDATE hyd_course_runs r SET state = CASE WHEN h.late OR (h.owned AND NOT h.leased) THEN 'EXPIRED' ELSE 'ENDED' END
            FROM held h WHERE r.id = h.id AND (h.late OR NOT h.owned OR NOT h.leased)''', (tenant,))

    def _task_use(self, db, tenant: str, todo_id: str) -> dict:
        return db.execute('''SELECT coalesce(sum(calls),0) AS calls, coalesce(sum(input_bytes),0) AS input_bytes,
                                    coalesce(sum(output_tokens),0) AS output_tokens
                             FROM hyd_course_runs WHERE account=%s AND todo_id=%s''', (tenant, todo_id)).fetchone()

    # ---- 점유 한 번 = 실행 하나
    def open_run(self, tenant: str, row: dict) -> dict:
        """지금 점유(row — worker_credentials._claim 이 확인한 살아 있는 점유)의 실행. 같은 점유면 같은 실행, 새 점유면 새 실행.
        → {run_id, model, deadline(epoch)}. 거절은 Denied."""
        todo_id, consumer = str(row['id']), str(row['consumer'])
        with self.connect() as db:
            grant = self._account(db, tenant)
            self._close_ended(db, tenant)
            run = db.execute('SELECT *, deadline > now() AS active FROM hyd_course_runs WHERE account=%s AND todo_id=%s AND consumer=%s',
                             (tenant, todo_id, consumer)).fetchone()
            if run:
                if run['state'] != 'OPEN':
                    raise Denied('run_time' if not run['active'] else 'claim_ended')
                return self._view(run)
            used = self._task_use(db, tenant, todo_id)
            if any(used[f] >= self.policy['task'][f] for f in USAGE):
                raise Denied('task_limit')
            if any(grant[f] >= self.policy['pc'][f] for f in USAGE):
                raise Denied('pc_limit')
            live = db.execute("SELECT count(*) AS n FROM hyd_course_runs WHERE account=%s AND state='OPEN'", (tenant,)).fetchone()['n']
            if live >= self.policy['max_concurrency']:
                raise Denied('concurrent')
            run = db.execute('''INSERT INTO hyd_course_runs(id,account,todo_id,generation,consumer,state,deadline)
                VALUES (%s,%s,%s,%s,%s,'OPEN',now() + %s * interval '1 second') RETURNING *, true AS active''',
                (uuid4(), tenant, todo_id, int(row.get('generation') or 0), consumer, self.policy['run']['seconds'])).fetchone()
            return self._view(run)

    def end(self, tenant: str, todo_id: str, consumer: str) -> int:
        """워커가 그 점유를 끝냈다(결과 제출 · 실패 · 사람 대기 · 보류 · 취소 — 끝 상태를 작업 행에 쓴 뒤). 워커가 끝을 알리지 못하고 죽어도
        _close_ended 가 작업 행으로 닫는다."""
        with self.connect() as db:
            return len(db.execute('''UPDATE hyd_course_runs SET state = CASE WHEN deadline <= now() THEN 'EXPIRED' ELSE 'ENDED' END
                WHERE account=%s AND todo_id=%s AND consumer=%s AND state='OPEN' RETURNING id''', (tenant, str(todo_id), str(consumer))).fetchall())

    def _view(self, run) -> dict:
        return dict(run_id=str(run['id']), model=self.policy['model'], deadline=run['deadline'].timestamp())

    def charge(self, run_id: str, *, todo_id: str, consumer: str, input_bytes: int, output_tokens: int) -> None:
        """모델 호출 한 번을 보내기 전에 적는다(출력 상한 전체를 미리 — 다시 보내기도 한 번으로 센다, 돌려주지 않는다)."""
        for name, amount in (('input_bytes', input_bytes), ('output_tokens', output_tokens)):
            if type(amount) is not int or amount <= 0:
                raise Denied('bad_request', f'{name} 값이 올바르지 않습니다')
        with self.connect() as db:
            owner = db.execute('SELECT account FROM hyd_course_runs WHERE id=%s', (run_id,)).fetchone()
            if not owner:
                raise Denied('token')
            tenant = owner['account']
            grant = self._account(db, tenant)       # 계정 행을 먼저 잠근다(open_run 과 같은 순서)
            run = db.execute('SELECT *, deadline > now() AS active FROM hyd_course_runs WHERE id=%s FOR UPDATE', (run_id,)).fetchone()
            if run['todo_id'] != str(todo_id) or run['consumer'] != str(consumer):
                raise Denied('claim_ended')
            if run['state'] != 'OPEN' or not run['active']:
                raise Denied('run_time' if not run['active'] else 'claim_ended')
            amount = dict(calls=1, input_bytes=input_bytes, output_tokens=output_tokens)
            task = self._task_use(db, tenant, run['todo_id'])
            for f in USAGE:
                if run[f] + amount[f] > self.policy['run'][f]:
                    raise Denied('run_limit')
                if task[f] + amount[f] > self.policy['task'][f]:
                    raise Denied('task_limit')
                if grant[f] + amount[f] > self.policy['pc'][f]:
                    raise Denied('pc_limit')
            db.execute('UPDATE hyd_course_runs SET calls=calls+1, input_bytes=input_bytes+%s, output_tokens=output_tokens+%s WHERE id=%s',
                       (input_bytes, output_tokens, run_id))
            db.execute('UPDATE hyd_course_grants SET calls=calls+1, input_bytes=input_bytes+%s, output_tokens=output_tokens+%s WHERE account=%s',
                       (input_bytes, output_tokens, tenant))
