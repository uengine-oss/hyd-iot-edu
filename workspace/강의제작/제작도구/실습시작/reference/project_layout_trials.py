"""새 프로젝트 ZIP 경계와 기존 랩 호환 검사. 학생 AI·DB를 실행하지 않는다."""
from pathlib import Path
import json
import sys
import tempfile
import zipfile
import shutil

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from lab_package import ROOT, pack, entry, student_files
from project_layout import write_metadata, errors
from verify_packages import check_zip, verify_lab
from lab_frame import step_page, guide_cost, answer_html, A, ask_ai


def main():
    work = (ROOT / '작업/검사/project-layout').resolve()
    work.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix='trial-', dir=work) as temp:
        base = Path(temp).resolve()
        assert base.is_relative_to(work) and base != work
        folder = base / 'sample-lab'
        files = {'run.py': 'print("자료 확인")\n', 'data/sample.csv': 'id\n1\n',
                 'app/features/sample.py': 'def decide(row):\n    raise NotImplementedError\n',
                 'app/ui/render.py': '# 결과 표시\n', 'app/utils/read.py': '# 자료 읽기\n'}
        for name, content in files.items():
            p = folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
        write_metadata(folder, '구조 확인', '제공 자료로 기능을 만듭니다.')
        guide = folder.with_name(folder.name + '_guide.html')
        guide.write_text('<section id="s1"><h2>01 실행</h2><details class="answer"><summary>정답 보기</summary></details></section>', encoding='utf-8')
        (folder / '.lab_connection.json').write_text('{"id":"test-only"}', encoding='utf-8')
        archive = pack(folder)
        item = entry('layout-trial', '통합반', 2, '구조 확인', 'trial', folder, guide_steps=['실행'])
        assert not check_zip(archive, folder)[0]
        verify_lab(item)
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            assert 'sample-lab/README.md' in names and 'sample-lab_guide.html' in names
            assert not any('.lab_connection.json' in n for n in names)
        records.append('영문 루트·바깥 가이드·DB 연결 제외·파일 바이트 통과')
        settings = json.loads((folder / '.vscode/settings.json').read_text(encoding='utf-8'))
        assert not settings['files.exclude'].get('AGENTS.md')
        assert settings['files.exclude']['**/__pycache__']
        records.append('AGENTS 표시·실행 캐시 숨김 통과')
        for invalid in ('한글-lab', 'Bad_Lab'):
            bad_folder = base / invalid
            shutil.copytree(folder, bad_folder)
            try:
                pack(bad_folder)
            except ValueError:
                pass
            else:
                raise AssertionError('잘못된 루트를 묶음: ' + invalid)
            assert check_zip(archive, bad_folder)[0]
            bad_archive = base / (invalid + '.zip')
            with zipfile.ZipFile(archive) as original, zipfile.ZipFile(bad_archive, 'w') as changed:
                for name in original.namelist():
                    changed.writestr(name.replace('sample-lab/', invalid + '/'), original.read(name))
            from lab_package import sha256
            bad_item = item | {'folder': invalid, 'path': bad_archive.relative_to(ROOT).as_posix(), 'sha256': sha256(bad_archive)}
            try:
                verify_lab(bad_item)
            except AssertionError as exc:
                assert 'kebab-case' in str(exc), exc
            else:
                raise AssertionError('잘못된 루트 검증 통과: ' + invalid)
        records.append('비영문·비표준 프로젝트 루트의 포장·ZIP·목록 검사 거부')
        natural = step_page('기능 구현', '자료를 보고 기능을 구현합니다.', [('자료 확인', '<p>자료를 열고 필요한 열을 확인합니다.</p>' + answer_html(A('확인한 자료로 요청합니다.', ask_ai('필요한 열을 설명해 줘.'))))])
        assert guide_cost(natural, ai_turns=2)['AI_대기'] == 3
        assert guide_cost(natural, (4.2, '실측'), ai_turns=2)['AI_대기'] == 4.2
        records.append('자연문 가이드 AI 요청 추정·명시 실측 우선 적용')
        packed = {p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}
        mutations = {
            '중복 안내': packed | {'data/README.md': b'duplicate'},
            '완성 결과 포함': packed | {'output/result.html': b'result'},
            '다른 AI 설정': packed | {'.github/copilot-instructions.md': b'other tool'},
            '옛 시작 안내': packed | {'START.md': b'old'},
            '비영문 경로': packed | {'data/자료.csv': b'data'},
            '화면 코드 누락': {k: v for k, v in packed.items() if not k.startswith('app/ui/')},
        }
        for label, modified in mutations.items():
            assert errors(modified), label
            records.append(label + ' 검출')
        guide.write_text('changed', encoding='utf-8')
        assert check_zip(archive, folder)[0]
        records.append('가이드와 ZIP 판 불일치 검출')
    index = json.loads((HERE / 'package-index.json').read_text(encoding='utf-8'))
    for item in index['labs']:
        if item['id'] in ('integrated-02-ontology', 'integrated-02-graph'):
            verify_lab(item)
            folder = (ROOT / item['path']).with_suffix('')
            assert not check_zip(ROOT / item['path'], folder)[0]
            records.append(item['id'] + ' 기존 ZIP 호환 통과')
    target = work / 'result.json'
    target.write_text(json.dumps({'passed': len(records), 'records': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 확인 통과: {target.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
