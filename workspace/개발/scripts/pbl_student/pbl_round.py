"""학생 자기 시나리오(지하철 공기 공급 장치 APU 의 공기 누설)를 떠 있는 이 PC 스택에서 학생 API 그대로 밟는 실측 도구.
언제: PBL 단계에서 학생이 자기 현장(유압이 아닌 설비)으로 문서 · 에이전트 · 스킬 · 도구 서버 · 흐름 · 경보를 끝까지 돌리는지 실제 스택으로 잴 때.

모든 명령은 --work <작업 폴더>(git 밖, 보통 작업/<날짜>_<제목>)를 받는다 — 학생 DB 를 <작업 폴더>/데이터/apu.sqlite3 에서 읽고 결과를
<작업 폴더>/실행/ 에 쓴다. 이 폴더의 나머지(흐름 그림 apu_air_leak.bpmn · 포털 요청 본문 pbl_requests.json · 스킬 skills/ · 학생 프로그램 둘)는
저장소에 있다. 학생 문서는 workspace/개발/tests/data/student/APU_공기공급장치_운전정비매뉴얼.md 다.

데이터: MetroPT-3 Dataset(UCI 791, CC BY 4.0 — https://archive.ics.uci.edu/dataset/791/metropt+3+dataset, 압축 약 208 MB)은 저장소에
올리지 않는다. 받아서 학생 DB 를 만든다:
    curl -L -o <작업 폴더>/데이터/metropt3/metropt3.zip https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip
    (압축을 풀어 MetroPT3(AirCompressor).csv) → py build_db.py "<작업 폴더>/데이터/metropt3/MetroPT3(AirCompressor).csv" <작업 폴더>/데이터/apu.sqlite3

    py pbl_round.py scan                    # 감지 규칙으로 데이터 전체를 훑어 발생 · 해제를 회사 고장 보고와 견준다(스택을 쓰지 않음)
    py pbl_round.py check                   # 흐름 그림 · 요청 본문을 서버 코드(파서 · 사전 검사 · 요청 모델)로 이 PC 안에서 확인(스택에는 읽기만)
    py pbl_round.py prepare [--only server,people,manual,flow] [--wait PT12M] [--exclude ID …] [--force-manual]
                                            # PBL 단계 확인 → 도구 서버 등록 · 연결 검사 · 읽기 → 역할 · 스킬 · 에이전트
                                            #   → 매뉴얼(올리기 → AI 추출 → 검토: 새 항목 넣기 → 적재) → 흐름(가져오기 · 사전 검사 · 등록 · 배포)
    py pbl_round.py case <갈래> [--speed N] [--hold approval|wait] [--keep]
    py pbl_round.py resume <갈래>            # --hold 로 멈춰 둔 처리 건을 process 를 다시 켠 뒤 이어서 본다(다시 켜기는 메인이 한다)
    py pbl_round.py branches                # 갈래 전부(다시 켬 제외)를 차례로 — 워커가 실제 AI 방식일 때만
    py pbl_round.py close <처리 건 id> …     # 열린 처리 건 정리

학생 쪽은 이 도구가 띄운다: 도구 서버(apu_server.py — 이 PC 의 루프백이 아닌 주소)와 감지 프로그램(apu_detector.py — 데이터의 정한 시각부터
시계에 맞춰 흘리며 포털 원천 접수 입구로 경보를 보냄). 포털 쪽은 학생이 포털에서 누르는 것과 같은 API 만 부른다(점검 scripts/check_stack.py 의
http · 포트 · 기다리기를 쓴다). 갈래마다 정답 값을 박지 않는다 — 단계마다 서버가 한 일과 까닭을 그대로 찍고, 데이터(학생 DB)의 사실과 견줘
어긋나면 「조용히 틀림?」으로 적는다. 결과는 사람이 읽는 줄로 찍고, 모아 볼 값은 <작업 폴더>/실행/pbl_<명령>[_<갈래>].json 에 남긴다.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
#: 데이터(학생 DB)와 실행 결과를 두는 git 밖 작업 폴더 — main 이 --work 로 정한다(저장소에는 데이터를 올리지 않는다)
WORK = OUT = DB = None
BPMN = HERE / 'apu_air_leak.bpmn'
REQUESTS = HERE / 'pbl_requests.json'
SKILL = HERE / 'skills' / 'apu-leak-diagnosis' / 'SKILL.md'
MANUAL = ROOT / 'workspace' / '개발' / 'tests' / 'data' / 'student' / 'APU_공기공급장치_운전정비매뉴얼.md'
for p in (HERE, ROOT / 'scripts', ROOT / 'common', ROOT / 'it' / 'process'):
    sys.path.insert(0, str(p))
import apu_detector as det        # noqa: E402  — 감지 규칙 · 15분 창(학생 프로그램과 같은 판정)
import check_stack as cs          # noqa: E402  — 점검과 같은 http · 포트 · 기다리기 · 처리 건 읽기
from hydcommon.words import particle  # noqa: E402

PY = sys.executable
ENV = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
PROCESS, WORKER = (f'{cs.H}:{cs.port(ROOT, p)}' for p in (8080, 8097))
FMT = det.FMT
ASSET, FLOW_ID = 'APU-01', 'apu_air_leak'
REQ = json.loads(REQUESTS.read_text(encoding='utf-8'))
SERVER = REQ['server']['name']
ROLE_NAME = REQ['role']['name']
DONE, STOPPED, SUSPECT, SEEN = '됨', '멈춤', '조용히 틀림?', '봄'
STATUS = {'TODO': '대기', 'IN_PROGRESS': '진행', 'SUBMITTED': '제출됨', 'DONE': '끝', 'COMPLETED': '끝', 'PENDING': '멈춤',
          'CANCELLED': '취소', 'FAILED': '실패', 'RUNNING': '진행 중'}
LEAD_NOTE = '효과 확인 값을 보고 차량 기지 입고 때 누설 시험을 다시 잡음(실측 도구가 적음)'
APPROVE, REJECT = '승인', '반려'           # 사람 승인 부품의 결정 값(procsvc.approval_part.APPROVE · REJECT — check 가 같은지 확인한다)

# 갈래: at = 데이터의 어느 경보(scan 이 정한 시각), speed = 데이터 배속, decide = 승인 단계에서 사람이 하는 일
#   recommended 추천 안 승인 · other 추천이 아닌 안 승인 · first 첫 안 승인 · reject 반려(사유 reason)
BRANCHES = {
    'leak-approve': dict(at='leak', speed=20, decide='recommended', clear=True,
                         about='진짜 누설(회사 고장 보고 4번) → 에이전트 판단 → 추천 안 승인 → 정비 기록 → 대기 → 효과 확인 → 결과'),
    'leak-reject': dict(at='leak', speed=20, decide='reject', reason='현장 판단으로 이번에는 정비하지 않음',
                        about='같은 누설을 사람이 반려 → 정비 기록 없이 결과 보고(반려)'),
    # 보고 밖 경보(scan: 2020-03-06 22:45 발생 · 23:30 해제)는 해제가 0.75시간 뒤라, 배속 20이면 해제가 사람의 결정보다 먼저 온다 — 사람 결정을 재는 갈래라 1배
    'false-reject': dict(at='false', speed=1, decide='reject', reason='에이전트 판단을 보고 정비하지 않음',
                         about='감지 규칙이 회사 고장 보고 밖에서 낸 경보 → 에이전트 판단 → 사람 반려'),
    'wrong-false': dict(at='false', speed=1, decide='first',
                        about='틀린 선택: 보고 밖 경보에서 사람이 정비안을 승인 → 정비 기록이 남는가'),
    'wrong-leak': dict(at='leak', speed=20, decide='other',
                       about='틀린 선택: 진짜 누설에서 추천이 아닌 안을 승인 → 승인한 안이 그대로 정비 기록에 가는가'),
    'server-down-ai': dict(at='leak', speed=20, decide='reject', reason='도구 서버가 꺼진 채 낸 판단이라 정비하지 않음', server='down_ai',
                           about='학생 도구 서버를 끈 채 AI 단계 → 까닭을 말하고 멈추는가, 값 없이 판정하는가'),
    'server-down-write': dict(at='leak', speed=20, decide='recommended', server='down_write',
                              about='AI 단계 뒤 도구 서버를 끄고 승인 → 정비 기록 등록이 보내지 못하고 까닭과 멈추는가 → 서버를 켜고 [같은 내용 다시 전달]'),
    'overlap': dict(at='leak', speed=20, decide='recommended', overlap=True, reason='같은 누설의 두 번째 경보 — 앞 처리 건에서 정비함',
                    about='같은 설비에 두 경보: 같은 경보를 다시 보냄 · 두 번째 감지 프로그램이 다른 경보를 보냄'),
    'changed-data': dict(at='other_leak', speed=20, decide='recommended', compare='leak-approve',
                         about='같은 경보 종류 · 다른 시각(회사 고장 보고 2번) → 앞 갈래의 판단을 그대로 내지 않는가'),
    'restart': dict(at='leak', speed=1, decide='recommended', hold='approval',
                    about='승인 대기에서 멈춰 두고 메인이 process 를 다시 켠 뒤 resume 으로 이어서 봄'),
}
ORDER = ('leak-approve', 'leak-reject', 'false-reject', 'wrong-false', 'wrong-leak', 'server-down-ai', 'server-down-write', 'overlap', 'changed-data')


# ---------------------------------------------------------------- 기록
class Stop(Exception):
    """이 단계에서 멈춘다 — reason 은 서버가 말한 까닭(또는 도구가 본 사실)을 그대로."""

    def __init__(self, step: str, reason: str):
        super().__init__(reason)
        self.step, self.reason = step, reason


class Run:
    def __init__(self, name: str):
        self.name, self.steps, self.data = name, [], {}
        print(f'\n== {name}', flush=True)

    def say(self, step: str, outcome: str, text: str, **data):
        print(f'[{step}] {outcome} — {text}', flush=True)
        self.steps.append(dict(at=datetime.now().isoformat(timespec='seconds'), step=step, outcome=outcome, text=text, **data))

    @staticmethod
    def note(text: str):
        print('    ' + text, flush=True)

    def outcome(self) -> str:
        kinds = [s['outcome'] for s in self.steps]
        return SUSPECT if SUSPECT in kinds else STOPPED if STOPPED in kinds else DONE

    def save(self) -> Path:
        OUT.mkdir(exist_ok=True)
        path = OUT / f'pbl_{self.name}.json'
        path.write_text(json.dumps(dict(name=self.name, outcome=self.outcome(), steps=self.steps, **self.data), ensure_ascii=False, indent=1,
                                   default=str), encoding='utf-8')
        print(f'(기록 {path})', flush=True)
        return path


def flat(text, limit=600) -> str:
    text = ' '.join(str(text or '').split())
    return text[:limit] + ('…' if len(text) > limit else '')


# ---------------------------------------------------------------- 포털 API
def api(method: str, path: str, body=None, timeout: float = 60):
    return cs.http(method, PROCESS + path, body, timeout=timeout)


def said(exc: Exception) -> str:
    """서버가 말한 까닭 전부(점검의 ApiError 는 글을 300자로 자르므로 원래 본문을 읽는다)."""
    body = getattr(exc, 'body', None)
    code = getattr(exc, 'code', None)
    head = f'HTTP {code}: ' if code else ''
    if isinstance(body, dict):
        text = body.get('reason') or body.get('detail') or json.dumps(body, ensure_ascii=False)
        problems = body.get('problems') or []
        if problems:
            text += ' / 문제 ' + ' · '.join(problem_text(p) for p in problems)
        return head + flat(text, 2000)
    return head + flat(body if body is not None else exc, 2000)


def problem_text(p: dict) -> str:
    where = p.get('where') or {}
    at = f"{where.get('kind_label') or ''} {where.get('name') or where.get('id') or ''}".strip()
    return f"{at + ': ' if at else ''}{p.get('reason')}"


def person() -> str:
    found = next((u['id'] for u in api('GET', '/api/inbox/users') if str(u.get('id') or '').startswith('user:')), None)
    if not found:
        raise Stop('사람', '업무 DB 에 사람 사용자(user:…)가 없어 누가 했는지 남길 수 없습니다')
    return found


def role_id() -> str:
    found = next((r['endpoint'] for r in api('GET', '/api/flows/catalog')['roles'] if r['name'] == ROLE_NAME), None)
    if not found:
        raise Stop('역할', f'역할 「{ROLE_NAME}」{particle(ROLE_NAME, "이")} 없습니다 — 먼저 prepare 를 돌리세요')
    return found


def fill(value, subs: dict):
    """요청 본문의 자리표($BY 등)를 채운다. 채울 값이 없는 자리표는 그대로 보내지 않고 멈춘다. '_' 로 시작하는 칸(설명)은 빼고 보낸다."""
    if isinstance(value, str) and value.startswith('$'):
        if value not in subs:
            raise Stop('요청 본문', f'{value} 를 채울 값이 없습니다')
        return subs[value]
    if isinstance(value, dict):
        return {k: fill(v, subs) for k, v in value.items() if not k.startswith('_')}
    if isinstance(value, list):
        return [fill(v, subs) for v in value]
    return value


def phase(run: Run, *, need_live: bool = False) -> str:
    """PBL 단계인가(서버의 판정 GET /api/course-access)와 AI 워커의 방식. 돌려줌 = 워커 방식(live · replay · None)."""
    access = api('GET', '/api/course-access')
    try:
        health = cs.http('GET', WORKER + '/health', timeout=5)
    except (cs.CheckError, OSError, urllib.error.URLError) as exc:
        health = {'ai_mode': None, 'error': str(exc)}
    mode = health.get('ai_mode')
    run.data['phase'] = {'phase': access.get('phase'), 'label': access.get('label'), 'expires': access.get('expires'), 'ai_mode': mode}
    if access.get('phase') != 'pbl' or access.get('expired'):
        closed = [v['reason'] for v in (access.get('actions') or {}).values() if not v.get('allowed')]
        closed += list((access.get('reasons') or {}).values())
        raise Stop('PBL 단계', f"지금 단계는 「{access.get('label')}」{'(기한 지남)' if access.get('expired') else ''}입니다 — 서버가 막는 것: "
                              + ' / '.join(closed))
    run.say('PBL 단계', DONE, f"단계 「{access.get('label')}」 · 기한 {access.get('expires') or '없음'} · AI 워커 {mode or '응답 없음'}")
    if need_live and mode != 'live':
        raise Stop('AI 워커', f"AI 워커가 「{mode or '응답 없음'}」 방식입니다 — PBL 의 AI 단계는 실제 AI 로만 돕니다. 갈래 전부를 돌리기 전에 워커를 실제 AI 방식으로 켜세요")
    return mode


def views_of(view: dict) -> tuple[dict, dict]:
    return cs.rows_of(view), cs.variables(view)


# ---------------------------------------------------------------- 학생 시스템(이 PC)
def student_host() -> str:
    """이 PC 의 루프백이 아닌 IPv4 주소 — 포털은 컨테이너 안에서 부르므로 루프백 주소의 학생 서버는 거절한다(mcp_check.address_problem)."""
    found = sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    usable = [a for a in found if not a.startswith('127.')]
    if not usable:
        raise Stop('학생 도구 서버', f'이 PC 에 루프백이 아닌 IPv4 주소가 없습니다({found}) — 포털이 닿을 주소에 도구 서버를 띄울 수 없습니다')
    return usable[0]


def tail(path: Path, n: int = 6) -> str:
    try:
        return ' / '.join(path.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-n:])
    except OSError:
        return '(기록 없음)'


class Student:
    """학생 시스템 자리 — 도구 서버(apu_server.py)와 감지 프로그램(apu_detector.py)을 이 PC 에서 띄우고 끈다.
    출력은 실행/pbl_<이름>_server.log · pbl_<이름>_detector.log."""

    def __init__(self, name: str, host: str, port: int):
        self.name, self.host, self.port = name, host, port
        self.server = self.detector = None
        self.lines: list[str] = []
        self.server_log, self.detector_log = OUT / f'pbl_{name}_server.log', OUT / f'pbl_{name}_detector.log'

    @property
    def url(self) -> str:
        return f'http://{self.host}:{self.port}/mcp'

    def server_up(self, clock: Path) -> None:
        if self.server is not None and self.server.poll() is None:
            return
        for attempt in range(10):                 # 앞 갈래가 끈 서버의 자리가 풀리기를 잠깐 기다린다
            try:
                with socket.socket() as s:
                    s.bind((self.host, self.port))
                break
            except OSError as exc:
                if attempt == 9:
                    raise Stop('학생 도구 서버', f'{self.host}:{self.port} 를 다른 프로그램이 쓰고 있습니다({exc}) — 앞서 띄운 도구 서버를 끄거나 --port 를 바꾸세요') from None
                time.sleep(1)
        OUT.mkdir(exist_ok=True)
        log = open(self.server_log, 'a', encoding='utf-8')
        self.server = subprocess.Popen([PY, str(HERE / 'apu_server.py'), '--db', str(DB), '--clock', str(clock), '--host', self.host,
                                        '--port', str(self.port)], stdout=log, stderr=subprocess.STDOUT, env=ENV, cwd=str(HERE))
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise Stop('학생 도구 서버', f'도구 서버가 뜨지 못하고 끝났습니다(종료 코드 {self.server.returncode}) — {tail(self.server_log)}')
            try:
                with socket.create_connection((self.host, self.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.5)
        raise Stop('학생 도구 서버', f'도구 서버가 40초 안에 {self.host}:{self.port} 에서 열리지 않았습니다 — {tail(self.server_log)}')

    def server_down(self) -> None:
        if self.server is not None and self.server.poll() is None:
            self.server.terminate()
            self.server.wait(15)
        self.server = None

    def detect(self, start: datetime, speed: float, clock: Path, until: datetime, tag: str = '') -> None:
        OUT.mkdir(exist_ok=True)
        self.lines = []
        args = [PY, str(HERE / 'apu_detector.py'), '--db', str(DB), '--portal', PROCESS, '--asset', ASSET, '--start', start.strftime(FMT),
                '--speed', str(speed), '--clock', str(clock), '--until', until.strftime(FMT)] + (['--event-tag', tag] if tag else [])
        self.detector = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ENV, cwd=str(HERE), text=True,
                                         encoding='utf-8', errors='replace')
        log = open(self.detector_log, 'a', encoding='utf-8')
        log.write(f'--- {datetime.now().isoformat(timespec="seconds")} {" ".join(args[2:])}\n')

        def read():
            for line in self.detector.stdout:
                self.lines.append(line.rstrip('\n'))
                log.write(line)
                log.flush()
        threading.Thread(target=read, daemon=True).start()

    def wait_line(self, prefix: str, timeout: float, after: int = 0) -> tuple[int, str] | None:
        """감지 프로그램 출력에서 after 번째 줄 뒤로 prefix 로 시작하는 줄을 기다린다 → (번호, 줄). 프로그램이 먼저 끝나면 None."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for i in range(after, len(self.lines)):
                if self.lines[i].startswith(prefix):
                    return i, self.lines[i]
            if self.detector is None or self.detector.poll() is not None:
                time.sleep(0.5)
                for i in range(after, len(self.lines)):
                    if self.lines[i].startswith(prefix):
                        return i, self.lines[i]
                return None
            time.sleep(0.5)
        raise Stop('감지 프로그램', f'{timeout:.0f}초 안에 「{prefix}」 줄이 나오지 않았습니다 — 마지막 출력: {" / ".join(self.lines[-4:]) or "없음"}')

    def detector_down(self) -> None:
        if self.detector is not None and self.detector.poll() is None:
            self.detector.terminate()
            self.detector.wait(15)
        self.detector = None

    def down(self) -> None:
        self.detector_down()
        self.server_down()


