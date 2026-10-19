"""강사 단독 진행과 다운로드부터 시작하는 실습 대본을 구성한다."""
from pathlib import Path
import shutil, re

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'산출물/실습/실전반_온라인'
SCRIPTS=ROOT/'산출물/교재/대본/실전반_온라인/01회차'
items=[('01','02_실습_학습노트.md','01일차_실습1_학습노트','학습노트_입력틀.md'),('02','04_실습_실행환경.md','01일차_실습2_실행환경','환경_확인표.md'),('03','06_실습_전체과정관찰.md','01일차_실습3_기록추적','README.md'),('04','08_실습_관계그림.md','01일차_실습4_관계그림','관계_검토표.md')]
for sid,name,folder,first in items:
    p=SCRIPTS/name;t=p.read_text('utf-8')
    opened=folder+'/시작코드' if sid=='03' else folder
    start=f'''## 시작. 자료를 받아 작업 폴더 열기

> [화면 {sid}-START] 실습 자료 다운로드 → 압축 해제 → VS Code 폴더 열기 → 탐색기. 화면은 후속 삽입 자리다. 다운로드 링크는 배포한 {folder}.zip을 연결한다. 실제 실습·캡처는 이번 문서 제작에서 수행하지 않는다.
> [조작] 이전 실습 파일을 닫는다. 수업 자료의 해당 ZIP을 내려받고 파일 탐색기에서 압축을 푼다. VS Code를 열어 파일 → 폴더 열기로 `{opened}`를 선택한다. 출처를 확인한 자료만 작업 공간 신뢰 여부를 판단한다. 파일 하나만 열거나 ZIP 내부에서 편집하지 않는다.

이번 실습 자료부터 받겠습니다. 같은 회차에도 실습이 여러 개 있으니까 파일 이름을 먼저 확인하겠습니다. 다운로드한 파일을 열어 보면 압축된 묶음입니다. 이 안에서 바로 수정하지 않고, 작업할 위치에 압축을 풀겠습니다.

이제 VS Code를 열겠습니다. 파일에서 폴더 열기를 선택하고, 방금 압축을 푼 폴더로 이동합니다. {'여기서는 시작코드를 선택하겠습니다. 완성된 코드를 먼저 읽지 않고 입력 자료부터 확인하면서 만들어 보겠습니다.' if sid=='03' else '이번 실습 폴더를 선택하겠습니다. 이전 실습 폴더와 섞이지 않도록 이름을 확인합니다.'}

왼쪽 탐색기에 파일 목록이 보입니다. 이 폴더가 지금 작업할 공간입니다. 파일 하나만 열었을 때와 달리, 자료와 결과를 같은 위치에서 관리할 수 있습니다. {'README부터 열겠습니다. 무엇을 만드는지, 어떤 자료를 읽는지 먼저 확인하겠습니다.' if sid=='03' else first+'부터 열겠습니다. 이 양식을 따라 오늘 남길 결과와 확인할 항목을 먼저 보겠습니다.'}

> [조작] 읽기 전용 입력과 수정할 파일, 결과가 저장될 위치를 차례로 짚는다. 전체 경로에 개인 사용자 이름이 보이면 화면에서 제외한다.

{'자료는 recorded에 있고, 제가 만들 부분은 trace_records의 검사 함수입니다. 결과는 result에 저장하겠습니다. 입력을 정답에 맞춰 바꾸는 것이 아니라, 그 입력을 어떻게 판단할지 코드를 작성하는 겁니다.' if sid=='03' else '지금 연 자료는 작업 순서와 결과를 남길 틀입니다. 필요한 부분을 읽고 실제 작업 도구로 이동하겠습니다. 작업을 마친 뒤에는 이 폴더로 돌아와 근거와 결과를 정리하겠습니다.'}

'''
    pos=t.find('\n## ')
    t=t[:pos+1]+start+t[pos+1:]
    # 수강생의 실시간 응답을 전제하지 않는다.
    replacements={'먼저 여러분의 판단을 적어 보세요.':'먼저 제가 어떤 기준으로 판단할지 정리하겠습니다.', '먼저 찾아보세요.':'먼저 찾아보겠습니다.', '먼저 생각해 보세요.':'먼저 생각해 보겠습니다.', '생각해 보세요.':'생각해 보겠습니다.', '비교해 보세요.':'비교해 보겠습니다.', '설명해 보세요.':'설명하겠습니다.', '적어 보세요.':'적겠습니다.', '골라보세요.':'고르겠습니다.', '확인해 보세요.':'확인하겠습니다.', '연결해 보세요.':'연결하겠습니다.', '잡아 보세요.':'잡겠습니다.'}
    lines=[]
    for line in t.splitlines():
        if not line.startswith(('>','#')):
            for a,b in replacements.items():line=line.replace(a,b)
        lines.append(line)
    p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    guide=BASE/folder/'가이드.html';html=guide.read_text('utf-8')
    intro=f'<section><h2>시작 · 실습 자료 다운로드와 작업 공간</h2><p>배포된 {folder}.zip을 내려받아 압축을 풉니다. VS Code의 폴더 열기로 {opened}를 엽니다. 파일 하나만 열거나 ZIP 안에서 편집하지 않습니다. 입력·수정 파일·결과 위치를 탐색기에서 확인한 뒤 아래 단계로 진행합니다.</p><div class="capture" data-shot="{sid}-START"><b>화면 {sid}-START · 후속 삽입 자리</b><p>다운로드한 ZIP, 압축 해제한 폴더, VS Code 폴더 열기와 탐색기. 개인 경로 제외.</p></div></section>'
    html=html.replace('<section>',intro+'<section>',1)
    guide.write_text(html,encoding='utf-8')
    shots=BASE/folder/'채울_화면.md'
    shots.write_text(shots.read_text('utf-8')+f'\n\n## {sid}-START\n다운로드 → 압축 해제 → VS Code 폴더 열기 → 입력·수정·결과 위치 확인.\n',encoding='utf-8')

