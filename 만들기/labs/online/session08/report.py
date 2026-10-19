"""검증된 8회차의 보고서와 최신 인계 접두 기록. 과거 본문은 바이트 그대로 보존."""
from helpers import *
import subprocess,collections
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')
t=json.loads((EV/'timing.json').read_text('utf8'));check=json.loads((EV/'final-check.json').read_text('utf8'))
assert len(check['labs'])==10 and check['preservation']['all_unrelated_work_preserved']
assert (EV/'visual-review.json').exists()
reportname='2026-10-18_8회차_점검결과.md'
common=f'''## 2026-10-18 8회차 문서 검증 마감 — 현재 기준

통합반8 점검과 실전반8 조립을 완료했다. 실전반8은 최신 실라버스·구성표를 대조하여 통합반11 이론 전체 64장을 배정했다. 통합반8은 61장 전부 유지했다. 양쪽 이론 발화는 각각 5개만 주체·연결·낭독 표현을 조정했으며, 본론·사례·조건·예외·복습·용어·퀴즈·정답을 보존했다. 통합반 실습4개, 실전반 실습·시연6개를 작성하고 모든 파생 산출물을 동기화했다.

최신 원본은 서로 분리된 다음 경로다.
- 통합반: D:/work/study/hyd-integrated-recovered-20261018 — codex/integrated-recovered-01-07 / b3bcf04
- 실전반: D:/work/study/hyd-portal-latest-20261014 — codex/practical-sessions-01-07 / 9a7f4f9

이번 작업에서 커밋·푸시는 하지 않았다. 시작 시 미커밋 상태는 통합반376건·실전반10건이며, CLAUDE.md와 포털·시스템 변경을 포함한 범위 밖 파일을 보존했다. 실전반 .evidence/session08/before.json은 이번 시작 기준이며 재생성하지 않는다. 두 루트의 .evidence/session08/baseline-integrated.json 또는 baseline-practical.json과 시작 Git 기록으로 분리 확인할 수 있다. 과거 .evidence·before.json 및 C 경로 기록은 수정하지 않았다.

문서 검증 범위: PPTX2개, PDF16개196쪽(덱125쪽·대본71쪽), 랩10개 HTML·ZIP, 복사자료104개. 덱/노트/대본 대응, PDF 원문·전쪽 렌더 배치, 로컬 링크, ZIP 목록·파일 바이트, 자료 해시와 정적 구문·참조를 확인했다. 이론 낭독 추정은 통합반78.063→78.092분(+1.745초), 실전반 원본94.743→94.758분(+0.873초). 목표 시간에 맞춘 삭제·늘리기는 하지 않았다. 추정은 실측이나 전체 수업 시간이 아니다.

실제 실습·학생 코드/테스트·AI 시연·HYD/DB 접속·브라우저 실습·캡처는 모두 미수행이다. 참조 자료의 미연결 값과 실행 환경은 수업에서 확인해야 한다. 통합반11 이론 재사용은 통합반11 랩 전체 마감을 뜻하지 않는다. 통합반11의 원래 실습 파일은 이번에 수정하지 않았다.

남은 일: 사용자의 다음 요청에서 통합반9부터 점검한다. 9회차는 시작하지 않았다. 통합반9~11의 랩을 포함한 회차별 마감은 별도이며, 실전반 온라인1~8회차 문서 검증과 실제 실행 검증은 구분한다. 기존의 다른 미완료 작업은 아래 이력에 남긴다.

[8회차 상세 결과·산출물·재현 명령](근거/{reportname})

---

'''
meta=[]
for root,course,folder in [(C,'통합반',I),(D,'실전반',P)]:
 for name in ['인계_통합반_회차별_점검.md','3_현황.md','6_남은_일.md','4_만드는_법.md']:
  p=root/'문서/교재'/name;old=p.read_bytes()
  if old.startswith(common.encode('utf8')):continue
  backup=EV/'meta-before'/course/name;backup.parent.mkdir(parents=True,exist_ok=True)
  assert not backup.exists();backup.write_bytes(old)
  p.write_bytes(common.encode('utf8')+old);meta.append(dict(path=str(p),prefix_bytes=len(common.encode('utf8')),old_sha256=hashlib.sha256(old).hexdigest()))
 production=f'''# 8회차 제작·검증 기록 — 2026-10-18

{course}8의 이론 전체와 실습 대본을 함께 점검했다. 강사 단독 진행, 앞 결과 이어 쓰기, 실제 결과 미선기입, 실패 강제 재현 금지 기준을 적용했다. 덱·노트·분할/합본/낭독본·PDF·랩 안내·입력자료·ZIP을 동기화하고 정적 문서 검증을 마쳤다. 실제 실행은 하지 않았다.

[상세 보고서]({root.as_posix()}/문서/교재/근거/{reportname})

'''
 p=folder/'제작기록.md';old=p.read_bytes() if p.exists() else b''
 if not old.startswith(production.encode('utf8')):
  backup=EV/'meta-before'/course/'제작기록.md';backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(old)
  p.write_bytes(production.encode('utf8')+old);meta.append(dict(path=str(p),prefix_bytes=len(production.encode('utf8')),old_sha256=hashlib.sha256(old).hexdigest()))
