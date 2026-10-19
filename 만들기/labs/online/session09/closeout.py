"""9회차 문서 마감. 시작 근거와 기존 메타 본문은 보존한다."""
from helpers import *
import collections, subprocess

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')

# 기존 렌더를 전쪽 시각 검토한 결과. 실습 실행 증거가 아니다.
dump(EV/'visual-review.json',dict(deck_pages=74,document_pages=45,total_pdf_pages=119,deck_sheets=9,document_sheets=12,method='전쪽 PDF 렌더의 제목·본문·표·그림·쪽나눔·여백 시각 확인. 잘림·겹침 발견 없음. 원본 대비 화면 변경은 문법을 고친45장뿐.',actual_lab_execution=False))

# 재생성 없이 현재 PDF 원문과 낭독본을 다시 대조한다.
pairs=[(I.parent/'낭독본/통합반_09일차_낭독본.md',I.parent/'통합반_09일차_대본.pdf'),(I/'실습_낭독합본.md',I/'통합반_09일차_실습대본.pdf')]
labs=sorted(p for p in (C/'산출물/실습/통합반_온라인').glob('09일차_실습*') if p.is_dir())
pairs += [(p/'강사대본.md',p/'강사대본.pdf') for p in labs]
fresh=[]
norm=lambda s:re.sub(r'\s+','',s)
for src,p in pairs:
 md=speech(src.read_text('utf8')) if src.name=='강사대본.md' else src.read_text('utf8')
 expected='\n'.join(re.sub(r'^#{1,3} ','',para.strip()) for para in md.strip().split('\n\n') if para.strip())
 pages=[]
 for i,page in enumerate(PdfReader(p).pages,1):
  lines=page.extract_text().splitlines()
  if lines and lines[0].strip()==str(i):lines=lines[1:]
  pages.append('\n'.join(lines))
 assert norm(expected)==norm('\n'.join(pages)),p
 fresh.append(dict(source=str(src),pdf=str(p),pages=len(pages),exact_text_match=True))
for i,lab in enumerate(labs,4):
 src=next(I.glob(f'{i:02}_실습_*.md'))
 assert src.read_bytes()==(lab/'강사대본.md').read_bytes()
 spoken=lambda s:norm('\n'.join(l for l in s.splitlines() if not l.startswith(('#','>','---'))).replace('**',''))
 assert spoken(src.read_text('utf8'))==spoken((I/'낭독본'/src.name).read_text('utf8'))
 assert all(html.escape(para.strip().removeprefix('## ').removeprefix('# ').removeprefix('> ')) in (lab/'안내.html').read_text('utf8') for para in src.read_text('utf8').strip().split('\n\n'))
dump(EV/'pdf-current-check.json',fresh)