def data_now(clock: Path | None) -> datetime | None:
    """학생 시스템의 「지금」(감지 프로그램이 적은 시계 — 도구 서버와 같은 식)."""
    try:
        c = json.loads(clock.read_text(encoding='utf-8'))
    except (OSError, ValueError, AttributeError):
        return None
    return datetime.strptime(c['data0'], FMT) + timedelta(seconds=(time.time() - float(c['wall0'])) * float(c['speed']))


def stamp(clock: Path | None) -> str:
    t = data_now(clock)
    return f'[데이터 {t:%m-%d %H:%M}]' if t else f'[{datetime.now():%H:%M:%S}]'


# ---------------------------------------------------------------- 데이터(학생 DB — 사실 대조용, 읽기만)
def db() -> sqlite3.Connection:
    if not DB.is_file():
        raise Stop('학생 데이터', f'{DB} 가 없습니다 — 이 폴더의 build_db.py 로 MetroPT-3 CSV 에서 만드세요(머리말 「데이터」)')
    return sqlite3.connect(f'file:{DB}?mode=ro', uri=True)


def reports() -> list[dict]:
    with db() as c:
        return [dict(zip(('no', 'start', 'end', 'failure', 'severity', 'report'), r))
                for r in c.execute('SELECT no, start, end, failure, severity, report FROM failure_reports ORDER BY start')]


def report_at(t: datetime, grace: timedelta = timedelta(0)) -> dict | None:
    """회사 고장 보고 가운데 그 시각을 품는 것(시작 ~ 끝 + grace). 경보 시각을 견줄 때는 grace 1시간(감지는 15분 창이 찬 뒤에 난다)."""
    for r in reports():
        if datetime.strptime(r['start'], FMT) <= t <= datetime.strptime(r['end'], FMT) + grace:
            return r
    return None


def maintenance_rows(case_id: str) -> list[dict]:
    with db() as c:
        return [dict(zip(('id', 'at', 'case_id', 'sop', 'action', 'by'), r))
                for r in c.execute('SELECT id, at, case_id, sop, action, by_whom FROM maintenance_log WHERE case_id = ? ORDER BY id', (case_id,))]


def truth(t: datetime, hours: float = 0.5) -> dict:
    """그 시각까지 hours 시간의 15분 창(도구 서버 apu_windows 와 같은 창)과 감지 규칙의 해제 판정 — 흐름의 「누설 멈춤?」과 견준다."""
    with db() as c:
        ws = det.windows(c, t - timedelta(hours=hours), t)
    return {'windows': ws, 'relieved': bool(ws) and all(map(det.relieved, ws)), 'report': report_at(t)}


