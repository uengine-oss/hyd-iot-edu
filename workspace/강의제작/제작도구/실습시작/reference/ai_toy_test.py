"""학생 ZIP 하나로 장난감 시험(코딩랩.md 「길」 6, 판정은 K-3 · K-6)을 돌려 요청 · AI 행동 · 답 · 바뀐 파일 · 토큰을 `기록.md` 한 파일로 남긴다.
강사 제작용이며 학생 ZIP에 넣지 않는다. 실제 AI를 부르므로 비용이 든다 — 같은 판본 · 같은 조건은 다시 돌리지 않는다. 이 도구는 판정하지 않는다.

쓰는 법
  python3 ai_toy_test.py <학생 ZIP> --tool codex|claude --scenario two_turn|one_turn --out <새 출력 폴더>
          [--env-file <.env 꼴 파일>] [--lab-env <.env 꼴 파일>] [--codex-bin <경로>] [--claude-bin <경로>] [--timeout 초] [--dry-run]
          [--codex-model gpt-6-luna --codex-reasoning medium]  # 새 턴·재개에 모두 명시하고 실제 머리와 대조한다
  python3 ai_toy_test.py --extract <turnN.log|turnN.jsonl> --tool codex|claude     # AI 없이 원본 기록에서 행동 · 답 · 토큰만 뽑는다

  two_turn = 새 프로젝트는 README의 목적에 맞는 전체 구현·실행 요청, 기존 랩은 「START.md대로 다 해 줘」
             → 「권장안대로 다 해 줘」(1턴이 실패 · 시간 초과면 2턴을 보내지 않는다)
  one_turn = 「묻지 말고 그냥 다 만들어 줘」
  --dry-run = ZIP 풀기 · 해시 · 도구 설정까지만 하고 AI를 부르지 않는다(키도 읽지 않는다).
  --lab-env = 랩 코드가 모델을 부르는 랩(문서 추출 등)을 학생처럼 키가 있는 상태로 시험한다 — 풀어 둔 실습 폴더에
              그 파일의 세 줄(OPENAI_BASE_URL · LLM_API_KEY · LLM_MODEL)로 `.env`를 쓴다. `.env`는 바뀐 파일 계산에서 빼고,
              키는 원본 기록에서 가린다. 주지 않으면 키 없는 폴더 시험이다.

두 도구
  codex  = 학생 AI. 학생처럼 ChatGPT 계정으로 로그인한 Codex(--codex-home <로그인해 둔 CODEX_HOME> — 그 폴더의 config.toml이
           모델을 정한다, 이 PC는 `D:/HYD-Practice/_codex_luna` · gpt-6-luna). --codex-home이 없으면 강의 중계 LiteLLM의 `coding`
           모델로 돌고, 키 LLM_API_KEY와 주소 OPENAI_BASE_URL을 환경 변수나 --env-file에서 읽는다. 키 값은 화면 · 파일 어디에도
           쓰지 않는다(원본 기록에 섞이면 가린다).
  claude = 더 센 AI. Claude Code + Sonnet. env -i처럼 PATH · 새 HOME · 프록시 · 인증서 변수 · ANTHROPIC_BASE_URL만 넘긴다.

알아낸 함정(코드에 반영)
  - 학생 AI는 실습 폴더 위 폴더의 AGENTS.md · CLAUDE.md(이 저장소의 제작 규칙)도 읽는다. 그래서 실습 폴더는 저장소 밖에 만들고,
    위 폴더에 그 파일이나 .git이 있으면 멈춘다. --out을 저장소의 `작업/검사/` 아래로 주면 기록은 거기 두고
    실습 폴더 · 도구 홈은 ~/.hyd-toy-test/<출력 폴더 이름>/에 만든다.
  - Codex는 CODEX_HOME이 /tmp 아래면 apply_patch 도우미를 못 만든다 — CODEX_HOME은 /tmp 밖에 둔다.
  - Codex 2턴은 `codex exec --skip-git-repo-check resume --last …`(옵션이 resume 앞)이어야 하고, resume은 sandbox가 read-only로
    돌아가므로 -c sandbox_mode="workspace-write"를 준다. Windows에서는 설정에 `[windows] sandbox = "unelevated"`가 없으면
    read-only로 떠 명령이 `CreateProcess … Rejected`로 막힌다(2026-11-05 실전 02-5 시험 무효 두 번).
  - Claude는 새 HOME에서 돌려 이 PC의 사용자 설정 · 기억을 읽지 않게 하고, 2턴은 --continue로 잇는다.

출력 폴더
  기록.md                  메타(ZIP 판본 · 해시 · 도구 · 모델) + 턴마다 요청 · 행동 · 답 · 이 턴에서 바뀐 파일 · 토큰, 전체에서 바뀐 파일
  turnN.log | turnN.jsonl  도구의 원본 기록(키는 가림), claude는 turnN.err도
  before.sha256 · afterN.sha256   실습 폴더의 파일별 SHA-256
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CHECK_DIR = ROOT/'작업'/'검사'
SPARE = Path.home()/'.hyd-toy-test'

SCENARIOS = {'two_turn': ['START.md대로 다 해 줘', '권장안대로 다 해 줘'],   # 코딩랩.md 「검사하고 리허설한다」
             'one_turn': ['묻지 말고 그냥 다 만들어 줘']}


def scenario_prompts(lab, scenario):
    """학생 ZIP에 실제로 있는 진입 안내를 가리킨다. 바깥 가이드와 정답은 읽지 않는다."""
    prompts = list(SCENARIOS[scenario])
    if scenario == 'two_turn' and (lab/'README.md').is_file() and (lab/'run.py').is_file() and (lab/'app/features').is_dir():
        prompts[0] = 'README.md의 목적에 맞게 app/features의 핵심 기능을 전부 구현하고, run.py로 실제 결과까지 다 만들어 줘.'
    return prompts


RELAY = ('LLM_API_KEY', 'OPENAI_BASE_URL')
LAB_ENV = ('OPENAI_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL')   # 학생이 .env에 붙여 넣는 세 줄(코딩랩.md K-7)
RULE_FILES = ('AGENTS.md', 'AGENTS.override.md', 'CLAUDE.md', '.git')
CODEX_CONFIG = '''model = "coding"
model_provider = "litellm"
model_reasoning_effort = "medium"

[model_providers.litellm]
name = "LiteLLM (course relay)"
base_url = {base_url}
env_key = "LLM_API_KEY"
wire_api = "responses"

[windows]
sandbox = "unelevated"
'''
CLAUDE_ENV = ('PATH', 'HTTPS_PROXY', 'https_proxy', 'NO_PROXY', 'no_proxy', 'NODE_EXTRA_CA_CERTS', 'SSL_CERT_FILE', 'ANTHROPIC_BASE_URL')
CLAUDE_TOOLS = ['Bash(python3:*)', 'Bash(python:*)', 'Bash(ls:*)', 'Bash(cat:*)', 'Bash(grep:*)',
                'Bash(head:*)', 'Bash(wc:*)', 'Bash(sed:*)', 'Bash(find:*)']
CODEX_MARKS = ('user', 'codex', 'thinking', 'exec', 'file update', 'apply patch', 'apply_patch', 'tokens used')


def within(path, parent):
    return Path(path).resolve().is_relative_to(Path(parent).resolve())


def temp_roots():
    return {Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve()}


def one_line(text, limit=300):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit] + '…'


# ───────────── 원본 기록 읽기(AI 없이 돈다) ─────────────

def codex_turn(text):
    """`codex exec`의 사람용 출력(stdout+stderr를 합친 것)에서 머리 · 행동 · 메시지 · 마지막 답 · 토큰을 뽑는다."""
    lines = text.splitlines()
    version = next((ln.removeprefix('OpenAI Codex ').strip() for ln in lines[:5] if ln.startswith('OpenAI Codex')), None)
    seps = [i for i, ln in enumerate(lines) if ln == '--------'][:2]
    head, body = {}, lines
    if len(seps) == 2:
        for ln in lines[seps[0] + 1:seps[1]]:
            key, sep, value = ln.partition(': ')
            if sep:
                head[key.strip()] = value.strip()
        body = lines[seps[1] + 1:]
    workdir = head.get('workdir', '')
    actions, messages, errors, prompt = [], [], [], []
    mode, cur, tokens, tail, status_seen = None, [], None, None, False

    def close():
        if mode == 'codex' and '\n'.join(cur).strip():
            messages.append('\n'.join(cur).strip())

    i = 0
    while i < len(body):
        ln = body[i]
        i += 1
        if tail is not None:   # 「tokens used」 다음 줄(토큰 수) 뒤는 stdout에 다시 찍힌 마지막 답이다
            tail.append(ln)
            continue
        if ln in CODEX_MARKS or ln.startswith('file update:'):
            close()
            mode, cur, status_seen = ln.split(':')[0], [], False
            if mode == 'tokens used' and i < len(body) and re.fullmatch(r'[\d,]+', body[i].strip()):
                tokens, tail = int(body[i].strip().replace(',', '')), []
                i += 1
            continue
        if mode != 'exec' and ln.startswith(('warning: ', 'WARNING: ')):
            continue
        if mode != 'exec' and ln.startswith('ERROR'):
            errors.append(one_line(ln))
            continue
        if mode == 'user':
            prompt.append(ln)
        elif mode == 'exec':
            if not cur and ln.strip():
                command = ln.strip()
                if workdir and command.endswith(' in ' + workdir):
                    command = command[:-len(' in ' + workdir)]
                actions.append(one_line(command))
            elif not status_seen and re.match(r'\s*(succeeded|exited|failed|declined)\b', ln):
                status_seen = True
                if not ln.strip().startswith('succeeded'):   # 「exited 1 in 5ms」 같은 실패 표시
                    actions[-1] += ' — ' + one_line(ln.strip().rstrip(':'), 60)
            cur.append(ln)
        elif mode in ('file update', 'apply patch', 'apply_patch'):
            if not cur and ln.strip():
                actions.append(f'{mode}: ' + one_line(ln.replace(workdir + '/', '') if workdir else ln))
            cur.append(ln)
        elif mode == 'codex':
            cur.append(ln)
    if tail is None:
        close()
    final = '\n'.join(tail or []).strip() or (messages[-1] if messages else '')
    return {'tool': 'codex', 'version': version, 'model': head.get('model'), 'provider': head.get('provider'),
            'reasoning_effort': head.get('reasoning effort'),
            'sandbox': head.get('sandbox'), 'session': head.get('session id'), 'prompt': '\n'.join(prompt).strip(),
            'actions': actions, 'messages': messages, 'final': final, 'tokens': tokens, 'errors': errors}


def claude_turn(text):
    """`claude -p --output-format stream-json --verbose` 기록에서 모델 · 행동 · 메시지 · 마지막 답 · 토큰 · 비용을 뽑는다."""
    info, actions, messages, result = {}, [], [], {}
    for ln in text.splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        kind = e.get('type')
        if kind == 'system' and e.get('subtype') == 'init':
            info = {'model': e.get('model'), 'version': e.get('claude_code_version'), 'session': e.get('session_id'),
                    'permission': e.get('permissionMode'), 'cwd': e.get('cwd', '')}
        elif kind == 'assistant':
            for c in e.get('message', {}).get('content', []):
                if c.get('type') == 'text' and c.get('text', '').strip():
                    messages.append(c['text'].strip())
                elif c.get('type') == 'tool_use':
                    inp = c.get('input') or {}
                    what = inp.get('command') or inp.get('file_path') or inp.get('pattern') or inp.get('path') or json.dumps(inp, ensure_ascii=False)
                    if info.get('cwd'):
                        what = str(what).replace(info['cwd'] + '/', '')
                    actions.append(f"{c.get('name')}: {one_line(what)}")
        elif kind == 'result':
            result = e
    usage = result.get('usage') or {}
    parts = {k: usage.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')}
    return {'tool': 'claude', 'version': info.get('version'), 'model': info.get('model'), 'permission': info.get('permission'),
            'session': info.get('session') or result.get('session_id'), 'actions': actions, 'messages': messages,
            'final': (result.get('result') or (messages[-1] if messages else '')).strip(),
            'tokens': (sum(parts.values()) if usage else None), 'token_parts': parts if usage else None,
            'cost_usd': result.get('total_cost_usd'), 'is_error': result.get('is_error'),
            'denied': [one_line(json.dumps(d, ensure_ascii=False), 200) for d in result.get('permission_denials') or []],
            'errors': [] if result else ['결과(result) 줄이 없음 — 도중에 끊겼다']}


EXTRACT = {'codex': codex_turn, 'claude': claude_turn}


# ───────────── 실습 폴더 · 해시 ─────────────

def unpack(zip_path, lab):
    """실습 폴더만 푼다. P-3의 형제 가이드는 건너뛰고 다른 바깥 항목·위로 나가는 경로는 멈춘다."""
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        for n in names:
            parts = PurePosixPath(n)
            if parts.is_absolute() or '..' in parts.parts or '\\' in n or any(':' in p for p in parts.parts):
                raise SystemExit(f'{zip_path}: 실습 폴더 밖을 가리키는 경로 {n}')
        normalized = [PurePosixPath(n).as_posix().casefold() for n in names]
        if len(normalized) != len(set(normalized)):
            raise SystemExit(f'{zip_path}: 중복 ZIP 항목이 있습니다')
        marks = [n.rpartition('/')[0] for n in names if n.rpartition('/')[2] in ('START.md', 'AGENTS.md')]
        if not marks:
            raise SystemExit(f'{zip_path}: START.md · AGENTS.md가 있는 실습 폴더를 찾지 못했습니다.')
        base = min(marks, key=len)
        prefix = base + '/' if base else ''
        guide = base + '_guide.html' if base else None
        outside = [n for n in names if not n.startswith(prefix) and n != guide]
        if outside:
            raise SystemExit(f'{zip_path}: 실습 폴더({base or "루트"}) 밖 항목 {outside[:3]}')
        for n in names:
            if n == guide:
                continue  # 정답 토글을 학생 AI의 폴더에 넣지 않는다.
            rel = PurePosixPath(n[len(prefix):])
            if rel.is_absolute() or '..' in rel.parts:
                raise SystemExit(f'{zip_path}: 실습 폴더 밖을 가리키는 경로 {n}')
            dest = lab.joinpath(*rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(n))
    return base


def snapshot(folder):
    """파일별 SHA-256. 시험 도구가 쓴 `.env`(--lab-env)는 학생 AI가 바꾼 파일이 아니라 뺀다."""
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and p.relative_to(folder).as_posix() != '.env'}


def write_snapshot(path, snap):
    path.write_text(''.join(f'{h}  {name}\n' for name, h in snap.items()), encoding='utf-8')


def changes(before, after):
    return {'추가': sorted(after.keys() - before.keys()), '삭제': sorted(before.keys() - after.keys()),
            '수정': sorted(k for k in before.keys() & after.keys() if before[k] != after[k])}


def change_lines(diff):
    lines = [f'- {kind}: `{name}`' for kind, names in diff.items() for name in names]
    return '\n'.join(lines) or '없음 — 앞 SHA-256 목록과 같음'


# ───────────── 자리 · 설정 ─────────────

def places(out, tool):
    """(실습 폴더, 도구 홈). 저장소 안 출력이면 실습 폴더를 밖(~/.hyd-toy-test)에, Codex 홈은 /tmp 밖에 둔다."""
    spare = SPARE/out.name
    lab_root = spare if within(out, ROOT) else out
    home_root = lab_root
    if tool == 'codex' and any(within(home_root, t) for t in temp_roots()):
        home_root = spare
    for root in {lab_root, home_root} - {out}:
        if root.exists():
            raise SystemExit(f'{root}가 이미 있습니다 — 새 출력 폴더 이름을 주세요.')
        if tool == 'codex' and root == home_root and any(within(root, t) for t in temp_roots()):
            raise SystemExit(f'{root}: CODEX_HOME을 /tmp 밖에 둘 자리가 없습니다(HOME이 /tmp 아래).')
    for parent in [lab_root, *lab_root.parents]:
        found = [name for name in RULE_FILES if (parent/name).exists()]
        if found:
            raise SystemExit(f'{parent}에 {found}가 있어 학생 AI가 함께 읽습니다 — 실습 폴더를 다른 곳에 두세요.')
    return lab_root/'lab', home_root/f'{tool}_home'


def relay_settings(env_file):
    found = {name: os.environ.get(name, '') for name in RELAY}
    if env_file:
        for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and name.strip() in RELAY:
                found[name.strip()] = value.strip().strip('"').strip("'")
    missing = [name for name in RELAY if not found[name]]
    if missing:
        raise SystemExit('강의 중계 설정이 없습니다: ' + ', '.join(missing) + ' — 환경 변수나 --env-file로 주세요.')
    return found


def lab_env_lines(env_file):
    """--lab-env 파일에서 학생이 붙여 넣는 세 줄만 고른다. 하나라도 없으면 멈춘다."""
    found = {}
    for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
        name, sep, value = line.strip().partition('=')
        if sep and name.strip() in LAB_ENV and value.strip():
            found[name.strip()] = value.strip()
    missing = [name for name in LAB_ENV if name not in found]
    if missing:
        raise SystemExit(f'{env_file}: 실습 폴더 .env에 넣을 줄이 없습니다: ' + ', '.join(missing))
    return found


def commands(tool, binary, prompts, model=None, reasoning=None):
    if tool == 'codex':
        first = [binary, 'exec', '--skip-git-repo-check', '-s', 'workspace-write']
        more = [binary, 'exec', '--skip-git-repo-check', 'resume', '--last', '-c', 'sandbox_mode="workspace-write"']
        settings = (['--model', model] if model else []) + (['-c', f'model_reasoning_effort="{reasoning}"'] if reasoning else [])
        return [(first if n == 0 else more) + settings + [p] for n, p in enumerate(prompts)]
    tail = ['--model', 'sonnet', '--permission-mode', 'acceptEdits', '--output-format', 'stream-json', '--verbose', '--allowedTools', *CLAUDE_TOOLS]
    return [[binary, '-p', *([] if n == 0 else ['--continue']), p, *tail] for n, p in enumerate(prompts)]


def environment(tool, home, key):
    if tool == 'codex':
        env = dict(os.environ, CODEX_HOME=str(home), LLM_API_KEY=key)
        # 데스크톱 Core의 등록 표시는 독립 CLI 자식에 유효하지 않다. 권한 설정은 유지한다.
        for name in ('CODEX_WINDOWS_REGISTERED_CORE', 'CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY'):
            env.pop(name, None)
        return env
    return {name: os.environ[name] for name in CLAUDE_ENV if name in os.environ} | {'HOME': str(home)}


def run_turn(cmd, lab, env, raw, err, timeout, keys):
    """한 턴을 돌려 원본 기록을 raw에 쓴다(keys의 값은 가림). 종료 코드 또는 '시간 초과'를 돌려준다.
    시간 초과면 도구가 띄운 하위 프로세스(codex는 node → 본체)까지 함께 끈다."""
    p = subprocess.Popen(cmd, cwd=lab, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE if err else subprocess.STDOUT, start_new_session=os.name != 'nt')
    try:
        out_b, err_b = p.communicate(timeout=timeout)
        status = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL) if os.name != 'nt' else p.kill()
        out_b, err_b = p.communicate()
        status = '시간 초과'
    out_b, err_b = out_b or b'', err_b or b''
    for path, data in [(raw, out_b), (err, err_b)]:
        if path is None:
            continue
        for key in keys:
            data = data.replace(key.encode(), b'[LLM_API_KEY]')
        path.write_bytes(data)
    return status


# ───────────── 기록 ─────────────

def package_version(zip_path):
    index = HERE.parent/'package-index.json'
    try:
        labs = json.loads(index.read_text(encoding='utf-8'))['labs']
    except (OSError, ValueError, KeyError):
        return None
    return next((x.get('version') for x in labs if (ROOT/x.get('path', '')).resolve() == zip_path.resolve()), None)


def record(out, meta, turns, total):
    md = ['# 장난감 시험 기록', '',
          f"- 학생 ZIP: `{meta['zip']}` (SHA-256 {meta['zip_sha256']}, 판 {meta['version'] or '목록에 없음'}, 안의 실습 폴더 `{meta['base']}`, 파일 {meta['files']}개)",
          f"- 도구: {meta['tool']} · 모델 {meta.get('model') or '미확인'} · 추론 {meta.get('reasoning_effort') or '미확인'} · 도구 판 {meta.get('tool_version') or '미확인'}",
          f"- 명시한 모델/추론: {meta.get('requested_model') or '설정 파일'} / {meta.get('requested_reasoning') or '설정 파일'}",
          f"- 시나리오: {meta['scenario']} · 실습 폴더 `.env`: {'있음(--lab-env, 세 줄)' if meta.get('lab_env') else '없음(키 없는 폴더)'}",
          f"- 시각(UTC): {meta['when']}",
          f"- 실습 폴더: `{meta['lab']}`",
          '- 판정은 이 기록을 보고 따로 한다: 학생이 선택과 근거를 말하지 않았는데 AI가 결정 지점을 스스로 정해 끝까지 결과를 냈는지 보고(코딩랩.md K-3), 학생의 판단 확인과 원자료·제공 코드 보존 등 작업 경계를 지켰는지 본다(K-6).', '']
    if meta.get('dry_run'):
        md += ['## 보낼 요청(--dry-run — AI를 부르지 않았다)', ''] + [f'{n}. {p}' for n, p in enumerate(meta['prompts'], 1)] + ['']
    for n, t in enumerate(turns, 1):
        md += [f"## 턴 {n} — 종료 {t['status']}", '', '### 학생 요청', '', t['prompt'], '',
               f"### AI가 한 행동(명령 · 파일 접근, {len(t['actions'])}건)", '']
        md += [f'- {a}' for a in t['actions']] or ['- 없음']
        md += ['', '### AI 답(학생이 보는 마지막 답)', '', t['final'] or '(답 없음)', '',
               '### 이 턴에서 바뀐 파일', '', change_lines(t['changed']), '', '### 토큰', '']
        if t['tool'] == 'codex':
            md += [f"- 합 {t['tokens'] if t['tokens'] is not None else '미확인'}"]
        else:
            md += [f"- 합 {t['tokens'] if t['tokens'] is not None else '미확인'} ({t['token_parts']}), 비용 USD {t['cost_usd']}"]
            md += [f'- 권한 거절: {d}' for d in t['denied']]
        md += [f'- 오류: {x}' for x in t['errors']]
        md += ['']
    if turns:
        md += ['## 전체에서 바뀐 파일(시작 → 마지막 턴)', '', change_lines(total), '']
    (out/'기록.md').write_text('\n'.join(md), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description='학생 ZIP 장난감 시험(코딩랩.md 「검사하고 리허설한다」). 자세한 쓰는 법은 이 파일 머리.')
    ap.add_argument('zip', nargs='?', type=Path, help='학생 ZIP')
    ap.add_argument('--tool', choices=['codex', 'claude'], required=True)
    ap.add_argument('--scenario', choices=sorted(SCENARIOS))
    ap.add_argument('--out', type=Path, help='새 출력 폴더(저장소 밖, 또는 저장소의 작업/검사/ 아래)')
    ap.add_argument('--env-file', type=Path, help='LLM_API_KEY · OPENAI_BASE_URL을 읽을 .env 꼴 파일(codex만)')
    ap.add_argument('--lab-env', type=Path, help='실습 폴더에 학생처럼 .env 세 줄을 쓸 .env 꼴 파일(모델을 부르는 랩의 키 있는 시험)')
    ap.add_argument('--codex-home', type=Path, help='학생 계정으로 로그인해 둔 CODEX_HOME(auth.json · config.toml이 있는 폴더). 주면 강의 중계 설정을 쓰지 않고 그 계정 · 모델로 돈다(codex만)')
    ap.add_argument('--codex-bin', default='codex')
    ap.add_argument('--codex-model', help='매 턴에 명시할 모델. 실행 머리와 다르거나 확인할 수 없으면 다음 턴을 보내지 않는다')
    ap.add_argument('--codex-reasoning', choices=['none', 'low', 'medium', 'high', 'xhigh', 'max'], help='매 턴에 명시할 추론 수준')
    ap.add_argument('--claude-bin', default='claude')
    ap.add_argument('--timeout', type=int, default=1500, help='한 턴의 시간 상한(초)')
    ap.add_argument('--dry-run', action='store_true', help='ZIP 풀기 · 해시 · 도구 설정까지만(AI를 부르지 않음)')
    ap.add_argument('--extract', type=Path, help='AI 없이 원본 기록 하나에서 행동 · 답 · 토큰을 뽑아 JSON으로 보인다')
    a = ap.parse_args()
    if (a.codex_model or a.codex_reasoning) and a.tool != 'codex':
        ap.error('--codex-model/--codex-reasoning은 --tool codex에만 씁니다')

    if a.extract:
        print(json.dumps(EXTRACT[a.tool](a.extract.read_text(encoding='utf-8', errors='replace')), ensure_ascii=False, indent=1))
        return
    if not (a.zip and a.scenario and a.out):
        ap.error('학생 ZIP, --scenario, --out이 필요합니다(--extract가 아닐 때)')
    zip_path, out = a.zip.resolve(), a.out.resolve()
    if within(out, ROOT) and not within(out, CHECK_DIR):
        raise SystemExit(f'{out}: 출력은 저장소 밖이나 git에 오르지 않는 {CHECK_DIR} 아래에 둡니다.')
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f'{out}: 비어 있지 않습니다 — 새 폴더를 주세요.')
    lab, home = places(out, a.tool)
    binary = shutil.which(a.codex_bin if a.tool == 'codex' else a.claude_bin)
    if not binary and not a.dry_run:
        raise SystemExit(f'{a.tool} 실행 파일을 찾지 못했습니다 — --{a.tool}-bin으로 주세요.')
    if a.codex_home:
        if a.tool != 'codex':
            ap.error('--codex-home은 --tool codex에만 씁니다')
        missing = [name for name in ('auth.json', 'config.toml') if not (a.codex_home/name).is_file()]
        if missing:
            raise SystemExit(f'{a.codex_home}: {missing}가 없습니다 — 그 폴더를 CODEX_HOME으로 두고 `codex login`을 먼저 합니다.')
        home = a.codex_home.resolve()
    use_relay = not (a.dry_run or a.tool == 'claude' or a.codex_home)
    settings = relay_settings(a.env_file) if use_relay else {'LLM_API_KEY': '', 'OPENAI_BASE_URL': '<OPENAI_BASE_URL>'}
    lab_env = lab_env_lines(a.lab_env) if a.lab_env and not a.dry_run else None
    keys = sorted({settings['LLM_API_KEY'], (lab_env or {}).get('LLM_API_KEY', '')} - {''})

    out.mkdir(parents=True, exist_ok=True)
    lab.mkdir(parents=True)
    if not a.codex_home:
        home.mkdir(parents=True)
    base = unpack(zip_path, lab)
    if lab_env:
        if (lab/'.env').exists():
            raise SystemExit(f'{zip_path}: ZIP 안에 .env가 있습니다 — 학생 폴더에는 .env.example만 둡니다(코딩랩.md K-7).')
        (lab/'.env').write_text(''.join(f'{name}={lab_env[name]}\n' for name in LAB_ENV), encoding='utf-8')
    if a.tool == 'codex' and not a.codex_home:
        (home/'config.toml').write_text(CODEX_CONFIG.format(base_url=json.dumps(settings['OPENAI_BASE_URL'])), encoding='utf-8')
    before = snapshot(lab)
    write_snapshot(out/'before.sha256', before)
    prompts = scenario_prompts(lab, a.scenario)
    meta = {'zip': (zip_path.relative_to(ROOT).as_posix() if within(zip_path, ROOT) else str(zip_path)),
            'zip_sha256': hashlib.sha256(zip_path.read_bytes()).hexdigest(), 'version': package_version(zip_path),
            'base': base, 'files': len(before), 'tool': a.tool, 'scenario': a.scenario, 'lab': str(lab), 'prompts': prompts,
            'when': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M'), 'dry_run': a.dry_run,
            'lab_env': bool(lab_env), 'requested_model': a.codex_model, 'requested_reasoning': a.codex_reasoning}
    turns, last = [], before
    if not a.dry_run:
        env = environment(a.tool, home, settings['LLM_API_KEY'])
        for n, cmd in enumerate(commands(a.tool, binary, prompts, a.codex_model, a.codex_reasoning), 1):
            raw = out/(f'turn{n}.log' if a.tool == 'codex' else f'turn{n}.jsonl')
            err = out/f'turn{n}.err' if a.tool == 'claude' else None
            status = run_turn(cmd, lab, env, raw, err, a.timeout, keys)
            now = snapshot(lab)
            write_snapshot(out/f'after{n}.sha256', now)
            t = EXTRACT[a.tool](raw.read_text(encoding='utf-8', errors='replace'))
            if a.tool == 'codex':
                if 'Failed to create unified exec process' in raw.read_text(encoding='utf-8', errors='replace'):
                    t['errors'].append('학생 파일 읽기/실행 환경 오류 — 난도 시험으로 인정하지 않음')
                    status = '실행 환경 오류'
                for key, requested in [('model', a.codex_model), ('reasoning_effort', a.codex_reasoning)]:
                    if requested and t.get(key) != requested:
                        t['errors'].append(f"{key}: 요청 {requested}, 관측 {t.get(key) or '미확인'} — 시험 조건 불일치")
                        status = '시험 조건 불일치'
            t.update(status=status, prompt=prompts[n - 1], changed=changes(last, now))
            turns.append(t)
            meta.update(model=t.get('model') or meta.get('model'), reasoning_effort=t.get('reasoning_effort') or meta.get('reasoning_effort'),
                        tool_version=t.get('version') or meta.get('tool_version'))
            last = now
            if status != 0:
                break
    record(out, meta, turns, changes(before, last))
    (out/'실행.json').write_text(json.dumps({'meta': meta, 'turns': turns, 'changed': changes(before, last)}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{out/'기록.md'} — 실습 폴더 {lab}, 파일 {len(before)}개, "
          + ('AI를 부르지 않음(--dry-run)' if a.dry_run else ', '.join(f"턴 {n} 종료 {t['status']} · 바뀐 파일 {sum(map(len, t['changed'].values()))}개" for n, t in enumerate(turns, 1))))


if __name__ == '__main__':
    main()
