"""Build the two course-specific final lab starters from approved sources."""
from html import escape
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[5]
SOURCES = ROOT/'it/process/definitions'
MANUAL = ROOT/'it/portal/www/samples/HI-01_shift-inspection-supplement.md'


def build(course, day, emphasis, notebook):
    parent=ROOT/f'workspace/강의제작/산출물/{course}/실습/{day:02}회차'
    folder=parent/'랩/shift-handover'
    (folder/'source').mkdir(parents=True,exist_ok=True)
    (folder/'output').mkdir(exist_ok=True)
    (folder/'source/inspection-manual.md').write_bytes(MANUAL.read_bytes())
    for source,target in [('shift_handover.bpmn','handover.bpmn'),('shift_handover.mapping.json','mapping.json')]:
        (folder/'source'/target).write_bytes((SOURCES/source).read_bytes())
    readme=f'''# {course} {day}회차 — 교대 인수인계

{emphasis}

기존 수업 시스템에서 새 인계안을 만들고 두 사람이 검토합니다. 재설치·재clone·별도 서버 주소 입력은 없습니다. 설치 폴더의 시작.bat을 실행하고 마지막에 표시된 포털을 엽니다. 기본 A/B/C와 앞 실습 결과는 유지합니다. 학생 시작본에는 강의 키가 들어 있지 않습니다.

안내.html을 열어 순서와 판정 조건을 확인하세요. source는 강사 제공 입력이며 이번 학생의 실제 조회 결과가 아닙니다. output은 학생이 저장할 결과의 자리입니다. 이번 과제의 에이전트 지침·조회 결과·인계안 완성본은 제공하지 않습니다.

완료 기준: 보충 문서의 원문/제안 대조와 추가 적재 → 자기 에이전트 배정 → 별도 교대 흐름 등록/시작 → 인계자 검토 → 인수자 확인 또는 보완 → 같은 처리 건의 완료와 남은 확인 사항 저장입니다. 인수 확인을 설비 조치·발주·정비 완료로 기록하면 안 됩니다.
'''
    (folder/'README.md').write_text(readme,encoding='utf8')
    (folder/'START.md').write_text('''# 이번에 할 일

교대 인수인계 담당자로서 제공 자료와 현재 설비·정비·ERP를 대조하는 에이전트를 만들고 제공 교대 흐름에 연결하세요. 대상·기준시각·작업 메모와 확인할 사실을 자기 말로 정리한 뒤 계획을 요청하세요. 안내.html의 순서와 판정 조건을 사용합니다.

확인 사례: 조회 자료가 메모와 일치하는 경우에는 해당 근거를 남깁니다. 업무가 없다는 정상 응답, 자료 누락, 출처 조회 실패를 서로 다르게 기록합니다. 메모의 완료 주장과 열린 작업지시가 다르면 해결되지 않은 차이를 남깁니다. 인수자의 실제 보완 요청은 같은 처리 건에서 반영합니다. 인수 확인은 정비·설비 조치가 아니며, 없는 완료를 만들거나 쓰기 도구를 호출하면 완료 기준을 충족하지 못합니다.

AI 실행이 멈추면 같은 처리 건과 원천 응답을 보존해 원인을 먼저 확인하세요. 완료 뒤 output/README.md의 항목을 저장하고 다시 열어 근거를 대조하세요. 처음부터 맞은 결과에 고의 오류를 넣을 필요는 없습니다.
''',encoding='utf8')
    (folder/'AGENTS.md').write_text('''# 작업 범위

이 폴더는 교대 인수인계 수업 시작본이다. 제공 문서와 기존 설비·정비·ERP 조회만 사용한다. 학생에게 목표·대상·기준시각·확인할 사실을 먼저 물어 짧은 계획을 세운다. 실제 조회 없이 완료 결과를 채우지 않는다. 키·강사 코드·외부 주소를 만들거나 요청문에 넣지 않는다.

제공 BPMN의 조회/초안·인계자 검토·인수자 보완/확인 구조와 원래 필드 이름은 유지한다. 변경 허용 범위는 화면 표시 이름과 조회 에이전트 배정이다. 원문에 없는 담당자·기한·완료를 만들지 않는다. 에이전트의 쓰기·설비 조치 도구를 추가하지 않는다. 출처의 시각·판본·연결 키, 자료 없음과 조회 실패, 현재 재고와 입고 예정을 구분한다. output에 학생이 확인한 결과와 미확인을 함께 저장한다.
''',encoding='utf8')
    (folder/'output/README.md').write_text('''# 저장할 결과

실제 작업 후 문서 적재 배치/판본, 에이전트 ID, 교대 흐름 판본, 처리 건 ID, 기준시각, 조회 출처·원천 결과 위치, 네 영역의 확인/모순/미확인, 사람 검토와 보완 사유, 최종 상태를 기록한다. 조회 결과의 사실과 작업 메모의 주장을 구분한다. 다른 PC에서도 이해할 수 있게 상대 경로를 사용한다. 키·강사 코드는 저장하지 않는다.
''',encoding='utf8')
    stages=[
        ('1. 시작과 업무 범위',f'''{emphasis} 대상 설비, 인계할 교대, 실제 기준시각, 전달받은 작업 메모를 자기 말로 정리합니다. 수업 중 실제 대상과 시각을 사용하며 예시 시각을 현재 값으로 복사하지 않습니다. 앞 실습 결과가 없어도 제공 보충 문서와 기존 시스템으로 시작할 수 있습니다. 포털 왼쪽 「수업 기능」이 「교대 실습」 상태인지 확인합니다. 코드가 없거나 거절되면 강사에게 확인하고 잠금을 우회하지 않습니다.'''),
        ('2. 보충 문서 추가 적재','''「매뉴얼 → 지식화」에서 source/inspection-manual.md를 선택합니다. 기존 쿨러·정비·구매 매뉴얼 목록과 배치를 먼저 기록합니다. 같은 보충 문서가 이미 적재되어 있으면 해당 판본과 원문을 확인해 재사용하고 재추출하지 않습니다. 새 문서라면 미리보기→에이전트 추출→원문과 절·단계·근거 대조→검토한 항목만 적재합니다. HI-01의 세 절차는 참고용이며 설비를 직접 실행하는 조치가 아닙니다. 불완전하거나 실패한 제안을 적재하지 않고 같은 처리 건의 오류·응답을 보존해 보완합니다. 추가 뒤 기존 세 문서의 배치가 그대로인지 확인합니다.'''),
        ('3. 자기 에이전트와 스킬','''「에이전트」에서 교대에 필요한 짧은 검토 스킬과 에이전트를 만듭니다. 목표와 확인할 출처·완료 기준을 먼저 설명하고 코딩 도우미의 제안은 원자료에 대조합니다. 업무 규칙은 「교대 인수인계」, 모델은 수업 기본값, 도구는 설비 지식·업무 자료·설비 이력의 조회 범위에서 선택합니다. 설비, 열린 작업지시, 현재 재고/입고 예정, 작업 메모의 네 영역을 확인해야 합니다. 메모의 완료 주장과 열린 작업지시의 모순, 조회 결과 없음과 출처 오류를 구별하는 기준을 직접 작성합니다. 도구 관리·임의 질문·다른 모델·쓰기 기능은 열리지 않습니다.'''),
        ('4. BPMN과 포털 연결','''source/handover.bpmn을 bpmn.io에서 열어 초안→인계자 검토→인수자 확인/보완→완료와 세 번의 초안 범위를 확인합니다. 표시 이름과 그림 배치는 바꿀 수 있으며 작업·연결·승인 조건을 추가하거나 제거하지 않습니다. 포털 「흐름」에서 이 파일을 가져옵니다. 흐름 ID는 제공 파일의 ShiftHandover를 유지합니다. source/mapping.json을 대조해 시작 입력 네 개와 각 작업의 부품·사람 역할·분기 조건을 연결합니다. 인계안 작성·보완 1·보완 2의 세 에이전트 칸에는 3단계에서 만든 자기 에이전트를 모두 배정합니다. 「검사」의 누락을 고친 뒤 「판본 등록」을 합니다. 기본 A/B/C의 매핑이나 배포는 바꾸지 않습니다. 임의 코드가 자동으로 포털 작업에 연결되는 것은 아닙니다.'''),
        ('5. 같은 처리 건에서 검토와 보완','''등록한 교대 판본을 시작하고 네 입력을 채웁니다. 포털의 「나」를 인계자 김운전으로 선택해 실제 초안·조회 근거를 검토합니다. 자료가 없거나 모순이면 미확인과 다음 확인 행동을 남깁니다. 승인 후 「나」를 인수자 최운전으로 바꾸어 근거와 남은 요청을 대조합니다. 보완할 사실이 있으면 사유를 적어 같은 건을 돌려보내고 보완된 초안과 인계자 재검토를 확인합니다. 처음부터 맞은 결과에 고의 오류를 넣지 않습니다. 인수 확인은 인계 기록만 남긴다는 확인을 한 뒤 제출합니다. 처리 건의 종료 상태와 미확인 항목을 확인하며 인수 확인을 정비 완료로 바꾸지 않습니다.'''),
        ('6. 실패 복구와 저장','''AI가 질문/권한 요청/실패로 멈추면 처리 건 ID·작업 ID·질문·호출 기록·원천 응답을 보존합니다. 새 건을 반복 시작하거나 DB/컨테이너를 지우지 말고 원인을 강사와 확인해 같은 건의 보완/재시도를 사용합니다. 통신 실패를 업무 없음으로 쓰지 않습니다. 완료 후 output에 적재 판본, 에이전트, 흐름 판본과 처리 건 ID, 조회 기준시각/근거, 사람 검토, 보완 사유, 완료·미확인 구분을 저장합니다. 다시 열어 각 주장으로부터 원문·조회 결과로 돌아갈 수 있어야 합니다.''')]
    stages.append(('7. Notion 학습노트 기록',notebook))
    body=''.join(f'<section><h2>{escape(title)}</h2><p>{escape(text)}</p></section>' for title,text in stages)
    html=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{course} 교대 인수인계</title><style>body{{max-width:850px;margin:40px auto;padding:0 22px;font:17px/1.85 system-ui;color:#182535;background:#f5f7fa}}section{{background:white;padding:18px 25px;margin:18px 0;border-radius:10px}}h1{{font-size:30px}}h2{{font-size:22px}}a{{color:#155ca4}}</style><h1>{course} {day}회차 · 교대 인수인계</h1><p>여러 출처를 대조한 인계안을 만들고 두 사람이 검토하여 다음 교대가 이어 확인할 일을 남깁니다.</p><p>학생 시작본 · 화면 사진은 포함하지 않습니다. 실제 결과는 자기 처리 건에서 확인하고 저장합니다.</p><p><a href="source/inspection-manual.md">보충 문서</a> · <a href="source/handover.bpmn">제공 BPMN</a> · <a href="source/mapping.json">연결 기준</a> · <a href="output/README.md">저장 항목</a></p>{body}</html>'''
    (folder/'안내.html').write_text(html,encoding='utf8')
    target=folder.with_suffix('.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(folder.parent))
    readme_path=parent/'README.md'
    text=readme_path.read_text(encoding='utf8')
    marker='## 현재 교대 인수인계 시작본'
    if marker not in text:
        first,rest=text.split('\n',1)
        text=first+'\n\n'+marker+'\n\n[현재 가이드](랩/shift-handover/안내.html) · [학생 시작 ZIP](랩/shift-handover.zip). 기존 PC와 강사 코드 해제 방식으로 보충 문서·자기 에이전트·제공 BPMN·사람 검토/보완을 연결합니다. 아래 이전 제작판과 구별합니다. 이 시작본 제공은 새 촬영·전체 강의 영상 검증 완료를 뜻하지 않습니다.\n'+rest
        readme_path.write_text(text,encoding='utf8')
    return str(folder.relative_to(ROOT))


if __name__=='__main__':
    # 7단계 문장: 통합반 실라버스 117행 · 실전반 96행(Notion 학습노트 기록, 미연결이면 Markdown을 직접 붙여 정리)
    for course,day,emphasis,notebook in [('통합반',11,'원문에서 추가한 지식이 조회 근거와 사람 검토로 이어지는 연결을 설명합니다.',
                                         '첫날 준비한 Notion 학습노트에 개념·참고 자료·실습 산출물·검증 결과를 연결해 기록합니다. 관계 모델, 판단 근거, 명세, 검증 결과, 이번 인계 기록을 학습노트에서 함께 찾아볼 수 있게 정리합니다. 수업 계정에서 Notion 연결과 쓰기 권한이 검증된 경우에만 MCP 연동을 쓰고, 연결되지 않았으면 output에 정리한 Markdown을 Notion 학습노트에 직접 붙여 정리합니다. MCP로 기록하지 않았다면 연결했다고 적지 않습니다.'),
                               ('실전반',8,'교대 담당자의 미완료 업무·재고와 입고 예정·모순을 구분하고 다음 확인 행동을 정합니다.',
                                         'Notion 학습노트에 핵심 개념·실습 결과·참고 출처를 연결합니다. 조회·판단·검토·실행 확인에 쓴 자료와 산출물을 이후에도 다시 찾아 쓸 수 있게 정리합니다. 수업 환경에서 쓸 수 있으면 MCP로 기록을 반영하고, 그렇지 않으면 output에 작성한 Markdown을 Notion 학습노트에 직접 붙여 완성합니다. MCP로 반영하지 않았다면 연결했다고 적지 않습니다.')]:
        print(build(course,day,emphasis,notebook))
