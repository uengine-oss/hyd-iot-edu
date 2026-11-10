"""간결한 학생 프로젝트의 안내·AI 설정·구조 검사. 기존 START 랩은 바꾸지 않는다."""
from pathlib import Path
import json
import re


AI_RULES = '''# AI 작업 경계

- `data/`, `app/ui/`, `app/utils/`, `run.py`는 제공 파일이다. 원자료와 제공 코드를 보존한다.
- 요청받은 핵심 기능과 판단 기준은 `app/features/`에서 구현한다. 실행 결과는 `output/`에만 쓴다.
- 먼저 자료와 현재 코드를 파악하고, 요청한 기능 범위에서 작게 구현한다. 무관한 기능이나 문서를 추가하지 않는다.
- 원자료만으로 정해지지 않는 판단은 사람에게 근거와 선택을 확인한다. AI가 대신 선택하거나 추천한 갈래로 완성하지 않는다.
- 원자료에 없는 값·관계·실행 결과를 만들지 않는다. 미확인, 값 없음, 0을 구별한다.
- 실제 실행한 명령·결과·변경 파일을 보고한다. 실행하지 않은 것을 성공했다고 말하지 않는다.
- DB는 이 폴더에 배정된 별도 랩 DB만 사용한다. 포털 DB나 전체 삭제 명령을 쓰지 않는다.
- 키와 비밀번호를 코드·결과·기록에 적지 않는다. 프로젝트 밖의 정답 가이드는 읽지 않는다.
'''

HIDDEN = {'.vscode': True,
          '**/__pycache__': True, '**/*.pyc': True}


def is_project(folder):
    folder = Path(folder)
    return (folder / 'run.py').is_file() and (folder / 'app/features').is_dir()


def readme(title, purpose, command='python run.py'):
    return (f'# {title}\n\n{purpose}\n\n'
            '```text\n'
            'data/           실습 자료\n'
            'app/features/   AI와 구현할 핵심 기능\n'
            'app/ui/         결과 화면 — 제공\n'
            'app/utils/      공통 처리 — 제공\n'
            'output/         실행 후 생기는 결과\n'
            'AGENTS.md       AI가 지킬 공통 규칙\n'
            '```\n\n'
            f'실행: `{command}`\n')


def write_metadata(folder, title, purpose, command='python run.py', extra_rules=''):
    """학생 설명은 README 하나. AGENTS는 보이며 도구별 설정·캐시만 숨긴다.

    extra_rules는 랩별 작업 경계만 받는다. 정답·전체 단계표·제작 지시는 넣지 않는다.
    이미 있는 VS Code 설정은 보존하고 이 프로젝트의 파일 숨김만 합친다.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'README.md').write_text(readme(title, purpose, command), encoding='utf-8-sig', newline='\n')
    rules = AI_RULES + ('\n' + extra_rules.strip() + '\n' if extra_rules.strip() else '')
    for relative in ('AGENTS.md',):
        p = folder / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rules, encoding='utf-8', newline='\n')
    settings = folder / '.vscode/settings.json'
    value = json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
    value['files.exclude'] = value.get('files.exclude', {}) | HIDDEN
    value['files.exclude'].pop('AGENTS.md', None)
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def root_errors(name):
    return [] if re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name) else [f'프로젝트 폴더는 영문 kebab-case여야 함: {name}']


def errors(files, root=None):
    """프로젝트 안 상대 경로→바이트. ZIP과 원본에 같은 검사를 적용한다."""
    out = root_errors(root) if root is not None else []
    for name in ('README.md', 'run.py', 'AGENTS.md'):
        if name not in files:
            out.append(f'프로젝트 필수 파일 없음: {name}')
    for prefix in ('data/', 'app/features/', 'app/ui/', 'app/utils/'):
        if not any(n.startswith(prefix) for n in files):
            out.append(f'역할별 파일 없음: {prefix}')
    for name in files:
        p = Path(name)
        if not name.isascii():
            out.append(f'영문이 아닌 경로: {name}')
        if p.name == 'README.md' and name != 'README.md':
            out.append(f'중복 학생 안내: {name}')
        if p.name in ('START.md', '준비_안내.md', 'CLAUDE.md'):
            out.append(f'이전 안내·규칙 사본: {name}')
        if name.startswith(('.claude/', '.github/')):
            out.append(f'사용하지 않는 AI 도구 설정: {name}')
        if name.startswith('output/'):
            out.append(f'시작본에 실행 결과 포함: {name}')
    return out
