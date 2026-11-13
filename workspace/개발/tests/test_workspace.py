"""작업 폴더(worker/workspace.py) — 실행마다 <작업 공간>/<테넌트>/<작업> 하나. 규칙 파일(CLAUDE.md)은 쓰지 않는다(규칙은 시스템 프롬프트로)."""
import os
import time

from worker import workspace

SKILL = {'skill_name': 'shift-handover-review', 'description': '교대 검토', 'content': '# 교대 검토\n실제 조회로 확인한다.'}


def test_작업_폴더에는_규칙_파일을_쓰지_않고_스킬_스키마_작업_기록만_쓴다(tmp_path):
    """B-03: 설정 출처를 끈 CLI 는 CLAUDE.md 를 읽지 않는다 — 읽히지 않는 사본을 남기지 않는다."""
    ws = workspace.for_run(tmp_path, 'todo-1', tenant_id='hyd')
    written = workspace.provision(ws, agent_id='claude-code', schema_prompt='스키마', task={'id': 'todo-1'}, skills=[SKILL])
    assert written == ['.claude/skills/shift-handover-review/SKILL.md']
    assert not (ws.path / 'CLAUDE.md').exists()
    assert (ws.path / 'context' / 'task.json').is_file() and (ws.path / 'context' / 'schema_prompt.md').read_text(encoding='utf8') == '스키마'


def test_보관_기한이_지난_실행_폴더만_지우고_열린_작업과_워커_상태_폴더는_남긴다(tmp_path):
    old, open_, fresh = (workspace.for_run(tmp_path, name, tenant_id='hyd') for name in ('old', 'open', 'fresh'))
    cache = tmp_path / '.ai-cache'
    cache.mkdir()
    (cache / 'k.json.gz').write_bytes(b'x')
    for ws in (old, open_):
        workspace.provision(ws, agent_id='claude-code', schema_prompt='s', task={})
    past = time.time() - 10 * 3600
    for path in [*old.path.rglob('*'), old.path, *open_.path.rglob('*'), open_.path, cache, cache / 'k.json.gz']:
        os.utime(path, (past, past))
    removed = workspace.sweep(tmp_path, 3600, keep=lambda run_id: run_id == 'open')
    assert removed == [old.path]
    assert open_.path.exists() and fresh.path.exists() and (cache / 'k.json.gz').exists()


def test_작업_폴더는_테넌트_아래_작업_id_하나다(tmp_path):
    ws = workspace.locate(tmp_path, '../escape', tenant_id='hyd')
    assert ws.path.parent == tmp_path / 'hyd' and '..' not in ws.path.name and not ws.exists
