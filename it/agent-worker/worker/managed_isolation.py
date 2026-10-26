"""Linux managed CLI boundary: a distinct UID and mandatory Landlock rules.

This protects worker credentials even when a bind-mounted secret is readable
to other users. Tool permissions and prompts are not the filesystem boundary.
Unsupported kernels/tools fail closed; the ordinary local worker is unchanged.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


UID = 65534
READ = 'read-file,read-dir,execute'
WRITE = READ + ',write-file,remove-dir,remove-file,make-dir,make-reg,make-sock,make-fifo,truncate'

# Claude Code provider selectors precede API-key authentication. A managed run
# must use its claim-bound gateway even if the host has other CLI/cloud logins.
# https://code.claude.com/docs/en/authentication#authentication-precedence
MODEL_ENV = frozenset(('ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_MODEL',
    'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL'))
OTHER_PROVIDER_PREFIXES = ('ANTHROPIC_', 'OPENAI_', 'CODEX_', 'AWS_', 'GOOGLE_', 'AZURE_', 'VERTEX_')
OTHER_PROVIDER_SELECTORS = frozenset(('CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
    'CLAUDE_CODE_USE_FOUNDRY', 'CLAUDE_CODE_OAUTH_TOKEN'))


def cli_args():
    # CLI flags override writable project/local settings. Skill discovery stays
    # enabled; only hooks and unrelated native execution/network tools go away.
    return ['--settings', json.dumps({'disableAllHooks': True}), '--tools',
            'Read,Glob,Grep,Write,Edit,Skill']


def enabled():
    return os.environ.get('HYD_MANAGED_MODEL_REQUIRED') == '1'


def _host():
    if sys.platform != 'linux' or os.geteuid() != 0 or not Path('/usr/bin/setpriv').is_file():
        raise RuntimeError('관리 AI 실행에는 Linux 권한 분리 실행기가 필요합니다')


def group_file(workdir):
    """Process ownership records must not be editable by the untrusted CLI."""
    _host()
    root = Path('/run/hyd-worker/groups')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root.parent, 0o700)
    os.chmod(root, 0o700)
    return root / (hashlib.sha256(str(Path(workdir).absolute()).encode()).hexdigest() + '.json')


def prepare(argv, kwargs):
    _host()
    root = Path(os.environ.get('CLIAGENTS_WORKSPACE_ROOT', '/workspace')).absolute()
    work = Path(kwargs.get('cwd') or '').absolute()
    if work.resolve() != work or root.resolve() != root or root not in work.parents or len(work.relative_to(root).parts) != 2:
        raise RuntimeError('관리 AI 작업 폴더는 교육 공간/작업별 실제 디렉터리여야 합니다')
    env = dict(kwargs.get('env') or {})
    config = Path(env.get('CLAUDE_CONFIG_DIR') or work / '.runtime-config' / 'claude-code')
    if config.resolve() != config.absolute() or work not in config.absolute().parents:
        raise RuntimeError('관리 AI 설정 폴더는 현재 작업 안에 있어야 합니다')
    home, tmp = work / '.runtime-home', work / '.runtime-tmp'
    for path in (config, home, tmp):
        path.mkdir(parents=True, exist_ok=True)
    # Do not follow retained links or chown a hard-linked external file.
    paths = [work, *work.rglob('*')]
    for path in paths:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise RuntimeError('관리 AI 작업 폴더의 링크·특수 파일은 허용하지 않습니다')
    for path in paths:
        os.chown(path, UID, UID, follow_symlinks=False)
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
    env.update(HOME=str(home), TMPDIR=str(tmp), USER='nobody', LOGNAME='nobody', CLAUDE_CONFIG_DIR=str(config))
    # Parent credentials must not be inherited, including references to files.
    for name in list(env):
        if (name.startswith('HYD_WORKER_') or name.startswith('HYD_CLASSROOM_')
                or name in OTHER_PROVIDER_SELECTORS
                or name.startswith(OTHER_PROVIDER_PREFIXES) and name not in MODEL_ENV):
            env.pop(name)
    command = ['/usr/bin/setpriv', '--reuid='+str(UID), '--regid='+str(UID), '--clear-groups',
               '--no-new-privs', '--inh-caps=-all', '--ambient-caps=-all', '--bounding-set=-all',
               '--landlock-access', 'fs']
    for path in ('/usr', '/lib', '/lib64', '/bin', '/sbin', '/etc', '/srv', '/proc'):
        if Path(path).exists():
            command += ['--landlock-rule', 'path-beneath:'+READ+':'+path]
    command += ['--landlock-rule', 'path-beneath:'+WRITE+':'+str(work)]
    for path in ('/dev/null', '/dev/urandom', '/dev/random'):
        command += ['--landlock-rule', 'path-beneath:read-file,write-file:'+path]
    return [*command, '--', *argv], dict(kwargs, env=env, umask=0o077)