t=json.loads((EV/'timing.json').read_text('utf8'))
reportname='2026-10-19_9회차_점검결과.md'
common=f'''## 2026-10-19 통합반9 문서 검증 마감 — 현재 상태

사용자의 현재 목표인 ‘실전반·통합반 지금 하던 작업 마무리’에 따라 이미 작성된 통합반9의 검증과 마감을 완료했다. 아래 중단 기록은 당시 상태이며 이 최신 기록으로 갱신한다. 통합반8·실전반8의 완료 산출물316개는 기존 최종 해시와 모두 일치한다. 실전반 온라인은8회차까지이며 실전반9를 만들지 않았다. 통합반10은 새로 시작하지 않았다.

최신 원본: 통합반 D:/work/study/hyd-integrated-recovered-20261018 (codex/integrated-recovered-01-07 / b3bcf04), 실전반 D:/work/study/hyd-portal-latest-20261014 (codex/practical-sessions-01-07 / 9a7f4f9). 두 폴더는 분리 유지한다. 과거 C 경로는 역사적 기록에서만 새 통합반 D 경로로 매핑해 읽는다.

통합반9은74장·이론70발화 블록을 모두 보존하고5블록을 다듬었다. 화면은45장의 중복 목적어만 수정했다. 빈 실습4개를 승인절차 작도→긴급대응 작도→시스템 연결→실행기록 확인으로 작성했다. 앞 결과 이어 쓰기, 강사의 직접 작성·확인·수정·재확인·저장·재열기 기준을 유지했다. PPTX·노트·분할/합본/낭독본·PDF7개119쪽·랩 HTML4개·ZIP4개·복사자료9개를 동기화하고 정적 검증했다. 이론 낭독 추정98.021091→98.086545분(+3.927273초), 대기90초 별도. 실측이나 전체 수업 시간이 아니다.

시작 근거는 양쪽 .evidence/session09/의 before-*.json 및 git-start-*.json이며 재생성하지 않는다. 상세 근거는 실전반 루트 .evidence/session09/에 있다. 기존 미커밋 CLAUDE.md·포털·시스템 수정, 다른 회차와 역사적 근거를 보존했다. 실제 실습·학생 코드/테스트·AI 시연·HYD/DB·브라우저 실습·캡처는 하지 않았고 커밋·푸시도 하지 않았다.

남은 범위: 통합반10~11은 랩 포함 전체 마감 전이다. 앞서 실전반에 이론을 사용한 것을 랩 마감으로 해석하지 않는다. 실전반6의 09_실습_사전검사와배포.md와 만들기/labs/online/session06/labs.py에는 일부러 부품·조건을 비우는 절차가 남아 있어 ‘억지 실패 재현 금지’와 불일치한다. 이번9에는 복제하지 않았다. 기존6은 수정하지 않았으며 추후 수정 시 덱·대본·랩·PDF·ZIP을 함께 동기화해야 한다. 따라서 과거 모든 문장까지 같은 기준이라고 단정하지 않는다.

방향·세부 기준은 기존 1_목적과_방향.md와 2_기준.md가 정본이다. 컨텍스트 요약은 보조다. 재개 시 최신 인계→실제 Git 상태→불변 시작 근거→현재 진행 기록→검증 결과 순서로 확인한다. 단순 목표 시간이나 장수를 맞추기 위한 삭제·늘리기, 성공 선기입, 가상 학생 응답은 금지한다.

[9회차 상세 결과·최종 파일](근거/{reportname})

---

'''
meta=[]
def prepend(p,text,key):
 prefix=text.encode('utf8');old=p.read_bytes() if p.exists() else b''
 backup=EV/'meta-before'/key
 if old.startswith(prefix):
  assert backup.exists();old=backup.read_bytes()
 else:
  assert not backup.exists(),backup
  backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(old)
  p.write_bytes(prefix+old)
 assert p.read_bytes()==prefix+old
 meta.append(dict(path=str(p),prefix_bytes=len(prefix),old_sha256=hashlib.sha256(old).hexdigest()))
for root,course in [(C,'통합반'),(D,'실전반')]:
 for name in ['인계_통합반_회차별_점검.md','3_현황.md','4_만드는_법.md','6_남은_일.md']:
  prepend(root/'문서/교재'/name,common,course+'/'+name)
prepend(I/'제작기록.md',f'''# 통합반9 제작·문서 검증 마감 — 2026-10-19

74장 유지, 이론70블록 중5개 조정, 실습4개 작성. 화면45장 문법 정정 외 화면73장 픽셀 동일. 이론 낭독 추정98.021091→98.086545분, 실습 발화 합계17.101818분. 모두 실측·수업 총시간과 구별한다. 분할/합본/낭독본·노트·PDF·HTML·입력자료·ZIP을 동기화했다. 실제 실행은 하지 않았다. 아래 기록은 이전 제작 당시 상태다.

[상세 결과]({C.as_posix()}/문서/교재/근거/{reportname})

---

''','통합반/제작기록.md')
dump(EV/'meta-preservation.json',meta)

files=set()
for p in [I,C/'만들기/decks/integrated/day09']:
 files.update(f for f in p.rglob('*') if f.is_file())
for sub in ['교재/대본','교재/PPTX','교재/PDF']:
 files.update(f for f in (C/'산출물'/sub/'통합반_온라인').glob('통합반_09일차*') if f.is_file())
files.update(f for f in (I.parent/'낭독본').glob('통합반_09일차*') if f.is_file())
for p in (C/'산출물/실습/통합반_온라인').glob('09*'):
 files.update(f for f in p.rglob('*') if f.is_file()) if p.is_dir() else files.add(p)
artifacts=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
dump(EV/'artifact-manifest.json',artifacts)
counts=dict(sorted(collections.Counter(p.suffix.lower() for p in files).items()))
links=[]
for label,rel in [('PPTX','산출물/교재/PPTX/통합반_온라인/통합반_09일차.pptx'),('덱 PDF','산출물/교재/PDF/통합반_온라인/통합반_09일차.pdf'),('이론 대본 PDF','산출물/교재/대본/통합반_온라인/통합반_09일차_대본.pdf'),('실습 대본 PDF','산출물/교재/대본/통합반_온라인/09회차/통합반_09일차_실습대본.pdf'),('분할 대본·구성표','산출물/교재/대본/통합반_온라인/09회차/구성표.md'),('랩4개 ZIP·HTML·PDF','산출물/실습/통합반_온라인/09회차_실습_안내.md')]:
 assert (C/rel).exists();links.append(f'- [{label}]({C.as_posix()}/{rel})')
