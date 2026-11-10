"""통합02의 지정 프로젝트 하나만 생성한다. 다른 과정·회차·강사 참조를 재생성하지 않는다.

python build_session2_projects.py ontology --dest 작업/검사/...
python build_session2_projects.py ontology --apply [--completed]
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile

import build_labs as B
import data_session2 as D
import lab_frame as F
from lab_package import ROOT, pack, entry, register, student_files, write_zip
from project_layout import write_metadata, errors
import session2_project as P
import session2_project_guides as G

DEST = ROOT / 'workspace/강의제작/산출물/통합반/실습/02회차/랩'
VERSION = 'v20-project'
WORK = ROOT / '작업/검사/session2-projects'


def write(path, text):
    F.write(path, text)


def source_data(folder):
    work = (ROOT / '작업/검사/session2-projects').resolve()
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix='data-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(work) and raw != work
        D.write_sources(raw)
        for path in raw.iterdir():
            write(folder / 'data' / P.NAMES[path.name], P.convert(path.read_text(encoding='utf-8-sig')))


def checker(folder, L):
    provided = [p.relative_to(folder).as_posix() for p in student_files(folder)
                if p.relative_to(folder).as_posix().startswith(('app/ui/', 'app/utils/')) or p.name == 'run.py']
    guard = F.provided_guard(folder, provided)
    chosen = P.convert(F.CHOSEN_CHECK)
    head = ('from pathlib import Path\nimport sys\n' + guard + chosen +
            '_root = Path(__file__).resolve().parents[2]\n_pre = provided_errors(_root) + chosen_errors(_root)\n')
    if L['kind'].startswith('graph'):
        return head + "for e in _pre: print(e)\nif _pre: sys.exit(1)\nprint('제공 파일·기록 검사 통과. 조회 결과는 원자료와 대조합니다.')\n"
    body = P.convert(B.CHECKER).replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    body = body.replace("root/'app/features'", "root/'output'")
    body = body.replace('가이드 「결과 형식」의 모양으로 만든 뒤 다시 실행하세요.', 'python run.py parts로 모델을 생성한 뒤 다시 실행하세요.')
    body = body.replace('(가이드 결과 형식 참고)', '')
    body = body.replace('if errors:\n', 'errors = _pre + errors\nif errors:\n')
    return head + body


def build_ontology(folder):
    L = B.design_integrated()
    source_data(folder)
    drawing = Path(__file__).with_name('session2_relationships.json')
    write(folder / 'data/relationships.json', drawing.read_text(encoding='utf-8-sig'))
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            text = P.convert(text)
            text = text.replace('5단계에서 정한 이름 기준', '정한 이름 기준')
            write(folder / P.convert(name), text)
    write(folder / 'app/features/requirements.md', '# 요구사항\n\n## 답을 쓸 사람·질문·기준일\n\n## 지킬 조건\n\n## 대조 결과·고친 점\n\n## 저장 시점·확인하지 못한 점\n')
    utilities, ui = P.result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/model.py', P.model_source())
    actions = P.actions_source(L)
    commands = {'sources': ('원자료', 'sources'), 'expected': ('기대 답', 'expected'),
                'design': ('식별자와 관계', 'design'), 'names': ('장치 이름', 'names'),
                'quantities': ('물리량과 센서', 'sensors'), 'units': ('단위', 'units'),
                'parts': ('공용 부품과 모델', 'parts'), 'query': ('질문별 대조', 'ask'), 'check': ('구조 검사', 'check')}
    actions += '\nCOMMANDS = {\n' + ''.join(f'    {cmd!r}: ({label!r}, {fn}),\n' for cmd, (label, fn) in commands.items()) + '}\n'
    write(folder / 'app/utils/actions.py', actions)
    write(folder / 'run.py', P.RUN)
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], G.ONTOLOGY_PURPOSE)
    steps = G.ontology()
    F.write_guide(folder, G.render(L['title'], G.ONTOLOGY_PURPOSE, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def validate(folder, L, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    item = entry('integrated-02-' + folder.name.removesuffix('-lab'), '통합반', '온라인 02회차', L['title'], VERSION, folder,
                 guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    assert not check_zip(folder.with_suffix('.zip'), folder)[0]
    verify_lab(item)
    return item


def replace_generated(source, target):
    """검사가 끝난 이 생성기의 프로젝트 하나만 정본에 반영한다."""
    target = target.resolve()
    if target.parent != DEST.resolve() or target.name != source.name or target.name not in ('ontology-lab', 'graph-lab'):
        raise ValueError('지정한 통합02 프로젝트 밖에는 반영하지 않습니다.')
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    for suffix in ('_guide.html', '.zip'):
        shutil.copyfile(source.parent / (source.name + suffix), target.parent / (target.name + suffix))


def completed(starter, destination, work):
    """학생용 완성본은 별도 묶음이며 시작 ZIP에 넣지 않는다. 유료 AI 호출 없음."""
    import session2_answers as A
    folder = work / 'completed' / starter.name
    shutil.copytree(starter, folder)
    files = A.integrated_design('A')
    files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen('A'))
    files['결과/기대_답.csv'] = B.expect_design_text()
    for name, text in files.items():
        write(folder / P.convert(name), P.convert(text))
    write_metadata(folder, '온톨로지 설계 · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단 기준 한 가지를 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.',
                   command='python run.py parts\npython run.py query')
    logs = {}
    for action in ('parts', 'check', 'query'):
        run = subprocess.run([sys.executable, 'run.py', action, '--no-open'], cwd=folder,
                             capture_output=True, text=True, encoding='utf-8')
        logs[action] = run.stdout + run.stderr
        if run.returncode:
            raise RuntimeError(logs[action])
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    write(work / 'completed-execution.json', json.dumps(logs, ensure_ascii=False, indent=2) + '\n')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lab', choices=['ontology'])
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더; 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 지정한 통합02 랩만 교체')
    parser.add_argument('--completed', action='store_true', help='별도 학생용 완성본도 실제 실행해 생성')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()):
            parser.error('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent / (args.lab + '-lab')
        if folder.exists():
            parser.error('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        L, steps = build_ontology(folder)
        validate(folder, L, steps)
        if args.completed:
            completed(folder, parent, parent)
    else:
        with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
            work = Path(temp).resolve()
            assert work.is_relative_to(WORK.resolve()) and work != WORK.resolve()
            source = work / (args.lab + '-lab')
            L, steps = build_ontology(source)
            validate(source, L, steps)
            archive = completed(source, work, work) if args.completed else None
            folder = DEST / source.name
            replace_generated(source, folder)
            register([validate(folder, L, steps)])
            if archive:
                target = DEST.parent / '완성본' / archive.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archive, target)
                shutil.copyfile(work / 'completed-execution.json', WORK / (args.lab + '-completed-execution.json'))
    print(folder)


if __name__ == '__main__':
    main()
