"""승인 Excel 순서에 따른 2회차 도입과 과정별 첫 UI 안내. 기존 본문을 보존한다."""
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(__file__).parent/'도입'

def first_paragraph(text, paragraph):
    heading=text.index('\n## ')
    start=text.index('\n\n',heading)+2
    end=text.index('\n\n',start)
    return text[:start]+paragraph+text[end:]

def main():
    for course in ('통합반','실전반'):
        folder=ROOT/'산출물'/course/'실습/02회차/대본'
        query=next(folder.glob('*_관계조회.md'))
        if course=='통합반':
            render=runpy.run_path(str(ROOT/'제작용/촬영/neo4j/sync_integrated_script.py'))['render']
            query.write_text(render(),encoding='utf-8')
        else:
            text=query.read_text(encoding='utf-8')
            header=text[:text.index('## 자료를 내려받고 작업 공간 열기')]
            intro=(SOURCE/f'관계조회_{course}.md').read_text(encoding='utf-8')
            ui_path=SOURCE/f'Neo4j_첫화면_{course}.md'
            ui=(ui_path if ui_path.exists() else SOURCE/'Neo4j_첫화면.md').read_text(encoding='utf-8')
            body=(SOURCE/f'관계조회_{course}_본문.md').read_text(encoding='utf-8')
            query.write_text(header+intro.rstrip()+'\n\n'+ui.rstrip()+'\n\n'+body.rstrip()+'\n',encoding='utf-8')

        mapping={
            '지식지도탐색':'앞 실습에서는 사이퍼로 설비의 센서와 교체 부품을 찾아봤습니다. 이번에는 HYD 포털의 지식 지도를 직접 눌러 같은 종류의 연결을 따라가 보겠습니다. 화면에서 대상의 종류와 속성, 관계 방향을 확인하고, 방금 쓴 실습 DB와 포털의 기준 지도가 별도라는 점도 구분하겠습니다.',
            '온톨로지설계':('앞에서는 준비된 그래프를 사이퍼로 조회하고, 포털의 지식 지도에서도 연결을 살펴봤습니다. 이제는 우리가 답하고 싶은 질문에 맞춰 지식 구조를 직접 만들겠습니다. 설비·센서·부품 자료에서 대상과 연결 기준을 정하고, 스키마와 예시 데이터를 만든 뒤 원자료와 대조하겠습니다. 실습 시작 도구에서 통합반의 온톨로지 설계를 선택해 새 작업 폴더를 열겠습니다.' if course=='통합반' else '앞에서는 준비된 그래프를 조회하고 포털의 기준 지도를 살펴봤습니다. 이번에는 부품이 어느 설비에서 쓰이고 어떤 공급 조건이 있는지 함께 찾을 수 있도록 모델을 확장하겠습니다. 설비·부품 자료와 공급 조건을 연결해 스키마와 데이터를 만들고, 원자료의 품번과 조건이 그대로 구별되는지 확인하겠습니다. 실습 시작 도구에서 실전반의 온톨로지 설계 자료를 열겠습니다.'),
            '그래프구현과검증':('앞 실습에서는 현장 자료로 스키마와 예시 데이터를 설계했습니다. 이번에는 그 구조를 별도 그래프 DB에 옮기고, 센서·물리량·교체 부품을 묻는 질문에 예상한 답이 나오는지 확인하겠습니다. 같은 데이터를 다시 넣어도 중복되지 않는지까지 보겠습니다. 실습 시작 도구에서 그래프 구현 자료를 열고 입력 폴더의 앞 단계 완성본을 사용하겠습니다. 개인 설계 결과를 쓰려면 원자료 검토 기록도 함께 가져오면 됩니다.' if course=='통합반' else '앞 실습에서는 부품의 사용 설비와 공급 조건을 연결하는 모델을 만들었습니다. 이번에는 그 모델을 별도 그래프 DB에 적재하고 품번으로 사용 설비와 공급 선택지를 직접 조회하겠습니다. 원자료의 조건이 빠지지 않았는지, 같은 데이터를 다시 넣어도 중복되지 않는지 확인합니다. 실습 시작 도구에서 그래프 구현 자료를 열겠습니다. 앞 단계 완성 모델이 제공되므로 개인 결과가 없어도 시작할 수 있습니다.')}
        if course=='실전반':
            mapping['조치조건표']='앞 이론에서는 작업 순서를 나타내는 SOP와 조건에 따라 판단을 나누는 DMN의 차이를 배웠습니다. 이번에는 제공된 작업 기준에서 경고·감점·제외 조건을 찾아 표로 만들겠습니다. 경계값과 여러 조건이 겹치는 사례를 대입하고, 판단의 근거가 원문에 있는지 확인할 거예요. 실습 시작 도구에서 조치 조건표 자료를 열겠습니다.'
        for name,paragraph in mapping.items():
            path=next(folder.glob(f'*_{name}.md'))
            text=first_paragraph(path.read_text(encoding='utf-8'),paragraph)
            if course=='통합반' and name=='온톨로지설계':
                marker='현장 자료와 준비된 양식을 먼저 도우미와 살펴보겠습니다.'
                if 'AI 채팅은 자료를 함께 살펴보고' not in text:
                    text=text.replace(marker,'''앞에서 파일과 터미널을 사용했으니 이번에는 AI 채팅을 열겠습니다. AI 채팅은 자료를 함께 살펴보고 작성이나 수정을 요청하는 곳입니다. 채팅을 열고 현재 작업 폴더가 이번 설계 실습인지 확인하겠습니다. 먼저 자료를 읽고 근거를 알려 달라고 요청할게요. 아직 파일을 바꾸라는 요청은 하지 않겠습니다.

> [조작] 설치된 Copilot 또는 Codex의 실제 채팅 버튼 위치·이름을 확인해 가리키고 클릭한다. 화면을 확인하지 않은 버튼명·위치를 낭독하지 않는다. 아래 탐색 요청을 실제 입력하고 전송한다. 응답에서 제시한 파일을 탐색기로 열어 근거를 대조하는 장면까지 보여 준다. 두 제품을 한 화면의 기능처럼 섞지 않는다.

'''+marker)
            path.write_text(text,encoding='utf-8')
    print('2회차 9편 도입·첫 UI 안내 동기화')

if __name__=='__main__':main()