dump(EV/'meta-preservation.json',meta)
artifacts=[]
for root,course,kind in [(C,'통합반','integrated'),(D,'실전반','practical')]:
 base=root/'산출물';files=set()
 for p in [root/f'산출물/교재/대본/{course}_온라인/08회차',root/f'만들기/decks/{kind}/day08']:
  files.update(f for f in p.rglob('*') if f.is_file())
 for sub in ['교재/대본','교재/PPTX','교재/PDF']:
  p=base/sub/f'{course}_온라인';files.update(f for f in p.glob(f'{course}_08일차*') if f.is_file())
 files.update(f for f in (base/f'교재/대본/{course}_온라인/낭독본').glob(f'{course}_08일차*') if f.is_file())
 for f in (base/f'실습/{course}_온라인').glob('08*'):
  files.update(x for x in f.rglob('*') if x.is_file()) if f.is_dir() else files.add(f)
 for f in sorted(files):artifacts.append(dict(course=course,path=str(f),bytes=f.stat().st_size,sha256=sha(f)))
dump(EV/'artifact-manifest.json',artifacts)
counts=collections.Counter(Path(x['path']).suffix.lower() for x in artifacts)
rows=[]
for course,v in t.items():
 rows.append(f"| {course} | {v['slides_before']}→{v['slides_after']} | {len(v['changed_speech_blocks'])}/{v['blocks']} | {v['before_minutes']:.6f}→{v['after_minutes']:.6f} | +{v['delta_seconds']:.6f}초 |")
labrows='\n'.join(f"| {c} | {p['file']} | 0→{p['spoken_minutes']:.6f}분 |" for c,v in t.items() for p in v['practice'])
edits=json.loads((EV/'speech-edits.json').read_text('utf8'))
editrows='\n'.join(f"| {e['course']} {e['slide']} | {e['before']} | {e['after']} |" for e in edits)
links=[]
for root,course in [(C,'통합반'),(D,'실전반')]:
 for label,rel in [('PPTX',f'산출물/교재/PPTX/{course}_온라인/{course}_08일차.pptx'),('덱 PDF',f'산출물/교재/PDF/{course}_온라인/{course}_08일차.pdf'),('이론 대본 PDF',f'산출물/교재/대본/{course}_온라인/{course}_08일차_대본.pdf'),('실습 대본 PDF',f'산출물/교재/대본/{course}_온라인/08회차/{course}_08일차_실습대본.pdf'),('분할 대본·구성표',f'산출물/교재/대본/{course}_온라인/08회차/구성표.md'),('랩10종 중 해당 과정 ZIP·HTML 안내',f'산출물/실습/{course}_온라인/08회차_실습_안내.md')]:
  assert (root/rel).exists();links.append(f'- [{course} {label}]({root.as_posix()}/{rel})')
