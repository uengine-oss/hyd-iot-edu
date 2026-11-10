"""언제: 키 없는 랩의 요청 글을 실제 Codex 계정 채팅에 보내고 학생의 --paste 경로를 검증할 때.

제작용이며 학생 ZIP에 넣지 않는다. 수업 API 호출로 기록하지 않는다. 실제 계정 호출의
원문·응답·모델·추론·토큰을 보관하고, 그 응답 바이트를 학생 실행 진입점의 --paste에 넘긴다.
인증 내용과 .env를 열지 않는다. 랩에 .env가 있으면 이 경로는 사용하지 않는다.
python account_chat.py <랩 폴더> <요청 해시> --out <새 시험 기록 루트>
    --codex-home D:/HYD-Practice/_codex_luna --codex-bin <절대 경로>
    --model gpt-6-luna --reasoning medium --max-calls 24 --timeout 180
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

from ai_toy_test import ROOT, SPARE, RULE_FILES


def json_events(raw):
    """모델의 답 안에 든 글자와 CLI 이벤트를 구별한다. 낯선 항목도 무도구로 인정하지 않는다."""
    result = {'thread_id': None, 'actions': [], 'errors': [], 'tokens': None, 'completed': False}
    for line in raw.decode('utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            result['errors'].append('JSON 이벤트가 아닌 stdout')
            continue
        kind = event.get('type')
        if kind == 'thread.started':
            identity = event.get('thread_id', '')
            if not re.fullmatch(r'[a-f0-9-]{36}', identity) or result['thread_id']:
                result['errors'].append('세션 식별자 누락/중복')
            result['thread_id'] = identity
        elif kind in ('item.started', 'item.updated', 'item.completed'):
            item = event.get('item', {})
            if item.get('type') not in ('reasoning', 'agent_message'):
                result['actions'].append({'id': item.get('id'), 'type': item.get('type')})
        elif kind == 'turn.completed':
            usage = event.get('usage', {})
            result['usage'] = usage
            result['tokens'] = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            result['completed'] = True
        elif kind in ('error', 'turn.failed'):
            result['errors'].append(event)
        elif kind != 'turn.started':
            result['errors'].append('확인되지 않은 이벤트: ' + str(kind))
    return result


def turn_settings(home, identity):
    """방금 생성한 세션만 찾고 turn_context의 모델·추론 두 값만 반환한다."""
    if not identity or not re.fullmatch(r'[a-f0-9-]{36}', identity):
        raise ValueError('확인된 세션 식별자가 없습니다')
    paths = list((home / 'sessions').rglob(f'rollout-*{identity}.jsonl'))
    if len(paths) != 1:
        raise ValueError('이번 세션의 실행 설정 기록을 하나로 찾지 못했습니다')
    settings = []
    with paths[0].open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('type') == 'turn_context':
                payload = row['payload']
                settings.append({'model': payload.get('model'), 'reasoning_effort': payload.get('effort')})
    if not settings or any(row != settings[0] for row in settings):
        raise ValueError('이번 세션의 모델·추론 설정이 없거나 일치하지 않습니다')
    return settings[0]


def student_interface(lab):
    """새 프로젝트와 기존 START 랩의 실제 요청 위치·붙여넣기 진입점."""
    if all((lab / name).is_file() for name in ('run.py', 'README.md', 'AGENTS.md', 'app/utils/llm_client.py')):
        return lab / 'output/model_requests', 'run.py'
    if (lab / 'llm_client.py').is_file() and (lab / 'START.md').is_file():
        return lab / '결과/요청', 'llm_client.py'
    raise ValueError('저장소 밖에 풀린 학생 프로젝트 또는 START 랩 폴더를 지정합니다')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('lab', type=Path)
    ap.add_argument('digest')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--codex-home', type=Path, required=True)
    ap.add_argument('--codex-bin', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--reasoning', choices=['none', 'low', 'medium', 'high', 'xhigh', 'max'], required=True)
    ap.add_argument('--max-calls', type=int, required=True)
    ap.add_argument('--timeout', type=int, default=180)
    a = ap.parse_args()
    lab, out = a.lab.resolve(), a.out.resolve()
    if not re.fullmatch(r'[a-f0-9]{12}', a.digest) or a.max_calls < 1 or a.timeout < 1:
        ap.error('요청 해시는 12자리 소문자 16진수, 상한은 양수여야 합니다')
    if (lab / '.env').exists():
        ap.error('키 없는 경로만 시험합니다. .env가 있는 폴더는 열지 않습니다')
    if lab.is_relative_to(ROOT):
        ap.error('저장소 밖에 풀린 학생 랩 폴더를 지정합니다')
    try:
        requests, entrypoint = student_interface(lab)
    except ValueError as error:
        ap.error(str(error))
    source = requests / (a.digest + '.md')
    if not source.is_file() or not (a.codex_home / 'auth.json').is_file():
        ap.error('요청 글 또는 로그인 파일이 없습니다')
    binary = shutil.which(a.codex_bin)
    if not binary:
        ap.error('Codex 실행 파일이 없습니다')
    out.mkdir(parents=True, exist_ok=True)
    used = len(list(out.glob('*/request.md')))
    run = out / a.digest
    if run.exists() or used >= a.max_calls:
        ap.error('이미 시도한 요청이거나 시험 호출 상한에 닿았습니다. 기록을 확인합니다')
    # 모델에는 요청 글만 전달한다. 학생의 코드·참조·가이드가 없는 빈 폴더에서 실행한다.
    isolated = SPARE / ('account-chat-' + hashlib.sha256(str(out).encode()).hexdigest()[:12])
    for parent in [isolated, *isolated.parents]:
        if any((parent / name).exists() for name in RULE_FILES):
            ap.error('계정 채팅 폴더의 상위에 규칙이나 저장소가 있습니다')
    isolated.mkdir(parents=True, exist_ok=True)
    run.mkdir()
    request = source.read_bytes()
    (run / 'request.md').write_bytes(request)
    prompt = ('아래는 외부 실행기가 보내는 에이전트 대화입니다. 요청 글의 system/user에 적힌 규약대로 다음 응답 하나를 작성하세요. '
              'tool/calls JSON은 외부 실행기에 돌려줄 조회 요청이므로 사용할 수 있습니다. '
              'Codex 자체의 실행·파일·검색 도구는 사용하지 마세요. 실제 조회 반환은 다음 요청에 제공됩니다. '
              '아직 반환되지 않은 관측값이나 실행 결과를 추측하지 마세요. 요청 글이 지정한 답의 형식만 반환하세요.\n\n').encode('utf-8') + request
    (run / 'prompt.txt').write_bytes(prompt)
    cmd = [binary, 'exec', '--skip-git-repo-check', '-s', 'read-only', '--json',
           '--model', a.model, '-c', f'model_reasoning_effort="{a.reasoning}"',
           '-c', 'features.shell_tool=false',
           '-o', str(run / 'response.txt'), '-']
    started = time.monotonic()
    child_env = dict(os.environ, CODEX_HOME=str(a.codex_home.resolve()),
                     PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    try:
        p = subprocess.run(cmd, cwd=isolated, env=child_env,
                           input=prompt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=a.timeout)
        raw, stderr, status = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        raw, stderr, status = e.stdout or b'', e.stderr or b'', 'timeout'
    except OSError as e:
        raw, stderr, status = b'', str(e).encode('utf-8'), 'launch_error'
    (run / 'events.jsonl').write_bytes(raw)
    (run / 'codex_stderr.log').write_bytes(stderr)
    observed = json_events(raw)
    try:
        observed.update(turn_settings(a.codex_home, observed['thread_id']))
    except (ValueError, OSError, KeyError) as error:
        observed['errors'].append(str(error))
    report = {'request_sha256': hashlib.sha256(request).hexdigest(), 'request_file': str(source),
              'prompt_sha256': hashlib.sha256(prompt).hexdigest(), 'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'model': observed.get('model'), 'reasoning_effort': observed.get('reasoning_effort'),
              'tokens': observed.get('tokens'), 'errors': observed.get('errors'), 'actions': observed.get('actions'),
              'status': status, 'elapsed_seconds': round(time.monotonic() - started, 3),
              'thread_id': observed['thread_id'], 'completed': observed['completed'], 'usage': observed.get('usage'),
              'host_shell_tool': False, 'student_entrypoint': entrypoint,
              'limit': a.max_calls, 'attempt': used + 1, 'method': '실제 Codex 계정 호출 뒤 학생 --paste',
              'course_api_call': False, 'pasted': False}
    answer = run / 'response.txt'
    valid = (status == 0 and observed['completed'] and report['model'] == a.model and report['reasoning_effort'] == a.reasoning
             and not report['errors'] and not report['actions'] and answer.is_file() and answer.stat().st_size > 0)
    if valid:
        data = answer.read_bytes()
        report['response_sha256'] = hashlib.sha256(data).hexdigest()
        try:
            pasted = subprocess.run([sys.executable, entrypoint, '--paste', a.digest, '--model', a.model],
                                    cwd=lab, env=child_env, input=data, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            (run / 'paste.log').write_bytes(pasted.stdout)
            report['paste_exit'] = pasted.returncode
            report['pasted'] = pasted.returncode == 0
        except subprocess.TimeoutExpired as error:
            (run / 'paste.log').write_bytes(error.stdout or b'')
            report['paste_exit'] = 'timeout'
        except OSError as error:
            (run / 'paste.log').write_text(str(error), encoding='utf-8')
            report['paste_exit'] = 'launch_error'
    (run / '실행.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['pasted']:
        raise SystemExit('실행 조건/응답/붙여넣기를 확인하지 못해 멈췄습니다. 기록을 확인합니다')


if __name__ == '__main__':
    main()