def scan(_args) -> dict:
    """감지 규칙(apu_detector.judge)으로 데이터 전체를 15분 창으로 훑는다 → 발생 · 해제 목록과 회사 고장 보고 대조, 갈래가 쓸 시각."""
    run = Run('scan')
    with db() as c:
        first, last = c.execute('SELECT min(ts), max(ts) FROM readings').fetchone()
        k, end = datetime.strptime(first, FMT), datetime.strptime(last, FMT)
        history, opened, events = [], None, []
        while k < end:
            new = det.windows(c, k, min(k + timedelta(days=7), end))
            if not new:
                break
            base = len(history)
            history.extend(new)
            for i in range(base, len(history)):
                got = det.judge(history, i, opened, ASSET)
                if got is None:
                    continue
                state, alert = got
                if state == 'RAISE':
                    opened = alert
                    events.append({'alertId': alert['alertId'], 'raise_at': alert['evidence']['data_time'], 'clear_at': None,
                                   'windows': alert['evidence']['windows']})
                else:
                    events[-1]['clear_at'] = alert['evidence']['data_time']
                    opened = None
            k += det.WINDOW * len(new)
    rows = reports()
    for e in events:
        t = datetime.strptime(e['raise_at'], FMT)
        e['report'] = next((r['no'] for r in rows if datetime.strptime(r['start'], FMT) - timedelta(hours=24) <= t
                            <= datetime.strptime(r['end'], FMT) + timedelta(hours=1)), None)
        e['hours_open'] = round((datetime.strptime(e['clear_at'], FMT) - t).total_seconds() / 3600, 2) if e['clear_at'] else None
        where = f"회사 고장 보고 {e['report']}번 근처" if e['report'] else '회사 고장 보고 밖'
        run.note(f"발생 {e['raise_at']} · 해제 {e['clear_at'] or '없음'}({e['hours_open']}시간) · {where} · {e['alertId']}")
    by_report = {e['report']: e for e in reversed(events) if e['report']}
    outside = [e for e in events if not e['report']]
    short = [e for e in outside if e['hours_open'] is not None and e['hours_open'] <= 3]
    picks = {'leak': by_report.get(4), 'other_leak': by_report.get(2), 'false': (short or outside or [None])[0]}
    for r in rows:
        e = by_report.get(r['no'])
        run.note(f"고장 보고 {r['no']}번 {r['start']} ~ {r['end']}: " + (f"감지 {e['raise_at']}(시작 뒤 {round((datetime.strptime(e['raise_at'], FMT) - datetime.strptime(r['start'], FMT)).total_seconds() / 3600, 2)}시간) · 해제 {e['clear_at']}" if e else '감지 못 함'))
    run.say('훑기', DONE, f"발생 {len(events)}번 — 고장 보고 근처 {len(events) - len(outside)}번 · 보고 밖 {len(outside)}번. 갈래 시각: "
            + ' · '.join(f"{k} {v['raise_at'] if v else '없음'}" for k, v in picks.items()))
    run.data.update(events=events, picks=picks, reports=rows)
    run.save()
    return run.data


def picks() -> dict:
    path = OUT / 'pbl_scan.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else scan(None)
    return data['picks']


# ---------------------------------------------------------------- 처리 건 지켜보기
def view_of(pid: str) -> dict:
    return api('GET', f'/api/instances/{pid}', timeout=30)


def follow(run: Run, pid: str, stop_when, timeout: float, clock: Path | None = None, what: str = '', every: float = 3):
    """처리 건을 timeout 초까지 지켜보며 단계가 바뀔 때마다 · 멈춤 표시가 생길 때마다 찍는다. stop_when(view) 가 값을 내면 (view, 값)."""
    seen, shown, last = {}, set(), None
    deadline = time.monotonic() + timeout
    while True:
        try:
            view = view_of(pid)
        except (cs.ApiError, OSError, urllib.error.URLError) as exc:    # process 가 잠깐 답하지 않음(다시 켜는 중 등) — 다시 묻는다
            view, last = None, exc
        if view is not None:
            for w in sorted(view.get('workitems') or [], key=lambda w: (w.get('generation') or 0, str(w.get('start_date') or ''))):
                mark = (w.get('status'), w.get('draft_status'))
                if seen.get(w['id']) != mark:
                    seen[w['id']] = mark
                    extra = f" (AI 실행 {w['draft_status']})" if w.get('draft_status') in ('FAILED', 'CANCELLED') else ''
                    run.note(f"{stamp(clock)} {w.get('activity_name') or w['activity_id']} — {STATUS.get(w.get('status'), w.get('status'))}{extra}")
            for s in (view.get('attention') or {}).get('steps') or []:
                key = (s.get('workitem'), s.get('kind'), s.get('reason'))
                if key not in shown:
                    shown.add(key)
                    run.note(f"{stamp(clock)} 멈춤 표시 「{s.get('name')}」 {s.get('label')} — {flat(s.get('reason'))}")
            got = stop_when(view)
            if got is not None:
                return view, got
        if time.monotonic() > deadline:
            raise Stop(what or '처리 건', f'{timeout:.0f}초 안에 다음 상태에 닿지 않았습니다' + (f' — 마지막으로 본 오류: {last}' if last else ''))
        time.sleep(every)


def until_approval(view):
    rows = cs.rows_of(view)
    if view['instance']['status'] != 'RUNNING':
        return 'ended'
    if (view.get('attention') or {}).get('steps'):
        return 'stuck'
    if (rows.get('Task_Approve') or {}).get('status') == 'IN_PROGRESS':
        return 'approval'
    return None


def until_after(view):
    rows = cs.rows_of(view)
    if view['instance']['status'] != 'RUNNING':
        return 'ended'
    if (view.get('attention') or {}).get('steps'):
        return 'stuck'
    if (rows.get('Task_LeadCheck') or {}).get('status') == 'IN_PROGRESS':
        return 'lead'
    return None


def until_wait(view):
    got = until_after(view)
    if got is not None:
        return got
    status = (cs.rows_of(view).get('Task_Wait') or {}).get('status')
    # 기다림(타이머) 단계는 시작하면 SUBMITTED(「제출됨」)로 시한을 기다린다 — IN_PROGRESS 만 보면 기다림을 놓치고 끝난 뒤에야 「지나감」으로 본다
    # (2026-11-23 B4-2: Docker 를 다시 켜기 전에 처리 건이 끝까지 가 버림)
    return 'wait' if status in ('IN_PROGRESS', 'SUBMITTED') else 'passed' if status in cs.DONE else None


def stuck_text(view: dict) -> str:
    return ' / '.join(f"「{s.get('name')}」 {s.get('label')}: {flat(s.get('reason'))}" for s in (view.get('attention') or {}).get('steps') or []) \
        or f"처리 건 상태 {view['instance']['status']} · 끝 「{view['instance'].get('end_label')}」"


# ---------------------------------------------------------------- prepare
def prepare(args) -> None:
    run = Run('prepare')
    only = set(args.only.split(',')) if args.only else {'server', 'people', 'manual', 'flow'}
    state_path = OUT / 'pbl_state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.is_file() else {}
    student = Student('prepare', args.host or student_host(), args.port)
    try:
        phase(run)
        by = person()
        subs = {'$BY': by, '$SERVER_URL': student.url, '$WAIT': args.wait, '$SKILL_MD': SKILL.read_text(encoding='utf-8')}
        if (state.get('agent') or {}).get('id'):
            subs['$AGENT_ID'] = state['agent']['id']         # 앞선 prepare 가 만든 에이전트(없으면 단계 설정을 채울 때 그 까닭으로 멈춘다)
        if 'server' in only:
            student.server_up(OUT / 'pbl_clock_prepare.json')   # 시계 파일이 없는 서버 — 「지금」이 필요한 도구는 까닭으로 거절한다(읽기 확인은 고장 보고로)
            state['server'] = prepare_server(run, fill(REQ['server'], subs), by)
        if 'people' in only:
            state.update(prepare_people(run, subs, by))
            subs['$AGENT_ID'] = state['agent']['id']
        if 'manual' in only:
            try:       # 흐름 준비는 매뉴얼 적재와 무관하다 — 적재가 멈춰도 그 까닭을 적고 흐름으로 간다(판단의 근거 지식이 없다는 사실은 AI 단계가 드러낸다)
                state['manual'] = prepare_manual(run, by, args.exclude or [], args.force_manual, args.extract_timeout, args.use_extraction)
            except Stop as stop:
                run.say(stop.step, STOPPED, stop.reason)
                state['manual'] = {'stopped': stop.reason}
        if 'flow' in only:
            state['flow'] = prepare_flow(run, fill(REQ['mapping'], subs), by, fill(REQ['deploy'], subs))
    except Stop as stop:
        run.say(stop.step, STOPPED, stop.reason)
    except cs.CheckError as exc:                  # 예상하지 못한 포털 오류 — 서버가 한 말을 그대로 남긴다
        run.say('포털 응답', STOPPED, said(exc))
    finally:
        student.down()
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf-8')
        run.data['state'] = state
        run.save()


def prepare_server(run: Run, body: dict, by: str) -> dict:
    name = body['name']
    try:
        out = api('POST', '/api/mcp/servers', body, timeout=90)
        gate = out['gate']
        run.say('도구 서버 등록', DONE, f"{name} {body['url']} — 읽기 도구 {gate.get('read_tools')} · 에이전트에게 막힌 도구 {gate.get('blocked_tools')}"
                + (f" · 경고 {out.get('warnings')}" if out.get('warnings') else ''))
    except cs.ApiError as exc:
        if exc.code != 409:
            raise Stop('도구 서버 등록', said(exc)) from None
        listed = next((s for s in api('GET', '/api/mcp/servers')['servers'] if s['name'] == name), {})
        run.say('도구 서버 등록', SEEN, f'이미 있음({said(exc)}) — 지금 주소 {listed.get("url") or "(목록에 주소 없음)"}')
        if listed.get('url') and listed['url'] != body['url']:
            try:
                api('PUT', f'/api/mcp/servers/{name}', body, timeout=90)
                run.say('도구 서버 고치기', DONE, f"주소를 {body['url']} 로")
            except cs.ApiError as exc2:
                raise Stop('도구 서버 고치기', said(exc2)) from None
    try:
        checked = api('POST', f'/api/mcp/servers/{name}/check', {'by': by}, timeout=90)
    except cs.ApiError as exc:
        raise Stop('연결 검사', said(exc)) from None
    record = checked.get('check') or {}
    run.say('연결 검사', DONE if record.get('status') == 'ok' else STOPPED,
            f"결과 {record.get('status')} · 도구 {[t.get('name') for t in record.get('tools') or []]}" + (f" · {flat(record.get('error'))}" if record.get('error') else ''))
    listed = next((s for s in api('GET', '/api/mcp/servers')['servers'] if s['name'] == name), {})
    run.say('에이전트에 붙일 수 있음', DONE if listed.get('selectable') else STOPPED, f"{listed.get('selectable')} {listed.get('reason') or ''}")
    try:
        tried = api('POST', f'/api/mcp/servers/{name}/tools/failure_reports/call', {'arguments': {}, 'by': by}, timeout=60)
    except cs.ApiError as exc:
        raise Stop('읽기 확인', said(exc)) from None
    text = (tried.get('result') or {}).get('text') or ''
    try:
        got = len(json.loads(text)['rows'])
    except (ValueError, KeyError, TypeError):
        got = None
    want = len(reports())
    run.say('읽기 확인', DONE if got == want else SUSPECT, f'포털의 [써 보기]로 회사 고장 보고를 읽음 — {got}건(학생 DB {want}건)')
    return {'name': name, 'url': body['url']}


