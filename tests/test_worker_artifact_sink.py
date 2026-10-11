"""Worker artifact bytes, containment, atomic publication and failed-write cleanup."""
from pathlib import Path
import pytest
from worker import workspace


def test_sink_preserves_utf8_and_mixed_newlines_and_replaces_atomically(tmp_path, monkeypatch):
    sink = workspace.Utf8DirectorySink(tmp_path)
    target = tmp_path / 'nested' / 'CLAUDE.md'
    sink.write('nested/CLAUDE.md', 'old\n')
    content = '# 한글\nLF\r\nCRLF\rCR\n'
    replace = workspace.os.replace
    def observe(source, destination):
        assert Path(destination) == target
        assert target.read_bytes() == b'old\n'
        assert Path(source).parent == target.parent
        assert Path(source).read_bytes() == content.encode('utf-8')
        replace(source, destination)
    monkeypatch.setattr(workspace.os, 'replace', observe)
    sink.write('nested/CLAUDE.md', content)
    assert target.read_bytes() == content.encode('utf-8')
    assert list(tmp_path.rglob('*.tmp')) == []
    assert sink.written == ['nested/CLAUDE.md', 'nested/CLAUDE.md']


@pytest.mark.parametrize('absolute', [False, True])
def test_sink_refuses_outside_paths(tmp_path, absolute):
    root = tmp_path / 'run'
    root.mkdir()
    outside = tmp_path / 'outside.md'
    sink = workspace.Utf8DirectorySink(root)
    with pytest.raises(ValueError, match='escapes'):
        sink.write(str(outside) if absolute else '../outside.md', 'must not escape')
    assert not outside.exists()
    assert list(root.iterdir()) == []
    assert sink.written == []


def test_sink_refuses_symlink_parent_escape(tmp_path):
    root, outside = tmp_path / 'run', tmp_path / 'outside'
    root.mkdir(); outside.mkdir()
    try:
        (root / 'link').symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f'OS cannot create directory symlink: {error}')
    sink = workspace.Utf8DirectorySink(root)
    with pytest.raises(ValueError, match='escapes'):
        sink.write('link/CLAUDE.md', 'must not escape')
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize('failure', ['write', 'replace'])
def test_sink_failure_preserves_previous_file_and_removes_temporary(tmp_path, monkeypatch, failure):
    sink = workspace.Utf8DirectorySink(tmp_path)
    sink.write('CLAUDE.md', 'original\n')
    if failure == 'write':
        fdopen = workspace.os.fdopen
        class InterruptedWriter:
            def __init__(self, fd, mode): self.stream = fdopen(fd, mode)
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def write(self, payload):
                self.stream.write(payload[:2])
                raise OSError('interrupted write')
        monkeypatch.setattr(workspace.os, 'fdopen', InterruptedWriter)
    else:
        def fail_replace(*args): raise OSError('interrupted replace')
        monkeypatch.setattr(workspace.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='interrupted'):
        sink.write('CLAUDE.md', 'new content\n')
    assert (tmp_path / 'CLAUDE.md').read_bytes() == b'original\n'
    assert list(tmp_path.iterdir()) == [tmp_path / 'CLAUDE.md']
    assert sink.written == ['CLAUDE.md']


def test_provision_uses_portable_sink_for_context(tmp_path):
    ws = workspace.for_run(tmp_path, 'portable')
    workspace.provision(ws, agent_id='claude-code', constitution='# 규칙\n', schema_prompt='# 스키마\n', task={'name': '작업'})
    assert (ws.path / 'CLAUDE.md').read_bytes() == '# 규칙\n'.encode()
    assert (ws.context_dir / 'schema_prompt.md').read_bytes() == '# 스키마\n'.encode()
    assert (ws.context_dir / 'task.json').read_bytes() == '{\n  "name": "작업"\n}'.encode()
