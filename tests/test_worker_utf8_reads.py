"""The actual Windows shell must parse the worker's original UTF-8 task bytes."""
import json
import os
import subprocess
import sys

import pytest

from worker import prompt


def test_file_read_contract_survives_initial_resume_restart_and_correction():
    messages = [prompt.build({'activity_name': '발주안 제안'}, {}, workdir='work'),
                prompt.resume_prompt('확인했습니다'),
                prompt.resume_prompt('확인했습니다', restarted=True),
                prompt.format_correction('필수 값 누락', [])]
    for message in messages:
        assert "Get-Content -Raw -Encoding UTF8 -LiteralPath 'context/task.json'" in message
        assert "read_text(encoding='utf-8')" in message
        assert '원본 파일에 BOM을 붙여 고치지 마세요' in message


@pytest.mark.skipif(sys.platform != 'win32', reason='Actual Windows PowerShell UTF-8 reader')
def test_actual_powershell_reads_bomless_worker_task_without_mutating_it(tmp_path):
    task = {'activity_name': '발주안 제안', 'query': '필요량과 공급사 견적을 대조합니다', 'need_qty': 6}
    source = tmp_path / 'task.json'
    raw = json.dumps(task, ensure_ascii=False).encode('utf-8')
    source.write_bytes(raw)
    assert not raw.startswith(b'\xef\xbb\xbf')
    command = ("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
               "$task=Get-Content -Raw -Encoding UTF8 -LiteralPath $env:HYD_TEST_UTF8_TASK | ConvertFrom-Json; "
               "if($task.need_qty -ne 6){exit 2}; [Console]::Write($task.activity_name+'|'+$task.query)")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                            env={**os.environ, 'HYD_TEST_UTF8_TASK': str(source)},
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    assert result.stdout.decode('utf-8') == task['activity_name'] + '|' + task['query']
    assert source.read_bytes() == raw