def prepare_people(run: Run, subs: dict, by: str) -> dict:
    out = {}
    role = fill(REQ['role'], subs)
    try:
        made = api('POST', '/api/roles', role)
        run.say('역할', DONE, f"{made['id']} 「{made['name']}」 구성원 {made.get('members')} · 지식 지도 {made.get('knowledge')}")
        out['role'] = {'id': made['id'], 'name': made['name']}
    except cs.ApiError as exc:
        if exc.code != 409:
            raise Stop('역할', said(exc)) from None
        out['role'] = {'id': role_id(), 'name': ROLE_NAME}
        run.say('역할', SEEN, f'이미 있음 — {said(exc)}')
    skill = fill(REQ['skill'], subs)
    try:
        api('POST', '/api/skills', skill)
        run.say('스킬', DONE, f"{skill['skill_name']} 만듦({len(skill['content'])}자)")
    except cs.ApiError as exc:
        if exc.code != 409:
            raise Stop('스킬', said(exc)) from None
        try:
            api('PUT', f"/api/skills/{skill['skill_name']}", skill)
            run.say('스킬', DONE, f"{skill['skill_name']} 이미 있어 본문을 지금 SKILL.md 로 고침")
        except cs.ApiError as exc2:
            raise Stop('스킬', said(exc2)) from None
    out['skill'] = skill['skill_name']
    agent = {k: v for k, v in fill(REQ['agent'], subs).items()}
    existing = next((a for a in api('GET', '/api/flows/catalog')['agents'] if a['name'] == agent['name']), None)
    try:
        if existing:
            made = api('PUT', f"/api/agents/{existing['id']}", agent)
            run.say('에이전트', DONE, f"{existing['id']} 이미 있어 지금 본문으로 고침 — 도구 {made.get('tools')}")
        else:
            made = api('POST', '/api/agents', agent)
            run.say('에이전트', DONE, f"{made['id']} 「{agent['name']}」 — 도구 {made.get('tools')} · 스킬 {agent['skills']}")
    except cs.ApiError as exc:
        raise Stop('에이전트', said(exc)) from None
    out['agent'] = {'id': (existing or made)['id'], 'name': agent['name']}
    return out


def prepare_manual(run: Run, by: str, exclude: list[str], force: bool, timeout: float, reuse: str | None = None) -> dict:
    """포털 「지식 › 문서 등록」의 길: 올리기 → AI 추출 → 검토(새 항목 제안은 모두 「넣기」, --exclude 는 「제외」) → 바뀌는 것 미리 보기 → 적재."""
    from procsvc.manual_knowledge import NEW_KINDS
    raw = MANUAL.read_bytes()
    loaded = [r for r in api('GET', '/api/kg/manuals') if r.get('current') and r['filename'] == MANUAL.name]
    upload = {'filename': MANUAL.name, 'data': base64.b64encode(raw).decode()}
    if len(loaded) == 1:
        upload['document_id'] = loaded[0]['document_id']           # 화면도 적재된 문서 하나면 그 문서의 개정으로 올린다
    try:
        preview = api('POST', '/api/kg/manuals/preview', upload, timeout=120)
    except cs.ApiError as exc:
        raise Stop('매뉴얼 올리기', said(exc)) from None
    sid = preview['source_id']
    run.say('매뉴얼 올리기', DONE, f"{MANUAL.name} {preview.get('chars')}자 · 원문 {sid}"
            + (f" · 이미 적재된 판 {preview['loaded']['batch'][:8]}(같은 원문 {preview['loaded']['same_source']})" if preview.get('loaded') else ''))
    if preview.get('loaded') and preview['loaded'].get('same_source') and not force:
        run.say('매뉴얼', SEEN, '같은 원문이 이미 적재돼 있어 AI 추출을 다시 하지 않음(다시 하려면 --force-manual)')
        return {'source_id': sid, 'batch': preview['loaded']['batch'], 'skipped': True}
    if reuse:          # 포털 「이전 추출 결과」에서 그 실행을 여는 것과 같다 — 새 AI 추출을 하지 않는다
        started = {'instance': reuse}
        run.say('AI 추출', SEEN, f'이전 추출 결과 {reuse} 를 연다(새 추출 없음)')
    else:
        try:
            started = api('POST', f'/api/kg/manuals/sources/{sid}/extractions', {'request_id': str(uuid.uuid4())}, timeout=120)
        except cs.ApiError as exc:
            raise Stop('AI 추출 시작', said(exc)) from None
        run.say('AI 추출 시작', DONE, f"처리 건 {started['instance']} · 구간 {started.get('segments')}")
    last, deadline = None, time.monotonic() + timeout
    while True:
        try:
            result = api('GET', f"/api/kg/manuals/sources/{sid}/extractions/{started['instance']}", timeout=60)
        except cs.ApiError as exc:
            raise Stop('AI 추출', said(exc)) from None
        mark = (result.get('status'), json.dumps(result.get('progress'), ensure_ascii=False), flat(result.get('log'), 200))
        if mark != last:
            last = mark
            run.note(f"[{datetime.now():%H:%M:%S}] 추출 {result.get('status')} · 진행 {result.get('progress') or '-'} · {mark[2]}")
        if result.get('preview'):
            break
        if result.get('status') in ('FAILED', 'CANCELLED', 'PENDING'):     # PENDING = 교정 세 차례 뒤 사람 확인 필요(엔진이 멈춤) — 기다려도 바뀌지 않는다
            raise Stop('AI 추출', f"추출이 {result['status']} 로 멈췄습니다 — {flat(result.get('log'), 2000)}")
        if time.monotonic() > deadline:
            raise Stop('AI 추출', f'{timeout:.0f}초 안에 추출 결과가 나오지 않았습니다(마지막 상태 {result.get("status")})')
        time.sleep(5)
    pv = result['preview']
    k = pv.get('knowledge') or {}
    v = pv.get('validation') or {}
    run.say('AI 추출', DONE, f"절 {len(pv.get('sections') or [])} · 절차 {len(pv.get('procedures') or [])} · 지식 "
            + ' · '.join(f'{kind} {len(items)}' for kind, items in k.items() if isinstance(items, list))
            + f" · 자동 검증 {'통과' if v.get('technical_ready') else '검토 필요 ' + str(len(v.get('issues') or [])) + '건'}")
    for issue in v.get('issues') or []:
        run.note(f"검증: {issue.get('code')} {issue.get('sop') or ''} — {flat(issue.get('message'), 300)}")
    for w in pv.get('warnings') or []:
        run.note(f'추출 경고: {flat(w, 300)}')
    if not any(k.get(kind) for kind in NEW_KINDS):
        run.say('새 항목 제안', SEEN, '추출이 새 구성 요소 · 증상 · 센서를 제안하지 않았습니다 — 이 설비의 고장 유형이 가리키는 구성 요소가 지금 지식에 없으면 적재가 그 까닭으로 막힙니다')
    reviewed = deepcopy(pv)
    reviewed['procedures'] = [p for p in reviewed['procedures'] if p['id'] not in exclude]
    for kind, items in (reviewed.get('knowledge') or {}).items():
        if isinstance(items, list):
            reviewed['knowledge'][kind] = [dict(i, **({'approved': True} if kind in NEW_KINDS else {})) for i in items if i.get('id') not in exclude]
    # 학생이 검토 화면의 절차 판에서 고르는 것(pbl_requests.json review — 이름으로 적은 고장 유형 · 대상 원인을 이 추출의 id 로)
    choices = (REQ.get('review') or {}).get('procedures') or {}
    known = {i['name']: i['id'] for kind in ('failure_modes', 'causes') for i in (reviewed.get('knowledge') or {}).get(kind) or []}
    for p in reviewed['procedures']:
        pick = choices.get(p['id'])
        if not pick:
            continue
        if pick.get('kind') == 'reference':
            p['link'] = {'kind': 'reference', 'executable': False}
        else:
            missing = [n for n in [pick['failure_mode'], *(pick.get('addresses') or [])] if n not in known]
            if missing:
                raise Stop('매뉴얼 검토', f"{p['id']}: 고르려는 {missing}이 이 추출의 고장 유형 · 원인에 없습니다 — 추출 결과의 이름: {sorted(known)}")
            base = p.get('link') or {}
            p['link'] = dict(base, kind=base.get('kind') or 'work_order', failureMode=known[pick['failure_mode']], relation=pick['relation'],
                             **({'addresses': [known[n] for n in pick['addresses']]} if pick.get('addresses') else {}))
        run.say('검토 선택', DONE, f"{p['id']} {p.get('name')} → {json.dumps(p['link'], ensure_ascii=False)}")
    links = {p['id']: p['link'] for p in reviewed['procedures'] if p.get('link') is not None}
    # 포털 검토 화면이 요청을 만들기 전에 스스로 멈추는 두 곳(hitl.js commitRequest) — 고장 유형 · 관계가 빈 실행 절차(링크가 없는 절차도 실행 절차다)
    blank = [p['id'] for p in reviewed['procedures'] if (p.get('link') or {}).get('kind') != 'reference'
             and (p.get('link') or {}).get('scope') != 'purchase' and not (p.get('link') or {}).get('failureMode')]
    if blank:
        raise Stop('매뉴얼 검토', f"고장 유형을 고르세요: {', '.join(blank)} — 고장 조치가 아닌 확인 · 참고 절차면 종류를 「참고 절차」로 바꾸세요(포털 검토 화면과 같은 멈춤)")
    unrelated = [s for s, l in links.items() if l.get('kind') != 'reference' and l.get('scope') != 'purchase' and not l.get('relation')]
    if unrelated:
        raise Stop('매뉴얼 검토', f"고장 유형과의 관계를 고르세요: {', '.join(unrelated)}(포털 검토 화면과 같은 멈춤)")
    request = dict(reviewed, links=links, by=by, reviewed=True)
    new = {kind: len((reviewed.get('knowledge') or {}).get(kind) or []) for kind in NEW_KINDS}
    try:
        changes = api('POST', '/api/kg/manuals/changes', request, timeout=120)
    except cs.ApiError as exc:
        raise Stop('바뀌는 것 미리 보기', said(exc)) from None
    run.say('바뀌는 것 미리 보기', DONE, f"빠지는 노드 {len(changes.get('removed') or [])} · 넣기를 고른 새 항목 {new}")
    try:
        out = api('POST', '/api/kg/manuals/commit', request, timeout=300)
    except cs.ApiError as exc:
        raise Stop('매뉴얼 적재', said(exc)) from None
    run.say('매뉴얼 적재', DONE, f"판 {out.get('batch')} · 절 {out.get('sections')} · 절차 {out.get('procedures')} · 단계 {out.get('steps')} · "
            f"지식 {json.dumps(out.get('knowledge'), ensure_ascii=False)[:400]}")
    return {'source_id': sid, 'batch': out.get('batch'), 'new_items': new}


def prepare_flow(run: Run, mapping: dict, by: str, deploy: dict) -> dict:
    """포털 「흐름 › 가져오기」의 길: .bpmn 가져오기 → 단계 설정으로 사전 검사 → 판본 등록 → 배포 → 경보 경로표."""
    xml = BPMN.read_text(encoding='utf-8')
    try:
        imported = api('POST', '/api/flows/import', {'xml': xml, 'file_name': REQ['flow']['file_name'], 'definition_id': FLOW_ID}, timeout=60)
    except cs.ApiError as exc:
        raise Stop('흐름 가져오기', said(exc)) from None
    parsed = imported['parsed']
    run.say('흐름 가져오기', DONE if not parsed.get('problems') else STOPPED,
            f"단계 {len(parsed['tasks'])} · 선 {len(parsed['flows'])} · 칸 {[l['name'] for l in parsed['lanes']]} · 그림 문제 {[problem_text(p) for p in parsed.get('problems') or []]}")
    try:
        checked = api('POST', f'/api/flows/{FLOW_ID}/check', {'mapping': mapping}, timeout=60)
    except cs.ApiError as exc:
        raise Stop('흐름 사전 검사', said(exc)) from None
    result = checked['check']
    for dep in (result.get('dependencies') or {}).get('items') or []:
        run.note(f"도구 서버 의존: {dep.get('server')} {dep.get('tool')} — {dep.get('status')} {flat(dep.get('reason') or '', 200)}")
    if not result['ok']:
        raise Stop('흐름 사전 검사', f"{len(result['problems'])}건 — " + ' · '.join(problem_text(p) for p in result['problems']))
    run.say('흐름 사전 검사', DONE, f"통과 · 등록 {checked.get('register')}")
    try:
        made = api('POST', f'/api/flows/{FLOW_ID}/register', {'mapping': mapping, 'by': by}, timeout=60)
    except cs.ApiError as exc:
        raise Stop('판본 등록', said(exc)) from None
    run.say('판본 등록', DONE, f"{FLOW_ID} 판본 {made['version']} 「{made.get('name')}」 · 시작 {made.get('start')}")
    try:
        api('POST', f'/api/process/definitions/{FLOW_ID}/deploy', dict(deploy, version=made['version']), timeout=60)
    except cs.ApiError as exc:
        raise Stop('배포', said(exc)) from None
    route = route_row()
    run.say('배포', DONE if route and route['definition'] == FLOW_ID else STOPPED, f"경보 경로표: {route or '이 경보의 줄이 없습니다'}")
    return {'version': made['version']}


