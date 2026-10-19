"""검증된 2회차 결과와 인계 갱신. 기존 기록은 아래에 보존."""
from pathlib import Path
import sys,json,shutil,re
D=Path(__file__).resolve().parents[4];C=Path(sys.argv[1]);EV=D/'.evidence/session02'
t=json.loads((EV/'timing.json').read_text('utf8'));i=t['integrated'];p=t['practical'];checks=json.loads((EV/'final-check.json').read_text('utf8'));assert checks['renders'][0]['integrated_all72_pixel_identical']
def write(f,s):f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s,encoding='utf8')
def prepend(f,s):
 old=f.read_text('utf8') if f.exists() else ''
 if old.startswith(s.splitlines()[0]):old=old.split('\n---\n\n',1)[1]
 write(f,s+'\n---\n\n'+old)
summary=f'''## 2026-10-18 2회차 마감 — 통합반 점검·실전반 조립·문서 검증 완료

2회차의 덱·분할 이론/실습 대본·낭독본·PDF·실습 안내/입력자료/ZIP까지 완료했다. 실제 실습·학생 테스트·AI 시연·시스템·브라우저·캡처는 하지 않았다. 다음 작업은 사용자가 요청할 때 3회차다. 이번에 통합반 3회차를 전체 완료 처리하지 않았다.

최신 통합반은 `{C.as_posix()}`, 최신 실전반은 `{D.as_posix()}`에 있다. 기존 미커밋 변경과 다른 회차를 보존했다. 커밋·푸시하지 않았다. D의 옛 course 통합반과 C의 옛 실전반 day02 조립본을 최신 원본으로 사용하지 않는다.

| 항목 | 통합반 2회차 | 실전반 2회차 |
|---|---|---|
| 덱 | 72장 유지, 화면 전부 픽셀 동일 | 107장 = 통합반2 전체72 + 통합반3 본문4~33의30 + 안내·정리5 |
| 이론 발화 | 68블록 중8 수정 | 103블록, 이론4단위 |
| 낭독 추정 | {i['before_minutes']:.4f}→{i['after_minutes']:.4f}분, {i['delta_seconds']:.1f}초 | 원본 전체합 {p['full_source_minutes']:.4f}→{p['minutes']:.4f}분, +{p['added_vs_full_source_seconds']:.1f}초 |
| 실습 | 기존 활동4개를 강사 진행 대본으로 작성 | 공통4개 + SOP·DMN 조건표1개 |
| 대본 PDF | 이론34쪽·실습4쪽 | 이론52쪽·실습6쪽 |
| 배포 | 가이드·ZIP 각4개 | 가이드·ZIP 각5개 |

원래 실라버스 이론 배정은 통합반115분, 실전반95분이다. 실전반의 실제 대본 추정은 183.1분으로 원배정보다88.1분 길다. 내용을 모두 보존해 조립한 결과이며 시간을 맞추려고 삭제하거나 보충으로 채우지 않았다. 분당275 가중음절 산식이며 실측이 아니다. 학습 대기145초/173초와 실제 실습 조작 시간은 별도이고, 전체 수업 길이는 계산·실측하지 않았다.

진행은 통합반 1~65장→실습4개→66~72장, 실전반 1~65장→공통 실습4개→66~97장→조건표 실습→98~107장 정리다. 실전반에서는 중간 목차·종결 인사를 반복하지 않고 전체 목표·목차를 한 번 제시한다. 서로 다른 회차의 개념을 중복이라고 가정해 삭제하지 않는다. 통합반3의 BSC/KPI 본론은 실전반3 배정으로 남긴다.

검증: 179장 발표자 노트 원문 일치, PPTX 내부 참조, 원본 대응102장과 공통 화면 본문99장 일치(표지·목표·목차3장은 통합 편집), 통합반72장 화면 픽셀 동일, 대본 PDF13개 원문 일치·전쪽 렌더, ZIP9개 공개 파일 바이트 일치. 기준 파일16,275개와 대조해 범위 밖 변경·누락 없음. 근거: D `.evidence/session02/final-check.json`, `timing.json`, `pdf-check.json`, `visual-review.json`.

상세 변경: `문서/교재/근거/2026-10-18_2회차_점검결과.md`. 각 반 `산출물/실습/…/02회차_실습_안내.md`에서 자료에 진입한다. 아래의 1회차 및 과거 미완료 기록은 이 최신 상태에 우선하지 않는다.
'''
changes='\n'.join(f"| {x['block'].replace('## ','')} | {x['before_minutes']:.4f} | {x['after_minutes']:.4f} | {(x['after_minutes']-x['before_minutes'])*60:+.1f}초 |" for x in t['integrated_changed_blocks'])
detail=summary+f'''
## 실제 수정 내용

통합반의 클래스·인스턴스·센서와 물리량·카디널리티·식별자·자료형/제약·Cypher 조회/집계/병합/검증을 화면과 대본으로 함께 검토했다. 화면의 핵심 설명·예제는 유지했다. 원본 68발화 중60개는 그대로이며, 8개(11.8%)에서 분할 촬영 때의 “다음 시간” 표현, 반복 도입, 학생에게 넘기던 실습 소개를 자연스러운 강사 진행으로 바꿨다. 개념 삭제는 없다. 덱 노트는 최종 대본으로 갱신했다.

| 발화 블록 | 이전 추정 분 | 이후 추정 분 | 차이 |
|---|---:|---:|---:|
{changes}

실전반은 최신 조립본을 신규 작성했다. 단순한 “72→107장 증가”는 비교 기준이 아니다. 실제 비교 기준은 채택한 원본 전체인 72+30=102장·98발화이고, 조립본은107장·103발화다. 공통 본문99장의 화면 내용·그림 참조는 단원 번호와 장 번호 외에 동일하다. 원본 3장의 표지·목표·목차는 합친 범위로 고쳤다. 추가5장은 조건표 실습 간지·설명2장, SOP/DMN 용어1장, 적용 퀴즈·정답2장이다. 원본 통합반3의 표지·목표·목차는 공통 메타정보에 통합했으며, 본문4~33장은 모두 사용했다. 표준 SOP 구성, 안전 조건, Step/Action, DMN 입력/비교/경계/AND·OR/출력/Hit Policy/누락·중복·상충/근거/저장 구조를 생략하지 않았다.

원본대응.json에 원본 회차·장과 목적 장을 기록했다. 2회차의 복습·용어·퀴즈7장은 98·99·101~104·106장으로 옮겼고, 새 SOP 정리를 사이와 마지막에 배치했다. 8개 대단원을 먼저 다룬 뒤 SOP·DMN 단원을09~13으로 이어 갔다. 표지·목차 외 발화 변경은 연결·단원 번호·실습 삽입·마무리에 국한한다. 원본 전체합182.7658분에서183.1396분으로 +0.20%, +22.4초다.

## 실습에서 바뀐 점

기존 실습 자체를 이번에 실행하거나 새로 성공시킨 것이 아니다. 통합반의 빈 분할 실습 대본4개에 기존 활동을 강사가 어떻게 진행할지를 작성했고, 그 대본과 입력자료를 실전반에도 적용했다. 자료 다운로드→압축 해제→VS Code 폴더 열기→작성→검토·수정→저장·재열기의 흐름이다. 개념은 ID를 정할 때, 관계를 쓸 때, 결과를 검사할 때 필요한 만큼 연결했다. 학생 응답을 가정하는 문답이나 AI가 특정 답을 내놓았다는 허구는 넣지 않았다.

| 실습 | 만들고 남길 것 | 검토할 기준 |
|---|---|---|
| 관계 조회 | 직접 작성한 질의와 조회 기록 | 원래 행·서로 다른 대상·집계 결과 대조, 값 누락 구별 |
| 기준 지식 탐색 | ID·종류·방향·근거 연결 기록 | 나가는/들어오는 관계, 기준 지식과 현재 진단 결과 구별 |
| 온톨로지 설계 | 요구사항·schema.json·graph.json·자료 검토 | 기존 원자료의 중복·별칭·단위 혼입·누락, 설비별 센서와 공용 부품 |
| 그래프 구현·검증 | 적재/조회 질의·검증 기록·오류 검토 사본 | 원자료 질문의 답, 재적재 중복, 형은 맞지만 의미가 틀린 연결 |
| 실전반 조건표 | 원문 조건표·경계 사례 판단 기록 | 온도·압력 경고, 시간 감점, 수동/트립 제외, 중첩·누락, 승인·수행 조건 |

실습1의 예제 그래프는 기준 시드에서 조회용으로 뽑은17노드·16관계 입력자료다. 실습3은 기존 오프라인 설비 CSV5개와 현장 메모에서 출발하며 완성 그래프를 복사하지 않는다. 설비별 구성 요소·센서는 설비 코드를 포함한 ID로, 공용 예비품은 SKU로 구별한다. 기준 시드의 공통 구성 모델과 다른 이유를 질문 범위로 설명했다. 실습4는 그 결과를 별도 랩 DB에 적재하는 강의 대본이며, 오류 사본은 파일에서만 검토하도록 했다.

실습5는 HM-8 작업 원문과 instances.cypher 규칙 발췌를 함께 제공한다. 시드 출처 절 번호와 교재 HM-8 판본의 절 번호를 임의로 같게 바꾸지 않았다. 압력·트립 조건은 첨부 HM-8에 없는 문장을 만들어내지 않고 규칙 발췌에 근거를 한정했다. 온도55 ℃ 이상/압력165 bar 미만은 경고, 팬100% 24시간 초과는 감점, 원격 자동 아님·트립 중 리셋 외 제어는 제외로 구별한다. 경고·감점이 있다고 실행이 허가되거나 SOP의 제한이 사라지지 않는다는 설명을 유지했다. 사례9개는 제공 입력이며 결과표는 빈칸이다.

실습 낭독 기본값: 통합반 {sum(x['spoken_minutes'] for x in i['practice']):.1f}분, 실전반 {sum(x['spoken_minutes'] for x in p['practice']):.1f}분. 이는 조작·AI 응답·재검토·환경 준비를 제외한 말의 양일 뿐이다. 실라버스 실습 배정125분/145분과 같다고 주장하지 않는다.

## 난이도와 사실 근거

대학4학년이 처음 접하는 도구·개념을 배운다는 기준으로 정의→교재 사례→직접 작성→근거 대조 순서를 유지했다. 그래프 식별자/제약의 역할과 의미 검증을 분리하고, SOP 절차와 DMN 판단, 경고/감점/제외, 승인과 완료 기록을 구별했다. 저장소 코드의 내부 구현을 새로 강의하는 분량은 추가하지 않았다.

- 실라버스: 문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx, 통합반17~23행·실전반17~25행을 읽기 전용 확인.
- 로컬 사실표: C 문서/교재/사실표/통합반_02-04일차_기술사실표.md 및 it/neo4j/v2/schema.json, instances.cypher, scripts/ontology_v2.py.
- 실습 조건의 입력 구조: it/agent/agentsvc/cards.py:97의 실행 코드 목록과 rule:ts1-warn/ps1-warn/auto-mode/trip-reset-only/fan-24h 발췌.
- 일반 개념 확인: [Neo4j MERGE 공식 문서](https://neo4j.com/docs/cypher-manual/4.4/clauses/merge/), [OMG DMN](https://www.omg.org/dmn/). 외부 검색은 사실 확인에만 사용했다.

## 검증 범위와 남은 일

PPTX2개/총179장, 대본 PDF13개/106쪽, 화면 렌더 PDF2개/179쪽, HTML안내9개, 배포ZIP9개를 검증했다. 모든 대본 PDF는 제목·본문을 낭독 원문과 공백 정규화 후 완전 대조했다. 합본·낭독본·발표자 노트의 장 범위는 누락·중복 없이 일치한다. 화면 렌더와 PDF 전쪽을 접촉 시트로 확인했으며, 잘림·겹침·한글 깨짐을 찾지 못했다. 통합반72장은 이전 렌더와 픽셀까지 동일하다. HTML은 정적 구조·본문·파일 참조를 확인했고 브라우저로 열지 않았다.

실제 랩 접속, 질의 실행, Copilot 응답, 학생 테스트와 캡처는 미수행이다. 접속 주소·DB·인증과 실제 결과 검증은 수업 환경에서 별도 진행해야 한다. 결과를 성공으로 미리 채우지 않았다. 3회차는 사용자가 요청할 때 새 회차로 점검하며, 이번에 참고한 SOP·DMN 외 통합반3의 나머지 전체 점검을 완료한 것으로 보지 않는다.
'''
# 숫자는 실제 PDF 검사 목록에서 계산한다.
pdfchecks=json.loads((EV/'pdf-check.json').read_text('utf8'));detail=detail.replace('대본 PDF13개/106쪽',f"대본 PDF13개/{sum(x['pages'] for x in pdfchecks)}쪽")
for root,course in [(C,'통합반'),(D,'실전반')]:
 for rel in ['문서/교재/인계_통합반_회차별_점검.md','문서/교재/3_현황.md','문서/교재/6_남은_일.md']:prepend(root/rel,summary)
 write(root/'문서/교재/근거/2026-10-18_2회차_점검결과.md',detail)
 prepend(root/f'산출물/교재/대본/{course}_온라인/02회차/제작기록.md',summary)
 shutil.copy2(EV/f'final-render/{course}_02일차.pdf',root/f'산출물/교재/PPTX/{course}_온라인/{course}_02일차.pdf')
