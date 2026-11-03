"""2회차 실습3의 수강생용 완성본을 새 작업 폴더에서 실행·검사한 뒤 별도 ZIP으로 묶는다."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import build_labs as labs

ROOT = labs.OUT
TOOLS = Path(__file__).resolve().parent / '완성본_설계'
LAB = '02일차_실습3_온톨로지설계'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def student_files(folder):
    files = {}
    for path in sorted(folder.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            if path.name.startswith('.env'):
                raise ValueError('환경 파일을 포함하지 않는 설계 실습만 묶을 수 있습니다.')
            files[path.relative_to(folder).as_posix()] = digest(path.read_bytes())
    return files


def bundle(course, workspace):
    is_supply = course == '실전반'
    session = ROOT / course / '실습/02회차'
    source = session / '랩' / LAB
    name = f'{course}_{LAB}_완성본'
    destination = session / '완성본' / (name+'.zip')
    before = student_files(source)
    folder = workspace/name
    shutil.copytree(source,folder)
    out = folder/'결과'
    shutil.copyfile(TOOLS/'모델실행.py',out/'모델실행.py')
    schema = labs.schema_for(is_supply,'A')
    schema.pop('branch',None)
    if is_supply:
        schema = {'classes':{'Supplier':schema['classes']['Supplier']}, 'relations':{'SUPPLIES':schema['relations']['SUPPLIES']},
                  'constraints':schema['constraints'][-2:]}
        schema['relations']['SUPPLIES']['properties'].update({'quote_source':'string','approval_source':'string','as_of':'string'})
        shutil.copyfile(TOOLS/'공급조건.py',out/'공급조건.py')
        purpose='부품을 쓰는 설비·구성 요소를 찾고, 기준일의 유효 견적과 SCM 승인 상태를 따로 확인합니다.'
        decision='공급 조건은 2026-10-15 기준으로 공급사·사내 품번별 가장 최근 유효 견적 한 건을 씁니다. SCM 등록 상태를 기준으로 승인과 조건부 승인을 포함하고 조건·기한을 함께 보존합니다. 비승인 상태도 견적과 구별해 남깁니다.'
    else:
        shutil.copyfile(TOOLS/'설비모델.py',out/'설비모델.py')
        dump(out/'표기_기준.json',{'구성요소_별칭':labs.NAME_ALIAS,'구성요소_이름':labs.CANON_NAME,
             '물리량_별칭':labs.WHAT_ALIAS,'단위_환산':labs.UNIT,'물리량_단위':labs.D.QUANTITIES})
        purpose='설비별 센서와 물리량, 단위·한계, 같은 부품을 쓰는 설비·구성 요소를 확인합니다.'
        decision='센서는 설비코드와 태그로, 부품은 사내 품번으로 구분합니다. 제조사 품번이 두 사내 품번에 걸리면 둘 다 표시합니다. 물리량의 기준 단위로 환산하고, 한계가 없는 채널에는 값을 채우지 않습니다.'
    dump(out/'설계_기준.json',schema)
    (out/'요구사항.md').write_text('# 이 모델로 확인할 질문\n\n'+purpose+'\n\n'+decision+'\n\n같은 이름·다른 품번과 없는 품번을 구분하고 입력 자료와 결과를 비교합니다.\n',encoding='utf-8')
    (out/'README.md').write_text('# 실행 결과\n\n모델실행.py가 자료를 읽어 schema.json, graph.json과 질문별_결과.json을 만듭니다. 명령을 실행할 때마다 이 세 파일을 다시 작성합니다.\n',encoding='utf-8')
    command='python -B -X utf8 결과/모델실행.py'
    help_text=f'''# {course} 2회차 온톨로지 설계 완성본

{purpose} ZIP 전체를 별도 폴더에 풀고, 이 문서가 있는 폴더에서 터미널을 열어 실행하세요. Python 3 표준 라이브러리를 사용합니다. AI 계정이나 그래프 DB 접속 없이 실행할 수 있습니다.

```text
{command}
```

기본 조회는 펌프 씰 품번 P-PMP-SEAL입니다. 다른 품번 또는 품명을 마지막에 붙이면 그 대상의 사용처를 확인합니다.

```text
{command} P-PMP-SEAL-HT
{command} NO-SUCH-PART
```

먼저 구조 검사의 출력을 보고, 부품을 쓰는 설비·구성 요소와 표시된 품번을 자료에서 찾아 확인하세요. 결과/질문별_결과.json에는 전체 설비의 센서·측정 항목과 부품별 사용처가 있습니다. 결과/자료_검토.md에서 원자료와 비교할 위치를 확인하세요.
'''
    (folder/'완성본_안내.md').write_text(help_text,encoding='utf-8')
    intro=(folder/'START.md').read_text(encoding='utf-8')
    (folder/'START.md').write_text(intro.split('\n',1)[0]+'\n\n완성한 모델을 실행하려면 [완성본 안내](완성본_안내.md)를 여세요. 아래는 이 모델이 푸는 원래 과제입니다.\n'+intro.split('\n',1)[1],encoding='utf-8')
    proc=subprocess.run([sys.executable,'-B','-X','utf8',str(out/'모델실행.py')],cwd=folder,text=True,encoding='utf8',capture_output=True)
    if proc.returncode:
        raise ValueError(proc.stdout + proc.stderr)
    result=json.loads((out/'질문별_결과.json').read_text(encoding='utf-8'))
    from csv import DictReader
    def relevant(file, predicate):
        with (folder/'자료'/file).open(encoding='utf-8-sig',newline='') as stream:
            return [f'{file} {i}행' for i,row in enumerate(DictReader(stream),2) if predicate(row)]
    lines=['# 원자료에서 확인한 내용', '',decision,'']
    if is_supply:
        for row in result['부품별 사용처']['P-PMP-SEAL']['공급 조건']:
            lines.append(f"- {row['공급사']}: {row['quote_source']}의 견적, {row['approval_source']}의 {row['approval_status']}. 단가 {row['price_manwon']}만원, 불량률 {row['defect_rate']:g}(비율), 납기 {row['lead_days']}일.")
        lines.extend(['','기간이 지난 견적과 같은 쌍의 이전 견적은 결과/견적_제외근거.json에서 확인합니다.'])
    else:
        lines.extend(['- 이관 코드와 현재 실물은 기능위치·일련번호로 대조했습니다. '+', '.join(relevant('설비_대장.csv',lambda x:x['상태']=='코드 통합')),
                      '- 철거 기록은 현재 설치된 구성 요소와 나눴습니다. '+', '.join(relevant('구성요소_목록.csv',lambda x:'철거' in x['비고'])),
                      '- W와 kPa로 온 값은 kW와 bar로 환산했습니다. '+', '.join(relevant('센서_목록.csv',lambda x:x['단위'] in ('W','kPa'))),
                      '- 공용 부품의 사용 설비: '+', '.join(result['부품별 사용처']['P-PMP-SEAL']['사용 설비'])+'. 예비품_목록.csv와 품번_교차표.csv에서 해당 품번과 대체 표기를 찾고 구성요소_목록.csv의 사용처와 비교합니다.'])
    (out/'자료_검토.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert before==student_files(source)
    package_files=student_files(folder)
    temp=workspace/(name+'.zip')
    with zipfile.ZipFile(temp,'w') as archive:
        for rel in package_files:
            entry=zipfile.ZipInfo(name+'/'+rel,(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry,(folder/rel).read_bytes())
    with zipfile.ZipFile(temp) as archive:
        assert archive.testzip() is None
        assert {n.split('/',1)[1]:digest(archive.read(n)) for n in archive.namelist()}==package_files
    destination.parent.mkdir(parents=True,exist_ok=True)
    os.replace(temp,destination)
    print(f'{destination} · {len(package_files)}개 파일 · {digest(destination.read_bytes())}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course',choices=['통합반','실전반'],required=True)
    parser.add_argument('--work',required=True,type=Path)
    args=parser.parse_args()
    args.work.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work) as temp:
        bundle(args.course,Path(temp).resolve())