# ---------------------------------------------------------------- 갈래
def route_row() -> dict | None:
    table = api('GET', '/api/flows/deployments')
    return next((r for r in table.get('routes') or [] if r.get('pattern') == det.PATTERN), None)


def require_route(run: Run) -> None:
    """경보를 보내기 전에: 이 경보를 지금 학생 흐름이 여는가(경로표 — 포털 「흐름 배포」 표와 같은 것)."""
    table = api('GET', '/api/flows/deployments')
    row = next((r for r in table.get('routes') or [] if r.get('pattern') == det.PATTERN), None)
    if row is None or row.get('definition') != FLOW_ID:
        fallback = table.get('unsupported') or {}
        names = {d['id']: d.get('name') for d in api('GET', '/api/process/definitions')}
        where = (f"지금 「{row.get('name')}」({row.get('definition')} {row.get('version')})이 엽니다" if row else
                 f"받는 배포 흐름이 없어 「{names.get(fallback.get('definition'), fallback.get('definition'))}」"
                 f"({fallback.get('definition')} {fallback.get('version')})로 갑니다")
        raise Stop('경보 경로', f"경보 {det.PATTERN}({det.NAME})는 {where} — 학생 흐름 {FLOW_ID}이 이 경보를 받지 않아 경보를 보내지 않았습니다. "
                              '흐름 가져오기 · 배포(prepare --only flow)의 멈춤 까닭을 보세요')
    run.say('경보 경로', DONE, f"{det.PATTERN} → {row['source']} 「{row['name']}」 판본 {row['version']}")


def at_of(name: str) -> dict:
    found = picks().get(name)
    if not found:
        raise Stop('데이터 시각', f'scan 이 「{name}」 갈래에 쓸 경보를 데이터에서 찾지 못했습니다 — pbl_scan.json 을 보세요')
    return found


def route_text(reply: dict) -> str:
    """경보 응답이 말한 경로(응답의 route — 배포된 흐름 · 현장 검토). 응답에 없으면 그렇다고 적는다(지어내지 않음)."""
    route = reply.get('route')
    if isinstance(route, dict):
        return f" · 서버: {route.get('text') or route.get('route')}"
    return ' · 응답에 경로(route)가 없음' if route is None else f' · 경로 {route}'


def send_alert(alert: dict) -> tuple[dict | None, str]:
    """학생의 두 번째 감지 프로그램 자리 — 같은 계약의 경보를 원천 접수 입구로 보낸다 → (받았으면 처리 건 행, 서버가 한 말)."""
    try:
        got = api('POST', '/api/instances/start', {'alert': alert}, timeout=120)   # t 는 감지 규칙(det.judge)이 데이터 시각으로 적었다
    except cs.ApiError as exc:
        return None, f'서버가 받지 않음 — {said(exc)}'
    return got, f"받음 — 처리 건 {got.get('proc_inst_id')} · 흐름 {got.get('proc_def_id')} {got.get('proc_def_version')}{route_text(got)}"


def overlap(run: Run, pid: str, alert: dict, raise_at: datetime) -> str | None:
    """같은 설비에 두 경보: ① 같은 경보(같은 alertId)를 다시 보낸다 — 같은 처리 건이거나 거절이어야 하고, 새 처리 건이면 「조용히 틀림?」.
    ② 두 번째 감지 프로그램이 15분 늦은 창으로 같은 규칙의 다른 경보를 보낸다 — 서버가 무엇을 하는지 그대로 찍는다. 돌려줌 = 두 번째 처리 건 id."""
    again, text = send_alert(alert)
    twin = again is not None and again.get('proc_inst_id') not in (None, pid)
    run.say('같은 경보 다시', SUSPECT if twin else DONE, text + (' — 같은 경보로 새 처리 건이 열렸습니다' if twin else ''))
    later = raise_at + det.WINDOW
    with db() as c:
        history = det.windows(c, later - det.WINDOW * det.RAISE_WINDOWS, later)
    # 두 번째 감지 프로그램도 이 실행의 사건 표시를 붙인다 — 붙이지 않으면 앞 실행의 두 번째 경보와 같은 경보 id 가 되어 「이미 받음」만 본다
    got = det.judge(history, len(history) - 1, None, ASSET, f'{run.name}-{uuid.uuid4().hex[:6]}-2')
    if got is None:
        run.say('두 번째 감지 프로그램', SEEN, f'15분 늦은 창({later:%H:%M}까지)으로는 감지 규칙이 경보를 내지 않습니다')
        return None
    inst, text = send_alert(got[1])
    run.say(f"두 번째 감지 프로그램 {got[1]['alertId']}", SEEN, text)
    return inst['proc_inst_id'] if inst and inst.get('proc_inst_id') not in (None, pid) else None


def agent_step(run: Run, view: dict, raise_at: datetime) -> dict:
    """AI 단계 「누설 판단 · 정비 제안」: 판정 · 안 · 추천, 학생 서버 · 지식 지도를 실제로 불렀는가, 회사 고장 보고와 같은가."""
    rows, values = views_of(view)
    w = rows.get('Task_Judge') or {}
    events = (api('GET', f"/api/todolist/{w['id']}").get('events') or []) if w.get('id') else []
    started = [str((e.get('data') or {}).get('tool') or '') for e in events if e.get('event_type') == 'tool_usage_started']
    failed = [str((e.get('data') or {}).get('tool') or '') for e in events if e.get('event_type') == 'tool_usage_finished' and (e.get('data') or {}).get('is_error')]
    student = [t for t in started if t.startswith(f'mcp__{SERVER}__')]
    knowledge = [t for t in started if t.startswith('mcp__neo4j__')]
    proposal = values.get('proposal') if isinstance(values.get('proposal'), dict) else None
    verdict = str((proposal or {}).get('verdict') or '')
    options = (proposal or {}).get('options') if isinstance((proposal or {}).get('options'), list) else []
    out = {'status': w.get('status'), 'tools': started, 'failed': failed, 'proposal': proposal}
    tools = f"도구 호출: 학생 서버 {len(student)}번 {sorted(set(student))} · 지식 지도 {len(knowledge)}번 · 오류 {len(failed)}번 {sorted(set(failed))}"
    if proposal is None:
        run.say('AI 판단', STOPPED, f"정비안(proposal)이 없습니다 — 단계 {STATUS.get(w.get('status'), w.get('status'))} · {stuck_text(view)} · {tools}")
        return out
    rec = proposal.get('recommended')
    run.say('AI 판단', DONE, f"판정 「{verdict}」 · 추천 {rec} · 안 {[(o.get('slot'), o.get('sop'), o.get('title')) for o in options]} · {tools}")
    run.note(f"요약: {flat(proposal.get('summary'), 500)}")
    record = report_at(raise_at, timedelta(hours=1))
    company = f"회사 고장 보고 {record['no']}번({record['start']} ~ {record['end']} 공기 누설)" if record else '회사 고장 보고 밖'
    said_leak = '누설' in verdict and '헛' not in verdict
    if '보류' in verdict:
        against = ' (판단 보류 — 보고와 견주지 않음)'
    elif bool(record) == said_leak:
        against = ' (보고와 같음)'
    else:
        against = ' (보고와 다름)' if record else ' (보고와 다름 — 보고 밖 경보는 보고되지 않은 사건일 수도 있다)'
    run.say('AI 판단 대조', SEEN, f"경보 데이터 시각 {raise_at:%Y-%m-%d %H:%M}은 {company} — 에이전트 판정 「{verdict}」{against}")
    ok_reads = [t for t in student if t not in failed]
    if '보류' not in verdict and not ok_reads:
        run.say('AI 판단', SUSPECT, f'학생 도구 서버 값을 한 번도 읽지 못했는데 판정 「{verdict}」을 냈습니다(지어낸 판단일 수 있음)')
    if '보류' not in verdict and not knowledge:
        run.note('지식 지도(매뉴얼 지식)를 읽지 않고 절차 번호를 냈습니다 — 정비안의 절차 번호를 매뉴얼과 견줘 보세요')
    return out


def decide(run: Run, view: dict, spec: dict, by: str, role: str) -> dict:
    """승인 단계에서 사람이 하는 일(포털 [승인] · [반려]와 같은 요청)."""
    rows, values = views_of(view)
    w = rows['Task_Approve']
    proposal = values.get('proposal') if isinstance(values.get('proposal'), dict) else {}
    options = proposal.get('options') if isinstance(proposal.get('options'), list) else []
    rec = proposal.get('recommended')
    kind = spec['decide']
    if kind == 'reject':
        body = {'decision': REJECT, 'option': None, 'by': by, 'role': role, 'reason': spec['reason']}
    else:
        if kind == 'recommended':
            chosen = next((o for o in options if rec is not None and str(o.get('slot')) == str(rec)), None)
            why = f"에이전트가 추천 안을 내지 않았습니다(판정 「{proposal.get('verdict')}」, 추천 {rec})"
        elif kind == 'other':
            chosen = next((o for o in options if str(o.get('slot')) != str(rec)), None)
            why = f'추천({rec})이 아닌 안이 없습니다 — 안 {[o.get("slot") for o in options]}'
        else:
            chosen = options[0] if options else None
            why = '고를 안이 없습니다'
        if chosen is None:
            raise Stop('정비 승인', why + ' — 이 갈래의 사람 행동을 할 수 없어 여기서 멈춥니다')
        body = {'decision': APPROVE, 'option': chosen.get('slot'), 'by': by, 'role': role, 'reason': f"실측 갈래({kind})"}
    try:
        api('POST', f"/api/todolist/{w['id']}/approve", body, timeout=60)
    except cs.ApiError as exc:
        raise Stop('정비 승인', said(exc)) from None
    picked = next((o for o in options if str(o.get('slot')) == str(body['option'])), {})
    run.say('정비 승인', DONE, f"승인 — 안 {body['option']} {picked.get('sop')} {picked.get('title')}" if body['decision'] == APPROVE
            else f"반려 — {body['reason']}")
    return body


def lead_check(run: Run, view: dict, by: str) -> None:
    w = cs.rows_of(view)['Task_LeadCheck']
    try:
        api('POST', f"/api/todolist/{w['id']}/submit", {'output': {'lead_note': LEAD_NOTE}, 'by': by}, timeout=60)
    except cs.ApiError as exc:
        raise Stop('책임자 확인', said(exc)) from None
    run.say('책임자 확인', DONE, f'제출 — {LEAD_NOTE}')


