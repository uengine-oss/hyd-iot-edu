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
WHO = {'by': '설치 점검', 'user_id': None, 'roles': []}
DONE = {'DONE', 'COMPLETED'}
PASS, FAIL, NA = '통과', '실패', '해당 없음'


class CheckError(RuntimeError):
    """학생이 읽는 실패 까닭."""


class ApiError(CheckError):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(f'응답 {code}: {detail}')


# ---------------------------------------------------------------- 바깥(명령 · HTTP)
def http(method: str, url: str, body=None, timeout: float = 15):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b'null')
    except urllib.error.HTTPError as exc:
        text = exc.read().decode('utf-8', 'replace')
        try:
            text = json.loads(text).get('detail', text)
        except (ValueError, AttributeError):
            pass
        raise ApiError(exc.code, str(text)[:300]) from None


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


def portal_ok(root: Path) -> bool:
    try:
        with urllib.request.urlopen(f'{H}:{port(root, 8088)}/', timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def check_services(root: Path, wait: float, **kw) -> tuple[str, str]:
    problems = wait_services(wait, **kw)
    if not portal_ok(root):
        problems.append(f'포털({H}:{port(root, 8088)}/)이 응답하지 않음')
    if problems:
        return FAIL, ' · '.join(problems) + ' — 「docker compose ps」와 「docker compose logs <서비스>」로 원인을 보고, 고친 뒤 시작 파일을 다시 실행하세요.'
    return PASS, '모든 서비스 · 포털 응답'


# ---------------------------------------------------------------- AI 단계
def replay_count(root: Path) -> int:
    return len(list((root / 'it' / 'agent-worker' / 'replay').glob('*.json.gz')))


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
        saved = replay_count(root)
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
    """추천 카드(option) · 그 승인 역할 · 그 역할을 가진 첫 사람 — 포털에서 「나」를 그 사람으로 고르고 [승인]을 누르는 것과 같다."""
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
    if status('R_fail') in DONE:
        return False, '승인 뒤 냉각 명령은 나갔지만 재관측에서 유온이 기준까지 내려가지 않았습니다(결과 보고: 미달) — 포털 「처리 건」에서 재관측 기록을 확인하세요.'
    steps = ' · '.join(f'{a} {status(a) or "-"}' for a in ('T_approve', 'T_cmd', 'T_reobs', 'T_wo', 'R_ok'))
    return False, f'처리 건이 정상 결과 보고에 닿지 않았습니다({view["instance"]["status"]}: {steps}) — 포털 「처리 건」에서 멈춘 단계를 확인하세요.'


def wait_for(seconds: float, probe, sleep=time.sleep, clock=time.monotonic, every: float = 3):
    deadline = clock() + seconds
    while True:
        try:
            value = probe()
        except (ApiError, urllib.error.URLError, OSError, KeyError, TypeError):
            value = None
        if value is not None:
            return value
        if clock() >= deadline:
            return None
        sleep(every)


def cooler_round(root: Path, record) -> None:
    process, plant, detector = (f'{H}:{port(root, p)}' for p in (8080, 8000, 8092))
    ai_mode = hyd_env.read(root / '.env').get('AI_MODE', '')
    hyd01 = lambda: http('GET', f'{detector}/api/detector/state')['assets']['HYD-01']
    view = lambda pid: http('GET', f'{process}/api/instances/{pid}')
    pid = None
    approval = None
    try:
        http('POST', f'{plant}/api/reset', {})
        if wait_for(120, lambda: (lambda s: s if s.get('phase') != 'RAISED' else None)(hyd01())) is None:
            raise CheckError('HYD-01 경보가 2분이 지나도 풀리지 않습니다. 포털에서 열린 처리 건을 먼저 끝내세요.')
        before = {i['proc_inst_id'] for i in http('GET', f'{process}/api/instances?limit=20')}
        http('POST', f'{process}/api/scenario/A/degrade', WHO)
        raised = wait_for(240, lambda: (lambda s: s if s.get('phase') == 'RAISED' else None)(hyd01()), every=5)
        if raised is None:
            raise CheckError('쿨러 열화를 넣었지만 4분 안에 경보가 나지 않았습니다(감지 서비스 확인).')
        record('경보', PASS, f'유온 {raised.get("ts1")} ℃ · 냉각 효율 {raised.get("ce")} %')
        found = wait_for(60, lambda: next((i for i in http('GET', f'{process}/api/instances?limit=20') if i['proc_inst_id'] not in before), None))
        if found is None:
            raise CheckError('경보가 났지만 1분 안에 처리 건이 열리지 않았습니다(처리 엔진 확인).')
        pid = found['proc_inst_id']
        if found.get('proc_def_id') != 'c3_cooling':
            raise CheckError(f'처리 건이 수업 흐름이 아닌 {found.get("proc_def_id")} 로 열렸습니다 — 시작 파일을 다시 실행하면 수업 흐름을 배포합니다.')
        record('처리 건 열림', PASS, f'{pid} (수업 흐름 냉각 긴급 대응)')
        outcome = wait_for(420, lambda: agent_outcome(view(pid), ai_mode), every=5)
        if outcome is None:
            raise CheckError('처리 건이 7분 안에 AI 판단 결과(승인 대기)에 닿지 않았습니다 — 포털 「처리 건」에서 판단 · 제안 단계를 확인하세요.')
        task = outcome[1]
        decision_id = variables(view(pid)).get('decision_id')
        decision = http('GET', f'{process}/api/decisions/{decision_id}')
        option, role, person = pick_approval(decision, http('GET', f'{process}/api/inbox/users'))
        approval = (task['id'], decision_id, role, person)
        record('AI 판단 · 제안', PASS, f'추천 카드 {option} — 승인 대기')
        body = {'decision': decision_id, 'option': option, 'by': person, 'role': role, 'reason': '설치 점검 — 추천 카드 승인'}
        try:
            http('POST', f'{process}/api/todolist/{task["id"]}/select', body, timeout=60)
        except ApiError as exc:
            if '새 카드 검토가 필요' not in exc.detail:
                raise CheckError(f'추천 카드 승인이 거절됐습니다: {exc.detail}') from None
            review = http('POST', f'{process}/api/todolist/{task["id"]}/decision-preview', {'decision': decision_id, 'option': option, 'parameters': {}}, timeout=60)
            http('POST', f'{process}/api/todolist/{task["id"]}/select', dict(body, review_id=review['id']), timeout=60)
        approval = None
        end = wait_for(300, lambda: (lambda v: v if v['instance']['status'] != 'RUNNING' else None)(view(pid)), every=3)
        ok, detail = flow_result(end or view(pid))
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
                         {'decision': decision_id, 'by': person, 'role': role, 'reason': '설치 점검이 연 처리 건 정리'})
                for w in rows.values():
                    if w.get('status') == 'PENDING' and w.get('agent_mode'):
                        http('POST', f'{process}/api/todolist/{w["id"]}/close', {'by': '설치 점검', 'reason': '설치 점검이 연 처리 건 정리'})
                closed = wait_for(180, lambda: (lambda v: v['instance']['status'] if v['instance']['status'] != 'RUNNING' else None)(view(pid)), every=5)
                if closed is None:
                    problems.append(f'점검이 연 처리 건 {pid} 이 아직 열려 있습니다 — 포털 「처리 건」에서 닫으세요')
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
            print('\n== 실습 스택 점검 (약 5~10분)\n[1/3] 서비스 응답')
            outcome, note = check_services(root, 60)
            record('서비스 · 포털', outcome, note)
            if outcome == PASS:
                print('[2/3] 쿨러 사건 한 바퀴 (경보까지 1분, AI 판단까지 2~4분, 승인 뒤 실행 1~3분)')
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
