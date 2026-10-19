from pathlib import Path
import json,re,hashlib
D=Path('D:/work/study/hyd-portal-latest-20261014');C=Path('D:/work/study/hyd-integrated-recovered-20261018');EV=D/'.evidence/online-revision-20261019'
rows=json.loads((EV/'metrics.json').read_text('utf8'));audit=json.loads((EV/'whole-audit.json').read_text('utf8'));sync=json.loads((EV/'sync.json').read_text('utf8'));matrix=json.loads((EV/'review-matrix.json').read_text('utf8'))
assert not audit['issues']
report='''# 온라인 두 과정 랩 후속 개정 — 2026-10-19

## 이번 마감 범위

통합반 1–11회차와 실전반 1–8회차의 기존 84개 랩을 개정하고 문서·파생물을 동기화했다. 신규 회차 제작은 하지 않았다. 이번에 1477장 이론 전체를 새로 전수 재독했다는 의미는 아니다. 기존 이론 검토를 보존하고 랩 연결·반복·자료·진행 대본을 검토했다. 제조 사례로 바뀐 통합반11/실전반8 이론 연결 발화도 함께 수정하고 발표자 노트와 낭독본을 맞췄다.

시간은 내용의 결과다. 50분·240분 등 배정 시간을 채우려고 분량을 늘리지 않는다. 실라버스의 공식 시간표 원문은 보존했으며 실제 영상 길이로 인용하지 않는다. 이하 숫자는 발화 원고의 같은 산식에 따른 추정이다. 조작·자료 판독·모델 응답·수정 시간이 포함된 실제 수업 시간은 실행·리허설하지 않아 확정하지 않았다.

## 실제 바뀐 진행과 난이도

1. 첫 실전 코딩은 목적만 아는 상태에서 시작한다. 제공 프로젝트의 실제 자료·현재 기능·미구현 부분을 AI와 탐색하고, 요구사항과 계획을 정한 다음 기록 연결 검사와 근거 보고서를 만든다. 이미 아는 파일 구조를 전제로 정밀 프롬프트부터 던지지 않는다. 기존 참조본과 수업 시작본도 구분했다.
2. 다음 랩은 탐색 절차 전체를 재강의하지 않는다. 앞 결과를 이어 쓰면서 온톨로지의 관계·출처, 판단 규칙의 조건, 수집 결과의 원문 대조, 스킬의 출력 계약, 행동 기준과 회귀 검증, 업무 프로세스의 상태·승인 등 해당 단계에서 새로 결정할 것을 다룬다. 짧은 도구 조작 단계는 연결된 업무의 준비 단계이며 독립적인 대형 실습으로 포장하지 않는다.
3. 통합반11·실전반8은 HYD-02 계획 정비를 준비하는 제조 업무로 연결했다. 생산 일정, 연속 작업 시간, 부품 가용 수량, 오일 준비, 담당 인력, 완료 기한을 대조한다. 주간 후보는 생산 충돌, 다음 야간 후보는 기한 초과로 제외되는 이유를 확인하고, 처음에는 보류했던 야간 후보를 후속 자료에 따라 다시 판단한다. 규칙·절차·회의 기록·생산 CSV·자원 CSV·후속 확인 자료를 사용하며 단문 회의 요약으로 끝내지 않는다. 날짜·작업 시간 등은 교육용 설정임을 표시했다.
4. 위 판단을 명세→지식 구조→근거를 갖춘 제안 에이전트→사람 확인과 보고를 포함한 흐름으로 이어 간다. 제안·승인·현장 정비 완료를 구별하며 미확인 자원을 임의로 확정하지 않는다. 제공 예제를 복사한 결과를 직접 구현한 것으로 설명하지 않는다.
5. 기존 제조 회의 스킬은 서로 다른 회의의 후속 상태와 중복 조치까지 대조하도록 보완했다. 납기 확인과 구매 완료, 서로 다른 설비의 점검 상태를 합치지 않는다. 그래프·판단 실습의 정상 자료를 망가뜨리는 오류 재현은 실제 의미·조건 대조로 바꿨다. 교육용 결손 입력은 그 목적을 표시하고 유지했다.
6. 긴 준비 목록은 제작용 비낭독으로 이동했다. 다운로드→압축 해제→VS Code 열기는 짧게 보여 주고 작업으로 이어 간다. 학생 가이드 배포·학생 응답·코드 줄별 해설을 중심에 두지 않는다. 복습과 조건·예외는 의미가 있을 때 유지한다.

## 수치와 산식

덱은 1477장→1477장으로 유지했다. 19회차·84랩 개정 및 동기화. 발화 수는 문장 구두점이 아닌 **빈 줄로 나눈 낭독 문단**으로 계산했다. 제목·인용 지시문·굵게 표시를 제외한 전후 문단을 SequenceMatcher로 대응하여 달라진 이전 문단과 이후 문단을 각각 집계한다. 이동·통합·분할 때문에 두 수는 다를 수 있다. 개별 파일과 수치는 metrics.json, 편집 이유와 전후 원문은 edits.json에 남겼다.

낭독 추정 = (한글 음절 수 + 숫자 수×1.6 + 영문 글자 수×0.6) / 275. 영문 용어 뒤 한글 독음은 기존 규칙으로 한글 독음만 세고 제목·비낭독 지시문을 제외한다. 선택 발화가 남아 있으면 포함될 수 있다. 실제 전체 진행 시간이나 적정 영상 길이의 실측이 아니다.

| 과정·회차 | 장수 전→후 | 랩 수 | 랩 발화 추정 전→후(분) | 바뀐 이전→이후 발화 문단 |
|---|---:|---:|---:|---:|
'''
for r in rows:report+=f"| {r['course']}{r['day']} | {r['slides']}→{r['slides']} | {r['labs']} | {r['before']:.1f}→{r['after']:.1f} | {r['old_changed_paragraphs']}→{r['new_changed_paragraphs']} |\n"
report+='''
## 검증 결과와 한계

- 전체 문서 감사: 19회차·1477장·84랩·2556개 산출물 파일 확인, 덱/노트/분할/합본/낭독본 대응·덱 PDF 원문·로컬 HTML 링크·ZIP 목록과 파일 바이트 불일치 0건.
- 이번 생성 PDF 원본 105종 270쪽: 원문 정확 일치, 전쪽 렌더와 9개 전쪽 배치표로 여백·잘림·겹침 확인. 기존 덱 PDF는 화면 내용 변경 없이 유지하며 본문 대응을 정적으로 검사했다. 전체 153 PDF 2632쪽이라는 감사 수는 기존 문서와 복사본도 포함하므로 새로 렌더한 수와 구별한다.
- Python AST·JSON·XML/BPMN 233개 정적 구문 검사 오류 0건. 학생 코드 import·실행이나 테스트 성공을 뜻하지 않는다.
- 실전반8 원본대응은 통합반11 64장. 최신 실라버스의 해당 회차 활동과 구성표·배정 자료를 대조했으며 공식 실라버스 파일은 수정하지 않았다.
- 시작 해시 1430개/1280개 기준 삭제 0, 교재·랩 작업 범위 밖 변경 0. CLAUDE.md 및 포털·DB·시스템 관련 기존 변경은 보존했다. 시작 브랜치와 HEAD를 유지했으며 커밋·푸시하지 않았다. 과거 .evidence 및 before.json을 다시 생성하거나 일괄 경로 치환하지 않았다.
- 실제 학생 코드·테스트·AI 시연·HYD/DB 접속·브라우저 실습·캡처는 수행하지 않았다. 교육적 설계와 문서 정합성 마감이며 모든 환경에서의 성공·실측 시간·수강 효과를 보증하는 표현은 사용하지 않는다. 이미지는 후속 촬영 범위다.

## 재현과 근거

두 루트의 분할 대본이 원본이다. 실전반 최신 루트에서 `python 만들기/labs/online/revision20261019/sync.py`로 현재 원본만 합성하고, `finish_checks.py`와 `metrics.py`로 문서·정적 검사를 재현한다. 과거 콘텐츠 생성기는 이번 원고를 덮을 수 있으므로 현행 원본 재생성에 쓰지 않는다.

근거: D:/work/study/hyd-portal-latest-20261014/.evidence/online-revision-20261019/ 아래 edits.json, review-matrix.json(84개), metrics.json, preservation.json, syntax.json, sync.json, whole-audit.json, whole-artifacts.json, visual-pages.json, overview/.

## 랩별 검토 목적

| 과정·회차 | 랩 | 이번 진행의 목적 |
|---|---|---|
'''
for r in matrix:report+=f"| {r['course']}{r['day']} | {r['lab']} | {r['purpose'].replace(chr(10),' ')} |\n"
name='2026-10-19_온라인_랩_후속개정.md'
for root in [C,D]:
 p=root/'문서/교재/근거'/name;p.write_text(report,encoding='utf8')
 notice=f'> 2026-10-19 후속 개정 문서 마감: 두 과정 19회차·84랩 대본과 파생물 동기화 및 정적 검증 완료. 시간은 내용에 따라 정하며 고정 시간 채우기 금지. 실제 실행·촬영·전체 시간 실측은 미수행. [상세 보고](근거/{name}). 아래 기록은 당시 이력으로 보존한다.\n\n'
 for filename in ['3_현황.md','5_결정_기록.md','6_남은_일.md','인계_통합반_회차별_점검.md']:
  p=root/'문서/교재'/filename;p.write_text(notice+p.read_text('utf8'),encoding='utf8')
 p=root/'문서/교재/4_만드는_법.md';p.write_text('> 최신 원본: 회차별 분할 대본과 현재 랩 자료. 파생물 갱신은 실전반 D:/work/study/hyd-portal-latest-20261014/만들기/labs/online/revision20261019/sync.py 사용. 옛 콘텐츠 생성기는 후속 개정 원고를 덮을 수 있으므로 실행하지 않는다.\n\n'+p.read_text('utf8'),encoding='utf8')
 p=root/'문서/교재/온라인_최종산출물_목록.md';s=p.read_text('utf8');s=notice+s+'\n## 후속 개정 실습 낭독 합본\n\n'
 for r in rows:
  rr=C if r['course']=='통합반' else D;pdf=rr/f"산출물/교재/대본/{r['course']}_온라인/{r['day']:02}회차/{r['course']}_{r['day']:02}일차_실습대본.pdf";s+=f"- [{r['course']} {r['day']}회차 실습 대본 PDF]({pdf.as_posix()})\n"
 p.write_text(s,encoding='utf8')
