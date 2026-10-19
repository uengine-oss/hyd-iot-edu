"""윤문 산출물의 재생성 원본과 최신 제작기록을 저장한다."""
from pathlib import Path
import shutil, json

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
BASE=ROOT/'산출물/실습/실전반_온라인'
assert (HERE/'검토기록.md').exists(),'윤문 완료 후 실행'
for folder in BASE.glob('01일차_실습*'):
    target=HERE/'templates'/folder.name;target.mkdir(parents=True,exist_ok=True)
    for name in ['가이드.html','채울_화면.md']:
        shutil.copy2(folder/name,target/name)
scripts=ROOT/'산출물/교재/대본/실전반_온라인/01회차'
check=json.loads((ROOT/'.evidence/practical01/practice-script-render/check.json').read_text('utf-8'))
p=scripts/'제작기록.md'
old=p.read_text('utf-8')
latest=f'''# 실전반 온라인 1회차 — 최신 문서 제작 결과

2026-10-18 사용자 범위 변경 반영. 직접 실습 실행·브라우저 조작·캡처를 하지 않고 랩·가이드·대본을 수정했다. 화면은 나중에 채울 자리로 남겼다. 따라서 아래 이전 기록의 포털 승인 대기·실제 촬영 대기는 이번 작업의 미완료 조건이 아니다.

## 이번 범위에서 제공한 것

- 실습 가이드4개, 후속 화면 자리25곳, 상황별 접이식 프롬프트23개. 단계별 조작·학생 질문·힌트·확인 기준·후속 장면을 연결했다.
- 학습노트 입력틀·환경 확인표·사건 연결표·관계 검토표. 실습3은 포털 처리 과정의 참조 비교를 작은 코드로 이해하는 응용이다. 기존 기록과 교육용 가림 자료를 구분한다.
- 실습 대본4개를 다운로드·압축해제·VS Code 폴더 열기부터 강사 단독 진행하는 방식으로 고쳤다. 학생 답변을 기다리지 않고 강사가 판단과 AI 응답 검토를 보여 준다. 발화에서 불필요한 제작 설명을 빼고 조작 지시를 비낭독으로 분리했다. 가이드 화면ID와 연결하고 윤문했다. 반복된 자동 설명을 합쳤으며 필요한 개념·판정 기준은 유지했다. 실제 수행한 것으로 들리는 표현을 후속 촬영 안내와 구별했다.
- 실습 대본 PDF {check['pages']}쪽, 원문 텍스트 일치. 실제 화면과 대화가 있는 완성 영상으로 표현하지 않는다.
- 실습 설계50/40/50/50분 합190분. 원배정130분 대비+60분. 설명을 시간에 맞춰 줄이지 않았다. 실제 완주·응답 지연은 미측정이다.
- 기존 이론 PPTX78장·PDF32쪽·74대본 블록·이론103.3분/학습대기65초 유지. 이론 본문·그림과 통합반 원본, D: 시스템 수정은 변경하지 않았다.

## 검증 범위와 후속 화면

문서·파일 대응·화면ID·코드 구문만 검사했다. 사용자 변경 지시 뒤 새 실습 실행은 하지 않았다. 코드 실행 결과와 저장 사건은 앞선 검증 범위만 인용한다. 앱 화면, 실제 Copilot 대화, 학생 완주를 새로 확인했다고 보고하지 않는다.

가이드의 `채울_화면.md`에 해당 장면과 확인 기준을 남겼다. 후속 캡처는 사용자가 다시 요청할 때 수행한다. 원본 발췌의 미확인 연결을 임의로 채우거나 허구의 화면을 넣지 않는다.

공개 수정 원본은 D: `산출물/`이다. 윤문 재생성 원본은 `만들기/labs/online/practical-day01/templates/`이며 `build_guides.py`가 복사한다. 이전 staging은 덮어쓰지 않는다. 검토 근거는 같은 제작 폴더의 `검토기록.md`, 문서 검사는 `.evidence/practical01/document-only-check.json`, PDF 검사는 `practice-script-render/check.json`이다.

커밋·푸시하지 않았다. C: 공통 원본에는 쓰지 않았다.

---

## 아래는 범위 변경 전 제작 이력

'''
p.write_text(latest+old,encoding='utf-8')
print('Reviewed guide sources and latest production record saved')

