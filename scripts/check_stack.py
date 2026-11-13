"""실습 스택이 끝까지 도는지 확인한다 — 시작 5 · 8단계와 점검(setup 의 점검.bat · 점검.command)이 이 파일 하나를 쓴다.

    python scripts/check_stack.py services [--wait 초]   # 시작 5단계: compose 의 모든 서비스가 떴는가 + 포털
    python scripts/check_stack.py ai                     # 시작 8단계: AI 워커가 .env 의 AI_MODE 로 켜졌는가 + 저장 응답(키 없음) / 강의 중계(키 있음)
    python scripts/check_stack.py all                    # 점검: 서비스 → 쿨러 사건 한 바퀴 → 강의 중계(실제로 한 번 묻기)

판정 대상은 손으로 적은 목록이 아니라 compose 가 아는 서비스 전부다(`docker compose config --services`). 계속 도는 서비스는
running + healthy(건강 확인이 없는 선택 도구는 running), 한 번 도는 준비 작업(재시작 정책 no)은 종료 코드 0 이어야 하고, 확인하는 동안
다시 시작한 서비스가 있으면 「재시작 반복」으로 실패다.
쿨러 사건 한 바퀴는 포털 버튼이 부르는 것과 같은 API 로: 설비 초기화 → 쿨러 열화 → 경보 → 처리 건(수업 흐름 c3_cooling) → AI 판단 · 제안 →
추천 카드를 그 승인 역할의 사람으로 승인 → 냉각 명령 → 재관측 → 작업지시 → 결과 보고(정상). 끝에 쿨러를 되돌리고, 점검이 연 처리 건이
열린 채 남으면 거절 · 닫기로 정리한다(데이터는 지우지 않는다).
결과는 통과 · 실패 · 해당 없음(키 없는 PC의 강의 중계처럼 그 PC에서 하지 않는 확인)으로만 쓴다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hyd_env  # noqa: E402
import prepare_ports  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
H = 'http://127.0.0.1'
BY = '실습 스택 점검'                       # 점검이 업무 기록에 남기는 행위자(점검.bat — 설치와 무관)
WHO = {'by': BY, 'user_id': None, 'roles': []}
DONE = {'DONE', 'COMPLETED'}
PASS, FAIL, NA = '통과', '실패', '해당 없음'


class CheckError(RuntimeError):
    """학생이 읽는 실패 까닭."""


class ApiError(CheckError):
    """서비스가 오류로 답했다. reason_code = 응답 detail 의 기계용 칸 code(있으면 — 예: 승인의 review_required)."""
    def __init__(self, code, detail, reason_code=None):
        self.code, self.detail, self.reason_code = code, detail, reason_code
        super().__init__(f'응답 {code}: {detail}')


# ---------------------------------------------------------------- 바깥(명령 · HTTP)
def http(method: str, url: str, body=None, timeout: float = 15):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b'null')
    except urllib.error.HTTPError as exc:
        text, reason_code = exc.read().decode('utf-8', 'replace'), None
        try:
            text = json.loads(text).get('detail', text)
        except (ValueError, AttributeError):
            pass
        if isinstance(text, dict):                      # 구조화된 거절 {"code": …, "reason": 학생 문장}
            reason_code, text = text.get('code'), text.get('reason') or json.dumps(text, ensure_ascii=False)
        raise ApiError(exc.code, str(text)[:300], reason_code) from None


def docker(*args, stdin: bytes | None = None) -> str:
    out = subprocess.run(['docker', *args], input=stdin, capture_output=True, cwd=ROOT)
    if out.returncode != 0:
        raise CheckError(f'docker {" ".join(args[:3])} 실패: {out.stderr.decode("utf-8", "replace").strip()[:300]}')
    return out.stdout.decode('utf-8', 'replace')


# ---------------------------------------------------------------- 서비스
def compose_rows() -> tuple[set[str], list[dict]]:
    expected = set(docker('compose', 'config', '--services').split())
    text = docker('compose', 'ps', '-a', '--format', 'json').strip()
    ps = json.loads(text) if text.startswith('[') else [json.loads(line) for line in text.splitlines() if line.strip()]
    inspected = {}
    if ps:
        for line in docker('inspect', '--format', '{{.Id}}|{{.HostConfig.RestartPolicy.Name}}|{{.RestartCount}}', *[p['ID'] for p in ps]).splitlines():
            cid, policy, count = line.split('|')
            inspected[cid] = (policy, int(count))
    rows = []
    for p in ps:
        policy, count = next((v for cid, v in inspected.items() if cid.startswith(p['ID'])), ('', 0))
        rows.append({'service': p['Service'], 'state': p['State'], 'health': p.get('Health') or '', 'exit_code': int(p.get('ExitCode') or 0),
                     'one_shot': policy == 'no', 'restarts': count})
    return expected, rows


def classify(expected: set[str], rows: list[dict], restarts_before: dict | None = None) -> tuple[list[str], list[str]]:
    """(지금 실패한 것, 아직 기다리는 것) — 모두 비면 다 떴다. restarts_before 는 앞서 「다 떴다」고 본 순간의 재시작 수."""
    by = {r['service']: r for r in rows}
    failed, waiting = [], []
    for name in sorted(expected):
        row = by.get(name)
        if row is None:
            waiting.append(f'{name}: 아직 만들어지지 않음')
            continue
        if row['one_shot']:
            if row['state'] == 'exited' and row['exit_code'] != 0:
                failed.append(f'{name}: 준비 작업이 실패했습니다(종료 코드 {row["exit_code"]})')
            elif row['state'] != 'exited':
                waiting.append(f'{name}: 준비 작업 중')
            continue
        if restarts_before is not None and row['restarts'] > restarts_before.get(name, row['restarts']):
            failed.append(f'{name}: 확인하는 동안 다시 시작했습니다(재시작 반복)')
        elif row['state'] in ('exited', 'dead'):
            failed.append(f'{name}: 멈춤(종료 코드 {row["exit_code"]})')
        elif row['state'] == 'restarting':
            waiting.append(f'{name}: 계속 다시 시작하는 중')
        elif row['state'] != 'running' or row['health'] not in ('healthy', ''):
            waiting.append(f'{name}: {"응답 확인 실패" if row["health"] == "unhealthy" else "켜지는 중"}')
    return failed, waiting


def wait_services(wait: float, *, rows_fn=compose_rows, sleep=time.sleep, clock=time.monotonic, confirm: float = 10) -> list[str]:
    """모두 뜰 때까지 기다린다. 다 떴으면 confirm 초 뒤 한 번 더 보아 그사이 다시 시작한 서비스가 없어야 끝. 실패 목록을 돌려준다."""
    deadline = clock() + wait
    while True:
        expected, rows = rows_fn()
        failed, waiting = classify(expected, rows)
        if not failed and not waiting:
            before = {r['service']: r['restarts'] for r in rows}
            sleep(confirm)
            expected, rows = rows_fn()
            failed, waiting = classify(expected, rows, before)
            if not failed and not waiting:
                return []
        if failed or clock() >= deadline:
            return failed + waiting
        sleep(5)


def port(root: Path, default: int) -> int:
    try:
        return prepare_ports.saved_port(root, default)
    except prepare_ports.PrepareError as exc:
        raise CheckError(str(exc)) from None


PORTAL_PATHS = ('/', '/svc/process/healthz')   # 화면 · 포털을 거쳐 서비스로 가는 같은 출처 길(포털 nginx.conf)


def portal_problems(root: Path) -> list[str]:
    """포털 화면과, 포털을 거쳐 process 에 닿는 같은 출처 길 — 응답하지 않은 주소와 까닭."""
    problems = []
    for path in PORTAL_PATHS:
        url = f'{H}:{port(root, 8088)}{path}'
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status != 200:
                    problems.append(f'포털({url})이 {response.status} 로 응답함')
        except urllib.error.HTTPError as exc:
            problems.append(f'포털({url})이 {exc.code} 로 응답함')
        except (urllib.error.URLError, OSError) as exc:
            problems.append(f'포털({url})이 응답하지 않음({exc})')
    return problems


def check_services(root: Path, wait: float, **kw) -> tuple[str, str]:
    problems = wait_services(wait, **kw)
    problems += portal_problems(root)
    if problems:
        return FAIL, ' · '.join(problems) + ' — 「docker compose ps」와 「docker compose logs <서비스>」로 원인을 보고, 고친 뒤 시작 파일을 다시 실행하세요.'
    return PASS, '모든 서비스 · 포털 응답'


# ---------------------------------------------------------------- AI 단계
def relay(call: bool = False) -> dict:
    """process 컨테이너 안에서 scripts/relay_probe.py 를 돌린다 — process 가 받은 중계 주소 · 키 그대로."""
    command = ['docker', 'compose', 'exec', '-T', 'process', 'python', '-', *(['--call'] if call else [])]
    out = subprocess.run(command, input=(ROOT / 'scripts' / 'relay_probe.py').read_bytes(), capture_output=True, cwd=ROOT)
    lines = out.stdout.decode('utf-8', 'replace').strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, ValueError):            # 확인 자체가 돌지 못했다(process 가 꺼짐 등) — 실패(종료 코드 1)는 위 JSON 으로 온다
        raise CheckError(f'process 안에서 강의 중계 확인을 돌리지 못했습니다: {out.stderr.decode("utf-8", "replace").strip()[:300]}') from None


def check_ai(root: Path, *, call: bool = False, relay_fn=relay, health_fn=None) -> tuple[str, str]:
    want = hyd_env.read(root / '.env').get('AI_MODE', '')
    try:
        health = (health_fn or (lambda: http('GET', f'{H}:{port(root, 8097)}/health', timeout=5)))()
    except (CheckError, urllib.error.URLError, OSError) as exc:
        return FAIL, f'AI 워커가 응답하지 않습니다({exc}). 「docker compose logs agent-worker」로 확인하세요.'
    got = health.get('ai_mode') or ''
    if got != want:
        return FAIL, f'AI 워커가 「{want or "정해지지 않음"}」 대신 「{got or "응답 없음"}」 방식으로 켜졌습니다. 시작 파일을 다시 실행하세요.'
    if want == 'replay':
        saved = health.get('replay_recordings')         # 워커가 켜질 때 실제로 읽은 녹화 수(깨진 녹화면 워커가 켜지지 않는다)
        if not isinstance(saved, int):
            return FAIL, 'AI 워커가 읽은 강사 녹화 수를 알리지 않습니다 — 새 판의 워커가 아닙니다. 시작 파일을 다시 실행하세요.'
        if not saved:
            return FAIL, '강사가 미리 진행한 AI 결과(it/agent-worker/replay/)가 이 판에 없습니다. README 「새 판 받기」대로 새 판을 받으세요. AI 단계가 없는 실습은 그대로 할 수 있습니다.'
        return NA, f'키 없는 수업 — AI 단계는 강사가 저장한 응답 {saved}개를 재생합니다(강의 중계는 부르지 않습니다).'
    try:
        out = relay_fn(call)
    except CheckError as exc:
        return FAIL, str(exc)
    return (PASS if out.get('ok') else FAIL), out.get('message') or json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------- 쿨러 사건 한 바퀴
def rows_of(view: dict) -> dict:
    out = {}
    for w in sorted(view.get('workitems') or [], key=lambda w: (w.get('generation') or 0, str(w.get('start_date') or ''))):
        out[w['activity_id']] = w
    return out


def variables(view: dict) -> dict:
    return {v['key']: v.get('value') for v in (view.get('instance') or {}).get('variables_data') or []}


def agent_outcome(view: dict, ai_mode: str):
    """AI 판단 · 제안 단계가 어디까지 왔나: ('approval', 승인 단계) · 실패면 CheckError · 아직이면 None."""
    rows = rows_of(view)
    agent, approve = rows.get('T_agent') or {}, rows.get('T_approve') or {}
    if approve.get('status') == 'IN_PROGRESS':
        return 'approval', approve
    if agent.get('status') == 'PENDING' and any(e.get('event_type') == 'task_deferred' for e in view.get('events') or []):
        raise CheckError('AI 판단이 보류됐습니다 — 수업용 기본 지식이 없는 것 같습니다. 시작 파일을 다시 실행하세요(7단계가 기본 지식을 넣습니다).')
    if agent.get('status') in ('FAILED', 'ERROR', 'CANCELLED'):
        hint = ('README 「새 판 받기」대로 강사가 저장한 AI 응답이 든 새 판을 받았는지 확인하세요' if ai_mode == 'replay'
                else '.env 의 LLM_API_KEY 와 인터넷 연결을 확인하세요(점검 끝의 「강의 중계」 줄에 까닭이 나옵니다)')
        raise CheckError(f'AI 워커가 판단하지 못했습니다({agent["status"]}): {str(agent.get("log") or "").strip()[:200]} — {hint}')
    return None


def pick_approval(decision: dict, people: list[dict]) -> tuple[str, str, str]:
    """추천 카드(option) · 그 승인 역할 · 그 역할을 가진 사람(이 PC의 담당자) — 포털에서 [승인]을 누르는 것과 같다."""
    option = next((o for o in decision.get('options') or [] if o.get('id') == decision.get('recommended')), None)
    if option is None:
        raise CheckError('AI 판단에 추천 카드가 없습니다 — 포털 「처리 건」에서 판단 · 제안 단계의 기록을 확인하세요.')
    role = (option.get('approver') or {}).get('id')
    person = next((p['id'] for p in people if role in (p.get('roles') or [])), None)
    if not role or not person:
        raise CheckError(f'추천 카드의 승인 역할({role or "없음"})을 가진 사람이 업무 DB에 없습니다 — 시작 파일을 다시 실행하세요.')
    return option['id'], role, person


def flow_result(view: dict) -> tuple[bool, str]:
    rows = rows_of(view)
    status = lambda a: (rows.get(a) or {}).get('status')
    if all(status(a) in DONE for a in ('T_cmd', 'T_reobs', 'T_wo', 'R_ok')):
        ref = (variables(view).get('work_order') or {}).get('ref') if isinstance(variables(view).get('work_order'), dict) else None
        return True, f'승인 → 냉각 명령 → 재관측(정상) → 작업지시{f" {ref}" if ref else ""} → 결과 보고(정상)'
    if all(status(a) in DONE for a in ('T_wo_only', 'T_fix', 'T_reobs_wo', 'R_wo_only')):   # 작업지시만인 카드(흐름 A 승인 뒤 갈래 — chosen_skill_kind)
        ref = (variables(view).get('work_order') or {}).get('ref') if isinstance(variables(view).get('work_order'), dict) else None
        return True, f'승인 → 작업지시{f" {ref}" if ref else ""}(설비 명령 없는 카드) → 정비 수행 → 재관측(정상) → 결과 보고(정상)'
    if status('R_kind') in DONE:
        return False, '승인한 카드에 설비 명령도 작업지시도 없어 냉각 흐름이 실행하지 않았습니다(결과 보고: 실행하지 않음) — 다시 판단해 다른 카드를 고르세요.'
    if status('R_fail') in DONE:
        how = '정비 뒤' if status('T_reobs_wo') in DONE else '냉각 명령 뒤'
        return False, f'승인한 조치({how})의 재관측에서 유온이 기준까지 내려가지 않았습니다(결과 보고: 미달) — 포털 「처리 건」에서 재관측 기록을 확인하세요.'
    steps = ' · '.join(f'{a} {status(a) or "-"}' for a in ('T_approve', 'T_cmd', 'T_reobs', 'T_wo', 'R_ok'))
    return False, f'처리 건이 정상 결과 보고에 닿지 않았습니다({view["instance"]["status"]}: {steps}) — 포털 「처리 건」에서 멈춘 단계를 확인하세요.'


class Timeout(CheckError):
    """기다린 시간 안에 원하는 상태가 오지 않았다 — 그동안 마지막으로 본 오류가 있으면 그 글을 붙인다."""


def wait_for(seconds: float, probe, what: str, sleep=time.sleep, clock=time.monotonic, every: float = 3):
    """probe() 가 None 이 아닌 값을 낼 때까지 기다린다. 서비스가 잠깐 답하지 않는 것(HTTP 오류 · 연결 오류)은 다시 묻고, 시간이 다 되면
    what 에 마지막 오류를 붙여 Timeout 을 낸다. 응답 모양이 다른 것(KeyError · TypeError — 코드 결함)은 잡지 않는다."""
    deadline, last = clock() + seconds, None
    while True:
        try:
            value = probe()
        except (ApiError, urllib.error.URLError, OSError) as exc:
            value, last = None, exc
        if value is not None:
            return value
        if clock() >= deadline:
            raise Timeout(what + (f' — 마지막으로 본 오류: {last}' if last else ''))
        sleep(every)


REVIEW_REQUIRED = 'review_required'             # process 가 「지금 조건으로 새 카드 검토(미리 보기 다시)」를 요구하는 거절 코드


def approve(process: str, task_id: str, body: dict) -> None:
    """포털의 [승인]과 같다: 고르기 → 예측이 낡았다는 거절(코드 review_required)이면 [미리 보기]로 지금 조건을 다시 보고 그 검토로 다시 고른다."""
    try:
        http('POST', f'{process}/api/todolist/{task_id}/select', body, timeout=60)
    except ApiError as exc:
        if exc.reason_code != REVIEW_REQUIRED:
            raise CheckError(f'추천 카드 승인이 거절됐습니다: {exc.detail}') from None
        review = http('POST', f'{process}/api/todolist/{task_id}/decision-preview',
                      {'decision': body['decision'], 'option': body['option'], 'parameters': {}}, timeout=60)
        http('POST', f'{process}/api/todolist/{task_id}/select', dict(body, review_id=review['id']), timeout=60)


def cooler_phase(state: dict) -> str:
    """감지기 상태의 HYD-01 쿨러 성능 저하 패턴 단계(IDLE · RAISED …) — 설비마다 패턴이 여럿이라 패턴별 칸(patterns)을 본다."""
    return state['patterns']['COOLER_DEGRADATION']['phase']


def cooler_round(root: Path, record) -> None:
    process, plant, detector = (f'{H}:{port(root, p)}' for p in (8080, 8000, 8092))
    ai_mode = hyd_env.read(root / '.env').get('AI_MODE', '')
    hyd01 = lambda: http('GET', f'{detector}/api/detector/state')['assets']['HYD-01']
    view = lambda pid: http('GET', f'{process}/api/instances/{pid}')
    pid = None
    approval = None
    try:
        http('POST', f'{plant}/api/reset', {})
        wait_for(120, lambda: (lambda s: s if cooler_phase(s) != 'RAISED' else None)(hyd01()),
                 'HYD-01 경보가 2분이 지나도 풀리지 않습니다. 포털에서 열린 처리 건을 먼저 끝내세요.')
        before = {i['proc_inst_id'] for i in http('GET', f'{process}/api/instances?limit=20')}
        http('POST', f'{process}/api/scenario/A/degrade', WHO)
        raised = wait_for(240, lambda: (lambda s: s if cooler_phase(s) == 'RAISED' else None)(hyd01()),
                          '쿨러 열화를 넣었지만 4분 안에 경보가 나지 않았습니다(감지 서비스 확인).', every=5)
        record('경보', PASS, f'유온 {raised.get("ts1")} ℃ · 냉각 효율 {raised.get("ce")} %')
        found = wait_for(60, lambda: next((i for i in http('GET', f'{process}/api/instances?limit=20') if i['proc_inst_id'] not in before), None),
                         '경보가 났지만 1분 안에 처리 건이 열리지 않았습니다(처리 엔진 확인).')
        pid = found['proc_inst_id']
        if found.get('proc_def_id') != 'c3_cooling':
            raise CheckError(f'처리 건이 수업 흐름이 아닌 {found.get("proc_def_id")} 로 열렸습니다 — 시작 파일을 다시 실행하면 수업 흐름을 배포합니다.')
        record('처리 건 열림', PASS, f'{pid} (수업 흐름 냉각 긴급 대응)')
        outcome = wait_for(420, lambda: agent_outcome(view(pid), ai_mode),
                           '처리 건이 7분 안에 AI 판단 결과(승인 대기)에 닿지 않았습니다 — 포털 「처리 건」에서 판단 · 제안 단계를 확인하세요.', every=5)
        task = outcome[1]
        decision_id = variables(view(pid)).get('decision_id')
        decision = http('GET', f'{process}/api/decisions/{decision_id}')
        option, role, person = pick_approval(decision, http('GET', f'{process}/api/inbox/users'))
        approval = (task['id'], decision_id, role, person)
        record('AI 판단 · 제안', PASS, f'추천 카드 {option} — 승인 대기')
        approve(process, task['id'], {'decision': decision_id, 'option': option, 'by': person, 'role': role, 'reason': f'{BY} — 추천 카드 승인'})
        approval = None
        try:
            end = wait_for(300, lambda: (lambda v: v if v['instance']['status'] != 'RUNNING' else None)(view(pid)), '승인 뒤 5분 안에 끝나지 않음', every=3)
        except Timeout:
            end = view(pid)                              # 끝나지 않은 처리 건 — 아래 판정이 멈춘 단계를 보인다
        ok, detail = flow_result(end)
        record('승인 뒤 실행', PASS if ok else FAIL, detail)
    except (CheckError, urllib.error.URLError, OSError) as exc:
        record('쿨러 사건', FAIL, str(exc))
    finally:
        cleanup(process, plant, pid, approval, view, record)


def cleanup(process, plant, pid, approval, view, record) -> None:
    """쿨러를 되돌리고, 점검이 연 처리 건이 열린 채면 닫는다(승인 대기 = 거절, 보류 = 닫기)."""
    problems = []
    for url, body in ((f'{process}/api/scenario/A/restore', WHO),):
        try:
            http('POST', url, body)
        except (CheckError, urllib.error.URLError, OSError) as exc:
            problems.append(f'쿨러 되돌리기 실패({exc})')
    if pid:
        try:
            current = view(pid)
            if current['instance']['status'] == 'RUNNING':
                rows = rows_of(current)
                if approval and (rows.get('T_approve') or {}).get('status') == 'IN_PROGRESS':
                    task_id, decision_id, role, person = approval
                    http('POST', f'{process}/api/todolist/{task_id}/reject-card',
                         {'decision': decision_id, 'by': person, 'role': role, 'reason': f'{BY}이 연 처리 건 정리'})
                stuck = [w for w in rows.values() if w.get('status') == 'PENDING' and w.get('agent_mode')]
                if stuck:
                    # 닫기는 사람 사용자만 할 수 있다(서버가 점검 이름 같은 글은 거절한다) — 승인 때와 같이 업무 DB 의 사람으로 닫는다
                    closer = approval[3] if approval else next(
                        (p['id'] for p in http('GET', f'{process}/api/inbox/users') if str(p.get('id') or '').startswith('user:')), None)
                    if not closer:
                        raise CheckError('닫을 사람 사용자가 업무 DB에 없습니다')
                    for w in stuck:
                        http('POST', f'{process}/api/todolist/{w["id"]}/close', {'by': closer, 'reason': f'{BY}이 연 처리 건 정리'})
                wait_for(180, lambda: (lambda v: v['instance']['status'] if v['instance']['status'] != 'RUNNING' else None)(view(pid)),
                         f'점검이 연 처리 건 {pid} 이 아직 열려 있습니다 — 포털 「처리 건」에서 닫으세요', every=5)
        except (CheckError, urllib.error.URLError, OSError, KeyError) as exc:
            problems.append(f'처리 건 {pid} 정리 실패({exc})')
    try:
        http('POST', f'{plant}/api/reset', {})
    except (CheckError, urllib.error.URLError, OSError) as exc:
        problems.append(f'설비 초기화 실패({exc})')
    record('점검 정리', FAIL if problems else PASS, ' · '.join(problems) or '쿨러 · 설비를 되돌리고 점검이 연 처리 건을 닫았습니다')


# ---------------------------------------------------------------- 실행
def show(results: list[tuple[str, str, str]]) -> int:
    width = max(len(r[0]) for r in results)
    print('\n== 결과')
    for name, outcome, note in results:
        print(f'{name.ljust(width)}  {outcome:<5}  {note}')
    bad = [r for r in results if r[1] == FAIL]
    print(f'\n실패 {len(bad)}건. 위 실패 줄의 내용을 보고 고친 뒤 다시 점검하세요.' if bad else '\n모두 통과했습니다(「해당 없음」은 이 PC에서 하지 않는 확인입니다).')
    return 1 if bad else 0


def main(argv: list[str], root: Path = ROOT) -> int:
    args = argv[1:]
    try:
        if args[:1] == ['services'] and len(args) in (1, 3) and (len(args) == 1 or (args[1] == '--wait' and args[2].isdigit())):
            outcome, note = check_services(root, float(args[2]) if len(args) == 3 else 180)
            print(f'{outcome}: {note}')
            return 0 if outcome == PASS else 1
        if args == ['ai']:
            outcome, note = check_ai(root)
            print(f'{outcome}: {note}')
            return 1 if outcome == FAIL else 0
        if args == ['all']:
            results: list[tuple[str, str, str]] = []
            record = lambda name, outcome, note: results.append((name, outcome, note))
            print('\n== 실습 스택 점검 (키 없는 PC 실측 약 2분 · 키 있는 PC는 AI 판단이 실제로 돌아 더 걸린다)\n[1/3] 서비스 응답')
            outcome, note = check_services(root, 60)
            record('서비스 · 포털', outcome, note)
            if outcome == PASS:
                print('[2/3] 쿨러 사건 한 바퀴 (기다리는 한도: 경보 4분 · 처리 건 1분 · AI 판단 7분 · 승인 뒤 실행 5분)')
                cooler_round(root, record)
            print('[3/3] 강의 중계')
            record('강의 중계', *check_ai(root, call=True))
            return show(results)
    except (CheckError, hyd_env.EnvFileError) as exc:
        print(f'{FAIL}: {exc}', file=sys.stderr)
        return 1
    print('사용: check_stack.py services [--wait 초] | ai | all', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
