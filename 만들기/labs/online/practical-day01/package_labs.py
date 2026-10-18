"""검토된 실습 자료를 다운로드용 ZIP으로 묶는다. 실습은 실행하지 않는다."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast, json

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'산출물/실습/실전반_온라인'
downloads=BASE/'다운로드';downloads.mkdir(exist_ok=True)
rows=['# 실전반 온라인 1회차 실습 자료','','강사가 각 실습 자료를 내려받아 압축을 풀고 VS Code로 여는 장면부터 혼자 진행합니다. 질문에 대한 판단도 강사가 설명하고 AI 응답을 검토합니다. 학생 응답을 기다리는 수업을 전제하지 않습니다. 직접 실습·캡처는 이번 제작 범위에서 제외합니다.','', '| 실습 | 다운로드 | 가이드 | 설계 시간 |','|---|---|---|---:|']
minutes=[None]*4
for folder,mins in zip(sorted(BASE.glob('01일차_실습*')),minutes):
    dest=downloads/(folder.name+'.zip')
    with ZipFile(dest,'w',compression=ZIP_DEFLATED) as archive:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                archive.write(p,Path(folder.name)/p.relative_to(folder))
    with ZipFile(dest) as archive:assert archive.testzip() is None
    rows.append(f'| {folder.name} | [ZIP](다운로드/{dest.name}) | [가이드]({folder.name}/가이드.html) | 미확정 |')
rows += ['', '실습3은 `시작코드/`만 VS Code 작업 공간으로 엽니다. `코드/`는 별도 온라인 완성본이며 처음부터 AI에 보여 주지 않습니다. 시작본의 비교 함수는 의도적으로 비어 있고 입출력·테스트·자료는 제공됩니다. 전체 시스템을 맨땅에서 재구축하는 활동이 아닙니다.', '', '실습1·2·4도 자료 다운로드부터 시작하지만 목적에 맞게 Notion·환경 확인·관계도 도구로 이동합니다. 불필요한 코드를 억지로 만들지 않습니다.', '', '기존205분 견적은 철회했습니다. 실제 조작·응답 검토를 포함한 전체 시간은 미확정입니다. [시간견적](01회차_시간견적.md)을 확인하세요.']
(BASE/'01회차_실습_안내.md').write_text('\n'.join(rows),encoding='utf-8')
for p in (BASE/'01일차_실습3_기록추적/시작코드').glob('*.py'):ast.parse(p.read_text('utf-8'))
print('4 ZIP files checked; starter syntax checked without execution')