edits=json.loads((EV/'speech-edits.json').read_text('utf8'))
editrows='\n'.join(f"| {e['slide']} | {e['before']} | {e['after']} | {e['reason']} |" for e in edits)
labrows='\n'.join(f"| {x['file']} | 0→{x['after_minutes']:.6f}분 |" for x in t['practice'])
report=f'''# 통합반9 점검·실습 작성 결과

2026-10-19. 현재 작성 중이던 통합반9의 문서 검증을 마감했다. 실전반 온라인은8회차까지이며 신규 실전반9는 없다. 8회차 산출물316개의 현재 해시는 기존 최종 목록과 일치한다. 통합반10~11은 이번 마감 범위가 아니며 새로 시작하지 않았다. 실제 실습 성공을 검증한 보고서가 아니다.

## 시작 기준·범위

통합반: `{C.as_posix()}` / codex/integrated-recovered-01-07 / b3bcf04ba73414f835c00218b2c6067d317e7f.
실전반: `{D.as_posix()}` / codex/practical-sessions-01-07 / 9a7f4f9449cacb7f9797033d1e97a7843375bbd3.
정확한 전체 HEAD는 git-start-*.json 및 최종 감사 기록을 따른다.

시작 해시 통합반8704개·실전반10145개를 각각 고정했다. 당시 미커밋 상태406건·36건(실전36에는 새 session09/start.py 포함). 범위 밖 기존 파일과 역사적 검증 근거를 보존하며, 지정 메타 문서는 원래 본문 바이트 앞에 최신 기록을 붙였다. 커밋·푸시는 하지 않았다. 두 작업 폴더와 서로의 옛 과정 사본을 섞지 않았다.

양쪽 최신 실라버스 SHA-256은9a18ffcd600748ace8a9e58fef417459cb7968de94a862f2d28515460cfa86df로 동일하다. 통합반 온라인9 행89~95의 이론35/25/25분, 실습35/45/40/35분과 구성표를 대조했다. 이론3개 전체와 덱74장을 함께 읽고, 이론43~67의 실습 소개→실습4개→이론68~74의 복습·용어·퀴즈·정답 순서를 보존했다. 실전반6의 통합반9 대응 자료는 참고만 하고 수정하지 않았다.

## 변경량·낭독 추정

| 항목 | 전→후 |
|---|---|
| 슬라이드 | 74→74, 삭제0 |
| 이론 발화 | 70블록 보존, 5블록 수정(7.14%) |
| 화면 | 45장 문법만 수정; 나머지73장 픽셀 동일 |
| 이론 낭독 추정 | {t['before_minutes']:.6f}→{t['after_minutes']:.6f}분 (+{t['delta_seconds']:.6f}초) |
| 실습 대본 | 빈4파일→완성 대본4개 |

산식은 이전 회차와 같은 `(한글 음절 수 + 숫자 문자 수×1.6 + 영문자 수×0.6) / 275`이다. 제목·비낭독 메모·마크다운 장식 제외, 영문(한글 독음)은 독음으로 계산한다. 퀴즈 대기90초는 별도다. 이론 배정85분보다13.086545분 큰 추정이지만 시간을 맞추기 위해 본론을 자르거나 늘리지 않았다. 실제 조작·생성·대기·재시도 시간이나 전체 수업 시간, 실측이 아니다.

| 시작 장 | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
{editrows}

핵심 개념·사례·조건·예외·복습·용어·퀴즈3개·정답을 전부 유지했다. 무조건 분기 설명과 BPMN 표준의 예외를 함께 보존했다. 전체74장 발표자 노트와 대본이 일치하며 구성.json의 PPTX 해시도 최종본과 같다.

## 실습4개

승인절차는 다운로드·압축 해제·VS Code에서 입력 읽기부터 작은 승인 그림을 직접 만들고 ID·선·끝을 확인한다. 긴급대응은 그 결과를 이어 받아3레인·정상/미달/거절·비중단형 승인 지연 타이머를 추가한다. 시스템 연결은 실제 ID와 역할·부품·조건·기한을 맞추고 실제 검사 결과에 따라 수정·재검사하며 등록과 배포를 구별한다. 실행기록 확인은 배포 판본과 사건·처리 건을 연결하고 승인 대기·접수·전달·명령·효과·결과를 구별한다. 네 실습 모두 저장·다시 열기까지 이어진다.

| 실습 발화 파일 | 동일 산식 추정 |
|---|---|
{labrows}

실습 발화 합계17.101818분. 원래 빈 파일 대비 증가이며 실습 수행 시간 추정이 아니다. 가상 학생 답변·성공 결과 선기입·억지 실패 재현을 넣지 않았다. input/output은 직접 기록할 빈 양식이다. reference의 BPMN·매핑·SVG는 제공 비교 자료이며 수업에서 직접 만든 결과가 아니다. 복사9파일은 최신 통합반 원본과 바이트가 같다. 기준 흐름과 수업 흐름은 과거/미래 버전으로 단정하지 않는다. 실제 환경의 배포·권한·부품과 실행 결과는 미확인이다.

## 산출물·검증

산출물 {len(artifacts)}파일(원본 덱·그림·분할/합본/낭독본·구성·제작 기록·배포 자료 포함). 도구·검증 이미지·보고서·현황 문서는 제외한다. 확장자별 {counts}. 파일별 바이트와 SHA-256은 실전반 루트 .evidence/session09/artifact-manifest.json에 있다.

- PPTX1개74장: 원본70발화 블록 대응·무누락, 노트74개 일치, 내부 관계·그림·레이아웃·테마 보존. 화면 변경45장만 존재.
- PDF7개119쪽: 덱74쪽·이론31쪽·실습 합본6쪽·개별 랩8쪽. 대본6PDF 원문 일치, 덱 원본 대비 텍스트/픽셀 차이45장만 확인. 전119쪽 렌더 배치를 시각 확인했다.
- 랩 HTML4개 로컬 링크, ZIP4개 총61파일의 목록·바이트 일치. 안내 HTML·강사 대본·낭독본 대응도 확인했다.
- 복사9자료 원본 해시 일치. JSON 파싱, BPMN ID·참조·매핑·타이머(승인 작업 부착·비중단·PT10M), 제작 도구 Python AST만 정적 검사했다. 학생 코드·테스트를 실행하지 않았다.
- 기존18,849개 시작 해시에서 누락·허용 범위 밖 변경 없음. CLAUDE.md·포털·시스템·다른 회차·과거 근거 보존. 메타 이전 본문은 별도 바이트 보존 검사했다.

현재 실행 금지 범위인 실제 실습·AI 시연·HYD/DB 연결·브라우저 실습·캡처는 모두 미수행이다. PDF 렌더와 문서 검증을 실행 성공으로 표현하지 않는다.

## 기준의 일관성과 후속 항목

1회차 제작 기록과 기존 목적·기준·인계를 대조하여 같은 내용 보존·강사 수행·전체 파생물 검증 기준을 적용했다. 다만 실전반6 `09_실습_사전검사와배포.md`와 제작 도구 `만들기/labs/online/session06/labs.py`에 일부러 부품·조건을 비우는 안내가 남아 있다. 현재 금지 기준과 불일치하므로 과거 모든 문장이 일관적이라고 주장하지 않는다. 이번9에는 복제하지 않았고 기존6은 보존했다. 후속 수정은 관련 모든 파생물 동기화가 필요하다.

통합반10~11은 랩 포함 전체 마감 전이다. 실전반7~8에 이론이 조립됐다는 사실은 원본 랩 완료의 근거가 아니다. 이번에는 새 회차를 시작하지 않았다.

## 최종 파일

{chr(10).join(links)}

## 재현·근거

정적 검증 명령(PowerShell):

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/roede/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'D:/work/study/hyd-portal-latest-20261014/만들기/labs/online/session09/verify.py' 'D:/work/study/hyd-integrated-recovered-20261018'
```

start.py와 before 파일은 재생성하지 않는다. assemble.py도 완료된 원본 수정을 다시 적용하지 않는다. 최종 근거는 실전반 루트 `.evidence/session09/`의 timing.json, speech-edits.json, final-check.json, pdf-current-check.json, visual-review.json, source-materials.json, meta-preservation.json, artifact-manifest.json, closeout-check.json이다. 양쪽 시작 Git·해시를 분리 보존했다.
'''
# 전체 HEAD는 실제 시작 근거에서 삽입한다.
report=report.replace('b3bcf04ba73414f835c00218b2c6067d317e7f',json.loads((EV/'git-start-integrated.json').read_text('utf8'))['head'])
for root in [C,D]:write(root/'문서/교재/근거'/reportname,report)
print(json.dumps(dict(artifacts=len(artifacts),counts=counts,pdf_pages=sum(x['pages'] for x in fresh)+74,meta=len(meta)),ensure_ascii=False))
