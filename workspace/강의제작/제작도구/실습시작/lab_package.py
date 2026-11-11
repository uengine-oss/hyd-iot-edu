"""학생 랩 ZIP을 쓰는 한 곳 — 넣을 파일 고르기 · ZIP 쓰기 · package-index 등록 · 가이드 꾸밈.

같은 폴더 내용이면 언제 다시 묶어도 ZIP 바이트가 같다: 항목 시각을 STAMP로 고정하고, 경로는 소문자 조각 순서
(Windows 탐색 순서와 같다)로 넣는다. 압축은 zlib가 하므로 zlib 판이 다른 PC에서는 바이트가 다를 수 있다 —
내용 대조는 verify_packages.py가 한다. 생성기(build_labs · build_common · build_judgement_labs · build_session3_* ·
start_guides/build.py)는 이 파일의 pack · register를 쓴다. 시스템 코드(main 브랜치의 ot/ · common/ · it/)를 읽는 생성기는
system_root() 한 곳으로 그 위치를 찾는다.

폴더만 고친 랩 하나를 다시 묶는다(생성기의 다른 변경이 딸려 오지 않는다):
    python lab_package.py <랩 폴더> [--version <새 판>]
새 ZIP을 verify_packages.check_zip으로 검사해 통과할 때만 바꿔 끼우고, package-index에 그 랩이 있으면 그 항목의
sha256(주면 version)만 고친다. 바이트가 바뀌었는데 --version이 없으면 멈춘다(판 이름이 내용을 가리키게).
그다음 verify_packages.py로 검사한다.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import html
from urllib.parse import unquote
import sys
import zipfile
from project_layout import is_project, root_errors

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INDEX = HERE/'package-index.json'
STAMP = (2026, 1, 1, 0, 0, 0)                                # ZIP 항목 시각 — 파일 수정 시각이 해시를 흔들지 않게
ALWAYS_SKIP = frozenset({'__pycache__', '.pytest_cache'})    # 실행 찌꺼기 — 어느 랩에도 넣지 않는다(.pyc도)
PRIVATE = frozenset({'.env', '랩_연결.json', '.lab_connection.json'})  # 이 PC의 키 · 랩 DB 연결

GUIDE_CSS = '''*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#20342f;font:17px/1.8 "Malgun Gothic",sans-serif}main{max-width:1000px;margin:auto;padding:52px 28px}h1{font-size:36px;line-height:1.35}h2{font-size:25px;line-height:1.45;margin:0 0 18px}h3{font-size:20px;margin:22px 0 8px}section{background:white;border:1px solid #dce5df;border-radius:16px;padding:30px;margin:24px 0}a{color:#176554;text-underline-offset:4px}nav{display:flex;gap:14px;flex-wrap:wrap}nav a,.button{display:inline-block;background:#e2eee7;padding:8px 16px;border-radius:8px}p{margin:12px 0}li{margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2ef;padding:18px;border-radius:8px;font-size:15px}code{font-family:Consolas,monospace}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #dce5df;text-align:left;vertical-align:top}img{max-width:100%;height:auto}small{color:#607269}.check{border-left:4px solid #32886a;padding:12px 18px;background:#edf6ef}details{border-top:1px solid #dce5df;margin-top:18px;padding-top:12px}summary{cursor:pointer}'''


def system_root():
    """시스템 코드(main 브랜치)가 있는 저장소 루트. 환경 변수 HYD_MAIN_ROOT가 있으면 그것, 없으면 이 저장소 루트.
    이 PC는 main 체크아웃 안에 workspace/가 있어 저장소 루트에 ot/ · common/ · it/가 있다. workspace만 받은 곳(클라우드 세션)은
    git worktree add ../main main 뒤 HYD_MAIN_ROOT=../main으로 돌린다."""
    root = Path(os.environ.get('HYD_MAIN_ROOT') or ROOT).resolve()
    if not (root/'ot/plant-sim').is_dir() or not (root/'common/hydcommon').is_dir():
        raise SystemExit(f'{root}: 시스템 코드(ot/plant-sim · common/hydcommon)가 없습니다. '
                         'workspace만 받은 곳이면 `git fetch origin main:main` → `git worktree add ../main main` 뒤 '
                         '`HYD_MAIN_ROOT=../main`으로 다시 실행합니다.')
    return root


def student_files(folder, exclude_names=PRIVATE):
    """랩 폴더에서 ZIP에 넣을 파일. exclude_names의 이름이 경로 조각에 있으면 뺀다."""
    folder = Path(folder)
    skip = ALWAYS_SKIP | exclude_names
    files = [p for p in folder.rglob('*')
             if p.is_file() and p.suffix != '.pyc' and not skip & set(p.relative_to(folder).parts)]
    return sorted(files, key=lambda p: [x.lower() for x in p.relative_to(folder).parts])


def zip_root(folder):
    """새 프로젝트는 영문 폴더 하나. 기존 랩은 NN회차/랩/<랩> 구조를 유지한다."""
    if is_project(folder):
        errors = root_errors(Path(folder).name)
        if errors:
            raise ValueError('; '.join(errors))
        return Path(folder).name
    return '/'.join(Path(folder).resolve().parts[-3:])


def write_zip(archive, entries):
    """[(ZIP 안 경로, 바이트)]를 받은 순서 · 고정 시각으로 쓴다. 다 쓴 뒤 바꿔 끼운다."""
    archive = Path(archive)
    tmp = archive.with_name(archive.name + '.tmp')
    with zipfile.ZipFile(tmp, 'w') as z:
        for name, data in entries:
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    os.replace(tmp, archive)
    return archive


def pack(folder, exclude_names=PRIVATE, archive=None):
    """랩 폴더 → 옆의 <랩>.zip(또는 archive). 옆의 ZIP이 다른 루트(shift-handover/ 등)로 묶여 있으면 멈춘다
    — 다시 묶으면 학생이 푼 폴더 구조가 바뀌므로 사용자가 루트 형식을 정한 뒤 묶는다."""
    folder = Path(folder)
    root = zip_root(folder)
    existing = folder.parent/(folder.name + '.zip')
    if outside_guide(folder):
        inside = [n for n in ('guide.html', '안내.html') if (folder/n).exists()]
        if inside:
            raise ValueError(f'{folder.name}: 가이드는 폴더 밖({folder.name}_guide.html)에 있어야 하는데 폴더 안에 {inside}가 있다 — 생성기를 다시 돌린다.')
    if existing.exists():
        with zipfile.ZipFile(existing) as z:
            if not any(n.startswith(root + '/') for n in z.namelist()):
                raise ValueError(f'{existing.name}: 기존 ZIP의 루트가 {root}/가 아니다. 루트 형식을 사용자가 정한 뒤 묶는다.')
    entries = [(f'{root}/{p.relative_to(folder).as_posix()}', p.read_bytes()) for p in student_files(folder, exclude_names)]
    guide = outside_guide(folder)
    if guide:   # 코딩 랩 가이드는 ZIP 안 랩 폴더 옆에 함께 둔다 — 학생은 풀고 가이드는 브라우저로, 랩 폴더는 VS Code로 연다(가이드.md P-3)
        entries.append((guide_name(folder), guide.read_bytes()))
    return write_zip(archive or existing, entries)


def pack_guide(folder, root):
    """도구 실습 랩 폴더 → 옆의 <랩>.zip. 가이드.html과 가이드가 여는 파일만 루트 폴더 root/ 아래에 담는다
    (2026-11-11 사용자 「1회차는 가이드파일만 담겨있으면 될텐데」, 가이드 P-13). 랩 폴더에 가이드가 열지 않는 파일이 있거나
    가이드가 여는 파일이 없으면 멈춘다 — 랩 폴더와 ZIP이 같은 것을 담게 한다."""
    folder = Path(folder)
    page = (folder/'가이드.html').read_text(encoding='utf-8')
    refs = {unquote(html.unescape(r)) for r in re.findall(r'(?:src|href)="([^"#?:]+)"', page)}
    have = {p.relative_to(folder).as_posix() for p in student_files(folder)} - {'가이드.html'}
    if refs != have:
        raise ValueError(f'{folder}: 가이드가 여는 파일과 랩 폴더가 다르다 — 폴더에 없음 {sorted(refs-have)}, 가이드가 안 씀 {sorted(have-refs)}')
    names = ['가이드.html', *sorted(refs, key=lambda n: n.lower().split('/'))]
    return write_zip(folder.parent/(folder.name+'.zip'), [(f'{root}/{n}', (folder/n).read_bytes()) for n in names])


def guide_name(folder):
    """랩 폴더 옆 <랩>_guide.html. 새 프로젝트는 ZIP 최상위, 기존 랩은 NN회차/랩/ 아래다."""
    root = zip_root(folder)
    parent = root.rsplit('/', 1)[0] + '/' if '/' in root else ''
    return f'{parent}{Path(folder).name}_guide.html'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def outside_guide(folder):
    """코딩 랩 가이드(랩 폴더 밖 `<랩>_guide.html` — lab_frame.guide_path와 같은 자리). 없으면 None."""
    folder = Path(folder)
    path = folder.parent/(folder.name + '_guide.html')
    return path if path.is_file() else None


def entry(id, course, session, title, version, folder, **extra):
    """package-index 항목 하나. folder 옆에 묶은 ZIP이 있어야 한다. 폴더 옆 가이드가 있으면 guide_file(경로 · sha256)을 붙인다."""
    folder = Path(folder)
    archive = folder.parent/(folder.name + '.zip')
    item = {'id': id, 'course': course, 'session': session, 'title': title, 'version': version,
            'folder': zip_root(folder), 'path': archive.resolve().relative_to(ROOT).as_posix(),
            'sha256': sha256(archive), **extra}
    if is_project(folder):
        item['layout'] = 'project'
    guide = outside_guide(folder)
    if guide:
        item['guide_file'] = {'path': guide.resolve().relative_to(ROOT).as_posix(), 'sha256': sha256(guide)}
    return item


def register(entries, index=INDEX):
    """같은 id는 바꾸고 새 id는 더한 뒤 (과정, 회차, 폴더) 순서로 쓴다 — 어느 생성기가 마지막에 돌아도 순서가 같다."""
    data = json.loads(index.read_text(encoding='utf-8')) if index.exists() else {'labs': []}
    new = {item['id']: item for item in entries}
    labs = [item for item in data['labs'] if item['id'] not in new] + list(new.values())
    data['labs'] = sorted(labs, key=lambda item: (item['course'], item['session'], item['folder']))
    index.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description='폴더만 고친 랩 하나를 다시 묶는다.')
    parser.add_argument('folder', type=Path, help='산출물/<과정>/실습/NN회차/랩/<랩>')
    parser.add_argument('--version', help='package-index의 새 판 이름(바이트가 바뀌면 필수)')
    args = parser.parse_args(argv)
    folder = args.folder.resolve()
    archive = folder.parent/(folder.name + '.zip')
    if not folder.is_dir():
        raise SystemExit(f'{folder}: 랩 폴더 없음')
    from verify_packages import check_zip
    labs = json.loads(INDEX.read_text(encoding='utf-8'))['labs']
    item = next((x for x in labs if x['path'] == archive.relative_to(ROOT).as_posix()), None)
    if item is None and (folder/'START.md').is_file():
        raise SystemExit(f'{folder.name}: START.md 랩은 start_guides/build.py로 묶는다(안내.html을 START.md에서 다시 만든다).')
    try:
        candidate = pack(folder, archive=archive.with_name(folder.name + '.새.zip'))
    except ValueError as exc:
        raise SystemExit(str(exc))
    try:
        errors, notes = check_zip(candidate, folder)
        for line in notes:
            print('참고:', line)
        if errors:
            for line in errors:
                print('오류:', line)
            print('새 ZIP이 검사를 통과하지 못해 바꾸지 않았다.')
            return 1
        new = sha256(candidate)
        old = sha256(archive) if archive.exists() else None
        if new == old:
            print(f'{archive.name}: 바이트가 같다. 바꾼 것 없음.')
            return 0
        if item is not None and not args.version:
            print(f'{archive.name}: 바이트가 바뀐다({(old or "없음")[:12]} → {new[:12]}). --version <새 판>을 준다(지금 {item["version"]}).')
            return 1
        os.replace(candidate, archive)
    finally:
        candidate.unlink(missing_ok=True)
    if item is None:
        print(f'{archive.name}: 다시 묶음({new[:12]}). package-index 밖 랩이라 목록은 그대로다.')
        return 0
    register([item | {'version': args.version, 'sha256': new} | ({'guide_file': entry(item['id'], item['course'], item['session'], item['title'], args.version, folder)['guide_file']} if outside_guide(folder) else {})])
    print(f'{archive.name}: 다시 묶음({new[:12]}), package-index {item["id"]} 판 {args.version}. 다음: verify_packages.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
