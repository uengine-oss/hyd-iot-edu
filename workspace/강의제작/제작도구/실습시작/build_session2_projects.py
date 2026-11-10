"""통합02의 지정 프로젝트 하나만 생성한다. 다른 과정·회차·강사 참조를 재생성하지 않는다.

python build_session2_projects.py ontology --dest 작업/검사/...
python build_session2_projects.py ontology --apply [--completed]
"""
from pathlib import Path
import argparse
from contextlib import nullcontext
import json
import shutil
import subprocess
import sys
import tempfile

import build_labs as B
import data_session2 as D
import lab_frame as F
from lab_package import ROOT, pack, entry, register, student_files, write_zip
from project_layout import write_metadata, errors, DB_RULE
import session2_project as P
import session2_project_guides as G
import session2_graph_project as GP

DEST = ROOT / 'workspace/강의제작/산출물/통합반/실습/02회차/랩'
VERSION = 'v22-project'   # 2026-11-11: 공용 고침(대조 칸 원래 글 · 오류 위치 · 저장 · 편집 승인 · 새 DB 적재 자리 · DB 경계 · 「랩 DB」 한 이름)
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
    body = P.convert(B.CHECKER).replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    body = body.replace("root/'app/features'", "root/'output'")
    body = body.replace('가이드 「결과 형식」의 모양으로 만든 뒤 다시 실행하세요.', 'python run.py parts로 모델을 생성한 뒤 다시 실행하세요.')
    body = body.replace('(가이드 결과 형식 참고)', '')
    body = body.replace('if errors:\n', 'errors = _pre + errors\nif errors:\n')
    if L['kind'].startswith('graph'):
        body = body.replace('python run.py parts로 모델을 생성', 'python run.py export로 그래프를 저장')
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


def build_graph(folder):
    L = B.graph_lab('통합반')
    source_data(folder)
    schema, graph = B.reference_model(False, B.LAB4_INPUT_BRANCH['통합반'])
    for name, value in [('schema.json', B.student_schema(schema)), ('graph.json', graph)]:
        write(folder / 'data/model' / name, P.convert(json.dumps(value, ensure_ascii=False, indent=2) + '\n'))
    write(folder / 'data/model/provenance.md', P.convert(B.provided_basis(False)))
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            if name == '결과/기대_답.csv':
                text = text.replace('값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」',
                                    '조회가 0행이면 「0줄」, 반환된 행의 빈 칸은 「없음」. 없는 품번을 설명하는 행을 반환하면 그 설명을 그대로 적음')
            write(folder / P.convert(name), P.convert(text).replace('python show_result.py가 실행', 'python run.py load가 실행'))
    write(folder / 'app/features/review.md', '# 실행 기록\n\n## 질문·사용할 자료·지킬 조건\n\n## 적재 전후 개수\n\n## 기대 답과 실제 결과·고친 근거\n\n## 기준 지도와 비교\n\n## 기준일·수정본 날짜·저장 시점·확인하지 못한 점\n')
    with tempfile.TemporaryDirectory(dir=WORK, prefix='changes-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(WORK.resolve()) and raw != WORK.resolve()
        D.write_changes(raw)
        for path in raw.iterdir():
            name = 'notes.md' if path.name == 'README.md' else P.NAMES[path.name]
            text = P.convert(path.read_text(encoding='utf-8-sig')).replace('`../data/`', '`data/`')
            write(folder / 'data/changes' / D.CHANGE_DATE / name, text)
    utilities, ui = P.result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/db.py', GP.db_source())
    write(folder / 'app/utils/cypher.py', GP.cypher_source())
    write(folder / 'app/utils/actions.py', GP.actions_source(L))
    write(folder / 'run.py', P.RUN)
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], G.GRAPH_PURPOSE, extra_rules=DB_RULE)
    steps = G.graph(B.portal_table())
    F.write_guide(folder, G.render(L['title'], G.GRAPH_PURPOSE, steps), ai_turns=sum(s['ai'] for s in steps))
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
    if starter.name == 'ontology-lab':
        files = A.integrated_design('A')
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen('A'))
        files['결과/기대_답.csv'] = B.expect_design_text()
        for name, text in files.items():
            write(folder / P.convert(name), P.convert(text))
        title, initial = '온톨로지 설계', 'python run.py parts\npython run.py query'
        context, actions = nullcontext(), ('parts', 'check', 'query')
    else:
        from reference.session2_graph_trials import fill, instance
        fill(folder)
        title, initial = '그래프 구현과 검증', 'python run.py db\npython run.py load\npython run.py update\npython run.py usage'
        context, actions = instance(folder), ('load', 'repeat', 'sensors', 'parts', 'usage', 'update', 'compare', 'export', 'check', 'usage')
    write_metadata(folder, title + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단 기준 한 가지를 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.'
                   + (' Docker Desktop을 켠 뒤 실행합니다.' if starter.name == 'graph-lab' else ''), command=initial)
    logs = {}
    with context:
        for action in actions:
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
    parser.add_argument('lab', choices=['ontology', 'graph'])
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더; 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 지정한 통합02 랩만 교체')
    parser.add_argument('--completed', action='store_true', help='별도 학생용 완성본도 실제 실행해 생성')
    args = parser.parse_args()
    build = build_ontology if args.lab == 'ontology' else build_graph
    WORK.mkdir(parents=True, exist_ok=True)
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()):
            parser.error('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent / (args.lab + '-lab')
        if folder.exists():
            parser.error('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        L, steps = build(folder)
        validate(folder, L, steps)
        if args.completed:
            completed(folder, parent, parent)
    else:
        with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
            work = Path(temp).resolve()
            assert work.is_relative_to(WORK.resolve()) and work != WORK.resolve()
            source = work / (args.lab + '-lab')
            L, steps = build(source)
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
