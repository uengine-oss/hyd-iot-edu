"""새 프로젝트의 실제 완료 기록과 사람의 대조를 별도 완성본에 묶는다.
원 실행·시작 ZIP은 읽기만 한다. 실제 반환을 재작성하거나 새 모델을 호출하지 않는다.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
from build_agent_labs import LAB, LEAD, TITLE
from lab_package import write_zip, student_files
from project_layout import write_metadata


def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, execution_evidence, out, review=None, review_evidence=None):
    source=Path(source).resolve();out=Path(out).resolve();execution_evidence=Path(execution_evidence).resolve()
    if not execution_evidence.is_file(): raise ValueError('실제 실행 근거 파일이 없습니다.')
    if not (source/'run.py').is_file(): raise ValueError('새 프로젝트 run.py가 있는 실제 실행 폴더를 지정합니다.')
    if source==LAB.resolve(): raise ValueError('학생 시작 프로젝트를 실제 실행 입력으로 쓰지 않습니다.')
    for path in student_files(LAB):
        name=path.relative_to(LAB)
        if str(name).startswith('app\\features') or name.parts[:2]==('app','features'): continue
        # UI와 README는 표시 파생물이다. 입력·실행·AI 규칙은 같은 판이어야 한다.
        if name.parts[:2]==('app','ui') or name==Path('README.md'): continue
        other=source/name
        if not other.is_file() or sha(other)!=sha(path): raise ValueError('제공 입력·실행 판이 다릅니다: '+name.as_posix())
    sys.path.insert(0,str(source))
    from app.utils.workflow import require_assessment, current_result
    from app.utils.evidence import EvidenceStore
    store=EvidenceStore(source); completed=[]; originals={}
    for path in sorted((source/'output/runs').glob('*/collection.json')):
        state=read(path);identity=state['request']['request_id']
        if state.get('status')!='collected': continue
        state,assessment,collected,assessed=require_assessment(source,identity,store)
        result=current_result(source,identity,store);plan=result and result.get('plan')
        if not plan or not plan.get('_provenance',{}).get('deliver_sha256'): raise ValueError(identity+': 현재 판의 점검 전달 결과가 없습니다.')
        if plan.get('delivery_status') != 'ready' or not plan.get('_provenance',{}).get('choices_sha256'):
            raise ValueError(identity+': 전달 요구가 미정이거나 선택 입력판 연결이 없습니다.')
        if not state.get('turns'): raise ValueError(identity+': 실제 모델 응답 참조가 없습니다.')
        for turn in state['turns']:
            record=source/turn['record'];reply=read(record)
            if reply.get('method') not in ['모델 서버','채팅으로 받음'] or not reply.get('response_text'): raise ValueError('실제 모델 응답 기록이 아닙니다: '+turn['record'])
            originals[record.relative_to(source).as_posix()]=sha(record)
        for file in [collected,assessed,collected.parent/'root_plan.json']: originals[file.relative_to(source).as_posix()]=sha(file)
        completed.append(identity)
    if not completed: raise ValueError('현재 입력·코드에 맞는 실제 완료 요청이 없습니다.')
    review_files={}
    if review:
        review=Path(review);evidence=read(Path(review_evidence)) if review_evidence else {}
        if evidence.get('review_sha256')!=sha(review): raise ValueError('검토 CSV와 검토 근거의 해시가 다릅니다.')
        expected={identity:sha(source/'output/runs'/identity/'collection.json') for identity in completed}
        if evidence.get('collection_sha256')!=expected: raise ValueError('검토가 대조한 실제 수집 판과 다릅니다.')
        rows=list(csv.DictReader(line for line in review.read_text(encoding='utf-8-sig').splitlines() if not line.startswith('#')))
        if not rows or set(row['request_id'] for row in rows)-set(completed): raise ValueError('검토 CSV가 다른 실행 요청을 가리킵니다.')
        review_files['app/features/review.csv']=review.read_bytes()
    stage=out.parent/(out.stem+'_build')/'root-cause-lab'
    if stage.exists(): raise ValueError('완성본 작업 폴더가 이미 있습니다. 다른 출력 이름으로 작업합니다.')
    shutil.copytree(LAB,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env','output'))
    for path in (source/'app/features').rglob('*'):
        if path.is_file() and path.suffix!='.pyc' and '__pycache__' not in path.parts:
            destination=stage/path.relative_to(source);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    # 현재 완료 요청만 포함한다. 미완료 요청이나 이전 계획을 현재 완성 결과와 섞지 않는다.
    needed=set(originals)
    for identity in completed:
        for path in (source/'output/runs'/identity).glob('*.json'):
            if path.name!='error.json': needed.add(path.relative_to(source).as_posix())
        state=read(source/'output/runs'/identity/'collection.json')
        for turn in state['turns']:
            request=source/'output/model_requests'/(turn['request_hash']+'.md')
            if request.is_file(): needed.add(request.relative_to(source).as_posix())
    for name in needed:
        destination=stage/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,destination)
    for name,raw in review_files.items(): (stage/name).write_bytes(raw)
    # 완성본에 제공하는 대조를 학생이 작성한 기록으로 표시하지 않는다.
    renderer=stage/'app/ui/render.py'
    display=renderer.read_text(encoding='utf-8')
    marker="section('records', '내가 작성한 요구·계획·대조', ''.join(records))"
    replacement="section('records', '완성본의 원자료 대조', '<p class=\"note\">실제 AI 응답을 원자료와 대조한 기록입니다. 원래 응답은 따로 보존합니다.</p>' + ''.join(records))"
    if marker not in display: raise ValueError('완성본 검토 출처를 표시할 위치가 없습니다.')
    renderer.write_text(display.replace(marker,replacement),encoding='utf-8',newline='\n')
    write_metadata(stage,TITLE,LEAD+' 실제 응답과 그 응답을 원문과 견준 기록을 별도로 읽는 완성본입니다.','python run.py --show')
    child=subprocess.run([sys.executable,'run.py','--show'],cwd=stage,capture_output=True,text=True,encoding='utf-8')
    if child.returncode: raise ValueError(child.stdout+'\n'+child.stderr)
    for name,expected in originals.items():
        if sha(stage/name)!=expected or sha(source/name)!=expected: raise ValueError('실제 기록이 변경됐습니다: '+name)
    entries=[('root-cause-lab/'+p.relative_to(stage).as_posix(),p.read_bytes()) for p in student_files(stage)]
    guide=LAB.parent/(LAB.name+'_guide.html')
    entries.append((guide.name,guide.read_bytes()));out.parent.mkdir(parents=True,exist_ok=True);write_zip(out,entries)
    report={'archive':str(out),'sha256':sha(out),'bytes':out.stat().st_size,'student_zip_sha256':sha(LAB.with_suffix('.zip')),'completed_requests':completed,'model_calls':0,'execution_evidence_sha256':sha(execution_evidence),'original_records':originals,'review_sha256':sha(review) if review else None,'review_actor':'제작 담당 Codex의 사후 원문 대조. 학생 작성 기록·독립 검토·현장 시간 실측이 아님.','render':{'stdout':child.stdout,'stderr':child.stderr,'html_sha256':sha(stage/'output/result.html'),'renderer_sha256':sha(renderer),'derivation':'완성본의 원자료 대조 제목·목적 표시만 변경. 학생 runtime/ZIP은 불변.'},'readme_derivation':{'review_items':['R1','R4'],'original_execution_sha256':sha(source/'README.md'),'student_readme_sha256':sha(LAB/'README.md'),'completed_readme_sha256':sha(stage/'README.md'),'purpose':LEAD+' 실제 응답과 그 응답을 원문과 견준 기록을 별도로 읽는 완성본입니다.','scope':'수행 전제가 없는 목적과 사람 비교 용어만 수정. 실제 실행 README는 불변. 원자료·AGENTS·런타임·핵심 함수·원응답의 동일성 검사는 유지하며 전체 파일 바이트가 실제 실행과 같다고 주장하지 않는다.'},'unverified':['새 폴더 재실행·원문 의미·네이티브 저장과 다시 열기 확인']}
    out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--execution-evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--review',type=Path);p.add_argument('--review-evidence',type=Path)
    a=p.parse_args();print(json.dumps(build(a.source,a.execution_evidence,a.out,a.review,a.review_evidence),ensure_ascii=False,indent=2))