def effect_retry(run: Run, view: dict, by: str, role: str) -> None:
    """포털 처리 건의 [같은 내용 다시 전달] — 재시도를 다 쓰고 멈춘 승인 뒤 바깥 호출(정비 기록 등록 = 「승인 뒤 MCP 호출」)을 승인한 내용
    그대로 다시 보낸다(instances.retry_effect_step, 승인했던 역할로). 사건이 있는 처리 건에서 그 단계 하나만 [다시 수행]하는 길은 새 판단을
    요구해 막힌다(rework_effects.admit) — 이 갈래가 재는 것은 「도구 서버를 다시 켠 뒤 같은 승인으로 이어지는가」다."""
    step = next((s for s in (view.get('attention') or {}).get('steps') or [] if 'effect_retry' in (s.get('actions') or [])), None)
    if step is None:
        raise Stop('같은 내용 다시 전달', f"멈춘 단계에 [같은 내용 다시 전달]이 없습니다 — {stuck_text(view)}")
    try:
        api('POST', f"/api/todolist/{step['workitem']}/effect-retry", {'by': by, 'role': role}, timeout=60)
    except cs.ApiError as exc:
        raise Stop('같은 내용 다시 전달', said(exc)) from None
    run.say('같은 내용 다시 전달', DONE, f"「{step.get('name')}」 — 승인한 내용 그대로 다시 보냄")


def result(run: Run, pid: str, view: dict, clock: Path | None) -> dict:
    """끝난 처리 건: 끝 · 결과 보고 · 대기 계획 · 효과 확인 값, 그리고 학생 DB 의 사실(정비 기록 · 그 시각의 15분 창)과 대조."""
    rows, values = views_of(view)
    inst = view['instance']
    path = [a for a in ('Task_ReportOk', 'Task_ReportFail', 'Task_ReportRejected') if (rows.get(a) or {}).get('status') in cs.DONE]
    report = values.get('result_report') if isinstance(values.get('result_report'), dict) else {}
    run.say('결과', DONE if inst['status'] == 'COMPLETED' else STOPPED,
            f"끝 「{inst.get('end_label') or STATUS.get(inst['status'], inst['status'])}」 · 결과 보고 {path or '없음'} · {flat(report.get('summary') or report.get('title'), 500)}")
    waited = values.get('waited')
    if isinstance(waited, dict):
        run.note(f"정비 뒤 대기: {json.dumps({k: waited.get(k) for k in ('source', 'virtual_s', 'real_s', 'time_scale', 'compression', 'clock') if k in waited}, ensure_ascii=False)}")
    out = {'status': inst['status'], 'end_label': inst.get('end_label'), 'reports': path, 'report': report,
           'approval': values.get('approval'), 'approved_option': values.get('approved_option'), 'waited': waited}
    written = maintenance_rows(pid)
    out['maintenance_log'] = written
    approved = values.get('approval') == APPROVE
    if approved and len(written) != 1 or not approved and written:
        run.say('정비 기록', SUSPECT, f"승인 {values.get('approval')} 인데 학생 DB 정비 기록이 {len(written)}줄입니다 — {written}")
    else:
        run.say('정비 기록', DONE, f"학생 DB 정비 기록 {len(written)}줄" + (f" — {written[0]['sop']} · {flat(written[0]['action'], 120)} · {written[0]['by']}" if written else ''))
    if values.get('checked_at'):
        t = datetime.strptime(values['checked_at'], FMT)
        fact = truth(t)
        out['effect'] = {k: values.get(k) for k in ('load_prev', 'load_last', 'oil_last', 'checked_at')}
        out['truth'] = fact
        flow_says = 'Task_ReportOk' in path or (rows.get('Task_ReportOk') or {}).get('status') in ('IN_PROGRESS', 'TODO')
        data_says = fact['relieved']
        same = flow_says == data_says
        record = fact['report']
        run.say('효과 확인 대조', DONE if same else SUSPECT,
                f"데이터 시각 {values['checked_at']} · 흐름 값 부하 {values.get('load_prev')} · {values.get('load_last')} · 오일 {values.get('oil_last')} → 흐름 「{'멈춤' if flow_says else '계속'}」"
                f" / 학생 DB 같은 창 {[(w['load_ratio'], w['samples']) for w in fact['windows']]} → 감지 규칙 해제 「{'예' if data_says else '아니요'}」"
                + (f" · 그 시각은 회사 고장 보고 {record['no']}번 안" if record else ' · 그 시각은 회사 고장 보고 밖'))
        run.note('학생 시스템은 기록된 데이터를 흘린다 — 정비 기록이 데이터를 바꾸지 않으므로 효과 확인은 승인한 조치의 효과가 아니라 그 시각의 기록을 잰다')
    return out


def close(run: Run, pid: str, by: str, role: str | None, reason: str = '실측 도구가 연 처리 건 정리') -> None:
    """열린 처리 건을 포털에서 사람이 하듯 닫는다: 승인 대기 = 반려, 책임자 확인 = 제출, 멈춘 단계 = 닫기."""
    try:
        view = view_of(pid)
    except cs.ApiError as exc:
        run.say('정리', STOPPED, f'{pid}: {said(exc)}')
        return
    if view['instance']['status'] != 'RUNNING':
        return
    rows = cs.rows_of(view)
    try:
        if (rows.get('Task_Judge') or {}).get('status') in ('IN_PROGRESS', 'SUBMITTED'):
            # AI 단계가 도는 동안에는 닫을 수 없다 — 그 단계가 끝나거나 보류할 때까지 기다린 뒤 닫는다(부르는 쪽은 학생 도구 서버를 켜 둔 채 부른다.
            # 2026-11-23 겹친 처리 건 갈래: 기다리지 않고 서버를 꺼 두 번째 처리 건이 「설비 데이터 연결을 확인」으로 보류한 채 남았다)
            view = cs.wait_for(900, lambda: (lambda v: v if (cs.rows_of(v).get('Task_Judge') or {}).get('status') not in ('IN_PROGRESS', 'SUBMITTED')
                                             else None)(view_of(pid)), 'AI 단계가 15분 안에 끝나지 않음', every=5)
            if view['instance']['status'] != 'RUNNING':
                run.say('정리', DONE, f"{pid} — 끝 「{view['instance'].get('end_label')}」")
                return
            rows = cs.rows_of(view)
        if (rows.get('Task_Approve') or {}).get('status') == 'IN_PROGRESS':
            api('POST', f"/api/todolist/{rows['Task_Approve']['id']}/approve", {'decision': REJECT, 'option': None, 'by': by,
                                                                                 'role': role or role_id(), 'reason': reason})
        if (rows.get('Task_LeadCheck') or {}).get('status') == 'IN_PROGRESS':
            api('POST', f"/api/todolist/{rows['Task_LeadCheck']['id']}/submit", {'output': {'lead_note': reason}, 'by': by})
        for s in (view.get('attention') or {}).get('steps') or []:
            if 'close' in (s.get('actions') or []):
                api('POST', f"/api/todolist/{s['workitem']}/close", {'by': by, 'reason': reason})
        end = cs.wait_for(180, lambda: (lambda v: v if v['instance']['status'] != 'RUNNING' else None)(view_of(pid)), '닫히지 않음', every=3)
        run.say('정리', DONE, f"{pid} — 끝 「{end['instance'].get('end_label')}」")
    except (cs.CheckError, OSError, urllib.error.URLError) as exc:
        detail = said(exc) if isinstance(exc, cs.ApiError) else str(exc)
        run.say('정리', STOPPED, f'{pid} 를 닫지 못함 — {detail} (AI 단계가 아직 도는 중이면 닫을 수 없다)')


def watch_clear(run: Run, student: Student, clear_at: str | None, clock: Path, speed: float, after: int) -> None:
    """감지 프로그램이 해제(CLEAR)를 보내는 것까지 본다 — 데이터 시각이 해제 시각에 닿을 때까지(15분 넘게 걸리면 기다리지 않음)."""
    if not clear_at or student.detector is None:
        return
    now = data_now(clock)
    wait = ((datetime.strptime(clear_at, FMT) + det.WINDOW - now).total_seconds() / speed) if now else None
    if wait is None or wait > 900:
        run.note(f'해제는 데이터 {clear_at} — 지금 배속으로 {wait and round(wait)}초 뒤라 기다리지 않음')
        return
    got = student.wait_line('해제', max(wait, 0) + 60, after)
    if got is None:
        run.say('해제(CLEAR)', SEEN, f"감지 프로그램이 해제 전에 끝남 — {' / '.join(student.lines[-2:])}")
        return
    answer = student.wait_line('포털 응답', 90, got[0])
    if answer is None:
        run.say('해제(CLEAR)', SEEN, f"포털이 받지 않음 — {student.lines[-1] if student.lines else '(출력 없음)'}")
        return
    try:
        reply = json.loads(answer[1][len('포털 응답'):].strip())
    except ValueError:
        reply = {}
    try:
        cleared_at = (json.loads(got[1][len('해제'):].strip()).get('evidence') or {}).get('data_time')
    except ValueError:
        cleared_at = None
    run.say('해제(CLEAR)', SEEN, f"데이터 {cleared_at or '(시각 모름)'}에 보냄 · 포털이 받음 — {reply.get('text') or flat(answer[1][len('포털 응답'):], 400)}"
            + (f" · 사건 상태 {reply.get('incident_state')}" if reply.get('incident_state') else ''))


def open_case(run: Run, student: Student, spec: dict, at: dict, clock: Path, speed: float) -> tuple[str, dict]:
    """감지 프로그램을 경보 시각부터 흘려 첫 경보를 보내게 하고, 포털이 연 처리 건을 받는다 → (처리 건 id, 경보)."""
    start = datetime.strptime(at['raise_at'], FMT)
    # 같은 기록 데이터를 갈래마다 다른 사건으로 흘린다 — 학생 시스템은 사건마다 새 경보 id 를 쓴다(같은 id 로 다시 보내면 같은 사건)
    student.detect(start, speed, clock, start + timedelta(hours=6), tag=f"{run.name}-{uuid.uuid4().hex[:6]}")
    run.say('감지 프로그램', DONE, f"데이터 {at['raise_at']} 부터 {speed}배로 흘림 · 회사 고장 보고 {at.get('report') or '밖'}")
    raised = student.wait_line('발생', 120)
    if raised is None:
        raise Stop('경보', f"감지 프로그램이 경보 없이 끝났습니다 — {' / '.join(student.lines[-3:])}")
    alert = json.loads(raised[1][len('발생'):].strip())
    answer = student.wait_line('포털 응답', 180, raised[0])
    if answer is None:
        raise Stop('경보', f"포털이 경보를 받지 않았습니다 — {student.lines[-1] if student.lines else '(출력 없음)'}")
    inst = json.loads(answer[1][len('포털 응답'):].strip())
    run.say('경보 → 처리 건', DONE if inst.get('proc_def_id') == FLOW_ID else STOPPED,
            f"{alert['alertId']} → 처리 건 {inst.get('proc_inst_id')} · 흐름 {inst.get('proc_def_id')} {inst.get('proc_def_version')}{route_text(inst)}")
    if inst.get('proc_def_id') != FLOW_ID:
        raise Stop('경보 → 처리 건', f"경보가 학생 흐름이 아니라 {inst.get('proc_def_id')} 로 열렸습니다")
    return inst['proc_inst_id'], alert


