"""2회차 네 랩의 학생용 완성본 — 실습 폴더에 가이드 「정답 보기」의 정할 자리 내용(강사 참조 기본 갈래)을 넣고 제공 흐름을 돌린 묶음.

계정이 없는 학생과 정답을 보고도 막힌 학생이 결과를 확인하는 묶음이다(코딩랩.md K-4). 실습 ZIP 밖 `산출물/<과정>/실습/02회차/완성본/`에 쓴다.
만드는 길: 랩 폴더 사본 → 단계마다 정답 토글 apply → `python show_result.py --no-open`(실습4는 이 스크립트가 띄운 랩 DB에서) → 모든 단계 「채움」 ·
`python check.py` 통과 확인 → 랩 DB 연결 파일 · 캐시를 뺀 뒤 ZIP. 같은 입력이면 같은 바이트다(보기.html에 시각 · 절대 경로 없음, ZIP 항목 시각 고정).
사용: python session2_completed.py [--check]   (--check = 두 번 만들어 바이트가 같은지, 새 폴더에 풀어 check.py가 통과하는지)
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_labs as B           # noqa: E402
import lab_frame as F            # noqa: E402
from lab_package import write_zip, sha256   # noqa: E402

PY = sys.executable
NOTE = ('# 학생용 완성본\n\n'
        '이 묶음은 실습 폴더에 가이드의 「정답 보기」 내용(정할 자리)을 넣고 결과 화면을 만든 판입니다. 계정이 없거나 정답을 보고도 막혔을 때 결과를 확인하는 데 씁니다.\n\n'
        '- `결과/보기.html`을 브라우저로 열면 단계마다 결과가 보입니다.\n'
        '- 다시 만들어 보려면 이 폴더에서 {run}를 실행합니다.\n'
        '- 결정 지점(`결과/정한_것.csv`)은 갈래 하나를 고른 판입니다. 다른 선택도 근거가 있으면 됩니다 — 그때 바뀌는 답은 가이드의 「정답 보기」에 있습니다.\n')
TARGETS = {('실전반', 3): ('실전반_02일차_실습3_온톨로지설계_완성본.zip', '실전반_02일차_실습3_온톨로지설계_완성본'),
           ('실전반', 4): ('02일차_실습4_그래프구현과검증_학생용완성본.zip', '02일차_실습4_그래프구현과검증')}
SKIP = {'랩_연결.json', '__pycache__', '.보기_이전.json'}


def show(folder):
    p = subprocess.run([PY, 'show_result.py', '--no-open'], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1'})
    states = re.findall(r'^\d\d .+?: (.+)$', p.stdout, re.M)
    if p.returncode or any(s not in ('채움', '볼 것 없음', '결과 보기') for s in states):
        raise SystemExit(f'{folder.name}: 결과 화면 단계가 다 채워지지 않았습니다(종료 코드 {p.returncode})\n{p.stdout[-2000:]}{p.stderr[-1000:]}')


def check(folder):
    p = subprocess.run([PY, 'check.py'], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1'})
    if p.returncode:
        raise SystemExit(f'{folder.name}: check.py 불통과\n{p.stdout[-2000:]}')
    return p.stdout.strip().splitlines()[-1]


def build(course, number, work):
    """완성본 폴더 하나를 work 아래에 만들고 (ZIP 이름, 루트, 폴더)를 돌려준다."""
    L = B.LABS[number](course)
    name = B.LAB3 if number == 3 else B.LAB4
    zip_name, root = TARGETS[(course, number)]
    folder = work / root
    shutil.copytree(B.OUT / course / '실습/02회차/랩' / name, folder)
    for s in L['steps']:
        if s.get('answer'):
            for rel, text in s['answer']['apply'].items():
                F.write(folder / rel, text)
    container = None
    try:
        if number == 4:
            up = subprocess.run([PY, 'lab_db.py', '--no-open'], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if up.returncode:
                raise SystemExit(f'{course} 실습4 완성본: lab_db.py 실패\n{up.stdout}{up.stderr}')
            container = json.loads((folder / '랩_연결.json').read_text(encoding='utf-8'))['container']
        show(folder)
        show(folder)       # 두 번째 실행: 직전 실행 칸이 채워진 판(같은 적재 · 같은 수정을 다시 한 결과)을 싣는다
    finally:
        if container:
            subprocess.run(['docker', 'rm', '-f', '-v', container], capture_output=True)
    last = check(folder)
    run = '`python show_result.py`' if number == 3 else '`python lab_db.py` 다음 `python show_result.py`(Docker Desktop 필요)'
    F.write(folder / '완성본_안내.md', NOTE.format(run=run))
    for p in list(folder.rglob('*')):
        if p.name in SKIP and p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    return zip_name, root, folder, last


def pack(folder, root, target):
    files = sorted((p for p in folder.rglob('*') if p.is_file()), key=lambda p: [x.lower() for x in p.relative_to(folder).parts])
    write_zip(target, [(f'{root}/{p.relative_to(folder).as_posix()}', p.read_bytes()) for p in files])


def main():
    out = {}
    with tempfile.TemporaryDirectory(prefix='s2completed-', dir=os.environ.get('HYD_REPLAY_DIR') or None) as tmp:
        tmp = Path(tmp)
        for course, _ in B.COURSES:
            for number in (3, 4):
                if course == '통합반':
                    print(f'통합반 실습{number}: build_session2_projects.py {"ontology" if number == 3 else "graph"} --apply --completed 사용')
                    continue
                work = tmp / f'{course}{number}'
                work.mkdir()
                zip_name, root, folder, last = build(course, number, work)
                target = B.OUT / course / '실습/02회차/완성본' / zip_name
                target.parent.mkdir(parents=True, exist_ok=True)
                pack(folder, root, target)
                out[f'{course} 실습{number}'] = {'zip': target.relative_to(B.ROOT).as_posix(), 'sha256': sha256(target), 'check': last}
                if '--check' in sys.argv:
                    again = tmp / f'{course}{number}_again'
                    again.mkdir()
                    _, _, folder2, _ = build(course, number, again)
                    second = tmp / 'second.zip'
                    pack(folder2, root, second)
                    if sha256(second) != sha256(target):
                        raise SystemExit(f'{zip_name}: 두 번 만든 바이트가 다릅니다.')
                    import zipfile
                    fresh = tmp / f'{course}{number}_fresh'
                    with zipfile.ZipFile(target) as z:
                        z.extractall(fresh)
                    out[f'{course} 실습{number}']['fresh_check'] = check(fresh / root)
                    out[f'{course} 실습{number}']['twice_same'] = True
    for k, v in out.items():
        print(k, v)


if __name__ == '__main__':
    main()