report=f'''# 8회차 통합반 점검·실전반 조립 결과

2026-10-18. 문서 제작과 정적 검증을 마감했다. 실제 수업·실행 성공을 검증한 보고서가 아니다. 9회차는 미착수이며 커밋·푸시는 하지 않았다.

## 시작 기준과 원본 배정

통합반 루트: `{C.as_posix()}` / `codex/integrated-recovered-01-07` / `b3bcf04ba73414f83595c00218b2c6067d317e7f`.
실전반 루트: `{D.as_posix()}` / `codex/practical-sessions-01-07` / `9a7f4f9449cacb7f9797033d1e97a7843375bbd3`.

시작 Git 변경376건·10건은 이번 작업 이전 상태다. 17,632개 파일의 시작 해시를 고정했고 통합반8·실전반8 및 지정 메타 문서 밖 기존 파일의 누락·예상 밖 변경은0이다. 기존 미커밋 수정의 상태를 초기화하거나 되돌리지 않았다. CLAUDE.md·포털·시스템 수정, 다른 회차, 과거 검증 근거도 보존했다. 메타 문서는 새 기록을 앞에 붙이고 이전 본문 바이트를 그대로 보존했다.

양쪽 `문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx` SHA-256은 `9a18ffcd600748ace8a9e58fef417459cb7968de94a862f2d28515460cfa86df`로 같다. 통합반 온라인8 행79~84(이론40+30, 실습40/50/35/45), 실전반 온라인8 행89~96(이론30+30, 실습30/30/30/30/40/20)을 구성표와 대조했다. 실전반8 원본은 통합반11이다. 통합반11 이론 전체64장과 실습 안내·제품 사례·마무리·복습·용어·퀴즈3문항·정답을 빠짐없이 원순서로 옮겼다. 원본대응.json에64장 대응을 기록했다. 이번에 통합반11의 원래 실습6파일을 수정하거나 전체 마감으로 표시하지 않았다.

## 덱·이론 변경량과 낭독 추정

| 과정 | 장수 전→후 | 수정 발화/전체 발화 블록 | 낭독 추정 전→후(분) | 변화 |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

실전반의 변경 전은 배정 원본 통합반11이다. 실전반8은 새 조립본이다. 두 과정 모두 삭제한 슬라이드·이론 발화 블록0개. 통합반은 화면 XML·그림·레이아웃·테마 전체 유지, 실전반은 표지 과정명만 변경했다. 전체125장 발표자 노트는 최종 대본과 일치한다. 실전 압축을 이유로 본론을 생략하지 않았다.

동일 산식: `(한글 음절 수 + 숫자 문자 수×1.6 + 영문자 수×0.6) / 275`. 제목·제작 메모·마크다운 장식 제외, 영문(한글 독음)은 독음으로 계산한다. 전후 동일 추출·계산 함수를 사용했다. 퀴즈 대기80초씩은 별도이며 위 값에 포함하지 않았다. 실습 동작·작성·검토·접속·대기·재시도 시간을 포함한 전체 수업 시간이 아니다. 실측도 아니다. 실라버스 이론 배정70분·60분보다 각각8.092분·34.758분 큰 추정이지만, 시간에 맞추어 내용을 자르거나 늘리지 않았다.

통합반 수정5블록(30,31~32,33~34,35~36,37~38), 실전반 수정5블록(1,2,21,41~42,58). 실제 문자열 조정은9건·8건이다. 강사 단독 수행 주체, 녹화 구간 연결, 실습에서 실제 남긴 기록을 읽는 표현을 고쳤다. 개념·조건·예외·사례를 삭제하지 않았다. 빈 실습 파일을 가리키던 비낭독 제작 메모와 empty_practice 구성 종류는 현재 상태에 맞췄다.

| 과정·시작 슬라이드 | 전 | 후 |
|---|---|---|
{editrows}

## 랩 변경10개

통합반8 원래 실습4파일은0바이트였다. 행동 기준5경우 작성→같은 입력·설정에서 반복 검증→실제 실패 근거에 따른 수정과 전체 회귀→세 출처의 교대 인수인계 흐름으로4개를 작성했다. 7회차의 실제 프로젝트를 이어 쓰되 없을 때 참조 예제로 작성한 범위를 구분한다. 비교 도구는 JSON 차이만 찾는 참조이며 실행기·자동 합격 판정기가 아니다. 실패를 만들기 위한 데이터 변조나 결과 선기입은 없다.

실전반8은 원본 통합반11의 비어 있던 실습6항목에 대응하여 업무 명세→작은 지식 구조→읽기와 제안 에이전트→작은 흐름→ProcessGPT 관찰→지식 자산화 대본6개를 작성했다. 같은 회의 준비 업무의 앞 결과를 다음 단계에서 이어 쓴다. 외부 일정 등록·초대 발송은 이번 작은 업무의 완료 결과에 넣지 않는다. 참조 예제의 일정 생성 구조와 실제 수업에서 만드는 범위를 명세로 구분한다.

모두 다운로드→압축 해제→VS Code 작업 공간→직접 작성·설정→결과·근거 확인→수정·재확인→저장·다시 열기 흐름이다. 억지 문답·가상 학생 응답은 없다. 코드/output의 파일은 빈 작성 양식이며 실행 성공 결과가 아니다.

| 과정 | 신규 실습 발화 파일 | 낭독 추정 전→후 |
|---|---|---:|
{labrows}

실습 발화 추정 합계: 통합반 {sum(x['spoken_minutes'] for x in t['통합반']['practice']):.6f}분, 실전반 {sum(x['spoken_minutes'] for x in t['실전반']['practice']):.6f}분. 원래 빈 파일 대비 증가이며 실습 수행 시간 추정이 아니다.

자료 구별: 통합반 인수인계의 이벤트·정비·부품3 JSON은 수업용 가상 입력이다. 사건/정비 시각과 조회 시각을 구분하고, 과거 정비를 현재 경보 해소로 읽지 않으며, 다른 설비의 부품을 무조건 합치지 않는다. 필드는 저장소 이벤트·ent.maintenance_history·ent.spare_stock 구조를 정적으로 대조했다. 실전반 example_meeting 복사본은 참조이며 실제 에이전트 ID·도구·extract 경로의 미연결 자리가 남아 있다. load_graph.py는 원래 저장소 scripts/ontology_v2.py를 필요로 하므로 단독 실행을 보장하지 않는다. 작업 위치·check/load/ask 순서를 안내하되 실행하지 않았다. Notion은 실제 연결과 쓰기 권한 확인 시에만 진행하며 수동 Markdown 정리 경로도 명시했다.

## 산출물과 검증

최종 산출물 목록은 artifact-manifest.json에 파일별 크기·SHA-256과 함께 기록했다. 제작 원본·그림·분할/합본/낭독본·구성/제작기록·배포 자료를 포함한 {len(artifacts)}파일이며, 검증 이미지·도구·본 보고서·상태 문서는 이 수에서 제외했다. 확장자별: {dict(sorted(counts.items()))}.

- PPTX2개:61장·64장, 내부 관계·노트125장·원본 대응 확인. 원본 대비 화면 렌더 차이는 통합반0쪽, 실전반 표지1쪽뿐이다.
- PDF16개196쪽: 덱2개125쪽, 이론 합본2개51쪽, 실습 합본2개10쪽, 개별 랩10개10쪽. 대본14개는 원문과 추출 텍스트 일치. 덱2개는 원본 PDF 전쪽 텍스트 비교(표지만 예외)와 이미지 비교. 전196쪽 렌더를 시각 확인했고 내용 잘림·겹침을 발견하지 않았다.
- HTML10개와 ZIP10개: 안내의 로컬 링크 존재, ZIP 목록과 풀린 모든 파일 바이트 일치. 참조 폴더도 HTML에서 바로 찾을 수 있다.
- 원본 복사104개: 원본/복사본 SHA-256 일치. JSON 파싱, Python AST 구문만 검사, CSV 열수, BPMN ID·연결·매핑 참조와 그래프 이름 공간·ID를 정적 확인했다. 학생 코드나 테스트를 import/실행하지 않았다.
- 각 구성표·랩 인덱스 링크, 구성.json PPTX 해시와 노트/대본 일치 확인. 과거 근거 파일은 재생성·일괄 경로 치환하지 않았다.

공식 제품 설명은 [ProcessGPT 저장소](https://github.com/uengine-oss/process-gpt)를 문헌으로 확인했다. 문헌 확인은 제품 시연·연결 검증과 다르다.

## 최종 파일

{chr(10).join(links)}

## 근거와 문서 검증 재현

현재 근거 루트: `{EV.as_posix()}`. before.json(불변 시작 해시), git-integrated.txt/git-practical.txt, syllabus.json, speech-edits.json, timing.json, 원본 백업 before/, source-materials.json, pdf-check.json, visual-review.json, final-check.json, artifact-manifest.json, meta-preservation.json을 함께 읽는다. 두 작업 폴더별 baseline 파일은 각 루트 `.evidence/session08/`에 있다. 과거 C 경로 근거는 읽을 때만 새 통합반 D 루트로 매핑한다.

아래는 문서 정적 검증 재현 명령이다. 학생 코드·DB·AI 시연을 실행하지 않는다. start.py 및 역사적 before.json은 다시 만들지 않는다.

```powershell
Set-Location 'D:/work/study/hyd-portal-latest-20261014'
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/roede/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' '만들기/labs/online/session08/verify.py' 'D:/work/study/hyd-integrated-recovered-20261018' --render
```

실제 실습·학생 코드/테스트 실행·AI 시연·HYD/DB 접속·브라우저 실습·캡처는 하지 않았다. 자료의 정적 검증과 문서 렌더만으로 실행 성공을 주장하지 않는다. 다음은 요청을 받은 뒤 통합반9 점검이며 이번에는 시작하지 않았다.
'''
for root in [C,D]:write(root/'문서/교재/근거'/reportname,report)
print(json.dumps(dict(artifacts=len(artifacts),extensions=dict(counts),metadata_updates=len(meta)),ensure_ascii=False))