def run_case(name: str, args) -> Run:
    spec = BRANCHES[name]
    hold = getattr(args, 'hold', None) or spec.get('hold')
    speed = float(getattr(args, 'speed', None) or spec['speed'])
    run = Run(f'case_{name}')
    run.note(spec['about'])
    clock = OUT / f'pbl_clock_{name}.json'
    student = Student(name, args.host or student_host(), args.port)
    pids, by, role, held = [], None, None, False
    try:
        phase(run)
        by, role = person(), role_id()
        at = at_of(spec['at'])
        require_route(run)
        if spec.get('server') == 'down_ai':
            run.say('학생 도구 서버', SEEN, '띄우지 않음(이 갈래는 서버가 꺼진 채 AI 단계를 본다)')
        else:
            student.server_up(clock)
            run.say('학생 도구 서버', DONE, student.url)
        pid, alert = open_case(run, student, spec, at, clock, speed)
        pids.append(pid)
        second = overlap(run, pid, alert, datetime.strptime(at['raise_at'], FMT)) if spec.get('overlap') else None
        if second:
            pids.append(second)
        view, got = follow(run, pid, until_approval, args.ai_timeout, clock, 'AI 판단')
        judged = agent_step(run, view, datetime.strptime(at['raise_at'], FMT))
        run.data['agent'] = judged
        if got != 'approval':
            raise Stop('AI 판단', f'승인 단계에 닿지 않았습니다 — {stuck_text(view)}')
        if hold == 'approval':
            save_hold(name, pid, clock, speed, at, 'approval', judged, student)
            held = True
            run.say('멈춰 둠', DONE, f'승인 대기에서 멈춰 둠 — 메인이 process 를 다시 켠 뒤 「py pbl_round.py resume {name}」')
            return run
        if spec.get('server') == 'down_write':
            student.server_down()
            run.say('학생 도구 서버', SEEN, '승인 전에 끔(정비 기록 등록이 보내지 못하게)')
        run.data['decision'] = decide(run, view, spec, by, role)
        if hold == 'wait':
            view, got = follow(run, pid, until_wait, args.after_timeout, clock, '정비 뒤 대기')
            if got == 'wait':
                save_hold(name, pid, clock, speed, at, 'wait', judged, student)
                held = True
                run.say('멈춰 둠', DONE, f'정비 뒤 대기 중에 멈춰 둠 — 메인이 process 를 다시 켠 뒤 「py pbl_round.py resume {name}」')
                return run
            run.say('멈춰 둠', STOPPED, f'정비 뒤 대기가 이미 지나 대기 중에 멈춰 둘 수 없었습니다({got})')
        finish(run, pid, by, role, clock, spec, student, args.after_timeout)
        if second:
            view2, got2 = follow(run, second, until_approval, args.ai_timeout, clock, '두 번째 처리 건 AI 판단')
            run.data['agent_second'] = agent_step(run, view2, datetime.strptime(at['raise_at'], FMT) + det.WINDOW)
            if got2 == 'approval':
                decide(run, view2, dict(decide='reject', reason=spec['reason']), by, role)
                view2, _ = follow(run, second, until_after, args.after_timeout, clock, '두 번째 처리 건')
            run.data['result_second'] = result(run, second, view2, clock)
        if spec.get('compare'):
            compare(run, spec['compare'])
        if spec.get('clear'):
            watch_clear(run, student, at.get('clear_at'), clock, speed, 0)
    except Stop as stop:
        run.say(stop.step, STOPPED, stop.reason)
    except cs.CheckError as exc:                  # 예상하지 못한 포털 오류 — 서버가 한 말을 그대로 남긴다
        run.say('포털 응답', STOPPED, said(exc))
    finally:
        if not held:
            student.down()
            if by and not getattr(args, 'keep', False):
                for p in pids:
                    close(run, p, by, role)
        run.data.update(branch=name, pids=pids, speed=speed)
        run.save()
    return run


def finish(run: Run, pid: str, by: str, role: str, clock: Path, spec: dict, student: Student, timeout: float) -> None:
    """승인 뒤 끝까지: 책임자 확인은 제출하고, 도구 서버를 끈 갈래는 멈춘 까닭을 찍고 서버를 켜 [같은 내용 다시 전달]."""
    reworked = False
    while True:
        view, got = follow(run, pid, until_after, timeout, clock, '승인 뒤')
        if got == 'lead':
            lead_check(run, view, by)
            continue
        if got == 'stuck':
            if spec.get('server') == 'down_write' and not reworked:
                run.say('정비 기록 등록', DONE, f'도구 서버가 꺼져 멈춤 — {stuck_text(view)}')
                run.data['stopped_write'] = stuck_text(view)
                student.server_up(clock)
                run.say('학생 도구 서버', DONE, '다시 켬')
                effect_retry(run, view, by, role)
                reworked = True
                continue
            raise Stop('승인 뒤', stuck_text(view))
        run.data['result'] = result(run, pid, view, clock)
        return


def compare(run: Run, other: str) -> None:
    """같은 경보 종류 · 다른 시각: 앞 갈래 기록과 견준다 — 같은 정비안을 그대로 냈거나 이번 단계가 학생 서버를 읽지 않았으면 「조용히 틀림?」."""
    path = OUT / f'pbl_case_{other}.json'
    if not path.is_file():
        run.say('앞 갈래와 견줌', SEEN, f'{path.name} 가 없어 견주지 않음 — 「case {other}」를 먼저 돌리세요')
        return
    before = (json.loads(path.read_text(encoding='utf-8')).get('agent') or {})
    now = run.data.get('agent') or {}
    same = before.get('proposal') is not None and before.get('proposal') == now.get('proposal')
    reads = [t for t in now.get('tools') or [] if t.startswith(f'mcp__{SERVER}__')]
    run.say('앞 갈래와 견줌', SUSPECT if same or not reads else DONE,
            f"정비안 {'같음 — 다른 데이터인데 앞 결과와 똑같은 정비안' if same else '다름'} · 이번 AI 단계의 학생 서버 호출 {len(reads)}번"
            f" · 앞 판정 「{(before.get('proposal') or {}).get('verdict')}」 / 이번 판정 「{(now.get('proposal') or {}).get('verdict')}」")


def save_hold(name, pid, clock, speed, at, kind, judged, student) -> None:
    student.down()       # 학생 프로그램은 끈다 — 시계 파일은 남아 resume 의 도구 서버가 같은 시계로 이어 간다
    (OUT / f'pbl_hold_{name}.json').write_text(json.dumps({'pid': pid, 'clock': str(clock), 'speed': speed, 'at': at, 'kind': kind,
                                                            'agent': judged, 'host': student.host, 'port': student.port},
                                                           ensure_ascii=False, indent=1, default=str), encoding='utf-8')


def resume(name: str, args) -> Run:
    hold_path = OUT / f'pbl_hold_{name}.json'
    run = Run(f'resume_{name}')
    if not hold_path.is_file():
        run.say('이어서 보기', STOPPED, f'{hold_path.name} 가 없습니다 — 「case {name} --hold approval」을 먼저 돌리세요')
        run.save()
        return run
    hold = json.loads(hold_path.read_text(encoding='utf-8'))
    spec, pid, clock = BRANCHES[name], hold['pid'], Path(hold['clock'])
    student = Student(name, hold['host'], hold['port'])
    by = role = None
    try:
        phase(run)
        by, role = person(), role_id()
        view = cs.wait_for(180, lambda: view_of(pid), 'process 가 처리 건을 돌려주지 않음', every=3)
        rows, values = views_of(view)
        waiting = {a: (rows.get(a) or {}).get('status') for a in ('Task_Judge', 'Task_Approve', 'Task_Record', 'Task_Wait', 'Task_Check')}
        same = values.get('proposal') == (hold.get('agent') or {}).get('proposal')
        expect = 'Task_Approve' if hold['kind'] == 'approval' else 'Task_Wait'
        ok = view['instance']['status'] == 'RUNNING' and waiting.get(expect) in ('IN_PROGRESS', 'SUBMITTED', 'DONE')   # 기다림 단계는 SUBMITTED 로 시한을 기다린다
        run.say('다시 켠 뒤', DONE if ok and same else SUSPECT if not same else STOPPED,
                f"처리 건 {view['instance']['status']} · 단계 {waiting} · 정비안 {'멈춰 둔 때와 같음' if same else '바뀜'} · {stuck_text(view) if view.get('attention') else '멈춤 표시 없음'}")
        student.server_up(clock)
        run.say('학생 도구 서버', DONE, f'같은 시계로 다시 켬 — 데이터 {stamp(clock)}')
        if hold['kind'] == 'approval':
            if waiting.get('Task_Approve') != 'IN_PROGRESS':
                raise Stop('정비 승인', f"승인 단계가 기다리지 않습니다({waiting.get('Task_Approve')})")
            run.data['decision'] = decide(run, view, spec, by, role)
        finish(run, pid, by, role, clock, spec, student, args.after_timeout)
    except Stop as stop:
        run.say(stop.step, STOPPED, stop.reason)
    except cs.CheckError as exc:                  # 예상하지 못한 포털 오류 — 서버가 한 말을 그대로 남긴다
        run.say('포털 응답', STOPPED, said(exc))
    finally:
        student.down()
        if by and not getattr(args, 'keep', False):
            close(run, pid, by, role)
        run.data.update(branch=name, pid=pid, hold=hold)
        run.save()
    return run


def branches(args) -> None:
    run = Run('branches')
    try:
        phase(run, need_live=True)
    except (Stop, cs.CheckError) as stop:
        run.say(getattr(stop, 'step', '포털 응답'), STOPPED, getattr(stop, 'reason', None) or said(stop))
        run.save()
        return
    results = []
    for name in ORDER:
        r = run_case(name, args)
        last = next((s for s in reversed(r.steps) if s['outcome'] in (STOPPED, SUSPECT)), r.steps[-1] if r.steps else {})
        results.append({'branch': name, 'outcome': r.outcome(), 'end': (r.data.get('result') or {}).get('end_label'),
                        'note': f"[{last.get('step')}] {last.get('text')}" if last else ''})
    print('\n== 갈래 결과')
    for row in results:
        print(f"{row['branch']:<18} {row['outcome']:<8} 끝 「{row['end']}」 {flat(row['note'], 200)}")
    print('\n다시 켬 갈래는 메인이: py pbl_round.py case restart → (process 다시 켜기) → py pbl_round.py resume restart')
    run.data['results'] = results
    run.save()


