"""두 과정 2회차 그래프 구현 완성본만 생성한다."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from graph_model import load_model
from run_graph import batches

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import data_session2 as D   # noqa: E402  PR-07 7.4 값 한 곳
COURSE_ROOT = HERE.parents[3] / '산출물'
LAB = '02일차_실습4_그래프구현과검증'


def package(course):
    practical = course == '실전반'
    base = COURSE_ROOT/course/'실습/02회차'
    lab = base/'랩'/LAB
    target = base/'완성본'/(LAB+'_학생용완성본.zip')
    files = {}
    for p in lab.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts: continue
        name=p.relative_to(lab).as_posix()
        if p.name=='.env':files[name]=b'';continue
        if p.suffix in {'.pyc','.zip'} or p.name=='랩_연결.json':raise ValueError('시작본에 생성 파일이 있습니다: '+name)
        files[name]=p.read_bytes()
    source_names=['run_graph.py','graph_model.py']
    source_names+=['queries/part_usage.cypher','queries/supply_terms.cypher'] if practical else \
                  ['queries/part_assets.cypher','queries/asset_sensors.cypher','queries/asset_parts.cypher','queries/asset_counts.cypher']
    for name in source_names:files[name]=(HERE/name).read_bytes()
    inputs=lab/'입력'
    g=load_model(inputs);summary={'input_nodes':len(g['nodes']),'input_edges':len(g['rels'])}
    if not practical:   # 수정본 반영은 통합반 실습4만
        delta=batches(load_model(inputs,True),g)
        summary.update(patch_statements=len(delta),patch_targets=[x['parameters'].get('key') or [x['parameters'].get('a'),x['parameters'].get('b')] for x in delta])
    files['결과/input_check.json']=(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode()
    selections=(f'견적 단가는 최신 적용 견적에서, 승인 상태는 품목별 SCM 승인 목록에서 읽습니다. 구매 기준서 PR-07 7.4에 걸리는 승인 공급사(불량률 {D.PR74_RATE_PCT} % 초과)는 승인 상태를 바꾸지 않고, '
                f'입고 전수 검사와 비교에 더할 비용 {D.PR74_EXTRA_MANWON}만 원을 근거 줄과 함께 조회 결과에 돌려줍니다. 비승인 공급사도 빼지 않고 승인 상태와 함께 돌려줍니다. 값마다 출처(견적 줄 · 승인 등록 줄 · 기준일)는 모델에 들어 있는 속성을 조회로 돌려받은 것이니, 그 줄을 `입력/자료/`에서 열어 함께 확인하세요.' if practical else
                '설비별 센서는 구성 요소에 붙은 것과 설비 전체에 붙은 것을 함께 조회합니다. 단위·정상값·한계·상한/하한을 구별하고 없는 값은 null로 남깁니다. 설비별 교체 부품은 교체 부품이 없는 구성 요소도 null로 남깁니다.')
    prep_tail=' 결과가' if practical else ' 수정본에서 바뀌는 대상이'
    run_tail=('합니다.' if practical else '하고, 수정본의 바뀐 속성과 연결만 두 번 적용해 ID 유지와 중복 여부를 검사합니다.')
    look='품번별 사용처와 공급 조건(값마다 출처 포함)' if practical else '기준·수정 설비 목록, 품번별 사용처, 설비별 센서 · 교체 부품'
    asset_param='' if practical else " 설비 질의는 `:param asset => 'HYD-01'`(전체 설비는 `''`)을 먼저 실행합니다."
    guide=f'''# {course} 그래프 구현 완성본 실행

압축을 새 폴더에 풀고 `run_graph.py`가 있는 폴더를 VS Code에서 여세요. 이 완성본은 AI 계정 없이 Python 표준 라이브러리와 Docker로 실행할 수 있습니다.

1. 터미널에서 `python run_graph.py --prepare`를 실행하세요. 입력 ID와 관계 끝점을 확인하고{prep_tail} `결과/input_check.json`에 기록됩니다.
2. Docker Desktop이 실행 중일 때 `python run_graph.py`를 실행하세요. 이 폴더의 `lab_db.py`가 전용 Neo4j를 준비합니다. 기준 모델을 두 번 넣어 대상·관계 수를 비교{run_tail}
3. `결과/run_result.json`의 {look}를 원자료와 비교하세요. `python run_graph.py --part P-FAN-BRG`로 다른 부품도 조회할 수 있습니다. 결과 파일을 보관하려면 다른 품번 실행 전에 사본을 남기세요.
4. `python lab_db.py`로 같은 랩 DB의 Browser를 열어 `queries/`의 질의를 직접 실행할 수도 있습니다. 품번 질의는 `:param part => 'P-PMP-SEAL'`을 먼저 실행합니다.{asset_param}

{selections}

원자료와 제공 모델은 `입력/`에 남고, 결과는 `결과/`에 저장됩니다. 실습을 마친 뒤 같은 폴더를 다시 열어 결과 파일을 확인하세요.
'''
    guide=guide.replace('결과 파일을 보관하려면', '동봉된 결과는 이 입력으로 실행해 얻은 값입니다. 결과 파일을 보관하려면')
    files['결과/run_result.json']=(HERE/'완성결과'/(course+'.json')).read_bytes()
    files['완성본_실행.md']=guide.encode()
    record='# 조회 결과를 읽는 기준\n\n'+('' if practical else
        '설비 이름이 바뀌어도 같은 ID로 갱신합니다. 불용 설비는 이력을 위해 보존하고 현재 가동 중인 설비의 예비품 조회에서는 제외합니다. `입력/자료_변경분/2026-10-20_수정본/설비_대장_변경.csv`의 설비 이름·상태를 기준 및 수정 결과와 비교하세요. '
        '같은 자료를 다시 적용하면 `run_result.json`의 노드·관계 수가 같아야 합니다.\n\n')+(
        '같은 자료를 다시 적재해도 `run_result.json`의 노드·관계 수가 같아야 합니다.\n\n' if practical else '')+(
        '`PS-4510`은 `입력/자료/품번_교차표.csv`에서 사내 품번을 찾아 조회합니다. 비슷한 이름의 다른 부품 `P-PMP-SEAL-HT`와 없는 품번의 결과도 함께 표시합니다. ')+('' if practical else
        '`구성요소_변경.csv`의 확인된 품번과 기존 그래프의 공용 부품 추정 근거를 구분하세요. 중복 센서 행 정리는 센서 자체를 지운다는 의미가 아닙니다.')+'\n\n'+selections+'\n'
    files['결과/검증_기록.md']=record.encode()
    files['결과/query.cypher']=('\n\n'.join('// '+n+'\n'+files[n].decode('utf-8-sig').strip()+';' for n in source_names if n.endswith('.cypher'))+'\n').encode()
    target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.tmp')
    with ZipFile(tmp,'w') as z:
        for name,body in sorted(files.items()):
            info=ZipInfo(LAB+'/'+name,(2026,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;z.writestr(info,body)
    with ZipFile(tmp) as z:
        assert set(z.namelist())=={LAB+'/'+n for n in files}
        assert all(z.read(LAB+'/'+n)==v for n,v in files.items())
    tmp.replace(target)
    return {'과정':course,'경로':target.relative_to(COURSE_ROOT.parent).as_posix(),'파일수':len(files),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'입력':summary}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('course',choices=['통합반','실전반']);a=parser.parse_args();print(json.dumps(package(a.course),ensure_ascii=False))