rebuild=f'''## 2026-10-18 2회차 생성·검증

통합반 수정 원본은 C의02회차 분할 MD, 실전반은 D의02회차 분할 MD와 원본대응.json이다. 조립 규칙과 실습5 원본은 D 만들기/labs/online/session02/에 있다. 통합반3 원본과 기존 다른 회차는 수정하지 않는다. 아래 명령은 D 루트에서 수행하며 학생 코드·실습을 실행하지 않는다.

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='{D.as_posix()}/.evidence/session02/deps'
python 만들기/labs/online/session02/assemble.py '{C.as_posix()}'
python '{C.as_posix()}/.claude/skills/lecture-deck/scripts/deck2pptx.py' 만들기/decks/practical/day02/실전반_02일차.md 산출물/교재/PPTX/실전반_온라인/실전반_02일차.pptx
python 만들기/labs/online/session02/build_documents.py '{C.as_posix()}'
python 만들기/labs/online/session02/verify.py '{C.as_posix()}'
```

assemble.py는 통합반에서 실전반을 다시 조립한다. 실전반 분할본만 직접 고친 뒤 무심코 실행하면 변경을 덮으므로 먼저 조립 규칙 또는 실습5 원본에 반영한다. build_documents.py는 분할본을 합치고 노트·낭독PDF·실습 자료·HTML·ZIP을 생성한다. 런타임 Python에는 reportlab/pypdf/pypdfium2/Pillow/lxml/python-pptx가 필요하며 덱 빌더는 pymupdf를 사용한다. 이번 임시 의존성은 D .evidence/session02/deps에 설치했다.

PPTX를 LibreOffice의 별도 프로필로 .evidence/session02/final-render에 PDF 변환한 뒤 verify.py에 --render를 붙여 전쪽 렌더와 이전 통합반 화면 비교를 수행한다. verify.py의 before.json/source-render는 이번 비교의 고정 기준이므로 현재 파일로 덮지 않는다. 원본 변경 후에는 현재 기준과 의도한 차이를 다시 검토한다. close_record.py는 검증 완료 뒤 수치·인계·제작기록·공개 덱 PDF를 갱신한다.
'''
for root in [C,D]:prepend(root/'문서/교재/4_만드는_법.md',rebuild)
print('records closed; public deck PDFs copied')