# ---------------------------------------------------------------- check (이 PC 안에서 서버 코드로)
def check(args) -> None:
    """흐름 그림 · 요청 본문 · 효과 확인 사슬을 서버 코드로 확인한다. 스택에는 읽기(GET)만 한다 — 부품 목록 · 사람 · 기본 제공 흐름 이름."""
    from fastmcp import Client
    from procsvc import agent_authoring as A, approval_part, bpmn_import, effect_parts, engine, mcp_registry, source_inbox
    from procsvc.agent_authoring_api import AgentReq, RoleReq, SkillReq
    from procsvc.flows_api import ImportReq, MappingReq
    from procsvc.instance_mode import ApproveReq, DeployReq, StartReq, SubmitReq
    from hydcommon import topics
    import apu_server
    run = Run('check')
    try:
        if (APPROVE, REJECT) != (approval_part.APPROVE, approval_part.REJECT):
            raise Stop('결정 값', f'도구의 승인 · 반려 값({APPROVE}, {REJECT})이 서버 부품({approval_part.APPROVE}, {approval_part.REJECT})과 다릅니다')
        xml = BPMN.read_text(encoding='utf-8')
        parsed = bpmn_import.parse_bpmn(xml)
        import xml.etree.ElementTree as ET
        tree = ET.fromstring(xml)
        model = {el.get('id') for el in tree.iter() if el.get('id') and el.tag.startswith('{' + bpmn_import.BPMN_NS + '}')
                 and el.tag.rsplit('}', 1)[1] not in ('definitions', 'process', 'collaboration', 'laneSet', 'messageEventDefinition')}
        drawn = {el.get('bpmnElement') for el in tree.iter() if el.get('bpmnElement')} - {tree.find(f'{{{bpmn_import.BPMN_NS}}}collaboration').get('id')}
        run.say('흐름 그림 좌표', DONE if model == drawn else STOPPED,
                f'그림 요소 {len(model)}개 모두 좌표가 있음' if model == drawn else f'좌표 없는 요소 {sorted(model - drawn)} · 요소 없는 좌표 {sorted(drawn - model)}')
        run.say('흐름 그림 읽기', DONE if not parsed['problems'] else STOPPED,
                f"단계 {len(parsed['tasks'])} · 시작 {[(s['name'], s['definition']) for s in parsed['starts']]} · 끝 {len(parsed['ends'])} · 분기 {len(parsed['gateways'])} · "
                f"선 {len(parsed['flows'])} · 칸 {[(l['name'], len(l['nodes'])) for l in parsed['lanes']]} · 문제 {[problem_text(p) for p in parsed['problems']]}")
        by = person()
        host = args.host or student_host()
        subs = {'$BY': by, '$SERVER_URL': f'http://{host}:{args.port}/mcp', '$AGENT_ID': 'agent:u-check000', '$WAIT': args.wait,
                '$SKILL_MD': SKILL.read_text(encoding='utf-8')}
        bodies = fill(REQ, subs)
        with db() as c:
            history = det.windows(c, datetime.strptime(at_of('leak')['raise_at'], FMT) - det.WINDOW * det.RAISE_WINDOWS,
                                  datetime.strptime(at_of('leak')['raise_at'], FMT))
        state, alert = det.judge(history, len(history) - 1, None, ASSET)
        models = [('역할', lambda: RoleReq(**bodies['role'])), ('스킬', lambda: SkillReq(**bodies['skill'])), ('에이전트', lambda: AgentReq(**bodies['agent'])),
                  ('흐름 가져오기', lambda: ImportReq(xml=xml, **bodies['flow'])), ('단계 설정', lambda: MappingReq(mapping=bodies['mapping'], by=by)),
                  ('배포', lambda: DeployReq(version='1', **bodies['deploy'])), ('경보', lambda: StartReq(alert=dict(alert, t='2026-11-22T00:00:00+00:00'))),
                  ('승인', lambda: ApproveReq(decision=APPROVE, option='A', by=by, role='role:apu-maint-lead')),
                  ('책임자 확인', lambda: SubmitReq(output={'lead_note': LEAD_NOTE}, by=by)),
                  ('역할 칸', lambda: A.role_fields(bodies['role'])), ('스킬 칸', lambda: A.skill_fields(bodies['skill']['skill_name'], bodies['skill'])),
                  ('에이전트 칸', lambda: A.agent_text_fields(bodies['agent'])),
                  ('도구 서버 칸', lambda: (mcp_registry._validate_name(bodies['server']['name']), mcp_registry.entry_from_body(bodies['server'])))]
        for label, make in models:
            try:
                make()
                run.say('요청 본문', DONE, f'{label}: 서버 요청 모델 · 칸 검사 통과')
            except Exception as exc:  # noqa: BLE001 — 어느 검사가 무엇으로 거절했는지 그대로 찍는다
                run.say('요청 본문', STOPPED, f'{label}: {type(exc).__name__} {flat(getattr(exc, "message", None) or getattr(exc, "reason", None) or exc, 400)}')
        rec = source_inbox.source_record(topics.K_ALERTS, None, None, dict(alert, t='2026-11-22T00:00:00+00:00'), source='http')
        clear = source_inbox.source_record(topics.K_ALERTS, None, None, dict(alert, state='CLEAR', t='2026-11-22T00:00:00+00:00'), source='http')
        run.say('경보 계약', DONE if rec['kind'] == 'RAISE' else STOPPED,
                f"감지 프로그램의 경보 {alert['alertId']}(데이터 {alert['evidence']['data_time']}) → 원천 접수 판정 {rec['kind']} · 같은 경보의 해제 → {clear['kind']}"
                ' (HTTP 입구가 해제를 받는지는 case 의 「해제(CLEAR)」 줄이 서버 응답으로 찍는다)')
        cat = api('GET', '/api/flows/catalog')
        table = api('GET', '/api/flows/deployments')
        sim = deepcopy(cat)        # 역할 · 에이전트를 만든 뒤의 부품 목록(만들기는 prepare 가 한다)
        sim['roles'].append({'name': ROLE_NAME, 'endpoint': 'role:' + REQ['role']['key'], 'human': True, 'resolutionRule': 'users 표 역할'})
        sim['agents'].append({'id': 'agent:u-check000', 'name': REQ['agent']['name'], 'goal': REQ['agent']['goal'], 'tools': REQ['agent']['tools']})
        taken = {f['name']: f['definition'] for f in table.get('flows') or [] if f.get('class_flow')}
        taken[table['reference']['name']] = table['reference']['definition']
        ctx = {'catalog': sim, 'definition_id': FLOW_ID, 'version': '1', 'file_name': REQ['flow']['file_name'], 'xml_sha256': bpmn_import.xml_sha256(xml),
               'name': None, 'taken_names': taken}
        checked = bpmn_import.check(parsed, bodies['mapping'], ctx)
        run.say('흐름 사전 검사(지금 서버 코드 · 지금 부품 목록)', DONE if checked['ok'] else STOPPED,
                f"문제 {len(checked['problems'])}건" + ''.join(f' / {problem_text(p)}' for p in checked['problems']))
        human = deepcopy(bodies['mapping'])
        human['start'] = {'kind': 'human', 'fields': [{'key': 'asset', 'text': '설비', 'type': 'text'}, {'key': 'alert', 'text': '경보', 'type': 'object'},
                                                      {'key': 'alert_id', 'text': '경보 id', 'type': 'text'}, {'key': 'pattern', 'text': '경보 종류', 'type': 'text'}]}
        ref = bpmn_import.check(parsed, human, ctx)
        run.say('참고 검사(시작만 사람 입력으로 — 서버에 보내지 않음)', DONE if ref['ok'] else STOPPED,
                f"시작 밖의 단계 설정 · 등록 검사 문제 {len(ref['problems'])}건" + ''.join(f' / {problem_text(p)}' for p in ref['problems']))
        # 효과 확인 사슬: 학생 도구 서버(이 PC 안에서 띄움)의 apu_windows 결과 → 꺼낼 값 → 「누설 멈춤?」 조건 — 누설 중 · 해제 뒤 두 시각
        task = bodies['mapping']['tasks']['Task_Check']['config']
        cond = bodies['mapping']['flows']['Flow_Stopped']['text']
        import tempfile
        for label, t in (('누설 중', datetime.strptime(at_of('leak')['raise_at'], FMT) + timedelta(minutes=30)),
                         ('해제 뒤', datetime.strptime(at_of('leak')['clear_at'], FMT) + timedelta(minutes=15))):
            with tempfile.TemporaryDirectory() as tmp:      # 멈춘 시계(배속 0) — 도구 서버의 「지금」을 그 시각에 둔다
                clock = Path(tmp) / 'clock.json'
                clock.write_text(json.dumps({'wall0': time.time(), 'data0': t.strftime(FMT), 'speed': 0}), encoding='utf-8')

                async def call(app=apu_server.build(str(DB), str(clock))):
                    async with Client(app) as client:
                        return (await client.call_tool(task['tool'], task['arguments'])).structured_content
                got = asyncio.run(call())
            values = effect_parts.extract_values(task['extract'], {'text': json.dumps(got, ensure_ascii=False)})
            stopped = engine.eval_condition(cond, values)
            fact = truth(t)
            run.say('효과 확인 사슬', DONE if stopped == fact['relieved'] else SUSPECT,
                    f"{label}(데이터 {t:%m-%d %H:%M}): 꺼낸 값 {values} → 조건 「{cond}」 {stopped} / 감지 규칙 해제 {fact['relieved']}")
        sample = {'proposal': {'verdict': '공기 누설', 'summary': '-', 'options': [{'slot': 'A', 'title': '누설 시험과 누설 위치 찾기', 'sop': 'SOP-APU-11', 'action': '누설 시험'}],
                               'recommended': 'A', 'losers': []}}
        cfg = bodies['mapping']['tasks']['Task_Approve']['config']
        chosen = approval_part.choose(sample, cfg, 'A')
        args_out = effect_parts.render(bodies['mapping']['tasks']['Task_Record']['config']['arguments'],
                                       dict(sample, approved_option=chosen, approved_by_name='담당자', proc_inst_id=f'{FLOW_ID}.check'))
        run.say('승인 → 정비 기록 인자', DONE, f'고른 안 {chosen} → record_maintenance 인자 {args_out}(idempotency_key 는 process 가 넣는다)')
    except Stop as stop:
        run.say(stop.step, STOPPED, stop.reason)
    except cs.CheckError as exc:                  # 예상하지 못한 포털 오류 — 서버가 한 말을 그대로 남긴다
        run.say('포털 응답', STOPPED, said(exc))
    finally:
        run.save()


# ---------------------------------------------------------------- 명령
def main(argv: list[str]) -> int:
    global WORK, OUT, DB
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('command', choices=('scan', 'check', 'prepare', 'case', 'resume', 'branches', 'close'))
    p.add_argument('--work', required=True, help='git 밖 작업 폴더(작업/<날짜>_<제목>) — 데이터/apu.sqlite3 를 읽고 실행/ 에 결과를 쓴다')
    p.add_argument('names', nargs='*', help='case · resume: 갈래 이름 / close: 처리 건 id')
    p.add_argument('--host', help='학생 도구 서버를 띄울 이 PC 주소(기본: 루프백이 아닌 첫 IPv4)')
    p.add_argument('--port', type=int, default=8711)
    p.add_argument('--only', help='prepare: server,people,manual,flow 가운데 고른 것만')
    p.add_argument('--wait', default='PT12M', help='흐름의 「정비 뒤 대기」 기간(ISO) — prepare · check')
    p.add_argument('--exclude', nargs='*', help='prepare manual: 검토에서 「제외」할 절차 · 지식 id')
    p.add_argument('--use-extraction', help='prepare manual: 새로 추출하지 않고 이 추출 처리 건의 결과로 검토 · 적재')
    p.add_argument('--force-manual', action='store_true', help='prepare manual: 같은 원문이 적재돼 있어도 AI 추출부터 다시')
    p.add_argument('--extract-timeout', type=float, default=3600)
    p.add_argument('--speed', type=float, help='case: 데이터 배속(갈래 기본값 대신)')
    p.add_argument('--hold', choices=('approval', 'wait'), help='case: 그 자리에서 멈춰 두고 resume 을 기다린다')
    p.add_argument('--keep', action='store_true', help='case · resume: 끝나지 않은 처리 건을 닫지 않고 둔다')
    p.add_argument('--ai-timeout', type=float, default=1200, help='AI 판단 단계를 기다리는 초')
    p.add_argument('--after-timeout', type=float, default=1800, help='승인 뒤 끝까지 기다리는 초')
    a = p.parse_args(argv)
    WORK = Path(a.work).resolve()
    if not WORK.is_dir():
        p.error(f'작업 폴더 {WORK} 가 없습니다')
    OUT, DB = WORK / '실행', WORK / '데이터' / 'apu.sqlite3'
    OUT.mkdir(exist_ok=True)
    if a.command == 'scan':
        scan(a)
    elif a.command == 'check':
        check(a)
    elif a.command == 'prepare':
        prepare(a)
    elif a.command == 'branches':
        branches(a)
    elif a.command in ('case', 'resume'):
        unknown = [n for n in a.names if n not in BRANCHES]
        if not a.names or unknown:
            p.error(f"갈래 이름을 적으세요: {', '.join(BRANCHES)}" + (f' (모르는 이름 {unknown})' if unknown else ''))
        for name in a.names:
            (run_case if a.command == 'case' else resume)(name, a)
    elif a.command == 'close':
        run = Run('close')
        by = person()
        for pid in a.names:
            close(run, pid, by, None)
        run.save()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
