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
# 그래프 랩 v33-lab(2026-11-18): 장난감 시험 two_turn에서 AI가 「다 해 줘」에 기능 파일 둘을 한 번에 고치고 update.cypher에 불용 설비 처리(정할 지점)를 학생 선택 없이 써 넣어, 랩별 경계 두 줄을 더함(GRAPH_RULE). 설계 랩은 v32-lab 그대로다.
VERSIONS = {'ontology-lab': 'v32-lab', 'graph-lab': 'v33-lab'}
# v32-lab — 2026-11-18: 독립 검토 두 건(판정/검토_통합2_ontology_v31.json · 검토_통합2_graph_v31.json) 고침 — 가이드 끝의 내 말로 되짚기, 기대 답을 결정 직후 · 구현 앞에, 역량 질문을 현장 값(설비 코드 · 품번)으로 묻기(식별자 틀과 무관), 같은 모델의 구성 요소 이름 맞추기는 제공 코드로(name_rules.py 뺌), 그래프 랩의 쿼리 짚어 보기와 장부의 이름. 앞 판 v31-lab: 설비 3대는 눈으로 다 읽혀 실습 랩 규모(코딩랩 K-3)보다 작아, 공장 규모에서 2라인 한일유압 설비 5대 · 모델 셋(현장 지시계 포함)을 골라 다시 만듦 — 정할 지점은 그대로, 이론 개편의 이름을 받고 요령의 까닭은 lab_frame TIP_*. 앞 판 v30-lab: 독립 검토(판정/검토_지침과_통합2회차.json) 고침 — 작업 2026-11-17_코딩랩-원리중심-학생결정자
WORK = ROOT / '작업/검사/session2-projects'


def write(path, text):
    F.write(path, text)


def result_sources():
    """제공 결과 화면 코드. 대조 표의 거르기 단추 글자를 표 머리로 읽히지 않는 말로 바꾼다(리허설 06 막힘 6)."""
    utilities, ui = P.result_sources()
    for old, new in [('o.textContent=only?"모든 줄":"다른 줄만"', 'o.textContent=only?"모든 줄 보기":"같음 줄 숨기기"'),
                     ('<button class="t only">다른 줄만</button>', '<button class="t only">같음 줄 숨기기</button>')]:
        if ui.count(old) != 1:
            raise ValueError(f'결과 화면 코드에서 바꿀 글을 찾지 못했습니다: {old}')
        ui = ui.replace(old, new)
    return utilities, ui


# 장난감 시험(2026-11-12) — AI가 결정 · 기대 답을 스스로 채우고, 기능 파일 여럿을 한꺼번에 짰다. 작업 경계만 둔다(형식은 강제하지 않음, 코딩랩 K-6).
DECISION_RULE = ('- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 답 후보도 된다). '
                 '학생이 정하지 않았으면 적지 않고, 정할 것을 선택지와 그 결과로 보여 묻는다.\n'
                 '- 한 번에 요청받은 기능 파일 하나만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. 랩 DB를 쓰는 기능은 랩 DB에서 실행한 결과로 확인한다.')   # 실전반 설계 랩이 쓴다(build_practical2_projects)

# 통합반 설계 랩의 랩별 경계 — 이 랩에는 랩 DB가 없고, 판단 함수 파일은 하나다. 표는 가이드가 한 요청에 둘셋을 맞추게 하므로 「요청받은 것만」으로 적는다(검토 지적, 코딩랩 K-6).
DESIGN_RULE = (DECISION_RULE.split('\n')[0] + '\n'
               '- 판단 함수 파일은 `app/features/quantity_rules.py` 하나다. 요청받았을 때만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. '
               '표(`design.csv` · `relations.csv` · `row_rules.csv` · `expected.csv` · `decisions.csv`)는 요청받은 것만 고친다.\n'
               '- 모델은 `python run.py parts`가 `output/schema.json` · `output/graph.json`에 쓴다. 이 두 파일을 손으로 고치지 않는다.')


# 리허설 07 막힘: Codex 샌드박스는 랩 DB(Docker)에 닿지 못해 AI가 실행을 시도하다 실패했다. 그래프 랩은 랩 DB 명령을 학생 터미널에 둔다.
GRAPH_DECISION_RULE = ('- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 답 후보도 된다). '
                       '학생이 정하지 않았으면 적지 않고, 정할 것을 선택지와 그 결과로 보여 묻는다.\n'
                       '- 한 번에 요청받은 기능 파일 하나만 고친 뒤 멈춘다. 랩 DB를 쓰는 명령(`python run.py` 기능)은 학생이 자기 터미널에서 실행하고, '
                       'AI는 학생이 붙여 준 터미널 출력과 결과 화면으로 확인한다. AI가 그 명령을 직접 실행하지 않는다.')   # 실전반 그래프 랩이 쓴다(build_practical2_projects)

