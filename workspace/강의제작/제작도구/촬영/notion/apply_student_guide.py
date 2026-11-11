"""검수한 Notion 학생 사진 가이드를 두 과정 랩 폴더와 한 파일 가이드(<랩>.html, lab_package.pack_page)에 반영한다.
build_student_guide.py로 만든 --draft와 원본 보존용 --backup이 필요하다.
확정 실습 대본/영상은 읽거나 고치지 않는다.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE.parents[1]/'실습시작'))
from lab_package import pack_page
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
    assert names=={p.name for p in (draft/'images').iterdir() if p.is_file()},'사진 경로집합 불일치'
    return data

def course_lab(course):
    return ROOT/f'workspace/강의제작/산출물/{course}/실습/01회차/랩/01일차_실습1_학습노트'

def preflight_targets(backup):
    backup=Path(backup).resolve()
    assert backup.is_relative_to((ROOT/'작업').resolve()),'백업은 작업 폴더 내부'
    for course in ('통합반','실전반'):
        lab=course_lab(course)
        assert lab.is_dir() and (lab/'가이드.html').is_file() and not (backup/course).exists(), course

def apply_course(draft,backup,course):
    """랩 폴더를 검수 출력(가이드.html · images/)으로 바꿔 끼우고 한 파일 가이드를 다시 만든다.
    바꾸기 전 랩 폴더와 한 파일 가이드는 backup/<과정>에 둔다. 랩 폴더에는 가이드가 여는 파일만 남는다(pack_page가 확인한다)."""
    draft=Path(draft).resolve(); backup=Path(backup).resolve()
    assert backup.is_relative_to((ROOT/'작업').resolve()),'백업은 작업 폴더 내부'
    lab=course_lab(course); page=lab.parent/(lab.name+'.html'); saved=backup/course
    if saved.exists():raise FileExistsError('기존 백업을 덮지 않습니다: '+str(saved))
    saved.mkdir(parents=True)
    shutil.copytree(lab,saved/lab.name)
    if page.exists():shutil.copy2(page,saved/page.name)
    before={p.relative_to(lab).as_posix():sha(p) for p in lab.rglob('*') if p.is_file()}
    shutil.rmtree(lab); lab.mkdir()
    shutil.copyfile(draft/'가이드.html',lab/'가이드.html')
    shutil.copytree(draft/'images',lab/'images')
    pack_page(lab)
    after={p.relative_to(lab).as_posix():sha(p) for p in lab.rglob('*') if p.is_file()}
    return {'course':course,'lab':lab.relative_to(ROOT).as_posix(),'page':page.relative_to(ROOT).as_posix(),'backup':saved.relative_to(ROOT).as_posix(),
            'before':before,'after':after,'page_sha256':sha(page),'guide_matches_draft':(lab/'가이드.html').read_bytes()==(draft/'가이드.html').read_bytes()}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--draft',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);a=ap.parse_args();proof=preflight(a.draft)
    preflight_targets(a.backup)
    results=[apply_course(a.draft,a.backup,c) for c in ['통합반','실전반']]
    assert results[0]['after']==results[1]['after'] and results[0]['page_sha256']==results[1]['page_sha256'],'두 과정 판이 다르다'
    (a.backup/'정본반영근거.json').write_text(json.dumps({'source_sha256':proof['source_sha256'],'generated_html_sha256':proof['html_sha256'],'courses':results,'actual_student_run':'미확인','publication':'미수행'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('두 과정 Notion 가이드와 한 파일 가이드 반영 완료. 실제 학생 수행 · 게시는 미확인.')

if __name__=='__main__':main()
