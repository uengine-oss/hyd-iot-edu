"""검수한 Notion 학생 사진 가이드를 두 과정 정본/ZIP에 반영한다.
build_student_guide.py로 만든 --draft와 원본 보존용 --backup이 필요하다.
확정 실습 대본/영상은 읽거나 고치지 않는다.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile,re,os
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
PRODUCTION={'예상시간.md','채울_화면.md','행동목록.json'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def preflight(draft):
    draft=Path(draft).resolve(); report=draft.parent/'학생가이드_사진근거.json'
    data=json.loads(report.read_text(encoding='utf-8'))
    assert sha(HERE/'학생가이드.json')==data['source_sha256'],'제작 원고와 검수 판본 불일치'
    assert sha(HERE/'build_student_guide.py')==data['builder_sha256'],'생성기와 검수 판본 불일치'
    assert sha(draft/'가이드.html')==data['html_sha256'],'검수 HTML 변경'
    source=json.loads((HERE/'학생가이드.json').read_text(encoding='utf-8'))
    assert len(data['photos'])==sum(len(s['photos']) for s in source['steps']) and data['sections']==len(source['sections']) and data['steps']==len(source['steps'])
    names=set()
    for p in data['photos']:
        name=Path(p['output']).name;names.add(name)
        assert sha(draft/'images'/name)==p['output_sha256'],name
    assert names=={p.name for p in (draft/'images').glob('*.png')},'사진 경로집합 불일치'
    return data

def course_lab(course):
    return ROOT/f'workspace/강의제작/산출물/{course}/실습/01회차/랩/01일차_실습1_학습노트'

def preflight_targets(backup):
    backup=Path(backup).resolve()
    assert backup.is_relative_to((ROOT/'작업').resolve()),'백업은 작업 폴더 내부'
    for course in ('통합반','실전반'):
        lab=course_lab(course); archive=lab.with_suffix('.zip')
        assert lab.is_dir() and archive.is_file() and not (backup/course).exists()
        assert not archive.with_name(archive.name+'.student.tmp').exists()
        for name in ('가이드.html','학습노트_입력틀.md','참고_교재_발췌.md'):assert (lab/name).is_file(),name
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for image in (lab/'images').glob('*'):
                name='01회차/랩/'+lab.name+'/images/'+image.name
                assert image.is_file() and re.fullmatch(r'n[0-9]{2}[-a-z0-9]+\.png',image.name) and name in z.namelist() and z.read(name)==image.read_bytes(), '출처를 확인할 수 없는 사진: '+str(image)

def input_sheet():
    data=json.loads((HERE/'학생가이드.json').read_text(encoding='utf-8'))
    lines=['# 주제 갤러리 입력 자료','','가이드의 해당 단계에 사용하는 예시 문구입니다. 자신의 주제를 만들 때는 제목과 소개를 자신의 내용으로 바꾸세요.']
    for step in data['steps']:
        if step['inputs']:
            lines.extend(['','## '+step['title']])
            for value in step['inputs']:lines.extend(['','```text',value,'```'])
    return '\n'.join(lines)+'\n'

def apply_course(draft,backup,course):
    draft=Path(draft).resolve(); backup=Path(backup).resolve()
    assert backup.is_relative_to((ROOT/'작업').resolve()),'백업은 작업 폴더 내부'
    lab=course_lab(course)
    archive=lab.with_suffix('.zip'); saved=backup/course
    if saved.exists():raise FileExistsError('기존 백업을 덮지 않습니다: '+str(saved))
    saved.mkdir(parents=True)
    shutil.copytree(lab,saved/lab.name);shutil.copy2(archive,saved/archive.name)
    before={p.relative_to(lab).as_posix():sha(p) for p in lab.rglob('*') if p.is_file()}
    for name in PRODUCTION:
        p=lab/name
        if p.exists():
            assert sha(p)==sha(saved/lab.name/name)
            p.unlink()
    shutil.copyfile(draft/'가이드.html',lab/'가이드.html')
    (lab/'학습노트_입력틀.md').write_text(input_sheet(),encoding='utf-8',newline='\n')
    for old in (lab/'images').glob('*.png'):
        if not (draft/'images'/old.name).is_file():
            assert sha(old)==sha(saved/lab.name/'images'/old.name)
            old.unlink()
    (lab/'images').mkdir(exist_ok=True)
    for p in (draft/'images').glob('*.png'):shutil.copyfile(p,lab/'images'/p.name)
    prefix='01회차/랩/'+lab.name+'/'
    expected={prefix+p.relative_to(lab).as_posix():p.read_bytes() for p in lab.rglob('*') if p.is_file()}
    tmp=archive.with_name(archive.name+'.student.tmp')
    if tmp.exists():raise FileExistsError(tmp)
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in sorted(expected.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,content)
    with zipfile.ZipFile(tmp) as z:
        assert set(z.namelist())==set(expected)
        assert all(z.read(n)==v for n,v in expected.items())
        assert not any(Path(n).name in PRODUCTION or '/대본/' in n for n in z.namelist())
    os.replace(tmp,archive)
    assert {p.name for p in (lab/'images').glob('*.png')}=={p.name for p in (draft/'images').glob('*.png')}
    after={p.relative_to(lab).as_posix():sha(p) for p in lab.rglob('*') if p.is_file()}
    preserved={n:h for n,h in before.items() if n not in PRODUCTION|{'가이드.html','학습노트_입력틀.md'} and not n.startswith('images/')}
    assert all(after[n]==h for n,h in preserved.items())
    return {'course':course,'lab':lab.relative_to(ROOT).as_posix(),'zip':archive.relative_to(ROOT).as_posix(),'backup':saved.relative_to(ROOT).as_posix(),'before':before,'after':after,'zip_sha256':sha(archive),'zip_files':len(expected),'zip_bytes_match':True,'zip_path_set_equal':True,'guide_matches_generated':(lab/'가이드.html').read_bytes()==(draft/'가이드.html').read_bytes(),'preserved_existing_student_files':len(preserved),'removed_production_files':sorted(PRODUCTION),'script_removed_from_zip_only':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--draft',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);a=ap.parse_args();proof=preflight(a.draft)
    preflight_targets(a.backup)
    results=[apply_course(a.draft,a.backup,c) for c in ['통합반','실전반']]
    assert set(results[0]['after'])==set(results[1]['after'])
    (a.backup/'정본반영근거.json').write_text(json.dumps({'source_sha256':proof['source_sha256'],'generated_html_sha256':proof['html_sha256'],'courses':results,'actual_student_run':'미확인','offline_P96':'별도 오프라인 묶음의 현장 접속/MCP 불가 대안 미확인','publication':'미수행'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('두 과정 Notion 가이드와 해당 ZIP 적용·경로집합/바이트 검증 완료. 실제 학생 수행/오프라인 대안/게시 미확인.')
if __name__=='__main__':main()