# 통합반 그래프 랩의 랩별 경계 — 위 둘에 장난감 시험(v32-lab two_turn)에서 뚫린 두 틈을 막는 줄을 더한다(코딩랩 K-6 · 길 6).
GRAPH_RULE = (GRAPH_DECISION_RULE + '\n'
              '- `app/features/update.cypher`의 불용 설비 처리는 `decisions.csv` 「불용 결정 설비」 줄을 학생이 정한 뒤에만 쓴다. '
              '정하기 전에는 수정본의 다른 줄만 반영하고 그 처리는 쓰지 않으며, 무엇을 정해야 하는지 선택지와 결과로 묻는다.\n'
              '- 「다 해 줘」처럼 여러 기능을 한꺼번에 부탁받아도 기능 파일 하나를 고친 뒤 멈추고, 다음 기능을 할지 묻는다.')


def run_source():
    """제공 run.py — 실행이 확인 필요로 끝나도 직전에 성공한 결과를 지우지 않고, 이번 실패를 위에 · 직전 성공을 그 아래에 밝혀 보인다(리허설 07 막힘)."""
    BS = chr(92)
    text = P.RUN
    old = "    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='" + BS + "n')" + chr(10) + \
          "    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '" + BS + "n', encoding='utf-8')" + chr(10)
    new = ("    failed = any(b['kind'] == 'error' for b in blocks)" + chr(10) +
           "    saved = output / 'result.json'" + chr(10) +
           "    last = json.loads(saved.read_text(encoding='utf-8')).get('last_success') if saved.exists() else None" + chr(10) +
           "    if not failed:" + chr(10) +
           "        last = {'action': args.action, 'title': title, 'blocks': blocks}" + chr(10) +
           "    shown = blocks + ([results.note('아래는 직전에 성공한 「' + last['title'] + '」 실행의 결과입니다. 이번 실행은 위의 확인 필요로 끝났습니다.')] + last['blocks'] if failed and last else [])" + chr(10) +
           "    target.write_text(page(actions.TITLE, title, shown), encoding='utf-8', newline='" + BS + "n')" + chr(10) +
           "    saved.write_text(json.dumps({'action': args.action, 'blocks': blocks, 'last_success': last}, ensure_ascii=False, indent=2) + '" + BS + "n', encoding='utf-8')" + chr(10))
    if text.count(old) != 1:
        raise ValueError('run.py 원본의 결과 쓰기 줄을 찾지 못했습니다.')
    return text.replace(old, new)


