from helpers import *
data=json.loads((EV/'finish11-check.json').read_text('utf8'));copies=json.loads((EV/'finish11-copies.json').read_text('utf8'))
report='''# 통합반11·실전반8 문서 마감 — 2026-10-19

두 과정의 마지막 온라인 회차를 함께 마감했다. 전체 목표의 마지막 보존·배정·산출물 감사는 별도로 계속한다.

통합반11의 이론64장을 실전반8에 온전히 대응했다. 두 과정 이론·덱 전체, 실습6개, 최신 실라버스와 구성표를 대조했다. 사례의 지식·값·출처, 제안과 승인·실행·업무 완료의 구분, 조건·예외·복습·용어·퀴즈3개·정답을 보존했다. 분량 목표에 맞춘 축약·늘리기는 없다.

| 과정 | 장수 전→후 | 수정 발화/전체 | 낭독 추정 전→후 |
|---|---:|---:|---:|
'''
for r in data:report+=f"| {r['course']}{r['day']} | 64→64 | {len(r['changed_blocks'])}/59 | {r['before_minutes']:.6f}→{r['after_minutes']:.6f}분 |\n"
report+='''
산식은 한글1·숫자1.6·영문0.6 가중음절/275, 괄호 속 한국어 발음 치환 등 앞 회차와 동일하다. 실제 녹음 또는 전체 수업 시간이 아니며 학습 대기80초와 조작·응답 시간은 별도다. 통합반 이론 변화는 +0.873초, 실전반은 같은 가중 글자 수라 추정 변화0초다.

통합반 발화1·2·21·41~42·58은 강사가 직접 만드는 주체와 실제 실습 전후의 시점을 분명히 했다. 두 과정29장 발화는 정상 결과 설명을 정상 경로 옆에 배치해, 회복 미달 경로도 정상 보고라는 오해를 없앴다. 화면48장은 준비된 연결·실제 처리 결과·미확인 범위를 명시했다. 나머지 화면은 보존하고 모든 발표자 노트128장을 현재 대본과 맞췄다.

통합반의 빈 랩6개를 작성했다. 실전반은 지식구조·제안에이전트·흐름실행3개에서 ZIP의 코드 폴더와 앞 실습의 결과를 이어 받을 input 위치를 구체화했다. 빈 양식으로 앞 결과를 덮어쓰지 않는다. 업무명세→지식구조→제안에이전트→흐름실행→제품 시연 관찰→지식자산화 순서다. 다운로드·압축 해제·VS Code·직접 작성과 설정·근거 확인·실제 문제 수정·재확인·저장·재열기를 포함했다. 참조 완성본의 일정 생성까지 실제로 수행했다고 쓰지 않는다. 준비된 읽기·제안·사람 확인·보고의 작은 범위와 예제의 확장 범위를 구별했다.

| 과정·랩 | 발화 낭독 추정 전→후(분) |
|---|---:|
'''
for r in data:
 for lab in r['labs']:report+=f"| {r['course']}{r['day']} {lab['file']} | {lab['before_minutes']:.6f}→{lab['after_minutes']:.6f} |\n"
report+=f'''
덱·원본·노트·분할/합본/낭독본·PDF·랩 HTML·입력자료·ZIP을 동기화했다. PDF18개206쪽(덱128·문서78)의 원문·전쪽 배치를 확인했다. 통합반 덱64쪽과 실전반 표지를 직접 확인했고 나머지63쪽은 두 과정 렌더 픽셀 동일을 검증했다. 문서78쪽 전부 검토했으며 잘림·겹침을 발견하지 않았다.

12개 ZIP은 과정별36/36/36/36/9/8파일, 총322파일로 배포 폴더와 목록·바이트가 일치한다. 복사자료{len(copies)}개의 해시, HTML 로컬 링크, JSON·Python AST 구문, BPMN ID·참조·매핑, 지식 예제의 이름 공간·식별자를 정적으로 확인했다. 실제 학생 코드나 테스트는 실행하지 않았다. 실제 실습·AI·HYD/DB·브라우저 실습·캡처도 하지 않았으며 문서 검증을 실환경 성공으로 해석하지 않는다. 커밋·푸시하지 않았다. 전체 기존 수정 보존 판정은 마지막 감사에 남긴다.

최신 원본과 산출물:
- [통합반11 구성표]({C.as_posix()}/산출물/교재/대본/통합반_온라인/11회차/구성표.md)
- [통합반11 랩 안내]({C.as_posix()}/산출물/실습/통합반_온라인/11회차_실습_안내.md)
- [실전반8 구성표]({D.as_posix()}/산출물/교재/대본/실전반_온라인/08회차/구성표.md)
- [실전반8 랩 안내]({D.as_posix()}/산출물/실습/실전반_온라인/08회차_실습_안내.md)

근거: 실전반 루트 `.evidence/finalize20261019/finish11-edits.json`, `finish11-check.json`, `finish11-pdf-check.json`, `finish11-copies.json`, `finish11-visual.json` 및 `review11-index.json`. 생성 도구는 `만들기/labs/online/finalize20261019/finish11.py`, 검증은 `verify11.py`다. 이미 실행한 생성 도구와 시작 스냅샷은 재실행하지 않는다. 기존 session08 등 역사적 기록은 보존한다. 현재 원본을 고친 뒤 파생물을 갱신하며 이전 C 경로를 실행 경로로 쓰지 않는다.
'''
name='2026-10-19_통합반11_실전반8_마감.md'
write(EV/'finish11-visual.json',json.dumps(dict(pdf_count=18,pages=206,document_pages=78,deck_pages=128,integrated_deck_viewed=list(range(1,65)),practical_deck_viewed=[1],practical_deck_pixel_identical_to_integrated=list(range(2,65)),document_contact_sheets_viewed=list(range(1,21)),clipping_or_overlap_found=False),ensure_ascii=False,indent=2))
for root,course,day in [(C,'통합반',11),(D,'실전반',8)]:
 write(root/'문서/교재/근거'/name,report)
 p=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차/제작기록.md';write(p,f'## 2026-10-19 마지막 회차 문서 마감\n\n64장·59발화 보존, 랩6개 동기화, PDF18개206쪽 전쪽 확인. 상세: [{name}]({(root/"문서/교재/근거"/name).as_posix()}). 전체 감사는 계속한다. 실제 실행·커밋·푸시 없음.\n\n---\n\n'+p.read_text('utf8'))
write(EV/'progress.md',(EV/'progress.md').read_text('utf8')+'\n\n## 통합반11·실전반8 문서 마감 완료\nfinish11.py 실행 완료(재실행 금지), verify11.py 통과. 18PDF206쪽 원문·전쪽 배치 확인, ZIP12개322파일 바이트 일치. 보고서 양쪽 기록. 다음 전체19회차84랩 감사와 기존 수정·역사적 근거 보존 검사 및 전체 최종 인계. goal 아직 active.\n')
print(name)
