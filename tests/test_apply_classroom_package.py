"""Windows delivery updates preserve existing work and undo a partial failure."""
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'apply_classroom_package.ps1'
POWERSHELL = shutil.which('powershell.exe') if os.name == 'nt' else None
pytestmark = pytest.mark.skipif(not POWERSHELL, reason='requires Windows PowerShell 5.1')


def archive(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)


def apply(source, destination):
    return subprocess.run([POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPT),
                           '-ArchivePath', str(source), '-Destination', str(destination)], capture_output=True)


def test_existing_changes_are_backed_up_and_other_student_data_is_preserved(tmp_path):
    dest = tmp_path / 'pc'; dest.mkdir()
    (dest / 'change.txt').write_bytes(b'student-edited')
    (dest / 'same.txt').write_bytes(b'unchanged')
    (dest / '.env').write_bytes(b'private-setting')
    (dest / 'my-notes.txt').write_bytes(b'student-notes')
    config = dest / 'it' / 'supabase' / 'config.toml'; config.parent.mkdir(parents=True)
    config.write_bytes(b'existing-database-setting')
    source = tmp_path / 'source.zip'
    archive(source, [('change.txt', b'new-version'), ('same.txt', b'unchanged'),
                     ('new/file.txt', b'new-file'), ('it/supabase/config.toml', b'upstream-default')])
    assert apply(source, dest).returncode == 0
    assert (dest / 'change.txt').read_bytes() == b'new-version'
    assert (dest / 'same.txt').read_bytes() == b'unchanged'
    assert (dest / 'new' / 'file.txt').read_bytes() == b'new-file'
    assert config.read_bytes() == b'existing-database-setting'
    assert (dest / '.env').read_bytes() == b'private-setting'
    assert (dest / 'my-notes.txt').read_bytes() == b'student-notes'
    backups = list((dest / '.hyd-runtime' / 'package-backups').glob('*/change.txt'))
    assert len(backups) == 1 and backups[0].read_bytes() == b'student-edited'
    assert not list((dest / '.hyd-runtime' / 'package-backups').glob('*/same.txt'))


def test_failure_after_writes_restores_existing_file_and_removes_new_file(tmp_path):
    dest = tmp_path / 'pc'; dest.mkdir()
    (dest / 'change.txt').write_bytes(b'original')
    source = tmp_path / 'source.zip'
    archive(source, [('change.txt', b'new'), ('new.txt', b'new-file'), ('../outside.txt', b'bad')])
    assert apply(source, dest).returncode != 0
    assert (dest / 'change.txt').read_bytes() == b'original'
    assert not (dest / 'new.txt').exists()
    assert not (tmp_path / 'outside.txt').exists()
    backups = list((dest / '.hyd-runtime' / 'package-backups').glob('*/change.txt'))
    assert len(backups) == 1 and backups[0].read_bytes() == b'original'


def test_existing_lab_env_is_preserved_and_new_lab_gets_template(tmp_path):
    dest = tmp_path / 'pc'; dest.mkdir()
    lab = dest / 'course' / 'labs' / 'offline' / '05-2-cause-agent' / '.env'
    lab.parent.mkdir(parents=True)
    lab.write_bytes(b'LLM_API_KEY=student-key\nCUSTOM_OPTION=preserve\n')
    source = tmp_path / 'source.zip'
    archive(source, [('course/labs/offline/05-2-cause-agent/.env', b'LLM_API_KEY=template\n'),
                     ('another-lab/.env', b'LLM_API_KEY=template\n')])
    assert apply(source, dest).returncode == 0
    assert lab.read_bytes() == b'LLM_API_KEY=student-key\nCUSTOM_OPTION=preserve\n'
    assert (dest / 'another-lab' / '.env').read_bytes() == b'LLM_API_KEY=template\n'
    assert not list((dest / '.hyd-runtime' / 'package-backups').glob('*/course/labs/offline/05-2-cause-agent/.env'))
