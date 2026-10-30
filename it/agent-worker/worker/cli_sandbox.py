"""AI 워커 컨테이너의 CLI 격리: 다른 UID(nobody) + 반드시 걸리는 Landlock 파일 규칙(setpriv). 이미지가 켠다(Dockerfile ENV HYD_CLI_SANDBOX=landlock).

워커 인증 파일 · 작업 폴더 밖 파일을 CLI(에이전트)가 읽거나 고치지 못하게 한다 — 도구 권한 · 프롬프트는 파일 경계가 아니다. 커널 · 도구가
지원하지 않으면 실행하지 않는다(격리 없이 도는 폴백 없음). 개발용 호스트 워커(Windows · macOS)는 이 격리 없이 돈다.
cli_args 는 어디서나 붙는다: 사용자 · 프로젝트 설정 출처와 훅을 끄고, 승인된 스킬 본문만 읽기 전용 플러그인으로 준다.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import shutil


UID = 65534
READ = 'read-file,read-dir,execute'
WRITE = READ + ',write-file,remove-dir,remove-file,make-dir,make-reg,make-sock,make-fifo,truncate'

# Claude Code provider selectors precede API-key authentication. A course run
# must use its claim-bound gateway even if the host has other CLI/cloud logins.
# https://code.claude.com/docs/en/authentication#authentication-precedence
MODEL_ENV = frozenset(('ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_MODEL',
    'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL'))
OTHER_PROVIDER_PREFIXES = ('ANTHROPIC_', 'OPENAI_', 'CODEX_', 'AWS_', 'GOOGLE_', 'AZURE_', 'VERTEX_')
OTHER_PROVIDER_SELECTORS = frozenset(('CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
    'CLAUDE_CODE_USE_FOUNDRY', 'CLAUDE_CODE_OAUTH_TOKEN'))


def _skill_root(workdir):
    return Path('/run/hyd-approved-skills') / hashlib.sha256(str(Path(workdir).absolute()).encode()).hexdigest()


def cleanup_skills(workdir):
    if enabled():
        root = _skill_root(workdir)
        if root.exists():
            shutil.rmtree(root)


def cli_args(workdir, skills):
    # Excluding user/project/local settings also excludes their skills. Deliver
    # only the approved DB skill bodies as an explicit, fresh session plugin;
    # never load the writable .claude directory as an unrestricted plugin.
    tools = ['Read', 'Write', 'Edit']
    if skills:tools.append('Skill')
    args = ['--setting-sources', '', '--settings', json.dumps({'disableAllHooks': True}),
            '--tools', ','.join(tools)]
    if skills:
        from procsvc.agents_store import skill_markdown
        for skill in skills:
            name = skill['skill_name']
            if not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\\' in name:
                raise RuntimeError('승인 스킬 이름이 작업 폴더 범위를 벗어납니다')
        # In the sandbox the CLI cannot replace this bundle during
        # correction/resume. Its Landlock write grant covers only workdir.
        if enabled():
            _host()
            root = _skill_root(workdir)
            root.mkdir(mode=0o755, parents=True, exist_ok=True)
        else:
            # Host worker (no sandbox): the bundle lives in the run's own workspace.
            root = Path(workdir)
        plugin = Path(tempfile.mkdtemp(prefix='.approved-skills-', dir=root))
        manifest = plugin / '.claude-plugin'
        manifest.mkdir()
        (manifest / 'plugin.json').write_text(json.dumps({'name':'hyd-course-skills','version':'1.0.0'}), encoding='utf8')
        for skill in skills:
            target = plugin / 'skills' / skill['skill_name']
            target.mkdir(parents=True)
            (target / 'SKILL.md').write_text(skill_markdown(skill), encoding='utf8')
        if enabled():
            for path in [plugin, *plugin.rglob('*')]:
                os.chmod(path, 0o555 if path.is_dir() else 0o444)
        args += ['--plugin-dir', str(plugin)]
    return args


def enabled():
    return os.environ.get('HYD_CLI_SANDBOX') == 'landlock'


def _host():
    if sys.platform != 'linux' or os.geteuid() != 0 or not Path('/usr/bin/setpriv').is_file():
        raise RuntimeError('AI 실행 격리(HYD_CLI_SANDBOX=landlock)에는 Linux root · setpriv 가 필요합니다')


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
        raise RuntimeError('AI 작업 폴더는 작업 공간/테넌트/작업 의 실제 디렉터리여야 합니다')
    env = dict(kwargs.get('env') or {})
    config = Path(env.get('CLAUDE_CONFIG_DIR') or work / '.runtime-config' / 'claude-code')
    if config.resolve() != config.absolute() or work not in config.absolute().parents:
        raise RuntimeError('AI 설정 폴더는 현재 작업 폴더 안에 있어야 합니다')
    home, tmp = work / '.runtime-home', work / '.runtime-tmp'
    for path in (config, home, tmp):
        path.mkdir(parents=True, exist_ok=True)
    # Do not follow retained links or chown a hard-linked external file.
    paths = [work, *work.rglob('*')]
    stale_sockets = []
    for path in paths:
        info = path.lstat()
        # Claude leaves its private IPC socket after exit. The process group is
        # reaped before resume; retain every other special-file restriction.
        if (stat.S_ISSOCK(info.st_mode) and info.st_uid == UID
                and path.parent == tmp / 'cc-socks' and path.suffix == '.sock'
                and path.stem.isdecimal()):
            stale_sockets.append(path)
            continue
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise RuntimeError('AI 작업 폴더의 링크·특수 파일은 허용하지 않습니다')
    for path in stale_sockets:
        path.unlink()
    paths = [path for path in paths if path not in stale_sockets]
    for path in paths:
        os.chown(path, UID, UID, follow_symlinks=False)
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
    env.update(HOME=str(home), TMPDIR=str(tmp), USER='nobody', LOGNAME='nobody', CLAUDE_CONFIG_DIR=str(config))
    # Parent credentials must not be inherited, including references to files.
    for name in list(env):
        if (name.startswith('HYD_WORKER_')
                or name in OTHER_PROVIDER_SELECTORS
                or name.startswith(OTHER_PROVIDER_PREFIXES) and name not in MODEL_ENV):
            env.pop(name)
    command = ['/usr/bin/setpriv', '--reuid='+str(UID), '--regid='+str(UID), '--clear-groups',
               '--no-new-privs', '--inh-caps=-all', '--ambient-caps=-all', '--bounding-set=-all',
               '--landlock-access', 'fs']
    for path in ('/usr', '/lib', '/lib64', '/bin', '/sbin', '/etc', '/srv', '/proc'):
        if Path(path).exists():
            command += ['--landlock-rule', 'path-beneath:'+READ+':'+path]
    for index, arg in enumerate(argv[:-1]):
        if arg == '--plugin-dir':
            plugin = Path(argv[index + 1]).resolve()
            if plugin.parent != _skill_root(work) or not plugin.is_dir():
                raise RuntimeError('승인 스킬 묶음은 워커가 만든 읽기 전용 경로여야 합니다')
            command += ['--landlock-rule', 'path-beneath:'+READ+':'+str(plugin)]
    command += ['--landlock-rule', 'path-beneath:'+WRITE+':'+str(work)]
    for path in ('/dev/null', '/dev/urandom', '/dev/random'):
        command += ['--landlock-rule', 'path-beneath:read-file,write-file:'+path]
    return [*command, '--', *argv], dict(kwargs, env=env, umask=0o077)