# 가이드가 채우라고 하는 절만 둔다 — 같은 대상의 다른 이름은 모델이 aliases · other_codes로 남기므로 따로 적는 절을 두지 않는다(검토 지적, 2026-11-17).
REQUIREMENTS = ('# 요구사항\n\n## 목적과 답을 쓸 사람\n\n## 역량 질문과 기준일\n\n## 지킬 조건 · 범위 밖\n\n'
                '## 대조 결과 · 고친 점\n\n## 저장 시점 · 확인하지 못한 점\n')


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
    D.require('통합반')
    L = B.design_integrated()
    source_data(folder)
    drawing = Path(__file__).with_name('session2_relationships.json')
    write(folder / 'data/relationships.json', drawing.read_text(encoding='utf-8-sig'))
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            write(folder / P.convert(name), P.convert(text))
    write(folder / 'app/features/requirements.md', REQUIREMENTS)
    utilities, ui = result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/model.py', P.model_source())
    actions = P.actions_source(L)
    commands = {'sources': ('원자료', 'sources'), 'expected': ('기대 답', 'expected'),
                'design': ('식별자와 관계', 'design'), 'names': ('구성 요소 이름과 실물', 'names'),
                'quantities': ('물리량과 센서', 'sensors'),
                'parts': ('부품과 모델', 'parts'), 'query': ('질문별 대조', 'ask'), 'check': ('구조 검사', 'check')}
    actions += '\nCOMMANDS = {\n' + ''.join(f'    {cmd!r}: ({label!r}, {fn}),\n' for cmd, (label, fn) in commands.items()) + '}\n'
    write(folder / 'app/utils/actions.py', actions)
    write(folder / 'run.py', run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], G.ONTOLOGY_PURPOSE, extra_rules=DESIGN_RULE)
    steps = G.ontology()
    F.write_guide(folder, G.render(L['title'], G.ONTOLOGY_PURPOSE, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def build_graph(folder):
    D.require('통합반')
    L = B.graph_lab('통합반')
    source_data(folder)
    schema, graph = B.reference_model(False, B.GRAPH_LAB_INPUT['통합반'])
    for name, value in [('schema.json', B.student_schema(schema)), ('graph.json', graph)]:
        write(folder / 'data/model' / name, P.convert(json.dumps(value, ensure_ascii=False, indent=2) + '\n'))
    write(folder / 'data/model/provenance.md', P.convert(B.provided_basis(False)))
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            if name == '결과/기대_답.csv':
                text = text.replace('값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」',
                                    '쿼리 결과가 0행이면 「0줄」, 반환된 행의 빈 칸은 「없음」. 없는 품번을 설명하는 행을 반환하면 그 설명을 그대로 적음')
                if '쿼리 결과가 0행이면' not in text:
                    raise ValueError('그래프 랩 기대 답 틀의 값 꼴 문장이 바뀌었습니다.')
            write(folder / P.convert(name), P.convert(text).replace('python show_result.py가 실행', 'python run.py load가 실행'))
    write(folder / 'app/features/review.md', '# 실행 기록\n\n## 역량 질문·사용할 자료·지킬 조건\n\n## 적재 전후 개수\n\n## 기대 답과 실제 결과·고친 근거\n\n## 기준 지도와 비교\n\n## 기준일·수정본 날짜·저장 시점·확인하지 못한 점\n')
    with tempfile.TemporaryDirectory(dir=WORK, prefix='changes-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(WORK.resolve()) and raw != WORK.resolve()
        D.write_changes(raw)
        for path in raw.iterdir():
            name = 'notes.md' if path.name == 'README.md' else P.NAMES[path.name]
            text = P.convert(path.read_text(encoding='utf-8-sig')).replace('`../data/`', '`data/`')
            write(folder / 'data/changes' / D.CHANGE_DATE / name, text)
    utilities, ui = result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/db.py', GP.db_source())
    write(folder / 'app/utils/cypher.py', GP.cypher_source(integrated=True))
    write(folder / 'app/utils/actions.py', GP.actions_source(L))
    write(folder / 'run.py', run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], G.GRAPH_PURPOSE, extra_rules=GRAPH_RULE + '\n' + DB_RULE)
    steps = G.graph(B.portal_table())
    F.write_guide(folder, G.render(L['title'], G.GRAPH_PURPOSE, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def validate(folder, L, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    item = entry('integrated-02-' + folder.name.removesuffix('-lab'), '통합반', '온라인 02회차', L['title'], VERSIONS[folder.name], folder,
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
        branch = B.GRAPH_LAB_INPUT['통합반']    # 완성본은 다음 랩(그래프)의 제공 모델과 같은 판단
        files = A.integrated_design(branch)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = B.expect_design_text(branch)
        files['결과/요구사항.md'] = A.integrated_requirements(branch)     # 가이드가 적게 하는 요구 글을 그 갈래로 채운다(빈 틀로 두면 요구 없이 완성된 것처럼 보인다)
        for name, text in files.items():
            write(folder / P.convert(name), P.convert(text))
        title, initial = '온톨로지 설계', 'python run.py parts\npython run.py query'
        context, actions, rules = nullcontext(), ('parts', 'check', 'query'), DESIGN_RULE
    else:
        from reference.session2_graph_trials import expectation, fill, instance
        fill(folder)
        expectation(folder, after='남김')     # 완성본은 수정본까지 반영한 상태라 기대 답도 그 뒤의 답이다
        title, initial = '그래프 구현과 검증', 'python run.py db\npython run.py load\npython run.py update\npython run.py usage'
        context, actions, rules = instance(folder), ('load', 'repeat', 'sensors', 'parts', 'update', 'usage', 'compare', 'export', 'check'), GRAPH_RULE + '\n' + DB_RULE
    write_metadata(folder, title + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단마다 갈래 하나를 골라 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.'
                   + (' Docker Desktop을 켠 뒤 실행합니다.' if starter.name == 'graph-lab' else ''), command=initial, extra_rules=rules)   # 완성본을 Codex로 열어도 같은 랩별 경계
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
    with D.for_course('통합반'):
        generate(parser, args, build)


def generate(parser, args, build):
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
