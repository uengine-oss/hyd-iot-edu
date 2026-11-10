"""언제: 장난감 시험 도구를 고쳤을 때 — 가이드 격리·손상 ZIP 거절·모델/추론 기록을 모델 호출 없이 확인한다."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import zipfile

import ai_toy_test as toy


def main():
    root = toy.ROOT / '작업' / '검사'
    root.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix='toy-harness-', dir=root) as temporary:
        work = Path(temporary)
        assert work.resolve().is_relative_to(root.resolve())
        base = '05회차/랩/실습'
        good = {base + '/START.md': '# 시작', base + '/AGENTS.md': '규칙',
                base + '/자료/관측.csv': '시각,값\n', base + '_guide.html': '숨긴 정답'}

        def bundle(name, entries):
            path = work / (name + '.zip')
            with zipfile.ZipFile(path, 'w') as z:
                for key, value in entries.items():
                    z.writestr(key, value)
            return path

        lab = work / 'student'
        lab.mkdir()
        assert toy.unpack(bundle('정상', good), lab) == base
        assert sorted(p.relative_to(lab).as_posix() for p in lab.rglob('*') if p.is_file()) == [
            'AGENTS.md', 'START.md', '자료/관측.csv']
        checks.append('형제 가이드는 풀지 않고 학생 파일 바이트 보존')
        assert (lab / '자료/관측.csv').read_text(encoding='utf-8') == good[base + '/자료/관측.csv']
        for i, bad in enumerate(['05회차/대본/답.md', '05회차/랩/다른_guide.html',
                                 base + '/../탈출.txt', base + '/..\\탈출.txt', base + '/C:/탈출.txt']):
            destination = work / f'reject{i}'
            destination.mkdir()
            try:
                toy.unpack(bundle(f'손상{i}', good | {bad: '금지'}), destination)
            except SystemExit:
                assert not list(destination.rglob('*'))
                checks.append(f'잘못된 경로 거절 {i + 1}')
            else:
                raise AssertionError(f'손상 경로를 허용함: {bad}')
        for i, alias in enumerate(['자료//value.txt', '자료/./value.txt', '자료/VALUE.txt']):
            destination = work / f'duplicate{i}'
            destination.mkdir()
            try:
                toy.unpack(bundle(f'중복{i}', good | {base + '/자료/value.txt': '원래 값', base + '/' + alias: '덮어쓸 값'}), destination)
            except SystemExit:
                assert not list(destination.rglob('*'))
                checks.append(f'정규화 경로 중복 거절 {i + 1}')
            else:
                raise AssertionError(f'중복 경로를 허용함: {alias}')
        for cmd in toy.commands('codex', 'codex.exe', ['first', 'resume'], 'gpt-6-luna', 'medium'):
            assert cmd[cmd.index('--model') + 1] == 'gpt-6-luna'
            assert 'model_reasoning_effort="medium"' in cmd
        checks.append('새 턴과 재개에 모델·추론 모두 명시')
        parsed = toy.codex_turn('OpenAI Codex test\n--------\nmodel: gpt-6-luna\nreasoning effort: medium\nprovider: openai\n--------\ncodex\nREADY\ntokens used\n12\nREADY\n')
        assert (parsed['model'], parsed['reasoning_effort'], parsed['tokens'], parsed['final']) == (
            'gpt-6-luna', 'medium', 12, 'READY')
        checks.append('실제 실행 머리 형식에서 모델·추론·토큰 추출')
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
        if not bash or not Path(bash).is_file():
            raise SystemExit('rehearsal_turn.sh의 머리 대조 시험에 bash가 필요합니다')
        fake = work / 'fake_codex.sh'
        fake.write_text('''#!/usr/bin/env bash
set -eu
last=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '-o' ]; then shift; last="$1"; fi
  shift
done
if command -v cygpath >/dev/null; then last=$(cygpath -u "$last"); fi
printf 'READY\\n' > "$last"
printf 'OpenAI Codex fake\\n--------\\nmodel: %s\\nreasoning effort: %s\\n--------\\ncodex\\nmodel: gpt-6-luna\\nreasoning effort: medium\\nREADY\\ntokens used\\n1\\nREADY\\n' "$FAKE_MODEL" "$FAKE_REASONING"
''', encoding='utf-8', newline='\n')
        fake.chmod(0o700)
        fake_home = work / 'fake_home'
        fake_home.mkdir()
        (fake_home / 'auth.json').write_text('{}', encoding='utf-8')
        fake_lab = work / 'fake_lab'
        fake_lab.mkdir()
        prompt = work / 'prompt.txt'
        prompt.write_text('無モデル試験', encoding='utf-8')
        for mode, model, effort, expected in [
            ('new', 'gpt-6-luna', 'medium', 0), ('resume', 'gpt-6-luna', 'medium', 0),
            ('new', 'different-model', 'medium', 2), ('resume', 'gpt-6-luna', 'high', 2),
            ('new', '', '', 2),
        ]:
            run = subprocess.run([bash, (toy.HERE / 'rehearsal_turn.sh').as_posix(), fake_lab.as_posix(), prompt.as_posix(), mode],
                                 env=dict(os.environ, CODEX_BIN=fake.as_posix(), CODEX_HOME=fake_home.as_posix(),
                                          CODEX_MODEL='gpt-6-luna', CODEX_REASONING='medium', FAKE_MODEL=model, FAKE_REASONING=effort),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            assert run.returncode == expected, (run.returncode, run.stderr.decode('utf-8', errors='replace'))
            checks.append(f'실제 셸 머리 대조 {mode} {model or "누락"}/{effort or "누락"}: 종료 {expected}')
    print(json.dumps({'passed': len(checks), 'failed': 0, 'checks': checks, 'model_calls': 0}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