# 시작본의 검사 함수만 비운다. 완성본은 다른 폴더로 유지한다.
lab=BASE/'01일차_실습3_기록추적';starter=lab/'시작코드';starter.mkdir(exist_ok=True)
for name in ['recorded','.github']:
    shutil.copytree(lab/'코드'/name,starter/name,dirs_exist_ok=True)
for name in ['test_trace_records.py']:
    shutil.copy2(lab/'코드'/name,starter/name)
text=(lab/'코드/trace_records.py').read_text('utf-8')
text=re.sub(r'(def check_link\(.*?\):)\n.*?(?=\n\ndef inspect_records)',r'\1\n    """입력의 존재와 일치 여부를 구분해 연결 판정을 만든다."""\n    raise NotImplementedError("참조 비교 규칙을 먼저 설명한 뒤 이 함수를 구현하세요.")\n',text,flags=re.S)
(starter/'trace_records.py').write_text(text,encoding='utf-8')
(starter/'README.md').write_text('''# 기록 추적기 시작 자료

먼저 recorded/case_a.json에서 작업지시의 판단 참조와 판단의 식별자를 찾습니다.
수정할 곳은 trace_records.py의 check_link 함수 한 개입니다. 나머지 입출력과 검사 틀은 제공됩니다.
값 없음·불일치·일치의 규칙을 말로 설명한 뒤 한 함수만 AI와 구현합니다.
함수를 작성하기 전에 실행하면 NotImplementedError가 발생하도록 비워 둔 시작본입니다. 실제 장애가 아닙니다.
구현 후 python trace_records.py, python -m unittest -v로 확인하도록 구성했습니다. 이번 제작에서는 새 실행을 하지 않았습니다.
입력 자료는 수정하지 않습니다. 결과는 result에 저장됩니다.
''',encoding='utf-8')
print('4 scripts now start from download; separate starter prepared without execution')