for r in rows:
 root=C if r['course']=='통합반' else D;p=root/f"산출물/교재/대본/{r['course']}_온라인/{r['day']:02}회차/제작기록.md";s=p.read_text('utf8') if p.exists() else ''
 p.write_text(f"> 2026-10-19 후속 개정: {r['labs']}랩 원고·HTML·PDF·ZIP 동기화. 발화 추정 {r['before']:.1f}→{r['after']:.1f}분, 변경 문단 {r['old_changed_paragraphs']}→{r['new_changed_paragraphs']}. 덱 {r['slides']}장 유지. 문서·정적 검증이며 실행·촬영·시간 실측 아님. 상세: {root.as_posix()}/문서/교재/근거/{name}\n\n"+s,encoding='utf8')
for rel in ['산출물/실습/실전반_온라인/01회차_시간견적.md','산출물/실습/실전반_온라인/01회차_시간과흐름_재검토.md','산출물/실습/실전반_온라인/01회차/실습과제_운영안.md']:
 p=D/rel;r=next(x for x in rows if x['course']=='실전반' and x['day']==1)
 p.write_text(f"> 최신 후속 개정: 1회차 랩 발화 추정 {r['after']:.1f}분(전체 진행 시간 아님). 아래 고정 견적·질문 횟수·학생 활동 전제는 과거 기록이며 현재 운영 지시로 쓰지 않는다. 현행 원고는 회차별 분할 대본과 실습 안내를 따른다. 상세: {D.as_posix()}/문서/교재/근거/{name}\n\n"+p.read_text('utf8'),encoding='utf8')
print('closeout records written')
