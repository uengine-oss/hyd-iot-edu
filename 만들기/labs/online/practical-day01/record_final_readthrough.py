"""최종 문서 검증·인계와 재생성용 가이드 원본 보존. 실습 실행 없음."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
B=ROOT/'산출물/실습/실전반_온라인'
S=ROOT/'산출물/교재/대본/실전반_온라인/01회차'
for folder in B.glob('01일차_실습*'):
 dest=HERE/'templates'/folder.name;dest.mkdir(parents=True,exist_ok=True)
 for name in ['가이드.html','채울_화면.md']:shutil.copy2(folder/name,dest/name)
latest='''## 2026-10-18 최신 최종 재독 — 힌트는 사고 질문, 답은 탐색 뒤 해설

이 절이 아래 이전 제작 이력보다 우선한다. 이론 3개·실습 4개 전체를 재독하고 윤문했다. 다운로드→압축 해제→VS Code 폴더 열기부터 강사가 혼자 관찰·가설·질문·검토를 진행한다. 학생 응답을 기다리거나 실제로 받지 않은 AI 응답을 대사로 꾸미지 않는다. 조작·입력·관측별 분기는 비낭독이다.

- 힌트16곳을 관찰·비교·가설을 유도하는 질문으로 수정했다. 정답 필드·구현 규칙을 주던 토글은 자기 관찰과 근거를 채우는 요청 예시로 바꿨다. 관계그림의 수치도 원문에서 직접 찾도록 바꿨다. 강사의 해설은 자료 탐색과 질문 뒤에 둔다. 기존 결과 비교는 구현 이후 별도 검증 자료다.
- 실습3은 빈 함수1개, 고정 입출력·자료2개·검사4개. 기본 대화4단계로 입력 파악→자기 가설→다른 입력으로 기준 재검토→작은 구현을 진행한다. 테스트 기대값과 완성본을 시작 때 먼저 열지 않는다.
- 실습2 ZIP에는 전체 시스템이 없다. `환경_준비_안내.md`에서 사전 준비한 HYD 저장소 루트로 새 창을 여는 절차를 명시했다. 실습4에는 판단 근거인 HM-8 매뉴얼을 포함했다.
- 시간은 **50/45/55/55분, 실습 합205분**. 원배정130분보다75분 많으며 설명을 줄이지 않았다. 설치·복구·AI 응답 지연은 별도이고 실제 낭독·학생 완주 실측은 하지 않았다. 이론 낭독104.9분·사고 시간65초는 별도 산식이다.
- 실습 PDF **16쪽**, 이론 PDF **32쪽**을 다시 생성했다. 두 PDF 모두 원문 텍스트 일치와 전쪽 렌더 배치를 확인했다. 실습 대본의 파란 영역은 비낭독 조작·분기다.
- PPTX **78장**, 대본74블록. 발표자 노트를 최신 이론 대본으로 갱신하고 노트 XML 이외 모든 ZIP 항목의 바이트 일치를 확인했다. 공통 본문·그림은 그대로다. 기존 보호 대상433파일의 해시도 그대로다.
- 가이드4개·화면 빈자리25곳·요청 토글25개·별도 기존 결과 비교 토글1개. 다운로드 ZIP4개를 갱신했다. 화면·AI 응답·실행 성공을 새로 확인한 것으로 표시하지 않는다.

**직접 실습·테스트 실행·브라우저 조작·캡처는 수행하지 않았다.** 새 시작본 구현의 실행 성공을 보증하지 않는다. 이번 검증은 문서 대응·Python 구문·ZIP 무결성·PDF/PPTX 및 보호 파일 비교다. 커밋·푸시하지 않았다.

원본은 D: 공개 `산출물/`과 `만들기/`다. C: `b1c146d11b60f1f8091eefb8764f86a00a73a0e8` 공통 원본과 통합반은 수정하지 않는다. `.evidence/practical01/output/`은 이전 체크포인트이므로 공개 최신 파일에 덮어쓰지 않는다. 현재 가이드는 `만들기/labs/online/practical-day01/templates/`에도 보존했다. `refine_question_hints.py`는 이미 적용한 일회성 수정이므로 재실행하지 않는다.

검토 기록: `만들기/labs/online/practical-day01/전체대본_최종검토.md`. 검증: `.evidence/practical01/final-readthrough-check.json`, `document-only-check.json`, `notes-refresh-check.json`, `pdf-check.json`, `practice-script-render/check.json`. 진입점: `산출물/실습/실전반_온라인/01회차_실습_안내.md`.

---

'''
for p in [ROOT/'문서/교재/인계_통합반_6회차_시작.md',S/'제작기록.md',S/'실습_검증범위.md']:
 p.write_text(latest+p.read_text('utf-8'),'utf-8')
p=HERE/'전체대본_최종검토.md'
p.write_text(p.read_text('utf-8')+'\n## 후속 통합 수정·최종 검증\n\n'+latest,'utf-8')
p=HERE/'README.md';p.write_text(p.read_text('utf-8')+'\n## 최신 재독 판본\n\n최신 상태는 `전체대본_최종검토.md`의 후속 통합 검증을 따른다. 현재 실습205분·PDF16쪽·이론104.9분·PDF32쪽이다. 가이드 질문형 힌트 수정과 재생성 원본 보존 완료. `preserve_reviewed.py`의 기록 문구는 이전 판본이며 최신 인계를 갱신하는 데 재사용하지 않는다.\n','utf-8')
print('Final review, handoff, validation scope and reviewed guide templates saved')
